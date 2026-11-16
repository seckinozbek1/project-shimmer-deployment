"""Proofs for tools/loop/fs_listing.py (D-705), on fixtures only: a fake provider, a fake ssh, a fake key
generator and a fake clock in a temporary folder; no network, no real ledger, no instance. Each proof is
run as built (passes), neutralised (must fail), restored (passes again).

    py -3.12 -X utf8 tools/loop/fs_listing_checks.py
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fs_listing as fs  # noqa: E402
import lambda_experiment_provider as adapter  # noqa: E402  (on the path through fs_listing)

IID = 'a' * 32
KEY_ID = 'b' * 32
FS_ID = 'c' * 32
IMAGE_ID = 'd' * 32
START = 1_800_000_000.0
LISTING = b'== df\n21474836480 1073741824 20401094656 /home/ubuntu/shimmer-filesystem\n== du depth 3\n1.0G\t/home/ubuntu/shimmer-filesystem\n'


class Clock:
    def __init__(self, t=START):
        self.t = t

    def time(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class FakeProvider:
    """The adapter's projected shapes. Every request is held to the adapter's own `allowed` rule and its
    bounded launch body rule; termination is a state change only."""

    def __init__(self, ledger, rate=0.75):
        self.ledger, self.rate = Path(ledger), rate
        self.calls, self.launch_body, self.ledger_at_launch = [], None, None
        self.status = None
        self.keys = []

    def request(self, endpoint, body=None, method=None):
        self.calls.append(endpoint)
        if endpoint == 'instances':
            if self.status in (None, 'terminated'):
                return {'data': []}
            return {'data': [dict(instance_id=IID, name=self.name, status=self.status)]}
        assert adapter.allowed(endpoint, body, method), endpoint
        if endpoint == 'instance-types':
            meta = lambda t, r, g='A10 (24 GB PCIe)': dict(type=t, gpu_type=g, gpu_count=1, cpu=30, ram_gib=200,
                                                           storage_gib=1400, hourly_rate=r)
            return {'data': [dict(metadata=meta('gpu_1x_h100_pcie', 2.49, 'H100 (80 GB PCIe)'), architecture='x86_64',
                                  regions=['us-east-1']),
                             dict(metadata=meta('gpu_1x_a10', self.rate), architecture='x86_64', regions=['us-east-1']),
                             dict(metadata=meta('gpu_1x_a6000', 0.5, 'A6000 (48 GB)'), architecture='x86_64',
                                  regions=['us-west-1'])]}
        if endpoint == 'file-systems':
            return {'data': [dict(id=FS_ID, name='shimmer-filesystem', region='us-east-1', bytes_used=1, is_in_use=False)]}
        if endpoint == 'images':
            return {'data': [dict(id=IMAGE_ID, family='lambda-stack-24-04', version='1', architecture='x86_64',
                                  region='us-east-1')]}
        if endpoint == 'ssh-keys' and body is not None:
            self.keys.append(KEY_ID)
            return {'data': [dict(id=KEY_ID, name=body['name'])]}
        if endpoint == 'ssh-keys':
            return {'data': [dict(id=k, name='k') for k in self.keys]}
        if endpoint.startswith('ssh-keys/'):
            self.keys = [k for k in self.keys if k != endpoint.split('/')[1]]
            return {'data': {}}
        if endpoint == 'instance-operations/launch':
            bounded = {'region_name', 'instance_type_name', 'ssh_key_names', 'quantity', 'name', 'image'}
            assert set(body) == bounded | {'file_system_names'} and body['quantity'] == 1, body
            assert body['file_system_names'] == ['shimmer-filesystem'], body
            self.launch_body = body
            self.name = body['name']
            self.ledger_at_launch = rows(self.ledger)
            self.status = 'booting'
            return {'data': dict(instance_ids=[IID])}
        raise AssertionError('unexpected provider request ' + endpoint)

    def instance(self, iid):
        if self.status in (None, 'terminated'):
            return dict(instance_id=iid, status='terminated')
        if self.status == 'booting':
            self.status = 'active'
            return dict(instance_id=iid, status='booting', hourly_rate=self.rate)
        return dict(instance_id=iid, status='active', public_ip='192.0.2.10', hourly_rate=self.rate)

    def terminate(self, iid):
        assert iid == IID
        self.status = 'terminated'


class FakeSsh:
    def __init__(self, listing_rc=0):
        self.remote, self.listing_rc = [], listing_rc

    def __call__(self, argv, timeout):
        assert argv[0] == 'ssh' and argv[-2] == 'ubuntu@192.0.2.10', argv
        command = argv[-1]
        self.remote.append(command)
        if command == 'true':
            return subprocess.CompletedProcess(argv, 0, b'', b'')
        if self.listing_rc != 0:
            return subprocess.CompletedProcess(argv, self.listing_rc, b'', b'ssh: connect failed\n')
        return subprocess.CompletedProcess(argv, 0, LISTING, b'')


def fake_keygen(identity, comment):
    Path(identity).write_text('fixture identity, not a key\n')
    Path(str(identity) + '.pub').write_text('ssh-ed25519 AAAAfixture ' + comment + '\n')
    return 'ssh-ed25519 AAAAfixture ' + comment


def cli(argv):
    """The command line's exit code, its printing kept out of the proof's output; an argparse refusal is 2."""
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            return fs.main(argv)
        except SystemExit as exc:
            return exc.code


def rows(path):
    path = Path(path)
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


def open_ledger(path):
    path.write_text(json.dumps(dict(event='budget_open', time_utc=fs.utc(START), loop_start_utc=fs.utc(START),
                                    budget_usd=100.0, storage_usd_per_day=0.13,
                                    a10_reference_price_usd_per_hour=0.75)) + '\n', encoding='utf-8')


def launch(base, names=('s05', 'gate_prep*'), ssh=None, provider=None, **kw):
    ledger = base / 'budget_ledger.jsonl'
    if not ledger.exists():
        open_ledger(ledger)
    provider = FakeProvider(ledger) if provider is None else provider
    ssh = FakeSsh() if ssh is None else ssh
    keys = base / 'keys'
    keys.mkdir(exist_ok=True)
    result = fs.execute(list(names), provider=provider, ssh=ssh, keygen=fake_keygen, clock=Clock(), ledger=ledger,
                        reaped=[ledger], out_dir=base / 'out', key_dir=keys, keep_awake=lambda action: False,
                        now_name='20261116t180000', **kw)
    return result, provider, ssh, ledger


def events(ledger):
    return [r['event'] for r in rows(ledger) if r['event'] != 'budget_open']


def proof_ledger_lines_in_order(base):
    result, provider, ssh, ledger = launch(base)
    assert result['status'] == 'listed', result
    assert events(ledger) == ['launch_intent', 'launch', 'termination'], events(ledger)
    # the intent, with its deadline, was in the ledger before the launch request
    assert [r['event'] for r in provider.ledger_at_launch if r['event'] != 'budget_open'] == ['launch_intent']
    intent, line, end = [r for r in rows(ledger) if r['event'] != 'budget_open']
    for r in (intent, line, end):
        assert r['instance_name'] == 'shimmer-loop-fs-listing-20261116t180000' and r['purpose'] == 'fs-listing', r
        assert r['type'] == 'gpu_1x_a10' and r['region'] == 'us-east-1' and r['price_usd_per_hour'] == 0.75, r
    deadline = fs.guard.instance_reaper.parse_time(intent['deadline_utc']).timestamp()
    assert 0 < deadline - START <= 30 * 60, deadline - START
    assert line['instance_id'] == IID and end['instance_id'] == IID
    assert end['actual_minutes'] >= 1 and end['actual_cost'] == round(0.75 * end['actual_minutes'] / 60, 4), end
    # the reaper's own reading sees the launch closed
    import datetime
    by_name, closed, _ = fs.guard.instance_reaper.ledger_view(rows(ledger), datetime.datetime.now(datetime.timezone.utc))
    assert closed and all(rec['ident'] in closed for rec in by_name.values()), (by_name, closed)
    assert (Path(result['folder']) / 'listing.txt').read_bytes() == LISTING
    assert provider.status == 'terminated' and provider.keys == [] and result['ssh_key_removed'] is True
    assert result['termination_confirmed'] and result['own_instance_absent'] is True
    assert not (base / 'keys' / 'ssh_identity').exists()
    assert not Path(str(ledger) + '.lock').exists()


def proof_terminates_on_ssh_failure(base):
    result, provider, ssh, ledger = launch(base, ssh=FakeSsh(listing_rc=255))
    assert result['status'] == 'failed' and result['failure']['error_type'] == 'ListingRefusal', result
    assert provider.status == 'terminated', provider.status
    assert events(ledger) == ['launch_intent', 'launch', 'termination'], events(ledger)
    assert result['termination_confirmed'] and provider.keys == []


def proof_cap_refuses_a_forecast_over_it(base):
    ledger = base / 'budget_ledger.jsonl'
    open_ledger(ledger)
    provider = FakeProvider(ledger, rate=3.0)     # 15 min x 3.0 USD/h x 1.3 = 0.975; cap 0.5
    try:
        launch(base, provider=provider, cap_usd=0.5)
    except fs.ListingRefusal as exc:
        assert 'over the listing cap' in str(exc), exc
    else:
        raise AssertionError('a forecast over the cap launched')
    assert provider.launch_body is None and 'instance-operations/launch' not in provider.calls
    assert events(ledger) == [] and not Path(str(ledger) + '.lock').exists()
    for bad in (0, -1, 5.01, float('nan')):     # 5.01: above the per-step pre-approval (D-708)
        try:
            fs.check_plan(bad, 15.0, 30.0, 0.0)
        except fs.ListingRefusal:
            continue
        raise AssertionError('cap %r admitted' % bad)


BAD_NAMES = ('a;rm -rf x', '$(id)', '`id`', 'a b', 'a|b', 'a&b', "x'y", 'x"y', 'a>b', '-delete', '..', '.', '',
             'a/b', 'a\\b', 'a\nb', '*' * 65)


def proof_shell_names_refused(base):
    for bad in BAD_NAMES:
        try:
            fs.validate_names(['s05', bad])
        except fs.ListingRefusal:
            pass
        else:
            raise AssertionError('name pattern admitted: %r' % bad)
        assert cli(['--names', 's05', bad]) == 2, bad
    ledger = base / 'budget_ledger.jsonl'
    open_ledger(ledger)
    provider = FakeProvider(ledger)
    try:
        launch(base, names=('s05', '$(id)'), provider=provider)
    except fs.ListingRefusal:
        pass
    else:
        raise AssertionError('a shell name reached the launch')
    assert provider.calls == [] and events(ledger) == []
    assert fs.validate_names(['s05', 'gate_prep*', 'D-S45', 'B2_suite', 'L1*']) == ['s05', 'gate_prep*', 'D-S45',
                                                                                   'B2_suite', 'L1*']


EXPECTED_S05 = ("set -u; test -d /home/ubuntu/shimmer-filesystem || { echo 'mount absent'; exit 3; }; "
                "echo '== df'; df -B1 --output=size,used,avail,target /home/ubuntu/shimmer-filesystem; "
                "echo '== du depth 3'; timeout 600 du -D -h --max-depth=3 /home/ubuntu/shimmer-filesystem; "
                "echo '== name 's05; timeout 300 find -H /home/ubuntu/shimmer-filesystem -maxdepth 6 -name s05 "
                "-printf '%y\\t%s\\t%p\\n'; timeout 600 find -H /home/ubuntu/shimmer-filesystem -maxdepth 6 -name s05 "
                "-type d -exec sh -c 'for d; do printf \"%s\\t%s files\\t%s\\n\" \"$(du -sh \"$d\" | cut -f1)\" "
                "\"$(find \"$d\" -type f | wc -l)\" \"$d\"; done' sh {} +")


def proof_command_set_cannot_change(base):
    assert fs.listing_script(['s05']) == EXPECTED_S05, fs.listing_script(['s05'])
    result, provider, ssh, ledger = launch(base, names=('s05',))
    assert set(ssh.remote) == {'true', EXPECTED_S05}, ssh.remote
    # an altered command set is refused before any provider call, never run
    old = fs.TEMPLATES
    fs.TEMPLATES = old + ('cat {mount}/secret.txt',)
    try:
        try:
            fs.listing_script(['s05'])
        except fs.ListingRefusal as exc:
            assert 'pinned digest' in str(exc), exc
        else:
            raise AssertionError('an altered command set was admitted')
        assert cli(['--names', 's05']) == 2
    finally:
        fs.TEMPLATES = old
    # no option takes a command: an unknown option is an argparse error, abbreviations are off
    for argv in (['--command', 'ls'], ['--exec', 'ls'], ['--names', 's05', '--script', 'x']):
        assert cli(argv) == 2, argv


PROOFS = [proof_ledger_lines_in_order, proof_terminates_on_ssh_failure, proof_cap_refuses_a_forecast_over_it,
          proof_shell_names_refused, proof_command_set_cannot_change]


def run(proof):
    with tempfile.TemporaryDirectory() as t:
        proof(Path(t))


def patch_attr(obj, name, value):
    def apply():
        old = getattr(obj, name)
        setattr(obj, name, value)
        return lambda: setattr(obj, name, old)
    return apply


ORIGINAL_RECORD = fs.record


def record_without_intent(ledger, event, **fields):
    if event != 'launch_intent':
        ORIGINAL_RECORD(ledger, event, **fields)


NEUTRALISE = {
    # the intent line dropped: the order proof must see it missing
    'proof_ledger_lines_in_order': patch_attr(fs, 'record', record_without_intent),
    # termination never requested: the instance stays up after a failed listing
    'proof_terminates_on_ssh_failure': patch_attr(fs, 'terminate_confirmed', lambda provider, iid, clock, limit=0: None),
    # the listing's own cap removed
    'proof_cap_refuses_a_forecast_over_it': patch_attr(fs, 'own_cap_refusal', lambda forecast, cap: None),
    # the name rule widened to anything
    'proof_shell_names_refused': patch_attr(fs, 'NAME', __import__('re').compile(r'(?s).*')),
    # the pin no longer checked
    'proof_command_set_cannot_change': patch_attr(fs, 'pinned', lambda: True),
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
    return 'PASS', ('%d proofs, each neutralise, fail, restore, pass, fake provider and ssh only: the intent line '
                    'with its deadline before the launch request, then launch and termination with cost; the '
                    'instance terminated after a listing and after an ssh failure; a forecast over the cap refused '
                    'before any launch; a name pattern with shell characters refused; the pinned command set the '
                    'only remote command' % len(passed))


if __name__ == '__main__':
    status, detail = check()
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
