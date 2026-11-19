"""Route S (#252) on the laptop: the seal job's requests from a plan, and the returned bundles made
laptop bundles. Never launches; the job bundle launches through the bound wrapper like any bundle.

    requests  --plan PLAN.json --session NAME [--session NAME ...] --out requests.json
              One request per plan entry, its arguments the sealer's own (the plan's common ones
              less the four the job sets itself: --reuse-assets, --inputs-from, --ledger and
              --output-dir). Seal the job with:
              tools/prepare_ordinary_final_run.py --arm S --seal-requests requests.json
              --reuse-assets <the reuse bundle> --inputs-from <inputs> --ledger <private ledger> ...
    request   --requests requests.json --reuse <the reuse bundle> --inputs <inputs> --ledger <private ledger>
              --forecast-minutes M --storage-forecast-usd U [--instance-types T] [--uncompared]
              --out <new folder> [--source COMMIT]
              Order 85 (D-675): a seal request written (seal_route.write_request) and checked as the bound
              wrapper will check it (request_error); nothing is sealed on the laptop. Refused before anything
              is written when the output drive has less free than request_floor_gib() (order 91;
              config/laptop_disk_floor.json lambda_launch_floor_gib).
              Launch it with tools/ordinary_final_bound_cloud.py --request <folder> ...
    admit     --job <job bundle> --run <the job's run folder> --sealed <folder of returned bundles>
              --reuse <the reuse bundle> --out <new folder>
              Each returned bundle refused when the read copy is stale (admission_stale_reason
              against the live private ledger: the job's own lines aside, and, under order 99,
              the complete guarded loop records of other instances when the guard's decision on
              the current ledgers still carries every bundle's sealed cap, budget_reason), else
              copied out, its asset archive linked by digest, its binding written (the project
              digest from the manifest when the archive is in the store); then the reverify and
              the preflight through the bound tools, one bundle at a time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tools' / 'loop')]
import seal_route as sr  # noqa: E402

import launch_floors  # noqa: E402

JOB_SET_FLAGS = ('--reuse-assets', '--inputs-from', '--ledger', '--output-dir')
# D-585; Seckin 19 Nov 2026 12:03 (replacing the fixed 30 GiB D-099 floor): what the laptop must have free before a
# heavy step starts: memory, and free disk at least the step's own expected size plus the margin of
# config/laptop_disk_floor.json (launch_floors.margin_gib, read at each gate, never copied). A step whose size is
# not known is held to launch_floors.FALLBACK_DISK_GIB and its gate line says footprint_known false.
MIN_MEMORY_GB = 2.0
MIN_DISK_GB = 5.0
EXPECTED_BYTES = {'seal': 512 * 2 ** 20, 'ordinary_final_bound_reverify.py': 16 * 2 ** 20,
                  'ordinary_final_bound_preflight.py': 16 * 2 ** 20}
WAIT_SECONDS = 30
HEAVY = ('prepare_ordinary_final_run.py', 'verify_ordinary_final_assets.py', 'ordinary_final_bound_reverify.py',
         'ordinary_final_bound_preflight.py')


def same_drive(a, b):
    """Whether two paths (or their nearest existing parents) are on one device, so a hard link holds."""
    def device(path):
        path = Path(path).resolve()
        while not path.exists():
            path = path.parent
        return os.stat(path).st_dev
    return device(a) == device(b)


def resources(disk_path):
    """One reading: free memory and free disk in GB, and the other heavy sealing steps running."""
    import psutil
    others = 0
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            line = ' '.join(proc.info.get('cmdline') or [])
        except (psutil.Error, TypeError):
            continue
        if proc.info['pid'] != os.getpid() and any(h in line for h in HEAVY):
            others += 1
    free = shutil.disk_usage(str(disk_path)).free
    return dict(memory_gb=round(psutil.virtual_memory().available / 2**30, 2), disk_bytes=free,
                disk_gb=round(free / 2**30, 2), other_seals=others)


def disk_floor_bytes(floor_bytes=None):
    """The margin a gate holds above the step's expected size: the one passed, else the laptop rule's margin
    read from config/laptop_disk_floor.json now (launch_floors.margin_gib; unreadable: the 30 GiB fallback)."""
    if floor_bytes is not None:
        return int(floor_bytes)
    return int(launch_floors.margin_gib()[0] * 2 ** 30)


def admits(reading, expected_bytes=0, floor_bytes=None):
    """The one reading admits the step: memory, no other seal, and disk free after the step's own
    expected size at or above the margin (disk_floor_bytes: the one passed, else the laptop rule's, read now)."""
    disk = reading.get('disk_bytes', reading['disk_gb'] * 2 ** 30)
    return (reading['memory_gb'] >= MIN_MEMORY_GB and reading['disk_gb'] >= MIN_DISK_GB and reading['other_seals'] == 0
            and disk - expected_bytes >= disk_floor_bytes(floor_bytes))


def wait_for_room(step, log, disk_path, read=resources, sleep=None, clock=None, floor_bytes=None, expected=None,
                  wait=True):
    """Gate a heavy step on ONE reading per wait cycle and log that same reading as its start line
    (never a second reading taken after the condition held: the gate and the record are one
    reading). Returns the start line of the reading the step started on (written to `log` unless it
    is None). With `wait` False one reading decides: no room is a refusal, never a wait (a gate under
    the ledger lock never waits, D-726). A step with no expected size (none passed, none in EXPECTED_BYTES)
    is held to the fallback floor launch_floors.FALLBACK_DISK_GIB, never to the margin alone, and its line
    says footprint_known false."""
    import time
    sleep = time.sleep if sleep is None else sleep
    clock = time.time if clock is None else clock
    known = expected is not None or step in EXPECTED_BYTES
    if known:
        expected = EXPECTED_BYTES[step] if expected is None else int(expected)
    else:
        expected = 0
        if floor_bytes is None:
            floor_bytes = int(launch_floors.required_gib(None)[0] * 2 ** 30)
    while True:
        reading = read(disk_path)
        if admits(reading, expected, floor_bytes):
            line = dict(reading, step=step, event='start', time_epoch=round(clock(), 3), expected_bytes=expected,
                        footprint_known=known, disk_floor_bytes=disk_floor_bytes(floor_bytes))
            if log is not None:
                with open(log, 'a', encoding='utf-8') as stream:
                    stream.write(json.dumps(line, sort_keys=True) + chr(10))
            return line
        if not wait and log is not None:
            # The refusing reading is the gate's record too (follow-up of a14bd4ab): event 'refused'.
            line = dict(reading, step=step, event='refused', time_epoch=round(clock(), 3), expected_bytes=expected,
                        footprint_known=known, disk_floor_bytes=disk_floor_bytes(floor_bytes))
            with open(log, 'a', encoding='utf-8') as stream:
                stream.write(json.dumps(line, sort_keys=True) + chr(10))
        sr.require(wait, 'No room for %s under the ledger lock (free %.2f GiB, memory %.2f GiB, %d other seals; floor '
                         '%.1f GiB after %d bytes): the room read before the lock is gone; admit again'
                   % (step, reading['disk_gb'], reading['memory_gb'], reading['other_seals'],
                      disk_floor_bytes(floor_bytes) / 2 ** 30, expected))
        sleep(WAIT_SECONDS)


# D-726 (Seckin 12:08, 18 Nov): laptop disk below a floor never again makes a measurement wait; the room is waited
# for before the budget ledger lock is taken, so a wait never holds every other launch. Seckin 19 Nov 12:03: the
# admission's laptop steps (unpack, reverify, preflight) need their expected bytes plus the laptop rule's margin
# (config/laptop_disk_floor.json margin_gib, 12 GiB), read at each call.
ADMIT_STEPS = ('ordinary_final_bound_reverify.py', 'ordinary_final_bound_preflight.py')
ADMIT_ROOM = 'admission'


def admit_floor_bytes():
    return int(launch_floors.margin_gib()[0] * 2 ** 30)


def plan_requests(plan, sessions, base='.'):
    """[{name, argv}] from the quick-read PLAN shape: {common: [...], sessions: {name: {forecast,
    arm, entries: [{item, workload, bundle, items?, passes?, replay_prompts?}]}}}."""
    base = Path(base).resolve()
    here = lambda p: str((base / p).resolve()) if not Path(p).is_absolute() else str(p)
    common, k = list(plan['common']), 0
    kept = []
    while k < len(common):
        if common[k] in JOB_SET_FLAGS:
            k += 2
            continue
        kept.append(common[k])
        if common[k] == '--image-env-manifest' and k + 1 < len(common):
            kept.append(here(common[k + 1]))
            k += 1
        k += 1
    out = []
    for name in sessions:
        session = plan['sessions'][name]
        for e in session['entries']:
            argv = ['--workload', here(e['workload']), '--forecast-minutes', str(session['forecast'])]
            if session['arm'] == 'B1':
                argv += ['--arm', 'B1', '--items', here(e['items']), '--b1-checkpoints', here(e['passes']),
                         '--replay-prompts', here(e['replay_prompts'])]
            out.append(dict(name='%s_%s' % (name, e['item']), argv=argv + kept))
    sr.require(len({r['name'] for r in out}) == len(out), 'Request names repeat')
    return out


def refused_name(out):
    """The first free `<out>.refused`, `<out>.refused-2`, ...: a later refusal never hides an earlier one."""
    n, name = 1, out.with_name(out.name + '.refused')
    while name.exists():
        n += 1
        name = out.with_name('%s.refused-%d' % (out.name, n))
    return name


def own_identifiers(run_folder, job_manifest_sha256, job_bundle):
    """The job instance's name and id. The run folder's launch intent must name the job bundle's
    manifest (the run folder is this job's). The name is derived as the bound wrapper derives it,
    from the job's own binding (guard.instance_name of the preparation commit and the manifest's
    digest), since the controller's launch_intent ledger line names only that; the id is the run
    folder's launch.json."""
    import loop_budget_guard as guard
    intent = Path(run_folder) / 'LAUNCH_INTENT.json'
    sr.require(intent.is_file(), 'The run folder holds no launch intent')
    value = json.loads(intent.read_text(encoding='utf-8'))
    sr.require(value.get('execution_manifest_sha256') == job_manifest_sha256, 'The run folder is not this seal job\'s')
    bound = json.loads((Path(job_bundle) / 'authorization_binding.json').read_text(encoding='utf-8'))
    sr.require(bound.get('manifest_sha256') == job_manifest_sha256, 'The job binding is not the job bundle\'s')
    own = {guard.instance_name(bound['preparation_commit'][:7] + '-' + bound['manifest_sha256'][:8])}
    launch = Path(run_folder) / 'launch.json'
    if launch.is_file():
        own |= {json.loads(launch.read_text(encoding='utf-8')).get('instance_id')}
    return {o for o in own if o}


def collected(run_folder, staging):
    """The job's collected evidence, held to the controller's collection record, extracted into
    `staging` (every member a plain file or folder inside it); its seal job result."""
    run_folder, staging = Path(run_folder), Path(staging)
    record = json.loads((run_folder / 'collection_integrity.json').read_text(encoding='utf-8'))
    archive = run_folder / 'collected_evidence.tar.gz'
    sr.require(sr.sha(archive) == record['sha256'], 'The collected evidence is not the archive the controller verified')
    import tarfile
    staging.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as stream:
        for member in stream.getmembers():
            target = (staging / member.name).resolve()
            sr.require(target.is_relative_to(staging.resolve()) and (member.isfile() or member.isdir()),
                       'Collected member refused: ' + member.name)
        stream.extractall(staging, **({'filter': 'data'} if hasattr(tarfile, 'data_filter') else {}))
    result = json.loads((staging / 'evidence' / 'seal_job_result.json').read_text(encoding='utf-8'))
    return staging / 'evidence' / 'sealed', result


def binding(bundle, final=None):
    """The authorization binding of a bundle from its own manifest, seal and digests (`final`: the
    folder it will be admitted under)."""
    b = Path(bundle)
    m = json.loads((b / 'execution_manifest.json').read_text(encoding='utf-8'))
    s = json.loads((b / 'seal.json').read_text(encoding='utf-8'))
    import ordinary_final_run as runner
    stored = runner.project_held(b, m['source_archive_sha256'])
    doc = dict(assets_sha256=m['assets_archive']['sha256'], bundle=str(final or b).replace('\\', '/'),
               manifest_sha256=sr.sha(b / 'execution_manifest.json'), preparation_commit=s['source_commit'],
               project_sha256=m['source_archive_sha256'] if stored else sr.sha(b / 'project.tar.gz'),
               seal_sha256=sr.sha(b / 'seal.json'), source_commit=s['source_commit'])
    sr.require(doc['project_sha256'] == m['source_archive_sha256'], 'Project archive differs from the manifest')
    (b / 'authorization_binding.json').write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    return doc


# Order 99 (operator 16 Nov 2026 20:11): several Lambda launches at once must not invalidate each other's seal
# admissions. What the read-copy rule protects, and keeps protecting: each returned bundle's hard cap was decided by
# the guard on the read copy, so (1) a ledger rewritten or cut since (not an append) refuses; (2) a line no guarded
# launch writes (another kind, a field outside IV.3, a hand copy, a launch with no intent before it, a record out
# of its order) refuses, since what it means for the budget is not known; (3) a launch of another instance, decided
# on a ledger the copy does not show, is admitted only when the guard's decision on the CURRENT ledgers, with each
# bundle's own sealed figures, still carries that bundle's sealed hard cap (budget_reason): no cap rests on room
# another launch has since taken.


def _moment(value):
    """A recorded time as an aware datetime, or None when it does not read as one."""
    import instance_reaper
    try:
        moment = instance_reaper.parse_time(value)
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo is not None else None


def _amount(value, positive):
    return type(value) in (int, float) and math.isfinite(value) and (value > 0 if positive else value >= 0)


def loop_record_reason(row, history):
    """None when `row`, a ledger line after the read copy that names another instance, is a line its guarded loop
    launch writes (loop_budget_guard.ledger_line through the controller or tools/loop/fs_listing.py, or the reaper's
    termination), in its record's order against `history` (every line before it, the read copy's included):
    launch_intent first and once, with its request time, a later deadline, a price and a cap; launch only after
    its intent, once, with an instance id and the intent's deadline, price and cap; termination only of a launch
    whose intent is there, naming its launch's instance id if it names one, with a readable cost. Else why not."""
    import loop_budget_guard as guard
    if not isinstance(row, dict):
        return 'a line that is not a JSON object'
    event = row.get('event')
    if event not in guard.EVENTS:
        return 'a line of another kind than a loop launch writes (%s)' % str(event)[:40]
    extra = guard.undeclared(row)
    if extra:
        return 'a %s line with a field outside IV.3 (%s)' % (event, ','.join(sorted(str(f) for f in extra))[:80])
    name = row.get('instance_name')
    if not (isinstance(name, str) and name.startswith(guard.PREFIX)):
        return 'a %s line naming no loop instance' % event
    if 'purpose' in row and not (isinstance(row['purpose'], str) and guard.PURPOSE.fullmatch(row['purpose'])):
        return 'a %s line whose purpose is not a short identifier' % event
    if _moment(row.get('time_utc')) is None:
        return 'a %s line with no readable time' % event
    requested = row.get('launch_requested_utc')
    record = [r for r in history if r.get('instance_name') == name and r.get('launch_requested_utc') == requested]
    if event in ('launch_intent', 'launch'):
        start, deadline = _moment(requested), _moment(row.get('deadline_utc'))
        if start is None or deadline is None or not deadline > start:
            return 'a %s line without its request time and a later deadline' % event
        for field in ('price_usd_per_hour', 'cap_usd'):
            if not _amount(row.get(field), True):
                return 'a %s line without its %s' % (event, field)
        if 'forecast_usd' in row and not _amount(row['forecast_usd'], False):
            return 'a %s line with an unreadable forecast_usd' % event
    if event == 'launch_intent':
        if record:
            return 'a launch_intent that is not the first line of its launch'
        return None
    if event == 'launch':
        intents = [r for r in record if r.get('event') == 'launch_intent']
        if not intents:
            return 'a launch line with no launch_intent before it (a launch the guard did not record)'
        if any(r.get('event') in ('launch', 'termination') for r in record):
            return 'a launch line after a launch or termination of its launch'
        if not (isinstance(row.get('instance_id'), str) and row['instance_id']):
            return 'a launch line with no instance id'
        if any(row.get(f) != intents[0].get(f) for f in ('deadline_utc', 'price_usd_per_hour', 'cap_usd')):
            return "a launch line whose deadline, price or cap is not its intent's"
        return None
    # termination: the controller's names its request time; the reaper's names the instance (and its id) only.
    for field in ('actual_cost', 'actual_minutes'):
        if row.get(field) is not None and not _amount(row[field], False):
            return 'a termination line with an unreadable %s' % field
    iid = row.get('instance_id')
    if iid is not None and not (isinstance(iid, str) and iid):
        return 'a termination line with an unreadable instance id'
    if requested is None:
        intents = [r for r in history if r.get('instance_name') == name and r.get('event') == 'launch_intent']
        record = ([r for r in history if r.get('instance_name') == name
                   and r.get('launch_requested_utc') == intents[-1].get('launch_requested_utc')] if intents else [])
    if not any(r.get('event') == 'launch_intent' for r in record):
        return 'a termination of a launch with no launch_intent before it'
    launches = [r for r in record if r.get('event') == 'launch']
    if iid is not None and launches and launches[-1].get('instance_id') != iid:
        return 'a termination naming another instance id than its launch'
    return None


def _named(row):
    """The instance name and id a line names, as strings only."""
    return {v for v in (row.get('instance_name'), row.get('instance_id')) if isinstance(v, str) and v}


def admission_stale_reason(job, live, own, found=None):
    """None when every live record (`live`: {key: path}, the budget ledger, R's ledger and the spend store, by
    seal_route.STALE_RULES) is its read copy with nothing appended but what the rule admits: for a ledger, the job's
    own lines (naming one of `own`, the job instance's name and id) and, under order 99, lines of other instances'
    guarded loop launches each in its record's order (loop_record_reason), each of these appended to `found`; for
    the spend store, only that it begins with the copy. A record with no copy is held as an empty one. Each record
    is read once, so what is checked is what is counted. Otherwise why the read copies are stale. A foreign line
    admitted here is admitted only with budget_reason holding for every returned bundle (admit)."""
    own = {o for o in own if o}
    copies = job['read_copies']
    for key, rule in sr.STALE_RULES.items():
        path = live.get(key)
        entry = copies.get(key) or dict(bytes=0, sha256=hashlib.sha256(b'').hexdigest())
        data = Path(path).read_bytes() if path is not None and Path(path).is_file() else b''
        if len(data) < entry['bytes'] or hashlib.sha256(data[:entry['bytes']]).hexdigest() != entry['sha256']:
            return 'the live %s does not begin with its read copy (rewritten, not appended)' % key
        if rule != 'own_lines':
            continue
        history = []
        for line in data[:entry['bytes']].decode('utf-8', errors='replace').splitlines():
            try:
                row = json.loads(line) if line.strip() else None
            except ValueError:
                continue
            if isinstance(row, dict):
                history.append(row)
        try:
            added = [json.loads(l) for l in data[entry['bytes']:].decode('utf-8').splitlines() if l.strip()]
        except ValueError:
            return 'a line of the %s after its read copy is not readable JSON' % key
        for n, row in enumerate(added, 1):
            if isinstance(row, dict) and _named(row) & own:
                history.append(row)
                continue
            problem = loop_record_reason(row, history)
            if problem:
                return ("line %d of %d of the %s after its read copy is neither the seal job's own nor a guarded loop "
                        "line of another instance: %s" % (n, len(added), key, problem))
            history.append(row)
            if found is not None:
                found.append(dict(ledger=key, event=row['event']))
    return None


def sealed_storage_forecast(argv):
    """The storage forecast a request sealed its budget on: its one --storage-forecast-usd, written in full with its
    value apart (the sealer's parser takes abbreviations, and the last value wins), or None."""
    flag = '--storage-forecast-usd'
    spelled = [i for i, a in enumerate(argv) if isinstance(a, str) and len(a.split('=', 1)[0]) > 2
               and flag.startswith(a.split('=', 1)[0])]
    if len(spelled) != 1 or argv[spelled[0]] != flag or spelled[0] + 1 >= len(argv):
        return None
    try:
        value = float(argv[spelled[0] + 1])
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def budget_reason(manifest, request, live, now_epoch, guard=None):
    """None when the guard's decision on the CURRENT ledgers (the budget ledger and R's, read as the reaper's), made
    with the returned bundle's own sealed figures (its forecast minutes, the first candidate's price it was sealed
    at, its stop reserve, its request's storage forecast), still gives at least the bundle's sealed hard cap, as the
    controller requires at launch. Else why not. Two launch gates are not read here, as they hold no figure of the
    cap: the standing orders (the attestation covers the seal) and the spend store's hand-back gate (D-S121: the
    API spend never counts toward Lambda's); every launch reads both again."""
    import loop_budget_guard as default_guard
    guard = guard or default_guard
    try:
        rate = manifest['instance_candidates'][0]['max_hourly_rate']
        minutes = manifest['forecast_minutes']
        reserve = manifest['workload_stop_reserve_seconds'] / 60
        hard = float(manifest['hard_ceiling_usd'])
    except (KeyError, IndexError, TypeError, ValueError):
        return 'the returned bundle does not carry the figures its budget was sealed on'
    storage = sealed_storage_forecast(request.get('argv') or [])
    if storage is None:
        return 'its request does not name its storage forecast once, in full'
    ledgers = [Path(live[k]) for k in ('budget_ledger', 'r_ledger') if live.get(k) is not None]
    try:
        decision = guard.check(ledgers=ledgers, forecast_minutes=minutes, hourly_rate=rate, storage_forecast_usd=storage,
                               now_epoch=now_epoch, reserve_minutes=reserve, reaped=ledgers)
    except guard.GuardRefusal as exc:
        return 'the guard refuses it on the current ledgers (%s)' % exc
    if not math.isfinite(hard) or decision['cap_usd'] + 1e-9 < hard:
        return ('the cap on the current ledgers, %.4f dollars, is below its sealed hard cap, %.4f dollars'
                % (decision['cap_usd'], hard))
    return None


# Open item 157 (the lead, 18 November 2026 17:33): ROUTE_GATE_e21d4b53's admission was refused at 16:53 by the bound
# preflight ("No declared instance type offered at its sealed rate; poll again later": the free A10s were taken),
# and admit.log said only "refused". (a) A refusing step's stdout and stderr tails go to admit.log (this process's
# stdout) before the refusal is raised, with key-like strings masked. (b) Before the ledger lock, the returned
# bundles' sealed manifests (read from the verified archive, nothing extracted) are held to the free inventory under
# their sealed type rule, read-only, every poll_interval_seconds up to wait_limit_minutes (config/admit_capacity_wait
# .json, read at call time); the lock is taken only once a declared type is offered at its sealed rate.
TAIL_LINES = 20
CAPACITY_PHRASE = 'No declared instance type offered at its sealed rate'
CAPACITY_CONFIG = ROOT / 'config' / 'admit_capacity_wait.json'
MASKS = (re.compile(r'sk-(?:ant-|proj-)?[A-Za-z0-9_-]{16,}'), re.compile(r'AKIA[A-Z0-9]{16}'),
         re.compile(r'AIza[A-Za-z0-9_-]{35}'),
         re.compile(r'(?i)((?:api_key|secret|token|password|credential)\w*\s*[=:]\s*)["\']?[^\s"\']{8,}'))


def masked(text):
    for rx in MASKS:
        text = rx.sub(lambda m: (m.group(1) if m.groups() else '') + '[masked]', text)
    return text


def write_refusal_tail(step, name, done, stream=None):
    """The refusing step's last TAIL_LINES lines of stdout and stderr, masked, to admit.log (stdout), flushed."""
    stream = stream or sys.stdout
    stream.write('%s refused %s (exit %s); its last %d lines:\n' % (step, name, done.returncode, TAIL_LINES))
    for label in ('stdout', 'stderr'):
        lines = (getattr(done, label, '') or '').splitlines()[-TAIL_LINES:]
        stream.write('  [%s] %s\n' % (label, 'nothing' if not lines else ''))
        for line in lines:
            stream.write('    %s\n' % masked(line)[:500])
    stream.flush()


def capacity_settings(path=None):
    """(poll interval seconds, wait limit minutes) from config/admit_capacity_wait.json; (0, 0) when absent."""
    p = Path(path or CAPACITY_CONFIG)
    if not p.is_file():
        return 0, 0
    data = json.loads(p.read_text(encoding='utf-8'))
    return int(data.get('poll_interval_seconds', 0)), float(data.get('wait_limit_minutes', 0))


def archived_manifests(run_folder, names):
    """The returned bundles' sealed manifests read from the controller-verified archive, before the lock; nothing
    is extracted or written."""
    import tarfile
    run_folder = Path(run_folder)
    record = json.loads((run_folder / 'collection_integrity.json').read_text(encoding='utf-8'))
    archive = run_folder / 'collected_evidence.tar.gz'
    sr.require(sr.sha(archive) == record['sha256'], 'The collected evidence is not the archive the controller verified')
    out = []
    with tarfile.open(archive) as stream:
        for name in names:
            try:
                member = stream.extractfile('evidence/sealed/%s/execution_manifest.json' % name)
            except KeyError:
                continue
            if member is not None:
                out.append(json.loads(member.read().decode('utf-8')))
    return out


def live_capacity(manifests):
    """The bound preflight's own capacity reading, read-only: one free inventory, each manifest's sealed type rule
    (guard.select_instance, no polling); the refusal text, or None. No provider call when no manifest declares
    instance candidates."""
    declared = [m for m in manifests if m.get('instance_candidates')]
    if not declared:
        return None
    import loop_budget_guard as guard
    from lambda_experiment_provider import LambdaExperiment
    from ordinary_final_cloud import credential_path
    types = LambdaExperiment(credential_path()).request('instance-types')['data']
    for m in declared:
        try:
            guard.select_instance(lambda: types, m['instance_candidates'], m['a10_reference_rate'], time, poll_seconds=0,
                                  type_rule=m.get('type_rule', 'a10_first'))
        except guard.GuardRefusal as exc:
            return str(exc)
    return None


def wait_for_capacity(manifests, probe, stream=None):
    """Poll `probe` before the ledger lock while it refuses for capacity, every interval up to the declared limit;
    any other answer returns at once (the preflight under the lock decides). Refuses after the limit."""
    stream = stream or sys.stdout
    interval, limit_min = capacity_settings()
    polls = int(limit_min * 60 // interval) if interval > 0 else 0
    for n in range(polls + 1):
        why = probe(manifests)
        if not why or CAPACITY_PHRASE not in why:
            return n
        if n == polls:
            break
        stream.write('waiting for capacity before the ledger lock (poll %d of %d, every %d s): %s\n'
                     % (n + 1, polls, interval, why))
        stream.flush()
        time.sleep(interval)
    sr.require(False, 'No capacity within %s minutes before the ledger lock: %s' % (limit_min, why))


def admit(job_bundle, run_folder, reuse, out, live, ledger, steps=True, run=subprocess.run, gate=None, lock=None, unlock=None,
          request=None, clock=None, capacity=None):
    """The returned bundles of one seal job made laptop bundles, all or none. Bound to the job: the
    run folder's launch intent names the job bundle's manifest; the bundles come only from the
    collected evidence the controller verified; each bundle's manifest and seal digests are the job
    result's own row; the result names the job's manifest; the reuse bundle's manifest is the one the
    job sealed. Under the ledger lock, held from the stale check through the last preflight: the read
    copies (`live`: {key: path}) checked once (admission_stale_reason), then each bundle staged, held to
    the guard's decision on the current ledgers when other launches wrote lines since the read copy
    (budget_reason, order 99), linked, bound, reverified and preflighted. Only when every bundle passes
    are they moved into `out` in one rename; otherwise nothing is admitted and the staging folder is
    kept, renamed refused, for the operator. D-726: the room for the laptop steps (their expected bytes
    plus the laptop rule's margin, admit_floor_bytes) is waited for before the lock is taken, never while it is held; under
    the lock each step's gate reads once and refuses when the room is gone. A refusal there on memory
    (under MIN_MEMORY_GB) or on another heavy sealing step running is intended too: the lock is never
    held through a wait, and the admission is simply run again. Open item 157: before the lock the returned
    bundles' capacity is polled read-only (wait_for_capacity, config/admit_capacity_wait.json), and a refusing
    step writes its stdout and stderr tails to admit.log (write_refusal_tail) before the refusal is raised."""
    import loop_budget_guard as guard
    lock = guard.acquire_lock if lock is None else lock
    unlock = guard.release_lock if unlock is None else unlock
    job_bundle, out = Path(job_bundle), Path(out)
    job_manifest = json.loads((job_bundle / 'execution_manifest.json').read_text(encoding='utf-8'))
    job_sha = sr.sha(job_bundle / 'execution_manifest.json')
    job = json.loads((job_bundle / sr.JOB_FILE).read_text(encoding='utf-8'))
    sr.require(job == job_manifest.get('seal_job') and sr.sha(job_bundle / sr.JOB_FILE) == job_manifest['support_files'][sr.JOB_FILE],
               'The job file is not the job bundle\'s sealed job')
    sr.require(sr.sha(Path(reuse) / 'execution_manifest.json') == job_manifest['support_files'][sr.REUSE_MANIFEST],
               'The reuse bundle is not the one the seal job sealed')
    record_job = job_manifest.get('kind') == sr.LAUNCH_RECORD_KIND
    # The checker's item 9: a seal request's job is admitted with its request (--request), and only it is.
    sr.require(record_job == (request is not None),
               'A seal request launch record is admitted with --request naming its request, and only it is')
    if record_job:
        # D-675: the job of a seal request was sealed on the instance; its record must be its request's.
        problem = sr.record_error(job_bundle, request)
        sr.require(problem is None, problem or '')
    own = own_identifiers(run_folder, job_sha, job_bundle)
    sr.require(not out.exists(), 'The admission folder exists already')
    # D-726: the room for every laptop step of the admission is waited for before the ledger lock, never under
    # it; under the lock each step's own gate reads once and refuses when the room is gone (step_gate).
    room = None
    if steps:
        if gate is not None:
            gate(ADMIT_ROOM)
        else:
            # The steps' expected bytes for every bundle, plus the collected evidence archive (extracted into the
            # staging folder under the lock; its compressed size, follow-up of a14bd4ab).
            archive = Path(run_folder) / 'collected_evidence.tar.gz'
            evidence = archive.stat().st_size if archive.is_file() else 0
            room = wait_for_room(ADMIT_ROOM, None, out.parent, read=resources, floor_bytes=admit_floor_bytes(),
                                 expected=sum(EXPECTED_BYTES.get(s, 0) for s in ADMIT_STEPS) * len(job['requests'])
                                 + evidence)
        # Open item 157 (b): capacity for every returned bundle, read-only, before the lock (never under it).
        wait_for_capacity(archived_manifests(run_folder, [r['name'] for r in job['requests']]),
                          capacity or live_capacity)
    held = lock(ledger)
    try:
        foreign = []
        reason = admission_stale_reason(job, live, own, foreign)
        sr.require(reason is None, 'Seal job read copy is stale: ' + str(reason))
        staging = out.with_name(out.name + '.staging')
        sr.require(not staging.exists(), 'A staging folder of an earlier admission is there; look at it first')
        rows = []
        try:
            sealed, result = collected(run_folder, staging / 'collected')
            sr.require(result.get('job_manifest_sha256') == job_sha, 'The collected result is another job\'s')
            if record_job:
                # Item 9: the instance sealed this request's job (its instance_job_seal.json, collected).
                problem = sr.instance_seal_error(staging / 'collected' / 'evidence', request)
                sr.require(problem is None, problem or '')
            rows_by = {r['name']: r for r in result.get('rows') or []}
            bundles = staging / 'bundles'
            bundles.mkdir()
            if room is not None:
                with open(staging / 'gate_log.jsonl', 'a', encoding='utf-8') as stream:
                    stream.write(json.dumps(dict(room, lock='before'), sort_keys=True) + chr(10))
            step_gate = gate or (lambda name: wait_for_room(name, staging / 'gate_log.jsonl', out.parent, read=resources,
                                                            floor_bytes=admit_floor_bytes(), wait=False))
            for request in job['requests']:
                row = rows_by.get(request['name']) or {}
                source = sealed / request['name']
                sr.require(row.get('rc') == 0 and (source / 'seal.json').is_file(), 'Not sealed by the job: ' + request['name'])
                sr.require(sr.sha(source / 'execution_manifest.json') == row.get('manifest_sha256')
                           and sr.sha(source / 'seal.json') == row.get('seal_sha256'),
                           'A returned bundle is not the one the job sealed: ' + request['name'])
                # D-675 condition 2: a returned bundle is a sealed bundle, never a seal request's launch record.
                sr.refuse_launch_record(json.loads((source / 'execution_manifest.json').read_text(encoding='utf-8')),
                                        'a returned bundle')
                if foreign:
                    # Order 99: other launches wrote lines since the read copy; the bundle's sealed cap must
                    # still be carried by the guard's decision on the current ledgers.
                    problem = budget_reason(json.loads((source / 'execution_manifest.json').read_text(encoding='utf-8')),
                                            request, live, (clock or time.time)())
                    sr.require(problem is None, 'Seal job read copy is stale: %d line(s) of other launches since it, '
                               'and for %s %s' % (len(foreign), request['name'], problem))
                target = bundles / request['name']
                shutil.move(str(source), str(target))
                entry = dict(name=request['name'])
                entry.update(sr.admit_returned(target, reuse))
                entry['binding'] = binding(target, out / request['name'])['manifest_sha256']
                if steps:
                    for step in ADMIT_STEPS:
                        step_gate(step)
                        done = run([sys.executable, '-X', 'utf8', str(ROOT / 'tools' / step), '--bundle', str(target)],
                                   capture_output=True, text=True)
                        if done.returncode != 0:
                            write_refusal_tail(step, request['name'], done)      # open item 157 (a)
                        sr.require(done.returncode == 0, '%s refused %s' % (step, request['name']))
                        entry[step] = done.returncode
                rows.append(dict(entry, admitted=True))
        except Exception:
            if staging.exists():
                staging.rename(refused_name(out))
            raise
        sr.write(bundles / 'admission.json', dict(job_manifest_sha256=job_sha, rows=rows, admitted=len(rows),
                                                  requests=len(job['requests'])))
        bundles.rename(out)      # every bundle admitted in one step
        return rows
    finally:
        unlock(held)


# Order 91 (D-678): the route request is not written below a floor. D-726 (Seckin 12:08, 18 Nov): laptop disk below a
# floor never again makes a measurement wait; the route's laptop worst case is 2.5 GiB, so 12 GiB leaves room. That
# Lambda launch floor is config/laptop_disk_floor.json lambda_launch_floor_gib (12), read at each call; the 19 Nov
# decision kept it as it is.
def request_floor_gib():
    return launch_floors.lambda_launch_floor_gib()[0]


def free_gib(folder):
    """Free space on the drive `folder` is (or will be) on, in GiB."""
    path = Path(folder).resolve()
    while not path.exists():
        path = path.parent
    return shutil.disk_usage(path).free / 2 ** 30


def request_budget(ledgers, forecast_minutes, storage_forecast_usd, instance_types=None, uncompared=False):
    """The budget block exactly as the sealer's own command line builds it for budget_fields (prepare_ordinary_final_run
    main): the ledgers the IV.3 cap reads, the forecast, the storage forecast, the declared types, uncompared."""
    return dict(ledgers=[Path(p) for p in ledgers], forecast_minutes=forecast_minutes,
                storage_forecast_usd=storage_forecast_usd,
                instance_types=instance_types.split(',') if instance_types else None,
                type_rule='fastest', gpus=1, comparison=None, uncompared=bool(uncompared))


def write_checked_request(out, source, requests, reuse, inputs, budget, parallel=16):
    """The request command: the disk floor read first, then the request written, then checked by request_error against
    this checkout's controller (what the bound wrapper checks before any provider call). Returns the request."""
    free, floor = free_gib(out), request_floor_gib()
    sr.require(free >= floor, 'Free disk %.1f GiB is below the request floor of %.1f GiB (order 91)'
               % (free, floor))
    request = sr.write_request(out, source, requests, reuse, inputs, budget, parallel=parallel)
    problem = sr.request_error(out, ROOT)
    sr.require(problem is None, 'The written request does not check: ' + str(problem))
    return request


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], allow_abbrev=False)
    sub = parser.add_subparsers(dest='command', required=True)
    r = sub.add_parser('requests', allow_abbrev=False)
    r.add_argument('--plan', type=Path, required=True)
    r.add_argument('--session', action='append', required=True)
    r.add_argument('--out', type=Path, required=True)
    r.add_argument('--base', type=Path, default=Path('.'), help="the folder the plan's relative paths start from")
    g = sub.add_parser('seal', allow_abbrev=False,
                       help='a laptop seal (the job bundle, or the byte-identity bundle) started only on one passing reading')
    g.add_argument('--log', type=Path, required=True)
    g.add_argument('sealer_args', nargs=argparse.REMAINDER, help="-- then the sealer's own arguments")
    g.add_argument('--output-dir', type=Path, required=True, help="the sealer's --output-dir: its drive is the disk the gate reads")
    q = sub.add_parser('request', allow_abbrev=False,
                       help='order 85: write and check a seal request; nothing is sealed on the laptop')
    q.add_argument('--source', default='HEAD', help='the commit the instance seals (default HEAD)')
    q.add_argument('--requests', type=Path, required=True, help='requests.json, from the requests command')
    q.add_argument('--reuse', type=Path, required=True, help='the reuse bundle (its manifest names the assets)')
    q.add_argument('--inputs', type=Path, required=True, help='runtime.candidate.lock and provider_inventory.json')
    q.add_argument('--ledger', type=Path, action='append', required=True, help='loop ledger(s) the IV.3 cap reads')
    q.add_argument('--forecast-minutes', type=float, required=True)
    q.add_argument('--storage-forecast-usd', type=float, required=True)
    q.add_argument('--instance-types', default=None, help='the declared instance types, comma separated')
    q.add_argument('--uncompared', action='store_true', help='the job belongs to no comparison (as the sealer takes it)')
    q.add_argument('--parallel', type=int, default=16)
    q.add_argument('--out', type=Path, required=True, help='a new folder')
    a = sub.add_parser('admit', allow_abbrev=False)
    for name in ('--job', '--run', '--reuse', '--out'):
        a.add_argument(name, type=Path, required=True)
    a.add_argument('--request', type=Path, default=None,
                   help='order 85: the seal request a launch record job was launched from (required for one)')
    args = parser.parse_args(argv)
    if args.command == 'requests':
        plan = json.loads(args.plan.read_text(encoding='utf-8'))
        requests = plan_requests(plan, args.session, args.base)
        sr.write(args.out, dict(requests=requests))
        print('%d requests' % len(requests))
        return 0
    if args.command == 'request':
        budget = request_budget(args.ledger, args.forecast_minutes, args.storage_forecast_usd, args.instance_types,
                                args.uncompared)
        request = write_checked_request(args.out, args.source, args.requests, args.reuse, args.inputs, budget,
                                        args.parallel)
        # Counts only (SEALED-RUN-A): no path, value or digest of the inputs is printed.
        print('seal request written and checked: %d files, %d requests' % (len(request['files']),
                                                                           len(request['job']['requests'])))
        return 0
    if args.command == 'seal':
        sealer_args = args.sealer_args[1:] if args.sealer_args[:1] == ['--'] else args.sealer_args
        # The gate's expected size (EXPECTED_BYTES['seal']) holds only for a seal that links a sealed
        # asset archive; one that builds the archive writes 13 to 22 GB, so it is refused here.
        sr.require('--reuse-assets' in sealer_args, 'The gated seal links a sealed asset archive: --reuse-assets is required')
        # The gate reads the drive of this --output-dir, so the sealer is given no other: any
        # argument the sealer's parser could read as --output-dir (it takes abbreviations) refuses.
        sr.require(not [a for a in sealer_args if a.startswith('--o') and '--output-dir'.startswith(a.split('=', 1)[0])],
                   "The gated seal takes its --output-dir before --, never among the sealer's arguments")
        # The sealer's parser takes abbreviations and the last value wins: exactly one --reuse-assets,
        # written in full with its value apart, and no other spelling of it, or the drive is not known.
        spellings = [a for a in sealer_args if a.startswith('--r') and '--reuse-assets'.startswith(a.split('=', 1)[0])]
        sr.require(spellings == ['--reuse-assets'], 'The gated seal takes exactly one --reuse-assets, written in full')
        reuse = Path(sealer_args[sealer_args.index('--reuse-assets') + 1])
        # A link across drives is a copy of the whole archive (bind_existing_assets): refused.
        sr.require(same_drive(reuse, args.output_dir), 'The reuse bundle and --output-dir are on different drives: '
                   'the sealer would copy the whole asset archive')
        drive = Path(args.output_dir).resolve().anchor or str(Path(args.output_dir).resolve())
        reading = wait_for_room('seal', args.log, drive)
        print('started on %s GB memory, %s GB disk' % (reading['memory_gb'], reading['disk_gb']))
        return subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'tools' / 'prepare_ordinary_final_run.py'),
                               '--output-dir', str(args.output_dir), *sealer_args]).returncode
    import instance_reaper
    private = instance_reaper.main_private()
    live = dict(budget_ledger=private / 'budget_ledger.jsonl', spend_store=private / 'cloud_reference_spend.jsonl',
                r_ledger=instance_reaper.R_LEDGER)
    rows = admit(args.job, args.run, args.reuse, args.out, live, private / 'budget_ledger.jsonl', request=args.request)
    print('%d of %d admitted' % (len(rows), len(rows)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
