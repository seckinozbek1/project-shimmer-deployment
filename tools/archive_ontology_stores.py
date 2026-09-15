"""Archive the ontology and GNN stores as one dated file OUTSIDE the repository, then
empty them (night chain W7 a).

Everything in ontology/stores/ today came from synthetic test runs. Before the ontology
foundations change the record shape, the old contents are archived where a later reader
can still find them, and the stores start empty. The archive is verified (every file is
read back from the zip and its sha256 compared) before anything is emptied; a mismatch
stops the tool with nothing removed.

Usage:
    py -3.12 -X utf8 tools/archive_ontology_stores.py [--stores DIR] [--out-dir DIR] [--dry-run]

Defaults: stores = <repo>/ontology/stores, out-dir = <repo's parent>/shimmer-archives
(outside the repository by construction). JSONL stores are truncated to zero bytes;
derived JSON artifacts (graph.json, gnn_state.json) are removed, since their modules
rebuild them from an empty store. Prints a JSON manifest (archive path, per-file bytes,
lines and sha256) so the report can quote it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STORES = ROOT / "ontology" / "stores"
DEFAULT_OUT_DIR = ROOT.parent / "shimmer-archives"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_and_empty(stores_dir: Path, out_dir: Path, *, dry_run: bool = False) -> dict:
    stores_dir = Path(stores_dir)
    out_dir = Path(out_dir)
    if out_dir.resolve() == ROOT.resolve() or ROOT.resolve() in out_dir.resolve().parents:
        raise SystemExit("refused: the archive directory must lie outside the repository")
    files = sorted(p for p in stores_dir.iterdir() if p.is_file() and p.name != ".gitkeep") \
        if stores_dir.exists() else []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest = {"archived_at_utc": stamp, "stores_dir": str(stores_dir), "files": [],
                "archive": None, "emptied": [], "removed": [], "dry_run": dry_run}
    digests = {}
    for p in files:
        data = p.read_bytes()
        digests[p.name] = _sha256(data)
        manifest["files"].append({"name": p.name, "bytes": len(data),
                                  "lines": data.count(b"\n"), "sha256": digests[p.name]})
    if not files:
        manifest["note"] = "no store files present; nothing archived, nothing emptied"
        return manifest
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"ontology_stores_{stamp}.zip"
    if dry_run:
        manifest["archive"] = str(archive) + " (not written, dry run)"
        return manifest
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, arcname=p.name)
    # Verify before emptying: every archived member must read back to the same digest.
    with zipfile.ZipFile(archive) as z:
        for p in files:
            if _sha256(z.read(p.name)) != digests[p.name]:
                raise SystemExit(f"refused: {p.name} did not read back from {archive} "
                                 f"with the same sha256; nothing was emptied")
    manifest["archive"] = str(archive)
    manifest["archive_bytes"] = archive.stat().st_size
    for p in files:
        if p.suffix == ".jsonl":
            p.write_bytes(b"")
            manifest["emptied"].append(p.name)
        else:
            p.unlink()
            manifest["removed"].append(p.name)
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stores", default=str(DEFAULT_STORES))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    manifest = archive_and_empty(Path(a.stores), Path(a.out_dir), dry_run=a.dry_run)
    print(json.dumps(manifest, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
