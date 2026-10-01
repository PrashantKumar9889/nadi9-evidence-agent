"""Apply one linguist correction and name the subtitles that must be redone."""

from nadi9.hypothesis_learner import LearnedState, _question_rule, refresh_surfaces


def apply_correction(state: LearnedState, correction: dict | None, decisions: dict[str, dict]) -> list[str]:
    if not correction:
        return []
    features = list(correction.get("affects_features") or [])
    drop = set(correction.get("drop_claims") or [])
    if correction.get("set_rule", {}).get("id") == "question-particle":
        state.question_votes = [
            vote for vote in state.question_votes if vote["claim_id"] not in drop
        ]
        state.question_votes.append(
            {
                "claim_id": f"correction:{correction['id']}",
                "value": correction["set_rule"]["value"],
                "reliability": 0.95,
                "source": f"correction:{correction['id']}",
            }
        )
        previous = state.rules.get("question-particle", {}).get("status")
        updated = _question_rule(state.question_votes)
        updated["prior_status"] = previous
        updated["resolved_by"] = f"correction:{correction['id']}"
        updated["statement"] = correction.get(
            "message",
            "Question particle updated from a linguist correction.",
        )
        state.rules["question-particle"] = updated
        refresh_surfaces(state)

    affected = [
        subtitle_id
        for subtitle_id, decision in decisions.items()
        if any(feature in decision.get("features", []) for feature in features)
    ]
    return affected
