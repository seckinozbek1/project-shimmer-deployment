#!/usr/bin/env python3
"""Stage one test corpus into the three input directories, and restore afterwards.

A corpus is a directory holding `context/` (the reference material and the document
under review) and `conventions/` (the operator's rules). Staging copies those into
`input/context/` and `input/conventions/`, having first moved whatever was there
into a timestamped holding directory so nothing of the operator's is lost.

This file carries no domain vocabulary and cannot: it copies whatever it is
pointed at, and every name it handles comes from the filesystem at runtime.

    py -3.9 -X utf8 tools/stage_corpus.py --list
    py -3.9 -X utf8 tools/stage_corpus.py --corpus <name>
    py -3.9 -X utf8 tools/stage_corpus.py --restore <holding-dir>
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPORA = ROOT / "benchmark" / "corpora"
STAGED = ("context", "conventions")
HOLD_ROOT = ROOT / "output" / "staged_inputs"


def _stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def list_corpora():
    if not CORPORA.is_dir():
        return []
    return sorted(p.name for p in CORPORA.iterdir() if p.is_dir())


def _clear_into(source_dir: Path, hold_dir: Path):
    """Move every file out of source_dir into hold_dir, keeping .gitkeep in place."""
    hold_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    if not source_dir.is_dir():
        return 0
    for p in sorted(source_dir.iterdir()):
        if not p.is_file() or p.name == ".gitkeep":
            continue
        shutil.move(str(p), str(hold_dir / p.name))
        moved += 1
    return moved


def stage(name: str):
    corpus = CORPORA / name
    if not corpus.is_dir():
        raise SystemExit("no such corpus: %s (have: %s)" % (name, ", ".join(list_corpora())))
    hold = HOLD_ROOT / ("%s__replaced_by_%s" % (_stamp(), name))
    for sub in STAGED:
        moved = _clear_into(ROOT / "input" / sub, hold / sub)
        print("[stage] input/%s: moved %d file(s) aside" % (sub, moved))
    # input/operational is repopulated by the pipeline from input/context, so it is
    # only cleared, never filled from the corpus.
    moved_op = _clear_into(ROOT / "input" / "operational", hold / "operational")
    print("[stage] input/operational: moved %d file(s) aside" % moved_op)

    copied = 0
    for sub in STAGED:
        src = corpus / sub
        if not src.is_dir():
            continue
        dest = ROOT / "input" / sub
        dest.mkdir(parents=True, exist_ok=True)
        for p in sorted(src.iterdir()):
            if p.is_file():
                shutil.copy2(p, dest / p.name)
                copied += 1
                print("[stage] input/%s/%s" % (sub, p.name))
    print("[stage] staged %s: %d file(s). Previous inputs held at %s"
          % (name, copied, hold.relative_to(ROOT)))
    return hold


def restore(hold: Path):
    hold = Path(hold)
    if not hold.is_absolute():
        hold = ROOT / hold
    if not hold.is_dir():
        raise SystemExit("no such holding directory: %s" % hold)
    for sub in STAGED + ("operational",):
        src = hold / sub
        if not src.is_dir():
            continue
        dest = ROOT / "input" / sub
        for p in sorted(dest.iterdir()):
            if p.is_file() and p.name != ".gitkeep":
                p.unlink()
        for p in sorted(src.iterdir()):
            if p.is_file():
                shutil.move(str(p), str(dest / p.name))
        print("[restore] input/%s restored" % sub)
    print("[restore] done from %s" % hold)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--restore", default=None)
    a = ap.parse_args(argv)
    if a.list or (not a.corpus and not a.restore):
        for name in list_corpora():
            print(name)
        return 0
    if a.restore:
        restore(a.restore)
        return 0
    stage(a.corpus)
    return 0


if __name__ == "__main__":
    sys.exit(main())
