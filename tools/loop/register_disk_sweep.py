"""Register, or print, the Task Scheduler task that runs tools/loop/disk_sweep.py (D-611, issue #266).

The task runs in Seckin's own session only (logon type InteractiveToken, least privilege, no password), once
a day at 04:30 local time, through `pythonw.exe` (no window, HIDDEN-A) as
`disk_sweep.py --apply`, in the MAIN checkout, found through git's common directory. It is also started on
demand: the loop's load watcher and every seal gate that reads free disk under 32 GiB call

    py -3.12 -X utf8 tools/loop/register_disk_sweep.py --run-now-if-low

which runs the registered task with `schtasks /Run` only when free disk is under 32 GiB (the 30 GiB floor of
D-099 plus a margin) and does nothing otherwise. One pass at a time (MultipleInstancesPolicy IgnoreNew, and
the sweep's own lock file).

    py -3.12 -X utf8 tools/loop/register_disk_sweep.py --dry-run   # print the task XML only
    py -3.12 -X utf8 tools/loop/register_disk_sweep.py             # register it (schtasks /Create), by the lead

Registration is the one `schtasks /Create /TN ShimmerLoopDiskSweep /XML <file> /F`; refused unless the main
checkout holds the script and a pythonw.exe stands beside the interpreter. Removing it is
`schtasks /Delete /TN ShimmerLoopDiskSweep /F`. This script never runs the sweep itself.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from cloud_run_common import no_window  # noqa: E402
import disk_sweep  # noqa: E402
import register_session_hook as hook  # noqa: E402

TASK_NAME = 'ShimmerLoopDiskSweep'
START_TIME = '04:30:00'
TIME_LIMIT = 'PT4H'
TRIGGER_GIB = 32
SCRIPT = Path('tools') / 'loop' / 'disk_sweep.py'


def main_script(root, must_exist=True):
    script = Path(root) / SCRIPT
    if must_exist and not script.is_file():
        raise hook.RegisterError('%s does not exist in the main checkout %s: merge the sweep there first; not registered'
                                 % (SCRIPT.as_posix(), root))
    return script


def task_xml(user, python, script, root, today=None):
    start = '%sT%s' % ((today or date.today()).isoformat(), START_TIME)
    return ('<?xml version="1.0" encoding="UTF-16"?>\n'
            '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
            '  <RegistrationInfo>\n    <Description>Shimmer loop: delete regenerable files by declared kinds, daily and '
            'when free disk is low (D-611, issue 266)</Description>\n  </RegistrationInfo>\n'
            '  <Triggers>\n    <CalendarTrigger>\n      <StartBoundary>%s</StartBoundary>\n      <Enabled>true</Enabled>\n'
            '      <ScheduleByDay>\n        <DaysInterval>1</DaysInterval>\n      </ScheduleByDay>\n'
            '    </CalendarTrigger>\n  </Triggers>\n'
            '  <Principals>\n    <Principal id="Author">\n      <UserId>%s</UserId>\n'
            '      <LogonType>%s</LogonType>\n      <RunLevel>%s</RunLevel>\n    </Principal>\n  </Principals>\n'
            '  <Settings>\n    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n'
            '    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n'
            '    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n'
            '    <StartWhenAvailable>true</StartWhenAvailable>\n'
            '    <AllowStartOnDemand>true</AllowStartOnDemand>\n    <Enabled>true</Enabled>\n'
            '    <Hidden>true</Hidden>\n    <ExecutionTimeLimit>%s</ExecutionTimeLimit>\n'
            '    <Priority>7</Priority>\n  </Settings>\n'
            '  <Actions Context="Author">\n    <Exec>\n      <Command>%s</Command>\n'
            '      <Arguments>-X utf8 "%s" --apply</Arguments>\n'
            '      <WorkingDirectory>%s</WorkingDirectory>\n    </Exec>\n  </Actions>\n</Task>\n'
            % (start, escape(user), hook.LOGON_TYPE, hook.RUN_LEVEL, TIME_LIMIT, escape(str(python)),
               escape(str(script)), escape(str(root))))


def schtasks(args, runner=subprocess.run):
    result = runner(['schtasks'] + args, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                    creationflags=no_window())
    return result.returncode, (getattr(result, 'stdout', '') or '').strip(), (getattr(result, 'stderr', '') or '').strip()


def register(xml, runner=subprocess.run):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'disk_sweep.xml'
        path.write_text(xml, encoding='utf-16')
        return schtasks(['/Create', '/TN', TASK_NAME, '/XML', str(path), '/F'], runner)


def run_now_if_low(root, free=shutil.disk_usage, runner=subprocess.run):
    """What the load watcher and the seal gates call: start the registered task only when free disk is under
    32 GiB. Returns (started, text)."""
    gib = free(str(root)).free / disk_sweep.GIB
    if gib >= TRIGGER_GIB:
        return False, 'free disk %.2f GiB is not under %d GiB; the sweep task was not started' % (gib, TRIGGER_GIB)
    code, out, err = schtasks(['/Run', '/TN', TASK_NAME], runner)
    return code == 0, 'free disk %.2f GiB: schtasks /Run %s exit %d %s' % (gib, TASK_NAME, code, (out or err))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Register the disk sweep task (D-611).')
    parser.add_argument('--dry-run', action='store_true', help='print the task XML and register nothing')
    parser.add_argument('--run-now-if-low', action='store_true',
                        help='start the registered task only when free disk is under 32 GiB (the load watcher and seal gates)')
    parser.add_argument('--user', help='the account the task runs as (default the current user)')
    args = parser.parse_args(argv)
    try:
        root = disk_sweep.main_root()
        if args.run_now_if_low:
            started, text = run_now_if_low(root)
            print(text)
            return 0 if (started or 'not under' in text) else 1
        script = main_script(root, must_exist=not args.dry_run)
        if args.dry_run and not script.is_file():
            print('NOTE: %s is not in the main checkout yet; registering is refused until it is merged there' % SCRIPT.as_posix())
        xml = task_xml(args.user or hook.current_user(), hook.windowless_python(), script, root)
    except (hook.RegisterError, disk_sweep.SweepError) as exc:
        print(str(exc))
        return 2
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
