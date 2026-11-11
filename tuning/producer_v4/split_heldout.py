"""Split the PROCESSOR candidate's read development items into a tuning part and a held-out part
(D-S72 item 2; docs/loop/PRODUCER_TRAINING_PLAN.md section 8), before any attempt.

    py -3.12 -X utf8 tuning/producer_v4/split_heldout.py --r1 <R1's replay_prompts.json> \
        --fresh <v4 fresh_prompts.json> --out <dir>

The 52 saved failing partitions (R1's `records` set) and the 100 fresh spans are each split in
half BY DOCUMENT, by SHA-256 of SEED plus the document's identity, within each stratum (the
fresh set's source; the partitions as one), each whole document to the side holding fewer rows,
so neither half is chosen by any result and no document has rows on both sides (D-330 item 1). DEV-84 is not
split: it is the no-loss condition, read every attempt. Writes four replay files (prompts only, no
reply text), each `tune` or `heldout`, and split.json with their digests. Nothing is read with a
model here.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

SEED = "producer-success:20261108:"


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def halves(rows, document, stratum):
    """(tune, heldout), split BY DOCUMENT (D-330 item 1): within each stratum the documents are
    ordered by SHA-256 of SEED and the document's identity, and each whole document goes to the
    side holding fewer rows so far (tune on a tie), so no document has rows on both sides."""
    groups = {}
    for row in rows:
        groups.setdefault(stratum(row), {}).setdefault(document(row), []).append(row)
    tune, held = [], []
    for name in sorted(groups):
        side_t, side_h = [], []
        for doc in sorted(groups[name], key=lambda d: _sha(SEED + d)):
            (side_t if len(side_t) <= len(side_h) else side_h).extend(groups[name][doc])
        tune += side_t
        held += side_h
    return tune, held


def replay_file(prompts, label):
    out = [dict(p, prompt_id="p%04d" % (i + 1), set=label) for i, p in enumerate(prompts)]
    return {"schema": "b3-replay-prompts-v1", "prompt_count": len(out), "prompts": out}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--r1", required=True)
    parser.add_argument("--fresh", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    r1 = json.loads(Path(args.r1).read_text(encoding="utf-8"))["prompts"]
    partitions = [p for p in r1 if p.get("set") == "records"]
    fresh = [p for p in json.loads(Path(args.fresh).read_text(encoding="utf-8"))["prompts"] if p.get("checkpoint") in (None, "tuned")]
    fresh = [{k: v for k, v in p.items() if k not in ("checkpoint", "pair_of")} for p in fresh]
    if len(partitions) != 52 or len(fresh) != 100:
        raise ValueError("expected the 52 partitions and the 100 fresh spans, found %d and %d" % (len(partitions), len(fresh)))
    source = lambda p: str(p.get("doc_id", "")).split(":")[0]
    sources = {}
    for p in fresh:
        sources[p["source_call_id"]] = p["source_call_id"].split("-")[1]
    parts = {"partitions": halves(partitions, lambda p: p["doc_id"], lambda p: "all"),  # one document across runs is one document
             "fresh": halves(fresh, lambda p: "%s|%s" % (sources[p["source_call_id"]], p["doc_id"]),
                             lambda p: sources[p["source_call_id"]])}
    record = {"schema": "producer-success-split-v1", "seed": SEED, "files": {}, "strata": {}}
    for name, (tune, held) in parts.items():
        for side, rows in (("tune", tune), ("heldout", held)):
            label = "%s_%s" % (name, side)
            path = out / (label + ".json")
            path.write_text(json.dumps(replay_file(rows, label), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
            record["files"][label] = {"path": path.name, "rows": len(rows), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                      "source_call_ids": sorted(r["source_call_id"] for r in rows)}
    for side in ("tune", "heldout"):
        rows = parts["fresh"][0 if side == "tune" else 1]
        counts = {}
        for r in rows:
            counts[sources[r["source_call_id"]]] = counts.get(sources[r["source_call_id"]], 0) + 1
        record["strata"]["fresh_" + side] = counts
    for name, (tune, held) in parts.items():
        docs = {}
        for side, rows in (("tune", tune), ("heldout", held)):
            for r in rows:
                key = (sources.get(r["source_call_id"], "all"), r["doc_id"])
                docs.setdefault(key, set()).add(side)
        both = sorted(k for k, v in docs.items() if len(v) > 1)
        if both:
            raise ValueError("a document has rows on both sides: %s" % both[:3])
        record["documents"] = dict(record.get("documents", {}), **{name: {"documents": len(docs), "on_both_sides": 0,
                                   "tune": sum(1 for v in docs.values() if v == {"tune"}),
                                   "heldout": sum(1 for v in docs.values() if v == {"heldout"})}})
    (out / "split.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: {"rows": v["rows"], "sha256": v["sha256"]} for k, v in record["files"].items()}, indent=1))
    print(json.dumps(record["strata"]))
    print(json.dumps(record["documents"]))
    _ = source
    return 0


if __name__ == "__main__":
    sys.exit(main())
