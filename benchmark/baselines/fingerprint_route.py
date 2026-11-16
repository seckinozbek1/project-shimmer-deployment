#!/usr/bin/env python3
"""A leakage fingerprint whose bge-m3 vectors are embedded on a rented machine (#260, EMBED-ROUTE-A).

gate_leakage.fingerprint embeds each distinct non-short record's text (embed_form) in the order of
its sorted exact hashes. This tool splits that one call in two, around the replay pass's embed
form, so the embedding runs on Lambda with no bound controller file changed:

  prepare --part name=path [--part ...] --out-dir D [--part-set <name>]
      D/skeleton.json   the fingerprint with every field but `vectors` (computed here, no model)
      D/keys.json       the vector rows' keys (sorted exact hashes), in row order
      D/records.jsonl   the route's records ({row, key, stay_local false, text}), the texts in embed_form
      D/parts/          embed_records.build's prompts file(s), each sealed as its own B1 replay bundle
      D/laptop/         an empty laptop run (done 0, zero vectors) for embed_records.merge
  finish --dir D --merged M --out F
      F                 the skeleton with `vectors` filled from embed_records.merge's M/vectors.f32, in
                        gate_leakage's own layout (`dim`, `parts` per row, `data` base64), the merge
                        required complete
`prepare` checks that its rows are exactly the texts gate_leakage.fingerprint would embed, in its order,
by running fingerprint itself with a recording embedder. Development or public material only; the
check against the gate set stays on role B's side.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
for p in (str(HERE), str(HERE.parent / "adapters")):
    if p not in sys.path:
        sys.path.insert(0, p)

from common import gate_leakage as gl  # noqa: E402
import embed_records as er  # noqa: E402


def _texts(parts):
    texts = {}
    for name, path, keys in [tuple(p) + (None,) * (3 - len(p)) for p in parts]:
        for q in [q for q in str(path).split(";") if q]:
            for _label, _sha, text, is_short in gl.records(q, keys, []):
                if not is_short:
                    texts.setdefault(gl.exact_hash(text), gl.embed_form(text))
    return texts


def prepare(parts, out_dir, part_set=None):
    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ValueError("the output folder must be new and empty")
    captured = []

    def record(texts):
        captured.extend(texts)
        return np.zeros((len(texts), er.DIM), dtype=np.float32)
    skeleton = gl.fingerprint(parts, embed=record, part_set=part_set)   # a declared set, carried into the skeleton (D-705)
    texts = _texts(parts)
    keys = sorted(texts)
    if captured != [texts[k] for k in keys]:
        raise ValueError("the rows are not the texts gate_leakage.fingerprint embeds, in its order")
    skeleton["vectors"] = None
    (out_dir / "laptop").mkdir(parents=True)
    (out_dir / "skeleton.json").write_text(json.dumps(skeleton, sort_keys=True), encoding="utf-8")
    (out_dir / "keys.json").write_text(json.dumps(keys), encoding="utf-8")
    with open(out_dir / "records.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for row, key in enumerate(keys):
            fh.write(json.dumps({"row": row, "key": key, "stay_local": False, "text": texts[key]}, ensure_ascii=False) + "\n")
    headers = er.build(out_dir / "records.jsonl", out_dir / "parts")
    blank = np.lib.format.open_memmap(out_dir / "laptop" / "vectors.f32", mode="w+", dtype=np.float32, shape=(len(keys), er.DIM))
    del blank
    (out_dir / "laptop" / "state.json").write_text(json.dumps(
        {"keys_sha256": er.key_digests(keys)["newline"], "dim": er.DIM, "n": len(keys), "done": 0}), encoding="utf-8")
    return {"rows": len(keys), "parts": len(headers), "records": skeleton["records"]}


def finish(directory, merged, out):
    directory, merged = Path(directory), Path(merged)
    skeleton = json.loads((directory / "skeleton.json").read_text(encoding="utf-8"))
    keys = json.loads((directory / "keys.json").read_text(encoding="utf-8"))
    state = json.loads((merged / "state.json").read_text(encoding="utf-8"))
    if state["n"] != len(keys) or state["done"] != len(keys) or state["keys_sha256"] != er.key_digests(keys)["newline"]:
        raise ValueError("the merged vectors are not complete for these keys")
    skeleton["vectors"] = {"dim": er.DIM, "parts": [sorted(skeleton["exact"][k]) for k in keys],
                           "data": "".join(er.data_base64(merged / "vectors.f32", len(keys), er.DIM))}
    Path(out).write_text(json.dumps(skeleton), encoding="utf-8")
    return {"rows": len(keys)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--part", action="append", required=True, help="name=path, or name=path#key,key")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--part-set", help="a declared, dated part set (gate_set.PART_SETS), never inferred")
    f = sub.add_parser("finish")
    f.add_argument("--dir", required=True)
    f.add_argument("--merged", required=True)
    f.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.command == "prepare":
        parts = []
        for spec in a.part:
            name, _, rest = spec.partition("=")
            path, _, keys = rest.partition("#")
            parts.append((name, path, keys.split(",") if keys else None))
        print(json.dumps(prepare(parts, a.out_dir, a.part_set)))
    else:
        print(json.dumps(finish(a.dir, a.merged, a.out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
