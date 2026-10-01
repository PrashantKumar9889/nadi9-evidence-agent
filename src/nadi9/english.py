"""English helpers shared by the translator and the verifier.

Dialect checks do not live here. This file only handles English shape:
stopwords, a few irregular verbs, and multi-word phrases such as "thank you".
"""

import re

STOPWORDS = {"the", "a", "an"}
AUXILIARIES = {"did", "do", "will"}
IRREGULAR = {"came": "come"}
PHRASES = ("thank you", "elder brother")


def normalize_source(text: str) -> str:
    cleaned = text.casefold().strip()
    cleaned = re.sub(r"[.?!]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def protect_phrases(text: str) -> str:
    protected = text
    for phrase in PHRASES:
        protected = re.sub(re.escape(phrase), phrase.replace(" ", "_"), protected, flags=re.IGNORECASE)
    return protected


def source_tokens(text: str) -> list[str]:
    protected = protect_phrases(text)
    raw = re.findall(r"[A-Za-z_']+", protected)
    tokens: list[str] = []
    for word in raw:
        lowered = word.lower()
        lowered = IRREGULAR.get(lowered, lowered)
        lowered = lowered.replace("_", " ")
        tokens.append(lowered)
    return tokens


def has_question(text: str) -> bool:
    return text.strip().endswith("?")


def has_negation(text: str) -> bool:
    return bool(re.search(r"\b(not|n't)\b", text, flags=re.IGNORECASE))


def has_back(text: str) -> bool:
    return bool(re.search(r"\bback\b", text, flags=re.IGNORECASE))


def has_copula(text: str) -> bool:
    return bool(re.search(r"\bis\b", text, flags=re.IGNORECASE))


def has_you_pronoun(text: str) -> bool:
    protected = protect_phrases(text)
    return bool(re.search(r"\byou\b", protected, flags=re.IGNORECASE))


def detect_tense(text: str) -> str:
    if re.search(r"\bwill\b", text, flags=re.IGNORECASE):
        return "future"
    if re.search(r"\b(did|came)\b", text, flags=re.IGNORECASE):
        return "past"
    return "present"


def split_clauses(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def split_vocative(clause: str, kinship: set[str]) -> tuple[str, str | None]:
    if "," not in clause:
        return clause, None
    left, right = clause.split(",", 1)
    candidate = right.strip().strip(".?!").lower()
    if candidate in kinship:
        return left.strip(), candidate
    return clause, None


def is_imperative(text: str, verb_lemmas: set[str], speaker_status: str) -> bool:
    if speaker_status != "higher":
        return False
    if has_you_pronoun(text) or re.search(r"\b(i|we|he|she)\b", text, flags=re.IGNORECASE):
        return False
    if re.search(r"\b(will|did)\b", text, flags=re.IGNORECASE):
        return False
    words = [token for token in source_tokens(text) if token not in STOPWORDS]
    if not words:
        return False
    return words[0] in verb_lemmas
