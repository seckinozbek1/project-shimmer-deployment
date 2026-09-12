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

ZERO-C, the commit containing this checkpoint, subject
`ZERO-C: bake safely loadable weights and prove offline decisions`.
Resolve its hash with `git log -1 --format=%H -- scripts/model_weights.py`.
The code parent at recovery was 64b83e0; ZERO-A and ZERO-B were already closed.

The inherited image carried a raw bge-m3 checkpoint. Its old probe passed only
after network retries and unsafe runtime conversion. The image now prepares
safetensors with an isolated torch 2.6.0 CPU reader using weights_only=True,
then removes the converter installation. Runtime pins and model ids stay fixed.
The probe refuses attempted network access and requires five votes with scores
and references. Check 244 proves safe conversion through the real loader.
Check 239 now finishes its synthetic proofs without unshipped corpora and names
that missing coverage; a nonempty but incomplete corpus still fails. Its mutation
executes the actual consumer rather than merely rewriting source text.

## Current item

ZERO-C is complete. Commit this checkpoint if still uncommitted, then open FOUR:
establish whether paired review depends on PROCESSOR extraction, then fix its
truncation loss. No other backlog implementation was opened in this session.
The loader now resolves a local snapshot and refuses custom generation overrides;
check 193 observes HTTP attempts as well as new connections, so a reused pool
cannot hide a request. Its actual resolver mutation fails and restoration passes.
SIXTEEN already has positive evidence. SEVENTEEN has a measured cache remedy,
with the historical GC event unproven.

## Ordered remaining work

1. FOUR: PROCESSOR extraction dependency and loss.
2. FIVE: parse valid envelopes through packaging, retain the payload contract.
3. SIX: explain each of the eight agents that never called a model.
4. SEVEN: scorer distinguishes never assigned, suspended, asked with no finding.
5. EIGHT: verify date_window visibility in the current scorer.
6. NINE: compute whether Python now settles ROWAN.
7. TEN: distinguish incomplete runs from completed empty runs.
8. ELEVEN: plain-language harness facts or explicit absence.
9. TWELVE: one run-id format.
10. THIRTEEN: structural proof against reading-only and no-op neutralisations.
11. FOURTEEN: trace typed records through real amendment artifacts.
12. FIFTEEN: pairing fallback value and WORDS-A compliance.
13. SIXTEEN: carry the ZERO-C container evidence into a complete answer.
14. SEVENTEEN: close the cache diagnosis with measured build reuse.
15. EIGHTEEN: prove README and image debt paid, including inherited omissions.
16. NINETEEN: classify document_dates.json in the manifest.
17. TWENTY: answer the learning-signal question, no GNN build.
18. TWENTY-ONE: put the quote prediction where the next run checks it.

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
Final host: PASS=243 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=245.
Final image: PASS=233 WARN=0 SKIP=8 FAIL/ERROR=4 TOTAL=245, plus all six offline
probe steps PASS, 122.8 seconds combined on the final image. Tests used --network none, --gpus all,
and no mounts. Checks 139, 193, 239 and 244 PASS. The two host failures are 01
(prompts/snapshots absent) and 145 (missing ignored contamination fixture).
The image's four source-only failures are 01, 28, 31 and 145; skips explicitly
name the coverage not run. No new unexplained failure remains.

Final logs: output/zero_c_resolved_host_gate.log and
output/zero_c_release_container_validation.log (the final image repeated the
233/245 result after the README refresh). Focused proofs are in
output/zero_c_loader_proof.log, output/zero_c_custom_code_proof.log,
output/zero_c_239_proof.log and output/zero_c_focused_proof.log. Each changed
check has an independent observable mutation effect and fail/restore/pass.
No neutralisation modified a real source file for the new proofs.

Docker: C:/Users/secki/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe.
Host-access py -3.9 sees installed dependencies and cached models; the sandbox
may hide them. Do not install replacements for sandbox-only failures. Only one
GPU model workload at a time. shimmer:zero-c carries the fixed runtime; old image
tags remain intact. All 121 copied files matched the tree. The final README
refresh carries the measured totals; the final image itself was verified again. Latest image identity and source audit: output/zero_c_source_audit.json.
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
