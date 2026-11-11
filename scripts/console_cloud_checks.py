"""Proofs for the console's cloud mode (scripts/console_cloud.py, D-S49 item 3), on fakes only.

No network, no provider, no instance, no real ledger: every proof runs in a temporary folder with
a stand-in runner that records the argv each step would run and writes the files the real tool
would. Where a proof guards a rule, the rule is neutralised in memory, the proof must FAIL, the
rule is restored and the proof must PASS. Prints one line per proof and a summary; exit 1 on any
failure.

    py -3.12 -X utf8 scripts/console_cloud_checks.py
"""
import contextlib
import hashlib
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tools'), str(ROOT / 'tools' / 'loop')]

import console_cloud as cc  # noqa: E402
import instance_reaper  # noqa: E402
import loop_budget_guard as guard  # noqa: E402

SENTINEL = 'CLOUD-CONSOLE-PROOF-SENTINEL-' + 'not-a-real-value'
BUDGET_LINE = dict(event='budget_open', time_utc='2026-11-01T00:00:00+00:00', budget_usd=200.0, hard_stop_usd=199.0,
                   a10_reference_price_usd_per_hour=1.29)
NOW = 1794100000.0


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


class FakeRunner:
    """Records each argv; writes what the real step would leave behind."""

    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def __call__(self, argv, log):
        argv = [str(a) for a in argv]
        self.calls.append(argv)
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        tool = Path(argv[3]).name
        if self.fail == tool:
            Path(log).write_text('Some tool line\nRefused: the stand-in step says no\n', encoding='utf-8')
            return 3
        if tool == 'console_cloud_inventory.py':
            out = Path(argv[argv.index('--out') + 1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(dict(instances=[], instance_types=[], images=[], read_only=True)), encoding='utf-8')
        if tool == 'prepare_ordinary_final_run.py':
            bundle = Path(argv[argv.index('--output-dir') + 1])
            bundle.mkdir(parents=True)
            minutes = float(argv[argv.index('--forecast-minutes') + 1])
            forecast = guard.forecast_usd(minutes, 1.29)
            cc.write(bundle / 'execution_manifest.json', dict(
                source_commit='0123456789abcdef0123456789abcdef01234567', forecast_minutes=minutes,
                forecast_usd=forecast, per_run_cap_usd=1.5 * forecast,
                instance_candidates=[dict(type='gpu_1x_a10', max_hourly_rate=1.29)],
                assets_archive=dict(filename='assets.tar', sha256='a' * 64)))
            cc.write(bundle / 'seal.json', dict(exposure='exposed'))
            (bundle / 'project.tar.gz').write_bytes(b'project')
        if tool == 'declare_asset_copy.py':
            bundle = Path(argv[argv.index('--bundle') + 1])
            cc.write(bundle / 'asset_copy_declaration.json', dict(operator_authorized=True))
        if tool == 'ordinary_final_bound_cloud.py':
            bundle = Path(argv[argv.index('--bundle') + 1])
            cc.write(bundle / 'controller_process.json', dict(pid=os.getpid(), detached=True))
        return 0


@contextlib.contextmanager
def sandbox(credential=True, budget=True, settings=True, asset_copy=None):
    """A temporary root: the cloud folder, the two ledgers, the settings, a credential file
    carrying a sentinel value (or none found)."""
    with tempfile.TemporaryDirectory(prefix='shimmer_cloud_console_') as tmp:
        root = Path(tmp)
        private, r_ledger = root / 'private' / 'budget_ledger.jsonl', root / 'roles' / 'R_ledger.jsonl'
        private.parent.mkdir(parents=True)
        private.write_text(json.dumps(BUDGET_LINE) + '\n' if budget else '', encoding='utf-8')
        reuse = root / 'reuse'
        reuse.mkdir()
        (reuse / 'assets.tar').write_bytes(b'assets')
        (reuse / 'runtime.candidate.lock').write_text('lock\n', encoding='utf-8')
        cc.write(reuse / 'asset_verification.json', dict(passed=True))
        (root / 'wheels').mkdir()
        credential_file = root / 'keys' / 'config.py'
        credential_file.parent.mkdir()
        credential_file.write_text('LAMBDA_API_KEY = "%s"\n' % SENTINEL, encoding='utf-8')
        cloud = root / 'output' / 'cloud'
        if settings:
            cc.write(cloud / cc.SETTINGS_NAME, dict(reuse_assets=str(reuse), wheelhouse=str(root / 'wheels'),
                                                     storage_forecast_usd=0.5, asset_copy=asset_copy))
        import agent_wrapper
        located = (lambda: credential_file) if credential else (lambda: None)
        with patch.object(cc, 'cloud_root', lambda: cloud), \
                patch.object(instance_reaper, 'PRIVATE_LEDGER', private), \
                patch.object(instance_reaper, 'R_LEDGER', r_ledger), \
                patch.object(agent_wrapper, 'resolve_config_path', located), \
                patch.dict(os.environ, {'SHIMMER_CONFIG_PATH': str(credential_file)}):
            yield dict(root=root, private=private, cloud=cloud, credential_file=credential_file)


FILES = dict(targets={'memo.md': b'# Memo\n\nA figure: 12 units.\n'}, grounding={'background.md': b'# Background\n'},
             conventions={'review_conventions.md': b'# Conventions\n\n## Rule one\n'})


def ready_desk(**kw):
    runner, clock = FakeRunner(), Clock()
    desk = cc.Desk(runner=runner, clock=clock, threads=False)
    plan_id = desk.prepare(FILES['targets'], FILES['grounding'], FILES['conventions'], **kw)
    return desk, runner, clock, plan_id


def refused(call):
    try:
        call()
    except cc.Refused as error:
        return str(error)
    return None


# ----------------------------------------------------------------------------------------------
# The proofs. Each returns (ok, detail).
# ----------------------------------------------------------------------------------------------
def proof_no_credential_refuses():
    with sandbox(credential=False):
        desk = cc.Desk(runner=FakeRunner(), clock=Clock(), threads=False)
        why = refused(lambda: desk.prepare(FILES['targets'], {}, FILES['conventions']))
        return why == cc.CREDENTIAL_MISSING, 'prepare with no credential file found: %r' % why


def proof_no_budget_refuses_and_writes_nothing():
    with sandbox(budget=False) as box:
        before = box['private'].read_bytes()
        desk = cc.Desk(runner=FakeRunner(), clock=Clock(), threads=False)
        why = refused(lambda: desk.prepare(FILES['targets'], {}, FILES['conventions']))
        unchanged = box['private'].read_bytes() == before and not any(p.name.endswith('.jsonl')
                                                                       for p in box['cloud'].rglob('*'))
        return bool(why) and 'No budget is open' in why and unchanged, 'no budget_open line: %r, ledger unchanged %s' % (
            why, unchanged)


def proof_sealed_refused():
    with sandbox():
        desk = cc.Desk(runner=FakeRunner(), clock=Clock(), threads=False)
        why = refused(lambda: desk.prepare(FILES['targets'], {}, FILES['conventions'], exposure='sealed'))
        return why == 'A sealed run is never started from the console', 'exposure sealed: %r' % why


def proof_chain_is_the_bound_path():
    with sandbox() as box:
        desk, runner, _, plan_id = ready_desk()
        tools = [Path(c[3]).name for c in runner.calls]
        want = ['console_cloud_inventory.py', 'prepare_ordinary_final_run.py', 'verify_ordinary_final_assets.py',
                'ordinary_final_bound_reverify.py', 'ordinary_final_bound_preflight.py']
        seal = runner.calls[1]
        sealed_ok = (seal[seal.index('--exposure') + 1] == 'exposed' and seal[seal.index('--arm') + 1] == 'B3'
                     and Path(seal[seal.index('--ledger') + 1]) == box['private']
                     and '--reuse-assets' in seal and '--workload' in seal)
        workload = box['cloud'] / plan_id / 'workload'
        targets = json.loads((workload / '_review_targets.json').read_text(encoding='utf-8'))
        staged = (targets == dict(source='operator', targets=['memo.md'], grounding=['background.md'], prior=[])
                  and (workload / 'conventions' / 'review_conventions.md').is_file())
        bound = (box['cloud'] / plan_id / 'bundle' / 'authorization_binding.json').is_file()
        state = desk.status(plan_id)
        return (tools == want and sealed_ok and staged and bound and state['state'] == 'ready'
                and state['quote']['upload_in_forecast'] is True), (
            'steps %s, seal exposed B3 on the private ledger %s, staged %s, bound %s, state %s'
            % (tools, sealed_ok, staged, bound, state['state']))


def proof_forecast_says_estimate_or_measured():
    with sandbox():
        desk, _, _, plan_id = ready_desk()
        basis = desk.status(plan_id)['basis']
        estimate = basis['kind'] == 'estimate' and bool(basis['rests_on'])
        # A "measured" entry with no date and machine is refused, never shown as measured.
        bad = dict(entries=dict(without_asset_copy=dict(kind='measured', minutes=30, measured_on={})))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'basis.json'
            path.write_text(json.dumps(bad), encoding='utf-8')
            with patch.object(cc, 'BASIS_PATH', path):
                why = refused(lambda: cc.forecast_basis(False))
        return estimate and why == 'A measured forecast names its date and machine', (
            'shipped basis is an estimate with what it rests on: %s; a measured entry with no date: %r' % (estimate, why))


def proof_launch_needs_cap_and_one_time_code():
    with sandbox() as box:
        desk, runner, clock, plan_id = ready_desk()
        quote = desk.confirmation(plan_id)
        cap = quote['quote']['cap_text']
        wrong = refused(lambda: desk.launch(plan_id, quote['code'], '%.2f' % (float(cap) - 0.01)))
        reused = refused(lambda: desk.launch(plan_id, quote['code'], cap))  # spent by the wrong attempt
        fresh = desk.confirmation(plan_id)
        clock.now += cc.NONCE_SECONDS + 1
        expired = refused(lambda: desk.launch(plan_id, fresh['code'], cap))
        clock.now = NOW
        other = refused(lambda: desk.launch('0' * 12, desk.confirmation(plan_id)['code'], cap))
        launches_before = sum(1 for c in runner.calls if c[3].endswith('ordinary_final_bound_cloud.py'))
        good = desk.confirmation(plan_id)
        desk.launch(plan_id, good['code'], cap)
        argv = [c for c in runner.calls if c[3].endswith('ordinary_final_bound_cloud.py')]
        expected = [*map(str, cc.python()), str(cc.TOOLS / 'ordinary_final_bound_cloud.py'),
                    '--bundle', str(box['cloud'] / plan_id / 'bundle'), '--output-dir', str(box['cloud'] / plan_id / 'run'),
                    '--ledger', str(box['private']), '--purpose', 'console-' + plan_id,
                    '--forecast-minutes', repr(float(desk.plan(plan_id)['forecast_minutes'])),
                    '--storage-forecast-usd', repr(0.5), '--forecast-includes-upload', '--detach']
        ok = (wrong and 'not the cap shown' in wrong and reused and 'unknown, used' in reused and expired
              and 'expired' in expired and other and launches_before == 0 and argv == [expected])
        return ok, ('wrong cap %r; reused %r; expired %r; another plan %r; no launch before %s; argv matches %s'
                    % (wrong, reused, expired, other, launches_before == 0, argv == [expected]))


def proof_asset_copy_drops_upload_flag():
    copy = dict(filesystem_name='shimmer-filesystem', mount='/lambda/nfs/shimmer-filesystem')
    with sandbox(asset_copy=copy):
        desk, runner, _, plan_id = ready_desk()
        declared = any(c[3].endswith('declare_asset_copy.py') for c in runner.calls)
        code = desk.confirmation(plan_id)
        desk.launch(plan_id, code['code'], code['quote']['cap_text'])
        argv = [c for c in runner.calls if c[3].endswith('ordinary_final_bound_cloud.py')][0]
        return declared and '--forecast-includes-upload' not in argv, (
            'declared from the operator settings %s; upload flag absent %s' % (declared, '--forecast-includes-upload' not in argv))


def proof_no_instance_limit_is_shown():
    """D-S95: there is no maximum number of loop instances, so the budget state names none."""
    with sandbox():
        state = cc.budget_state(NOW)
        return 'max_instances' not in state and not hasattr(guard, 'MAX_LOOP_INSTANCES'), (
            'budget state %s; guard limit %s' % (sorted(state), getattr(guard, 'MAX_LOOP_INSTANCES', None)))


DELIVERED = {'memo/review_findings.md': b'# Findings\n', 'memo/review_data.json': b'{}\n',
             'memo/tracked_changes.docx': b'PK-docx-stand-in', '_run_summary.md': b'# Run summary\n'}


def finished_run(box, plan_id, desk, cleanup_absent=True):
    """A run folder in the shape the controller leaves, with the ledger's termination line."""
    bundle = box['cloud'] / plan_id / 'bundle'
    folder = box['cloud'] / plan_id / 'run' / 'bundle'
    folder.mkdir(parents=True)
    cc.write(bundle / 'RUN_FOLDER.json', dict(run_folder=folder.as_posix()))
    cc.write(folder / 'CURRENT_PHASE.json', dict(phase='terminated_and_cleaned', epoch=NOW))
    cc.write(folder / 'activation.json', dict(seconds=180.0, metadata=dict(public_ip='192.0.2.10')))
    for phase, seconds in (('ssh_ready_0', 6), ('assets_transfer', 600), ('ordinary_workload', 1200),
                           ('ordinary_workload_start', 5), ('pack_evidence', 30), ('mystery_step', 60)):
        cc.write(folder / (phase + '_timing.json'), dict(seconds=seconds))
    cc.write(folder / 'termination_requested.json', dict(epoch=NOW))
    cc.write(folder / 'TERMINATION_VERIFIED.json', dict(epoch=NOW + 72, metadata=dict(status='terminated'),
                                                         estimated_cost_upper_bound_usd=0.987, utc='x'))
    cc.write(folder / 'cleanup.json', dict(own_instance_absent=cleanup_absent))
    collected = folder.joinpath(*cc.DELIVERABLES)
    for relative, data in DELIVERED.items():
        (collected / relative).parent.mkdir(parents=True, exist_ok=True)
        (collected / relative).write_bytes(data)
    name = desk.plan(plan_id)['instance_name']
    with box['private'].open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(dict(event='termination', instance_name=name, actual_minutes=35, actual_cost=0.76,
                                     time_utc='2026-11-09T00:00:00+00:00')) + '\n')
    return folder


def proof_actual_time_cost_and_shut_down():
    with sandbox() as box:
        desk, _, _, plan_id = ready_desk()
        code = desk.confirmation(plan_id)
        desk.launch(plan_id, code['code'], code['quote']['cap_text'])
        finished_run(box, plan_id, desk)
        o = desk.status(plan_id)['outcome']
        parts = o['parts_minutes']
        ok = (o['shut_down'] is True and o['actual_minutes'] == 35 and o['actual_cost_usd'] == 0.76
              and parts == dict(start_machine=3.1, copy_files=10.0, prepare_machine=0.0, review=20.0, collect_results=0.5,
                                other=1.0, shut_down=1.2)
              and desk.plan(plan_id)['state'] == 'finished')
        return ok, 'outcome %s' % json.dumps({k: o[k] for k in ('shut_down', 'actual_minutes', 'actual_cost_usd',
                                                                   'parts_minutes')}, sort_keys=True)


def proof_deliverables_are_listed_and_served():
    """At the end each document's files are listed and served through token routes, only those
    listed; the gone sentence stands only beside a confirmed shutdown."""
    try:
        import fastapi  # noqa: F401
    except ImportError:
        return None, 'fastapi absent: deliverables proof skipped'
    import io
    import zipfile
    from fastapi.testclient import TestClient
    from startup_submit_checks import _isolated_server
    with sandbox() as box, tempfile.TemporaryDirectory(prefix='shimmer_cloud_server_') as tmp:
        server = _isolated_server(Path(tmp))
        access = secrets.token_urlsafe(24)
        desk = cc.Desk(runner=FakeRunner(), clock=Clock(), threads=False)
        plan_id = desk.prepare(FILES['targets'], FILES['grounding'], FILES['conventions'])
        before = refused(lambda: desk.deliverable(plan_id, 'memo'))
        code = desk.confirmation(plan_id)
        desk.launch(plan_id, code['code'], code['quote']['cap_text'])
        folder = finished_run(box, plan_id, desk)
        # A file beside the deliverables, never listed: a path built before the listing is read reaches it.
        folder.joinpath(*cc.DELIVERABLES[:-1], 'outside.txt').write_text('not a deliverable', encoding='utf-8')
        o = desk.status(plan_id)['outcome']
        listing = {d['doc_id']: sorted(f['name'] for f in d['files']) for d in o['deliverables']['documents']}
        with patch.dict(os.environ, {'SHIMMER_TOKEN_HASH': hashlib.sha256(access.encode()).hexdigest()}), \
                patch.object(cc, 'DESK', desk):
            client, headers = TestClient(server.app), {'Authorization': 'Bearer ' + access}
            base = '/cloud/plans/%s' % plan_id
            zipped = client.get(base + '/deliverables/memo', headers=headers)
            names = sorted(zipfile.ZipFile(io.BytesIO(zipped.content)).namelist()) if zipped.status_code == 200 else None
            one = client.get(base + '/files/memo/review_findings.md', headers=headers)
            summary = client.get(base + '/files/_run/_run_summary.md', headers=headers)
            escapes = [client.get(base + path, headers=headers).status_code for path in (
                '/files/memo/..%2F..%2F..%2Fplan.json', '/files/_run/..%2F..%2F..%2F..%2Fplan.json',
                '/files/_run/plan.json', '/deliverables/other', '/files/_run/..%2Foutside.txt',
                '/files/memo/..%2F..%2Foutside.txt')]
            no_token = client.get(base + '/deliverables/memo').status_code
        ok = (before == 'No results for this plan'
              and listing == {'memo': ['review_data.json', 'review_findings.md', 'tracked_changes.docx']}
              and [f['name'] for f in o['deliverables']['run_files']] == ['_run_summary.md']
              and names == ['review_data.json', 'review_findings.md', 'tracked_changes.docx']
              and one.status_code == 200 and one.content == DELIVERED['memo/review_findings.md']
              and summary.status_code == 200 and all(c == 404 for c in escapes) and no_token == 401
              and o['gone'] == cc.GONE)
        return ok, ('before the end %r; listed %s; zip %s; one file %s; summary %s; outside the listing %s; '
                    'no token %s; gone %s' % (before, listing, names, one.status_code, summary.status_code, escapes,
                                              no_token, o['gone'] is not None))


def proof_not_shut_down_is_said():
    with sandbox() as box:
        desk, _, _, plan_id = ready_desk()
        code = desk.confirmation(plan_id)
        desk.launch(plan_id, code['code'], code['quote']['cap_text'])
        finished_run(box, plan_id, desk, cleanup_absent=False)
        o = desk.status(plan_id)['outcome']
        return o['shut_down'] is False and o['gone'] is None, (
            'cleanup did not find the instance gone: shut_down %s, gone sentence %s' % (o['shut_down'], o['gone']))


def proof_progress_is_the_tracked_reader():
    with sandbox() as box:
        desk, _, _, plan_id = ready_desk()
        code = desk.confirmation(plan_id)
        desk.launch(plan_id, code['code'], code['quote']['cap_text'])
        bundle = box['cloud'] / plan_id / 'bundle'
        folder = box['cloud'] / plan_id / 'run' / 'bundle'
        folder.mkdir(parents=True)
        cc.write(bundle / 'RUN_FOLDER.json', dict(run_folder=folder.as_posix()))
        cc.write(folder / 'CURRENT_PHASE.json', dict(phase='assets_transfer', epoch=NOW - 600))
        cc.write(folder / 'assets_transfer_archive.json', dict(bytes=20_000_000_000))
        line = desk.status(plan_id, observations={'stat -c': '5000000000'})['progress']
        import ordinary_final_progress
        same = ordinary_final_progress.reading_for(folder, observations={'stat -c': '5000000000'}, now=NOW)
        return line == same and '5.00 of 20.00 GB' in line and 'measured' in line, 'progress %r' % line


def proof_failed_step_is_reported_in_one_line():
    with sandbox():
        runner = FakeRunner(fail='ordinary_final_bound_preflight.py')
        desk = cc.Desk(runner=runner, clock=Clock(), threads=False)
        plan_id = desk.prepare(FILES['targets'], {}, FILES['conventions'])
        state = desk.status(plan_id)
        why = refused(lambda: desk.confirmation(plan_id))
        return (state['state'] == 'failed' and state['error'] == 'Refused: the stand-in step says no'
                and why == 'This plan is not ready to start'), 'state %s, error %r, confirmation %r' % (
            state['state'], state['error'], why)


def proof_no_key_in_any_response():
    """Every route, end to end through the real server app, against the credential's sentinel
    value and its path: neither appears in any response, plan file or log the module writes."""
    try:
        import fastapi  # noqa: F401
    except ImportError:
        return None, 'fastapi absent: route proof skipped'
    from fastapi.testclient import TestClient
    from startup_submit_checks import _isolated_server
    with sandbox() as box, tempfile.TemporaryDirectory(prefix='shimmer_cloud_server_') as tmp:
        server = _isolated_server(Path(tmp))
        access = secrets.token_urlsafe(24)
        runner = FakeRunner()
        desk = cc.Desk(runner=runner, clock=Clock(), threads=False)
        with patch.dict(os.environ, {'SHIMMER_TOKEN_HASH': hashlib.sha256(access.encode()).hexdigest()}), \
                patch.object(cc, 'DESK', desk):
            client, headers = TestClient(server.app), {'Authorization': 'Bearer ' + access}
            bodies = []
            r = client.get('/cloud', headers=headers)
            bodies.append(r.text)
            unauth = client.get('/cloud').status_code
            files = [('files', (n, d)) for group in FILES.values() for n, d in group.items()]
            roles = json.dumps({'memo.md': 'target', 'background.md': 'grounding', 'review_conventions.md': 'conventions'})
            sealed = client.post('/cloud/plans', headers=headers, files=files, data=dict(roles=roles, exposure='sealed'))
            made = client.post('/cloud/plans', headers=headers, files=files, data=dict(roles=roles))
            plan_id = made.json().get('plan_id')
            bodies += [sealed.text, made.text, client.get('/cloud/plans/' + plan_id, headers=headers).text]
            code = client.post('/cloud/plans/%s/confirmation' % plan_id, headers=headers).json()
            bad = client.post('/cloud/plans/%s/launch' % plan_id, headers=headers, data=dict(code=code['code'],
                                                                                              confirm_cap_usd='0.00'))
            code = client.post('/cloud/plans/%s/confirmation' % plan_id, headers=headers).json()
            good = client.post('/cloud/plans/%s/launch' % plan_id, headers=headers,
                               data=dict(code=code['code'], confirm_cap_usd=code['quote']['cap_text']))
            unknown = client.get('/cloud/plans/zzz', headers=headers).status_code
            bodies += [json.dumps(code), bad.text, good.text, client.get('/cloud', headers=headers).text]
            written = [p.read_text(encoding='utf-8', errors='replace') for p in box['cloud'].rglob('*')
                       if p.is_file() and p.suffix in ('.json', '.log')]
            secrets_seen = [t for t in bodies + written
                            if SENTINEL in t or str(box['credential_file']) in t
                            or box['credential_file'].as_posix() in t]
            ok = (unauth == 401 and sealed.status_code == 409 and made.status_code == 202 and bad.status_code == 409
                  and good.status_code == 202 and unknown == 404 and not secrets_seen
                  and json.loads(bodies[0])['credential_found'] is True)
            return ok, ('no token %s, sealed %s, prepared %s, wrong cap %s, launched %s, unknown plan %s; '
                        'responses and files carrying the key or its path: %d'
                        % (unauth, sealed.status_code, made.status_code, bad.status_code, good.status_code, unknown,
                           len(secrets_seen)))


SCREEN_SCRIPT = ROOT / 'scripts' / 'ui' / 'cloud_mode.js'
SCREEN_DRIVER = r"""
const fs = require('fs'), vm = require('vm');
const [script, payload] = [process.argv[2], JSON.parse(fs.readFileSync(process.argv[3], 'utf8'))];
const out = {};
for (const lang of ['en', 'tr']) {
  const app = {innerHTML: ''}, elements = {};
  const context = {console, JSON, Object, Array, String, Number, setTimeout: () => 0, clearTimeout: () => 0,
    location: {hash: ''}, FormData: function () {},
    ShimmerLocale: {language: () => lang, message: s => s},
    document: {getElementById: id => elements[id] || (elements[id] = {addEventListener() {}, files: [], value: ''})}};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(script, 'utf8') + ';this.ShimmerCloud = ShimmerCloud;', context);
  const screens = {};
  const deps = path => ({apiJson: () => ({then(f) { f({ok: true, body: payload[path]}); return {catch() {}}; }}),
    detailText: b => String(b), rerender() {}, currentPlan: () => 'abcdef012345'});
  context.ShimmerCloud.renderSetup(app, deps('setup')); screens.setup = app.innerHTML;
  context.ShimmerCloud.renderPlan(app, deps('ready'), 'abcdef012345'); screens.ready = app.innerHTML;
  context.ShimmerCloud.renderPlan(app, deps('running'), 'abcdef012345'); screens.running = app.innerHTML;
  context.ShimmerCloud.renderPlan(app, deps('finished'), 'abcdef012345'); screens.finished = app.innerHTML;
  out[lang] = screens;
}
process.stdout.write(JSON.stringify(out));
"""


def proof_every_screen_says_where_the_documents_go():
    """The four screens, rendered by the shipped scripts/ui/cloud_mode.js under node in both
    languages, each carry the one sentence of where the documents go and the mode's name; the
    estimate is labelled an estimate; the finished screen says the machine was shut down."""
    import shutil as _shutil
    import subprocess
    node = _shutil.which('node')
    if node is None:
        return None, 'node absent: screen proof skipped'
    basis = dict(kind='estimate', rests_on='a stated basis')
    quote = dict(forecast_minutes=32.6, forecast_usd=0.91, cap_text='1.37', instance_type='gpu_1x_a10',
                 hourly_rate_usd=1.29, upload_in_forecast=True)
    payload = dict(
        setup=dict(credential_found=True, settings_ready=True, budget=dict(budget_open=True, left_usd=90,
                                                                             running_instances=0),
                   plans=[]),
        ready=dict(state='ready', targets=['memo.md'], quote=quote, basis=basis),
        running=dict(state='launched', targets=['memo.md'], quote=quote, basis=basis, phase='ordinary_workload',
                     progress='ordinary_workload progress: 3 of 9 calls measured'),
        finished=dict(state='finished', targets=['memo.md'], quote=quote, basis=basis,
                      outcome=dict(shut_down=True, actual_minutes=35, actual_cost_usd=0.76, cost_upper_bound_usd=0.99,
                                   results_folder='output/cloud/x/run/bundle', cost_note='n', parts_note='p',
                                   parts_minutes=dict(start_machine=3.1, review=20.0, shut_down=1.2), gone=cc.GONE,
                                   deliverables=dict(available=True, documents=[dict(doc_id='memo', files=[
                                       dict(name='review_findings.md', bytes=11)])], run_files=[
                                       dict(name='_run_summary.md', bytes=14)]))))
    with tempfile.TemporaryDirectory(prefix='shimmer_cloud_screens_') as tmp:
        driver, data = Path(tmp) / 'driver.js', Path(tmp) / 'payload.json'
        driver.write_text(SCREEN_DRIVER, encoding='utf-8')
        data.write_text(json.dumps(payload), encoding='utf-8')
        done = subprocess.run([node, str(driver), str(SCREEN_SCRIPT), str(data)],
                              capture_output=True, text=True, encoding='utf-8', timeout=60,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if done.returncode != 0:
        return False, 'node failed: ' + done.stderr.strip()[-300:]
    screens = json.loads(done.stdout)
    missing = []
    for lang in ('en', 'tr'):
        sentence = cc.DOCUMENTS[lang].replace("'", '&#39;')
        for name, html in screens[lang].items():
            if sentence not in html or cc.NAME[lang] not in html:
                missing.append('%s/%s' % (lang, name))
    labels = ('Estimate' in screens['en']['ready'] and 'Tahmin' in screens['tr']['ready']
              and 'The machine was shut down.' in screens['en']['finished']
              and 'Makine kapatıldı.' in screens['tr']['finished'] and 'no maximum; the total budget is the limit' in screens['en']['setup']
              and '3 of 9 calls measured' in screens['en']['running']
              and cc.GONE['en'] in screens['en']['finished'] and cc.GONE['tr'] in screens['tr']['finished']
              and '/cloud/plans/abcdef012345/files/memo/review_findings.md' in screens['en']['finished']
              and '/cloud/plans/abcdef012345/deliverables/memo' in screens['en']['finished']
              and '/files/_run/_run_summary.md' in screens['en']['finished'])
    return not missing and labels, 'screens without the sentence or the name: %s; labels shown %s' % (missing, labels)


PROOFS = [
    ('no credential file found refuses before anything', proof_no_credential_refuses),
    ('no budget_open line refuses and no ledger line is written', proof_no_budget_refuses_and_writes_nothing),
    ('a sealed run is refused', proof_sealed_refused),
    ('the chain is stage, inventory, seal (exposed B3, private ledger), verify, bind, reverify, preflight',
     proof_chain_is_the_bound_path),
    ('the forecast says estimate or measured, never a bare figure', proof_forecast_says_estimate_or_measured),
    ('a launch needs the cap to the cent and an unused, unexpired code for this plan',
     proof_launch_needs_cap_and_one_time_code),
    ('an operator asset copy is declared and the upload flag dropped', proof_asset_copy_drops_upload_flag),
    ('no instance limit is shown, since there is none (D-S95)', proof_no_instance_limit_is_shown),
    ('actual time and cost from the ledger, parts from the receipts, shut down confirmed',
     proof_actual_time_cost_and_shut_down),
    ('a machine not confirmed gone is said so, with no gone sentence', proof_not_shut_down_is_said),
    ("each document's deliverables are listed and served through token routes, only those listed",
     proof_deliverables_are_listed_and_served),
    ('progress is tools/ordinary_final_progress.py, measured', proof_progress_is_the_tracked_reader),
    ('a failed step is one line and blocks the confirmation', proof_failed_step_is_reported_in_one_line),
    ('the routes never show the key or its path', proof_no_key_in_any_response),
    ('every screen says where the documents go, in both languages', proof_every_screen_says_where_the_documents_go),
]


def _unlisted_paths(self, plan_id, doc_id, name=None):
    """The neutralised form: a name joined onto the path with no listing consulted."""
    o = self.status(plan_id, observe=False).get('outcome')
    cc.refuse(o is not None, 'No results for this plan')
    root = Path(o['deliverables']['root'])
    folder = root if doc_id == cc.RUN_FILES else root / doc_id
    return folder if name is None else folder / name


def _skip_cap_check(self, plan_id, code, confirm_cap_usd):
    with self.lock:
        entry = self.codes.pop(self.digest(code), None)
    cc.refuse(entry is not None, 'The confirmation code is unknown, used, or for another plan')
    return entry


def _keep_code(self, plan_id, code, confirm_cap_usd):
    entry = self.codes.get(self.digest(code))
    cc.refuse(entry is not None and entry['plan_id'] == plan_id and confirm_cap_usd == entry['cap_text'],
              'The amount confirmed is not the cap shown')
    return entry


# (what, proof, patcher): with the rule neutralised the proof must fail.
NEUTRALISATIONS = [
    ('credential check removed', proof_no_credential_refuses, lambda: patch.object(cc, 'credential_located', lambda: True)),
    ('budget check removed', proof_no_budget_refuses_and_writes_nothing,
     lambda: patch.object(cc, 'require_budget', lambda now=None: {})),
    ('cap comparison removed', proof_launch_needs_cap_and_one_time_code,
     lambda: patch.object(cc.Desk, 'take_code', _skip_cap_check)),
    ('code kept after use', proof_launch_needs_cap_and_one_time_code, lambda: patch.object(cc.Desk, 'take_code', _keep_code)),
    ('limit typed as 16', proof_no_instance_limit_is_shown,
     lambda: patch.object(cc, 'budget_state', lambda now=None: dict(budget_open=True, max_instances=16))),
    ('shut down read from the provider status alone', proof_not_shut_down_is_said,
     lambda: patch.object(cc, 'outcome', lambda folder, name: dict(shut_down=True))),
    ('upload flag always passed', proof_asset_copy_drops_upload_flag,
     lambda: patch.object(cc.Desk, 'launch_argv', staticmethod(lambda plan, settings: [
         *cc.python(), cc.TOOLS / 'ordinary_final_bound_cloud.py', '--forecast-includes-upload', '--detach']))),
    ('a name joined onto the path without the listing', proof_deliverables_are_listed_and_served,
     lambda: patch.object(cc.Desk, 'deliverable', _unlisted_paths)),
    ('the documents sentence dropped from the screens', proof_every_screen_says_where_the_documents_go, lambda: _sentence_dropped()),
]


@contextlib.contextmanager
def _sentence_dropped():
    """A copy of cloud_mode.js whose screen head no longer carries the documents sentence."""
    global SCREEN_SCRIPT
    source = SCREEN_SCRIPT.read_text(encoding='utf-8')
    needle = 'esc(DOCS[lang()])'
    cc.refuse(source.count(needle) == 1, 'the screen head moved, so the neutralisation cannot be applied')
    with tempfile.TemporaryDirectory(prefix='shimmer_cloud_neutral_') as tmp:
        copy = Path(tmp) / 'cloud_mode.js'
        copy.write_text(source.replace(needle, '""'), encoding='utf-8')
        saved, SCREEN_SCRIPT = SCREEN_SCRIPT, copy
        try:
            yield
        finally:
            SCREEN_SCRIPT = saved


def run(proof):
    try:
        return proof()
    except Exception as error:  # a proof that raises fails, with its class
        return False, 'raised %s: %s' % (type(error).__name__, str(error)[:200])


def main():
    failures = 0
    for what, proof in PROOFS:
        ok, detail = run(proof)
        word = 'SKIP' if ok is None else 'PASS' if ok else 'FAIL'
        failures += word == 'FAIL'
        print('%s %s: %s' % (word, what, detail))
    for what, proof, patcher in NEUTRALISATIONS:
        with patcher():
            ok, detail = run(proof)
        if ok:
            failures += 1
            print('FAIL neutralised (%s) and the proof still passes: %s' % (what, detail))
            continue
        ok, _ = run(proof)
        if not ok:
            failures += 1
            print('FAIL restored (%s) and the proof fails' % what)
            continue
        print('PASS neutralised (%s): FAIL; restored: PASS' % what)
    total = len(PROOFS) + len(NEUTRALISATIONS)
    print('%s console cloud mode: %d of %d proofs and neutralisations pass' % (
        'PASS' if not failures else 'FAIL', total - failures, total))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
