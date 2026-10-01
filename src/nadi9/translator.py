"""Compose a subtitle from supported pieces, or abstain."""

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
    normalize_source,
    source_tokens,
    split_clauses,
    split_vocative,
)
from nadi9.hypothesis_learner import LearnedState

_SKIP = STOPWORDS | AUXILIARIES | {"not", "back", "is"}


def translate_cue(cue: dict, learned: LearnedState) -> dict:
    features = _features(cue, learned)
    lemmas, unknown = _scan(cue, learned)
    assumptions = _base_assumptions(cue, features)
    non_blocking = _non_blocking(lemmas, learned)
    evidence: list[str] = []

    if unknown:
        return _decision(
            cue,
            nadi_9_text=None,
            status="HUMAN_REVIEW",
            confidence=0.22,
            reason=(
                "No attested Nadi-9 form for: "
                + ", ".join(unknown)
                + ". The line was left untranslated instead of inventing a word."
            ),
            evidence=evidence,
            assumptions=assumptions,
            conflicts=[],
            review_question=(
                "What is the attested Nadi-9 form, if any, for: " + ", ".join(unknown) + "?"
            ),
            features=features,
            non_blocking=non_blocking,
        )

    blocking: list[str] = []
    for lemma in lemmas:
        resolved = learned.resolve(lemma, cue)
        if resolved.status == "ok":
            evidence.extend(resolved.evidence)
            continue
        if resolved.status == "missing":
            unknown.append(lemma)
        else:
            blocking.append(resolved.detail or lemma)

    if unknown:
        return _decision(
            cue,
            nadi_9_text=None,
            status="HUMAN_REVIEW",
            confidence=0.22,
            reason="A word in this line has no supported form.",
            evidence=_unique(evidence),
            assumptions=assumptions,
            conflicts=[],
            review_question=(
                "What is the attested Nadi-9 form, if any, for: " + ", ".join(unknown) + "?"
            ),
            features=features,
            non_blocking=non_blocking,
        )

    if blocking:
        review = (
            "Is this friend kin (kari) or non-kin (luma)? "
            "The cue does not say which relationship applies."
            if any("friend" in item for item in blocking)
            else blocking[0]
        )
        return _decision(
            cue,
            nadi_9_text=None,
            status="HUMAN_REVIEW",
            confidence=0.36,
            reason=(
                "Reliable sources do not agree, or a required context field is missing. "
                "No Nadi-9 wording was chosen."
            ),
            evidence=_unique(evidence),
            assumptions=assumptions,
            conflicts=blocking,
            review_question=review,
            features=features,
            non_blocking=non_blocking,
        )

    if "question" in features and learned.question_particle is None:
        return _decision(
            cue,
            nadi_9_text=None,
            status="HUMAN_REVIEW",
            confidence=0.4,
            reason=(
                "Examples support the question particle ke, and a reliable expert supports ki. "
                "The line was not finished with a guess."
            ),
            evidence=_unique(evidence + ["example:questions", "expert:EX2"]),
            assumptions=assumptions,
            conflicts=["examples and expert EX1 support ke; expert EX2 supports ki"],
            review_question="Which question particle is accepted: ke or ki?",
            features=features,
            non_blocking=non_blocking,
        )

    if "respect" in features and "negation" in features:
        return _decision(
            cue,
            nadi_9_text=None,
            status="HUMAN_REVIEW",
            confidence=0.33,
            reason="No example shows the respect particle and the negation particle in the same clause.",
            evidence=_unique(evidence),
            assumptions=assumptions,
            conflicts=["grammar:respect vs grammar:negation order is unattested together"],
            review_question="When a line is both respectful and negative, which particle sits next to the verb?",
            features=features,
            non_blocking=non_blocking,
        )

    reused = _reuse_example(cue, learned)
    if reused is not None:
        example, text = reused
        assumptions.append(
            f"Reused surviving example {example['id']} because the source text and the status pattern match."
        )
        return _decision(
            cue,
            nadi_9_text=text,
            status="APPROVE",
            confidence=0.9,
            reason=(
                f"The source matches surviving example {example['id']}. "
                "That Nadi-9 line was reused and still has to pass the verifier."
            ),
            evidence=_unique(evidence + [f"example:{example['id']}"]),
            assumptions=assumptions,
            conflicts=[],
            review_question=None,
            features=features,
            non_blocking=non_blocking,
        )

    composed, compose_evidence, error = _compose(cue, learned)
    if composed is None:
        return _decision(
            cue,
            nadi_9_text=None,
            status="HUMAN_REVIEW",
            confidence=0.3,
            reason=error or "The line could not be composed from supported pieces.",
            evidence=_unique(evidence),
            assumptions=assumptions,
            conflicts=[],
            review_question=error or "Which attested pattern should this line follow?",
            features=features,
            non_blocking=non_blocking,
        )

    assumptions.append(
        "No single example has this whole sentence, so attested pieces were combined in the learned order."
    )
    return _decision(
        cue,
        nadi_9_text=composed,
        status="APPROVE",
        confidence=0.81,
        reason=(
            "Every content word is supported by surviving examples. "
            "The verifier still has to accept the line before it can ship."
        ),
        evidence=_unique(evidence + compose_evidence),
        assumptions=assumptions,
        conflicts=[],
        review_question=None,
        features=features,
        non_blocking=non_blocking,
    )


def _features(cue: dict, learned: LearnedState) -> list[str]:
    text = cue["source"]
    features: list[str] = []
    if has_question(text):
        features.append("question")
    if has_negation(text):
        features.append("negation")
    if has_back(text):
        features.append("back")
    if has_copula(text):
        features.append("copula")
    if cue.get("speaker_status") == "lower" and cue.get("addressee_status") == "higher":
        features.append("respect")
    if has_you_pronoun(text):
        features.append("you")
    if "friend" in source_tokens(text):
        features.append("friend")
    if is_imperative(text, learned.verb_lemmas, str(cue.get("speaker_status", ""))):
        features.append("imperative")
    elif any(token in learned.verb_lemmas for token in source_tokens(text)):
        features.append(detect_tense(text))
    return features


def _scan(cue: dict, learned: LearnedState) -> tuple[list[str], list[str]]:
    lemmas: list[str] = []
    unknown: list[str] = []
    for clause in split_clauses(cue["source"]):
        main, vocative = split_vocative(clause, learned.kinship_lemmas)
        parts = [main]
        if vocative:
            parts.append(vocative)
        for part in parts:
            for token in source_tokens(part):
                if token in _SKIP:
                    continue
                if token in learned.code_switch or any(key == token for key, _cond in learned.lexicon):
                    lemmas.append(token)
                else:
                    unknown.append(token)
    return _unique(lemmas), _unique(unknown)


def _reuse_example(cue: dict, learned: LearnedState) -> tuple[dict, str] | None:
    example = learned.examples_by_norm.get(normalize_source(cue["source"]))
    if example is None:
        return None
    if _respect(example) != _respect(cue):
        return None
    if has_you_pronoun(cue["source"]) or has_you_pronoun(example["source"]):
        if _you_bucket(example) != _you_bucket(cue):
            return None
    if is_imperative(
        example["source"], learned.verb_lemmas, str(example.get("speaker_status", ""))
    ) != is_imperative(cue["source"], learned.verb_lemmas, str(cue.get("speaker_status", ""))):
        return None
    return example, example["nadi9"]


def _compose(cue: dict, learned: LearnedState) -> tuple[str | None, list[str], str | None]:
    evidence: list[str] = []
    rendered: list[str] = []
    for clause in split_clauses(cue["source"]):
        text, clause_evidence, error = _compose_clause(clause, cue, learned)
        if text is None:
            return None, evidence, error
        evidence.extend(clause_evidence)
        rendered.append(text)
    if not rendered:
        return None, evidence, "The cue has no clauses."
    return " ".join(rendered), evidence, None


def _compose_clause(
    clause: str, cue: dict, learned: LearnedState
) -> tuple[str | None, list[str], str | None]:
    main, vocative = split_vocative(clause, learned.kinship_lemmas)
    subjects: list[str] = []
    objects: list[str] = []
    times: list[str] = []
    adjectives: list[str] = []
    interjections: list[str] = []
    evidence: list[str] = []
    verb_lemma: str | None = None
    saw_pronoun = False
    copula = False

    for token in source_tokens(main):
        if token in STOPWORDS or token in AUXILIARIES or token in {"not", "back"}:
            continue
        if token == "is":
            copula = True
            evidence.append("grammar:copula")
            continue
        if token in learned.code_switch and not any(key == token for key, _cond in learned.lexicon):
            subjects.append(token)
            evidence.append("grammar:code-switch")
            continue
        resolved = learned.resolve(token, cue)
        if resolved.status != "ok" or not resolved.nadi:
            return None, evidence, resolved.detail or f"Could not resolve {token}"
        evidence.extend(resolved.evidence)
        if resolved.pos == "interjection":
            interjections.append(resolved.nadi)
        elif resolved.pos == "pronoun":
            if saw_pronoun:
                objects.append(resolved.nadi)
            else:
                subjects.append(resolved.nadi)
                saw_pronoun = True
        elif resolved.pos == "time":
            times.append(resolved.nadi)
        elif resolved.pos == "adjective":
            adjectives.append(resolved.nadi)
        elif resolved.pos == "verb":
            verb_lemma = token
        elif not subjects and not saw_pronoun:
            subjects.append(resolved.nadi)
        else:
            objects.append(resolved.nadi)

    pieces = interjections + subjects + objects + times + adjectives
    if verb_lemma:
        if _respect(cue) and has_negation(clause):
            return None, evidence, "Respect and negation are not attested in the same clause."
        stem = learned.verb_stems.get(verb_lemma)
        if stem is None:
            return None, evidence, f"No stem for {verb_lemma}"
        if is_imperative(clause, learned.verb_lemmas, str(cue.get("speaker_status", ""))):
            surface = stem + learned.suffixes.get("imperative", "")
        else:
            tense = detect_tense(clause)
            if tense not in learned.suffixes:
                return None, evidence, f"No supported suffix for {tense}"
            surface = stem + learned.suffixes[tense]
        if _respect(cue):
            if learned.rules.get("respect", {}).get("status") != "accepted":
                return None, evidence, "Respect placement is not an accepted rule."
            pieces.append("sha")
            evidence.append("grammar:respect")
        if has_negation(clause):
            if learned.rules.get("negation", {}).get("status") != "accepted":
                return None, evidence, "Negation placement is not an accepted rule."
            pieces.append("na")
            evidence.append("grammar:negation")
        pieces.append(surface)
        if has_back(clause):
            if learned.rules.get("back", {}).get("status") != "accepted":
                return None, evidence, "The back particle is not an accepted rule."
            pieces.append("reth")
            evidence.append("grammar:back")
    elif copula:
        pieces.append("ri")

    if vocative:
        resolved = learned.resolve(vocative, cue)
        if resolved.status != "ok" or not resolved.nadi:
            return None, evidence, resolved.detail or f"Could not resolve {vocative}"
        pieces.append(resolved.nadi)
        evidence.extend(resolved.evidence)

    if has_question(clause):
        particle = learned.question_particle
        if not particle:
            return None, evidence, "Question particle is unresolved."
        pieces.append(particle)
        evidence.append("correction:C01" if learned.rules["question-particle"].get("resolved_by") else "example:questions")

    if not pieces:
        return None, evidence, "Nothing attested could be placed in this clause."
    return " ".join(pieces), evidence, None


def _respect(meta: dict) -> bool:
    return meta.get("speaker_status") == "lower" and meta.get("addressee_status") == "higher"


def _you_bucket(meta: dict) -> str:
    if meta.get("addressee_status") == "higher":
        return "addressee_higher"
    return "addressee_not_higher"


def _base_assumptions(cue: dict, features: list[str]) -> list[str]:
    assumptions = [
        f"Speaker {cue.get('speaker')} is {cue.get('speaker_status')} status and "
        f"addressee {cue.get('addressee')} is {cue.get('addressee_status')} status."
    ]
    if "respect" in features:
        assumptions.append("Lower speaker to higher addressee means sha is required before a verb.")
    if "you" in features:
        form = "shu" if cue.get("addressee_status") == "higher" else "tu"
        assumptions.append(f"Addressee status selects the you-form {form}.")
    if "copula" in features and "wifi" in cue["source"].lower():
        assumptions.append("wifi stays in English because the grammar note lists it as a tech noun.")
    return assumptions


def _non_blocking(lemmas: list[str], learned: LearnedState) -> list[str]:
    notes: list[str] = []
    for lemma in lemmas:
        notes.extend(learned.non_blocking.get(lemma, []))
    return _unique(notes)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _decision(
    cue: dict,
    *,
    nadi_9_text: str | None,
    status: str,
    confidence: float,
    reason: str,
    evidence: list[str],
    assumptions: list[str],
    conflicts: list[str],
    review_question: str | None,
    features: list[str],
    non_blocking: list[str],
) -> dict:
    return {
        "subtitle_id": cue["id"],
        "source_text": cue["source"],
        "nadi_9_text": nadi_9_text,
        "confidence": confidence,
        "confidence_reason": reason,
        "decision": status,
        "evidence": evidence,
        "assumptions": assumptions,
        "conflicts": conflicts,
        "review_question": review_question,
        "start": cue["start"],
        "end": cue["end"],
        "speaker": cue.get("speaker"),
        "addressee": cue.get("addressee"),
        "scene": cue.get("scene"),
        "features": features,
        "non_blocking_conflicts": non_blocking,
        "reprocessed": False,
        "revision": 1,
    }
