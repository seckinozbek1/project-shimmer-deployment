#!/usr/bin/env python3
"""The negotiation advisor's scorer and set tools (D-605, #262; docs/loop/stages/NEG_ADVISOR_PLAN.md).

The role session's tools, which read items and keys in its own folder (never the builder's):

    build            --set S            build/<id>/build.json -> items/<id>/item.json, key.json and SOURCE.md
                                        (the plan's deterministic labels, section 4.1 and 4.2); prints each
                                        item's token count and refuses the set when one is over 24,000
    validate-prompts --set S --out P    one validate prompt per position (the mapping, plan section 4.2)
    validate-read    --set S --prompts P --answers A    mapping_validation.json, kappa over (article, proposal, stance);
                                        refuses answers not of P, not made by Phi-4, or missing a position
    sample           --set S --out F    the checker's 20 percent sheet (at least 8 items), texts and no labels
    sample-read      --set S --sheet F  checker_agreement.json, per-field kappa against the key
    judge-prompts    --set S --b1 A --system A --cloud A --out P     the blind judge's prompts (plan section 6.3)
    grade-sheet      --judge-prompts P --out F          the checker's 25 percent of the judge's entries (at least 10)
    grade-read       --set S --sheet F --judge-answers A    grade_agreement.json, the checker's kappa with the judge
    freeze           --set S --corpora C [--extra D ...] [--no-embedding] [--device cpu|cuda]
                                        also draws cloud_subset.json (D-606) and names its SHA-256
    handback         --set S --out F    counts only
    power            --set S --k K --out F    the power record of claim A1 at opening k's alpha (plan section 7.3)
    score            --set S --configuration C --k K --b1 A --system A --cloud A --judge A [--per-item-out F]

The plan amendments (docs/loop/stages/NEG_PLAN_AMENDMENTS.md): AM-1, a field whose reference gives one class
is at the bar only at 100 percent raw agreement, labelled "single class, kappa undefined" (sample-read,
grade-read, validate-read, bar line 4 and M9); AM-2, red lines reported declared and held (held computed from
the key's fate) with each arm's agreement with held and every red line's source (`red_lines` in the report);
AM-3, M10 open-point detection (movable or settled, from the key's fate and the arm's stance), indicator only,
never a claim and never in the bar (`M10` beside M1 in `figures`, and the report's `M10` block).
The power record's code_sha256 is of this file's LF bytes.

The scorer prints aggregates only, a cell of fewer than 5 items as its count alone; per-item rows go only
to a path inside the role session's set folder, never inside the repository. Every figure
of plan section 6 is computed here, with the BCa cluster bootstrap, the jackknife and the cluster
permutation test of tools/score_negotiation.py. Development, exposed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import neg_advisor as na  # noqa: E402
import answer_form  # noqa: E402
import reread_replies as rr  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sn = _load("score_negotiation", ROOT / "tools" / "score_negotiation.py")

BUILD_SCHEMA = "neg-advisor-build-v1"
KEY_SCHEMA = "neg-advisor-key-v1"
FATES = ("kept", "changed", "removed", "open")
ALIGN = ("aligned", "opposed", "not_stated")
CONFIGURATIONS = ("bilateral", "shifting", "group_vs_group", "one_vs_group", "everyone")
NO_ANSWER = "no_answer"
NGRAM = 5
KEPT_SHARE, CHANGED_SHARE = 0.8, 0.2
SHIFT_JACCARD = 0.5
KAPPA_FLOOR = 0.60
SEED = 20261113
SAMPLE_SHARE, SAMPLE_MIN = 0.20, 8
GRADE_SHARE, GRADE_MIN = 0.25, 10
HEADLINE = ("P",)
MAX_OPENINGS = 2
# D-710 (Seckin 20:27, docs/loop/DECISIONS.md): the one set allowed more openings than MAX_OPENINGS, named by
# its digest: the old 24-item pilot takes a third opening, indicator only, at alpha 0.05 / 2^3 = 0.00625,
# re-reading its saved answers. Every other set keeps MAX_OPENINGS. Declared here alone.
EXTRA_OPENINGS = {"6a8af3c7e3fd7f9ffd5cf1e64809b5d00d129f18162c6f0059e3377a18e3007f": 3}
MIN_POWER_SIMS = 1000
POWER_FLOOR = 0.8
POWER_RECORD = "docs/loop/stages/NEG_ADVISOR_POWER.json"
OPENINGS = "docs/loop/HELDOUT_OPENINGS.md"
_OPENING = re.compile(r"neg-advisor\s+opening\s+k=(\d+)\s+set=([0-9a-f]{64})\s+config=([0-9a-f]{64})")
CHECKS = ("C-cite", "C-reason", "C-closed", "C-mandate", "C-earlier")
CONFIG_FIELDS = ("commit", "b1_prompts_sha256", "system_prompts_sha256", "cloud_prompts_sha256", "cloud_model_id",
                 "judge_prompts_sha256", "validate_prompts_sha256", "cloud_subset_sha256", "checkpoint_digests",
                 "power_record_sha256", "models")
# The groups whose loaded checkpoint digest the configuration binds, and the record that carries it (an
# arm's answers, the judge's answers, or the mapping validation for the validator's pass).
DIGEST_GROUPS = (("B1", "b1"), ("system", "system_advice"), ("system", "system_audit"), ("judge", "judge"),
                 ("validation", "validate"))
# The groups whose loaded model id must be the registry's own model of their agent (the form declares it;
# JUDGE's local.model is null): a Phi-3.5 judge or validator pass is refused, whatever its digests say.
MODEL_BOUND_GROUPS = (("judge", "judge"), ("validation", "validate"))
# The three cloud-subset refusals of score (plan 5.2): the subset bound to the freeze and the
# configuration, the subset the plan's draw from the frozen keys, the cloud answers of its items exactly.
SUBSET_REFUSALS = ("bound", "drawn", "answered")
# What validate-read refuses (plan 4.2): answers of another prompts file, made by another model than the
# registry's JUDGE model, or missing a position of the build files.
VALIDATION_REQUIRES = ("prompts", "model", "every_position")
# Plan section 5.2 (D-606): the cloud reference's subset, drawn by the scorer from the frozen set.
CLOUD_SUBSET_SIZE = 20
CLOUD_TAG = "20261113-negadv-cloud"
SUBSET_FILE = "cloud_subset.json"
MIN_PART_PLACES = 1
# Plan section 6: a reporting cell of fewer items gives its count alone, no figure and no interval.
MIN_CELL = 5
# Plan section 6.2: the modes in which a check never reads the key (the system's withholding).
KEYLESS_MODES = ("system",)
# Plan section 7.1 line 1: the bar's margin over B1 on M1, with the interval's lower bound above zero.
BAR_MARGIN = 0.10
# What the system's withholding drops on (plan section 5, item 2).
WITHHELD_AUDIT = "unsupported"
SAMPLE_FIELDS = ("fate", "state", "conflict", "alignment", "red_line")
# AM-1 (D-662, docs/loop/stages/NEG_PLAN_AMENDMENTS.md): on a field where the reference (the key, or the
# checker against the judge) gives one class only, kappa is undefined; the raw agreement is reported and the
# field is at the bar only at 100 percent, labelled so. Bar line 4 and M9's validation alike.
SINGLE_CLASS_FULL = 1.0
SINGLE_CLASS_LABEL = "single class, kappa undefined"
# AM-2 (D-665, D-693): a declared red line held when its proposal was removed from the next round's text, not
# held when it passed (kept or changed), and open, its own count, when it is still bracketed; from the fate.
# The "no recorded objection" clause cannot fire: check_build refuses positions after round k.
HELD_FATES = ("removed",)
LET_THROUGH_FATES = ("kept", "changed")
OPEN_FATES = ("open",)
# The stances by which an arm's advice holds a red line (rejects or counters the proposal).
HOLDING_STANCES = ("reject", "counter")
# The stances an arm's piece can give; a piece with none is counted no_stance and is a disagreement (order 82).
ANSWERED_STANCES = tuple(na.STANCES)
# AM-3: M10, open-point detection, indicator only (never a claim, never in the bar). The key's class per
# proposal from its fate, the arm's prediction from its stance; no stance is a miss counted by its reason.
MOVABLE, SETTLED = "movable", "settled"
M10_CLASSES = (MOVABLE, SETTLED)
MOVABLE_FATES = ("open", "changed")
SETTLED_FATES = ("kept", "removed")
MOVABLE_STANCES = ("counter",)
SETTLED_STANCES = ("accept", "reject")
M10_MISSES = ("no_reply", "withheld", "no_piece", "no_stance", "stance_not_declared")
M10_STATUS = "indicator only (AM-3): never a claim, never in the bar"
# D-711 items 2 and 3 (Seckin 20:40): every item's record is complete or has a party's notes missing (a
# masked-party item among them); every bar figure is reported per kind, and a bar reading needs both kinds and
# no item of undeclared kind. The bar's lines are NEG_BAR.md's (D-709, floor 0.60 at 20:25), read per kind.
COMPLETE, MISSING_NOTES = "complete", "missing_notes"
RECORD_KINDS = (COMPLETE, MISSING_NOTES)
UNDECLARED_KIND = "undeclared"
# A set whose freeze is recorded is never built again: its keys are read as they are (D-693).
FROZEN_RECORD = "FREEZE.json"
# D-664: every red line carries its source; for now only the document (v1.1 adds the operator's). Declared once,
# in the advisor's code (benchmark/baselines/neg_advisor.py), which stores it on the item's persona too.
RED_LINE_SOURCES = na.RED_LINE_SOURCES
# D-711: every item records whether every party's notes are on record (complete) or one party's are not
# (missing_notes, whose key answer for that party is not_stated). Required on a synthetic build; a real build
# without it reads as not recorded until role N records it.
RECORD_KIND_UNSET = "not_recorded"
# D-706 item 3 and D-707: real items alone are the headline; synthetic items are reported apart, never pooled.
SYNTHETIC_ROW = ("synthetic items, reported apart from the real items and never pooled with them; their answers "
                 "come from their construction (D-706 item 3, D-707)")
# The operator's party-structure instruction (Seckin 16 November 2026 20:32, NEG_BAR.md): every item's structure,
# computed from its declared parties alone, never read from words: two single parties, two teams (coalitions),
# one party against a coalition, three or more parties. Every bar figure and floor is reported per structure,
# and a bar reading is refused for a set whose headline items hold one structure only.
TWO_SINGLES, TEAMS, ONE_VS_COALITION, THREE_OR_MORE = "two_singles", "teams", "one_vs_coalition", "three_or_more"
STRUCTURES = (TWO_SINGLES, TEAMS, ONE_VS_COALITION, THREE_OR_MORE)
MIN_STRUCTURES = 2
# D-715 item 1 (Seckin 22:31): the bar passes only when every structure the set holds meets every line and floor,
# and overall does too. The fewest headline items a structure needs in a set: a reporting cell of fewer than
# MIN_CELL items gives its count alone, with no figure and no interval (plan section 6), so a structure with
# fewer items could never meet a line, and a pass on it could not be read at all. Declared here alone.
MIN_ITEMS_PER_STRUCTURE = MIN_CELL
# What the pass is read on: each record kind (D-711), each structure the set holds and overall (D-715 item 1).
BAR_READ_ON = ("kinds", "structures", "overall")
UNDECLARED_STRUCTURE = "not_computed"
OVERALL = "overall"
PARTY_KINDS = ("single", "coalition")
# D-668 gap 6: a coalition declares at least this many members when it declares any.
MIN_MEMBERS = 2
# The scorer's code digest is of its LF bytes, so a CRLF checkout names the committed code (#262 gap 2).
CODE_EOL = (b"\r\n", b"\n")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def outside_repository(path):
    """Refuse a path inside the repository: per-item rows and the set never live there (plan section 9).
    One rule with the forms' (neg_advisor.outside_repository), the root read at call time."""
    p = Path(path).resolve()
    try:
        p.relative_to(Path(ROOT).resolve())
    except ValueError:
        return p
    raise ValueError("refused: a per-item file or the set may not be written inside the repository")


def inside_set(path, set_dir):
    """The per-item rows' path: inside the role session's own set folder and outside the repository."""
    p = outside_repository(path)
    try:
        p.relative_to(Path(set_dir).resolve())
    except ValueError:
        raise ValueError("refused: per-item rows are written only inside the role session's set folder") from None
    return p


# ---------------------------------------------------------------------------
# section 4.1: text, by deterministic rules


_BRACKET_MARK = re.compile(r"\b(alt(ernative)?|option)\s*\d*\s*[:.]?", re.I)


def norm_text(text):
    """Brackets and option markers removed, case folded, curly quotes straight, whitespace one space."""
    text = str(text or "").replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    text = text.replace("[", " ").replace("]", " ")
    text = _BRACKET_MARK.sub(" ", text)
    return " ".join(text.lower().split())


def grams(text):
    words = norm_text(text).split()
    return {tuple(words[i:i + NGRAM]) for i in range(len(words) - NGRAM + 1)}


def jaccard5(a, b):
    ga, gb = grams(a), grams(b)
    return len(ga & gb) / len(ga | gb) if ga | gb else 0.0


def bracket_spans(text):
    """The top-level [...] spans of a text, their inner text (nested brackets kept inside)."""
    out, depth, start = [], 0, None
    for i, ch in enumerate(str(text or "")):
        if ch == "[":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == "]" and depth:
            depth -= 1
            if depth == 0:
                out.append(text[start:i])
    return out


# #281 gap 8 (D-666, D-667): an unagreed article with no bracket span but numbered option markers (an option or
# alternative label with its number, at a line's start or followed by a colon or a closing parenthesis) holds
# several proposals the brackets do not mark. Its text is never split by guess: the build is refused with the
# article named, and the builder brackets each proposal. Structure only (WORDS-A): the label is the one
# _BRACKET_MARK already strips, and its number is what is counted. Other languages' labels: #281's D-668 list.
_NUMBERED_OPTION = re.compile(r"^[ \t]*(?:alt(?:ernative)?|option)[ \t]*(\d+)\b"
                              r"|\b(?:alt(?:ernative)?|option)[ \t]*(\d+)[ \t]*[:)]", re.I | re.M)
UNBRACKETED_OPTIONS_MIN = 2


def unbracketed_options(article):
    """The distinct numbers of an unagreed article's option markers when it holds no bracket span (else [])."""
    text = str(article.get("text") or "")
    if article.get("agreed") or any(s.strip() for s in bracket_spans(text)):
        return []
    return sorted({int(a or b) for a, b in _NUMBERED_OPTION.findall(text)})


def refuse_unbracketed_options(item_id, article):
    """Refuse visibly an article read as one proposal although it numbers several options (#281 gap 8)."""
    numbers = unbracketed_options(article)
    if len(numbers) >= UNBRACKETED_OPTIONS_MIN:
        raise ValueError("refused: %s: article %s numbers %d options (%s) and holds no bracket; it would be read as "
                         "one proposal, so each proposal is bracketed in the build file, never split by guess"
                         % (item_id, article.get("id"), len(numbers), ", ".join(str(n) for n in numbers)))


def split_article(article):
    """(paragraphs, proposals) of a build article: paragraphs at blank lines, PAR-<n> numbered across the
    item by the caller; proposals one per top-level bracket span, or the whole text when it holds none and
    is not agreed; an agreed article holds none."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", article["text"]) if p.strip()]
    if article.get("agreed"):
        props = []
    else:
        spans = [s.strip() for s in bracket_spans(article["text"]) if s.strip()]
        props = spans or [article["text"].strip()]
    return paras, props


def _share(proposal, target):
    g = grams(proposal)
    if not g:
        return None
    tg = grams(target)
    return len(g & tg) / len(g)


def fate(proposal, next_text):
    """The plan's fate: open, kept, changed or removed."""
    if next_text is None:
        return "removed"
    short = len(norm_text(proposal).split()) < NGRAM
    for span in bracket_spans(next_text):
        if (norm_text(proposal) in norm_text(span)) if short else ((_share(proposal, span) or 0) >= KEPT_SHARE):
            return "open"
    if short:
        return "kept" if norm_text(proposal) in norm_text(next_text) else "removed"
    s = _share(proposal, next_text) or 0.0
    return "kept" if s >= KEPT_SHARE else ("changed" if s >= CHANGED_SHARE else "removed")


# ---------------------------------------------------------------------------
# section 4.2: from the positions on record


def applicable(positions, party, article, number):
    """A party's positions on one proposal (its 1-based bracket number): the proposal-specific ones when it
    has any, else its article-level ones."""
    mine = [p for p in positions if p["party"] == party and p["article"] == article]
    specific = [p for p in mine if p.get("proposal") == number]
    return specific if specific else [p for p in mine if p.get("proposal") is None]


def _sign(stances):
    s = {1 if x in ("support", "accept") else -1 for x in stances}
    return s.pop() if len(s) == 1 else 0


def conflict_label(positions, persona, article, number):
    mine = applicable(positions, persona, article, number)
    if any(p["stance"] == "oppose" for p in mine):
        return "conflict"
    return "no_conflict" if mine else "not_stated"


def alignment_label(positions, persona, party, article, numbers):
    """aligned, opposed or not_stated, compared proposal by proposal (the article itself when it holds none)."""
    common = []
    for n in numbers or [None]:
        a = _sign([p["stance"] for p in applicable(positions, persona, article, n)])
        b = _sign([p["stance"] for p in applicable(positions, party, article, n)])
        if a and b:
            common.append(a == b)
    if not common:
        return "not_stated"
    return "aligned" if all(common) else "opposed"


def state_label(article_id, k, previous_ids, agreed, has_proposals, positions, persona):
    if any(p["party"] == persona and p["article"] == article_id and p["stance"] == "accept" and p["round"] < k
           for p in positions):
        return "binding"
    if k > 1 and article_id not in previous_ids:
        return "new"
    return "bracketed" if has_proposals and not agreed else "closed"


def configuration(item, key):
    """The plan's section 3.2, first that holds."""
    parties = item["parties"]
    if len(parties) == 2:
        return "bilateral"
    if len(parties) >= 3:
        sets = [frozenset(p for p, lab in cells.items() if lab == "aligned") for cells in key["alignment"].values()]
        sets = [s for s in sets if s]
        for i in range(len(sets)):
            for j in range(i + 1, len(sets)):
                if len(sets[i] & sets[j]) / len(sets[i] | sets[j]) < SHIFT_JACCARD:
                    return "shifting"
    persona = item["persona"]
    others = [p for p in parties if p["id"] != persona["id"]]
    if persona["kind"] == "coalition" and any(p["kind"] == "coalition" for p in others):
        return "group_vs_group"
    if persona["kind"] == "single" and any(p["kind"] == "coalition" for p in others):
        return "one_vs_group"
    return "everyone"


def structure_of(parties):
    """The item's party structure (the operator's 20:32 instruction), from its declared parties and their kinds
    alone: three or more parties; else two singles, two coalitions (teams), or one single against a coalition."""
    parties = list(parties or [])
    if len(parties) < 2:
        raise ValueError("an item names at least two parties")
    if len(parties) >= 3:
        return THREE_OR_MORE
    kinds = sorted(p.get("kind") for p in parties)
    if kinds == ["single", "single"]:
        return TWO_SINGLES
    if kinds == ["coalition", "coalition"]:
        return TEAMS
    if kinds == ["coalition", "single"]:
        return ONE_VS_COALITION
    raise ValueError("a party is single or coalition")


def check_parties(b):
    """D-668 gap 6 and the structure tag: each party single or coalition, a coalition's declared members (at least
    MIN_MEMBERS, never itself, each once), a position stated on behalf of a coalition only by one of its declared
    members, and a declared `structure` the one Python computes."""
    item_id = b.get("item_id")
    parties = b.get("parties") or []
    ids = [p.get("id") for p in parties]
    if len(set(ids)) != len(ids):
        raise ValueError("%s: a party is named twice" % item_id)
    for p in parties:
        if p.get("kind") not in PARTY_KINDS:
            raise ValueError("%s: a party is single or coalition" % item_id)
        members = p.get("members")
        if members is None:
            continue
        if p["kind"] != "coalition" or not isinstance(members, list) or len(members) < MIN_MEMBERS:
            raise ValueError("%s: only a coalition declares members, at least %d" % (item_id, MIN_MEMBERS))
        if p["id"] in members or len(set(members)) != len(members) or not all(isinstance(m, str) and m for m in members):
            raise ValueError("%s: a coalition's members are other parties, each once" % item_id)
    if b["persona"].get("id") not in ids:
        raise ValueError("%s: the persona is one of the item's parties" % item_id)
    by_id = {p["id"]: p for p in parties}
    if b["persona"].get("kind") != by_id[b["persona"]["id"]].get("kind"):
        raise ValueError("%s: the persona's kind is its party's kind" % item_id)
    for pos in b.get("positions") or []:
        whole = pos.get("on_behalf_of")
        if whole is None:
            continue
        if pos.get("party") not in ((by_id.get(whole) or {}).get("members") or []):
            raise ValueError("%s: a position on behalf of a coalition is stated by one of its declared members"
                             % item_id)
    declared = b.get("structure")
    if declared is not None and declared != structure_of(parties):
        raise ValueError("%s: the declared structure is not the one its parties give (%s)"
                         % (item_id, structure_of(parties)))


def check_layers(b):
    """D-666: each document layer entry of a build declares its kind, its text, and an article of the excerpt or
    none; the record's layers not read are names."""
    arts = {a.get("id") for a in b.get("articles") or []}
    for e in b.get("layers") or []:
        if not isinstance(e, dict) or e.get("layer") not in na.LAYER_KINDS:
            raise ValueError("%s: a layer entry's kind is one of %s" % (b.get("item_id"), ", ".join(na.LAYER_KINDS)))
        if not isinstance(e.get("text"), str) or not e["text"].strip():
            raise ValueError("%s: a layer entry carries its text" % b.get("item_id"))
        if e.get("article") is not None and e["article"] not in arts:
            raise ValueError("%s: a layer entry's article is one of the excerpt's, or none" % b.get("item_id"))
    if not all(isinstance(x, str) and x for x in b.get("layers_not_read") or []):
        raise ValueError("%s: the layers not read are named" % b.get("item_id"))


def credited(positions, parties):
    """The positions with each one a member stated on behalf of its coalition credited to the coalition, the
    member kept as `speaker` (D-668 gap 6); a member's own position stays its own."""
    out = []
    for p in positions:
        if p.get("on_behalf_of") is not None:
            p = dict(p, party=p["on_behalf_of"], speaker=p["party"])
        out.append(p)
    return out


REQUIRED_BUILD = ("item_id", "part", "process", "round", "persona", "parties", na.TERMS_FIELD, na.ATTRIBUTION_FIELD)


def check_build(b):
    for f in REQUIRED_BUILD:
        if f not in b:
            raise ValueError("a build file lacks %s" % f)
    for f in (na.TERMS_FIELD, na.ATTRIBUTION_FIELD):
        if f in REQUIRED_BUILD and (not isinstance(b[f], str) or not b[f].strip()):
            raise ValueError("%s: a build file states its %s in words" % (b.get("item_id"), f))
    if b.get("schema") != BUILD_SCHEMA or not _ID.match(str(b["item_id"])) or b["part"] not in ("P", "H", "G"):
        raise ValueError("a build file has no valid schema, id or part")
    if type(b["round"]) is not int or not 1 <= b["round"] <= 5:
        raise ValueError("%s: the round is 1 to 5" % b["item_id"])
    if b["persona"].get("kind") not in ("single", "coalition"):
        raise ValueError("%s: the persona is single or coalition" % b["item_id"])
    if b.get("synthetic") and b.get("record_kind") is None:
        raise ValueError("%s: a synthetic build records its record kind (D-711)" % b["item_id"])
    check_parties(b)
    check_layers(b)
    na.read_red_lines(b.get("red_lines"))
    for p in b.get("positions") or []:
        if p.get("stance") not in na.POSITION_STANCES or not str(p.get("id", "")).startswith("POS-"):
            raise ValueError("%s: a position needs a POS- id and a declared stance" % b["item_id"])
        if type(p.get("round")) is not int or p["round"] > b["round"]:
            raise ValueError("%s: a position lies after round k" % b["item_id"])
    if b["part"] == "G":
        g = b.get("game") or {}
        for f in ("issues", "tables", "thresholds", "required", "veto", "last_deal"):
            if f not in g:
                raise ValueError("%s: a game lacks %s" % (b["item_id"], f))
    elif not 3 <= len(b.get("articles") or []) <= 6:
        raise ValueError("%s: an excerpt holds 3 to 6 articles" % b["item_id"])
    # D-711 items 2 and 3: the record's kind, and the party a masked-party item hides (always missing notes).
    kind = b.get("record_kind")
    if kind is not None and kind not in RECORD_KINDS:
        raise ValueError("%s: record_kind is one of %s" % (b["item_id"], ", ".join(RECORD_KINDS)))
    if b.get("masked_party") is not None:
        if kind != MISSING_NOTES or b["masked_party"] not in {p.get("id") for p in b.get("parties") or []}:
            raise ValueError("%s: a masked party is one of the item's parties, on a missing_notes item"
                             % b["item_id"])


def build_item(b):
    """(item, key) of one build file, by the plan's rules."""
    check_build(b)
    persona = b["persona"]["id"]
    red_ids, red_sources = na.read_red_lines(b.get("red_lines"))
    common = {"item_id": b["item_id"], "part": b["part"], "process": b["process"], "round": b["round"],
              "synthetic": bool(b.get("synthetic")), "post_cutoff": bool(b.get("post_cutoff"))}
    if b.get("record_kind") is not None:
        # D-711: declared by the set builder; never rendered into a prompt (render_advice reads named fields).
        # Left out when undeclared, so record_kind() reads it as undeclared and the bar reading refuses it.
        common["record_kind"] = b["record_kind"]
    if b.get("missing_parties"):
        common["missing_parties"] = sorted(b["missing_parties"])
    item = dict(common, schema=na.ITEM_SCHEMA,
                **{f: str(b.get(f) or "").strip() for f in (na.TERMS_FIELD, na.ATTRIBUTION_FIELD)},
                persona={"id": persona, "kind": b["persona"]["kind"], "red_lines": red_ids,
                         # D-664 item 2: every red line with its source, in the advisor's item too.
                         "red_line_sources": red_sources},
                parties=[dict({"id": p["id"], "kind": p["kind"]}, **({"members": list(p["members"])} if p.get("members")
                                                                    else {})) for p in b["parties"]])
    # The operator's 20:32 party structure, computed from the declared parties (never rendered into a prompt).
    key = dict(common, schema=KEY_SCHEMA, persona_kind=b["persona"]["kind"], structure=structure_of(b["parties"]))
    if b.get("masked_party") is not None:
        key["masked_party"] = b["masked_party"]
    if b["part"] == "G":
        g = b["game"]
        item.update(game={"issues": g["issues"], "persona_table": g["tables"][persona],
                          "persona_threshold": g["thresholds"][persona]},
                    articles=[], positions=[], round_index=[], previous_index=[], trades_on_record=[])
        key.update(game=g, proposals={}, articles={}, alignment={}, approach_targets=[])
        return item, key
    # D-668 gap 6: a member's position stated on behalf of its coalition is the coalition's.
    positions = credited(b.get("positions") or [], b["parties"])
    k = b["round"]
    previous_ids = {r["id"] for r in b.get("previous_index") or []}
    round_ids = {r["id"] for r in b.get("round_index") or []} | {a["id"] for a in b["articles"]}
    renumber = b.get("renumbering") or {}
    arts, kprops, karts, align = [], {}, {}, {}
    par = 0
    for a in b["articles"]:
        refuse_unbracketed_options(b["item_id"], a)
        paras, props = split_article(a)
        pars = []
        for t in paras:
            par += 1
            pars.append({"id": "PAR-%d" % par, "text": t})
        plist = [{"id": "P-%s-%d" % (a["id"], i + 1), "text": t} for i, t in enumerate(props)]
        arts.append({"id": a["id"], "title": a["title"], "agreed": bool(a.get("agreed")), "paragraphs": pars,
                     "proposals": plist})
        nxt = (b.get("next_articles") or {}).get(renumber.get(a["id"], a["id"]))
        karts[a["id"]] = {"state": state_label(a["id"], k, previous_ids, a.get("agreed"), bool(plist), positions,
                                               persona), "next_text": nxt}
        for i, pr in enumerate(plist):
            mine = applicable(positions, persona, a["id"], i + 1)
            lab = conflict_label(positions, persona, a["id"], i + 1)
            f = fate(pr["text"], nxt)
            supports = lab == "no_conflict"
            adv = (("advanced" if f == "kept" else "not_advanced" if f == "removed" else None) if supports else
                   ("advanced" if f == "removed" else "not_advanced" if f == "kept" else None) if lab == "conflict"
                   else None)
            lines = [p["id"] for p in mine if p["id"] in red_sources and p["stance"] == "oppose"]
            red_line = lab == "conflict" and bool(lines)
            kprops[pr["id"]] = {
                "article": a["id"], "conflict": lab, "fate": f, "advanced": adv, "red_line": red_line,
                # D-664: the source of the red line it rests on (each declared one is from the document for now).
                "red_line_source": red_sources[lines[0]] if red_line else None,
                "supported_earlier": any(p["stance"] in ("support", "accept") and p["round"] < k for p in mine)}
        numbers = list(range(1, len(plist) + 1))
        align[a["id"]] = {p["id"]: alignment_label(positions, persona, p["id"], a["id"], numbers)
                          for p in b["parties"] if p["id"] != persona}
    for aid in sorted(previous_ids - round_ids):
        karts[aid] = {"state": "dropped", "next_text": None}
    targets = sorted(p for p in {q for cells in align.values() for q in cells}
                     if any(c.get(p) == "aligned" for c in align.values())
                     and not any(c.get(p) == "opposed" for c in align.values()))
    item.update(articles=arts, round_index=b.get("round_index") or [], previous_index=b.get("previous_index") or [],
                positions=[dict({f: p.get(f) for f in ("id", "party", "round", "article", "proposal", "quote", "source")},
                                **({"speaker": p["speaker"]} if p.get("speaker") else {})) for p in positions],
                trades_on_record=[{"id": t["id"], "give": "P-%s-%d" % (t["give"][0], t["give"][1]),
                                   "get": "P-%s-%d" % (t["get"][0], t["get"][1]), "round": t["round"]}
                                  for t in b.get("trades_on_record") or []])
    if b.get("layers") is not None or b.get("layers_not_read"):
        # D-666: the document's own layers, each apart with its kind, author and anchor, each with a citable id.
        item["layers"] = [dict({"id": na.LAYER_ID % (n + 1), "layer": e["layer"], "text": " ".join(e["text"].split()),
                                "author": str(e.get("author") or ""), "article": e.get("article")},
                               **({"anchor": " ".join(str(e["anchor"]).split())} if e.get("anchor") else {}))
                          for n, e in enumerate(b.get("layers") or [])]
        item["layers_not_read"] = list(b.get("layers_not_read") or [])
    key.update(proposals=kprops, articles=karts, alignment=align, approach_targets=targets)
    key["configuration"] = configuration(item, key)
    # D-668 gap 4: every other party's movement toward or away from the persona, from the positions on record.
    key["movement"] = na.movement_map(item, positions)
    return item, key


def build_set(set_dir, *, count=None, limit=None):
    """Every build file to its item, key and SOURCE.md, after every item's whole advice prompt is counted by
    the B1 model's tokenizer (`count`, default neg_advisor.token_counter): one over the limit (plan section
    3.1, 24,000) refuses the whole set before anything is written."""
    set_dir = outside_repository(set_dir)
    if (set_dir / FROZEN_RECORD).is_file():
        # A frozen set (the pilot among them) is read as it is: a rebuild would rewrite its keys (new fields
        # such as red_line_source) and change the set_sha256 its freeze, power record and openings name.
        raise ValueError("refused: the set is frozen (%s is recorded); its keys are read as they are, never "
                         "built again" % FROZEN_RECORD)
    limit = na.TOKEN_LIMIT if limit is None else limit
    config = na.load_config(na.CONFIG_PATH)
    built = []
    for path in sorted((set_dir / "build").glob("*/build.json")):
        item, key = build_item(_read(path))
        if item["item_id"] != path.parent.name:
            raise ValueError("a build file's id is not its folder's name")
        if not (path.parent / "SOURCE.md").is_file():
            raise ValueError("%s: a build folder holds its SOURCE.md" % item["item_id"])
        built.append((item, key, (path.parent / "SOURCE.md").read_bytes()))
    if not built:
        raise ValueError("no build files under build/")
    count = count or na.token_counter()
    tokens = {item["item_id"]: int(count(na.render_advice(config, item))) for item, _k, _s in built}
    over = sorted(i for i, t in tokens.items() if t > limit)
    if over:
        raise ValueError("refused: %d item(s) over the %d-token budget: %s" % (len(over), limit, ", ".join(over)))
    for item, key, source in built:
        _write_json(set_dir / "items" / item["item_id"] / "item.json", item)
        _write_json(set_dir / "items" / item["item_id"] / "key.json", key)
        (set_dir / "items" / item["item_id"] / "SOURCE.md").write_bytes(source)
    return {"items": len(built), "tokens": tokens, "max_tokens": max(tokens.values()), "limit": limit, "over": 0}


def read_keys(set_dir):
    keys = {}
    for path in sorted((Path(set_dir) / "items").glob("*/key.json")):
        key = _read(path)
        if key.get("schema") != KEY_SCHEMA:
            raise ValueError("not an advisor key: %s" % path.parent.name)
        keys[key["item_id"]] = key
    return keys


# ---------------------------------------------------------------------------
# section 6.2: Python's checks


def checks(item, key, reply, *, mode):
    """{proposal id: {check: True/False}} of one reply. mode `key` reads the key (scoring); mode `system`
    never does: it reads the reply's own state and conflict and the item's red lines, and C-earlier does not
    run there (plan section 6.2)."""
    if reply is None or item.get("game"):
        return {}
    pars, poss, props, arts = na.item_ids(item)
    article_of = {p["id"]: a["id"] for a in item["articles"] for p in a["proposals"]}
    number_of = {p["id"]: i + 1 for a in item["articles"] for i, p in enumerate(a["proposals"])}
    red = set(item["persona"].get("red_lines") or [])
    given = {t["give"] for t in reply["trades"]}
    later = {p["id"] for p in item["positions"] if p["party"] == item["persona"]["id"] and p["round"] == item["round"]}
    out = {}
    for pid, piece in reply["proposals"].items():
        if piece.get("written_by") == PYTHON:
            # A piece Python wrote (system_python: a conflict the positions on record decide, no stance and
            # no reasons) is no advice to check: it would pass every check by having nothing to check.
            continue
        stance, reasons = piece.get("stance"), piece.get("reasons") or []
        aid = article_of[pid]
        r = {"C-cite": all(x in pars | poss for x in reasons),
             "C-reason": stance not in ("reject", "counter") or (bool(reasons) and (stance != "counter" or bool(piece.get("wording"))))}
        if mode not in KEYLESS_MODES:
            state = key["articles"][aid]["state"]
            red_conflict = key["proposals"][pid]["red_line"]
            r["C-earlier"] = not (stance == "reject" and key["proposals"][pid]["supported_earlier"]
                                  and not any(x in later for x in reasons))
        else:
            state = reply["state"].get(aid)
            mine = applicable(item["positions"], item["persona"]["id"], aid, number_of[pid])
            red_conflict = piece.get("conflict") == "conflict" and any(p["id"] in red for p in mine)
        r["C-closed"] = not (stance in ("reject", "counter") and state in ("closed", "binding"))
        r["C-mandate"] = not (stance == "accept" and red_conflict and pid not in given)
        out[pid] = r
    return out


def trade_checks(item, reply):
    """(valid trades, trades given, trades on record carried, trades on record)."""
    if reply is None or item.get("game"):
        return 0, 0, 0, 0
    _, _, props, _ = na.item_ids(item)
    valid = sum(1 for t in reply["trades"] if t["give"] in props and t["get"] in props and t["give"] != t["get"])
    cited = {x for e in reply["proposals"].values() for x in e.get("reasons") or []}
    offered = {(t["give"], t["get"]) for t in reply["trades"]}
    on_record = item.get("trades_on_record") or []
    carried = sum(1 for t in on_record if (t["give"], t["get"]) in offered or t["id"] in cited)
    return valid, len(reply["trades"]), carried, len(on_record)


def withhold(item, reply, audit):
    """The system's kept reply: a piece the audit calls unsupported, or a system-mode check refuses, is
    withheld (it scores no_answer); its trail is returned beside it."""
    if reply is None:
        return None, {"given": 0, "audit_unsupported": 0, "audit_missing": 0, **{c: 0 for c in CHECKS}}
    if item.get("game"):
        # A game reply holds a deal and trades, never proposals: nothing to withhold (session 18, 15 Nov).
        return reply, {"given": 0, "audit_unsupported": 0, "audit_missing": 0, **{c: 0 for c in CHECKS}}
    trail = {"given": sum(1 for e in reply["proposals"].values() if e.get("written_by") != PYTHON),
             "audit_unsupported": 0, "audit_missing": 0, **{c: 0 for c in CHECKS}}
    results = checks(item, None, reply, mode="system")
    kept = {}
    python_kept = 0
    for pid, piece in reply["proposals"].items():
        if piece.get("written_by") == PYTHON:
            # Python's own piece was never the model's advice: no audit asked it and no check reads it.
            kept[pid] = piece
            python_kept += 1
            continue
        said = (audit or {}).get(pid)
        failed = [c for c, ok in results[pid].items() if not ok]
        if said == WITHHELD_AUDIT:
            trail["audit_unsupported"] += 1
        elif said is None:
            trail["audit_missing"] += 1
        for c in failed:
            trail[c] += 1
        if said != WITHHELD_AUDIT and not failed:
            kept[pid] = piece
    out = dict(reply, proposals=kept)
    trail["kept"] = len(kept) - python_kept
    return out, trail


# ---------------------------------------------------------------------------
# the system's Python step (lane neg-round1, standing order 102, D-707): where the item's own positions on
# record decide a field by the plan's declared rules (section 4.2, the same functions the key is built with:
# `applicable`, `state_label`'s order, the previous and round indexes), Python sets it and the model's answer
# is kept beside it; where they prove a model answer impossible, the answer is refused and kept beside it
# (HONEST-OUTPUT-A). It never reads the key and decides nothing that needs a stance's meaning (WORDS-A):
# whether a quote supports, opposes or accepts is left to the model. Positions after round k are refused by
# check_build, so every position the item holds is on record before the advice.

PYTHON = "python"
SYSTEM_PYTHON_COUNTS = ("conflict_filled", "conflict_set", "conflict_agreed", "conflict_refused",
                        "state_filled", "state_set", "state_agreed", "state_refused", "state_left",
                        "alignment_refused",
                        # D-711 item 1, never invent: what each model entry says it rests on, apart.
                        "on_record", "inferred_kept", "inferred_refused", "inferred_set_aside",
                        "on_record_without_position", "alignment_inferred_kept", "alignment_inferred_refused",
                        "alignment_inferred_set_aside")
INFERRED_REFUSALS = ("no_line", "line_too_short", "line_not_found")


def _collapsed(text):
    return " ".join(str(text or "").split())


def item_texts(item):
    """Every text the advice prompt shows (article titles, paragraphs, proposals, every party's position
    quotes), each with its whitespace collapsed: what an inferred entry's line must be copied from."""
    texts = [p.get("quote") for p in item.get("positions") or []]
    for a in item.get("articles") or []:
        texts.append(a.get("title"))
        texts += [x["text"] for x in a.get("paragraphs") or []] + [x["text"] for x in a.get("proposals") or []]
    # D-666: the document's layers the prompt shows (a comment, a tracked change, a note) are its text too.
    texts += [e.get(f) for e in item.get("layers") or [] for f in ("text", "anchor")]
    return [_collapsed(x) for x in texts if x]


def basis_refusal(item, quote):
    """None when an inferred entry's line stands in the item's text as written (whitespace collapsed, case
    kept: the same reading as POSITION-GAPS-A's identical quotes) and holds at least BASIS_QUOTE_MIN_WORDS
    words; else the reason it is refused: no_line, line_too_short or line_not_found."""
    line = _collapsed(quote)
    if not line:
        return "no_line"
    if len(line.split()) < na.BASIS_QUOTE_MIN_WORDS:
        return "line_too_short"
    return None if any(line in text for text in item_texts(item)) else "line_not_found"


def _numbers(article):
    return list(range(1, len(article["proposals"]) + 1))


def structural_state(item, article):
    """The article's state by the plan's rule with `binding` set aside: new (k > 1 and not in the previous
    round's index), bracketed (proposals on the table, not agreed) or closed. `binding` needs the stance of the
    persona's earlier positions, so it is only ever left possible (`binding_possible`), never decided here."""
    previous = {r["id"] for r in item.get("previous_index") or []}
    if item["round"] > 1 and article["id"] not in previous:
        return "new"
    return "bracketed" if article["proposals"] and not article.get("agreed") else "closed"


def binding_possible(item, article_id):
    """True when the persona holds a position on the article from an earlier round (the only positions
    `state_label` reads for `binding`); False proves the state is not binding."""
    persona = item["persona"]["id"]
    return any(p["party"] == persona and p["article"] == article_id and p["round"] < item["round"]
               for p in item.get("positions") or [])


def dropped_articles(item):
    """The previous round's articles no longer in this round (its index or its excerpt): dropped, by
    construction of the round texts."""
    previous = {r["id"] for r in item.get("previous_index") or []}
    now = {r["id"] for r in item.get("round_index") or []} | {a["id"] for a in item.get("articles") or []}
    return sorted(previous - now)


def system_python(item, reply):
    """(reply, counts): the system's advice with the fields its positions on record decide set by Python.

    - conflict: a proposal with no applicable persona position (the plan's `applicable`: proposal-specific
      positions, else article-level ones) is not_stated by the plan's own definition; a missing piece is
      added as Python's (`written_by` python, conflict alone), a model answer set to it is kept in
      `conflict_model`. Where such a position exists, a model's not_stated is refused (`conflict_refused`)
      and kept in `conflict_model`; conflict against no_conflict is the model's (it needs the stance).
    - state: dropped for every previous-round article no longer in this round; for an excerpt article where
      binding is impossible, its structural state; where binding is possible the model's answer stands when
      it is binding or the structural state, and is otherwise refused (kept in `state_model`).
    - alignment: a party listed aligned or opposed on an article where, proposal by proposal, the persona or
      that party holds no applicable position is not_stated by the plan's rule: it is taken off the list.
    Never the key; nothing from a quote's words."""
    counts = Counter({c: 0 for c in SYSTEM_PYTHON_COUNTS})
    if reply is None or item.get("game"):
        return reply, counts
    persona = item["persona"]["id"]
    positions = item.get("positions") or []
    proposals = {pid: dict(piece) for pid, piece in (reply.get("proposals") or {}).items()}
    for article in item["articles"]:
        for n, prop in enumerate(article["proposals"], 1):
            mine = applicable(positions, persona, article["id"], n)
            piece = proposals.get(prop["id"])
            inferred = False
            if piece is not None and piece.get("written_by") != PYTHON:
                # D-711 item 1: an entry that says nothing is held as on record; an inferred one stands only
                # with its line found in the item's text, and is never counted as on record.
                if piece.get("basis") == na.INFERRED:
                    why = basis_refusal(item, piece.get("basis_quote"))
                    if why:
                        if "conflict" in piece:
                            piece["conflict_model"] = piece.pop("conflict")
                        piece["inferred_refused"] = why
                        counts["inferred_refused"] += 1
                    else:
                        inferred = True
                        counts["inferred_kept"] += 1
                else:
                    counts["on_record"] += 1
            if not mine:
                if piece is None:
                    proposals[prop["id"]] = {"id": prop["id"], "reasons": [], "conflict": "not_stated",
                                             "written_by": PYTHON}
                    counts["conflict_filled"] += 1
                elif piece.get("conflict") == "not_stated":
                    counts["conflict_agreed"] += 1
                else:
                    said = piece.get("conflict")
                    if inferred and said is not None:
                        # Not on record is not_stated: the inference stays visible beside it, never scored.
                        piece["inferred"] = {"conflict": said, "basis_quote": piece.get("basis_quote")}
                        counts["inferred_set_aside"] += 1
                    elif said is not None:
                        counts["on_record_without_position"] += 1
                    if "conflict_model" not in piece:
                        piece["conflict_model"] = said
                    piece["conflict"] = "not_stated"
                    piece["conflict_by"] = PYTHON
                    counts["conflict_set"] += 1
            elif piece is not None and piece.get("conflict") == "not_stated":
                piece["conflict_model"] = piece.pop("conflict")
                piece["conflict_refused"] = "positions_on_record"
                counts["conflict_refused"] += 1
    state = dict(reply.get("state") or {})
    state_model = {}
    for article in item["articles"]:
        aid, said = article["id"], state.get(article["id"])
        structural = structural_state(item, article)
        if not binding_possible(item, aid):
            if said is None:
                counts["state_filled"] += 1
            elif said == structural:
                counts["state_agreed"] += 1
            else:
                state_model[aid] = said
                counts["state_set"] += 1
            state[aid] = structural
        elif said is None:
            counts["state_left"] += 1
        elif said in ("binding", structural):
            counts["state_agreed"] += 1
        else:
            state_model[aid] = state.pop(aid)
            counts["state_refused"] += 1
    for aid in dropped_articles(item):
        said = state.get(aid)
        if said is None:
            counts["state_filled"] += 1
        elif said == "dropped":
            counts["state_agreed"] += 1
        else:
            state_model[aid] = said
            counts["state_set"] += 1
        state[aid] = "dropped"
    by_id = {a["id"]: a for a in item["articles"]}
    alignment = {}
    for aid, said in (reply.get("alignment") or {}).items():
        numbers = _numbers(by_id[aid]) if aid in by_id else []
        kept = {}
        inferred, refused_line = False, None
        if said.get("basis") == na.INFERRED:
            refused_line = basis_refusal(item, said.get("basis_quote"))
            inferred = refused_line is None
            counts["alignment_inferred_kept" if inferred else "alignment_inferred_refused"] += 1
        aside = []
        for side in ("aligned", "opposed"):
            kept[side] = []
            for party in said.get(side) or []:
                decided = any(applicable(positions, persona, aid, n) and applicable(positions, party, aid, n)
                              for n in numbers or [None])
                if refused_line:
                    counts["alignment_refused"] += 1
                elif decided:
                    kept[side].append(party)
                elif inferred:
                    # Not on record: the inferred party stays visible beside the entry, never scored.
                    aside.append({"party": party, "side": side})
                    counts["alignment_inferred_set_aside"] += 1
                else:
                    counts["alignment_refused"] += 1
                    counts["on_record_without_position"] += 1
        if inferred:
            kept.update(basis=na.INFERRED, basis_quote=said.get("basis_quote"))
            if aside:
                kept["inferred"] = aside
        elif refused_line:
            kept["inferred_refused"] = refused_line
        alignment[aid] = kept
    out = dict(reply, proposals=proposals, state=state, alignment=alignment)
    if state_model:
        out["state_model"] = state_model
    return out, counts


# ---------------------------------------------------------------------------
# AM-2 (D-665): red lines measured two ways, declared and held


def held_red_line(row):
    """A key proposal's held red line: None when it rests on no declared red line or is still open (its own
    count, `red_line_outcome`); True when it was removed from the next round's text; False when it passed
    (kept or changed). Read from the fate the key already holds, the same for every arm."""
    if not row.get("red_line"):
        return None
    if row["fate"] in HELD_FATES:
        return True
    if row["fate"] in LET_THROUGH_FATES:
        return False
    return None


def red_line_outcome(row):
    """held, not_held or open for a declared red line (None for none; a fate of no class is undetermined)."""
    if not row.get("red_line"):
        return None
    held = held_red_line(row)
    if held is not None:
        return "held" if held else "not_held"
    return "open" if row["fate"] in OPEN_FATES else "undetermined"


def red_line_source(row):
    """A declared red line's source (D-664): the key's own, or, for a key built before the field, the only
    source this version has. A source not declared in RED_LINE_SOURCES is refused, never counted."""
    source = row.get("red_line_source") or RED_LINE_SOURCES[0]
    if source not in RED_LINE_SOURCES:
        raise ValueError("refused: a red line's source is not one of %s" % ", ".join(RED_LINE_SOURCES))
    return source


def extracted_red_line(item, pid, piece):
    """Whether an arm's advice treats a proposal as resting on a red line: it calls it a conflict and a
    persona position on it is one the record marks a red line (the system-mode reading of C-mandate, no key)."""
    number = {p["id"]: (a["id"], i + 1) for a in item["articles"] for i, p in enumerate(a["proposals"])}[pid]
    red = set(item["persona"].get("red_lines") or [])
    mine = applicable(item["positions"], item["persona"]["id"], number[0], number[1])
    return piece.get("conflict") == "conflict" and any(p["id"] in red for p in mine)


def red_line_part(item, key, reply):
    """One item's red-line counter for one arm. The record's side (declared, held, by source) is the same for
    every arm; the arm's side counts the red lines it extracted, those the key declares, and on those its
    agreement with held (its advice holds the line when it rejects or counters). A piece with no stance is
    counted (no_stance) and is a disagreement, never dropped."""
    c = Counter()
    props = (reply or {}).get("proposals") or {}
    for pid, row in key["proposals"].items():
        held = held_red_line(row)
        if row.get("red_line"):
            c["declared"] += 1
            c["source:" + red_line_source(row)] += 1
            c[red_line_outcome(row)] += 1
        piece = props.get(pid)
        if not piece or not extracted_red_line(item, pid, piece):
            continue
        c["extracted"] += 1
        if row.get("red_line") and held is None:
            c["on_" + red_line_outcome(row)] += 1
        if held is None:
            continue
        c["on_declared"] += 1
        stance = piece.get("stance")
        if stance not in ANSWERED_STANCES:
            c["no_stance"] += 1
        else:
            c["agree"] += (stance in HOLDING_STANCES) == held
    return c


def red_lines_report(per_arm, keys):
    """AM-2's aggregates: the record's declared red lines, their sources and the held share, and each arm's
    extraction and agreement with held. Over the arm's own items (the cloud on its subset); a cell of fewer
    than MIN_CELL items with a declared red line is its item count alone."""
    out = {"source_field": "every red line carries its source; this version: %s" % ", ".join(RED_LINE_SOURCES),
           "by_arm": {}}
    record = None
    for arm, parts in sorted(per_arm.items()):
        ids = [i for i in sorted(parts) if keys[i]["part"] != "G"]
        with_red = [i for i in ids if parts[i]["RL"]["declared"]]
        c = sum((parts[i]["RL"] for i in ids), Counter())
        if len(with_red) < MIN_CELL:
            out["by_arm"][arm] = {"items": len(with_red)}
        else:
            out["by_arm"][arm] = {"items": len(with_red), "extracted": c["extracted"], "on_declared": c["on_declared"],
                                  "on_open": c["on_open"], "agree_with_held": c["agree"], "no_stance": c["no_stance"],
                                  "agreement": c["agree"] / c["on_declared"] if c["on_declared"] else None}
        if record is None or len(ids) > record[0]:
            record = (len(ids), len(with_red), c)
    if record is not None:
        _n, items, c = record
        if items < MIN_CELL:
            out["record"] = {"items": items}
        else:
            decided = c["held"] + c["not_held"]
            out["record"] = {"items": items, "declared": c["declared"], "held": c["held"], "not_held": c["not_held"],
                             "open": c["open"], "undetermined": c["undetermined"],
                             "held_share": c["held"] / decided if decided else None,
                             "by_source": {k.split(":", 1)[1]: v for k, v in sorted(c.items()) if k.startswith("source:")}}
    return out


# ---------------------------------------------------------------------------
# AM-3: M10, open-point detection


def open_point_class(fate_label):
    """The key's M10 class of a proposal from its fate: movable (open, changed), settled (kept, removed); None
    for a fate of neither (never scored)."""
    if fate_label in MOVABLE_FATES:
        return MOVABLE
    if fate_label in SETTLED_FATES:
        return SETTLED
    return None


def open_point_prediction(reply, given, pid):
    """(prediction, None) or (NO_ANSWER, reason) of one proposal: movable on a counter, settled on an accept or
    a reject. No stance is a miss by its reason: no reply, a piece the system withheld (in what it gave, not in
    what it kept), no piece for the proposal, a piece with no stance, a stance outside the declared ones."""
    if reply is None:
        return NO_ANSWER, "no_reply"
    piece = (reply.get("proposals") or {}).get(pid)
    if piece is not None and piece.get("written_by") == PYTHON:
        # The system's Python step wrote this piece (a conflict alone): the model gave none.
        return NO_ANSWER, "no_piece"
    if piece is None:
        gave = ((given or {}).get("proposals") or {}).get(pid)
        return NO_ANSWER, ("withheld" if gave is not None else "no_piece")
    stance = piece.get("stance")
    if stance is None:
        return NO_ANSWER, "no_stance"
    if stance in MOVABLE_STANCES:
        return MOVABLE, None
    if stance in SETTLED_STANCES:
        return SETTLED, None
    return NO_ANSWER, "stance_not_declared"


def open_point_part(key, reply, given=None):
    """(rows, misses) of one item for one arm: rows a Counter of (key class, prediction), a miss predicted
    no_answer; misses a Counter of the reasons. `given` is the reply before any withholding."""
    rows, misses = Counter(), Counter()
    for pid, row in key["proposals"].items():
        true = open_point_class(row.get("fate"))
        if true is None:
            continue
        pred, why = open_point_prediction(reply, given if given is not None else reply, pid)
        rows[(true, pred)] += 1
        if why:
            misses[why] += 1
    return rows, misses


def macro_f1_two(c):
    """M10: Macro-F1 over the two classes, movable and settled, whatever the key holds; a prediction of
    no_answer is a miss. A class with no row in the key and none predicted has no F1, and the figure is then
    undefined (None, left out of the bootstrap with its mass reported)."""
    if not c:
        return None
    f1s = []
    for k in M10_CLASSES:
        tp = c.get((k, k), 0)
        fp = sum(v for (t, p), v in c.items() if p == k and t != k)
        fn = sum(v for (t, p), v in c.items() if t == k and p != k)
        if tp + fp + fn == 0:
            return None
        f1s.append(2 * tp / (2 * tp + fp + fn))
    return sum(f1s) / len(f1s)


def open_points_report(per_arm, keys, figures, drops, *, k=1, resamples=None):
    """AM-3's block: per arm on its headline items (the cloud on its subset's) the figure with its interval
    (the same cell as M1's), the key's and the predicted classes, the misses by reason and the parser's drop
    counts of the stance and the reply; and the system-minus-B1 difference where both arms exist. Indicator
    only: no `shown`, never in the claims and never in the bar. A cell under MIN_CELL items is its count."""
    out = {"status": M10_STATUS, "classes": list(M10_CLASSES), "by_arm": {}}
    for arm, parts in sorted(per_arm.items()):
        head = [i for i in sorted(parts) if keys[i]["part"] in HEADLINE]
        if len(head) < MIN_CELL:
            out["by_arm"][arm] = {"items": len(head)}
            continue
        rows = sum((parts[i]["M10"] for i in head), Counter())
        misses = sum((parts[i]["M10m"] for i in head), Counter())
        arm_drops = (drops or {}).get(arm) or {}
        out["by_arm"][arm] = {
            "items": len(head), "figure": figures[arm]["M10"], "rows": sum(rows.values()),
            "key": {c: sum(v for (t, _p), v in rows.items() if t == c) for c in M10_CLASSES},
            "predicted": {c: sum(v for (_t, p), v in rows.items() if p == c) for c in M10_CLASSES + (NO_ANSWER,)},
            "misses": {r: misses[r] for r in M10_MISSES if misses[r]},
            "stance_drops": dict(arm_drops.get("proposals.stance") or {}),
            "reply_drops": dict(arm_drops.get("reply") or {})}
    if "system" in per_arm and "B1" in per_arm:
        head = [i for i in sorted(keys) if keys[i]["part"] in HEADLINE and i in per_arm["system"] and i in per_arm["B1"]]
        diff = test_claim("M10", [per_arm["system"][i]["M10"] for i in head],
                          [per_arm["B1"][i]["M10"] for i in head], k, resamples=resamples)
        out["system_minus_B1"] = dict({f: v for f, v in diff.items() if f != "shown"}, status=M10_STATUS)
    return out


# ---------------------------------------------------------------------------
# section 6.1 and 6.4: the rows of each figure, per item


def item_parts(item, key, reply, *, given=None):
    """{figure: Counter} of one item for one arm. `given` is the arm's reply before any withholding (for
    M8 on what it gave); None means the reply is what it gave."""
    parts = {f: Counter() for f in ("M1", "M1s", "M1m", "M2", "M3", "M4", "M4f", "M5", "M5a", "M5n", "M6", "M7", "M8",
                                    "M8g", "G", "RL", "M10", "M10m")}
    if item.get("game"):
        parts["G"] = game_part(key["game"], item["persona"]["id"], reply)
        return parts
    props = (reply or {}).get("proposals") or {}
    parts["RL"] = red_line_part(item, key, reply)
    parts["M10"], parts["M10m"] = open_point_part(key, reply, given)
    place = {p["id"]: (a["id"], n) for a in item["articles"] for n, p in enumerate(a["proposals"], 1)}
    for pid, row in key["proposals"].items():
        piece = props.get(pid) or {}
        parts["M1"][(row["conflict"], piece.get("conflict", NO_ANSWER))] += 1
        # M1's two parts, a diagnostic beside the plan's figure (lane neg-round1): by the item's positions alone,
        # the same for every arm, a proposal with no applicable persona position (its conflict decided by
        # structure) or with one (conflict against no_conflict needs a stance's meaning).
        mine = applicable(item["positions"], item["persona"]["id"], *place[pid]) if pid in place else []
        parts["M1m" if mine else "M1s"][(row["conflict"], piece.get("conflict", NO_ANSWER))] += 1
        stance = piece.get("stance")
        if row["fate"] in ("kept", "changed", "removed"):
            hit = (stance, row["fate"]) in (("accept", "kept"), ("counter", "changed"), ("reject", "removed"))
            parts["M4"]["hit" if hit else "miss"] += 1
            # D-712: M4 by the key's fate, so a constant stance cannot pass on a set where one fate dominates.
            parts["M4f"][(row["fate"], "hit" if hit else "miss")] += 1
        if row["conflict"] in ("conflict", "no_conflict"):
            hit = (row["conflict"] == "no_conflict" and stance == "accept") or \
                  (row["conflict"] == "conflict" and stance in ("reject", "counter"))
            parts["M5"]["hit" if hit else "miss"] += 1
            if row["advanced"] == "advanced":
                parts["M5a"]["hit" if hit else "miss"] += 1
            elif row["advanced"] == "not_advanced":
                parts["M5n"]["hit" if hit else "miss"] += 1
        if row["fate"] == "changed" and stance == "counter" and piece.get("wording"):
            nxt = key["articles"][row["article"]]["next_text"] or ""
            closer = jaccard5(piece["wording"], nxt) > jaccard5(na.proposal_text(item, pid) or "", nxt)
            parts["M6"]["hit" if closer else "miss"] += 1
    for aid, cells in key["alignment"].items():
        said = ((reply or {}).get("alignment") or {}).get(aid)
        for party, lab in cells.items():
            if reply is None:
                pred = NO_ANSWER
            elif said is None:
                pred = "not_stated"
            else:
                a, o = party in said["aligned"], party in said["opposed"]
                pred = NO_ANSWER if a and o else "aligned" if a else "opposed" if o else "not_stated"
            parts["M2"][(lab, pred)] += 1
    for aid, row in key["articles"].items():
        parts["M3"][(row["state"], ((reply or {}).get("state") or {}).get(aid, NO_ANSWER))] += 1
    if reply is not None:
        targets, approached = set(key["approach_targets"]), set(reply["approach"])
        if approached:
            parts["M7"]["prec_n"] += 1
            parts["M7"]["prec"] += len(approached & targets) / len(approached)
        if targets:
            parts["M7"]["rec_n"] += 1
            parts["M7"]["rec"] += len(approached & targets) / len(targets)
    for name, r in (("M8", reply), ("M8g", given if given is not None else reply)):
        for result in checks(item, key, r, mode="key").values():
            parts[name]["pieces"] += 1
            parts[name]["pass"] += all(result.values())
            for c, ok in result.items():
                parts[name][c] += ok
    return parts


def deal_score(table, deal):
    return sum(table[i][o] for i, o in deal.items())


def game_part(game, persona, reply):
    c = Counter()
    deal = (reply or {}).get("deal") or {}
    c["items"] += 1
    issues = [i["id"] for i in game["issues"]]
    if set(deal) != set(issues):
        return c
    tables, th = game["tables"], game["thresholds"]
    mine = deal_score(tables[persona], deal)
    above = mine >= th[persona]
    passing = [p for p in tables if deal_score(tables[p], deal) >= th[p]]
    feasible = len(passing) >= game["required"] and all(v in passing for v in game["veto"])
    c["G1"] += above and feasible
    c["G4"] += mine > deal_score(tables[persona], game["last_deal"])
    import itertools
    options = [i["options"] for i in game["issues"]]
    scores = {p: deal_score(tables[p], deal) for p in tables}
    dominated = False
    for combo in itertools.product(*options):
        other = dict(zip(issues, combo))
        s = {p: deal_score(tables[p], other) for p in tables}
        if all(s[p] >= scores[p] for p in tables) and any(s[p] > scores[p] for p in tables):
            dominated = True
            break
    c["G2"] += not dominated
    weight = {i: max(tables[persona][i].values()) - min(tables[persona][i].values()) for i in issues}
    for t in (reply or {}).get("trades") or []:
        c["trades"] += 1
        c["G3"] += weight[t["give"]] < weight[t["get"]]
    return c


def class_f1(c, cls):
    """F1 of one class of a (key, prediction) counter (D-712); None when the class has no row and none predicted."""
    tp = c.get((cls, cls), 0)
    fp = sum(v for (t, p), v in c.items() if p == cls and t != cls)
    fn = sum(v for (t, p), v in c.items() if t == cls and p != cls)
    return None if tp + fp + fn == 0 else 2 * tp / (2 * tp + fp + fn)


def macro_f1(c):
    """Macro-F1 over the key's classes; a prediction outside them (no_answer among them) is a miss."""
    classes = sorted({t for (t, _p) in c if isinstance(t, str) and c[(t, _p)] > 0}) if c else []
    if not classes:
        return None
    f1s = []
    for k in classes:
        tp = c.get((k, k), 0)
        fp = sum(v for (t, p), v in c.items() if p == k and t != k)
        fn = sum(v for (t, p), v in c.items() if t == k and p != k)
        f1s.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return sum(f1s) / len(f1s)


def _share_of(c, num, den):
    return c[num] / c[den] if c and c.get(den) else None


def _rate(c):
    n = (c or {}).get("hit", 0) + (c or {}).get("miss", 0)
    return c["hit"] / n if n else None


FIGURES = {
    "M1": macro_f1, "M10": macro_f1_two, "M2": macro_f1, "M3": macro_f1,
    # Diagnostics, not plan figures: M1 on the proposals whose conflict the positions decide by structure
    # (M1s) and on those whose conflict needs a stance's meaning (M1m); see item_parts.
    "M1s": macro_f1, "M1m": macro_f1,
    "M4": _rate,
    "M5": _rate,
    "M5a": _rate,
    "M5n": _rate,
    "M6": _rate,
    "M7p": lambda c: _share_of(c, "prec", "prec_n"), "M7r": lambda c: _share_of(c, "rec", "rec_n"),
    "M8": lambda c: _share_of(c, "pass", "pieces"), "M8g": lambda c: _share_of(c, "pass", "pieces"),
    "G1": lambda c: _share_of(c, "G1", "items"), "G2": lambda c: _share_of(c, "G2", "items"),
    "G3": lambda c: _share_of(c, "G3", "trades"), "G4": lambda c: _share_of(c, "G4", "items"),
}
SOURCE = {"M7p": "M7", "M7r": "M7", "G1": "G", "G2": "G", "G3": "G", "G4": "G"}


def m9_parts(judge_rows, withheld_counters):
    """{(arm, item): Counter(sum, n, two)} of the judge's grades; a withheld system counter scores 0."""
    out = {}
    for r in judge_rows:
        c = out.setdefault((r["arm"], r["item_id"]), Counter())
        c["n"] += 1
        c["sum"] += r["grade"] or 0
        c["two"] += r["grade"] == 2
    for (arm, item_id), n in withheld_counters.items():
        out.setdefault((arm, item_id), Counter())["n"] += n
    return out


# ---------------------------------------------------------------------------
# intervals and claims (plan sections 6.5 and 7)


def interval(fig, parts, alpha=0.05, resamples=None):
    fn = FIGURES[fig]
    est, lo, hi, und = sn.bca(fn, parts, alpha=alpha, resamples=resamples, seed=SEED)
    return {"estimate": est, "lower": lo, "upper": hi, "undefined_mass": und, "items": len(parts)}


def _paired(fn):
    def stat(c):
        a = Counter({k[1:]: v for k, v in c.items() if k[0] == "a"})
        b = Counter({k[1:]: v for k, v in c.items() if k[0] == "b"})
        x, y = fn(_unwrap(a)), fn(_unwrap(b))
        return None if x is None or y is None else x - y
    return stat


def _wrap(tag, c):
    return Counter({(tag,) + (k if isinstance(k, tuple) else (k,)): v for k, v in c.items()})


def _unwrap(c):
    return Counter({(k[0] if len(k) == 1 else k): v for k, v in c.items()})


def test_claim(fig, system_parts, other_parts, k, *, resamples=None):
    """The plan's section 7.2 rule: defined, the BCa lower bound of the paired difference above zero, the
    jackknife lower bound above zero, and the permutation p at most 0.05 / 2^k (one-sided)."""
    alpha = 0.05 / 2 ** k
    if len(system_parts) < MIN_CELL:
        # A comparison on fewer than MIN_CELL items is a reporting cell given as its count alone (plan 6.1).
        return {"items": len(system_parts), "difference": None, "bca_lower": None, "jackknife_lower": None,
                "permutation_p": None, "alpha": alpha, "undefined_mass": None, "shown": False}
    fn = FIGURES[fig]
    paired = [_wrap("a", s) + _wrap("b", o) for s, o in zip(system_parts, other_parts)]
    stat = _paired(fn)
    est, lo, _hi, und = sn.bca(stat, paired, alpha=2 * alpha, resamples=resamples, seed=SEED)
    jack = sn.jackknife_lower(stat, paired, alpha)

    def pair_stat(pp):
        x = fn(sum((a for a, _ in pp), Counter()))
        y = fn(sum((b for _, b in pp), Counter()))
        return None if x is None or y is None else x - y
    p = sn.permutation_p(pair_stat, list(zip(system_parts, other_parts)), resamples=resamples, seed=SEED)
    shown = est is not None and lo is not None and lo > 0 and jack is not None and jack > 0 and p is not None and p <= alpha
    return {"items": len(system_parts), "difference": est, "bca_lower": lo, "jackknife_lower": jack,
            "permutation_p": p, "alpha": alpha, "undefined_mass": und, "shown": shown}


def claim_status(power_record):
    """A1 a claim only when its power is 0.8 or more at every correlation simulated; else an indicator."""
    by = (power_record or {}).get("power_by_icc") or {}
    if by and all(v >= POWER_FLOOR for v in by.values()):
        return "claim"
    return "indicator"


def max_openings(set_sha256):
    """The openings a set may take: MAX_OPENINGS, or the more D-710 grants the one set it names."""
    return EXTRA_OPENINGS.get(set_sha256, MAX_OPENINGS)


def opening_claim_status(power_record, k):
    """A1's status at opening k: an opening beyond MAX_OPENINGS (D-710's third) is an indicator whatever its
    power record says; otherwise `claim_status`."""
    if type(k) is int and k > MAX_OPENINGS:
        return "indicator"
    return claim_status(power_record)


# ---------------------------------------------------------------------------
# the power (plan section 7.3)


POWER_ASSUMED = {"agreement": {"system": 0.70, "B1": 0.60, "cloud": 0.75},
                 "no_answer": {"system": 0.10, "B1": 0.05, "cloud": 0.02}}


def opening_alpha(k):
    """The one-sided alpha of opening k: 0.05 / 2^k, so 0.025 at k = 1 and 0.0125 at k = 2."""
    return 0.05 / 2 ** k


def simulate_power(sizes, shares, *, iccs=(0.2, 0.5), sims=MIN_POWER_SIMS, resamples=500, seed=SEED,
                   assumed=POWER_ASSUMED, k=1):
    """{icc: power} of A1 by simulation: per item a random effect on the logit of agreement with the given
    intra-item correlation; each set scored by `test_claim` at opening k's alpha with `resamples` draws."""
    rng = random.Random(seed)
    classes = sorted(shares)
    out = {}
    for icc in iccs:
        sd = math.sqrt(icc / (1 - icc) * (math.pi ** 2 / 3))
        hits = 0
        for _ in range(sims):
            sys_parts, b1_parts = [], []
            for n in sizes:
                u = rng.gauss(0, sd)
                cs, cb = Counter(), Counter()
                for _r in range(n):
                    true = rng.choices(classes, weights=[shares[c] for c in classes])[0]
                    for arm, c in (("system", cs), ("B1", cb)):
                        if rng.random() < assumed["no_answer"][arm]:
                            pred = NO_ANSWER
                        else:
                            q = assumed["agreement"][arm]
                            q = 1 / (1 + math.exp(-(math.log(q / (1 - q)) + u)))
                            pred = true if rng.random() < q else rng.choice([x for x in classes if x != true] or [true])
                        c[(true, pred)] += 1
                sys_parts.append(cs)
                b1_parts.append(cb)
            hits += test_claim("M1", sys_parts, b1_parts, k, resamples=resamples)["shown"]
        out[str(icc)] = round(hits / sims, 4)
    return out


def code_sha256(path=None):
    """The scorer's SHA-256 over its LF bytes (CRLF made LF), the same on a CRLF checkout and in the commit,
    so a power record names the committed code (#262 gap 2, as tools/negotiation_power.py does)."""
    return hashlib.sha256(Path(path or __file__).read_bytes().replace(*CODE_EOL)).hexdigest()


def is_headline(key):
    """A headline item: a real item of a headline part. A synthetic item never is (D-706 item 3, D-707)."""
    return key["part"] in HEADLINE and not key.get("synthetic")


def power_record(set_dir, *, k=1, sims=MIN_POWER_SIMS, resamples=500, freeze_path=None):
    keys = read_keys(set_dir)
    freeze = _read(freeze_path or Path(set_dir) / "FREEZE.json")
    head = [k for k in keys.values() if is_headline(k)]
    sizes = [len(k["proposals"]) for k in head]
    labels = Counter(r["conflict"] for k in head for r in k["proposals"].values())
    total = sum(labels.values())
    shares = {c: labels[c] / total for c in labels}
    by = simulate_power(sizes, shares, sims=sims, resamples=resamples, k=k)
    return {"schema": "neg-advisor-power-v1", "set_sha256": freeze["set_sha256"], "headline_items": len(sizes),
            "proposals": sum(sizes), "k": k, "alpha": opening_alpha(k), "sims": sims, "resamples": resamples, "shares": shares,
            "assumed": POWER_ASSUMED, "power_by_icc": by, "code_sha256": code_sha256(),
            "a1": claim_status({"power_by_icc": by})}


# ---------------------------------------------------------------------------
# the refusals and the report


def stratum(key):
    """A key's cloud-subset stratum (plan section 5.2): part, configuration and round count; a game item's
    configuration is `game`. Read from the part, the configuration and the round alone."""
    configuration = "game" if key["part"] == "G" else key.get("configuration")
    return "%s|%s|%d" % (key["part"], configuration, key["round"])


def cloud_subset(keys, size=CLOUD_SUBSET_SIZE):
    """The plan's section 5.2 draw, seeded and stratified: places shared among the strata in proportion to
    their sizes by the largest remainder (ties by the stratum's name), then at least one place for each part
    with an item (a part with none takes one, for its largest stratum, ties by name, from the stratum whose
    places exceed its quota most, ties by name, among parts keeping one or more); within a stratum the items
    in the order of the SHA-256 of `20261113-negadv-cloud:<item id>`."""
    strata = {}
    for i, k in keys.items():
        strata.setdefault(stratum(k), []).append(i)
    n = len(keys)
    part = lambda s: s.split("|")[0]
    if size >= n:
        places = {s: len(m) for s, m in strata.items()}
        quota = {s: float(len(m)) for s, m in strata.items()}
    else:
        quota = {s: size * len(m) / n for s, m in strata.items()}
        places = {s: math.floor(q) for s, q in quota.items()}
        rest = size - sum(places.values())
        for s in sorted(strata, key=lambda s: (-(quota[s] - places[s]), s))[:rest]:
            places[s] += 1
        for name in sorted({part(s) for s in strata}):
            mine = [s for s in strata if part(s) == name]
            if sum(places[s] for s in mine) >= MIN_PART_PLACES:
                continue
            held = Counter()
            for s in strata:
                held[part(s)] += places[s]
            donors = [s for s in strata if places[s] > 0 and held[part(s)] > 1]
            if not donors:
                continue
            take = sorted(donors, key=lambda s: (-(places[s] - quota[s]), s))[0]
            give = sorted(mine, key=lambda s: (-len(strata[s]), s))[0]
            places[take] -= 1
            places[give] += 1
    chosen = []
    for s, members in strata.items():
        chosen += sorted(members, key=lambda i: _sha("%s:%s" % (CLOUD_TAG, i)))[:places[s]]
    return {"schema": "neg-advisor-cloud-subset-v1", "size": size, "seed": CLOUD_TAG,
            "reads": "the part, the configuration and the round count of each item, never a label or a result",
            "strata": {s: {"items": len(strata[s]), "places": places[s]} for s in sorted(strata)},
            "items": sorted(chosen)}


def write_cloud_subset(set_dir, keys):
    """cloud_subset.json in the set folder, and its SHA-256."""
    path = Path(set_dir) / SUBSET_FILE
    _write_json(path, cloud_subset(keys))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refuse(*, freeze, configuration, configuration_sha256, k, openings_text, power, power_text, arms, judge=None,
           subset_bytes=None, keys=None, validation=None):
    """None, or the first reason this scoring is refused (plan section 7.4)."""
    if not freeze or freeze.get("dry_run") or not freeze.get("embedding"):
        return "the freeze is a dry run or ran without its embedding test"
    limit = max_openings(freeze.get("set_sha256"))
    if type(k) is not int or not 1 <= k <= limit:
        return "opening %r: at most %d openings for this set" % (k, limit)
    if openings_text is None:
        return "the openings ledger is not committed"
    if not any(int(m.group(1)) == k and m.group(2) == freeze["set_sha256"] and m.group(3) == configuration_sha256
               for m in _OPENING.finditer(openings_text)):
        return "no committed opening line names k=%d, this set and this configuration" % k
    missing = [f for f in CONFIG_FIELDS if not configuration.get(f)]
    if missing:
        return "the configuration lacks %s" % ", ".join(missing)
    if power_text is None or power is None:
        return "the power record is not committed"
    if _sha(power_text) != configuration.get("power_record_sha256"):
        return "the power record is not the configuration's"
    if power.get("set_sha256") != freeze["set_sha256"] or power.get("sims", 0) < MIN_POWER_SIMS \
            or power.get("k") != k or power.get("alpha") != opening_alpha(k) or power.get("code_sha256") != code_sha256():
        return "the power record is not of this set, opening k=%d and its alpha %s, number of sets and code" % (
            k, opening_alpha(k))
    if subset_bytes is None:
        return "the cloud subset (%s) is not in the set folder" % SUBSET_FILE
    subset_sha = hashlib.sha256(subset_bytes).hexdigest()
    if "bound" in SUBSET_REFUSALS and \
            not (subset_sha == freeze.get("cloud_subset_sha256") == configuration.get("cloud_subset_sha256")):
        return "the cloud subset is not the freeze's and the configuration's"
    subset = json.loads(subset_bytes.decode("utf-8"))
    if "drawn" in SUBSET_REFUSALS and (keys is None or subset.get("items") != cloud_subset(keys).get("items")):
        return "the cloud subset is not the plan's draw from this set"
    for arm, field in (("B1", "b1_prompts_sha256"), ("system", "system_prompts_sha256"), ("cloud", "cloud_prompts_sha256")):
        answers = arms.get(arm)
        if answers is None:
            return "the %s arm is not given" % arm
        if answers.get("prompts_sha256") != configuration.get(field):
            return "the %s answers are not of the configuration's prompts" % arm
        if answers.get("schema") != rr.ADVISOR_SCHEMA:
            return "the %s answers are not read by tools/reread_replies.py (%s, not %s): read them again" % (
                arm, answers.get("schema"), rr.ADVISOR_SCHEMA)
    if "answered" in SUBSET_REFUSALS and (arms["cloud"].get("subset_sha256") != subset_sha or sorted(
            {r["item_id"] for r in arms["cloud"].get("rows") or []}) != sorted(subset.get("items") or [])):
        return "the cloud answers are not of the cloud subset's items"
    if judge is None:
        return "the judge's answers are not given"
    if judge.get("prompts_sha256") != configuration.get("judge_prompts_sha256"):
        return "the judge's answers are not of the configuration's judge prompts"
    if judge.get("schema") != rr.ADVISOR_SCHEMA:
        return "the judge's answers are not read by tools/reread_replies.py: read them again"
    if validation is None:
        return "the mapping validation is not given"
    if validation.get("prompts_sha256") != configuration.get("validate_prompts_sha256"):
        return "the mapping validation is not of the configuration's validate prompts"
    given = dict(arms, judge=judge, validation=validation)
    for record, group in MODEL_BOUND_GROUPS:
        loaded = ((given[record].get("models") or {}).get(group) or {}).get("model_id")
        if loaded != registry_model(group):
            return "the %s pass did not load %s, the registry's model of its agent" % (group, registry_model(group))
    digests = configuration.get("checkpoint_digests") or {}
    for arm, group in DIGEST_GROUPS:
        loaded = ((given[arm].get("models") or {}).get(group) or {}).get("digest")
        if not digests.get(group) or loaded != digests[group]:
            return "the %s checkpoint loaded is not the configuration's" % group
    return None


def registry_model(group):
    """The model a form group must load: the registry's own `model` of the group's agent, read from
    config/agent_registry.json at call time (the judge and the validator: JUDGE's Phi-4)."""
    declared = {g["group"]: g for g in na.load_config(na.CONFIG_PATH)["models"]}[group]
    registry = json.loads((Path(ROOT) / "config" / "agent_registry.json").read_text(encoding="utf-8"))
    return registry["agents"][declared["agent"]]["model"]


def replies_by_item(answers, group):
    return {r["item_id"]: r for r in answers["rows"] if r["form"] == "advice" and r["group"] == group}


def _cell(fig, pool, resamples):
    """One reporting cell: under MIN_CELL items its count alone; a game figure its estimate and count, no
    interval (plan 6.4); otherwise the estimate and its interval."""
    if len(pool) < MIN_CELL:
        return {"items": len(pool)}
    if SOURCE.get(fig) == "G":
        return {"estimate": FIGURES[fig](sum(pool, Counter())), "items": len(pool)}
    return interval(fig, pool, resamples=resamples)


def _figures(parts, ids, keys, resamples):
    head = [i for i in ids if keys[i]["part"] in HEADLINE]
    games = [i for i in ids if keys[i]["part"] == "G"]
    return {fig: _cell(fig, [parts[i][SOURCE.get(fig, fig)] for i in (games if SOURCE.get(fig) == "G" else head)],
                       resamples) for fig in FIGURES}


def withheld_counters(item, key, given, kept):
    """The counters the system withheld that the judge would have graded (`neg_advisor.judged`): a counter
    with wording on a proposal whose fate is changed or kept. Each scores 0 in M9."""
    if not given or item.get("game"):
        return 0
    return sum(1 for pid, e in given["proposals"].items()
               if pid not in (kept or {}).get("proposals", {}) and na.judged(e, key["proposals"].get(pid)))


def cell_dimensions(items, keys, structures):
    """The report's cell dimensions, each (name, item id -> group): the plan's configuration and round count,
    the party structure (Seckin 20:32), the persona's kind (D-668 gap 6: a coalition persona apart from a single
    party), the part, the post-cutoff mark and the record kind (D-711)."""
    return (("configuration", lambda i: keys[i].get("configuration")), ("round", lambda i: keys[i]["round"]),
            ("structure", lambda i: structures.get(i)),
            ("persona_kind", lambda i: keys[i].get("persona_kind") or items[i]["persona"]["kind"]),
            ("part", lambda i: keys[i]["part"]), ("post_cutoff", lambda i: keys[i]["post_cutoff"]),
            ("record_kind", lambda i: keys[i].get("record_kind", RECORD_KIND_UNSET)))


def report(items, keys, arms, *, k=1, judge=None, power=None, resamples=None, subset=None, validation=None,
           python_step=True):
    """The report of a set: the real items alone give every headline figure, cell, claim and the bar; the
    synthetic items, when the set holds any, are reported apart under `synthetic` by the same rules, never
    pooled with the real ones, their claims indicators and their bar never the bar (D-706 item 3, D-707).
    Per-item rows of both stay under `_per_item`, which the caller writes only inside the set folder."""
    real = {i: v for i, v in keys.items() if not v.get("synthetic")}
    synthetic = {i: v for i, v in keys.items() if v.get("synthetic")}
    sub = None if subset is None else set(subset)
    kw = dict(k=k, resamples=resamples, validation=validation, python_step=python_step)
    if real:
        out = _report_on(items, real, arms, judge=judge, power=power,
                         subset=None if sub is None else sorted(sub & set(real)), **kw)
    else:
        out = {"schema": "neg-advisor-report-v1", "items": 0, "headline_items": 0, "figures": {}, "claims": {},
               "bar": {"cleared": None, "why": "no real items: the synthetic row is never the bar"}, "_per_item": {}}
    out["real_items"] = len(real)
    if synthetic:
        syn = _report_on(items, synthetic, arms, judge=judge, power=None,
                         subset=None if sub is None else sorted(sub & set(synthetic)), **kw)
        for arm, rows in syn.pop("_per_item").items():
            out["_per_item"].setdefault(arm, {}).update(rows)
        for claim in syn.get("claims", {}).values():
            claim["status"] = "indicator"
            claim["shown"] = False
        syn["bar"] = dict(syn.get("bar") or {}, is_the_bar=False)
        syn["row"] = SYNTHETIC_ROW
        out["synthetic"] = syn
    else:
        out["synthetic"] = {"items": 0}
    return out


def _report_on(items, keys, arms, *, k=1, judge=None, power=None, resamples=None, subset=None, validation=None,
               python_step=True):
    """The aggregates of one group of items (the real ones, or apart the synthetic ones): per arm every figure with its interval, per configuration and round count M1 to M3
    with n (a cell under 5 items its count alone), the system's audit trail, the trades, the games and the
    claims. The cloud reference is read on the cloud subset alone (D-606), with B1 and the system on the
    same subset beside their full figures; A2 is on the subset's headline items."""
    ids = sorted(keys)
    sub = sorted(subset) if subset is not None else ids
    validation = validation or {}
    per_arm, trails, trades = {}, Counter(), {}
    advised = {}
    withheld = Counter()
    python_counts = Counter()
    for arm, (answers, group) in arms.items():
        rows = replies_by_item(answers, group)
        mine = sub if arm == "cloud" else ids
        parts, tr = {}, Counter()
        for i in mine:
            row = rows.get(i) or {}
            reply = row.get("reply")
            given = reply
            if arm == "system":
                if python_step:
                    reply, computed = system_python(items[i], reply)
                    python_counts.update(computed)
                reply, trail = withhold(items[i], reply, row.get("audit"))
                trails.update(trail)
                withheld[("system", i)] += withheld_counters(items[i], keys[i], given, reply)
            parts[i] = item_parts(items[i], keys[i], reply, given=given)
            advised.setdefault(arm, {})[i] = reply
            v, n, carried, on_record = trade_checks(items[i], reply)
            tr.update({"valid": v, "given": n, "carried": carried, "on_record": on_record})
        per_arm[arm] = parts
        trades[arm] = dict(tr)
    figures = {arm: _figures(parts, sorted(parts), keys, resamples) for arm, parts in per_arm.items()}
    on_subset = {arm: _figures(parts, [i for i in sub if i in parts], keys, resamples)
                 for arm, parts in per_arm.items() if arm != "cloud"}
    head = [i for i in ids if keys[i]["part"] in HEADLINE]
    head_sub = [i for i in sub if keys[i]["part"] in HEADLINE]
    # Seckin 20:32: each item's party structure, computed from its declared parties (a frozen key without the
    # field is read from its item; a key naming another structure is refused).
    structures = {i: item_structure(items[i], keys[i]) for i in ids if items[i].get("parties")}
    cells = {}
    for arm, parts in per_arm.items():
        for dim, value in cell_dimensions(items, keys, structures):
            groups = {}
            for i in sorted(parts):
                if keys[i]["part"] != "G":
                    groups.setdefault(str(value(i)), []).append(i)
            for g, members in groups.items():
                for fig in ("M1", "M2", "M3"):
                    cells.setdefault(arm, {}).setdefault(dim, {}).setdefault(g, {})[fig] = _cell(
                        fig, [parts[i][fig] for i in members], resamples)
    out = {"schema": "neg-advisor-report-v1", "items": len(ids), "headline_items": len(head),
           "cloud_subset": {"items": len(sub), "headline_items": len(head_sub)}, "figures": figures,
           "figures_on_cloud_subset": on_subset, "cells": cells, "system_trail": dict(trails), "trades": trades,
           # The system's Python step (system_python): what the positions on record set, filled and refused.
           "system_python": dict(python_counts) if python_step else "off",
           "a1_status": opening_claim_status(power, k), "metric": "our metric, no published benchmark",
           "validation": {f: validation.get(f) for f in ("mapping", "checker", "grade", "fields")},
           # AM-2 (D-665): red lines declared and held, each with its source.
           "red_lines": red_lines_report(per_arm, keys),
           # D-663: every answer field the parser could not read, by arm, field and reason.
           "drops": dict({arm: rr.drop_counts(answers, group) for arm, (answers, group) in arms.items()},
                         judge=rr.drop_counts({"rows": judge or []}))}
    given, kept = trails.get("given", 0), trails.get("kept", 0)
    out["withheld_rate"] = (given - kept) / given if given else None
    claims = {}
    if "system" in per_arm and "B1" in per_arm:
        claims["A1"] = dict(test_claim("M1", [per_arm["system"][i]["M1"] for i in head],
                                       [per_arm["B1"][i]["M1"] for i in head], k, resamples=resamples),
                            status=opening_claim_status(power, k))
        for fig in ("M2", "M3"):
            claims["A3_" + fig] = dict(test_claim(fig, [per_arm["system"][i][fig] for i in head],
                                                  [per_arm["B1"][i][fig] for i in head], k, resamples=resamples),
                                       status="indicator")
    if "system" in per_arm and "cloud" in per_arm:
        claims["A2"] = dict(test_claim("M1", [per_arm["system"][i]["M1"] for i in head_sub],
                                       [per_arm["cloud"][i]["M1"] for i in head_sub], k, resamples=resamples),
                            status="indicator", on="the cloud subset's headline items")
    if claims.get("A1", {}).get("status") != "claim" and "A1" in claims:
        claims["A1"]["shown"] = False
    out["claims"] = claims
    # AM-3: M10 beside M1, indicator only; outside the claims, so the bar never reads it.
    out["M10"] = open_points_report(per_arm, keys, figures, out["drops"], k=k, resamples=resamples)
    if judge is not None:
        m9 = m9_parts(judge, withheld)
        out["M9"] = {}
        for arm in per_arm:
            c = sum((v for (a, _i), v in m9.items() if a == arm), Counter())
            out["M9"][arm] = {"mean_grade": c["sum"] / c["n"] if c["n"] else None,
                              "share_two": c["two"] / c["n"] if c["n"] else None, "counters": c["n"],
                              "withheld_counters": sum(v for (a, _i), v in withheld.items() if a == arm)}
        out["M9_status"] = "validated" if validation.get("grade") else "not validated"
    out["bar"] = bar(out, validation=validation)
    # D-711 items 2 and 3, D-712: every bar figure and floor per record kind, and the NEG_BAR.md reading.
    out["by_record_kind"] = {arm: kind_figures(parts, keys, arms[arm], resamples)
                             for arm, parts in per_arm.items()}
    # Seckin 20:32: every bar figure and floor per party structure and overall; the bar refused on one structure.
    out["by_structure"] = {arm: structure_figures(parts, keys, arms[arm], resamples, structures)
                           for arm, parts in per_arm.items()}
    out["neg_bar"] = neg_bar_reading(keys, out["by_record_kind"].get("system"), out["by_structure"].get("system"),
                                     structures)
    # D-668 gap 4: whom each arm approached among the parties moving toward or away (indicator only).
    out["movement"] = movement_report(advised, keys, structures)
    out["_per_item"] = {arm: {i: {f: {str(k): v for k, v in c.items()} for f, c in parts[i].items() if c}
                              for i in sorted(parts)} for arm, parts in per_arm.items()}
    return out


# ---------------------------------------------------------------------------
# the bar of NEG_BAR.md (D-709, D-711 item 3, D-712): per record kind, the lines and the class floors

BAR_FIGURES = ("M1", "M1m", "M10", "M4", "M7p", "M7r", "M8")
NEG_BAR_LINES = (("1", (("M1", 0.60),)), ("2", (("M10", 0.60),)), ("3", (("M4", 0.60),)),
                 ("4", (("M7r", 0.80), ("M7p", 0.70))), ("5", (("M8", 1.0),)))
NEG_BAR_M1_LOWER = 0.33
NEG_BAR_DROP_SHARE = 0.10
# D-712 (Seckin 20:49): the class floors, each at 0.60 (no figure below 60), on the line of its figure. A figure
# averaged over classes, or a rate a constant answer could pass, is floored on the class that matters:
# M1 and M1m on the conflict class's F1; M10 on the movable class's F1; M4 on the hit rate within each fate
# the key holds. M7's two sides are floored by line 4 itself; M8 needs 1.0; M2, M3, M5 and M6 are not bar
# figures, their per-class rows are reported in `figures` only (NEG_BAR.md lists each).
CLASS_FLOOR = 0.60
CLASS_FLOORS = (("1", "M1", "conflict"), ("1", "M1m", "conflict"), ("2", "M10", MOVABLE),
                ("3", "M4f", "kept"), ("3", "M4f", "changed"), ("3", "M4f", "removed"))


def record_kind(key):
    return key.get("record_kind") or UNDECLARED_KIND


def _read_fields(reply):
    """How many answer fields a read reply holds (the denominator of the drop share beside the drops)."""
    if not isinstance(reply, dict):
        return 0
    if "deal" in reply:
        return len(reply.get("deal") or {}) + len(reply.get("trades") or [])
    return sum(len(reply.get(f) or []) for f in ("proposals", "state", "alignment", "approach", "trades"))


def drop_share(answers, group, ids):
    """Fields dropped over fields read plus dropped, on the given items' rows of one group (a reply lost whole
    counts as one drop, its reason `reply`)."""
    read = dropped = 0
    for r in answers.get("rows") or []:
        if r.get("form") == "advice" and r.get("group") == group and r.get("item_id") in ids:
            read += _read_fields(r.get("reply"))
            dropped += sum(sum(v.values()) for v in (r.get("drops") or {}).values())
    return {"read": read, "dropped": dropped, "share": dropped / (read + dropped) if read + dropped else None}


def class_floors(parts, ids):
    """Each D-712 floor's value on the pooled rows of the items: a class F1, or for M4 the hit rate in one fate
    (None when the fate has no row; a floor with no value is not met)."""
    out = []
    for line, fig, cls in CLASS_FLOORS:
        pool = sum((parts[i][fig] for i in ids), Counter())
        if fig == "M4f":
            n = pool.get((cls, "hit"), 0) + pool.get((cls, "miss"), 0)
            value = pool.get((cls, "hit"), 0) / n if n else None
            rows = n
        else:
            value = class_f1(pool, cls)
            rows = sum(v for (t, _p), v in pool.items() if t == cls)
        out.append({"line": line, "figure": fig, "class": cls, "value": value, "rows": rows,
                    "floor": CLASS_FLOOR, "met": value is not None and value >= CLASS_FLOOR})
    return out


def group_figures(parts, keys, arm_answers, resamples, group_of, groups):
    """{group: {items, figures, floors, drops}} over the arm's headline items of each group (`group_of(item id)`):
    the bar figures with their intervals (a cell under MIN_CELL items its count alone), the class floors and
    the drop share. A group with no item is left out."""
    answers, group = arm_answers
    out = {}
    head = [i for i in sorted(parts) if keys[i]["part"] in HEADLINE]
    for g in groups:
        ids = [i for i in head if group_of(i) == g]
        if not ids:
            continue
        out[g] = {"items": len(ids),
                  "figures": {fig: _cell(fig, [parts[i][SOURCE.get(fig, fig)] for i in ids], resamples)
                              for fig in BAR_FIGURES},
                  "floors": class_floors(parts, ids), "drops": drop_share(answers, group, set(ids))}
    return out


def kind_figures(parts, keys, arm_answers, resamples):
    """{record kind: {items, figures, floors, drops}} over the arm's headline items of each kind (D-711 item 3)."""
    return group_figures(parts, keys, arm_answers, resamples, lambda i: record_kind(keys[i]),
                         RECORD_KINDS + (UNDECLARED_KIND,))


def structure_figures(parts, keys, arm_answers, resamples, structures):
    """{structure: {items, figures, floors, drops}} per party structure (the operator's 20:32 instruction), and
    the same over every headline item as `overall`."""
    out = group_figures(parts, keys, arm_answers, resamples, lambda i: structures.get(i) or UNDECLARED_STRUCTURE,
                        STRUCTURES + (UNDECLARED_STRUCTURE,))
    out.update(group_figures(parts, keys, arm_answers, resamples, lambda i: OVERALL, (OVERALL,)))
    return out


MOVEMENT_STATUS = "indicator only (D-668 gap 4): never a claim, never in the bar"


def party_moves(key):
    """{party: toward | away | mixed} of one key's movement map over its articles: toward when it moved toward
    the persona on some article and away on none, away the reverse, mixed when both; steady and not_stated
    parties are left out."""
    seen = {}
    for cells in (key.get("movement") or {}).values():
        for party, label in cells.items():
            if label in ("toward", "away"):
                seen.setdefault(party, set()).add(label)
    return {p: (labels.pop() if len(labels) == 1 else "mixed") for p, labels in seen.items()}


def movement_report(advised, keys, structures):
    """D-668 gap 4, three-party moves: per arm and per structure (and overall), of the parties moving toward the
    persona the share the arm approached, and of those moving away the share it approached. A cell under
    MIN_CELL items gives its count alone. Indicator only, never in the bar. A key built before the field has no
    movement map and adds nothing."""
    out = {"status": MOVEMENT_STATUS, "arms": {}}
    for arm, replies in advised.items():
        cells = {}
        for i, reply in replies.items():
            moves = party_moves(keys[i])
            approached = set((reply or {}).get("approach") or [])
            for group in (structures.get(i) or UNDECLARED_STRUCTURE, OVERALL):
                c = cells.setdefault(group, {"items": set(), "counts": Counter()})
                if moves:
                    c["items"].add(i)
                for party, label in moves.items():
                    c["counts"][label] += 1
                    c["counts"][label + "_approached"] += party in approached
                # An arm that gives the movement itself (the step-wise chain) is read against the key, cell by cell.
                said = (reply or {}).get("movement")
                if isinstance(said, dict):
                    for aid, cells_ in (keys[i].get("movement") or {}).items():
                        for party, label in cells_.items():
                            c["counts"]["movement_rows"] += 1
                            c["counts"]["movement_agreed"] += (said.get(aid) or {}).get(party) == label
        block = {}
        for group, c in cells.items():
            n = len(c["items"])
            if n < MIN_CELL:
                block[group] = {"items": n}
                continue
            counts = dict(c["counts"])
            block[group] = {"items": n, "counts": counts,
                            "toward_approached": (counts.get("toward_approached", 0) / counts["toward"]
                                                  if counts.get("toward") else None),
                            "away_approached": (counts.get("away_approached", 0) / counts["away"]
                                                if counts.get("away") else None),
                            "movement_agreement": (counts.get("movement_agreed", 0) / counts["movement_rows"]
                                                   if counts.get("movement_rows") else None)}
        out["arms"][arm] = block
    return out


def item_structure(item, key):
    """The item's structure, computed from its declared parties; a key that names another is refused."""
    got = structure_of(item.get("parties"))
    if key.get("structure") is not None and key["structure"] != got:
        raise ValueError("%s: the key's structure is not the one the item's parties give" % key.get("item_id"))
    return got


def bar_lines(block):
    """One block's NEG_BAR.md lines, each with its figures and its class floors (D-712)."""
    figs, floors = block.get("figures") or {}, block.get("floors") or []
    lines = {}
    for line, needs in NEG_BAR_LINES:
        ok = all((figs.get(fig) or {}).get("estimate") is not None and figs[fig]["estimate"] >= target
                 for fig, target in needs)
        if line == "1":
            lower = (figs.get("M1") or {}).get("lower")
            ok = ok and lower is not None and lower > NEG_BAR_M1_LOWER
        if line == "5":
            share = (block.get("drops") or {}).get("share")
            ok = ok and share is not None and share <= NEG_BAR_DROP_SHARE
        missed = [f for f in floors if f["line"] == line and not f["met"]]
        lines[line] = {"figures_met": ok, "floors_missed": ["%s:%s" % (f["figure"], f["class"]) for f in missed],
                       "met": ok and not missed}
    return lines


def neg_bar_reading(keys, by_kind, by_structure=None, structures=None):
    """The NEG_BAR.md bar read for the system arm on each record kind apart: refused for a set without both
    kinds or with an item of undeclared kind (D-711 item 3), and for a set whose headline items hold fewer than
    MIN_STRUCTURES party structures or an item whose structure is not computed (the operator's 20:32
    instruction; `structures` {item id: structure}, else each key's own); else per kind every line with its
    class floors (D-712). Refused too when a structure it holds has fewer than MIN_ITEMS_PER_STRUCTURE headline
    items (D-715 item 1). Passed only when every line and floor holds on both kinds, on every structure the set
    holds and overall (`structures` in the reading, D-715 item 1). Which set it may be read on (the validation
    set, once per round) is the procedure's, not the scorer's."""
    heads = [i for i in keys if keys[i]["part"] in HEADLINE]
    kinds = {record_kind(keys[i]) for i in heads}
    if structures is None:
        structures = {i: keys[i].get("structure") for i in heads}
    held = {structures.get(i) or UNDECLARED_STRUCTURE for i in heads}
    refusals = []
    if UNDECLARED_KIND in kinds:
        refusals.append("an item's record kind is not declared (D-711 item 2)")
    elif set(RECORD_KINDS) - kinds:
        refusals.append("the set does not hold both record kinds (D-711 item 3): %s missing"
                        % ", ".join(sorted(set(RECORD_KINDS) - kinds)))
    if UNDECLARED_STRUCTURE in held:
        refusals.append("an item's party structure is not computed (Seckin 20:32)")
    elif len(held) < MIN_STRUCTURES:
        refusals.append("the set holds one party structure only (Seckin 20:32): %s" % ", ".join(sorted(held)))
    else:
        few = sorted(s for s in held if sum(1 for i in heads if structures.get(i) == s) < MIN_ITEMS_PER_STRUCTURE)
        if few:
            refusals.append("the set holds fewer than %d headline items of %s (D-715 item 1)"
                            % (MIN_ITEMS_PER_STRUCTURE, ", ".join(few)))
    if refusals:
        return {"refused": "; ".join(refusals), "passed": False}
    if not by_kind:
        return {"refused": "no system arm", "passed": False}
    out = {"passed": True, "kinds": {}}
    for kind in RECORD_KINDS:
        lines = bar_lines(by_kind.get(kind) or {})
        out["kinds"][kind] = lines
        if "kinds" in BAR_READ_ON:
            out["passed"] = out["passed"] and all(v["met"] for v in lines.values())
    # D-715 item 1: every structure the set holds and overall each meet every line and floor, or the bar is not
    # met; a structure or the overall block missing from `by_structure` is read as not met.
    blocks = by_structure or {}
    out["structures"] = {s: bar_lines(blocks.get(s) or {}) for s in sorted(held) + [OVERALL]}
    for s, lines in out["structures"].items():
        if ("overall" if s == OVERALL else "structures") in BAR_READ_ON:
            out["passed"] = out["passed"] and all(v["met"] for v in lines.values())
    out["structures_failing"] = sorted(s for s, lines in out["structures"].items()
                                       if not all(v["met"] for v in lines.values()))
    return out


def judge_prompts(set_dir, arms, out):
    """The judge's prompts from every arm's answers: the system's withheld counters are not shown (they
    score 0 in M9); every other counter on a proposal whose fate is changed or kept is, blind."""
    items, keys = na.read_items(set_dir), read_keys(set_dir)
    replies = {}
    for arm, (answers, group) in arms.items():
        rows = replies_by_item(answers, group)
        replies[arm] = {}
        for i in items:
            row = rows.get(i) or {}
            reply = row.get("reply")
            if arm == "system":
                reply, _trail = withhold(items[i], reply, row.get("audit"))
            replies[arm][i] = reply
    entries = na.judge_entries(items, keys, replies, na.mandate_text)
    return na.build_judge(entries, outside_repository(out))


def bar(rep, *, validation=None):
    """The plan's section 7.1, line by line. Line 1, one rule for a claim and an indicator: A1's paired
    difference at least 10 points AND its BCa lower bound above zero. Line 4: the mapping validation and
    every field of the checker's sample at or above kappa 0.60, else not assessable."""
    validation = validation or {}
    f = rep["figures"]
    if "system" not in f or "B1" not in f:
        return {"cleared": None, "why": "both arms are needed"}
    single = sorted(f for f, v in (validation.get("fields") or {}).items()
                    if f.split(":")[0] in ("mapping", "checker") and v.get("label"))
    if not (validation.get("mapping") and validation.get("checker")):
        return {"cleared": None, "why": "not assessable: the mapping validation or the checker's sample is below "
                                        "kappa 0.60 (a single-class field below 100 percent agreement, AM-1) or "
                                        "not recorded", "lines": {"4": False}, "single_class_fields": single}
    s8, b8 = f["system"]["M8g"].get("estimate"), f["B1"]["M8g"].get("estimate")
    a1 = rep["claims"].get("A1", {})
    diff, lower = a1.get("difference"), a1.get("bca_lower")
    lines = {
        "1": diff is not None and lower is not None and diff >= BAR_MARGIN and lower > 0,
        "2": s8 is not None and b8 is not None and s8 >= b8 - 0.05,
        "3": rep["withheld_rate"] is not None and rep["withheld_rate"] <= 0.30,
        "4": True,
    }
    return {"cleared": all(lines.values()), "lines": lines, "single_class_fields": single}


def agreement(reference, other):
    """One field's agreement (AM-1): its rows, Cohen's kappa, the raw agreement, whether the reference gives
    a single class, and whether it is at the bar: kappa at or above KAPPA_FLOOR, or, on a single-class field
    (kappa undefined, or 0 whatever the other side says), the raw agreement at SINGLE_CLASS_FULL, labelled."""
    n = len(reference)
    raw = sum(1 for x, y in zip(reference, other) if x == y) / n if n else None
    kappa = _kappa(reference, other)
    single = n > 0 and len(set(reference)) == 1
    value = {"rows": n, "kappa": kappa, "raw_agreement": raw, "single_class": single}
    value["at_or_above_floor"] = at_bar(value)
    if single:
        value["label"] = SINGLE_CLASS_LABEL
    return value


def at_bar(value):
    """A recorded agreement at the bar (AM-1): a single-class field by its raw agreement at SINGLE_CLASS_FULL,
    any other by its kappa at or above KAPPA_FLOOR. A record without the single-class fields (written before
    AM-1) is read by its kappa alone."""
    if not isinstance(value, dict):
        return False
    if value.get("single_class"):
        raw = value.get("raw_agreement")
        return isinstance(raw, (int, float)) and raw >= SINGLE_CLASS_FULL
    kappa = value.get("kappa")
    return isinstance(kappa, (int, float)) and kappa >= KAPPA_FLOOR


def _field_numbers(value):
    return {f: value.get(f) for f in ("rows", "kappa", "raw_agreement", "single_class", "label")
            if value.get(f) is not None} | {"at_bar": at_bar(value)}


def validation_state(set_dir, judge_answers=None):
    """Line 4's inputs read from the set folder: the mapping validation's latest round, every checker field,
    and the grade agreement of these judge answers, each at the bar by AM-1's rule (`at_bar`). A missing file
    is False. `fields` carries each one's numbers (kappa, raw agreement, the single-class label), no text."""
    set_dir = Path(set_dir)
    out = {"mapping": False, "checker": False, "grade": False, "fields": {}}
    path = set_dir / "mapping_validation.json"
    if path.is_file():
        value = _read(path)
        out["mapping"] = at_bar(value)
        out["fields"]["mapping"] = _field_numbers(value)
    path = set_dir / "checker_agreement.json"
    if path.is_file():
        fields = _read(path).get("fields") or {}
        out["checker"] = sorted(fields) == sorted(SAMPLE_FIELDS) and all(at_bar(v) for v in fields.values())
        out["fields"].update({"checker:" + f: _field_numbers(v) for f, v in sorted(fields.items())})
    path = set_dir / "grade_agreement.json"
    if path.is_file() and judge_answers is not None:
        g = _read(path)
        out["grade"] = at_bar(g) and g.get("judge_prompts_sha256") == judge_answers.get("prompts_sha256")
        out["fields"]["grade"] = _field_numbers(g)
    return out


# ---------------------------------------------------------------------------
# the mapping validation, the checker's samples and the hand-back


def build_positions(set_dir):
    return {_read(p)["item_id"]: _read(p).get("positions") or [] for p in sorted((Path(set_dir) / "build").glob("*/build.json"))}


NOT_AN_ID = "not_an_id"


def validator_article(said, ids):
    """The validator's article as the reader takes it (D-617): exactly one id of the item's list, as
    written; anything else (a heading, a near spelling, an id of another item) is its own different answer,
    never mapped to an id."""
    got, _ = answer_form.match(said, ids)   # by its form alone (D-663): case, spaces, quotes, a number
    return got if got is not None else NOT_AN_ID


# The article rule each validate form was read under: version 1 (round 1, validate_p01) took the answer
# as written, as the reader at ad9a5c8a did, so a re-read of round 1 gives its recorded kappa; version 2
# (D-617) takes only an exact id of the item's list.
ARTICLE_RULES = {1: lambda said, ids: said, 2: validator_article}


def validate_read(set_dir, answers, prompts_sha256, previous=None, form_version=1):
    """The mapping's agreement with the validator: Cohen's kappa over (article, proposal, stance), over
    EVERY position of the build files. Refused when the answers are not of the validate prompts file
    (`prompts_sha256`), when the pass did not load the registry's JUDGE model (Phi-4), or when a position
    has no answer row; an answer row that does not parse counts as no_answer, a disagreement. Each run is
    one round, kept with the rounds before it (`previous`), so the hand-back gives the kappa before and
    after a revision; the top level is the latest round, with the prompts digest and the pass's models,
    which score binds."""
    by_item = build_positions(set_dir)
    mapper = {(i, p["id"]): p for i, ps in by_item.items() for p in ps}
    if "prompts" in VALIDATION_REQUIRES and answers.get("prompts_sha256") != prompts_sha256:
        raise ValueError("refused: the validate answers are not of this validate prompts file")
    model = ((answers.get("models") or {}).get("validate") or {}).get("model_id")
    if "model" in VALIDATION_REQUIRES and model != registry_model("validate"):
        raise ValueError("refused: the validate pass did not load %s" % registry_model("validate"))
    rows = {(r["item_id"], r["position_id"]): r for r in answers["rows"] if r["form"] == "validate"}
    missing = sorted(set(mapper) - set(rows))
    if "every_position" in VALIDATION_REQUIRES and missing:
        raise ValueError("refused: %d position(s) have no validate answer row" % len(missing))
    ids = {i: set(na.article_ids(item)) for i, item in na.read_items(set_dir).items()}
    a, b, agree, off_list = [], [], 0, 0
    for pos, m in sorted(mapper.items()):
        r = rows.get(pos) or {}
        mine = "%s|%s|%s" % (m["article"], m.get("proposal"), m["stance"])
        if r.get("mapping"):
            said = ARTICLE_RULES[form_version](r["mapping"].get("article"), ids.get(pos[0], set()))
            off_list += said == NOT_AN_ID
            theirs = "%s|%s|%s" % (said, r["mapping"].get("proposal"), r["mapping"].get("stance"))
        else:
            theirs = NO_ANSWER
        a.append(mine)
        b.append(theirs)
        agree += mine == theirs
    measured = agreement(a, b)
    latest = {"form_version": form_version, "article_not_an_id": off_list,
              "drops": rr.drop_counts({"rows": list(rows.values())}),
              "positions": len(mapper), "answered": sum(1 for x in b if x != NO_ANSWER), "agree": agree,
              "floor": KAPPA_FLOOR, "prompts_sha256": answers.get("prompts_sha256"), "models": answers.get("models"),
              **{f: v for f, v in measured.items() if f != "rows"}}
    rounds = list((previous or {}).get("rounds") or []) + [latest]
    return dict(latest, schema="neg-advisor-mapping-validation-v1", unit="(article, proposal, stance)", rounds=rounds)


def _kappa(a, b):
    n = len(a)
    if n == 0:
        return None
    agree = sum(1 for x, y in zip(a, b) if x == y) / n
    labels = set(a) | set(b)
    chance = sum((a.count(c) / n) * (b.count(c) / n) for c in labels)
    return None if chance == 1 else (agree - chance) / (1 - chance)


def _seeded(ids, tag, share, minimum):
    order = sorted(ids, key=lambda i: _sha("%s:%s" % (tag, i)))
    return order[:min(len(order), max(minimum, math.ceil(share * len(order))))]


def _persona_positions(item):
    return [p["id"] for p in item.get("positions") or [] if p["party"] == item["persona"]["id"]]


# The persona fields the checker's sheet leaves out: the red lines, and their sources (D-664), which name them too.
CHECKER_HIDDEN = ("red_lines", "red_line_sources")


def sample_sheet(set_dir):
    """The checker's sheet: the sampled items with no label and no red-line mark (the persona's red lines
    are a field it labels again: `red_line` or `not_red_line` per persona position)."""
    items, keys = na.read_items(set_dir), read_keys(set_dir)
    chosen = _seeded([i for i in items if items[i]["part"] != "G"], "20261113-negadv-sample", SAMPLE_SHARE, SAMPLE_MIN)
    unmarked = lambda item: dict(item, persona={f: v for f, v in item["persona"].items() if f not in CHECKER_HIDDEN})
    return {"schema": "neg-advisor-checker-sheet-v1", "items": [
        {"item_id": i, "item": unmarked(items[i]),
         "next_articles": {a: r["next_text"] for a, r in keys[i]["articles"].items()},
         "fill": {"fate": {p: None for p in keys[i]["proposals"]}, "state": {a: None for a in keys[i]["articles"]},
                  "conflict": {p: None for p in keys[i]["proposals"]},
                  "alignment": {a: {q: None for q in cells} for a, cells in keys[i]["alignment"].items()},
                  "red_line": {p: None for p in _persona_positions(items[i])}}}
        for i in chosen]}


def sample_read(set_dir, sheet):
    keys, items = read_keys(set_dir), na.read_items(set_dir)
    fields = {f: ([], []) for f in SAMPLE_FIELDS}
    for entry in sheet["items"]:
        key, fill = keys[entry["item_id"]], entry["fill"]
        item = items[entry["item_id"]]
        red = set(item["persona"].get("red_lines") or [])
        for pos in _persona_positions(item):
            fields["red_line"][0].append("red_line" if pos in red else "not_red_line")
            fields["red_line"][1].append((fill.get("red_line") or {}).get(pos) or NO_ANSWER)
        for pid, row in key["proposals"].items():
            for f in ("fate", "conflict"):
                fields[f][0].append(row[f])
                fields[f][1].append(fill[f].get(pid) or NO_ANSWER)
        for aid, row in key["articles"].items():
            fields["state"][0].append(row["state"])
            fields["state"][1].append(fill["state"].get(aid) or NO_ANSWER)
        for aid, cells in key["alignment"].items():
            for q, lab in cells.items():
                fields["alignment"][0].append(lab)
                fields["alignment"][1].append((fill["alignment"].get(aid) or {}).get(q) or NO_ANSWER)
    # AM-1: each field by `agreement`, the key the reference: a field where the key gives one class is at
    # the bar only at 100 percent raw agreement, labelled "single class, kappa undefined".
    out = {f: agreement(a, b) for f, (a, b) in fields.items()}
    return {"schema": "neg-advisor-checker-agreement-v1", "items": len(sheet["items"]), "fields": out}


def grade_sheet(judge_prompts):
    value = na.read_file(judge_prompts)
    entries = [p["entry"] for p in value["prompts"] if p["form"] == "judge"]
    chosen = set(_seeded([e["entry_id"] for e in entries], "20261113-negadv-grade", GRADE_SHARE, GRADE_MIN))
    return {"schema": "neg-advisor-grade-sheet-v1", "entries": [
        {"entry_id": e["entry_id"], "proposal": e["proposal"], "mandate": e["mandate"], "wording": e["wording"],
         "next": e["next"], "grade": None} for e in entries if e["entry_id"] in chosen]}


def grade_read(sheet, judge_answers):
    judged = {r["entry_id"]: r["grade"] for r in judge_answers["rows"] if r["form"] == "judge"}
    a = [str(e["grade"]) for e in sheet["entries"]]
    b = [str(judged.get(e["entry_id"])) for e in sheet["entries"]]
    # AM-1 for M9's validation: the checker's grades the reference, the judge's the other side.
    measured = agreement(a, b)
    return dict({f: v for f, v in measured.items() if f != "rows"}, schema="neg-advisor-grade-agreement-v1",
                entries=len(a), judge_prompts_sha256=judge_answers.get("prompts_sha256"))


def handback(set_dir):
    """Counts only: no id, no quote, no text field of any kind."""
    keys = read_keys(set_dir)
    out = {"schema": "neg-advisor-handback-v1", "items": len(keys),
           "per_part": dict(Counter(k["part"] for k in keys.values())),
           "per_round": dict(Counter(str(k["round"]) for k in keys.values())),
           "per_configuration": dict(Counter(k.get("configuration") or "game" for k in keys.values())),
           "post_cutoff": sum(1 for k in keys.values() if k["post_cutoff"]),
           "synthetic": sum(1 for k in keys.values() if k["synthetic"])}
    rows = {"conflict": Counter(), "fate": Counter(), "state": Counter(), "alignment": Counter()}
    for k in keys.values():
        for r in k["proposals"].values():
            rows["conflict"][r["conflict"]] += 1
            rows["fate"][r["fate"]] += 1
        for r in k["articles"].values():
            rows["state"][r["state"]] += 1
        for cells in k["alignment"].values():
            rows["alignment"].update(cells.values())
    out["rows"] = {f: {"rows": sum(c.values()), "shares": {lab: round(v / sum(c.values()), 4) for lab, v in c.items()}}
                   for f, c in rows.items() if c}
    out["counters_possible"] = sum(1 for k in keys.values() for r in k["proposals"].values() if r["fate"] in na.JUDGED_FATES)
    out["game_items"] = sum(1 for k in keys.values() if k["part"] == "G")
    for name in ("mapping_validation.json", "checker_agreement.json", "FREEZE.json"):
        path = Path(set_dir) / name
        if path.is_file():
            v = _read(path)
            if name == "FREEZE.json":
                out["freeze"] = {"set_sha256": v.get("set_sha256"), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                 "leakage_counts": v.get("leakage_counts"), "dry_run": v.get("dry_run"),
                                 "cloud_subset_sha256": v.get("cloud_subset_sha256")}
            elif name == "mapping_validation.json":
                out["mapping_validation"] = {"kappa_by_round": [r.get("kappa") for r in v.get("rounds") or [v]],
                                             "positions": v.get("positions"), "at_or_above_floor": v.get("at_or_above_floor")}
            else:
                out[name[:-5]] = _numbers_only(v)
    out["sources"] = source_counts(set_dir)
    out.update(role_counts(set_dir))
    return out


SOURCE_STATES = ("research_allowed", "redistribution_allowed")


def source_counts(set_dir):
    """The sources by count (brief section 9): `sources.json`, a list of {used, research_allowed,
    redistribution_allowed}, each of the two terms true, false or null (unconfirmed). Counts only."""
    path = Path(set_dir) / "sources.json"
    if not path.is_file():
        return None
    out = {"used": 0, "refused": 0}
    for s in _read(path):
        out["used" if s.get("used") is True else "refused"] += 1
        for term in SOURCE_STATES:
            v = s.get(term)
            state = "unconfirmed" if v is None else ("yes" if v is True else "no")
            out["%s_%s" % (term, state)] = out.get("%s_%s" % (term, state), 0) + 1
    return out


ROLE_COUNTS = ("positions_dropped", "items_replaced", "shortfall_P", "shortfall_H", "shortfall_G")


def role_counts(set_dir):
    """The role session's own counts (brief section 9), from `role_counts.json`: whole numbers under the
    declared names only; anything else is refused, so no text can travel this way."""
    path = Path(set_dir) / "role_counts.json"
    if not path.is_file():
        return {}
    value = _read(path)
    if not isinstance(value, dict) or set(value) - set(ROLE_COUNTS) \
            or any(type(v) is not int or v < 0 for v in value.values()):
        raise ValueError("refused: role_counts.json holds whole numbers under %s only" % ", ".join(ROLE_COUNTS))
    return dict(value)


def _numbers_only(value):
    if isinstance(value, dict):
        return {k: _numbers_only(v) for k, v in value.items() if not isinstance(v, str) or k == "schema"}
    if isinstance(value, list):
        return [_numbers_only(v) for v in value if not isinstance(v, str)]
    return value


# ---------------------------------------------------------------------------
# the leakage pass, through the freeze machinery (plan section 8)


def item_passages(item):
    texts = [p["text"] for a in item.get("articles") or [] for p in a["paragraphs"]]
    texts += [p["quote"] for p in item.get("positions") or []]
    return [t for t in texts if len(t.split()) >= fz().MIN_WORDS]


def fz():
    return _load("freeze_negotiation_set", ROOT / "tools" / "freeze_negotiation_set.py")


ACCEPT_PREFIX = "accept-skipped:"


def corpus_list(path):
    """(corpus paths, accepted skipped kinds) of a corpus list, read exactly as freeze_negotiation_set.main
    reads it (D-618): blank lines and lines starting with # left out, every line stripped, each
    `accept-skipped: <kind>` line a kind corpus_passages accepts though it does not read it, every other
    line a path."""
    lines = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#")]
    accept = [l.split(":", 1)[1].strip() for l in lines if l.startswith(ACCEPT_PREFIX)]
    return [Path(l) for l in lines if not l.startswith(ACCEPT_PREFIX)], accept


def set_digest(set_dir):
    """(listing, SHA-256) of the frozen set: every file under items/ (item.json, key.json and SOURCE.md of
    each item) with its own SHA-256, sorted by path."""
    set_dir = Path(set_dir)
    listing = sorted((str(p.relative_to(set_dir)).replace("\\", "/"), hashlib.sha256(p.read_bytes()).hexdigest())
                     for p in (set_dir / "items").rglob("*") if p.is_file())
    digest = _sha("\n".join("%s %s" % x for x in listing))
    return listing, digest


def freeze(set_dir, corpus_paths, *, encode=None, model=None, progress=print, accept_skipped=(), export=None):
    f = fz()
    set_dir = outside_repository(set_dir)
    items = na.read_items(set_dir)
    corpora = f.corpus_passages(corpus_paths, accept_skipped=accept_skipped)
    mine = {i: item_passages(it) for i, it in items.items()}
    if export is not None:
        # The embedding input alone (freeze_negotiation_set.export_records), no model, no FREEZE.json.
        return f.export_records([p for c in corpora.values() for p in c["passages"]]
                                + [p for ps in mine.values() for p in ps], outside_repository(export))
    sources = {}
    for i in items:
        src = set_dir / "build" / i / "SOURCE.md"
        text = src.read_text(encoding="utf-8") if src.is_file() else ""
        sources[i] = set(f._URL.findall(text))
    index = f.GramIndex([(i, p) for i, ps in mine.items() for p in ps])
    jaccard_hits = {name: index.matches(c["passages"]) for name, c in corpora.items()}
    corpus_vectors = ({n: f.encode_chunked(encode, c["passages"], progress=progress, label=n)
                       for n, c in corpora.items() if c["passages"]} if encode else {})
    counts, leaked = Counter(), []
    for i, ps in mine.items():
        hits = {name: {t for o, t in h if o == i} for name, h in jaccard_hits.items()}
        vectors = f.encode_chunked(encode, ps) if encode and ps else None
        leaks = f.leakage(ps, vectors, corpora, corpus_vectors, urls=sources[i], stems=set(), jaccard_hits=hits)
        hit = False
        for name, c in leaks.items():
            for threshold, n in c.items():
                if n:
                    counts["%s:%s" % (name, threshold)] += n
                    hit = True
        if hit:
            leaked.append(i)
    if leaked:
        raise ValueError("leakage: %d item(s) over a threshold; replace them and run again" % len(leaked))
    subset_sha = write_cloud_subset(set_dir, read_keys(set_dir))
    listing, digest = set_digest(set_dir)
    value = {"schema": "neg-advisor-freeze-v1", "set_sha256": digest, "files": len(listing), "items": len(items),
             "leakage_counts": dict(counts), "corpora": sorted(str(p) for p in corpus_paths),
             "thresholds": {"jaccard": f.JACCARD, "ngram": f.NGRAM, "cosine": f.COSINE, "min_words": f.MIN_WORDS},
             "embedding": ({"model": model, "precision": "float32"} if encode is not None else None),
             "dry_run": encode is None, "cloud_subset_sha256": subset_sha,
             "listing": "every file under items/, each item's SOURCE.md among them"}
    _write_json(set_dir / ("FREEZE.json" if encode is not None else "FREEZE.dryrun.json"), value)
    return value


# ---------------------------------------------------------------------------
# the command line


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "handback", "power", "sample", "validate-prompts", "validate-read", "sample-read", "freeze", "score"):
        s = sub.add_parser(name, allow_abbrev=False)
        s.add_argument("--set", required=True, type=Path)
        if name in ("handback", "power", "sample", "validate-prompts"):
            s.add_argument("--out", required=True, type=Path)
    sub.choices["power"].add_argument("--k", required=True, type=int)
    sub.choices["validate-read"].add_argument("--answers", required=True, type=Path)
    sub.choices["validate-read"].add_argument("--prompts", required=True, type=Path)
    sub.choices["sample-read"].add_argument("--sheet", required=True, type=Path)
    sub.choices["freeze"].add_argument("--corpora", required=True, type=Path)
    sub.choices["freeze"].add_argument("--extra", action="append", type=Path, default=[])
    sub.choices["freeze"].add_argument("--no-embedding", action="store_true")
    sub.choices["freeze"].add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    sub.choices["freeze"].add_argument("--export-records", type=Path, default=None)
    sub.choices["freeze"].add_argument("--vectors", type=Path, default=None)
    sub.choices["freeze"].add_argument("--records", type=Path, default=None)
    s = sub.choices["score"]
    s.add_argument("--configuration", required=True, type=Path)
    s.add_argument("--k", required=True, type=int)
    for arm in ("b1", "system", "cloud"):
        s.add_argument("--" + arm, required=True, type=Path)
    s.add_argument("--judge", required=True, type=Path)
    s.add_argument("--per-item-out", type=Path)
    jp = sub.add_parser("judge-prompts", allow_abbrev=False)
    jp.add_argument("--set", required=True, type=Path)
    for arm in ("b1", "system", "cloud"):
        jp.add_argument("--" + arm, required=True, type=Path)
    jp.add_argument("--out", required=True, type=Path)
    g = sub.add_parser("grade-sheet", allow_abbrev=False)
    g.add_argument("--judge-prompts", required=True, type=Path)
    g.add_argument("--out", required=True, type=Path)
    gr = sub.add_parser("grade-read", allow_abbrev=False)
    gr.add_argument("--set", required=True, type=Path)
    gr.add_argument("--sheet", required=True, type=Path)
    gr.add_argument("--judge-answers", required=True, type=Path)
    args = parser.parse_args(argv)
    c = args.command
    if c == "build":
        print(json.dumps(build_set(args.set)))
    elif c == "handback":
        _write_json(args.out, handback(args.set))
        print(json.dumps({"written": "counts only"}))
    elif c == "power":
        _write_json(args.out, power_record(args.set, k=args.k))
        print(json.dumps({"written": str(args.out)}))
    elif c == "sample":
        _write_json(outside_repository(args.out), sample_sheet(args.set))
        print(json.dumps({"written": "the checker's sheet"}))
    elif c == "sample-read":
        _write_json(Path(args.set) / "checker_agreement.json", sample_read(args.set, _read(args.sheet)))
    elif c == "validate-prompts":
        value = na.build(args.set, "validate", None, outside_repository(args.out), positions=build_positions(args.set))
        print(json.dumps({"prompts": value["prompt_count"]}))
    elif c == "validate-read":
        path = Path(args.set) / "mapping_validation.json"
        _write_json(path, validate_read(args.set, _read(args.answers), hashlib.sha256(args.prompts.read_bytes()).hexdigest(),
                                        _read(path) if path.is_file() else None,
                                        form_version=na.validate_form_version(_read(args.prompts).get("config"))))
    elif c == "judge-prompts":
        value = judge_prompts(args.set, {"B1": (_read(args.b1), "b1"), "system": (_read(args.system), "system_advice"),
                                         "cloud": (_read(args.cloud), "b1")}, args.out)
        print(json.dumps({"prompts": value["prompt_count"]}))
    elif c == "grade-sheet":
        _write_json(outside_repository(args.out), grade_sheet(args.judge_prompts))
    elif c == "grade-read":
        value = grade_read(_read(args.sheet), _read(args.judge_answers))
        _write_json(outside_repository(Path(args.set) / "grade_agreement.json"), value)
        print(json.dumps({"entries": value["entries"], "kappa": value["kappa"]}))
    elif c == "freeze":
        paths, accept = corpus_list(args.corpora)
        paths += list(args.extra)
        f = fz()
        if args.export_records is not None:
            out = freeze(args.set, paths, accept_skipped=accept, export=args.export_records)
            print(json.dumps(dict(out, forecast_minutes=f.route_forecast_minutes(out["rows"]))))
            return 0
        encode, release, model = (None, None, None)
        if args.vectors is not None:
            if args.no_embedding or args.records is None:
                print("refused: --vectors needs --records and takes no --no-embedding")
                return 2
            encode = f.vectors_encoder(args.vectors, args.records)
            model = encode.route
        elif not args.no_embedding:
            encode, release, model = f.bge_m3_encoder(args.device)
            encode = f.formed(encode)
        try:
            value = freeze(args.set, paths, encode=encode, model=model, accept_skipped=accept)
        finally:
            if release is not None:
                release()
        print(json.dumps({"items": value["items"], "leakage_counts": value["leakage_counts"], "dry_run": value["dry_run"]}))
    else:
        items, keys = na.read_items(args.set), read_keys(args.set)
        conf_text = args.configuration.read_text(encoding="utf-8")
        power_text = sn.committed_text(ROOT, POWER_RECORD)
        arms = {"B1": _read(args.b1), "system": _read(args.system), "cloud": _read(args.cloud)}
        judge_answers = _read(args.judge)
        subset_path = Path(args.set) / SUBSET_FILE
        subset_bytes = subset_path.read_bytes() if subset_path.is_file() else None
        why = refuse(freeze=_read(Path(args.set) / "FREEZE.json") if (Path(args.set) / "FREEZE.json").is_file() else None,
                     configuration=json.loads(conf_text), configuration_sha256=_sha(conf_text), k=args.k,
                     openings_text=sn.committed_text(ROOT, OPENINGS), power=json.loads(power_text) if power_text else None,
                     power_text=power_text, arms=arms, judge=judge_answers, subset_bytes=subset_bytes, keys=keys,
                     validation=_read(Path(args.set) / "mapping_validation.json")
                     if (Path(args.set) / "mapping_validation.json").is_file() else None)
        if why:
            print("refused: " + why)
            return 2
        if args.per_item_out:
            inside_set(args.per_item_out, args.set)
        judge = [r for r in judge_answers["rows"] if r["form"] == "judge"]
        rep = report(items, keys, {"B1": (arms["B1"], "b1"), "system": (arms["system"], "system_advice"),
                                   "cloud": (arms["cloud"], "b1")}, k=args.k, judge=judge, power=json.loads(power_text),
                     subset=json.loads(subset_bytes.decode("utf-8"))["items"],
                     validation=validation_state(args.set, judge_answers))
        if args.per_item_out:
            _write_json(inside_set(args.per_item_out, args.set), rep.pop("_per_item"))
        rep.pop("_per_item", None)
        print(json.dumps(rep, indent=1, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
