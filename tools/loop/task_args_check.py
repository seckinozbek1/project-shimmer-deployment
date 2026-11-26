#!/usr/bin/env python3
"""A scheduled task whose command line still holds an unexpanded shell variable or names a path that does not exist
(beta item 26, OPEN_ITEMS 184, third paragraph).

Cause found on 23 November 2026: the task ShimmerUntScitabAfter was registered with the argument
`...\\external\\s05$d` (a shell variable that was never expanded, the folder name lost), so
external/s05/UNT_after_gated.pyw ran `launch.py after` with a working folder that does not exist; Python raised in
subprocess.run before any child started and pythonw exited 1, at 20:49 and 20:54 after the part had ended. By hand the
right folder was typed, so it delivered at once. ShimmerUntScitabPrepare and ShimmerUntContradocPrepare carry the same
`s05$d` (all three disabled since). Task Scheduler expands %NAME% itself and passes `$(name)` event values, so neither
is flagged; a `$name` it never expands is.

For each action of each task whose name starts with the prefix (default Shimmer):
- `variable`: a `$name` in Execute, Arguments or WorkingDirectory (not `$(name)`, not `$$`);
- `missing`: Execute, WorkingDirectory or a quoted or bare absolute path in Arguments (C:\\..., \\\\server\\...)
  that does not exist after %NAME% expansion.

    py -3.12 -X utf8 tools/loop/task_args_check.py [--prefix Shimmer] [--enabled-only]
prints one line per problem (task, state, field, the token) and exits 1 when there is one. Read-only: the task list is
read with Get-ScheduledTask; nothing is registered, changed or deleted. No credential is read.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mechanism_common as mc  # noqa: E402

VARIABLE = re.compile(r'(?<!\$)\$(?!\()(?!\$)([A-Za-z_][A-Za-z0-9_]*)')
QUOTED = re.compile(r'"([^"]*)"')
ABSOLUTE = re.compile(r'^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\)')
FIELDS = ('execute', 'arguments', 'working_directory')
TIMEOUT_S = 120


def _tokens(arguments):
    """The quoted strings, then the bare words outside quotes."""
    text = arguments or ''
    quoted = QUOTED.findall(text)
    bare = QUOTED.sub(' ', text).split()
    return quoted + bare


def problems(action, exists=None):
    """[(field, kind, token)] for one action {task, state, execute, arguments, working_directory}."""
    exists = exists or (lambda p: Path(p).exists())
    out = []
    for field in FIELDS:
        for m in VARIABLE.finditer(action.get(field) or ''):
            out.append((field, 'variable', '$' + m.group(1)))
    paths = []
    for field in ('execute', 'working_directory'):
        value = (action.get(field) or '').strip().strip('"')
        if value:
            paths.append((field, value))
    paths += [('arguments', t) for t in _tokens(action.get('arguments'))]
    for field, token in paths:
        expanded = os.path.expandvars(token) if '%' in token else token
        if ABSOLUTE.match(expanded) and not exists(expanded):
            out.append((field, 'missing', token))
    return out


def live_actions(prefix='Shimmer'):
    """[{task, state, execute, arguments, working_directory}] of the tasks whose name starts with prefix."""
    script = ("$ErrorActionPreference='Stop'; Get-ScheduledTask | Where-Object { $_.TaskName -like '%s*' } | "
              "ForEach-Object { $t=$_; $t.Actions | ForEach-Object { [pscustomobject]@{task=$t.TaskName; "
              "state=[string]$t.State; execute=$_.Execute; arguments=$_.Arguments; working_directory=$_.WorkingDirectory} } } "
              "| ConvertTo-Json -Depth 3" % prefix.replace("'", ''))
    done = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True,
                          text=True, timeout=TIMEOUT_S, creationflags=mc.no_window())
    if done.returncode != 0:
        raise RuntimeError('Get-ScheduledTask exit %d: %s' % (done.returncode, (done.stderr or '').strip()[-200:]))
    text = (done.stdout or '').strip()
    if not text:
        return []
    value = json.loads(text)
    return value if isinstance(value, list) else [value]


def report(actions, enabled_only=False, exists=None):
    """(lines, count) over the actions."""
    lines = []
    for a in actions:
        if enabled_only and str(a.get('state')) == 'Disabled':
            continue
        for field, kind, token in problems(a, exists):
            lines.append('%s (%s): %s %s %s' % (a.get('task'), a.get('state'), field,
                                                'holds an unexpanded' if kind == 'variable' else 'names a path that does not exist:',
                                                token))
    return lines, len(lines)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    prefix = 'Shimmer'
    if '--prefix' in args:
        i = args.index('--prefix')
        prefix = args[i + 1]
        del args[i:i + 2]
    lines, n = report(live_actions(prefix), enabled_only='--enabled-only' in args)
    for line in lines:
        print(line)
    print('task_args_check: %d problems in tasks named %s*' % (n, prefix))
    return 1 if n else 0


if __name__ == '__main__':
    raise SystemExit(main())
