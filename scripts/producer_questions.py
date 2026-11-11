"""The producer backend's narrowed roles (INFRA-050; D-S57 item 1, D-S56 item 1, D-S62 item 3).

Each role is declared in config/producer_questions.json: the evidence Python selects, a fixed
prompt with fixed answers (a choice) or a span the unit must hold verbatim (an extraction), and what
Python writes from the answer. A choice is read from the model's own probabilities in one forward
pass (choice_decision.py through agent_wrapper.call_choice): the model writes no text, and the quote
on a record is Python's echo of the evidence it selected.

    claim_support      LEGAL_ANALYST: does the context passage Python ranks first for a unit
                       support what the unit states (GROUNDED, THIN, UNSUPPORTED, OUT_OF_SCOPE)
    speech_act         SPEECH_ACT_TAGGER: what one line does, from the acts the OPERATOR declares
                       (none declared: never asked)
    citation_target    CITATION_RESOLVER: which other document a line refers to, among those whose
                       name it carries; exactly one is resolved by Python with no call
    name_role          INST_FINDER: a name and a role, kept only when the unit holds both verbatim
    inventory_element  ARCHIVIST: an element, kept only when the unit holds it verbatim; its
                       document count is Python's
    editorial_verdict  the editorial ranks: is an observation's finding sound, routed to a rank on
                       the other model family from the finding's own

Nothing is used under a question until its form is `decision` and, for a choice,
config/semantic_thresholds.json holds its family's measured threshold (`not_used` says why); until
then each role runs as shipped. Adopting a form is a recorded decision after its measurement.
"""
import json
import re
from pathlib import Path

import choice_decision

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "producer_questions.json"
SCHEMA = "producer-questions-v1"
REPLY_FORM, DECISION_FORM = "reply", "decision"
CHOICES = ("claim_support", "speech_act", "citation_target", "editorial_verdict")
EXTRACTIONS = ("name_role", "inventory_element")
QUESTIONS = CHOICES + EXTRACTIONS
NOT_ADOPTED = "form_reply"
NO_THRESHOLD = "no_measured_threshold"
NO_ACTS = "no_operator_declared_act"
TOO_LARGE = "question_over_its_size"
TOO_MANY = "more_candidates_than_declared"
NOT_VERBATIM = "not_found_verbatim_in_the_unit"
NO_OTHER_FAMILY = "no_rank_of_the_other_model_family"
UNCLEAR = {"label": choice_decision.UNSETTLED, "surface": "Unclear"}
DECIDED = "Decided from the model's own probabilities, no text written: %s (probability %.3f)."
FAMILIES = {"local_producer": "producer", "local_auditor": "auditor"}


def load_config(path=CONFIG_PATH):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema") != SCHEMA or any(name not in value for name in QUESTIONS):
        raise ValueError("config/producer_questions.json: schema %s with %s" % (SCHEMA, ", ".join(QUESTIONS)))
    for name in QUESTIONS:
        form_of(value[name])
    for name in CHOICES:
        declared = value[name]["decision"]["answers"]
        if declared:
            choice_decision.declare("x", answers_of(value[name]))
    return value


def form_of(question):
    """How the question is asked. A value this code does not know is refused, never read as the default."""
    form = question.get("form", REPLY_FORM)
    if form not in (REPLY_FORM, DECISION_FORM):
        raise ValueError("config/producer_questions.json: form is reply or decision")
    return form


def answers_of(question, count=None):
    """The question's answers, Unclear last. citation_target offers its first `count` letters and
    None; speech_act the operator's acts."""
    declared = list(question["decision"]["answers"])
    if count is not None:
        declared = declared[:count] + [a for a in declared if a["label"] == "none"]
    return [{"label": a["label"], "surface": a["surface"]} for a in declared] + [UNCLEAR]


def not_used(question):
    """Why the narrowed form is not used ('' when it is)."""
    if form_of(question) != DECISION_FORM:
        return NOT_ADOPTED
    if "decision" in question:
        if not question["decision"]["answers"]:
            return NO_ACTS
        if choice_decision.threshold(question["decision"]["threshold_family"]) is None:
            return NO_THRESHOLD
    return ""


def _fill(template, slots):
    """One pass over the template, so braces in the evidence stay as written."""
    return re.sub(r"\{(%s)\}" % "|".join(map(re.escape, slots)), lambda m: slots[m.group(1)], template)


def _sized(question, prompt):
    if len(prompt) > int(question["max_prompt_chars"]):
        raise choice_decision.ChoiceRefused(TOO_LARGE)
    return prompt


def _answer_lines(question, answers):
    meaning = {a["label"]: a.get("meaning") for a in question["decision"]["answers"]}
    return "\n".join("%s%s" % (a["surface"], (": " + meaning[a["label"]]) if meaning.get(a["label"]) else "") for a in answers)


def normalised(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def verbatim(span, unit_text):
    """True when the span is in the unit, whitespace-normalised, and carries a letter or a digit."""
    span = normalised(span)
    return bool(span) and bool(re.search(r"\w", span)) and span in normalised(unit_text)


def decided_sentence(label, decision):
    return DECIDED % (label, float((decision or {}).get("confidence") or 0.0))


def settled_label(decision, answers):
    if not isinstance(decision, dict) or not decision.get("settled"):
        return None
    label = decision.get("decided")
    return label if label in {a["label"] for a in answers} and label != choice_decision.UNSETTLED else None


# claim_support (LEGAL_ANALYST)

def render_claim_support(question, unit_text, passage_text):
    return _sized(question, _fill(question["decision"]["template"], {"unit": normalised(unit_text), "passage": normalised(passage_text)}))


def claim_support_item(decision, question, unit_id, passage_ref, passage_text):
    """One LEGAL_ANALYST item for a settled answer, None otherwise (INFRA-050's neutral fields)."""
    answers = answers_of(question)
    label = settled_label(decision, answers)
    if label is None:
        return None
    return dict(ref=str(passage_ref), kind="finding", confidence="CONFIDENT", claim_id=str(unit_id), verdict=label,
                passage_ref=str(passage_ref),
                support_probabilities=[float(a["probability"]) for a in decision.get("answers") or []],
                quote=normalised(passage_text), reasoning=decided_sentence(label, decision), ref_ids=[str(passage_ref)])


# speech_act (SPEECH_ACT_TAGGER)

def lines_of(question, unit_text, heading=None):
    """The unit's lines that carry a letter or a digit, its heading line excepted, in order, at most
    the declared number."""
    out = []
    for line in str(unit_text or "").splitlines():
        line = line.strip()
        if not line or not re.search(r"\w", line) or (heading and normalised(line) == normalised(heading)):
            continue
        out.append(line)
    return out[:int(question["max_lines_per_unit"])]


def render_speech_act(question, line):
    answers = answers_of(question)
    return _sized(question, _fill(question["decision"]["template"], {"line": normalised(line), "answer_lines": _answer_lines(question, answers)}))


def speech_act_item(decision, question, utterance_id, line):
    label = settled_label(decision, answers_of(question))
    if label is None:
        return None
    return dict(ref=str(utterance_id), kind="finding", confidence="CONFIDENT", utterance_id=str(utterance_id), text=normalised(line),
                speech_act=label, force=decided_sentence(label, decision))


# citation_target (CITATION_RESOLVER)

def candidates_for(line, documents, own_name):
    """The other documents every word of whose name the line carries, by the shared tokeniser,
    in the order given; a name with no word is never a candidate."""
    import pairing_map
    words = set(pairing_map._norm_label(line))
    found = []
    for name in documents:
        if name == own_name:
            continue
        tokens = set(pairing_map._norm_label(name))
        if tokens and tokens <= words:
            found.append(name)
    return found


def citation_plan(question, line, documents, own_name):
    """('python', target) for exactly one candidate, ('ask', candidates) for two to the declared
    number, ('refused', TOO_MANY) beyond it, or None when the line names no other document."""
    found = candidates_for(line, documents, own_name)
    if not found:
        return None
    if len(found) == 1:
        return ("python", found[0])
    if len(found) > int(question["max_candidates"]):
        return ("refused", TOO_MANY)
    return ("ask", found)


def render_citation(question, line, candidates):
    answers = answers_of(question, count=len(candidates))
    listed = "\n".join("%s: %s" % (a["surface"], name) for a, name in zip(answers, candidates))
    return _sized(question, _fill(question["decision"]["template"],
                                  {"line": normalised(line), "candidates": listed, "answer_lines": _answer_lines(question, answers)}))


def citation_item(source_document, line, *, target=None, decision=None, question=None, candidates=None):
    """A Python resolution (target given) or a settled choice among candidates; None when unsettled."""
    if target is not None:
        return dict(ref=str(source_document), kind="finding", confidence="CONFIDENT", source_document=str(source_document),
                    target_document=str(target), citation_form=normalised(line), resolved=True, decided_by="python")
    answers = answers_of(question, count=len(candidates))
    label = settled_label(decision, answers)
    if label is None:
        return None
    chosen = None if label == "none" else candidates[int(label.rsplit("_", 1)[1]) - 1]
    return dict(ref=str(source_document), kind="finding", confidence="CONFIDENT", source_document=str(source_document),
                target_document=chosen, citation_form=normalised(line), resolved=chosen is not None,
                decided_by="model", reasoning=decided_sentence(label, decision))


# extractions (INST_FINDER, ARCHIVIST)

def keep_extracted(question, items, unit_text):
    """(kept, refused): an item is kept only when each declared span field it must hold is in the
    unit verbatim (name_role: name and evidence_in_text; inventory_element: element)."""
    must = ("name", "evidence_in_text") if question["agent"] == "INST_FINDER" else ("element",)
    kept, refused = [], []
    for item in items or []:
        missing = [f for f in must if not verbatim((item or {}).get(f), unit_text)]
        (refused if missing else kept).append(dict(item, refused_reason=NOT_VERBATIM, refused_fields=missing) if missing else item)
    return kept, refused


def corpus_count(element, documents):
    """Python's document count for an inventory element: the documents whose text holds it verbatim."""
    names = [d["name"] for d in documents if verbatim(element, d.get("text"))]
    return len(names), names


# editorial_verdict (the editorial ranks)

def family_of(backend):
    return FAMILIES.get(str(backend or ""))


def route(ranks, finding_backend, written_by):
    """The ranks that may review the observation: for a model's finding, those whose backend is of
    the other family; for a Python finding, every rank. [] means none may, and the record says so."""
    if written_by == "python":
        return list(ranks)
    own = family_of(finding_backend)
    return [r for r in ranks if family_of(r["backend"]) is not None and family_of(r["backend"]) != own]


def render_editorial(question, finding_sentence, unit_text):
    return _sized(question, _fill(question["decision"]["template"], {"finding": normalised(finding_sentence), "unit": normalised(unit_text)}))


def editorial_item(decision, question, ref, finding_sentence):
    label = settled_label(decision, answers_of(question))
    if label is None:
        return None
    return dict(ref=str(ref), kind="finding", confidence="CONFIDENT", verdict=label, rationale=decided_sentence(label, decision),
                quote=normalised(finding_sentence))
