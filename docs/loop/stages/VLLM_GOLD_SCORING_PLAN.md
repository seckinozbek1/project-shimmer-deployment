# vLLM against the current path, scored on development gold (D-625, #217, #264)

Written on 14 November 2026, before any gold-scored vLLM figure exists. It decides how each group of the
vLLM comparison is judged. Nothing here changes after a figure is read; a change is a new decision.

Seckin, 14:38 (D-625): vLLM's bar is the development set's gold answers. Each engine is scored against
gold; vLLM's macro-F1 may be at most 1 point below the current path's at the paired bootstrap lower
bound, and its validity may not be lower. Agreement between the engines (bytes, labels, items both
listed, coverage) is reported apart, as the D-608 cross-platform stability finding, and is never the bar.
V2 (lead, 14:45): the gold bar applies where gold exists, which is PROCESSOR's DEV rows; the other groups
are held to validity, and their agreement is reported.

## What is scored, and how

1. **PROCESSOR, the 84 DEV rows of checkpoint 168.**
   - Scorer: the frozen DEV scorer, `score(row, raw, truncated)` of
     `tuning/second_domain_agnostic_v2/runtime.py` (producer branch). It is vendored line for line as
     `benchmark/baselines/dev_gold_score.py` because the sealed project archive carries no `tuning/`.
     A check holds the copy equal to the frozen per-row metrics of checkpoint 168's `full_dev_scored.json`
     on all 84 rows (`GoldScoreProof`).
   - Gold: each row's `canonical_target` from `tuning/producer_v3/dataset.json`. It is development
     tuning data, not a benchmark key. It travels in the sealed replay file beside its prompt.
   - Per row: contract validity, refusal correctness, and tp, fp, fn for evidence, claims, typed gaps
     and typed uncertainty.
   - **Bar:**
     - macro-F1 is the mean of the four F1s over pooled counts;
     - vLLM's macro-F1 minus the current path's, one-sided 5 percent paired bootstrap lower bound
       (2,000 resamples, clusters by document family), must be at least -0.01;
     - contract validity must not be lower;
     - items in valid replies must not be fewer (102 of 102 on the current path).
   - The current path's replies are those of vllm-test-217b. A DEV row whose current reply text is not on
     hand (its digest matches no saved reply) is left out of every arm, so the comparison stays paired.
     It is counted (`rows_left_out_no_current_text`).
   - Scored on the instance. Only the counts and the bar's figures leave it.
2. **The 40 PROCESSOR synthetic records, ARCHIVIST, EDITOR_CLERK, CITATION_RESOLVER, LEGAL_ANALYST and
   SPEECH_ACT_TAGGER.** There is no per-call gold: the synthetic suite's keys score a whole pipeline
   run's findings (`tools/score_corpus.py`), and a replay makes no findings.
   - Held to validity: contract validity not lower than the current path's, per agent.
   - Agreement is reported as the stability finding: byte identity, label agreement, agreement on items
     both listed, and item coverage.
   - End-to-end gold scoring of these roles (V1) is Seckin's choice, not part of this plan.
3. **VERIFIER.** It has no gold of its own, and its output is advisory. Held to validity, with agreement
   reported, as in 2. In this launch it also carries the diagnosis of the stability finding:
   - vLLM with `VLLM_BATCH_INVARIANT=0`;
   - transformers on vLLM's own library stack (`hf_aux`), compared with the current path.

## What it is never

- A key is never opened by anyone running this: only the scorer reads gold.
- No figure is read before this file is committed.
- Speed is reported, cross-session against vllm-test-217b on the same machine type. It is not part of
  the bar.
