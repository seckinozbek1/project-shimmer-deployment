#!/usr/bin/env python3
"""Seckin's 200 blind labels of the labeller's positions (D-736, D-739; role V's tool, NEG-SYNTH-A).

After the OLMo run role V draws about 200 positions: about 50 uniformly at random (seeded, the seed recorded: the
labeller's accuracy without bias) and about 150 where the labeller's probability over the declared stances at the
deciding token is lowest (neg_synth_label.py read-pass --confidence; his label replaces the labeller's there).
Seckin labels by phone through the supervisor's chat (D-739): role V writes the positions in batches of 10 to
_xfer/V_to_supervisor (each a short id, the text he needs and every field's answers numbered), the supervisor
writes his answers as JSON to _xfer/supervisor_to_V, and this tool merges them and writes counts only for the lead.

    draw --random-only  --sheets S1 --sheets S2 [--seed N] [--random 50] --out <work>/review_random.json
             [--counts <_xfer/V_to_lead>/V_SYNLAB1_RANDOM_DRAWN.json]   before the labeller (Seckin 16:45)
    draw --random2 300 --after <work>/review_random.json --sheets S1 --sheets S2 --out <work>/review_random2.json
             [--counts <_xfer/V_to_lead>/V_SYNLAB1_RANDOM2_DRAWN.json]   300 more, uniformly, before the labeller
    draw     --sheets S1 --sheets S2 --labels L1 --labels L2 --confidence C1 --confidence C2
             --after <work>/review_random2.json (or review_random.json) [--low 150] --out <work>/review_set.json
             (without --after: both groups at once, [--seed N] [--random 50])
    batches  --review <work>/review_set.json --sheets S1 --sheets S2 --out-dir <_xfer/V_to_supervisor>
    read     --review <work>/review_set.json --sheets S1 --sheets S2 --answers-dir <_xfer/supervisor_to_V>
             --labels L1 --labels L2 --counts <_xfer/V_to_lead>/V_SYNLAB1_SECKIN_COUNTS.json --merged-dir <work>

A batch holds no labeller label, probability or group, in a seeded shuffled order. An answers file is
{"schema": "neg-synth-seckin-answers-v1", "batch": N, "batch_sha256": (optional, the batch's own), "answers":
{"P001": {"article": 1, "wording": 1, "stance": 2, "firm_limit": 1}}}: option numbers (an option text is
accepted only when it is not itself a number).
Printed lines and the counts file carry counts, the seed and digests only, never a quote, an item id or a label.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import secrets
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import neg_synth as ns  # noqa: E402
import neg_synth_label as nsl  # noqa: E402

REVIEW_SCHEMA = "neg-synth-review-set-v1"
COUNTS_SCHEMA = "neg-synth-review-counts-v1"
GROUPS = ("random", "random2", "low")   # random2: the 300 drawn second (Seckin 17:59)


def _sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def _sheets(paths):
    out = {}
    for path in paths:
        name = nsl.set_of(path)
        out[name] = {s["item_id"]: s for s in nsl.check_sheets(json.loads(Path(path).read_text(encoding="utf-8")))}
    return out


_READING = re.compile(r"^(?P<set>.+)_r[0-9]+$")


def label_set(path, sets=None):
    """A labels file's set, from its name: `labels_<set>.json`, or `labels_<set>_r<k>.json` for a later reading of
    the same saved replies (lane/label-wording-reader). With `sets` (the sheets' set names) the name must be one of
    them, alone or with that reading tag, else it is refused, so a labels file never goes silently unmatched."""
    name = Path(path).name
    if not (name.startswith("labels_") and name.endswith(".json")):
        raise ValueError("refused: a labels file is named labels_<set>.json or labels_<set>_r<k>.json")
    stem = name[len("labels_"):-len(".json")]
    if sets is None:
        return stem
    if stem in sets:
        return stem
    tagged = _READING.match(stem)
    if tagged and tagged.group("set") in sets:
        return tagged.group("set")
    raise ValueError("refused: the labels file %s names no set of the sheets given" % name)


def _by_set(paths, schema_key=None, sets=None):
    out = {}
    for path in paths:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if schema_key:
            if value.get("schema") != nsl.CONFIDENCE_SCHEMA:
                raise ValueError("refused: not a confidence file")
            name = value["set"]
        else:
            name = label_set(path, sets)
        if name in out:
            raise ValueError("refused: two files of one set")
        out[name] = value["positions"] if schema_key else value
    return out


def draw(sheets, labels, confidence, *, seed=None, n_random=50, n_low=150):
    """The review set: `n_random` positions drawn uniformly from every sheet position with `random.Random(seed)`,
    then the `n_low` lowest by confidence among the rest (no label or no confidence first, then the lowest
    probability, then the key), shown in one seeded shuffled order."""
    seed = secrets.randbelow(2 ** 31) if seed is None else int(seed)
    pool = sorted((name, item, pos["id"]) for name, items in sheets.items() for item, s in items.items()
                  for pos in s["positions"])
    rng = random.Random(seed)
    chosen = rng.sample(pool, min(n_random, len(pool)))
    rest = [k for k in pool if k not in set(chosen)]

    def low_key(k):
        name, item, pos = k
        has_label = pos in labels.get(name, {}).get(item, {})
        c = (confidence.get(name, {}).get(item, {}).get(pos) or {}).get("confidence")
        return (1 if has_label and c is not None else 0, c if c is not None else -1.0, k)
    low = sorted(rest, key=low_key)[:n_low]
    rows = [dict(group="random", set=k[0], item_id=k[1], position_id=k[2]) for k in chosen] + \
           [dict(group="low", set=k[0], item_id=k[1], position_id=k[2]) for k in low]
    rng.shuffle(rows)
    for n, row in enumerate(rows, 1):
        row["review_id"] = "P%03d" % n
    return {"schema": REVIEW_SCHEMA, "seed": seed, "random": len(chosen), "low": len(low), "pool": len(pool),
            "rows": rows, "drawn_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


RANDOM_SCHEMA = "neg-synth-review-random-v1"


def _pool(sheets):
    return sorted((name, item, pos["id"]) for name, items in sheets.items() for item, s in items.items()
                  for pos in s["positions"])


def _keys_sha(rows):
    """The SHA-256 of the drawn positions, as (set, item, position, review id) in their drawn order."""
    return _sha(json.dumps([[r["set"], r["item_id"], r["position_id"], r["review_id"]] for r in rows]))


def draw_random(sheets, *, seed=None, n_random=50):
    """Seckin 16:45: the uniform group alone, drawn before the labeller runs (it needs no label): `n_random`
    positions sampled with `random.Random(seed)` and shown in that generator's shuffled order, ids P001...; the
    seed and the drawn positions' SHA-256 recorded, so the later draw takes exactly these and excludes them."""
    seed = secrets.randbelow(2 ** 31) if seed is None else int(seed)
    pool = _pool(sheets)
    rng = random.Random(seed)
    chosen = rng.sample(pool, min(n_random, len(pool)))
    rows = [dict(group="random", set=k[0], item_id=k[1], position_id=k[2]) for k in chosen]
    rng.shuffle(rows)
    for n, row in enumerate(rows, 1):
        row["review_id"] = "P%03d" % n
    return {"schema": RANDOM_SCHEMA, "seed": seed, "random": len(rows), "pool": len(pool), "rows": rows,
            "drawn_sha256": _keys_sha(rows), "drawn_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


RANDOM2_SCHEMA = "neg-synth-review-random2-v1"
RECORD_GROUPS = {RANDOM_SCHEMA: ("random",), RANDOM2_SCHEMA: ("random", "random2")}


def prior_rows(prior, sheets):
    """Every row of an earlier random record (draw_random's, or draw_random2's which carries the first one's rows
    unchanged before its own), held to the record's own SHA-256 and to these sheets."""
    groups = RECORD_GROUPS.get(prior.get("schema"))
    if groups is None or _keys_sha(prior.get("rows") or []) != prior.get("drawn_sha256"):
        raise ValueError("refused: not the recorded random draw (its positions differ from their SHA-256)")
    pool = set(_pool(sheets))
    if any((r["set"], r["item_id"], r["position_id"]) not in pool or r["group"] not in groups for r in prior["rows"]):
        raise ValueError("refused: the recorded random draw names a position these sheets do not hold")
    keys = [(r["set"], r["item_id"], r["position_id"]) for r in prior["rows"]]
    if len(set(keys)) != len(keys):
        raise ValueError("refused: the recorded random draw names one position twice")
    return [dict(r) for r in prior["rows"]]


def draw_random2(sheets, prior, *, n=300):
    """Seckin 17:59 (the lead 18:01): `n` more positions drawn uniformly at random, before the labeller, from the
    pool minus every position the recorded draw holds; all of them when fewer remain (`short` says so). Sampled and
    shuffled with random.Random of the recorded seed and the step, ids continuing after the record's; the record's
    rows come first unchanged, so its batches keep their digests; the new record's SHA-256 covers every row."""
    if prior.get("schema") != RANDOM_SCHEMA:
        raise ValueError("refused: the second random draw follows the first random draw's record")
    first = prior_rows(prior, sheets)
    taken = {(r["set"], r["item_id"], r["position_id"]) for r in first}
    rest = [k for k in _pool(sheets) if k not in taken]
    rng = random.Random("%s:random2" % prior["seed"])
    chosen = rng.sample(rest, min(n, len(rest)))
    rows = [dict(group="random2", set=k[0], item_id=k[1], position_id=k[2]) for k in chosen]
    rng.shuffle(rows)
    for number, row in enumerate(rows, len(first) + 1):
        row["review_id"] = "P%03d" % number
    every = first + rows
    return {"schema": RANDOM2_SCHEMA, "seed": prior["seed"], "random": len(first), "random2": len(rows), "asked": n,
            "short": len(rows) < n, "pool": prior["pool"], "remaining_after": len(rest) - len(rows), "rows": every,
            "random_sha256": prior["drawn_sha256"], "drawn_sha256": _keys_sha(every),
            "drawn_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


def draw_after(sheets, labels, confidence, prior, *, n_low=150):
    """The review set after the labeller ran: the recorded random group unchanged (ids and order), then the `n_low`
    lowest by confidence among the positions it did not draw, shuffled with the recorded seed, ids continuing."""
    first = prior_rows(prior, sheets)
    taken = {(r["set"], r["item_id"], r["position_id"]) for r in first}
    rest = [k for k in _pool(sheets) if k not in taken]

    def low_key(k):
        name, item, pos = k
        has_label = pos in labels.get(name, {}).get(item, {})
        c = (confidence.get(name, {}).get(item, {}).get(pos) or {}).get("confidence")
        return (1 if has_label and c is not None else 0, c if c is not None else -1.0, k)
    low = [dict(group="low", set=k[0], item_id=k[1], position_id=k[2]) for k in sorted(rest, key=low_key)[:n_low]]
    random.Random(prior["seed"]).shuffle(low)
    for n, row in enumerate(low, len(first) + 1):
        row["review_id"] = "P%03d" % n
    return {"schema": REVIEW_SCHEMA, "seed": prior["seed"], "random": sum(r["group"] == "random" for r in first),
            "random2": sum(r["group"] == "random2" for r in first), "low": len(low),
            "pool": prior["pool"], "rows": first + low, "random_sha256": prior["drawn_sha256"],
            "drawn_sha256": _keys_sha(first + low),
            "drawn_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


def page_items(review, sheets, t):
    """What a batch shows for each review row: the sheet's round, parties and articles, the statement with its
    party and round, and each field's declared answers. Never a label, a probability or the row's group."""
    items = []
    for row in review["rows"]:
        sheet = sheets[row["set"]][row["item_id"]]
        position = next(p for p in sheet["positions"] if p["id"] == row["position_id"])
        items.append({"id": row["review_id"], "round": sheet["round"],
                      "parties": ["%s (%s)" % (p["id"], p["kind"]) for p in sheet["parties"]],
                      "articles": [{"id": a["id"], "title": a["title"], "agreed": bool(a["agreed"]), "text": a["text"]}
                                   for a in sheet["articles"]],
                      "party": position["party"], "statement_round": position["round"], "quote": position["quote"],
                      "answers": nsl.declared_answers(sheet, position, t)})
    return items


BATCH_SCHEMA = "neg-synth-review-batch-v1"
BATCH_SIZE = 10


def batches(review, sheets, t, size=BATCH_SIZE):
    """[(number, json value, text)]: the review rows in their drawn order, `size` a batch, each position under its
    short id with the text Seckin needs (round, parties, articles, the statement with its party and round) and
    each field's answers numbered from 1. No labeller label, probability or group."""
    items = page_items(review, sheets, t)
    out = []
    for start in range(0, len(items), size):
        number = start // size + 1
        chunk = items[start:start + size]
        for item in chunk:
            item["options"] = {f: {str(n): v for n, v in enumerate(vals, 1)} for f, vals in item.pop("answers").items()}
        value = {"schema": BATCH_SCHEMA, "batch": number, "batches": (len(items) + size - 1) // size, "items": chunk}
        lines = ["Batch %d of %d. For each position give one number per line, as in: P001 article 1, wording 1, "
                 "stance 2, firm 1." % (number, value["batches"]), ""]
        names = {"article": "article", "wording": "wording", "stance": "stance", "firm_limit": "firm"}
        for item in chunk:
            lines += ["%s. Round %s. Parties: %s." % (item["id"], item["round"], ", ".join(item["parties"])), ""]
            for a in item["articles"]:
                lines += ["ARTICLE %s: %s%s" % (a["id"], a["title"], " (agreed)" if a["agreed"] else ""), a["text"], ""]
            lines += ["STATEMENT by %s, round %s:" % (item["party"], item["statement_round"]), item["quote"], ""]
            for f, opts in item["options"].items():
                lines.append("%s: %s" % (names[f], ", ".join("%s) %s" % (n, v) for n, v in opts.items())))
            lines += ["", "---", ""]
        value["sha256"] = _sha(json.dumps(chunk, sort_keys=True, ensure_ascii=False))
        out.append((number, value, chr(10).join(lines)))
    return out


ANSWERS_SCHEMA = "neg-synth-seckin-answers-v1"
# D-748: the supervisor's list of conditional acceptances sits beside the answers files; it is no answers file.
CONDITIONAL_FILE = "conditional_items.json"
# D-745 (Seckin 17:39 and 17:42): an answers file says where its labels came from. Its top-level field PROVENANCE_FIELD
# names one of PROVENANCES; a file without it, or with any other value, is refused (the lead 17:46: refusing is the
# safe side). Only BLIND answers are his independent labels: every other provenance is counted and reported apart,
# never pooled with them. Declared by the supervisor who writes the files (the lead 18:03): the key "provenance" at
# the top level, beside schema, batch, batch_sha256 and answers; "blind" (Seckin's own independent reading),
# "suggested_and_approved" (he approved the supervisor's suggested labels), "agent_annotated_and_approved" (three
# blind agent annotators, two reviewers, a recommender, Seckin approving the open items). A free-text
# "provenance_note" beside it is never read.
PROVENANCE_FIELD = "provenance"
BLIND = "blind"
SUGGESTED = "suggested_and_approved"
AGENT_ANNOTATED = "agent_annotated_and_approved"
PROVENANCES = (BLIND, SUGGESTED, AGENT_ANNOTATED)


def provenance_of(files):
    """{review id: provenance} from the answer files' top-level provenance field (D-745)."""
    out = {}
    for value in files:
        prov = value.get(PROVENANCE_FIELD)
        if prov not in PROVENANCES:
            raise ValueError("refused: an answers file carries no declared provenance (D-745)")
        for rid in (value.get("answers") or {}):
            out[rid] = prov
    return out


def answers_from(files, review, sheets, t):
    """{review id: {field: value}} from the supervisor's answer files: each names its batch and that batch's digest,
    every id of that batch, each field's answer by its option number (or its option text); an id of another batch,
    a number no option has, or a second answer to one id refuses."""
    declared = {n: v for n, v, _txt in batches(review, sheets, t)}
    out = {}
    for value in files:
        if value.get("schema") != ANSWERS_SCHEMA or value.get("batch") not in declared:
            raise ValueError("refused: not an answers file of a declared batch")
        batch = declared[value["batch"]]
        if value.get("batch_sha256") not in (None, batch["sha256"]):
            raise ValueError("refused: the answers are of another version of this batch")
        options = {item["id"]: item["options"] for item in batch["items"]}
        for rid, answer in (value.get("answers") or {}).items():
            if rid not in options or rid in out:
                raise ValueError("refused: an answer names an id outside its batch, or one id twice")
            got = {}
            for field, choice in answer.items():
                opts = options[rid].get(field)
                if opts is None:
                    raise ValueError("refused: an answer names a field the position does not ask")
                key = str(choice).strip()
                if key.isdigit():          # a number is always an option number (a wording "1" is option 2)
                    if key not in opts:
                        raise ValueError("refused: an answer is not one of the numbered options")
                    got[field] = opts[key]
                elif key in opts.values():
                    got[field] = key
                else:
                    raise ValueError("refused: an answer is not one of the numbered options")
            out[rid] = got
    return out


def as_label(answer, t):
    """His answer in the labels file's form, or None when a field is missing."""
    if not all(k in answer for k in ("article", "wording", "stance")):
        return None
    return {"article": answer["article"], "proposal": None if answer["wording"] == t["whole"] else int(answer["wording"]),
            "stance": answer["stance"], "red_line": bool(t["firm_values"].get(answer.get("firm_limit", "no"), False))}


def _zero():
    return {"drawn": 0, "answered": 0, "agree_all": 0, "agree_stance": 0, "changed": 0, "labeller_had_none": 0}


def read(review, answer_files, labels, sheets, t, conditional=None):
    """(counts, merged labels by set): agreement on the random group, how many of the low group changed; his
    label replaces the labeller's on the low group only. Counts, never a label. D-745: `groups` counts his BLIND
    answers only (the unbiased figure); answers of any other provenance are counted under `by_provenance` and never
    pooled into `groups`; `positions_by_provenance` counts the answered positions of each."""
    given = answers_from(answer_files, review, sheets, t)
    prov = provenance_of(answer_files)
    counts = {g: _zero() for g in GROUPS}
    by_prov = {p: {g: _zero() for g in GROUPS} for p in PROVENANCES}
    merged = json.loads(json.dumps(labels))
    for row in review["rows"]:
        his = as_label(given.get(row["review_id"], {}), t)
        p = prov.get(row["review_id"], BLIND)
        c = counts[row["group"]] if p == BLIND else by_prov[p][row["group"]]
        if p == BLIND:
            c["drawn"] += 1
        by_prov[p][row["group"]]["drawn"] += int(p != BLIND)
        if his is None:
            continue
        c["answered"] += 1
        olmo = labels.get(row["set"], {}).get(row["item_id"], {}).get(row["position_id"])
        if olmo is None:
            c["labeller_had_none"] += 1
        same = olmo == his
        c["agree_all"] += int(same)
        c["agree_stance"] += int(olmo is not None and olmo["stance"] == his["stance"])
        c["changed"] += int(not same)
        if row["group"] == "low":
            merged.setdefault(row["set"], {}).setdefault(row["item_id"], {})[row["position_id"]] = his
    by_prov[BLIND] = counts
    out = {"schema": COUNTS_SCHEMA, "seed": review["seed"], "pool": review["pool"], "groups": counts,
           "groups_are": "blind answers only (D-745); other provenances under by_provenance, never pooled",
           "by_provenance": by_prov,
           "positions_by_provenance": {p: sum(by_prov[p][g]["answered"] for g in GROUPS) for p in PROVENANCES},
           # D-745 (all five random batches suggested and approved, 17:48): with no blind answer there is no blind
           # figure, said so in the record, never a zero read as one.
           "blind_figure": ("none: no answer is blind; every answered position is %s"
                            % "/".join(p for p in PROVENANCES if p != BLIND and by_prov[p]["random"]["answered"]
                                       + sum(by_prov[p][g]["answered"] for g in GROUPS if g != "random"))
                            if not any(counts[g]["answered"] for g in GROUPS)
                            else "groups: %d blind answers" % sum(counts[g]["answered"] for g in GROUPS)),
           "answers_sha256": _sha(json.dumps(given, sort_keys=True)), "batches_answered": len(answer_files),
           # D-748: the supervisor's list of conditional acceptances, carried by count alone (optional; absent is None).
           "conditional_items": None if conditional is None else len(conditional),
           "read_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "note": "counts only: agreement on the random group, changes on the low group; no item id or label"}
    return out, merged


def _write(path, value):
    path = ns.na.outside_repository(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError("refused: %s exists already (nothing is overwritten)" % path.name)
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10) * 2)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw")
    b = sub.add_parser("batches")
    r = sub.add_parser("read")
    for q in (d, b, r):
        q.add_argument("--sheets", action="append", required=True)
    d.add_argument("--labels", action="append", default=[])
    r.add_argument("--labels", action="append", required=True)
    d.add_argument("--confidence", action="append", default=[])
    d.add_argument("--random-only", action="store_true",
                   help="the uniform group alone, before the labeller runs (Seckin 16:45); no labels needed")
    d.add_argument("--after", default=None, help="the recorded random draw: take it unchanged and exclude it")
    d.add_argument("--random2", type=int, default=None,
                   help="with --after the first random record: N more drawn uniformly now, before the labeller")
    d.add_argument("--counts", default=None, help="with --random-only: a counts-only record for the lead")
    d.add_argument("--seed", type=int, default=None)
    d.add_argument("--random", type=int, default=50)
    d.add_argument("--low", type=int, default=150)
    d.add_argument("--out", required=True)
    for q in (b, r):
        q.add_argument("--review", required=True)
    b.add_argument("--out-dir", required=True)
    r.add_argument("--answers-dir", required=True)
    r.add_argument("--counts", required=True)
    r.add_argument("--merged-dir", required=True)
    r.add_argument("--conditional", default=None,
                   help="the supervisor's conditional_items.json (D-748, optional): carried by count alone")
    args = ap.parse_args(argv)
    cfg = ns.load_config()
    t = nsl.load_template(cfg)
    sheets = _sheets(args.sheets)
    if args.cmd == "draw":
        if args.random2 is not None:
            if args.labels or args.confidence or args.random_only or not args.after:
                raise SystemExit("refused: --random2 takes the first random record (--after) and the sheets alone")
            prior = json.loads(Path(args.after).read_text(encoding="utf-8"))
            value = draw_random2(sheets, prior, n=args.random2)
            _write(Path(args.out), value)
            shown = {k: value[k] for k in ("seed", "pool", "random", "random2", "asked", "short", "remaining_after",
                                           "drawn_sha256")}
            if args.counts:
                _write(Path(args.counts), dict(shown, schema="neg-synth-review-random2-counts-v1",
                                               drawn_at=value["drawn_at"], note="counts, the seed and a digest only"))
            print(json.dumps(shown, sort_keys=True))
            return 0
        if args.random_only:
            if args.labels or args.confidence or args.after:
                raise SystemExit("refused: --random-only reads the sheets alone")
            value = draw_random(sheets, seed=args.seed, n_random=args.random)
            _write(Path(args.out), value)
            shown = {k: value[k] for k in ("seed", "pool", "random", "drawn_sha256")}
            if args.counts:
                _write(Path(args.counts), dict(shown, schema="neg-synth-review-random-counts-v1",
                                               drawn_at=value["drawn_at"], note="counts, the seed and a digest only"))
            print(json.dumps(shown, sort_keys=True))
            return 0
        if not args.labels or not args.confidence:
            raise SystemExit("refused: the draw after the labeller needs its labels and confidence")
        labels, confidence = _by_set(args.labels, sets=sheets), _by_set(args.confidence, "confidence")
        if args.after:
            prior = json.loads(Path(args.after).read_text(encoding="utf-8"))
            value = draw_after(sheets, labels, confidence, prior, n_low=args.low)
        else:
            value = draw(sheets, labels, confidence, seed=args.seed, n_random=args.random, n_low=args.low)
        _write(Path(args.out), value)
        print(json.dumps({k: value[k] for k in ("seed", "pool", "random", "low")}, sort_keys=True))
        return 0
    review = json.loads(Path(args.review).read_text(encoding="utf-8"))
    if review.get("schema") in RECORD_GROUPS and args.cmd == "batches":
        review = dict(review, rows=prior_rows(review, sheets))
    elif review.get("schema") != REVIEW_SCHEMA:
        raise SystemExit("refused: not a review set")
    if args.cmd == "batches":
        written, kept = batches(review, sheets, t), 0
        for number, value, text in written:
            target = Path(args.out_dir) / ("SYNLAB1_batch_%02d.json" % number)
            if target.is_file():
                # A batch written before (the random group, Seckin 16:45) is kept when it is the same batch.
                if json.loads(target.read_text(encoding="utf-8")).get("sha256") != value["sha256"]:
                    raise SystemExit("refused: batch %d was written before with other positions" % number)
                kept += 1
                continue
            _write(target, value)
            _write(target.with_suffix(".txt"), text + chr(10))
        print(json.dumps({"batches": len(written), "kept": kept, "positions": len(review["rows"])}, sort_keys=True))
        return 0
    files = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(Path(args.answers_dir).glob("*.json"))
             if f.name != CONDITIONAL_FILE]
    conditional = None
    if args.conditional and Path(args.conditional).is_file():
        value = json.loads(Path(args.conditional).read_text(encoding="utf-8"))
        conditional = value if isinstance(value, list) else (value.get("items") if isinstance(value, dict) else None)
        if not isinstance(conditional, list):
            raise SystemExit("refused: conditional_items.json is not a list of items (D-748)")
    counts, merged = read(review, files, _by_set(args.labels, sets=sheets), sheets, t, conditional=conditional)
    _write(Path(args.counts), counts)
    for name, value in merged.items():
        _write(Path(args.merged_dir) / ("labels_%s_reviewed.json" % name), value)
    print(json.dumps({g: {k: counts["groups"][g][k] for k in ("drawn", "answered", "agree_all", "changed")}
                      for g in GROUPS}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
