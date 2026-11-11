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
small, and silence would lose the claim for nothing. It is still only Python's evidence.

Two paths differ, and a figure from one is no figure of the other. The replay selects on a document's
whole text for the claim alone, with no embedding; `review` selects per unit, with the embedding
model, on the rule's whole text. The review path is measured again before product use.

Otherwise a selection is refused, never guessed, with a reason: `no_table`, `no_match` (as above, on
a table above the caps or among several) or `tie` (two tables rank equal, or the caps fall between
two rows or columns ranked equal, so which to cut is not known).

The embedding ranker is injected. It ranks only what words and figures leave equal, it differs by
device, so a measured prompt is built once and saved with its indexes, and the selection says
`ranked_by`.

A rule asks for the review with `[compare: cells]` on its heading: the operator declares it, its text
is the claim, and each unit whose table bears on it is one question, decided from the model's own
probabilities (D-S41) with no text. Every decision goes to the pairing map row; a settled "not met"
is also a model's record (`finding`, INFRA-048), marked and never an amendment. With no measured
threshold nothing is asked.
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
# Python's sentence on a decided finding: its catalog row reads these words (as passage_pairs').
DECISION_NOTE = "Decided from the model's own answer probabilities on the cells Python selected; it wrote no text: %s, confidence %.3f."
# What a review survives: any failure of a call, so a document never loses its computed findings.
CAUGHT = Exception
_NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*")


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


def figures(text):
    """The numbers `text` writes, as floats."""
    out = set()
    for token in _NUMBER.findall(str(text or "")):
        try:
            out.add(float(token.replace(",", "")))
        except ValueError:
            continue
    return out


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


def _whole(table, of_tables):
    rows, columns = list(range(len(table["rows"]))), list(range(len(table["header"])))
    return {"selected": True, "refused": None, "selected_by": "whole_table", "table": 0, "of_tables": of_tables,
            "of_rows": len(rows), "of_columns": len(columns), "named_rows": 0, "named_columns": 0,
            "cells": render(table, rows, columns), "rows": rows, "columns": columns, "left_out_rows": 0,
            "left_out_columns": 0, "ranked_by": None}


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
    if best[:2] == (0, 0.0):
        if len(found) == 1 and _within_caps(found[0], config):
            return _whole(found[0], 1)
        return _refused(NO_MATCH, of_tables=len(found))
    if strength.count(best) > 1:
        return _refused(TIE, of_tables=len(found))
    chosen = strength.index(best)
    table = found[chosen]
    rows, columns, keys = ranked[chosen]
    # The embedding only orders what a cut would choose between, so with no cut it is not asked.
    cut_ahead = (len(table["rows"]) > min(config["fill_rows"], config["max_rows"])
                 or len(columns) - len(keys) > max(config["max_columns"] - len(keys), 1))
    row_extra, column_extra = _embedded(table, keys, claim, embed_with if cut_ahead else None)
    # A column is kept only when named, or all of them when none is. Key columns stand outside it.
    named_columns = [i for i in _order(columns, column_extra) if _matched(columns[i]) and i not in keys]
    others = [i for i in range(len(columns)) if i not in keys]
    wanted_columns = named_columns or others
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
    return dict(fields, selected=True, refused=None, selected_by="labels", cells=render(table, rows_shown, columns_shown), rows=rows_shown,
                columns=columns_shown, left_out_rows=len(table["rows"]) - len(rows_shown),
                left_out_columns=len(table["header"]) - len(columns_shown),
                ranked_by="words_and_embedding" if row_extra is not None else "words")


def declared(rules):
    """The rules whose heading declares `[compare: cells]`."""
    return [r for r in rules or [] if r.get("compare") == COMPARE_CELLS]


def question(config, cells, claim, contracts=None):
    """The narrow question on a claim and its cells; one pass, so a cell's braces stay text. The
    `{tools}` slot holds what the judge agent's declared tools found (`judge_agent.claim_tools`,
    under `contracts`, the shipped ones by default), "" when no contract declares a shown tool."""
    import judge_agent
    slots = {"cells": cells, "claim": claim, "tools": judge_agent.claim_tools(cells, claim, contracts)}
    return re.sub(r"\{(cells|claim|tools)\}", lambda m: slots[m.group(1)], config["decision"]["template"])


def threshold_of(config):
    return choice_decision.threshold(config["decision"]["threshold_family"])


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


def _row(unit, selection, decision):
    """One decided question in the pairing map: identifiers, indexes and numbers, no text."""
    return {"unit_id": unit.get("unit_id"), "selected_by": selection["selected_by"], "rows": selection["rows"],
            "columns": selection["columns"], "of_rows": selection["of_rows"], "of_columns": selection["of_columns"],
            "ranked_by": selection["ranked_by"], "decided": decision["decided"], "settled": decision["settled"],
            "why": decision["why"], "confidence": decision["confidence"], "threshold": decision["threshold"],
            "declared_mass": decision["declared_mass"], "logits_dtype": decision.get("logits_dtype"),
            "answers": {a["label"]: a["probability"] for a in decision["answers"]}}


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
    if any(s["selected_by"] == "labels" for _, s in chosen):
        kept = [(u, s) for u, s in chosen if s["selected_by"] == "labels"]
        calls["whole_tables_left"] = len(chosen) - len(kept)
        chosen = kept
    calls["whole_table"] = sum(1 for _, s in chosen if s["selected_by"] == "whole_table")
    return chosen


def review(units, rule, source_rule_id, ask, config, embed_with=None, fields_present=None, on_kept=None, contracts=None):
    """(records, calls): the rule's claim on each unit's selected cells, put to `ask(user_text) ->
    decision or None`. `calls` holds each decision (`decisions`), what was refused
    (`selection_refused`, a kept record's `refused`) and why anything was not asked (`not_asked`,
    `why`). The declared number of failed calls in a row stops the rule; a raised failure stops it
    at once, named by its type, and what the review holds stays.

    `contracts` are the judge agent's (D-S55): its declared tools fill the question's `{tools}`
    slot and each tool call is one row of `calls["tool_rows"]` (`judge_agent.tool_rows`). With
    {} no tool is declared, the question is the measured one and no row is kept; None reads the
    shipped contracts."""
    import judge_agent
    contracts = judge_agent.shipped_contracts() if contracts is None else contracts
    calls = {"tables": 0, "whole_table": 0, "whole_tables_left": 0, "made": 0, "failed": 0, "unreadable": 0, "unsettled": 0,
             "not_met": 0, "decisions": [], "decision_notes": {}, "selection_refused": [], "refused": [], "stopped": None, "raised": None,
             "not_asked": None, "tool_rows": []}

    def tools(unit, prompt, *rows):
        calls["tool_rows"].extend(judge_agent.tool_rows(judge_agent.CELL_CLAIM, contracts, rule["id"], unit.get("unit_id"),
                                                        prompt, rows))
    records = []
    if threshold_of(config) is None:
        calls["not_asked"] = "no question asked: no threshold measured for " + config["decision"]["threshold_family"]
        calls["why"] = "cells_no_threshold"
        return records, calls
    streak = 0
    try:
        chosen = _selections(units, rule.get("rule") or "", config, embed_with, calls, on_selected=tools)
        if len(chosen) > config["max_units_per_rule"]:
            calls["not_asked"] = "no question asked: %d tables, above the declared %d" % (len(chosen), config["max_units_per_rule"])
            calls["why"] = "cells_too_many"
            return records, calls
        for unit, selection in chosen:
            claim = rule.get("rule") or ""
            prompt = question(config, selection["cells"], claim, contracts)
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
            calls["decisions"].append(_row(unit, selection, decision))
            if cls != "FLAG":
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
    else:
        return None
    return {"unit_id": None, "rule_id": rule_id, "kind": "cell_claim", "reason": reason, "why": why,
            "consumer_agents": [], "status": "stopped"}
