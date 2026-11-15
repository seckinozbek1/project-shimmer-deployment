# Design note: instruction optimisation on the development set (#255, D-567 step 3; accepted with conditions, lead 14:05, 13 November)

Written before any code or read. Instructions only, in the MIPROv2 style: no demonstrations, no training, no threshold tuned on held-out rows.

## 1. Targets

The frozen texts are left out. These are the PROCESSOR two-turn prompt (`config/compact_extraction_prompt.json`, EXTRACTION-A, check 263), everything the decoding policy pins (DECODING-A protocols), and B1's prompt (`b1_prompt.json`, the comparator; it is the baseline and is never optimised).

| # | Target | Lives in | Read by | Decided from |
|---|---|---|---|---|
| T1 | passage_pair decision question | `config/passage_pairs.json` `decision.template` | `passage_pairs.render` and `pair_judge_prompt.json` (held equal by check 324) | JUDGE's choice probabilities (CHOICE-A) |
| T2 | cell_claim decision question | `config/cell_selection.json` `decision.template` | `cell_selection.question` and `choice_judge_prompt.json` claim form (check 326) | JUDGE's choice probabilities |
| T3 | rule_check question | `config/auditor_questions.json` `rule_check` | the paired review's uncomputable plans (INFRA-051) | choice probabilities |
| T4 | pair_fidelity question | `config/auditor_questions.json` `pair_fidelity` | VERIFIER's narrow form | choice probabilities |
| T5 | the narrowed producer roles' questions | `config/producer_questions.json` | `producer_questions.py` (INFRA-050) | all forms are `reply` today, so out of scope until adopted |
| T6 | the agent-need questions | lane/assign-model's voter references (path to confirm with that lane) | the assignment layer's later model step | out of scope until that lane lands |
| T7 | the case questions | `config/case_questions.json` | CASE-QUESTIONS-A | agent is null, nothing asked, so out of scope |

**Scope before the claim read: T1 and T2 only.** They are the two questions the K1 configuration actually asks. T3 and T4 come after their forms are adopted.

**Equality checks move with the text.** Changing T1 or T2 also changes the replay forms that checks 324 and 326 hold equal to them. So a candidate is written to both files in one commit, and the checks stay green.

## 2. Development material and the split

**Sources.** Only the development pools the leakage check kept apart from the gate set:
- `external/contradoc/dev` and `external/scitab/dev`;
- minus every G1 item, since G1's half B is spent (D-294) and half A fixed the current thresholds;
- minus the gate set: disjointness is CERTIFIED ON ROLE B'S SIDE (L separation, D-558). A check that reads the gate's ids returns only counts and a pass or fail per development pool (gate_leakage's split). The optimiser and this lane receive the pool names and pass or fail, never a gate id, an excluded group or a paper id. Until a pool is certified, only tooling is built;
- nothing from role B's holdout.

**Build.** Built by the adapters (`--side holdout --development` is NOT used; the development side only), staged with `tools/stage_workload.py`. Keys are read only through `tools/score_corpus.py`.

**Split.** A seeded split by group (ContraDoc) and by paper (SciTab):
- FIT, 60 percent: candidates are generated and scored on it, and each candidate's threshold is chosen on it by `choice_read.choose_threshold` (C_BAR's rule).
- HELD-OUT, 40 percent: read ONCE, at the end, for the single chosen candidate and the shipped text, through a `HELDOUT_OPENINGS.md` row (Part `instruction-opt-<target>`, k 1, alpha 0.025) committed before the read. It is stated in every report as the held-out read.

**Sizes (to confirm by count at build).** ContraDoc: the dev pool less G1 is about 100 documents, so about 60 fit and 40 held-out. SciTab: about 15 tables (about 90 claims) fit and 10 (about 60) held-out. If a pool is smaller, the read is reported as underpowered, never resized after a look.

## 3. The loop (MIPROv2-style, instructions only)

**Proposer.** Qwen2.5-7B base (local_producer family), on Lambda through the replay pass. The answering model is JUDGE, Phi-4 (another family), so the optimiser never grades its own writing.
- Meta-prompt: the target's current text, its fixed answer set (which must stay byte for byte, with the answers' first tokens distinct, as CHOICE-A refuses otherwise) and failure TYPES from FIT only (counts per gold class and per decided class). No item text from held-out ever reaches it.

**Candidates.**
- ONE round of 8 candidates per target (D-598, Seckin 12:35, 13 November: the second round is dropped). T2 (SciTab) runs first, being cheaper, then T1.
- Each candidate is screened in Python before any call: the answer set is unchanged, the placeholders (`{passage_a}`, `{passage_b}`, `{cells}`, `{claim}`, `{tools}`) are present exactly once, and the length is under the shipped text plus 50 percent.

**Scoring.**
- Each candidate is rendered into a choice prompts file (`choice_judge.py build` with the candidate in place of the template, on a branch copy) and run on the A10 as a B1 replay bundle (form choice, no bound controller file).
- `choice_read` gives the probabilities; the threshold comes from FIT; the label goes through `tools/score_corpus.py`.
- Metric per target, the paper's: T1 is ContraDoc binary accuracy with ABSTAIN wrong; T2 is SciTab 3-class macro-F1 (the gate's declared setting).

**Selection.** The FIT figure is the mean over 2 seeded FIT minibatches. The best candidate goes forward only if it beats the shipped text on FIT by at least 2 points; otherwise the shipped text stands and no held-out read is opened.

**WORDS-A.** The proposer writes texts. Python checks only structure: placeholders, the answer set, length. Nothing in code decides what a candidate's words mean.

## 4. Counts, time and cost (estimates; measured rates where named)

| Item | Prompts | Time |
|---|---|---|
| T1, one candidate on FIT | 60 documents x up to 40 pairs x 2 orders, at most 4,800 choice passes | at 0.36 s (measured, D-476): about 29 min |
| T1, a minibatch of 25 documents | 2,000 passes | about 12 min |
| T2, one candidate on FIT | about 90 claims | about 1 min |
| Proposer, the one round | 2 targets x 8 candidates | under 5 min of generation |

**The one round (D-598).**
- T2 first: 8 candidates x 2 minibatches x 1 min, about 16 min plus 14.5 min set-up on one machine.
- T1 then: 8 candidates x 2 minibatches x 12 min, about 3.2 h of A10, split over 2 machines, about 1.6 h each plus 14.5 min set-up each.
- Final held-out read for the chosen candidate and the shipped text: T1 2 x 40 documents x 80 passes, about 32 min; T2 2 x 60 claims, about 1 min. One machine.

**Cost at 1.29 USD an hour.**

| Part | Estimate |
|---|---|
| T2 fit | about 0.5 h, about 0.7 USD |
| T1 fit | 2 x 1.85 h = 3.7 h, about 4.8 USD |
| Proposer | 1 short launch, about 0.5 USD |
| Held-out | about 1.2 USD |
| **Total** | **about 7.2 USD (9.4 with the guard's 1.3 factor); was 12.7 (16.5) with two rounds** |

**Seals.** Through the Lambda sealing path (#252), not on the laptop. Runs are planned for 14 to 15 November, after #252's test job (about 14 November, midday).

**Wall time.** About half a day: one proposer launch, the T2 job, then the T1 job, each sealed through #252. The budget question (now about 9.4 USD with the factor) is with Seckin.

**Tooling to build first, about 4 h.** A candidate renderer, the Python screen, a FIT driver that writes one prompts file per candidate, and the held-out reader that refuses without its committed opening.

## 5. The bar (written before any read)

Adopt a candidate for a target only if all of these hold:
1. **FIT:** at least 2 points over the shipped text (mean of the 2 minibatches).
2. **HELD-OUT, read once:** the candidate's metric minus the shipped text's is at least 3 points, with the paired bootstrap 97.5 percent interval (clusters: documents or tables) above zero, through the same scoring functions `gate_score.compute` uses (labelled "not a gate read").
3. **Integrity:** no more decisions refused than the shipped text (CHOICE-A ties, mass) on HELD-OUT.

Otherwise the shipped text stays. Either way the result is recorded with both figures and the opening row. Adoption is a recorded decision; checks 324 and 326 move with it.

## 6. Not built on, stated

- The gate set and the quick subset are never read by any step here.
- Thresholds are re-chosen on FIT for each candidate. A candidate that changes the answer tokens is refused by the screen.
- The proposer sees counts and types only, never held-out items.
