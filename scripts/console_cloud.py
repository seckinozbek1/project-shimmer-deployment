"""The console's cloud mode: "On a rented cloud machine" / "Kiralık bulut makinesinde" (D-S49 item 3,
D-S50 item 3, D-S51 step 3(e)).

From the console, the user runs a real review on a rented machine started for the run and shut
down after it. Nothing here goes around the sealed, bound path: a review is staged as a workload
folder, sealed by `tools/prepare_ordinary_final_run.py`, its assets verified, bound, reverified
locally, preflighted live, and launched only by `tools/ordinary_final_bound_cloud.py --detach`,
whose guard, ledger lines, deadline and reaper are the loop's own (LOOP-LAUNCH-A). No bound
controller file is changed by this module and none is imported to launch.

What this module never does:
  - read, hold, print or return the provider credential. It only asks
    `agent_wrapper.resolve_config_path()` whether a credential file can be FOUND, and answers yes
    or no; the file is read by the provider adapter inside the child processes, as for every loop
    launch (CONTROLLER-BINDING, `credential_path()`);
  - write a ledger line, open a budget or change one. With no `budget_open` line it refuses;
  - prepare or launch a sealed run (SEALED-RUN-A runs are role B's, never the console's);
  - launch without the user's explicit confirmation: the cap shown, to the cent, echoed back with
    a one-time code that expires after 15 minutes.

The forecast the seal carries comes from `config/cloud_forecast_basis.json`, whose every entry
says whether it is MEASURED (date and machine) or an ESTIMATE (and what it rests on); the console
shows which. No maximum number of instances is shown: there is none (D-S95); the total budget
and its hard stop are the only limit.

Launches from the console write the loop's private ledger (the one the reaper reads, which is the
only ledger the bound wrapper accepts) under the purpose `console-<plan id>`, and run in their own
folder under `output/cloud/<plan id>/`. They share the loop's one budget and its reaper on purpose;
there is no instance limit (D-S95).
"""
import hashlib
import hmac
import json
import math
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
for _path in (str(ROOT / 'scripts'), str(TOOLS), str(TOOLS / 'loop')):
    if _path not in sys.path:
        sys.path.append(_path)

import cloud_run_common  # noqa: E402
import instance_reaper  # noqa: E402
import loop_budget_guard as guard  # noqa: E402

NAME = {'en': 'On a rented cloud machine', 'tr': 'Kiralık bulut makinesinde'}
DOCUMENTS = {'en': 'Your documents are copied to the rented machine for this review and deleted with it when '
                   'it is shut down.',
             'tr': 'Belgeleriniz bu inceleme için kiralık makineye kopyalanır ve makine kapatılınca onunla '
                   'birlikte silinir.'}
GONE = {'en': 'The rented machine and its copy of your documents are gone.',
        'tr': 'Kiralık makine ve belgelerinizin oradaki kopyası artık yok.'}
NONCE_SECONDS = 900
# Where the controller unpacks the collected evidence of a B3 run: the pipeline's own run folder.
DELIVERABLES = ('downloaded', 'evidence', 'run', 'deliverables')
RUN_FILES = '_run'
PURPOSE_PREFIX = 'console-'
PLAN_ID = re.compile(r'[0-9a-f]{12}')
FILE_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,120}')
CAP_TEXT = re.compile(r'[0-9]{1,6}\.[0-9]{2}')
SETTINGS_FIELDS = ('reuse_assets', 'wheelhouse', 'storage_forecast_usd', 'asset_copy')
SETTINGS_NAME = 'console_settings.json'
BASIS_PATH = ROOT / 'config' / 'cloud_forecast_basis.json'
STEP_TIMEOUT_SECONDS = 3 * 3600
CREDENTIAL_MISSING = ('No provider credential file found; set SHIMMER_CONFIG_PATH to your own credential file '
                      'outside the repository')

# The preparation, in order. Each is one child process or one local write; every one but
# `stage` and `bind` is an existing tool, run exactly as the loop runs it.
STEPS = ('stage', 'inventory', 'seal', 'verify_assets', 'bind', 'reverify', 'declare_asset_copy', 'live_preflight')

# The parts of a finished run (D-S49 item 4), read from the controller's own timing receipts.
# Loading the models happens inside the review and is not timed apart.
PARTS = (
    ('start_machine', ('ssh_ready',)),
    ('copy_files', ('assets_transfer', 'support_transfer', 'asset_copy_probe', 'asset_copy_seed', 'asset_copy_use',
                    'archive_integrity', 'extract_payload')),
    ('prepare_machine', ('fresh_directory', 'create_environment', 'install_pinned_wheels', 'dependency_closure',
                         'python_gate', 'gpu_metadata', 'watchdog_receipt_transfer')),
    ('review', ('ordinary_workload',)),
    ('collect_results', ('stop_workload', 'pack_evidence', 'evidence_hash', 'evidence_download', 'final_gpu_state')),
)


class Refused(Exception):
    """A one-line refusal the console shows as it is."""


def refuse(condition, message):
    if not condition:
        raise Refused(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.part')
    temporary.write_text(json.dumps(value, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    temporary.replace(path)


def sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def utc(epoch):
    return datetime.fromtimestamp(float(epoch), timezone.utc).isoformat()


# ----------------------------------------------------------------------------------------------
# What is set up: the credential (located only), the operator's settings, the budget.
# ----------------------------------------------------------------------------------------------
def credential_located():
    """True when a provider credential file can be FOUND by the repository's one resolver. The
    file is never opened here and its path never leaves this function."""
    import agent_wrapper
    return agent_wrapper.resolve_config_path() is not None


def cloud_root():
    return ROOT / 'output' / 'cloud'


def settings_path():
    return cloud_root() / SETTINGS_NAME


def read_settings():
    """The operator's deployment-local settings for cloud mode, written by hand, never by the
    console: the verified asset bundle to reuse, the wheelhouse, the storage forecast and,
    optionally, the operator's provider-side asset copy (ASSET-COPY-A)."""
    path = settings_path()
    refuse(path.is_file(), 'Cloud mode is not set up: the operator writes output/cloud/%s '
                           '(docs/CLOUD_CONSOLE.md)' % SETTINGS_NAME)
    try:
        value = read(path)
    except ValueError:
        raise Refused('output/cloud/%s is not JSON' % SETTINGS_NAME)
    refuse(isinstance(value, dict) and set(value) <= set(SETTINGS_FIELDS)
           and all(k in value for k in SETTINGS_FIELDS[:3]),
           'output/cloud/%s needs reuse_assets, wheelhouse and storage_forecast_usd (and optionally asset_copy)'
           % SETTINGS_NAME)
    reuse = Path(value['reuse_assets'])
    try:
        verified = read(reuse / 'asset_verification.json').get('passed') is True
    except (OSError, ValueError):
        verified = False
    refuse(verified and (reuse / 'assets.tar').is_file(), 'The asset bundle to reuse has no passed asset verification')
    refuse(Path(value['wheelhouse']).is_dir(), 'The wheelhouse folder is missing')
    storage = value['storage_forecast_usd']
    refuse(isinstance(storage, (int, float)) and not isinstance(storage, bool) and storage >= 0,
           'storage_forecast_usd must be a number of dollars')
    copy = value.get('asset_copy')
    refuse(copy is None or (isinstance(copy, dict) and set(copy) == {'filesystem_name', 'mount'}
                            and isinstance(copy['filesystem_name'], str) and copy['filesystem_name']
                            and isinstance(copy['mount'], str) and copy['mount'].startswith('/')),
           'asset_copy is null or {filesystem_name, mount}')
    return dict(reuse_assets=reuse, wheelhouse=Path(value['wheelhouse']), storage_forecast_usd=float(storage),
                asset_copy=copy)


def launch_ledger():
    """The ledger a console launch writes: the private one the reaper reads (the bound wrapper
    accepts no other). Resolved at call time."""
    return Path(instance_reaper.PRIVATE_LEDGER)


def ledger_rows():
    rows = []
    for path in guard.reaper_ledgers():
        rows.extend(instance_reaper.read_ledger(path))
    return rows


def budget_state(now=None):
    """The budget as the guard reads it, read-only: no lock taken, no line written."""
    now = time.time() if now is None else now
    rows = ledger_rows()
    state = dict(budget_open=any(r.get('event') == 'budget_open' for r in rows))
    if not state['budget_open']:
        return state
    budget, hard_stop = instance_reaper.budget_figures(rows)
    if budget is None or hard_stop is None:
        return dict(state, budget_open=False)
    spend, running, caps, _ = guard.ledger_state(guard.reaper_ledgers(), now)
    ceiling = guard.cap_ceiling(budget, hard_stop)
    return dict(state, budget_usd=budget, hard_stop_usd=hard_stop, warning_usd=instance_reaper.warning_figure(rows),
                spend_usd=round(spend, 2),
                running_caps_usd=round(caps, 2), running_instances=len(running),
                left_usd=round(ceiling - spend - caps, 2))


def require_budget(now=None):
    state = budget_state(now)
    refuse(state['budget_open'], 'No budget is open: the operator writes the budget_open line in the ledger; '
                                 'the console never writes one')
    return state


def forecast_basis(asset_copy):
    """The forecast entry for this launch, refused unless it says what it is."""
    entry = read(BASIS_PATH)['entries']['with_asset_copy' if asset_copy else 'without_asset_copy']
    kind = entry.get('kind')
    refuse(kind in ('measured', 'estimate'), 'The forecast basis must say measured or estimate')
    if kind == 'measured':
        on = entry.get('measured_on') or {}
        refuse(isinstance(on, dict) and on.get('date') and on.get('machine'),
               'A measured forecast names its date and machine')
    else:
        refuse(isinstance(entry.get('rests_on'), str) and entry['rests_on'], 'An estimate says what it rests on')
    minutes = entry.get('minutes')
    refuse(isinstance(minutes, (int, float)) and minutes > 0, 'The forecast basis has no minutes')
    return entry


def setup_state(now=None):
    """What the console's first cloud screen shows: is everything in place, and why not."""
    out = dict(name=NAME, documents=DOCUMENTS, credential_found=credential_located())
    try:
        settings = read_settings()
        out.update(settings_ready=True, asset_copy=settings['asset_copy'] is not None)
    except Refused as error:
        out.update(settings_ready=False, settings_problem=str(error))
    out['budget'] = budget_state(now)
    return out


# ----------------------------------------------------------------------------------------------
# Staging the user's documents as a workload folder the sealer reads.
# ----------------------------------------------------------------------------------------------
def stage(folder, targets, grounding, conventions):
    """Write `context/`, `conventions/` and `_review_targets.json` (source operator), the layout
    `tools/stage_workload.py` writes and the sealer reads. Each argument maps a file name to its
    bytes. A name read like an answer key is refused, as stage_workload refuses it."""
    import stage_workload
    refuse(targets, 'Choose at least one document to review')
    refuse(conventions, 'Choose the review conventions file')
    names = [*targets, *grounding, *conventions]
    for name in names:
        refuse(FILE_NAME.fullmatch(name) is not None and '..' not in name,
               'A file name may hold letters, digits, dot, hyphen and underscore only: %s' % name[:60])
        refuse(not stage_workload.key_like(name), 'A file named like an answer key is refused: %s' % name)
    refuse(len(set(targets) | set(grounding)) == len(targets) + len(grounding), 'Two documents share one name')
    refuse(len(set(conventions)) == len(conventions), 'Two conventions files share one name')
    folder = Path(folder)
    for name, data in [*targets.items(), *grounding.items()]:
        (folder / 'context').mkdir(parents=True, exist_ok=True)
        (folder / 'context' / name).write_bytes(data)
    for name, data in conventions.items():
        (folder / 'conventions').mkdir(parents=True, exist_ok=True)
        (folder / 'conventions' / name).write_bytes(data)
    manifest = dict(source='operator', targets=sorted(targets), grounding=sorted(grounding), prior=[])
    (folder / '_review_targets.json').write_text(json.dumps(manifest, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


# ----------------------------------------------------------------------------------------------
# The preparation chain and the launch, as child processes.
# ----------------------------------------------------------------------------------------------
def run_child(argv, log):
    """One child process, hidden (HIDDEN-A), its output into `log`. Returns its exit code."""
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    with open(log, 'ab') as stream:
        try:
            done = subprocess.run([str(a) for a in argv], cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=stream,
                                  stderr=subprocess.STDOUT, timeout=STEP_TIMEOUT_SECONDS,
                                  creationflags=cloud_run_common.no_window())
        except subprocess.TimeoutExpired:
            return 124
    return done.returncode


def python():
    return [sys.executable, '-X', 'utf8']


def step_argv(step, plan, settings):
    """The argv of one preparation step, or None for a local step."""
    folder = Path(plan['folder'])
    bundle = folder / 'bundle'
    if step == 'inventory':
        return [*python(), TOOLS / 'console_cloud_inventory.py', '--out', folder / 'inputs' / 'provider_inventory.json']
    if step == 'seal':
        return [*python(), TOOLS / 'prepare_ordinary_final_run.py', '--output-dir', bundle,
                '--reuse-assets', settings['reuse_assets'], '--inputs-from', folder / 'inputs',
                '--workload', folder / 'workload', '--exposure', 'exposed', '--arm', 'B3',
                '--ledger', launch_ledger(), '--forecast-minutes', repr(float(plan['forecast_minutes'])),
                '--storage-forecast-usd', repr(settings['storage_forecast_usd']), '--uncompared']
    if step == 'verify_assets':
        return [*python(), TOOLS / 'verify_ordinary_final_assets.py', '--bundle', bundle,
                '--wheelhouse', settings['wheelhouse']]
    if step == 'reverify':
        return [*python(), TOOLS / 'ordinary_final_bound_reverify.py', '--bundle', bundle]
    if step == 'declare_asset_copy':
        copy = settings['asset_copy']
        if copy is None:
            return None
        return [*python(), TOOLS / 'declare_asset_copy.py', '--bundle', bundle,
                '--filesystem-name', copy['filesystem_name'], '--mount', copy['mount']]
    if step == 'live_preflight':
        return [*python(), TOOLS / 'ordinary_final_bound_preflight.py', '--bundle', bundle]
    return None


def bind(bundle):
    """authorization_binding.json from the sealed bundle's own digests, as every loop launch
    carries it. It binds identity only; the spend is authorized by the user's confirmation."""
    bundle = Path(bundle)
    manifest = read(bundle / 'execution_manifest.json')
    binding = dict(bundle=bundle.as_posix(), manifest_sha256=sha(bundle / 'execution_manifest.json'),
                   seal_sha256=sha(bundle / 'seal.json'), project_sha256=sha(bundle / 'project.tar.gz'),
                   assets_sha256=manifest['assets_archive']['sha256'], source_commit=manifest['source_commit'],
                   preparation_commit=manifest['source_commit'])
    write(bundle / 'authorization_binding.json', binding)
    return binding


def instance_name(bundle):
    binding = read(Path(bundle) / 'authorization_binding.json')
    return guard.instance_name(binding['preparation_commit'][:7] + '-' + binding['manifest_sha256'][:8])


def sealed_quote(bundle, settings):
    """The figures the seal carries, for the confirmation screen."""
    m = read(Path(bundle) / 'execution_manifest.json')
    first = (m.get('instance_candidates') or [{}])[0]
    return dict(forecast_minutes=m['forecast_minutes'], forecast_usd=round(float(m['forecast_usd']), 2),
                cap_usd=float(m['per_run_cap_usd']), cap_text=cap_text(m['per_run_cap_usd']),
                instance_type=first.get('type'), hourly_rate_usd=first.get('max_hourly_rate'),
                storage_forecast_usd=settings['storage_forecast_usd'],
                upload_in_forecast=not (Path(bundle) / 'asset_copy_declaration.json').is_file())


def cap_text(cap):
    """The cap to the cent, rounded UP, so "up to" is never below the sealed cap."""
    return '%.2f' % (math.ceil(round(float(cap) * 100, 6)) / 100)


class Desk:
    """The plans of one server process. Plans live on disk under output/cloud/<plan id>/; the
    one-time confirmation codes live only in this process, so a restart asks for a new one."""

    def __init__(self, runner=run_child, clock=time.time, threads=True):
        self.runner, self.clock, self.threads = runner, clock, threads
        self.lock = threading.Lock()
        self.codes = {}

    # -- plans on disk --------------------------------------------------------------------------
    def folder(self, plan_id):
        refuse(isinstance(plan_id, str) and PLAN_ID.fullmatch(plan_id) is not None, 'Unknown plan')
        folder = cloud_root() / plan_id
        refuse((folder / 'plan.json').is_file(), 'Unknown plan')
        return folder

    def plan(self, plan_id):
        return read(self.folder(plan_id) / 'plan.json')

    def save(self, plan):
        write(Path(plan['folder']) / 'plan.json', plan)

    def plans(self):
        root = cloud_root()
        if not root.is_dir():
            return []
        out = []
        for item in sorted(root.iterdir()):
            if PLAN_ID.fullmatch(item.name) and (item / 'plan.json').is_file():
                out.append(self.status(item.name, observe=False))
        return out

    # -- preparing ------------------------------------------------------------------------------
    def prepare(self, targets, grounding, conventions, exposure=None):
        refuse(exposure in (None, '', 'exposed'), 'A sealed run is never started from the console')
        refuse(credential_located(), CREDENTIAL_MISSING)
        settings = read_settings()
        require_budget(self.clock())
        basis = forecast_basis(settings['asset_copy'] is not None)
        plan_id = secrets.token_hex(6)
        folder = cloud_root() / plan_id
        folder.mkdir(parents=True)
        plan = dict(plan_id=plan_id, folder=folder.as_posix(), created_utc=utc(self.clock()), state='preparing',
                    purpose=PURPOSE_PREFIX + plan_id, forecast_minutes=basis['minutes'], basis=basis,
                    targets=sorted(targets), steps=[dict(name=s, state='waiting') for s in STEPS])
        self.save(plan)
        stage(folder / 'workload', targets, grounding, conventions)
        plan['steps'][0].update(state='done', seconds=0.0)
        self.save(plan)
        if self.threads:
            threading.Thread(target=self._prepare, args=(plan_id, settings), daemon=True).start()
        else:
            self._prepare(plan_id, settings)
        return plan_id

    def _prepare(self, plan_id, settings):
        plan = self.plan(plan_id)
        folder = Path(plan['folder'])
        logs = folder / 'logs'
        try:
            (folder / 'inputs').mkdir(parents=True, exist_ok=True)
            shutil.copyfile(settings['reuse_assets'] / 'runtime.candidate.lock', folder / 'inputs' / 'runtime.candidate.lock')
            for step in plan['steps'][1:]:
                started = self.clock()
                step.update(state='running', started_epoch=started)
                self.save(plan)
                if step['name'] == 'bind':
                    bind(folder / 'bundle')
                    code = 0
                else:
                    argv = step_argv(step['name'], plan, settings)
                    if argv is None:
                        step.update(state='not_needed', seconds=0.0)
                        self.save(plan)
                        continue
                    code = self.runner(argv, logs / (step['name'] + '.log'))
                step.update(seconds=round(self.clock() - started, 1))
                if code != 0:
                    step.update(state='failed', exit_code=code)
                    plan.update(state='failed', error=self.last_line(logs / (step['name'] + '.log')) or
                                'The %s step stopped with exit %d' % (step['name'], code))
                    self.save(plan)
                    return
                step['state'] = 'done'
                self.save(plan)
            plan.update(state='ready', quote=sealed_quote(folder / 'bundle', settings))
            self.save(plan)
        except (Refused, OSError, ValueError, KeyError) as error:
            plan.update(state='failed', error=str(error) or type(error).__name__)
            self.save(plan)

    @staticmethod
    def last_line(log):
        """The last line a step wrote: the existing tools refuse in one line, never with a key."""
        try:
            lines = [l.strip() for l in Path(log).read_text(encoding='utf-8', errors='replace').splitlines() if l.strip()]
        except OSError:
            return None
        return lines[-1][:300] if lines else None

    # -- confirming and launching ---------------------------------------------------------------
    def confirmation(self, plan_id):
        """A one-time code for this plan's sealed cap, valid for NONCE_SECONDS."""
        plan = self.plan(plan_id)
        refuse(plan['state'] == 'ready', 'This plan is not ready to start')
        budget = require_budget(self.clock())
        code = secrets.token_urlsafe(24)
        expires = self.clock() + NONCE_SECONDS
        with self.lock:
            self.codes = {k: v for k, v in self.codes.items() if v['expires'] > self.clock()}
            self.codes[self.digest(code)] = dict(plan_id=plan_id, cap_text=plan['quote']['cap_text'], expires=expires)
        return dict(code=code, expires_utc=utc(expires), expires_in_seconds=NONCE_SECONDS, quote=plan['quote'],
                    budget=budget, basis=plan['basis'])

    @staticmethod
    def digest(code):
        return hashlib.sha256(str(code).encode('utf-8')).hexdigest()

    def take_code(self, plan_id, code, confirm_cap_usd):
        """The code is spent on its first use, whatever the outcome."""
        with self.lock:
            entry = self.codes.pop(self.digest(code), None)
        refuse(entry is not None and hmac.compare_digest(entry['plan_id'], plan_id),
               'The confirmation code is unknown, used, or for another plan')
        refuse(self.clock() <= entry['expires'], 'The confirmation code expired; ask for a new one')
        refuse(isinstance(confirm_cap_usd, str) and CAP_TEXT.fullmatch(confirm_cap_usd) is not None
               and confirm_cap_usd == entry['cap_text'],
               'The amount confirmed is not the cap shown (%s USD)' % entry['cap_text'])
        return entry

    def launch(self, plan_id, code, confirm_cap_usd):
        entry = self.take_code(plan_id, code, confirm_cap_usd)
        plan = self.plan(plan_id)
        refuse(plan['state'] == 'ready', 'This plan is not ready to start')
        refuse(plan['quote']['cap_text'] == entry['cap_text'], 'The plan changed after the code was given')
        refuse(credential_located(), CREDENTIAL_MISSING)
        settings = read_settings()
        require_budget(self.clock())
        folder = Path(plan['folder'])
        bundle = folder / 'bundle'
        refuse(not (bundle / 'LAUNCH_INTENT.json').exists() and not (bundle / 'RUN_FOLDER.json').exists(),
               'This plan was launched already')
        argv = self.launch_argv(plan, settings)
        plan.update(state='launching', launch_requested_utc=utc(self.clock()))
        self.save(plan)
        code_ = self.runner(argv, folder / 'logs' / 'launch.log')
        if code_ != 0:
            plan.update(state='failed', error=self.last_line(folder / 'logs' / 'launch.log') or
                        'The launch stopped with exit %d' % code_)
            self.save(plan)
            raise Refused(plan['error'])
        plan.update(state='launched', launched_epoch=self.clock(), instance_name=instance_name(bundle))
        self.save(plan)
        return plan_id

    @staticmethod
    def launch_argv(plan, settings):
        folder = Path(plan['folder'])
        bundle = folder / 'bundle'
        argv = [*python(), TOOLS / 'ordinary_final_bound_cloud.py', '--bundle', bundle, '--output-dir', folder / 'run',
                '--ledger', launch_ledger(), '--purpose', plan['purpose'],
                '--forecast-minutes', repr(float(read(bundle / 'execution_manifest.json')['forecast_minutes'])),
                '--storage-forecast-usd', repr(settings['storage_forecast_usd'])]
        if not (bundle / 'asset_copy_declaration.json').is_file():
            argv.append('--forecast-includes-upload')
        return [*argv, '--detach']

    # -- while it runs and after ----------------------------------------------------------------
    def status(self, plan_id, observe=True, observations=None):
        plan = self.plan(plan_id)
        out = {k: plan.get(k) for k in ('plan_id', 'state', 'created_utc', 'purpose', 'targets', 'error', 'quote',
                                         'basis', 'launch_requested_utc')}
        out.update(name=NAME, documents=DOCUMENTS,
                   steps=[{k: s.get(k) for k in ('name', 'state', 'seconds')} for s in plan['steps']])
        now = self.clock()
        running = next((s for s in plan['steps'] if s['state'] == 'running'), None)
        if plan['state'] == 'preparing':
            done = sum(1 for s in plan['steps'] if s['state'] in ('done', 'not_needed'))
            out['preparation'] = dict(done=done, total=len(plan['steps']),
                                      step=running['name'] if running else None,
                                      step_seconds=round(now - running['started_epoch'], 1) if running else None,
                                      note='Each step reports only on completion; the count of steps done is '
                                           'the measured progress')
        if plan['state'] in ('launched', 'finished'):
            out.update(self.run_state(plan, now, observe, observations))
            if out.get('outcome') and plan['state'] != 'finished':
                plan['state'] = out['state'] = 'finished'
                self.save(plan)
        return out

    def run_state(self, plan, now, observe, observations):
        bundle = Path(plan['folder']) / 'bundle'
        try:
            folder = Path(read(bundle / 'RUN_FOLDER.json')['run_folder'])
        except (OSError, ValueError, KeyError):
            folder = None
        if folder is None:
            try:
                pid = read(bundle / 'controller_process.json').get('pid')
            except (OSError, ValueError):
                pid = None
            if guard.pid_alive(pid) is False:
                return dict(run='stopped_before_launch', run_error=self.last_line(bundle / 'controller_detached.log'))
            return dict(run='starting', progress='No instance is requested yet: the guard is deciding')
        out = dict(run='running')
        try:
            out['phase'] = read(folder / 'CURRENT_PHASE.json').get('phase')
        except (OSError, ValueError):
            out['phase'] = None
        if (folder / 'TERMINATION_VERIFIED.json').is_file():
            out['outcome'] = outcome(folder, plan.get('instance_name'))
            out['run'] = 'finished'
            return out
        if observe:
            import ordinary_final_progress
            out['progress'] = ordinary_final_progress.reading_for(folder, observations=observations, now=now)
        return out

    # -- the deliverables of a finished run -----------------------------------------------------
    def deliverable(self, plan_id, doc_id, name=None):
        """The path of one listed document folder (name None) or one listed file, of a finished
        plan only. Only what deliverables_listing lists is ever served: a name is matched against
        the listing, never joined onto a path first."""
        state = self.status(plan_id, observe=False)
        o = state.get('outcome')
        refuse(o is not None and o['deliverables']['available'], 'No results for this plan')
        root = Path(o['deliverables']['root'])
        if doc_id == RUN_FILES:
            listed = {f['name'] for f in o['deliverables']['run_files']}
            refuse(name in listed, 'Unknown plan')
            return root / name
        document = next((d for d in o['deliverables']['documents'] if d['doc_id'] == doc_id), None)
        refuse(document is not None, 'Unknown plan')
        if name is None:
            return root / doc_id
        refuse(name in {f['name'] for f in document['files']}, 'Unknown plan')
        return root / doc_id / name


def deliverables_listing(folder):
    """Each document's files and the run's own files, from the collected run folder."""
    root = Path(folder).joinpath(*DELIVERABLES)
    if not root.is_dir():
        return dict(available=False, why='The results were not collected into this run folder', documents=[],
                    run_files=[])
    documents, run_files = [], []
    for item in sorted(root.iterdir()):
        if item.is_dir():
            files = [dict(name=p.relative_to(item).as_posix(), bytes=p.stat().st_size)
                     for p in sorted(item.rglob('*')) if p.is_file()]
            documents.append(dict(doc_id=item.name, files=files))
        elif item.is_file():
            run_files.append(dict(name=item.name, bytes=item.stat().st_size))
    return dict(available=True, root=root.as_posix(), documents=documents, run_files=run_files)


def measured_parts(folder):
    """Minutes per part of a finished run, from the controller's own receipts. A timing receipt
    no part names is counted under `other`, so nothing is dropped."""
    folder = Path(folder)
    seconds = {name: 0.0 for name, _ in PARTS}
    seconds['other'] = 0.0
    named = {phase: part for part, phases in PARTS for phase in phases}
    for path in sorted(folder.glob('*_timing.json')):
        phase = path.name[:-len('_timing.json')]
        if phase.endswith(('_start', '_collect')):
            continue  # the halves of a detached phase, already inside the phase's own receipt
        base = re.sub(r'_[0-9]+$', '', phase)
        try:
            value = float(read(path).get('seconds') or 0)
        except (OSError, ValueError, TypeError):
            continue
        seconds[named.get(phase, named.get(base, 'other'))] += value
    try:
        seconds['start_machine'] += float(read(folder / 'activation.json').get('seconds') or 0)
    except (OSError, ValueError, TypeError):
        pass
    try:
        seconds['shut_down'] = (float(read(folder / 'TERMINATION_VERIFIED.json')['epoch'])
                                - float(read(folder / 'termination_requested.json')['epoch']))
    except (OSError, ValueError, KeyError, TypeError):
        seconds['shut_down'] = None
    return {k: (None if v is None else round(v / 60, 1)) for k, v in seconds.items()}


def outcome(folder, name):
    """The actual time and cost of a finished run, and whether the machine was shut down."""
    folder = Path(folder)
    term = read(folder / 'TERMINATION_VERIFIED.json')
    try:
        cleanup = read(folder / 'cleanup.json')
    except (OSError, ValueError):
        cleanup = {}
    terminated = (term.get('metadata') or {}).get('status') == 'terminated'
    absent = cleanup.get('own_instance_absent') is True
    line = None
    for row in ledger_rows():
        if row.get('event') == 'termination' and name and row.get('instance_name') == name:
            line = row
    shut_down = terminated and absent
    return dict(shut_down=shut_down, gone=GONE if shut_down else None, deliverables=deliverables_listing(folder),
                provider_status=(term.get('metadata') or {}).get('status'),
                own_instance_absent=absent, terminated_utc=term.get('utc'),
                actual_minutes=line.get('actual_minutes') if line else None,
                actual_cost_usd=line.get('actual_cost') if line else None,
                cost_upper_bound_usd=round(float(term.get('estimated_cost_upper_bound_usd') or 0), 2),
                cost_note='From the ledger and the controller (an upper bound); the provider invoice may differ',
                parts_minutes=measured_parts(folder),
                parts_note='Loading the models happens inside the review and is not timed apart',
                results_folder=folder.relative_to(ROOT).as_posix() if folder.is_relative_to(ROOT) else folder.name)


DESK = Desk()
