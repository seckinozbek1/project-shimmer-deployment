For the lead session only, started by Seckin in the main checkout: if `docs/loop/private/LOOP_STATE.md` exists and its status is not DONE, read `prompts/SHIMMER_AUTONOMOUS_LOOP_2026-10-27.md`, then that state file, then the newest file in `docs/loop/private/handoff/`, before doing anything else, and continue the loop from the step it names. Subagents, teammates, checkers, lanes, role sessions and clones ignore this line and do only the task they were given.

# Project Shimmer, agent operating contract

This file is the operating contract for an AI coding agent (Claude Code) working in
this repository. It is terse and rule-shaped, not a tutorial (the newcomer guide is
README.md). The founding specification is [genesis.md](genesis.md), Parts I to XXVII:
read it before making any change. Shimmer is a standalone document processing swarm
governed by an append-only constitution. It is domain-agnostic only in a narrow sense:
no domain vocabulary appears in code (the vocabulary rule below), and its results differ
widely between the fields it has run on.

## Hard rules

- No em dashes anywhere. Use commas, colons, periods, or parentheses.
- LAW-IV (privacy) is never edited. It outranks LAW-0 (operator sovereignty) for
  sensitive-content handling, with no exceptions. A single leak is irreversible.
- The constitution is append-only. The INFRA-029 amendment-guard tripwire
  (`scripts/constitution_guard.py`, `check_constitution_change`, called by
  `Constitution.save` and the snapshot load) refuses a write that would modify or delete an
  existing `amendments[]` entry or seed law unless the operator approves it in an interactive
  session through the operator handler (LAW-0); with no handler, outside interactive mode or
  without an approval it is refused (the snapshot load keeps the live constitution), and each
  such decision is logged to `durable/governance/constitution_guard_log.jsonl`. A new amendment
  is accepted only as one verified append per write, `operator_approved`, an INFRA id being the
  next one. No-gap rule: an amendment id is never reused, never inserted
  between existing ids, never renumbered. Every numbered DELTA is recorded in
  `config/constitution.json` `amendments[]`, the single canonical record; no DELTA
  lives only in prose.
- Model ids are read live from the provider, never hardcoded. A deprecated model STOPS
  the run for operator approval; there is no auto-swap. Model choice is owned solely by
  `config/agent_registry.json` (`spec.model`); the key layer never sets a model. Use
  bare model aliases (`claude-opus-4-8`), never dated snapshot ids.
- API keys live OUTSIDE the repository, located via `$SHIMMER_CONFIG_PATH`, then a
  sibling `../api_keys/config.py`, then the repo-root `.env_path` pointer. Never
  hardcode, log, echo, or commit a key value. `load_api_keys` reads key values only via
  a fixed allowlist.
- Domain vocabulary is OPERATOR-DECLARED, in `config/domain_vocabulary.json`, and appears in
  NO code. The vocabulary probe (check 174) reads its terms from there and holds none of its
  own; check 22's previously hardcoded regex now reads from the same file under
  `previous_domain`. A guard written once, in code, against the domain of the day is the
  mistake both checks exist to prevent. Severity is per family (`fail` blocks, `warn` reports
  a count); ALL-CAPS terms match case-sensitively. `input/` and `benchmark/` are never
  scanned, and `config/convention_registry.json` is exempt (gitignored, generated at BOOT).
- Tokenisation is UNICODE-AWARE and there is ONE tokeniser: `pairing_map._norm_label`.
  `reference_tables._words` delegates to it. They used to differ in script range and in a
  word-length filter, and the containment test compares one side's tokens against the other's,
  so on any corpus with an accented letter the band mechanism produced nothing at all,
  silently. Two tokenisers that must agree are one tokeniser.
- No domain-specific content in `scripts/`. Domain knowledge lives in `config/`
  (compiled conventions) and `durable/` (learned assets spawned from `input/context/`,
  under `durable/learnings/` and `durable/reference/`). Retired scenario tooling lives
  in `scripts/archived/` (still parsed by the gate, exempt from the domain gate by the
  `download_*`/`retry_*` naming convention or by carrying no domain vocabulary).
- English only for code, config file names, and folder names. No spaces or unicode in
  paths.
- Every convention review finding cites at least one CONV-* and at least one REF-*.
- A convention heading that carries the operator's own rule id keeps that id as its
  `category`, and NOTHING else is consulted for it: `finding_record.source_rule_id_for` reads
  it back for attribution. The parser's English keyword table (`_CATEGORY_KEYWORDS`) is now
  DELETED (CLASSIFIER-B): a heading with no rule id keeps its own first word, read rather than
  interpreted. The table used to run first and silently reclassified an operator slug containing
  the word "value", losing attribution for every finding under that rule; when measured it fired
  on 0 of 44 shipped headings, returned order-dependent answers ("Borrowing and attribution"
  became `citation_style`), and still mapped "Naming and values" into the ethics bucket. Do not
  reintroduce it; gate check 176 refuses its return.
- WORDS-A: where a decision rests on WHAT WORDS MEAN it is decided by the five-voter ensemble
  (`scripts/semantic_ensemble.py`), never by a literal keyword table and never by one method
  alone. References live in `config/semantic_references.json`, thresholds in
  `config/semantic_thresholds.json` with the error rate each produces. Regex keeps everything
  STRUCTURAL: declared syntax, bracket declarations, ids, delimiters, formats, run-id shapes.
  A place that already REFUSES rather than guessing (document dating) stays as it is and is
  never converted into something that votes.
- A heading's brackets carry the severity, the subject tags, and two DECLARATIONS read by their
  leading word only: `[scope: class=A, device]` (the field labels, optionally pinned to a value,
  that identify the units the rule governs) and `[requires: calibration authority signature]`
  (the labels whose absence from a unit in scope is a finding). A scoped rule pairs on its scope
  alone; a declared required field that is absent is decided by Python with no call
  (`absence_path: computed`); a scoped rule with no declared requirement is one narrow model
  question per unit in scope (`absence_path: judged`), its answer stamped with the unit and rule.
  Scope is never derived from text or counts; the operator declares it. Labels are the
  operator's own words and appear in no code.
- UNITS-A: `pairing_map.split_units` makes a PREAMBLE unit (kind `preamble`, id `u00-` plus
  the document's own title slug, index 0) of the text before the first body heading whenever
  that text carries content beyond heading lines and rules. It is never a heading ordinal,
  so no `u01..uNN` id moves, and the extraction ledger keeps every span identity and offset
  (`benchmark/fixtures/unit_identity_before_preamble.json` pins both on all twelve corpus
  documents; check 273). The preamble is excluded from `unmatched_findings`: "no rule applies"
  is its normal state, not a missing field. Measured, not preferred: the clinical sheet's
  declared result counts sat above its first heading and were unreachable in five runs; they
  are reachable now, and STILL not computable, because the per-laboratory labels carry a comma
  the structural label reader does not admit. Widening that reader is a separate decision on
  every corpus, not a way to reach a catch.
- CONTROLLER-BINDING: a sealed bundle is bound to the CONTROLLER it was sealed with. The
  sealer's `local_control_hashes` pin `tools/ordinary_final_cloud.py`, the bound wrapper and the
  provider adapter beside the runtime files, and `execute()` verifies every name in that map
  before its first provider call, so a launch under a changed controller refuses
  (`Controller source changed`) with no instance, key or launch intent created. Before this the
  seal pinned the runtime the controller carries but not the controller; only the launch
  receipt recorded its hash, after the instance existed. Proven both ways with a neutralization
  that drops the controller from the binding (controller gate). The controller carries no
  credential path (loop S1, 2026-10-27): `credential_path()` calls
  `agent_wrapper.resolve_config_path()` just before the first provider call, never at import,
  and with nothing found refuses in one line naming `SHIMMER_CONFIG_PATH` before any provider
  call, instance, key or launch intent. The watchdog argument and the independent cleanup use
  the same path; the status reader and both live preflights use the same function. This edit
  changed the bound controller file, so every bundle sealed before it (v12 included) refuses
  with `Controller source changed` and must be re-sealed; past results are unaffected. Loop S2
  (2026-10-27) changed six of the seven bound files (`tools/cloud_run_common.py`,
  `tools/cloud_run_watchdog.py`, `tools/ordinary_final_bound_cloud.py`,
  `tools/ordinary_final_cloud.py`, `tools/ordinary_final_run.py`,
  `tools/ordinary_final_watchdog.py`; `tools/lambda_experiment_provider.py` is unchanged) and
  added four files the controller imports to decide and record a launch to the binding
  (`tools/loop_budget_guard.py`, `tools/loop/instance_reaper.py`, `tools/loop/keep_awake.py`,
  `tools/run_remote_experiment.py`), so every bundle sealed before S2 refuses the same way and
  cannot be re-executed; a new seal carries the new hashes. S2 checker round 2 changed
  `tools/ordinary_final_cloud.py`, `tools/ordinary_final_bound_cloud.py`,
  `tools/loop_budget_guard.py` and `tools/loop/instance_reaper.py` again, so bundles sealed
  before it refuse the same way and must be re-sealed. `scripts/agent_wrapper.py` is not
  in the controller binding: the seal already pins it among the runtime files the bundle
  carries. Loop S5 changed `tools/ordinary_final_run.py`, `tools/ordinary_final_cloud.py`
  and `tools/ordinary_final_bound_cloud.py` (the B1 arm, the B3-only batch form, per-entry
  evidence past the soft budget, the sealed B1 argument check), so bundles sealed before
  S5's merge refuse the same way and must be re-sealed. D-S17 item 1 (at most two loop
  instances) changed `tools/ordinary_final_cloud.py`, `tools/loop_budget_guard.py` and
  `tools/loop/instance_reaper.py`, so every bundle sealed before it refuses with
  `Controller source changed` and must be re-sealed. D-101 (after L7, D-100) changed `tools/ordinary_final_run.py` again (a
  declared multi-round run is assessed without the Producer 168 model-call requirement), so
  bundles sealed before it refuse the same way and must be re-sealed. Open item 37 (disk on the instance:
  the runner's `evidence/disk_usage.json` before, sampled during and after the workload, and
  the evidence packer's `disk_after_evidence.json`) changed `tools/ordinary_final_run.py` and
  `tools/ordinary_final_cloud.py`, so bundles sealed before it refuse the same way and must be
  re-sealed. Arm L (D-S13 item 6d, ARM-L-A) changed `tools/ordinary_final_run.py` and
  `tools/ordinary_final_cloud.py` again, so bundles sealed before it refuse the same way and must
  be re-sealed.
- LOOP-LAUNCH-A (loop S2): every ordinary final launch is a loop launch. The bound wrapper
  (`tools/ordinary_final_bound_cloud.py`) requires `--ledger`, `--purpose` (a short
  identifier: lower case, digits, hyphens), `--forecast-minutes` and `--storage-forecast-usd`;
  `execute()` refuses without that launch plan. The `--ledger` must be one the reaper reads
  (the private ledger or R's), and the guard always reads both of those beside any
  `--read-ledger` and needs a `budget_open` line among them. Before the launch request
  `tools/loop_budget_guard.py` decides, holding an exclusive lock beside the ledger from its
  decision through the intent line and reading the provider inventory again just before it:
  it refuses when two loop instances already run (D-S17: at most two at a time, a third
  refused in one line, "Two loop instances are running; at most two at a time"; the limit is
  `instance_reaper.MAX_LOOP_INSTANCES`, read by the guard as `loop_budget_guard.MAX_LOOP_INSTANCES`
  and by `admits_another`; each instance counted once over the open ledger launches and the
  `shimmer-loop-` names in the inventory), when the inventory lists a loop instance no ledger
  records (its cap could not be counted) or any instance that is not a loop instance (the
  controller, the sealer and the bound preflight refuse that too), when the per-run cap `min(1.5 x forecast, ceiling - spend - running
  caps - storage forecast)`, ceiling `min(hard stop, budget - 1)` (`loop_budget_guard.cap_ceiling`,
  so a hard stop at the budget never removes the one-dollar margin), is below the forecast
  (measured minutes x live price x 1.3), or when
  the capped run time does not cover the forecast time plus the run's stop reserve (the cap
  rule alone keeps spend + forecast + storage at or below that ceiling). The budget is
  never a code constant (D-S9): the guard and the reaper read it from the ledgers' latest
  `budget_open` or `budget_change` line (`instance_reaper.budget_figures`; the hard stop is that
  line's `hard_stop_usd`, else the budget less the one-dollar margin), a launch with no readable
  budget line is refused, and the reaper terminates every loop instance while no budget line can
  be read. The type rule's A10 reference is the latest `a10_reference_price_usd_per_hour` on any
  budget line. The hard stop counts every running loop instance together (spend is the
  total over all launches); the reaper judges each instance on its own record and, should more
  than two be left running, ends the latest-requested beyond the limit (`over_instance_limit`).
  A controller's independent cleanup requires its own instance gone and no instance outside the
  loop, and names another loop instance still running apart (`other_loop_instances`).
  An open launch accrues spend only up to its recorded deadline; past it, with no
  instance of its name listed, the reaper closes it with one termination line
  (`intent_without_instance`, or `instance_not_listed_charged_to_deadline` for a launch whose
  instance is gone), charged to the deadline: a ceiling counted as actual spend and never
  refunded. A closing or termination line goes to every ledger file that holds the launch
  (`instance_reaper.holders`: R's ledger for a launch only R recorded, both for a copied line),
  and to the append ledger only for a listed loop instance no ledger records. The ledger lock holds its pid and creation time; a held lock is
  refused in one line naming its age, its pid and whether that pid runs, and no tool removes it.
  `--purpose` is checked in `launch_plan()` before any provider call. Spend is counted once per
  launch across ledgers, a termination closing a launch by its instance id or its name (a
  `copied_from` line is not counted twice). The instance name always starts `shimmer-loop-`
  and the `launch_intent` line, with its `deadline_utc`, is written before the request;
  `launch` and `termination` lines follow, a recovered launch gets its `launch` line before
  its termination, and the ledger is closed in its own try before the rest of the cleanup. A
  ledger line carries only the declared fields (`loop_budget_guard.LEDGER_FIELDS`, which also
  declares the reaper's `by` and `reason`) and anything else is refused. Instance candidates
  (the A10 first, then other single-GPU types with the run's VRAM at no more than twice the
  A10's recorded price), rate caps and the soft and hard caps are sealed manifest fields set
  by the sealer from the provider inventory it is given and the guard's formula; the type rule
  polls for the A10 in us-east-1 for up to 30 minutes before a fallback, and the runner's
  hardware check reads the selected candidate. Which figures are CODE CONSTANTS, stated
  exactly: the loop's budget rule (the 1-dollar margin, `instance_reaper.MARGIN_USD`, read by
  the guard; the 1.5 cap factor, the 1.3 forecast factor and the type rule's factor 2 in
  `tools/loop_budget_guard.py`), the two
  reserves (`WORKLOAD_STOP_RESERVE_SECONDS` 900, `TERMINATION_RESERVE_SECONDS` 180) in the
  sealer, and the run's own hardware floors. No per-run cap is a code default:
  `cloud_run_common.budget_deadlines` and the general watchdog (`--soft-usd`, `--hard-usd`)
  take them as required arguments, and the general path's sealers take them on the command
  line (`prepare_cloud_run.py --soft-usd/--hard-usd`, `run_remote_experiment.py prepare
  --soft-usd/--hard-usd`). The general cloud path (`tools/deploy_cloud_run.py`,
  `tools/run_remote_experiment.py`) refuses a `shimmer-loop-` name, any loop ledger argument,
  and any launch while a loop ledger is open (`budget_open` without `budget_close`);
  `deploy_cloud_run` resolves the instance name first and, on a failure, terminates only an
  instance whose name it resolved and which is not a loop instance. `--detach` runs the
  controller as a detached process that survives the session; while an instance can exist the
  controller holds `SetThreadExecutionState` through `tools/loop/keep_awake.py`, and the ledger
  deadline is what `tools/loop/instance_reaper.py` acts on if the controller dies. A bundle is
  launched once: `RUN_FOLDER.json` is written into it only after the launch intent, and either
  marker refuses a second launch with or without `--output-dir`, for the session bundle and
  for every batch entry (`ordinary_final_cloud.consumed`); a run folder left by an
  attempt refused earlier is kept and the next attempt takes `<bundle>.2`.
- B1-ARM-A (loop S5): the sealer writes `arm` (B3, B1 or L) into every manifest; a manifest
  without one is B3. A B1 manifest carries `b1` (its sealed passes `{name, checkpoint, args}`, the
  item ids of its one document, the `items.json` digest) and `items.json` as a support file;
  a sealed checkpoint carries only the options `benchmark/baselines/bare_model.py`'s parser
  takes (`ordinary_final_run.B1_SEALED_ARGS`, refused at sealing otherwise; that parser takes
  no abbreviations). `tools/ordinary_final_run.py` keeps every guard for both arms, refuses an
  authorization whose `arm` differs from the sealed one (none means B3), and for B1 loads the
  sealed `bare_model.py` in its own process, never imports `pipeline`, runs `main()` once per
  checkpoint into `evidence/b1/<name>`, and passes only on one reply record per item per
  checkpoint. A batch entry's plan arm must equal its sealed arm; a batch file may say
  `"form": "b3_only"` (exposed bundles only, each item once, unpaired). Past the soft budget
  a batch entry's `batch_pack_evidence` and `batch_evidence_hash` still run. The analyser
  reports a B1 entry from `evidence/result.json` and each checkpoint's `b1_summary.json`. A sealed
  B1 pass is `{name, checkpoint, args}` (D-056 condition 6): `name` is a free label (lower case,
  digits, underscore; unique) naming `evidence/b1/<name>`, `checkpoint` (tuned or base) is
  passed as `--checkpoint`, and a pass without `checkpoint` loads the checkpoint its name names.
- ARM-L-A (D-S13 item 6d): a third sealed arm, `L`, runs the launcher menu as shipped on the
  loop's own instance with the same controller, guard, ledger, reaper and binding; never on the
  laptop. The sealer (`--arm L --launcher-question "..."`, exposed only, refused for a sealed run
  by the sealer and by `admit_workload`) puts the workload's context and conventions files into
  one flat `launcher_input/` (nothing under `input/`; each file where the wizard's own
  `classify()` places it), adds `shimmer.sh`, `tools/runtime_contract.py` and
  `tools/cloud_run/runtime.json` to the archive, and seals a `launcher` block: the draft question,
  the children's environment exactly `ordinary_final_run.LAUNCHER_CHILD_ENVIRONMENT`
  (`SHIMMER_MODEL_MODE=base`, `SHIMMER_SKIP_INSTALL=1`, hub and pip offline) and a prompt map,
  each prompt with its answers in the order it is asked (menu `1`, `1`, `Q`; task `R`, `D`; the
  wizard's target question answered with the numbers it lists the targets under; `y` to the
  pipeline's three questions each run; the preflight's continue question and an escalation
  optional, an escalation deferred). Every sealed prompt must be a printf text of the bound
  `shimmer.sh` or one string constant of the bound wizard or pipeline
  (`launcher_prompt_error`, at sealing and on the instance). The runner keeps every guard, makes
  `project/.venv` from its own runtime (no pip; a `.pth` adds its site-packages), runs
  `bash shimmer.sh` once with pipes in its own session and answers each prompt only from the map
  at a line start once the output is quiet (`drive_session`); an unknown prompt, answers used up,
  30 minutes with no output or the deadline (the budget stop less a minute) ends the session,
  never a guess. A child Python that loads the sitecustomize from `PYTHONPATH` applies
  `cloud_run_observer.deny_network` and logs to `evidence/launcher/network/`; the denial is a
  Python-level patch, so native code and non-Python children are neither denied nor counted, and
  a Python child that never loads the sitecustomize (`-I`, `-S`, `-E`, `PYTHONPATH` dropped)
  leaves no log and is not counted (S7 close; an independent child count is an open item). The two runs move to `evidence/launcher/review|draft/`;
  `assess_launcher` passes integrity only: the menu ended by itself with exit 0, every sealed
  answer given, one run per task reaching its end with exit 0 and one pipeline_start and end, the
  run summary and the memo, the draft's manifest and memo cleared, the socket layer denied in
  every Python child that loaded the sitecustomize and the denial in full in every pipeline
  process, and no blocked attempt among them (a measured count of those children, not a proof of
  no network for the session); incomplete semantic
  work is recorded and does not fail the arm, since base models as shipped carry no quality claim. The controller refuses arm L in a batch, and
  `stop_workload` also ends what runs from the remote project; the analyser's `Launcher session`
  row reports it, never comparable with B3 or B1. Its workload progress (PROGRESS-A) is the sealed
  answers given, read off the runner's own answer lines (`ordinary_final_progress.launcher_workload`).
  Check 311 (`tools/ordinary_final_launcher_checks.py`).
- STAGE-A (loop S5): `tools/stage_workload.py` turns an adapter or generator build into the
  sealer's workload folder (`_review_targets.json` at the top, `context/`, `conventions/`,
  and `case_manifest.json` for multi-round, copied byte for byte) and writes each B1 bundle's
  own `items.json` outside it. It never copies `answer_key.json` or build records, and
  refuses the whole staging when a file under `context/` or `conventions/` is named like a
  key. Check 287.
- PREFILL-E (loop S5, D-056, D-058, D-060, D-061, D-063): with nothing set, the producer loads
  sdpa (`SHIMMER_PRODUCER_ATTENTION`) and every producer call and every B1 call
  (`benchmark/baselines/bare_model.py`, both checkpoints, every item) runs pinned per call to the
  memory-efficient sdpa backend and prefilled in one shot through `final_models.generate_with_prefill`,
  both recorded as decision D-063 (D-061's declared fallback: E missed its threshold; sdpa one shot
  was byte-identical to one-shot eager on 12 of 12 replayed B3 prompts, E on 8 of 12). Eager
  (one shot or chunked) and chunked prefill (`SHIMMER_PRODUCER_PREFILL_CHUNK`, E is
  `E_CHUNK_TOKENS` 512, 2 tokens left to generate()) are measurement settings, each accepted only
  with its decision id (`SHIMMER_PRODUCER_ATTENTION_DECISION`, `SHIMMER_PRODUCER_PREFILL_DECISION`);
  a decision named with the default is accepted only when it is D-063. One rule each:
  `final_models.attention_setting` and `prefill_setting`. The producer and B1 share one kernel.
  The `_load_qwen` models run sdpa pinned the same way, one shot; the Auditor896 classifier stays
  eager (its runtime contract says so). Every reply record carries `attention` (kernel, prefill
  setting, decisions) and `prefill` (chunks, tail, seconds). Out of memory or a refused kernel is
  written once and raised as a named failure, never retried; a prompt whose tokens plus the output
  allowance exceed the model's positions is refused before generating, recorded (`context`,
  `prompt_over_context`, a RUN_REPORT row) and is a declared exclusion of B3. B1 measurement
  passes (`--attention eager`, `--prefill-chunk N`) need a decision id; each pass records its peak
  GPU memory, and `bare_model.py compare --a --b --out` counts byte-identical replies and agreeing
  labels. `benchmark/baselines/replay_prompts.py` replays B3 producer prompts (payloads only) as an
  exposed-only replay pass; its `e`, `one_shot` and `e_repeat` paths are measurement paths, `sdpa`
  is the run proper's. The sealer evaluates the bound rules, and the runner's B1 rule is held equal
  to bare_model's. The analyser states "producer and B1 sdpa, prefilled in one shot,
  memory-efficient backend pinned (D-063); differs from v5 to v12, which ran the producer eager".
  Also from D-061: a VERIFIER reply that is not an object is a recorded contract failure;
  `semantic_incomplete` is its own assessment reason; no partition retry under deterministic
  decoding (`retry_skipped_deterministic`). The producer was trained and evaluated eager one shot,
  so its 102-of-102 DEV figure is a one-shot eager figure; the difference is a preregistration
  section 9 limitation. Loop S5 changed `tools/ordinary_final_run.py` several times (D-061, D-063),
  so bundles sealed before S5's merge refuse with `Controller source changed`. Checks 282, 288, 289.
- SEALED-RUN-A (loop S2): a sealed run (`--exposure sealed` at sealing, role B's
  `--test-manifest`) is prepared outside the repository from the test archive; its seal
  carries the test manifest's SHA-256 (an exposed seal says `exposed, no manifest`). At launch
  the controller requires the same test manifest and `--frozen-tag`, the bundle hash and the
  tag's commit to equal the seal's, and a run folder outside the repository. It prints counts
  and timings only (`phase N at S s`), attaches no provider storage, and writes nothing in the
  repository except ledger lines. `--frozen-tag` resolves `refs/tags/<name>` only (annotated or
  lightweight); a commit id, branch, HEAD or revision expression is refused. A sealed bundle
  inside the repository is refused before any write, with or without `--output-dir` or
  `--detach`. The sealer LF-normalises only plain-text and HTML workload members (the
  extensions `scripts/text_extract.py` reads as text); binary members and the case manifest
  keep their bytes. `protected_test` is sealable only on a sealed bundle; an
  exposed run behaves as before. `--batch` runs several bundles in one instance session
  item by item (B3 then B1 per item), each with its own run folder under `batch/`, seal entry,
  authorization and evidence, so a stop leaves every finished pair complete. The analyser
  (`tools/analyze_ordinary_final_run.py`, `--batch` for a session) writes `RUN_REPORT.md`
  (Annex A 11.12: purpose and sealed-or-exposed lines first, the `SHIMMER_INST_FINDER` value,
  FACT_CHECKER withheld with both B.4 reasons, instance type and price, asset copy MATCH or
  not, the role-separation sentence for a sealed run; a field that does not apply says why) and
  the same rows in `FINAL_STATUS.json` under `report`. The sealer refuses an unratified
  `SHIMMER_INST_FINDER=off` with the pipeline's own ratification test, read from the bound
  source. Named extras of the source archive are `prepare_ordinary_final_run.ARCHIVE_EXTRAS`;
  a listed path the bound commit lacks fails in one line, and test material never travels in
  the source archive.
- MULTI-ROUND-A (loop S2, D-011): final mode admits Review with `--multi-round` and
  `--multi-round-manifest` together; Draft, the flag alone and the manifest alone stay refused
  by `main()`'s own final-mode block. The controller admits a multi-round workload only when
  DECLARED, SEALED and VALID: `ordinary_final_run.admit_workload` checks `multi_round` true,
  the case manifest hash in `support_files` and `case_manifest_sha256`, `fixture: false`, the
  live field set and exactly `MULTI_ROUND_ARGV` (`reference_serial`, no topology file); the
  spans are checked by `validate_live_case_manifest` at sealing and at launch (not on the
  instance), against the documents the bound pipeline's own `_load_corpus` loads;
  `execution_topology` is unchanged (D-011 choice 3).
  The runner's assessment passes a multi-round run only on outcome `reviewed` and activation
  `activated` (`multi_round.read_saved`), its round review recorded, and exactly one
  pipeline_start and one pipeline_end in its telemetry; it does not require a model call of it
  (`ordinary_final_run.model_call_required`, D-101: L7 failed nine reviewed multi-round entries
  on that requirement alone), while every other B3 run still needs its Producer 168 call. The
  phase saves its own step times (`timings` in `audit/multi_round.json`, `seconds` per round in
  `audit/round_reuse.json`, `time.perf_counter`, rounded to microseconds; open item 39), since a
  multi-round run has no topology runtime and empty `phase_latencies`; the analyser reports them
  in its `Multi-round step times` row. Later rounds reuse unchanged units through a
  Python-only per-round review (`multi_round_rounds`): a unit's signature covers its text, its
  paired rules, the labels of the document's field vocabulary those rules name
  (`multi_round_rounds.named_vocabulary`, the only way the vocabulary reaches the computation;
  a label no paired rule names recomputes nothing) and its units of measure
  (`SIGNATURE_INPUTS`), reused records and model asks are rebased onto the new unit id, the
  record is `audit/round_reuse.json`, and the round findings are posted on the run bus (backend
  `paired`, model `python`, one envelope per round document); nothing in the pipeline reads them yet (`tools/score_corpus.py` scores them).
  The case's typed records are computed in Python, with no model call (open item 35, INC-023:
  the one free-form PROCESSOR call over the whole case ran to its output cap on real execution):
  one position per declared (round, actor, issue), accepted only on exactly one accepted source,
  numeric only when its quote states exactly one figure with a unit; one movement between
  consecutive positions, always `unknown` (`multi_round_phase.computed_records`, `written_by`
  `python`, posted with backend `computed`, model `python`). Only the strategic layer's explicit
  decision-support modes still call PROCESSOR and VERIFIER. A
  term that vanished while its section states an unclaimed newcomer in the same unit of measure
  is refused as a possible rename (`paired_review.possible_successor`), never minted as
  withdrawn, until S5 measures an ensemble decision for it; two figures with no unit count as
  the same measure there and are refused under their own reason. Check 279 and
  `tools/multi_round_launch_checks.py` hold this end to end.
- ASSET-COPY-A: the ordinary final controller (`tools/ordinary_final_cloud.py`) can use a
  PROVIDER-SIDE COPY of the sealed asset archive, and it is OFF unless the bundle carries an
  operator-written `asset_copy_declaration.json` (`filesystem_name`, `mount`,
  `operator_authorized: true`, `assets_sha256`), written by `tools/declare_asset_copy.py` from
  the bundle's own digest; a declaration whose `assets_sha256` is not this bundle's archive is
  refused (`Asset copy declaration is for another bundle`), the controller never writes one (for
  the autonomous loop of 27 October 2026 only, the operator authorised the loop to write the
  declaration with `tools/declare_asset_copy.py` for the bundles it runs and to replace the
  filesystem's archive after recording the old digest, `docs/loop/DECISIONS.md` D-028; the
  filesystem is never deleted), a
  sealed run never reads one, a launch outside us-east-1 drops it, and without one the launch
  plan must state `--forecast-includes-upload`. The one such resource, `shimmer-filesystem` (us-east-1, 20 GB, $4.00 a month, created
  by the operator by hand because the adapter has no create endpoint and never will), is
  recorded with its verification and deletion rule in `docs/DEPLOYMENT_RESOURCES.md`. With one, the instance is launched with that filesystem
  attached (the provider adapter admits exactly one `file_system_names` entry and nothing else
  new), a probe hashes the copy under its hash-keyed name `assets-<sha256>.tar` ON THE INSTANCE
  and compares it to the sealed manifest's digest (the sidecar this machine could write is
  never the proof), a MATCH is copied into place and the upload skipped, and MISSING,
  MISMATCH, UNREACHABLE or a failed copy fall back to the upload byte for byte as v9 ran it.
  `archive_integrity` hashes whatever is on the instance, as always. A MISSING copy is seeded
  only after that phase passed, with `mv -n`, so a stale or corrupt file is never overwritten;
  a MISMATCH is recorded suspect for the operator and never replaced by a run. Every outcome
  is in `asset_copy_receipt.json`. The five local proofs are in
  `tools/ordinary_final_controller_checks.py` (states MATCH, MISSING, MISMATCH, UNREACHABLE;
  a copy under another digest never matches; the fallback argv equals the v9 argv; no seed
  without integrity; a neutralised probe that stops hashing is caught) and the rehearsal runs
  three copy polarities through a real shell, each a loop launch named `shimmer-loop-rehearsal`
  on a ledger of its own (`rehearsal_ledger.jsonl` beside each rehearsal bundle, never the
  loop's ledger). The rehearsal works only in
  `<Linux home>/shimmer-rehearsal`, read through its own shell at run time; it refuses an
  empty, root or relative home, and builds every `rm -rf` through one guard that refuses
  anything outside that folder (checked in `tools/ordinary_final_controller_checks.py`).
  Every loop launch since L1 used the asset copy under the operator's D-S4 authorization
  (MATCH; D-057, D-109); outside that it is unauthorized until the operator says otherwise,
  and it changes nothing when undeclared.
- Test corpora from other domains live in `benchmark/corpora/` (real public data, outside the
  vocabulary probe's roots) and are staged with `tools/stage_corpus.py`. Run one before
  claiming domain agnosticism; the first unseen corpus found five parser defects in ten minutes.
  A key outside `benchmark/corpora/` is scored with `tools/score_corpus.py --key <answer_key.json>
  --run <run>`, and its twin with `--twin-key` and `--twin-run`; the scorer refuses a twin the key
  does not name and a run that is not of the twin's document. It reads `expected_refusals` by
  refusal kind (a rename Python matched is no false positive; one only a model's record matches
  satisfies nothing), scores a run holding `audit/multi_round.json` per round and document from
  Python's round findings only (a round-scoped key is refused on any other run), and reports
  the four relations Python never writes apart, located only by a marked model-written record
  (check 293). Development cases built from
  repository material live in `benchmark/dev_cases/`: exposed, development only.

## Change discipline

- Read-only trace before any structural change. Trace to the point where the decision
  is mechanical.
- Full upstream and downstream hygiene for every change: all writers, all importers,
  string literals, path constructions, genesis.md, README.md, CLAUDE.md, .gitignore,
  the verify gate, hardcoded lists, and CLI flags.
- The gate stays green and non-mutating at every commit. Commit each coherent unit
  standalone.

## Working method and git discipline

- NO PIPELINE RUNS FROM THIS MACHINE (standing rule, in force from 2026-09-11 until development
  moves to a rented GPU box). Start no pipeline run of any kind, and do not ask to. Every
  proof is built on fixtures, mocks, deterministic paths and the artifacts already saved on
  disk under `output/runs/`. This laptop has an 8 GB card and pages at 15 GB of RAM: a single
  run costs one to three hours and blocks everything else, including the gate, which loads a
  model onto the same card.
- PUSH-TARGET GUARD: the sole origin must be `project-shimmer-deployment`. Confirm it
  before any git remote operation. Never push unless the operator explicitly says to push.
- Before any git operation, scan the staged diff for key patterns (Anthropic `sk-ant-`,
  OpenAI `sk-proj-`/`sk-`, AWS `AKIA`, Google `AIza`, any value assigned to a
  credential-named variable). If a real key is detected, STOP, do not commit or push,
  and alert the operator. Commit SHAs, hashes, UUIDs, and numeric ids are not keys.
- Process operator job specs (the sequenced `.md` files under `prompts/`) PART BY PART:
  complete and report each PART before reading the next, and honor every STOP. Do not
  run unattended.
- Surface conflicts rather than silently assume. When a spec's literal wording conflicts
  with a repo convention or a higher-priority instruction, report the conflict and your
  chosen resolution; do not paper over it.
- Prompts are self-contained: a job spec carries the context needed to execute it. The
  changelog and any external ledger are maintained outside Claude Code unless the spec
  says otherwise.
- OPEN-ITEMS: `docs/fix/OPEN_ITEMS.md` is the standing record of everything FOUND AND
  CONSCIOUSLY NOT FIXED, each entry carrying what it is, the evidence, why it was left, and
  what would settle it. It is WRITTEN AT THE END OF EVERY PASS and READ AND REPORTED AT THE
  START OF EVERY PASS, before any work is proposed. It is not a plan and nothing in it is
  authorized or scheduled. What the operator deliberately deferred belongs to the roadmap,
  and tuning work to `docs/fix/TUNING_BACKLOG.md`, not here: an item earns its place by
  having been seen and passed over.
- PROGRESS-A: any phase that takes more than a couple of minutes reports MEASURED PROGRESS in
  every sitrep, not just its name. Four values, every time: how much of the work is done
  against the total, how long it has been running, the current rate, and the remaining time
  at that rate. Where the tool gives no progress (the controller captures scp with no
  output), measure it with a read-only observation of the work itself (a `stat` of the
  partial file on the instance over the run's own key, a count of finished items in the
  log) and state it as measured, never as inferred. Where nothing can be measured, say so
  and say why; never substitute an estimate for a reading. This applies to the asset
  upload, the seed copy, model acquisition, wheel installation, the workload's own
  generation progress, and any local phase of similar length, including the rehearsal's
  polarities and long gate runs. Set the sitrep up this way before the phase starts; it
  should not need asking (it was asked for during the v12 upload, 2026-09-19). The reader is
  the TRACKED tool `tools/ordinary_final_progress.py`, one reading per phase, never a
  scratchpad script: the scratchpad version broke on a quoting fault mid-run and printed an
  empty rate into a live sitrep. Its proofs (`tools/ordinary_final_progress_checks.py`,
  replayed from run v12's own saved observations, no network) are held by gate check 274 and
  `tools/ordinary_final_progress_gate.py` with neutralize/fail/restore/pass. A controller
  phase that is neither given a reader nor listed as completion-only FAILS that check, so a
  new long phase cannot quietly go unmeasured.

## The verify gate

- The gate is `scripts/verify_session1.py`. Its total is the length of its CHECKS list,
  not a hardcoded number.
- Checks must prove behavior with EXECUTED coverage: run the live path on fixtures.
  Source inspection alone, or a zero-caller scaffold, is not proof. No
  dormant-but-claimed-built scaffold is acceptable: every part (function, flag, field,
  branch, store) must have a live duty or an executed gate path.
- Gate checks are non-mutating: they use tempdirs and never write the real
  `durable/`, `ontology/`, or `config/` stores.

## Governed structure

- Changes to the constitution or to governed inter-agent structure require an
  operator-ratified DELTA. Agents propose; the operator ratifies; agents never
  self-apply. The operator decides every escalation. No silent self-modification.
- The meta-law tripwire (INFRA-043) extends the constitution guard
  (`scripts/constitution_guard.py`) to the genesis/meta layer. `check_genesis_integrity`
  requires genesis Part I to mirror the guarded `seed_laws` (a missing seed law flags a
  tampered immutable core). The VERIFIED no-gap DELTA path is the SOLE route to change
  governed structure: `verify_amendment_append` (enforced inside `check_constitution_change`)
  requires a new INFRA-NNN amendment to carry the next id (`prior_max + 1`, never reused, never a gap; ids other than INFRA-NNN, such as the runtime AMEND-NNN, are checked for operator approval and one per write only),
  be `operator_approved`, and add one amendment per write (the signature scan is a separate
  flag on operator and agent text, not part of this check). Never bypass this path to change
  governed structure.
- The LAW-0 asymmetry is load-bearing, not a preference. The guard refuses AGENTS (they can
  never amend governed structure; a signature-carrying agent DELTA is refused and routed to
  the operator), but it NEVER hard-blocks the OPERATOR, who is sovereign under LAW-0:
  operator input gets confirm-and-proceed in interactive mode and log-and-proceed in
  non-interactive mode (`operator_input_verdict` returns proceed, or the operator's own
  abort, never a block). Never build anything that could hard-block the operator on the
  signature scan: a guard that cages the operator inverts LAW-0.
- The signature scan (`scan_for_meta_signature`) is a FLAG for operator attention, not a
  complete semantic guarantee: it has false positives and false negatives. Do not overclaim
  it or rely on it as a complete bypass guard.

## The canonical envelope (INFRA-037)

- Agents emit and consume ONE flat per-item envelope: `{agent, doc_id, items[]}`. Each
  item is strictly flat (every value a scalar or an array of scalars; no nested objects).
  Consumers read by reference from the append-only message bus, and a higher `revision`
  per `item_id` supersedes an earlier one.
- The paired review POSTS its computed findings to the bus (`_paired_convention_review`,
  `backend=paired`, `model=python`). They used to be returned in memory to phase 6 only, so
  `GET /findings`, the held-out scorer and every other bus reader were blind to the findings
  Python actually made. Anything that produces a Finding record must put it on the bus; a
  record that lives only in a return value is not a record.
- A table header's label is `pairing_map.header_label`, which strips the unit parenthetical
  BEFORE normalising. Every site that normalises a header uses it. The unit is read separately.
- The typed Finding record (`scripts/finding_record.py`) is one such item: `rule_id`,
  `source_rule_id` (the operator's own id for that rule), `unit_id`, `value_a`/`unit_a`,
  `value_b`/`unit_b`, `relation`, `record_verdict` (`ok`/`irregular`, deliberately NOT
  `verdict`, which the verifiability gate fires on), `source_refs`, `explanation`. Its
  schema lives in `config/agent_contracts.json` under `finding_record`; the module reads it
  rather than carrying a second copy. `explanation` is for the human reader and is stripped
  from any payload travelling to another agent (`strip_reasoning`).

- INST-SWITCH-A (loop S1, 2026-10-27): `SHIMMER_INST_FINDER=off` is honoured only under an
  operator-approved constitution amendment whose change names INST_FINDER and
  SHIMMER_INST_FINDER (no amendment id in code); otherwise the run refuses at start (exit 9),
  never ignoring the setting. The amendment is DRAFTED, not ratified
  (`docs/INST_FINDER_SWITCH_DELTA_DRAFT.md`); agents never ratify it. INST_FINDER stays in
  `PRODUCTION_AGENTS_CORPUS_LEVEL` and the registry; the loop (header unchanged) skips it,
  records `not_called` with state `switched_off`, and labels results from the dispatched list.
  The setting is saved in `audit/agent_switches.json` and the run summary. Check 277.
- REPLIES-A (loop S1, 2026-10-27; Annex A 11.6.4): every model call writes exactly one record
  through `reply_records.write`, inside the backend function that holds the raw text
  (`call_claude`, `call_gpt`, `call_qwen`, `call_local`) and in Auditor896's `predict`, never in
  `dispatch` or `run_task` (the draft memo calls `dispatch` directly, on the drafter's own backend; INC-031, check 312). Records go to
  `<run_dir>/audit/model_replies/`; outcomes are appended separately by call id to
  `outcomes.jsonl`; a redaction-enabled run keeps `sha256:` and `length_bytes:` only; a call with
  no run context writes nothing (never a fallback to `output/`). Saving a reply never promotes
  it: check 269 still holds that only Python-computed findings become amendments.
  `guard_secrets.py --staged` refuses `audit/model_replies/` and `seals/` at any depth (case
  folded), including inside a staged archive such as the controller's collected evidence
  `.tar.gz`, which has been force-committed under `docs/fix/` before. Checks 275 and 276.
- UNCOMPUTABLE-A (loop S5, D-068): on a paired plan of kind `uncomputable` (Python computed no
  comparison), the model's answer is kept as a model-written Finding record, never discarded:
  stamped by Python with the judged-absence stamping and the PLAN's rule
  (`paired_review.stamp_from_plan`; a rule id the reply names is replaced), screened by the shared
  refusals (`paired_review.judged_item_refusal`: quote not in the unit and the three absence-claim
  refusals; listed in the pairing map under `uncomputable_refused`), kept only from a reply that is
  ok and did not refuse (why it gave none in `uncomputable_judged`), and posted once as Python's
  stamped copy (`stamped_by: python`, `judged_path: uncomputable`) under the model's backend and
  model, so written by `model`; the call's own post still withholds its items. Outcome
  `judged_uncomputable` (`judged_listed`, `judged_refused`); `advisory_not_kept` names runs before
  D-068. Never promoted (check 269), marked wherever model findings are shown. Check 290. The
  benchmark adapters label a semantically incomplete run from its records (D-066), report
  completeness per document and arm, and add sensitivity S-6.
- WRITTEN-BY-A (loop S2): who wrote a finding is read off the bus post it travelled in
  (`finding_record.written_by`): `python` only for `backend` `paired`/`computed` with a model
  id starting `python`, `model` for everything else, including an item no envelope claims.
  Items are stamped (`stamp_written_by`) before any copy is made: the stamp joins each item to
  the envelope that carried it by object identity, which holds only for the envelope's own
  items, so it runs first and every later reader reads the stamp. Never compare the identities
  of copies, and never decide provenance by an agent name or by a field the item itself carries
  (a model's `provenance` is removed when it is stamped). `GET /runs/{run_id}/findings` carries
  `written_by` on every record.

## Review modes

- Phase 5.5 runs `wide` (each agent sees the whole document and the whole registry) or
  `paired` (a pairing map decides which rules could apply to which units, Python computes the
  arithmetic, and a model is called only where the figures disagree or nothing is computable).
  `pipeline.resolve_review_mode` owns the rule: `--review-mode` always wins, otherwise
  `paired` under the local backend profile and `wide` under cloud. `server._default_review_mode`
  MIRRORS that function rather than importing it (a liveness probe must not import the
  pipeline); gate check 165 pins the mirror to the original.
- Where arithmetic can decide, arithmetic outranks the model: the finding carries Python's
  numbers whatever the model says about them.
- A band the rule does not state itself is read from the reference corpus's own TABLES
  (`scripts/reference_tables.py`), never from prose. Everything it does is structural and
  carries no domain or language vocabulary: a range is two same-unit numbers in one cell (no
  connector word anywhere, the column's declared unit overrules the token after the first
  number); a prose header unit is accepted ONLY if it composes to a unit the document under
  review itself writes; key columns are learned from the rule that cites the table; and a rule
  must name the RANGE column as well as the key column, or a completeness rule inherits a yield
  band. A row is matched by word containment over the unit's own labelled field VALUES, most
  specific wins, and a TIE IS REFUSED rather than broken. A finding cites the REF-* of the
  passage the table came from.
- The LOW side of a band is never settled by arithmetic where the rule qualifies it. The
  condition is detected structurally (the field labels the rule names that the comparison and
  its row key do not use); a qualified finding carries `conditional_on` and neither
  `amendment_from_finding` nor the computed-amendment pass will promote it. The pairing map
  records the evidence per unit as `band_conditions` before any verdict fires.

## Findings, citations, and grounding

- The verifiability gate (`scripts/verifiability_gate.py`) is pipeline behavior, not a
  governed change: an affirmative finding that cites nothing is downgraded to UNCERTAIN,
  flagged-and-kept (never dropped). It reuses the UNCERTAIN channel (genesis Part XXV) and
  INFRA-037 supersession (a `revision + 1` item). The fire-set is an explicit per-agent
  constant (LEGAL_ANALYST GROUNDED; PRACTICE_AUDITOR ALIGNED/COMPLIANT/VIOLATION/ANTI_PATTERN;
  FACT_CHECKER CONFIRMED); self-hedging verdicts never fire. Do not remove or weaken it.
- WEB-REF is a real citation form (`WEB-REF-NNNN`), minted by
  `reference_builder.add_web_reference` from the three structured web-source fields
  (FACT_CHECKER `source_url`, PRACTICE_AUDITOR `reference_url` and `reference_source`) and
  cited in `ref_ids` exactly like a REF-*. The corpus-REF regex uses the `(?<!WEB-)`
  disambiguation so a WEB-REF id is never miscounted as a REF. Inline free-text URL
  extraction is out of scope (convention-activated, deferred).
- The empty-convention carve-out (INFRA-042): the CONV-* requirement is relaxed ONLY when
  the convention registry is empty (an amendment then grounds on a REF-* or a WEB-REF-*).
  NEVER relax it when conventions exist; the rule is state-gated, not blanket.
- INFRA-044 appended five relations to the Finding record (`changed_from_prior`,
  `unchanged_from_prior`, `moved_toward`, `moved_away`, `absent_since_prior`) and four
  optional fields (`field_label`, `delta`, `band_distance_change`, `provenance`). A record
  carrying one of the five is ok-verdict, minted in Python from the operator-declared earlier
  version (`pipeline._prior_comparison`, `paired_review.prior_*`, `absent_checks`,
  `reference_tables.prior_values_for_scalars`), cited to the earlier paragraph, and NEVER an
  amendment. Anything unsettled (tie, unit mismatch, no citation, disagreeing bands, no key
  column) is refused on the record in the pairing map, never minted. The records are rendered
  by ONE renderer (`finding_record.render_prior_comparison`) in both `document_summary.md`
  and `review_findings.md` and carried in `review_data.json` under `prior_comparisons`; only
  `provenance=computed` records appear in that section. The figure reader (`_QUANTITY`) reads
  a currency symbol (Unicode Sc) or a short all-caps code before the number, accented unit
  letters, comma-grouped thousands, and a multi-word unit only when the document writes it
  after a figure more than once; no currency, unit or word is named in code.
- HONEST-OUTPUT-A (loop S2): every model-written finding stays in view and is marked, in both
  languages, "Written by a model. Not promoted to an amendment. Not checked by Python."
  (`finding_record.MODEL_FINDING_MARK`): in `document_summary.md`, `reviewed_document.md`,
  `_run_summary.md`, the console (its proof needs Node and says so when skipped) and the
  master's own `model_findings_not_promoted` section of `review_data.json` (rendered in
  `review_findings.md`). `tracked_changes.docx` carries amendments only, so no model finding
  and no mark. Only Python's records enter the earlier-version section and its band list. A model item there carries `model_claimed_verdict`,
  `checked_by_python: false` and `promoted: false` and never `confidence`, `record_verdict` or
  `verdict`. The producer sentence is generated from the stamps (`findings_provenance`, also a
  log event) and names only what ran; Python findings and model items are counted apart; a
  relation only a model reported is listed apart and marked, in the run summary and in
  `tools/score_corpus.py`. `audit_synthesis.md` counts "audit-trail patterns", not document
  findings, and counts an escalation once per distinct topic and payload
  (`audit_synthesizer.escalation_key`); one with no topic or no payload is reported apart and
  never becomes a pattern or a proposal. A judging model's sentence on a Python finding is a
  quoted note naming the model its call recorded (`paired_review.stamp_note_writer`, the
  computed bus post's `note_models`), "not recorded" otherwise, and notes are counted apart.
  A model item carries `reader_notes` (`paired_review.model_item_notes`: another unit's
  passage cited, the pairing map's rejection of its rule, no addends named, figures not in its
  unit). Every paired judging call is recorded with its outcome
  (`paired_review.judging_call_record`) on the computed bus post (`judging_calls`), on a
  `PAIRED_JUDGING_CALLS` post when no computed finding carries it, and in the pairing map; a
  failed call is `reply_failed` whatever it was asked, and a judged-absence call that returned
  carries its claims listed and refused (`absence_listed`, `absence_refused`). The deliverables
  state the calls made and the notes kept with ONE count (`paired_review.notes_on_python_findings`,
  one per Python finding carrying a model's note) under one label in every file, and count the
  judged-absence calls, never asked for a note, apart (`paired_review.judging_call_counts`). A docx comment's author is read from the
  amendment's provenance (`docx_builder.comment_author`): Python for an amendment built from a
  computed finding, the model agent for one built from a model's record, and the drafter only for
  an amendment taken from AMENDMENT_DRAFTER's own payload. Figures go
  through one formatter (`finding_record.figure_text`). A record without a `written_by` stamp is
  never Python's in any section (`finding_record.is_model_written`). An escalation naming an agent
  the run did not register is counted apart in `audit_synthesis.md`, with the names listed. The
  run summary states the INST_FINDER setting as "switched on/off for this run"; its internal name
  stays in `audit/agent_switches.json`. `review_data.json` and `delta_proposals.json` stay
  canonical English in a Turkish run (the Turkish reader gets the `.md` and `.docx` renders).
  None of the markdown deliverables, `_run_summary.md` or `audit_synthesis.md` carries an
  em dash. Check 278.

## Document role resolution and task modes

- The 4-tier role resolution chain (`scripts/role_resolution.py`) decides which files in
  `input/context/` are under review. First match wins: tier 1 operator manifest
  (`input/context/_review_targets.json`, authoritative, never overwritten), tier 2 a
  `review_targets:` field in `review_mandate.md`, tier 3 the sidecar + date cutoff (the
  legacy mechanism, writes nothing), tier 4 a guarded content-inference STUB behind
  `--infer-roles` (off by default). With NO manifest, `_populate_operational` behaves
  exactly as the date-cutoff-only mechanism did. Preserve that backward compatibility.
- Task modes are `--task review` (default) and `--task draft`. Draft mode phase 0 generates
  a memo from `--question` with the AMENDMENT_DRAFTER model of the run's profile (Opus under Cloud, the local drafter under Local; Local Draft not yet proven), writes it to
  `input/context/`, marks it the review target with `source=system_draft`, and the existing
  phases review it. A `source=system_draft` manifest is run-scoped: it is cleared at run-end
  (`role_resolution.clear_system_draft`) so it never persists as a stale tier-1 target. An
  operator- or convention-written manifest is deliberate instruction and is never cleared.
- The manifest's optional `prior` list (R6 / INFRA-044) names the grounding file(s) that are
  an EARLIER VERSION of a document under review. A prior is forced grounding (never
  promoted); a file that is both target and prior is reviewed, not compared, with a warning.
  `role_resolution.manifest_prior` reads it; the intake wizard asks for it. A review run's
  optional `--question` is folded into the run objectives AFTER the operator-path signature
  scan has read it, echoed in `document_summary.md` and `_run_summary.md`, never parsed, and
  never persisted under `input/context/`. No new CLI flag exists for the earlier version.
- The `_review_targets.json` manifest and the generated draft memo are deployment-local
  runtime artifacts, never source to commit. The memo is named `draft_memo_<slug>.md` (from
  `_draft_memo_filename`): the stable `draft_memo_` prefix makes it match the
  `input/context/draft_memo_*` ignore rule without catching the tracked corpus `*.md`, and
  the slug keeps it readable. It is written to `input/context/`, cleared at run-end by
  `clear_system_draft`, and its only durable copy lives in the gitignored
  `output/runs/<id>/deliverables/<doc_id>/memo.md` (BP-16).

## Writing an amendment

- Every amendment is rendered DETERMINISTICALLY from the typed Finding records
  (`paired_review.ensure_amendments_for_findings`). The AMENDMENT_DRAFTER model call is OFF
  by default. Measured, not preferred: with one run's arithmetic held identical and only the
  prose changed, recall moved 2/9 to 5/9, and a true band finding scored as a false positive
  for saying "exceeds the typical yield range" instead of naming the figures. Context for that
  figure (from the operator's own records): it was measured on 7 September 2026, on the
  synthetic wheat test, on code from the earlier `shimmer-fix` repository that is not in this
  repository's history; it was a single draw; it was a location count, not a reason-confirmed count; and the
  wheat test and its key are not published here.
- The COMPUTED FIGURES LEAD every comment, with their units, the registry rule id, the
  operator's own id and the REF-* the finding rests on. They were a fallback used only when the
  model said nothing; the model almost always said something. Never make them a fallback again.
- `--amendment-polish` enables an optional wording pass, narrow BY CONSTRUCTION: one call per
  finding, seeing only that finding, its unit and its rule; it may return exactly
  `paired_review.POLISHABLE_FIELDS` (`explanation`, `proposed_text`) and `apply_polish` merges
  those two and discards everything else. NO amendment is ever taken from the model, so it
  cannot introduce one the arithmetic did not produce, and the rule id, location, refs and
  figures are never in its reach. A failed or silent call degrades to the template, never to
  no amendment.
- `proposed_text` is the one field a model can supply that arithmetic cannot: the corrected
  line as it should read. `action` stays `flag` either way, because proposing wording is not
  deciding the change is safe to make.
- A comment opens with one plain sentence per relation naming the unit (with its heading), the
  rule, both figures with their units and the relation; a sum names the values it added and a
  product its two factors. An absence says what was checked in code instead of figures. The
  rule's own words follow, quoted, and a model's sentence comes last, labelled as the model's.
  Every template has a row for the second output language (tr) in
  `scripts/ui/localization_catalog.js`. A figure is written as the unit's own text writes it
  (`61 units`); a figure the unit does not write keeps the record's format (`16.0`, checks 171
  and 172). The two provenance sentences check 269 reads stay word for word.
- An amendment and its finding sit at the UNIT'S OWN PASSAGE: phase 5.5 cites the indexed
  passage that holds the unit's first line when exactly one does
  (`paired_review.unit_passage_refs`); a figure compared from elsewhere (a reference table, a
  bound) is cited as such (`compared_with_refs`), never as the location; a unit Python cannot
  place sits at document level, its finding and amendment cite no other unit's or the corpus's
  passage, and the amendment says so. A heading places a unit only at a passage whose first
  line it is, exactly (`paired_review.opens_with`). A comment that ends with a model's note says
  the figures were computed in code and only the quoted note is a model's
  (`COMPUTED_PROVENANCE_WITH_NOTE`).

## The sensitivity boundary

- `scripts/sensitivity_layer/` is the privacy home (a package, not a single module). It
  imports nothing editorial; only orchestration imports it.
- Sensitivity is operator-convention-defined, never model-judged. The operator declares
  a `confidentiality` or `redaction` convention category (CONV-*); the local Qwen
  redactor applies those rules to spans. Regular-shaped PII the operator authorizes
  (grouped-digit identifiers, number-plus-magnitude figures) is caught deterministically
  and merged with model proposals. The detector carries no language literals: all
  vocabulary lives in `config/language_redaction_cues.json` (operator-extensible per
  language).
- There is no engine-side default-categories floor. Redaction acts only on compiled
  operator rules; with none in force the run HARD-STOPS for a conscious operator choice
  (supply a compiling rule, or pass `--no-redaction-override` to declare the run
  redact-nothing, logged to the governance ledger). Never a silent default, never a
  silent ship. An approved span is scrubbed from every operator-facing artifact and
  "applied" means VERIFIED ABSENT by a post-apply grep gate (a surviving or unlocatable
  span BLOCKs).
- The full LAW-IV outbound masking layer is BUILT and WIRED (INFRA-041) and is
  OPERATOR-ACTIVATED: `LAYER_ACTIVE` defaults to False. When the operator activates a
  sensitive run, operator-marked spans are held local and replaced by typed placeholders
  before any network or API call, and every masking is appended to the exposure ledger
  (`durable/governance/exposure_ledger.jsonl`). Nothing sensitive reaches the live
  network flow without explicit operator activation; while the layer is inactive the run
  hard-gates and refuses to start unless the operator passes
  `--sensitivity-layer-inactive-override` (logged). `may_use_web` is an enforced control:
  an agent reaches the web only if its registry flag permits it.

## Three-input-type model (genesis Part XVIII)

- `input/context/`: the domain learning corpus. Read at BOOT by adaptive_spawn. Never
  receives deliverables.
- `input/operational/`: the documents under review. Populated by the pipeline at runtime
  from `input/context/` based on the 4-tier role resolution (tier 3 falls back to the
  cutoff in `config/review_scope.json`). Not manually populated.
- `input/conventions/`: the operator review framework (`review_conventions.md` +
  `review_mandate.md`). Parsed into `config/convention_registry.json` at BOOT.

## Entry points

- `start_shimmer.bat` -> `scripts/desktop_launcher.py`: primary Windows desktop
  starter. Uses read-only `preflight.startup_report`, explicit backend selection,
  shared `startup_settings`, an in-memory bearer token and an owned server.
  `scripts/desktop_server.py` stops on parent-pipe EOF or Stop and joins workers.
  The browser opens at `/console`; task, roles and privacy belong to the console.
  No automatic installation, provider call or review on desktop startup.
- `shimmer.bat` / `shimmer.sh`: the master launcher (venv bootstrap, preflight, menu).
  Option [1] offers Review or Draft; [2] chat; [3] server; [4] gate; [5] import wizard.
- `scripts/intake_wizard.py`: scan, classify, place, set the cutoff, choose mode, write the
  review-targets manifest. Driven by the launcher and by chat (as a subprocess).
- `scripts/chat.py`: the tkinter chat interface (Qwen NL parsing or command mode). Its startup line says only what the probe checked (libraries import, a model is named) and a request the model did not answer says so before the command parser's reply (check 310).
- `scripts/server.py`: the token-gated FastAPI dock. Config is env-driven (`SHIMMER_*`,
  read once at startup, printed to stderr); `SHIMMER_TOKEN_HASH` is required. The
  [runtime reference](docs/RUNTIME_REFERENCE.md) route table is the complete route list and gate check 167 fails if it and the app disagree
  in either direction; check 116 does the same for the `SHIMMER_*` env table.
  `/runs/{run_id}/findings` and `/runs/{run_id}/pairs` serve the STRUCTURED review (typed
  Finding records off the bus, and the pairing map with no document text);
  `/runs/{run_id}/deliverables` stays the human artifact. The pairing map's `absence` record
  and a finding's `absence_path` are on disk and on the bus but not yet in the two routes'
  projections (recorded in docs/RUNTIME_REFERENCE.md).
- CONSOLE-A (loop S7): the console's views of saved model replies, unpromoted model findings,
  agent switches, the run report and the test change request log read `scripts/console_views.py`
  projections through token routes; saved replies are shown as metadata and outcomes, never text;
  every model finding carries `MODEL_FINDING_MARK`; a sealed run (a marker walk that fails closed)
  shows counts and timings only (`/activation` its decisions as counts, a pending question on
  `/approvals` and `/runs/{run_id}` its timings only; its run record on `/runs/{run_id}` and
  `/runs` document, file and target counts and no name, question or error text) and its
  per-flaw routes, with
  `/undated-documents` and `/convention-assignment`, answer 403; only `/health` and `/console`
  answer without a token (FastAPI's own documentation routes are off). The Annex B.4 reasons live
  once, in `scripts/run_report_text.py`. The screenshots in `docs/loop/ui/` are rendered by
  `tools/console_screenshots.py`: the run pages from the committed fixture only (replies under a
  fixed clock inside the run window), the test-change-requests pages from the repository's own
  `docs/test_change_requests.md` as of the render; two renders of one tree are byte-identical.
  The sealed note names the document, file and target names it withholds and that the Annex B.4 reasons are shown under Agent switches; on the multi-round section it sits directly under the heading (open item 55). Checks 298 to 306.
- `scripts/harness/`: one agent, one unit, one rule, one backend (`run_agent.py`), plus
  `probe_arithmetic.py` (can the model do the arithmetic with no review framing at all) and
  `score_envelope.py`. The harness never builds its own prompt: it builds the wrapper the
  pipeline builds, so the bytes reaching the model are the pipeline's bytes. Check 146 holds
  that property; it fails if the harness grows its own prompt assembly.
- `tools/run_local_demo.py` (`.ps1`): the local run wrapper. Starts the pipeline in-process
  (its filename is denied in shell commands), adds `--backend-profile local` if none was
  named, passes everything else through, and samples RAM/VRAM to a JSON file rewritten after
  every sample so the peaks survive a kill.
- `Dockerfile` / `compose.yaml` / `tools/entrypoint.sh`: the container. The image copies
  source (`scripts/`, `config/`, `tools/`, `corpus_ingest/`, the three root markdown
  files, `VERSION`, `docs/RUNTIME_REFERENCE.md`, `requirements.txt`), the two frozen evaluation protocols the decoding policy is
  read from (`tuning/producer_v3/evaluation_protocol.json`,
  `tuning/auditor_canonical_execution/evaluation_protocol.json`), the Producer DEV rows
  and rendered prompts check 263 reproduces (`tuning/producer_v3/dataset.json`,
  `tuning/producer_v3/prepared_dev.json`) and the three declared
  synthetic `benchmark/fixtures/`
  files used by the condition, severity and external-rule checks; the entry point takes `serve`, `run` (through
  `tools/run_local_demo.py`, never naming the pipeline file) or `verify` (the gate with
  `--offline`), `verify` by default. The weight layers (`--build-arg BAKE_WEIGHTS=true`) sit
  BEFORE the source layers so a source rebuild reuses retained weight cache; keep
  that order. A local cache export under output/ protects against builder GC.
  The baked build prepares bge-m3 safetensors with a temporary patched CPU
  torch reader; runtime pins stay unchanged and old torch refuses pickle conversion.
  The offline probe requires five votes and fails on attempted network access.
  The local generation loader resolves a cache-only snapshot before loading, so
  nested custom-generation lookups stay local too; unapproved overrides refuse.
  `.gitattributes` pins shell scripts to LF; the Dockerfile strips a trailing CR
  regardless. A container gate loads models on the GPU: never overlap it with the host gate
  or a run.
- Local PROCESSOR extraction has an 8192-token contract allowance, measured from
  complete source envelopes; the local backstop permits it. Ordinary phase budgets
  and cloud budgets stay unchanged. The local editorial board now reaches its
  existing configured 8192 allowance, formerly clamped to 4096. Phase-5 auditors
  receive draft availability and truncation explicitly; failed-contract
  best-effort objects are withheld.
- DECODING-A: every local generate site (`agent_wrapper.call_local`, `agent_wrapper.call_qwen`,
  the chat parser) decodes under the frozen evaluation policy, read at call time by
  `scripts/decoding_policy.py` from the protocol files `config/decoding_policy.json` names
  (`tuning/producer_v3/evaluation_protocol.json` for `local_producer`,
  `tuning/auditor_canonical_execution/evaluation_protocol.json` for `local_auditor`, each
  digest-pinned with CRLF normalised to LF; a drifted protocol refuses the call before any
  load, and `final_models.admit_ordinary` refuses the run). No decoding value is ever typed
  into a wrapper. Only the protocol's `max_new_tokens` is withheld (an evaluation cap; the
  pipeline's per-agent budget stays in force); everything the protocol does not name
  (`repetition_penalty`, `temperature`, `top_k`, `top_p`) stays with the checkpoint's own
  generation config, exactly as during evaluation. REDACTOR (`qwen_local`) has no frozen
  protocol: its greedy policy is DECLARED NEW in the same file, never called restored. The
  stop-reason logic reads the stop set generate() actually used (the policy's, else the
  model's own). Measured, not preferred: `final_models.verify_runtime` sets strict torch
  determinism for the whole process, and run 88323b86 (2026-09-17), which passed no decoding
  kwargs, let the Producer checkpoint's own top-p sampling config build a warper whose
  float32 CUDA cumsum has no deterministic implementation, so every local call raised
  RuntimeError at its first sampling step. Check 262, the integration gate and
  `tools/ordinary_final_decoding_gate.py` (every family, instrumented cumsum, strict mode
  on CUDA) hold this; each has neutralize/fail/restore/pass proofs.
- DECODING-B (loop S5, D-S14 item 3): the compact producer (PROCESSOR on `local_producer`
  bound by `compact_contracts.bind_producer` with the validated messages, report_optimized)
  decodes under a logits constraint built per request from that request's OWN declaration
  (`scripts/contract_decoding.py`, declared in `config/contract_decoding.json`), with
  `compact_contracts.producer` UNCHANGED behind it, the prompt bytes unchanged (check 263) and
  the frozen decoding policy unchanged (greedy stays greedy; the constraint rides beside the
  kwargs as one logits processor, `contract_decoding.for_call`, the only place it is built).
  Only the canonical reply can be generated: sorted keys and compact separators (the form all
  84 DEV replies of checkpoint 168 take, NOT the key order the contract's example names), one
  item per owned alias in owned order, every key present, claims only CLM ids written in that
  span's text, refs only that span's grounded set (the validator's: REF ids in its text and
  the passages `bounded_extraction.grounding` placed in it), no id twice, status extracted
  exactly when claims, questions or uncertainty is non-empty, questions and uncertainty the
  model's own non-blank, unrepeated JSON strings; or the refusal object, which stays the
  model's to give and the validator's to refuse. A token the model would have chosen anyway
  is never changed; every step where its top token was not admitted is counted. Every
  constrained call records `decoding_constraint` (name, version, declaration and request
  digests, steps, interventions, dead end) on its reply record and in its usage (the
  `backend_invocation` telemetry row); every other call records none. Measured, not
  preferred: L7, L8, L10 and L11 refused 52 of 283 compact partitions (invented CLM ids in
  35 calls, two of them runaway lists to the 1536 cap, a dropped uncertainty key, a
  context-only alias, one item for two spans, the neighbouring span's REF), each repeated
  byte for byte by a deterministic re-ask; all 52 saved replies leave the constrained
  language, and all 84 frozen DEV replies stay inside it with no intervention. The DEV
  figure (102 of 102 items, 75 of 84 rows valid, 9 refusals) is re-measured under the
  constraint by the replay path `sdpa_constrained` (`benchmark/baselines/replay_prompts.py`,
  `extract --call-ids --dev`); measured on the A10 by replay R1 (D-116): all 52 failing
  partitions valid under the constraint, DEV 75 of 84 valid with 9 refusals as before, 0
  interventions on the DEV rows; adopted. The replay path changed `tools/ordinary_final_run.py`
  (`REPLAY_PATHS`), so bundles sealed before it refuse with `Controller source changed`.
  Check 295 and the decoding gate (strict determinism on CUDA) hold this.
  The same processor carries the ENVELOPE of four agents (D-S14, s5_diag_b3 K9 to K11; K8):
  VERIFIER and PRACTICE_AUDITOR on local_auditor and ARCHIVIST and EDITOR_CLERK on local_producer
  (`config/envelope_decoding.json`, `contract_decoding.EnvelopeGrammar`, built per call by
  `for_envelope` from the agent's own contract in `config/agent_contracts.json`; a wrapper bound
  to a compact contract gets none). Admitted: an optional opening fence, the envelope
  `{agent, doc_id, items}` in that key order with `agent` the calling agent and `doc_id` any
  string, flat items opening with the agent's declared `leading_keys` in order, then the other
  required keys (`CORE_ITEM_REQUIRED`, then the contract's `required`) and any other declared
  field name (the core optional and runtime keys, the contract's fields, the finding_record
  fields) in any order, each at most once, the item closing only when every required key is
  written; the declared `confident` alias in its key's place; a required value neither null nor
  empty; JSON whitespace in runs of at most 16; the stop token only after the envelope's closing
  brace, after which anything may follow. `leading_keys` is the order every saved valid item
  writes: VERIFIER every required key in the validator's order, PRACTICE_AUDITOR every one but
  `explanation` (2 valid L12 replies write it last), ARCHIVIST its confidence key first,
  EDITOR_CLERK its confidence key first. EDITOR_CLERK was declared at the S5 close in place of
  the removed K8 kind stamp (ENVELOPE-B): measured on all 61 of its saved replies in L7, L8,
  L10, L11, L12 and L12b with the Qwen tokenizer, the 49 valid ones (26 items, `kind` second or
  last) are inside the language with 0 interventions, and all 12 without `kind` (4 refused, 8
  accepted only by the stamp, which the tool counts as `stamped` from the run's
  `contract_normalized`, never as valid) leave it where the item closed; which key the model
  writes in its place is not known until a replay on the model is read. NOT
  constrained, measured: enumerated values (36 of 74 valid VERIFIER items write a `finding` and
  123 of 1,838 valid PRACTICE_AUDITOR items a `verdict` the contract does not declare, which the
  validator accepts) and `doc_id`. Measured on every saved reply of the three agents in L7, L8,
  L10, L11 and all 37 L12 entries with each backend's tokenizer
  (`tools/envelope_decoding_measure.py`): all 1,932 valid replies (38 VERIFIER, 1,838
  PRACTICE_AUDITOR, 56 ARCHIVIST) are inside the language with 0 interventions, and all 24
  failed ones leave it. It does not stop a repetition inside a string or an item list that runs
  to the output cap. Measured on the A10 (R2a, R2b; D-132, D-134): no valid reply changed, and
  14 of the 24 failed calls became valid; 10 stayed invalid (8 VERIFIER at 2,048 tokens, one item
  per reference; 1 PRACTICE_AUDITOR at 768, one sentence repeated; and 1 PRACTICE_AUDITOR the
  constraint kept open for its required `explanation`, which then ran to 768, open item 47).
  VERIFIER's output allowance is now 4,096 (`pipeline.VERIFIER_MAX_TOKENS`, D-134; FACT_CHECKER
  keeps `AUDIT_MAX_TOKENS` 2,048, check 216), measured by replay R2c on the A10: of those 8
  VERIFIER prompts, 4 end on their own at 2,342 to 3,590 tokens and pass the unchanged
  validator, 4 still reach 4,096, with no out-of-memory failure and the same 21.89 GB peak. Not
  covered: the other local_producer agents and the other local_auditor agents (no measurement).
  EDITOR_CLERK's constraint has no replay on the model yet (fixtures and saved replies only).
  The decoding checks' probe agent is CITATION_RESOLVER, so its kwargs test carries no
  constraint. The cloud replay (`replay_prompts.py extract --agents ...`, one model a
  file, then `run` on sdpa and sdpa_constrained, judged by the agent's own validator) was read
  as R2a and R2b, and the constraint adopted (D-132, D-134). No bound controller file changed. Check 297
  and the decoding gate hold this.
- HIDDEN-A (loop S5, D-079): every child process the operator-side tools start (the
  controller, the bound wrapper, both watchdogs, the provider adapter, the general launch
  wrappers, the progress and status readers, and every file under `tools/loop/`) passes its
  creation flags through `cloud_run_common.no_window`, which ORs in the Windows no-window
  flag and changes nothing elsewhere; a child that must keep the operator's console says so
  with `keep_console` (an interactive ssh passphrase, the sealer's foreground re-exec), and a
  `runner` defaulting to `subprocess.run` is given `cloud_run_common.hidden_run`. Measured,
  not preferred: the detached controller has no console, so each ssh, scp, ssh-keygen and
  curl it started opened a visible window on the operator's screen. The controller check and
  gate check 292 scan every start's AST and run the controller, adapter, termination client
  and progress reader against fakes that record each start's flags. This changed six bound
  controller files, so bundles sealed before it refuse with `Controller source changed`. The console checks' start scan (check 306) refuses a `creationflags` that also sets CREATE_NEW_CONSOLE or DETACHED_PROCESS, beside which Windows ignores the no-window flag, and counts `os.exec*`, attribute chains and modules reached by `importlib.import_module` or `__import__` (loop S7 round 3).
- WAVES-A (loop S5, D-076, INC-019): a semantic gather larger than the scheduler's
  `max_pending` (256) runs as consecutive waves of at most that many calls
  (`semantic_waves.run_waves`), in source order, every chunk shown the ONE bus snapshot and
  depending on the ONE parent set read before the first, posts published in source order; it is
  never refused for its size, and a gather at or below the bound is one `run_wave` exactly as
  before. Measured, not preferred: a development ContractNLI agreement with 289 judging plans
  refused the whole run before this. Check 291.
- LEDGER-CHECK-A (loop D-S16 item 1): `tools/loop/request_ledger_check.py` checks the
  operator's private request ledger (passed with `--ledger`, never committed) against the loop
  specification itself: every Annex C row and every `D-Sn` entry with its numbered items and
  lettered sub-items needs a row (lettered list lines one row each; letters inside a sentence
  one row for the item or one per letter), a row matching no item fails (relayed notes, `N-`,
  are exempt), every DONE row's decision heading, commit and backticked path must resolve, and
  a RUNNING row (not `RUNNING (standing)`) unchanged for 24 hours that names no running launch,
  lane or role session fails. Running is read from evidence, never a name alone: a launch
  only when the budget ledger (`--budget-ledger`, default the private folder's
  `budget_ledger.jsonl`) holds its launch with no termination, a lane only when
  `git worktree list` shows its branch, and a role session or agent never (no offline record),
  so a row naming only those is not exempt. One count line; exit 1 on any failure. Run it whenever the ledger
  changes, in every checker round, and before every merge, tag and push. Check 296 runs its
  proofs on fixtures only (`tools/loop/request_ledger_check_checks.py`).
- EXTRACTION-A: under `report_optimized` the PROCESSOR call sends EXACTLY the two turns
  checkpoint 168 was evaluated on (`compact_contracts.validated_messages`): the compact
  contract plus the frozen semantic policy as the system turn, read from
  `config/compact_extraction_prompt.json` and never typed into a script, and one canonical
  payload (`context_only_spans`, `production_contract`, `required_refs`, `role`,
  `routed_rules`, `source_spans`, `supplied_refs`; sorted keys, compact separators) as the
  user turn, through the model's own chat template. No context package, reference passages,
  rules, bus, briefs or anchor reach the model on that path. Check 263 renders a DEV row
  through the runtime builder and requires the protocol's recorded prompt sha256 byte for
  byte. Measured, not preferred: run 110990c1 (v5, 2026-09-18) ran the checkpoint on a
  14k-character agent prompt with the contract mid-prompt and failed 4 of 4 partitions,
  where the same checkpoint had 102 of 102 valid items on the 2.5k-character validated shape.
- EXTRACTION-B: a cited ref is grounded by PYTHON'S OWN PLACEMENT of indexed passages in
  source spans (`bounded_extraction.grounding`, one paragraph splitter shared with the
  reference index, `reference_builder.paragraph_ranges`), never by an id written inside the
  span's text alone. Every indexed passage inside a span is shown as ` (REF-NNNN)` at its
  end, the way the training spans carried their references, and the validator's citable set
  is the same placement. An id the index does not hold, or one that names another span's
  passage, is refused as `Ungrounded extraction evidence` exactly as before. v5: no real
  document carries inline ids, so every non-empty refs array was refused; the v5 raw outputs
  are the proof, task-000003 passes and task-000008 (each ref one paragraph off) is refused.
- ENVELOPE-A: a model-written spelling of a core key is read as that key ONLY when it is
  declared in `config/agent_contracts.json` `core_field_aliases` (today `confident` for
  `confidence`), the canonical key is absent, and the value maps without interpretation
  (`CONFIDENT`/`UNCERTAIN` as written, `true` to CONFIDENT, `false` to UNCERTAIN); every
  application is recorded as `contract_normalized` on the result, the bus post, the
  observation row and the telemetry call record. v5: the tuned Producer wrote `confident` in
  three of six item-bearing calls with the right value each time and each failed on that key
  alone; the same base under sampling never did in 145 items; the flip is one argmax at the
  key's first token, so the parser holds whether the origin is the adapter or value priming.
  Never widen the alias list from a hunch: an alias is a measured model habit, declared.
- ENVELOPE-B (D-S14, K8) is REMOVED (S5 close). It let a contract declare `single_kind_stamp`
  so Python wrote EDITOR_CLERK's `kind` where the model wrote none (and refused a written kind
  other than the declared one). It breached H9: editing `config/agent_contracts.json` is a
  product change allowed only where a stage specification calls for it, and none did; and it
  supplied a value the model did not write, after failures were seen (D-S14 item 3). The key,
  `agent_wrapper.single_kind_stamp` and `stamp_single_kind` are gone: the contract file is byte
  for byte its content before the K8 commit (a448af1) and the validator is as before K8 (a
  missing or empty `kind` is refused for every agent; a written kind is checked for presence
  only, the wrong-kind refusal going with the key it was read from). Check 264 proves that
  state, each proof neutralised by putting K8 back. The cause is fixed in decoding instead:
  EDITOR_CLERK is a declared envelope agent (DECODING-B, check 297), so an item cannot close
  before `kind` is written. What depended on the stamp, from the saved evidence: 8 B3 entries
  had one EDITOR_CLERK item stamped, and the 5 of them that passed integrity (L12
  `27_f3_s3101_htmn`, `34_f6_s6101_pfqp`; L12b `02_f1_s1102_mstx`, `04_f5_s5102_hcvm`,
  `05_f5_s5101_bmpd`) passed only through it, since a refused EDITOR_CLERK call is a
  `required_contract_failure`; the other 3 (L12 `30_f5_s5101_bmpd`, `32_f5_s5102_hcvm`, L12b
  `01_f1_s1101_cvjx`) failed for other reasons as well.
- VERIFIER-A: the typed-record worked example is built from the agent's own `required` list
  (`_record_example_required`) with the contract's DECLARED values where it enumerates them
  (FACT_CHECKER's verdict CONFIRMED, VERIFIER's finding MATCH; `_declared_values`, never a
  sentence about a value), and the section names the agent's own verdict-bearing field
  (`_own_verdict_field`: `verdict`, else `finding`; VERIFIER has no `verdict`). A document with
  no accepted PROCESSOR items records VERIFIER as `not_called` (`processor_draft_unavailable`)
  and its advisory pairing as unavailable (`auditor_pairs.record_unavailable`); a
  partition-merged delivery with partitions missing reaches both auditors as a PARTIAL draft
  (`_accepted_draft`, `processor_draft_partial`, `processor_missing_partitions`, the note).
  FACT_CHECKER keeps its call. Checks 265 and 268 hold this.
- PAIRING-A: `auditor_pairs.build` refuses at the DELIVERY level only for a single PROCESSOR
  call (`delivery_scope` is `single`): its best-effort object is not a draft. A
  partition-merged delivery already carries only the items of accepted, untruncated
  partitions, each bound to its span by an ownership receipt, and the fidelity comparison is
  span-local by construction, so its items pair even when another partition is missing; such
  pairs require a receipt (`partial_delivery_without_receipt` otherwise) and carry
  `delivery: partial` on the pair record, the coverage event (`pairs_from_partial_delivery`),
  the run summary and `FINAL_STATUS.json`. Document-level completeness stays where it belongs:
  `semantic_incomplete`, `stopped`, `pipeline_not_completed`. Measured, not preferred: the old
  gate read the whole delivery per item, so one refused partition discarded every accepted one
  and the advisory classifier had no pairs in v5 or v6 (it never actually fired: VERIFIER was
  skipped upstream, which the partial draft now prevents). VERIFIER's RENDERED payload shows
  each pair as `pair_id` (the join key), `producer_item`, `source_evidence.text`,
  `source_ref_ids`, `auditor_relation`, `classifier_status` and `delivery`
  (`auditor_pairs.pair_view`), and each draft item without `DRAFT_ITEM_RUNTIME_KEYS`
  (`draft_view`); the pair records, telemetry, reply records and bus keep every identifier.
  Measured, not preferred (D-S14 K2): the ten L8 VERIFIER prompts of 44,467 to 54,657 tokens
  ran out of GPU memory on the A10 before their first token; the same prompts measure 17,932
  to 23,668 tokens projected (Phi tokenizer, offline), and none of the 22 saved VERIFIER items
  carried a pair or producer identifier to join by. Check 266.
- EXTRACTION-C: a bounded request carries at most `owned_spans_per_request` owned spans
  (declared in `config/compact_extraction_prompt.json`, today 2, read by
  `compact_contracts.request_size`), because every training input and DEV row of checkpoint
  168 carries one or two; the pipeline used to send four. v6 lost the exact compact shape on
  its one three-span request and kept it on every validated-layout request (102 of 102 DEV
  items, four of them all-empty). Under the frozen policy an entry without claim ids or an
  explicit absence statement is CORRECTLY extracted as `empty` with no refs (20 of 20 training
  targets and 4 of 4 DEV answers), so partition 1's emptiness was right and the missing key
  was the whole failure; no tolerance was added. Check 267.
- `scripts/pipeline.py`: the pipeline driver (the flags above).

## Key paths

- `config/`: governance and compiled config (`constitution.json`, `agent_registry.json`,
  `agent_contracts.json`, `convention_registry.json`, `review_scope.json`,
  `editorial_board.json`, `language_redaction_cues.json`).
- `scripts/`: the pipeline, the agent modules, `sensitivity_layer/`, `ontology_*`,
  `role_resolution.py`, `intake_wizard.py`, `chat.py`, and `archived/` (retired tooling).
- `input/`: `context/`, `conventions/`, `operational/` (see above).
- `output/runs/<id>/`: per-run artifacts. BP-16 layout: `deliverables/` holds one subfolder
  per document (named after the document, doc-name prefix stripped from each file:
  `review_data.json`, `review_findings.md`, `tracked_changes.docx`, `grounding_summary.md`,
  `document_summary.md`, `reviewed_document.md`) plus a top-level `_run_summary.md` index;
  a draft run also keeps the memo as `<doc_id>/memo.md`. The canonical basenames live in
  `run_context.DELIVERABLE_FILENAMES` (one source for the writer and the pipeline). `audit/`
  (with `pairing_map.json`, carrying per unit `band_conditions` and `prior_comparisons` and
  per document `prior_orphans`) and `logs/` sit alongside. `logs/call_evidence.jsonl` records,
  per model call, the structural identifiers of what the call was shown (unit, neighbour unit
  ids, heading, reference ids supplied and rendered, rule ids, agent, backend, model, run,
  call id), never text; the call id joins the cost row and the bus post
  (`scripts/call_evidence.py`). `scripts/fn_evidence.py` classifies every missed expected
  defect into one of four evidence classes from saved artifacts only, through the scorer,
  which is the only reader of a key. Runs never overwrite each other.
- `durable/`: learned and governance state that survives reset: `learnings/`, `cache/`,
  `global/`, `governance/`, `reference/`.
- `ontology/stores/`: the cross-run learning graph (capture, graph, GNN state). Its storage
  layer is `scripts/ontology_store.py` (night W7): every record carries a scope enforced on
  every read and write (one value, `DEFAULT_SCOPE`, until an engagement concept exists), a
  provenance struct `{time, agent, run, type}` (type `document`; the rule-derived type is
  declared unfilled until that path has run), a live store plus an immutable log
  (`provisions_log.jsonl`) with supersession decided at the query layer, and supersede built
  but delete deliberately not. `tools/archive_ontology_stores.py` archives and empties the
  stores outside the repository.
  FOUR NODE TYPES share one scope and each has its own reader: `Provision` (capture),
  `Relation` (job 2), `Resolution` (job 3) and `ExternalRuleResolution` (external-rule
  answers, `scripts/external_rules.py`). `ontology_reader.provenance_summary` tests an
  ALLOWLIST (`node == "Provision"`, a record with no node being one), never a list of types
  to exclude: both later node types leaked into the provision count when they were added, and
  an allowlist is what kept the fourth out of it.
  `scripts/ontology_reader.py` reads provisions and relations (`GET /ontology`,
  `/ontology/provisions/{id}`, `/ontology/relations`, the console's Agents page, and its own
  CLI inspector); `ontology_conflicts` and `external_rules` read their own resolution nodes
  through the same scoped storage layer (`GET /ontology/conflicts`, the external-rule answers). It
  carries identifiers and provenance ONLY, never a provision's text.
  `scripts/relation_extract.py` finds relations between units; EVERY pattern lives in
  `config/relation_patterns.json` and none in code (S5), the embedding ranker is INJECTED
  never imported, and an ambiguous reference is REFUSED rather than resolved to one candidate.
  `scripts/ontology_conflicts.py` holds the operator's decision: a store-versus-rule
  disagreement is REFUSED in that run with both sides named, the answer is written to the
  ontology under a stable conflict id so the same conflict is never put to the operator
  twice, "keep refusing" is a real third answer, an unrecognised answer is refused rather
  than stored, and the override rate carries its own not-statistically-meaningful caveat
  inside the return value. NOTHING in a review reads a relation or a store-versus-rule conflict today; a review
  reads stored external-rule answers only when `input/external_rules/` exists.
  `scripts/ontology_candidates.py` (job 4) proposes candidate provision pairs from the
  persisted encoder: a forward pass only, it never trains and never writes state. THE GNN
  DOES NOT RESET ITS WEIGHTS EACH RUN (a belief stated for weeks and corrected 2026-09-11):
  `gnn_update` restores persisted weights and keeps a trained-node high-water mark, so a
  second update over the same graph has a zero delta and unchanged weights. It has learned
  nothing because the TIER-2 SIGNAL IS EMPTY, not because it forgets. Every candidate set
  and the state summary therefore carry `ranked_on` (graph structure: node type, degree,
  edges), `learned_relevance: false` and `tier2_signal: empty` IN THE RETURN VALUE, and
  check 213 fails if that qualifier is ever replaced by a learned-relevance claim, including
  one that mentions the phrase without denying it. Never present a candidate set as learned
  relevance.
- `corpus_ingest/`: the corpus ingestion contract, validator, and grounding-files helper.
- `benchmark/keys/`: the answer key, control document, ledger scripts and frozen scorer for
  recall measurement. GITIGNORED, never committed, never opened by an agent. Only the scorer
  reads the key. Check 145 (the contamination probe) scans `config/`, `scripts/`, `tests/`
  and the harness fixtures for the key's figures and fails if one appears; a planted figure
  in the repo would make every recall number meaningless.
- `tools/`: operator-facing run wrappers (see Entry points).

## Commands

Every hand-typed run needs both override flags (shown on the first two lines below and
implied on the rest): without `--sensitivity-layer-inactive-override` the run exits 6 while
the LAW-IV layer ships inactive, and without `--no-redaction-override` it hard-stops at the
redaction gate whenever no operator redaction rule compiles, which is the case for every
shipped corpus. The launcher, the wizard and the server add both for a normal run.

```
py -3.12 -X utf8 scripts/verify_session1.py        # verification gate (run every session)
py -3.12 scripts/pipeline.py --non-interactive --sensitivity-layer-inactive-override --no-redaction-override
py -3.12 scripts/pipeline.py --task draft --question "..."   # draft mode
py -3.12 scripts/pipeline.py --review-mode paired --pairs-per-unit 3   # paired review
py -3.12 -X utf8 tools/run_local_demo.py --non-interactive --sensitivity-layer-inactive-override --no-redaction-override
py -3.12 -X utf8 scripts/harness/run_agent.py --agent NAME --profile local|api \
    --unit-file U --unit-id u01 --rule-file R --rule-id CONV-001 --out results.json
py -3.12 scripts/pipeline.py --list-snapshots      # list saved snapshots
py -3.12 scripts/pipeline.py --save-snapshot NAME  # snapshot learned state
py -3.12 scripts/pipeline.py --load-snapshot NAME  # restore a snapshot
py -3.12 scripts/pipeline.py --reset-snapshot      # strip back to seed defaults
py -3.12 scripts/bus_viewer.py --follow            # live bus and cost stream
```


## Report Recommendations comparison path

The operator-authorized local optimization is documented in
`docs/fix/REPORT_RECOMMENDATIONS_IMPLEMENTATION.md`. `report_optimized` is an
explicit ordinary local topology; reference defaults stay available. Its
PROCESSOR wire aliases hydrate into the unchanged canonical source extraction
contract, with mandatory ownership/coverage and a provisional 1536-token bound;
the call itself is sent in the validated two-turn shape with Python-placed
reference markers (EXTRACTION-A and EXTRACTION-B above).
A source ledger never silently omits preamble or table-surround text. Do not
promote this path based on fixture/tokenizer measurements alone. No full model
run, cloud work or multi-round execution was authorized by this implementation.
The dedicated ordinary safe gate avoids those workloads. Preserve exact typed
comparison eligibility, cross-family validation, ordered posts and explicit
semantic incompleteness when extending it.
