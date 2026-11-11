"""Find, then judge (P2 (a), D-S38, D-S39): Python proposes pairs of passages of one document.

A contradiction needs two passages together, and 37 of ContraDoc's 60 sampled documents are one
unit, so pairing units reaches nothing there: the passage is a sentence, read from the text.

Everything here is structural. A passage is a stretch of text between sentence ends or line
ends; its words are the one tokeniser's (`pairing_map._norm_label`); a word's weight is how rare
it is in this document, so no word list exists in any language. A pair is proposed because the
embedding model puts its two passages close, or, when that model cannot load, because they share
rare words; shared labels and shared figures the plan names are not built. The proposer never
reads a key and never decides anything: a pair says only "these two are worth showing a model
together". What a pair's words mean is the model's to judge (WORDS-A), and that judgement is a
model's record, never Python's.

    passages(text)            the passages of a text, with their offsets
    propose(items, limit)     the `limit` best pairs of those passages, best first
    prepare(units, config)    a document's passages, encoded once, and its pairs
    review(...)               a declared rule's pairs put to `ask`, both orders, as a model's records

A rule asks for this with `[compare: passages]` on its heading: the operator declares it, and no
rule's words are read to decide it.

`config/passage_pairs.json` `form` chooses how a pair is judged: `reply` (a JSON reply, read by
read_reply) or `decision` (D-S41: the model's own probabilities over the declared answers, read by
read_decision; no text, so the passages Python chose are the only quotes). A settled answer counts
as a reply's outcome would; a decision that is not settled counts as cannot tell. Under `decision`
nothing is asked until the family's threshold has been measured. The finding is the same model's
record either way; the decision and its confidence travel in the pairing map row, from which
`paired_review.model_item_notes` writes the note every deliverable shows.
"""
import json
import math
import re
from pathlib import Path

import choice_decision
import paired_review
import pairing_map

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "passage_pairs.json"
COMPARE_PASSAGES = "passages"
JUDGED_PATH = paired_review.JUDGED_PATH_PASSAGE_PAIR
REPLY_FORM, DECISION_FORM = "reply", "decision"
NO_THRESHOLD_WHY = "no_threshold"
# Python's sentence on a decided finding: its catalog row (scripts/ui/localization_catalog.js) reads
# these words, and it goes in `reader_notes`, since "The model wrote" would be false of a decision.
DECISION_NOTE = ("Decided from the model's own answer probabilities; it wrote no text. In both orders: %s, confidence %.3f and %.3f; "
                 "the fixed answers held at least %.3f of its probability.")

# A sentence ends at . ! or ?, with any closing quote or bracket, before white space and a
# capital, a digit or an opening quote or bracket. Scripts without capitals end at the line.
_CLOSING = re.escape("\"')]" + chr(0x201D) + chr(0x2019))
_OPENING = re.escape("\"'([" + chr(0x201C) + chr(0x2018))
_END = re.compile(r"(?<=[.!?])[" + _CLOSING + r"]*\s+(?=[" + _OPENING + r"]?[^\W\d_a-z]|\d)")
_NOT_PROSE = re.compile(r"^\s*(#|\||[-=_*]{3,}\s*$)")
MIN_WORDS = 4          # a shorter stretch joins the next: an abbreviation's stop, not a sentence
_FIGURE = re.compile(r"\d[\d,.]*")
# What a review survives: any failure of a call (out of memory, no chat template, a masking
# refusal), so a document never loses its computed findings to this step.
CAUGHT = Exception
FAILED_ORDER = "FAILED"   # the class of an order whose call failed, beside a reply's own classes
# The reply reader's fence and escape, as bare_model.py's section 5.4 reader writes them.
_FENCE = re.compile(r"^\s*```[^`\s]*\s*$")
_ESCAPE = re.compile(r'\\(["\\/bfnrtu])|\\')


def _words(text):
    return [w for w in re.split(r"[\W_]+", str(text or "").lower()) if w]


def passages(text):
    """[{index, start, end, text}] in order: the sentences of every prose line of `text`."""
    out = []
    position = 0
    for line in str(text or "").splitlines(keepends=True):
        begin, position = position, position + len(line)
        if not line.strip() or _NOT_PROSE.match(line):
            continue
        cuts = [0] + [m.end() for m in _END.finditer(line)] + [len(line)]
        held, first = None, len(out)
        for a, b in zip(cuts, cuts[1:]):
            start = a if held is None else held
            if len(_words(line[start:b])) < MIN_WORDS and b < len(line):
                held = start
                continue
            held = None
            piece = line[start:b]
            lead = len(piece) - len(piece.lstrip())
            piece = piece.strip()
            if len(_words(piece)) >= MIN_WORDS:
                out.append({"index": len(out), "start": begin + start + lead,
                            "end": begin + start + lead + len(piece), "text": piece})
            elif piece and len(out) > first:
                # a short stretch closing a line belongs to the sentence before it
                last = out[-1]
                last["end"] = begin + start + lead + len(piece)
                last["text"] = str(text)[last["start"]:last["end"]]
    return out


def _tokens(text):
    """The tokeniser's words of a passage, each once: the same words a label reduces to."""
    return set(pairing_map._norm_label(text))


def _weights(token_sets):
    """How rare each word is among these passages: log(1 + n / passages holding it)."""
    count = {}
    for tokens in token_sets:
        for token in tokens:
            count[token] = count.get(token, 0) + 1
    size = len(token_sets)
    return {token: math.log(1 + size / n) for token, n in count.items()}


def _figures(text):
    return bool(_FIGURE.search(str(text or "")))


def similarity(a, b, weights):
    """The cosine of two passages' rare-word weights; 0 when they share no word."""
    shared = a & b
    if not shared:
        return 0.0
    top = sum(weights[t] ** 2 for t in shared)
    size = math.sqrt(sum(weights[t] ** 2 for t in a) * sum(weights[t] ** 2 for t in b))
    return top / size if size else 0.0


def embed(items):
    """The shipped embedding model's unit vectors of `items`, or None when it cannot load: the
    proposer then ranks on words, and the record says which ranked."""
    import embedding_store
    st = embedding_store._try_import_st()
    if st is None:
        return None
    try:
        model = embedding_store._load_model(st, embedding_store.DEFAULT_MODEL_NAME)
        return model.encode([p["text"] for p in items], normalize_embeddings=True, batch_size=16,
                            show_progress_bar=False).tolist()
    except Exception:
        return None


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _numpy():
    try:
        import numpy
    except ImportError:
        return None
    return numpy


# How far below the `limit`-th score the matrix keeps a pair for the exact sum. Its products are
# added in another order, so its last digits differ, far inside this.
_TIE_MARGIN = 1e-9


def _vector_candidates(vectors, same, limit):
    """The pairs that can reach the top `limit` by cosine: every pair of different passages, cut
    with numpy's matrix to those at or near the `limit`-th score when numpy is there. The cut
    only saves time: `propose` ranks what is left with the exact sum, so the ranking is the same
    with numpy and without it."""
    numpy = _numpy()
    size = len(vectors)
    if numpy is None or size < 2:
        return [(i, j) for i in range(size) for j in range(i + 1, size) if same[i] != same[j]]
    matrix = numpy.asarray(vectors, dtype=numpy.float64)
    first, second = numpy.triu_indices(size, 1)
    labels = numpy.unique(same, return_inverse=True)[1]
    different = labels[first] != labels[second]
    first, second = first[different], second[different]
    values = (matrix @ matrix.T)[first, second]
    if len(values) > limit:
        at = len(values) - limit
        chosen = values >= numpy.partition(values, at)[at] - _TIE_MARGIN
        first, second = first[chosen], second[chosen]
    return list(zip(first.tolist(), second.tolist()))


def propose(items, limit, vectors=None):
    """The `limit` best pairs of `items`, best first: [{a, b, score, figures}]. Ranked by the
    cosine of `vectors` when given (the embedding model), else by shared rare words.

    `a` and `b` are indexes into `items`, a before b. A pair of identical passages is left out:
    a text repeating itself contradicts nothing. Ties keep document order, so a build is
    deterministic. The figure mark says both passages state a figure; it orders nothing here.
    """
    tokens = [_tokens(p["text"]) for p in items]
    # Identity is read on every word: the tokeniser drops short words, so "shall not pay" and
    # "shall pay", or "5 days" and "9 days", reduce to the same tokens and are the likeliest pairs.
    same = [" ".join(_words(p["text"])) for p in items]
    weights = _weights(tokens)
    rows = []
    candidates = (_vector_candidates(vectors, same, limit) if vectors else
                  [(i, j) for i in range(len(items)) for j in range(i + 1, len(items)) if same[i] != same[j]])
    for i, j in candidates:
        score = _dot(vectors[i], vectors[j]) if vectors else similarity(tokens[i], tokens[j], weights)
        if score > 0:
            rows.append((-score, i, j))
    rows.sort()
    return [{"a": i, "b": j, "score": round(-s, 6),
             "figures": _figures(items[i]["text"]) and _figures(items[j]["text"])}
            for s, i, j in rows[:limit]]


def load_config(path=CONFIG_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def declared(rules):
    """The rules whose heading declares `[compare: passages]`."""
    return [r for r in rules or [] if r.get("compare") == COMPARE_PASSAGES]


def form_of(config):
    """How a pair is judged. A value this code does not know is refused, never read as the default."""
    form = config.get("form", REPLY_FORM)
    if form not in (REPLY_FORM, DECISION_FORM):
        raise ValueError("config/passage_pairs.json: form is reply or decision")
    return form


def deciding(config):
    return form_of(config) == DECISION_FORM


def threshold_of(config):
    return choice_decision.threshold(config["decision"]["threshold_family"])


def render(config, first, second):
    """The question on two passages, in the order given; one pass, so a passage's braces stay."""
    lines = chr(10).join(o["line"] for o in config["outcomes"])
    slots = {"passage_a": first, "passage_b": second, "outcome_lines": lines}
    template = config["decision"]["template"] if deciding(config) else config["template"]
    return re.sub(r"\{(passage_a|passage_b|outcome_lines)\}", lambda m: slots[m.group(1)], template)


def _without_fences(reply):
    return "\n".join(line for line in reply.splitlines() if not _FENCE.match(line))


def _last_balanced_object(text):
    """The last balanced {...}: from each closing brace, last first, scan back for the brace
    that balances it; the first closing brace that has one wins."""
    for end in range(len(text) - 1, -1, -1):
        if text[end] != "}":
            continue
        depth = 0
        for start in range(end, -1, -1):
            if text[start] == "}":
                depth += 1
            elif text[start] == "{":
                depth -= 1
                if depth == 0:
                    return text[start:end + 1]
    return None


def _loads(candidate):
    """The JSON value of `candidate`, or ValueError. A backslash that starts no valid escape is
    doubled, and failing that a raw line break inside a string is admitted."""
    try:
        return json.loads(candidate)
    except ValueError:
        pass
    try:
        return json.loads(_ESCAPE.sub(lambda m: m.group(0) if m.group(1) else "\\\\", candidate))
    except ValueError:
        return json.loads(candidate, strict=False)


def _outcome_key(value):
    return " ".join(str(value).lower().replace("_", " ").split())


def read_reply(text, config):
    """(class, reason) of one reply: its last balanced JSON object with fences dropped, its
    outcome read against the declared spellings; (None, None) when it cannot be read. The one
    reading of a reply: `scripts/` cannot import `benchmark/`, so this is `doc_judge.parse_reply`
    written again, and check 324 holds the two equal on the replies that once told them apart."""
    if not isinstance(text, str) or not text.strip():
        return None, None
    candidate = _last_balanced_object(_without_fences(text))
    if candidate is None:
        return None, None
    try:
        value = _loads(candidate)
    except ValueError:
        return None, None
    if not isinstance(value, dict) or not isinstance(value.get("outcome"), str):
        return None, None
    key = _outcome_key(value["outcome"])
    for outcome in config["outcomes"]:
        if key in {_outcome_key(a) for a in outcome["accepted"]}:
            reason = value.get("reason")
            return outcome["class"], reason if isinstance(reason, str) else None
    return None, None


def read_decision(decision, config):
    """(class, decision) of one decision: a settled answer's declared class, UNDECIDED for one not
    settled, (None, None) for anything that is no decision of the declared answers."""
    if not isinstance(decision, dict) or "settled" not in decision:
        return None, None
    if not decision["settled"]:
        return "UNDECIDED", decision
    for answer in config["decision"]["answers"]:
        if answer["label"] == decision.get("decided"):
            return answer["class"], decision
    return None, None


def read_answer(value, config):
    return read_decision(value, config) if deciding(config) else read_reply(value, config)


def call(wrapper, stable, dynamic, config, budget):
    """The one model call on a pair question, already masked."""
    if deciding(config):
        return wrapper.call_choice(stable + ("\n\n" + dynamic if dynamic else ""), config["decision"]["answers"],
                                   threshold_of(config))
    return wrapper.dispatch(stable, dynamic, **budget)


def answer_of(result, config):
    """What `ask` hands back: the reply's text or the decision, None for a failed call."""
    if not getattr(result, "ok", False):
        return None
    return result.parsed if deciding(config) else result.raw_text


def outcome_of(result, config):
    """The reply record's outcome of one call."""
    if not getattr(result, "ok", False):
        return "backend_failure"
    return "decided" if deciding(config) else "free_text"


def decision_row(first, second, decision):
    """One order of a pair in the pairing map: passage indexes, labels and numbers, no text."""
    return {"passages": [first["index"], second["index"]], "decided": decision["decided"], "settled": decision["settled"],
            "why": decision["why"], "confidence": decision["confidence"], "threshold": decision["threshold"],
            "declared_mass": decision["declared_mass"], "logits_dtype": decision.get("logits_dtype"),
            "answers": {a["label"]: a["probability"] for a in decision["answers"]}}


def outbound(wrapper, text, context=""):
    """(stable, dynamic) of one pair question, masked as `run_task` masks a prompt (LAW-IV,
    INFRA-041 chokepoint 1): a pair call goes straight to dispatch, so it is masked here. With no
    masker injected, or on a backend the injected masker exempts, the question is unchanged.
    `context` is the whole document's text: a name is detected only beside a title or an
    identifier, which two sentences need not hold, so the masker reads the document for its spans
    and replaces them in the question alone."""
    stable, dynamic = text, ""
    if wrapper.outbound_masker is not None:
        stable, dynamic = wrapper.outbound_masker(stable, dynamic, backend=wrapper.backend, agent=wrapper.name,
                                                  context=context)
    return stable, dynamic


def document_passages(units):
    """Every unit's passages, in unit order, each carrying its unit id."""
    out = []
    for unit in units:
        for item in passages(unit.get("text")):
            out.append(dict(item, index=len(out), unit_id=unit.get("unit_id")))
    return out


def record(first, second, rule_id, source_rule_id, reason):
    """A model's finding on one pair. That they contradict is the model's word and stays marked
    as such; `paired_review.judged_item_refusal` holds each quote to its own unit, as every judged
    answer is, and only then does it carry Python's mark. A pair across two units names the second
    in `compared_unit_id` (INFRA-047): this step is the only one that may."""
    item = {"item_id": "pair-%s-%d-%d" % (rule_id, first["index"], second["index"]), "revision": 1,
            "rule_id": rule_id, "unit_id": first["unit_id"], "relation": "contradiction",
            "record_verdict": "irregular", "quote": first["text"], "quote_b": second["text"],
            "explanation": reason or "", "judged_path": JUDGED_PATH}
    if source_rule_id:
        item["source_rule_id"] = source_rule_id
    if second["unit_id"] != first["unit_id"]:
        item["compared_unit_id"] = second["unit_id"]
    return item


def model_of(wrapper):
    """Whose answers are whose: a reply is reused only from the model that gave it."""
    return wrapper.backend, wrapper.model


def too_many(items, config):
    return len(items) > config["max_passages"]


def prepare(units, config, embed_with=None):
    """A document's side of the review, done once whatever number of rules declares it: its
    passages, their one encoding and their pairs. Above the declared `max_passages` nothing is
    encoded and no pair proposed, and every rule's row says so."""
    prepared = {"units": units, "items": [], "pairs": [], "ranked_by": None, "raised": None,
                "context": "\n\n".join(str(u.get("text") or "") for u in units)}
    try:
        prepared["items"] = items = document_passages(units)
        if not too_many(items, config):
            vectors = (embed_with or embed)(items) if items else None
            prepared["ranked_by"] = "embedding" if vectors else "words"
            prepared["pairs"] = propose(items, config["limit"], vectors)
    except CAUGHT as exc:
        prepared["raised"] = type(exc).__name__
    return prepared


def _reply(prompt, ask, memo, calls, streak):
    """The reply to `prompt`, or None for a failed call. A prompt holds no rule text, so what a
    model already answered, `memo` being that model's, is its answer for any rule: no call."""
    if prompt in memo:
        calls["reused"] += 1
        return memo[prompt]
    calls["made"] += 1
    reply = ask(prompt)
    if reply is None:
        calls["failed"] += 1
        streak[0] += 1
    else:
        streak[0] = 0
        memo[prompt] = reply
    return reply


def _both_orders(first, second, ask, config, memo, calls, streak):
    """[(class, reason), (class, reason)] of a pair, or None once `streak` failed calls in a row
    reach the declared stop. A failed call is counted apart from a reply that came back and could
    not be read, its order's class being `FAILED_ORDER`; `streak` is a one-item list, carried
    across pairs."""
    answers = []
    for a, b in ((first, second), (second, first)):
        reply = _reply(render(config, a["text"], b["text"]), ask, memo, calls, streak)
        if reply is None:
            if streak[0] >= config["stop_after_failed_calls"]:
                return None
            answers.append((FAILED_ORDER, None))
            continue
        cls, reason = read_answer(reply, config)
        calls["unreadable"] += cls is None
        answers.append((cls, reason))
        if "decisions" in calls and cls is not None:
            calls["unsettled"] += not reason["settled"]
            calls["decisions"].append(decision_row(a, b, reason))
    return answers


def unjudged(rule_id, calls, kept):
    """The rule's not-judged row, or None when every pair was answered. `why` picks the reader's
    words, which say whether anything was kept: a stop before any call on the document, a stop with
    records kept, a stop with none, or failed calls under the stop."""
    if calls["not_asked"]:
        why, reason = calls.get("why", "too_many_passages"), calls["not_asked"]
    elif calls["stopped"]:
        reason = calls["stopped"]
        why = "pairs_not_prepared" if not calls["made"] else "pairs_partly_stopped" if kept else "failed"
    elif calls["failed"]:
        why, reason = "pairs_some_failed", "%d of %d calls failed" % (calls["failed"], calls["made"])
    elif not calls["made"] and not calls.get("reused"):
        why, reason = "pairs_none", "no pair to ask: %d passages" % calls["passages"]
    else:
        return None
    return {"unit_id": None, "rule_id": rule_id, "kind": "passage_pair", "reason": reason, "why": why,
            "consumer_agents": [], "status": "stopped"}


def review(prepared, rule, source_rule_id, ask, config, memo=None, fields_present=None, on_kept=None, contracts=None):
    """(records, calls): every pair of `prepared` put to `ask(user_text) -> reply text or None`,
    in both orders. A pair is a record only when both orders say contradict (D-S38, the view the
    measurement's bar reads) and the judged paths' refusals keep it, its two passages standing in
    one unit or in two (INFRA-047, `cross_unit_kept` counts those); every call is counted, whatever
    became of it. `memo` is {prompt: reply} of the model
    `ask` reaches, kept across rules; `fields_present` is {unit id: the fields Python parsed off
    it}, as the judged paths read it; `on_kept` is told the two prompts of each record kept.

    The declared number of failed calls in a row stops the rule. A raised failure (out of memory,
    no chat template, a masking refusal) stops it at once: what the review already holds stays,
    the rest of the document's review goes on, and `calls` names it by its type alone (`raised`)
    and says why it stopped (`stopped`). Above `max_passages` nothing is asked (`not_asked`).

    Under the `decision` form `ask` gives a decision, `reason` is no sentence of the model's, and
    `calls` adds `form`, `unsettled`, `decisions` (each order's probabilities) and `decision_notes`
    ({item id: Python's sentence}); with no measured threshold nothing is asked either, and `why`
    says so.

    `contracts` are the judge agent's (D-S55): each `check_quote` of a pair both orders flagged is one
    row of `calls["tool_rows"]` (present only once a row is kept) when its contract declares the tool, stamped with the first order's
    question. {} or None declares none, and nothing else here reads them."""
    import judge_agent
    records = []
    items, proposed = prepared["items"], prepared["pairs"]
    calls = {"passages": len(items), "pairs": 0, "made": 0, "reused": 0, "failed": 0, "unreadable": 0,
             "one_order_only": 0, "failed_beside_flag": 0, "cross_unit_kept": 0, "refused": [],
             "ranked_by": prepared["ranked_by"], "stopped": None, "raised": prepared["raised"], "not_asked": None}
    decided = deciding(config)
    if decided:
        calls.update(form=DECISION_FORM, unsettled=0, decisions=[], decision_notes={})
    if calls["raised"]:
        calls["stopped"] = "stopped by a raised %s, 0 of 0 pairs answered" % calls["raised"]
        return records, calls
    if too_many(items, config):
        calls["not_asked"] = "no pair asked: %d passages, above the declared %d" % (len(items), config["max_passages"])
        return records, calls
    if decided and threshold_of(config) is None:
        calls["not_asked"] = "no pair asked: no threshold measured for " + config["decision"]["threshold_family"]
        calls["why"] = NO_THRESHOLD_WHY
        return records, calls
    memo = {} if memo is None else memo
    text_of = {u.get("unit_id"): u.get("text") for u in prepared["units"]}
    streak = [0]
    try:
        for pair in proposed:
            first, second = items[pair["a"]], items[pair["b"]]
            answers = _both_orders(first, second, ask, config, memo, calls, streak)
            if answers is None:
                calls["stopped"] = "stopped after %d failed calls in a row, %d of %d pairs answered" % (
                    streak[0], calls["pairs"], len(proposed))
                break
            # Answered means both replies came back; a failed order leaves the pair open.
            whole = all(c != FAILED_ORDER for c, _ in answers)
            calls["pairs"] += whole
            flags = [c == "FLAG" for c, _ in answers]
            if all(flags):
                unit_id, other = first["unit_id"], second["unit_id"]
                across = other != unit_id
                item = record(first, second, rule["id"], source_rule_id, None if decided else answers[0][1])
                refusal = paired_review.judged_item_refusal(item, rule, (fields_present or {}).get(unit_id),
                                                            text_of.get(unit_id),
                                                            second_unit_text=text_of.get(other, "") if across else None)
                tool_rows = judge_agent.tool_rows(judge_agent.PASSAGE_PAIR, contracts or {}, rule["id"], unit_id,
                                                  render(config, first["text"], second["text"]),
                                                  [judge_agent.check_quote_row(refusal)])
                if tool_rows:
                    calls.setdefault("tool_rows", []).extend(tool_rows)
                if refusal:
                    calls["refused"].append({"unit_id": unit_id, "rule_id": rule["id"],
                                             "relation": item["relation"], "reason": refusal})
                    continue
                records.append(paired_review.mark_screened(item))
                calls["cross_unit_kept"] += across
                if decided:
                    calls["decision_notes"][item["item_id"]] = DECISION_NOTE % (
                        answers[0][1]["decided"], answers[0][1]["confidence"], answers[1][1]["confidence"],
                        min(answers[0][1]["declared_mass"], answers[1][1]["declared_mass"]))
                if on_kept:
                    on_kept((render(config, first["text"], second["text"]),
                             render(config, second["text"], first["text"])))
            elif any(flags):
                calls["one_order_only" if whole else "failed_beside_flag"] += 1
    except CAUGHT as exc:
        calls["raised"] = type(exc).__name__
        calls["stopped"] = "stopped by a raised %s, %d of %d pairs answered" % (
            calls["raised"], calls["pairs"], len(proposed))
    return records, calls
