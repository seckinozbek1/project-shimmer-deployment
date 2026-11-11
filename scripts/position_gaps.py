"""The gap between the parties on an issue, round by round, in Python (D-S46 item 2, D-319).

A computed movement means one thing only: the same sentence with only the figure changed. Two
parties' quotes on an issue in a round are compared only when they are identical as written
(whitespace collapsed, case kept) except for the one figure each holds, and two consecutive rounds
only when all four quotes are that one sentence. Then the gap between the parties is computed in each
round, and one `trajectory` record says what it did, in the relation names of INFRA-044:
`moved_toward` when it narrows, `moved_away` when it widens, `unchanged_from_prior` when it stays
within the arithmetic tolerance. The record is the multi-round case's own typed record
(multi_round.KINDS: a trajectory has both parties as participants and evidence from each in both
rounds); nothing is added to the Finding record.

Why one rule and no reading of units: three rounds of an independent checker found that every rule
reading a window of words around a figure could be made to call two measures equal when they are
not ("The monthly rent is 9,000 credits." against "The yearly rent is 108,000 credits.", "9,000
credits, per month", "Per month 9,000 credits", a measure in brackets, after a dash, in the next sentence), each a
confident wrong record. Where the whole sentence is the same, whatever it says the figure measures,
it says of both figures. Everything else is refused as `quotes_differ_outside_figure`: one measure
read as two only refuses, and that cost is accepted. No word is named in code and none is read.

Nothing is carried forward: a party that states nothing on the issue in a round leaves that pair
not computed, as multi_round.project never carries a position forward. With more than two parties
stating an issue, Python does not choose which two to compare. `outcomes` says, for every declared
issue and pair of consecutive rounds, what was computed or why not.
"""
import hashlib
import json

import paired_review

WRITTEN_BY = "python"
# Stands for the figure in a quote's comparison form. A NUL cannot be written in a quote, so no
# text a party wrote can equal it.
FIGURE = "\x00"
# How the comparison form is shown to a reader.
SHOWN_FIGURE = "[figure]"


def sentence(text):
    """(form, value) of a quote holding one figure: the quote with that figure's number replaced
    by FIGURE and every run of whitespace collapsed to one space, case kept; or (None, why):
    `a_position_in_words` (no figure) or `several_figures` (more than one, so Python does not
    choose which is the position). A currency sign or code stays in the form, as written."""
    text = str(text or "")
    found = [m for m in paired_review._QUANTITY.finditer(text) if paired_review.norm_number(m.group("num")) is not None]
    if not found:
        return None, "a_position_in_words"
    if len(found) > 1:
        return None, "several_figures"
    m = found[0]
    start, end = m.span("num")
    return " ".join((text[:start] + FIGURE + text[end:]).split()), paired_review.norm_number(m.group("num"))


def shown(form):
    """A comparison form as a reader sees it."""
    return form.replace(FIGURE, SHOWN_FIGURE)


def declared_figure(text, unit):
    """(value, None) of a quote holding one figure with the issue's declared unit standing right
    after it, as declared (spacing between them, case kept, the unit ending at a word's edge); or
    (None, why): `a_position_in_words`, `several_figures` (any second figure is another measure),
    `not_the_declared_unit` (whatever follows the figure is not the declared unit as written)."""
    text = str(text or "")
    found = [m for m in paired_review._QUANTITY.finditer(text) if paired_review.norm_number(m.group("num")) is not None]
    if not found:
        return None, "a_position_in_words"
    if len(found) > 1:
        return None, "several_figures"
    m = found[0]
    if m.group("sym") or m.group("code"):
        return None, "not_the_declared_unit"
    rest = text[m.end("num"):]
    gap = len(rest) - len(rest.lstrip(" \t\u00a0\u202f"))
    after = rest[gap:]
    if not after.startswith(unit) or (after[len(unit):len(unit) + 1].isalnum()):
        return None, "not_the_declared_unit"
    return paired_review.norm_number(m.group("num")), None


def declared_unit(manifest, issue_id):
    """The unit the case manifest declares for an issue (multi_round.declared_unit), else None."""
    issue = next((i for i in manifest.get("issues", []) if i.get("issue_id") == issue_id), {})
    return issue.get("unit")


def _record_id(*parts):
    readable = ".".join(("trajectory",) + parts)
    import multi_round as mr
    if mr.identifier(readable):
        return readable
    return "trajectory." + hashlib.sha256(json.dumps(parts).encode("utf-8")).hexdigest()[:32]


def _stated(positions, round_id, issue_id):
    """{actor: position} of the accepted positions on an issue in a round."""
    return {p["actor_id"]: p for p in positions
            if p["round_id"] == round_id and p["issue_id"] == issue_id and p["state"] == "accepted"}


# The order in which a pair's reasons are reported when both parties' positions fail.
_WHY_ORDER = ("a_position_in_words", "several_figures")
_DECLARED_WHY_ORDER = ("a_position_in_words", "several_figures", "not_the_declared_unit")


def same_sentence(form_a, form_b):
    """Two comparison forms are one sentence with only the figure changed. The one test, used at both
    levels: a gap's two quotes in one round, and a movement's two rounds (so all four quotes)."""
    return form_a == form_b


def _gap(stated, unit=None):
    """(gap, form, [actor, ...]) of two parties' figures in one round, or (None, why, None). With a
    declared unit, each quote's one figure is read against it and the form is the unit; without,
    the two quotes must be the same sentence with only the figure changed."""
    if len(stated) < 2:
        return None, "a_party_states_nothing", None
    if len(stated) > 2:
        return None, "more_than_two_parties", None
    actors = sorted(stated)
    if unit is not None:
        read = [declared_figure(stated[a].get("position", ""), unit) for a in actors]
        failed = [why for value, why in read if value is None]
        if failed:
            return None, min(failed, key=_DECLARED_WHY_ORDER.index), None
        (a, _), (b, _) = read
        return abs(a - b), unit, actors
    read = [sentence(stated[a].get("position", "")) for a in actors]
    failed = [why for form, why in read if form is None]
    if failed:
        return None, min(failed, key=_WHY_ORDER.index), None
    (form_a, a), (form_b, b) = read
    if not same_sentence(form_a, form_b):
        return None, "quotes_differ_outside_figure", None
    return abs(a - b), form_a, actors


def rounds_agree(form_before, form_now):
    """A movement compares two gaps, so it rests on four quotes: each round's two already agree, and
    this asks that the two rounds' sentences agree too."""
    return same_sentence(form_before, form_now)


def relation(before, now):
    """The INFRA-044 relation of a gap that went from `before` to `now`."""
    if paired_review._close(before, now):
        return "unchanged_from_prior"
    return "moved_toward" if now < before else "moved_away"


def gaps(manifest, positions):
    """(trajectory records, outcome rows). One outcome row per declared issue and pair of
    consecutive rounds; a record for each row that could be computed."""
    rounds = [r["round_id"] for r in sorted(manifest["rounds"], key=lambda r: r["sequence"])]
    records, rows = [], []
    for issue in [i["issue_id"] for i in manifest["issues"]]:
        unit = declared_unit(manifest, issue)
        for previous, current in zip(rounds, rounds[1:]):
            row = {"issue_id": issue, "rounds": [previous, current], "written_by": WRITTEN_BY, "provenance": "computed",
                   "read_by": "declared_unit" if unit is not None else "same_sentence"}
            rows.append(row)
            before_stated, now_stated = _stated(positions, previous, issue), _stated(positions, current, issue)
            before, form_before, actors_before = _gap(before_stated, unit)
            now, form_now, actors_now = _gap(now_stated, unit)
            if before is None or now is None:
                row["outcome"] = "not_computed"
                row["why"] = (form_before if before is None else form_now) + (
                    "_in_" + (previous if before is None else current))
                continue
            if actors_before != actors_now:
                row.update(outcome="not_computed", why="different_parties")
                continue
            if not rounds_agree(form_before, form_now):
                row.update(outcome="not_computed", why="quotes_differ_outside_figure_between_%s_and_%s" % (previous, current))
                continue
            kind = relation(before, now)
            stated = [before_stated[a] for a in actors_before] + [now_stated[a] for a in actors_now]
            form = unit if unit is not None else shown(form_before)
            reading = ("in %s, the unit declared for the issue" % unit if unit is not None else
                       "all four quotes reading \"%s\" with only the figure changed" % form)
            record = {"record_id": _record_id(previous, current, issue), "case_id": manifest["case_id"],
                      "kind": "trajectory", "state": "accepted", "category": "observed_evidence",
                      "confidence": "CONFIDENT", "actor_id": actors_before[0], "actor_ids": list(actors_before),
                      "issue_id": issue, "round_id": current, "previous_round_id": previous,
                      "relation": kind, "gap_before": before, "gap_now": now, "measure": form,
                      "figures": [(declared_figure(p.get("position", ""), unit)[0] if unit is not None
                                   else sentence(p.get("position", ""))[1]) for p in stated],
                      "read_by": row["read_by"],
                      "figure_actors": [p["actor_id"] for p in stated],
                      "figure_rounds": [p["round_id"] for p in stated],
                      "position_ids": [p.get("record_id") for p in stated],
                      "source_ids": [s for p in stated for s in p["source_ids"]],
                      "ref_ids": [r for p in stated for r in p["ref_ids"]],
                      "text": "the gap between %s on %s went from %g in %s to %g in %s, %s" % (
                          " and ".join(actors_before), issue, before, previous, now, current, reading),
                      "written_by": WRITTEN_BY, "provenance": "computed"}
            record.update(item_id=record["record_id"], revision=1, ref=record["record_id"])
            records.append(record)
            row.update(outcome=kind, gaps=[before, now], measure=form, record_id=record["record_id"])
    return records, rows


def figures_in_gaps(records, rows, positions):
    """{position record id: (value, form) or (None, why)}: a position carries a figure only when it
    takes part in a computed gap; otherwise the reason its first pair of rounds was not computed."""
    out = {}
    for record in records:
        for pid, value in zip(record["position_ids"], record["figures"]):
            out[pid] = (value, record["measure"])
    for p in positions:
        if p.get("record_id") in out:
            continue
        why = next((r.get("why") for r in rows if r["issue_id"] == p["issue_id"] and p["round_id"] in r["rounds"]
                    and r["outcome"] == "not_computed"), None)
        out[p.get("record_id")] = (None, why or "not_in_a_computed_gap")
    return out
