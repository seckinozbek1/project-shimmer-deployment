# S7 report: console and launchers

Stage S7 of the autonomous loop of 27 October 2026, on branch `loop/s07`, created from the loop branch at `ea1c0d5` (S2 merged and tagged); its first pass ran alongside S5 (D-075), its final pass after the S5 close, inside v1 (D-S18 item 2b). The lead's close commits were made in the worktree `.claude/worktrees/s07-lead`. Opus, medium effort from 28 October 2026 (Annex D, D-S11).

## What was done

- **Item 1, the console shows the S1 to S6 data.** Lane s07-ui (`003e826`): read-only routes and views for the saved model replies and their outcomes (metadata only, never reply text, DS7-1), the model-written findings with their mark in both languages, provenance labels, multi-round runs with their reuse record, the agent switches (INST_FINDER on or off, the FACT_CHECKER withholding with both Annex B.4 reasons from one shared module, DS7-3, DS7-8), the run report and cost rows, and the test-change request log. The final pass reviewed S5's later additions against the console (lane s07-fix2, FIX2_REVIEW).
- **Item 2, never a sealed test's per-flaw results.** Every new view filters a sealed run to counts and timings; a sealed run's per-flaw routes answer 403 and `POST /evidence` refuses it (DS7-4, DS7-7). The close's adversarial checker found one route the filter missed, `/runs/{id}/activation`, which carried unit and rule ids into a sealed run's view: fixed in lane s07-fix2 and added to check 304's sealed observation (FIX2_ACTIVATION).
- **Item 3, API and gate checks.** Every route answers 401 without the token except exactly `/health` and `/console`; FastAPI's own `/docs`, `/redoc` and `/openapi.json` are switched off (DS7-5, check 305, with a neutralisation that switches them back on). Checks 298 to 306 (console), 307 to 310 (launchers and the chat window) and 311 (arm L) each prove neutralise, fail, restore, pass; the route table in `docs/RUNTIME_REFERENCE.md` equals the app's 36 routes (check 167).
- **Item 4, screenshots.** 27 pages rendered at 1280 and 390 pixels from the committed fixture (`tools/console_screenshots.py`), checked by a fresh checker (fix lane s07-fix1 closed its items, `10a25e9`); the final pass re-rendered what changed and scanned every page's rendered text with the H5 and private patterns (FIX2_SCREENS).
- **Item 5, launchers.** Lane s07-launch (`9ee7d26`): `shimmer.bat`, `shimmer.sh` and `start_shimmer.bat` reach their menus and end at end of input, with an honest banner; the `shimmer.bat` quoting defect that stopped every Windows start before installing anything is fixed (`7e80630`).
- **D-S13 item 6.** 6a: `start_shimmer.bat` driven on the merged tree as far as a script can (D-147). 6b: done as S10 item 1 (D-154). 6c: the 3.12 `.venv` in the main checkout (SIX_C). 6d: arm L (D-148), a third sealed arm that runs the launcher menu once on the instance; launch L14 (L14_RESULT). 6e: the chat window in command mode, two defects found and fixed, check 310 (D-147).

## Decisions

`docs/loop/DECISIONS.md`: D-075 (S7's first pass during S5), D-147 (the final pass), D-148 (arm L), D-154 (DS7-1 to DS7-8, the first-pass merges, S7 before S6, 6b to S10), and the close decision (CLOSE_D).

## Checkers

Three fresh checkers at the close (adversarial 13 items: 1 CRITICAL, 2 SERIOUS, 10 MINOR; completeness 13 gaps; claims 6 items) and a records consistency check before L14 (30 found, fixed in D-153). CHECKERS_RESULT

## Gate

The full gate at `02fae41` (the loop branch merged into loop/s07) equals the S5 worktree baseline apart from check 28 (a worktree has no `input/`) and S7's route checks, which skip under py -3.12 without fastapi and pass in the loop venv. The reaper proof passes from the lead's shell. GATE_RESULT

## Count line

COUNT_LINE

## Stage boundary

BOUNDARY

## Effort

Opus, medium effort from 28 October 2026 (Annex D, D-S11).
