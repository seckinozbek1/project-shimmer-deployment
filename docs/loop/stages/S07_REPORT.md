# S7 report: console and launchers

Stage S7 of the autonomous loop of 27 October 2026, on branch `loop/s07`, created from the loop branch at `ea1c0d5` (S2 merged and tagged); its first pass ran alongside S5 (D-075), its final pass after the S5 close, inside v1 (D-S18 item 2b). The lead's close commits were made in the worktree `.claude/worktrees/s07-lead`. Opus, medium effort from 28 October 2026 (Annex D, D-S11).

## What was done

- **Item 1, the console shows the S1 to S6 data.** Lane s07-ui (`003e826`): read-only routes and views for the saved model replies and their outcomes (metadata only, never reply text, DS7-1), the model-written findings with their mark in both languages, provenance labels, multi-round runs with their reuse record, the agent switches (INST_FINDER on or off, the FACT_CHECKER withholding with both Annex B.4 reasons from one shared module, DS7-3, DS7-8), the run report and cost rows, and the test-change request log. Exits 8 and 9 (a refused multi-round run, an unratified INST_FINDER switch) are governance statuses in the server and the console, not failures (lane s07-exitcodes, merged at `c2cce30`, check 108; open item 11, sweep 3). The final pass reviewed S5's later additions against the console (lane s07-fix2): none needed a console view for v1 (D-156).
- **Item 2, never a sealed test's per-flaw results.** Every new view filters a sealed run to counts and timings; a sealed run's per-flaw routes answer 403 and `POST /evidence` refuses it (DS7-4, DS7-7). The close's adversarial checker found one route the filter missed, `/runs/{id}/activation`, which carried unit and rule ids into a sealed run's view: fixed in lane s07-fix2 and added to check 304's sealed observation (`4dddfe0`, `9c5377b`, merged at `015c388`; with it a pending question on `/approvals` and `/runs/{id}` keeps only its timings, `/undated-documents` and `/convention-assignment` answer 403, and a sealed run's record names no document, file or target, D-156).
- **Item 3, API and gate checks.** Every route answers 401 without the token except exactly `/health` and `/console`; FastAPI's own `/docs`, `/redoc` and `/openapi.json` are switched off (DS7-5, check 305, with a neutralisation that switches them back on). Checks 298 to 306 (console), 307 to 310 (launchers and the chat window) and 311 (arm L) each prove neutralise, fail, restore, pass; the route table in `docs/RUNTIME_REFERENCE.md` equals the app's 36 routes (check 167).
- **Item 4, screenshots.** 27 images of 16 views rendered from the committed fixture (the English views at 1280 and 390 pixels, the five Turkish views at 1280 only) (`tools/console_screenshots.py`), checked by a fresh checker (fix lane s07-fix1 closed its items, `10a25e9`); the final pass re-rendered what changed and scanned every page's rendered text with the H5 and private patterns : ten sealed-section pages re-rendered, the rendered text of 7 pages scanned, name pattern and private patterns 0 (D-156).
- **Item 5, launchers.** Lane s07-launch (`9ee7d26`): `shimmer.bat`, `shimmer.sh` and `start_shimmer.bat` reach their menus and end at end of input, with an honest banner; the `shimmer.bat` quoting defect that stopped every Windows start before installing anything is fixed (`7e80630`).
- **D-S13 item 6.** 6a: `start_shimmer.bat` driven on the merged tree as far as a script can (D-147). 6b: moved to S10 item 1 (D-154); the README's manual install ran on a fresh clone (D-157), and the launchers' own installs (`shimmer.bat`, `shimmer.sh`) on fresh clones of loop/s07 are queued at the operator's 4 GB floor (D-158) (SIX_B). 6c: the 3.12 `.venv` in the main checkout (SIX_C). 6d: arm L (D-148), a third sealed arm that runs the launcher menu once on the instance; launch L14 (L14_RESULT). 6e: the chat window in command mode, two defects found and fixed, check 310 (D-147); plain-language mode needs the local Qwen model and 4 GB free, and the loop runs it at a 4 GB window (D-158) (PLAIN).

## Decisions

`docs/loop/DECISIONS.md`: D-075 (S7's first pass during S5), D-147 (the final pass), D-148 (arm L), D-154 (DS7-1 to DS7-8, the first-pass merges, S7 before S6, 6b to S10), D-155 (L14 read), D-156 (the checkers' code findings fixed), D-157 (the arm L fix merged; the gate stopped for memory), D-158 (sweep 3), and the close decision (CLOSE_D).

## Checkers

Round 1, three fresh checkers at the close (adversarial 13 items: 1 CRITICAL, 2 SERIOUS, 10 MINOR; completeness 13 gaps; claims 6 items; private `analysis/s7close-*.md`) and a records consistency check before L14 (30 found, private `analysis/consistency_l14.md`, fixed in D-153). The code findings, the CRITICAL sealed `/activation` leak included, were fixed in lane s07-fix2 and the claims checker's corrections recorded (D-156); adversarial item 13 (arm L declaring its run non-sensitive) was fixed in lane s07-arml2 (D-157); one was left as open item 52 (arm L counts only the Python children that report themselves). L14's own failure was fixed in lane s07-arml2, merged at `3f45d23` (D-157). Sweep 3 over S7 (D-158): 16 found, 0 brought back, 15 decided, 0 kept, 1 to Seckin. Round 2 (IV.4 item 5) on `02fae41..c2cce30` (private `analysis/s7close-round2.md`, D-159): adversarial, of round 1's 13 items 9 closed, 3 recorded, 1 closed in part, and 3 new MINOR items, none CRITICAL or SERIOUS; completeness, the round 1 gaps closed or scheduled and 7 close steps not yet listed; claims, 4 of round 1's 6 closed and 12 statements corrected. ROUND2_CLOSE

## Exit criteria (S07_PLAN.md)

| Criterion | State at this close | Evidence |
|---|---|---|
| Console and launchers current, including S6's additions | Met for S1 to S5 and the S7 work; the pass over S6's additions is S6's close work (S7 ran before S6, D-154) | items 1 and 5 above; issue #112, D-158 |
| Route table and checks 104 and 167 pass | Met: 36 routes, checks 104, 116, 165 to 167 pass in the loop venv at `015c388` and `c2cce30` | D-156; merge `c2cce30` |
| Screenshots checked and reviewed | Met: all 27 images checked when rendered (lane s07-fix1); the ten sealed pages re-rendered at `015c388` reviewed by a fresh checker, 0 CRITICAL, 0 SERIOUS, 5 MINOR (open item 55) | `docs/loop/ui/`; private `analysis/s7_shots_checker.md` |
| Gate checks | Met: checks 298 to 311 added, 108 extended, each with neutralise, fail, restore, pass | D-156, D-157, merge `c2cce30` |
| Checkers closed; stage merged; tag | CLOSE_STATE | Checkers below; D-159 |

## Spend

L14: 13 billed minutes, 0.28 USD (forecast 1.68, cap 2.52; D-155). SPEND_L14B

## Gate

The full gate at `02fae41` (the loop branch merged into loop/s07) equals the S5 worktree baseline apart from check 28 (a worktree has no `input/`) and S7's route checks, which skip under py -3.12 without fastapi and pass in the loop venv. The reaper proof passes from the lead's shell at `c2cce30` (`all_passed`, saved in private `gate_logs/s07_c2cce30/reaper_proof.log`). GATE_RESULT

## Count line

COUNT_LINE

## Stage boundary

BOUNDARY

## Effort

Opus, medium effort from 28 October 2026 (Annex D, D-S11).
