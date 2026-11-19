"""Score-time re-readers of saved raw replies (D-663, standing order 82, #279; lead 15 November 18:57).

No answer is dropped for its form alone. The runtime parsers live in bound files (benchmark/baselines/,
scripts/: every sealed bundle carries them), so they stay as they are until the next re-seal; the tolerant
reading happens here, at scoring, on the replies each pass saved in its reply records, the same way for every
arm (system, B1, cloud):

- `advisor`: the negotiation advisor's pass folder (or the cloud reference's {prompt id: text} file) read
  again into an answers file of schema ADVISOR_SCHEMA, every row carrying its drops by field and reason;
- `negotiation`: the negotiation B1 pass folder (or the cloud file) read again into NEGOTIATION_SCHEMA rows,
  each movement row carrying its drop reason;
- `b1`: a B1 pass folder's labels read again from their reply records into a NEW folder, the frozen parser
  first and the form reading only where it read no label.

Every form reading is tools/answer_form.py's: form only, never content (WORDS-A). The one JSON rule is the
LAST top-level object of a reply; a reply holding several is counted `several_objects_last_read`, never dropped. The
bound modules are imported read-only, for their prompt files, item ids and the frozen B1 parser. No text is
printed; outputs are written outside the repository where the bound module requires it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "tools"), str(ROOT / "scripts"), str(ROOT / "benchmark" / "baselines"),
           str(ROOT / "benchmark" / "adapters")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import answer_form as af  # noqa: E402

ADVISOR_SCHEMA = "neg-advisor-answers-v2"
NEGOTIATION_SCHEMA = "negotiation-answers-v2"
B1_RELABEL_FILE = "b1_relabel.json"
READ_BY = "tools/reread_replies.py (D-663)"


def _modules():
    import neg_advisor as na
    import negotiation_b1 as nb
    return na, nb


def _texts_of(run_dir, measurement_file, schema, prompts_sha256, what, text_of=None):
    """{prompt id: (row, text or None)} of a pass folder: each measurement row's reply text from its record
    (`text_of(record, row)` when given: the advisor's choice decisions are read as their settled label)."""
    import reply_records
    run_dir = Path(run_dir)
    measurement = json.loads((run_dir / measurement_file).read_text(encoding="utf-8"))
    if measurement.get("schema") != schema or measurement.get("prompts_sha256") != prompts_sha256:
        raise ValueError("the pass folder is not a %s pass of these prompts" % what)
    records = {r.get("call_id"): r for r in reply_records.records(run_dir / "audit" / "model_replies")}
    out = {}
    for row in measurement.get("rows") or []:
        record = records.get(row.get("call_id")) or {}
        if text_of is not None:
            out[row["prompt_id"]] = (row, text_of(record, row))
            continue
        reply = record.get("reply") or {}
        out[row["prompt_id"]] = (row, reply.get("text") if isinstance(reply, dict) and record.get("backend_ok") else None)
    return measurement, out


def _value_of(read_file, prompts_path):
    value = read_file(prompts_path)
    value["_sha256"] = hashlib.sha256(Path(prompts_path).read_bytes()).hexdigest()
    return value


# ---------------------------------------------------------------------------
# the negotiation advisor


def _object(text, drops):
    """The reply's last object, `several_objects_last_read` counted; None with its reason counted under `reply`."""
    value, why, several = af.last_object(text)
    if several:
        drops.add("reply", af.SEVERAL_OBJECTS)
    if value is None:
        drops.add("reply", why)
    return value


def _read(value, declared, field, drops):
    got, why = af.match(value, declared)
    if why:
        drops.add(field, why)
    return got


def _read_all(value, declared, field, drops):
    got, why = af.match_all(value, declared)
    for reason in why:
        drops.add(field, reason)
    return got


def _entries(value, field, drops):
    out = []
    for e in af.as_list(value):
        if isinstance(e, dict):
            out.append(e)
        else:
            drops.add(field, af.NOT_OBJECT)
    return out


_TRAILING_NUMBER = re.compile(r"(\d+)$")


def _cited(value, known):
    """(id, None) or (None, reason) of one cited id: by form (answer_form.match), and an integer n as the one
    known id whose trailing number is n ("3" as PAR-3), refused as ambiguous when two known ids end in n."""
    got, why = af.match(value, known)
    if got is not None:
        return got, None
    text, bad = af.one_value(value)
    if bad or not af.bare(text).isdigit():
        return None, bad or why
    n = int(af.bare(text))
    hits = sorted(k for k in known if _TRAILING_NUMBER.search(k) and int(_TRAILING_NUMBER.search(k).group(1)) == n)
    if len(hits) == 1:
        return hits[0], None
    return None, af.AMBIGUOUS if hits else af.NOT_DECLARED


def _basis(e, entry, field, drops):
    """D-711 item 1: an entry's `basis` by its form (one of neg_advisor.BASES) and its `basis_quote` as written
    (outer spaces off). A basis not read is counted and left out, so the entry is held as on record; the quote
    is checked against the item's text by the scorer's Python step, never here."""
    na, _ = _modules()
    if e.get("basis") is not None:
        got = _read(e["basis"], na.BASES, field + ".basis", drops)
        if got is not None:
            entry["basis"] = got
    quote, bad = af.one_value(e.get("basis_quote")) if e.get("basis_quote") is not None else (None, None)
    if bad:
        drops.add(field + ".basis_quote", bad)
    elif isinstance(quote, str) and quote.strip():
        entry["basis_quote"] = quote.strip()


def advice(text, item):
    """The advice reply read by the plan's section 5.1 schema, every field by its form (case, spaces, quotes,
    emphasis, punctuation, fences, a number for an id, a list of one and one value for a list, an integer
    reason as its one known id), the LAST object of the reply. None when there is no object. `drops` counts
    what is still not read, by field and reason; an entry with one bad field keeps its other fields."""
    na, _ = _modules()
    drops = af.Drops()
    value = _object(text, drops)
    if value is None:
        return None, drops.as_dict()
    if item.get("game"):
        options = {i["id"]: tuple(i["options"]) for i in item["game"]["issues"]}
        deal = value.get("deal") if isinstance(value.get("deal"), dict) else {}
        clean = {}
        for k, v in deal.items():
            issue = _read(k, options, "deal.issue", drops)
            option = _read(v, options[issue], "deal.option", drops) if issue is not None else None
            if option is not None:
                clean[issue] = option
        trades = []
        for t in _entries(value.get("trades"), "trades", drops):
            give, get = (_read(t.get(f), options, "trades." + f, drops) for f in ("give", "get"))
            if give is not None and get is not None:
                trades.append({"give": give, "get": get})
        return {"deal": clean, "trades": trades, "unknown_ids": drops.total()}, drops.as_dict()
    pars, poss, props, arts = na.item_ids(item)
    known_articles = arts | {r["id"] for r in item.get("previous_index") or []}
    parties = {p["id"] for p in item["parties"]}
    cited_ids = pars | poss | props | arts
    proposals, unknown = {}, 0
    for e in _entries(value.get("proposals"), "proposals", drops):
        pid = _read(e.get("id"), props, "proposals.id", drops)
        if pid is None or pid in proposals:
            if pid is not None:
                drops.add("proposals.id", af.DUPLICATE)
            unknown += 1
            continue
        reasons = []
        for r in af.as_list(e.get("reasons")):
            got, why = _cited(r, cited_ids)
            if got is None:
                raw, bad = af.one_value(r)
                if bad:
                    drops.add("proposals.reasons", bad)
                    continue
                got = raw   # kept as written: the scorer judges a reason outside the item
            if got not in reasons:
                reasons.append(got)
        entry = {"id": pid, "reasons": reasons}
        for f, declared in (("conflict", na.CONFLICT), ("stance", na.STANCES)):
            if e.get(f) is not None:
                got = _read(e[f], declared, "proposals." + f, drops)
                if got is not None:
                    entry[f] = got
        if isinstance(e.get("wording"), str) and e["wording"].strip():
            entry["wording"] = e["wording"].strip()
        _basis(e, entry, "proposals", drops)
        if isinstance(e.get("rationale"), str) and e["rationale"].strip():
            entry["rationale"] = e["rationale"].strip()   # D-713 reason_first: kept apart, never scored
        proposals[pid] = entry
    trades = []
    for t in _entries(value.get("trades"), "trades", drops):
        give, get = (af.one_value(t.get(f)) for f in ("give", "get"))
        if give[1] or get[1]:
            drops.add("trades", give[1] or get[1])
            continue
        trades.append({"give": af.bare(give[0]), "get": af.bare(get[0])})
    approach = _read_all(value.get("approach"), parties, "approach", drops)
    alignment = {}
    for e in _entries(value.get("alignment"), "alignment", drops):
        aid = _read(e.get("article"), arts, "alignment.article", drops)
        if aid is None:
            unknown += 1
            continue
        alignment[aid] = {"aligned": _read_all(e.get("aligned"), parties, "alignment.aligned", drops),
                          "opposed": _read_all(e.get("opposed"), parties, "alignment.opposed", drops)}
        _basis(e, alignment[aid], "alignment", drops)
    state = {}
    for e in _entries(value.get("state"), "state", drops):
        aid = _read(e.get("article"), known_articles, "state.article", drops)
        if aid is None:
            unknown += 1
            continue
        said = _read(e.get("state"), na.STATES, "state.state", drops)
        if said is not None:
            state[aid] = said
    return ({"proposals": proposals, "trades": trades, "approach": approach, "alignment": alignment,
             "state": state, "unknown_ids": unknown}, drops.as_dict())


def audit(text, config):
    """(label, None) or (None, reason): the audit reply's leading answer against the declared spellings."""
    spellings = {s: label for label, ss in config["audit"]["answers"].items() for s in ss}
    got, why = af.leading(text, tuple(spellings))
    return (spellings[got], None) if got is not None else (None, why)


_GRADE = re.compile(r"([012])(?![0-9])")


def judge(text):
    """(grade, None) or (None, reason): the leading digit 0, 1 or 2 (plan section 6.3), after the reply's
    form (fence lines, quotes, emphasis) and a leading field label ("Grade: 2") are taken off."""
    if not isinstance(text, str) or not text.strip():
        return None, af.EMPTY
    lines = [line for line in af.unfence(text).splitlines() if line.strip()]
    first = af.bare(lines[0]) if lines else ""
    for candidate in (first, af.bare(af._LABEL.sub("", first, count=1))):
        found = _GRADE.match(candidate)
        if found:
            return int(found.group(1)), None
    return None, af.NOT_DECLARED


NO_PROPOSAL = ("none", "null")   # the validate prompt writes a missing proposal as "none"; JSON writes null


def validate(text):
    """({article, proposal, stance}, None) or (None, reason): the validator's last object, by form: an article
    written as a number is its text, a proposal written as digits is that integer and "none" or "null" is no
    proposal, the stance one of the declared stances. The scorer matches the article to the item's ids."""
    na, _ = _modules()
    drops = af.Drops()
    value = _object(text, drops)
    if value is None:
        return None, next(iter(drops.counts["reply"]))
    article, why = af.one_value(value.get("article"))
    if why:
        return None, why
    article = af.bare(article)
    if not article:
        return None, af.EMPTY
    stance, why = af.match(value.get("stance"), na.POSITION_STANCES)
    if why:
        return None, why
    proposal = af.single(value.get("proposal"))
    if isinstance(proposal, str):
        written = af.key(proposal)
        proposal = None if written in NO_PROPOSAL else int(written) if written.isdigit() else proposal
    if proposal is not None and type(proposal) is not int:
        return None, af.NOT_TEXT
    return {"article": article, "proposal": proposal, "stance": stance}, None


def advisor_rows(value, texts, *, measured_audits=None, composed=None):
    """{schema, prompts_sha256, rows} as neg_advisor.answers_from_texts writes them, each row read by the
    readers above and carrying `drops`. A system advice's audits are matched to the audit prompts the run
    derived (neg_advisor.audit_prompts, the run's own rule, held to the SHA-256 the pass recorded); a piece
    read here that the run never audited is counted `not_asked` under `audit`. A step-wise prompt (S0) has no
    reply text: its reply is the one Python composed from its checked steps (`composed`: prompt id to
    (reply, steps), neg_advisor.stepwise_replies), each refused step counted under `steps` by step and reason,
    and its audits read and counted the same way."""
    na, _ = _modules()
    config = value["config"]
    rows = []
    for p in value["prompts"]:
        text = texts.get(p["prompt_id"])
        row = {"prompt_id": p["prompt_id"], "group": p["group"], "form": p["form"], "item_id": p["item_id"]}
        if p.get("stance_context") is not None:
            # D-756 item 5 (P8): the arm a stepwise prompt was built in, so a scorer never mixes the two arms.
            row["stance_context"] = p["stance_context"]
        if p["form"] == "advice":
            chain = (composed or {}).get(p["prompt_id"])
            if chain is None:
                reply, found = advice(text, p["item"])
                drops = af.Drops().merge(found)
            else:
                reply, drops = chain[0], af.Drops()
                refused = {}
                for s in chain[1]:
                    if s["refused"]:
                        # Counted in the drop share under the declared reason; the step and its own reason as
                        # neg_advisor.answers writes them (`steps_refused`).
                        drops.add("steps", af.STEP_REFUSED)
                        name = "%s:%s" % (s["step"], s["refused"])
                        refused[name] = refused.get(name, 0) + 1
                row.update(method=na.STEPWISE, steps=len(chain[1]), steps_refused=dict(sorted(refused.items())))
            row.update(reply=reply)
            if p["group"] == "system_advice":
                audits, flips = {}, {}
                for d in (na.audit_prompts(config, p, text) if chain is None else na.audit_prompts(config, p, None, reply)):
                    sha, said = (measured_audits or {}).get(d["prompt_id"], (None, None))
                    if sha is not None and sha != d["user_sha256"]:
                        raise ValueError("an audit prompt the pass ran is not the rendering of its advice: %s" % d["prompt_id"])
                    label, why = audit(said, config) if sha is not None else (None, None)
                    if why:
                        drops.add("audit", why)
                    if d.get("kind") == na.CONFLICT_AUDIT:
                        # P5 (lane/neg-optional): the second family's answer on one candidate, kept apart.
                        flips[(d["proposal_id"], d["position_id"])] = label
                    else:
                        audits[d["proposal_id"]] = label
                for pid, piece in sorted(((reply or {}).get("proposals") or {}).items()):
                    if pid not in audits and "stance" in piece and "conflict" in piece:
                        drops.add("audit", af.NOT_ASKED)
                row["audit"] = audits
                if flips:
                    row["reply"], counts = na.auditor_flip(reply, flips)
                    row["auditor_flip"] = dict(sorted(counts.items()))
            row["drops"] = drops.as_dict()
        elif p["form"] == "judge":
            grade, why = judge(text)
            row.update(entry_id=p["entry"]["entry_id"], arm=p["entry"]["arm"], proposal_id=p["entry"]["proposal_id"],
                       grade=grade, drops={"grade": {why: 1}} if why else {})
        else:
            mapping, why = validate(text)
            row.update(position_id=p["position"]["id"], mapping=mapping, drops={"mapping": {why: 1}} if why else {})
        rows.append(row)
    return {"schema": ADVISOR_SCHEMA, "read_by": READ_BY, "prompts_sha256": value.get("_sha256"), "rows": rows}


def advisor_answers(prompts_path, run_dir, out=None):
    """A system or B1 advisor pass folder read again (as neg_advisor.answers, with the readers above)."""
    na, _ = _modules()
    value = _value_of(na.read_file, prompts_path)
    measurement, rows = _texts_of(run_dir, na.MEASUREMENT_FILE, na.MEASUREMENT_SCHEMA, value["_sha256"],
                                  "negotiation advisor",
                                  text_of=lambda record, row: na.recorded_text(record, value["config"], row.get("form")))
    texts, audits = {}, {}
    for pid, (row, text) in rows.items():
        if row.get("form") == "audit":
            audits[pid] = (row.get("user_sha256"), text)
        else:
            texts[pid] = text
    result = advisor_rows(value, texts, measured_audits=audits,
                          composed=na.stepwise_replies(value, run_dir, measurement))
    result["models"] = measurement.get("models")
    if out:
        na._write_json(na.outside_repository(out), result)
    return result


def advisor_answers_from_texts(prompts_path, texts_path, out=None):
    """The cloud reference's replies to B1's prompts ({prompt id: text}) read again the same way."""
    na, _ = _modules()
    value = _value_of(na.read_file, prompts_path)
    if any(p["group"] != "b1" for p in value["prompts"]):
        raise ValueError("the cloud reference answers B1's prompts only")
    result = advisor_rows(value, json.loads(Path(texts_path).read_text(encoding="utf-8")))
    result["subset_sha256"] = value.get("subset_sha256")
    if out:
        na._write_json(na.outside_repository(out), result)
    return result


def drop_counts(answers, group=None):
    """{field: {reason: count}} over an answers file's rows, of one group when given."""
    drops = af.Drops()
    for r in answers.get("rows") or []:
        if group is None or r.get("group") == group:
            drops.merge(r.get("drops") or {})
    return drops.as_dict()


# ---------------------------------------------------------------------------
# negotiation movement (B1 and the cloud reference)


def movement(reply, config):
    """(label, None) or (no_answer, reason): the reply's leading answer against each answer's `accepted`
    spellings and its own declared `line`, by form (fence lines, spaces, case, quotes, emphasis, punctuation,
    a leading field label). Never a near word (WORDS-A)."""
    _, nb = _modules()
    spellings = {}
    for a in config["movement"]["answers"]:
        for s in list(a["accepted"]) + [a["line"]]:
            spellings[s] = a["label"]
    got, why = af.leading(reply, tuple(spellings))
    if got is None and isinstance(reply, str):
        whole, _ = af.match(" ".join(af.unfence(reply).split()), tuple(spellings))
        got = whole
    return (spellings[got], None) if got is not None else (nb.NO_ANSWER, why)


def negotiation_rows(value, texts):
    """{schema, prompts_sha256, rows} as negotiation_b1.answers_from_texts writes them, movement rows read by
    `movement` and carrying `drop`; suggestion rows by the system's own reader, unchanged."""
    _, nb = _modules()
    config = value["config"]
    sconfig = {"suggestion": value["suggestion"]}
    rows = []
    for p in value["prompts"]:
        text = texts.get(p["prompt_id"])
        row = {"prompt_id": p["prompt_id"], "group": p["group"], "form": p["form"], "case_id": p["case_id"],
               "issue_id": p["issue_id"]}
        if p["form"] == "movement":
            label, why = movement(text, config)
            row.update(rounds=p["rounds"], label=label, drop=why)
        else:
            item, why = nb.read_suggestion(text, p["chosen"], sconfig)
            row.update(kept=item is not None, refusal=why,
                       suggested_wording=(item or {}).get("suggested_wording"), quote=(item or {}).get("quote"),
                       checks=(item or {}).get("checks"))
        rows.append(row)
    return {"schema": NEGOTIATION_SCHEMA, "read_by": READ_BY, "prompts_sha256": value.get("_sha256"), "rows": rows}


def negotiation_answers(prompts_path, run_dir, out=None):
    _, nb = _modules()
    value = _value_of(nb.read_file, prompts_path)
    _, rows = _texts_of(run_dir, nb.MEASUREMENT_FILE, nb.MEASUREMENT_SCHEMA, value["_sha256"], "negotiation B1")
    result = negotiation_rows(value, {pid: text for pid, (_row, text) in rows.items()})
    if out:
        nb._write_json(out, result)
    return result


def negotiation_answers_from_texts(prompts_path, texts_path, out=None, model_id=None):
    _, nb = _modules()
    value = _value_of(nb.read_file, prompts_path)
    result = negotiation_rows(value, json.loads(Path(texts_path).read_text(encoding="utf-8")))
    if model_id:
        result["model_id"] = model_id
    if out:
        nb._write_json(out, result)
    return result


# ---------------------------------------------------------------------------
# B1 labels


def b1_label(reply, bench, item_id=None):
    """The frozen parser's result (bare_model.parse_reply, unchanged); where it found no label it can read
    (`no_label`, `label_not_in_list`), the reply's last object's label read again by form (a list of one, a
    number as its text, quotes, emphasis, punctuation) and then by the frozen label rule, marked `form_read`.
    One still not read keeps the frozen failure and names `form_drop`."""
    import bare_model as bm
    out = dict(bm.parse_reply(reply, bench, item_id), form_read=False, form_drop=None)
    if out["parsed"] or out["failure"] not in ("no_label", "label_not_in_list"):
        return out
    obj, why, _several = af.last_object(reply)
    if obj is None:
        return dict(out, form_drop=why)
    written, why = af.one_value(obj.get("label"))
    if why:
        return dict(out, form_drop=why)
    read = bm._read_label(dict(out, failure=None), dict(obj, label=af.bare(written)), bench, item_id)
    if read["parsed"]:
        return dict(read, form_read=True, form_drop=None)
    return dict(out, form_drop=af.NOT_DECLARED)


def b1_relabel(run_dir, out_dir, spec=None):
    """Every label file of a B1 pass folder read again from its reply record through `b1_label`, written to
    `out_dir/labels/`, never into the pass. A failed call stays a backend failure; a reply whose text is not
    kept (a sensitive pass keeps only its SHA-256) is copied as it was and counted `reply_not_kept`. Returns
    the counts (labels, read_again, changed, form_read, reply_not_kept, parse failures by reason), also
    written to `out_dir/b1_relabel.json`."""
    import bare_model as bm
    run_dir, out_dir = Path(run_dir), Path(out_dir)
    if out_dir.resolve() == run_dir.resolve() or run_dir.resolve() in out_dir.resolve().parents:
        raise ValueError("relabel writes beside a pass folder, never into it")
    spec = spec or bm.load_prompt()
    labels, calls, _summary = bm._pass_folder(run_dir)
    counts = {"labels": 0, "read_again": 0, "changed": 0, "form_read": 0, "reply_not_kept": 0, "parse_failures": {}}
    for item_id, label in sorted(labels.items()):
        counts["labels"] += 1
        new = dict(label)
        record = calls.get(label.get("call_id")) or {}
        reply = record.get("reply") if isinstance(record.get("reply"), dict) else {}
        text = reply.get("text")
        bench = spec["benchmarks"][label["benchmark"]]
        if label.get("backend_ok") is False:
            parsed = dict(bm.parse_reply(None, bench), failure="backend_failure", form_read=False, form_drop=None)
        elif not isinstance(text, str):
            counts["reply_not_kept"] += 1
            parsed = None
        else:
            parsed = b1_label(text, bench, label.get("item_id"))
        if parsed is not None:
            counts["read_again"] += 1
            new.update({"label": parsed["label"], "abstain": not parsed["parsed"],
                        "undecided": bool(parsed["parsed"]) and bm._norm_label(parsed["label"]) == bm._norm_label(bench["undecided"]),
                        "parse_failure": parsed["failure"], "parse_repaired": parsed["repaired"],
                        "parse_truncated_object": parsed["truncated_object"],
                        "parse_form_read": parsed["form_read"], "parse_form_drop": parsed["form_drop"]})
            if "evidence_hashed" in label:
                new.update(evidence_hashed=bm._hashed(parsed["evidence"]), reason_hashed=bm._hashed(parsed["reason"]))
            else:
                new.update(evidence=parsed["evidence"], reason=parsed["reason"])
            counts["form_read"] += int(parsed["form_read"])
            if parsed["failure"] and not parsed["parsed"]:
                counts["parse_failures"][parsed["failure"]] = counts["parse_failures"].get(parsed["failure"], 0) + 1
        new["read_by"] = READ_BY
        counts["changed"] += int(new.get("label") != label.get("label"))
        bm._write_json(out_dir / "labels" / (str(item_id) + ".json"), new)
    counts["parse_failures"] = dict(sorted(counts["parse_failures"].items()))
    bm._write_json(out_dir / B1_RELABEL_FILE, dict(counts, source=run_dir.name, read_by=READ_BY))
    return counts


# ---------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("advisor", "negotiation"):
        s = sub.add_parser(name, allow_abbrev=False)
        s.add_argument("--prompts", required=True, type=Path)
        s.add_argument("--run", type=Path, help="a pass folder (B1 or the system)")
        s.add_argument("--texts", type=Path, help="the cloud reference's {prompt id: text} file")
        s.add_argument("--out", required=True, type=Path)
        if name == "negotiation":
            s.add_argument("--model-id", help="the cloud reference's model id, carried into its answers")
    b = sub.add_parser("b1", allow_abbrev=False)
    b.add_argument("--run", required=True, type=Path)
    b.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "b1":
            print(json.dumps(b1_relabel(args.run, args.out), indent=1, sort_keys=True))
            return 0
        if bool(args.run) == bool(args.texts):
            raise ValueError("give one of --run and --texts")
        if args.command == "advisor":
            result = (advisor_answers(args.prompts, args.run, args.out) if args.run
                      else advisor_answers_from_texts(args.prompts, args.texts, args.out))
        else:
            result = (negotiation_answers(args.prompts, args.run, args.out) if args.run
                      else negotiation_answers_from_texts(args.prompts, args.texts, args.out, args.model_id))
        print(json.dumps({"rows": len(result["rows"]), "drops": drop_counts(result) if args.command == "advisor"
                          else {k: v for k, v in sorted(_movement_drops(result).items())}}, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print("reread stopped: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 4


def _movement_drops(answers):
    out = {}
    for r in (answers or {}).get("rows") or []:
        if r.get("form") == "movement" and r.get("drop"):
            out[r["drop"]] = out.get(r["drop"], 0) + 1
    return out


if __name__ == "__main__":
    raise SystemExit(main())
