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

SIX, the commit containing this checkpoint,
`SIX: account for every agent without a saved model call`.
Resolve its exact hash with `git log -1 --format=%H -- docs/fix/RESUME.md` until
another item updates this file. Earlier completed items: FIVE in
2ff8e23762ade7958a3e2a236e6fe425f362db13, FOUR in
f928fa92eb8263fcc0ced334059a777e72bcd58c, ZERO-C in
963cae235d1ef2f2e949f72133259a05a1647fe1.

Both saved runs account for all eight uncalled agents: STYLE_GUARDIAN has no
assigned rule; AMENDMENT_DRAFTER used template synthesis; REDACTOR was waived in
non-sensitive mode; five senior editors were never summoned. Both boards stopped
at the clerk after confident concern observations without out_of_mandate. The
real escalation predicate returns false, an uncertain variant returns true.
README and LEDGER name all eight and why that is correct under existing policy.
No code or check changed. All 121 shipped files in shimmer:six match the tree.
Full host gate 244/246 with only known failures 01 and 145. Adversarial read done.

## Current item

None open. Continue with SEVEN after SIX is committed. The scorer must consume
existing unit suspension evidence and distinguish it from never assigned and
asked with no finding. Do not infer an actual model call from assignment alone.

## Ordered remaining work

1. SEVEN: scorer distinguishes never assigned, suspended, asked with no finding.
2. EIGHT: verify date_window visibility in the current scorer.
3. NINE: compute whether Python now settles ROWAN.
4. TEN: distinguish incomplete runs from completed empty runs.
5. ELEVEN: plain-language harness facts or explicit absence.
6. TWELVE: one run-id format.
7. THIRTEEN: structural proof against reading-only and no-op neutralisations.
8. FOURTEEN: trace typed records through real amendment artifacts.
9. FIFTEEN: pairing fallback value and WORDS-A compliance.
10. SIXTEEN: carry the ZERO-C container evidence into a complete answer.
11. SEVENTEEN: close the cache diagnosis with measured build reuse.
12. EIGHTEEN: prove README and image debt paid, including inherited omissions.
13. NINETEEN: classify document_dates.json in the manifest.
14. TWENTY: answer the learning-signal question, no GNN build.
15. TWENTY-ONE: put the quote prediction where the next run checks it.

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
Final SIX host: PASS=244 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=246.
Final FOUR image: PASS=234 WARN=0 SKIP=8 FAIL/ERROR=4 TOTAL=246, plus all six
offline probe steps PASS, 163 seconds combined. Tests used --network none,
--gpus all and no mounts. Host failures: 01 (prompts/snapshots absent) and 145
(missing ignored contamination fixture). Image source-only failures: 01, 28,
31 and 145. Skips name unavailable coverage. No new unexplained failure remains.
Logs: output/six_host_gate.log, output/four_container_validation.log and
output/four_mutation_proof.log. Focused changes prove independently observable
mutation effects before fail/restore/pass. No proof mutates real source files.
ZERO-C's earlier logs and image remain preserved; see LEDGER.

Docker: C:/Users/secki/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe.
Host-access py -3.9 sees installed dependencies and cached models; the sandbox
may hide them. Do not install replacements for sandbox-only failures. Only one
GPU model workload at a time. shimmer:six carries the current source and README.
SIX changes only documentation; its source audit matched all 121 shipped files.
FIVE's changed parser check passed offline without mounts. The full image gate
above was run on shimmer:four; its runtime and model layers remain unchanged.
All older tags remain intact. Current image identity and per-file source hashes:
output/six_source_audit.json. All source refreshes reused model/conversion layers.
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
