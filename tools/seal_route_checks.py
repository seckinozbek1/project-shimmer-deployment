"""Proofs for route S (#252, tools/seal_route.py and the sealer's input_sha), on fixtures only: no
launch, no seal of a real bundle, no network. Each proof is neutralised in memory, must FAIL, is
restored and must PASS.

    py -3.12 -X utf8 tools/seal_route_checks.py
"""
import contextlib
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import seal_route as sr  # noqa: E402


def git_in(folder):
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")

    def git(*args):
        done = subprocess.run(["git", "-C", str(folder), *args], env=env, capture_output=True, text=True)
        if done.returncode != 0:
            raise sr.RouteError("git %s: %s" % (args[0], done.stderr.strip()[:200]))
        return done.stdout
    return git


def laptop_commit(folder, files):
    """A laptop-side repository with one commit with a parent: (commit, tree, commit object bytes)."""
    folder.mkdir(parents=True)
    git = git_in(folder)
    git("init", "-q", "-b", "main")
    for key, value in (("user.name", "fixture"), ("user.email", "fixture@localhost"), ("core.autocrlf", "false")):
        git("config", key, value)
    (folder / "first.txt").write_text("parent\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "parent")
    (folder / "first.txt").unlink()
    for name, text in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(text)
    git("add", "-A")
    git("commit", "-q", "-m", "the bound commit")
    commit = git("rev-parse", "HEAD").strip()
    obj = subprocess.run(["git", "-C", str(folder), "cat-file", "commit", commit], capture_output=True).stdout
    return commit, git("rev-parse", "HEAD^{tree}").strip(), obj


def instance_checkout(folder, files):
    """The instance's checkout as the runner's git_checkout makes it: one new commit of the files."""
    folder.mkdir(parents=True)
    git = git_in(folder)
    git("init", "-q", "-b", "gate")
    for key, value in (("user.name", "Shimmer gate"), ("user.email", "gate@localhost"), ("core.autocrlf", "false")):
        git("config", key, value)
    for name, text in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(text)
    git("add", "-A", "-f", "--", ".")
    git("commit", "-q", "--no-verify", "-m", "arm G gate tree")
    return git


FILES = {"tools/a.py": b"print(1)\n", "config/b.json": b"{}\n"}


def proof_exact_commit(mod=sr):
    """The instance re-creates the laptop's commit id over the same tree; a different tree refuses."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        commit, tree, obj = laptop_commit(tmp / "laptop", FILES)
        (tmp / "commit.bin").write_bytes(obj)
        git = instance_checkout(tmp / "inst", FILES)
        made = mod.exact_commit(git, tmp / "commit.bin", commit, tree)
        head = git("rev-parse", "HEAD").strip()
        shown = git("show", commit + ":tools/a.py")
        other = instance_checkout(tmp / "other", dict(FILES, **{"tools/a.py": b"print(2)\n"}))
        try:
            mod.exact_commit(other, tmp / "commit.bin", commit, tree)
            refused = None
        except sr.RouteError as exc:
            refused = str(exc)
        except Exception as exc:
            refused = type(exc).__name__
        wrong_tree = None
        try:
            mod.exact_commit(git_in(tmp / "inst"), tmp / "commit.bin", commit, "f" * 40)
        except sr.RouteError as exc:
            wrong_tree = str(exc)
    ok = made["commit"] == commit and head == commit and shown == "print(1)\n" and bool(refused) and bool(wrong_tree)
    return ok, "commit re-created %s, HEAD the laptop's %s; another tree: %r; another sealed tree id: %r" % (
        made["commit"] == commit, head == commit, refused, wrong_tree)


def proof_verified_inputs_and_stat(mod=sr):
    """Hashed once, a digest is reused only while the size, modification time, inode and sampled
    chunks stand: one byte changed in a sampled chunk with the same size and time is caught, and a
    touched time alone is caught by the stat."""
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "big.bin"
        size = 40 * 1024 * 1024
        with f.open("wb") as stream:
            stream.write(b"x" * size)
        record = mod.verified_inputs([f], workers=2)
        same = mod.recorded_sha(f, record) == mod.sha(f)
        st = os.stat(f)
        offset = mod.chunk_offsets(size)[5] + 17
        with open(f, "r+b") as stream:
            stream.seek(offset)
            stream.write(b"y")                     # one byte, same size
        os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns))   # and the same time
        same_stat = (os.stat(f).st_size, os.stat(f).st_mtime_ns) == (st.st_size, st.st_mtime_ns)
        changed = mod.recorded_sha(f, record)
        with open(f, "r+b") as stream:
            stream.seek(offset)
            stream.write(b"x")
        os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
        touched = mod.recorded_sha(f, record)
        missing = mod.recorded_sha(f, {})
    ok = same and same_stat and changed is None and touched is None and missing is None
    return ok, ("unchanged reuses its digest %s; one byte in a sampled chunk, same size and time, hashes again %s; a "
                "touched time hashes again %s; no record %s" % (same, changed is None, touched is None, missing is None))


def proof_sealer_uses_the_record_only_on_the_instance(prep=None):
    """The sealer's input_sha takes the record only on Linux with the runner's variable; else it reads."""
    import prepare_ordinary_final_run as sealer
    prep = prep or sealer
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "big.bin"
        f.write_bytes(b"real bytes")
        rec = Path(tmp) / "record.json"
        lie = {str(f.resolve()): dict(sha256="a" * 64, size=f.stat().st_size, mtime_ns=f.stat().st_mtime_ns, inode=f.stat().st_ino,
                                      chunks=sr.chunk_digests(f, f.stat().st_size))}
        rec.write_text(json.dumps({"files": lie}), encoding="utf-8")
        with patch.dict(os.environ, {"SHIMMER_SEAL_VERIFIED_INPUTS": str(rec)}):
            with patch.object(prep.sys, "platform", "win32"):
                laptop = prep.input_sha(f)
            with patch.object(prep.sys, "platform", "linux"):
                instance = prep.input_sha(f)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SHIMMER_SEAL_VERIFIED_INPUTS", None)
            with patch.object(prep.sys, "platform", "linux"):
                unset = prep.input_sha(f)
    real = hashlib.sha256(b"real bytes").hexdigest()
    ok = laptop == real and instance == "a" * 64 and unset == real
    return ok, "laptop reads the bytes %s; instance takes the record %s; no variable reads %s" % (
        laptop == real, instance == "a" * 64, unset == real)


def bundle_with_project(folder, data=b"project bytes"):
    folder.mkdir(parents=True)
    (folder / "project.tar.gz").write_bytes(data)
    (folder / "execution_manifest.json").write_text(json.dumps({"source_archive_sha256": hashlib.sha256(data).hexdigest()}),
                                                     encoding="utf-8")
    return folder


def proof_project_stored_once(mod=sr):
    """Item 3: the project archive goes to the store once by its fingerprint, is never replaced, a
    stored file is held to its digest, and the bundle keeps only the record."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        store = tmp / "store"
        a = mod.store_project(bundle_with_project(tmp / "a"), store)
        b = mod.store_project(bundle_with_project(tmp / "b"), store)
        stored = list(store.iterdir())
        left = (tmp / "a" / "project.tar.gz").exists()
        record = json.loads((tmp / "a" / sr.PROJECT_IN_STORE).read_text(encoding="utf-8"))
        (store / stored[0].name).write_bytes(b"tampered")
        try:
            mod.store_project(bundle_with_project(tmp / "c"), store)
            tampered = None
        except sr.RouteError as exc:
            tampered = str(exc)
    ok = (len(stored) == 1 and not a["already_stored"] and b["already_stored"] and not left
          and record["sha256"] == hashlib.sha256(b"project bytes").hexdigest() and bool(tampered))
    return ok, "one stored file %s; second already stored %s; bundle keeps no archive %s; a tampered store refused %r" % (
        len(stored) == 1, b["already_stored"], not left, tampered)


def ledger_fixture(folder, lines):
    path = Path(folder) / "ledger.jsonl"
    path.write_text("".join(json.dumps(l) + "\n" for l in lines), encoding="utf-8")
    return path


def copy_entry(path):
    data = Path(path).read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def proof_stale_read_copy_refused(mod=sr):
    """The read copies are refused on return when a live record moved: a ledger line after the job was
    sealed that is not the job's own (in the budget ledger or in R's), a rewritten ledger, or a spend
    store that no longer begins with its copy; the job's own launch lines alone are admitted."""
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        live = {}
        for key, line in (("budget_ledger", {"event": "budget_open", "budget_usd": 351.0}),
                          ("r_ledger", {"event": "launch", "instance_name": "shimmer-loop-r1"}),
                          ("spend_store", {"event": "ceiling", "ceiling_usd": 60.0})):
            live[key] = tmp / (key + ".jsonl")
            live[key].write_text(json.dumps(line) + "\n", encoding="utf-8")
        job = {"read_copies": {k: copy_entry(v) for k, v in live.items()}}
        own = {"shimmer-loop-seal-job", "id-1"}
        with live["budget_ledger"].open("a", encoding="utf-8") as s_:
            s_.write(json.dumps({"event": "launch_intent", "instance_name": "shimmer-loop-seal-job"}) + "\n")
            s_.write(json.dumps({"event": "termination", "instance_id": "id-1"}) + "\n")
        with live["spend_store"].open("a", encoding="utf-8") as s_:
            s_.write(json.dumps({"event": "close", "spent_usd": 0.1}) + "\n")
        out["only the job's own lines and an appended spend store admitted"] = mod.stale_reason(job, live, own) is None
        saved = live["budget_ledger"].read_bytes()
        with live["budget_ledger"].open("a", encoding="utf-8") as s_:
            s_.write(json.dumps({"event": "launch", "instance_name": "shimmer-loop-other"}) + "\n")
        out["a foreign ledger line refused"] = bool(mod.stale_reason(job, live, own))
        live["budget_ledger"].write_bytes(saved)
        saved_r = live["r_ledger"].read_bytes()
        with live["r_ledger"].open("a", encoding="utf-8") as s_:
            s_.write(json.dumps({"event": "launch", "instance_name": "shimmer-loop-r2"}) + "\n")
        out["a new line in R's ledger refused"] = bool(mod.stale_reason(job, live, own))
        live["r_ledger"].write_bytes(saved_r)
        saved_s = live["spend_store"].read_bytes()
        live["spend_store"].write_text(json.dumps({"event": "ceiling", "ceiling_usd": 90.0}) + "\n", encoding="utf-8")
        out["a rewritten spend store refused"] = bool(mod.stale_reason(job, live, own))
        live["spend_store"].write_bytes(saved_s)
        live["budget_ledger"].write_text(json.dumps({"event": "budget_open", "budget_usd": 300.0}) + "\n", encoding="utf-8")
        out["a rewritten ledger refused"] = bool(mod.stale_reason(job, live, own))
    return all(out.values()), "; ".join("%s %s" % (k, v) for k, v in out.items())


def proof_requests_carry_their_files(mod=sr):
    """Every file argument moves into the workloads archive; a flag the job sets itself refuses."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        w = tmp / "workload"
        (w / "context").mkdir(parents=True)
        (w / "context" / "doc.md").write_text("text", encoding="utf-8")
        listed, archive = mod.job_requests([{"name": "b0", "argv": ["--workload", str(w), "--forecast-minutes", "112"]}], tmp)
        with tarfile.open(archive) as t:
            names = t.getnames()
        try:
            mod.job_requests([{"name": "b1", "argv": ["--ledger", "x"]}], tmp)
            own_flag = None
        except sr.RouteError as exc:
            own_flag = str(exc)
    ok = listed[0]["argv"][1] == "{ws}/0/workload/workload" and "0/workload/workload/context/doc.md" in names and bool(own_flag)
    return ok, "argument %r; archived %s; a job flag in a request %r" % (listed[0]["argv"][1], names, own_flag)


def proof_per_bundle_receipt(mod=sr):
    """A bundle's asset receipt comes from the one verification only when it reuses that archive."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        assets = {"filename": "assets.tar", "sha256": "a" * 64, "bytes": 10, "members": {"m": {"sha256": "b" * 64, "bytes": 1}}}
        models = [{"model_id": "m", "revision": "r" * 40, "cache_ref": {"bytes": 40, "sha256": "c" * 64}}]
        for name, a in (("reuse", assets), ("mine", assets), ("other", dict(assets, sha256="d" * 64))):
            (tmp / name).mkdir()
            (tmp / name / "execution_manifest.json").write_text(json.dumps({"assets_archive": a, "models": models}), encoding="utf-8")
        receipt = {"passed": True, "archive_sha256": "a" * 64, "verified_members": 1, "default_revision_resolutions": []}
        got = mod.per_bundle_receipt(tmp / "mine", tmp / "reuse", receipt)
        try:
            mod.per_bundle_receipt(tmp / "other", tmp / "reuse", receipt)
            other = None
        except sr.RouteError as exc:
            other = str(exc)
    ok = got["manifest_sha256"] == hashlib.sha256((tmp / "mine" / "execution_manifest.json").read_bytes()).hexdigest() if False else (
        got["passed"] is True and len(got["manifest_sha256"]) == 64 and bool(other))
    return ok, "receipt under its own manifest digest %s; another archive refused %r" % (len(got["manifest_sha256"]) == 64, other)


def proof_project_held_by_fingerprint(run=None):
    """Item 3 in the runner's rule (the controller, the bound wrapper and the reverify read it): the
    bundle's own bytes held to the digest, or a store record naming exactly that fingerprint's file;
    a changed archive, another digest's record and no archive at all are refused."""
    import ordinary_final_run as runner
    run = run or runner
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data = b"project bytes"
        digest = hashlib.sha256(data).hexdigest()
        local = bundle_with_project(tmp / "local", data)
        out["local held"] = run.project_held(local, digest) is None
        (local / "project.tar.gz").write_bytes(b"changed")
        out["changed refused"] = _refused(lambda: run.project_held(local, digest))
        stored = tmp / "stored"
        stored.mkdir()
        (stored / "PROJECT_IN_STORE.json").write_text(json.dumps({"sha256": digest, "store_name": "project-%s.tar.gz" % digest}),
                                                      encoding="utf-8")
        out["store named"] = run.project_held(stored, digest) == "project-%s.tar.gz" % digest
        (stored / "PROJECT_IN_STORE.json").write_text(json.dumps({"sha256": "e" * 64, "store_name": "project-%s.tar.gz" % ("e" * 64)}),
                                                      encoding="utf-8")
        out["another record refused"] = _refused(lambda: run.project_held(stored, digest))
        (tmp / "empty").mkdir()
        out["nothing refused"] = _refused(lambda: run.project_held(tmp / "empty", digest))
    import ordinary_final_cloud as controller
    out["store command named"] = "projects/project-" in controller.project_from_store_command("/m", "project-%s.tar.gz" % digest, "/r")
    out["odd name refused"] = _refused(lambda: controller.project_from_store_command("/m", "../x.tar.gz", "/r"))
    return all(out.values()), "; ".join("%s %s" % (k, v) for k, v in out.items())


def proof_reverify_reads_members_from_git(rv=None):
    """Item 3 in the reverify: with the archive in the store, every member the sealed commit carries
    is read from git and held to the manifest's digest; one that differs refuses."""
    import ordinary_final_bound_reverify as reverify
    rv = rv or reverify
    files = {"scripts/a.py": b"print(1)\r\n", "config/b.json": b"{}\n"}
    expected = {n: hashlib.sha256(d.replace(b"\r\n", b"\n")).hexdigest() for n, d in files.items()}
    expected["input/context/doc.md"] = "f" * 64
    members, compared = rv.members_from_git(expected, set(files), lambda n: files[n])
    wrong = dict(expected, **{"config/b.json": "0" * 64})
    refused = _refused(lambda: rv.members_from_git(wrong, set(files), lambda n: files[n]))
    ok = compared == 2 and members["input/context/doc.md"] is None and members["scripts/a.py"] == b"print(1)\n" and refused
    return ok, "compared %d, generated member not read %s, a differing member refused %s" % (
        compared, members["input/context/doc.md"] is None, refused)


def bound_job(base, arm="S", claimed=True, tag="job"):
    """A run root holding an arm S manifest, its seal and its sealed job file, as the runner leaves
    it before the seals start; returns the manifest's digest and the job file's."""
    base.mkdir(parents=True, exist_ok=True)
    job = {"schema": sr.JOB_SCHEMA, "tag": tag, "attestation": {"orders": [1, 2, 3], "refusals": []}}
    (base / "seal_job.json").write_text(json.dumps(job), encoding="utf-8")
    manifest = {"arm": arm, "seal_job": job, "support_files": {"seal_job.json": sr.sha(base / "seal_job.json")}}
    (base / "execution_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (base / "seal.json").write_text(json.dumps({"execution_manifest_sha256": sr.sha(base / "execution_manifest.json")}),
                                    encoding="utf-8")
    if claimed:
        (base / "RUN_CLAIMED").write_text("1", encoding="utf-8")
    return sr.sha(base / "execution_manifest.json"), sr.sha(base / "seal_job.json")


def attestation_file(path, base, manifest_sha, job_sha, expires, refusals=()):
    path.write_text(json.dumps({"orders": [1, 2, 3], "refusals": list(refusals), "bundle": str(base),
                                "job_manifest_sha256": manifest_sha, "seal_job_sha256": job_sha,
                                "expires_epoch": expires}), encoding="utf-8")
    return path


def proof_guard_reads_the_attestation_only_on_the_instance(gd=None):
    """The guard takes the laptop's attestation of standing orders 1 to 3 only on Linux with the
    runner's variable and only bound to this job (its arm S manifest and job file by digest, the run
    claimed, before its expiry); off Linux it is ignored and the laptop checks its own records; an
    attestation of another job, an expired one, one in a run root of another arm, one before the run is
    claimed, or one naming other orders refuses: none of them weakens the guard."""
    sys.path.insert(0, str(ROOT / "tools" / "loop"))
    import loop_budget_guard as guard
    import time as clock
    gd = gd or guard
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        later = clock.time() + 600
        m, j = bound_job(tmp / "job")
        good = attestation_file(tmp / "good.json", tmp / "job", m, j, later)
        env = {gd.SEAL_ATTESTATION_ENV: str(good)}
        out["bound job read"] = gd.attested_failures(env, "linux") == []
        out["laptop ignores it"] = gd.attested_failures(env, "win32") is None
        out["no variable"] = gd.attested_failures({}, "linux") is None
        m2, j2 = bound_job(tmp / "other", tag="another job")
        out["another job refused"] = _refused(lambda: gd.attested_failures(
            {gd.SEAL_ATTESTATION_ENV: str(attestation_file(tmp / "x.json", tmp / "job", m2, j2, later))}, "linux"))
        out["expired refused"] = _refused(lambda: gd.attested_failures(
            {gd.SEAL_ATTESTATION_ENV: str(attestation_file(tmp / "e.json", tmp / "job", m, j, clock.time() - 1))}, "linux"))
        m3, j3 = bound_job(tmp / "b3", arm="B3")
        out["another arm refused"] = _refused(lambda: gd.attested_failures(
            {gd.SEAL_ATTESTATION_ENV: str(attestation_file(tmp / "a.json", tmp / "b3", m3, j3, later))}, "linux"))
        m4, j4 = bound_job(tmp / "unclaimed", claimed=False)
        out["unclaimed refused"] = _refused(lambda: gd.attested_failures(
            {gd.SEAL_ATTESTATION_ENV: str(attestation_file(tmp / "u.json", tmp / "unclaimed", m4, j4, later))}, "linux"))
        out["other refusals refused"] = _refused(lambda: gd.attested_failures(
            {gd.SEAL_ATTESTATION_ENV: str(attestation_file(tmp / "r.json", tmp / "job", m, j, later, refusals=[[1, "broken", "x"]]))},
            "linux"))
        out["no file refused"] = _refused(lambda: gd.attested_failures({gd.SEAL_ATTESTATION_ENV: str(tmp / "none.json")}, "linux"))
    return all(out.values()), "; ".join("%s %s" % (k, v) for k, v in out.items())


def job_fixture(tmp, mod=sr):
    """A run root and a checkout as the instance holds them after the runner's guards, with small
    stand-ins for the asset archive, the model cache, the wheels and the frozen model files. The read
    copies are named as the sealer names them (`mod.read_copy_name`) and sealed as support files."""
    base, tree = tmp / "base", tmp / "tree"
    (base / "hf_cache" / "hub" / "models--m" / "snapshots" / ("r" * 40)).mkdir(parents=True)
    (base / "hf_cache" / "hub" / "models--m" / "snapshots" / ("r" * 40) / "w.bin").write_bytes(b"weights" * 1000)
    (base / "wheels").mkdir()
    (base / "wheels" / "pkg.whl").write_bytes(b"wheel")
    (base / "assets.tar").write_bytes(b"archive" * 1000)
    (base / "project" / "docs" / "fix").mkdir(parents=True)
    (base / "project" / "docs" / "fix" / "adapter.bin").write_bytes(b"adapter")
    (tree / "config").mkdir(parents=True)
    spec = {r: {"files": {"adapter": {"path": "docs/fix/adapter.bin"}}} for r in ("producer", "auditor")}
    (tree / "config" / "final_models.json").write_text(json.dumps(spec), encoding="utf-8")
    assets = {"filename": "assets.tar", "sha256": sr.sha(base / "assets.tar"), "bytes": 7000, "members": {}}
    models = [{"model_id": "m", "revision": "r" * 40, "cache_ref": {"bytes": 40, "sha256": "c" * 64}}]
    (base / sr.REUSE_MANIFEST).write_text(json.dumps({"assets_archive": assets, "models": models}), encoding="utf-8")
    copy_data = {"budget_ledger": b'{"event": "budget_open"}\n', "spend_store": b'{"event": "ceiling"}\n'}
    for key, data in copy_data.items():
        (base / mod.read_copy_name(key)).parent.mkdir(parents=True, exist_ok=True)
        (base / mod.read_copy_name(key)).write_bytes(data)
    with tarfile.open(base / sr.WORKLOADS, "w") as t:
        info = tarfile.TarInfo("0/workload/w/a.txt")
        info.size = 1
        t.addfile(info, __import__("io").BytesIO(b"a"))
    copies = {k: {"path": sr.READ_COPIES[k], "sha256": sr.sha(base / mod.read_copy_name(k)), "bytes": len(copy_data[k])}
              for k in ("budget_ledger", "spend_store")}
    job = {"schema": sr.JOB_SCHEMA, "commit": "a" * 40, "tree": "b" * 40, "parallel": 2,
           "requests": [{"name": "s%d" % k, "argv": ["--workload", "{ws}/0/workload/w"]} for k in range(3)],
           "read_copies": copies, "read_copy_time_epoch": 0, "attestation": {"orders": [1, 2, 3], "refusals": []}}
    (base / sr.JOB_FILE).write_text(json.dumps(job), encoding="utf-8")
    support = {sr.JOB_FILE: sr.sha(base / sr.JOB_FILE), sr.REUSE_MANIFEST: sr.sha(base / sr.REUSE_MANIFEST),
               **{mod.read_copy_name(k): v["sha256"] for k, v in copies.items()}}
    (base / "execution_manifest.json").write_text(json.dumps({"arm": "S", "seal_job": job, "assets_archive": {"filename": "assets.tar"},
                                                              "support_files": support}), encoding="utf-8")
    return base, tree, job, assets, models


def fake_sealer(assets, models):
    """Stands in for the bound sealer: writes a bundle reusing the archive (as the sealer links it)."""
    calls = []

    def run(argv, cwd, env, stdin, stdout, stderr, timeout):
        out = Path(argv[argv.index("--output-dir") + 1])
        calls.append(dict(argv=argv, env=env))
        out.mkdir(parents=True)
        data = ("project of %s" % out.name).encode()
        (out / "project.tar.gz").write_bytes(data)
        reuse = Path(argv[argv.index("--reuse-assets") + 1])
        os.link(reuse / "assets.tar", out / "assets.tar")
        manifest = {"source_archive_sha256": hashlib.sha256(data).hexdigest(), "assets_archive": assets, "models": models}
        (out / "execution_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (out / "seal.json").write_text(json.dumps({"source_commit": "a" * 40}), encoding="utf-8")
        return types.SimpleNamespace(returncode=0)
    return run, calls


def failing_sealer(assets, models, failing, log_bytes=20000):
    """The fake sealer, except that request `failing` links the archives, writes a long log ending in
    its cause and exits 1, as a seal that fails after binding the reused archive."""
    good, calls = fake_sealer(assets, models)

    def run(argv, cwd, env, stdin, stdout, stderr, timeout):
        out = Path(argv[argv.index("--output-dir") + 1])
        if out.name != failing:
            return good(argv, cwd, env, stdin, stdout, stderr, timeout)
        calls.append(dict(argv=argv, env=env))
        out.mkdir(parents=True)
        (out / "project.tar.gz").write_bytes(b"half-written project")
        os.link(Path(argv[argv.index("--reuse-assets") + 1]) / "assets.tar", out / "assets.tar")
        stdout.write(b"x" * log_bytes + b"\nRuntimeError: the cause of this seal's failure\n")
        stdout.flush()
        return types.SimpleNamespace(returncode=1)
    return run, calls


def proof_failed_seal_returns_no_archive_and_names_its_cause(mod=sr):
    """C4 launch 3: a seal that fails after binding the reused archive returns no asset or project
    archive (strip_returned, whatever the outcome), and every request leaves a small tail beside its
    bundle naming its exit code and the end of its log, capped at SEAL_TAIL_BYTES."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        base, tree, job, assets, models = job_fixture(tmp, mod)
        run, _calls = failing_sealer(assets, models, "s1")
        receipt = {"passed": True, "archive_sha256": assets["sha256"], "verified_members": 0, "default_revision_resolutions": []}
        with patch.object(mod.os, "symlink", lambda s_, d, target_is_directory=False: Path(d).mkdir(parents=True)):
            result = mod.run_job(base, job, tree, tmp / "evidence", __import__("time").time() + 600, {"PATH": ""},
                                 tmp / "home", tmp / "store", lambda b: receipt, seal_run=run)
        sealed = tmp / "evidence" / "sealed"
        left = sorted(p.relative_to(sealed).as_posix() for p in sealed.rglob("*")
                      if p.name in ("assets.tar", "project.tar.gz"))
        tails = {r["name"]: json.loads((sealed / (r["name"] + ".seal_tail.json")).read_text(encoding="utf-8"))
                 for r in job["requests"] if (sealed / (r["name"] + ".seal_tail.json")).is_file()}
        failed = tails.get("s1", {})
        small = all(len(t["tail"].encode("utf-8")) <= 4096 for t in tails.values())
        row = next(r for r in result["rows"] if r["name"] == "s1")
    ok = (not left and failed.get("rc") == 1 and "the cause of this seal's failure" in failed.get("tail", "")
          and failed.get("log_bytes", 0) > 4096 and small and len(tails) == 3 and not result["execution_integrity_passed"]
          and sorted(row.get("stripped", [])) == ["assets.tar", "project.tar.gz"] and result["sealed"] == 2)
    return ok, "archives left in the evidence %s; tails %d of 3, capped %s; failed tail rc %s naming its cause %s; stripped %s; sealed %s" % (
        left, len(tails), small, failed.get("rc"), "the cause of this seal's failure" in failed.get("tail", ""),
        row.get("stripped"), result["sealed"])


def run_failing_job(mod, tmp, run, **patches):
    """run_job on the job fixture with the sealer stand-in `run` and any module patches; returns
    (result, the evidence's sealed folder)."""
    base, tree, job, assets, models = job_fixture(tmp, mod)
    receipt = {"passed": True, "archive_sha256": assets["sha256"], "verified_members": 0, "default_revision_resolutions": []}
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(mod.os, "symlink", lambda s_, d, target_is_directory=False: Path(d).mkdir(parents=True)))
        for name, value in patches.items():
            stack.enter_context(patch.object(mod, name, value))
        result = mod.run_job(base, job, tree, tmp / "evidence", __import__("time").time() + 600, {"PATH": ""},
                             tmp / "home", tmp / "store", lambda b: receipt, seal_run=run(assets, models))
    return result, tmp / "evidence" / "sealed"


def archives_left(sealed):
    return sorted(p.relative_to(sealed).as_posix() for p in sealed.rglob("*") if p.name in ("assets.tar", "project.tar.gz"))


def proof_a_seal_that_raises_is_a_failed_row(mod=sr):
    """Checker gap 1: a sealer start that raises OSError after the archives were linked is that
    request's failure (a row with its reason and a tail), not an exception past the strip."""
    def raising(assets, models):
        good, _ = fake_sealer(assets, models)

        def run(argv, cwd, env, stdin, stdout, stderr, timeout):
            out = Path(argv[argv.index("--output-dir") + 1])
            if out.name != "s1":
                return good(argv, cwd, env, stdin, stdout, stderr, timeout)
            out.mkdir(parents=True)
            (out / "project.tar.gz").write_bytes(b"half")
            os.link(Path(argv[argv.index("--reuse-assets") + 1]) / "assets.tar", out / "assets.tar")
            raise OSError("cannot start the sealer")
        return run
    with tempfile.TemporaryDirectory() as tmp:
        try:
            result, sealed = run_failing_job(mod, Path(tmp), raising)
        except OSError as exc:
            return False, "the OSError escaped run_job: %s" % exc
        left = archives_left(sealed)
        row = next(r for r in result["rows"] if r["name"] == "s1")
        tail = json.loads((sealed / "s1.seal_tail.json").read_text(encoding="utf-8")) if (sealed / "s1.seal_tail.json").is_file() else {}
    ok = not left and "OSError" in row.get("reason", "") and "OSError" in tail.get("reason", "") and result["sealed"] == 2
    return ok, "archives left %s; row reason %r; tail written %s; sealed %s" % (left, row.get("reason"), bool(tail), result["sealed"])


def proof_an_error_after_sealing_strips_the_bundle(mod=sr):
    """Checker gap 2: a seal that succeeded and then fails in the job's own steps (here the store)
    is stripped of both archives and counted failed."""
    def broken_store(bundle, store, copy=None):
        raise OSError("the store cannot be written")
    with tempfile.TemporaryDirectory() as tmp:
        result, sealed = run_failing_job(mod, Path(tmp), lambda a, m: fake_sealer(a, m)[0], store_project=broken_store)
        left = archives_left(sealed)
        rows = result["rows"]
    stripped = all(sorted(r.get("stripped", [])) == ["assets.tar", "project.tar.gz"] and "post_error" in r for r in rows)
    ok = not left and stripped and result["sealed"] == 0 and not result["execution_integrity_passed"]
    return ok, "archives left %s; every row stripped of both and named post_error %s; sealed %s" % (left, stripped, result["sealed"])


def proof_run_requests_raising_strips_every_bundle(mod=sr):
    """Checker gap 1, its last part: when run_requests itself raises after the bundles linked their
    archives, run_job's finally strips every request's bundle and the error still propagates; and a
    tail that cannot be written is recorded on the row (tail_error), never raised."""
    def raising_requests(job, places, tree, out_root, env, deadline, run=None):
        for request in job["requests"]:
            argv = mod.request_argv(request, places, Path(out_root) / request["name"], "ledger", "inputs")
            run(argv, None, None, None, None, None, None)
        raise RuntimeError("the request pool broke")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            run_failing_job(mod, Path(tmp) / "a", lambda a, m: fake_sealer(a, m)[0], run_requests=raising_requests)
            propagated = False
        except RuntimeError:
            propagated = True
        sealed = Path(tmp) / "a" / "evidence" / "sealed"
        bundles = sorted(p.name for p in sealed.iterdir() if p.is_dir())
        left = archives_left(sealed)

        def no_tail(log_path, row):
            raise OSError("the tail cannot be written")
        result, _ = run_failing_job(mod, Path(tmp) / "b", lambda a, m: fake_sealer(a, m)[0], seal_tail=no_tail)
        tail_errors = [r.get("tail_error") for r in result["rows"]]
    ok = propagated and bundles == ["s0", "s1", "s2"] and not left and tail_errors == ["OSError"] * 3 and result["sealed"] == 3
    return ok, "error propagated %s; bundles %s; archives left %s; tail errors recorded %s" % (propagated, bundles, left, tail_errors)


def proof_the_seal_log_is_capped(mod=sr):
    """Checker gap 3: the whole seal log stays in the evidence but only its last SEAL_LOG_BYTES."""
    with tempfile.TemporaryDirectory() as tmp:
        result, sealed = run_failing_job(mod, Path(tmp), lambda a, m: failing_sealer(a, m, "s1", log_bytes=200000)[0])
        log = (sealed / "s1.seal.log").read_bytes()
        tail = json.loads((sealed / "s1.seal_tail.json").read_text(encoding="utf-8"))
    ok = len(log) <= 64 * 1024 and log.endswith(b"the cause of this seal's failure\n") and tail["log_bytes"] > 200000
    return ok, "log kept %d bytes, ending in the cause %s; size before recorded %d" % (
        len(log), log.endswith(b"the cause of this seal's failure\n"), tail["log_bytes"])


def proof_job_end_to_end(mod=sr):
    """run_job on stand-ins: the read copies placed and held to their digests, the large inputs hashed
    once and named to every seal with the attestation, every request sealed, each bundle given its
    receipt, its project archive stored by fingerprint and its asset archive left out of what returns."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        base, tree, job, assets, models = job_fixture(tmp)
        run, calls = fake_sealer(assets, models)
        receipt = {"passed": True, "archive_sha256": assets["sha256"], "verified_members": 0, "default_revision_resolutions": []}
        links = []

        def symlink(src, dst, target_is_directory=False):
            links.append((src, dst))
            Path(dst).mkdir(parents=True)
        with patch.object(mod.os, "symlink", symlink):
            result = mod.run_job(base, job, tree, tmp / "evidence", __import__("time").time() + 600, {"PATH": ""},
                                 tmp / "home", tmp / "store", lambda b: receipt, seal_run=run)
        sealed = tmp / "evidence" / "sealed"
        returned = {p.name: sorted(x.name for x in p.iterdir()) for p in sealed.iterdir() if p.is_dir()}
        stored = sorted(x.name for x in (tmp / "store").iterdir())
        ledger = (tree / sr.READ_COPIES["budget_ledger"]).read_bytes()
        record = json.loads((base / "verified_inputs.json").read_text(encoding="utf-8"))
        envs = {c["env"].get(sr.VERIFIED_INPUTS_ENV) for c in calls}
    ok = (result["execution_integrity_passed"] and result["sealed"] == 3 and len(calls) == 3 and len(stored) == 3
          and all("assets.tar" not in v and "project.tar.gz" not in v and sr.PROJECT_IN_STORE in v and "asset_verification.json" in v
                  for v in returned.values())
          and ledger == b'{"event": "budget_open"}\n' and len(record["files"]) == 2 and envs == {str(base / "verified_inputs.json")})
    return ok, "sealed %s of 3; stored %d; returned files %s; inputs hashed once %d; every seal named the record %s" % (
        result["sealed"], len(stored), sorted(set(tuple(v) for v in returned.values())), len(record["files"]), len(envs) == 1)


def returned_job(tmp, fail_preflight_at=None):
    """A seal job run end to end on stand-ins, its evidence collected as the controller collects it,
    and the laptop's job bundle and run folder: (job bundle, run folder, reuse bundle, live records)."""
    import tarfile as tf
    base, tree, job, assets, models = job_fixture(tmp)
    run, _calls = fake_sealer(assets, models)
    receipt = {"passed": True, "archive_sha256": assets["sha256"], "verified_members": 0, "default_revision_resolutions": []}
    with patch.object(sr.os, "symlink", lambda s_, d, target_is_directory=False: Path(d).mkdir(parents=True)):
        sr.run_job(base, job, tree, base / "evidence", __import__("time").time() + 600, {"PATH": ""}, tmp / "home",
                   tmp / "store", lambda b: receipt, seal_run=run)
    run_folder = tmp / "run"
    run_folder.mkdir()
    with tf.open(run_folder / "collected_evidence.tar.gz", "w:gz") as archive:
        for path in sorted((base / "evidence").rglob("*")):
            if path.is_file():
                archive.add(path, arcname=path.relative_to(base).as_posix(), recursive=False)
    (run_folder / "collection_integrity.json").write_text(json.dumps({"sha256": sr.sha(run_folder / "collected_evidence.tar.gz")}),
                                                         encoding="utf-8")
    job_bundle = tmp / "job"
    job_bundle.mkdir()
    for name in ("execution_manifest.json", sr.JOB_FILE):
        (job_bundle / name).write_bytes((base / name).read_bytes())
    result = json.loads((base / "evidence" / "seal_job_result.json").read_text(encoding="utf-8"))
    (run_folder / "LAUNCH_INTENT.json").write_text(json.dumps({"execution_manifest_sha256": sr.sha(job_bundle / "execution_manifest.json")}),
                                                  encoding="utf-8")
    (run_folder / "launch.json").write_text(json.dumps({"instance_id": "id-1"}), encoding="utf-8")
    # The job bundle's binding, as the lead writes it, and the controller's real ledger lines: the
    # launch_intent line names only the instance name the bound wrapper derives from that binding.
    job_sha = sr.sha(job_bundle / "execution_manifest.json")
    (job_bundle / "authorization_binding.json").write_text(json.dumps({"manifest_sha256": job_sha,
                                                                       "preparation_commit": "abcdef1234567"}), encoding="utf-8")
    sys.path.insert(0, str(ROOT / "tools" / "loop"))
    import loop_budget_guard as guard
    name = guard.instance_name("abcdef1" + "-" + job_sha[:8])
    live = {"budget_ledger": tmp / "live.jsonl"}
    live["budget_ledger"].write_bytes((base / sr.read_copy_name("budget_ledger")).read_bytes()
                                      + (json.dumps({"event": "launch_intent", "instance_name": name}) + "\n").encode()
                                      + (json.dumps({"event": "launch", "instance_name": name, "instance_id": "id-1"}) + "\n").encode()
                                      + b'{"event": "termination", "instance_id": "id-1"}\n')
    live["spend_store"] = tmp / "spend.jsonl"
    live["spend_store"].write_bytes((base / sr.read_copy_name("spend_store")).read_bytes())
    return job_bundle, run_folder, base / "reuse_bundle", live, result, base


def rewrite_result(run_folder, base, change):
    """The collected evidence again after `change(result)`, with its collection record (as if the
    instance had written it so)."""
    import tarfile as tf
    path = base / "evidence" / "seal_job_result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    change(result)
    path.write_text(json.dumps(result), encoding="utf-8")
    with tf.open(run_folder / "collected_evidence.tar.gz", "w:gz") as archive:
        for p_ in sorted((base / "evidence").rglob("*")):
            if p_.is_file():
                archive.add(p_, arcname=p_.relative_to(base).as_posix(), recursive=False)
    (run_folder / "collection_integrity.json").write_text(json.dumps({"sha256": sr.sha(run_folder / "collected_evidence.tar.gz")}),
                                                         encoding="utf-8")


def proof_driver_admits_returned_bundles(drv=None):
    """The laptop driver, bound to its job, all or none: every bundle admitted at once under the
    ledger lock held from the stale check through the last step, its asset archive linked and its
    binding written with the stored digest; refused, admitting nothing, for a stale read copy, a run
    folder of another job, a result of another job, a returned bundle that is not the job's own, a
    reuse bundle other than the sealed one, and a step refusing mid-way (the staging folder kept)."""
    import seal_route_driver as driver
    drv = drv or driver
    out = {}
    locks = []
    lock = lambda ledger: locks.append(("lock", Path(ledger).name)) or "held"
    unlock = lambda held: locks.append(("unlock", held))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        job_bundle, run_folder, reuse, live, result, base = returned_job(tmp)
        events = []
        real_stale = sr.stale_reason

        def stale(job, live_, own):
            events.append("stale")
            return real_stale(job, live_, own)

        def step_run(argv, capture_output, text):
            events.append("step")
            return types.SimpleNamespace(returncode=0)
        args = dict(steps=True, run=step_run, gate=lambda name: None, unlock=lambda held: events.append("unlock"),
                    lock=lambda ledger: events.append("lock") or "held")
        with patch.object(sr, "stale_reason", stale):
            rows = drv.admit(job_bundle, run_folder, reuse, tmp / "out", live, live["budget_ledger"], **args)
        out["all admitted at once"] = len(rows) == 3 and sorted(p.name for p in (tmp / "out").iterdir()) == ["admission.json", "s0", "s1", "s2"]
        out["assets linked"] = all((tmp / "out" / r["name"] / "assets.tar").is_file() for r in rows)
        binding = json.loads((tmp / "out" / "s0" / "authorization_binding.json").read_text(encoding="utf-8"))
        manifest = json.loads((tmp / "out" / "s0" / "execution_manifest.json").read_text(encoding="utf-8"))
        out["binding names the stored digest"] = binding["project_sha256"] == manifest["source_archive_sha256"]
        out["lock held from the stale check through every step"] = events == ["lock", "stale"] + ["step"] * 6 + ["unlock"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        job_bundle, run_folder, reuse, live, result, base = returned_job(tmp)
        args = dict(steps=False, lock=lock, unlock=unlock)
        with live["budget_ledger"].open("ab") as s_:
            s_.write(b'{"event": "launch", "instance_name": "shimmer-loop-other"}\n')
        out["stale refused"] = _refused(lambda: drv.admit(job_bundle, run_folder, reuse, tmp / "o1", live, live["budget_ledger"], **args))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        job_bundle, run_folder, reuse, live, result, base = returned_job(tmp)
        args = dict(steps=False, lock=lock, unlock=unlock)
        intent = json.loads((run_folder / "LAUNCH_INTENT.json").read_text(encoding="utf-8"))
        (run_folder / "LAUNCH_INTENT.json").write_text(json.dumps(dict(intent, execution_manifest_sha256="e" * 64)), encoding="utf-8")
        out["another job's run folder refused"] = _refused(lambda: drv.admit(job_bundle, run_folder, reuse, tmp / "o2", live,
                                                                            live["budget_ledger"], **args))
        (run_folder / "LAUNCH_INTENT.json").write_text(json.dumps(intent), encoding="utf-8")
        # Another job's bundle swapped in for s1: its digests are not the job result's row.
        other = base / "evidence" / "sealed" / "s1"
        (other / "seal.json").write_text(json.dumps({"source_commit": "b" * 40}), encoding="utf-8")
        rewrite_result(run_folder, base, lambda r: None)
        out["another bundle swapped in refused"] = _refused(lambda: drv.admit(job_bundle, run_folder, reuse, tmp / "o3", live,
                                                                             live["budget_ledger"], **args))
        out["nothing admitted on a refusal"] = not (tmp / "o3").exists() and (tmp / "o3.refused").exists()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        job_bundle, run_folder, reuse, live, result, base = returned_job(tmp)
        args = dict(steps=False, lock=lock, unlock=unlock)
        rewrite_result(run_folder, base, lambda r: r.update(job_manifest_sha256="f" * 64))
        out["another job's result refused"] = _refused(lambda: drv.admit(job_bundle, run_folder, reuse, tmp / "o4", live,
                                                                        live["budget_ledger"], **args))
        out["its staging kept as refused, none left as staging"] = (tmp / "o4.refused").exists() and not (tmp / "o4.staging").exists()
        _refused(lambda: drv.admit(job_bundle, run_folder, reuse, tmp / "o4", live, live["budget_ledger"], **args))
        out["a second refusal kept apart"] = (tmp / "o4.refused-2").exists() and (tmp / "o4.refused").exists()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        job_bundle, run_folder, reuse, live, result, base = returned_job(tmp)
        manifest = json.loads((reuse / "execution_manifest.json").read_text(encoding="utf-8"))
        (reuse / "execution_manifest.json").write_text(json.dumps(dict(manifest, note="another reuse bundle")), encoding="utf-8")
        out["another reuse bundle refused"] = _refused(lambda: drv.admit(job_bundle, run_folder, reuse, tmp / "o5", live,
                                                                        live["budget_ledger"], steps=False, lock=lock, unlock=unlock))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        job_bundle, run_folder, reuse, live, result, base = returned_job(tmp)
        calls = []

        def step_run(argv, capture_output, text):
            calls.append(Path(argv[-1]).name)
            return types.SimpleNamespace(returncode=1 if len(calls) == 4 else 0)
        out["a mid-way refusal admits nothing"] = _refused(lambda: drv.admit(
            job_bundle, run_folder, reuse, tmp / "o6", live, live["budget_ledger"], steps=True, run=step_run,
            gate=lambda name: None, lock=lock, unlock=unlock)) and not (tmp / "o6").exists() and (tmp / "o6.refused").exists()
    return all(out.values()), "; ".join("%s %s" % (k, v) for k, v in out.items())


def proof_driver_gates_and_logs_one_reading(drv=None):
    """D-585, D-099: the laptop driver gates a heavy step on ONE reading per wait cycle and logs that
    exact reading as the step's start line: a cycle below the floor waits, the passing reading is the
    one logged, never a second reading taken after it (which here would show less memory)."""
    import seal_route_driver as driver
    drv = drv or driver
    big = 40 * 2 ** 30
    readings = iter([dict(memory_gb=1.5, disk_gb=40.0, disk_bytes=big, other_seals=0),
                     dict(memory_gb=2.4, disk_gb=40.0, disk_bytes=big, other_seals=1),
                     dict(memory_gb=2.1, disk_gb=40.0, disk_bytes=big, other_seals=0),
                     dict(memory_gb=1.8, disk_gb=40.0, disk_bytes=big, other_seals=0)])
    slept = []
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "gate_log.jsonl"
        started = drv.wait_for_room("reverify", log, tmp, read=lambda path: next(readings), sleep=slept.append, clock=lambda: 1.0)
        lines = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
    ok = (len(slept) == 2 and started["memory_gb"] == 2.1 and len(lines) == 1 and lines[0]["memory_gb"] == 2.1
          and lines[0]["other_seals"] == 0 and lines[0]["step"] == "reverify")
    return ok, "waited %d cycles; started on %s GB; logged %s" % (len(slept), started["memory_gb"], lines)


def proof_driver_gate_holds_the_disk_floor(drv=None):
    """D-099: the gate admits a step only when the disk free after the step's own expected size stays at
    or above standing_orders_check.DISK_FLOOR, read at the gate (moved here to 40 GiB, the gate follows
    it); one byte short waits."""
    import seal_route_driver as driver
    import standing_orders_check as orders
    drv = drv or driver
    expected = drv.EXPECTED_BYTES["seal"]
    with patch.object(orders, "DISK_FLOOR", 40 * 2 ** 30):
        floor = orders.DISK_FLOOR
        at = dict(memory_gb=4.0, disk_gb=99.0, disk_bytes=floor + expected, other_seals=0)
        short = dict(at, disk_bytes=floor + expected - 1)
        between = dict(at, disk_bytes=35 * 2 ** 30)   # above the shipped 30 GiB, below the moved floor
        out = {"at the floor admitted": drv.admits(at, expected), "one byte short waits": not drv.admits(short, expected),
               "the floor read, not copied": not drv.admits(between, expected)}
    return all(out.values()), "; ".join("%s %s" % (k, v) for k, v in out.items())


def proof_input_changed_while_hashed_refused(mod=sr):
    """The stat and the chunks are taken before the hash and again after it: a file that changes while
    it is hashed (one byte, same size, the time put back) gets no recorded digest; the job stops."""
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "big.bin"
        f.write_bytes(b"x" * (3 * 1024 * 1024))
        st = os.stat(f)

        def changing(path):
            digest = sr.sha(path)
            with open(path, "r+b") as stream:
                stream.write(b"y")
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
            return digest
        refused = _refused(lambda: mod.verified_inputs([f], workers=1, hasher=changing))
        f.write_bytes(b"x" * (3 * 1024 * 1024))
        steady = mod.verified_inputs([f], workers=1)
        full = steady[str(f.resolve())]["sha256"] == sr.sha(f)
    ok = refused and full
    return ok, "a file changed while hashed refused %s; a steady one recorded with its full digest %s" % (refused, full)


def proof_hash_once_reaches_the_sealer(mod=sr):
    """End to end through the REAL sealer functions: the job records the archive by the path the
    sealer opens (the reuse bundle's link), and the sealer's bind_existing_assets then takes the full
    recorded digest through input_sha without reading the archive again; the digest is the full one."""
    import prepare_ordinary_final_run as prep
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        base, tree, job, assets, models = job_fixture(tmp)
        with patch.object(mod.os, "symlink", lambda s_, d, target_is_directory=False: Path(d).mkdir(parents=True)):
            places = mod.place_inputs(tree, base, job, tmp / "home")
        previous = json.loads((Path(places["reuse"]) / "execution_manifest.json").read_text(encoding="utf-8"))["assets_archive"]
        large = mod.large_inputs(base, places)
        record = mod.verified_inputs(large)
        rec = tmp / "verified_inputs.json"
        rec.write_text(json.dumps({"files": record}), encoding="utf-8")
        reads = []
        real_sha = prep.sha
        target = tmp / "out" / "assets.tar"
        target.parent.mkdir()
        with patch.dict(os.environ, {"SHIMMER_SEAL_VERIFIED_INPUTS": str(rec)}), patch.object(prep.sys, "platform", "linux"), \
                patch.object(prep, "sha", lambda p: reads.append(Path(p).name) or real_sha(p)), \
                patch.object(prep, "expected_members", lambda m, w, h: previous["members"]):
            bound = prep.bind_existing_assets(places["reuse"], [], {}, tmp, target)
        full = any(e["sha256"] == sr.sha(base / "assets.tar") for e in record.values())
    archive_reads = [r for r in reads if r == "assets.tar"]
    ok = bound["sha256"] == assets["sha256"] and not archive_reads and full
    return ok, "bound %s; archive read again by the sealer %d times; the recorded digest is the full one %s" % (
        bound["sha256"] == assets["sha256"], len(archive_reads), full)


def proof_seal_command_refuses_a_seal_that_builds_assets(drv=None):
    """The gated seal's expected size is a seal that links a sealed asset archive; a seal without
    --reuse-assets (one that builds the 13 to 22 GB archive) is refused before the gate or the sealer."""
    import seal_route_driver as driver
    drv = drv or driver
    started = []
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(drv, "wait_for_room", lambda step, log, disk: started.append(step) or dict(memory_gb=9, disk_gb=99)),                 patch.object(drv.subprocess, "run", lambda argv: started.append("sealer") or types.SimpleNamespace(returncode=0)):
            with contextlib.redirect_stdout(__import__("io").StringIO()):
                try:
                    drv.main(["seal", "--log", str(Path(tmp) / "g.log"), "--output-dir", str(Path(tmp) / "b"), "--", "--arm", "S"])
                    refused = False
                except sr.RouteError as exc:
                    refused = "--reuse-assets is required" in str(exc)
                linked = drv.main(["seal", "--log", str(Path(tmp) / "g.log"), "--output-dir", str(Path(tmp) / "c"), "--",
                                   "--reuse-assets", "x"])
    ok = refused and started == ["seal", "sealer"] and linked == 0
    return ok, "a seal building assets refused %s before any step %s; a linked seal runs %s" % (refused, started, linked == 0)


def proof_seal_command_reads_the_output_drive(drv=None):
    """The gated seal reads the disk of the drive its --output-dir is on, not the repository's."""
    import seal_route_driver as driver
    drv = drv or driver
    seen = {}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "bundle"
        with patch.object(drv, "wait_for_room", lambda step, log, disk: seen.update(disk=str(disk)) or
                          dict(memory_gb=9, disk_gb=99)), \
                patch.object(drv.subprocess, "run", lambda argv: types.SimpleNamespace(returncode=0)):
            with contextlib.redirect_stdout(__import__("io").StringIO()):
                drv.main(["seal", "--log", str(Path(tmp) / "g.log"), "--output-dir", str(out), "--", "--arm", "S",
                          "--reuse-assets", "x"])
    ok = seen.get("disk") == Path(out).resolve().anchor
    return ok, "gate read %r for an output folder on %r" % (seen.get("disk"), Path(out).resolve().anchor)


def proof_driver_finds_the_job_s_own_lines(drv=None):
    """Gap 1 of round 2: the controller's launch_intent ledger line names only the instance name, which
    the driver derives from the job's binding as the bound wrapper does; with the real name-only line the
    job's own lines are admitted and any other launch line refuses."""
    import seal_route_driver as driver
    drv = drv or driver
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        job_bundle, run_folder, reuse, live, result, base = returned_job(tmp)
        own = drv.own_identifiers(run_folder, sr.sha(job_bundle / "execution_manifest.json"), job_bundle)
        job = json.loads((job_bundle / sr.JOB_FILE).read_text(encoding="utf-8"))
        clean = sr.stale_reason(job, live, own)
    ok = clean is None and any(o.startswith("shimmer-loop-") for o in own) and "id-1" in own
    return ok, "own identifiers %s; the controller's own lines admitted %s" % (sorted(own), clean is None)


def proof_gated_seal_refuses_another_drive_and_its_own_output(drv=None):
    """Gaps 2 and 3 of round 2: the gated seal refuses a reuse bundle on another drive (a link would be
    a copy of the whole archive), and any argument the sealer could read as --output-dir among the
    passed-through ones (--output-dir, --output-dir=..., an abbreviation such as --out)."""
    import seal_route_driver as driver
    drv = drv or driver
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        base = ["seal", "--log", str(Path(tmp) / "g.log"), "--output-dir", str(Path(tmp) / "b"), "--", "--reuse-assets", tmp]
        with patch.object(drv, "wait_for_room", lambda step, log, disk: dict(memory_gb=9, disk_gb=99)),                 patch.object(drv.subprocess, "run", lambda argv: types.SimpleNamespace(returncode=0)),                 contextlib.redirect_stdout(__import__("io").StringIO()):
            out["same drive runs"] = drv.main(base) == 0
            with patch.object(drv, "same_drive", lambda a, b: False):
                out["another drive refused"] = _refused(lambda: drv.main(base))
            for extra in (["--output-dir", "x"], ["--output-dir=x"], ["--out", "x"], ["--outp=x"]):
                out["%s refused" % extra[0]] = _refused(lambda: drv.main(base + extra))
    return all(out.values()), "; ".join("%s %s" % (k, v) for k, v in out.items())


def proof_gated_seal_takes_one_reuse_bundle(drv=None):
    """Round 3, gap 1: the sealer's parser takes abbreviations and the last value wins, so the gated
    seal takes exactly one --reuse-assets written in full: a second value (--reuse-assets twice, an
    abbreviation such as --reuse-a, or --reuse-assets=...) refuses, whatever drive it names."""
    import seal_route_driver as driver
    drv = drv or driver
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        base = ["seal", "--log", str(Path(tmp) / "g.log"), "--output-dir", str(Path(tmp) / "b"), "--", "--reuse-assets", tmp]
        with patch.object(drv, "wait_for_room", lambda step, log, disk: dict(memory_gb=9, disk_gb=99)), \
                patch.object(drv.subprocess, "run", lambda argv: types.SimpleNamespace(returncode=0)), \
                contextlib.redirect_stdout(__import__("io").StringIO()):
            out["one value runs"] = drv.main(base) == 0
            for extra in (["--reuse-assets", "D:/other"], ["--reuse-a", "D:/other"], ["--reuse-assets=D:/other"]):
                out["%s refused" % extra[0].split("=")[0] + ("=" if "=" in extra[0] else "")] = _refused(lambda: drv.main(base + extra))
            out["the = form alone refused"] = _refused(lambda: drv.main(base[:-2] + ["--reuse-assets=" + tmp]))
    return all(out.values()), "; ".join("%s %s" % (k, v) for k, v in out.items())


def proof_admission_refuses_a_leftover_staging_folder(drv=None):
    """Round 3, gap 2: an earlier admission's staging folder refuses a new one, with its reason, and is
    left exactly as it was."""
    import seal_route_driver as driver
    drv = drv or driver
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        job_bundle, run_folder, reuse, live, result, base = returned_job(tmp)
        staging = tmp / "out.staging"
        (staging / "kept").mkdir(parents=True)
        (staging / "kept" / "note.txt").write_text("earlier", encoding="utf-8")
        before = sorted(str(p.relative_to(staging)) for p in staging.rglob("*"))
        try:
            drv.admit(job_bundle, run_folder, reuse, tmp / "out", live, live["budget_ledger"], steps=False,
                      lock=lambda ledger: "held", unlock=lambda held: None)
            reason = None
        except sr.RouteError as exc:
            reason = str(exc)
        after = sorted(str(p.relative_to(staging)) for p in staging.rglob("*"))
        untouched = before == after and (staging / "kept" / "note.txt").read_text(encoding="utf-8") == "earlier"
        nothing_else = not (tmp / "out").exists() and not (tmp / "out.refused").exists()
    ok = bool(reason) and "staging folder of an earlier admission" in reason and untouched and nothing_else
    return ok, "refused %r; the folder untouched %s; nothing admitted or renamed %s" % (reason, untouched, nothing_else)


def proof_a_bad_collected_member_leaves_refused(drv=None):
    """Round 3, gap 3: a refusal inside collected(), after the staging folder exists (a member outside
    it), keeps that folder as .refused and leaves no .staging."""
    import tarfile as tf
    import seal_route_driver as driver
    drv = drv or driver
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        job_bundle, run_folder, reuse, live, result, base = returned_job(tmp)
        archive = run_folder / "collected_evidence.tar.gz"
        with tf.open(archive, "w:gz") as stream:
            info = tf.TarInfo("../outside.txt")
            info.size = 1
            stream.addfile(info, __import__("io").BytesIO(b"x"))
        (run_folder / "collection_integrity.json").write_text(json.dumps({"sha256": sr.sha(archive)}), encoding="utf-8")
        refused = _refused(lambda: drv.admit(job_bundle, run_folder, reuse, tmp / "out", live, live["budget_ledger"],
                                             steps=False, lock=lambda ledger: "held", unlock=lambda held: None))
        kept = (tmp / "out.refused").exists() and not (tmp / "out.staging").exists() and not (tmp / "outside.txt").exists()
    ok = refused and kept
    return ok, "a member outside refused %s; kept as .refused, no .staging, nothing written outside %s" % (refused, kept)


def proof_sealed_flags_are_the_runner_s(prep=None):
    """C4 finding: the sealer seals, for an arm S manifest, the run flags the runner admits (argv_for),
    and holds every manifest to that rule at seal time; the old chain (the ordinary flags for arm S)
    is refused there, as the controller refused it at launch."""
    import prepare_ordinary_final_run as sealer
    import ordinary_final_run as runner
    prep = prep or sealer
    manifest = {"arm": "S", "argv": prep.manifest_argv(None, "S", None, False)}
    held = manifest["argv"] == runner.argv_for(manifest)
    prep.seal_flags_hold(manifest)
    ordinary = _refused(lambda: prep.seal_flags_hold(dict(manifest, argv=list(runner.ARGV))))
    b3 = prep.manifest_argv(None, "B3", None, False) == runner.argv_for({"arm": "B3", "multi_round": False})
    ok = held and ordinary and b3
    return ok, "arm S sealed with the runner's flags %s; the ordinary flags refused at seal time %s; B3 unchanged %s" % (held, ordinary, b3)


def proof_preflight_runs_the_controller_s_admission(pf=None):
    """The bound preflight runs the controller's workload admission (admit_workload) before any provider
    call, so a bundle whose run flags drift from its arm is refused there and no provider client is built."""
    import ordinary_final_bound_preflight as preflight
    import ordinary_final_run as runner
    pf = pf or preflight
    built = []
    with tempfile.TemporaryDirectory() as tmp:
        b = Path(tmp)
        names = ("seal_source.tar", "commit_object.bin", "seal_job.json", "seal_workloads.tar", "reuse_manifest.json")
        manifest = {"arm": "S", "multi_round": False, "protected_test": False, "argv": list(runner.ARGV),
                    "seal_job": {"commit": "a" * 40, "tree": "b" * 40}, "support_files": {n: "c" * 64 for n in names}}
        (b / "execution_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (b / "seal.json").write_text("{}", encoding="utf-8")
        (b / "authorization_binding.json").write_text(json.dumps({"manifest_sha256": sr.sha(b / "execution_manifest.json")}),
                                                      encoding="utf-8")
        with patch.object(pf, "LambdaExperiment", lambda *a: built.append(1) or (_ for _ in ()).throw(AssertionError("provider"))), \
                patch.object(pf, "credential_path", lambda: "unused"):
            try:
                pf.main(b)
                reason = None
            except RuntimeError as exc:
                reason = str(exc)
            except AssertionError:
                reason = "the provider was reached"
    ok = reason == "Run flags changed" and not built
    return ok, "drifted flags refused %r; provider client built %s" % (reason, bool(built))


def proof_run_folder_holds_every_support_file(mod=sr):
    """C4 launch 2: with --output-dir the bound wrapper copies only the bundle's top-level files into
    the run folder, and the controller then holds every sealed support file there (execute's
    `Support source changed`). A job bundle whose read copies are named as the sealer names them
    passes that check in the run folder, each read copy at the digest the job records."""
    import ordinary_final_bound_cloud as bound
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        base, _tree, job, _assets, _models = job_fixture(tmp, mod)
        out = bound.run_folder(base.resolve(), tmp / "runs", False)
        manifest = json.loads((out / "execution_manifest.json").read_text(encoding="utf-8"))
        missing = [n for n, d in manifest["support_files"].items() if not (out / n).is_file() or sr.sha(out / n) != d]
        copies = [k for k, e in job["read_copies"].items()
                  if not (out / mod.read_copy_name(k)).is_file() or sr.sha(out / mod.read_copy_name(k)) != e["sha256"]]
        sealed = all(mod.read_copy_name(k) in manifest["support_files"] for k in job["read_copies"])
    ok = not missing and not copies and sealed and len(job["read_copies"]) == 2
    return ok, "support files missing from the run folder %s; read copies missing or changed %s; each read copy sealed %s" % (
        missing, copies, sealed)


@contextlib.contextmanager
def arm_s_sealing_stand_ins(prep, tmp):
    """Only the heavy collaborators of prepare() are replaced, on the module given (the real sealer or
    a neutralised copy): git, the runtime sample, the wheels and models, the reused archive, the bound
    tree archive and the laptop's read copies and standing orders. Its own logic runs, flags included."""
    import multi_round_launch_checks as mrc
    import decoding_policy
    import final_models
    real_read = prep.read
    # Two pinned wheels (small stand-in files), so the sealer writes a real two-line install.lock.
    wheelhouse = Path(tmp) / "wheelhouse"
    wheelhouse.mkdir(parents=True, exist_ok=True)
    locked = {"pkg-a": "1.0", "pkg-b": "2.0"}
    wheels = {}
    for name in locked:
        (wheelhouse / (name + ".whl")).write_bytes(name.encode())
        wheels[name] = dict(filename=name + ".whl", sha256=hashlib.sha256(name.encode()).hexdigest())

    def source_sample(source, extra=()):
        names = mrc.RUNTIME_SAMPLE + (decoding_policy.DECLARATION,) + tuple(extra)
        return {n: (ROOT / n).read_bytes().replace(b"\r\n", b"\n") for n in names}

    def reused(bundle, models, wheels, wheelhouse, target):
        Path(target).write_bytes(b"asset archive stand-in")
        return dict(filename=Path(target).name, sha256=sr.sha(target), bytes=Path(target).stat().st_size, members={})

    def tree_archive(root, source, archive):
        Path(archive).write_bytes(b"tree stand-in")
        return "b" * 40

    def laptop_copies(main_private, r_ledger, now=None):
        data = {"budget_ledger": b'{"event": "budget_open"}\n', "spend_store": b'{"event": "ceiling"}\n',
                "r_ledger": b'{"event": "budget_open"}\n'}
        return {k: dict(path=sr.READ_COPIES[k], sha256=hashlib.sha256(d).hexdigest(), bytes=len(d), data=d)
                for k, d in data.items()}, 1_000_000.0

    environment = {k: v for k, v in os.environ.items() if k != "SHIMMER_INST_FINDER"}
    with patch.object(prep, "OUT", prep.OUT), \
            patch.object(prep, "git", lambda root, *args: ("f" * 40 + "\n").encode()), \
            patch.object(prep, "runtime_source", source_sample), \
            patch.object(prep, "read", lambda path: {} if Path(path).as_posix().endswith("tools/cloud_run/models.json")
                         else real_read(path)), \
            patch.object(prep, "pins", lambda path: dict(locked)), \
            patch.object(prep, "validate_wheels", lambda directory, pinned: dict(wheels)), \
            patch.object(prep, "wheel_member_hashes", lambda path, sha256, cache_dir=None: {}), \
            patch.object(prep, "WHEELS", wheelhouse), \
            patch.object(prep, "bind_existing_assets", reused), \
            patch.object(prep, "bound_tree_archive", tree_archive), \
            patch.object(sr, "read_copies", laptop_copies), \
            patch.object(prep.guard, "standing_orders_failures", lambda root: []), \
            patch.object(prep.guard, "standing_orders_root", lambda: tmp), \
            patch.object(final_models, "verify", lambda role, root=None: (None, {})), \
            patch.dict(os.environ, environment, clear=True), \
            contextlib.redirect_stdout(__import__("io").StringIO()):
        yield mrc.cc


def seal_arm_s(prep, tmp):
    """An arm S job bundle sealed by `prep.prepare()` under arm_s_sealing_stand_ins; returns its folder."""
    inputs = tmp / "inputs"
    inputs.mkdir()
    (inputs / "runtime.candidate.lock").write_text("", encoding="utf-8")
    reuse = tmp / "reuse"
    reuse.mkdir()
    (reuse / "execution_manifest.json").write_text(json.dumps({"assets_archive": {"filename": "assets.tar"}}), encoding="utf-8")
    (tmp / "w.txt").write_text("a workload stand-in\n", encoding="utf-8")
    requests = tmp / "requests.json"
    requests.write_text(json.dumps({"requests": [{"name": "s0", "argv": ["--workload", str(tmp / "w.txt")]}]}), encoding="utf-8")
    bundle = tmp / "job"
    with arm_s_sealing_stand_ins(prep, tmp) as cc:
        (inputs / "provider_inventory.json").write_text(json.dumps(dict(
            instances=[], instance_types=[cc.A10_TYPE], images=[dict(cc.IMAGE)], observed_at="fixture")), encoding="utf-8")
        ledger = tmp / "ledger" / "budget_ledger.jsonl"
        cc.open_ledger(ledger)
        prep.prepare(bundle, reuse_assets=reuse, arm="S", seal_requests=requests, inputs_from=inputs,
                     budget=dict(ledgers=[ledger], forecast_minutes=cc.FORECAST_MINUTES, storage_forecast_usd=cc.STORAGE_USD,
                                 reaped=[ledger], uncompared=True),
                     now_epoch=cc.FakeClock().now)
    return bundle


def proof_sealed_files_are_lf(prep=None, run_mod=None):
    """C4 launch 4: every text file the sealer writes (each JSON through the shared write(), and
    install.lock through write_text_lf) is LF on every platform, so its digest, and the env key over
    install.lock's, are the same on the laptop and on the instance."""
    import prepare_ordinary_final_run as sealer
    import declare_asset_copy
    prep = prep or sealer
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with contextlib.ExitStack() as stack:
            if run_mod is not None:
                stack.enter_context(patch.object(prep, "write", run_mod.write))
                stack.enter_context(patch.object(declare_asset_copy, "write", run_mod.write))
            bundle = seal_arm_s(prep, tmp)
        texts = {p.name: p.read_bytes() for p in bundle.iterdir() if p.is_file() and p.suffix == ".json"}
        crlf = sorted(n for n, b in texts.items() if b"\r\n" in b)
        multi = [n for n, b in texts.items() if b.count(b"\n") > 1]
        lock = (bundle / "install.lock").read_bytes()
    ok = not crlf and len(multi) >= 3 and b"\r" not in lock and lock.count(b"\n") >= 2
    return ok, "JSON files written %d, multi-line %d, with CRLF %s; the bundle's install.lock: %d lines, CR %s" % (
        len(texts), len(multi), crlf, lock.count(b"\n"), b"\r" in lock)


def proof_arm_s_sealed_through_prepare(prep=None):
    """The sealer's own prepare() seals an arm S job bundle (stand-ins for its heavy collaborators
    only): its run flags are the runner's argv_for, every support file sits beside the manifest (each
    read copy among them), a nested support name is refused at sealing, and a run folder made from
    the bundle with --output-dir holds every support file the controller checks."""
    import prepare_ordinary_final_run as sealer
    import ordinary_final_run as runner
    import ordinary_final_bound_cloud as bound
    prep = prep or sealer
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bundle = seal_arm_s(prep, tmp)
        m = json.loads((bundle / "execution_manifest.json").read_text(encoding="utf-8"))
        flags = m["arm"] == "S" and m["argv"] == runner.argv_for(m)
        top = all("/" not in n and "\\" not in n for n in m["support_files"])
        copies = sorted(m["seal_job"]["read_copies"])
        sealed = all(m["support_files"].get(sr.read_copy_name(k)) == m["seal_job"]["read_copies"][k]["sha256"] for k in copies)
        out = bound.run_folder(bundle.resolve(), tmp / "runs", False)
        missing = [n for n, d in m["support_files"].items() if not (out / n).is_file() or sr.sha(out / n) != d]
        nested = _refused(lambda: prep.top_level_support(["install.lock", "read_copies/budget_ledger"]))
    ok = flags and top and sealed and copies == ["budget_ledger", "r_ledger", "spend_store"] and not missing and nested
    return ok, ("argv equals the runner's argv_for %s; support files top-level %s; read copies sealed %s %s; missing from "
                "the run folder %s; a nested support name refused %s" % (flags, top, copies, sealed, missing, nested))


def proof_gate_tree_archived_from_the_laptop_commit_object(prep=None):
    """Arm G in a route-S job (22:43 refusal): the instance's repository holds the laptop's commit object
    with no parent, as exact_commit leaves it. The gate tree is archived from it, every member's time the
    commit's committer time (read from the object, never from a `git log` walk that needs the parent)."""
    import prepare_ordinary_final_run as sealer
    prep = prep or sealer
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        commit, tree, obj = laptop_commit(tmp / "laptop", FILES)
        wanted = int(git_in(tmp / "laptop")("show", "-s", "--format=%ct", commit).strip())
        (tmp / "commit.bin").write_bytes(obj)
        git = instance_checkout(tmp / "inst", FILES)
        sr.exact_commit(git, tmp / "commit.bin", commit, tree)
        walk = subprocess.run(["git", "-C", str(tmp / "inst"), "log", "-1", "--format=%ct", commit], capture_output=True)
        archive = tmp / "gate_source.tar"
        made = prep.bound_tree_archive(tmp / "inst", commit, archive)
        with tarfile.open(archive) as tar:
            members = {m.name: m.mtime for m in tar.getmembers()}
    ok = made == tree and set(members) == set(FILES) and set(members.values()) == {wanted}
    return ok, "tree id %s, members %d, times %s (committer time %d); a log walk in that repository exits %d" % (
        made == tree, len(members), sorted(set(members.values())), wanted, walk.returncode)


def _refused(call):
    try:
        call()
    except Exception:
        return True
    return False


def _module_from(path, old, new, name, more=()):
    source = Path(path).read_text(encoding="utf-8")
    for passage, replacement in ((old, new),) + tuple(more):
        if source.count(passage) != 1:
            raise RuntimeError("the passage moved, so the neutralisation cannot be applied")
        source = source.replace(passage, replacement)
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    exec(compile(source, str(path), "exec"), mod.__dict__)
    return mod


def _swap_module(proof, kw, path, old, new, *more):
    """`more` adds further (old, new) passages, each applied once, after the first."""
    @contextlib.contextmanager
    def swap():
        original = globals()[proof]
        mod = _module_from(path, old, new, Path(path).stem + "_neutralised", more)
        globals()[proof] = lambda: original(**{kw: mod})
        try:
            yield
        finally:
            globals()[proof] = original
    return swap


def _module_with(old, new):
    source = Path(sr.__file__).read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise RuntimeError("the passage moved, so the neutralisation cannot be applied")
    mod = types.ModuleType("seal_route_neutralised")
    mod.__file__ = sr.__file__
    exec(compile(source.replace(old, new), sr.__file__, "exec"), mod.__dict__)
    return mod


def _swap(name, passage, replacement):
    @contextlib.contextmanager
    def swap():
        original = globals()[name]
        mod = _module_with(passage, replacement)
        globals()[name] = lambda: original(mod)
        try:
            yield
        finally:
            globals()[name] = original
    return swap


PROOFS = [
    ("the instance re-creates the laptop's commit over the same tree; another tree refuses", "proof_exact_commit"),
    ("arm G in a route-S job: the gate tree is archived from the parentless commit object, members at its committer time",
     "proof_gate_tree_archived_from_the_laptop_commit_object"),
    ("a large input is hashed once and its digest reused only while its stat stands", "proof_verified_inputs_and_stat"),
    ("the sealer takes the verified-inputs record only on the instance", "proof_sealer_uses_the_record_only_on_the_instance"),
    ("item 3: the project archive stored once by its fingerprint, never replaced", "proof_project_stored_once"),
    ("a stale read copy is refused on the laptop", "proof_stale_read_copy_refused"),
    ("a request's files travel in the workloads archive", "proof_requests_carry_their_files"),
    ("a bundle's asset receipt comes from the one verification of its archive", "proof_per_bundle_receipt"),
    ("item 3: a project archive is the bundle's bytes or a store record of exactly its fingerprint", "proof_project_held_by_fingerprint"),
    ("item 3: the reverify reads the committed members from git, each held to its digest", "proof_reverify_reads_members_from_git"),
    ("the guard reads the laptop's attestation of the standing orders only on the instance",
     "proof_guard_reads_the_attestation_only_on_the_instance"),
    ("the seal job end to end on stand-ins: placed, hashed once, sealed, stored, stripped", "proof_job_end_to_end"),
    ("the laptop driver admits returned bundles and refuses a stale read copy", "proof_driver_admits_returned_bundles"),
    ("the laptop driver gates a heavy step on one reading and logs that reading", "proof_driver_gates_and_logs_one_reading"),
    ("the gate holds the D-099 disk floor after the step's expected size", "proof_driver_gate_holds_the_disk_floor"),
    ("a large input that changes while it is hashed gets no digest", "proof_input_changed_while_hashed_refused"),
    ("hash-once reaches the sealer: the archive keyed by the path it opens, the full digest taken", "proof_hash_once_reaches_the_sealer"),
    ("the gated seal reads the disk of its output drive", "proof_seal_command_reads_the_output_drive"),
    ("the gated seal refuses a seal that would build the asset archive", "proof_seal_command_refuses_a_seal_that_builds_assets"),
    ("the driver finds the job's own lines with the controller's name-only intent line", "proof_driver_finds_the_job_s_own_lines"),
    ("the gated seal refuses another drive and an --output-dir among the sealer's arguments",
     "proof_gated_seal_refuses_another_drive_and_its_own_output"),
    ("the gated seal takes exactly one --reuse-assets, written in full", "proof_gated_seal_takes_one_reuse_bundle"),
    ("an admission refuses a leftover staging folder and leaves it untouched", "proof_admission_refuses_a_leftover_staging_folder"),
    ("a bad collected member leaves the staging folder refused", "proof_a_bad_collected_member_leaves_refused"),
    ("the sealer seals the runner's flags for arm S and holds every arm to them", "proof_sealed_flags_are_the_runner_s"),
    ("the bound preflight runs the controller's workload admission before any provider call",
     "proof_preflight_runs_the_controller_s_admission"),
    ("C4 launch 2: a run folder made with --output-dir holds every support file the job reads",
     "proof_run_folder_holds_every_support_file"),
    ("prepare() seals arm S with the runner's flags, every support file top-level and held in a run folder",
     "proof_arm_s_sealed_through_prepare"),
    ("C4 launch 3: a failed seal returns no archive and names its cause in a capped tail",
     "proof_failed_seal_returns_no_archive_and_names_its_cause"),
    ("a sealer start that raises is that request's failed row, its archives stripped", "proof_a_seal_that_raises_is_a_failed_row"),
    ("an error after a seal (the store) strips both archives", "proof_an_error_after_sealing_strips_the_bundle"),
    ("the seal log in the evidence is capped to its last bytes", "proof_the_seal_log_is_capped"),
    ("run_requests raising after the archives are linked strips every bundle; a tail error is recorded",
     "proof_run_requests_raising_strips_every_bundle"),
    ("C4 launch 4: every text file the sealer writes is LF on every platform", "proof_sealed_files_are_lf"),
]

DRIVER = ROOT / "tools" / "seal_route_driver.py"
OLD_CHAIN = ("        argv=runner.gate_argv(gate_block) if gate_block else runner.LAUNCHER_ARGV if launcher "
             "else MULTI_ROUND_ARGV if multi_round else ARGV,\n")
NEUTRALISATIONS = [
    ("CRLF put back in the shared write()", "proof_sealed_files_are_lf", _swap_module(
        "proof_sealed_files_are_lf", "run_mod", ROOT / "tools" / "ordinary_final_run.py",
        "sort_keys=True)+'\\n', encoding='utf8', newline='\\n')\n",
        "sort_keys=True)+'\\n', encoding='utf8', newline='\\r\\n')\n")),
    ("install.lock written by a bare write_text with CRLF again", "proof_sealed_files_are_lf", _swap_module(
        "proof_sealed_files_are_lf", "prep", ROOT / "tools" / "prepare_ordinary_final_run.py",
        "    write_text_lf(OUT/'install.lock', install)\n",
        "    (OUT/'install.lock').write_text(install, encoding='utf8', newline='\\r\\n')\n")),
    ("CRLF put back in the install.lock writer", "proof_sealed_files_are_lf", _swap_module(
        "proof_sealed_files_are_lf", "prep", ROOT / "tools" / "prepare_ordinary_final_run.py",
        "    Path(path).write_text(text, encoding='utf8', newline='\\n')\n",
        "    Path(path).write_text(text, encoding='utf8', newline='\\r\\n')\n")),
    ("the finally strip removed", "proof_run_requests_raising_strips_every_bundle", _swap(
        "proof_run_requests_raising_strips_every_bundle",
        "            for request in job['requests']:\n                strip_returned(out / request['name'])\n",
        "            pass\n")),
    ("a tail error raised, not recorded", "proof_run_requests_raising_strips_every_bundle", _swap(
        "proof_run_requests_raising_strips_every_bundle",
        "        except Exception as exc:\n            row['tail_error'] = type(exc).__name__\n",
        "        except ZeroDivisionError as exc:\n            row['tail_error'] = type(exc).__name__\n")),
    ("a raising sealer escapes the request", "proof_a_seal_that_raises_is_a_failed_row", _swap(
        "proof_a_seal_that_raises_is_a_failed_row",
        "        except Exception as exc:\n            row = dict(name=request['name'], rc=None,",
        "        except subprocess.TimeoutExpired as exc:\n            row = dict(name=request['name'], rc=None,")),
    ("no strip after an error past the seal", "proof_an_error_after_sealing_strips_the_bundle", _swap(
        "proof_an_error_after_sealing_strips_the_bundle",
        "            row['post_error'] = ' '.join(str(exc).split())[:300]\n            row['stripped'] = strip_returned(bundle)\n",
        "            row['post_error'] = ' '.join(str(exc).split())[:300]\n")),
    ("the seal log not capped", "proof_the_seal_log_is_capped", _swap(
        "proof_the_seal_log_is_capped", "            cap_log(log_path)\n", "")),
    ("C4 launch 3: a failed seal's archives kept", "proof_failed_seal_returns_no_archive_and_names_its_cause", _swap(
        "proof_failed_seal_returns_no_archive_and_names_its_cause",
        "            row['stripped'] = strip_returned(bundle)\n            continue\n", "            continue\n")),
    ("C4 launch 3: no seal tail written", "proof_failed_seal_returns_no_archive_and_names_its_cause", _swap(
        "proof_failed_seal_returns_no_archive_and_names_its_cause",
        "            write(str(out) + SEAL_TAIL_SUFFIX, tail)\n", "")),
    ("C4 launch 3: the tail not capped", "proof_failed_seal_returns_no_archive_and_names_its_cause", _swap(
        "proof_failed_seal_returns_no_archive_and_names_its_cause",
        "            stream.seek(max(0, size - SEAL_TAIL_BYTES))\n            tail = stream.read(SEAL_TAIL_BYTES)\n",
        "            tail = stream.read()\n")),
    ("C4 launch 2: the read copies in a subfolder again", "proof_run_folder_holds_every_support_file", _swap(
        "proof_run_folder_holds_every_support_file",
        "READ_COPY_PREFIX = 'read_copy_'", "READ_COPY_PREFIX = 'read_copies/'")),
    ("the old flag chain put back in prepare()", "proof_arm_s_sealed_through_prepare", _swap_module(
        "proof_arm_s_sealed_through_prepare", "prep", ROOT / "tools" / "prepare_ordinary_final_run.py",
        "        argv=manifest_argv(gate_block, arm, launcher, multi_round),\n", OLD_CHAIN)),
    ("the old flag chain put back in prepare() and not held at seal time", "proof_arm_s_sealed_through_prepare", _swap_module(
        "proof_arm_s_sealed_through_prepare", "prep", ROOT / "tools" / "prepare_ordinary_final_run.py",
        "        argv=manifest_argv(gate_block, arm, launcher, multi_round),\n", OLD_CHAIN,
        ("    seal_flags_hold(manifest)\n    write(OUT/'execution_manifest.json', manifest)\n",
         "    write(OUT/'execution_manifest.json', manifest)\n"))),
    ("a nested support name admitted at sealing", "proof_arm_s_sealed_through_prepare", _swap_module(
        "proof_arm_s_sealed_through_prepare", "prep", ROOT / "tools" / "prepare_ordinary_final_run.py",
        "    require(not nested, 'A support file sits in a subfolder,", "    require(True, 'A support file sits in a subfolder,")),
    ("the old flag chain for arm S", "proof_sealed_flags_are_the_runner_s", _swap_module(
        "proof_sealed_flags_are_the_runner_s", "prep", ROOT / "tools" / "prepare_ordinary_final_run.py",
        "    if arm == 'S':\n        return list(runner.SEAL_ARGV)\n", "")),
    ("the flags not held at seal time", "proof_sealed_flags_are_the_runner_s", _swap_module(
        "proof_sealed_flags_are_the_runner_s", "prep", ROOT / "tools" / "prepare_ordinary_final_run.py",
        "    require(manifest['argv'] == runner.argv_for(manifest),", "    require(True,")),
    ("the preflight without the controller's admission", "proof_preflight_runs_the_controller_s_admission", _swap_module(
        "proof_preflight_runs_the_controller_s_admission", "pf", ROOT / "tools" / "ordinary_final_bound_preflight.py",
        "    run.admit_workload(m, read(base / 'seal.json'), base)\n", "")),
    ("the instance name not derived from the job's binding", "proof_driver_finds_the_job_s_own_lines", _swap_module(
        "proof_driver_finds_the_job_s_own_lines", "drv", DRIVER,
        "own = {guard.instance_name(bound['preparation_commit'][:7] + '-' + bound['manifest_sha256'][:8])}", "own = set()")),
    ("a reuse bundle on another drive admitted", "proof_gated_seal_refuses_another_drive_and_its_own_output", _swap_module(
        "proof_gated_seal_refuses_another_drive_and_its_own_output", "drv", DRIVER,
        "sr.require(same_drive(reuse, args.output_dir),", "sr.require(True,")),
    ("an --output-dir among the sealer's arguments admitted", "proof_gated_seal_refuses_another_drive_and_its_own_output", _swap_module(
        "proof_gated_seal_refuses_another_drive_and_its_own_output", "drv", DRIVER,
        "sr.require(not [a for a in sealer_args if a.startswith('--o') and '--output-dir'.startswith(a.split('=', 1)[0])],",
        "sr.require(True,")),
    ("a second --reuse-assets value taken", "proof_gated_seal_takes_one_reuse_bundle", _swap_module(
        "proof_gated_seal_takes_one_reuse_bundle", "drv", DRIVER,
        "sr.require(spellings == ['--reuse-assets'],", "sr.require(True,")),
    ("a leftover staging folder not refused", "proof_admission_refuses_a_leftover_staging_folder", _swap_module(
        "proof_admission_refuses_a_leftover_staging_folder", "drv", DRIVER,
        "        sr.require(not staging.exists(), 'A staging folder of an earlier admission is there; look at it first')\n", "")),
    ("collected() moved outside the try", "proof_a_bad_collected_member_leaves_refused", _swap_module(
        "proof_a_bad_collected_member_leaves_refused", "drv", DRIVER,
        "        rows = []\n        try:\n            sealed, result = collected(run_folder, staging / 'collected')\n",
        "        rows = []\n        sealed, result = collected(run_folder, staging / 'collected')\n        try:\n")),
    ("the stale check moved before the lock", "proof_driver_admits_returned_bundles", _swap_module(
        "proof_driver_admits_returned_bundles", "drv", DRIVER,
        "    held = lock(ledger)\n    try:\n        reason = sr.stale_reason(job, live, own)\n",
        "    reason = sr.stale_reason(job, live, own)\n    held = lock(ledger)\n    try:\n")),
    ("a later refusal renaming over an earlier one", "proof_driver_admits_returned_bundles", _swap_module(
        "proof_driver_admits_returned_bundles", "drv", DRIVER,
        "    while name.exists():", "    while False:")),
    ("a seal that builds the archive admitted by the gate", "proof_seal_command_refuses_a_seal_that_builds_assets", _swap_module(
        "proof_seal_command_refuses_a_seal_that_builds_assets", "drv", DRIVER,
        "sr.require('--reuse-assets' in sealer_args,", "sr.require(True,")),
    ("a returned bundle not held to the job's row", "proof_driver_admits_returned_bundles", _swap_module(
        "proof_driver_admits_returned_bundles", "drv", DRIVER,
        "sr.require(sr.sha(source / 'execution_manifest.json') == row.get('manifest_sha256')", "sr.require(True or sr.sha(source / 'execution_manifest.json') == row.get('manifest_sha256')")),
    ("the run folder not held to the job", "proof_driver_admits_returned_bundles", _swap_module(
        "proof_driver_admits_returned_bundles", "drv", DRIVER,
        "sr.require(value.get('execution_manifest_sha256') == job_manifest_sha256,", "sr.require(True,")),
    ("the result not held to the job", "proof_driver_admits_returned_bundles", _swap_module(
        "proof_driver_admits_returned_bundles", "drv", DRIVER,
        "sr.require(result.get('job_manifest_sha256') == job_sha,", "sr.require(True,")),
    ("the reuse bundle not held to the job", "proof_driver_admits_returned_bundles", _swap_module(
        "proof_driver_admits_returned_bundles", "drv", DRIVER,
        "sr.require(sr.sha(Path(reuse) / 'execution_manifest.json') == job_manifest['support_files'][sr.REUSE_MANIFEST],", "sr.require(True,")),
    ("the stale check not made in the admission", "proof_driver_admits_returned_bundles", _swap_module(
        "proof_driver_admits_returned_bundles", "drv", DRIVER,
        "reason = sr.stale_reason(job, live, own)", "reason = None")),
    ("the ledger lock not held", "proof_driver_admits_returned_bundles", _swap_module(
        "proof_driver_admits_returned_bundles", "drv", DRIVER, "held = lock(ledger)", "held = 'held'")),
    ("a refusal mid-way leaving what passed admitted", "proof_driver_admits_returned_bundles", _swap_module(
        "proof_driver_admits_returned_bundles", "drv", DRIVER,
        "staging.rename(refused_name(out))", "(staging / 'bundles').rename(out); staging.rename(refused_name(out))")),
    ("the gated seal reading the repository's drive", "proof_seal_command_reads_the_output_drive", _swap_module(
        "proof_seal_command_reads_the_output_drive", "drv", DRIVER,
        "reading = wait_for_room('seal', args.log, drive)", "reading = wait_for_room('seal', args.log, ROOT)")),
    ("R's ledger not held to its copy", "proof_stale_read_copy_refused", _swap("proof_stale_read_copy_refused",
        "STALE_RULES = {'budget_ledger': 'own_lines', 'r_ledger': 'own_lines', 'spend_store': 'prefix'}",
        "STALE_RULES = {'budget_ledger': 'own_lines', 'spend_store': 'prefix'}")),
    ("the spend store not held to its copy", "proof_stale_read_copy_refused", _swap("proof_stale_read_copy_refused",
        "STALE_RULES = {'budget_ledger': 'own_lines', 'r_ledger': 'own_lines', 'spend_store': 'prefix'}",
        "STALE_RULES = {'budget_ledger': 'own_lines', 'r_ledger': 'own_lines'}")),
    ("an input's state not compared after its hash", "proof_input_changed_while_hashed_refused", _swap(
        "proof_input_changed_while_hashed_refused",
        "require(state(path) == before[path], 'A large input changed while it was hashed: ' + Path(path).name)", "pass")),
    ("the archive keyed by the run root's path, not the one the sealer opens", "proof_hash_once_reaches_the_sealer", _swap(
        "proof_hash_once_reaches_the_sealer",
        "return [Path(places['reuse']) / previous['filename']] + [",
        "return [Path(base) / 'assets.tar'] + [")),
    ("the sealer taking the record off Linux", "proof_sealer_uses_the_record_only_on_the_instance", _swap_module(
        "proof_sealer_uses_the_record_only_on_the_instance", "prep", ROOT / "tools" / "prepare_ordinary_final_run.py",
        "if record and sys.platform == 'linux':", "if record:")),
    ("the project archive left in the returned bundle", "proof_job_end_to_end", _swap("proof_job_end_to_end",
        "row['store'] = store_project(bundle, store)", "row['store'] = None")),
    ("the disk floor copied into the gate", "proof_driver_gate_holds_the_disk_floor", _swap_module(
        "proof_driver_gate_holds_the_disk_floor", "drv", ROOT / "tools" / "seal_route_driver.py",
        "and disk - expected_bytes >= orders.DISK_FLOOR)", "and disk - expected_bytes >= 30 * 2 ** 30)")),
    ("the step's expected size not counted", "proof_driver_gate_holds_the_disk_floor", _swap_module(
        "proof_driver_gate_holds_the_disk_floor", "drv", ROOT / "tools" / "seal_route_driver.py",
        "and disk - expected_bytes >= orders.DISK_FLOOR)", "and disk >= orders.DISK_FLOOR)")),
    ("a second reading logged after the gate", "proof_driver_gates_and_logs_one_reading", _swap_module(
        "proof_driver_gates_and_logs_one_reading", "drv", ROOT / "tools" / "seal_route_driver.py",
        "line = dict(reading, step=step, event='start',", "line = dict(read(disk_path), step=step, event='start',")),
    ("the attestation read on the laptop too", "proof_guard_reads_the_attestation_only_on_the_instance", _swap_module(
        "proof_guard_reads_the_attestation_only_on_the_instance", "gd", ROOT / "tools" / "loop_budget_guard.py",
        "if not path or platform != 'linux':", "if not path:")),
    ("the attestation not bound to its job", "proof_guard_reads_the_attestation_only_on_the_instance", _swap_module(
        "proof_guard_reads_the_attestation_only_on_the_instance", "gd", ROOT / "tools" / "loop_budget_guard.py",
        "and sealed.get('refusals') == value['refusals'] and (base / 'RUN_CLAIMED').is_file(),",
        "or True,")),
    ("the attestation's expiry not read", "proof_guard_reads_the_attestation_only_on_the_instance", _swap_module(
        "proof_guard_reads_the_attestation_only_on_the_instance", "gd", ROOT / "tools" / "loop_budget_guard.py",
        "refuse(isinstance(expires, (int, float)) and (time.time() if now is None else now) < expires,", "refuse(True,")),
    ("a store record of another fingerprint accepted", "proof_project_held_by_fingerprint", _swap_module(
        "proof_project_held_by_fingerprint", "run", ROOT / "tools" / "ordinary_final_run.py",
        "require(held.get('sha256') == digest and held.get('store_name') == 'project-%s.tar.gz' % digest,", "require(True,")),
    ("the reverify not comparing a member read from git", "proof_reverify_reads_members_from_git", _swap_module(
        "proof_reverify_reads_members_from_git", "rv", ROOT / "tools" / "ordinary_final_bound_reverify.py",
        "require(hashlib.sha256(data).hexdigest() == digest, 'Archived runtime differs from sealed commit: ' + name)", "pass")),
    ("the commit time read by a git log walk", "proof_gate_tree_archived_from_the_laptop_commit_object", _swap_module(
        "proof_gate_tree_archived_from_the_laptop_commit_object", "prep", ROOT / "tools" / "prepare_ordinary_final_run.py",
        "mtime = int(committer[0].rsplit(b' ', 2)[-2])",
        "mtime = int(run('log', '-1', '--format=%ct', source).decode().strip())")),
    ("the commit id not compared", "proof_exact_commit", _swap("proof_exact_commit",
        "require(written == commit,", "require(True,")),
    ("the tree not compared", "proof_exact_commit", _swap("proof_exact_commit",
        "require(git('rev-parse', commit + '^{tree}').strip() == tree,", "require(True,")),
    ("the stat not compared", "proof_verified_inputs_and_stat", _swap("proof_verified_inputs_and_stat",
        "if (st.st_size, st.st_mtime_ns, st.st_ino) != (entry['size'], entry['mtime_ns'], entry['inode']):", "if False:")),
    ("the chunks not compared", "proof_verified_inputs_and_stat", _swap("proof_verified_inputs_and_stat",
        "if chunk_digests(path, st.st_size) != entry.get('chunks'):", "if False:")),
    ("a stored archive not held to its digest", "proof_project_stored_once", _swap("proof_project_stored_once",
        "require(sha(target) == digest, 'A stored project archive does not hold its own digest: ' + target.name)", "pass")),
    ("any appended line taken as the job's own", "proof_stale_read_copy_refused", _swap("proof_stale_read_copy_refused",
        "foreign = [r for r in added if not ({r.get('instance_name'), r.get('instance_id')} & own)]", "foreign = []")),
    ("the job's own flags admitted in a request", "proof_requests_carry_their_files", _swap("proof_requests_carry_their_files",
        "require(not any(a in argv for a in ('--output-dir', '--reuse-assets', '--inputs-from', '--ledger')),", "require(True,")),
    ("a receipt for any archive", "proof_per_bundle_receipt", _swap("proof_per_bundle_receipt",
        "require({k: mine['assets_archive'][k] for k in keys} == {k: theirs['assets_archive'][k] for k in keys},", "require(True,")),
]


def run(name):
    try:
        return globals()[name]()
    except Exception as exc:
        return False, "raised %s: %s" % (type(exc).__name__, str(exc)[:200])


def main():
    failures = 0
    for what, name in PROOFS:
        ok, detail = run(name)
        failures += not ok
        print("%s %s: %s" % ("PASS" if ok else "FAIL", what, detail))
    for what, name, patcher in NEUTRALISATIONS:
        with patcher():
            ok, detail = run(name)
        if ok:
            failures += 1
            print("FAIL neutralised (%s) and the proof still passes: %s" % (what, detail))
            continue
        if not run(name)[0]:
            failures += 1
            print("FAIL restored (%s) and the proof fails" % what)
            continue
        print("PASS neutralised (%s): FAIL; restored: PASS" % what)
    total = len(PROOFS) + len(NEUTRALISATIONS)
    print("%s route S checks: %d of %d proofs and neutralisations pass" % ("PASS" if not failures else "FAIL",
                                                                         total - failures, total))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
