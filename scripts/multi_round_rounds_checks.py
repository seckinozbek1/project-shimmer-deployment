"""Gate checks for S2b items 3 to 6 (multi-round enablement, pipeline lane).

No model, provider, network or GPU. The multi-round case phase runs for real
(multi_round_phase.execute with the pipeline's own wrapper factory,
pipeline._build_wrapper), and the model boundary is replaced below run_task by the
same stand-ins check 276 uses (reply_records_checks.backends): run_task, call_local
and the reply-record writer all execute. The case material is a declared two-round
fixture written here; its replies are authored, labelled as such, and measure
nothing about model quality.

Each item is proven by neutralise, fail, restore, pass (effect_proof). The S2
checker round 1 items add: each signature input (a rule, a vocabulary label, a
known unit) proven to matter by removing it from SIGNATURE_INPUTS; reused model
asks rebased; the production convention-parse path run once on a temporary
project root; the round findings on the bus; a renamed figure with no unit.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
import uuid
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import multi_round as mr
import multi_round_rounds as rounds
import paired_review as pr
import pairing_map as pm
import reply_records

ROOT = Path(__file__).resolve().parent.parent

RULES = [{"id": "CONV-001", "category": "conv-m01", "severity": "required",
          "rule": "A reading must lie between 10 units and 60 units."}]


def round_text(beta):
    return ("## Entry Alpha\n\nReading: 61 units\n\n"
            "## Entry Beta\n\nReading: %s units\n\n"
            "## Entry Gamma\n\nReading: 5 units\n" % beta)


def documents(beta_r2=70):
    return [{"id": "case_r1", "name": "case_r1.md", "text": round_text(40)},
            {"id": "case_r2", "name": "case_r2.md", "text": round_text(beta_r2)}]


def manifest(docs):
    sources = []
    for rnd, doc in (("r1", docs[0]), ("r2", docs[1])):
        quote = "Reading: 61 units"
        start = doc["text"].index(quote)
        sources.append({"source_id": "s_" + rnd, "round_id": rnd, "actor_id": "actor_a", "issue_id": "issue_a",
                        "document_id": doc["id"], "unit_id": "u01-entry-alpha", "char_start": start,
                        "char_end": start + len(quote), "quote": quote, "state": "accepted"})
    return {"schema_version": 1, "case_id": "declared_case", "fixture": False,
            "rounds": [{"round_id": "r1", "sequence": 1, "document_ids": [docs[0]["id"]]},
                       {"round_id": "r2", "sequence": 2, "document_ids": [docs[1]["id"]]}],
            "actors": [{"actor_id": "actor_a"}], "issues": [{"issue_id": "issue_a"}], "sources": sources}


def authored_replies(case_id="declared_case"):
    """PRE-AUTHORED REPLIES, NOT MODEL OUTPUT: one position per round, accepted."""
    proposals = [{"record_id": "p_" + r, "kind": "position", "state": "accepted", "case_id": case_id,
                  "confidence": "UNCERTAIN", "category": "semantic_interpretation", "text": "declared",
                  "actor_id": "actor_a", "issue_id": "issue_a", "round_id": r, "source_ids": ["s_" + r],
                  "position": "typed_a", "ref": "s_" + r} for r in ("r1", "r2")]
    decisions = [{"target_record_id": "p_" + r, "state": "accepted", "confidence": "UNCERTAIN",
                  "source_ids": ["s_" + r], "ref": "s_" + r, "kind": "review"} for r in ("r1", "r2")]
    return (json.dumps({"agent": "PROCESSOR", "doc_id": case_id, "items": proposals}),
            json.dumps({"agent": "VERIFIER", "doc_id": case_id, "items": decisions}))


def mocked_multi_round_run(out_root, *, beta_r2=70, plan_spy=None):
    """The real case phase, the pipeline's own wrapper factory, stand-in backends."""
    import pipeline as pl
    from harness.run_agent import build_orchestrator
    from reference_builder import ReferenceIndex
    from reply_records_checks import backends
    registry = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
    registry = dict(registry)
    registry["PROCESSOR"] = dict(registry["PROCESSOR"], backend="local_producer", model="fixture-producer")
    registry["VERIFIER"] = dict(registry["VERIFIER"], backend="local_auditor", model="fixture-auditor")
    orch = build_orchestrator(root=ROOT, out_root=Path(out_root), registry=registry)
    ctx = orch.run_context
    docs = documents(beta_r2)
    record = mr.begin(ctx, manifest(docs))
    refs = ReferenceIndex.open(ROOT, index_path=ctx.reference_index_path())
    producer, verifier = authored_replies()
    import multi_round_phase
    real_plan_calls = pr.plan_calls

    def spy(units, pairs, *args, **kwargs):
        if plan_spy is not None:
            plan_spy.append(sorted({u for u, _ in pairs}))
        return real_plan_calls(units, pairs, *args, **kwargs)
    with backends(local=[producer, verifier]), patch.object(pr, "plan_calls", spy), \
            contextlib.redirect_stderr(io.StringIO()):
        code = multi_round_phase.execute(ctx, record, docs, refs, lambda name: pl._build_wrapper(name, orch, {}),
                                         sensitive=False, convention_registry={"conventions": RULES})
    return {"code": code, "record": record, "ctx": ctx, "run_dir": ctx.run_dir}


# ---------- observations ------------------------------------------------------------------

def _round_posts(run_dir):
    """S2 checker H4: the round findings as the run bus carries them."""
    import finding_record
    bus = Path(run_dir) / "logs" / "agent_bus.jsonl"
    out = []
    lines = bus.read_text(encoding="utf-8").splitlines() if bus.is_file() else []
    for line in lines:
        msg = json.loads(line)
        body = msg.get("body") or {}
        if msg.get("channel") != "multi_round" or body.get("event") != "AGENT_OUTPUT":
            continue
        payload = body.get("payload") or {}
        if payload.get("agent") != rounds.FINDINGS_AGENT:
            continue  # the case phase's own PROCESSOR and VERIFIER outputs
        items = payload.get("items") or []
        out.append((payload.get("doc_id"), finding_record.written_by(body.get("backend"), body.get("model")),
                    sorted((i.get("unit_id"), i.get("relation")) for i in items),
                    len({i.get("item_id") for i in items}) == len(items)))
    return out


def observe_reuse():
    spy = []
    with tempfile.TemporaryDirectory(prefix="shimmer_rounds_reuse_") as td:
        run = mocked_multi_round_run(td, plan_spy=spy)
        saved = rounds.read(run["run_dir"]) or {}
        out = {"code": run["code"], "outcome": run["record"].get("outcome"),
               "round_review": run["record"].get("round_review"), "plan_units": spy, "rounds": [],
               "bus": _round_posts(run["run_dir"])}
        for rnd in saved.get("rounds", []):
            doc = rnd["documents"][0]
            out["rounds"].append({
                "round_id": rnd["round_id"],
                "status": {u["unit_id"]: u["status"] for u in doc["units"]},
                "reused_from": {u["unit_id"]: (u.get("reused_from") or {}).get("round_id") for u in doc["units"]},
                "pairs_computed": doc["pairs_computed"],
                "findings": sorted((f["unit_id"], f["relation"], f.get("value_a")) for f in doc["findings"])})
        return out


def check_reuse():
    o = observe_reuse()
    if len(o["rounds"]) != 2 or o["code"] != 0:
        return "FAIL", "case phase did not record two rounds"
    r1, r2 = o["rounds"]
    ok = (set(r1["status"].values()) == {"computed"}
          and r2["status"] == {"u01-entry-alpha": "reused", "u02-entry-beta": "computed", "u03-entry-gamma": "reused"}
          and r2["reused_from"]["u01-entry-alpha"] == "r1" and r2["reused_from"]["u03-entry-gamma"] == "r1"
          and o["plan_units"] == [["u01-entry-alpha", "u02-entry-beta", "u03-entry-gamma"], ["u02-entry-beta"]]
          and r2["pairs_computed"] == 1 and r1["pairs_computed"] == 3
          and r2["findings"] == [("u01-entry-alpha", "above_band", 61.0), ("u02-entry-beta", "above_band", 70.0),
                                 ("u03-entry-gamma", "below_band", 5.0)]
          and r1["findings"] == [("u01-entry-alpha", "above_band", 61.0), ("u03-entry-gamma", "below_band", 5.0)]
          and o["round_review"] == {"record": "audit/round_reuse.json", "availability": "recorded",
                                    "bus_envelopes": 2}
          # H4: every round document's findings are on the bus, written by Python,
          # each with its own item id so no round supersedes another.
          and o["bus"] == [("case_r1", "python", [("u01-entry-alpha", "above_band"),
                                                  ("u03-entry-gamma", "below_band")], True),
                           ("case_r2", "python", [("u01-entry-alpha", "above_band"),
                                                  ("u02-entry-beta", "above_band"),
                                                  ("u03-entry-gamma", "below_band")], True)])
    return ("PASS" if ok else "FAIL", "only the changed unit's pairs recomputed in round 2; findings on the bus")


# ---------- S2 checker A10: what the signature covers, the parse path, needs_model --------

RULE_CHANGED = dict(RULES[0], rule="A reading must lie between 10 units and 65 units.")
SCOPED_RULE = {"id": "CONV-002", "category": "conv-m02", "severity": "required",
               "rule": "[scope: reading] Each entry must say how the reading was taken."}


def signature_text(*, extra="", gamma_unit="units", lead=""):
    return (lead + "## Entry Alpha\n\nReading: 61 units\n\n"
            "## Entry Beta\n\nReading: 40 units\n%s\n"
            "## Entry Gamma\n\nReading: 5 %s\n" % (extra, gamma_unit))


def _second_round(text_r2, *, rules_r1=None, rules_r2=None):
    """Round 1 on the base text, round 2 on `text_r2`, one shared reuse table."""
    earlier = {}
    rules_r1 = rules_r1 or RULES
    rounds.review_document({"id": "d1", "text": signature_text()}, rules_r1, earlier, round_id="r1")
    rows, _, _ = rounds.review_document({"id": "d2", "text": text_r2}, rules_r2 or rules_r1, earlier,
                                        round_id="r2")
    return rows


def observe_signature():
    """Round 2 status of Entry Alpha, whose own text never changes."""
    def alpha(rows):
        return next(r["status"] for r in rows if r["unit_id"].endswith("entry-alpha"))
    return {"unchanged": alpha(_second_round(signature_text())),
            "rule": alpha(_second_round(signature_text(), rules_r2=[RULE_CHANGED])),
            "vocabulary": alpha(_second_round(signature_text(extra="Batch note: 3 units\n"))),
            "known_units": alpha(_second_round(signature_text(gamma_unit="kg")))}


def check_signature():
    o = observe_signature()
    ok = o == {"unchanged": "reused", "rule": "computed", "vocabulary": "computed", "known_units": "computed"}
    return ("PASS" if ok else "FAIL", "a changed rule, vocabulary label or known unit recomputes an unchanged unit")


def observe_moved_asks():
    """A unit inserted before the others moves every id; the reused rows' model asks follow."""
    rows = _second_round(signature_text(lead="## Entry Zero\n\nReading: 30 units\n\n"),
                         rules_r1=RULES + [SCOPED_RULE])
    return [(r["unit_id"], r["status"], sorted({n["unit_id"] for n in r.get("needs_model") or []}))
            for r in rows]


def check_moved_asks():
    o = observe_moved_asks()
    reused = [r for r in o if r[1] == "reused"]
    ok = len(reused) == 3 and all(ids == [unit_id] for unit_id, _, ids in reused)
    return ("PASS" if ok else "FAIL", "a reused unit's model asks name this round's unit id")


class _Ctx:
    """The two things review_rounds reads from a run context."""

    def __init__(self, root):
        self.project_root = root

    def audit_dir(self):
        return Path(self.project_root) / "audit"


CONVENTIONS_MD = ("# Review conventions\n\n## CONV-M01 Reading range [required]\n\n"
                  "A reading must lie between 10 units and 60 units.\n")


def observe_parse():
    """The production path: no registry passed, so the round review compiles the
    operator's conventions from input/conventions under the run's project root."""
    with tempfile.TemporaryDirectory(prefix="shimmer_rounds_parse_") as td:
        conv = Path(td) / "input" / "conventions"
        conv.mkdir(parents=True)
        (conv / "review_conventions.md").write_text(CONVENTIONS_MD, encoding="utf-8")
        docs = documents()
        rec = rounds.review_rounds(_Ctx(td), manifest(docs), docs)
        return {"availability": rec.get("availability"),
                "rounds": [([u["status"] for u in r["documents"][0]["units"]],
                            sorted((f["unit_id"], f["relation"]) for f in r["documents"][0]["findings"]))
                           for r in rec.get("rounds", [])]}


def check_parse():
    o = observe_parse()
    ok = (o["availability"] == "recorded"
          and o["rounds"] == [(["computed"] * 3, [("u01-entry-alpha", "above_band"), ("u03-entry-gamma", "below_band")]),
                              (["reused", "computed", "reused"],
                               [("u01-entry-alpha", "above_band"), ("u02-entry-beta", "above_band"),
                                ("u03-entry-gamma", "below_band")])])
    return ("PASS" if ok else "FAIL", "with no registry passed, the operator's conventions are compiled and used")


def _without(name):
    return patch.object(rounds, "SIGNATURE_INPUTS", tuple(n for n in rounds.SIGNATURE_INPUTS if n != name))


def observe_replies():
    with tempfile.TemporaryDirectory(prefix="shimmer_rounds_replies_") as td:
        run = mocked_multi_round_run(td)
        folder = reply_records.folder(run["ctx"])
        rows = reply_records.records(folder)
        current = reply_records.outcomes(folder)
        return {"code": run["code"], "outcome": run["record"].get("outcome"),
                "records": [(r["agent"], r["backend"], r["phase"], bool(r["reply"] and r["reply"].get("text")))
                            for r in rows],
                "call_ids_unique": len({r["call_id"] for r in rows}) == len(rows),
                "outcomes": [current.get(r["call_id"], "not_decided") for r in rows],
                # The case records name the very calls whose replies were saved.
                "records_name_saved_calls": sorted(
                    {rec.get("producer_call_id") for rec in run["record"]["records"]}
                    | {rec.get("reviewer_call_id") for rec in run["record"]["records"]})
                    == sorted(r["call_id"] for r in rows)}


def check_replies():
    o = observe_replies()
    ok = (o["code"] == 0 and o["outcome"] == "reviewed"
          and o["records"] == [("PROCESSOR", "local_producer", "multi_round", True),
                               ("VERIFIER", "local_auditor", "multi_round", True)]
          and o["call_ids_unique"] and o["outcomes"] == ["advisory_not_record"] * 2
          and o["records_name_saved_calls"])
    return ("PASS" if ok else "FAIL", "one saved record per multi-round call, outcome advisory_not_record")


V1 = "## Section One\n\nAlpha count: 42 units\nBeta level: 17 units\nGamma total: 9 units\n"


# S2 checker A9: the same section with figures that carry no unit of measure.
V1_NO_UNIT = "## Section One\n\nAlpha count: 42\nBeta level: 17\nGamma total: 9\n"


def _absent(v2_lines, v1=V1):
    v2 = "## Section One\n\n" + "".join(line + "\n" for line in v2_lines)
    index = pr.prior_index(v1, lambda i: "REF-0001", known_units=set())
    units = pm.split_units(v2, document_id="v2")
    present = set()
    for unit in units:
        present |= pm.unit_fields(unit.get("text", ""))
    unit = units[0]
    scalars, _, _ = pr.extract_fields(unit.get("text", ""), known_units=set())
    slug = unit["unit_id"].split("-", 1)[1]
    hits, _ = pr.prior_lookup(index, scalars, slug)
    checks, refused = pr.absent_checks(index, present, slug, scalars=scalars, hits=hits)
    return ({c["stated_field"]: c["relation"] for c in checks},
            {r["label"]: r["reason"].split(":")[0] for r in refused})


def observe_rename():
    moved = round(17 * 1.25, 2)   # the value moved by a quarter: far outside rename_tolerance()
    return {
        "renamed_kept": _absent(["Alpha count: 42 units", "Beta score: 17 units", "Gamma total: 9 units"]),
        "renamed_moved": _absent(["Alpha count: 42 units", "Beta score: %s units" % moved, "Gamma total: 9 units"]),
        "withdrawn": _absent(["Alpha count: 42 units", "Beta level: 17 units"]),
        "withdrawn_other_measure": _absent(["Alpha count: 42 units", "Beta level: 17 units", "Delta share: 3 kg"]),
        "no_unit_renamed_moved": _absent(["Alpha count: 42", "Beta score: %s" % moved, "Gamma total: 9"], V1_NO_UNIT),
        "no_unit_withdrawn": _absent(["Alpha count: 42", "Beta level: 17"], V1_NO_UNIT),
    }


def check_rename():
    o = observe_rename()
    kept_minted, kept_refused = o["renamed_kept"]
    moved_minted, moved_refused = o["renamed_moved"]
    gone_minted, gone_refused = o["withdrawn"]
    other_minted, other_refused = o["withdrawn_other_measure"]
    bare_minted, bare_refused = o["no_unit_renamed_moved"]
    bare_gone_minted, bare_gone_refused = o["no_unit_withdrawn"]
    ok = ("beta level" not in kept_minted and kept_refused.get("beta level") == "possible rename, not a confirmed withdrawal"
          and "beta level" not in moved_minted
          and moved_refused.get("beta level") == "possible rename with a moved value, not a confirmed withdrawal"
          and gone_minted == {"gamma total": "absent_since_prior"} and not gone_refused
          and other_minted == {"gamma total": "absent_since_prior"} and not other_refused
          # A9: with no unit on either figure, the unit cannot tell them apart, so
          # the possible rename is refused under its own reason, never minted.
          and "beta level" not in bare_minted
          and bare_refused.get("beta level") == "possible rename of a figure with no unit, not a confirmed withdrawal"
          and bare_gone_minted == {"gamma total": "absent_since_prior"} and not bare_gone_refused)
    return ("PASS" if ok else "FAIL", "renamed-and-moved refused, with or without a unit; true withdrawal minted")


# Check 261 strips exactly these five statements of main and these two parser flags,
# then compares every function hash with the pinned contract. S2b leaves all seven as
# they were at the stage base: their AST digests are pinned here, so an edit to any
# of them fails this check (and would need check 261's own change, under IV.6).
_TESTS = {"args.multi_round or args.multi_round_manifest", "multi_manifest is not None", "multi_record is not None"}
_FLAGS = {"--multi-round", "--multi-round-manifest"}


def stripped_statements(source):
    tree = ast.parse(source)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    parser = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_build_arg_parser")
    statements = []
    for s in main.body:
        if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name) \
                and s.targets[0].id in {"multi_record", "multi_manifest"}:
            statements.append(s)
        elif isinstance(s, ast.If) and ast.unparse(s.test) in _TESTS:
            statements.append(s)
    flags = [s for s in parser.body if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)
             and s.value.args and isinstance(s.value.args[0], ast.Constant) and s.value.args[0].value in _FLAGS]
    return [hashlib.sha256(ast.dump(s, include_attributes=False).encode()).hexdigest()[:16]
            for s in statements + flags]


# The seven digests at the stage base (d830cee), measured with stripped_statements:
# main's two assignments and three branches, then the two parser flags, in order.
BASE_STRIPPED = ["aa2c2b68a153aedc", "6d1a31688d5f9332", "9d2477941680e5c8", "aa0cf8ac2100fc5d",
                 "172bf358a00be93b", "7ed8802292da0134", "e8ad2dcad3f0b193"]


def observe_check261_structure():
    source = (ROOT / "scripts" / "pipeline.py").read_text(encoding="utf-8")
    return {"digests": stripped_statements(source)}


def check_check261_structure():
    o = observe_check261_structure()
    ok = len(o["digests"]) == 7 and o["digests"] == BASE_STRIPPED
    return ("PASS" if ok else "FAIL", "five stripped statements and two parser flags unchanged")


class _EditedMain:
    """Neutralisation: the pipeline source as read here, with one stripped statement
    edited (the case-phase return code changed), as an S2b edit there would be."""

    def __enter__(self):
        real = Path.read_text

        def read_text(path, *args, **kwargs):
            text = real(path, *args, **kwargs)
            if Path(path).name == "pipeline.py" and Path(path).parent.name == "scripts":
                text = text.replace("            return 8\n    activation_agents", "            return 9\n    activation_agents", 1)
            return text
        self.patch = patch.object(Path, "read_text", read_text)
        self.patch.__enter__()
        return self

    def __exit__(self, *exc):
        return self.patch.__exit__(*exc)


class MultiRoundRoundsChecks(unittest.TestCase):
    def prove(self, name, observe, check, neutralise):
        from effect_proof import prove_effect
        prove_effect(name=name, validate=lambda: mr.validate_manifest(manifest(documents())) is not None,
                     observe=observe, check=check, neutralise=neutralise)

    def test_s2b3_later_round_reruns_only_what_changed(self):
        self.prove("s2b3_reuse", observe_reuse, check_reuse,
                   lambda: patch.object(rounds, "unit_signature", lambda *a, **k: uuid.uuid4().hex))

    def test_h4_round_findings_reach_the_bus(self):
        self.prove("h4_round_bus", observe_reuse, check_reuse,
                   lambda: patch.object(rounds, "post_findings", lambda *a, **k: 2))

    def test_a10_a_changed_rule_recomputes(self):
        self.prove("a10_rule", observe_signature, check_signature, lambda: _without("rules"))

    def test_a10_a_changed_vocabulary_recomputes(self):
        self.prove("a10_vocabulary", observe_signature, check_signature, lambda: _without("vocabulary"))

    def test_a10_a_changed_known_unit_recomputes(self):
        self.prove("a10_known_units", observe_signature, check_signature, lambda: _without("known_units"))

    def test_a10_reused_model_asks_are_rebased(self):
        self.prove("a10_asks", observe_moved_asks, check_moved_asks,
                   lambda: patch.object(rounds, "_rebase_asks", lambda asks, unit_id: asks))

    def test_a10_the_convention_parse_path_runs(self):
        import convention_parser
        self.prove("a10_parse", observe_parse, check_parse,
                   lambda: patch.object(convention_parser, "parse_conventions",
                                        lambda root: convention_parser.ConventionRegistry()))

    def test_s2b4_every_multi_round_reply_saved_once(self):
        self.prove("s2b4_replies", observe_replies, check_replies,
                   lambda: patch.object(reply_records, "write", lambda *a, **k: None))

    def test_s2b5_renamed_and_moved_is_not_withdrawn(self):
        self.prove("s2b5_rename", observe_rename, check_rename,
                   lambda: patch.object(pr, "possible_successor", lambda *a, **k: None))

    def test_a9_renamed_figure_with_no_unit_is_not_withdrawn(self):
        # Neutralised: the successor test requires a unit, as the value test does.
        real = pr.possible_successor
        self.prove("a9_no_unit_rename", observe_rename, check_rename,
                   lambda: patch.object(pr, "possible_successor",
                                        lambda unit, *a, **k: real(unit, *a, **k) if unit else None))

    def test_s2b6_check_261_statements_left_as_they_are(self):
        self.prove("s2b6_check261", observe_check261_structure, check_check261_structure, _EditedMain)


def check():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MultiRoundRoundsChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(case).split(" ")[0] + ": " + str(err).strip().splitlines()[-1][:160]
                    for case, err in list(result.failures) + list(result.errors)]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", ("%d S2b proofs, each neutralise, fail, restore, pass: a later round recomputes only the "
                    "changed unit's pairs and records the reuse; a changed rule, vocabulary label or known "
                    "unit recomputes an unchanged unit; reused model asks carry the new unit id; the "
                    "convention-parse path runs; the round findings reach the bus; every multi-round reply "
                    "saved once as advisory_not_record; a renamed term whose value moved, or that has no "
                    "unit, is refused, not withdrawn; check 261's stripped statements unchanged"
                    % result.testsRun)


if __name__ == "__main__":
    status, detail = check()
    print(status, detail)
