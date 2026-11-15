"""Proofs for lane/seal-speed, on fixtures only: no seal, no model, no network.

(A) tools/verify_ordinary_final_assets.py reads the archive once. On the same fixture bundle the
    verifier as it stood at the K-seal commit (read from git) and the one-pass verifier write
    byte-identical receipts, and both refuse a member with one byte flipped (whole digest re-recorded
    so only the member check can catch it), a wrong whole digest, and bytes after the archive's end.
(B) tools/prepare_ordinary_final_run.py hashes wheel members streamed and caches them by the wheel's
    full SHA-256: the streamed hashes equal the old whole-member hashes, a second call is a cache hit,
    a wheel whose bytes changed is read afresh, and an entry naming another digest, wheel or rule is
    never used.

Each proof is neutralised in memory, must FAIL, is restored and must PASS.

    py -3.12 -X utf8 tools/seal_speed_checks.py
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import types
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import prepare_ordinary_final_run as prep  # noqa: E402
import verify_ordinary_final_assets as new_verify  # noqa: E402

BASE_COMMIT = "933a9428"   # the K-seal commit the lane branched from
MODEL = "fixture-org/fixture-model"
REVISION = "a" * 40


def wheelhouse():
    """A wheelhouse holding the pinned huggingface_hub wheel the verifier imports."""
    for root in (ROOT, ROOT.parents[2] if len(ROOT.parents) > 2 else ROOT):
        folder = root / "output" / "cloud_wheels" / "ordinary_final_cp312"
        if list(folder.glob("huggingface_hub-0.30.2-*.whl")):
            return folder
    return None


def old_verify():
    """The verifier at BASE_COMMIT, loaded from git as its own module."""
    source = subprocess.run(["git", "-C", str(ROOT), "show", BASE_COMMIT + ":tools/verify_ordinary_final_assets.py"],
                            capture_output=True, check=True).stdout.decode("utf-8")
    mod = types.ModuleType("verify_ordinary_final_assets_old")
    mod.__file__ = str(ROOT / "tools" / "verify_ordinary_final_assets.py")
    exec(compile(source, mod.__file__, "exec"), mod.__dict__)
    return mod


def build_bundle(folder, flip=False, rerecord=False, wrong_whole=False, trailing=False):
    """A bundle with an HF-cache-shaped asset archive and its manifest. `flip` changes one byte of
    the weight member; `rerecord` records the whole digest of the archive as written (so only the
    member check can refuse); `wrong_whole` records another whole digest; `trailing` appends bytes
    after the end of the archive and records its size."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    prefix = "hf_cache/hub/models--" + MODEL.replace("/", "--")
    weight = bytes(range(256)) * 4096
    members = {prefix + "/refs/main": REVISION.encode("ascii"),
               prefix + "/snapshots/" + REVISION + "/config.json": json.dumps({"model_type": "fixture"}).encode(),
               prefix + "/snapshots/" + REVISION + "/model.safetensors": weight}
    recorded = {n: {"bytes": len(d), "sha256": hashlib.sha256(d).hexdigest()} for n, d in members.items()}
    if flip:
        members[prefix + "/snapshots/" + REVISION + "/model.safetensors"] = b"\xff" + weight[1:]   # weight[0] is 0
    archive = folder / "assets.tar"
    with tarfile.open(archive, "w", format=tarfile.PAX_FORMAT) as out:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            out.addfile(info, io.BytesIO(data))
    clean_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if trailing:
        with archive.open("ab") as stream:
            stream.write(b"after the end" * 100)
    raw = archive.read_bytes()
    whole = hashlib.sha256(raw).hexdigest() if (rerecord or not (flip or trailing)) else clean_digest
    if wrong_whole:
        whole = "e" * 64
    ref = REVISION.encode("ascii")
    manifest = {"assets_archive": {"filename": "assets.tar", "bytes": len(raw), "sha256": whole, "members": recorded},
                "models": [{"model_id": MODEL, "revision": REVISION,
                            "cache_ref": {"bytes": len(ref), "sha256": hashlib.sha256(ref).hexdigest()}}]}
    (folder / "execution_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return folder


def refusal(mod, bundle, wheels):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            mod.verify(bundle, wheels)
    except Exception as exc:   # require() raises the module's own error type
        return str(exc) or type(exc).__name__
    return None


def proof_one_pass_verifier(new=None):
    new = new or new_verify
    wheels = wheelhouse()
    if wheels is None:
        return False, "no huggingface_hub 0.30.2 wheel found under output/cloud_wheels: the proof cannot run"
    old = old_verify()
    out = {}
    with tempfile.TemporaryDirectory(prefix="shimmer_seal_speed_") as tmp:
        tmp = Path(tmp)
        receipts = []
        for name, mod in (("old", old), ("new", new)):
            bundle = build_bundle(tmp / ("clean_" + name))
            with contextlib.redirect_stdout(io.StringIO()):
                mod.verify(bundle, wheels)
            receipts.append((bundle / "asset_verification.json").read_bytes())
        out["receipts identical"] = receipts[0] == receipts[1] and json.loads(receipts[1])["passed"] is True
        cases = {"one member byte flipped": dict(flip=True, rerecord=True), "a wrong whole digest": dict(wrong_whole=True),
                 "bytes after the archive's end": dict(trailing=True)}
        for case, kw in cases.items():
            out[case] = {name: bool(refusal(mod, build_bundle(tmp / (case.replace(" ", "_") + name), **kw), wheels))
                         for name, mod in (("old", old), ("new", new))}
    ok = out["receipts identical"] and all(all(v.values()) for k, v in out.items() if isinstance(v, dict))
    return ok, "; ".join("%s: %s" % (k, v) for k, v in out.items())


def make_wheel(path, payload=b"x" * 10_000_000):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("pkg/__init__.py", b"")
        z.writestr("pkg/big.so", payload)
        z.writestr("pkg-1.0.dist-info/RECORD", b"not asserted")
        z.writestr("pkg-1.0.data/scripts/tool", b"not asserted")
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def old_member_hashes(path):
    """The sealer's computation at BASE_COMMIT: every asserted member read whole."""
    with zipfile.ZipFile(path) as archive:
        return {n: hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist()
                if not n.endswith('/') and '.dist-info/' not in n and '.data/' not in n}


def proof_wheel_member_cache(mod=None):
    mod = mod or prep
    out = {}
    with tempfile.TemporaryDirectory(prefix="shimmer_seal_speed_wheels_") as tmp:
        tmp = Path(tmp)
        wheel = tmp / "wheels" / "pkg-1.0-py3-none-any.whl"
        wheel.parent.mkdir()
        cache = tmp / "cache"
        digest = make_wheel(wheel)
        first = mod.wheel_member_hashes(wheel, digest, cache)
        out["streamed equals whole"] = first == old_member_hashes(wheel) and set(first) == {"pkg/__init__.py", "pkg/big.so"}
        with patch.object(mod, "stream_member_hashes", lambda path: (_ for _ in ()).throw(AssertionError("read again"))):
            try:
                out["second call a cache hit"] = mod.wheel_member_hashes(wheel, digest, cache) == first
            except AssertionError:
                out["second call a cache hit"] = False
        changed = make_wheel(wheel, payload=b"y" * 10_000_000)
        out["changed wheel read afresh"] = mod.wheel_member_hashes(wheel, changed, cache) == old_member_hashes(wheel)
        # An entry that names another digest, another wheel or another rule is never used.
        lies = {}
        for field, value in (("wheel_sha256", "f" * 64), ("wheel", "other.whl"), ("rule", "another rule")):
            entry = cache / (changed + ".json")
            record = json.loads(entry.read_text(encoding="utf-8"))
            record[field] = value
            record["members"] = {"pkg/big.so": "0" * 64}
            entry.write_text(json.dumps(record), encoding="utf-8")
            lies[field] = mod.wheel_member_hashes(wheel, changed, cache) == old_member_hashes(wheel)
        out["entries naming another digest, wheel or rule ignored"] = all(lies.values())
        out["no partial file left"] = not list(cache.glob("*.part"))
    ok = all(out.values())
    return ok, "; ".join("%s: %s" % (k, v) for k, v in out.items())


def _module_with(module, *pairs):
    """The module's source with each (old, new) passage replaced, each found exactly once."""
    source = Path(module.__file__).read_text(encoding="utf-8")
    for old, new in zip(pairs[::2], pairs[1::2]):
        if source.count(old) != 1:
            raise RuntimeError("the passage moved, so the neutralisation cannot be applied")
        source = source.replace(old, new)
    mod = types.ModuleType(module.__name__ + "_neutralised")
    mod.__file__ = module.__file__
    exec(compile(source, module.__file__, "exec"), mod.__dict__)
    return mod


def _swap(name, **made):
    @contextlib.contextmanager
    def swap():
        original = globals()[name]
        kwargs = {k: v() for k, v in made.items()}
        globals()[name] = lambda: original(**kwargs)
        try:
            yield
        finally:
            globals()[name] = original
    return swap


PROOFS = [
    ("(A) the one-pass verifier writes the old receipt and refuses what the old one refuses", "proof_one_pass_verifier"),
    ("(B) the wheel member hashes are streamed and cached by the wheel's full digest", "proof_wheel_member_cache"),
]

NEUTRALISATIONS = [
    ("the member digest not compared", "proof_one_pass_verifier", _swap("proof_one_pass_verifier", new=lambda: _module_with(
        new_verify, "require(h.hexdigest()==entry['sha256'],'Member hash mismatch: '+member.name)", "pass"))),
    ("the whole digest not compared", "proof_one_pass_verifier", _swap("proof_one_pass_verifier", new=lambda: _module_with(
        new_verify, "require(whole==expected['sha256'] and reader.bytes==expected['bytes'],'Asset archive hash mismatch')", "pass"))),
    ("the cache keyed by the wheel's file name", "proof_wheel_member_cache", _swap("proof_wheel_member_cache", mod=lambda: _module_with(
        prep, "entry = cache_dir/(wheel_sha256 + '.json')", "entry = cache_dir/(path.name + '.json')",
        "value.get('wheel_sha256') == wheel_sha256 and value.get('wheel') == path.name", "value.get('wheel') == path.name",
        "part = entry.with_name(entry.name + '.%d.part' % os.getpid())", "part = entry.with_name(entry.name + '.part')"))),
    ("the cache entry's own record not read", "proof_wheel_member_cache", _swap("proof_wheel_member_cache", mod=lambda: _module_with(
        prep, "if (isinstance(value, dict) and value.get('wheel_sha256') == wheel_sha256", "if (isinstance(value, dict)"))),
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
    print("%s seal-speed checks: %d of %d proofs and neutralisations pass" % ("PASS" if not failures else "FAIL",
                                                                            total - failures, total))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
