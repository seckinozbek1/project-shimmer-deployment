#!/usr/bin/env python3
"""Proofs for #281 gaps 9 and 10 (D-666, D-667): the redaction gate's listed strings, its
"cannot detect" line, and the "intent unknown" warning. Every proof runs the real redaction
stage (scripts/sensitivity_layer/redaction_stage.run_redaction_phase) on invented fixtures:
an authored REDACTOR reply, no model, no network, no real document. The five-voter ensemble
is held to a refusal (or an authored verdict) so no embedding model is loaded.

415. The post-apply grep also checks the strings an operator rule LISTS in quotation marks:
     one left in a shipped file BLOCKS whatever was detected or proposed, on the NONE path,
     after other spans were applied, and for a held document; one the redactor marked is
     applied and passes. The record names the rule and the string's place, never the string.
416. A rule that lists no string and authorises no detector gets a "cannot detect" line in
     the run, on the bus and in every document's report; a rule with a listed string or a
     detector does not.
417. A convention no pattern takes as redaction intent while the ensemble cannot run is an
     "intent unknown" warning, in the run, on the bus and in every document's report; with
     the ensemble running its verdict is a decision and no warning is given.

Each proof follows scripts/effect_proof.py: neutralise, fail, restore, pass. A
neutralisation changes a declared constant or the data the rule reads, never the function
under test.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from effect_proof import prove_effect  # noqa: E402

# Invented strings, about nothing real.
LISTED_A = "Harbour Ledger Seven"
LISTED_B = "Quill Point"
LISTED_RULE = {"id": "CONV-L1", "category": "conv-confidentiality", "action": "flag",
               "rule": 'must not contain the project codes "%s" or “%s”' % (LISTED_A, LISTED_B)}
NO_DETECTOR_RULE = {"id": "CONV-L2", "category": "conv-confidentiality", "action": "flag",
                    "rule": "must not disclose the client's home address"}
FIGURE_RULE = {"id": "CONV-L3", "category": "conv-confidentiality", "action": "flag",
               "rule": "redact company turnover figures"}
DOC_TEXT = "## Entry\n\nThe work under %s continues near %s this week.\n" % (LISTED_A, LISTED_B)
NEVER = re.compile(r"(?!x)x(a)?(b)?(c)?(d)?")


class _Bus:
    def __init__(self):
        self.bodies = []

    def _post_orchestrator(self, **kwargs):
        self.bodies.append(kwargs.get("body") or {})

    def events(self):
        return [b.get("event") for b in self.bodies]

    def compiled(self):
        return next((b for b in self.bodies if b.get("event") == "REDACTION_RULES_COMPILED"), {})


class _Redactor:
    """The REDACTOR's reply, authored: {document id: spans}; None fails its contract."""

    def __init__(self, spans):
        self.spans = spans

    def run_task(self, *, work_payload, **kwargs):
        doc_id = work_payload["document_id"]
        spans = self.spans.get(doc_id, [])
        if spans is None:
            return {"ok": False, "error": "contract_violation", "contract_missing": ["json parse failure"]}
        items = [{"kind": "redaction", "span": s, "category": "confidentiality", "replacement": "[REDACTED]",
                  "method": "REDACT", "rule_id": "CONV-L1"} for s in spans]
        return {"ok": True, "parsed": {"agent": "REDACTOR", "doc_id": doc_id, "items": items}}


@contextlib.contextmanager
def ensemble(verdict=None):
    """The five-voter ensemble held: a refusal (verdict None), or an authored record."""
    import semantic_ensemble as se

    def decide(candidate, decision, **kwargs):
        if verdict is None:
            raise se.EnsembleRefusal("fixture: the ensemble is held unavailable")
        return {"result": bool(verdict), "yes": 5 if verdict else 0, "of": 5, "majority": 3,
                "votes": [], "safety_veto": None}
    with patch.object(se, "decide", decide):
        yield


def stage(td, docs, spans, conventions):
    """The real stage over `docs`. Each document ships a master and a reviewed document
    holding its text; the render writes the reviewed document from the scrubbed body, as
    the pipeline's render does. Returns (summary, bus, stderr text)."""
    from sensitivity_layer.redaction_stage import run_redaction_phase
    deliverables = {}
    for d in docs:
        folder = Path(td) / d["id"]
        folder.mkdir()
        (folder / "review_data.json").write_text(json.dumps({"amendments": []}), encoding="utf-8")
        (folder / "reviewed_document.md").write_text(d["text"], encoding="utf-8")
        deliverables[d["id"]] = {"amendments_json": str(folder / "review_data.json"),
                                 "reviewed_document": str(folder / "reviewed_document.md")}

    def render(scrubbed_master, body_red, doc, info, scrub):
        Path(info["reviewed_document"]).write_text(body_red, encoding="utf-8")
    bus, err = _Bus(), io.StringIO()
    with contextlib.redirect_stderr(err):
        summary = run_redaction_phase(bus, docs, deliverables, None, {"conventions": conventions},
                                      build_wrapper=lambda name: _Redactor(spans), render_deliverable=render)
    return summary, bus, err.getvalue()


def _doc(doc_id, text=DOC_TEXT):
    return {"id": doc_id, "name": doc_id + ".md", "text": text}


# ---------------------------------------------------------------------------- 415


def observe_listed():
    """Four documents: nothing marked (the NONE path), both listed strings marked, one
    marked and one left, and a held reply; plus the parse of the three quotation forms."""
    from sensitivity_layer.rules import listed_strings
    docs = [_doc("doc_none"), _doc("doc_both"), _doc("doc_one"), _doc("doc_held")]
    spans = {"doc_none": [], "doc_both": [LISTED_A, LISTED_B], "doc_one": [LISTED_B], "doc_held": None}
    summary, shipped, counts = {}, {}, []
    # One stage per document: the run's spans are shared across its documents, so each
    # case runs alone.
    for d in docs:
        with ensemble(), tempfile.TemporaryDirectory(prefix="shimmer_listed_") as td:
            one, bus, _err = stage(td, [d], {d["id"]: spans[d["id"]]}, [LISTED_RULE])
            summary[d["id"]] = one[d["id"]]
            shipped[d["id"]] = (Path(td) / d["id"] / "reviewed_document.md").read_text(encoding="utf-8")
            counts.append(bus.compiled().get("listed_strings"))
    out = {}
    for d in docs:
        entry = summary[d["id"]]
        found = ((entry.get("escalation") or {}).get("detail") or {}).get("listed_string_survivors")
        out[d["id"]] = {"state": entry["state"], "failure_kind": entry.get("failure_kind"),
                        "listed": sorted((f["rule_id"], f["listed"], tuple(f["artifacts"])) for f in found or []),
                        "string_in_record": any(s in json.dumps(found or []) for s in (LISTED_A, LISTED_B))}
    out["both_scrubbed"] = LISTED_A not in shipped["doc_both"] and LISTED_B not in shipped["doc_both"]
    out["compiled_counts"] = counts[0] if all(c == counts[0] for c in counts) else counts
    out["parsed"] = listed_strings('a "one" b “two” c «three» d „four“ e "one"')
    return json.loads(json.dumps(out))


LISTED_WANT = {
    "doc_none": {"state": "BLOCKED", "failure_kind": "pii_survives_in_deliverable",
                 "listed": [["CONV-L1", 1, ["reviewed_document"]], ["CONV-L1", 2, ["reviewed_document"]]],
                 "string_in_record": False},
    "doc_both": {"state": "APPLIED", "failure_kind": None, "listed": [], "string_in_record": False},
    "doc_one": {"state": "BLOCKED", "failure_kind": "pii_survives_in_deliverable",
                "listed": [["CONV-L1", 1, ["reviewed_document"]]], "string_in_record": False},
    "doc_held": {"state": "BLOCKED", "failure_kind": "pii_survives_in_deliverable",
                 "listed": [["CONV-L1", 1, ["reviewed_document"]], ["CONV-L1", 2, ["reviewed_document"]]],
                 "string_in_record": False},
    "both_scrubbed": True,
    "compiled_counts": {"CONV-L1": 2},
    "parsed": ["one", "two", "three", "four"],
}


def check_listed():
    o = observe_listed()
    return ("PASS" if o == LISTED_WANT else "FAIL", "listed strings: %s" % ("as declared" if o == LISTED_WANT else o))


# ---------------------------------------------------------------------------- 416


def observe_cannot_detect():
    rules = [LISTED_RULE, NO_DETECTOR_RULE, FIGURE_RULE]
    with ensemble(), tempfile.TemporaryDirectory(prefix="shimmer_cannot_") as td:
        summary, bus, err = stage(td, [_doc("doc_a", "## Entry\n\nNothing marked here.\n")], {"doc_a": []}, rules)
    lines = sorted(re.findall(r"rule (CONV-L\d) \([^)]*\): cannot detect", err))
    return {"lines": lines, "bus": sorted(w["id"] for w in bus.compiled().get("cannot_detect") or []),
            "report": summary["doc_a"].get("cannot_detect"), "state": summary["doc_a"]["state"]}


CANNOT_WANT = {"lines": ["CONV-L2"], "bus": ["CONV-L2"], "report": ["CONV-L2"], "state": "NONE"}


def check_cannot_detect():
    o = observe_cannot_detect()
    return ("PASS" if o == CANNOT_WANT else "FAIL", "cannot detect: %s" % ("as declared" if o == CANNOT_WANT else o))


# ---------------------------------------------------------------------------- 417

# A redaction rule in a language the phrasing patterns do not read (invented wording), an
# ordinary review rule, and an English redaction rule that compiles.
OTHER_LANGUAGE_RULE = {"id": "CONV-I1", "category": "rapor", "action": "flag",
                       "rule": "Rapor müşterinin ev adresini göstermemelidir."}
REVIEW_RULE = {"id": "CONV-I2", "category": "register", "action": "flag", "rule": "use formal register"}
ENGLISH_RULE = {"id": "CONV-I3", "category": "conv-confidentiality", "action": "flag",
                "rule": "must not contain an individual's identity number"}


def observe_intent(verdict=None):
    from sensitivity_layer.rules import redaction_rules
    conventions = [OTHER_LANGUAGE_RULE, REVIEW_RULE, ENGLISH_RULE]
    with ensemble(verdict), tempfile.TemporaryDirectory(prefix="shimmer_intent_") as td:
        compiled = redaction_rules({"conventions": conventions})
        summary, bus, err = stage(td, [_doc("doc_a", "## Entry\n\nNothing marked here.\n")], {"doc_a": []},
                                  conventions)
    return {"compiled": sorted(r["id"] for r in compiled["operator_rules"]),
            "unknown": sorted(w["id"] for w in compiled["intent_unknown"]),
            "lines": sorted(re.findall(r"convention (CONV-I\d) \([^)]*\): intent unknown", err)),
            "bus": sorted(w["id"] for w in bus.compiled().get("intent_unknown") or []),
            "report": summary["doc_a"].get("intent_unknown")}


INTENT_WANT = {"compiled": ["CONV-I3"], "unknown": ["CONV-I1", "CONV-I2"], "lines": ["CONV-I1", "CONV-I2"],
               "bus": ["CONV-I1", "CONV-I2"], "report": ["CONV-I1", "CONV-I2"]}
# The ensemble ran and said no: a decision, so nothing is unknown.
DECIDED_WANT = {"compiled": ["CONV-I3"], "unknown": [], "lines": [], "bus": [], "report": None}


def check_intent():
    o = observe_intent()
    return ("PASS" if o == INTENT_WANT else "FAIL", "intent unknown: %s" % ("as declared" if o == INTENT_WANT else o))


# ---------------------------------------------------------------------------- the proofs


def _prove(name, observe, check, neutralise):
    return prove_effect(name=name, validate=lambda: True, observe=observe, check=check, neutralise=neutralise)


def check_415():
    from sensitivity_layer import rules, scrub
    if check_listed()[0] != "PASS":
        return check_listed()
    proofs = [
        # Neutralised: the quotation marks are not read, so no rule lists a string.
        _prove("listed_strings_read_from_the_rule", observe_listed, check_listed,
               lambda: patch.object(rules, "_LISTED_STRING_RE", NEVER)),
        # Neutralised: the grep reads no shipped artifact, so a listed string left in one passes.
        _prove("listed_strings_grepped_in_every_shipped_file", observe_listed, check_listed,
               lambda: patch.object(scrub, "VERIFY_KEYS", ())),
    ]
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass: an operator rule's strings listed in "
                    "quotation marks are verified absent from every shipped file after apply; one left BLOCKS on "
                    "the NONE path, after other spans were applied, and for a held document; one marked passes; "
                    "the record names the rule and the place, never the string (#281 gap 9)" % len(proofs))


def check_416():
    from sensitivity_layer import rules, redaction_detect
    if check_cannot_detect()[0] != "PASS":
        return check_cannot_detect()
    proofs = [
        # Neutralised: listed strings not read, so the listing rule cannot be checked either.
        _prove("a_listed_string_makes_a_rule_checkable", observe_cannot_detect, check_cannot_detect,
               lambda: patch.object(rules, "_LISTED_STRING_RE", NEVER)),
        # Neutralised: no shape detector exists, so the figure rule cannot be checked either.
        _prove("a_detector_makes_a_rule_checkable", observe_cannot_detect, check_cannot_detect,
               lambda: patch.object(redaction_detect, "_SHAPES", ())),
    ]
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass: a rule with no listed string and no "
                    "detector is a 'cannot detect' line in the run, on the bus and in every document's report; a "
                    "rule with either is not (#281 gap 9)" % len(proofs))


def check_417():
    from sensitivity_layer import rules, redaction_stage
    if check_intent()[0] != "PASS":
        return check_intent()
    if observe_intent(verdict=False) != DECIDED_WANT:
        return "FAIL", "a ran ensemble's no was reported as unknown: %s" % observe_intent(verdict=False)
    real = redaction_stage.redaction_rules
    proofs = [
        # Neutralised: the ensemble's refusal record is not kept, so the unknown reads as a no.
        _prove("an_ensemble_refusal_is_not_a_no", observe_intent, check_intent,
               lambda: patch.object(rules, "_ensemble_redaction_intent", lambda text: (False, None))),
        # Neutralised: the compiled report carries no unknown, so the stage has nothing to say.
        _prove("the_stage_reports_the_unknown", observe_intent, check_intent,
               lambda: patch.object(redaction_stage, "redaction_rules",
                                    lambda registry, **kw: dict(real(registry, **kw), intent_unknown=[]))),
    ]
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass: a convention no pattern takes as "
                    "redaction intent while the ensemble cannot run is an 'intent unknown' warning in the run, on "
                    "the bus and in every document's report; a ran ensemble's no is a decision (#281 gap 10)"
                    % len(proofs))


def main():
    status = 0
    for name, fn in (("415", check_415), ("416", check_416), ("417", check_417)):
        s, detail = fn()
        print(name, s, detail)
        status |= s != "PASS"
    return status


if __name__ == "__main__":
    raise SystemExit(main())
