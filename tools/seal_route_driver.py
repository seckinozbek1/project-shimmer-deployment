"""Route S (#252) on the laptop: the seal job's requests from a plan, and the returned bundles made
laptop bundles. Never launches; the job bundle launches through the bound wrapper like any bundle.

    requests  --plan PLAN.json --session NAME [--session NAME ...] --out requests.json
              One request per plan entry, its arguments the sealer's own (the plan's common ones
              less the four the job sets itself: --reuse-assets, --inputs-from, --ledger and
              --output-dir). Seal the job with:
              tools/prepare_ordinary_final_run.py --arm S --seal-requests requests.json
              --reuse-assets <the reuse bundle> --inputs-from <inputs> --ledger <private ledger> ...
    admit     --job <job bundle> --run <the job's run folder> --sealed <folder of returned bundles>
              --reuse <the reuse bundle> --out <new folder>
              Each returned bundle refused when the read copy is stale (seal_route.stale_reason
              against the live private ledger, the job's own lines aside), else copied out, its
              asset archive linked by digest, its binding written (the project digest from the
              manifest when the archive is in the store); then the reverify and the preflight
              through the bound tools, one bundle at a time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tools' / 'loop')]
import seal_route as sr  # noqa: E402

JOB_SET_FLAGS = ('--reuse-assets', '--inputs-from', '--ledger', '--output-dir')
# D-585, D-099: what the laptop must have free before a heavy step starts: memory, and disk above
# the standing orders' own floor (standing_orders_check.DISK_FLOOR, read at each gate, never copied)
# after the step's expected size.
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


def admits(reading, expected_bytes=0):
    """The one reading admits the step: memory, no other seal, and disk free after the step's own
    expected size at or above the D-099 floor, read from standing_orders_check now."""
    import standing_orders_check as orders
    disk = reading.get('disk_bytes', reading['disk_gb'] * 2 ** 30)
    return (reading['memory_gb'] >= MIN_MEMORY_GB and reading['disk_gb'] >= MIN_DISK_GB and reading['other_seals'] == 0
            and disk - expected_bytes >= orders.DISK_FLOOR)


def wait_for_room(step, log, disk_path, read=resources, sleep=None, clock=None):
    """Gate a heavy step on ONE reading per wait cycle and log that same reading as its start line
    (never a second reading taken after the condition held: the gate and the record are one
    reading). Returns the reading the step started on."""
    import time
    sleep = time.sleep if sleep is None else sleep
    clock = time.time if clock is None else clock
    while True:
        reading = read(disk_path)
        expected = EXPECTED_BYTES.get(step, 0)
        if admits(reading, expected):
            import standing_orders_check as orders
            line = dict(reading, step=step, event='start', time_epoch=round(clock(), 3), expected_bytes=expected,
                        disk_floor_bytes=orders.DISK_FLOOR)
            with open(log, 'a', encoding='utf-8') as stream:
                stream.write(json.dumps(line, sort_keys=True) + chr(10))
            return reading
        sleep(WAIT_SECONDS)


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


def admit(job_bundle, run_folder, reuse, out, live, ledger, steps=True, run=subprocess.run, gate=None, lock=None, unlock=None):
    """The returned bundles of one seal job made laptop bundles, all or none. Bound to the job: the
    run folder's launch intent names the job bundle's manifest; the bundles come only from the
    collected evidence the controller verified; each bundle's manifest and seal digests are the job
    result's own row; the result names the job's manifest; the reuse bundle's manifest is the one the
    job sealed. Under the ledger lock, held from the stale check through the last preflight: the read
    copies (`live`: {key: path}) checked once, then each bundle staged, linked, bound, reverified and
    preflighted. Only when every bundle passes are they moved into `out` in one rename; otherwise
    nothing is admitted and the staging folder is kept, renamed refused, for the operator."""
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
    own = own_identifiers(run_folder, job_sha, job_bundle)
    sr.require(not out.exists(), 'The admission folder exists already')
    held = lock(ledger)
    try:
        reason = sr.stale_reason(job, live, own)
        sr.require(reason is None, 'Seal job read copy is stale: ' + str(reason))
        staging = out.with_name(out.name + '.staging')
        sr.require(not staging.exists(), 'A staging folder of an earlier admission is there; look at it first')
        rows = []
        try:
            sealed, result = collected(run_folder, staging / 'collected')
            sr.require(result.get('job_manifest_sha256') == job_sha, 'The collected result is another job\'s')
            rows_by = {r['name']: r for r in result.get('rows') or []}
            bundles = staging / 'bundles'
            bundles.mkdir()
            for request in job['requests']:
                row = rows_by.get(request['name']) or {}
                source = sealed / request['name']
                sr.require(row.get('rc') == 0 and (source / 'seal.json').is_file(), 'Not sealed by the job: ' + request['name'])
                sr.require(sr.sha(source / 'execution_manifest.json') == row.get('manifest_sha256')
                           and sr.sha(source / 'seal.json') == row.get('seal_sha256'),
                           'A returned bundle is not the one the job sealed: ' + request['name'])
                target = bundles / request['name']
                shutil.move(str(source), str(target))
                entry = dict(name=request['name'])
                entry.update(sr.admit_returned(target, reuse))
                entry['binding'] = binding(target, out / request['name'])['manifest_sha256']
                if steps:
                    for step in ('ordinary_final_bound_reverify.py', 'ordinary_final_bound_preflight.py'):
                        (gate or (lambda name: wait_for_room(name, staging / 'gate_log.jsonl', out.parent)))(step)
                        done = run([sys.executable, '-X', 'utf8', str(ROOT / 'tools' / step), '--bundle', str(target)],
                                   capture_output=True, text=True)
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
    a = sub.add_parser('admit', allow_abbrev=False)
    for name in ('--job', '--run', '--reuse', '--out'):
        a.add_argument(name, type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'requests':
        plan = json.loads(args.plan.read_text(encoding='utf-8'))
        requests = plan_requests(plan, args.session, args.base)
        sr.write(args.out, dict(requests=requests))
        print('%d requests' % len(requests))
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
    rows = admit(args.job, args.run, args.reuse, args.out, live, private / 'budget_ledger.jsonl')
    print('%d of %d admitted' % (len(rows), len(rows)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
