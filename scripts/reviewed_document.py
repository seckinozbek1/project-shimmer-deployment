"""The reviewed document: `deliverables/<doc>/reviewed_document.md` (open item 19, part 2).

A person reads this file to see the review of one document. It is the document under
review in its own words and order, with each finding shown under the part of the
document (the unit) it concerns, and a short header: what was asked, how many findings
of each kind the review made, and what it did not check.

It is a RENDER and decides nothing. Every finding, amendment, count and mark it shows
was made before it is called, by the code that already makes them:

- the amendments and the model findings are the master's own lists (the same objects
  `review_data.json` holds, so the counts here are that file's counts);
- Python's findings are the list `document_summary.md` counts;
- the refusals and the pairs left unchecked are the pairing map's own records
  (`audit/pairing_map.json`);
- the mark on each finding is `finding_record.provenance_mark`, or the mark constant
  itself where no record is at hand (HONEST-OUTPUT-A: a model-written finding carries "Written by a model. Not promoted to an amendment. Not
  checked by Python.");
- an amendment's sentence is its own `comment`, and a Python finding with no amendment is
  said with `paired_review.computed_sentence`, the sentence a comment opens with, or, for a
  comparison with an earlier version, with its reader line.

Every finding given to it is shown exactly once, at its unit or, when its unit's text
cannot be located or it names no unit of this document, in one of two sections after
the document, each saying which; the document's own text, and every text a model or
an agent wrote, is escaped so that none of it can look like a finding block
(`_escape`), except the document's own code blocks and code spans, which Markdown
already shows as written (`_doc_text`); the counts are checked against what was shown
before the text is returned (a RuntimeError beats a silently incomplete deliverable, as in
`summary_generators.render_operative_summary`).

Each agent's raw reply, the judging calls and every registered agent's state are in the
agent record (`run_context.DELIVERABLE_FILENAMES["per_agent_deliverable"]`), which this
file names but does not repeat. Every template here has a row for the second output
language (tr) in `scripts/ui/localization_catalog.js`; the document's own text, the
ids, the figures and a model's own words are kept exactly as they are.
"""
from __future__ import annotations

import re
from pathlib import Path

import amendment_render
import finding_record
import localization
import paired_review
import run_context
import summary_generators

BS = "\\"
TITLE_SUFFIX = ": reviewed document"
INTRO = ("This is the document under review, in its own words and order. Each finding is "
         "shown under the part of the document it concerns.")
ASKED_HEADING = "## What was asked"
FOUND_HEADING = "## What the review found"
NOT_CHECKED_HEADING = "## What was not checked"
DOCUMENT_HEADING = "## The document with its findings"
UNPLACED_HEADING = "## Findings that name no part of this document"
UNPLACED_INTRO = ("These findings name a part this document does not have, or no part at all, "
                  "so they cannot be shown in the text above.")
UNLOCATED_HEADING = "## Findings on parts whose text could not be located"
UNLOCATED_INTRO = ("These findings name a part of this document, but that part's text could not be "
                   "located in the document above, so they are shown here under the part's name.")
UNLOCATED_PART = "Part {unit}:"
NO_FINDING_HERE = "No finding here."

OBJECTIVES_OWN = "- The operator's objectives: "
OBJECTIVES_DEFAULT = "- Objectives: the default review objectives (the operator gave none of their own)."
QUESTION_LINE = "- The operator's question: "
# The registry's size: the rules this review could apply, not a count of the rules
# evaluated on this document (no record gives that number for every review mode).
RULES_FROM = "- Rules in the registry: {n}, read from {files}. Each rule's own words are quoted in {summary}."
RULES_PLAIN = "- Rules in the registry: {n}. Each rule's own words are quoted in {summary}."

COUNT_FIGURES = "- Findings computed by Python from the document's figures: {n}."
COUNT_CHECKED = "- Required fields Python checked in code and found absent: {n}."
COUNT_MODEL = "- Findings written by a model, not checked by Python and not promoted: {n}."
COUNT_AMENDMENTS = ("- Amendments proposed, each built by Python from one of its own findings: {n}. "
                    "They are also listed in {findings} and marked in {docx}.")
COUNT_AMENDMENTS_OTHER = ("- Amendments taken from an agent's own record, not computed by Python: {n}. "
                          "They are also listed in {findings} and marked in {docx}.")
COUNT_REFUSED = "- Answers from a model that Python refused: {n}."
COUNT_UNTYPED = ("- Items a model wrote with no typed record, so not shown at any part here, not checked by "
                 "Python and not promoted: {n}. They are in {record}.")
COUNT_NOT_CHECKED = "- Rules that could not be checked on a part of this document: {n}."
# A count is stated only when the pairing record carries the lists it is made of. The
# paired review writes them (pipeline._paired_convention_review); a wide review builds a
# pairing record too but writes at most `not_judged` into it, and a run whose map failed
# has none, so in both neither count was recorded and none is stated.
REFUSAL_KEYS = ("absence_refused", "uncomputable_refused")
# `suspended` is written by the same paired step only when a rule was withdrawn, so its
# absence beside these two means none was.
UNCHECKED_KEYS = ("not_judged", "judging_calls")
COUNT_REFUSED_UNRECORDED = ("- Answers from a model that Python refused: not recorded, because this review "
                            "kept no record of refused answers for this document.")
COUNT_NOT_CHECKED_UNRECORDED = ("- Rules that could not be checked on a part of this document: not recorded, "
                                "because this review kept no record of its judging calls for this document.")

NOTHING_LEFT = "- Nothing the review planned for this document was left unchecked."
NO_CALL_RECORD = ("- This review kept no record of its judging calls for this document, so this file "
                  "cannot say whether anything it planned was left unchecked.")
NO_PAIRING = ("- The review's record of what it paired for this document is not available, so "
              "this file cannot list what was left unchecked.")
RULE_NOT_GIVEN = "- Rule {rule}: {why}."
SHOWN_AT_UNITS = "- Rules not checked on a single part are shown at that part below."
NO_CALL_AGENTS = "- Registered agents that had made no model call when this file was written: {n} ({agents})."
RECORD_POINTER = ("- Each agent's raw reply, every judging call and every registered agent's state "
                  "are in {record}; so are the advisory editorial board's observations when the "
                  "board ran.")

# The label that opens each block (the mark itself, for every finding).
SUGGESTED = "Suggested change: "
SUGGESTED_TEXT = '"{text}" (amendment {n} in {findings}).'
SUGGESTED_NONE = ("none proposed; the passage is flagged for the operator to decide "
                  "(amendment {n} in {findings}).")
AMENDMENT_FROM_AGENT = "An amendment from {agent}, not computed by Python."
NO_AMENDMENT = "No amendment: "
NO_AMENDMENT_REASONS = {
    "prior": "a comparison with the earlier version never becomes an amendment.",
    "ok": "nothing is wrong here, so no amendment is needed.",
    "conditional": "the rule attaches a condition the figures cannot settle.",
    "advisory": "the rule is advisory, so it makes no amendment.",
    "unknown_severity": "the rule's severity is not one Python recognises, so it makes no amendment.",
    "duplicate": "an amendment for this part and rule already rests on another of Python's findings.",
    "none": "no amendment was built from it.",
}
PRIOR_LEAD = "Compared with the earlier version: "
MODEL_REPORTED = "{agent} reported: "
MODEL_WROTE = "The model wrote: "
PYTHON_ADDS = "Python adds: "
REFUSED_LABEL = "Refused by Python."
REFUSED_LINE = "A model's answer under rule {rule} was refused: {reason}."
# The refusal reasons paired_review.judged_item_refusal returns, each with the reader's
# words (its first four are written there as plain strings, the rest as constants).
REFUSAL_REASONS = {
    "absence claim supplies no quote": "it says a field is absent but quotes nothing from this part",
    "absence claim names no field": "it says a field is absent but does not name the field",
    "claims a field absent that this unit carries": "it says a field is absent that this part states",
    "quotes text that does not appear in this unit": "it quotes text that does not appear in this part",
    paired_review.NO_QUOTE_ABSENCE_RELATION: "it says something is absent but quotes nothing from this part",
    paired_review.NO_FIGURES_FIGURE_RELATION: "it compares figures but gives none",
    paired_review.PRIOR_RELATION_NO_EARLIER_VERSION: "it compares with an earlier version, and none was declared",
    paired_review.CONTRADICTION_NOT_IRREGULAR: "it names a contradiction but does not mark it irregular",
    paired_review.CONTRADICTION_NEEDS_TWO_QUOTES: "it says two passages contradict each other but does not quote both",
    paired_review.CONTRADICTION_SAME_PASSAGE: "it says two passages contradict each other but quotes one passage twice",
    paired_review.CONTRADICTION_NO_UNIT_TEXT: "it says two passages contradict each other and this part has no text to check them against",
    paired_review.CONTRADICTION_QUOTE_TOO_SHORT: "it says two passages contradict each other but a quote is too short to be a passage",
    paired_review.CONTRADICTION_SECOND_QUOTE_NOT_IN_UNIT: "it says two passages contradict each other but the second quote is not in this part",
    paired_review.CONTRADICTION_SECOND_UNIT_NOT_CHECKED: "it says two passages contradict each other but names a second part no check read",
    paired_review.CLAIM_NOT_FROM_CELLS: "it says a claim is not met but comes from no cells Python selected",
    paired_review.CLAIM_RULE_NOT_CELLS: "it says a claim is not met under a rule that does not compare cells",
    paired_review.CLAIM_NOT_IRREGULAR: "it names a claim not met but does not mark it irregular",
    paired_review.CLAIM_NOT_THE_RULE: "it says a claim is not met but does not state the rule's own claim",
    paired_review.CLAIM_CELLS_NOT_IN_UNIT: "it says a claim is not met on cells this part does not write",
    paired_review.RULE_NOT_MET_NOT_FROM_RULE_CHECK: "it says this part does not meet the rule but comes from no rule-check decision",
    paired_review.RULE_NOT_MET_PLAN_NOT_UNCOMPUTABLE: "it says this part does not meet the rule on a question that was not one Python could compute nothing for",
    paired_review.RULE_NOT_MET_NOT_IRREGULAR: "it says this part does not meet the rule but does not mark it irregular",
    paired_review.RULE_NOT_MET_QUOTE_NOT_UNIT: "it says this part does not meet the rule but quotes text that is not this part's",
}
NOT_CHECKED_LABEL = "Not checked."
NOT_CHECKED_LINE = "Rule {rule} on this part: {why}."
WHY_ASSIGNED_ELSEWHERE = "it is assigned to {agents} only, which do not review the document's parts"
WHY_NO_AGENT = "no agent that reviews the document's parts was assigned to it"
WHY_CALL_FAILED = "the call to the model failed, so nothing from its reply was kept"
WHY_SUSPENDED = "it was withdrawn from this part by its own condition"
WHY_PAIRS_PARTLY_STOPPED = "the calls to the model failed and the comparison stopped: what it kept before then is shown, and the pairs left were not judged"
WHY_PAIRS_NOT_PREPARED = "the document could not be prepared for comparing passages, so no call was made"
WHY_PAIRS_SOME_FAILED = "some calls to the model failed, so those pairs were not judged"
WHY_CELLS_IN_WIDE = "it compares a claim with a table's cells, which only a paired review does, so nothing was asked"
WHY_CELLS_NO_THRESHOLD = "it compares a claim with a table's cells, and no threshold has been measured for deciding that, so nothing was asked"
WHY_CELLS_TOO_MANY = "it compares a claim with a table's cells, and this document holds more tables than the declared limit, so nothing was asked"
WHY_CELLS_PARTLY_STOPPED = "the calls to the model failed and the comparison stopped, so some tables were not decided"
WHY_CELLS_SOME_FAILED = "some calls to the model failed, so those tables were not decided"
WHY_COMPARE_IN_WIDE = "it compares passages, which only a paired review does, so no pair was asked"
WHY_TOO_MANY_PASSAGES = "it compares passages, and this document holds more than the declared limit, so no pair was asked"
WHY_NO_THRESHOLD = "it compares passages, and no threshold has been measured for deciding them, so no pair was asked"
WHY_PAIRS_NONE = "it compares passages, and this document offers no pair to compare, so no pair was asked"
WHY_CELLS_NONE = "it compares a claim with a table's cells, and no table here could be selected from, so nothing was asked"
COUNT_DECIDED = "Questions decided from a model's answer probabilities, with no text written: {n}, of which {unsettled} could not be settled."
COUNT_CELLS_NOT_MET = "Claims a model's probabilities say a table's cells do not meet: {n}. No finding is written for these until a relation is ratified."


def _flat(text):
    return " ".join(str(text or "").split())


def _quote(lines):
    """One block of lines as a quotation, set apart from the document's own text."""
    return ["> " + ln if ln else ">" for ln in lines]


def _escape(text):
    """Text this file did not write (the document's own words, a model's or an agent's),
    so that none of it can look like a finding block: every backslash, every `>` (a
    quotation at a line start, after a list marker or anywhere) and every `<` (raw HTML,
    such as a blockquote or a bold tag) is escaped, and so are the bold markers (`**`,
    `__`) every finding block opens with. The backslash goes first, so a backslash
    already in the text cannot cancel an escape added after it. Markdown shows every
    character as written; when the sensitivity layer is active the redaction renders this
    file from scrubbed inputs (`write_from_scrubbed`), and its survivor grep reads the file
    with every escape undone (`sensitivity_layer.scrub`), so an escape can never hide a span."""
    text = str(text or "").replace(BS, BS + BS).replace(">", BS + ">").replace("<", BS + "<")
    return text.replace("**", BS + "*" + BS + "*").replace("__", BS + "_" + BS + "_")


# CommonMark structure the document's own text can carry (PATCH_2 review round 4): an
# opening code fence (up to three spaces, three or more backticks or tildes, an info
# string) and a list item marker.
_FENCE_OPEN = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
_LIST_ITEM = re.compile(r"^ {0,3}(?:[-*+]|\d{1,9}[.)])(?:[ \t]|$)")
# A GitHub-flavoured table splits its cells on a pipe before it reads a code span, so a
# backtick pair with a pipe between them may not be one code span there: it is not
# taken for one.
_SPAN_BREAKERS = "|"


def _columns(line):
    """The width of a line's leading whitespace, a tab reaching the next multiple of 4."""
    col = 0
    for ch in line:
        if ch == " ":
            col += 1
        elif ch == "\t":
            col += 4 - col % 4
        else:
            break
    return col


# A CommonMark line ends at a line feed, a carriage return or the two together, and
# nowhere else (str.splitlines also breaks at a form feed, a vertical tab and other
# separators, where a Markdown reader sees no line break; PATCH_2 review round 4).
_COMMONMARK_LINE = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+\Z")


def _lines(text):
    """The lines of `text` as a CommonMark reader splits them, each with its ending."""
    return _COMMONMARK_LINE.findall(text)


def _code_lines(text):
    """The code block lines of `text`, as `_code_scan` reads them."""
    return _code_scan(text)[0]


def _open_fence(text):
    """The fence `text` leaves open at its end, else None. A Markdown reader runs an
    unclosed fence to the end of the file, so what follows the document must close it."""
    return _code_scan(text)[1]


def _in_code(offset, code, text):
    """True when `offset` stands inside a code block with more of the block after it. A
    finding set there would be shown as code, exactly like the document's own lines.
    `code` lists one region per line, so touching regions are one block."""
    blocks = []
    for start, end in code:
        if blocks and blocks[-1][1] == start:
            blocks[-1][1] = end
        else:
            blocks.append([start, end])
    if _open_fence(text) and blocks and offset >= blocks[-1][0]:
        return True  # an open fence runs to the end of the file, whatever follows here
    return any(s <= offset < e and text[offset:e].strip() for s, e in blocks)


def _code_scan(text):
    """The [start, end) offsets of the lines of `text` a CommonMark reader shows as a
    code block: a fenced block (its fence lines included), and an indented block (four
    columns or more) after a blank line or at the start. Conservative by construction,
    because a line taken for code is shown unescaped: a fence is taken only at the left
    margin or outside a list, and an indented line never after a list item, where it
    could be the item's own text (the list is taken to end only at a line at the margin
    after a blank line, or at a fence at the margin). A line not taken for code is
    escaped, which at worst shows a backslash in a block that was code."""
    out, pos = [], 0
    fence, in_list, after_blank, indented = None, False, True, False
    for line in _lines(text):
        start, pos = pos, pos + len(line)
        body = line.rstrip("\r\n")
        if fence is not None:
            out.append((start, pos))
            if re.match(r"^ {0,3}%s{%d,}[ \t]*$" % (re.escape(fence[0]), len(fence)), body):
                fence = None
            continue
        if not body.strip(" \t"):
            after_blank = True
            continue
        cols = _columns(body)
        if cols >= 4 and not in_list and (after_blank or indented):
            out.append((start, pos))
            indented, after_blank = True, False
            continue
        indented = False
        opened = _FENCE_OPEN.match(body)
        if (opened and not (opened.group(2)[0] == "`" and "`" in opened.group(3))
                and (not opened.group(1) or not in_list)):
            fence, in_list, after_blank = opened.group(2), False, False
            out.append((start, pos))
            continue
        if _LIST_ITEM.match(body):
            in_list = True
        elif cols == 0 and after_blank:
            in_list = False
        after_blank = False
    return out, fence


def _code_spans(line):
    """The [start, end) of each code span on one line, delimiters included, by the
    CommonMark rule: a backtick run not escaped by a backslash opens, the next run of the
    same length closes, and a run with no such closer is plain text. A span is taken
    only within the line, and never across a `_SPAN_BREAKERS` character."""
    spans, i = [], 0
    while i < len(line):
        if line[i] == "\\":
            i += 2
            continue
        if line[i] != "`":
            i += 1
            continue
        j = i
        while j < len(line) and line[j] == "`":
            j += 1
        k, close = j, None
        while k < len(line):
            if line[k] != "`":
                k += 1
                continue
            m = k
            while m < len(line) and line[m] == "`":
                m += 1
            if m - k == j - i:
                close = (k, m)
                break
            k = m
        if close is not None and not any(ch in line[j:close[0]] for ch in _SPAN_BREAKERS):
            spans.append((i, close[1]))
            i = close[1]
        else:
            i = j
    return spans


def _escape_outside_code(text):
    """Document text outside every code region: `_escape`, and every backtick and tilde
    too, so no backtick that was not a code span's delimiter can open one in this file (a
    backslash `_escape` doubled would otherwise free a backtick it escaped), and no fence
    `_code_scan` declined can open as one here."""
    return _escape(text).replace("`", BS + "`").replace("~", BS + "~")


def _doc_text(fragment, offset, code):
    """The document's own words, `fragment` standing at `offset` in the document whose
    code block lines are `code` (`_code_lines`). Inside a code block or a code span the
    text is left exactly as written: Markdown shows it there as written and reads no
    markup in it, so it cannot look like a finding block, and an escape would be shown
    as a backslash. Everything else is escaped (`_escape_outside_code`)."""
    out, pos = [], offset
    for line in _lines(fragment):
        start, pos = pos, pos + len(line)
        if any(s <= start < e for s, e in code):
            out.append(line)
            continue
        cursor, kept = 0, []
        for s, e in _code_spans(line):
            kept += [_escape_outside_code(line[cursor:s]), line[s:e]]
            cursor = e
        out.append("".join(kept) + _escape_outside_code(line[cursor:]))
    return "".join(out)


def _free_text(text):
    """A model's or an agent's own words on one line, escaped (`_escape`)."""
    return _escape(_flat(text))


def _model_note(note):
    """A judging model's note beside Python's finding, escaped (`_escape`)."""
    return _escape(note)


def _reader_text(f):
    """A finding's reader line, escaped (`_escape`): it carries a model's own ids and
    units on a model finding."""
    return _free_text(finding_record.reader_line(f))


def _last_line_at(text, line, cursor):
    """Where `line` stands as a WHOLE line of `text`, at or after `cursor`, or -1. A
    short line found inside a longer one is not its place."""
    at = text.find(line, cursor)
    while at >= 0:
        end = at + len(line)
        if (at == 0 or text[at - 1] == "\n") and (end == len(text) or text[end] in "\r\n"):
            return at
        at = text.find(line, at + 1)
    return -1


def _anchor(text, body, cursor):
    """(start, end) of a unit's text from the cursor: the whole text, else (a table
    row, whose header is shared) its own last line as a whole line; (-1, -1) if neither."""
    at = text.find(body, cursor)
    if at >= 0:
        return at, at + len(body)
    last = [ln for ln in body.splitlines() if ln.strip()][-1]
    at = _last_line_at(text, last, cursor)
    return (at, at + len(last)) if at >= 0 else (-1, -1)


def _skips_a_unit(text, later_units, cursor, at):
    """True when a unit found at `at` would be placed past the place of the next unit
    that can be placed from the cursor: placing it there would leave that unit, and
    every finding under it, behind."""
    following = next((s for s, _ in (_anchor(text, str(u["text"]), cursor) for u in later_units) if s >= 0), None)
    return following is not None and at > following


def _place(text, units):
    """The document as fragments in order: ("text", fragment) for the document's own
    words and ("unit", unit_id) right after the words of each unit. Every character
    of the document is in exactly one text fragment, in order. A unit whose text
    cannot be found from where the previous one ended (a table row, whose header is
    shared) is placed after its own last line, found as a whole line. A unit is never
    placed past the next unit's own place (that would skip the units between); one
    that cannot be placed gets no place, and its findings go to a section after the
    document that names its part and says its text could not be located."""
    units = [u for u in units if str(u.get("text") or "").strip()]
    out, cursor, placed = [], 0, set()
    for i, unit in enumerate(units):
        at, end = _anchor(text, str(unit["text"]), cursor)
        if at < 0:
            continue
        if _skips_a_unit(text, units[i + 1:], cursor, at):
            continue
        out.append(("text", text[cursor:end]))
        out.append(("unit", unit["unit_id"]))
        placed.add(unit["unit_id"])
        cursor = end
    out.append(("text", text[cursor:]))
    return out, placed


def _figure(value):
    """A figure as the join compares it: a number (int, float or a numeric string)
    as a float, so 5, 5.0 and "5" are one figure; anything else as its text."""
    if isinstance(value, bool) or value is None:
        return repr(value)
    try:
        number = float(value.strip()) if isinstance(value, str) else float(value)
    except (TypeError, ValueError, OverflowError):
        return repr(value)
    return repr(number) if number == number else repr(value)


def _key(unit_id, rule_id, relation, value_a, value_b):
    # No identity is carried from a finding to the amendment built from it, so the
    # join is on unit, rule, relation and the two figures compared as numbers.
    return (str(unit_id or ""), str(rule_id or ""), str(relation or ""), _figure(value_a), _figure(value_b))


def _finding_key(f):
    return _key(f.get("unit_id"), finding_record.resolved_rule_id(f), f.get("relation"),
                f.get("value_a"), f.get("value_b"))


def _amendment_key(a):
    return _key(a.get("finding_unit_id"), a.get("finding_rule_id") or a.get("convention_ref"),
                a.get("finding_relation"), a.get("finding_value_a"), a.get("finding_value_b"))


def _amendment_unit(a):
    return a.get("unit_id_repaired_to") or a.get("finding_unit_id")


def _no_amendment_reason(f, amendments, rules_by_id):
    if f.get("relation") in finding_record.PRIOR_RELATIONS:
        return "prior"
    if str(f.get("record_verdict") or "").lower() == "ok":
        return "ok"
    if f.get("conditional_on"):
        return "conditional"
    rule_id = finding_record.resolved_rule_id(f)
    makes, _ = paired_review._severity_makes_amendment(paired_review.severity_of_rule(rule_id, rules_by_id or {}))
    if makes is False:
        return "advisory"
    if makes is None:
        return "unknown_severity"
    if any(_amendment_unit(a) == f.get("unit_id")
           and (a.get("finding_rule_id") or a.get("convention_ref")) == rule_id for a in amendments):
        return "duplicate"
    return "none"


def _sentence_for(f, units, rule_texts):
    """Python's own sentence for a finding that made no amendment: the sentence an
    amendment's comment opens with, or, for a comparison with the earlier version,
    the finding's reader line."""
    if f.get("relation") in finding_record.PRIOR_RELATIONS:
        return localization.text(PRIOR_LEAD) + finding_record.reader_line(f) + "."
    unit = units.get(f.get("unit_id"))
    tokens = f.get("_written_tokens")
    if tokens is None:
        tokens = paired_review.written_tokens(f, units, rule_texts)
    return localization.message(paired_review.computed_sentence(
        dict(f, unit_title=paired_review._unit_title(unit), _written_tokens=tokens)))


def _amendment_block(a, n, finding, names):
    t = localization.text
    if a.get("derived_from") == "computed_finding":
        mark = (finding_record.provenance_mark(finding) if finding is not None else
                t(finding_record.CHECKED_ABSENCE_MARK) if a.get("finding_relation") in finding_record.ABSENCE_RELATIONS
                else t(finding_record.COMPUTED_FINDING_MARK))
    else:
        mark = t(AMENDMENT_FROM_AGENT, agent=_free_text(a.get("agent")) or t(finding_record.NOTE_MODEL_NOT_RECORDED))
    # The comment can end with a model's note, and the proposed text can be a model's.
    lines = ["**%s** %s" % (mark, _free_text(localization.message(_flat(a.get("comment")))))]
    proposed = _free_text(a.get("proposed_text"))
    lines.append(t(SUGGESTED) + (t(SUGGESTED_TEXT, text=proposed, n=n, findings=names["findings"]) if proposed
                                 else t(SUGGESTED_NONE, n=n, findings=names["findings"])))
    return lines


def _python_block(f, reason, units, rule_texts):
    t = localization.text
    # The sentence quotes the document's heading and labels, so it is escaped like them.
    lines = ["**%s** %s" % (finding_record.provenance_mark(f), _free_text(_sentence_for(f, units, rule_texts)))]
    note = _flat(f.get("explanation"))
    if note and f.get("explanation_by") == finding_record.WRITTEN_BY_MODEL:
        # The judging model's sentence beside Python's finding is the model's, said so.
        lines.append(summary_generators.model_note_line(_model_note(note),_free_text(f.get("explanation_model")) or None))
    lines.append(t(NO_AMENDMENT) + t(NO_AMENDMENT_REASONS[reason]))
    return lines


def _model_prose(f):
    """The model's own sentence, whole. It is never cut: a cut could split a span the
    redaction must remove, and the scrub, which matches whole spans, would leave the
    fragment in the file."""
    return _free_text(f.get("explanation") or f.get("reasoning"))


def _model_block(f):
    t = localization.text
    mark = t(finding_record.MODEL_FINDING_MARK)
    # The mark and the finding are on one line, so no line names the finding without it.
    lines = ["**%s** %s%s." % (mark, t(MODEL_REPORTED, agent=_free_text(f.get("agent")) or "?"),
                               _reader_text(f))]
    prose = _model_prose(f)
    if prose:
        lines.append('%s"%s"' % (t(MODEL_WROTE), prose))
    notes = [_free_text(localization.message(n)) for n in f.get("reader_notes") or []]
    if f.get("figures_in_unit") is False and not notes:
        notes.append(t("The unit it names does not state these figures."))
    if notes:
        lines.append(t(PYTHON_ADDS) + " ".join(notes))
    return lines


def _refused_block(entry):
    t = localization.text
    reason = str(entry.get("reason") or "")
    said = t(REFUSAL_REASONS[reason]) if reason in REFUSAL_REASONS else _free_text(localization.message(reason))
    return ["**%s** %s" % (t(REFUSED_LABEL), t(REFUSED_LINE, rule=_free_text(entry.get("rule_id")) or "?", reason=said))]


# The `why` a not-judged row may carry, for a rule its agents were given and could not finish.
WHY_BY_KIND = {"too_many_passages": WHY_TOO_MANY_PASSAGES, "compare_in_wide": WHY_COMPARE_IN_WIDE,
               "pairs_partly_stopped": WHY_PAIRS_PARTLY_STOPPED, "pairs_not_prepared": WHY_PAIRS_NOT_PREPARED,
               "pairs_some_failed": WHY_PAIRS_SOME_FAILED, "no_threshold": WHY_NO_THRESHOLD, "pairs_none": WHY_PAIRS_NONE,
               "cells_none": WHY_CELLS_NONE, "cells_in_wide": WHY_CELLS_IN_WIDE,
               "cells_no_threshold": WHY_CELLS_NO_THRESHOLD, "cells_too_many": WHY_CELLS_TOO_MANY,
               "cells_partly_stopped": WHY_CELLS_PARTLY_STOPPED, "cells_some_failed": WHY_CELLS_SOME_FAILED}


def _why_not_checked(entry):
    t = localization.text
    kind = entry.get("_why")
    if kind == "failed":
        return t(WHY_CALL_FAILED)
    if kind == "suspended":
        return t(WHY_SUSPENDED)
    if kind in WHY_BY_KIND:
        return t(WHY_BY_KIND[kind])
    agents = [str(a) for a in entry.get("consumer_agents") or [] if a]
    return t(WHY_ASSIGNED_ELSEWHERE, agents=", ".join(agents)) if agents else t(WHY_NO_AGENT)


def _not_checked_block(entry):
    t = localization.text
    return ["**%s** %s" % (t(NOT_CHECKED_LABEL),
                           t(NOT_CHECKED_LINE, rule=_free_text(entry.get("rule_id")) or "?", why=_why_not_checked(entry)))]


def master_lists(master):
    """The master's amendments and model findings, the lists review_data.json holds,
    which this file shows and counts."""
    master = master if isinstance(master, dict) else {}
    return ([a for a in master.get("amendments") or [] if isinstance(a, dict)],
            [f for f in master.get(amendment_render.MODEL_FINDINGS_KEY) or [] if isinstance(f, dict)])


def amendment_counts(amendments):
    """(built by Python from its own finding, taken from an agent's record): the
    header counts them apart, because only the first kind is computed."""
    computed = sum(1 for a in amendments if a.get("derived_from") == "computed_finding")
    return computed, len(amendments) - computed


def decided_counts(pairing):
    """The counted lines of the rules decided from probabilities: they were checked, so they are not
    among what was left unchecked, and a cell claim's decision has no finding to show for it."""
    t = localization.text
    rows = [r for key in ("passage_pairs", "cell_claims") for r in (pairing or {}).get(key) or [] if isinstance(r, dict)]
    decided = [d for r in rows for d in r.get("decisions") or []]
    if not decided:
        return []
    lines = [t(COUNT_DECIDED, n=len(decided), unsettled=sum(1 for d in decided if not d.get("settled")))]
    not_met = sum(int(r.get("not_met") or 0) for r in rows)
    return lines + [t(COUNT_CELLS_NOT_MET, n=not_met)] if not_met else lines


def not_checked_entries(pairing):
    """What the pairing map records as left unchecked: a rule no reviewing agent was
    given (per unit, or for the whole document in wide mode), a rule withdrawn from a
    unit by its own condition, and a judged-absence or no-comparison question whose
    call failed (a failed call asked only for a note leaves Python's finding standing,
    so it is not here)."""
    pairing = pairing or {}
    out = [dict(e, _why=e.get("why") or "not_given") for e in pairing.get("not_judged") or [] if isinstance(e, dict)]
    out += [dict(e, _why="suspended") for e in pairing.get("suspended") or [] if isinstance(e, dict)]
    out += [dict(c, _why="failed") for c in pairing.get("judging_calls") or []
            if isinstance(c, dict) and c.get("outcome") == "reply_failed"
            and c.get("plan_kind") in (paired_review.JUDGED_ABSENCE_PLAN, paired_review.UNCOMPUTABLE_PLAN)]
    return out


def refused_entries(pairing):
    """The model answers Python refused, from the pairing map (judged absences and
    D-068's answers where Python could compute nothing)."""
    pairing = pairing or {}
    return [e for key in ("absence_refused", "uncomputable_refused")
            for e in pairing.get(key) or [] if isinstance(e, dict)]


def _recorded(pairing, keys):
    """True when the pairing record carries every list in `keys` (see REFUSAL_KEYS)."""
    return isinstance(pairing, dict) and all(k in pairing for k in keys)


def _pairing_counts(pairing, refused, unchecked):
    """The header's refusal and unchecked-rule counts: the pairing map's, where it
    carries the lists they are made of (a paired review), or said not to be recorded
    rather than stated as 0 (a wide review, whose pairing record lacks them, or no
    pairing record at all)."""
    t = localization.text
    return [t(COUNT_REFUSED, n=len(refused)) if _recorded(pairing, REFUSAL_KEYS) else t(COUNT_REFUSED_UNRECORDED),
            t(COUNT_NOT_CHECKED, n=len(unchecked)) if _recorded(pairing, UNCHECKED_KEYS)
            else t(COUNT_NOT_CHECKED_UNRECORDED)]


def _where(unit_id, placed, units):
    """Where a finding on `unit_id` is shown: at its placed unit (the unit id); in the
    section of parts whose text could not be located (("unlocated", unit_id)), for a
    unit of this document that has no place; or with the findings that name no part of
    this document (None)."""
    if unit_id in placed:
        return unit_id
    if unit_id in units:
        return ("unlocated", unit_id)
    return None


def write_from_scrubbed(info, scrubbed_master, scrubbed_text, scrub, activation=None):
    """Write the file again from scrubbed inputs (the redaction phase's render step, run
    only when the sensitivity layer is active), the way the master's deliverables are:
    every span is gone before the renderer escapes anything or sets a finding into the
    text, so neither can hide or split one. `info` is the document's deliverable record;
    `scrub` scrubs an object's free text; `activation` is the activation record as it
    stands now, since the redaction's own calls came after phase 6. With no recorded inputs
    nothing is rendered, and the on-disk scrub and the survivor grep still run on the file."""
    inputs = info.get("reviewed_render_inputs")
    if inputs:
        kept = ("document_text", "master", "output_language", "activation")
        scrubbed = dict(scrub({k: v for k, v in inputs.items() if k not in kept}),
                        document_text=scrubbed_text, master=scrubbed_master,
                        activation=scrub(activation if activation is not None else inputs.get("activation")),
                        output_language=inputs.get("output_language"))
        Path(info["reviewed_document"]).write_text(render(**scrubbed), encoding="utf-8")


def ship_memo(source, destination, info):
    """Put a draft run's memo in the deliverables. The memo is the document under review,
    so where phase 9 scrubbed it (`scrubbed_body`, set by the redaction stage) it ships that
    way, and otherwise as written: with the layer off, and with it on when the operator
    waived redaction, no operator rule is in force or the document had no master."""
    scrubbed = (info or {}).get("scrubbed_body")
    text = Path(source).read_text(encoding="utf-8") if scrubbed is None else scrubbed
    Path(destination).write_text(text, encoding="utf-8")


@localization.presentation
def render(*, document_id, document_name, document_text, master, python_findings, pairing=None,
           rules=(), source_files=(), objectives="", question="", activation=None, untyped_items=0) -> str:
    """The reviewed document as Markdown, in the run's output language.

    master: this document's master (`amendments` and `model_findings_not_promoted` are
    read). python_findings: Python's findings for the document (stamped `written_by`).
    pairing: the document's pairing record (a paired review's carries the refusal and
    judging-call lists, a wide review's does not), or None when none was built. rules: the registry's rules.
    source_files: the files the rules were read from. objectives: the operator's own
    objectives, empty when the run used the default ones. question: the operator's
    question, echoed and never parsed. activation: the run's agent activation record.
    untyped_items: how many items the run's agents wrote with no typed record, which no
    list here holds."""
    t = localization.text
    names = {key: run_context.DELIVERABLE_FILENAMES[value] for key, value in (
        ("findings", "amendments_md"), ("docx", "amendments_docx"), ("summary", "operative_summary"),
        ("record", "per_agent_deliverable"))}
    text = str(document_text or "")
    amendments, model = master_lists(master)
    python = [f for f in python_findings or [] if isinstance(f, dict) and not finding_record.is_model_written(f)]
    rules = [r for r in rules or [] if isinstance(r, dict) and r.get("id")]
    rules_by_id = {str(r["id"]): r for r in rules}
    rule_texts = {str(r["id"]): r.get("rule") for r in rules}
    refused = refused_entries(pairing)
    unchecked = not_checked_entries(pairing)
    unit_list = sorted(paired_review.unit_texts_for(text, document_id).values(), key=lambda u: u.get("index", 0))
    units = {u["unit_id"]: u for u in unit_list}
    fragments, placed = _place(text, unit_list)

    # Each amendment is joined to the one Python finding it was built from (same unit,
    # rule, relation and figures), so that finding is shown once, as the amendment.
    remaining = list(python)
    joined = []
    for n, a in enumerate(amendments, 1):
        match = next((f for f in remaining if _finding_key(f) == _amendment_key(a)), None)
        if match is not None:
            remaining.remove(match)
        joined.append((n, a, match))

    blocks = {}
    unlocated = []

    def at(unit_id):
        where = _where(unit_id, placed, units)
        if isinstance(where, tuple) and where[1] not in unlocated:
            unlocated.append(where[1])
        return blocks.setdefault(where, [])

    for n, a, match in joined:
        at(_amendment_unit(a)).append(("amendment", _amendment_block(a, n, match, names)))
    for f in remaining:
        at(f.get("unit_id")).append(("python", _python_block(
            f, _no_amendment_reason(f, amendments, rules_by_id), units, rule_texts)))
    for f in model:
        at(f.get("unit_id")).append(("model", _model_block(f)))
    for e in refused:
        at(e.get("unit_id")).append(("refused", _refused_block(e)))
    document_level_unchecked = [e for e in unchecked if not e.get("unit_id")]
    for e in unchecked:
        if e.get("unit_id"):
            at(e.get("unit_id")).append(("unchecked", _not_checked_block(e)))

    checked = sum(1 for f in python if f.get("relation") in finding_record.ABSENCE_RELATIONS)
    lines = ["# %s%s" % (document_name or document_id, t(TITLE_SUFFIX)), "", t(INTRO), "",
             t(ASKED_HEADING), ""]
    lines.append(t(OBJECTIVES_OWN) + '"%s"' % _flat(objectives) if _flat(objectives) else t(OBJECTIVES_DEFAULT))
    if _flat(question):
        lines.append(t(QUESTION_LINE) + _flat(question))
    files = ", ".join(str(s) for s in source_files or [] if s)
    lines.append(t(RULES_FROM, n=len(rules), files=files, summary=names["summary"]) if files
                 else t(RULES_PLAIN, n=len(rules), summary=names["summary"]))
    computed = amendment_counts(amendments)[0]
    lines += ["", t(FOUND_HEADING), "",
              t(COUNT_FIGURES, n=len(python) - checked), t(COUNT_CHECKED, n=checked),
              t(COUNT_MODEL, n=len(model))] + ([t(COUNT_UNTYPED, n=untyped_items, record=names["record"])] if untyped_items else []) + [
              t(COUNT_AMENDMENTS, n=computed, findings=names["findings"], docx=names["docx"]),
              t(COUNT_AMENDMENTS_OTHER, n=len(amendments) - computed, findings=names["findings"],
                docx=names["docx"])]
    lines += _pairing_counts(pairing, refused, unchecked) + decided_counts(pairing) + ["", t(NOT_CHECKED_HEADING), ""]
    if pairing is None:
        lines.append(t(NO_PAIRING))
    elif not _recorded(pairing, UNCHECKED_KEYS):
        lines.append(t(NO_CALL_RECORD))
    elif not unchecked:
        lines.append(t(NOTHING_LEFT))
    for e in document_level_unchecked:
        lines.append(t(RULE_NOT_GIVEN, rule=e.get("rule_id") or "?", why=_why_not_checked(e)))
    if len(document_level_unchecked) < len(unchecked):
        lines.append(t(SHOWN_AT_UNITS))
    silent = [str(r.get("agent")) for r in (activation or {}).get("agent_states") or []
              if isinstance(r, dict) and r.get("agent") and not r.get("actual_calls")]
    if silent:
        lines.append(t(NO_CALL_AGENTS, n=len(silent), agents=", ".join(silent)))
    lines += [t(RECORD_POINTER, record=names["record"]), "", "---", "", t(DOCUMENT_HEADING), ""]

    shown = {"amendment": 0, "python": 0, "model": 0}

    def emit(entries):
        out = []
        for kind, block in entries:
            if out:
                out.append(">")
            out += _quote(block)
            if kind in shown:
                shown[kind] += 1
        return out

    code = _code_lines(text)
    offset = 0
    waiting = []

    def shown_at(unit_id):
        return (emit(blocks.get(unit_id)) if blocks.get(unit_id) else _quote([t(NO_FINDING_HERE)])) + [""]

    for kind, value in fragments:
        if kind == "text":
            start, offset = offset, offset + len(value)
            if value.strip():
                lead = len(value) - len(value.lstrip("\n"))
                lines += [_doc_text(value.strip("\n"), start + lead, code), ""]
            continue
        # A unit can end inside a code block (a line that looks like a heading): what
        # concerns it waits until the block ends, or it would be shown as code.
        waiting.append(value)
        if not _in_code(offset, code, text):
            for unit_id in waiting:
                lines += shown_at(unit_id)
            waiting = []
    fence = _open_fence(text)
    if fence:
        lines += [fence, ""]
    for unit_id in waiting:
        lines += shown_at(unit_id)
    if unlocated:
        lines += ["---", "", t(UNLOCATED_HEADING), "", t(UNLOCATED_INTRO), ""]
        for unit_id in unlocated:
            lines += [t(UNLOCATED_PART, unit=unit_id), ""] + emit(blocks[("unlocated", unit_id)]) + [""]
    if blocks.get(None):
        lines += ["---", "", t(UNPLACED_HEADING), "", t(UNPLACED_INTRO), ""] + emit(blocks[None]) + [""]
    if (shown["amendment"], shown["python"], shown["model"]) != (len(amendments), len(remaining), len(model)):
        raise RuntimeError("reviewed_document.render: %d amendments, %d other Python findings and %d model "
                           "findings given, %d, %d and %d shown; a finding would have been silently dropped"
                           % (len(amendments), len(remaining), len(model),
                              shown["amendment"], shown["python"], shown["model"]))
    return "\n".join(lines).rstrip("\n") + "\n"
