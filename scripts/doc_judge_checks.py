"""Gate check: G1 document-level judging (benchmark/baselines/doc_judge.py) end to end on
fixtures, with canned models. No model, no pipeline run, no provider, no network.

The end-to-end cases EXECUTE the live path on four invented workloads written into a temporary folder
(one per benchmark adapter it is scored with: a consistency rule, two hypothesis rules, three
category rules, three table claims):

1. build: one prompt per (model group, document, rule heading with an operator id), each the
   config's own template filled with the document and that rule's own text, one user turn and
   no filled example; the file re-renders and holds its SHA-256s (load_prompts);
2. the sealed pass: replay_prompts.py's own `run` command (the runner's replay pass,
   tools/ordinary_final_run.py b1_argv) hands the file to doc_judge.run, every prompt goes to
   its group's canned model as ONE user turn (no system turn) and leaves exactly one reply
   record with its text, and the runner's replay_observation counts them all; the analyser
   names the pass as G1;
3. the judge: a holds or not met is kept only with a quote found in the document after
   whitespace normalisation; a missing quote, a quote not in the document, an unparseable reply,
   an outcome the config does not declare, a quote that is not the document's content and a
   failed call are refused; cannot be settled (and
   a rule's UNCERTAIN) is kept;
4. the scores: labels written in bare_model's format are labelled by the adapters' own
   label_b1 through tools/score_corpus.py and the figures (precision, recall, F1, accuracy,
   correct refusals, labels by source) equal the ones computed by hand from the fixture; in the
   as_b3 view a refused answer is silence, counted apart and never a FLAG;
5. the key is opened only by tools/score_corpus.py;
6. sealing: the file passes the sealer's replay_declaration and the runner's b1_checkpoints
   with a replay pass `--paths sdpa`, and the runner expects one record per prompt;
7. the comparator (D-241): `build --b1` adds B1's own two turns per model group and item, sent
   with B1's allowance, read by bare_model's reader and scored as the view b1_comparator, a
   left-out item is in no figure, a run of other items or inputs gets no verdict, and the bar's
   conditions are computed on hand-made figures;
8. the parts that need no run: the real items file and its pin, the quote rule and quote_units on
   hand-written text, and the command line.

Each is proven by neutralise, fail, restore, pass (scripts/effect_proof.py).
"""
import builtins
import contextlib
import hashlib
import inspect
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "benchmark" / "baselines"
for _path in (str(ROOT / "scripts"), str(ROOT / "tools"), str(BASELINES), str(ROOT / "benchmark" / "adapters")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from effect_proof import prove_effect  # noqa: E402

KEY_NAME = "answer_key.json"


def _tool():
    import doc_judge
    return doc_judge


def _write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1) if isinstance(data, (dict, list)) else data, encoding="utf-8")
    return path


# ---- fixture ------------------------------------------------------------------------------

DOCS = {
    "contradoc": ("d0aaaaaaaaaa", "# D-d0aaaaaaaaaa\n\n## P-00001\n\nPassage: part\n\nThe bridge opened in spring.\nIt carried\n"
                  "   two lanes of traffic.\n\n## P-00002\n\nPassage: part\n\nThe bridge never opened.\n",
                  [("CONV-CDOC-01", "No passage may contain a statement that cannot be true together with another statement.")]),
    "contractnli": ("d1bbbbbbbbbb", "# D-d1bbbbbbbbbb\n\n## P-00001\n\nPassage: part\n\nThe reader keeps every note private.\n"
                    "Notes may be shared with staff.\n",
                    [("CONV-CNLI-NDA-1", "Hypothesis about the agreement: Notes are kept private. If the agreement does not settle the hypothesis, emit UNCERTAIN."),
                     ("CONV-CNLI-NDA-2", "Hypothesis about the agreement: Notes are destroyed yearly. If the agreement does not settle the hypothesis, emit UNCERTAIN.")]),
    "cuad": ("d2cccccccccc", "# D-d2cccccccccc\n\n## P-00001\n\nPassage: part\n\nThis plan begins on the first day of May.\n",
             [("CONV-CUAD-01", "The document must contain, in at least one passage, a clause of this category: Start Date."),
              ("CONV-CUAD-02", "The document must contain, in at least one passage, a clause of this category: End Date."),
              ("CONV-CUAD-03", "The document must contain, in at least one passage, a clause of this category: Notice Period.")]),
    "scitab": ("d3dddddddddd", "# D-d3dddddddddd\n\n## P-00001\n\nPassage: part\n\n| Model | Score |\n|---|---|\n| Alpha | 81.5 |\n"
               "| Beta | 79.2 |\n",
               [("CONV-ST01", "Claim about the table: Alpha scores below Beta."),
                ("CONV-ST02", "Claim about the table: Alpha scores above Beta."),
                ("CONV-ST03", "Claim about the table: Alpha was trained on more data.")]),
}
# Gold per (benchmark, rule): the adapters' own labels.
GOLD = {("contradoc", "CONV-CDOC-01"): "contradictory",
        ("contractnli", "CONV-CNLI-NDA-1"): "contradiction", ("contractnli", "CONV-CNLI-NDA-2"): "not mentioned",
        ("cuad", "CONV-CUAD-01"): "present", ("cuad", "CONV-CUAD-02"): "absent", ("cuad", "CONV-CUAD-03"): "absent",
        ("scitab", "CONV-ST01"): "refutes", ("scitab", "CONV-ST02"): "supports", ("scitab", "CONV-ST03"): "not enough info"}
CONFIG_OVERRIDE = {"models": [{"group": "phi", "backend": "local_auditor", "agent": "PRACTICE_AUDITOR", "checkpoint": "base"},
                              {"group": "qwen", "backend": "local_producer", "agent": "PROCESSOR", "checkpoint": "base"}]}


def _reply(outcome, quote="", reason="r"):
    return json.dumps({"outcome": outcome, "quote": quote, "reason": reason})


# Canned replies per (group, rule), and what the judge must make of each:
# (kept, refusal, class written, class kept).
REPLIES = {
    ("phi", "CONV-CDOC-01"): ("```json\n" + _reply("not met", "It carried two lanes of traffic.") + "\n```",
                              (True, None, "FLAG", "FLAG")),                       # whitespace-normalised quote
    ("phi", "CONV-CNLI-NDA-1"): (_reply("not met", "Notes may be shared with staff."), (True, None, "FLAG", "FLAG")),
    ("phi", "CONV-CNLI-NDA-2"): (_reply("UNCERTAIN"), (True, None, "UNDECIDED", "UNDECIDED")),
    ("phi", "CONV-CUAD-01"): (_reply("holds", "begins on the first day of May"), (True, None, "CLEAR", "CLEAR")),
    ("phi", "CONV-CUAD-02"): (_reply("not met", "The plan ends in June."), (False, "quote_not_in_document", "FLAG", "ABSTAIN")),
    ("phi", "CONV-CUAD-03"): (_reply("not met", "  "), (False, "quote_missing", "FLAG", "ABSTAIN")),
    ("phi", "CONV-ST01"): (_reply("not met", "| Alpha | 81.5 |"), (True, None, "FLAG", "FLAG")),       # a table row
    ("phi", "CONV-ST02"): (_reply("UNCERTAIN"), (True, None, "UNDECIDED", "UNDECIDED")),
    ("phi", "CONV-ST03"): (_reply("not met", "|---|---|"), (False, "quote_not_content", "FLAG", "ABSTAIN")),  # a separator
    ("qwen", "CONV-ST01"): (_reply("holds", "1"), (False, "quote_not_content", "CLEAR", "ABSTAIN")),   # cut from a figure
    ("qwen", "CONV-ST02"): (_reply("holds", "81.5"), (True, None, "CLEAR", "CLEAR")),                  # a whole cell
    ("qwen", "CONV-ST03"): (_reply("not met", "Passage: part"), (False, "quote_not_content", "FLAG", "ABSTAIN")),  # a marker
    ("qwen", "CONV-CDOC-01"): (_reply("holds", "The bridge opened in spring."), (True, None, "CLEAR", "CLEAR")),
    ("qwen", "CONV-CNLI-NDA-1"): ("I think it holds.", (False, "no_json_object", "ABSTAIN", "ABSTAIN")),
    ("qwen", "CONV-CNLI-NDA-2"): (_reply("maybe"), (False, "outcome_not_declared", "ABSTAIN", "ABSTAIN")),
    ("qwen", "CONV-CUAD-01"): (_reply("cannot be settled"), (True, None, "UNDECIDED", "UNDECIDED")),
    ("qwen", "CONV-CUAD-02"): (None, (False, "out_of_memory", "ABSTAIN", "ABSTAIN")),   # the call fails
    ("qwen", "CONV-CUAD-03"): (_reply("holds", "This plan begins on the first day of May."), (True, None, "CLEAR", "CLEAR")),
}


# B1's canned replies per (group, rule): the label each model gives on the comparator prompts.
# None is an unreadable reply, an abstention.
B1_REPLIES = {("phi", "CONV-CDOC-01"): "contradictory", ("qwen", "CONV-CDOC-01"): "not_contradictory",
              ("phi", "CONV-ST01"): "refutes", ("qwen", "CONV-ST01"): "refutes",
              ("phi", "CONV-ST02"): "refutes", ("qwen", "CONV-ST02"): "supports",
              ("phi", "CONV-ST03"): "not enough info", ("qwen", "CONV-ST03"): None}
LEFT_OUT = "iscit01"
# Evidence units in the key's own form: phi's CDOC-01 flag quotes this unit, its ST01 flag does not.
EVIDENCE = {"CONV-CDOC-01": ["u01-p-00001"], "CONV-ST01": ["u02-p-00002"]}


def workloads(root):
    """Four staged workloads (tools/stage_workload.py layout) and their adapter keys."""
    root = Path(root)
    folders, benches, keys = [], [], []
    for bench, (doc_id, text, rules) in DOCS.items():
        w = root / "workload" / bench
        _write(w / "_review_targets.json", {"targets": [doc_id + ".md"], "grounding": [], "prior": [], "source": "operator"})
        _write(w / "context" / (doc_id + ".md"), text)
        _write(w / "conventions" / "rules.md", "# Review rules\n\n" + "".join(
            "## %s Rule [required] [conformance]\n\n%s\n\n" % (rid, rtext) for rid, rtext in rules))
        key = {"benchmark": bench, "document": doc_id + ".md", "planted": [], "clean": [], "twin_of": None,
               "items": [{"item_id": "i%s%02d" % (bench[:4], k), "rule_id": rid, "gold": GOLD[(bench, rid)],
                          "evidence_unit_ids": list(EVIDENCE.get(rid, ()))} for k, (rid, _) in enumerate(rules)]}
        keys.append(_write(root / "keys" / bench / KEY_NAME, key))
        folders.append(str(w))
        benches.append(bench)
    config = dict(json.loads((BASELINES / "doc_judge_prompt.json").read_text(encoding="utf-8")), **CONFIG_OVERRIDE)
    config_path = _write(root / "doc_judge_prompt.json", config)
    return folders, benches, [str(k) for k in keys], config_path


class Fake:
    """A canned model: replies by (group, rule), one token per word. It records each
    rendering it was asked for (the system turn must be None: one user turn)."""

    def __init__(self, group, prompts, asked):
        self.group, self.asked = group, asked
        self.by_user = {p["user"]: (p["rule_id"], p.get("item_id"), p.get("form")) for p in prompts if p["group"] == group}

    def prepare(self):
        return {"model_id": "fixture/" + self.group, "digest": "fixture", "checkpoint": {"checkpoint": "base"}}

    def max_context(self):
        return 10 ** 6

    def count_prompt(self, system, user):
        return len(user.split())

    def generate(self, system, user, max_new_tokens):
        rule, item_id, form = self.by_user[user]
        self.asked.append((self.group, rule, system) if form is None else (self.group, rule, system, max_new_tokens, user))
        label = B1_REPLIES.get((self.group, rule), "undecided")
        reply = (("no label here" if label is None else json.dumps({"item_id": item_id, "label": label, "evidence": "e", "reason": "r"}))
                 if form else REPLIES[(self.group, rule)][0])
        if reply is None:
            raise type("OutOfMemoryError", (RuntimeError,), {})("fixture: out of memory")
        cut = (self.group, rule) == ("phi", "CONV-ST01")      # this reply reaches its allowance in both arms
        return {"text": reply, "payload": "<rendered>" + user, "form": "rendered_prompt",
                "output_tokens": max_new_tokens if cut else len(reply.split()), "prefill": {"prefill_seconds": 0.01, "chunks": 0}}

    def release(self):
        pass


@contextlib.contextmanager
def canned(prompts, asked):
    tool = _tool()
    groups = {"local_auditor": "phi", "local_producer": "qwen"}
    with patch.object(tool, "make_backend", lambda reader, context: Fake(groups[reader["backend"]], prompts, asked)):
        yield


def pipeline_run(td):
    """build, the sealed replay pass, judge and score, on the fixture. Returns every product."""
    import replay_prompts
    td = Path(td)
    folders, benches, keys, config = workloads(td)
    tool = _tool()
    prompts_file = td / "replay_prompts.json"
    built = tool.build(folders, prompts_file, benchmarks=benches, config_path=config)
    asked = []
    out = td / "evidence" / "b1" / "g1"
    with canned(built["prompts"], asked), contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()):
        code = replay_prompts.main(["run", "--prompts", str(prompts_file), "--out", str(out), "--paths", "sdpa"])
    judged = scores = None
    if code == 0:
        judged = tool.judge(prompts_file, out, td / "judged")
        scores = tool.score(td / "judged" / "judgements.json", keys, td / "scored")
    return {"built": built, "asked": asked, "code": code, "out": out, "judged": judged, "scores": scores,
            "prompts_file": prompts_file, "keys": keys}


def observe_stopped():
    """The pass stops at its sixth prompt: what it answered stays readable, and no verdict is given."""
    tool = _tool()
    with tempfile.TemporaryDirectory(prefix="shimmer_g1_stop_") as td:
        td = Path(td)
        folders, _, keys, config = workloads(td)
        items = [str(_write(td / "items" / (bench + ".json"), {"items": [
            {"item_id": "i%s%02d" % (bench[:4], k), "document_id": doc_id, "rule_id": rid, "benchmark": bench}
            for k, (rid, _) in enumerate(rules)]})) for bench, (doc_id, _, rules) in DOCS.items()]
        prompts_file = td / "p.json"
        built = tool.build(folders, prompts_file, items=items, config_path=config, b1=True)
        out, asked, calls, stopped = td / "pass", [], [0], False
        with canned(built["prompts"], asked):
            factory = tool.make_backend

            def stopping(reader, context):
                backend = factory(reader, context)
                generate = backend.generate

                def counted(system, user, n):
                    calls[0] += 1
                    if calls[0] > 5:
                        raise RuntimeError("fixture: stopped")
                    return generate(system, user, n)
                backend.generate = counted
                return backend
            with patch.object(tool, "make_backend", stopping), contextlib.redirect_stdout(io.StringIO()):
                try:
                    tool.run(prompts_file, out)
                except RuntimeError:
                    stopped = True
        fixture_config = json.loads(Path(config).read_text(encoding="utf-8"))
        try:
            with patch.object(tool, "load_config", lambda path=None: fixture_config):
                judged = tool.judge(prompts_file, out, td / "judged")
        except OSError as exc:
            return {"stopped": stopped, "judge": type(exc).__name__}
        sc = tool._score_corpus()
        bar_items = _write(td / "bar_items.json", {"contradoc": ["icont00"], "scitab": ["iscit00", "iscit02"], "left_out": [LEFT_OUT],
                                                   "prompts_sha256": judged["prompts_sha256"], "keys_sha256": tool.keys_digest(sc, keys)})
        with patch.object(tool, "BAR_ITEMS_SHA256", tool._lf_sha(bar_items)):
            scores = tool.score(td / "judged" / "judgements.json", keys, td / "scored", bar_items=bar_items)
        return {"stopped": stopped, "complete": judged["complete"], "answered": sum(1 for r in judged["judgements"] if r["source"] != "no_reply"),
                "bar": scores["bar"], "refused": "did not finish" in str(scores["bar_refused"])}


def expected_stopped():
    return {"stopped": True, "complete": False, "answered": 5, "bar": None, "refused": True}


def comparator_run(td):
    """The same fixture with the comparator: every workload's items, `build --b1`, the sealed
    pass, judge, and score leaving one item out."""
    import replay_prompts
    td = Path(td)
    folders, _, keys, config = workloads(td)
    items = []
    for bench, (doc_id, _, rules) in DOCS.items():
        items.append(str(_write(td / "items" / (bench + ".json"), {"items": [
            {"item_id": "i%s%02d" % (bench[:4], k), "document_id": doc_id, "rule_id": rid, "benchmark": bench}
            for k, (rid, _) in enumerate(rules)]})))
    tool = _tool()
    prompts_file = td / "replay_prompts.json"
    built = tool.build(folders, prompts_file, items=items, config_path=config, b1=True)
    asked = []
    out = td / "evidence" / "b1" / "g1"
    with canned(built["prompts"], asked), contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()):
        code = replay_prompts.main(["run", "--prompts", str(prompts_file), "--out", str(out), "--paths", "sdpa"])
    fixture_config = json.loads(Path(config).read_text(encoding="utf-8"))
    quiet = contextlib.redirect_stdout(io.StringIO())
    judged_path = td / "judged" / "judgements.json"
    with patch.object(tool, "load_config", lambda path=None: fixture_config), quiet:
        tool.main(["judge", "--prompts", str(prompts_file), "--run", str(out), "--out", str(td / "judged")])
    judged = json.loads(judged_path.read_text(encoding="utf-8"))
    sc = tool._score_corpus()
    manifest = {"contradoc": ["icont00"], "scitab": ["iscit00", "iscit02"], "left_out": [LEFT_OUT],
                "prompts_sha256": judged["prompts_sha256"], "keys_sha256": tool.keys_digest(sc, keys)}
    bar_items = _write(td / "bar_items.json", manifest)
    wrong = _write(td / "bar_items_wrong.json", dict(manifest, scitab=["iscit00"]))
    other = _write(td / "bar_items_other.json", dict(manifest, keys_sha256="0" * 64))
    other_prompts = _write(td / "bar_items_other_prompts.json", dict(manifest, prompts_sha256="0" * 64))
    with patch.object(tool, "BAR_ITEMS_SHA256", tool._lf_sha(bar_items)), contextlib.redirect_stdout(io.StringIO()):
        cli = tool.main(["score", "--judgements", str(judged_path), *[a for k in keys for a in ("--key", k)],
                         "--bar-items", str(bar_items), "--out", str(td / "scored")])
    scores = json.loads((td / "scored" / "g1_scores.json").read_text(encoding="utf-8")) if cli == 0 else {}
    with patch.object(tool, "BAR_ITEMS_SHA256", tool._lf_sha(bar_items)):
        unpinned = tool.score(judged_path, keys, td / "scored2", bar_items=wrong)
    with patch.object(tool, "BAR_ITEMS_SHA256", tool._lf_sha(other)):
        other_inputs = tool.score(judged_path, keys, td / "scored7", bar_items=other)
    with patch.object(tool, "BAR_ITEMS_SHA256", tool._lf_sha(other_prompts)):
        prompts_differ = tool.score(judged_path, keys, td / "scored10", bar_items=other_prompts)
    with patch.object(tool, "BAR_ITEMS_SHA256", tool._lf_sha(wrong)):
        refused = tool.score(judged_path, keys, td / "scored3", bar_items=wrong)
    second = plain = None
    with patch.object(tool, "BAR_ITEMS_SHA256", tool._lf_sha(bar_items)):
        for attempt in ("second", "plain"):
            try:
                tool.score(judged_path, keys, td / "scored", bar_items=bar_items if attempt == "second" else None)
            except ValueError as exc:
                second, plain = (str(exc), plain) if attempt == "second" else (second, str(exc))
        try:
            tool.score(judged_path, keys + keys[:1], td / "scored4", bar_items=bar_items)
            twice = None
        except ValueError as exc:
            twice = str(exc)
    edited = _write(td / "judged2.json", dict(judged, repository_config_matches=False))
    edited_b1 = _write(td / "judged4.json", dict(judged, repository_b1_prompt_matches=False))
    missing = _write(td / "judged3.json", dict(judged, groups=judged["groups"] + ["third"]))
    first_blocked = None
    with patch.object(tool, "BAR_ITEMS_SHA256", tool._lf_sha(bar_items)):
        changed = tool.score(edited, keys, td / "scored5", bar_items=bar_items)
        changed_b1 = tool.score(edited_b1, keys, td / "scored8", bar_items=bar_items)
        absent = tool.score(missing, keys, td / "scored6", bar_items=bar_items)
        tool.score(judged_path, keys, td / "scored9")             # no verdict: blocks nothing
        try:
            late = tool.score(judged_path, keys, td / "scored9", bar_items=bar_items)
        except ValueError as exc:
            late, first_blocked = {}, str(exc)
    tampered = dict(json.loads(prompts_file.read_text(encoding="utf-8")))
    tampered["b1_prompt"] = dict(tampered["b1_prompt"], note="a field no prompt renders")
    tampered_file = _write(td / "tampered.json", tampered)
    try:
        tool.load_prompts(tampered_file)
        b1_prompt_held = False
    except ValueError:
        b1_prompt_held = True
    return {"built": built, "asked": asked, "code": code, "scores": scores, "file": prompts_file, "refused": refused,
            "unpinned": unpinned, "out": out, "report": (td / "scored" / "G1_RESULTS.md").read_text(encoding="utf-8") if cli == 0 else "",
            "second": second, "plain": plain, "twice": twice, "changed": changed, "changed_b1": changed_b1, "absent": absent,
            "other_inputs": other_inputs, "prompts_differ": prompts_differ, "late": late, "first_blocked": first_blocked, "b1_prompt_held": b1_prompt_held, "cli": cli}


# ---- observations -------------------------------------------------------------------------

def observe_build():
    with tempfile.TemporaryDirectory(prefix="shimmer_g1_build_") as td:
        folders, benches, _, config = workloads(td)
        tool = _tool()
        built = tool.build(folders, Path(td) / "p.json", benchmarks=benches, config_path=config)
        reloaded = len(tool.load_prompts(Path(td) / "p.json"))
        rows = []
        for p in built["prompts"]:
            bench = p["benchmark"]
            doc_id, text, rules = DOCS[bench]
            rule_text = dict(rules)[p["rule_id"]]
            user = p["user"]
            rows.append([p["group"], bench, p["rule_id"], rule_text in user, text in user,
                         -1 < user.find(text) < user.find(rule_text), '"outcome"' not in user])
        return {"rows": sorted(rows), "reloaded": reloaded, "count": built["prompt_count"]}


def expected_build():
    rows = [[g, bench, rid, True, True, True, True] for g in ("phi", "qwen")
            for bench, (_, _, rules) in DOCS.items() for rid, _ in rules]
    return {"rows": sorted(rows), "reloaded": 18, "count": 18}


def observe_pass():
    import ordinary_final_run
    import analyze_ordinary_final_run as analysis
    import reply_records
    with tempfile.TemporaryDirectory(prefix="shimmer_g1_pass_") as td:
        got = pipeline_run(td)
        records = reply_records.records(got["out"] / "audit" / "model_replies")
        seen = ordinary_final_run.replay_observation(got["out"], got["built"]["prompt_count"], ["sdpa"])
        status = analysis.replay_pass_status(got["out"] / "replay_measurement.json", "g1",
                                             {"checkpoints": {"g1": {"exit_code": got["code"]}}})
        return {"code": got["code"], "records": len(records),
                "texts_kept": sum(1 for r in records if not r["sensitive"] and isinstance((r.get("reply") or {}).get("text"), str)),
                "failed_calls": sum(1 for r in records if not r["backend_ok"]),
                "systems": sorted({str(s) for _, _, s in got["asked"]}),
                "asked": len(got["asked"]),
                "runner_missing": seen["items_without_one_record"], "runner_expected": seen["items"],
                "analyser": analysis.replay_text("g1", status).split(";")[0]}


def expected_pass():
    return {"code": 0, "records": 18, "texts_kept": 17, "failed_calls": 1, "systems": ["None"], "asked": 18,
            "runner_missing": [], "runner_expected": 18,
            "analyser": "g1 (exit 0): document-level judging (G1) of 18 prompts, one per model group, document and rule"}


def observe_judge():
    with tempfile.TemporaryDirectory(prefix="shimmer_g1_judge_") as td:
        got = pipeline_run(td)
        if got["judged"] is None:
            return {"code": got["code"]}
        return {"code": got["code"], "rows": sorted([r["group"], r["rule_id"], r["kept"], r["refusal"], r["written_cls"], r["cls"]]
                                                    for r in got["judged"]["judgements"])}


def expected_judge():
    return {"code": 0, "rows": sorted([g, rid, *want] for (g, rid), (_, want) in REPLIES.items())}


def _by_hand():
    """The figures each view must give, computed here from GOLD and REPLIES alone."""
    spec_classes = {"contradictory": "FLAG", "not contradictory": "CLEAR", "contradiction": "FLAG",
                    "entailment": "CLEAR", "not mentioned": "UNDECIDED", "absent": "FLAG", "present": "CLEAR",
                    "refutes": "FLAG", "supports": "CLEAR", "not enough info": "UNDECIDED"}
    out = {}
    for group in ("phi", "qwen"):
        for view in ("screened", "unscreened", "as_b3"):
            for bench in DOCS:
                rows = []
                for (g, rid), (_, (kept, refusal, written, cls)) in REPLIES.items():
                    if g != group or (bench, rid) not in GOLD:
                        continue
                    gold = spec_classes[GOLD[(bench, rid)]]
                    refused = not kept and refusal not in ("out_of_memory",)
                    failed = refusal == "out_of_memory"
                    if view == "screened":
                        pred = cls
                    elif view == "unscreened":
                        pred = written
                    else:
                        pred = "CLEAR" if (refused or failed) else cls
                    source = ("silence" if view == "as_b3" and (refused or failed) else
                              "as_written" if view == "unscreened" and written != "ABSTAIN" else
                              "no_reply" if failed else "refused" if refused else
                              "kept_unsettled" if written == "UNDECIDED" else "kept_claim")
                    rows.append((pred, gold, source, refused, written))
                tp = sum(1 for p, g, *_ in rows if p == "FLAG" and g == "FLAG")
                fp = sum(1 for p, g, *_ in rows if p == "FLAG" and g != "FLAG")
                fn = sum(1 for p, g, *_ in rows if g == "FLAG" and p != "FLAG")
                out[(group, view, bench)] = {
                    "tp": tp, "fp": fp, "fn": fn,
                    "correct": sum(1 for p, g, *_ in rows if p == g),
                    "silence": sum(1 for _, _, s, *_ in rows if s == "silence"),
                    "silence_flags": sum(1 for p, _, s, *_ in rows if s == "silence" and p == "FLAG"),
                    "refusals": sum(1 for *_, r, _ in rows if r),
                    "correct_refusals": sum(1 for _, g, _, r, w in rows if r and w not in ("ABSTAIN", g)),
                    "removed_right": sum(1 for _, g, _, r, w in rows if r and w == g)}
    return out


def observe_scores():
    with tempfile.TemporaryDirectory(prefix="shimmer_g1_score_") as td:
        try:
            got = pipeline_run(td)
        except ValueError as exc:  # the scoring refused (a label folder the scorer did not label)
            return {"stopped": type(exc).__name__}
        if got["scores"] is None:
            return {"code": got["code"]}
        out = {}
        for group, views in got["scores"]["scores"].items():
            for view, benches in views.items():
                for bench, m in benches.items():
                    out["%s/%s/%s" % (group, view, bench)] = {
                        "tp": m["flag_tp"], "fp": m["flag_fp"], "fn": m["flag_fn"],
                        "correct": round(m["accuracy"] * m["items"]),
                        "silence": m["silence_labels"], "silence_flags": m["silence_flags"],
                        "refusals": m["refusals"], "correct_refusals": m["correct_refusals"],
                        "removed_right": m["refusals_that_removed_a_right_answer"]}
        return {"code": got["code"], "figures": out}


def expected_scores():
    figures = {}
    for (group, view, bench), m in _by_hand().items():
        figures["%s/%s/%s" % (group, view, bench)] = dict(m)
    return {"code": 0, "figures": figures}


def observe_comparator():
    import bare_model
    import python_only
    with tempfile.TemporaryDirectory(prefix="shimmer_g1_b1_") as td:
        got = comparator_run(td)
        spec = bare_model.load_prompt()
        form = [p for p in got["built"]["prompts"] if p.get("form")]
        calls = [a for a in got["asked"] if len(a) == 5]
        same = 0
        for p in form:
            doc_id, text, rules = DOCS[p["benchmark"]]
            conventions = [("%s Rule [required] [conformance]" % rid, rtext) for rid, rtext in rules]
            same += p["user"] == bare_model.render_user(spec, p["benchmark"], document=text, conventions=conventions, item=p) \
                and p["system"] == bare_model.render_system(spec, p["benchmark"])
        by_system = sum(1 for a in calls if a[2] == bare_model.render_system(spec, next(
            p["benchmark"] for p in form if p["user"] == a[4])))
        import ordinary_final_run
        import prepare_ordinary_final_run
        import analyze_ordinary_final_run as analysis
        replay = prepare_ordinary_final_run.replay_declaration(got["file"].read_bytes())
        seen = ordinary_final_run.replay_observation(got["out"], got["built"]["prompt_count"], ["sdpa"])
        status = analysis.replay_pass_status(got["out"] / "replay_measurement.json", "g1",
                                             {"checkpoints": {"g1": {"exit_code": got["code"]}}})
        return {"declared": replay["prompt_count"], "runner_missing": seen["items_without_one_record"],
                "analyser": analysis.replay_text("g1", status).split(";")[0],
                "code": got["code"], "count": got["built"]["prompt_count"], "reloaded": len(_tool().load_prompts(got["file"])),
                "form": len(form), "same_as_bare_model": same, "calls": len(calls), "calls_with_b1_system": by_system,
                "allowances": sorted({a[3] for a in calls}) == [int(python_only.pipeline_literal("PRODUCTION_MAX_TOKENS"))],
                "g1_systems": sorted({str(a[2]) for a in got["asked"] if len(a) == 3})}


def expected_comparator():
    return {"declared": 36, "runner_missing": [],
            "analyser": "g1 (exit 0): document-level judging (G1) of 18 prompts, one per model group, document and rule, and 18 with B1's own prompt",
            "code": 0, "count": 36, "reloaded": 36, "form": 18, "same_as_bare_model": 18, "calls": 18,
            "calls_with_b1_system": 18, "allowances": True, "g1_systems": ["None"]}


def observe_comparator_scores():
    with tempfile.TemporaryDirectory(prefix="shimmer_g1_b1s_") as td:
        got = comparator_run(td)
        out = {}
        for group, views in got["scores"]["scores"].items():
            for bench in ("contradoc", "scitab"):
                m = views["b1_comparator"][bench]
                out["%s/%s" % (group, bench)] = [m["items"], m["flag_tp"], m["flag_fp"], m["flag_fn"]]
        scores = got["scores"]["scores"]
        phi = scores["phi"]
        bar = got["scores"]["bar"] or {}
        rows = bar.get("rows") or {}
        return {"figures": out, "left_out": got["scores"]["left_out"], "screened_scitab_items":
                phi["screened"]["scitab"]["items"],
                "bar_read": got["scores"]["bar"] is not None,
                "other_items_get_no_verdict": got["refused"]["bar"] is None and bool(got["refused"]["bar_refused"]),
                "an_unpinned_file_gets_no_verdict": got["unpinned"]["bar"] is None and "pinned" in str(got["unpinned"]["bar_refused"]),
                "the_first_score_stands": "first score" in str(got["second"]) and "first score" in str(got["plain"]),
                "a_score_with_no_verdict_blocks_nothing": got["first_blocked"] is None and got["late"].get("bar") is not None,
                "a_document_has_one_key": "two keys" in str(got["twice"]),
                "a_changed_config_gets_no_verdict": got["changed"]["bar"] is None and got["changed_b1"]["bar"] is None,
                "a_missing_model_gets_no_verdict": got["absent"]["bar"] is None,
                "other_keys_get_no_verdict": got["other_inputs"]["bar"] is None,
                "other_prompts_get_no_verdict": got["prompts_differ"]["bar"] is None,
                "the_b1_prompt_is_held_to_its_digest": got["b1_prompt_held"], "cli": got["cli"],
                "bound_to": sorted(k for k in ("judgements_sha256", "prompts_sha256", "run_id", "key_sha256") if got["scores"].get(k)),
                "quoting_evidence": [phi["screened"]["contradoc"]["tp_quoting_evidence"], phi["screened"]["scitab"]["tp_quoting_evidence"]],
                "truncated": [phi["screened"]["scitab"]["truncated"], phi["b1_comparator"]["scitab"]["truncated"]],
                "b1_abstain": scores["qwen"]["b1_comparator"]["scitab"]["abstain"],
                "states": {g: {b: r["state"] for b, r in row.items()} for g, row in rows.items()},
                "verdict": bar.get("verdict"),
                "discordant": got["scores"]["discordant"].get("qwen", {}).get("scitab"),
                "kept_listed": sorted(r["item_id"] for r in got["scores"]["flags"]["phi"]["screened"]),
                "report_has": [s in got["report"] for s in ("Verdict: not_usable", "Only one arm right, phi contradoc",
                                                            "It carried two lanes of traffic.",
                                                            "Left out of every figure: " + LEFT_OUT)],
                "report_lists_no_passes": "missed: passes" not in got["report"],
                "digests": len(got["scores"]["doc_judge_sha256"] or "") + len(got["scores"]["bar_items_sha256"] or "")}


def expected_comparator_scores():
    # gold: CDOC-01 FLAG; ST01 FLAG, ST02 left out, ST03 UNDECIDED.
    return {"figures": {"phi/contradoc": [1, 1, 0, 0], "qwen/contradoc": [1, 0, 0, 1],
                        "phi/scitab": [2, 1, 0, 0], "qwen/scitab": [2, 1, 0, 0]},
            "left_out": [LEFT_OUT], "screened_scitab_items": 2, "bar_read": True,
            "other_items_get_no_verdict": True, "an_unpinned_file_gets_no_verdict": True,
            "the_first_score_stands": True, "a_score_with_no_verdict_blocks_nothing": True, "a_document_has_one_key": True,
            "a_changed_config_gets_no_verdict": True, "a_missing_model_gets_no_verdict": True, "other_keys_get_no_verdict": True, "other_prompts_get_no_verdict": True,
            "the_b1_prompt_is_held_to_its_digest": True, "cli": 0, "bound_to": ["judgements_sha256", "key_sha256", "prompts_sha256", "run_id"],
            "quoting_evidence": [1, 0], "truncated": [1, 1], "b1_abstain": 1,
            "states": {"phi": {"contradoc": "missed", "scitab": "missed"}, "qwen": {"contradoc": "missed", "scitab": "missed"}},
            "verdict": "not_usable",
            "discordant": {"g1_only": 0, "b1_only": 1, "documents_g1_ahead": 0, "documents_b1_ahead": 1},
            "kept_listed": ["icont00", "icont00", "icuad00", "iscit00"], "report_has": [True] * 4, "report_lists_no_passes": True, "digests": 128}


def observe_real_items():
    """The real file, its pinned digest and its counts."""
    tool = _tool()
    path = BASELINES / "g1_bar_items.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    return {"pinned": tool._lf_sha(path) == tool.BAR_ITEMS_SHA256,
            "counts": [len(value["contradoc"]), len(value["scitab"]), len(value["left_out"])],
            "digests": [len(value["prompts_sha256"]), len(value["keys_sha256"])],
            "disjoint": not (set(value["left_out"]) & set(value["scitab"]))}


def expected_real_items():
    return {"pinned": True, "counts": [60, 93, 2], "digests": [64, 64], "disjoint": True}


QUOTES = {"# Params": True, "P-51": True, "81.5": True, "| Alpha | 81.5 |": True, "Alpha": True, "1,000": True,
          "81": False, "5": False, ".5": False, "81.": False, ",000": False, "1,": False, "lph": False,
          "Passage: part": False, "Passage": False, "part": False, "00001": False, "P-00001": False, "## P-00001": False,
          "# D-d3dddddddddd": False, "P-00001 Passage: part": False, "## P-00001 Passage: part | Model": False,
          "|---|---|": False}
QUOTE_DOC = ("# D-d3dddddddddd\n\n## P-00001\n\nPassage: part\n\n| Model | Score |\n|---|---|\n| Alpha | 81.5 |\n| # Params | 1,000 |\n"
             "| P-51 | 2 |\n\n## P-00002\n\nPassage: part\n\nThe end.\n")


def observe_quotes():
    tool = _tool()
    config = tool.load_config()
    return {q: tool.quote_is_content(q, QUOTE_DOC, config) for q in QUOTES}


def expected_quotes():
    return dict(QUOTES)


EVIDENCE_CASES = {"long, in evidence alone": ("one two three", ["u01"], ["u01"], True),
                  "two words": ("one two", ["u01"], ["u01"], False),
                  "also outside the evidence": ("one two three", ["u01", "u02"], ["u01"], False),
                  "two units, both evidence": ("one two three", ["u01", "u02"], ["u01", "u02"], True),
                  "in no unit": ("one two three", [], ["u01"], False)}


def observe_evidence_rule():
    return {name: _tool().quotes_evidence(q, u, e) for name, (q, u, e, _) in EVIDENCE_CASES.items()}


def expected_evidence_rule():
    return {name: case[3] for name, case in EVIDENCE_CASES.items()}


def observe_reader():
    """A reply with a raw newline in its quote is read; a lone surrogate in one is written."""
    tool = _tool()
    config = tool.load_config()
    newline = tool.parse_reply('{"outcome": "not met", "quote": "It carried\n   two lanes", "reason": "r"}', config)
    with tempfile.TemporaryDirectory(prefix="shimmer_g1_utf_") as td:
        path = Path(td) / "x.json"
        reason = tool.parse_reply('{"outcome": "not met", "quote": "x", "reason": "\\ud83d"}', config)["reason"]
        tool._write_json(path, {"reason": reason})
        back = json.loads(path.read_text(encoding="utf-8"))["reason"]
        return {"newline_outcome": newline["outcome"], "newline_failure": newline["failure"], "surrogate_kept": back == reason,
                "no_partial_left": sorted(p.name for p in Path(td).iterdir())}


def expected_reader():
    return {"newline_outcome": "not met", "newline_failure": None, "surrogate_kept": True, "no_partial_left": ["x.json"]}


def observe_units():
    tool = _tool()
    document, config = DOCS["contradoc"][1], tool.load_config()
    return [tool.quote_units(document, q, config) for q in ("two lanes of traffic.", "The bridge never opened.", "nowhere", "Passage", "bridge")]


def expected_units():
    return [["u01-p-00001"], ["u02-p-00002"], [], [], ["u01-p-00001", "u02-p-00002"]]


def observe_cli():
    tool = _tool()
    with tempfile.TemporaryDirectory(prefix="shimmer_g1_cli_") as td:
        td = Path(td)
        folders, _, _, config = workloads(td)
        doc_id, _, rules = DOCS["contradoc"]
        items = _write(td / "items.json", {"items": [{"item_id": "icont00", "document_id": doc_id, "rule_id": rules[0][0], "benchmark": "contradoc"}]})
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            built = tool.main(["build", "--workload", folders[0], "--items", str(items), "--config", str(config), "--b1", "--out", str(td / "p.json")])
            refused = tool.main(["build", "--workload", folders[0], "--benchmark", "contradoc", "--config", str(config), "--b1", "--out", str(td / "q.json")])
        count = json.loads((td / "p.json").read_text(encoding="utf-8"))["prompt_count"]
        manifest = td / "workload" / "contradoc" / "_review_targets.json"
        _write(manifest, dict(json.loads(manifest.read_text(encoding="utf-8")), grounding=["x.md"]))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with_reference = tool.main(["build", "--workload", folders[0], "--items", str(items), "--config", str(config), "--b1", "--out", str(td / "r.json")])
        return {"built": built, "count": count, "no_items": refused, "with_reference": with_reference}


def expected_cli():
    return {"built": 0, "count": 4, "no_items": 4, "with_reference": 4}


def _m(tp, fp, fn, items, documents=None, strata=None, abstain=0, evidence=None):
    return {"flag_tp": tp, "flag_fp": fp, "flag_fn": fn, "items": items, "abstain": abstain, "truncated": 0,
            "flag_tp_documents": tp if documents is None else documents,
            "tp_quoting_evidence": tp if evidence is None else evidence,
            "strata": strata or [[items, tp + fn, tp + fp]]}


BAR_CASES = {
    # name: (screened, comparator, passes)
    "better_than_b1": (_m(20, 4, 10, 60), _m(15, 8, 15, 60), True),
    "equal_to_b1": (_m(15, 5, 15, 60), _m(15, 5, 15, 60), True),
    "a_cautious_b1_does_not_fail_a_sound_model": (_m(18, 3, 12, 60), _m(4, 0, 26, 60), True),
    "a_silent_b1_does_not_fail_a_sound_model": (_m(18, 3, 12, 60), _m(0, 0, 30, 60), True),
    "a_flag_heavy_b1_does_not_fail_a_sound_model": (_m(18, 3, 12, 60), _m(27, 21, 3, 60), True),
    "a_lower_net_rate": (_m(14, 8, 16, 60), _m(15, 5, 15, 60), False),
    "one_correct_flag": (_m(1, 0, 29, 60), _m(0, 0, 30, 60), False),
    "one_document": (_m(6, 0, 24, 60, 1), _m(1, 0, 29, 60), False),
    "at_chance": (_m(15, 15, 15, 60), _m(2, 8, 28, 60), False),
    "flags_everything": (_m(30, 30, 0, 60), _m(2, 8, 28, 60), False),
    "flags_whole_tables": (_m(40, 20, 0, 60, strata=[[3, 2, 3]] * 20), _m(2, 8, 38, 60), False),
    "quotes_elsewhere": (_m(18, 3, 12, 60, evidence=1), _m(4, 0, 26, 60), False),
    "b1_unreadable": (_m(18, 3, 12, 60), _m(4, 0, 26, 60, abstain=4), False),
}


def _refused(call):
    try:
        call()
    except ValueError:
        return True
    return False


def observe_bar():
    tool = _tool()
    rows = {name: tool.bar_row(mine, b1, "contradoc")["passes"] for name, (mine, b1, _) in BAR_CASES.items()}
    good, poor = BAR_CASES["better_than_b1"][:2], BAR_CASES["at_chance"][:2]
    unread = BAR_CASES["b1_unreadable"][:2]

    def figures(*per_group):
        return {g: {"screened": {"contradoc": c[0], "scitab": s[0]}, "b1_comparator": {"contradoc": c[1], "scitab": s[1]}}
                for g, c, s in per_group}
    return {"rows": rows,
            "one_model_on_both": tool.bar(figures(("phi", good, good), ("qwen", poor, poor)))["models_passing"],
            "two_models_one_each": tool.bar(figures(("phi", good, poor), ("qwen", poor, good)))["usable_signal"],
            "no_comparator": tool.bar({"phi": {"screened": {"contradoc": good[0], "scitab": good[0]}}}),
            "void_is_marked": tool.bar_row(*BAR_CASES["b1_unreadable"][:2])["state"],
            "a_miss_needing_no_b1_beats_void": tool.bar_row(_m(0, 0, 30, 60), _m(4, 0, 26, 60, abstain=4))["state"],
            "void_report": [(s in tool.report({"scores": {}, "bar": tool.bar(figures(("phi", unread, unread)))})) for s in
                            ("Verdict: void", "void: B1 too often unreadable", "missed:")],
            "void_verdict": tool.bar(figures(("phi", unread, good), ("qwen", poor, poor)))["verdict"],
            "both_void_is_not_a_miss": tool.bar(figures(("phi", unread, unread), ("qwen", unread, unread)))["usable_signal"],
            "a_bad_stratum_is_refused": _refused(lambda: tool.chance_tail([[3, 2, 4]], 1)),
            "an_allowance_override_is_refused": _refused(lambda: tool.run("no such file", "no such folder", max_new_tokens=256)),
            "missed_beats_void": tool.bar(figures(("phi", unread, poor)))["verdict"],
            "scitab_needs_no_evidence": tool.bar_row(*BAR_CASES["quotes_elsewhere"][:2], "scitab")["passes"],
            "two_tables_tail": round(tool.chance_tail([[3, 2, 1], [3, 2, 1]], 2), 6)}


def expected_bar():
    return {"rows": {name: case[2] for name, case in BAR_CASES.items()}, "one_model_on_both": ["phi"],
            "two_models_one_each": False, "no_comparator": None, "void_is_marked": "void",
            "a_miss_needing_no_b1_beats_void": "missed", "void_report": [True, True, False],
            "void_verdict": "void", "missed_beats_void": "not_usable", "scitab_needs_no_evidence": True,
            "both_void_is_not_a_miss": None, "a_bad_stratum_is_refused": True, "an_allowance_override_is_refused": True,
            "two_tables_tail": round((2 / 3) ** 2, 6)}


def _opener():
    for frame in inspect.stack()[2:]:
        name = Path(frame.filename).name
        if "pathlib" in frame.filename or name in (Path(__file__).name,):
            continue
        return name
    return "?"


def observe_key_reads():
    seen = set()
    real_open, real_read = builtins.open, Path.read_text

    def traced_open(file, *a, **k):
        if Path(str(file)).name == KEY_NAME:
            seen.add(_opener())
        return real_open(file, *a, **k)

    def traced_read(self, *a, **k):
        if self.name == KEY_NAME:
            seen.add(_opener())
        return real_read(self, *a, **k)
    with tempfile.TemporaryDirectory(prefix="shimmer_g1_keys_") as td:
        with patch.object(builtins, "open", traced_open), patch.object(Path, "read_text", traced_read):
            got = pipeline_run(td)
    return {"code": got["code"], "openers": sorted(seen)}


def expected_key_reads():
    return {"code": 0, "openers": ["score_corpus.py"]}


def observe_sealing():
    import ordinary_final_run
    import prepare_ordinary_final_run
    with tempfile.TemporaryDirectory(prefix="shimmer_g1_seal_") as td:
        folders, benches, _, config = workloads(td)
        built = _tool().build(folders, Path(td) / "p.json", benchmarks=benches, config_path=config)
        data = (Path(td) / "p.json").read_bytes()
        try:
            replay = prepare_ordinary_final_run.replay_declaration(data)
        except Exception as exc:  # the sealer refuses the file
            return {"declared": type(exc).__name__}
        items = json.dumps({"items": [{"item_id": "x1", "document_id": "d0aaaaaaaaaa", "rule_id": "CONV-CDOC-01",
                                       "benchmark": "contradoc"}]}).encode("utf-8")
        targets = json.dumps({"targets": ["d0aaaaaaaaaa.md"]}).encode("utf-8")
        b1 = prepare_ordinary_final_run.b1_fields(items, targets, [{"name": "g1", "replay": True, "args": ["--paths", "sdpa"]}],
                                                  replay)
        manifest = {"b1": b1}
        return {"declared": replay["prompt_count"] == built["prompt_count"],
                "passes": [c["name"] for c in ordinary_final_run.b1_checkpoints(manifest)],
                "expected_records": ordinary_final_run.expected_records(manifest)}


def expected_sealing():
    return {"declared": True, "passes": ["g1"], "expected_records": 18}


def observe_render():
    """The REAL bare_model.LocalBackend._render on a stub tokenizer that records the messages
    it is given: G1's None system turn and B1's string system turn."""
    import bare_model
    seen = []

    class Tok:
        def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
            seen.append([(m["role"], m["content"]) for m in messages])
            return "rendered"
    backend = object.__new__(bare_model.LocalBackend)
    backend._loaded = lambda: (Tok(), None)
    backend._render(None, "u")
    backend._render("s", "u")
    return seen


def expected_render():
    return [[("user", "u")], [("system", "s"), ("user", "u")]]


def render_none_branch_reverted():
    """bare_model._render as before G1: a system message whatever the system turn is."""
    import bare_model

    def old(self, system, user):
        tok, _ = self._loaded()
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        return tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return patch.object(bare_model.LocalBackend, "_render", old)


# ---- J1: a named candidate on the saved judging prompts and on B1's (D-261, D-262) ------------

class J1Backend:
    """A canned model that records the reader it was built with and what it was sent."""

    def __init__(self, reader, seen, cap=False):
        self.reader, self.seen, self.cap = reader, seen, cap

    def prepare(self):
        self.seen.append(("load", self.reader["model_id"], tuple(sorted(self.reader["decoding"]["kwargs"])), self.reader["decoding"]["status"]))
        return {"model_id": self.reader["model_id"], "digest": "fixture", "checkpoint": {"checkpoint": "base"}}

    def max_context(self):
        return 10 ** 6

    def count_prompt(self, system, user):
        return len(user.split())

    def generate(self, system, user, max_new_tokens):
        self.seen.append(("call", max_new_tokens, system))
        return {"text": "{}", "payload": user, "form": "rendered_prompt", "output_tokens": max_new_tokens if self.cap else 1,
                "prefill": {"prefill_seconds": 0.01, "chunks": 0}}

    def release(self):
        pass


def j1_file(td):
    tool = _tool()
    td = Path(td)
    folders, _, _, _ = workloads(td)
    items, calls = [], []
    for bench, (doc_id, text, rules) in DOCS.items():
        items.append(str(_write(td / "items" / (bench + ".json"), {"items": [
            {"item_id": "i%s%02d" % (bench[:4], k), "document_id": doc_id, "rule_id": rid, "benchmark": bench}
            for k, (rid, _) in enumerate(rules)]})))
        calls.append({"call_id": "c" + doc_id, "document_id": doc_id, "rule_id": rules[0][0], "item_id": "i%s00" % bench[:4],
                      "unit_id": "u01", "unit_text": text, "fields_present": [], "user": "You are an agent. " + text})
    saved = _write(td / "calls.json", calls)
    prompts_file = td / "prompts.json"
    built = tool.build(folders, prompts_file, items=items, config_path=BASELINES / "doc_judge_prompt_j1.json", b1=True, agent_calls=saved)
    return prompts_file, built, calls


def j1_pass(td, prompts_file, cap=False):
    import decoding_policy
    tool = _tool()
    seen = []
    reader = {"agent": "PRACTICE_AUDITOR", "backend": "local_auditor", "model_id": "the auditor's own", "model_mode": "base",
              "decoding": decoding_policy.policy("local_auditor")}
    with contextlib.redirect_stdout(io.StringIO()):
        tool.run(prompts_file, Path(td) / "out", backend_factory=lambda r, c: J1Backend(r, seen, cap), reader_for=lambda g, a: dict(reader))
    return seen


def observe_j1():
    import bare_model
    tool = _tool()
    j1 = json.loads((BASELINES / "doc_judge_prompt_j1.json").read_text(encoding="utf-8"))
    spec = bare_model.load_prompt()
    with tempfile.TemporaryDirectory(prefix="shimmer_j1_") as td:
        prompts_file, built, calls = j1_file(td)
        seen = j1_pass(td, prompts_file)
        reloaded = len(tool.load_prompts(prompts_file))
    groups = {}
    for p in built["prompts"]:
        g = groups.setdefault(p["group"], {"agent": 0, "b1": 0, "note": 0, "shipped_system": 0})
        g[p.get("form")] += 1
        g["note"] += p["user"].endswith(j1["j1"]["agent_note"])
        g["shipped_system"] += p.get("form") == "b1" and p["system"] == bare_model.render_system(spec, p["benchmark"])
    loads = [s for s in seen if s[0] == "load"]
    return {"groups": groups, "no_document_prompt": all(p.get("form") for p in built["prompts"]),
            "agent_first": built["prompts"][0]["form"], "models": sorted({s[1] for s in loads}),
            "stops_left": sorted({k for s in loads for k in s[2]} & {"eos_token_id", "pad_token_id"}), "status": sorted({s[3] for s in loads}),
            "allowances": sorted({s[1] for s in seen if s[0] == "call"}), "reloaded": reloaded == built["prompt_count"]}


def expected_j1():
    return {"groups": {"judge_direct": {"agent": 4, "b1": 9, "note": 0, "shipped_system": 0},
                       "judge_reason": {"agent": 4, "b1": 9, "note": 4, "shipped_system": 9}},
            "no_document_prompt": True, "agent_first": "agent", "models": ["unsloth/phi-4-bnb-4bit"], "stops_left": [], "status": ["new"],
            "allowances": [768, 1536, 2048], "reloaded": True}


def observe_j1_stop():
    with tempfile.TemporaryDirectory(prefix="shimmer_j1s_") as td:
        prompts_file, built, _ = j1_file(td)
        try:
            seen = j1_pass(td, prompts_file, cap=True)
            return {"stopped": False, "calls": len([s for s in seen if s[0] == "call"])}
        except RuntimeError as exc:
            return {"stopped": "ran to the allowance" in str(exc)}


def expected_j1_stop():
    return {"stopped": True}


def observe_j1_reading():
    import judge_read
    unit = "Alpha scores 81.5 in the table."
    good = {"verdict": "VIOLATION", "record_verdict": "irregular", "relation": "date_window", "value_a": "81.5", "quote": "Alpha scores 81.5"}
    ok = dict(good, verdict="COMPLIANT", record_verdict="ok")
    words = dict(good, relation="in_conflict", value_a=None)   # undeclared: `contradiction` is declared since INFRA-046
    no_figures = dict(good, relation="sum_mismatch", value_a=None)
    hedge = dict(good, confidence="UNCERTAIN")
    elsewhere = dict(good, quote="words the unit does not hold")
    draft = json.dumps({"items": [ok]})
    final = json.dumps({"items": [good]})
    m = _m(5, 0, 2, 15, strata=[[15, 7, 5]])
    counts = {"calls": 20, "readable": 20}
    b1 = _m(4, 1, 3, 15)
    base = judge_read.agent_row(m, counts, b1, 0)
    rows = {"contradoc": {"judge_direct": dict(base), "judge_reason": dict(base, net=9)}, "scitab": {"judge_direct": dict(base, passes=False), "judge_reason": dict(base, passes=False)}}
    tie = {"contradoc": {"judge_direct": dict(base), "judge_reason": dict(base)}}
    none = {"contradoc": {"judge_direct": dict(base, passes=False)}}
    both = lambda item: [judge_read.call_class([item], unit, None, v) for v in judge_read.VIEWS]
    return {"last_object": judge_read.call_class(judge_read.reply_items("Thinking. %s Then.\n%s" % (draft, final)), unit),
            "escape_repaired": judge_read.reply_items('{"items": [{"quote": "a \\| b"}]}') is not None,
            "prose": judge_read.reply_items("no json at all"), "flat_object": judge_read.reply_items(json.dumps({"verdict": "x"})),
            "ok": both(ok), "words": both(words), "no_figures": both(no_figures), "hedged": both(hedge), "quote_elsewhere": both(elsewhere),
            "verdict_only": judge_read.call_class([{"verdict": "violation"}], unit, None, "judge"), "no_items": judge_read.call_class([], unit),
            "order": [judge_read.item_class(c) for c in (["CLEAR", "FLAG"], ["REFUSED", "CLEAR"], ["SILENT", "REFUSED"], ["SILENT", "UNREADABLE"], ["UNREADABLE"])],
            "passes": base["passes"], "flags_everything": judge_read.agent_row(_m(7, 8, 0, 15, strata=[[15, 7, 15]]), counts, b1, -9)["not_flagging_everything"],
            "unreadable": judge_read.agent_row(m, dict(counts, readable=18), b1, 0)["passes"],
            "not_above_c1": judge_read.agent_row(m, counts, b1, 5)["passes"],
            "precision": judge_read.agent_row(_m(5, 3, 2, 15, strata=[[15, 7, 8]]), counts, b1, 0)["precision_at_least_b1"],
            "few_b1_flags": judge_read.agent_row(_m(5, 3, 2, 15, strata=[[15, 7, 8]]), counts, _m(1, 0, 6, 15), 0)["precision_at_least_b1"],
            "decide": [judge_read.decide(rows), judge_read.decide(tie), judge_read.decide(none)]}


def expected_j1_reading():
    return {"last_object": "FLAG", "escape_repaired": True, "prose": None, "flat_object": None,
            "ok": ["CLEAR", "CLEAR"], "words": ["REFUSED", "FLAG"], "no_figures": ["REFUSED", "FLAG"], "hedged": ["REFUSED", "REFUSED"],
            "quote_elsewhere": ["REFUSED", "REFUSED"], "verdict_only": "FLAG", "no_items": "SILENT",
            "order": [("FLAG", "kept_claim"), ("CLEAR", "kept_claim"), ("UNDECIDED", "refused"), ("ABSTAIN", "silence"), ("ABSTAIN", "unreadable")],
            "passes": True, "flags_everything": False, "unreadable": False, "not_above_c1": False, "precision": False, "few_b1_flags": True,
            "decide": [("go", "judge_reason"), ("go", "judge_direct"), ("drop", None)]}


# The invented J1 fixture's declared class setting (D-380): its SciTab gold holds not enough info.
J1_FIXTURE_SETTINGS = {"scitab": "3-class", "contradoc": "2-class"}


def observe_j1_end_to_end():
    """`read` on a whole fixture pass: it finishes, and each guard refuses."""
    import judge_read
    tool = _tool()
    with tempfile.TemporaryDirectory(prefix="shimmer_j1e_") as td:
        td = Path(td)
        prompts_file, built, _ = j1_file(td)
        j1_pass(td, prompts_file)
        keys = [str(k) for k in sorted((td / "keys").rglob(KEY_NAME))]
        sc = tool._score_corpus()
        bar = {"prompts_sha256": hashlib.sha256(prompts_file.read_bytes()).hexdigest(), "keys_sha256": tool.keys_digest(sc, keys), "left_out": [],
               "c1_net": {"contradoc": 0, "scitab": 1}, "items": {"contradoc": 1, "scitab": 1}}
        bar_path = _write(td / "bar.json", bar)
        baseline = _write(td / "base.json", {"flags": {"qwen_tuned": {tool.COMPARATOR: []}}})
        got = judge_read.read(prompts_file, td / "out", keys, bar_path, baseline, td / "read", J1_FIXTURE_SETTINGS)
        out = {"verdict": got["verdict"], "items": sorted(got["views"]["judge_direct"]["strict"]), "unreadable": got["call_counts"]["judge_direct/scitab"]["readable"]}
        tries = {"again": (td / "read", bar), "other_prompts": (td / "r2", dict(bar, prompts_sha256="0")), "other_keys": (td / "r3", dict(bar, keys_sha256="0"))}
        for name, (folder, value) in tries.items():
            try:
                judge_read.read(prompts_file, td / "out", keys, _write(td / (name + ".json"), value), baseline, folder, J1_FIXTURE_SETTINGS)
                out[name] = "read"
            except ValueError:
                out[name] = "refused"
        measurement = json.loads((td / "out" / tool.MEASUREMENT_FILE).read_text(encoding="utf-8"))
        _write(td / "out" / tool.MEASUREMENT_FILE, dict(measurement, complete=False))
        try:
            judge_read.read(prompts_file, td / "out", keys, bar_path, baseline, td / "r4", J1_FIXTURE_SETTINGS)
            out["unfinished"] = "read"
        except ValueError:
            out["unfinished"] = "refused"
    return out


def expected_j1_end_to_end():
    return {"verdict": "drop", "items": ["contradoc", "scitab"], "unreadable": 1 - 1,
            "again": "refused", "other_prompts": "refused", "other_keys": "refused", "unfinished": "refused"}


def observe_j1_truncated():
    """A B1 reply that ran to its allowance holds a draft object: it is unreadable, not an answer."""
    import judge_read
    rows = [{"prompt_id": "c1", "group": "g", "label": "refutes", "abstain": False, "parse_failure": None, "length_reached_allowance": True},
            {"prompt_id": "c2", "group": "g", "label": "refutes", "abstain": False, "parse_failure": None, "length_reached_allowance": False}]
    tool = _tool()
    with patch.object(tool, "_comparator_rows", lambda value, by_prompt, records: [dict(r) for r in rows]):
        got = judge_read.b1_rows({}, {}, {})
    return [(r["label"], r["abstain"]) for r in got]


def expected_j1_truncated():
    return [(None, True), ("refutes", False)]


# ---- neutralisations ----------------------------------------------------------------------

def rule_text_dropped():
    tool = _tool()
    real = tool.render_user
    return patch.object(tool, "render_user", lambda config, *, document, rule_text: real(config, document=document, rule_text=""))


def dispatch_skipped():
    import replay_prompts
    return patch.object(replay_prompts, "is_doc_judge", lambda path: False)


def system_turn_sent():
    """The pass sends a system turn, as B1 does."""
    tool = _tool()
    real = tool.run

    def wrapped(*a, **k):
        factory = tool.make_backend

        def with_system(reader, context):
            backend = factory(reader, context)
            generate = backend.generate
            backend.generate = lambda system, user, n: generate("fixture system", user, n)
            return backend
        with patch.object(tool, "make_backend", with_system):
            return real(*a, **k)
    return patch.object(tool, "run", wrapped)


def quote_unchecked():
    tool = _tool()
    real = tool.screen
    return patch.object(tool, "screen", lambda parsed, document, config: real(parsed, document, dict(config, quote_required_for=[])))


def silence_as_detection():
    tool = _tool()
    real = tool.view_class

    def flagging(row, view):
        cls, source = real(row, view)
        return ("FLAG", source) if source == "silence" else (cls, source)
    return patch.object(tool, "view_class", flagging)


def scorer_as_b3():
    import score_corpus
    real = score_corpus.benchmark_items
    return patch.object(score_corpus, "benchmark_items", lambda key, run_dir, arm="B3": real(key, run_dir))


def key_read_here():
    """doc_judge reads the key's item table itself."""
    tool = _tool()
    import score_corpus

    def reading(key_path):
        key = json.loads(Path(key_path).read_text(encoding="utf-8"))
        doc_id = key["document"].rsplit(".", 1)[0]
        return {"document_id": doc_id, "benchmark": key["benchmark"],
                "items": [{"item_id": i["item_id"], "rule_id": i["rule_id"], "document_id": doc_id,
                           "benchmark": key["benchmark"]} for i in key["items"]]}
    real = tool._score_corpus

    def module():
        sc = real()
        shim = type("Shim", (), {})()
        for name in ("benchmark_labels", "_adapter_for", "key_digest"):
            setattr(shim, name, getattr(sc, name))
        shim.item_table = reading
        return shim
    return patch.object(tool, "_score_corpus", module)


def comparator_without_system():
    """The pass drops B1's system turn."""
    tool = _tool()
    real = tool.run

    def wrapped(*a, **k):
        factory_now = tool.make_backend

        def strip(reader, context):
            backend = factory_now(reader, context)
            generate = backend.generate
            backend.generate = lambda system, user, n: generate(None, user, n)
            return backend
        with patch.object(tool, "make_backend", strip):
            return real(*a, **k)
    return patch.object(tool, "run", wrapped)


def raw_unit_ids():
    """quote_units hands back the headings' own ids, which no key holds."""
    tool = _tool()
    return patch.object(tool.units, "unit_id", lambda k: "P-%05d" % k)


def digest_unpinned():
    return patch.object(_tool(), "BAR_ITEMS_SHA256", "0" * 64)


def figure_edges_ignored():
    return patch.object(_tool(), "_inside", lambda content, edge, step: False)


def evidence_words_ignored():
    return patch.object(_tool(), "BAR_EVIDENCE_WORDS", 0)


def evidence_overlap_is_enough():
    return patch.object(_tool(), "_all_evidence", lambda units, evidence: bool(set(units or ()) & set(evidence or ())))


def strict_reader():
    import json as module
    real = module.loads

    def strict(text, **k):
        k.pop("strict", None)
        return real(text, **k)
    return patch.object(_tool().json, "loads", strict)


def any_file_blocks():
    return patch.object(_tool(), "_no_verdict_yet", lambda out: not (Path(out) / "g1_scores.json").exists())


def markers_kept():
    tool = _tool()
    return patch.object(tool, "content_text", lambda document, config: tool.normalise(document))


def _always(name):
    return lambda: patch.object(_tool(), name, lambda *a, **k: True)


def comparator_needs_nothing():
    """--b1 is dropped from the build, so nothing is refused and no comparator is added."""
    tool = _tool()
    real = tool.build
    return patch.object(tool, "build", lambda workloads, out, b1=False, **k: real(workloads, out, **k))


def left_out_ignored():
    tool = _tool()
    real = tool.score
    return patch.object(tool, "score", lambda judgements, keys, out, bar_items=None: real(judgements, keys, out))


def chance_ignored():
    return patch.object(_tool(), "BAR_CHANCE", 1.0)


def strata_pooled():
    """The chance test forgets the tables: one pool, as a plain hypergeometric."""
    tool = _tool()
    real = tool.chance_tail

    def pooled(strata, correct):
        return real([[sum(s[k] for s in strata) for k in range(3)]], correct)
    return patch.object(tool, "chance_tail", pooled)


def manifest_unchecked():
    return patch.object(_tool(), "bar_refusal", lambda per_group, manifest: None)


def bar_any_benchmark():
    """Every row passes, whatever its conditions."""
    tool = _tool()
    real = tool.bar_row

    def lenient(mine, b1, benchmark=None):
        row = real(mine, b1, benchmark)
        return dict(row, passes=True, state="met")
    return patch.object(tool, "bar_row", lenient)


def sealer_dispatch_removed():
    import replay_prompts
    import doc_judge
    return patch.object(doc_judge, "is_prompts_file", lambda value: False)


# ---- the suite ----------------------------------------------------------------------------

class DocJudgeChecks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        result = prove_effect(name=name, validate=lambda: (BASELINES / "doc_judge.py").is_file(), observe=observe,
                              check=lambda: ("PASS" if observe() == expected() else "FAIL", name),
                              neutralise=neutralise)
        DocJudgeChecks.evidence.append(result)

    def test_build_renders_each_rule_once_per_group(self):
        """Neutralised: the template is filled without the rule's own text."""
        self.prove("build", observe_build, expected_build, rule_text_dropped)

    def test_the_sealed_replay_pass_runs_g1(self):
        """Neutralised: replay_prompts.py's run does not hand the file to doc_judge."""
        self.prove("sealed_pass", observe_pass, expected_pass, dispatch_skipped)

    def test_one_user_turn_only(self):
        """Neutralised: the pass sends a system turn."""
        self.prove("user_turn_only", observe_pass, expected_pass, system_turn_sent)

    def test_the_quote_rule_refuses(self):
        """Neutralised: no outcome requires a quote."""
        self.prove("quote_rule", observe_judge, expected_judge, quote_unchecked)

    def test_scores_through_the_scorer(self):
        """Neutralised: the scorer labels the folder as a B3 run."""
        self.prove("scores_b1_path", observe_scores, expected_scores, scorer_as_b3)

    def test_silence_is_never_a_detection(self):
        """Neutralised: silence is read as a FLAG."""
        self.prove("silence_apart", observe_scores, expected_scores, silence_as_detection)

    def test_the_key_is_read_only_by_the_scorer(self):
        """Neutralised: doc_judge reads the key's item table itself."""
        self.prove("key_reads", observe_key_reads, expected_key_reads, key_read_here)

    def test_the_real_render_sends_one_user_turn_for_none(self):
        """Neutralised: bare_model._render's None branch reverted (a system message always)."""
        self.prove("real_render", observe_render, expected_render, render_none_branch_reverted)

    def test_the_comparator_sends_b1s_own_turns(self):
        """Neutralised: the pass drops B1's system turn."""
        self.prove("comparator", observe_comparator, expected_comparator, comparator_without_system)

    def test_the_comparator_is_scored_and_an_item_left_out(self):
        """Neutralised: the items file is not passed to the scorer."""
        self.prove("comparator_scores", observe_comparator_scores, expected_comparator_scores, left_out_ignored)

    def test_the_bar_refuses_a_flagger_at_chance(self):
        """Neutralised: the chance limit is lifted."""
        self.prove("bar_chance", observe_bar, expected_bar, chance_ignored)

    def test_the_bar_conditions_on_each_table(self):
        """Neutralised: the chance test pools the tables."""
        self.prove("bar_strata", observe_bar, expected_bar, strata_pooled)

    def test_a_run_of_other_items_gets_no_verdict(self):
        """Neutralised: the scored items are not held to the decision's."""
        self.prove("bar_items", observe_comparator_scores, expected_comparator_scores, manifest_unchecked)

    def test_a_quote_finds_the_key_form_of_its_unit(self):
        """Neutralised: quote_units returns the headings' own ids."""
        self.prove("quote_units", observe_units, expected_units, raw_unit_ids)

    def test_a_flag_quoting_the_evidence_counts_end_to_end(self):
        """Neutralised: quote_units returns the headings' own ids, so no quote matches a key."""
        self.prove("evidence_end_to_end", observe_comparator_scores, expected_comparator_scores, raw_unit_ids)

    def test_the_real_items_file_is_the_pinned_one(self):
        """Neutralised: another digest is pinned."""
        self.prove("real_items", observe_real_items, expected_real_items, digest_unpinned)

    def test_a_piece_of_a_figure_is_no_quote(self):
        """Neutralised: a quote's edges are not read."""
        self.prove("quote_edges", observe_quotes, expected_quotes, figure_edges_ignored)

    def test_a_marker_is_no_quote(self):
        """Neutralised: the markers stay in the text a quote is read against."""
        self.prove("quote_markers", observe_quotes, expected_quotes, markers_kept)

    def test_only_the_pinned_items_file_gets_a_verdict(self):
        """Neutralised: any file counts as pinned."""
        self.prove("guard_pin", observe_comparator_scores, expected_comparator_scores, _always("_pinned"))

    def test_a_changed_config_gets_no_verdict(self):
        """Neutralised: the repository's config and B1 prompt are not compared."""
        self.prove("guard_repository", observe_comparator_scores, expected_comparator_scores, _always("_matches_repository"))

    def test_a_missing_model_gets_no_verdict(self):
        """Neutralised: the models are not compared with the config."""
        self.prove("guard_groups", observe_comparator_scores, expected_comparator_scores, _always("_same_groups"))

    def test_other_keys_get_no_verdict(self):
        """Neutralised: the keys are not compared with the items file."""
        self.prove("guard_keys", observe_comparator_scores, expected_comparator_scores, _always("_same_keys"))

    def test_other_prompts_get_no_verdict(self):
        """Neutralised: the prompts are not compared with the items file."""
        self.prove("guard_prompts", observe_comparator_scores, expected_comparator_scores, _always("_same_prompts"))

    def test_the_b1_prompt_is_held_to_its_digest(self):
        """Neutralised: load_prompts does not read the digest."""
        self.prove("guard_b1_prompt", observe_comparator_scores, expected_comparator_scores, _always("_b1_prompt_holds"))

    def test_a_score_with_no_verdict_blocks_nothing(self):
        """Neutralised: any file in the folder blocks."""
        self.prove("guard_stale", observe_comparator_scores, expected_comparator_scores, any_file_blocks)

    def test_condition_4_wants_three_words(self):
        """Neutralised: any length counts."""
        self.prove("evidence_words", observe_evidence_rule, expected_evidence_rule, evidence_words_ignored)

    def test_condition_4_wants_every_unit_to_be_evidence(self):
        """Neutralised: overlap with the evidence is enough."""
        self.prove("evidence_units", observe_evidence_rule, expected_evidence_rule, evidence_overlap_is_enough)

    def test_a_raw_newline_in_a_quote_is_read(self):
        """Neutralised: the reader stays strict."""
        self.prove("reader", observe_reader, expected_reader, strict_reader)

    def test_the_first_score_stands(self):
        """Neutralised: a folder holding a verdict is written again."""
        self.prove("guard_first", observe_comparator_scores, expected_comparator_scores, _always("_no_verdict_yet"))

    def test_a_stopped_pass_stays_readable(self):
        """Neutralised: the measurement is written only at the end."""
        self.prove("stopped_readable", observe_stopped, expected_stopped, lambda: patch.object(_tool(), "_save_progress", lambda out, value: None))

    def test_a_stopped_pass_gets_no_verdict(self):
        """Neutralised: an unfinished pass counts as finished."""
        self.prove("stopped_no_verdict", observe_stopped, expected_stopped, _always("_finished"))

    def test_the_command_line_takes_the_comparator(self):
        """Neutralised: --b1 is dropped."""
        self.prove("cli", observe_cli, expected_cli, comparator_needs_nothing)

    def test_the_bar_needs_every_condition(self):
        """Neutralised: every row passes."""
        self.prove("bar_conditions", observe_bar, expected_bar, bar_any_benchmark)

    def test_a_candidate_stops_on_its_own_tokens(self):
        """Neutralised: the backend's frozen stop ids stay, other tokens in another vocabulary."""
        self.prove("j1_stops", observe_j1, expected_j1, lambda: patch.object(_tool(), "own_stops", lambda decoding, group: decoding))

    def test_each_group_gets_its_own_form(self):
        """Neutralised: the agent's note is dropped."""
        self.prove("j1_note", observe_j1, expected_j1, lambda: patch.object(_tool(), "agent_user", lambda config, group, user: user))

    def test_the_direct_group_loses_b1s_reasoning_line(self):
        """Neutralised: B1's system turn stays as shipped in both groups."""
        self.prove("j1_direct", observe_j1, expected_j1, lambda: patch.object(_tool(), "comparator_system", lambda config, group, system: system))

    def test_a_model_that_never_stops_is_stopped_early(self):
        """Neutralised: the stop is never reached."""
        self.prove("j1_early", observe_j1_stop, expected_j1_stop, lambda: patch.object(_tool(), "EARLY_STOP", 10 ** 6))

    def test_the_reasoning_is_never_read_as_the_answer(self):
        """Neutralised: the first JSON object is read, the reasoning's own."""
        import bare_model


        def first(text):
            if "{" not in text:
                return None
            start = text.index("{")
            try:
                return text[start:start + json.JSONDecoder().raw_decode(text[start:])[1]]
            except ValueError:
                return text[start:]
        self.prove("j1_last", observe_j1_reading, expected_j1_reading, lambda: patch.object(bare_model, "_last_balanced_object", first))

    def test_a_kept_answer_goes_through_the_pipelines_refusal(self):
        """Neutralised: nothing is refused."""
        import paired_review
        self.prove("j1_refusal", observe_j1_reading, expected_j1_reading, lambda: patch.object(paired_review, "judged_item_refusal", lambda *a, **k: None))

    def test_silence_is_no_detection_in_j1(self):
        """Neutralised: a silent call is read as clear."""
        import judge_read
        real = judge_read.item_class
        self.prove("j1_silence", observe_j1_reading, expected_j1_reading,
                   lambda: patch.object(judge_read, "item_class", lambda calls: ("CLEAR", "kept_claim") if "SILENT" in calls else real(calls)))

    def test_j1_refuses_a_judge_that_flags_everything(self):
        """Neutralised: every item may be flagged, as C1's replies were."""
        import judge_read
        self.prove("j1_varies", observe_j1_reading, expected_j1_reading, lambda: patch.object(judge_read, "MAX_FLAGGED", 1.0))

    def test_strict_keeps_only_what_the_pipeline_would(self):
        """Neutralised: a record outside the declared relations is kept as a finding."""
        import finding_record
        self.prove("j1_strict", observe_j1_reading, expected_j1_reading, lambda: patch.object(finding_record, "is_finding", lambda item: True))

    def test_j1_reads_end_to_end_with_every_guard(self):
        """Neutralised: nothing is refused."""
        import judge_read
        self.prove("j1_guards", observe_j1_end_to_end, expected_j1_end_to_end, lambda: patch.object(judge_read, "refusal", lambda *a: None))

    def test_a_truncated_b1_reply_is_unreadable(self):
        """Neutralised: its draft object is read as the answer."""
        import judge_read
        self.prove("j1_truncated", observe_j1_truncated, expected_j1_truncated,
                   lambda: patch.object(judge_read, "b1_rows", lambda value, by_prompt, records: _tool()._comparator_rows(value, by_prompt, records)))

    def test_the_sealer_and_runner_take_the_file(self):
        """Neutralised: replay_prompts.load_prompts no longer knows a G1 file."""
        self.prove("sealing", observe_sealing, expected_sealing, sealer_dispatch_removed)


def check():
    DocJudgeChecks.evidence = []
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DocJudgeChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(case).split(" ")[0] + ": " + str(err).strip().splitlines()[-1][:200]
                    for case, err in list(result.failures) + list(result.errors)]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass: G1 prompts built once per model group, document "
                    "and rule from the rule's own text with no filled example; run through the sealed replay pass as one "
                    "user turn, one reply record with its text per prompt, counted by the runner and named by the analyser; "
                    "the quote rule refuses a missing or unfound quote, one that is not the document's content, an unparseable reply and an undeclared outcome; "
                    "scored through tools/score_corpus.py (label_b1) with silence apart, never a detection; the key opened "
                    "only by the scorer; the file sealed as a replay pass of --paths sdpa; the real LocalBackend._render sends one user turn for a None system turn and both turns for B1's; "
                    "the comparator sends B1's own turns with B1's allowance and is scored by the same path; the bar's "
                    "conditions hold on hand-made figures" % len(DocJudgeChecks.evidence))


if __name__ == "__main__":
    status, detail = check()
    print(status, detail)
    sys.exit(0 if status == "PASS" else 1)
