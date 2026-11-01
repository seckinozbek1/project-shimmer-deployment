# S10 report: fresh-clone test (laptop and Docker)

Stage S10 of the autonomous loop of 27 October 2026, on branch `loop/s10`, created from the loop branch at `f269149` after the S7 merge and tag (D-163). Part V puts S10 after S8; D-S18 moves S8 and S9 after v1, so S10 ran before them (D-163). Plan: `docs/loop/stages/S10_PLAN.md`, checked twice (D-163). Opus, medium effort from 28 October 2026 (Annex D, D-S11).

## Open items at the start

Read at the branch point: item 7 (check 252 and the Dockerfile line), item 20 (the frozen launchers), item 54 (closed in S7). Both 7 and 20 are closed in this stage (below).

## What was done

- **Item 0, the launcher retirement.** `lane/s06-launchers` merged (`635ff40`): the sixteen frozen launchers and their nineteen companion files (35 files) moved to `archive/frozen_launchers/` byte for byte, no live caller left (D-163). Open item 20 and issue #25 closed. The D-154 re-walk ran after lane s10-fix1 (where `shimmer.sh` changed): `start_shimmer.bat --check-entry --no-browser` resolves its entry with the 3.12 venv, `shimmer.bat` reaches its menu and ends at end of input, `shimmer.sh` was walked by 6b on `s10-sh-3`; checks 298 to 311 pass (298 to 306 and 309 with fastapi) (D-168).
- **Item 0b, the S7 close's launcher-path defects (D-162).** Lane s10-fix1 (`d124540`, D-165): a draft under the local profile no longer calls the Claude API (INC-031; check 312), with the pinned-baseline amendment for `_draft_generate_with_evidence` in both pinned files (`0f424f48b9e9ab223d260a75a8cc2d679f2f9ad4449e7afac72991a7ec7c7a0a` to `35a84f2fe132acd4abb137523a18513d119b9f51b5274c649904a0645a894270`; the draft now also writes a `backend_invocation` telemetry row, which the amendment's reason does not mention, D-168); `shimmer.sh` passes its venv's Python in a form Windows Python can open (INC-030; check 308 with a real Windows venv); the chat window's startup line says only what was checked, and a request the model could not answer says so (check 310). L14c (sealed at `74408d3` after gate G1b and the side gates; 91 billed minutes, 1.96 USD): the review ran from the menu to its end again (exit 0); the draft wrote its memo with the local model on the instance (AMENDMENT_DRAFTER on `local_producer`, 1,148 tokens in, 4,096 out, the output cap; no network attempt, where L14b had three), and its review of the memo was still running when the run reached its deadline, so the menu was stopped and the arm's assessment failed (`launcher_stopped:deadline`, `draft_not_completed`, `draft_memo_missing`, `draft_context_not_cleared`). The draft path itself is fixed; a complete draft needs a longer run (L14d, after v1, D-167).
- **Item 1, laptop fresh clone.** D-S13 item 6b: `shimmer.bat`'s own install on a fresh clone (`s10-bat-2`, 724 s, menu reached with Local; D-160) and `shimmer.sh`'s under Git Bash on a fresh clone of loop/s10 at `74408d3` (`s10-sh-3`, 723 s, the CUDA torch build, menu reached; its piped `L` was read by a child before the backend question, open item 65). The final proof of S10 item 1 (a new fresh clone of the loop branch after S11's merge, README steps only, its own gate baseline) follows S11 (D-163); this stage is tagged `-open` until it has run.
- **Item 2, Docker.** Lane s10-image (`2db17e4`, D-165): a trace over 106 checks in a folder shaped like the image; every check that failed there for a missing file now skips and names it, proven on its own check with no assertion removed; `VERSION` ships; `seals/` is kept out of the build context; `tools/loop/` ships inert (DS10-2); the Dockerfile's shipping-gate line restored (open item 7, check 252 now passes; issue #7 closed). The build and the container gate did not run: free disk was 40.9 GB against the 30 GB floor plus the image; they follow the pip cache purge after S10's last fresh install (D-165; FOR_SECKIN 19:45).
- **Item 3, Lambda smoke run.** Moved to S12 item 8, and S12 leaves the loop (D-S17 item 3).
- **Item 4, defects recorded.** Fixed: INC-031 (`3bca570`, check 312), INC-030 (`5324b61`, check 308), the chat window's two honesty defects (`5324b61`, check 310), the image's checks that failed for a missing file (`49194bc`), the Dockerfile's shipping-gate line (`49194bc`, check 252), check 207's bypassed stand-in and check 311's literal assertion (`3bca570`, `5324b61`), and lane s10-fix2's (D-168). Recorded for S6: open items 57 to 67 (issues #115 to #125).
- **Item 5, the pip cache purge.** Waits for S10's last fresh install (D-S15 item 1, D-S17 item 3, D-165).

## Decisions

`docs/loop/DECISIONS.md`: D-163 (S10 starts), D-164 (D-S20 applied), D-165 (the two lanes merged, the pinned amendment, Local Draft's wording, open items 57 to 64), D-166 (gate G1b, the side gates, L14c sealed, the consistency check), D-168 (round 1, the sweep and the late S7 audit), and CLOSE_D.

## Gate

G1b at `09f563f`: PASS 272, WARN 1, SKIP 12, FAIL/ERROR 28 of 313, the loop baseline's non-pass set less check 252, which now passes; every side gate exits 0 at `74408d3` (D-166). GATE_CLOSE

## Checkers

CHECKERS

## Spend

SPEND

## Count line

COUNT

## Stage boundary

BOUNDARY

## Effort

Opus, medium effort from 28 October 2026 (Annex D, D-S11).
