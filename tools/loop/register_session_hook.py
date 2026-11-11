"""Register, or print, the Task Scheduler task that runs session_end_salvage.py (D-S107 item 3).

The task runs in Seckin's own session only (logon type InteractiveToken, least privilege): no
password is stored or asked for, and it runs only while he is logged on. It starts
`tools/loop/session_end_salvage.py --event-id <id>` through `pythonw.exe` (no window, HIDDEN-A)
on these events of the System log: User32 1074 (shutdown or restart initiated), Winlogon 7002
(logoff), Kernel-Power 42 (entering sleep) and Kernel-Power 506 (modern standby, a closed lid on
such laptops); and, with `--with-security-4647`, Security 4647 (user-initiated logoff), which a
standard user may not be able to subscribe to. The event id reaches the script through the
trigger's value query.

    py -3.12 -X utf8 tools/loop/register_session_hook.py --dry-run   # print the task XML only
    py -3.12 -X utf8 tools/loop/register_session_hook.py             # register it (schtasks /Create)

The registration is the one `schtasks /Create /TN ShimmerLoopSessionEnd /XML <file> /F` command,
run by the lead; nothing else is changed. The task always runs the MAIN checkout's script, found
through git's common directory, in the main checkout (D-412 item 4): registration is refused when
that script does not exist there, and when no pythonw.exe stands beside the interpreter (a console
python would open a window, D-412 item 9). Only one pass runs at a time (MultipleInstancesPolicy
IgnoreNew, beside the script's own lock). schtasks' own output and error are printed as they are. Removing it is `schtasks /Delete /TN
ShimmerLoopSessionEnd /F`.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from cloud_run_common import no_window  # noqa: E402
import session_end_salvage  # noqa: E402

TASK_NAME = 'ShimmerLoopSessionEnd'
LOGON_TYPE = 'InteractiveToken'
RUN_LEVEL = 'LeastPrivilege'
TIME_LIMIT = 'PT2M'
# (log, provider, event id): the events that end or suspend the session.
TRIGGERS = (
    ('System', 'User32', 1074),
    ('System', 'Microsoft-Windows-Winlogon', 7002),
    ('System', 'Microsoft-Windows-Kernel-Power', 42),
    ('System', 'Microsoft-Windows-Kernel-Power', 506),
)
SECURITY_TRIGGER = ('Security', 'Microsoft-Windows-Security-Auditing', 4647)


SCRIPT = Path('tools') / 'loop' / 'session_end_salvage.py'


class RegisterError(RuntimeError):
    pass


def windowless_python(executable=None):
    """pythonw.exe beside the running interpreter; refused when there is none (no console window)."""
    exe = Path(executable or sys.executable)
    candidate = exe if exe.name.lower() == 'pythonw.exe' else exe.with_name('pythonw.exe')
    if not candidate.exists():
        raise RegisterError('No pythonw.exe beside %s: the task would open a console window; not registered' % exe)
    return candidate


def main_script(root):
    """The main checkout's session_end_salvage.py; refused when it does not exist there."""
    script = Path(root) / SCRIPT
    if not script.is_file():
        raise RegisterError('%s does not exist in the main checkout %s: merge the hook there first; not registered'
                            % (SCRIPT.as_posix(), root))
    return script


def trigger_xml(log, provider, event_id):
    query = ('<QueryList><Query Id="0" Path="%s"><Select Path="%s">'
             "*[System[Provider[@Name='%s'] and EventID=%d]]</Select></Query></QueryList>"
             % (log, log, provider, event_id))
    return ('    <EventTrigger>\n      <Enabled>true</Enabled>\n      <Subscription>%s</Subscription>\n'
            '      <ValueQueries>\n        <Value name="eventId">Event/System/EventID</Value>\n'
            '      </ValueQueries>\n    </EventTrigger>\n' % escape(query))


def task_xml(user, python, script, root, with_security=False):
    triggers = list(TRIGGERS) + ([SECURITY_TRIGGER] if with_security else [])
    return ('<?xml version="1.0" encoding="UTF-16"?>\n'
            '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
            '  <RegistrationInfo>\n    <Description>Shimmer loop: salvage and stop every loop instance when the '
            'session ends (D-S107 item 3)</Description>\n  </RegistrationInfo>\n'
            '  <Triggers>\n' + ''.join(trigger_xml(*t) for t in triggers) + '  </Triggers>\n'
            '  <Principals>\n    <Principal id="Author">\n      <UserId>%s</UserId>\n'
            '      <LogonType>%s</LogonType>\n      <RunLevel>%s</RunLevel>\n    </Principal>\n  </Principals>\n'
            '  <Settings>\n    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n'
            '    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n'
            '    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n'
            '    <AllowStartOnDemand>true</AllowStartOnDemand>\n    <Enabled>true</Enabled>\n'
            '    <Hidden>true</Hidden>\n    <ExecutionTimeLimit>%s</ExecutionTimeLimit>\n'
            '    <Priority>4</Priority>\n  </Settings>\n'
            '  <Actions Context="Author">\n    <Exec>\n      <Command>%s</Command>\n'
            '      <Arguments>-X utf8 "%s" --event-id $(eventId)</Arguments>\n'
            '      <WorkingDirectory>%s</WorkingDirectory>\n    </Exec>\n  </Actions>\n</Task>\n'
            % (escape(user), LOGON_TYPE, RUN_LEVEL, TIME_LIMIT, escape(str(python)), escape(str(script)),
               escape(str(root))))


def current_user():
    domain, name = os.environ.get('USERDOMAIN', ''), os.environ.get('USERNAME', '')
    return ('%s\\%s' % (domain, name)) if domain else name


def register(xml, runner=subprocess.run):
    """The one schtasks call. Returns (exit code, its output, its error)."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'session_hook.xml'
        path.write_text(xml, encoding='utf-16')
        result = runner(['schtasks', '/Create', '/TN', TASK_NAME, '/XML', str(path), '/F'],
                        stdin=subprocess.DEVNULL, capture_output=True, text=True, creationflags=no_window())
    return result.returncode, (getattr(result, 'stdout', '') or '').strip(), (getattr(result, 'stderr', '') or '').strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Register the session-end salvage task (D-S107 item 3).')
    parser.add_argument('--dry-run', action='store_true', help='print the task XML and register nothing')
    parser.add_argument('--with-security-4647', action='store_true', help='also trigger on Security 4647')
    parser.add_argument('--user', help='the account the task runs as (default the current user)')
    parser.add_argument('--root', help='the main checkout (default: found through git from this script)')
    args = parser.parse_args(argv)
    try:
        root = session_end_salvage.checked_root(args.root) if args.root else session_end_salvage.main_root()
        xml = task_xml(args.user or current_user(), windowless_python(), main_script(root), root,
                       args.with_security_4647)
    except (RegisterError, session_end_salvage.HookError) as exc:
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
