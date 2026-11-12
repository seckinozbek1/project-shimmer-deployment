#!/usr/bin/env python3
"""Embed a records file with bge-m3 on a rented machine, through the replay pass (D-507, D-510).

The leakage fingerprint (benchmark/adapters/common/gate_leakage.py) embeds each distinct record's
text, in the order of its sorted exact hashes, with BAAI/bge-m3 into float32 unit rows. On the
laptop that is slow; this form lets the same job ride the ordinary final runner's replay pass on a
Lambda machine, so NO bound controller file changes (the runner already runs replay_prompts.py on
the sealed replay_prompts.json, counts one reply record per prompt and asks for
replay_measurement.json; see tools/ordinary_final_run.py replay_observation).

    build  --records <records.jsonl> --out-dir <dir> [--from-row N] [--chunk N]
    run    (through replay_prompts.py: `run --prompts <file> --out <folder> --paths sdpa`)
    merge  --part "<evidence>|<prompts>" ... --laptop <the laptop run's folder> --out <new folder>
           [--local-rows rows.(json|npy) --local-vectors vectors.npy] [--require-complete]

A records file is JSON lines in embedding order (the sorted exact hashes the fingerprint embeds),
the text already in the fingerprint's own form (`embed_form`: NFKC, whitespace collapsed, case
kept): the driver's `{row, key, stay_local, text}` or a plain `{id, text}`. A stay_local row's text
never travels (its row number only, in the header); the laptop fills it.

`build` writes SEVERAL prompts files, `<dir>/partNN/replay_prompts.json`. ONE SESSION PER PART: each part is
its own B1 bundle (arm B1 with one replay pass) and its own launch (a batch of B1 entries alone cannot be
built: the controller's batch has only the paired and the b3_only forms), sealed with `--image-layers
--image-env-manifest external/image/M1_env_manifest.json` so it starts warm (the image layers need the asset copy
declaration, which the sealer writes into every exposed bundle itself). Each launch packs and downloads
a bounded evidence folder inside the controller's fixed phase timeouts (pack 180 s, download 600 s): at most MAX_PART_ROWS (85,000
rows, 85,000 x 1,024 x 4 B = 348 MB of vectors) and MAX_PART_BYTES (60 MB) of prompts file. Each
part holds a contiguous range of rows [from_row, row_end); the parts tile the rows from `--from-row`
to the end. A chunk (CHUNK_RECORDS rows) is one prompt, so the runner's one-reply-record-per-prompt
rule is this form's one-record-per-chunk rule. A chunk's records are JSON lines, gzip-compressed and
written as LOWERCASE HEX (never base64: base64 text can spell a credential pattern such as `AIza...`
and the sealer's scan refuses the bundle), each chunk held to its SHA-256.

`run` embeds every chunk with the sealed model (loaded offline, no fallback), batch rule and
precision, writes `vectors/<prompt_id>.npy` (float32 unit rows) and ONE reply record per chunk, and
`replay_measurement.json` ONLY when every chunk has one finite unit vector a record, of the declared
size. `merge` reads each part's vectors from collected evidence as bytes, one chunk at a time, checks
every digest, and fills the rows the laptop has not written, from three sources only: the laptop's
rows below its `done`, its listed local rows, and the instance's rows, one part's evidence folder at a time
(`--part` once per part, each a separate folder). One exception to "one source": a listed local row that
lies inside the laptop's written prefix is compared with the laptop's row (cosine floor) and the laptop's
kept, since the laptop's own list names rows its sequential run already wrote. Instance rows that the laptop
already has (an overlap, from building at `laptop done - 2048`) are compared by cosine and refused
below COSINE_FLOOR; the laptop's rows are kept. A refusal removes only the files this call created. The output has the laptop driver's own LAYOUT (an
`.npy` `vectors.f32` of shape (n, dim) float32, and `state.json`), byte-identical in layout to what
`gate_leakage.fingerprint` base64-encodes into `vectors.data`; the instance's vectors equal the
laptop's only within the tolerance (float rounding across cards and batch sizes), never byte for byte.
`done` in the state written is the COUNT of rows that have a vector (not a prefix length); `missing_rows`
names the rest.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import math
import os
import sys
import tarfile
import time
import unicodedata
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "scripts"

SCHEMA = "embed-records-v1"
MEASUREMENT_SCHEMA = "embed-records-measurement-v1"
MEASUREMENT_FILE = "replay_measurement.json"
PROGRESS_FILE = "embed_progress.json"
VECTORS_DIR = "vectors"
AGENT_LABEL = "EMBED_RECORDS"
PHASE = "EMBED"
PATH = "sdpa"
MODEL = "BAAI/bge-m3"
DIM = 1024
CHUNK_RECORDS = 2048
# The laptop driver's rule (D-490): batch 16 up to 6,000 characters, batch 2 above; sentence-transformers
# sorts a call's texts by length itself. float32 throughout (tf32 is a declared option, never a default).
BATCH_RULE = {"short_chars": 6000, "short_batch": 16, "long_batch": 2}
PRECISIONS = ("float32", "tf32")
UNIT_TOLERANCE = 1e-3
CHUNK_KEYS = {"prompt_id", "start", "count", "first_id", "last_id", "records_sha256", "records_gz_hex"}
MAX_PART_ROWS = 85000
MAX_PART_BYTES = 60_000_000
COSINE_FLOOR = 0.999
OVERLAP_ROWS = 2048


def _sha(data) -> str:
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def embed_form(text) -> str:
    """The one text form the fingerprint embeds (gate_leakage.embed_form): NFKC, whitespace collapsed, case kept."""
    return " ".join(unicodedata.normalize("NFKC", str(text)).split())


def unit_rows(matrix):
    """float32 unit rows (gate_leakage._unit_rows); a zero row stays zero."""
    import numpy as np
    matrix = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return (matrix / norms).astype(np.float32)


def key_digests(ids) -> dict:
    """The digests of the ordered id list in the forms a driver may have kept it in (the laptop driver's
    `keys_sha256`): the merge accepts a laptop state whose digest is any of them."""
    ids = list(ids)
    return {"newline": _sha("\n".join(ids)), "newline_trailing": _sha("".join(i + "\n" for i in ids)),
            "json": _sha(json.dumps(ids)), "json_compact": _sha(json.dumps(ids, separators=(",", ":"))),
            "concat": _sha("".join(ids))}


# ---------------------------------------------------------------------------
# build


def _wire(data: bytes) -> str:
    """The text a binary blob travels as: lowercase hex."""
    return data.hex()


HEX_LINE = 50


def _pieces(text: str) -> list:
    """The hex as short pieces, one a line in the file: the sealer's scan (a word-character run before a credential word) is
    quadratic in the length of an unbroken run of word characters, and a megabyte of hex is one such run."""
    return [text[i:i + HEX_LINE] for i in range(0, len(text), HEX_LINE)]


def _size(chunk) -> int:
    return sum(len(x) for x in chunk["records_gz_hex"])


def encode_blob(raw: bytes) -> str:
    """gzip, then lowercase hex: no credential pattern of the sealer's scan can match 0-9a-f."""
    return _wire(gzip.compress(raw, 6, mtime=0))


def decode_blob(text: str) -> bytes:
    return gzip.decompress(bytes.fromhex(text))


def _chunk(prompt_id, rows):
    """rows: [(row, key, text)] ascending by row."""
    raw = "".join(json.dumps({"row": r, "id": i, "text": t}, ensure_ascii=False) + chr(10) for r, i, t in rows).encode("utf-8")
    return {"prompt_id": prompt_id, "start": rows[0][0], "count": len(rows), "first_id": rows[0][1], "last_id": rows[-1][1],
            "records_sha256": _sha(raw), "records_gz_hex": _pieces(encode_blob(raw))}


def read_records(path):
    """(row, key, text or None) of a records file, in file order. Two line forms: the driver's
    `{"row","key","stay_local","text"}` (rows 0.. with no gap; a stay_local row carries no text on the wire, its
    text is ignored and None is yielded) and the plain `{"id","text"}`. Refuses a key out of order or repeated, a row
    out of sequence, and text that is not already in the fingerprint's form (the form is the route's one claim)."""
    previous = None
    with open(path, "r", encoding="utf-8") as fh:
        for number, line in enumerate(fh):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("line %d is not an object" % (number + 1))
            if "key" in row:
                if set(row) != {"row", "key", "stay_local", "text"} or row["row"] != number or type(row["stay_local"]) is not bool:
                    raise ValueError("line %d is not {row, key, stay_local, text} with row %d" % (number + 1, number))
                key, local = row["key"], row["stay_local"]
            else:
                if set(row) != {"id", "text"}:
                    raise ValueError("line %d is not {id, text}" % (number + 1))
                key, local = row["id"], False
            if not isinstance(key, str) or not key or not isinstance(row["text"], str):
                raise ValueError("line %d: a key or text is not a string" % (number + 1))
            if not local and (not row["text"] or row["text"] != embed_form(row["text"])):
                raise ValueError("line %d: the text is empty or not in the embedding form (NFKC, whitespace collapsed)" % (number + 1))
            if previous is not None and key <= previous:
                raise ValueError("line %d: keys must be unique and ascending, the order the fingerprint embeds in" % (number + 1))
            previous = key
            yield number, key, (None if local else row["text"])


def build(records, out_dir, *, from_row=0, chunk=CHUNK_RECORDS, precision="float32", model=MODEL, dim=DIM,
          max_part_rows=MAX_PART_ROWS, max_part_bytes=MAX_PART_BYTES):
    """Write `out_dir/partNN/replay_prompts.json` (the parts tile the rows from `from_row`); returns the headers.
    Two passes over the records file: the keys and stay_local rows first (the digests every part carries), then the
    chunks, a part closing at `max_part_rows` embedded rows or `max_part_bytes` of file."""
    if precision not in PRECISIONS:
        raise ValueError("precision is one of " + ", ".join(PRECISIONS))
    if chunk < 1 or from_row < 0 or max_part_rows < chunk:
        raise ValueError("chunk, from_row and the part size must be positive, a part holding at least one chunk")
    ids, local = [], []
    for row, key, text in read_records(records):
        ids.append(key)
        if text is None:
            local.append(row)
    n = len(ids)
    digests = key_digests(ids)
    del ids
    out_dir = Path(out_dir)
    headers, state = [], {"chunks": [], "rows": 0, "bytes": 0, "chars": 0, "start": from_row}

    def close(row_end):
        chunks = state["chunks"]
        header = {"schema": SCHEMA, "model": model, "dim": dim, "form": "gate_leakage.embed_form",
                  "normalised": "float32 unit rows", "batch_rule": BATCH_RULE, "precision": precision,
                  "sorted_ascending": True, "total_records": n, "from_row": state["start"], "row_end": row_end,
                  "part": len(headers) + 1, "embedded_records": state["rows"], "embedded_characters": state["chars"],
                  "stay_local_rows": [r for r in local if state["start"] <= r < row_end], "ids_sha256": digests,
                  "chunks_sha256": _sha("".join(c["records_sha256"] for c in chunks)), "prompt_count": len(chunks)}
        folder = out_dir / ("part%02d" % header["part"])
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / "replay_prompts.json", "w", encoding="utf-8", newline="\n") as fh:
            fh.write("{" + ", ".join(json.dumps(k) + ": " + json.dumps(v) for k, v in header.items()) + ', "prompts": [\n')
            fh.write(",\n".join(json.dumps(c, indent=0) for c in chunks))
            fh.write("\n]}\n")
        headers.append(header)
        state.update(chunks=[], rows=0, bytes=0, chars=0, start=row_end)

    def add(rows):
        c = _chunk("c%06d" % rows[0][0], rows)
        if state["chunks"] and (state["rows"] + len(rows) > max_part_rows or state["bytes"] + _size(c) > max_part_bytes):
            close(state["last_row"] + 1)
        state["chunks"].append(c)
        state["rows"] += len(rows)
        state["bytes"] += _size(c) + 300 + len(c["records_gz_hex"]) * 6
        state["chars"] += sum(len(t) for _r, _k, t in rows)
        state["last_row"] = rows[-1][0]

    rows = []
    for row, key, text in read_records(records):
        if text is None or row < from_row:
            continue
        rows.append((row, key, text))
        if len(rows) == chunk:
            add(rows)
            rows = []
    if rows:
        add(rows)
    if not state["chunks"] and not headers:
        raise ValueError("no record to embed at or after from_row %d (the file holds %d)" % (from_row, n))
    close(n)
    return headers


# ---------------------------------------------------------------------------
# read (load_prompts): every chunk against its own SHA-256


def is_prompts_path(path) -> bool:
    """True for an embed-records file: the head sniff first (the file may be 100 MB), then the schema."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(64)
    except OSError:
        return False
    return head.startswith(b'{"schema": "' + SCHEMA.encode() + b'"')


def decode_chunk(prompt):
    """[(row, id, text)] of one chunk, after its SHA-256, count, order and form are checked."""
    if set(prompt) != CHUNK_KEYS:
        raise ValueError("a chunk carries other fields than %s" % sorted(CHUNK_KEYS))
    raw = decode_blob("".join(prompt["records_gz_hex"]))
    if _sha(raw) != prompt["records_sha256"]:
        raise ValueError("a chunk does not match its SHA-256: " + str(prompt["prompt_id"]))
    rows = [json.loads(line) for line in raw.decode("utf-8").split(chr(10)) if line]
    if len(rows) != prompt["count"] or not rows or rows[0]["id"] != prompt["first_id"] or rows[-1]["id"] != prompt["last_id"]             or rows[0]["row"] != prompt["start"]:
        raise ValueError("a chunk's count or ends are wrong: " + str(prompt["prompt_id"]))
    if any(b["id"] <= a["id"] or b["row"] <= a["row"] for a, b in zip(rows, rows[1:]))             or any(r["text"] != embed_form(r["text"]) or not r["text"] for r in rows):
        raise ValueError("a chunk is out of order or not in the embedding form: " + str(prompt["prompt_id"]))
    return [(r["row"], r["id"], r["text"]) for r in rows]


def read_file(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != SCHEMA or not isinstance(value.get("prompts"), list):
        raise ValueError("not an embed records file (" + SCHEMA + ")")
    if value.get("precision") not in PRECISIONS or value.get("batch_rule") != BATCH_RULE:
        raise ValueError("the file's precision or batch rule is not one this tool runs")
    return value


def load_prompts(path):
    """The chunk list (without its decoded records), each chunk checked, ascending in row and key, no row twice,
    inside the part's row range, and together exactly the range's rows (the stay_local ones excepted)."""
    value = read_file(path)
    prompts = value["prompts"]
    if not prompts or value.get("prompt_count") != len(prompts):
        raise ValueError("the file holds no chunk, or its count is wrong")
    previous_key, previous_row, seen, total = None, value["from_row"] - 1, set(), 0
    for prompt in prompts:
        rows = decode_chunk(prompt)
        if prompt["prompt_id"] in seen:
            raise ValueError("a chunk id repeats")
        if rows[0][0] <= previous_row or (previous_key is not None and rows[0][1] <= previous_key) or rows[-1][0] >= value["row_end"]:
            raise ValueError("chunks overlap, are not ascending, or leave the part's row range")
        seen.add(prompt["prompt_id"])
        previous_row, previous_key, total = rows[-1][0], rows[-1][1], total + len(rows)
    local = [r for r in value["stay_local_rows"] if value["from_row"] <= r < value["row_end"]]
    if total != value["embedded_records"] or total + len(local) != value["row_end"] - value["from_row"]:
        raise ValueError("the chunks do not add up to the part's declared rows")
    if _sha("".join(p["records_sha256"] for p in prompts)) != value["chunks_sha256"]:
        raise ValueError("the chunk list does not match its digest")
    return prompts


# ---------------------------------------------------------------------------
# run (on the instance)


def embed_batched(embed, texts, rule=BATCH_RULE):
    """float32 unit rows of `texts`, in order: the short ones at one batch size, the long ones at another.
    `embed(list of texts, batch_size)` returns one vector a text."""
    import numpy as np
    order = {"short": [], "long": []}
    for index, text in enumerate(texts):
        order["short" if len(text) <= rule["short_chars"] else "long"].append(index)
    rows = [None] * len(texts)
    for kind in ("short", "long"):
        indexes = order[kind]
        if not indexes:
            continue
        out = unit_rows(embed([texts[i] for i in indexes], rule[kind + "_batch"]))
        if out.shape[0] != len(indexes):
            raise ValueError("the embedder returned the wrong number of vectors")
        for i, row in zip(indexes, out):
            rows[i] = row
    return np.stack(rows) if rows else np.zeros((0, 0), dtype=np.float32)


def vector_fault(matrix, count, dim):
    """None, or why a chunk's vectors fail the route's integrity rule."""
    import numpy as np
    if matrix.dtype != np.float32 or matrix.shape != (count, dim):
        return "shape %s dtype %s, not (%d, %d) float32" % (matrix.shape, matrix.dtype, count, dim)
    if not np.isfinite(matrix).all():
        return "a vector is not finite"
    if np.abs(np.linalg.norm(matrix, axis=1) - 1.0).max() > UNIT_TOLERANCE:
        return "a vector is not a unit row"
    return None


def shipped_embedder(precision, model_name=MODEL):
    """The repository's own loader (embedding_store._load_model), OFFLINE: the hub's offline switches are set before
    anything loads, so no network retry is possible, and any other model than the sealed one is refused."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    try:
        import huggingface_hub.constants as hub_constants
        hub_constants.HF_HUB_OFFLINE = True
    except ImportError:
        pass
    import embedding_store as es
    st = es._try_import_st()
    if st is None:
        raise RuntimeError("sentence-transformers is not importable: the embedding cannot run")
    model = es._load_model(st, model_name)
    if model is None or getattr(model, "_shimmer_model_id", None) != model_name:
        raise RuntimeError("the sealed model %s did not load (no fallback is accepted)" % model_name)
    if precision == "tf32":
        import torch
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    def embed(texts, batch_size):
        return model.encode(list(texts), normalize_embeddings=True, batch_size=batch_size, convert_to_numpy=True).astype("float32")
    embed.max_seq_length = getattr(model, "max_seq_length", None)
    embed.dim = model.get_sentence_embedding_dimension()
    return embed


def run(prompts_path, out, *, paths=(PATH,), decision=None, max_new_tokens=None, embedder=None, run_id=None):
    """Every chunk embedded and saved; returns the measurement (written only when every chunk passed)."""
    import numpy as np
    import bare_model
    import reply_records
    if list(paths) != [PATH]:
        raise ValueError("an embedding pass runs the %s path alone" % PATH)
    if decision is not None or max_new_tokens is not None:
        raise ValueError("an embedding pass names no decision and no token allowance")
    prompts = load_prompts(prompts_path)
    value = read_file(prompts_path)
    out = Path(out)
    (out / VECTORS_DIR).mkdir(parents=True, exist_ok=True)
    context = bare_model.RunContext(out, run_id or ("embed-" + uuid.uuid4().hex[:12]))
    started = time.perf_counter()
    embed = embedder or shipped_embedder(value["precision"], value["model"])
    dim = value["dim"]
    if getattr(embed, "dim", dim) != dim:
        raise ValueError("the model's size is not the file's declared %d" % dim)
    rows, done_records = [], 0
    for prompt in prompts:
        records = decode_chunk(prompt)
        t0 = time.perf_counter()
        matrix = embed_batched(embed, [t for _r, _i, t in records], value["batch_rule"])
        fault = vector_fault(matrix, len(records), dim)
        if fault:
            raise RuntimeError("chunk %s: %s" % (prompt["prompt_id"], fault))
        data = io.BytesIO()
        np.save(data, matrix, allow_pickle=False)
        (out / VECTORS_DIR / (prompt["prompt_id"] + ".npy")).write_bytes(data.getvalue())
        seconds = round(time.perf_counter() - t0, 3)
        row = {"prompt_id": prompt["prompt_id"], "start": prompt["start"], "count": prompt["count"],
               "vectors_file": VECTORS_DIR + "/" + prompt["prompt_id"] + ".npy", "vectors_sha256": _sha(data.getvalue()),
               "seconds": seconds, "max_characters": max(len(t) for _r, _i, t in records)}
        call = reply_records.write(context, agent=AGENT_LABEL, backend="local_embedding", model_id=value["model"],
                                   model_mode="shipped", payload=None, reply=json.dumps(row, sort_keys=True), ok=True,
                                   error="", sensitive=False, phase=PHASE, doc_id=prompt["prompt_id"])
        if not call:
            raise RuntimeError("the reply record for chunk %s could not be written" % prompt["prompt_id"])
        rows.append(dict(row, call_id=call))
        done_records += len(records)
        (out / PROGRESS_FILE).write_text(json.dumps({"done_chunks": len(rows), "chunks": len(prompts), "done_records": done_records,
                                                     "records": value["embedded_records"], "seconds": round(time.perf_counter() - started, 1)}),
                                         encoding="utf-8")
    measurement = {"schema": MEASUREMENT_SCHEMA, "model": value["model"], "dim": dim, "form": value["form"],
                   "precision": value["precision"], "batch_rule": value["batch_rule"],
                   "max_seq_length": getattr(embed, "max_seq_length", None),
                   "records_file_sha256": hashlib.sha256(Path(prompts_path).read_bytes()).hexdigest(),
                   "total_records": value["total_records"], "from_row": value["from_row"], "embedded_records": done_records,
                   "chunks": rows, "seconds": round(time.perf_counter() - started, 1), "prompts": len(prompts), "failures": 0}
    (out / MEASUREMENT_FILE).write_text(json.dumps(measurement, indent=1, sort_keys=True), encoding="utf-8")
    return measurement


# ---------------------------------------------------------------------------
# merge (on the laptop)


class _Evidence:
    """Bytes by relative path from a folder or a collected_evidence tar.gz, nothing extracted."""

    def __init__(self, path):
        self.path = Path(path)
        self.tar = tarfile.open(self.path, "r:*") if self.path.is_file() else None
        self.names = {m.name.lstrip("./"): m for m in self.tar.getmembers() if m.isfile()} if self.tar else None

    def find(self, suffix):
        if self.tar:
            return sorted(n for n in self.names if n.endswith(suffix))
        return sorted(str(p.relative_to(self.path)).replace("\\", "/") for p in self.path.rglob("*") if p.is_file() and str(p).replace("\\", "/").endswith(suffix))

    def read(self, name):
        if self.tar:
            return self.tar.extractfile(self.names[name]).read()
        return (self.path / name).read_bytes()


def _measurement(evidence, prompts_path):
    digest = hashlib.sha256(Path(prompts_path).read_bytes()).hexdigest()
    found = []
    for name in evidence.find(MEASUREMENT_FILE):
        try:
            m = json.loads(evidence.read(name))
        except ValueError:
            continue
        if isinstance(m, dict) and m.get("schema") == MEASUREMENT_SCHEMA:
            found.append((name, m))
    if len(found) != 1:
        raise ValueError("the evidence holds %d embedding measurements, not one" % len(found))
    name, m = found[0]
    if m["records_file_sha256"] != digest:
        raise ValueError("the measurement is of another records file")
    return name.rsplit("/", 1)[0] + "/" if "/" in name else "", m


def peak_memory_mb():
    """The process's measured peak working set in MB (Windows PeakWorkingSetSize, else ru_maxrss), or None."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            c = Counters()
            c.cb = ctypes.sizeof(c)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.psapi.GetProcessMemoryInfo(wintypes.HANDLE(handle), ctypes.byref(c), c.cb)
            return round(c.PeakWorkingSetSize / 1048576, 1)
        import resource
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except Exception:  # noqa: BLE001 - a measurement only
        return None


def _load_rows(path):
    import numpy as np
    path = str(path)
    if path.endswith(".npy"):
        return [int(r) for r in np.load(path, allow_pickle=False)]
    return [int(r) for r in json.loads(Path(path).read_text(encoding="utf-8"))]


GLOBAL_FIELDS = ("schema", "model", "dim", "total_records", "ids_sha256", "precision", "batch_rule")


def merge(parts, laptop_dir, out_dir, **kwargs):
    """See `_merge`. A refusal or failure removes what THIS call created (the temporary vector file, the output folder if
    it made it) and nothing else: never a file in a folder it did not create, the laptop's folder included."""
    created = []
    try:
        return _merge(parts, laptop_dir, out_dir, _created=created, **kwargs)
    except BaseException:
        import gc
        gc.collect()
        for path in reversed(created):
            try:
                path.unlink() if path.is_file() else path.rmdir()
            except OSError:
                pass
        raise


def _merge(parts, laptop_dir, out_dir, *, require_complete=False, local_rows=None, local_vectors=None, _created=None):
    """vectors.f32 (a NumPy .npy, shape (n, dim) float32, the laptop driver's own layout) and state.json in `out_dir`.
    `parts` is [(evidence, prompts_file)], one per part (each part is its own bundle, its own launch and its own evidence folder), read one chunk at a time (the evidence a folder
    or a collected_evidence.tar.gz, never extracted). Every row comes from exactly one source: the laptop's rows below
    its `done`, the listed local rows (`local_rows`: a list or a .json/.npy path; `local_vectors`: an .npy, one row
    each, in list order), or the instance's rows. A listed row inside the laptop's prefix is the one exception to "one source": it is compared with the laptop's row (cosine floor)
    and the laptop's kept; a row in two parts, or in a part and the list (past the prefix), is refused. An instance row inside the laptop's prefix is the overlap: compared with the
    laptop's row by cosine, refused below COSINE_FLOOR, the laptop's row kept. `require_complete` refuses while any row
    has no vector; without it `done` is the count of rows that have one and `missing_rows` names the rest."""
    import numpy as np
    laptop_dir, out_dir = Path(laptop_dir), Path(out_dir)
    if out_dir.resolve() == laptop_dir.resolve() or (out_dir.exists() and any(out_dir.iterdir())):
        raise ValueError("the output folder must be new and empty: the laptop's folder is never written")
    if not parts:
        raise ValueError("no part given")
    values = [{k: v for k, v in read_file(pp).items() if k != "prompts"} for _e, pp in parts]   # headers only: one part's chunks in memory at a time
    for v in values[1:]:
        if any(v[f] != values[0][f] for f in GLOBAL_FIELDS):
            raise ValueError("the parts are of different record lists, models or rules")
    spans = sorted((v["from_row"], v["row_end"]) for v in values)
    if any(b[0] < a[1] for a, b in zip(spans, spans[1:])):
        raise ValueError("two parts claim the same rows")
    n, dim = values[0]["total_records"], values[0]["dim"]
    state = json.loads((laptop_dir / "state.json").read_text(encoding="utf-8"))
    if state["dim"] != dim or state["n"] != n or state["keys_sha256"] not in values[0]["ids_sha256"].values():
        raise ValueError("the laptop run is of another record list, size or key digest")
    done = int(state["done"])
    laptop = np.load(laptop_dir / "vectors.f32", mmap_mode="r")
    if not 0 <= done <= n or laptop.shape != (n, dim) or laptop.dtype != np.float32:
        raise ValueError("the laptop run's vector file is not (n, dim) float32")
    if isinstance(local_rows, (str, Path)):
        local_rows = _load_rows(local_rows)
    local_rows = [int(r) for r in (local_rows or [])]
    extra, local_inside = None, 0
    if local_rows:
        extra = np.load(local_vectors, allow_pickle=False) if local_vectors is not None else None
        if extra is None or extra.shape != (len(local_rows), dim) or len(set(local_rows)) != len(local_rows) \
                or min(local_rows) < 0 or max(local_rows) >= n or vector_fault(extra, len(local_rows), dim):
            raise ValueError("the listed local rows and their vectors do not fit (n, dim) float32 unit rows, or repeat a row")
        inside = np.array(local_rows) < done
        if inside.any():
            # listed AND already written by the laptop: the laptop's row is kept, the listed one must agree with it
            cos = np.einsum("ij,ij->i", extra[inside], np.asarray(laptop[np.array(local_rows)[inside]]))
            if cos.min() < COSINE_FLOOR:
                raise ValueError("a listed local row disagrees with the laptop's written row (cosine %.4f)" % cos.min())
            local_inside = int(inside.sum())
            extra = extra[~inside]
            local_rows = [r for r, i in zip(local_rows, inside) if not i]
    created = _created if _created is not None else []
    if not out_dir.exists():
        out_dir.mkdir(parents=True)
        created.append(out_dir)
    tmp = out_dir / "vectors.tmp.npy"
    created.append(tmp)                     # registered BEFORE it is made: a failure inside open_memmap leaves it behind
    result = np.lib.format.open_memmap(tmp, mode="w+", dtype=np.float32, shape=(n, dim))
    try:
        filled = np.zeros(n, dtype=bool)
        filled[:done] = True
        step = 8192
        for r in range(0, done, step):
            result[r:min(done, r + step)] = laptop[r:min(done, r + step)]
        dropped, compared, worst = 0, 0, 1.0
        local_set = set(local_rows)
        for (evidence_path, prompts_path), value in zip(parts, values):
            load_prompts(prompts_path)
            evidence = _Evidence(evidence_path)
            base, m = _measurement(evidence, prompts_path)
            if m["dim"] != dim or m["total_records"] != n or m["from_row"] != value["from_row"] or m["failures"] != 0 \
                    or m["embedded_records"] != value["embedded_records"] or m["model"] != value["model"]:
                raise ValueError("the measurement does not describe this records file")
            chunks = {c["prompt_id"]: c for c in m["chunks"]}
            prompts = {pp["prompt_id"]: pp for pp in read_file(prompts_path)["prompts"]}
            if set(chunks) != set(prompts):
                raise ValueError("the measurement's chunks are not the file's")
            for pid in sorted(chunks, key=lambda q: chunks[q]["start"]):
                c = chunks[pid]
                raw = evidence.read(base + c["vectors_file"])
                if _sha(raw) != c["vectors_sha256"] or c["start"] != prompts[pid]["start"] or c["count"] != prompts[pid]["count"]:
                    raise ValueError("vectors of chunk %s do not match their recorded digest or place" % pid)
                array = np.load(io.BytesIO(raw), allow_pickle=False)
                fault = vector_fault(array, c["count"], dim)
                if fault:
                    raise ValueError("chunk %s: %s" % (pid, fault))
                rows = np.array([r for r, _i, _t in decode_chunk(prompts[pid])])
                inside = rows < done
                if inside.any():
                    # the overlap: the laptop's rows are kept, the instance's must agree with them
                    cos = np.einsum("ij,ij->i", array[inside], np.asarray(laptop[rows[inside]]))
                    dropped += int(inside.sum())
                    compared += int(inside.sum())
                    worst = min(worst, float(cos.min()))
                    if cos.min() < COSINE_FLOOR:
                        raise ValueError("the instance's rows disagree with the laptop's (cosine %.4f, floor %s)" % (cos.min(), COSINE_FLOOR))
                take = ~inside
                if filled[rows[take]].any() or (local_set and np.isin(rows[take], local_rows).any()):
                    raise ValueError("a row has a vector from two sources")
                result[rows[take]] = array[take]
                filled[rows[take]] = True
                del array, raw
        if local_rows:
            result[np.array(local_rows)] = extra
            filled[local_rows] = True
        result.flush()
    finally:
        result = None      # release the mapping before anything raises: Windows keeps the file open while a traceback holds it
    missing = [int(r) for r in np.flatnonzero(~filled)]
    if require_complete and missing:
        raise ValueError("%d row(s) have no vector from any source, the first is %d" % (len(missing), missing[0]))
    os.replace(tmp, out_dir / "vectors.f32")
    created.remove(tmp)
    created.append(out_dir / "vectors.f32")
    written = {"keys_sha256": state["keys_sha256"], "dim": dim, "n": n, "done": int(filled.sum()), "laptop_done": done,
               "local_rows": len(local_rows), "local_rows_inside_laptop_prefix": local_inside, "instance_rows_inside_laptop_prefix": dropped,
               "overlap_compared": compared, "overlap_min_cosine": round(worst, 6) if compared else None,
               "missing_rows": missing, "peak_working_set_mb": peak_memory_mb()}
    created.append(out_dir / "state.json")   # registered BEFORE it is written
    (out_dir / "state.json").write_text(json.dumps(written), encoding="utf-8")
    return written


def data_base64(vectors_path, n, dim, block=3 * 1024 * 1024):
    """The pieces of the base64 text of the first n rows of an .npy vector file (its header skipped): joined, exactly
    gate_leakage.fingerprint's `vectors.data` for the same matrix (a block is a multiple of 3 bytes)."""
    import numpy as np
    left = n * dim * 4
    with open(vectors_path, "rb") as fh:
        version = np.lib.format.read_magic(fh)
        np.lib.format._read_array_header(fh, version)
        while left:
            data = fh.read(min(block, left))
            if not data:
                raise ValueError("the vector file is shorter than n rows")
            left -= len(data)
            yield base64.b64encode(data).decode("ascii")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--records", required=True)
    b.add_argument("--out-dir", required=True)
    b.add_argument("--from-row", type=int, default=0, help="the laptop's done less %d, so the parts overlap its rows" % OVERLAP_ROWS)
    b.add_argument("--chunk", type=int, default=CHUNK_RECORDS)
    b.add_argument("--precision", choices=PRECISIONS, default="float32")
    m = sub.add_parser("merge")
    m.add_argument("--part", action="append", required=True, help="<evidence folder or tar.gz>|<replay_prompts.json>, once per bundle")
    m.add_argument("--laptop", required=True)
    m.add_argument("--out", required=True)
    m.add_argument("--require-complete", action="store_true")
    m.add_argument("--local-rows", help="the row numbers the laptop's listed-rows mode wrote (.json list or .npy)")
    m.add_argument("--local-vectors", help=".npy, one row a listed row, in list order")
    return parser


def main(argv=None):
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "build":
            headers = build(args.records, args.out_dir, from_row=args.from_row, chunk=args.chunk, precision=args.precision)
            print(json.dumps([{k: h[k] for k in ("part", "from_row", "row_end", "embedded_records", "embedded_characters", "prompt_count")}
                              for h in headers]))
        else:
            pairs = [tuple(x.split("|", 1)) for x in args.part]
            print(json.dumps(merge(pairs, args.laptop, args.out, require_complete=args.require_complete,
                                   local_rows=args.local_rows, local_vectors=args.local_vectors)))
        return 0
    except Exception as exc:
        print("embed_records stopped: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
