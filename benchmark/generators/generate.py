"""Command line for the generators. Standard library only; never imports Shimmer.

    py -3.12 benchmark/generators/generate.py suite dev          # benchmark/dev_suite/generated/
    py -3.12 benchmark/generators/generate.py suite long_range   # benchmark/long_range/generated/
    py -3.12 benchmark/generators/generate.py one f3 7 --out DIR [--long-range] [--rounds 3]
    py -3.12 benchmark/generators/generate.py check DIR          # re-validate a written suite

`suite` reads the committed SEEDS.json of that suite, builds and validates every test in
memory, and only when all pass replaces the suite's generated/ folder. A failure writes
nothing.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))

import generators as gen  # noqa: E402
from generators import bundle  # noqa: E402

SUITES = {"dev": BENCH / "dev_suite", "long_range": BENCH / "long_range"}


def _suite_tests(suite):
    seeds = json.loads((SUITES[suite] / "SEEDS.json").read_text(encoding="utf-8"))
    out = []
    for entry in seeds["tests"]:
        out.append((entry["family"], int(entry["seed"]), _options(entry)))
    return out


def _options(entry):
    """The generator options a SEEDS.json entry records: long_range (family 5) and
    rounds (family 4, two or three)."""
    opts = {"long_range": True} if entry.get("long_range") else {}
    if entry.get("rounds") is not None:
        opts["rounds"] = int(entry["rounds"])
    return opts


def _test_name(test):
    folder = sorted(test)[0]
    return folder.rsplit("_", 1)[0]


def _listing(built):
    rows = []
    for (family, seed, opts), test in built:
        roles = bundle._roles(test)
        row = {"test": _test_name(test), "family": family, "seed": seed,
               "long_range": bool(opts.get("long_range"))}
        if family == "f4":
            row["rounds"] = opts.get("rounds", 2)
        row["bundles"] = {role: roles[role] for role in sorted(roles)}
        rows.append(row)
    return {"format": gen.bundle.tr.FORMAT_VERSION, "input_format_sha256": input_format_sha256(),
            "tests": rows}


def input_format_sha256():
    """The SHA-256 of the input-format draft the suite was generated against: the bytes
    of docs/INPUT_FORMAT.md as committed (CRLF read as LF, so a Windows checkout with
    autocrlf gives the hash VERSIONS.md records)."""
    data = (BENCH.parent / "docs" / "INPUT_FORMAT.md").read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _replace_generated(target):
    """Remove the suite's generated/ folder, refusing any other path."""
    target = target.resolve()
    allowed = {(SUITES[s] / "generated").resolve() for s in SUITES}
    if target not in allowed:
        raise SystemExit("refusing to remove %s" % target)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)


def cmd_suite(args):
    built = []
    for family, seed, opts in _suite_tests(args.suite):
        try:
            built.append(((family, seed, opts), gen.generate(family, seed, **opts)))
        except bundle.ValidationError as exc:
            print("FAILED, nothing written:\n%s" % exc)
            return 1
    out = SUITES[args.suite] / "generated"
    _replace_generated(out)
    n = 0
    for _, test in built:
        n += len(bundle.write_test(test, str(out / _test_name(test))))
    with open(out / "suite_listing.json", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(_listing(built), indent=2) + "\n")
    print("%d tests, %d files written under %s (input format draft %s)"
          % (len(built), n, out, input_format_sha256()))
    return 0


def cmd_one(args):
    opts = _options({"long_range": args.long_range, "rounds": args.rounds})
    try:
        test = gen.generate(args.family, args.seed, **opts)
    except bundle.ValidationError as exc:
        print("FAILED, nothing written:\n%s" % exc)
        return 1
    out = Path(args.out) / _test_name(test)
    if out.exists() and any(out.iterdir()):
        print("refusing to write into a non-empty folder: %s" % out)
        return 1
    files = bundle.write_test(test, str(out))
    print("%d files written under %s" % (len(files), out))
    return 0


def cmd_check(args):
    root = Path(args.dir)
    bad = 0
    tests = [p for p in sorted(root.iterdir()) if p.is_dir()]
    for p in tests:
        errs = bundle.validate_test(bundle.read_test(str(p)))
        if errs:
            bad += 1
            print("%s: %d problem(s)\n  %s" % (p.name, len(errs), "\n  ".join(errs[:20])))
    print("%d of %d tests valid" % (len(tests) - bad, len(tests)))
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("suite")
    s.add_argument("suite", choices=sorted(SUITES))
    o = sub.add_parser("one")
    o.add_argument("family", choices=sorted(gen.FAMILIES))
    o.add_argument("seed", type=int)
    o.add_argument("--out", required=True)
    o.add_argument("--long-range", action="store_true")
    o.add_argument("--rounds", type=int, choices=(2, 3), default=None,
                   help="family 4 only: two or three versions (default two)")
    c = sub.add_parser("check")
    c.add_argument("dir")
    args = ap.parse_args(argv)
    return {"suite": cmd_suite, "one": cmd_one, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    sys.exit(main())
