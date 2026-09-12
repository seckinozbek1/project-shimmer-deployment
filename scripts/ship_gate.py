"""Read-only check of the declared usage-data boundary in a shipping tree."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import durable_paths


def inspect_shipping_tree(root):
    root = Path(root)
    usage = tuple(durable_paths.USAGE_DERIVED_PATHS)
    authority = tuple(durable_paths.AUTHORITY_PATHS)
    policies = durable_paths.ARTIFACT_POLICIES
    errors = []
    if not root.is_dir():
        errors.append("shipping root missing")
    if set(usage) & set(authority):
        errors.append("usage and authority overlap")
    for name in durable_paths.ALL_SUBDIRS:
        if "durable/" + name not in usage + authority:
            errors.append("uncategorised durable directory: " + name)
    dates = policies.get("document_dates") or {}
    if (dates.get("category") != "usage-derived" or dates.get("shipping") != "omit"
            or not dates.get("path")):
        errors.append("document_dates ruling missing or inconsistent")
    for name, policy in policies.items():
        rel = policy.get("path", "")
        path = Path(rel)
        if path.is_absolute() or ".." in path.parts or not rel:
            errors.append("invalid artifact path: " + name)
            continue
        if policy.get("category") == "usage-derived" and not any(
                path == Path(parent) or Path(parent) in path.parents for parent in usage):
            errors.append("artifact outside its usage category: " + name)
        if policy.get("shipping") == "omit" and ((root / path).exists() or (root / path).is_symlink()):
            errors.append("artifact must be omitted: " + name)
    for rel in usage:
        path = root / rel
        if not path.exists() and not path.is_symlink():
            continue
        # Do not read payloads or emit operator filenames. Empty directory
        # placeholders are allowed; data and links are not shipped.
        entries = [path] if not path.is_dir() or path.is_symlink() else path.rglob("*")
        if any(p.is_symlink() or (p.is_file() and (p.name != ".gitkeep" or p.stat().st_size))
               for p in entries):
            errors.append("populated usage path: " + rel)
    return {"status": "FAIL" if errors else "PASS", "violations": errors,
            "document_dates": {key: dates.get(key) for key in ("path", "category", "shipping")}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    result = inspect_shipping_tree(args.root)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
