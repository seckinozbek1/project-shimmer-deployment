# Multi-round positioning / decision-support implementation

Status: implementation only, 2026-09-14. No real model execution, benchmark,
inference probe, GPU workload, provider/cloud workload or remote execution was
performed. Substantive quality, runtime, GPU needs, cost, throughput and scaling
are **UNMEASURED / UNVERIFIED**. Fixture results are not semantic-quality results.

## Entry and baseline

Entered on main at `68c2c55891b31d15ad155d5c758fc0a17587707c`, the documentation-only
closure following `47c63aca09603ab5c7ad662753d647397a623ce8`. Tracked working/index
trees were clean; locally recorded origin/main was one commit behind. No fetch
was made. Operator `SHIMMER_HANDOFF.md`, `durable/`, ignored input/output and
ontology state were preserved. The user's new roadmap instruction supersedes
the older next-item wording in historical handovers.

The canonical current-version comparison baseline remains
`47c63aca09603ab5c7ad662753d647397a623ce8`. The next locked item is exactly
**Current-version cloud composite experiment**. It was not started. No push is
authorized here; the operator handles pushing the local closure commit.

## Architecture and execution contract

Read-only tracing covered the founding/working rules, README, RESUME, LEDGER,
routing audit, registry/contracts, pipeline/orchestrator, wrapper, bus/context,
reference builder, synthesis/amendment paths, run identity/completion, server,
console, privacy/ontology capture and deterministic gate/effect-proof mechanisms.

The CLI accepts `--multi-round` with `--multi-round-manifest`. The explicit case
branch runs after existing startup model/privacy gates, before date population,
adaptive spawning, ordinary Review/Draft phases and ontology capture. It creates
the existing orchestrator with `run_adaptive_spawn=False` and uses fresh PROCESSOR
and VERIFIER wrappers. Their call-specific contracts come from
`config/multi_round_contracts.json`; the fixed roster and ordinary contracts are
unchanged. This is a source-grounded case extraction/compilation task followed by
independent fidelity review, within the existing agents' capabilities. No new
agent, charter or constitutional change is introduced.

Both non-sensitive CLI declarations are required. Sensitive requests refuse
before reaching model warmup or case evidence binding. API submission requires
explicit `task=review`, `sensitive=false`, `multi_round=true` and manifest JSON;
normal upload/confirmation/authentication rules still apply. A manifest without
the opt-in is refused. The manifest is stored under the new run's audit directory,
never staged as a corpus document. The worker adds the two flags only for an
explicitly recorded request. Dense/sparse remains independently selectable.

`audit/multi_round.json` records requested, eligible, activated, phase_not_reached,
refused/unavailable and completion outcome separately. Missing ordinary-run state
is reported as not_requested/not_recorded, without creating a file. A call failure
does not erase an already recorded activation. Hard interruption can leave an
activated, incomplete phase; ordinary RunCompletion remains authoritative for
process completion. Activation is not proof of model success or coverage.

The authored candidate envelope is advisory on the existing bus while being
reviewed. VERIFIER can withhold or reject a candidate, not rewrite or invent it.
Missing decisions remain unresolved. Rejected positions withhold their dependent
movements. Accepted/refused records are then posted as flat canonical items with
producer/reviewer agent, backend, model, call identifiers, item identity/revision,
confidence and REF handles. The standard wrapper keeps constitution consultation,
call evidence, cost and activation recording. No direct generation/provider API
is added. The semantic path is implemented but has only been exercised with
pre-authored transport replies, never real models.

## Case, evidence and semantic boundaries

The version-1 manifest declares `case_id`, `fixture`, `rounds`, `actors`, `issues`
and `sources`. Each round has `round_id`, positive unique `sequence` and unique
`document_ids`. Sequence gaps are allowed and displayed. Identifiers are exact,
case-sensitive opaque values; labels never merge identities. Actors/issues may
enter or disappear at any round. One document cannot silently belong to two rounds.

Each source declares `source_id`, `round_id`, `actor_id`, `issue_id`, `document_id`,
`unit_id`, zero-based `char_start` and exclusive `char_end`, exact `quote`, and
accepted/rejected/refused or unresolved evidence state. Spans address the extracted
document text, not byte offsets in the original PDF/Word file. Runtime checks
the exact span and allocates a REF through the existing reference index. Saved
views recheck the REF's document, unit and offsets. Semantic attribution is still
an operator/model assertion; structural equality does not certify its truth.

Flat records have case/actor/issue/round identity, `record_id`, `kind`, `state`,
`confidence`, `category`, `text` and `source_ids`. Position records add a typed
`position` and optional numeric `value`/`unit`. Movement records identify previous
and current rounds and position IDs, carrying both sides' source evidence.
Non-adjacent comparisons are supported. Accepted substantive cross-round claims
must cite both named rounds. Cross-actor trajectory/decision-support records can
declare `actor_ids`; every participant needs support from both rounds.

Represented movements are concession, hardening, reversal, stable, ambiguous and
unknown. These are model-authored semantic classifications. No keyword, regex,
numeric-delta or equality heuristic assigns them. Unknown, not_comparable,
insufficient_evidence, unresolved, rejected and refused records remain visible.
Competing accepted interpretations are kept as separate records.

The projection includes ordered timelines, actor and issue histories, current
positions from the latest declared round only, movements, unresolved issues,
trajectory, decision-support observations, evidence and all original records.
Convergence/divergence and persistent disagreement can be expressed as grounded
trajectory/decision-support interpretations, not calculated from prose. Structural
comparisons carry explicit typed equality and same-unit numeric deltas with
position/movement IDs. They do not label negotiating significance.

Observed evidence, semantic interpretation, derived structural comparison and
recommendation are distinct. Recommendations require an additional explicit
manifest `allow_recommendations=true`; ordinary movement never creates advice.
No recommendation is applied to policy, sources or review amendments.

## Scope and operator surface

The case master is a run-local snapshot with an explicit case identity. Its rounds
are cross-round case data, not global knowledge. Reusing a case in a later run
requires explicitly supplying its manifest and source material again. There is
no implicit cross-run loader, durable case store, precedent promotion, convention
mutation or negotiation-to-governance transition. Existing governed startup
privacy/model decisions may still write their usual governance receipts.

The existing authenticated `GET /runs/{run_id}/multi-round` reads the master.
The console exposes the optional manifest in Advanced intake and renders saved
case sections plus existing clickable run-reference links. Ordinary detail views
do not fetch the case route. JSON is the canonical master; all histories/views
derive from it. This mode produces case decision support, not ordinary amendment
documents. Sensitive release/redaction of case outputs is deliberately unavailable.

`benchmark/fixtures/multi_round_fixture.json` contains explicitly synthetic source
spans and pre-authored producer/reviewer envelopes, including competing movement
interpretations. Its fixture declaration is checked; live mode refuses fixture
manifests. Test adapters alone use authored responses at the dispatch boundary.

## Validation and remaining limits

Run only `scripts/multi_round_no_generation_gate.py` for this item's safe subset.
It blocks generation/provider-library imports and network connections. It runs
the dedicated fixtures and a source-inspected allowlist of legacy checks; it never
calls the full gate. The ordinary pipeline is not run by these tests. Its parser
and selected route/form/worker code are exercised independently.

The pinned baseline fixture contains hashes of the baseline pipeline function
ASTs. A test removes only the named, explicit case branches and CLI options and
requires every remaining pipeline function to equal the pinned version. This
proves source isolation, not measured cloud equivalence. Ordinary defaults and
Review/Draft dense/sparse choices are separately exercised without workloads.

Adversarial proofs neutralise the saved projection and actual console renderer,
observe a changed downstream result, require failure, restore and require pass.
The no-op has NO_OBSERVED_EFFECT and is not credited as a successful mutation.
Source/binding tests also reject missing, wrong-round/actor/issue, duplicate,
non-ordered, unsupported and cross-case states. The authored transport test uses
the real AgentWrapper parser, activation audit and bus consumer, with dispatch
replaced; it creates no durable/ontology state.

HTTP transport/auth integration is **UNVERIFIED on this host**: FastAPI is absent
from the system, Python 3.9 and repository virtual environments. The HTTP fixture
is retained and reports SKIP, not PASS. The actual route handler, auth decorator,
form normalization and worker flag branch are tested without starting a server.
Node tests execute shipped console functions and subscription logic, not a browser
engine; graphical layout is UNVERIFIED. No dependency installation was performed.

The full legacy gate and image/GPU checks were NOT RUN because they include
prohibited model workloads. Historical 257 PASS / 4 SKIP host and 249 PASS /
10 SKIP / 2 known missing-input image failures remain historical, not fresh
results. No image rebuild/parity, fresh-clone readiness or cloud-quality claim
is made. Detailed final safe-subset counts are recorded in RESUME and LEDGER.

## Credential-scan closure follow-up

The pre-commit scan initially stopped at `scripts/verify_session1.py:16060`
(original line). After explicit operator authorization, source/AST inspection
proved that this was a test-local credential inside `_w8_console_body`, used
only to set an expected test hash and authenticate in-process TestClient calls.
The fixture restores its environment. No provider credential was loaded, found
or displayed. The fixed test value was replaced with a fresh value from Python's
`secrets.token_urlsafe` generator.

The complete rerun found three equivalent legacy test-local fixed values, one
subprocess-output expression, and one JavaScript block-comment description.
All were verified without displaying values. The other fixed fixtures now also
generate fresh values; the expression's local variable was renamed, and the
comment was rephrased. No runtime authentication behavior, secret-scanner rule,
credential exemption, or ordinary pipeline contract was changed. Assignment-only
execution proves distinct generated values and compatible hash construction for
all four fixtures; no FastAPI server or pipeline was started.

The final full-file scan covers all 17 intended commit files, with no unresolved
flags. Staged-file verification is repeated before the local commit. Location-only
proof is saved in `output/multi_round_implementation/credential_flag_review.json`.
No real credential required rotation. HTTP fixture integration remains skipped
for the previously recorded missing dependency; that check is not claimed passed.
