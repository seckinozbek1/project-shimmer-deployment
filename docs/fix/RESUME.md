# RESUME

**Read this file first and continue without asking.**

## Recovery

Recovered main at 64b83e0ff6925c374c6618b4ffa90aed4645dbfd, 31 commits ahead of
origin/main (2c88112). No staged or tracked edits existed at takeover. Preserved
SHIMMER_HANDOFF.md and all untracked durable state. The untracked
tools/container_offline_probe.py belongs to the unfinished image item.
The older handoff, LEDGER and WORDS_TODO lag the code. ZERO-A and ZERO-B are
closed by 64b83e0. The previous RESUME called the image item ONE; its canonical
name in SHIMMER_HANDOFF is ZERO-C, distinct from the closed learning item ONE.

## Item just completed

ELEVEN, the commit containing this checkpoint,
`ELEVEN: give reviewers explicit harness summaries and name missing descriptions`.
Resolve its exact hash with `git log -1 --format=%H -- docs/fix/RESUME.md` until
another item updates this file. Prior TEN is 6ddea2a, NINE b5eaad0 and EIGHT
b688d26; the complete recovery and earlier local hashes are in LEDGER.

The harness generator now supplies reviewer summaries for testing_against_cluster
and fires_at_all on all 18 agents. Missing reviewer text is explicit; technical
facts remain in the developer view. Corrected the legal agent's stale description
of the existing follow-up cap. No firing policy, test coverage or dependency was
added. No gate check changed. The actual JavaScript and HTML renderer show all 36
summaries; five mutations have independently observed effects, FAIL and restored
PASS. Developer text stays identical in 35/36 rows, with only the cap correction.
shimmer:eleven passes check 195 offline and its exact UI/data pass the rendering
proof in host Node. All 122 shipped files match. Full host gate 245/247, known
01/145 only. Adversarial read done and README/image debt paid. Details in LEDGER.

## Current item

None open. Continue TWELVE after this commit: resolve the two run-id formats from
the current sources and real artifacts, preserving existing run identities.

## Ordered remaining work

1. TWELVE: one run-id format.
2. THIRTEEN: structural proof against reading-only and no-op neutralisations.
3. FOURTEEN: trace typed records through real amendment artifacts.
4. FIFTEEN: pairing fallback value and WORDS-A compliance.
5. SIXTEEN: carry the ZERO-C container evidence into a complete answer.
6. SEVENTEEN: close the cache diagnosis with measured build reuse.
7. EIGHTEEN: prove README and image debt paid, including inherited omissions.
8. NINETEEN: classify document_dates.json in the manifest.
9. TWENTY: answer the learning-signal question, no GNN build.
10. TWENTY-ONE: put the quote prediction where the next run checks it.

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

## Decisions made in the operator's place

Gathered so they can be read together. Each is one line plus its reason.

**This session:**

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

Recovered baseline: PASS=242 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=244, at 64b83e0.
Final ELEVEN host: PASS=245 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=247.
Final FOUR image: PASS=234 WARN=0 SKIP=8 FAIL/ERROR=4 TOTAL=246, plus all six
offline probe steps PASS, 163 seconds combined. Tests used --network none,
--gpus all and no mounts. Host failures: 01 (prompts/snapshots absent) and 145
(missing ignored contamination fixture). Image source-only failures: 01, 28,
31 and 145. Skips name unavailable coverage. No new unexplained failure remains.
Logs: output/eleven_host_gate.log, output/four_container_validation.log and
output/eleven_mutation_proof.log. Focused changes prove independently observable
mutation effects before fail/restore/pass. No proof mutates real source files.
ZERO-C's earlier logs and image remain preserved; see LEDGER.

Docker: C:/Users/secki/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe.
Host-access py -3.9 sees installed dependencies and cached models; the sandbox
may hide them. Do not install replacements for sandbox-only failures. Only one
GPU model workload at a time. shimmer:eleven carries the current source and
README. All 122 shipped files match (output/eleven_source_audit.json); check
195 passed in the image offline with no mounts. Its exact UI/data pass the
rendering proof in host Node. TEN's check 246 passed in shimmer:ten offline. EIGHT's
computed date-window proof passed in shimmer:eight offline with no mounts.
SEVEN's checks 174 and 218 passed in its image.
The full image gate above was run on shimmer:four; the model loader, pins and
weights remain unchanged. All older tags remain intact. Source refreshes reused
model/conversion layers.
Build cache: output/shimmer_build_cache, about 14.41 GB, ignored and local only.
Reuse it with the --cache-from/--cache-to commands in README; no global Docker
configuration change or registry upload was made.

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
