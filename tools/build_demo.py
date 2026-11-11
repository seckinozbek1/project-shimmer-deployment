"""Build the console's demo (D-S48): one static folder from saved run folders, opened with no install.

    py -3.12 -X utf8 tools/build_demo.py --out <folder> \
        --rounds synthetic=<run> --review synthetic=<run> --documents synthetic=<folder> \
        --rounds public=<run>    --review public=<run>    --documents public=<folder>

`--rounds` is a multi-round run folder (audit/multi_round.json, round_reuse.json, version_changes.json,
case_questions.json); `--review` an ordinary two-version review (deliverables/<document>/review_data.json
and the files beside it). Either may instead be the batch entry's `collected_evidence.tar.gz`: it is
unpacked into a temporary folder (only files under evidence/, no model reply record) and the one run
folder of that kind inside it is read; none or several is refused.`--documents` the folder holding the case's documents as given to the run
(.md, .txt or .docx, read with scripts/text_extract.py), shown on the documents screen. Each is optional;
a screen whose record is not given says so. The two case kinds are `synthetic` and `public`, in that order.

What it writes, and nothing else:

    index.html     the demo: every record inlined as JSON, no request of any kind (a Content Security
                   Policy of default-src 'none' forbids one), no token, no key, no storage
    files/         the deliverables to download, byte copies of the run's own files
    open_demo.bat  a double-click starter for Windows; open_demo.sh for macOS and Linux
    README.txt     what this folder is, in English and in the second language (tr)

It reads only the folders it is given. Under benchmark/ it reads only benchmark/dev_cases/ (the two
worked cases' own source documents, development cases built for demonstration: one synthetic, one a
public UN text); every other path under benchmark/ is refused, and documents under external/ are
refused too. A run's own evidence may lie under external/, where the loop keeps its cloud evidence.
The test is made below whichever checkout holds the path, worktree or main. With no
--documents, the documents are read from the runs' own evidence when one folder there holds every
document the runs name. It shows what the saved records say and
decides nothing: Python's findings are the round review's records and the amendments built from computed
findings; everything a model wrote (the master's model findings, a movement a model answered, a suggested
wording) is shown apart, each with finding_record.MODEL_FINDING_MARK. A sealed run is refused, since a
sealed run's text is never shown (CONSOLE-A). Two builds from the same folders are byte-identical: no
clock, no absolute path and no run id is written.
"""
import argparse
import contextlib
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import finding_record  # noqa: E402
import localization  # noqa: E402

TEMPLATE = ROOT / "scripts" / "ui" / "demo.html"
DEFAULT_OUT = ROOT / "demo"   # scripts/ui/console.html links to ../../demo/index.html
DATA_MARKER = "/*DEMO_DATA*/"
KINDS = ("synthetic", "public")
DOWNLOADS = ("tracked_changes.docx", "review_findings.md", "document_summary.md",
             "version_changes.md", "case_positions.md")
DOCUMENT_SUFFIXES = (".md", ".txt", ".docx")
REFUSED_ROOTS = ("benchmark", "external")   # for --documents
RUN_REFUSED_ROOTS = ("benchmark",)          # for a run or its evidence
ALLOWED_UNDER_REFUSED = (("benchmark", "dev_cases"),)
MODEL_MARK = finding_record.MODEL_FINDING_MARK
PYTHON_MARK = finding_record.COMPUTED_FINDING_MARK
SELECTED_MARK = "Selected by Python from the case's declared sources. No model chose it."
CHANGES_MARK = "Computed in code from the two versions. No model read them or wrote any of this."

# Every label the page shows. Each needs a row in the second language (tr) in scripts/ui/localization_catalog.js; the
# build refuses otherwise, so no screen can fall back to English in the second language.
STRINGS = [
    "Shimmer demo", "Demo: no installation, saved examples",
    "This page shows the saved results of two demonstration cases: one synthetic, one a public UN text. "
    "They are not benchmark evidence and say nothing about how well the system does on other documents.",
    "Nothing here runs. No model, no internet connection, no key and no password is used. The documents "
    "stay on this computer: this page only reads the copies saved in its own folder.",
    "Choose a case to begin.", "Read only. Nothing you do here changes a saved result.",
    "English", "Türkçe", "Start", "Case", "Synthetic case", "Public UN text",
    "Made up for this demonstration. No real organisation or state is meant.",
    "A real public United Nations draft and its revision.",
    "Documents", "Rounds side by side", "What changed", "Findings", "Positions",
    "Suggested wording", "Downloads", "Round", "Document", "Text",
    "The document texts were not included in this demo build.",
    "Part", "Checked again in this round", "Unchanged since round {round}: its findings were reused",
    "This record is not part of this demo build.",
    "Found by Python", "Written by a model",
    "Python computed these from the document's own figures and the rules. No model wrote them.",
    "A model wrote these. They are shown so you can read them, not because anyone checked them.",
    "None.", "Rule", "Earlier", "Now", "Sentence removed", "Sentence added", "Sentence changed",
    "Before", "After", "Figure changed", "From round {before} to round {after}",
    "Suggested change to the text", "The model wrote", "Comment",
    "Stated positions", "Party", "Issue", "Statement", "Source",
    "Movement between rounds", "Moved toward the other party", "Moved away from the other party",
    "Moved neither way", "The model could not settle it", "Unknown: not asked",
    "Unknown: the question could not be asked",
    "Toward or away is a model's reading of three statements. It is never computed.",
    "Suggested wording for {party}", "Why, as the model gave it", "Passages it rests on",
    "Python chose the passages; a model wrote the wording. Nothing here is an amendment.",
    "No suggestion was kept for this case.",
    "No suggestion was kept on this issue. Python's record says:", "The text as it stands",
    "Files from the saved run, as the run wrote them.", "Download",
    "Tracked changes (Word)", "Findings (text)", "Document summary (text)",
    "What changed between versions (text)", "Positions and suggested wording (text)",
    "Ordinary review of the last version against the one before", "Review of all rounds",
    "This build uses invented test material, not the worked cases' saved results.",
    "How the run ended",
    "This run finished and passed its integrity check.",
    "This run finished, but did not pass its integrity check. Part of its work is incomplete: what is shown here is everything it produced, and nothing more.",
    "No integrity record was included for this run.",
    "Set aside: the answer of {agent} did not have the form the system requires, so the parts it covered were not checked.",
    "Why it was set aside, as the system recorded it:",
    "Size of the answer set aside: {bytes} bytes.",
    "Part of the review could not be completed, so some rules were not checked.",
    "A required agent's answer did not have the required form.",
    "Reason recorded:",
    "No measured threshold exists yet for deciding toward or away, so this question was not put to a model.",
    "No other party's position is recorded on this issue to compare with, so this question was not asked.",
    "No suggestion was asked: the case declares no party whose position the wording should support.",
    "No suggestion was asked. Python's record says:",
]
for _mark in (MODEL_MARK, PYTHON_MARK, SELECTED_MARK, CHANGES_MARK):
    STRINGS.append(_mark)

DOWNLOAD_LABELS = {"tracked_changes.docx": "Tracked changes (Word)", "review_findings.md": "Findings (text)",
                   "document_summary.md": "Document summary (text)",
                   "version_changes.md": "What changed between versions (text)",
                   "case_positions.md": "Positions and suggested wording (text)"}


class Refused(SystemExit):
    pass


def _json(path):
    path = Path(path)
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else None


def _repo_parts(path):
    """`path`'s parts below the checkout that holds it (the nearest folder with a .git entry, so a
    worktree and the main checkout are read alike), or below ROOT; None outside any."""
    resolved = Path(path).resolve()
    for folder in [resolved] + list(resolved.parents):
        if (folder / ".git").exists():
            return resolved.relative_to(folder).parts
    try:
        return resolved.relative_to(ROOT.resolve()).parts
    except ValueError:
        return None


def _refuse_location(path, roots=REFUSED_ROOTS):
    """Refuses a folder under any of `roots` in a checkout, but benchmark/dev_cases/. The documents
    are held to benchmark/ and external/; a run's own evidence to benchmark/ only, since the loop's
    cloud evidence lives under external/ (D-332)."""
    parts = _repo_parts(path)
    if parts and parts[0] in roots and not any(parts[:len(a)] == a for a in ALLOWED_UNDER_REFUSED):
        raise Refused("refused: %s is under %s/, which the demo never reads for this" % (Path(*parts), parts[0]))


SEAL_RECORDS = ("seal.json", "seal_entry.json", "execution_manifest.json")


def _refuse_sealed(run):
    """Refuses a run sealed for the test: its own status, or a seal record in the run folder or the
    three folders above it (a batch entry's evidence/run sits two below its seal). A seal record that
    cannot be read refuses too (fail closed); an exposed one is read and passes."""
    sealed = Refused("refused: %s is a sealed run; its text is never shown (CONSOLE-A)" % Path(run).name)
    run = Path(run)
    if (_json(run / "status.json") or {}).get("exposure") == "sealed":
        raise sealed
    for folder in [run] + list(run.parents)[:3]:
        if (folder / "sealed_manifest.json").exists():
            raise sealed
        for name in SEAL_RECORDS:
            if not (folder / name).is_file():
                continue
            try:
                record = _json(folder / name)
            except ValueError:
                raise sealed from None
            if record is None or record.get("exposure") == "sealed":
                raise sealed


VIOLATIONS_DIR = Path("audit") / "contract_violations"


def _violation_header(path):
    """The lines Python writes above a set-aside reply (agent, why, size), never the reply itself."""
    import ast
    head = {}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# ---"):
            break
        key, sep, value = line[2:].partition(": ") if line.startswith("# ") else ("", "", "")
        if sep and key in ("agent", "missing_fields", "raw_text_bytes"):
            head[key] = value.strip()
    try:
        missing = ast.literal_eval(head.get("missing_fields", "[]"))
    except (ValueError, SyntaxError):
        missing = [head.get("missing_fields", "")]
    size = head.get("raw_text_bytes", "")
    return {"agent": head.get("agent") or Path(path).name.split("_", 1)[0],
            "missing": [str(m) for m in (missing if isinstance(missing, list) else [missing])],
            "bytes": int(size) if size.isdigit() else None}


def _run_status(run):
    """What the run's own records say about how it ended: the runner's result beside the run folder
    (evidence/result.json), the pipeline's completion record and the set-aside replies' headers.
    `recorded` false when none of these was given."""
    run = Path(run)
    result = _json(run.parent / "result.json") if run.name == "run" else None
    completion = _json(run / "audit" / "run_completion.json")
    folder = run / VIOLATIONS_DIR
    violations = [_violation_header(p) for p in sorted(folder.glob("*.txt"))] if folder.is_dir() else []
    status = {"recorded": result is not None, "violations": violations}
    if result is not None:
        status.update(integrity_passed=result.get("execution_integrity_passed") is True,
                      reasons=[str(r) for r in result.get("reasons") or []],
                      exit_code=result.get("pipeline_exit_code"))
    if completion is not None:
        status.update(reached_end=completion.get("reached_end"), semantic_complete=completion.get("semantic_complete"))
    return status


def _both(render, item):
    return {"en": render(item, output_language="en"), "tr": render(item, output_language="tr")}


def _documents(folder, rounds_record):
    if folder is None:
        return None
    import text_extract
    found = {}
    for path in sorted(Path(folder).iterdir()):
        if path.is_file() and path.suffix.lower() in DOCUMENT_SUFFIXES:
            found[path.stem] = {"document_id": path.stem, "name": path.name,
                                "text": text_extract.extract_text(path).replace("\r\n", "\n")}
    order = []
    manifest = (rounds_record or {}).get("manifest") or {}
    for rnd in sorted(manifest.get("rounds") or [], key=lambda r: r["sequence"]):
        for doc_id in rnd.get("document_ids") or []:
            if doc_id in found:
                order.append(dict(found.pop(doc_id), round_id=rnd["round_id"]))
    return order + [dict(found[k], round_id=None) for k in sorted(found)]


def _round_findings(findings):
    out = []
    for f in findings or []:
        if not finding_record.is_finding(f):
            continue
        out.append({"unit_id": f.get("unit_id") or "", "rule_id": f.get("rule_id") or "",
                    "line": _both(finding_record.reader_line, f)})
    return sorted(out, key=lambda f: (f["unit_id"], f["rule_id"], f["line"]["en"]))


def _rounds(run):
    saved = _json(run / "audit" / "round_reuse.json")
    if saved is None:
        return None
    out = []
    for rnd in sorted(saved.get("rounds") or [], key=lambda r: r.get("sequence", 0)):
        docs = []
        for doc in rnd.get("documents") or []:
            docs.append({"document_id": doc.get("document_id"),
                         "units": [{"unit_id": u.get("unit_id"), "status": u.get("status"),
                                    "reused_from": (u.get("reused_from") or {}).get("round_id")}
                                   for u in doc.get("units") or []],
                         "findings": _round_findings(doc.get("findings"))})
        out.append({"round_id": rnd.get("round_id"), "sequence": rnd.get("sequence"), "documents": docs})
    return out


def _changes(run):
    saved = _json(run / "audit" / "version_changes.json")
    if saved is None:
        return None
    out = []
    for c in saved.get("comparisons") or []:
        sentences = [{"change": s.get("change"), "unit_id": s.get("unit_id"),
                      "before": (s.get("before") or {}).get("text"), "after": (s.get("after") or {}).get("text")}
                     for s in c.get("sentences") or []]
        figures = [{"unit_id": f.get("unit_id"), "label": f.get("label"), "earlier": f.get("earlier"),
                    "now": f.get("now"), "measure": f.get("measure")}
                   for f in c.get("figures") or [] if f.get("relation") == "changed_from_prior"]
        out.append({"round_before": c.get("round_before"), "round_after": c.get("round_after"),
                    "before": c.get("before"), "after": c.get("after"), "sentences": sentences,
                    "figures": figures})
    return out


def _positions(run):
    saved = _json(run / "audit" / "multi_round.json")
    if saved is None:
        return None, None
    order = {r["round_id"]: r["sequence"] for r in (saved.get("manifest") or {}).get("rounds") or []}
    positions = [{"round_id": r.get("round_id"), "actor_id": r.get("actor_id"), "issue_id": r.get("issue_id"),
                  "text": r.get("position"), "ref_ids": r.get("ref_ids") or []}
                 for r in saved.get("records") or [] if r.get("kind") == "position" and r.get("state") == "accepted"]
    positions.sort(key=lambda p: (p["issue_id"], p["actor_id"], order.get(p["round_id"], 0)))
    return positions, saved


def _case_questions(run):
    saved = _json(run / "audit" / "case_questions.json")
    if saved is None:
        return None, None
    movements = []
    for row in saved.get("movements") or []:
        by_model = row.get("written_by") == finding_record.WRITTEN_BY_MODEL
        movements.append({"actor_id": row.get("actor_id"), "issue_id": row.get("issue_id"),
                          "round_before": row.get("round_before"), "round_after": row.get("round_after"),
                          "outcome": row.get("outcome"), "answer": row.get("answer") if by_model else None,
                          "written_by": "model" if by_model else "python"})
    suggestions, selections, outcomes = [], [], []
    for item in saved.get("support") or []:
        if item.get("item") == "outcome" and item.get("outcome") != "suggested":
            outcomes.append({"issue_id": item.get("issue_id"), "outcome": item.get("outcome"),
                             "reason": item.get("reason")})
        if item.get("item") == "suggestion":
            suggestions.append({"issue_id": item.get("issue_id"), "party": item.get("party"),
                                "wording": item.get("suggested_wording"), "why": item.get("why"),
                                "citations": [{"passage_id": c.get("passage_id"), "round_id": c.get("round_id"),
                                               "actor_id": c.get("actor_id"), "text": c.get("text")}
                                              for c in item.get("citations") or []]})
        elif item.get("item") == "selection":
            selections.append({"issue_id": item.get("issue_id"), "party": item.get("party"),
                               "passages": len(item.get("passages") or [])})
    return movements, {"suggestions": suggestions, "selections": selections, "outcomes": outcomes}


def _review(run):
    root = run / "deliverables"
    if not root.is_dir():
        return None
    out = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        master = _json(folder / "review_data.json")
        if master is None:
            continue
        amendments = []
        for a in master.get("amendments") or []:
            if not isinstance(a, dict):
                continue
            python_built = a.get("derived_from") == "computed_finding"
            amendments.append({"location": a.get("location") or "", "rule_id": a.get("convention_ref") or "",
                               "original_text": a.get("original_text") or "",
                               "proposed_text": a.get("proposed_text") or "",
                               "comment": a.get("comment") or "",
                               "written_by": "python" if python_built else "model"})
        models = []
        for f in master.get("model_findings_not_promoted") or []:
            if isinstance(f, dict):
                models.append({"unit_id": f.get("unit_id") or "", "rule_id": finding_record.resolved_rule_id(f) or "",
                               "line": _both(finding_record.reader_line, f),
                               "model_wrote": str(f.get("explanation") or f.get("reasoning") or "")})
        out.append({"document_id": master.get("document_id") or folder.name, "amendments": amendments,
                    "model_findings": models})
    return out


def _copy_downloads(run, source_label, files_dir, case_key):
    """Byte copies of the run's own deliverables, under files/<case>/<rounds|review>/<document>/."""
    out = []
    root = run / "deliverables"
    if not root.is_dir():
        return out
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        for name in DOWNLOADS:
            src = folder / name
            if not src.is_file():
                continue
            rel = Path("files") / case_key / source_label / folder.name / name
            dest = files_dir.parent / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())
            out.append({"document_id": folder.name, "file": name, "label": DOWNLOAD_LABELS[name],
                        "source": source_label, "href": rel.as_posix(), "bytes": src.stat().st_size})
    return out


def build_case(kind, rounds, review, documents, out):
    case ={"key": kind, "kind": kind}
    files_dir = out / "files"
    downloads = []
    if rounds is not None:
        rounds = Path(rounds)
        positions, record = _positions(rounds)
        movements, support = _case_questions(rounds)
        case.update(case_id=(record or {}).get("case_id") or ((record or {}).get("manifest") or {}).get("case_id"),
                    rounds=_rounds(rounds), changes=_changes(rounds), positions=positions,
                    movements=movements, support=support)
        downloads += _copy_downloads(rounds, "rounds", files_dir, kind)
        case.setdefault("status", {})["rounds"] = _run_status(rounds)
    else:
        record = None
    if review is not None:
        review = Path(review)
        case["review"] = _review(review)
        case.setdefault("status", {})["review"] = _run_status(review)
        downloads += _copy_downloads(review, "review", files_dir, kind)
    case["documents"] = _documents(documents, record)
    case["downloads"] = downloads
    return case


def strings():
    catalog = localization.catalog()
    missing = [s for s in STRINGS if s not in catalog]
    if missing:
        raise Refused("refused: no row in the second language (tr) in scripts/ui/localization_catalog.js for: %s" % missing)
    return {"en": {s: s for s in STRINGS}, "tr": {s: catalog[s] for s in STRINGS},
            "marks": {"model": MODEL_MARK, "python": PYTHON_MARK, "selected": SELECTED_MARK,
                      "changes": CHANGES_MARK}}


def _inline(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).replace("</", "<\\/")


README = """Shimmer demo: no installation, saved examples
==============================================

Open index.html in a web browser (on Windows, double-click open_demo.bat).
It shows the saved results of two demonstration cases, one synthetic and one a
public UN text. They are not benchmark evidence. Nothing runs: no model, no
internet connection, no key and no password. The page makes no request of any
kind; the files under files/ are copies of what the saved runs wrote.

Shimmer demosu: kurulum yok, kayıtlı örnekler
=============================================

index.html dosyasını bir web tarayıcısında açın (Windows'ta open_demo.bat
dosyasına çift tıklayın). Sayfa iki gösterim örneğinin kayıtlı sonuçlarını
gösterir: biri kurgusal, biri kamuya açık bir BM metni. Bunlar kıyaslama kanıtı
değildir. Hiçbir şey çalışmaz: model, internet bağlantısı, anahtar ya da parola
kullanılmaz. Sayfa hiçbir istek yapmaz; files/ altındaki dosyalar kayıtlı
çalıştırmaların yazdıklarının kopyalarıdır.
"""
BAT = '@echo off\r\nrem Opens the Shimmer demo in the default web browser. Nothing is installed.\r\nstart "" "%~dp0index.html"\r\n'
SH = ('#!/bin/sh\n# Opens the Shimmer demo in the default web browser. Nothing is installed.\n'
      'here="$(cd "$(dirname "$0")" && pwd)"\n'
      'if command -v open >/dev/null 2>&1; then open "$here/index.html"; else xdg-open "$here/index.html"; fi\n')


def build(out, cases, *, test_material=False):
    """`cases`: {kind: {"rounds": path|None, "review": path|None, "documents": path|None}}.
    `test_material` puts a line on every screen saying the build is of invented test material (the
    checks' fixture), so a fixture build can never pass for the worked cases' results."""
    out = Path(out)
    unknown = sorted(set(cases) - set(KINDS))
    if unknown:
        raise Refused("refused: case kinds are %s, not %s" % (", ".join(KINDS), unknown))
    for given in cases.values():
        for name in ("rounds", "review", "documents"):
            if given.get(name) is not None:
                _refuse_location(given[name], REFUSED_ROOTS if name == "documents" else RUN_REFUSED_ROOTS)
    with contextlib.ExitStack() as stack:
        resolved = {}
        for kind, given in cases.items():
            entry, roots = dict(given), []
            for name in ("rounds", "review"):
                if given.get(name) is not None:
                    entry[name], root = _run_folder(given[name], name, stack)
                    _refuse_sealed(Path(entry[name]))
                    roots.append(root)
            if entry.get("documents") is None:
                entry["documents"] = _documents_in_evidence(roots, _document_ids(entry))
            resolved[kind] = entry
        return _write(out, resolved, test_material)


def _document_ids(entry):
    """The documents the given runs name: every round's documents, and each reviewed document."""
    ids = set()
    if entry.get("rounds") is not None:
        manifest = (_json(Path(entry["rounds"]) / "audit" / "multi_round.json") or {}).get("manifest") or {}
        ids |= {d for r in manifest.get("rounds") or [] for d in r.get("document_ids") or []}
    if entry.get("review") is not None:
        ids |= {p.parent.name for p in (Path(entry["review"]) / "deliverables").glob("*/review_data.json")}
    return ids


def _documents_in_evidence(roots, ids):
    """With no --documents, the one folder inside the runs' own evidence (an unpacked archive's
    evidence/, or a run folder and the folder holding it) whose documents include every document the
    runs name, matched by file name without suffix, from the first root holding exactly one such folder.
    None otherwise: the documents screen then says the texts were not included."""
    if not ids:
        return None
    for root in roots:   # the multi-round run's evidence first, then the review's
        found = set()
        for path in Path(root).rglob("*"):
            if path.is_file() and path.suffix.lower() in DOCUMENT_SUFFIXES and path.stem in ids:
                folder = path.parent
                stems = {p.stem for p in folder.iterdir() if p.is_file() and p.suffix.lower() in DOCUMENT_SUFFIXES}
                if ids <= stems:
                    found.add(folder)
        if len(found) == 1:
            return found.pop()
    return None


ARCHIVE_SUFFIXES = (".tar.gz", ".tgz")
# What a run folder of each kind must hold, to find it inside an unpacked evidence archive.
RUN_MARKERS = {"rounds": "audit/multi_round.json", "review": "deliverables/*/review_data.json"}


def _safe_members(archive):
    """Regular files and folders under evidence/, no absolute or parent path, and nothing under
    audit/model_replies/: the demo never reads a model's raw reply, so none is unpacked. The entry's
    seal records at the top are unpacked too, so a sealed archive is refused (`_refuse_sealed`)."""
    out = []
    for m in archive.getmembers():
        name = PurePosixPath(m.name)
        if m.isfile() and len(name.parts) == 1 and name.name in SEAL_RECORDS:
            out.append(m)
            continue
        if name.is_absolute() or ".." in name.parts or not name.parts or name.parts[0] != "evidence":
            continue
        if "model_replies" in name.parts or not (m.isfile() or m.isdir()):
            continue
        out.append(m)
    return out


def _run_folder(path, name, stack):
    """(run folder, where its evidence lies): a run folder as given and the folder holding it, or the
    one run folder of that kind inside a collected_evidence.tar.gz, unpacked into a temporary folder
    that `stack` removes after the build, and that archive's evidence/."""
    path = Path(path)
    if path.is_dir():
        # A run folder; or an evidence folder or batch entry holding one (run/, evidence/run/,
        # downloaded/evidence/run/); or a batch entry holding only its collected_evidence.tar.gz.
        for run in (path, path / "run", path / "evidence" / "run", path / "downloaded" / "evidence" / "run"):
            if any(run.glob(RUN_MARKERS[name])):
                return run, (path if run != path else path.parent)
        if (path / "collected_evidence.tar.gz").is_file():
            path = path / "collected_evidence.tar.gz"
    if not (path.is_file() and path.name.endswith(ARCHIVE_SUFFIXES)):
        return path, path.parent
    into = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="shimmer_demo_evidence_")))
    with tarfile.open(path, "r:gz") as archive:
        members = _safe_members(archive)
        try:
            archive.extractall(into, members=members, filter="data")
        except TypeError:  # an interpreter without extraction filters; the members are already safe
            archive.extractall(into, members=members)
    evidence = into / "evidence"
    found = sorted({p.parents[len(PurePosixPath(RUN_MARKERS[name]).parts) - 1]
                    for p in evidence.rglob(PurePosixPath(RUN_MARKERS[name]).name)
                    if p.match(RUN_MARKERS[name])})
    if len(found) != 1:
        raise Refused("refused: %s holds %d run folders with %s; unpack it and name one"
                      % (path.name, len(found), RUN_MARKERS[name]))
    return found[0], evidence


def _write(out, cases, test_material):
    if out.exists():
        if not (out / "index.html").is_file() and any(out.iterdir()):
            raise Refused("refused: %s exists and is not a demo folder" % out)
        shutil.rmtree(out)
    out.mkdir(parents=True)
    data = {"schema_version": 1, "test_material": bool(test_material),
            "cases": [build_case(kind, cases[kind].get("rounds"), cases[kind].get("review"),
                                 cases[kind].get("documents"), out) for kind in KINDS if kind in cases]}
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(DATA_MARKER) != 1:
        raise Refused("refused: %s must hold %s exactly once" % (TEMPLATE.name, DATA_MARKER))
    page = template.replace(DATA_MARKER, "var DEMO = %s;\nvar DEMO_TEXT = %s;" % (_inline(data), _inline(strings())))
    (out / "index.html").write_text(page, encoding="utf-8", newline="\n")
    (out / "README.txt").write_text(README, encoding="utf-8", newline="\n")
    (out / "open_demo.bat").write_bytes(BAT.encode("ascii"))
    (out / "open_demo.sh").write_text(SH, encoding="utf-8", newline="\n")
    return data


def _pairs(values, name):
    out = {}
    for value in values or []:
        kind, sep, path = value.partition("=")
        if not sep or not path:
            raise Refused("refused: --%s takes KIND=FOLDER, not %r" % (name, value))
        out[kind] = Path(path)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the console's demo folder from saved runs (D-S48).")
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help="the demo folder (default demo/ at the repository root, where console.html links to it)")
    for name in ("rounds", "review", "documents"):
        parser.add_argument("--" + name, action="append", default=[], metavar="KIND=FOLDER")
    parser.add_argument("--test-material", action="store_true",
                        help="say on every screen that the build is of invented test material")
    args = parser.parse_args(argv)
    cases = {}
    for name in ("rounds", "review", "documents"):
        for kind, path in _pairs(getattr(args, name), name).items():
            cases.setdefault(kind, {})[name] = path
    data = build(args.out, cases, test_material=args.test_material)
    print("demo written: %d case(s), %d file(s) to download"
          % (len(data["cases"]), sum(len(c["downloads"]) for c in data["cases"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
