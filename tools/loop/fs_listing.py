"""D-705 (standing order 99): a listing-only loop launch that shows what the persistent file system
`shimmer-filesystem` holds, NAMES AND SIZES ONLY.

One guarded loop launch, the same pieces the ordinary final controller uses, none of them changed:
  * the budget guard's decision (`loop_budget_guard.check`) under the ledger lock, with the inventory
    read again under the lock, the reaper's ledgers, the standing orders 1 to 3 and the spend store;
  * its own cap (`--cap-usd`, default 1, at most the per-step pre-approval, 5 USD since D-708, read from
    config/loop_spend_limits.json at call time, PARALLEL-LAMBDA-A): a forecast over it is refused
    before any provider call that changes anything; the cap used is the smaller of it and the guard's;
  * the ledger lines the reaper and the spend tools read (`launch_intent` with its deadline before the
    launch request, `launch`, `termination` with the billed minutes and cost), written through
    `loop_budget_guard.ledger_line` and `append` on a ledger the reaper reads, the instance named
    `shimmer-loop-fs-listing-<UTC time>`, purpose `fs-listing`;
  * a short deadline (`--deadline-minutes`, default 30, at most 60), the reaper's to enforce;
  * the provider adapter (`tools/lambda_experiment_provider.py`): the cheapest x86_64 single-GPU type
    with capacity in us-east-1 (where the file system lives), launched with exactly that file system
    attached, a temporary ssh key registered and removed.
Over ssh it runs ONLY the fixed command set below (`TEMPLATES`, pinned by `TEMPLATES_SHA256`): `df`,
`du -h --max-depth=3` of the mount and, for each `--names` pattern, a `find -maxdepth 6 -name` that
prints each match's type, bytes and path, and for a matching folder its size and file count. Nothing
reads a file's contents, copies or writes on the file system. Only the name patterns come from the
command line, each held to [A-Za-z0-9_*.-]+. The output is saved under the main checkout's
docs/loop/private/fs_listing/<instance name>/; the instance is then terminated and the termination
confirmed in a finally block, so a failed listing still ends the instance and closes the ledger.
No watchdog process is armed: the in-process termination and the reaper (the ledger deadline) end it.

    py -3.12 -X utf8 tools/loop/fs_listing.py --names s05 'gate_prep*'           # dry run: the fixed script
    py -3.12 -X utf8 tools/loop/fs_listing.py --names s05 'gate_prep*' --execute # the one launch

The credential is found by the repository's one resolver at the moment of use and never printed.
Proofs: tools/loop/fs_listing_checks.py (fixtures, a fake provider and a fake ssh; check 395).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / 'tools'), str(Path(__file__).resolve().parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import loop_budget_guard as guard  # noqa: E402
from cloud_run_common import credential_locations, no_window  # noqa: E402

PURPOSE = 'fs-listing'
FILESYSTEM_NAME = 'shimmer-filesystem'        # declare_asset_copy.LOOP_FILESYSTEM_NAME
MOUNT = '/home/ubuntu/shimmer-filesystem'     # declare_asset_copy.LOOP_MOUNT; a link to /lambda/nfs/shimmer-filesystem on the instance, so du -D and find -H follow it (16 Nov run listed 0 without)
REGION = 'us-east-1'                          # the file system lives there
IMAGE_FAMILY = 'lambda-stack-24-04'
DEFAULT_CAP_USD = 1.0
DEFAULT_FORECAST_MINUTES = 15.0
DEFAULT_DEADLINE_MINUTES = 30.0
MAX_DEADLINE_MINUTES = 60.0
STOP_RESERVE_MINUTES = 5.0                    # the listing stops this long before the deadline
LISTING_SECONDS = 1200
ACTIVATION_SECONDS = 600
SSH_ATTEMPTS = 30
TERMINATION_WAIT_SECONDS = 900
MAX_NAMES = 32
NAME = re.compile(r'[A-Za-z0-9_*.-]+')

# The whole remote command set. Only {mount} (the constant above) and {name} (a validated pattern,
# quoted) are filled in. Read-only listing: no file's contents, no copy, no write on the mount.
HEADER = "set -u; test -d {mount} || {{ echo 'mount absent'; exit 3; }}"
TEMPLATES = (
    "echo '== df'; df -B1 --output=size,used,avail,target {mount}",
    "echo '== du depth 3'; timeout 600 du -D -h --max-depth=3 {mount}",
)
NAME_TEMPLATES = (
    "echo '== name '{name}; timeout 300 find -H {mount} -maxdepth 6 -name {name} -printf '%y\\t%s\\t%p\\n'",
    "timeout 600 find -H {mount} -maxdepth 6 -name {name} -type d -exec sh -c "
    "'for d; do printf \"%s\\t%s files\\t%s\\n\" \"$(du -sh \"$d\" | cut -f1)\" \"$(find \"$d\" -type f | wc -l)\" \"$d\"; done'"
    " sh {{}} +",
)
TEMPLATES_SHA256 = '2a606548e8b5d534c3f24379ca4a7c1473bebd259057bc9128feee38ae0fc74c'


class ListingRefusal(RuntimeError):
    """A one-line refusal before or around the launch."""


def refuse(condition, message):
    if not condition:
        raise ListingRefusal(message)


def utc(epoch):
    return datetime.fromtimestamp(float(epoch), timezone.utc).isoformat()


def templates_digest(header=None, templates=None, name_templates=None, mount=None):
    value = [HEADER if header is None else header, list(TEMPLATES if templates is None else templates),
             list(NAME_TEMPLATES if name_templates is None else name_templates), MOUNT if mount is None else mount]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode('utf-8')).hexdigest()


def pinned():
    """The command set is the one reviewed: its digest equals the pin written in this file."""
    return templates_digest() == TEMPLATES_SHA256


def validate_names(names):
    """Each name pattern [A-Za-z0-9_*.-]+, at most 64 characters, no leading hyphen, not dots alone,
    no repeats, at most MAX_NAMES of them. Anything else refuses the whole run, before any provider call."""
    names = list(names or [])
    refuse(len(names) <= MAX_NAMES, 'At most %d name patterns' % MAX_NAMES)
    refuse(len(set(names)) == len(names), 'A name pattern repeats')
    for name in names:
        refuse(isinstance(name, str) and len(name) <= 64 and NAME.fullmatch(name) is not None
               and not name.startswith('-') and name.strip('.') != '',
               'A name pattern may hold only letters, digits and _ * . - (no leading hyphen, not dots alone)')
    return names


def listing_script(names):
    """The one remote command: the fixed header and templates, each name quoted into the name templates."""
    refuse(pinned(), 'The listing command set differs from its pinned digest; it is never run altered')
    names = validate_names(names)
    mount = shlex.quote(MOUNT)
    parts = [HEADER.format(mount=mount)] + [t.format(mount=mount) for t in TEMPLATES]
    for name in names:
        parts += [t.format(mount=mount, name=shlex.quote(name)) for t in NAME_TEMPLATES]
    return '; '.join(parts)


def own_cap_refusal(forecast_usd, cap_usd):
    """The listing's own cap: a forecast over it refuses the launch."""
    refuse(forecast_usd <= cap_usd, 'Forecast %.2f dollars is over the listing cap %.2f dollars' % (forecast_usd, cap_usd))


def max_cap_usd():
    """PARALLEL-LAMBDA-A, D-708: the per-step pre-approval, read now from its one declared source
    (config/loop_spend_limits.json through loop_budget_guard.read_spend_limits), never a number here."""
    try:
        return guard.read_spend_limits()['step_preapproved_usd']
    except guard.GuardRefusal as exc:
        refuse(False, str(exc))


def check_plan(cap_usd, forecast_minutes, deadline_minutes, storage_forecast_usd):
    top = max_cap_usd()
    refuse(type(cap_usd) in (int, float) and math.isfinite(cap_usd) and 0 < cap_usd <= top + guard.LIMIT_TOLERANCE_USD,
           'The cap is above 0 and at most %.2f dollars (the per-step pre-approval)' % top)
    refuse(type(forecast_minutes) in (int, float) and 0 < forecast_minutes, 'Forecast minutes must be positive')
    refuse(type(deadline_minutes) in (int, float) and forecast_minutes + STOP_RESERVE_MINUTES <= deadline_minutes
           <= MAX_DEADLINE_MINUTES, 'The deadline covers the forecast and the stop reserve and is at most %.0f minutes'
           % MAX_DEADLINE_MINUTES)
    refuse(type(storage_forecast_usd) in (int, float) and storage_forecast_usd >= 0, 'Invalid storage forecast')


def cheapest_type(rows):
    """The cheapest x86_64 single-GPU type with capacity in us-east-1 (type name breaks a tie)."""
    usable = [x for x in rows if x.get('architecture') == 'x86_64' and REGION in (x.get('regions') or [])
              and int(x['metadata'].get('gpu_count') or 0) == 1
              and type(x['metadata'].get('hourly_rate')) in (int, float) and x['metadata']['hourly_rate'] > 0]
    refuse(usable, 'No single-GPU x86_64 type has capacity in %s now; try again later' % REGION)
    best = min(usable, key=lambda x: (x['metadata']['hourly_rate'], x['metadata']['type']))
    return best['metadata']['type'], float(best['metadata']['hourly_rate'])


def record(ledger, event, **fields):
    """One ledger line through the guard's own writer (exactly the declared IV.3 fields)."""
    guard.append(ledger, guard.ledger_line(event, **fields))


def terminate_confirmed(provider, iid, clock, limit=TERMINATION_WAIT_SECONDS):
    """Request termination until the provider lists the instance terminated or no longer lists it.
    The confirmation time, or None when it was not confirmed within `limit` (the reaper then ends it)."""
    begin = clock.time()
    while clock.time() - begin < limit:
        try:
            if provider.instance(iid).get('status') == 'terminated':
                return clock.time()
            provider.terminate(iid)
        except Exception:
            pass
        clock.sleep(5)
    return None


def ssh_run(argv, timeout):
    return subprocess.run(argv, capture_output=True, timeout=timeout, creationflags=no_window())


def generate_key(identity, comment):
    """A temporary ed25519 identity; its public key text."""
    done = subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(identity), '-C', comment],
                          capture_output=True, creationflags=no_window())
    refuse(done.returncode == 0, 'Temporary ssh key generation failed')
    return Path(str(identity) + '.pub').read_text(encoding='utf-8').strip()


def credential_path():
    """The provider credential file, by the repository's one resolver, at the moment of use."""
    scripts = str(ROOT / 'scripts')
    if scripts not in sys.path:
        sys.path.append(scripts)
    import agent_wrapper
    path = agent_wrapper.resolve_config_path()
    refuse(path is not None, 'No provider credential file found: set SHIMMER_CONFIG_PATH')
    return Path(path)


def real_provider():
    from lambda_experiment_provider import LambdaExperiment
    return LambdaExperiment(credential_path())


def out_root():
    """docs/loop/private/fs_listing of the MAIN checkout (instance_reaper.main_private)."""
    return Path(guard.instance_reaper.main_private()) / 'fs_listing'


def awake(action):
    try:
        import keep_awake as helper
    except ImportError:
        return False
    try:
        return helper.hold() if action == 'hold' else helper.release()
    except Exception:
        return False


def save(folder, name, value):
    Path(folder, name).write_text(json.dumps(value, indent=1, sort_keys=True) + '\n', encoding='utf-8')


def execute(names, *, cap_usd=DEFAULT_CAP_USD, forecast_minutes=DEFAULT_FORECAST_MINUTES,
            deadline_minutes=DEFAULT_DEADLINE_MINUTES, storage_forecast_usd=0.0, provider=None, ssh=None,
            keygen=None, clock=time, ledger=None, reaped=None, spend_store=None, out_dir=None, key_dir=None,
            keep_awake=awake, now_name=None):
    """The one listing launch. Returns the run record. Refusals before the intent line raise; after it,
    every failure is recorded and the instance is still terminated and the ledger closed."""
    check_plan(cap_usd, forecast_minutes, deadline_minutes, storage_forecast_usd)
    script = listing_script(names)          # the pin and every name pattern, before any provider call
    ledger = Path(guard.reaper_ledgers()[0] if ledger is None else ledger)
    guard.require_reaped(ledger, reaped)
    name = guard.instance_name('fs-listing-' + (now_name or datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%S')))
    provider = real_provider() if provider is None else provider
    ssh = ssh_run if ssh is None else ssh
    keygen = generate_key if keygen is None else keygen
    guard.refuse_foreign_inventory(provider.request('instances')['data'])
    kind, rate = cheapest_type(provider.request('instance-types')['data'])
    forecast = guard.forecast_usd(forecast_minutes, rate)
    own_cap_refusal(forecast, cap_usd)
    filesystems = [f for f in provider.request('file-systems')['data']
                   if f.get('name') == FILESYSTEM_NAME and f.get('region') == REGION]
    refuse(len(filesystems) == 1, 'The provider does not list %s in %s' % (FILESYSTEM_NAME, REGION))
    images = [i for i in provider.request('images')['data']
              if i.get('region') == REGION and i.get('family') == IMAGE_FAMILY and i.get('architecture') == 'x86_64']
    refuse(images, 'No %s image in %s' % (IMAGE_FAMILY, REGION))
    image = sorted(images, key=lambda i: str(i.get('version')))[-1]
    folder = Path(out_root() if out_dir is None else out_dir) / name
    keys = Path(tempfile.mkdtemp(prefix='fs-listing-') if key_dir is None else key_dir)
    identity = keys / 'ssh_identity'
    refuse(not identity.exists() and not Path(str(identity) + '.pub').exists(), 'Temporary key path occupied')
    run = dict(instance_name=name, purpose=PURPOSE, type=kind, region=REGION, price_usd_per_hour=rate,
               forecast_usd=round(forecast, 4), listing_cap_usd=cap_usd, names=list(names), phases=[])
    lock = guard.acquire_lock(ledger)
    registration = iid = None
    intent = launch_line = held = False
    start = deadline = None
    try:
        inventory = provider.request('instances')['data']
        decision = guard.check(ledgers=[ledger], forecast_minutes=forecast_minutes, hourly_rate=rate,
                               storage_forecast_usd=storage_forecast_usd, now_epoch=clock.time(),
                               reserve_minutes=STOP_RESERVE_MINUTES, provider_names=guard.loop_inventory(inventory),
                               instance_type=kind, reaped=reaped, spend_store=spend_store)
        cap = min(cap_usd, decision['cap_usd'])
        own_cap_refusal(forecast, cap)
        run.update(cap_usd=round(cap, 4), budget=decision)
        folder.mkdir(parents=True, exist_ok=False)
        public = keygen(identity, name)
        registration = provider.request('ssh-keys', dict(name=name, public_key=public))['data'][0]
        start = clock.time()
        deadline = start + min(deadline_minutes * 60, cap / rate * 3600)
        common = dict(instance_name=name, type=kind, region=REGION, price_usd_per_hour=rate, purpose=PURPOSE,
                      forecast_usd=round(forecast, 4), cap_usd=round(cap, 4))
        # IV.3: the name and the deadline are in the ledger before the launch request.
        record(ledger, 'launch_intent', time_utc=utc(start), launch_requested_utc=utc(start),
               deadline_utc=utc(deadline), **common)
        intent = True
    finally:
        guard.release_lock(lock)
        if not intent and registration is not None:
            try:
                provider.request('ssh-keys/' + registration['id'], method='DELETE')
            except Exception:
                pass
            registration = None
    status = 'failed'
    try:
        held = bool(keep_awake('hold'))
        launched = provider.request('instance-operations/launch', dict(
            region_name=REGION, instance_type_name=kind, ssh_key_names=[registration['name']], quantity=1,
            name=name, image={'id': image['id']}, file_system_names=[FILESYSTEM_NAME]))['data']
        iid = launched['instance_ids'][0]
        record(ledger, 'launch', time_utc=utc(clock.time()), launch_requested_utc=utc(start), instance_id=iid,
               deadline_utc=utc(deadline), **common)
        launch_line = True
        while True:
            state = provider.instance(iid)
            if state.get('status') == 'active' and state.get('public_ip'):
                break
            refuse(clock.time() - start < ACTIVATION_SECONDS, 'Activation timeout')
            clock.sleep(5)
        refuse(float(state.get('hourly_rate', rate)) == rate, 'The activated price differs from the selected price')
        options = ['-i', str(identity), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
                   '-o', 'StrictHostKeyChecking=accept-new', '-o', 'UserKnownHostsFile=' + str(keys / 'known_hosts'),
                   '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2']
        base = ['ssh', *options, 'ubuntu@' + state['public_ip']]
        for attempt in range(SSH_ATTEMPTS):
            try:
                ready = ssh(base + ['true'], 20).returncode == 0
            except subprocess.TimeoutExpired:
                ready = False
            run['phases'].append(dict(phase='ssh_ready', attempt=attempt, ready=ready))
            if ready:
                break
            clock.sleep(5)
        else:
            refuse(False, 'ssh not ready')
        remaining = int(deadline - STOP_RESERVE_MINUTES * 60 - clock.time())
        refuse(remaining > 0, 'The deadline leaves no time for the listing')
        began = clock.time()
        try:
            done = ssh(base + [script], min(LISTING_SECONDS, remaining))
        except subprocess.TimeoutExpired:
            refuse(False, 'The listing ran past its time')
        out, err = done.stdout or b'', done.stderr or b''
        run['phases'].append(dict(phase='listing', returncode=done.returncode, seconds=round(clock.time() - began, 1),
                                  stdout_bytes=len(out), stderr_bytes=len(err)))
        refuse(not credential_locations(out + err, 'listing'), 'Possible credential in the listing; output withheld')
        Path(folder, 'listing.txt').write_bytes(out)
        Path(folder, 'listing_stderr.txt').write_bytes(err)
        refuse(done.returncode == 0, 'The listing exited %d' % done.returncode)
        status = 'listed'
    except Exception as exc:
        run['failure'] = dict(error_type=type(exc).__name__,
                              message=str(exc) if isinstance(exc, (ListingRefusal, guard.GuardRefusal)) else 'see phases')
    finally:
        recovered = True
        if iid is None:
            try:
                matches = [x for x in provider.request('instances')['data'] if x.get('name') == name]
                refuse(len(matches) <= 1, 'Ambiguous launch recovery')
                if matches:
                    iid = matches[0]['instance_id']
            except Exception as exc:
                recovered = False      # unknown: the ledger stays open, the reaper ends it at its deadline
                run['recovery_failure'] = type(exc).__name__
        end = terminate_confirmed(provider, iid, clock) if iid else clock.time()
        run['termination_confirmed'] = end is not None
        if recovered and end is not None:
            try:
                if iid and not launch_line:
                    record(ledger, 'launch', time_utc=utc(end), launch_requested_utc=utc(start), instance_id=iid,
                           deadline_utc=utc(deadline), **common)
                minutes = max(0, math.ceil((end - start) / 60)) if iid else 0
                record(ledger, 'termination', time_utc=utc(end), launch_requested_utc=utc(start), instance_id=iid,
                       actual_minutes=minutes, actual_cost=round(rate * minutes / 60, 4), **common)
                run.update(actual_minutes=minutes, actual_cost=round(rate * minutes / 60, 4))
            except Exception as exc:
                run['ledger_close_failure'] = type(exc).__name__
        if held:
            keep_awake('release')
        try:
            provider.request('ssh-keys/' + registration['id'], method='DELETE')
            run['ssh_key_removed'] = all(k.get('id') != registration['id'] for k in provider.request('ssh-keys')['data'])
        except Exception as exc:
            run['ssh_key_removed'] = False
            run['ssh_key_failure'] = type(exc).__name__
        for path in (identity, Path(str(identity) + '.pub'), keys / 'known_hosts'):
            Path(path).unlink(missing_ok=True)   # files only; the empty temporary folder is left
        try:
            left = [x for x in provider.request('instances')['data']
                    if (iid and x.get('instance_id') == iid) or x.get('name') == name]
            run['own_instance_absent'] = not [x for x in left if x.get('status') != 'terminated']
        except Exception as exc:
            run['own_instance_absent'] = None
            run['inventory_failure'] = type(exc).__name__
        run.update(status=status, instance_id=iid, requested_utc=utc(start), deadline_utc=utc(deadline))
        save(folder, 'run.json', run)
    return dict(run, folder=str(folder))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], allow_abbrev=False)
    parser.add_argument('--names', nargs='*', default=[], help='name patterns, each [A-Za-z0-9_*.-]+')
    parser.add_argument('--cap-usd', type=float, default=DEFAULT_CAP_USD)
    parser.add_argument('--forecast-minutes', type=float, default=DEFAULT_FORECAST_MINUTES)
    parser.add_argument('--deadline-minutes', type=float, default=DEFAULT_DEADLINE_MINUTES)
    parser.add_argument('--storage-forecast-usd', type=float, default=0.0)
    parser.add_argument('--execute', action='store_true', help='launch; without it only the fixed script is printed')
    args = parser.parse_args(argv)
    try:
        check_plan(args.cap_usd, args.forecast_minutes, args.deadline_minutes, args.storage_forecast_usd)
        script = listing_script(args.names)
        if not args.execute:
            print('dry run, no provider call; the one remote command would be:')
            print(script)
            return 0
        result = execute(args.names, cap_usd=args.cap_usd, forecast_minutes=args.forecast_minutes,
                         deadline_minutes=args.deadline_minutes, storage_forecast_usd=args.storage_forecast_usd)
    except (ListingRefusal, guard.GuardRefusal) as exc:
        print('refused: ' + str(exc))
        return 2
    print('%s on %s at %.2f USD/h: %s; termination confirmed: %s; billed %s min, %s USD; folder %s' % (
        result['instance_name'], result['type'], result['price_usd_per_hour'], result['status'],
        result['termination_confirmed'], result.get('actual_minutes'), result.get('actual_cost'), result['folder']))
    if result.get('failure'):
        print('failure: %s %s' % (result['failure']['error_type'], result['failure']['message']))
    if not result['termination_confirmed']:
        print('TERMINATION NOT CONFIRMED: the ledger stays open and the reaper ends the instance at its deadline')
        return 2
    return 0 if result['status'] == 'listed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
