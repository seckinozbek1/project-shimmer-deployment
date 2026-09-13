# Project Shimmer, agent operating contract

This file is the operating contract for an AI coding agent (Claude Code) working in
this repository. It is terse and rule-shaped, not a tutorial (the newcomer guide is
README.md). The founding specification is [genesis.md](genesis.md), Parts I to XXVII:
read it before making any change. Shimmer is a standalone, domain-agnostic document
processing swarm governed by an append-only constitution.

## Hard rules

- No em dashes anywhere. Use commas, colons, periods, or parentheses.
- LAW-IV (privacy) is never edited. It outranks LAW-0 (operator sovereignty) for
  sensitive-content handling, with no exceptions. A single leak is irreversible.
- The constitution is append-only. The INFRA-029 amendment-guard tripwire
  (`scripts/constitution_guard.py`) intercepts any attempt to modify or delete an
  existing `amendments[]` entry or seed law from any code path; adding a new id is the
  only allowed change. No-gap rule: an amendment id is never reused, never inserted
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
- Test corpora from other domains live in `benchmark/corpora/` (real public data, outside the
  vocabulary probe's roots) and are staged with `tools/stage_corpus.py`. Run one before
  claiming domain agnosticism; the first unseen corpus found five parser defects in ten minutes.

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
  requires a new amendment to carry the next id (`prior_max + 1`, never reused, never a gap),
  be `operator_approved`, and clear the signature scan. Never bypass this path to change
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

## Document role resolution and task modes

- The 4-tier role resolution chain (`scripts/role_resolution.py`) decides which files in
  `input/context/` are under review. First match wins: tier 1 operator manifest
  (`input/context/_review_targets.json`, authoritative, never overwritten), tier 2 a
  `review_targets:` field in `review_mandate.md`, tier 3 the sidecar + date cutoff (the
  legacy mechanism, writes nothing), tier 4 a guarded content-inference STUB behind
  `--infer-roles` (off by default). With NO manifest, `_populate_operational` behaves
  exactly as the date-cutoff-only mechanism did. Preserve that backward compatibility.
- Task modes are `--task review` (default) and `--task draft`. Draft mode phase 0 generates
  a memo from `--question` with the AMENDMENT_DRAFTER (Opus) model, writes it to
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
  for saying "exceeds the typical yield range" instead of naming the figures.
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
- `scripts/chat.py`: the tkinter chat interface (Qwen NL parsing or command mode).
- `scripts/server.py`: the token-gated FastAPI dock. Config is env-driven (`SHIMMER_*`,
  read once at startup, printed to stderr); `SHIMMER_TOKEN_HASH` is required. The README's
  route table is the complete route list and gate check 167 fails if it and the app disagree
  in either direction; check 116 does the same for the `SHIMMER_*` env table.
  `/runs/{run_id}/findings` and `/runs/{run_id}/pairs` serve the STRUCTURED review (typed
  Finding records off the bus, and the pairing map with no document text);
  `/runs/{run_id}/deliverables` stays the human artifact. The pairing map's `absence` record
  and a finding's `absence_path` are on disk and on the bus but not yet in the two routes'
  projections (recorded in README section I).
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
  files, `requirements.txt`) and the three declared synthetic `benchmark/fixtures/`
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
  THREE NODE TYPES share one scope and each has its own reader: `Provision` (capture),
  `Relation` (job 2) and `Resolution` (job 3). `ontology_reader.provenance_summary` tests an
  ALLOWLIST (`node == "Provision"`, a record with no node being one), never a list of types
  to exclude: both later node types leaked into the provision count when they were added, and
  an allowlist is what stops a fourth from doing it again.
  `scripts/ontology_reader.py` is the store's only reader (`GET /ontology`,
  `/ontology/provisions/{id}`, the console's Agents page, and its own CLI inspector). It
  carries identifiers and provenance ONLY, never a provision's text.
  `scripts/relation_extract.py` finds relations between units; EVERY pattern lives in
  `config/relation_patterns.json` and none in code (S5), the embedding ranker is INJECTED
  never imported, and an ambiguous reference is REFUSED rather than resolved to one candidate.
  `scripts/ontology_conflicts.py` holds the operator's decision: a store-versus-rule
  disagreement is REFUSED in that run with both sides named, the answer is written to the
  ontology under a stable conflict id so the same conflict is never put to the operator
  twice, "keep refusing" is a real third answer, an unrecognised answer is refused rather
  than stored, and the override rate carries its own not-statistically-meaningful caveat
  inside the return value. NOTHING in a review reads a relation or a conflict today.
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
py -3.9 -X utf8 scripts/verify_session1.py        # verification gate (run every session)
py -3.9 scripts/pipeline.py --non-interactive --sensitivity-layer-inactive-override --no-redaction-override
py -3.9 scripts/pipeline.py --task draft --question "..."   # draft mode
py -3.9 scripts/pipeline.py --review-mode paired --pairs-per-unit 3   # paired review
py -3.9 -X utf8 tools/run_local_demo.py --non-interactive --sensitivity-layer-inactive-override --no-redaction-override
py -3.9 -X utf8 scripts/harness/run_agent.py --agent NAME --profile local|api \
    --unit-file U --unit-id u01 --rule-file R --rule-id CONV-001 --out results.json
py -3.9 scripts/pipeline.py --list-snapshots      # list saved snapshots
py -3.9 scripts/pipeline.py --save-snapshot NAME  # snapshot learned state
py -3.9 scripts/pipeline.py --load-snapshot NAME  # restore a snapshot
py -3.9 scripts/pipeline.py --reset-snapshot      # strip back to seed defaults
py -3.9 scripts/bus_viewer.py --follow            # live bus and cost stream
```
