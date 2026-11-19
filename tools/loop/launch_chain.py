"""Launch chain: when a prerequisite job ends, the next planned job launches in the same move (Seckin, 18 November
2026 13:40, "Bekletilmesin": nothing ready may wait; a mechanism, not a rule). File format: docs/loop/LAUNCH_CHAIN.md.

    py -3.12 -X utf8 tools/loop/launch_chain.py              # one real pass over every folder with a chain.json
    py -3.12 -X utf8 tools/loop/launch_chain.py --dry-run    # each step's state and what would launch; writes nothing
    py -3.12 -X utf8 tools/loop/launch_chain.py --clear FOLDER:STEP   # release a held step (under the lock)

Run by the Windows task ShimmerLaunchChain every 3 minutes (pyw.exe, hidden). For each launch folder under
external/s05 of the main checkout (resolved through shared_paths, SHIMMER_MAIN_CHECKOUT) that holds a chain.json
beside its launch.py, it reads `launch.py status`, the budget ledger and the admission file, works out which steps
are done, running and ready, and launches each ready step by calling launch.py with that step: a request in the
foreground with its seal at once, admit in the foreground of this runner (it waits for admitted/admission.json
with admitted equal to requests) and then the parts, a ledger step (seal or part) as launch.py starts it
(detached) with `watch.py <step>` started detached beside it.

Double launches are what this guards against first (review of 393a1d37, the lead 14:08):
- right before each launch call the status and the ledger are read again; a step no longer 'not launched', or one
  with a launch_intent or launch line for its purpose and no termination after it, is not launched again;
- a `launch_started` trace line is written before the call, so a pass killed mid-launch leaves a record, and a
  step in `launching` or `unconfirmed` is never launched again (only `--clear` releases an unconfirmed one);
- launches go one at a time against the budget ledger lock, and a GuardRefusal counts only when it is in the
  step's own controller_detached.log, in bytes written after this launch began. The guard raises it when it
  cannot take the ledger lock (tools/loop_budget_guard.py acquire_lock), before the guard's decision, before the
  launch_intent line and before any machine is created, so a refused launch cost nothing. A refused step is held
  10 minutes like a failed launch and alerts after 3 refusals in a row.
- a ledger launch call that exits non-zero or times out after launch_started is held as unconfirmed until
  --clear (a detached controller may still be polling for an instance type, up to 30 minutes, before any intent
  line; ordinary_final_cloud.py), with an alert; it is never retried on a timer;
- a request is written only on a quiet ledger, checked right before the request call (no lock, no launch
  anywhere in the last 60 s), its seal follows with nothing between, and only the request folder the chain's own
  call made is ever renamed aside (request_stale_<HHMM>): the marker request.launch_chain.json names the folder
  and the call's window, the folder must have been created inside that window, and the marker is retired once
  the done file is there; a folder made by hand, even after an old marker, is left alone and alerted. Three
  stale refusals in a row alert. Nothing is ever deleted; no link or junction is followed (launch folders and
  controller logs reached through one are skipped); requires.repo is limited to the main checkout and its
  worktrees.

It never raises a cap, never changes launch.py, and never launches a step whose `launch.py preflight` fails (it
traces and writes ALERT.md instead). An operating-system lock keeps two real passes apart.

Pass length (the task's limit is 180 minutes). The budget is checked before each reading and before each launch:
after PASS_BUDGET_S (50 minutes) no new step is begun, except the seal that follows the request this pass just
wrote. The longest step begun just before the budget, at its timeouts, is a request and its seal: lock wait 3 +
preflight 10 + lock wait 3 + status read 3 + quiet wait 4 + request 30, then status read 3 + lock wait 3 +
preflight 10 + lock wait 3 + status read 3 + seal launch 20 + confirmation 4 = 99 minutes; an admit is 3 + 10 +
3 + 15 + 20 = 51, a part 3 + 10 + 3 + 3 + 20 + 4 = 43. Worst pass: 50 + 3 (the reading) + 99 = 152 minutes, in
whichever folder holds that step; every other folder is skipped once the budget is spent.

One trace line per action goes to docs/loop/private/mechanism_trace.jsonl (mechanism launch_chain), and one
summary line a pass. First readiness times are kept in docs/loop/private/launch_chain_state.json, written only
under the lock.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath, PureWindowsPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mechanism_common as mc  # noqa: E402

NAME = 'launch_chain'
KINDS = ('request', 'admit', 'ledger')
STATES_LAUNCHED = ('running', 'done', 'failed')
STEP_LINE = re.compile(r"^([A-Za-z0-9_-]+) \((-?[0-9.]+(?:e-?[0-9]+)?), '([^']+)'\) (\{.*\})")
WAITING_MINUTES = 5            # the watchdog's rule: a step ready this long with no launch is late
CONFIRM_MINUTES = 10           # a launch must show in the ledger (or its done file) by then, else unconfirmed
RETRY_MINUTES = 10             # a refused launch, a GuardRefusal or a failed preflight is tried again after this
REPEAT_ALERT = 3               # refusals of one kind in a row before ALERT.md
INTENT_WINDOW_MIN = 30         # a launch_intent younger than this with no termination is a launch in flight
ADMIT_WAIT_MINUTES = 20        # an admit with no visible work counts as launching this long after its launch
ADMIT_LOG_QUIET_MINUTES = 15   # an admit.log written more recently than this is an admission at work
POLL_S = 15
PASS_BUDGET_S = 50 * 60        # no new launch is begun after this
TIMEOUT_S = {'status': 180, 'preflight': 600, 'request': 1800, 'admit': 900, 'ledger': 1200}
STARTED = 'launch_started'
UNCONFIRMED = 'launch_unconfirmed'
ACTION_RESULTS = (STARTED, 'launch', 'launch_failed', 'preflight_failed', 'guard_refused', UNCONFIRMED, 'cleared')
HOLDING = ('launch_failed', 'preflight_failed', 'guard_refused')
LEDGER_LOCK_WAIT_S = 180
CONFIRM_WAIT_S = 240
LOCK_POLL_S = 3
REQUEST_QUIET_S = 60
REQUEST_QUIET_WAIT_S = 240
STALE_MARK = 'read copy is stale'
MARKER = 'request.launch_chain.json'
FOLDER_PATH_KEYS = ('admission',)
SEAL_LOG = 'request.run/controller_detached.log'


class ChainError(ValueError):
    pass


def root_dir():
    return Path(mc.MAIN) / 'external' / 's05'


def state_path():
    return Path(mc.PRIVATE) / 'launch_chain_state.json'


def lock_path():
    return Path(mc.PRIVATE) / 'launch_chain.lock'


def ledger_path():
    return Path(mc.PRIVATE) / 'budget_ledger.jsonl'


def ledger_lock_path():
    return Path(mc.PRIVATE) / 'budget_ledger.jsonl.lock'


def parse_time(text):
    try:
        t = dt.datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def interpreter():
    """python.exe beside pythonw.exe (the task runs pyw), so a child's printed status can be read."""
    exe = Path(sys.executable)
    if exe.name.lower() == 'pythonw.exe' and (exe.parent / 'python.exe').is_file():
        exe = exe.parent / 'python.exe'
    return [str(exe), '-X', 'utf8']


def child_env():
    env = dict(os.environ)
    env.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')
    env.setdefault('SHIMMER_MAIN_CHECKOUT', str(mc.MAIN))
    return env


# ---- the plan file ----

def _relative(value, what):
    """A folder-relative path: no drive, no root, no '..'."""
    if not isinstance(value, str) or not value.strip():
        raise ChainError('%s is not a path' % what)
    for p in (PureWindowsPath(value), PurePosixPath(value)):
        if p.is_absolute() or p.drive or p.root or '..' in p.parts:
            raise ChainError('%s %r must be relative to the folder with no ..' % (what, value))
    return value


def launch_purposes(folder):
    """PURPOSES of launch.py read as a literal (never executed); {} when it is not a literal."""
    try:
        tree = ast.parse((Path(folder) / 'launch.py').read_text(encoding='utf-8'))
    except (OSError, SyntaxError, ValueError):
        return {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PURPOSES' for t in node.targets):
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                return {}
            return value if isinstance(value, dict) else {}
    return {}


def load_chain(folder):
    """The folder's chain.json, checked; None when the folder has none."""
    path = Path(folder) / 'chain.json'
    if not path.is_file():
        return None
    try:
        chain = json.loads(path.read_text(encoding='utf-8'))
    except ValueError as exc:
        raise ChainError('chain.json is not JSON: %s' % exc) from None
    steps = chain.get('steps') if isinstance(chain, dict) else None
    if not isinstance(steps, list) or not steps:
        raise ChainError('chain.json names no steps')
    purposes = launch_purposes(folder)
    seen = []
    for s in steps:
        name, kind = s.get('step'), s.get('kind')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', name) or name in seen:
            raise ChainError('step name %r is missing, malformed or repeated' % name)
        if kind not in KINDS:
            raise ChainError('step %s: kind %r is not one of %s' % (name, kind, ', '.join(KINDS)))
        if kind == 'request':
            _relative((s.get('done_when') or {}).get('exists'), 'step %s done_when.exists' % name)
        for key in FOLDER_PATH_KEYS:
            if key in s:
                _relative(s[key], 'step %s %s' % (name, key))
        if kind == 'ledger':
            check_ledger_step(s, steps, purposes)
        for p in s.get('after', []):
            ref = p if isinstance(p, str) else p.get('step')
            state = 'done' if isinstance(p, str) else p.get('state', 'done')
            if ref not in seen:
                raise ChainError('step %s: prerequisite %r is not an earlier step' % (name, ref))
            if state not in ('done', 'launched'):
                raise ChainError('step %s: prerequisite state %r is not done or launched' % (name, state))
        for r in s.get('requires', []):
            if not any(k in r for k in ('file', 'commit', 'folder')):
                raise ChainError('step %s: a requires entry names no file, commit or folder' % name)
            if 'file' in r and (not PureWindowsPath(r['file']).is_absolute() or '..' in PureWindowsPath(r['file']).parts):
                raise ChainError('step %s: requires.file must be an absolute path with no ..' % name)
            if 'folder' in r and (not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', str(r['folder']))
                                  or r['folder'] in ('.', '..')):
                raise ChainError('step %s: requires.folder must be a sibling folder name' % name)
            if 'commit' in r and not re.fullmatch(r'[0-9a-f]{7,40}', str(r['commit'])):
                raise ChainError('step %s: requires.commit must be 7 to 40 hex digits' % name)
        seen.append(name)
    return chain


PURPOSE = re.compile(r'[a-z0-9][a-z0-9-]{0,39}')


def check_ledger_step(s, steps, purposes):
    """A ledger step must have a purpose (declared, or a key of launch.py PURPOSES) of the guard's form, and one
    after admit must declare its own controller_logs (a seal right after its request defaults to request.run)."""
    name = s['step']
    s.setdefault('purpose', purposes.get(name))
    if not isinstance(s.get('purpose'), str) or not PURPOSE.fullmatch(s['purpose']):
        raise ChainError('step %s: a ledger step needs a purpose (chain.json or launch.py PURPOSES) of the form '
                         '[a-z0-9][a-z0-9-]{0,39}' % name)
    kinds = {x['step']: x['kind'] for x in steps}
    after = [kinds.get(p if isinstance(p, str) else p.get('step')) for p in s.get('after', [])]
    if 'admit' in after and not s.get('controller_logs'):
        raise ChainError('step %s: a ledger step after admit must declare its own controller_logs' % name)
    logs = s.get('controller_logs', [SEAL_LOG] if 'request' in after else [])
    s['controller_logs'] = [_relative(x, 'step %s controller_logs' % name) for x in logs]


REPARSE_POINT = 0x400


def is_reparse(path):
    """True for a symbolic link, a junction or any other reparse point (never followed)."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return (os.path.islink(path) or bool(getattr(os.path, 'isjunction', lambda p: False)(path))
            or bool(getattr(st, 'st_file_attributes', 0) & REPARSE_POINT))


def through_links(base, path):
    """True when `path`, or any folder between `base` and it, is a link or junction."""
    base, path = Path(base), Path(path)
    try:
        parts = path.relative_to(base).parts
    except ValueError:
        return True
    current = base
    for part in parts:
        current = current / part
        if is_reparse(current):
            return True
    return False


def chain_folders(root=None):
    root = Path(root or root_dir())
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if not is_reparse(p) and p.is_dir() and (p / 'chain.json').is_file()
                  and (p / 'launch.py').is_file() and not is_template(p))


def is_template(folder):
    """True when the folder's chain.json declares "template": true (OPEN_ITEMS 159): a template folder is copied by
    hand (role V drives its own copy) and is never planned or launched. An unreadable chain.json is not a template:
    its error surfaces where it is loaded."""
    try:
        chain = json.loads((Path(folder) / 'chain.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return isinstance(chain, dict) and chain.get('template') is True


def own_logs(folder, step):
    """The step's own controller logs (its globs), never through a link or junction."""
    out = []
    for pattern in step.get('controller_logs', []):
        out += [log for log in Path(folder).glob(pattern) if not through_links(folder, log)]
    return out


# ---- reading the state ----

def call_launch(folder, args, timeout):
    """(exit code, stdout, stderr tail) of `launch.py <args>` run in the folder."""
    try:
        done = subprocess.run(interpreter() + [str(Path(folder) / 'launch.py')] + list(args), cwd=str(folder),
                              env=child_env(), stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=timeout, creationflags=mc.no_window())
    except subprocess.TimeoutExpired:
        return 124, '', 'timed out after %d s' % timeout
    return done.returncode, done.stdout or '', (done.stderr or '')[-400:]


def read_status(folder, timeout=None):
    rc, text, err = call_launch(folder, ['status'], timeout or TIMEOUT_S['status'])
    if rc != 0:
        raise ChainError('launch.py status exit %d: %s' % (rc, err.strip()[-200:]))
    return parse_status(text)


def parse_status(text):
    """{step: {'cost', 'state', 'phase'}} from `launch.py status` lines `name (cost, 'state') {phase}`."""
    out = {}
    for line in text.splitlines():
        m = STEP_LINE.match(line.strip())
        if not m:
            continue
        try:
            phase = ast.literal_eval(m.group(4))
        except (ValueError, SyntaxError):
            phase = {}
        out[m.group(1)] = {'cost': float(m.group(2)), 'state': m.group(3), 'phase': phase if isinstance(phase, dict) else {}}
    return out


def read_ledger():
    try:
        with open(ledger_path(), encoding='utf-8') as f:
            rows = []
            for raw in f:
                raw = raw.strip()
                if raw:
                    try:
                        rows.append(json.loads(raw))
                    except ValueError:
                        continue
            return rows
    except OSError:
        return []


def in_flight(rows, purpose, t=None):
    """The purpose's last launch_intent or launch line when no termination follows it (an intent only while
    younger than INTENT_WINDOW_MIN); else None."""
    if not purpose:
        return None
    own = [r for r in rows if r.get('purpose') == purpose and r.get('event') in ('launch_intent', 'launch', 'termination')]
    if not own or own[-1]['event'] == 'termination':
        return None
    last = own[-1]
    if last['event'] == 'launch_intent':
        when = parse_time(last.get('time_utc'))
        if when is None or ((t or mc.now()) - when).total_seconds() > INTENT_WINDOW_MIN * 60:
            return None
    return last


def admission(folder, step):
    path = Path(folder) / step.get('admission', 'admitted/admission.json')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def admitted_all(folder, step):
    a = admission(folder, step)
    return bool(a) and isinstance(a.get('requests'), int) and a['requests'] > 0 and a.get('admitted') == a['requests']


def actions(trace, folder_name, step_name):
    return [x for x in trace if x.get('mechanism') == NAME and x.get('folder') == folder_name
            and x.get('step') == step_name and x.get('result') in ACTION_RESULTS]


def last_action(trace, folder_name, step_name):
    rows = actions(trace, folder_name, step_name)
    return rows[-1] if rows else None


def in_a_row(trace, folder_name, step_name, result):
    """How many of the step's latest actions in a row ended in `result` (launch_started lines skipped)."""
    n = 0
    for x in reversed(actions(trace, folder_name, step_name)):
        if x['result'] == STARTED:
            continue
        if x['result'] != result:
            break
        n += 1
    return n


def step_bundles(folder, step):
    """The step's bundle names in order: plan.json `bundles[step]` (what launch.py BUNDLES is read from), else a
    literal BUNDLES in launch.py (never executed); None when neither names the step."""
    try:
        plan = json.loads((Path(folder) / 'plan.json').read_text(encoding='utf-8'))
        named = (plan.get('bundles') or {}).get(step['step']) if isinstance(plan, dict) else None
        if isinstance(named, list) and all(isinstance(b, str) for b in named):
            return named
    except (OSError, ValueError, AttributeError):
        pass
    try:
        tree = ast.parse((Path(folder) / 'launch.py').read_text(encoding='utf-8'))
    except (OSError, SyntaxError, ValueError):
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'BUNDLES' for t in node.targets):
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                return None
            named = value.get(step['step']) if isinstance(value, dict) else None
            return named if isinstance(named, list) and all(isinstance(b, str) for b in named) else None
    return None


EVIDENCE = 'collected_evidence.tar.gz'
RESULT_MEMBER = 'evidence/result.json'


def batch_run_folder(folder, step, bundles):
    """admitted/<first bundle> (where launch.py runs a batch), else the folder of the step's own controller log."""
    first = Path(folder) / 'admitted' / bundles[0]
    if first.is_dir() and not through_links(folder, first):
        return first
    logs = own_logs(folder, step)
    return logs[0].parent if logs else None


def evidence_exit_code(path):
    """pipeline_exit_code of evidence/result.json in one collected_evidence.tar.gz (only that member is read)."""
    import tarfile
    try:
        with tarfile.open(path, 'r:gz') as tar:
            member = tar.getmember(RESULT_MEMBER)
            if not member.isfile():
                return None
            handle = tar.extractfile(member)
            result = json.loads(handle.read().decode('utf-8')) if handle else None
    except (OSError, KeyError, ValueError, EOFError, tarfile.TarError):
        return None
    return result.get('pipeline_exit_code') if isinstance(result, dict) else None


def batch_state(folder, step, row, bundles):
    """A batch part (more than one bundle) never writes workload_return.json: done when the instance ended
    terminated_and_cleaned with TERMINATION_VERIFIED, no controller_failure, and one batch/NN_*/collected_evidence
    per bundle whose evidence/result.json has pipeline_exit_code 0; failed otherwise, with the reason."""
    phase, cost, n = row['phase'], row['cost'], len(bundles)
    current = (phase.get('CURRENT_PHASE') or {}).get('phase')
    problems = []
    if current != 'terminated_and_cleaned':
        problems.append('phase %s' % current)
    if 'TERMINATION_VERIFIED' not in phase:
        problems.append('no TERMINATION_VERIFIED')
    if 'controller_failure' in phase:
        problems.append('controller_failure %s' % (phase['controller_failure'].get('error_type')))
    run = batch_run_folder(folder, step, bundles)
    found = [] if run is None else sorted(p for p in (run / 'batch').glob('[0-9][0-9]_*/' + EVIDENCE)
                                          if not through_links(folder, p))
    if len(found) != n:
        problems.append('%d of %d batch evidences' % (len(found), n))
    bad = [p.parent.name for p in found if evidence_exit_code(p) != 0]
    if bad:
        problems.append('%d evidences without pipeline_exit_code 0 (%s)' % (len(bad), ', '.join(bad[:3])))
    if problems:
        return 'failed', 'ended batch of %d: %s (%.3f USD)' % (n, '; '.join(problems), cost)
    return 'done', 'ended batch, %d of %d batch evidences with pipeline_exit_code 0, terminated_and_cleaned (%.3f USD)' % (
        len(found), n, cost)


def own_state(folder, step, status, rows=(), t=None):
    """done, running, launching, failed, pending or unknown, from the evidence alone (no trace)."""
    kind = step['kind']
    if kind == 'request':
        return ('done', 'the request is written') if (Path(folder) / step['done_when']['exists']).exists() \
            else ('pending', 'no %s yet' % step['done_when']['exists'])
    if kind == 'admit':
        if admitted_all(folder, step):
            return 'done', 'admission.json: all requests admitted'
        a = admission(folder, step)
        if a:
            return 'failed', 'admission.json: %s of %s admitted' % (a.get('admitted'), a.get('requests'))
        return 'pending', 'no admission yet'
    row = status.get(step['step'])
    if row is None:
        return 'unknown', 'launch.py status prints no line for this step'
    if row['state'] == 'running':
        return 'running', 'ledger launch line, no termination (%.3f USD so far)' % row['cost']
    if row['state'] == 'ended':
        bundles = step_bundles(folder, step)
        if bundles and len(bundles) > 1:
            return batch_state(folder, step, row, bundles)
        code = (row['phase'].get('workload_return') or {}).get('exit_code')
        if code == 0:
            return 'done', 'ended, workload_return exit_code 0 (%.3f USD)' % row['cost']
        return 'failed', 'ended, workload_return exit_code %s (%.3f USD)' % (code, row['cost'])
    if row['state'] == 'not launched':
        flight = in_flight(rows, step.get('purpose'), t)
        if flight:
            return 'launching', 'the ledger has a %s line for %s at %s and no termination' % (
                flight['event'], step.get('purpose'), flight.get('time_utc'))
        return 'pending', 'not launched'
    return 'unknown', 'state %r' % row['state']


def known_checkouts():
    """The main checkout and its worktrees (`git worktree list --porcelain`), resolved."""
    known = [Path(mc.MAIN)]
    try:
        out = subprocess.run(['git', '-C', str(mc.MAIN), 'worktree', 'list', '--porcelain'], capture_output=True,
                             text=True, timeout=60, creationflags=mc.no_window()).stdout or ''
    except (OSError, subprocess.TimeoutExpired):
        out = ''
    known += [Path(line[len('worktree '):].strip()) for line in out.splitlines() if line.startswith('worktree ')]
    return known


def _norm(path):
    try:
        return os.path.normcase(str(Path(path).resolve()))
    except OSError:
        return os.path.normcase(str(path))


def repo_known(repo):
    return _norm(repo) in {_norm(p) for p in known_checkouts()}


def git_is_ancestor(repo, commit, ref):
    try:
        return subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', '--end-of-options', commit, ref],
                              capture_output=True, timeout=60, creationflags=mc.no_window()).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def external_ok(req, context):
    """(holds, why) for one `requires` entry."""
    if 'file' in req:
        ok = Path(req['file']).exists()
        return ok, '%s %s' % (Path(req['file']).name, 'exists' if ok else 'does not exist yet')
    if 'commit' in req:
        ref = req.get('ref', 'HEAD')
        repo = Path(req.get('repo') or mc.MAIN)
        if not repo_known(repo):
            return False, 'repo %s is not the main checkout or one of its worktrees; refused' % repo
        ok = git_is_ancestor(repo, req['commit'], ref)
        return ok, 'commit %s %s the lead tip (%s)' % (req['commit'], 'is on' if ok else 'is not yet on', ref)
    other = Path(context['root']) / req['folder']
    states = context['evaluate'](other)
    got = states.get(req.get('step'), {}).get('state')
    want = req.get('state', 'done')
    ok = got == 'done' if want == 'done' else got in STATES_LAUNCHED
    return ok, '%s %s is %s' % (other.name, req.get('step'), got)


def evaluate(folder, chain, status, trace, t, root=None, cache=None, rows=()):
    """{step: {'state', 'why', 'step'}} with state one of done, running, failed, unknown, launching, unconfirmed,
    held (prerequisites done, a recent refusal or failed preflight), ready, waiting."""
    folder = Path(folder)
    cache = {} if cache is None else cache
    context = {'root': root or folder.parent,
               'evaluate': lambda other: folder_states(other, trace, t, root=root, cache=cache, rows=rows)}
    out = {}
    for step in chain['steps']:
        name = step['step']
        state, why = own_state(folder, step, status, rows, t)
        last = last_action(trace, folder.name, name)
        age = (t - parse_time(last['time'])).total_seconds() / 60 if last and parse_time(last.get('time')) else None
        if state == 'pending' and last and last['result'] == UNCONFIRMED:
            state, why = 'unconfirmed', ('launch.py %s exited %s at %s after launch_started; a detached controller may '
                                         'still be waiting for an instance; held until --clear %s:%s'
                                         % (name, last.get('rc'), last['time'], folder.name, name))
        if state == 'pending' and last and (last['result'] == STARTED or (last['result'] == 'launch' and last.get('rc') == 0)):
            window = CONFIRM_MINUTES + (step.get('admit_wait_minutes', ADMIT_WAIT_MINUTES) if step['kind'] == 'admit' else 0)
            if age is not None and age < window:
                state, why = 'launching', 'launch begun by the chain %.0f min ago (%s), not yet in the evidence' % (
                    age, last['result'])
            elif step['kind'] == 'admit' and admit_active(folder, step):
                state, why = 'launching', ('admission at work (staging folder or admit.log written in the last %d min), '
                                           'begun by the chain %.0f min ago' % (ADMIT_LOG_QUIET_MINUTES, age or 0))
            else:
                state, why = 'unconfirmed', ('launch begun by the chain at %s (%s), never confirmed by the evidence; '
                                             'held until --clear %s:%s' % (last['time'], last['result'], folder.name, name))
        if state == 'pending':
            unmet = []
            for p in step.get('after', []):
                ref = p if isinstance(p, str) else p['step']
                want = 'done' if isinstance(p, str) else p.get('state', 'done')
                got = out[ref]['state']
                if not (got == 'done' if want == 'done' else got in STATES_LAUNCHED):
                    unmet.append('%s is %s (needs %s)' % (ref, got, want))
            for r in step.get('requires', []):
                ok, rwhy = external_ok(r, context)
                if not ok:
                    unmet.append(rwhy)
            if unmet:
                state, why = 'waiting', '; '.join(unmet)
            elif last and last['result'] in HOLDING and age is not None and age < RETRY_MINUTES:
                state, why = 'held', '%s %.0f min ago; tried again after %d min' % (last['result'], age, RETRY_MINUTES)
            else:
                state, why = 'ready', 'every prerequisite holds: ' + (', '.join(
                    (p if isinstance(p, str) else '%s %s' % (p['step'], p.get('state'))) for p in step.get('after', []))
                    or 'none')
        out[name] = {'step': name, 'kind': step['kind'], 'state': state, 'why': why}
    return out


def folder_states(folder, trace, t, root=None, cache=None, rows=None, status_timeout=None):
    folder = Path(folder)
    key = str(folder.resolve())
    if cache is not None and key in cache:
        return cache[key]
    chain = load_chain(folder)
    if chain is None:
        result = {}
    else:
        status = read_status(folder, status_timeout) if any(s['kind'] == 'ledger' for s in chain['steps']) else {}
        if cache is not None:
            cache[key] = {}      # a folder naming itself cannot loop
        result = evaluate(folder, chain, status, trace, t, root=root, cache=cache,
                          rows=read_ledger() if rows is None else rows)
    if cache is not None:
        cache[key] = result
    return result


# ---- first readiness (written only under the chain lock) ----

def load_state():
    try:
        return json.loads(state_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_state(state):
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.writing')
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True), encoding='utf-8', newline='\n')
    os.replace(tmp, path)


def note_readiness(plans, t, write=True):
    """Give each ready or held step its first-seen time (kept in the state file when `write`)."""
    state = load_state()
    first = state.get('ready_since', {})
    keep = {}
    for folder, steps in plans.items():
        for name, row in steps.items():
            if row['state'] in ('ready', 'held'):
                key = '%s:%s' % (folder, name)
                keep[key] = first.get(key) or mc.iso(t)
                row['ready_since'] = keep[key]
    for key, value in first.items():
        if key.split(':', 1)[0] not in plans:
            keep[key] = value
    if write:
        state['ready_since'] = keep
        save_state(state)
    return keep


# ---- the pass ----

def plan(root=None, t=None, folders=None, write_state=False, status_timeout=None, deadline=None):
    """{folder name: {step: row}} for every chain folder, and {folder name: error} for those unreadable."""
    t = t or mc.now()
    trace = mc.read_trace()
    rows = read_ledger()
    plans, errors, cache = {}, {}, {}
    for folder in (folders or chain_folders(root)):
        if deadline is not None and time.time() > deadline:
            errors[folder.name] = 'not read: the reading ran out of its time'
            continue
        try:
            plans[folder.name] = folder_states(folder, trace, t, root=root, cache=cache, rows=rows,
                                               status_timeout=status_timeout)
        except (ChainError, OSError, KeyError, TypeError, ValueError) as exc:
            errors[folder.name] = '%s: %s' % (type(exc).__name__, exc)
    note_readiness(plans, t, write=write_state)
    return plans, errors


def waiting(root=None, t=None, minutes=WAITING_MINUTES, status_timeout=60, budget_s=180):
    """The watchdog's rule: every step whose prerequisites have held for more than `minutes` with no launch.
    Status calls are bounded (`status_timeout` each, `budget_s` in all); the first-seen times are written only
    when the chain lock is free (taken and released at once), never while a real pass runs."""
    t = t or mc.now()
    plans, errors = plan(root, t, status_timeout=status_timeout, deadline=time.time() + budget_s)
    ok, _ = acquire_lock(t)
    if ok:
        try:
            note_readiness(plans, t, write=True)
        finally:
            release_lock()
    late = []
    for folder, steps in plans.items():
        for name, row in steps.items():
            since = parse_time(row.get('ready_since'))
            if row['state'] in ('ready', 'held') and since and (t - since).total_seconds() > minutes * 60:
                late.append({'folder': folder, 'step': name, 'state': row['state'], 'ready_since': row['ready_since'],
                             'minutes': round((t - since).total_seconds() / 60, 1), 'why': row['why']})
    return late, errors


_HELD = []          # the open handle of this process's chain lock
LOCK_OFFSET = 1 << 20


def _lock_region(f, on):
    """Lock (or unlock) the chain lock on the open handle `f`, without waiting; OSError when it is held.
    Windows: msvcrt byte-range lock, which conflicts between any two handles. POSIX: flock, which belongs to
    the open file description, so two handles conflict even inside one process and closing another handle
    of the same file does not drop it (fcntl.lockf record locks are per process: a second handle in the
    same process was granted the lock, and any close of the file released it; the Linux gate showed it)."""
    if os.name == 'nt':
        import msvcrt
        f.seek(LOCK_OFFSET)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK if on else msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(f.fileno(), (fcntl.LOCK_EX | fcntl.LOCK_NB) if on else fcntl.LOCK_UN)


def acquire_lock(t=None):
    """(True, previous holder) when this process holds the chain lock, (False, holder) when another does.
    An operating-system lock on an open handle of launch_chain.lock: a pass that dies releases it with its
    process, so no age rule is needed, and nothing is ever deleted (the file only records the last holder)."""
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8'):
        pass
    f = open(path, 'r+b')
    try:
        _lock_region(f, True)
    except OSError:
        f.close()
        try:
            held = json.loads(path.read_text(encoding='utf-8') or '{}')
        except (OSError, ValueError):
            held = {}
        return False, held
    f.seek(0)
    try:
        previous = json.loads(f.read(4096).decode('utf-8') or '{}')
    except ValueError:
        previous = {}
    f.seek(0)
    f.truncate()
    f.write(json.dumps({'pid': os.getpid(), 'time': mc.iso(t)}).encode('utf-8'))
    f.flush()
    _HELD.append(f)
    return True, previous


def release_lock():
    while _HELD:
        f = _HELD.pop()
        try:
            _lock_region(f, False)
        except OSError:
            pass
        f.close()


# ---- request folders: only the chain's own are ever touched, and only renamed ----

def request_dir(step):
    return PurePosixPath(step['done_when']['exists'].replace('\\', '/')).parts[0]


def read_marker(folder):
    try:
        marker = json.loads((Path(folder) / MARKER).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return marker if isinstance(marker, dict) and marker.get('mechanism') == NAME else {}


def folder_born(path):
    st = os.stat(path)
    return getattr(st, 'st_birthtime', None) or st.st_ctime


def chain_wrote(folder, step, partial=False):
    """True only for the request folder the chain's own request call made: the marker names it, and the folder
    was created inside that call's window (from just before the call to its end, or its timeout when the pass was
    killed). A folder made by hand at any other time, even after an old marker, is never the chain's. With
    `partial`, a marker already retired (its done file seen) does not count either."""
    marker = read_marker(folder)
    if marker.get('request_dir') != request_dir(step) or (partial and marker.get('done_at')):
        return False
    src = Path(folder) / request_dir(step)
    start = marker.get('started_epoch')
    if not isinstance(start, (int, float)) or not src.is_dir() or is_reparse(src):
        return False
    end = marker.get('ended_epoch') or start + TIMEOUT_S['request']
    return start - 2 <= folder_born(src) <= end + 2


def write_marker(folder, step, **fields):
    marker = read_marker(folder) if not fields.get('started_epoch') else {}
    marker.update({'mechanism': NAME, 'request_dir': request_dir(step)}, **fields)
    marker['time'] = mc.iso()
    (Path(folder) / MARKER).write_text(json.dumps(marker), encoding='utf-8', newline='\n')


def retire_marker(folder, step):
    """Once the request's done file is there, the marker records it (done_at): no partial folder is ever taken
    for the chain's again under that marker."""
    marker = read_marker(folder)
    if (marker.get('request_dir') == request_dir(step) and not marker.get('done_at')
            and (Path(folder) / step['done_when']['exists']).exists()):
        write_marker(folder, step, done_at=mc.iso())
        mc.trace(NAME, 'marker_retired', folder=Path(folder).name, step=step['step'])


def set_aside(folder, relative):
    """Rename `relative` aside as <name>_stale_<HHMM>; never delete it. The new name, or None (nothing there or
    the rename refused: traced and alerted, never raised)."""
    src = Path(folder) / relative
    if not src.exists():
        return None
    stamp = mc.now().strftime('%H%M')
    dst = src.with_name('%s_stale_%s' % (src.name, stamp))
    n = 2
    while dst.exists():
        dst = src.with_name('%s_stale_%s_%d' % (src.name, stamp, n))
        n += 1
    try:
        os.rename(src, dst)
    except OSError as exc:
        mc.trace(NAME, 'set_aside_refused', folder=Path(folder).name, path=relative, error=str(exc)[:200])
        mc.alert('launch_chain:set_aside:%s' % Path(folder).name, 'Launch chain: could not rename %s/%s aside (%s); '
                 'the request waits for the lead.' % (Path(folder).name, relative, type(exc).__name__))
        return None
    return dst.name


def recent_launches(seconds, now_s=None):
    """Launch or launch_intent lines in the budget ledger, and chain launches, within `seconds`."""
    now_s = time.time() if now_s is None else now_s
    hits = []
    for r in read_ledger()[-300:]:
        t = parse_time(r.get('time_utc'))
        if r.get('event') in ('launch', 'launch_intent') and t and now_s - t.timestamp() < seconds:
            hits.append('ledger %s %s' % (r.get('event'), r.get('purpose')))
    for x in mc.read_trace()[-500:]:
        t = parse_time(x.get('time'))
        if x.get('mechanism') == NAME and x.get('result') in (STARTED, 'launch') and t and now_s - t.timestamp() < seconds:
            hits.append('chain %s %s' % (x.get('folder'), x.get('step')))
    return hits


def wait_quiet_ledger():
    """True once the ledger lock is gone and nothing launched anywhere in the last REQUEST_QUIET_S seconds."""
    end = time.time() + REQUEST_QUIET_WAIT_S
    while ledger_lock_path().exists() or recent_launches(REQUEST_QUIET_S):
        if time.time() >= end:
            return False
        time.sleep(LOCK_POLL_S)
    return True


def wait_ledger_lock(limit_s=None):
    """True once the budget ledger lock file is gone (within `limit_s`)."""
    end = time.time() + (LEDGER_LOCK_WAIT_S if limit_s is None else limit_s)
    while ledger_lock_path().exists():
        if time.time() >= end:
            return False
        time.sleep(LOCK_POLL_S)
    return True


# ---- one step ----

def log_offsets(folder, step):
    """{relative log path: size now} for the step's own controller logs (globs allowed, no link followed)."""
    out = {}
    for log in own_logs(folder, step):
        try:
            out[str(log.relative_to(folder))] = log.stat().st_size
        except OSError:
            continue
    return out


def refusal_seen(folder, step, offsets):
    """(log, the GuardRefusal line) from the step's own controller log, in bytes written after `offsets`; or None."""
    for log in own_logs(folder, step):
        rel = str(log.relative_to(folder))
        try:
            with open(log, 'rb') as f:
                f.seek(offsets.get(rel, 0))
                fresh = f.read(1 << 20).decode('utf-8', 'replace')
        except OSError:
            continue
        for line in fresh.splitlines():
            if 'GuardRefusal' in line:
                return rel, line.strip()[:300]
    return None


def confirm_launch(folder, step, offsets):
    """('confirmed' | 'guard_refused' | 'unconfirmed', detail) after a ledger launch that returned 0: waits until
    the ledger lock is gone and the status leaves 'not launched', or the step's own log gains a GuardRefusal."""
    end = time.time() + CONFIRM_WAIT_S
    while True:
        seen = refusal_seen(folder, step, offsets)
        if seen:
            return 'guard_refused', seen
        if not ledger_lock_path().exists():
            try:
                state = read_status(folder).get(step['step'], {}).get('state')
            except ChainError:
                state = None
            if state and state != 'not launched':
                return 'confirmed', state
        if time.time() >= end:
            return 'unconfirmed', 'no ledger launch line within %d s' % CONFIRM_WAIT_S
        time.sleep(LOCK_POLL_S)


def still_not_launched(folder, step):
    """Read the status and the ledger again right before a launch call: None when the step is still not launched,
    else why not to launch it."""
    if step['kind'] == 'request':
        return 'the request appeared meanwhile' if (Path(folder) / step['done_when']['exists']).exists() else None
    if step['kind'] == 'admit':
        return 'the admission appeared meanwhile' if admission(folder, step) else None
    try:
        state = read_status(folder).get(step['step'], {}).get('state')
    except ChainError as exc:
        return 'status unreadable right before the launch: %s' % exc
    if state != 'not launched':
        return 'status now says %r' % state
    flight = in_flight(read_ledger(), step.get('purpose'))
    if flight:
        return 'the ledger now has a %s line for %s at %s' % (flight['event'], step.get('purpose'), flight.get('time_utc'))
    return None


def record_intent(folder, step):
    mc.trace(NAME, STARTED, folder=folder.name, step=step['step'], kind=step['kind'], purpose=step.get('purpose'))


def launch_step(folder, step, row, chain):
    """Preflight, a fresh reading, then the step; one trace line per action. True when the step was started."""
    name, kind = step['step'], step['kind']
    if kind == 'request':
        if (Path(folder) / request_dir(step)).exists():
            if not chain_wrote(folder, step, partial=True):
                mc.trace(NAME, 'deferred', folder=folder.name, step=name,
                         why='%s exists without its done file and the chain did not write it' % request_dir(step))
                mc.alert('launch_chain:foreign_request:%s' % folder.name,
                         'Launch chain: %s/%s exists without its done file and was not written by the chain (the lead may '
                         'be writing it); left alone, the request waits.' % (folder.name, request_dir(step)))
                return False
            aside = set_aside(folder, request_dir(step))
            if aside is None:
                return False
            mc.trace(NAME, 'set_aside', folder=folder.name, step=name, renamed=aside,
                     why='the chain\'s own request folder without its done file; renamed aside, never deleted')
    if not wait_ledger_lock():
        mc.trace(NAME, 'deferred', folder=folder.name, step=name, why='the budget ledger lock was held for %d s'
                 % LEDGER_LOCK_WAIT_S)
        return False
    # The step is named so launch.py holds that step kind's RAM floor (tools/loop/launch_floors.py, Seckin 18 Nov
    # 18:54); a launch.py that predates it reads only its first argument and holds its one floor.
    rc, out, err = call_launch(folder, ['preflight', name], TIMEOUT_S['preflight'])
    if rc != 0:
        tail = (out.strip().splitlines() or [''])[0][:300]
        mc.trace(NAME, 'preflight_failed', folder=folder.name, step=name, rc=rc, preflight=tail)
        mc.alert('launch_chain:preflight:%s:%s' % (folder.name, name),
                 'Launch chain: %s %s is ready but launch.py preflight failed (exit %d): %s. Not launched; the chain '
                 'tries again after %d minutes.' % (folder.name, name, rc, tail, RETRY_MINUTES))
        return False
    if not wait_ledger_lock():
        mc.trace(NAME, 'deferred', folder=folder.name, step=name, why='the budget ledger lock was held after preflight')
        return False
    why_not = still_not_launched(folder, step)
    if why_not:
        mc.trace(NAME, 'already_launched', folder=folder.name, step=name, why=why_not)
        return False
    offsets = log_offsets(folder, step)
    if kind == 'request':
        # Quiet ledger right before the request call (not before preflight): no lock and no launch anywhere in the
        # last REQUEST_QUIET_S seconds, so nothing writes the ledger between this request and its seal.
        if not wait_quiet_ledger():
            mc.trace(NAME, 'deferred', folder=folder.name, step=name,
                     why='the ledger was not quiet for %d s (lock or a launch in the last %d s)' % (
                         REQUEST_QUIET_WAIT_S, REQUEST_QUIET_S))
            return False
        write_marker(folder, step, started_epoch=time.time(), ended_epoch=None, done_at=None)
    record_intent(folder, step)
    rc, out, err = call_launch(folder, [name], TIMEOUT_S[kind])
    if kind == 'request':
        write_marker(folder, step, ended_epoch=time.time())
    request = stale_request_of(chain, step) if kind == 'ledger' else None
    if request and seal_refused_stale(rc, out + err):
        aside = set_aside(folder, request_dir(request)) if chain_wrote(folder, request) else None
        mc.trace(NAME, 'request_stale', folder=folder.name, step=name, rc=rc, renamed=aside,
                 why='the seal found its request read copy stale; the request is written again on the next pass'
                 if aside else 'the seal found its request stale; the request is not the chain\'s own, left alone')
        if aside:
            mc.trace(NAME, 'cleared', folder=folder.name, step=name, why='stale request, not launched')
            mc.trace(NAME, 'cleared', folder=folder.name, step=request['step'], why='request set aside as stale')
        else:
            mc.trace(NAME, 'launch_failed', folder=folder.name, step=name, kind=kind, rc=rc,
                     why='stale request the chain did not write; held %d minutes' % RETRY_MINUTES)
        count = stale_in_a_row(folder.name, name)
        if count >= REPEAT_ALERT or not aside:
            mc.alert('launch_chain:stale:%s' % folder.name, 'Launch chain: the seal in %s was refused as stale %d times '
                     'in a row%s; read the folder.' % (folder.name, count, '' if aside else ' (request not the chain\'s own)'))
        return False
    if rc == 0 and kind == 'ledger':
        outcome, detail = confirm_launch(folder, step, offsets)
        if outcome == 'guard_refused':
            log, line = detail
            mc.trace(NAME, 'guard_refused', folder=folder.name, step=name, kind=kind, log=log, refusal=line,
                     why='launch.py exit 0 but the guard refused before any machine was created; held %d minutes, '
                         'then tried again' % RETRY_MINUTES)
            n = in_a_row(mc.read_trace(), folder.name, name, 'guard_refused')
            if n >= REPEAT_ALERT:
                mc.alert('launch_chain:guard:%s:%s' % (folder.name, name), 'Launch chain: %s %s was refused %d times in '
                         'a row, no machine created; the last refusal (%s): %s' % (folder.name, name, n, log, line))
            return False
        out = out + '\nconfirm: %s (%s)' % (outcome, detail)
    if rc != 0 and kind == 'ledger':
        # After launch_started a detached controller may still be waiting for an instance type (up to 30 minutes,
        # before any intent line): never retried on a timer; held as unconfirmed until --clear, with an alert.
        result = ledger_failure_result(rc)
        mc.trace(NAME, result, folder=folder.name, step=name, kind=kind, rc=rc,
                 tail=(out.strip().splitlines() or [''])[-1][:300], stderr=err.strip()[-200:])
        mc.alert('launch_chain:unconfirmed:%s:%s' % (folder.name, name),
                 'Launch chain: launch.py %s in %s exited %d (%s) after launch_started; a detached controller may '
                 'still be starting. Held until the lead reads the folder and runs --clear %s:%s.'
                 % (name, folder.name, rc, 'timed out' if rc == 124 else 'non-zero', folder.name, name))
        return False
    if rc != 0:
        mc.trace(NAME, 'launch_failed', folder=folder.name, step=name, kind=kind, rc=rc, why=row['why'],
                 tail=(out.strip().splitlines() or [''])[-1][:300], stderr=err.strip()[-200:])
        mc.alert('launch_chain:failed:%s:%s' % (folder.name, name),
                 'Launch chain: launch.py %s in %s exited %d; not launched. The chain tries again after %d minutes; '
                 'read the folder before then if this repeats.' % (name, folder.name, rc, RETRY_MINUTES))
        return False
    mc.trace(NAME, 'launch', folder=folder.name, step=name, kind=kind, rc=0, why=row['why'],
             tail=(out.strip().splitlines() or [''])[-1][:300])
    if kind == 'ledger' and step.get('watch', True) and (folder / 'watch.py').is_file():
        mc.trace(NAME, 'watch_started', folder=folder.name, step=name, pid=start_watcher(folder, name))
    if kind == 'admit':
        after_admit_launch(folder, step)
    return True


def after_admit_launch(folder, step):
    """Seckin 18 Nov 20:37 (no process blocks another): the admission runs detached and the pass goes on at once;
    the parts are planned when a later reading finds admission.json full. The step counts as launching while its
    admission is visibly at work (admit_active), else for admit_wait_minutes after the launch."""
    mc.trace(NAME, 'admit_detached', folder=folder.name, step=step['step'],
             admitted=admitted_all(folder, step), window_minutes=step.get('admit_wait_minutes', ADMIT_WAIT_MINUTES))


def admit_active(folder, step, now=None):
    """True while an admission is visibly at work: its staging folder exists (never through a link), or admit.log
    was written within ADMIT_LOG_QUIET_MINUTES (the capacity wait writes a line every 2 minutes)."""
    folder = Path(folder)
    out = folder / Path(step.get('admission', 'admitted/admission.json')).parts[0]
    staging = out.with_name(out.name + '.staging')
    if staging.is_dir() and not is_reparse(staging):
        return True
    log = folder / 'admit.log'
    try:
        age = (now or time.time()) - log.stat().st_mtime
    except OSError:
        return False
    return age < ADMIT_LOG_QUIET_MINUTES * 60


def ledger_failure_result(rc):
    """The trace result for a ledger launch call that exited non-zero (or timed out) after launch_started."""
    return UNCONFIRMED


def seal_refused_stale(rc, text):
    """A seal refused because its request read copy went stale: a non-zero exit saying so (an exit 0 never is)."""
    return rc != 0 and STALE_MARK in text.lower()


def stale_in_a_row(folder_name, step_name):
    """request_stale lines of this seal since its last confirmed launch."""
    n = 0
    for x in reversed(mc.read_trace()):
        if x.get('mechanism') != NAME or x.get('folder') != folder_name or x.get('step') != step_name:
            continue
        if x.get('result') == 'launch':
            break
        n += x.get('result') == 'request_stale'
    return n


def stale_request_of(chain, step):
    """The request step a ledger step depends on directly, or None."""
    kinds = {s['step']: s for s in chain['steps']}
    for p in step.get('after', []):
        ref = kinds.get(p if isinstance(p, str) else p.get('step'))
        if ref and ref['kind'] == 'request':
            return ref
    return None


def start_watcher(folder, step_name):
    # Detached (0x8) and a new process group (0x200), with the no-window flag through mc.no_window (HIDDEN-A).
    proc = subprocess.Popen(interpreter() + [str(Path(folder) / 'watch.py'), step_name], cwd=str(folder), env=child_env(),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=(0x00000008 | 0x00000200 | mc.no_window()) if os.name == 'nt' else 0,
                            start_new_session=os.name != 'nt')
    return proc.pid


def flag_problems(folder_name, steps):
    for name, row in steps.items():
        if row['state'] == 'failed':
            mc.alert('launch_chain:step_failed:%s:%s' % (folder_name, name),
                     'Launch chain: %s %s failed (%s); the steps after it wait for the lead.' % (folder_name, name, row['why']),
                     every=10 ** 9)
        elif row['state'] == 'unconfirmed':
            mc.alert('launch_chain:unconfirmed:%s:%s' % (folder_name, name), 'Launch chain: %s' % row['why'])


def passes_for(chain):
    """Readings a folder gets in one pass: enough for every step to follow the one before in the same move."""
    return len(chain['steps']) + 1


def budget_spent(started_s):
    """started_s is a time.monotonic() reading: a wall-clock step (a VM or WSL clock resync) never moves the budget."""
    return time.monotonic() - started_s > PASS_BUDGET_S


def seal_exempt(chain, step, follow):
    """The seal that follows the request this pass just wrote is begun even after the budget (it must follow)."""
    return bool(follow) and step['kind'] == 'ledger' and stale_request_of(chain, step) is not None


def skip_without_chain(folder):
    """A folder whose chain.json was held (renamed) or removed after the listing is skipped cleanly: one trace
    line, no folder error (the REBUILD_J1_B1 TypeError of 18 Nov 19:42)."""
    mc.trace(NAME, 'skipped', folder=Path(folder).name, why='no chain.json now (held or removed after the listing)')
    return True


def run_folder(folder, root, started_s, tally):
    chain = load_chain(folder)
    if chain is None and skip_without_chain(folder):
        return
    follow = False          # True right after this pass wrote a request: its seal is next, budget or not
    for _ in range(passes_for(chain)):
        if budget_spent(started_s) and not follow:
            mc.trace(NAME, 'deferred', folder=folder.name, why='the pass has run %d minutes; no new launch is begun'
                     % (PASS_BUDGET_S // 60))
            return
        plans, errs = plan(root, folders=[folder], write_state=True)
        if errs:
            raise ChainError(errs[folder.name])
        for s in chain['steps']:
            if s['kind'] == 'request':
                retire_marker(folder, s)
        steps = plans[folder.name]
        flag_problems(folder.name, steps)
        ready = [s for s in chain['steps'] if steps[s['step']]['state'] == 'ready']
        started = False
        for step in ready:
            if budget_spent(started_s) and not seal_exempt(chain, step, follow):
                mc.trace(NAME, 'deferred', folder=folder.name, step=step['step'],
                         why='the pass has run %d minutes; no new launch is begun' % (PASS_BUDGET_S // 60))
                return
            follow = False
            if step['kind'] == 'request' and tally['requests'] >= 1:
                mc.trace(NAME, 'deferred', folder=folder.name, step=step['step'], why='one request a pass')
                continue
            if launch_step(folder, step, steps[step['step']], chain):
                tally['launched'].append('%s:%s' % (folder.name, step['step']))
                tally['requests'] += step['kind'] == 'request'
                started = True
                if step['kind'] == 'request':
                    follow = True
                    break  # read again at once: the seal follows its request with nothing between
            else:
                tally['refused'].append('%s:%s' % (folder.name, step['step']))
                return     # a failed preflight or launch holds the rest of this folder for this pass
        if not started:
            return


FOLDER_FAULTS = (Exception,)


def run_once(root=None):
    ok, held = acquire_lock()
    if not ok:
        mc.trace(NAME, 'locked', held=held)
        return 0
    tally = {'launched': [], 'refused': [], 'requests': 0}
    errors = {}
    started_s = time.monotonic()
    try:
        for folder in chain_folders(root):
            try:
                run_folder(folder, root, started_s, tally)
            except FOLDER_FAULTS as exc:  # one folder's fault never stops the others
                errors[folder.name] = '%s: %s' % (type(exc).__name__, str(exc)[:300])
                mc.trace(NAME, 'folder_error', folder=folder.name, error=errors[folder.name])
                mc.alert('launch_chain:folder:%s' % folder.name,
                         'Launch chain: %s could not be handled: %s' % (folder.name, errors[folder.name][:200]))
        mc.trace(NAME, 'ok', launched=tally['launched'], refused=tally['refused'], errors=errors,
                 seconds=round(time.monotonic() - started_s))
    finally:
        release_lock()
    return 0


def clear(spec, root=None):
    """Release a held step: FOLDER:STEP must name a step of a folder's chain.json; written under the lock."""
    folder_name, _, step_name = spec.partition(':')
    folder = Path(root or root_dir()) / folder_name
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', folder_name) or folder_name in ('.', '..'):
        return 2, 'refused: %r is not a folder name' % folder_name
    try:
        chain = load_chain(folder)
    except ChainError as exc:
        return 2, 'refused: %s' % exc
    if not chain or step_name not in [s['step'] for s in chain['steps']]:
        return 2, 'refused: %s names no step of a chain.json' % spec
    ok, held = acquire_lock()
    if not ok:
        return 3, 'refused: a pass holds the lock (%s); try again' % held
    try:
        mc.trace(NAME, 'cleared', folder=folder_name, step=step_name, why='--clear by hand')
    finally:
        release_lock()
    return 0, 'cleared %s' % spec


def print_plan(plans, errors):
    would = []
    for folder, steps in plans.items():
        print('== %s' % folder)
        for name, row in steps.items():
            print('  %-8s %-11s %s' % (name, row['state'], row['why']))
            if row['state'] == 'ready':
                would.append('%s %s (%s; preflight runs first)' % (folder, name, row['why']))
    for folder, error in errors.items():
        print('== %s: UNREADABLE: %s' % (folder, error))
    print('WOULD LAUNCH: ' + ('; '.join(would) if would else 'nothing'))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--dry-run', action='store_true', help='print each step and what would launch; write nothing')
    ap.add_argument('--root', help='the folder holding the launch folders (default external/s05 of the main checkout)')
    ap.add_argument('--clear', metavar='FOLDER:STEP', help='release a held step (one trace line, under the lock)')
    args = ap.parse_args(argv)
    if args.clear:
        code, text = clear(args.clear, args.root)
        print(text)
        return code
    if args.dry_run:
        print_plan(*plan(args.root, write_state=False))
        return 0
    return run_once(args.root)


if __name__ == '__main__':
    raise SystemExit(main())
