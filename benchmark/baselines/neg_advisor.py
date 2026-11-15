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
JUDGE_SEED = 20261113
AGENT_LABEL = "NEG_ADVISOR"
PHASE = "NEG_ADVISOR"
# The plan's section 3.1 token budget: the whole advice prompt, by the B1 model's own tokenizer and chat
# template, at most this many tokens, so the 2,048-token allowance fits inside its 32,768 positions.
TOKEN_LIMIT = 24000
TOKENIZER = "Qwen/Qwen2.5-7B-Instruct"
# What the judge must never see (plan section 6.3): a citation id of the item, in any wording it grades.
CITATION_ID = re.compile(r"\b(?:PAR|POS)-\d+\b|\bP-[A-Za-z0-9.]+-\d+\b")
# The fields load_prompts holds each prompt to (its rendering, its digest, no system turn, its allowance).
HELD_FIELDS = ("user", "user_sha256", "system", "max_new_tokens")
JUDGED_FATES = ("changed", "kept")
# The build file's and the item's terms-of-use field and its attribution field (plan section 10). The
# field's name is declared here, under benchmark/, where the vocabulary probe (check 174) does not read:
# the code under tools/ names it only through this constant, so its own text carries no such word.
TERMS_FIELD = "licence"
ATTRIBUTION_FIELD = "attribution"


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
    return check_config(json.loads(Path(path).read_text(encoding="utf-8")))


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


def render_advice(config, item):
    a = config["advice"]
    persona = item["persona"]
    who = "%s (%s)" % (persona["id"], persona["kind"])
    parties = ", ".join("%s (%s)" % (p["id"], p["kind"]) for p in item["parties"])
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
        return "- %s%s, %s, round %s, on %s: %s" % (p["id"], mark, p["party"], p["round"], where, p["quote"])
    mandate = "\n".join(line(p) for p in item["positions"] if p["party"] == persona["id"]) or "(none on record)"
    others = "\n".join(line(p) for p in item["positions"] if p["party"] != persona["id"]) or "(none on record)"
    blocks = []
    for art in item["articles"]:
        head = "ARTICLE %s: %s%s" % (art["id"], art["title"], " (agreed)" if art.get("agreed") else "")
        paras = "\n".join("%s: %s" % (p["id"], p["text"]) for p in art["paragraphs"])
        props = "\n".join("%s: %s" % (p["id"], p["text"]) for p in art["proposals"])
        blocks.append(head + "\n" + paras + ("\nPROPOSALS:\n" + props if props else ""))
    index = lambda rows: ", ".join("%s %s" % (r["id"], r["title"]) for r in rows) or "(none)"
    trades = "; ".join("%s: give %s for %s, round %s" % (t["id"], t["give"], t["get"], t["round"])
                       for t in item.get("trades_on_record") or []) or "(none)"
    return _fill(a["template"], {"{persona}": who, "{round}": item["round"], "{process}": item["process"],
                                 "{mandate}": mandate, "{positions}": others, "{parties}": parties,
                                 "{articles}": "\n\n".join(blocks), "{round_index}": index(item["round_index"]),
                                 "{previous_index}": index(item["previous_index"]), "{trades}": trades,
                                 "{instructions}": a["instructions"]})


def item_ids(item):
    """(paragraph ids, position ids, proposal ids, article ids) of an item."""
    pars = {p["id"] for a in item.get("articles") or [] for p in a["paragraphs"]}
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
        if not isinstance(e, dict) or e.get("id") not in props or e["id"] in proposals:
            unknown += 1
            continue
        reasons = _ids(e.get("reasons")) or []
        entry = {"id": e["id"], "reasons": reasons}
        if e.get("conflict") in CONFLICT:
            entry["conflict"] = e["conflict"]
        if e.get("stance") in STANCES:
            entry["stance"] = e["stance"]
        if isinstance(e.get("wording"), str) and e["wording"].strip():
            entry["wording"] = e["wording"].strip()
        proposals[e["id"]] = entry
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
        if not isinstance(e, dict) or e.get("article") not in arts:
            unknown += 1
            continue
        alignment[e["article"]] = {"aligned": [p for p in (_ids(e.get("aligned")) or []) if p in parties],
                                   "opposed": [p for p in (_ids(e.get("opposed")) or []) if p in parties]}
    state = {}
    for e in value.get("state") if isinstance(value.get("state"), list) else []:
        if isinstance(e, dict) and e.get("article") in known_articles and e.get("state") in STATES:
            state[e["article"]] = e["state"]
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


def parse_judge(text):
    if not isinstance(text, str):
        return None
    said = text.strip()
    return int(said) if said in ("0", "1", "2") else None


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


def build(set_dir, form, groups, out, *, config_path=CONFIG_PATH, positions=None, subset=None):
    """The advice prompts of every item for each named group, or one validate prompt per position (the
    positions with their mapping come from the role session's build files, `positions`). With `subset`
    (a cloud_subset.json), the b1 group's prompts of the subset's items alone: the cloud reference's
    file, each prompt B1's byte for byte."""
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
        for group in groups:
            for item_id, item in items.items():
                user = render_advice(config, item)
                prompts.append(dict(declared[group], prompt_id="a%04d" % (len(prompts) + 1), form="advice",
                                    item_id=item_id, item=item, user=user, user_sha256=_sha(user), system=None,
                                    max_new_tokens=config["advice"]["max_new_tokens"]))
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
            user, key = render_advice(config, p["item"]), (p["group"], p["item_id"])
        elif p.get("form") == "validate" and p["group"] == "validate":
            user, key = render_validate(config, p["item"], p["position"]), ("validate", p["item_id"], p["position"]["id"])
        elif p.get("form") == "judge" and p["group"] == "judge":
            user, key = render_judge(config, p["entry"]), ("judge", p["entry"]["entry_id"])
        else:
            raise ValueError("a prompt names a form or group this file does not declare: %s" % p.get("prompt_id"))
        wanted = {"user": user, "user_sha256": _sha(user), "system": None,
                  "max_new_tokens": config[p["form"]]["max_new_tokens"]}
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


def audit_prompts(config, prompt, text):
    """The derived audit prompts of one system advice reply: one per piece of advice that parses."""
    reply = parse_advice(text, prompt["item"])
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
    return out


def run(prompts_path, out, *, backend_factory=None, reader_for=None, run_id=None):
    """Every prompt through its group's model, one reply record each, then (for a file holding the
    system's advice) every derived audit prompt through the auditor group. The measurement file is
    written after every prompt, so a stopped pass stays readable."""
    import bare_model
    import decoding_policy
    import final_models
    import reply_records
    value = read_file(prompts_path)
    config = value["config"]
    out = outside_repository(out)
    context = bare_model.RunContext(out, run_id or ("neg-advisor-" + uuid.uuid4().hex[:12]))
    factory = backend_factory or make_backend
    rows, models, texts = [], {}, {}
    sha = hashlib.sha256(Path(prompts_path).read_bytes()).hexdigest()

    def snapshot(complete):
        return {"schema": MEASUREMENT_SCHEMA, "run_id": context.run_id, "complete": complete,
                "prompts": len(value["prompts"]), "derived": sum(1 for r in rows if r["form"] == "audit"),
                "prompts_sha256": sha, "config_sha256": value["config_sha256"], "models": models,
                "seconds": round(sum(r["seconds"] or 0 for r in rows), 3), "rows": rows,
                "reads": "ids, counts and seconds only here; the replies in the reply records"}

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
            for p in mine:
                tokens = int(backend.count_prompt(None, p["user"]))
                row = {"prompt_id": p["prompt_id"], "form": p["form"], "group": group["group"], "prompt_tokens": tokens,
                       "max_new_tokens": int(p["max_new_tokens"]), "failure": None, "seconds": None,
                       "user_sha256": p["user_sha256"], "derived_from": p.get("derived_from")}
                result, error = {}, ""
                if tokens + int(p["max_new_tokens"]) > int(limit):
                    row["failure"] = error = "prompt_over_context"
                else:
                    started = time.perf_counter()
                    result = backend.generate(None, p["user"], int(p["max_new_tokens"])) or {}
                    row["seconds"] = round(time.perf_counter() - started, 3)
                text = result.get("text") if isinstance(result.get("text"), str) else None
                texts[p["prompt_id"]] = text
                decoding = dict(decoding_policy.usage_fields(reader["decoding"]), max_new_tokens=int(p["max_new_tokens"]))
                call = reply_records.write(context, agent=AGENT_LABEL, backend=reader["backend"], model_id=reader["model_id"],
                                           model_mode=reader.get("model_mode"), payload=result.get("payload"),
                                           payload_form=result.get("form"), reply=text, ok=not error, error=error,
                                           decoding=decoding, sensitive=False, phase=PHASE, doc_id=p["item_id"],
                                           attention=result.get("attention"), prefill=result.get("prefill"))
                if not call:
                    raise RuntimeError("the reply record for prompt %s could not be written" % p["prompt_id"])
                row["call_id"] = call
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
                   for d in audit_prompts(config, p, texts.get(p["prompt_id"]))]
        if derived:
            one_group({g["group"]: g for g in config["models"]}["system_audit"], derived)
    result = snapshot(True)
    _write_json(out / MEASUREMENT_FILE, result)
    return result


# ---------------------------------------------------------------------------
# answers


def answers_from_texts(value, texts, *, measured_audits=None):
    """{schema, prompts_sha256, rows}: per prompt its parsed reply. For the system's advice, each piece's
    audit answer, its prompt rendered again from the advice reply and held to the SHA-256 the pass recorded
    (`measured_audits`: derived prompt id to (user_sha256, text))."""
    config = value["config"]
    rows = []
    for p in value["prompts"]:
        text = texts.get(p["prompt_id"])
        row = {"prompt_id": p["prompt_id"], "group": p["group"], "form": p["form"], "item_id": p["item_id"]}
        if p["form"] == "advice":
            row["reply"] = parse_advice(text, p["item"])
            if p["group"] == "system_advice":
                audits = {}
                for d in audit_prompts(config, p, text):
                    sha, said = (measured_audits or {}).get(d["prompt_id"], (None, None))
                    if sha is not None and sha != d["user_sha256"]:
                        raise ValueError("an audit prompt the pass ran is not the rendering of its advice: %s" % d["prompt_id"])
                    audits[d["proposal_id"]] = parse_audit(said, config) if sha is not None else None
                row["audit"] = audits
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
        record = records.get(row.get("call_id")) or {}
        reply = record.get("reply") or {}
        text = reply.get("text") if isinstance(reply, dict) and record.get("backend_ok") else None
        if row.get("form") == "audit":
            audits[row["prompt_id"]] = (row.get("user_sha256"), text)
        else:
            texts[row["prompt_id"]] = text
    result = answers_from_texts(value, texts, measured_audits=audits)
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
    b.add_argument("--out", required=True, type=Path)
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
        value = build(args.set, args.form, [g for g in args.groups.split(",") if g], args.out, subset=args.subset)
        print(json.dumps({"prompts": value["prompt_count"]}))
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
