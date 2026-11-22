# Shimmer results

Every result Shimmer has, newest first: the first results on untouched items of 21 November 2026 (seen and untouched items apart), the first results of November 2026 with their
sources, the earlier development state, the development results to 31 October 2026, the
testing rules and how to reproduce the evaluation. Every figure on this page is a
development or validation figure, except the untouched-item figures of 21 November 2026. The final test set has not been run. The short
[README](../README.md) gives a summary; the earlier README sections on results were moved
here on 19 November 2026 (D-816).

## Scores at a glance (22 November 2026)

Every measured set, one row each. "Untouched" items were not used to build or tune the system; "seen" items were. The same table stands near the top of the README and on the progress page.

| Measure | Set | Items | Answered | Score |
|---|---|---|---|---|
| Contradictions (ContraDoc), system | untouched | 8 documents | 8 | accuracy 0.875 (range 0.625 to 1.0, chance test p 0.249) |
| Table claims (SciTab), system | untouched | 15 claims | 13 | accuracy 11 of 13 answered = 0.846 (range 0.769 to 1.0, 4 tables, chance test p 0.026); 2 of 15 unanswered (13.3 percent); unanswered counted wrong: 11 of 15 = 0.733; coverage rule loosened by the project owner's decision for this set, after the result was seen |
| Negotiation, conflict, system | untouched | 31 synthetic items, 197 proposals | 192 | 0.955 (range 0.924 to 0.980, p 0.0001) |
| Negotiation, code checks, system | untouched | 31 synthetic items, 197 proposals | 192 | 1.0, with 2.5 percent of pieces dropped |
| Negotiation, open point, system | untouched | 31 synthetic items, 197 proposals | 192 | 0.393 (range 0.342 to 0.452, p 0.753) |
| Negotiation, stance, system | untouched | 31 synthetic items, 197 proposals | 192 | 0.299 (range 0.219 to 0.389, p 0.938) |
| Negotiation, approach, system | untouched | 31 synthetic items | too few | no score: too few answers for the coverage rule |
| Negotiation, open point, cloud model | untouched | 20 synthetic items, 132 proposals | 132 | 0.381 (range 0.334 to 0.449); system on the same items 0.407 (range 0.348 to 0.480) |
| Negotiation, stance, cloud model | untouched | 20 synthetic items, 132 proposals | 132 | 0.295 (range 0.221 to 0.364); system on the same items 0.330 (range 0.244 to 0.435) |
| Negotiation, open point and stance, bare model | untouched | 31 synthetic items, 197 proposals | 77 | no score: more than 5 percent of answers missing (120 of 197) |
| Table claims (SciTab), system | seen | 78 claims, 13 tables | not given here | three-class macro-F1 0.598 (range 0.444 to 0.656, chance p 0.0001) |
| Contradictions (ContraDoc), system | seen | 15 documents | not given here | accuracy 0.533 |
| Negotiation, conflict, earlier system | seen | 18 items, 179 proposals | not given here | three-class macro-F1 0.629 |
| Negotiation, open point and stance, earlier system | seen | 18 items, 179 proposals | not given here | 0.435 and 0.330 |

The coverage rule (at most 5 percent of answers missing) still holds for every other measurement, ContraDoc included. The project owner loosened it for this one SciTab set on 22 November 2026, after the result had been seen.

## First results on untouched items (21 November 2026)

These are first results. The final test set has not run yet, and the alpha fell short of its targets (at least 10 points above the bare model, at most 10 points below the cloud model, and a mark for each of the five negotiation lines, three of them 0.60). Each untouched figure below was scored once, on items the project had not used to build or tune it, with thresholds written before the look, on the frozen code v1.0-alpha (commit f1d58f93). "Alpha" here means the current state of the code, not a finished release.

The bare model is Qwen2.5-7B-Instruct, the open model Shimmer builds on, used on its own with nothing around it. The cloud model is claude-opus-4-8, a large model run by an outside provider. No cloud run exists on the untouched ContraDoc and SciTab items. The cloud target was 5 points until 20 November. Before the look at any untouched item, the project owner changed it to 10, after every earlier check on seen items had missed 5. His reason: 5 points would be an unfair comparison against a large cloud model. No result changed because of this; every earlier check still fell short of 10.

How to read the figures. An interval is the range the true score probably lies in. It comes from a bootstrap: the items are drawn again many times and the score is recomputed each time. The chance test p tells how often luck alone would give a score this good or better; a high p means luck alone often scores this well. Macro-F1 is an average of the score of each answer class, so every class counts equally. The coverage rule refuses a main score when more than 5 percent of answers are missing, held back or filled in by the scoring code.

### Untouched items

| Task | Set | Measure | Result | Interval (95 percent) | Chance test | Note |
|---|---|---|---|---|---|---|
| Contradictions (ContraDoc) | 8 documents, 6 groups | accuracy (7 of 8 documents right) | 0.875 | 0.625 to 1.0 | permutation p 0.249 | not distinguishable from chance; 2 documents hold a contradiction, 1 was found, no false alarm; answering "no contradiction" every time scores 0.75 on this set |
| Table claims (SciTab) | 3 papers, 4 tables, 15 claims, 13 answered | accuracy (11 of 13 answered claims right) | 0.846 | 0.769 to 1.0 (4 tables) | chance p 0.026 | 2 of 15 unanswered (13.3 percent); unanswered counted wrong: 11 of 15 = 0.733; coverage rule loosened by the project owner's decision for this set, after the result was seen (22 November 2026); small set; read on the same answers after a fault in the code that reads them was fixed |
| Negotiation advice, conflict | 31 synthetic items, 197 proposals | conflict detection | 0.955 | 0.924 to 0.980 | p 0.0001 | above the 0.60 mark |
| Negotiation advice, code checks | 31 synthetic items, 197 proposals | share of advice pieces that satisfy the code's own checks | 1.0, with 2.5 percent of pieces dropped (the mark allows at most 10 percent) | not given | not given | at its mark of 1.0 |
| Negotiation advice, open point | 31 synthetic items, 197 proposals | open point detection | 0.393 | 0.342 to 0.452 | p 0.753 | below the 0.60 mark |
| Negotiation advice, stance | 31 synthetic items, 197 proposals | stance matches fate | 0.299 | 0.219 to 0.389 | p 0.938 | below the 0.60 mark |
| Negotiation advice, approach | 31 synthetic items, 197 proposals | whom the advice says to approach | none | none | none | refused by the coverage rule: too few answers |

The 31 negotiation items are synthetic: a program wrote them. They are not taken from real negotiations. A proposal is one bracketed option in an article of a draft text. Its fate is what happened to it in the next round: still open, kept, changed, or removed. Conflict detection asks whether a proposal clashes with the position of the party being advised. Open point detection asks whether a proposal is still open to change or already settled. Stance matches fate asks whether the advice (accept, counter, reject) matches what the parties did next (kept, changed, removed).

### Seen items

These are figures on items the project had already looked at while building the system, measured before the look at the untouched items. They are development figures and do not show accuracy on untouched documents.

| Task | Set | Measure | Result |
|---|---|---|---|
| Table claims (SciTab) | 78 seen claims, 13 tables | three-class macro-F1 | 0.598 (interval 0.444 to 0.656, chance p 0.0001) |
| Contradictions (ContraDoc) | 15 seen documents | accuracy, same scoring rule as the untouched set | 0.533 |
| Negotiation advice | 18 headline items (179 proposals) of a 24-item development pilot, an earlier version of the system | three-class macro-F1 on conflicts | 0.629 |
| Negotiation advice | the same 18 items | open point detection / stance matches fate | 0.435 / 0.330, both below the 0.60 mark |

The seen SciTab figure is a three-class macro-F1; the untouched figure is an accuracy on the answered claims, so the two are not directly comparable. The older ContraDoc and negotiation figures in the section below use other scores or other versions of the system.

### Comparison with the bare and the cloud model (negotiation, open point and stance)

| Measure | Bare model | Cloud model (20 items) | System (31 synthetic items, 197 proposals) | System (same 20 items) |
|---|---|---|---|---|
| Open point detection | no figure (120 of 197 proposals unanswered; 81 of 132 on the 20 items) | 0.381 (0.334 to 0.449), 132 proposals | 0.393 (0.342 to 0.452) | 0.407 (0.348 to 0.480) |
| Stance matches fate | no figure (same reason) | 0.295 (0.221 to 0.364) | 0.299 (0.219 to 0.389) | 0.330 (0.244 to 0.435) |

The cloud model answered all 31 items. By a rule fixed in advance to limit cost, its answers are scored on a set of 20 items. We also scored the system on those same 20 items, from its saved answers. Same written rules and scorer, untouched items, one look: a comparison, not a reading against a target. On the same items the system is slightly higher, but the ranges overlap, so the two are about equal. The bare model had no answer for 81 of the 132 proposals on the 20 items, and for 120 of the 197 over the whole set. More than 5 percent were missing, so it gets no figure. The missing answers were checked as a real absence, not a reading fault.

On two hard measures, open point and stance, on 20 synthetic items, the system and the cloud model we tested are about equal. Even the cloud model we tested is far below 0.60 on them, so the measures are hard. The system's open point and stance figures cannot be told from chance, so being level tells us little yet. On synthetic items, what the parties did next was chosen by a program.

On conflict, Shimmer found clashes well on synthetic items (0.955); we have no baseline for this line yet.

Shimmer answered nearly all proposals (192 of 197), while the bare model left 120 of 197 empty; that is coverage, not accuracy. The frozen alpha code ran its own 502 checks: 485 of 502 checks were green, 6 were skipped, and 11 known failures are carried as known.

The 0.60 mark was set for our own benchmark, with no outside source for a normal level, so, taken together with the chance test results, it needs to be reconsidered. The beta will make the benchmark itself more reasonable and will also review the chance test.

Note on seen items, from the answers of the 15 November pilot. On 24 seen items, the cloud model (on its own 14-item subset) scored 0.507 on open point detection (interval 0.425 to 0.612, p 0.51) and 0.396 on stance matches fate (interval 0.292 to 0.537, p 0.0001). Both are below 0.60 too. The bare model and the system as it was then got no figure: more than half of their proposals had no answer piece.

## First results (November 2026)

This section is updated in the same step as every measurement and every stage change (D-481). Last updated: 19 November 2026.

Shimmer is an open-source system that reviews documents against rules a person writes down. Several agents built on models from different families check each other, Python does every comparison that arithmetic or a field check can decide, and every finding a model writes stays marked as unchecked. It also advises on multi-round negotiation drafts.

These are first results. They come from development and validation material, much of it seen while the system was being built. The final test set has not been run, and nothing here shows how Shimmer does on documents it has never seen. We publish them now because the weak results matter as much as the good ones.

**Contradictions in documents (ContraDoc, public benchmark).** On 15 development documents, scored on 19 November 2026, Shimmer found contradictions with an F1 of 0.615 (precision 0.667, recall 0.571). Accuracy on the same documents reads 0.667, but 9 of the 15 were decided by silence; counting only items the model actually decided, accuracy is 0.267. On an earlier 15 documents (18 November) it found 4 of 10 contradictions with no false alarm. On a 40-document steering subset (runs of 18 November, before the latest fixes), Shimmer scored 55.0 percent accuracy, against 52.5 for the same local model used bare and 90.0 for a large cloud model on the same 40 documents (references scored on 13 November). 26 of the 40 went undecided. Under the project's own rules this run does not count, because it is void on integrity with too many items left undecided, and it is well short of both bars (at least 10 points above the bare model, at most 10 below the cloud model: D-842, 5 points until 20 November 2026).

**Claims about scientific tables (SciTab, public benchmark).** On 47 development claims from 15 tables (19 November), Shimmer reached a macro-F1 of 0.776 on the two classes this set holds (supports, refutes) and 0.517 on the declared three-class setting (95 percent interval 0.471 to 0.566); the set has no "not enough information" claims, so the three-class figure cannot exceed 0.667 here. This reading takes the model's most likely answer; the official path, which waits for a threshold not yet chosen, still reads 0.225, the score of answering "supports" every time. On a 78-claim steering subset, older code left every claim undecided (0.190), while the bare model scored 55.8 and the cloud model 81.7 on the same claims. This run, on the same quick subset 0127b080, does not count under the project's rules either (void on integrity, every claim undecided), and it is below both bars.

**Negotiation advice (our own benchmark).** On 18 headline items (179 proposals) of a 24-item development pilot, scored on 18 November, the new system raised the main conflict measure (three-class macro-F1) from 0.419 to 0.629, a paired gain of 0.210 (interval 0.103 to 0.322). Dropped answers fell from 11.2 percent to 0. Open-point detection rose to 0.435 and stance-against-outcome to 0.330, both short of our 0.60 bar. On the same items, the bare model's earlier answers scored 0.217 on the main measure; the cloud model scored 0.648 on 14 of them. Both are references only; every measured Shimmer run so far used local open-weight models.

The weak point is plain: Shimmer found none of the 12 real conflicts. Conflict-class F1 is 0, in three different methods. We traced the cause from the system's own outputs: the step that asks whether a party's position opposes a proposal never chose "oppose" in 1,453 decisions, because most positions were written before the proposal existed, so the question did not fit. A new question now asks whether the proposal, if adopted, would go against what the position asks for. It is built and tested on fixtures, and will be measured on fresh sets of 24 and 40 items made for it. It has not been measured yet.

**What comes next.** The final test set is read once, after the system reaches its written bars on validation items. Until then, every figure here is a development figure.

### Sources of the first results

"(record)" marks a figure whose source is one of the project's private records, kept off the public repository; a source that is public is named with its file and line.

| Number | Source | Set | Items | Date |
|---|---|---|---|---|
| ContraDoc contradiction F1 0.615, P 0.667, R 0.571 | (record) | development, G1 half A, second 15 documents (D1/D2) | 15 documents | run 18 Nov, scored 19 Nov 00:31 |
| ContraDoc accuracy 0.667; 9 of 15 by silence; model-only 0.267 | (record) | same | 15 | 19 Nov |
| ContraDoc 4 of 10 contradictions, no false alarm (accuracy 60.0) | docs/loop/DECISIONS.md:7843 | development, first 15 documents | 15 | 18 Nov (D-737) |
| ContraDoc steering subset 55.0 [40.0, 70.0], 26 of 40 undecided; void on integrity, does not count, below both bars | (record) | quick subset 0127b080, code before the night fixes | 40 documents | run 18 Nov, scored 19 Nov 01:09 |
| ContraDoc bare 52.5 [37.5, 67.5], cloud 90.0 [80.0, 97.5] | (record) | quick subset 0127b080 | 40 | 13 Nov |
| SciTab 2-class macro-F1 0.776 | (record) | development, G1 half A (D1/D2) | 47 claims, 15 tables | 19 Nov 03:37 |
| SciTab 3-class macro-F1 0.517 [0.471, 0.566] | (record) | same | 47 claims | 19 Nov |
| SciTab 3-class ceiling 0.667 (no not-enough-info gold) | (record) | same | 47 | 19 Nov |
| SciTab official path 0.225 (3-class) = all-supports baseline | (record) | same | 47 | 19 Nov |
| SciTab steering subset 0.190 [0.142, 0.227], 78 of 78 undecided; void on integrity, does not count, below both bars | (record) | quick subset 0127b080, code before the night fixes | 78 claims, 13 tables | run 18 Nov, scored 19 Nov 01:09 |
| SciTab bare 55.8 [40.7, 62.7], cloud 81.7 [55.0, 92.9] | (record) | quick subset 0127b080 | 78 | 13 Nov |
| Negotiation M1 0.419 to 0.629 [0.578, 0.665], gain +0.210 [+0.103, +0.322] | (record) | old pilot 6a8af3c7 (development) | 18 headline items, 179 proposals (docs/loop/stages/NEG_ROUND1.md:3-4, 9) | scored 18 Nov 20:02 |
| Negotiation dropped answers 11.2 percent to 0 | (record) | same | 18 | 18 Nov |
| Negotiation M10 0.435, M4 0.330 (bar 0.60) | (record); docs/loop/stages/NEG_BAR.md:9-10 | same | 18 | 18 Nov |
| Negotiation conflict-class F1 0, 12 conflicts | (record) | same | 18 | 18 Nov |
| Conflict F1 0 in plain, stepwise and improved methods | (record) | same pilot | 18 | 19 Nov 15:17 |
| "Oppose" never chosen in 1,453 decisions (147 + 1,306) | docs/loop/stages/NEG_CONFLICT_FIX_REPORT.md:28-29, 44 | stepwise runs' saved replies | 24 items | 19 Nov |
| Bare model M1 0.217 | (record) | same pilot, bare model's saved answers, no Python step | 18 | answers 15 Nov, rescored 16 Nov |
| Cloud model M1 0.648 | (record) | subset of the pilot | 14 | 15 Nov, rescored 16 Nov |
| C4 fix sets: 24-item pilot, 40-item validation, not measured | docs/loop/stages/NEG_CONFLICT_FIX_REPORT.md:126 | fresh sets built for the fix | 24 and 40 | not run |

Comparison conditions to keep beside every reference figure: the steering-subset references are on the same items as Shimmer but from a different run and date; the negotiation bare-model figure is from older saved answers without the Python step; the cloud negotiation figure covers 14 of the 18 items. Every measured Shimmer run so far used local open-weight models; the bare-model and cloud model figures are references only.

## Earlier development results (to 18 November 2026)

**Status: v1, a prototype.** "v1" names this documented state of the repository, published on GitHub on 2 November 2026;
its code version is the one in [VERSION](../VERSION) (`0.1.0.dev8` at this commit; `CITATION.cff` states the same version, gate check 314).
Every result in this repository is a development
result on exposed material (material the project saw while it was being built).
None of it is a held-out or sealed result, and none of it shows how well Shimmer
works on documents it has not seen. After v1, a fresh, unseen set is read only if
the whole system first passes a gate on development items no attempt was tuned on
(D-S92, D-371 in docs/loop/DECISIONS.md). As of 11 November 2026 the gate had not
been measured, and the loop's deadline for it was 14 November 2026; on 18 November
2026 no gate result existed yet, and the first results above are development and
validation figures. This
version is not released as a Python package, and no package release is promised.

In development, on the four public benchmarks measured by 31 October 2026 (ContraDoc, SciTab, ContractNLI and CUAD), Shimmer scores below the bare model on two (ContraDoc, and CUAD, where it found none of the gold flags), ties it on ContractNLI on precision, recall, F1 and accuracy (the bare model leads only on correct refusals), and is about even on SciTab (F1 0.571 against 0.600); it leads only on the synthetic suite (F1 0.875 against 0.614), whose rules are the kind its own computations were built for. On the public benchmarks the rule items go instead to judging calls by PRACTICE_AUDITOR on the local auditor model, and in L12's six B3 entries 686 of its 803 answers copy the filled example in its own contract (VIOLATION, missing_field), 409 of 410 on CUAD; the quote rule refuses them, so nothing is kept (the parallel track's measurement on the saved runs, 1 November). The work after v1 that addressed it, recorded as D-S22 in docs/loop/DECISIONS.md (D-176): a Python-only refusal of answers with no quote, figures or earlier version behind them (R1) is merged (D-210), and a document-level judging experiment (G1) gave no usable signal on either model (D-248). The gate above is the next step.

### Which benchmarks count

On 4 November 2026 the operator cancelled CUAD and ContractNLI for all further development work, for poor fit, after their development scores were known (D-S34, applied in D-226 in docs/loop/DECISIONS.md); the record gives no reason beyond poor fit. The gate (D-S92, 9 November 2026, D-371) is read on ContraDoc and SciTab only. PUBHEALTH is a separate out-of-domain check, not part of the gate, and CLadder and Corr2Cause are a causal probe, an indicator rather than a Shimmer benchmark (D-335, D-357); as of 11 November 2026 none of the three has been measured.

### The state on 18 November 2026

This is the README's former "Where Shimmer is now" section as it stood on 18 November 2026, kept for the record; the first results above replace it.

**Version 1.0 is not released yet.** It waits until the negotiation advisor reaches its written bar on the validation items (standing order 102): on the 31 untouched synthetic items its conflict line is 0.955, but open point detection (0.393) and stance matches fate (0.299) are below the 0.60 mark. No final test, release or ablation starts before that.

**Since 15 November.** The full gate ran green on Lambda on the code pushed on 17 November. A development run on two ContraDoc documents showed that the faster inference engine (vLLM) hands the GPU back before every other model loads: every entry reached its end with no failed call, at one server restart of about two minutes per document. Four launch hazards met during the night runs are fixed, each with its own gate check.

**Which code these documents describe.** The code on GitHub's main branch is the loop's merged and checked state, pushed as one snapshot commit (tag `code-2026-11-15-a`) after a pre-push scan. Later code changes are pushed the same way, with their documents (D-488, D-650).

**Then.** No gate result existed yet. Every figure Shimmer had was development, exposed and in-sample.

- A second steering read on a quick subset of the gate set did not pass: too many entries were void on integrity. No figures from it are quoted, because a void read measures the run, not the system. (The first results above give a later read of the same quick subset, run on 18 November; it is void on integrity too and does not count.)
- One cause of that is found: a retry step re-asked a refused extraction with a narrower context than the one its answer was checked against, so good answers were refused. The fix is written and is now being proven on development items before it is read again.
- Most remaining misses came from parts that Python compared and found consistent, so no model was asked there. A model is now asked in those places too, and its answer stays marked as not checked by Python. Where arithmetic or a field check can decide, Python still decides.
- A faster inference engine, vLLM, scored as well as the current engine on development items and is being built into the pipeline, one part at a time, each part checked against correct answers before use.
- Every parser and scorer is being made tolerant of answer form (spaces, case, quotes, a number written for a string, code fences), the same way for every system compared, so that no answer is dropped for its form alone. No scored measurement runs until this is done.

### Our negotiation benchmark

Beside the public benchmarks, Shimmer is building its own benchmark for multi-round negotiation drafts:

- each item's answer comes from what the parties actually did in the real next round, not from a judgement written afterwards;
- agent labels are checked twice, by two agents of different model families, with a third for ties, and their agreement is reported;
- the items, the labels and the scorer are frozen before any system is run on them; the benchmark is to be published with its scorer (for sources whose terms do not allow the texts to be shared, the source links instead, so anyone can fetch them and rerun);
- a small pilot has run. It is indicative only, below the size needed for a claim; it is used to find and fix faults in the measurement, never to tune the system. Its first results, labelled as such, are in the first results above.

## Development results to 31 October 2026 (development, exposed)

Purpose: development measurement and run health, on exposed material, with no seal and no manifest.

**Every figure on this page is a development figure on exposed material.** The documents were seen while Shimmer was being built, the samples are a handful of documents per benchmark, and one run per document is counted; runs that failed integrity were re-run up to twice (L12c re-ran five entries once more, which this page does not score; see the L12b section). No figure here is a held-out or sealed result, and none supports a claim about accuracy on unseen material. Sealed results, when they exist, are added to this page beside these and replace nothing on it.

**In one sentence.** On the four public benchmarks measured, Shimmer scores below the bare model on two (ContraDoc, and CUAD, where it found none of the gold flags), ties it on ContractNLI on precision, recall, F1 and accuracy (the bare model leads only on correct refusals, 5 of 11 against 0), and is about even on SciTab (F1 0.571 against 0.600); it leads only on the synthetic suite (F1 0.875 against 0.614), whose rules are the kind its own computations were built for. On the public benchmarks the rule items go instead to judging calls by PRACTICE_AUDITOR on the local auditor model, and in L12's six B3 entries 686 of its 803 answers copy the filled example in its own contract (VIOLATION, missing_field), 409 of 410 on CUAD; the quote rule refuses them, so nothing is kept (the parallel track's measurement on the saved runs, 1 November). The work that addresses it comes after v1: a document-level judging experiment (G1) and a Python-only refusal of answers with no quote, figures or earlier version behind them (R1), recorded as D-S22 in docs/loop/DECISIONS.md (D-176), then the sealed evaluation.

**Which benchmarks count after this page (note of 11 November 2026).** The four public benchmarks above were measured in development. On 4 November 2026 the operator cancelled CUAD and ContractNLI for all further development work, for poor fit, after their development scores on this page were known (D-S34, applied in D-226 in docs/loop/DECISIONS.md); the record gives no reason beyond poor fit. FinDVer was left where it was (D-226). The gate that decides whether the fresh set is read (D-S92, 9 November 2026, D-371) uses ContraDoc and SciTab only. PUBHEALTH is a separate out-of-domain check, not part of the gate, and CLadder and Corr2Cause are a causal probe, an indicator rather than a Shimmer benchmark (D-335, D-357); none of the three has been measured yet. Nothing on this page was changed by these decisions.

Built on 31 October 2026 from runs already done (L4a to L12b), revised on 2 November 2026 (L12c is listed but not scored: no committed record holds its scores). No launch was made for this page. The saved run outputs and builds behind it were lost in the 16 November 2026 data loss on the build machine (D-704): the older development figures on this page can no longer be re-scored; only their recorded results remain. These development runs were not preregistered. For sealed results, the order of preregistration, freeze and sampling will be attested only by the project's local records.

## How to read the tables

- **Arms.** B3 is Shimmer, the whole pipeline in paired review. B1 is the bare model: the main reading agent's model given one fixed prompt per item and no pipeline. "B1 tuned" carries the producer's tuned adapter; "B1 base" is the same model without it, and exists only where a run made it.
- **Benchmark mode and as shipped** (docs/benchmarks/SCORING_MODES.md, decisions D-113 and D-S13 item 9). Benchmark mode counts every model judgement the pipeline shows as advice as a finding; it is the main figure. As shipped is S-8: only Python's findings, every model-written record left out. A user's review is the same in both; advice stays labelled as advice. **This scoring rule was chosen after development scores had been seen.**
- **A finding** is an item labelled with the benchmark's flag class: ContractNLI contradiction, SciTab refutes, ContraDoc contradictory, CUAD absent, FinDVer refuted, the synthetic suite violated. Precision, recall and F1 are those of the flag class. "n/a" means the arm flagged nothing, so precision is undefined.
- **Correct refusal rate**: of the items whose gold label is the benchmark's "cannot be settled" class (ContractNLI not mentioned, SciTab not enough info), the share the arm labelled with that class. ContraDoc, CUAD and FinDVer have no such class.
- **Time per document**: the workload minutes of the run on the instance (model loading included), from each entry's own timing record. A B1 entry that ran two checkpoints counts half its minutes for each (D-096).
- **Cost per correct finding**: the arm's workload minutes on the set at 1.29 USD an hour, divided by its correct findings (D-096's method: no 1.3 margin, no session overhead). Session overhead (about 15 minutes a launch and 2 minutes an entry, measured) would raise every figure. "none" means no correct finding.
- **Which run counts.** For each document, the latest run. Where a run failed execution integrity and was re-run, the re-run is used and named; where the latest run still failed, it is used, named as failed, and its document is listed below each table. The first runs are shown beside the re-runs.

## Summary (development, exposed)

| Benchmark | Sample | Arm | Precision | Recall | F1 | Correct refusal | Min per document | USD per correct finding |
|---|---|---|---|---|---|---|---|---|
| ContractNLI | 2 agreements, 34 items | B3 benchmark mode | 0 of 5 (0.000) | 0 of 2 | 0.000 | 0 of 11 | 63.5 | none |
| | | B3 as shipped (S-8) | n/a (0 flagged) | 0 of 2 | n/a | 0 of 11 | 63.5 | none |
| | | B1 tuned | 0 of 3 (0.000) | 0 of 2 | 0.000 | 5 of 11 | 5.4 | none |
| SciTab | 3 tables, 14 claims | B3 benchmark mode | 4 of 7 (0.571) | 4 of 7 (0.571) | 0.571 | no gold item | 4.4 | 0.070 |
| | | B3 as shipped (S-8) | n/a (0 flagged) | 0 of 7 | n/a | no gold item | 4.4 | none |
| | | B1 tuned | 3 of 3 (1.000) | 3 of 7 (0.429) | 0.600 | no gold item | 1.8 | 0.039 |
| ContraDoc | 3 documents, 3 items | B3 benchmark mode | n/a (0 flagged) | 0 of 1 | n/a | no class | 5.7 | none |
| | | B3 as shipped (S-8) | n/a (0 flagged) | 0 of 1 | n/a | no class | 5.7 | none |
| | | B1 tuned | 1 of 1 (1.000) | 1 of 1 (1.000) | 1.000 | no class | 0.9 | 0.060 |
| CUAD | 1 contract, 41 categories | B3 benchmark mode | n/a (0 flagged) | 0 of 34 | n/a | no class | 109.2 | none |
| | | B3 as shipped (S-8) | n/a (0 flagged) | 0 of 34 | n/a | no class | 109.2 | none |
| | | B1 tuned | 24 of 27 (0.889) | 24 of 34 (0.706) | 0.787 | no class | 9.7 | 0.0087 |
| FinDVer | 1 filing, 1 item | all arms | not measured | not measured | not measured | no class | B3 97.7, B1 13.4 | none |
| CUAD-claim | | | not run | | | | | |
| Synthetic suite | 20 bundles, 96 items, 48 planted rule items | B3 benchmark mode | 42 of 48 (0.875) | 42 of 48 (0.875) | 0.875 | not measured | 10.6 | 0.109 |
| | | B3 as shipped (S-8) | 40 of 40 (1.000) | 40 of 48 (0.833) | 0.909 | not measured | 10.6 | 0.114 |
| | | B1 tuned | 35 of 66 (0.530) | 35 of 48 (0.729) | 0.614 | not measured | 2.5 | 0.031 |

B3 rows that include a run which still failed execution integrity after its second re-run (L12b): CUAD (its one contract) and the synthetic suite (2 of 20 bundles); each is marked failed with its cause. Five suite bundles that count as passed here passed only because Python wrote EDITOR_CLERK's missing `kind` field, a change removed at the S5 close; they are named in the L12b section, with their re-run L12c. Rows that use an L12b run are on newer code than L12 (sealed at `d6ce19a`: VERIFIER's output allowance 4,096 and the envelope constraint for VERIFIER, PRACTICE_AUDITOR and ARCHIVIST). The suite row covers families 1, 2, 3, 5 and 6; the multi-round family 4 is reported in its section. Each section below gives the counts behind every figure, the runs, the documents left out or failed, and what the figures do not show.

**Correct labels from silence.** The adapters label an item with no kept record as the benchmark's "nothing wrong" class, so B3's correct labels on these benchmarks come from saying nothing, not from detection: on L12 in benchmark mode 27 of them are of that kind (CUAD 7 present, ContractNLI 18 entailment, ContraDoc 2 not contradictory), and as shipped (S-8) the same holds (the parallel track's measurement on the saved runs, 1 November).

## ContractNLI (development, exposed)

Two development agreements, `0d98d9131a5b` (band A) and `01c9504b9c28` (band B), merged parts, 17 hypotheses each: 34 items, gold 2 contradiction, 21 entailment, 11 not mentioned.

| Arm | Run | Integrity | Accuracy (ABSTAIN wrong) | Flagged | Correct flags | Gold flags | Not mentioned, correct of gold | Min per document | Set USD |
|---|---|---|---|---|---|---|---|---|---|
| B3 benchmark mode | L12 re-run, both agreements | both passed | 18 of 34 (0.529) | 5 | 0 | 2 | 0 of 11 | 63.5 | 2.73 |
| B3 as shipped (S-8) | L12 re-run | both passed | 21 of 34 (0.618) | 0 | 0 | 2 | 0 of 11 | 63.5 | 2.73 |
| B1 tuned | L11 | both passed | 18 of 34 (0.529) | 3 | 0 | 2 | 5 of 11 (13 labelled) | 5.4 | 0.23 |
| B3 benchmark mode, first run | L11 | both failed (semantically incomplete) | 8 of 34 (0.235; benchmark mode, while the S5 report's 9 of 34 is the earlier as-shipped reading) | 19 | 1 | 2 | 0 of 11 | 53.0 | 2.28 |
| B3 as shipped (S-8), first run | L11 | both failed | 21 of 34 (0.618) | 0 | 0 | 2 | 0 of 11 | 53.0 | 2.28 |

On the L12 re-run benchmark mode and as-shipped primary give the same labels (25 advice records read, none attributed through the rule map).

Earlier code, three other agreements (`04f58368963d`, `5db65ebc6ba5`, `e42dff968be2`; 51 items, gold 4 contradiction, 27 not mentioned): B3 (L6 for the first two, L4b for the third; all three semantically incomplete, never re-run) benchmark mode 16 of 51, 19 flagged, 2 correct (precision 0.105, recall 0.500), 1.74 USD per correct finding, 54.0 minutes a document; S-8 20 of 51, nothing flagged; not mentioned 0 of 27; benchmark mode and as-shipped primary agree. B1 tuned (L4a, L4b) 28 of 51, 3 flagged, 1 correct (precision 0.333, recall 0.250), not mentioned 15 of 27, 4.2 minutes, 0.27 USD per correct finding; B1 base 31 of 51, 1 flagged, 0 correct, not mentioned 16 of 27, 4.2 minutes.

**What these figures do not show.** Two agreements and two gold contradictions: no difference between arms here means anything. Under S-8 B3 says nothing about any hypothesis, and silence counts as entailment, so S-8's 21 of 34 is what an arm that answers "entailment" to everything scores; it is not a reading. B3 never labels "not mentioned" (it is reached only through a refusal, and none occurred). Every B3 flag comes from a model-written record. The model-text review of L11 sampled 15 of the 526 model texts written across its eight documents (ContractNLI, SciTab and ContraDoc together): The first-run figures are from runs that failed integrity. Reviews of model-written texts, one per launch, each a seeded sample of 15 (docs/loop/stages/S05_REPORT.md: L11 at about line 198, L8, L12 and L12b in the table at about lines 311 to 328): L11 (ContractNLI, SciTab and ContraDoc; SciTab's counted rows for two documents come from it) 1 correct, 5 partly correct, 9 wrong; L8 (the synthetic suite) 4 correct, 9 wrong, 2 empty; L12 (the external benchmarks and the suite; ContractNLI's counted rows) 4 correct, 5 partly correct, 6 wrong; L12b (re-runs) 2 correct, 1 partly correct, 12 wrong. L12c (the integrity re-run of five suite entries, not scored here) has no model-text review.

## SciTab (development, exposed)

Three development tables, `09b24267b75a`, `0e7ff50baa5f`, `26937b278860`: 14 claims, gold 7 supports, 7 refutes, 0 not enough info.

| Arm | Run | Integrity | Macro-F1 | Flagged | Correct flags | Gold flags | Answered | Min per document | Set USD |
|---|---|---|---|---|---|---|---|---|---|
| B3 benchmark mode | L11 for `09b24267b75a` and `26937b278860`, L12 re-run for `0e7ff50baa5f` | all three passed | 0.381 | 7 | 4 | 7 | 14 | 4.4 | 0.28 |
| B3 as shipped (S-8) | same | all three passed | 0.222 | 0 | 0 | 7 | 14 | 4.4 | 0.28 |
| B1 tuned | L11 | all three passed | 0.475 | 3 | 3 | 7 | 13 (1 reply not parsed) | 1.8 | 0.12 |
| B3 benchmark mode, first run | L11 | `0e7ff50baa5f` failed (semantically incomplete) | 0.375 | 9 | 5 | 7 | 14 | 4.3 | 0.27 |

Benchmark mode and as-shipped primary agree on the re-run set (9 advice records, none attributed through the map); on the first run they agreed too.

Earlier code, two other tables (`406b855fc91c`, `f0ed2e1a4be4`; 9 claims, 4 refutes): B3 (L6, both semantically incomplete, never re-run) benchmark mode macro-F1 0.433, 3 flagged, 2 correct (precision 0.667, recall 0.500), 3.5 minutes a document, 0.076 USD per correct finding; S-8 0.238, nothing flagged. B1 tuned and base (L4a) gave the same labels: macro-F1 0.390, 1 flagged, 1 correct, 3.0 minutes, 0.127 USD per correct finding.

**What these figures do not show.** 14 claims on three tables. No gold claim is "not enough info", so the correct refusal rate cannot be computed on this sample. Every B3 refutes label is a model-written record; with them removed (S-8) B3 flags nothing. One table's first run failed integrity and was re-run in L12; the re-run passed.

## ContraDoc (development, exposed)

Three development documents, `01015e47de8a`, `027002a77443` (band A), `06cd776dcc1a` (band B): one item each, gold 1 contradictory.

| Arm | Run | Integrity | Accuracy (ABSTAIN wrong) | Flagged | Correct flags | Gold flags | Min per document | Set USD |
|---|---|---|---|---|---|---|---|---|
| B3 benchmark mode | L12 re-run for `01015e47de8a`, `027002a77443`; L12b (code `d6ce19a`) for `06cd776dcc1a` | all three passed | 2 of 3 | 0 | 0 | 1 | 5.7 | 0.37 |
| B3 as shipped (S-8) | same | all three passed | 2 of 3 | 0 | 0 | 1 | 5.7 | 0.37 |
| B3 benchmark mode, L12 | L12 re-run, all three | `06cd776dcc1a` failed (semantically incomplete) | 2 of 3 | 0 | 0 | 1 | 6.8 | 0.44 |
| B1 tuned | L11 | all passed | 2 of 3 (1 ABSTAIN) | 1 | 1 | 1 | 0.9 | 0.06 |
| B3 benchmark mode, first run | L11 | all three failed | 3 of 3 | 1 | 1 | 1 | 5.4 | 0.35 |
| B3 as shipped (S-8), first run | L11 | all three failed | 2 of 3 | 0 | 0 | 1 | 5.4 | 0.35 |

The first run's one correct flag in benchmark mode came from a model's advice record attributed through the run's rule map, in a run that failed integrity; neither re-run made such a record. Evidence containment (the marked evidence sentence, exact containment, not the official Evidence Hit Rate): 1 of 1 in benchmark mode on the first run and on the earlier-code run below (the advice record that flagged it), 0 of 1 in every other row.

Earlier code, two other documents (`077164cc8a97`, `c7f1d5f10f35`; gold 1 contradictory): B3 (L6, both semantically incomplete, never re-run) benchmark mode 2 of 2, 1 flagged and correct, 0.22 USD per correct finding, 5.2 minutes a document; as shipped (S-8, and the as-shipped primary) 1 of 2 with 1 answered, nothing flagged. B1 tuned (L4a) 1 of 2, nothing flagged; B1 base 0 of 2 (1 ABSTAIN), nothing flagged; 0.7 minutes a document each.

**What these figures do not show.** One gold contradiction in three documents; one document more or less changes every figure. `06cd776dcc1a` failed integrity in L11 and L12 and passed in L12b, on newer code than the other two documents' runs; its label is the same in all three runs.

## CUAD (development, exposed)

One development contract, `527255a5c970` (band B, 2,664 words), 41 categories: gold 34 absent, 7 present. CUAD's official ranked metrics cannot be produced; macro-F1 over present and absent is not comparable with published numbers.

| Arm | Run | Integrity | Macro-F1 | Flagged absent | Correct | Gold absent | Answered | Min per document | Set USD |
|---|---|---|---|---|---|---|---|---|---|
| B3 benchmark mode | L12b (code `d6ce19a`) | failed (semantically incomplete, required contract failure: VERIFIER's list ran to 4,096 tokens, open item 48) | 0.146 | 0 | 0 | 34 | 41 | 109.2 | 2.35 |
| B3 as shipped (S-8) | L12b | failed | 0.146 | 0 | 0 | 34 | 41 | 109.2 | 2.35 |
| B3, L12 | L12 re-run | failed (semantically incomplete) | 0.146 | 0 | 0 | 34 | 41 | 114.3 | 2.46 |
| B1 tuned | L10 | passed | 0.593 | 27 | 24 | 34 | 40 (41 parsed, 1 undecided) | 9.7 | 0.21 |
| B3, first run | L10 | failed (semantically incomplete) | 0.146 | 0 | 0 | 34 | 41 | 98.9 | 2.13 |

**What these figures do not show.** One contract. B3 failed integrity on all three runs (L10, L12, L12b) and is used as failed. B3 recorded no absence on this contract in any run (in L10 all 410 answers on uncomputable plans were refused, D-105). In a 41-rule bundle Python's own blank-field records are set aside in the primary analysis, so CUAD's absent class is reached only through a model-written absence record and S-8 cannot flag on it. CUAD's rule means "in at least one passage", but the labeller turns one unit's absence into the document's absence, so a perfect per-unit judge replayed in Python labels all 41 items absent (7 false positives): B3's 0 of 34 against B1's 24 of 34 does not measure detection, whatever the model does, and changing the labeller is a preregistration matter, not for v1 (the parallel track's measurement on the saved runs, 1 November).

## FinDVer (development, exposed)

One development filing, `e61777d6327c` (band D), one item, run in L4b on earlier code (commit `344522f`). **Not measured**: no arm decided the item. B3 ended semantically incomplete and its item is ABSTAIN (97.7 workload minutes); B1 tuned and B1 base each ran to the 2,048-token output allowance without a label (13.4 minutes each, half of one two-checkpoint entry; D-115). The segmented B3 reading and the revised B1 prompt for FinDVer (D-115) are measured by L13, which is scheduled after v1 and has not run. **FinDVer's held-out (`test`) labels have been public since 14 July 2026** (MIT licence; docs/benchmarks/SELECTION.md, FinDVer, and docs/benchmarks/FINDVER_B1_REVISION.md), so the contamination guard the benchmark's paper relied on is gone; any FinDVer figure, here or later, is read with that in mind.

## CUAD as a claim check (development, exposed)

**Not run.** Its development measurement is part of L13, scheduled after v1 (D-133 item 3).

## Synthetic development suite (development, exposed)

The suite's generators, seeds and answer keys are in this repository, so it is exposed by construction (benchmark/dev_suite/README.md). Families 1, 2, 3, 5 and 6: ten tests and their ten clean twins, 20 bundles, 96 items (48 on tests, 48 on twins), 48 gold flag items, 134 planted flaws. Scored by the synthetic adapter; the planted-flaw counts agree with `tools/score_corpus.py` on every B3 run.

| Arm | Runs | Integrity | Precision | Recall | F1 | Planted flaws located, reason confirmed | Twin items flagged | Records on unplanted units | Min per bundle | Set USD | USD per correct finding |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B3 benchmark mode | L12b (code `d6ce19a`) for the 11 L12 left failed, L12 re-run for 8, L8 for `f3_s3102_bsqv` | 18 of 20 passed (5 of them only through the removed stamp, below); 2 failed (below) | 42 of 48 (0.875) | 42 of 48 (0.875) | 0.875 | 114 of 134 (0.851) | 6 | 45 | 10.6 | 4.57 | 0.109 (0.040 per confirmed flaw) |
| B3 as shipped (S-8) | same | same | 40 of 40 (1.000) | 40 of 48 (0.833) | 0.909 | 114 of 134 (0.851) | 0 | 0 | 10.6 | 4.57 | 0.114 |
| B1 tuned | L8 | 20 of 20 passed | 35 of 66 (0.530) | 35 of 48 (0.729) | 0.614 | 5 of 134 located by a quote; reason not computed | 31 | 11 | 2.5 | 1.09 | 0.031 |
| B3 benchmark mode, L12 | L12 re-run for 19, L8 for `f3_s3102_bsqv` | 9 of 20 passed (2 of them only through the removed stamp); 11 failed (semantically incomplete) | 42 of 47 (0.894) | 42 of 48 (0.875) | 0.884 | 114 of 134 (0.851) | 5 | 51 | 10.9 | 4.67 | 0.111 |
| B3 as shipped (S-8), L12 | same | same | 40 of 40 (1.000) | 40 of 48 (0.833) | 0.909 | 114 of 134 (0.851) | 0 | 0 | 10.9 | 4.67 | 0.117 |
| B3 benchmark mode, first run | L8 | 1 of 20 passed; 10 bundles left out (VERIFIER out of GPU memory, a setup failure) | 17 of 19 (0.895) | 17 of 30 (0.567) | 0.694 | 45 of 79 | 2 | 5 | 7.3 | 3.15 | 0.186 |

Every planted flaw B3 located was located by a Python-written record (114 by Python, 0 by a model), so its location recall is the same in both modes. The repository scorer counts 0 false-positive amendments and 0 distractor hits on every B3 run, tests and twins. As-shipped primary (today's reading, before S-8) is precision 42 of 46 and recall 42 of 48 on this set (42 of 45 on the L12 set). The L12b runs changed no planted flaw found: the located and reason-confirmed counts are those of L12; benchmark mode gained one flagged twin item.

The 11 bundles that failed integrity on L12 were re-run in L12b; 9 passed and 2 still fail, each in the table as failed with its cause (D-138): `f1_s1101_cvjx` (a twin; two PRACTICE_AUDITOR replies ran to their 768-token allowance after the envelope constraint required an explanation, open item 47) and `f3_s3102_vwmj` (a test; VERIFIER's one-item-per-reference list ran to its 4,096-token allowance, open item 48).

**Family 4, multi-round (B3 only).** Four tests and their four twins, 8 bundles, run as declared multi-round cases (L12 re-run of L7's entries; all 8 passed integrity; 0.56 workload minutes a bundle). Scored by `tools/score_corpus.py` on each round's findings (the synthetic adapter does not score this key form). Every round finding is Python's, so both modes give the same figures. No B1 arm exists for these cases.

| Role | Bundles | Planted entries located | Reason confirmed | False positives (irregular round findings on no planted entry) | Distractor hits |
|---|---|---|---|---|---|
| Tests | `f4_s4101_gdks`, `f4_s4102_nqsw`, `f4_s4103_vqjj`, `f4_s4104_rstq` | 79 of 82 | 76 of 82 (0.927) | 0 | 0 |
| Twins | `f4_s4101_bjfg`, `f4_s4102_xwpv`, `f4_s4103_kmvf`, `f4_s4104_xtxd` | 39 of 42 | 36 of 42 (0.857) | 0 | 0 |

**A family 4 twin is not a clean twin in a multi-round run** (open item 26). It repairs only the last round; its earlier rounds are the test's, so their breaches stay in it and its own multi-round key lists them as planted entries (the 42 above). Its 0 false positives therefore say nothing a clean twin's would: no figure here measures false alarms on a document clean in every round, and the repository scorer runs no twin check on a multi-round run.

**Correct refusal rate: not measured.** The suite's refusal entries (`expected_refusals`, the rename probes) are scored on the ordinary two-version review of the family 4 bundles, which are the probe launches L9a and L9b, scheduled after v1; the runs scored here carry no refusal entry.

**What these figures do not show.** The keys are in the repository and the generators were written by the same project, so the suite measures regressions, not recall on unseen material. Two of the twenty B3 runs used are semantically incomplete; counting only semantically complete documents (S-6), B3 locates 103 of 134 planted flaws (34 of 134 on the L12 set, where eleven were incomplete). Eleven of the latest runs are on newer code (L12b) than the other nine. B1 flags 31 items on the clean twins, which no figure above weighs against its recall. The B3 first-run figures leave out ten bundles that failed setup.

## L12b: second re-run of 13 entries (development, exposed)

L12b re-ran the 13 entries that still failed integrity after L12, in two sessions on two instances at once, sealed at `d6ce19a` (VERIFIER's output allowance 4,096 and the envelope constraint for VERIFIER, PRACTICE_AUDITOR and ARCHIVIST), so newer code than L12. 10 of 13 passed (D-138). Of the 37 B3 entries that first failed integrity in L7, L8, L10 and L11, 24 passed in L12, 10 more in L12b and 3 still failed.

**Five of those passes depended on a removed change.** Python wrote EDITOR_CLERK's `kind` field where the model had written none, and a refused EDITOR_CLERK reply fails integrity, so five entries passed only through it: L12 `f3_s3101_htmn` and `f6_s6101_pfqp`, L12b `f1_s1102_mstx`, `f5_s5102_hcvm` and `f5_s5101_bmpd`, all suite bundles. The change was removed at the S5 close (D-143). L12c (code `5c3c129`, EDITOR_CLERK under its own decoding constraint) re-ran the five: four passed and `f1_s1102_mstx` failed (VERIFIER's list ran to 4,096 tokens, open item 48). So 33 of the 37 pass on their own and 4 still fail (D-146). The figures on this page use the L12 and L12b runs of the five; their L12c runs were not scored.

| Entry | L12 | L12b |
|---|---|---|
| ContraDoc `06cd776dcc1a` | failed: semantically incomplete, required contract failure | passed |
| CUAD `527255a5c970` | failed: same | failed: VERIFIER's list ran to 4,096 tokens (open item 48) |
| Suite `f1_s1101_vxnf`, `f2_s2101_sxwc`, `f2_s2102_pbnd`, `f5_s5101_hndk`, `f5_s5102_fpcw`, `f6_s6101_sgkh` | failed: same | passed |
| Suite `f1_s1102_mstx`, `f5_s5101_bmpd`, `f5_s5102_hcvm` | failed: same | passed only through the removed stamp; in L12c `f5_s5101_bmpd` and `f5_s5102_hcvm` passed and `f1_s1102_mstx` failed (open item 48) |
| Suite `f1_s1101_cvjx` | failed: same | failed: two PRACTICE_AUDITOR replies ran to 768 tokens under the envelope constraint (open item 47) |
| Suite `f3_s3102_vwmj` | failed: same | failed: VERIFIER's list ran to 4,096 tokens (open item 48) |

The three that still failed after L12b, and `f1_s1102_mstx` after L12c, are recorded with their causes and are not fixed before v1 (D-S18 item 2a, D-146); each needs a decision measured on development runs.

## Left out, and why

- **SciTab, ContraDoc and ContractNLI B1 base on the current documents**: not run (L11 ran B1 tuned only). B1 base appears only on the earlier-code documents.
- **L2** (ContraDoc 5, SciTab 5) **and L3e** (ContraDoc 1, FinDVer 1): ran before D-068, when every judging answer on these benchmarks was discarded, so B3 equalled the no-finding baseline item for item; not a reading of Shimmer. Their B1 passes (L2: base and tuned, eager and sdpa measurement passes) are attention-kernel measurements; the four documents of theirs that L4a ran again appear above through L4a.
- **L4a B3** on ContractNLI, ContraDoc, SciTab: ran before D-068 and was re-run by L6 on the same documents, so L6 is used. **L4b B3** on ContractNLI `5db65ebc6ba5`: refused 6.8 minutes in (a run failure, INC-019) and re-run by L6, so L6 is used.
- **L5v, L6m, L6s2, R1, R2**: verification and replay launches, not scored runs of a benchmark.
- **The negotiation comparisons and the catalogue test** (L7, L12): regression cases from repository material, not a benchmark or the suite; they are reported in the decisions record (D-106).
- **Family 4 ordinary two-version probes (L9a, L9b), FinDVer segmented, CUAD-claim (L13)**: scheduled after v1, not run.

## How these were measured

- **Instance.** One `gpu_1x_a10` (24 GB) in us-east-1 per launch, at 1.29 USD an hour, read from the provider at each launch. Every run is an exposed run.
- **Launches used** (window, the commit its bundles were built from, billed minutes and cost from the loop's ledger, docs/loop/BUDGET.md):

| Launch | Window | Code at | Billed minutes | Cost (USD) | Used here for |
|---|---|---|---|---|---|
| L4a | from 2026-10-28 23:19 +0300 | `8b48f78` | 121 | 2.60 | B1 tuned and base, earlier-code ContraDoc, SciTab, ContractNLI `04f58368963d` |
| L4b | from 2026-10-29 11:38 +0300 | `344522f` | 204 | 4.39 | B1 on ContractNLI `5db65ebc6ba5` and `e42dff968be2`, B3 on `e42dff968be2`; FinDVer, all arms |
| L6 | 2026-10-29 | `18eee21` | 174 | 3.74 | B3 earlier-code ContraDoc, SciTab, ContractNLI |
| L11 | 2026-10-29 23:18 to 2026-10-30 02:29 UTC | `d50b299` | 191 | 4.11 | B3 first runs and two SciTab tables; B1 tuned on ContractNLI, SciTab, ContraDoc |
| L7 | 2026-10-30 02:58 to 04:01 UTC | `55f1dd1` | 64 | 1.38 | family 4 first runs |
| L10 | 2026-10-30 04:08 to 06:13 UTC | `55f1dd1` | 125 | 2.69 | CUAD B1 tuned, CUAD B3 first run |
| L8 | 2026-10-30 07:41 to 12:12 UTC | `55f1dd1` | 271 | 5.83 | suite B1 tuned, suite B3 first runs, `f3_s3102_bsqv` |
| L12 | 2026-10-30 16:26 to 2026-10-31 02:36 UTC | `2b585af` | 610 | 13.12 | B3 re-runs of 37 entries after the D-S14 fixes (contract-shaped decoding for the producer, D-116) |
| L12b a, L12b b | 2026-10-31, two sessions on two instances at once | `d6ce19a` | 178 and 114 | 3.83 and 2.45 | B3 second re-runs of 13 entries (VERIFIER 4,096, the envelope constraint; D-138) |
| L12c | 2026-10-31 from 19:09 UTC | `5c3c129` | 79 | 1.70 | not scored here: the integrity of the five stamp-only passes (D-146) |

- **Code.** The labels and scores were computed on 31 October 2026 with the adapters' `label --scoring benchmark|as_shipped` and `score` commands and `tools/score_corpus.py` at `6fa01b9` (loop/s05), on the saved run outputs, into a scratch folder. Re-labelled as shipped, the saved label sets of L11 and L10 are reproduced exactly apart from the mode name, and those of L4a, L4b and L6 exactly apart from the mode name and the setup-failure fields the adapters added later (D-084); no label or score changed. Items and scoring bundles are the builds each launch was staged from (`external/s05/L11/build`, `external/s05/L10/build`, the S5 development build). Nothing here is from an S8 run. Those builds and the saved outputs were lost on 16 November 2026 (D-704), so this reproduction can no longer be repeated; the figures stand as recorded.
- **Development detection scoring (after v1, D-S26 item 1).** The adapters now have a third, development-only mode, `label --scoring detection_dev` (decision D-194, written before any score was read with it), which no figure on this page uses yet. It reads the same records as the two modes above, labels an item only from a claim the run kept, and makes an item with no kept claim ABSTAIN, reporting those silence labels apart instead of counting them as detections; it reads CUAD's "in at least one passage" rules per document (absent only when every unit of the document lacks the clause) and reaches ContractNLI's "not mentioned" when every unit of the agreement is recorded as not settling the hypothesis. The saved development runs re-scored with it are the "before" of D-S26 item 2 (next paragraph); the preregistration is unchanged.
- **The "before" under detection scoring (D-S26 item 2, D-196).** The saved L10 (CUAD) and L11 (ContractNLI, ContraDoc, SciTab) development sets re-scored with `detection_dev`, no launch, development and exposed. B3 kept a claim on none of CUAD's 41 items, on 17 of ContractNLI's 34 (16 say contradiction, 1 of them right), on none of ContraDoc's 3 and on 9 of SciTab's 14 (all refutes, 5 right); every other B3 item is silence and scores ABSTAIN. Headlines, as shipped then detection: CUAD macro-F1 0.146 then 0.0; ContractNLI accuracy 0.265 then 0.029; ContraDoc judgement accuracy 0.667 then 0.0; SciTab macro-F1 0.375 then 0.208. B1 tuned is unchanged under this mode (its labels are its own answers): 0.593, 0.529, 0.667, 0.475. So on these four benchmarks almost every correct B3 label so far came from silence; detection by B3 is 1 of 34 on ContractNLI and 5 of 14 on SciTab, and none on CUAD and ContraDoc. Each improvement after v1 is scored on this same material against these figures (D-S26 item 3). L12 to L12c re-ran 7, 2 and 0 of these documents for integrity (B3 only); they are not a second baseline.
- **Models.** The producer is the tuned 7B checkpoint 168 under sdpa attention, prefilled in one shot (D-063), constrained to its contract on L12 and L12b (D-116), with the auditors' envelopes constrained on L12b (D-132); the auditors run on their own local checkpoints. B1 tuned and base load the same 7B model with and without the producer's adapter.
- **Decoding.** Every local model call decodes under the frozen evaluation policy its checkpoint was evaluated with (`config/decoding_policy.json`: greedy, one beam, no sampling), under strict determinism; B1 reads the same policy.
- **Agents withheld or settings changed.** FACT_CHECKER was withheld from every B3 run (`withheld_audit_agents` in the shipped `config/review_scope.json`: on an earlier test every item it returned was wrong; it is switched off, not deleted, because deleting an agent needs the operator's approval under the constitution and cannot be undone without code, while keeping it leaves the LAW-III checks unchanged). INST_FINDER was on: the sealed manifest set `SHIMMER_INST_FINDER=on` for every run (switching it off needs an amendment that is not ratified).
- **Who wrote what.** The public benchmarks' documents and gold labels are their authors' (docs/benchmarks/SELECTION.md). The synthetic suite's generators and keys, the adapters that map a run to a benchmark label and compute its metric, and the repository scorer were written by this project, by the same model family that builds Shimmer.
- **Catches that depended on a directive** (a `[scope:]` or `[requires:]` declaration) were not recorded per catch for these runs.
- **Cost.** Instance cost only; no model API cost was incurred (every model ran on the instance). The per-finding figures leave out the session overhead and the storage share (4.00 USD a month for the asset filesystem).

## Summary to 31 October 2026, as the README gave it

This is the README's former "What has been measured" section, moved here on 19 November 2026 (D-816). Its table copied the [summary above](#summary-development-exposed) and is not repeated; every figure it held (B3 in benchmark mode and as shipped, B1 tuned, minutes per document) is in that table. Every figure here is **development, exposed**.

- **B3** is Shimmer, the whole pipeline in paired review. **B1** is the bare
  model: the main reading model given one fixed prompt per item, with no
  pipeline. "B1 tuned" carries the producer's tuned adapter.
- **Benchmark mode** counts a model judgement that the pipeline shows as advice
  as a finding. **As shipped (S-8)** counts only Python's findings: it is the
  adapters' sensitivity analysis S-8, which scores a run as if every
  model-written record were absent. This scoring rule was chosen after
  development scores had been seen.
- **Every benchmark here is a pilot:** each has fewer than 30 documents and fewer
  than 100 scored decisions.
- **Purpose of these runs:** development measurement and run health, on exposed
  material, with no seal and no manifest.
- **These development runs were not preregistered.** For sealed results, the
  order of preregistration, freeze and sampling will be attested only by the
  project's local records.
- Precision, recall and F1 are those of the benchmark's flag class (for example
  "contradiction" or "refutes"). "n/a" means nothing was flagged.

What these figures do not show:

- **B3's correct labels here come from saying nothing, not from detection.** An
  item with no kept record is labelled the "nothing wrong" class; on L12, 27 of
  B3's correct labels are of that kind (CUAD 7 present, ContractNLI 18
  entailment, ContraDoc 2 not contradictory), in benchmark mode and as shipped.
- **Samples are tiny.** One to three documents per benchmark, one counted run per
  document; runs that failed integrity were re-run up to twice. One item more or
  less changes a figure a great deal.
- **Some B3 runs still failed their execution checks after a second re-run**
  and are counted as failed: the CUAD contract and 2 of the 20 suite bundles.
  Five suite bundles counted as passed did so only through a change removed at
  the S5 close (Python writing a field the model left out); re-run once more
  (L12c, not scored on the page), four passed and one failed. The results page
  names each one with its cause.
- **The synthetic suite is exposed by construction.** Its generators, seeds and
  answer keys are in this repository. It measures regressions, not recall on
  unseen material. On the suite's clean twins, B1 flagged 31 items and B3 in
  benchmark mode flagged 6; B3 in benchmark mode also wrote 45 records on units
  with no planted flaw.
- **The suite's generators were written by the same model family that builds
  Shimmer**, so the tests and the pipeline may share blind spots.
- **Public benchmark documents may have been seen by the models in training.**
- **Every B3 flag on the external benchmarks came from a model-written record.**
  Counting only Python's findings (as shipped, S-8), B3 flagged nothing on them.
  Reviews of model-written texts, a seeded sample of 15 per launch, found:
  L11 (external benchmarks) 1 correct, 5 partly correct, 9 wrong; L8 (the
  synthetic suite) 4 correct, 9 wrong, 2 empty; L12 (benchmarks and suite) 4
  correct, 5 partly correct, 6 wrong; L12b (re-runs) 2 correct, 1 partly
  correct, 12 wrong. L12c (the integrity re-run of five suite entries, not
  scored) has no model-text review. The results page says which rows each
  launch counts for.
- **Not every field a sealed result report needs is here.** The project's
  testing rules list the fields of a result report. The results page gives, for
  these development runs: the purpose, that they are exposed, the dates, the
  code commits, the models, the decoding settings, the machine and its price,
  the cost, who wrote the tests, keys and scorer, the scorer's commit, recall
  and precision, the clean-twin result, the layer that produced the catches
  (Python or a model), the withheld agent (FACT_CHECKER) and the model-text
  review. It does not give a test version or manifest hash (there is none: no
  seal), attribution counts, false positives counted in every deliverable,
  or whether each catch depended on a directive (not recorded for these runs).
  The sealed evaluation, after v1, fills every field.

**Which code was measured.** The runs were built from commits `8b48f78`,
`344522f`, `18eee21`, `d50b299`, `55f1dd1` and `2b585af`; labels and scores were
computed at `6fa01b9`. The second re-run of the entries that still failed (L12b)
was built from `d6ce19a`, which adds a decoding constraint on the output of
VERIFIER, PRACTICE_AUDITOR and ARCHIVIST and a larger VERIFIER output allowance
(4,096 tokens). So the rows that use an L12b run (one ContraDoc document, the
CUAD contract and 11 suite bundles) are on newer code than the rest; the results
page says which run each row uses. Changes made after `d6ce19a` were not
measured (L12c, built from `5c3c129`, re-ran five entries for their integrity
only; their scores were not computed). There is no release-candidate commit.

**Which schedule was measured.** Every B3 run in the table used the
`report_optimized` execution topology on the local backend profile, with paired
review (the sealed runner's arguments, `ARGV` in `tools/ordinary_final_run.py`).
The multi-round family 4 used `reference_serial` (`MULTI_ROUND_ARGV`). The
pipeline's default is `reference_serial`, and the console, the menu launchers and
the command in the [quickstart](USER_GUIDE.md#11-quickstart) do not select `report_optimized`, so an ordinary review started
from them runs a schedule no B3 figure here was measured on. The measured one
needs `--execution-topology report_optimized` and a `--topology-config` lane file
(the runner's is one lane on `cuda:0`, `TOPOLOGY` in the same file).

**History.** The reports under `docs/fix/` from September 2026 describe runs on
tests whose keys the project had read. They are history, with their dates and caveats, and are not evidence of what Shimmer can do now.

## Testing rules

The project's testing rules bind every change, run, score and public statement.
In short:

- Every test used so far is exposed, and can be used only for development and
  regression.
- A sealed test is written, checked, run and scored by separate roles. The builder
  never sees its documents, key or per-item results, and nobody changes it after
  a result has been seen.
- A sealed test is fixed by a hash recorded before the run, with the code commit
  and the scorer.
- Every report states its purpose, whether its test is sealed or exposed, and
  which layer (Python or a model) produced each catch.
- Sealed final-test figures remain the evidence bar: no number is quoted publicly
  as evidence of what Shimmer can do on unseen documents until it holds on at
  least three independently prepared tests, sealed before the run, on one code
  commit, with the spread reported. First results on development and validation
  sets may be quoted publicly when they are labelled as first results and say
  that the final test set has not been run (the operator's decision of
  19 November 2026, D-816).

The preregistration draft is
[docs/benchmarks/PREREGISTRATION.md](benchmarks/PREREGISTRATION.md) and the
benchmark choice is [docs/benchmarks/SELECTION.md](benchmarks/SELECTION.md).

## Reproducing the evaluation

- **Synthetic suite.** Regenerate it from its committed seeds and score a run with
  the repository scorer:

```powershell
py -3.12 benchmark/generators/generate.py suite dev
py -3.12 -X utf8 tools/score_corpus.py --key <answer_key.json> --run <run folder>
```

  [benchmark/dev_suite/README.md](../benchmark/dev_suite/README.md) gives the twin
  options and the multi-round form. The scorer reads a judged absence from
  Python's stamped copy only; the model's raw reply, and any answer Python
  refused, are counted apart and locate nothing.
- **External benchmarks.** The adapters in `benchmark/adapters/` build test
  bundles from a benchmark file, label a run's output and score the labels
  (`build`, `label --scoring benchmark|v2_primary|detection_dev`, `score`; the synthetic suite's
  adapter names its first command `items`). `label` also writes
  the sensitivity analyses, S-8 among them; the "as shipped (S-8)" figures above
  are S-8, not `--scoring v2_primary`, which gives today's reading and can differ
  (on the suite, precision 42 of 46 against S-8's 40 of 40). The bare-model arm
  is `benchmark/baselines/bare_model.py`. No benchmark data is committed;
  `docs/benchmarks/SELECTION.md` names each source, version and licence.
- **Runs.** Full runs go to a rented GPU through the sealed controller
  (`tools/ordinary_final_bound_cloud.py`), which refuses a launch the budget
  cannot carry. The [cloud preparation guide](CLOUD_RUN_PREPARATION.md)
  describes it.
- The run folders behind the results page were kept outside version control and
  were not published. Most of them were lost in a data loss on the build machine
  on 16 November 2026 (D-704): the older development figures can no longer be
  re-scored, and only their recorded results remain. The sealed sets, the gate
  set and the 12 November leakage fingerprint were recovered and checked against
  their recorded digests (D-705).
