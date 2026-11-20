# Short README: applied (lane readme-short, 19 November 2026)

Purpose: apply section B of the approved public first-results draft (Seckin, 19 November 2026 21:26, G-20261119-2126, recorded by the lead as D-816), move every other README section into docs pages, and update the testing rule per his 21:06 decision. Development documentation only; no run, no spend.

## Move table as applied

Old line numbers are README.md at 02d1da49 (620 lines).

| Old section (lines) | Now at | Change in moving |
|---|---|---|
| Opening paragraph (1-7) | README top paragraph and bullets | replaced by the approved B1 text |
| Status and 31 October paragraph (9-20) | docs/RESULTS.md, "Earlier development results (to 18 November 2026)" | README keeps one status line; the 11 and 14 November gate wording rewritten in the past tense with the 18 November state |
| Which benchmarks count now (22) | docs/RESULTS.md, "Which benchmarks count" | |
| Where Shimmer is now (24-55) | README "First results" table; docs/RESULTS.md "First results (November 2026)" (text A, D-481 update rule kept); the 18 November text kept as "The state on 18 November 2026"; "Our negotiation benchmark" | "Going" list (49-54) dropped as the approved table says; the pilot bullet's "no pilot figures are quoted" now points to the first results |
| What Shimmer is (56-83) | docs/METHOD.md, "Design and related work" | links made relative |
| What it does (85-117) | docs/METHOD.md, "What it does" | |
| It does not (118-129) | docs/LIMITATIONS.md, "What it does not do" | "Claude under Cloud" made "a provider model under Cloud"; anchors relinked to docs/THREAT_MODEL.md |
| How a review works (131-157) | docs/METHOD.md, "How a review works" | |
| What has been measured (159-261) | docs/RESULTS.md, "Summary to 31 October 2026, as the README gave it" | its table not repeated: every figure is in the page's own Summary table |
| Limitations (262-283) | docs/LIMITATIONS.md, "Limitations" | line 265 corrected: the steering subsets were scored on the same items, different runs and dates |
| Hardware and cost (285-311) | docs/INSTALL.md, "Hardware and cost" | |
| Install (313-396) | docs/INSTALL.md, "Install" | |
| Quickstart (397-441) | docs/USER_GUIDE.md, "11. Quickstart" | |
| Configuration (442-470) | docs/USER_GUIDE.md, "12. Configuration" | |
| Constitution and agents (471-501) | docs/METHOD.md, "The constitution and agents" | |
| Privacy (502-517) | docs/THREAT_MODEL.md, "Privacy (LAW-IV)"; one line in docs/LIMITATIONS.md | |
| Access (518-525) | docs/THREAT_MODEL.md, "Access (one operator)" | |
| Testing rules (526-546) | docs/RESULTS.md, "Testing rules" | last bullet updated (below) |
| Reproducing the evaluation (548-580) | docs/RESULTS.md, "Reproducing the evaluation" | |
| Development and validation (582-603) | docs/METHOD.md, "Development and validation checks" | |
| History of this repository (605-613) | docs/METHOD.md, "History of this repository" | |
| Citation and licence (615-619) | README, "Citation and licence" | approved B1 text |

Table C of the draft is on docs/RESULTS.md as "Sources of the first results", every private record path replaced by "(record)"; public sources (docs/loop/DECISIONS.md, docs/loop/stages/NEG_*.md) keep file and line.

## Testing rule

Old README.md:540 now reads, in docs/RESULTS.md "Testing rules": sealed final-test figures remain the evidence bar (three independently prepared sealed tests, one commit, spread reported); first results on development and validation sets may be quoted publicly when labelled as first results and stating that the final test set has not been run (D-816). docs/loop/LOOP_UNDERSTANDING.md item 123 carries the same narrowing. The loop specification under prompts/ (Annex 11.11) is not edited.

## Hygiene

- Readers of README.md in scripts/ and tools/: only scripts/routing_doc_checks.py (check 260) reads it, for the link to docs/RUNTIME_REFERENCE.md, which the short README keeps. Checks 116 and 167 read docs/RUNTIME_REFERENCE.md; check 01 lists README.md as an allowed root file; check 314 reads CITATION.cff and VERSION only. No check reads a moved heading.
- Links fixed: docs/RUNTIME_REFERENCE.md (README#development-and-validation to METHOD.md), docs/THREAT_MODEL.md (the "stated plainly in README.md" line), docs/USER_GUIDE.md intro, docs/RUNBOOK.md (fresh-clone steps). CLAUDE.md and docs/CLAUDE_REFERENCE.md name README.md only as the newcomer guide; unchanged. A link and anchor check over the eight changed pages found none broken. No em or en dash in any changed file; no collaborator, partner or integration name added.
- Not changed: the Dockerfile still copies README.md and docs/RUNTIME_REFERENCE.md only, so in the image the README's links to the new docs pages do not resolve (an image change is outside this lane). D-816 is cited but lives in the lead's DECISIONS.md, not yet on this branch.

## Checks run (each alone, `--offline --checks N`)

| Check | Result |
|---|---|
| 260 routing documentation parity | PASS |
| 116 env table | PASS |
| 167 route table | PASS (fastapi absent here: skipped as N/A, the known baseline) |
| 01 directory structure | SKIP (worktree has no local input/output trees, the known baseline) |
| 314 CITATION.cff version | PASS |

## Independent audit fixes (lane readme-audit-fixes, 19 November 2026)

Seckin approved every fix of the independent publication audit (19 November 2026 21:49, G-20261119-2149); the same points are applied here. Line numbers are after the change.

- README.md:16-17: v1 "published on GitHub on 2 November 2026"; "Version 1.0 is not released yet" kept.
- README.md:24: table column "Bare model / cloud model (references only)".
- README.md:27, 29: the two steering-subset rows say "does not count (void on integrity), below both bars".
- README.md:32-36: new paragraph: under the project's rules the quick subset 0127b080 run does not count (void on integrity, many items undecided), well short of both bars (at least 10 points above the bare model, at most 5 below the cloud model); "every measured Shimmer run so far" used local models; cloud figures are references only.
- docs/RESULTS.md:18: ContraDoc steering-subset paragraph gains the same does-not-count and both-bars sentence.
- docs/RESULTS.md:20: SciTab steering-subset sentence gains it too.
- docs/RESULTS.md:22: bare and cloud negotiation figures stated as references only; every measured Shimmer run used local models.
- docs/RESULTS.md:37, 43: source rows marked "void on integrity, does not count, below both bars".
- docs/RESULTS.md:55: comparison conditions end with the references-only sentence.
- docs/RESULTS.md:59: v1 "published on GitHub on 2 November 2026".
- docs/RESULTS.md:90: the 18 November record notes the later read of the same quick subset is void on integrity too.
- docs/RESULTS.md:102: "frozen before any system is run on them; the benchmark is to be published with its scorer" (no claim that it is already published).
- docs/LIMITATIONS.md:11: the steering-subset Shimmer run does not count and is below both bars.
- docs/LIMITATIONS.md:24-26: "Shimmer's cloud backend" has no figure; cloud model figures are references only; "Every measured Shimmer run so far".
- docs/INSTALL.md:96: "Every measured Shimmer run so far used one NVIDIA A10".

No "frozen and published before any system is run" wording was found on these pages; METHOD.md, USER_GUIDE.md, THREAT_MODEL.md, GUIDE_EN.md, GUIDE_TR.md and RUNTIME_REFERENCE.md held no audit point. The site, CV, LinkedIn and Medium points (S1-S7, C1-C2, M1-M5, L1-L2) are outside this repository.
