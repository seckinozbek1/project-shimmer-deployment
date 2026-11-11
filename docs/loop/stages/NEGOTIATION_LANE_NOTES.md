# Negotiation measurement: where things stand (lane/cases-3, 9 November 2026)

Merged into the loop branch as D-462, at lane tip `49b061c7`, after nego-plan-check's PASS. The plan
is `docs/loop/stages/NEGOTIATION_MEASUREMENT_PLAN.md`; the tools are held by gate check 347 (50 proofs,
fixtures only, no model, no held-out case).

## Done and merged

- The plan, the role B request, the author brief and the round-3 rubric.
- `tools/score_negotiation.py`: labels, figures, intervals and tests, openings, claims, refusals, and
  failed entries. A failed entry of either kind scores `no_answer` on every row of its case. Records
  are read only at the entry root. A CUDA out-of-memory error is the system's own failure.
- `tools/freeze_negotiation_set.py`: declarations, minimums, pooled kappa, leakage (exact, one 5-gram
  index, bge-m3 cosine in float32 token-budget batches, same source), a token forecast, and the GPU
  watched before and after every chunk.
- `tools/negotiation_power.py` and its committed records; C1 is expected to be indicator-only.
- `benchmark/baselines/negotiation_b1.py`: both B1 forms, carried by the replay pass.

## Waits on role B (the lead starts role B and the author agent; this lane does not)

1. The author agent writes the held-out cases in role B's own folder, by the author brief.
2. Role B's labellers write the keys: labellers 1 and 2, the revision round if the pooled kappa is
   below 0.60, then labeller 3. A declarer fills the declarations.
3. Role B adds to `NEGOTIATION_CORPORA.txt` the external development sets the loop has read.
4. Role B runs the freeze, `--device cuda`, when the GPU reads idle (D-399). It runs one job at a
   time, after causal-probe's digest and choice-build's fingerprints. The forecast is about 480 minutes
   on the CPU. It writes FREEZE.json; a case over any leakage threshold is replaced and checked again.
5. Role B moves the frozen cases in.

## Then, in order

- `tools/negotiation_power.py --freeze FREEZE.json --only C1`, 1,000 sets, committed as
  `NEGOTIATION_POWER_C1.json`.
- The configuration record, then the B1 and cloud prompts files built from the frozen set. Before the
  "evet" request, the cost is recomputed from the frozen counts (plan section 5).
- Step 5 (sealing the cases' bundles) waits on the frozen configuration. No Lambda launch until the
  D-S105 savings are proven and the image is tested.
- Seal, then the opening line, then launch (D-395 N8). The scorer reads only behind the committed
  opening.

## Known limits (stated in the plan)

- The controller writing FINAL_STATUS.json and its three failure records at the entry root, for every
  batch entry, is the bound controller's code. judge-product answered that it is not guaranteed: the
  failure records go only to the session folder, and FINAL_STATUS.json exists only where the analyser
  ran. It is open item 97 (on lane/tiers). Until a per-entry `entry_outcome.json` exists, a lost entry
  refuses the scoring, the safe side, and is a ground for opening 2.
- GPU watch: one reading a chunk, so a brief job by another process between two readings is missed.
  Under Windows' display driver there is no per-process memory figure, so other processes' memory is
  inferred, with a first-chunk window.
