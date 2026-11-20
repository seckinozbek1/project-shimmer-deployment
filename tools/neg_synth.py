#!/usr/bin/env python3
"""Synthetic negotiation items: the seeded sampler, the generator's brief, the assembler, the validator and the
provenance record (standing order 102, D-707; docs/loop/stages/NEG_FINAL_ITEMS_METHOD.md section 2;
docs/loop/stages/NEG_SYNTH_PIPELINE.md).

Synthetic items are made for the development sets, the validation set and the pilots only, NEVER for the final
test (D-707): every build file says `synthetic: true`, a set folder is marked with its declared set, and
`refuse_synthetic_in_final` is the freeze's guard.

The answer comes from a structure; the model only writes prose (DyVal, Perez et al.). A card has two parts,
drawn from two separate random streams of one seed:

- `structure`: what any reader of the item may see (round k, the parties and their kinds, the articles of the
  excerpt and of the two indexes, the number of competing wordings per article, and the statement slots: who
  spoke, in which round, about which article or wording);
- `hidden`: what decides the key (the persona, every wording's fate in round k+1, whole articles gone in round
  k+1, every statement's stance, the persona's red lines, which statements use the firm wording, the trades on
  record), with `declared_key`, the labels the scorer's own rules give from it.

The brief is made from `structure` alone, so it is the same for any two hidden draws (proof: check 456). The
generator writes every variant of every slot (a wording and its revision, four versions of each statement);
Python alone picks the variant each item uses from `hidden`. The generator therefore never learns a fate, a
stance, a red line or the persona, and it never sees a key, a rubric or a Shimmer prompt.

The validator (`validate`) checks the reply's form and the texts' structure by Python (every slot present,
word bands, no bracket, identifier or option marker in a text, a revision inside its declared share band, no
shared 5-gram between two wordings of one article), assembles the build file, runs the scorer's own
`build_item` on it and refuses any field of the key that differs from the card's declared key. Meaning (does a
statement say what its variant says) is role V's labelling, never a word table here (WORDS-A).

Commands (role S, in its own folder; every path written is refused inside the repository). The card folder
is found by the tool from the set name (D-716): `<role root>/work/keys/<set>`, the role root read from
SHIMMER_ROLE_S_ROOT or, unset, the parent of this code checkout (role S runs from `<S>/code`), as declared in
`config/neg_synth.json` `card_folder`. The session names no card path; `--keys` and `--card` stay for the lead's
side and the fixtures.

    seed-base   --out <S>/SEED_BASE.json                     the run's random base, drawn once, never shown
    check-split                                             the split plan's form, its sets and ranges
    draw        --set dev_1 --seed-base F --briefs <S>/briefs   cards and prompts; counts only [--keys DIR]
    assemble    --set dev_1 --item <item id> --prompt P --reply R --set-dir <S>/sets/dev_1
                --generator-family claude --model-id <live alias> [--decoding JSON] [--regeneration N]
                                                            [--card C in place of --item]
    coverage    --set dev_1                                   class counts of the drawn cards only [--keys DIR]
    set-check   --set-dir <S>/sets/dev_1                      D-711: both record kinds held, each item records it
    select      --set dev_1 --set-dir <S>/sets/dev_1 --dropped <B's check> <label-compare>
                --out <S>/sets/dev_1/KEPT.json                the first `target` items in seed order no screen
                                                            dropped; counts printed, ids only in --out [--keys DIR]
    label-sheets --set-dir <S>/sets/dev_1 --out <V>/sheets_dev_1.json   what role V labels from: no stance,
                                                            no target article or wording, no red-line mark
    label-compare --set dev_1 --set-dir <S>/sets/dev_1 --labels <V's labels .json> --out <S>/label_compare.json
                                                            role V's labels of every built item against its card:
                                                            counts and kappa printed, dropped ids only in --out
                                                            [--keys DIR in place of --set]

A set declaring `strata` (a stratified draw, D-711 items 2 and 3, D-715 item 1, D-732; a top-up set such as
`validation_strata` names the set it joins in `tops_up`) draws each seed inside one party structure, (seed // 2)
modulo its strata in the scorer's order, crossed with the record kind; `draw`, `coverage` and `select` read it
from the set name alone, and `select` keeps the declared count of each structure. The seed scheme is unchanged
(base + offset + i, the set's own range).

It prints counts and problem codes only, never a text, a seed or a label. No model is called here.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import re
import secrets
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sna = _load("score_neg_advisor", ROOT / "tools" / "score_neg_advisor.py")
na = sna.na
af = sna.answer_form
SELECT_SCHEMA = "neg-synth-kept-v1"

CONFIG_PATH = ROOT / "config" / "neg_synth.json"
CONFIG_SCHEMA = "neg-synth-config-v1"
GENERATOR_SCHEMA = "neg-synth-generator-v1"
CARD_SCHEMA = "neg-synth-card-v1"
SEED_BASE_SCHEMA = "neg-synth-seed-base-v1"
SET_MARK_SCHEMA = "neg-synth-set-v1"
PROVENANCE_SCHEMA = "neg-synth-provenance-v1"
PROVENANCE_FILE = "PROVENANCE.jsonl"
SET_MARK = "SYNTHETIC_SET.json"
# The files whose bytes decide a card and its key: the sampler, its two declarations, and the scorer whose
# label rules the declared key mirrors. Their LF digest is each card's sampler_sha256.
VERSION_FILES = ("tools/neg_synth.py", "config/neg_synth.json", "config/neg_synth_generator.json",
                 "tools/score_neg_advisor.py")
STRUCTURE_FIELDS = ("process", "subject", "round", "parties", "articles", "round_ids", "previous_ids", "slots",
                    "record_kind", "missing_parties")
HIDDEN_FIELDS = ("persona", "fates", "removed_articles", "stances", "red_lines", "firm", "trades")
KEY_PROPOSAL_FIELDS = ("article", "conflict", "fate", "advanced", "red_line", "supported_earlier")
REPLY_KEYS = ("titles", "articles", "statements")
WORDING_KEYS = ("wording", "revision")
PROVENANCE_REQUIRED = ("schema", "item_id", "set", "synthetic", "seed", "sampler_sha256", "card_sha256",
                       "brief_sha256", "reply_sha256", "build_sha256", "generator_family", "generator_model_id",
                       "decoding", "regeneration", "generated_at", "validator")
_SLOT_ID = re.compile(r"\b[AS]\d+(?:\.\d+)?\b")
_DATED = re.compile(r"(?:^|[-_@])20\d{2}-?\d{2}-?\d{2}$")


class SeedRefused(ValueError):
    """No hidden draw of this seed met the declared constraints; the seed is counted, never used."""


# ---------------------------------------------------------------------------
# declarations


def load_config(path=CONFIG_PATH):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    if cfg.get("schema") != CONFIG_SCHEMA:
        raise ValueError("the synthetic config's schema is not %s" % CONFIG_SCHEMA)
    check_split(cfg)
    return cfg


def load_generator(cfg):
    gen = json.loads((ROOT / cfg["generation"]["template"]).read_text(encoding="utf-8"))
    if gen.get("schema") != GENERATOR_SCHEMA:
        raise ValueError("the generator template's schema is not %s" % GENERATOR_SCHEMA)
    return gen


def check_split(cfg):
    """The split plan's form: unique names, declared purposes (never a final test), at least one development
    set, exactly one validation set, at least two pilots, a target no larger than its draw, and seed ranges
    that never overlap. A top-up set (`tops_up`, a stratified draw, `check_strata`) adds items to the declared
    set it names and is not counted as a set of its own. A fix set (`fix`, `check_fix`: one fix's own fresh
    validation or pilot set, D-789) is not counted either. Returns the sets."""
    split = cfg.get("split") or {}
    sets = split.get("sets") or []
    refused = {str(p).lower() for p in split.get("refused_purposes") or []}
    names, spans = set(), []
    purposes = Counter()
    fixes = Counter()
    for s in sets:
        name, purpose = s.get("name"), str(s.get("purpose", "")).lower()
        if not name or name in names:
            raise ValueError("a split set has no name or repeats one")
        if purpose in refused or purpose not in ("development", "validation", "pilot"):
            raise ValueError("refused: set %s declares purpose %r; synthetic items are for development, "
                             "validation and pilots only, never the final test (D-707)" % (name, purpose))
        for f in ("target", "drawn", "offset"):
            if type(s.get(f)) is not int or s[f] < 0:
                raise ValueError("set %s: %s is a whole number" % (name, f))
        if not 0 < s["target"] <= s["drawn"]:
            raise ValueError("set %s: its target is above zero and at most its draw" % name)
        names.add(name)
        spans.append((s["offset"], s["offset"] + s["drawn"], name))
        fix = check_fix(s)
        if fix is not None:
            fixes[(fix, purpose)] += 1
        elif "tops_up" not in s:
            purposes[purpose] += 1
    if any(n > 1 for n in fixes.values()):
        raise ValueError("a fix declares at most one validation set and one pilot set")
    by_name = {s["name"]: s for s in sets}
    for s in sets:
        check_strata(s, by_name)
        up = by_name.get(s.get("tops_up"))
        if up is not None and "fix" in up:
            raise ValueError("set %s tops up a fix set; a fix set takes no top-up" % s["name"])
    if purposes["development"] < 1 or purposes["validation"] != 1 or purposes["pilot"] < 2:
        raise ValueError("the split needs at least one development set, exactly one validation set and at "
                         "least two pilots")
    spans.sort()
    for (a0, a1, an), (b0, b1, bn) in zip(spans, spans[1:]):
        if b0 < a1:
            raise ValueError("the seed ranges of %s and %s overlap" % (an, bn))
    return sets


FIX_ID = re.compile(r"^[A-Z][A-Z0-9]{0,15}$")
FIX_PURPOSES = ("validation", "pilot")


def check_fix(s):
    """A fix set's declaration (D-789: every fix is measured on its own fresh validation and pilot sets, built
    before the fix is tried; config/neg_synth.json `split.fix_rule`): `fix` names the fix (an upper-case id such as
    C4), `fix_decision` the decision that orders it; its purpose is validation or pilot, it tops up nothing, and it
    is never counted as the plan's one validation set or one of its pilots. None for a set without `fix`."""
    if "fix" not in s:
        return None
    fix, name = s.get("fix"), s["name"]
    if not isinstance(fix, str) or not FIX_ID.match(fix):
        raise ValueError("set %s: fix is an upper-case id of a declared fix (for example C4)" % name)
    if not isinstance(s.get("fix_decision"), str) or not s["fix_decision"].strip():
        raise ValueError("set %s: a fix set names the decision that orders it (fix_decision)" % name)
    if str(s.get("purpose", "")).lower() not in FIX_PURPOSES:
        raise ValueError("set %s: a fix set is a validation or a pilot set" % name)
    if "tops_up" in s:
        raise ValueError("set %s: a fix set tops up no other set" % name)
    return fix


def check_strata(s, by_name):
    """A stratified draw's declaration (D-711 items 2 and 3, D-715 item 1, D-732; config/neg_synth.json
    `strata`): `strata` {party structure: the fewest items the set keeps of it}, each a structure the scorer
    computes (score_neg_advisor.STRUCTURES), each at least one, its target their sum, and at least two seeds per
    item it keeps of each structure. `tops_up` names the declared set the items join, of the same purpose, which
    is no top-up itself and draws no strata; a top-up always draws strata. A set without either draws as before."""
    name, strata, up = s["name"], s.get("strata"), s.get("tops_up")
    if strata is None and up is None:
        return None
    if up is not None:
        base = by_name.get(up)
        if base is None or up == name or "tops_up" in base or "strata" in base:
            raise ValueError("set %s tops up %r, which is not a declared plain set" % (name, up))
        if str(base.get("purpose", "")).lower() != str(s.get("purpose", "")).lower():
            raise ValueError("set %s tops up a set of another purpose" % name)
        if strata is None:
            raise ValueError("set %s: a top-up set declares its strata" % name)
    if not isinstance(strata, dict) or not strata or set(strata) - set(sna.STRUCTURES):
        raise ValueError("set %s: strata name the scorer's party structures only: %s"
                         % (name, ", ".join(sna.STRUCTURES)))
    if any(type(v) is not int or v < 1 for v in strata.values()):
        raise ValueError("set %s: each stratum keeps a whole number of items, at least one" % name)
    if s["target"] != sum(strata.values()):
        raise ValueError("set %s: its target is the sum of its strata" % name)
    if any(s["drawn"] // len(strata) < 2 * v for v in strata.values()):
        raise ValueError("set %s: it draws at least two seeds per item it keeps of each stratum" % name)
    return strata


def strata_order(s):
    """A stratified set's structures in the scorer's order: the one order its seeds are assigned in."""
    strata = s.get("strata") or {}
    return [x for x in sna.STRUCTURES if x in strata]


def stratum_of(seed, s):
    """The party structure a stratified set's seed is drawn in (D-732): (seed // 2) modulo the number of strata,
    so with the record kind (seed modulo 2, D-711) the two are crossed and every stratum holds both kinds about
    half and half. None for a set without strata, whose seeds draw as before."""
    order = strata_order(s)
    return order[(seed // 2) % len(order)] if order else None


def split_set(cfg, name):
    for s in check_split(cfg):
        if s["name"] == name:
            return s
    raise ValueError("no declared set %r" % name)


_ITEM_ID = re.compile(r"^syn-[0-9a-f]{16}$")


def role_root(cfg, environ=None):
    """Role S's root (D-716): the declared environment variable when set, else the parent of this code checkout,
    since role S runs from `<S>/code`. Declared in config/neg_synth.json `card_folder`, never a path in code."""
    decl = cfg["card_folder"]
    if decl.get("root_default") != "checkout_parent":
        raise ValueError("card_folder.root_default declares an unknown default")
    value = (os.environ if environ is None else environ).get(decl["root_env"], "").strip()
    return Path(value) if value else ROOT.parent


def card_folder(cfg, set_name, environ=None):
    """The card folder of one declared set: `<role root>/<relative>/<set>` (D-716). A name that is not a declared
    set is refused, so no other folder can be reached through it."""
    split_set(cfg, set_name)
    return role_root(cfg, environ).joinpath(*cfg["card_folder"]["relative"], set_name)


def card_path(cfg, set_name, item, environ=None):
    """One card of a declared set by its item id; an id of another form is refused."""
    if not _ITEM_ID.match(str(item)):
        raise SystemExit("refused: not an item id")
    return card_folder(cfg, set_name, environ) / (item + ".card.json")


def _keys_dir(args, cfg, *, must_exist=True):
    """The explicit --keys folder when given (the lead's side and the fixtures), else the set's declared card
    folder. A refusal names neither the folder nor any card in it."""
    if getattr(args, "keys", None):
        return Path(args.keys)
    if not getattr(args, "set", None):
        raise SystemExit("refused: give --set (the card folder is found from it) or --keys")
    folder = card_folder(cfg, args.set)
    if must_exist and not folder.is_dir():
        raise SystemExit("refused: set %s has no card folder under the role root (D-716)" % args.set)
    return folder


def sampler_sha256(root=ROOT):
    h = hashlib.sha256()
    for rel in VERSION_FILES:
        data = (Path(root) / rel).read_bytes().replace(b"\r\n", b"\n")
        h.update(rel.encode("utf-8") + b"\0" + hashlib.sha256(data).hexdigest().encode("ascii") + b"\n")
    return h.hexdigest()


def _sha(value):
    if isinstance(value, (bytes, bytearray)):
        return hashlib.sha256(value).hexdigest()
    if isinstance(value, str):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def item_id_of(seed):
    return "syn-" + hashlib.sha256(("neg-synth-item:%d" % seed).encode("ascii")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# seeds and the split


def new_seed_base():
    """A random base for one run's seeds (role S, once). Kept in its folder; the lead never sees it."""
    return {"schema": SEED_BASE_SCHEMA, "base": secrets.randbelow(2 ** 52) + 2 ** 40}


def seeds_for(cfg, name, base):
    s = split_set(cfg, name)
    if type(base) is not int or base < 0:
        raise ValueError("the seed base is a whole number")
    return list(range(base + s["offset"], base + s["offset"] + s["drawn"]))


# ---------------------------------------------------------------------------
# the sampler


def _rng(seed, stream):
    return random.Random("neg-synth:%d:%s" % (seed, stream))


def _pick(rng, weights):
    keys = list(weights)
    return rng.choices(keys, [float(weights[k]) for k in keys])[0]


def _party_id(name):
    return re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")


def party_kinds(rng, d, structure=None):
    """The parties' kinds. With no stratum, the number from `parties` and each kind from `coalition_share`, as
    always. In a stratum (D-732) the two-party structures fix them (two singles, two coalitions, or one of each
    in a drawn order), and three_or_more draws the number from `parties` restricted to three or more and each
    kind from `coalition_share`."""
    if structure is None:
        n = int(_pick(rng, d["parties"]))
        return ["coalition" if rng.random() < d["coalition_share"] else "single" for _ in range(n)]
    if structure == sna.TWO_SINGLES:
        return ["single", "single"]
    if structure == sna.TEAMS:
        return ["coalition", "coalition"]
    if structure == sna.ONE_VS_COALITION:
        return rng.sample(["single", "coalition"], 2)
    if structure == sna.THREE_OR_MORE:
        many = {n: w for n, w in d["parties"].items() if int(n) >= 3}
        if not many:
            raise ValueError("the declared parties distribution gives no three-party item")
        n = int(_pick(rng, many))
        return ["coalition" if rng.random() < d["coalition_share"] else "single" for _ in range(n)]
    raise ValueError("not a party structure: %r" % (structure,))


def draw_structure(seed, cfg, structure=None):
    """What the item shows, from the seed's structure stream alone; in a stratified set, inside the seed's
    stratum (`structure`, stratum_of)."""
    rng = _rng(seed, "structure")
    d, pools = cfg["distributions"], cfg["pools"]
    lo_round, hi_round = cfg["constraints"]["rounds"]
    k = int(_pick(rng, d["round_k"]))
    if not lo_round <= k < hi_round:
        raise ValueError("round k is %d; it needs a round k+1 inside %s" % (k, cfg["constraints"]["rounds"]))
    kinds = party_kinds(rng, d, structure)
    singles = iter(rng.sample(pools["single_names"], kinds.count("single")))
    groups = iter(rng.sample(pools["coalition_names"], kinds.count("coalition")))
    parties = []
    for kind in kinds:
        name = next(groups) if kind == "coalition" else next(singles)
        parties.append({"id": _party_id(name), "name": name, "kind": kind})
    subject = rng.choice(pools["subjects"])

    n_br = int(_pick(rng, d["bracketed_articles"]))
    n_closed = int(_pick(rng, d["closed_articles"]))
    n_new = 1 if k > 1 and rng.random() < d["new_article_share"] else 0
    lo, hi = cfg["constraints"]["excerpt_articles"]
    if not lo <= n_br + n_closed + n_new <= hi:
        n_new = 0
    if not lo <= n_br + n_closed + n_new <= hi:
        raise ValueError("the declared distributions give an excerpt outside %s" % [lo, hi])
    n_other = int(_pick(rng, d["other_round_articles"]))
    n_dropped = 1 if k > 1 and rng.random() < d["dropped_article_share"] else 0
    a_lo, a_hi = d["article_id_range"]
    numbers = rng.sample(range(a_lo, a_hi + 1), n_br + n_closed + n_new + n_other + n_dropped)
    roles = (["bracketed"] * n_br + ["closed"] * n_closed + ["new"] * n_new + ["other"] * n_other
             + ["dropped"] * n_dropped)
    by_role = {}
    for number, role in zip(numbers, roles):
        by_role.setdefault(role, []).append(number)
    articles = []
    for number in sorted(by_role.get("bracketed", []) + by_role.get("closed", []) + by_role.get("new", [])):
        aid = "A%d" % number
        if number in by_role.get("closed", []):
            articles.append({"id": aid, "agreed": True, "new": False, "proposals": 0})
        else:
            articles.append({"id": aid, "agreed": False, "new": number in by_role.get("new", []),
                             "proposals": int(_pick(rng, d["proposals_per_article"]))})
    excerpt = [a["id"] for a in articles]
    round_ids = sorted(excerpt + ["A%d" % x for x in by_role.get("other", [])], key=lambda s: int(s[1:]))
    previous_ids = []
    if k > 1:
        new_ids = {"A%d" % x for x in by_role.get("new", [])}
        previous_ids = sorted([a for a in round_ids if a not in new_ids]
                              + ["A%d" % x for x in by_role.get("dropped", [])], key=lambda s: int(s[1:]))

    open_articles = [a for a in articles if not a["agreed"]]
    closed = [a for a in articles if a["agreed"]]
    slots = []

    def add(party, article, proposal):
        rnd = k if article["new"] else rng.randint(1, k)
        slots.append({"party": party["id"], "round": rnd, "article": article["id"], "proposal": proposal})

    for party in parties:
        covered = set()
        for a in open_articles:
            if rng.random() >= d["slot_share"]:
                continue
            covered.add(a["id"])
            if rng.random() < d["proposal_level_share"]:
                # A party that speaks wording by wording speaks to every wording of the article, so whether a
                # wording is stated never depends on how many wordings compete (the cue check's bracket count).
                for i in range(1, a["proposals"] + 1):
                    add(party, a, i)
            else:
                add(party, a, None)
        need = min(d["min_articles_per_party"], len(open_articles)) - len(covered)
        rest = [a for a in open_articles if a["id"] not in covered]
        for a in rng.sample(rest, max(0, need)):
            add(party, a, None)
        for a in closed:
            if rng.random() < d["closed_slot_share"]:
                add(party, a, None)
    # D-711: the record kind alternates with the seed, so every set's draws hold both kinds about half and
    # half. A missing-notes item keeps one party in the item with none of its notes on record (its slots are
    # dropped before numbering): its key answer is not_stated, and it is never the persona.
    record_kind = record_kind_of(seed, cfg)
    missing = []
    if record_kind == "missing_notes":
        missing = sorted(p["id"] for p in rng.sample(parties, cfg["record_kinds"]["missing_parties"]))
        slots = [s for s in slots if s["party"] not in missing]
    rng.shuffle(slots)
    for i, s in enumerate(slots, 1):
        s["slot"] = "S%d" % i
    return {"process": "%s %s" % (cfg["item"]["process_prefix"], item_id_of(seed)), "subject": subject,
            "round": k, "parties": parties, "articles": articles, "round_ids": round_ids,
            "previous_ids": previous_ids, "slots": slots, "record_kind": record_kind, "missing_parties": missing}


def record_kind_of(seed, cfg):
    kinds = cfg["record_kinds"]["kinds"]
    if tuple(kinds) != sna.RECORD_KINDS:
        raise ValueError("the declared record kinds are the scorer's: %s" % ", ".join(sna.RECORD_KINDS))
    return kinds[seed % len(kinds)]


def draw_hidden(seed, structure, cfg, attempt):
    """What decides the key, from the seed's hidden stream for one attempt."""
    rng = _rng(seed, "hidden:%d" % attempt)
    d = cfg["distributions"]
    k = structure["round"]
    persona = rng.choice([p["id"] for p in structure["parties"] if p["id"] not in structure.get("missing_parties", [])])
    agreed = {a["id"]: a["agreed"] for a in structure["articles"]}
    stances = {s["slot"]: _pick(rng, d["stances_closed"] if agreed[s["article"]] else d["stances_bracketed"])
               for s in structure["slots"]}
    fates, removed_articles = {}, []
    r = d["resolved_share"]
    for a in structure["articles"]:
        if a["agreed"]:
            continue
        n = a["proposals"]
        if rng.random() < d["whole_article_removed_share"]:
            removed_articles.append(a["id"])
            for i in range(1, n + 1):
                fates["%s.%d" % (a["id"], i)] = "removed"
            continue
        # At most one competing wording of an article is resolved (kept or changed), and each wording is
        # resolved with the same share r whatever the article's size: one winner with probability n * r.
        if n * r > 1:
            raise ValueError("resolved_share %.2f cannot hold for an article of %d wordings" % (r, n))
        winner = rng.randint(1, n) if rng.random() < n * r else None
        for i in range(1, n + 1):
            fates["%s.%d" % (a["id"], i)] = _pick(rng, d["resolved_split"] if i == winner else d["unresolved_split"])
    candidates = [s["slot"] for s in structure["slots"]
                  if s["party"] == persona and stances[s["slot"]] == "oppose" and not agreed[s["article"]]]
    red = [s for s in candidates if rng.random() < d["red_line_share"]]
    if candidates and not red:
        red = [rng.choice(candidates)]
    firm = set(red)
    for s in structure["slots"]:
        if s["party"] != persona and stances[s["slot"]] == "oppose" and \
                rng.random() < d["firm_variant_other_parties_share"]:
            firm.add(s["slot"])
    trades = []
    wordings = sorted(fates)
    if len(wordings) >= 2 and rng.random() < d["trade_share"]:
        give, get = rng.sample(wordings, 2)
        trades.append({"id": "T-1", "give": give, "get": get, "round": rng.randint(1, k)})
    return {"persona": persona, "fates": fates, "removed_articles": sorted(removed_articles),
            "stances": stances, "red_lines": sorted(red, key=lambda x: int(x[1:])),
            "firm": sorted(firm, key=lambda x: int(x[1:])), "trades": trades}


def positions_of(structure, hidden):
    """The position records the declared key is computed from: statement slot S<n> is POS-<n>."""
    return [{"id": "POS-" + s["slot"][1:], "party": s["party"], "round": s["round"], "article": s["article"],
             "proposal": s["proposal"], "stance": hidden["stances"][s["slot"]]} for s in structure["slots"]]


def declared_key(structure, hidden):
    """The key the scorer's own rules give from the card, before any text exists: the labels of
    score_neg_advisor.build_item with every fate taken from the card (plan sections 3.2, 4.1, 4.2)."""
    positions = positions_of(structure, hidden)
    persona = hidden["persona"]
    red_ids = {"POS-" + s[1:] for s in hidden["red_lines"]}
    k = structure["round"]
    previous = set(structure["previous_ids"])
    round_ids = set(structure["round_ids"]) | {a["id"] for a in structure["articles"]}
    kinds = {p["id"]: p["kind"] for p in structure["parties"]}
    props, arts, align = {}, {}, {}
    for a in structure["articles"]:
        aid = a["id"]
        arts[aid] = {"state": sna.state_label(aid, k, previous, a["agreed"], a["proposals"] > 0, positions,
                                              persona)}
        for i in range(1, a["proposals"] + 1):
            mine = sna.applicable(positions, persona, aid, i)
            lab = sna.conflict_label(positions, persona, aid, i)
            f = hidden["fates"]["%s.%d" % (aid, i)]
            adv = (("advanced" if f == "kept" else "not_advanced" if f == "removed" else None)
                   if lab == "no_conflict" else
                   ("advanced" if f == "removed" else "not_advanced" if f == "kept" else None)
                   if lab == "conflict" else None)
            props["P-%s-%d" % (aid, i)] = {
                "article": aid, "conflict": lab, "fate": f, "advanced": adv,
                "red_line": lab == "conflict" and any(p["id"] in red_ids and p["stance"] == "oppose" for p in mine),
                "supported_earlier": any(p["stance"] in ("support", "accept") and p["round"] < k for p in mine)}
        numbers = list(range(1, a["proposals"] + 1))
        align[aid] = {p: sna.alignment_label(positions, persona, p, aid, numbers) for p in kinds if p != persona}
    for aid in sorted(previous - round_ids):
        arts[aid] = {"state": "dropped"}
    targets = sorted(p for p in {q for cells in align.values() for q in cells}
                     if any(c.get(p) == "aligned" for c in align.values())
                     and not any(c.get(p) == "opposed" for c in align.values()))
    key = {"proposals": props, "articles": arts, "alignment": align, "approach_targets": targets}
    item_like = {"parties": [{"id": p, "kind": kinds[p]} for p in kinds],
                 "persona": {"id": persona, "kind": kinds[persona]}}
    key["configuration"] = sna.configuration(item_like, key)
    return key


def m10_class(cfg, fate):
    c = cfg["constraints"]
    return "movable" if fate in c["movable_fates"] else "settled" if fate in c["settled_fates"] else None


def meets_constraints(key, cfg):
    c = cfg["constraints"]
    props = key["proposals"].values()
    conflicts = Counter(p["conflict"] for p in props)
    m10 = Counter(m10_class(cfg, p["fate"]) for p in props)
    return (conflicts["conflict"] >= c["min_conflict"] and conflicts["no_conflict"] >= c["min_no_conflict"]
            and m10["movable"] >= c["min_movable"] and m10["settled"] >= c["min_settled"]
            and sum(1 for p in props if p["red_line"]) >= c["min_red_line"])


def sample_card(seed, cfg=None, *, version=None, stratum=None):
    """One seed's card: structure, hidden draw, declared key. Deterministic in (seed, config, code). In a
    stratified set the card records its `stratum`, the party structure the scorer computes from its parties."""
    cfg = cfg or load_config()
    structure = draw_structure(seed, cfg, stratum)
    if stratum is not None and sna.structure_of(structure["parties"]) != stratum:
        raise ValueError("the drawn parties are not of the seed's stratum")
    for attempt in range(cfg["constraints"]["max_hidden_attempts"]):
        hidden = draw_hidden(seed, structure, cfg, attempt)
        key = declared_key(structure, hidden)
        if meets_constraints(key, cfg):
            card = {"schema": CARD_SCHEMA, "item_id": item_id_of(seed), "seed": seed, "synthetic": True,
                    "sampler_sha256": version or sampler_sha256(), "hidden_attempt": attempt,
                    "structure": structure, "hidden": hidden, "declared_key": key}
            if stratum is not None:
                card["stratum"] = stratum
            return card
    raise SeedRefused("no hidden draw met the declared constraints")


# ---------------------------------------------------------------------------
# the brief: structure only


def brief_view(card):
    """The one projection of a card the generator's brief is made from. It reads `structure` alone; nothing
    under `hidden` or `declared_key`, and no seed or digest, can reach the brief through it."""
    s = card["structure"]
    names = {p["id"]: p["name"] for p in s["parties"]}
    return {
        "subject": s["subject"],
        "parties": [dict({"name": p["name"], "kind": p["kind"]},
                         **({"no_notes": True} if p["id"] in s.get("missing_parties", []) else {}))
                    for p in s["parties"]],
        "titles": sorted(set(s["round_ids"]) | set(s["previous_ids"]), key=lambda x: int(x[1:])),
        "articles": [{"id": a["id"], "agreed": a["agreed"],
                      "slots": ["%s.%d" % (a["id"], i) for i in range(1, a["proposals"] + 1)]}
                     for a in s["articles"]],
        "statements": [{"slot": x["slot"], "party": names[x["party"]], "round": x["round"], "article": x["article"],
                        "wording": None if x["proposal"] is None else "%s.%d" % (x["article"], x["proposal"])}
                       for x in s["slots"]]}


def render_prompt(view, gen, cfg):
    forms = gen["line_forms"]
    parties = "\n".join(forms["party_coalition" if p["kind"] == "coalition" else "party_single"].format(name=p["name"])
                        + (forms["party_no_notes"] if p.get("no_notes") else "") for p in view["parties"])
    titles = "\n".join(forms["title"].format(article=a) for a in view["titles"])
    arts = []
    for a in view["articles"]:
        if a["agreed"]:
            arts.append(forms["agreed"].format(article=a["id"]))
        else:
            arts.append(forms["open_article"].format(article=a["id"], count=len(a["slots"]),
                                                     slots=", ".join(a["slots"])))
    stmts = []
    for x in view["statements"]:
        if x["wording"] is None:
            stmts.append(forms["statement_article"].format(slot=x["slot"], party=x["party"], round=x["round"],
                                                           article=x["article"]))
        else:
            stmts.append(forms["statement_proposal"].format(slot=x["slot"], party=x["party"], round=x["round"],
                                                            wording=x["wording"], article=x["article"]))
    bands = "\n".join(forms["band"].format(field=f, low=lo, high=hi)
                      for f, (lo, hi) in cfg["generation"]["word_bands"].items())
    reply_form = json.dumps(gen["reply_form"], indent=1, ensure_ascii=False)
    out = gen["template"]
    for name, value in (("setting", view["subject"]), ("parties", parties), ("titles", titles),
                        ("articles", "\n".join(arts)), ("statements", "\n".join(stmts)), ("bands", bands),
                        ("reply_form", reply_form)):
        out = out.replace("{" + name + "}", value)
    return out


def brief_of(card, cfg=None, gen=None):
    cfg = cfg or load_config()
    return render_prompt(brief_view(card), gen or load_generator(cfg), cfg)


# ---------------------------------------------------------------------------
# assembly and the validator


def _words(text):
    return str(text).split()


def _grams(text):
    return sna.grams(text)


def _share(a, b):
    ga = _grams(a)
    return len(ga & _grams(b)) / len(ga) if ga else 0.0


def variant_of(card, slot, cfg):
    v = cfg["generation"]["variants"]
    return v["firm"] if slot in card["hidden"]["firm"] else v[card["hidden"]["stances"][slot]]


def assemble(card, reply, cfg):
    """The build file of a card and a generator reply (tools/score_neg_advisor.py's build schema)."""
    s, h = card["structure"], card["hidden"]
    titles = reply["titles"]
    arts, nxt = [], {}
    for a in s["articles"]:
        body = reply["articles"][a["id"]]
        if a["agreed"]:
            text = body["agreed_text"].strip()
            arts.append({"id": a["id"], "title": titles[a["id"]], "text": text, "agreed": True})
            nxt[a["id"]] = text
            continue
        chapeau = body["chapeau"].strip()
        slots = ["%s.%d" % (a["id"], i) for i in range(1, a["proposals"] + 1)]
        w = {x: body["wordings"][x] for x in slots}
        arts.append({"id": a["id"], "title": titles[a["id"]],
                     "text": chapeau + "\n\n" + "\n\n".join("[%s]" % w[x]["wording"].strip() for x in slots)})
        if a["id"] in h["removed_articles"]:
            continue
        parts = [chapeau]
        for x in slots:
            f = h["fates"][x]
            if f == "kept":
                parts.append(w[x]["wording"].strip())
            elif f == "changed":
                parts.append(w[x]["revision"].strip())
            elif f == "open":
                parts.append("[%s]" % w[x]["wording"].strip())
        nxt[a["id"]] = "\n\n".join(parts)
    positions = []
    for p, x in zip(positions_of(s, h), s["slots"]):
        p = dict(p, quote=reply["statements"][x["slot"]][variant_of(card, x["slot"], cfg)].strip(),
                 source="invented record, round %d, statement %s" % (x["round"], x["slot"][1:]))
        positions.append(p)
    item = cfg["item"]
    return {
        "schema": sna.BUILD_SCHEMA, "item_id": card["item_id"], "part": item["part"], "process": s["process"],
        "round": s["round"], "synthetic": True, "post_cutoff": bool(item["post_cutoff"]),
        "record_kind": s["record_kind"], "missing_parties": list(s["missing_parties"]),
        na.TERMS_FIELD: item["terms_text"], na.ATTRIBUTION_FIELD: item["attribution_text"],
        "persona": {"id": h["persona"], "kind": next(p["kind"] for p in s["parties"] if p["id"] == h["persona"])},
        "red_lines": ["POS-" + x[1:] for x in h["red_lines"]],
        "parties": [{"id": p["id"], "kind": p["kind"]} for p in s["parties"]],
        "articles": arts,
        "round_index": [{"id": a, "title": titles[a]} for a in s["round_ids"]],
        "previous_index": [{"id": a, "title": titles[a]} for a in s["previous_ids"]],
        "next_articles": nxt,
        "positions": positions,
        "trades_on_record": [{"id": t["id"], "give": [t["give"].split(".")[0], int(t["give"].split(".")[1])],
                              "get": [t["get"].split(".")[0], int(t["get"].split(".")[1])], "round": t["round"]}
                             for t in h["trades"]]}


def _text_problems(where, text, band):
    out = []
    if not isinstance(text, str) or not text.strip():
        return ["reply_form:" + where]
    n = len(_words(text))
    if not band[0] <= n <= band[1]:
        out.append("words:" + where)
    if "[" in text or "]" in text:
        out.append("bracket:" + where)
    if na.CITATION_ID.search(text) or _SLOT_ID.search(text):
        out.append("identifier:" + where)
    if sna._BRACKET_MARK.search(text):
        out.append("option_mark:" + where)
    return out


def _keys_exact(value, expected):
    return isinstance(value, dict) and set(value) == set(expected)


def reply_problems(card, reply, cfg):
    """The reply's form and its texts' structure, by Python. Problem codes only, never text."""
    s = card["structure"]
    bands = cfg["generation"]["word_bands"]
    variants = sorted(set(cfg["generation"]["variants"].values()))
    lo, hi = cfg["generation"]["revision_share_band"]
    if not _keys_exact(reply, REPLY_KEYS):
        return ["reply_form:top"]
    out = []
    ids = set(s["round_ids"]) | set(s["previous_ids"])
    if not _keys_exact(reply["titles"], ids):
        out.append("reply_form:titles")
    else:
        for a in sorted(ids):
            out += _text_problems("title:" + a, reply["titles"][a], bands["title"])
    if not _keys_exact(reply["articles"], [a["id"] for a in s["articles"]]):
        return out + ["reply_form:articles"]
    seen = {}
    for a in s["articles"]:
        body = reply["articles"][a["id"]]
        if a["agreed"]:
            if not _keys_exact(body, ["agreed_text"]):
                out.append("reply_form:" + a["id"])
                continue
            out += _text_problems("agreed:" + a["id"], body["agreed_text"], bands["agreed_text"])
            continue
        slots = ["%s.%d" % (a["id"], i) for i in range(1, a["proposals"] + 1)]
        if not _keys_exact(body, ["chapeau", "wordings"]) or not _keys_exact(body["wordings"], slots) or \
                not all(_keys_exact(body["wordings"][x], WORDING_KEYS) for x in slots):
            out.append("reply_form:" + a["id"])
            continue
        out += _text_problems("chapeau:" + a["id"], body["chapeau"], bands["chapeau"])
        for x in slots:
            out += _text_problems("wording:" + x, body["wordings"][x]["wording"], bands["wording"])
            out += _text_problems("revision:" + x, body["wordings"][x]["revision"], bands["revision"])
        if any(o.startswith("reply_form:") for o in out):
            continue
        for x in slots:
            w, r = body["wordings"][x]["wording"], body["wordings"][x]["revision"]
            if not lo <= _share(w, r) <= hi:
                out.append("revision_share:" + x)
            if _grams(w) & _grams(body["chapeau"]) or _grams(r) & _grams(body["chapeau"]):
                out.append("overlap_chapeau:" + x)
            for y in slots:
                if y != x and (_grams(w) & (_grams(body["wordings"][y]["wording"]) |
                                            _grams(body["wordings"][y]["revision"]))):
                    out.append("overlap:" + x)
                    break
            norm = sna.norm_text(w)
            if norm in seen:
                out.append("duplicate:" + x)
            seen[norm] = x
    slots = [x["slot"] for x in s["slots"]]
    if not _keys_exact(reply["statements"], slots):
        return out + ["reply_form:statements"]
    for x in slots:
        body = reply["statements"][x]
        if not _keys_exact(body, variants):
            out.append("reply_form:" + x)
            continue
        for v in variants:
            out += _text_problems("statement:%s:%s" % (x, v), body[v], bands["statement"])
        if len({sna.norm_text(body[v]) for v in variants if isinstance(body[v], str)}) != len(variants):
            out.append("variants_alike:" + x)
    return out


def key_problems(card, build):
    """The scorer's own key of the assembled build against the card's declared key, field by field."""
    try:
        _item, key = sna.build_item(build)
    except (ValueError, KeyError, TypeError):
        return ["build_refused"]
    want = card["declared_key"]
    out = []
    if set(key["proposals"]) != set(want["proposals"]):
        out.append("key:proposals")
    for pid in sorted(set(key["proposals"]) & set(want["proposals"])):
        for f in KEY_PROPOSAL_FIELDS:
            if key["proposals"][pid].get(f) != want["proposals"][pid].get(f):
                out.append("key:%s:%s" % (f, pid))
    if {a: v["state"] for a, v in key["articles"].items()} != {a: v["state"] for a, v in want["articles"].items()}:
        out.append("key:state")
    if key["alignment"] != want["alignment"]:
        out.append("key:alignment")
    if key["approach_targets"] != want["approach_targets"]:
        out.append("key:approach_targets")
    if key["configuration"] != want["configuration"]:
        out.append("key:configuration")
    return out


def validate(card, reply, cfg=None):
    """(problems, build): the reply's structure, then the scorer's key of the assembled build against the card.
    A non-empty problem list rejects the item (regenerated once from a fresh card, then dropped and counted)."""
    cfg = cfg or load_config()
    problems = reply_problems(card, reply, cfg)
    if problems:
        return problems, None
    build = assemble(card, reply, cfg)
    problems = key_problems(card, build)
    return problems, (None if problems else build)


def read_reply(raw):
    """(object, None) or (None, reason): the generator's reply read once by the project's one form reader
    (tools/answer_form.py, ANSWER-FORM-A): fences, prose around it and several objects (the last read) are form,
    never a rejection; the reply's bytes are what provenance digests."""
    try:
        text = bytes(raw).decode("utf-8")
    except UnicodeDecodeError:
        return None, "not_utf8"
    obj, why, _several = af.last_object(text)
    return (obj, None) if obj is not None else (None, why)


def select(cards, set_dir, target, dropped=()):
    """The set's kept items: the first `target` built items in seed order that no screen dropped (role B's
    deduplication, label-compare's mismatches, a cue batch). Ids out, in order; the seeds never leave."""
    built = {q.parent.name for q in Path(set_dir).glob("build/*/build.json")}
    drop = set(dropped)
    order = [c["item_id"] for c in sorted(cards, key=lambda c: c["seed"]) if c["item_id"] in built]
    kept = [i for i in order if i not in drop][:target]
    kinds = Counter(c["structure"]["record_kind"] for c in cards if c["item_id"] in set(kept))
    return {"schema": SELECT_SCHEMA, "target": target, "built": len(order), "dropped": len(drop & set(order)),
            "kept": kept, "short": max(0, target - len(kept)), "record_kinds": dict(kinds)}


def structure_counts(cards):
    """{party structure: cards}, each computed by the scorer from the card's declared parties alone."""
    return dict(Counter(sna.structure_of(c["structure"]["parties"]) for c in cards))


def select_strata(cards, set_dir, strata, dropped=()):
    """A stratified set's kept items (D-732): per declared structure, the first `strata[structure]` built items
    of that structure in seed order that no screen dropped; a structure with fewer is short by the difference,
    so a stratum never borrows from another. Ids out, in seed order; the seeds never leave."""
    built = {q.parent.name for q in Path(set_dir).glob("build/*/build.json")}
    drop = set(dropped)
    order = [c for c in sorted(cards, key=lambda c: c["seed"]) if c["item_id"] in built]
    keep, by_structure = set(), Counter()
    for c in order:
        st = sna.structure_of(c["structure"]["parties"])
        if c["item_id"] in drop or by_structure[st] >= strata.get(st, 0):
            continue
        keep.add(c["item_id"])
        by_structure[st] += 1
    kept = [c["item_id"] for c in order if c["item_id"] in keep]
    kinds = Counter(c["structure"]["record_kind"] for c in order if c["item_id"] in keep)
    short = {st: strata[st] - by_structure[st] for st in strata if by_structure[st] < strata[st]}
    return {"schema": SELECT_SCHEMA, "target": sum(strata.values()), "built": len(order),
            "dropped": len(drop & {c["item_id"] for c in order}), "kept": kept, "short": sum(short.values()),
            "record_kinds": dict(kinds), "structures": {st: by_structure[st] for st in strata},
            "short_by_structure": short}


def strata_problems(cov, s):
    """A stratified set's drawn cards against its declared strata: a structure with fewer cards than it keeps."""
    return ["structure:%s" % st for st, n in (s.get("strata") or {}).items()
            if cov.get("structure", {}).get(st, 0) < n]


# ---------------------------------------------------------------------------
# role V's labels against the cards


SHEET_SCHEMA = "neg-synth-label-sheet-v1"
SHEET_POSITION_FIELDS = ("id", "party", "round", "quote")


def label_sheet(build):
    """What role V labels from: the round-k articles, the parties and the persona, and each position's quote
    with its party and round only. Never the stance, the article or wording a position was written for, the
    red-line marks, round k+1 or the card."""
    return {"schema": SHEET_SCHEMA, "item_id": build["item_id"], "round": build["round"],
            "persona": {"id": build["persona"]["id"], "kind": build["persona"]["kind"]},
            "parties": [{"id": p["id"], "kind": p["kind"]} for p in build["parties"]],
            "articles": [{"id": a["id"], "title": a["title"], "text": a["text"], "agreed": bool(a.get("agreed"))}
                         for a in build["articles"]],
            "positions": [{f: p[f] for f in SHEET_POSITION_FIELDS} for p in build["positions"]]}


def _label_tuple(article, proposal, stance):
    """The plan's one unit of mapping agreement: (article, proposal, stance) (plan section 4.2)."""
    return "%s|%s|%s" % (article, proposal, stance)


def compare_labels(cards, labels):
    """Role V's labels, made from the item text alone, against the cards. `labels` is {item id: {POS id:
    {article, proposal, stance, red_line}}}; red_line is read on the persona's positions only (the item's
    mandate, plan section 3 item 4). An item with any position labelled otherwise, or not labelled, is dropped
    and counted. Agreement (AM-1, score_neg_advisor.agreement) over the triple and over red lines."""
    ref_t, got_t, ref_r, got_r = [], [], [], []
    kept, dropped = [], []
    for card in cards:
        mine = labels.get(card["item_id"]) or {}
        red = {"POS-" + s[1:] for s in card["hidden"]["red_lines"]}
        bad = False
        for p in positions_of(card["structure"], card["hidden"]):
            got = mine.get(p["id"]) if isinstance(mine.get(p["id"]), dict) else {}
            want = _label_tuple(p["article"], p["proposal"], p["stance"])
            have = _label_tuple(got.get("article"), got.get("proposal"), got.get("stance")) if got else "no_answer"
            ref_t.append(want)
            got_t.append(have)
            bad |= want != have
            if p["party"] == card["hidden"]["persona"]:
                ref_r.append(p["id"] in red)
                got_r.append(got.get("red_line") if got else "no_answer")
                bad |= (p["id"] in red) != got.get("red_line")
        (dropped if bad else kept).append(card["item_id"])
    return {"items": len(cards), "kept": len(kept), "dropped": len(dropped), "dropped_ids": sorted(dropped),
            "mapping": sna.agreement(ref_t, got_t), "red_line": sna.agreement(ref_r, got_r)}


# ---------------------------------------------------------------------------
# set folders, the final-test guard and provenance


def prepare_set(set_dir, name, cfg):
    """Mark a set folder with its declared set (development, validation or pilot), outside the repository.
    A frozen folder, or one marked for another set, is refused."""
    s = split_set(cfg, name)
    set_dir = na.outside_repository(set_dir)
    if (set_dir / sna.FROZEN_RECORD).is_file():
        raise ValueError("refused: the set is frozen; nothing is added to it")
    mark = set_dir / SET_MARK
    if mark.is_file():
        old = json.loads(mark.read_text(encoding="utf-8"))
        if old.get("set") != name:
            raise ValueError("refused: the folder is marked for another set")
        return set_dir
    set_dir.mkdir(parents=True, exist_ok=True)
    mark.write_text(json.dumps({"schema": SET_MARK_SCHEMA, "set": name, "purpose": s["purpose"], "synthetic": True},
                               indent=1) + "\n", encoding="utf-8")
    return set_dir


def synthetic_count(set_dir):
    """How many build or item files of a set folder say synthetic, and whether it carries a synthetic mark."""
    set_dir = Path(set_dir)
    n = 0
    for pattern in ("build/*/build.json", "items/*/item.json"):
        for p in set_dir.glob(pattern):
            try:
                if json.loads(p.read_text(encoding="utf-8")).get("synthetic"):
                    n += 1
            except ValueError:
                n += 1
    return n, (set_dir / SET_MARK).is_file()


def refuse_synthetic_in_final(set_dir):
    """The final test's guard (D-707): a final-test folder holding any synthetic build or item, or carrying a
    synthetic set mark, is refused. Role N calls it before the final test's freeze."""
    n, marked = synthetic_count(set_dir)
    if n or marked:
        raise ValueError("refused: the final test holds %d synthetic file(s)%s; synthetic items are never in the "
                         "final test (D-707)" % (n, " and a synthetic set mark" if marked else ""))
    return 0


def check_generator(family, model_id, cfg):
    gen = cfg["generation"]
    fam = str(family or "").strip().lower()
    if fam != gen["generator_family"]:
        raise ValueError("refused: the generator family is declared as %s" % gen["generator_family"])
    mid = str(model_id or "").strip()
    if not mid:
        raise ValueError("refused: the generator's live model id is recorded")
    if any(f in mid.lower() for f in gen["families_never_generator"]):
        raise ValueError("refused: a family the system under test uses never generates")
    if _DATED.search(mid):
        raise ValueError("refused: a dated snapshot id; a bare alias read live is recorded")
    return fam, mid


def provenance_row(card, set_name, prompt_text, reply_bytes, build, *, family, model_id, decoding,
                   regeneration, cfg, generated_at=None):
    fam, mid = check_generator(family, model_id, cfg)
    if type(regeneration) is not int or regeneration < 0:
        raise ValueError("the regeneration count is a whole number")
    return {"schema": PROVENANCE_SCHEMA, "item_id": card["item_id"], "set": set_name, "synthetic": True,
            "seed": card["seed"], "sampler_sha256": card["sampler_sha256"], "card_sha256": _sha(card),
            "brief_sha256": _sha(prompt_text), "reply_sha256": _sha(bytes(reply_bytes)), "build_sha256": _sha(build),
            "generator_family": fam, "generator_model_id": mid, "decoding": decoding if decoding is not None else {},
            "regeneration": regeneration,
            "generated_at": generated_at or time.strftime("%Y-%m-%dT%H:%M:%S%z"), "validator": "passed"}


def write_provenance(set_dir, row):
    """One row appended to the set's PROVENANCE.jsonl, refused when a declared field is missing or empty, or
    when the item already has a row."""
    for f in PROVENANCE_REQUIRED:
        if f not in row or row[f] is None or row[f] == "":
            raise ValueError("refused: a provenance row lacks %s" % f)
    if row["synthetic"] is not True:
        raise ValueError("refused: a synthetic provenance row says synthetic")
    path = Path(set_dir) / PROVENANCE_FILE
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("item_id") == row["item_id"]:
                raise ValueError("refused: the item already has a provenance row")
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return path


def write_item(set_dir, card, build, cfg):
    folder = Path(set_dir) / "build" / card["item_id"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "build.json").write_text(json.dumps(build, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / "SOURCE.md").write_text(cfg["item"]["source_note"] + "\n", encoding="utf-8")
    return folder


# ---------------------------------------------------------------------------
# coverage of a batch


def coverage(cards, cfg):
    """Class counts over a batch's declared keys: fates, conflict, M10 (movable or settled, AM-3) and the red
    lines' outcome (AM-2: held on removed, not held on kept or changed, open apart)."""
    out = {"fate": Counter(), "conflict": Counter(), "m10": Counter(), "red_line_outcome": Counter(),
           "record_kind": Counter(), "structure": Counter(), "items": 0}
    for card in cards:
        out["items"] += 1
        out["record_kind"][card["structure"]["record_kind"]] += 1
        out["structure"][sna.structure_of(card["structure"]["parties"])] += 1
        for p in card["declared_key"]["proposals"].values():
            out["fate"][p["fate"]] += 1
            out["conflict"][p["conflict"]] += 1
            out["m10"][m10_class(cfg, p["fate"])] += 1
            if p["red_line"]:
                out["red_line_outcome"]["held" if p["fate"] in sna.HELD_FATES else
                                        "not_held" if p["fate"] in sna.LET_THROUGH_FATES else "open"] += 1
    return {k: (dict(v) if isinstance(v, Counter) else v) for k, v in out.items()}


EXPECTED_CLASSES = {"fate": sna.FATES, "conflict": na.CONFLICT, "m10": ("movable", "settled"),
                    "red_line_outcome": ("held", "not_held"), "record_kind": sna.RECORD_KINDS}


def set_kind_problems(set_dir, cfg):
    """D-711 on a set folder: every built item records its kind, and the set holds both kinds at the declared
    minimum. Problem codes only."""
    kinds = Counter()
    out = []
    for p in sorted(Path(set_dir).glob("build/*/build.json")):
        kind = json.loads(p.read_text(encoding="utf-8")).get("record_kind")
        if kind not in sna.RECORD_KINDS:
            out.append("record_kind_missing")
        kinds[kind] += 1
    floor = cfg["constraints"]["batch_min_per_class"]["record_kind"]
    out += ["record_kind:" + k for k in sna.RECORD_KINDS if kinds[k] < floor]
    return out


def built_structures(set_dir):
    """{party structure: {record kind: built items}} of a set folder, the structure computed by the scorer from
    each build's declared parties; counts only."""
    out = {}
    for p in sorted(Path(set_dir).glob("build/*/build.json")):
        b = json.loads(p.read_text(encoding="utf-8"))
        try:
            st = sna.structure_of(b.get("parties"))
        except ValueError:
            st = sna.UNDECLARED_STRUCTURE
        kind = b.get("record_kind") if b.get("record_kind") in sna.RECORD_KINDS else sna.UNDECLARED_KIND
        out.setdefault(st, {}).setdefault(kind, 0)
        out[st][kind] += 1
    return out


def coverage_problems(cov, cfg):
    mins = cfg["constraints"]["batch_min_per_class"]
    return ["%s:%s" % (field, c) for field, classes in EXPECTED_CLASSES.items() for c in classes
            if cov[field].get(c, 0) < mins[field]]


# ---------------------------------------------------------------------------
# command line


def _write_json(path, value):
    path = na.outside_repository(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("seed-base")
    p.add_argument("--out", required=True)
    sub.add_parser("check-split")
    p = sub.add_parser("draw")
    p.add_argument("--set", required=True)
    p.add_argument("--seed-base", required=True)
    p.add_argument("--keys")
    p.add_argument("--briefs", required=True)
    p = sub.add_parser("assemble")
    for f in ("--set", "--prompt", "--reply", "--set-dir", "--generator-family", "--model-id"):
        p.add_argument(f, required=True)
    one = p.add_mutually_exclusive_group(required=True)
    one.add_argument("--item")
    one.add_argument("--card")
    p.add_argument("--decoding", default="{}")
    p.add_argument("--regeneration", type=int, default=0)
    p = sub.add_parser("coverage")
    one = p.add_mutually_exclusive_group(required=True)
    one.add_argument("--set")
    one.add_argument("--keys")
    p = sub.add_parser("select")
    p.add_argument("--set", required=True)
    p.add_argument("--keys")
    p.add_argument("--set-dir", required=True)
    p.add_argument("--dropped", nargs="*", default=[])
    p.add_argument("--out", required=True)
    p = sub.add_parser("set-check")
    p.add_argument("--set-dir", required=True)
    p = sub.add_parser("label-sheets")
    p.add_argument("--set-dir", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("label-compare")
    one = p.add_mutually_exclusive_group(required=True)
    one.add_argument("--set")
    one.add_argument("--keys")
    p.add_argument("--labels", required=True)
    p.add_argument("--set-dir", required=True)
    p.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    cfg = load_config()
    if args.cmd == "seed-base":
        out = Path(args.out)
        if out.exists():
            raise SystemExit("refused: a seed base exists; it is drawn once per run")
        _write_json(out, new_seed_base())
        print("seed base written")
        return 0
    if args.cmd == "check-split":
        for s in check_split(cfg):
            print("%-17s %-11s target %3d drawn %3d offset %6d" % (s["name"], s["purpose"], s["target"], s["drawn"],
                                                                  s["offset"])
                  + ("" if "strata" not in s else "  strata %s%s" % (
                      ", ".join("%s %d" % (st, s["strata"][st]) for st in strata_order(s)),
                      ", tops up %s" % s["tops_up"] if "tops_up" in s else ""))
                  + ("  fix %s (%s)" % (s["fix"], s["fix_decision"].split(" (")[0]) if "fix" in s else ""))
        return 0
    if args.cmd == "draw":
        base = _read_json(args.seed_base)
        if base.get("schema") != SEED_BASE_SCHEMA:
            raise SystemExit("refused: not a seed base file")
        version, gen = sampler_sha256(), load_generator(cfg)
        drawn = refused = 0
        keys = _keys_dir(args, cfg, must_exist=False)
        declared = split_set(cfg, args.set)
        for seed in seeds_for(cfg, args.set, base["base"]):
            try:
                card = sample_card(seed, cfg, version=version, stratum=stratum_of(seed, declared))
            except SeedRefused:
                refused += 1
                continue
            card["set"] = args.set
            _write_json(keys / (card["item_id"] + ".card.json"), card)
            out = na.outside_repository(Path(args.briefs) / (card["item_id"] + ".prompt.md"))
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(render_prompt(brief_view(card), gen, cfg), encoding="utf-8")
            drawn += 1
        print("set %s: %d cards drawn, %d seeds refused by the constraints" % (args.set, drawn, refused))
        return 0
    if args.cmd == "assemble":
        source = Path(args.card) if args.card else card_path(cfg, args.set, args.item)
        if not source.is_file():
            raise SystemExit("refused: set %s holds no card of that item (D-716)" % args.set)
        card = _read_json(source)
        if card.get("set") != args.set:
            raise SystemExit("refused: the card was drawn for another set")
        prompt = Path(args.prompt).read_text(encoding="utf-8")
        if prompt != brief_of(card, cfg):
            raise SystemExit("refused: the prompt is not this card's brief")
        reply_bytes = Path(args.reply).read_bytes()
        reply, why = read_reply(reply_bytes)
        if why:
            print("rejected: 1 problem (reply_form:%s)" % why)
            return 2
        problems, build = validate(card, reply, cfg)
        if problems:
            codes = Counter(p.split(":")[0] for p in problems)
            print("rejected: %d problem(s): %s" % (len(problems), ", ".join("%s %d" % kv for kv in sorted(codes.items()))))
            return 2
        set_dir = prepare_set(args.set_dir, args.set, cfg)
        row = provenance_row(card, args.set, prompt, reply_bytes, build, family=args.generator_family,
                             model_id=args.model_id, decoding=json.loads(args.decoding),
                             regeneration=args.regeneration, cfg=cfg)
        write_item(set_dir, card, build, cfg)
        write_provenance(set_dir, row)
        print("accepted: 1 item written with its provenance row")
        return 0
    if args.cmd == "select":
        cards = [_read_json(q) for q in sorted(_keys_dir(args, cfg).glob("*.card.json"))]
        if any(c.get("set") != args.set for c in cards):
            raise SystemExit("refused: a card of another set is in the keys folder")
        dropped = set()
        for f in args.dropped:
            value = _read_json(f)
            dropped |= set(value.get("dropped_ids") or [])
        declared = split_set(cfg, args.set)
        if declared.get("strata"):
            out = select_strata(cards, args.set_dir, declared["strata"], dropped)
        else:
            out = select(cards, args.set_dir, declared["target"], dropped)
        _write_json(Path(args.out), out)
        print(json.dumps({k: out[k] for k in ("target", "built", "dropped", "short", "record_kinds", "structures",
                                              "short_by_structure") if k in out}, sort_keys=True))
        return 2 if out["short"] or len(out["record_kinds"]) < len(sna.RECORD_KINDS) else 0
    if args.cmd == "set-check":
        problems = set_kind_problems(args.set_dir, cfg)
        print("set check: " + (", ".join(problems) if problems else "both record kinds present, each item records its kind"))
        print("built items by party structure and record kind: " + json.dumps(built_structures(args.set_dir),
                                                                               sort_keys=True))
        return 2 if problems else 0
    if args.cmd == "label-sheets":
        sheets = [label_sheet(_read_json(p)) for p in sorted(Path(args.set_dir).glob("build/*/build.json"))]
        _write_json(Path(args.out), {"schema": SHEET_SCHEMA, "sheets": sheets})
        print("label sheets: %d items" % len(sheets))
        return 0
    if args.cmd == "label-compare":
        labels = _read_json(args.labels)
        built = {q.parent.name for q in Path(args.set_dir).glob("build/*/build.json")}
        keys = _keys_dir(args, cfg)
        missing = [i for i in built if not (keys / (i + ".card.json")).is_file()]
        if missing:
            raise SystemExit("refused: %d built item(s) have no card in the card folder" % len(missing))
        cards = [_read_json(keys / (i + ".card.json")) for i in sorted(built)]
        if args.set and any(c.get("set") != args.set for c in cards):
            raise SystemExit("refused: a card of another set is in the card folder")
        out = compare_labels(cards, labels)
        _write_json(Path(args.out), out)
        print(json.dumps({k: out[k] for k in ("items", "kept", "dropped", "mapping", "red_line")}, sort_keys=True))
        return 0
    if args.cmd == "coverage":
        cards = [_read_json(p) for p in sorted(_keys_dir(args, cfg).glob("*.card.json"))]
        if args.set and any(c.get("set") != args.set for c in cards):
            raise SystemExit("refused: a card of another set is in the card folder")
        cov = coverage(cards, cfg)
        problems = coverage_problems(cov, cfg)
        if args.set:
            problems += strata_problems(cov, split_set(cfg, args.set))
        print(json.dumps(cov, sort_keys=True))
        if problems:
            print("below the declared batch minimum: " + ", ".join(problems))
            return 2
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
