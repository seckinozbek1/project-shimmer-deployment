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
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import role_resolution

# scripts/ is sys.path[0] when launched as `python scripts/intake_wizard.py`, so
# the sibling framework modules import by bare name (same convention as pipeline).
import convention_parser
import redaction_gate
import sensitivity_layer

ROOT = Path(__file__).resolve().parent.parent
SCOPE_PATH = ROOT / "config" / "review_scope.json"

# Supported document extensions (everything else of a recognized NAME is special-
# cased below; anything unrecognized is skipped).
SUPPORTED_DOC_EXT = {".md", ".txt", ".pdf", ".docx"}
CONVENTION_NAMES = {"review_conventions.md", "review_mandate.md"}
# A convention file is recognised by CONTENT as well as by those two legacy
# names: the text formats worth opening to look for rule headings, and the size
# past which a file is taken as a document rather than a rule sheet.
CONVENTION_TEXT_EXT = {".md", ".txt"}
CONVENTION_SNIFF_BYTES = 4 * 1024 * 1024
SCOPE_NAME = "review_scope.json"
SIDECAR_SUFFIX = "_corpus_ingest.json"


# --- small prompt helper -------------------------------------------------------

def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


# --- classification ------------------------------------------------------------

def _carries_rule_headings(path: Path) -> bool:
    """True when a text file carries the operator's own rule headings, asked of
    the convention parser itself rather than answered here. Only text formats
    are opened; a parse or decode failure is not a classification."""
    if path.suffix.lower() not in CONVENTION_TEXT_EXT:
        return False
    try:
        if path.stat().st_size > CONVENTION_SNIFF_BYTES:
            return False
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return convention_parser.text_carries_rule_headings(text)


def classify(path: Path) -> "tuple[str, str, Optional[Path]]":
    """Return (kind, why, target_dir_relative_to_ROOT). target is None when the
    file is unsupported and should be skipped."""
    name = path.name
    if name in CONVENTION_NAMES:
        return ("CONVENTIONS", "review rules", Path("input") / "conventions")
    # The operator names their own files. A file carrying rule headings IS the
    # review framework whatever it is called, so intake classifies it by the
    # same signal the parser will read it with instead of by a fixed name.
    if _carries_rule_headings(path):
        return ("CONVENTIONS", "review rules (carries rule headings)",
                Path("input") / "conventions")
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


def _choose_backend_profile() -> "tuple[str, list[str]]":
    """Ask which backend the run uses, and emit --backend-profile for it.

    The wizard collected every other run flag and never this one, so a review
    started from the launcher or from chat always took the pipeline's own
    default. That decides real behaviour, not just cost: resolve_review_mode
    selects paired under local and wide under cloud, so the flag the wizard
    omitted was choosing the review mode by accident.

    When a caller has already chosen (the launcher asks before its preflight,
    since the profile decides what readiness means) SHIMMER_BACKEND_PROFILE
    carries that answer and the operator is not asked the same question twice.
    """
    preset = (os.environ.get("SHIMMER_BACKEND_PROFILE") or "").strip().lower()
    if preset in ("cloud", "local"):
        return (preset + " (chosen at startup)", ["--backend-profile", preset])
    print()
    print("Which backend will this run use?")
    print()
    print("  [1] Cloud (Claude / GPT through your API keys; costs money per run)")
    print("  [2] Local (models on this machine; no provider is called, no API cost)")
    print()
    choice = _ask("Choose [1/2, Enter for Cloud]: ")
    profile = "local" if choice == "2" else "cloud"
    return (profile, ["--backend-profile", profile])


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


# --- which ingestion contract this import is under -----------------------------

def _ingest_mode_flags(classified) -> "list[str]":
    """Declare the run's ingestion mode from what is actually being imported.

    Two contracts exist and were silently conflated. corpus_ingest's validator
    requires a _corpus_ingest.json sidecar and hard-fails without one, but that
    contract governs an EXTERNALLY FED corpus, where the sidecar's
    role=context_grounding is what keeps retrieved precedent from being promoted
    to the documents under review. The wizard stages the operator's own files,
    where no such metadata exists: writing a sidecar here would mean inventing
    the role, date and source-verification fields the operator never supplied,
    and the pipeline would then warn that a sidecar appeared in a standalone run.

    So the reconciliation is a DECLARATION, not a fabricated file. A sidecar the
    operator brought means integrated; no sidecar means standalone, which is the
    pipeline's own default. The wizard emitted neither, so an integrated import
    ran as standalone and the promotion exclusion never fired."""
    has_sidecar = any(kind == "SIDECAR" for _p, kind, _t in classified)
    if not has_sidecar:
        # A sidecar placed by an earlier import still governs this run.
        has_sidecar = any((ROOT / "input" / "context").glob("*" + SIDECAR_SUFFIX))
    if has_sidecar:
        print()
        print("  An ingestion sidecar is present, so this run is declared integrated:")
        print("  files marked context_grounding stay grounding and are never reviewed.")
        return ["--mode", "integrated"]
    return []


# --- what the conventions actually declare -------------------------------------

def summarize_conventions(paths) -> dict:
    """Read the rule sheets with the real parser and report what it extracted:
    how many rules, which subject tags, how many rules carry a scope or a
    requires declaration. Intake had no surface for any of this, so a subject
    tag that failed to parse (or a heading the operator thought was a rule and
    the parser did not) was invisible until the run produced nothing. Reading
    only: this places nothing and decides nothing."""
    summary = {"files": [], "rules": 0, "subjects": set(),
               "scoped": 0, "requires": 0, "unreadable": []}
    for path in paths:
        try:
            text = Path(path).read_text(encoding="utf-8")
            rules = convention_parser._parse_text_lines(text, Path(path).name, [1])
        except (OSError, UnicodeDecodeError, ValueError):
            summary["unreadable"].append(Path(path).name)
            continue
        subjects = set()
        scoped = requires = 0
        for rule in rules:
            subjects |= set(getattr(rule, "subjects", None) or [])
            if getattr(rule, "scope", None):
                scoped += 1
            if getattr(rule, "requires", None):
                requires += 1
        summary["files"].append({"name": Path(path).name, "rules": len(rules),
                                 "subjects": sorted(subjects), "scoped": scoped,
                                 "requires": requires})
        summary["rules"] += len(rules)
        summary["subjects"] |= subjects
        summary["scoped"] += scoped
        summary["requires"] += requires
    summary["subjects"] = sorted(summary["subjects"])
    return summary


def _print_convention_summary(summary: dict) -> None:
    """Print the declaration report. Silence about an absent declaration would
    be a claim that none was wanted, so each line says what was read."""
    if not summary["files"] and not summary["unreadable"]:
        return
    print()
    print("Conventions read:")
    for entry in summary["files"]:
        print(f"  {entry['name']}: {entry['rules']} rules")
    for name in summary["unreadable"]:
        print(f"  {name}: could not be parsed, it will be placed but may yield no rules")
    if not summary["files"]:
        # Nothing was read, so nothing can be said about what was declared.
        return
    if summary["rules"] == 0:
        print("  No rules were extracted. Check that rule headings carry your own")
        print("  rule ids, for example '## CONV-D01 , conv-value-in-range [required]'.")
        return
    subjects = summary["subjects"]
    print("  Subject tags:  "
          + (", ".join(subjects) if subjects
             else "none declared (every rule goes to every agent that can act on it)"))
    print("  Scope:         "
          + (f"{summary['scoped']} rule(s) declare [scope: ...]" if summary["scoped"]
             else "none declared (every rule applies to every unit)"))
    if summary["requires"]:
        print(f"  Requires:      {summary['requires']} rule(s) declare [requires: ...]")


# --- conventions presence ------------------------------------------------------

def _conventions_will_exist(classified) -> bool:
    for _p, kind, _t in classified:
        if kind == "CONVENTIONS":
            return True
    conv_dir = ROOT / "input" / "conventions"
    if conv_dir.is_dir():
        for p in conv_dir.iterdir():
            # Same reconciliation as classify(): the parser reads every file in
            # this directory, so a rule sheet already sitting here counts under
            # whatever name the operator gave it.
            if p.is_file() and (p.name in CONVENTION_NAMES
                                or _carries_rule_headings(p)):
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
    mode_label = parallel_label = maxdocs_label = profile_label = ""
    if not import_only:
        profile_label, profile_flags = _choose_backend_profile()
        run_flags += profile_flags
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
        run_flags += _ingest_mode_flags(classified)

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
        print(f"  Backend:       {profile_label}")
        print(f"  Mode:          {mode_label}")
        print(f"  Parallel docs: {parallel_label}")
        print(f"  Max docs:      {maxdocs_label}")
    _print_convention_summary(summarize_conventions(
        [p for p, kind, _t in classified if kind == "CONVENTIONS"]))
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
