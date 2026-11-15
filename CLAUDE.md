For the lead session only, started by Seckin in the main checkout: if `docs/loop/private/LOOP_STATE.md` exists and its status is not DONE, read `prompts/SHIMMER_AUTONOMOUS_LOOP_2026-10-27.md`, then that state file, then the newest file in `docs/loop/private/handoff/`, before doing anything else, and continue the loop from the step it names. Subagents, teammates, checkers, lanes, role sessions and clones ignore this line and do only the task they were given.

# Project Shimmer, agent operating contract

This file is the short rule list. `docs/CLAUDE_REFERENCE.md` holds the complete former text of this file verbatim,
under the same headings, and is binding exactly as this file was: read the sections for the area you are changing
before you change it. The founding specification is [genesis.md](genesis.md) (Parts I to XXVII); read it before any change.
Shimmer is a standalone document processing swarm governed by an append-only constitution. README.md is the newcomer guide.

## Hard rules (full text: docs/CLAUDE_REFERENCE.md#hard-rules)

- No em dashes anywhere. Use commas, colons, periods, or parentheses.
- LAW-IV (privacy) is never edited and outranks LAW-0 for sensitive content, no exceptions. A single leak is irreversible.
- The constitution is append-only: the INFRA-029 guard refuses edits of existing amendments or seed laws without operator approval; no-gap ids, one verified append per write; every DELTA lives in `config/constitution.json` `amendments[]`.
- Model ids are read live from the provider, never hardcoded; a deprecated model STOPS the run; model choice is owned by `config/agent_registry.json`; use bare aliases, never dated snapshot ids.
- API keys live OUTSIDE the repository (`$SHIMMER_CONFIG_PATH`, sibling `../api_keys/config.py`, `.env_path`); never hardcode, log, echo or commit a key value.
- Domain vocabulary is operator-declared in `config/domain_vocabulary.json` and appears in no code (checks 174 and 22); `input/` and `benchmark/` are never scanned.
- One Unicode-aware tokeniser: `pairing_map._norm_label`; `reference_tables._words` delegates to it.
- No domain-specific content in `scripts/`: domain knowledge lives in `config/` and `durable/`; retired tooling lives in `scripts/archived/`.
- English only for code, config file names and folder names; no spaces or unicode in paths.
- Every convention review finding cites at least one CONV-* and at least one REF-*.
- A convention heading carrying the operator's own rule id keeps it as its `category`; the `_CATEGORY_KEYWORDS` table is deleted and must not return (check 176).
- A heading's brackets carry severity, subject tags, and the `[scope: ...]` and `[requires: ...]` declarations; scope is declared by the operator, never derived from text or counts.

## Hard-rule feature blocks (one line each; read the full text before touching the area)

- WORDS-A: meaning decisions go to the five-voter ensemble, never a keyword table; regex keeps structure only (full text: docs/CLAUDE_REFERENCE.md#words-a)
- UNITS-A: a preamble unit u00 is made from text before the first heading; no u01..uNN id moves (full text: docs/CLAUDE_REFERENCE.md#units-a)
- CONTROLLER-BINDING: a sealed bundle is bound to its controller source hashes; any bound-file change forces re-seal (the 14 November merge changed the runner, controller, bound wrapper, guard and sealer: re-seal every bundle) (full text: docs/CLAUDE_REFERENCE.md#controller-binding)
- LOOP-LAUNCH-A: every ordinary final launch is a loop launch under the budget guard, ledger, reaper and cap rule (full text: docs/CLAUDE_REFERENCE.md#loop-launch-a)
- B1-ARM-A: sealed arm B1 runs the bare model once per sealed checkpoint with the runner guards kept (full text: docs/CLAUDE_REFERENCE.md#b1-arm-a)
- DOCJUDGE-A: doc_judge judges each document and rule once with three outcomes and quote-checked claims; development only (full text: docs/CLAUDE_REFERENCE.md#docjudge-a)
- EMBED-ROUTE-A: leakage-fingerprint embeddings can run on a rented machine through the replay pass, one part per launch (full text: docs/CLAUDE_REFERENCE.md#embed-route-a)
- ARM-L-A: sealed arm L drives the launcher menu as shipped on the loop instance, integrity assessed only (full text: docs/CLAUDE_REFERENCE.md#arm-l-a)
- GATE-ARM-A: sealed arm G runs the gate on a rented machine from the bound commit tree as a git checkout (full text: docs/CLAUDE_REFERENCE.md#gate-arm-a)
- BACKUP-A: `tools/loop/backup_private.py` pushes all branches and tags to the private remote `backup-private` only after a visibility, URL and secret scan (full text: docs/CLAUDE_REFERENCE.md#backup-a). PUSH-TARGET GUARD exception: backup-private is a second, non-origin remote, pushes there are approved under D-612; origin stays the sole origin and is never used by it.
- SALVAGE-A: if Claude stops, usage or silence triggers save and stop every loop instance without Claude (full text: docs/CLAUDE_REFERENCE.md#salvage-a)
- STAGE-A: tools/stage_workload.py stages adapter builds for the sealer and never copies answer keys (full text: docs/CLAUDE_REFERENCE.md#stage-a)
- PREFILL-E: producer and B1 run sdpa, one-shot prefill, memory-efficient kernel pinned; other settings need a decision id (full text: docs/CLAUDE_REFERENCE.md#prefill-e)
- SEALED-RUN-A: a sealed run is prepared outside the repository, prints counts and timings only, needs the frozen tag (full text: docs/CLAUDE_REFERENCE.md#sealed-run-a)
- MULTI-ROUND-A: final mode admits multi-round Review only when declared, sealed and valid; records computed in Python (full text: docs/CLAUDE_REFERENCE.md#multi-round-a)
- VERSION-CHANGES-A: a multi-round run writes version changes in Python with no model, from declared numbered references (full text: docs/CLAUDE_REFERENCE.md#version-changes-a)
- CASE-QUESTIONS-A: two narrow model steps (toward or away, suggested wording) behind injected callables, never free-form (full text: docs/CLAUDE_REFERENCE.md#case-questions-a)
- POSITION-GAPS-A: position gaps between parties are computed from declared units or identical quotes, never read from words (full text: docs/CLAUDE_REFERENCE.md#position-gaps-a)
- NEGOTIATION-MEASURE-A: negotiation movement and round-3 wording are measured on held-out cases by plan; indicator-only until power holds (full text: docs/CLAUDE_REFERENCE.md#negotiation-measure-a)
- ASSET-COPY-A: provider-side asset copy is off unless the bundle carries an operator declaration; probed on the instance (full text: docs/CLAUDE_REFERENCE.md#asset-copy-a)
- IMAGE-A: ready-to-run image layers on the filesystem, checked by hash, bound read-only, built only when missing (full text: docs/CLAUDE_REFERENCE.md#image-a)
- FACTORS-A: every change in a figure is attributed to a recorded factor; cross-machine-type comparisons are refused (full text: docs/CLAUDE_REFERENCE.md#factors-a)

## Change discipline (full text: docs/CLAUDE_REFERENCE.md#change-discipline)

- Read-only trace before any structural change, down to where the decision is mechanical.
- Full upstream and downstream hygiene: writers, importers, string literals, paths, genesis.md, README.md, CLAUDE.md, CLAUDE_REFERENCE.md, .gitignore, the verify gate, hardcoded lists, CLI flags.
- The gate stays green and non-mutating at every commit; commit each coherent unit standalone.

## Working method and git discipline (full text: docs/CLAUDE_REFERENCE.md#working-method-and-git-discipline)

- NO PIPELINE RUNS FROM THIS MACHINE (since 2026-09-11): start none and do not ask; proofs use fixtures, mocks and saved artifacts under `output/runs/`.
- RESOURCE-ALERT-A (Seckin, 14 November 2026 15:39): any stop or wait caused by RAM or disk (a seal, launch, freeze or test held by the memory or disk floor) is an emergency, not a routine report item. The moment it happens the lead (1) sends Seckin a push notification, one line: what is blocked, free RAM and disk, what he could close or approve; (2) writes the same line, with the time, at the top of docs/loop/private/ALERT.md; (3) clears ALERT.md once the block is gone. It does not wait for the next FOR_SECKIN entry. Lanes tell the lead at once when a floor holds them.
- STANDING-ORDERS-A: the lead keeps STANDING_ORDERS.md; script-proven orders are checked at every wake, launch, merge, push and report (full text: docs/CLAUDE_REFERENCE.md#standing-orders-a)
- PUSH-TARGET GUARD: the sole origin must be `project-shimmer-deployment`; confirm before any remote operation; never push unless the operator says to push.
- Before any git operation scan the staged diff for key patterns (`sk-ant-`, `sk-proj-`/`sk-`, `AKIA`, `AIza`, values assigned to credential-named variables); on a real key STOP and alert the operator.
- Process operator job specs under `prompts/` PART BY PART, report each part, honor every STOP, do not run unattended.
- Surface conflicts between a spec and a repo convention rather than silently assuming; report your resolution.
- Prompts are self-contained; the changelog and external ledger are maintained outside Claude Code unless the spec says otherwise.
- OPEN-ITEMS: docs/fix/OPEN_ITEMS.md records what was found and consciously not fixed; written at the end of every pass, read at the start (full text: docs/CLAUDE_REFERENCE.md#open-items)
- PROGRESS-A: phases over a couple of minutes report four measured progress values through tools/ordinary_final_progress.py (full text: docs/CLAUDE_REFERENCE.md#progress-a)
- LIVE-VIEW-A: tools/ordinary_final_live.py shows an exposed cloud run call by call, with stall and alert lines; sealed gets counts only (full text: docs/CLAUDE_REFERENCE.md#live-view-a)

## The verify gate (full text: docs/CLAUDE_REFERENCE.md#the-verify-gate)

- The gate is `scripts/verify_session1.py`; its total is the length of CHECKS. Checks prove EXECUTED behavior on fixtures, never source inspection alone, and never write real `durable/`, `ontology/` or `config/`. No zero-caller or dormant scaffold counts as built: every part has a live duty or an executed gate path.

## Governed structure (full text: docs/CLAUDE_REFERENCE.md#governed-structure)

- Changes to the constitution or governed inter-agent structure need an operator-ratified DELTA; agents propose, never self-apply; the INFRA-043 meta-law tripwire holds the genesis layer.
- LAW-0 asymmetry: the guard refuses agents but never hard-blocks the operator; the signature scan is a flag, not a complete guarantee.

## Envelope, findings and review (full text: docs/CLAUDE_REFERENCE.md#the-canonical-envelope-infra-037, #review-modes, #findings-citations-and-grounding)

- One flat per-item envelope `{agent, doc_id, items[]}` (INFRA-037); anything producing a Finding record must put it on the bus; header labels use `pairing_map.header_label`.
- Phase 5.5 runs `wide` or `paired` (`pipeline.resolve_review_mode`); where arithmetic can decide, arithmetic outranks the model; bands come from reference tables, never prose.
- The verifiability gate downgrades uncited affirmative findings to UNCERTAIN; never remove or weaken it. WEB-REF is a real citation form; the empty-convention carve-out (INFRA-042) is state-gated; INFRA-044 adds five prior-comparison relations, never amendments.
- INST-SWITCH-A: SHIMMER_INST_FINDER=off is honoured only under an operator-approved amendment; otherwise the run refuses (full text: docs/CLAUDE_REFERENCE.md#inst-switch-a)
- NO-WEB-LOCAL-A: under the local profile no agent reaches the web; the one gate is SearchRouter.search (full text: docs/CLAUDE_REFERENCE.md#no-web-local-a)
- REPLIES-A: every model call writes exactly one reply record inside its backend function; saving never promotes (full text: docs/CLAUDE_REFERENCE.md#replies-a)
- RELATIONS-A: four relations (rate, carry, copy, unit mismatch) are computed in Python from declared rules, with refusals recorded (full text: docs/CLAUDE_REFERENCE.md#relations-a)
- RELATIONS-B: contradiction relation within one unit: model-written, quote-checked, marked, never promoted (full text: docs/CLAUDE_REFERENCE.md#relations-b)
- RELATIONS-C: a contradiction may span two units only from the passage pair step (full text: docs/CLAUDE_REFERENCE.md#relations-c)
- CHOICE-A: narrow questions can be decided from local model probabilities over a fixed answer set with a measured threshold (full text: docs/CLAUDE_REFERENCE.md#choice-a)
- PAIRS-A: rules declaring [compare: passages] rank sentence pairs by embedding and judge both orders (full text: docs/CLAUDE_REFERENCE.md#pairs-a)
- UNCOMPUTABLE-A: on an uncomputable plan the model answer is kept as a stamped, screened, never-promoted record (full text: docs/CLAUDE_REFERENCE.md#uncomputable-a)
- CELLS-A: rules declaring [compare: cells] take their text as a claim over Python-selected table cells (full text: docs/CLAUDE_REFERENCE.md#cells-a)
- DETECTION-DEV-A: adapters have a development detection scoring mode built in one helper; silence is never a detection (full text: docs/CLAUDE_REFERENCE.md#detection-dev-a)
- GATE-LEAKAGE-A: the leakage check is split across two sides; constants written first, counts and ids only (full text: docs/CLAUDE_REFERENCE.md#gate-leakage-a)
- GATE-SET-A: the gate set is drawn from groups the leakage check kept, whole groups, size as floor (full text: docs/CLAUDE_REFERENCE.md#gate-set-a)
- GATE-SCORE-A: gate figures use each paper's metric with paired cluster bootstrap and alpha-spending bars (full text: docs/CLAUDE_REFERENCE.md#gate-score-a)
- WRITTEN-BY-A: who wrote a finding is read off the bus post it travelled in, stamped before any copy (full text: docs/CLAUDE_REFERENCE.md#written-by-a)
- JUDGE-AGENT-A: narrow judge tasks go to the registered JUDGE agent whose contract declares them; Python runs the tools (full text: docs/CLAUDE_REFERENCE.md#judge-agent-a)
- ASSIGN-A: agents are assigned per document before dispatch from structural conditions and declared skip rules, never below the declared floor (full text: docs/CLAUDE_REFERENCE.md#assign-a)
- HONEST-OUTPUT-A: every model-written finding stays visible and marked as not promoted and not checked by Python (full text: docs/CLAUDE_REFERENCE.md#honest-output-a)
- READABLE-A: reviewed_document.md is a pure render of the document with findings quoted under their units (full text: docs/CLAUDE_REFERENCE.md#readable-a)
- INSTR-OPT-A: the instruction optimisation tooling runs one round per target on the development set, its bar committed before any round (full text: docs/CLAUDE_REFERENCE.md#instr-opt-a)
- ROUTE-S-A: bundles can be sealed on a Lambda instance as a fifth arm, returned without asset or project archives and verified from their own tree (full text: docs/CLAUDE_REFERENCE.md#route-s-a)
- NEG-ADVISOR-A: the negotiation advisor is measured on held-out public items against its own bar, development only (full text: docs/CLAUDE_REFERENCE.md#neg-advisor-a)
- DISK-SWEEP-A: tools/loop/disk_sweep.py deletes only regenerable files of the kinds declared in config/disk_sweep.json, and refuses everything else (full text: docs/CLAUDE_REFERENCE.md#disk-sweep-a)

## Task modes, amendments, sensitivity, inputs (full text: docs/CLAUDE_REFERENCE.md#document-role-resolution-and-task-modes, #writing-an-amendment, #the-sensitivity-boundary, #three-input-type-model-genesis-part-xviii)

- 4-tier role resolution picks review targets (manifest first); tasks are `review` or `draft`; a system_draft manifest is cleared at run end; `prior` names an earlier version.
- Amendments are rendered deterministically from typed Finding records, computed figures lead, no amendment is ever taken from a model; `--amendment-polish` only rewords two fields.
- Sensitivity is operator-convention-defined; no engine default floor; the masking layer is operator-activated; "applied" means verified absent by the post-apply grep gate.
- Inputs: `input/context/` learning corpus, `input/operational/` runtime-populated review targets, `input/conventions/` operator framework.

## Entry points and runtime features (full text: docs/CLAUDE_REFERENCE.md#entry-points)

- Entry points: `start_shimmer.bat`, `shimmer.bat`/`shimmer.sh`, `scripts/intake_wizard.py`, `scripts/chat.py`, `scripts/server.py` (token-gated; route table in docs/RUNTIME_REFERENCE.md), `scripts/harness/`, `tools/run_local_demo.py`, the container files.
- CONSOLE-A: console views of replies, model findings, switches and reports read tokened projections; sealed runs show counts only (full text: docs/CLAUDE_REFERENCE.md#console-a)
- CLOUD-CONSOLE-A: the console cloud mode goes only through the sealed, bound path with a typed cap and one-time code (full text: docs/CLAUDE_REFERENCE.md#cloud-console-a)
- DEMO-A: the demo is a static, request-free folder built by tools/build_demo.py from dev cases only (full text: docs/CLAUDE_REFERENCE.md#demo-a)
- DECODING-A: every local generate site decodes under the frozen evaluation policy read at call time, never typed in (full text: docs/CLAUDE_REFERENCE.md#decoding-a)
- DECODING-B: compact producer and four envelope agents decode under a per-request logits constraint; measured and adopted (full text: docs/CLAUDE_REFERENCE.md#decoding-b)
- HIDDEN-A: every operator-side child process passes creation flags through cloud_run_common.no_window (full text: docs/CLAUDE_REFERENCE.md#hidden-a)
- WAVES-A: a semantic gather above max_pending runs as consecutive waves, never refused for its size (full text: docs/CLAUDE_REFERENCE.md#waves-a)
- LEDGER-CHECK-A: loop tooling checks the request ledger, issue deferrals and finished-state claims against evidence (full text: docs/CLAUDE_REFERENCE.md#ledger-check-a)
- EXTRACTION-A: report_optimized PROCESSOR sends exactly the two validated turns checkpoint 168 was evaluated on (full text: docs/CLAUDE_REFERENCE.md#extraction-a)
- EXTRACTION-B: a cited ref is grounded by Python placement of indexed passages in spans, not by ids in text (full text: docs/CLAUDE_REFERENCE.md#extraction-b)
- EXTRACTION-C: a bounded request carries at most owned_spans_per_request (2) owned spans (full text: docs/CLAUDE_REFERENCE.md#extraction-c)
- ENVELOPE-A: a model spelling of a core key is read only when declared in core_field_aliases and recorded (full text: docs/CLAUDE_REFERENCE.md#envelope-a)
- ENVELOPE-B: the single_kind_stamp is removed; EDITOR_CLERK kind is enforced in decoding instead (full text: docs/CLAUDE_REFERENCE.md#envelope-b)
- VERIFIER-A: VERIFIER example built from the agent required list; missing drafts record not_called or partial (full text: docs/CLAUDE_REFERENCE.md#verifier-a)
- PAIRING-A: auditor pairs refuse only single-call deliveries; partial deliveries pair with ownership receipts (full text: docs/CLAUDE_REFERENCE.md#pairing-a)

## Key paths (full text: docs/CLAUDE_REFERENCE.md#key-paths)

- `config/` governance and compiled config; `scripts/` pipeline and agents; `input/` three input types; `output/runs/<id>/` per-run artifacts (never overwritten); `durable/` learned state; `ontology/stores/` cross-run store (the GNN never learns from runs).
- `benchmark/keys/` is gitignored and never opened by an agent; only the frozen scorer reads it (check 145 scans for key figures).
- `tools/` operator-facing wrappers; `corpus_ingest/` ingestion contract.

## Report Recommendations comparison path (full text: docs/CLAUDE_REFERENCE.md#report-recommendations-comparison-path)

- `report_optimized` is an explicit local topology documented in `docs/fix/REPORT_RECOMMENDATIONS_IMPLEMENTATION.md`; do not promote it on fixture measurements alone.

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
