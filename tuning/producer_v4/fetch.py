"""Fetch the public carrier documents the producer v4 rows are built on (sources.json), once.

    py -3.12 -X utf8 tuning/producer_v4/fetch.py --out external/s05/P1/carriers_raw

The only step that reaches the network. It reads the public rows API of each Hugging Face source
or downloads its declared file, and writes one JSON lines file per source and use
(<source>_train.jsonl, and <source>_fresh.jsonl for a fresh in-family offset): one line per
document, {source, doc_id, position, paragraphs}, the text as published, nothing else. A file
already written is kept (the fetch is not repeated over it). No key, label or answer field is kept.
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS_API = "https://datasets-server.huggingface.co/rows"
PAGE = 50


def _get(url, attempts=4):
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=180) as response:
                return response.read()
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(5 * (attempt + 1))


def _field(row, path):
    """The text under a dotted path: a string, or a list (of lists) of strings, flattened."""
    value = [row]
    for part in path.split("."):
        nxt = []
        for v in value:
            if isinstance(v, dict):
                nxt.append(v.get(part))
            elif isinstance(v, list):
                nxt += [x.get(part) if isinstance(x, dict) else None for x in v]
        value = nxt
    out = []

    def flat(v):
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, list):
            for x in v:
                flat(x)
    flat(value)
    return [t for t in out if t and t.strip()]


def paragraphs(row, fields):
    found = []
    for path in fields:
        found += _field(row, path)
    return found


def fetch_rows(spec, offset, count):
    rows = []
    while len(rows) < count:
        query = urllib.parse.urlencode({"dataset": spec["dataset"], "config": spec["config"], "split": spec["split"],
                                        "offset": offset + len(rows), "length": min(PAGE, count - len(rows))})
        page = json.loads(_get(ROWS_API + "?" + query))
        got = [r["row"] for r in page.get("rows") or []]
        if not got:
            break
        rows += got
    return rows


def fetch_file(spec):
    value = json.loads(_get(spec["url"]))
    return value if isinstance(value, list) else list(value.values())


def documents(name, spec, rows, start):
    out = []
    for i, row in enumerate(rows):
        doc = spec.get("id")
        ident = None
        if doc:
            ident = row
            for part in doc.split("."):
                ident = ident.get(part) if isinstance(ident, dict) else None
        out.append({"source": name, "doc_id": str(ident if ident is not None else "%s-%06d" % (name, start + i)),
                    "position": start + i, "paragraphs": paragraphs(row, spec["text"])})
    return [d for d in out if d["paragraphs"]]


def write(path, docs):
    path.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in docs), encoding="utf-8", newline="\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    declared = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    fresh = declared["fresh_in_family"]["offsets"]
    for name, source in declared["sources"].items():
        spec = source["fetch"]
        use = "train" if source["use"] == "train" else "fresh"
        target = out / ("%s_%s.jsonl" % (name, use))
        if not target.is_file():
            if spec["kind"] == "rows":
                docs = documents(name, spec, fetch_rows(spec, spec["offset"], spec["count"]), spec["offset"])
            else:
                docs = documents(name, spec, fetch_file(spec), 0)
            write(target, docs)
            print(name, use, len(docs), "documents")
        if name in fresh and not (out / ("%s_fresh.jsonl" % name)).is_file():
            docs = documents(name, spec, fetch_rows(spec, fresh[name], 20), fresh[name])
            write(out / ("%s_fresh.jsonl" % name), docs)
            print(name, "fresh", len(docs), "documents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
