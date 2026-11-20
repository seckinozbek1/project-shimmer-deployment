#!/usr/bin/env python3
"""Role B's deduplication step for the synthetic negotiation items (D-707; docs/loop/stages/NEG_SYNTH_PIPELINE.md
step 5; NEG_FINAL_ITEMS_METHOD.md section 2, Lee et al. 2022).

Four rules against the reference material (the pilot set, the development items and corpora, the gate sets and
the real items' texts), the stricter of the project's thresholds, read from config/neg_synth.json `screens.dedup`:

- exact: a record's normalised SHA-256 (gate_leakage.exact_hash) is a reference record's;
- runs: a record shares one 8-word run with the reference (gate_leakage.runs, overlap.py's rule, GATE-LEAKAGE-A);
- jaccard: a passage of at least 20 words has a 5-gram Jaccard of 0.5 or more with a reference passage (the
  scorer's normalisation, score_neg_advisor.grams);
- cosine: a record's embedding has a cosine of 0.90 or more with a reference record (bge-m3 through
  gate_leakage.shipped_embedder, or an injected embedder in the proofs).

And within the synthetic sets: two items whose whole texts have a cosine of 0.90 or more, or that share a passage
of at least 20 words exactly, keep one (the first by item id); the other is dropped and counted.

Split as gate_leakage is: `fingerprint` runs where the reference texts are and writes hashes, gram hashes and
vectors only, never a text; `check` and `within` run in role B's folder on the synthetic candidates and write
counts and item ids only.

    candidates  --set-dir <S set folder> --out <B>/candidates.json          the items' own texts, by item id
    fingerprint --part <name>=<path>[;<path>...] [--part ...] --out <B>/reference.json [--embed | VECTORS] [--sidecar]
    check       --fingerprints F --candidates C --out <B>/dedup_check.json [--embed | VECTORS]
    within      --candidates C [C ...] --out <B>/dedup_within.json (--embed | VECTORS)
    export      (--part ... | --candidates C [C ...]) --out-dir <new folder>   the embedding input alone, no model

The embedding may run on a rented machine (EMBED-ROUTE-A, the freeze's route, NEG-SYNTH-A): `export` writes the
texts the command will embed, in the one embedding form, as freeze_negotiation_set.export_records does (records.jsonl
and an empty laptop run); benchmark/baselines/embed_records.py builds the parts, the replay pass embeds them on
Lambda and `merge --require-complete` reads them back; then VECTORS, `--vectors <merged folder> --records
<records.jsonl>`, stands in for `--embed` (freeze_negotiation_set.vectors_encoder: another key list, a missing row or
a text the records do not hold is refused). The laptop never loads bge-m3 on this route.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "tools"), str(ROOT / "benchmark" / "adapters")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import neg_synth as ns  # noqa: E402
from common import gate_leakage as gl  # noqa: E402

FORMAT = "neg-synth-dedup-fingerprints-v1"
CANDIDATES_SCHEMA = "neg-synth-dedup-candidates-v1"
RULES = ("exact", "runs", "jaccard", "cosine")
GRAM_HASH_CHARS = 16


def thresholds(cfg=None):
    t = dict((cfg or ns.load_config())["screens"]["dedup"])
    if t["run_words"] != gl.overlap.SHINGLE:
        raise ValueError("the run rule is overlap.py's %d words" % gl.overlap.SHINGLE)
    return t


def _n_words(text):
    return len(str(text).split())


def gram_hashes(text):
    return sorted({hashlib.sha256(" ".join(g).encode("utf-8")).hexdigest()[:GRAM_HASH_CHARS]
                   for g in ns.sna.grams(text)})


def build_texts(build):
    """A build file's own texts: titles, every paragraph of round k and round k+1, and every quote."""
    out = [a["title"] for a in build.get("articles", [])]
    for a in build.get("articles", []):
        out += [p for p in a["text"].split("\n\n") if p.strip()]
    for text in (build.get("next_articles") or {}).values():
        out += [p for p in text.split("\n\n") if p.strip()]
    out += [p["quote"] for p in build.get("positions", [])]
    return [t.strip() for t in out if t and t.strip()]


def candidates_of_set(set_dir):
    rows = []
    for path in sorted(Path(set_dir).glob("build/*/build.json")):
        b = json.loads(path.read_text(encoding="utf-8"))
        rows.append({"id": b["item_id"], "group": b["item_id"], "texts": build_texts(b)})
    return {"schema": CANDIDATES_SCHEMA, "candidates": rows}


def _unit(rows):
    import numpy as np
    m = np.asarray(rows, dtype=np.float32)
    if m.ndim != 2:
        m = m.reshape(len(rows), -1)
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1
    return m / n


def _kept(items, t):
    return [x for x in items if _n_words(x) >= t["short_min_words"]]


def embed_inputs(parts=None, candidates=None, cfg=None):
    """The texts `fingerprint` (over `parts`) or `check` and `within` (over `candidates`) give the embedder, in
    its form, so an export holds exactly what the vectors are later asked for."""
    t = thresholds(cfg)
    texts = []
    for _part, items in sorted((parts or {}).items()):
        texts += [gl.embed_form(x) for x in _kept(items, t)]
    for c in candidates or []:
        texts += [gl.embed_form(x) for x in _kept(c["texts"], t)]
        texts.append(gl.embed_form(" ".join(c["texts"])))
    return texts


def _freeze_tools():
    import freeze_negotiation_set as fns
    return fns


def route_embedder(vectors_dir, records_path):
    """The merged vectors of the rented machine's pass, in place of bge-m3 (EMBED-ROUTE-A)."""
    return _freeze_tools().vectors_encoder(vectors_dir, records_path)


SIDECAR_SUFFIX = ".vectors.npy"


def sidecar_path(fingerprint_path):
    p = Path(fingerprint_path)
    return p.with_name(p.stem + SIDECAR_SUFFIX)


def _sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def reference_vectors(fp, base=None):
    """The fingerprint's unit rows: inline (`rows`) or, in the sidecar form, the float32 .npy beside the fingerprint,
    memory-mapped read-only and held to its recorded SHA-256 and shape (a missing, changed or misshapen file is
    refused). None when the fingerprint carries no vectors."""
    v = fp.get("vectors")
    if not v:
        return None
    if "rows" in v:
        return _unit(v["rows"])
    import numpy as np
    if base is None:
        raise ValueError("the fingerprint keeps its vectors in a sidecar: name the fingerprint's folder")
    path = Path(base) / v["file"]
    if not path.is_file():
        raise ValueError("the fingerprint's vectors file is missing: " + v["file"])
    if _sha_file(path) != v["sha256"]:
        raise ValueError("the fingerprint's vectors file differs from its recorded SHA-256")
    m = np.load(path, mmap_mode="r", allow_pickle=False)
    if m.dtype != np.float32 or m.shape != (v["count"], v["dim"]):
        raise ValueError("the fingerprint's vectors file is not (%d, %d) float32" % (v["count"], v["dim"]))
    return m


def fingerprint(parts, cfg=None, embed=None, sidecar=None):
    """{part: [texts]} to hashes only: exact hashes, 8-word runs, 5-gram hashes of passages of at least the
    declared words, and (with an embedder) one unit vector per record. No text is kept. With `sidecar` (a .npy
    path) the vectors go there as float32, one row per distinct text in the embedding form, the parts owning it
    listed per row, and the fingerprint keeps the file's name, shape and SHA-256 (a JSON list of floats would be
    gigabytes for the reference material and could not be read on the laptop)."""
    t = thresholds(cfg)
    fp = {"format": FORMAT, "thresholds": t, "counts": {}, "exact": {}, "runs": {}, "grams": [], "vectors": None}
    texts, owners = [], []
    for part, items in sorted(parts.items()):
        n = 0
        for text in _kept(items, t):
            n += 1
            fp["exact"].setdefault(gl.exact_hash(text), []).append(part)
            for r in gl.runs(text):
                fp["runs"].setdefault(r, []).append(part)
            if _n_words(text) >= t["jaccard_min_words"]:
                fp["grams"].append([part, gram_hashes(text)])
            texts.append(gl.embed_form(text))
            owners.append(part)
        fp["counts"][part] = n
    for d in (fp["exact"], fp["runs"]):
        for h in d:
            d[h] = sorted(set(d[h]))
    if embed is not None and texts and sidecar is not None:
        import numpy as np
        rows = {}
        for text, part in zip(texts, owners):
            rows.setdefault(text, set()).add(part)
        distinct = sorted(rows)
        m = np.ascontiguousarray(_unit(embed(distinct)), dtype=np.float32)
        sidecar = ns.na.outside_repository(Path(sidecar))
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        with open(sidecar, "wb") as fh:
            np.save(fh, m, allow_pickle=False)
        fp["vectors"] = {"dim": int(m.shape[1]), "count": int(m.shape[0]), "parts": [sorted(rows[x]) for x in distinct],
                         "file": sidecar.name, "sha256": _sha_file(sidecar), "dtype": "float32"}
    elif embed is not None and texts:
        m = _unit(embed(texts))
        fp["vectors"] = {"dim": int(m.shape[1]), "parts": owners, "rows": [[float(x) for x in r] for r in m]}
    if fp["vectors"] is not None:
        if getattr(embed, "route", None):
            fp["vectors"]["route"] = dict(embed.route)
    return fp


def best_jaccard(passage_grams, index, sizes):
    """The highest 5-gram Jaccard of one passage's gram hashes with any indexed reference passage."""
    shared = {}
    for g in passage_grams:
        for i in index.get(g, ()):
            shared[i] = shared.get(i, 0) + 1
    return max((n / (sizes[i] + len(passage_grams) - n) for i, n in shared.items()), default=0.0)


def check(fp, candidates, cfg=None, embed=None, base=None):
    """Each candidate item against the reference fingerprint, by the four rules. Counts and ids only. `base` is
    the fingerprint's folder, where a sidecar vectors file lies."""
    t = thresholds(cfg)
    if fp.get("format") != FORMAT:
        raise ValueError("not a synthetic dedup fingerprint")
    if fp.get("vectors") and embed is None:
        raise ValueError("the fingerprint carries vectors: the cosine rule needs the embedder")
    index, sizes = {}, []
    for i, (_part, grams) in enumerate(fp["grams"]):
        sizes.append(len(grams))
        for g in grams:
            index.setdefault(g, []).append(i)
    ref = reference_vectors(fp, base)
    hits = {r: [] for r in RULES}
    for c in candidates:
        texts = [x for x in c["texts"] if _n_words(x) >= t["short_min_words"]]
        why = set()
        if any(gl.exact_hash(x) in fp["exact"] for x in texts):
            why.add("exact")
        if any(gl.runs(x) & fp["runs"].keys() for x in texts):
            why.add("runs")
        for x in texts:
            if _n_words(x) >= t["jaccard_min_words"]:
                if best_jaccard(gram_hashes(x), index, sizes) >= t["jaccard"]:
                    why.add("jaccard")
                    break
        if ref is not None and texts:
            mine = _unit(embed([gl.embed_form(x) for x in texts]))
            if mine.shape[1] != ref.shape[1]:
                raise ValueError("the embedder's vectors are not the fingerprint's size")
            if float((mine @ ref.T).max()) >= t["cosine"]:
                why.add("cosine")
        for r in why:
            hits[r].append(c["id"])
    dropped = sorted({i for ids in hits.values() for i in ids})
    return {"candidates": len(candidates), "dropped": len(dropped), "by_rule": {r: len(hits[r]) for r in RULES},
            "dropped_ids": dropped, "ids": {r: sorted(hits[r]) for r in RULES}, "embedding": ref is not None,
            "thresholds": t}


def within(candidates, cfg=None, embed=None):
    """Near-duplicates among the synthetic items themselves: keep the first by item id, drop the other."""
    t = thresholds(cfg)
    if embed is None:
        raise ValueError("the within-set rule needs the embedder")
    rows = sorted(candidates, key=lambda c: c["id"])
    whole = _unit(embed([gl.embed_form(" ".join(c["texts"])) for c in rows])) if rows else None
    long_hashes = [{gl.exact_hash(x) for x in c["texts"] if _n_words(x) >= t["jaccard_min_words"]} for c in rows]
    dropped, pairs = set(), 0
    for i in range(len(rows)):
        if rows[i]["id"] in dropped:
            continue
        for j in range(i + 1, len(rows)):
            if rows[j]["id"] in dropped:
                continue
            if float(whole[i] @ whole[j]) >= t["within_set_cosine"] or long_hashes[i] & long_hashes[j]:
                pairs += 1
                dropped.add(rows[j]["id"])
    return {"items": len(rows), "pairs": pairs, "dropped": len(dropped), "dropped_ids": sorted(dropped)}


def _write(path, value):
    path = ns.na.outside_repository(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1) + "\n", encoding="utf-8")


def _candidates(paths):
    rows = []
    for p in paths:
        value = json.loads(Path(p).read_text(encoding="utf-8"))
        if value.get("schema") != CANDIDATES_SCHEMA:
            raise SystemExit("refused: not a synthetic candidates file")
        rows += value["candidates"]
    return rows


def _parts(specs):
    parts = {}
    for spec in specs:
        name, _, paths = spec.partition("=")
        for q in paths.split(";"):
            gl.guard(q)
            parts.setdefault(name, []).extend(text for _f, _sha, text, _short in gl.records(q))
    return parts


def _embedder(args):
    """--embed (bge-m3 on this machine), VECTORS (the rented machine's merged vectors) or neither; never both."""
    vectors, records = getattr(args, "vectors", None), getattr(args, "records", None)
    if (vectors is None) != (records is None):
        raise SystemExit("refused: --vectors and --records go together")
    if vectors is not None:
        if getattr(args, "embed", False):
            raise SystemExit("refused: --embed or --vectors, not both")
        return route_embedder(vectors, records)
    return gl.shipped_embedder() if getattr(args, "embed", False) else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("candidates")
    p.add_argument("--set-dir", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("fingerprint")
    p.add_argument("--part", action="append", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--embed", action="store_true")
    p.add_argument("--sidecar", action="store_true",
                   help="vectors to <out stem>.vectors.npy beside the fingerprint (float32, one row a distinct text)")
    p = sub.add_parser("check")
    p.add_argument("--fingerprints", required=True)
    p.add_argument("--candidates", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--embed", action="store_true")
    p = sub.add_parser("within")
    p.add_argument("--candidates", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--embed", action="store_true")
    for name in ("fingerprint", "check", "within"):
        sub.choices[name].add_argument("--vectors", help="the merged vectors folder (embed_records.py merge)")
        sub.choices[name].add_argument("--records", help="the records.jsonl `export` wrote for them")
    p = sub.add_parser("export")
    p.add_argument("--part", action="append")
    p.add_argument("--candidates", nargs="+")
    p.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)
    cfg = ns.load_config()
    if args.cmd == "export":
        if bool(args.part) == bool(args.candidates):
            raise SystemExit("refused: export takes --part or --candidates, one of them")
        out_dir = ns.na.outside_repository(Path(args.out_dir))
        if args.part:
            texts = embed_inputs(parts=_parts(args.part), cfg=cfg)
        else:
            texts = embed_inputs(candidates=_candidates(args.candidates), cfg=cfg)
        fns = _freeze_tools()
        got = fns.export_records(texts, out_dir)
        print("export: %d texts, %d distinct rows, records %s..., forecast %.1f min at the laptop GPU's rate"
              % (got["passages"], got["rows"], got["records_sha256"][:12], fns.route_forecast_minutes(got["rows"])))
        return 0
    embed = _embedder(args)
    if args.cmd == "within" and embed is None:
        raise SystemExit("refused: the within-set rule needs --embed or --vectors")
    if args.cmd == "candidates":
        value = candidates_of_set(args.set_dir)
        _write(Path(args.out), value)
        print("candidates: %d items" % len(value["candidates"]))
        return 0
    if args.cmd == "fingerprint":
        if args.sidecar and embed is None:
            raise SystemExit("refused: --sidecar holds vectors; name --embed or --vectors")
        fp = fingerprint(_parts(args.part), cfg, embed, sidecar=sidecar_path(args.out) if args.sidecar else None)
        _write(Path(args.out), fp)
        print("fingerprint: " + ", ".join("%s %d records" % kv for kv in sorted(fp["counts"].items()))
              + ("; vectors %d x %d in %s" % (fp["vectors"]["count"], fp["vectors"]["dim"], fp["vectors"]["file"])
                 if fp["vectors"] and "file" in fp["vectors"] else ""))
        return 0
    if args.cmd == "check":
        fp = json.loads(Path(args.fingerprints).read_text(encoding="utf-8"))
        out = check(fp, _candidates(args.candidates), cfg, embed, base=Path(args.fingerprints).parent)
        out["fingerprints_sha256"] = hashlib.sha256(Path(args.fingerprints).read_bytes()).hexdigest()
        _write(Path(args.out), out)
        print("check: %d candidates, %d dropped, by rule %s" % (out["candidates"], out["dropped"], out["by_rule"]))
        return 0
    if args.cmd == "within":
        out = within(_candidates(args.candidates), cfg, embed)
        _write(Path(args.out), out)
        print("within: %d items, %d pairs, %d dropped" % (out["items"], out["pairs"], out["dropped"]))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
