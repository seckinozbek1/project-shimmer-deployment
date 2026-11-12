# Lessons from every attempt (D-S71 item 1)

One entry per attempt of any optimisation: what was tried, the measured result on read development items, why it went that way (traced in the saved records, not guessed), and what the next attempt changes because of it. The next attempt's recipe cites the lessons it acts on. The fresh set and sealed material never feed a lesson. Written by the lead from the lanes' reports; newest last.

## L-1. The judge, J1: a long agent prompt against a narrow question (D-261 to D-263)

- **Tried.** Phi-4 as the judging model on ContraDoc, through the B1 prompt and a narrow judge prompt on Python-chosen passage pairs.
- **Result.** Neither cleared the bar (`drop`, 7.50 USD).
- **Why.** No relation of the Finding record could carry a contradiction in words, so a correct answer had nowhere to go (D-263). On the measured prompts, the long prompt broke where the short, narrow question on Python-selected evidence did not.
- **Next changed.** The relation `contradiction` (INFRA-046, INFRA-047). The judge asked one narrow question, decided from its answer probabilities (CHOICE-A, D-S41).

## L-2. The judge, C base: the untrained choice form (D-291)

- **Tried.** Phi-4 base, choice form, one forward pass, on ContraDoc and SciTab half A.
- **Result.** ContraDoc .70 against B1 .60; SciTab .738 against B1 .918.
- **Why.** The pair proposer reaches ContraDoc's contradictions, but SciTab's claims need cells the base did not read well.
- **Next changed.** Training (T) on pair and claim rows in the run-time form.

## L-3. The judge, T attempt 1: trained on two mixes (D-292 to D-294)

- **Tried.** LoRA on Phi-4, `dev_mix` and `permissive_mix`, checkpoints at .5 and 1.
- **Result.** Half A permissive ContraDoc .733, SciTab .837. Half B, read once: `drop` for every candidate; by the sign test, training did not help.
- **Why.** The held-out accuracy was flat after the midpoint. The pair rows were not in the form the run-time question takes (other sources, other pair shapes), so training taught a different question.
- **Next changed (attempt 2).** Pair rows built from the run-time proposer's own pairs on web documents, with figure-changed twins. Claims in the run-time form with its tools block. The benchmarks' source families under a quarter (2e: 21.1 percent). No pair Unclear.

## L-4. The judge, the D-S45 either attempt (D-297, D-316)

- **Tried.** "Either base + reason", chosen on half A among several combinations.
- **Result.** In sample: 6 wins and 2 losses of 30.
- **Why it misleads.** The effect was chosen on the data that measured it. Half B's out-of-sample difference was about one document of 30, at which the power on 100 documents is .40 to .47, not .80.
- **Next changed.** A power figure is stated from an out-of-sample effect beside any in-sample one. A failure at that size is reported as "not shown at this size".

## L-5. The position comparison: three checker rounds (D-317, D-319)

- **Tried.** Reading a figure's measure from a window of words around it: the longest repeated phrase, then words after it, brackets, and a clause before it.
- **Result.** Every round's attack found quote shapes where two different measures read as one, which gave confident wrong records. The strict rule then computed no movement on the worked case.
- **Why.** Any word outside the window can change the measure, and telling a unit word from prose is a decision about meaning, which code may not make (WORDS-A).
- **Next changed.** A gap only between quotes identical except for the figure (D-319), and the unit declared per issue in the case manifest (D-S70 item 4).

## L-6. The worked cases on the product as shipped (D-332)

- **Tried.** Both cases run as multi-round workloads and as ordinary two-version reviews, with the shipped models and settings.
- **Result.** Both multi-round runs passed in under two minutes; both reviews were semantically incomplete.
- **Why (from the saved records).** In the host-agreement review, VERIFIER wrote a 13,263-byte reply that never closed its canonical envelope. In the draft-resolution review, one compact PROCESSOR partition returned the refusal object.
- **Next changed.** The auditor lane's VERIFIER work and the producer lane's PROCESSOR candidate take these two calls as read development evidence. Step 5 reruns the cases only after the parts improve.

## L-7. The ontology proposer, attempt 1 (outside the success rule, D-330)

- **Tried.** A two-round message-passing GNN over a run-scoped unit graph, against the shipped passage ranker, on the repository's generator tests (four families, 40 trained, 40 measured).
- **Result.** Gold unit pairs in the first 10: ranker 2 of 316, gnn_s 188, gnn_e 156; gnn_s won 39 of 40 documents. A measurement, not a success.
- **Why.** The generator's links are structural (the unit before, a row keyed by a heading, a shared label far away); ranking by meaning almost never reaches them, and gnn_s's hand-built features write those structures down. The gain may be the features, not the learning, and the tests are the generator's own families on both sides.
- **Next changed.** A structural control with no training that the GNN must also beat by the margin; the earlier best re-measured on each new block; a held-out family rotation as the next candidate.

## L-8. Launching three trainings at once: the uploads and the copy probe (D-352 to D-356)

- **Tried.** Three trainings (judge 2e, producer bundle 3, auditor) launched within ten minutes of each other, each uploading the same 22.25 GB archive from this machine. The judge was then relaunched with the asset copy declared, and launched a third time uploading alone.
- **Result.** In parallel each upload ran at about 2 MB/s (PROGRESS-A readings at 06:28, 07:13, 07:59 and 08:45). The judge's passed the controller's fixed 10,800 s scp limit and stopped with no training, about 4.02 USD. The relaunch stopped at the copy probe's fixed 300 s deadline, with no state recorded, about 0.28 USD. Uploading alone, the third launch ran at 5.8 MB/s and finished inside the limit.
- **Why.** One uplink is shared across simultaneous scp streams, while the forecasts assumed one upload measured alone. The probe hashes the whole copy on the instance, and earlier probes took 3.1 to 4.1 minutes, close to the 300 s deadline. Both limits are bound constants.
- **Next changed.** Bundles launched together from here either declare the copy (when the region is us-east-1 and the probe has margin) or are staggered by more than one upload. The probe's deadline and the scp limit are recorded as open items for after v1. The bound wrapper's fastest-order fix (lane/wrapper-rule) waits for the trainings to end.

## L-9. The ontology proposer, attempt 2 (the first opening under D-330)

- **Tried.** Attempt 1's recipe unchanged, trained on 80 generator documents (blocks 910 and 920). It was measured once on held-out block 930 (40 documents, 313 gold pairs) beside the shipped embedding ranker, a structural control with no training (the same pair features in a fixed order) and attempt 1's model.
- **Result.** Pass at alpha .025. Gold pairs in the first 10: ranker 3, control 13, the candidate 171, attempt 1's model 187. In the first 40: 17, 89, 302 and 305. 39 document wins and 0 losses against the ranker at K 10. Not real progress over attempt 1's model (-1.5 points at K 10).
- **Why, from the saved records.** The control reaches far less than the GNN, so the gain is not the hand-built features read in a fixed order; the GNN learns how to weigh them with the graph. Doubling the training documents did not help on this block.
- **Next changed.** No further attempt is needed for this part's stopping rule. More generator data is not the lever; documents people wrote, with these kinds of links, would be. Adoption still needs the routing DELTA ratified and D-S61 item 4(b)'s system comparison. These tests are synthetic only.

## L-10. The auditor's rule check, training attempt 1 (AUD_TRAIN5, D-366)

- **Tried.** LoRA on Phi-3.5-mini, two mixes (dev_mix, permissive_mix), checkpoints at half and full, decided by the argmax of the answer probabilities, measured on half A of the 789 development questions against the untrained base.
- **Result.** Macro-F1: base .541; the best arm (permissive_mix at half) .588. The margin is .047 against the required .05: fail, but progress (D-S72's +.02 minimum met). Half B stays closed.
- **Why, from the saved records.** The loss is the calibration of the decision, not the data size, the mix or the base's ceiling. Training doubled the not-met class (F1 .42 to .62-.65; precision .41 to .70-.76), but sank met answers into Unclear (met recall .37 to .26-.32; 273-285 Unclear answers against 158 gold). Half against full is flat, and the two mixes differ by .02 or less. The training rows are balanced and short, while the measured parts are long, with another prior, so the probabilities rank better but the argmax keeps the training prior.
- **Next changed (attempt 2).** The decision rule only: per-label log-probability offsets, fitted per arm on half A (the untrained form included) and frozen before half B. No new training. Exploratory 2-fold cross-validation on A puts the best arm's margin at .115. Half B, read once, carries the claim.

## L-11. The judge, attempt 2e (T2E_TRAIN_F, D-370)

- **Tried.** T's unchanged recipe on run-time-form pair rows and tools-form claim rows (2e), 710 updates on Phi-4, read in-sample on half A against the session's own base.
- **Result.** trained_full passes: SciTab 2-class macro-F1 .703 to .797 (+.095), ContraDoc net held at 8 (12 right and 4 false, against 9 and 1). trained_half fails. It is still below B1 with reasoning on SciTab (.838, 2-class macro-F1; D-380). The fitted-temperature calibration qualified no threshold (D-371); corrected: the calibration failed on a code defect, not on the judge (D-373) (corrected D-382).
- **Why, from the saved records.** The claim rows in the tools form moved SciTab. ContraDoc is capped by which pairs the proposer reaches, and more right flags came with more false ones, so net held. Held-out accuracy was still rising at 710 updates, so the run was not trained to saturation.
- **Next changed.** Attempt 2f: a calibration procedure written before it runs, covering both families, tested on the D-S92 gate set. If more training is needed: more updates and harder same-document No pairs, from trained_full.

## L-12. The producer, attempt 1 (P3_TRAIN_B, D-370)

- **Tried.** Checkpoint 168's recipe on 676 rows (v3 plus 340 on public carriers), 2 passes, the full checkpoint tested.
- **Result.** Partitions_tune 20 to 0, fresh_tune 23 to 0, no role worse; FAIL on condition (a) as written.
- **Why, from the saved records.** (a) tested "the same invalid rows as 168" on a wrong premise: of 168's 9 invalid DEV rows, 5 are correct refusals and 4 wrongful refusals. The candidate kept the 5 and answered the 4, 3 exactly right. Training loss near zero (last-32 mean .0018) and exact DEV rows trading 11 to 9 point to overfitting the constructed form; the fresh gain is partly in the same constructed family.
- **Next changed.** (a) restated against the targets from attempt 2 on, never re-scoring attempt 1; the half checkpoint (about one pass) tested; archivist's 8 to 3 drift watched, not significant at this size.

## L-13. The evening of 11 November: shared GPU, a crash at check 310, estimates that slipped (D-495)

- **What happened.** Two full gate runs (the export and its baseline) and the leakage fingerprint's embedding ran together on the 8 GB card (7,987 of 8,192 MiB used). The gates crawled from check 241 on. The export run then crashed at check 310 (Tcl_AsyncDelete), as two runs had done that afternoon. The 22:10 and 22:30 estimates passed unmeasured, and Seckin had to ask at 22:35.
- **Why.** No queue for the GPU. A known crash was treated by rerunning. A crashed gate restarted from check 0. Nothing watched for a stalled job. Estimates were guesses, not rates. Two gate runs per push where one would do.
- **Next changed.** D-495's six rules, standing orders 62 to 67.

## L-14. Estimate from the work left, not from a rate (addition to D-495 rule 5; Seckin's assistant, 12:30, 12 November)

- **What happened.** The fingerprint embedding's end time slipped four times: 07:00, 11:30, 12:00, then 12:40 to 12:55. Each estimate divided the rows left by an average rate measured while the long records were still ahead, and the items were processed in length order.
- **Rule from now on.** For any job whose items vary in size, the estimate is the work actually left divided by a rate measured on items of similar size. For the embedding, that means the characters still to embed (each capped at the model's 8,192-token window), split into length classes, each class over its own measured characters per second. The estimate is a range, and it states what it rests on: which counts, which rates, measured when.
- **Applied at 12:31.**
  - Left: 5,531 rows, 22.9 M effective characters.
  - Up to 6,000 characters: 4,936 rows, 14.1 M characters, at 8 to 14 thousand characters a second (measured on the current 1,500 to 2,000-character rows, about 8 rows a second): 17 to 29 minutes.
  - Over 6,000: 595 rows, 8.8 M characters, at 5.5 to 6.5 thousand characters a second (measured on the local tail of full-length records, 5 to 6 s each): 23 to 27 minutes.
  - Then the final write, about 15 minutes.
  - End: about 13:20 to 13:45.
