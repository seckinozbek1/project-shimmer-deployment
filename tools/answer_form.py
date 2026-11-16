"""One reading of a model answer's FORM, for every parser and scorer (D-663, standing order 82, #279).

No answer is dropped for its form alone: leading or trailing spaces, case, surrounding quotes or emphasis
marks, a number written for a string, a list for a single value or the reverse, stray punctuation at either end,
code fences. Every score-time reader of a model's saved answer (the scorers under tools/ and the re-readers of
saved raw replies, tools/reread_replies.py) reads its answer fields through this module, the same way for every
arm (system, B1, cloud), so a form never decides a score. The runtime parsers inside bound files (scripts/,
benchmark/adapters/, benchmark/baselines/: every sealed bundle carries them) stay as they are until the next
re-seal (lead, 15 November 18:57; docs/loop/stages/PARSE_SWEEP.md lists them).

Form only, never content (WORDS-A): nothing here guesses what a word means. There is no fuzzy match, no
synonym table, no edit distance and no prefix match; a value is read as a declared value only when, with its
form taken off, it IS that value, and when two declared values would read alike the answer is refused as
ambiguous. An answer that still cannot be read comes back with a reason name from REASONS, which the caller
counts (`Drops`) and prints in its score report.

Standard library only, under tools/, which no sealed bundle carries."""

from __future__ import annotations

import re

# The reasons an answer field is still not read, the only names a caller counts drops under.
EMPTY = "empty"                    # nothing left once the form is taken off, or no value at all
NOT_TEXT = "not_text"              # a value of another type (an object, a boolean, a fraction)
LIST_NOT_ONE = "list_not_one"      # a list where one value is asked, holding none or several
NOT_DECLARED = "not_declared"      # a value that is none of the declared values
AMBIGUOUS = "ambiguous"            # two declared values read alike once their form is taken off
NO_OBJECT = "no_json_object"       # no JSON object in the reply
JSON_INVALID = "json_invalid"      # a JSON object that does not parse, even repaired
NOT_OBJECT = "not_an_object"       # an entry of a list of objects that is no object
DUPLICATE = "duplicate"            # a second entry for one id, the first kept
NOT_ASKED = "not_asked"            # a piece the run never put to its next step (an audit it never asked)
REASONS = (EMPTY, NOT_TEXT, LIST_NOT_ONE, NOT_DECLARED, AMBIGUOUS, NO_OBJECT, JSON_INVALID, NOT_OBJECT, DUPLICATE,
           NOT_ASKED)
# Counted, never dropped: a reply holding more than one JSON object; the last one is read (lead 18:57).
SEVERAL_OBJECTS = "several_objects_last_read"
NOTES = (SEVERAL_OBJECTS,)

# A line that is only a code fence, with or without its language tag.
FENCE = re.compile(r"^\s*```[^`\s]*\s*$")
# Marks a model puts around a whole answer, taken off only as a matched pair at both ends.
QUOTE_PAIRS = (('"', '"'), ("'", "'"), ("`", "`"), ("“", "”"), ("‘", "’"))
EMPHASIS_PAIRS = (("**", "**"), ("__", "__"), ("*", "*"))
# Punctuation left at either end of a value, never inside it ("3.1" keeps its point, "3.1." loses the last).
STRAY = ".,;:!?"
# Written between the words of one value: "no_conflict", "no conflict" and "no  conflict" are one form.
SEPARATORS = ("_",)


def unfence(text):
    """The text without its code-fence lines (a reply wrapped in ```json ... ``` is read as its content)."""
    if not isinstance(text, str):
        return text
    return "\n".join(line for line in text.splitlines() if not FENCE.match(line))


def _trim(text):
    return text.strip()


def _fold(text):
    return text.casefold()


def integer_text(value):
    """A JSON integer as its text (7 is read as "7"); a boolean is not an integer here; anything else as it is.
    A fraction (7.0) is left as it is: its text is not the integer's."""
    return str(value) if isinstance(value, int) and not isinstance(value, bool) else value


def single(value):
    """A list of exactly one value is that value; anything else as it is."""
    return value[0] if isinstance(value, list) and len(value) == 1 else value


def as_list(value):
    """A field asked as a list: a list as it is, None as no entries, one value as a list of one."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def bare(text):
    """The text with its form taken off: outer whitespace, a matched pair of quotes or emphasis marks around the
    whole, stray punctuation at either end, repeated until nothing changes. Inner text is never touched."""
    previous = None
    while text != previous:
        previous = text
        text = _trim(text)
        for opening, closing in QUOTE_PAIRS + EMPHASIS_PAIRS:
            if len(text) >= len(opening) + len(closing) and text.startswith(opening) and text.endswith(closing):
                text = text[len(opening):len(text) - len(closing)]
                break
        text = text.strip(STRAY) if STRAY else text
    return text


def key(text):
    """The comparison key of one value: its form taken off, case folded, separators and runs of whitespace one
    space. Two values are the same answer when their keys are equal, and only then."""
    text = _fold(bare(str(text)))
    for sep in SEPARATORS:
        text = text.replace(sep, " ")
    return " ".join(text.split())


def one_value(value):
    """(text, None) or (None, reason): one answer value in its written form, before any comparison."""
    value = integer_text(single(value))
    if isinstance(value, list):
        return None, LIST_NOT_ONE
    if value is None:
        return None, EMPTY
    if not isinstance(value, str):
        return None, NOT_TEXT
    return value, None


def match(value, declared):
    """(the declared value, None) or (None, reason): `value` read as one of `declared` by its form only."""
    text, why = one_value(value)
    if why:
        return None, why
    wanted = key(text)
    if not wanted:
        return None, EMPTY
    hits = sorted({d for d in declared if key(d) == wanted}, key=str)
    if len(hits) > 1:
        return None, AMBIGUOUS
    if not hits:
        return None, NOT_DECLARED
    return hits[0], None


def match_all(values, declared):
    """([declared values, in order, each once], [reasons of the entries not read]) of a field asked as a list."""
    kept, why = [], []
    for v in as_list(values):
        got, reason = match(v, declared)
        if reason:
            why.append(reason)
        elif got not in kept:
            kept.append(got)
    return kept, why


class Drops:
    """The count of answer fields not read, by field and reason; printed in every score report."""

    def __init__(self):
        self.counts = {}

    def add(self, field, reason):
        if reason not in REASONS + NOTES:
            raise ValueError("a drop is counted under one of answer_form.REASONS, not %r" % (reason,))
        by_reason = self.counts.setdefault(field, {})
        by_reason[reason] = by_reason.get(reason, 0) + 1

    def merge(self, other):
        for field, by_reason in (other.counts if isinstance(other, Drops) else other or {}).items():
            for reason, n in by_reason.items():
                for _ in range(n):
                    self.add(field, reason)
        return self

    def total(self):
        return sum(n for by_reason in self.counts.values() for n in by_reason.values())

    def as_dict(self):
        return {f: dict(sorted(r.items())) for f, r in sorted(self.counts.items())}


_BAD_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')


def _objects(text):
    """The spans of the top-level {...} in `text`, braces inside JSON strings not counted."""
    spans, depth, start, in_string, escaped = [], 0, None, False, False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"' and depth > 0:
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0:
                spans.append((start, i + 1))
    return spans


def _loads(candidate):
    """The JSON value of one candidate: as written, else with each backslash that starts no JSON escape
    doubled, else with raw line breaks inside strings admitted; ValueError when none parses."""
    import json
    for attempt in (lambda c: json.loads(c), lambda c: json.loads(_BAD_ESCAPE.sub(r"\\\\", c)),
                    lambda c: json.loads(_BAD_ESCAPE.sub(r"\\\\", c), strict=False)):
        try:
            return attempt(candidate)
        except ValueError:
            continue
    raise ValueError("not JSON")


def last_object(text):
    """(object, None, several) or (None, reason, several): the LAST top-level JSON object of the reply that
    parses, its fence lines dropped (one rule for every reader, lead 18:57). `several` is True when the reply
    holds more than one object that parses: counted as several_objects_last_read, never dropped."""
    if not isinstance(text, str) or not text.strip():
        return None, EMPTY, False
    text = unfence(text)
    parsed = []
    for start, end in _objects(text):
        try:
            value = _loads(text[start:end])
        except ValueError:
            continue
        if isinstance(value, dict):
            parsed.append(value)
    if parsed:
        return parsed[-1], None, len(parsed) > 1
    return None, (JSON_INVALID if _objects(text) else NO_OBJECT), False


# A field label a model writes before its answer ("Answer: supported", "Grade: 2"): letters and spaces, then a
# colon, at the very start. Taken off as form when what follows is a declared answer.
_LABEL = re.compile(r"^[^\W\d_][^\W\d_ ]*(?: [^\W\d_]+){0,2}\s*:\s*")
# Where a leading answer ends when the model goes on after it: a comma, semicolon, point, colon, bracket,
# dash or line break.
_AFTER = re.compile(r"\s*(?:[,;.:!?(\[]|\s-\s|\n)")


def leading(text, declared):
    """(declared value, None) or (None, reason): a reply that IS one declared answer, or that opens with one
    and goes on after a boundary ("Supported, because ...", "Cannot tell. The text ..."), its fence lines and
    a leading field label taken off. The answer must stand whole before the boundary: a prefix of a word is
    never read, and two declared answers reading alike refuse as ambiguous."""
    if not isinstance(text, str) or not text.strip():
        return None, EMPTY
    lines = [line for line in unfence(text).splitlines() if line.strip()]
    if not lines:
        return None, EMPTY
    first = lines[0].strip()
    best = (None, NOT_DECLARED)
    for line in (first, _LABEL.sub("", first, count=1)):
        for candidate in (line, _AFTER.split(bare(line), maxsplit=1)[0]):
            got, why = match(candidate, declared)
            if got is not None or why == AMBIGUOUS:
                return got, why
    return best
