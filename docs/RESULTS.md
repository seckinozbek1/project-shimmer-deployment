# Shimmer v1 results: development, exposed

**Every figure on this page is a development figure on exposed material.** The documents were seen while Shimmer was being built, the samples are a handful of documents per benchmark, and one run per document was made. No figure here is a held-out or sealed result, and none supports a claim about accuracy on unseen material. Sealed results, when they exist, are added to this page beside these and replace nothing on it.

Built on 31 October 2026 from runs already done (L4a to L12). No launch was made for this page.

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
| ContraDoc | 3 documents, 3 items | B3 benchmark mode | n/a (0 flagged) | 0 of 1 | n/a | no class | 6.8 | none |
| | | B3 as shipped (S-8) | n/a (0 flagged) | 0 of 1 | n/a | no class | 6.8 | none |
| | | B1 tuned | 1 of 1 (1.000) | 1 of 1 (1.000) | 1.000 | no class | 0.9 | 0.060 |
| CUAD | 1 contract, 41 categories | B3 benchmark mode | n/a (0 flagged) | 0 of 34 | n/a | no class | 114.3 | none |
| | | B3 as shipped (S-8) | n/a (0 flagged) | 0 of 34 | n/a | no class | 114.3 | none |
| | | B1 tuned | 24 of 27 (0.889) | 24 of 34 (0.706) | 0.787 | no class | 9.7 | 0.0087 |
| FinDVer | 1 filing, 1 item | all arms | not measured | not measured | not measured | no class | B3 97.7, B1 13.4 | none |
| CUAD-claim | | | not run | | | | | |
| Synthetic suite | 20 bundles, 96 items, 48 planted rule items | B3 benchmark mode | 42 of 47 (0.894) | 42 of 48 (0.875) | 0.884 | not measured | 10.9 | 0.111 |
| | | B3 as shipped (S-8) | 40 of 40 (1.000) | 40 of 48 (0.833) | 0.909 | not measured | 10.9 | 0.117 |
| | | B1 tuned | 35 of 66 (0.530) | 35 of 48 (0.729) | 0.614 | not measured | 2.5 | 0.031 |

B3 rows that include a run which failed execution integrity: ContraDoc (1 of 3 documents), CUAD (its one contract) and the synthetic suite (11 of 20 bundles); their second re-run is L12b, below. The suite row covers families 1, 2, 3, 5 and 6; the multi-round family 4 is reported in its section. Each section below gives the counts behind every figure, the runs, the documents left out or failed, and what the figures do not show.

## ContractNLI (development, exposed)

Two development agreements, `0d98d9131a5b` (band A) and `01c9504b9c28` (band B), merged parts, 17 hypotheses each: 34 items, gold 2 contradiction, 21 entailment, 11 not mentioned.

| Arm | Run | Integrity | Accuracy (ABSTAIN wrong) | Flagged | Correct flags | Gold flags | Not mentioned, correct of gold | Min per document | Set USD |
|---|---|---|---|---|---|---|---|---|---|
| B3 benchmark mode | L12 re-run, both agreements | both passed | 18 of 34 (0.529) | 5 | 0 | 2 | 0 of 11 | 63.5 | 2.73 |
| B3 as shipped (S-8) | L12 re-run | both passed | 21 of 34 (0.618) | 0 | 0 | 2 | 0 of 11 | 63.5 | 2.73 |
| B1 tuned | L11 | both passed | 18 of 34 (0.529) | 3 | 0 | 2 | 5 of 11 (13 labelled) | 5.4 | 0.23 |
| B3 benchmark mode, first run | L11 | both failed (semantically incomplete) | 8 of 34 (0.235) | 19 | 1 | 2 | 0 of 11 | 53.0 | 2.28 |
| B3 as shipped (S-8), first run | L11 | both failed | 21 of 34 (0.618) | 0 | 0 | 2 | 0 of 11 | 53.0 | 2.28 |

On the L12 re-run benchmark mode and as-shipped primary give the same labels (25 advice records read, none attributed through the rule map).

Earlier code, three other agreements (`04f58368963d`, `5db65ebc6ba5`, `e42dff968be2`; 51 items, gold 4 contradiction, 27 not mentioned): B3 (L6 for the first two, L4b for the third; all three semantically incomplete, never re-run) benchmark mode 16 of 51, 19 flagged, 2 correct (precision 0.105, recall 0.500), 1.74 USD per correct finding, 54.0 minutes a document; S-8 20 of 51, nothing flagged; not mentioned 0 of 27; benchmark mode and as-shipped primary agree. B1 tuned (L4a, L4b) 28 of 51, 3 flagged, 1 correct (precision 0.333, recall 0.250), not mentioned 15 of 27, 4.2 minutes, 0.27 USD per correct finding; B1 base 31 of 51, 1 flagged, 0 correct, not mentioned 16 of 27, 4.2 minutes.

**What these figures do not show.** Two agreements and two gold contradictions: no difference between arms here means anything. Under S-8 B3 says nothing about any hypothesis, and silence counts as entailment, so S-8's 21 of 34 is what an arm that answers "entailment" to everything scores; it is not a reading. B3 never labels "not mentioned" (it is reached only through a refusal, and none occurred). Every B3 flag comes from a model-written record, and the model-text review of L11 found 9 of 15 sampled model texts wrong and 5 partly correct. The first-run figures are from runs that failed integrity.

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
| B3 benchmark mode | L12 re-run, all three | 2 passed; `06cd776dcc1a` failed (semantically incomplete) | 2 of 3 | 0 | 0 | 1 | 6.8 | 0.44 |
| B3 as shipped (S-8) | L12 re-run | as above | 2 of 3 | 0 | 0 | 1 | 6.8 | 0.44 |
| B1 tuned | L11 | all passed | 2 of 3 (1 ABSTAIN) | 1 | 1 | 1 | 0.9 | 0.06 |
| B3 benchmark mode, first run | L11 | all three failed | 3 of 3 | 1 | 1 | 1 | 5.4 | 0.35 |
| B3 as shipped (S-8), first run | L11 | all three failed | 2 of 3 | 0 | 0 | 1 | 5.4 | 0.35 |

The first run's one correct flag in benchmark mode came from a model's advice record attributed through the run's rule map, in a run that failed integrity; the re-run made no such record. Evidence containment (the marked evidence sentence, exact containment, not the official Evidence Hit Rate): 1 of 1 in benchmark mode on the first run and on the earlier-code run below (the advice record that flagged it), 0 of 1 in every other row.

Earlier code, two other documents (`077164cc8a97`, `c7f1d5f10f35`; gold 1 contradictory): B3 (L6, both semantically incomplete, never re-run) benchmark mode 2 of 2, 1 flagged and correct, 0.22 USD per correct finding, 5.2 minutes a document; as shipped (S-8, and the as-shipped primary) 1 of 2 with 1 answered, nothing flagged. B1 tuned (L4a) 1 of 2, nothing flagged; B1 base 0 of 2 (1 ABSTAIN), nothing flagged; 0.7 minutes a document each.

**What these figures do not show.** One gold contradiction in three documents; one document more or less changes every figure. `06cd776dcc1a` failed integrity on both runs (L11 and L12) and is in the table as failed; its second re-run is L12b (below).

## CUAD (development, exposed)

One development contract, `527255a5c970` (band B, 2,664 words), 41 categories: gold 34 absent, 7 present. CUAD's official ranked metrics cannot be produced; macro-F1 over present and absent is not comparable with published numbers.

| Arm | Run | Integrity | Macro-F1 | Flagged absent | Correct | Gold absent | Answered | Min per document | Set USD |
|---|---|---|---|---|---|---|---|---|---|
| B3 benchmark mode | L12 re-run | failed (semantically incomplete) | 0.146 | 0 | 0 | 34 | 41 | 114.3 | 2.46 |
| B3 as shipped (S-8) | L12 re-run | failed | 0.146 | 0 | 0 | 34 | 41 | 114.3 | 2.46 |
| B1 tuned | L10 | passed | 0.593 | 27 | 24 | 34 | 40 | 9.7 | 0.21 |
| B3, first run | L10 | failed (semantically incomplete) | 0.146 | 0 | 0 | 34 | 41 | 98.9 | 2.13 |

**What these figures do not show.** One contract. B3 failed integrity on both runs and is used as failed; its second re-run is L12b. B3 recorded no absence on this contract in either run (in L10 all 410 answers on uncomputable plans were refused, D-105). In a 41-rule bundle Python's own blank-field records are set aside in the primary analysis, so CUAD's absent class is reached only through a model-written absence record and S-8 cannot flag on it.

## FinDVer (development, exposed)

One development filing, `e61777d6327c` (band D), one item, run in L4b on earlier code (commit `344522f`). **Not measured**: no arm decided the item. B3 ended semantically incomplete and its item is ABSTAIN (97.7 workload minutes); B1 tuned and B1 base each ran to the 2,048-token output allowance without a label (13.4 minutes each, half of one two-checkpoint entry; D-115). The segmented B3 reading and the revised B1 prompt for FinDVer (D-115) are measured by L13, which is scheduled after v1 and has not run.

## CUAD as a claim check

**Not run.** Its development measurement is part of L13, scheduled after v1 (D-133 item 3).

## Synthetic development suite (development, exposed)

The suite's generators, seeds and answer keys are in this repository, so it is exposed by construction (benchmark/dev_suite/README.md). Families 1, 2, 3, 5 and 6: ten tests and their ten clean twins, 20 bundles, 96 items (48 on tests, 48 on twins), 48 gold flag items, 134 planted flaws. Scored by the synthetic adapter; the planted-flaw counts agree with `tools/score_corpus.py` on every B3 run.

| Arm | Runs | Integrity | Precision | Recall | F1 | Planted flaws located, reason confirmed | Twin items flagged | Records on unplanted units | Min per bundle | Set USD | USD per correct finding |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B3 benchmark mode | L12 re-run for 19, L8 for `f3_s3102_bsqv` | 9 of 20 passed; 11 failed (semantically incomplete) | 42 of 47 (0.894) | 42 of 48 (0.875) | 0.884 | 114 of 134 (0.851) | 5 | 51 | 10.9 | 4.67 | 0.111 (0.041 per confirmed flaw) |
| B3 as shipped (S-8) | same | same | 40 of 40 (1.000) | 40 of 48 (0.833) | 0.909 | 114 of 134 (0.851) | 0 | 0 | 10.9 | 4.67 | 0.117 |
| B1 tuned | L8 | 20 of 20 passed | 35 of 66 (0.530) | 35 of 48 (0.729) | 0.614 | 5 of 134 located by a quote; reason not computed | 31 | 11 | 2.5 | 1.09 | 0.031 |
| B3 benchmark mode, first run | L8 | 1 of 20 passed; 10 bundles left out (VERIFIER out of GPU memory, a setup failure) | 17 of 19 (0.895) | 17 of 30 (0.567) | 0.694 | 45 of 79 | 2 | 5 | 7.3 | 3.15 | 0.186 |

Every planted flaw B3 located was located by a Python-written record (114 by Python, 0 by a model), so its location recall is the same in both modes. The repository scorer counts 0 false-positive amendments and 0 distractor hits on every B3 run, tests and twins. As-shipped primary (today's reading, before S-8) is precision 42 of 45 and recall 42 of 48 on this set.

The 11 bundles that failed integrity on the re-run: `f1_s1101_cvjx`, `f1_s1101_vxnf`, `f1_s1102_mstx`, `f2_s2101_sxwc`, `f2_s2102_pbnd`, `f3_s3102_vwmj`, `f5_s5101_bmpd`, `f5_s5101_hndk`, `f5_s5102_fpcw`, `f5_s5102_hcvm`, `f6_s6101_sgkh`. They are in the table as failed; their second re-run is L12b.

**Family 4, multi-round (B3 only).** Four tests and their twins, 8 bundles, run as declared multi-round cases (L12 re-run of L7's entries; all 8 passed integrity; 0.56 workload minutes a bundle). Scored by `tools/score_corpus.py` on each round's findings (the synthetic adapter does not score this key form): 118 of 124 planted entries located, 112 of 124 with the reason confirmed (0.903), 0 false positives, 0 distractor hits. Every round finding is Python's, so both modes give the same figure. No B1 arm exists for these cases.

**Correct refusal rate: not measured.** The suite's refusal entries (`expected_refusals`, the rename probes) are scored on the ordinary two-version review of the family 4 bundles, which are the probe launches L9a and L9b, scheduled after v1; the runs scored here carry no refusal entry.

**What these figures do not show.** The keys are in the repository and the generators were written by the same project, so the suite measures regressions, not recall on unseen material. Eleven of the twenty B3 runs used are semantically incomplete; counting only semantically complete documents (S-6), B3 locates 34 of 134 planted flaws. B1 flags 31 items on the clean twins, which no figure above weighs against its recall. The B3 first-run figures leave out ten bundles that failed setup.

## L12b: second re-run of 13 entries (placeholder)

> **LEAD TO FILL.** L12b re-runs the 13 entries that still failed integrity after L12: ContraDoc `06cd776dcc1a`, CUAD `527255a5c970`, and the 11 suite bundles listed above. When it has been read, give each entry's latest integrity status here, and replace the B3 rows of the ContraDoc, CUAD and synthetic suite tables with figures from L12b where an entry passed (scripts and method as for L12, report below). Until then the tables above use the L12 runs, failed as stated.

| Entry | L12 | L12b |
|---|---|---|
| ContraDoc `06cd776dcc1a` | failed: semantically incomplete, required contract failure | (lead) |
| CUAD `527255a5c970` | failed: same | (lead) |
| 11 suite bundles | failed: same | (lead) |

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
| L7 | 2026-10-30 02:57 to 04:01 UTC | `55f1dd1` | 64 | 1.38 | family 4 first runs |
| L10 | 2026-10-30 04:08 to 06:13 UTC | `55f1dd1` | 125 | 2.69 | CUAD B1 tuned, CUAD B3 first run |
| L8 | 2026-10-30 07:41 to 12:12 UTC | `55f1dd1` | 271 | 5.83 | suite B1 tuned, suite B3 first runs, `f3_s3102_bsqv` |
| L12 | 2026-10-30 16:26 to 2026-10-31 02:36 UTC | `2b585af` | 610 | 13.12 | B3 re-runs of 37 entries after the D-S14 fixes (contract-shaped decoding for the producer, D-116) |

- **Code.** The labels and scores were computed on 31 October 2026 with the adapters' `label --scoring benchmark|as_shipped` and `score` commands and `tools/score_corpus.py` at `6fa01b9` (loop/s05), on the saved run outputs, into a scratch folder. Re-labelled as shipped, the saved label sets of L11 and L10 are reproduced exactly apart from the mode name, and those of L4a, L4b and L6 exactly apart from the mode name and the setup-failure fields the adapters added later (D-084); no label or score changed. Items and scoring bundles are the builds each launch was staged from (`external/s05/L11/build`, `external/s05/L10/build`, the S5 development build). Nothing here is from an S8 run.
- **Models.** The producer is the tuned 7B checkpoint 168 under sdpa attention, prefilled in one shot (D-063), constrained to its contract on L12 (D-116); the auditors run on their own local checkpoints. B1 tuned and base load the same 7B model with and without the producer's adapter.
- **Cost.** Instance cost only; no model API cost was incurred (every model ran on the instance). The per-finding figures leave out the session overhead and the storage share (4.00 USD a month for the asset filesystem).
