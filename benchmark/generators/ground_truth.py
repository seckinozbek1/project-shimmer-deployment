"""Ground-truth scanners: the planted flaws that Python does not compute, found again by
this package's own code in the rendered text (D-042).

The figure audit (audit.py) finds every comparison Python would make. Some planted
flaws are flaws whether or not Python computes them: a figure written in another
measure than its rule or reference table uses, a rate applied wrongly, a copied figure
that differs from its source unit, a carried figure that differs from the unit before,
a window or fee band that lives only in a distant definition. Each family declares how
to find its own such flaws in the key's `ground_truth_checks` (the scorer ignores it),
and `scan` finds EVERY instance in a parsed document. The validator requires the
instances to equal the keyed entries of those kinds exactly, so a flaw dropped from the
key is caught, and a twin that still carries one is caught (a twin keys none).

Nothing here imports Shimmer, and nothing here models what Shimmer computes.
"""
import datetime

from . import textrules as tr


def _units(res):
    return [u for u in res["doc"]["units"] if not u["preamble"]]


def _line(u, label):
    for ln in u["lines"]:
        if ln["norm"] == label:
            return ln
    return None


def _figure(u, label):
    ln = _line(u, label)
    if ln is not None and ln["kind"][0] == "figure":
        return ln["kind"][1], ln["kind"][2]
    return None


def _column(u, label):
    for t in u["tables"]:
        for c, hd in enumerate(t["headers"]):
            if hd["norm"] == label:
                return t, c
    return None


def _factor(conversions, frm, to):
    for a, b, f in conversions:
        if a == frm and b == to:
            return f
    return None


def _entry(unit, rule, relation, kind, field, a, b, **extra):
    e = {"unit": unit, "rule": rule, "relation": relation, "kind": kind,
         "claim": {"relation": relation, "field_label": field, "value_a": tr.r6(a), "value_b": tr.r6(b)}}
    for k in ("unit_a", "unit_b"):
        if k in extra:
            e["claim"][k] = extra.pop(k)
    e.update(extra)
    return e


def _band_row(res, u, band):
    """The reference-table range a unit matches for one band column (section 7 row
    matching: key-cell words inside the unit's value words, most words wins, a tie
    refused); None when there is none."""
    t, c = band["table"], band["col"]
    cands = []
    for row in t["rows"]:
        kw = set()
        for k in band["keys"]:
            if row[k][0] == "text":
                kw.update(tr.words(row[k][1]))
        if kw and kw <= u["value_words"] and row[c][0] == "range":
            cands.append((len(kw), row[c][1]))
    if not cands:
        return None
    top = max(n for n, _ in cands)
    best = [r for n, r in cands if n == top]
    return best[0] if len(best) == 1 else None


def _scan_measure(res, chk):
    out = []
    conv = chk["conversions"]
    for u in _units(res):
        for ln in u["lines"]:
            if ln["kind"][0] != "figure":
                continue
            v, m = ln["kind"][1], ln["kind"][2]
            lw = set(ln["norm"].split())
            for t in u["tables"]:
                for hd in t["headers"]:
                    f = _factor(conv, m, hd["measure"]) if hd["measure"] else None
                    if f and set(hd["norm"].split()) < lw and tr.measure_powers(m) != hd["powers"]:
                        out.append(_entry(u["id"], chk["rule_for"]["column"], "unit_mismatch", chk["kind"],
                                          ln["norm"], v, v * f, unit_a=m, unit_b=hd["measure"],
                                          compared_with="column"))
            for band in res.get("bands", []):
                hd = band["table"]["headers"][band["col"]]
                f = _factor(conv, m, hd["measure"])
                if f and tr.measure_powers(m) != hd["powers"] and _band_row(res, u, band) is not None:
                    out.append(_entry(u["id"], chk["rule_for"]["reference"], "unit_mismatch", chk["kind"],
                                      ln["norm"], v, v * f, unit_a=m, unit_b=hd["measure"],
                                      compared_with="reference"))
    return out


def _scan_rate(res, chk):
    out = []
    for u in _units(res):
        rate, base, got = (_figure(u, chk[k]) for k in ("rate", "base", "result"))
        if not (rate and base and got) or rate[1] != "%":
            continue
        want = tr.r6(rate[0] * base[0] / 100.0)
        if not tr.same(want, got[0]):
            out.append(_entry(u["id"], chk["rule"], "rate_mismatch", chk["kind"], chk["result"], want, got[0]))
    return out


def _scan_copy(res, chk):
    out = []
    by_heading = {u["heading"]: u for u in _units(res)}
    for u in _units(res):
        kc, vc = _column(u, chk["key_column"]), _column(u, chk["column"])
        if kc is None or vc is None or kc[0] is not vc[0]:
            continue
        t, n = vc[0], 0
        for row in t["rows"]:
            cell = row[vc[1]]
            if cell[0] != "number":
                continue
            n += 1
            key = row[kc[1]]
            src = by_heading.get(key[1]) if key[0] == "text" else None
            fig = _figure(src, chk["source_label"]) if src is not None else None
            if fig is not None and not tr.same(fig[0], cell[1]):
                out.append(_entry(u["id"], chk["rule"], "copy_mismatch", chk["kind"],
                                  "%s row%d" % (chk["column"], n), fig[0], cell[1], source_unit=src["id"]))
    return out


def chain(u, closing, column):
    """(rows of the carried column, stated closing figure) of one count, or None."""
    st = _figure(u, closing)
    col = _column(u, column)
    if st is None or col is None:
        return None
    rows = [row[col[1]][1] for row in col[0]["rows"] if row[col[1]][0] == "number"]
    return (rows, st[0]) if rows else None


def _scan_carry(res, chk):
    out = []
    units = _units(res)
    for p_u, q_u in zip(units, units[1:]):
        p, q = chain(p_u, chk["closing"], chk["column"]), chain(q_u, chk["closing"], chk["column"])
        if p is None or q is None or not tr.same(sum(q[0]), q[1]):
            continue
        if not tr.same(q[0][0], p[1]) and not tr.same(q[0][0], tr.r6(sum(p[0]))):
            out.append(_entry(q_u["id"], chk["rule"], "carry_mismatch", chk["kind"],
                              "%s row1" % chk["column"], p[1], q[0][0], depends_on_unit=p_u["id"]))
    return out


def _definition(res, chk, term):
    for u in _units(res):
        ln = _line(u, chk["term_label"])
        if ln is not None and ln["value"] == term:
            return u
    return None


def _scan_far_window(res, chk):
    out = []
    for first, second, term, rule, kind in chk["pairs"]:
        d = _definition(res, chk, term)
        bound = _figure(d, chk["bound_label"]) if d is not None else None
        for u in _units(res):
            a, b = _line(u, first), _line(u, second)
            if a is None or b is None or a["kind"][0] != "date" or b["kind"][0] != "date" or bound is None:
                continue
            gap = abs((datetime.date(*b["kind"][1]) - datetime.date(*a["kind"][1])).days)
            if gap > bound[0]:
                out.append(_entry(u["id"], rule, "date_window", kind, first, gap, bound[0],
                                  related_unit=d["id"]))
    return out


def _scan_far_fee(res, chk):
    out = []
    d = _definition(res, chk, chk["term"])
    col = _column(d, chk["table_column"]) if d is not None else None
    cls_col = _column(d, chk["class"]) if d is not None else None
    if col is None or cls_col is None:
        return out
    ranges = {row[cls_col[1]][1]: row[col[1]][1] for row in col[0]["rows"]
              if row[cls_col[1]][0] == "text" and row[col[1]][0] == "range"}
    for u in _units(res):
        fee, cls = _figure(u, chk["fee"]), _line(u, chk["class"])
        if fee is None or cls is None or cls["value"] not in ranges:
            continue
        lo, hi = ranges[cls["value"]]
        if fee[0] > hi:
            out.append(_entry(u["id"], chk["rule"], "above_band", chk["kinds"]["above"], chk["fee"],
                              fee[0], hi, related_unit=d["id"]))
        elif fee[0] < lo:
            out.append(_entry(u["id"], chk["rule"], "below_band", chk["kinds"]["below"], chk["fee"],
                              fee[0], lo, related_unit=d["id"]))
    return out


SCANNERS = {"measure": _scan_measure, "rate": _scan_rate, "copy": _scan_copy, "carry": _scan_carry,
            "far_window": _scan_far_window, "far_fee": _scan_far_fee}
LINKS = ("depends_on_unit", "source_unit", "related_unit")


def kinds(checks):
    """The planted kinds the scanners find (every other kind is the audit's)."""
    out = set()
    for chk in checks or ():
        if "kind" in chk:
            out.add(chk["kind"])
        for p in chk.get("pairs", ()):
            out.add(p[4])
        out.update((chk.get("kinds") or {}).values())
    return out


def scan(res, checks, ordered=True):
    """Every ground-truth instance in an audited document. `ordered` False skips the
    checks that read reading order (the reordered-sections probe moves blocks)."""
    out = []
    for chk in checks or ():
        if chk["check"] == "carry" and not ordered:
            continue
        out.extend(SCANNERS[chk["check"]](res, chk))
    return out


def signature(e):
    c = e.get("claim") or {}
    return (e.get("unit"), e.get("rule"), e.get("relation"), e.get("kind"), c.get("field_label"),
            repr(tr.r6(c.get("value_a", 0))), repr(tr.r6(c.get("value_b", 0))),
            c.get("unit_a"), c.get("unit_b")) + tuple(e.get(k) for k in LINKS)
