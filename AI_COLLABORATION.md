# AI collaboration log

This project was written with a Cursor coding agent (Grok). The agent was asked to follow the assignment PDF and to keep the design explainable by someone with no years of industry experience.

## What the assistant did

- Read the assignment and turned it into a pipeline, a synthetic pack, tests, and docs.
- Wrote the tests before the implementation. The first run failed because the package did not exist yet.
- Implemented the modules, then the tests and the sample command were run and fixed until they passed.
- Drafted the fresher explanation from the code that actually ran, not from a plan that was never executed.

## What was checked

- `python3 -m pytest` — conflict, unsupported word, correction, tool failure, prompt injection, verifier rejection.
- `PYTHONPATH=src python3 -m nadi9 run --data data/synthetic --out sample_run` — the five sample artifacts were written by that command.
- A printed decision list was checked by hand: question lines change from review to approve after the correction; `forgive` and `friend` stay in review; water is `nira`, not `zorblax`; non-question lines stay on revision 1.

## What was rejected

- **LangChain or LangGraph.** The assignment is a short pipeline. A framework would hide the steps a reviewer needs to see.
- **One prompt that translates the episode.** That is the failure mode the brief scores poorly. The mock model is asked only for hypotheses, and one of those hypotheses is thrown out.
- **Letting the model mint Nadi-9 words** when the pack has a gap. The empty subtitle is the product.
- **Trusting Dictionary A because it is the biggest list,** or trusting a retrieved paragraph because it says to ignore the rules.
- **Re-running every subtitle after the correction.** The correction names a feature. Only lines tagged with that feature are redone.
- **A live API call in the default path.** Evaluators should not need a personal key. Live mode refuses to send the pack to a network model.

## What the assistant got wrong at first

The interview-only word test expected the Nadi-9 form `pelu`, while the first loader stored the English lemma `work`. The grammar-note parser also kept a trailing period on `phone`. Both were caught by running the tests and reading the decision dump, then fixed in the loader. That is the check that matters: the assistant’s draft was not accepted until the tests and the sample run agreed with it.
