"""The document-level overlap check of D-S77 item 1, split so no one reads both sides.

  overlap-digest --mix <name>=<file> [--mix ...] --out <digest.json.gz>
      run by the lead on the training mixes' own row files (JSON or JSON lines; every string
      value at any depth is read): every 8-word run, lower-cased words as the judge's builder
      reads them (`tools/build_judge_training.py`, SHINGLE 8), kept only as the first 16 hex
      characters of its SHA-256, with the name of every mix that holds it and each file's
      SHA-256. No text of any mix is written.
  overlap --digest <digest.json.gz> --input <release file> [--sample <file>] --out <file>
      run by role B on a benchmark's release file through its adapter: each document's text and
      its rules' text, cut into the same runs and hashed the same way; written are counts, the
      mixes hit, and the source document ids of the documents that share a run (opaque keys or
      row numbers, never text), as an exclusion file `build --exclude` reads.

Standard library only.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path

SHINGLE = 8
HASH_CHARS = 16
_WORD = re.compile(r"\w+")


def words(text):
    return _WORD.findall(str(text).lower())


def shingle_hashes(text) -> set:
    w = words(text)
    return {hashlib.sha256(" ".join(w[i:i + SHINGLE]).encode("utf-8")).hexdigest()[:HASH_CHARS]
            for i in range(len(w) - SHINGLE + 1)}


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _rows(path):
    text = Path(path).read_text(encoding="utf-8")
    try:
        yield json.loads(text)
    except ValueError:
        for line in text.splitlines():
            if line.strip():
                yield json.loads(line)


def digest(mixes) -> dict:
    """{"shingle_words", "hash_chars", "files": {name: [sha256 ...]}, "hashes": {hash: [mix names]}}
    over `mixes`, a list of (name, path)."""
    held, files = {}, {}
    for name, path in mixes:
        files.setdefault(name, []).append(hashlib.sha256(Path(path).read_bytes()).hexdigest())
        for row in _rows(path):
            for text in _strings(row):
                for h in shingle_hashes(text):
                    names = held.setdefault(h, [])
                    if name not in names:
                        names.append(name)
    return {"shingle_words": SHINGLE, "hash_chars": HASH_CHARS, "files": files,
            "hashes": {h: sorted(n) for h, n in sorted(held.items())}}


def write_digest(data, out):
    with gzip.open(out, "wt", encoding="utf-8") as fh:
        json.dump(data, fh, sort_keys=True)


def read_digest(path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("shingle_words") != SHINGLE or data.get("hash_chars") != HASH_CHARS:
        raise ValueError("the digest was made with another run length or hash length")
    return data


def check(adapter, records, data, options=None) -> dict:
    hashes = data["hashes"]
    docs = adapter.documents(records, dict(options or {}, development=True))
    hit, by_mix = [], {}
    for doc in docs:
        found = set()
        for text in [p["text"] for p in doc["parts"]] + [r["text"] for r in doc["rules"]]:
            found |= shingle_hashes(text) & hashes.keys()
        if found:
            hit.append(str(doc["source_document_id"]))
            for name in {n for h in found for n in hashes[h]}:
                by_mix[name] = by_mix.get(name, 0) + 1
    return {"benchmark": adapter.BENCHMARK, "shingle_words": SHINGLE,
            "digest_files": data["files"], "documents_checked": len(docs),
            "documents_sharing_a_run": len(hit), "documents_by_mix": dict(sorted(by_mix.items())),
            "source_document_ids": sorted(hit)}
