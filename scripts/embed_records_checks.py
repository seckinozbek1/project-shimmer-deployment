"""Proofs of the embedding route (D-507, D-510): benchmark/baselines/embed_records.py, the replay pass's
`embed-records-v1` form that embeds a records file with bge-m3 on a rented machine, one session per part, and the
laptop merge that fills a row set from three sources. No model, no GPU, no provider, no network: a stub embedder
(a deterministic vector from each text's hash) stands where bge-m3 would, in a temporary folder, beside the
real gate_leakage.fingerprint. Each of the 44 proofs is neutralise, fail, restore, pass (scripts/effect_proof.py).
`done` in the state a merge writes is the COUNT of rows that have a vector, not a prefix length.

file (8 proofs): each chunk held to its SHA-256; keys ascending; the embedding form; nothing to embed refused; the
  head sniff that tells the form; load_prompts' ascending/range check (a chunk copied over another) and its totals
  (a chunk dropped); a stay_local row's text never in a chunk or the file; the sealer's replay_declaration and the
  runner's b1_checkpoints and expected_records take the file, one reply record a chunk.
form (2): embed_form and unit rows equal gate_leakage's on awkward strings.
run (7): the batch rule, vectors in the records' order, one reply record a chunk (the runner's replay_observation
  counts them), a vector a record, finite unit vectors (the run's own call), no decision and no allowance,
  the sdpa path alone.
merge (17): the fingerprint's layout and bytes for equal vectors, the laptop's rows kept, each vector file held to
  its digest, this records file only, the laptop's key list, never into the laptop's folder, every row neither
  side gave listed, a row from two sources refused (instance and list), a listed row inside the laptop's prefix
  held to the laptop's, completeness when asked, the overlap's cosine floor, vectors held to unit finite rows
  (the merge's own call, a NaN file whose digest was fixed up), two parts never claiming the same rows, the
  mapping released before a refusal's cleanup, the temporary file and state.json registered before they are made
  (a failure injected inside open_memmap and while state.json is written leaves nothing), and cleanup removing only what the call created (an existing
  output folder, a foreign file and the laptop's folder untouched).
split (2 proofs, observed over a merge of several separate evidence folders): the rows cap and the bytes cap of a part (some
  folders, some collected tars, one per part, as one session per part leaves them).
credentials (2): the sealer's own scan finds nothing in a built file of realistic size or in bytes that spell
  `AIza...` in base64; the hex lines are short (50 characters).
offline (2): the hub's switches (environment and its own constant, with huggingface_hub imported first) are set
  before the loader runs, and a model that did not load is refused.
dispatch (2): replay_prompts.py hands the form over with the runner's own argv, and its own guard refuses another
  path, a decision or an allowance.
binding (2): the route imports nothing of tools/ and travels in the source archive with replay_prompts.py.
"""
from __future__ import annotations

import ast
import base64
import os
import contextlib
import hashlib
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "baselines"), str(ROOT / "benchmark" / "adapters")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from effect_proof import prove_effect  # noqa: E402
from common import gate_leakage as leakage  # noqa: E402
import embed_records as er  # noqa: E402
import replay_prompts  # noqa: E402

DIM = 8
CHUNK = 7
FROM_ROW = 5


ITEMS = json.dumps({"items": [{"item_id": "x1", "document_id": "d0aaaaaaaaaa", "rule_id": "CONV-X-01", "benchmark": "x"}]}).encode("utf-8")
TARGETS = json.dumps({"targets": ["d0aaaaaaaaaa.md"]}).encode("utf-8")


def patched(obj, name, value):
    return mock.patch.object(obj, name, value)


def _with_source(module, name, old, new):
    import inspect
    import textwrap
    import types
    src = textwrap.dedent(inspect.getsource(getattr(module, name)))
    olds, news = (old, new) if isinstance(old, list) else ([old], [new])
    for o_, n_ in zip(olds, news):
        assert src.count(o_) == 1, (name, o_)
        src = src.replace(o_, n_)
    namespace = dict(vars(module))
    exec(compile(src, module.__file__, "exec"), namespace)
    made = namespace[name]
    live = types.FunctionType(made.__code__, vars(module), made.__name__, made.__defaults__, made.__closure__)
    live.__kwdefaults__ = made.__kwdefaults__
    return patched(module, name, live)


def _stub_vector(text):
    d = hashlib.sha256(text.encode("utf-8")).digest()
    return [(d[i] - 127.5) / 64.0 for i in range(DIM)]


class Stub:
    """The route's embedder: embed(texts, batch_size); remembers each call's batch size and size."""
    dim = DIM
    max_seq_length = 64

    def __init__(self, drop=False, nan=False):
        self.calls, self.drop, self.nan = [], drop, nan

    def __call__(self, texts, batch_size):
        import numpy as np
        self.calls.append((batch_size, len(texts)))
        rows = np.array([_stub_vector(t) for t in texts], dtype=np.float32)
        if self.drop and len(rows) > 1:
            rows = rows[:-1]
        if self.nan and len(rows):
            rows[0, 0] = float("nan")
        return rows


def _texts():
    base = ["the quick brown fox jumps over the lazy dog number %d and then keeps running far away" % i for i in range(30)]
    base += ["the ﬁne  print of clause  %d says the supplier shall deliver  the goods without delay" % i for i in range(6)]
    base += ["a very long record %d " % i + ("lorem ipsum dolor sit amet " * 260) for i in range(3)]   # over 6,000 characters
    base += [base[0], base[1]]                                                                      # exact duplicates
    base += ["too short"]                                                                          # no record (under eight words)
    return base


def layout():
    """([(key, text)] in embedding order, stay_local rows): the fixture's distinct records as the fingerprint orders
    them, and two short ones past the laptop's rows that never leave it (the driver's stay_local)."""
    texts = {}
    for text in _texts():
        if len(text.split()) >= leakage.MIN_WORDS:
            texts.setdefault(leakage.exact_hash(text), leakage.embed_form(text))
    ordered = sorted(texts.items())
    stay = [r for r, (_k, t) in enumerate(ordered) if r >= FROM_ROW + 4 and len(t) <= er.BATCH_RULE["short_chars"]][:2]
    return ordered, stay


def fixture(td):
    """(records jsonl path in the driver's form, reference fingerprint dict, ordered [(id, text)])."""
    td = Path(td)
    part = td / "part.json"
    part.write_text(json.dumps(_texts()), encoding="utf-8")
    fp = leakage.fingerprint([("p", str(part))], embed=lambda texts: Stub()(texts, 16))
    ordered, stay = layout()
    path = td / "records.jsonl"
    path.write_text("".join(json.dumps({"row": r, "key": k, "stay_local": r in stay, "text": t},
                                       ensure_ascii=False) + chr(10) for r, (k, t) in enumerate(ordered)), encoding="utf-8")
    return path, fp, ordered


def _reference(fp):
    import numpy as np
    return np.frombuffer(base64.b64decode(fp["vectors"]["data"]), dtype=np.float32).reshape(-1, fp["vectors"]["dim"])


def _build_parts(td, records, from_row=FROM_ROW, **kw):
    """[replay_prompts.json path of each part]: build writes <dir>/partNN/replay_prompts.json."""
    out = Path(td) / "parts"
    headers = er.build(records, out, from_row=from_row, chunk=CHUNK, dim=DIM, **kw)
    return [out / ("part%02d" % h["part"]) / "replay_prompts.json" for h in headers]


def _build(td, records, from_row=FROM_ROW, **kw):
    parts = _build_parts(td, records, from_row, **kw)
    assert len(parts) == 1, len(parts)
    return parts[0]


def _caught(fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - the name of the refusal is the observation
        return "refused: " + type(exc).__name__
    return "accepted"


def _sub(td, name):
    folder = Path(td) / name
    folder.mkdir()
    return folder


def _run(td, prompts, **kw):
    out = Path(td) / "pass"
    stub = kw.pop("embedder", None) or Stub()
    try:
        m = er.run(prompts, out, embedder=stub, **kw)
        return out, stub, m
    except Exception as exc:  # noqa: BLE001
        return out, stub, "raised: " + type(exc).__name__ + ": " + str(exc)[:34]


# ---- 1: the file ----------------------------------------------------------------------------

def observe_file():
    import ordinary_final_run
    import prepare_ordinary_final_run
    with tempfile.TemporaryDirectory(prefix="shimmer_embed_file_") as td:
        records, _fp, ordered = fixture(td)
        prompts = _build(td, records)
        n = len(ordered)
        try:
            loaded = replay_prompts.load_prompts(prompts)
        except Exception as exc:  # noqa: BLE001
            return {"load": "raised: " + type(exc).__name__}
        raw = json.loads(prompts.read_text(encoding="utf-8"))
        stay = layout()[1]
        decoded = [row for pr in raw["prompts"] for row in er.decode_chunk(pr)]
        file_text = prompts.read_text(encoding="utf-8")
        leak = {"keys_in_chunks": sum(1 for _r, k, _t in decoded if k in {ordered[r][0] for r in stay}),
                "texts_in_chunks": sum(1 for _r, _k, t in decoded if t in {ordered[r][1] for r in stay}),
                "rows_in_chunks": sum(1 for r, _k, _t in decoded if r in stay),
                "keys_in_file": sum(1 for r in stay if ordered[r][0] in file_text),
                "rows_listed": raw["stay_local_rows"] == stay}
        tampered = json.loads(prompts.read_text(encoding="utf-8"))
        import gzip as _gzip
        first = tampered["prompts"][0]
        lines = _gzip.decompress(bytes.fromhex("".join(first["records_gz_hex"]))).decode("utf-8").split(chr(10))
        lines[0] = lines[0].replace('"text": "', '"text": "x', 1)       # one word changed, the count, ends and form intact
        first["records_gz_hex"] = er._pieces(_gzip.compress(chr(10).join(lines).encode("utf-8")).hex())
        bad = Path(td) / "tampered.json"
        bad.write_text(json.dumps(tampered), encoding="utf-8")
        dropped = json.loads(prompts.read_text(encoding="utf-8"))       # the last chunk gone, count and digest kept honest
        dropped["prompts"].pop()
        dropped["prompt_count"] = len(dropped["prompts"])
        dropped["chunks_sha256"] = hashlib.sha256("".join(c["records_sha256"] for c in dropped["prompts"]).encode()).hexdigest()
        short = Path(td) / "dropped.json"
        short.write_text(json.dumps(dropped), encoding="utf-8")
        doubled = json.loads(prompts.read_text(encoding="utf-8"))       # chunk 1 replaced by a copy of chunk 0 under its own id
        doubled["prompts"][1] = dict(doubled["prompts"][0], prompt_id="c999999")
        doubled["chunks_sha256"] = hashlib.sha256("".join(c["records_sha256"] for c in doubled["prompts"]).encode()).hexdigest()
        twice = Path(td) / "doubled.json"
        twice.write_text(json.dumps(doubled), encoding="utf-8")
        shuffled = Path(td) / "shuffled.jsonl"
        lines = records.read_text(encoding="utf-8").splitlines()
        r0, r1 = json.loads(lines[0]), json.loads(lines[1])
        r0["key"], r1["key"] = r1["key"], r0["key"]               # rows in sequence, keys out of order
        shuffled.write_text(chr(10).join([json.dumps(r0), json.dumps(r1)] + lines[2:]) + chr(10), encoding="utf-8")
        unformed = Path(td) / "unformed.jsonl"
        unformed.write_text(json.dumps({"id": "a", "text": "two  spaces"}) + "\n", encoding="utf-8")
        declaration = prepare_ordinary_final_run.replay_declaration(prompts.read_bytes())
        b1 = prepare_ordinary_final_run.b1_fields(ITEMS, TARGETS, [{"name": "embed", "replay": True, "args": ["--paths", "sdpa"]}], declaration)
        manifest = {"b1": b1}
        return {"is_form": replay_prompts.is_embed_records(prompts), "is_other": replay_prompts.is_embed_records(records), "leak": leak,
                "chunks": len(loaded), "from_row": raw["from_row"], "embedded": raw["embedded_records"], "total": raw["total_records"] == n,
                "head_is_schema": prompts.read_bytes().startswith(b'{"schema": "embed-records-v1"'),
                "tampered": _caught(lambda: replay_prompts.load_prompts(bad)),
                "dropped_chunk": _caught(lambda: er.load_prompts(short)), "repeated_rows": _caught(lambda: er.load_prompts(twice)),
                "shuffled": _caught(lambda: er.build(shuffled, Path(td) / "xo", chunk=CHUNK, dim=DIM)),
                "unformed": _caught(lambda: er.build(unformed, Path(td) / "yo", chunk=CHUNK, dim=DIM)),
                "empty_tail": _caught(lambda: er.build(records, Path(td) / "zo", from_row=n, chunk=CHUNK, dim=DIM)),
                "declared": declaration["prompt_count"] == len(loaded),
                "passes": [c["name"] for c in ordinary_final_run.b1_checkpoints(manifest)],
                "expected_records": ordinary_final_run.expected_records(manifest) == len(loaded),
                "replay_error": ordinary_final_run.replay_error(["--paths", "sdpa"])}


def expected_file():
    return {"is_form": True, "is_other": False, "leak": {"keys_in_chunks": 0, "texts_in_chunks": 0, "rows_in_chunks": 0, "keys_in_file": 0, "rows_listed": True}, "chunks": 5, "from_row": FROM_ROW, "embedded": 32, "total": True,
            "head_is_schema": True, "tampered": "refused: ValueError", "dropped_chunk": "refused: ValueError", "repeated_rows": "refused: ValueError", "shuffled": "refused: ValueError",
            "unformed": "refused: ValueError", "empty_tail": "refused: ValueError", "declared": True,
            "passes": ["embed"], "expected_records": True, "replay_error": None}


# ---- 2: the text form and the unit rows -----------------------------------------------------

def observe_form():
    import numpy as np
    awkward = ["  A B\tC\n ", "ﬁne ﬂow ①", "ÅNGSTRÖM  Café", "x"]
    matrix = np.array([[3.0, 4.0, 0.0], [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
    return {"form": [er.embed_form(t) == leakage.embed_form(t) for t in awkward],
            "case_kept": er.embed_form("ABC def") == "ABC def",
            "rows": bool(np.array_equal(er.unit_rows(matrix), leakage._unit_rows(matrix))),
            "zero_row": ["%.3f" % v for v in er.unit_rows(matrix)[1]]}


def expected_form():
    return {"form": [True, True, True, True], "case_kept": True, "rows": True, "zero_row": ["0.000", "0.000", "0.000"]}


# ---- 3: the run -----------------------------------------------------------------------------

def observe_run():
    import numpy as np
    import ordinary_final_run
    with tempfile.TemporaryDirectory(prefix="shimmer_embed_run_") as td:
        records, _fp, ordered = fixture(td)
        prompts = _build(td, records)
        out, stub, m = _run(td, prompts)
        stay = layout()[1]
        want = [(r, k, t) for r, (k, t) in enumerate(ordered) if r >= FROM_ROW and r not in stay]
        rows = np.concatenate([np.load(out / m_["vectors_file"]) for m_ in m["chunks"]])
        expect = er.unit_rows(np.array([_stub_vector(t) for _r, _k, t in want], dtype=np.float32))
        seen = ordinary_final_run.replay_observation(out, len(m["chunks"]), ["sdpa"])
        long_ = [c for c in stub.calls if c[0] == er.BATCH_RULE["long_batch"]]
        short_ = [c for c in stub.calls if c[0] == er.BATCH_RULE["short_batch"]]
        # integrity: a dropped vector and a non-finite one
        out2, _s2, dropped = _run(_sub(td, "d"), prompts, embedder=Stub(drop=True))
        out3, _s3, nan = _run(_sub(td, "n"), prompts, embedder=Stub(nan=True))
        return {"records": len(want), "vectors_in_order": bool(np.array_equal(rows, expect)),
                "reply_records": seen["reply_records"], "expected": seen["items"], "summary": seen["summary_written"],
                "one_each": seen["items_without_one_record"] == [], "npy_files": len(list((out / er.VECTORS_DIR).glob("*.npy"))),
                "long_batches": sum(c[1] for c in long_), "short_batch_calls_use_16": all(c[0] == 16 for c in short_) and bool(short_),
                "dropped": dropped, "dropped_measurement": (out2 / er.MEASUREMENT_FILE).exists(),
                "nan": nan, "nan_measurement": (out3 / er.MEASUREMENT_FILE).exists(),
                "path_refused": _caught(lambda: er.run(prompts, Path(td) / "q", paths=["e"], embedder=Stub())),
                "decision_refused": _caught(lambda: er.run(prompts, Path(td) / "r", decision="D-1", embedder=Stub())),
                "tokens_refused": _caught(lambda: er.run(prompts, Path(td) / "r2", max_new_tokens=5, embedder=Stub()))}


def expected_run():
    return {"records": 32, "vectors_in_order": True, "reply_records": 5, "expected": 5, "summary": True, "one_each": True,
            "npy_files": 5, "long_batches": 3, "short_batch_calls_use_16": True,
            "dropped": "raised: ValueError: the embedder returned the wrong nu", "dropped_measurement": False, "nan": "raised: RuntimeError: chunk c000005: a vector is not fin", "nan_measurement": False,
            "path_refused": "refused: ValueError", "decision_refused": "refused: ValueError", "tokens_refused": "refused: ValueError"}


# ---- 4: the merge ---------------------------------------------------------------------------

def _evidence_tar(out, tar_path):
    with tarfile.open(tar_path, "w:gz") as tar:
        for p in sorted(Path(out).rglob("*")):
            if p.is_file():
                tar.add(p, arcname="evidence/b1/embed/" + str(p.relative_to(out)).replace("\\", "/"))


def _laptop(td, fp, ordered, done, altered_row=None):
    """The laptop driver's folder: vectors.f32 pre-sized n x dim, `done` rows written, state.json."""
    import numpy as np
    ref = _reference(fp)
    n = len(ordered)
    folder = Path(td) / "laptop"
    folder.mkdir()
    full = np.zeros((n, DIM), dtype=np.float32)
    full[:done] = ref[:done]
    if altered_row is not None and altered_row < done:
        full[altered_row] = ref[altered_row] * 0.5     # a float-rounding difference only the laptop's row carries
    with open(folder / "vectors.f32", "wb") as fh:
        np.save(fh, full)            # the driver's file is a NumPy .npy
    (folder / "state.json").write_text(json.dumps({"keys_sha256": er.key_digests([i for i, _t in ordered])["concat"],
                                                   "dim": DIM, "n": n, "done": done}), encoding="utf-8")
    return folder, full


def _vec(td, name, array):
    import numpy as np
    path = Path(td) / name
    with open(path, "wb") as fh:
        np.save(fh, np.asarray(array, dtype=np.float32))
    return path


def observe_merge():
    import numpy as np
    with tempfile.TemporaryDirectory(prefix="shimmer_embed_merge_") as td:
        td = Path(td)
        records, fp, ordered = fixture(td)
        n = len(ordered)
        ref = _reference(fp)
        prompts = _build(td, records)
        out, _stub, m = _run(td, prompts)
        tar = td / "collected_evidence.tar.gz"
        _evidence_tar(out, tar)
        laptop, laptop_full = _laptop(td, fp, ordered, done=FROM_ROW + 3, altered_row=0)   # overlaps the first chunk's first rows
        merged = td / "merged"
        stay = layout()[1]
        lvec = _vec(td, "local_vectors.npy", ref[stay])
        kw = dict(local_rows=stay, local_vectors=lvec)
        state = er.merge([(tar, prompts)], laptop, merged, require_complete=True, **kw)
        got = np.load(merged / "vectors.f32")
        rest = [r for r in range(FROM_ROW + 3, n) if r not in stay]
        result = {"state": state, "n": n, "shape": list(got.shape), "dtype": str(got.dtype),
                  "laptop_row_kept": bool(np.array_equal(got[0], laptop_full[0])) and not np.array_equal(got[0], ref[0]),
                  "laptop_rows_all": bool(np.array_equal(got[:FROM_ROW + 3], laptop_full[:FROM_ROW + 3])),
                  "route_rows_equal_fingerprint": bool(np.array_equal(got[rest], ref[rest])),
                  "local_rows_from_the_laptop": bool(np.array_equal(got[stay], ref[stay]))}
        # the bytes the fingerprint writes: the merge is the whole matrix
        laptop2, _ = _laptop(_sub(td, "x"), fp, ordered, done=FROM_ROW)
        merged2 = td / "merged2"
        er.merge([(tar, prompts)], laptop2, merged2, require_complete=True, **kw)
        result["base64_equals_fingerprint_data"] = "".join(er.data_base64(merged2 / "vectors.f32", n, DIM)) == fp["vectors"]["data"]
        result["bytes_equal_fingerprint"] = np.load(merged2 / "vectors.f32").tobytes() == ref.tobytes()
        # refusals
        def merged_to(name, ev=tar, pr=prompts, lp=laptop2, **more):
            return lambda: er.merge([(ev, pr)], lp, td / name, **{"require_complete": True, **kw, **more})
        moved = td / "moved.tar.gz"
        with tarfile.open(tar) as src, tarfile.open(moved, "w:gz") as dst:
            for member in src.getmembers():
                data = src.extractfile(member).read() if member.isfile() else None
                if data is not None and member.name.endswith(".npy") and member.name.endswith("c000005.npy"):
                    data = data[:-4] + bytes([data[-4] ^ 1, data[-3], data[-2], data[-1]])
                member.size = len(data) if data is not None else 0
                dst.addfile(member, io.BytesIO(data) if data is not None else None)
        other = _build(_sub(td, "o"), records, precision="tf32")
        keyed, _ = _laptop(_sub(td, "k"), fp, ordered, done=FROM_ROW)
        (keyed / "state.json").write_text(json.dumps({"keys_sha256": "0" * 64, "dim": DIM, "n": n, "done": FROM_ROW}), encoding="utf-8")
        gap, _ = _laptop(_sub(td, "g"), fp, ordered, done=FROM_ROW - 2)
        result.update({"digest_moved": _caught(merged_to("m1", ev=moved)),
                       "other_records_file": _caught(merged_to("m2", pr=other)),
                       "other_key_list": _caught(merged_to("m3", lp=keyed)),
                       "into_laptop_folder": _caught(lambda: er.merge([(tar, prompts)], laptop2, laptop2, **kw)),
                       "gap_complete_refused": _caught(merged_to("m4", lp=gap)),
                       "missing_row_refused": _caught(lambda: er.merge([(tar, prompts)], laptop2, td / "m6", require_complete=True)),
                       "overlap_with_instance_refused": _caught(merged_to("m7", local_rows=stay + [rest[0]], local_vectors=_vec(td, "ov.npy", ref[stay + [rest[0]]]))),
                       "overlap_with_laptop_refused": _caught(merged_to("m8", local_rows=stay + [0], local_vectors=_vec(td, "ov2.npy", np.concatenate([ref[stay], ref[1:2]])))),
                       "listed_row_in_prefix_agreeing": er.merge([(tar, prompts)], laptop2, td / "m9", require_complete=True, local_rows=stay + [1], local_vectors=_vec(td, "ov3.npy", ref[stay + [1]]))["local_rows_inside_laptop_prefix"]})
        part = er.merge([(tar, prompts)], gap, td / "m5", **kw)
        result["gap_done"] = part["done"]
        result["gap_missing"] = part["missing_rows"]
        result["gap_file_shape"] = list(np.load(td / "m5" / "vectors.f32").shape)
        return result


def expected_merge():
    return {"state": {"keys_sha256": "x", "dim": DIM, "n": 39, "done": 39, "laptop_done": FROM_ROW + 3, "local_rows": 2, "local_rows_inside_laptop_prefix": 0,
                      "instance_rows_inside_laptop_prefix": 3, "overlap_compared": 3, "overlap_min_cosine": True, "missing_rows": [], "peak_working_set_mb": "x"},
            "n": 39, "shape": [39, DIM], "dtype": "float32",
            "laptop_row_kept": True, "laptop_rows_all": True, "route_rows_equal_fingerprint": True, "local_rows_from_the_laptop": True,
            "base64_equals_fingerprint_data": True, "bytes_equal_fingerprint": True,
            "digest_moved": "refused: ValueError", "other_records_file": "refused: ValueError", "other_key_list": "refused: ValueError",
            "into_laptop_folder": "refused: ValueError", "gap_complete_refused": "refused: ValueError",
            "missing_row_refused": "refused: ValueError", "overlap_with_instance_refused": "refused: ValueError",
            "overlap_with_laptop_refused": "refused: ValueError", "listed_row_in_prefix_agreeing": 1, "gap_done": 37, "gap_missing": [FROM_ROW - 2, FROM_ROW - 1],
            "gap_file_shape": [39, DIM]}


# ---- credentials, the split, the offline load ---------------------------------------------------

def observe_credentials():
    """The sealer's own scan (cloud_run_common.credential_locations, the one prepare_ordinary_final_run uses on
    replay_prompts.json): a built file of realistic size has no hit, and the bytes that spell `AIza...` in base64
    spell nothing in the hex the chunks are written in."""
    import random
    from cloud_run_common import credential_locations
    random.seed(7)
    words = [hashlib.sha256(str(i).encode()).hexdigest()[:random.randint(3, 9)] for i in range(4000)]
    with tempfile.TemporaryDirectory(prefix="shimmer_embed_cred_") as td:
        keys = sorted(hashlib.sha256(str(i).encode()).hexdigest() for i in range(16000))
        records = Path(td) / "r.jsonl"
        with open(records, "w", encoding="utf-8") as fh:
            for row, key in enumerate(keys):
                text = " ".join(random.choice(words) for _ in range(random.randint(30, 170)))
                fh.write(json.dumps({"row": row, "key": key, "stay_local": False, "text": text}) + chr(10))
        er.build(records, Path(td) / "p", chunk=er.CHUNK_RECORDS, dim=DIM)
        data = (Path(td) / "p" / "part01" / "replay_prompts.json").read_bytes()
        prefix = "AI" + "za"                                          # built at run time: no key-shaped literal in the source
        tail = "".join(("SyA1B2C3D4", "E5F6G7H8I9", "J0K1L2M3N4", "O5P6Q7"))
        crafted = base64.b64decode(prefix + tail)
        assert base64.b64encode(crafted).decode("ascii") == prefix + tail         # the bytes base64 as a Google key
        pieces = max(len(x) for c in json.loads(data.decode("utf-8"))["prompts"] for x in c["records_gz_hex"])
        return {"hex_piece_max": pieces, "megabytes_scanned": len(data) > 8_000_000, "realistic_hits": len(credential_locations(data, "replay_prompts.json")) if pieces <= 1000 else "not scanned: one long run",
                "crafted_hits": len(credential_locations(er._wire(crafted).encode(), "replay_prompts.json")),
                "lowercase_hex_only": set(er._wire(crafted)) <= set("0123456789abcdef")}


def expected_credentials():
    return {"hex_piece_max": 50, "megabytes_scanned": True, "realistic_hits": 0, "crafted_hits": 0, "lowercase_hex_only": True}


def observe_split():
    import numpy as np
    with tempfile.TemporaryDirectory(prefix="shimmer_embed_split_") as td:
        td = Path(td)
        records, fp, ordered = fixture(td)
        n = len(ordered)
        stay = layout()[1]
        ref = _reference(fp)
        by_rows = _build_parts(_sub(td, "a"), records, max_part_rows=14)
        by_bytes = _build_parts(_sub(td, "b"), records, max_part_bytes=1500)
        headers = [er.read_file(pp) for pp in by_rows]
        ranges = [(h["from_row"], h["row_end"]) for h in headers]
        pairs = []
        for i, pp in enumerate(by_rows):
            out, _s, m = _run(_sub(td, "run%d" % i), pp)
            if i % 2:
                tar = td / ("ev%d.tar.gz" % i)
                _evidence_tar(out, tar)
                pairs.append((tar, pp))
            else:
                pairs.append((out, pp))             # a part's evidence as a folder of its own, the others as collected tars
        laptop, _full = _laptop(td, fp, ordered, done=FROM_ROW)
        merged = er.merge(pairs, laptop, td / "merged", local_rows=stay, local_vectors=_vec(td, "lv.npy", ref[stay]), require_complete=True)
        whole = np.load(td / "merged" / "vectors.f32")
        return {"parts": len(by_rows), "more_parts_when_bytes_are_short": len(by_bytes) > len(by_rows),
                "tile": ranges[0][0] == FROM_ROW and ranges[-1][1] == n and all(a[1] == b[0] for a, b in zip(ranges, ranges[1:])),
                "rows_within_cap": all(h["embedded_records"] <= 14 for h in headers),
                "stay_rows_in_their_own_part": sorted(r for h in headers for r in h["stay_local_rows"]) == stay,
                "merge_done": merged["done"], "bytes_equal_fingerprint": whole.tobytes() == ref.tobytes(),
                "constants": [er.MAX_PART_ROWS, er.MAX_PART_BYTES, er.MAX_PART_ROWS * er.DIM * 4 // 1_000_000]}


def expected_split():
    return {"parts": 3, "more_parts_when_bytes_are_short": True, "tile": True, "rows_within_cap": True,
            "stay_rows_in_their_own_part": True, "merge_done": 39, "bytes_equal_fingerprint": True, "constants": [85000, 60000000, 348]}


def observe_offline():
    """shipped_embedder sets the hub's offline switches BEFORE the loader runs, and refuses a model that did not load."""
    import types
    seen = {}
    fake = types.ModuleType("embedding_store")
    fake._try_import_st = lambda: object()

    def load(st, name):
        seen["HF_HUB_OFFLINE"] = os.environ.get("HF_HUB_OFFLINE")
        seen["TRANSFORMERS_OFFLINE"] = os.environ.get("TRANSFORMERS_OFFLINE")
        return None
    fake._load_model = load
    import huggingface_hub.constants as hub_constants          # imported first: its offline flag was read at that import
    saved_constant = hub_constants.HF_HUB_OFFLINE
    hub_constants.HF_HUB_OFFLINE = False
    inner = fake._load_model

    def load_constant(st, name):
        seen["hub_constant"] = hub_constants.HF_HUB_OFFLINE
        return inner(st, name)
    fake._load_model = load_constant
    saved = {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")}
    previous = sys.modules.get("embedding_store")
    sys.modules["embedding_store"] = fake
    for k in saved:
        os.environ.pop(k, None)
    try:
        outcome = _caught(lambda: er.shipped_embedder("float32"))
    finally:
        hub_constants.HF_HUB_OFFLINE = saved_constant
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        if previous is None:
            sys.modules.pop("embedding_store", None)
        else:
            sys.modules["embedding_store"] = previous
    return {"at_load": seen, "no_fallback_model": outcome}


def expected_offline():
    return {"at_load": {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "hub_constant": True}, "no_fallback_model": "refused: RuntimeError"}


def observe_merge_integrity():
    """Vectors whose digest was fixed up to match but which are not finite; the overlap with the laptop that disagrees;
    two parts that claim the same rows."""
    import numpy as np
    with tempfile.TemporaryDirectory(prefix="shimmer_embed_integrity_") as td:
        td = Path(td)
        records, fp, ordered = fixture(td)
        n = len(ordered)
        stay = layout()[1]
        ref = _reference(fp)
        prompts = _build(td, records)
        out, _s, m = _run(td, prompts)
        kw = dict(local_rows=stay, local_vectors=_vec(td, "lv.npy", ref[stay]), require_complete=True)
        # evidence with c000005's vectors NaN, the measurement's digest corrected to match
        bad = Path(_sub(td, "bad"))
        for p_ in Path(out).rglob("*"):
            if p_.is_file():
                target = bad / p_.relative_to(out)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(p_.read_bytes())
        npy = bad / "vectors" / "c000005.npy"
        arr = np.load(npy)
        arr[0, 0] = float("nan")
        with open(npy, "wb") as fh:
            np.save(fh, arr)
        meas = json.loads((bad / er.MEASUREMENT_FILE).read_text(encoding="utf-8"))
        for c in meas["chunks"]:
            if c["prompt_id"] == "c000005":
                c["vectors_sha256"] = hashlib.sha256(npy.read_bytes()).hexdigest()
        (bad / er.MEASUREMENT_FILE).write_text(json.dumps(meas), encoding="utf-8")
        laptop, _f = _laptop(td, fp, ordered, done=FROM_ROW + 3)
        disagree, full = _laptop(_sub(td, "dg"), fp, ordered, done=FROM_ROW + 3)
        full[FROM_ROW + 1] = ref[FROM_ROW + 2]                      # a laptop row that is another record's vector
        with open(disagree / "vectors.f32", "wb") as fh:
            np.save(fh, full)
        tar = td / "ev.tar.gz"
        _evidence_tar(out, tar)
        # the mapping is released before the cleanup runs, and a refusal removes only what the call made
        import gc
        import weakref
        alive = {}
        real_open, real_collect = np.lib.format.open_memmap, gc.collect

        def tracking_open(*a, **k):
            m_ = real_open(*a, **k)
            alive["ref"] = weakref.ref(m_)
            return m_

        def tracking_collect(*a, **k):
            alive["held_at_cleanup"] = alive["ref"]() is not None if "ref" in alive else None
            return real_collect(*a, **k)
        with mock.patch.object(np.lib.format, "open_memmap", tracking_open), mock.patch.object(gc, "collect", tracking_collect):
            refused_disagree = _caught(lambda: er.merge([(tar, prompts)], disagree, td / "o4", **kw))
        existing = _sub(td, "pre")                                 # an output folder that already existed (empty): kept
        refused_existing = _caught(lambda: er.merge([(tar, prompts)], disagree, existing, **kw))
        foreign = _sub(td, "foreign")                              # not empty: refused before anything is made, nothing removed
        (foreign / "vectors.tmp.npy").write_bytes(b"someone else's")
        refused_foreign = _caught(lambda: er.merge([(tar, prompts)], laptop, foreign, **kw))
        laptop_before = sorted((f.name, f.stat().st_size) for f in Path(laptop).iterdir())
        _caught(lambda: er.merge([(tar, prompts)], disagree, laptop, **kw))
        laptop_after = sorted((f.name, f.stat().st_size) for f in Path(laptop).iterdir())
        return {"mapping_released_before_cleanup": alive.get("held_at_cleanup") is False,
                "refused_after_mapping_opened": refused_disagree, "no_file_or_folder_left": not (td / "o4").exists(),
                "existing_folder_kept": existing.is_dir() and not any(existing.iterdir()) and refused_existing.startswith("refused"),
                "foreign_file_kept": (foreign / "vectors.tmp.npy").is_file() and (foreign / "vectors.tmp.npy").read_bytes() == b"someone else's" and refused_foreign.startswith("refused"),
                "laptop_folder_untouched": laptop_before == laptop_after,
                "nan_with_good_digest": _caught(lambda: er.merge([(bad, prompts)], laptop, td / "o1", **kw)),
                "overlap_disagrees": _caught(lambda: er.merge([(tar, prompts)], disagree, td / "o2", **kw)),
                "same_rows_twice": _caught(lambda: er.merge([(tar, prompts), (tar, prompts)], laptop, td / "o3", **kw))}


def observe_injected_failures():
    """A failure injected where the call has made a file but not yet returned: inside open_memmap (after the file exists)
    and while state.json is written (after vectors.f32 and a partial state.json exist). Nothing the call made is left."""
    import numpy as np
    with tempfile.TemporaryDirectory(prefix="shimmer_embed_inject_") as td:
        td = Path(td)
        records, fp, ordered = fixture(td)
        ref = _reference(fp)
        stay = layout()[1]
        prompts = _build(td, records)
        out, _s, _m = _run(td, prompts)
        laptop, _f = _laptop(td, fp, ordered, done=FROM_ROW)
        kw = dict(local_rows=stay, local_vectors=_vec(td, "lv.npy", ref[stay]), require_complete=True)
        real_open = np.lib.format.open_memmap

        def failing_open(*a, **k):
            made = real_open(*a, **k)
            if k.get("mode") != "w+":                       # the laptop's file is opened for reading by the same function
                return made
            made.flush()                                    # the output file exists now
            del made                                        # the injection itself must not hold the mapping open
            raise OSError("injected: disk full inside open_memmap")
        first = td / "i1"
        with mock.patch.object(np.lib.format, "open_memmap", failing_open):
            refused_open = _caught(lambda: er.merge([(out, prompts)], laptop, first, **kw))
        real_write = Path.write_text

        def failing_write(self, data, *a, **k):
            if self.name == "state.json" and self.parent == second:
                real_write(self, data[:5], *a, **k)        # a partial file, then the failure
                raise OSError("injected: disk full while writing state.json")
            return real_write(self, data, *a, **k)
        second = td / "i2"
        with mock.patch.object(Path, "write_text", failing_write):
            refused_state = _caught(lambda: er.merge([(out, prompts)], laptop, second, **kw))
        return {"open_failure": refused_open, "after_open_failure": sorted(p_.name for p_ in first.rglob("*")) if first.exists() else "folder gone",
                "state_failure": refused_state, "after_state_failure": sorted(p_.name for p_ in second.rglob("*")) if second.exists() else "folder gone"}


def expected_injected_failures():
    return {"open_failure": "refused: OSError", "after_open_failure": "folder gone", "state_failure": "refused: OSError",
            "after_state_failure": "folder gone"}


def expected_merge_integrity():
    return {"mapping_released_before_cleanup": True, "refused_after_mapping_opened": "refused: ValueError",
            "no_file_or_folder_left": True, "existing_folder_kept": True, "foreign_file_kept": True, "laptop_folder_untouched": True,
            "nan_with_good_digest": "refused: ValueError", "overlap_disagrees": "refused: ValueError", "same_rows_twice": "refused: ValueError"}


# ---- 5a: the replay pass's own command -------------------------------------------------------

def observe_dispatch():
    """`replay_prompts.py run --paths sdpa` (the runner's replay argv, b1_argv) hands the file to this form."""
    import ordinary_final_run
    with tempfile.TemporaryDirectory(prefix="shimmer_embed_cli_") as td:
        records, _fp, _ordered = fixture(td)
        prompts = _build(td, records)
        (Path(td) / "replay_prompts.json").write_bytes(prompts.read_bytes())       # where the runner looks (b1_argv)
        argv = ordinary_final_run.b1_argv(td, td, Path(td) / "cli", {"name": "embed", "replay": True, "args": ["--paths", "sdpa"]})
        with patched(er, "shipped_embedder", lambda precision, model_name=er.MODEL: Stub()), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = replay_prompts.main(argv)
            refused = replay_prompts.main(["run", "--prompts", str(prompts), "--out", str(Path(td) / "cli2"), "--paths", "e"])
            refused_decision = replay_prompts.main(["run", "--prompts", str(prompts), "--out", str(Path(td) / "cli3"), "--paths", "sdpa", "--decision", "D-1"])
            refused_tokens = replay_prompts.main(["run", "--prompts", str(prompts), "--out", str(Path(td) / "cli4"), "--paths", "sdpa", "--max-new-tokens", "5"])
        return {"argv_head": argv[0], "exit": code, "refused_exit": refused, "refused_decision": refused_decision, "refused_tokens": refused_tokens,
                "reply_records": len(list((Path(td) / "cli" / "audit" / "model_replies").glob("*.json"))),
                "measurement": (Path(td) / "cli" / er.MEASUREMENT_FILE).is_file()}


def expected_dispatch():
    return {"argv_head": "run", "exit": 0, "refused_exit": 4, "refused_decision": 4, "refused_tokens": 4, "reply_records": 5, "measurement": True}


# ---- 5: nothing bound changes ---------------------------------------------------------------

def observe_binding():
    import prepare_ordinary_final_run as prep
    tree = ast.parse((ROOT / "benchmark/baselines/embed_records.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    tools = {p.stem for p in (ROOT / "tools").glob("*.py")} | {"tools"}
    names = ["benchmark/baselines/embed_records.py", "benchmark/baselines/replay_prompts.py"]
    return {"imports_nothing_of_tools": sorted(imported & tools),
            "travels_with_replay_prompts": [any(prep.named(n, p) for p in prep.ARCHIVE_EXTRAS) for n in names]}


def expected_binding():
    return {"imports_nothing_of_tools": [], "travels_with_replay_prompts": [True, True]}


def run_checks():
    proofs = [
        ("file: chunks held to their SHA-256", observe_file, expected_file, lambda: _with_source(
            er, "decode_chunk", '    if _sha(raw) != prompt["records_sha256"]:', "    if False:")),
        ("file: ascending ids", observe_file, expected_file, lambda: _with_source(
            er, "read_records", '            if previous is not None and key <= previous:', "            if False:")),
        ("file: the embedding form", observe_file, expected_file, lambda: _with_source(
            er, "read_records", '            if not local and (not row["text"] or row["text"] != embed_form(row["text"])):', "            if False:")),
        ("file: nothing to embed refused", observe_file, expected_file, lambda: _with_source(
            er, "build", '    if not state["chunks"] and not headers:', "    if False:")),
        ("file: the head tells the form", observe_file, expected_file, lambda: patched(er, "is_prompts_path", lambda path: False)),
        ("form: the fingerprint's text form", observe_form, expected_form, lambda: patched(
            er, "embed_form", lambda text: " ".join(str(text).casefold().split()))),
        ("form: unit rows", observe_form, expected_form, lambda: _with_source(
            er, "unit_rows", "    norms[norms == 0] = 1\n", "")),
        ("run: the batch rule", observe_run, expected_run, lambda: _with_source(
            er, "embed_batched", '        order["short" if len(text) <= rule["short_chars"] else "long"].append(index)',
            '        order["short"].append(index)')),
        ("run: the records' order", observe_run, expected_run, lambda: _with_source(
            er, "embed_batched", "        for i, row in zip(indexes, out):\n            rows[i] = row",
            "        for i, row in zip(indexes, out[::-1]):\n            rows[i] = row")),
        ("run: one reply record a chunk", observe_run, expected_run, lambda: patched(
            sys.modules["reply_records"] if "reply_records" in sys.modules else __import__("reply_records"), "write",
            lambda *a, **k: "unwritten")),
        ("run: a vector a record", observe_run, expected_run, lambda: _with_source(
            er, "embed_batched", "        if out.shape[0] != len(indexes):", "        if False:")),
        ("run: finite unit vectors (the run's own call)", observe_run, expected_run, lambda: _with_source(
            er, "run", "        fault = vector_fault(matrix, len(records), dim)", "        fault = None")),
        ("run: no decision and no allowance", observe_run, expected_run, lambda: _with_source(
            er, "run", "    if decision is not None or max_new_tokens is not None:", "    if False:")),
        ("run: the sdpa path alone", observe_run, expected_run, lambda: _with_source(
            er, "run", '    if list(paths) != [PATH]:', "    if False:")),
        ("merge: the fingerprint's layout and bytes for equal vectors", observe_merge, expected_merge, lambda: _with_source(
            er, "_merge", "        result[rows[take]] = array[take]", "        result[rows[take]] = array[take][::-1]")),
        ("merge: the laptop's rows kept", observe_merge, expected_merge, lambda: _with_source(
            er, "_merge", "    for r in range(0, done, step):", "    for r in range(0, 0, step):")),
        ("merge: each vector file held to its digest", observe_merge, expected_merge, lambda: _with_source(
            er, "_merge", '        if _sha(raw) != c["vectors_sha256"] or c["start"] != prompts[pid]["start"] or c["count"] != prompts[pid]["count"]:',
            "        if False:")),
        ("merge: this records file only", observe_merge, expected_merge, lambda: _with_source(
            er, "_measurement", '    if m["records_file_sha256"] != digest:', "    if False:")),
        ("merge: the laptop's key list", observe_merge, expected_merge, lambda: _with_source(
            er, "_merge", '    if state["dim"] != dim or state["n"] != n or state["keys_sha256"] not in values[0]["ids_sha256"].values():',
            '    if False:')),
        ("merge: never into the laptop's folder", observe_merge, expected_merge, lambda: _with_source(
            er, "_merge", "    if out_dir.resolve() == laptop_dir.resolve() or (out_dir.exists() and any(out_dir.iterdir())):", "    if False:")),
        ("merge: every row neither side gave is listed", observe_merge, expected_merge, lambda: _with_source(
            er, "_merge", "    missing = [int(r) for r in np.flatnonzero(~filled)]",
            "    missing = [int(r) for r in np.flatnonzero(~filled) if r >= 5]")),
        ("merge: a row from two sources refused (instance and local)", observe_merge, expected_merge, lambda: _with_source(
            er, "_merge", "            if filled[rows[take]].any() or (local_set and np.isin(rows[take], local_rows).any()):", "            if False:")),
        ("merge: a listed row inside the laptop's prefix must agree with it", observe_merge, expected_merge, lambda: _with_source(
            er, "_merge", '            if cos.min() < COSINE_FLOOR:' + chr(10) + '                raise ValueError("a listed local row',
            '            if False:' + chr(10) + '                raise ValueError("a listed local row')),
        ("build: a stay_local row's text never travels", observe_file, expected_file, lambda: _with_source(
            er, "read_records", "            yield number, key, (None if local else row[\"text\"])", "            yield number, key, row[\"text\"]")),
        ("merge: complete when asked", observe_merge, expected_merge, lambda: _with_source(
            er, "_merge", "    if require_complete and missing:", "    if False:")),
        ("dispatch: replay_prompts.py hands the form over", observe_dispatch, expected_dispatch, lambda: patched(
            replay_prompts, "is_embed_records", lambda path: False)),
        ("dispatch: sdpa alone, no decision, no allowance (replay_prompts.py's own guard)", observe_dispatch, expected_dispatch, lambda: _with_source(
            replay_prompts, "main", '''                raise ValueError("an embedding pass runs the sdpa path alone, no decision, no token allowance")''', "                pass")),
        ("file: load_prompts' ascending, no repeat, inside the range", observe_file, expected_file, lambda: _with_source(
            er, "load_prompts", '''        if rows[0][0] <= previous_row or (previous_key is not None and rows[0][1] <= previous_key) or rows[-1][0] >= value["row_end"]:''', "        if False:")),
        ("file: load_prompts' totals", observe_file, expected_file, lambda: _with_source(
            er, "load_prompts", '''    if total != value["embedded_records"] or total + len(local) != value["row_end"] - value["from_row"]:''', "    if False:")),
        ("credentials: short hex lines", observe_credentials, expected_credentials, lambda: patched(er, "HEX_LINE", 100000)),
        ("credentials: hex, never base64", observe_credentials, expected_credentials, lambda: patched(
            er, "_wire", lambda data: base64.b64encode(data).decode("ascii"))),
        ("split: the rows cap", observe_split, expected_split, lambda: _with_source(
            er, "build", '''        if state["chunks"] and (state["rows"] + len(rows) > max_part_rows or state["bytes"] + _size(c) > max_part_bytes):''',
            '''        if state["chunks"] and state["bytes"] + _size(c) > max_part_bytes:''')),
        ("split: the bytes cap", observe_split, expected_split, lambda: _with_source(
            er, "build", '''        if state["chunks"] and (state["rows"] + len(rows) > max_part_rows or state["bytes"] + _size(c) > max_part_bytes):''',
            '''        if state["chunks"] and state["rows"] + len(rows) > max_part_rows:''')),
        ("offline: the hub switches set before the load", observe_offline, expected_offline, lambda: _with_source(
            er, "shipped_embedder", '''    os.environ["HF_HUB_OFFLINE"] = "1"''', "    pass")),
        ("offline: the hub's own constant set (huggingface_hub imported first)", observe_offline, expected_offline, lambda: _with_source(
            er, "shipped_embedder", "        hub_constants.HF_HUB_OFFLINE = True", "        pass")),
        ("merge: vectors held to unit finite rows (the merge's own call)", observe_merge_integrity, expected_merge_integrity, lambda: _with_source(
            er, "_merge", '''            fault = vector_fault(array, c["count"], dim)''', "            fault = None")),
        ("merge: the mapping is released before a refusal's cleanup", observe_merge_integrity, expected_merge_integrity, lambda: _with_source(
            er, "_merge", "        result = None      # release the mapping before anything raises: Windows keeps the file open while a traceback holds it",
            "        pass")),
        ("merge: cleanup removes only what the call created", observe_merge_integrity, expected_merge_integrity, lambda: _with_source(
            er, "merge", "        for path in reversed(created):", "        for path in [Path(out_dir) / \"vectors.tmp.npy\", Path(out_dir), Path(laptop_dir) / \"state.json\"]:")),
        ("merge: the temporary file registered before it is made", observe_injected_failures, expected_injected_failures, lambda: _with_source(
            er, "_merge", ['    created.append(tmp)                     # registered BEFORE it is made: a failure inside open_memmap leaves it behind' + chr(10),
                           '    result = np.lib.format.open_memmap(tmp, mode="w+", dtype=np.float32, shape=(n, dim))'],
            ['', '    result = np.lib.format.open_memmap(tmp, mode="w+", dtype=np.float32, shape=(n, dim))' + chr(10) + '    created.append(tmp)'])),
        ("merge: state.json registered before it is written", observe_injected_failures, expected_injected_failures, lambda: _with_source(
            er, "_merge", '    created.append(out_dir / "state.json")   # registered BEFORE it is written' + chr(10), "")),
        ("merge: the overlap's cosine floor", observe_merge_integrity, expected_merge_integrity, lambda: _with_source(
            er, "_merge", "                if cos.min() < COSINE_FLOOR:", "                if False:")),
        ("merge: two parts never claim the same rows", observe_merge_integrity, expected_merge_integrity, lambda: _with_source(
            er, "_merge", ["    if any(b[0] < a[1] for a, b in zip(spans, spans[1:])):",
                          "            if filled[rows[take]].any() or (local_set and np.isin(rows[take], local_rows).any()):"],
            ["    if False:", "            if False:"])),

        ("binding: no tools import", observe_binding, expected_binding, _tools_import),
        ("binding: travels with replay_prompts.py", observe_binding, expected_binding, _extras_without_baselines),
    ]
    results = []
    for name, observe, expected, neutralise in proofs:
        if "--verbose" in sys.argv:
            print(name, flush=True)
        results.append(prove_effect(name=name, validate=lambda: er.SCHEMA == "embed-records-v1" and er.DIM == 1024 and er.MAX_PART_ROWS == 85000, observe=observe,
                                    check=lambda o=observe, e=expected, n=name: ("PASS" if _normal(o()) == _normal(e()) else "FAIL", n),
                                    neutralise=neutralise))
    return "PASS", ("%d proofs on an invented record list, a stub embedder and the real gate_leakage.fingerprint, no model and no key: "
                    "the file held to its SHA-256s and the fingerprint's text form, the sealer and the runner taking it with one reply "
                    "record a chunk, the batch rule, vectors in the records' order, integrity before the measurement, the merge "
                    "in the fingerprint's layout (bytes equal for equal vectors) with the laptop's rows kept, the overlap held to a cosine floor, and no bound controller file involved") % len(results)


def _normal(value):
    """The merge's key digest is the fixture's own: compare the rest."""
    if isinstance(value, dict) and isinstance(value.get("state"), dict):
        st = dict(value["state"], keys_sha256="x")
        if "overlap_min_cosine" in st:
            st["overlap_min_cosine"] = st["overlap_min_cosine"] is not None and st["overlap_min_cosine"] >= er.COSINE_FLOOR
        if "peak_working_set_mb" in st:
            st["peak_working_set_mb"] = "x"
        value = dict(value, state=st)
    return json.dumps(value, sort_keys=True)


@contextlib.contextmanager
def _all(*managers):
    with contextlib.ExitStack() as stack:
        for m in managers:
            stack.enter_context(m)
        yield


@contextlib.contextmanager
def _tools_import():
    """Neutralise: the route's source imports a tools module (the observation reads the file's own AST)."""
    path = ROOT / "benchmark/baselines/embed_records.py"
    original = Path.read_text

    def read_text(self, *a, **k):
        text = original(self, *a, **k)
        return text + "\nimport ordinary_final_run\n" if Path(self) == path else text
    with mock.patch.object(Path, "read_text", read_text):
        yield


@contextlib.contextmanager
def _extras_without_baselines():
    import prepare_ordinary_final_run as prep
    with patched(prep, "ARCHIVE_EXTRAS", ("benchmark/adapters/",)):
        yield


if __name__ == "__main__":
    print(run_checks())
