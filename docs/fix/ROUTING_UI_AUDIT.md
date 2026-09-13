# README, upstream/downstream routing and UI audit

Audit date: 2026-09-13. Entry commit:
`13144755a7493713060c76256352657c3f5cc1d1`.

## Decision and scope

Current documentation now describes the implemented path from intake to evidence
and output. The console adds a small recorded-activity summary and a developer
drill-down, qualifies successful process exit, labels current-registry rule text,
and warns that Local Draft is unsupported. The only new service behavior is a
read-only, authenticated activation/completion projection. No review routing,
model, prompt, generation budget, suppression policy, constitution, governance
decision or performance optimization changes are accepted.

The [README architecture map](../../README.md#end-to-end-architecture) is the one
current end-to-end map. Its [all-18-agent routing table](../../README.md#all-18-agents-actual-tasks-profiles-and-downstream-consumers)
joins actual tasks, both model/backend profiles, eligibility/activation keys,
repeat bounds, outputs and downstream consumers. This report supplies the deeper
entry/artifact tables and contradiction record instead of duplicating that table.
The [runbook](../RUNBOOK.md) covers the operator flow and recovery limits.

Entry checks used the staged-secret scanner before git status, log and rev-list.
The closure commit was present; the tracked tree was clean. Existing untracked
`SHIMMER_HANDOFF.md` and `durable/` were preserved. Local `origin/main...HEAD`
reported `0 0`; this differs from the preceding audit's handover. No fetch or push
was performed here, and the local ref is not evidence of who changed the remote.

Prior activation decisions stay closed: dense/reference default, all 18 agents
inventoried, no accepted new suppression rule, no sparse promotion. No heavy
benchmark was needed: saved evidence and isolated consumer fixtures establish
the routing/UI claims. Gate model loading is separate from a quality benchmark.
No provider/cloud call, private-document run, VM, machine setting change or
fresh-clone test was used.

## Entry-point routing

| Entry point / intended user | Source -> authoritative parser -> normalized representation | Validation / governance refusal | Backend / privacy / task | Final runtime and consumer |
|---|---|---|---|---|
| Windows desktop, ordinary operator | `start_shimmer.bat` -> `desktop_launcher` / `preflight.startup_report` / `startup_settings` -> validated launch settings and owned server | Package/cache/posture checks; server readiness failure remains visible, no synthetic model review | Startup Local/Cloud; subsequent explicit Normal/Sensitive and Review/Draft in console | `desktop_server` -> server -> `_run_job` -> pipeline subprocess |
| Browser ordinary intake | `renderSubmit` form -> authenticated `server.submit` -> normalized task/privacy, target/prior filename arrays and staging manifest | Explicit task/privacy/confirmation; upload limits; `standalone_intake` classification; conflicting files, invalid roles and governed convention changes refused | Backend is server-wide; Local defaults paired, Cloud wide; Sensitive unavailable with inactive shipped layer | `_standalone_plan`, worker `_place_standalone`, exclusive file placement -> pipeline roles |
| Native API caller | Multipart `intake_mode=standalone`, `confirmed=true`, literal privacy and JSON filename arrays -> same submit parser | Server validates independently of UI; worker revalidates placement at start | Same backend/privacy/task path; no per-job backend or activation-profile field | Same single worker and subprocess, no alternate review engine |
| Legacy/integrated API caller | Omitted intake mode or prepared bundle -> ingestion validator plus `_corpus_ingest.json` -> ingested context/staging | Existing sidecar validation; legacy task/privacy defaults differ from native explicit requirements | `SHIMMER_MODE` selects pipeline intent, not native parser; env backend, task defaults, optional wide/paired | Legacy placement/cleanup -> pipeline; broad native ownership guarantees do not apply |
| Raw CLI/developer | `pipeline._build_arg_parser` -> argparse flags and effective objectives | Confirmation, privacy/model/constitution gates and optional file operator channel; noninteractive does not invent approval | Explicit backend/review/activation/task/override flags; dense default; Draft direct Claude memo | `pipeline.main` with tracked completion and `RunContext`; no server status.json |
| Local diagnostic runner | `tools/run_local_demo.py` -> wrapper parser/forwarded CLI args -> same pipeline module | Same governance; no automatic privacy waiver; resource sampling is observation | Defaults Local; explicit options forwarded | In-process pipeline, isolated output option when requested |
| Legacy terminal launchers | `shimmer.bat` / `shimmer.sh` -> setup/preflight and command selection | Can install dependencies and perform legacy preflight; not a passive daily starter | Legacy CLI path, existing configuration | Same scripts; retained as advanced/historical setup, not contradictory recommended startup |
| Single-agent developer harness | `scripts/harness/run_agent.py` -> selected unit/rule/agent | Contract/governance under the harness; not full-run intake/coverage proof | Chosen agent/configuration | One test task, not an automatic subject-cluster evaluation or production run |
| Container entry point | `tools/entrypoint.sh` -> serve/run/verify command | Mount/config/model prerequisites; missing operator tree is not filled with fixtures | Named image configuration; `run` uses local demo runner | Same server/pipeline/gate; no complete container review measured here |

Upstream trace: `role_resolution` resolves explicit `_review_targets.json`,
mandate targets, then sidecar/date-cutoff roles; inference remains a guarded stub.
`review_scope` and `document_dating` record undated exclusions. Explicit targets
can override dating; prior versions remain grounding and ambiguous target/prior
overlaps do not silently compare. `_populate_operational` applies roles and
integrated promotion exclusion. Native task objectives become review phase
payloads through `_effective_run_objectives`; editorial builds its own objectives.

BOOT creates the run context/identity/completion marker, compiles conventions and
writes assignment before document work. Subject tags are structural exact matches;
scope/requires/unless and severity remain distinct. Five-voter semantic decisions
handle the governed language/shape questions they actually own; older deterministic
label/relevance heuristics also remain. External-rule proposal loading and answered
structural conflicts are real, but `_applicable` external proposals are not merged
into the compiled registry. Configuration paths, parser flags and startup settings
have different consumers; a UI choice is not evidence of every downstream effect.

## Agent routing and bus effect

The README table is traced against `pipeline._LOCAL_PROFILE and _resolve_local_models` (the explicit
profile map in pipeline source), `config/agent_registry.json`, production/audit
lists, `_paired_judging_agent`, `_convention_review_firing_agents`,
`_deepen_legal_analyst_findings_local`, `_polish_findings`,
`phase_6_5_editorial_review`, and `sensitivity_layer.redaction_stage.run_redaction_phase`.
The resolver applies `config/local_models.json` prequantized producer/auditor IDs over the fallback map; the Local table is checked against that executed resolver. Names in configuration describe the shipped selection, not current provider
availability. No live provider lookup is needed or authorized for this trace.

Corpus ARCHIVIST, INST_FINDER and CITATION_RESOLVER run over a bounded corpus digest
before per-document PROCESSOR, SPEECH_ACT_TAGGER and LEGAL_ANALYST. ARCHIVIST's
inventory explicitly reaches legal and wide practice work. The two audit-oriented
corpus agents lack a named final-document reader, but their accepted bus records
enter `bus_reader.assemble_context`. That context includes canonical latest item
revisions, recent messages and traffic counts under a budget. The preceding
activation audit's executed bus ablation proves this path can change a later
consumer prompt; it was preserved, not rerun or relabeled as quality evidence.

The accepted PROCESSOR projection reaches VERIFIER/FACT_CHECKER with the source
and explicit draft availability/truncation metadata. A malformed draft is withheld,
not converted to an empty clean finding. Local LEGAL may deepen up to six first-pass
findings, serially; empty/capped pass one explains the prior six-call reduction.
That is bounded additional work, not a new suppression policy or failure retry.

Paired conventions combine deterministic comparisons and semantic questions.
Unmatched consumer, unresolved applicability, supported computed absence and
no-model-work plans are separate non-call reasons. Untagged rules select the
existing first/default consumer; rules are not reclassified semantically to save
calls. Numeric records can post `backend=paired`, `model=python`; model wording is
not the authority for arithmetic. Known field matching misses remain limitations.

Synthesis uses typed findings, records amendment refusals and renders the master.
Optional polish can change only explanation/proposed text, not IDs, figures or
citations. Fresh amendment bus payload can bypass polish. Draft phase 0 instead
uses one direct free-text Claude call, bypassing `run_task`'s envelope and context
path; Local's producer remap does not make that callable as a Local memo.

The editorial board is advisory. Readable master/privacy eligibility precede the
clerk; lower confidence than the configured threshold or enabled out-of-mandate
summons the next rank up to the configured cap. Concern alone is not that trigger.
Unknown/nonempty confidence's existing fallback is not a measured confidence
score. The board does not rewrite the master or govern release. Phase 9 is reached
after phase 7 and before phase 8; actual REDACTOR calls additionally require the
active layer, no waiver, compiled rules and readable master. HELD_WARNING continues
with a warning; BLOCKED produces nonzero exit. No privacy guarantee is inferred.

`agent_activation` owns observability, not policy. A request may fail before
dispatch; `actual_call` marks an attempted wrapper dispatch, not successful token
generation. Contract failures post distinct events and raw audit evidence, with
no automatic contract retry. Provider transport backoff, later documents, legal
deepening and editorial climbs are different mechanisms. Recovery/capping remain
visible even for accepted output. A phase never reached has unknown eligibility.

## Artifact routing

All run paths below are relative to the run folder unless prefixed otherwise.
“Can be absent” means inspect the named evidence; it is never permission to infer
zero work or quality. Run-local artifacts are retained output, not durable learning.

| Artifact | Producer -> real consumer | Runtime effect / scope and persistence | UI / operator exposure | Absence meaning |
|---|---|---|---|---|
| `logs/agent_bus.jsonl` | wrapper, orchestrator and computed findings -> bus_reader, synthesis, audits, server finding/refusal views, scorer | Append-only run-local messages; canonical latest revisions feed later tasks | Findings, failures, refusals; raw log for developers | No accepted finding is not no attempted work; failures and non-calls require other evidence |
| `logs/cost_tracker.jsonl`, `cost_tracker.json` | call accounting -> aggregate cost/report/scorer diagnostics | Run-local generation/cost events; aggregate derived | Developer files, progress/model-call projection | Not a reliable substitute for activation dispatch counts |
| `logs/call_evidence.jsonl` | wrapper/pairing call boundary -> evidence classifier/scorer | Run-local structural call evidence; not a prompt archive | Developer diagnostics and expected-defect evidence API | Missing or incomplete join can leave review state unknown |
| `audit/pairing_map.json` | paired/wide review -> planner diagnostics, server pairs/documents, scorer | Run-local planned/computed/judged/refused work; informs execution and saved coverage | Partial API projection; full file contains absence/bands/prior detail | Phase may not have run; empty UI cannot certify all rules checked |
| `audit/convention_assignment.json` | BOOT assignment -> firing gates and registry excerpts, server/scorer | Run-local assignment, actual routing input | Subject/rule allocation; current-registry idle summary is a separate projection | Old run or unreached BOOT; not zero agent activity |
| `audit/agent_activation.json` | actual phase gates + observed wrapper/direct dispatch -> `routing_view`, authenticated activation route, console | Run-local observation only; not a model prompt or suppression dependency | Compact summary; developer agent/reason/re-fire details | Missing, malformed or wrong identity explicitly unavailable; no zero fabrication |
| `audit/reference_index.json` | deterministic reference-index builder and web additions -> agent excerpts, REF validation/renderers, references API | Run-local reference source; not CITATION_RESOLVER's graph | REF click resolves excerpt; WEB-REF currently not clickable in console | Index absent versus unknown ID distinct; no current/global fallback |
| `audit/undated_documents.json` | dating/role preparation -> server undated view | Run-local exclusion audit | Undated/excluded/reviewed-anyway lists | Older/missing file can project empty lists; roles/cutoff still need inspection |
| Accepted verification items and contract dumps | VERIFIER/FACT_CHECKER/wrapper -> synthesis, reports, bus consumers and scorer | Run-local findings; malformed items withheld, dumps audit-only | Findings/contract-failure section; raw audit evidence | No usable verification output is not an affirmative check |
| Editorial observations / board audit | editorial loop -> next rank, advisory annotations and audit | Run-local; affects escalation, does not replace master or release gate | Deliverable commentary and developer evidence | Waiver, privacy restriction, missing master, failed lower rank or no escalation |
| `deliverables/<doc>/review_data.json` | synthesis / allowed polish / redaction -> renderers, server amendments and scorer | Run-local canonical amendment master | Amendment view and downloaded master | No qualifying amendment, refusal, failed phase or no document; not clean coverage |
| `review_findings.md`, `tracked_changes.docx` | amendment_render from master -> operator/download | Run-local pure renders, not independent semantic decisions | Readable amendments / tracked-change DOCX | Rendering may not have completed; “done” folder is only file presence |
| `grounding_summary.md`, `document_summary.md`, `reviewed_document.md` | pipeline report writers -> operator | Run-local summaries/per-agent content; not a complete coverage certificate | Downloaded document folder | Phase/document may be absent or incomplete |
| `memo.md` | Draft generation, preservation copy -> review input and final operator file | Run-local saved memo; temporary source can be cleaned | Draft download | Review task, unsupported Local Draft or failed generation |
| `audit/audit_synthesis.md`, `delta_proposals.json` | phase 7 AuditSynthesizer -> orch.escalate_delta_proposals, governed operator evaluation and existing durable-learning controls | Run-local audit/proposals; proposals do not auto-amend constitution or rules | Files and review summary | Phase not reached or no proposal; not evidence that governance was changed |
| `audit/absence_quote_prediction.json` | absence evidence prediction -> later scorer comparison | Run-local audit forecast, not routing policy | Developer/scorer evidence | No forecast/usable comparison; no measured quote-recall claim |
| `audit/pending_approval.json`, `approval_decision.json` | governed operator channel / approval endpoint -> pipeline polling and governance evaluator | Run-local handshake with possible governed persistent decision | Pending question; records answer, never asserts approval effect | No pending question or already consumed/answered; inspect status |
| `audit/run_identity.json`, `run_completion.json` | RunContext / tracked entry and explicit reached-end mark -> server discovery, scorer, new activation projection | Run-local identity; completion independent from process exit | Identity/recorded completion | Old/malformed/no-start marker; hard kill can leave running, not completed |
| `status.json`, `logs/pipeline_stdout.log` | server worker/persisted job and subprocess capture -> restart recovery, run resource/log route | Run-local server state, not direct CLI output contract | Process state, stop reason, log | CLI run or child not started; lost staging is not resumable generation |
| `deliverables/_run_summary.md` | final pipeline index after end-work -> operator/archive | Run-local index, can exist without server pairing-based document list | Whole-run ZIP/files | Final index not reached; partial files may still exist |
| `ontology/stores/` provision/revision store | best-effort end capture -> ontology reader/API, graph builder | Cross-run persistent state; sensitivity handling keyed to layer state | Provenance/revisions and relations | No captured entries is not no reviewed content; capture failure is nonfatal |
| Ontology graph / GNN weights/state/candidates | graph build and structural fit -> maintenance/candidate API | Persistent structural model, no learned relevance and no review-agent inbound route | Agents/ontology developer surfaces with qualifications | No graph/model or insufficient nodes; not a failed review-quality score |
| Ontology conflict answers | answer API -> store/summary and callable apply_resolutions utility | Persistent answer; production review does not call this feedback path | Recorded/refused/override summaries | Unanswered versus answered-refuse distinct; no automatic next-run effect claimed |
| `durable/` and protected governance categories | orchestrator/memory/governance -> precedents, caches and controlled decisions | Cross-run; reset categories exclude protected global/governance state | Mostly files and governed questions | Not erased by deleting a run; never treat as disposable audit output |

## Contradictions found and disposition

The previous README and runbook are preserved verbatim with explicit historical
banners. Their section names below identify the stale claim clusters without
turning thousands of historical lines into current instructions.

| ID / old location | Contradiction with traced consumer | Disposition |
|---|---|---|
| D1 README G/H and runbook startup | Multiple setup/legacy start paths read as the normal entry; later desktop starter owns environment selection, loopback/auth and child lifecycle | Current README/runbook lead with desktop; legacy paths clearly advanced |
| D2 README C, harness shared receive/hand/constitution | Uniform structured-call claims ignore Draft's direct free-text Claude memo before review | Document bypass and Local Draft unsupported; narrow harness wording; no routing redesign |
| D3 README agent prose and registry notes | Capability declarations are broader than actual downstream consumers; audit-only can be misread as no effect | Actual all-18 runtime table; shared bus effect explicit; registry capabilities/policy unchanged |
| D4 harness re-fire prose | “No agent ever asked again after failure”/zero re-fire conflates contract retry, per-document work, transport backoff and bounded follow-ups | Correct builder descriptions and regenerate harness; preserve actual limits |
| D5 README F/J/K phase-9 wording | “Phase no longer executes” obscures reached phase versus actual REDACTOR call and inactive layer/waiver/rules/master gates | Correct phase order, eligibility and NONE/APPLIED/BLOCKED/HELD_WARNING/SKIPPED distinction |
| D6 README J/K benchmarks | “No run scored since” and all later work unmeasured contradict saved September 13 quality/activation evidence; old time/recall numbers remain interspersed | Current qualified baseline table; archive historical cloud/device/catalogue/negotiation results without deleting evidence |
| D7 README ontology, harness ontology, API docs | Write-only/unbuilt-store claims conflict with real API readers; other prose promises next-run conflict consumption absent from production review | Distinguish human/API readers/end capture from missing agent feedback; structural GNN only; correct server answer docstring |
| D8 README I / old runbook routes | Retired status/queue/results/approval aliases and legacy sidecar examples obscure native intake | One exact live route table; native parser distinguished from pipeline mode and legacy defaults |
| D9 README/rule route description | Current registry said not to vary per run even though it can regenerate | Current-registry label in UI/docs; historical rule reconstruction remains debt |
| D10 runbook persistence/reset/backup | “Regenerable”/backup scope can imply operator input, outputs or all config are covered; deleting run conflates learned state | Explicit state table and exact backup coverage; preserve old restore procedure as historical evidence |
| D11 README container/gate sections | Numerous historical totals/images and source-only failures read as current; local laptop prohibition was superseded only for separately authorized audits | Current closure record points to this report; historical numbers archived; no machine remedy/deployment work authorized here |
| D12 founding/working design versus implementation | Governance design names capabilities and broad architecture not all implemented as runtime paths | Preserve governed texts unchanged; README distinguishes founding intent from measured wiring |

| UI/backend ID | Actual disagreement or gap | Decision |
|---|---|---|
| U1 Success label | “Finished, no problems” and “nothing checked/nothing to download” on an empty pairing-based document list overstate process outcome | “Process finished”; explicit coverage/completion qualification in both views |
| U2 Hidden activation | Existing assignment idle lists cannot establish calls, failures or phase-not-reached eligibility | Add read-only `/runs/{run_id}/activation`, compact ordinary summary and optional developer details |
| U3 Citation history | Rule click resolves current global registry, whereas REF click resolves saved run index | Label rule source; exercise both links; no fake historical snapshot |
| U4 Draft choice | Local badge plus Draft option can imply supported local memo generation | Add visible Cloud-required/Local-unsupported hint; keep architecture change out of scope |
| U5 Archive/completion | Server document done is any file; ZIP includes root index and partial folders despite narrower docstring | Correct docs/docstring; no inferred privacy release or complete-coverage guarantee |
| U6 API projection gaps | Pair view omits full absence/band/prior details; finding projection omits some typed metadata; WEB-REF not clickable | Record on-disk inspection path and unresolved UI debt, no false completeness claim |
| U7 Historical console audit | Old audit claims findings/pairs only fetched on successful runs | Historical banner notes actual nonqueued fetch path; preserve original causal evidence |

## Changes, rejected changes and debt

Changed: current README and runbook; labeled original archives and historical
API/UI design files; harness builder descriptions and generated harness; server
documentation plus one protected read-only endpoint; `routing_view`; small console
labels/activity section; executable API, JavaScript and documentation checks
registered as checks 259/260 where appropriate. No new framework or runtime Node
dependency. The main map and tables are consolidated, not copied into every report.

Rejected: inferring skipped agents from missing artifacts; claiming new sparse
savings; altering agent eligibility/model policy to match prose; replacing semantic
judgment with deterministic relevance; treating recovered JSON as quality;
automatically enabling privacy; suppressing known image failures; a large default
debug panel; new historical rule-snapshot storage; Local Draft redesign; ontology
feedback implementation; new performance measurements. These exceed this item's
truth/alignment scope or lack evidence.

Remaining debt: historical rule snapshots/current-ID ambiguity; WEB-REF navigation;
full absence/band/prior metadata in API views; per-run persisted backend; robust
coverage presentation for old/missing audit files; archive release/completeness
semantics; Local Draft; inactive Sensitive layer; semantic/grounding/reason quality;
label/scoped absence limitations; ontology/GNN agent feedback and relevance;
individual agent cluster quality tests; a graphical browser/layout acceptance pass.
The executed Node tests exercise shipped functions and their consumers, not a
browser engine or visual layout. Existing older section anchors move into the
historical README; old deep links may need the archive rather than the current guide.

Fresh-clone prerequisites/debt, **not tested**: Python/dependency/CUDA compatibility,
actual cache weights (including prepared bge-m3 safetensors), required input
directories, explicit native versus sidecar intake, local credential configuration
for Cloud, generated harness/compiled registry ownership, ignored state/evidence,
Windows starter availability, image/tag/cache preparation and mount boundaries.
Do not infer an empty source checkout has this installation's operator state or
caches. No packaging/distribution change is made to force clone/image tests green.

## Verification and closure

Adversarial read identified the important non-equivalences: activation versus
dispatch/generation, unreached phase versus ineligible, empty pairing projection
versus no files, current rule text versus historical source, and process success
versus coverage/privacy. The read-only reader rejects malformed, mismatched and
inconsistent activation records; it does not repair missing evidence into success.

| Verification | Result and evidence boundary |
|---|---|
| Focused API fixture | PASS. Real ActivationAudit/RunCompletion writers -> protected HTTP route; 401/404, missing/malformed/wrong-run/inconsistent aggregates, actual failure/non-call/unknown states and pre-dispatch failure. The route's reader is neutralized: changed HTTP output, failed check, restore/pass; no-op refused as NO_OBSERVED_EFFECT. |
| Executable console fixture | PASS. Node executes shipped JavaScript functions and actual detail-render subscription with real API fixture responses. Proves stale navigation/DOM replacement rejection, unavailable evidence, ordinary/developer separation, failures/caps, actual server status projection and recorded completion states. Real run REF HTTP response reaches the click panel; missing ID is visible. Rule click labels current registry; actual submit render warns about Local Draft. Renderer/subscription neutralizations fail and restore; no-op refused. Node is a host test runner only. |
| Documentation checks | PASS. Exact all-18 roster; registry Cloud models and Local IDs through the executed actual resolver; CLI dense default; RunContext filenames; isolated regenerated harness equality. Existing checks 116/167 match documented env names and all actual routes. No giant prose snapshot. |
| Initial host gate | 257 PASS / 0 WARN / 4 SKIP / 0 FAIL, TOTAL 261; native exit 0. |
| Final host gate | **257 PASS / 0 WARN / 4 SKIP / 0 FAIL, TOTAL 261; native exit 0.** Final runtime and expanded fixture code. The later README-only intake-name/DELTA-label corrections passed focused documentation checks and the final image gate; runtime source did not change. |
| Final local image | `shimmer:routing-ui`, **`sha256:50502ba700a1d288f113007269bd9e9a620288f39b53e9a091954672a9224c35`**, 14,409,962,003 bytes. Offline source overlay on verified `shimmer:activation`; cached dependency/weight layers, no pull/download/provider use. Rebuild required because server/UI/harness/test source ships. A final README-only refresh took cached layers; initial image evidence was retained separately. |
| Complete source parity | **142/142 expected source paths and normalized SHA-256 hashes match**, no missing/extra path or mismatch. CRLF normalized to LF explicitly; no raw-byte/EOL identity claim. Final closure rechecks every hash against the working tree. |
| Final unmounted image gate | **249 PASS / 0 WARN / 10 SKIP / 2 FAIL, TOTAL 261; native exit 1**, 135.0s. `--network none`, `--gpus all`, no mounts, no pull. New checks 259/260 pass. The two failures remain **28 input/ missing** and **31 input/context/ missing**, not converted to passes. Initial image gate had the same counts and failures. |
| Preservation/hygiene | All 275 baseline/operator snapshot files and 54 diagnostic, 8 quality, 46 speed and 243 activation manifest entries remain unchanged. Original README/runbook text matches the historical archives (line endings normalized). Staged location-only credential scan and whitespace check pass. No operator input/state cleanup, no prior evidence mutation. |

Host skips: 01 optional local directory coverage, 15 live search, 38 cold embedding
download, 145 missing ignored contamination fixture. Image adds 215/217/224/227/230
for intentionally unshipped corpora and 222 for unshipped legacy host launchers.
Other mixed synthetic/corpus checks retain their own limits. These results are
not a clean contamination certificate, an all-green image result, a fresh-clone
test, a graphical browser test or an end-to-end container/private-document review.

Evidence is retained under ignored `output/routing_ui/`: focused logs and response
fixtures, initial/final host/image logs and native exits, source inventory, original
text preservation and prior evidence preservation, plus the sealed manifest.
Source/API fixture checks make no provider or generation calls; full gates load
cached assets under offline controls. Host and image model-loading workloads were
serialized. No heavy quality/performance benchmark was run for this item.


The authorized local commit will be reported in the final handback; a commit
cannot contain its own final hash. Nothing was pushed. The next locked item is
exactly **FinOps + VM/GPU feasibility analysis** and was not started. The canonical
roadmap remains unchanged.
