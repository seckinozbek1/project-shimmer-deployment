#!/usr/bin/env python3
"""The negotiation advisor's runner forms (D-605, #262; docs/loop/stages/NEG_ADVISOR_PLAN.md section 5).

Four forms, fixed in `neg_advisor_prompt.json` before any item exists:

- `advice`: one prompt per item, the same text for B1 (group `b1`, the bare base checkpoint), the
  system's advice (group `system_advice`) and the cloud reference (B1's prompts byte for byte);
- `audit`: the system's audit of its own advice by the other family (group `system_audit`), one
  narrow question per piece of advice. Its prompts are DERIVED in the pass from the system's advice
  replies, rendered by `render_audit`, so `answers` renders each again from the saved advice reply
  and holds it to the SHA-256 the pass recorded;
- `judge`: the blind grade of a counter's wording (group `judge`), built after the runs from every
  arm's answers, in one shuffled order with opaque entry ids (tools/score_neg_advisor.py judge-prompts,
  which reads the keys);
- `validate`: the role session's check of a position-to-article mapping (group `validate`;
  tools/score_neg_advisor.py validate-prompts).

A system advice group that declares `method: stepwise` (D-713) runs, on the pass, the step-wise chain in
place of its one prompt (S0: `stepwise_call`), one reply record per step, and `answers` composes the reply
again from the saved steps (`recompose_stepwise`). Off unless the prompts file's own config declares it.

    build    --set <set folder> --form advice --groups b1[,system_advice] --out <prompts.json>
    run      --prompts <prompts.json> --out <pass folder>         every prompt through its group (a GPU)
    answers  --prompts <prompts.json> --run <pass folder> --out <answers.json>
    texts    --prompts <prompts.json> --texts <prompt id to text .json> --out <answers.json>   (the cloud reference)

Rides the replay pass (`replay_prompts.is_neg_advisor`); no bound controller file changed. The model of
each group is resolved by `bare_model.resolve_reader` from the registry, as for every replay pass, and
recorded in the measurement; a group that declares `model` (the judge and the validator: JUDGE's registry
`local.model` is null, so `resolve_reader` would give the active auditor, Phi-3.5) loads that model, which
must be the registry's own model of its agent (`reader_of`). Every file this tool writes is refused inside
the repository (`outside_repository`). The builder never runs this on an item: every proof is on fixtures.
Development, exposed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "scripts"
for _p in (str(SCRIPTS), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CONFIG_PATH = HERE / "neg_advisor_prompt.json"
CONFIG_SCHEMA = "neg-advisor-prompt-v1"
SCHEMA = "neg-advisor-prompts-v1"
ANSWERS_SCHEMA = "neg-advisor-answers-v1"
MEASUREMENT_SCHEMA = "neg-advisor-measurement-v1"
MEASUREMENT_FILE = "replay_measurement.json"
ITEM_SCHEMA = "neg-advisor-item-v1"
FORMS = ("advice", "audit", "judge", "validate")
GROUPS = ("b1", "system_advice", "system_audit", "judge", "validate")
CONFLICT = ("conflict", "no_conflict", "not_stated")
STANCES = ("accept", "reject", "counter")
STATES = ("closed", "dropped", "bracketed", "new", "binding")
AUDIT = ("supported", "unsupported", "cannot_tell")
POSITION_STANCES = ("support", "oppose", "accept")
# D-711 item 1 (never invent): an advice entry may say what it rests on. `on_record` (also an entry that says
# nothing) is held to the positions on record; `inferred` must carry `basis_quote`, the line it rests on, which
# the scorer's Python step checks against the item's own text and never counts as on record.
ON_RECORD, INFERRED = "on_record", "inferred"
BASES = (ON_RECORD, INFERRED)
BASIS_QUOTE_MAX_CHARS = 400
# The fewest words a basis line holds (the plan's 5-gram, NGRAM in tools/score_neg_advisor.py): a shorter
# line would be found in almost any text and support nothing.
BASIS_QUOTE_MIN_WORDS = 5
JUDGE_SEED = 20261113
AGENT_LABEL = "NEG_ADVISOR"
PHASE = "NEG_ADVISOR"
# The plan's section 3.1 token budget: the whole advice prompt, by the B1 model's own tokenizer and chat
# template, at most this many tokens, so the 2,048-token allowance fits inside its 32,768 positions.
TOKEN_LIMIT = 24000
TOKENIZER = "Qwen/Qwen2.5-7B-Instruct"
# What the judge must never see (plan section 6.3): a citation id of the item, in any wording it grades.
CITATION_ID = re.compile(r"\b(?:PAR|POS|LAY)-\d+\b|\bP-[A-Za-z0-9.]+-\d+\b")
# The fields load_prompts holds each prompt to (its rendering, its digest, no system turn, its allowance).
HELD_FIELDS = ("user", "user_sha256", "system", "max_new_tokens")
JUDGED_FATES = ("changed", "kept")
# The build file's and the item's terms-of-use field and its attribution field (plan section 10). The
# field's name is declared here, under benchmark/, where the vocabulary probe (check 174) does not read:
# the code under tools/ names it only through this constant, so its own text carries no such word.
TERMS_FIELD = "licence"
ATTRIBUTION_FIELD = "attribution"
# D-664 item 2: every red line carries its source. For now only the document (v1.1 adds the operator's mandate);
# a build may give a red line as a position id (from the document) or as {"position", "source"}.
RED_LINE_SOURCES = ("from the document",)
OPERATOR_SOURCE = "given by the operator"      # #278 (D-848): red lines the operator declares for the advised party
OPERATOR_SCHEMA = "neg-operator-red-lines-v1"
# D-666 item 2: the document layers the advisor takes in, as the reader returns them apart (scripts/docx_layers.py,
# scripts/pdf_layers.py, scripts/html_layers.py): each entry its layer kind, its text, its author and, for a
# comment, the text it is anchored on. Each carries an id `LAY-<n>`, so a reason can cite it.
LAYER_KINDS = ("insertion", "deletion", "comment", "footnote", "endnote", "annotation")
LAYER_ID = "LAY-%d"
# D-668 gap 4: how a non-persona party moved toward or away from the persona over the rounds on record.
MOVEMENTS = ("toward", "away", "steady", "not_stated")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _norm(text):
    return " ".join(str(text or "").lower().replace(".", " ").split())


def outside_repository(path):
    """Refuse a path inside the repository: items, per-item rows, prompts, passes and answers never live
    there (plan section 9). The root is read at call time, so a proof can move it."""
    p = Path(path).resolve()
    try:
        p.relative_to(Path(ROOT).resolve())
    except ValueError:
        return p
    raise ValueError("refused: a negotiation advisor file may not be written inside the repository")


# ---------------------------------------------------------------------------
# the config


# D-617: the validate form's versions. 1 (round 1, validate_p01) asked for "the article id"; 2 lists the
# item's article ids and asks for exactly one of them. A config without `form_version` is version 1, so
# round-1 prompts files and records still read.
VALIDATE_FORMS = (1, 2)
VALIDATE_IDS_SEPARATOR = ", "


def validate_form_version(config):
    version = ((config or {}).get("validate") or {}).get("form_version", 1)
    if version not in VALIDATE_FORMS:
        raise ValueError("the validate form version is one of %s" % (VALIDATE_FORMS,))
    return version


def article_ids(item):
    """The ids the validator may answer for an item, in the excerpt's order (D-617): ids only, never a
    heading."""
    return [a["id"] for a in item.get("articles") or []]


def check_config(value):
    if not isinstance(value, dict) or value.get("schema") != CONFIG_SCHEMA:
        raise ValueError("not a negotiation advisor prompt config (%s)" % CONFIG_SCHEMA)
    slots = {"advice": ("{persona}", "{round}", "{process}", "{mandate}", "{positions}", "{parties}", "{articles}",
                        "{round_index}", "{previous_index}", "{trades}", "{instructions}"),
             "audit": ("{proposal_id}", "{proposal}", "{stance}", "{conflict}", "{wording}", "{cited}"),
             "judge": ("{proposal}", "{mandate}", "{wording}", "{next}"),
             "validate": ("{articles}", "{party}", "{round}", "{quote}", "{article}", "{proposal}", "{stance}")
                         + (("{article_ids}",) if validate_form_version(value) >= 2 else ())}
    for form, needed in slots.items():
        block = value.get(form)
        if not isinstance(block, dict) or not isinstance(block.get("template"), str):
            raise ValueError("the config declares a %s template" % form)
        for slot in needed:
            if block["template"].count(slot) != 1:
                raise ValueError("the %s template fills %s once" % (form, slot))
        if type(block.get("max_new_tokens")) is not int or block["max_new_tokens"] <= 0:
            raise ValueError("the %s form declares a positive max_new_tokens" % form)
    for method in ALLOWANCE_METHODS:
        block = (value["advice"].get("methods") or {}).get(method)
        if block is None or (method != PLAIN and isinstance(block, dict) and "max_new_tokens" not in block):
            continue
        if not isinstance(block, dict) or type(block.get("max_new_tokens")) is not int or block["max_new_tokens"] <= 0:
            raise ValueError("the %s method declares a positive max_new_tokens (D-725, D-740)" % method)
    for slot in ("{persona}", "{round}", "{table}", "{threshold}", "{parties}", "{issues}", "{instructions}"):
        if str(value["advice"].get("game_template")).count(slot) != 1:
            raise ValueError("the game template fills %s once" % slot)
    answers = value["audit"].get("answers")
    if not isinstance(answers, dict) or sorted(answers) != sorted(AUDIT):
        raise ValueError("the audit form declares its three answers once each")
    seen = set()
    for spellings in answers.values():
        normed = {_norm(s) for s in spellings}
        if normed & seen:
            raise ValueError("an audit spelling is declared twice")
        seen |= normed
    groups = value.get("models")
    if not isinstance(groups, list) or sorted(g.get("group") for g in groups) != sorted(GROUPS):
        raise ValueError("the config declares the five model groups once each")
    for g in groups:
        if not (g.get("backend") in ("local_auditor", "local_producer") and isinstance(g.get("agent"), str)
                and g.get("checkpoint") in ("base", "tuned")):
            raise ValueError("a model group needs a local backend, an agent and a checkpoint")
        if "model" in g and not (isinstance(g["model"], str) and g["model"].strip()):
            raise ValueError("a model group's declared model is a model id")
    for name in ("judge", "validate"):
        if not {g["group"]: g for g in groups}[name].get("model"):
            raise ValueError("the %s group declares its model (Phi-4, the registry's model of JUDGE)" % name)
    return value


def load_config(path=CONFIG_PATH):
    return check_decoding(check_config(json.loads(Path(path).read_text(encoding="utf-8"))))


def _fill(template, slots):
    """One pass over the template, so text holding a slot's name is never read as a slot."""
    out, rest = [], template
    while True:
        hits = [(rest.find(k), k) for k in slots if rest.find(k) >= 0]
        if not hits:
            out.append(rest)
            return "".join(out)
        at, key = min(hits)
        out.append(rest[:at] + str(slots[key]))
        rest = rest[at + len(key):]


# ---------------------------------------------------------------------------
# rendering


def party_text(party):
    """A party as the prompt names it: its id and kind, and a coalition's declared members (D-668 gap 6)."""
    if party.get("members"):
        return "%s (%s of %s)" % (party["id"], party["kind"], ", ".join(party["members"]))
    return "%s (%s)" % (party["id"], party["kind"])


def layer_line(entry):
    """One document layer entry as the prompt shows it (D-666): its id, kind, author and anchor, then its text."""
    who = " by %s" % entry["author"] if entry.get("author") else ""
    on = ' on "%s"' % entry["anchor"] if entry.get("anchor") else ""
    return "- %s, %s%s%s: %s" % (entry["id"], entry["layer"], who, on, entry["text"])


def _layer_block(head, entries):
    return ("\n" + head + "\n" + "\n".join(layer_line(e) for e in entries)) if entries else ""


def render_advice(config, item, method=None):
    a = config["advice"]
    method = method or PLAIN
    persona = item["persona"]
    by_id = {p["id"]: p for p in item["parties"]}
    who = party_text(dict(by_id.get(persona["id"]) or {}, id=persona["id"], kind=persona["kind"]))
    parties = ", ".join(party_text(p) for p in item["parties"])
    if item.get("game"):
        g = item["game"]
        table = "\n".join("- %s: %s" % (issue, ", ".join("%s %s" % (o, s) for o, s in sorted(opts.items())))
                          for issue, opts in sorted(g["persona_table"].items()))
        issues = "\n".join("- %s: %s" % (i["id"], ", ".join(i["options"])) for i in g["issues"])
        return _fill(a["game_template"], {"{persona}": who, "{round}": item["round"], "{table}": table,
                                          "{threshold}": g["persona_threshold"], "{parties}": parties,
                                          "{issues}": issues, "{instructions}": a["game_instructions"]})
    red = set(persona.get("red_lines") or [])

    def line(p):
        where = p["article"] + ("" if p.get("proposal") is None else " proposal %d" % p["proposal"])
        mark = " RED LINE" if p["id"] in red else ""
        # D-668 gap 6: a position a member stated on behalf of its coalition is the coalition's; who said it is shown.
        party = p["party"] + (", said by %s" % p["speaker"] if p.get("speaker") else "")
        return "- %s%s, %s, round %s, on %s: %s" % (p["id"], mark, party, p["round"], where, p["quote"])
    mandate = "\n".join(line(p) for p in item["positions"] if p["party"] == persona["id"]) or "(none on record)"
    others = "\n".join(line(p) for p in item["positions"] if p["party"] != persona["id"]) or "(none on record)"
    layers = item.get("layers") or []
    blocks = []
    for art in item["articles"]:
        head = "ARTICLE %s: %s%s" % (art["id"], art["title"], " (agreed)" if art.get("agreed") else "")
        paras = "\n".join("%s: %s" % (p["id"], p["text"]) for p in art["paragraphs"])
        props = "\n".join("%s: %s" % (p["id"], p["text"]) for p in art["proposals"])
        # D-666: the document's own layers on this article (comments, tracked changes, notes), each apart.
        notes = _layer_block("NOTES AND CHANGES IN THE DOCUMENT ON THIS ARTICLE:",
                             [e for e in layers if e.get("article") == art["id"]])
        blocks.append(head + "\n" + paras + ("\nPROPOSALS:\n" + props if props else "") + notes)
    rest = _layer_block("NOTES AND CHANGES IN THE DOCUMENT OUTSIDE THESE ARTICLES:",
                        [e for e in layers if e.get("article") is None])
    if rest:
        blocks.append(rest.lstrip("\n"))
    if item.get("layers_not_read"):
        blocks.append("LAYERS OF THE DOCUMENT THE READER COULD NOT READ: %s" % ", ".join(item["layers_not_read"]))
    index = lambda rows: ", ".join("%s %s" % (r["id"], r["title"]) for r in rows) or "(none)"
    trades = "; ".join("%s: give %s for %s, round %s" % (t["id"], t["give"], t["get"], t["round"])
                       for t in item.get("trades_on_record") or []) or "(none)"
    return _fill(a["template"], {"{persona}": who, "{round}": item["round"], "{process}": item["process"],
                                 "{mandate}": mandate, "{positions}": others, "{parties}": parties,
                                 "{articles}": "\n\n".join(blocks), "{round_index}": index(item["round_index"]),
                                 "{previous_index}": index(item["previous_index"]), "{trades}": trades,
                                 "{instructions}": a["instructions"] + method_instructions(config, method)})


def item_ids(item):
    """(passage ids, position ids, proposal ids, article ids) of an item; the passages are its paragraphs and
    its document layer entries (D-666), both citable as a reason."""
    pars = {p["id"] for a in item.get("articles") or [] for p in a["paragraphs"]}
    pars |= {e["id"] for e in item.get("layers") or []}
    poss = {p["id"] for p in item.get("positions") or []}
    props = {p["id"] for a in item.get("articles") or [] for p in a["proposals"]}
    arts = {a["id"] for a in item.get("articles") or []}
    return pars, poss, props, arts


def proposal_text(item, pid):
    for a in item.get("articles") or []:
        for p in a["proposals"]:
            if p["id"] == pid:
                return p["text"]
    return None


def cited_text(item, ids):
    texts = {p["id"]: p["text"] for a in item.get("articles") or [] for p in a["paragraphs"]}
    texts.update({p["id"]: "%s, round %s: %s" % (p["party"], p["round"], p["quote"]) for p in item.get("positions") or []})
    texts.update({e["id"]: layer_line(e)[len("- %s, " % e["id"]):] for e in item.get("layers") or []})
    return "\n".join("- %s: %s" % (i, texts[i]) for i in ids if i in texts) or "(nothing it cites is in the item)"


def render_audit(config, item, piece):
    return _fill(config["audit"]["template"], {
        "{proposal_id}": piece["id"], "{proposal}": proposal_text(item, piece["id"]) or "",
        "{stance}": piece["stance"], "{conflict}": piece["conflict"], "{wording}": piece.get("wording") or "(none)",
        "{cited}": cited_text(item, piece.get("reasons") or [])})


def render_judge(config, entry):
    return _fill(config["judge"]["template"], {"{proposal}": entry["proposal"], "{mandate}": entry["mandate"],
                                               "{wording}": entry["wording"], "{next}": entry["next"]})


def render_validate(config, item, position):
    arts = "\n\n".join("ARTICLE %s: %s\n%s" % (a["id"], a["title"], "\n".join(p["text"] for p in a["paragraphs"]))
                       for a in item["articles"])
    return _fill(config["validate"]["template"], {
        "{articles}": arts, "{party}": position["party"], "{round}": position["round"], "{quote}": position["quote"],
        "{article}": position["article"],
        "{proposal}": "none" if position.get("proposal") is None else position["proposal"],
        "{stance}": position["stance"], "{article_ids}": VALIDATE_IDS_SEPARATOR.join(article_ids(item))})


# ---------------------------------------------------------------------------
# D-664 red-line sources, D-666 document layers, D-668 gap 4 movement: computed in Python, never from words


def read_red_lines(declared):
    """(ids, {id: source}) of a build's red lines (D-664 item 2): each a position id, from the document, or
    {"position": id, "source": s} with s one of RED_LINE_SOURCES; anything else is refused."""
    ids, sources = [], {}
    for r in declared or []:
        if isinstance(r, str):
            pid, source = r, RED_LINE_SOURCES[0]
        elif isinstance(r, dict) and isinstance(r.get("position"), str):
            pid, source = r["position"], r.get("source", RED_LINE_SOURCES[0])
        else:
            raise ValueError("a red line is a position id or {position, source}")
        if source not in RED_LINE_SOURCES:
            raise ValueError("a red line's source is one of: %s" % ", ".join(RED_LINE_SOURCES))
        if pid in sources:
            raise ValueError("a red line is declared twice: %s" % pid)
        ids.append(pid)
        sources[pid] = source
    return ids, sources


def operator_red_lines(item):
    """#278 (D-848): the red lines the operator declared for the item's advised party, each {id, text}, checked;
    none when none was declared (`persona.operator_red_lines`, put there at build time from the operator's file)."""
    lines = item["persona"].get("operator_red_lines") or []
    if not isinstance(lines, list) or not all(isinstance(r, dict) and isinstance(r.get("id"), str) and r["id"] and
                                              isinstance(r.get("text"), str) and r["text"].strip() for r in lines):
        raise ValueError("an operator red line is {id, text}")
    if len({r["id"] for r in lines}) != len(lines):
        raise ValueError("an operator red line id repeats")
    return [{"id": r["id"], "text": " ".join(r["text"].split())} for r in lines]


def party_red_lines(item):
    """D-848, for the difference check (#309) and the chain: the advised party's red lines for one item, declared
    ones only: those the record marks (its positions in `persona.red_lines`, each with its source) and those the
    operator gave (#278). Each {id, text, source, round, article}; nothing is read from words (WORDS-A)."""
    persona = item["persona"]
    by_id = {p["id"]: p for p in item.get("positions") or []}
    out = [{"id": pid, "text": by_id[pid]["quote"], "source": red_line_source(persona, pid),
            "round": by_id[pid].get("round"), "article": by_id[pid].get("article")}
           for pid in persona.get("red_lines") or [] if pid in by_id and by_id[pid]["party"] == persona["id"]]
    return out + [dict(r, source=OPERATOR_SOURCE, round=None, article=None) for r in operator_red_lines(item)]


def with_operator_red_lines(item, table):
    """A copy of `item` with the operator's red lines for it (`table`: the operator file's items, by item id)."""
    import copy as _copy
    out = _copy.deepcopy(item)
    lines = (table or {}).get(item["item_id"])
    if lines:
        out["persona"]["operator_red_lines"] = lines
        operator_red_lines(out)
    return out


def read_operator_file(path):
    """The operator's red lines file (#278): {schema, items: {item id: [{id, text}]}}; None for no path."""
    if path is None:
        return None
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema") != OPERATOR_SCHEMA or not isinstance(value.get("items"), dict):
        raise ValueError("not an operator red lines file (%s)" % OPERATOR_SCHEMA)
    return value["items"]


def red_line_source(persona, position_id):
    """The source of one of the persona's red lines (D-664); None when the position is no red line. An item
    built before the field holds no sources: its red lines are from the document, the only source there was."""
    if position_id not in set(persona.get("red_lines") or []):
        return None
    return (persona.get("red_line_sources") or {}).get(position_id) or RED_LINE_SOURCES[0]


_READER_LAYERS = (("insertions", "insertion"), ("deletions", "deletion"), ("comments", "comment"),
                  ("footnotes", "footnote"), ("endnotes", "endnote"))


def layers_from_reader(reading):
    """D-666 item 2: the build's layer entries from what the document reader returns apart, never from words.
    `reading` is a .docx reading (scripts/docx_layers.read_layers: insertions, deletions, comments with their
    anchors, footnotes, endnotes, and its layer record), a PDF or HTML reading (pdf_layers / html_layers: its
    `items`, annotations or changes, and its `record`), or a list of such items. Returns {"layers": [{layer,
    text, author, anchor, article: None}], "empty": entries with no text left out, "not_read": the record's
    lost layers}; the set builder places each entry on its article (or leaves it None, outside the excerpt)."""
    out, empty = [], 0

    def put(kind, text, author, anchor=""):
        nonlocal empty
        text = " ".join(str(text or "").split())
        if not text:
            empty += 1
            return
        out.append({"layer": kind, "text": text, "author": str(author or ""), "anchor": " ".join(str(anchor or "").split()),
                    "article": None})
    record = None
    if isinstance(reading, dict) and any(k in reading for k, _kind in _READER_LAYERS):
        for key, kind in _READER_LAYERS:
            for r in reading.get(key) or []:
                put(kind, r.get("text"), r.get("author"), r.get("anchor") if kind == "comment" else "")
        record = reading.get("record")
    else:
        items = getattr(reading, "items", reading)
        record = getattr(reading, "record", None)
        for r in items or []:
            kind = r.get("layer")
            if kind not in LAYER_KINDS:
                raise ValueError("a reader item's layer is one of %s" % ", ".join(LAYER_KINDS))
            put(kind, r.get("note") if kind == "annotation" else r.get("text"), r.get("author"))
    return {"layers": out, "empty": empty, "not_read": list((record or {}).get("lost") or [])}


def _sign_of(stances):
    s = {1 if x in ("support", "accept") else -1 for x in stances}
    return s.pop() if len(s) == 1 else 0


def party_movement(positions, persona, party, article, numbers):
    """D-668 gap 4: how `party` moved relative to the persona on one article over the rounds on record. Per
    round in which the party holds a position on the article, its relation to the persona (same or opposite
    sign, proposal by proposal by the plan's `applicable`, the persona's sign over all its rounds), kept when
    every proposal they share agrees; then the first and last such round: toward (opposite, then same), away
    (same, then opposite), steady, or not_stated (fewer than two rounds with a relation). From the declared
    stances and rounds alone."""
    rounds = sorted({p["round"] for p in positions if p["party"] == party and p["article"] == article})
    relations = []
    for rnd in rounds:
        in_round = [p for p in positions if p["round"] == rnd]
        rel = set()
        for n in numbers or [None]:
            mine = _sign_of([p["stance"] for p in _applicable(positions, persona, article, n)])
            theirs = _sign_of([p["stance"] for p in _applicable(in_round, party, article, n)])
            if mine and theirs:
                rel.add(mine == theirs)
        if len(rel) == 1:
            relations.append(rel.pop())
    if len(relations) < 2:
        return "not_stated"
    first, last = relations[0], relations[-1]
    return "steady" if first == last else ("toward" if last else "away")


def movement_map(item, positions):
    """{article: {party: movement}} over every party but the persona (D-668 gap 4), from `positions` with their
    stances: the build's declared stances for the key, the stances the step-wise chain had checked for the
    system's advice (an item's own positions carry no stance)."""
    persona = item["persona"]["id"]
    return {art["id"]: {p["id"]: party_movement(positions, persona, p["id"], art["id"],
                                                list(range(1, len(art["proposals"]) + 1)))
                        for p in item["parties"] if p["id"] != persona}
            for art in item.get("articles") or []}


# ---------------------------------------------------------------------------
# reading replies


def _json_object(text):
    if not isinstance(text, str):
        return None
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _ids(value):
    return [str(v) for v in value] if isinstance(value, list) and all(isinstance(v, (str, int)) for v in value) else None


def _one_id(value):
    """One id as a string: a JSON integer is read as its text, as `_ids` reads a list (role N session 23: the
    system wrote 7 article ids as numbers equal to a known id). Any other type stays as it is and is not known."""
    return str(value) if isinstance(value, int) and not isinstance(value, bool) else value


def parse_advice(text, item):
    """The reply read by the schema of the plan's section 5.1, or None when it does not parse. Unknown ids
    are dropped and counted (`unknown_ids`); a field outside its declared values is left out of its entry, so
    the scorer reads it as no_answer."""
    value = _json_object(text)
    if value is None:
        return None
    unknown = 0
    if item.get("game"):
        g = item["game"]
        options = {i["id"]: set(i["options"]) for i in g["issues"]}
        deal = value.get("deal") if isinstance(value.get("deal"), dict) else {}
        clean = {k: str(v) for k, v in deal.items() if k in options and str(v) in options[k]}
        unknown += len(deal) - len(clean)
        trades = []
        for t in value.get("trades") if isinstance(value.get("trades"), list) else []:
            if isinstance(t, dict) and t.get("give") in options and t.get("get") in options:
                trades.append({"give": t["give"], "get": t["get"]})
            else:
                unknown += 1
        return {"deal": clean, "trades": trades, "unknown_ids": unknown}
    pars, poss, props, arts = item_ids(item)
    known_articles = arts | {r["id"] for r in item.get("previous_index") or []}
    parties = {p["id"] for p in item["parties"]}
    proposals = {}
    for e in value.get("proposals") if isinstance(value.get("proposals"), list) else []:
        if not isinstance(e, dict) or _one_id(e.get("id")) not in props or _one_id(e["id"]) in proposals:
            unknown += 1
            continue
        reasons = _ids(e.get("reasons")) or []
        entry = {"id": _one_id(e["id"]), "reasons": reasons}
        if e.get("conflict") in CONFLICT:
            entry["conflict"] = e["conflict"]
        if e.get("stance") in STANCES:
            entry["stance"] = e["stance"]
        if isinstance(e.get("wording"), str) and e["wording"].strip():
            entry["wording"] = e["wording"].strip()
        if e.get("basis") in BASES:
            entry["basis"] = e["basis"]
        if isinstance(e.get("basis_quote"), str) and e["basis_quote"].strip():
            entry["basis_quote"] = e["basis_quote"].strip()
        if isinstance(e.get("rationale"), str) and e["rationale"].strip():
            entry["rationale"] = e["rationale"].strip()   # D-713: kept apart, never scored
        proposals[entry["id"]] = entry
    trades = []
    for t in value.get("trades") if isinstance(value.get("trades"), list) else []:
        if isinstance(t, dict) and isinstance(t.get("give"), str) and isinstance(t.get("get"), str):
            trades.append({"give": t["give"], "get": t["get"]})
        else:
            unknown += 1
    approach = [p for p in (_ids(value.get("approach")) or []) if p in parties]
    unknown += len(_ids(value.get("approach")) or []) - len(approach)
    alignment = {}
    for e in value.get("alignment") if isinstance(value.get("alignment"), list) else []:
        if not isinstance(e, dict) or _one_id(e.get("article")) not in arts:
            unknown += 1
            continue
        alignment[_one_id(e["article"])] = {"aligned": [p for p in (_ids(e.get("aligned")) or []) if p in parties],
                                   "opposed": [p for p in (_ids(e.get("opposed")) or []) if p in parties]}
        if e.get("basis") in BASES:
            alignment[_one_id(e["article"])]["basis"] = e["basis"]
        if isinstance(e.get("basis_quote"), str) and e["basis_quote"].strip():
            alignment[_one_id(e["article"])]["basis_quote"] = e["basis_quote"].strip()
    state = {}
    for e in value.get("state") if isinstance(value.get("state"), list) else []:
        if isinstance(e, dict) and _one_id(e.get("article")) in known_articles and e.get("state") in STATES:
            state[_one_id(e["article"])] = e["state"]
        else:
            unknown += 1
    return {"proposals": proposals, "trades": trades, "approach": approach, "alignment": alignment, "state": state,
            "unknown_ids": unknown}


def parse_audit(text, config):
    if not isinstance(text, str) or not text.strip():
        return None
    said = _norm(text.strip().splitlines()[0])
    for label, spellings in config["audit"]["answers"].items():
        if said in {_norm(s) for s in spellings}:
            return label
    return None


JUDGE_GRADE = re.compile(r"([012])(?![0-9])")


def parse_judge(text):
    # The grade is the reply's leading digit, 0, 1 or 2, as the plan's section 6.3 asks; text after it is
    # ignored (Phi-4 goes on after the digit within max_new_tokens 4: role N session 19, 15 Nov). A reply
    # that does not open with one of the three digits, or opens with a longer number, is not a grade.
    if not isinstance(text, str):
        return None
    found = JUDGE_GRADE.match(text.strip())
    return int(found.group(1)) if found else None


def parse_validate(text):
    value = _json_object(text)
    if value is None or not isinstance(value.get("article"), str) or value.get("stance") not in POSITION_STANCES:
        return None
    proposal = value.get("proposal")
    if proposal is not None and type(proposal) is not int:
        return None
    return {"article": value["article"], "proposal": proposal, "stance": value["stance"]}


# ---------------------------------------------------------------------------
# prompts files


def read_items(set_dir):
    """Every item.json under <set>/items, by item id. Never a key."""
    items = {}
    for path in sorted((Path(set_dir) / "items").glob("*/item.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if item.get("schema") != ITEM_SCHEMA:
            raise ValueError("not an advisor item: %s" % path.parent.name)
        items[item["item_id"]] = item
    if not items:
        raise ValueError("no items under %s" % (Path(set_dir) / "items"))
    return items


def _file(config, prompts, extra=None):
    value = {"schema": SCHEMA, "config": config, "config_sha256": _sha(_canonical(config)),
             "prompt_count": len(prompts), "prompts": prompts}
    value.update(extra or {})
    return value


def read_subset(path):
    """(item ids, SHA-256) of a cloud_subset.json (tools/score_neg_advisor.py cloud_subset, D-606)."""
    data = Path(path).read_bytes()
    value = json.loads(data.decode("utf-8"))
    if value.get("schema") != "neg-advisor-cloud-subset-v1" or not isinstance(value.get("items"), list):
        raise ValueError("not a negotiation advisor cloud subset")
    return list(value["items"]), hashlib.sha256(data).hexdigest()


def build(set_dir, form, groups, out, *, config_path=CONFIG_PATH, positions=None, subset=None, stance_contexts=None):
    """The advice prompts of every item for each named group, or one validate prompt per position (the
    positions with their mapping come from the role session's build files, `positions`). With `subset`
    (a cloud_subset.json), the b1 group's prompts of the subset's items alone: the cloud reference's
    file, each prompt B1's byte for byte. With `stance_contexts` (D-756 item 5, P8: e.g. full,trimmed), the
    system's stepwise advice is built once per named arm, each prompt marked `stance_context`, so one run carries
    the arms side by side; without it nothing is marked and the file is as before."""
    out = outside_repository(out)
    config = load_config(config_path)
    declared = {g["group"]: g for g in config["models"]}
    items = read_items(set_dir)
    prompts = []
    extra = {}
    if subset is not None:
        if form != "advice" or list(groups or []) != ["b1"]:
            raise ValueError("a subset builds the cloud reference's file: the advice form, group b1 alone")
        chosen, extra["subset_sha256"] = read_subset(subset)
        if not set(chosen) <= set(items):
            raise ValueError("the cloud subset names an item the set does not hold")
        items = {i: items[i] for i in items if i in set(chosen)}
    if form == "advice":
        if not groups or any(g not in ("b1", "system_advice") for g in groups):
            raise ValueError("the advice form runs on b1 and system_advice only")
        if stance_contexts is not None:
            if "system_advice" not in groups or not list(stance_contexts) or \
                    len(set(stance_contexts)) != len(list(stance_contexts)):
                raise ValueError("stance contexts name each arm once, on the system's advice")
            for c in stance_contexts:
                check_stance_context(config, "system_advice", c)
        for group in groups:
            arms = list(stance_contexts) if (stance_contexts is not None and group == "system_advice") else [None]
            for arm in arms:
                for item_id, item in items.items():
                    if arm is not None and not has_chain(item):
                        # An item with no chain (a game, or no proposal) asks no stance: built once, unmarked
                        # (read as the full arm), never twice.
                        if arm != arms[0]:
                            continue
                        arm_here = None
                    else:
                        arm_here = arm
                    user = render_advice(config, item, method_of(config, group))
                    prompt = dict(declared[group], prompt_id="a%04d" % (len(prompts) + 1), form="advice",
                                  item_id=item_id, item=item, user=user, user_sha256=_sha(user), system=None,
                                  max_new_tokens=advice_allowance(config, group))
                    if arm_here is not None:
                        prompt["stance_context"] = arm_here
                    prompts.append(prompt)
        audit = "system_advice" in groups
        return _write(out, _file(config, prompts, dict(extra, audit=audit)))
    if form == "validate":
        for item_id, item in items.items():
            for pos in (positions or {}).get(item_id, []):
                user = render_validate(config, item, pos)
                prompts.append(dict(declared["validate"], prompt_id="v%04d" % (len(prompts) + 1), form="validate",
                                    item_id=item_id, item=item, position=pos, user=user, user_sha256=_sha(user),
                                    system=None, max_new_tokens=config["validate"]["max_new_tokens"]))
        return _write(out, _file(config, prompts, {"audit": False, "validate_form_version": validate_form_version(config)}))
    raise ValueError("build makes the advice or the validate form; the judge form is `judge`")


def rebuild(prompts_path, out, *, config_path, operator_path=None):
    """The advice prompts of an existing prompts file built again under another declared config (a round's switch
    copy): the same items, prompt ids, groups and stance contexts, each prompt rendered again from its own item, so a
    set already built (and its key held apart) can be run under a new switch with no new set build. The source is
    held to its own SHA-256 and checks (load_prompts); its digest is kept as `rebuilt_from`. Advice form only."""
    out = outside_repository(out)
    source = Path(prompts_path)
    value = read_file(source)
    config = load_config(config_path)
    table = read_operator_file(operator_path)
    declared = {g["group"]: g for g in config["models"]}
    prompts = []
    for p in value["prompts"]:
        if p.get("form") != "advice" or p["group"] not in declared:
            raise ValueError("rebuild makes the advice form of a declared group only: %s" % p.get("prompt_id"))
        arm = check_stance_context(config, p["group"], p.get("stance_context"))
        item = with_operator_red_lines(p["item"], table)
        user = render_advice(config, item, method_of(config, p["group"]))
        prompt = dict(declared[p["group"]], prompt_id=p["prompt_id"], form="advice", item_id=p["item_id"],
                      item=item, user=user, user_sha256=_sha(user), system=None,
                      max_new_tokens=advice_allowance(config, p["group"]))
        if arm is not None:
            prompt["stance_context"] = arm
        prompts.append(prompt)
    extra = {k: value[k] for k in ("subset_sha256",) if k in value}
    extra.update(audit=any(p["group"] == "system_advice" for p in prompts),
                 rebuilt_from=hashlib.sha256(source.read_bytes()).hexdigest())
    if operator_path is not None:
        extra["operator_red_lines_sha256"] = hashlib.sha256(Path(operator_path).read_bytes()).hexdigest()
    written = _write(out, _file(config, prompts, extra))
    load_prompts(out)
    return written


def judged(piece, row):
    """True for a counter the judge grades (plan section 6.3): a counter with wording, on a proposal whose
    fate is changed or kept. One rule for the judge's entries and for M9's withheld counters."""
    return bool(piece) and piece.get("stance") == "counter" and bool(piece.get("wording")) and row is not None \
        and row.get("fate") in JUDGED_FATES


def blind(text):
    """A text with every citation id of an item replaced, so the judge sees no PAR-, POS- or P- id."""
    return CITATION_ID.sub("[a cited passage]", str(text or ""))


def judge_entries(items, keys, arms, mandate_of):
    """The judge's entries, one per counter an arm gave on a proposal whose fate is changed or kept, each
    with an opaque id, in one shuffled order (seed JUDGE_SEED). `arms` maps an arm to its answers file's
    replies by item; `keys` the next round's text per article. The arm stays in the entry, never in the
    prompt; no citation id reaches it (`blind`)."""
    entries = []
    for arm in sorted(arms):
        for item_id, reply in sorted(arms[arm].items()):
            key, item = keys.get(item_id), items.get(item_id)
            if not reply or not key or not item or item.get("game"):
                continue
            for pid, piece in sorted(reply["proposals"].items()):
                row = key["proposals"].get(pid)
                if not judged(piece, row):
                    continue
                nxt = key["articles"][row["article"]].get("next_text") or ""
                entries.append({"arm": arm, "item_id": item_id, "proposal_id": pid,
                                "proposal": blind(proposal_text(item, pid)), "mandate": blind(mandate_of(item)),
                                "wording": blind(piece["wording"]), "next": blind(nxt)})
    rng = random.Random(JUDGE_SEED)
    rng.shuffle(entries)
    for e in entries:
        e["entry_id"] = _sha("%s|%s|%s|%d" % (e["arm"], e["item_id"], e["proposal_id"], JUDGE_SEED))[:16]
    return entries


def mandate_text(item):
    red = set(item["persona"].get("red_lines") or [])
    return "\n".join("- %s%s" % (p["quote"], " (red line)" if p["id"] in red else "")
                     for p in item["positions"] if p["party"] == item["persona"]["id"]) or "(none on record)"


def build_judge(entries, out, *, config_path=CONFIG_PATH):
    out = outside_repository(out)
    config = load_config(config_path)
    group = {g["group"]: g for g in config["models"]}["judge"]
    prompts = []
    for e in entries:
        user = render_judge(config, e)
        prompts.append(dict(group, prompt_id="j%04d" % (len(prompts) + 1), form="judge", item_id=e["item_id"],
                            entry=e, user=user, user_sha256=_sha(user), system=None,
                            max_new_tokens=config["judge"]["max_new_tokens"]))
    return _write(out, _file(config, prompts, {"audit": False}))


def _write(out, value):
    _write_json(out, value)
    return value


def is_prompts_file(value):
    return isinstance(value, dict) and value.get("schema") == SCHEMA


def load_prompts(path):
    """The prompts, each rendered again from its own inputs and held to its SHA-256."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not is_prompts_file(value) or not isinstance(value.get("prompts"), list) or not value["prompts"]:
        raise ValueError("not a negotiation advisor prompts file (%s)" % SCHEMA)
    config = check_config(value.get("config"))
    if value.get("config_sha256") != _sha(_canonical(config)):
        raise ValueError("the prompts file's config does not match its SHA-256")
    if value.get("prompt_count") != len(value["prompts"]):
        raise ValueError("the prompts file's count is wrong")
    groups = {g["group"]: g for g in config["models"]}
    ids, keys = set(), set()
    for p in value["prompts"]:
        g = groups.get(p.get("group"))
        if g is None or any(p.get(k) != g.get(k) for k in ("backend", "agent", "checkpoint", "model")):
            raise ValueError("a prompt names a model group its config does not declare: %s" % p.get("prompt_id"))
        if p.get("form") == "advice" and p["group"] in ("b1", "system_advice"):
            # D-756 item 5: a marked arm is held to the config's declarations; one (group, item) per arm.
            arm = check_stance_context(config, p["group"], p.get("stance_context"))
            user, key = render_advice(config, p["item"], method_of(config, p["group"])), (p["group"], p["item_id"], arm)
        elif p.get("form") == "validate" and p["group"] == "validate":
            user, key = render_validate(config, p["item"], p["position"]), ("validate", p["item_id"], p["position"]["id"])
        elif p.get("form") == "judge" and p["group"] == "judge":
            user, key = render_judge(config, p["entry"]), ("judge", p["entry"]["entry_id"])
        else:
            raise ValueError("a prompt names a form or group this file does not declare: %s" % p.get("prompt_id"))
        wanted = {"user": user, "user_sha256": _sha(user), "system": None,
                  "max_new_tokens": (advice_allowance(config, p["group"]) if p["form"] == "advice"
                                     else config[p["form"]]["max_new_tokens"])}
        if any(p.get(f) != wanted[f] for f in HELD_FIELDS):
            raise ValueError("a prompt is not its template's rendering: %s" % p.get("prompt_id"))
        if p["prompt_id"] in ids or key in keys:
            raise ValueError("a prompt id, or a (group, item), repeats")
        ids.add(p["prompt_id"])
        keys.add(key)
    if value.get("audit") is not (any(p["group"] == "system_advice" for p in value["prompts"])):
        raise ValueError("a file audits exactly when it holds the system's advice")
    return value["prompts"]


def read_file(path):
    load_prompts(path)
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# run (one GPU): the static prompts by group, then the system's audit prompts derived from its advice


def make_backend(reader, context):
    import bare_model
    return bare_model.LocalBackend(reader, context)


def reader_of(group, allowance, *, root=ROOT, resolve=None):
    """The reader of one model group: `bare_model.resolve_reader` from the registry, then, for a group that
    declares `model`, that model, refused unless it is the registry's own `model` of the group's agent on the
    group's backend. JUDGE's registry `local.model` is null, so resolve_reader alone gives the active auditor
    (Phi-3.5, VERIFIER's model); the judge and the validator declare Phi-4, JUDGE's model (plan 6.3)."""
    import bare_model
    reader = (resolve or bare_model.resolve_reader)(root, agent=group["agent"], checkpoint=group["checkpoint"],
                                                    max_new_tokens=allowance)
    if reader.get("backend") != group["backend"]:
        raise ValueError("group %s resolves to backend %s, not its declared %s"
                         % (group["group"], reader.get("backend"), group["backend"]))
    if group.get("model"):
        registry = json.loads((Path(root) / "config" / "agent_registry.json").read_text(encoding="utf-8"))
        entry = registry["agents"][group["agent"]]
        if entry.get("model") != group["model"] or (entry.get("local") or {}).get("backend") != group["backend"]:
            raise ValueError("group %s declares %s, not the registry's model of %s on %s"
                             % (group["group"], group["model"], group["agent"], group["backend"]))
        reader = dict(reader, model_id=group["model"],
                      sources=dict(reader.get("sources") or {}, model="neg_advisor_prompt.json group %s: the registry's "
                                   "model of %s" % (group["group"], group["agent"])))
    return reader


def token_counter(name=TOKENIZER):
    """The B1 model's own token count of an advice prompt: one user turn through its chat template, as
    bare_model.LocalBackend counts it. The tokenizer alone is loaded, from the local cache, no model."""
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(name, local_files_only=True, trust_remote_code=False)
    return lambda user: len(tok.apply_chat_template([{"role": "user", "content": user}], tokenize=True,
                                                    add_generation_prompt=True))


def audit_prompts(config, prompt, text, reply=None):
    """The derived audit prompts of one system advice reply: one per piece of advice that parses. A
    step-wise reply (composed by Python from the checked steps, `reply`) is audited the same way."""
    reply = parse_advice(text, prompt["item"]) if reply is None else reply
    if reply is None or prompt["item"].get("game"):
        return []
    group = {g["group"]: g for g in config["models"]}["system_audit"]
    out = []
    for pid, piece in sorted(reply["proposals"].items()):
        if "stance" not in piece or "conflict" not in piece:
            continue
        user = render_audit(config, prompt["item"], piece)
        out.append(dict(group, prompt_id="%s-audit-%s" % (prompt["prompt_id"], pid), form="audit",
                        item_id=prompt["item_id"], derived_from=prompt["prompt_id"], proposal_id=pid, user=user,
                        user_sha256=_sha(user), max_new_tokens=config["audit"]["max_new_tokens"]))
    # P5 (lane/neg-optional): one second-family question per candidate of a no_conflict proposal, the chosen
    # sentence shown; only a chain under a declared auditor_band writes candidates.
    for pid, piece in sorted(reply["proposals"].items()):
        if piece.get("conflict") != "no_conflict" or not piece.get("auditor_candidates"):
            continue
        template = config["advice"]["methods"][STEPWISE]["auditor"]
        for c in piece["auditor_candidates"]:
            user = _fill(template, {"{proposal_id}": pid, "{proposal}": proposal_text(prompt["item"], pid) or "",
                                    "{party}": c["party"], "{sentence}": c["sentence"]})
            out.append(dict(group, prompt_id="%s-caudit-%s-%s" % (prompt["prompt_id"], pid, c["position"]),
                            form="audit", kind=CONFLICT_AUDIT, item_id=prompt["item_id"],
                            derived_from=prompt["prompt_id"], proposal_id=pid, position_id=c["position"], user=user,
                            user_sha256=_sha(user), max_new_tokens=config["audit"]["max_new_tokens"]))
    return out


# ---------------------------------------------------------------------------
# output side (D-672, D-663 (b)): Shimmer's own advisor groups only


# A group declares how its answer is produced. `decide_by: choice` (the judge's grade, the auditor's answer)
# decides from the model's next-token probabilities over the form's declared `choice_answers`, with no
# text (CHOICE-A, scripts/choice_decision.py); `constraint: schema` (the system's advice, the validator's
# mapping) generates under a logits constraint built from the item's own ids and the declared enums
# (DECODING-B, scripts/schema_decoding.py). B1 and the cloud reference declare neither and generate freely.
DECIDE_BY_CHOICE = "choice"
SCHEMA_CONSTRAINT = "schema"
CHOICE_GROUPS = {"judge": "judge", "system_audit": "audit"}
SCHEMA_GROUPS = {"system_advice": "advice", "validate": "validate"}
WORDING_MAX_CHARS = 1500
# Lane neg-round1 (standing order 102): the advice's reasons list holds at most this many ids, so one entry per
# proposal fits the 2,048-token allowance (the pilot's free replies listed up to 37 PAR ids for one piece).
REASONS_MAX = 8


def check_decoding(config):
    """The groups' declarations, refused unless each is on a group of Shimmer's own that may carry it, the
    choice forms declare their answers and a threshold, and B1 declares neither."""
    for g in config["models"]:
        group = g["group"]
        if g.get("decide_by") is not None:
            if g["decide_by"] != DECIDE_BY_CHOICE or group not in CHOICE_GROUPS:
                raise ValueError("group %s may not decide by %r" % (group, g["decide_by"]))
            block = config[CHOICE_GROUPS[group]]
            answers = block.get("choice_answers")
            if not isinstance(answers, list) or len(answers) < 2 or \
                    not all(isinstance(a, dict) and a.get("label") and a.get("surface") for a in answers):
                raise ValueError("the %s form declares its choice answers" % CHOICE_GROUPS[group])
            t = block.get("choice_threshold")
            if not (type(t) in (int, float) and 0 <= t <= 1):
                raise ValueError("the %s form declares its choice threshold" % CHOICE_GROUPS[group])
        if g.get("constraint") is not None:
            if g["constraint"] != SCHEMA_CONSTRAINT or group not in SCHEMA_GROUPS:
                raise ValueError("group %s may not carry the constraint %r" % (group, g["constraint"]))
        if g.get("method") is not None:
            if g["method"] not in METHODS or group != METHOD_GROUP:
                raise ValueError("group %s may not declare the method %r (D-713: one of %s, on %s alone)"
                                 % (group, g["method"], ", ".join(METHODS), METHOD_GROUP))
            if g["method"] != PLAIN and not isinstance((config["advice"].get("methods") or {}).get(g["method"]), dict):
                raise ValueError("the advice form declares the method %s" % g["method"])
            if g["method"] == STEPWISE:
                block = config["advice"]["methods"][STEPWISE]
                t = block.get("choice_threshold")
                if type(block.get("max_new_tokens")) is not int or block["max_new_tokens"] <= 0 or \
                        not (type(t) in (int, float) and 0 <= t <= 1):
                    raise ValueError("the stepwise method declares its step allowance and its choice threshold")
                check_stepwise_block(block)
    return config


def step_order(block):
    """The chain's declared order (GENERATED_FIRST when none is declared)."""
    return block.get("order") or GENERATED_FIRST


def check_stepwise_block(block):
    """D-756 items 5 and 6: the declared order is one of ORDERS; under choice_first each choice-first template is
    declared and none shows `{changes}` (no line is generated yet when it is asked); a declared trimmed stance
    template fills each of TRIMMED_SLOTS once and shows nothing of `{changes}`, `{article}` or `{title}`."""
    if step_order(block) not in ORDERS:
        raise ValueError("the stepwise order is one of %s" % ", ".join(ORDERS))
    if step_order(block) == CHOICE_FIRST:
        first = block.get("choice_first")
        if not isinstance(first, dict) or not all(isinstance(first.get(k), str) for k in CHOICE_FIRST_TEMPLATES):
            raise ValueError("the choice_first order declares its templates: %s" % ", ".join(CHOICE_FIRST_TEMPLATES))
        if any("{changes}" in first[k] for k in CHOICE_FIRST_TEMPLATES):
            raise ValueError("a choice_first template shows {changes}, which is not asked yet")
    trimmed = block.get("stance_trimmed")
    if trimmed is not None:
        if not isinstance(trimmed, str) or any(trimmed.count(s) != 1 for s in TRIMMED_SLOTS) or \
                any(s in trimmed for s in ("{changes}", "{article}", "{title}")):
            raise ValueError("the trimmed stance template fills %s once each and nothing more" % ", ".join(TRIMMED_SLOTS))
    optional_switches(block)
    return block


# ---------------------------------------------------------------------------
# lane/neg-optional (Seckin 19 November 2026 01:23, the optional ideas of D-756: P2, C2, P6, P5, C3), each behind
# its own switch in `advice.methods.stepwise`, every one off as shipped, read when the chain runs. Off, the chain
# asks exactly the questions it asked before. Every new step is a choice step (CHOICE-A); none ends a chain.
# - P2 `fate_forecast`: after a proposal's stance, one choice over `fate_answers`, shown the proposal and every
#   position on record on its article (never the trimmed context); the piece keeps `fate` marked `fate_basis`
#   inferred (D-711). One declared precedence rule, `fate_precedence`: `stance` (the stance stays, the fate sits
#   beside it) or `fate` (the stance is `fate_stance[fate]`, the earlier stance kept as `stance_from_fate`). The
#   fate never writes the conflict field.
# - C2 `conflict_question: two_checks`: each position's stance step becomes two yes/no steps, `touches` (does it
#   speak to what the proposal changes) and `holds` (would what it asks for still hold if the proposal were
#   adopted); oppose is yes then no, anything else `two_checks_otherwise`; the oppose margin is the smaller of the
#   two answers' margins toward oppose, so P3's threshold reads it as before.
# - P6 `quote_grounding`: an oppose is grounded by choosing, from the position's own sentences numbered by
#   form (scripts/sentence_split.py), the one that opposes, or 0 for none (CHOICE-A, so the quote is verbatim
#   by construction). 0 sends the oppose back to `quote_none_stance`; a refused or unaskable choice keeps the
#   oppose unground and is counted, never ending the chain.
# - P5 `auditor_band` [low, high): a persona position the chain did not read as oppose whose oppose margin lies
#   in the band is grounded as in P6 (P6 must be on); a chosen sentence makes it a candidate, and audit_prompts
#   derives one question per candidate for the second family (group system_audit, the audit's own answers). A
#   proposal flips from no_conflict to conflict only on that auditor's `supported` (auditor_flip). No cue word
#   is read: the trigger is the margin band (WORDS-A).
# - C3 `conditional_accept` {label, counts_as}: the stance step offers a fourth answer for a conditional
#   acceptance, from its own template; Python counts it as `counts_as`, declared from D-748 (labelled accept),
#   and keeps it marked on the piece. Its later-round carry-forward (open item 158) is not modelled here.
# - C4 `conflict_question: compare` (lane/neg-conflict-fix, D-806; docs/loop/stages/NEG_CONFLICT_FIX_REPORT.md):
#   the stance question asks whether a position on record "supports, opposes or accepts" a proposal, though 73 of
#   the 85 persona positions of the pilot were put on record in an earlier round than the item's (most in round
#   0), before any proposal text existed, so none can express an attitude toward it; in 1,453 saved stance steps
#   oppose was never the top answer (largest share 0.034). `compare` asks instead, per touched position, one
#   CHOICE-A question that sets what the position asks for against what the proposal would do if adopted as
#   written, both rounds shown (`{position_round}`, `{round}`), over the declared `compare_answers` (each a label,
#   named in the template, and the declared stance it counts as, exactly one of them oppose). The piece keeps the
#   label answered beside the stance it counts as; the oppose margin is the margin toward the label counting as
#   oppose, so P3's threshold reads it as before. Not with conditional_accept, not in the trimmed arm.
# - R2 `limit_read` (lane/neg-round2-candidate, D-814 round 2; docs/loop/stages/NEG_ROUND2_CANDIDATE.md): the second
#   route to a conflict, a crossed red line, is asked only of positions the build marks red lines, and no pilot item
#   marks one (0 of 24; 0 red-line steps among 2,696 saved step records), so conflict had one route, the stance
#   step. `limit_read` true reads the persona's own positions for limits: once per item, before any proposal, each
#   persona position not marked a red line is asked one CHOICE-A question from `limit` (the party, the round it was
#   put on record in and the quote, never a proposal's text, so the read does not lean on the stance or compare
#   step) over the declared `limit_answers` (each a label named in the template and whether it counts as a limit,
#   exactly one of them true). Then each proposal a position read as a limit applies to is asked `limit_cross`
#   (yes or no); a yes makes the proposal a conflict as a marked red line's yes does. The piece keeps `limit_hit`
#   and the crossed `limit_lines` marked `limit_basis` inferred (D-711: read by the model, never on record), apart
#   from the declared `red_line_hit`; the reply keeps every read in `limit_reads`. A refused read or crossing
#   check is no limit and no crossing, counted, never ending a chain. Composes with every conflict question, both
#   orders and both stance contexts; a marked red line is never read again.
# - R3 `room_fate` (lane/neg-round2-m4-m10, D-840; docs/loop/stages/NEG_ROUND2_M4_M10.md): the chain's stance was
#   counter whenever the open point step said yes, else reject on a conflict, else accept; that open point step is
#   shown the proposal's text alone (no position, no other proposal), so it cannot know whether the room will move
#   the proposal (c4pilot_1: yes 79, no 73), and reject needs both a persona conflict and that blind no, while the
#   key's fate (kept, changed, removed) is what the whole room did with the text. `room_fate` true drops the open
#   point step and asks, per proposal, one CHOICE-A question from `room_fate_text`: the proposal, the other proposals on
#   its article (`{alternatives}`, Python's list by structure, or `room_fate_alone`), and every touched position
#   with the label the chain's own compare or stance step answered for it (`{room}`, or `room_fate_none`), over the
#   declared `room_fate_answers` (each a label named in the template and the stance it sets, each of STANCES set by
#   exactly one: the plan's M4 pairs, declared before any read). The stance is the answer's; the wording is asked
#   only for a counter; the conflict field is never written by it; the piece keeps `room_fate` marked inferred. A
#   refused answer leaves the proposal without a stance, counted. Not with fate_forecast (one fate question).
# - R3b `changes_id_echo` (same lane): the `changes` template shows `{proposal_id}: {proposal}`, and the model
#   copies the line with its id in front (c4pilot_1: 111 of the 112 `not_in_the_proposal` refusals; c4val_1: 175 of
#   176), so the line is refused although its text is the proposal's, word for word. `changes_id_echo` true accepts
#   a `changes` answer that starts with exactly the proposal id the prompt showed, then a colon, and whose rest is
#   in the proposal; the rest is kept, the step marked `id_echo`. A structural read of the id Python put in the
#   prompt, never a word list; any other form is refused as before.
# - Round 3 (D-863, D-864; docs/loop/stages/NEG_ROUND3.md): the room fate's answer set had no place for a proposal
#   still in dispute (the key's `open`, about 70 percent of M10's movable class by the declared sampler), so a text
#   left on the table unchanged was "kept" and scored settled; and with no position read "against" the answer was
#   "kept" in 156 of 156 development cases, a copy of the compare reads shown in `{room}`. Two changes: the room
#   fate may declare a fourth answer setting counter (two answers set counter, accept and reject one each, nothing
#   else), and `room_unanchored` true shows each touched position in `{room}` without its "read:" label. The
#   labels are the config's, never a word list here (WORDS-A); off as shipped, round 2 configs ask exactly as before.
STANCE_QUESTION, TWO_CHECKS, COMPARE = "stance", "two_checks", "compare"
CONFLICT_QUESTIONS = (STANCE_QUESTION, TWO_CHECKS, COMPARE)
COMPARE_SLOTS = ("{proposal}", "{quote}", "{party}", "{position_round}", "{round}")
FATE_PRECEDENCES = ("stance", "fate")
YES_NO = ("yes", "no")
QUOTE_MAX_SENTENCES = 9
NO_SENTENCE = "0"
CONFLICT_AUDIT = "conflict_audit"
LIMIT_READ, LIMIT_CROSS = "limit_read", "limit_cross"
LIMIT_SLOTS = ("{party}", "{quote}", "{position_round}")
LIMIT_NEVER = ("{changes}", "{proposal}", "{proposal_id}", "{article}", "{title}")
LIMIT_CROSS_SLOTS = ("{proposal}", "{quote}")
ROOM_FATE, ROOM_FATE_TEMPLATE = "room_fate", "room_fate_text"
ROOM_FATE_SLOTS = ("{proposal}", "{alternatives}", "{room}")
# - #310 `party_frame` (lane/neg-round2-d798, D-845): no step of the chain names the party it advises, so items with
#   different personas and the same text get the same questions. `party_frame` true puts one frame before every
#   step's question, filled by Python from what the item declares alone: the advised party (`party_text`), its
#   positions on record with their rounds and articles (its interests), the other parties' positions on the
#   proposal's article (the opposing positions), and the rounds on record on that article with the parties that put
#   positions in each (the history). Nothing is chosen by a word list (WORDS-A); `party_frame_none` fills an empty
#   list. Item-level steps (R2's limit read) get the frame over the whole item.
# - #311 `reason_field` (same lane, D-845): after a proposal's stance, one generated step `reason` from
#   `reason_text` asks for two lines, the mechanism of the change and its expected effect for the advised party.
#   Python reads the two lines by their declared heads (REASON_PARTS, the form the template asks for, never a
#   meaning cue) into the piece's `reason`; a reply without both is refused with its ANSWER-FORM-A reason
#   (`no_mechanism`, `no_effect`), counted like every refused step, and only that field is dropped. Recorded and
#   reported, never a bar figure.
PARTY_FRAME_SLOTS = ("{persona}", "{interests}", "{others}", "{history}")
# - D-848 `mandate_split`: the advised party's mandate up front before every question, its red lines (declared on the
#   record and given by the operator, #278, each with its source; `party_red_lines`) apart from its bargainable points
#   (its other positions on record); each operator red line is also asked by the red_line step of every proposal,
#   and a yes makes a conflict as a marked red line does. Reading red lines out of texts stays in the beta.
MANDATE_SLOTS = ("{persona}", "{red_lines}", "{bargainable}")
REASON, REASON_PARTS, REASON_MAX_CHARS = "reason", ("mechanism", "effect"), 400
# - #3 `trade_read` (same lane, D-846): the stepwise chain's reply always held no trades (and no binding state), though
#   21 of the 64 C4 items declare trades_on_record. `trade_read` true asks, once per declared trade of the advised
#   party whose give and get are both proposals on the table, one CHOICE-A question from `trade_text` (the two
#   proposals, the trade's round and the item's) over `trade_answers` (each a label named in the template and whether
#   it keeps the trade, exactly one keeping); a kept trade is offered again in the reply's `trades`, every read kept in
#   `trade_reads` marked inferred; a refused read keeps nothing, counted. Read from the declared structure alone.
TRADE_READ, TRADE_SLOTS = "trade_read", ("{give}", "{get}", "{trade_round}", "{round}")
OPTIONAL_DEFAULTS = {"fate_forecast": False, "conflict_question": STANCE_QUESTION, "quote_grounding": False,
                     "auditor_band": None, "conditional_accept": None, "limit_read": False,
                     "room_fate": False, "changes_id_echo": False, "party_frame": False, "reason_field": False,
                     "trade_read": False, "mandate_split": False, "room_unanchored": False}
# Round 3: the one stance a second room fate answer may set (a proposal still open and one reworded both move).
ROOM_FATE_SHARED = "counter"


def _template(block, key, need=(), never=("{changes}",)):
    t = block.get(key)
    if not isinstance(t, str) or any(s not in t for s in need) or any(s in t for s in never):
        raise ValueError("the stepwise method declares its %s template (with %s, never %s)"
                         % (key, ", ".join(need) or "no slot", ", ".join(never)))
    return t


def optional_switches(block):
    """The declared optional switches of the stepwise block, each checked, every one off when not declared."""
    got = {k: (v if block.get(k) is None else block[k]) for k, v in OPTIONAL_DEFAULTS.items()}
    for k in ("fate_forecast", "quote_grounding", "limit_read", "room_fate", "changes_id_echo", "party_frame",
              "reason_field", "trade_read", "mandate_split", "room_unanchored"):
        if type(got[k]) is not bool:
            raise ValueError("advice.methods.stepwise.%s is true or false" % k)
    if got["room_unanchored"] and not got["room_fate"]:
        raise ValueError("room_unanchored changes the room fate question: it needs room_fate")
    if got["fate_forecast"]:
        _template(block, "fate", ("{proposal}", "{positions}"))
        answers = block.get("fate_answers")
        if not isinstance(answers, list) or len(answers) < 2 or len(set(answers)) != len(answers) or \
                not all(isinstance(a, str) and a for a in answers):
            raise ValueError("the fate forecast declares its answers")
        if block.get("fate_precedence") not in FATE_PRECEDENCES:
            raise ValueError("the fate forecast declares one precedence rule: %s" % ", ".join(FATE_PRECEDENCES))
        if block["fate_precedence"] == "fate":
            to = block.get("fate_stance")
            if not isinstance(to, dict) or set(to) != set(answers) or not all(v in STANCES for v in to.values()):
                raise ValueError("fate precedence maps every fate answer to one stance (fate_stance)")
    if got["conflict_question"] not in CONFLICT_QUESTIONS:
        raise ValueError("advice.methods.stepwise.conflict_question is one of %s" % ", ".join(CONFLICT_QUESTIONS))
    if got["conflict_question"] == TWO_CHECKS:
        _template(block, "touches", ("{proposal}", "{quote}"))
        _template(block, "holds", ("{proposal}", "{quote}"))
        if block.get("two_checks_otherwise") not in POSITION_STANCES or block["two_checks_otherwise"] == OPPOSE:
            raise ValueError("two_checks_otherwise is a declared stance other than oppose")
    if got["conflict_question"] == COMPARE:
        compare_answers(block)
    if got["limit_read"]:
        limit_answers(block)
    if got["room_fate"]:
        if got["fate_forecast"]:
            raise ValueError("room_fate and fate_forecast each ask a proposal's fate: declare one")
        room_fate_answers(block)
    if got["party_frame"]:
        _template(block, "party_frame_text", PARTY_FRAME_SLOTS)
        if not isinstance(block.get("party_frame_none"), str) or not block["party_frame_none"].strip():
            raise ValueError("the party frame declares party_frame_none")
    if got["trade_read"]:
        trade_answers(block)
    if got["mandate_split"]:
        _template(block, "mandate_split_text", MANDATE_SLOTS)
        if not isinstance(block.get("party_frame_none"), str) or not block["party_frame_none"].strip():
            raise ValueError("the mandate split fills an empty list with party_frame_none")
    if got["reason_field"]:
        t = _template(block, "reason_text", ("{proposal}", "{stance}"))
        if any(("%s:" % k) not in t.lower() for k in REASON_PARTS):
            raise ValueError("the reason template asks for each of %s as a line head" % ", ".join(REASON_PARTS))
    if got["quote_grounding"]:
        _template(block, "quote", ("{proposal}", "{sentences}"))
        if block.get("quote_none_stance") not in POSITION_STANCES or block["quote_none_stance"] == OPPOSE:
            raise ValueError("quote_none_stance is a declared stance other than oppose")
    band = got["auditor_band"]
    if band is not None:
        if not (isinstance(band, list) and len(band) == 2 and all(type(v) in (int, float) for v in band)
                and -1 <= band[0] < band[1] <= 1):
            raise ValueError("auditor_band is [low, high) within -1 and 1")
        if not got["quote_grounding"]:
            raise ValueError("the auditor band needs quote_grounding: a flip needs a chosen sentence")
        _template(block, "auditor", ("{proposal}", "{sentence}"))
    cond = got["conditional_accept"]
    if cond is not None:
        if not isinstance(cond, dict) or not isinstance(cond.get("label"), str) or not cond["label"] or \
                cond["label"] in POSITION_STANCES or cond.get("counts_as") not in POSITION_STANCES:
            raise ValueError("conditional_accept declares a new label and the declared stance it counts as")
        if got["conflict_question"] != STANCE_QUESTION:
            raise ValueError("conditional_accept is a fourth answer of the stance question, not of two_checks")
        _template(block, "stance_conditional", ("{proposal}", "{quote}", cond["label"]))
    return got


def compare_answers(block):
    """C4: the compare question's declared answers as (labels in declared order, {label: stance it counts as},
    the label counting as oppose). Its template fills every COMPARE_SLOTS slot and names every label; the labels
    are distinct and none is a declared stance (so a record never reads as the stance question's); each counts
    as one of POSITION_STANCES, exactly one as oppose (so, with at least two answers, another as another stance)."""
    template = _template(block, "compare", COMPARE_SLOTS)
    answers = block.get("compare_answers")
    if not isinstance(answers, list) or len(answers) < 2 or \
            not all(isinstance(a, dict) and isinstance(a.get("label"), str) and a["label"] for a in answers):
        raise ValueError("the compare question declares its answers, each a label and the stance it counts as")
    labels = tuple(a["label"] for a in answers)
    if len(set(labels)) != len(labels) or any(l in POSITION_STANCES or l != l.strip().lower() for l in labels):
        raise ValueError("the compare answers are distinct lower-case labels, none a declared stance")
    if any(a.get("counts_as") not in POSITION_STANCES for a in answers):
        raise ValueError("each compare answer counts as one of %s" % ", ".join(POSITION_STANCES))
    against = [a["label"] for a in answers if a["counts_as"] == OPPOSE]
    if len(against) != 1:
        raise ValueError("exactly one compare answer counts as oppose")
    if any(l not in template for l in labels):
        raise ValueError("the compare template names every declared answer")
    return labels, {a["label"]: a["counts_as"] for a in answers}, against[0]


def limit_answers(block):
    """R2: the limit read's declared answers as (labels in declared order, {label: counts as a limit}). Its
    template `limit` fills every LIMIT_SLOTS slot, shows none of LIMIT_NEVER (it reads the position alone, before
    any proposal) and names every label; the labels are distinct lower-case words, none a declared stance or yes or
    no; each declares `limit` true or false, exactly one true. The crossing template `limit_cross` fills
    LIMIT_CROSS_SLOTS and never shows `{changes}` (it is asked under either order)."""
    template = _template(block, "limit", LIMIT_SLOTS, LIMIT_NEVER)
    _template(block, "limit_cross", LIMIT_CROSS_SLOTS)
    answers = block.get("limit_answers")
    if not isinstance(answers, list) or len(answers) < 2 or \
            not all(isinstance(a, dict) and isinstance(a.get("label"), str) and a["label"] for a in answers):
        raise ValueError("the limit read declares its answers, each a label and whether it counts as a limit")
    labels = tuple(a["label"] for a in answers)
    if len(set(labels)) != len(labels) or \
            any(l in POSITION_STANCES or l in YES_NO or l != l.strip().lower() for l in labels):
        raise ValueError("the limit answers are distinct lower-case labels, none a declared stance, yes or no")
    if any(type(a.get("limit")) is not bool for a in answers):
        raise ValueError("each limit answer declares limit true or false")
    if sum(1 for a in answers if a["limit"]) != 1:
        raise ValueError("exactly one limit answer counts as a limit")
    if any(l not in template for l in labels):
        raise ValueError("the limit template names every declared answer")
    return labels, {a["label"]: a["limit"] for a in answers}


def room_fate_answers(block):
    """R3: the room fate's declared answers as (labels in declared order, {label: the stance it sets}). Its template
    `room_fate_text` fills every ROOM_FATE_SLOTS slot, never shows `{changes}` (asked under either order) and names every
    label; `room_fate_alone` and `room_fate_none` are declared texts; the labels are distinct lower-case words, none a
    declared stance, position stance, yes or no; each sets one of STANCES and each of STANCES is set by exactly one,
    except that round 3 (D-864) admits one fourth answer setting ROOM_FATE_SHARED (counter): a proposal still open
    and one reworded both move. Any other count, a fifth answer or an undeclared stance is refused."""
    template = _template(block, ROOM_FATE_TEMPLATE, ROOM_FATE_SLOTS)
    for k in ("room_fate_alone", "room_fate_none"):
        if not isinstance(block.get(k), str) or not block[k].strip():
            raise ValueError("the room fate declares %s" % k)
    answers = block.get("room_fate_answers")
    if not isinstance(answers, list) or \
            not all(isinstance(a, dict) and isinstance(a.get("label"), str) and a["label"] for a in answers):
        raise ValueError("the room fate declares its answers, each a label and the stance it sets")
    labels = tuple(a["label"] for a in answers)
    if len(set(labels)) != len(labels) or any(l in STANCES or l in POSITION_STANCES or l in YES_NO or
                                              l != l.strip().lower() for l in labels):
        raise ValueError("the room fate answers are distinct lower-case labels, none a stance, yes or no")
    set_by = [a.get("stance") for a in answers]
    allowed = (sorted(STANCES), sorted(STANCES + (ROOM_FATE_SHARED,)))
    if sorted(s for s in set_by if s in STANCES) not in allowed or len(set_by) not in (len(STANCES), len(STANCES) + 1) \
            or any(s not in STANCES for s in set_by):
        raise ValueError("each room fate answer sets one stance, each of %s exactly once (%s at most twice)"
                         % (", ".join(STANCES), ROOM_FATE_SHARED))
    if any(l not in template for l in labels):
        raise ValueError("the room fate template names every declared answer")
    return labels, {a["label"]: a["stance"] for a in answers}


def trade_answers(block):
    """#3: the trade read's declared answers as (labels in declared order, {label: keeps the trade}). Its template
    `trade_text` fills every TRADE_SLOTS slot, never shows `{changes}` and names every label; the labels are distinct
    lower-case words, none a stance, yes or no; exactly one keeps the trade."""
    template = _template(block, "trade_text", TRADE_SLOTS)
    answers = block.get("trade_answers")
    if not isinstance(answers, list) or len(answers) < 2 or \
            not all(isinstance(a, dict) and isinstance(a.get("label"), str) and a["label"] for a in answers):
        raise ValueError("the trade read declares its answers, each a label and whether it keeps the trade")
    labels = tuple(a["label"] for a in answers)
    if len(set(labels)) != len(labels) or any(l in STANCES or l in POSITION_STANCES or l in YES_NO or
                                              l != l.strip().lower() for l in labels):
        raise ValueError("the trade answers are distinct lower-case labels, none a stance, yes or no")
    if any(type(a.get("keeps")) is not bool for a in answers) or sum(1 for a in answers if a["keeps"]) != 1:
        raise ValueError("each trade answer declares keeps true or false, exactly one true")
    if any(l not in template for l in labels):
        raise ValueError("the trade template names every declared answer")
    return labels, {a["label"]: a["keeps"] for a in answers}


def position_sentences(quote):
    """A position's sentences, ended by form (scripts/sentence_split.py), each stripped and non-empty."""
    import sentence_split
    text = " ".join(str(quote or "").split())
    cuts = [0] + list(sentence_split.ends(text)) + [len(text)]
    return [s for s in (text[a:b].strip() for a, b in zip(cuts, cuts[1:])) if s]


def _margin_toward(probabilities, label):
    if not probabilities or label not in probabilities or len(probabilities) < 2:
        return None
    return probabilities[label] - max(v for k, v in probabilities.items() if k != label)


def auditor_flip(reply, labels):
    """(reply, counts): P5's flip, a no_conflict proposal put to conflict when the second family's answer on one
    of its candidates is `supported` (labels: (proposal id, position id) to the audit label, None unanswered); an
    accept stance becomes reject, a counter is kept. A copy; `reply` is never changed."""
    import copy as _copy
    out, counts = _copy.deepcopy(reply), Counter()
    for (pid, pos), label in sorted(labels.items()):
        counts["asked"] += 1
        piece = ((out or {}).get("proposals") or {}).get(pid)
        if label is None:
            counts["unanswered"] += 1
        elif label != "supported":
            counts["not_supported"] += 1
        elif piece is not None and piece.get("conflict") == "no_conflict":
            piece["conflict"] = "conflict"
            if piece.get("stance") == "accept":
                piece["stance"] = "reject"
            piece["flipped_by"] = {"position": pos, "auditor": label}
            counts["flipped"] += 1
        else:
            counts["already_conflict"] += 1
    return out, counts


def check_stance_context(config, group, context):
    """A prompt's stance context: none (the shipped question) or one of STANCE_CONTEXTS, only on the system's
    advice under the stepwise method, `trimmed` only when its template is declared."""
    if context is None:
        return None
    if context not in STANCE_CONTEXTS:
        raise ValueError("a stance context is one of %s" % ", ".join(STANCE_CONTEXTS))
    if group != METHOD_GROUP or method_of(config, group) != STEPWISE:
        raise ValueError("a stance context is a stepwise arm of the system's advice alone")
    if context == TRIMMED_CONTEXT and not isinstance(config["advice"]["methods"][STEPWISE].get("stance_trimmed"), str):
        raise ValueError("the trimmed arm needs advice.methods.stepwise.stance_trimmed")
    return context


def decision_probabilities(decision):
    """{label: probability} of a choice decision, or None when there is none."""
    if not isinstance(decision, dict) or not isinstance(decision.get("answers"), list):
        return None
    return {a["label"]: a["probability"] for a in decision["answers"]}


def oppose_margin(probabilities):
    """p(oppose) minus the largest probability of another answer; None without probabilities."""
    if not probabilities or OPPOSE not in probabilities or len(probabilities) < 2:
        return None
    return probabilities[OPPOSE] - max(v for k, v in probabilities.items() if k != OPPOSE)


def red_lines_text(item):
    """The persona's red lines on record as the trimmed stance step shows them, one quote a line."""
    red = set(item["persona"].get("red_lines") or [])
    lines = [p["quote"] for p in item.get("positions") or [] if p["id"] in red and p["party"] == item["persona"]["id"]]
    return "\n".join("- %s" % q for q in lines) or "(none on record)"


# ---------------------------------------------------------------------------
# D-713 (Seckin 20:51): two reasoning methods for the system's advice, declared variants, off by default. The
# system_advice group declares `method` in neg_advisor_prompt.json (none: plain); nothing types it in.
# - reason_first: each advice entry writes a short `rationale` before its labels, a fixed field the reader
#   keeps apart; no figure reads it and nothing reads its words.
# - stepwise: one advice question becomes a chain of narrow ones per proposal (what it changes, whose position
#   it touches and how, whether it crosses a red line, whether an open point remains, and wording for a
#   counter), each answer checked by Python before the next; Python composes the advice from the checked
#   answers by the plan's rules. Run through an injected `ask` (CASE-QUESTIONS-A); B1 always generates plainly.

PLAIN, REASON_FIRST, STEPWISE = "plain", "reason_first", "stepwise"
METHODS = (PLAIN, REASON_FIRST, STEPWISE)
ALLOWANCE_METHODS = (PLAIN, REASON_FIRST)    # methods whose advice prompt may declare its own max_new_tokens (D-725, D-740)
METHOD_GROUP = "system_advice"
RATIONALE_MAX_CHARS = 300
STEPS = ("changes", "stance", "red_line", "open_point", "wording")
STEP_ANSWERS = {"stance": POSITION_STANCES, "red_line": ("yes", "no"), "open_point": ("yes", "no")}
# D-756 item 6 (N3): the chain's declared order, `advice.methods.stepwise.order`. `generated_first` (none declared,
# the order S0 shipped with): per proposal the generated `changes` step first, its checked line shown to every later
# step, so a refused `changes` ends the proposal's chain before any stance is asked. `choice_first`: the choice steps
# (each touched position's stance, the persona's red lines, the open point) are asked first from the templates of
# `advice.methods.stepwise.choice_first` (none of them shows `{changes}`), then the generated steps (`changes`, and
# the counter `wording` when the open point is yes); a refused generated step drops only its own field, is counted
# with its reason like every refused step, and never ends the chain.
GENERATED_FIRST, CHOICE_FIRST = "generated_first", "choice_first"
ORDERS = (GENERATED_FIRST, CHOICE_FIRST)
CHOICE_FIRST_TEMPLATES = ("stance", "red_line", "open_point", "wording")
# D-756 item 5 (P8): the context a stance step is shown, chosen per prompt at build time (`stance_context`), so one
# prompts file can carry both arms side by side, each prompt marked. `full` (none marked, the shipped question):
# the stance template of the declared order. `trimmed`: `advice.methods.stepwise.stance_trimmed`, only the
# proposal's text, the one position and the persona's red lines on record. No fate forecast exists in the chain;
# one added later keeps the whole item whatever the arm.
FULL_CONTEXT, TRIMMED_CONTEXT = "full", "trimmed"
STANCE_CONTEXTS = (FULL_CONTEXT, TRIMMED_CONTEXT)
TRIMMED_SLOTS = ("{proposal}", "{party}", "{quote}", "{red_lines}")
# D-756 items 2 and 3 (N1, P3): the oppose margin of a stance step, its probability of `oppose` minus the largest
# probability of another declared stance (CHOICE-A's renormalised probabilities, read from the step's decision).
OPPOSE = "oppose"


def method_of(config, group):
    """The method a group declares (PLAIN when none); only the system's advice group may declare another."""
    for g in config["models"]:
        if g["group"] == group:
            return g.get("method") or PLAIN
    return PLAIN


def advice_allowance(config, group):
    """The advice form's allowance of new tokens for one group, read from the config when a prompt is built
    and again when it is loaded: the system's advice under the plain method (M-plain) takes
    `advice.methods.plain.max_new_tokens` when the config declares it (D-725: 4,096, since 2,048 is tight for
    one entry per proposal under the tuple advice schema), and under reason_first
    `advice.methods.reason_first.max_new_tokens` (D-740: the same 4,096, so the methods compared to M-plain
    are not cut shorter); B1 and stepwise keep the form's own `advice.max_new_tokens` (stepwise's declared
    figure, 512, is its per-step allowance, not the advice prompt's)."""
    method = method_of(config, group)
    if group == METHOD_GROUP and method in ALLOWANCE_METHODS:
        block = (config["advice"].get("methods") or {}).get(method)
        if isinstance(block, dict) and block.get("max_new_tokens") is not None:
            return block["max_new_tokens"]
    return config["advice"]["max_new_tokens"]


def method_instructions(config, method):
    """The text a method adds after the advice instructions (none for plain or stepwise: stepwise asks its own
    questions)."""
    if method != REASON_FIRST:
        return ""
    return "\n" + config["advice"]["methods"][REASON_FIRST]["instructions_extra"]


def _collapse(text):
    return " ".join(str(text or "").split())


def _step_check(step, answer, item, proposal, position=None, answers=None, id_echo=False):
    """(value, None) or (None, reason): Python's check of one step's answer before the next step is asked
    (`answers`, a step's own declared answers when they are not STEP_ANSWERS'). `id_echo` (R3b, changes_id_echo):
    a `changes` line starting with exactly the proposal id the prompt showed and a colon is read without that id."""
    if step == REASON and answers is None:
        read = {}
        for line in str(answer or "").splitlines():
            head, sep, rest = line.strip().strip("*#- ").partition(":")
            key = head.strip(" *").lower()
            if sep and key in REASON_PARTS and rest.strip(" *") and key not in read:
                read[key] = " ".join(rest.strip(" *").split())[:REASON_MAX_CHARS]
        missing = [k for k in REASON_PARTS if k not in read]
        return (read, None) if not missing else (None, "no_" + missing[0])
    said = _collapse(answer)
    if answers is not None:
        word = said.lower().strip(" .\"'")
        return (word, None) if word in answers else (None, "not_declared")
    if step == "changes" and id_echo and said.startswith("%s:" % proposal["id"]):
        said = said[len(proposal["id"]) + 1:].strip()
    if step == "changes":
        if len(said.split()) < BASIS_QUOTE_MIN_WORDS:
            return None, "line_too_short"
        return (said, None) if said in _collapse(proposal["text"]) else (None, "not_in_the_proposal")
    if step in STEP_ANSWERS:
        word = said.lower().strip(" .\"'")
        return (word, None) if word in STEP_ANSWERS[step] else (None, "not_declared")
    if step == "wording":
        if not said:
            return None, "empty"
        if CITATION_ID.search(said):
            return None, "cites_an_id"
        return (said[:WORDING_MAX_CHARS], None)
    raise ValueError("no such step: %s" % step)


def _applicable(positions, party, article, number):
    mine = [p for p in positions if p["party"] == party and p["article"] == article]
    specific = [p for p in mine if p.get("proposal") == number]
    return specific if specific else [p for p in mine if p.get("proposal") is None]


class _NotedSteps(list):
    """The chain's list of steps, telling `hook` of each step's verdict as it is appended (right after its ask)."""

    def __init__(self, hook):
        super().__init__()
        self.hook = hook

    def append(self, entry):
        super().append(entry)
        self.hook(entry)


def stepwise_advice(config, item, ask, on_step=None, stance_context=None):
    """(reply, steps): the advice of one item by the step-wise chain, `reply` in parse_advice's shape (each piece
    marked `method` stepwise and `basis` on_record), `steps` every question asked with its answer and Python's
    verdict. `ask(step, user, answers)` returns the model's text (for a choice step, its settled label), or a pair
    (that text, the choice step's {answer: probability}). A choice step whose answer Python refuses ends that
    proposal's chain, and what it would have decided is left unanswered; a refused generated step does the same
    under the `generated_first` order and drops only its own field under `choice_first` (D-756 item 6, N3).
    A position's stance is asked only of the positions the mapping puts on the proposal, in the declared
    `stance_context` (D-756 item 5, P8: none or `full`, the order's own stance template; `trimmed`, the proposal,
    the one position and the persona's red lines); a red line only when one of the persona's applicable positions
    is marked one; conflict, alignment and the stance are Python's. Each piece keeps its checked stances with
    their probabilities and oppose margins (`position_stances`, D-756 items 2 and 3) and, when a red line was
    asked, `red_line_hit`. `on_step(entry)`, when given, receives each step's verdict right after its ask, before
    the next ask."""
    block = config["advice"]["methods"][STEPWISE]
    check_stepwise_block(block)
    order = step_order(block)
    context = stance_context or FULL_CONTEXT
    if context not in STANCE_CONTEXTS:
        raise ValueError("a stance context is one of %s" % ", ".join(STANCE_CONTEXTS))
    if context == TRIMMED_CONTEXT and not isinstance(block.get("stance_trimmed"), str):
        raise ValueError("the trimmed arm needs advice.methods.stepwise.stance_trimmed")
    first = block.get("choice_first") or {}
    opt = optional_switches(block)
    cond = opt["conditional_accept"]
    if cond is not None and context == TRIMMED_CONTEXT:
        raise ValueError("conditional_accept has its own stance template; the trimmed arm does not carry it")
    compare = compare_answers(block) if opt["conflict_question"] == COMPARE else None
    room = room_fate_answers(block) if opt["room_fate"] else None
    if compare is not None and context == TRIMMED_CONTEXT:
        raise ValueError("the compare question has its own template; the trimmed arm does not carry it")
    persona = item["persona"]["id"]
    red = set(item["persona"].get("red_lines") or [])
    red_text = red_lines_text(item)
    positions = item.get("positions") or []
    steps, proposals, signs = (_NotedSteps(on_step) if on_step is not None else []), {}, {}
    judged = {}   # position id -> the stance its step answered, Python-checked (D-668 gap 4: the movement's input)

    frame_now, lead = [""], [""]
    if opt["mandate_split"]:
        none, lines = block["party_frame_none"], party_red_lines(item)
        red_ids = {r["id"] for r in lines}
        lead[0] = _fill(block["mandate_split_text"], {
            "{persona}": party_text(item["persona"]),
            "{red_lines}": "\n".join("- (%s) %s" % (r["source"], r["text"]) for r in lines) or none,
            "{bargainable}": "\n".join("- round %s, article %s: %s" % (p.get("round"), p["article"], p["quote"])
                                       for p in positions if p["party"] == item["persona"]["id"]
                                       and p["id"] not in red_ids) or none}) + "\n\n"
    op_lines = operator_red_lines(item) if opt["mandate_split"] else []

    def frame_for(article):
        """#310: the frame before every question, from the item's declarations alone (None: the whole item)."""
        none = block["party_frame_none"]
        pid = item["persona"]["id"]
        mine = [p for p in positions if p["party"] == pid]
        others = [p for p in positions if p["party"] != pid and (article is None or p["article"] == article)]
        on_art = [p for p in positions if article is None or p["article"] == article]
        rounds = sorted({p.get("round") for p in on_art if isinstance(p.get("round"), int)})
        history = ["- round %d: positions by %s" % (r, ", ".join(sorted({p["party"] for p in on_art
                                                                         if p.get("round") == r}))) for r in rounds]
        closed = [a["id"] for a in item["articles"] if a.get("agreed")]
        now = {e.get("id") for e in item.get("round_index") or []}
        fell = [e.get("id") for e in item.get("previous_index") or [] if e.get("id") not in now]
        if closed:
            history.append("- agreed in this round's text: %s" % ", ".join(closed))
        if fell:
            history.append("- in the previous round's text, no longer in this one: %s" % ", ".join(fell))
        history += ["- trade on record by the party you advise, round %s: gave %s, expects %s"
                    % (t.get("round"), t.get("give"), t.get("get")) for t in item.get("trades_on_record") or []]
        return _fill(block["party_frame_text"], {
            "{persona}": party_text(item["persona"]),
            "{interests}": "\n".join("- round %s, article %s: %s" % (p.get("round"), p["article"], p["quote"])
                                     for p in mine) or none,
            "{others}": "\n".join("- %s, round %s: %s" % (p["party"], p.get("round"), p["quote"])
                                  for p in others) or none,
            "{history}": "\n".join(history) or none}) + "\n\n"

    def put(step, user, answers):
        said = ask(step, lead[0] + frame_now[0] + user, answers)
        return said if isinstance(said, tuple) else (said, None)

    if opt["party_frame"]:
        frame_now[0] = frame_for(None)

    # R2: the persona's positions read for limits, once per item, before any proposal (none marked a red line).
    read_lines, limit_reads = set(), {}
    if opt["limit_read"]:
        limit_labels, counts_limit = limit_answers(block)
        for pos in positions:
            if pos["party"] != persona or pos["id"] in red:
                continue
            user = _fill(block["limit"], {"{party}": pos["party"], "{quote}": pos["quote"],
                                          "{position_round}": str(pos.get("round"))})
            said, probs = put(LIMIT_READ, user, limit_labels)
            got, why = _step_check(LIMIT_READ, said, item, None, pos, limit_labels)
            steps.append({"proposal": None, "step": LIMIT_READ, "position": pos["id"], "accepted": why is None,
                          "refused": why})
            limit_reads[pos["id"]] = {"answered": got, "limit": bool(why is None and counts_limit[got]),
                                      "probabilities": probs, "basis": INFERRED}
            if limit_reads[pos["id"]]["limit"]:
                read_lines.add(pos["id"])

    for art in item["articles"]:
        if opt["party_frame"]:
            frame_now[0] = frame_for(art["id"])
        for n, prop in enumerate(art["proposals"], 1):
            base = {"{proposal_id}": prop["id"], "{proposal}": prop["text"], "{article}": art["id"],
                    "{title}": art["title"]}
            piece = {"id": prop["id"], "reasons": [], "method": STEPWISE, "basis": ON_RECORD}
            proposals[prop["id"]] = piece
            touched = [p for party in sorted({q["party"] for q in positions})
                       for p in _applicable(positions, party, art["id"], n)]
            mine = [p for p in touched if p["party"] == persona]
            lines = [p for p in mine if p["id"] in red]

            def generated(step, template, slots):
                said, _probs = put(step, _fill(template, slots), None)
                echo = opt["changes_id_echo"] and step == "changes"
                # Off, the check is called exactly as before (check 468's neutralisation replaces it by that signature).
                value, why = (_step_check(step, said, item, prop, id_echo=True) if echo
                              else _step_check(step, said, item, prop))
                entry = {"proposal": prop["id"], "step": step, "accepted": why is None, "refused": why}
                if echo and why is None and _collapse(said).startswith("%s:" % prop["id"]):
                    entry["id_echo"] = True
                steps.append(entry)
                return value, why

            def choice(step, user, pos=None, answers=None):
                said, probs = put(step, user, tuple(answers) if answers is not None else STEP_ANSWERS[step])
                got, why = _step_check(step, said, item, prop, pos, answers)
                entry = {"proposal": prop["id"], "step": step, "accepted": why is None, "refused": why}
                if pos is not None:
                    entry = {"proposal": prop["id"], "step": step, "position": pos["id"], "accepted": why is None,
                             "refused": why}
                steps.append(entry)
                return got, why, probs

            def stance_user(pos, changes):
                slots = dict(base, **{"{party}": pos["party"], "{quote}": pos["quote"]})
                if context == TRIMMED_CONTEXT:
                    return _fill(block["stance_trimmed"], {"{proposal}": prop["text"], "{party}": pos["party"],
                                                           "{quote}": pos["quote"], "{red_lines}": red_text})
                if order == CHOICE_FIRST:
                    return _fill(first["stance"], slots)
                return _fill(block["stance"], dict(slots, **{"{changes}": changes}))

            def position_stance(pos, changes):
                """(stance, refused, entry): one position's stance by the declared conflict question (C2, C3)."""
                if opt["conflict_question"] == TWO_CHECKS:
                    slots = dict(base, **{"{party}": pos["party"], "{quote}": pos["quote"]})
                    said, probs = {}, {}
                    for step in ("touches", "holds"):
                        got, why, p = choice(step, _fill(block[step], slots), pos, YES_NO)
                        if why:
                            return None, why, None
                        said[step], probs[step] = got, p
                    stance = OPPOSE if (said["touches"], said["holds"]) == ("yes", "no") else block["two_checks_otherwise"]
                    a, b = _margin_toward(probs["touches"], "yes"), _margin_toward(probs["holds"], "no")
                    return stance, None, {"party": pos["party"], "stance": stance, "checks": said, "probabilities": probs,
                                          "oppose_margin": None if a is None or b is None else min(a, b)}
                if compare is not None:
                    labels, counts_as, against = compare
                    slots = dict(base, **{"{party}": pos["party"], "{quote}": pos["quote"],
                                          "{position_round}": str(pos.get("round")), "{round}": str(item.get("round"))})
                    got, why, probs = choice("compare", _fill(block["compare"], slots), pos, labels)
                    if why:
                        return None, why, None
                    return counts_as[got], None, {"party": pos["party"], "stance": counts_as[got], "answered": got,
                                                  "probabilities": probs,
                                                  "oppose_margin": _margin_toward(probs, against)}
                if cond is not None:
                    slots = dict(base, **{"{party}": pos["party"], "{quote}": pos["quote"]})
                    got, why, probs = choice("stance", _fill(block["stance_conditional"], slots), pos,
                                             POSITION_STANCES + (cond["label"],))
                    if why:
                        return None, why, None
                    entry = {"party": pos["party"], "stance": got, "probabilities": probs,
                             "oppose_margin": oppose_margin(probs)}
                    if got == cond["label"]:
                        entry.update(stance=cond["counts_as"], answered=got)
                    return entry["stance"], None, entry
                got, why, probs = choice("stance", stance_user(pos, changes), pos)
                if why:
                    return None, why, None
                return got, None, {"party": pos["party"], "stance": got, "probabilities": probs,
                                   "oppose_margin": oppose_margin(probs)}

            def ground(pos, entry):
                """P6 (and P5's candidates): the sentence of the position that opposes, chosen by number."""
                sentences = position_sentences(pos["quote"])
                if not sentences or len(sentences) > QUOTE_MAX_SENTENCES:
                    entry["quote"] = {"chosen": None, "reason": "too_many_sentences" if sentences else "no_sentence"}
                    return None
                listed = "\n".join("%d. %s" % (k, s) for k, s in enumerate(sentences, 1))
                user = _fill(block["quote"], dict(base, **{"{party}": pos["party"], "{sentences}": listed}))
                got, why, _p = choice("quote", user, pos, (NO_SENTENCE,) + tuple(str(k) for k in range(1, len(sentences) + 1)))
                if why:
                    entry["quote"] = {"chosen": None, "reason": "refused"}
                    return None
                if got == NO_SENTENCE:
                    entry["quote"] = {"chosen": 0}
                    return None
                entry["quote"] = {"chosen": int(got), "sentence": sentences[int(got) - 1]}
                return entry["quote"]["sentence"]

            def in_band(pos, entry):
                band, m = opt["auditor_band"], entry.get("oppose_margin")
                return band is not None and pos["party"] == persona and entry["stance"] != OPPOSE and m is not None \
                    and band[0] <= m < band[1]

            def choice_steps(changes):
                """The choice steps of one proposal: (stances, hit, open point) or None when one is refused."""
                stances, kept = {}, {}
                for pos in touched:
                    got, why, entry = position_stance(pos, changes)
                    if why:
                        if kept:
                            piece["position_stances"] = kept
                        return None
                    if opt["quote_grounding"] and got == OPPOSE:
                        ground(pos, entry)
                        if entry["quote"].get("chosen") == 0:
                            got = entry["stance"] = block["quote_none_stance"]
                            entry["sent_back"] = True
                    elif opt["quote_grounding"] and in_band(pos, entry):
                        sentence = ground(pos, entry)
                        if sentence:
                            piece.setdefault("auditor_candidates", []).append(
                                {"position": pos["id"], "party": pos["party"], "sentence": sentence,
                                 "oppose_margin": entry["oppose_margin"]})
                    stances[pos["id"]] = got
                    kept[pos["id"]] = entry
                if kept:
                    piece["position_stances"] = kept
                judged.update(stances)
                piece["reasons"] = [p["id"] for p in touched]
                for pos in touched:
                    signs.setdefault((art["id"], n, pos["party"]), set()).add(
                        1 if stances[pos["id"]] in ("support", "accept") else -1)
                hit = False
                for pos in lines:
                    slots = dict(base, **{"{quote}": pos["quote"]})
                    template = first["red_line"] if order == CHOICE_FIRST else block["red_line"]
                    if order != CHOICE_FIRST:
                        slots["{changes}"] = changes
                    got, why, _probs = choice("red_line", _fill(template, slots), pos)
                    if why:
                        return None
                    hit = hit or got == "yes"
                for op in op_lines:
                    # D-848: each operator red line asked of every proposal by the red_line step.
                    slots = dict(base, **{"{quote}": op["text"]})
                    template = first["red_line"] if order == CHOICE_FIRST else block["red_line"]
                    if order != CHOICE_FIRST:
                        slots["{changes}"] = changes
                    got, why, _probs = choice("red_line", _fill(template, slots))
                    if why:
                        return None
                    if got == "yes":
                        hit = True
                        piece.setdefault("operator_lines_hit", []).append(op["id"])
                if lines or op_lines:
                    piece["red_line_hit"] = hit
                crossed, read = [], [p for p in mine if p["id"] in read_lines]
                for pos in read:
                    slots = dict(base, **{"{quote}": pos["quote"], "{party}": pos["party"],
                                          "{position_round}": str(pos.get("round")), "{round}": str(item.get("round"))})
                    got, why, _probs = choice(LIMIT_CROSS, _fill(block["limit_cross"], slots), pos, YES_NO)
                    if not why and got == "yes":
                        crossed.append(pos["id"])
                if read:
                    piece.update(limit_hit=bool(crossed), limit_lines=crossed, limit_basis=INFERRED)
                if not mine and not piece.get("operator_lines_hit"):
                    piece["conflict"] = "not_stated"
                else:
                    piece["conflict"] = "conflict" if hit or crossed or \
                        any(stances[p["id"]] == "oppose" for p in mine) else "no_conflict"
                if room is not None:
                    # R3: the blind open point step is not asked; the room fate decides the stance.
                    return stances, hit, None
                template = first["open_point"] if order == CHOICE_FIRST else block["open_point"]
                slots = dict(base) if order == CHOICE_FIRST else dict(base, **{"{changes}": changes})
                got, why, _probs = choice("open_point", _fill(template, slots))
                if why:
                    return None
                return stances, hit, got

            def forecast():
                """P2: the proposal's fate, one choice over the declared answers, the whole article shown."""
                if not opt["fate_forecast"] or "stance" not in piece:
                    return
                shown = "\n".join("- %s: %s" % (p["party"], p["quote"]) for p in positions
                                  if p["article"] == art["id"]) or "(none on record)"
                user = _fill(block["fate"], dict(base, **{"{positions}": shown, "{red_lines}": red_text}))
                got, why, probs = choice("fate", user, None, tuple(block["fate_answers"]))
                if why:
                    return
                piece.update(fate=got, fate_basis=INFERRED, fate_probabilities=probs)
                if block["fate_precedence"] == "fate":
                    new = block["fate_stance"][got]
                    if new != piece["stance"]:
                        piece["stance_from_fate"] = {"was": piece["stance"]}
                        piece["stance"] = new
                    if new != "counter":
                        piece.pop("wording", None)

            def room_stance():
                """R3: the proposal's fate in the room, one choice over the declared answers; the stance it sets,
                or None when refused (the proposal is then left without a stance)."""
                labels, sets = room
                kept = piece.get("position_stances") or {}
                read = []
                for pos in touched:
                    e = kept.get(pos["id"]) or {}
                    line = "- %s, round %s: %s" % (pos["party"], pos.get("round"), pos["quote"])
                    # Round 3: unanchored, the position alone, without the chain's own read of it.
                    read.append(line if opt["room_unanchored"] else
                                "%s\n  read: %s" % (line, e.get("answered") or e.get("stance")))
                others = ["- %s" % q["text"] for q in art["proposals"] if q["id"] != prop["id"]]
                user = _fill(block[ROOM_FATE_TEMPLATE], dict(base, **{
                    "{alternatives}": "\n".join(others) or block["room_fate_alone"],
                    "{room}": "\n".join(read) or block["room_fate_none"], "{round}": str(item.get("round"))}))
                got, why, probs = choice(ROOM_FATE, user, None, labels)
                if why:
                    return None
                piece[ROOM_FATE] = {"answered": got, "probabilities": probs, "basis": INFERRED}
                return sets[got]

            def reason_step():
                """#311: the reasoning field after the stance, a generated step; a refusal drops this field only."""
                if not opt["reason_field"] or "stance" not in piece:
                    return
                value, why = generated(REASON, block["reason_text"], dict(base, **{"{stance}": piece["stance"]}))
                if not why:
                    piece[REASON] = value

            if room is not None:
                # R3: the choice steps and the changes line in the declared order, then the room fate; the
                # wording only for a counter.
                if order == CHOICE_FIRST:
                    if choice_steps(None) is None:
                        continue
                    value, why = generated("changes", block["changes"], base)
                    if not why:
                        piece["changes"] = value
                else:
                    value, why = generated("changes", block["changes"], base)
                    if why:
                        continue
                    piece["changes"] = value
                    if choice_steps(value) is None:
                        continue
                stance = room_stance()
                if stance is None:
                    continue
                piece["stance"] = stance
                if stance == "counter":
                    template = first["wording"] if order == CHOICE_FIRST else block["wording"]
                    wording, why = generated("wording", template, dict(base, **{"{changes}": piece.get("changes", "")}))
                    if not why:
                        piece["wording"] = wording
                reason_step()
                continue
            if order == CHOICE_FIRST:
                # N3: the choice steps first; then the generated ones, each refused one dropping its own field only.
                decided = choice_steps(None)
                if decided is None:
                    continue
                value, why = generated("changes", block["changes"], base)
                if not why:
                    piece["changes"] = value
                if decided[2] == "yes":
                    piece["stance"] = "counter"
                    wording, why = generated("wording", first["wording"], base)
                    if not why:
                        piece["wording"] = wording
                else:
                    piece["stance"] = "reject" if piece["conflict"] == "conflict" else "accept"
                forecast()
                reason_step()
                continue
            value, why = generated("changes", block["changes"], base)
            if why:
                continue
            piece["changes"] = value
            decided = choice_steps(value)
            if decided is None:
                continue
            if decided[2] == "yes":
                wording, why = generated("wording", block["wording"], dict(base, **{"{changes}": value}))
                if why:
                    continue
                piece.update(stance="counter", wording=wording)
            else:
                piece["stance"] = "reject" if piece["conflict"] == "conflict" else "accept"
            forecast()
            reason_step()
    # #3 (D-846) trade_read: each trade on record by the party it advises whose give and get are both on the table,
    # one CHOICE-A question, keep or drop; a kept one is offered again in the reply's trades.
    trades, trade_reads = [], {}
    if opt["trade_read"]:
        labels, keeps = trade_answers(block)
        texts = {q["id"]: q["text"] for a in item["articles"] for q in a["proposals"]}
        if opt["party_frame"]:
            frame_now[0] = frame_for(None)
        for t in item.get("trades_on_record") or []:
            if t.get("give") not in texts or t.get("get") not in texts or t["give"] == t["get"]:
                continue
            user = _fill(block["trade_text"], {"{give}": "%s: %s" % (t["give"], texts[t["give"]]),
                                                "{get}": "%s: %s" % (t["get"], texts[t["get"]]),
                                                "{trade_round}": str(t.get("round")), "{round}": str(item.get("round"))})
            said, probs = put(TRADE_READ, user, labels)
            got, why = _step_check(TRADE_READ, said, item, None, None, labels)
            steps.append({"proposal": None, "step": TRADE_READ, "trade": t.get("id"), "accepted": why is None,
                          "refused": why})
            trade_reads[t.get("id")] = {"answered": got, "probabilities": probs, "basis": INFERRED}
            if why is None and keeps[got]:
                trades.append({"give": t["give"], "get": t["get"]})
    alignment = {}
    for art in item["articles"]:
        cells = {}
        for party in sorted({p["id"] for p in item["parties"]} - {persona}):
            common = []
            for n in range(1, len(art["proposals"]) + 1) or [None]:
                a, b = signs.get((art["id"], n, persona), set()), signs.get((art["id"], n, party), set())
                if len(a) == 1 and len(b) == 1:
                    common.append(a == b)
            if common:
                cells[party] = "aligned" if all(common) else "opposed"
        alignment[art["id"]] = {"aligned": sorted(p for p, v in cells.items() if v == "aligned"),
                                "opposed": sorted(p for p, v in cells.items() if v == "opposed")}
    reply = {"proposals": proposals, "trades": trades, "approach": [], "alignment": alignment, "state": {},
             "unknown_ids": 0,
             # D-668 gap 4: every other party's movement toward or away from the persona over the rounds,
             # composed by Python from the stances the chain checked (a position not judged is not used).
             "movement": movement_map(item, [dict(p, stance=judged[p["id"]]) for p in positions if p["id"] in judged])}
    if opt["limit_read"]:
        reply["limit_reads"] = limit_reads
    if opt["trade_read"]:
        reply["trade_reads"] = trade_reads
    return reply, steps


def _enum(values):
    return {"type": "enum", "values": sorted(values)}


def _list_of(node):
    return {"type": "array", "items": node}


def advice_schema(item, method=None):
    method = method or PLAIN
    """The plan's section 5.1 reply as a schema, its ids read from the item (the game reply for a game)."""
    if item.get("game"):
        issues = item["game"]["issues"]
        return {"type": "object", "keys": [
            ["deal", {"type": "object", "keys": [[i["id"], _enum(i["options"]), True] for i in issues]}, True],
            ["trades", _list_of({"type": "object", "keys": [["give", _enum(i["id"] for i in issues), True],
                                                            ["get", _enum(i["id"] for i in issues), True]]}), True]]}
    pars, poss, props, arts = item_ids(item)
    known_articles = arts | {r["id"] for r in item.get("previous_index") or []}
    parties = {p["id"] for p in item["parties"]}
    first = ([["rationale", {"type": "string", "max_chars": RATIONALE_MAX_CHARS}, True]]
             if method == REASON_FIRST else [])

    def proposal(pid):
        return {"type": "object", "keys": [
            ["id", _enum([pid]), True]] + first + [["conflict", _enum(CONFLICT), True], ["stance", _enum(STANCES), True],
            ["basis", _enum(BASES), False], ["basis_quote", {"type": "string", "max_chars": BASIS_QUOTE_MAX_CHARS}, False],
            ["wording", {"type": "string", "max_chars": WORDING_MAX_CHARS}, False],
            ["reasons", dict(_list_of(_enum(pars | poss)), max_items=REASONS_MAX), True]]}
    # One entry per proposal of the item, in the excerpt's order, each with its own id (lane neg-round1: on
    # the pilot's 18 development items the free replies gave a piece for 32 of 179 proposals, the system, and
    # 61, B1; a list of any length let the model stop after a few).
    in_order = [p["id"] for a in item.get("articles") or [] for p in a["proposals"]]
    return {"type": "object", "keys": [
        ["proposals", {"type": "tuple", "items": [proposal(pid) for pid in in_order]}, True],
        ["trades", _list_of({"type": "object", "keys": [["give", _enum(props), True], ["get", _enum(props), True]]}), True],
        ["approach", _list_of(_enum(parties)), True],
        ["alignment", _list_of({"type": "object", "keys": [["article", _enum(arts), True],
                                                           ["aligned", _list_of(_enum(parties)), True],
                                                           ["opposed", _list_of(_enum(parties)), True],
                                                           ["basis", _enum(BASES), False],
                                                           ["basis_quote", {"type": "string",
                                                                            "max_chars": BASIS_QUOTE_MAX_CHARS}, False]]}),
         True],
        ["state", _list_of({"type": "object", "keys": [["article", _enum(known_articles), True],
                                                       ["state", _enum(STATES), True]]}), True]]}


def validate_schema(item):
    """The validator's reply as a schema: one of the item's article ids, a proposal number or null, a stance."""
    return {"type": "object", "keys": [["article", _enum(article_ids(item)), True],
                                       ["proposal", {"type": "integer_or_null"}, True],
                                       ["stance", _enum(POSITION_STANCES), True]]}


def schema_of(prompt):
    return (advice_schema(prompt["item"], prompt.get("method") or PLAIN) if prompt["form"] == "advice"
            else validate_schema(prompt["item"]))


def choice_answers(config, prompt):
    return config[CHOICE_GROUPS[prompt["group"]]]["choice_answers"]


def recorded_text(record, config, form):
    """The answer text a reply record holds: a generated reply's text, or for a choice decision the label it
    settles on under the form's declared threshold (a declared spelling every reader reads), or the
    choice module's own word for an unsettled decision. None for a failed call."""
    if not record.get("backend_ok"):
        return None
    decision = record.get("decision")
    if isinstance(decision, dict):
        import choice_decision
        block = config["judge" if form == "judge" else "audit"]
        return choice_decision.settle(decision, block["choice_threshold"])["decided"]
    reply = record.get("reply") or {}
    return reply.get("text") if isinstance(reply, dict) else None


def make_advisor_backend(reader, context):
    import bare_model

    class AdvisorBackend(bare_model.LocalBackend):
        """bare_model's local backend, with a constrained generate for the advisor's schema groups: the same
        model, rendering, attention and prefill as generate(), the constraint's processor added."""

        def generate_constrained(self, system, user, max_new_tokens, schema, source):
            import torch
            import decoding_policy
            import final_models
            import schema_decoding
            tok, mdl = self._loaded()
            prompt = self._render(system, user)
            inputs = tok(prompt, return_tensors="pt", add_special_tokens=False).to(mdl.device)
            attention = bare_model.declared_attention(self.reader)
            eos = decoding_policy.effective_eos(self.reader["decoding"], mdl)
            built = schema_decoding.constraint(source, schema, tok, int(inputs["input_ids"].shape[1]), eos, source)
            with torch.no_grad(), bare_model.b1_attention(mdl, implementation=attention["attention_implementation"]) as observe:
                observed = observe()
                out, measured = final_models.generate_with_prefill(
                    mdl, inputs, max_new_tokens=max_new_tokens, decoding_kwargs=self.reader["decoding"]["kwargs"],
                    prefill=bare_model.prefill_of(attention), **built.generate_kwargs())
            start = int(inputs["input_ids"].shape[1])
            text = tok.decode(out[0][start:], skip_special_tokens=True)
            generated = int(out[0].shape[0]) - start
            del inputs, out
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            return {"text": text, "payload": prompt, "form": "rendered_prompt", "output_tokens": generated,
                    "attention": dict(attention, **observed), "prefill": measured, "constraint": built.summary()}

    return AdvisorBackend(reader, context)


def call(backend, prompt, config):
    """One prompt through its group's declared way: a choice decision, a schema-constrained generation, or a
    free generation (B1, the cloud reference's prompts on a local model never: those carry no declaration)."""
    n = int(prompt["max_new_tokens"])
    if prompt.get("decide_by") == DECIDE_BY_CHOICE:
        return backend.choose(None, prompt["user"], choice_answers(config, prompt))
    if prompt.get("constraint") == SCHEMA_CONSTRAINT:
        return backend.generate_constrained(None, prompt["user"], n, schema_of(prompt),
                                            "%s:%s" % (prompt["form"], prompt["prompt_id"]))
    return backend.generate(None, prompt["user"], n)


# S0 (NEG_ROUND1.md section 6): the step-wise chain on the replay pass. A system advice prompt whose group declares
# `method: stepwise` in the prompts file's own config is not generated: stepwise_advice asks its chain on the same
# resident model, each generated step (changes, wording) within the method's declared allowance and each choice
# step (stance, red line, open point) decided from next-token probabilities over its declared answers (CHOICE-A)
# and settled at the method's declared threshold, every answer checked by Python before the next. Every step call
# writes one reply record: the item's last one in the pass folder as the prompt's own (one record per prompt
# there, as the sealed pass counts), the earlier ones under <pass>/STEPWISE_DIR (`stepwise_steps`, this pass's own
# name; the choice form's method chain uses reasoning_methods.STEPS_DIR, `method_steps`). A choice step's record
# carries its decision and no reply (CHOICE-A). A step Python's check refuses is written as REASON-METHODS-A writes
# one: backend_ok false, error `method_refused: <step> <reason>`, no decision, a generated step keeping its text.
# A call that raises leaves every step already asked written and in the measurement rows. An item with no proposal
# (a game) has no chain and runs its prompt as plain. Off unless the file declares the method.
STEPWISE_DIR = "stepwise_steps"
STEP_FORM = "step"


def has_chain(item):
    """An item the stepwise chain asks questions of: no game, at least one proposal."""
    return not item.get("game") and any(a["proposals"] for a in item.get("articles") or [])


def is_stepwise(config, prompt):
    return prompt.get("form") == "advice" and method_of(config, prompt.get("group")) == STEPWISE and \
        has_chain(prompt["item"])


def step_answers(labels):
    """A choice step's declared answers: each label its own surface (STEP_ANSWERS, fixed in code)."""
    return [{"label": a, "surface": a} for a in labels]


def stepwise_call(backend, prompt, config, limit, record, rows, verdict):
    """(reply, steps) of one step-wise prompt: stepwise_advice with an `ask` on `backend`. Each step's row is
    appended to `rows` once its call returned (ids, counts, seconds and hashes, never a text); `record(row,
    result, text, error)` holds its reply record and `verdict(row, entry)` gives it Python's check of the
    answer, before the next step is asked."""
    import choice_decision
    block = config["advice"]["methods"][STEPWISE]
    allowance, threshold = int(block["max_new_tokens"]), block["choice_threshold"]

    def ask(step, user, answers):
        tokens = int(backend.count_prompt(None, user))
        n = 0 if answers else allowance
        row = {"prompt_id": "%s-s%03d" % (prompt["prompt_id"], len(rows) + 1), "form": STEP_FORM, "step": step,
               "group": prompt["group"], "derived_from": prompt["prompt_id"], "prompt_tokens": tokens,
               "max_new_tokens": n, "failure": None, "seconds": None, "user_sha256": _sha(user)}
        result, error, text = {}, "", None
        if tokens + n > int(limit):
            row["failure"] = error = "prompt_over_context"
        else:
            started = time.perf_counter()
            result = (backend.choose(None, user, step_answers(answers)) if answers
                      else backend.generate(None, user, n)) or {}
            row["seconds"] = round(time.perf_counter() - started, 3)
        if isinstance(result.get("decision"), dict):
            text = choice_decision.settle(result["decision"], threshold)["decided"]
        elif isinstance(result.get("text"), str):
            text = result["text"]
        rows.append(row)
        record(row, result, text, error)
        return text, decision_probabilities(result.get("decision"))

    return stepwise_advice(config, prompt["item"], ask, on_step=lambda entry: verdict(rows[-1], entry),
                           stance_context=prompt.get("stance_context"))


REFUSED_CATEGORY = "method_refused"


def refusal_error(entry):
    """A refused step's record error, REASON-METHODS-A's form: `method_refused: <step> <reason>`."""
    return "%s: %s %s" % (REFUSED_CATEGORY, entry["step"], entry["refused"])


def step_texts(config, record):
    """A step record's answer as the chain read it: a choice decision settled at the method's threshold, or the
    generated text. None for a failed call; for a step Python's check refused (no decision, backend_ok false),
    its generated text if it had one, so the check refuses it again for the same reason."""
    if not record.get("backend_ok"):
        if record.get("error_category") != REFUSED_CATEGORY:
            return None
        reply = record.get("reply") or {}
        return reply.get("text") if isinstance(reply, dict) else None
    decision = record.get("decision")
    if isinstance(decision, dict):
        import choice_decision
        return choice_decision.settle(decision, config["advice"]["methods"][STEPWISE]["choice_threshold"])["decided"]
    reply = record.get("reply") or {}
    return reply.get("text") if isinstance(reply, dict) else None


def recompose_stepwise(config, prompt, step_rows, records):
    """(reply, steps) of a step-wise prompt from its saved step records, no model: the chain asked again with each
    recorded answer in order, every question held to the SHA-256 the pass recorded for it. A pass whose steps do
    not replay is refused."""
    queue = list(step_rows)

    def ask(step, user, answers):
        if not queue:
            raise ValueError("the pass holds fewer steps than the chain asks: %s" % prompt["prompt_id"])
        row = queue.pop(0)
        if row.get("step") != step or row.get("user_sha256") != _sha(user):
            raise ValueError("a saved step is not the chain's question: %s" % row.get("prompt_id"))
        record = records.get(row.get("call_id")) or {}
        # D-756 item 3: a choice step's per-answer probabilities, as its reply record saved them (CHOICE-A).
        return step_texts(config, record), decision_probabilities(record.get("decision") if record.get("backend_ok") else None)

    reply, steps = stepwise_advice(config, prompt["item"], ask, stance_context=prompt.get("stance_context"))
    if queue:
        raise ValueError("the pass holds more steps than the chain asks: %s" % prompt["prompt_id"])
    for row, entry in zip(step_rows, steps):
        record = records.get(row.get("call_id")) or {}
        if record.get("error_category") == REFUSED_CATEGORY and record.get("error") != refusal_error(entry):
            raise ValueError("a saved step's refusal is not the chain's: %s" % row.get("prompt_id"))
        if record.get("backend_ok") and entry["refused"]:
            raise ValueError("a saved step the pass accepted is refused on reading: %s" % row.get("prompt_id"))
    return reply, steps


def stepwise_replies(value, run_dir, measurement):
    """{prompt id: (reply, steps)} of every step-wise prompt of a pass, composed again from its saved step records
    (the pass folder's and STEPWISE_DIR's), each held to its recorded question and refusal (recompose_stepwise)."""
    import reply_records
    run_dir = Path(run_dir)
    records = {}
    for folder in (run_dir / "audit" / "model_replies", run_dir / STEPWISE_DIR / "audit" / "model_replies"):
        if folder.is_dir():
            records.update({r.get("call_id"): r for r in reply_records.records(folder)})
    steps = {}
    for row in measurement.get("rows") or []:
        if row.get("form") == STEP_FORM:
            steps.setdefault(row["derived_from"], []).append(row)
        elif row.get("method") == STEPWISE:
            steps.setdefault(row["prompt_id"], [])
    by_id = {p["prompt_id"]: p for p in value["prompts"]}
    composed = {}
    for pid, saved in steps.items():
        if pid not in by_id or not is_stepwise(value["config"], by_id[pid]):
            raise ValueError("the pass holds steps of a prompt that is not step-wise: %s" % pid)
        composed[pid] = recompose_stepwise(value["config"], by_id[pid], saved, records)
    return composed


def run(prompts_path, out, *, backend_factory=None, reader_for=None, run_id=None):
    """Every prompt through its group's model, one reply record each, then (for a file holding the
    system's advice) every derived audit prompt through the auditor group. A step-wise prompt runs its
    chain (S0, above). The measurement file is written after every prompt, so a stopped pass stays
    readable."""
    import bare_model
    import decoding_policy
    import final_models
    import reply_records
    value = read_file(prompts_path)
    config = check_decoding(value["config"])
    out = outside_repository(out)
    context = bare_model.RunContext(out, run_id or ("neg-advisor-" + uuid.uuid4().hex[:12]))
    side = {}

    def steps_context():
        if "context" not in side:
            side["context"] = bare_model.RunContext(out / STEPWISE_DIR, context.run_id)
        return side["context"]
    factory = backend_factory or make_advisor_backend
    rows, models, texts, composed = [], {}, {}, {}
    sha = hashlib.sha256(Path(prompts_path).read_bytes()).hexdigest()

    def snapshot(complete):
        return {"schema": MEASUREMENT_SCHEMA, "run_id": context.run_id, "complete": complete,
                "prompts": len(value["prompts"]), "derived": sum(1 for r in rows if r["form"] == "audit"),
                "steps": sum(1 for r in rows if r["form"] == STEP_FORM),
                "prompts_sha256": sha, "config_sha256": value["config_sha256"], "models": models,
                "seconds": round(sum(r["seconds"] or 0 for r in rows), 3), "rows": rows, "reads": "ids, counts and seconds only here; the replies in the reply records"}

    def one_group(group, mine):
        allowance = max(int(p["max_new_tokens"]) for p in mine)
        reader = reader_for(group, allowance) if reader_for is not None else reader_of(group, allowance)
        if final_models.mode() == "final":
            final_models.verify_runtime()
        backend = factory(reader, context)
        try:
            loaded = backend.prepare()
            models[group["group"]] = {"model_id": loaded.get("model_id"), "digest": loaded.get("digest"),
                                      "backend": reader["backend"], "agent": reader["agent"]}
            limit = backend.max_context()

            def write(where, p, result, text, error):
                decoding = dict(decoding_policy.usage_fields(reader["decoding"]), max_new_tokens=int(p["max_new_tokens"]))
                call_id = reply_records.write(where, agent=AGENT_LABEL, backend=reader["backend"], model_id=reader["model_id"],
                                              model_mode=reader.get("model_mode"), payload=result.get("payload"),
                                              payload_form=result.get("form"),
                                              # CHOICE-A: a decided call has a decision and no reply.
                                              reply=None if isinstance(result.get("decision"), dict) else text,
                                              ok=not error, error=error,
                                              decoding=decoding, sensitive=False, phase=PHASE, doc_id=p["item_id"],
                                              attention=result.get("attention"), prefill=result.get("prefill"),
                                              decoding_constraint=result.get("constraint"), decision=result.get("decision"))
                if not call_id:
                    raise RuntimeError("the reply record for prompt %s could not be written" % p["prompt_id"])
                return call_id

            for p in mine:
                if is_stepwise(config, p):
                    # S0: the chain. Each step's record is held until the next step is asked, then written
                    # under STEPWISE_DIR; the last one in the pass folder as the prompt's own. A step Python's
                    # check refuses is written as REASON-METHODS-A writes one: backend_ok false, its error
                    # `method_refused: <step> <reason>`, no decision (a generated step keeps its text).
                    pending, step_rows = [], []

                    def record(row, result, text, error, p=p, pending=pending):
                        if pending:
                            flush(pending.pop(), steps_context())
                        pending.append({"row": row, "result": result, "text": text, "error": error, "p": p})

                    def verdict(row, entry, pending=pending):
                        if not entry["refused"] or not pending or pending[-1]["row"] is not row:
                            return
                        held, row["refused"] = pending[-1], entry["refused"]
                        if not held["error"]:
                            held["error"] = refusal_error(entry)
                            if isinstance(held["result"].get("decision"), dict):
                                held["result"], held["text"] = dict(held["result"], decision=None), None

                    def flush(held, where):
                        row = held["row"]
                        row["call_id"] = write(where, dict(held["p"], max_new_tokens=row["max_new_tokens"]), held["result"],
                                               held["text"], held["error"])
                        row["record"] = "pass" if where is context else STEPWISE_DIR
                        row["decided"] = isinstance(held["result"].get("decision"), dict)

                    parent = {"prompt_id": p["prompt_id"], "form": "advice", "group": group["group"], "method": STEPWISE,
                              "prompt_tokens": None, "max_new_tokens": int(p["max_new_tokens"]), "failure": None,
                              "seconds": None, "user_sha256": p["user_sha256"], "derived_from": None, "call_id": None}
                    if p.get("stance_context") is not None:
                        parent["stance_context"] = p["stance_context"]
                    rows.append(parent)
                    try:
                        reply, steps = stepwise_call(backend, p, config, limit, record, step_rows, verdict)
                    finally:
                        # A later call that raised leaves every step already asked written and in the rows.
                        if pending:
                            flush(pending.pop(), context)
                        rows.extend(step_rows)
                        parent.update(steps=len(step_rows), last_step=step_rows[-1]["prompt_id"] if step_rows else None)
                        _write_json(out / MEASUREMENT_FILE, snapshot(False))
                    composed[p["prompt_id"]] = reply
                    parent["steps_refused"] = sum(1 for s in steps if s["refused"])
                    _write_json(out / MEASUREMENT_FILE, snapshot(False))
                    continue
                tokens = int(backend.count_prompt(None, p["user"]))
                row = {"prompt_id": p["prompt_id"], "form": p["form"], "group": group["group"], "prompt_tokens": tokens,
                       "max_new_tokens": int(p["max_new_tokens"]), "failure": None, "seconds": None,
                       "user_sha256": p["user_sha256"], "derived_from": p.get("derived_from")}
                result, error = {}, ""
                if tokens + int(p["max_new_tokens"]) > int(limit):
                    row["failure"] = error = "prompt_over_context"
                else:
                    started = time.perf_counter()
                    result = call(backend, p, config) or {}
                    row["seconds"] = round(time.perf_counter() - started, 3)
                text = result.get("text") if isinstance(result.get("text"), str) else None
                texts[p["prompt_id"]] = text
                call_id = write(context, p, result, text, error)
                row.update(call_id=call_id, decided=isinstance(result.get("decision"), dict),
                           constrained=isinstance(result.get("constraint"), dict))
                rows.append(row)
                _write_json(out / MEASUREMENT_FILE, snapshot(False))
        finally:
            release = getattr(backend, "release", None)
            if callable(release):
                release()

    for group in config["models"]:
        mine = [p for p in value["prompts"] if p["group"] == group["group"]]
        if mine:
            one_group(group, mine)
    if value.get("audit"):
        derived = [d for p in value["prompts"] if p["group"] == "system_advice"
                   for d in (audit_prompts(config, p, None, composed[p["prompt_id"]]) if p["prompt_id"] in composed
                             else audit_prompts(config, p, texts.get(p["prompt_id"])))]
        if derived:
            one_group({g["group"]: g for g in config["models"]}["system_audit"], derived)
    result = snapshot(True)
    _write_json(out / MEASUREMENT_FILE, result)
    return result


# ---------------------------------------------------------------------------
# answers


def answers_from_texts(value, texts, *, measured_audits=None, composed=None):
    """{schema, prompts_sha256, rows}: per prompt its parsed reply. For the system's advice, each piece's
    audit answer, its prompt rendered again from the advice reply and held to the SHA-256 the pass recorded
    (`measured_audits`: derived prompt id to (user_sha256, text)). A step-wise prompt's reply is the one
    Python composed from its checked steps (`composed`: prompt id to (reply, steps)), with the steps'
    refusals counted by reason."""
    config = value["config"]
    rows = []
    for p in value["prompts"]:
        text = texts.get(p["prompt_id"])
        row = {"prompt_id": p["prompt_id"], "group": p["group"], "form": p["form"], "item_id": p["item_id"]}
        if p.get("stance_context") is not None:
            row["stance_context"] = p["stance_context"]
        if p["form"] == "advice":
            chain = (composed or {}).get(p["prompt_id"])
            row["reply"] = parse_advice(text, p["item"]) if chain is None else chain[0]
            if chain is not None:
                refused = Counter("%s:%s" % (s["step"], s["refused"]) for s in chain[1] if s["refused"])
                row.update(method=STEPWISE, steps=len(chain[1]), steps_refused=dict(sorted(refused.items())))
            if p["group"] == "system_advice":
                audits, flips = {}, {}
                for d in (audit_prompts(config, p, text) if chain is None else audit_prompts(config, p, None, chain[0])):
                    sha, said = (measured_audits or {}).get(d["prompt_id"], (None, None))
                    if sha is not None and sha != d["user_sha256"]:
                        raise ValueError("an audit prompt the pass ran is not the rendering of its advice: %s" % d["prompt_id"])
                    label = parse_audit(said, config) if sha is not None else None
                    if d.get("kind") == CONFLICT_AUDIT:
                        flips[(d["proposal_id"], d["position_id"])] = label
                    else:
                        audits[d["proposal_id"]] = label
                row["audit"] = audits
                if flips:
                    row["reply"], counts = auditor_flip(row["reply"], flips)
                    row["auditor_flip"] = dict(sorted(counts.items()))
        elif p["form"] == "judge":
            row.update(entry_id=p["entry"]["entry_id"], arm=p["entry"]["arm"], proposal_id=p["entry"]["proposal_id"],
                       grade=parse_judge(text))
        else:
            row.update(position_id=p["position"]["id"], mapping=parse_validate(text))
        rows.append(row)
    return {"schema": ANSWERS_SCHEMA, "prompts_sha256": value.get("_sha256"), "rows": rows}


def answers(prompts_path, run_dir, out=None):
    import reply_records
    value = read_file(prompts_path)
    value["_sha256"] = hashlib.sha256(Path(prompts_path).read_bytes()).hexdigest()
    run_dir = Path(run_dir)
    measurement = json.loads((run_dir / MEASUREMENT_FILE).read_text(encoding="utf-8"))
    if measurement.get("schema") != MEASUREMENT_SCHEMA or measurement.get("prompts_sha256") != value["_sha256"]:
        raise ValueError("the pass folder is not a negotiation advisor pass of these prompts")
    records = {r.get("call_id"): r for r in reply_records.records(run_dir / "audit" / "model_replies")}
    texts, audits = {}, {}
    for row in measurement.get("rows") or []:
        if row.get("form") == STEP_FORM or row.get("method") == STEPWISE:
            continue
        record = records.get(row.get("call_id")) or {}
        text = recorded_text(record, value["config"], row.get("form"))
        if row.get("form") == "audit":
            audits[row["prompt_id"]] = (row.get("user_sha256"), text)
        else:
            texts[row["prompt_id"]] = text
    composed = stepwise_replies(value, run_dir, measurement)
    result = answers_from_texts(value, texts, measured_audits=audits, composed=composed)
    result["models"] = measurement.get("models")
    if out:
        _write_json(outside_repository(out), result)
    return result


def answers_from_text_file(prompts_path, texts_path, out=None):
    """The cloud reference's answers: its replies to B1's prompts byte for byte, as {prompt id: text}."""
    value = read_file(prompts_path)
    value["_sha256"] = hashlib.sha256(Path(prompts_path).read_bytes()).hexdigest()
    if any(p["group"] != "b1" for p in value["prompts"]):
        raise ValueError("the cloud reference answers B1's prompts only")
    result = answers_from_texts(value, json.loads(Path(texts_path).read_text(encoding="utf-8")))
    result["subset_sha256"] = value.get("subset_sha256")
    if out:
        _write_json(outside_repository(out), result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", allow_abbrev=False)
    b.add_argument("--set", required=True, type=Path)
    b.add_argument("--form", required=True, choices=("advice",))
    b.add_argument("--groups", required=True)
    b.add_argument("--subset", type=Path, help="cloud_subset.json: the cloud reference's file, group b1 alone")
    b.add_argument("--stance-contexts", default=None,
                   help="D-756 item 5: the stepwise system advice built once per arm, e.g. full,trimmed")
    b.add_argument("--config", type=Path, default=CONFIG_PATH,
                   help="the prompts config to build from (default the shipped neg_advisor_prompt.json); a run's "
                        "declared switches, e.g. conflict_question compare (C4), live in its own copy")
    b.add_argument("--out", required=True, type=Path)
    rb = sub.add_parser("rebuild", allow_abbrev=False,
                        help="an existing prompts file's advice prompts built again under another declared config")
    rb.add_argument("--prompts", required=True, type=Path)
    rb.add_argument("--config", required=True, type=Path)
    rb.add_argument("--out", required=True, type=Path)
    rb.add_argument("--operator-red-lines", type=Path, default=None,
                    help="#278: the operator's red lines file (neg-operator-red-lines-v1), by item id")
    r = sub.add_parser("run", allow_abbrev=False)
    r.add_argument("--prompts", required=True, type=Path)
    r.add_argument("--out", required=True, type=Path)
    a = sub.add_parser("answers", allow_abbrev=False)
    a.add_argument("--prompts", required=True, type=Path)
    a.add_argument("--run", required=True, type=Path)
    a.add_argument("--out", required=True, type=Path)
    t = sub.add_parser("texts", allow_abbrev=False)
    t.add_argument("--prompts", required=True, type=Path)
    t.add_argument("--texts", required=True, type=Path)
    t.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "build":
        value = build(args.set, args.form, [g for g in args.groups.split(",") if g], args.out, subset=args.subset,
                      config_path=args.config, stance_contexts=None if args.stance_contexts is None
                      else [c for c in args.stance_contexts.split(",") if c])
        print(json.dumps({"prompts": value["prompt_count"]}))
    elif args.command == "rebuild":
        value = rebuild(args.prompts, args.out, config_path=args.config, operator_path=args.operator_red_lines)
        print(json.dumps({"prompts": value["prompt_count"], "config_sha256": value["config_sha256"]}))
    elif args.command == "run":
        result = run(args.prompts, args.out)
        print(json.dumps({"prompts": result["prompts"], "derived": result["derived"], "seconds": result["seconds"]}))
    elif args.command == "answers":
        print(json.dumps({"rows": len(answers(args.prompts, args.run, args.out)["rows"])}))
    else:
        print(json.dumps({"rows": len(answers_from_text_file(args.prompts, args.texts, args.out)["rows"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
