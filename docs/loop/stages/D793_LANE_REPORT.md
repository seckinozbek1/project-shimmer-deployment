# D-793 lane report (role A, builder)

Branch `lane/d793-loop-io`, from 1b01c84c. Code commit cd4fa3e5746868884cde542dbb4fa39a097debcc; this report and
the permission plan are in the commit after it. Nothing pushed; no settings, permission, CLAUDE.md, README.md or
docs/RUNTIME_REFERENCE.md edited; scripts/verify_session1.py not run or touched; no role session started.

## Files

- `tools/loop/loop_requests.py`: `new` (prints the id), `list`, `overdue` over docs/loop/private/requests/.
- `tools/loop/loop_heartbeat.py`: `beat` writes LOOP_HEARTBEAT.txt, `check` reads both heartbeats.
- `tools/loop/inbox_ids.py`: `missing`, `unread`, `seen ID` over SUPERVISOR_INBOX.md, read-only.
- `tools/loop/role_starter.py`: `start NAME.cmd`, `status`, and the internal detached `_wrap`.
- `tools/loop/loop_io_checks.py`: 8 fixture proofs.
- `docs/loop/stages/D793_ROLE_START_PLAN.md`: the exact permission the lead would need, for the supervisor.

The main checkout is found only through `shared_paths.private_dir()`, called at use time; no personal path is in a
tracked file.

## How each item is proven

`py -3.12 -X utf8 tools/loop/loop_io_checks.py -v` prints PASS for 8 proofs. Each runs as built, then neutralised (must
differ), then restored (must match again), in a temporary folder with `shared_paths.private_dir` patched to it:

| proof | as built | neutralised by | neutralised result |
|---|---|---|---|
| requests_overdue | one OVERDUE line (the unanswered past request), exit 1; statuses answered, open, overdue | ACK prefix changed | two OVERDUE lines, the answered one now overdue |
| heartbeat_two_way | one line with the LEAD.lock session; 25 min old exits 1 (STALE), 5 min old exits 0; absent supervisor reported | STALE_MINUTES = 10**6 | old heartbeat exits 0, no STALE |
| inbox_ids | missing one entry, unread one id, seen exit codes 0/1/2; inbox bytes and mtime unchanged | id pattern that never matches | all three missing, seen gives 2 |
| start_allow_list | off-list name refused, never launched; wrapper refuses it; a path name refused | allow-list admits everything | started, wrapper ran cmd /c on it |
| start_check_pass | the real role_start_check on fixtures: PASS starts, FAIL (missing guard) refused | check_pass always PASS | the FAIL file is launched too |
| start_two_at_most | one live mark plus one supervisor cmd.exe process refuse a third; an exit file frees the slot; a running file is refused | MAX_RUNNING = 99 | the third starts |
| start_marks_and_log | .started (pid, file), old .exit removed, wrapper writes .log and `exit 3 ...`, jsonl start and exit, FOR_SECKIN line, lock removed | record() a no-op | no jsonl lines |
| start_hidden | the launch carries the no-window flag and starts only `role_starter.py _wrap NAME` | no_window returns flags unchanged | no-window bit missing |

Read-only smoke runs on the real private folder (from the worktree, through shared_paths): `inbox_ids.py seen
G-20261119-1437` prints read; `inbox_ids.py missing` lists 246 of 248 entries (all written before D-793);
`loop_heartbeat.py check` reports both heartbeats absent (exit 0); `loop_requests.py list` shows none;
`role_starter.py status` shows 0 of 2 running.

## Design choices the decision did not settle (simplest reading taken)

- Request ids count n from 1 within the minute; files are created exclusively. `--answer-in` defaults to 30 minutes.
  An ACK file answers by existence; its content is not read. A request whose header cannot be read counts as overdue.
- Heartbeat age comes from the first token of the first line (an ISO time), else the file's modification time.
  An absent loop heartbeat exits 0, as the brief says; only a present one over 20 minutes exits 1.
- `inbox_ids.py missing` lists every entry without an id, including the old ones; it exits 1 while any exist. If the
  lead wants only new entries checked, a `--newer-than` filter is a small follow-up.
- `seen ID` exits 0 read, 1 unread, 2 absent.
- Marks use the file stem: `start_n31.started`, `.log`, `.exit`. A new start removes the previous `.exit` (history
  stays in role_starts.jsonl); the log is appended with a `--- start` separator.
- Running sessions: this tool's live marks (wrapper pid alive, no exit file) plus cmd.exe processes whose command line
  names a start_*.cmd in role_starts (the supervisor's starts). When the process list cannot be read, the start goes
  ahead on marks alone and says so. A lock file stops two starts racing.
- D-793 asks for one FOR_SECKIN line per start. The tool prints that line (`FOR_SECKIN: ...`) and records the start in
  role_starts.jsonl; the lead adds it to FOR_SECKIN, since that file is the lead's own.
- Refusals and exits are recorded in role_starts.jsonl too (D-790: no result only in a terminal).

## What could not be done here

- The permission itself is not added (by the brief); see D793_ROLE_START_PLAN.md.
- A real detached start was not run (by the brief). The breakaway-from-job flag is tried first, with a fallback
  without it; whether the role outlives the lead's shell on this host is seen only on the first real start.
- No gate check number was assigned; scripts/verify_session1.py was not touched. The lead can wire
  `loop_io_checks.run_all` in as a check.

## Lines for the lead to add

CLAUDE.md (feature block list):

- LOOP-IO-A (D-793, Seckin 19 November 2026 14:34): request files REQ-<YYYYMMDD-HHMM>-<n>.md with answer-by times and ACK files in docs/loop/private/requests (tools/loop/loop_requests.py, `overdue` exits 1), two-way heartbeats (tools/loop/loop_heartbeat.py, `beat` at least every 15 minutes, `check` exits 1 over 20), an id on every SUPERVISOR_INBOX entry (tools/loop/inbox_ids.py, read-only), and role starts only through tools/loop/role_starter.py: allow-listed start files with a role_start_check PASS, at most two at once, each with a started mark, a log, an exit file and a role_starts.jsonl line; no self-restart (proofs: tools/loop/loop_io_checks.py)

STANDING_ORDERS:

- D-793 (Seckin 19 November 2026 14:34): the lead runs `loop_heartbeat.py beat` at least every 15 minutes and `loop_requests.py overdue` at every wake; it starts a role session only with `role_starter.py start` on an allow-listed start file (role_start_check PASS, at most two at once) and adds the printed FOR_SECKIN line; until the permission in docs/loop/stages/D793_ROLE_START_PLAN.md is approved and added, the supervisor makes the starts; the loop never restarts itself.
