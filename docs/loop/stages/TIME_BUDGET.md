# Where the time goes (D-S80 targets, measured under D-S81)

Measured from saved evidence only; no model was run. Written by `demo-console` (D-338) and committed by the lead (D-340); revised on 9 November for the lead's D-339 and compare-check's findings (D-362). Two kinds of reading, with their dates and machines:

- the review and launch figures, read on 8 November from runs on the A10 (`gpu_1x_a10`, us-east-1);
- the upload figures of 9 November (D-354 to D-356), read from the lead's PROGRESS-A observations of uploads leaving this laptop's uplink.

Under D-S81 these are targets that are measured and reported, never a condition of success. This file measures and names causes; it proposes no change for this loop (D-339).

## Sources

- Each run's `logs/model_telemetry.jsonl`: `pipeline_start` and `pipeline_end`, `model_load_start` and `model_load_end`, `backend_invocation`, `generation_interval`.
- The controller's `*_timing.json` phase files.
- The batch entries' workload timings.
- The budget ledger's `launch_requested_utc`.

- The lead's PROGRESS-A readings of the 9 November uploads (D-354), and the run folders of `T2E_TRAIN_E` (D-356).

Runs read: the cases batch (4 entries), L12 (37), L12b (13), C1 (25), L11's B1 and B3 pairs, J1, C base, D-277, D-278 and D-291, and the 9 November launches.

Three definitions apply throughout:

- **Wall time of a review:** `pipeline_start` to `pipeline_end`, read from the run's telemetry. It leaves out the process start before the pipeline and the runner's own work around it.
- **Entry time:** the batch entry's `batch_workload_<n>_timing.json`, the runner's whole workload for that entry. D-332 and D-338 gave the cases in entry time (1.5, 31.7, 0.5 and 20 min; the timing files read 92, 1,906, 32 and 1,257 s, so 1.5, 31.8, 0.5 and 21.0 min; D-332 rounds the last to 20). The same entries in wall time are 50 s, 31.2 min, 0.1 s and 20.4 min. Both are stated, never mixed in one figure.
- **Pages:** about 3,000 characters a page. A document's size is the largest `char_end` its run's reference index holds for it.

Every figure below is a cold figure, with the models loaded during the run, unless it says warm. D-S80 item 1's limits are for a warm machine, and no warm run exists. The warm estimate (wall time less about 50 s, below) is an estimate, and the counts of section "Timed-out items" are given both ways.

## Targets against measured figures

| Target (D-S80) | Measured on the A10 | Source |
|---|---|---|
| Short document of about 5 pages: 2.5 min | Not met, even on shorter documents. ContraDoc (5,100 to 8,000 characters, 2 to 3 pages): median 5.2 min (C1, n=15, all 15 passed integrity), 7.4 min (L12, n=3; `06cd776dcc1a`, 8.3 min, failed integrity). Host-agreement review (8,600 characters): 31.2 min, failed integrity. Draft-resolution review (6,500 characters): 20.4 min, failed integrity. CUAD contract (16,700 characters, about 5.6 pages): 113.7 min in L12 and 108.7 min in L12b (corrected from 108.7 for both in the text committed by D-340), both failed integrity. ContractNLI (8,700 to 11,600 characters): 35.7 to 90.2 min, both passed (L12). A time taken from an entry that failed integrity (`semantic_incomplete`) is the time of a review that did not finish its semantic work, and is marked so wherever it appears | L12, L12b, C1, cases entries 2 and 4 |
| Document of about 20 pages: 7.5 min | No run of that size exists | none |
| Three-round negotiation case, all rounds: 15 min | Met for the multi-round run itself: host agreement 50 s (5 suggestion calls), draft resolution 0.1 s (no calls). Not met if the case includes the ordinary review of the last version (31.2 and 20.4 min more) | cases entries 1 to 4 |
| One benchmark question: 15 s | B1 in the choice form: 0.36 s a prompt (C base, 7,340 prompts). B1 with a generated answer (Phi-4, J1, as D-278 corrected D-277): 13.5 s direct and 36.9 s with reasoning, means over B1's 155 prompts of about 1,250 tokens (J1's `replay_measurement.json`, its `rows` by `form` `b1`). D-278's "long" figures, 35.2 s and 55.2 s, are not B1's: they are the judge variants on the 94 agent-form prompts of about 5,800 tokens (`form` `agent`). B3 on SciTab: median 220 s a table of about 3.7 claims, so about 59 s a claim, including about 30 s of model loads (C1, n=10; 9 passed integrity, `22_scitab_459af44812cf`, 228.6 s, failed). B3 on ContraDoc: one question a document, as in the first row | D-291, D-278, C1 |
| Launch to ready (filesystem copy): 7.5 min | Not met. With the copy a MATCH: 14.8 min (L12) and 14.4 min (C1). Without it, so with the upload: 72.7 min (the cases, the seeding launch), 73.3 min (J1), 70.2 min (C base) | ledger, phase files |
| At most 5 times B1, same item and machine | Same item, same session and machine type: L11's B3 and B1 entries, entry times, models loaded cold in both arms, B3 at L11's code. Only 2 of the 8 L11 pairs completed (both arms passed integrity): SciTab `09b24267b75a` 2.4 and `26937b278860` 2.6, both within 5 times. The other 6 pairs' B3 entries failed integrity (`semantic_incomplete`, 4 with `required_contract_failure`), so their quotients (ContraDoc 5.3, 4.2 and 7.8; SciTab 2.1; ContractNLI 5.3 and 15.2) are shown apart and are not ratios of completed reviews. No completed ContraDoc or ContractNLI pair exists. Current B3 code (L12) against L11's B1 is a cross-run figure, with code and session differing jointly, so it is shown apart and never as the ratio | L11 `batch_workload` timings; L12 telemetry |

## The B1 ratio, per document

D-S80 item 2's figure is the same item on the same machine type, both arms completed. L11 is the one run with such pairs: its B3 and B1 entries ran in one session on one A10, both cold, timed as entry times. Every L11 B1 entry passed integrity; only 2 of the 8 L11 B3 entries did (each entry's `evidence/result.json`). So the ratio table holds the two completed pairs, and the six pairs whose B3 entry failed are shown apart, never as a ratio of completed reviews.

| Document | L11 B3 entry (s), integrity | L11 B1 entry (s), integrity | Ratio, same session |
|---|---|---|---|
| SciTab `09b24267b75a` | 247, passed | 104, passed | 2.4 |
| SciTab `26937b278860` | 331, passed | 128, passed | 2.6 |

**Shown apart: pairs whose B3 entry failed integrity.** Each failed entry is the time of a review that did not finish its semantic work (`semantic_incomplete`; `required_contract_failure` where marked), so its quotient is not a completed review's ratio.

| Document | L11 B3 entry (s), integrity | L11 B1 entry (s) | Quotient |
|---|---|---|---|
| ContraDoc `01015e47de8a` | 295, failed (`semantic_incomplete`) | 56, passed | 5.3 |
| ContraDoc `027002a77443` | 235, failed (both reasons) | 56, passed | 4.2 |
| ContraDoc `06cd776dcc1a` | 439, failed (both reasons) | 56, passed | 7.8 |
| SciTab `0e7ff50baa5f` | 187, failed (both reasons) | 91, passed | 2.1 |
| ContractNLI `0d98d9131a5b` | 1,895, failed (`semantic_incomplete`) | 355, passed | 5.3 |
| ContractNLI `01c9504b9c28` | 4,470, failed (both reasons) | 295, passed | 15.2 |

**Shown apart: the current B3 code (L12) against L11's B1.** A cross-run quotient: an L12 pipeline wall over an L11 entry time, with code, session and timing definition differing jointly. It shows how far the current code moves, and is never the ratio.

| Document | L12 B3 wall (s), integrity | L11 B1 entry (s) | Cross-run quotient |
|---|---|---|---|
| ContraDoc `01015e47de8a` | 441, passed | 56 | 7.9 |
| ContraDoc `027002a77443` | 205, passed | 56 | 3.7 |
| ContraDoc `06cd776dcc1a` | 497, failed (both reasons) | 56 | 8.9 |
| SciTab `0e7ff50baa5f` | 180, passed | 91 | 2.0 |
| ContractNLI `0d98d9131a5b` | 2,141, passed | 355 | 6.0 |
| ContractNLI `01c9504b9c28` | 5,411, passed | 295 | 18.3 |

## Where the time goes inside a review

- **Model loading is small.** Every L12, L12b, C1 and case review loads models cold three times (the producer, the auditor, then the producer again after an eviction), 30 to 37 s in all.
  - A warm machine with both models resident would save about 30 s a document, and about 22 s more of boot and indexing (D-100).
  - The warm estimate is therefore the wall time less about 50 s.
- **Outside the models (Python, I/O):** 4 to 29 s a run.
- **Embedding:** 16 to 105 s a run.
- **Model generation takes the rest,** almost all of it in a few agents' calls.
  - **PRACTICE_AUDITOR's judging calls on paired plans:** one call per (unit, rule) plan Python could not settle, about 12 to 15 s each. They take 89 percent of the ContractNLI wall time (195 to 272 calls), 83 to 89 percent of CUAD's (410 calls), and 60 to 65 percent of the two case reviews' (76 and 64 calls).
  - **Single long generations:**
    - VERIFIER: 422 s in one call. This is the host-agreement call whose 13 KB reply was set aside.
    - CITATION_RESOLVER: 188 s in one call on the draft resolution, and 20 to 32 percent of the wall time on the synthetic suite.
    - PROCESSOR: 26 to 48 percent of the wall time on the short ContraDoc runs.

## Launch to ready, with the copy a MATCH (L12, C1)

| Phase | Time |
|---|---|
| Instance up and ssh ready | 4.2 to 5.3 min |
| Hashing the filesystem copy on the instance | 3.1 to 4.1 min |
| Copying it into place | 2.5 to 2.9 min |
| Pinned wheels | 1.3 to 1.5 min |
| Support transfer | 0.7 min |
| Extraction and integrity | 0.7 min |

Without a MATCH, the upload alone takes 63 min (3,797 to 3,857 s).

## Launches of 9 November: three uploads at once, and the copy probe's deadline (D-354 to D-356)

Measured only; nothing here was changed.

- **Three uploads shared one uplink.** The three launches of D-353 each uploaded the 22.25 GB asset archive from this machine at the same time, at about 2 MB/s each (the lead's PROGRESS-A readings at 06:28, 07:13, 07:59 and 08:45 UTC+3, D-354). One upload alone ran at about 5.8 MB/s: C base's `assets_transfer` took 3,800 s for 22.25 GB (D-291 rounds it to 5.9). The auditor's last 1.5 GB, once alone, ran at about 5 MB/s (D-356).
- **The scp limit.** The controller's asset transfer is one scp with a fixed 10,800 s timeout (`tools/ordinary_final_cloud.py`, a bound file). At about 2 MB/s, 22.25 GB needs about 11,100 s, past the limit. `dev-t2e-train` had uploaded 76.2 percent at 07:59 and hit the limit at about 08:43 ("Transport deadline exceeded"); no training ran, about 4.02 USD. The other two finished their uploads inside it, the auditor's only after the others had left the link.
- **The copy probe's deadline.** The relaunch with the asset copy declared (`T2E_TRAIN_E`, D-355) stopped at "Phase deadline exceeded: asset_copy_probe". The probe hashes the 22.25 GB copy on the instance under a fixed 300 s deadline; L12 and C1 measured it at 3.1 to 4.1 min, and this time it ran past 5. Its receipt records no state (`used: false`, `seeded: false`), so the copy itself was not judged. About 0.28 USD; no training. The cause of the slower read is not traced (D-356).
- **Launch to ready, as these launches give it:** past 10,800 s for an upload shared three ways; not reached for a probe past 300 s.

## The biggest causes (measured; under D-S81 no change is proposed or made in this loop)

1. **Paired judging calls.** PRACTICE_AUDITOR makes one call per (unit, rule) plan Python could not settle, about 12 to 15 s each. Their number grows with units times paired rules: 64 and 76 on the case reviews, 195 to 272 on ContractNLI, 410 on CUAD. They take 60 to 89 percent of the wall time on rule-heavy documents.
2. **Single generations that run long.** VERIFIER: 422 s in one call (the host-agreement call whose 13 KB reply was set aside). CITATION_RESOLVER: 188 s in one call. On the shorter runs PROCESSOR takes 26 to 48 percent of the wall time.
3. **Launch to ready.** With a MATCH: the instance becoming ready (4.2 to 5.3 min), the hash of the filesystem copy on the instance (3.1 to 4.1 min) and the copy into place (2.5 to 2.9 min). Without a MATCH: the upload (63 min alone, about three times as long shared three ways). A probe past its 300 s deadline stops the launch (D-356).
4. **Model loading:** three cold loads a run, 30 to 37 s; small beside causes 1 and 2.
5. **The B1 ratio follows cause 1.** The two completed same-session pairs (SciTab, 2.4 and 2.6 times B1) are within 5 times. Among the pairs whose B3 entry failed integrity, shown apart, 2 of 3 ContraDoc quotients (5.3 and 7.8) and both ContractNLI quotients (5.3 and 15.2) are above 5; no completed ContraDoc or ContractNLI pair exists to settle it.

## Timed-out items (D-S80 item 4)

Counted against twice each target, from the wall times above (the reading of 8 November; each run's wall is `pipeline_start` to `pipeline_end`). D-S80 item 1's limits are for a warm machine, so the count that answers them is the warm-adjusted one (the wall less about 50 s, the estimate above); the cold count is printed beside it so the adjustment can be seen. No run was warm, so the warm column rests on that estimate.

| Target, twice it | Over, cold | Over, warm-adjusted (the count against D-S80) | Not over, warm-adjusted | Not over, cold |
|---|---|---|---|---|
| Short document, 2.5 min, so over 5 min | C1 ContraDoc 9 of 15; L12 ContraDoc 2 of 3 (one failed integrity); L12b ContraDoc 0 of 1; both case reviews (20.4 and 31.2 min) and both CUAD (L12, L12b), all four failed integrity; both ContractNLI (L12), passed | C1 ContraDoc 4 of 15 (5.2 to 7.4 min warm); L12 ContraDoc 2 of 3; L12b 0 of 1; the case reviews, ContractNLI and CUAD as cold | C1 ContraDoc 11 of 15 (warm 1.8 to 4.8 min: the 6 under 5 min cold, and 5 more whose cold walls are 5.1 to 5.7 min); L12 ContraDoc 1 of 3; L12b 1 of 1 | 6 C1 ContraDoc (2.6 to 3.6 min), 1 L12 (3.4 min), 1 L12b (4.9 min) |
| Question, 15 s, so over 30 s | every B3 SciTab claim measured (about 59 s a claim, C1 n=10, one entry failed integrity); B1 with reasoning (36.9 s) | B3 SciTab about 46 s a claim (220 s less 50, over 3.7 claims); B1 as cold (its figures are per call, models loaded) | B1 in the choice form and B1 direct, as cold | B1 in the choice form (0.36 s); B1 direct (13.5 s). The judge variants on the agent-form prompts (35.2 s and 55.2 s) are not B1 and are not counted here |
| Three-round case, 15 min, so over 30 min | none for the multi-round runs (50 s, 0.1 s); with its ordinary review, the host-agreement case (50 s and 31.2 min, together 32.1 min) | the host-agreement case with its review, about 31.2 min (the review less 50 s; the multi-round run recorded no model load, so it is not adjusted) | the draft-resolution case with its review (about 19.6 min warm) | the draft-resolution case with its review (0.1 s and 20.4 min) |
| Launch to ready, 7.5 min, so over 15 min | every launch with an upload (70.2 to 73.3 min) | not applicable: a launch has no warm form | not applicable | the two launches with a MATCH (14.4 and 14.8 min, just under) |

The two 9 November launches that stopped (D-354 at the scp limit, D-356 at the copy probe) never became ready, so they have no launch-to-ready figure and are counted in neither column; each is named in the launch section above.

No run's records carry a timed-out field yet, so these counts are read from the timings, not from a marker.

## Not measured

- A 20-page document.
- A run on a warm machine. The warm figure above is an estimate: the wall time less the measured loads and boot.
