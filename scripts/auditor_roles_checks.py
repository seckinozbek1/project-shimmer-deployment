"""D-S57 item 1, the auditor backend's roles (lane/auditor): proofs on fixtures, no model.

1. A unit that carries only its heading is asked no model question (judged absence or
   uncomputable): each question not asked is recorded with its reason, and a unit with any
   other line is asked exactly as before. The preamble's own test is the same function, so the
   preamble rule of UNITS-A is unchanged.
2. The envelope grammar's declared enumerations and string bounds (check 297's file,
   EnumerationAndBoundChecks), neutralised by dropping both.
3. The four RELATIONS-A relations make no judging call under semantic waves (open item 78),
   neutralised by restoring the old set.
4. The local role-to-model map is the registry's `local` blocks; the driver holds no table.
5. PRACTICE_AUDITOR's rule check (judged-absence and uncomputable plans), one narrow question
   decided from the model's own probabilities (config/auditor_questions.json): asked only once
   adopted and measured, the prompt the rule's words and the unit's text alone, a settled not met
   one model-written record naming the field Python found absent on a judged absence (none when
   the rule names no single one, none on an uncomputable plan), the driver's own branch run with
   stand-ins.
6. VERIFIER's pair fidelity as one narrow question per pair auditor_pairs built, decided from
   probabilities: the evidence Auditor896 is shown, an item per settled answer joined to its pair,
   posted under the model, and the driver's phase-5 branch taking it only once adopted.
7. tools/build_auditor_training.py's rows are the rule check exactly as sent, by the declared
   plan, the held-out side by group, the overlap removed and counted, no share-alike row in
   permissive_mix, byte-identical across builds.
8. tools/build_auditor_questions.py's development questions are each byte for byte the driver's
   rule check on its unit and rule, and each answer the release's annotation of that unit.
9. benchmark/baselines/auditor_train.py: a recipe only from the shipped rule check's rows and
   questions, no development question a training row, and the session on the replay pass
   (judge_train.train on a tiny random model on the CPU, every pass by a stand-in backend),
   one reply record per question where the runner counts.
10. D-S59: config/role_graph.json's roles and needs, a cycle and an order against a dependency
   refused, independent roles at once on their models' lanes in the existing scheduler, and the
   graph that ran saved in execution_topology.json, equal to the scheduler's own tasks and times.
11. D-313: Python's claim-coverage record on each pair, beside VERIFIER and Auditor896, never in
   what VERIFIER is shown.
12. D-330: benchmark/baselines/auditor_read.py reads half A alone, and half B only after a committed
   opening row and a committed passed half-A record, at alpha 0.05 / 2^k.
Gate check 333 runs check(): every proof, then neutralise, fail, restore, pass for each.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "tools", ROOT / "benchmark" / "baselines"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import paired_review  # noqa: E402
import pairing_map  # noqa: E402


def _plans(text, rule):
    units = {"u01-s": {"unit_id": "u01-s", "title": "S", "text": text, "index": 1}}
    sink = []
    plans = paired_review.plan_calls(units, [("u01-s", rule["id"])], {rule["id"]: rule}, {},
                                     unasked_sink=sink)
    return plans, sink


class HeadingOnlyUnitChecks(unittest.TestCase):
    SCOPED = {"id": "CONV-001", "rule": "Each entry states its reviewer when it applies.",
              "scope": ["entry"]}
    PLAIN = {"id": "CONV-002", "rule": "The section explains its purpose."}

    def test_a_heading_only_unit_is_asked_nothing_and_says_so(self):
        for rule, kind in ((self.SCOPED, "absence_judged"), (self.PLAIN, "uncomputable")):
            with self.subTest(kind=kind):
                plans, sink = _plans("## S\n\n---\n", rule)
                self.assertEqual(plans, [])
                self.assertEqual(sink, [{"unit_id": "u01-s", "rule_id": rule["id"], "kind": kind,
                                         "reason": paired_review.HEADING_ONLY_UNIT}])

    def test_a_unit_with_text_is_asked_as_before(self):
        for rule, kind in ((self.SCOPED, "absence_judged"), (self.PLAIN, "uncomputable")):
            with self.subTest(kind=kind):
                plans, sink = _plans("## S\n\nThe purpose is stated here.\n", rule)
                self.assertEqual([p["kind"] for p in plans], [kind])
                self.assertEqual(sink, [])
        # With no sink given the plans are the same.
        units = {"u01-s": {"unit_id": "u01-s", "text": "## S\n", "index": 1}}
        self.assertEqual(paired_review.plan_calls(units, [("u01-s", "CONV-002")], {"CONV-002": self.PLAIN}, {}), [])

    def test_the_preamble_test_is_the_same_function(self):
        self.assertIsNone(pairing_map._preamble_unit("# Title\n\n***\n"))
        self.assertEqual(pairing_map._preamble_unit("# Title\nLab: A\n")["kind"], "preamble")
        self.assertFalse(pairing_map.carries_content("# T\n## U\n - - -\n\n"))
        self.assertTrue(pairing_map.carries_content("# T\nx\n"))


class RoleToModelMapChecks(unittest.TestCase):
    """D-S57 item 2: the local role-to-model map is the registry's `local` blocks, read by the
    driver; the driver holds no table of its own."""

    def _driver(self):
        import ast
        source = (ROOT / "scripts" / ("pipe" + "line.py")).read_text(encoding="utf-8")
        return ast.parse(source)

    def test_the_driver_reads_the_registry_and_holds_no_table(self):
        import ast
        import json
        import tempfile
        tree = self._driver()
        literal = [n for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict)
                   and any(isinstance(t, ast.Name) and t.id == "_LOCAL_PROFILE" for t in n.targets)]
        self.assertEqual(literal, [])
        reader = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_registry_local_profile")
        scope = {"Path": Path, "json": json}
        exec(compile(ast.Module(body=[reader], type_ignores=[]), "<driver reader>", "exec"), scope)
        registry = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "config").mkdir()
            registry["agents"]["VERIFIER"]["local"] = {"backend": "local_auditor", "model": "fixture/auditor"}
            del registry["agents"]["FACT_CHECKER"]["local"]
            (Path(tmp) / "config" / "agent_registry.json").write_text(json.dumps(registry), encoding="utf-8")
            profile = scope["_registry_local_profile"](Path(tmp))
        self.assertEqual(profile["VERIFIER"], ("local_auditor", "fixture/auditor"))
        self.assertNotIn("FACT_CHECKER", profile)
        self.assertNotIn("REDACTOR", profile)

    def test_the_shipped_map_keeps_the_family_split(self):
        import json
        registry = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
        local = {n: s["local"]["backend"] for n, s in registry.items() if "local" in s}
        self.assertEqual(set(local), set(registry) - {"REDACTOR"})
        auditors = {n for n, b in local.items() if b == "local_auditor"}
        self.assertEqual(auditors, {"VERIFIER", "FACT_CHECKER", "PRACTICE_AUDITOR", "JUDGE", "EDITOR_HEAD_OF_DEPARTMENT",
                                    "EDITOR_DEPUTY_DG", "EDITOR_DG"})
        self.assertEqual(set(local.values()), {"local_auditor", "local_producer"})


def _decision(label, settled=True, confidence=0.9):
    import choice_decision
    return {"schema": choice_decision.SCHEMA, "decided": label if settled else choice_decision.UNSETTLED,
            "settled": settled, "confidence": confidence, "threshold": 0.5, "why": None if settled else "below_threshold",
            "answers": [], "declared_mass": 0.99}


class RuleCheckQuestionChecks(unittest.TestCase):
    """PRACTICE_AUDITOR's judged absence as one narrow question decided from the model's own
    probabilities (config/auditor_questions.json): asked only once adopted and measured, its
    prompt the rule's words and the unit's text alone, and its answer reaching the paired review's
    own judged-absence bookkeeping as the reply it reads."""

    UNIT = "## Entry 4\nClass: A\nDevice: pump {model 7}\n"
    OTHER = "## Entry 5\nClass: A\nDevice: valve\nCalibrated by: lab two\n"
    RULE = {"id": "CONV-003", "rule": "Each class A device entry states calibrated by, where it applies.",
            "scope": ["class=A"]}

    def vocabulary(self):
        return pairing_map.field_vocabulary([{"text": self.UNIT}, {"text": self.OTHER}])

    def question(self, **changes):
        import auditor_questions
        question = auditor_questions.load_config()["rule_check"]
        question.update(changes)
        return question

    def test_asked_only_once_adopted_and_measured(self):
        from unittest.mock import patch
        import auditor_questions
        shipped = self.question()
        self.assertEqual(auditor_questions.not_asked(shipped, "PRACTICE_AUDITOR"), auditor_questions.NOT_ADOPTED)
        adopted = self.question(form="decision")
        self.assertEqual(auditor_questions.not_asked(adopted, "PRACTICE_AUDITOR"), auditor_questions.NO_THRESHOLD)
        with patch.object(auditor_questions.choice_decision, "threshold", lambda family: 0.6):
            self.assertTrue(auditor_questions.asks(adopted, "PRACTICE_AUDITOR"))
            self.assertEqual(auditor_questions.not_asked(adopted, "STYLE_GUARDIAN"), auditor_questions.AGENT_DIFFERS)
        with self.assertRaises(ValueError):
            auditor_questions.not_asked(self.question(form="decide"))

    def test_the_prompt_is_the_question_and_the_evidence_alone(self):
        import auditor_questions
        import choice_decision
        question = self.question()
        prompt = auditor_questions.render_rule_check(question, self.RULE["rule"], self.UNIT)
        self.assertIn(self.RULE["rule"], prompt)
        self.assertIn("pump {model 7}", prompt)       # braces in the evidence stay
        self.assertNotIn("{rule}", prompt)
        self.assertNotIn("contract", prompt.lower())
        for answer in auditor_questions.answers(question):
            self.assertIn("\n%s: " % answer["surface"], prompt)
        with self.assertRaises(choice_decision.ChoiceRefused):
            auditor_questions.render_rule_check(question, self.RULE["rule"], "x" * question["max_prompt_chars"])

    def test_a_settled_not_met_is_one_screened_record_and_nothing_else_is(self):
        import auditor_questions
        import finding_record
        question = self.question()
        field = auditor_questions.absent_named_field(self.RULE["rule"], self.UNIT, self.vocabulary())
        self.assertEqual(pairing_map._norm_label(field), pairing_map._norm_label("Calibrated by"))
        self.assertIsNone(auditor_questions.absent_named_field(self.RULE["rule"], self.OTHER, self.vocabulary()))
        reply = auditor_questions.rule_check_reply(_decision("not_met"), question, plan_kind="absence_judged", unit_text=self.UNIT, ref="REF-0004",
                                                       field_label=field, ok=True, call_id="c1", backend="local_auditor",
                                                       model="m")
        (item,) = reply["parsed"]["items"]
        self.assertTrue(finding_record.is_finding_shaped(item))
        self.assertEqual((item["relation"], item["record_verdict"], item["ref"]), ("missing_field", "irregular", "REF-0004"))
        # A not met whose rule names no single absent field writes nothing, and says why.
        unnamed = auditor_questions.rule_check_reply(_decision("not_met"), question, plan_kind="absence_judged", unit_text=self.UNIT, ref="",
                                                         field_label=None, ok=True, call_id="c1", backend="b", model="m")
        self.assertEqual((unnamed["parsed"]["items"], unnamed["unwritten"]), ([], auditor_questions.NO_FIELD_NAMED))
        self.assertIsNone(paired_review.judged_item_refusal(dict(item, unit_id="u04", rule_id="CONV-003"), self.RULE,
                                                            pairing_map.unit_fields(self.UNIT), self.UNIT))
        for decision in (_decision("met"), _decision("not_met", settled=False),
                         _decision("cannot be settled"), None, {"decided": "not_met"}):
            got = auditor_questions.rule_check_reply(decision, question, plan_kind="absence_judged", unit_text=self.UNIT, ref="", field_label=field,
                                                         ok=decision is not None, call_id=None, backend="b", model="m")
            self.assertEqual(got["parsed"]["items"], [], decision)
            self.assertEqual(got["ok"], decision is not None)

    def test_the_drivers_branch_decides_and_hands_the_reply_on(self):
        """The driver's own branch, taken from its source and run with stand-ins for the call and
        for consume_judgment: adopted and measured, it makes one call_choice with the declared
        answers and threshold and no generated call, and hands consume_judgment the reply; not
        adopted, it falls through to the shipped call."""
        import ast
        import asyncio
        from types import SimpleNamespace
        from unittest.mock import patch
        import auditor_questions
        import choice_decision
        source = (ROOT / "scripts" / ("pipe" + "line.py")).read_text(encoding="utf-8")
        branch = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == "plan.get('kind') in ('absence_judged', paired_review_mod.UNCOMPUTABLE_PLAN)"
                      and "auditor_questions" in ast.unparse(n))
        loop = ast.AsyncFor(target=ast.Name(id="once", ctx=ast.Store()),
                            iter=ast.Call(func=ast.Name(id="_one", ctx=ast.Load()), args=[], keywords=[]),
                            body=[branch, ast.Expr(ast.Call(func=ast.Name(id="fell_through", ctx=ast.Load()),
                                                            args=[], keywords=[]))], orelse=[])
        body = ast.AsyncFunctionDef(name="body", args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[],
                                                                       defaults=[]), body=[loop], decorator_list=[], returns=None)
        module = ast.fix_missing_locations(ast.Module(body=[body], type_ignores=[]))

        def run(form, kind="absence_judged"):
            seen = {"choice": [], "consumed": [], "fell": 0}

            async def _one():
                yield 1

            def call_choice(prompt, answers, threshold):
                seen["choice"].append((prompt, answers, threshold))
                return SimpleNamespace(ok=True, parsed=_decision("not_met"), backend="local_auditor", model="m")

            def narrow_ask(orch, doc, wrapper, agent, rule, calls, **call):
                def ask(user):
                    r = call["send"](user, "")
                    call["seen"].update(backend=r.backend, model=r.model)
                    call["call_of"][user] = "call-1"
                    return call["answer_of"](r)
                return ask

            scope = dict(asyncio=asyncio, plan={"kind": kind}, agent="PRACTICE_AUDITOR",
                         rule=self.RULE, unit={"unit_id": "u04", "text": self.UNIT}, doc={"id": "d1", "text": self.UNIT},
                         orch=None, wrapper=SimpleNamespace(call_choice=call_choice, backend="local_auditor", model="m"),
                         _narrow_ask=narrow_ask, paired_review_mod=paired_review, plan_index=0, checks=[],
                         source_rule_id="R-3", refs=[], unit_ref="REF-0004", _one=_one, log_event=lambda *a, **k: None,
                         _LOG=None, _run_id_of=lambda o: "r", vocabulary=self.vocabulary(),
                         consume_judgment=lambda *a: seen["consumed"].append(a[-1]),
                         fell_through=lambda: seen.__setitem__("fell", seen["fell"] + 1))
            exec(compile(module, "<driver branch>", "exec"), scope)
            question = dict(auditor_questions.load_config()["rule_check"], form=form)
            with patch.object(auditor_questions, "load_config", lambda: {"rule_check": question}), \
                    patch.object(choice_decision, "threshold", lambda family: 0.6):
                asyncio.run(scope["body"]())
            return seen

        adopted = run("decision")
        self.assertEqual(adopted["fell"], 0)
        (prompt, answers, threshold), = adopted["choice"]
        self.assertIn(self.RULE["rule"], prompt)
        self.assertEqual(threshold, 0.6)
        self.assertEqual([a["label"] for a in answers], ["met", "not_met", "cannot be settled"])
        (reply,) = adopted["consumed"]
        self.assertEqual((reply["ok"], reply["call_id"], len(reply["parsed"]["items"])), (True, "call-1", 1))
        shipped = run("reply")
        self.assertEqual((shipped["choice"], shipped["consumed"], shipped["fell"]), ([], [], 1))
        # On an uncomputable plan the same question is asked; its not met is one rule_not_met
        # (INFRA-051), the unit's own text its quote, and the reply names the plan kind it came from.
        uncomputable = run("decision", kind="uncomputable")
        self.assertEqual(len(uncomputable["choice"]), 1)
        (reply,) = uncomputable["consumed"]
        (item,) = reply["parsed"]["items"]
        self.assertEqual((item["relation"], item["record_verdict"], item["quote"], reply["rule_check"]),
                         ("rule_not_met", "irregular", self.UNIT.strip(), "uncomputable"))
        self.assertIsNone(reply["unwritten"])
        # A plan of another kind never takes it.
        other = run("decision", kind="computed")
        self.assertEqual((other["choice"], other["consumed"], other["fell"]), ([], [], 1))


class PairFidelityQuestionChecks(unittest.TestCase):
    """VERIFIER's pair fidelity as one narrow question per pair auditor_pairs built, decided from
    the model's own probabilities: the evidence Auditor896 is shown, an item per settled answer
    joined to its pair directly, posted under the model, and the driver's phase-5 branch taking
    it only once adopted and measured."""

    def pair(self, n=1):
        record = dict(pair_id="auditor-pair-%d" % n, producer_item_id="PROCESSOR:d:item:%d" % n, producer_revision=1,
                      source_span_id="span-%d" % n, source_ref_ids=["REF-000%d" % n], auditor_relation="MATCH",
                      classifier_status="classified")
        view = dict(pair_id=record["pair_id"], producer_item={"claims_referenced": ["CLM-%d" % n], "draft_text": "x"},
                    source_evidence={"text": "Passage %d states {a} figure." % n})
        return record, view

    def question(self, **changes):
        import auditor_questions
        return dict(auditor_questions.load_config()["pair_fidelity"], **changes)

    def test_the_prompt_is_the_pairs_evidence_alone(self):
        import auditor_questions
        record, view = self.pair()
        prompt = auditor_questions.render_pair(self.question(), view["source_evidence"]["text"], view["producer_item"])
        self.assertIn("Passage 1 states {a} figure.", prompt)
        self.assertIn(auditor_questions.extraction_text(view["producer_item"]), prompt)
        self.assertNotIn("auditor-pair", prompt)
        self.assertNotIn("contract", prompt.lower())
        self.assertEqual([a["label"] for a in auditor_questions.answers(self.question())],
                         ["MATCH", "DIVERGENCE", "OMISSION", "ADDITION", "cannot be settled"])

    def test_a_settled_answer_is_one_item_joined_to_its_pair(self):
        import auditor_pairs
        import auditor_questions
        record, view = self.pair()
        item = auditor_questions.pair_item(_decision("OMISSION"), self.question(), record, view["source_evidence"]["text"])
        self.assertEqual((item["finding"], item["auditor_pair_id"], item["ref"]), ("OMISSION", record["pair_id"], "REF-0001"))
        self.assertIs(auditor_pairs.finding_pair(item, [record, self.pair(2)[0]]), record)
        for decision in (_decision("MATCH", settled=False), _decision("cannot be settled"), None, {"decided": "MATCH"}):
            self.assertIsNone(auditor_questions.pair_item(decision, self.question(), record, "t"), decision)

    def test_the_decisions_are_posted_under_the_model_and_joined(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import auditor_pairs
        driver = __import__("pipe" + "line")
        pairs = [self.pair(1), self.pair(2), self.pair(3)]
        answers = {"Passage 1": _decision("MATCH"), "Passage 2": _decision("ADDITION", settled=False),
                   "Passage 3": _decision("DIVERGENCE")}
        posts, joins, asked = [], [], []

        def call_choice(prompt, given, threshold):
            asked.append(threshold)
            decision = next(v for k, v in answers.items() if k in prompt)
            return SimpleNamespace(ok=True, parsed=decision, backend="local_auditor", model="phi")

        wrapper = SimpleNamespace(backend="local_auditor", model="phi", call_choice=call_choice,
                                  post_to_bus=lambda **k: posts.append(k))

        def prepare(w, payload):
            w._auditor_pair_state = [r for r, v in pairs]
            return dict(payload, auditor_pair_context={"pairs": [v for r, v in pairs]})

        def narrow_ask(orch, doc, w, agent, rule, calls, **call):
            def ask(user):
                r = call["send"](user, "")
                call["seen"].update(backend=r.backend, model=r.model)
                call["call_of"][user] = "call-%d" % len(call["call_of"])
                return call["answer_of"](r)
            return ask
        with patch.object(auditor_pairs, "prepare_context", prepare), \
                patch.object(auditor_pairs, "compare", lambda w, result: joins.append(result)), \
                patch.object(driver, "_narrow_ask", narrow_ask), \
                patch.object(driver.choice_decision if hasattr(driver, "choice_decision") else __import__("choice_decision"),
                             "threshold", lambda family: 0.7):
            result = driver._verifier_pair_decisions(None, {"id": "d1", "text": "t"}, wrapper, {"task": "t"},
                                                     self.question(form="decision"))
        self.assertEqual(asked, [0.7, 0.7, 0.7])
        self.assertTrue(result["ok"])
        self.assertEqual([(i["auditor_pair_id"], i["finding"]) for i in result["parsed"]["items"]],
                         [("auditor-pair-1", "MATCH"), ("auditor-pair-3", "DIVERGENCE")])
        self.assertEqual([d["settled"] for d in result["pair_decisions"]], [True, False, True])
        (post,) = posts
        self.assertEqual((post["body"]["backend"], post["body"]["model"]), ("local_auditor", "phi"))
        import finding_record
        self.assertEqual(finding_record.written_by(post["body"]["backend"], post["body"]["model"]),
                         finding_record.WRITTEN_BY_MODEL)
        (joined,) = joins
        self.assertIs(joined, result)

    def test_the_drivers_phase_5_branch_takes_it_only_once_adopted(self):
        import ast
        from types import SimpleNamespace
        from unittest.mock import patch
        import auditor_pairs
        import auditor_questions
        import choice_decision
        source = (ROOT / "scripts" / ("pipe" + "line.py")).read_text(encoding="utf-8")
        branch = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == "name == 'VERIFIER'" and "auditor_questions" in ast.unparse(n))
        loop = ast.For(target=ast.Name(id="once", ctx=ast.Store()), iter=ast.List(elts=[ast.Constant(1)], ctx=ast.Load()),
                       body=[branch, ast.Expr(ast.Call(func=ast.Name(id="fell_through", ctx=ast.Load()), args=[],
                                                       keywords=[]))], orelse=[])
        module = ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[]))

        def run(form):
            seen = {"fell": 0, "threads": []}
            entry = SimpleNamespace(as_dict=lambda: {"ref_id": "REF-0001"})
            scope = dict(name="VERIFIER", wrapper=SimpleNamespace(), doc={"id": "d1"}, proc={}, payload={"task": "x"},
                         reference_index=SimpleNamespace(find_by_document=lambda i: [entry]), names=[], tasks=[],
                         orch=None, _verifier_pair_decisions=object(),
                         asyncio=SimpleNamespace(to_thread=lambda f, *a: seen["threads"].append((f, a)) or "task"),
                         fell_through=lambda: seen.__setitem__("fell", seen["fell"] + 1))
            question = dict(auditor_questions.load_config()["pair_fidelity"], form=form)
            config = dict(auditor_questions.load_config(), pair_fidelity=question)
            with patch.object(auditor_questions, "load_config", lambda: config), \
                    patch.object(auditor_pairs, "eligible", lambda w, p: True), \
                    patch.object(choice_decision, "threshold", lambda family: 0.7):
                exec(compile(module, "<driver phase 5 branch>", "exec"), scope)
            return seen, scope
        adopted, scope = run("decision")
        self.assertEqual((adopted["fell"], scope["names"], scope["tasks"]), (0, ["VERIFIER"], ["task"]))
        (function, args), = adopted["threads"]
        self.assertIs(function, scope["_verifier_pair_decisions"])
        self.assertEqual(scope["wrapper"]._auditor_pair_request["references"], [{"ref_id": "REF-0001"}])
        shipped, scope = run("reply")
        self.assertEqual((shipped["fell"], shipped["threads"], scope["names"]), (1, [], []))


class TrainingRowChecks(unittest.TestCase):
    """tools/build_auditor_training.py on planted sources: every row is the rule check exactly as the
    pipeline renders it, the answers follow the plan, the held-out side shares no group, a text sharing
    a run with a development text is removed and counted, permissive_mix holds no share-alike row, and
    two builds are byte-identical."""

    def plant(self, root):
        import json
        raw = root / "raw"
        raw.mkdir(parents=True)
        (raw / "wanli_train.jsonl").write_text("".join(json.dumps(
            {"id": "w%d" % i, "pairID": "g%d" % i, "premise": "Premise number %d says the office opens at nine." % i,
             "hypothesis": "The office opens at nine." if i % 3 == 0 else "The office closes early.",
             "gold": ("entailment", "contradiction", "neutral")[i % 3]}) + "\n" for i in range(60)), encoding="utf-8")
        tab = root / "tabfact"
        (tab / "csv").mkdir(parents=True)
        (tab / "train_id.json").write_text(json.dumps(["t1.csv"]), encoding="utf-8")
        (tab / "r1_training_all.json").write_text(json.dumps({"t1.csv": [["the total is 4", "the total is 5"], [1, 0], "a small table"]}),
                                                 encoding="utf-8")
        (tab / "r2_training_all.json").write_text("{}", encoding="utf-8")
        (tab / "csv" / "t1.csv").write_text("item#count\na#1\nb#3\n", encoding="utf-8")
        dev = root / "dev"
        dev.mkdir()
        (dev / "contradoc.json").write_text("{}", encoding="utf-8")
        (dev / "scitab.json").write_text("[]", encoding="utf-8")
        (dev / "notes.md").write_text("Premise number 7 says the office opens at nine.", encoding="utf-8")
        return root

    def multinli(self, raw):
        genres = ("fiction", "government")
        return [{"promptID": "p%d" % i, "pairID": "m%d" % i, "premise": "A clerk in story %d files the forms by noon." % i,
                 "hypothesis": "The forms are filed.", "label": i % 3, "genre": genres[i % 2]} for i in range(90)]

    def build(self, root, out):
        from unittest.mock import patch
        import build_auditor_training as b
        plan = (("multinli", "entailment", "met", 6, False), ("multinli", "entailment", "met", 3, True),
                ("wanli", "entailment", "met", 6, False), ("tabfact", "entailed", "met", 1, False),
                ("wanli", "contradiction", "not_met", 6, False), ("tabfact", "refuted", "not_met", 1, False),
                ("wanli", "neutral", "cannot be settled", 6, False))
        with patch.object(b, "PLAN", plan), patch.object(b, "HELD_OUT_SHARE", 0.2):
            return b.build(root, root / "dev" / "contradoc.json", root / "dev" / "scitab.json", [root / "dev"], out,
                           lambda text: len(text.split()), multinli_rows=self.multinli)

    def test_the_rows_are_the_rule_check_as_sent(self):
        import json
        import tempfile
        import auditor_questions
        import build_auditor_training as b
        with tempfile.TemporaryDirectory() as tmp:
            root = self.plant(Path(tmp) / "src")
            manifest = self.build(root, Path(tmp) / "a")
            again = self.build(root, Path(tmp) / "b")
            question = auditor_questions.load_config()["rule_check"]
            self.assertEqual(manifest["question_sha256"], b.question_digest(question))
            self.assertEqual(manifest["overlap"]["wanli"]["removed_text"], 1)       # the planted run
            for mix in b.MIXES:
                for side in ("train", "held_out"):
                    name = "%s_%s.jsonl" % (mix, side)
                    self.assertEqual((Path(tmp) / "a" / name).read_bytes(), (Path(tmp) / "b" / name).read_bytes())
                rows = {side: [json.loads(l) for l in (Path(tmp) / "a" / ("%s_%s.jsonl" % (mix, side))).read_text(
                    encoding="utf-8").splitlines()] for side in ("train", "held_out")}
                self.assertFalse({(r["set"], r["group"]) for r in rows["train"]} & {(r["set"], r["group"]) for r in rows["held_out"]})
                for row in rows["train"]:
                    self.assertEqual(row["form"], "rule_check")
                    self.assertIn(row["answer"], [a["label"] for a in auditor_questions.answers(question)])
                    head = question["decision"]["template"].split("{rule}")[0]
                    self.assertTrue(row["user"].startswith(head))
                if mix == "permissive_mix":
                    self.assertFalse(any(r["share_alike"] for side in rows.values() for r in side))
                else:
                    self.assertTrue(any(r["share_alike"] for r in rows["train"]))
                self.assertEqual(manifest, again)
            self.assertTrue(any("| item | count |" in r["user"] for r in rows["train"] + rows["held_out"]))


class DevelopmentQuestionChecks(unittest.TestCase):
    """tools/build_auditor_questions.py on the ContractNLI adapter's own fixture: each question is
    byte for byte the rule check the driver renders for that unit and rule (the unit from the
    driver's own split of the written document under another document id, the rule from the
    pipeline's parser), and each answer is the release's annotation of that unit."""

    def test_each_question_is_the_drivers_call_on_its_unit_and_rule(self):
        import json
        import tempfile
        import auditor_questions
        import build_auditor_questions as q
        import convention_parser
        sys.path.insert(0, str(ROOT / "benchmark" / "adapters"))
        from common import bundle
        fixture = ROOT / "benchmark" / "adapters" / "contractnli" / "fixtures" / "synthetic_items.json"
        with tempfile.TemporaryDirectory() as tmp:
            value = q.build(fixture, Path(tmp) / "questions.json")
            again = q.build(fixture, Path(tmp) / "again.json")
            self.assertEqual((Path(tmp) / "questions.json").read_bytes(), (Path(tmp) / "again.json").read_bytes())
            self.assertEqual(value, again)
            question = auditor_questions.load_config()["rule_check"]
            docs = {d["document_id"]: d for d in q._adapter().documents(q._adapter().read_source(fixture), {"side": "development"})}
            self.assertTrue(value["questions"])
            for row in value["questions"]:
                doc = docs[row["document_id"]]
                text = bundle.render_document(doc["document_id"], [p["text"] for p in doc["parts"]])
                units = {u["unit_id"]: u for u in pairing_map.split_units(text, document_id="the-run-file-name")}
                folder = Path(tmp) / row["question_id"] / "input" / "conventions"
                folder.mkdir(parents=True)
                (folder / "rules.md").write_text(bundle.render_rules(doc["rules"]), encoding="utf-8", newline="\n")
                registry = [c.as_dict() for c in convention_parser.parse_conventions(folder.parents[1]).conventions]
                rule = next(c for c in registry if str(c["category"]).upper() == row["rule_id"])
                self.assertEqual(row["user"], auditor_questions.render_rule_check(question, rule.get("rule", ""),
                                                                                  units[row["unit_id"]].get("text", "")))
                item = next(i for i in doc["items"] if i["rule_id"] == row["rule_id"])
                self.assertEqual(row["answer"], q.GOLD[item["gold"]])
                if row["answer"] != "cannot be settled":
                    self.assertIn(int(row["unit_id"][1:3]), item["evidence_parts"])


class AuditorTrainingPassChecks(unittest.TestCase):
    """benchmark/baselines/auditor_train.py: a recipe is assembled only from rows and questions of the
    shipped rule check, refuses a development question that is a training row, and the session runs
    on the replay pass (judge_train.train on a tiny random model on the CPU, then every pass, each
    question decided by a stand-in backend), leaving one reply record per question where the runner
    counts and the measurement beside them."""

    def recipe_files(self, tmp, tamper=None):
        import json
        import auditor_questions
        import build_auditor_training as b
        sys.path.insert(0, str(ROOT / "benchmark" / "baselines"))
        import auditor_train as a
        question = auditor_questions.load_config()["rule_check"]
        digest = b.question_digest(question)
        rows_dir = Path(tmp) / "rows"
        rows_dir.mkdir()
        labels = [x["label"] for x in auditor_questions.answers(question)]

        def rows(side, n):
            return [{"row_id": "%s%d" % (side, i), "form": "rule_check", "answer": labels[i % 3], "share_alike": False,
                     "tokens": 10, "user": auditor_questions.render_rule_check(question, "rule %s %d" % (side, i), "part %d" % i),
                     "set": "s", "group": "g%d" % i} for i in range(n)]
        for mix in b.MIXES:
            b.write_rows(rows_dir / ("%s_train.jsonl" % mix), rows("t" + mix, 48))
            b.write_rows(rows_dir / ("%s_held_out.jsonl" % mix), rows("h" + mix, 6))
        (rows_dir / "manifest.json").write_text(json.dumps({"question_sha256": digest}), encoding="utf-8")
        questions = [{"question_id": "q%d" % i, "document_id": "d", "unit_id": "u01-p-00001", "rule_id": "CONV-X",
                      "answer": labels[i % 3], "half": "AB"[i % 2],
                      "user": auditor_questions.render_rule_check(question, "dev rule %d" % i, "dev part %d" % i)} for i in range(5)]
        if tamper == "question_is_a_row":
            questions[0]["user"] = rows("t" + "dev_mix", 1)[0]["user"]
        for q in questions:
            q["user_sha256"] = a._sha(q["user"])
        qpath = Path(tmp) / "questions.json"
        qpath.write_text(json.dumps({"schema": a.QUESTIONS_SCHEMA, "question_sha256": "0" * 64 if tamper == "other_question"
                                     else digest, "questions": questions}), encoding="utf-8")
        files = {}
        for mix in b.MIXES:
            files[mix] = Path(tmp) / ("%s.json" % mix)
            a.assemble(rows_dir, mix, qpath, files[mix], "m", "r", 3, 1000.0, {"half": 0.5, "full": 1.0}, ["base", "half", "full"])
        session = Path(tmp) / "session.json"
        a.session(files["dev_mix"], files["permissive_mix"], session)
        return a, session, questions

    def test_a_recipe_refuses_another_question_and_a_question_that_is_a_row(self):
        import tempfile
        for tamper, said in (("other_question", "ask different questions"), ("question_is_a_row", "is a training row")):
            with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, said, msg=tamper):
                self.recipe_files(tmp, tamper)
        with tempfile.TemporaryDirectory() as tmp:
            self.recipe_files(tmp)          # untampered, the same files assemble

    def test_the_session_trains_then_asks_and_leaves_one_record_a_question(self):
        import json
        import tempfile
        from types import SimpleNamespace
        import torch
        import replay_prompts
        sys.path.insert(0, str(ROOT / "tools"))
        from judge_training_checks import tiny_load

        class Backend:
            def __init__(self, reader, context):
                self.reader = reader

            def prepare(self):
                return {"model_id": "fixture", "digest": "d" + ("+a" if self.reader.get("adapter") else "")}

            def choose(self, system, user, answers):
                assert system is None
                rows = [{"label": x["label"], "surface": x["surface"], "token_id": i, "probability": p}
                        for i, (x, p) in enumerate(zip(answers, (0.6, 0.3, 0.1)))]
                return {"decision": {"answers": rows, "top": rows[0]["label"], "declared_mass": 0.9, "settled": False,
                                     "decided": "cannot be settled", "why": "no_threshold"},
                        "payload": "<u>" + user + "<a>", "form": "rendered_prompt", "attention": {}, "prefill": {}}

        with tempfile.TemporaryDirectory() as tmp:
            a, session, questions = self.recipe_files(tmp)
            self.assertTrue(replay_prompts.is_auditor_training(session))
            self.assertEqual(len(replay_prompts.load_prompts(session)), len(questions))
            reader = lambda adapter: {"backend": "local_auditor", "model_id": "fixture", "model_mode": "base",
                                      **({"adapter": adapter} if adapter else {})}
            out = Path(tmp) / "out"
            summary = a.run(session, out, load=tiny_load(torch, []), backend_factory=Backend, reader=reader)
            records = list((out / "audit" / "model_replies").glob("*.json"))
            self.assertEqual(len(records), len(questions))
            self.assertTrue((out / a.MEASUREMENT).is_file())
            self.assertEqual([r["mix"] for r in summary["recipes"]], ["dev_mix", "permissive_mix"])
            for mix in ("dev_mix", "permissive_mix"):
                for name in ("base", "half") + (("full",) if mix == "dev_mix" else ()):
                    self.assertEqual(len(list((out / "passes" / mix / name / "audit" / "model_replies").glob("*.json"))),
                                     len(questions), (mix, name))
            record = json.loads(records[0].read_text(encoding="utf-8"))
            self.assertIn("decision", record)
            self.assertFalse((record.get("reply") or {}).get("text"))
            self.assertTrue((out / "training" / "result.json").is_file() and (out / "dev_mix" / "training" / "result.json").is_file())
            with self.assertRaises(ValueError):
                a.run(session, Path(tmp) / "again", paths=["sdpa", "e"], load=tiny_load(torch, []), backend_factory=Backend,
                      reader=reader)


class RoleGraphChecks(unittest.TestCase):
    """D-S59: config/role_graph.json, the roles of a run and what each needs, checked for cycles,
    ordered topologically, run by the existing scheduler (independent roles at once on their models'
    lanes, a role only after what it needs), and the graph that ran saved in execution_topology.json
    beside its measured times."""

    def graph(self, roles):
        return {"schema": "role-graph-v1", "roles": {k: {"needs": v, "scope": "document"} for k, v in roles.items()}}

    def test_the_shipped_graph_loads_in_one_order(self):
        import role_graph
        graph = role_graph.load()
        first = role_graph.order(graph)
        self.assertEqual(first, role_graph.order(role_graph.load()))
        role_graph.check_order(graph, first)
        self.assertLess(first.index("PROCESSOR"), first.index("VERIFIER"))
        self.assertLess(first.index("EDITOR_DEPUTY_DG"), first.index("EDITOR_DG"))
        flat = [r for layer in role_graph.layers(graph) for r in layer]
        self.assertEqual(sorted(flat), sorted(graph["roles"]))
        import json
        registry = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
        self.assertTrue(set(registry) <= set(graph["roles"]))

    def test_a_cycle_is_refused(self):
        import role_graph
        for roles, said in (({"A": ["B"], "B": ["C"], "C": ["A"], "D": []}, "cycle among: A, B, C"),
                            ({"A": ["A"]}, "needs itself"), ({"A": ["Z"]}, "does not declare")):
            with self.assertRaisesRegex(role_graph.GraphRefused, said):
                role_graph.check(self.graph(roles))

    def test_an_order_against_a_dependency_is_refused(self):
        import role_graph
        from execution_scheduler import Lane, Scheduler
        graph = role_graph.load()
        with self.assertRaisesRegex(role_graph.GraphRefused, "VERIFIER would run before PROCESSOR"):
            role_graph.check_order(graph, ["VERIFIER", "PROCESSOR"])
        built = role_graph.tasks(graph, {"PROCESSOR": lambda c: 1, "VERIFIER": lambda c: 2}, "d1", lambda r: "")
        swapped = [t.__class__(**dict(t.__dict__, sequence=1 - t.sequence)) for t in built]
        with Scheduler([Lane("primary")]) as scheduler, self.assertRaisesRegex(ValueError, "respect dependencies"):
            scheduler.run(swapped)

    def run_graph(self, delay=0.15):
        import threading
        import time
        import role_graph
        from execution_scheduler import Lane, Scheduler
        graph = role_graph.load()
        models = {"PROCESSOR": "qwen", "VERIFIER": "phi", "PRACTICE_AUDITOR": "phi"}
        seen, lock = {}, threading.Lock()

        def action(role):
            def act(context):
                begin = time.perf_counter()
                time.sleep(delay * (3 if role == "PROCESSOR" else 1))
                with lock:
                    seen[role] = (begin, time.perf_counter(), context.worker.lane.name)
                return role
            return act
        built = role_graph.tasks(graph, {r: action(r) for r in models}, "d1", models.get)
        scheduler = Scheduler([Lane("producer", models=("qwen",)), Lane("auditor", models=("phi",))])
        outcomes = scheduler.run(built)
        scheduler.close()
        return graph, scheduler, seen, outcomes

    def test_independent_roles_run_at_once_on_their_models_lanes(self):
        graph, scheduler, seen, outcomes = self.run_graph()
        self.assertTrue(all(o.state == "completed" for o in outcomes.values()))
        self.assertEqual((seen["PROCESSOR"][2], seen["PRACTICE_AUDITOR"][2], seen["VERIFIER"][2]),
                         ("producer", "auditor", "auditor"))
        self.assertLess(seen["PRACTICE_AUDITOR"][0], seen["PROCESSOR"][1])     # at once
        self.assertGreaterEqual(seen["VERIFIER"][0], seen["PROCESSOR"][1])     # only after what it needs

    def test_the_saved_graph_is_what_ran(self):
        import json
        import tempfile
        from types import SimpleNamespace
        import execution_topology
        import role_graph
        from execution_scheduler import Lane
        graph, scheduler, seen, _ = self.run_graph(delay=0.05)
        record = role_graph.as_run(graph, scheduler.tasks, scheduler.events)
        self.assertEqual(set(record["roles"]), {t.agent for t in scheduler.tasks.values()})
        for role, ran in record["roles"].items():
            self.assertEqual([r["task"] for r in ran], [t.id for t in scheduler.tasks.values() if t.agent == role])
            self.assertAlmostEqual(ran[0]["start_monotonic_s"], next(
                e["monotonic_s"] for e in scheduler.events if e["event"] == "task_start" and e["task"] == ran[0]["task"]))
        self.assertEqual(record["edges"], [{"from": "PROCESSOR", "to": "VERIFIER"}])
        self.assertTrue(record["kept_declared_order"])
        # A task that started before what it needs had ended is named.
        events = [dict(e) for e in scheduler.events]
        verifier = next(t.id for t in scheduler.tasks.values() if t.agent == "VERIFIER")
        early = min(e["monotonic_s"] for e in events if e["event"] == "task_start")
        for e in events:
            if e["event"] == "task_start" and e["task"] == verifier:
                e["monotonic_s"] = early
        broken = role_graph.as_run(graph, scheduler.tasks, events)
        self.assertEqual([(v["role"], v["needs"]) for v in broken["violations"]], [("VERIFIER", "PROCESSOR")])
        self.assertFalse(broken["kept_declared_order"])
        # execution_topology.json carries it, written by the Runtime itself.
        with tempfile.TemporaryDirectory() as tmp:
            context = SimpleNamespace(run_id="r1", audit_dir=lambda: Path(tmp) / "audit")
            runtime = execution_topology.Runtime([Lane("primary")], graph)
            runtime.run_context = context
            built = role_graph.tasks(graph, {"PROCESSOR": lambda c: 1, "VERIFIER": lambda c: 2}, "d2", lambda r: "")
            runtime.scheduler.run(built)
            runtime.write()
            expected = json.loads(json.dumps(role_graph.as_run(graph, runtime.scheduler.tasks, runtime.scheduler.events)))
            saved = json.loads((Path(tmp) / "audit" / "execution_topology.json").read_text(encoding="utf-8"))
            runtime.scheduler.close()
            self.assertEqual(saved["role_graph"], expected)
            self.assertEqual(sorted(saved["role_graph"]["roles"]), ["PROCESSOR", "VERIFIER"])
            self.assertEqual(saved["role_graph"]["declared_sha256"], role_graph.digest(graph))
        # A run whose role graph has a cycle does not start.
        from unittest.mock import patch
        with patch.object(role_graph, "load", lambda: role_graph.check(self.graph({"A": ["B"], "B": ["A"]}))), \
                self.assertRaises(role_graph.GraphRefused):
            execution_topology.Runtime([Lane("primary")])


class ClaimCoverageChecks(unittest.TestCase):
    """D-313: Python's claim-coverage check on each pair auditor_pairs builds, a RECORD beside
    VERIFIER and Auditor896: on the pair record and its telemetry row, never in what VERIFIER is
    shown, and changing no call."""

    def test_the_coverage_states(self):
        import auditor_pairs as a
        cases = [("no claim here", [], a.NO_CLAIMS), ("CLM-1 and CLM-2.", ["CLM-1", "CLM-2"], "MATCH"),
                 ("CLM-1 and CLM-2.", ["CLM-1"], "OMISSION"), ("CLM-1.", ["CLM-1", "CLM-9"], "ADDITION"),
                 ("CLM-1 and CLM-2.", ["CLM-1", "CLM-9"], "DIVERGENCE"), ("xCLM-3 only", [], a.NO_CLAIMS)]
        for text, claims, status in cases:
            got = a.claim_coverage(text, {"claims_referenced": claims})
            self.assertEqual(got["status"], status, (text, claims))
        detail = a.claim_coverage("CLM-1 and CLM-2.", {"claims_referenced": ["CLM-1", "CLM-9"]})
        self.assertEqual((detail["missing_claims"], detail["added_claims"]), (["CLM-2"], ["CLM-9"]))

    def test_it_is_on_the_record_and_not_in_what_verifier_is_shown(self):
        import bounded_extraction as extraction
        import auditor_pairs as a
        source = "Entry text naming CLM-7 and CLM-8."
        spans = extraction.ledger(source, "fixture")
        item = dict(item_id="PROCESSOR:fixture:item", revision=1, claims_referenced=["CLM-7"])
        producer = dict(ok=True, truncated=False, parsed=dict(items=[item]), source_ownership=[dict(
            producer_item_id=item["item_id"], producer_revision=1, producer_call_id="call", item_hash=a.item_hash(item),
            source_span_ids=[spans[0].id])])
        (pair,), missing, _ = a.build("run", dict(id="fixture", text=source), producer, [])
        self.assertEqual(pair["record"]["claim_coverage"], "OMISSION")
        self.assertEqual(pair["record"]["claim_coverage_detail"]["missing_claims"], ["CLM-8"])
        a.validate(pair["record"])                       # the pair's identity is unchanged by it
        shown = a.pair_view(pair["record"], pair)
        self.assertNotIn("claim_coverage", json_text(shown))
        import compact_contracts
        import re
        sample = "a CLM-1, CLM-22a and xCLM-3 and CLM-4-b."
        self.assertEqual(a.CLAIM_ID.findall(sample), re.findall(r"\bCLM-[A-Za-z0-9-]+", sample))
        self.assertIn(a.CLAIM_ID.pattern, (Path(compact_contracts.__file__).read_text(encoding="utf-8")))


class RuleNotMetChecks(unittest.TestCase):
    """INFRA-051: rule_not_met appended last to the Finding record (contract and fallback), minted
    only by the rule-check step on a settled No on an uncomputable plan, irregular, its quote the
    unit's own text, screened and marked, never a figure relation, and refused from any other path,
    on another plan, when not irregular, or quoting other text, each under its own reason."""

    UNIT = "## Entry 9\nThe section explains its purpose in one line.\n"
    RULE = {"id": "CONV-009", "rule": "Each section states who approved it."}

    def kept(self, **changes):
        import auditor_questions
        question = auditor_questions.load_config()["rule_check"]
        reply = auditor_questions.rule_check_reply(_decision("not_met"), question, plan_kind="uncomputable",
                                                   unit_text=self.UNIT, ref="REF-0009", field_label=None, ok=True,
                                                   call_id="c9", backend="local_auditor", model="m")
        (item,) = reply["parsed"]["items"]
        return dict(item, unit_id="u01-entry-9", rule_id=self.RULE["id"], **changes), reply

    def test_the_relation_is_appended_last_and_reads_in_words(self):
        import json
        import finding_record as fr
        sys.path.insert(0, str(ROOT))
        from benchmark.adapters.common import records
        contract = json.loads((ROOT / "config" / "agent_contracts.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["finding_record"]["relations"][-3:], ["contradiction", "claim_not_met", "rule_not_met"])
        self.assertEqual(fr._FALLBACK["relations"][-3:], ["contradiction", "claim_not_met", "rule_not_met"])
        self.assertEqual(list(fr.relations()), list(fr._FALLBACK["relations"]))
        self.assertNotIn("rule_not_met", fr.figure_relations())
        self.assertEqual(records.TEXT_RELATIONS, fr.TEXT_RELATIONS)
        item, _ = self.kept()
        self.assertFalse(fr.is_finding(item))                      # a record only with Python's mark
        self.assertTrue(records.is_typed_record(dict(item, text_screened=True)))
        self.assertFalse(records.is_typed_record(item))
        self.assertIn("was judged not to meet the rule", fr.reader_line(dict(item, text_screened=True)))

    def test_the_rule_check_step_mints_it_and_the_screen_keeps_it(self):
        import paired_review as pr
        import finding_record as fr
        item, reply = self.kept()
        self.assertEqual((item["relation"], item["record_verdict"], item["quote"], reply["rule_check"]),
                         ("rule_not_met", "irregular", self.UNIT.strip(), "uncomputable"))
        self.assertIsNone(pr.judged_item_refusal(item, self.RULE, set(), self.UNIT, rule_check_plan="uncomputable"))
        marked = pr.mark_screened(item)
        self.assertTrue(marked[fr.SCREENED_FIELD])
        self.assertTrue(fr.is_finding(marked))

    def test_each_refusal(self):
        import paired_review as pr
        item, _ = self.kept()
        cases = [
            (item, None, pr.RULE_NOT_MET_NOT_FROM_RULE_CHECK),          # a model's reply on a judged path
            (item, "absence_judged", pr.RULE_NOT_MET_PLAN_NOT_UNCOMPUTABLE),
            (dict(item, record_verdict="ok"), "uncomputable", pr.RULE_NOT_MET_NOT_IRREGULAR),
            (dict(item, quote="The section explains its purpose"), "uncomputable", pr.RULE_NOT_MET_QUOTE_NOT_UNIT),
            (dict(item, quote="Some other text."), "uncomputable", pr.RULE_NOT_MET_QUOTE_NOT_UNIT),
            (dict(item, quote=""), "uncomputable", pr.RULE_NOT_MET_QUOTE_NOT_UNIT),
        ]
        for candidate, plan, reason in cases:
            self.assertEqual(pr.judged_item_refusal(candidate, self.RULE, set(), self.UNIT, rule_check_plan=plan), reason,
                             (plan, reason))
        import reviewed_document
        import judged_rescreen
        catalog = (ROOT / "scripts" / "ui" / "localization_catalog.js").read_text(encoding="utf-8")
        for name in ("RULE_NOT_MET_NOT_FROM_RULE_CHECK", "RULE_NOT_MET_PLAN_NOT_UNCOMPUTABLE",
                     "RULE_NOT_MET_NOT_IRREGULAR", "RULE_NOT_MET_QUOTE_NOT_UNIT"):
            reason = getattr(pr, name)
            words = reviewed_document.REFUSAL_REASONS[reason]
            self.assertIn('"%s": "' % words, catalog)
            self.assertIn(reason, judged_rescreen.KINDS)

    def test_the_driver_hands_the_plan_kind_to_both_judged_screens(self):
        import ast
        source = (ROOT / "scripts" / ("pipe" + "line.py")).read_text(encoding="utf-8")
        calls = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Call)
                 and ast.unparse(n.func) == "paired_review_mod.judged_item_refusal"]
        passed = [next((ast.unparse(k.value) for k in c.keywords if k.arg == "rule_check_plan"), None) for c in calls]
        self.assertEqual(passed.count("r.get('rule_check') if isinstance(r, dict) else None"), 2, passed)


class HeldOutReadChecks(unittest.TestCase):
    """D-330: benchmark/baselines/auditor_read.py reads half A alone for every choice, and scores
    half B only when the committed docs/loop/HELDOUT_OPENINGS.md holds the opening's row and the
    committed half-A record shows half A passed for the same attempt and decisions; it tests half B
    at the row's alpha, 0.05 / 2^k."""

    def fixture(self, tmp, margin=0.45):
        import json
        import random
        import subprocess
        sys.path.insert(0, str(ROOT / "benchmark" / "baselines"))
        import auditor_read as r
        root = Path(tmp)
        rng = random.Random(1)
        questions = []
        for half in "AB":
            for d in range(8):
                for i in range(9):
                    questions.append({"question_id": "%s%d_%d" % (half, d, i), "document_id": "doc-%s%d" % (half, d),
                                      "half": half, "answer": r.LABELS[i % 3], "user_sha256": "u%s%d%d" % (half, d, i)})
        qpath = root / "questions.json"
        qpath.write_text(json.dumps({"questions": questions}), encoding="utf-8")
        out = root / "session"

        def write(path, skill):
            path.parent.mkdir(parents=True, exist_ok=True)
            lines = []
            for q in questions:
                right = rng.random() < skill
                top = q["answer"] if right else r.LABELS[(r.LABELS.index(q["answer"]) + 1) % 3]
                probs = {lab: (0.9 if lab == top else 0.05) for lab in r.LABELS}
                lines.append(json.dumps({"question_id": q["question_id"], "half": q["half"], "answer": q["answer"],
                                         "probabilities": probs, "top": top}))
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        for name, path in r.decision_files(out).items():
            write(path, 0.5 if name == "base" else 0.5 + margin)
        repo = root / "repo"
        (repo / "docs" / "loop" / "stages").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "fixture@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "fixture"], check=True)
        return r, root, qpath, out, repo, questions

    def commit(self, repo, message):
        import subprocess
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", message], check=True)
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

    def opening(self, r, repo, questions, candidate, commit, k=1, attempt=1):
        import hashlib
        import json
        material = hashlib.sha256(json.dumps(sorted((q["question_id"], q["user_sha256"], q["answer"])
                                                    for q in questions if q["half"] == "B"),
                                             separators=(",", ":")).encode()).hexdigest()
        (repo / r.OPENINGS).write_text(
            "| Part | k | Alpha | Attempt | Held-out material | Tuning pass record (commit) | Written | Result |\n"
            "|---|---|---|---|---|---|---|---|\n"
            "| %s | %d | %r | %d %s | rule_check_dev.json %s | %s | 2026-11-08 | |\n"
            % (r.PART, k, 0.05 / 2 ** k, attempt, candidate, material, commit), encoding="utf-8")

    def test_half_a_is_read_alone(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            r, root, qpath, out, repo, questions = self.fixture(tmp)
            first = r.read_a(out, qpath, 1, root / "a1.json")
            for path in r.decision_files(out).values():        # half B's rows changed: nothing moves
                rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
                for row in rows:
                    if row["half"] == "B":
                        row["top"] = "met"
                path.write_text("\n".join(json.dumps(x) for x in rows) + "\n", encoding="utf-8")
            second = r.read_a(out, qpath, 1, root / "a2.json")
            for key in ("half_a_macro_f1", "selected", "margin", "thresholds", "passed_half_a"):
                self.assertEqual(first[key], second[key], key)
            self.assertTrue(first["passed_half_a"])

    def test_half_b_is_scored_only_after_a_committed_opening_and_record(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            r, root, qpath, out, repo, questions = self.fixture(tmp)
            record_rel = "docs/loop/stages/AUDITOR_RULE_CHECK_HALF_A_1.json"
            record = r.read_a(out, qpath, 1, repo / record_rel)
            cand = record["selected"]
            args = (out, qpath, record_rel, 1, cand, repo, root / "b.json")
            with self.assertRaisesRegex(r.ReadRefused, "not committed"):      # nothing committed yet
                r.read_b(*args)
            commit = self.commit(repo, "the half-A record")
            self.opening(r, repo, questions, cand, commit)
            with self.assertRaisesRegex(r.ReadRefused, "not committed"):      # the row is not committed
                r.read_b(*args)
            self.commit(repo, "the opening")
            for attempt, other in ((2, cand), (1, "dev_mix@unknown")):
                with self.assertRaises(r.ReadRefused):                         # no row for that opening
                    r.read_b(out, qpath, record_rel, attempt, other, repo, root / "b.json")
            result = r.read_b(*args)
            self.assertEqual((result["opening_k"], result["alpha"]), (1, 0.025))
            self.assertTrue(result["passed"], result)
            # Decisions changed after the record: refused.
            path = r.decision_files(out)[cand]
            path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaisesRegex(r.ReadRefused, "not the ones"):
                r.read_b(*args)

    def test_a_failed_half_a_never_opens_half_b(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            r, root, qpath, out, repo, questions = self.fixture(tmp, margin=0.0)
            record_rel = "docs/loop/stages/AUDITOR_RULE_CHECK_HALF_A_1.json"
            record = r.read_a(out, qpath, 1, repo / record_rel)
            self.assertFalse(record["passed_half_a"])
            commit = self.commit(repo, "record")
            self.opening(r, repo, questions, record["selected"], commit)
            self.commit(repo, "opening")
            with self.assertRaisesRegex(r.ReadRefused, "does not show half A passed"):
                r.read_b(out, qpath, record_rel, 1, record["selected"], repo, root / "b.json")

    def test_attempt_2_offsets_are_fitted_on_half_a_and_applied_frozen_to_half_b(self):
        """Attempt 2 (AUDITOR_RULE_CHECK_ATTEMPT_2.md): each arm's per-label offsets are fitted on its
        own half-A rows, frozen in the record, and applied unrefitted to half B."""
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            r, root, qpath, out, repo, questions = self.fixture(tmp, margin=0.3)
            for name, path in r.decision_files(out).items():
                if name == "base":
                    continue
                rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
                for row in rows:          # the trained arms put a met answer under Unclear
                    if row["answer"] == "met":
                        row["probabilities"] = {"met": 0.35, "not_met": 0.10, "cannot be settled": 0.55}
                        row["top"] = "cannot be settled"
                path.write_text("\n".join(json.dumps(x) for x in rows) + "\n", encoding="utf-8")
            plain = r.read_a(out, qpath, 1, root / "plain.json")
            rel = "docs/loop/stages/AUDITOR_RULE_CHECK_HALF_A_2.json"
            record = r.read_a(out, qpath, 2, repo / rel, calibration="prior_offset")
            cand = record["selected"]
            self.assertEqual(record["calibration"], "prior_offset")
            self.assertLess(record["offsets"][cand]["cannot be settled"], 0)
            self.assertGreater(record["half_a_macro_f1"][cand], plain["half_a_macro_f1"][cand])
            commit = self.commit(repo, "the attempt-2 record")
            self.opening(r, repo, questions, cand, commit, attempt=2)
            self.commit(repo, "the opening")
            result = r.read_b(out, qpath, rel, 2, cand, repo, root / "b.json")
            files = r.decision_files(out)
            want = (r.macro_f1(r.calibrated(r._rows(files[cand], "B", questions), record["offsets"][cand]))
                    - r.macro_f1(r.calibrated(r._rows(files["base"], "B", questions), record["offsets"]["base"])))
            raw = r.macro_f1(r._rows(files[cand], "B", questions)) - r.macro_f1(r._rows(files["base"], "B", questions))
            self.assertAlmostEqual(result["half_b_gain"], want)
            self.assertNotAlmostEqual(want, raw)
            with self.assertRaises(r.ReadRefused):
                r.read_a(out, qpath, 2, root / "x.json", calibration="isotonic")

    def test_the_alpha_halves_with_each_opening(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            r, root, qpath, out, repo, questions = self.fixture(tmp)
            record_rel = "docs/loop/stages/AUDITOR_RULE_CHECK_HALF_A_1.json"
            record = r.read_a(out, qpath, 1, repo / record_rel)
            commit = self.commit(repo, "record")
            self.opening(r, repo, questions, record["selected"], commit, k=3)
            self.commit(repo, "opening")
            result = r.read_b(out, qpath, record_rel, 1, record["selected"], repo, root / "b.json")
            self.assertEqual(result["alpha"], 0.05 / 8)


def _auditor_read():
    sys.path.insert(0, str(ROOT / "benchmark" / "baselines"))
    import auditor_read
    return auditor_read


def _b_rows(path, questions):
    """Half B's rows of a decisions file, as a neutralised half-A read would mix them in."""
    import json
    gold = {q["question_id"]: q for q in questions if q["half"] == "B"}
    return [dict(row, gold=gold[row["question_id"]]["answer"], document_id=gold[row["question_id"]]["document_id"])
            for row in map(json.loads, Path(path).read_text(encoding="utf-8").splitlines())
            if row.get("half") == "B"]


def _skip_passed_check():
    """read_b with the half-A pass test taken out: the committed record is read as passed."""
    from unittest.mock import patch
    r = _auditor_read()
    original = r._git_show

    def show(repo, rev, path):
        text = original(repo, rev, path)
        if path.endswith(".json"):
            import json
            return json.dumps(dict(json.loads(text), passed_half_a=True))
        return text
    return patch.object(r, "_git_show", show)


def _rule_check_refusal_without(skip):
    """paired_review._rule_check_refusal with one of its four checks taken out."""
    import paired_review as pr

    def refusal(item, unit_text, plan):
        if skip != "path" and plan is None:
            return pr.RULE_NOT_MET_NOT_FROM_RULE_CHECK
        if skip != "plan" and plan is not None and plan != pr.UNCOMPUTABLE_PLAN:
            return pr.RULE_NOT_MET_PLAN_NOT_UNCOMPUTABLE
        if skip != "irregular" and str(item.get("record_verdict") or "").lower() != "irregular":
            return pr.RULE_NOT_MET_NOT_IRREGULAR
        if skip != "quote" and pr._squash(item.get("quote")) != pr._squash(unit_text):
            return pr.RULE_NOT_MET_QUOTE_NOT_UNIT
        return None
    return refusal


def json_text(value):
    import json
    return json.dumps(value, sort_keys=True)


def _run(suite):
    import io
    return unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(suite)


def _cases(case, *names):
    return unittest.TestSuite(case(n) for n in names) if names else \
        unittest.defaultTestLoader.loadTestsFromTestCase(case)


def _neutralisations():
    from unittest.mock import patch
    import contract_decoding
    import envelope_decoding_checks
    import report_recommendations_checks
    import semantic_waves

    def no_declarations(init=contract_decoding.EnvelopeContract.__init__):
        def build(self, agent, required, spellings, optional, leading=None, enums=None, max_chars=None):
            init(self, agent, required, spellings, optional, leading)
        return patch.object(contract_decoding.EnvelopeContract, "__init__", build)
    import ast

    def second_table(original=RoleToModelMapChecks._driver):
        def driver(self):
            tree = original(self)
            tree.body.append(ast.parse('_LOCAL_PROFILE = {"VERIFIER": ("local_auditor", "m")}').body[0])
            return tree
        return patch.object(RoleToModelMapChecks, "_driver", driver)
    import auditor_questions
    import role_graph
    import execution_topology

    def no_record(write=execution_topology.Runtime.write):
        def without(self):
            graph, self.role_graph = self.role_graph, {"schema": "role-graph-v1", "roles": {}}
            try:
                write(self)
            finally:
                self.role_graph = graph
        return patch.object(execution_topology.Runtime, "write", without)
    return [
        ("a cycle in the role graph is accepted",
         lambda: _cases(RoleGraphChecks, "test_a_cycle_is_refused"),
         lambda: patch.object(role_graph, "order", lambda graph: sorted(graph["roles"]))),
        ("an order against a dependency is accepted",
         lambda: _cases(RoleGraphChecks, "test_an_order_against_a_dependency_is_refused"),
         lambda: patch.object(role_graph, "check_order", lambda graph, sequence: list(sequence))),
        ("the role tasks carry no edge to what they need",
         lambda: _cases(RoleGraphChecks, "test_independent_roles_run_at_once_on_their_models_lanes"),
         lambda: patch.object(role_graph, "needs", lambda graph, role: [])),
        ("the saved graph is not what ran",
         lambda: _cases(RoleGraphChecks, "test_the_saved_graph_is_what_ran"),
         no_record),
        ("a task started before what it needs is not named",
         lambda: _cases(RoleGraphChecks, "test_the_saved_graph_is_what_ran"),
         lambda: patch.object(role_graph, "_times", lambda events, original=role_graph._times: (
             original(events)[0], {k: float("-inf") for k in original(events)[1]}))),
    ] + [
        ("the driver's judged absence never takes the decision form",
         lambda: _cases(RuleCheckQuestionChecks, "test_the_drivers_branch_decides_and_hands_the_reply_on"),
         lambda: patch.object(auditor_questions, "asks", lambda question, agent=None: False)),
        ("a not met record is written with no field Python named",
         lambda: _cases(RuleCheckQuestionChecks, "test_a_settled_not_met_is_one_screened_record_and_nothing_else_is"),
         lambda: patch.object(auditor_questions, "rule_check_reply",
                              lambda *a, original=auditor_questions.rule_check_reply, **k: original(
                                  *a, **dict(k, field_label=k.get("field_label") or "any field")))),
        ("the question is asked before its form is adopted",
         lambda: _cases(RuleCheckQuestionChecks, "test_asked_only_once_adopted_and_measured"),
         lambda: patch.object(auditor_questions, "form_of", lambda question: auditor_questions.DECISION_FORM)),
        ("the driver's phase 5 never takes the pair decision form",
         lambda: _cases(PairFidelityQuestionChecks, "test_the_drivers_phase_5_branch_takes_it_only_once_adopted"),
         lambda: patch.object(auditor_questions, "asks", lambda question, agent=None: False)),
        ("an unsettled pair answer writes an item",
         lambda: _cases(PairFidelityQuestionChecks, "test_the_decisions_are_posted_under_the_model_and_joined"),
         lambda: patch.object(auditor_questions, "_settled_label", lambda decision, question: (decision or {}).get("decided"))),
        ("a training row is not the rule check as the pipeline sends it",
         lambda: _cases(TrainingRowChecks),
         lambda: patch.object(auditor_questions, "render_rule_check",
                              lambda question, rule, unit: "Rule: %s / Text: %s" % (rule, unit))),
        ("a development question's rule is not the text the pipeline's parser reads",
         lambda: _cases(DevelopmentQuestionChecks),
         lambda: patch.object(__import__("build_auditor_questions"), "rule_texts",
                              lambda rules: {r["rule_id"].upper(): r["text"] + " [as written]" for r in rules})),
        ("the replay pass does not hand the auditor training file over",
         lambda: _cases(AuditorTrainingPassChecks, "test_the_session_trains_then_asks_and_leaves_one_record_a_question"),
         lambda: patch.object(__import__("replay_prompts"), "is_auditor_training", lambda path: False)),
        ("a recipe is not held to its questions",
         lambda: _cases(AuditorTrainingPassChecks, "test_a_recipe_refuses_another_question_and_a_question_that_is_a_row"),
         lambda: patch.object(__import__("auditor_train"), "check", lambda value: value)),
        ("half B is scored with no committed opening",
         lambda: _cases(HeldOutReadChecks, "test_half_b_is_scored_only_after_a_committed_opening_and_record"),
         lambda: patch.object(_auditor_read(), "opening_row",
                              lambda repo, attempt, candidate, material: (1, 0.025, "HEAD"))),
        ("half B is scored from an uncommitted register",
         lambda: _cases(HeldOutReadChecks, "test_half_b_is_scored_only_after_a_committed_opening_and_record"),
         lambda: patch.object(_auditor_read(), "_git_show",
                              lambda repo, rev, path: (Path(repo) / path).read_text(encoding="utf-8"))),
        ("half B is scored after a failed half A",
         lambda: _cases(HeldOutReadChecks, "test_a_failed_half_a_never_opens_half_b"),
         _skip_passed_check),
        ("half B is tested at a fixed level",
         lambda: _cases(HeldOutReadChecks, "test_the_alpha_halves_with_each_opening"),
         lambda: patch.object(_auditor_read(), "opening_row",
                              lambda repo, attempt, candidate, material, original=_auditor_read().opening_row: (
                                  lambda k, a, c: (k, 0.025, c))(*original(repo, attempt, candidate, material)))),
        ("attempt 2's offsets are never applied",
         lambda: _cases(HeldOutReadChecks, "test_attempt_2_offsets_are_fitted_on_half_a_and_applied_frozen_to_half_b"),
         lambda: patch.object(_auditor_read(), "calibrated", lambda rows, offsets: list(rows))),
        ("half B refits attempt 2's offsets",
         lambda: _cases(HeldOutReadChecks, "test_attempt_2_offsets_are_fitted_on_half_a_and_applied_frozen_to_half_b"),
         lambda: patch.object(_auditor_read(), "calibrated",
                              lambda rows, offsets, original=_auditor_read().calibrated: original(
                                  rows, _auditor_read().fit_offsets(rows) if rows and rows[0].get("half") == "B" else offsets))),
        ("half A reads half B's rows",
         lambda: _cases(HeldOutReadChecks, "test_half_a_is_read_alone"),
         lambda: patch.object(_auditor_read(), "_rows",
                              lambda path, half, questions, original=_auditor_read()._rows: [
                                  dict(row, half=half) for row in original(path, half, questions)] + _b_rows(path, questions))),
        ("rule_not_met is kept from a reply on a judged path",
         lambda: _cases(RuleNotMetChecks, "test_each_refusal"),
         lambda: patch.object(__import__("paired_review"), "_rule_check_refusal", _rule_check_refusal_without("path"))),
        ("rule_not_met is kept on a plan that was not uncomputable",
         lambda: _cases(RuleNotMetChecks, "test_each_refusal"),
         lambda: patch.object(__import__("paired_review"), "_rule_check_refusal", _rule_check_refusal_without("plan"))),
        ("rule_not_met is kept when not irregular",
         lambda: _cases(RuleNotMetChecks, "test_each_refusal"),
         lambda: patch.object(__import__("paired_review"), "_rule_check_refusal", _rule_check_refusal_without("irregular"))),
        ("rule_not_met is kept quoting text that is not the unit's",
         lambda: _cases(RuleNotMetChecks, "test_each_refusal"),
         lambda: patch.object(__import__("paired_review"), "_rule_check_refusal", _rule_check_refusal_without("quote"))),
        ("rule_not_met counts with no screen mark",
         lambda: _cases(RuleNotMetChecks, "test_the_relation_is_appended_last_and_reads_in_words"),
         lambda: patch.object(__import__("finding_record"), "TEXT_RELATIONS", ("contradiction", "claim_not_met"))),
        ("the claim coverage reads nothing",
         lambda: _cases(ClaimCoverageChecks),
         lambda: patch.object(__import__("auditor_pairs"), "claim_coverage",
                              lambda source, item: dict(status="no_claims", span_claims=0, referenced_claims=0,
                                                        missing_claims=[], added_claims=[]))),
        ("the driver holds its own table again",
         lambda: _cases(RoleToModelMapChecks, "test_the_driver_reads_the_registry_and_holds_no_table"),
         second_table),
        ("a heading-only unit is asked as before",
         lambda: _cases(HeadingOnlyUnitChecks, "test_a_heading_only_unit_is_asked_nothing_and_says_so"),
         lambda: patch.object(pairing_map, "carries_content", lambda text: True)),
        ("the envelope grammar ignores enumerations and bounds",
         lambda: _cases(envelope_decoding_checks.EnumerationAndBoundChecks),
         no_declarations),
        ("the four relations still make a judging call",
         lambda: _cases(report_recommendations_checks.RecommendationChecks,
                        "test_exact_comparison_admits_the_four_relations"),
         lambda: patch.object(semantic_waves, "EXACT_RELATIONS",
                              ("sum_mismatch", "product_mismatch", "above_band", "below_band"))),
    ]


def check():
    """The gate's entry: every proof passes, and each neutralisation fails its proof, then
    passes again once restored."""
    import envelope_decoding_checks
    import report_recommendations_checks
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]),
        _cases(envelope_decoding_checks.EnumerationAndBoundChecks),
        _cases(report_recommendations_checks.RecommendationChecks, "test_exact_comparison_admits_the_four_relations")])
    full = _run(suite)
    if not full.wasSuccessful():
        return "FAIL", "the auditor role proofs do not pass: %d failures, %d errors" % (
            len(full.failures), len(full.errors))
    bad = []
    for name, cases, neutralise in _neutralisations():
        with neutralise():
            caught = not _run(cases()).wasSuccessful()
        restored = _run(cases()).wasSuccessful()
        if not (caught and restored):
            bad.append(name)
    if bad:
        return "FAIL", "BAD PROOF: not caught or not restored: " + "; ".join(bad)
    return "PASS", "%d auditor role proofs pass; %d neutralisations each fail and restore" % (
        full.testsRun, len(_neutralisations()))


if __name__ == "__main__":
    print(check())
