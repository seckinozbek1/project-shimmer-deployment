"""A narrow question decided from the model's own probabilities (D-S41).

The question is short and states a fixed set of answers. The answer is read from the next-token
logits of ONE forward pass over the rendered prompt: nothing is generated, so the model writes no
text and no quote, and the evidence is whatever Python selected for the question.

    declare(text, answers)            a question: the rendered prompt and its ordered answers
    bind(question, encode)            each answer's token, or ChoiceRefused
    decide(score_fn, question, t)     the decision: one call of `score_fn`, no generation
    settle(decision, t)               the same probabilities read against another threshold
    tempered(decision, T)             the probabilities under a fitted temperature (calibration)
    threshold(family)                 the measured threshold of a family, None when there is none

An answer is {"label", "surface"}: the label is what the decision says, the surface what the prompt
told the model to write. Anything else on the answer is the caller's and passes through.

Why the first tokens must differ. `score_fn` gives the logits of the next token only, and D-S41 asks
for one forward pass, so an answer is scored on its first token. Two answers sharing that token
cannot be told apart by it, and scoring the whole span would take one more pass per answer; so
`bind` REFUSES such a declaration rather than scoring anything, and the caller declares surfaces
that differ at once. Refused at binding, because only the model's tokenizer can say.

Why the token is read after the prompt. A tokenizer writes a word differently at the start of a text
and after other text, so `surface` alone can give a token the model would never emit there. `bind`
encodes the prompt with the surface after it and takes the first token past the prompt's own, and
refuses when the surface changes how the prompt's own tokens fall.

The probabilities are renormalised over the declared answers. `declared_mass` is what those answers
held of the whole vocabulary: a low figure means the model wanted to say something else, and the
renormalised confidence hides that, so it is recorded on every decision and read beside it, with
`undeclared_top`: the likeliest token outside the set, by its id and probability.

Confidence is the top probability. Below the threshold the decision is UNSETTLED; a tie is UNSETTLED
at any threshold, never broken by the order of the declaration; with no threshold the probabilities
stand and the decision is UNSETTLED, as the ensemble refuses a voter with no entry (WORDS-A). A
threshold comes from `config/semantic_thresholds.json`, section `choice_decision`, measured on
development material with the error rate it produces beside it, and never from code.
"""
import json
import math
from pathlib import Path

SCHEMA = "choice-decision-v1"
UNSETTLED = "cannot be settled"
BELOW_THRESHOLD, TIE, NO_THRESHOLD = "below_threshold", "tie", "no_threshold"
THRESHOLDS_PATH = Path(__file__).resolve().parents[1] / "config" / "semantic_thresholds.json"
THRESHOLDS_SECTION = "choice_decision"


class ChoiceRefused(ValueError):
    """A question that cannot be decided as declared."""


class ChoiceUnreadable(ChoiceRefused):
    """Logits that cannot be read: one call's failure, where a refused declaration is every call's."""


def declare(text, answers):
    """The question on rendered prompt `text`: at least two answers, each with its own label and
    its own surface, in the order given."""
    if not isinstance(text, str) or not text.strip():
        raise ChoiceRefused("a question needs its rendered prompt")
    answers = [dict(a) for a in answers or []]
    if len(answers) < 2:
        raise ChoiceRefused("a question declares at least two answers")
    for answer in answers:
        if not all(isinstance(answer.get(k), str) and answer[k].strip() for k in ("label", "surface")):
            raise ChoiceRefused("an answer needs a label and a surface")
    for key in ("label", "surface"):
        if len({a[key] for a in answers}) != len(answers):
            raise ChoiceRefused("no two answers share a " + key)
    return {"text": text, "answers": answers}


def bind(question, encode):
    """`question` with each answer's `token_id`, the token that writes its surface after this
    prompt. `encode(text)` is the model's tokenizer, adding no special tokens."""
    prompt = list(encode(question["text"]))
    held = {}
    answers = []
    for answer in question["answers"]:
        whole = list(encode(question["text"] + answer["surface"]))
        if len(whole) <= len(prompt) or whole[:len(prompt)] != prompt:
            raise ChoiceRefused("the surface of answer %r joins the prompt's last token" % answer["label"])
        token = whole[len(prompt)]
        if token in held:
            raise ChoiceRefused("answers %r and %r share their first token" % (held[token], answer["label"]))
        held[token] = answer["label"]
        answers.append(dict(answer, token_id=int(token)))
    return dict(question, answers=answers)


def _log_sum(values):
    top = max(values)
    if top == -math.inf:
        return top
    return top + math.log(math.fsum(math.exp(v - top) for v in values))


def probabilities(logits, token_ids):
    """(probability of each token over `token_ids` alone, the mass they hold of the whole vocabulary)."""
    values = [float(v) for v in logits]
    if not values or any(math.isnan(v) or v == math.inf for v in values):
        raise ChoiceUnreadable("the logits are not finite")
    if any(not 0 <= t < len(values) for t in token_ids):
        raise ChoiceRefused("an answer's token is outside the logits")
    chosen = [values[t] for t in token_ids]
    held = _log_sum(chosen)
    if held == -math.inf:
        raise ChoiceUnreadable("the declared answers hold no probability at all")
    return [math.exp(v - held) for v in chosen], math.exp(held - _log_sum(values))


def undeclared_top(logits, token_ids):
    """{token_id, probability} of the likeliest token no answer declares, of the whole vocabulary:
    what the model wanted to say instead, as numbers. None when the answers are the vocabulary."""
    values = [float(v) for v in logits]
    declared = set(token_ids)
    rest = [(v, n) for n, v in enumerate(values) if n not in declared]
    if not rest:
        return None
    value, token = max(rest)
    return {"token_id": token, "probability": math.exp(value - _log_sum(values))}


def settle(decision, threshold):
    """`decision` read against `threshold`: its probabilities unchanged, its verdict from them."""
    if threshold is not None and not (type(threshold) in (int, float) and 0 <= threshold <= 1):
        raise ChoiceRefused("a threshold is a probability")
    ranked = sorted(decision["answers"], key=lambda a: -a["probability"])
    top = ranked[0]
    why = None
    if top["probability"] == ranked[1]["probability"]:
        why = TIE
    elif threshold is None:
        why = NO_THRESHOLD
    elif top["probability"] < threshold:
        why = BELOW_THRESHOLD
    return dict(decision, top=None if why == TIE else top["label"], confidence=top["probability"], threshold=threshold,
                settled=why is None, why=why, decided=top["label"] if why is None else UNSETTLED)


def tempered(decision, temperature):
    """`decision` with its probabilities scaled by a fitted `temperature` (calibration, D-S54 item 1):
    each answer's log probability divided by it, renormalised over the declared answers, the same as
    dividing the logits. The order of the answers never changes, only how far apart they stand; a
    temperature of 1 gives the probabilities back. `declared_mass` and `undeclared_top` are the
    model's and stay. Read it again with `settle`."""
    if not (type(temperature) in (int, float) and math.isfinite(temperature) and temperature > 0):
        raise ChoiceRefused("a temperature is a positive number")
    logs = [math.log(a["probability"]) if a["probability"] > 0 else -math.inf for a in decision["answers"]]
    held = _log_sum([v / temperature for v in logs])
    answers = [dict(a, probability=math.exp(v / temperature - held)) for a, v in zip(decision["answers"], logs)]
    return dict(decision, answers=answers, temperature=temperature)


def decide(score_fn, question, threshold):
    """The decision on a bound `question`: `score_fn(rendered prompt)` is called once and gives the
    next-token logits. Labels, surfaces, tokens and numbers only: the record holds no text."""
    answers = question["answers"]
    logits = score_fn(question["text"])
    tokens = [a["token_id"] for a in answers]
    shares, mass = probabilities(logits, tokens)
    rows = [{"label": a["label"], "surface": a["surface"], "token_id": a["token_id"], "probability": p}
            for a, p in zip(answers, shares)]
    return settle({"schema": SCHEMA, "answers": rows, "declared_mass": mass, "undeclared_top": undeclared_top(logits, tokens)}, threshold)


def threshold(family, path=THRESHOLDS_PATH):
    """The measured threshold of `family`, or None when none has been measured."""
    section = json.loads(Path(path).read_text(encoding="utf-8")).get(THRESHOLDS_SECTION) or {}
    value = section.get(family)
    if value is not None and not (type(value) in (int, float) and 0 <= value <= 1):
        raise ChoiceRefused("the threshold of %s is not a probability" % family)
    return value
