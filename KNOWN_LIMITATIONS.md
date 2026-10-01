# Known limitations

These are deliberate limits, not forgotten bugs. The goal was a reviewable decision path for one short scene.

- **The pack is synthetic.** The brief’s audio files, six-page grammar, and real episode were not in the workspace. `data/synthetic/` is labeled demo data. Nadi-9 is fictional.
- **Glosses are given.** Each approved example includes aligned tokens. The learner counts those alignments. It does not discover suffixes from raw audio or from an unsegmented paragraph.
- **English coverage is narrow.** The parser handles the sentence shapes in this episode (questions, negation, one irregular past verb, “thank you”, a comma address). It is not a general English analyzer.
- **Shared English helper.** `english.py` detects “not”, tense cues, and phrases for both the translator and the verifier. A bug in that helper could be repeated on both sides. Dialect checks and the “bad string” verifier tests are separate. A stricter version would duplicate the negation check inside the verifier.
- **Respect particle on verbs other than “come”.** The examples show `sha` on `come`. The grammar note says `sha` goes before the verb in general, and there is no counterexample, so lines such as “Did you eat food?” use `sha` before `eat`. That is a generalization a linguist might still want to confirm.
- **Negation plus respect is not composed.** No example shows `na` and `sha` in one clause, and both notes say “immediately before the verb.” Those lines would be `HUMAN_REVIEW`. This episode does not contain one.
- **Confidence is a heuristic.** Exact example reuse scores higher than a composed line. The number is never 1, and it is always paired with a sentence. It is not a calibrated probability.
- **One episode, one dialect, no user interface.** Scaling to many episodes would mean one learned store per dialect, the same per-episode budget, and a review queue. That runner is not built here.
- **Interviews are text files.** The transcription tool returns the synthetic transcript. It does not decode audio. A failure is simulated by raising `ToolFailure`.
- **The live model is not used.** `--mode live` does not send data to an API, even if a key is present. Mock mode is the supported run.
- **Viewer comments never settle a rule.** They are loaded so the injection comment can be quarantined. They do not outvote experts or examples.
- **Reading speed is a character count** at 17 characters per second. It does not know how Nadi-9 is pronounced.
