# CHAIN_ADMIT_RETRY: a refused admission is a refused launch

Lane `lane/chain-admit-retry`, 19 November 2026 (written 20:48).

## What went wrong

`tools/loop/launch_chain.py` starts `launch.py admit`, which runs `tools/seal_route_driver.py admit` detached
(output to `admit.log`). Three times on 19 November the admission stopped at once, before anything was admitted:

- ROUTE_GATE_e958ecc4, 18:55: `loop_budget_guard.GuardRefusal: Another launch holds the ledger lock`;
- SYN_DEDUP_LEAD, 20:07: the same GuardRefusal;
- ROUTE_GATE_e958ecc4, 20:08: `seal_route.RouteError: No room for ... under the ledger lock ...; admit again`.

The chain never saw the exit (the process is detached), so once its window passed it marked the step "launch
begun, never confirmed by the evidence; held until --clear" and never tried again. The lead cleared each by hand.

## The fix

1. `tools/seal_route_driver.py` (not controller-bound: it is not in `prepare_ordinary_final_run.CONTROL_FILES`,
   so no bundle needs a re-seal):
   - `lock_refusal_is_retry` turns a GuardRefusal on the ledger lock into `AdmitRetry('ledger_lock')`; the gate
     under the lock (wrapped by `no_room_is_retry`) turns the no-room RouteError into `AdmitRetry('no_room')` (the staging folder is
     renamed aside as before, so the next admission is not blocked). `AdmitRetry` is a `RouteError`.
   - `admit_main` writes the admission's exit record `<out>.exit.json` (`admitted.exit.json`) every time:
     `exit_code`, `outcome` (`admitted`, `refused_retry`, `failed`), `kind`, the first 300 characters of the
     message, `pid`, start and end times. A retryable refusal exits **75** (`ADMIT_RETRY_EXIT`); any other failure
     is recorded `failed` and raised as before.
2. `tools/loop/launch_chain.py`:
   - the `launch_started` line of an admit records `admit_log_offset` (admit.log's size when this attempt began);
   - `admit_refusal` decides, for an admit with no admission folder whose latest action is this chain's launch:
     first the exit record of this attempt (same pid as the `started detached, pid N` line, else ended after the
     launch began), exit 75 and `refused_retry`; else, for a driver without the record, the last line admit.log
     gained after this attempt began, when it is the ledger-lock GuardRefusal or the no-room RouteError and no
     `N of N admitted` line came with it;
   - such a step is `held`; the pass writes a `guard_refused` trace line (kind admit), so the hold and retry of the
     guard refusal apply: tried again after `RETRY_MINUTES` (10), ALERT.md after 3 in a row
     (`in_a_row` skips an admission's own detached `launch` lines);
   - a detached admission that leaves no evidence of its own still goes launching, then unconfirmed until
     `--clear`, exactly as before. Another attempt's record or older log bytes are never read as this one's.

Request steps run in the foreground and were already retried (`launch_failed` is in HOLDING); ledger steps read a
GuardRefusal from their own controller log as before. The admission was the one gap.

## Proofs (check 517, `tools/loop/launch_chain_checks.py`)

Each neutralised, failed, restored, passed:

- `admit_refused_retried`: exit record and older-driver log, each held 10 minutes, retried, admitted, part follows;
- `admit_refused_three_alert`: three refused admissions in a row alert;
- `admit_silent_stays_unconfirmed`: no evidence stays unconfirmed; an old record (other pid) and old log bytes ignored;
- `driver_admit_exit`: exit 75 and `refused_retry` on a held lock, `failed` and raised on another refusal,
  `admitted` and 0 on success; the chain's constants equal the driver's.

## Note for the lead

Launch folders run the driver from the checkout their `launch.py` names. Until that checkout has this commit the
chain still recovers through the admit.log fallback, for attempts begun after this chain version is live (the
offset is recorded from then on). Steps held unconfirmed before that still need one `--clear`.
