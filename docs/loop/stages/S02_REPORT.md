# S2 report: honest outputs, multi-round enablement, and the run controller

Stage S2 of the autonomous loop of 27 October 2026, on branch `loop/s02`, created from `loop-s01-v1` (`cef0294`). No pipeline run and no Lambda spend. Plain English; `<USER_HOME>` stands for the user's home folder. The stage was carried by two lead sessions: the first until 12:45 +03:00, then, after the restart for push rights (Annex D, D-S5 item 6), a second one.

## What was done

- **S2a, honest deliverables (Annex A 11.6.4 second half, 11.6.5).** Every model finding not promoted to an amendment stays in view and carries "Written by a model. Not promoted to an amendment. Not checked by Python." (and its Turkish rendering) in `document_summary.md`, `reviewed_document.md`, `_run_summary.md`, `review_data.json` (`model_findings_not_promoted`) and the console. Provenance is read off the bus post (`finding_record.written_by`; WRITTEN-BY-A); an unstamped record is never Python's. The producer sentence is generated from what ran (`findings_provenance`), with the Turkish catalog updated. Amendment templates read as plain sentences naming the unit, the rule, both figures with units and the relation; one figure formatter is used everywhere. An absence finding sits at the unit that lacks the field, or says Python could not place it. `audit_synthesis.md` counts audit-trail patterns, sets apart escalations with no topic or payload and those naming unregistered agents. Model-only relations are listed apart. Every paired judging call is recorded with its outcome, and the deliverables state calls made and notes kept. Gate check 278 (46 proofs, each neutralise, fail, restore, pass).
- **S2b, multi-round.** Final mode admits a declared multi-round Review (`--multi-round` with its manifest); later rounds reuse unchanged units through a Python-only per-round review (`multi_round_rounds`), recorded in `audit/round_reuse.json`; every reply of a multi-round run is saved once (outcome `advisory_not_record`); a term that vanished while its section states an unclaimed newcomer in the same unit of measure is refused as a possible rename, never minted as withdrawn (the S5 measurement on the S3 rename probes decides any ensemble rule). Check 261's five stripped statements and two parser flags are unchanged. Gate checks 279 and 280; check 185 replaced (its old edge case is the behaviour S2b item 5 reverses).
- **S2c, the run controller.** External bundle and output paths (`--output-dir`), the seal carries the test manifest's hash, `RUN_REPORT.md` and `FINAL_STATUS.json` `report` rows with every 11.12 field, the purpose and sealed-or-exposed lines, the INST_FINDER value, FACT_CHECKER withheld with both B.4 reasons, instance type and price, and the asset-copy result. Instance candidates, region, rate cap and caps are sealed manifest fields; the loop budget guard (`tools/loop_budget_guard.py`) decides every ordinary final launch; ledger lines and `shimmer-loop-` names; detached runs with keep-awake; sealed mode; the protected-test guard for sealed runs; batches (B3 then B1 per item); new phases classified for check 274; named archive extras; the asset-copy declaration must name the bundle's own archive. Proven in `tools/ordinary_final_controller_checks.py` (73 tests, 51 neutralisation proofs at the round-2 lane commit), `tools/cloud_run_checks.py` (88 tests) and `tools/multi_round_launch_checks.py`.
- **S2d.** README, `CLAUDE.md` (LOOP-LAUNCH-A, SEALED-RUN-A, MULTI-ROUND-A, HONEST-OUTPUT-A, WRITTEN-BY-A, CONTROLLER-BINDING, ASSET-COPY-A), `docs/RUNTIME_REFERENCE.md`, `docs/CLOUD_RUN_PREPARATION.md`, `docs/RUNBOOK.md` and `docs/DEPLOYMENT_RESOURCES.md` updated with each change.
- **Annex D applied in S2.** D-S4: the loop may write asset-copy declarations for the bundles it runs and refresh the filesystem's archive (D-028, wording in `CLAUDE.md`, `docs/CLOUD_RUN_PREPARATION.md`, `docs/DEPLOYMENT_RESOURCES.md`). D-S9: the guard and the reaper read the budget and the hard stop from the ledger's latest budget line (`addf658`, D-031); with no readable budget line a launch is refused and the reaper terminates every loop instance; the scheduled reaper read budget 70 and hard stop 69 from 10:06:59 UTC. Proof on the mocked provider: `tools/loop/reaper_proof.py`, run at `f4e3813` (steps 1 to 10; step 9 closes an intent with no instance after its deadline, step 10 writes the closing line to the ledger that holds the launch): all passed; at `b8e5c17`, on a copy with the budget reading neutralised (`budget_figures` returning 50 and 49), steps 6 and 8 failed (results in the private records; the same held at `addf658`), plus controller checks registered in the gate's neutralisation list. D-S10 (progress file): D-035.

## Guards replaced (S2b item 1, S2c items 9 and 10), file and line at the S2 tip

Each refusal of multi-round or of a protected test was replaced only by a check that the run is declared, sealed and valid.

| File | Before (at `cef0294`) | Now |
|---|---|---|
| `tools/ordinary_final_run.py` | line 61 "Excluded workload" (multi-round and `protected_test` refused); line 62 argv check; the authorization's hard-coded A10 and us-east-1 | `admit_workload` (line 138, called at 183) checks `multi_round`, the case manifest hash in `support_files` and `case_manifest_sha256`, `fixture: false`, the live field set (`validate_live_case_manifest`, line 75) and exactly `MULTI_ROUND_ARGV` (line 212); `selected_candidate` (line 220) reads the sealed instance candidate; `max_runs == 1` kept (one run per bundle) |
| `tools/ordinary_final_bound_cloud.py` | lines 33 and 34 | admitted exactly when declared, sealed and valid (around line 123); a sealed bundle inside the repository is refused before any write (`refuse_sealed_bundle_in_repository`, line 61) |
| `tools/ordinary_final_cloud.py` | the authorization's `multi_round=False` (line 312) | `m['multi_round']` and `m['protected_test']` from the sealed manifest (lines 363, 626); `--frozen-tag` resolves `refs/tags/<name>` only |
| `tools/prepare_ordinary_final_run.py` | line 177 fixed multi-round off; the "no multi-round" restriction (206) and the transfer-plan exclusion (220) | seals the declared value (`multi_round = case is not None`, line 300; lines 372, 375, 425) |
| `tools/prepare_cloud_run.py` | lines 129, 131 to 139, 152 and 165 | `behavioral_proof` (line 104) requires an explicit declaration and refuses a declared multi-round on this path (it seals `dependency_dag`; D-011 choice 3); the "exactly three guards" count (line 155) is unchanged, because the pipeline gained no new top-level branch, proven by a `cloud_run_checks` case |
| `tools/ordinary_final_v3_cloud.py` | line 38 | unchanged: frozen to bundle v3 (S2c item 16); its scope check equals that one bundle's sealed declaration, and it cannot launch now (consumed authorization, no `shimmer-loop-` name, no launch plan). A docstring added in `d51983c` was removed again (D-034), so the file equals its `cef0294` content, as does `tools/ordinary_final_retry_cloud.py` |

## Controller binding (S2c item 15)

Of the seven files the v12 manifest binds, six changed in S2: `tools/cloud_run_common.py`, `tools/cloud_run_watchdog.py`, `tools/ordinary_final_bound_cloud.py`, `tools/ordinary_final_cloud.py`, `tools/ordinary_final_run.py`, `tools/ordinary_final_watchdog.py` (`tools/lambda_experiment_provider.py` is unchanged). Four files the controller imports to decide and record a launch joined the binding: `tools/loop_budget_guard.py`, `tools/loop/instance_reaper.py`, `tools/loop/keep_awake.py`, `tools/run_remote_experiment.py` (`tools/prepare_ordinary_final_run.py`, `local_control_hashes`). Every bundle sealed before S2, v12 included, refuses with "Controller source changed" and cannot be re-executed with the changed files; past results are not affected. New manifests carry the new hashes.

## Pinned-baseline amendments (IV.7)

Five S2 entries in each of `benchmark/fixtures/multi_round_baseline_contract.json` and `benchmark/fixtures/topology_reference_contract.json`, each with the reason "Operator-directed, 2026-10-27, loop stage S02: ...":

1. S2a honest deliverables and S2b multi-round: `_append_board_to_deliverable`, `_paired_convention_review`, `_render_per_agent_md`, `phase_5_5_convention_review`, `phase_6_synthesis`, `write_deliverables_run_summary`.
2. S2a reader-check fixes (note-writing model): `_paired_convention_review`, `_render_per_agent_md`, `phase_6_synthesis`, `write_deliverables_run_summary`.
3. S2 checker round 1 fixes (model items kept out of the earlier-version section): `_paired_convention_review`, `phase_6_synthesis` (merge `5e2c432`).
4. S2 checker round 2 fixes: `_paired_convention_review`, `_render_per_agent_md`, `phase_6_synthesis`, `write_deliverables_run_summary`.
5. S2 checker round 3 fixes (judged-absence call outcomes, one note count): `_paired_convention_review`, `_render_per_agent_md`.

`main` needed no amendment: the final-mode admission sits inside its `if final_models.mode() == 'final':` block, which `reference_tree` strips before hashing (`scripts/execution_topology_checks.py`, `RemoveFinalTelemetry`), so its pinned hash did not move. The corpus loop header and check 261's five stripped statements are unchanged.

## Gate (IV.7)

Main checkout baseline: `docs/loop/GATE_BASELINE.md` (275 entries at S0; 278 at the S1 close; 281 with S2's checks 278 to 280). Non-pass set at the S1 close and at every S2 gate: SKIP 01, 145, 261; WARN 38; ERROR 91, 96, 101, 108, 110, 126, 129, 140, 196, 203, 210, 213, 214, 247, 250, 251, 259; FAIL 117, 118, 121, 146, 193, 246, 248, 252, 255, 257 (31 checks). Causes as the baseline records them: most are the interpreter (no `fastapi`, `uvicorn` or `pypdf`) or the network; 252 is code (the Dockerfile line, open item 7); 146, 193, 246 and 248 (and 255, most likely the missing `fastapi`) are not established.

| Commit | Main gate | Side gates |
|---|---|---|
| `4701f84` (checker round 1 closed) | PASS 250, WARN 1, SKIP 3, FAIL or ERROR 27, the baseline's non-pass set | run at `7027a29`, all pass |
| `e1ca581` (D-S9 merged) | PASS 250, WARN 1, SKIP 3, FAIL or ERROR 27, the same set | all six pass |
| `b8e5c17` (round-2 merge) and `424d81c` (round-3 text) | not run at these commits (memory below the 4 GB floor, D-013); covered by the next gate, whose tree contains both | lane runs: controller gate 73 tests, cloud checks 88, check 278 46 proofs, localization pass |
| `af3e390` (check 181 needles) | PASS 250, WARN 1, SKIP 3, FAIL or ERROR 27, the same 31 non-pass checks (791 s) | not run (only `scripts/verify_session1.py` changed) |
| `f4e3813` (round-3 merge, D-038) | PASS 250, WARN 1, SKIP 3, FAIL or ERROR 27, the same 31 non-pass checks (652 s) | all six pass (controller gate 75 tests) |

Commits without their own gate run are listed in D-034 (a recorded departure).

## Checkers

- **Round 1** (first session): completeness, adversarial, claims; all items closed by the lanes (D-022 to D-026).
- **Reader check (S2a item 8)**: three rounds (rounds 1 and 2 in the first session; round 3 on `e1ca581` mocks: 0 CRITICAL, 2 SERIOUS, 9 MINOR, all earlier SERIOUS items fixed or partly fixed). Round 3's items were closed by the pipeline fix lane (`45aaaea`); the two SERIOUS items go to a tie-break checker with the fixed deliverables, as IV.4 requires after a third round.
- **Round 2** (on `e1ca581`): completeness 48 items, 34 covered, 7 gaps (1 SERIOUS); adversarial 15 items (2 SERIOUS); claims 5 items (1 SERIOUS). All closed: code by `lane/s02-fix2-controller` (`e549dc5`) and `lane/s02-fix2-pipeline` (`45aaaea`), text and records by the lead (D-034, D-036, D-037). Open item 20 records the frozen launchers (P9 reason a). One item closes only at the stage close: `VERSION` is set to `0.1.0.dev2` there (claims round 2, item 5).
- **Round 3** (on `b8e5c17`): completeness 53 items, 45 covered, 1 MINOR gap (reaper proof not re-run after `e549dc5`: re-run, D-037); claims 8 MINOR, all text, fixed (`424d81c`); adversarial 0 CRITICAL, 1 SERIOUS (a failed or all-refused judged-absence call described as listed), 7 MINOR; all fixed by `lane/s02-fix3` (`c3a14d6`) and the lead (`af3e390`), merged as `f4e3813` (D-038: the reaper's deadline charge is a ceiling).
- **Tie-break after round 3** (IV.4 step 5), on `f4e3813`: the SERIOUS item NOT CONFIRMED (fixed); of the seven MINOR, six NOT CONFIRMED and one confirmed as a records gap (the reaper proof's saved result predated step 10), closed by saving the tie-break checker's own run at `f4e3813` (all 18 results pass, step 10 included); a further records gap (this report listed four pin entries, not five) closed here. No checker item is open.

## Count line

S2 named 48 specification and exit items (the round-2 completeness checker's count), plus every item of three checker rounds (round 2: 7 + 15 + 5; round 3: 1 + 8 + 8; round 1 is recorded in D-022 to D-026), three reader-check rounds (round 3: 11) and two tie-breaks. 48 items done; every checker item worked and closed in the stage except two recorded as open items with their reasons: open item 20 (frozen tuning launchers bypass the loop guard; P9 reason a, an operator decision, listed in FOR_SECKIN) and open item 21 (an in-range value under a rule-stated range costs a model call; a review-behaviour change recorded for the S6 sweep under P16). 0 BLOCKED.

## Loop-until-certain (III.2 step 4)

1. **What is left?** Records and the close: `VERSION` 0.1.0.dev2, the merge, the loop-branch gate, the tag, the `VERSIONS.md` row, the push and the issues. Nothing in the code.
2. **How critical, and is each really resolved?** Every CRITICAL and SERIOUS item has evidence at `f4e3813` from a checker other than the one that raised it (tie-breaks). The gate equals the baseline at the last two code commits. The live reaper runs the merged code without error and reads budget 70 and hard stop 69.
3. **Am I sure?** One uncertainty remains and is stated: the commits named in D-034 and `b8e5c17`/`424d81c` have no gate log of their own; every later gate covers their trees. No other doubt was found in a third look.

## Spend

0.00 USD on instances in S2. The storage share of `shimmer-filesystem` accrues to the reserve (about 0.13 USD a day).
