"""A linguist correction reruns only the subtitles that use the changed rule."""

from nadi9.pipeline import run_episode


def test_correction_reprocesses_only_question_lines(data_dir, tmp_path):
    result = run_episode(data_dir, tmp_path / "out")

    question_ids = {"S001", "S003", "S010"}
    assert set(result.reprocessed_ids) == question_ids

    for subtitle_id in question_ids:
        decision = result.by_id(subtitle_id)
        assert decision["reprocessed"] is True
        assert decision["revision"] == 2
        assert decision["first_pass_decision"] == "HUMAN_REVIEW"
        assert decision["decision"] == "APPROVE"
        assert decision["nadi_9_text"].endswith("ke")
        assert "ki" not in decision["nadi_9_text"].split()

    untouched = result.by_id("S002")
    assert untouched["reprocessed"] is False
    assert untouched["revision"] == 1
    assert untouched["decision"] == "APPROVE"
    assert untouched["nadi_9_text"] == "hae mi dora solva"

    rule = result.learned.rule("question-particle")
    assert rule["status"] == "accepted"
    assert rule["value"] == "ke"
    assert rule["resolved_by"] == "correction:C01"
    assert result.model_calls <= 25
    assert result.tool_calls <= 50
