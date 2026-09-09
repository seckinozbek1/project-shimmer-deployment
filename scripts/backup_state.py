"""Backup and verify Shimmer's non-regenerable state (productization STEP 10/11).

WHY THIS EXISTS. Most of what a run produces can be rebuilt: the convention
registry is regenerated at BOOT, the embedding store rebuilds from
input/context/, the ontology graph and GNN state are recomputed every run, and
per-run output under output/runs/ is a terminal artifact. Two trees are NOT
regenerable, and until this script there was no backup mechanism for them at
all:

  durable/          learned and governance state that survives a reset:
                    cache/, global/, learnings/, reference/, governance/. The
                    governance subtree in particular is an append-only audit
                    trail (model approvals, constitution-guard decisions,
                    redaction waivers, sensitivity overrides, the LAW-IV
                    exposure ledger). Lose it and the record of what was
                    approved, waived or exposed is gone.
  ontology/stores/  the cross-run learning graph's append-master JSONL stores
                    (provisions, delta proposals). graph.json and gnn_state.json
                    are derived and rebuild themselves, but the JSONL masters do
                    not.

Three config files are copied alongside them because they are the governed
inputs a restored state has to match: config/constitution.json (append-only, the
single canonical amendment record), config/agent_registry.json (the sole source
of each agent's model) and config/pricing.json (what a call is billed at).

WHAT THIS DOES NOT DO, deliberately:
  - No compression. A plain directory copy is inspectable with a file browser
    and needs no library. There is no tar/zip dependency to go wrong.
  - No cloud, no upload, no network. The destination is a folder the operator
    names. Where that folder lives (a second disk, an external drive, a synced
    directory) is the operator's decision, not this script's.
  - No scheduler. Run it when you decide to; the RUNBOOK says when.
  - NO RESTORE COMMAND. Restore is a documented copy the operator performs
    consciously (see docs/RUNBOOK.md). A script that can overwrite live durable
    and governance state on a single command is a foot-gun: one wrong argument
    and an append-only audit trail is silently replaced by an older one.
  - No secrets. API keys live OUTSIDE the repository by design and are never
    read, copied, printed or referenced by value here.

USAGE

    python scripts/backup_state.py --dest D:/shimmer_backups
    python scripts/backup_state.py --dest D:/shimmer_backups --label pre_upgrade
    python scripts/backup_state.py --verify D:/shimmer_backups/shimmer_backup_20260903_181500

A backup is a timestamped folder under --dest holding the trees above plus
MANIFEST.json, which records a SHA-256 and a byte length for every copied file.
--verify re-hashes every file the manifest lists and reports MODIFIED, MISSING
and EXTRA entries. Exit codes: 0 intact / backup written, 1 verification failed,
2 a usage or filesystem error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MANIFEST_NAME = "MANIFEST.json"
MANIFEST_SCHEMA = "shimmer_backup_manifest/v1"
BACKUP_PREFIX = "shimmer_backup_"

# The trees copied whole, relative to the project root. Order is the order they
# appear in the manifest.
BACKUP_TREES = (
    "durable",
    "ontology/stores",
)

# The governed config files copied individually (the rest of config/ is either
# regenerated at BOOT or operator-edited source under version control).
BACKUP_FILES = (
    "config/constitution.json",
    "config/agent_registry.json",
    "config/pricing.json",
)

_HASH_CHUNK = 1024 * 1024


def sha256_of(path: Path) -> str:
    """Streaming SHA-256, so a large embedding store does not have to fit in
    memory. Returns the lowercase hex digest."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(_HASH_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _iter_files(base: Path):
    """Every file under `base`, sorted, deterministic across platforms."""
    if not base.exists():
        return
    for path in sorted(p for p in base.rglob("*") if p.is_file()):
        yield path


def create_backup(project_root, dest, *, label: str = "") -> dict:
    """Copy the non-regenerable trees and the governed config files from
    `project_root` into a new timestamped folder under `dest`, write
    MANIFEST.json, and return a summary dict:

        {"backup_dir": str, "manifest_path": str, "file_count": int,
         "total_bytes": int, "missing_sources": [str], "created_at": str}

    `missing_sources` names any configured tree or file that did not exist in
    the source (an empty repo, or a store that has never been written). That is
    recorded rather than treated as an error, so a first backup on a fresh clone
    still succeeds and says what was not there.

    Never writes into `project_root`: this function only reads from it.
    """
    project_root = Path(project_root).resolve()
    dest = Path(dest)
    if not project_root.is_dir():
        raise NotADirectoryError(f"project root not found: {project_root}")
    dest.mkdir(parents=True, exist_ok=True)

    name = BACKUP_PREFIX + _now_stamp() + (f"_{label}" if label else "")
    backup_dir = dest / name
    if backup_dir.exists():
        # Same-second collision, or a re-run with the same label. Never merge
        # into an existing backup: a mixed folder would verify against a
        # manifest that does not describe it.
        raise FileExistsError(f"backup folder already exists: {backup_dir}")
    backup_dir.mkdir(parents=True)

    entries = []
    missing = []

    for rel_tree in BACKUP_TREES:
        src_base = project_root / rel_tree
        if not src_base.is_dir():
            missing.append(rel_tree)
            continue
        for src in _iter_files(src_base):
            rel = src.relative_to(project_root).as_posix()
            dst = backup_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            entries.append({"path": rel, "bytes": dst.stat().st_size,
                            "sha256": sha256_of(dst)})

    for rel_file in BACKUP_FILES:
        src = project_root / rel_file
        if not src.is_file():
            missing.append(rel_file)
            continue
        dst = backup_dir / rel_file
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        entries.append({"path": rel_file, "bytes": dst.stat().st_size,
                        "sha256": sha256_of(dst)})

    created_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "created_at": created_at,
        "project_root": str(project_root),
        "label": label,
        "trees": list(BACKUP_TREES),
        "files": list(BACKUP_FILES),
        "missing_sources": missing,
        "file_count": len(entries),
        "total_bytes": sum(e["bytes"] for e in entries),
        "entries": entries,
    }
    manifest_path = backup_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                             encoding="utf-8")
    return {
        "backup_dir": str(backup_dir),
        "manifest_path": str(manifest_path),
        "file_count": manifest["file_count"],
        "total_bytes": manifest["total_bytes"],
        "missing_sources": missing,
        "created_at": created_at,
    }


def verify_backup(backup_dir) -> dict:
    """Re-hash every file MANIFEST.json lists and return:

        {"ok": bool, "checked": int, "modified": [str], "missing": [str],
         "extra": [str], "manifest": {...}}

    `modified` is a hash or length mismatch, `missing` a manifest entry with no
    file on disk, `extra` a file present in the backup that the manifest does
    not list (the manifest itself excluded). ok is True only when all three are
    empty.
    """
    backup_dir = Path(backup_dir)
    manifest_path = backup_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"no {MANIFEST_NAME} in {backup_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError(f"unexpected manifest schema: {manifest.get('schema')!r}")

    modified, missing = [], []
    listed = set()
    for entry in manifest.get("entries", []):
        rel = entry["path"]
        listed.add(rel)
        path = backup_dir / rel
        if not path.is_file():
            missing.append(rel)
            continue
        if path.stat().st_size != entry["bytes"] or sha256_of(path) != entry["sha256"]:
            modified.append(rel)

    on_disk = {p.relative_to(backup_dir).as_posix()
               for p in _iter_files(backup_dir)} - {MANIFEST_NAME}
    extra = sorted(on_disk - listed)

    return {
        "ok": not (modified or missing or extra),
        "checked": len(listed),
        "modified": sorted(modified),
        "missing": sorted(missing),
        "extra": extra,
        "manifest": manifest,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Back up or verify Shimmer's non-regenerable state "
                    "(durable/, ontology/stores/, the governed config files).")
    parser.add_argument("--dest", metavar="FOLDER",
                        help="destination folder for a new timestamped backup")
    parser.add_argument("--verify", metavar="BACKUP_FOLDER",
                        help="verify an existing backup folder against its MANIFEST.json")
    parser.add_argument("--label", default="",
                        help="optional suffix for the backup folder name "
                             "(e.g. pre_upgrade); letters, digits, _ and - only")
    parser.add_argument("--project-root", default=str(ROOT),
                        help="the Shimmer repository to back up. Defaults to the repository "
                             "this script lives in; the verify gate points it at a temporary "
                             "tree so a gate run never copies or touches the real durable/.")
    return parser


def main(argv=None) -> int:
    args = _build_arg_parser().parse_args(argv)
    if bool(args.dest) == bool(args.verify):
        print("Give exactly one of --dest (make a backup) or --verify (check one).",
              file=sys.stderr)
        return 2

    if args.verify:
        try:
            result = verify_backup(args.verify)
        except (FileNotFoundError, ValueError, OSError) as e:
            print(f"[backup] cannot verify {args.verify}: {type(e).__name__}: {e}",
                  file=sys.stderr)
            return 2
        print(f"[backup] verifying {args.verify}", file=sys.stderr)
        print(f"[backup]   files in manifest: {result['checked']}", file=sys.stderr)
        for kind in ("modified", "missing", "extra"):
            for rel in result[kind]:
                print(f"[backup]   {kind.upper()}: {rel}", file=sys.stderr)
        if result["ok"]:
            print("[backup] INTACT: every file matches its recorded SHA-256 and length.",
                  file=sys.stderr)
            return 0
        print(f"[backup] FAILED: {len(result['modified'])} modified, "
              f"{len(result['missing'])} missing, {len(result['extra'])} unexpected.",
              file=sys.stderr)
        return 1

    label = "".join(c for c in args.label if c.isalnum() or c in "_-")
    try:
        summary = create_backup(args.project_root, args.dest, label=label)
    except (NotADirectoryError, FileExistsError, OSError) as e:
        print(f"[backup] backup failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    print(f"[backup] wrote {summary['file_count']} file(s), "
          f"{summary['total_bytes']} byte(s) to {summary['backup_dir']}", file=sys.stderr)
    if summary["missing_sources"]:
        print(f"[backup] not present in the source, so not backed up: "
              f"{summary['missing_sources']}", file=sys.stderr)
    print(f"[backup] verify it any time with:\n"
          f"    python scripts/backup_state.py --verify {summary['backup_dir']}",
          file=sys.stderr)
    print("[backup] restore is a DELIBERATE COPY, not a command here: see "
          "docs/RUNBOOK.md, 'Restoring from a backup'.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
