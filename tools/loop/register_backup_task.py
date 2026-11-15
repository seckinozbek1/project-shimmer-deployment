"""Register, or print, the daily Task Scheduler task that runs tools/loop/backup_private.py (D-612).

Like register_session_hook.py: the task runs in the operator's own session only (InteractiveToken,
least privilege, no password), through pythonw.exe (no window, HIDDEN-A), in the MAIN checkout, once a
day (`DAILY_AT`), and when a start was missed it runs as soon as the session is back. It is only
printed by default tooling; registering is the one `schtasks /Create` call and is the lead's step.

    py -3.12 -X utf8 tools/loop/register_backup_task.py --dry-run   # print the task XML only
    py -3.12 -X utf8 tools/loop/register_backup_task.py             # register it (schtasks /Create)

Removing it is `schtasks /Delete /TN ShimmerBackupPrivate /F`.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from cloud_run_common import no_window  # noqa: E402
import register_session_hook as hook  # noqa: E402
import session_end_salvage  # noqa: E402

TASK_NAME = 'ShimmerBackupPrivate'
DAILY_AT = '04:30:00'
TIME_LIMIT = 'PT1H'
SCRIPT = Path('tools') / 'loop' / 'backup_private.py'


def task_xml(user, python, script, root, start='2026-11-14T%s' % DAILY_AT):
    return ('<?xml version="1.0" encoding="UTF-16"?>\n'
            '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
            '  <RegistrationInfo>\n    <Description>Shimmer: daily push of all branches and tags to the private '
            'backup repository (D-612)</Description>\n  </RegistrationInfo>\n'
            '  <Triggers>\n    <CalendarTrigger>\n      <StartBoundary>%s</StartBoundary>\n'
            '      <Enabled>true</Enabled>\n      <ScheduleByDay>\n        <DaysInterval>1</DaysInterval>\n'
            '      </ScheduleByDay>\n    </CalendarTrigger>\n  </Triggers>\n'
            '  <Principals>\n    <Principal id="Author">\n      <UserId>%s</UserId>\n'
            '      <LogonType>%s</LogonType>\n      <RunLevel>%s</RunLevel>\n    </Principal>\n  </Principals>\n'
            '  <Settings>\n    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n'
            '    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n'
            '    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n'
            '    <StartWhenAvailable>true</StartWhenAvailable>\n    <AllowStartOnDemand>true</AllowStartOnDemand>\n'
            '    <Enabled>true</Enabled>\n    <Hidden>true</Hidden>\n'
            '    <ExecutionTimeLimit>%s</ExecutionTimeLimit>\n    <Priority>7</Priority>\n  </Settings>\n'
            '  <Actions Context="Author">\n    <Exec>\n      <Command>%s</Command>\n'
            '      <Arguments>-X utf8 "%s"</Arguments>\n'
            '      <WorkingDirectory>%s</WorkingDirectory>\n    </Exec>\n  </Actions>\n</Task>\n'
            % (start, escape(user), hook.LOGON_TYPE, hook.RUN_LEVEL, TIME_LIMIT, escape(str(python)),
               escape(str(script)), escape(str(root))))


def register(xml, runner=subprocess.run):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'backup_task.xml'
        path.write_text(xml, encoding='utf-16')
        done = runner(['schtasks', '/Create', '/TN', TASK_NAME, '/XML', str(path), '/F'],
                      stdin=subprocess.DEVNULL, capture_output=True, text=True, creationflags=no_window())
    return done.returncode, (getattr(done, 'stdout', '') or '').strip(), (getattr(done, 'stderr', '') or '').strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Register the daily private backup task (D-612).')
    parser.add_argument('--dry-run', action='store_true', help='print the task XML and register nothing')
    parser.add_argument('--user', help='the account the task runs as (default the current user)')
    parser.add_argument('--root', help='the main checkout (default: found through git from this script)')
    args = parser.parse_args(argv)
    try:
        root = session_end_salvage.checked_root(args.root) if args.root else session_end_salvage.main_root()
        script = root / SCRIPT
        python = hook.windowless_python()
    except (hook.RegisterError, session_end_salvage.HookError) as exc:
        print(str(exc))
        return 2
    if not script.is_file():
        if not args.dry_run:
            print('%s does not exist in the main checkout %s: merge it there first; not registered' % (SCRIPT.as_posix(), root))
            return 2
        print('note: %s is not yet in the main checkout' % SCRIPT.as_posix(), file=sys.stderr)
    xml = task_xml(args.user or hook.current_user(), python, script, root)
    if args.dry_run:
        print(xml)
        return 0
    code, out, err = register(xml)
    print('schtasks /Create %s: exit %d' % (TASK_NAME, code))
    for text in (out, err):
        if text:
            print(text)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
