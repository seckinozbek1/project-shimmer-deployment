"""Two narrow model steps of a multi-round case, each behind an injected function (D-S39, D-S41).

Open item 35 (INC-023) took the free-form case call away: it asked for everything at once and
ran to its output cap. These two steps are the narrow opposite. Python selects exactly what is
asked about, the question's shape is fixed in config/case_questions.json, and the callable that
answers is injected, so no model is needed to prove anything here and which model answers is
decided outside this file. strategic_support.execute, the free-form path, is not used.

Toward or away. For each accepted movement record Python selects the party's two positions and
the other party's position they answer, and asks one fixed-answer question. `decide(question)`
returns {answer, confidence, settled}. A movement stays `unknown` unless the question is answered
and settled; an answered movement carries the literal answer in `movement_answer`, the value of
the record's own vocabulary in `movement`, and `movement_decided_by: model`. A failed call, a
reply of another shape or `cannot be settled` leaves it `unknown` and says why. With several
other parties, or none, nothing is asked: Python does not choose whose position is the measure.

Suggested wording. For each issue the case manifest declares `open`, for the one actor it declares
`supported`, Python selects that issue's stated positions and the passages of the last round's
units the issue declares in `text_units`, and one narrow call to `suggest(question)` asks for
wording. A suggestion is kept only when it cites at least one passage it was given and only such
passages. It is written by a model, marked so, never checked by Python and never an amendment:
nothing here can reach one, since a multi-round run writes none.

Every item says which it is: `written_by: python, provenance: computed` for what Python selected,
`written_by: model` for what a model answered. `run` with no callables asks nothing and still
returns Python's selections, each row saying why.

What answers. `agent` in config/case_questions.json names a registered agent, and that agent's
model is config/agent_registry.json's, the one owner of model choice. It is null until a decision
sets it. `multi_round_phase.case_question_calls` builds the callables through
`narrow_call.narrow_ask`, the masking and the audit trail of the pair call. `movement.form` says how a movement is asked:
`decision`, from the model's own probabilities in one forward pass (D-S41, a local backend only),
or `reply`, read from generated text. `not_asked` says what stops each step before any call: no
agent, and for a decision no measured threshold, or a backend that gives no probabilities.
"""
from copy import deepcopy
import json
from pathlib import Path

import choice_decision
import finding_record
import multi_round as mr
import pairing_map
import passage_pairs
import reviewed_document
from run_context import DELIVERABLE_FILENAMES
import version_changes

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "case_questions.json"
RECORD_NAME = "case_questions.json"
DELIVERABLE_KEY = "case_positions"
MODEL_MARK = finding_record.MODEL_FINDING_MARK
DECISION_FORM, REPLY_FORM = "decision", "reply"
COMPUTED = {"written_by": "python", "provenance": "computed"}


def load_config(path=CONFIG_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def agent_of(config):
    """The registered agent that answers, or None: the one place this is read."""
    return config.get("agent") or None


def deciding(config):
    form = config["movement"].get("form", DECISION_FORM)
    if form not in (DECISION_FORM, REPLY_FORM):
        raise ValueError("config/case_questions.json: movement.form is decision or reply")
    return form == DECISION_FORM


def threshold_of(config):
    return choice_decision.threshold(config["movement"]["decision"]["threshold_family"])


def not_asked(config, *, gives_probabilities):
    """{step: why} for each step that must ask nothing, before any call. A decision with no
    measured threshold could only come back unsettled, so it is not asked, as in cell_selection."""
    if agent_of(config) is None:
        return {"movements": "no_agent", "suggestions": "no_agent"}
    if deciding(config) and not gives_probabilities:
        return {"movements": "no_probabilities_on_this_backend"}
    if deciding(config) and threshold_of(config) is None:
        return {"movements": "no_threshold"}
    return {}


def call_movement(wrapper, stable, dynamic, config, budget):
    """The one model call on a movement question, already masked."""
    if deciding(config):
        return wrapper.call_choice(stable + ("\n\n" + dynamic if dynamic else ""),
                                   config["movement"]["decision"]["answers"], threshold_of(config))
    return wrapper.dispatch(stable, dynamic, **budget)


def answer_of(result, config=None):
    """What `ask` hands back: the decision or the reply's text, None for a failed call."""
    if not getattr(result, "ok", False):
        return None
    return result.parsed if config is not None and deciding(config) else result.raw_text


def outcome_of(result, config=None):
    """The reply record's outcome of one call."""
    if not getattr(result, "ok", False):
        return "backend_failure"
    return "decided" if config is not None and deciding(config) else "free_text"


def decider(ask, seen, config):
    """`decide(question)` over `ask(prompt)`, in the shape ask_movements reads."""
    if not deciding(config):
        return generated_decide(ask, config)

    def decide(question):
        decision = ask(question["text"])
        if decision is None:
            return None
        return {"answer": decision["decided"], "confidence": decision["confidence"], "settled": decision["settled"],
                "model": seen.get("model"), "why": decision.get("why"), "declared_mass": decision.get("declared_mass")}
    return decide


def suggester(ask):
    """`suggest(question)` over `ask(prompt)`."""
    return lambda question: ask(question["text"])


def _failure_limit(config):
    return config["max_failures_in_a_row"]


def _rounds(manifest):
    return {r["round_id"]: r["sequence"] for r in manifest["rounds"]}


def _positions(record):
    return [r for r in record["records"] if r["kind"] == "position" and r["state"] == "accepted"]


def _other_position(record, movement):
    """(position, None) of the other party that the later statement answers: its latest at or
    before the earlier round, else its latest up to the later one. (None, reason) otherwise."""
    order = _rounds(record["manifest"])
    others = [p for p in _positions(record) if p["issue_id"] == movement["issue_id"]
              and p["actor_id"] != movement["actor_id"]]
    if len({p["actor_id"] for p in others}) > 1:
        return None, "several_other_parties"
    before = [p for p in others if order[p["round_id"]] <= order[movement["previous_round_id"]]]
    upto = [p for p in others if order[p["round_id"]] <= order[movement["round_id"]]]
    held = before or upto
    if not held:
        return None, "no_other_position"
    return max(held, key=lambda p: order[p["round_id"]]), None


def movement_question(movement, earlier, later, other, config):
    fixed = config["movement"]
    text = (fixed["template"].replace("{earlier}", earlier["position"]).replace("{later}", later["position"])
            .replace("{other}", other["position"]))
    return {"question_id": movement["record_id"], "text": text, "options": list(fixed["options"]),
            "issue_id": movement["issue_id"], "actor_id": movement["actor_id"],
            "other_actor_id": other["actor_id"], "round_before": movement["previous_round_id"],
            "round_after": movement["round_id"],
            "position_ids": [earlier["record_id"], later["record_id"], other["record_id"]]}


def _read_decision(reply, options):
    """(answer, confidence, settled, model), or None when the reply is not of the agreed shape."""
    if not isinstance(reply, dict) or reply.get("answer") not in options or type(reply.get("settled")) is not bool:
        return None
    confidence = reply.get("confidence")
    if confidence is not None and type(confidence) not in (int, float, str):
        return None
    return reply["answer"], confidence, reply["settled"], reply.get("model")


def _settled(answer, settled, config):
    return settled and answer in config["movement"]["record_value"]


def _apply(movement, answer, confidence, model, config):
    movement.update(movement=config["movement"]["record_value"][answer], movement_answer=answer,
                    movement_confidence=confidence, movement_decided_by="model",
                    movement_model=model or "not recorded", written_by="model", provenance="model_decided",
                    category="semantic_interpretation", checked_by_python=False, mark=MODEL_MARK)


def ask_movements(record, decide, config, why_not=None):
    """Asks each accepted movement once, in order, and returns one outcome row each. Changes only
    the movements answered and settled. `decide` None asks nothing, for the reason `why_not`."""
    by_id = {r["record_id"]: r for r in record["records"]}
    limit, streak, out = _failure_limit(config), 0, []
    for movement in [r for r in record["records"] if r["kind"] == "movement"]:
        row = dict(COMPUTED, movement_id=movement["record_id"], issue_id=movement["issue_id"],
                   actor_id=movement["actor_id"], round_before=movement["previous_round_id"],
                   round_after=movement["round_id"])
        out.append(row)
        if movement["state"] != "accepted":
            row["outcome"] = "not_asked_positions_not_accepted"
            continue
        other, reason = _other_position(record, movement)
        if other is None:
            row["outcome"] = "not_asked_" + reason
            continue
        question = movement_question(movement, by_id[movement["previous_position_id"]],
                                     by_id[movement["current_position_id"]], other, config)
        row.update(position_ids=question["position_ids"], other_actor_id=other["actor_id"])
        if decide is None:
            row["outcome"] = "not_asked_" + (why_not or "no_decider")
            continue
        if streak >= limit:
            row["outcome"] = "not_asked_stopped_after_failures"
            continue
        reply = None
        try:
            reply = decide(deepcopy(question))
            read = _read_decision(reply, question["options"])
        except Exception as exc:  # a failed call is recorded by its type, never fatal to the case
            read, row["error_type"] = None, type(exc).__name__
        if read is None:
            streak += 1
            row["outcome"] = "failed"
            continue
        streak = 0
        answer, confidence, settled, model = read
        row.update(answer=answer, confidence=confidence, written_by="model", provenance="model_decided",
                   model=model or "not recorded", mark=MODEL_MARK)
        row.update({k: reply[k] for k in ("why", "declared_mass") if k in reply})
        if _settled(answer, settled, config):
            _apply(movement, answer, confidence, model, config)
            row["outcome"] = "decided"
        else:
            row["outcome"] = "not_settled"
    return out


def _plain(text):
    return " ".join(str(text or "").split())


def check_quotes(record, documents, rows):
    """Each asked movement row's quotes, the positions Python put to the model, checked in Python
    against the text of the round each was stated in. A model's answer is shown only beside quotes
    that stand there; one whose quotes do not is refused and leaves the movement unknown."""
    texts = {d.get("id"): _plain(d.get("text")) for d in documents or [] if isinstance(d, dict)}
    sources = {s["source_id"]: s for s in record["evidence"]}
    records = {r["record_id"]: r for r in record["records"]}
    for row in rows:
        if "position_ids" not in row:
            continue
        quotes = [sources[sid] for pid in row["position_ids"] for sid in records[pid]["source_ids"]]
        row["quotes_checked"] = all(_plain(s["quote"]) in texts.get(s["document_id"], "") for s in quotes)
        if not row["quotes_checked"] and row.get("outcome") == "decided":
            movement = records.get(row["movement_id"])
            if movement is not None:
                movement["movement"] = "unknown"
                for key in ("movement_answer", "movement_confidence", "movement_decided_by", "movement_model", "mark"):
                    movement.pop(key, None)
                movement.update(written_by="python", provenance="computed", category="observed_evidence")
            row["outcome"] = "refused_quotes_not_in_round"


def generated_decide(generate, config):
    """A `decide` for a model that can only generate text: `generate(prompt) -> text`. Same shape
    as the fixed-answer call: an answer is read only when the reply names exactly one option as a
    JSON field, or is that option alone. Anything else cannot be settled."""
    def decide(question):
        reply = generate(question["text"] + "\n" + config["movement"]["generated_suffix"])
        if reply is None:   # a failed call, not an unclear answer
            return None
        answer = _answer_in(str(reply), question["options"])
        unsettled = config["movement"]["unsettled_answer"]
        if answer is None:
            return {"answer": unsettled, "confidence": None, "settled": False}
        return {"answer": answer, "confidence": None, "settled": answer != unsettled}
    return decide


def _answer_in(reply, options):
    text = reply.strip().strip('."').lower()
    if text in options:
        return text
    value = _object(reply)
    answer = value.get("answer") if isinstance(value, dict) else None
    return answer if answer in options else None


def _object(reply):
    if isinstance(reply, dict):
        return reply
    text = passage_pairs._without_fences(str(reply or ""))
    found = passage_pairs._last_balanced_object(text)
    try:
        return json.loads(found) if found else None
    except ValueError:
        return None


# ---- suggested wording -------------------------------------------------------------------------

def supported_party(manifest):
    """The one actor the manifest declares `supported`, or None."""
    held = [a["actor_id"] for a in manifest["actors"] if a.get("supported") is True]
    return held[0] if len(held) == 1 else None


def open_issues(manifest):
    return [i for i in manifest["issues"] if i.get("open") is True]


def _last_round_passages(record, documents, issue):
    """The passages of the last round's units the issue declares, with their document and unit."""
    wanted = set(issue.get("text_units") or [])
    last = max(record["manifest"]["rounds"], key=lambda r: r["sequence"])
    docs = {d.get("id"): d for d in documents or [] if isinstance(d, dict)}
    out = []
    for doc_id in last.get("document_ids") or []:
        if doc_id not in docs:
            continue
        units = [u for u in pairing_map.split_units(docs[doc_id].get("text", ""), document_id=doc_id)
                 if u["unit_id"].split("-", 1)[-1] in wanted]
        held = [(item["unit_id"], item["text"]) for item in passage_pairs.document_passages(units)]
        # A table is no sentence, and in a schedule it is the text the issue turns on.
        held += [(u["unit_id"], " | ".join(row)) for u in units
                 for head, rows in version_changes._tables(u.get("text", "")) for row in [head] + rows]
        out += [{"document_id": doc_id, "unit_id": unit_id, "round_id": last["round_id"], "text": text,
                 "kind": "text"} for unit_id, text in held]
    return out


def selection(record, documents, party, issue):
    """Python's part for one open issue: the stated positions in round order, and the passages."""
    order = _rounds(record["manifest"])
    stated = sorted((s for s in record["evidence"] if s["issue_id"] == issue["issue_id"]),
                    key=lambda s: (order[s["round_id"]], s["actor_id"]))
    passages = [{"document_id": s["document_id"], "unit_id": s["unit_id"], "round_id": s["round_id"],
                 "actor_id": s["actor_id"], "text": s["quote"], "ref_id": s["ref_id"], "kind": "position"}
                for s in stated] + _last_round_passages(record, documents, issue)
    for n, p in enumerate(passages, start=1):
        p["passage_id"] = "P%d" % n
    last = max(record["manifest"]["rounds"], key=lambda r: r["sequence"])["round_id"]
    return dict(COMPUTED, item="selection", issue_id=issue["issue_id"], party=party, passages=passages,
                last_round=last, position=issue.get("position") or "", fallback=issue.get("fallback") or "",
                closed_units=list(issue.get("closed_units") or []))


def suggestion_question(chosen, config):
    fixed = config["suggestion"]
    lines = "\n".join("%s (%s): %s" % (p["passage_id"], p.get("actor_id") or "text of the last round", p["text"])
                      for p in chosen["passages"])
    text = (fixed["template"].replace("{party}", chosen["party"]).replace("{issue}", chosen["issue_id"])
            .replace("{position}", chosen.get("position") or "not declared")
            .replace("{fallback}", chosen.get("fallback") or "not declared")
            .replace("{round}", chosen.get("last_round") or "").replace("{passages}", lines))
    return {"question_id": "suggestion." + chosen["issue_id"], "text": text, "issue_id": chosen["issue_id"],
            "party": chosen["party"], "passage_ids": [p["passage_id"] for p in chosen["passages"]]}


def _cites_ok(cites, known):
    return isinstance(cites, list) and bool(cites) and len(set(map(str, cites))) == len(cites) \
        and all(c in known for c in cites)


def _bounds(chosen):
    """(low, high, measure) when the party's position and fallback are each one figure in one
    measure, else None: then whether the wording stays inside them is the checker's to judge."""
    import paired_review
    found = [paired_review.quantities(chosen.get(k) or "") for k in ("position", "fallback")]
    if any(len(f) != 1 or not f[0][1] for f in found):
        return None
    measures = {paired_review._unit_str(paired_review.unit_exponents(f[0][1])) for f in found}
    if len(measures) != 1:
        return None
    values = [f[0][0] for f in found]
    return min(values), max(values), measures.pop()


def inside_position(wording, chosen):
    """True or False when Python can tell, from the figures in the party's own measure; else
    "not_computable"."""
    import paired_review
    bounds = _bounds(chosen)
    if bounds is None:
        return "not_computable"
    low, high, measure = bounds
    figures = [v for v, unit, *_ in paired_review.quantities(wording)
               if unit and paired_review._unit_str(paired_review.unit_exponents(unit)) == measure]
    if not figures:
        return "not_computable"
    return all(low <= v <= high for v in figures)


def read_suggestion(reply, chosen, config):
    """(item, None), or (None, why it was refused). The wording is never repaired. Python checks what
    it can (D-S46 item 3): the quote stands in a passage of this round the suggestion cites; no cited
    passage is in text both sides recorded as agreed; a figure in the party's own measure lies
    between its declared position and fallback. The rest is the rubric's checker's."""
    value = _object(reply)
    fixed = config["suggestion"]
    if not isinstance(value, dict):
        return None, "not_an_object"
    wording, why = value.get("suggested_wording"), value.get("why")
    if not isinstance(wording, str) or not wording.strip() or len(wording) > fixed["max_wording_chars"]:
        return None, "wording_missing_or_too_long"
    if not isinstance(why, str) or not why.strip() or len(why) > fixed["max_why_chars"]:
        return None, "reason_missing_or_too_long"
    passages = {p["passage_id"]: p for p in chosen["passages"]}
    if not _cites_ok(value.get("cites"), passages):
        return None, "citation_not_given"
    if any(" ".join(wording.split()) == " ".join(p["text"].split()) for p in passages.values()):
        return None, "repeats_a_passage"
    cited = [passages[c] for c in value["cites"]]
    quote = value.get("quote")
    this_round = [p for p in cited if p["round_id"] == chosen.get("last_round")]
    if not isinstance(quote, str) or not quote.strip():
        return None, "quote_missing"
    if not this_round:
        return None, "no_citation_from_this_round"
    if not any(_plain(quote) in _plain(p["text"]) for p in this_round):
        return None, "quote_not_in_this_round"
    closed = set(chosen.get("closed_units") or [])
    if any(p.get("kind") == "text" and str(p["unit_id"]).split("-", 1)[-1] in closed for p in cited):
        return None, "reopens_agreed_text"
    inside = inside_position(wording, chosen)
    if inside is False:
        return None, "outside_position_and_fallback"
    return {"item": "suggestion", "quote": quote.strip(),
            "checks": {"quote_in_this_round": True, "agreed_text_left_alone": True, "inside_position": inside}, "issue_id": chosen["issue_id"], "party": chosen["party"],
            "suggested_wording": wording.strip(), "why": why.strip(), "written_by": "model",
            "provenance": "model_written", "checked_by_python": False, "promoted": False, "mark": MODEL_MARK,
            "model": value.get("model") or "not recorded",
            "citations": [passages[c] for c in value["cites"]]}, None


def ask_suggestions(record, documents, suggest, config, why_not=None, on_kept=None):
    """One narrow call per open issue. Returns [selection or suggestion or outcome rows]. `on_kept`
    hears the question of each suggestion kept: a kept one ends as a model's, never promoted."""
    party = supported_party(record["manifest"])
    if party is None:
        return [dict(COMPUTED, item="outcome", outcome="no_supported_party_declared")]
    out, streak = [], 0
    for issue in open_issues(record["manifest"]):
        chosen = selection(record, documents, party, issue)
        out.append(chosen)
        row = dict(COMPUTED, item="outcome", issue_id=issue["issue_id"])
        out.append(row)
        question = suggestion_question(chosen, config)
        if suggest is None:
            row["outcome"] = "not_asked_" + (why_not or "no_suggester")
        elif len(question["text"]) > config["suggestion"]["max_prompt_chars"]:
            row["outcome"] = "not_asked_too_long"
        elif streak >= _failure_limit(config):
            row["outcome"] = "not_asked_stopped_after_failures"
        else:
            try:
                reply = suggest(deepcopy(question))
                item, why = (None, "call_failed") if reply is None else read_suggestion(reply, chosen, config)
            except Exception as exc:  # recorded by its type, never fatal to the case
                item, why = None, "call_failed_" + type(exc).__name__
            if item is None:
                streak += 1
                row.update(outcome="failed" if str(why).startswith("call_failed") else "refused", reason=why)
            else:
                streak = 0
                row["outcome"] = "suggested"
                out.append(item)
                if on_kept is not None:
                    on_kept(question)
    return out


def run(record, documents, decide=None, suggest=None, config=None, why_not=None, on_kept=None):
    """Both steps on a case record. Answered movements change `record["records"]`, which are
    validated again; everything else is the returned layer. `why_not` is `not_asked`'s."""
    config = config or load_config()
    why_not = why_not or {}
    movements = ask_movements(record, decide, config, why_not.get("movements"))
    check_quotes(record, documents, movements)
    mr.validate_records(record["manifest"], record["evidence"], record["records"])
    support = ask_suggestions(record, documents, suggest, config, why_not.get("suggestions"), on_kept)
    failed = sum(r.get("outcome") == "failed" for r in movements + support)
    return {"schema_version": 1, "asked": {"movements": decide is not None, "suggestions": suggest is not None},
            "failed": failed, "movements": movements, "support": support}


def _escape(text):
    return reviewed_document._escape(text)


def _line(text):
    """Text this file did not write, a document's or a model's, on one line and escaped as the
    reviewed document escapes it (READABLE-A): none of it can open a quotation, raw HTML or bold,
    or read as one of this file's own lines."""
    return _escape(str(text).replace("\r", " ").replace("\n", " "))


def render(layer):
    """The one renderer of this layer. Every line says whose it is."""
    out = ["# Positions and suggested wording",
           "Lines marked Computed were selected by Python from the case's declared sources. "
           "Lines marked Model were written by a model and checked by no one. Nothing here is an amendment."]
    out.append("## Gap between the parties")
    out.append("Computed: in two consecutive rounds, the gap between the parties on an issue, where each quote states "
               "one figure in the unit the case declares for the issue, or, for an issue with no declared unit, where "
               "the parties' quotes are the same sentence with only the figure changed. Nothing is computed from words.")
    for row in layer.get("gaps") or []:
        head = "- %s, rounds %s to %s:" % (row["issue_id"], row["rounds"][0], row["rounds"][1])
        if row["outcome"] == "not_computed":
            out.append("%s Computed: not computed (%s)." % (head, _line(row["why"])))
        else:
            if row.get("read_by") == "declared_unit":
                out.append("%s Computed: %s, the gap went from %g to %g %s (the unit declared for the issue)." % (
                    head, row["outcome"], row["gaps"][0], row["gaps"][1], _line(row["measure"])))
            else:
                out.append("%s Computed: %s, the gap went from %g to %g; all four quotes read \"%s\" with only the "
                           "figure changed." % (head, row["outcome"], row["gaps"][0], row["gaps"][1], _line(row["measure"])))
    out.append("## Movement between rounds")
    for row in layer["movements"]:
        head = "- %s, %s, rounds %s to %s:" % (row["actor_id"], row["issue_id"], row["round_before"], row["round_after"])
        if row["outcome"] in ("decided", "not_settled"):
            out.append("%s Model: %s (%s; quotes checked against the round text). %s" % (
                head, _line(row.get("answer")), row["outcome"], MODEL_MARK))
        else:
            out.append("%s Computed: movement unknown (%s)." % (head, row["outcome"]))
    party = next((i.get("party") for i in layer["support"] if i.get("party")), None)
    out.append("## Suggested wording for %s" % (party or "no declared party"))
    for item in layer["support"]:
        if item["item"] == "selection":
            out.append("### %s" % item["issue_id"])
            out.append("Computed: passages selected.")
            out += ["- %s, %s, %s, %s: %s" % (p["passage_id"], p["round_id"], p.get("actor_id") or "text",
                                              p["unit_id"], _line(p["text"])) for p in item["passages"]]
        elif item["item"] == "suggestion":
            out.append("Model: suggested wording. %s" % MODEL_MARK)
            out.append("> %s" % _line(item["suggested_wording"]))
            out.append("Model: the passage it rests on, quoted. %s" % _line(item.get("quote", "")))
            checks = item.get("checks") or {}
            out.append("Computed: the quote stands in this round's text; no agreed text is cited; inside the "
                       "party's position and fallback: %s." % {True: "yes", "not_computable": "not computable from "
                       "figures, for the checker"}.get(checks.get("inside_position"), "not checked"))
            out.append("Model: why. %s" % _line(item["why"]))
            out.append("Cited: %s" % ", ".join(c["passage_id"] for c in item["citations"]))
        else:
            out.append("Computed: %s%s." % (item["outcome"], " (%s)" % item["reason"] if item.get("reason") else ""))
    return "\n\n".join(out) + "\n"


def write(ctx, layer, record):
    """audit/case_questions.json, and one deliverable in the last round's first document's folder."""
    audit = ctx.audit_dir() / RECORD_NAME
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(json.dumps(layer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    last = max(record["manifest"]["rounds"], key=lambda r: r["sequence"])
    folder = ctx.doc_deliverables_dir(last["document_ids"][0])
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / DELIVERABLE_FILENAMES[DELIVERABLE_KEY]
    path.write_text(render(layer), encoding="utf-8", newline="\n")
    return path
