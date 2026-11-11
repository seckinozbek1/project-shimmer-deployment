"""The auditor backend's narrow questions (D-S57 item 1, D-S56 item 1, D-S62 item 3).

Each question is declared in config/auditor_questions.json: the evidence Python selects, a fixed
prompt with fixed answers, and what Python writes from each answer. The answer is read from the
model's own probabilities in one forward pass (choice_decision.py through
agent_wrapper.call_choice): the model writes no text, the quote on a record is Python's echo of the
evidence it selected, and the probabilities are on the call's reply record (REPLIES-A).

    rule_check       PRACTICE_AUDITOR's question on one unit and one rule where Python computed
                     no figure (plan kinds absence_judged and uncomputable): met (a rule whose
                     condition does not apply is met), not met, or cannot be settled, the three
                     classes of an inference set. A settled not met is a model-written Finding
                     record where the config maps it to a declared relation (missing_field on a
                     judged absence, naming the field Python finds absent), and none elsewhere.
    pair_fidelity    VERIFIER's question on one pair auditor_pairs.build made (a source span and
                     the producer item placed in it): MATCH, DIVERGENCE, OMISSION, ADDITION, or
                     cannot be settled. A settled answer is one VERIFIER item for its pair. Not
                     adopted: on the shipped path a pair shows no claim (the config says why).

Nothing is asked under a question until its form is `decision` and config/semantic_thresholds.json
holds its family's measured threshold (`asks`); until then each role runs as shipped. Adopting a
form is a recorded decision after the measurement.
"""
import json
import re
from pathlib import Path

import choice_decision

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "auditor_questions.json"
REPLY_FORM, DECISION_FORM = "reply", "decision"
QUESTIONS = ("rule_check", "pair_fidelity")
TOO_LARGE = "question_over_its_size"
NOT_ADOPTED = "form_reply"
NO_THRESHOLD = "no_measured_threshold"
AGENT_DIFFERS = "another_agent_judges_this_rule"
NO_RELATION_DECLARED = "not_met, but the record declares no relation for this plan kind"
NO_FIELD_NAMED = "not_met, but the rule's words name no single field the unit lacks"
DECIDED = "Decided from the model's own probabilities, no text written: %s (probability %.3f)."


def decided_sentence(label, decision):
    return DECIDED % (label, float((decision or {}).get("confidence") or 0.0))


def load_config(path=CONFIG_PATH):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema") != "auditor-questions-v1" or any(name not in value for name in QUESTIONS):
        raise ValueError("config/auditor_questions.json: schema auditor-questions-v1 with %s" % ", ".join(QUESTIONS))
    for name in QUESTIONS:
        form_of(value[name])
        choice_decision.declare("x", value[name]["decision"]["answers"])   # two or more distinct answers
    return value


def form_of(question):
    """How the question is asked. A value this code does not know is refused, never read as the default."""
    form = question.get("form", REPLY_FORM)
    if form not in (REPLY_FORM, DECISION_FORM):
        raise ValueError("config/auditor_questions.json: form is reply or decision")
    return form


def threshold_of(question):
    return choice_decision.threshold(question["decision"]["threshold_family"])


def not_asked(question, agent=None):
    """Why the decision form is not used for a call ('' when it is): the form is not adopted, no
    measured threshold exists, or the call's judging agent is not the question's."""
    if form_of(question) != DECISION_FORM:
        return NOT_ADOPTED
    if agent is not None and agent != question["agent"]:
        return AGENT_DIFFERS
    if threshold_of(question) is None:
        return NO_THRESHOLD
    return ""


def asks(question, agent=None):
    return not not_asked(question, agent)


def _fill(template, slots):
    """One pass over the template, so braces in the evidence stay as written."""
    return re.sub(r"\{(%s)\}" % "|".join(map(re.escape, slots)), lambda m: slots[m.group(1)], template)


def _sized(question, prompt):
    if len(prompt) > int(question["max_prompt_chars"]):
        raise choice_decision.ChoiceRefused(TOO_LARGE)
    return prompt


def applies_to(question, plan_kind):
    """True when the rule check is asked on a plan of this kind."""
    return plan_kind in (question.get("plan_kinds") or ())


def render_rule_check(question, rule_text, unit_text):
    """The rule check on one rule's own words and one unit's own text."""
    return _sized(question, _fill(question["decision"]["template"],
                                  {"rule": str(rule_text or "").strip(), "unit": str(unit_text or "").strip()}))


def extraction_text(producer_item):
    """The producer item as Auditor896 is shown it (auditor_pairs.predict): its semantic fields, as
    sorted JSON."""
    return json.dumps(producer_item, sort_keys=True, ensure_ascii=False)


def render_pair(question, source_text, producer_item):
    """The pair question on one source span and the producer item placed in it."""
    return _sized(question, _fill(question["decision"]["template"],
                                  {"source": str(source_text or "").strip(), "extraction": extraction_text(producer_item)}))


def answers(question):
    return question["decision"]["answers"]


def _settled_label(decision, question):
    """The settled answer's label, None for an unsettled decision or anything that is no decision
    of the declared answers."""
    if not isinstance(decision, dict) or not decision.get("settled"):
        return None
    labels = {a["label"] for a in answers(question)}
    label = decision.get("decided")
    return label if label in labels and label != choice_decision.UNSETTLED else None


def absent_named_field(rule_text, unit_text, vocabulary):
    """The one field label of the document's vocabulary that the rule's own words name and the unit
    does not carry, written so the shared tokeniser reads it back as that label; None when there is
    none or more than one. A missing_field record must name its field (paired_review's judged-
    absence refusals), and which field is Python's to say, never the model's."""
    import pairing_map
    present = pairing_map.unit_fields(unit_text or "")
    candidates = sorted(set(pairing_map.needed_fields(rule_text or "", vocabulary or ())) - set(present))
    if len(candidates) != 1:
        return None
    text = " ".join(candidates[0])
    return text if pairing_map._norm_label(text) == candidates[0] else None


def rule_check_reply(decision, question, *, plan_kind, unit_text, ref, field_label, ok, call_id, backend, model):
    """The decision as the reply the paired review's bookkeeping for its plan kind reads (`ok`,
    `parsed.items`, `call_id`, `backend`, `model`): a settled answer the config maps to a record on
    this plan kind gives one Finding-shaped item, the unit's own text as its quote (Python's echo of
    the evidence it selected); any other answer gives none, and a settled not met the config maps
    to nothing says so in `unwritten`. The decision itself travels as `decision`."""
    items, unwritten = [], None
    label = _settled_label(decision, question) if ok else None
    mapped = ((question["decision"].get("record") or {}).get(plan_kind) or {}).get(label) if label else None
    if label == "not_met" and not mapped:
        unwritten = NO_RELATION_DECLARED
    elif mapped and mapped["relation"] == "missing_field" and not field_label:
        unwritten = NO_FIELD_NAMED
    elif mapped:
        item = dict(ref=str(ref or ""), kind="finding", confidence="CONFIDENT", relation=mapped["relation"],
                    record_verdict=mapped["record_verdict"], quote=str(unit_text or "").strip(),
                    explanation=decided_sentence(label, decision))
        if field_label:
            item["field_label"] = field_label
        items.append(item)
    # `rule_check` names the plan kind the decision was asked on: what paired_review's screen reads
    # to know a rule_not_met came from this step (INFRA-051). A model's reply never carries it.
    return {"ok": bool(ok), "parsed": {"items": items}, "call_id": call_id, "backend": backend,
            "model": model, "decision": decision if ok else None, "unwritten": unwritten, "rule_check": plan_kind}


def pair_item(decision, question, record, source_text):
    """One VERIFIER item for a settled answer on a pair, None otherwise. auditor_pair_id joins the
    pair directly (auditor_pairs.finding_pair); the passage is the quote (Python's echo)."""
    label = _settled_label(decision, question)
    if label is None:
        return None
    refs = list(record.get("source_ref_ids") or [])
    return dict(ref=refs[0] if refs else "", kind="finding",
                confidence="CONFIDENT", finding=label, auditor_pair_id=record["pair_id"],
                producer_item_id=record["producer_item_id"], producer_revision=record["producer_revision"],
                source_span_id=record["source_span_id"], source_ref_ids=refs,
                quote=str(source_text or "").strip(), reasoning=decided_sentence(label, decision))
