"""#309 (D-847, D-848): the difference check between a source text and a proposed text.

A post step, never a phase of a review: it reads texts a run already wrote, asks narrow questions and
writes its own marked record. It changes no prompt, answer, finding, amendment or score
(docs/fix/DIFF_CHECK_309.md section 1.2), and nothing in a sealed bundle imports it.

Python's part is structure only (WORDS-A). Both texts are split into sentences by the project's one
splitter (`passage_pairs.passages_read`); a sentence standing in both is no change; the leftovers are
paired by word similarity with ties refused (`version_changes._paired`), giving changed, removed and
added sentences, and inside a changed pair the words removed and added are listed (difflib). Nothing in
this file reads what a word means.

The model's part is the meaning, as narrow fixed-answer questions to the JUDGE agent decided from its
probabilities (CHOICE-A): per change, one question per declared kind (tools/diff_check.json `kinds`:
the operator's four of D-847) and one per red line of the advised party (D-848), each "is this
statement true of this change? Yes, No, Unclear". One question per kind, since one change can be two
kinds. A flag is a settled Yes; with no measured threshold nothing settles. The judge writes no text:
every quote on a record is a span Python placed, checked to stand in the text it names before the record
is kept. Every record is a model's: marked with finding_record.MODEL_FINDING_MARK, promoted false,
checked_by_python false, and never an amendment or a finding.

    align(source, proposed, config)                 [change]: changed, removed, added sentences
    replacement(unit_text, line, config)            [change]: an amendment's proposed line against its unit
    amendment_pairs(review_data)                    pairs from amendments carrying a proposed_text
    version_change_pairs(record)                    pairs from audit/version_changes.json (already aligned)
    negotiation_pairs(item, parsed)                 pairs from counter wordings (neg_advisor)
    red_lines_from_item(item)                       the advised party's red lines on the record
    declared_red_lines(rows)                        red lines the user declares (#278)
    questions(change, red_lines, config)            the questions of one change
    check(pairs, red_lines, judge, config)          the record; `judge(text, answers)` gives a decision
    write_run(run_dir, judge, red_lines, config)    the post step on a finished run folder
    replay_prompts(set_path, out, config)           the accuracy set as a doc_judge choice prompts file

    py -3.12 -X utf8 tools/diff_check.py replay --set benchmark/fixtures/diff_check_309/accuracy_set.json --out P
    py -3.12 -X utf8 tools/diff_check.py score --set S --prompts P --run PASS --out F   (no model)
"""
import argparse
import copy
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "benchmark" / "baselines", ROOT / "benchmark" / "adapters"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import finding_record  # noqa: E402
import passage_pairs  # noqa: E402
import version_changes  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().with_suffix(".json")
CONFIG_SCHEMA = "diff-check-config-v1"
SCHEMA = "diff-check-v1"
RECORD_NAME = "diff_check.json"
DELIVERABLE_NAME = "diff_check.md"
SET_SCHEMA = "diff-check-set-v1"
BENCHMARK = "diff309"
RED_LINE = "red_line"
CHANGED, REMOVED, ADDED = "changed", "removed", "added"
MARK = finding_record.MODEL_FINDING_MARK
SPANS_NOTE = "Python placed the sentences and checked each quote stands in its text; which kind of change it is, is the model's answer."
LINE_HEAD = "Difference check (#309, added after the run): "
_SLOT = re.compile(r"\{(passage_a|passage_b)\}")


class DiffCheckRefused(ValueError):
    """A configuration or an input the check cannot run as declared."""


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_config(path=CONFIG_PATH):
    value = json.loads(Path(path).read_text(encoding="utf-8")) if not isinstance(path, dict) else path
    return check_config(value)


def check_config(value):
    if not isinstance(value, dict) or value.get("schema") != CONFIG_SCHEMA:
        raise DiffCheckRefused("not a diff_check config (%s)" % CONFIG_SCHEMA)
    if type(value.get("enabled")) is not bool:
        raise DiffCheckRefused("the switch `enabled` is true or false")
    t = value.get("threshold")
    if t is not None and not (type(t) in (int, float) and 0 <= t <= 1):
        raise DiffCheckRefused("a threshold is a probability or null")
    kinds = value.get("kinds")
    if not isinstance(kinds, list) or not kinds or len({k.get("kind") for k in kinds}) != len(kinds) \
            or any(not (isinstance(k.get("kind"), str) and isinstance(k.get("statement"), str) and k["statement"].strip())
                   for k in kinds) or RED_LINE in {k["kind"] for k in kinds}:
        raise DiffCheckRefused("each kind is declared once with its statement")
    template = value.get("template")
    if not isinstance(template, str) or sorted(m.group(1) for m in _SLOT.finditer(template)) != ["passage_a", "passage_b"]:
        raise DiffCheckRefused("the template fills {passage_a} (the statement) and {passage_b} (the change) once each")
    if "{party}" not in value.get("red_line_statement", "") or "{quote}" not in value["red_line_statement"]:
        raise DiffCheckRefused("the red-line statement names {party} and {quote}")
    import choice_decision
    choice_decision.declare(template, value.get("answers"))
    if value.get("flag_label") not in {a["label"] for a in value["answers"]}:
        raise DiffCheckRefused("the flag label is one of the declared answers")
    return value


# ---- structure: where the texts differ ----------------------------------------------------------

def sentences(text):
    """[{start, end, text}] of `text` by the project's one splitter."""
    found, _ = passage_pairs.passages_read(text)
    return [{"start": p["start"], "end": p["end"], "text": p["text"]} for p in found]


def words_changed(before, after):
    """(words removed, words added) between two sentences, in order: structure only."""
    a, b = before.split(), after.split()
    removed, added = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op in ("replace", "delete"):
            removed.append(" ".join(a[i1:i2]))
        if op in ("replace", "insert"):
            added.append(" ".join(b[j1:j2]))
    return removed, added


def _change(kind, before, after):
    row = {"change": kind, "source": before, "proposed": after}
    if before and after:
        row["words_removed"], row["words_added"] = words_changed(before["text"], after["text"])
    return row


def align(source, proposed, config):
    """[change] between two whole texts: a sentence standing in both is no change; the leftovers are
    paired by similarity, a tie refused (both then stand as removed and added)."""
    old, new = sentences(source), sentences(proposed)
    left_old, left_new = list(old), []
    for p in new:
        match = next((q for q in left_old if q["text"] == p["text"]), None)
        if match is not None:
            left_old.remove(match)
        else:
            left_new.append(p)
    pairs = version_changes._paired(left_old, left_new, config["min_sentence_similarity"])
    if not pairs and len(left_old) == 1 and len(left_new) == 1:
        # One sentence left on each side: it is the only partner either has, so they are one changed
        # sentence however few words they share (structure: no other pairing exists).
        pairs = [(0, 0)]
    out = [_change(CHANGED, left_old[i], left_new[j]) for i, j in pairs]
    gone, come = {i for i, _ in pairs}, {j for _, j in pairs}
    out += [_change(REMOVED, p, None) for i, p in enumerate(left_old) if i not in gone]
    out += [_change(ADDED, None, p) for j, p in enumerate(left_new) if j not in come]
    return out


def replacement(unit_text, line, config):
    """[change] for an amendment's proposed line: it replaces the one sentence of its unit most like it
    (a tie, or none alike enough, refused: then it stands as added). The rest of the unit is no change."""
    new = sentences(line) or ([{"start": 0, "end": len(line), "text": line.strip()}] if line.strip() else [])
    old = sentences(unit_text)
    if any(p["text"] == n["text"] for p in old for n in new):
        new = [n for n in new if all(p["text"] != n["text"] for p in old)]
    pairs = version_changes._paired(old, new, config["min_sentence_similarity"])
    out = [_change(CHANGED, old[i], new[j]) for i, j in pairs]
    come = {j for _, j in pairs}
    return out + [_change(ADDED, None, n) for j, n in enumerate(new) if j not in come]


# ---- where a source and a proposed text stand ---------------------------------------------------

def _pair(origin, ident, source, proposed, mode="whole", **extra):
    return dict({"origin": origin, "id": ident, "source_text": source, "proposed_text": proposed, "mode": mode}, **extra)


def amendment_pairs(review_data, doc_id=None):
    """Amendments carrying a proposed line (the --amendment-polish pass; none as shipped)."""
    out = []
    for n, a in enumerate((review_data or {}).get("amendments") or []):
        proposed = a.get("proposed_text") if isinstance(a, dict) else None
        if isinstance(proposed, str) and proposed.strip() and isinstance(a.get("original_text"), str):
            out.append(_pair("amendment", "%s:%s" % (doc_id or "document", a.get("ref") or n), a["original_text"], proposed,
                             mode="replacement", document_id=doc_id, unit_id=a.get("finding_unit_id")))
    return out


def version_change_pairs(record):
    """The changed, removed and added sentences of audit/version_changes.json, already aligned by Python."""
    out = []
    for c in (record or {}).get("comparisons") or []:
        for n, s in enumerate(c.get("sentences") or []):
            out.append(_pair("version_change", "%s>%s:%d" % (c.get("before"), c.get("after"), n),
                             (s.get("before") or {}).get("text") or "", (s.get("after") or {}).get("text") or "",
                             mode="aligned", aligned=s.get("change"), document_id=c.get("after"), unit_id=s.get("unit_id")))
    return out


def negotiation_pairs(item, parsed):
    """Each counter's wording against its proposal's text (neg_advisor.parse_advice, proposal_text)."""
    texts = {p["id"]: p["text"] for a in (item or {}).get("articles") or [] for p in a.get("proposals") or []}
    out = []
    for pid, entry in sorted(((parsed or {}).get("proposals") or {}).items()):
        if entry.get("stance") == "counter" and entry.get("wording") and pid in texts:
            out.append(_pair("negotiation_counter", pid, texts[pid], entry["wording"]))
    return out


def red_lines_from_item(item):
    """The advised party's red lines (D-848), read by the negotiation advisor's one reader,
    `neg_advisor.party_red_lines`: its positions the record marks in `persona.red_lines`, and the
    operator's (#278, `persona.operator_red_lines`, put there by `neg_advisor.py rebuild
    --operator-red-lines`), each by its own text and with its source."""
    import neg_advisor
    party = item["persona"]["id"]
    return [{"party": party, "quote": r["text"], "source": r["source"], "red_line_id": r["id"]}
            for r in neg_advisor.party_red_lines(item)]


def declared_red_lines(rows, config=None):
    """Red lines the user declares (#278): [{party, quote}] as given, nothing read from words."""
    out = []
    for r in rows or []:
        if not (isinstance(r, dict) and isinstance(r.get("party"), str) and r["party"].strip()
                and isinstance(r.get("quote"), str) and r["quote"].strip()):
            raise DiffCheckRefused("a declared red line is {party, quote}")
        out.append({"party": r["party"].strip(), "quote": r["quote"].strip(), "source": r.get("source") or "declared by the user"})
    return out


# ---- the questions -----------------------------------------------------------------------------

def change_block(change, config):
    nothing = config["nothing"]
    return config["change_block"].replace("{source}", (change["source"] or {}).get("text") or nothing) \
        .replace("{proposed}", (change["proposed"] or {}).get("text") or nothing)


def render(config, statement, block):
    """One pass over the template, as doc_judge.render_choice fills a choice pair form, so a text holding
    braces stays text and the replay's question is this one byte for byte."""
    slots = {"passage_a": statement, "passage_b": block}
    return _SLOT.sub(lambda m: slots[m.group(1)], config["template"])


def red_line_statement(config, line):
    return config["red_line_statement"].replace("{party}", line["party"]).replace("{quote}", line["quote"])


def questions(change, red_lines, config):
    """[{kind, statement, text}] of one change: each declared kind, and each red line on a change that
    leaves a proposed sentence (a removed sentence cannot break a line by what it says)."""
    block = change_block(change, config)
    out = [{"kind": k["kind"], "statement": k["statement"], "text": render(config, k["statement"], block)}
           for k in config["kinds"]]
    if change.get("proposed"):
        for n, line in enumerate(red_lines or []):
            statement = red_line_statement(config, line)
            out.append({"kind": RED_LINE, "red_line": n, "statement": statement, "text": render(config, statement, block)})
    return out


def _quote_holds(span, text):
    return span is None or (isinstance(span.get("start"), int) and text[span["start"]:span["end"]] == span["text"])


def check(pairs, red_lines, judge, config):
    """The record of every pair. `judge(text, answers)` returns a choice decision (choice_decision
    shape: decided, settled, confidence, answers); None asks nothing and records why."""
    import choice_decision
    rows, refused = [], []
    for pair in pairs:
        if pair["mode"] == "replacement":
            changes = replacement(pair["source_text"], pair["proposed_text"], config)
        elif pair["mode"] == "aligned":
            src = pair["source_text"] or None
            prop = pair["proposed_text"] or None
            changes = [_change(pair["aligned"], src and {"start": 0, "end": len(src), "text": src},
                               prop and {"start": 0, "end": len(prop), "text": prop})]
        else:
            changes = align(pair["source_text"], pair["proposed_text"], config)
        for n, change in enumerate(changes):
            if not (_quote_holds(change["source"], pair["source_text"]) and _quote_holds(change["proposed"], pair["proposed_text"])):
                refused.append({"pair": pair["id"], "change": n, "reason": "quote_not_in_text"})
                continue
            asked = []
            for q in questions(change, red_lines, config):
                row = {k: v for k, v in q.items() if k != "text"}
                row["question_sha256"] = _sha(q["text"])
                if judge is None:
                    row["outcome"] = "not_asked"
                else:
                    try:
                        decision = choice_decision.settle(judge(q["text"], config["answers"]), config["threshold"])
                    except choice_decision.ChoiceRefused as exc:
                        row["outcome"], row["reason"] = "refused", str(exc)
                    else:
                        row.update(outcome="decided", decided=decision["decided"], settled=decision["settled"],
                                   confidence=decision["confidence"], declared_mass=decision.get("declared_mass"),
                                   probabilities={a["label"]: a["probability"] for a in decision["answers"]})
                asked.append(row)
            flags = sorted({r["kind"] if r["kind"] != RED_LINE else "%s:%d" % (RED_LINE, r["red_line"])
                            for r in asked if r.get("settled") and r.get("decided") == config["flag_label"]})
            rows.append(dict({k: pair.get(k) for k in ("origin", "id", "document_id", "unit_id") if pair.get(k) is not None},
                             change=change["change"], source=change["source"], proposed=change["proposed"],
                             words_removed=change.get("words_removed"), words_added=change.get("words_added"),
                             questions=asked, flags=flags, written_by=finding_record.WRITTEN_BY_MODEL,
                             promoted=False, checked_by_python=False, mark=MARK))
    return {"schema": SCHEMA, "enabled": config["enabled"], "threshold": config["threshold"], "mark": MARK,
            "spans_note": SPANS_NOTE, "red_lines": red_lines or [], "pairs": len(pairs), "changes": rows,
            "refused": refused, "counts": counts(rows, refused)}


def counts(rows, refused=()):
    flagged = [r for r in rows if r["flags"]]
    asked = [q for r in rows for q in r["questions"]]
    return {"changes": len(rows), "flagged": len(flagged), "questions": len(asked),
            "settled": sum(1 for q in asked if q.get("settled")),
            "unsettled": sum(1 for q in asked if q.get("outcome") == "decided" and not q.get("settled")),
            "not_asked": sum(1 for q in asked if q.get("outcome") == "not_asked"),
            "refused": sum(1 for q in asked if q.get("outcome") == "refused") + len(list(refused))}


# ---- the deliverables --------------------------------------------------------------------------

def _esc(text):
    import reviewed_document
    return reviewed_document._escape(str(text or "").replace("\n", " "))


def render_md(record):
    c = record["counts"]
    out = ["# Difference check between the source and the proposed text (#309)", MARK, SPANS_NOTE,
           "Changes placed: %d. Flagged: %d. Questions asked: %d, settled %d, not settled %d, not asked %d, refused %d." % (
               c["changes"], c["flagged"], c["questions"], c["settled"], c["unsettled"], c["not_asked"], c["refused"])]
    if record["threshold"] is None:
        out.append("No threshold is measured for these questions, so none is settled and nothing is flagged.")
    for r in record["changes"]:
        lines = ["## %s %s, sentence %s" % (r["origin"], _esc(r["id"]), r["change"])]
        if r["source"]:
            lines.append("- Source: %s" % _esc(r["source"]["text"]))
        if r["proposed"]:
            lines.append("- Proposed: %s" % _esc(r["proposed"]["text"]))
        for q in r["questions"]:
            what = q["kind"] if q["kind"] != RED_LINE else "red line: " + _esc(record["red_lines"][q["red_line"]]["quote"])
            state = {"decided": "%s (%s, confidence %.2f)" % (q.get("decided"), "settled" if q.get("settled") else "not settled",
                                                              q.get("confidence") or 0.0),
                     "not_asked": "not asked", "refused": "refused: %s" % _esc(q.get("reason"))}[q["outcome"]]
            lines.append("- %s: %s. %s" % (what, state, MARK))
        out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


def summary_line(record):
    c = record["counts"]
    return "%s%d changes placed, %d flagged, %d of %d questions settled; see %s. %s" % (
        LINE_HEAD, c["changes"], c["flagged"], c["settled"], c["questions"], DELIVERABLE_NAME, MARK)


def _append_line(path, line):
    """One line at the end of a rendered file, the bytes before it kept; a line already there is not
    written twice."""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if LINE_HEAD in text:
        return False
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(("" if text.endswith("\n") else "\n") + "\n" + line + "\n")
    return True


def run_pairs(run_dir):
    """Every source and proposed text pair a finished run folder holds."""
    run_dir = Path(run_dir)
    pairs = []
    for data in sorted((run_dir / "deliverables").glob("*/review_data.json")):
        pairs += amendment_pairs(json.loads(data.read_text(encoding="utf-8")), data.parent.name)
    vc = run_dir / "audit" / version_changes.RECORD_NAME
    if vc.is_file():
        pairs += version_change_pairs(json.loads(vc.read_text(encoding="utf-8")))
    return pairs


def write_run(run_dir, judge, red_lines=(), config=None):
    """The post step: audit/diff_check.json, deliverables/<doc>/diff_check.md for each document with a
    pair (deliverables/diff_check.md for pairs of no document) and one line at the end of that
    document's reviewed_document.md and of _run_summary.md. Off: writes nothing and returns None."""
    config = config or load_config()
    if not config["enabled"]:
        return None
    run_dir = Path(run_dir)
    record = check(run_pairs(run_dir), list(red_lines or []), judge, config)
    audit = run_dir / "audit" / RECORD_NAME
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(json.dumps(record, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    written = [audit]
    docs = sorted({r.get("document_id") for r in record["changes"]}, key=lambda d: d or "")
    for doc in docs:
        mine = dict(record, changes=[r for r in record["changes"] if r.get("document_id") == doc],
                    counts=counts([r for r in record["changes"] if r.get("document_id") == doc]))
        folder = run_dir / "deliverables" / doc if doc else run_dir / "deliverables"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / DELIVERABLE_NAME).write_text(render_md(mine), encoding="utf-8", newline="\n")
        written.append(folder / DELIVERABLE_NAME)
        if doc and _append_line(folder / "reviewed_document.md", summary_line(mine)):
            written.append(folder / "reviewed_document.md")
    if _append_line(run_dir / "deliverables" / "_run_summary.md", summary_line(record)):
        written.append(run_dir / "deliverables" / "_run_summary.md")
    return written


def choice_judge(score_fn, encode):
    """`judge(text, answers)` on a local model: one forward pass, nothing generated (CHOICE-A). The
    threshold is applied by `check`, so the decision is made here with none."""
    import choice_decision

    def judge(text, answers):
        question = choice_decision.bind(choice_decision.declare(text, [{"label": a["label"], "surface": a["surface"]}
                                                                       for a in answers]), encode)
        return choice_decision.decide(score_fn, question, None)
    return judge


# ---- the accuracy set and its replay -----------------------------------------------------------

def load_set(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema") != SET_SCHEMA or not isinstance(value.get("pairs"), list) or not value["pairs"]:
        raise DiffCheckRefused("not a diff_check accuracy set (%s)" % SET_SCHEMA)
    kinds = {k["kind"] for k in load_config()["kinds"]} | {RED_LINE}
    seen = set()
    for p in value["pairs"]:
        if p.get("id") in seen or not all(isinstance(p.get(k), str) for k in ("id", "source", "proposed")) \
                or not isinstance(p.get("expected"), list) or set(p["expected"]) - kinds \
                or set(p.get("tolerated") or []) - kinds or set(p.get("tolerated") or []) & set(p["expected"]):
            raise DiffCheckRefused("a pair needs a unique id, its two texts and its expected kinds: %s" % p.get("id"))
        seen.add(p["id"])
    return value


def replay_config(config, base_path=ROOT / "benchmark" / "baselines" / "choice_judge_prompt.json"):
    """choice_judge_prompt.json with its choice forms replaced by this one question, and its first model
    group renamed to the declared group and agent: no model id is written by this file."""
    import doc_judge
    base = json.loads(Path(base_path).read_text(encoding="utf-8"))
    value = copy.deepcopy(base)
    group = dict(base["models"][0], **config["replay_group"])
    value["models"] = [group]
    value["choice"] = {"forms": {"pair": {"template": config["template"], "limit": 1,
                                          "answers": [dict(a) for a in config["answers"]]}}}
    value["note"] = "#309 accuracy pass (tools/diff_check.py replay): " + config["description"]
    return doc_judge.check_config(value)


def replay_prompts(set_path, out, config=None):
    """The accuracy set as a doc_judge prompts file of form choice, kind pair: one document per pair,
    holding each statement and each change block once, every question a span pair of it. Reads no
    expected kind: those stay in the set, read again only by `score`."""
    import doc_judge
    config = config or load_config()
    value = load_set(set_path)
    rconfig = replay_config(config)
    group = rconfig["models"][0]
    documents, prompts = {}, []
    for p in value["pairs"]:
        lines = declared_red_lines(p.get("red_lines"))
        changes = align(p["source"], p["proposed"], config)
        parts, spans = [], {}

        def put(key, text):
            start = sum(len(x) + 2 for x in parts)
            parts.append(text)
            spans[key] = [start, start + len(text)]
        for k in config["kinds"]:
            put(("s", k["kind"]), k["statement"])
        for n, line in enumerate(lines):
            put(("r", n), red_line_statement(config, line))
        for n, change in enumerate(changes):
            put(("c", n), change_block(change, config))
        text = "\n\n".join(parts)
        documents[p["id"]] = {"benchmark": BENCHMARK, "target": p["id"], "text": text, "sha256": doc_judge._sha(text),
                              "conventions": []}
        for n, change in enumerate(changes):
            for q in questions(change, lines, config):
                key = ("s", q["kind"]) if q["kind"] != RED_LINE else ("r", q["red_line"])
                kind_id = q["kind"] if q["kind"] != RED_LINE else "%s-%d" % (RED_LINE, q["red_line"])
                user = doc_judge.render_choice(rconfig, "pair", {"passage_a": text[slice(*spans[key])],
                                                                 "passage_b": text[slice(*spans[("c", n)])]})
                if user != q["text"]:
                    raise DiffCheckRefused("the replay's question is not the check's: %s" % p["id"])
                prompts.append({"form": doc_judge.CHOICE_FORM, "choice": "pair", "group": group["group"],
                                "backend": group["backend"], "agent": group["agent"], "checkpoint": group["checkpoint"],
                                "benchmark": BENCHMARK, "document_id": p["id"], "item_id": p["id"], "rule_id": kind_id,
                                "system": None, "max_new_tokens": 0, "user": user, "user_sha256": doc_judge._sha(user),
                                "pair_id": "%s-c%d" % (kind_id, n), "pair": [n, n], "order": "ab",
                                "span_a": spans[key], "span_b": spans[("c", n)], "change": change["change"]})
    for number, prompt in enumerate(prompts, 1):
        prompt["prompt_id"] = "d%06d" % number
    result = {"schema": doc_judge.SCHEMA, "kind": doc_judge.KIND, "config": rconfig,
              "config_sha256": doc_judge._sha(doc_judge._canonical(rconfig)), "documents": documents, "prompts": prompts,
              "prompt_count": len(prompts), "refused_claims": [], "cell_counts": {},
              "reads": "the accuracy set's texts and declared red lines only: no expected kind"}
    doc_judge._write_json(out, result)
    doc_judge.load_prompts(out)
    return result


def pass_decisions(prompts_path, run_dir):
    """{prompt_id: decision} of a complete replay pass of these prompts (pair_judge.finished_pass);
    a failed call has none."""
    import pair_judge
    value, seen, records = pair_judge.finished_pass(prompts_path, run_dir)
    out = {}
    for p in value["prompts"]:
        record = records.get((seen.get(p["prompt_id"]) or {}).get("call_id")) or {}
        if record.get("backend_ok") and isinstance(record.get("decision"), dict):
            out[p["prompt_id"]] = record["decision"]
    return out


def score(set_path, prompts_path, decisions, config=None):
    """Per kind: true and false flags against the declared kinds, from a pass's decisions
    ({prompt_id: choice decision}); a pair is flagged for a kind when any of its changes settles Yes.
    Development figures, never a bar."""
    import choice_decision
    config = config or load_config()
    value = load_set(set_path)
    prompts = json.loads(Path(prompts_path).read_text(encoding="utf-8"))["prompts"]
    flagged, asked = {}, {}
    for p in prompts:
        kind = RED_LINE if p["rule_id"].startswith(RED_LINE + "-") else p["rule_id"]
        asked.setdefault(p["item_id"], set()).add(kind)
        d = decisions.get(p["prompt_id"])
        if d and choice_decision.settle(d, config["threshold"])["decided"] == config["flag_label"]:
            flagged.setdefault(p["item_id"], set()).add(kind)
    table = {}
    for kind in [k["kind"] for k in config["kinds"]] + [RED_LINE]:
        row = {"true_flag": 0, "false_flag": 0, "missed": 0, "true_clear": 0}
        for pair in value["pairs"]:
            if kind not in asked.get(pair["id"], set()) or kind in (pair.get("tolerated") or []):
                continue
            want, got = kind in pair["expected"], kind in flagged.get(pair["id"], set())
            row[("true_flag" if want else "false_flag") if got else ("missed" if want else "true_clear")] += 1
        table[kind] = row
    return {"threshold": config["threshold"], "per_kind": table}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("replay")
    r.add_argument("--set", required=True)
    r.add_argument("--out", required=True)
    s = sub.add_parser("score")
    s.add_argument("--set", required=True)
    s.add_argument("--prompts", required=True)
    s.add_argument("--run", required=True, help="the complete replay pass folder of these prompts")
    s.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "replay":
        value = replay_prompts(args.set, args.out)
        print("prompts", value["prompt_count"], "documents", len(value["documents"]))
    else:
        result = score(args.set, args.prompts, pass_decisions(args.prompts, args.run))
        Path(args.out).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print("kinds", len(result["per_kind"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
