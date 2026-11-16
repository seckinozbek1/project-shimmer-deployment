"""A PDF page's layout recovered from where its text is drawn (D-668, READER-LAYERS-A).

pdf_layers used to keep pypdf's page text as it came: two columns interleaved line by line, the
running header and the page number inside the text of every page, a table's cells run together
and no heading, so a PDF was always one unit. This module reads the positions instead. Its input
is each page's text FRAGMENTS, as pypdf's text visitor hands them (pdf_layers.fragments): the
text, the point it is drawn at, its size and whether it is set at an angle. Every decision is by
geometry and font size, never by the words, and every threshold is the operator's, declared in
config/document_reader.json `pdf_layout` (`settings`); with none declared nothing is recovered
and the record says so.

1. LINES: fragments at one height (within `line_tolerance_em` of the size) are one line; on a
   line, a gap wider than `cell_gap_em` starts a new CELL.
2. RUNNING HEADERS AND FOOTERS: a line in the top or bottom `margin_band_share` of the page whose
   text, with every digit read as one mark, stands on `repeat_pages_min` pages or more is set
   apart from the main text (kept in the reading's items, counted in the record).
3. COLUMNS: a vertical gutter is an x position that `column_lines_min` lines or more split at,
   no line crosses, and whose left cells fill at least `column_fill_share` of their column (a
   table's short cells do not). The text is read column by column, top to bottom; a line that
   crosses the gutter (a title over both columns) closes the columns above it.
4. TABLES: `table_rows_min` lines or more in a row with the same number of cells (two or more)
   starting at the same x positions (within `align_tolerance_em`) are a table, written as `|`
   rows, its first row the header (html_layers._table_text, the HTML reader's own form). A row
   beside a table whose cells start at the table's positions but are fewer or more is a table
   Python could not recover: its rows stay as plain lines and the record counts it lost.
5. HEADINGS: a one-line block whose size is at least `heading_size_ratio` times the body size
   (the size most characters are set in) and at most `heading_chars_max` long is a heading; the
   largest size is level 1, the next level 2 and so on, and when the level-1 size is used more
   than once every heading moves down one (the .docx and HTML shift rule), so
   pairing_map.split_units gives a unit per heading.
6. PARAGRAPHS: a line that fills its column (`line_fill_share`) runs on into the next line; a
   shorter one ends its paragraph. Blocks are separated by a blank line.

What is lost is counted, never dropped: text set at an angle (kept after the page's other text,
its place in the reading order not recovered) and tables not recovered. A width is estimated as
`char_width_em` of the size per character, since pypdf's visitor hands no glyph widths.
"""
from __future__ import annotations

import re
from collections import Counter

SETTINGS_KEYS = ("line_tolerance_em", "cell_gap_em", "margin_band_share", "repeat_pages_min",
                 "column_lines_min", "column_fill_share", "align_tolerance_em", "table_rows_min",
                 "heading_size_ratio", "heading_chars_max", "line_fill_share", "char_width_em")
_DIGITS = re.compile(r"\d+")
_SPACE = re.compile(r"\s+")


def settings(declared):
    """The declared `pdf_layout` block, or None when it is missing or any value is not a positive
    number: then no layout is recovered (pdf_layers records the structure as lost)."""
    if not isinstance(declared, dict):
        return None
    out = {}
    for key in SETTINGS_KEYS:
        value = declared.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            return None
        out[key] = float(value)
    return out


# ---------- lines and cells ----------------------------------------------------------------------

def _width(text, size, s):
    return len(text) * size * s["char_width_em"]


def _cells(fragments, s):
    """One line's fragments, left to right, joined into cells."""
    cells = []
    for f in sorted(fragments, key=lambda f: f["x"]):
        x1 = f["x"] + _width(f["text"], f["size"], s)
        if cells and f["x"] - cells[-1]["x1"] <= s["cell_gap_em"] * max(f["size"], cells[-1]["size"]):
            last = cells[-1]
            gap = f["x"] - last["x1"]
            last["text"] += ("" if gap < 0.1 * f["size"] and not f["text"][:1].isspace() else " ") + f["text"]
            last["x1"] = max(last["x1"], x1)
            last["size"] = max(last["size"], f["size"])
            last["chars"] += len(f["text"])
        else:
            cells.append({"x0": f["x"], "x1": x1, "text": f["text"], "size": f["size"], "chars": len(f["text"])})
    for c in cells:
        c["text"] = _SPACE.sub(" ", c["text"]).strip()
    return [c for c in cells if c["text"]]


def lines_of(page, s):
    """The page's upright fragments as lines, top to bottom: [{"top", "size", "cells"}]; and the
    number of fragments set at an angle, which are kept apart."""
    upright = [f for f in page["fragments"] if not f.get("rotated") and f["text"].strip()]
    rotated = [f for f in page["fragments"] if f.get("rotated") and f["text"].strip()]
    rows = []
    for f in sorted(upright, key=lambda f: (-f["y"], f["x"])):
        if rows and abs(rows[-1]["y"] - f["y"]) <= s["line_tolerance_em"] * max(f["size"], rows[-1]["size"]):
            rows[-1]["fragments"].append(f)
            rows[-1]["size"] = max(rows[-1]["size"], f["size"])
        else:
            rows.append({"y": f["y"], "size": f["size"], "fragments": [f]})
    out = []
    for r in rows:
        cells = _cells(r["fragments"], s)
        if cells:
            out.append({"top": page["height"] - r["y"], "size": r["size"], "cells": cells})
    return out, rotated


def _text(line):
    return " ".join(c["text"] for c in line["cells"])


# ---------- running headers and footers ----------------------------------------------------------

def _band(line, page, s):
    share = s["margin_band_share"] * page["height"]
    if line["top"] <= share:
        return "top"
    if line["top"] >= page["height"] - share:
        return "bottom"
    return None


def running_lines(pages, page_lines, s):
    """{(page index, line index)} of the lines repeated in a margin band on enough pages."""
    seen = Counter()
    keys = {}
    for p, (page, lines) in enumerate(zip(pages, page_lines)):
        here = set()
        for i, line in enumerate(lines):
            band = _band(line, page, s)
            if band:
                key = (band, _DIGITS.sub("#", _text(line)))
                keys[(p, i)] = key
                here.add(key)
        seen.update(here)
    return {pi for pi, key in keys.items() if seen[key] >= s["repeat_pages_min"]}


# ---------- columns ------------------------------------------------------------------------------

def _gutter(lines, s):
    """The x of the best gutter among `lines`, or None."""
    candidates = []
    for line in lines:
        for a, b in zip(line["cells"], line["cells"][1:]):
            candidates.append((a["x1"] + b["x0"]) / 2)
    best = None
    for g in sorted(set(round(c, 1) for c in candidates)):
        split = [l for l in lines if any(a["x1"] <= g <= b["x0"] for a, b in zip(l["cells"], l["cells"][1:]))]
        if len(split) < s["column_lines_min"]:
            continue
        crossing = sum(1 for l in lines if any(c["x0"] < g < c["x1"] for c in l["cells"]))
        if crossing >= len(split):
            continue
        left = [c for l in split for c in l["cells"] if c["x1"] <= g]
        start = min(c["x0"] for c in left)
        fills = sorted((c["x1"] - c["x0"]) / max(g - start, 1e-6) for c in left)
        if fills[len(fills) // 2] < s["column_fill_share"]:
            continue
        if best is None or len(split) > best[1]:
            best = (g, len(split))
    return None if best is None else best[0]


def _side(line, keep):
    cells = [c for c in line["cells"] if keep(c)]
    return dict(line, cells=cells) if cells else None


def read_order(lines, s, depth=0):
    """`lines` in reading order, each column read top to bottom before the next. Returns (lines,
    columns found): a line is {"top", "size", "cells", "width"}, width that of its column."""
    width = (max(c["x1"] for l in lines for c in l["cells"]) - min(c["x0"] for l in lines for c in l["cells"])) if lines else 0
    for l in lines:
        l.setdefault("width", width)
    if depth >= 3 or len(lines) < s["column_lines_min"]:
        return lines, 0
    g = _gutter(lines, s)
    if g is None:
        return lines, 0
    out, found, left, right = [], 1, [], []

    def flush():
        nonlocal found
        for part in (left, right):
            ordered, more = read_order(list(part), s, depth + 1)
            found += more
            out.extend(ordered)
        left.clear()
        right.clear()

    for line in lines:
        if any(c["x0"] < g < c["x1"] for c in line["cells"]):
            flush()
            out.append(line)
            continue
        a = _side(line, lambda c: c["x1"] <= g)
        b = _side(line, lambda c: c["x0"] >= g)
        if a:
            a.pop("width", None)
            left.append(a)
        if b:
            b.pop("width", None)
            right.append(b)
    flush()
    return out, found


# ---------- tables, headings, paragraphs ---------------------------------------------------------

def _aligned(a, b, s):
    tol = s["align_tolerance_em"] * max(a["size"], b["size"])
    return len(a["cells"]) == len(b["cells"]) and all(abs(x["x0"] - y["x0"]) <= tol for x, y in zip(a["cells"], b["cells"]))


def _starts_at(line, table, s):
    tol = s["align_tolerance_em"] * line["size"]
    xs = [c["x0"] for c in table[0]["cells"]]
    return len(line["cells"]) > 1 and all(any(abs(c["x0"] - x) <= tol for x in xs) for c in line["cells"])


def blocks_of(lines, s):
    """[("table", rows) | ("lines", [line]) | ("uneven", [line])] in order. A run of lines of two
    or more cells, each starting at the first line's x positions or the first at theirs, is a
    table when every line has the same cells at the same positions, and a table not recovered
    when they differ."""
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if len(line["cells"]) > 1:
            k = i + 1
            while (k < len(lines) and len(lines[k]["cells"]) > 1
                   and (_starts_at(lines[k], [line], s) or _starts_at(line, [lines[k]], s))):
                k += 1
            run = lines[i:k]
            if len(run) >= s["table_rows_min"]:
                if all(_aligned(line, r, s) for r in run):
                    out.append(("table", [[c["text"] for c in l["cells"]] for l in run]))
                else:
                    out.append(("uneven", run))
                i = k
                continue
        out.append(("lines", [line]))
        i += 1
    return out


def body_size(page_lines):
    """The size most characters are set in, across the document."""
    weight = Counter()
    for lines in page_lines:
        for line in lines:
            for c in line["cells"]:
                weight[round(c["size"] * 2) / 2] += c["chars"]
    return weight.most_common(1)[0][0] if weight else 0.0


def _is_heading(line, body, s):
    return (body > 0 and len(line["cells"]) == 1 and line["size"] >= body * s["heading_size_ratio"]
            and len(_text(line)) <= s["heading_chars_max"])


def heading_levels(page_lines, body, s):
    """{rounded size: level}: the largest heading size is level 1, unless it is used more than
    once, when every level moves down one."""
    sizes = Counter(round(l["size"] * 2) / 2 for lines in page_lines for l in lines if _is_heading(l, body, s))
    ranked = sorted(sizes, reverse=True)
    shift = 1 if ranked and sizes[ranked[0]] > 1 else 0
    return {size: min(rank + 1 + shift, 6) for rank, size in enumerate(ranked)}


def _paragraphs(lines, s):
    """Plain lines joined into paragraphs: a line filling its column runs on into the next."""
    paras, current = [], []
    for line in lines:
        current.append(_text(line))
        span = line["cells"][-1]["x1"] - line["cells"][0]["x0"]
        if line.get("width", 0) <= 0 or span < s["line_fill_share"] * line["width"]:
            paras.append(current)
            current = []
    if current:
        paras.append(current)
    out = []
    for words in paras:
        text = ""
        for piece in words:
            text = piece if not text else (text + piece if text.endswith("-") else text + " " + piece)
        out.append(text)
    return out


def lay_out(pages, s):
    """Every page's text in reading order, and what was found and lost.

    `pages` is [{"width", "height", "fragments": [{"x", "y", "size", "text", "rotated"}]}].
    Returns {"pages": [text], "running": [(page_no, band, text)], "found": {columns, running,
    headings, tables}, "lost": {rotated, tables}}."""
    table_text = _table_renderer()
    laid = [lines_of(p, s) for p in pages]
    page_lines = [lines for lines, _ in laid]
    running = running_lines(pages, page_lines, s)
    kept_running = []
    body_lines = []
    for p, lines in enumerate(page_lines):
        keep = []
        for i, line in enumerate(lines):
            if (p, i) in running:
                kept_running.append((p + 1, _band(line, pages[p], s), _text(line)))
            else:
                keep.append(line)
        body_lines.append(keep)
    body = body_size(body_lines)
    levels = heading_levels(body_lines, body, s)
    found = {"columns": 0, "running": len(kept_running), "headings": 0, "tables": 0}
    lost = {"rotated": 0, "tables": 0}
    texts = []
    for p, lines in enumerate(body_lines):
        ordered, columns = read_order(lines, s)
        found["columns"] += 1 if columns else 0
        parts, plain = [], []

        def flush_plain():
            parts.extend(_paragraphs(plain, s))
            plain.clear()

        for kind, value in blocks_of(ordered, s):
            if kind == "table":
                flush_plain()
                parts.append(table_text(value))
                found["tables"] += 1
            elif kind == "uneven":
                flush_plain()
                lost["tables"] += 1
                parts.append("\n".join(_text(l) for l in value))
            else:
                line = value[0]
                if _is_heading(line, body, s):
                    flush_plain()
                    parts.append("#" * levels[round(line["size"] * 2) / 2] + " " + _text(line))
                    found["headings"] += 1
                else:
                    plain.append(line)
        flush_plain()
        rotated = laid[p][1]
        if rotated:
            lost["rotated"] += len(rotated)
            parts.append(" ".join(_SPACE.sub(" ", f["text"]).strip() for f in rotated))
        texts.append("\n\n".join(x for x in parts if x))
    return {"pages": texts, "running": kept_running, "found": found, "lost": lost}


def _table_renderer():
    import html_layers
    return html_layers._table_text
