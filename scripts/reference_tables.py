"""Bands read from the reference corpus's own tables, evaluated without a model.

H5 put the arithmetic in Python and read a band out of a RULE's own text. That
left a gap the H7 scoring made visible: the bands that matter most do not live in
the rule at all, they live in a TABLE in the reference corpus, and the rule only
points at it. Those pairs were computed as far as the figures allowed and then
handed to a model to judge against retrieved prose, which is exactly the job the
model is worst at.

This module closes that gap. It reads the reference corpus's markdown tables into
structured records, matches a unit of the document under review to a table ROW by
the unit's own labelled fields, and hands the resulting (low, high, unit) to the
same comparison code H5 already proved. Python decides; the model is not asked.

Nothing here is domain-specific and nothing can be (S5). Five mechanisms carry the
whole module and every one of them is structural:

  * A RANGE IS TWO NUMBERS IN ONE CELL. A cell holding exactly two quantities of
    the same unit, the first not greater than the second, separated by a short run
    of non-numeric text, is a range. No word for "to" appears here, in any
    language, because none is needed: the shape is the signal.
  * A UNIT COMES FROM THE HEADER, and where the header writes it in prose the
    reading is SELF-VALIDATING. "kes per qm" is accepted as "kes/qm" only
    because "kes/qm" is a unit THE DOCUMENT ITSELF WRITES. An interpretation that
    composes to a unit the document never uses is rejected rather than guessed at,
    so the module can never invent a unit, and no connector word is hardcoded.
    Both word orders are tried, since which of the two tokens is the numerator is
    itself a language assumption, and a phrase that composes both ways is refused.
  * KEY COLUMNS ARE LEARNED, from the rule text that cites the table and from
    which columns discriminate rows. No column name is hardcoded.
  * A ROW MATCHES A UNIT BY WORD CONTAINMENT over the unit's own labelled field
    VALUES. The most specific matching row wins; a tie is refused rather than
    broken, because a wrong row is a wrong band and a wrong band is a false
    finding.
  * A FIGURE IS READ FROM A VALUE COLUMN BY LABEL EQUALITY (R6, the earlier
    version of a document): a document label equal, word for word, to a key cell
    identifies that row, and the row's one value column supplies the figure. Ties
    are refused both ways. This identifies a row, never a round: which document
    is the earlier version is the operator's declaration, not an inference.

Deliberate limits, recorded rather than hidden:

  * A key cell that encodes a NUMERIC COMPARISON in prose, keyed by a threshold and
    a direction word rather than by a name, cannot be matched by word containment,
    and is refused as a tie rather than guessed. Resolving it would need a list of
    direction words, which is a domain and language leak of exactly the kind the
    vocabulary probe exists to catch. Such a table yields no band and no finding.
  * A band stated in PROSE rather than in a table is not read here, UNLESS the
    prose has the one shape parse_prose_bands reads: a label, a colon, and a
    range in the same sentence ("Class-A sensor: standard tolerance band 20 to
    60 units."). That shape is a table with the punctuation removed, not a
    judgment, and reading it is not corpus-tuning: the reference material is
    read as it was written, nothing about it is rewritten, and the same refusal
    discipline applies (RANGE_MAX_GAP, one range per sentence, a tie refused).
    A sentence with two figures that are not a labelled range of one unit is
    left alone; the rule-text path (paired_review.bounds_from_rule) still
    covers a rule that states its own numbers.
"""

from __future__ import annotations

import re

import pairing_map

# The two bounds of a range may be separated by at most this many characters of
# non-numeric text. Long enough for a connector word in any language, short enough
# that two unrelated figures in one prose cell are not read as a band.
RANGE_MAX_GAP = 12

# A prose unit is at most this many tokens: a numerator, a connector of any
# length in any language, and a denominator. Only the first and last tokens are
# read, so a longer connector costs nothing; the cap exists to stop a whole
# parenthetical sentence being read as a unit.
PROSE_UNIT_MAX_TOKENS = 4

# A labelled prose band's own label, "Class-A sensor" in "Class-A sensor:
# standard tolerance band 20 to 60 units.", is at most this many characters
# before the colon. Long enough for a real label, short enough that a colon
# ending a much longer clause is not mistaken for one.
PROSE_LABEL_MAX_CHARS = 48

# A sentence boundary: a period, question mark or exclamation mark followed by
# whitespace, or the end of the text. Does not split on a period inside a
# number (RANGE_MAX_GAP already keeps the two bounds of a range close together,
# so a decimal point never reaches this split).
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

_QUANTITY = None  # bound lazily from paired_review to avoid an import cycle


def _quantity_re():
    global _QUANTITY
    if _QUANTITY is None:
        import paired_review
        _QUANTITY = paired_review._QUANTITY
    return _QUANTITY


def _norm_number(token):
    import paired_review
    return paired_review.norm_number(token)


def _unit_exponents(unit_str):
    import paired_review
    return paired_review.unit_exponents(unit_str)


def _unit_str(exponents):
    import paired_review
    return paired_review._unit_str(exponents)


def _words(text):
    """Content words of a string, tokenised EXACTLY as a field label is.

    refine R3: this delegates to pairing_map._norm_label rather than running its
    own split. It used to have its own regex, and the two disagreed twice over: a
    different script range, and a minimum word length the label side applied and
    this side did not. The disagreement was invisible and total, because
    `set(headers[i]) <= rule_words` at the containment test compares one side's
    tokens against the other's. Two tokenisers that must agree are one tokeniser.
    """
    return set(pairing_map._norm_label(text))


# ---------------------------------------------------------------------------
# units


def document_unit_tokens(text):
    """Every unit string the document writes, from its label lines and its table
    headers. This is the vocabulary a prose unit is validated against."""
    import paired_review

    units = set()
    for line in (text or "").splitlines():
        m = pairing_map._LABEL_LINE.match(line)
        if m:
            q = paired_review.first_quantity(m.group(2))
            if q and q[1]:
                units.add(q[1])
    for block in pairing_map._table_blocks(text or ""):
        if len(block) < 2 or not pairing_map._TABLE_SEP.match(block[1]):
            continue
        for cell in block[0].strip().strip("|").split("|"):
            unit = paired_review._header_unit(cell)
            if unit:
                units.add(unit)
        for row in block[2:]:
            for cell in row.strip().strip("|").split("|"):
                q = paired_review.first_quantity(cell)
                if q and q[1]:
                    units.add(q[1])
    # R6: a multi-word unit the document writes after a figure more than once is
    # part of its vocabulary too, and a figure followed by that phrase reads whole.
    units |= paired_review.unit_phrases(text or "")
    return units


def resolve_unit(raw, known_units=()):
    """A header's declared unit as a unit string, or "".

    Two readings, in order. A parenthetical that is already unit-shaped
    ("qm/zed") is taken as it stands. A parenthetical written in prose
    ("kes per qm") is composed from its first and last tokens, each mapped to a
    unit the document actually writes (exactly, or as the unique document unit
    that is a prefix of it, which is how an abbreviation is recognised inside its
    spelled-out form). BOTH orders are tried, because which token is the
    numerator is a language assumption. A composition is ACCEPTED ONLY IF the
    result is itself a unit the document writes, and only if exactly one order
    composes. That is what makes this safe without a connector word list: a
    reading the document does not corroborate is discarded.
    """
    text = str(raw or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"[A-Za-z%][A-Za-z0-9/%·*-]*", text):
        return text
    tokens = [t for t in re.split(r"\s+", text) if t]
    if not (2 <= len(tokens) <= PROSE_UNIT_MAX_TOKENS):
        return ""
    known = {str(u) for u in known_units if u}
    if not known:
        return ""

    def _as_known(token):
        # refine R3: strip only what cannot be part of a unit token, rather than
        # keeping an ASCII allowlist. The allowlist scrubbed a currency symbol or
        # any non-Latin unit to the empty string, so the column simply had no unit
        # and the band was dropped.
        token = re.sub(r"[\d\s()\[\].,;:!?]+", "", token)
        if not token:
            return None
        if token in known:
            return token
        candidates = {u for u in known
                      if not any(ch.isdigit() for ch in u)
                      and token.lower().startswith(u.lower())}
        return next(iter(candidates)) if len(candidates) == 1 else None

    # refine R3: try BOTH orders and refuse a tie. Reading the first token as the
    # numerator and the last as the denominator assumes one word order, and many
    # languages write the same phrase the other way round. The order was the
    # hidden connector the module claimed not to have. Self-validation still does
    # the real work: an order is accepted only when it composes to a unit the
    # document itself writes, and if BOTH orders compose, that is an ambiguity and
    # is refused rather than broken, exactly as match_row refuses a tied row.
    head, tail = _as_known(tokens[0]), _as_known(tokens[-1])
    if not head or not tail:
        return ""
    accepted = []
    for numerator, denominator in ((head, tail), (tail, head)):
        composed_exp = _unit_exponents("%s/%s" % (numerator, denominator))
        for candidate in known:
            if _unit_exponents(candidate) == composed_exp and candidate not in accepted:
                accepted.append(candidate)
    return accepted[0] if len(accepted) == 1 else ""


# ---------------------------------------------------------------------------
# parsing a table


def _cell_quantities(cell):
    """Every (value, unit, start, end) in a cell, in order."""
    import paired_review
    # One reader for every figure (R6): a currency written before the number is
    # read here exactly as it is in a label line.
    return paired_review.quantities(cell)


def _accept_cell_unit(raw, fallback_unit):
    """The unit of one number inside a cell, given what the column declares.

    The quantity regex takes whatever word follows a number as its unit, which is
    right in a table cell and wrong in a range: between the two bounds of a range
    the word following the first number is the connector, not a unit. Rather than
    knowing any connector word, the column's own declared unit is the arbiter. A token that does not
    agree with it is discarded in its favour; where the column declares nothing,
    the cell's own token stands, and two disagreeing tokens then simply fail to
    form a range."""
    if not raw:
        return fallback_unit
    if not fallback_unit:
        return raw
    if _unit_exponents(raw) == _unit_exponents(fallback_unit):
        return raw
    return fallback_unit


def cell_range(cell, fallback_unit=""):
    """(low, high, unit) when a cell states a range, else None.

    A range is exactly two quantities, of the same unit (or of no unit, taking the
    column's), the first not greater than the second, separated by at most
    RANGE_MAX_GAP characters of non-numeric text. Anything else is not a range,
    including a cell with three numbers, which is prose."""
    quantities = _cell_quantities(cell)
    if len(quantities) != 2:
        return None
    (lo, lo_unit, _, lo_end), (hi, hi_unit, hi_start, _) = quantities
    if hi_start - lo_end > RANGE_MAX_GAP:
        return None
    gap = str(cell)[lo_end:hi_start]
    if re.search(r"\d", gap):
        return None
    unit_a = _accept_cell_unit(lo_unit, fallback_unit)
    unit_b = _accept_cell_unit(hi_unit, fallback_unit)
    if not fallback_unit and _unit_exponents(unit_a) != _unit_exponents(unit_b):
        # No column unit to arbitrate, and the two bounds disagree. In "a CONNECTOR
        # b UNIT" the unit follows the LAST figure, so a token attached to the first
        # figure alone is the connector, not a unit. Structural, and it needs no
        # connector word: "4 to 7 kg" resolves to kg, "4 kg to 7 kg" already agrees,
        # and a range written with a dash carries no token on either bound. Found
        # when a real reference table wrote its unit in a column of its own, which
        # left the header with nothing to arbitrate with.
        unit_a = unit_b
    if _unit_exponents(unit_a) != _unit_exponents(unit_b):
        return None
    if lo > hi and hi < 0 <= lo and hi_start == lo_end:
        # An ASCII hyphen between two figures is consumed as the second one's SIGN,
        # so "135-145" reads as 135 and -145 and is refused as descending. An EMPTY
        # gap between the two matches is the tell: nothing separated them except the
        # character the number pattern swallowed. An en-dash range never hits this,
        # which is why the first real table to exercise it did so only by writing a
        # hyphen. Structural, and it cannot fire where a real separator exists.
        hi = -hi
    if lo > hi:
        return None
    return (lo, hi, _unit_str(_unit_exponents(unit_a)) if unit_a else "")


def parse_table(block, *, ref_id="", document_id="", known_units=()):
    """One markdown table block as a structured record, or None.

    Columns are classified from their body cells, never from their names:
      range  every non-empty cell states a range (see cell_range)
      value  every non-empty cell states a single quantity
      text   anything else
    """
    import paired_review

    if len(block) < 3 or not pairing_map._TABLE_SEP.match(block[1]):
        return None
    raw_headers = [c.strip() for c in block[0].strip().strip("|").split("|")]
    # The label a header carries once its UNIT parenthetical is taken off. A
    # header writes its unit in brackets, and _norm_label folds those words into
    # the label, so a header like "Price band (kes per qm)" would normalise to
    # ('price', 'band', 'kes'). Testing whether a rule names that column then
    # demands the rule also write out the unit, which no rule does, and the
    # column silently never matches. The unit is read separately anyway.
    headers = [pairing_map.header_label(c) for c in raw_headers]
    header_units = [resolve_unit(paired_review._header_unit(c) or
                                 (re.search(r"\(([^)]{1,32})\)\s*$", c).group(1)
                                  if re.search(r"\(([^)]{1,32})\)\s*$", c) else ""),
                                 known_units)
                    for c in raw_headers]
    rows = []
    for line in block[2:]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < len(raw_headers):
            cells += [""] * (len(raw_headers) - len(cells))
        rows.append(cells[:len(raw_headers)])
    if not rows:
        return None

    kinds = []
    for i in range(len(raw_headers)):
        cells = [r[i] for r in rows if r[i].strip()]
        if not cells:
            kinds.append("text")
            continue
        if all(cell_range(c, header_units[i]) is not None for c in cells):
            kinds.append("range")
        elif all(len(_cell_quantities(c)) == 1 for c in cells):
            kinds.append("value")
        else:
            kinds.append("text")
    # A UNIT COLUMN. A header does not always carry the unit: real reference tables
    # commonly put it in a column of its own beside the figure, and the first
    # unseen corpus this module was pointed at did exactly that, so every band was
    # dropped for having no unit. A text column counts as the unit column when
    # every one of its non-empty cells is a unit THE DOCUMENT UNDER REVIEW ITSELF
    # WRITES. That is the same self-validation resolve_unit uses, and it is why a
    # column of prose can never be mistaken for one: prose is not in the document's
    # unit vocabulary. The unit is then per ROW, which is what lets one table carry
    # figures in different units.
    known = {str(u) for u in known_units if u}
    unit_column = None
    if known:
        for i, kind in enumerate(kinds):
            if kind != "text":
                continue
            cells = [r[i].strip() for r in rows if r[i].strip()]
            if cells and all(c in known for c in cells):
                unit_column = i
                break
    return {"ref_id": ref_id, "document_id": document_id,
            "raw_headers": raw_headers, "headers": headers,
            "header_units": header_units, "kinds": kinds, "rows": rows,
            "unit_column": unit_column}


def _sentences(text):
    """A passage split into sentences, stripped of markdown table rows and
    blank lines: a prose band never lives inside a cell parse_table already
    reads, and reading it twice would double the same figure into two bands."""
    out = []
    for para in re.split(r"\n\s*\n", text or ""):
        lines = [ln for ln in para.splitlines()
                 if ln.strip() and not ln.lstrip().startswith("|")
                 and not ln.lstrip().startswith("#")]
        if not lines:
            continue
        joined = " ".join(ln.strip() for ln in lines)
        for sentence in _SENTENCE_END.split(joined):
            sentence = sentence.strip()
            if sentence:
                out.append(sentence)
    return out


def parse_prose_band_sentence(sentence, *, known_units=()):
    """(label, remainder, low, high, unit, column_phrase) for one sentence, or
    None.

    The one shape read: LABEL, a colon, then a RANGE in the same sentence
    ("Class-A sensor: standard tolerance band 20 to 60 units."). The label is
    the text before the first colon; the range is read from the text after it
    by cell_range, the same function a table cell uses, so the same discipline
    applies without a second implementation to keep in step: exactly two
    quantities of one unit, close enough together to be a range and not two
    unrelated figures, tied bounds refused, a descending pair refused. The
    words between the colon and the range's first figure ("standard tolerance
    band") are read as column_phrase: the same role a table header plays,
    naming what the two numbers mean, so bands_for_unit's own rule "the rule
    must name the range column" has real words to test against a prose band
    exactly as it does a table's header.

    Refuses, returning None, rather than guessing, when:
      - there is no colon, or the text before it is not label-shaped (empty,
        or longer than PROSE_LABEL_MAX_CHARS, which is the sign of a colon
        ending a clause rather than introducing a label);
      - the text after the colon does not reduce to exactly one range by
        cell_range's own test (no range, or MORE than two quantities in play,
        such as a second, unrelated figure later in the same sentence: two
        unrelated figures in one sentence are not a band, the same caution
        the module already holds for one table cell);
      - known_units is given and the range's unit is not one the document
        under review itself writes (the same self-validation resolve_unit
        uses: an uncorroborated unit is left alone, not trusted on its own).
    """
    if ":" not in sentence:
        return None
    label, _, remainder = sentence.partition(":")
    label = label.strip()
    remainder = remainder.strip()
    if not label or len(label) > PROSE_LABEL_MAX_CHARS:
        return None
    if not remainder:
        return None
    # The sentence must carry exactly the two quantities that make the range:
    # a third figure anywhere in the remainder means this sentence states more
    # than one fact, and picking one reading over another is exactly the
    # coin-toss this module refuses elsewhere.
    quantities = _cell_quantities(remainder)
    if len(quantities) != 2:
        return None
    band = cell_range(remainder, "")
    if band is None:
        return None
    low, high, unit = band
    if not unit:
        return None
    known = {str(u) for u in known_units if u}
    if known and unit not in known:
        return None
    first_start = quantities[0][2]
    column_phrase = remainder[:first_start].strip(" .,;:")
    return (label, remainder, low, high, unit, column_phrase)


def parse_prose_bands(text, *, ref_id="", document_id="", known_units=()):
    """Every labelled prose band in a passage, grouped into synthetic tables.

    Every sentence in the passage that matches parse_prose_band_sentence's one
    shape becomes one ROW (label, range-cell); rows are grouped by their
    (unit, column_phrase) into one synthetic table per distinct range kind,
    matching what an operator who had written this as a real table would have
    produced (one column of labels, one column of ranges, headed by what the
    ranges mean, one unit per table). Grouping, not one table per sentence, is
    what lets key_column_indexes recognise the label column as discriminating
    at all: that test requires at least two distinct cells, which a
    single-row table can never have, and device_class_reference.md states
    three such sentences (Class-A, Class-B, Class-C) in the one passage,
    exactly the shape a real table would have three rows for. Grouping by
    column_phrase as well as unit keeps two different kinds of bound that
    happen to share a unit (a tolerance band and, elsewhere, a separate
    distance band both in the same unit) as two tables, not one column that
    would answer either rule's question with the wrong row. A tie between two
    labels is then a tie between two ROWS of the one table, handled by
    match_row exactly as a real table's rows are.
    """
    by_group = {}
    for sentence in _sentences(text):
        hit = parse_prose_band_sentence(sentence, known_units=known_units)
        if hit is None:
            continue
        label, remainder, low, high, unit, column_phrase = hit
        by_group.setdefault((unit, column_phrase), []).append((label, remainder))
    out = []
    for (unit, column_phrase), rows in by_group.items():
        out.append({
            "ref_id": ref_id, "document_id": document_id,
            "raw_headers": ["label", column_phrase],
            "headers": [(), pairing_map.header_label(column_phrase)],
            "header_units": ["", unit],
            "kinds": ["text", "range"],
            "rows": [[label, remainder] for label, remainder in rows],
            "unit_column": None,
        })
    return out


def parse_tables(text, *, ref_id="", document_id="", known_units=()):
    """Every markdown table in a passage, as structured records."""
    out = []
    for block in pairing_map._table_blocks(text or ""):
        table = parse_table(block, ref_id=ref_id, document_id=document_id,
                            known_units=known_units)
        if table is not None:
            out.append(table)
    out.extend(parse_prose_bands(text, ref_id=ref_id, document_id=document_id,
                                 known_units=known_units))
    return out


def tables_from_entries(entries, *, exclude_document_id="", known_units=()):
    """Every reference-corpus table, carrying the REF-* id of the passage it came
    from, so a finding built on it can cite that passage and nothing else.

    `entries` is the reference index's own entry dicts. The document UNDER REVIEW
    is excluded: its own tables are the figures being checked, not the reference
    band they are checked against."""
    out = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("document_id") and entry["document_id"] == exclude_document_id:
            continue
        out.extend(parse_tables(entry.get("text_excerpt") or "",
                                ref_id=entry.get("ref_id") or "",
                                document_id=entry.get("document_id") or "",
                                known_units=known_units))
    return out


# ---------------------------------------------------------------------------
# matching a unit to a row


def key_column_indexes(table, rule_text=""):
    """Which columns identify a row, learned rather than named.

    Discriminating: a text column whose non-empty cells are all distinct, so it
    tells the rows apart. Named: a column whose header label words all appear in
    the rule text that cites this table. The intersection is used when it is
    non-empty, because a rule naming a column is the operator saying which column
    identifies the row; otherwise every discriminating text column is used, and a
    column that identifies nothing simply fails to match, which costs a band
    rather than inventing one."""
    discriminating = []
    for i, kind in enumerate(table["kinds"]):
        if kind != "text":
            continue
        cells = [r[i].strip() for r in table["rows"] if r[i].strip()]
        if len(cells) >= 2 and len(set(cells)) == len(cells):
            discriminating.append(i)
    if not rule_text:
        return discriminating
    rule_words = _words(rule_text)
    named = [i for i in discriminating
             if table["headers"][i] and set(table["headers"][i]) <= rule_words]
    return named or discriminating


def unit_value_words(unit_text):
    """The content words of the unit's own labelled field VALUES.

    Values, not labels: a row is identified by what the document SAYS in a field,
    not by the fact that the field exists."""
    words = set()
    for line in (unit_text or "").splitlines():
        m = pairing_map._LABEL_LINE.match(line)
        if m:
            words |= _words(m.group(2))
    return words


def match_row(table, unit_text, rule_text=""):
    """(row_index, matched_word_count) for the row this unit belongs to, or None.

    A row matches when every content word of its key cells appears among the
    unit's own field values. The most specific match wins; a tie between two rows
    is REFUSED, because picking one would be picking a band by coin toss."""
    keys = key_column_indexes(table, rule_text)
    if not keys:
        return None
    unit_words = unit_value_words(unit_text)
    if not unit_words:
        return None
    best, best_score, tied = None, 0, False
    for index, row in enumerate(table["rows"]):
        row_words = set()
        for i in keys:
            row_words |= _words(row[i])
        if not row_words or not row_words <= unit_words:
            continue
        score = len(row_words)
        if score > best_score:
            best, best_score, tied = index, score, False
        elif score == best_score and best is not None:
            tied = True
    if best is None or tied:
        return None
    return (best, best_score)


# ---------------------------------------------------------------------------
# bands


def low_side_condition(rule_text, vocabulary, used_labels, unit_labels):
    """Whether a BELOW-band result may be stated as a finding on its own.

    A rule can attach a condition to the low side only: a figure under the band is
    an irregularity unless something else is on file. The condition is not read
    from prose (that would need a domain vocabulary); it is detected structurally,
    as the document field labels the RULE names that the band's own computation
    and row match do not use. A rule that names nothing beyond what it computes
    attaches no condition, and a below-band result fires as a finding.

    Returns (condition_labels, verdict) where verdict is:
      "fire"   no condition, or the unit carries none of the condition fields, so
               the absence is itself what the rule calls the irregularity;
      "model"  the unit carries a condition field whose CONTENT decides the case.
               A label's presence is machine-checkable; what it says is not, so
               the computed values go to the model rather than a firm finding
               being invented from a field nobody read.
    """
    if not vocabulary:
        return ((), "fire")
    named = pairing_map.needed_fields(rule_text or "", vocabulary)
    condition = sorted(named - set(used_labels or ()))
    if not condition:
        return ((), "fire")
    if set(condition) & set(unit_labels or ()):
        return (tuple(condition), "model")
    return (tuple(condition), "fire")


def prior_values_for_scalars(table, scalars, rule_text=""):
    """A figure read from a VALUE column of a table by word-set EQUALITY between a
    document label and a key cell. The sibling of bands_for_unit for kind ==
    "value": bands_for_unit finds a ROW for a unit by containment over the unit's
    field values, this finds a row for a LABEL by equality over the key cells. It
    identifies a row, never a round: which document is the earlier version is the
    operator's declaration, not this function's inference.

    Returns (hits, refused). hits maps a label tuple to {value, unit, ref_id,
    document_id, row_index, row_label, column_label, key_labels}. A table with no
    key column or with anything other than exactly one value column is refused
    whole (one refusal with an empty label); a label matching two rows, or two
    labels matching one row, is refused for those labels. Equality per key
    column, not containment: a summary table lists terms by their full names, and
    containment would let "rate" match "match rate" and "special rate" alike.
    """
    import paired_review

    keys = [i for i in key_column_indexes(table, rule_text) if i != table.get("unit_column")]
    values = [i for i, k in enumerate(table["kinds"]) if k == "value"]
    if rule_text:
        rw = _words(rule_text)
        named = [i for i in values if table["headers"][i] and set(table["headers"][i]) <= rw]
        values = named or values
    if not keys:
        # key_column_indexes wants every key cell distinct, so a duplicated key cell
        # leaves the table with no key column at all: refused whole, and said so.
        return {}, [{"label": "", "ref_id": table["ref_id"],
                     "reason": "no key column identifies the rows (a duplicated or empty "
                               "key cell leaves none)"}]
    if len(values) != 1:
        return {}, [{"label": "", "ref_id": table["ref_id"],
                     "reason": "table has %d value column(s); exactly one is required"
                               % len(values)}]
    col = values[0]
    hits, refused, by_row = {}, [], {}
    for label in sorted(scalars):
        target = set(label)
        rows = [ri for ri, row in enumerate(table["rows"])
                if any(_words(row[i]) == target for i in keys)]
        if not rows:
            continue
        if len(rows) > 1:
            refused.append({"label": " ".join(label), "ref_id": table["ref_id"],
                            "reason": "tie between %d rows" % len(rows)})
            continue
        ri = rows[0]
        row = table["rows"][ri]
        q = paired_review.first_quantity(row[col])
        if q is None:
            continue
        value, cell_unit = q
        fallback = table["header_units"][col] or (
            row[table["unit_column"]].strip() if table.get("unit_column") is not None else "")
        unit = _accept_cell_unit(cell_unit, fallback)
        unit = _unit_str(_unit_exponents(unit)) if unit else ""
        hits[label] = {
            "value": value, "unit": unit,
            "ref_id": table["ref_id"], "document_id": table["document_id"],
            "row_index": ri,
            "row_label": " ".join(row[i].strip() for i in keys if row[i].strip()),
            "column_label": " ".join(table["headers"][col] or ()),
            "key_labels": tuple(table["headers"][i] for i in keys if table["headers"][i]),
        }
        by_row.setdefault(ri, []).append(label)
    for ri, labels in by_row.items():
        if len(labels) > 1:
            for label in labels:
                refused.append({"label": " ".join(label), "ref_id": table["ref_id"],
                                "reason": "reverse tie: %d document labels match one row"
                                          % len(labels)})
                hits.pop(label, None)
    return hits, refused


def bands_for_unit(tables, unit_text, rule_text):
    """Every band this unit inherits from the reference tables, for this rule.

    One band per (table, range column) whose row this unit matches. Each carries
    the REF-* id of the passage the table came from, which is what a finding built
    on it cites, and the KEY LABELS the row was matched by, which the low-side
    condition test needs so that it does not mistake the row's own identifying
    column for a side condition."""
    bands = []
    for table in tables or []:
        hit = match_row(table, unit_text, rule_text)
        if hit is None:
            continue
        row_index, matched = hit
        row = table["rows"][row_index]
        keys = key_column_indexes(table, rule_text)
        row_label = " ".join(row[i].strip() for i in keys if row[i].strip())
        key_labels = tuple(table["headers"][i] for i in keys if table["headers"][i])
        rule_words = _words(rule_text)
        for i, kind in enumerate(table["kinds"]):
            if kind != "range":
                continue
            # The rule must name the RANGE COLUMN, not merely the column that
            # identifies the row. Matching on the key column alone was wrong and
            # the first live run showed why: a completeness rule that happens to
            # say "region" inherited the yield band, because "region" is the key
            # column, and produced a band finding under a rule that says nothing
            # about yields at all. One extra containment test, over the table's
            # own header words and the rule's own text, and no vocabulary.
            column_label = table["headers"][i]
            if not column_label or not set(column_label) <= rule_words:
                continue
            # The unit comes from the header, or, where the table carries one, from
            # this ROW's unit column. Per row, not per column: one table may state
            # figures in different units.
            fallback = table["header_units"][i]
            if not fallback and table.get("unit_column") is not None:
                fallback = row[table["unit_column"]].strip()
            parsed = cell_range(row[i], fallback)
            if parsed is None:
                continue
            low, high, unit = parsed
            if not unit:
                continue
            bands.append({
                "low": low, "high": high, "unit": unit,
                "ref_id": table["ref_id"],
                "document_id": table["document_id"],
                "row_label": row_label,
                "column_label": " ".join(table["headers"][i] or ()),
                "key_labels": key_labels,
                "matched_words": matched,
            })
    return bands


def band_conditions_for_unit(tables, unit_text, rules, *, vocabulary=None):
    """The pairing map's record of what the band check could and could not decide.

    Written into <run>/audit/pairing_map.json per unit BEFORE any band verdict
    fires, so the reason a low figure was or was not stated as a finding is on the
    record rather than inside a model's head. It records the raw evidence, not a
    conclusion: which band was matched from which reference passage, which fields
    the rule names beyond the row key, and which of those the unit actually
    carries."""
    unit_labels = pairing_map.unit_fields(unit_text or "")
    out = []
    for rule in rules or []:
        rule_text = rule.get("rule", "")
        for band in bands_for_unit(tables, unit_text, rule_text):
            condition, verdict = low_side_condition(
                rule_text, vocabulary, band["key_labels"], unit_labels)
            out.append({
                "rule_id": rule.get("id"),
                "ref_id": band["ref_id"],
                "row_label": band["row_label"],
                "column_label": band["column_label"],
                "low": band["low"], "high": band["high"], "unit": band["unit"],
                "condition_fields": [" ".join(c) for c in condition],
                "condition_fields_present": [" ".join(c) for c in condition
                                             if c in unit_labels],
                "low_side_verdict": verdict,
            })
    return out
