"""Check 387 (D-663, standing order 82, #279): tools/answer_form.py reads an answer's form and never its
content. Each form the rule names is proven by a case that is read with the step and lost without it:
outer spaces, case, surrounding quotes, emphasis marks, a number written for a string, a list for one value,
one value for a list, stray punctuation at either end, code fences, and the separator in a value of two words.
Content is never guessed (WORDS-A): another word, a prefix, a fraction and an ambiguous pair are refused with
their reason names, and a drop is counted only under one of answer_form.REASONS. The last JSON object of a
reply is read (several counted), a leading answer is read past what follows it, and tools/reread_replies.py
reads a saved B1 pass again into a new folder with the frozen parser first (lead 18:57: bound files unchanged).

Each is neutralise, fail, restore, pass (scripts/effect_proof.py). No model, no file, no benchmark item.
"""
import json
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "tools"), str(ROOT / "scripts"), str(ROOT / "benchmark" / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import answer_form as af  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

# Invented declared values: a state, a two-word class, a numeric id and a letter id.
DECLARED = ("closed", "no_conflict", "7", "A1")


def reads(cases):
    """{repr(case): (declared value or None, reason or None)} of each case read against DECLARED."""
    return lambda: {repr(c): af.match(c, DECLARED) for c in cases}


def ok(cases, value):
    return {repr(c): (value, None) for c in cases}


class AnswerFormChecks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        AnswerFormChecks.evidence.append(prove_effect(
            name=name, validate=lambda: True, observe=observe,
            check=lambda: ("PASS" if observe() == expected else "FAIL", name), neutralise=neutralise))

    def _form(self, name, cases, value, target, replacement):
        observe, want = reads(cases), ok(cases, value)
        self.assertEqual(observe(), want)
        self.prove(name, observe, want, lambda: patch.object(af, target, replacement))

    def test_01_outer_spaces(self):
        self._form("outer_spaces_taken_off", [" 'closed' ", " closed. ", "\t**closed**\n"], "closed",
                   "_trim", lambda text: text)

    def test_02_case(self):
        observe = reads(["Closed", "CLOSED", "a1"])
        want = {repr("Closed"): ("closed", None), repr("CLOSED"): ("closed", None), repr("a1"): ("A1", None)}
        self.assertEqual(observe(), want)
        self.prove("case_folded", observe, want, lambda: patch.object(af, "_fold", lambda text: text))

    def test_03_quotes(self):
        self._form("surrounding_quotes_taken_off", ['"closed"', "'closed'", "`closed`", "“closed”"],
                   "closed", "QUOTE_PAIRS", ())

    def test_04_emphasis(self):
        self._form("emphasis_marks_taken_off", ["**closed**", "__closed__", "*closed*"], "closed",
                   "EMPHASIS_PAIRS", ())

    def test_05_number_for_a_string(self):
        self._form("integer_read_as_its_text", [7, [7]], "7", "integer_text", lambda value: value)

    def test_06_list_for_one_value(self):
        self._form("list_of_one_read_as_the_value", [["closed"], [" Closed. "]], "closed", "single",
                   lambda value: value)

    def test_07_one_value_for_a_list(self):
        observe = lambda: af.match_all("A1", DECLARED)
        want = (["A1"], [])
        self.assertEqual(observe(), want)
        self.assertEqual(af.match_all(["A1", "a1 ", "B9"], DECLARED), (["A1"], [af.NOT_DECLARED]))
        self.assertEqual(af.as_list(None), [])
        self.prove("one_value_read_as_a_list_of_one", observe, want,
                   lambda: patch.object(af, "as_list", lambda value: value if isinstance(value, list) else []))

    def test_08_stray_punctuation(self):
        self._form("stray_punctuation_taken_off", ["closed.", "closed,", "closed!", "closed:", "...closed;"],
                   "closed", "STRAY", "")

    def test_09_code_fences(self):
        reply = "```json\n{\"state\": \"closed\"}\n```"
        observe = lambda: (lambda t: json.loads(t) if t.strip().startswith("{") else None)(af.unfence(reply))
        want = {"state": "closed"}
        self.assertEqual(observe(), want)
        self.prove("code_fence_lines_dropped", observe, want,
                   lambda: patch.object(af, "FENCE", re.compile(r"(?!)")))

    def test_10_separator(self):
        self._form("separator_read_as_a_space", ["no conflict", "NO  CONFLICT"],
                   "no_conflict", "SEPARATORS", ())

    def test_11_content_never_guessed(self):
        # WORDS-A: another word, a prefix, a word inside, a fraction, a boolean, an object: refused, each named.
        got = {repr(c): af.match(c, DECLARED) for c in ("shut", "close", "closed down", 7.0, True, {"v": "closed"},
                                                       ["closed", "7"], [], "**", None, "A-1", "3.1")}
        want = {"'shut'": (None, af.NOT_DECLARED), "'close'": (None, af.NOT_DECLARED),
                "'closed down'": (None, af.NOT_DECLARED), "7.0": (None, af.NOT_TEXT), "True": (None, af.NOT_TEXT),
                "{'v': 'closed'}": (None, af.NOT_TEXT), "['closed', '7']": (None, af.LIST_NOT_ONE),
                "[]": (None, af.LIST_NOT_ONE), "'**'": (None, af.EMPTY), "None": (None, af.EMPTY),
                "'A-1'": (None, af.NOT_DECLARED), "'3.1'": (None, af.NOT_DECLARED)}
        self.assertEqual(got, want)
        # Inner text is never touched: a point inside a figure and a hyphen inside an id stay.
        self.assertEqual((af.bare(" 3.1. "), af.bare("A-1")), ("3.1", "A-1"))
        # Two declared values that read alike: the answer is refused, never one of them picked.
        self.assertEqual(af.match("no conflict", ("no_conflict", "No Conflict")), (None, af.AMBIGUOUS))

    def test_12_drops_counted_by_reason(self):
        def observe():
            drops = af.Drops()
            for value in ("shut", ["a", "b"], "closed", 7.0):
                _, why = af.match(value, DECLARED)
                if why:
                    drops.add("state", why)
            try:
                drops.add("state", "unknown")
                named_only = False
            except ValueError:
                named_only = True
            return drops.as_dict(), drops.total(), named_only
        want = ({"state": {af.LIST_NOT_ONE: 1, af.NOT_DECLARED: 1, af.NOT_TEXT: 1}}, 3, True)
        self.assertEqual(observe(), want)
        self.prove("drops_counted_under_named_reasons_only", observe, want,
                   lambda: patch.object(af, "REASONS", af.REASONS + ("unknown",)))


    def test_13_last_object_several_counted(self):
        # One JSON rule for every reader (lead 18:57): the LAST top-level object that parses, fence lines
        # dropped, a brace inside a string not counted; several objects counted, never dropped.
        fence = "`" * 3
        reply = 'For example {"label": "x"}. Answer:\n' + fence + 'json\n{"label": "closed", "why": "a } b"}\n' + fence
        observe = lambda: (af.last_object(reply), af.last_object('{"a": "x \\| y"}')[0], af.last_object("none"),
                           af.last_object("{not json}")[1], af.last_object("")[1])
        want = (({"label": "closed", "why": "a } b"}, None, True), {"a": "x \\| y"}, (None, af.NO_OBJECT, False),
                af.JSON_INVALID, af.EMPTY)
        self.assertEqual(observe(), want)
        real = af._objects
        self.prove("the_last_object_is_read", observe, want,
                   lambda: patch.object(af, "_objects", lambda text: real(text)[:1]))
        drops = af.Drops()
        drops.add("reply", af.SEVERAL_OBJECTS)
        self.assertEqual(drops.as_dict(), {"reply": {"several_objects_last_read": 1}})

    def test_14_leading_answer(self):
        # A reply that opens with one declared answer and goes on after a boundary, or that carries a field
        # label before it, is that answer; a prefix of a word, or a word that is no answer, is not.
        declared = ("supported", "unsupported", "cannot_tell")
        replies = ("Supported, because the text says so", "Answer: Cannot tell. Nothing in it", "**Unsupported**",
                   "supportedly", "maybe", "")
        observe = lambda: [af.leading(r, declared) for r in replies]
        want = [("supported", None), ("cannot_tell", None), ("unsupported", None), (None, af.NOT_DECLARED),
                (None, af.NOT_DECLARED), (None, af.EMPTY)]
        self.assertEqual(observe(), want)
        self.prove("a_leading_answer_is_read", observe, want,
                   lambda: patch.object(af, "_AFTER", re.compile(r"(?!)")))
        self.prove("a_field_label_is_taken_off", observe, want,
                   lambda: patch.object(af, "_LABEL", re.compile(r"(?!)")))

    def test_15_b1_labels_read_again(self):
        # tools/reread_replies.py b1: a saved B1 pass read again from its reply records into a NEW folder, the
        # frozen parser (bound, unchanged) first and the form reading only where it read no label; a sensitive
        # reply (no text kept) copied and counted; the pass's own files untouched.
        import tempfile
        import reread_replies as rr
        import bare_model as bm
        spec = bm.load_prompt()
        key, bench = next(iter(spec["benchmarks"].items()))
        first = bm.label_names(bench)[0]
        with tempfile.TemporaryDirectory() as td:
            run, out = Path(td) / "run", Path(td) / "again"
            (run / "labels").mkdir(parents=True)
            (run / "audit" / "model_replies").mkdir(parents=True)
            replies = {"i1": json.dumps({"label": first + "."}), "i2": json.dumps({"label": "zzz"}),
                       "i3": None, "i4": json.dumps({"label": [first]})}
            for n, (item, text) in enumerate(sorted(replies.items())):
                reply = {"sha256": "0" * 64, "length_bytes": 1}
                if text is not None:
                    reply["text"] = text
                (run / "audit" / "model_replies" / ("%06d_c%d.json" % (n, n))).write_text(json.dumps(
                    {"call_id": "c%d" % n, "sequence": n, "backend_ok": True, "reply": reply}), encoding="utf-8")
                (run / "labels" / (item + ".json")).write_text(json.dumps(
                    {"item_id": item, "benchmark": key, "call_id": "c%d" % n, "backend_ok": True, "label": None,
                     "abstain": True, "parse_failure": "label_not_in_list", "evidence": None}), encoding="utf-8")
            observe = lambda: (lambda c: (c["read_again"], c["changed"], c["form_read"], c["reply_not_kept"],
                                          c["parse_failures"]))(rr.b1_relabel(run, out, spec))
            want = (3, 2, 2, 1, {"label_not_in_list": 1})
            self.assertEqual(observe(), want)
            self.assertEqual(json.loads((out / "labels" / "i1.json").read_text(encoding="utf-8"))["label"], first)
            self.assertIsNone(json.loads((run / "labels" / "i1.json").read_text(encoding="utf-8"))["label"])
            self.assertFalse(bm.parse_reply(replies["i1"], bench)["parsed"])   # the frozen parser, unchanged
            self.prove("b1_labels_read_again_whatever_their_form", observe, want,
                       lambda: patch.object(rr, "b1_label", lambda reply, bench, item_id=None: dict(
                           bm.parse_reply(reply, bench, item_id), form_read=False, form_drop=None)))
            with self.assertRaises(ValueError):
                rr.b1_relabel(run, run / "inside", spec)


def check():
    AnswerFormChecks.evidence = []
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(AnswerFormChecks).run(result)
    if not result.wasSuccessful():
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors]
        return "FAIL", "; ".join(problems[:5])
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass, no model and no item: outer spaces, case, "
                    "surrounding quotes, emphasis marks, a number for a string, a list for one value and one value "
                    "for a list, stray punctuation, code fences and the separator are read as the declared value; "
                    "another word, a prefix, a fraction and an ambiguous pair are refused by name, and drops are "
                    "counted under the named reasons only; the last object of a reply read and several counted, a "
                    "leading answer read past what follows it and past a field label, and a saved B1 pass read "
                    "again into a new folder, the frozen parser first" % len(AnswerFormChecks.evidence))


def main():
    status, detail = check()
    for proof in AnswerFormChecks.evidence:
        print(proof["name"], proof["status"])
    print(status, detail)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
