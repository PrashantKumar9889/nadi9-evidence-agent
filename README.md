# Nadi-9 subtitle agent

Evidence-grounded subtitles for **Nadi-9**, a fictional dialect. The agent learns only from the synthetic pack in `data/synthetic/`, translates a short scene, and sends uncertain lines to a person.

**SYNTHETIC DEMO DATA.** Nadi-9 is not a real language. Nothing in this repository is field evidence.

The default path is mock mode. It does not call a model API and does not need a key.

## Quick Start (Beginner-Friendly & Cross-Platform)

No API key or external network access is needed. Mock mode runs by default using the synthetic pack.

### Option 1: Easiest (Zero setup, runs anywhere)
```bash
# Run the pipeline and generate sample_run artifacts
python run.py run --data data/synthetic --out sample_run

# Inspect quarantined entries, outliers, and learned rules
python run.py inspect --data data/synthetic

# Live interview walkthrough of a single subtitle decision (e.g. S001, S008, S012)
python run.py explain --subtitle S001
```

### Option 2: Installed CLI
```bash
python -m pip install -e .
nadi9 run --data data/synthetic --out sample_run
nadi9 inspect --data data/synthetic
nadi9 explain --subtitle S001
```

### Option 3: Direct module invocation with PYTHONPATH
- **Linux / macOS**:
  ```bash
  PYTHONPATH=src python3 -m nadi9 run --data data/synthetic --out sample_run
  PYTHONPATH=src python3 -m nadi9 inspect --data data/synthetic
  PYTHONPATH=src python3 -m nadi9 explain --subtitle S001
  ```
- **Windows (PowerShell)**:
  ```powershell
  $env:PYTHONPATH="src"; python -m nadi9 run --data data/synthetic --out sample_run
  $env:PYTHONPATH="src"; python -m nadi9 inspect --data data/synthetic
  $env:PYTHONPATH="src"; python -m nadi9 explain --subtitle S001
  ```

Output files written to `sample_run/`:
- `sample_run/subtitles.srt` — standard timed subtitle file
- `sample_run/subtitle_decisions.jsonl` — machine-readable decisions with confidence & evidence
- `sample_run/learned_rules.json` — verified rules, lexicon, and quarantined items
- `sample_run/review_queue.json` — focused queue for human linguists
- `sample_run/final_report.md` — summary release recommendation
- `sample_run/audit_log.jsonl` — full chronological event trail

## Running the Automated Tests
```bash
pytest
```

The 10 automated tests cover:
- Reliable-source conflict resolution (kinship vs peer friend)
- Unsupported vocabulary handling (abstains without hallucinating)
- Mid-episode linguist correction & targeted replanning (reprocesses only affected lines)
- Audio transcription tool outage (fails closed, preserves remaining run)
- Prompt injection & poisoned dictionary entries (quarantined before voting)
- Independent verifier rejection (negation, unsupported words, reading speed)

## What the run will and will not do

Approved lines are built from forms the pack supports. If a word is missing, or two reliable sources disagree and the scene does not settle it, the Nadi-9 line is left empty and the decision is `HUMAN_REVIEW`.

A correction in the pack is applied after the first pass. Only subtitles that use the changed feature are translated and checked again.

Model calls stay within 25. Tool calls stay within 50. Both caps are flags: `--max-model-calls` and `--max-tool-calls`.

## Layout

- `src/nadi9/` — the agent
- `data/synthetic/` — the labeled demo pack
- `tests/` — the required behaviors
- `sample_run/` — output of the mock run
- `ARCHITECTURE.md` — planning, memory, verification, failures, trust
- `AI_COLLABORATION.md` — what the coding assistant did and what was rejected
- `KNOWN_LIMITATIONS.md` — what was left unfinished on purpose
