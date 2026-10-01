"""Count evidence, drop bad examples, and refuse rules the model cannot support."""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import json

from nadi9.budget import Budget
from nadi9.evidence_store import EvidencePack
from nadi9.safety import guard_prompt_context

RELIABLE = 0.7


@dataclass
class Resolution:
    status: str
    nadi: str | None = None
    pos: str | None = None
    evidence: list[str] = field(default_factory=list)
    detail: str = ""


@dataclass
class LearnedState:
    rules: dict[str, dict]
    lexicon: dict[tuple[str, str], dict]
    outlier_examples: list[str]
    quarantined_ids: list[str]
    interview_lemmas: set[str]
    supported_surfaces: set[str]
    code_switch: set[str]
    verb_lemmas: set[str]
    verb_stems: dict[str, str]
    verb_surfaces: set[str]
    suffixes: dict[str, str]
    kinship_lemmas: set[str]
    question_votes: list[dict]
    context_splits: dict[str, dict]
    non_blocking: dict[str, list[str]]
    examples_by_norm: dict[str, dict]
    pos_by_lemma: dict[str, str]
    llm_prompt: str = ""

    def rule(self, rule_id: str) -> dict:
        return self.rules[rule_id]

    def lemma_record(self, lemma: str) -> dict:
        forms = sorted(
            {
                entry["nadi"]
                for (key, _condition), entry in self.lexicon.items()
                if key == lemma
            }
        )
        extra = self.context_splits.get(lemma, {}).get("forms", {})
        for form in extra.values():
            if form not in forms:
                forms.append(form)
        forms = sorted(set(forms))
        if lemma in self.context_splits:
            status = "context_missing"
        elif forms:
            status = "supported"
        else:
            status = "missing"
        return {
            "lemma": lemma,
            "forms": forms,
            "status": status,
            "context": self.context_splits.get(lemma, {}).get("context"),
        }

    @property
    def question_particle(self) -> str | None:
        rule = self.rules.get("question-particle", {})
        if rule.get("status") == "accepted":
            return rule.get("value")
        return None

    def resolve(self, lemma: str, cue: dict) -> Resolution:
        if lemma in self.code_switch and (lemma, "") not in self.lexicon and (lemma, "kin") not in self.lexicon:
            if not any(key == lemma for key, _cond in self.lexicon):
                return Resolution("ok", nadi=lemma, pos="noun", evidence=["grammar:code-switch"])
        if lemma in self.context_splits and not cue.get("friend_relation"):
            split = self.context_splits[lemma]
            forms = ", ".join(f"{name}={form}" for name, form in sorted(split["forms"].items()))
            return Resolution(
                "context_missing",
                detail=f"{lemma} depends on {split['context']} ({forms})",
                evidence=split.get("evidence", []),
            )
        condition = ""
        if lemma == "you":
            condition = (
                "addressee_higher"
                if cue.get("addressee_status") == "higher"
                else "addressee_not_higher"
            )
        if cue.get("friend_relation") and lemma in self.context_splits:
            condition = str(cue["friend_relation"])
        entry = self.lexicon.get((lemma, condition))
        if entry is None and condition:
            entry = self.lexicon.get((lemma, ""))
        if entry is None:
            return Resolution("missing", detail=f"No supported form for {lemma}")
        return Resolution(
            "ok",
            nadi=entry["nadi"],
            pos=entry["pos"],
            evidence=list(entry["evidence"]),
        )


def _condition(token: dict, example: dict) -> str:
    if token.get("condition"):
        return str(token["condition"])
    if token.get("lemma") == "you":
        if example.get("addressee_status") == "higher":
            return "addressee_higher"
        return "addressee_not_higher"
    return ""


def _surface(token: dict) -> str:
    return str(token.get("surface") or token["nadi"])


def _outlier_ids(examples: list[dict]) -> list[str]:
    grouped: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for example in examples:
        for token in example.get("tokens", []):
            if token.get("pos") in {"particle", "copula", "postverb"}:
                continue
            key = (token["lemma"], _condition(token, example))
            grouped[key].append((token["nadi"], example["id"]))
    outliers: set[str] = set()
    for pairs in grouped.values():
        counts = Counter(nadi for nadi, _example_id in pairs)
        if len(counts) < 2:
            continue
        majority, majority_count = counts.most_common(1)[0]
        if majority_count < 2:
            continue
        for nadi, example_id in pairs:
            if nadi != majority:
                outliers.add(example_id)
    return sorted(outliers)


def _dict_agrees(entries: list[dict], lemma: str, nadi: str, condition: str) -> str | None:
    for entry in entries:
        if entry.get("english", "").lower() != lemma:
            continue
        if entry.get("nadi9", "").lower() != nadi:
            continue
        entry_condition = str(entry.get("condition") or "")
        if entry_condition == condition:
            return str(entry["id"])
    return None


def _placement_ok(tokens: list[dict], feature: str) -> bool:
    surfaces = [_surface(token) for token in tokens]
    verb_indexes = [index for index, token in enumerate(tokens) if token.get("pos") == "verb"]
    if feature == "negation":
        if not any(token.get("feature") == "negation" for token in tokens):
            return True
        for index, token in enumerate(tokens):
            if token.get("feature") == "negation":
                return index + 1 < len(tokens) and tokens[index + 1].get("pos") == "verb"
        return False
    if feature == "respect":
        if not any(token.get("feature") == "respect" for token in tokens):
            return True
        for index, token in enumerate(tokens):
            if token.get("feature") == "respect":
                return index + 1 < len(tokens) and tokens[index + 1].get("pos") == "verb"
        return False
    if feature == "back":
        if not any(token.get("pos") == "postverb" for token in tokens):
            return True
        for index, token in enumerate(tokens):
            if token.get("pos") == "postverb":
                return index > 0 and tokens[index - 1].get("pos") == "verb"
        return False
    if feature == "question":
        if not any(token.get("feature") == "question" for token in tokens):
            return True
        return bool(tokens) and tokens[-1].get("feature") == "question"
    if feature == "word-order":
        if not verb_indexes:
            return True
        verb_at = verb_indexes[0]
        for index, token in enumerate(tokens):
            if token.get("pos") in {"noun", "pronoun", "kinship", "adjective", "time"} and index > verb_at:
                return False
        return True
    if feature == "time":
        if not verb_indexes:
            return True
        for index, token in enumerate(tokens):
            if token.get("pos") == "time" and index > verb_indexes[0]:
                return False
        return True
    return True


def _rule(
    rule_id: str,
    statement: str,
    status: str,
    support: list[str],
    counterexamples: list[str] | None = None,
    value: str | None = None,
    reason: str = "",
) -> dict:
    return {
        "id": rule_id,
        "statement": statement,
        "status": status,
        "value": value,
        "support": support,
        "counterexamples": counterexamples or [],
        "confidence": 0.0 if status != "accepted" else 0.8,
        "reason": reason,
        "resolved_by": None,
        "prior_status": None,
    }


def learn(
    pack: EvidencePack,
    llm: object,
    budget: Budget,
    audit: list[dict],
    llm_failures: list[str],
) -> LearnedState:
    outliers = _outlier_ids(pack.examples)
    surviving = [example for example in pack.examples if example["id"] not in set(outliers)]
    audit.append({"kind": "outliers", "example_ids": outliers})

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for example in surviving:
        for token in example.get("tokens", []):
            if token.get("pos") in {"particle", "copula", "postverb"}:
                continue
            key = (token["lemma"], _condition(token, example))
            grouped[key].append({"example": example, "token": token})

    lexicon: dict[tuple[str, str], dict] = {}
    pos_by_lemma: dict[str, str] = {}
    for (lemma, condition), items in grouped.items():
        forms = Counter(item["token"]["nadi"] for item in items)
        nadi, count = forms.most_common(1)[0]
        if len(forms) > 1:
            continue
        evidence = [f"example:{item['example']['id']}" for item in items]
        dict_b_id = _dict_agrees(pack.dictionary_b, lemma, nadi, condition)
        if dict_b_id:
            evidence.append(f"dictionary:B:{dict_b_id}")
        supported = count >= 2 or (count >= 1 and dict_b_id is not None)
        if not supported:
            continue
        pos = items[0]["token"]["pos"]
        pos_by_lemma[lemma] = pos
        lexicon[(lemma, condition)] = {
            "lemma": lemma,
            "condition": condition,
            "nadi": nadi,
            "pos": pos,
            "evidence": evidence,
            "example_count": count,
        }

    non_blocking: dict[str, list[str]] = defaultdict(list)
    supported_by_lemma = {lemma: entry["nadi"] for (lemma, _cond), entry in lexicon.items()}
    for entry in pack.dictionary_a:
        lemma = entry.get("english", "").lower()
        nadi = entry.get("nadi9", "").lower()
        if lemma in supported_by_lemma and supported_by_lemma[lemma] != nadi and not entry.get("feature"):
            non_blocking[lemma].append(
                f"dictionary:A:{entry['id']} has {nadi}, examples support {supported_by_lemma[lemma]}"
            )

    suffixes: dict[str, set[str]] = defaultdict(set)
    verb_stems: dict[str, str] = {}
    verb_lemmas: set[str] = set()
    for example in surviving:
        for token in example.get("tokens", []):
            if token.get("pos") != "verb":
                continue
            verb_lemmas.add(token["lemma"])
            verb_stems[token["lemma"]] = token["nadi"]
            tense = token.get("tense")
            if not tense:
                continue
            surface = _surface(token)
            stem = token["nadi"]
            if tense == "imperative":
                suffixes["imperative"].add("" if surface == stem else surface)
            elif surface.startswith(stem):
                suffixes[tense].add(surface[len(stem) :])

    suffix_map: dict[str, str] = {}
    suffix_counters: list[str] = []
    for tense, found in suffixes.items():
        if len(found) == 1:
            suffix_map[tense] = next(iter(found))
        else:
            suffix_counters.append(tense)

    def support_if_consistent(feature: str, rule_id: str, statement: str, grammar_id: str) -> dict:
        bad = [
            example["id"]
            for example in surviving
            if not _placement_ok(example.get("tokens", []), feature)
        ]
        support = [f"example:{example['id']}" for example in surviving]
        if grammar_id in pack.grammar_rules:
            support.append(f"grammar:{grammar_id}")
        status = "accepted" if not bad else "unresolved"
        return _rule(rule_id, statement, status, support[:8], [f"example:{item}" for item in bad])

    rules: dict[str, dict] = {
        "word-order": support_if_consistent(
            "word-order",
            "word-order",
            "Content words stay before the verb.",
            "word-order",
        ),
        "negation": support_if_consistent(
            "negation",
            "negation",
            "na sits immediately before the verb.",
            "negation",
        ),
        "respect": support_if_consistent(
            "respect",
            "respect",
            "sha sits immediately before the verb when the speaker is lower status than the addressee.",
            "respect",
        ),
        "back": support_if_consistent(
            "back",
            "back",
            "reth sits immediately after the verb.",
            "back",
        ),
        "time-place": support_if_consistent(
            "time",
            "time-place",
            "Time words sit before the verb.",
            "place-time",
        ),
    }
    for tense, suffix in suffix_map.items():
        rules[f"tense-{tense}"] = _rule(
            f"tense-{tense}",
            f"{tense} uses suffix '{suffix}' on the verb stem.",
            "accepted",
            [f"grammar:tense-{tense}"] if f"tense-{tense}" in pack.grammar_rules else [],
            value=suffix,
        )

    question_votes = _question_votes(pack, surviving)
    rules["question-particle"] = _question_rule(question_votes)

    context_splits: dict[str, dict] = {}
    for expert in pack.experts:
        for claim in expert.get("claims", []):
            if claim.get("type") == "context_split":
                context_splits[claim["lemma"]] = {
                    "context": claim.get("context", "context"),
                    "forms": dict(claim.get("forms", {})),
                    "evidence": [f"expert:{expert['id']}"],
                }
    # Dictionary A friend form should remain visible even though it is not supported.
    for entry in pack.dictionary_a:
        if entry.get("english", "").lower() == "friend":
            split = context_splits.setdefault(
                "friend",
                {"context": "kin vs non-kin", "forms": {}, "evidence": []},
            )
            split["forms"].setdefault("non_kin", entry["nadi9"])
            split["evidence"].append(f"dictionary:A:{entry['id']}")

    interview_lemmas = {pair["nadi"] for pair in pack.interview_pairs}

    kinship = {lemma for lemma, pos in pos_by_lemma.items() if pos == "kinship"}
    verb_surfaces = _verb_surfaces(verb_stems, suffix_map)
    supported_surfaces = _surfaces(lexicon, suffix_map, verb_surfaces, rules, pack.code_switch)

    from nadi9.english import normalize_source

    examples_by_norm = {
        normalize_source(example["source"]): example
        for example in surviving
    }

    state = LearnedState(
        rules=rules,
        lexicon=lexicon,
        outlier_examples=outliers,
        quarantined_ids=list(pack.quarantined_ids),
        interview_lemmas=interview_lemmas,
        supported_surfaces=supported_surfaces,
        code_switch=set(pack.code_switch),
        verb_lemmas=verb_lemmas,
        verb_stems=verb_stems,
        verb_surfaces=verb_surfaces,
        suffixes=suffix_map,
        kinship_lemmas=kinship,
        question_votes=question_votes,
        context_splits=context_splits,
        non_blocking=dict(non_blocking),
        examples_by_norm=examples_by_norm,
        pos_by_lemma=pos_by_lemma,
    )
    state.supported_surfaces = _surfaces(
        lexicon, suffix_map, verb_surfaces, rules, pack.code_switch
    )
    _ask_model(state, llm, budget, audit, llm_failures)
    return state


def _question_votes(pack: EvidencePack, surviving: list[dict]) -> list[dict]:
    values = {
        token["nadi"]
        for example in surviving
        for token in example.get("tokens", [])
        if token.get("feature") == "question"
    }
    votes: list[dict] = []
    if len(values) == 1:
        votes.append(
            {
                "claim_id": "example:questions",
                "value": next(iter(values)),
                "reliability": pack.example_reliability,
                "source": "examples",
            }
        )
    for expert in pack.experts:
        for claim in expert.get("claims", []):
            if claim.get("type") == "particle" and claim.get("feature") == "question-particle":
                votes.append(
                    {
                        "claim_id": f"expert:{expert['id']}:question-particle",
                        "value": claim["value"],
                        "reliability": float(expert.get("reliability", 0.7)),
                        "source": f"expert:{expert['id']}",
                    }
                )
    for entry in pack.dictionary_a:
        if entry.get("feature") == "question-particle":
            votes.append(
                {
                    "claim_id": "dictionary:A:question",
                    "value": entry["nadi9"],
                    "reliability": pack.dictionary_a_reliability,
                    "source": f"dictionary:A:{entry['id']}",
                }
            )
    return votes


def _question_rule(votes: list[dict]) -> dict:
    reliable = [vote for vote in votes if vote["reliability"] >= RELIABLE]
    values = sorted({vote["value"] for vote in reliable})
    support = [vote["claim_id"] for vote in reliable]
    if len(values) == 1:
        return _rule(
            "question-particle",
            "The question particle is the last token.",
            "accepted",
            support,
            value=values[0],
            reason="Reliable sources agree.",
        )
    conflicts = []
    if len(values) > 1:
        conflicts.append(
            " vs ".join(
                f"{vote['source']}={vote['value']}" for vote in reliable if vote["value"] in values
            )
        )
    return _rule(
        "question-particle",
        "The question particle is disputed, so questions cannot be finished.",
        "unresolved",
        support,
        value=None,
        reason="Reliable sources disagree." if conflicts else "Not enough reliable evidence.",
    )


def _verb_surfaces(verb_stems: dict[str, str], suffixes: dict[str, str]) -> set[str]:
    surfaces: set[str] = set()
    for stem in verb_stems.values():
        surfaces.add(stem)
        for suffix in suffixes.values():
            surfaces.add(f"{stem}{suffix}")
    return surfaces


def _surfaces(
    lexicon: dict[tuple[str, str], dict],
    suffixes: dict[str, str],
    verb_surfaces: set[str],
    rules: dict[str, dict],
    code_switch: set[str],
) -> set[str]:
    surfaces = {entry["nadi"] for entry in lexicon.values()}
    surfaces.update(verb_surfaces)
    surfaces.update(code_switch)
    for particle in ("na", "sha", "reth", "ri"):
        surfaces.add(particle)
    question = rules.get("question-particle", {})
    if question.get("status") == "accepted" and question.get("value"):
        surfaces.add(question["value"])
    return surfaces


def refresh_surfaces(state: LearnedState) -> None:
    state.supported_surfaces = _surfaces(
        state.lexicon,
        state.suffixes,
        state.verb_surfaces,
        state.rules,
        state.code_switch,
    )


def _ask_model(
    state: LearnedState,
    llm: object,
    budget: Budget,
    audit: list[dict],
    llm_failures: list[str],
) -> None:
    summary = (
        f"supported_lemmas={sorted({lemma for lemma, _cond in state.lexicon})}; "
        f"accepted_suffixes={state.suffixes}; "
        f"code_switch={sorted(state.code_switch)}"
    )
    prompt = guard_prompt_context(summary)
    state.llm_prompt = prompt
    try:
        budget.model("hypothesis-proposal")
        audit.append({"kind": "model_call", "name": "hypothesis-proposal"})
        raw = llm.complete(prompt)  # type: ignore[attr-defined]
    except Exception as exc:  # provider failures stay inside the run
        from nadi9.errors import BudgetExceeded, LLMFailure

        if isinstance(exc, BudgetExceeded):
            raise
        message = str(exc)
        llm_failures.append(message)
        audit.append({"kind": "llm_failure", "message": message})
        state.rules["mock-plural-zo"] = _rule(
            "mock-plural-zo",
            "Model call failed before a proposal arrived.",
            "rejected",
            [],
            reason="The model was unavailable. No model-proposed rule was accepted.",
        )
        return

    try:
        payload = json.loads(raw)
        proposals = payload.get("proposals", [])
    except json.JSONDecodeError:
        proposals = []
        audit.append({"kind": "llm_failure", "message": "Model returned non-JSON"})

    for proposal in proposals:
        proposal_id = str(proposal.get("id", "model-proposal"))
        statement = str(proposal.get("statement", ""))
        if proposal_id == "mock-plural-zo" or "-zo" in statement:
            supported = any(surface.endswith("zo") for surface in state.supported_surfaces)
            state.rules[proposal_id] = _rule(
                proposal_id,
                statement,
                "rejected" if not supported else "accepted",
                [],
                reason=(
                    "The model proposed this rule, but no example, dictionary, or grammar note supports -zo."
                    if not supported
                    else "Evidence contains -zo."
                ),
            )
            audit.append({"kind": "hypothesis_rejected", "id": proposal_id})
            continue
        state.rules[proposal_id] = _rule(
            proposal_id,
            statement,
            "not_adopted",
            [],
            reason="Examples already decide word order. A model vote is not a source.",
        )
        audit.append({"kind": "hypothesis_not_adopted", "id": proposal_id})
