"""Proofs for tools/loop/fs_trim.py (D-827), on fixtures only: fs_listing's fake provider and fake key
generator, a fake ssh that plays the remote trim script's outputs, and a fake clock in a temporary folder; no
network, no real ledger, no instance. Each proof is run as built (passes), neutralised (must fail), restored
(passes again).

    py -3.12 -X utf8 tools/loop/fs_trim_checks.py
"""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fs_trim as ft  # noqa: E402
import fs_listing_checks as flc  # noqa: E402  (its fake provider, clock, key generator and ledger helpers)

A = 'projects/project-' + 'a' * 64 + '.tar.gz'
B = 'projects/project-' + 'b' * 64 + '.tar.gz'
C = 'projects/project-' + 'c' * 64 + '.tar.gz'
D = 'projects/project-' + 'd' * 64 + '.tar.gz'
E = 'projects/project-' + 'e' * 64 + '.tar.gz'
GOOD = [dict(path=A, bytes=100), dict(path=B, bytes=200), dict(path=C, bytes=300), dict(path=D, bytes=400),
        dict(path=E, bytes=500)]
DF = '1B-blocks Used Avail Mounted on\n'
DF_SIZE = 9_223_372_036_854_775_808               # the size the real mount reports


class FakeSsh:
    """Plays the remote script on a fake mount: {path: ('file', size) | ('link', size) | ('dir', 0)}. It reads
    the entries back from the script's one printf, so it checks the script carries them."""

    def __init__(self, mount, trim_rc=0, cut_after=None, stop_after=None, cut_rc=None, argv_limit=None,
                 stdin_cut=None, drop_list_line=False):
        self.mount, self.trim_rc, self.remote, self.commands = dict(mount), trim_rc, [], []
        self.cut_after, self.stop_after = cut_after, stop_after   # a local timeout, the remote time budget
        self.cut_rc = cut_rc                                      # a cut by a lost connection instead
        self.argv_limit = argv_limit        # the Windows ssh client cuts a long command line (20 Nov 10:06)
        self.stdin_cut = stdin_cut          # standard input cut short (must never run a partial script)
        self.drop_list_line = drop_list_line  # the temporary list file one line short

    def __call__(self, argv, timeout, data=None):
        assert argv[0] == 'ssh' and argv[-2] == 'ubuntu@192.0.2.10', argv
        command = argv[-1]
        self.commands.append(command)
        if command == 'true':
            return subprocess.CompletedProcess(argv, 0, b'', b'')
        if command == 'bash -s':
            script = data.decode('utf-8')
            self.remote.append(script)
            if self.stdin_cut is not None:
                script = script[:self.stdin_cut]
        else:
            assert data is None, 'a command-line script with standard input too'
            self.remote.append(command)
            script = command[:self.argv_limit] if self.argv_limit is not None else command
        if self.trim_rc != 0:
            return subprocess.CompletedProcess(argv, self.trim_rc, b'', b'ssh: connect failed\n')
        if script.startswith('{ ') and not script.endswith('; }\n'):
            # bash parses a brace group whole before running it: a cut group is a syntax error, nothing runs
            return subprocess.CompletedProcess(argv, 2, b'', b'bash: line 1: syntax error: unexpected end of file\n')
        assert re.search(r'end=\$\(\( \$\(date -u \+%s\) \+ (\d+) \)\)', script), script
        used = 10_000 + sum(s for kind, s in self.mount.values())
        out = ['== df before', DF.strip(), '%d %d %d /home/ubuntu/shimmer-filesystem' % (DF_SIZE, used, DF_SIZE - used)]
        found = re.search(r"printf '%s %s\\n' (.*?) > \"\$list\"", script)
        if found is None:
            # the script ends inside the printf (its redirect cut off): printf writes its words to stdout, a
            # missing last argument as empty, and the shell ends there with exit 0, as on 20 Nov 10:06
            words = script.split("printf '%s %s\\n' ", 1)[1].split(' ')
            words += [''] * (len(words) % 2)
            out += ['%s %s' % pair for pair in zip(words[0::2], words[1::2])]
            return subprocess.CompletedProcess(argv, 0, ('\n'.join(out) + '\n').encode('utf-8'), b'')
        words = found.group(1).split(' ')
        pairs = list(zip(words[0::2], words[1::2]))
        written = len(pairs) - (1 if self.drop_list_line else 0)
        out += ['== list', str(written)]
        declared = re.search(r'if \[ "\$n" -ne (\d+) \]; then echo \'LIST_SHORT\'; exit 6; fi', script)
        if declared is not None and int(declared.group(1)) != written:
            out.append('LIST_SHORT')
            return subprocess.CompletedProcess(argv, 6, ('\n'.join(out) + '\n').encode('utf-8'), b'')
        out.append('== trim')
        for n, (path, size) in enumerate(pairs):
            if self.stop_after is not None and n == self.stop_after:
                out.append('STOPPED_AT_TIME')
                break
            out.append('TRY\t%s\t%s\t%d' % (path, size, 1_800_000_000 + 7 * n))
            if self.cut_after is not None and n == self.cut_after:
                partial = ('\n'.join(out) + '\n').encode('utf-8')
                if self.cut_rc is not None:
                    return subprocess.CompletedProcess(argv, self.cut_rc, partial, b'Connection closed\n')
                # subprocess.run kills ssh at the timeout and attaches what it had read
                raise subprocess.TimeoutExpired(argv, timeout, output=partial, stderr=b'')
            kind = self.mount.get(path)
            if kind is None:
                out.append('SKIP_MISSING\t%s\t%s' % (path, size))
            elif kind[0] == 'link':
                out.append('SKIP_LINK\t%s\t%s' % (path, size))
            elif kind[0] == 'dir':
                out.append('SKIP_NOT_FILE\t%s\t%s' % (path, size))
            elif str(kind[1]) != size:
                out.append('SKIP_SIZE\t%s\t%s\t%s' % (path, size, kind[1]))
            else:
                del self.mount[path]
                out.append('DELETED\t%s\t%s' % (path, size))
        out += ['== trim end', str(1_800_000_000 + 7 * len(pairs))]
        used = 10_000 + sum(s for kind, s in self.mount.values())
        out += ['== df after', DF.strip(), '%d %d %d /home/ubuntu/shimmer-filesystem' % (DF_SIZE, used, DF_SIZE - used)]
        return subprocess.CompletedProcess(argv, 0, ('\n'.join(out) + '\n').encode('utf-8'), b'')


MOUNT = {A: ('file', 100), B: ('file', 999), C: ('link', 300), E: ('dir', 0)}   # D is missing


def launch(base, entries=GOOD, ssh=None, provider=None, **kw):
    ledger = base / 'budget_ledger.jsonl'
    if not ledger.exists():
        flc.open_ledger(ledger)
    provider = flc.FakeProvider(ledger) if provider is None else provider
    ssh = FakeSsh(MOUNT) if ssh is None else ssh
    keys = base / 'keys'
    keys.mkdir(exist_ok=True)
    result = ft.execute(list(entries), provider=provider, ssh=ssh, keygen=flc.fake_keygen, clock=flc.Clock(),
                        ledger=ledger, reaped=[ledger], out_dir=base / 'out', key_dir=keys,
                        keep_awake=lambda action: False, now_name='20261120t120000', **kw)
    return result, provider, ssh, ledger


def cli(argv):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            return ft.main(argv)
        except SystemExit as exc:
            return exc.code


HEX = 'f' * 64
BAD_PATHS = (
    'project-%s.tar.gz' % HEX,                                  # at the mount root
    'assets-%s.tar' % HEX, 'assets-x.tar.gz',                   # never-touch asset archives
    'image/env-%s.tar.gz' % HEX, 'image/project-%s.tar.gz' % HEX,  # never-touch layers
    'outputs/project-%s.tar.gz' % HEX,                          # outside projects/
    'projects/../assets-%s.tar' % HEX, 'projects/..', 'projects/project-..%s.tar.gz' % HEX,  # dot-dot
    'projects/sub/project-%s.tar.gz' % HEX, 'projects//project-%s.tar.gz' % HEX,  # below projects/
    'projects/project-*.tar.gz', 'projects/project-?%s.tar.gz' % HEX, 'projects/project-[a]%s.tar.gz' % HEX,
    'projects/project-{a,b}.tar.gz', 'projects/~', 'projects/project-%s.tar.gz\\x' % HEX,  # wildcards
    'projects/assets-%s.tar.gz' % HEX,                          # an assets name under projects/
    'projects/project-%s.tar.gz;rm -rf x' % HEX, 'projects/$(id).tar.gz', 'projects/`id`.tar.gz',
    "projects/project-%s'.tar.gz" % HEX, 'projects/project-%s .tar.gz' % HEX, 'projects/a\nb',
    'projects/-rf', 'projects/', 'projects/project-%s.tar' % HEX, 'projects/project-XYZ.tar.gz',
    'projects/notes.txt', '/home/ubuntu/shimmer-filesystem/projects/project-%s.tar.gz' % HEX,
)
BAD_ENTRIES = ([], 'not a list', [dict(path=A)], [dict(path=A, bytes=0)], [dict(path=A, bytes=-1)],
               [dict(path=A, bytes=True)], [dict(path=A, bytes=1.5)], [dict(path=A, bytes='100')],
               [dict(path=A, bytes=1, extra=1)], [dict(path=A, bytes=1), dict(path=A, bytes=1)],
               [dict(path='projects/project-%064x.tar.gz' % i, bytes=1) for i in range(201)])


def proof_validator_refuses_each_bad_path_class(base):
    for bad in BAD_PATHS:
        try:
            ft.validate_list([dict(path=A, bytes=1), dict(path=bad, bytes=1)])
        except ft.TrimRefusal:
            pass
        else:
            raise AssertionError('path admitted: %r' % bad)
    for bad in BAD_ENTRIES:
        try:
            ft.validate_list(bad)
        except ft.TrimRefusal:
            pass
        else:
            raise AssertionError('list admitted: %r' % (bad if len(str(bad)) < 100 else 'long list'))
    # the command line refuses a bad list before any provider call, exit 2
    bad_file = base / 'bad.json'
    bad_file.write_text(json.dumps([dict(path='assets-%s.tar' % HEX, bytes=1)]), encoding='utf-8')
    assert cli(['--list', str(bad_file)]) == 2
    assert cli(['--list', str(bad_file), '--execute']) == 2
    ledger = base / 'budget_ledger.jsonl'
    flc.open_ledger(ledger)
    provider = flc.FakeProvider(ledger)
    try:
        launch(base, entries=[dict(path=A, bytes=1), dict(path='image/x', bytes=1)], provider=provider)
    except ft.TrimRefusal:
        pass
    else:
        raise AssertionError('a never-touch path reached the launch')
    assert provider.calls == [] and flc.events(ledger) == []
    # 200 good entries are admitted
    many = [dict(path='projects/project-%064x.tar.gz' % i, bytes=i + 1) for i in range(200)]
    assert len(ft.validate_list(many)) == 200
    assert ft.validate_list(GOOD[:2]) == GOOD[:2]


EXPECTED_TWO = (
    "{ set -u; test -d /home/ubuntu/shimmer-filesystem/projects || { echo 'projects absent'; exit 3; }; "
    "if test -L /home/ubuntu/shimmer-filesystem/projects; then echo 'projects is a link'; exit 4; fi; "
    "echo '== df before'; timeout 120 df -B1 --output=size,used,avail,target /home/ubuntu/shimmer-filesystem; "
    "end=$(( $(date -u +%s) + 600 )); list=$(mktemp) || exit 5; "
    "printf '%s %s\\n' " + A + " 100 " + B + " 200 > \"$list\"; n=$(wc -l < \"$list\"); echo '== list'; "
    "echo \"$n\"; if [ \"$n\" -ne 2 ]; then echo 'LIST_SHORT'; exit 6; fi; "
    "echo '== trim'; while read -r p b; do "
    "if [ \"$(date -u +%s)\" -ge \"$end\" ]; then echo 'STOPPED_AT_TIME'; break; fi; "
    "f=/home/ubuntu/shimmer-filesystem/\"$p\"; printf 'TRY\\t%s\\t%s\\t%s\\n' \"$p\" \"$b\" \"$(date -u +%s)\"; "
    "if test -L \"$f\"; then printf 'SKIP_LINK\\t%s\\t%s\\n' \"$p\" \"$b\"; "
    "elif ! test -e \"$f\"; then printf 'SKIP_MISSING\\t%s\\t%s\\n' \"$p\" \"$b\"; "
    "elif ! test -f \"$f\"; then printf 'SKIP_NOT_FILE\\t%s\\t%s\\n' \"$p\" \"$b\"; "
    "else s=$(timeout 60 stat -c %s -- \"$f\" 2>/dev/null || echo unknown); "
    "if [ \"$s\" != \"$b\" ]; then printf 'SKIP_SIZE\\t%s\\t%s\\t%s\\n' \"$p\" \"$b\" \"$s\"; "
    "else timeout 300 rm -f -- \"$f\"; r=$?; "
    "if ! test -e \"$f\" && ! test -L \"$f\"; then printf 'DELETED\\t%s\\t%s\\n' \"$p\" \"$b\"; "
    "else printf 'FAILED\\t%s\\t%s\\t%s\\n' \"$p\" \"$b\" \"$r\"; fi; fi; fi; "
    "done < \"$list\"; rm -f -- \"$list\"; echo '== trim end'; date -u +%s; "
    "echo '== df after'; timeout 120 df -B1 --output=size,used,avail,target /home/ubuntu/shimmer-filesystem; }\n")


def proof_script_holds_only_pinned_commands_and_names(base):
    script = ft.trim_script(GOOD[:2], 600)
    assert script == EXPECTED_TWO, script
    for bad in (10, 0, -5, 3601, 600.0, '600', True, '600; rm -rf /'):   # the time slot takes a bounded int only
        try:
            ft.trim_script(GOOD[:2], bad)
        except ft.TrimRefusal:
            continue
        raise AssertionError('time budget admitted: %r' % (bad,))
    # take the filled templates out: only the validated names and their bytes remain
    assert script.startswith(ft.WRAP[0]) and script.endswith(ft.WRAP[1])
    rest = script[len(ft.WRAP[0]):-len(ft.WRAP[1])]
    mount = '/home/ubuntu/shimmer-filesystem'
    for t in (ft.HEADER, ft.DF_BEFORE, ft.LOOP, ft.DF_AFTER):
        piece = t.format(mount=mount)
        assert rest.count(piece) == 1, t
        rest = rest.replace(piece, '')
    head, middle = ft.LIST.split('{seconds}')
    middle, tail = middle.split('{entries}')
    tail, end = tail.split('{count}')
    for piece in (head, middle, tail, end):
        assert rest.count(piece) == 1, piece
        rest = rest.replace(piece, ' ')
    rest = rest.replace(';', ' ').split()
    assert rest == ['600', A, '100', B, '200', '2'], rest
    # no recursive or wildcard deletion anywhere in the command set
    for banned in ('rm -r', 'rm -fr', 'rm -rf', 'rm -R', 'rm -f -r', '-delete', 'find ', 'xargs', 'rm -f -- *', 'eval', '$(cat'):
        assert banned not in script, banned
    assert script.count('rm -f -- ') == 2       # the exact file and the temporary list file
    # the remote command run is exactly that script
    result, provider, ssh, ledger = launch(base, entries=GOOD[:2])
    trim = [p for p in result['phases'] if p['phase'] == 'trim'][0]
    assert trim['remote_seconds'] == trim['timeout_seconds'] - ft.STOP_MARGIN_SECONDS, trim
    assert ssh.remote == [ft.trim_script(GOOD[:2], trim['remote_seconds'])], ssh.remote
    assert set(ssh.commands) == {'true', 'bash -s'}, ssh.commands


def proof_templates_pin(base):
    assert ft.pinned() and ft.templates_digest() == ft.TEMPLATES_SHA256
    for altered in (ft.TEMPLATES[:3] + (ft.LOOP.replace('rm -f --', 'rm -rf --'),) + ft.TEMPLATES[4:],
                    ft.TEMPLATES + ('cat {mount}/secret.txt',)):
        assert ft.templates_digest(templates=altered) != ft.TEMPLATES_SHA256
    old = ft.LOOP
    ft.LOOP = old.replace('rm -f --', 'rm -rf --')
    ft.TEMPLATES = (ft.HEADER, ft.DF_BEFORE, ft.LIST, ft.LOOP, ft.DF_AFTER)
    try:
        try:
            ft.trim_script(GOOD[:2], 600)
        except ft.TrimRefusal as exc:
            assert 'pinned digest' in str(exc), exc
        else:
            raise AssertionError('an altered command set was admitted')
        good = base / 'good.json'
        good.write_text(json.dumps(GOOD[:2]), encoding='utf-8')
        assert cli(['--list', str(good)]) == 2
    finally:
        ft.LOOP = old
        ft.TEMPLATES = (ft.HEADER, ft.DF_BEFORE, ft.LIST, ft.LOOP, ft.DF_AFTER)
    for argv in (['--list', 'x', '--command', 'ls'], ['--list', 'x', '--script', 'x'], ['--li', 'x']):
        assert cli(argv) == 2, argv


def proof_simulated_run_summary(base):
    result, provider, ssh, ledger = launch(base)
    assert result['status'] == 'failed' or result['status'] == 'trimmed', result
    folder = Path(result['folder'])
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    assert summary['deleted_count'] == 1 and summary['deleted_bytes'] == 100, summary
    assert summary['skips_by_reason'] == {'SKIP_SIZE': 1, 'SKIP_LINK': 1, 'SKIP_MISSING': 1, 'SKIP_NOT_FILE': 1}, summary
    assert [r['outcome'] for r in summary['rows']] == ['DELETED', 'SKIP_SIZE', 'SKIP_LINK', 'SKIP_MISSING',
                                                       'SKIP_NOT_FILE'], summary['rows']
    assert summary['rows'][1]['found'] == '999'
    assert summary['df_before']['used'] - summary['df_after']['used'] == 100 == summary['freed_bytes_by_df']
    assert summary['unreported'] == [] and summary['unexpected_lines'] == []
    assert result['status'] == 'trimmed', result
    assert flc.events(ledger) == ['launch_intent', 'launch', 'termination'], flc.events(ledger)
    intent, line, end = [r for r in flc.rows(ledger) if r['event'] != 'budget_open']
    for r in (intent, line, end):
        assert r['instance_name'] == 'shimmer-loop-fs-trim-20261120t120000' and r['purpose'] == 'fs-trim', r
    deadline = ft.guard.instance_reaper.parse_time(intent['deadline_utc']).timestamp()
    assert 0 < deadline - flc.START <= 30 * 60
    assert json.loads((folder / 'entries.json').read_text(encoding='utf-8')) == GOOD
    # an output line for a path not on the list, or a missing outcome, fails the run (still terminated)
    text = (folder / 'trim.txt').read_text(encoding='utf-8')
    odd = ft.summarise(text.replace('== trim end', 'DELETED\tprojects/other.tar.gz\t1\n== trim end'), GOOD)
    assert odd['unexpected_lines'] == ['DELETED\tprojects/other.tar.gz\t1'] and odd['complete'] is False, odd
    short = ft.summarise('\n'.join(l for l in text.splitlines() if not l.startswith('DELETED')), GOOD)
    assert short['unreported'] == [A] and short['in_flight'] == [A] and short['deleted_count'] == 0, short
    assert summary['complete'] is True and summary['tried'] == 5 and summary['slowest_file_seconds'] == 7, summary


def proof_partial_run_is_never_unknown(base):
    # the 20 Nov case: the remote command's ssh call times out after two files; what it had read is kept
    result, provider, ssh, ledger = launch(base, ssh=FakeSsh(MOUNT, cut_after=2))
    assert result['status'] == 'failed' and 'ran past its time' in result['failure']['message'], result
    folder = Path(result['folder'])
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    assert (folder / 'trim.txt').read_bytes().startswith(b'== df before'), 'partial output not saved'
    assert summary['cut_by_local_timeout'] is True and summary['complete'] is False, summary
    assert summary['deleted_count'] == 1 and summary['deleted_bytes'] == 100, summary
    assert summary['skips_by_reason'] == {'SKIP_SIZE': 1}, summary
    assert summary['in_flight'] == [C] and summary['not_tried'] == [D, E], summary
    assert result['summary']['deleted_count'] == 1 and result['summary']['in_flight'] == [C], result['summary']
    trim = [p for p in result['phases'] if p['phase'] == 'trim'][0]
    assert trim['timed_out'] is True and trim['returncode'] is None, trim
    assert provider.status == 'terminated' and result['termination_confirmed'], result
    assert flc.events(ledger) == ['launch_intent', 'launch', 'termination'], flc.events(ledger)
    # the remote loop stops itself at its time budget: nothing in flight, the rest untouched, df after printed
    second = base / 'second'
    second.mkdir()
    result, provider, ssh, ledger = launch(second, ssh=FakeSsh(MOUNT, stop_after=3))
    summary = json.loads((Path(result['folder']) / 'summary.json').read_text(encoding='utf-8'))
    assert result['status'] == 'failed' and 'time budget' in result['failure']['message'], result
    assert summary['stopped_at_time'] is True and summary['in_flight'] == [] and summary['not_tried'] == [D, E]
    assert summary['deleted_count'] == 1 and summary['df_after'] is not None, summary
    # the connection lost after two files (ssh exit 255 with part of the output): the lines are kept too
    third = base / 'third'
    third.mkdir()
    result, provider, ssh, ledger = launch(third, ssh=FakeSsh(MOUNT, cut_after=2, cut_rc=255))
    summary = json.loads((Path(result['folder']) / 'summary.json').read_text(encoding='utf-8'))
    assert result['status'] == 'failed' and 'exited 255' in result['failure']['message'], result
    assert summary['deleted_count'] == 1 and summary['in_flight'] == [C] and summary['not_tried'] == [D, E], summary
    assert provider.status == 'terminated' and result['termination_confirmed'], result


LONG = [dict(path='projects/project-%064x.tar.gz' % (0x9e3779b97f4a7c15 * (i + 1)), bytes=131_947_000 + 37 * i)
        for i in range(90)]                         # the 20 Nov 10:06 shape: 90 entries, 64-hex names, 9 digits
WINDOWS_SSH_LIMIT = 8191


def command_line_transport(base, script):
    """The 20 Nov 10:06 transport: the whole script as the ssh command argument."""
    return base + [script], None


def proof_long_list_arrives_whole(base):
    script = ft.trim_script(LONG, 810)
    assert len(script) > WINDOWS_SSH_LIMIT + 1000, len(script)
    mount = {e['path']: ('file', e['bytes']) for e in LONG}
    # (a) the 10:06 failure reproduced: the script on the command line (unwrapped, as then), cut by the
    # Windows ssh client near 8 KB inside the printf; df and entry lines on stdout, exit 0, no == trim line
    saved = ft.remote_call, ft.WRAP, ft.pinned, ft.MAX_COMMAND_CHARS
    ft.remote_call, ft.WRAP, ft.pinned, ft.MAX_COMMAND_CHARS = command_line_transport, ('', ''), lambda: True, 10 ** 6
    try:
        old = base / 'old'
        old.mkdir()
        ssh = FakeSsh(mount, argv_limit=WINDOWS_SSH_LIMIT)
        result, provider, _, ledger = launch(old, entries=LONG, ssh=ssh)
    finally:
        ft.remote_call, ft.WRAP, ft.pinned, ft.MAX_COMMAND_CHARS = saved
    text = (Path(result['folder']) / 'trim.txt').read_text(encoding='utf-8')
    lines = text.splitlines()
    assert lines[0] == '== df before' and '== trim' not in lines and '== list' not in lines, lines[:5]
    entry_lines = [l for l in lines if l.startswith('projects/project-')]
    last = LONG[len(entry_lines) - 1]
    assert 60 <= len(entry_lines) < 90, len(entry_lines)
    assert entry_lines[-1] != '%s %d' % (last['path'], last['bytes']), entry_lines[-1]   # stops mid-entry
    summary = json.loads((Path(result['folder']) / 'summary.json').read_text(encoding='utf-8'))
    assert summary['reached_trim'] is False and summary['list_lines'] is None and summary['tried'] == 0, summary
    assert summary['deleted_count'] == 0 and len(summary['not_tried']) == 90 and summary['complete'] is False
    assert result['status'] == 'failed' and 'before its trim step' in result['failure']['message'], result
    assert 'nothing was deleted' in result['failure']['message'] and ssh.mount == mount
    assert provider.status == 'terminated' and result['termination_confirmed'], result
    # (b) as built: the script on standard input to `bash -s`, the same client limit has nothing to cut
    new = base / 'new'
    new.mkdir()
    ssh = FakeSsh(mount, argv_limit=WINDOWS_SSH_LIMIT)
    result, provider, _, ledger = launch(new, entries=LONG, ssh=ssh)
    trim = [p for p in result['phases'] if p['phase'] == 'trim'][0]
    assert trim['remote_command'] == 'bash -s' and trim['script_bytes'] > WINDOWS_SSH_LIMIT, trim
    assert set(ssh.commands) == {'true', 'bash -s'} and all(len(c) <= ft.MAX_COMMAND_CHARS for c in ssh.commands)
    assert result['status'] == 'trimmed', result
    summary = json.loads((Path(result['folder']) / 'summary.json').read_text(encoding='utf-8'))
    assert summary['complete'] and summary['list_lines'] == 90 and summary['deleted_count'] == 90, summary
    assert [r['path'] for r in summary['rows']] == [e['path'] for e in LONG] and ssh.mount == {}
    # (c) standard input cut short: the brace group is a syntax error, nothing runs, the run refuses
    third = base / 'third'
    third.mkdir()
    ssh = FakeSsh(mount, stdin_cut=5000)
    result, provider, _, ledger = launch(third, entries=LONG, ssh=ssh)
    assert result['status'] == 'failed' and 'exited 2' in result['failure']['message'], result
    assert ssh.mount == mount and result['summary']['tried'] == 0, result['summary']
    # (d) the list file one line short: LIST_SHORT before the loop, a clear refusal, nothing touched
    fourth = base / 'fourth'
    fourth.mkdir()
    ssh = FakeSsh(mount, drop_list_line=True)
    result, provider, _, ledger = launch(fourth, entries=LONG, ssh=ssh)
    assert result['status'] == 'failed' and 'LIST_SHORT' in result['failure']['message'], result
    assert '89 lines for 90 entries' in result['failure']['message'] and ssh.mount == mount, result
    # the command-line guard: a script on the ssh argument is refused before it is sent
    fifth = base / 'fifth'
    fifth.mkdir()
    saved = ft.remote_call
    ft.remote_call = command_line_transport
    try:
        ssh = FakeSsh(mount)
        result, provider, _, ledger = launch(fifth, entries=LONG, ssh=ssh)
    finally:
        ft.remote_call = saved
    assert result['status'] == 'failed' and 'standard input' in result['failure']['message'], result
    assert ssh.commands == ['true'] and provider.status == 'terminated', ssh.commands


def proof_finally_terminates_on_failure(base):
    result, provider, ssh, ledger = launch(base, ssh=FakeSsh(MOUNT, trim_rc=255))
    assert result['status'] == 'failed' and result['failure']['error_type'] == 'TrimRefusal', result
    assert provider.status == 'terminated', provider.status
    assert flc.events(ledger) == ['launch_intent', 'launch', 'termination'], flc.events(ledger)
    assert result['termination_confirmed'] and provider.keys == [] and result['ssh_key_removed'] is True
    assert result['own_instance_absent'] is True and not (base / 'keys' / 'ssh_identity').exists()
    assert not Path(str(ledger) + '.lock').exists()


PROOFS = [proof_validator_refuses_each_bad_path_class, proof_script_holds_only_pinned_commands_and_names,
          proof_templates_pin, proof_simulated_run_summary, proof_partial_run_is_never_unknown,
          proof_long_list_arrives_whole, proof_finally_terminates_on_failure]

ORIGINAL_SUMMARISE = ft.summarise


def summarise_discarding_a_cut(text, entries, cut=False):
    """The 20 Nov behaviour: a cut command's output thrown away."""
    return ORIGINAL_SUMMARISE('' if cut else text, entries, cut=cut)


def run(proof):
    with tempfile.TemporaryDirectory() as t:
        proof(Path(t))


def patch_attr(obj, name, value):
    def apply():
        old = getattr(obj, name)
        setattr(obj, name, value)
        return lambda: setattr(obj, name, old)
    return apply


def patch_both(*patches):
    """Apply several patches; returns one restore that undoes them in reverse order."""
    restores = [apply() for apply in patches]
    return lambda: [restore() for restore in reversed(restores)]


NEUTRALISE = {
    # the archive name rule widened to anything after projects/
    'proof_validator_refuses_each_bad_path_class': patch_attr(ft, 'validate_entry', lambda e: dict(e)),
    # the entries no longer quoted into the list template (an extra command slips in)
    'proof_script_holds_only_pinned_commands_and_names': patch_attr(
        ft, 'LIST', ft.LIST.replace('> "$list"', '> "$list"; ls {entries}')),
    # the pin no longer checked
    'proof_templates_pin': patch_attr(ft, 'pinned', lambda: True),
    # the parser reads every line as DELETED
    'proof_simulated_run_summary': patch_attr(ft, 'OUTCOMES', ('DELETED',)),
    # a timed-out command's partial output thrown away (the 20 Nov 09:32 run)
    'proof_partial_run_is_never_unknown': patch_attr(ft, 'summarise', summarise_discarding_a_cut),
    # the script back on the ssh command line (the 20 Nov 10:06 transport), its length guard lifted
    'proof_long_list_arrives_whole': lambda: patch_both(patch_attr(ft, 'remote_call', command_line_transport),
                                                        patch_attr(ft, 'MAX_COMMAND_CHARS', 10 ** 6)),
    # termination never confirmed: the instance stays up after a failed trim
    'proof_finally_terminates_on_failure': patch_attr(ft, 'terminate_confirmed',
                                                       lambda provider, iid, clock, limit=0: None),
}


def neutralised(proof):
    restore = NEUTRALISE[proof.__name__]()
    try:
        run(proof)
    except Exception:
        return True
    finally:
        restore()
    return False


def check():
    passed = []
    for proof in PROOFS:
        try:
            run(proof)
            if not neutralised(proof):
                return 'FAIL', proof.__name__ + ' still passes when neutralised'
            run(proof)
        except Exception as exc:
            return 'FAIL', '%s: %s %s' % (proof.__name__, type(exc).__name__, str(exc)[:160])
        passed.append(proof.__name__)
    return 'PASS', ('%d proofs, each neutralise, fail, restore, pass, fake provider and ssh only: every bad path '
                    'class (root, assets-*, image/*, outside projects/, dot-dot, below projects/, wildcards, shell '
                    'characters, not a project archive name, bad bytes, empty or over 200) refused before any '
                    'provider call; the remote command only the pinned templates and the validated names; the pin '
                    'refuses an altered set; DELETED and SKIP lines parsed into the summary with df before and '
                    'after; a run cut by the local timeout, the remote time budget or a lost connection keeps its outcome '
                    'lines, the file in flight and the files not tried; a 90-entry script over 8 KB goes on standard '
                    'input to bash -s and gives one outcome per entry, while the 20 Nov 10:06 command-line transport '
                    'cut near 8 KB is reproduced and refused as never reaching the trim step, a cut input runs '
                    'nothing and a short list stops at LIST_SHORT; the instance terminated and the ledger closed '
                    'after a failed trim' % len(passed))


if __name__ == '__main__':
    status, detail = check()
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
