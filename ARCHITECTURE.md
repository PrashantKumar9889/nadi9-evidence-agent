# Architecture

The agent is a straight pipeline. A later step may reject an earlier step. No step is allowed to invent a Nadi-9 word to keep a line fluent.

```text
Evidence → Evidence Store → Hypothesis Learner → Planner
        → Translator → Independent Verifier → Human Review → Final Decision
```

A linguist correction sits between the first decision and the final decision. It marks only the affected subtitles and those lines go through translate and verify again.

## Modules

| Module | Job |
| --- | --- |
| `evidence_store.py` | Read the pack through tools. Screen every document before it can vote. |
| `hypothesis_learner.py` | Count glosses, drop outlier examples, accept or reject rules. |
| `planner.py` | Order cues so missing words and open conflicts go first. |
| `translator.py` | Reuse a matching example or compose supported pieces. Otherwise abstain. |
| `verifier.py` | Check the proposed string against the learned tables. It does not call the translator. |
| `correction.py` | Apply one linguist correction and list the subtitle ids that use that feature. |
| `pipeline.py` | Run the steps, catch tool and model failures, write the artifacts. |
| `safety.py` | Detect instruction-like text inside evidence. |
| `llm.py` | Mock provider by default. It proposes rules. It does not write subtitles. |
| `budget.py` | Stop at 25 model calls or 50 tool calls. |

## Planning

Each cue gets a risk score from the source text and the learned tables:

1. Unknown English words (highest).
2. A word whose form depends on missing context, such as `friend`.
3. A question while the question particle is still unresolved.
4. A lower-status speaker talking to a higher-status addressee.

The planner runs risky cues first so a budget stop, if it happened, would leave the safer lines for later. The files are still written in subtitle id order. After a correction, the plan shrinks to the ids whose stored features include the corrected feature. Other decisions are copied forward unchanged.

## Memory

Learned state is plain data: lexicon entries, rule records, outlier example ids, quarantined ids, and the question votes that are still allowed to count. Each subtitle decision stores the features it used (`question`, `past`, `respect`, and so on), the evidence ids, the assumptions, and the conflicts. That record is what the correction step reads. The audit log stores tool calls, quarantines, the model proposal, and which lines were redone.

## Source precedence

A source does not win because it is long or new.

1. Text that matches an instruction pattern is quarantined and cannot vote.
2. An approved example that disagrees with two or more other approved examples is treated as an outlier and dropped.
3. A content word is usable when at least two surviving examples agree, or one surviving example agrees with Dictionary B.
4. Dictionary A is broad and low reliability (0.25). It cannot create a word and it cannot veto a form that examples and Dictionary B already support. The disagreement is still stored.
5. If two sources at reliability 0.7 or higher disagree on the question particle, the particle stays unresolved.
6. Viewer comments are kept as audience noise. They are too weak to settle a rule.
7. Interview pairs are recorded, but a word that appears only in an interview is not usable in a subtitle.

## Translation

The translator does not ask a model for a sentence.

- If the whole source matches a surviving example, and the status pattern matches, that Nadi-9 line is reused.
- Otherwise the line is built in a fixed order that the examples support: subject, object, time, adjective, respect particle, negation particle, verb, back particle, vocative, question particle.
- Suffixes come from the learned table (`ra`, `va`, `mi`, or a bare stem for a higher-status command).
- `you` is `shu` for a higher addressee and `tu` otherwise, because the examples split that way.
- If any content word has no supported form, the Nadi-9 field stays empty.
- If `friend` is needed and the cue does not say kin or non-kin, the line stays empty. Both forms remain visible in the conflict.

## Verification

`verifier.py` never imports the translator. It receives the English source, the cue (speaker and status), the learned tables, and the candidate string.

It checks unsupported tokens, missing negation, question-particle placement, respect placement, the back particle, the you-form, tense or imperative shape, the copula, omitted supported words, a friend form used without context, subtitle timing, and reading speed (17 characters per second).

If the verifier fails, the decision becomes `HUMAN_REVIEW` even when the translator had proposed `APPROVE`. A token that is not in the learned surfaces is removed from the subtitle so a bad string is not what a viewer would read.

English helpers such as “does this sentence contain not?” live in `english.py` and are shared. The dialect checks are not shared. See `KNOWN_LIMITATIONS.md`.

## Human review and the final decision

`APPROVE` requires a Nadi-9 string, no blocking conflict, confidence at or above 0.7, and a passing verifier. Confidence is a short written reason plus a number. It is capped below 1.

`HUMAN_REVIEW` is used when evidence is missing, sources at or above 0.7 disagree, required context is absent, the verifier disagrees, a tool fails closed on that line, or the call budget is exhausted. The review question names the missing fact. It does not say “please check this.”

The release recommendation is `DO_NOT_RELEASE` while any line is in review.

## Failure recovery

- A transcription outage is caught per interview. The run continues on the remaining files. Words that existed only in those interviews are absent.
- A model failure is caught around the single hypothesis call. No model-proposed rule is accepted. Example counting still runs.
- An unexpected error on one cue becomes `HUMAN_REVIEW` for that cue.
- Hitting either call cap stops further model or tool use. Unchecked cues are marked for review instead of being guessed.

## Trust boundaries

- Evidence text is data. `safety.py` drops lines that tell the agent to ignore instructions, change role, skip review, invent words, or approve every subtitle.
- The model prompt is a short summary of counts and suffixes. Raw dictionary notes are not pasted into it.
- A model proposal is rejected unless the pack already contains the pattern. The mock model’s “plural -zo” rule is rejected on every normal run.
- Dictionary A’s poisoned water entry is dropped before voting, so `zorblax` never becomes a supported form.
- The verifier is a separate gate from the translator.

## Call budgets

Defaults are 25 model calls and 50 tool calls per episode. The mock episode uses one model call (the hypothesis proposal) and well under 50 tool calls (file reads, interview transcription, and validation of lines that actually have Nadi-9 text). Abstentions are not sent to the validator. After the correction, only the three question lines are validated again.
