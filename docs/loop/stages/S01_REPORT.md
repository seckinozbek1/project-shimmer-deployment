# S1 report: hygiene, saving every model reply, the INST_FINDER switch, multi-round readiness

Stage S1 of the autonomous loop of 27 October 2026, on branch `loop/s01` (created from `loop-s00-v1-open`, `5e844ed`). No pipeline run and no Lambda spend.

(Draft, filled in as the commits land.)

## Commits and gates

| Commit | Content | Gate (main checkout, `py -3.12`) |
|---|---|---|
| `f1d7a51` | S1 plan (records only) | not needed (records only) |
| `979aa4e` (C1) | Parts 1 and 5 | main PASS 244, WARN 1, SKIP 3, FAIL or ERROR 28 (the S0 baseline plus new check 275, which passes; same non-pass set); six side gates pass |

## Part 1. The collaborator's project name

- Re-verified with the H5 pattern: exactly two tracked files, one hit each (`docs/fix/SESSION_HANDOFF.md` line 25, `docs/fix/WORDS_D_INVENTORY.md` line 4). Private patterns over tracked files: 0 files for each of the three (incomplete: private patterns missing from `.claude/` (I.0 item 4 failed); the same three patterns were applied from `docs/loop/private/loop_private_patterns.txt`). So no private-pattern hit needed a binding check.
- A scratch script found each line by the hex pattern and replaced the whole token: line 25 of `SESSION_HANDOFF.md` now names "a private repository, not named here", line 4 of `WORDS_D_INVENTORY.md` "an ingestion folder for an external system (not in this repository)". One line changed in each file. Recount: 0 files in the working tree and 0 in the index at C1.
- Incident INC-003 (private record): after C1 the lead checked the commit message with a pattern that spelled the name in plain letters, once, in a tool call; nothing in any file, commit or record carries it (re-checked with the hex pattern). Decision D-009; reported to Seckin.

## Part 5. Documentation corrections, the request log, the seals folder

- `CLAUDE.md`: the "2/9 to 5/9" sentence keeps its point and now carries its context (7 September 2026; the synthetic wheat test; code from an earlier repository not in this history; a single draw; a location count, not reason-confirmed; the wheat test and key not published here).
- `docs/history/README_PRE_ROUTING_AUDIT.md`: a dated correction note after each of the two "clean twin was never run" statements, pointing to the 2026-09-12 overnight runs and the 2026-09-11 deepening-pass measurements in the same document. No other change.
- `docs/test_change_requests.md`: header and fields (Annex B.6); a verdict for every test folder under `benchmark/corpora/` and for the superseded tuning datasets; eleven requests (TCR-001 to TCR-011), proposals only.
- `.gitignore` gains `seals/`. `scripts/guard_secrets.py --staged` refuses any staged path under `seals/` (plain prefix test over git's own staged-name list, force-added paths included; no new regex). Gate check 275 (`scripts/staged_path_checks.py`): name-list cases, and on a real git index a staged and a force-added `seals/` path refused, an ordinary path passing; the git case is skipped with its reason where git is absent (the container). Neutralise, fail, restore, pass on that check alone: PASS, FAIL (2 failures), PASS.
- `docs/THREAT_MODEL.md`: now says the guard scans file contents across the working tree, that `--staged` checks staged paths only, and that no hook runs it (the `.githooks` folder the old text named does not exist).
