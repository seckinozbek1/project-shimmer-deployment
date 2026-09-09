"""Document intake wizard for Project Shimmer.

Invoked by the master launcher (shimmer.bat / shimmer.sh):
  - menu option [1] Run a review: `--emit-flags PATH` (full wizard, then the
    launcher runs pipeline.py with the collected flags written to PATH);
  - menu option [5] Import documents: `--import-only` (place files + set the
    cutoff only, no run, no flags).

It owns the operator-decision surface the launcher cannot express on its own:
scan a folder and classify each file, place files into the right trees, print
and optionally edit the date cutoff (config/review_scope.json), choose the
Normal/Sensitive run mode (mapped to the pipeline override flags, with a Qwen
reachability check for Sensitive), ask the parallelism and max-document limits,
warn when no conventions are present, then show a plan and confirm before any
copy.

This module is domain-agnostic by construction: it carries no domain vocabulary,
no hardcoded absolute paths, and never prints or stores a key value. Model
selection, per-agent flags, jurisdiction, and language detection are NOT wizard
knobs (they are owned by the registry / conventions / the pipeline).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import role_resolution

# scripts/ is sys.path[0] when launched as `python scripts/intake_wizard.py`, so
# the sibling framework modules import by bare name (same convention as pipeline).
import redaction_gate
import sensitivity_layer

ROOT = Path(__file__).resolve().parent.parent
SCOPE_PATH = ROOT / "config" / "review_scope.json"

# Supported document extensions (everything else of a recognized NAME is special-
# cased below; anything unrecognized is skipped).
SUPPORTED_DOC_EXT = {".md", ".txt", ".pdf", ".docx"}
CONVENTION_NAMES = {"review_conventions.md", "review_mandate.md"}
SCOPE_NAME = "review_scope.json"
SIDECAR_SUFFIX = "_corpus_ingest.json"


# --- small prompt helper -------------------------------------------------------

def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


# --- classification ------------------------------------------------------------

def classify(path: Path) -> "tuple[str, str, Optional[Path]]":
    """Return (kind, why, target_dir_relative_to_ROOT). target is None when the
    file is unsupported and should be skipped."""
    name = path.name
    if name in CONVENTION_NAMES:
        return ("CONVENTIONS", "review rules", Path("input") / "conventions")
    if name == SCOPE_NAME:
        return ("CONFIG", "date cutoff settings", Path("config"))
    if name.endswith(SIDECAR_SUFFIX):
        return ("SIDECAR", "grounding case metadata", Path("input") / "context")
    if path.suffix.lower() in SUPPORTED_DOC_EXT:
        return ("DOCUMENT", "pipeline sorts into context or operational by the cutoff",
                Path("input") / "context")
    return ("UNSUPPORTED", "not a supported type; skipped", None)


def scan(folder: Path) -> "list[Path]":
    return sorted(p for p in folder.iterdir() if p.is_file())


# --- date cutoff (config/review_scope.json) ------------------------------------

def _read_scope() -> dict:
    if SCOPE_PATH.exists():
        try:
            return json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _current_cutoff_str() -> str:
    return str(_read_scope().get("cutoff_date") or "(none set)")


def _write_cutoff(value: str) -> None:
    scope = _read_scope()
    scope["cutoff_date"] = value
    scope["cutoff_type"] = "date"
    SCOPE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCOPE_PATH.write_text(json.dumps(scope, indent=2) + "\n", encoding="utf-8")


def _explain_and_maybe_update_cutoff() -> "Optional[str]":
    """Print the current cutoff and let the operator change it. Returns the new
    cutoff if the operator set one, else None (kept). The caller re-asserts a set
    value after file placement so an imported review_scope.json cannot clobber the
    operator's explicit override."""
    scope = _read_scope()
    cur = scope.get("cutoff_date")
    print()
    if cur:
        print(f"Current date cutoff: {cur}. Documents dated before this are context/grounding.")
        print("Documents dated on or after this are under review.")
    else:
        print("No date cutoff is set. All documents will be treated the same.")
    new = _ask("Change the cutoff? Enter a new date (YYYY-MM-DD) or press Enter to keep: ")
    if not new:
        return None
    try:
        datetime.strptime(new, "%Y-%m-%d")
    except ValueError:
        print(f"'{new}' is not a valid YYYY-MM-DD date. Keeping the current cutoff.")
        return None
    _write_cutoff(new)
    print(f"Cutoff updated to {new}.")
    return new


# --- run mode (maps to the pipeline override flags) ----------------------------

_NORMAL_FLAGS = ["--sensitivity-layer-inactive-override", "--no-redaction-override"]


def _choose_mode() -> "tuple[str, Optional[list[str]]]":
    print()
    print("Select run mode:")
    print()
    print("  [1] Normal mode (recommended for most reviews)")
    print("      Reviews your documents, flags defects, and proposes amendments. Any")
    print("      personal data or confidential figures found are FLAGGED in the findings")
    print("      but NOT scrubbed from the deliverables. You receive the full output.")
    print("      Use this when the documents are not sensitive.")
    print()
    print("  [2] Sensitive mode")
    print("      Everything in normal mode, plus a local model (Qwen, on your machine,")
    print("      nothing leaves) scans for personal data and confidential figures and")
    print("      scrubs them from the output before deliverables are finalized. If a")
    print("      scrub cannot be confirmed clean, the deliverable is held. Use this when")
    print("      the documents contain real personal, client, or commercial data.")
    print()
    choice = _ask("Choose [1/2]: ")
    if choice == "2":
        return _sensitive_flags()
    # Blank or "1" -> Normal. Both overrides are required for the run to actually
    # start and produce full, unredacted output (see the pipeline startup gates).
    return ("Normal (no redaction)", list(_NORMAL_FLAGS))


def _sensitive_flags() -> "tuple[str, Optional[list[str]]]":
    """Sensitive mode keeps redaction ON (no --no-redaction-override). Check Qwen
    reachability first and let the operator confirm or switch."""
    qstat = redaction_gate.qwen_backend_status(ROOT)
    if not qstat.get("configured"):
        print()
        print(f"The local Qwen redaction backend is not reachable: {qstat.get('detail')}")
        ans = _ask("Sensitive mode needs it. [s]witch to Normal, [c]ontinue anyway, or [q]uit? ").lower()
        if ans.startswith("q"):
            return ("(cancelled)", None)
        if ans.startswith("c"):
            print("Continuing in Sensitive mode. The pipeline will stop at its redaction")
            print("gate if Qwen truly cannot run; set it up or switch to Normal if so.")
        else:
            return ("Normal (no redaction)", list(_NORMAL_FLAGS))
    flags: "list[str]" = []
    if not sensitivity_layer.is_active():
        print()
        print("Note: the full LAW-IV outbound masking layer is operator-activated and is")
        print("currently inactive. Deliverable redaction still runs locally; outbound")
        print("masking to the network is deferred until the layer is activated.")
        flags.append("--sensitivity-layer-inactive-override")
    return ("Sensitive (redaction on)", flags)


# --- parallelism + document cap ------------------------------------------------

def _ask_positive_int(prompt: str, flag: str, default_label: str) -> "tuple[str, list[str]]":
    ans = _ask(prompt)
    if not ans:
        return (default_label, [])
    try:
        n = int(ans)
        if n < 1:
            raise ValueError
    except ValueError:
        print(f"Not a positive whole number. Using {default_label}.")
        return (default_label, [])
    return (str(n), [flag, str(n)])


# --- conventions presence ------------------------------------------------------

def _conventions_will_exist(classified) -> bool:
    for _p, kind, _t in classified:
        if kind == "CONVENTIONS":
            return True
    conv_dir = ROOT / "input" / "conventions"
    if conv_dir.is_dir():
        for p in conv_dir.iterdir():
            if p.is_file() and p.name in CONVENTION_NAMES:
                return True
    return False


def _count_by_kind(classified) -> dict:
    counts = {"DOCUMENT": 0, "CONVENTIONS": 0, "CONFIG": 0, "SIDECAR": 0}
    for _p, kind, _t in classified:
        if kind in counts:
            counts[kind] += 1
    return counts


def _ask_and_write_review_targets(doc_names: "list[str]") -> None:
    """Ask which placed documents are under review; the rest become grounding.
    Writes input/context/_review_targets.json (tier 1, source=operator). Empty or
    no selection writes nothing, so the date cutoff decides (backward compatible)."""
    if not doc_names:
        return
    print()
    print("Which of these documents should be REVIEWED? The rest become reference/grounding.")
    for i, name in enumerate(doc_names, 1):
        print(f"  [{i}] {name}")
    ans = _ask("Enter the numbers to review (comma-separated), 'all', or Enter to let "
               "the date cutoff decide: ")
    if not ans:
        return
    if ans.strip().lower() == "all":
        targets, grounding = list(doc_names), []
    else:
        picked = []
        for tok in re.split(r"[,\s]+", ans.strip()):
            if tok.isdigit() and 1 <= int(tok) <= len(doc_names):
                picked.append(doc_names[int(tok) - 1])
        if not picked:
            print("No valid selection. Leaving the role split to the date cutoff.")
            return
        targets = sorted(set(picked))
        grounding = [n for n in doc_names if n not in targets]
    # R6: one of the grounding documents may be an EARLIER VERSION of a document
    # under review (the previous round of a negotiation, the previous draft). The
    # operator says so; nothing infers it. Enter keeps the manifest as before.
    prior = []
    if grounding:
        print()
        print("Grounding documents:")
        for i, name in enumerate(grounding, 1):
            print(f"  [{i}] {name}")
        ans2 = _ask("Is one of these an EARLIER VERSION of a document under review? "
                    "Enter its number, or Enter for none: ")
        if ans2.strip().isdigit() and 1 <= int(ans2.strip()) <= len(grounding):
            prior = [grounding[int(ans2.strip()) - 1]]
    role_resolution.write_manifest(
        ROOT / "input" / "context", targets, "operator",
        grounding=grounding, prior=prior, now_iso=datetime.now(timezone.utc).isoformat())
    print(f"Marked {len(targets)} document(s) under review; {len(grounding)} as grounding"
          + (f"; {prior[0]} as the earlier version." if prior else "."))


# --- main flow -----------------------------------------------------------------

def run(emit_flags_path: "Optional[str]", import_only: bool) -> int:
    print("Document intake")
    folder_str = _ask("Enter the folder containing your documents: ")
    if not folder_str:
        print("No folder given. Nothing to do.")
        return 1
    folder = Path(folder_str).expanduser()
    if not folder.is_dir():
        print(f"Not a folder: {folder}")
        return 1

    files = scan(folder)
    if not files:
        print("No files found in that folder.")
        return 1

    print()
    print(f"Found {len(files)} file(s):")
    classified = []  # (path, kind, target_rel)
    for p in files:
        kind, why, target = classify(p)
        if kind == "UNSUPPORTED":
            print(f"  - {p.name}: SKIP ({why})")
            continue
        print(f"  - {p.name}: {kind} ({why}) -> {target.as_posix()}/")
        classified.append((p, kind, target))
    if not classified:
        print("No supported files to import.")
        return 1

    chosen_cutoff = _explain_and_maybe_update_cutoff()

    run_flags: "list[str]" = []
    mode_label = parallel_label = maxdocs_label = ""
    if not import_only:
        mode_label, mode_flags = _choose_mode()
        if mode_flags is None:
            print("Cancelled. No files placed.")
            return 1
        run_flags += mode_flags
        print()
        parallel_label, pflag = _ask_positive_int(
            "How many documents to review in parallel? (default 4, higher is faster but "
            "uses more API quota) [Enter for default]: ",
            "--max-concurrent-docs", "4 (default)")
        run_flags += pflag
        maxdocs_label, mflag = _ask_positive_int(
            "How many documents to review at most? [Enter for all]: ",
            "--max-docs", "all")
        run_flags += mflag

    if not _conventions_will_exist(classified):
        print()
        ans = _ask("No review conventions found. The pipeline will run with default rules "
                   "only. [P]roceed with defaults or [Q]uit? ").lower()
        if ans.startswith("q"):
            print("Quit. No files placed.")
            return 1

    counts = _count_by_kind(classified)
    print()
    print("Review plan:")
    print(f"  Documents:   {counts['DOCUMENT']} -> input/context/ (pipeline sorts by cutoff)")
    print(f"  Conventions: {counts['CONVENTIONS']} -> input/conventions/")
    print(f"  Config:      {counts['CONFIG']} -> config/")
    print(f"  Sidecars:    {counts['SIDECAR']} -> input/context/")
    print(f"  Date cutoff: {_current_cutoff_str()}")
    if not import_only:
        print(f"  Mode:          {mode_label}")
        print(f"  Parallel docs: {parallel_label}")
        print(f"  Max docs:      {maxdocs_label}")
    confirm = _ask("Proceed? [Y/n]: ").lower()
    if confirm.startswith("n"):
        print("Cancelled. No files placed.")
        return 1

    print()
    for p, _kind, target in classified:
        dest_dir = ROOT / target
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest_dir / p.name)
        print(f"  Placed {p.name} -> {target.as_posix()}/")

    # The operator's interactive cutoff override is the final word: re-assert it
    # so an imported review_scope.json placed above cannot overwrite it.
    if chosen_cutoff:
        _write_cutoff(chosen_cutoff)

    # Tier 1 of the document role resolution chain: let the operator name which of
    # the placed documents are under review (the rest become grounding). Writes
    # input/context/_review_targets.json with source="operator".
    _ask_and_write_review_targets([p.name for p, kind, _t in classified if kind == "DOCUMENT"])

    cutoff = _current_cutoff_str()
    print()
    print("What happens next:")
    print(f"  The pipeline reads these files. Documents dated {cutoff} or later are reviewed")
    print("  against your conventions and grounding corpus. Documents dated before the")
    print("  cutoff stay as reference context. The date is resolved from the filename (a")
    print("  4-digit year in the name is the primary signal).")

    if emit_flags_path and not import_only:
        Path(emit_flags_path).write_text(" ".join(run_flags), encoding="utf-8")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Project Shimmer document intake wizard")
    parser.add_argument("--emit-flags", metavar="PATH", default=None,
                        help="write the collected pipeline flags (space-separated) to this file")
    parser.add_argument("--import-only", action="store_true",
                        help="place documents and set the cutoff only; collect no run flags")
    args = parser.parse_args(argv)
    try:
        return run(args.emit_flags, args.import_only)
    except KeyboardInterrupt:
        print()
        print("Interrupted. No further changes.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
