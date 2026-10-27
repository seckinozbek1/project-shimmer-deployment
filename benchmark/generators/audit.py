"""The figure audit of INPUT_FORMAT section 7, done by this package's own code.

Reads the RENDERED Markdown (never the family's abstract model), so what is audited
is exactly what Shimmer would read. It implements, from docs/INPUT_FORMAT.md alone:

- units, unit ids and fields (section 2), refusing anything outside the restricted
  subset the generators write (see textrules.classify_value);
- conventions, brackets and directives (sections 3 and 4) and the directive rule of
  section 5 (scope only with requires, every rule names a document label or declares
  a scope, coverage of every unit but the preamble, no [unless: ...]);
- pairing (section 4), and on every paired unit every product, sum and blank-cell
  comparison (section 7, "Figure audit"), every reference-table band and rule-stated
  band with its ratios and the low-side condition (section 7), every date window, and
  every computed absence;
- attribution of each finding to an operator rule (section 9), refusing a winner that
  depends on how the word overlap is counted;
- the change records of section 6 (for two-version tests).

Nothing here imports Shimmer. The arithmetic is plain float arithmetic rounded to six
places, with the section 6 tolerance.
"""
import datetime
import re

from . import textrules as tr

LABEL_LINE = re.compile(r"^\s*(?:[-*+] )?([A-Za-z][A-Za-z0-9 ()/%._-]{1,48}):(.*)$")
HEADING = re.compile(r"^(#{1,6}) (.*)$")
RULE_ID = re.compile(r"CONV-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", re.I)
LIST_START = re.compile(r"^\s*(?:[-*+] |\d+[.)] )")
NL = chr(10)
RENAME_TOLERANCE = 0.02   # the repository-wide rename tolerance of INPUT_FORMAT section 8
BOUND_SENTENCE =re.compile(r"^The [a-z ]+ is \d+ (?:days|hours)\.$")
SEVERITIES = ("required", "recommended", "advisory")


def _paragraphs(lines):
    paras, cur = [], []
    for ln in lines:
        if ln.strip() == "":
            if cur:
                paras.append(cur)
                cur = []
        else:
            cur.append(ln)
    if cur:
        paras.append(cur)
    return paras


def _basic_text_checks(text, name, errors):
    if text.startswith("\ufeff"):
        errors.append("%s: byte-order mark" % name)
    if not tr.is_ascii_clean(text):
        errors.append("%s: not plain ASCII with LF endings" % name)
    if not text.endswith("\n"):
        errors.append("%s: no final newline" % name)
    if "```" in text:
        errors.append("%s: a code fence" % name)


def _split_header(cell):
    m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", cell)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return cell.strip(), ""


def _parse_table(para, name, errors):
    rows = []
    for ln in para:
        if not (ln.startswith("|") and ln.endswith("|")):
            errors.append("%s: a table line that does not start and end with |" % name)
            return None
        rows.append([c.strip() for c in ln[1:-1].split("|")])
    if len(rows) < 3:
        errors.append("%s: a table with no body row" % name)
        return None
    if not all(re.fullmatch(r":?-+:?", c) for c in rows[1]):
        errors.append("%s: a table without a separator row" % name)
        return None
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        errors.append("%s: a table with uneven rows" % name)
        return None
    headers = []
    for cell in rows[0]:
        label, measure = _split_header(cell)
        if measure and not re.fullmatch(r"[A-Za-z%][A-Za-z0-9/%*-]{0,15}", measure):
            errors.append("%s: header measure %r is not compact" % (name, measure))
        if re.search(r"\d", measure):
            errors.append("%s: a digit in header measure %r" % (name, measure))
        if not tr.norm(label):
            errors.append("%s: header %r normalises to nothing" % (name, cell))
        headers.append({"raw": label, "norm": tr.norm(label), "measure": measure,
                        "powers": tr.measure_powers(measure)})
    body = []
    for r in rows[2:]:
        cells = []
        for c in r:
            k = tr.classify_cell(c)
            if k[0] == "bad":
                errors.append("%s: %s" % (name, k[1]))
            cells.append(k)
        body.append(cells)
    return {"headers": headers, "rows": body,
            "size": sum(len(ln) + 1 for ln in para), "lines": list(para)}


def parse_document(text, name):
    """Units and fields of one document, in the restricted subset."""
    errors = []
    _basic_text_checks(text, name, errors)
    lines = text.split("\n")
    if not lines or not lines[0].startswith("# "):
        errors.append("%s: the first line is not the one title" % name)
        return {"name": name, "title": "", "units": [], "errors": errors, "paragraphs": 0}
    title = lines[0][2:].strip()
    paras = _paragraphs(lines[1:])
    units = []
    pre = {"id": None, "heading": title, "preamble": True, "lines": [], "tables": [],
           "prose": []}
    cur = pre
    position = 0
    for para_index, para in enumerate(paras, start=1):
        first = para[0]
        h = HEADING.match(first)
        if h:
            if len(para) != 1:
                errors.append("%s: a heading not alone in its paragraph" % name)
            level = len(h.group(1))
            if level != 2:
                errors.append("%s: heading level %d (only one title, entries at level 2)"
                              % (name, level))
                continue
            position += 1
            cur = {"id": tr.unit_id(position, h.group(2)), "heading": h.group(2),
                   "preamble": False, "lines": [], "tables": [], "prose": []}
            units.append(cur)
            continue
        if all(ln.startswith("|") for ln in para):
            t = _parse_table(para, name, errors)
            if t:
                cur["tables"].append(t)
            continue
        label_lines = [LABEL_LINE.match(ln) for ln in para]
        if all(label_lines):
            for m in label_lines:
                label, value = m.group(1), m.group(2)
                if label != label.strip() or not tr.norm(label):
                    errors.append("%s: label %r" % (name, label))
                kind = tr.classify_value(value)
                if kind[0] == "bad":
                    errors.append("%s: %s" % (name, kind[1]))
                cur["lines"].append({"raw": label, "norm": tr.norm(label),
                                     "value": value.strip(), "kind": kind, "para": para_index})
            continue
        if any(label_lines):
            errors.append("%s: label lines mixed with prose in one paragraph" % name)
            continue
        for ln in para:
            if ":" in ln or LIST_START.match(ln) or re.search(r"\d", ln) or "|" in ln:
                errors.append("%s: prose line %r carries a colon, digit, bar or list start"
                              % (name, ln))
        cur["prose"].append(" ".join(para))
    has_pre = bool(pre["lines"] or pre["tables"] or pre["prose"])
    if has_pre:
        pre["id"] = "u00-" + tr.slug(title)
        units.insert(0, pre)
    seen = set()
    for u in units:
        u["labels"] = set()
        u["value_words"] = set()
        line_norms = [ln["norm"] for ln in u["lines"]]
        if len(set(line_norms)) != len(line_norms):
            errors.append("%s: %s states a label twice" % (name, u["id"]))
        for ln in u["lines"]:
            u["labels"].add(ln["norm"])
            u["value_words"].update(tr.words(ln["value"]))
        for t in u["tables"]:
            for hd in t["headers"]:
                u["labels"].add(hd["norm"])
        sl = u["id"][4:]
        if sl in seen:
            errors.append("%s: two units share the slug %s" % (name, sl))
        seen.add(sl)
    return {"name": name, "title": title, "units": units, "errors": errors,
            "paragraphs": len(paras) + 1}


def parse_conventions(text, name):
    errors = []
    _basic_text_checks(text, name, errors)
    lines = text.split("\n")
    paras = _paragraphs(lines)
    rules = []
    if not paras or not paras[0][0].startswith("# "):
        errors.append("%s: no title" % name)
        return {"rules": rules, "errors": errors}
    started = False
    pending = None
    for para in paras:
        h = HEADING.match(para[0])
        if h:
            if len(para) != 1:
                errors.append("%s: a heading not alone in its paragraph" % name)
            heading = h.group(2)
            for content in re.findall(r"\[([^\]]*)\]", heading):
                c = content.strip()
                low = c.lower()
                if low in SEVERITIES or low == "conformance":
                    continue
                if re.match(r"^(scope|requires)\s*:", low):
                    continue
                if re.match(r"^unless\s*:", low):
                    errors.append("%s: [unless: ...] is a directive section 5 forbids" % name)
                elif re.match(r"^[A-Za-z_-]+\s*:", c):
                    errors.append("%s: bracket [%s] stops the run" % (name, c))
                else:
                    errors.append("%s: tag [%s] reaches no reviewer used here" % (name, c))
            if para is paras[0]:
                continue
            m = RULE_ID.search(heading)
            if not m or m.start() != 0 or (len(heading) > m.end() and heading[m.end()] != " "):
                errors.append("%s: heading %r is not a rule heading" % (name, heading))
                continue
            started = True
            rid = m.group(0)
            if re.search(r"\d", rid):
                errors.append("%s: rule id %s carries a digit" % (name, rid))
            sev = "required"
            scope, requires = [], []
            for content in re.findall(r"\[([^\]]*)\]", heading):
                low = content.strip().lower()
                if low in SEVERITIES:
                    sev = low
                d = re.match(r"^(scope|requires)\s*:(.*)$", content.strip(), re.I)
                if d:
                    entries = [e.strip() for e in d.group(2).split(",") if e.strip()]
                    for e in entries:
                        if d.group(1).lower() == "scope":
                            lab, _, val = e.partition("=")
                            scope.append((tr.norm(lab), " ".join(val.split()).lower() if val else None))
                        else:
                            requires.append(tr.norm(e))
            pending = {"id": rid, "severity": sev, "scope": scope, "requires": requires,
                       "texts": []}
            rules.append(pending)
            continue
        if not started:
            if any(LIST_START.match(ln) for ln in para):
                errors.append("%s: a list item before the first rule" % name)
            continue
        if any(LIST_START.match(ln) for ln in para):
            errors.append("%s: a list item under %s" % (name, pending["id"]))
        pending["texts"].append(" ".join(para))
    ids = set()
    for r in rules:
        if len(r["texts"]) != 1:
            errors.append("%s: %s has %d paragraphs" % (name, r["id"], len(r["texts"])))
        r["text"] = " ".join(r["texts"])
        if len(r["text"]) < 16:
            errors.append("%s: %s rule text is shorter than 16 characters" % (name, r["id"]))
        if r["id"].upper() in ids:
            errors.append("%s: %s is not unique" % (name, r["id"]))
        ids.add(r["id"].upper())
        r["words"] = set(tr.words(r["text"]))
        r["own_bands"] = _own_bands(r, errors, name)
    return {"rules": rules, "errors": errors}


def _own_bands(rule, errors, name):
    nums = tr.numbers_with_measures(rule["text"])
    groups = {}
    for v, meas in nums:
        if not meas:
            errors.append("%s: %s has a number with no measure" % (name, rule["id"]))
            continue
        groups.setdefault(tr.measure_powers(meas), []).append(v)
    bands = []
    for powers, vals in sorted(groups.items()):
        if len(vals) < 2:
            errors.append("%s: %s has a lone figure (no band)" % (name, rule["id"]))
            continue
        bands.append({"lo": min(vals), "hi": max(vals), "powers": powers})
    return bands


def parse_grounding(text, name):
    """A reference file: a title, prose paragraphs and band tables only."""
    errors = []
    _basic_text_checks(text, name, errors)
    lines = text.split("\n")
    if not lines[0].startswith("# "):
        errors.append("%s: no title" % name)
    paras = _paragraphs(lines[1:])
    tables, sentences = [], []
    for para in paras:
        if all(ln.startswith("|") for ln in para):
            t = _parse_table(para, name, errors)
            if t:
                tables.append(t)
            continue
        for ln in para:
            if ":" in ln or LIST_START.match(ln) or "|" in ln or ln.startswith("#"):
                errors.append("%s: line %r is not plain prose" % (name, ln))
        joined = " ".join(para)
        if len(joined) > 200 and re.search(r"\d", joined):
            errors.append("%s: a paragraph past 200 characters carries a figure" % name)
        if re.search(r"\d", joined) and not BOUND_SENTENCE.match(joined):
            errors.append("%s: a digit outside a bound sentence: %r" % (name, joined))
    sentences = reader_sentences(text, stored=True)
    return {"name": name, "tables": tables, "sentences": sentences, "errors": errors,
            "paragraphs": len(paras) + 1}


def _sentences(text):
    """Split one joined paragraph after every '.', '?' or '!' followed by space."""
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def reader_sentences(text, stored=False):
    """The bound search's sentences (INPUT_FORMAT section 7, "What a sentence is").
    Per paragraph (a run of non-blank lines): lines starting, after spaces, with '|' or
    '#' are dropped, the rest joined with single spaces, then split after '.', '?' or
    '!'. With stored=True (a grounding file, the earlier version included) only the
    stored passage is read: a prose paragraph's first 200 characters; a table passage
    holds only '|' lines and gives nothing."""
    out = []
    for para in _paragraphs(text.split(NL)):
        if stored:
            if all(ln.lstrip().startswith("|") for ln in para):
                continue
            para = NL.join(para)[:200].split(NL)
        kept = [ln.strip() for ln in para if not ln.lstrip().startswith(("|", "#"))]
        if kept:
            out.extend(_sentences(" ".join(kept)))
    return out


def _band_tables(tables, name, errors):
    """Section 7 column kinds, key columns and the ranges of every range column."""
    out = []
    for t in tables:
        ncol = len(t["headers"])
        kinds = []
        for c in range(ncol):
            cells = [row[c] for row in t["rows"] if row[c][0] != "blank"]
            if cells and all(k[0] == "range" for k in cells):
                kinds.append("range")
            elif cells and all(k[0] == "number" for k in cells):
                kinds.append("value")
            else:
                kinds.append("text")
        if t["size"] > 900:
            errors.append("%s: a table passage over 900 characters loses rows" % name)
        for c in range(ncol):
            if kinds[c] != "range":
                continue
            if not t["headers"][c]["measure"]:
                errors.append("%s: a range column with no header measure" % name)
                continue
            for row in t["rows"]:
                k = row[c]
                if k[0] == "range" and k[1][0] > k[1][1]:
                    errors.append("%s: a range written high first" % name)
            keys = []
            for k in range(ncol):
                if kinds[k] != "text":
                    continue
                cells = [row[k][1] for row in t["rows"] if row[k][0] == "text"]
                if len(cells) >= 2 and len(set(cells)) == len(cells):
                    keys.append(k)
            out.append({"table": t, "col": c, "keys": keys, "file": name})
    return out


def _named(rule, universe):
    named = [L for L in sorted(universe) if L and set(L.split()) <= rule["words"]]
    keep = []
    for L in named:
        sL = set(L.split())
        if any(sL < set(M.split()) for M in named):
            continue
        keep.append(L)
    return keep


def _first_line(u, label):
    for ln in u["lines"]:
        if ln["norm"] == label:
            return ln
    return None


def _in_scope(rule, u):
    for lab, pinned in rule["scope"]:
        if lab not in u["labels"]:
            return False
        if pinned is not None:
            ln = _first_line(u, lab)
            if ln is None or " ".join(ln["value"].split()).lower() != pinned:
                return False
    return True


def _figures(u):
    out = []
    for ln in u["lines"]:
        k = ln["kind"]
        if k[0] == "figure":
            out.append({"label": ln["norm"], "value": k[1], "powers": tr.measure_powers(k[2]),
                        "measure": k[2]})
        elif k[0] == "date":
            out.append({"label": ln["norm"], "value": float(k[1][0]), "powers": (),
                        "measure": ""})
    return out


def _attribute(u_rules, field, basis):
    """Section 9: each paired rule scores 2 per word of the set of its named labels'
    words found in the field label, plus 1 per such word found in the finding's basis
    sentence split at spaces ('sum of N values under <column>', '<a> times <b>',
    '<column> is filled in N of M rows'). The code counts the set; the per-label count
    is kept as a stricter second reading, and the planted rule must win strictly under
    both, never by reading order or an all-zero default."""
    fw = set(field.split()) if field else set()
    sw = set(basis.lower().split())
    best = {}
    for mode in ("set", "sum"):
        scores = []
        for r in u_rules:
            if mode == "set":
                nw = set()
                for L in r["named"]:
                    nw.update(L.split())
                s = 2 * len(nw & fw) + len(nw & sw)
            else:
                s = sum(2 * len(set(L.split()) & fw) + len(set(L.split()) & sw)
                        for L in r["named"])
            scores.append(s)
        top = max(scores) if scores else 0
        winners = [r["id"] for r, s in zip(u_rules, scores) if s == top]
        best[mode] = (winners, top)
    w1, w2 = best["set"][0], best["sum"][0]
    if len(w1) != 1 or w1 != w2 or best["set"][1] == 0:
        return None, "attribution of %s is not settled the same way under both overlap counts (%s / %s)" % (field or "a finding", w1, w2)
    return w1[0], None


def _bound_for(rule, sentences):
    cands = []
    for s in sentences:
        nums = tr.numbers_with_measures(s)
        if len(nums) != 1 or not nums[0][1]:
            continue
        val, meas = nums[0]
        rest = re.sub(r"(?<![\w.])" + tr.NUMBER + r"\s*" + re.escape(meas), " ", s, count=1)
        ow = tr.words(rest)
        if set(ow) <= rule["words"]:
            cands.append((len(ow), len(set(ow)), val, meas, s))
    if not cands:
        return None, None
    best = None
    for idx in (0, 1):      # by word count, and by distinct words: the winner must agree
        top = max(c[idx] for c in cands)
        tops = [c for c in cands if c[idx] == top]
        if len(tops) != 1 or (best is not None and tops[0] is not best):
            return None, "date-window bound for %s is a tie or depends on the count" % rule["id"]
        best = tops[0]
    _, _, val, meas, s = best
    if meas not in ("days", "hours"):
        return None, None
    return (val, meas, s), None


def audit(target_text, target_name, conv_text, conv_name, grounding, prior_name=None,
          enforce_section5=True):
    """Every comparison Python would make on the target. `grounding` maps a file name
    to its text; `prior_name` (if any) is one of them and is read as a document."""
    errors = []
    doc = parse_document(target_text, target_name)
    errors.extend(doc["errors"])
    conv = parse_conventions(conv_text, conv_name)
    errors.extend(conv["errors"])
    tables, sentences = [], []
    prior = None
    for gname in sorted(grounding):
        gtext = grounding[gname]
        if gname == prior_name:
            prior = parse_document(gtext, gname)
            errors.extend(prior["errors"])
            for u in prior["units"]:
                tables.extend(u["tables"])
            sentences.extend(reader_sentences(gtext, stored=True))
            if prior["paragraphs"] >= 120:
                errors.append("%s: %d paragraphs (keep under 120)" % (gname, prior["paragraphs"]))
        else:
            g = parse_grounding(gtext, gname)
            errors.extend(g["errors"])
            tables.extend(g["tables"])
            sentences.extend(g["sentences"])
            if g["paragraphs"] >= 120:
                errors.append("%s: %d paragraphs (keep under 120)" % (gname, g["paragraphs"]))
    sentences.extend(reader_sentences(target_text, stored=False))
    bands = _band_tables(tables, "reference", errors)
    parse_errors = list(errors)

    universe = set()
    for u in doc["units"]:
        universe |= u["labels"]
    rules = conv["rules"]
    for r in rules:
        r["named"] = _named(r, universe)
    pairing = {u["id"]: [] for u in doc["units"]}
    for r in rules:
        if r["scope"] and not r["requires"] and enforce_section5:
            errors.append("%s: scope without requires (section 5, rule 3)" % r["id"])
        if r["requires"] and not r["scope"] and enforce_section5:
            errors.append("%s: requires without scope does nothing" % r["id"])
        if not r["scope"] and not r["named"] and enforce_section5:
            errors.append("%s names no document label (section 5, rule 4)" % r["id"])
        if r["scope"] and r["own_bands"]:
            errors.append("%s: a completeness rule states a band" % r["id"])
        for u in doc["units"]:
            if r["scope"]:
                ok = _in_scope(r, u)
            else:
                ok = bool(r["named"]) and all(L in u["labels"] for L in r["named"])
            if ok:
                pairing[u["id"]].append(r)
    if enforce_section5:
        for u in doc["units"]:
            if not u["preamble"] and not pairing[u["id"]]:
                errors.append("%s: no rule applies (section 5, rule 5)" % u["id"])
            if u["preamble"] and pairing[u["id"]]:
                errors.append("%s: a rule pairs with the preamble" % u["id"])

    findings = []

    def add(u, relation, field, a, b, rule, conditional=False, ratio=False):
        findings.append({"unit": u["id"], "relation": relation, "field_label": field,
                         "value_a": tr.r6(a), "value_b": tr.r6(b), "rule": rule,
                         "conditional": conditional, "ratio": ratio})

    for u in doc["units"]:
        u_rules = pairing[u["id"]]
        if not u_rules:
            continue
        figs = [f for f in _figures(u)]
        # products: any two label-line figures against a third
        for i in range(len(figs)):
            for j in range(i + 1, len(figs)):
                pm = tr.mul(figs[i]["powers"], figs[j]["powers"])
                for k in range(len(figs)):
                    if k in (i, j) or figs[k]["powers"] != pm:
                        continue
                    prod = tr.r6(figs[i]["value"] * figs[j]["value"])
                    if not tr.same(prod, figs[k]["value"]):
                        rid, why = _attribute(u_rules, figs[k]["label"], "%s times %s"
                                              % (figs[i]["label"], figs[j]["label"]))
                        if why:
                            errors.append("%s: %s" % (u["id"], why))
                        add(u, "product_mismatch", figs[k]["label"], prod, figs[k]["value"], rid)
        # sums and blank cells
        for t in u["tables"]:
            for c, hd in enumerate(t["headers"]):
                cells = [row[c] for row in t["rows"]]
                nums = [k[1] for k in cells if k[0] == "number"]
                nonblank = [k for k in cells if k[0] != "blank"]
                if hd["measure"] or (nonblank and all(k[0] == "number" for k in nonblank)):
                    if any(k[0] == "blank" for k in cells):
                        rid, why = _attribute(u_rules, hd["norm"], "%s is filled in %d of %d rows"
                                              % (hd["norm"], len(nums), len(cells)))
                        if why:
                            errors.append("%s: %s" % (u["id"], why))
                        add(u, "missing_field", hd["norm"], len(nums), len(cells), rid)
                if hd["measure"] and len(nums) >= 2:
                    cw = set(hd["norm"].split())
                    for f in figs:
                        if f["powers"] != hd["powers"] or not f["powers"]:
                            continue
                        fw = set(f["label"].split())
                        if cw < fw:
                            s = tr.r6(sum(nums))
                            if not tr.same(s, f["value"]):
                                rid, why = _attribute(u_rules, f["label"], "sum of %d values under %s"
                                                      % (len(nums), hd["norm"]))
                                if why:
                                    errors.append("%s: %s" % (u["id"], why))
                                add(u, "sum_mismatch", f["label"], s, f["value"], rid)
        for r in u_rules:
            # computed absence
            if r["scope"] and r["requires"]:
                for req in r["requires"]:
                    if req not in u["labels"]:
                        add(u, "missing_field", req, 0, 1, r["id"])
                continue
            # reference-table bands
            for b in bands:
                t, c = b["table"], b["col"]
                hd = t["headers"][c]
                if not set(hd["norm"].split()) <= r["words"]:
                    continue
                named_keys = [k for k in b["keys"]
                              if t["headers"][k]["norm"] and set(t["headers"][k]["norm"].split()) <= r["words"]]
                use = named_keys or b["keys"]
                cands = []
                for row in t["rows"]:
                    kw = set()
                    for k in use:
                        if row[k][0] == "text":
                            kw.update(tr.words(row[k][1]))
                    if kw and kw <= u["value_words"] and row[c][0] == "range":
                        cands.append((len(kw), row))
                if not cands:
                    continue
                top = max(n for n, _ in cands)
                best = [row for n, row in cands if n == top]
                if len(best) != 1:
                    errors.append("%s: band row tie for %s" % (u["id"], r["id"]))
                    continue
                lo, hi = best[0][c][1]
                key_heads = {t["headers"][k]["norm"] for k in use}
                _compare(u, r, figs, lo, hi, hd["powers"], key_heads, True, add)
            for ob in r["own_bands"]:
                _compare(u, r, figs, ob["lo"], ob["hi"], ob["powers"], set(), False, add)
            # date windows
            dl = [ln for ln in u["lines"] if ln["kind"][0] == "date" and ln["norm"] in r["named"]]
            if len(dl) == 2:
                bound, why = _bound_for(r, sentences)
                if why:
                    errors.append("%s: %s" % (u["id"], why))
                if bound:
                    d1 = datetime.date(*dl[0]["kind"][1])
                    d2 = datetime.date(*dl[1]["kind"][1])
                    gap = abs((d2 - d1).days)
                    if bound[1] == "hours":
                        gap *= 24
                    if gap > bound[0] and not tr.same(gap, bound[0]):
                        add(u, "date_window", dl[0]["norm"], gap, bound[0], r["id"])
    for f in findings:
        if f["rule"] is None:
            errors.append("%s: a %s finding with no rule" % (f["unit"], f["relation"]))
    return {"doc": doc, "prior": prior, "rules": rules, "pairing": pairing,
            "findings": findings, "errors": errors, "parse_errors": parse_errors,
            "sentences": sentences}


def _compare(u, r, figs, lo, hi, powers, key_heads, from_table, add):
    items = []
    if from_table:
        targets = [f for f in figs if f["powers"] == powers]
        cols = [(t, c) for t in u["tables"] for c, hd in enumerate(t["headers"])
                if hd["powers"] == powers and hd["measure"]]
    else:
        held = [f for f in figs if f["label"] in r["named"] and f["powers"] == powers]
        held_cols = [(t, c) for t in u["tables"] for c, hd in enumerate(t["headers"])
                     if hd["norm"] in r["named"] and hd["powers"] == powers]
        if held or held_cols:
            targets, cols = held, held_cols
        else:
            targets = [f for f in figs if f["powers"] == powers]
            cols = [(t, c) for t in u["tables"] for c, hd in enumerate(t["headers"])
                    if hd["powers"] == powers and hd["measure"]]
    for f in targets:
        items.append((f["label"], f["value"], [f["label"]], False))
    for t, c in cols:
        n = 0
        for row in t["rows"]:
            if row[c][0] == "number":
                n += 1
                items.append(("%s row%d" % (t["headers"][c]["norm"], n), row[c][1],
                              [t["headers"][c]["norm"]], False))
    for i, fi in enumerate(figs):
        for j, fj in enumerate(figs):
            if i == j or fj["value"] == 0:
                continue
            if tr.div(fi["powers"], fj["powers"]) == powers:
                items.append((None, tr.r6(fi["value"] / fj["value"]),
                              [fi["label"], fj["label"]], True))
    for label, v, compared, ratio in items:
        if v > hi:
            add(u, "above_band", label, v, hi, r["id"], False, ratio)
        elif v < lo:
            conditional = False
            if from_table:
                allowed = set(compared) | key_heads
                conditional = not set(r["named"]) <= allowed
            add(u, "below_band", label, v, lo, r["id"], conditional, ratio)


def prior_records(result):
    """Section 6 change records and refusals, from an audit() result with a prior."""
    doc, prior, rules, pairing = result["doc"], result["prior"], result["rules"], result["pairing"]
    records, refusals = [], []
    if prior is None:
        return records, refusals
    by_slug_t = {u["id"][4:]: u for u in doc["units"]}
    earlier = {}
    for pu in prior["units"]:
        for ln in pu["lines"]:
            earlier.setdefault(ln["norm"], []).append((pu, ln))
        if pu["tables"]:
            refusals.append(("earlier tables are not modelled", pu["id"]))
    def lookup(label, slug):
        """The earlier statement of a label (section 6): (None, None) when the earlier
        version does not state it with a figure, (None, why) when it is refused (several
        figures even under the same slug, or no REF id), else (statement, None)."""
        hits = [(pu, pl) for pu, pl in earlier.get(label, [])
                if pl["kind"][0] in ("figure", "date")]
        if not hits:
            return None, None
        def val(pl):
            return pl["kind"][1] if pl["kind"][0] == "figure" else pl["kind"][1][0]
        if len({val(pl) for _, pl in hits}) > 1:
            hits = [(pu, pl) for pu, pl in hits if pu["id"][4:] == slug]
            if len({val(pl) for _, pl in hits}) != 1:
                return None, "several earlier figures"
        if hits[0][1]["para"] >= 120:
            return None, "past the indexed paragraphs"
        return hits[0], None

    for u in doc["units"]:
        u_rules = pairing[u["id"]]
        for ln in u["lines"]:
            k = ln["kind"]
            if k[0] not in ("figure", "date"):
                continue
            hit, why = lookup(ln["norm"], u["id"][4:])
            if why:
                refusals.append((why, ln["norm"]))
                continue
            if hit is None:
                continue
            pu, pl = hit
            now_m = k[2] if k[0] == "figure" else ""
            then_m = pl["kind"][2] if pl["kind"][0] == "figure" else ""
            if not now_m or tr.measure_powers(now_m) != tr.measure_powers(then_m):
                refusals.append(("measure", ln["norm"]))
                continue
            if not u_rules:
                refusals.append(("no rule", ln["norm"]))
                continue
            a, b = k[1], pl["kind"][1]
            if tr.same(a, b):
                rel = "unchanged_from_prior"
            else:
                ranges = set()
                for r in u_rules:
                    if r["scope"] or ln["norm"] not in r["named"]:
                        continue
                    for ob in r["own_bands"]:
                        if ob["powers"] == tr.measure_powers(now_m):
                            ranges.add((ob["lo"], ob["hi"]))
                if len(ranges) == 1:
                    lo, hi = next(iter(ranges))
                    da = 0 if lo <= a <= hi else min(abs(a - lo), abs(a - hi))
                    db = 0 if lo <= b <= hi else min(abs(b - lo), abs(b - hi))
                    if tr.same(da, db):
                        rel = "changed_from_prior"
                    elif da < db:
                        rel = "moved_toward"
                    else:
                        rel = "moved_away"
                else:
                    if len(ranges) > 1:
                        refusals.append(("several bands", ln["norm"]))
                    rel = "changed_from_prior"
            records.append({"field_label": ln["norm"], "relation": rel, "value_a": tr.r6(a),
                            "value_b": tr.r6(b), "unit": then_m, "unit_id": u["id"]})
    target_labels = set()
    for u in doc["units"]:
        target_labels |= u["labels"]
    for pu in prior["units"]:
        tu = by_slug_t.get(pu["id"][4:])
        for pl in pu["lines"]:
            if pl["kind"][0] not in ("figure", "date"):
                continue
            if tu is None:
                refusals.append(("orphan", pl["norm"]))
                continue
            if pl["norm"] in target_labels:
                continue
            then_v = pl["kind"][1] if pl["kind"][0] == "figure" else float(pl["kind"][1][0])
            then_m = pl["kind"][2] if pl["kind"][0] == "figure" else ""
            renamed = False
            for tl in tu["lines"]:
                # new unless the earlier version states it, anywhere, with a successful lookup
                if lookup(tl["norm"], tu["id"][4:])[0] is not None:
                    continue
                if tl["kind"][0] != "figure" or not then_m:
                    continue
                if tr.measure_powers(tl["kind"][2]) != tr.measure_powers(then_m):
                    continue
                # 2% of the larger of the two in absolute value, 2% included
                scale = max(abs(tl["kind"][1]), abs(then_v), 1e-12)
                if abs(tl["kind"][1] - then_v) <= RENAME_TOLERANCE * scale:
                    renamed = True
            if renamed:
                refusals.append(("possible rename", pl["norm"]))
                continue
            citing = [r for r in rules if pl["norm"] in set(_named_any(r, pl["norm"]))]
            if not citing and not pairing[tu["id"]]:
                refusals.append(("no rule", pl["norm"]))
                continue
            records.append({"field_label": pl["norm"], "relation": "absent_since_prior",
                            "value_a": None, "value_b": tr.r6(then_v), "unit": then_m,
                            "unit_id": tu["id"]})
    return records, refusals


def _named_any(rule, label):
    return [label] if label and set(label.split()) <= rule["words"] else []
