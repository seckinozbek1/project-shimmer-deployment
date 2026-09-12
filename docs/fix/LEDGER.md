# Ledger: what the README must say, and what the image is behind on

## SEVEN CLOSED, 2026-09-12

SIX closed in f772a84d7a9c6a9eb0d381a79821a83c2571bd77.
The scorer already read convention_assignment.json; the handoff's claim that it
never did was stale. The remaining defect was real: every assigned rule became
asked=True, without consulting calls or per-unit suspension. The new review-state
column consumes existing pairing_map[document].suspended records and the saved
call evidence. It reports never_assigned, no_consumer, suspended, asked,
assigned_not_asked and unknown. No condition is re-evaluated and no rule's authority
changes. Suspension matches the exact unit and either the recorded registry id or
its operator-id alias. Ambiguous unit shorthand across documents stays unknown.

Decision: require recorded rule text and unit exposure to an assigned consumer
for asked recall. Assignment alone is not a call, and a production-only agent
seeing a rule is not its judge. Missing consumer metadata, including older
untagged assignments without their fallback consumer list, stays unknown. This
is a reporting limitation, not a change to untagged-rule dispatch. Existing
call_evidence.calls_exposing excludes clipped rules and clipped whole-document
payloads; the scorer also filters document and consumer identity.
Decision: preserve raw recall over every planted entry. Display suspended rows
and their count, exclude them from asked recall and false-negative mechanism
diagnosis. The withdrawal is the paired-review decision even if an earlier broad
prompt exposed the rule; a finding on that unit remains visible in raw recall.
Recorded exposure does not assert a successful response or correct reasoning.

Check 218 now executes the scorer's CLI entry point in-process over declared
artifacts and a synthetic key entirely inside a temporary directory. It no longer
creates/removes a fixed directory in the real benchmark tree. The fixture proves
its eight distinct entries, two typed findings, and one suspension of a rule
shared with an unsuspended sibling before behavioral assertions. Raw recall is
2/8, asked recall 2/4, two asked entries have no matched finding, one assigned
entry has no qualifying call, and one suspended entry is not a false-negative
mechanism failure. Missing evidence and ambiguous units remain unknown. Existing
date_window/above_band visibility and no-deliverable qualifications stay proved.

Five mutations independently change the scorer's actual output before checking:
remove the suspension reader, spread a suspension to its sibling unit, treat
assignment as exposure, count a production-only caller as a judge, and reject
the numeric document-position format in real paired-call logs. Each makes
check 218 FAIL and restoration PASS (output/seven_mutation_proof.log). Adversarial
read found the consumer-identity issue during the initial full gate, so that
in-flight gate is intermediate only; the final source requires a fresh full gate.
A shape-only replay over all 152 recorded unit-rule combinations in each saved
run initially reported every entry as uncalled. Investigation found doc_id='1'
in paired-call logs while pairing_map uses the document name. The reader now
accepts that observed numeric logging format only after uniquely resolving the
unit across documents; a numeric value that is an actual document key retains
its identity. The fixture now carries that real format, and removing the branch
changes 2/4 asked recall to 0/1 before the check FAILS. A fresh saved-artifact
replay finds 36 and 39 exposed combinations, with 116 and 113 uncalled; this is
an exposure census, not a gold-key score (output/seven_saved_shape_audit.json).
No saved run contains a suspension, so that new-state proof remains synthetic.
README now explains every state and denominator. No new dependency, pipeline run,
model generation or real answer-key read. The intermediate host gate returned
242 PASS and four failures: known 01/145, the old in-flight fixture missing the
new consumer metadata, and check 174 flagging an incidental domain-reserved word
in the new docstring. The word was replaced without relaxing the guard. Checks
174 and 218 now PASS locally and in the final image. No behavior changed for the
docstring correction. Final host gate: PASS=244 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=246,
known failures 01 and 145 only (output/seven_final_host_gate.log).
Adversarial read, README/image debt and final validation are complete.
Final shimmer:seven is sha256:4c7714a97517538a5ca385b48f977f45d49bb76a9585de25cc537f6194e4e3f4,
14,408,239,160 bytes. All 121 shipped files match after CRLF normalization
(output/seven_source_audit.json). Checks 174 and 218 PASS with --network none and
no mounts (output/seven_container_check.log). Model layers remain unchanged and
were reused. No GPU model probe repeated for this scorer-only change.

## SIX CLOSED, 2026-09-12

FIVE closed in 2ff8e23762ade7958a3e2a236e6fe425f362db13.
The two saved runs agree between cost_tracker.jsonl and call_evidence.jsonl:
29/39 calls, ten distinct called agents, the same eight uncalled agents. The
machine-readable accounting is output/six_agent_accounting.json. No answer key
was consulted. The evidence is under output/runs/2026-09-12__1doc_review and
output/runs/2026-09-12__1doc_review__479f3219, with the original terminal traces
in output/run_flawed.log and output/run_clean.log.

| Uncalled agent | Saved evidence and actual control-flow explanation | Assessment |
|---|---|---|
| STYLE_GUARDIAN | by_agent is empty; all rules tagged conformance or editorial. firing_convention_review_agents returns only PRACTICE_AUDITOR. | Correct. All rules being assigned does not mean all agents have assignments; the handoff's claim that the firing gate excluded nobody is wrong. |
| AMENDMENT_DRAFTER | Both traces say amendment_drafter_skipped reason=template_path. phase_6_synthesis defaults amendment_polish=False and renders typed findings. | Correct. Amendment work still ran deterministically. Existing check 175 exercises this consumer and writes real artifacts with no model available. |
| REDACTOR | Both traces say redaction_screening waived=1 and phase_skipped phase=9 reason=non_sensitive_mode. | Correct for these declared non-sensitive runs; not evidence of a completed privacy examination. |
| EDITOR_HEAD_OF_UNIT | The clerk's valid observations trigger neither low confidence nor out_of_mandate. The actual board loop breaks before rank_idx advances. | Correct under the ratified parsimony policy. |
| EDITOR_HEAD_OF_SECTION | The same stopped escalation chain never reaches the second senior rank. | Correct under that policy. |
| EDITOR_HEAD_OF_DEPARTMENT | The same stopped chain never reaches the first upper-family rank. | Correct under that policy. |
| EDITOR_DEPUTY_DG | The same stopped chain never reaches this rank. | Correct under that policy. |
| EDITOR_DG | The same stopped chain never reaches the final rank. | Correct under that policy. |

Both audit/editorial/BOARD_*.json files say REVIEWED, ranks_run=[EDITOR_CLERK],
rounds=0. The clerk returned four/three valid concern observations, all CONFIDENT
and without out_of_mandate. The actual _observation_triggers_escalation returns
(False, '') for both; changing only confidence to UNCERTAIN returns True.
The configured threshold is 0.7; CONFIDENT maps to 1.0 and UNCERTAIN to 0.4.
A concern verdict alone is not a summon trigger. This is a call-accounting answer,
not a finding-quality endorsement. No new policy or routing change is justified.

Decision: preserve the existing firing, synthesis, privacy and escalation policies;
the saved evidence explains all eight absences without treating them as empty
model responses. README now names each agent, cause and assessment. No code or
check changed, so there is no new neutralisation claim. Adversarial read compared
all-eight-rules-assigned with each agent's actual assignment, checked both board
states against the predicate, and distinguished privacy waiver from successful
scrubbing. The README-only image refresh reused the existing source/model layers.
Final shimmer:six: sha256:ccbb94d3e8cdbf332e8795016a7e44e29e116aa27995a6bb896eb2a54caa6111,
14,408,236,153 bytes. All 121 shipped files match the tree after CRLF normalization
(output/six_source_audit.json). The final refresh preserves the README's existing
heading hierarchy. Runtime is unchanged from FIVE/FOUR, so no model probe was
repeated for this documentation-only item. Full host gate: PASS=244 WARN=0 SKIP=0
FAIL/ERROR=2 TOTAL=246, known failures 01 and 145 only (output/six_host_gate.log).

## FIVE CLOSED, 2026-09-12

FOUR closed in f928fa92eb8263fcc0ced334059a777e72bcd58c.
Read-only replay disproves the claimed three wrapper-only failures in the second
saved run. With the configured cached producer tokenizer, LEGAL_ANALYST has
6552 characters / 2048 tokens and no balanced JSON; PROCESSOR has 7420 / 2048,
19 complete inner candidates and an unfinished envelope; SPEECH_ACT_TAGGER has
5092 / 2048, 34 complete inner candidates and an unfinished envelope. None is a
complete valid payload. output/five_saved_reply_audit.json records parser results.
The first measurement selected an uncached model id and correctly refused a
cache-only lookup; the accepted measurement reads active_producer from config.

The current parser already recovers complete envelopes from prose and fences.
Decision: retain it and its payload contract; strengthen check 148 through real
run_task with mocked dispatch. This avoids presenting invented closing syntax or
an incomplete extraction as the model's complete work. The check now proves
fences, prose plus fences, inline code, field retention, and rejection of nested
items, missing core fields, bare lists, cut envelopes and absent JSON. Fixture
validity is established before behavioral assertions. No generation or pipeline
invocation, no new dependency, and no claim to have solved future model adherence.
README now corrects the stale packaging claim. The adversarial read checked
complete versus cut envelopes and that the proof does not fabricate a wrapper.
Three mutations independently changed actual run_task outcomes: removing recovery
rejects a valid reply, removing only flatness rejection admits a nested item,
and taking the first empty candidate loses later content. Each then makes check
148 FAIL, with restoration PASS (output/five_mutation_proof.log). An initial
all-validation bypass also broke the parser's list assumptions; the accepted
mutation isolates the flatness branch instead of counting that exception.
The image refresh ships only the changed README and check, with unchanged runtime
and model layers. shimmer:five is
sha256:8bd5fe355d5c8f48a5e56907141c7627c25bbdab0b8b139ec2d65f72c0c64b84,
14,408,235,510 bytes. All 121 shipped files match the tree after CRLF normalization
(output/five_source_audit.json). Check 148 PASS in that image with --network none
and no mounts (output/five_container_check.log). An initial shell-quoted status
assertion lost its Python string quotes after printing PASS; stdin-based execution
confirmed exit 0. No GPU workload or full model probe was repeated for this
check/documentation-only change; FOUR's full image validation remains the runtime
baseline. Full host gate: PASS=244 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=246,
unchanged known failures 01 and 145 (output/five_host_gate.log). No new failure.

## FOUR CLOSED, 2026-09-12

ZERO-C closed in 963cae2. FOUR traced the PROCESSOR -> phase-5 audit dependency;
paired unit planning and arithmetic read source directly, while optional recent
bus context may still carry prior output. Both saved local PROCESSOR replies hit
2048 tokens; the preserved replies contain 21/19 complete items and 17/7 distinct
unit names, then cut mid-item. The handoff overstated their completeness.
Current complete paragraph extraction envelopes measure 6288/6081 indented tokens
(4588/4381 compact), with a largest item of 157, using the cached Qwen tokenizer.
Decision: a local PROCESSOR allowance of 8192, the next doubling of the existing
4096 backstop that fits the measured full envelope and item reserve. Other active
agent budgets and cloud budgets remain unchanged. No new dependency. This is
capacity for the measured case, not a claim that generation cannot hit a limit.
Phase 5 now names unavailable/truncated drafts and refuses to pass a parser's
best-effort object from a failed contract as though it were a usable extraction.
Budget measurement: output/four_budget_measurement_current.json. References were
deduplicated during investigation; the final measurement uses full current source
paragraphs because saved aliases repeat spans and the clean tail changed since
its saved run. No answer key was read and no model generation was run.

Check 245 now proves effect through the real production and audit functions:
a declared 5821-token response, parsed and round-tripped through the cached
tokenizer, preserves all 61 items through both auditors. Dispatch is mocked;
there is no model generation or pipeline invocation. Four mutations were proved
independently before asking the check: removing the local override and restoring
the old backstop both turn the complete extraction into a truncated failed
contract; removing the failed-draft guard forwards its best-effort object; omitting
the state update removes the audit flags. Each then makes check 245 FAIL, and
each restoration returns PASS. output/four_mutation_proof.log records the effects.
The first harness compilation needed class-method indentation dedented; this was
a proof-harness defect fixed before accepting any mutation result.
README and CLAUDE now describe the measured allowance, backend scope and explicit
audit state. Final host gate: 244 PASS, 0 WARN, 0 SKIP, 2 known failures,
246 total (01 and 145), output/four_host_gate.log. Final image gate: 234 PASS,
0 WARN, 8 SKIP, 4 known source-only failures (01, 28, 31, 145), 246 total.
All six offline probe steps passed with --network none, --gpus all and no mounts;
combined validation took 163 seconds, output/four_container_validation.log.
shimmer:four is sha256:ca369d682d718ab017187416ff3ca0d5fe5f919aebdcf2846115f9f9806da601,
14,408,233,378 bytes. All 121 shipped files match the working tree after CRLF
normalization (output/four_source_audit.json). The 7.4-second build reused the
model and conversion layers from the local cache (output/four_build.log).
Adversarial read checked backend scope, the effective outer cap, failed and
valid-partial drafts, fixture validity, the last item at both consumers, and
the source-versus-bus dependency qualification. No new failure remains.
This proves capacity and data flow with mocked dispatch, not a new review run.

## Recovery and ZERO-C, 2026-09-12

Recovered main at 64b83e0, ahead of origin/main (2c88112) by 31 commits.
Starting local-only commits, newest first: `64b83e0`, `e1fbad7`, `31744ad`, `6877744`, `c7f23ee`, `2b699ea`, `7d07e5a`, `3753314`, `45aae4d`, `9b7b25c`, `d08fc17`, `1721eb5`, `a499bfa`, `a6bd658`, `f1f09cd`, `a4d86de`, `b146d82`, `61c1f34`, `5496cff`, `44e3168`, `b17c4be`, `9b4f027`, `015e062`, `119bf60`, `ce05cbd`, `dc6a271`, `139083a`, `4afe561`, `72651b4`, `524770c`, `2bd395f`.

No staged or tracked edits. Preserved the untracked handoff, durable state, and
tools/container_offline_probe.py. ZERO-A and ZERO-B were completed in 64b83e0;
the RESUME label "ONE: image" means ZERO-C, not the already closed learning item.
The ledger and WORDS_TODO were older than the code and RESUME.

The sandbox hid user-installed Python packages, Docker and cached models. Its
gate returned 157 PASS, 1 WARN, 86 FAIL/ERROR out of 244. The same requested
Python 3.9 command with host access returned 242 PASS, 0 WARN, 0 SKIP, 2 FAIL
(01 and 145), TOTAL 244. No checks were changed to recover that baseline.
Docker is installed per user under AppData/Local/Programs/DockerDesktop.

Inherited image shimmer:baked2 (1f7c5a1c05de) was built from 64b83e0 on this day.
Build history jz2a69nwrl13bqysol1hwthx2 completed at 14:50:14 UTC. Checked source
hashes, including the untracked probe, matched the working tree. Thus the rebuild
had already happened, but offline proof and documentation were unfinished.

The cache-only container load fails because torch 2.5.1 cannot load bge-m3's
pytorch_model.bin. No model.safetensors exists in the inherited image. The old
fallback both contacts the network and calls an unsafe pickle reader directly.
Decision: prepare the same state dict as safetensors during the image build,
using torch 2.6.0 CPU with weights_only=True, and refuse conversion on older torch.
Reason: the runtime needs usable weights offline, not merely a cache directory.
The inherited six-step probe eventually PASSED, but only after network retries
and runtime conversion. Its pass did not prove the absence of attempted network
access or that the baked weights were directly loadable. The strengthened probe
checks both. Docker with --gpus all reports CUDA available and one device, so
the earlier claim that this container cannot reach a GPU is stale.
Dependency reason: torch 2.6.0 CPU is an isolated, temporary BUILD dependency for
safe conversion; it is removed in the same layer. Runtime requirements, model ids,
thresholds, references, and redaction reach are unchanged.

Rebuild expectation: add loadable bge-m3 safetensors and current source; the six
offline probe steps must pass with --network none and no mounts. Checks 139 and
193 will be executed in that environment separately from the host gate.

Build-cache evidence for SEVENTEEN: the producer download ran again for 170.4 s
on the inherited build, while the other two weight layers were cached. The
producer cache record is now absent, though its image layer exists. buildx
inspect reports a 20 GiB GC policy; buildx du reports 21.51 GB of remaining cache.
Automatic GC is consistent with these facts; no log of the historical eviction
was recovered, so the specific event is not claimed as proven.
[Docker's GC documentation](https://docs.docker.com/build/cache/garbage-collection/)
explains why no manual prune is needed for cache records to disappear.
Decision: export and reuse a local BuildKit cache under ignored output/ for the
rebuild. Reason: preserve expensive layers independently of the builder's GC
without changing global Docker settings or uploading an image. Host free disk
was 105 GB before the build; the additional cache footprint will be measured.

Check 244's focused proof passed. Neutralising the old-reader refusal changes
the outcome from no read/no file to a read and a file, then the check FAILS.
Neutralising the writer changes a usable file to no file, then the check FAILS
because the real embedding loader cannot prepare weights. Restoring each returns PASS. Both observable effects
were measured before consulting the check, satisfying THIRTEEN-B. The real
full-checkpoint conversion was subsequently proved by the build and probe.
The build has now converted the real bge-m3 state dict to 2,271,064,456 bytes of
safetensors using torch 2.6.0 CPU. The temporary installation was removed.

Adversarial read found inherited image debt: checks 238 and 239 require declared
fixtures the Dockerfile omits, while 236 skips its condition fixture. Decision:
ship those three existing synthetic fixtures by explicit COPY. Reason: execute
these behavioral proofs in the product image. No corpus, held-out answer key or
operator input is added. The subsequent source rebuild includes this correction.
The adversarial read also strengthened check 244 to exercise the real
embedding_store conversion consumer through a cache-only snapshot lookup.
Deleting that consumer call produces no file and makes the check FAIL; restore
passes. The probe's vote validator and network-attempt guard were separately
neutralised: missing scores and attempted-access-followed-by-success become
accepted, the proofs fail, and restoring each returns PASS. The focused proof
log is output/zero_c_focused_proof.log. No neutralisation changed a real source file.

The strengthened probe passed all six steps, without mounts or attempted network
access. Its corrected counts are three cached models and four configured decisions.
Checks 139 and 193 PASS inside that GPU-enabled, network-none image. The old
container limitation is closed: SIXTEEN now has measured positive evidence.
A source rebuild importing output/shimmer_build_cache reused ALL three weight
RUN layers and the conversion layer. The local cache occupies 14,411,270,809 bytes.
This solves the repeated-download cost without claiming a recovered GC event.

The first complete image gate returned 232 PASS, 8 SKIP and 5 failures of 245.
Four are deliberate source-only absences (01, 28, 31 and 145). The fifth, check
239, was a CHECK defect: after its severity proof it demanded unshipped corpora
and aborted before its other synthetic proofs. It now names that unavailable
corpus coverage and finishes the synthetic proofs; a nonempty but incomplete
corpus set still fails fixture validation. Its old source-text-only mutation
was also replaced with execution: disabling advisory withholding creates an
amendment and removes the refusal record. No product semantics changed.
The compiled convention registry was reviewed against durable_paths.py: it is
RULE-derived authority and explicitly ships as-is. It remains untouched.
Runtime directories remain mount-supplied, as the shipping contract declares.

A second adversarial image read found a deeper SIXTEEN defect: the old check 193
passed while Transformers 4.52.3 retried custom_generate/generate.py by repo id.
The library catches that failure and still loads, so successful blocked loading
was not proof of zero attempted access. Installed source and the versioned
[upstream implementation](https://github.com/huggingface/transformers/blob/v4.52.3/src/transformers/generation/utils.py)
show the file_exists request bypasses the local_files_only keyword. Decision:
resolve snapshot_download(local_files_only=True) once and pass the resulting
local directory to all tokenizer/config/model loads. Keep the configured id for
cache keys and logs. Reason: preserve the existing cached-model contract without
changing packages, models or process-global offline flags. Check 193 now counts
HTTP Session.send, connect, connect_ex and DNS attempts, including caught errors.
The first full-suite mutation produced no socket event despite a repo-id load.
Socket-only guards miss HTTP requests using an existing pooled connection; adding
the HTTP boundary makes that attempted request observable independently of pool
state. The check refused the no-op proof rather than accepting it as evidence. Its neutralisation
removes actual snapshot resolution, replacing the old forced tokenizer exception.
Check 139's two weightless model doubles stub snapshot resolution explicitly.
Resolving a Hub cache to a local path must also not grant implicit permission to
custom generation code. The helper refuses a snapshot carrying that override;
the configured checkpoints contain none. A declared, parsed Python fixture
proves refusal, and removing the guard returns the path and makes check 193 FAIL.
The real upstream custom-generation lookup independently proves the core effect:
a local directory has zero attempts, the repository id attempts access. The real
model check then passed, its resolver was neutralised and FAILED, and restoration
PASSED with zero attempts. Check 139's quantisation branch was likewise removed,
changed actual loader kwargs, FAILED and restored PASS. Logs are
output/zero_c_loader_proof.log and output/zero_c_custom_code_proof.log.
The image gate also exposed that earlier checks create an empty corpora parent.
Check 239 now tests actual corpus files, not that incidental directory: any
nonempty incomplete set fails, zero files reports absent coverage explicitly.

ZERO-C CLOSED by the commit containing this entry, subject
`ZERO-C: bake safely loadable weights and prove offline decisions`.
Final host gate: PASS=243 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=245. Only 01 and 145
remain, matching the recovered environment. Final container: PASS=233 WARN=0
SKIP=8 FAIL/ERROR=4 TOTAL=245, in 138.2 seconds with the six-step probe included, then 122.8 seconds on the final refresh.
Only 01, 28, 31 and 145 fail for the documented source-only absences; all eight
skips name network or unshipped-file coverage. Checks 139, 193, 239 and 244 PASS.
The real check 193 mutation produces one attempted HTTP access, and restoration
loads with zero attempts. The final probe also makes zero attempted accesses.
Full logs: output/zero_c_resolved_host_gate.log and
output/zero_c_resolved_container_validation.log. The tested image digest is
31ea6534411f4827e4a8035467787ae4eb2bdb605c0400627fbce8f4610d61b4.
All 121 copied files matched the tree by SHA256 after normalizing line endings.
The final README records these totals. Its refresh also recopied source whose
line endings the host gate normalized, so the final image was verified directly
again: the same 233/245 image result and all six probe steps PASS. The final
image is sha256:3593728d036a31f9fb9d76ebcca54d1126cb2aa18f762da70626f10bb1dee910. All 121 final files match the tree;
per-file hashes are recorded in output/zero_c_source_audit.json. Final image log:
output/zero_c_release_container_validation.log. Adversarial read is
complete. Next is FOUR; no other backlog implementation was opened.

No pipeline, provider model call, paid operation, reset, or push was performed.

Opened 2026-09-12. Kept because the operator moved the README pass and the image
rebuild to the end of a working run rather than before every commit (see README
section L, the discipline boundary at `9b4f027`). This is the record of what those
two deferred passes will have to catch up on, so neither has to be inferred from a
diff.

Two sections. **Owed before this run** is the backlog that already existed.
**This run** is appended to as each commit lands.

---

## Owed before this run started

Image last built at `139083a`. Seven commits have landed since. The image ships
`scripts/`, `config/`, `tools/` and `corpus_ingest/` only, so a commit touching
only `README.md` or `benchmark/` does not affect it.

| commit | what it changed | image affected |
|---|---|---|
| `dc6a271` | container figures recorded | no |
| `ce05cbd` | README figures pinned to their commit | no |
| `119bf60` | scorer checks a reason, not only a location; typed `claim` in the device key | **yes**: `tools/score_corpus.py`, `scripts/verify_session1.py` |
| `015e062` | `quote` field on the contract; twin detector | **yes**: `config/agent_contracts.json`, `scripts/paired_review.py`, `scripts/pipeline.py`, `tools/score_corpus.py`, `scripts/verify_session1.py` |
| `9b4f027` | advisory items withheld; typed amendments; deepening cap | **yes**: `scripts/agent_wrapper.py`, `scripts/paired_review.py`, `scripts/pipeline.py`, `tools/score_corpus.py`, `scripts/verify_session1.py` |
| `b17c4be` | discipline boundary named | no |
| `44e3168` | quote required on absence claims, forward only | **yes**: `scripts/paired_review.py`, `scripts/pipeline.py`, `scripts/verify_session1.py` |
| `1721eb5` | two rule sets: operator conventions vs external rules | **yes**: `scripts/external_rules.py` (new), `scripts/verify_session1.py` |
| `9b7b25c` | external answers persist; `input/external_rules/` entry point; conflict-list limit notice | **yes**: `scripts/external_rules.py`, `scripts/verify_session1.py` |
| `3753314` | severity decides; suspensions reach the pairing map; the two rule sets meet a run | **yes**: `scripts/pipeline.py`, `scripts/paired_review.py`, `scripts/verify_session1.py` |

### MODEL-A / TWO-K: the ensemble's weights, the image, and what offline now means

**Dependencies added: NONE.** The ensemble uses the embedding model the project
already ships (`BAAI/bge-m3`, via `embedding_store`'s own loader and cache), and
`sentence-transformers`, `scikit-learn`, `numpy`, `scipy` and `torch` were
already required. KeyBERT's own package is NOT installed: its algorithm is
implemented directly against the same model plus scikit-learn's vectoriser,
which is what the package wraps. So no new pip requirement, and no image size
delta from packages.

**The weights are the cost, and they are not new either.** bge-m3 is roughly
2.3 GB and is downloaded at runtime by sentence-transformers. It was already
load-bearing for semantic retrieval; what changed is that it is now reachable
from a PARSE-TIME decision.

**What offline means now, stated rather than left for later.** This is item
SIXTEEN's question and it has an answer rather than a note:

- with the weights present, the ensemble runs and redaction intent is decided by
  four triggers;
- **without them the ensemble REFUSES**, the refusal is recorded, and the three
  structural triggers decide exactly as they did before TWO-K. Redaction
  compilation does not fail and does not narrow;
- so a container that does not carry the weights is not broken. It is the
  pre-TWO-K product, which is a defensible state, and the difference is visible
  in `semantic_votes` rather than silent.

This was a deliberate construction: the ensemble is UNIONED with the regexes
rather than replacing them, so a missing model can only cost the improvement,
never the baseline. Replacing them would have made the weights a hard
requirement for a LAW-IV path in an offline container.

**Image decision:** the image does not carry the weights today and this change
does not make it necessary. Adding 2.3 GB to make an offline container reach a
fourth trigger it can already live without is the wrong trade, and it is
recorded as the operator's to revisit.

### DEBT-A, operator-facing and stated as such

**A convention that used to produce an amendment no longer does, and the
operator finds out by its absence.** That is the wording, and it is the one
change in this batch an operator meets without being told.

Specifically: a convention whose heading declares `[advisory]` now produces its
FINDING and NO AMENDMENT (`3753314`, the operator's own ruling). Before that
commit every convention produced an amendment regardless of its declared
severity, because the severity was parsed and consumed by nothing.

Why it is not merely a silent removal, and what a reader must still be told:
- the withheld amendment IS recorded, on the bus, through the existing amendment
  refusal path, carrying `finding_stands: True` and the reason.
- but the operator reading `review_findings.md` or the amendments docx sees one
  fewer amendment and no explanation there.
- **no shipped corpus is affected**: all 44 convention headings across the six
  corpora resolve to `required`, so nothing changes for any corpus today. The
  change bites the first operator who writes `[advisory]` and expects an
  amendment.

**README must say:** that `[advisory]` on a convention heading now means "report
it, propose nothing", that `[required]` and `[recommended]` are unchanged, that
an UNDECLARED severity falls back to `required` rather than being guessed
(`TWO-H`), and that an unrecognised severity is refused rather than defaulted.

**Four of the seven affect the image.** The gate total moved 228 to 234 across
them, so the container figure recorded in the README (`PASS=215 SKIP=7 FAIL=6
TOTAL=228`, measured at `139083a`) is stale by six checks and will need
remeasuring, not editing.

**README items already owed from those seven:** none. Each of the seven carried
its own README pass at the time, under the pre-`9b4f027` discipline. The boundary
starts at `9b4f027`, and `b17c4be` and `44e3168` both updated the README in the
same commit. So the backlog for the README is empty and the backlog for the image
is four commits.

---

## This run

Appended as each commit lands. Format: what the README will have to say, and
whether the image is affected.

### A prediction to be checked against a real run

The quote requirement (`44e3168`) predicts that on the next run **14 judged
absence claims** (5 on the flawed twin, 9 on the clean, from the saved pairing
maps) will either carry a quote or be refused and recorded under
`absence_refused`. The 7 computed absences are Python's own arithmetic and need
no quote.

This is a falsifiable prediction about model compliance, recorded here rather
than left in a report so the next run can be checked against it. If the model
complies, `absence_refused` stays empty and 14 findings carry quotes. If it does
not, the refused count says how often, and the refusal reason says which.

### 5496cff  Item ONE: operator verdict joined to its subject

**README will have to say:** a new durable store,
`durable/governance/operator_decisions.jsonl`, holding an operator verdict joined
to its subject; a timeout now recorded as DEFERRED rather than returned only in
memory; a sixth source, a sixth node type (`OperatorDecision`) and a sixth edge
type (`DECIDED_ON`) in the Tier-1 graph, the first edge whose source is not a
Provision and the first carrying a human judgement. Also that the tier2 literal
and the GNN node vocabulary are deliberately unchanged, and why. Gate total
moves 234 to 235.

**Image affected: YES.** `scripts/durable_paths.py`, `scripts/ontology_graph.py`,
the pipeline driver, `scripts/verify_session1.py`.

**Reasoning recorded at** `docs/fix/LEARNING_SIGNAL.md`, which the README should
point at rather than restate. Its headline for the README: the rows this
produces are not a training set (order of one DeltaProposal and zero conflicts
per run), and they are worth creating for audit and for conflict memory, not on
the argument that the GNN will learn from them.

### b146d82  Knowledge categories, and the reset hole they expose

**README will have to say:** three declared knowledge categories
(constitution-derived, rule-derived, usage-derived) with the membership test;
that `USAGE_DERIVED_PATHS` and `AUTHORITY_PATHS` in `durable_paths` are the
declared manifest and are asserted disjoint and covering; and, most importantly
for a reader, that **`--reset-snapshot` now clears `ontology/stores` as well**,
which it did not before, so the captured provisions, the Tier-1 graph and the
GNN state no longer survive a reset. That last point is a behaviour change to an
operator-facing command and belongs in the command's own documentation, not only
in a limitations note. Gate total moves 235 to 236.

**Image affected: YES.** `scripts/durable_paths.py`, `scripts/snapshot_manager.py`,
`scripts/verify_session1.py`.

**Reasoning recorded at** `docs/fix/KNOWLEDGE_CATEGORIES.md`. Its headlines for
the README: the isolation rule in concrete form (a user starts with the rules and
the constitution represented and nothing carried over from anyone's use), and the
corrected volume finding (usage-derived has the volume and lacks ground truth;
operator decisions have ground truth and lack volume; neither alone is a training
signal).

**Also records the reshaped item TWO proposal** (one relation, `[unless: <field>]`)
which is NOT yet built.

### f1f09cd  Item TWO: a rule condition points at a field AND at another rule

**README will have to say:** a third heading declaration, `[unless: <target>]`,
alongside `scope` and `requires`, with both target kinds decided from the
target's own shape; that an unrecognised declaration is now REFUSED
(`ConventionDeclarationError`) rather than absorbed as a subject tag, which is a
behaviour change an operator can hit by writing a declaration this parser does
not know; a new `unless` field on the convention registry entry; a new
`qualified_by` key in the paired payload; and a sixth graph edge type,
`QUALIFIED_BY`, the first between two Conventions. Gate total moves 236 to 237.

**Image affected: YES.** `scripts/convention_parser.py`, `scripts/paired_review.py`,
the pipeline driver, `scripts/ontology_graph.py`, `scripts/verify_session1.py`.
(`benchmark/fixtures/` is not shipped in the image.)

**Behaviour change worth calling out separately in the README:** the refusal.
Every shipped corpus was verified to still parse, but an operator's own
conventions file carrying, say, `[priority: 2]` would now stop the run where it
previously proceeded with that instruction silently reinterpreted.

---

### a499bfa  TWO-A, TWO-B, TWO-C: a usable refusal, a visible loss, a suspension that suspends

**README will have to say:** that the refusal introduced by `f1f09cd` now names
the offending declaration and LISTS the recognised ones, derived from the
parser's own regex rather than restated, and explains that `priority`,
`immutable` and `outranked_by` belong to the constitution and not to a
conventions file. An operator stopped without being told what IS allowed cannot
fix the file.

**Found while checking, and the most serious thing in this commit:** `unless`
was parsed, carried into the payload and drawn as a graph edge, and NEVER
EVALUATED. It suspended nothing at all. It now applies per unit in
`plan_calls`, so the same rule can be suspended on one entry and in force on the
next, which is what the declaration actually says. Anything that reported on the
`f1f09cd` feature before this commit was describing something inert.

**Two edges settled by registry membership rather than by shape:** a document
field literally named `conv-status` parsed as a rule condition, and is now
re-read as a field when it names no rule the registry holds; and a rule
condition naming a rule that does not exist resolves `unresolved` and NEVER
suspends, because a suspension that cannot be checked must not switch a rule off
silently.

**TWO-B:** excluding a qualified rule as a reattribution target can lose a
computed plan. That loss was counted under the generic not-judged reason, which
does not distinguish it from a rule nothing could act on. It is now named
(which rules blocked it), logged as `paired_review_reattribution_blocked`, and
carried on the not-judged entry.

**Image affected: YES.** `scripts/convention_parser.py`,
`scripts/paired_review.py`, the pipeline driver, `scripts/verify_session1.py`.
Gate total moves 236 to 237.

---

### 1721eb5  Item THREE: two rule sets, authority and information kept apart

**README will have to say:** that a second, separate rule set exists. The
operator's conventions carry AUTHORITY; a rule found outside carries only
INFORMATION. Where they do not conflict both apply; where they conflict the run
REFUSES that pair, names it and puts it to the operator, and the answer is
stored against a stable id so the same disagreement is never raised twice. An
external rule is a PROPOSAL until accepted, and acceptance records an OWNER and
is refused without one.

**This is what gives the conflict record its rows.** Item ONE joined an operator
verdict to its subject and the record had zero rows, because nothing in the
system raised a conflict. This raises them. The two were built to meet: the
answer vocabulary, the id shape and the unrecognised-answer rule are
`ontology_conflicts`' own, so one reader serves both.

**No discovery and no search, by decision.** Nothing reaches outside the
machine and no code path fetches an external rule. The only external rules in
existence are four hand-written entries in
`benchmark/fixtures/external_rules_fixture.json`, which declares itself a
fixture in its own first field and states that no real one exists. Check 238
pins that declaration, so a real rule cannot be slipped in under it.

**What counts as a conflict, deliberately narrow:** a shared declared subject
(scope plus requires, compared with the project's ONE tokeniser, so overlap is
whole-label and "Reading date" does not meet "Reading") AND a real disagreement
on severity, action, or a conditional suspension one side declares and the other
does not. Overlap plus agreement is not a conflict. Refusing more than this
would make the operator arbitrate questions nobody is asking.

**Image affected: YES.** `scripts/external_rules.py` (new),
`scripts/verify_session1.py`. Gate total moves 237 to 238.
(`benchmark/fixtures/` is not shipped in the image.)

**NOT wired into the pipeline.** The module and its gate are complete and
executed, but no pipeline phase calls `detect_external_conflicts` yet, because
there is no external rule for a real run to load. Wiring a loader that can only
ever find a fixture would be a zero-caller scaffold of the kind the gate's own
rules forbid. The decision and its reasoning are recorded here rather than left
implicit.

---

## Items still open at the end of this session

Recorded here because the working TODO does not survive the session.

**Closed this session:** ONE (both halves except the conflict rows, which travel
with THREE), TWO.

**Open, in the operator's stated order:**

- **THREE** the two rule sets: operator conventions and external rules kept
  separate, parallel application, conflict refusal put to the operator, and the
  answer stored so the same conflict is never raised twice. This is also what
  gives the conflict record its rows, so ONE is not fully closed until this is.
  Build no discovery and no search.
- **FOUR** PROCESSOR's extraction is thrown away every run. First establish
  whether paired review depends on those extractions (asked twice, never
  answered), then fix the loss.
- **FIVE** envelope-shape violations at source: strip the packaging, still refuse
  a genuinely malformed payload.
- **SIX** eight of eighteen agents never ran; say why each, and whether correct.
- **SEVEN** the scorer cannot tell not-asked from asked-and-found-nothing.
  Worsened by TWO and THREE landing, since more rules will legitimately not be
  asked.
- **SEVEN** the scorer cannot tell not-asked from asked-and-found-nothing.
  **AMENDED BY THE OPERATOR (addendum, after `1721eb5`): THREE STATES, not
  two.** A rule suspended by `unless` now produces no pair, so the scorer reads
  it as not asked when it was DELIBERATELY not asked, which is a third fact and
  the most defensible of the three. The states to distinguish when this item is
  worked:
    1. **never assigned** the rule was never paired to this unit at all
    2. **assigned but suspended for this unit** the pairing existed and a
       conditional suspension withdrew it. `plan_calls` accumulates exactly this
       (unit, rule and resolved detail) in a local `suspensions` list at
       `paired_review.py:1424` and **NEVER RETURNS IT**, so today the evidence is
       computed and thrown away. That is the same reading-not-effect shape TWO-E
       documents, in code I wrote three commits ago: the suspension changes the
       plan, which is the important half and is gated, but its RECORD reaches
       nobody. Carrying it out is the first half of this item and is cheap.
    3. **asked and found nothing** the call was made and returned no finding
  Note the asymmetry: state 2 is a CORRECT outcome and must never be scored as
  a miss, whereas state 1 may be a coverage gap worth reporting.
- **EIGHT** whether the scorer surfaces a `date_window` finding.
- **NINE** whether Python now settles ROWAN by arithmetic (the prose band reader
  landed after that run).
- **TEN** the run directory cannot distinguish not-finished from
  finished-with-nothing.
- **ELEVEN** two harness parts read technically in both views.
- **TWELVE** two run_id formats.
- **THIRTEEN** the pattern behind six wrongly-passing checks: propose something
  cheap and structural.
- **FOURTEEN** whether the typed record now survives the amendment path for a
  real run, and which artifacts a scorer reads.
- **FIFTEEN** the pairing map's similarity fallback: what it catches that an
  exact match does not.
- **SIXTEEN** two checks that cannot pass in the container (analysis only, no
  container run).
- **SEVENTEEN** the image layer ordering (diagnose from records only, no
  rebuild).
- **EIGHTEEN** the payable README and image debt as one list (this file).
- **NINETEEN** decide the category of `document_dates.json` and let the manifest
  carry the ruling.
- **TWENTY** whether the GNN can learn at all: name a third source or recommend
  keeping it as a candidate finder. Answer only.
- **TWENTY-ONE** record the quote prediction where a run checks it (the
  prediction is already in this file, under "This run"; it still needs to be
  somewhere a run reads).
