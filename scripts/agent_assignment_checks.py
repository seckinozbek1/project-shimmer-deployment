"""Proofs of the agent-assignment layer (D-571, D-572, D-575; scripts/agent_assignment.py), on fixtures.

The structural conditions are read from text alone; with the shipped declaration (no skip rule) every
agent is assigned and the dispatch is the old one; a declared skip rule skips its agent and the skip is
recorded; a skip below the floor is refused before any call (PROCESSOR, VERIFIER while PROCESSOR runs,
INST_FINDER unless the operator's switch turned it off, a replacement agent); the floor is data, read
from the declaration; the pipeline's two production loops dispatch only the assigned agents. Each proof
that rests on the floor is neutralised (refuse_below_floor made a no-op): the proof must then fail.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import agent_assignment as aa  # noqa: E402

TABLE = "# Results\n\n| Model | Score |\n|---|---|\n| A | 71.2 |\n| B | 68.0 |\n\nThe table compares two models (REF-0001).\n"
PROSE = "# Terms\n\nThe parties agree to the terms below.\nParagraph 2 of Article 3 applies.\n"
PER_DOC = ["PROCESSOR", "SPEECH_ACT_TAGGER", "LEGAL_ANALYST"]


class AgentAssignmentChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        audit = Path(self.temp.name) / "audit"
        self.ctx = SimpleNamespace(audit_dir=lambda: audit)

    def test_conditions_are_read_from_structure(self):
        t, p = aa.conditions(TABLE), aa.conditions(PROSE)
        self.assertEqual((t["has_table"], t["table_rows"], t["numeric_cells"], t["citation_markers"]), (True, 3, 2, 1))
        self.assertEqual((p["has_table"], p["table_rows"], p["numeric_cells"]), (False, 0, 0))
        self.assertGreaterEqual(p["citation_markers"], 1, "a declared numbered reference is counted")
        self.assertEqual(set(t), set(aa.declaration()["conditions"]))

    def test_shipped_declaration_assigns_every_agent_and_records_it(self):
        self.assertEqual(aa.declaration()["skip_rules"], [])
        self.assertEqual(aa.dispatch(self.ctx, "d1", PER_DOC, TABLE), PER_DOC)
        rows = json.loads((self.ctx.audit_dir() / aa.RECORD).read_text(encoding="utf-8"))
        self.assertEqual(rows[0]["doc_id"], "d1")
        self.assertTrue(all(d["assigned"] for d in rows[0]["decisions"].values()))

    def test_a_declared_skip_rule_skips_its_agent_and_says_why(self):
        rule = dict(agent="SPEECH_ACT_TAGGER", when=dict(has_table=True, prose_lines=1), rule="fixture rule")
        decided = aa.assign(PER_DOC, aa.conditions(TABLE), [rule])
        self.assertFalse(decided["SPEECH_ACT_TAGGER"]["assigned"])
        self.assertEqual(decided["SPEECH_ACT_TAGGER"]["rule"], "fixture rule")
        self.assertTrue(aa.assign(PER_DOC, aa.conditions(PROSE), [rule])["SPEECH_ACT_TAGGER"]["assigned"])
        with patch.object(aa, "declaration", return_value=dict(aa.declaration(), skip_rules=[rule])), \
                patch("agent_activation.not_called") as not_called:
            self.assertEqual(aa.dispatch(self.ctx, "d2", PER_DOC, TABLE), ["PROCESSOR", "LEGAL_ANALYST"])
        self.assertEqual(not_called.call_args.kwargs["state"], "unassigned")
        with self.assertRaises(aa.AssignmentRefused):
            aa.assign(PER_DOC, aa.conditions(TABLE), [dict(rule, when=dict(meaning="normative"))])

    def test_the_floor_refuses_an_assignment_below_it(self):
        found = aa.conditions(TABLE)
        for agents, rule, switched in (
                (PER_DOC, dict(agent="PROCESSOR", when=dict(has_table=True), rule="fixture"), ()),
                (["PROCESSOR", "VERIFIER"], dict(agent="VERIFIER", when=dict(has_table=True), rule="fixture"), ()),
                (["INST_FINDER", "ARCHIVIST"], dict(agent="INST_FINDER", when=dict(has_table=True), rule="fixture"), ())):
            with self.assertRaises(aa.AssignmentRefused, msg=rule["agent"]):
                aa.assign(agents, found, [rule], switched_off=switched)
        # the operator's ratified switch, not the layer, turns INST_FINDER off: that is no refusal
        aa.refuse_below_floor({"INST_FINDER": {"assigned": False}}, aa.floor(), switched_off={"INST_FINDER"})
        with self.assertRaises(aa.AssignmentRefused):
            aa.assign(PER_DOC, found, [dict(agent="LEGAL_ANALYST", when=dict(has_table=True), rule="fixture",
                                             replacement="SPEECH_ACT_TAGGER")])

    def test_the_floor_is_data(self):
        items = aa.floor()
        self.assertEqual([i["id"] for i in items], ["F1", "F2", "F3", "F4", "F5", "F6", "F7"])
        self.assertTrue(all(i["rule"] for i in items))
        rule = dict(agent="SPEECH_ACT_TAGGER", when=dict(has_table=True), rule="fixture")
        extra = items + [dict(id="FX", rule="a fixture rule", agents=["SPEECH_ACT_TAGGER"], when_assigned=None)]
        with self.assertRaises(aa.AssignmentRefused):
            aa.assign(PER_DOC, aa.conditions(TABLE), [rule], floor_items=extra)
        self.assertFalse(aa.assign(PER_DOC, aa.conditions(TABLE), [rule], floor_items=items)["SPEECH_ACT_TAGGER"]["assigned"])

    def test_the_pipeline_dispatches_only_the_assigned_agents(self):
        tree = ast.parse((ROOT / "scripts" / "pipeline.py").read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "phase_3_4_content_production")
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "dispatch" and getattr(n.func.value, "id", None) == "agent_assignment"]
        self.assertEqual(len(calls), 2, "the corpus-level and the per-document loops each ask the layer")
        loop = next(n for n in ast.walk(fn) if isinstance(n, ast.For) and getattr(n.iter, "id", None) == "PRODUCTION_AGENTS_PER_DOC")
        self.assertEqual(ast.unparse(loop.body[0]), "if agent_name not in per_doc:\n    continue",
                         "the per-document loop skips an agent the layer did not assign")
        zips = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "zip"
                and n.args and getattr(n.args[0], "id", None) == "per_doc"]
        self.assertEqual(len(zips), 1, "the per-document results are labelled by the assigned agents")


FLOOR_PROOFS = ["test_the_floor_refuses_an_assignment_below_it", "test_the_floor_is_data"]
TESTS = [n for n in dir(AgentAssignmentChecks) if n.startswith("test_")]


def _single(name):
    result = unittest.TestResult()
    AgentAssignmentChecks(name).run(result)
    return result.wasSuccessful()


def prove_neutralizations():
    proofs = []
    for name in FLOOR_PROOFS:
        before = _single(name)
        with patch.object(aa, "refuse_below_floor", lambda *a, **k: None):
            failed = not _single(name)
        after = _single(name)
        proofs.append(dict(check=name, neutralized="agent_assignment.refuse_below_floor", baseline_pass=before,
                           neutralized_fail=failed, restored_pass=after))
    return {"passed": all(p["baseline_pass"] and p["neutralized_fail"] and p["restored_pass"] for p in proofs), "proofs": proofs}


def check():
    result = unittest.TestResult()
    unittest.TestSuite(AgentAssignmentChecks(n) for n in TESTS).run(result)
    problems = result.failures + result.errors
    if problems:
        return ("FAIL", "%d failures/errors; first: %s" % (len(problems), problems[0][1].strip().splitlines()[-1]))
    proofs = prove_neutralizations()
    if not proofs["passed"]:
        return ("FAIL", "a neutralise, fail, restore, pass proof of the floor did not hold")
    return ("PASS", "%d cases and %d neutralise/fail/restore/pass proofs (D-571, D-572, D-575): structural conditions "
            "only; the shipped declaration assigns every agent; a declared skip is recorded; the floor, read as data, "
            "refuses PROCESSOR, VERIFIER while PROCESSOR runs, INST_FINDER outside its switch and any replacement"
            % (result.testsRun, len(proofs["proofs"])))


if __name__ == "__main__":
    print(check())
