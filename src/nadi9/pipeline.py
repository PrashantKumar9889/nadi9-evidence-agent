"""Run one episode: evidence, hypotheses, plan, translate, verify, correct, report."""

from dataclasses import dataclass
from pathlib import Path

from nadi9.budget import Budget
from nadi9.correction import apply_correction
from nadi9.errors import BudgetExceeded, ToolFailure
from nadi9.evidence_store import load_evidence
from nadi9.hypothesis_learner import LearnedState, learn
from nadi9.llm import provider_for_mode
from nadi9.planner import plan_cues
from nadi9.reporting import write_outputs
from nadi9.tools import TranscriptionTool
from nadi9.translator import translate_cue
from nadi9.verifier import verify_subtitle


@dataclass
class RunResult:
    decisions: list[dict]
    reprocessed_ids: list[str]
    learned: LearnedState
    audit: list[dict]
    tool_failures: list[str]
    llm_failures: list[str]
    model_calls: int
    tool_calls: int
    finished_safely: bool
    interview_lemmas: set[str]
    supported_surfaces: set[str]
    quarantined_ids: set[str]
    llm_prompt: str

    def by_id(self, subtitle_id: str) -> dict:
        for decision in self.decisions:
            if decision["subtitle_id"] == subtitle_id:
                return decision
        raise KeyError(subtitle_id)


def run_episode(
    data_dir: str | Path,
    out_dir: str | Path | None = None,
    *,
    mode: str = "mock",
    max_model_calls: int = 25,
    max_tool_calls: int = 50,
    llm: object | None = None,
    transcription_tool: TranscriptionTool | None = None,
) -> RunResult:
    budget = Budget(max_model_calls=max_model_calls, max_tool_calls=max_tool_calls)
    audit: list[dict] = []
    tool_failures: list[str] = []
    llm_failures: list[str] = []
    model = llm if llm is not None else provider_for_mode(mode)
    transcriber = transcription_tool or TranscriptionTool()
    finished_safely = True
    decisions_by_id: dict[str, dict] = {}
    learned: LearnedState | None = None
    reprocessed: list[str] = []
    episode_cues: list[dict] = []

    try:
        # Phase 1: Load and safety-screen all evidence sources
        pack = load_evidence(Path(data_dir), budget, audit, transcriber, tool_failures)
        episode_cues = list(pack.episode)

        # Phase 2: Form hypotheses, drop statistical outliers, resolve lexicon
        learned = learn(pack, model, budget, audit, llm_failures)
        cues = list(pack.episode)

        # Phase 3 & 4: Risk-based planning, translation composition & independent verification (Pass 1)
        for cue in plan_cues(cues, learned):
            decisions_by_id[cue["id"]] = _produce(cue, learned, budget, audit)

        # Phase 5: Dynamic replanning when a mid-episode correction arrives
        reprocessed = apply_correction(learned, pack.correction, decisions_by_id)
        audit.append(
            {
                "kind": "correction_applied",
                "id": None if not pack.correction else pack.correction.get("id"),
                "affected": reprocessed,
            }
        )

        # Phase 6: Targeted re-translation & re-verification of ONLY affected cues (Pass 2)
        by_cue = {cue["id"]: cue for cue in cues}
        for subtitle_id in reprocessed:
            previous = decisions_by_id[subtitle_id]
            updated = _produce(by_cue[subtitle_id], learned, budget, audit)
            updated["first_pass_decision"] = previous["first_pass_decision"]
            updated["reprocessed"] = True
            updated["revision"] = previous["revision"] + 1
            decisions_by_id[subtitle_id] = updated
            audit.append({"kind": "reprocessed", "subtitle_id": subtitle_id})
    except BudgetExceeded as exc:
        finished_safely = True
        audit.append({"kind": "budget_exceeded", "message": str(exc)})
        if learned is not None:
            for cue in episode_cues:
                decisions_by_id.setdefault(cue["id"], _budget_decision(cue))
    except ToolFailure as exc:
        finished_safely = True
        tool_failures.append(str(exc))
        audit.append({"kind": "tool_failure", "tool": "pipeline", "message": str(exc)})

    if learned is None:
        raise ToolFailure("Evidence could not be loaded; see the audit log.")

    ordered = [decisions_by_id[key] for key in sorted(decisions_by_id)]
    if out_dir is not None:
        write_outputs(
            Path(out_dir),
            decisions=ordered,
            learned=learned,
            audit=audit,
            model_calls=budget.model_calls,
            tool_calls=budget.tool_calls,
            reprocessed_ids=reprocessed,
        )
    return RunResult(
        decisions=ordered,
        reprocessed_ids=reprocessed,
        learned=learned,
        audit=audit,
        tool_failures=tool_failures,
        llm_failures=llm_failures,
        model_calls=budget.model_calls,
        tool_calls=budget.tool_calls,
        finished_safely=finished_safely,
        interview_lemmas=set(learned.interview_lemmas),
        supported_surfaces=set(learned.supported_surfaces),
        quarantined_ids=set(learned.quarantined_ids),
        llm_prompt=learned.llm_prompt,
    )


def _produce(cue: dict, learned: LearnedState, budget: Budget, audit: list[dict]) -> dict:
    try:
        draft = translate_cue(cue, learned)
    except Exception as exc:  # one bad line must not kill the episode
        audit.append({"kind": "subtitle_error", "subtitle_id": cue["id"], "message": str(exc)})
        draft = _error_decision(cue, str(exc))
    if draft["nadi_9_text"] is None:
        draft["verifier"] = {"passed": False, "issues": ["abstained before verification"]}
        draft["first_pass_decision"] = draft["decision"]
        audit.append(
            {
                "kind": "subtitle_decided",
                "subtitle_id": cue["id"],
                "decision": draft["decision"],
            }
        )
        return draft
    try:
        budget.tool(f"validate:{cue['id']}")
        audit.append({"kind": "tool_call", "tool": "validate", "target": cue["id"]})
        report = verify_subtitle(
            source_text=draft["source_text"],
            nadi_9_text=draft["nadi_9_text"],
            cue=cue,
            learned=learned,
            start=draft["start"],
            end=draft["end"],
        )
    except BudgetExceeded:
        raise
    except Exception as exc:
        report_issues = [f"verifier error: {exc}"]
        draft["verifier"] = {"passed": False, "issues": report_issues}
        draft["decision"] = "HUMAN_REVIEW"
        draft["review_question"] = "The verifier could not finish. Please review this line by hand."
        draft["confidence"] = min(float(draft["confidence"]), 0.3)
        draft["confidence_reason"] = draft["confidence_reason"] + " Verifier failed closed."
        draft["first_pass_decision"] = draft["decision"]
        return draft

    draft["verifier"] = {"passed": report.passed, "issues": report.issues}
    if not report.passed:
        draft["decision"] = "HUMAN_REVIEW"
        draft["confidence"] = min(float(draft["confidence"]), 0.45)
        draft["confidence_reason"] = (
            draft["confidence_reason"] + " Verifier disagreed, so the line was not approved."
        )
        draft["review_question"] = draft["review_question"] or (
            "Verifier rejected the line: " + "; ".join(report.issues)
        )
        if any("unsupported" in issue for issue in report.issues):
            draft["nadi_9_text"] = None
    draft["first_pass_decision"] = draft["decision"]
    audit.append(
        {
            "kind": "subtitle_decided",
            "subtitle_id": cue["id"],
            "decision": draft["decision"],
            "verifier_passed": report.passed,
        }
    )
    return draft


def _error_decision(cue: dict, message: str) -> dict:
    return {
        "subtitle_id": cue["id"],
        "source_text": cue.get("source", ""),
        "nadi_9_text": None,
        "confidence": 0.1,
        "confidence_reason": f"This line failed closed after an internal error: {message}",
        "decision": "HUMAN_REVIEW",
        "evidence": [],
        "assumptions": [],
        "conflicts": [],
        "review_question": "An internal error stopped this line. Please translate it by hand.",
        "start": cue.get("start", "00:00:00,000"),
        "end": cue.get("end", "00:00:01,000"),
        "speaker": cue.get("speaker"),
        "addressee": cue.get("addressee"),
        "scene": cue.get("scene"),
        "features": [],
        "non_blocking_conflicts": [],
        "reprocessed": False,
        "revision": 1,
    }


def _budget_decision(cue: dict) -> dict:
    decision = _error_decision(cue, "call budget exhausted")
    decision["review_question"] = "The call budget was used up before this line could be checked."
    decision["confidence_reason"] = "Stopped because the model or tool budget was exhausted."
    return decision
