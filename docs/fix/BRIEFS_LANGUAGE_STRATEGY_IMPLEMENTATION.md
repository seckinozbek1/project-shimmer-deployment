# Agent briefs, run languages and strategic support, 2026-09-14

Implemented against `6b92ed3b17c9ae7123a72a474d8267724a11839e`, with deterministic
validation only. No real generation, GPU workload, provider call, remote execution,
cloud provisioning, multi-round workload or optimized benchmark occurred. No push.
Next locked item: **Optimized current-version cloud composite experiment**.
The historical canonical roadmap is unchanged.

## Entry and preserved work

Entry was clean on main at 6b92ed3, matching locally recorded origin/main. Status,
branch, twelve commits and tracking state were inspected without fetching. Existing
operator `SHIMMER_HANDOFF.md`, `durable/` and prior cloud evidence were preserved.
No scheduler, model worker, model selection, generation limit or governance rule
was changed. Reference and DAG modes remain available; multi-round stays separately
opted in and inactive by default. The DAG's existing multi-round/Draft exclusions
remain in place, not silently relaxed by this work.

The A100 evidence remains the cold 1,958-second, 20-call result recorded at 804afa5.
The existing quality anomalies and unmeasured warm/composite performance are not
fixed by these source changes. This is a new prompt-policy version, not evidence
that the baseline semantics or runtime have improved.

## Track A: execution briefs

`scripts/agent_briefs.py` declares current interfaces for all 18 registered agents.
Responsibilities and exclusions are read from the actual registry, and output
requirements from the current call contract. They are not copied into a second
policy table. Consumer identities also expose the existing activation audit's
consumer contract. Editorial interface order is checked against the pipeline's
rank tuple. Unknown extension agents receive only a generic calling-subsystem
interface; no invented adjacent agent or routing edge is asserted.

The existing stable role block contains identity, DOES, DOES NOT, directives and
the output schema. The compact brief adds supplied upstream artifacts, produced
artifact, downstream consumers, non-duplication boundaries, evidence, uncertainty
and refusal expectations. Ordinary Review calls, the legacy prompt template and
the free-text Draft path all receive the policy. Draft explicitly retains its
free-text output contract instead of being instructed to return an agent envelope.

Adjacent awareness is interface-aware and conclusion-independent: an agent name
does not imply artifact availability, correctness or factual authority. The brief
requires independent evidence checking within the agent's responsibility, preserves
competing interpretations, and does not duplicate adjacent deliverables. It does
not remove independent verification or editorial rank authority. Briefs add no bus
post, activation decision, scheduler edge or automatic follow-up.

Brief text measures 784-945 characters per registered agent; the default language
instruction adds 531 characters. Existing role/schema blocks are not repeated in
the brief. Existing local final reminders and token budgets remain unchanged.
These character counts are a prompt-bloat audit, not token/prefill measurements.

`--agent-briefs enabled|disabled` defaults to enabled. The disabled control permits
a later brief comparison while holding the language policy constant. It does not
restore byte-identical historical prompts: language instructions and the approved
static/dynamic boundary relocation are separate changes.

## Static and dynamic prompt boundaries

The stable prefix contains role/contract, brief, run language policy and constitution.
Current convention subsets, references, bus context, objectives, document/unit and
work payload remain dynamic. The full work payload still occurs once. The Draft
builder now places retrieved passages beside the dynamic question, preserving
their text and REF identifiers. No evidence was removed or shortened.

Each call records `logs/prompt_structure.jsonl`: call ID, agent, brief version and
setting, input/output language, static/dynamic character counts and SHA-256 of the
actual static prefix. No raw prompt, source passage or credential is copied there.
Cache-hit state is null; prefix identity is not a measured cache benefit. Existing
provider caching remains optional, with no new provider-specific dependency.
Writes are synchronized only during append and failure is reported without
preventing the semantic call, consistent with existing call-evidence bookkeeping.

The existing reference AST checks retain their pinned baseline. They explicitly
account for only the new CLI/configuration hooks and Draft prompt relocation;
the scheduler and other pipeline bodies remain protected. Passing these checks
does not claim old and new prompts are identical.

## Track B: language contract

Run options are immutable and scoped to the run, not environment globals or agent
names. CLI, `/submit`, persisted job/status fields and worker argv use the same
validation. `audit/run_options.json` persists schema version 1.

| Option | Contract |
| --- | --- |
| `input_language` | `auto` by default; explicit `en` and `tr` also accepted. |
| `output_language` | `en` by default, or `tr`. |
| `agent_briefs` | `enabled` by default, or `disabled`. |

Input `auto` means the model receives the original multilingual material without
a forced language classification. There is no keyword detector. Mixed input is
allowed. Output Auto is intentionally not offered or accepted: the operator picks
English or Turkish. Missing values receive the documented defaults; explicit
empty/invalid values refuse, and missing historical option files use English
display defaults. Malformed saved option files are not silently accepted.

Public explanations, narratives and requested advisory options are instructed in
the selected language. Original quotations, identifiers, field names, enums,
numbers, units and provenance remain unchanged. Nothing controls or exposes
hidden chain-of-thought. This is output behavior, not internal-reasoning telemetry.

The console adds a compact **Output language / Çıktı dili** selector and repeats
the selected language in its confirmation plan. Case-layer labels, movement labels
and acceptance/availability labels have English/Turkish projections. For example,
`concession` stays the machine value while the Turkish label is `Taviz`.

The canonical amendment Markdown writer selects Turkish headings and renders the
same master, including public explanations, original text and evidence references.
Supplemental structured fields remain visible with unchanged machine names and
values. The English render retains its existing path. JSON is never translated.
Source backticks cannot escape newly rendered fenced data, and the case HTML/UI
escapes authored text. Existing DOCX generation and legacy console chrome retain
their structural English headings; generated prose receives the run instruction.
This is not a claim of complete UI/DOCX internationalization or automatic translation
of historical outputs.

## Track C: strategic recommendation layer

The case manifest adds optional `decision_support_mode`:

| Mode | Behavior |
| --- | --- |
| `trajectory_only` | Default; no strategy call or recommendation. |
| `decision_support` | Existing supported case analysis and structural comparisons, without prescriptive strategy calls. |
| `strategic_options` | Explicit advisory proposal plus independent review; no recommendation type allowed. |
| `recommendation` | Explicit options/recommendations plus independent review; also requires `allow_recommendations: true`. |

The trajectory producer contract now keeps prescriptive advice in the separate
phase. Legacy saved recommendation categories remain readable in the legacy view;
they are not promoted into the new provenance-validated layer.

`strategic_support.py` validates a separate `strategic_layer` (schema version 1)
within the case record. The authenticated saved-case API exposes it as an additive
`strategic_support` projection. Evidence and the original case view remain available
if the strategic layer is malformed. Trajectory records are persisted before
strategy work; optional strategy failure cannot erase them. Unavailable advice
does not claim that independent review occurred.

Display nodes separate:

- `OBSERVED`: source-bound quotations, with original source state and references.
- `INTERPRETED`: proposed/accepted case interpretations, including semantic movement
  and trajectory narratives, with state and uncertainty. An author's observation
  label alone does not turn a paraphrase into source evidence.
- `DERIVED`: existing typed structural comparisons, not invented strategic meaning.
- `STRATEGIC_OPTION`: an explicitly requested advisory action and its tradeoffs.
- `RECOMMENDATION`: advice linked to accepted options and their provenance.

Semantic trajectory text remains an interpretation with a trajectory stage; it is
not relabeled as a deterministic derivation. Arithmetic never decides which
strategic action to take. Zero, one or multiple defensible options are supported.
Unavailable and insufficient-evidence states coexist with intact trajectory output.
Rejected/unresolved proposals remain visible with their states rather than being
silently promoted or dropped.

An option/recommendation carries `record_id`, `type`, `state`, `confidence`, `action`,
`upside`, `risk`, `assumptions`, `uncertainty`, `actor_ids`, `issue_ids`, `round_ids`,
`source_ids`, `interpretation_ids`, `trajectory_ids` and `option_ids`. Reviewed
records add case/ref bindings and producer/reviewer agent, backend, model and call
IDs. Stable values are shared by both display languages.

Validation requires accepted source and interpretation/trajectory links, complete
supporting source sets, exact actor/issue/round scope, consistent REF bindings,
distinct identities and independent PROCESSOR/VERIFIER provenance. Recommendations
must link accepted options and retain their sources, assumptions and uncertainty.
A rejected option withholds its recommendation. Missing review never promotes a
proposal. Competing interpretations and uncertainty cannot be erased by a later
CONFIDENT label. Structural validation is not proof of substantive strategic merit.

The optional execution path uses fresh existing wrappers and separate contracts,
never direct model/provider APIs. It requires the existing explicit case and
privacy gates. Only authored fake wrappers exercised it here. No real strategy
generation or multi-round execution occurred.

## Validation and adversarial findings

The combined command is
`python scripts/brief_language_strategy_no_generation_gate.py`.
It blocks provider/model imports and sockets, replaces credential loading with an
empty fixture loader, executes authored tests, then runs the topology and previous
safe gates. The full suite contains prohibited model/GPU workloads and was not run.

Coverage includes all briefs and registry boundaries, editorial interfaces,
conclusion independence, static/dynamic evidence preservation, reference/DAG
prompt construction, prefix metadata, configuration defaults/refusals, both
cross-language directions, mixed input, Turkish institutional phrasing, citation
and numeric stability, saved API projection and worker argv. Strategy tests cover
all five layers, missing provenance, competing/single options, failed review,
uncertainty, insufficient evidence, malformed strategy with valid trajectory, and
English/Turkish rendering. Node executes the shipped console function offline.
Neutralise/fail/restore tests cover brief insertion, provenance enforcement and
UI escaping; existing scheduler and multi-round no-op proofs still run.

Adversarial fixes included: dynamic placement of per-call rule subsets and Draft
references; Draft language wiring; strategy errors isolated from trajectory data;
rejected options withholding recommendations; uncertainty/provenance preservation;
source/claim type separation; explicit unavailable review state; and preserving the
console's original mixed line endings to avoid unrelated churn. No new shared
model state or semantic sequencing dependency was introduced. Localization copies
display values without mutating the canonical source graph or amendment master.

Real contract/quality impact, output-length impact, recovery rate, latency, prefix
cache benefit, Turkish semantic quality and multi-round recommendation quality are
all **UNVERIFIED / UNMEASURED**. No runtime or substantive improvement is claimed.
The next benchmark must distinguish source version, topology, brief setting,
language policy and workload, rather than attribute all changes to concurrency.


## Closure validation and changed files

Final combined gate: **73 PASS / 2 SKIP / 0 FAIL** (24 capability tests,
23 topology tests, 17 multi-round tests and 9 safe legacy checks). The two skips
are unavailable FastAPI and optional local prompts/snapshots coverage. Python
syntax checks covered 104 modules. All 325 prior A100 evidence files match the
recorded SHA-256 manifest. Serial reference and DAG modes remain available;
multi-round remains inactive by default. No provider, model, GPU, cloud, remote
or real multi-round workload ran. No resource was provisioned and nothing pushed.

Changed implementation files:
- `scripts/agent_briefs.py`, `scripts/run_options.py`, `scripts/strategic_support.py`
- `scripts/agent_wrapper.py`, `scripts/bus_reader.py`, `scripts/pipeline.py`
- `scripts/amendment_render.py`, `scripts/server.py`, `scripts/ui/console.html`
- `scripts/multi_round.py`, `scripts/multi_round_phase.py`
- `config/multi_round_contracts.json`, `config/strategic_support_contracts.json`

Changed validation files:
- `scripts/brief_language_strategy_checks.py`
- `scripts/brief_language_strategy_no_generation_gate.py`
- `scripts/ui/brief_language_strategy_checks.js`
- `scripts/execution_topology_checks.py`, `scripts/multi_round_checks.py`
- `benchmark/fixtures/brief_language_strategy.json`

Changed documentation: `README.md`, `docs/api/RUN_LANGUAGE_AND_STRATEGY.md`,
`docs/fix/RESUME.md`, `docs/fix/LEDGER.md`, and this report.
Operator-owned untracked `SHIMMER_HANDOFF.md` and `durable/` are preserved.
The next locked item is **Optimized current-version cloud composite experiment**;
it has not begun.


## Localization completion, 2026-09-14

Starting commit: `2a84becd825163487842476b8807a269b73078bf`.
Turkish mode is now intended to provide complete user-facing localization across
the supported current console, report, DOCX and CLI presentation surfaces.

**Invariant:** In Turkish output mode, no user-facing English structural/chrome
text should remain unless it is intentionally preserved source content, a
canonical identifier, or an untranslated proper name/technical token that must
remain exact.

The shared catalog in `scripts/ui/localization_catalog.js` is consumed by the
Python presentation helper and the browser helper. Translation occurs at display
boundaries, before source values are interpolated. No heavyweight framework or
new API route is introduced. English is the default and unknown exact technical
diagnostics retain their original text.

Completed surfaces:
- Console navigation, buttons, submission controls and confirmation text;
  health, progress, phase/governance states, warnings, validation, known errors,
  refusals, empty/unavailable states, agent/harness descriptions and downloads.
- Review/findings/amendment, case/multi-round, trajectory, strategic-support and
  recommendation labels, including enum-to-display projections.
- Context, operative, prior-comparison, audit, absence-prediction, per-agent and
  run-summary report structure; amendment Markdown headings and owned comments.
- DOCX headings, explanatory/comment labels, uncertainty captions and reference
  ledger structure. Persisted output language reaches the actual DOCX writer.
- CLI help and known operator prompts, summaries, errors and completion messages.

Intentionally exact content: original/quoted source passages, operator-authored
text, filenames, proper/model names, agent/rule/evidence IDs, provenance, numeric
values, canonical JSON fields and enum values, raw structured evidence and original
diagnostic logs/tracebacks. Commands, flags and required approval response tokens
remain exact. Native operating-system file dialogs and Word application chrome
are outside Shimmer's renderer; the console's file-selection button is localized.
Existing saved source/model prose is not retrospectively translated. Actual
model-generated Turkish prose quality remains **UNVERIFIED** without generation.

The audit also corrected corrupted Turkish selector characters, late-bound
language rendering and DOCX language propagation. Switching the submission form's
language preserves user input and file roles; reopening a run uses its saved
language, with English fallback for older runs. Computed amendment commentary is
translated only for display; its canonical record is unchanged.

Validation: `python scripts/localization_no_generation_gate.py` exited 0:
**94 PASS / 2 SKIP / 0 FAIL** (21 localization, 24 briefs/language/strategy,
23 topology, 17 multi-round and 9 safe legacy checks). The localization suite
includes 16 assertions against the actual console functions in offline Node and
actual generated DOCX ZIP/XML checks. Known legacy English headings are rejected
in targeted Turkish fixtures; source quotations, IDs, canonical enums, HTML
escaping, English output/fallback, locale isolation, persisted options, CLI errors
and help are checked. Fail-and-restore probes prove the localization assertions
detect neutralized translations. Syntax checks cover 107 Python modules. The
two skips remain unavailable FastAPI and optional local prompts/snapshots coverage.

All 325 prior A100 evidence files match their recorded SHA-256 manifest.
No model generation, GPU, provider/cloud workload, remote execution, provisioning
or real multi-round execution occurred. Serial/reference and DAG modes remain
available; multi-round remains inactive by default. Nothing was pushed.
Operator-owned `SHIMMER_HANDOFF.md` and `durable/` are preserved.

The next locked item remains **Optimized current-version cloud composite experiment**.
It has not started.
