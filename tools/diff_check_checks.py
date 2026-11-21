#!/usr/bin/env python3
"""Check 689 (#309, D-847, D-848; docs/fix/DIFF_CHECK_309.md): the difference check between a source text and a
proposed text, a post step that changes no prompt, answer, finding or score.

The proofs, on invented texts and a scripted judge (no model, no key, nothing launched, nothing written in the
repository):

1. align: structure only. A sentence standing in both texts is no change; two edited sentences pair with their own
   partners (changed, with the words removed and added); a new sentence is added; a sole leftover on each side is
   one changed sentence; an amendment's proposed line replaces the one sentence of its unit most like it.
2. judged: one question per declared kind per change, each the template's rendering; a scripted judge saying Yes
   to one statement flags that kind alone under a threshold; the shipped threshold is 0.999 (D-855, in-sample,
   development only): a 0.9 answer stays 'cannot be settled' and flags nothing, a 0.9995 Yes flags its kind; with
   the threshold set to null every question decides 'cannot be settled' and nothing is flagged; every record is marked model-written, promoted false,
   checked_by_python false; a judge refusal is recorded, not raised.
3. red_line (D-848): the advised party's red lines are read by neg_advisor.party_red_lines (persona.red_lines,
   its own positions only, and the operator's, #278); each changed or added proposed sentence gets one red-line
   question per line, a removed sentence none; the scripted judge's Yes flags red_line:N.
4. quote: a change whose span does not stand in its text is refused on the record and asked nothing.
5. run_folder: off, write_run writes nothing and every file keeps its bytes; on, it writes audit/diff_check.json,
   deliverables/<doc>/diff_check.md and ONE line at the end of reviewed_document.md and _run_summary.md, the bytes
   before it unchanged, review_data.json unchanged, and a second run adds no second line.
6. replay: the shipped accuracy set becomes a doc_judge choice prompts file that load_prompts accepts, every
   question the check's own byte for byte, no expected kind in the file; the set declares 5 pairs per kind, red-line
   pairs and no-change pairs.
7. additive: no module the measured runs import (scripts/, benchmark/baselines/, benchmark/adapters/) imports
   diff_check, and the bundle archive rule (tools/prepare_ordinary_final_run.archive_names) carries none of its files.

Run as built (passes), neutralised four times (the quote check always true; the similarity pairing returning none;
the line written over the file instead of after it; the red lines on the record read as none), each must fail,
restored and run again (passes).
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "tools", ROOT / "scripts", ROOT / "benchmark" / "baselines"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import diff_check as dc  # noqa: E402

SET = ROOT / "benchmark" / "fixtures" / "diff_check_309" / "accuracy_set.json"


def config(**over):
    return dict(dc.load_config(), **over)


def scripted(yes_on, sure=0.9):
    """A judge answering Yes with `sure` when the question holds `yes_on`, No with `sure` otherwise."""
    def judge(text, answers):
        top = "yes" if yes_on and yes_on in text else "no"
        rows = [{"label": a["label"], "surface": a["surface"], "token_id": n,
                 "probability": sure if a["label"] == top else (1.0 - sure) / 2} for n, a in enumerate(answers)]
        return {"schema": "choice-decision-v1", "answers": rows, "declared_mass": 0.97, "undeclared_top": None}
    return judge


def refusing(text, answers):
    import choice_decision
    raise choice_decision.ChoiceRefused("scripted refusal")


@contextlib.contextmanager
def patched(owner, name, value):
    old = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield
    finally:
        setattr(owner, name, old)


def caught(fn):
    try:
        return fn()
    except Exception as exc:
        return "raised %s" % type(exc).__name__


# ---- proofs -----------------------------------------------------------------------------------

def observe_align():
    cfg = config()
    src = ("The Supplier shall deliver the goods within thirty days of the order. The Buyer shall pay each invoice "
           "within sixty days of receipt. This Agreement is governed by the law of the seat.")
    new = ("The Supplier shall deliver the goods within thirty days of the order unless the Buyer agrees otherwise. "
           "The Buyer shall pay each invoice within ninety days of receipt. This Agreement is governed by the law of "
           "the seat. Notices are given in writing.")
    rows = dc.align(src, new, cfg)
    sole = dc.align("The Supplier may suspend deliveries if the Buyer has not paid an invoice within sixty days.",
                    "The Supplier may suspend deliveries at any time.", cfg)
    rep = dc.replacement("The rate is reported by the station each season. The rate stays within the declared band for each season.",
                         "The rate stays within the declared band for the season.", cfg)
    return {"changes": sorted((r["change"], (r["source"] or {}).get("text", "")[:24], (r["proposed"] or {}).get("text", "")[:24])
                              for r in rows),
            "words": sorted(tuple(r.get("words_added") or ()) for r in rows if r["change"] == "changed"),
            "sole": [r["change"] for r in sole],
            "replacement": [(r["change"], r["source"]["text"][:12]) for r in rep]}


def expected_align():
    return {"changes": [("added", "", "Notices are given in wri"),
                        ("changed", "The Buyer shall pay each", "The Buyer shall pay each"),
                        ("changed", "The Supplier shall deliv", "The Supplier shall deliv")],
            "words": [("ninety",), ("order unless the Buyer agrees otherwise.",)],
            "sole": ["changed"],
            "replacement": [("changed", "The rate sta")]}


def _pair(src, new):
    return dc._pair("pair", "p1", src, new)


SRC = "The Tenant may sublet the premises with the prior written consent of the Landlord."
NEW = "The Tenant may sublet the premises."


def observe_judged():
    cfg = config()
    kinds = {k["kind"]: k["statement"] for k in cfg["kinds"]}
    flagged = dc.check([_pair(SRC, NEW)], [], scripted(kinds["dropped_condition"]), config(threshold=0.8))
    shipped = dc.check([_pair(SRC, NEW)], [], scripted(kinds["dropped_condition"]), cfg)
    sure = dc.check([_pair(SRC, NEW)], [], scripted(kinds["dropped_condition"], 0.9995), cfg)
    unset = dc.check([_pair(SRC, NEW)], [], scripted(kinds["dropped_condition"], 0.9995), config(threshold=None))
    refused = dc.check([_pair(SRC, NEW)], [], refusing, config(threshold=0.8))
    row = flagged["changes"][0]
    texts = [q["text"] for q in dc.questions(dc.align(SRC, NEW, cfg)[0], [], cfg)]
    return {"asked": [q["kind"] for q in row["questions"]], "flags": row["flags"],
            "marked": (row["mark"], row["promoted"], row["checked_by_python"], row["written_by"]),
            "rendered": all(t == dc.render(cfg, s, dc.change_block(dc.align(SRC, NEW, cfg)[0], cfg))
                            for t, s in zip(texts, kinds.values())),
            "shipped": (cfg["enabled"], cfg["threshold"], shipped["changes"][0]["flags"],
                        sorted({q["decided"] for q in shipped["changes"][0]["questions"]})),
            "shipped_sure": sure["changes"][0]["flags"],
            "unset": (unset["changes"][0]["flags"], sorted({q["decided"] for q in unset["changes"][0]["questions"]})),
            "refused": (refused["counts"]["refused"], refused["changes"][0]["flags"])}


def expected_judged():
    cfg = config()
    return {"asked": [k["kind"] for k in cfg["kinds"]], "flags": ["dropped_condition"],
            "marked": (dc.MARK, False, False, "model"), "rendered": True,
            "shipped": (False, 0.999, [], ["cannot be settled"]), "shipped_sure": ["dropped_condition"],
            "unset": ([], ["cannot be settled"]), "refused": (len(cfg["kinds"]), [])}


ITEM = {"item_id": "fx1", "persona": {"id": "A", "kind": "state", "red_lines": ["POS-1", "POS-9"],
                    "operator_red_lines": [{"id": "OP-1", "text": "No transfer without notice."}]},
        "positions": [{"id": "POS-1", "party": "A", "quote": "Data stays within the region at all times.", "round": 1},
                      {"id": "POS-2", "party": "A", "quote": "A three year term suits us.", "round": 1},
                      {"id": "POS-9", "party": "B", "quote": "We need worldwide hosting.", "round": 1}],
        "articles": [{"id": "4", "proposals": [{"id": "P-4-1", "text": "The Processor shall host the data within the region."}]}]}
PARSED = {"proposals": {"P-4-1": {"id": "P-4-1", "stance": "counter",
                                  "wording": "The Processor may host the data in any country."}}}


def observe_red_line():
    lines = dc.red_lines_from_item(ITEM)
    pairs = dc.negotiation_pairs(ITEM, PARSED)
    rec = dc.check(pairs, lines, scripted("Data stays within the region"), config(threshold=0.8))
    removed = dc.questions({"change": dc.REMOVED, "source": {"text": "x y z w"}, "proposed": None}, lines, config())
    return {"lines": [(l["party"], l["quote"], l["source"]) for l in lines],
            "pairs": [(p["origin"], p["id"]) for p in pairs],
            "red_questions": [q["red_line"] for q in rec["changes"][0]["questions"] if q["kind"] == dc.RED_LINE],
            "flags": rec["changes"][0]["flags"],
            "removed_red": [q for q in removed if q["kind"] == dc.RED_LINE],
            "bad_declared": caught(lambda: dc.declared_red_lines([{"party": "A"}]))}


def expected_red_line():
    return {"lines": [("A", "Data stays within the region at all times.", "from the document"),
                      ("A", "No transfer without notice.", "given by the operator")],
            "pairs": [("negotiation_counter", "P-4-1")], "red_questions": [0, 1], "flags": ["red_line:0"],
            "removed_red": [], "bad_declared": "raised DiffCheckRefused"}


def observe_quote():
    cfg = config(threshold=0.8)
    pair = dc._pair("version_change", "v1", "The Buyer shall pay within thirty days.", "The Buyer shall pay within ninety days.",
                    mode="aligned", aligned="changed")
    good = dc.check([pair], [], scripted("never"), cfg)
    real_change = dc._change

    def shifted(kind, before, after):
        row = real_change(kind, before, after)
        if row["proposed"]:
            row["proposed"] = dict(row["proposed"], text=row["proposed"]["text"].replace("ninety", "ninety-nine"))
        return row
    with patched(dc, "_change", shifted):
        bad = dc.check([pair], [], scripted("never"), cfg)
    return {"good": (len(good["changes"]), good["refused"]), "bad": (len(bad["changes"]), bad["refused"])}


def expected_quote():
    return {"good": (1, []), "bad": (0, [{"pair": "v1", "change": 0, "reason": "quote_not_in_text"}])}


def _run_folder(root):
    run = Path(root) / "run"
    doc = run / "deliverables" / "doc1"
    doc.mkdir(parents=True)
    (doc / "review_data.json").write_text(json.dumps({"amendments": [
        {"ref": "u02", "original_text": "Rate: 61 units. " + SRC, "proposed_text": NEW, "finding_unit_id": "u02-rate"},
        {"ref": "u03", "original_text": "Nothing proposed here.", "proposed_text": None}]}), encoding="utf-8")
    (doc / "reviewed_document.md").write_text("# Reviewed\n\nThe body as rendered.\n", encoding="utf-8", newline="\n")
    (run / "deliverables" / "_run_summary.md").write_text("# Run summary\n\nCounts.", encoding="utf-8", newline="\n")
    return run


def _bytes(run):
    return {str(p.relative_to(run)): p.read_bytes() for p in sorted(run.rglob("*")) if p.is_file()}


def observe_run_folder():
    with tempfile.TemporaryDirectory() as tmp:
        run = _run_folder(tmp)
        before = _bytes(run)
        off = dc.write_run(run, scripted("never"), (), config())
        after_off = _bytes(run)
        on = dc.write_run(run, scripted("never"), (), config(enabled=True))
        after_on = _bytes(run)
        dc.write_run(run, scripted("never"), (), config(enabled=True))
        twice = _bytes(run)
        record = json.loads((run / "audit" / dc.RECORD_NAME).read_text(encoding="utf-8"))
        keys = {k.replace("\\", "/"): k for k in after_on}
        rd, rs = keys["deliverables/doc1/reviewed_document.md"], keys["deliverables/_run_summary.md"]
        added = after_on[rd][len(before[rd]):].decode("utf-8")
        return {"off": (off, after_off == before),
                "written": sorted(str(Path(p).relative_to(run)).replace("\\", "/") for p in on),
                "prefix": (after_on[rd].startswith(before[rd]), after_on[rs].startswith(before[rs])),
                "line": (added.count(dc.LINE_HEAD), dc.MARK in added),
                "review_data": after_on[keys["deliverables/doc1/review_data.json"]] == before[keys["deliverables/doc1/review_data.json"]],
                "once": twice[rd].decode("utf-8").count(dc.LINE_HEAD),
                "record": (record["counts"]["changes"], record["changes"][0]["origin"], record["changes"][0]["promoted"])}


def expected_run_folder():
    return {"off": (None, True),
            "written": ["audit/diff_check.json", "deliverables/_run_summary.md", "deliverables/doc1/diff_check.md",
                        "deliverables/doc1/reviewed_document.md"],
            "prefix": (True, True), "line": (1, True), "review_data": True, "once": 1,
            "record": (1, "amendment", False)}


def observe_replay():
    import doc_judge
    cfg = config()
    value = dc.load_set(SET)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "p.json"
        built = dc.replay_prompts(SET, out, cfg)
        text = out.read_text(encoding="utf-8")
        loaded = doc_judge.load_prompts(out)
    per = {}
    for p in value["pairs"]:
        for k in p["expected"] or ["none"]:
            per[k] = per.get(k, 0) + 1
    own = {}
    for p in value["pairs"]:
        for change in dc.align(p["source"], p["proposed"], cfg):
            for q in dc.questions(change, dc.declared_red_lines(p.get("red_lines")), cfg):
                own.setdefault(p["id"], []).append(q["text"])
    return {"loaded": len(loaded) == built["prompt_count"],
            "same": all(q["user"] in own[q["document_id"]] for q in built["prompts"]),
            "keys_absent": ('"expected"' not in text and '"tolerated"' not in text),
            "per_kind": {k: per[k] for k in sorted(per)}}


def expected_replay():
    return {"loaded": True, "same": True, "keys_absent": True,
            "per_kind": {"dropped_condition": 5, "none": 3, "obligation_to_statement": 5, "one_way_ban": 5,
                         "red_line": 1, "widened_scope": 6}}


def observe_additive():
    import ast
    import prepare_ordinary_final_run as prep
    importers = []
    for folder in ("scripts", "benchmark/baselines", "benchmark/adapters"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            name = path.relative_to(ROOT).as_posix()
            if name.endswith("_checks.py") or name.startswith("scripts/verify_"):
                continue        # gate files: never in a bundle, never run by a measured pass
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                if any(n.split(".")[0] in ("diff_check", "diff_check_checks") for n in names):
                    importers.append(str(path.relative_to(ROOT)))
    ours = ["tools/diff_check.py", "tools/diff_check.json", "tools/diff_check_checks.py",
            "benchmark/fixtures/diff_check_309/accuracy_set.json", "scripts/verify_session1.py"]
    shipped = ["scripts/pipeline.py", "benchmark/baselines/doc_judge.py"]
    return {"importers": importers, "archived": prep.archive_names(ours + shipped, extras=("benchmark/baselines/",))}


def expected_additive():
    return {"importers": [], "archived": ["scripts/pipeline.py", "benchmark/baselines/doc_judge.py"]}


PROOFS = ("align", "judged", "red_line", "quote", "run_folder", "replay", "additive")


def _overwrite(path, line):
    path.write_text(line + "\n", encoding="utf-8")
    return True


NEUTRALISATIONS = {
    "quote": ((dc, "_quote_holds", lambda span, text: True), ("quote",)),
    "pairing": ((dc.version_changes, "_paired", lambda a, b, t: []), ("align",)),
    "append": ((dc, "_append_line", _overwrite), ("run_folder",)),
    "red_lines": ((dc, "red_lines_from_item", lambda item: []), ("red_line",)),
}


def run():
    space = globals()
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            first = {n: space["observe_" + n]() for n in PROOFS}
            broken = {}
            for name, (patch, proofs) in NEUTRALISATIONS.items():
                with patched(*patch):
                    broken[name] = {n: caught(space["observe_" + n]) for n in proofs}
            again = {n: space["observe_" + n]() for n in PROOFS}
        expected = {n: space["expected_" + n]() for n in PROOFS}
    except Exception as exc:
        return "FAIL", "%s %s" % (type(exc).__name__, str(exc)[:300])
    for n in PROOFS:
        if first[n] != expected[n]:
            return "FAIL", "%s as built: %s" % (n, str(first[n])[:900])
        if again[n] != expected[n]:
            return "FAIL", "%s after restore: %s" % (n, str(again[n])[:400])
    for name, (_patch, proofs) in NEUTRALISATIONS.items():
        for n in proofs:
            if broken[name][n] == expected[n]:
                return "FAIL", "%s still passes when %s is neutralised" % (n, name)
    return "PASS", ("%d proofs, %d neutralisations, fail, restore, pass, no model: changed sentences placed by "
                    "structure; one question per kind and red line to a scripted judge, a flag only when settled, "
                    "a 0.9 answer unsettled under the shipped 0.999 (D-855), nothing settled with a null "
                    "threshold; every record marked a model's and never "
                    "promoted; a quote not in its text refused; off writes nothing, on adds one line after the "
                    "rendered bytes; the accuracy set replays as doc_judge choice prompts; no measured path imports "
                    "it (%s)" % (len(PROOFS), len(NEUTRALISATIONS), ", ".join(PROOFS)))


if __name__ == "__main__":
    status, detail = run()
    print("689", status, detail)
