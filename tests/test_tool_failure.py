"""A dead transcription tool must not crash the run or invent interview words."""

from nadi9.errors import ToolFailure
from nadi9.pipeline import run_episode


class DownTranscription:
    def transcribe(self, interview: dict) -> str:
        raise ToolFailure(f"temporary outage for {interview.get('id')}")


def test_transcription_failure_is_contained(data_dir, tmp_path):
    result = run_episode(
        data_dir,
        tmp_path / "out",
        transcription_tool=DownTranscription(),
    )

    assert result.finished_safely is True
    assert result.tool_failures
    assert any(event["kind"] == "tool_failure" for event in result.audit)
    assert "pelu" not in result.interview_lemmas

    water = result.by_id("S011")
    assert water["decision"] == "APPROVE"
    assert "nira" in water["nadi_9_text"].split()
    assert "zorblax" not in water["nadi_9_text"].split()


def test_successful_transcription_records_interview_only_word(data_dir, tmp_path):
    result = run_episode(data_dir, tmp_path / "out")
    assert "pelu" in result.interview_lemmas
    assert "pelu" not in result.supported_surfaces
