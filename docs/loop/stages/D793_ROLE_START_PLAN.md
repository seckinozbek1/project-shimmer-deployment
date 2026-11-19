# D-793 item 1: role starts by the loop, the permission plan (for the supervisor's review)

Written 2026-11-19 by lane role A (lane/d793-loop-io). Nothing here is applied: no settings or permission file was
written or changed. Until the supervisor approves and the lead adds the rule, the supervisor keeps doing the starts
(D-793 item 1).

## What the lead would run

One command, with one start-file name as its only argument:

    py -3.12 -X utf8 tools/loop/role_starter.py start start_<role>_<step>.cmd

`tools/loop/role_starter.py` itself refuses unless the name is a bare .cmd file in docs/loop/private/role_starts,
is listed in docs/loop/private/role_starts/ALLOWED_STARTS.json, passes tools/loop/role_start_check.py (PASS, exit 0),
is not already running, and fewer than two role sessions run (its own live marks plus cmd.exe processes naming a
start file in role_starts). It writes `<stem>.started`, `<stem>.log`, `<stem>.exit` and one line per start, refusal
and exit in docs/loop/private/session_results/role_starts.jsonl, and prints the FOR_SECKIN line for the lead.

## The exact permission to add

One allow rule in the lead's project settings (`permissions.allow`), for the shell tool the lead uses:

    Bash(py -3.12 -X utf8 tools/loop/role_starter.py start:*)

and, if the lead runs it through the PowerShell tool instead, the same rule for that tool:

    PowerShell(py -3.12 -X utf8 tools/loop/role_starter.py start:*)

Nothing else is widened. Claude Code judges each part of a chained command apart, so the rule does not admit
anything joined to it with `&&`, `;` or `|`. The `:*` admits any argument, and the tool's own allow-list is what
limits the argument to approved start files. The detached wrapper the tool starts (`role_starter.py _wrap NAME`) is
a child process, not a Claude command, so it needs no rule; it re-checks the allow-list before running the file.

The read-only commands `role_starter.py status`, `loop_requests.py list|overdue`, `loop_heartbeat.py check` and
`inbox_ids.py missing|unread|seen` and the writers `loop_requests.py new` and `loop_heartbeat.py beat` need allow
rules of the same form only if the lead's settings do not already admit `py -3.12 -X utf8 tools/loop/...`.

## Who edits the allow-list

The lead edits ALLOWED_STARTS.json (a JSON list of start-file names). That file is the second gate: the supervisor
can review it at any time, and a start file not on it is refused and recorded.

## Risks the supervisor may weigh

- A start file on the list can be changed after it is listed; role_start_check runs at every start, but it checks
  guards and the request commands against the role's settings, not the purpose of the file.
- The process check reads cmd.exe command lines through PowerShell Get-CimInstance; when that fails the limit is
  counted from this tool's marks only, and the start line says so.
- The wrapper asks Windows to break away from the caller's job so the role outlives the lead's shell; where the job
  forbids that it starts inside the job, and a role could then end with the lead's shell.
