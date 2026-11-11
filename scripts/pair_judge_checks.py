"""Gate check: find then judge (P2 (a)). Python proposes pairs of passages of one document, and
the replay's reader scores what a model said of each. No model, no provider, no key: an invented
document, invented replies and an invented key, in a temporary folder.

Each proof is neutralise, fail, restore, pass (scripts/effect_proof.py):
1. passages keep their place: every passage is the text at its offsets, a heading and a table row
   are no passage, and a stop inside a short stretch joins the next;
2. the proposer ranks by shared rare words: the two passages on one subject come first, passages
   sharing no word are no pair, and identical passages are no pair;
3. a flag needs both orders in the bar's view, an unreadable order flags nothing;
4. a flag on a gold document is right only on a pair touching a marked passage;
5. a pair prompt is its template's rendering of the document's own passages: a tampered one is
   refused by load_prompts;
6. the verdict needs every condition of the bar;
7. review keeps a pair only when both orders say contradict, and shows the model both passages;
8. the runtime's question is the measured one, word for word, with the same limit and allowance;
9. the real phase 5.5 carries a declared rule's pair to review_data.json as a model's finding;
10. two passages differing only in a short word or a figure stay a pair;
11. the scorer marks a sentence on its best passage alone, never on a near copy as well;
12. a whole read scores an invented pass, and refuses a stopped pass, other inputs and a second
    read into one folder;
13. a sensitive run's masker sees the pair question, and the backend only what it returns;
14. a pair across two units is a record naming both, each quote held to its own unit, and a
    model's reply on a judged path cannot reach across units by writing the field (INFRA-047);
15. a kept pair goes through judged_item_refusal on its unit, then carries Python's mark;
16. the runtime reads a reply as the replay reads it, on fences, braces, a bad escape and a raw
    line break;
17. a failed call is counted apart from an unreadable reply, five in a row stop the rule, and a
    raised failure keeps the document's computed findings and says so;
18. a document is encoded once, a second declared rule makes no call, above `max_passages` nothing
    is asked and the row says so, and numpy leaves the ranking as it was;
19. a compare rule makes no unit plan, and refuses `[scope:]`, `[requires:]` and `[unless:]`, on a
    heading and in JSON alike;
20. an external rule declaring `compare` differs from a convention that does not;
21. every pair call leaves run_task's trail, its evidence naming the document, and a kept pair's
    calls end not promoted.
"""
import contextlib
import importlib
import inspect
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "benchmark" / "baselines"
for path in (str(BASELINES), str(ROOT / "scripts"), str(ROOT / "tools")):
    if path not in sys.path:
        sys.path.insert(0, path)

import agent_activation  # noqa: E402
import call_evidence  # noqa: E402
import convention_parser  # noqa: E402
import external_rules  # noqa: E402
import finding_record  # noqa: E402
import generation_observation  # noqa: E402
import passage_pairs  # noqa: E402
import reply_records  # noqa: E402
import sensitivity_layer  # noqa: E402
import run_options  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

# Benchmark modules, on the path only from here: the gate's import scan reads statements.
doc_judge = importlib.import_module("doc_judge")
pair_judge = importlib.import_module("pair_judge")

TEXT = ("# Annual note\n\n"
        "| table | row | stays out |\n\n"
        "Dr. Lund says the harbour authority owns the northern quay outright.\n\n"
        "Rainfall across the valley was unusually heavy last winter season.\n\n"
        "The northern quay is leased from a private harbour owner.\n\n"
        "Rainfall across the valley was unusually heavy last winter season.\n")


@contextlib.contextmanager
def patched(owner, name, value):
    old = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield
    finally:
        setattr(owner, name, old)


def observe_passages():
    items = passage_pairs.passages(TEXT)
    return {"texts": [p["text"] for p in items],
            "placed": all(TEXT[p["start"]:p["end"]] == p["text"] for p in items)}


def expected_passages():
    return {"texts": ["Dr. Lund says the harbour authority owns the northern quay outright.",
                      "Rainfall across the valley was unusually heavy last winter season.",
                      "The northern quay is leased from a private harbour owner.",
                      "Rainfall across the valley was unusually heavy last winter season."],
            "placed": True}


def observe_proposal():
    items = passage_pairs.passages(TEXT)
    return [(p["a"], p["b"]) for p in passage_pairs.propose(items, 10)]


def expected_proposal():
    return [(0, 2)]


def call(pair, order, cls):
    return {"pair": pair, "order": order, "cls": cls}


ROWS = [call((0, 1), "ab", "FLAG"), call((0, 1), "ba", "FLAG"),
        call((0, 2), "ab", "FLAG"), call((0, 2), "ba", "CLEAR"),
        call((1, 2), "ab", "FLAG"), call((1, 2), "ba", None)]


def observe_orders():
    return sorted(pair_judge.flagged_pairs(ROWS, "both_orders"))


def expected_orders():
    return [(0, 1)]


def observe_place():
    two = {"marked": [1], "partner": [4], "references": 1}
    one = {"marked": [1], "partner": [1], "references": 1}
    lone = {"marked": [1], "partner": [], "references": 0}
    named = {"marked": [1], "partner": [], "references": 1}
    return [pair_judge.place({(1, 4)}, two), pair_judge.place({(1, 2)}, two), pair_judge.place({(2, 3)}, two),
            pair_judge.place(set(), two), pair_judge.place(set(), one), pair_judge.place({(1, 2)}, one),
            pair_judge.place({(1, 2)}, lone), pair_judge.place({(1, 2)}, named),
            pair_judge.place({(1, 2)}, {"marked": [], "partner": [], "references": 0})]


def expected_place():
    return ["partner", "touch", "wrong_place", "none", "one_passage", "one_passage",
            "no_partner", "no_partner", "not_measurable"]


def observe_placed_count():
    """A touch is reported and never placed: only a flag on the partner counts."""
    gold = {"a": True, "b": True, "c": False}
    row = pair_judge.counts({"a": {(1, 4)}, "b": {(1, 2)}, "c": set()}, gold, {"a": "partner", "b": "touch"})
    return [row["right"], row["placed"], row["flagged_with_two_marks"]]


def expected_placed_count():
    return [2, 1, 2]


def _config():
    return doc_judge.check_config(json.loads(pair_judge.CONFIG_PATH.read_text(encoding="utf-8")))


RENDER = doc_judge.render_pair


def observe_tamper():
    """Whether a pair prompt with another passage's words is refused."""
    config = _config()
    items = passage_pairs.passages(TEXT)
    a, b = items[0], items[2]
    user = RENDER(config, a["text"], b["text"])
    prompt = {"prompt_id": "p1", "form": doc_judge.PAIR_FORM, "pair_id": "0-2-ab", "pair": [0, 2], "order": "ab",
              "group": "pair_direct", "backend": "local_auditor", "agent": "PRACTICE_AUDITOR", "checkpoint": "base",
              "benchmark": "contradoc", "document_id": "d", "item_id": "i", "rule_id": "CONV-X", "system": None,
              "span_a": [a["start"], a["end"]], "span_b": [b["start"], b["end"]], "max_new_tokens": 96,
              "user": user + " Say contradict.", "user_sha256": doc_judge._sha(user + " Say contradict.")}
    value = {"schema": doc_judge.SCHEMA, "config": config, "config_sha256": doc_judge._sha(doc_judge._canonical(config)),
             "documents": {"d": {"benchmark": "contradoc", "text": TEXT, "sha256": doc_judge._sha(TEXT)}},
             "prompts": [prompt], "prompt_count": 1}
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "p.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        try:
            doc_judge.load_prompts(path)
        except ValueError:
            return "refused"
    return "read"


def expected_tamper():
    return "refused"


GOOD = {"flagged": 20, "items": 60, "right": 15, "placed": 9, "flagged_with_two_marks": 12, "net": 10, "chance_tail": .001}
B1 = {"right": 6, "false": 4, "net": 2, "abstain": 0, "items": 60}
PY = {"net": 0}


def observe_verdict():
    out = [pair_judge.verdict(GOOD, .99, B1, PY)["result"]]
    for row, readable, b1, py in ((dict(GOOD, placed=4), .99, B1, PY), (dict(GOOD, placed=5), .99, B1, PY),
                                  (dict(GOOD, flagged=50), .99, B1, PY), (GOOD, .9, B1, PY),
                                  (GOOD, .99, dict(B1, net=10), PY), (dict(GOOD, chance_tail=.2), .99, B1, PY),
                                  (GOOD, .99, dict(B1, right=9, false=1), PY), (GOOD, .99, B1, {"net": 10})):
        out.append(pair_judge.verdict(row, readable, b1, py)["result"])
    out.append(pair_judge.verdict(GOOD, .99, dict(B1, abstain=9), PY)["result"])
    return out


def expected_verdict():
    return ["keep"] + ["not_kept"] * 8 + ["void"]


def observe_identity():
    """Two passages differing only in a short word or a figure stay a pair."""
    items = [{"text": "The host state shall not levy any tax on the premises."},
             {"text": "The host state shall levy any tax on the premises."},
             {"text": "Notice must be given within 5 days of arrival here."},
             {"text": "Notice must be given within 9 days of arrival here."}]
    return sorted((p["a"], p["b"]) for p in passage_pairs.propose(items, 2))


def expected_identity():
    return [(0, 1), (2, 3)]


QUAY_A = "The harbour authority owns the northern quay outright since the founding deed."
QUAY_B = "The northern quay is leased by the harbour authority from a private owner."
COMPARE_RULE = {"id": "CONV-009", "category": "conv-h09", "severity": "required", "compare": "passages",
                "rule": "No passage may state what another passage rules out."}


def _review(units, ask, rule=None, config=None, **kwargs):
    config = config or passage_pairs.load_config()
    prepared = passage_pairs.prepare(units, config, lambda items: None)
    return passage_pairs.review(prepared, rule or COMPARE_RULE, "CONV-H09", ask, config, **kwargs)


def _contradict(user):
    return '{"outcome": "contradict", "reason": "both name the owner"}'


def observe_runtime():
    """Both orders through passage_pairs.review on invented replies: what becomes a record."""
    units = [{"unit_id": "u01-a", "text": QUAY_A + " " + QUAY_B}]
    asked = []

    def ask(user):
        asked.append(user)
        return _contradict(user)
    kept, calls = _review(units, ask)
    one, _ = _review(units, iter_replies())
    return {"kept": [(k["quote"], k["quote_b"], k["unit_id"], k["relation"], k.get("text_screened")) for k in kept],
            "calls": calls, "one_order": len(one), "shown_both": all(QUAY_A in u and QUAY_B in u for u in asked)}


def iter_replies():
    replies = iter(['{"outcome": "contradict"}', 'not json at all'])
    return lambda user: next(replies)


def expected_runtime():
    return {"kept": [(QUAY_A, QUAY_B, "u01-a", "contradiction", True)],
            "calls": {"passages": 2, "pairs": 1, "made": 2, "reused": 0, "failed": 0, "unreadable": 0, "one_order_only": 0,
                      "failed_beside_flag": 0, "ranked_by": "words", "cross_unit_kept": 0, "refused": [],
                      "stopped": None, "raised": None, "not_asked": None},
            "one_order": 0, "shown_both": True}


def observe_cross_unit():
    """INFRA-047: a pair across two units is asked in both orders and is a model's record at the
    first unit, naming the second, and the reader line names both only by Python's mark."""
    kept, calls = _review([{"unit_id": "u01-a", "text": QUAY_A}, {"unit_id": "u02-b", "text": QUAY_B}], _contradict)
    item = kept[0] if kept else {}
    unmarked = {k: v for k, v in item.items() if k != finding_record.SCREENED_FIELD}
    return {"kept": len(kept), "made": calls["made"], "count": calls["cross_unit_kept"], "refused": calls["refused"],
            "where": (item.get("unit_id"), item.get("compared_unit_id"), item.get("quote"), item.get("quote_b")),
            "finding": finding_record.is_finding(item) if item else None,
            "line": ("u01-a" in finding_record.reader_line(item), "u02-b" in finding_record.reader_line(item)) if item else None,
            "unmarked_line": "u02-b" in finding_record.reader_line(unmarked) if item else None}


def expected_cross_unit():
    return {"kept": 1, "made": 2, "count": 1, "refused": [], "where": ("u01-a", "u02-b", QUAY_A, QUAY_B),
            "finding": True, "line": (True, True), "unmarked_line": False}


def _cross_refusal(**fields):
    """The one test on a contradiction whose first quote stands in its unit, QUAY_A in `u01-a`."""
    second = fields.pop("second", None)
    unit = fields.pop("unit", QUAY_A)
    item = dict({"unit_id": "u01-a", "relation": "contradiction", "record_verdict": "irregular",
                 "quote": QUAY_A, "quote_b": QUAY_B}, **fields)
    return passage_pairs.paired_review.judged_item_refusal(item, {"id": "CONV-009"}, None, unit, second_unit_text=second)


def observe_cross_refusals():
    """Each way a record could claim a second unit Python did not read, on the one test."""
    both = QUAY_A + " " + QUAY_B
    return {"kept": _cross_refusal(compared_unit_id="u02-b", second=QUAY_B),
            "one unit as before": _cross_refusal(unit=both),
            "a reply writes the field": _cross_refusal(compared_unit_id="u02-b", unit=both),
            "text with no name": _cross_refusal(second=QUAY_B),
            "its own unit": _cross_refusal(compared_unit_id="u01-a", second=QUAY_B, unit=both),
            "blank second unit": _cross_refusal(compared_unit_id="u02-b", second="  "),
            "held to the second": _cross_refusal(compared_unit_id="u02-b", second="Other words stand in this unit here.", unit=both),
            "same words": _cross_refusal(compared_unit_id="u02-b", second=QUAY_A, quote_b=QUAY_A)}


def expected_cross_refusals():
    unchecked = "contradiction names a second unit no check read"
    return {"kept": None, "one unit as before": None, "a reply writes the field": unchecked,
            "text with no name": unchecked, "its own unit": unchecked,
            "blank second unit": "contradiction with no unit text to check against",
            "held to the second": "contradiction second quote does not appear in this unit",
            "same words": "contradiction quotes one passage twice"}


def _with_source(module, name, old, new):
    """`module.name` with one line of its own source changed, as a neutralisation."""
    source = inspect.getsource(getattr(module, name))
    assert source.count(old) == 1, old
    space = dict(vars(module))
    exec(source.replace(old, new), space)
    return patched(module, name, space[name])


def _refusal_with(old, new):
    return _with_source(passage_pairs.paired_review, "judged_item_refusal", old, new)


def observe_phase_cross():
    """The real phase 5.5 on two units: the record reaches the deliverables at the first unit,
    names the second, stays a model's and unpromoted, and the reviewed document shows both ids."""
    import agent_wrapper
    import honest_output_checks as hoc
    from unittest.mock import patch
    text = chr(10).join((hoc.DOC_TEXT, "## Entry Quay", "", QUAY_A, "", "## Entry Pier", "", QUAY_B, ""))

    def dispatch(self, stable, dynamic="", **kwargs):
        both = QUAY_A in stable and QUAY_B in stable
        reply = '{"outcome": "%s", "reason": "fixture"}' % ("contradict" if both else "compatible")
        return agent_wrapper.CallResult(self.backend, "fixture-auditor", reply)
    with tempfile.TemporaryDirectory() as td, patch.object(agent_wrapper.AgentWrapper, "dispatch", dispatch), \
            patch.object(passage_pairs, "embed", lambda items: None):
        run = hoc.mocked_run(Path(td), style_guardian=False, text=text, rules=hoc.RULES + [COMPARE_RULE])
        found, amended, shown = [], 0, []
        for path in sorted(Path(run["run_dir"]).rglob("review_data.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            amended += sum(QUAY_A in json.dumps(a) for a in data.get("amendments") or [])
            for f in data.get("model_findings_not_promoted") or []:
                if f.get("relation") == "contradiction":
                    found.append((f.get("quote"), f.get("quote_b"), f.get("written_by"), f.get("promoted"),
                                  str(f.get("unit_id")).endswith("entry-quay"),
                                  str(f.get("compared_unit_id")).endswith("entry-pier")))
                    shown.append(f.get("compared_unit_id"))
        reviewed = "".join(p.read_text(encoding="utf-8") for p in Path(run["run_dir"]).rglob("reviewed_document.md"))
    return {"found": found, "amended": amended, "named": bool(shown) and all(u in reviewed for u in shown)}


def expected_phase_cross():
    return {"found": [(QUAY_A, QUAY_B, "model", False, True, True)], "amended": 0, "named": True}


# Hyphens: four words to the proposer, two or three to the judged paths' whitespace count.
SHORT_A = "North-quay harbour-owner-lease."
SHORT_B = "North-quay harbour-owner-freehold."


def observe_refused():
    """A kept pair goes through the judged paths' own refusal: this one's quotes are too short."""
    kept, calls = _review([{"unit_id": "u01-a", "text": SHORT_A + chr(10) + SHORT_B}], _contradict)
    return {"kept": len(kept), "refused": calls["refused"]}


def expected_refused():
    return {"kept": 0, "refused": [{"unit_id": "u01-a", "rule_id": "CONV-009", "relation": "contradiction",
                                    "reason": "contradiction quote is too short to be a passage"}]}


REPLIES = (
    '```json\n{"outcome": "contradict", "reason": "fenced"}\n```',
    '{"outcome": "compatible", "reason": "kept"}\n```{x}',
    '{"outcome": "contradict", "reason": "the clause {a} and the clause {b} differ"}',
    '{"outcome": "contradict", "reason": "the path a\\quay is named"}',
    '{"outcome": "contradict", "reason": "one line\nand the next"}',
    'First I looked. {"outcome": "compatible"} Then {"outcome": "contradict", "reason": "the last one"}',
    '{"outcome": "cannot_tell", "reason": 7}', '{"outcome": " Contradictory "}', '{"outcome": "maybe"}',
    '{"outcome": 1}', '[1, 2]', '{"outcome": "contradict", "reason": "an open } brace"}', "", "   ", None,
)


def observe_same_reader():
    """The runtime's reading of each reply is the replay's: class and reason."""
    runtime = passage_pairs.load_config()
    measured = _config()
    classes = {o["value"]: o["class"] for o in measured["outcomes"]}
    out = []
    for reply in REPLIES:
        replay = doc_judge.parse_reply(reply, measured)
        reason = replay["reason"] if replay["outcome"] else None
        out.append(passage_pairs.read_reply(reply, runtime) == (classes.get(replay["outcome"]), reason))
    return out


def expected_same_reader():
    return [True] * len(REPLIES)


def observe_same_prompt():
    """The prompt the pipeline sends is the prompt the replay measured."""
    measured = _config()
    runtime = passage_pairs.load_config()
    return (doc_judge.render_pair(measured, QUAY_A, QUAY_B) == passage_pairs.render(runtime, QUAY_A, QUAY_B)
            and measured["max_new_tokens"] == runtime["max_new_tokens"]
            and measured["pair"]["limit"] == runtime["limit"])


def observe_phase():
    """The real phase 5.5 on a mocked run: the declared rule's pair reaches review_data.json as a
    model's finding, marked and not promoted, and a rule with no declaration asks nothing."""
    import agent_wrapper
    import honest_output_checks as hoc
    from unittest.mock import patch
    text = chr(10).join((hoc.DOC_TEXT, "## Entry Quay", "", QUAY_A, "", QUAY_B, ""))
    asked = []

    def dispatch(self, stable, dynamic="", **kwargs):
        asked.append(stable)
        both = QUAY_A in stable and QUAY_B in stable
        reply = '{"outcome": "%s", "reason": "fixture"}' % ("contradict" if both else "compatible")
        return agent_wrapper.CallResult(self.backend, "fixture-auditor", reply)
    with tempfile.TemporaryDirectory() as td, patch.object(agent_wrapper.AgentWrapper, "dispatch", dispatch), \
            patch.object(passage_pairs, "embed", lambda items: None):
        run = hoc.mocked_run(Path(td), style_guardian=False, text=text, rules=hoc.RULES + [COMPARE_RULE])
        found = []
        for path in sorted(Path(run["run_dir"]).rglob("review_data.json")):
            for f in json.loads(path.read_text(encoding="utf-8")).get("model_findings_not_promoted") or []:
                if f.get("relation") == "contradiction":
                    found.append((f.get("quote"), f.get("quote_b"), f.get("written_by"), f.get("promoted")))
    return {"found": found, "asked": bool(asked)}


def expected_phase():
    return {"found": [(QUAY_A, QUAY_B, "model", False)], "asked": True}


def observe_masked():
    """A sensitive run's masker sees the pair question and the backend sees only what it returns:
    the call skips run_task, so nothing else would mask it (LAW-IV)."""
    import agent_wrapper
    import harness.run_agent as run_agent
    import honest_output_checks as hoc
    from unittest.mock import patch
    text = chr(10).join((hoc.DOC_TEXT, "## Entry Quay", "", QUAY_A, "", QUAY_B, ""))
    seen, sent = [], []

    def masker(stable, dynamic, *, backend, agent, context=""):
        seen.append((stable, dynamic, bool(backend), bool(agent)))
        return stable.replace("harbour", "[PLACE]"), dynamic

    def dispatch(self, stable, dynamic="", **kwargs):
        sent.append(stable + dynamic)
        return agent_wrapper.CallResult(self.backend, "fixture-auditor", '{"outcome": "compatible", "reason": "fixture"}')
    real = run_agent.build_orchestrator

    def masked_orchestrator(**kwargs):
        orch = real(**kwargs)
        orch.outbound_masker = masker
        return orch
    with tempfile.TemporaryDirectory() as td, patch.object(agent_wrapper.AgentWrapper, "dispatch", dispatch),             patch.object(run_agent, "build_orchestrator", masked_orchestrator),             patch.object(passage_pairs, "embed", lambda items: None):
        hoc.mocked_run(Path(td), style_guardian=False, text=text, rules=hoc.RULES + [COMPARE_RULE])
    return {"masker_saw_both": any(QUAY_A in s and QUAY_B in s for s, _, _, _ in seen),
            "told_who": all(b and a for _, _, b, a in seen), "sent": bool(sent),
            "raw_sent": any("harbour" in s for s in sent)}


def expected_masked():
    return {"masker_saw_both": True, "told_who": True, "sent": True, "raw_sent": False}


SIX = [{"unit_id": "u01-a", "text": chr(10).join(
    "The northern quay was leased to tenant number %d of the harbour." % n for n in range(1, 7))}]


def observe_failures():
    """A failed call is not an unreadable reply; a run of them stops the rule, and a reply that
    came back in between starts the count again."""
    alternating = iter([None, "no json", None, None, None, "no json"] + [None] * 30)
    _, spaced = _review(SIX, lambda user: next(alternating))
    _, dead = _review(SIX, lambda user: None)
    pick = lambda c: (c["made"], c["failed"], c["unreadable"], c["pairs"], c["stopped"])
    return {"spaced": pick(spaced), "dead": pick(dead)}


def expected_failures():
    return {"spaced": (11, 9, 2, 0, "stopped after 5 failed calls in a row, 0 of 15 pairs answered"),
            "dead": (5, 5, 0, 0, "stopped after 5 failed calls in a row, 0 of 15 pairs answered")}


def observe_prepare_raised():
    """A failure while the document is prepared stops the rule the same way, asking nothing."""
    def embed(items):
        raise MemoryError("the card is full")
    config = passage_pairs.load_config()
    asked = []
    try:
        prepared = passage_pairs.prepare(SIX, config, embed)
    except MemoryError:
        return "the document was lost"
    kept, calls = passage_pairs.review(prepared, COMPARE_RULE, None, lambda user: asked.append(user), config)
    return {"kept": kept, "asked": asked, "raised": calls["raised"], "stopped": calls["stopped"]}


def expected_prepare_raised():
    return {"kept": [], "asked": [], "raised": "MemoryError", "stopped": "stopped by a raised MemoryError, 0 of 0 pairs answered"}


def _phase_run(dispatch, rules=()):
    """The real phase 5.5 on a mocked run with a declared rule: (pair rows, not_judged rows of
    that rule, a review_data.json, the reader's file, the run context's incomplete mark)."""
    import agent_wrapper
    import honest_output_checks as hoc
    from unittest.mock import patch
    text = chr(10).join((hoc.DOC_TEXT, "## Entry Quay", "", QUAY_A, "", QUAY_B, ""))
    with tempfile.TemporaryDirectory() as td, patch.object(agent_wrapper.AgentWrapper, "dispatch", dispatch), \
            patch.object(passage_pairs, "embed", _phase_embed["value"] or (lambda items: None)):
        run = hoc.mocked_run(Path(td), style_guardian=False, text=text, rules=hoc.RULES + [COMPARE_RULE] + list(rules))
        folder = Path(run["run_dir"])
        pairing = json.loads(next(folder.rglob("pairing_map.json")).read_text(encoding="utf-8"))
        document = pairing["batch_sheet"]
        data = json.loads(next(folder.rglob("review_data.json")).read_text(encoding="utf-8"))
        reader = next(folder.rglob("reviewed_document.md")).read_text(encoding="utf-8")
        context = run["ctx"]
    return (document["passage_pairs"], [e for e in document["not_judged"] if e.get("kind") == "passage_pair"],
            data, reader, getattr(context, "semantic_incomplete", False))


def _raising(self, stable, dynamic="", **kwargs):
    raise MemoryError("the card is full")


def observe_raised():
    """A raised generation failure leaves the document's computed findings, the row says what
    raised, the rule is on the not-judged list and the run is not called complete."""
    try:
        rows, unjudged, data, reader, incomplete = _phase_run(_raising)
    except MemoryError:
        return "the document was lost"
    return {"raised": [r["raised"] for r in rows], "stopped": [r["stopped"] for r in rows],
            "not_judged": [e["reason"] for e in unjudged], "amendments": bool(data.get("amendments")),
            "reader": "the call to the model failed" in reader, "incomplete": incomplete}


def expected_raised():
    stopped = "stopped by a raised MemoryError, 0 of 2 pairs answered"
    return {"raised": ["MemoryError"], "stopped": [stopped], "not_judged": [stopped], "amendments": True,
            "reader": True, "incomplete": True}


def observe_failed_calls():
    """A failed reply reaches the row as failed, never as unreadable, and marks the run."""
    import agent_wrapper

    def dispatch(self, stable, dynamic="", **kwargs):
        return agent_wrapper.CallResult(self.backend, "fixture-auditor", "", ok=False, error="fixture")
    rows, unjudged, _, reader, incomplete = _phase_run(dispatch)
    return {"rows": [(r["failed"], r["unreadable"], r["stopped"]) for r in rows], "not_judged": [e["reason"] for e in unjudged],
            "reader": "some calls to the model failed, so those pairs were not judged" in reader, "incomplete": incomplete}


def expected_failed_calls():
    return {"rows": [(4, 0, None)], "not_judged": ["4 of 4 calls failed"], "reader": True, "incomplete": True}


def observe_partial_stop():
    """A stop after a record was kept says so in the reader's words, never that nothing was kept."""
    import agent_wrapper
    calls = []

    def dispatch(self, stable, dynamic="", **kwargs):
        calls.append(stable)
        if len(calls) > 2:
            raise MemoryError("the card is full")
        return agent_wrapper.CallResult(self.backend, "fixture-auditor", _contradict(stable))
    rows, unjudged, data, reader, _ = _phase_run(dispatch)
    return {"kept": [r["kept"] for r in rows], "why": [e["why"] for e in unjudged],
            "shown": any(f.get("relation") == "contradiction" for f in data.get("model_findings_not_promoted") or []),
            "reader": "what it kept before then is shown" in reader, "nothing kept said": "nothing from its reply was kept" in reader}


def expected_partial_stop():
    return {"kept": [1], "why": ["pairs_partly_stopped"], "shown": True, "reader": True, "nothing kept said": False}


def observe_rows_by_kind():
    """Every kind of stop has its own row, and the reader has words for every `why`, in the second output language
    too; a preparation failure made no call and says that."""
    import reviewed_document
    base = {"not_asked": None, "stopped": None, "made": 0, "failed": 0, "reused": 0, "passages": 4}
    rows = [passage_pairs.unjudged("R", dict(base, **calls), kept) for calls, kept in (
        ({"stopped": "s"}, []), ({"stopped": "s", "made": 3}, [{}]), ({"stopped": "s", "made": 3}, []),
        ({"failed": 1, "made": 8}, []), ({"not_asked": "n"}, []), ({"not_asked": "n", "why": "no_threshold"}, []),
        ({}, []), ({"made": 8}, []), ({"reused": 4}, []))]
    whys = [r and r["why"] for r in rows]
    # A row's words: its kind's own, or for `failed` the failed call's (reviewed_document._why_not_checked).
    worded = lambda why: why == "failed" or why in reviewed_document.WHY_BY_KIND
    return {"why": whys, "every row worded": all(worded(w) for w in whys if w is not None),
            "no row without a reason": all(r is None or r["why"] for r in rows),
            "words": sorted(k for k in reviewed_document.WHY_BY_KIND if not k.startswith("cells_")),
            "second_language": all(_turkish(v) for v in reviewed_document.WHY_BY_KIND.values()) and _turkish(reviewed_document.WHY_CALL_FAILED)}


def expected_rows_by_kind():
    return {"why": ["pairs_not_prepared", "pairs_partly_stopped", "failed", "pairs_some_failed", "too_many_passages", "no_threshold", "pairs_none", None, None],
            "every row worded": True, "no row without a reason": True,
            "words": ["compare_in_wide", "no_threshold", "pairs_none", "pairs_not_prepared", "pairs_partly_stopped", "pairs_some_failed", "too_many_passages"],
            "second_language": True}


def observe_failed_order():
    """A pair is answered only with both replies back; a failed order beside a flag is counted
    apart from a reply that said otherwise."""
    replies = iter([_contradict(""), None, _contradict(""), '{"outcome": "compatible"}'])
    _, calls = _review([{"unit_id": "u", "text": QUAY_A + chr(10) + QUAY_B + chr(10) + "The northern quay was leased by the harbour."}],
                       lambda user: next(replies, '{"outcome": "compatible"}'))
    return [calls["pairs"], calls["failed_beside_flag"], calls["one_order_only"], calls["failed"]]


def expected_failed_order():
    return [2, 1, 1, 1]


SECOND_RULE = dict(COMPARE_RULE, id="CONV-010", category="conv-h10", rule="No two passages may disagree about one thing.")
REAL_PREPARE, REAL_REVIEW, REAL_LOAD = passage_pairs.prepare, passage_pairs.review, passage_pairs.load_config
REAL_RECORD = passage_pairs.record


def _contradict_call(calls):
    import agent_wrapper

    def dispatch(self, stable, dynamic="", **kwargs):
        calls.append(stable)
        return agent_wrapper.CallResult(self.backend, "fixture-auditor", _contradict(stable))
    return dispatch


def observe_two_rules():
    """A second declared rule costs no encoding and no call, and has its own records."""
    calls, encoded = [], []

    def embed(items):
        encoded.append(len(items))
        return None
    rows, _, data, _, _ = _phase_run_counted(_contradict_call(calls), embed)
    kept = sorted(f.get("rule_id") for f in data.get("model_findings_not_promoted") or [] if f.get("relation") == "contradiction")
    return {"encoded": len(encoded), "calls": len(calls), "rows": [(r["rule_id"], r["made"], r["reused"], r["ranked_by"]) for r in rows],
            "kept": kept}


def expected_two_rules():
    return {"encoded": 1, "calls": 4, "rows": [("CONV-009", 4, 0, "words"), ("CONV-010", 0, 4, "words")],
            "kept": ["CONV-009", "CONV-009", "CONV-010", "CONV-010"]}


def _phase_run_counted(dispatch, embed):
    real = _phase_embed.get("value")
    _phase_embed["value"] = embed
    try:
        return _phase_run(dispatch, rules=[SECOND_RULE])
    finally:
        _phase_embed["value"] = real


_phase_embed = {"value": None}


def _prepare_per_rule(prepared, *args, **kwargs):
    return REAL_REVIEW(REAL_PREPARE(prepared["units"], REAL_LOAD()), *args, **kwargs)


def _no_memory(*args, **kwargs):
    return REAL_REVIEW(*args, **dict(kwargs, memo={}))


def observe_other_model():
    """An answer is reused only from the model that gave it: a rule judged on another model is
    asked again. The two agents run different models in the registry."""
    import pipeline as driver
    from unittest.mock import patch
    calls = []
    agents = {"CONV-009": "PRACTICE_AUDITOR", "CONV-010": "STYLE_GUARDIAN"}
    real = driver._paired_judging_agent
    with patch.object(driver, "_paired_judging_agent",
                      lambda rule, assignment: agents.get(rule.get("id")) or real(rule, assignment)):
        rows, _, _, _, _ = _phase_run(_contradict_call(calls), rules=[SECOND_RULE])
    return [(r["agent"], r["made"], r["reused"]) for r in rows]


def expected_other_model():
    return [("PRACTICE_AUDITOR", 4, 0), ("STYLE_GUARDIAN", 4, 0)]


def observe_max_passages():
    """Above the declared number no pair is asked and nothing encoded, the row says so, the
    rule is on the not-judged list in the reader's words, and the run is not marked incomplete."""
    calls, encoded = [], []

    def embed(items):
        encoded.append(1)
        return None
    with patched(passage_pairs, "load_config", lambda: dict(REAL_LOAD(), max_passages=1)):
        _phase_embed["value"] = embed
        try:
            rows, unjudged, _, reader, incomplete = _phase_run(_contradict_call(calls))
        finally:
            _phase_embed["value"] = None
    return {"calls": len(calls), "encoded": len(encoded), "rows": [(r["passages"], r["not_asked"], r["ranked_by"]) for r in rows],
            "not_judged": [e["reason"] for e in unjudged], "reader": "no pair was asked" in reader, "incomplete": incomplete}


def expected_max_passages():
    said = "no pair asked: 6 passages, above the declared 1"
    return {"calls": 0, "encoded": 0, "rows": [(6, said, None)], "not_judged": [said], "reader": True, "incomplete": False}


def observe_numpy_ranking():
    """The same ranking with numpy and without it, ties and identical passages among them, and
    the exact sum run on the near top only when numpy is there."""
    vectors = [[((i * 7 + k * 3) % 11) / 11 - .4 for k in range(8)] for i in range(40)]
    vectors[5] = list(vectors[4])
    vectors[9] = list(vectors[8])
    items = [{"text": "The harbour passage number %d stands here." % i} for i in range(40)]
    items[12] = dict(items[11])
    counted = []
    real = passage_pairs._dot

    def dot(a, b):
        counted.append(1)
        return real(a, b)
    with patched(passage_pairs, "_dot", dot):
        fast = passage_pairs.propose(items, 10, vectors)
    summed = len(counted)
    with patched(passage_pairs, "_numpy", lambda: None):
        slow = passage_pairs.propose(items, 10, vectors)
    return {"same": fast == slow, "length": len(fast), "fewer": summed < 780}


def expected_numpy_ranking():
    return {"same": True, "length": 10, "fewer": True}


def observe_not_twice():
    """A compare rule makes no unit plan: the planner gets its pairs and plans nothing for it, and
    the review asks it only of passages."""
    import paired_review
    unit = {"unit_id": "u01-a", "text": "Kind: quay" + chr(10) + QUAY_A}
    plans = paired_review.plan_calls({"u01-a": unit}, [("u01-a", "CONV-009")], {"CONV-009": COMPARE_RULE}, {})
    open_rule = {k: v for k, v in COMPARE_RULE.items() if k != "compare"}
    other = paired_review.plan_calls({"u01-a": unit}, [("u01-a", "CONV-009")], {"CONV-009": open_rule}, {})
    return {"compare": len(plans), "ordinary": len(other)}


def expected_not_twice():
    return {"compare": 0, "ordinary": 1}


class _Sticky(dict):
    """A rule whose declaration the planner would not see."""
    def get(self, key, default=None):
        return "" if key == "compare" else dict.get(self, key, default)


def _parsed(text):
    import convention_parser
    try:
        return [r.compare for r in convention_parser._parse_text_lines(text, "c.md", [0])]
    except convention_parser.ConventionDeclarationError:
        return "refused"


def _parsed_json(item):
    import convention_parser
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "c.json"
        path.write_text(json.dumps({"conventions": [dict(item, id="CONV-1", rule="No passage may state what another rules out.")]}), encoding="utf-8")
        try:
            return [r.compare for r in convention_parser._parse_json(path, [0])]
        except convention_parser.ConventionDeclarationError:
            return "refused"


RULE_LINE = chr(10) + "No passage may state what another passage rules out." + chr(10)


def observe_declaration():
    """A heading and a JSON convention read `compare` alike, and refuse alike."""
    return {"heading": _parsed("## CONV-H09 Contradiction [compare: passages]" + RULE_LINE),
            "heading other": _parsed("## CONV-H09 Contradiction [compare: units]" + RULE_LINE),
            "heading scope": _parsed("## CONV-H09 Contradiction [compare: passages] [scope: class]" + RULE_LINE),
            "heading requires": _parsed("## CONV-H09 Contradiction [compare: passages] [requires: class]" + RULE_LINE),
            "heading unless": _parsed("## CONV-H09 Contradiction [compare: passages] [unless: class]" + RULE_LINE),
            "heading none": _parsed("## CONV-H09 Contradiction [scope: class]" + RULE_LINE),
            "json": _parsed_json({"compare": "passages"}), "json other": _parsed_json({"compare": "units"}),
            "json number": _parsed_json({"compare": 1}), "json blank": _parsed_json({"compare": ""}),
            "json scope": _parsed_json({"compare": "passages", "scope": ["class"]}),
            "json requires": _parsed_json({"compare": "passages", "requires": ["class"]}),
            "json unless": _parsed_json({"compare": "passages", "unless": ["class"]}),
            "json none": _parsed_json({})}


def expected_declaration():
    return {"heading": ["passages"], "heading other": "refused", "heading scope": "refused", "heading requires": "refused",
            "heading unless": "refused", "heading none": [""], "json": ["passages"], "json other": "refused",
            "json number": "refused", "json blank": "refused", "json scope": "refused", "json requires": "refused",
            "json unless": "refused", "json none": [""]}


def observe_external():
    """An external rule declaring `compare` on a subject a convention shares is a difference."""
    import external_rules
    conv = {"id": "CONV-1", "scope": [{"label": "class"}], "severity": "required"}
    ext = {"id": "EXT-1", "scope": [{"label": "class"}], "severity": "required", "compare": "passages"}
    found = external_rules.detect_external_conflicts([conv], [ext])
    return [c["differences"] for c in found] + [external_rules.detect_external_conflicts([conv], [dict(ext, compare="")])]


def expected_external():
    return [[{"field": "compare", "convention": "none", "external": "passages"}], []]


OPERATOR_RULE = {"id": "CONV-R1", "category": "confidentiality", "rule": "Personal names must not leave.", "action": "redact"}
TITLED = "Dr. Lund says the harbour authority owns the northern quay outright."
BARE = "Lund signed the lease of the northern quay from a private owner."
OTHER = "Rainfall across the valley was unusually heavy last winter season."


def observe_real_mask():
    """The real masker and the real detector, on a sensitive network run: a title in one sentence,
    the bare name in another, and the pair prompt of the bare sentence holds no name. The question
    keeps its words. The rule's reading is injected, since it would load the embedding model."""
    import sensitivity_layer
    from sensitivity_layer import redaction_detect
    from unittest.mock import patch
    config = passage_pairs.load_config()
    document = chr(10).join((TITLED, "", BARE, "", OTHER))
    prompt = passage_pairs.render(config, BARE, OTHER)
    with tempfile.TemporaryDirectory() as folder, \
            patch.object(redaction_detect, "authorized_shapes", lambda rules, cues: {"name": ("CONV-R1", "confidentiality")}), \
            patch.object(sensitivity_layer, "should_mask_outbound", lambda **kwargs: True):
        masker = sensitivity_layer.make_outbound_prompt_masker(
            sensitive=True, operator_rules=[OPERATOR_RULE], project_root=ROOT, registry={}, run_id="r",
            ledger_path=Path(folder) / "ledger.jsonl")
        wrapper = type("W", (), {"outbound_masker": staticmethod(masker), "backend": "claude_api", "name": "PRACTICE_AUDITOR"})()
        sent, _ = passage_pairs.outbound(wrapper, prompt, context=document)
        alone = sensitivity_layer.mask_text(BARE + " " + TITLED, operator_rules=[OPERATOR_RULE], project_root=ROOT)[0]
    return {"name": "Lund" in sent, "placeholder": "[REDACTED:NAME_TITLE]" in sent,
            "question kept": "Can both passages be true of the same thing" in sent and OTHER in sent,
            "no context unchanged": alone}


def expected_real_mask():
    return {"name": False, "placeholder": True, "question kept": True,
            "no context unchanged": BARE + " Dr. [REDACTED:NAME_TITLE] harbour authority owns the northern quay outright."}


def _mask_without(**dropped):
    import sensitivity_layer
    real = sensitivity_layer.mask_text
    return patched(sensitivity_layer, "mask_text", lambda text, **kwargs: real(text, **{k: v for k, v in kwargs.items() if k not in dropped}))


def observe_wide():
    """On a wide run a declared rule asks nothing, and the pairing map and the reader's words
    say so, in both languages; a rule beside it is not listed."""
    import asyncio
    import honest_output_checks as hoc
    import pipeline as driver
    import reference_builder
    import reviewed_document
    import run_options as options
    from harness.run_agent import build_orchestrator
    from unittest.mock import patch
    ordinary = next(r for r in hoc.RULES)
    rules = [ordinary, COMPARE_RULE]
    assignment = {"by_rule": {r["id"]: {"consumer_agents": ["PRACTICE_AUDITOR"], "status": "assigned"} for r in rules},
                  "by_agent": {"PRACTICE_AUDITOR": [r["id"] for r in rules]}}
    doc = {"id": "batch_sheet", "name": "batch_sheet.md", "text": chr(10).join((hoc.DOC_TEXT, "## Entry Quay", "", QUAY_A, "", QUAY_B, ""))}

    async def reply(wrapper, payload, *args, **kwargs):
        return {"ok": True, "agent": wrapper.name, "backend": "local_auditor", "model": "fixture", "raw_text": "",
                "parsed": {"agent": wrapper.name, "doc_id": doc["id"], "items": []}, "item_count": 0}
    with tempfile.TemporaryDirectory() as td:
        orch = build_orchestrator(root=ROOT, out_root=Path(td))
        options.configure(orch.run_context, "auto", "en", "enabled")
        index = reference_builder.ReferenceIndex.open(ROOT, index_path=Path(td) / "refs.json")
        index.add(input_type="operational", document_id=doc["id"], document_name=doc["name"],
                  location={"page": 1, "paragraph": 1}, text_excerpt=hoc.DOC_TEXT)
        index.save()
        with patch.object(driver, "_run_one", reply), patch.object(passage_pairs, "embed", lambda items: None):
            asyncio.run(driver.phase_5_5_convention_review(
                orch, {}, [doc], "declared proof", {"conventions": rules}, index, embed_store=None,
                max_concurrent_docs=1, review_mode="wide", convention_assignment=assignment))
        pairing = json.loads(next(Path(orch.run_context.run_dir).rglob("pairing_map.json")).read_text(encoding="utf-8"))["batch_sheet"]
    entries = reviewed_document.not_checked_entries(pairing)
    words = [reviewed_document._why_not_checked(e) for e in entries]
    return {"rules": [e["rule_id"] for e in entries], "words": words,
            "passage_pairs": pairing.get("passage_pairs"), "second_language": _turkish(reviewed_document.WHY_COMPARE_IN_WIDE)}


def expected_wide():
    return {"rules": ["CONV-009"], "words": ["it compares passages, which only a paired review does, so no pair was asked"],
            "passage_pairs": None, "second_language": True}


def _turkish(english):
    """True when the catalog has a second-language row for `english`."""
    catalog = (ROOT / "scripts" / "ui" / "localization_catalog.js").read_text(encoding="utf-8")
    return ('"%s": "' % english) in catalog


def observe_spaces_id():
    """A compared unit id of spaces is refused, read with a second text or without one."""
    return {"alone": _cross_refusal(compared_unit_id="   ", unit=QUAY_A + " " + QUAY_B),
            "with a text": _cross_refusal(compared_unit_id="   ", second=QUAY_B)}


def expected_spaces_id():
    said = passage_pairs.paired_review.CONTRADICTION_SECOND_UNIT_NOT_CHECKED
    return {"alone": said, "with a text": said}


def reviewed_document_module():
    import reviewed_document
    return reviewed_document


def rescreen_module():
    import judged_rescreen
    return judged_rescreen


def observe_reason_table():
    """Every CONTRADICTION_ reason, read off the module, has the reader's words, a second-language row
    and a re-screen kind: a new reason with none fails here."""
    review = passage_pairs.paired_review
    reasons = [getattr(review, name) for name in dir(review) if name.startswith("CONTRADICTION_")]
    table = reviewed_document_module().REFUSAL_REASONS
    return {"reasons": len(reasons), "no words": [r for r in reasons if r not in table],
            "no second-language row": [r for r in reasons if r in table and not _turkish(table[r])],
            "no kind": [r for r in reasons if r not in rescreen_module().KINDS]}


def expected_reason_table():
    return {"reasons": 7, "no words": [], "no second-language row": [], "no kind": []}


def observe_repeat_sentence():
    """One sentence repeated in two other units, each contradicting the first unit, is two
    records and stays two through the post's dedupe."""
    units = [{"unit_id": "u01-a", "text": QUAY_A}, {"unit_id": "u02-b", "text": QUAY_B}, {"unit_id": "u03-c", "text": QUAY_B}]
    kept, _ = _review(units, _contradict)
    return sorted(k["compared_unit_id"] for k in passage_pairs.paired_review.dedupe(kept))


def expected_repeat_sentence():
    return ["u02-b", "u03-c"]


def observe_counted():
    """Pair calls count in the map's calls and judging calls, apart from note calls, with their
    outcome and a failed one as failed; on a document with no plan the rule's agent has no
    "nothing to do" row."""
    import agent_wrapper
    import honest_output_checks as hoc
    from unittest.mock import patch
    text = chr(10).join((hoc.DOC_TEXT, "## Entry Quay", "", QUAY_A, "", QUAY_B, ""))
    calls = []

    def dispatch(self, stable, dynamic="", **kwargs):
        calls.append(stable)
        ok = len(calls) != 2
        return agent_wrapper.CallResult(self.backend, "fixture-auditor", _contradict(stable) if ok else "", ok=ok)
    with tempfile.TemporaryDirectory() as td, patch.object(agent_wrapper.AgentWrapper, "dispatch", dispatch), \
            patch.object(passage_pairs, "embed", lambda items: None):
        run = hoc.mocked_run(Path(td), style_guardian=False, text=text, rules=[COMPARE_RULE])
        folder = Path(run["run_dir"])
        document = json.loads(next(folder.rglob("pairing_map.json")).read_text(encoding="utf-8"))["batch_sheet"]
        rows = json.loads((folder / "audit" / "agent_activation.json").read_text(encoding="utf-8"))["decisions"]
    judging = [c for c in document["judging_calls"] if c["plan_kind"] == "passage_pair"]
    counts = passage_pairs.paired_review.judging_call_counts(document["judging_calls"])
    return {"calls_made": document["calls_made"] == len(calls), "judging": len(judging) == len(calls),
            "outcomes": sorted({c["outcome"] for c in judging}), "note_calls": counts["note_calls"],
            "pair_calls": counts["pair_calls"] == len(calls),
            "idle": [r["agent"] for r in rows if r["reason"] in ("planner_no_model_work", "existing_pairing_refusal")
                     and r["agent"] == "PRACTICE_AUDITOR"]}


def expected_counted():
    return {"calls_made": True, "judging": True, "outcomes": ["judged_passage_pair", "reply_failed"], "note_calls": 0,
            "pair_calls": True, "idle": []}


def observe_rescreen():
    """A saved cross-unit record is re-screened with both its units read; the same record with its
    second quote changed is refused."""
    import pairing_map
    text = chr(10).join(("# Note", "", "## Part one", "", QUAY_A, "", "## Part two", "", QUAY_B, ""))
    units = [u["unit_id"] for u in pairing_map.split_units(text, document_id="d")]
    first, second = units[-2], units[-1]
    item = {"item_id": "pair-CONV-009-0-1", "revision": 1, "rule_id": "CONV-009", "unit_id": first, "compared_unit_id": second,
            "relation": "contradiction", "record_verdict": "irregular", "quote": QUAY_A, "quote_b": QUAY_B,
            "judged_path": "passage_pair", "text_screened": True}
    out = {}
    for name, record in (("kept", item), ("changed", dict(item, quote_b="Another sentence that stands nowhere at all."))):
        with tempfile.TemporaryDirectory() as folder:
            run, workload = Path(folder) / "run", Path(folder) / "workload"
            (run / "logs").mkdir(parents=True)
            (run / "audit").mkdir()
            (workload / "context").mkdir(parents=True)
            (workload / "context" / "d.md").write_text(text, encoding="utf-8")
            (workload / "_review_targets.json").write_text(json.dumps({"targets": ["d.md"]}), encoding="utf-8")
            (run / "audit" / "pairing_map.json").write_text(json.dumps({"d": {"units": []}}), encoding="utf-8")
            (run / "logs" / "agent_bus.jsonl").write_text(json.dumps({"body": {
                "event": "AGENT_OUTPUT", "stamped_by": "python", "payload": {"items": [record]}}}) + chr(10), encoding="utf-8")
            result = rescreen_module().rescreen(run, workload)
        out[name] = [result["kept_by_path"], result["refused_now"], [r["kind"] for r in result["refused"]]]
    return out


def expected_rescreen():
    return {"kept": [{"passage_pair": 1}, 0, []], "changed": [{"passage_pair": 1}, 1, ["f_contradiction_second_quote"]]}


def observe_thread():
    """The pair calls leave the event loop's thread, and the trail still reaches the run."""
    import threading
    where, calls = [], []
    inner = _contradict_call(calls)

    def dispatch(self, stable, dynamic="", **kwargs):
        where.append(threading.current_thread() is threading.main_thread())
        return inner(self, stable, dynamic, **kwargs)
    rows, _, _, _, _ = _phase_run(dispatch)
    return {"on the loop's thread": any(where), "made": [r["made"] for r in rows], "calls": len(calls)}


def expected_thread():
    return {"on the loop's thread": False, "made": [4], "calls": 4}


def observe_cap():
    """A compare rule takes no place under `--pairs-per-unit`: the ordinary rule beside it stays."""
    pairing = {"units": [{"unit_id": "u1", "paired": [{"rule_id": "CONV-009"}, {"rule_id": "CONV-001"}]}]}
    return list(passage_pairs.paired_review.pairs_from_map(pairing, cap_per_unit=1, not_unit_rules={"CONV-009"}))


def expected_cap():
    return [[("u1", "CONV-001")], []]


async def _inline(function, *args, **kwargs):
    return function(*args, **kwargs)


def _lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []


def observe_audit():
    """Every pair call leaves the trail run_task leaves: its prompt's identity, its evidence with
    the document, its cost dimensions during the call and never after, its activation row, and a
    kept pair's calls end not promoted while the others stay free text."""
    import agent_wrapper
    import call_evidence
    import honest_output_checks as hoc
    import reply_records
    from unittest.mock import patch
    text = chr(10).join((hoc.DOC_TEXT, "## Entry Quay", "", QUAY_A, "", QUAY_B, ""))
    costs = []

    def dispatch(self, stable, dynamic="", **kwargs):
        costs.append((self._cost_phase, self._cost_doc_id, bool(self._cost_call_id)))
        both = QUAY_A in stable and QUAY_B in stable
        return agent_wrapper.CallResult(self.backend, "fixture-auditor", _contradict(stable) if both else
                                        '{"outcome": "compatible", "reason": "fixture"}')
    with tempfile.TemporaryDirectory() as td, patch.object(agent_wrapper.AgentWrapper, "dispatch", dispatch), \
            patch.object(passage_pairs, "embed", lambda items: None):
        run = hoc.mocked_run(Path(td), style_guardian=False, text=text, rules=hoc.RULES + [COMPARE_RULE])
        folder = Path(run["run_dir"])
        evidence = _lines(call_evidence.evidence_path(folder))
        evidence = [e for e in evidence if e.get("task") == "passage_pair"]
        ids = {e["call_id"] for e in evidence}
        prompts = {row["call_id"] for row in _lines(folder / "logs" / "prompt_structure.jsonl")}
        rows = json.loads((folder / "audit" / "agent_activation.json").read_text(encoding="utf-8"))["decisions"]
        rows = [r for r in rows if r["reason"] == "passage_pair"]
        outcomes = reply_records.outcomes(folder / "audit" / "model_replies")
    return {"costs": sorted(set(costs)), "evidence": sorted({(e["doc_id"], e["phase"], e["payload_rule_id"], e["payload_document_id"]) for e in evidence}),
            "prompts": ids <= prompts and len(ids), "rows": sorted({(r["doc_id"], r["downstream_consumer"], r["trigger_source"], r["evidence"]["doc_id"]) for r in rows}),
            "joined": {r["call_id"] for r in rows} == ids, "outcomes": sorted(outcomes[i] for i in ids)}


def expected_audit():
    return {"costs": [("5.5", "batch_sheet", True)], "evidence": [("batch_sheet", "5.5", "CONV-009", "batch_sheet")],
            "prompts": 4, "rows": [("batch_sheet", "model_finding_not_promoted", "convention_declaration", "batch_sheet")],
            "joined": True, "outcomes": ["free_text", "free_text", "not_promoted", "not_promoted"]}


def observe_draft_defaults():
    """The draft memo's words stay direct_call's defaults."""
    import agent_activation
    captured = {}

    class Audit:
        def decision(self, agent, **kwargs):
            captured.update(kwargs)
            return {}

        def update(self, row, **kwargs):
            pass
    from unittest.mock import patch
    wrapper = type("W", (), {"name": "X", "run_context": None})()
    result = type("R", (), {"ok": True})()
    with patch.object(agent_activation, "get", lambda context: Audit()):
        agent_activation.direct_call(wrapper, "c", lambda: result, reason="r", source_phase="0")
    return [captured["consumer"], captured["trigger_source"], captured["doc_id"]]


def sc_module():
    return doc_judge._score_corpus()


def observe_marks():
    """The scorer places a sentence on its best passage, never on a near copy as well."""
    with tempfile.TemporaryDirectory() as folder:
        key = Path(folder) / "answer_key.json"
        key.write_text(json.dumps({"benchmark": "contradoc", "document": "d.md", "items": [
            {"item_id": "i", "rule_id": "CONV-X", "gold": "contradictory",
             "evidence_sentence": "The quay was sold in the year 1901."}]}), encoding="utf-8")
        return sc_module().marked_passages(key, "i", ["The quay was sold in the year 1907.", "The quay was sold in the year 1901.",
                                                      "Rain fell all week on the town."])


def expected_marks():
    return {"marked": [1], "partner": [], "references": 0}


def observe_source_marks():
    """The partner is read from the benchmark's own source, through the adapter, as positions."""
    sc = sc_module()
    adapter = sc._adapter_for("contradoc")
    item = adapter.ids.opaque_item_id(adapter.BENCHMARK, "7")
    with tempfile.TemporaryDirectory() as folder:
        key = Path(folder) / "answer_key.json"
        key.write_text(json.dumps({"benchmark": "contradoc", "document": "d.md", "items": [
            {"item_id": item, "rule_id": "CONV-X", "gold": "contradictory", "evidence_sentence": "x"}]}), encoding="utf-8")
        source = Path(folder) / "source.json"
        source.write_text(json.dumps({"pos": {"7": {"unique id": "7", "text": "t", "evidence": "The quay was sold in 1901.",
                                                    "ref sentences": ["Nobody ever sold the quay at all."]}}}), encoding="utf-8")
        return sc.marked_passages(key, item, ["Rain fell all week on the town.", "Nobody ever sold the quay at all.",
                                              "The quay was sold in 1901."], source)


def expected_source_marks():
    return {"marked": [2], "partner": [1], "references": 1}


def observe_split():
    """The product's passages are the measured ones: a document read by unit or whole."""
    import pairing_map
    text = chr(10).join(("# Note", "", "## Part one", "", "The quay was sold to the city in 1901.", "",
                         "## Part two", "", "Nobody ever sold the quay to anyone at all.", ""))
    whole = [p["text"] for p in passage_pairs.passages(text)]
    units = [p["text"] for p in passage_pairs.document_passages(pairing_map.split_units(text))]
    return whole == units


def observe_no_fallback():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        (folder / "context").mkdir()
        (folder / "context" / "d.md").write_text("The quay was sold to the city in 1901. The quay was never sold to the city at all.", encoding="utf-8")
        (folder / "context" / "_review_targets.json").write_text(json.dumps({"targets": ["d.md"]}), encoding="utf-8")
        items = folder / "items.json"
        items.write_text(json.dumps([{"document_id": "d", "item_id": "i", "rule_id": "CONV-X", "benchmark": "contradoc"}]), encoding="utf-8")
        try:
            pair_judge.build([folder], [items], folder / "p.json", embed=lambda passages: None)
        except ValueError:
            return "refused"
    return "built"


def _fixture_read(folder, complete=True, tamper=None):
    """A whole read over an invented pass: two documents, one gold, one clear."""
    folder = Path(folder)
    config = _config()
    gold_text = "The quay was sold to the city in the year 1901.\n\nThe quay has never been sold to anyone at all.\n"
    clear_text = "The town has one bakery near the old market.\n\nThe bakery sells bread to the town every day.\n"
    prompts, documents, rows, keys = [], {}, [], []
    for doc, text, gold in (("dgold", gold_text, True), ("dclear", clear_text, False)):
        documents[doc] = {"benchmark": "contradoc", "target": doc + ".md", "text": text, "sha256": doc_judge._sha(text),
                          "conventions": [], "top_score": .5}
        items = passage_pairs.passages(text)
        for order, a, b in (("ab", items[0], items[1]), ("ba", items[1], items[0])):
            user = doc_judge.render_pair(config, a["text"], b["text"])
            pid = "p%d" % (len(prompts) + 1)
            prompts.append({"prompt_id": pid, "form": doc_judge.PAIR_FORM, "pair_id": "0-1-" + order, "pair": [0, 1],
                            "order": order, "group": "pair_direct", "backend": "local_auditor", "agent": "PRACTICE_AUDITOR",
                            "checkpoint": "base", "benchmark": "contradoc", "document_id": doc, "item_id": "i" + doc,
                            "rule_id": "CONV-X", "span_a": [a["start"], a["end"]], "span_b": [b["start"], b["end"]],
                            "system": None, "max_new_tokens": 96, "user": user, "user_sha256": doc_judge._sha(user)})
            rows.append({"prompt_id": pid, "call_id": "c" + pid, "length_reached_allowance": False})
        key = folder / (doc + "_key.json")
        key.write_text(json.dumps({"benchmark": "contradoc", "document": doc + ".md", "items": [
            {"item_id": "i" + doc, "rule_id": "CONV-X", "gold": "contradictory" if gold else "not contradictory",
             "evidence_sentence": "The quay has never been sold to anyone at all." if gold else ""}]}), encoding="utf-8")
        keys.append(key)
    value = {"schema": doc_judge.SCHEMA, "kind": doc_judge.KIND, "config": config,
             "config_sha256": doc_judge._sha(doc_judge._canonical(config)), "documents": documents, "prompts": prompts,
             "prompt_count": len(prompts)}
    prompts_path = folder / "prompts.json"
    prompts_path.write_text(json.dumps(value), encoding="utf-8")
    run = folder / "run"
    replies = run / "audit" / "model_replies"
    replies.mkdir(parents=True)
    records = {}
    for r, p in zip(rows, prompts):
        outcome = "contradict" if p["document_id"] == "dgold" else "compatible"
        records[r["call_id"]] = {"call_id": r["call_id"], "backend_ok": True, "reply": {"text": json.dumps({"outcome": outcome})}}
    (run / doc_judge.MEASUREMENT_FILE).write_text(json.dumps({
        "schema": doc_judge.MEASUREMENT_SCHEMA, "prompts_sha256": pair_judge._digest(prompts_path), "complete": complete,
        "rows": rows}), encoding="utf-8")
    j1 = folder / "j1.json"
    j1.write_text(json.dumps({"views": {"judge_reason": {"b1_all": {"contradoc": {
        "flag_tp": 0, "flag_fp": 0, "abstain": 0, "items": 2}}}}}), encoding="utf-8")
    source = folder / "source.json"
    source.write_text("{}", encoding="utf-8")
    sc = sc_module()
    bar = dict(thresholds=pair_judge.BAR, prompts_sha256=pair_judge._digest(prompts_path),
               b1_sha256=pair_judge._digest(j1), source_sha256=pair_judge._digest(source),
               keys_sha256=doc_judge.keys_digest(sc, keys))
    if tamper == "thresholds":
        bar["thresholds"] = dict(pair_judge.BAR, chance_at_most=1.0)
    elif tamper:
        bar[tamper] = "another"
    bar_path = folder / "bar.json"
    bar_path.write_text(json.dumps(bar), encoding="utf-8")
    return (prompts_path, run, keys, bar_path, j1, source, folder / "out"), list(records.values())


def _attempt(complete=True, tamper=None):
    import reply_records
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as folder:
        args, records = _fixture_read(folder, complete, tamper)
        marks = lambda key, item, texts, source=None: ({"marked": [1], "partner": [0], "references": 1}
                                                       if item == "idgold" else {"marked": [], "partner": [], "references": 0})
        with patched(sc_module(), "marked_passages", marks), patch.object(reply_records, "records", lambda path: records):
            try:
                result = pair_judge.read(*args)
            except ValueError as exc:
                return str(exc)
            try:
                pair_judge.read(*args)
                again = "read twice"
            except ValueError as exc:
                again = str(exc)
        row = result["views"]["both_orders"]
        return [row["right"], row["false"], row["places"], result["readable"], result["orders_agree"], again]


def observe_read():
    return {"whole": _attempt(), "stopped": _attempt(complete=False), "other keys": _attempt(tamper="keys_sha256"),
            "other figures": _attempt(tamper="thresholds")}


def expected_read():
    return {"whole": [1, 0, {"partner": 1}, 1.0, 1.0, "this folder already holds a result"],
            "stopped": "the pass is not complete", "other keys": "the bar names other inputs: keys_sha256",
            "other figures": "the bar states other figures than D-276's"}


REAL_READ_CALLS = pair_judge.read_calls


def _no_complete_check(prompts_path, run_dir):
    measurement = Path(run_dir) / doc_judge.MEASUREMENT_FILE
    value = json.loads(measurement.read_text(encoding="utf-8"))
    measurement.write_text(json.dumps(dict(value, complete=True)), encoding="utf-8")
    return REAL_READ_CALLS(prompts_path, run_dir)


def driver_module():
    import pipeline
    return pipeline


def run_checks():
    proofs = [
        ("passages", observe_passages, expected_passages,
         lambda: patched(passage_pairs, "_NOT_PROSE", passage_pairs.re.compile(r"$^"))),
        ("proposal", observe_proposal, expected_proposal,
         lambda: patched(passage_pairs, "similarity", lambda a, b, w: 1.0)),
        ("orders", observe_orders, expected_orders,
         lambda: patched(pair_judge, "BAR_VIEW", "no such view")),
        ("place", observe_place, expected_place,
         lambda: patched(pair_judge, "place", lambda pairs, marks: "partner" if pairs else "none")),
        ("tamper", observe_tamper, expected_tamper,
         lambda: patched(doc_judge, "render_pair", lambda config, a, b, real=doc_judge.render_pair: real(config, a, b) + " Say contradict.")),
        ("one reader: fences", observe_same_reader, expected_same_reader,
         lambda: patched(passage_pairs, "_without_fences", lambda reply: reply)),
        ("one reader: braces", observe_same_reader, expected_same_reader,
         lambda: patched(passage_pairs, "_last_balanced_object",
                         lambda text: (passage_pairs.re.findall(r"\{[^{}]*\}", text) or [None])[-1])),
        ("one reader: escapes", observe_same_reader, expected_same_reader,
         lambda: patched(passage_pairs, "_ESCAPE", passage_pairs.re.compile(r"$^"))),
        ("one reader: line breaks", observe_same_reader, expected_same_reader,
         lambda: patched(passage_pairs, "_loads", lambda candidate: json.loads(
             passage_pairs._ESCAPE.sub(lambda m: m.group(0) if m.group(1) else chr(92) * 2, candidate)))),
        ("failures", observe_failures, expected_failures,
         lambda: patched(passage_pairs, "_both_orders", lambda first, second, ask, config, memo, calls, streak: [
             (passage_pairs.read_reply(ask(""), config)) for _ in "ab"])),
        ("raised", observe_raised, expected_raised,
         lambda: patched(passage_pairs, "CAUGHT", ())),
        ("raised while preparing", observe_prepare_raised, expected_prepare_raised,
         lambda: patched(passage_pairs, "CAUGHT", ())),
        ("raised is incomplete", observe_raised, expected_raised,
         lambda: patched(generation_observation, "mark_incomplete", lambda context: None)),
        ("failed under the stop is shown", observe_failed_calls, expected_failed_calls,
         lambda: patched(passage_pairs, "unjudged", lambda rule_id, calls, kept: None)),
        ("a partial stop says what was kept", observe_partial_stop, expected_partial_stop,
         lambda: _with_source(passage_pairs, "unjudged", 'else "pairs_partly_stopped" if kept else "failed"', 'else "failed"')),
        ("own words per stop", observe_rows_by_kind, expected_rows_by_kind,
         lambda: _with_source(passage_pairs, "unjudged", '"pairs_not_prepared" if not calls["made"] else ', "")),
        ("a pair needs both replies", observe_failed_order, expected_failed_order,
         lambda: _with_source(passage_pairs, "review", "whole = all(c != FAILED_ORDER for c, _ in answers)", "whole = True")),
        ("failed is incomplete", observe_failed_calls, expected_failed_calls,
         lambda: patched(generation_observation, "mark_incomplete", lambda context: None)),
        ("one encoding", observe_two_rules, expected_two_rules,
         lambda: patched(passage_pairs, "review", _prepare_per_rule)),
        ("no second call", observe_two_rules, expected_two_rules,
         lambda: patched(passage_pairs, "review", _no_memory)),
        ("another model is asked", observe_other_model, expected_other_model,
         lambda: patched(passage_pairs, "model_of", lambda wrapper: "one model")),
        ("max passages", observe_max_passages, expected_max_passages,
         lambda: patched(passage_pairs, "too_many", lambda items, config: False)),
        ("numpy ranking", observe_numpy_ranking, expected_numpy_ranking,
         lambda: patched(passage_pairs, "_TIE_MARGIN", -1.0)),
        ("not asked twice", observe_not_twice, expected_not_twice,
         lambda: patched(passage_pairs.paired_review, "plan_calls",
                         lambda units, pairs, rules, *a, real=passage_pairs.paired_review.plan_calls, **k: real(
                             units, pairs, {i: _Sticky(r) for i, r in rules.items()}, *a, **k))),
        ("the declaration: other values", observe_declaration, expected_declaration,
         lambda: patched(convention_parser, "_compare_value", lambda raw, where: "" if raw is None else str(raw))),
        ("the declaration: beside others", observe_declaration, expected_declaration,
         lambda: patched(convention_parser, "_refuse_compare_beside", lambda *a: None)),
        ("external rules", observe_external, expected_external,
         lambda: patched(external_rules, "_compare_of", lambda rule: "")),
        ("audit: prompt identity", observe_audit, expected_audit,
         lambda: patched(run_options, "record_prompt", lambda *a: None)),
        ("audit: evidence", observe_audit, expected_audit,
         lambda: patched(call_evidence, "record", lambda *a: None)),
        ("audit: activation row", observe_audit, expected_audit,
         lambda: patched(agent_activation, "direct_call", lambda wrapper, call_id, call, **k: call())),
        ("audit: not promoted", observe_audit, expected_audit,
         lambda: patched(passage_pairs, "review", lambda *a, **k: REAL_REVIEW(*a, **dict(k, on_kept=None)))),
        ("draft keeps its words", observe_draft_defaults, lambda: ["draft_memo_then_review", "task_mode", ""],
         lambda: patched(agent_activation.direct_call, "__kwdefaults__", dict(agent_activation.direct_call.__kwdefaults__, consumer="other"))),
        ("cross unit: names the second", observe_cross_unit, expected_cross_unit,
         lambda: patched(passage_pairs, "record", lambda *a: {k: v for k, v in REAL_RECORD(*a).items() if k != "compared_unit_id"})),
        ("cross unit: the mark names them", observe_cross_unit, expected_cross_unit,
         lambda: _with_source(finding_record, "reader_line", 'item.get("compared_unit_id") and item.get(SCREENED_FIELD)', 'item.get("compared_unit_id")')),
        ("cross unit: a claim no check read", observe_cross_refusals, expected_cross_refusals,
         lambda: _refusal_with('if bool(named) != (second_unit_text is not None) or (named and other in ("", str(item.get("unit_id") or ""))):', "if False:")),
        ("spaces name no second unit", observe_spaces_id, expected_spaces_id,
         lambda: _refusal_with('bool(named) != (second_unit_text is not None) or (named and other in ("", str(item.get("unit_id") or "")))',
                               'bool(other) != (second_unit_text is not None) or (other and other == str(item.get("unit_id") or ""))')),
        ("every contradiction reason has its words", observe_reason_table, expected_reason_table,
         lambda: patched(reviewed_document_module(), "REFUSAL_REASONS",
                         {k: v for k, v in reviewed_document_module().REFUSAL_REASONS.items()
                          if k != passage_pairs.paired_review.CONTRADICTION_SECOND_UNIT_NOT_CHECKED})),
        ("every contradiction reason has its kind", observe_reason_table, expected_reason_table,
         lambda: patched(rescreen_module(), "KINDS",
                         {k: v for k, v in rescreen_module().KINDS.items()
                          if k != passage_pairs.paired_review.CONTRADICTION_SECOND_UNIT_NOT_CHECKED})),
        ("two other units, two records", observe_repeat_sentence, expected_repeat_sentence,
         lambda: _with_source(passage_pairs.paired_review, "dedupe", 'key += (item.get("compared_unit_id"),)', "pass")),
        ("cross unit: blank second unit", observe_cross_refusals, expected_cross_refusals,
         lambda: _refusal_with("(other and not _squash(second_unit_text))", "False")),
        ("cross unit: held to the second", observe_cross_refusals, expected_cross_refusals,
         lambda: _refusal_with("second_unit_text if other else unit_text", "unit_text")),
        ("cross unit: same words", observe_cross_refusals, expected_cross_refusals,
         lambda: _refusal_with("_one_wording(_squash(quotes[0]), _squash(quotes[1])) if other else", "False if other else")),
        ("cross unit: phase 5.5", observe_phase_cross, expected_phase_cross,
         lambda: patched(passage_pairs, "review", lambda *a, **k: ([], REAL_REVIEW(*a, **k)[1]))),
        ("refused", observe_refused, expected_refused,
         lambda: patched(passage_pairs.paired_review, "judged_item_refusal", lambda *a, **k: None)),
        ("python's mark", observe_runtime, expected_runtime,
         lambda: patched(passage_pairs.paired_review, "mark_screened", lambda item: item)),
        ("runtime", observe_runtime, expected_runtime,
         lambda: patched(passage_pairs, "read_reply", lambda text, config: ("FLAG", None) if "contradict" in str(text) else ("FLAG", None))),
        ("same prompt", observe_same_prompt, lambda: True,
         lambda: patched(passage_pairs, "render", lambda config, a, b: "another question")),
        ("phase 5.5", observe_phase, expected_phase,
         lambda: patched(passage_pairs, "declared", lambda rules: [])),
        ("masked", observe_masked, expected_masked,
         lambda: patched(passage_pairs, "outbound", lambda wrapper, text: (text, ""))),
        ("masked on the document: the context", observe_real_mask, expected_real_mask,
         lambda: _mask_without(context=True)),
        ("masked on the document: the name alone", observe_real_mask, expected_real_mask,
         lambda: patched(sensitivity_layer, "_name_parts", lambda span: [])),
        ("wide review says so", observe_wide, expected_wide,
         lambda: _with_source(driver_module(), "_wide_not_judged", 'if c.get("compare"):', "if False:")),
        ("pair calls are counted", observe_counted, expected_counted,
         lambda: _with_source(driver_module(), "_paired_convention_review",
                              'len(results) + sum(row["made"] for row in pairing["passage_pairs"] + pairing["cell_claims"])', "len(results)")),
        ("pair calls apart from notes", observe_counted, expected_counted,
         lambda: _with_source(passage_pairs.paired_review, "judging_call_counts",
                              "len(calls) - absence - uncomputable - pairs", "len(calls) - absence - uncomputable")),
        ("no idle row", observe_counted, expected_counted,
         lambda: _with_source(driver_module(), "_paired_convention_review", "if name in pair_agents:", "if False:")),
        ("a saved pair is re-screened", observe_rescreen, expected_rescreen,
         lambda: _with_source(rescreen_module(), "kept_items", 'else "passage_pair" if written == paired_review.JUDGED_PATH_PASSAGE_PAIR', "")),
        ("off the event loop", observe_thread, expected_thread,
         lambda: patched(driver_module().asyncio, "to_thread", _inline)),
        ("a compare rule takes no place", observe_cap, expected_cap,
         lambda: _with_source(passage_pairs.paired_review, "pairs_from_map", ' if p["rule_id"] not in not_unit_rules]', "]")),
        ("a touch is not placed", observe_placed_count, expected_placed_count,
         lambda: patched(pair_judge, "counts", lambda flags, gold, places: {"right": 2, "placed": 2, "flagged_with_two_marks": 2})),
        ("source marks", observe_source_marks, expected_source_marks,
         lambda: patched(sc_module(), "_overlap", lambda a, b: 1.0 if "Rain" in a else 0.0)),
        ("one split", observe_split, lambda: True,
         lambda: patched(passage_pairs, "document_passages", lambda units: [])),
        ("no fallback", observe_no_fallback, lambda: "refused",
         lambda: patched(pair_judge, "_words_allowed", True)),
        ("identity", observe_identity, expected_identity,
         lambda: patched(passage_pairs, "_words", lambda text: sorted(passage_pairs._tokens(text)))),
        ("read", observe_read, expected_read,
         lambda: patched(pair_judge, "read_calls", _no_complete_check)),
        ("marks", observe_marks, expected_marks,
         lambda: patched(sc_module(), "_overlap", lambda a, b: 1.0 if "1907" in a else 0.0)),
        ("verdict", observe_verdict, expected_verdict,
         lambda: patched(pair_judge, "verdict", lambda row, readable, b1, python, bar=None: {"result": "keep"})),
    ]
    results = []
    for name, observe, expected, neutralise in proofs:
        results.append(prove_effect(name=name, validate=lambda: pair_judge.CONFIG_PATH.is_file(), observe=observe,
                                    check=lambda: ("PASS" if observe() == expected() else "FAIL", name),
                                    neutralise=neutralise))
    return "PASS", "%d proofs, each neutralise, fail, restore, pass: passages keep their place, pairs share rare words, a flag needs both orders and the marked passage, a tampered pair prompt is refused, the verdict needs every condition; the product path is masked, holds each quote to its own unit (a second unit only from this step) and to the judged refusals, reads a reply as the replay does, survives a failed or raised call, costs one encoding and no second call, is declared one way and leaves run_task's audit trail" % len(results)


if __name__ == "__main__":
    print(run_checks())
