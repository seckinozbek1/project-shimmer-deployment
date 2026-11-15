"""Route S (#252, D-565 order 3, D-585): ordinary final bundles sealed on a Lambda instance.

A sealing job is a loop launch like any other: the laptop seals one small job bundle (arm S),
the controller launches it under the guard, the ledger and the reaper, and the instance runs the
BOUND sealer (tools/prepare_ordinary_final_run.py at the job's commit) once per request, many in
parallel. The ledger stays on the laptop as the only writer of totals.

What travels in the job bundle, each a support file under its digest:
  - SEAL_SOURCE: the bound commit's tracked tree, read from git's objects (bound_tree_archive), and
    COMMIT_OBJECT: that commit's own object, so the instance re-creates the SAME commit id over the
    same tree (`git hash-object -t commit -w`), and the seals it makes name the laptop's commit;
    the tree id is held to the sealed one, so a different tree refuses;
  - JOB_FILE: the requests (each the sealer's own arguments, file arguments named by their place in
    WORKLOADS), the declared read copies (the budget ledger, the spend store, the comparison
    registry, the asset copy history, R's ledger) with their digests and the time they were taken,
    and the standing-orders attestation (orders 1 to 3, checked on the laptop's records at that
    time). No credential path or value travels;
  - WORKLOADS: every file a request names (staged workloads, items, passes, replay prompts, inputs);
  - REUSE_MANIFEST: the execution manifest of the bundle whose asset archive the seals reuse.

On the instance (run_job): the commit, the inputs in place, the archive, the model files and the
wheels hashed ONCE (`verified_inputs`, D-565 item 2's full check), the seals run, one asset
verification gives every bundle its receipt, each project archive is written once by its
fingerprint to the persistent store (item 3) and the returned bundle carries none, and no bundle
carries the 22 GB asset archive. Back on the laptop (`admit_returned`): the read copy is refused
when the live ledger moved beyond the job's own launch lines, and each bundle gets its asset
archive linked again by digest.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

SEAL_SOURCE = 'seal_source.tar'
COMMIT_OBJECT = 'commit_object.bin'
JOB_FILE = 'seal_job.json'
WORKLOADS = 'seal_workloads.tar'
REUSE_MANIFEST = 'reuse_manifest.json'
JOB_SCHEMA = 'shimmer-seal-job-v1'
STORE_FOLDER = 'projects'            # under the persistent store's mount: project-<sha256>.tar.gz
PROJECT_IN_STORE = 'PROJECT_IN_STORE.json'
VERIFIED_INPUTS_ENV = 'SHIMMER_SEAL_VERIFIED_INPUTS'
ATTESTATION_ENV = 'SHIMMER_SEAL_ATTESTATION'
BLOCK = 8 * 1024 * 1024
HEX64 = re.compile(r'[0-9a-f]{64}')
HEX40 = re.compile(r'[0-9a-f]{40}')
TOKEN = re.compile(r'\{ws\}/([A-Za-z0-9_.\-/]+)')
# The read copies, by the place the guard and the sealer read each from: inside the checkout
# (docs/loop/private, found through git's common directory) and R's ledger under the home folder.
READ_COPIES = {
    'budget_ledger': 'docs/loop/private/budget_ledger.jsonl',
    'spend_store': 'docs/loop/private/cloud_reference_spend.jsonl',
    'comparisons': 'docs/loop/private/comparisons.jsonl',
    'asset_copy_history': 'docs/loop/private/asset_copy_history.jsonl',
    'r_ledger': '~/local/shimmer-roles/_handoff/R_ledger.jsonl',
}
# C4 launch 2: each read copy is a TOP-LEVEL support file of the job bundle (read_copy_<key>), since
# the bound wrapper's --output-dir copies only the bundle's top-level files into the run folder.
READ_COPY_PREFIX = 'read_copy_'
ATTESTED_ORDERS = (1, 2, 3)


def read_copy_name(key):
    """The support file a read copy travels as, beside the manifest (no subfolder)."""
    return READ_COPY_PREFIX + key


class RouteError(RuntimeError):
    """A one-line refusal of route S."""


def require(condition, message):
    if not condition:
        raise RouteError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(BLOCK), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')


# ---------------------------------------------------------------------------
# the job, as the laptop seals it


def read_copies(main_private, r_ledger, now=None):
    """{key: {source, path, sha256, bytes}} of every read copy that exists, and the time taken. A
    copy is the file's bytes at that moment; nothing else of the private folder travels."""
    sources = {'budget_ledger': Path(main_private) / 'budget_ledger.jsonl',
               'spend_store': Path(main_private) / 'cloud_reference_spend.jsonl',
               'comparisons': Path(main_private) / 'comparisons.jsonl',
               'asset_copy_history': Path(main_private) / 'asset_copy_history.jsonl',
               'r_ledger': Path(r_ledger)}
    out = {}
    for key, path in sources.items():
        if path.is_file():
            data = path.read_bytes()
            out[key] = dict(path=READ_COPIES[key], sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), data=data)
    require('budget_ledger' in out and 'spend_store' in out, 'A seal job needs read copies of the ledger and the spend store')
    return out, (time.time() if now is None else now)


def attestation(refusals, now=None):
    """The standing orders the guard reads before a seal, checked on the laptop's own records:
    the attestation the instance's guard reads in their place (it has none of those records)."""
    require(refusals == [], 'A standing order does not hold on the laptop: no seal job: %s' % refusals)
    return dict(orders=list(ATTESTED_ORDERS), refusals=[], time_epoch=round(now or time.time(), 3),
                checked_by='standing_orders_check.launch_refusals on the main checkout, by the laptop sealer')


def job_requests(requests, folder, extra=None):
    """The requests with every file argument moved into WORKLOADS: [{name, argv}], each `{ws}/...`
    a member of the archive written to `folder`. File arguments are the sealer's own flags."""
    FILE_FLAGS = ('--workload', '--items', '--b1-checkpoints', '--replay-prompts', '--image-env-manifest')
    members, out = {}, []
    for k, request in enumerate(requests):
        name = request['name']
        require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.\-]{0,95}', name or '') is not None, 'A request name is required')
        argv = list(request['argv'])
        for i, value in enumerate(argv[:-1]):
            if argv[i] in FILE_FLAGS:
                source = Path(argv[i + 1])
                require(source.exists(), 'A request names a file that does not exist: %s' % source.name)
                place = '%d/%s/%s' % (k, argv[i].lstrip('-'), source.name)
                members[place] = source
                argv[i + 1] = '{ws}/' + place
        require(not any(a in argv for a in ('--output-dir', '--reuse-assets', '--inputs-from', '--ledger')),
                'A request names a flag the job sets itself')
        out.append(dict(name=name, argv=argv))
    require(len({r['name'] for r in out}) == len(out), 'Request names repeat')
    for place, source in (extra or {}).items():
        require(Path(source).is_file(), 'A job input does not exist: %s' % Path(source).name)
        members[place] = Path(source)
    archive = Path(folder) / WORKLOADS
    with tarfile.open(archive, 'w', format=tarfile.PAX_FORMAT) as stream:
        for place, source in sorted(members.items()):
            stream.add(str(source), arcname=place, recursive=True, filter=_plain)
    return out, archive


def _plain(info):
    info.uid = info.gid = 0
    info.uname = info.gname = ''
    info.mtime = 0
    return info if (info.isfile() or info.isdir()) else None


def job_block(commit, tree, requests, copies, taken, attested, parallel=16):
    require(HEX40.fullmatch(commit or '') and HEX40.fullmatch(tree or ''), 'The job names its commit and tree')
    require(isinstance(parallel, int) and 1 <= parallel <= 64, 'Parallel seals are 1 to 64')
    return dict(schema=JOB_SCHEMA, commit=commit, tree=tree, requests=requests, parallel=parallel,
                read_copies={k: {f: v[f] for f in ('path', 'sha256', 'bytes')} for k, v in copies.items()},
                read_copy_time_epoch=round(taken, 3), attestation=attested)


def job_declaration(manifest, support):
    """The sealed job block, or a one-line refusal (the runner's admission)."""
    job = manifest.get('seal_job')
    require(isinstance(job, dict) and job.get('schema') == JOB_SCHEMA, 'An arm S bundle carries its seal job')
    require(HEX40.fullmatch(job.get('commit') or '') and HEX40.fullmatch(job.get('tree') or ''),
            'The seal job names its commit and tree')
    for name in (SEAL_SOURCE, COMMIT_OBJECT, JOB_FILE, WORKLOADS, REUSE_MANIFEST):
        require(isinstance(support.get(name), str) and HEX64.fullmatch(support[name]), 'The seal job file is not sealed: ' + name)
    require(isinstance(job.get('requests'), list) and job['requests'], 'The seal job has no request')
    require(set(job.get('read_copies') or {}) <= set(READ_COPIES), 'An undeclared read copy')
    require((job.get('attestation') or {}).get('refusals') == [], 'The seal job carries no clean attestation')
    return job


# ---------------------------------------------------------------------------
# the instance


def exact_commit(git, commit_object, commit, tree):
    """The checkout's commit made the laptop's commit: its own object written (same bytes, same id),
    the branch moved to it, and its tree the sealed one (a different tree refuses)."""
    written = git('hash-object', '-t', 'commit', '-w', str(commit_object)).strip()
    require(written == commit, 'The commit object is not the sealed commit (%s, sealed %s)' % (written, commit))
    require(git('rev-parse', commit + '^{tree}').strip() == tree, "The sealed commit's tree is not the sealed tree")
    git('update-ref', 'refs/heads/gate', commit)
    require(git('rev-parse', 'HEAD').strip() == commit, 'HEAD is not the sealed commit')
    return dict(commit=commit, tree=tree)


def place_inputs(tree, base, job, home):
    """The checkout made ready for the bound sealer: the read copies where the guard reads them, the
    frozen model files the project archive carries, the wheelhouse and the reuse bundle. Returns the
    folders the requests' arguments name."""
    tree, base = Path(tree), Path(base)
    copies = {}
    for key, entry in job['read_copies'].items():
        data = (base / read_copy_name(key)).read_bytes()
        require(hashlib.sha256(data).hexdigest() == entry['sha256'], 'Read copy changed: ' + key)
        target = Path(home) / entry['path'][2:] if entry['path'].startswith('~/') else tree / entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        copies[key] = str(target)
    spec = json.loads((tree / 'config/final_models.json').read_text(encoding='utf-8'))
    for role in ('producer', 'auditor'):
        for entry in spec[role]['files'].values():
            target = tree / entry['path']
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                os.link(base / 'project' / entry['path'], target)
    wheels = tree / 'output/cloud_wheels/ordinary_final_cp312'
    wheels.parent.mkdir(parents=True, exist_ok=True)
    if not wheels.exists():
        os.symlink(base / 'wheels', wheels, target_is_directory=True)
    reuse = base / 'reuse_bundle'
    reuse.mkdir(exist_ok=True)
    shutil.copyfile(base / REUSE_MANIFEST, reuse / 'execution_manifest.json')
    previous = json.loads((reuse / 'execution_manifest.json').read_text(encoding='utf-8'))['assets_archive']
    if not (reuse / previous['filename']).exists():
        os.link(base / 'assets.tar', reuse / previous['filename'])
    workloads = base / 'ws'
    with tarfile.open(base / WORKLOADS) as stream:
        for member in stream.getmembers():
            target = (workloads / member.name).resolve()
            require(target.is_relative_to(workloads.resolve()) and (member.isfile() or member.isdir()),
                    'Workload member refused: ' + member.name)
        stream.extractall(workloads, **({'filter': 'data'} if hasattr(tarfile, 'data_filter') else {}))
    return dict(copies=copies, reuse=str(reuse), workloads=str(workloads))


CHUNK = 1024 * 1024
CHUNKS = 16


def chunk_offsets(size):
    """The offsets of the sampled chunks: CHUNKS evenly spread over the file, the first and the last
    included (all of a file shorter than that)."""
    if size <= CHUNK * CHUNKS:
        return list(range(0, max(size, 1), CHUNK))
    step = (size - CHUNK) // (CHUNKS - 1)
    return [k * step for k in range(CHUNKS - 1)] + [size - CHUNK]


def chunk_digests(path, size):
    out = {}
    with Path(path).open('rb') as stream:
        for offset in chunk_offsets(size):
            stream.seek(offset)
            out[str(offset)] = hashlib.sha256(stream.read(CHUNK)).hexdigest()
    return out


def verified_inputs(paths, workers=8, hasher=sha):
    """D-565 item 2's full check, once per job: every large input hashed (in parallel), each
    recorded with the size, modification time and inode it had and the digests of sampled chunks,
    so a seal that finds the same stat and the same chunks uses the digest and one that does not
    hashes again. The full check before the final read is the launch instance's own
    archive_integrity, which hashes the archive whole on every launch."""
    paths = sorted({str(Path(p).resolve()) for p in paths})

    def state(path):
        st = os.stat(path)
        return dict(size=st.st_size, mtime_ns=st.st_mtime_ns, inode=st.st_ino, chunks=chunk_digests(path, st.st_size))
    before = {path: state(path) for path in paths}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        digests = dict(zip(paths, pool.map(hasher, paths)))
    out = {}
    for path in paths:
        # The stat and the chunks are taken before the hash and again after it: a file that changed
        # while it was hashed has no recorded digest at all (the job stops).
        require(state(path) == before[path], 'A large input changed while it was hashed: ' + Path(path).name)
        out[path] = dict(before[path], sha256=digests[path])
    return out


def recorded_sha(path, record):
    """A digest from the job's verified-inputs record when the file still has the stat it was
    hashed with; None otherwise (the caller then hashes it)."""
    entry = (record or {}).get(str(Path(path).resolve()))
    if not entry:
        return None
    st = os.stat(path)
    if (st.st_size, st.st_mtime_ns, st.st_ino) != (entry['size'], entry['mtime_ns'], entry['inode']):
        return None
    if chunk_digests(path, st.st_size) != entry.get('chunks'):
        return None
    return entry['sha256']


# C4 launch 3: a failed seal's cause, small enough to come back in any pack: its exit code and the last
# bytes of its log (stdout and stderr together), beside the bundle in the evidence folder.
SEAL_TAIL_BYTES = 4096
SEAL_TAIL_SUFFIX = '.seal_tail.json'
# The whole log stays in the evidence too, bounded to its last SEAL_LOG_BYTES (the pack has a fixed deadline).
SEAL_LOG_BYTES = 64 * 1024


def cap_log(log_path, limit=None):
    """Keep only the last `limit` bytes of a seal's log in place; returns its size before."""
    limit = SEAL_LOG_BYTES if limit is None else limit
    log_path = Path(log_path)
    size = log_path.stat().st_size if log_path.is_file() else 0
    if size > limit:
        with log_path.open('rb') as stream:
            stream.seek(size - limit)
            kept = stream.read(limit)
        log_path.write_bytes(kept)
    return size


def seal_tail(log_path, row):
    """{name, rc, seconds, reason, log_bytes, tail}: the request's row and the last SEAL_TAIL_BYTES of
    its log, decoded with replacement, never more."""
    log_path = Path(log_path)
    size = log_path.stat().st_size if log_path.is_file() else 0
    tail = b''
    if size:
        with log_path.open('rb') as stream:
            stream.seek(max(0, size - SEAL_TAIL_BYTES))
            tail = stream.read(SEAL_TAIL_BYTES)
    return dict(row, log_bytes=size, tail=tail.decode('utf-8', errors='replace'))


def strip_returned(bundle):
    """C4 launch 3: the archives a returned bundle must not carry back, removed whatever the seal's
    outcome (a failed seal kept the reuse archive's hard link, about 13 GB, and the evidence pack ran
    past its deadline). Returns the names removed."""
    bundle = Path(bundle)
    names = {'assets.tar', 'project.tar.gz'}
    try:
        named = json.loads((bundle / 'execution_manifest.json').read_text(encoding='utf-8'))['assets_archive']['filename']
        if isinstance(named, str) and Path(named).name == named:
            names.add(named)
    except Exception:
        pass
    removed = []
    for name in sorted(names):
        if (bundle / name).is_file():
            (bundle / name).unlink()
            removed.append(name)
    return removed


def request_argv(request, places, out_dir, ledger, inputs):
    argv = [a.replace('{ws}', places['workloads']) for a in request['argv']]
    for a in argv:
        require('{ws}' not in a and not TOKEN.search(a), 'A request argument names no workload member')
    return ['--output-dir', str(out_dir), '--reuse-assets', places['reuse'], '--inputs-from', str(inputs),
            '--ledger', str(ledger)] + argv


def run_requests(job, places, tree, out_root, env, deadline, run=subprocess.run):
    """Every request through the bound sealer, `job['parallel']` at a time; [{name, rc, seconds}]."""
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    ledger = Path(places['copies']['budget_ledger'])

    def one(request):
        started = time.time()
        out = out_root / request['name']
        log_path = str(out) + '.seal.log'
        # Every request ends in a row: a failure to start, a timeout or any other error is that
        # request's failure (its reason recorded), never an exception that skips the strip.
        try:
            argv = [sys.executable, '-X', 'utf8', 'tools/prepare_ordinary_final_run.py'] + request_argv(
                request, places, out, ledger, Path(places['workloads']) / 'inputs')
            left = deadline - time.time()
            if left <= 60:
                row = dict(name=request['name'], rc=None, seconds=0.0, reason='deadline')
            else:
                with open(log_path, 'wb') as log:
                    try:
                        done = run(argv, cwd=str(tree), env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                   timeout=left - 30)
                        row = dict(name=request['name'], rc=done.returncode, seconds=round(time.time() - started, 3))
                    except subprocess.TimeoutExpired:
                        row = dict(name=request['name'], rc=None, seconds=round(time.time() - started, 3), reason='timeout')
        except Exception as exc:
            row = dict(name=request['name'], rc=None, seconds=round(time.time() - started, 3),
                       reason='%s: %s' % (type(exc).__name__, ' '.join(str(exc).split())[:300]))
        try:
            tail = seal_tail(log_path, row)
            cap_log(log_path)
            write(str(out) + SEAL_TAIL_SUFFIX, tail)
        except Exception as exc:
            row['tail_error'] = type(exc).__name__
        return row
    # The first request alone, so the wheel member cache it fills serves every later seal; then the
    # rest, `parallel` at a time.
    first = [one(job['requests'][0])]
    with concurrent.futures.ThreadPoolExecutor(max_workers=job['parallel']) as pool:
        return first + list(pool.map(one, job['requests'][1:]))


def store_project(bundle, store, copy=shutil.copyfile):
    """Item 3: the bundle's project archive written once by its fingerprint into the store
    (moved in from a temporary name; an existing file of that name is never replaced, and is held
    to its digest), then removed from the bundle, which records where it went."""
    bundle, store = Path(bundle), Path(store)
    manifest = json.loads((bundle / 'execution_manifest.json').read_text(encoding='utf-8'))
    digest = manifest['source_archive_sha256']
    require(sha(bundle / 'project.tar.gz') == digest, 'Project archive differs from its manifest')
    store.mkdir(parents=True, exist_ok=True)
    target = store / ('project-%s.tar.gz' % digest)
    if target.exists():
        require(sha(target) == digest, 'A stored project archive does not hold its own digest: ' + target.name)
        reused = True
    else:
        part = target.with_name(target.name + '.%d.part' % os.getpid())
        copy(bundle / 'project.tar.gz', part)
        require(sha(part) == digest, 'The project archive copied to the store does not hold its digest')
        try:
            os.link(part, target)      # never replaces: a name another seal stored first stays
            reused = False
        except FileExistsError:
            reused = True
        finally:
            part.unlink()
        require(sha(target) == digest, 'The stored project archive does not hold its digest')
    (bundle / 'project.tar.gz').unlink()
    record = dict(sha256=digest, bytes=target.stat().st_size, store_name=target.name, already_stored=reused)
    write(bundle / PROJECT_IN_STORE, record)
    return record


# ---------------------------------------------------------------------------
# back on the laptop


def ledger_lines(path):
    return [line for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


# How each read copy is held against its live record on return: a ledger may have gained only the
# job's own launch lines; the spend store must begin with its copy.
STALE_RULES = {'budget_ledger': 'own_lines', 'r_ledger': 'own_lines', 'spend_store': 'prefix'}


def stale_reason(job, live, own):
    """None when every live record (`live`: {key: path}, the budget ledger, R's ledger and the spend
    store) is its read copy with nothing appended but what its rule admits: for a ledger, the job's
    own launch lines (a line naming one of `own`, the job instance's name and id); for the spend store,
    only that it begins with the copy. A record with no copy is held as an empty one. Otherwise why the
    read copies are stale and the bundles must be sealed again."""
    own = {o for o in own if o}
    copies = job['read_copies']
    for key, rule in STALE_RULES.items():
        path = live.get(key)
        entry = copies.get(key) or dict(bytes=0, sha256=hashlib.sha256(b'').hexdigest())
        data = Path(path).read_bytes() if path is not None and Path(path).is_file() else b''
        if hashlib.sha256(data[:entry['bytes']]).hexdigest() != entry['sha256'] or len(data) < entry['bytes']:
            return 'the live %s does not begin with its read copy (rewritten, not appended)' % key
        if rule != 'own_lines':
            continue
        added = [json.loads(l) for l in data[entry['bytes']:].decode('utf-8').splitlines() if l.strip()]
        foreign = [r for r in added if not ({r.get('instance_name'), r.get('instance_id')} & own)]
        if foreign:
            return '%d line(s) of the %s after its read copy are not the seal job\'s own (first: %s)' % (
                len(foreign), key, foreign[0].get('event'))
    return None


def admit_returned(bundle, reuse_bundle, link=os.link):
    """A bundle the job sealed, made a laptop bundle (the driver checks the read copies first, once):
    its asset archive linked again from the reuse bundle (the same digest and size, so not hashed
    again); the project archive left in the store, named by PROJECT_IN_STORE."""
    bundle = Path(bundle)
    manifest = json.loads((bundle / 'execution_manifest.json').read_text(encoding='utf-8'))
    previous = json.loads((Path(reuse_bundle) / 'execution_manifest.json').read_text(encoding='utf-8'))['assets_archive']
    assets = manifest['assets_archive']
    require({k: assets.get(k) for k in ('sha256', 'bytes', 'members')} == {k: previous.get(k) for k in ('sha256', 'bytes', 'members')},
            'The bundle reuses another asset archive than the reuse bundle')
    target = bundle / assets['filename']
    if not target.exists():
        link(Path(reuse_bundle) / previous['filename'], target)
    require(target.stat().st_size == assets['bytes'], 'Linked asset archive size mismatch')
    stored = json.loads((bundle / PROJECT_IN_STORE).read_text(encoding='utf-8'))
    require(stored.get('sha256') == manifest['source_archive_sha256'], 'The stored project archive is not the manifest\'s')
    return dict(bundle=bundle.name, assets_linked=True, project_in_store=stored['store_name'])


# ---------------------------------------------------------------------------
# the job end to end on the instance (called by the runner's arm S after every guard)


def large_inputs(base, places):
    """The files hashed once per job, each by the path the sealer opens: the reuse bundle's link to
    the asset archive (bind_existing_assets), and the model files of the cache (resolved there)."""
    previous = json.loads((Path(places['reuse']) / 'execution_manifest.json').read_text(encoding='utf-8'))['assets_archive']
    return [Path(places['reuse']) / previous['filename']] + [
        p for p in (Path(base) / 'hf_cache').rglob('*') if p.is_file() and not p.is_symlink()]


def run_job(base, job, tree, evidence, deadline, env, home, store, verify_assets, seal_run=subprocess.run):
    """The seal job after the runner's guards and the exact commit: inputs in place, the large inputs
    hashed once, every request sealed, each bundle's asset receipt from one verification, the project
    archives to the store, and the returned bundles stripped of the asset archive. Writes and returns
    the job's result."""
    base, evidence = Path(base), Path(evidence)
    out = evidence / 'sealed'
    started = time.time()
    places = place_inputs(tree, base, job, home)
    large = large_inputs(base, places)
    record = verified_inputs(large)
    record_path = base / 'verified_inputs.json'
    write(record_path, dict(job_commit=job['commit'], files=record, seconds=round(time.time() - started, 3)))
    hashed_at = time.time()
    # The reuse bundle's archive verified ONCE (the one-pass verifier): every bundle's receipt is
    # that verification under its own manifest digest.
    reuse_receipt = verify_assets(Path(places['reuse']))
    seal_env = dict(env, **{VERIFIED_INPUTS_ENV: str(record_path), ATTESTATION_ENV: str(base / 'attestation.json')})
    # The attestation bound to this job (loop_budget_guard.attested_failures): the run root, the
    # manifest's and the job file's digests, and an expiry at the job's deadline.
    write(base / 'attestation.json', dict(job['attestation'], job_commit=job['commit'], bundle=str(base),
                                          job_manifest_sha256=sha(base / 'execution_manifest.json'),
                                          seal_job_sha256=sha(base / JOB_FILE), expires_epoch=deadline))
    rows = None
    try:
        rows = run_requests(job, places, tree, out, seal_env, deadline, run=seal_run)
    finally:
        if rows is None:
            # run_requests itself raised: no bundle carries an archive back, whatever it holds.
            for request in job['requests']:
                strip_returned(out / request['name'])
    for row in rows:
        bundle = out / row['name']
        if row['rc'] != 0 or not (bundle / 'seal.json').is_file():
            row['stripped'] = strip_returned(bundle)
            continue
        try:
            row['receipt'] = per_bundle_receipt(bundle, Path(places['reuse']), reuse_receipt)
            row['store'] = store_project(bundle, store)
            assets = json.loads((bundle / 'execution_manifest.json').read_text(encoding='utf-8'))['assets_archive']
            (bundle / assets['filename']).unlink()
            row['manifest_sha256'] = sha(bundle / 'execution_manifest.json')
            row['seal_sha256'] = sha(bundle / 'seal.json')
        except Exception as exc:
            row['post_error'] = ' '.join(str(exc).split())[:300]
            row['stripped'] = strip_returned(bundle)
    result = dict(arm='S', job_manifest_sha256=sha(base / 'execution_manifest.json'), requests=len(job['requests']), sealed=sum(1 for r in rows if r['rc'] == 0 and 'post_error' not in r),
                  rows=rows, hash_once_seconds=round(hashed_at - started, 3), seconds=round(time.time() - started, 3),
                  execution_integrity_passed=all(r['rc'] == 0 and 'post_error' not in r for r in rows))
    result['reasons'] = [] if result['execution_integrity_passed'] else ['seal_requests_failed']
    write(evidence / 'seal_job_result.json', result)
    return result


def per_bundle_receipt(bundle, reuse_bundle, reuse_receipt):
    """The asset verification receipt of a bundle that reuses the verified archive: the same archive
    digest, size, members and models as the bundle the archive was verified in, its own manifest
    digest (the receipt the bound wrapper reads)."""
    bundle, reuse_bundle = Path(bundle), Path(reuse_bundle)
    mine = json.loads((bundle / 'execution_manifest.json').read_text(encoding='utf-8'))
    theirs = json.loads((reuse_bundle / 'execution_manifest.json').read_text(encoding='utf-8'))
    keys = ('sha256', 'bytes', 'members')
    require({k: mine['assets_archive'][k] for k in keys} == {k: theirs['assets_archive'][k] for k in keys},
            'The bundle does not reuse the verified archive')
    mine_models = {m['model_id']: (m['revision'], m['cache_ref']) for m in mine['models']}
    theirs_models = {m['model_id']: (m['revision'], m['cache_ref']) for m in theirs['models']}
    require(mine_models == theirs_models, 'The bundle names other models than the verified archive')
    require(reuse_receipt.get('passed') is True and reuse_receipt.get('archive_sha256') == mine['assets_archive']['sha256'],
            'The verified archive receipt did not pass')
    receipt = dict(reuse_receipt, manifest_sha256=sha(bundle / 'execution_manifest.json'),
                   verified_in='seal job, once for the reused archive (route S)')
    write(bundle / 'asset_verification.json', receipt)
    return receipt
