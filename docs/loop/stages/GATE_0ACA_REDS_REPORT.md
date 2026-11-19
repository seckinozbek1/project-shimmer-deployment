# Gate 0acab665: the thirteen new reds

Lane `lane/gate-0aca-reds`, 19 November 2026. The full gate of 0acab665 on Lambda (arm G, Linux, Python
3.12.3, a git checkout) ended 453 PASS, 14 FAIL, 10 ERROR, 6 SKIP. Eleven reds were known (28, 31, 118,
121, 146, 193, 257, 325, 333, 338, 348) and are not touched here. The thirteen new ones had four causes:
one Windows-only import, one Windows-only path form, two fixtures made stale by later merges, and one
neutralisation made stale by a later signature change. No check was weakened, skipped or marked known red.

Log: `verify.log` of the 0acab665 gate evidence (line numbers below are in that file).

## Per check

| Check | Log line | Cause (code line at 0acab665) | Fix |
|---|---|---|---|
| 431 | 18412: `proof_declared_wheelhouse_part_accepted: ModuleNotFoundError No module named 'msvcrt'` | `tools/loop/drive_paced.py:47` `import msvcrt` at module level (since 4741b371); the wheelhouse proof imports drive_paced, which no Linux-gate check did at 3efb3a37 | the lock (`drive_paced.lock()`) imports msvcrt on Windows and uses `fcntl.flock` on POSIX, the same split as `launch_chain._lock_region`; the module-level import is gone |
| 575, 576, 577, 578 | 18502 to 18509: `ERROR ModuleNotFoundError: No module named 'msvcrt'` | the same import: the D-763 checks import drive_paced | the same fix |
| 640, 641, 642, 643 | 18510 to 18517: the same error | the same import: the D-764 checks import drive_paced | the same fix |
| 534 | 18489: `role_start_check as built: ('FAIL', True, 'FAIL', 'FAIL', True, 'STOPPED', [])` | `tools/loop/role_start_check.py:108` `resolve()` and `guards()` take a .cmd path such as `inputs_N\REQUEST_ROLE_N_S9.md` as written; on POSIX a backslash is part of a name, so an existing file read as missing. After that, the allowlist proof failed too: `:66` `ABS_MD_RE` knew only `C:\...` absolute paths, so a POSIX absolute request path on the claude -p line was never found | `cmd_path()` turns a .cmd path's backslashes into separators on POSIX (Windows unchanged), applied in `guards()` and `resolve()`; on POSIX `ABS_MD_RE` also accepts a POSIX absolute path (Windows pattern unchanged) |
| 465 | 18438: `proof_step_five_admitted_five_point_oh_one_refused: AssertionError {... 'spend_limits_decision': 'D-749'}` | stale fixture: `tools/loop/spend_limits_checks.py:74` pinned `'D-708'` and `:90` pinned 140/197/337, while D-749 (c4bbb368, after the green gate) declares 203 from 197, ceiling 400; fails on Windows too | the proofs read the declared figures from `config/loop_spend_limits.json` as it is: the decision is the file's, the remaining-limit proof (renamed `proof_remaining_limit_from_the_declared_baseline`) places its spends 9, 5.5 and 4 USD under the declared ceiling, checks ceiling = baseline + limit and that the newest history entry carries the top-level decision and limit; the 5 USD step pin stays; same neutralisations |
| 476 | 18458: `claim_cells_checked as built: {'listed': {... 'python_cells': False ...` | stale fixture: N4 (97261614, `config/cell_selection.json` `whole_table_max_cells` 160) shows a small named table whole, so the F1 cells of the fixture table are R2C3 and R1C3, no longer R2C2 and R1C2 (`tools/reasoning_methods_checks.py:81, 333, 343, 422`); the model cited the Acc cells; fails on Windows too | the fixture cites R2C3 and R1C3 and expects their rendering (`R2C3: BERT large / F1 score = 70`); the proofs and neutralisations are otherwise unchanged |
| 468 | 18429: `test_03_stepwise_chain_checked_step_by_step: effect_proof.ProofFailure: OBSERVATION_ERROR` | stale neutralisation: `tools/neg_advisor_d711_checks.py:339` patched `_step_check` with a lambda of five parameters; `neg_advisor._step_check` gained `answers=None` in aaa7bf97 (neg-optional), so the neutralised run raised TypeError instead of showing the changed observation; fails on Windows too | the lambda takes `answers=None` |

## Proofs

Windows (the laptop), only these checks:

    py -3.12 -X utf8 scripts/verify_session1.py --checks 431,465,468,476,534,575,576,577,578,640,641,642,643

Linux (WSL Ubuntu, Python 3.12.3, the same as the Lambda gate), on the same tree:

    wsl -d Ubuntu -- python3.12 -X utf8 scripts/verify_session1.py --checks 431,465,468,476,534,575,576,577,578,640,641,642,643

| Tree | Windows | Linux (WSL) |
|---|---|---|
| 0acab665, before the fix | 10 PASS, 465, 468, 476 FAIL | the Lambda log (after the drive_paced fix alone, WSL: 534 still FAIL) |
| 0acab665 plus the fix | 13 PASS | 13 PASS |
| lead tip 155e17bb, before the fix | not run | 13 of 13 FAIL or ERROR, as on Lambda |
| lane rebased onto 155e17bb | 13 PASS | 13 PASS |

Every gate check whose source names a touched module (395, 430 to 432, 465 to 468, 470, 471, 475, 476,
490 to 494, 507 to 509, 515, 516, 518, 531 to 535, 539 to 543, 575 to 578, 640 to 643; 41 checks) passed
on both systems on the rebased tree. Both systems ran every branch of the fix: the msvcrt lock on Windows
and flock on Linux, the backslash handling as a no-op on Windows and as a conversion on Linux. The full
gate was not run on the laptop.

## Mergeability

The lane is rebased onto `lead/night-20261119` (155e17bb); it merges as a fast-forward. Nothing seal-bound
is touched (no controller, runner, sealer or guard file).

## Found, not fixed

- `tools/loop/loop_io_checks.py` (D-793, not in CHECKS) fails on Linux at the lead tip with or without this
  lane: `start_hidden still passes when neutralised`. Its window flag is Windows-only (HIDDEN-A); it is
  outside the thirteen and is left for the lead.
