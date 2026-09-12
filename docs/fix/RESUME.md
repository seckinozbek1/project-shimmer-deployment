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

FOUR, the commit containing this checkpoint,
`FOUR: preserve local extraction capacity and audit draft state`.
Resolve its exact hash with `git log -1 --format=%H -- docs/fix/RESUME.md` until
another item updates this file. Previous item ZERO-C closed in
963cae235d1ef2f2e949f72133259a05a1647fe1.

PROCESSOR's local allowance and the outer cap are now 8192, measured against
6288/6081-token complete current-source extraction envelopes. Other active and
cloud budgets stay unchanged. Phase 5 withholds failed-contract best-effort
objects and gives both auditors draft availability/truncation explicitly.
Check 245 proves all 61 declared items reach both auditors through real phase
functions and mocked dispatch. Four observable mutations fail, restoration passes.
The two saved outputs were cut at 2048 tokens and contain 21/19 complete items,
not all 18 units as the older handoff claimed. Paired planning reads source;
optional recent bus context can still carry PROCESSOR output. No generation ran.
README, CLAUDE and shimmer:four are current. Full host and image gates passed
at their known environment bars. Adversarial read complete; details in LEDGER.

## Current item

None open. Continue with FIVE after the FOUR commit. Inspect saved raw envelope
failures against the actual parser before deciding what needs repair. Do not
loosen valid payload contracts or salvage a truncated response as complete.

## Ordered remaining work

1. FIVE: parse valid envelopes through packaging, retain the payload contract.
2. SIX: explain each of the eight agents that never called a model.
3. SEVEN: scorer distinguishes never assigned, suspended, asked with no finding.
4. EIGHT: verify date_window visibility in the current scorer.
5. NINE: compute whether Python now settles ROWAN.
6. TEN: distinguish incomplete runs from completed empty runs.
7. ELEVEN: plain-language harness facts or explicit absence.
8. TWELVE: one run-id format.
9. THIRTEEN: structural proof against reading-only and no-op neutralisations.
10. FOURTEEN: trace typed records through real amendment artifacts.
11. FIFTEEN: pairing fallback value and WORDS-A compliance.
12. SIXTEEN: carry the ZERO-C container evidence into a complete answer.
13. SEVENTEEN: close the cache diagnosis with measured build reuse.
14. EIGHTEEN: prove README and image debt paid, including inherited omissions.
15. NINETEEN: classify document_dates.json in the manifest.
16. TWENTY: answer the learning-signal question, no GNN build.
17. TWENTY-ONE: put the quote prediction where the next run checks it.

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
Final FOUR host: PASS=244 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=246.
Final FOUR image: PASS=234 WARN=0 SKIP=8 FAIL/ERROR=4 TOTAL=246, plus all six
offline probe steps PASS, 163 seconds combined. Tests used --network none,
--gpus all and no mounts. Host failures: 01 (prompts/snapshots absent) and 145
(missing ignored contamination fixture). Image source-only failures: 01, 28,
31 and 145. Skips name unavailable coverage. No new unexplained failure remains.
Logs: output/four_host_gate.log, output/four_container_validation.log and
output/four_mutation_proof.log. Focused changes prove independently observable
mutation effects before fail/restore/pass. No proof mutates real source files.
ZERO-C's earlier logs and image remain preserved; see LEDGER.

Docker: C:/Users/secki/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe.
Host-access py -3.9 sees installed dependencies and cached models; the sandbox
may hide them. Do not install replacements for sandbox-only failures. Only one
GPU model workload at a time. shimmer:four carries the current runtime;
shimmer:zero-c and the older tags remain intact. All 121 copied files matched
the tree. Image identity and per-file source hashes: output/four_source_audit.json.
The 7.4-second build reused model and conversion layers.
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
