# S1 report: hygiene, saving every model reply, the INST_FINDER switch, multi-round readiness

Stage S1 of the autonomous loop of 27 October 2026, on branch `loop/s01` (created from `loop-s00-v1-open`, `5e844ed`). No pipeline run and no Lambda spend.

(Draft, filled in as the commits land.)

## Commits and gates

| Commit | Content | Gate (main checkout, `py -3.12`) |
|---|---|---|
| `f1d7a51` | S1 plan (records only) | not needed (records only) |
| `979aa4e` (C1) | Parts 1 and 5 | main PASS 244, WARN 1, SKIP 3, FAIL or ERROR 28 (the S0 baseline plus new check 275, which passes; same non-pass set); six side gates pass |
| `0fc3e07` | records (D-009, D-010, this report) | not needed (records only) |
| `b761171` (C2) | Part 3, merge of `lane/s01-credential` (`4c1efb1`) plus the lead's `CLAUDE.md` text | main PASS 244, WARN 1, SKIP 3, FAIL or ERROR 28, same non-pass set as C1; six side gates pass (controller gate passed with the four new tests; cloud-run checks 83 of 83) |

## Part 3. The credential path out of the code

- **The 20 files.** Live (changed): `tools/ordinary_final_cloud.py`, `tools/ordinary_final_status.py`, `tools/ordinary_final_bound_preflight.py`, `tools/ordinary_final_v3_preflight.py`. Neither `tools/prepare_cloud_run.py` nor `tools/prepare_ordinary_final_run.py` uses any of the 20. Frozen (unchanged, listed for S13): `tools/checkpoint120_cloud.py` (bound by `tuning/second_tuning_eval_runtime_v2_1/historical_preservation.json`) and, frozen by function with no binding record (D-010), `auditor_blocker_closure_cloud`, `auditor_canonical_cloud`, `auditor_classifier_lora_cloud`, `auditor_classifier_lora_current_cloud`, `auditor_classifier_lora_stabilized_cloud`, `auditor_feature_cloud`, `auditor_final_cloud`, `auditor_final_retry_cloud`, `auditor_linear_cloud`, `auditor_optuna_hpo_cloud`, `auditor_v2_cloud`, `checkpoint120_v21_cloud`, `producer_v3_cloud`, `second_tuning_pilot`, `run_first_real_tuning` (all under `tools/`). `tools/test_auditor_feature_remote.py` is unchanged.
- **Behaviour.** `credential_path()` in the controller calls `agent_wrapper.resolve_config_path()` at the moment of use, never at import, and refuses in one line naming `SHIMMER_CONFIG_PATH` when nothing resolves. The provider call keeps the text `provider=LambdaExperiment(CREDENTIAL)`; the watchdog argument and the independent cleanup use the same resolved path; the status reader and both live preflights use the same function.
- **Bound controller files changed.** Of the seven, only `tools/ordinary_final_cloud.py`. Every bundle sealed before C2, v12 included, now refuses with `Controller source changed` and must be re-sealed. Past results are not affected. The lane noted that `scripts/agent_wrapper.py` now chooses the credential file but is not pinned by the seal; pinning it is left for S2c's controller work.
- **`LINUX_ROOT`.** `tools/ordinary_final_rehearsal.py` (live) reads the Linux home at run time through its own shell and works only in `<home>/shimmer-rehearsal`; an empty, root or relative home is refused; every `rm -rf` is built by one guard that refuses any target outside that folder. Nothing runs at import.
- **Trace.** No importer reads `controller.CREDENTIAL` or the rehearsal's old constant; the controller checks search for the kept source text; no reader in `scripts/` or the main gate.
- **Proofs.** Four new tests in `tools/ordinary_final_controller_checks.py` (run by the controller side gate), each proven by neutralise, fail, restore, pass: (a) the path comes from `SHIMMER_CONFIG_PATH` at use; (b) the one-line refusal comes before any provider handle in the controller, the status reader and both preflights; (c) importing the tools resolves nothing and starts no subprocess; (d) every `rm -rf` target is the rehearsal folder or below it, and empty, root and relative homes are refused. The lane also found that `read_without_the_controller_binding` used `read` without importing it, so that existing gate proof had been passing on a `NameError`; with the import added it fails for the reason it tests.
- **Docs.** `docs/CLOUD_RUN_PREPARATION.md` and the CONTROLLER-BINDING and ASSET-COPY-A bullets of `CLAUDE.md`. No `RUNTIME_REFERENCE.md` row.
- **Left for S13.** `docs/fix/ORDINARY_FINAL_CLOUD_RUN_PREPARATION.md` around line 181 shows a historical watchdog command with the literal personal credential path; it is history and is handled by the history rewrite.

## Part 1. The collaborator's project name

- Re-verified with the H5 pattern: exactly two tracked files, one hit each (`docs/fix/SESSION_HANDOFF.md` line 25, `docs/fix/WORDS_D_INVENTORY.md` line 4). Private patterns over tracked files: 0 files for each of the three (incomplete: private patterns missing from `.claude/` (I.0 item 4 failed); the same three patterns were applied from `docs/loop/private/loop_private_patterns.txt`). So no private-pattern hit needed a binding check.
- A scratch script found each line by the hex pattern and replaced the whole token: line 25 of `SESSION_HANDOFF.md` now names "a private repository, not named here", line 4 of `WORDS_D_INVENTORY.md` "an ingestion folder for an external system (not in this repository)". One line changed in each file. Recount: 0 files in the working tree and 0 in the index at C1.
- Incident INC-003 (private record): after C1 the lead checked the commit message with a pattern that spelled the name in plain letters, once, in a tool call; nothing in any file, commit or record carries it (re-checked with the hex pattern). Decision D-009; reported to Seckin.

## Part 5. Documentation corrections, the request log, the seals folder

- `CLAUDE.md`: the "2/9 to 5/9" sentence keeps its point and now carries its context (7 September 2026; the synthetic wheat test; code from an earlier repository not in this history; a single draw; a location count, not reason-confirmed; the wheat test and key not published here).
- `docs/history/README_PRE_ROUTING_AUDIT.md`: a dated correction note after each of the two "clean twin was never run" statements, pointing to the 2026-09-12 overnight runs and the 2026-09-11 deepening-pass measurements in the same document. No other change.
- `docs/test_change_requests.md`: header and fields (Annex B.6); a verdict for every test folder under `benchmark/corpora/` and for the superseded tuning datasets; eleven requests (TCR-001 to TCR-011), proposals only.
- `.gitignore` gains `seals/`. `scripts/guard_secrets.py --staged` refuses any staged path under `seals/` (plain prefix test over git's own staged-name list, force-added paths included; no new regex). Gate check 275 (`scripts/staged_path_checks.py`): name-list cases, and on a real git index a staged and a force-added `seals/` path refused, an ordinary path passing; the git case is skipped with its reason where git is absent (the container). Neutralise, fail, restore, pass on that check alone: PASS, FAIL (2 failures), PASS.
- `docs/THREAT_MODEL.md`: now says the guard scans file contents across the working tree, that `--staged` checks staged paths only, and that no hook runs it (the `.githooks` folder the old text named does not exist).
