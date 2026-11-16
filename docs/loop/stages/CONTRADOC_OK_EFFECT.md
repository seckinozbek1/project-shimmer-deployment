# The effect of the "does not contradict" fix on ContraDoc (D-652 item 1, D-657, D-669; lane contradoc-d652, 16 November 2026)

Read from saved replies and artifacts only: no model, no provider, no answer key opened by this lane, 0 USD.
The fix is INFRA-055 (ab98eed9): a well-formed `record_verdict: ok` contradiction answer is kept as the model's
record instead of being refused as "contradiction not marked irregular", together with the agent sentence that
now tells the model to give that answer.

## 1. What the saved material holds

The 16 November data loss (D-696, D-704, D-705) removed G1 and the old s05 run folders, including the 12 half A
pairing maps the 15 November 16:54 trace read, and the quick-read outputs of D-634 (READ_20261115). What remains:

| Source | Runs | Distinct documents | Judging calls | Contradiction answers | ok answers |
|---|---|---|---|---|---|
| external/s05/REFPAIR (B3, A10 and A100, sealed before INFRA-055) | 4 | 2 | 4 | 0 | 0 |
| external/s05_dryrun/work2 (B2 maps, no replies) | 5 | 5 | 0 | 0 | 0 |
| Recorded only: the 16:54 trace of 12 half A maps (INFRA-055_DRAFT.md, ab98eed9) | 12 | 8 of half A's 30 | not recorded | 22 judged answers | 0 |
| Recorded only: K0's quick read (D-634, 40 documents, aggregates) | 7 sessions | 40 | not recorded | not recorded | not recorded |

Read by `tools/contradoc_ok_effect.py` (check 485) for the two surviving sources; the other two rows are the
recorded counts, not re-read.

## 2. Counts and figures (95 percent exact intervals)

1. **The code change alone moves no saved label.** Every saved run was made under the old instruction, which told
   the agents never to write an ok contradiction. ok answers: 0 of 22 recorded judged answers on half A
   (interval [0.0, 15.4] percent); 0 of 4 surviving judging calls ([0.0, 60.2] percent), which held no
   contradiction answer at all. Documents that INFRA-055 could move: 0 of 8 recorded half A documents
   ([0.0, 36.9] percent); 0 of 4 surviving runs ([0.0, 60.2] percent) under both readings.
2. **The frozen gate reading (v2_primary) on K0's quick set.** K0 scored 55.0 [40.0, 70.0] on 40 documents: 22
   right (7 located contradictions, 15 clean documents read clean), 11 contradictions lost as silence, 7 false
   positives. 22 + 11 + 7 = 40, so K0 had **0 ABSTAIN labels**. Under v2_primary a document can move only out of
   ABSTAIN (a refused ok answer), so the code change can move **0 of 40, change 0.0 points** on K0's figure, by
   construction and not by estimate.
3. **What only a run can show: the instruction's effect.** The new sentence lets the model answer "does not
   contradict" where it used to write a false irregular record or nothing. On K0's labels that can turn at most
   the 7 false positives right and at most the 7 located contradictions wrong: a bound of [-17.5, +17.5] points
   on 40 documents under v2_primary. Under detection_dev's `each` reading a ContraDoc document was never CLEAR
   from a model's answer before INFRA-055 (CLEAR needs every unit to hold); now it can be, but only on documents
   where every unit got a model call. K0's loss table says 11 of 18 contradictions were lost because Python found
   nothing and asked no model, so units without a call can never hold and those documents stay ABSTAIN under
   `each`. The size of the `each` gain is not knowable from the saved material.

## 3. The run that would answer it

- **Items.** G1's ContraDoc half A, 30 documents: the ids survive in git (`benchmark/baselines/g1_bar_items.json`,
  60 ContraDoc ids; half A by `choice_read.halves`, D-296, D-649). The file's SHA-256 here is `e460abea...`, not
  the `b082d594...` recorded in D-239's entry: the builder checks which version holds the bar's 60 ids before
  building and records the digest it used. Half B stays closed.
- **What runs.** Shimmer's system arm only (B3), no B1 and no cloud (D-671), on a bundle sealed on Lambda from a
  commit carrying INFRA-055 and the parser sweep (D-663), with the shipped topology. Integrity by line 2 unchanged.
- **The reading, written before the run.** (a) `tools/contradoc_ok_effect.py` on every run folder: ok answers per
  judging call and per contradiction answer, kept now or refused, and the two label bounds. (b) The scorer's own
  route (`tools/score_corpus.py`, detection_dev and v2_primary; the key read there only, by the lead) twice on the
  same runs: as written, and with every kept ok contradiction record removed (a what-if of the old rule on the
  new answers). The difference is the effect of keeping ok answers, with a paired 95 percent interval over
  documents. The instruction's effect on the irregular answers is not separated: that would need a second arm
  under the old instruction, which this plan does not buy (stated as a limit).
- **Cost, two ways** (A10 at 1.29 USD an hour; K0's measured 9.42 USD over 438 minutes for its 40 ContraDoc
  documents, about 11.0 minutes and 0.236 USD a document including each session's setup):

| Option | Without the saving measures | With them |
|---|---|---|
| (a) all 30 half A documents | 7.07 + 0.43 seal job = **7.50 USD** (9.29 if the asset copy reads MISSING and the 64-minute upload runs) | **6.11 USD**: one instance and one setup for all 30 (about 8.3 minutes a document, assuming about 15 minutes of setup in each of K0's 7 sessions; an assumption, not a measurement), asset copy MATCH, the seal in a route S job already planned |
| (b) the first 15 half A documents in hash order | 3.53 + 0.43 = **3.96 USD** | **3.44 USD**, same measures |

  The saving measures are: one batch instance instead of K0's several sessions; the asset copy reused (MATCH on the Lambda
  file system, no upload); the bundle sealed in a route S job that runs anyway for the next re-seal. The vLLM
  route for the two auditors is not counted, since its ContraDoc speed is not yet measured (the GPU-release run,
  D-694 item 1, measures it). Option (a) is above the 5 USD per-step pre-approval (D-708) and needs Seckin's word;
  option (b) is within it. Recommendation: (b) first; (a)'s second half only if (b) shows any kept ok answer.
- **Stop rule.** The session stops if spend reaches 1.5 times the forecast (the sealed hard ceiling) and reports.

## 4. Limits

- Every saved figure here comes from runs under the old instruction; they bound the code change, never the
  instruction's effect.
- The recorded half A counts (22 answers, 8 documents) cannot be re-read: their maps were lost on 16 November.
- K0's ABSTAIN count is derived from its recorded aggregates (55.0 percent, 7 located, 11 lost, 7 false
  positives), not read from labels.
