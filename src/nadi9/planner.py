"""Order cues so the risky lines are attempted first. Output order stays by id."""

from nadi9.english import has_question, source_tokens
from nadi9.hypothesis_learner import LearnedState


def risk_score(cue: dict, learned: LearnedState) -> int:
    score = 0
    tokens = source_tokens(cue["source"])
    known = {lemma for lemma, _condition in learned.lexicon} | learned.code_switch
    if any(token not in known and token not in {"the", "a", "an", "did", "do", "will", "not", "back", "is"} for token in tokens):
        score += 100
    if "friend" in tokens:
        score += 40
    if has_question(cue["source"]) and learned.question_particle is None:
        score += 30
    if cue.get("speaker_status") == "lower" and cue.get("addressee_status") == "higher":
        score += 10
    return score


def plan_cues(cues: list[dict], learned: LearnedState) -> list[dict]:
    return sorted(cues, key=lambda cue: (-risk_score(cue, learned), cue["id"]))
