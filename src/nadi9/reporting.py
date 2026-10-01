"""Write the sample-run artifacts a reviewer can open without rerunning code."""

from pathlib import Path
import json

from nadi9.hypothesis_learner import LearnedState


def write_outputs(
    out_dir: Path,
    *,
    decisions: list[dict],
    learned: LearnedState,
    audit: list[dict],
    model_calls: int,
    tool_calls: int,
    reprocessed_ids: list[str],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_srt(out_dir / "subtitles.srt", decisions)
    _write_jsonl(out_dir / "subtitle_decisions.jsonl", decisions)
    (out_dir / "learned_rules.json").write_text(
        json.dumps(_rules_payload(learned), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    review = [_review_item(decision) for decision in decisions if decision["decision"] == "HUMAN_REVIEW"]
    (out_dir / "review_queue.json").write_text(
        json.dumps(review, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "final_report.md").write_text(
        _report(decisions, learned, model_calls, tool_calls, reprocessed_ids),
        encoding="utf-8",
    )
    _write_jsonl(out_dir / "audit_log.jsonl", audit)


def _write_srt(path: Path, decisions: list[dict]) -> None:
    ordered = sorted(decisions, key=lambda item: item["subtitle_id"])
    blocks: list[str] = []
    for index, decision in enumerate(ordered, start=1):
        text = decision["nadi_9_text"] or f"[HUMAN_REVIEW] {decision['source_text']}"
        blocks.append(f"{index}\n{decision['start']} --> {decision['end']}\n{text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _rules_payload(learned: LearnedState) -> dict:
    lexicon = [
        {
            "lemma": entry["lemma"],
            "condition": entry["condition"] or None,
            "nadi": entry["nadi"],
            "pos": entry["pos"],
            "evidence": entry["evidence"],
        }
        for entry in sorted(learned.lexicon.values(), key=lambda item: (item["lemma"], item["condition"]))
    ]
    return {
        "dataset": "SYNTHETIC DEMO. Nadi-9 is fictional and is not a real language.",
        "outlier_examples": learned.outlier_examples,
        "quarantined": learned.quarantined_ids,
        "rules": list(learned.rules.values()),
        "lexicon": lexicon,
        "context_splits": learned.context_splits,
    }


def _review_item(decision: dict) -> dict:
    return {
        "subtitle_id": decision["subtitle_id"],
        "source_text": decision["source_text"],
        "reason": decision["confidence_reason"],
        "review_question": decision["review_question"],
        "conflicts": decision["conflicts"],
        "confidence": decision["confidence"],
        "evidence": decision["evidence"],
    }


def _report(
    decisions: list[dict],
    learned: LearnedState,
    model_calls: int,
    tool_calls: int,
    reprocessed_ids: list[str],
) -> str:
    approved = [item for item in decisions if item["decision"] == "APPROVE"]
    review = [item for item in decisions if item["decision"] == "HUMAN_REVIEW"]
    lines = [
        "# Final report",
        "",
        "SYNTHETIC DEMO. Nadi-9 is fictional. Nothing in this pack is evidence about a real language.",
        "",
        "## Release recommendation",
        "",
        "**DO_NOT_RELEASE**",
        "",
        f"{len(review)} subtitle(s) still need a linguist. "
        "A fluent line is not a substitute for a missing or disputed word.",
        "",
        "## What was learned",
        "",
        f"Outlier examples set aside: {', '.join(learned.outlier_examples) or 'none'}.",
        f"Quarantined items: {', '.join(learned.quarantined_ids) or 'none'}.",
        "",
        "| Rule | Status | Value |",
        "| --- | --- | --- |",
    ]
    for rule in learned.rules.values():
        lines.append(f"| {rule['id']} | {rule['status']} | {rule.get('value') or ''} |")
    lines.extend(
        [
            "",
            "## Subtitles",
            "",
            "| Id | Decision | Confidence | Nadi-9 or review |",
            "| --- | --- | --- | --- |",
        ]
    )
    for decision in decisions:
        shown = decision["nadi_9_text"] or "HUMAN_REVIEW (no invented wording)"
        lines.append(
            f"| {decision['subtitle_id']} | {decision['decision']} | {decision['confidence']} | {shown} |"
        )
    lines.extend(
        [
            "",
            "## Correction",
            "",
            "The linguist correction resolved the question particle to `ke`.",
            "Only question subtitles were translated and verified again: "
            + (", ".join(reprocessed_ids) if reprocessed_ids else "none")
            + ".",
            "",
            "## Review queue",
            "",
        ]
    )
    if not review:
        lines.append("No open review items.")
    for decision in review:
        lines.append(f"- **{decision['subtitle_id']}**: {decision['review_question']}")
    lines.extend(
        [
            "",
            "## Budgets",
            "",
            f"Model calls: {model_calls} / 25.",
            f"Tool calls: {tool_calls} / 50.",
            "",
            "## Why some lines are blank in Nadi-9",
            "",
            "Approved lines are built only from forms that survived the evidence checks.",
            "Lines with a missing word, a status split, or a failed verification do not receive a made-up Nadi-9 word.",
            "",
        ]
    )
    return "\n".join(lines)
