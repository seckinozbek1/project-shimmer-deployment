# Final Auditor pairing contract

`FINAL_MODELS_INTEGRATED_TELEMETRY_READY`

Continuation of `093afce`, implementing the operator's explicit advisory-pair
architecture decision. No training, cloud compute, real model workload, protected
data, multi-round or performance benchmark was executed. Readiness here means
the ordinary integration and deterministic validation pass, not measured quality
or speed improvement.

## Contract

Auditor896 is a **pair-level four-way classifier**. VERIFIER remains the rich
finding generator. The two record layers are separate. Classification is advisory:
VERIFIER may agree, disagree, return multiple findings, return none, or refuse.
There is no classifier/VERIFIER equality gate and no label broadcast to findings.

Each schema1 pair binds run_id, document_id, producer_agent, producer_item_id,
producer_revision, source_span_id/source_unit_id/source_ref_ids and source_hash.
`pair_id` is `auditor-pair-` plus the SHA-256 of that canonical identity. It is
deterministic from owned identities, not generated prose or a paragraph guess.
The record also retains the original producer_call_id, ownership mechanism,
Producer168 adapter identity, Auditor896 adapter identity, classifier_call_id,
classifier_status and auditor_relation. It does not manufacture confidence,
reasoning, severity or evidence. Classifier confidence/logits are unavailable
because the prepared predictor exposes a class label, not calibrated confidence.

Two structural ownership mechanisms are admitted:

* Successful compact hydration stamps a **runtime-owned** `source_ownership`
  receipt outside the model envelope. It binds item/revision, a hash of the
  Producer semantic fields, exact ledger span IDs, and the original call ID.
  Partition merging retains these receipts. Pairing re-resolves the exact span
  IDs in the current document ledger and excludes stale revisions/content.
* A structured Producer `ref_ids` entry or canonical single `ref` can bind a nonempty operational excerpt
  in the existing ReferenceIndex for the same document. Each explicit reference
  produces its own pair. Foreign-document refs, unknown refs and prose mentions
  grant no ownership. `document-level` placeholders and paragraph numbers are not fallback links;
  a single `ref` must match an existing index ID exactly.

An item with two explicit units produces two independent inputs and decisions.
No units are merged into one input. A compact owned span can have no REF ID:
its existing span ID/hash still establishes ownership; no reference is invented.
If there is no current explicit binding, record `AUDITOR_PAIR_UNAVAILABLE` and
continue existing VERIFIER behavior. Incomplete/failed/unknown-completeness
Producer delivery is not classified. Older revisions, changed content under an
old receipt, or conflicting content under one item/revision are excluded.

## Source-level data flow

1. `compact_contracts.bind_producer` preserves the actual owned Span objects on
   the wrapper. The existing hydration validator still establishes complete
   coverage and runtime IDs. After a successful response,
   `auditor_pairs.stamp_ownership` stamps sidecar receipts.
2. `bounded_extraction.merge` carries receipts and their physical Producer call
   IDs through the existing partition merge without altering typed items.
3. `pipeline.phase_5_audit` attaches the original Producer result, current source
   document and ReferenceIndex entries to the **VERIFIER wrapper only**. The
   original VERIFIER/FACT_CHECKER payload construction remains otherwise intact.
4. Within the active ordinary VERIFIER request, after its existing constitution
   check and before context assembly, `auditor_pairs.prepare_context` constructs
   current pairs, invokes the frozen classifier once per pair, persists receipts,
   and adds `auditor_pair_context` to the work payload.
5. `auditor_pairs.predict` uses `final_models.classifier_messages`, including the
   existing reference normalization and native chat serialization. Each input has
   one source span and that one Producer item's semantic content. Hydrated
   `draft_text` is not misrepresented as Producer-authored output: that field is
   mechanically copied original text, so the classifier receives the actual
   extracted claims/questions/uncertainty/status. Reference-path authored
   draft_text is retained when present. No semantic paraphrase is synthesized.
6. `final_models.resident('auditor', ...)` loads the exact896 adapter/head/mean/std
   with the pinned base/runtime and existing numerical admission. Context overflow
   fails the pair without truncation; load, shape or finite failures produce an
   explicit failed-pair receipt. There is no base-classifier fallback. The resident
   predictor retains its sticky numerical-stop behavior.
7. VERIFIER receives the pair record, exact owned source evidence and corresponding
   Producer semantic item as structured context. It uses its existing generative
   backend and contract. Its base/generative model identity is distinct from the
   final896 classifier identity in telemetry.
8. `auditor_pairs.compare` records explicit finding joins after the unchanged
   parsing/bus path. It never mutates parsed findings, acceptance or refusal.

The task filter is exact: final mode, local_auditor backend, VERIFIER, ordinary
`verify_draft_against_source`, and a pipeline-supplied request. No FACT_CHECKER,
convention, style, editorial, strategic, computed-finding or multi-round path is
redirected. Existing conditional activation and dense/reference operation remain.

## Multiple findings, empty output and failures

A finding is comparable only if it explicitly names an existing pair ID, or
supplies matching Producer item/revision and source-span/reference identity.
Contradictory identity fields do not establish a direct pair-ID join. Ambiguous
joins remain null. Missing optional source refs in the existing finding contract
do not become a new refusal. A shared paragraph, matching text, matching class,
or document-level proximity never establishes a join.

Pair and finding records are persisted separately. The join receipt records
`agree`, `disagree` or `not_comparable`; disagreement does not declare either
model wrong and does not change governance. A classifier prediction does not
create any finding when VERIFIER returns empty or refuses. Classifier failure or
unavailable ownership still permits the original VERIFIER call. Live-wrapper
fixtures compare base and final behavior for empty/refused output under missing
pairing and classifier failure.

## Telemetry and critical path

The existing `logs/model_telemetry.jsonl` now includes:

| Event | Evidence |
| --- | --- |
| `auditor_pair` | Stable identity, model provenance, status, relation, call link, forward-attempt state |
| `auditor_pair_unavailable` | Item/revision and explicit coverage reason |
| `auditor_pair_coverage` | Considered/eligible Producer items, constructed pairs, unavailable items and failures |
| `model_call` for AUDITOR896 | Separate service interval, parent Producer call, pair/task/wave IDs, token count where known |
| `auditor_pair_barrier` | Pair preparation interval and the classifier calls consumed by VERIFIER |
| `auditor_verifier_join` | Separate finding IDs/relations, null or explicit pair joins, agreement, empty/refusal state |

Raw events contain identities/counts, not source prose. The model's actual work
payload carries the source and extraction content. Resource activity counts now
include pair invocations. Attempted classifier calls and confirmed forward attempts
are distinct: a model-load failure is not claimed as a completed forward; unknown
counts remain marked unknown in synthetic/injected implementations.

`model_telemetry.summarize` now derives pair coverage, relation distribution,
classifier service, failures, joined/unjoined findings and agreement/disagreement.
Parent call IDs measure Producer-to-Auditor and Auditor-to-VERIFIER handoffs. A
reused wrapper rebuilds its parent list from the current Producer request, so a
previous request's classifier IDs do not leak into the next dependency chain.

Scheduler tasks retain the full VERIFIER transaction interval, including pair
calls. Separate backend service intervals avoid counting that nested classifier
work twice as model service. The summary includes per-wave start/end and explicit
downstream phase consumer barriers with required task IDs and the interval since
the latest required Auditor completion. Lane serialization edges and prior-phase
dependencies remain visible. Critical-path service and gaps remain separate;
overlap is handled with interval unions, not sums of parallel agent durations.

The observed DAG measures actual scheduling dependencies. Completion-to-consumer
gaps are not automatically labeled avoidable waiting, and a role's path service is
not a counterfactual speedup estimate. CPU operations outside scheduled tasks are
not individually attributed to a model. Reference-serial runs without scheduler
evidence still report that DAG unavailable; handoff/call/pair evidence is present.
These precision limits are explicit and are not a reason to defer the ordinary
instrumented run or invent measurements.

## Startup and frozen artifacts

`SHIMMER_MODEL_MODE=final` no longer trips the old generic blocker. Ordinary Review
startup verifies both frozen artifact sets, the pinned runtime and an executable
pair-contract self-check covering valid ownership, missing ownership, stale
revision and non-guessed finding joins. A failed self-check or invalid runtime
still refuses. The Producer loader remains selectable and fail-closed. No frozen
hyperparameter, checkpoint, base identity, trained weight or normalization was
changed. Full identities remain in `config/final_models.json` and the integration
report. Startup fixtures mock the runtime check; they do not load a real model.

## Validation and effect proofs

The focused gate executes the existing compact Producer/VERIFIER contracts,
topology, report/recommendation and ordinary activation suites, plus the new pair
fixtures. External connections and model/provider imports are blocked; Windows
asyncio's local wakeup socketpair is permitted. It does not chain into multi-round.
The current exact test count and result are saved in
`final_model_integration/validation.json` and `no_generation_tests.log`.

Fixtures cover one MATCH, one OMISSION, independent relations across two items,
two explicit units for one item, multiple/different findings, explicit and missing
joins, absent ownership, missing optional refs, empty/refused responses, numerical
failure, incomplete delivery, stale revisions, valid startup, wrong/mixed artifacts
and invalid runtime. A live AgentWrapper fixture proves that classifier context
actually reaches the backend while multiple differing findings remain unchanged.
Another fixture proves compact sidecars survive hydration and partition merging.
Serial/parallel timing fixtures cover handoffs, waves and consumer barriers.

Seven neutralize/fail/restore/pass proofs pass: frozen checkpoint identity;
overlap accounting; pairing-dependent startup admission; source ownership;
stale-revision exclusion; no guessed ownership; and no one-label-to-many-findings
broadcast. Mutants create an observable wrong behavior: fake ownership,
stale-item admission or relabelled findings. Restoring the real implementation
restores a passing check. The existing activation proof suite also rejects no-op
neutralization. Historical function AST hashes are preserved after removing only
the explicitly named additive telemetry/pair-request adapters; no review baseline
was silently replaced.

## Non-blocking limitations and next action

**Auditor896 external macro F1 remains about 0.8010; historical macro F1 about 0.4576;
historical OMISSION recall remains 1/12.** No quality improvement is claimed. Pair
coverage depends on explicit ownership; some reference-mode Producer items may
legitimately have no pair. Many VERIFIER findings will have no structural pair
join under the unchanged optional-field contract. The future run will measure
these coverage rates. The typed ordinary inputs and advisory influence have not
been benchmarked against a new labeled evaluation, and no latency improvement is
claimed. Non-streaming TTFT, calibrated confidence and unexposed counters remain
unavailable.

The former pairing blocker is closed. Stop after the local commit. The next stage,
only after separate authorization, is the instrumented ordinary pre-multi-round
full cloud run. No push or cloud launch is part of this task.
