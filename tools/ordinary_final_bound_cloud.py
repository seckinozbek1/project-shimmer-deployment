"""One operator-authorized run bound to the sealed bundle named by its authorization_binding.json.

The binding file, written when the bundle is sealed and checked here before
anything else, names the sealed source commit, the manifest, seal, project archive
and asset archive digests and the preparation commit. The controller is bound to
exactly those values and refuses on any difference, on a consumed authorization or
without a passed local reverification. HEAD may have moved by evidence-only
commits; what launches is the sealed archive whose digest is bound here.

Every launch is a loop launch: the ledger, the purpose and the measured forecast basis
are required, and the budget guard decides before the launch request (IV.3).
--output-dir runs the bundle in a fresh run folder outside it (a sealed run's folder
must sit outside the repository); without it the run folder is the bundle, as before.
--detach starts the controller as a detached process that survives this one.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

import ordinary_final_cloud as controller
import ordinary_final_run as run
from ordinary_final_run import read, write, sha, require
import loop_budget_guard as guard

DETACH_LOG = 'controller_detached.log'


def spawn_detached(argv, log):
    """Start `python argv...` detached from this process: its own process group, no console,
    and (where the job allows it) outside this process's job, so ending this process, or the
    session that started it, does not end the controller. Returns the child's pid."""
    stream = open(log, 'ab')
    try:
        base = [sys.executable, *map(str, argv)]
        if os.name == 'nt':
            flags = (getattr(subprocess, 'DETACHED_PROCESS', 0x8) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x200)
                     | getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            for extra in (getattr(subprocess, 'CREATE_BREAKAWAY_FROM_JOB', 0x01000000), 0):
                try:
                    return subprocess.Popen(base, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                            creationflags=flags | extra, close_fds=True).pid
                except OSError:
                    if not extra:
                        raise
        return subprocess.Popen(base, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                start_new_session=True, close_fds=True).pid
    finally:
        stream.close()


def consumed(bundle):
    """A bundle launched once, in place (LAUNCH_INTENT.json) or in a run folder (RUN_FOLDER.json)."""
    return (Path(bundle) / 'LAUNCH_INTENT.json').exists() or (Path(bundle) / 'RUN_FOLDER.json').exists()


def run_folder(bundle, output_dir, sealed):
    """The folder the run writes into. Without --output-dir it is the bundle (the development
    default). With it, a fresh folder <output-dir>/<bundle name> receives a copy of every sealed
    file except the asset archive, which is read where it is. A folder left by an attempt
    refused before its launch intent is kept as evidence and the next attempt takes the next
    name (<bundle name>.2, .3, ...). The bundle records its run folder only once the launch
    intent exists (the controller writes RUN_FOLDER.json then), so it is consumed once."""
    if output_dir is None:
        require(not sealed or not bundle.is_relative_to(controller.ROOT.resolve()),
                'A sealed run folder must sit outside the repository')
        return bundle
    root = Path(output_dir).resolve()
    require(not sealed or not root.is_relative_to(controller.ROOT.resolve()), 'A sealed run folder must sit outside the repository')
    out, n = root / bundle.name, 2
    while out.exists():
        require(not (out / 'LAUNCH_INTENT.json').exists(), 'Authorization already consumed')
        out, n = root / ('%s.%d' % (bundle.name, n)), n + 1
    out.mkdir(parents=True)
    archive = read(bundle / 'execution_manifest.json')['assets_archive']['filename']
    for item in bundle.iterdir():
        if item.is_file() and item.name != archive:
            (out / item.name).write_bytes(item.read_bytes())
    return out


def execute(bundle, plan, output_dir=None):
    b = Path(bundle).resolve()
    binding = read(b / 'authorization_binding.json')
    controller.MANIFEST = binding['manifest_sha256']
    controller.SEAL = binding['seal_sha256']
    controller.PREPARATION = binding['preparation_commit']
    controller.INSTANCE_NAME = guard.instance_name(binding['preparation_commit'][:7] + '-' + binding['manifest_sha256'][:8])
    controller.LAUNCH = dict(plan, bundle_folder=b)
    require(sha(b / 'execution_manifest.json') == binding['manifest_sha256'] and sha(b / 'seal.json') == binding['seal_sha256'],
            'Authorized identity changed')
    m = read(b / 'execution_manifest.json')
    seal = read(b / 'seal.json')
    require(m['source_commit'] == binding['source_commit'], 'Sealed source commit differs from the binding')
    require(m['source_archive_sha256'] == binding['project_sha256'], 'Project identity changed')
    require(sha(b / 'project.tar.gz') == binding['project_sha256'], 'Project archive bytes changed')
    assets = m['assets_archive']
    require(assets['filename'] == 'assets.tar' and assets['sha256'] == binding['assets_sha256'], 'Asset identity changed')
    # The budget is the sealed IV.3 budget, read from the manifest the binding names: an
    # ordered candidate list that starts with the A10, a soft cap below the hard cap, and a
    # hard cap that is the sealed per-run cap. No figure is typed here.
    candidates = m.get('instance_candidates')
    require(isinstance(candidates, list) and candidates and candidates[0].get('type') == guard.PREFERRED_TYPE
            and 0 < m['soft_budget_usd'] < m['hard_ceiling_usd'] == m['per_run_cap_usd'], 'Budget differs from the authorization')
    # Multi-round and protected tests are admitted exactly when declared, sealed and valid.
    require(m['model_mode'] == 'final' and m['max_runs'] == 1, 'Scope differs from the authorization')
    run.admit_workload(m, seal, b)
    # Consumed by a launch in place (LAUNCH_INTENT.json) or in a run folder (RUN_FOLDER.json),
    # with or without --output-dir this time (A6).
    require(not consumed(b), 'Authorization already consumed')
    verified = read(b / 'asset_verification.json')
    require(verified['passed'] and verified['manifest_sha256'] == binding['manifest_sha256']
            and verified['archive_sha256'] == binding['assets_sha256'], 'Asset verification absent for this identity')
    require(all(r['ref_bytes'] == 40 for r in verified['default_revision_resolutions']), 'Refs not verified at 40 bytes')
    local = read(b / 'AUTHORIZED_LOCAL_REVERIFICATION.json')
    require(local['passed'] and local['manifest_sha256'] == binding['manifest_sha256'], 'Local reverification missing')
    live = read(b / 'authorized_live_preflight.json')
    require(live['passed'] and live['manifest_sha256'] == binding['manifest_sha256'], 'Live preflight missing')
    # The archive path is stored relative to the repository when the bundle is inside it and
    # absolute otherwise, so a bundle outside the repository launches as one inside does.
    archive = b / assets['filename']
    try:
        stored = archive.relative_to(controller.ROOT).as_posix()
    except ValueError:
        stored = archive.as_posix()
    write(b / 'assets_transfer_archive.json', dict(path=stored, bytes=assets['bytes'], sha256=assets['sha256'],
          manifest_sha256=binding['manifest_sha256']))
    folder = run_folder(b, output_dir, seal.get('exposure') == 'sealed')
    controller.BASE = folder
    write(folder / 'bound_controller_identity.json', dict(wrapper_sha256=sha(__file__), controller_sha256=sha(controller.__file__),
          binding=binding, maximum_instances=1, maximum_runs=max(1, len(plan.get('batch') or [])), bundle_folder=b.as_posix()))
    controller.execute()


def plan_from(args):
    batch = None
    if args.batch:
        batch = [dict(item=e['item'], arm=e['arm'], bundle=Path(e['bundle'])) for e in read(args.batch)['entries']]
    report = dict(test_version=args.test_version, authors=dict(test=args.test_author, key=args.key_author,
                  scorer=args.scorer_author), scorer_version=args.scorer_version)
    return dict(ledger=args.ledger, read_ledgers=args.read_ledger or [], purpose=args.purpose,
                forecast_minutes=args.forecast_minutes, forecast_includes_upload=args.forecast_includes_upload,
                storage_forecast_usd=args.storage_forecast_usd, r_inputs=args.r_inputs, test_manifest=args.test_manifest,
                frozen_tag=args.frozen_tag, batch=batch, report=report)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, default=None, help='run in a fresh folder here instead of in the bundle')
    p.add_argument('--ledger', type=Path, required=True, help='loop ledger: read, and receives the launch and termination lines')
    p.add_argument('--read-ledger', type=Path, action='append', help="another ledger the guard reads (R's)")
    p.add_argument('--r-inputs', type=Path, default=None, help='R_INPUTS.json when role R launches')
    p.add_argument('--purpose', required=True, help='one short line: why this run')
    p.add_argument('--forecast-minutes', type=float, required=True, help='measured basis in minutes (docs/loop/BUDGET.md)')
    p.add_argument('--forecast-includes-upload', action='store_true')
    p.add_argument('--storage-forecast-usd', type=float, required=True)
    p.add_argument('--test-manifest', type=Path, default=None, help="role B's seal manifest (sealed runs)")
    p.add_argument('--frozen-tag', default=None, help='the frozen tag a sealed run must be built from')
    p.add_argument('--batch', type=Path, default=None, help='batch file: {"entries": [{item, arm, bundle}]}')
    p.add_argument('--test-version', default=None)
    p.add_argument('--test-author', default=None)
    p.add_argument('--key-author', default=None)
    p.add_argument('--scorer-author', default=None)
    p.add_argument('--scorer-version', default=None)
    p.add_argument('--detach', action='store_true', help='start the controller detached and return')
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(argv)
    if args.detach:
        rest = [a for a in argv if a != '--detach']
        log = Path(args.bundle).resolve() / DETACH_LOG
        pid = spawn_detached([Path(__file__).resolve(), *rest], log)
        write(Path(args.bundle).resolve() / 'controller_process.json', dict(pid=pid, detached=True))
        print('Controller started detached; its output is in the bundle', flush=True)
        return 0
    execute(args.bundle, plan_from(args), args.output_dir)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
