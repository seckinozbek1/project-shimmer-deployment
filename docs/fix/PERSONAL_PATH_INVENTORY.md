# Personal path inventory

Read-only inventory written in loop stage S1 Part 2 (2026-10-27). It changes no other file. It is the input for loop stage S13, which rewrites the repository's history to replace every personal path form with `<USER_HOME>` (and to remove the collaborator's project name). The exact literal forms, including every escaped form, are kept outside the repository and are never committed; here each form has a label.

Counted at `loop-base` (`f31eff4`, the loop's starting commit) over all tracked files, case-insensitive. Paths under `prompts/`, `docs/loop/private/`, `benchmark/keys/` and `input/` hold no tracked file there.

## 1. Forms and counts at the starting commit

| Label | Form (described, not spelled) | Files | Hits |
|---|---|---|---|
| F1 | drive letter, colon, backslash, Users, backslash, account name | 81 | 758 |
| F2 | drive letter, colon, slash, Users, slash, account name | 22 | 22 |
| F3 | as F1 with every backslash doubled (the JSON-escaped form) | 72 | 14608 |
| F4 | slash, home, slash, the Linux user name | 11 | 39 |
| F5 | the slug form: drive letter, two hyphens, Users, hyphen, account name (a Claude Code project-folder name) | 3 | 11 |
| F6 | slash, drive letter, slash, Users, slash, account name (Git Bash) | 0 | 0 |
| F7 | slash, mnt, slash, drive letter, slash, Users, slash, account name (WSL) | 0 | 0 |
| F8 | URL-encoded forms, such as percent-5C or percent-2F between Users and the account name | 0 | 0 |

- **Union** (files with any form): 186 files, 15438 hits.
- **Case variants:** none found; every hit uses the case shown in the private forms file.
- **Other escapes searched and not found:** four backslashes, `\u005c`, `\x5c`, `file:///`, a path without the drive letter.
- **Inside compressed files at the starting commit:** the zip, docx and tar.gz files were opened in memory and searched; no form was found (archives nested inside them were not opened). S13 step 4 repeats this over history.
- **The bare account name outside a path** occurs 6 times (in `CITATION.cff`, `LICENSE`, `docs/fix/SESSION_HANDOFF.md` and `docs/fix/STEP_W0_REPORT.md`), inside the author's name and the public GitHub account name. It is **never a replacement target**.

## 2. Classes

(a) hash-bound: 73 files; (b) code that reads the path at run time: 16; (c) generated log or archive: 93; (d) prose: 4.

**How (a) was counted, both methods.** Exact hash match: 73 files (each file's git-blob SHA-256, its working-tree SHA-256 with CRLF, its LF-normalised SHA-256 and its git blob id, searched in every tracked text file). Path mention in a hash-bearing JSON record: 78 files. The 6 files named by path but matching no hash appear only in a plain path list and are counted in class (c). Some files match only on the CRLF working-tree hash, so line endings matter for any rewrite.

### (a) Hash-bound

| File | Forms (hits) | Bound by |
|---|---|---|
| `benchmark/first_tuning_experiment_v1/ADMIN_SUBMISSION.md` | F1 3 | `benchmark/first_tuning_experiment_v1/freeze.json`; `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/catalog_proofs/first_tuning_experiment_v1.json` |
| `benchmark/first_tuning_experiment_v1/README.md` | F1 1 | `benchmark/first_tuning_experiment_v1/freeze.json`; `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/catalog_proofs/first_tuning_experiment_v1.json` |
| `benchmark/first_tuning_review_cohort_v2/ADMIN_SUBMISSION.md` | F1 3 | `benchmark/first_tuning_review_cohort_v2/freeze.json`; `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/catalog_proofs/first_tuning_review_cohort_v2.json` |
| `benchmark/machine_adjudication_v2/README.md` | F1 1 | `benchmark/machine_adjudication_v2/release_freeze.json`; `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/catalog_proofs/machine_adjudication_v2.json` |
| `benchmark/producer_coverage_amendment_v1/README.md` | F1 1 | `benchmark/producer_coverage_amendment_v1/release_freeze.json`; `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/catalog_proofs/producer_coverage_amendment_v1.json` |
| `benchmark/producer_coverage_amendment_v2/README.md` | F1 1 | `benchmark/producer_coverage_amendment_v2/release_freeze.json`; `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/catalog_proofs/producer_coverage_amendment_v2.json` |
| `benchmark/producer_coverage_amendment_v3/blind_evidence/access_logs/access-10080-1789500384027621900.json` | F3 8 | `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/blind_evidence/access_logs/access-11168-1789500167047263800.json` | F3 9 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/blind_evidence/access_logs/access-12240-1789500509500202700.json` | F3 10 | `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/blind_evidence/access_logs/access-17060-1789499809541088500.json` | F3 10 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/blind_evidence/access_logs/access-18464-1789500022553400300.json` | F3 9 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/blind_evidence/access_logs/access-22836-1789499778478030500.json` | F3 10 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/blind_evidence/access_logs/access-26128-1789500035030834200.json` | F3 10 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/blind_evidence/access_logs/access-26368-1789499973062923000.json` | F3 10 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/blind_evidence/access_logs/access-26660-1789499890935745300.json` | F3 8 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/blind_evidence/access_logs/access-28220-1789499855711586900.json` | F3 9 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/blind_evidence/access_logs/access-6724-1789499996499124000.json` | F3 7 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/FIRST_TARGET_ACCESS.json` | F3 1 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-10080-1789500384027621900.json` | F3 8 | `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-11168-1789500167047263800.json` | F3 9 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-12240-1789500509500202700.json` | F3 10 | `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-15156-1789502030254366700.json` | F3 1008 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-17060-1789499809541088500.json` | F3 10 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-18464-1789500022553400300.json` | F3 9 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-20728-1789500539621797200.json` | F3 8 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-20812-1789500666296035500.json` | F3 35 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-22500-1789500584207636200.json` | F3 1 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-22836-1789499778478030500.json` | F3 10 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-25028-1789501221980191900.json` | F3 14 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-25764-1789501654888958300.json` | F3 224 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-25812-1789502420667570900.json` | F3 53 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-26128-1789500035030834200.json` | F3 10 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-26368-1789499973062923000.json` | F3 10 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-26660-1789499890935745300.json` | F3 8 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-27496-1789501654586764700.json` | F3 670 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-27624-1789500666067027800.json` | F3 3716 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-27940-1789500702441123000.json` | F3 12 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-28172-1789501653877098000.json` | F3 1916 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-28220-1789499855711586900.json` | F3 9 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-28740-1789501514169116900.json` | F3 16 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-29472-1789501654111965500.json` | F3 1378 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-29700-1789502473182401300.json` | F3 29 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-2976-1789500595411468200.json` | F3 19 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-29984-1789501687350806900.json` | F3 18 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-30040-1789501654337342500.json` | F3 806 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-30652-1789500746301809500.json` | F3 109 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-3240-1789502030102817700.json` | F3 431 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-3400-1789500870732447000.json` | F3 109 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-4988-1789500614706615500.json` | F3 2761 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-6476-1789501655190978500.json` | F3 1006 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/access_logs/access-6724-1789499996499124000.json` | F3 7 | `benchmark/producer_coverage_amendment_v3/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_ACCESS_AUDIT.json`; `benchmark/producer_coverage_amendment_v3/blind_evidence/PRE_GOLD_FREEZE.json`; `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/production_gate/validation.log` | F1 17 | `benchmark/producer_coverage_amendment_v3/release_freeze.json` |
| `benchmark/task_semantics/README.md` | F1 1 | `benchmark/task_semantics_v2/baseline_reference.json` |
| `benchmark/task_semantics_v2/README.md` | F1 2 | `benchmark/task_semantics_v2/freeze.json` |
| `docs/fix/ORDINARY_FINAL_CLOUD_RUN_PREPARATION.md` | F2 1 | `docs/fix/ordinary_final_cloud_run/READY_FOR_AUTHORIZATION.json` |
| `docs/fix/auditor_blocker_closure_run/admission_neutralized.log` | F1 1 | `docs/fix/auditor_blocker_closure_run/ADMISSION_VALIDATION.json`; `docs/fix/auditor_blocker_closure_run/EVIDENCE_MANIFEST.json` |
| `docs/fix/auditor_feature_blocker/gpu_row32_v2/probe.json` | F3 2 | `docs/fix/auditor_feature_blocker/evidence_manifest.json` |
| `docs/fix/auditor_feature_blocker/gpu_row32_v4/probe.json` | F3 2 | `docs/fix/auditor_feature_blocker/evidence_manifest.json` |
| `docs/fix/auditor_feature_blocker/gpu_rows30_33/probe.json` | F3 2 | `docs/fix/auditor_feature_blocker/evidence_manifest.json`; `docs/fix/auditor_feature_remote_run/downloaded/diagnostic_payload/comparison_provenance.json` |
| `docs/fix/auditor_feature_blocker/guard_neutralization.log` | F1 1 | `docs/fix/auditor_feature_blocker/evidence_manifest.json` |
| `docs/fix/auditor_optuna_hpo_run/downloaded/tuning/auditor_optuna_hpo/preparation_receipt.json` | F3 8 | `docs/fix/auditor_optuna_hpo_run/EVIDENCE_MANIFEST.json`; `docs/fix/auditor_optuna_hpo_run/downloaded/execution_manifest.json`; `docs/fix/auditor_optuna_hpo_run/downloaded/tuning/auditor_optuna_hpo/seal.json`; `docs/fix/auditor_optuna_hpo_run/execution_manifest.json`; `tuning/auditor_optuna_hpo/seal.json` |
| `docs/fix/contract_model_ab_20260915/LOCAL_GATES.json` | F3 1 | `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/catalog_proofs/historical_contract_ab.json`; `docs/fix/contract_model_ab_20260915/ARTIFACT_HASHES.json` |
| `docs/fix/contract_model_ab_20260915/local_source_preflight.json` | F3 1 | `benchmark/producer_coverage_amendment_v3/post_freeze/validation_evidence/catalog_proofs/historical_contract_ab.json`; `docs/fix/contract_model_ab_20260915/ARTIFACT_HASHES.json` |
| `docs/fix/remote_short_burst_retry_20260915/controller_executed.txt` | F2 1 | `docs/fix/remote_short_burst_retry_20260915/artifact_hashes.json`; `docs/fix/remote_short_burst_secure_20260915/historical_before.json` |
| `docs/fix/remote_short_burst_secure_20260915/LOCAL_GATES.json` | F3 1 | `docs/fix/remote_short_burst_secure_20260915/artifact_hashes.json` |
| `docs/fix/remote_short_burst_secure_20260915/local_source_preflight.json` | F3 1 | `docs/fix/remote_short_burst_secure_20260915/artifact_hashes.json` |
| `tools/auditor_blocker_closure_cloud.py` | F2 1 | `docs/fix/auditor_blocker_closure_run/EVIDENCE_MANIFEST.json`; `docs/fix/auditor_blocker_closure_run/execution_manifest.json` |
| `tools/auditor_final_retry_cloud.py` | F2 1 | `docs/fix/auditor_final_retry_run/execution_manifest.json` |
| `tools/checkpoint120_cloud.py` | F2 1 | `tuning/second_tuning_eval_runtime_v2_1/historical_preservation.json` |
| `tools/ordinary_final_cloud.py` | F2 1 | `docs/fix/ORDINARY_FINAL_V12_RUN_RESULTS.md`; `docs/fix/ordinary_final_cloud_run_v12/AUTHORIZED_LOCAL_REVERIFICATION.json`; `docs/fix/ordinary_final_cloud_run_v12/authorization_binding.json`; `docs/fix/ordinary_final_cloud_run_v12/execution_manifest.json` |
| `tools/run_first_real_tuning.py` | F2 1 | `docs/fix/first_real_tuning_20260916/EVIDENCE_HASHES.json` |
| `tuning/auditor_optuna_hpo/preparation_receipt.json` | F3 8 | `docs/fix/auditor_optuna_hpo_run/EVIDENCE_MANIFEST.json`; `docs/fix/auditor_optuna_hpo_run/downloaded/execution_manifest.json`; `docs/fix/auditor_optuna_hpo_run/downloaded/tuning/auditor_optuna_hpo/seal.json`; `docs/fix/auditor_optuna_hpo_run/execution_manifest.json`; `tuning/auditor_optuna_hpo/seal.json` |
| `tuning/second_tuning_eval_runtime_v2/source_evidence.json` | F3 4 | `docs/fix/producer_checkpoint120_eval_runtime_v2/downloaded/tuning/second_tuning_eval_runtime_v2/freeze.json`; `docs/fix/producer_checkpoint120_eval_v2_1/downloaded/tuning/second_tuning_eval_runtime_v2_1/freeze.json`; `docs/fix/producer_tuning_v3_run/downloaded/tuning/second_tuning_eval_runtime_v2_1/freeze.json`; `tuning/producer_v3/historical_preservation.json`; `tuning/second_tuning_eval_runtime_v2/freeze.json`; `tuning/second_tuning_eval_runtime_v2_1/freeze.json`; `tuning/second_tuning_eval_runtime_v2_1/historical_preservation.json` |

### (b) Code that reads the path at run time

| File | Forms (lines) | Reason |
|---|---|---|
| `tools/auditor_canonical_cloud.py` | F2 line 8 | code: path literal assigned to a module constant used at run time |
| `tools/auditor_classifier_lora_cloud.py` | F2 line 8 | code: path literal assigned to a module constant used at run time |
| `tools/auditor_classifier_lora_current_cloud.py` | F2 line 8 | code: path literal assigned to a module constant used at run time |
| `tools/auditor_classifier_lora_stabilized_cloud.py` | F2 line 8 | code: path literal assigned to a module constant used at run time |
| `tools/auditor_feature_cloud.py` | F2 line 8 | code: path literal assigned to a module constant used at run time |
| `tools/auditor_final_cloud.py` | F2 line 8 | code: path literal assigned to a module constant used at run time |
| `tools/auditor_linear_cloud.py` | F2 line 8 | code: path literal assigned to a module constant used at run time |
| `tools/auditor_optuna_hpo_cloud.py` | F2 line 8 | code: path literal assigned to a module constant used at run time |
| `tools/auditor_v2_cloud.py` | F2 line 8 | code: path literal assigned to a module constant used at run time |
| `tools/checkpoint120_v21_cloud.py` | F2 line 8 | code: path literal assigned to a module constant used at run time |
| `tools/ordinary_final_bound_preflight.py` | F2 line 18 | code: path literal assigned to a module constant used at run time |
| `tools/ordinary_final_rehearsal.py` | F4 line 49 | code: path literal assigned to a module constant used at run time |
| `tools/ordinary_final_status.py` | F2 line 21 | code: path literal assigned to a module constant used at run time |
| `tools/ordinary_final_v3_preflight.py` | F2 line 18 | code: path literal assigned to a module constant used at run time |
| `tools/producer_v3_cloud.py` | F2 line 8 | code: path literal assigned to a module constant used at run time |
| `tools/second_tuning_pilot.py` | F2 line 8 | code: path literal assigned to a module constant used at run time |

### (c) Generated logs and archives

| File | Forms (hits) | Reason |
|---|---|---|
| `docs/fix/ordinary_final_cloud_run/transfer_plan.json` | F3 2 | generated bundle transfer plan (model_cache_local / wheelhouse_local written by tools/prepare_ordinary_final_run.py, never read back) |
| `docs/fix/ordinary_final_cloud_run_v10/transfer_plan.json` | F3 2 | generated bundle transfer plan (model_cache_local / wheelhouse_local written by tools/prepare_ordinary_final_run.py, never read back) |
| `docs/fix/ordinary_final_cloud_run_v11/transfer_plan.json` | F3 2 | generated bundle transfer plan (model_cache_local / wheelhouse_local written by tools/prepare_ordinary_final_run.py, never read back) |
| `docs/fix/ordinary_final_cloud_run_v12/transfer_plan.json` | F3 2 | generated bundle transfer plan (model_cache_local / wheelhouse_local written by tools/prepare_ordinary_final_run.py, never read back) |
| `docs/fix/ordinary_final_cloud_run_v2/transfer_plan.json` | F3 2 | generated bundle transfer plan (model_cache_local / wheelhouse_local written by tools/prepare_ordinary_final_run.py, never read back) |
| `docs/fix/ordinary_final_cloud_run_v3/transfer_plan.json` | F3 2 | generated bundle transfer plan (model_cache_local / wheelhouse_local written by tools/prepare_ordinary_final_run.py, never read back) |
| `docs/fix/ordinary_final_cloud_run_v4/transfer_plan.json` | F3 2 | generated bundle transfer plan (model_cache_local / wheelhouse_local written by tools/prepare_ordinary_final_run.py, never read back) |
| `docs/fix/ordinary_final_cloud_run_v5/transfer_plan.json` | F3 2 | generated bundle transfer plan (model_cache_local / wheelhouse_local written by tools/prepare_ordinary_final_run.py, never read back) |
| `docs/fix/ordinary_final_cloud_run_v6/transfer_plan.json` | F3 2 | generated bundle transfer plan (model_cache_local / wheelhouse_local written by tools/prepare_ordinary_final_run.py, never read back) |
| `docs/fix/ordinary_final_cloud_run_v7/transfer_plan.json` | F3 2 | generated bundle transfer plan (model_cache_local / wheelhouse_local written by tools/prepare_ordinary_final_run.py, never read back) |
| `docs/fix/ordinary_final_cloud_run_v8/transfer_plan.json` | F3 2 | generated bundle transfer plan (model_cache_local / wheelhouse_local written by tools/prepare_ordinary_final_run.py, never read back) |
| `docs/fix/ordinary_final_cloud_run_v9/transfer_plan.json` | F3 2 | generated bundle transfer plan (model_cache_local / wheelhouse_local written by tools/prepare_ordinary_final_run.py, never read back) |
| `docs/fix/ordinary_final_decoding_fix/baseline_gate_at_HEAD.log` | F1 8, F5 3 | captured gate/test/console log |
| `docs/fix/ordinary_final_decoding_fix/decoding_tests.log` | F1 10 | captured gate/test/console log |
| `docs/fix/ordinary_final_decoding_fix/main_gate.log` | F1 13 | captured gate/test/console log |
| `docs/fix/ordinary_final_decoding_fix/main_gate_rerun.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_decoding_fix/startup_tests.log` | F1 7 | captured gate/test/console log |
| `docs/fix/ordinary_final_rehearsal/absent_root_workload.stderr.log` | F4 4 | captured gate/test/console log |
| `docs/fix/ordinary_final_rehearsal_v10/absent_root_workload.stderr.log` | F4 4 | captured gate/test/console log |
| `docs/fix/ordinary_final_rehearsal_v11/absent_root_workload.stderr.log` | F4 4 | captured gate/test/console log |
| `docs/fix/ordinary_final_rehearsal_v11/rehearsal.json` | F4 3 | generated rehearsal report (WSL NFS asset path) |
| `docs/fix/ordinary_final_rehearsal_v12/absent_root_workload.stderr.log` | F4 4 | captured gate/test/console log |
| `docs/fix/ordinary_final_rehearsal_v12/rehearsal.json` | F4 3 | generated rehearsal report (WSL NFS asset path) |
| `docs/fix/ordinary_final_rehearsal_v6/absent_root_workload.stderr.log` | F4 4 | captured gate/test/console log |
| `docs/fix/ordinary_final_rehearsal_v7/absent_root_workload.stderr.log` | F4 4 | captured gate/test/console log |
| `docs/fix/ordinary_final_rehearsal_v8/absent_root_workload.stderr.log` | F4 4 | captured gate/test/console log |
| `docs/fix/ordinary_final_rehearsal_v9/absent_root_workload.stderr.log` | F4 4 | captured gate/test/console log |
| `docs/fix/ordinary_final_startup_fix/startup_tests.log` | F1 7 | captured gate/test/console log |
| `docs/fix/ordinary_final_transport_fix/baseline_gate_at_9a421d0.log` | F1 15, F5 5 | captured gate/test/console log |
| `docs/fix/ordinary_final_transport_fix/controller_tests.log` | F1 3 | captured gate/test/console log |
| `docs/fix/ordinary_final_transport_fix/decoding_tests.log` | F1 10 | captured gate/test/console log |
| `docs/fix/ordinary_final_transport_fix/main_gate.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_transport_fix/startup_tests.log` | F1 7 | captured gate/test/console log |
| `docs/fix/ordinary_final_v10_gates/baseline_gate_at_b120c9a.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v10_gates/controller_tests.log` | F1 3 | captured gate/test/console log |
| `docs/fix/ordinary_final_v10_gates/decoding_gate.log` | F1 33 | captured gate/test/console log |
| `docs/fix/ordinary_final_v10_gates/decoding_tests.log` | F1 10 | captured gate/test/console log |
| `docs/fix/ordinary_final_v10_gates/main_gate.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v10_gates/startup_tests.log` | F1 7 | captured gate/test/console log |
| `docs/fix/ordinary_final_v11_gates/baseline_gate_at_5479ced.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v11_gates/controller_tests.log` | F1 3 | captured gate/test/console log |
| `docs/fix/ordinary_final_v11_gates/decoding_gate.log` | F1 33 | captured gate/test/console log |
| `docs/fix/ordinary_final_v11_gates/decoding_tests.log` | F1 10 | captured gate/test/console log |
| `docs/fix/ordinary_final_v11_gates/main_gate.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v11_gates/startup_tests.log` | F1 7 | captured gate/test/console log |
| `docs/fix/ordinary_final_v12_gates/baseline_gate_at_a867a99.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v12_gates/controller_tests.log` | F1 4 | captured gate/test/console log |
| `docs/fix/ordinary_final_v12_gates/decoding_gate.log` | F1 33 | captured gate/test/console log |
| `docs/fix/ordinary_final_v12_gates/decoding_tests.log` | F1 10 | captured gate/test/console log |
| `docs/fix/ordinary_final_v12_gates/main_gate.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v12_gates/main_gate_first_run.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v12_gates/startup_tests.log` | F1 7 | captured gate/test/console log |
| `docs/fix/ordinary_final_v13_gates/baseline_gate_at_dc638c9.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v13_gates/controller_tests.log` | F1 24 | captured gate/test/console log |
| `docs/fix/ordinary_final_v13_gates/decoding_gate.log` | F1 33 | captured gate/test/console log |
| `docs/fix/ordinary_final_v13_gates/decoding_tests.log` | F1 10 | captured gate/test/console log |
| `docs/fix/ordinary_final_v13_gates/main_gate.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v13_gates/progress_gate.log` | F1 2 | captured gate/test/console log |
| `docs/fix/ordinary_final_v13_gates/startup_tests.log` | F1 7 | captured gate/test/console log |
| `docs/fix/ordinary_final_v5_gates/baseline_gate_at_287a2a1.log` | F1 8, F5 3 | captured gate/test/console log |
| `docs/fix/ordinary_final_v5_gates/controller_tests.log` | F1 3 | captured gate/test/console log |
| `docs/fix/ordinary_final_v5_gates/decoding_tests.log` | F1 10 | captured gate/test/console log |
| `docs/fix/ordinary_final_v5_gates/main_gate.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v5_gates/startup_tests.log` | F1 7 | captured gate/test/console log |
| `docs/fix/ordinary_final_v6_gates/baseline_gate_at_e50a1cc.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v6_gates/controller_tests.log` | F1 3 | captured gate/test/console log |
| `docs/fix/ordinary_final_v6_gates/decoding_gate.log` | F1 33 | captured gate/test/console log |
| `docs/fix/ordinary_final_v6_gates/decoding_tests.log` | F1 10 | captured gate/test/console log |
| `docs/fix/ordinary_final_v6_gates/main_gate.log` | F1 11 | captured gate/test/console log |
| `docs/fix/ordinary_final_v6_gates/startup_tests.log` | F1 7 | captured gate/test/console log |
| `docs/fix/ordinary_final_v7_gates/baseline_gate_at_a8f752e.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v7_gates/controller_tests.log` | F1 3 | captured gate/test/console log |
| `docs/fix/ordinary_final_v7_gates/decoding_gate.log` | F1 33 | captured gate/test/console log |
| `docs/fix/ordinary_final_v7_gates/decoding_tests.log` | F1 10 | captured gate/test/console log |
| `docs/fix/ordinary_final_v7_gates/main_gate.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v7_gates/startup_tests.log` | F1 7 | captured gate/test/console log |
| `docs/fix/ordinary_final_v8_gates/baseline_gate_at_445550d.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v8_gates/controller_tests.log` | F1 3 | captured gate/test/console log |
| `docs/fix/ordinary_final_v8_gates/decoding_gate.log` | F1 33 | captured gate/test/console log |
| `docs/fix/ordinary_final_v8_gates/decoding_tests.log` | F1 10 | captured gate/test/console log |
| `docs/fix/ordinary_final_v8_gates/main_gate.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v8_gates/startup_tests.log` | F1 7 | captured gate/test/console log |
| `docs/fix/ordinary_final_v9_gates/baseline_gate_at_037db5b.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v9_gates/controller_tests.log` | F1 3 | captured gate/test/console log |
| `docs/fix/ordinary_final_v9_gates/decoding_gate.log` | F1 33 | captured gate/test/console log |
| `docs/fix/ordinary_final_v9_gates/decoding_tests.log` | F1 10 | captured gate/test/console log |
| `docs/fix/ordinary_final_v9_gates/main_gate.log` | F1 8 | captured gate/test/console log |
| `docs/fix/ordinary_final_v9_gates/startup_tests.log` | F1 7 | captured gate/test/console log |
| `docs/fix/report_recommendations/local_inference/local_validation_auditor_probe.json` | F3 4 | generated json/txt evidence (probe, preflight, receipt, captured controller) |
| `docs/fix/report_recommendations/local_inference/local_validation_auditor_retry_probe.json` | F3 4 | generated json/txt evidence (probe, preflight, receipt, captured controller) |
| `docs/fix/report_recommendations/local_inference/local_validation_probe.json` | F3 4 | generated json/txt evidence (probe, preflight, receipt, captured controller) |
| `docs/fix/runtime_hardening_20260915/source_preflight.json` | F3 1 | generated json/txt evidence (probe, preflight, receipt, captured controller) |
| `docs/fix/runtime_hardening_20260915/validation.json` | F3 1 | generated json/txt evidence (probe, preflight, receipt, captured controller) |

### (d) Prose

| File | Forms (hits) | Reason |
|---|---|---|
| `docs/fix/LEDGER.md` | F1 2 | prose documentation (report/ledger/handoff) quoting a local path |
| `docs/fix/SESSION_HANDOFF.md` | F1 3 | prose documentation (report/ledger/handoff) quoting a local path |
| `docs/fix/STEP_DOCKER_REPORT.md` | F1 1 | prose documentation (report/ledger/handoff) quoting a local path |
| `docs/fix/STEP_W7_REPORT.md` | F1 1 | prose documentation (report/ledger/handoff) quoting a local path |

## 3. What replacing a path with `<USER_HOME>` would break, per class

- **(a)** The file no longer matches its binding record, so every tool that recomputes those hashes (the benchmark integrity scripts, the reverify tools, the tuning release and verify steps) reports a change. Updating a record's hash changes that record, so the records that hash it change in turn. For `tools/ordinary_final_cloud.py`, the controller binding refuses the old sealed bundles. S13 leaves these files as they are, with a note that they describe pre-rewrite content and can be checked against the private backup bundle.
- **(b)** Nothing expands `<USER_HOME>`, so a tool would look for a file or folder literally named so: the credential file would not be found, and the rehearsal would create, mount into and remove a folder of that literal name. Loop stage S1 Part 3 removed the path from the live tools at the current tip (they now resolve it at run time); the frozen tools keep it, and in old commits the rewrite turns it into the literal placeholder text.
- **(c)** Nothing runs these files; the evidence no longer matches the bytes captured at the time.
- **(d)** Nothing breaks.

## 4. History

Scope: git log --all (283 commits; branches api, console, docker, lane/s01-credential, lane/s01-replies, loop/2026-10-27, loop/s01, main, night-2026-09-11 and origin/*; tags loop-base, loop-s00-v1-open).

| Label | Commits that added or changed it | Hits added | Hits removed |
|---|---|---|---|
| F1 | 32 | 765 | 7 |
| F2 | 24 | 23 | 5 |
| F3 | 22 | 14608 | 0 |
| F4 | 9 | 39 | 1 |
| F5 | 3 | 11 | 0 |
| F6 | 0 | 0 | 0 |
| F7 | 0 | 0 | 0 |
| F8 | 0 | 0 | 0 |

Per form, the commits (short hash, date, hits added and removed):

- **F1:** `939da2c` 2026-09-19 +2/-0; `88e9ba2` 2026-09-19 +90/-0; `00f0cba` 2026-09-19 +78/-0; `15ce9f4` 2026-09-18 +69/-0; `bd1fc2e` 2026-09-18 +69/-0; `a687b56` 2026-09-18 +69/-0; `037db5b` 2026-09-18 +69/-0; `205bbb3` 2026-09-18 +69/-0; `a387a83` 2026-09-18 +72/-0; `fbfc6f8` 2026-09-18 +36/-0; `e89ebf0` 2026-09-18 +3/-2; `a7bdd96` 2026-09-18 +40/-0; `5c695d5` 2026-09-18 +2/-0; `57fc0b2` 2026-09-18 +36/-0; `8d46fe9` 2026-09-18 +10/-0; `eb71e6b` 2026-09-18 +7/-0; `04cdb02` 2026-09-17 +1/-0; `459d694` 2026-09-17 +1/-0; `a4e369f` 2026-09-15 +17/-0; `6ff6f07` 2026-09-15 +1/-0; `0114f66` 2026-09-15 +1/-0; `5f9be7a` 2026-09-15 +1/-0; `befb468` 2026-09-15 +3/-0; `4d7645d` 2026-09-15 +4/-0; `fee042a` 2026-09-15 +2/-0; `090b3d5` 2026-09-15 +1/-0; `f3e8424` 2026-09-15 +0/-2; `5b72b16` 2026-09-13 +2/-3; `83866c9` 2026-09-13 +5/-0; `d1aca5c` 2026-09-11 +3/-0; `a3c666f` 2026-09-11 +1/-0; `8b1c30e` 2026-09-11 +1/-0
- **F2:** `4c1efb1` 2026-10-27 +0/-4; `74aa488` 2026-09-18 +2/-0; `c158131` 2026-09-18 +1/-0; `20d553a` 2026-09-18 +1/-0; `776d8c1` 2026-09-17 +1/-0; `c9c2380` 2026-09-17 +1/-0; `f5a6c00` 2026-09-17 +1/-0; `f8dbcd1` 2026-09-17 +1/-0; `b4f7e82` 2026-09-17 +1/-0; `b15a902` 2026-09-17 +1/-0; `ceabb0a` 2026-09-17 +1/-0; `23f6271` 2026-09-17 +1/-0; `550b914` 2026-09-17 +1/-0; `12a08e8` 2026-09-17 +1/-0; `05ce2a0` 2026-09-16 +1/-0; `3dd892d` 2026-09-16 +1/-0; `668a9fa` 2026-09-16 +1/-0; `539ca0c` 2026-09-16 +1/-0; `bee77af` 2026-09-16 +1/-0; `a818d43` 2026-09-16 +1/-0; `e65324c` 2026-09-16 +1/-0; `2a01407` 2026-09-15 +1/-0; `83866c9` 2026-09-13 +0/-1; `963cae2` 2026-09-12 +1/-0
- **F3:** `03a1e1d` 2026-09-19 +2/-0; `dc638c9` 2026-09-19 +2/-0; `a867a99` 2026-09-19 +2/-0; `fa0234f` 2026-09-18 +2/-0; `e0d5e0d` 2026-09-18 +2/-0; `4291ccf` 2026-09-18 +2/-0; `92cf995` 2026-09-18 +2/-0; `a8583ef` 2026-09-18 +2/-0; `68b8eb5` 2026-09-18 +2/-0; `8d46fe9` 2026-09-18 +2/-0; `eb71e6b` 2026-09-18 +2/-0; `776d8c1` 2026-09-17 +2/-0; `459d694` 2026-09-17 +6/-0; `b15a902` 2026-09-17 +8/-0; `d00a136` 2026-09-17 +8/-0; `67be2d5` 2026-09-16 +4/-0; `a4e369f` 2026-09-15 +14440/-0; `aad0ec0` 2026-09-15 +100/-0; `8752da6` 2026-09-15 +2/-0; `1aa4696` 2026-09-15 +2/-0; `60a55af` 2026-09-15 +2/-0; `c514d5b` 2026-09-15 +12/-0
- **F4:** `4c1efb1` 2026-10-27 +0/-1; `03a1e1d` 2026-09-19 +7/-0; `dc638c9` 2026-09-19 +7/-0; `a867a99` 2026-09-19 +4/-0; `fa0234f` 2026-09-18 +4/-0; `e0d5e0d` 2026-09-18 +4/-0; `4291ccf` 2026-09-18 +4/-0; `92cf995` 2026-09-18 +4/-0; `e89ebf0` 2026-09-18 +5/-0
- **F5:** `fbfc6f8` 2026-09-18 +3/-0; `a7bdd96` 2026-09-18 +5/-0; `57fc0b2` 2026-09-18 +3/-0

- **Commit and tag messages:** 283 commit messages and 2 tag messages searched; no form in any of them.
- **File and folder names in history:** 9968 unique paths and 456 folders; no form in any name.
- **The collaborator's project name** (searched only with the hex pattern, counts and file names only): 0 path names, 0 commit-message lines, 0 tag-message lines; at the starting commit, 2 files (`docs/fix/SESSION_HANDOFF.md`, `docs/fix/WORDS_D_INVENTORY.md`), both changed in S1 commit C1. It stays in history until S13.

### Binary and compressed files in history (input for S13 step 4)

Counts by type: docx 5, npy 4, pkl 5, png 14, safetensors 2, tar.gz 11, zip 5 (46 paths, all still tracked at the starting commit).

- **docx:** `docs/fix/ordinary_final_cloud_run_v5/downloaded/evidence/run/deliverables/result_sheet/tracked_changes.docx`, `docs/fix/ordinary_final_cloud_run_v6/downloaded/evidence/run/deliverables/result_sheet/tracked_changes.docx`, `docs/fix/ordinary_final_cloud_run_v7/downloaded/evidence/run/deliverables/result_sheet/tracked_changes.docx`, `docs/fix/ordinary_final_cloud_run_v8/downloaded/evidence/run/deliverables/result_sheet/tracked_changes.docx`, `docs/fix/ordinary_final_cloud_run_v9/downloaded/evidence/run/deliverables/result_sheet/tracked_changes.docx`
- **npy:** `tuning/auditor_optuna_hpo/clean_initialization/hpo_mean.npy`, `tuning/auditor_optuna_hpo/clean_initialization/hpo_std.npy`, `tuning/auditor_optuna_hpo/clean_initialization/repeat_verification/hpo_mean.npy`, `tuning/auditor_optuna_hpo/clean_initialization/repeat_verification/hpo_std.npy`
- **pkl:** `docs/fix/ordinary_final_cloud_run_v5/downloaded/project/durable/cache/embedding_store.pkl`, `docs/fix/ordinary_final_cloud_run_v6/downloaded/project/durable/cache/embedding_store.pkl`, `docs/fix/ordinary_final_cloud_run_v7/downloaded/project/durable/cache/embedding_store.pkl`, `docs/fix/ordinary_final_cloud_run_v8/downloaded/project/durable/cache/embedding_store.pkl`, `docs/fix/ordinary_final_cloud_run_v9/downloaded/project/durable/cache/embedding_store.pkl`
- **png:** `docs/fix/console_audit_shots/agents_developer.png`, `docs/fix/console_audit_shots/agents_human.png`, `docs/fix/console_audit_shots/ontology_sections_developer.png`, `docs/fix/console_audit_shots/ontology_sections_human.png`, `docs/fix/console_audit_shots/run_findings_developer.png`, `docs/fix/console_audit_shots/run_findings_human.png`, `docs/fix/console_audit_shots/runs_developer.png`, `docs/fix/console_audit_shots/runs_human.png`, `docs/fix/w8_screenshots/agents_developer.png`, `docs/fix/w8_screenshots/agents_human.png`, `docs/fix/w8_screenshots/run_findings_developer.png`, `docs/fix/w8_screenshots/run_findings_human.png`, `docs/fix/w8_screenshots/runs_developer.png`, `docs/fix/w8_screenshots/runs_human.png`
- **safetensors:** `tuning/auditor_optuna_hpo/clean_initialization/hpo_head-200.safetensors`, `tuning/auditor_optuna_hpo/clean_initialization/repeat_verification/hpo_head-200.safetensors`
- **tar.gz:** `docs/fix/contract_model_ab_20260915/evidence.tar.gz`, `docs/fix/contract_model_ab_20260915/source.tar.gz`, `docs/fix/ordinary_final_cloud_run_v3/collected_evidence.tar.gz`, `docs/fix/ordinary_final_cloud_run_v4/collected_evidence.tar.gz`, `docs/fix/ordinary_final_cloud_run_v5/collected_evidence.tar.gz`, `docs/fix/ordinary_final_cloud_run_v6/collected_evidence.tar.gz`, `docs/fix/ordinary_final_cloud_run_v7/collected_evidence.tar.gz`, `docs/fix/ordinary_final_cloud_run_v8/collected_evidence.tar.gz`, `docs/fix/ordinary_final_cloud_run_v9/collected_evidence.tar.gz`, `docs/fix/producer_checkpoint120_eval_runtime_v2/evidence.tar.gz`, `docs/fix/producer_checkpoint120_eval_v2_1/evidence.tar.gz`
- **zip:** `benchmark/first_tuning_experiment_v1/reviewer_1_first_tuning_v1.zip`, `benchmark/first_tuning_experiment_v1/reviewer_2_first_tuning_v1.zip`, `benchmark/first_tuning_review_cohort_v2/reviewer_1_first_tuning_v1_cohort_v2.zip`, `benchmark/first_tuning_review_cohort_v2/reviewer_2_first_tuning_v1_cohort_v2.zip`, `tuning/first_domain_agnostic_v1/training_bundle.zip`

## 5. Recount in the tree that S1 commit C5 commits

Counted in the git index of S1 commit C5 (after C1 to C4 were merged; `loop/s01` at `7f5dd9d` plus this inventory and the multi-round readiness report, neither of which carries a form):

| Label | Files at the starting commit | Hits at the starting commit | Files at C5 | Hits at C5 |
|---|---|---|---|---|
| F1 | 81 | 758 | 81 | 758 |
| F2 | 22 | 22 | 18 | 18 |
| F3 | 72 | 14608 | 72 | 14608 |
| F4 | 11 | 39 | 10 | 38 |
| F5 | 3 | 11 | 3 | 11 |
| F6, F7, F8 | 0 | 0 | 0 | 0 |
| **Union** | **186** | **15438** | **181** | **15433** |

The difference is S1 Part 3 (commit C2): the four live controller tools no longer hard-code the credential path (four F2 hits) and the rehearsal no longer hard-codes its Linux folder (one F4 hit). Every other file is unchanged; the history rewrite (S13) handles the rest.

