"""The content-blind choice of the S5 dry-run documents (loop plan S5 item 0.6, DS5-5).

Per benchmark, a fixed number of development documents from each length band that holds
development documents (docs/benchmarks/SELECTION.md, Length bands; PLAN below). Inside a
band the documents are sorted by word count (preregistration section 5.6, Words), ties by
opaque document id in code-point order, and k documents are taken at evenly spaced
positions of the n in the band: the 1-based positions floor(j * (n + 1) / (k + 1)) for
j = 1..k, which for k = 1 is the median (the lower median when n is even). The rule reads
each document's words, band, side and opaque id from the adapter's own `bands` command and
nothing else: no gold, no text, no source id is read by the choice or written by it.

The replacement for a chosen document (R24: a document whose B1 memory bound passes the
limit) is the next document of its band in the same order that is not chosen, else the
previous one; it is listed beside each choice, so it too is fixed before any run.

CUAD takes at most what the cut rule leaves (plan item 0.6): one band B document, else one
band A document; the band A document is listed as the fallback.

Usage (reads the B-dev development items under external/, never commits anything):
    py -3.12 -X utf8 benchmark/dryrun/choose.py --external <repo>/external --out <file>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADAPTERS = HERE.parent / "adapters"
if str(ADAPTERS) not in sys.path:
    sys.path.insert(0, str(ADAPTERS))

# documents per band, per benchmark (plan item 0.6); CUAD's band A is the fallback only
PLAN = {"contradoc": {"A": 3, "B": 2}, "scitab": {"A": 5}, "findver": {"B": 1, "C": 2, "D": 2},
        "contractnli": {"A": 2, "B": 3}, "cuad": {"B": 1}}
FALLBACK = {"cuad": {"A": 1}}
ORDER = ("contradoc", "scitab", "findver", "contractnli", "cuad")
DEVELOPMENT = "development"
# Where the B-dev development items sit under external/<name>/dev/, and each adapter's
# options for `bands` (ContraDoc's frozen assignment).
INPUTS = {"contradoc": ("ContraDoc.development.json", {"assignment": "contradoc_split_development.json"}),
          "scitab": ("sci_tab.development.json", {}),
          "findver": ("data/testmini.json", {"reports": "financial_reports"}),
          "contractnli": ("dev.json", {}),
          "cuad": ("CUAD_v1.development.json", {})}
READ_FIELDS = ("document_id", "words", "length_band", "side")   # all the choice reads


def positions(n: int, k: int) -> list:
    """The 0-based indices of k evenly spaced positions among n sorted documents."""
    if k > n:
        raise ValueError("%d documents asked from a band of %d" % (k, n))
    return [(j * (n + 1)) // (k + 1) - 1 for j in range(1, k + 1)]


def _view(row) -> dict:
    """The only fields of a bands row the choice may read."""
    return {key: row[key] for key in READ_FIELDS}


def choose_band(rows, k):
    """[(chosen row, replacement row or None)] for one band's development rows."""
    ordered = sorted((_view(r) for r in rows), key=lambda r: (int(r["words"]), str(r["document_id"])))
    picked = positions(len(ordered), k)
    out = []
    for index in picked:
        later = [i for i in range(index + 1, len(ordered)) if i not in picked]
        earlier = [i for i in range(index - 1, -1, -1) if i not in picked]
        spare = (later or earlier or [None])[0]
        out.append((dict(ordered[index], position=index + 1, band_size=len(ordered)),
                    None if spare is None else dict(ordered[spare], position=spare + 1)))
    return out


def choose(bench, rows, plan=None, fallback=None) -> list:
    """The chosen documents of one benchmark from its `bands` rows: opaque id, band, words,
    position in the band's order, band size, the replacement, and the role (chosen or
    fallback)."""
    plan = PLAN[bench] if plan is None else plan
    fallback = FALLBACK.get(bench, {}) if fallback is None else fallback
    dev = [r for r in rows if r["side"] == DEVELOPMENT]
    out = []
    for role, wanted in (("chosen", plan), ("fallback", fallback)):
        for band, k in sorted(wanted.items()):
            for row, spare in choose_band([r for r in dev if r["length_band"] == band], k):
                out.append({"benchmark": bench, "role": role, "band": band,
                            "document_id": row["document_id"], "words": int(row["words"]),
                            "position": row["position"], "band_size": row["band_size"],
                            "replacement": None if spare is None else {
                                "document_id": spare["document_id"], "words": int(spare["words"]),
                                "position": spare["position"]}})
    return out


def _adapter(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location("dryrun_adapter_" + name, ADAPTERS / name / "adapter.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bands_rows(external, name) -> list:
    """The adapter's own `bands` output for the development file (words and ids; no build)."""
    from common import cli
    file_name, options = INPUTS[name]
    dev = Path(external) / name / "dev"
    resolved = {k: str(dev / v) for k, v in options.items()}
    return cli.bands(_adapter(name), dev / file_name, **resolved)["documents"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--external", required=True, help="the folder holding <name>/dev/")
    parser.add_argument("--out", required=True, help="the list (opaque ids only), a JSON file")
    args = parser.parse_args(argv)
    chosen = []
    for name in ORDER:
        chosen.extend(choose(name, bands_rows(args.external, name)))
    result = {"rule": "loop plan S5 item 0.6 (DS5-5): per benchmark and band, sorted by words, "
                      "ties by opaque id, positions floor(j(n+1)/(k+1)); read: words, band, side, "
                      "opaque id; no gold",
              "plan": PLAN, "fallback": FALLBACK, "documents": chosen}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for row in chosen:
        print("%-11s %-8s %s %-12s words=%d pos=%d/%d" % (row["benchmark"], row["role"], row["band"],
                                                        row["document_id"], row["words"],
                                                        row["position"], row["band_size"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
