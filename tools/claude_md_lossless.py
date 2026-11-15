"""Prove the CLAUDE.md slimming (issue #263, D-607) lost nothing.

Two proofs, exit 0 only when both hold:
1. every non-blank line of the full text as of BASE_COMMIT (its docs/CLAUDE_REFERENCE.md, or its
   CLAUDE.md before the slimming; first 2de5c5ef, moved to eeda384a by the 14 November merge) appears, in
   order, in docs/CLAUDE_REFERENCE.md (lines are compared with line endings removed; extra lines in the
   reference, such as its header and anchor lines, are allowed between them);
2. every named feature tag that opens a bullet in the old file (NAME-A, NAME-B, LAW-IV, ...) is
   named in the new CLAUDE.md.

Usage: py -3.12 -X utf8 tools/claude_md_lossless.py [--root DIR] [--base COMMIT]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# The base moves only at a recorded decision that changes the full text (lane/merge-1114 carried nine
# lanes' CLAUDE.md edits into the reference, 14 November 2026); the slimming's own base was 2de5c5ef.
BASE_COMMIT = "eeda384a"
TAG = re.compile(r"^- ([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)(?=[ (:])")


def old_text(root: Path, base: str) -> str:
    """The full text as of `base`: its docs/CLAUDE_REFERENCE.md where the base has one (after the slimming),
    else its CLAUDE.md (before it)."""
    for path in ("docs/CLAUDE_REFERENCE.md", "CLAUDE.md"):
        out = subprocess.run(["git", "-C", str(root), "show", f"{base}:{path}"], capture_output=True)
        if out.returncode == 0:
            return out.stdout.decode("utf-8")
    raise SystemExit(f"FAIL: no CLAUDE.md or reference at {base}")


def lines_of(text: str) -> list[str]:
    return [ln.rstrip("\r") for ln in text.split("\n")]


def missing_in_order(old: list[str], ref: list[str]) -> tuple[int, str] | None:
    """Return (old line number, text) of the first non-blank old line not found in order."""
    pos = 0
    for number, line in enumerate(old, start=1):
        if not line.strip():
            continue
        while pos < len(ref) and ref[pos] != line:
            pos += 1
        if pos >= len(ref):
            return number, line
        pos += 1
    return None


def old_tags(old: list[str]) -> list[str]:
    seen: list[str] = []
    for line in old:
        match = TAG.match(line)
        if match and match.group(1) not in seen:
            seen.append(match.group(1))
    return seen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--base", default=BASE_COMMIT)
    args = parser.parse_args(argv)
    root = Path(args.root)
    old = lines_of(old_text(root, args.base))
    ref_path = root / "docs" / "CLAUDE_REFERENCE.md"
    new_path = root / "CLAUDE.md"
    if not ref_path.exists() or not new_path.exists():
        print("FAIL: CLAUDE.md or docs/CLAUDE_REFERENCE.md missing")
        return 1
    ref = lines_of(ref_path.read_text(encoding="utf-8"))
    new_text = new_path.read_text(encoding="utf-8")
    code = 0
    gap = missing_in_order(old, ref)
    nonblank = sum(1 for ln in old if ln.strip())
    if gap:
        print(f"FAIL: full-text line {gap[0]} at the base not found in order in the reference: {gap[1][:100]}")
        code = 1
    else:
        print(f"PASS: all {nonblank} non-blank lines of the full text at {args.base} appear in order in docs/CLAUDE_REFERENCE.md")
    tags = old_tags(old)
    absent = [t for t in tags if t not in new_text]
    if absent:
        print(f"FAIL: tags not named in the new CLAUDE.md: {', '.join(absent)}")
        code = 1
    else:
        print(f"PASS: all {len(tags)} feature tags are named in the new CLAUDE.md")
    return code


if __name__ == "__main__":
    sys.exit(main())
