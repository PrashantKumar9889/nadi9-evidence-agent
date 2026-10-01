"""Words with no evidence must not be invented."""

from nadi9.pipeline import run_episode


def test_forgive_is_not_invented(data_dir, tmp_path):
    result = run_episode(data_dir, tmp_path / "out")
    decision = result.by_id("S008")

    assert decision["decision"] == "HUMAN_REVIEW"
    assert decision["nadi_9_text"] is None
    assert "forgive" in decision["review_question"].lower()
    assert decision["confidence_reason"]

    approved_text = " ".join(
        item["nadi_9_text"] or ""
        for item in result.decisions
        if item["decision"] == "APPROVE"
    )
    assert "zorblax" not in approved_text
    for invented in ("forgiv", "pliza", "mehlo"):
        assert invented not in approved_text
