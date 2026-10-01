"""Load the synthetic pack, screen it, and keep source metadata."""

from dataclasses import dataclass, field
from pathlib import Path
import re

from nadi9.budget import Budget
from nadi9.errors import ToolFailure
from nadi9.safety import screen_text
from nadi9.tools import Retriever, TranscriptionTool


_COND_PAIR = re.compile(
    r"COND:([a-z0-9_]+)\s+EN:([a-z ]+?)\s+NADI:([a-z0-9]+)",
    flags=re.IGNORECASE,
)
_PAIR = re.compile(r"EN:([a-z ]+?)\s+NADI:([a-z0-9]+)", flags=re.IGNORECASE)


@dataclass
class EvidencePack:
    data_dir: Path
    manifest: dict
    examples: list[dict]
    grammar_text: str
    grammar_rules: dict[str, str]
    code_switch: set[str]
    dictionary_a: list[dict]
    dictionary_b: list[dict]
    experts: list[dict]
    viewers: list[dict]
    interviews: list[dict]
    interview_pairs: list[dict]
    episode: list[dict]
    correction: dict | None
    quarantined_ids: list[str] = field(default_factory=list)
    source_meta: list[dict] = field(default_factory=list)
    example_reliability: float = 0.9
    dictionary_a_reliability: float = 0.25
    dictionary_b_reliability: float = 0.8
    interview_reliability: float = 0.6
    viewer_reliability: float = 0.35
    grammar_reliability: float = 0.75


def _grammar_sections(text: str) -> tuple[dict[str, str], set[str], float]:
    reliability = 0.75
    match = re.search(r"^reliability:\s*([0-9.]+)", text, flags=re.MULTILINE)
    if match:
        reliability = float(match.group(1))
    rules: dict[str, str] = {}
    sections = re.split(r"^## rule\s+", text, flags=re.MULTILINE)
    for section in sections[1:]:
        lines = section.strip().splitlines()
        title = lines[0].strip()
        body = "\n".join(lines[1:])
        id_match = re.search(r"^id:\s*(\S+)", body, flags=re.MULTILINE)
        rule_id = id_match.group(1) if id_match else title
        rules[rule_id] = body.strip()
    code_switch: set[str] = set()
    code_body = rules.get("code-switch", "")
    listed = re.search(r"English spelling:\s*(.+)", code_body)
    if listed:
        code_switch = {
            part.strip().lower().strip(".,;")
            for part in listed.group(1).split(",")
            if part.strip()
        }
    return rules, code_switch, reliability


def _extract_pairs(interview_id: str, transcript: str, quarantined: list[str]) -> list[dict]:
    pairs: list[dict] = []
    for index, line in enumerate(transcript.splitlines(), start=1):
        screened = screen_text(line)
        if screened.quarantined:
            quarantined.append(f"{interview_id}:line:{index}")
            continue
        conditioned = _COND_PAIR.search(line)
        if conditioned:
            pairs.append(
                {
                    "interview_id": interview_id,
                    "condition": conditioned.group(1).lower(),
                    "lemma": conditioned.group(2).strip().lower(),
                    "nadi": conditioned.group(3).lower(),
                }
            )
            continue
        plain = _PAIR.search(line)
        if plain:
            pairs.append(
                {
                    "interview_id": interview_id,
                    "condition": "",
                    "lemma": plain.group(1).strip().lower(),
                    "nadi": plain.group(2).lower(),
                }
            )
    return pairs


def load_evidence(
    data_dir: Path,
    budget: Budget,
    audit: list[dict],
    transcription_tool: TranscriptionTool,
    tool_failures: list[str],
) -> EvidencePack:
    root = Path(data_dir)
    retriever = Retriever(budget, audit)
    manifest = retriever.read_json(root / "manifest.json")
    if not isinstance(manifest, dict):
        raise ToolFailure("manifest.json must be an object")

    examples_doc = retriever.read_json(root / "examples.json")
    grammar_text = retriever.read_text(root / "grammar_note.md")
    grammar_rules, code_switch, grammar_reliability = _grammar_sections(grammar_text)
    dictionary_a_doc = retriever.read_json(root / "dictionary_a.json")
    dictionary_b_doc = retriever.read_json(root / "dictionary_b.json")
    experts_doc = retriever.read_json(root / "experts.json")
    viewers_doc = retriever.read_json(root / "viewers.json")
    episode_doc = retriever.read_json(root / "episode.json")
    correction_doc = retriever.read_json(root / "correction.json")

    quarantined: list[str] = []

    def keep_entry(entry: dict) -> bool:
        blob = " ".join(
            str(entry.get(key, "")) for key in ("english", "nadi9", "note", "id")
        )
        screened = screen_text(blob)
        if screened.quarantined:
            quarantined.append(str(entry.get("id", "unknown-entry")))
            audit.append(
                {
                    "kind": "quarantine",
                    "id": entry.get("id"),
                    "matches": screened.matches,
                }
            )
            return False
        return True

    dictionary_a = [entry for entry in dictionary_a_doc["entries"] if keep_entry(entry)]
    dictionary_b = [entry for entry in dictionary_b_doc["entries"] if keep_entry(entry)]

    viewers: list[dict] = []
    for comment in viewers_doc["comments"]:
        screened = screen_text(comment.get("text", ""))
        if screened.quarantined:
            quarantined.append(str(comment.get("id")))
            audit.append(
                {
                    "kind": "quarantine",
                    "id": comment.get("id"),
                    "matches": screened.matches,
                }
            )
            continue
        viewers.append(comment)

    interview_pairs: list[dict] = []
    interviews: list[dict] = []
    for name in manifest["interviews"]:
        try:
            interview = retriever.read_json(root / "interviews" / name)
            if not isinstance(interview, dict):
                raise ToolFailure(f"{name} is not an object")
            budget.tool(f"transcribe:{interview.get('id', name)}")
            audit.append(
                {
                    "kind": "tool_call",
                    "tool": "transcribe",
                    "target": interview.get("id", name),
                }
            )
            transcript = transcription_tool.transcribe(interview)
        except ToolFailure as exc:
            tool_failures.append(str(exc))
            audit.append(
                {
                    "kind": "tool_failure",
                    "tool": "transcribe",
                    "target": name,
                    "message": str(exc),
                }
            )
            continue
        interviews.append(interview)
        interview_pairs.extend(
            _extract_pairs(str(interview.get("id", name)), transcript, quarantined)
        )

    examples = examples_doc["examples"] if isinstance(examples_doc, dict) else examples_doc
    episode = episode_doc["cues"] if isinstance(episode_doc, dict) else episode_doc
    experts = experts_doc["experts"] if isinstance(experts_doc, dict) else experts_doc

    return EvidencePack(
        data_dir=root,
        manifest=manifest,
        examples=examples,
        grammar_text=grammar_text,
        grammar_rules=grammar_rules,
        code_switch=code_switch,
        dictionary_a=dictionary_a,
        dictionary_b=dictionary_b,
        experts=experts,
        viewers=viewers,
        interviews=interviews,
        interview_pairs=interview_pairs,
        episode=episode,
        correction=correction_doc if isinstance(correction_doc, dict) else None,
        quarantined_ids=quarantined,
        example_reliability=float(examples_doc.get("reliability", 0.9)),
        dictionary_a_reliability=float(dictionary_a_doc.get("reliability", 0.25)),
        dictionary_b_reliability=float(dictionary_b_doc.get("reliability", 0.8)),
        interview_reliability=float(manifest.get("interview_reliability", 0.6)),
        viewer_reliability=float(viewers_doc.get("reliability", 0.35)),
        grammar_reliability=grammar_reliability,
    )
