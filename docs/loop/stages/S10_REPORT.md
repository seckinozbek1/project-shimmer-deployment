# S10 report: fresh-clone test (laptop and Docker)

Stage S10 of the autonomous loop of 27 October 2026, on branch `loop/s10`, created from the loop branch at `f269149` after the S7 merge and tag (D-163). Part V puts S10 after S8; D-S18 moves S8 and S9 after v1, so S10 ran before them (D-163). Plan: `docs/loop/stages/S10_PLAN.md`, checked twice (D-163). Opus, medium effort from 28 October 2026 (Annex D, D-S11).

## Open items at the start

Read at the branch point: item 7 (check 252 and the Dockerfile line), item 20 (the frozen launchers), item 54 (closed in S7). Both 7 and 20 are closed in this stage (below).

## What was done

- **Item 0, the launcher retirement.** `lane/s06-launchers` merged (`635ff40`): the sixteen frozen launchers and their nineteen companion files (35 files) moved to `archive/frozen_launchers/` byte for byte, no live caller left (D-163). Open item 20 and issue #25 closed. The D-154 re-walk ran after lane s10-fix1 (where `shimmer.sh` changed): `start_shimmer.bat --check-entry --no-browser` resolves its entry with the main checkout's new `.venv` (made by 6c, Python 3.12.9 by its `pyvenv.cfg`), `shimmer.bat` reaches its menu and ends at end of input, `shimmer.sh` was walked by 6b on `s10-sh-3`; checks 298 to 306, 309, 310, 312 and 313 pass with fastapi (`venv_gate312`) at `6f69323`, and 307, 308 and 311 in the full gate (D-169; private `gate_logs/s10_rewalk/`).
- **Item 0b, the S7 close's launcher-path defects (D-162).** Lane s10-fix1 (`d124540`, D-165): a draft under the local profile no longer calls the Claude API (INC-031; check 312), with the pinned-baseline amendment for `_draft_generate_with_evidence` in both pinned files (`0f424f48b9e9ab223d260a75a8cc2d679f2f9ad4449e7afac72991a7ec7c7a0a` to `35a84f2fe132acd4abb137523a18513d119b9f51b5274c649904a0645a894270`; the draft now also writes a `backend_invocation` telemetry row, which the amendment's reason does not mention, D-168); `shimmer.sh` passes its venv's Python in a form Windows Python can open (INC-030; check 308 with a real Windows venv); the chat window's startup line says only what was checked, and a request the model could not answer says so (check 310). L14c (sealed at `74408d3` after gate G1b and the side gates; 91 billed minutes, 1.96 USD): the review ran from the menu to its end again (exit 0); the draft wrote its memo with the local model on the instance (AMENDMENT_DRAFTER on `local_producer`, 1,148 tokens in, 4,096 out, the output cap; no network attempt, where L14b had three), and its review of the memo was still running when the run reached its deadline, so the menu was stopped and the arm's assessment failed (`launcher_stopped:deadline`, `draft_not_completed`, `draft_memo_missing`, `draft_context_not_cleared`). The draft path itself is fixed; a complete draft needs a longer run (L14d, after v1, D-167).
- **Item 1, laptop fresh clone.** D-S13 item 6b: `shimmer.bat`'s own install on a fresh clone (`s10-bat-2`, 724 s, menu reached with Local; D-160) and `shimmer.sh`'s under Git Bash on a fresh clone of loop/s10 at `74408d3` (`s10-sh-3`, 723 s, the CUDA torch build, menu reached; its piped `L` was read by a child before the backend question, open item 65). The final proof of S10 item 1 (a new fresh clone of the loop branch after S11's merge, README steps only, its own gate baseline) follows S11 (D-163); this stage is tagged `-open` until it has run.
- **Item 2, Docker.** Lane s10-image (`2db17e4`, D-165): a trace over 106 checks in a folder shaped like the image; every check that failed there for a missing file now skips and names it, proven on its own check with no assertion removed; `VERSION` ships; `seals/` is kept out of the build context; `tools/loop/` ships inert (DS10-2); the Dockerfile's shipping-gate line restored (open item 7, check 252 now passes; issue #7 closed). The build and the container gate did not run: free disk was 40.9 GB against the 30 GB floor plus the image; they follow the pip cache purge after S10's last fresh install (D-165; FOR_SECKIN 19:45). Open at this close, under the tag `loop-s10-v1-open` (D-168): the final fresh-clone proof and its gate baseline, the image build, the container gate and the container baseline. 6e (plain-language chat) is deferred for memory (D-168).
- **Item 3, Lambda smoke run.** Moved to S12 item 8, and S12 leaves the loop (D-S17 item 3).
- **Item 4, defects recorded.** Fixed: INC-031 (`3bca570`, check 312), INC-030 (`5324b61`, check 308), the chat window's two honesty defects (`5324b61`, check 310), the image's checks that failed for a missing file (`49194bc`), the Dockerfile's shipping-gate line (`49194bc`, check 252), check 207's bypassed stand-in and check 311's literal assertion (`3bca570`, `5324b61`), and lane s10-fix2's (`72d1f80`, merged at `ac86b20`: no local-profile path builds a provider client, check 313; checks 312, 295, 297 and 310 tightened; D-169). Recorded for S6: open items 57 to 69 (issues #115 to #127).
- **Item 5, the pip cache purge.** Waits for S10's last fresh install (D-S15 item 1, D-S17 item 3, D-165).

## Decisions

`docs/loop/DECISIONS.md`: D-163 (S10 starts), D-164 (D-S20 applied), D-165 (the two lanes merged, the pinned amendment, Local Draft's wording, open items 57 to 64), D-166 (gate G1b, the side gates, L14c sealed, the consistency check), D-167 (L14c read, L14d after v1, 6b), D-168 (round 1, the sweep and the late S7 audit), and D-169 (round 2 and the close).

## Gate

G1b at `09f563f`: PASS 272, WARN 1, SKIP 12, FAIL/ERROR 28 of 313, the loop baseline's non-pass set less check 252, which now passes; every side gate exits 0 at `74408d3` (D-166). After lane s10-fix2 (`6f69323`, unbuffered, 22:31 to 22:56): PASS 273, WARN 1, SKIP 12, FAIL/ERROR 28 of 314, the same non-pass set as G1b (check 313 new and passing); side gates at `6f69323` in the main checkout: all seven exit 0, no tracked change left. The edits after it (check 313's harness case and its fourth neutralisation, check 312's and 313's docstrings, D-169, D-170) were run alone, PASS (private `gate_logs/s10_round3/checks_312_313.log`), and are covered by the loop-branch gate after the merge.

## Checkers

Round 1 (private `analysis/s10close-round1.md`): completeness 13 gaps, adversarial 1 SERIOUS and 5 MINOR, claims 7, sweep 17, the late S7 audit 4 (D-168). Round 2 (private `analysis/s10close-round2.md`): completeness 12 closed, 11 recorded, 7 open (records); adversarial 2 SERIOUS (both record gaps) and 5 MINOR; claims 5. Round 3 (private `analysis/s10close-round3.md`): completeness 16 closed, 3 open (records); adversarial 1 SERIOUS (check 313's fourth neutralisation failed by the harness exiting, not by a client being built) and 3 MINOR (docstrings); claims 11 (records). All closed or recorded (D-170); no CRITICAL or SERIOUS item is left, so no tie-break was needed. Each item's closure is listed in D-168 (round 1), D-169 (round 2) and D-170 (round 3).

## Spend

L14c: 91 billed minutes, 1.96 USD (forecast 1.48, cap 2.22; D-167). S10 spent 1.96 USD; the loop's total is 66.63 USD by the reaper, 132.37 left under 199.

## Count line

S10 plan: items 0 to 6 and section 0b's eight items; done: 0, 0b.1 to 0b.4, 0b.6, 0b.8, 1 (6b both launchers), 2.1, 4; open under the tag: 1 (final proof and baseline), 2.2 to 2.4 (image, container gate, baseline), 5 (purge after the final proof); deferred: 0b.5's full draft (L14d after v1, money and v1's date, FOR_SECKIN 22:15), 0b.7 (6e, memory); item 3 moved out of the loop (D-S17). Checker items: every one fixed or recorded with its reason. Not now, in S6 by P16, each with its issue: open items 57 to 69 (item 56, found at the S7 close, also stays for S6). Plan item 6 (the other letters of D-S13 item 6, status only): 6a's loop-end walk is S14's, 6c done (D-162), 6b done, 6d and 6e deferred (D-167, D-168).

## Stage boundary

Instances at the boundary: none (reaper after L14c, 0 listed). Storage: about 0.71 USD so far; at 0.13 USD a day (BUDGET.md) to the loop's estimated end on 7 November, about 0.8 more, about 1.5 in all, 0.5 past the 1.0 set aside (D-139), charged to the reserve first (IV.3). Disk about 40 GB free. Loop-until-certain, three rounds after checker round 3: what is left is named above; none is critical; the one uncertainty is the image's size against the disk floor, measured only when it is built.

## Effort

Opus, medium effort from 28 October 2026 (Annex D, D-S11).
