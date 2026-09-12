# RESUME

**Read this file first and continue without asking.**

## Recovery

Recovered main at 64b83e0ff6925c374c6618b4ffa90aed4645dbfd, 31 commits ahead of
origin/main (2c88112). No staged or tracked edits existed at takeover. Preserved
SHIMMER_HANDOFF.md and all untracked durable state. At takeover, the untracked
tools/container_offline_probe.py belonged to the unfinished image item; it is now
completed and tracked.
The older handoff, LEDGER and WORDS_TODO lag the code. ZERO-A and ZERO-B are
closed by 64b83e0. The previous RESUME called the image item ONE; its canonical
name in SHIMMER_HANDOFF is ZERO-C, distinct from the closed learning item ONE.

## Item just completed

BASELINE NORMALIZATION, the commit containing this checkpoint:
`Normalize unavailable baseline coverage without hiding regressions`.
Previous checkpoint 2562578. Resolve this commit with
`git log -1 --format=%H -- docs/fix/RESUME.md` until a later item updates this file.

Checks 01/145 distinguish unavailable local coverage from malformed or incomplete
present inputs. Required source directories and present local-tree structure still
fail when invalid. Nonempty digest schema, complete scan and actual contamination
assertions remain active. Fixed grouped numeric extraction, silent read/traversal
omissions, unsupported directory links and disappearing text entries.
New 254 exercises valid, absent and invalid fixtures; nine mutations change real
outcomes before 254 FAIL, then restoration recovers both outcomes and PASS.

Full host gate: PASS=253  WARN=0  SKIP=2  FAIL/ERROR=0  TOTAL=255, native exit 0.
output/baseline_host_gate.log and baseline_host_exit.json. Exactly 01/145 SKIP:
optional local directories and an absent local contamination hash fixture.
No known baseline FAIL remains. No SKIP claims successful contamination coverage.
Full image gate: PASS=243  WARN=0  SKIP=10  FAIL/ERROR=2  TOTAL=255; only unchanged 28/31 FAIL,
because the unmounted image has no intake tree. 01/145 SKIP and new 254 PASS.
output/baseline_container_gate.log. Image shimmer:baseline:
sha256:4a3321795ee3c01a91d2fe151517cce07da87b7c1818ec8beedd415cd8272a34, 14408312142 bytes. All 126 intended files match
(output/baseline_source_audit.json); all model/conversion layers reused.
Seven monitored live files unchanged (output/baseline_preservation.log).
Independent adversarial review complete; nine restoring mutation proofs PASS.
README/image debt paid. No production policy/dependency change, model generation,
pipeline run or push. This is a gate normalization, not a new review acceptance run.

## Current item

None open. The operator's requested host-baseline normalization is complete.
The first real document review remains unrun under the standing no-pipeline rule.
The ordered takeover report remains in PROTOTYPE_CHECKPOINT.md as a historical
record of 2562578; this follow-up adds one local commit, leaving 53 unpushed.

## Ordered remaining work

None. The takeover backlog and its baseline-normalization follow-up are complete.

## Current-session decisions

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
32. Record old plan counts as a forecast and check actual emitted claims:
    changed cohorts, empty answers and failed judging cannot confirm fourteen compliant claims.
33. Preserve refusal policy while making its reason accurate:
    missing quotes must not be described as a field already present.
34. Treat only declared absent local coverage as SKIP, per the operator's request:
    invalid present inputs and incomplete scans cannot establish a clean result.

## Decisions made in the operator's place

Gathered so they can be read together. Each is one line plus its reason.

**Inherited ZERO-A/B decisions (completed before takeover):**

1. **Closed the 7 unauthorising rules by making the silence visible, not by
   adding detectors.** They name content no shape detector finds, so authorising
   nothing is correct; building address/date/location detectors is a reach
   change the item did not ask for.
2. **Posted the unapplied-rule warning to the bus rather than the log.** A log
   line is not an operator-facing artifact, and this has to reach the same place
   every other redaction outcome does.

**Earlier sessions (still standing):**

3. Expanded the redaction reference set (15 to 40 positives) rather than
   dropping voters; writing reference text is work, not a ruling.
4. Rejected the minimum-margin threshold criterion; it is a worst-case measure
   one pathological case sets.
5. Made the lexical voters score CONTENT tokens, not whole sentences; both
   classes share the prohibition grammar.
6. Added style and formatting rules as negatives, after check 41 exposed their
   absence ("use formal register" scored 5 of 5).
7. Balanced the cost function once the safety veto owned the false-negative
   side.
8. Gave SBERT a veto on the NO side only (0 misses in 40 against the ensemble's
   4); a veto can only ADD redaction.
9. Set that veto at 0.09, above every style rule, accepting two unrescued weak
   true cases. **Conservative: declines to widen redaction reach.**
10. Unioned the ensemble with the regexes rather than replacing them, in TWO-K
    and E3; a missing model costs the improvement, never the baseline.
11. Deleted `_CATEGORY_KEYWORDS` rather than converting it; it fired on 0 of 44,
    was order-dependent, and still carried the "value" defect.
12. Kept `claim_classifier` and marked it unconsumed rather than deleting a
    module with a live gate check.
13. Narrowed WORDS-F to alternating-word regexes; 135 hits was useless, 21 is
    exact.

## Gate and environment

Full host gate: PASS=253  WARN=0  SKIP=2  FAIL/ERROR=0  TOTAL=255, native exit 0.
output/baseline_host_gate.log and baseline_host_exit.json. Exactly 01/145 SKIP:
optional local directories and an absent local contamination hash fixture.
No known baseline FAIL remains. No SKIP claims successful contamination coverage.
Full image gate: PASS=243  WARN=0  SKIP=10  FAIL/ERROR=2  TOTAL=255; only unchanged 28/31 FAIL,
because the unmounted image has no intake tree. 01/145 SKIP and new 254 PASS.
output/baseline_container_gate.log. Image shimmer:baseline:
sha256:4a3321795ee3c01a91d2fe151517cce07da87b7c1818ec8beedd415cd8272a34, 14408312142 bytes. All 126 intended files match
(output/baseline_source_audit.json); all model/conversion layers reused.
Seven monitored live files unchanged (output/baseline_preservation.log).
Independent adversarial review complete; nine restoring mutation proofs PASS.
README/image debt paid. No production policy/dependency change, model generation,
pipeline run or push. This is a gate normalization, not a new review acceptance run.

The latest separate offline model/ensemble probe remains the TWENTY-ONE probe
(output/twentyone_offline_probe.log). Production source and model layers did not
change in this follow-up, so that probe was not repeated or relabelled.
Docker: C:/Users/secki/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe.
Host py -3.9 has the installed pinned dependencies when run with host access.
Only one GPU workload at a time. Build cache stays in output/shimmer_build_cache.
Use direct process capture when redirecting the host gate: the initial PowerShell
redirection emitted native stderr as an error record despite the zero-failure table.
The preserved first log is output/baseline_powershell_gate.log; the final direct
capture confirms native exit 0. No check or status filter changed between runs.

## Standing terms

No pipeline run, provider/cloud model call, paid operation, or push. The operator
pushes. Preserve local history and durable state; do not reset, clean, rebase,
amend or stash it. No new dependency without a written ledger reason. Work one
item at a time and commit it before opening the next. Pay README/image debt in
its item. Every changed check needs neutralise/fail/restore/pass and an independent
changed-outcome proof; fixtures must establish their own validity. Adversarial
read before each commit. Rewrite RESUME after each completed item. No em dashes
in newly written text. Keep the ratified five-voter semantics and REFUSES cases.
Choose conservative reversible details, record reasons, and continue autonomously.

**Read this file first and continue without asking.**
