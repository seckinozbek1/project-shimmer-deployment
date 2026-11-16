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
    fingerprint --part <name>=<path>[;<path>...] [--part ...] --out <B>/reference.json [--embed]
    check       --fingerprints F --candidates C --out <B>/dedup_check.json [--embed]
    within      --candidates C [C ...] --out <B>/dedup_within.json --embed
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


def fingerprint(parts, cfg=None, embed=None):
    """{part: [texts]} to hashes only: exact hashes, 8-word runs, 5-gram hashes of passages of at least the
    declared words, and (with an embedder) one unit vector per record. No text is kept."""
    t = thresholds(cfg)
    fp = {"format": FORMAT, "thresholds": t, "counts": {}, "exact": {}, "runs": {}, "grams": [], "vectors": None}
    texts, owners = [], []
    for part, items in sorted(parts.items()):
        n = 0
        for text in items:
            if _n_words(text) < t["short_min_words"]:
                continue
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
    if embed is not None and texts:
        m = _unit(embed(texts))
        fp["vectors"] = {"dim": int(m.shape[1]), "parts": owners, "rows": [[float(x) for x in r] for r in m]}
    return fp


def best_jaccard(passage_grams, index, sizes):
    """The highest 5-gram Jaccard of one passage's gram hashes with any indexed reference passage."""
    shared = {}
    for g in passage_grams:
        for i in index.get(g, ()):
            shared[i] = shared.get(i, 0) + 1
    return max((n / (sizes[i] + len(passage_grams) - n) for i, n in shared.items()), default=0.0)


def check(fp, candidates, cfg=None, embed=None):
    """Each candidate item against the reference fingerprint, by the four rules. Counts and ids only."""
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
    ref = _unit(fp["vectors"]["rows"]) if fp.get("vectors") else None
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
    p = sub.add_parser("check")
    p.add_argument("--fingerprints", required=True)
    p.add_argument("--candidates", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--embed", action="store_true")
    p = sub.add_parser("within")
    p.add_argument("--candidates", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--embed", action="store_true", required=True)
    args = ap.parse_args(argv)
    cfg = ns.load_config()
    embed = gl.shipped_embedder() if getattr(args, "embed", False) else None
    if args.cmd == "candidates":
        value = candidates_of_set(args.set_dir)
        _write(Path(args.out), value)
        print("candidates: %d items" % len(value["candidates"]))
        return 0
    if args.cmd == "fingerprint":
        parts = {}
        for spec in args.part:
            name, _, paths = spec.partition("=")
            for q in paths.split(";"):
                gl.guard(q)
                parts.setdefault(name, []).extend(text for _f, _sha, text, _short in gl.records(q))
        fp = fingerprint(parts, cfg, embed)
        _write(Path(args.out), fp)
        print("fingerprint: " + ", ".join("%s %d records" % kv for kv in sorted(fp["counts"].items())))
        return 0
    if args.cmd == "check":
        fp = json.loads(Path(args.fingerprints).read_text(encoding="utf-8"))
        out = check(fp, _candidates(args.candidates), cfg, embed)
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
