"""Small tools: read a file, transcribe a synthetic interview, validate later."""

import json
from pathlib import Path

from nadi9.budget import Budget
from nadi9.errors import DataError, ToolFailure


class Retriever:
    def __init__(self, budget: Budget, audit: list[dict]) -> None:
        self.budget = budget
        self.audit = audit

    def read_text(self, path: Path) -> str:
        self.budget.tool(f"retrieve:{path.name}")
        self.audit.append({"kind": "tool_call", "tool": "retrieve", "target": path.name})
        if not path.is_file():
            raise DataError(f"Missing evidence file: {path}")
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ToolFailure(f"Could not read {path.name}") from exc

    def read_json(self, path: Path) -> dict | list:
        raw = self.read_text(path)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DataError(f"{path.name} is not valid JSON") from exc


class TranscriptionTool:
    """Synthetic interviews are already text. The tool can still fail closed."""

    def transcribe(self, interview: dict) -> str:
        text = interview.get("transcript")
        if not isinstance(text, str) or not text.strip():
            raise ToolFailure(f"No transcript for {interview.get('id', 'unknown')}")
        return text


class FailingTranscriptionTool(TranscriptionTool):
    """Used by tests and by anyone simulating an outage."""

    def transcribe(self, interview: dict) -> str:
        raise ToolFailure(f"temporary outage for {interview.get('id', 'unknown')}")
