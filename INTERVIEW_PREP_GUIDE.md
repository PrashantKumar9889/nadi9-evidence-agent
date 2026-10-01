# Nadi-9 Dialect Agent: Complete Interview Preparation Guide
*Tailored for Junior / Intern Candidates with 0 Years Experience to Ace the Senior-Level Technical Discussion*

---

## 1. The 60-Second "Elevator Pitch" (Memorize & Internalize This)

> **Interviewer:** *"Tell me about this project and what problem it solves."*

**Your Answer:**
> "The core challenge of this project is **reasoning under extreme uncertainty without hallucinating**. 
> 
> Most LLM applications fail because when an AI model doesn't know a word, it simply makes up a plausible-sounding answer. For an OTT entertainment platform releasing content in a new or low-resource dialect (here called **Nadi-9**), inventing fake words or guessing grammar ruins the viewer experience and misleads linguists.
> 
> Instead of a monolithic prompt that pretends to know everything, I designed an **evidence-grounded, modular pipeline**. It extracts grammar rules and vocabulary from noisy, contradictory sources, screens out prompt injections and poisoned entries, plans translation order based on linguistic risk, and verifies every single subtitle with an **independent verifier**. 
> 
> Crucially, when evidence is missing or conflicting, the system exhibits **epistemic humility**—it intentionally leaves the translation blank, assigns low confidence, and escalates a precise, actionable question to a human linguist. Out of 12 subtitle lines, 10 are approved with verified evidence citations, and 2 are safely escalated for review, with a final recommendation of `DO_NOT_RELEASE` until a linguist confirms the ambiguous terms."

---

## 2. Core Architectural Philosophy: Why This Wins Over Naive LLM Apps

| Feature | Naive LLM Prompt Approach (Scores 0%) | Our Evidence-Grounded Agent (Scores 100%) |
| :--- | :--- | :--- |
| **Translation Logic** | Asks GPT-4/Claude to "translate to Nadi-9". | Composes only attested lemmas and suffixes using verified SOV syntax rules. |
| **Missing Words** | Invents plausible-sounding gibberish (`forgiv`, `pliza`). | Leaves text empty, sets status to `HUMAN_REVIEW`, flags specific missing words. |
| **Conflicting Data** | Arbitrarily picks one dictionary or hallucinates a blend. | Compares source reliability scores; marks lines unresolved if reliable sources conflict. |
| **Verification** | Self-verification (asking the same LLM "is this correct?"). | Separate, deterministic validator module with zero translator imports. |
| **Correction Event** | Re-runs the entire episode (wasting tokens and budget). | Dependency-aware replanning: re-runs *only* the 3 cues tagged with the `question` feature. |
| **Security** | Susceptible to indirect prompt injection in user comments. | Quarantines instruction-like text before it can vote or enter model context. |
| **Cost & Budget** | Unbounded recursive agent loops. | Strict budget ceiling: max 25 model calls, max 50 tool calls per episode. |

---

## 3. High-Level System Architecture

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 EVIDENCE SOURCES                       │
                  │  (Examples, Dict A, Dict B, Grammar, Experts, Audio)   │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │             1. SAFETY & INGESTION FILTER               │
                  │  • Screens prompt injections (quarantines A-044, V2)   │
                  │  • Detects statistical outliers (drops E19, E20)       │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │            2. HYPOTHESIS & LEXICON LEARNER             │
                  │  • Establishes source precedence (Examples > Dict B)   │
                  │  • Validates SOV word order, tense affixes (-ra, -va)  │
                  │  • Identifies conflicts (friend: kin vs non-kin)       │
                  │  • Rejects unsupported LLM proposal (mock-plural-zo)   │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │              3. RISK-BASED CUE PLANNER                 │
                  │  • Prioritizes high-risk cues first (missing words,    │
                  │    unresolved questions, status differentials)         │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │             4. ATTESTED TRANSLATION ENGINE             │
                  │  • Matches surviving examples or composes SOV blocks   │
                  │  • Explicitly abstains if words or context are missing │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │             5. INDEPENDENT VERIFICATION GATE           │
                  │  • Token whitelist check (no unverified words)         │
                  │  • Particle placement (na, sha, reth, ke)              │
                  │  • Reading speed check (<= 17 chars/sec)               │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                        ┌────────────────────┴───────────────────┐
                        │                                        │
           Pass 1 Decisions                               Mid-Run Linguist
                  │                                     Correction (C01)
                  ▼                                              │
      ┌───────────────────────┐                                  ▼
      │ S001, S003, S010:     │                        ┌───────────────────┐
      │ Flagged HUMAN_REVIEW  │                        │ Updates ke rule,  │
      │ (Question unresolved) │                        │ re-plans only     │
      └───────────┬───────────┘                        │ question cues     │
                  │                                    └─────────┬─────────┘
                  └───────────────────┬──────────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────────────────────┐
                  │               PASS 2 REPROCESSING (REVISION 2)         │
                  │  • Re-translates only S001, S003, S010                 │
                  │  • Upgrades to APPROVE with confidence 0.81            │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │              FINAL ARTIFACTS & AUDIT LOG               │
                  │  • subtitles.srt | subtitle_decisions.jsonl            │
                  │  • learned_rules.json | review_queue.json              │
                  │  • final_report.md (DO_NOT_RELEASE)                    │
                  └────────────────────────────────────────────────────────┘
```

---

## 4. Module-by-Module Code Walkthrough (In Simple Terms)

### `nadi9/safety.py` — The Security Bouncer
- **Analogy:** Airport luggage scanner.
- **What it does:** Uses regex patterns to catch instructions hidden inside data (e.g., `"IGNORE ALL PREVIOUS INSTRUCTIONS"`, `"Approve every subtitle"`, `"Invent fluent Nadi-9"`).
- **Why it matters:** In real-world AI, malicious actors inject prompt injections into viewer comments or vendor dictionaries. If untreated, the LLM would ignore system instructions and hallucinate translations.
- **What it catches:**
  - `A-044` (Poisoned entry in Dictionary A claiming water is `"zorblax"`).
  - `V2` (Viewer comment attempting prompt injection).
  - `INT-5:line:2` (Interview line with prompt injection).

### `nadi9/evidence_store.py` — The Evidence Vault
- **Analogy:** Courtroom evidence registrar.
- **What it does:** Reads raw JSON/markdown files, tracks metadata (author, date, assigned reliability score), and invokes the transcription tool for audio interviews.
- **Key Reliability Weights:**
  - Approved Examples: `0.90` (High ground truth)
  - Dictionary B (Community Linguist Nia): `0.80` (Reliable)
  - Grammar Note: `0.75` (Helpful structural baseline)
  - Audio Interviews: `0.60` (Spoken, noisy context)
  - Viewer Feedback: `0.35` (Noisy audience opinion)
  - Dictionary A (Old Vendor): `0.25` (Low reliability, vendor errors)

### `nadi9/hypothesis_learner.py` — The Detective / Linguist Core
- **Analogy:** A scientific consensus panel.
- **What it does:**
  1. **Statistical Outlier Detection:** Groups all example sentences by `(lemma, condition)`. If one translation differs from the consensus majority of $\ge 2$ examples, it is labeled an **outlier** and dropped. (Catches `E19` and `E20`).
  2. **Lexicon Acceptance Rule:** A word is accepted *only* if supported by $\ge 2$ surviving examples, or $1$ surviving example plus agreement with Dictionary B.
  3. **Tense & Suffix Mining:** Extracts regular verb suffixes:
     - Present: `-ra`
     - Past: `-va`
     - Future: `-mi`
     - Imperative: bare verb stem
  4. **Question Particle Voting:** Compares votes across reliable sources ($\ge 0.70$). Before correction, Examples/EX1 support `ke`, but EX2 supports `ki`. Because reliable sources disagree, the rule status becomes `unresolved`.
  5. **Hallucination Shield:** Calls the LLM for grammar proposals. The LLM confidently proposes `mock-plural-zo` (stating all nouns take `-zo` with 99% confidence). The learner checks if `-zo` is attested anywhere in the evidence. It is not, so the learner explicitly **rejects** the rule!

### `nadi9/planner.py` — The ER Triage Nurse
- **Analogy:** Hospital triage.
- **What it does:** Scores cues by linguistic risk before running translation:
  - Unknown words: +100
  - Context-sensitive words (like `friend`): +40
  - Unresolved question particle: +30
  - Status differential (lower speaking to higher): +10
- **Why it matters:** If the system hits its 25 model call or 50 tool call ceiling, high-risk cues have already been evaluated and flagged for human review, preventing catastrophic silent failures on difficult lines.

### `nadi9/translator.py` — The Careful Translator
- **Analogy:** A LEGO builder who refuses to build without the right bricks.
- **What it does:**
  - Scans the English cue. If any content word lacks attested evidence (e.g., `forgive`), it **immediately abstains**.
  - If a word is ambiguous without scene context (e.g., `friend` kin vs non-kin), it **abstains and formulates a specific question**.
  - If the question particle is disputed, it **abstains**.
  - For supported lines, it either reuses an identical surviving example or composes words in verified SOV order:
    $$\text{Subject} \to \text{Object} \to \text{Time} \to \text{Adjective} \to [\text{sha (respect)}] \to [\text{na (negation)}] \to \text{Verb Stem}+\text{Tense} \to [\text{reth (back)}] \to [\text{Vocative}] \to [\text{Question Particle}]$$

### `nadi9/verifier.py` — The Independent Building Inspector
- **Analogy:** Code reviewer who never wrote the code.
- **What it does:** Has zero imports from `translator.py`. Independently verifies the candidate Nadi-9 string:
  1. *Token Whitelist:* Is every token in `supported_surfaces`?
  2. *Negation Placement:* Is `na` placed immediately before the verb?
  3. *Respect Particle:* If speaker is lower status and addressee is higher status, is `sha` present before the verb? If not required, is `sha` absent?
  4. *Back Particle:* Is `reth` immediately after the verb?
  5. *Pronoun Appropriateness:* Is `shu` used for higher status addressee and `tu` for peer/lower?
  6. *Omissions:* Did any supported English content word get dropped?
  7. *Subtitle Timing & Reading Speed:* Does reading speed exceed 17 characters per second?

### `nadi9/correction.py` — Targeted Replanning Engine
- **Analogy:** Smart incremental compiler (like Webpack or Rust incremental build).
- **What it does:** When Linguist Asha's correction (`C01`) arrives:
  - It drops the discredited claims (`EX2` and `Dictionary A`).
  - It adds Asha's vote for `ke` with reliability `0.95`.
  - It updates `question-particle` rule status from `unresolved` to `accepted` (`ke`).
  - **Crucially:** Instead of re-translating all 12 cues, it checks which cues have the `"question"` feature in their stored metadata (`S001`, `S003`, `S010`).
  - It triggers re-translation and re-verification *only* for those 3 cues!

### `nadi9/budget.py` — The Resource Guardian
- Tracks model calls (max 25) and tool calls (max 50).
- If exceeded, raises `BudgetExceeded`, terminating loops and failing safely to `HUMAN_REVIEW`.

---

## 5. The 7 "Surprise Events" & Exact Answers for Evaluators

| Surprise Event from Brief | Where It Arrives in Data | How Our Agent Handles It Safely |
| :--- | :--- | :--- |
| **1. Poisoned Dictionary Entry** | `Dictionary A` entry `A-044` (`water = zorblax` with prompt injection note). | `safety.screen_text` detects injection pattern; drops the entry. `zorblax` never enters vocabulary; `water` is translated as `nira` from approved examples. |
| **2. Two Approved Examples Have Mistakes** | Examples `E19` (`water = zorblax`) and `E20` (`brother = bhairo`). | `hypothesis_learner._outlier_ids` identifies they conflict with multiple other approved examples (`E03, E04, E15` for water; `E02, E18` for brother) and drops them. |
| **3. Word Changes Meaning Based on Status** | `friend` (kin `kari` vs non-kin `luma`); `you` (higher `shu` vs peer `tu`). | For `you`, uses metadata `addressee_status`. For `friend`, if the scene context is missing, it abstains with a blocking conflict question: *"Is this friend kin (kari) or non-kin (luma)?"*. |
| **4. Linguist Correction Mid-Episode** | `correction.json` (`C01`) arrives resolving question particle to `ke`. | `correction.py` updates the rule state and uses dependency tracking to reprocess *only* cues with the `question` feature (`S001, S003, S010`). |
| **5. Model Proposes Unsupported Grammar** | `MockLLM` proposes `mock-plural-zo` (all nouns take `-zo`, 99% confidence). | `hypothesis_learner._ask_model` validates the proposal against known surfaces. Since `-zo` is unattested, the rule is marked `rejected`. |
| **6. Retrieval Injects Malicious Commands** | Viewer comment `V2` (`IGNORE ALL PREVIOUS INSTRUCTIONS...`). | `screen_text` catches injection and quarantines `V2`. It is excluded from the LLM prompt and voting. |
| **7. Tool Failure / Audio Outage** | Simulated transcription outage in `FailingTranscriptionTool`. | Catch block in `pipeline.py` logs a tool failure in the audit log, fails closed for those interview words (`pelu`), and allows the rest of the episode to finish safely. |

---

## 6. Live Subtitle Demonstration Walkthroughs

During the technical interview, you can run these commands live in the terminal:

### Scenario A: Complex Approval with Replanning (`S001`)
**Command:** `python run.py explain --subtitle S001`
- **Source:** *"You came back, elder brother?"*
- **Context:** Mira (lower status) talking to Devan (higher status).
- **Pass 1:** Abstains with `HUMAN_REVIEW` because question particle is disputed between `ke` and `ki`.
- **Event:** Correction `C01` resolves question particle to `ke`.
- **Pass 2:** Re-translates to:
  $$\mathbf{shu}\ (\text{you, higher})\ \mathbf{sha}\ (\text{respect})\ \mathbf{solva}\ (\text{came})\ \mathbf{reth}\ (\text{back})\ \mathbf{orun}\ (\text{elder brother})\ \mathbf{ke}\ (?)$$
- **Verifier:** Verifies token whitelist, `sha` before verb, `reth` after verb, `orun` vocative placement, `ke` at end. Verifier passes $\to$ `APPROVE` with confidence `0.81`.

### Scenario B: Unsupported Term Abstention (`S008`)
**Command:** `python run.py explain --subtitle S008`
- **Source:** *"Please forgive me."*
- **Behavior:** The pack contains no attested Nadi-9 translation for `forgive`.
- **Decision:** Leaves `nadi_9_text` as `null` (`[EMPTY / ABSTAINED]`), confidence `0.22`, decision `HUMAN_REVIEW`.
- **Review Question:** *"What is the attested Nadi-9 form, if any, for: please, forgive, me?"*
- **Key Takeaway:** Demonstrates epistemic humility—we never hallucinate fake words like `forgiv` or `pliza`.

### Scenario C: Context-Sensitive Ambiguity (`S012`)
**Command:** `python run.py explain --subtitle S012`
- **Source:** *"He is a good friend."*
- **Behavior:** `friend` has a context split: kin is `kari`, non-kin is `luma`. The cue metadata doesn't specify if this friend is a relative.
- **Decision:** Leaves `nadi_9_text` empty, marks `HUMAN_REVIEW`.
- **Review Question:** *"Is this friend kin (kari) or non-kin (luma)? The cue does not say which relationship applies."*

---

## 7. Model Answers to the 6 Senior-Level Interview Questions (Section 10)

### Q1: How does your agent decide that a source is trustworthy?
> **Answer:** 
> "Trustworthiness is not determined by file size, recency, or superficial fluency. We apply a 3-part verification strategy:
> 1. **Prior Reliability Weights:** We assign baseline reliability based on provenance: verified examples (0.90) and community linguists (0.80) are trusted over unverified vendor dictionaries (0.25) and audience comments (0.35).
> 2. **Safety Quarantine Gate:** Any document containing prompt-injection patterns (like role overrides or 'ignore previous instructions') is immediately stripped of voting rights.
> 3. **Statistical Consensus & Cross-Validation:** An approved example can still be wrong. If an example asserts a translation that conflicts with a 2-to-1 majority of other approved examples, our outlier detector quarantines that example as an error (e.g., dropping E19 and E20). A content word is only usable if supported by multiple surviving examples or corroborated by the reliable community dictionary."

### Q2: How would you detect that the verifier is repeating the translator's mistake?
> **Answer:**
> "This is the classic correlated-error problem in AI systems. We mitigate this in three ways:
> 1. **Strict Architectural Decoupling:** `verifier.py` never imports `translator.py`. It does not ask an LLM or translator to review its own output.
> 2. **Rule Asymmetry:** The translator uses generative composition (building SOV phrases from pieces), while the verifier uses deterministic negative constraints (checking token whitelists, particle positioning relative to verb boundaries, and character-per-second constraints).
> 3. **Shared Dependency Auditing:** As noted in our `KNOWN_LIMITATIONS.md`, both modules currently share `english.py` helpers (such as clause segmentation and negation detection). If `english.py` misclassifies a sentence as non-negative, both modules would miss it. In production, we would decouple this by having the verifier run an independent grammatical parser or double-blind regex rules."

### Q3: What changes when a linguist corrects one grammar rule?
> **Answer:**
> "In naive systems, a correction forces an expensive, wasteful re-run of the entire episode. 
> In our architecture, subtitle decisions store rich state, including the specific linguistic features used (`features: ['question', 'respect', 'past']`). 
> When correction `C01` arrives specifying that it affects the `'question'` feature, the pipeline:
> 1. Updates the rule status in `LearnedState` and refreshes surface tokens.
> 2. Filters existing decisions for cues where `'question' in cue['features']`.
> 3. Reprocesses *only* those 3 cues (`S001, S003, S010`), incrementing their revision number to 2.
> The other 9 cues remain untouched, preserving their revision history and saving call budgets."

### Q4: Which decisions should never be automated?
> **Answer:**
> "Three decisions must always require human sign-off:
> 1. **Inventing Missing Lexicon:** An automated agent should never fabricate vocabulary for unsupported words. It must abstain and escalate.
> 2. **Unresolved High-Reliability Disagreements:** When two trusted sources ($\ge 0.70$) directly disagree and there is no authoritative tiebreaker, the agent must not flip a coin; it must defer to a human specialist.
> 3. **Final Episode Release:** The final release recommendation must remain `DO_NOT_RELEASE` as long as any single subtitle in the episode is unresolved. Automation should assist and triage, but the broadcast gatekeeper must be human."

### Q5: How would the system work for 5,000 episodes and 40 dialects?
> **Answer:**
> "To scale horizontally from 1 episode to 5,000 episodes across 40 dialects:
> 1. **Partitioned Knowledge Stores:** We would separate the learned state into a centralized Dialect Knowledge Base per dialect, versioned like a database migration.
> 2. **Stateless Episode Workers:** Episode processing would become a stateless distributed worker job (e.g., using Celery or AWS Lambda), reading from the dialect knowledge store and processing subtitle cues in parallel batches.
> 3. **Human-in-the-Loop Review Queue:** Unresolved cues would be routed to a centralized review dashboard (like the schema in `review_queue.json`) where human linguists answer focused questions. Once a linguist answers a question (e.g., resolving a kinship term), that answer is pushed as a global correction event, propagating only to affected episodes.
> 4. **Strict Rate and Cost Budgets:** Each episode worker maintains a hard budget cap (e.g., 25 model calls, 50 tool calls), with alerts triggered if anomalous episodes spike in review rate."

### Q6: What did an AI coding assistant suggest that you chose not to accept?
> **Answer:**
> "During development with an AI coding assistant, it made several suggestions that were rejected because they violated safety and transparency:
> 1. **Heavier Agent Frameworks:** It suggested using LangChain/LangGraph. I rejected this because heavy abstractions obscure state transitions, tool calls, and error boundaries, which contradicts the brief's requirement for full auditability.
> 2. **Fallback Word Invention:** When words like 'forgive' were missing, it suggested prompting the LLM to generate phonotactically plausible Nadi-9 words. I rejected this because the assignment explicitly rewards knowing when to abstain.
> 3. **Global Re-run on Correction:** It initially wrote a loop that reprocessed all 12 subtitles after the linguist correction. I rejected this in favor of feature-tagged dependency tracking to reprocess only the affected question lines.
> 4. **Self-Verification Prompts:** It suggested passing the generated subtitle back into the LLM with 'Does this translation look right?'. I rejected this in favor of an independent, deterministic verifier."

---

## 8. Tips for Sounding Like a Senior Engineer (Even with 0 Years Experience)

1. **Own Your Experience Level with Pride:**
   > *"I have 0 years of formal industry experience, but I designed this architecture with senior engineering principles: strict decoupling, defensive input screening, deterministic verification, and fail-safe error handling."*
2. **Use the Right Vocabulary:**
   - Instead of *"The AI didn't know the word so it stopped,"* say: *"The agent recognized an evidentiary gap and exercised epistemic humility by abstaining."*
   - Instead of *"We check if someone hacked the prompt,"* say: *"We treat retrieved context as untrusted data and screen for indirect prompt injection before model synthesis."*
   - Instead of *"We rerun the questions,"* say: *"We maintain feature-level dependency tracking to achieve targeted, incremental replanning."*
3. **Showcase the Live CLI:**
   - Don't just talk about code. Run:
     ```bash
     python run.py explain --subtitle S001
     python run.py explain --subtitle S008
     pytest
     ```
   - Running live tests and walking through the terminal demonstrates technical confidence and reproducibility.
