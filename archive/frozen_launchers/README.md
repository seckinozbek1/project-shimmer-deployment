# Frozen launchers (retired)

These are the sixteen tuning and evaluation launchers that lived in `tools/` until the
operator's decision D-S13 item 2 (30 October 2026) retired them, closing open item 20
(`docs/fix/OPEN_ITEMS.md`, issue #25):

`auditor_blocker_closure_cloud`, `auditor_canonical_cloud`, `auditor_classifier_lora_cloud`,
`auditor_classifier_lora_current_cloud`, `auditor_classifier_lora_stabilized_cloud`,
`auditor_feature_cloud`, `auditor_final_cloud`, `auditor_final_retry_cloud`,
`auditor_linear_cloud`, `auditor_optuna_hpo_cloud`, `auditor_v2_cloud`,
`checkpoint120_cloud`, `checkpoint120_v21_cloud`, `producer_v3_cloud`,
`run_first_real_tuning`, `second_tuning_pilot`.

Each one launched a single past cloud run of Producer or Auditor tuning or evaluation. It
sent its launch request through the provider adapter without the loop budget guard
(`tools/loop_budget_guard.py`) or the general cloud path's refusals, and named its instance
without the `shimmer-loop-` prefix, so the instance reaper would not end one. Nothing live
called any of them: no gate check, no script under `scripts/`, no loop tool, the container
or a document outside the run records.

Nineteen companions moved with them, because each imports a launcher or reads a launcher's
source, directly or through another companion, and would otherwise point at a moved file:
the run preparers (`auditor_canonical_prepare`, `auditor_classifier_lora_prepare`,
`auditor_classifier_lora_current_prepare`, `auditor_classifier_lora_stabilized_prepare`,
`auditor_linear_prepare`, `auditor_v2_prepare`, `prepare_auditor_blocker_closure`,
`prepare_auditor_final`, `prepare_auditor_final_retry`, `prepare_auditor_optuna_hpo_launch`),
their local tests (`test_auditor_blocker_closure`, `test_auditor_classifier_lora_stabilized`,
`test_auditor_feature_remote`, `test_auditor_final_retry`, `test_auditor_feature_diagnostics`,
`test_auditor_feature_admission`), `auditor_linear_local`, `analyze_auditor_linear` and
`validate_auditor_feature_admission`.

Every file was moved with `git mv` and its bytes are unchanged, so each SHA-256 recorded for
it under `docs/fix/` and `tuning/` still holds; only the path is new (`tools/<name>.py` in
those records is `archive/frozen_launchers/<name>.py` here). The records under `docs/fix/`
are kept exactly as they were. `.gitattributes` here carries the attributes the files had in
`tools/`, so a checkout keeps their bytes.

They are kept for the record, not to be run. From this folder a launcher cannot import the
provider adapter (it found `lambda_experiment_provider` beside itself in `tools/`), and its
`ROOT` (`Path(__file__).resolve().parents[1]`) now names `archive/`, so its own refusal on
an existing `docs/fix/<run>/LAUNCH_INTENT.json` would no longer find that record. A cloud
launch goes through the loop's controller and its budget guard.
