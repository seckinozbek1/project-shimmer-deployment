# Shimmer prototype checkpoint, 2026-09-13

This is the historical report for commit `2562578`, not the current resume point.
The operator subsequently pushed main through `b733188`, which normalized baseline
checks 01/145: host 253 PASS, 2 SKIP, 0 FAIL, native exit 0. The closure documentation
commit remains local. Read [RESUME.md](RESUME.md) for current state, image/probe
limits and the locked product roadmap. All old gate counts, local-only inventories
and remaining-work statements below describe the earlier checkpoint. They do not
authorize bypassing the new roadmap or its conditional VM step.

The ordered takeover backlog is complete through TWENTY-ONE. This is a source,
fixture and container checkpoint. A new end-to-end document review has not been
run: the standing no-pipeline-runs rule remains in force on this machine. Model
accuracy and general domain independence are not established by these proofs.

## Recovered state and inherited work

Recovered `main` at `64b83e0ff6925c374c6618b4ffa90aed4645dbfd`, 31 commits ahead of
`origin/main` (`2c88112`). No staged or tracked edits existed. The untracked
`SHIMMER_HANDOFF.md`, `durable/` and `tools/container_offline_probe.py` were preserved.
The probe was subsequently completed and committed. ZERO-A/B already existed in
64b83e0. ZERO-C was the earliest unfinished item; the old RESUME called it ONE,
which conflicted with the separately closed learning item. No history was rewritten.

The inherited baked image had model files but could not directly load its bge-m3
weights on the pinned runtime. Its apparent offline success hid network attempts
and runtime conversion. The sandbox also hid installed dependencies and Docker;
host access recovered the actual 242-pass, two-known-failure baseline without a
Python migration. Documentation and image claims lagged the local-only commits.

## Completed work and problems closed

| Item | Completed behavior or established finding | Local commit(s) |
|---|---|---|
| ZERO-C | Safely prepared bge-m3 safetensors during build, direct offline loading, cached snapshot resolution, refusal of custom-code overrides, attempted-network detection, three shipped synthetic fixtures and reusable local build cache. Runtime pins and model identities retained. | 963cae23 |
| FOUR | Measured 61-item extraction replies exceeded the old budget. Local PROCESSOR now has 8192 tokens; invalid drafts are withheld and auditors see extraction status. Honored the board's existing 8192 request and corrected the first scope claim. | f928fa92, c07c0b44 |
| FIVE | Saved violations were incomplete or absent JSON, not valid envelopes lost to packaging. Proved existing recovery and real payload rejection without loosening contracts. | 2ff8e237 |
| SIX | Accounted for all eight agents without saved model calls through assignments, deterministic drafting, waived redaction and absent editorial escalation. No unsupported routing change. | f772a84d |
| SEVEN | Scorers distinguish assignment, suspension and actual exposure to an assigned consumer. Raw recall stays complete; numeric document positions require unique unit identity. | 3e1fc361 |
| EIGHT | Actual date-window findings reach bus, amendments and both scorer routes, with typed reasons. Corrected the claim that the mechanism was untyped. | b688d26a |
| NINE | Actual ROWAN arithmetic reports 61 against a 20..60 band independently of the model's explanation. Retained the explanatory call as existing policy. | b5eaad06 |
| TEN | Persisted start/end/finally completion evidence separates early stop, successful finish, unsuccessful finish and unknown historical completion. Both scorers read it. | 6ddea2a7 |
| ELEVEN | Supplied 36 human reviewer summaries across both harness views, with a visible missing-description notice. Exercised the actual console renderer. | 046ba2a1 |
| TWELVE | One full UUID identity across launcher/server/pinned runs, immutable identity evidence and safe legacy recovery. Renaming no longer changes identity; recovered queue ordering uses submission time. | df27b839 |
| THIRTEEN | Executable mutation-proof protocol validates inputs, measures an independent consumer effect before consulting a check, refuses no-op mutations and verifies restoration. Coverage is explicitly bounded. | 08c00951 |
| FOURTEEN | Typed reasons survive actual synthesis and file output; both scorers read all document masters, including an empty first document. All-untyped evidence is unverifiable. Historical artifacts remain unchanged. | c014f21d |
| FIFTEEN | Retired uncalibrated fallback promotion that fell through to registry order. Unresolved applicability remains visible with no invented votes or thresholds; it cannot become a new missing-field finding. API and console expose refusal. | bdcaf01d |
| SIXTEEN | Executed the product offline with GPU exposure, distinguished real loads from stubs and unavailable corpus coverage. Fixed check 88's worker cleanup race and proved worker completion before fixture teardown. | b768481e |
| SEVENTEEN | Reconciled Dockerfile, archived logs and live build history. Model layers are reusable through the measured cache remedy; historical GC is consistent with records, not asserted as an observed event. No global Docker settings changed. | d2b22bae |
| EIGHTEEN | Audited inherited documentation/image debt. Exposed advisory withholding through actual synthesis, bus, API and both console views. Corrected a false conflict-summary claim: conflicting external additions are refused while operator conventions remain in force. | 0a6a0fe8 |
| NINETEEN | Explicitly classified document dates as usage-derived and omitted from shipping. A real build-stage shipping gate rejects populated stores; an isolated bad-image build fails while local data stays unchanged. | 5af01dba |
| TWENTY | Recommended measured candidate finding against the deterministic baseline. Narrow executable oracles are a third signal source, not general relevance truth. All 78 apparent operator verdicts were fixtures; check 107 now isolates its ledger and joins its writer. Historical rows preserved and excluded from the assessment. The ignored detailed report was explicitly tracked in a documentation follow-up. | 2b863d22, ffd8c9c1 |
| TWENTY-ONE | Recorded the 14-judged/7-computed forecast in configuration read by actual runs. Per-question audit and the real summary distinguish quotes, refusals, empty/failed/missing-consumer/partial outcomes and changed counts. Corrected misleading missing-quote refusal reasons. | 2562578 |

Each implementation checkpoint has a full host gate, focused consumer evidence,
an adversarial read and refreshed image evidence where it changes shipped files.
The final image receives a fresh complete suite. Exact evidence and earlier image
identities are retained in [LEDGER.md](LEDGER.md).

## README and image changes

README now describes actual extraction budgets and draft withholding, agent-call
accounting, scorer states, completion evidence, identity, human harness views,
typed amendment readers, fallback refusal, advisory and conflict behavior,
knowledge/date shipping, the learning objective and its limits, and the checked
quote prediction. It also corrects offline/GPU coverage and cache claims.

The image bakes directly loadable weights, resolves local snapshots first, includes
three synthetic gate fixtures, and executes the empty-shipping check during build.
The temporary patched CPU conversion dependency is build-only; runtime dependencies
remain pinned as before. Every later refresh reused the model/conversion layers.
The local exported BuildKit cache remains ignored under output; no registry upload,
Docker-wide configuration change or replacement of prior checkpoint tags occurred.
The final image includes all 126 intended source/config/fixture files. This includes
the pre-existing generated convention registry under the declared shipping contract;
operator usage stores and unshipped corpora remain omitted.

## Historical verification at 2562578

- Host gate: **252 PASS, 0 WARN, 0 SKIP, 2 known FAIL, TOTAL 254**.
  `output/twentyone_host_gate.log`. Failures: 01, missing prompts/snapshots;
  145, contamination fixture absent from the source snapshot. No new failure.
- Full final-image gate: **242 PASS, 0 WARN, 8 SKIP, 4 known FAIL, TOTAL 254**,
  134.6 seconds. `output/twentyone_container_gate.log`. Failures: 01/28/31,
  declared runtime/layout inputs absent from the unmounted image; 145, the absent
  fixture. Skips: 15/38 network, 222 host launchers, 215/217/224/227/230 unshipped
  corpora. Mixed checks name missing corpus coverage while exercising shipped proofs.
- The final image is **shimmer:twentyone**, `sha256:103f29f6f3f1c4edbfd74156edca037e2b2c9753669a1e1696ba0e41ede868cf`,
  14,408,304,202 bytes. All **126 intended files** match with CRLF-normalized
  SHA256, with no omitted or extra path: `output/twentyone_source_audit.json`.
  Every model and conversion layer was reused: `output/twentyone_build.log`.
- The separate six-step offline probe passed in **29.6 seconds**, with zero detected
  HTTP/socket/DNS attempts: `output/twentyone_offline_probe.log`. Both container runs
  used `--network none --gpus all`, no mounts. Check 193 exercises a real cached Phi
  load; 139 exercises the CUDA construction branch with model construction stubbed.
  The separate probe loads real bge-m3 and executes the declared ensemble decisions.
  None of this is a model-generation or completed-review claim.
- New 253's parsed 14/7 cohort reconciles actual bus findings and saved refusals;
  five consumer mutations change outcomes before failure, followed by restored
  outcomes and PASS: `output/twentyone_proof.log`. The summary mutation changes the
  rendered report while the underlying audit status correctly stays PASS.
- Seven monitored live artifacts remain byte-identical: five ontology stores,
  the operator-decision ledger and document dates. Snapshot and comparison evidence:
  `output/twentyone_state_hashes_before_gate.json`, `output/twentyone_preservation.log`.
- Source changes were read adversarially after gate restoration. The final tracked
  tree is committed locally; no push. The runtime/image source was frozen before
  these final verification runs; subsequent edits only closed repository reports.


## Historical remaining-work assessment and limits

No ordered development item remains open. The first real review of the final
prototype, real provider output quality, broader corpus measurements and measured
candidate-finder gain remain unverified because no pipeline run is permitted here.
At that checkpoint, the standing rule required a GPU environment for acceptance
work. The later locked roadmap in RESUME now controls when and whether VM work occurs.
No cloud/provider model generation, paid operation, push or new learning component was performed.
The operator still decides whether a learned relevance component should be built.
The seven unapplied shape rules remain visibly unapplied under the existing ruling;
this work does not widen redaction reach or add detectors.

The known fixture/layout gate failures and deliberately unshipped coverage are
listed with the final results. They are not silently reclassified as passes.
Historical completion and typed evidence are not backfilled. The 78 synthetic
operator-decision rows remain append-only history, not a human training corpus.

## Decisions made during this takeover

1. Keep Python 3.9 and the runtime pins: installed host dependencies were hidden
   by the sandbox, so migration would disguise an access problem.
2. Prepare safetensors with a temporary patched CPU reader: the same weights
   become directly loadable without unsafe runtime pickle conversion.
3. Export and import a local BuildKit cache: preserve expensive layers outside
   builder GC without changing global Docker configuration or uploading images.
4. Ship the three existing synthetic gate fixtures: their behavioral proofs must
   execute in the image without shipping corpora or held-out answer keys.
5. Keep rule-derived convention authority and mount-supplied runtime directories
   as declared by the existing shipping contract; preserve local operator state.
6. Name unavailable corpus coverage while running check 239's synthetic proofs:
   a shipping decision must not abort unrelated behavioral checks.
7. Resolve cached generation snapshots before loading and refuse custom-code
   overrides: preserve offline loading without granting new execution permission.
8. Count HTTP attempts as well as socket events: a pooled connection must not
   hide access from the verification proof.
9. Give local PROCESSOR 8192 output tokens: measured complete replies exceed
   4096; retain cloud budgets until evidence from that backend exists.
10. Withhold failed-contract drafts and label cuts for auditors: missing
    extraction is not evidence of missing source content.
11. Preserve existing envelope recovery and payload rejection: saved failures
    are incomplete or absent JSON, not valid work lost to packaging.
12. Preserve the four policies explaining eight uncalled agents: saved artifacts
    and executed predicates account for every absence without a routing change.
13. Require actual exposure to an assigned consumer for asked recall: eligibility
    and unrelated production calls cannot establish a judging opportunity.
14. Keep raw recall complete and show suspended rows separately: a deliberately
    withdrawn rule is not an ordinary false-negative mechanism failure.
15. Accept recorded numeric document positions only with unique unit identity:
    the saved logging format must work without spreading evidence across documents.
16. Honor the editorial board's existing 8192 request and correct FOUR's scope
    claim: the earlier 4096 local cap had suppressed an explicit configuration.
17. Keep ROWAN's explanation request while documenting arithmetic independence:
    the measured finding is reliable without changing the current review policy.
18. Record pipeline work completion separately from server process status: the
    two writers own different facts, and exit code 0 alone can mean an early stop.
19. Leave historical completion unknown without evidence: a new marker cannot
    retroactively establish how an older run ended.
20. Supply explicit reviewer summaries and name missing descriptions: technical
    prose is not a translation, and routing tests do not prove each agent's quality.
21. Preserve identity independently of folder labels: one UUID generator avoids
    split identities while recorded legacy IDs preserve existing artifact meaning.
22. Sort the recovered queue by submission time: random UUID spelling cannot
    encode the user's submission order.
23. Add an explicit consumer-proof protocol with bounded coverage: enforce
    execution order and reject ineffective evidence without pretending a syntax
    scan can infer every check's claim or the completeness of an observation.
24. Read every document master in the selected run: match the existing run-wide
    bus scope and avoid silently dropping amendments from later documents.
25. Report all-untyped located evidence as unverifiable: missing evidence is
    different from a key that never asked the question.
26. Retire uncalibrated fallback promotion: its adapter used registry order and
    had no WORDS-A applicability evidence; keep uncertainty visible instead.
27. Refuse unmatched-unit absence while applicability remains undecided: retiring
    fallback must not create new unsupported missing-field findings.
28. Keep the measured cache import/export remedy and existing layer order: repeat
    downloads are solved without claiming an unobserved historical GC event.
29. Describe advisory withholding and external-conflict authority as they execute:
    preserve policy, expose missing historical fields as unknown and repair misleading reports.
30. Classify document-date conclusions as usage-derived and omit them from shipping:
    operator-specific filenames strengthen the empty-shipping rule; keep local data intact.
31. Keep candidate finding subject to measured incremental value over the deterministic baseline:
    no general independent truth source is demonstrated; fixture verdicts supply no human labels.
32. Record the old plan counts as a forecast and test actual emitted claims:
    changed cohorts and empty or failed answers cannot establish fourteen compliant claims.
33. Preserve existing refusal policy while correcting its reason:
    a missing quote must not be reported as a field already present.

## Historical local-only inventory at 2562578

At the historical 2562578 checkpoint, main was 52 commits ahead of origin/main: the 31 inherited
commits below, 20 completed takeover commits already listed, and the commit
containing the original report. Nothing had been pushed at that point; the operator
later pushed all of this inventory plus b733188. The original handoff and durable
state remain intentionally untracked. Full hashes and subjects are recorded below so the
starting local work is distinguishable from the takeover work.

### Inherited local-only commits

- `2bd395f7fa1118ec90046325950892f4cd3a9c50`: A review rule reaches a judging agent, and the log says plans not calls
- `524770c8338992dd1afbcf64ac262e540908af01`: Refuse a missing_field claim that names no field, or names a present one
- `72651b42f80cd51bd6adbf9347ce4a80d2f0441a`: truncated reaches the cost row, so a cut response says it was cut
- `4afe561347ba90737813bc6678ba3db7c03f1857`: Record that the scorer credits a location, not a reason
- `139083a5e1afbdb9ffae46da8d0b9e205a301bca`: Corpus: CEDAR declared out of D02 scope, and the key corrected to the rule
- `dc6a271750e76d4e5e067cfa07a3cc395e9bddcc`: Container: rebuilt at this HEAD, offline gate proved inside it
- `ce05cbd81758ff308759c35c1b969971a1fc2a5d`: README: pin the current gate figures to the commit they were measured at
- `119bf602cfb2f331a11ef6b48e04e291ee84152c`: Scorer: check the reason, not only the location
- `015e0620c568fe8e56b5675b92a96c3fc3062344`: Quote the passage, and report a claim made identically in both twins
- `9b4f027783806ca19e98233bc6e261886c328296`: Attribution, typed amendments, a bounded deepening pass
- `b17c4bee85d68443ac5cf4679957f10375e232ea`: README: name the real commit the discipline boundary starts at
- `44e3168f4c3f724357b7fcec84c1949786f6f053`: A quote is required on an absence claim, from this commit forward
- `5496cff0a3cdc781fe7817f6b1fe725794156eeb`: Item ONE: an operator verdict joined to its subject, and read by the graph
- `61c1f34bfe5f37bf52b349256122b18dd79668f0`: Ledger: record what item ONE owes the README and the image
- `b146d82a5e6a5ce52052e1867bdd125ba723138c`: Knowledge categories, and the reset hole they expose
- `a4d86de718e7bf31bdf5d4225e6620eaa140a699`: Ledger: what the knowledge-category decision owes the README
- `f1f09cd888d0578ffa401fcdd450c0955386cc3d`: Item TWO: a rule condition points at a field AND at another rule
- `a6bd658ecdcc4ebf9ff9789ea3775f601ae0cbc8`: Ledger: item TWO debt, and the open items recorded durably
- `a499bfa68501696a6d1b3182b1050a4bde9bdc82`: TWO-A, TWO-B, TWO-C: a usable refusal, a visible loss, a suspension that suspends
- `1721eb518225a8ee68a46aa57d50495b4f2e61bb`: THREE: two rule sets, authority and information kept apart
- `d08fc175ac44b2fde110cee6f3d6e5803dca8d2e`: LEDGER: record a499bfa and 1721eb5, including what item THREE did not wire
- `9b7b25cb76024f7e2f6c93acfd87c687eaa807b7`: THREE-A/B/C and TWO-E: answers persist, a rule can enter, the limit is visible
- `45aae4d1da8e5a5b0f17f4757361ef12f1981db9`: LEDGER: SEVEN amended to three states; the suspension record is computed and discarded
- `3753314d241030ff50291aa60210cfab6b97b476`: THREE-D, TWO-F, SEVEN-A: the two rule sets meet a run, severity decides, evidence survives
- `7d07e5aaa1aaeda35551aa058e20af0fb260d1e9`: TWO-G, TWO-H, THIRTEEN-B, CHECKS-A, DEBT-A
- `2b699ea6b45e8760a6207e00de6be9ea3b25a68b`: TWO-I, TWO-J, CLASSIFIER-A: close the phrasing route, retire the severity guess
- `c7f23ee9fa35ae902902413328fcb1d7c1513cd0`: WORDS-A: the five-voter ensemble, built and measured; four voters do not separate
- `6877744c21c6f00152d5e53d0540d66c828e8e77`: TWO-K: redaction intent decided by the five-voter ensemble, unioned with the regexes
- `31744ad37c5979507c4d7c1cbc89be3887180cc5`: WORDS-B: nine fields, one verdict each; the category keyword table deleted
- `e1fbad7b49d50c137352419a66774549bd860ea6`: WORDS-D, E and F: 29 decisions inventoried, the worst converted, the shape guarded
- `64b83e0ff6925c374c6618b4ffa90aed4645dbfd`: ZERO: the active prohibition compiles, and an unapplied redaction rule is named

### Takeover commits before this final checkpoint

- `963cae235d1ef2f2e949f72133259a05a1647fe1`: ZERO-C: bake safely loadable weights and prove offline decisions
- `f928fa92eb8263fcc0ced334059a777e72bcd58c`: FOUR: preserve local extraction capacity and audit draft state
- `2ff8e23762ade7958a3e2a236e6fe425f362db13`: FIVE: prove reply packaging recovery without loosening contracts
- `f772a84d7a9c6a9eb0d381a79821a83c2571bd77`: SIX: account for every agent without a saved model call
- `3e1fc361f294b225b9d92fdc629fa8ba0b709b09`: SEVEN: score unit suspensions and actual judging exposure separately
- `c07c0b44bc40d13ce885e9c16507df5aa8a353ab`: FOUR follow-up: prove and document the board budget effect
- `b688d26a2a2b599eca470b697ca6908d8d35f6c5`: EIGHT: confirm date-window scoring through both typed artifact paths
- `b5eaad06c227583400b28df43f9fe4c55bc292d5`: NINE: measure ROWAN arithmetic and retain its explanatory call
- `6ddea2a7c48af8c59dc19e37265a595da0b62fdd`: TEN: persist pipeline completion and distinguish completed empty work
- `046ba2a13eac74fb622e1eb5bc36fbe9a73ddbb1`: ELEVEN: give reviewers explicit harness summaries and name missing descriptions
- `df27b83971f2255dfe3c5c8f1629ada933a0165c`: TWELVE: preserve one run identity across entry points and artifacts
- `08c00951df9182aa28177e97e95c5c206d28e965`: THIRTEEN: require consumer effects and restoration in mutation proofs
- `c014f21d96e527a56e61e178593ca4171f0c05ef`: FOURTEEN: retain every document in typed amendment scoring
- `bdcaf01d62b1177e679e499a769bf1450aa93f94`: FIFTEEN: refuse uncalibrated fallback pairing and preserve uncertainty
- `b768481e9725cd08f2c7690c2623bd3e17ee7afa`: SIXTEEN: verify the current image offline with GPU access
- `d2b22baede21c206c7e38cc56ccfa4764ea630dc`: SEVENTEEN: close the cache diagnosis with measured reuse
- `0a6a0fe8bbbe29e7d45a8271ea0855cf49b0417e`: EIGHTEEN: pay inherited documentation debt and expose withholding accurately
- `5af01dba543248a51a27565dcab08d9d61da68e1`: NINETEEN: classify document dates and enforce empty shipping
- `2b863d227be662e3bfadc7fca0e668a25db69573`: TWENTY: recommend measured candidate finding and isolate fixture verdicts
- `ffd8c9c117bac2bf1a1eb4ccae4823d6468fcac7`: TWENTY: retain the detailed learning-signal assessment
