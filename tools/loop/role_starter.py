"""Role starts by the loop, within limits (D-793 item 1, Seckin 19 November 2026 14:34).

    py -3.12 -X utf8 tools/loop/role_starter.py start START_FILE.cmd
    py -3.12 -X utf8 tools/loop/role_starter.py status

Everything lives in docs/loop/private/role_starts/ of the main checkout, found only through tools/loop/shared_paths.py.
`start` takes a bare file name in that folder and refuses, in one line, unless every condition holds:

1. the name is on the allow-list ALLOWED_STARTS.json in that folder (a JSON list of start-file names, or an object
   whose "allowed" is that list; the lead edits it, this tool only reads it);
2. tools/loop/role_start_check.py, run on that file from that folder, prints PASS and exits 0;
3. fewer than MAX_RUNNING (2) role sessions are running: the union of (a) this tool's `<stem>.started` marks with no
   `<stem>.exit` whose wrapper process is still alive and (b) cmd.exe processes whose command line names a start_*.cmd
   in that folder (the supervisor's own starts; skipped, and said so, when the process list cannot be read);
4. that same file is not already running.

On start it writes `<stem>.started` (time, pid of the wrapper, file), removes the previous run's `<stem>.exit` (the
history stays in role_starts.jsonl), and launches this same tool as a detached wrapper with no window (HIDDEN-A,
cloud_run_common.no_window). The wrapper re-checks the allow-list, runs `cmd /c <file>` hidden with stdout and stderr
appended to `<stem>.log`, and when it ends writes `<stem>.exit` (exit code, time). Each start, refusal and exit is one
JSON line in docs/loop/private/session_results/role_starts.jsonl (D-790). `start` prints a FOR_SECKIN line for the
lead to add (D-793: each start gets one line in FOR_SECKIN). It never edits a .cmd and never starts anything else; it
writes no settings or permission file.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
import shared_paths  # noqa: E402
from cloud_run_common import no_window  # noqa: E402

FOLDER = 'role_starts'
ALLOW = 'ALLOWED_STARTS.json'
RESULTS = ('session_results', 'role_starts.jsonl')
LOCK = 'role_starter.lock'
MAX_RUNNING = 2
CHECK = HERE / 'role_start_check.py'
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


class Refused(Exception):
    pass


def now():
    return dt.datetime.now().astimezone().replace(microsecond=0)


def private():
    return shared_paths.private_dir()


def folder():
    return private() / FOLDER


def record(entry):
    path = private().joinpath(*RESULTS)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(dict({'time': now().isoformat()}, **entry), ensure_ascii=False) + '\n')


def allowed(where):
    try:
        data = json.loads((where / ALLOW).read_text(encoding='utf-8-sig'))
    except OSError:
        raise Refused('no allow-list %s in role_starts' % ALLOW)
    except ValueError:
        raise Refused('%s is not valid JSON' % ALLOW)
    names = data.get('allowed') if isinstance(data, dict) else data
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise Refused('%s holds no list of start-file names' % ALLOW)
    return set(names)


def check_pass(path, runner=None):
    """(passed, first line) from role_start_check.py run on `path` from its folder."""
    runner = runner or subprocess.run
    try:
        done = runner([sys.executable, '-X', 'utf8', str(CHECK), str(path)], cwd=str(path.parent),
                      capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120,
                      stdin=subprocess.DEVNULL, creationflags=no_window())
    except (OSError, subprocess.SubprocessError) as exc:
        return False, 'role_start_check did not run (%s)' % type(exc).__name__
    first = ((done.stdout or '').splitlines() or [''])[0].strip()
    return done.returncode == 0 and first.startswith('PASS '), first or 'no output'


def pid_alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            ok = kernel.GetExitCodeProcess(handle, ctypes.byref(code))
            return bool(ok) and code.value == 259               # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_mark(path):
    out = {}
    try:
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            key, sep, value = line.partition(':')
            if sep:
                out[key.strip()] = value.strip()
    except OSError:
        pass
    return out


def marked_running(where, alive=None):
    """Stems with a .started mark, no .exit and a live wrapper pid."""
    alive = alive or pid_alive
    out = set()
    for mark in sorted(where.glob('*.started')):
        if (where / (mark.stem + '.exit')).exists():
            continue
        if alive(read_mark(mark).get('pid')):
            out.add(mark.stem)
    return out


def process_starts(where, runner=None):
    """Stems of start_*.cmd files in `where` that a running cmd.exe names, or None when the list cannot be read."""
    if os.name != 'nt':
        return set()
    runner = runner or subprocess.run
    script = ("Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" | "
              "ForEach-Object { $_.CommandLine }")
    try:
        done = runner(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True,
                      text=True, encoding='utf-8', errors='replace', timeout=60, stdin=subprocess.DEVNULL,
                      creationflags=no_window())
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    base = os.path.normcase(str(where))
    out = set()
    for line in (done.stdout or '').splitlines():
        low = os.path.normcase(line)
        if base not in low:
            continue
        for name in os.listdir(where):
            if name.lower().endswith('.cmd') and name.lower().startswith('start_') \
                    and os.path.normcase(str(where / name)) in low:
                out.add(Path(name).stem)
    return out


def running(where, alive=None, processes=None):
    """(stems running, note)."""
    marks = marked_running(where, alive)
    procs = (processes or process_starts)(where)
    if procs is None:
        return marks, 'process list not read; marks only'
    return marks | procs, ''


def take_lock(where):
    try:
        fd = os.open(str(where / LOCK), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        raise Refused('another start is being made (%s present)' % LOCK)
    os.write(fd, ('%s pid %d\n' % (now().isoformat(), os.getpid())).encode('ascii'))
    os.close(fd)


def launch(stem, where):
    """Start the detached, windowless wrapper; returns its pid."""
    cmd = [sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), '_wrap', stem + '.cmd']
    kwargs = dict(cwd=str(where), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                  close_fds=True)
    try:
        proc = subprocess.Popen(cmd, creationflags=no_window(CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB),
                                **kwargs)
    except OSError:                         # the job forbids breakaway: start inside it
        proc = subprocess.Popen(cmd, creationflags=no_window(CREATE_NEW_PROCESS_GROUP), **kwargs)
    return proc.pid


def start(name, runner=None, alive=None, processes=None, launcher=None):
    """(exit code, lines). Refusals are recorded and return 1."""
    where = folder()
    try:
        if Path(name).name != name or not name.lower().endswith('.cmd'):
            raise Refused('name a bare .cmd file in role_starts, not a path')
        path = where / name
        if not path.is_file():
            raise Refused('%s is not a file in role_starts' % name)
        if name not in allowed(where):
            raise Refused('%s is not on %s' % (name, ALLOW))
        take_lock(where)
        try:
            ok, first = check_pass(path, runner)
            if not ok:
                raise Refused('role_start_check did not pass: %s' % first)
            stems, note = running(where, alive, processes)
            if path.stem in stems:
                raise Refused('%s is already running' % name)
            if len(stems) >= MAX_RUNNING:
                raise Refused('%d role sessions running (%s), the limit is %d'
                              % (len(stems), ', '.join(sorted(stems)), MAX_RUNNING))
            try:
                (where / (path.stem + '.exit')).unlink()
            except FileNotFoundError:
                pass
            pid = (launcher or launch)(path.stem, where)
            at = now().isoformat()
            (where / (path.stem + '.started')).write_text('time: %s\npid: %s\nfile: %s\n' % (at, pid, name),
                                                          encoding='utf-8', newline='\n')
        finally:
            try:
                (where / LOCK).unlink()
            except FileNotFoundError:
                pass
    except Refused as exc:
        record({'event': 'refused', 'file': name, 'reason': str(exc)})
        return 1, ['REFUSED %s: %s' % (name, exc)]
    count = len(stems) + 1
    record({'event': 'start', 'file': name, 'pid': pid, 'check': first, 'running_after': count,
            'log': path.stem + '.log', 'note': note})
    return 0, ['STARTED %s pid %s (check: %s; running now %d of %d)%s' % (name, pid, first, count, MAX_RUNNING,
                                                                          '; ' + note if note else ''),
               'FOR_SECKIN: %s role start %s by the loop (D-793), pid %s, role_start_check PASS, %d of %d running; '
               'log role_starts/%s.log, exit file role_starts/%s.exit'
               % (at, name, pid, count, MAX_RUNNING, path.stem, path.stem)]


def wrap(name, runner=None):
    """The detached wrapper: run the start file hidden, log its output, write its exit file."""
    where = folder()
    stem = Path(name).stem
    if Path(name).name != name or name not in allowed(where):
        record({'event': 'wrap_refused', 'file': name})
        return 1
    runner = runner or subprocess.run
    with open(where / (stem + '.log'), 'a', encoding='utf-8', errors='replace') as log:
        log.write('--- start %s\n' % now().isoformat())
        log.flush()
        try:
            code = runner(['cmd', '/c', str(where / name)], cwd=str(where), stdin=subprocess.DEVNULL, stdout=log,
                          stderr=subprocess.STDOUT, creationflags=no_window()).returncode
        except OSError as exc:
            log.write('cannot run (%s)\n' % type(exc).__name__)
            code = -1
    at = now().isoformat()
    (where / (stem + '.exit')).write_text('exit %s %s\n' % (code, at), encoding='utf-8', newline='\n')
    record({'event': 'exit', 'file': name, 'exit': code})
    return 0


def status(alive=None, processes=None):
    where = folder()
    stems, note = running(where, alive, processes)
    lines = ['running %d of %d: %s%s' % (len(stems), MAX_RUNNING, ', '.join(sorted(stems)) or 'none',
                                         ' (%s)' % note if note else '')]
    for mark in sorted(where.glob('*.started')):
        info = read_mark(mark)
        ended = where / (mark.stem + '.exit')
        state = ended.read_text(encoding='utf-8', errors='replace').strip() if ended.exists() else (
            'running' if mark.stem in stems else 'no exit file and no live process')
        lines.append('  %s started %s pid %s: %s' % (mark.stem, info.get('time', '?'), info.get('pid', '?'), state))
    return lines


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(argv) == 2 and argv[0] == 'start':
            code, lines = start(argv[1])
        elif len(argv) == 2 and argv[0] == '_wrap':
            return wrap(argv[1])
        elif argv == ['status']:
            code, lines = 0, status()
        else:
            print('usage: role_starter.py start START_FILE.cmd | status')
            return 2
    except shared_paths.MainCheckoutError as exc:
        print(str(exc))
        return 2
    for line in lines:
        print(line)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
