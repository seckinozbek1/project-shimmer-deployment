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
  S5's merge refuse the same way and must be re-sealed. D-S17 item 1 (then at most two loop
  instances) changed `tools/ordinary_final_cloud.py`, `tools/loop_budget_guard.py` and
  `tools/loop/instance_reaper.py`, so every bundle sealed before it refuses with
  `Controller source changed` and must be re-sealed. D-S57 item 4 (four loop instances) changed
  `tools/loop/instance_reaper.py` and `tools/loop_budget_guard.py` again, so bundles sealed before
  it refuse the same way and must be re-sealed. D-S71 item 2 (eight loop instances, D-323) and D-S79 (sixteen, D-337) changed
  the same two files again, so bundles sealed before it refuse the same way and must be re-sealed
  (no count limit since D-S95).
  Arm G (GATE-ARM-A, D-S75) and the declared type order (D-S78 item 2) changed
  `tools/ordinary_final_run.py`, `tools/ordinary_final_cloud.py` and `tools/loop_budget_guard.py`
  in the same re-seal. The gate-pin rule (`ordinary_final_run.pin_held`, lane/gate-pins) changed
  `tools/ordinary_final_run.py`, so bundles sealed before it refuse the same way and must be re-sealed;
  so did admitting check 0 (lane/gate-zero). D-S84 (salvage, then stop) changed `tools/loop/instance_reaper.py` and
  `tools/ordinary_final_cloud.py` again, so bundles sealed before it refuse the same way and must
  be re-sealed. D-S95 (no maximum number of loop instances; the type rule's tiers above the A10 by
  the fastest route, with exactly the GPUs a run needs) changed `tools/loop/instance_reaper.py`,
  `tools/loop_budget_guard.py` and `tools/ordinary_final_cloud.py`, so bundles sealed before it
  refuse with `Controller source changed` and must be re-sealed; running instances keep their sealed
  bundles and are not touched (D-S96 item 1). D-382 (the reference-pair rule keyed by machine type,
  one type per comparison, the exact GPU count in the declared order and the per-instance overrun
  reserve) changed `tools/loop_budget_guard.py` and `tools/loop/instance_reaper.py` again, so bundles
  sealed before it refuse the same way and must be re-sealed. The bound wrapper's type-rule admission (`tools/ordinary_final_bound_cloud.py`,
  `sealed_candidates_admitted`: a declared order admitted as the controller and the bound preflight
  admit it) changed a bound file, so bundles sealed before it refuse the same way and must be
  re-sealed. D-101 (after L7, D-100) changed `tools/ordinary_final_run.py` again (a
  declared multi-round run is assessed without the Producer 168 model-call requirement), so
  bundles sealed before it refuse the same way and must be re-sealed. Open item 37 (disk on the instance:
  the runner's `evidence/disk_usage.json` before, sampled during and after the workload, and
  the evidence packer's `disk_after_evidence.json`) changed `tools/ordinary_final_run.py` and
  `tools/ordinary_final_cloud.py`, so bundles sealed before it refuse the same way and must be
  re-sealed. Arm L (D-S13 item 6d, ARM-L-A) changed `tools/ordinary_final_run.py` and
  `tools/ordinary_final_cloud.py` again, so bundles sealed before it refuse the same way and must
  be re-sealed. D-S50 (the filesystem verified on the provider's own inventory) changed
  `tools/lambda_experiment_provider.py`: one read-only operation, GET `file-systems`, returning
  each filesystem's id, name, region, bytes used, whether it is in use and any field the provider
  names a capacity, and nothing that creates, changes or deletes one (`allowed`, proved in the
  controller and metadata checks), so bundles sealed before it refuse the same way and must be
  re-sealed. D-322 (D-S70 item 4, an issue's declared unit) changed
  `tools/ordinary_final_run.py` (`LIVE_ISSUE_FIELDS`, `live_case_fields_error`), so bundles sealed
  before it refuse the same way and must be re-sealed. D-398 (the asset copy probe's
  deadline scaled with the archive's size, and the filesystem's free space read before a seed)
  changed `tools/ordinary_final_cloud.py`, in the same re-seal. D-401 adds
  `tools/loop/cloud_reference_spend.py` (the spend reader the guard imports) to the binding, and
  D-S107 items 1 and 5, D-403, D-412 item 2 and D-421 (F7) changed the controller, the reaper, the
  guard and the bound wrapper again, all in the same re-seal. F1 (D-421) adds
  `tools/loop/standing_orders_check.py`: before a real launch (and a real seal) the guard runs the
  checkers of standing orders 1 (the filesystem copy), 2 (the API key and its approvals) and 3 (the
  budget and its warnings) on the main checkout's records (`loop_budget_guard.standing_orders_refusal`)
  and refuses in one line naming each that does not hold; the bound preflight runs them too. While
  order 1 reads a past launch that uploaded with no copy and no `ASSET_COPY_REASON.md`, every real
  launch and seal is refused until that reason is recorded. The guard and the preflight read the
  orders through `standing_orders_check.launch_refusals(ctx, (1, 2, 3))` alone, a list of the orders
  broken or unable to check, never a checker's truthiness (its state is a word). So a Lambda launch
  also waits on order 2: every paid API run since D-S106 approved by one "Seckin: evet" line with a
  rule-named key source. D-436: the comparison registry and the
  asset copy history live in the MAIN checkout's private folder through git's common directory, as
  the spend store and the salvage folder do (`instance_reaper.main_private`, resolved once per
  process; a salvage folder git cannot find reads as no request); D-S121 (D-453) keeps two ceilings:
  the guard and the reaper count Lambda alone toward its hard stop (299, budget 300, a budget line's
  `warning_usd` 270 read by `instance_reaper.warning_figure`, declared in `BUDGET_LINE_FIELDS`, carried
  in the guard's decision as `warning_usd` and `warning_reached`, in the reaper's status and the
  console), and the API spend has its own ceiling in the spend store, read from its latest `ceiling`
  line (`{event: ceiling, time_utc, ceiling_usd, warning_usd}`, never a constant; none refuses every
  paid run), with each planned run's worst case held by a `reserve` line (kind, order, worst case)
  for the runs ordered after it until it opens an intent or a `skipped` line records it skipped
  (`cloud_reference_spend.api_room`, called by the paid runners' `check_cap`, D-441, which holds a
  paid run to the API ceiling alone: Lambda's budget is reported there, never a limit, D-S121; each
  caller passes its own run kind, `kind=` having no default, so lane/causal's older call without one
  is reconciled at its merge, D-467); at either warning the reaper's pass puts one FOR_SECKIN entry
  at the top, once per kind and figure (`instance_reaper.note_warnings`), under the file's lock
  `FOR_SECKIN.md.lock` by a write beside it and one move (`put_on_top`; a held lock writes nothing
  and the next pass retries; a salvage entry is retried five times, then appended to
  `FOR_SECKIN_ENTRY.md` in its episode's folder, never lost; a failed move leaves no tmp file), in the
  form standing order 3 reads; the lead takes `FOR_SECKIN.md.lock` for its own edits of FOR_SECKIN, and
  committing and pushing FOR_SECKIN stays the lead's step. Order 3 (`standing_orders_check.check_budget`) takes every figure from those
  lines, none from code, and a store with no API ceiling line reads unable to check, so it blocks
  Lambda launches too through order 3. Order 1 judges only launches that uploaded
  (`assets_transfer_timing.json`, as the launch records check reads) and keeps one whose receipt
  records the controller's own fallback (`PROBE_TIMEOUT`, `UNREACHABLE`, `USE_FAILED`, a suspect
  `MISMATCH`) or a `MISSING` copy, seeded or not; a compared run's report names its machine type from its own controller
  records or is refused (`analyze`), and the adapters refuse a paired figure of two rented arms that
  do not both record it. An AST check holds that the guard, the reaper, the controller, the spend
  reader and the bound preflight load no name nothing in them assigns (the 4cdceafe NameError).
  IMAGE-A (D-S108, D-S109, D-417) changed `tools/ordinary_final_cloud.py` again (the image
  phases), in the same re-seal.
- LOOP-LAUNCH-A (loop S2): every ordinary final launch is a loop launch. The bound wrapper
  (`tools/ordinary_final_bound_cloud.py`) requires `--ledger`, `--purpose` (a short
  identifier: lower case, digits, hyphens), `--forecast-minutes` and `--storage-forecast-usd`;
  `execute()` refuses without that launch plan. The `--ledger` must be one the reaper reads
  (the private ledger or R's), and the guard always reads both of those beside any
  `--read-ledger` and needs a `budget_open` line among them. Before the launch request
  `tools/loop_budget_guard.py` decides, holding an exclusive lock beside the ledger from its
  decision through the intent line and reading the provider inventory again just before it:
  there is no maximum number of loop instances (D-S95, which removed the count limit D-S17 item 1
  set and D-S79 raised to sixteen; each instance is still counted once over the open ledger launches
  and the `shimmer-loop-` names in the inventory, its cap among the running caps, so the total
  budget is the only limit); it refuses when the inventory lists a loop instance no ledger
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
  total over all launches); the reaper judges each instance on its own record, however many run,
  and ends a stray (no recorded deadline) or an overrunning one (past its deadline) automatically.
  A controller's independent cleanup requires its own instance gone and no instance outside the
  loop, and names another loop instance still running apart (`other_loop_instances`).
  D-382 item 5, D-401 item 2: with no count limit, the per-run cap also reserves, per running loop
  instance and for this one, its price times one reaper period and a margin (300 + 120 s,
  `instance_reaper.REAPER_PERIOD_SECONDS` and `REAPER_MARGIN_SECONDS`; `loop_budget_guard.overrun_reserve`,
  `overrun_reserve_usd` in the decision), so instances each running past their due moment until the
  reaper ends them stay inside the ceiling. A stated limit: the reaper is a task that runs only while
  Seckin is logged on, so while he is logged off its period is unbounded and each instance's own
  deadline and watchdog are what end it (an open question to him). The cap also counts the cloud
  reference's API spend toward the total budget (D-401): the guard reads the shared store
  `docs/loop/private/cloud_reference_spend.jsonl` of the main checkout as cloud-console's reader finds it
  (`loop_budget_guard.spend_store_path`, `api_spend`, `api_spend_usd` in the decision); an absent or
  unreadable store refuses, never read as no spend, and a spend file role C handed back
  (`C_*cloud_reference_spend.jsonl` in its `_handoff` folder) refuses every launch until each of its
  lines is in the store. A mocked launch reads only the store it is given. By design the
  reaper never ends an instance that is not a loop instance: such an instance is only refused at
  launch, by the guard, the controller, the sealer and the bound preflight (D-382 item 7). Accepted
  by procedure, not code (D-382 item 6): two launches on different ledgers can decide at the same
  moment, each lock held beside its own ledger, so neither sees the other's intent line; launches
  are made from one ledger at a time.
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
  A10's recorded price, only with `--type-rule a10_first`; by default, D-S78 item 2 and D-S79, the
  fastest offered x86_64 type first by `tools/cloud_run/gpu_speed_order.json`, the A10 and one and
  two tiers above it (B200, H100, GH200, A100; D-S95; `loop_budget_guard.speed_order`, the provider's
  published generations), then price, with exactly the GPUs the run needs (`gpus_needed_match`, never
  more, in the declared order too) and no price factor: TYPE_RULE_FACTOR and the A10-first poll limit
  only `--type-rule a10_first` (D-S102 item 12). GH200 is arm64 and stays out until arm64 wheels exist.
  Only single-GPU types are rentable until the runner's hardware projection changes (D-382 item 3):
  the sealer refuses `--gpus` above 1 with that sentence, and seals `gpus` in the manifest. D-S96 item
  2 and D-382 item 1: a fastest or listed order leaves the A10 only for a MACHINE TYPE whose D-S82
  reference-set pair is measured (`measured` in the speed order file, keyed by machine type such as
  `gpu_1x_h100_pcie`, each entry made by `factor_record.measured_entry` from the reference pair of all
  three reference items: per item the A10 and new-type run folders, both records' digests, one commit
  and the `machine_effect` result; its factor is the MEDIAN of the three items' factors; it is read
  again from the folders at sealing by `factor_record.check_measured`; any item that moved a score
  keeps the type out, and since exact score equality may never hold across GPU generations, then the
  type stays out (D-401 item 3)); a listed type with none is
  refused, and the kept types rank by their factor with the A10 at 1.0 (`measured_tiers`), so a type
  measured slower than the A10 ranks below it. Exempt only the reference-set run itself (its
  workload a declared reference item, `factor_record.reference_workload`). Until a pair is measured
  every launch stays on the A10. The speed order file is read at sealing and sealed into the
  manifest's candidates; it is not pinned, and each change to it is recorded in DECISIONS. A B3 or B1
  bundle names its comparison with `--comparison <name>` or states `--uncompared` (one of the two;
  `prepare_ordinary_final_run.comparison_declared`; the console's reviews are `--uncompared`; a
  reference-set run needs neither). Every launch of one comparison runs on one machine type, the
  first launch's, recorded at launch after the guard's decision and under the ledger lock in
  `comparisons.jsonl` beside the private ledger (`loop_budget_guard.claim_comparison`; the sealer reads
  it, `comparison_type`, and seals that one candidate). A figure whose arms' selected types differ is
  refused on every figure path in code: `factor_record.require_same_type` (the `arms` command), the
  analyser's batch pairing (`analyze_ordinary_final_run.pair_machine_types`, `batch_machine_types.json`)
  and the adapters' `score --paired-with`. The gate scoreboard is written by hand: each of its rows is
  checked with the `arms` command first. The manifest records `tier`), or
  the order named with
  `--instance-types`, `type_rule: declared` with `type_order`
  `fastest` or `listed`, exactly the run's GPU count (one today), no poll and no price limit beyond each type's sealed rate,
  the cap rule and the budget unchanged; all arms of one comparison are sealed with one named type),
  rate caps and the soft and hard caps are sealed manifest fields set
  by the sealer from the provider inventory it is given and the guard's formula; the type rule
  polls for the A10 in us-east-1 for up to 30 minutes before a fallback, and the runner's
  hardware check reads the selected candidate. Which figures are CODE CONSTANTS, stated
  exactly: the loop's budget rule (the 1-dollar margin, `instance_reaper.MARGIN_USD`, read by
  the guard; the 1.5 cap factor, the 1.3 forecast factor and the type rule's factor 2, which only
  `--type-rule a10_first` applies, in `tools/loop_budget_guard.py`; the overrun reserve's period and
  margin, `instance_reaper.REAPER_PERIOD_SECONDS` 300 and `REAPER_MARGIN_SECONDS` 120), the two
  reserves (`WORKLOAD_STOP_RESERVE_SECONDS` 900, `TERMINATION_RESERVE_SECONDS` 180) in the
  sealer, and the run's own hardware floors. No per-run cap is a code default:
  `cloud_run_common.budget_deadlines` and the general watchdog (`--soft-usd`, `--hard-usd`)
  take them as required arguments, and the general path's sealers take them on the command
  line (`prepare_cloud_run.py --soft-usd/--hard-usd`, `run_remote_experiment.py prepare
  --soft-usd/--hard-usd`). The general cloud path (`tools/deploy_cloud_run.py`,
  `tools/run_remote_experiment.py`) refuses a `shimmer-loop-` name, any loop ledger argument,
  and any launch while a loop ledger is open (`budget_open` without `budget_close`);
  `deploy_cloud_run` resolves the instance name first and, on a failure, terminates only an
  instance whose name it resolved and which is not a loop instance. That path's sealer
  (`prepare_cloud_run.prepare`) still holds `requirements.txt` to its own `tools/cloud_run/runtime.lock`
  and to the A100 smoke baseline (transformers 4.52.3), so since `requirements.txt` pins 4.51.3
  (lane/gate-pins) its `dependency_pins_match_completed_baseline` refuses; no gate check and no loop
  launch runs it on the real files (open item 106). `--detach` runs the
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
- DOCJUDGE-A (v1 parallel track, G1, operator-approved 2026-11-01): `benchmark/baselines/doc_judge.py`
  judges each (document, rule) ONCE over the whole document: the rule's own text, one user turn
  through the model's own chat template, no filled example, three declared outcomes. No system
  turn is sent; a model's own chat template may add its default one (Qwen2.5's stock template
  does, read from its tokenizer config), and the rendered prompt saved in every reply record
  shows what was sent. The config is `benchmark/baselines/doc_judge_prompt.json`. It rides the runner's existing replay
  pass (`replay_prompts.py run` and `load_prompts` hand a `doc-judge-prompts-v1` file to it;
  `--paths sdpa` only, no decision), so NO bound controller file changed. Each prompt goes through
  `bare_model.LocalBackend` (system turn None means one user turn; B1 always sends both) and
  writes one reply record with its text; `judge` reads a pass only when its `prompts_sha256` is
  the given prompts file's. A holds or not met is kept only with a quote found in
  the document (whitespace-normalised); the labels are bare_model-format and scored only through
  `tools/score_corpus.py` (`item_table`, `benchmark_labels(..., arm="B1")`), silence counted
  apart and never a detection. A kept quote must also be the document's content (open item 84:
  found with the heading and label lines out, a letter or digit, cut at a word's or a number's
  edge, a word's own hyphen or apostrophe not being inside it; `quote_not_content` otherwise). `build --b1`
  adds, per model group and item, B1's own two turns with B1's allowance (form `b1`, D-241),
  because a B1 bundle holds one document: `judge` reads them with `bare_model.parse_reply`, `score`
  scores them as the view `b1_comparator`, lists every kept claim on a scored item with its quote, and with
  `--bar-items` (the items the decision fixed, those left out and the prompts' and keys' digests,
  `benchmark/baselines/g1_bar_items.json`, digest pinned in `BAR_ITEMS_SHA256`) writes the bar's
  verdict (`bar`, `bar_row`, `chance_tail`: usable, not_usable or void) into `g1_scores.json`,
  refused for another file, other inputs or other items on the two benchmarks. `judge` runs at
  the bound commit. A pass is a pilot go only, never above B1. Development, exposed; not an
  arm of the preregistration. Check 321 (with a proof on the real `LocalBackend._render`).
- ARM-L-A (D-S13 item 6d): a third sealed arm, `L`, runs the launcher menu as shipped on the
  loop's own instance with the same controller, guard, ledger, reaper and binding; never on the
  laptop. The sealer (`--arm L --launcher-question "..."`, exposed only, refused for a sealed run
  by the sealer and by `admit_workload`; and, D-159 and D-184 (issue #135), sealed only from
  development material already in the repository: every workload file must be, byte for byte as
  staged, a file tracked at the bound commit, else `launcher_material_error` refuses naming it)
  puts the workload's context and conventions files into
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
- GATE-ARM-A (D-S75, D-329): a fourth sealed arm, `G`, runs the gate on a rented machine as a
  loop launch: `tools/prepare_ordinary_final_run.py --arm G --gate-form full|side
  [--gate-checks n,n] [--known-red n,n]` seals a `gate` block (form, checks, known-red list, the
  bound gate's check numbers read from its CHECKS titles, the gate's `requirements.txt` pins, each
  required in the sealed runtime lock (a pin holds against the lock's version with its local label
  dropped when the pin names none, `2.5.1+cu121` holding `2.5.1` and nothing else loosened; one rule at
  sealing and admission, `ordinary_final_run.pin_held`, lane/gate-pins; check numbers start at 0, the
  gate's own first check, lane/gate-zero), and the digest of `gate_source.tar`, `git archive` of the
  bound commit, a support file). Exposed only, no workload, never in a batch. On the instance the
  runner keeps every guard, extracts the tree (a member outside it refused) and runs, in a child
  process with its own environment (the sealed model cache, the hub offline, no SHIMMER_ setting
  or credential; the runner's in-process network denial does not reach it), the laptop's command
  `python -u -X utf8 scripts/verify_session1.py --results <file> [--checks n,n]`, or each side gate
  of `ordinary_final_run.SIDE_GATES`. The gate's two flags are off by default: `--results` writes
  one line per check (number, title, status, seconds) as it goes, `--checks` runs only those.
  `assess_gate` passes integrity when the gate ended by itself, every expected check left its row
  and every one outside the known-red list is PASS, WARN or SKIP (a side gate exit 0); a known-red
  check that passes is reported now green. The analyser's `Gate` row gives the counts, known red,
  now green, not run and the gate's minutes; never comparable with B3, B1 or L. A cloud gate counts
  as the gate only after a parity run on a commit the laptop has just gated, compared check by
  check (D-S75 item 3). Proofs in `tools/ordinary_final_gate_arm_checks.py`, in the controller gate.
- SALVAGE-A (D-S84): if Claude stops, the loop's instances are saved and stopped with no Claude
  involved. `tools/loop/instance_reaper.py` reads two triggers on every run: seven-day usage at or
  above `USAGE_STOP_PERCENT` (95) in `.claude/loop_status.json`, and no lead heartbeat
  (`docs/loop/private/continue_hook_state.json`, LOOP_STATE or FOR_SECKIN written) for
  `SILENCE_MINUTES` (90) while a loop instance runs. Either opens an episode
  (`docs/loop/private/salvage/episode.json`; D-412 item 2: ONE salvage folder for the reaper, every
  controller's poll and the sign-out hook, the MAIN checkout's, found through git's common directory
  by the spend store's path rule, `instance_reaper.salvage_dir`, resolved at use) and writes a request per running loop instance
  (`salvage/requests/<name>.request.json`). The controller polls it (`salvage_stop`): no new
  phase starts, the phase in hand is given `SALVAGE_ITEM_SECONDS` (300), then the stop and
  collection phases the soft budget exempts run as at any stop (workload stopped, evidence packed,
  hashed and copied to the run folder, instance terminated and verified, ledger closed), and it
  answers with `<name>.done.json` (`salvage_record`: packs, finished and unfinished entries, cost).
  An instance with no answer `SALVAGE_ANSWER_SECONDS` (600) after its request is terminated by
  the reaper (`salvage_no_answer`); one that answered while still listed, `salvage_done_still_listed`.
  Once every instance is verified gone the reaper writes `docs/loop/private/SALVAGE_REPORT_<time>.md`
  (trigger, each instance, finished, lost, cost, packs, how to resume) and a top entry in FOR_SECKIN,
  and moves the episode into `salvage/<time>/`. A salvage error never stops the deadline and hard-stop
  terminations. A `--mock-state` proof run makes no salvage pass unless it names `--salvage-dir`.
  Proofs: `tools/ordinary_final_salvage_checks.py`, in the controller gate with neutralise, fail,
  restore, pass. On sign-out, shutdown, sleep or modern standby (D-S107 item 3, no password,
  D-412), `tools/loop/session_end_salvage.py` terminates first: it opens a session-end episode naming
  every running loop instance, writes each one's request through `salvage_pass`, then terminates every
  loop instance listed at once with no wait (a logoff follows 1074 by 4.6 to 9.2 s), each in its own
  try (a failure is recorded by its class name, and the reaper ends that instance once its request goes
  unanswered), one ledger line each (`by` `session_hook`, reason `session_end_<event>`) on every ledger
  holding the launch, R's included, or the append ledger for an instance no ledger records, and closes
  the episode by `close_salvage`, whose report names the Windows event. A normal shutdown or sign-out
  therefore ends the instances WITHOUT their controllers' packs (what a run folder already collected
  stays), and when the provider cannot be reached in time each instance is bounded only by its own
  recorded deadline. A trigger can fire at the wrong moment (a shutdown then cancelled, an updater's
  restart, an S3 sleep handled only after resume), and it stops R's instances too. One pass at a time
  (MultipleInstancesPolicy IgnoreNew and a lock beside the salvage folder, replaced after 180 s); a
  session-end episode applies only to the instances it named (`salvage_pass`), so one left open over a
  reboot is closed and never applied to a newer launch (the report says so), while a newer launch still meets
  the usual triggers and joins the episode when one fires (D-435). Every path (ledgers, salvage folder,
  reports, FOR_SECKIN, the log) is the main checkout's, from git's common directory; with git unreadable the
  script's own checkout is used and the log says so, and a `--root` that is not the main checkout is refused.
  One listing precedes the first termination. Each run is one line in
  `session_hook_log.jsonl` (event, id, provider, seconds used, `first_real_of_event`). It is started by
  the Task Scheduler task `ShimmerLoopSessionEnd`, InteractiveToken and least privilege, on System
  User32 1074, Winlogon 7002 and Kernel-Power 42 and 506 (Security 4647 optional), registered by
  `tools/loop/register_session_hook.py` (`--dry-run` prints the XML), which refuses unless the main
  checkout holds the script and a pythonw.exe exists, and prints schtasks' own error. Check 348.
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
  (Annex A 11.12: purpose and sealed-or-exposed lines first, the `SHIMMER_INST_FINDER` value
  sealed in the manifest beside the one each pipeline run saved in `audit/agent_switches.json`,
  a difference or an unreadable record named `DIFFERS FROM THE SEAL` and kept in
  `FINAL_STATUS.json` under `inst_finder` (D-184, issue #133), FACT_CHECKER withheld with both B.4 reasons, instance type and price, asset copy MATCH or
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
  live field set (top level `LIVE_CASE_FIELDS` and, D-S70 item 4, each issue's `LIVE_ISSUE_FIELDS`,
  one function `live_case_fields_error` at sealing and admission) and exactly `MULTI_ROUND_ARGV` (`reference_serial`, no topology file); the
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
  a label no paired rule names recomputes nothing), its units of measure and the text of every
  other unit its copy or carry checks read (`neighbours`, RELATIONS-A) (`SIGNATURE_INPUTS`), reused records and model asks are rebased onto the new unit id, the
  record is `audit/round_reuse.json`, and the round findings are posted on the run bus (backend
  `paired`, model `python`, one envelope per round document); nothing in the pipeline reads them yet (`tools/score_corpus.py` scores them).
  The case's typed records are computed in Python, with no model call (open item 35, INC-023:
  the one free-form PROCESSOR call over the whole case ran to its output cap on real execution):
  one position per declared (round, actor, issue), accepted only on exactly one accepted source,
  numeric only when it takes part in a computed gap between two parties (POSITION-GAPS-A: the same
  sentence with only the figure changed), else `figure_left_out` names why; one movement between
  consecutive positions, always `unknown` (`multi_round_phase.computed_records`, `written_by`
  `python`, posted with backend `computed`, model `python`). Only the strategic layer's explicit
  decision-support modes still call PROCESSOR and VERIFIER. A
  term that vanished while its section states an unclaimed newcomer in the same unit of measure
  is refused as a possible rename (`paired_review.possible_successor`), never minted as
  withdrawn, until S5 measures an ensemble decision for it; two figures with no unit count as
  the same measure there and are refused under their own reason. Check 279 and
  `tools/multi_round_launch_checks.py` hold this end to end.
- VERSION-CHANGES-A (D-S39): a multi-round run writes what changed between versions in Python, with
  no model: `scripts/version_changes.py`, `audit/version_changes.json` and `version_changes.md` in each
  later version's folder, through one renderer. Per unit: sentences added, removed and changed with
  both versions cited (a tie refused), text values, table cells and rows, and the two-version review's
  figure records. A manifest does not say which documents are versions of each other, so they are
  paired by shared headings. Numbered references are checked from `numbered_references` in
  `config/relation_patterns.json`, no pattern in code; a number the document lacks fits no relation of
  the Finding record, so it is a computed note, never a finding (adding a relation is governed).
  Check 327.
- CASE-QUESTIONS-A (D-S39 item 2, D-S41): two narrow model steps behind injected callables
  (`scripts/case_questions.py`, `config/case_questions.json`), never the free-form `strategic_options`
  path (INC-023). Toward or away: per accepted movement Python selects the party's two positions and
  the other party's, and `decide(question)` returns {answer, confidence, settled}; `generated_decide`
  gives the same shape from generated text. `movement` stays `unknown` unless answered and settled; an
  answer takes the nearest value of `multi_round.MOVEMENTS` (held exact by multi_round_checks) with the
  literal answer in `movement_answer`, is marked `movement_decided_by: model`, and travels in its own
  bus post, never as Python's. Suggested wording: for each issue the manifest declares `open`, for the
  one actor it declares `supported`, one call to `suggest(question)`; a suggestion is kept only with
  citations it was given, is marked model-written and is never an amendment. The case phase builds both
  from the driver's wrapper factory (`multi_round_phase.case_question_calls`) through
  `narrow_call.narrow_ask`, the body of the driver's `_narrow_ask`, so each call is masked and leaves
  the pair call's trail, and `main`'s pinned case statements (check 261) stay as they are. The agent that answers is `agent` in `config/case_questions.json`, its model the registry's,
  and it is null: nothing is asked. A decision with no measured threshold (`case_movement` in
  `config/semantic_thresholds.json`) or on a backend with no probabilities asks nothing either, and
  each row says why; Python's selections are written to `case_positions.md` either way. D-S46 item 3:
  a suggestion is kept only with a quote copied from a passage of the last round it cites, citing no
  unit the case declares agreed (`closed_units`), and, where the party's declared position and
  fallback are one figure each in one measure, with no figure of that measure outside them; the
  rest goes to the rubric (`benchmark/dev_cases/host_agreement_three_rounds/ROUND3_RUBRIC.md`), scored
  by a checker who did not build it. Nothing here has been run on a model. Check 328.
- POSITION-GAPS-A (D-S46 item 2, D-319, D-322): `scripts/position_gaps.py` computes the gap between
  two parties on a declared issue in each of two consecutive rounds and writes one `trajectory` record
  (the multi-round case's own typed record, both parties as participants) with the INFRA-044 relation:
  `moved_toward` (narrower), `moved_away` (wider), `unchanged_from_prior` (within the tolerance), the
  four figures, their positions and sources, and its `measure`. Two paths, chosen by the manifest:
  (1) an issue with a declared `unit` (D-S70 item 4: the operator's own words, declared syntax, no
  digit, one line, `multi_round.declared_unit`; the host-agreement case declares `days`, `months` and
  `EUR`) is computed when each quote holds one figure with that unit standing right after it, as
  declared (spacing between, case kept, ending at a word's edge); any other measure is refused as
  `not_the_declared_unit`, a currency sign or code before the figure included. The declared unit is
  trusted as declared: a rent issue declared `EUR` compares a monthly with a yearly figure, so the
  whole measure is declared (`EUR per month`). (2) An issue with none is computed only when its four
  quotes are identical as written (whitespace collapsed, case kept) except for the one figure each
  holds: a computed movement then means "the same sentence with only the figure changed"; any other
  pair is refused as `quotes_differ_outside_figure`. No unit is read from words on either path: three
  rounds of an independent checker found every rule reading a window around a figure could call two
  measures equal that are not ("The monthly rent is 9,000 EUR." against "The yearly rent is 108,000
  EUR.", "9,000 EUR, per month", "Per month 9,000 EUR", brackets, a dash, the next sentence). A quote
  with no figure is `a_position_in_words`, with several `several_figures`. A position carries `value`
  and `unit` only when it takes part in a computed gap; otherwise `figure_left_out` names why
  (`multi_round_phase._numeric`). Measured: the worked case scores 16 of 16 with its declared units
  and 11 of 16 without them, each refused row named; the draft-resolution case declares none (its
  only figures are the dates of the day it names, and its one actor gives no gap). Nothing is
  computed from words, nothing carried forward, nothing chosen among three parties; every issue and
  round pair gets an outcome row (`position_gaps` on the case record, `read_by` naming the path),
  shown in `case_positions.md`. Nothing is added to the Finding record. A model's answer on a
  movement in words is kept only when the quotes Python gave it stand in the round text. Scored by
  `tools/score_case_movement.py` against a key written before the code
  (`benchmark/dev_cases/host_agreement_three_rounds/EXPECTED_MOVEMENT.json`) and a perturbation made
  in the check; the independent checker's first case and every quote of its attack probes are
  replayed from `benchmark/fixtures/position_gaps_replay.json`, each attack a proof on both paths.
  Check 337; the issue field set and the unit's syntax in `tools/multi_round_launch_checks.py`.
- NEGOTIATION-MEASURE-A (D-S102 item 8, D-389, D-414, D-419, D-430, D-437, D-451, D-456): positions toward or away and the
  round-3 wording are measured on held-out cases by `docs/loop/stages/NEGOTIATION_MEASUREMENT_PLAN.md`,
  written and checked before any figure; development, exposed, not a gate benchmark, "our metric, no
  published benchmark". `tools/score_negotiation.py` maps every outcome to a label (`no_answer`,
  never in the key, for a missing row or an unreadable reply, counted for every arm), gives Macro-F1
  over the key's classes, movement precision, recall and coverage with the two floors, the round-3
  good-suggestion rate under one rule for a quote in agreed text, and a BCa cluster bootstrap (exact
  below 10,000 distinct resamples) with a jackknife over cases and a cluster permutation test beside
  it. One primary claim, C1 (Macro-F1, system against B1), at 0.05 / 2^k one-sided (0.025 at the first
  opening); C2 to C5 are indicators, never claims (D-414). C1 is a claim only if its power, simulated
  at the frozen headline count with 1,000 or more sets and each arm's over-prediction of
  `not_computable` (`tools/negotiation_power.py`, record `docs/loop/stages/NEGOTIATION_POWER_C1.json`),
  is 0.8 or more at every correlation (the record read from the commit, its code and assumptions the
  committed ones); otherwise the measurement is indicator-only, as it is expected to be (D-430). The
  record names each claim's status by that rule (`claim_by_plan_rule`). The scorer refuses a dry-run
  freeze, a
  missing or mismatched opening line or power record, any arm whose records do not match the
  configuration, a frozen case with no system run, two model groups, and a third opening. Each
  `--system-run` is a run folder, one per case; one with no case record is a failed entry only when its
  bundle's FINAL_STATUS.json says failed, in a failed or stopped state, and never for a case with a case
  record in a run given (D-437, `refuse_system_runs`). A FAILED status counts in any pipeline state. Either kind, infrastructure (only a
  cause of the runner or the machine: the controller's failure records, no runner result, a terminal
  error whose recorded type and module are the host out of memory, `builtins.MemoryError`; a CUDA
  out-of-memory error is the system's own) or the
  system's own reasons (any pipeline exception, `backend_failure`, the run's own reasons), scores
  `no_answer` on every row, kept in the frozen key and counted apart by kind; only infrastructure can
  call for opening 2; records are read only at the entry root, never under `downloaded/`, and the runner's reasons decide the kind (D-451, D-456).
  `benchmark/baselines/negotiation_b1.py` holds the two B1 forms (`movement`: four declared quotes,
  four declared answers, 16 output tokens for B1 and the cloud alike; `suggestion`: the system's own
  question over the whole last round, read by `case_questions.read_suggestion`), rides the replay pass
  (`replay_prompts.is_negotiation`), and changes no bound controller file.
  `tools/freeze_negotiation_set.py` (role B's) fills the declared headings, refuses a case below the
  minimums, settles the key on pooled kappa (floor 0.60, one revision round, labeller 3), reads .docx
  and .jsonl corpora, checks the same source, reads each passage's 5-grams once against one index of
  the cases' gram sets (`GramIndex`, the same answer as every pair), encodes each corpus once, in chunks and in batches of at most 8,192 tokens
  into float32 arrays, with a time forecast covering all three steps (on the CPU,
  or with `--device cuda` on the GPU only when it reads idle under D-399, read again after every chunk (memory others hold, utilisation beyond its own) and
  moved to the CPU when another process takes it), refuses
  a leaked case, and writes `FREEZE.json` (a dry run writes `FREEZE.dryrun.json`). Check 347
  (`tools/negotiation_measure_checks.py`), fixtures only.
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
  `archive_integrity` hashes whatever is on the instance, as always. The probe's deadline scales
  with the sealed archive's size (D-398, open item 94, #203: `asset_copy_probe_seconds`, the slowest
  measured rate, 13.15 GB in 246 s, with a 1.5 margin and a 300 s floor; 625 s for 22.25 GB). A
  MISSING copy is seeded only with room for the whole archive on the filesystem, read from the
  provider's own inventory (`asset_copy_room`, GET `file-systems` of D-S50: one capacity field in
  bytes less the bytes used; full, unlisted or unreadable refuses the seed, named in the receipt's
  `seed_refused`, never the run), and only after that phase passed, with `mv -n`, so a stale or corrupt file is never overwritten;
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
  and it changes nothing when undeclared. D-S107 item 1 makes it the default for every loop launch:
  the sealer writes the declaration into every exposed bundle from its own digest, on the loop's
  filesystem (`asset_copy_for_bundle`; `declare_asset_copy.LOOP_FILESYSTEM_NAME`, `LOOP_MOUNT`), or
  `asset_copy_absent.json` with one recorded reason (`sealed run` by itself, `another region` with
  `--no-asset-copy`); the controller and the bound preflight refuse a us-east-1 loop launch with
  neither (`require_asset_copy_or_reason`), so every worker brief that seals a bundle carries the
  declaration step by sealing through the sealer, and a hand-made bundle is declared with
  `tools/declare_asset_copy.py`. In us-east-1 `--forecast-includes-upload` is admitted only with
  `--upload-reason` from a declared list, each checked, never free text (`upload_reason_admitted`,
  D-421: `sealed run` against the seal, `another region` against the selected region, `seed of a
  missing digest` against the declaration and the seed history). A probe past its deadline falls back
  to the upload, recorded as `PROBE_TIMEOUT`, and never fails the run (`probe_timed_out`). A
  filesystem whose inventory has no capacity field has room (D-403, the documented live case of
  D-306: no quota). D-S107 item 5: a MISSING copy is seeded once, after integrity, for every later
  launch; the seed first names the archives the filesystem holds, and the receipt (`old_digests`)
  and `asset_copy_history.jsonl` beside the private ledger record the time, the old digests, the new
  digest and the launch (nothing is deleted). No container image is carried today; if one ever is,
  the same rule applies to it. `tools/loop/asset_copy_launch_check.py` (through
  `tools/loop/upload_losses.py`) fails on every loop launch since 5 November 2026 that uploaded the
  archive while the copy could have been used; check 350 holds its rule on fixtures.
- IMAGE-A (D-S108, D-S109, D-417, form B): a ready-to-run image on `shimmer-filesystem`, as layers
  used in place. `tools/image_layers.py` (stdlib; sealed into the bundle as a support file with its
  spec `image_spec.json`, written by `prepare_ordinary_final_run.py --image-layers`, the manifest's
  `layers` block naming both and every layer key) keeps under `<mount>/image/<kind>/<key>/` one
  layer per model (the sealed `assets.tar` members under `hf_cache/hub/models--...`), the wheels (the
  members under `wheels/`) and a venv built on the mount with the controller's own pinned command
  plus `--no-compile`, bytecode removed, so a rebuild from the same wheels is the same bytes; the env
  key binds `install.lock`, the machine image id, the Python version and the tool's digest, and the
  env layer is sealed only from the build record an earlier launch brought back
  (`tools/image_layer_plan.py env-manifest`, then `--image-env-manifest`); without one it is
  `UNSEALED` and never used. Only with a declared copy (ASSET-COPY-A) and a sealed spec does the
  controller run `image_check` on the instance after ssh and before any workload step: every file of
  every layer hashed in parallel against the sealed digests, the exact file and symlink set, one
  state per layer (`MATCH`, `MISSING`, `MISMATCH`, `UNREACHABLE`, `UNSEALED`) in
  `image_receipt.json`. Every model and the wheels `MATCH`: no asset archive is fetched,
  `archive_integrity` hashes `project.tar.gz` alone, only it is extracted, and the layers are bound
  READ-ONLY into the run root (`sudo mount --bind`, then `remount,bind,ro`, refused unless `findmnt`
  lists it `ro` and a write under it fails), the env too when it `MATCH`es, so `create_environment`
  and the wheel install are skipped; the runner reads the same paths and hashes the models again as
  always. Anything else: the asset path runs exactly as without layers, then each `MISSING` layer
  is built from the run's verified extraction (beside its final name, moved in with a rename that
  never replaces a layer) and checked again (`image_recheck`); a `MISMATCH` layer is never replaced
  by a run, and a failed bind falls back to the asset path: the tool unmounts every bind it made
  (its own partial read-write bind included) before it refuses, and the controller's `image_release`
  reads the mount table again and refuses the run ("Image layers are left mounted under the run
  root") unless nothing is left mounted under the run root. A recheck that loses a first `MATCH`
  fetches the assets then (`match_lost_on_recheck`). An `image_check`, `image_build`,
  `image_recheck` or `image_bind` past its deadline is recorded (`timed_out`), its process group
  stopped (`stop_image_phase`: TERM, then KILL, waiting until `kill -0` finds the group gone, and
  `stopped` per phase in the receipt), and read as no answer (all `UNREACHABLE`; a build not built
  and nothing checked again; a recheck fetching the assets without `match_lost_on_recheck`; a bind
  released only once its stop is confirmed, else the run refused), never a failure, as D-421 does
  for the copy probe. The tool turns SIGTERM into an exception (`image_layers.on_term`), so a
  stopped build removes its own partial and `.build-<key>` folders and a stopped bind its mounts.
  The env build directory is claimed with one `os.mkdir`: a second build of the key refuses, is
  recorded not built and never touches the other's. These changed `tools/ordinary_final_cloud.py`, so
  bundles sealed before them refuse with `Controller source changed`; `tools/image_layers.py`
  changed too, so the env key (which binds the tool's digest) moved. `--image-measure` (M1) adds
  `image_measure`: cold read rates with 1, 4, 8 and 16 readers after dropping the page cache, and
  form A (the env as a Docker image, saved to the mount, loaded cold, run with the GPU) where Docker
  exists. The tool writes `image_progress.json`, which `tools/ordinary_final_progress.py` reads for
  `image_check`, `image_recheck`, `image_build` and `image_measure` (PROGRESS-A). What the tool
  prints for the controller is one `IMAGE_RESULT` line of at most `image_layers.SUMMARY_CAP_BYTES`
  (8,192), measured as printed (`summary_line`: the marker and the canonical JSON). Its compact form
  (`_compact`) keeps per layer its kind, key, state, files and bytes and, of each of its up to three
  difference lists, at most two names of at most 160 characters each; per build record its name,
  built, reason, seconds and, where it has a manifest, the manifest's digest, key and file and
  symlink counts, never the manifest. Past the cap it prints the minimal form (`_minimal`: each
  state; each record's name, built and manifest digest; the bound and left lists), and past that only
  the record's name and digest (`summary_unavailable`), which every controller parser reads as no
  answer. Every form names the full record (`--out`, in the run root, which the evidence pack
  collects) with its digest; `tools/image_layer_plan.py env-manifest` refuses a summary with no
  record digest or no manifest digest for the env record, and otherwise reads the full record from
  the session's `collected_evidence.tar.gz` only at that digest and the env manifest only at that
  manifest digest. Measured, not preferred: M1 (11 November 2026)
  printed its whole 5,425,078-byte build record, and the controller's collect over the ssh pipe hung
  to its 120 s deadline (LIVE-VIEW-A's 32 KB) and stopped the run after every layer was built. Every
  detached phase's collect (`ordinary_final_cloud.phase_collect_command`) also reads each of the
  phase's two files whole only up to `PHASE_COLLECT_CAP_BYTES` (14,000; the largest collect of every
  earlier launch, the wheel install, was 12,266 bytes), a larger one as its last 14,000 bytes after a
  `PHASE_OUTPUT_CAPPED <file> <bytes>` line, listed under `output_capped` in the phase's timing
  record (a marker is read only for the phase's own two files, `phase_files`, once each). This changed `tools/ordinary_final_cloud.py` and `tools/image_layers.py`, so bundles sealed
  before it refuse with `Controller source changed` and the env key moved again. Off unless sealed;
  no launch uses it before the M2 test launch passes (D-S109 item 4). Proofs: the image checks in
  `tools/ordinary_final_image_checks.py`, in the controller gate with neutralise, fail, restore, pass;
  the real tool runs on a local stand-in mount, only the venv, pip, mount and findmnt calls faked.
- Test corpora from other domains live in `benchmark/corpora/` (real public data, outside the
  vocabulary probe's roots) and are staged with `tools/stage_corpus.py`. Run one before
  claiming domain agnosticism; the first unseen corpus found five parser defects in ten minutes.
  A key outside `benchmark/corpora/` is scored with `tools/score_corpus.py --key <answer_key.json>
  --run <run>`, and its twin with `--twin-key` and `--twin-run`; the scorer refuses a twin the key
  does not name and a run that is not of the twin's document. It reads `expected_refusals` by
  refusal kind (a rename Python matched is no false positive; one only a model's record matches
  satisfies nothing), scores a run holding `audit/multi_round.json` per round and document from
  Python's round findings only (a round-scoped key is refused on any other run), and reports
  a key relation the record does not declare apart, located only by a marked model-written record
  (since INFRA-045 the record declares all four such relations, so the section prints only under
  a record without them, and `tools/miss_diagnosis.py` reads a run whose pairing map carries no
  `relation_refusals` as made before INFRA-045); it reads a judged absence from Python's stamped
  copy only, the model's raw reply to that call (refused answers included) locating nothing and
  counted apart with the refused answers (D-184, issue #32; check 293). Development cases built from
  repository material live in `benchmark/dev_cases/`: exposed, development only.

- FACTORS-A (D-S82): every change in a figure is attributed to its cause. `tools/factor_record.py`
  writes, from a run's own sealed records (manifest, launch record, seal), a factor record: arm,
  machine type, models, checkpoint, training recipe, calibration, prompt or context, decoding, item
  set, scorer, seed and the rest of the code, each a short digest with its source. The project
  files each factor reads are declared in `config/factor_record.json`; a file no factor claims is
  `code`, and a factor nothing records is `None`. Not recorded on both sides counts as the same;
  recorded on one side only, it differs. `compare` names the differing factors. `attribute` gives
  a gain to one factor only when it alone differs, or when an isolating pair on the same metric
  measures it (differing in that factor alone); the rest is one joint row, never split, and
  every isolating pair it refuses is listed. `machine_effect` reads only the fixed reference set run on the A10
  and the new type with the machine alone differing: a time factor, and any moved score reported as a
  hardware effect. The pair only measures a time factor (D-389): it never makes a figure on one type
  comparable with a figure on another. The set (`reference_set.items`, the
  lead's ruling) is three exposed B3 entries already run on the A10 with integrity passed: ContraDoc
  0436316e6bb3 and SciTab 09b24267b75a from C1 and the timing entry's document news_train_96
  (01015e47de8a) from L12, each with its item_set (checked against its own workload digests), its
  A10 workload seconds, its source run, folder and commit. The
  analyser writes the record into `FINAL_STATUS.json` (`factors`) and a `Factor record` row of
  `RUN_REPORT.md`. `render_table` writes the per-result table. Results and arms compared with each
  other run on one machine type, always (D-S95 item 5, D-389 ruling 2): `attribute`
  (`require_machine_pair`) refuses any comparison across machine types, whatever pairs are given; the
  reference-set pair itself (`compare` marks it `reference_pair`) is the one cross-type comparison
  admitted, for its time factor, and never licenses comparing figures across types. Where a paired
  figure is made, the benchmark adapters' `score --paired-with` refuses two labels files recording
  different machine types, or one recording it beside one that does not
  (`common/cli.check_same_machine`; `label --run-folder` records the arm's type through
  `factor_record.require_same_type`), and says `not recorded` when neither does. Check 342.

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
- STANDING-ORDERS-A (D-S110, D-410): the lead keeps docs/loop/private/STANDING_ORDERS.md, every standing instruction of the operator with how it is proven to hold now. tools/loop/standing_orders_check.py checks the script-proven ones at every wake, launch, merge, push and report; a broken order (a violation found) is an alarm and blocks the step it guards, as UNABLE TO CHECK does for orders 1 to 3 only; "check not built", "kept in part", "code proven, not the order" and "nothing to check yet" are their own states (D-426, D-429, D-430). Order 1 reads every us-east-1 launch from the landing of the launch records check, the history since 5 November reported once; `--only 1` before every launch. The session start says STALE when the result is over 24 hours old or the tablet changed. A decision that suspends or narrows an order says so on a `**Suspends.**` or `**Narrows.**` line naming `order N`, quoting the reading it rests on with its time; without both, order N is broken (F5). Every lane and checker reads it at session start (tools/loop/session_start.py). `--orders` prints the tablet and the last result alone; check 349.
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
- LIVE-VIEW-A (Annex D D-S66): `tools/ordinary_final_live.py`, beside the progress reader,
  shows an exposed cloud run call by call from the instance's own reply records and
  `outcomes.jsonl`: passed, refused (with its reason), out of memory or crashed, and its
  seconds; running counts; the phase, cost and the progress reader's line; a stall when nothing
  finished for longer than 3 x the run's median measured seconds per call (never less than its
  slowest), or per training update. It writes a self-refreshing page (`<bundle>/live_view/`
  or `--page`), a one-line summary and one `ALERT` line per pattern (a repeat, out of memory, a
  crash, a refusal rate above `--development-refusals`, a stall); it never pushes or writes
  FOR_SECKIN. Its one remote program is read-only and sends only `ITEM_FIELDS`, never reply or
  payload text; a sealed bundle (anything but an exposed seal, failing closed) gets counts and
  timings only, `--items` refused, and no page inside the repository. Not in the controller
  binding. Measured, not preferred: an ssh answer over about 32 KB read through a pipe never
  completed on this machine, so its answer goes to a temporary file. Check 340
  (`tools/ordinary_final_live_checks.py`, replayed from `tools/ordinary_final_live_fixture.json`).

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
  per `item_id` supersedes an earlier one. `agent_wrapper.decode_items` and the judged paths pass each
  item through `finding_record.with_readable_ids`: a declared field of the wrong shape is removed and
  named in `unreadable_fields`, and an `item_id` becomes a string, because a model can write any JSON and
  the contract check accepts a list of scalars anywhere. A clean item comes back as the same object.
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
- NO-WEB-LOCAL-A (loop S11, D-S23 item 1, open item 68, D-180): under the local backend profile
  no agent reaches the web, whatever its registry flag (`may_use_web`) says; web access opens
  only under the cloud profile. The one place web access is opened is
  `search_router.SearchRouter.search`. Before the query masker and before every engine (api
  plan, direct fetch, ddgs, the DDG scrape, Brave), it refuses for roster agents and system
  callers alike when `search_router.web_access_open()` is false. That function is true only for
  exactly `cloud` in `SHIMMER_BACKEND_PROFILE` (unset means cloud; empty or unknown stays
  closed). The refusal is logged `web_access_refused backend_profile=<p> agent=<a>` and raised
  as a PermissionError. `_run_summary.md` states the backend profile and whether web access was
  open from the same function (`write_deliverables_run_summary`, amended in both pinned
  baselines), and the console's startup backend line says whether it is closed or open (read
  from the profile `/health` reports). Outside the rule: `scripts/corpus_validator.py`'s corpus
  download, an operator tool no agent and no run calls. Check 316 (`scripts/web_access_checks.py`).
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
  `.tar.gz`, which has been force-committed under `docs/fix/` before. It refuses an archive
  with bytes after its last compressed stream and one whose suffix names a format it cannot
  read (`.lz`, `.lzma`, `.Z` among them), fail closed (D-183). Checks 275 and 276.
- RELATIONS-B (INFRA-046, operator-approved in chat 2026-11-05, D-264): `contradiction` is
  appended to the Finding record, with the optional field `quote_b`: two passages of one unit,
  in words, that cannot both be true (`finding_record.TEXT_RELATIONS`, no figure relation). Only
  a model writes it, and only the two judged paths keep it: `paired_review.judged_item_refusal`
  refuses one that is not irregular, lacks a quote, has no unit text, has a quote under three
  whitespace-separated words (G1's bar), quotes text its unit does not hold, or quotes one passage
  twice (same words or overlapping places). `paired_review.mark_screened` then sets `text_screened`,
  which `agent_wrapper._finalize_envelope` removes from every model reply; `is_finding` and
  the benchmark record reader count the relation only with that mark, so from any other agent, or
  refused, it stays an ordinary item (`is_finding_shaped` is what the judged paths read first).
  Python checks the words, lower-cased with spacing folded, never that they contradict; the record
  stays a model's, marked and never promoted, and `finding_record.reader_line` shows both passages.
  A quote is scrubbed like any free text, whole spans only: a fragment of an approved span in a
  quote is a condition on activating the layer (open item 86), as in any model sentence. The
  console's `/findings` route carries no quote field. No scoring rule
  changed, but a kept contradiction decides its item like any model record, so an item decided by
  a refusal or silence can now be FLAG. Measured, not preferred: no relation could carry a
  contradiction in words, one cause of ContraDoc's zero beside the model (D-263). The second quote
  is held to the unit though a call also shows its neighbours. Check 322.
- RELATIONS-C (INFRA-047, operator-approved in chat 2026-11-06, D-278): a `contradiction` may
  stand in two units of one document, only from the passage pair step (`scripts/passage_pairs.py`,
  a rule declaring `[compare: passages]`): Python chose both passages from the document, the model
  said contradict in both orders, and `judged_item_refusal` then holds `quote` to `unit_id` and
  `quote_b` to `compared_unit_id`, given `second_unit_text`. Only that step passes it, so a
  model's reply on a judged path that writes `compared_unit_id` is refused
  (`CONTRADICTION_SECOND_UNIT_NOT_CHECKED`). No field, relation or prompt changed. The record
  sits at the first unit, `reader_line` names both by Python's mark, and it stays a model's,
  marked, never an amendment. Check 324.
- CHOICE-A (D-S41): a narrow question can be decided from the local model's own probabilities
  over a fixed answer set, with no generated text (`scripts/choice_decision.py`). One forward pass
  (`final_models.next_token_logits`, inside the pinned attention, one shot) gives the next token's
  logits, so an answer is scored on the token that writes it after the prompt, and answers sharing
  that token are refused. Probabilities are renormalised over the declared set, `declared_mass`
  keeps what the set held, confidence is the top probability, and below the threshold, on a tie or
  with no threshold the decision is `cannot be settled`. A threshold lives in
  `config/semantic_thresholds.json` under `choice_decision`, measured with the error rate it
  produces; none is measured, and a family with none decides nothing. `AgentWrapper.call_choice` is
  the route (local backends only; the caller masks, as `passage_pairs.outbound` does): one reply
  record with `decision` and no reply. The replay's form is `choice` (`benchmark/baselines/
  choice_judge.py`, no bound controller file changed; a pass applies no threshold). The passage
  pair step reads `form` in `config/passage_pairs.json`: `reply`, shipped, or `decision`, adopted
  only by a recorded decision. A finding from a decision is a model's, marked, never an amendment,
  with no Finding field added: its quotes are the passages Python chose, `explanation` stays empty
  since the deliverables show that as "The model wrote", and the decision and confidence are
  Python's `reader_notes` sentence, from the pairing map row (`decisions`, `decision_notes`) through
  `paired_review.model_item_notes`. The reading is `benchmark/baselines/choice_read.py`, the bar of
  `docs/loop/stages/C_BAR.md` in code: `read-a` opens half A alone, `read-b` refuses without T's
  frozen recipe digest or a stated `--base-alone` and counts every read of half B in a file it
  appends to; keys through `tools/score_corpus.py` only. Nothing here has run on a real model.
  Check 325.
- PAIRS-A (P2 (a), D-S38, D-274 to D-279): a rule declaring `[compare: passages]` (nothing else
  on its heading; paired review only, in wide review it is listed as not judged) makes no unit
  plan and takes no place under `--pairs-per-unit`: `scripts/passage_pairs.py` splits the document
  into sentences, ranks pairs by the embedding model (`config/passage_pairs.json`: 40 pairs, 400
  passages, 5 failed calls in a row stop the rule) and puts each to the judging agent in both
  orders, one narrow question, free form (`_free_form_call`), a record only when both say
  contradict. The call skips `run_task`, so it applies the masker itself, with the whole document
  as `context`: `sensitivity_layer.mask_text` detects spans on context plus text and, under a
  context only, also replaces a name's capitalised words one by one, since a detected span
  often runs past the name. A script with no capitals has no such words, so a bare name there is
  not found: a condition on activating the layer. Detection runs on each pair call on a sensitive
  network run, its cost unmeasured. Failed calls, partial stops and preparation failures each
  reach the reader in their own words; pair calls count in `calls_made` and `judging_calls`. The
  measurement is `benchmark/baselines/pair_judge.py`, on the replay pass. Check 324.
- RELATIONS-A (INFRA-045, operator-approved in chat 2026-10-31, "Ben simdiden onayliyorum
  yapalim."): four relations are appended to the Finding record (`rate_mismatch`,
  `carry_mismatch`, `copy_mismatch`, `unit_mismatch`) and Python computes them in the paired
  review (`scripts/relation_checks.py`, from `paired_review.compute_checks` and `plan_calls`;
  a runtime module despite its name, declared so it travels in the cloud source archive, D-204),
  posts them as its own records and renders their amendments like every computed finding. A
  RATE is a part, a whole in the same measure and a proportion in a declared dimensionless scale
  (`%`); the rule must name the proportion and one other figure by the unit's own labels, the
  third is the same-measure figure sharing most words with the rule (a tie is refused), and the
  figure compared is the one the rule names first. A rate is refused (`rate_reading_ambiguous`)
  when its figures also fit another plain reading (the larger is the smaller plus or minus the
  proportion of it), and a share of a zero whole is refused; which arithmetic a rule's words
  mean is never decided in code (D-198). A UNIT MISMATCH is a stated total (or a figure
  a band applies to) in another measure than its column (or band), converted by a decimal prefix
  on a base, both declared in `config/unit_conversions.json` (`ha`, `dB`, `min`, `cd` against
  `a`, `B`, `in`, `d` never convert); a unit with a digit or caret never converts, and an
  unconvertible pair is refused, on the band path too for a figure the rule names. It is
  attributed to the one paired rule whose declared `[scope:]` or `[requires:]` reads the
  figure's label or its measure, never to the sum or band rule it was compared under, and is
  refused (`unit_rule_undeclared`, `unit_rule_ambiguous`) when none or more than one does
  (D-198, open item 76 closed). An agreeing rate, copy or carry settles its rule only when the
  rule names nothing that check did not read; otherwise the rule's other plans stay. A COPY is a table row whose key cell is exactly another unit's
  heading, in a column that unit states as a label line; the rule must name the key column and
  the value column. A CARRY is a column's first row against the column sum of the unit just
  before, under the same first-row key; the rule must name the column and that key, and a unit
  before that does not add up on its own is refused (which figure it carries is not arithmetic).
  Refusals go to the pairing map's `relation_refusals` (every paired review writes the list) and
  a multi-round document's `relation_refusals`; a copy or carry cites its own unit's passage and
  the other unit's as `compared_with_refs`, names it in `compared_unit_id`, and the text of every
  unit a copy's key cell names (whatever the copy's outcome) and of the carry's unit before is
  the signature input `neighbours`. Measured by the parallel track, not reproduced by the loop
  (D-197, D-198): its replays with the pipeline's own functions and the bundles' reference
  tables (no model) found, on the 27 L12 development entries, 32 losses, 20 of them in these
  four kinds (rate and ratio 8, copy 4, carry 4, unit 4), and moved the 6 L12 tests (f1, f2, f6)
  from 70 to 90 of 90 located, the 24 other bundles of those seeds from 274 to 350 of 360 and
  108 bundles of 18 fresh seeds from 1032 to 1320 of 1350, with 0 irregular records on 24 clean
  twins; those figures predate D-198, whose refusals and declared attribution may lower them.
  The loop's own replay (D-197) found 0 new Python records on the L10 and L11 public benchmark
  documents. The L12 cloud evidence itself was made by the old code and is not re-run. Applied by the loop under
  Annex D D-S19 item 1 (operator's authorization, "1 dongu uygulasin"), decision D-197; the
  fresh review's fixes are D-198. Check 319.
- UNCOMPUTABLE-A (loop S5, D-068): on a paired plan of kind `uncomputable` (Python computed no
  comparison), the model's answer is kept as a model-written Finding record, never discarded:
  stamped by Python with the judged-absence stamping and the PLAN's rule
  (`paired_review.stamp_from_plan`; a rule id the reply names is replaced), screened by the shared
  refusals (`paired_review.judged_item_refusal`: quote not in the unit and the three absence-claim
  refusals; listed in the pairing map under `uncomputable_refused`; R1, D-S22 item 1 (d): then,
  on both judged paths, an absence relation (`finding_record.ABSENCE_RELATIONS`) with no quote, a
  figure relation (`finding_record.figure_relations()`, the declared relations less the absence and
  earlier-version ones) whose `value_a` and `value_b` are neither a number nor a date (`paired_review._is_figure`), and an earlier-version relation
  (`finding_record.PRIOR_RELATIONS`) when no earlier version was loaded (`prior_declared`, from the
  documents `_prior_comparison` runs on), each under its own reason; check 322), kept only from a reply that is
  ok and did not refuse (why it gave none in `uncomputable_judged`), and posted once as Python's
  stamped copy (`stamped_by: python`, `judged_path: uncomputable`) under the model's backend and
  model, so written by `model`; the call's own post still withholds its items. Outcome
  `judged_uncomputable` (`judged_listed`, `judged_refused`), and a call with an answer kept ends as
  `not_promoted` in the reply outcomes (D-268); `advisory_not_kept` names runs before
  D-068. Never promoted (check 269), marked wherever model findings are shown. Check 290. The
  benchmark adapters label a semantically incomplete run from its records (D-066), report
  completeness per document and arm, and add sensitivity S-6.
- CELLS-A (P2 (b), D-S42): a rule declaring `[compare: cells]` (read and refused as `passages` is, default off) has its text taken as a claim. `scripts/cell_selection.py` reads a unit's pipe table and ranks rows and columns by the one tokeniser's words, weighted by rarity among the table's labels, by figures the claim writes, and by an injected embedding that only settles what those leave equal, never reading a key. It keeps the caption, header and key columns, the columns named (all when none is) and the rows named, with unnamed rows up to `fill_rows`, since a claim on one row is usually a comparison and that cannot be read structurally (`config/cell_selection.json`). A claim naming nothing in a document's one table within the caps sees the whole table (`selected_by: whole_table`, counted apart); above them, or on a tie the caps fall on, it is refused with its reason. The question is the replay's claim form, held equal by check 326, masked against the whole document, and decided by `AgentWrapper.call_choice` (D-S41); `_narrow_ask` in the pipeline driver is the one call both P2 steps make. With no measured threshold nothing is asked. Every decision stands in the pairing map's `cell_claims` row, identifiers and numbers only. A settled "not met" is also the relation `claim_not_met` (INFRA-048, operator-approved 2026-11-07), written at `cell_selection.finding` alone: `quote` holds the cells Python selected and `quote_b` the claim, so no field is new. `finding_record.TEXT_RELATIONS` holds it for the mark, `CELL_RELATIONS` tells it from a pair of passages. `paired_review._cell_claim_refusal` refuses it unless the cell step passed its `selected_cells` (so a reply on a judged path that writes it is refused, as a second unit is), the rule declares `[compare: cells]`, it is irregular, `quote_b` is the rule's own text and the cells stand in the unit; Python never checks that the claim fails, it is a model's, marked, never an amendment, and `holds` and `cannot be settled` make no record. `doc_judge.select_cells` is this selection with no embedding, so it stays pure for `load_prompts`, and a claim refused is listed in the prompts file. On SciTab the key states no cells, so reach is unknowable there. Check 326.
- DETECTION-DEV-A (D-S26 item 1, D-194): the benchmark adapters have a DEVELOPMENT scoring mode,
  `label --scoring detection_dev`, built in ONE helper (`benchmark/adapters/common/detection.py`);
  each adapter only declares its document-level reading on its `Spec` (`detection`: CUAD
  `exists`, ContractNLI and SciTab `three_way`, ContraDoc `each`; FinDVer, CUAD-claim and the
  synthetic suite none, so refused). A label rests on a kept claim: an item with no kept claim is
  `silence`, ABSTAIN in every measure, its `v2_primary` label reported apart, never a detection.
  Unit states come from kept records over the run's own pairing-map unit list; CUAD is absent
  only when every unit lacks the clause; ContractNLI's not mentioned is reached when every unit is
  unsettled (UNCERTAIN or an absence relation), and an absence relation is never a contradiction.
  `v2_primary` and `benchmark` (the preregistration's modes) are unchanged; any change to the
  rule is a new decision written before the scores it changes are read. Development builds only
  (a parts record naming any other side is refused); the `v2_primary` decision's counts sit under
  `v2_primary_counts`, never mixed into `counts`; no S-4 (D-195). D-472: the cell step's decisions are read from the
  pairing map's `cell_claims` row (`detection.cell_decisions`): settled as holding is a unit that holds, not settled
  a unit that is uncertain (never CLEAR), a settled "not met" speaks through its kept record alone, and S-8 reads no
  decision; `tools/score_corpus.py` `benchmark_items(..., scoring="detection_dev")` is the scorer's route (B3 only,
  `v2_primary` by default). D-471: the SciTab build takes `--rule-declaration "compare: cells"`, the rule's text then
  the claim alone; each benchmark's build admits its own declaration only (`bundle.BENCHMARK_DECLARATIONS`). D-478: the
  cut is computed from the as-shipped rules in every build (`bundle.shipped_rules`), so a declared build's parts,
  items and keys are the as-shipped build's; a claim is CLEAR only when no unit carries a settled "not met" cell
  decision, kept or refused (`detection.cell_not_met`, else a conflict); the gate's system arm is
  `gate_score.system_arm`, labelled in the mode `system_test.SCORING` declares per benchmark (D-476: ContraDoc
  `v2_primary`, SciTab `detection_dev`). Check 317.
- GATE-LEAKAGE-A (D-S100, D-S102 item 3, D-403): `benchmark/adapters/common/gate_leakage.py` is the
  leakage check for every item set, split so no one reads both sides: `fingerprint` on the lead's side
  (every JSON string of at least 8 words of each named part, `#key,key` to read under keys only, a judge
  mix as `#rows,held_out`; hashes, 8-word runs and bge-m3 unit vectors, no text) and `check` on role
  B's (`--benchmark contradoc|scitab` or any set's `--candidates`; counts and ids only, a group out
  whole). It reads JSON, text and .tar.gz/.tar/.zip members, refuses other archives and the fresh set's
  folder on every path and archive member (one exception, D-442: the fresh ids file, by its pinned digest,
  for `exclude-ids` only), and lists what it skips (key files and model assets unread). Thresholds are constants written first (`docs/loop/stages/LEAKAGE_PROTOCOL.md`: exact, one
  8-word run, cosine at most .92 and read from step 2's record, listed source or group); other thresholds or a check without the cosine rule
  are refused by the draw. Not lane/causal's frozen `leakage.py`, which it does not replace before 12
  November. Check 325.
- GATE-SET-A (D-S92, D-S100, D-380, D-S120): `benchmark/baselines/gate_set.py` draws the gate set on role B's
  side from the groups the leakage check kept (salted SHA-256 orders, whole groups and papers, the quick
  subset first, then the claim set: whole groups or papers in claim-salt order until 230 ContraDoc
  documents, or 352 SciTab claims whatever the class setting (counted as drawn; the draw reads no
  label), stopping at the first that reaches it, the size being the floor (D-S120 option A, D-454,
  D-458), too few refused; a leakage result without the
  cosine rule, an exclusion file, this input or every required part refused) and declares SciTab's class setting from the
  drawn claim set's gold counts after the draw (D-458; 3-class at 30 and 15 percent not enough info, else 2-class). The
  declared setting is required by `scitab/adapter.py`'s headline (`score --class-setting`),
  `judge_read.macro_f1` and `figures` and `choice_read.figures`, never read off the gold present; G1's
  sets are 2-class (`judge_read.G1_SETTINGS`). `docs/loop/stages/GATE_SET.md` holds the rules. Check 325.
- GATE-SCORE-A (D-S99, D-376, D-403): `benchmark/baselines/gate_score.py` gives the gate's figures in
  each paper's metric (ContraDoc accuracy, ABSTAIN wrong; SciTab macro-F1 in the declared setting), each
  with its item count and one paired cluster bootstrap (by document, or by table), bar (a) at 10 points
  with the interval above zero and bar (b) at 5 points below the cloud reference; the k-th claim read is
  at level 1 - .05 / 2^k, k counted from the committed openings, and read once through `figures`, which takes the frozen set file, checks its digest against a pin and the arms' items against
  its list (`compute` is the computation alone;
  the two pins are the digests of the freeze's two set files, and k counts only `gate-claim-set` rows writing that digest
  in full); only `figures` output may be recorded as a gate figure (D-422: a later read needs a decision carrying the marker line
  `**Quick-subset evidence.**`), a quick-subset read at 95 percent, steering only. ContraDoc's adapter reports
  R-acc(pos) and EHR over true positives, B3's labelled unit-level. Check 325.
- WRITTEN-BY-A (loop S2): who wrote a finding is read off the bus post it travelled in
  (`finding_record.written_by`): `python` only for `backend` `paired`/`computed` with a model
  id starting `python`, `model` for everything else, including an item no envelope claims.
  Items are stamped (`stamp_written_by`) before any copy is made: the stamp joins each item to
  the envelope that carried it by object identity, which holds only for the envelope's own
  items, so it runs first and every later reader reads the stamp. Never compare the identities
  of copies, and never decide provenance by an agent name or by a field the item itself carries
  (a model's `provenance` is removed when it is stamped). `GET /runs/{run_id}/findings` carries
  `written_by` on every record.
- JUDGE-AGENT-A (D-S55 items 1, 2, 4, 5; D-S56 item 1): a narrow task (`cell_claim`,
  `passage_pair`) is taken by the registered agent whose contract declares it in a `judge` block
  (`judge_agent.role_for`; no agent name in code), and only when the task is asked from the model's
  probabilities (the pair step's `reply` form keeps its route); with none declaring it the rule's
  subject chooses as before (`pipeline._judging_role`, `_paired_judging_agent`) and nothing else
  changes. The task's declared tools are Python's and run around the question: `find_cells` (the
  selection, shown as the CELLS block), `locate_figures` (each figure the claim writes, read off the
  CELLS block, shown as the FIGURES block in the question's `{tools}` slot) and `check_quote` (the
  judged paths' refusal, after the decision, never shown). With no shown tool declared the slot is
  "" and the question is the measured one byte for byte; the replay fills the slot with the same
  function (`judge_agent.claim_tools`, from `doc_judge.render_choice`). Each tool call is one record
  in `<run>/audit/judge_tools.jsonl` (indexes, counts, the question's digest, the call id), never in
  the pairing map. Boot refuses (`judge_agent.refusals`) a task two agents declare, a tool Python does
  not run for its task, and a role whose contract declares `checks: [ROLE]` on ROLE's backend or
  model. The agent is `JUDGE` (INFRA-049, operator-approved in chat 2026-11-08, "Tamam, birincisi
  ekle."), on `local_auditor` under its own `spec.model`; it writes no text, the quote is Python's,
  and no contract text reaches its prompt. Its own model is Phi-4 (`spec.model`; a `_LOCAL_PROFILE`
  entry with no model takes the registry's, D-313). A stated limit: in a run where both
  auditor-side models are used, Phi-4 loads beside Phi-3.5 and nothing unloads either. No shipped
  run reaches it (no shipped rule declares a judge task, and the pair form is reply until adopted);
  before a decision form is adopted, the peak VRAM of a run that loads both must be measured on the
  A10 (the cases or a replay), or the judge must unload what it does not need. Check 331.

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
  `agent_record.md`, `_run_summary.md`, the console (its proof needs Node and says so when skipped) and the
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
  judged-absence calls and the calls on an uncomputable plan, never asked for a note, apart
  (`paired_review.judging_call_counts`). A docx comment's author is read from the
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
- READABLE-A (open item 19, part 2): `reviewed_document.md` is the document under review for a
  person: its own text, whole and in order, each finding quoted under the unit it concerns (an
  amendment by its comment and suggested change, Python's other findings by their sentence and
  why no amendment, a model finding with the mark on the line that states it, a refused answer
  and a rule left unchecked in words), after a header with what was asked, the counts of each
  kind and what was not checked. It is a RENDER (`scripts/reviewed_document.py`) and decides
  nothing: amendments and model findings are the master's lists (`master_lists`, so the counts
  equal `review_data.json`), Python's findings are the list `document_summary.md` counts, the
  refusals and unchecked rules are the pairing map's; every amendment, Python finding and model
  finding given is shown once or the render raises. The per-agent record is `agent_record.md` (key `per_agent_deliverable`, renderer
  `_render_per_agent_md`, the board appends there). When the sensitivity layer is active both are
  text artifacts the redaction scrubs on disk (`sensitivity_layer.scrub.TEXT_ARTIFACT_KEYS`; checks 46
  and 47), and the reviewed document is rendered again from scrubbed inputs first (below). The document's own
  text and every text a model or an agent wrote are escaped (`_escape`: every backslash, every
  `>` and `<`, and `**`, `__`), so none of it can open a quotation (at a line start or after a
  list marker), raw HTML or bold, and no line of it reads as a finding block; the document's own
  code blocks and code spans are left as written, since Markdown shows them so and reads no
  markup there (`_code_lines`, `_code_spans`, conservative: no indented line after a list item,
  no span across a pipe; lines split only at a line feed, a carriage return or both, as
  CommonMark splits them, `_lines`), and outside them every backtick is escaped too, so none can open a
  span; a model's sentence is never cut, here or in the operative and grounding summaries
  (`summary_generators._whole`), and the grounding summary shows each cited passage whole, read
  again from its context document (`reference_builder.with_whole_passages`, given the texts by
  phase 6), or, when it cannot, the stored excerpt only where it cannot have been clipped, else
  no text (`summary_generators._passage_text`);
  the refusal and unchecked counts are stated only when the pairing record carries the paired
  review's lists (`absence_refused` and `uncomputable_refused`; `not_judged` and
  `judging_calls`), and say "not recorded" for a wide review, whose record lacks them, or with no
  record; amendments are counted apart by who built them; the header states the registry's size,
  not a count of rules evaluated; a unit whose text cannot be located is named in a section of
  its own. Under an active sensitivity layer (off as shipped), phase 9 renders the file again
  from scrubbed inputs (`reviewed_document.write_from_scrubbed`, called by the redaction's render
  callback, the inputs and the run's language recorded at phase 6 as `reviewed_render_inputs`, the
  activation record read again), the way the master's deliverables are: a span is gone before the
  renderer escapes anything or sets a finding into the text, so neither can hide or split one. It
  stays a text artifact as the second net. The scrub is ONE matching pass on the text as it stands
  (`scrub._scrub_one_pass`, for the text artifacts, the master and the body): every match of every
  span in every form (`scrub._span_forms`: the exact tokens with any whitespace between them, the
  tolerant form, and for a span with one plain number the form a record writes it in, in both
  Unicode normal forms) is found, overlapping and touching matches merge, and each range is replaced
  whole by the placeholder, never by text a model chose. The tolerant form reads a span with or
  without the configured Arabic article and vowel marks, across invisible characters and `scrub._SEPARATORS`, and
  each gap and the token after it are one atomic group, so a gap cannot swallow tokens and backtrack
  on repetitive text. `_redact_obj` scrubs every free-text string and leaves numbers and
  `_STRUCTURAL_FIELDS` alone, so a span cannot change what a record is; the survivor grep
  still reads them. A unit id writes its heading's words (`pairing_map._slug`), so an id carrying a
  span is derived again from the scrubbed text (`redaction_stage._neutral_unit_ids`) and the old id
  scrubbed as an exact string. Every document that reaches the scrub is scrubbed and grepped with
  every span proposed in the run (`redaction_stage._run_spans`; identical strings collapse, nothing
  else), a precaution, since a context passage can hold text any document's span names.
  Deterministic spans are read before any redactor call, from each document and from the context
  passages its grounding summary shows (`grounding_passages`). A document held or blocked at the
  redactor, or with an unreadable master (BLOCKED), is scrubbed with what is known, a known span
  surviving in it BLOCKS, and a render that raises BLOCKS that document alone, held or not; what the model would have marked in
  it is reported as `spans_unknown_from`. Only a document's own spans must be located in it; a
  document with none reports NONE, or `only_other_documents_spans`. `memo.md` ships as phase 9
  scrubbed it, where phase 9 did. The survivor grep is the net: it also reads every artifact but the docx with its
  escapes undone and as running text (`scrub._running_views`). The matcher is not complete: open
  item 86 gives what it is known not to read. A unit that ends inside a code block has its findings shown
  after the block, and a fence left open is closed after the document. Check 320.

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
  rule, both figures with their units and the relation; a sum names the values it added, a
  product its two factors, a rate its three figures by their labels, and a copy or a carry the
  other unit it read the compared figure from (RELATIONS-A). An absence says what was checked in code instead of figures. The
  rule's own words follow, quoted, and a model's sentence comes last, labelled as the model's.
  Every template has a row for the second output language (tr) in
  `scripts/ui/localization_catalog.js`. A figure is written as the unit's own text writes it
  (`61 units`); a figure the unit does not write keeps the record's format (`16.0`, checks 171
  and 172). The two provenance sentences check 269 reads stay word for word.
- An amendment and its finding sit at the UNIT'S OWN PASSAGE: phase 5.5 cites the indexed
  passage of the copy under review that holds the unit's first line, when exactly one does and no
  other unit claims it
  (`paired_review.unit_passage_refs`); a figure compared from elsewhere (a reference table, a
  bound, or for a copy or a carry the other unit's own passage) is cited as such
  (`compared_with_refs`), never as the location; a unit Python cannot
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
  an agent reaches the web only if its registry flag permits it, and only under the cloud
  backend profile (NO-WEB-LOCAL-A).

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
- `scripts/chat.py`: the tkinter chat interface (Qwen NL parsing or command mode). Its startup line says only what the probe checked (libraries import, a model is named) and a request the model did not answer says so before the command parser's reply (check 310). A mode the person set wins over the mode a review request is read as (proposed by the model or defaulted by the parser), and the window says so (D-183, check 310).
- `scripts/server.py`: the token-gated FastAPI dock. Config is env-driven (`SHIMMER_*`,
  read once at startup, printed to stderr); `SHIMMER_TOKEN_HASH` is required. The
  [runtime reference](docs/RUNTIME_REFERENCE.md) route table is the complete route list and gate check 167 fails if it and the app disagree
  in either direction; check 116 does the same for the `SHIMMER_*` env table.
  `/runs/{run_id}/findings` and `/runs/{run_id}/pairs` serve the STRUCTURED review (typed
  Finding records off the bus, and the pairing map with no document text);
  `/runs/{run_id}/deliverables` stays the human artifact. The pairing map's `absence` record
  and a finding's `absence_path` are on disk and on the bus but not yet in the two routes'
  projections (recorded in docs/RUNTIME_REFERENCE.md); the same holds for RELATIONS-A's
  `relation_refusals` and a finding's `rate_fields`, `rate_figures`, `compared_unit_id`,
  `compared_field` and `compared_with_refs`.
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
- CLOUD-CONSOLE-A (D-S49 item 3, D-S62 item 9): the console's cloud mode, "On a rented cloud machine" /
  "Kiralık bulut makinesinde" (`scripts/console_cloud.py`, routes `/cloud...`, screens
  `scripts/ui/cloud_mode.js`, `docs/CLOUD_CONSOLE.md`), goes only through the sealed, bound path: it stages
  the chosen files, reads the inventory (`tools/console_cloud_inventory.py`), seals an exposed B3 bundle,
  verifies, binds, reverifies and preflights with the existing tools, and launches only
  `tools/ordinary_final_bound_cloud.py --detach` on the private ledger under the purpose `console-<plan id>`,
  its run folder under `output/cloud/<plan id>/`. A launch needs the sealed cap typed back to the cent and a
  one-time code (15 minutes, spent on first use). It refuses a sealed run, no credential file found (located
  only, never read or shown) and no `budget_open` line (it never writes a ledger line). The forecast is shown
  as measured (date, machine) or estimate (`config/cloud_forecast_basis.json`), no instance limit is
  shown since there is none (D-S95), progress is `tools/ordinary_final_progress.py`, and the actual time
  and cost come from the ledger's termination line. "Shut down" needs both the terminated status and the
  cleanup's own-instance-absent, and only then the machine and its copy of the documents are said to be gone;
  each document's deliverables are listed from the collected run and served only by listed name
  (`/cloud/plans/{plan_id}/files/...`, `/deliverables/{doc_id}`). Each screen says where the documents go.
  No bound controller file changed.
  Check 338 (`scripts/console_cloud_checks.py`, fakes only).
- DEMO-A (D-S48): the console's first way in, "Demo: no installation, saved examples", is a
  static folder built by `tools/build_demo.py` (`--rounds`, `--review`, `--documents`, each
  `synthetic=` or `public=` a folder; a run may be a batch entry's `collected_evidence.tar.gz`,
  unpacked into a temporary folder with no reply record and no parent path; with no `--documents`
  the documents are read from the runs' own evidence when one folder there holds every document
  they name) into `demo/` at the repository root by default: `index.html` with every record
  inlined (template `scripts/ui/demo.html`), `files/` holding byte copies of the deliverables to
  download, `open_demo.bat` and `open_demo.sh`. No server, no token, no key, no storage: a Content
  Security Policy of `default-src 'none'` forbids every request. It is never served by the server
  (CONSOLE-A stands: only /health and /console answer without a token); `console.html` carries
  one line in both languages (en, tr) naming it and saying to open `open_demo.bat` in the demo folder,
  with a link relative to the file (`../../demo/index.html`). It decides nothing: Python's
  findings are the round review's records and amendments built from computed findings; every
  model item (master model finding, answered movement, kept suggestion) is shown apart with
  `MODEL_FINDING_MARK`; every label has a tr row in the catalog or the build refuses. Every case
  screen first states how each run ended, from the run's own records (`evidence/result.json`, the
  completion record, and the header Python writes above each set-aside reply in
  `audit/contract_violations/`, never the reply): a run that failed integrity is said to have failed,
  with its reasons in words. A run may be given as a run folder, an evidence folder, a batch entry or
  its archive; a batch entry whose seal record says sealed, or cannot be read, is refused. Under
  `benchmark/` it reads only `benchmark/dev_cases/` (the two worked cases' own source documents,
  development cases built for demonstration: one synthetic, one a public UN text); every other
  path under `benchmark/` and a sealed run (CONSOLE-A) are refused, and documents under `external/`
  too (a run's evidence may lie there, where the loop keeps its cloud evidence), in any checkout. Two builds
  of the same folders are byte-identical. Proven on `scripts/fixtures/demo/` (two INVENTED cases,
  written by `tools/demo_fixture.py` through the real case phase with stub answers; a fixture build
  says so on every screen, `--test-material`). Publish nothing without the operator's yes (D-S48
  item 4). Check 341 (`scripts/demo_checks.py`, needs Node).
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
  EDITOR_CLERK's constraint has no replay on the model yet (fixtures and saved replies only);
  its replay file and bar (all 61 distinct saved prompts: 49 valid, 8 stamped, 4 failed; R2's
  rules A to D) are built by `benchmark/baselines/producer_replays.py editor-clerk`. Its `roles`
  command builds a ROLES file (`replay_prompts.py extract --checkpoints tuned,base`): each other
  producer role's saved prompt replayed on the tuned producer and on its own base, both loaded
  once, every reply judged by its agent's own contract, the pairs counted for a sign test
  (D-S57; in final mode every local_producer role loads checkpoint 168's adapter, trained on
  PROCESSOR only). Neither changes a bound controller file. Check 297. The PROCESSOR candidate
  for checkpoint 168 (D-S57 item 3, `docs/loop/PRODUCER_TRAINING_PLAN.md`, written before any
  row) is built by `tuning/producer_v4/` (public carriers, v3's clauses, the frozen interpreter's
  labels) and trained and tested by `benchmark/baselines/producer_train.py` on the same replay
  pass (168's recipe; the test asks `tuned` and `candidate`, the candidate on the pinned base
  with its adapter, `bare_model.LocalBackend` in final mode). 168 is replaced only under the
  plan's rule (section 8: a seeded split by document into a tuning half and a held-out half;
  `benchmark/baselines/producer_score.py` scores the tuning record and refuses a held-out pass or
  score unless `docs/loop/HELDOUT_OPENINGS.md` holds a committed opening, D-330). Check 335. The narrowed producer roles of INFRA-050 (LEGAL_ANALYST's claim
  support, SPEECH_ACT_TAGGER's act from the operator's declared set, CITATION_RESOLVER's choice
  among Python's candidates, INST_FINDER's and ARCHIVIST's verbatim spans, the editorial verdict
  routed to the other family) are declared in `config/producer_questions.json` and built in
  `scripts/producer_questions.py`; every form ships `reply`, so each role runs as shipped until a
  form is `decision` with a measured threshold. Check 336.
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
  proofs on fixtures only (`tools/loop/request_ledger_check_checks.py`). Its sibling
  `tools/loop/issue_deferral_check.py` (D-S24 item 4; `--issues` is gh's open-issue JSON, never
  fetched) fails on an open issue with neither `operator-deferred` nor `loop-deferred` and no
  stage milestone S05 to S14, a `honesty-or-release` issue after v1 (S06, S08, S09, S12, S14, from
  D-S18 item 3) labelled `loop-deferred`, a SCHEDULED or DEFERRED row naming no `#nnn`, and,
  from D-179 on, a decision's `**Moves.**`, `**Defers.**`, `**Drops.**` or `**Skips.**` marker
  line naming no issue (a declared marker, not a word list, under WORDS-A; earlier decisions
  are grandfathered and counted); check 315 runs its proofs on fixtures, and it runs at every
  stage gate beside this one. A third sibling, `tools/loop/status_evidence_check.py` (D-S101 item 3,
  D-383), fails on a finished-state claim (done, verified, closed, merged, measured, applied,
  and the Turkish bitti, doğrulandı, kapandı, birleşti, birleştirildi, ölçüldü, uygulandı) with
  no evidence or a pointer that does not resolve, in the request ledger (DONE and VERIFIED
  rows), LOOSE_ENDS.md (its State column), the return brief, FOR_SECKIN.md, PUSH_RECORD.md,
  AFTER_V1_PLAN.md (claims read only in declared forms, never from prose), PROGRESS.json
  (`status` done or verified, its own id removed from its fields) and gh's closed-issue JSON
  given as a file (never fetched; not planned counted apart). A decision must exist and, for a
  ledger row or a PROGRESS stage, at least one decision it names must name its own id; a commit
  must be an ancestor of the loop branch and have changed every tracked path it is cited for; a
  file must exist inside the root or the private folder and not be empty (a bare name only
  directly under them); a run folder must hold a non-empty `result.json` or `FINAL_STATUS.json`
  directly or in `evidence/`; a branch name, an Annex D entry and a short id are no evidence; a
  ledger status outside DONE, VERIFIED, RUNNING, SCHEDULED, DEFERRED and BLOCKED fails; an absent
  record fails unless named with `--skip` (closed issues need `--closed-issues` or `--skip issues`). A commit named with no path is
  checked for ancestry only; a finished state written only in running prose is not read. In
  the push record a commit may instead be an ancestor of refs/remotes/origin/main (the page lives
  on main, D-S98, D-192); `--fetch-push-ref` refreshes it with a read-only fetch first. A file tracked on the loop branch counts
  when the checkout's disk lags it. A record holding a state word with no claim in a declared form fails. Not read,
  stated in its docstring: the progress page (generated from records read at their source), the
  12 November package (not built), and promises never closed (the D-S97 look-back's work). Run
  at every wake, merge, push and report; check 343 runs its proofs on fixtures.
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
  `document_summary.md`, `reviewed_document.md`, `agent_record.md`) plus a top-level
  `_run_summary.md` index;
  a draft run also keeps the memo as `<doc_id>/memo.md`. The canonical basenames live in
  `run_context.DELIVERABLE_FILENAMES` (one source for the writer and the pipeline). `audit/`
  (with `pairing_map.json`, carrying per unit `band_conditions` and `prior_comparisons` and
  per document `prior_orphans`) and `logs/` sit alongside. `logs/call_evidence.jsonl` records,
  per model call, the structural identifiers of what the call was shown (unit, neighbour unit
  ids, heading, reference ids supplied and rendered, rule ids, agent, backend, model, run,
  call id), never text; the call id joins the cost row and the bus post
  (`scripts/call_evidence.py`). `scripts/fn_evidence.py` classifies every missed expected
  defect into one of four evidence classes from saved artifacts only, through the scorer,
  which is the only reader of a key. `tools/miss_diagnosis.py` runs that over many (run or
  collected_evidence.tar.gz, key) pairs through `score_corpus.score(..., result=...)` and
  writes one loss table (classes, sub-causes, the code sites that decide them; check 318). An
  adapter item with no evidence unit is DOCUMENT-LEVEL only when its gold marks no location
  (`location_measurable` false) and nothing was cut (`document_level`): it is read over every
  unit of its own document in the run's pairing map, takes the WEAKEST class any unit reached
  (`document_units`, `document_level_class`), and its sub-cause is read on the units of that
  class only. An item marked beyond the cut with no unit is UNKNOWN `evidence_cut_undecided`
  (a part kept only to mid-text, or a text that matched no part, cannot be told from the key),
  one whose marked evidence matched no part `item_evidence_unmatched`, one whose key does not
  state `location_measurable` `item_location_unstated`, a document-level item whose key marks
  another item beyond the cut `document_level_on_cut_document`, and a run with no pairing map
  `no_pairing_map`. A cut that removed the evidence of an item marking no location is otherwise
  invisible (the parts record is in neither the run nor the key), and on a benchmark
  whose items never mark a location (CUAD and SciTab today) a cut is never seen. An uncomputable
  answer Python refused is its own sub-cause, `exposed_uncomputable_refused`, decided from the
  judging row of a call that kept nothing and reports refusing, its reasons read on that call's
  unit and rule (a refusal row carries no call id).
  Runs never overwrite each other.
- `durable/`: learned and governance state that survives reset: `learnings/`, `cache/`,
  `global/`, `governance/`, `reference/`.
- `ontology/stores/`: the cross-run ontology store (capture and the graph; no GNN state is written
  by a run, D-S112 item 1). Its storage
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
  NEVER LEARNS FROM RUNS (D-S112 item 1, D-417): no run path calls `gnn_update` (check 64,
  its proofs in `scripts/ontology_gnn_rule_checks.py`). It is trained only by its own command,
  `scripts/ontology_gnn.py train --training-set <declaration> --state <file>`, on a declared
  training set (`ontology_gnn.py declare`: one graph by path and SHA-256, its material named, and
  the declaring person's own statement, by `--domain-agnostic --case-agnostic --declared-by`,
  that it is domain- and case-agnostic; the tool never writes that statement and cannot verify
  it). The run store is refused by place, by content (the graph's bytes against every file of
  `ontology/stores/`) and by the build provenance `ontology_graph` writes (`built_from`); a graph
  copied from the store and edited is not caught. A GNN state carries its whole chain of training
  sets (`training_sets`); a state without it, as every run-trained state was, is refused by the
  state reader, the candidate finder (`/ontology/candidates` answers 409) and the training
  command. The run-trained state of the main checkout was archived out of `ontology/stores/`
  with its record (D-432, `tools/archive_ontology_stores.py --only`). The run end is
  `pipeline._ontology_run_end` (capture and the graph rebuild), which check 64 runs with
  `gnn_update` recorded. Training further on one user's own material is a later opt-in path,
  not yet built. Within its own training,
  `gnn_update` restores persisted weights and keeps a trained-node high-water mark, so a
  second update over the same declared graph has a zero delta and unchanged weights. It has
  learned nothing because the TIER-2 SIGNAL IS EMPTY, not because it forgets. Every candidate set
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
