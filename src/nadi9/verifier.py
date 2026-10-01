"""Independent checks. This module does not call the translator."""

from dataclasses import dataclass

from nadi9.english import (
    AUXILIARIES,
    STOPWORDS,
    detect_tense,
    has_back,
    has_copula,
    has_negation,
    has_question,
    has_you_pronoun,
    is_imperative,
    source_tokens,
)
from nadi9.hypothesis_learner import LearnedState

_SKIP = STOPWORDS | AUXILIARIES | {"not", "back", "is"}
_MAX_CHARS_PER_SECOND = 17


@dataclass
class VerifyResult:
    passed: bool
    issues: list[str]


def verify_subtitle(
    *,
    source_text: str,
    nadi_9_text: str | None,
    cue: dict,
    learned: LearnedState,
    start: str,
    end: str,
) -> VerifyResult:
    issues: list[str] = []
    if not nadi_9_text:
        return VerifyResult(False, ["no nadi-9 text submitted"])

    tokens = nadi_9_text.split()
    for token in tokens:
        if token not in learned.supported_surfaces:
            issues.append(f"unsupported token: {token}")

    if has_negation(source_text):
        if "na" not in tokens:
            issues.append("missing negation particle")
        else:
            index = tokens.index("na")
            if index + 1 >= len(tokens) or tokens[index + 1] not in learned.verb_surfaces:
                issues.append("negation is not immediately before the verb")

    if has_question(source_text):
        particle = learned.question_particle
        if not particle:
            issues.append("question particle is unresolved")
        elif tokens[-1] != particle:
            issues.append("question particle missing or not final")

    _check_respect(cue, tokens, learned, issues)
    _check_back(source_text, tokens, learned, issues)
    _check_you(source_text, cue, tokens, learned, issues)
    _check_tense(source_text, cue, tokens, learned, issues)
    if has_copula(source_text) and "ri" not in tokens:
        issues.append("missing copula")
    _check_omissions(source_text, tokens, cue, learned, issues)
    _check_friend_context(source_text, tokens, learned, issues)
    _check_timing(nadi_9_text, start, end, issues)
    return VerifyResult(passed=not issues, issues=issues)


def _check_respect(cue: dict, tokens: list[str], learned: LearnedState, issues: list[str]) -> None:
    required = cue.get("speaker_status") == "lower" and cue.get("addressee_status") == "higher"
    verb_indexes = [index for index, token in enumerate(tokens) if token in learned.verb_surfaces]
    if required and verb_indexes:
        verb_at = verb_indexes[0]
        if verb_at == 0 or tokens[verb_at - 1] != "sha":
            issues.append("missing respect particle before the verb")
    if not required and "sha" in tokens:
        issues.append("unexpected respect particle")


def _check_back(source_text: str, tokens: list[str], learned: LearnedState, issues: list[str]) -> None:
    if has_back(source_text):
        if "reth" not in tokens:
            issues.append("missing back particle")
            return
        index = tokens.index("reth")
        if index == 0 or tokens[index - 1] not in learned.verb_surfaces:
            issues.append("back particle is not immediately after the verb")
    elif "reth" in tokens:
        issues.append("unexpected back particle")


def _check_you(
    source_text: str,
    cue: dict,
    tokens: list[str],
    learned: LearnedState,
    issues: list[str],
) -> None:
    if not has_you_pronoun(source_text):
        return
    resolved = learned.resolve("you", cue)
    if resolved.status != "ok" or not resolved.nadi:
        issues.append("you-form is not resolved")
        return
    if resolved.nadi not in tokens:
        issues.append(f"you-form mismatch: expected {resolved.nadi}")


def _check_tense(
    source_text: str,
    cue: dict,
    tokens: list[str],
    learned: LearnedState,
    issues: list[str],
) -> None:
    if is_imperative(source_text, learned.verb_lemmas, str(cue.get("speaker_status", ""))):
        for token in source_tokens(source_text):
            stem = learned.verb_stems.get(token)
            if stem and stem not in tokens:
                issues.append("imperative should use the bare verb stem")
        return
    if not any(token in learned.verb_lemmas for token in source_tokens(source_text)):
        return
    tense = detect_tense(source_text)
    suffix = learned.suffixes.get(tense)
    if suffix is None:
        issues.append(f"missing {tense} tense suffix")
        return
    matched = any(token in learned.verb_surfaces and token.endswith(suffix) for token in tokens)
    if not matched:
        issues.append(f"missing {tense} tense suffix")


def _check_omissions(
    source_text: str,
    tokens: list[str],
    cue: dict,
    learned: LearnedState,
    issues: list[str],
) -> None:
    for token in source_tokens(source_text):
        if token in _SKIP:
            continue
        known = token in learned.code_switch or any(key == token for key, _cond in learned.lexicon)
        if not known:
            continue
        if token in learned.code_switch and not any(key == token for key, _cond in learned.lexicon):
            if token not in tokens:
                issues.append(f"omission: {token}")
            continue
        resolved = learned.resolve(token, cue)
        if resolved.status != "ok" or not resolved.nadi:
            issues.append(f"translated without support for {token}")
            continue
        if resolved.pos == "verb":
            if not any(
                item in learned.verb_surfaces and item.startswith(resolved.nadi) for item in tokens
            ):
                issues.append(f"omission: {token}")
        elif resolved.nadi not in tokens:
            issues.append(f"omission: {token}")


def _check_friend_context(
    source_text: str,
    tokens: list[str],
    learned: LearnedState,
    issues: list[str],
) -> None:
    if "friend" not in source_tokens(source_text):
        return
    record = learned.lemma_record("friend")
    if record["status"] == "context_missing" and any(form in tokens for form in record["forms"]):
        issues.append("friend form used without relationship context")


def _check_timing(nadi_9_text: str, start: str, end: str, issues: list[str]) -> None:
    try:
        duration = _seconds(end) - _seconds(start)
    except ValueError:
        issues.append("timing could not be read")
        return
    if duration <= 0:
        issues.append("timing is not positive")
        return
    speed = len(nadi_9_text) / duration
    if speed > _MAX_CHARS_PER_SECOND:
        issues.append(f"reading speed is too fast ({speed:.1f} characters per second)")


def _seconds(stamp: str) -> float:
    hours, minutes, rest = stamp.split(":")
    seconds, millis = rest.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000
