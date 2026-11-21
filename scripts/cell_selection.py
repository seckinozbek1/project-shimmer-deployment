"""Cell selection (P2 (b), D-S38, D-S42): for a claim on a table, Python selects the rows and
columns that bear on it, and a model is shown the claim and those cells alone.

Everything here is structural. A table is a pipe table as `pairing_map` and `reference_tables`
read one, with its separator row; its caption is the line standing above it. A word is the one
tokeniser's (`pairing_map._norm_label`), weighted by how rare it is among the table's own labels,
so no word list exists in any language. A figure is digits the claim writes and a cell writes, read
as a number. Which arithmetic a claim asks for, and what any word of it means, is never read here
(WORDS-A): a selection says only "these cells are worth showing a model with this claim". It reads
no key.

    tables(text)                         the pipe tables of a text
    select(text, claim, config, embed)   the selection, or the reason there is none
    render(table, rows, columns)         the selected cells as a caption and a pipe table
    review(units, rule, ask, config)     a declared rule's claim put to `ask` on each unit's table

What is kept. The header row and the key columns always (the leading columns that hold labels, not
figures). Columns the claim names, or every column when it names none. Rows the claim names first,
then, up to `fill_rows`, the rows it does not name: a claim on one row is usually a comparison with
the others, and which it is cannot be read structurally, so a row cut for a small table would cut
the comparison. Above the declared caps the lowest ranked are left out, and the selection says so.

A claim that shares a word or a figure with no row and no column of a document's one table, the
table being within the caps, is shown the whole table (`selected_by: whole_table`): these tables are
small, and silence would lose the claim for nothing. It is still only Python's evidence. A table the
claim does name is shown whole too, caption and every cell, when its body cells (rows times columns)
are within the declared `whole_table_max_cells` (`selected_by: small_table`, N4): no cut then hides
what the claim needs. The bound is a size, never fitted to a claim or a score. The verdict stays the
model's and Python's checks only lower it (TABLE-AUTHORITY-A).

Two paths differ, and a figure from one is no figure of the other. The replay selects on a document's
whole text for the claim alone, with no embedding; `review` selects per unit, with the embedding
model, on the rule's whole text. The review path is measured again before product use.

Otherwise a selection is refused, never guessed, with a reason: `no_table`, `no_match` (as above, on
a table above the caps or among several; with an injected embedding ranker the table and its cells are chosen
by it instead, `selected_by: embedding_fallback`, D-873 stage b, and two tables ranked equal are a `tie`) or `tie` (two tables rank equal, or the caps fall between
two rows or columns ranked equal, so which to cut is not known).

The embedding ranker is injected. It ranks only what words and figures leave equal, it differs by
device, so a measured prompt is built once and saved with its indexes, and the selection says
`ranked_by`.

A rule asks for the review with `[compare: cells]` on its heading: the operator declares it, its text
is the claim, and each unit whose table bears on it is one question, decided from the model's own
probabilities (D-S41) with no text. Every decision goes to the pairing map row; a settled "not met"
is also a model's record (`finding`, INFRA-048), marked and never an amendment. With no measured
threshold nothing is asked.

Decision authority on tables (TABLE-AUTHORITY-A, D-642 (b) and (d), D-646, D-670). The verdict is the
model's, decided as CHOICE-A decides it. Python checks only what it can compute and only lowers: a
lowered verdict is a LEANING on the pairing map row (`leaning`, `leaning_confidence`, `leaning_why`),
never a settled decision, never a record, never turned around and never raised.
  - `below_threshold`: an unsettled decision whose top answer is "holds" or "not met" and whose only
    reason is the measured threshold (never a tie, never "no threshold") is kept as a leaning.
  - `figure_unverified` (`figure_check`): a settled "holds" whose claim writes a figure that stands
    in no shown cell and is not one difference or ratio of two figures of one shown row or column,
    within the cells' own rounding, is lowered: where arithmetic can decide a sub-step, Python's
    result outranks the model's, and where it cannot decide the claim it decides nothing.
  - `cited_cell_missing` and `no_cell_cited` (`cited_cells`): when the table tool request ran
    (TABLE-TOOL-A), the cells the judge cited are its request's cell ids; a cited id the table does
    not hold, or a verdict citing no cell at all, is lowered, "holds" or "not met" alike, and a
    lowered "not met" writes no record.
"""
import json
import math
import re
from pathlib import Path

import choice_decision
import paired_review
import pairing_map

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "cell_selection.json"
NO_TABLE, NO_MATCH, TIE = "no_table", "no_match", "tie"
COMPARE_CELLS = "cells"
# N4: a table the claim names, small by the declared `whole_table_max_cells`, is shown whole; it is
# still a table the claim named, so a document's whole tables of no match give way to it as to labels.
SMALL_TABLE = "small_table"
EMBEDDING_FALLBACK = "embedding_fallback"
NAMED_BY = ("labels", SMALL_TABLE)
# Python's sentence on a decided finding: its catalog row reads these words (as passage_pairs').
DECISION_NOTE = "Decided from the model's own answer probabilities on the cells Python selected; it wrote no text: %s, confidence %.3f."
# What a review survives: any failure of a call, so a document never loses its computed findings.
CAUGHT = Exception
_NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*")
# TABLE-AUTHORITY-A: the answers that carry a verdict (config/cell_selection.json labels), and why a
# verdict was lowered to a leaning, the program's own closed set.
LEANABLE = ("holds", "not met")
HOLDS_LABEL = "holds"
LEAN_BELOW, LEAN_FIGURE = "below_threshold", "figure_unverified"
LEAN_CITED_MISSING, LEAN_NONE_CITED = "cited_cell_missing", "no_cell_cited"
_CITED_CELL = re.compile(r"r[1-9][0-9]*c[1-9][0-9]*")
ID_NOT_VALID = "id_not_valid"     # table_tools.ID_NOT_VALID, held equal by check 483


def load_config(path=CONFIG_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _cells(line, width=None):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if width is None:
        return cells
    return (cells + [""] * width)[:width]


def _caption(lines, at):
    """The nearest line above a table that is neither blank nor a heading; "" when there is none."""
    for line in reversed(lines[:at]):
        if line.strip():
            return "" if line.lstrip().startswith("#") else line.strip()
    return ""


def tables(text):
    """[{caption, header, rows}]: every pipe table of `text` with its separator row, each row as
    wide as its header."""
    lines = str(text or "").splitlines()
    out, at = [], 0
    while at < len(lines):
        if not pairing_map._TABLE_ROW.match(lines[at]):
            at += 1
            continue
        end = at
        while end < len(lines) and pairing_map._TABLE_ROW.match(lines[end]):
            end += 1
        block = lines[at:end]
        if len(block) >= 3 and pairing_map._TABLE_SEP.match(block[1]):
            header = _cells(block[0])
            out.append({"caption": _caption(lines, at), "header": header,
                        "rows": [_cells(line, len(header)) for line in block[2:]]})
        at = end
    return out


def figure_value(token):
    """One figure as a table cell or a claim writes it, as a float, or None: the one reader the cell
    step uses (D-652, audit A1). "71,2%", "71.2%", "71.2" and "-3.4" read 71.2, 71.2, 71.2 and 3.4.
    The comma is norm_number's rule, the review's one comma rule: a single comma with no point is a
    decimal comma ("71,2" is 71.2, not 712), groups of three are thousands ("1,254" is 1254). A sign
    and a percent or footnote mark are read off: the figure is matched as a magnitude, since a claim
    writes "fell by 3.4" where its cell writes "-3.4"."""
    t = str(token or "").strip().strip("%*+-−").strip()
    if not re.fullmatch(r"\d+(?:[.,]\d+)*", t):
        return None
    value = paired_review.norm_number(t)
    return None if value is None else abs(value)


def figures(text):
    """The numbers `text` writes, as floats, each read by figure_value."""
    out = set()
    for token in _NUMBER.findall(str(text or "")):
        value = figure_value(token)
        if value is not None:
            out.add(value)
    return out


def _figure_spans(text):
    """[(value, half unit)] of each figure `text` writes: the half unit is half of the last place the
    figure is written to, so 71.2 stands for anything from 71.15 to 71.25 (the writer's own rounding)."""
    out = []
    for token in _NUMBER.findall(str(text or "")):
        value = figure_value(token)
        if value is None:
            continue
        places = 0
        whole = token.replace(",", "") if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", token) else token
        if re.search(r"[.,]\d+$", whole):
            places = len(re.split(r"[.,]", whole)[-1])
        out.append((value, 0.5 * 10 ** -places))
    return out


def _overlaps(low, high, value, half):
    return low <= value + half and value - half <= high


def _one_step(value, half, a, b):
    """Whether `value` (written to within `half`) is the difference or the ratio of figures `a` and
    `b`, each (value, half unit): computed over the intervals the cells' rounding leaves open."""
    (x, hx), (y, hy) = a, b
    if _overlaps(abs(x - y) - hx - hy, abs(x - y) + hx + hy, value, half):
        return True
    for (p, hp), (q, hq) in ((a, b), (b, a)):
        if q - hq > 0 and _overlaps((p - hp) / (q + hq), (p + hp) / (q - hq), value, half):
            return True
    return False


def figure_check(cells, claim):
    """TABLE-AUTHORITY-A rule 3, on the CELLS block the model was shown: {written, in_cells, one_step,
    unverified}, counts only. A claim figure is found when a shown cell writes it (as `figures`
    reads both), else it is one arithmetic step when it is the difference or the ratio of two
    figures of one shown row or one shown column, within the cells' own rounding; any other is
    unverified. Which arithmetic the claim's words ask for is never read (WORDS-A): a found or
    computed figure is no verdict, and an unverified one only lowers a "holds"."""
    written = _figure_spans(claim)
    seen, claim_figures = set(), []
    for value, half in written:
        if value not in seen:
            seen.add(value)
            claim_figures.append((value, half))
    found = tables(cells)
    out = {"written": len(claim_figures), "in_cells": 0, "one_step": 0, "unverified": 0}
    if not claim_figures:
        return out
    if not found:
        out["unverified"] = len(claim_figures)
        return out
    table = found[0]
    grid = [[_figure_spans(cell) for cell in row] for row in table["rows"]]
    shown = set()
    for row in grid:
        for spans in row:
            shown.update(v for v, _h in spans)
    lines = [[s for spans in row for s in spans] for row in grid]
    width = max((len(row) for row in grid), default=0)
    lines += [[s for row in grid if c < len(row) for s in row[c]] for c in range(width)]
    for value, half in claim_figures:
        if value in shown:
            out["in_cells"] += 1
        elif any(_one_step(value, half, line[i], line[j])
                 for line in lines for i in range(len(line)) for j in range(i + 1, len(line))):
            out["one_step"] += 1
        else:
            out["unverified"] += 1
    return out


def cited_cells(request_rows):
    """{cells, missing}: the cell ids the judge's one table tool request cited in its calls Python
    ran (`cells`, sorted), and how many of its lines named an id the table does not hold
    (`missing`). None when no request reply was read: then nothing was cited and nothing is lowered."""
    if request_rows is None:
        return None
    cells = sorted({a for row in request_rows if row.get("ok") for a in row.get("args") or [] if _CITED_CELL.fullmatch(str(a))})
    return {"cells": cells, "missing": sum(1 for row in request_rows if row.get("refused") == ID_NOT_VALID)}


# D-715 item 2 (Seckin 22:31): showing a cell stays optional, but whenever the judge names a cell its record says
# which. The path a decision row's `cells_named` came from: the table tool request's lines (every id a line named,
# run or refused), or none, when no request reply was read: the choice decision itself writes no text, so it
# names no cell. An audit record only: no leaning, figure, score or prompt reads it.
NAMED_BY_REQUEST, NAMED_BY_NONE = "request", "no_text"


def named_cells(request_rows):
    """{cells_named, cells_named_by} of one decision (D-715 item 2): the sorted cell ids every line of the
    judge's request named, whether Python ran the line or refused it (a reply naming none gives none); with no
    request reply read (`request_rows` None: no request, none made, or it failed), none, by `no_text`."""
    if request_rows is None:
        return {"cells_named": [], "cells_named_by": NAMED_BY_NONE}
    return {"cells_named": sorted({str(a) for row in request_rows for a in row.get("args") or []
                                   if _CITED_CELL.fullmatch(str(a))}),
            "cells_named_by": NAMED_BY_REQUEST}


def leaning_of(decision, check=None, cited=None):
    """(leaning, its confidence, why) of one decision under TABLE-AUTHORITY-A, or (None, None, []):
    the decision itself is never changed. An unsettled decision leans only below its threshold with a
    verdict on top; a settled verdict is lowered by an unverified figure ("holds" only) or by its
    citations (either verdict). The confidence is the model's own top probability."""
    if not isinstance(decision, dict):
        return None, None, []
    why = []
    if not decision.get("settled"):
        top = decision.get("top")
        if decision.get("why") != choice_decision.BELOW_THRESHOLD or top not in LEANABLE:
            return None, None, []
        why.append(LEAN_BELOW)
        verdict = top
    else:
        verdict = decision.get("decided")
        if verdict not in LEANABLE:
            return None, None, []
    if verdict == HOLDS_LABEL and check and check.get("unverified"):
        why.append(LEAN_FIGURE)
    if cited is not None:
        if cited.get("missing"):
            why.append(LEAN_CITED_MISSING)
        elif not cited.get("cells"):
            why.append(LEAN_NONE_CITED)
    if not why:
        return None, None, []
    return verdict, decision.get("confidence"), why


def key_columns(table):
    """The leading columns that hold labels: column 0, and each next one with more cells holding
    no figure than cells holding one."""
    keys = [0]
    for index in range(1, len(table["header"])):
        cells = [row[index] for row in table["rows"] if row[index]]
        with_figure = sum(1 for cell in cells if figures(cell))
        if not cells or with_figure * 2 >= len(cells):
            break
        keys.append(index)
    return keys


def _weights(token_sets):
    """How rare each word is among these labels: log(1 + n / labels holding it)."""
    count = {}
    for tokens in token_sets:
        for token in tokens:
            count[token] = count.get(token, 0) + 1
    size = max(len(token_sets), 1)
    return {token: math.log(1 + size / n) for token, n in count.items()}


def _tokens(text):
    return set(pairing_map._norm_label(text))


def _rank(table, claim):
    """(row keys, column keys, keys): each row's and column's (figures written, shared-word weight)
    against the claim, read on the row's label cells and on the column's header."""
    keys = key_columns(table)
    wanted = _tokens(claim)
    written = figures(claim)
    row_words = [_tokens(" ".join(row[i] for i in keys)) for row in table["rows"]]
    column_words = [_tokens(name) for name in table["header"]]
    weights = _weights(row_words + column_words)
    rows, columns = [], []
    held = [[bool(figures(cell) & written) for cell in row] for row in table["rows"]]
    for words, hits in zip(row_words, held):
        rows.append((sum(hits), round(sum(weights[t] for t in words & wanted), 6)))
    for index, words in enumerate(column_words):
        columns.append((sum(row[index] for row in held), round(sum(weights[t] for t in words & wanted), 6)))
    return rows, columns, keys


def _matched(score):
    return score[0] > 0 or score[1] > 0


def _cut(order, scores, cap):
    """(kept, tied): the first `cap` of `order`, and whether the cap falls between two named ones
    ranked equal."""
    if len(order) <= cap:
        return list(order), False
    a, b = order[cap - 1], order[cap]
    return list(order[:cap]), _matched(scores[a]) and scores[a] == scores[b]


def _order(scores, extra):
    """Indexes best first; `extra` (the embedding's score) settles what words and figures leave equal."""
    return sorted(range(len(scores)), key=lambda i: (-scores[i][0], -scores[i][1], -(extra[i] if extra else 0.0), i))


def _embedded(table, keys, claim, embed_with):
    """Each row's and column's cosine with the claim, or (None, None) with no embedding model."""
    if embed_with is None:
        return None, None
    labels = [" ".join(row[i] for i in keys) for row in table["rows"]] + list(table["header"])
    vectors = embed_with([{"text": text} for text in [claim] + labels])
    if not vectors:
        return None, None
    scores = [sum(x * y for x, y in zip(vectors[0], v)) for v in vectors[1:]]
    return scores[:len(table["rows"])], scores[len(table["rows"]):]


def render(table, rows, columns):
    """The caption and the kept cells as a pipe table, in the table's own order."""
    shown = [table["header"]] + [table["rows"][i] for i in rows]
    lines = ["| " + " | ".join(row[i] for i in columns) + " |" for row in shown]
    lines.insert(1, "|" + "---|" * len(columns))
    return "\n".join(([table["caption"]] if table["caption"] else []) + lines)


def _refused(reason, **fields):
    return dict({"selected": False, "refused": reason, "selected_by": None, "cells": "", "rows": [], "columns": [],
                 "ranked_by": None}, **fields)


def _within_caps(table, config):
    return len(table["rows"]) <= config["max_rows"] and len(table["header"]) <= config["max_columns"]


def _small(table, config):
    """N4 (Seckin 01:11): whether a table's body cells (rows times columns) are within the declared
    `whole_table_max_cells`; absent or 0, no table is small. A size bound only, read on the table."""
    return len(table["rows"]) * len(table["header"]) <= int(config.get("whole_table_max_cells") or 0)


def _whole(table, of_tables, chosen=0, selected_by="whole_table"):
    rows, columns = list(range(len(table["rows"]))), list(range(len(table["header"])))
    return {"selected": True, "refused": None, "selected_by": selected_by, "table": chosen, "of_tables": of_tables,
            "of_rows": len(rows), "of_columns": len(columns), "named_rows": 0, "named_columns": 0,
            "cells": render(table, rows, columns), "rows": rows, "columns": columns, "left_out_rows": 0,
            "left_out_columns": 0, "ranked_by": None}


def _by_embedding(found, claim, embed_with):
    """D-873 stage b: the index of the table whose caption and cell text lie nearest the claim by the injected
    embedding, or None when there is no vector or the two best tables rank equal (a tie is never guessed)."""
    texts = [" ".join([t["caption"]] + list(t["header"]) + [cell for row in t["rows"] for cell in row]) for t in found]
    vectors = embed_with([{"text": text} for text in [claim] + texts])
    if not vectors or len(vectors) != len(texts) + 1:
        return None
    scores = [round(sum(x * y for x, y in zip(vectors[0], v)), 6) for v in vectors[1:]]
    best = max(scores)
    return scores.index(best) if scores.count(best) == 1 else None


def _fallen(selection):
    """Marks a selection made by the embedding fallback, so a reader can count it."""
    return dict(selection, selected_by=EMBEDDING_FALLBACK, ranked_by="embedding")


def select(text, claim, config, embed_with=None):
    """The cells of `text` that bear on `claim`: {selected, refused, selected_by, table, cells, rows,
    columns, named_rows, named_columns, of_rows, of_columns, left_out_rows, left_out_columns, ranked_by}.
    `rows` and `columns` are indexes into the chosen table, in its order."""
    found = tables(text)
    if not found:
        return _refused(NO_TABLE)
    ranked = [_rank(table, claim) for table in found]
    strength = []
    for table, (rows, columns, _) in zip(found, ranked):
        caption = sum(1 for _ in _tokens(table["caption"]) & _tokens(claim))
        strength.append((sum(r[0] for r in rows) + sum(c[0] for c in columns),
                         round(sum(r[1] for r in rows) + sum(c[1] for c in columns), 6), caption))
    best = max(strength)
    fallback = False
    if best[:2] == (0, 0.0):
        if len(found) == 1 and _within_caps(found[0], config):
            return _whole(found[0], 1)
        if embed_with is None:
            return _refused(NO_MATCH, of_tables=len(found))
        chosen = _by_embedding(found, claim, embed_with)
        if chosen is None:
            return _refused(TIE if len(found) > 1 else NO_MATCH, of_tables=len(found))
        fallback = True
    elif strength.count(best) > 1:
        return _refused(TIE, of_tables=len(found))
    else:
        chosen = strength.index(best)
    table = found[chosen]
    rows, columns, keys = ranked[chosen]
    # N4: the table the claim names, when small, is shown whole with its caption, nothing cut.
    if _small(table, config):
        named = _whole(table, len(found), chosen, SMALL_TABLE)
        named.update(named_rows=sum(1 for r in rows if _matched(r)),
                     named_columns=sum(1 for i, c in enumerate(columns) if _matched(c) and i not in keys))
        return _fallen(named) if fallback else named
    # The embedding only orders what a cut would choose between, so with no cut it is not asked.
    cut_ahead = (len(table["rows"]) > min(config["fill_rows"], config["max_rows"])
                 or len(columns) - len(keys) > max(config["max_columns"] - len(keys), 1))
    row_extra, column_extra = _embedded(table, keys, claim, embed_with if cut_ahead else None)
    # A column is kept when named, or all of them when none is. Key columns stand outside it. Named
    # columns are filled with unnamed ones up to `fill_columns` (0 when not declared), as rows are, so a
    # named label column cannot crowd out the figures.
    named_columns = [i for i in _order(columns, column_extra) if _matched(columns[i]) and i not in keys]
    others = [i for i in range(len(columns)) if i not in keys]
    unnamed_columns = [i for i in _order(columns, column_extra) if not _matched(columns[i]) and i not in keys]
    column_fill = max(config.get("fill_columns", 0) - len(named_columns), 0)
    wanted_columns = named_columns + unnamed_columns[:column_fill] if named_columns else others
    room = max(config["max_columns"] - len(keys), 1)
    kept_columns, column_tie = _cut(wanted_columns, columns, room)
    named_rows = [i for i in _order(rows, row_extra) if _matched(rows[i])]
    unnamed = [i for i in _order(rows, row_extra) if not _matched(rows[i])]
    fill = max(config["fill_rows"] - len(named_rows), 0)
    kept_rows, row_tie = _cut(named_rows + unnamed[:fill], rows, config["max_rows"])
    fields = {"table": chosen, "of_tables": len(found), "of_rows": len(table["rows"]), "of_columns": len(table["header"]),
              "named_rows": len(named_rows), "named_columns": len(named_columns)}
    if column_tie or row_tie:
        return _refused(TIE, **fields)
    columns_shown = sorted(set(keys) | set(kept_columns))
    rows_shown = sorted(kept_rows)
    result = dict(fields, selected=True, refused=None, selected_by="labels", cells=render(table, rows_shown, columns_shown), rows=rows_shown,
                  columns=columns_shown, left_out_rows=len(table["rows"]) - len(rows_shown),
                  left_out_columns=len(table["header"]) - len(columns_shown),
                  ranked_by="words_and_embedding" if row_extra is not None else "words")
    return _fallen(result) if fallback else result


def declared(rules):
    """The rules whose heading declares `[compare: cells]`."""
    return [r for r in rules or [] if r.get("compare") == COMPARE_CELLS]


def question(config, cells, claim, contracts=None, results=""):
    """The narrow question on a claim and its cells; one pass, so a cell's braces stay text. The
    `{tools}` slot holds what the judge agent's declared tools found (`judge_agent.claim_tools`,
    under `contracts`, the shipped ones by default), "" when no contract declares a shown tool,
    followed by the table tool request's RESULTS block (`results`, D-681), "" when no request ran."""
    import judge_agent
    slots = {"cells": cells, "claim": claim, "tools": judge_agent.claim_tools(cells, claim, contracts) + results}
    return re.sub(r"\{(cells|claim|tools)\}", lambda m: slots[m.group(1)], config["decision"]["template"])


def threshold_of(config):
    return choice_decision.threshold(config["decision"]["threshold_family"])


def missing_threshold(rules, config=None):
    """SciTab P6 (Seckin 19 Nov 01:11, changed by the lead 01:25): the record a run states before any
    model call when a rule declares `[compare: cells]` and no threshold is measured for the cell
    step's family, None otherwise. The run is not refused: the step still asks and saves the answer
    probabilities (N1), but no decision settles, so a figure from it is a scorer's default unless a
    threshold is chosen later (the silent 0.225 of 19 Nov)."""
    ids = [r.get("id") for r in declared(rules)]
    if not ids:
        return None
    config = load_config() if config is None else config
    if threshold_of(config) is not None:
        return None
    return {"cell_threshold_missing": ids, "threshold_family": config["decision"]["threshold_family"],
            "decisions_unsettled": True}


def call(wrapper, stable, dynamic, config):
    """The one model call on a claim, already masked."""
    return wrapper.call_choice(stable + ("\n\n" + dynamic if dynamic else ""), config["decision"]["answers"],
                               threshold_of(config))


def answer_of(result):
    """What `ask` hands back: the decision, None for a failed call."""
    return result.parsed if getattr(result, "ok", False) else None


def outcome_of(result):
    return "decided" if getattr(result, "ok", False) else "backend_failure"


def class_of(decision, config):
    """A settled answer's declared class, UNDECIDED for one not settled, None for no decision."""
    if not isinstance(decision, dict) or "settled" not in decision:
        return None
    if not decision["settled"]:
        return "UNDECIDED"
    return next((a["class"] for a in config["decision"]["answers"] if a["label"] == decision.get("decided")), None)


def finding(rule, unit, selection, decision, source_rule_id=None):
    """The Finding record of a claim the cells do not meet (INFRA-048): the cells Python selected in
    `quote`, the claim in `quote_b`, no sentence of the model's. That the claim fails is the model's
    decision and stays marked as such; `paired_review.judged_item_refusal` holds the rest."""
    item = {"item_id": "cell-%s-%s" % (rule["id"], unit.get("unit_id")), "revision": 1, "rule_id": rule["id"],
            "unit_id": unit.get("unit_id"), "relation": "claim_not_met", "record_verdict": "irregular",
            "quote": selection["cells"], "quote_b": rule.get("rule") or "", "explanation": "",
            paired_review.JUDGED_PATH_FIELD: paired_review.JUDGED_PATH_CELL_CLAIM}
    if source_rule_id:
        item["source_rule_id"] = source_rule_id
    return item


def _row(unit, selection, decision, authority=None):
    """One decided question in the pairing map: identifiers, indexes and numbers, no text.
    `authority` is TABLE-AUTHORITY-A's reading beside the decision ({check, cited}); with it the
    row carries `leaning`, `leaning_confidence`, `leaning_why`, `figures` and, when a request
    ran, `cited_cells` and `cited_missing`. The decision's own fields are never changed by it."""
    row = {"unit_id": unit.get("unit_id"), "selected_by": selection["selected_by"], "rows": selection["rows"],
           "columns": selection["columns"], "of_rows": selection["of_rows"], "of_columns": selection["of_columns"],
           "ranked_by": selection["ranked_by"], "decided": decision["decided"], "settled": decision["settled"],
           "why": decision["why"], "confidence": decision["confidence"], "threshold": decision["threshold"],
           "declared_mass": decision["declared_mass"], "logits_dtype": decision.get("logits_dtype"),
           "answers": {a["label"]: a["probability"] for a in decision["answers"]}}
    if authority is not None:
        check, cited = authority.get("check"), authority.get("cited")
        leaning, confidence, why = leaning_of(decision, check, cited)
        row.update(leaning=leaning, leaning_confidence=confidence, leaning_why=why, figures=check)
        if cited is not None:
            row.update(cited_cells=cited["cells"], cited_missing=cited["missing"])
        if authority.get("named") is not None:
            row.update(authority["named"])     # D-715 item 2: recorded beside the decision, read by nothing
    return row


def _selections(units, claim, config, embed_with, calls, on_selected=None):
    """[(unit, selection)] of the units a question goes to. A whole table is asked only where no
    unit's table names the claim's words, or every table of a long document would be asked.
    `on_selected(unit, None, row)` is told each refused selection's `find_cells` row: no question
    follows it, so `review` cannot."""
    import judge_agent
    chosen = []
    for unit in units:
        selection = select(unit.get("text"), claim, config, embed_with)
        if selection["refused"] == NO_TABLE:
            continue
        calls["tables"] += 1
        if selection["selected"]:
            chosen.append((unit, selection))
        else:
            calls["selection_refused"].append({"unit_id": unit.get("unit_id"), "reason": selection["refused"]})
            if on_selected:
                on_selected(unit, None, judge_agent.find_cells_row(selection))
    if any(s["selected_by"] in NAMED_BY for _, s in chosen):
        kept = [(u, s) for u, s in chosen if s["selected_by"] in NAMED_BY]
        calls["whole_tables_left"] = len(chosen) - len(kept)
        chosen = kept
    calls["whole_table"] = sum(1 for _, s in chosen if s["selected_by"] == "whole_table")
    return chosen


def review(units, rule, source_rule_id, ask, config, embed_with=None, fields_present=None, on_kept=None, contracts=None,
           ask_request=None):
    """(records, calls): the rule's claim on each unit's selected cells, put to `ask(user_text) ->
    decision or None`. `calls` holds each decision (`decisions`), what was refused
    (`selection_refused`, a kept record's `refused`) and why anything was not asked (`not_asked`,
    `why`). The declared number of failed calls in a row stops the rule; a raised failure stops it
    at once, named by its type, and what the review holds stays.

    `contracts` are the judge agent's (D-S55): its declared tools fill the question's `{tools}`
    slot and each tool call is one row of `calls["tool_rows"]` (`judge_agent.tool_rows`). With
    {} no tool is declared, the question is the measured one and no row is kept; None reads the
    shipped contracts.

    `ask_request(spec) -> ask(user_text) -> reply text or None` is the table tool request's narrow
    call (D-681). It is used only when the contracts declare `request_tools` for the task: then each
    question is preceded by ONE request (`table_tools.request_round`), its lines are each a tool row,
    and its RESULTS block joins the `{tools}` slot. With nothing declared no request is made, no key
    is added to `calls` and the question is byte for byte the measured one."""
    import judge_agent
    contracts = judge_agent.shipped_contracts() if contracts is None else contracts
    calls = {"tables": 0, "whole_table": 0, "whole_tables_left": 0, "made": 0, "failed": 0, "unreadable": 0, "unsettled": 0, "leanings": 0,
             "not_met": 0, "decisions": [], "decision_notes": {}, "selection_refused": [], "refused": [], "stopped": None, "raised": None,
             "not_asked": None, "tool_rows": []}
    requested = judge_agent.request_tools(judge_agent.CELL_CLAIM, contracts) if ask_request is not None else []
    if requested:
        calls.update(requests=0, requests_skipped=0, request_failed=0, request_calls=0)

    def tools(unit, prompt, *rows):
        calls["tool_rows"].extend(judge_agent.tool_rows(judge_agent.CELL_CLAIM, contracts, rule["id"], unit.get("unit_id"),
                                                        prompt, rows))
    records = []
    if threshold_of(config) is None:
        # N1 (Seckin 19 Nov 01:11): asked all the same; each answer's probabilities stand on its reply
        # record and its row, every decision UNSETTLED (no_threshold), so no record is written.
        calls["no_threshold"] = config["decision"]["threshold_family"]
    streak = 0
    try:
        chosen = _selections(units, rule.get("rule") or "", config, embed_with, calls, on_selected=tools)
        if len(chosen) > config["max_units_per_rule"]:
            calls["not_asked"] = "no question asked: %d tables, above the declared %d" % (len(chosen), config["max_units_per_rule"])
            calls["why"] = "cells_too_many"
            return records, calls
        for unit, selection in chosen:
            claim = rule.get("rule") or ""
            results = ""
            cited = None
            request_rows = None
            if requested:
                import table_tools
                failed_before = calls["request_failed"]
                results, request_rows, request_prompt = table_tools.request_round(
                    unit.get("text"), selection, claim, config, requested, ask_request, calls)
                if request_prompt is not None and request_rows:
                    tools(unit, request_prompt, *request_rows)
                if request_prompt is not None and calls["request_failed"] == failed_before:
                    cited = cited_cells(request_rows)
            prompt = question(config, selection["cells"], claim, contracts, results) if results else \
                question(config, selection["cells"], claim, contracts)
            tools(unit, prompt, judge_agent.find_cells_row(selection),
                  judge_agent.locate_figures_row(selection["cells"], claim))
            calls["made"] += 1
            decision = ask(prompt)
            if decision is None:
                calls["failed"] += 1
                streak += 1
                if streak >= config["stop_after_failed_calls"]:
                    calls["stopped"] = "stopped after %d failed calls in a row, %d of %d tables decided" % (
                        streak, len(calls["decisions"]), len(chosen))
                    break
                continue
            streak = 0
            cls = class_of(decision, config)
            if cls is None:
                calls["unreadable"] += 1
                continue
            calls["unsettled"] += not decision["settled"]
            row = _row(unit, selection, decision, {"check": figure_check(selection["cells"], claim), "cited": cited,
                                                   "named": named_cells(request_rows if cited is not None else None)})
            calls["decisions"].append(row)
            calls["leanings"] += bool(row["leaning"])
            if cls != "FLAG":
                continue
            if row["leaning"]:     # TABLE-AUTHORITY-A rule 4: a lowered "not met" writes no record
                continue
            calls["not_met"] += 1
            item = finding(rule, unit, selection, decision, source_rule_id)
            if item is None:
                continue
            refusal = paired_review.judged_item_refusal(item, rule, (fields_present or {}).get(unit.get("unit_id")), unit.get("text"),
                                                        selected_cells=selection["cells"])
            tools(unit, prompt, judge_agent.check_quote_row(refusal))
            if refusal:
                calls["refused"].append({"unit_id": unit.get("unit_id"), "rule_id": rule["id"],
                                         "relation": item.get("relation"), "reason": refusal})
                continue
            records.append(paired_review.mark_screened(item))
            calls["decision_notes"][item["item_id"]] = DECISION_NOTE % (decision["decided"], decision["confidence"])
            if on_kept:
                on_kept((prompt,))
    except CAUGHT as exc:
        calls["raised"] = type(exc).__name__
        calls["stopped"] = "stopped by a raised %s, %d tables decided" % (calls["raised"], len(calls["decisions"]))
    return records, calls


def unjudged(rule_id, calls):
    """The rule's not-judged row, or None when every question was answered. `why` picks the
    reader's words."""
    if calls["not_asked"]:
        why, reason = calls["why"], calls["not_asked"]
    elif calls["stopped"]:
        why, reason = ("cells_partly_stopped" if calls["decisions"] else "failed"), calls["stopped"]
    elif calls["failed"]:
        why, reason = "cells_some_failed", "%d of %d calls failed" % (calls["failed"], calls["made"])
    elif not calls["made"]:
        why, reason = "cells_none", "no question asked: %d tables, %d selections refused" % (calls["tables"], len(calls["selection_refused"]))
    elif calls.get("no_threshold"):
        why, reason = "cells_no_threshold", "asked, nothing decided: no threshold measured for " + calls["no_threshold"]
    else:
        return None
    return {"unit_id": None, "rule_id": rule_id, "kind": "cell_claim", "reason": reason, "why": why,
            "consumer_agents": [], "status": "stopped"}
