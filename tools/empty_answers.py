"""Empty answers: tagged, counted, listed by item id, and checked again at the next run (beta list item 17).

The operator's rule (Seckin, 23 November 2026): "boş cevap olmamalı ama olursa boş diye taglemeliyiz, bir sonraki
validation/pilotta düzelip düzelmediğine bakmalıyız" (there should be no empty answer; if there is one it is tagged
empty, and the next validation or pilot checks whether it was fixed). This module is the one reading of that rule
for every scorer; it changes no score. A scorer decides, by its own existing rule, which items the system left
without an answer (tools/coverage_check.py: any basis outside its ANSWERED; the negotiation scorer: a proposal
M10 reads as no_answer, by its reason). Each such item becomes one entry here:

    {"item_id": ..., "sub_id": <proposal id or null>, "tag": "empty", "reason": <the scorer's own reason>}

`summary` gives the counts a score report prints (count, share, by reason; no id). `listing` is the file a scorer
writes beside its report, the only place item ids appear: every empty entry and every key the run scored, so the
next run can tell an item now answered from one not in that run. `recheck` reads a previous listing against the
current run: for each previously empty key `now_answered`, `still_empty` or `not_in_this_run`.

    py -3.12 -X utf8 tools/empty_answers.py recheck PREVIOUS.json CURRENT.json [--out REPORT.json]

prints the counts by status and exits 0; it writes the per-item statuses to --out only. Exit 2: a file is not a
listing of this schema.

The negotiation scorer is never edited: tools/score_neg_advisor.py's own SHA-256 is pinned in every power record
(code_sha256), so any edit would refuse them. `negotiation_report` calls its report() unchanged and, while it runs,
records each (arm, item, reply) its item_parts receives, reading each proposal with the scorer's own
open_point_prediction; the report it returns is the scorer's, unchanged. The CLI wraps `score` the same way:

    py -3.12 -X utf8 tools/empty_answers.py neg-score [--empty-list PATH] [--recheck OLD] -- score <its args>

runs score_neg_advisor's main unchanged (its report printed as before), then prints one line of empty counts per
arm (no id) and writes the listings by arm (ids) to PATH, which must be inside the --set folder, as --per-item-out
is. Standard library only, except that neg-score and negotiation_report import the scorer.
"""
import json
import sys
from pathlib import Path

TAG = "empty"
LABEL_TR = "boş"            # the operator's word, for output written for him in Turkish
SCHEMA = "empty-answers-v1"
NOW_ANSWERED, STILL_EMPTY, NOT_IN_THIS_RUN = "now_answered", "still_empty", "not_in_this_run"
STATUSES = (NOW_ANSWERED, STILL_EMPTY, NOT_IN_THIS_RUN)


def key_of(item_id, sub_id=None):
    """The comparison key of one scored piece: the item id, and the proposal id when the scorer scores pieces."""
    return "%s|%s" % (item_id, "" if sub_id is None else sub_id)


# Seckin 18:10 (G-20261123-1812) item (c): an answer the system itself withheld as unsupported stays under the
# empty tag but is counted on its own line, apart from plain silence. Withheld: the negotiation scorer's
# `withheld` (a piece the audit found unsupported), a label whose kept claims did not establish a verdict or
# conflict (detection.NOT_ESTABLISHED, detection.CONFLICT) and a leaning alone (D-907). Every other reason
# (no answer, no piece, no stance, silence, a failed or excluded run) is silence.
WITHHELD, SILENCE = "withheld", "silence"
KINDS = (WITHHELD, SILENCE)
WITHHELD_REASONS = ("withheld", "dev_not_established", "dev_conflict", "leaning_only")


def kind_of(reason):
    return WITHHELD if str(reason).split("/")[0] in WITHHELD_REASONS else SILENCE


def entry(item_id, reason, sub_id=None):
    return {"item_id": str(item_id), "sub_id": None if sub_id is None else str(sub_id), "tag": TAG,
            "reason": str(reason), "kind": kind_of(reason)}


def summary(entries, scored):
    """Counts for a score report: no item id. `scored` is the number of pieces the run scored."""
    by_reason, by_kind = {}, {k: 0 for k in KINDS}
    for e in entries:
        by_reason[e["reason"]] = by_reason.get(e["reason"], 0) + 1
        by_kind[kind_of(e["reason"])] += 1
    return {"tag": TAG, "label_tr": LABEL_TR, "count": len(entries), "scored": scored,
            "share": round(len(entries) / scored, 4) if scored else None,
            "items": len({e["item_id"] for e in entries}), "by_kind": by_kind,
            "by_reason": dict(sorted(by_reason.items()))}


def kind_lines(s):
    """The two printed lines of item (c), from a summary."""
    return ["%s (%s), withheld by the system as unsupported: %d" % (TAG, LABEL_TR, s["by_kind"][WITHHELD]),
            "%s (%s), silence (no answer given): %d" % (TAG, LABEL_TR, s["by_kind"][SILENCE])]


def both_figures(correct, answered, items):
    """Item (a): the main figure over the answered items and the figure that counts each empty answer as wrong,
    from the scorer's own count of right answers. Only for a share of right answers (accuracy): a figure like
    macro-F1 is not a count over items and is not rescaled here."""
    return {"main": round(correct / answered, 4) if answered else None,
            "blanks_counted_wrong": round(correct / items, 4) if items else None,
            "correct": correct, "answered": answered, "items": items}


def figures_line(f):
    return ("main figure %s (%d of %d answered right) | blanks counted wrong %s (%d of %d)"
            % (f["main"], f["correct"], f["answered"], f["blanks_counted_wrong"], f["correct"], f["items"]))


# The negotiation scorer already scores an unanswered proposal as no_answer, always wrong (item_parts), so its
# figures are the blanks-counted-wrong figures; the report prints that figure in both places, named so.
NEG_FIGURES = ("M1", "M10", "M4")
DEFAULT_NEG_LISTING = "empty_answers.json"


def neg_both_figures(report):
    """{arm: {figure: {main, blanks_counted_wrong}}} of a negotiation report's figures (the same value: the
    scorer counts a blank as wrong)."""
    out = {}
    for arm, figs in sorted((report.get("figures") or {}).items()):
        for f in NEG_FIGURES:
            cell = figs.get(f) or {}
            est = cell.get("estimate") if isinstance(cell, dict) else cell
            out.setdefault(arm, {})[f] = {"main": est, "blanks_counted_wrong": est}
    return out


def listing(measure, entries, scored_keys, *, run=None):
    """The file written beside a score report: every empty entry by id, and every key the run scored."""
    return {"schema": SCHEMA, "measure": str(measure), "run": run, "tag": TAG, "label_tr": LABEL_TR,
            "empty": sorted(entries, key=lambda e: (e["item_id"], e["sub_id"] or "")),
            "scored_keys": sorted(set(scored_keys)), "summary": summary(entries, len(set(scored_keys)))}


def read_listing(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("empty"), list):
        raise ValueError("not an empty-answers listing")
    return data


def recheck(previous, current):
    """{'counts': {status: n}, 'items': [entry with status]} for each key empty in `previous`, read in `current`
    (both listings). A key the current run scored and did not tag empty is now answered."""
    now_empty = {key_of(e["item_id"], e.get("sub_id")) for e in current.get("empty") or []}
    scored = set(current.get("scored_keys") or [])
    counts, items = {s: 0 for s in STATUSES}, []
    for e in previous.get("empty") or []:
        k = key_of(e["item_id"], e.get("sub_id"))
        status = STILL_EMPTY if k in now_empty else NOW_ANSWERED if k in scored else NOT_IN_THIS_RUN
        counts[status] += 1
        items.append(dict(e, status=status))
    return {"previous_run": previous.get("run"), "measure": current.get("measure"), "counts": counts,
            "items": items}


def recheck_listings(previous, listed):
    """{arm: counts by status} of each arm's previously empty pieces read in this run (an arm absent from either
    side skipped; the synthetic block per arm as `synthetic:<arm>`); each item's status is written into `listed`."""
    out = {}
    for arm, cur in listed.items():
        if arm == "synthetic":
            for a, c in (cur or {}).items():
                p = ((previous or {}).get("synthetic") or {}).get(a)
                if p:
                    c["recheck"] = recheck(p, c)
                    out["synthetic:" + a] = c["recheck"]["counts"]
        elif (previous or {}).get(arm):
            cur["recheck"] = recheck(previous[arm], cur)
            out[arm] = cur["recheck"]["counts"]
    return out


def _scorer():
    root = Path(__file__).resolve().parents[1]
    for p in (str(root / "tools"), str(root / "scripts"), str(root / "benchmark" / "baselines")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import score_neg_advisor
    return score_neg_advisor


class _Recorder:
    """While active, the scorer's replies_by_item marks which arm its report is on (matched by the arm's answers
    and group, else by the arms' order) and its item_parts records that arm's empty pieces. Both wrappers call the
    scorer's own functions and return their results unchanged; the module is restored on exit."""

    def __init__(self, sc, arms):
        self.sc, self.arms, self.arm, self.turn, self.found = sc, list(arms.items()), None, 0, {}

    def __enter__(self):
        self.real_rbi, self.real_parts = self.sc.replies_by_item, self.sc.item_parts
        self.sc.replies_by_item, self.sc.item_parts = self._rbi, self._parts
        return self

    def __exit__(self, *exc):
        self.sc.replies_by_item, self.sc.item_parts = self.real_rbi, self.real_parts
        return False

    def _rbi(self, answers, group, *a, **k):
        same = [n for n, (ans, g) in self.arms if ans is answers and g == group]
        self.arm = same[0] if len(same) == 1 else self.arms[self.turn % len(self.arms)][0]
        self.turn += 1
        return self.real_rbi(answers, group, *a, **k)

    def _parts(self, item, key, reply, *a, **k):
        out = self.real_parts(item, key, reply, *a, **k)
        if not item.get("game") and self.arm is not None:
            given = k.get("given") if k.get("given") is not None else reply
            block = "synthetic" if key.get("synthetic") else "real"
            got = self.found.setdefault(block, {}).setdefault(self.arm, ([], []))
            iid = item.get("item_id")
            for pid in sorted(key.get("proposals") or {}):
                got[1].append(key_of(iid, pid))
                why = self.sc.open_point_prediction(reply, given, pid)[1]
                if why:
                    got[0].append(entry(iid, why, pid))
        return out


def _listings(found):
    listed = {arm: listing("negotiation:" + arm, e, s) for arm, (e, s) in (found.get("real") or {}).items()}
    if found.get("synthetic"):
        listed["synthetic"] = {arm: listing("negotiation:synthetic:" + arm, e, s)
                               for arm, (e, s) in found["synthetic"].items()}
    return listed


def negotiation_report(items, keys, arms, **kw):
    """(report, listings, summaries): score_neg_advisor.report(items, keys, arms, **kw) as it returns it, the
    listings by arm (ids; the synthetic block apart) and the summaries by arm (counts only)."""
    sc = _scorer()
    with _Recorder(sc, arms) as rec:
        rep = sc.report(items, keys, arms, **kw)
    listed = _listings(rec.found)
    return rep, listed, {arm: v["summary"] for arm, v in listed.items() if arm != "synthetic"}


def neg_lines(line):
    """The printed lines per arm: items (a) and (c), counts and where the listing is, never an id."""
    out = []
    for arm, s in sorted(line["empty"].items()):
        for f, v in sorted((line.get("figures") or {}).get(arm, {}).items()):
            out.append("%s %s: main figure %s | blanks counted wrong %s (the scorer counts a blank as wrong)"
                       % (arm, f, v["main"], v["blanks_counted_wrong"]))
        out.append("%s: %s (%s) %d of %d proposals, listed in %s" % (arm, TAG, LABEL_TR, s["count"], s["scored"],
                                                                   line.get("listing")))
        out += ["%s: %s" % (arm, t) for t in kind_lines(s)]
    return out


def neg_score(argv):
    """neg-score [--empty-list PATH] [--recheck OLD] -- score <args>: the scorer's main unchanged, then the listings."""
    if "--" not in argv:
        print(__doc__)
        return 2
    mine, theirs = argv[:argv.index("--")], argv[argv.index("--") + 1:]
    opts = dict(zip(mine[::2], mine[1::2]))
    if (len(mine) % 2 or set(opts) - {"--empty-list", "--recheck"}
            or theirs[:1] != ["score"] or "--set" not in theirs[:-1]):
        print("refused: neg-score takes [--empty-list PATH] [--recheck OLD] -- score ... --set SET ...")
        return 2
    sc = _scorer()
    set_dir = Path(theirs[theirs.index("--set") + 1])
    # D-950 (Seckin 18:10, item b): by default the listing sits in the set folder, beside the per-item rows.
    target = sc.inside_set(Path(opts.get("--empty-list") or set_dir / DEFAULT_NEG_LISTING), set_dir)
    previous = json.loads(Path(opts["--recheck"]).read_text(encoding="utf-8")) if "--recheck" in opts else None
    box, real_report = {}, sc.report

    def recording_report(items, keys, arms, **kw):
        sc.report = real_report
        try:
            rep, box["listed"], _s = negotiation_report(items, keys, arms, **kw)
            box["figures"] = neg_both_figures(rep)
        finally:
            sc.report = recording_report
        return rep
    sc.report = recording_report
    try:
        code = sc.main(theirs)
    finally:
        sc.report = real_report
    if code != 0 or "listed" not in box:
        return code
    listed = box["listed"]
    line = {"empty": {arm: v["summary"] for arm, v in listed.items() if arm != "synthetic"},
            "figures": box.get("figures", {}), "listing": str(target)}
    if previous is not None:
        line["recheck"] = recheck_listings(previous, listed)
    target.write_text(json.dumps(listed, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(line, sort_keys=True, ensure_ascii=False))
    for text in neg_lines(line):
        print(text)
    return 0


def main(argv):
    if argv[:1] == ["neg-score"]:
        return neg_score(argv[1:])
    if len(argv) < 3 or argv[0] != "recheck":
        print(__doc__)
        return 2
    out = None
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
    try:
        previous, current = read_listing(argv[1]), read_listing(argv[2])
    except (OSError, ValueError) as e:
        print("not an empty-answers listing (%s): stop" % type(e).__name__)
        return 2
    result = recheck(previous, current)
    if out:
        Path(out).write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    c = result["counts"]
    print("previously empty (%s) %d: now answered %d, still empty %d, not in this run %d"
          % (TAG, sum(c.values()), c[NOW_ANSWERED], c[STILL_EMPTY], c[NOT_IN_THIS_RUN]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
