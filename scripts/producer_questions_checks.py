"""Proofs of the producer backend's narrowed roles (INFRA-050), on fixtures only.

The declaration loads; nothing is used while a form is reply or no threshold is measured, and
speech_act never with no operator-declared act; each question renders only the evidence Python
selected, with Unclear always offered; a settled answer writes the declared record and an unsettled
one none; a citation naming exactly one other document is Python's with no call, more than the
declared candidates refused; an extracted span is kept only when the unit holds it verbatim, and an
element's document count is Python's; an editorial observation on a model's finding goes only to a
rank of the other model family. Each proof is neutralised where marked. check() returns
(status, detail) for the gate (check 336).
"""
import copy
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import choice_decision  # noqa: E402
import producer_questions as pq  # noqa: E402


def decision(label, answers, p=0.9, settled=True):
    rows = [{"label": a["label"], "surface": a["surface"], "token_id": i, "probability": (p if a["label"] == label else (1 - p) / (len(answers) - 1))}
            for i, a in enumerate(answers)]
    return {"answers": rows, "settled": settled, "decided": label if settled else choice_decision.UNSETTLED, "confidence": p}


# The LEGAL_ANALYST item's keys: the neutral fields of INFRA-050 and the envelope's core keys, nothing else.
NEUTRAL = {"ref", "kind", "confidence", "claim_id", "verdict", "passage_ref", "support_probabilities", "quote", "reasoning", "ref_ids"}


def run_proofs():
    results = []

    def proof(name, ok):
        results.append((name, bool(ok)))

    config = pq.load_config()
    proof("the declaration loads with every question", set(pq.QUESTIONS) <= set(config))
    proof("as shipped every form is reply, so nothing is used", all(pq.not_used(config[n]) == pq.NOT_ADOPTED for n in pq.QUESTIONS))
    adopted = copy.deepcopy(config["claim_support"])
    adopted["form"] = "decision"
    real_threshold = choice_decision.threshold
    choice_decision.threshold = lambda family, path=None: None
    try:
        proof("decision with no measured threshold is still not used", pq.not_used(adopted) == pq.NO_THRESHOLD)
    finally:
        choice_decision.threshold = real_threshold
    acts = copy.deepcopy(config["speech_act"])
    acts["form"] = "decision"
    proof("speech_act with no operator-declared act is never asked", pq.not_used(acts) == pq.NO_ACTS)
    bad = copy.deepcopy(config)
    bad["claim_support"]["form"] = "maybe"
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "q.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        try:
            pq.load_config(path)
            refused = False
        except ValueError:
            refused = True
    proof("refused: a form this code does not know", refused)

    q = config["claim_support"]
    prompt = pq.render_claim_support(q, "Part {text}  with   spaces", "The passage text.")
    proof("claim_support renders the unit and the passage only, braces kept", "Part {text} with spaces" in prompt and "The passage text." in prompt
          and "REF-" not in prompt)
    answers = pq.answers_of(q)
    proof("Unclear is always offered last", answers[-1] == pq.UNCLEAR and [a["label"] for a in answers[:-1]] == ["GROUNDED", "THIN", "UNSUPPORTED", "OUT_OF_SCOPE"])
    item = pq.claim_support_item(decision("THIN", answers), q, "u02-x", "REF-0007", "The  passage text.")
    proof("a settled answer writes the neutral LEGAL_ANALYST item", item["verdict"] == "THIN" and item["claim_id"] == "u02-x"
          and item["passage_ref"] == "REF-0007" and item["quote"] == "The passage text." and item["ref_ids"] == ["REF-0007"]
          and set(item) <= NEUTRAL and len(item["support_probabilities"]) == 5 and "probability 0.900" in item["reasoning"])
    proof("an unsettled answer writes none", pq.claim_support_item(decision("THIN", answers, settled=False), q, "u", "REF-1", "t") is None)
    proof("an Unclear answer writes none", pq.claim_support_item(decision(choice_decision.UNSETTLED, answers), q, "u", "REF-1", "t") is None)
    big = copy.deepcopy(q)
    big["max_prompt_chars"] = 10
    try:
        pq.render_claim_support(big, "x", "y")
        sized = False
    except choice_decision.ChoiceRefused as exc:
        sized = str(exc) == pq.TOO_LARGE
    proof("a question over its size is refused", sized)

    s = copy.deepcopy(config["speech_act"])
    s["decision"]["answers"] = [{"label": "proposal", "surface": "Propose", "meaning": "it puts something forward"},
                                {"label": "acceptance", "surface": "Accept"}]
    lines = pq.lines_of(s, "Heading\n\nFirst line.\n---\n  Second line  \n", heading="Heading")
    proof("speech_act lines skip the heading, blanks and rules", lines == ["First line.", "Second line"])
    rendered = pq.render_speech_act(s, lines[0])
    proof("the operator's acts are the answers, with their meanings", "Propose: it puts something forward" in rendered and "Accept" in rendered
          and "Unclear" in rendered)
    act = pq.speech_act_item(decision("proposal", pq.answers_of(s)), s, "u01-l1", "First  line.")
    proof("a settled act writes the tagger's item", act["speech_act"] == "proposal" and act["text"] == "First line.")

    c = config["citation_target"]
    docs = ["Annual Plan", "Annual Plan Review", "Site Notes", "Own Document"]
    proof("one named document is Python's, with no call", pq.citation_plan(c, "See the site notes.", docs, "Own Document") == ("python", "Site Notes"))
    proof("two named documents are asked", pq.citation_plan(c, "The annual plan review revised the annual plan.", docs, "Own Document")
          == ("ask", ["Annual Plan", "Annual Plan Review"]))
    proof("a line naming no other document is no citation", pq.citation_plan(c, "Nothing here.", docs, "Own Document") is None)
    proof("the document under review is never its own candidate", pq.citation_plan(c, "Own document only.", docs, "Own Document") is None)
    many = ["Annex " + w for w in ("north", "south", "east", "west", "upper", "lower")]
    proof("more than the declared candidates is refused", pq.citation_plan(c, " ".join(many), many, "x") == ("refused", pq.TOO_MANY))
    cands = ["Annual Plan", "Annual Plan Review"]
    rendered = pq.render_citation(c, "line", cands)
    proof("a citation question offers its own letters, None and Unclear", "A: Annual Plan" in rendered and "B: Annual Plan Review" in rendered
          and "\nC" not in rendered and "None" in rendered and "Unclear" in rendered)
    offered = pq.answers_of(c, count=2)
    chosen = pq.citation_item("Own", "line", decision=decision("candidate_2", offered), question=c, candidates=cands)
    proof("a settled letter resolves to its candidate", chosen["target_document"] == "Annual Plan Review" and chosen["resolved"] is True
          and chosen["decided_by"] == "model")
    none = pq.citation_item("Own", "line", decision=decision("none", offered), question=c, candidates=cands)
    proof("None writes resolved false", none["resolved"] is False and none["target_document"] is None)
    py = pq.citation_item("Own", "line", target="Site Notes")
    proof("Python's resolution says so", py["decided_by"] == "python" and py["resolved"] is True)

    unit = "The board met.  Chair: Dana Smith signed the minutes."
    kept, refused = pq.keep_extracted(config["name_role"], [{"name": "Dana Smith", "role": "chair", "evidence_in_text": "Chair: Dana Smith"},
                                                            {"name": "Lee Park", "role": "chair", "evidence_in_text": "Chair: Lee Park"}], unit)
    proof("a name the unit holds verbatim is kept, an invented one refused with its reason",
          [k["name"] for k in kept] == ["Dana Smith"] and refused[0]["refused_reason"] == pq.NOT_VERBATIM
          and refused[0]["refused_fields"] == ["name", "evidence_in_text"])
    kept, refused = pq.keep_extracted(config["inventory_element"], [{"element": "minutes"}, {"element": "ledger"}], unit)
    proof("an element is kept only verbatim", [k["element"] for k in kept] == ["minutes"] and len(refused) == 1)
    count, names = pq.corpus_count("minutes", [{"name": "a", "text": "the minutes"}, {"name": "b", "text": "no"}, {"name": "c", "text": "Minutes"}])
    proof("an element's document count is Python's, case kept", (count, names) == (1, ["a"]))

    ranks = [{"name": "EDITOR_CLERK", "backend": "local_producer"}, {"name": "EDITOR_HEAD_OF_DEPARTMENT", "backend": "local_auditor"}]
    proof("a producer-written finding goes to an auditor rank only", [r["name"] for r in pq.route(ranks, "local_producer", "model")] == ["EDITOR_HEAD_OF_DEPARTMENT"])
    proof("an auditor-written finding goes to a producer rank only", [r["name"] for r in pq.route(ranks, "local_auditor", "model")] == ["EDITOR_CLERK"])
    proof("a Python finding may go to either", len(pq.route(ranks, "paired", "python")) == 2)
    proof("with no rank of the other family, none reviews it", pq.route(ranks[:1], "local_producer", "model") == [])
    e = config["editorial_verdict"]
    ed = pq.editorial_item(decision("concern", pq.answers_of(e)), e, "REF-0003", "The total is wrong.")
    proof("a settled editorial verdict writes the rank's item", ed["verdict"] == "concern" and ed["quote"] == "The total is wrong.")

    # Neutralisations: each must make its proof fail.
    neutral = []
    real = pq.verbatim
    pq.verbatim = lambda span, unit_text: True
    try:
        k, _ = pq.keep_extracted(config["name_role"], [{"name": "Lee Park", "evidence_in_text": "x"}], unit)
        neutral.append(("verbatim test removed: an invented name is kept", len(k) == 1))
    finally:
        pq.verbatim = real
    real_family = pq.family_of
    pq.family_of = lambda backend: "producer"
    try:
        neutral.append(("one family for every backend: no rank may review", pq.route(ranks, "local_producer", "model") == []))
    finally:
        pq.family_of = real_family
    real_settled = pq.settled_label
    pq.settled_label = lambda d, answers: "THIN"
    try:
        neutral.append(("unsettled read as settled: a record is written", pq.claim_support_item(decision("THIN", answers, settled=False), q, "u", "REF-1", "t") is not None))
    finally:
        pq.settled_label = real_settled
    for name, failed_as_it_should in neutral:
        proof("neutralised, " + name, failed_as_it_should)
    return results


def check():
    results = run_proofs()
    failed = [n for n, ok in results if not ok]
    if failed:
        return "FAIL", "%d of %d proofs failed: %s" % (len(failed), len(results), "; ".join(failed[:5]))
    return "PASS", ("%d proofs: the narrowed producer roles (INFRA-050) are off as shipped and with no measured threshold; each question "
                    "renders only Python's evidence, a settled answer writes the declared record, a citation to one document is Python's, "
                    "a span is kept only verbatim, an editorial observation goes to the other family; 3 neutralisations fail" % len(results))


if __name__ == "__main__":
    status, detail = check()
    print(status, detail)
    sys.exit(0 if status == "PASS" else 1)
