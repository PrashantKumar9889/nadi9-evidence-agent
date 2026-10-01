"""Reliable sources disagree on 'friend'. The agent must not pick a side."""

from nadi9.pipeline import run_episode


def test_friend_conflict_stays_visible_and_blocks_approval(data_dir, tmp_path):
    result = run_episode(data_dir, tmp_path / "out")

    friend = result.learned.lemma_record("friend")
    forms = set(friend["forms"])
    assert "kari" in forms
    assert "luma" in forms
    assert friend["status"] == "context_missing"

    decision = result.by_id("S012")
    assert decision["decision"] == "HUMAN_REVIEW"
    assert decision["nadi_9_text"] is None
    assert decision["conflicts"]
    assert any("friend" in item for item in decision["conflicts"])
    assert "kin" in decision["review_question"].lower()
    assert decision["confidence_reason"]
