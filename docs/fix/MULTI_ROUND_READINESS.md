# Multi-round readiness: what stops the first real multi-round run, and what must change

Written 2026-10-27 in loop stage S1 Part 6, from a read-only trace of the code at commit `f31eff4` (the loop's starting point). It changes no code. It is the design input for loop stage S2 (multi-round enablement and the run controller). Line numbers are from that commit and are approximate ("around").

**Terms.** A *multi-round run* reviews two or more versions of a document set in order (rounds), declared in a *case manifest*. The *controller* is the operator-side tool that rents a GPU instance, uploads the sealed bundle, runs the pipeline and collects the evidence (`tools/ordinary_final_cloud.py` and the tools around it). A *seal* is the record of hashes that binds a run to exactly the code, settings and files it was prepared with. *Exposed* means the builder has seen the test; *sealed* means it has not.

## 1. Every guard that refuses or disables multi-round

**In the pipeline (`scripts/`):**

- `scripts/pipeline.py` around 4117 to 4119: in final model mode, `--multi-round`, `--multi-round-manifest` or any task other than Review stops the run ("Frozen final models are limited to ordinary Review"). This is the main blocker: every sealed bundle sets `SHIMMER_MODEL_MODE=final` (`tools/prepare_ordinary_final_run.py` around 200). It was missing from the earlier list of known guards.
- `scripts/execution_topology.py` around 244 to 245: any topology other than `reference_serial` is refused for multi-round ("multi-round remains separately gated"). Sealed runs use `report_optimized` (`tools/ordinary_final_run.py` around 84). Also missing from the earlier list.
- `scripts/pipeline.py` around 4186 to 4190: a run stops (exit 8) unless both override flags are given; sealed flags carry both.
- `scripts/pipeline.py` around 4444 to 4448 and `scripts/multi_round_phase.py` around 44: multi-round refuses when redaction is on (`sensitive_multi_round_unavailable`).
- `scripts/multi_round_phase.py` around 46: a fixture manifest is refused (section 4).
- `scripts/multi_round_phase.py` around 56 to 57 and `scripts/strategic_support.py` around 152: PROCESSOR and VERIFIER must not share a backend or model. The local profile passes (Qwen2.5-7B on the producer backend, Phi-3.5-mini on the auditor backend; `pipeline.py` around 437 and 448).
- `scripts/pipeline.py` around 4132 to 4137: the task must be Review and the manifest valid.

**In the controller and seal (`tools/`):**

- `tools/ordinary_final_run.py`: around 60 (`max_runs == 1` and final mode), around 61 (`multi_round is False and protected_test is False`, "Excluded workload"), around 62 (run flags must equal the sealed list exactly; that list, around 81 to 86, has no `--multi-round`).
- `tools/prepare_ordinary_final_run.py`: around 177 seals `multi_round=False, protected_test=False`; around 206 the restriction "no multi-round"; around 220 excludes "multi-round data" from the transfer plan.
- `tools/ordinary_final_bound_cloud.py` around 34 and `tools/ordinary_final_v3_cloud.py` around 38: require `multi_round is False` and `max_runs == 1`.
- `tools/ordinary_final_cloud.py` around 312: writes `multi_round=False` into the authorization.
- `tools/prepare_cloud_run.py` (the older cloud path, used through `tools/cloud_run_checks.py` and `tools/run_remote_experiment.py`, not the ordinary final path): around 129 requires multi-round inactive; around 131 to 139 finds the three top-level multi-round branches in pipeline `main`, requires none taken and exactly three ("guard contract drift"); around 152 requires `--multi-round` to be refused; around 165 records `multi_round_inactive`.

**The `protected_test` refusal** appears only in `tools/ordinary_final_run.py` around 61, `tools/prepare_ordinary_final_run.py` around 177 and `tools/ordinary_final_preparation_checks.py` around 22 and 48. Nothing in `scripts/` reads it.

**Tests that expect these refusals** and would flip when a guard changes: `tools/ordinary_final_preparation_checks.py` around 48 and 67; `scripts/execution_topology_checks.py` around 416, 478 and 480.

**Places that only record "no multi-round"**: `tools/analyze_ordinary_final_run.py` around 75, `tools/cloud_run_observer.py` around 396 and 411, `tools/ordinary_final_startup_gate.py` around 50, `scripts/final_integration_no_generation_gate.py` around 114, `tools/prepare_remote_experiment.py` around 30 and 68, `tools/run_remote_experiment.py` around 101.

## 2. Controller and seal changes for one sealed multi-round run (design only)

The run uses open-weight models on a rented GPU and no paid provider.

1. **Model mode.** Either (a) the base models, which needs no pipeline change but is refused by `ordinary_final_run.py` around 60 and 64 and by its `assess` (around 118, which expects the adapter checkpoint's telemetry); or (b) the frozen adapters, by letting final mode admit `--multi-round` for Review at `pipeline.py` around 4118. Option (b) changes `main`'s pinned code hash (point 6).
2. **Topology.** Seal the multi-round flags with `--execution-topology reference_serial` and no `--topology-config`; the alternative, widening `execution_topology.py` around 244, needs its own proof.
3. **Run flags.** A second sealed flag list for multi-round (the ordinary flags plus `--multi-round --multi-round-manifest <bundle>/case_manifest.json`). The exact-match check at `ordinary_final_run.py` around 62 compares against the list the manifest's workload kind names; the exact-match rule stays.
4. **Manifest and seal.** At `prepare_ordinary_final_run.py` around 177 seal `multi_round=True` with a `case_manifest_sha256`, and `protected_test=False` for an exposed case. The case documents are injected into `input/context/` (around 112 to 119) and the case manifest becomes a hashed support file (around 163 to 167). The restriction (around 206) and the exclusion (around 220) are reworded. The three hard refusals (`ordinary_final_run.py` around 61, `ordinary_final_bound_cloud.py` around 34, `ordinary_final_cloud.py` around 312) become "equals the sealed value", so a bundle can never claim more than it was sealed with.
5. **Assessment.** `assess` (`ordinary_final_run.py` around 111 to 133) knows only ordinary events. A multi-round assessment reads `audit/multi_round.json` through `multi_round.read_saved`, passes only when the outcome is `reviewed` and the activation is `activated`, and `analyze_ordinary_final_run.py` around 75 reports the true value.
6. **Gate check 261 and the "exactly three guards" rule.** Check 261 (`scripts/multi_round_checks.py` around 208 to 229) strips exactly five named statements from `main` (two assignments and three `if` branches) and two parser flags, then compares every pipeline function's code hash with `benchmark/fixtures/multi_round_baseline_contract.json`. Changing `pipeline.py` around 4118 (inside the final-mode block, not stripped) changes `main`'s hash, which is recorded as a pinned-baseline amendment in that file and in `benchmark/fixtures/topology_reference_contract.json`. Adding a fourth top-level branch that uses one of the three stripped tests would break both check 261 (it asserts five) and `prepare_cloud_run.py` around 139 (it asserts three); any new branch must use a different test or sit inside an existing branch. The preferred design leaves the five stripped statements as they are.
7. **Budget and instance type.** See section 8.

## 3. Run output outside the repository (design only)

Today the bundle and its evidence live under `docs/fix/ordinary_final_cloud_run*`. What would change:

- `tools/prepare_ordinary_final_run.py`: around 18 the default output folder; around 87 to 88 it copies `runtime.candidate.lock` and `provider_inventory.json` from that folder (make the source a parameter); `--output-dir` (around 226) already accepts any path; around 76 the asset archive is reused by hard link, which works only on the same drive (otherwise copy and re-hash).
- `tools/ordinary_final_cloud.py` around 21 (bundle folder; the bound wrapper already overrides it) and around 180 and 359 (the asset archive is read relative to the repository root); `tools/ordinary_final_bound_cloud.py` around 44 writes that path relative to the root, which fails for an outside bundle. Store it relative to the bundle instead.
- `tools/analyze_ordinary_final_run.py` around 13 hard-codes the folder: add a bundle argument.
- `tools/ordinary_final_bound_reverify.py` around 64 to 68 accepts generated files only under `input/` or `docs/fix/` and requires that HEAD moved only under `docs/fix/`: retarget.
- The controller's own hashes stay relative to the repository root: they pin the controller, not the output.
- A run root resolved like the credential path: an environment variable, then a sibling folder outside the repository, and a refusal of any root inside the repository; only a hash summary is committed back.

## 4. The live case manifest, and why the fixture is refused

The rules (`scripts/multi_round.py` around 53 to 83; `scripts/strategic_support.py` around 13 to 18):

- `schema_version`: 1. `case_id`: an identifier of letters, digits, `_`, `-` and `.`, at most 128 characters. `fixture`: true or false, and false for a live run.
- Optional `allow_recommendations` (default false) and `decision_support_mode` (`trajectory_only` by default; `decision_support`, `strategic_options`, or `recommendation`, which needs `allow_recommendations: true`).
- `rounds`: at least two, each with a unique `round_id` and a unique whole-number `sequence` from 1 to 10000; `document_ids` are valid identifiers and no document belongs to two rounds.
- `actors` and `issues`: at least one each, unique ids.
- `sources`: each names an existing round, actor and issue; its `document_id` belongs to that round; it has a valid `unit_id`; `0 <= char_start < char_end`; a non-empty `quote`; an allowed `state`.
- At run time `bind_sources` (around 123 to 140) requires the quote to equal the document text between `char_start` and `char_end` exactly. Document text comes from `input/context/` (`pipeline.py` around 4461) and a document's id is its file name without extension (around 644 to 674), so spans are measured on the bundled bytes (line endings normalised to LF at preparation, around 115).

**Why the fixture is refused.** `scripts/multi_round_phase.py` around 46 requires `not manifest["fixture"]` ("fixture_requires_offline_test_adapter"). The fixture (`benchmark/fixtures/multi_round_fixture.json`) holds synthetic source spans and pre-authored producer and reviewer outputs, labelled "SYNTHETIC, PRE-AUTHORED SEMANTIC OUTPUTS. NOT MODEL QUALITY EVIDENCE"; its documents live inside the fixture file, not in `input/context/`; and the bundle builder drops `/fixtures/` and `benchmark/` (`prepare_ordinary_final_run.py` around 31 and 111). A live run with pre-authored outputs would measure nothing (`docs/fix/MULTI_ROUND_IMPLEMENTATION.md` around 123 to 126).

## 5. Material that could feed an exposed case, and what stops it

- The anonymised negotiation corpora (Company A and Union B) under `benchmark/corpora/negotiation_r2_to_r3/` and `benchmark/corpora/negotiation_r3_to_r4/` hold three dated company offers whose file names are valid document ids. The local copies of that corpus elsewhere on this laptop carry real party names in their file names; those are never used, published or uploaded (Annex A, 11.13), and only the anonymised versions in `benchmark/corpora/` may be used.
- What stops it today: no case manifest exists (actors, issues and exact spans must be written); the union's positions are thin in this material; the corpus has known weaknesses (one author wrote the labels in both documents, the mandate and the key; two of the nineteen recorded comparisons are false; `docs/test_change_requests.md` TCR-001 and TCR-002); there is no multi-round answer key; and it is builder-seen, so it can only ever be an exposed development case, never a sealed test. The guards in section 1 also apply.
- A synthetic multi-round case written from the published input format (loop stage S3, generator family 4) is the other candidate, and is exposed by construction.

## 6. Will every model reply in a multi-round run be saved?

Answered after loop stage S1 Part 4 (the reply write path) was merged (commit `f8d0087`): **yes, by the code path; not yet proven by an executed multi-round test.**

- The multi-round phase gets its wrappers from the pipeline's own factory (`pipeline.py` around 4470: `lambda name: _build_wrapper(name, orch, keys)`), and `_build_wrapper` (around 1052 to 1072) passes the run's `run_context` and its `sensitive` flag to every wrapper.
- Every multi-round model call goes through `wrapper.run_task` (`scripts/multi_round_phase.py` around 27, with `items_are_advisory=True`; the strategic layer uses the same factory), and `run_task` reaches a backend function through `dispatch`. Each backend function now writes exactly one record into `<run_dir>/audit/model_replies/` before returning (`scripts/reply_records.py`, gate check 276).
- The outcome of each multi-round reply is `advisory_not_record`, because the phase marks its items advisory.
- A multi-round run with redaction enabled is refused before any wrapper is built (`multi_round_phase.py` around 44), so multi-round records always carry text.
- What is not yet shown: an executed multi-round run, mocked, in which every reply produces exactly one record. Loop stage S2b item 4 adds that proof.

## 7. Decisions before the run

Each is classified by the loop's decision profile (Part III.2 of the loop spec). Class R decisions are taken by the loop and recorded in `docs/loop/DECISIONS.md` (D-011); none of these is Class S.

1. Frozen adapters or base models: the frozen adapters (final mode admits a declared multi-round Review), so the run measures the models every other sealed run uses.
2. Whether the Producer and Auditor checkpoints suit the multi-round contracts (`config/multi_round_contracts.json`, never trained on): measured in the first development run, not assumed.
3. Topology: `reference_serial` for multi-round; `execution_topology.py` is not widened.
4. Case material: the synthetic multi-round case from loop stage S3 and, if a manifest can be written, the anonymised negotiation material, both as exposed development cases.
5. Who writes the case manifest: the builder, for an exposed development case (Annex B.1); a sealed case is written by role B only.
6. Decision-support mode: `trajectory_only`, recommendations off.
7. `protected_test` stays false for exposed cases; only a sealed bundle prepared by role B may set it.
8. Output location: outside the repository for sealed runs (loop stage S2c item 1); development runs may keep the default.
9. Rate cap, soft and hard caps, per-run cap: from the live price and the loop's budget formula, set in the manifest (section 8).
10. Fallback instance types and regions: the loop's type rule (another single-GPU type only at no more than twice the A10's price, with enough memory).
11. What counts as a pass: outcome `reviewed` and activation `activated` for run health; quality is reported separately and never called a pass.
12. The pinned-baseline amendments that decisions 1 and 3 need: recorded through the loop's pinned-baseline path, never hidden.

## 8. Hard-coded values that must become manifest parameters (design only)

- **Instance type `gpu_1x_a10`:** `tools/ordinary_final_cloud.py` around 190, 301 and 310; `tools/ordinary_final_run.py` around 100; `tools/ordinary_final_bound_preflight.py` around 30 to 31; `tools/prepare_ordinary_final_run.py` around 170; `tools/ordinary_final_v3_preflight.py` around 29 to 30. The hardware check at `ordinary_final_run.py` around 186 to 188 also requires an A10 with at least 23 GB of GPU memory, 30 CPUs, 190 GiB of RAM and 30 GiB of free disk.
- **Region `us-east-1`:** `ordinary_final_cloud.py` around 192, 300 and 310; `ordinary_final_run.py` around 101; `ordinary_final_bound_preflight.py` around 34; `prepare_ordinary_final_run.py` around 171 and 197.
- **Rate cap 1.29 USD an hour:** `tools/ordinary_final_watchdog.py` around 13; `ordinary_final_cloud.py` around 192; `prepare_ordinary_final_run.py` around 171 and 198; `ordinary_final_bound_cloud.py` around 33; `ordinary_final_v3_cloud.py` around 37.
- **Soft 5 and hard 7 USD:** sealed at `prepare_ordinary_final_run.py` around 199 and checked at `ordinary_final_bound_cloud.py` around 33, but typed again inside the controller (`ordinary_final_cloud.py` around 208, 239, 284, 310 and 386), which ignores the manifest.
- **The generic cloud path** (`tools/cloud_run_common.py` around 165 to 168: 5 and 10 USD) is used by `cloud_run_watchdog.py` and `deploy_cloud_run.py`, not by the ordinary final path.
- **Time reserves** (900, 840, 240 and 180 seconds): `ordinary_final_run.py` around 107 and 205; `ordinary_final_cloud.py` around 208, 239 and 386; `ordinary_final_watchdog.py` around 14 to 15. Preparation seals 900 and 180 (around 199) but the controller does not read them.
- **Image and Python version:** preparation takes the provider's first image (around 198) and the controller checks for Python 3.12.3 (`ordinary_final_cloud.py` around 342).

**Design.** The execution manifest carries an ordered list of instance candidates (type, regions, rate cap, GPU-name pattern, minimum GPU memory, CPU and RAM, image), `soft_budget_usd`, `hard_ceiling_usd`, `per_run_cap_usd` and the time reserves. The controller picks the first offered candidate whose live rate is within its cap and records the choice in the authorization; the authorization check, the watchdog deadlines, the hardware check and the preflight read the selected candidate instead of literals. The per-run cap is computed by the loop's formula (the smaller of 1.5 times the forecast and the remaining budget less running caps, storage forecast and 1 USD) and sealed; every phase deadline follows from the sealed values.
