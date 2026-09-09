"""Document role resolution: the 4-tier chain that decides which files in
input/context/ are under review and which are grounding. Tiers, highest authority
first; first match wins, each tier the fallback of the previous:

  Tier 1  Operator instruction   a pre-existing _review_targets.json (the operator
          named the targets via the wizard, the chat, or the server). Authoritative:
          kept as-is, never overwritten.
  Tier 2  Convention             a `review_targets:` field in
          input/conventions/review_mandate.md names the targets (minimal parse).
  Tier 3  Sidecar + date cutoff  the existing mechanism (M1 sidecar grounding
          exclusion + review_scope.json cutoff). The chain writes nothing here, so
          with no manifest the pipeline behaves exactly as before.
  Tier 4  Content inference      a guarded stub behind --infer-roles (off by
          default). NOT IMPLEMENTED: logs "tier 4 not enabled" and returns
          unresolved, leaving the remaining files to the date cutoff.

The manifest input/context/_review_targets.json is underscore-prefixed, so the
Item 1a corpus guard (text_extract.is_corpus_file) never loads it as a document.
Its keys: `targets` (under review), `grounding` (reference material), `prior` (R6:
grounding files that are an EARLIER VERSION of a document under review, compared
against it and never promoted), `source`, `resolved_at`.

This module is domain-agnostic: no domain vocabulary, no hardcoded absolute paths.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MANIFEST_NAME = "_review_targets.json"
MANDATE_NAME = "review_mandate.md"
# Recognized provenance tags for the manifest's `source` field.
VALID_SOURCES = {"operator", "convention", "filename", "content", "system_draft"}


def manifest_path(context_dir: Path) -> Path:
    return Path(context_dir) / MANIFEST_NAME


def read_manifest(context_dir: Path) -> "dict | None":
    """Return the parsed manifest dict, or None if absent or unreadable."""
    p = manifest_path(context_dir)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_manifest(context_dir: Path, targets, source: str, *, grounding=None,
                   prior=None, now_iso: "str | None" = None) -> Path:
    """Write _review_targets.json. Filenames are reduced to their basename so a
    crafted path can never point outside input/context/.

    `prior` (R6) names the grounding file(s) that are an EARLIER VERSION of a
    document under review, so the review can compare the two. A prior is grounding,
    never promoted to input/operational/."""
    context_dir = Path(context_dir)
    context_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "targets": [Path(str(t)).name for t in (targets or [])],
        "grounding": [Path(str(g)).name for g in (grounding or [])],
        "prior": [Path(str(p)).name for p in (prior or [])],
        "source": source if source in VALID_SOURCES else "operator",
        "resolved_at": now_iso or "",
    }
    p = manifest_path(context_dir)
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return p


def manifest_targets(manifest: "dict | None") -> set:
    if not manifest:
        return set()
    t = manifest.get("targets")
    return {Path(str(x)).name for x in t} if isinstance(t, list) else set()


def manifest_grounding(manifest: "dict | None") -> set:
    if not manifest:
        return set()
    g = manifest.get("grounding")
    return {Path(str(x)).name for x in g} if isinstance(g, list) else set()


def manifest_prior(manifest: "dict | None") -> set:
    """The files the operator declared as an EARLIER VERSION of a document under
    review (R6). A manifest without the key, the common case, yields set()."""
    if not manifest:
        return set()
    p = manifest.get("prior")
    return {Path(str(x)).name for x in p} if isinstance(p, list) else set()


def clear_system_draft(context_dir: Path) -> bool:
    """Remove a SYSTEM-generated draft memo and its _review_targets.json, so a draft
    run's artifacts do not persist as a stale tier-1 review target on the next run.
    Acts ONLY when the manifest's source is 'system_draft'; an operator- or
    convention-written manifest is left in place (that is deliberate instruction).
    Returns True if it cleared a system_draft manifest."""
    context_dir = Path(context_dir)
    data = read_manifest(context_dir)
    if not data or data.get("source") != "system_draft":
        return False
    for fname in data.get("targets", []):
        if isinstance(fname, str) and fname:
            try:
                (context_dir / Path(fname).name).unlink()
            except OSError:
                pass
    try:
        manifest_path(context_dir).unlink()
    except OSError:
        pass
    return True


def _parse_convention_targets(mandate_path: Path) -> "list[str]":
    """Tier 2 (minimal): a single `review_targets:` line in review_mandate.md.
    Accepts a JSON-ish list or a comma/space separated list of filenames. Returns
    [] when the field is absent or the file is unreadable."""
    mandate_path = Path(mandate_path)
    if not mandate_path.is_file():
        return []
    try:
        text = mandate_path.read_text(encoding="utf-8")
    except OSError:
        return []
    m = re.search(r"(?im)^\s*review_targets\s*:\s*(.+)$", text)
    if not m:
        return []
    raw = m.group(1).strip().strip("[]")
    parts = re.split(r"[,\s]+", raw)
    return [p.strip().strip("\"'") for p in parts if p.strip().strip("\"'")]


def resolve_review_roles(project_root: Path, *, infer_roles: bool = False,
                         now_iso: "str | None" = None) -> dict:
    """Run the chain. Returns {resolved_by, targets, grounding, manifest_written}.
    Writes _review_targets.json only when tier 2 resolves (tier 1 is already an
    operator-written manifest; tiers 3/4 defer to the date cutoff)."""
    project_root = Path(project_root)
    context_dir = project_root / "input" / "context"

    # Tier 1: operator instruction (a pre-existing manifest). Highest authority.
    existing = read_manifest(context_dir)
    if existing is not None:
        targs = manifest_targets(existing)
        print(f"[role-resolution] tier 1: operator manifest names {len(targs)} target(s)",
              file=sys.stderr, flush=True)
        return {"resolved_by": "operator", "targets": sorted(targs),
                "grounding": sorted(manifest_grounding(existing)),
                "prior": sorted(manifest_prior(existing)), "manifest_written": False}

    # Tier 2: a convention names the targets (minimal review_targets: field).
    conv_targets = _parse_convention_targets(
        project_root / "input" / "conventions" / MANDATE_NAME)
    if conv_targets:
        names = sorted({Path(t).name for t in conv_targets})
        write_manifest(context_dir, names, "convention", now_iso=now_iso)
        print(f"[role-resolution] tier 2: convention names {len(names)} target(s)",
              file=sys.stderr, flush=True)
        return {"resolved_by": "convention", "targets": names, "grounding": [],
                "prior": [], "manifest_written": True}

    # Tier 3: sidecar + date cutoff (existing mechanism). The chain writes nothing;
    # the caller applies the cutoff to every file the manifest did not resolve.
    print("[role-resolution] tier 3: no operator/convention targets; deferring to the "
          "sidecar + date cutoff", file=sys.stderr, flush=True)

    # Tier 4: content inference (guarded stub, off by default).
    if infer_roles:
        print("[role-resolution] tier 4 not enabled (content inference is a stub); "
              "leaving the remaining files to the date cutoff", file=sys.stderr, flush=True)

    return {"resolved_by": "cutoff", "targets": [], "grounding": [], "prior": [],
            "manifest_written": False}
