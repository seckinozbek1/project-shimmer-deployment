#!/usr/bin/env python3
"""Check 534 (lane/promise-tracker): nothing silently waits (Seckin 18 November 2026 21:46, SUPERVISOR_INBOX):
tools/loop/promise_watch.py and tools/loop/role_start_check.py.

On invented fixtures in a temporary directory: a main checkout with launch folders, a private folder holding
PLANNED_STEPS.jsonl, a budget ledger, role exit files and a trace, a roles folder with outputs, and start .cmd files.
No real private folder, launch folder or role folder is read.

  late_step          a step past expected_start + 5 minutes with no launch alerts, also one whose only launch line
                     is older than its since; one launched in the chain trace, one launched by ledger purpose, one
                     not yet due and one whose output exists stay quiet
  failed_launch      a launch_failed (or rc != 0) line with no new launch for over 5 minutes alerts; one followed by
                     a launch, and one failed 2 minutes ago, stay quiet
  role_gap           a role exit file showing exit with the expected output missing alerts; an exit with the output
                     present and a session still running stay quiet; no file under the roles folder is opened
  real_exit_path     the V SYNLAB1c case (18 Nov 22:39): an exit_file named by its path from the main checkout with
                     the start .cmd's %DATE% %TIME% lines and the outputs missing alerts role_gap, and ready reports
                     it as ended without output (not as not launched); with the outputs present both stay quiet
  once_per_cause     a second run writes no second ALERT line for the same cause, but a trace line every run
  unforeseen_stops   an unreadable plan line writes one ALERT line, result stopped, and no other cause is checked
  ready_lists        ready lists steps whose needs exist and that are not launched or failed, not those waiting or
                     running; a need of the form {any: [{exit_line: F}, ...]} holds once one exit file shows exit
  role_start_check   a start .cmd whose request is missing fails naming that guard; a complete one passes; an
                     "if exist" output guard fails when the output exists; a findstr file is never opened
  role_start_allowlist  the commands the start's requests name are matched against its --settings allow and deny
                     rules: allowed launch.py and watch.py steps pass; a denied lead tool named in a second request in
                     the same folder fails DENIED; an unlisted command and a compound with one unlisted part fail NOT
                     ALLOWED; only the settings file and REQUEST_*.md files are opened
  role_start_lines   request lines outside fences that start with a shell verb (a prose "Copy ... into", a bare
                     cp -r, a mkdir) are commands too and fail NOT ALLOWED; the in-place version passes
  role_start_old_handback  an old <step>_HANDBACK.json, <step>_DONE.json, <step>\result.json or <step>\STOP.txt in
                     the role's to-lead folder fails the start with "old hand-back present: <path>"; names only
  role_start_patterns  --print-patterns prints the settings' Bash allow and deny rules and nothing else of the file

Each proof is run as built (passes), neutralised (must fail), restored and run again (passes).
"""
from __future__ import annotations

import builtins
import contextlib
import datetime as dt
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mechanism_common as mc  # noqa: E402
import promise_watch as pw  # noqa: E402
import role_start_check as rsc  # noqa: E402

NOW = dt.datetime.now().astimezone().replace(microsecond=0)


def ago(minutes):
    return (NOW - dt.timedelta(minutes=minutes)).isoformat()


class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base = Path(self.tmp.name)
        self.main = self.base / 'main'
        self.private = self.base / 'private'
        (self.private / 'role_starts').mkdir(parents=True)
        self.roles = self.base / 'roles'
        (self.roles / '_xfer' / 'N_to_lead').mkdir(parents=True)
        self.cfg = pw.load_config()
        for folder in ('F_A', 'F_B'):
            (self.main / self.cfg['launch_root'] / folder).mkdir(parents=True)
        self.plan = []
        self.patches = [patch.object(mc, 'PRIVATE', self.private), patch.object(mc, 'TRACE', self.private / 'trace.jsonl'),
                        patch.object(mc, 'ALERT', self.private / 'ALERT.md'),
                        patch.object(mc, 'ALERT_STATE', self.private / 'alert_state.json'),
                        patch.object(mc, 'MAIN', self.main)]

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def step(self, step, start_min_ago, **kw):
        line = dict({'step': step, 'owner': 'lead', 'needs': [], 'expected_start': ago(start_min_ago),
                     'expected_output': []}, **kw)
        with open(self.private / 'PLANNED_STEPS.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(line) + '\n')

    def raw_plan(self, text):
        with open(self.private / 'PLANNED_STEPS.jsonl', 'a', encoding='utf-8') as f:
            f.write(text + '\n')

    def chain(self, folder, step, result, minutes_ago, rc=None):
        line = {'time': ago(minutes_ago), 'mechanism': 'launch_chain', 'result': result, 'folder': folder, 'step': step}
        if rc is not None:
            line['rc'] = rc
        with open(mc.TRACE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(line) + '\n')

    def ledger(self, purpose, event='launch'):
        with open(self.private / 'budget_ledger.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'event': event, 'purpose': purpose, 'time_utc': ago(3)}) + '\n')

    def exit_file(self, name, exited, minutes_ago=1):
        path = self.private / 'role_starts' / name
        path.write_text('start 18/11/2026 20:00:00.00 \n' + ('exit 0 18/11/2026 20:40:00.00 \n' if exited else ''),
                        encoding='utf-8')
        t = (NOW - dt.timedelta(minutes=minutes_ago)).timestamp()
        os.utime(path, (t, t))

    def put(self, path, text='{"secret": "never read"}'):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def check(self):
        return pw.check(now=NOW, cfg=self.cfg, main=self.main, private=self.private)

    def alerts(self, word):
        try:
            return [x for x in mc.ALERT.read_text(encoding='utf-8').splitlines() if word in x]
        except OSError:
            return []

    def traces(self):
        return [x.get('result') for x in mc.read_trace() if x.get('mechanism') == pw.NAME]


def caught(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return 'raised %s' % type(exc).__name__


def kinds(result):
    return sorted('%s:%s' % (x['kind'], x['step']) for x in result['causes'])


def observe_late_step():
    with Fixture() as f:
        f.step('A_late', 20, folder='F_A', chain_step='seal', needs=['request/done.json'])
        f.step('B_chain_launched', 20, folder='F_A', chain_step='admit')
        f.chain('F_A', 'admit', 'launch', 10, rc=0)
        f.step('C_ledger_launched', 20, folder='F_B', chain_step='Q1', purpose='dev-q1')
        f.ledger('dev-q1')
        f.step('D_not_due', -30, folder='F_B', chain_step='Q2')
        f.step('E_done', 20, folder='F_B', chain_step='Q3', expected_output=['out/*.json'])
        f.put(f.main / f.cfg['launch_root'] / 'F_B' / 'out' / 'q3.json')
        f.step('K_old_attempt', 20, folder='F_B', chain_step='D1', purpose='dev-d1', since=ago(15))
        f.chain('F_B', 'D1', 'launch', 40, rc=0)          # an earlier attempt, before since: does not count
        r = f.check()
        lines = f.alerts('Planned step late')
        return kinds(r), len(lines), any('A_late' in x and 'request/done.json' in x for x in lines), f.traces()


def expected_late_step():
    return ['late:A_late', 'late:K_old_attempt'], 2, True, ['alert']


def neutralise_late_step():
    return patch.object(pw, 'is_late', lambda now, start, minutes: False)


def observe_failed_launch():
    with Fixture() as f:
        f.step('G_failed', 60, folder='F_A', chain_step='Q1')
        f.chain('F_A', 'Q1', 'launch_failed', 20, rc=1)
        f.step('H_relaunched', 60, folder='F_A', chain_step='Q2')
        f.chain('F_A', 'Q2', 'launch_failed', 20, rc=1)
        f.chain('F_A', 'Q2', 'launch', 16, rc=0)
        f.step('I_recent', 60, folder='F_A', chain_step='Q3')
        f.chain('F_A', 'Q3', 'launch_unconfirmed', 2, rc=124)
        f.step('J_rc', 60, folder='F_B', chain_step='seal')
        f.chain('F_B', 'seal', 'launch_unconfirmed', 30, rc=124)
        r = f.check()
        return kinds(r), len(f.alerts('failed and not launched again'))


def expected_failed_launch():
    return ['failed:G_failed', 'failed:J_rc'], 2


def neutralise_failed_launch():
    cfg = dict(pw.load_config(), failed_results=[])
    real = pw.chain_events

    def blind(step, trace, _cfg):
        return [e for e in real(step, [dict(x, rc=None) for x in trace], cfg) if e[1] != 'failed']
    return patch.object(pw, 'chain_events', blind)


def observe_role_gap():
    with Fixture() as f:
        out = f.roles / '_xfer' / 'N_to_lead'
        f.step('N_S40', 60, owner='role N', role_session='N S40', exit_file='n40_exit.txt',
               expected_output=[str(out / 'S40_HANDBACK.json')])
        f.exit_file('n40_exit.txt', exited=True)
        f.step('N_S39', 60, owner='role N', role_session='N S39', exit_file='n39_exit.txt',
               expected_output=[str(out / 'S39_HANDBACK.json')])
        f.exit_file('n39_exit.txt', exited=True)
        f.put(out / 'S39_HANDBACK.json')
        f.step('N_S41', 60, owner='role N', role_session='N S41', exit_file='n41_exit.txt',
               expected_output=[str(out / 'S41_HANDBACK.json')])
        f.exit_file('n41_exit.txt', exited=False)
        opened, real_open = [], builtins.open

        def guarded(file, *a, **k):
            if str(f.roles) in str(file) and not _placed(file):
                opened.append(str(file))
            return real_open(file, *a, **k)
        with patch.object(builtins, 'open', guarded):
            r = f.check()
        return kinds(r), len(f.alerts('Role session ended without its output')), r['states'], opened


def expected_role_gap():
    return (['role_gap:N_S40'], 1, {'N_S40': 'exited_without_output', 'N_S39': 'done', 'N_S41': 'running'}, [])


def neutralise_role_gap():
    return patch.object(pw, 'role_exit', lambda step, exit_dir, *a: (False, False, None))


def observe_real_exit_path():
    """The V SYNLAB1c case of 18 Nov: exit_file named by its path from the main checkout, the start .cmd's
    %DATE% %TIME% lines, outputs missing: check alerts role_gap and ready says ended without output; with the
    outputs present both stay quiet."""
    out = []
    for present in (False, True):
        with Fixture() as f:
            label = f.roles / '_xfer' / 'lead_to_V' / 'syn_label' / 'V_SYNLAB1'
            outputs = [str(label / 'admitted' / 'admission.json'), str(label / 'run_label')]
            f.step('role_V:SYNLAB1c', 30, owner='role V (supervisor starts)', role_session='V SYNLAB1c',
                   exit_file='docs/loop/private/role_starts/v_synlab1c_exit.txt', expected_output=outputs,
                   added=ago(40))
            path = f.private / 'role_starts' / 'v_synlab1c_exit.txt'
            path.write_text('start 18/11/2026 22:39:32.43 \nexit 0 18/11/2026 22:39:53.46 \n', encoding='utf-8')
            if present:
                f.put(outputs[0])
                (label / 'run_label').mkdir(parents=True)
            r = f.check()
            rows = pw.ready(now=NOW, cfg=f.cfg, main=f.main, private=f.private)
            out.append((kinds(r), len(f.alerts('Role session ended without its output')),
                        [why.split(' (')[0] for _, why in rows]))
    return out


def expected_real_exit_path():
    return [(['role_gap:role_V:SYNLAB1c'], 1, ['role session ended without output']), ([], 0, [])]


def neutralise_real_exit_path():
    return patch.object(pw, 'exit_path', lambda name, exit_dir, cfg, main: Path(exit_dir) / name)


def observe_once_per_cause():
    with Fixture() as f:
        f.step('A_late', 20, folder='F_A', chain_step='seal')
        f.check()
        f.check()
        return len(f.alerts('Planned step late')), f.traces()


def expected_once_per_cause():
    return 1, ['alert', 'alert']


def neutralise_once_per_cause():
    return patch.object(pw, 'ONCE', 0)


def observe_unforeseen_stops():
    with Fixture() as f:
        f.step('A_late', 20, folder='F_A', chain_step='seal')
        f.raw_plan('{"step": "broken", "owner": "lead"')
        r = f.check()
        return (r['result'], len(f.alerts('Promise watch stopped')), len(f.alerts('Planned step late')), f.traces())


def expected_unforeseen_stops():
    return 'stopped', 1, 0, ['stopped']


def neutralise_unforeseen_stops():
    real = pw.read_plan

    def lenient(path, cfg):
        good = [x for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip().endswith('}')]
        tmp = Path(path).with_name('lenient.jsonl')
        tmp.write_text('\n'.join(good) + '\n', encoding='utf-8')
        return real(tmp, cfg)
    return patch.object(pw, 'read_plan', lenient)


def observe_ready_lists():
    with Fixture() as f:
        root = f.main / f.cfg['launch_root']
        f.put(root / 'F_A' / 'admitted' / 'admission.json')
        f.step('Q1_ready', 10, folder='F_A', chain_step='Q1', needs=['admitted/admission.json'])
        f.step('Q2_waiting', 10, folder='F_A', chain_step='Q2', needs=['admitted/missing.json'])
        f.step('Q3_running', 10, folder='F_A', chain_step='Q3', needs=['admitted/admission.json'])
        f.chain('F_A', 'Q3', 'launch', 5, rc=0)
        f.step('Q4_failed', 30, folder='F_A', chain_step='Q4', needs=['admitted/admission.json'])
        f.chain('F_A', 'Q4', 'launch_failed', 20, rc=1)
        f.exit_file('n40_exit.txt', exited=False)               # still running
        f.exit_file('v1b_exit.txt', exited=True)                # ended: one of the two holds
        f.exit_file('n38_exit.txt', exited=False)
        f.step('S41_slot_free', 10, owner='role N', role_session='N S41', exit_file='n41_exit.txt',
               needs=[{'any': [{'exit_line': 'n40_exit.txt'}, {'exit_line': 'v1b_exit.txt'}]}])
        f.step('S42_no_slot', 10, owner='role N', role_session='N S42', exit_file='n42_exit.txt',
               needs=[{'any': [{'exit_line': 'n40_exit.txt'}, {'exit_line': 'n38_exit.txt'}]}])
        rows = pw.ready(now=NOW, cfg=f.cfg, main=f.main, private=f.private)
        return sorted(name for name, _ in rows)


def expected_ready_lists():
    return ['Q1_ready', 'Q4_failed', 'S41_slot_free']


def neutralise_ready_lists():
    return patch.object(pw, 'missing_needs', lambda step, cfg, main: ['x'])


CMD = r'''@echo off
rem fixture role start
cd /d {role}
if not exist inputs_N\REQUEST_ROLE_N_S9.md (echo REQUEST_ROLE_N_S9.md missing: stop & exit /b 2)
if not exist {xfer}\S8_HANDBACK.json (echo S8 has not handed back: stop & exit /b 4)
findstr /c:"BLOCKERS = []" {xfer}\launch.py >nul || (echo launch.py still lists blockers: stop & exit /b 2)
if exist {xfer}\S9_HANDBACK.json (echo S9_HANDBACK.json already exists: stop & exit /b 3)
echo start %DATE% %TIME% > "%~dp0n9_exit.txt"
claude -p "Read ROLE_N.md in this folder. Your inputs are in the folder inputs_N; carry out REQUEST_ROLE_N_S9.md there, up to its STOP." --append-system-prompt-file ROLE_N.md --settings role_settings_N.json --output-format json > r.json
'''


def observe_role_start_check():
    with Fixture() as f:
        role, xfer = f.roles / 'N', f.roles / '_xfer' / 'N_to_lead'
        for p in (role / 'ROLE_N.md', role / 'role_settings_N.json', xfer / 'S8_HANDBACK.json', xfer / 'launch.py'):
            f.put(p)
        cmd = f.put(f.base / 'start_n_s9.cmd', CMD.format(role=role, xfer=xfer))
        opened, real_open = [], builtins.open

        def guarded(file, *a, **k):
            if str(f.roles) in str(file) and not _placed(file):
                opened.append(str(file))
            return real_open(file, *a, **k)
        with patch.object(builtins, 'open', guarded), patch.object(Path, 'read_text', _guard_read(f.roles, opened)):
            missing = rsc.evaluate(cmd)
            f.put(role / 'inputs_N' / 'REQUEST_ROLE_N_S9.md')
            complete = rsc.evaluate(cmd)
            f.put(xfer / 'S9_HANDBACK.json')
            done = rsc.evaluate(cmd)
        stopped = rsc.evaluate(f.base / 'no_such.cmd')[0]
        return (missing[0], [x for x in missing[1] if 'FAILED' in x and 'REQUEST_ROLE_N_S9.md missing' in x] != [],
                complete[0], done[0], [x for x in done[1] if 'FAILED' in x and 'S9_HANDBACK' in x] != [], stopped, opened)


def _placed(path):
    """The two kinds of role-folder file role_start_check may open: the --settings file and a REQUEST_*.md."""
    name = Path(str(path)).name
    return name.startswith('role_settings_') or (name.startswith('REQUEST_') and name.endswith('.md'))


def _guard_read(roots, opened):
    real = Path.read_text

    def read_text(self, *a, **k):
        if str(roots) in str(self) and not _placed(self):
            opened.append(str(self))
        return real(self, *a, **k)
    return read_text


ALLOW_CMD = r'''@echo off
cd /d {role}
if not exist role_settings_V.json (echo settings missing: stop & exit /b 2)
claude -p "Read ROLE_V.md. Then carry out {req} completely, up to its STOP." --append-system-prompt-file ROLE_V.md --settings role_settings_V.json --output-format json > r.json
'''

ALLOW_SETTINGS = {'permissions': {
    'allow': ['Bash(py -3.12 -X utf8 launch.py:*)', 'Bash(py -3.12 -X utf8 watch.py *)', 'Bash(py -3.12 -X utf8 C:/x/*)'],
    'deny': ['Bash(py -3.12 -X utf8 C:/x/lead_tools/*)', 'Bash(git push:*)']}}


def observe_role_start_allowlist():
    """A request naming allowed launch.py and watch.py steps passes; a second request it names in its own folder that
    tells the role to run a denied lead tool fails DENIED (deny wins over the broader allow); one naming an unlisted
    command fails NOT ALLOWED; a compound command with one unlisted part fails; no non-placed role file is opened."""
    out = {}
    with Fixture() as f:
        role, xfer = f.roles / 'V', f.roles / '_xfer' / 'lead_to_V'
        f.put(role / 'ROLE_V.md')
        f.put(role / 'role_settings_V.json', json.dumps(ALLOW_SETTINGS))
        allowed = ('# request\nRun `py -3.12 -X utf8 launch.py status` then\n```\npy -3.12 -X utf8 watch.py admit\n```\n'
                   'Never read `ROLE_V.md` notes.\n')
        cases = {
            'allowed': allowed,
            'denied': allowed + 'Then follow REQUEST_ROLE_V_NEXT.md.\n',
            'unlisted': allowed + 'Then run `git status` once.\n',
            'compound': allowed + 'Then `py -3.12 -X utf8 launch.py seal && git log -1`.\n'}
        f.put(xfer / 'REQUEST_ROLE_V_NEXT.md', 'Wait: `py -3.12 -X utf8 C:/x/lead_tools/wait_admit_room.py --room 1`\n')
        opened, real_open = [], builtins.open

        def guarded(file, *a, **k):
            if str(f.roles) in str(file) and not _placed(file):
                opened.append(str(file))
            return real_open(file, *a, **k)
        with patch.object(builtins, 'open', guarded), patch.object(Path, 'read_text', _guard_read(f.roles, opened)):
            for name, text in cases.items():
                req = f.put(xfer / ('REQUEST_ROLE_V_%s.md' % name.upper()), text)
                cmd = f.put(f.base / ('start_v_%s.cmd' % name), ALLOW_CMD.format(role=role, req=req))
                status, lines = rsc.evaluate(cmd)
                verdicts = sorted({x.split()[0] + (' ALLOWED' if x.split()[:2] == ['NOT', 'ALLOWED'] else '')
                                   for x in lines if x.startswith('    ')})
                out[name] = (status, verdicts)
            out['denied_names_tool'] = any('DENIED' in x and 'wait_admit_room.py' in x
                                           for x in rsc.evaluate(f.base / 'start_v_denied.cmd')[1])
        out['opened'] = opened
    return out


def expected_role_start_allowlist():
    return {'allowed': ('PASS', ['ALLOWED']), 'denied': ('FAIL', ['ALLOWED', 'DENIED']),
            'unlisted': ('FAIL', ['ALLOWED', 'NOT ALLOWED']), 'compound': ('FAIL', ['ALLOWED', 'NOT ALLOWED']),
            'denied_names_tool': True, 'opened': []}


def neutralise_role_start_allowlist():
    return patch.object(rsc, 'judge', lambda cmd, perms: ('ALLOWED', ''))


def expected_role_start_check():
    return 'FAIL', True, 'PASS', 'FAIL', True, 'STOPPED', []


def neutralise_role_start_check():
    return patch.object(rsc.os.path, 'exists', lambda p: True)


def observe_role_start_lines():
    """The S41b case (19 Nov): a request whose copy is a prose line ("1. Copy ... into work"), a bare `cp -r` line and
    a mkdir line, none in backticks or a fence, fails NOT ALLOWED naming each; the same request with those lines
    replaced by an allowed in-place read passes."""
    out = {}
    with Fixture() as f:
        role, xfer = f.roles / 'N', f.roles / '_xfer' / 'lead_to_N'
        f.put(role / 'ROLE_V.md')                                  # the names ALLOW_CMD's claude -p line gives
        f.put(role / 'role_settings_V.json', json.dumps(ALLOW_SETTINGS))
        ok ='# request\nRead in place:\n```\npy -3.12 -X utf8 launch.py answers --run %s\\S41_r\n```\n' % xfer
        cases = {'copying': ok + '1. Copy the folder `S41_r` into `work\\s41\\` before reading.\n'
                            'cp -r %s\\S41_r work\\s41\n- mkdir work\\s41\n' % xfer,
                 'in_place': ok + '1. Read every file in place; nothing is moved.\n'}
        for name, text in cases.items():
            req = f.put(xfer / ('REQUEST_ROLE_N_%s.md' % name.upper()), text)
            cmd = f.put(f.base / ('start_n_%s.cmd' % name), ALLOW_CMD.format(role=role, req=req))
            status, lines = rsc.evaluate(cmd)
            bad = sorted(x.split('NOT ALLOWED', 1)[1].split()[0] for x in lines if x.strip().startswith('NOT ALLOWED'))
            out[name] = (status, bad)
    return out


def expected_role_start_lines():
    return {'copying': ('FAIL', ['Copy', 'cp', 'mkdir']), 'in_place': ('PASS', [])}


def neutralise_role_start_lines():
    return patch.object(rsc, 'line_commands', lambda text: [])


def observe_role_start_patterns():
    """--print-patterns prints the settings' Bash allow and deny rules and no other settings content."""
    with Fixture() as f:
        role = f.roles / 'V'
        f.put(role / 'ROLE_V.md')
        f.put(role / 'role_settings_V.json', json.dumps(dict(ALLOW_SETTINGS, secretish='SHOULD_NOT_PRINT')))
        cmd = f.put(f.base / 'start_v_p.cmd', ALLOW_CMD.format(role=role, req='REQUEST_ROLE_V_X.md'))
        status, lines = rsc.print_patterns(cmd)
        text = ' '.join(lines)
        return (status, 'Bash(git push:*)' in text, 'Bash(py -3.12 -X utf8 launch.py:*)' in text,
                'SHOULD_NOT_PRINT' in text)


def expected_role_start_patterns():
    return 'PATTERNS', True, True, False


def neutralise_role_start_patterns():
    return patch.object(rsc, 'print_patterns', lambda c: ('PATTERNS', ['SHOULD_NOT_PRINT']))


def observe_role_start_old_handback():
    """The S41b case (19 Nov): an old S41b_HANDBACK.json (or _DONE.json, S41b\\result.json, S41b\\STOP.txt) in the
    role's to-lead folder fails the start naming it; another step's file and a renamed old file do not."""
    out = {}
    with Fixture() as f:
        role, xfer = f.roles / 'N', f.roles / '_xfer' / 'N_to_lead'
        f.put(role / 'ROLE_N.md')
        f.put(role / 'role_settings_N.json', json.dumps(ALLOW_SETTINGS))
        cmd = f.put(f.base / 'start_n_s41b.cmd', ALLOW_CMD.replace('ROLE_V', 'ROLE_N').replace('_V.json', '_N.json')
                    .format(role=role, req='REQUEST_ROLE_N_X.md'))
        f.put(role / 'REQUEST_ROLE_N_X.md', 'nothing')
        f.put(xfer / 'S41_HANDBACK.json')
        f.put(xfer / 'S41b_HANDBACK_20261119-0801.json')
        out['other_step'] = rsc.evaluate(cmd)[0]
        for name in ('S41b_HANDBACK.json', 'S41b_DONE.json', 'S41b/result.json', 'S41b/STOP.txt'):
            f.put(xfer / name)
            status, lines = rsc.evaluate(cmd)
            out[name] = (status, any('old hand-back present' in x and name.split('/')[-1] in x for x in lines))
            (xfer / name).unlink()
        out['cleared'] = rsc.evaluate(cmd)[0]
    return out


def expected_role_start_old_handback():
    return {'other_step': 'PASS', 'S41b_HANDBACK.json': ('FAIL', True), 'S41b_DONE.json': ('FAIL', True),
            'S41b/result.json': ('FAIL', True), 'S41b/STOP.txt': ('FAIL', True), 'cleared': 'PASS'}


def neutralise_role_start_old_handback():
    return patch.object(rsc, 'old_handbacks', lambda *a: [])


PROOFS = ('late_step', 'failed_launch', 'role_gap', 'real_exit_path', 'once_per_cause', 'unforeseen_stops', 'ready_lists',
          'role_start_check', 'role_start_allowlist', 'role_start_lines', 'role_start_patterns',
          'role_start_old_handback')


def run_all():
    done, space = [], globals()
    for name in PROOFS:
        observe, expected, neutralise = space['observe_' + name], space['expected_' + name], space['neutralise_' + name]
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                first = observe()
                with neutralise():
                    broken = caught(observe)
                again = observe()
        except Exception as exc:  # noqa: BLE001
            return 'FAIL', '%s: %s %s' % (name, type(exc).__name__, str(exc)[:300])
        if first != expected():
            return 'FAIL', '%s as built: %s' % (name, str(first)[:600])
        if broken == expected():
            return 'FAIL', '%s still passes when neutralised' % name
        if again != expected():
            return 'FAIL', '%s after restore: %s' % (name, str(again)[:400])
        done.append('%s (neutralised: %s)' % (name, str(broken)[:160]))
    return 'PASS', '%d proofs, each neutralise, fail, restore, pass, no real private or role folder read: %s' % (
        len(done), '; '.join(done))


if __name__ == '__main__':
    status, detail = run_all()
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
