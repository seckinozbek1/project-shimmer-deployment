"""Which rules could apply to which units, decided before any agent judges anything.

The wide review handed a model eight declarations and twelve rules in one call and
got a summary of the rules back. Paired review asks one narrow question per (unit,
rule) pair instead, which is only affordable if the pairs are chosen rather than
enumerated: a cross product of 8 units and 17 rules is 136 calls, and a local call
with the typed-record section costs 78 to 85 seconds.

So this module decides pairs, deterministically first:

    split_units      the document becomes units with stable ids
    field_vocabulary the labels the document itself uses, learned from the document
    needed_fields    which of those labels a rule's own text names
    pair_units       a rule pairs with a unit only when the unit carries every
                     field the rule needs, with a recorded reason either way

Nothing here knows anything about any domain (S5). The field vocabulary is read
out of the operator's document, and what a rule needs is read out of the operator's
rule text. A rule that names a label the document uses pairs with the units that
carry it; a rule that names none of them is ambiguous and is handed to the
embedding pass to rank, never guessed at here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import finding_record

# Words that carry no discriminating power when matching a rule against a field
# label. Deliberately closed-class only: articles, prepositions, auxiliaries. No
# domain terms, because a domain term is exactly what has to survive to do the
# matching.
STOPWORDS = frozenset("""
a an the and or but if then than that this these those of in on at to for from by
with without under over above below between per each any all no not is are was were
be been being has have had do does did must shall should may might can could will
would its it their his her our your as into onto out up down when where which who
whom whose what how why more most less least same other another such only also both
""".split())

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.M)
# The label may begin with any letter in any script and continue with word
# characters: it was `[A-Za-z][A-Za-z0-9 ...]`, so a label carrying a single
# accented or non-Latin letter was not a label line at all, and every field it
# introduced was invisible to the pairing map, the arithmetic and the band match.
# Byte-identical for ASCII input.
_LABEL_LINE = re.compile(r"^[ \t]*[-*+]?[ \t]*([^\W\d_][\w ()/%._-]{1,48}?)[ \t]*:[ \t]*(\S.*)$",
                         re.UNICODE)
_TABLE_ROW = re.compile(r"^[ \t]*\|(.+)\|[ \t]*$")
_TABLE_SEP = re.compile(r"^[ \t]*\|[\s:|-]+\|[ \t]*$")


def _slug(text, limit=40):
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s[:limit] or "unit"


def header_label(raw_header):
    """A table header's label with its UNIT parenthetical removed first.

    A header writes its unit in brackets, and _norm_label folds those words into
    the label unless the length filter happens to drop them: "Area (ha)" came out
    as ('area',) only because "ha" is two letters, while "Extent (zed)" came out as
    ('extent', 'zed'). Every containment test over labels then failed for any
    three-letter-or-longer unit: a rule naming "extent" did not pair with the
    column, and a scalar "total declared extent" was not recognised as that
    column's total, so the sum check silently never ran. The unit is read
    separately by paired_review._header_unit and has no business in the label.
    One helper, used by every site that normalises a header."""
    return _norm_label(re.sub(r"\s*\([^)]*\)\s*$", "", str(raw_header or "")))


# A placeholder for a hyphen JOINING two word characters, substituted before
# the [\W_]+ split so "Class-A" survives as one token rather than splitting
# into "class" and a fragment the length floor then drops. Must itself be a
# \w sequence (so the split does not cut through it) and must not collide
# with real input; an ASCII sentinel is the plain, correct answer here, not a
# Unicode look-alike hyphen, which is NOT a \w character under re's own
# UNICODE-flag classification and silently fails the same way a raw split
# character would (found by testing the placeholder's own re.match result
# before trusting it, not by assuming a Unicode character "looks like a
# letter"). Accepted, narrow edge case: literal input containing this exact
# ASCII sequence around a hyphen would be misread; no real label or rule text
# does, and a document that did would fail visibly (a stray extra token), not
# silently.
_HYPHEN_JOIN_PLACEHOLDER = "xhyphenx"


def _stem(word):
    """Fold a plural to its singular: strip a trailing 's', or fold a
    trailing '-ies' to '-y'. Minimal and structural, not a general stemmer:
    two suffix rules, no irregular plurals, no other suffix.

    Refuses where a trailing 's' is almost never a genuine plural marker,
    checked against the real corpus that motivated this fix, not assumed:
    after another 's' ("class" -to- "clas" would tie every "Class-A" against
    every "Class-B"), after 'us' ("corpus", "focus"), after 'is' ("basis",
    "diagnosis"). A word of 3 characters or fewer is left alone (folding
    "gas" or "was" serves nothing and risks colliding with an unrelated
    3-letter word)."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if not word.endswith("s") or len(word) <= 3:
        return word
    if word.endswith(("ss", "us", "is")):
        return word
    return word[:-1]


def _norm_label(label):
    """A field label reduced to its discriminating words, in order.

    refine R3: the split is UNICODE-AWARE. It used to be `[^a-z0-9]+`, which does
    not merely ignore a non-ASCII letter, it CUTS THE WORD AT IT: a label reading
    "bolge" with an umlaut came out as ('lge',), and a French or Polish label came
    out as a different fragment on each side of the comparison. Every operator
    whose language is not written in unaccented ASCII lost their column labels
    silently, with no error and no log line. `[\\W_]+` on the lowercased string is
    byte-identical for ASCII input, so nothing about an English corpus changes.

    A hyphen JOINS two word characters rather than splitting them, checked
    before the length floor: "Class-A" was splitting into "class" and a
    dropped single-letter fragment, so "Class-A sensor" and "Class-B sensor"
    reduced to the identical `('class', 'sensor')`, and no band or field
    match could ever tell the two apart. Proved on the device corpus: three
    real labels this way, in one table AND in one prose sentence, tied
    identically either way, since both paths already shared this function
    (Job A's own docstring, "two tokenisers that must agree are one
    tokeniser", extended here to a single splitting rule they both must use).

    A trailing plural is folded to its singular (_stem), on BOTH the label
    side and, via this same function, wherever a rule's own words are read:
    two independent raw word-bag builders used to exist for the rule side
    (pairing_map.needed_fields, paired_review.date_pair_for_rule), already
    disagreeing with each other and with this function before either defect
    was found (this function alone dropped short words and stopwords; the
    two rule-side splits did neither, by design, since a rule's incidental
    words never needed filtering for a subset test to work). Both now call
    this one function instead of building their own bag: one tokeniser, not
    three drifting toward disagreement. Proved on the device corpus's own
    wording gap: the reference states "fault timestamp" and the rule says
    "state the two timestamps"; without folding, no subset test the words
    ever pass through can equate the two, however the split or the length
    floor is tuned.

    RESIDUAL LIMIT, recorded rather than claimed away: `len(w) > 2` is itself an
    alphabetic assumption. Two characters is a fragment in a Latin script and a
    whole word in a logographic one, so a CJK label is still dropped. Fixing that
    means making the threshold script-aware, which changes how every existing
    label is cut and is not a change to make in passing. The stem is two suffix
    rules over English morphology specifically; a label in a language whose
    plural is not built with a trailing 's' gains nothing from it and loses
    nothing either, since neither rule can match a word that does not end in
    the sequences it tests for.
    """
    text = str(label).lower()
    text = re.sub(r"(?<=[^\W_])-(?=[^\W_])", _HYPHEN_JOIN_PLACEHOLDER, text)
    words = [w.replace(_HYPHEN_JOIN_PLACEHOLDER, "-")
            for w in re.split(r"[\W_]+", text, flags=re.UNICODE) if w]
    return tuple(_stem(w) for w in words if w not in STOPWORDS and len(w) > 2)


# ---------------------------------------------------------------------------
# splitting


def split_units(text, *, document_id=""):
    """Split a document into units with stable ids.

    Headings first: every heading below the top level starts a unit, and the
    material under it, tables included, stays whole (a table is never cut across
    units). A document with no such headings is split on its table blocks, and a
    document that is one table is split by row, because a row is the natural unit
    of a ledger. Ids are derived from position and heading text, so the same
    document always yields the same ids.

    Every unit also carries "index": its 0-based position in the list this
    function returns, the SAME position the unit_id's own numeric prefix
    already encodes (u01, u02, ...), now as a field a caller can read without
    parsing a string. This is the single source: every caller that re-keys a
    unit list to a dict on unit_id (paired_review.unit_texts_for,
    pipeline.py's phase 5.5 and phase 6 unit maps) copies the whole dict by
    reference, so index survives every one of those re-keyings with no change
    needed at any of them. Adding it here, once, is what makes "the unit
    immediately before/after" answerable at all: a dict keyed by unit_id has
    no memory of order on its own, index is what restores it. index is
    assigned identically in every branch below (0-based list position, the
    order units are appended in), never derived from an "i" loop variable
    directly, because those variables mean different things per branch
    (0-based for headings, 1-based for rows and tables) and mixing bases
    across branches would put contradictory numbers in the same field.
    """
    text = text or ""
    headings = [m for m in _HEADING.finditer(text)]
    body_headings = [m for m in headings if len(m.group(1)) >= 2]
    units = []
    if body_headings:
        for i, m in enumerate(body_headings):
            start = m.start()
            end = body_headings[i + 1].start() if i + 1 < len(body_headings) else len(text)
            title = m.group(2).strip()
            units.append({
                "unit_id": "u%02d-%s" % (i + 1, _slug(title)),
                "title": title,
                "kind": "section",
                "text": text[start:end].strip(),
                "index": len(units),
            })
        return units

    blocks = _table_blocks(text)
    if len(blocks) == 1 and len(blocks[0]) > 2:
        header = blocks[0][0]
        for i, row in enumerate(blocks[0][2:], 1):
            units.append({
                "unit_id": "u%02d-row" % i,
                "title": "row %d" % i,
                "kind": "row",
                "text": header + "\n" + blocks[0][1] + "\n" + row,
                "index": len(units),
            })
        return units
    for i, block in enumerate(blocks, 1):
        units.append({"unit_id": "u%02d-table" % i, "title": "table %d" % i,
                      "kind": "table", "text": "\n".join(block),
                      "index": len(units)})
    if not units and text.strip():
        units.append({"unit_id": "u01-document", "title": "document",
                      "kind": "document", "text": text.strip(),
                      "index": 0})
    return units


def _table_blocks(text):
    blocks, current = [], []
    for line in (text or "").splitlines():
        if _TABLE_ROW.match(line):
            current.append(line)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


# ---------------------------------------------------------------------------
# what the document calls things


def unit_fields(unit_text):
    """The field labels this unit carries, as normalised word tuples.

    Two sources, both structural: a `label: value` line, and a table's header
    cells when the block has a separator row. Nothing is inferred from meaning.
    """
    fields = set()
    lines = (unit_text or "").splitlines()
    for line in lines:
        m = _LABEL_LINE.match(line)
        if m:
            norm = _norm_label(m.group(1))
            if norm:
                fields.add(norm)
    for block in _table_blocks(unit_text or ""):
        if len(block) < 2 or not _TABLE_SEP.match(block[1]):
            continue
        for cell in block[0].strip().strip("|").split("|"):
            norm = header_label(cell)
            if norm:
                fields.add(norm)
    return fields


def unit_field_values(unit_text):
    """{normalised label: normalised value} for every `label: value` line of a unit.
    A table cell is a row's value, not the unit's, and is not read here. Values are
    lowercased and whitespace-collapsed for comparison with a declared scope value;
    they are never written into a map reason line (they are document content)."""
    out = {}
    for line in (unit_text or "").splitlines():
        m = _LABEL_LINE.match(line)
        if m:
            norm = _norm_label(m.group(1))
            if norm and norm not in out:
                out[norm] = " ".join(m.group(2).strip().lower().split())
    return out


def scope_declaration(rule):
    """The rule's declared scope (D, option 2) as [(label tuple, value or None)],
    the label normalised exactly as the document's own labels are; [] when the
    rule declares none. The declaration is the operator's, from the heading
    bracket; nothing here derives a scope from counts or text."""
    out = []
    for entry in rule.get("scope") or []:
        if isinstance(entry, dict):
            label, value = entry.get("label"), entry.get("value")
        else:
            label, _, value = str(entry).partition("=")
        norm = _norm_label(str(label or ""))
        if not norm:
            continue
        value = " ".join(str(value).lower().split()) if value not in (None, "") else None
        out.append((norm, value))
    return out


def required_declaration(rule):
    """The rule's declared required labels (D, option 2), normalised; set()."""
    return {n for n in (_norm_label(str(x)) for x in (rule.get("requires") or [])) if n}


def field_vocabulary(units):
    """Every field label the document uses anywhere."""
    vocab = set()
    for unit in units:
        vocab |= unit_fields(unit.get("text", ""))
    return vocab


def needed_fields(rule_text, vocabulary):
    """Which of the document's own field labels this rule's text names.

    A label counts as named when every one of its discriminating words appears in
    the rule text. That is a mechanical test over the operator's own vocabulary:
    no list of domain terms exists in this file, and none can, because the terms
    come from the operator's document and rules at runtime.
    """
    # The rule's own words, read by _norm_label, the SAME function the label
    # side already goes through. A second, independent raw split used to
    # live here (no stopword filter, no length floor, by design, since a
    # subset test only needs the LABEL's already-filtered words to be found,
    # and the rule's incidental words never needed filtering for that). It
    # existed at all because the split itself, not the filtering, is what
    # both sides must agree on: the label side's own hyphen-splitting and
    # unstemmed plural were already the actual failure (device corpus: three
    # class labels tying identically, and a bound naming "timestamp" against
    # a rule saying "timestamps"), and a second split here could drift from
    # the first without either side raising an error, which it already had.
    # Filtering the rule's words too is harmless for the subset test (a
    # stopword or two-letter word could never have been in a label's own
    # words either), so one function serves both sides with nothing lost.
    words = set(_norm_label(rule_text or ""))
    named = {label for label in vocabulary if label and set(label) <= words}
    # Longest match only (D, option 1, 2026-09-11, built without measurement). A
    # label whose words are a proper subset of another named label's words is the
    # shorter phrase inside the longer one, not a second field the rule requires:
    # a rule saying "calibration authority signature" names that label, not also
    # the glossary's "calibration authority". Before this, the shorter label was
    # required of every unit too, and on the first tagged corpus that rejected the
    # rule for the very entries that carried the signature. A rule that genuinely
    # needs both labels loses the shorter one here; the map's reason line shows it.
    return {label for label in named
            if not any(label != other and set(label) < set(other) for other in named)}


# ---------------------------------------------------------------------------
# pairing


def pair_units(units, rules, *, vocabulary=None, rank=None, rank_cap=3):
    """Decide which rules could apply to which units.

    Deterministic first. A rule that names fields the document uses pairs only
    with the units that carry all of them, and the reason is recorded either way.
    A rule that names none of the document's field labels carries no mechanical
    signal at all; it is marked ambiguous and, when a ranker is supplied, only
    then is similarity used, and only to ORDER the candidates the deterministic
    pass could not decide.

    `rank` is an optional callable (unit_text, [(rule_id, rule_text)]) -> ordered
    list of rule_ids. Injected rather than imported so this module never depends
    on an embedding store being present.
    """
    if vocabulary is None:
        vocabulary = field_vocabulary(units)
    rule_needs = {}
    for rule in rules:
        rule_needs[rule["id"]] = needed_fields(rule.get("rule", ""), vocabulary)

    entries = []
    for unit in units:
        have = unit_fields(unit.get("text", ""))
        have_values = None
        paired, rejected, ambiguous = [], [], []
        for rule in rules:
            rid = rule["id"]
            # D, option 2: a rule with a DECLARED scope pairs on its scope fields (and
            # values) alone; the fields its text happens to name are not requirements.
            # Its absence checks come from its declared requires (paired_review.plan_calls).
            scope = scope_declaration(rule)
            if scope:
                if have_values is None:
                    have_values = unit_field_values(unit.get("text", ""))
                missing = [lab for lab, _v in scope if lab not in have]
                wrong = [lab for lab, v in scope
                         if v is not None and lab in have and have_values.get(lab) != v]
                if not missing and not wrong:
                    paired.append({
                        "rule_id": rid, "scope_declared": True,
                        "reason": "unit carries every scope field the rule declares: "
                                  + ", ".join(" ".join(lab) + ("=" + v if v is not None else "")
                                              for lab, v in scope),
                    })
                elif missing:
                    rejected.append({
                        "rule_id": rid, "scope_declared": True,
                        "reason": "unit lacks the declared scope field "
                                  + ", ".join(" ".join(lab) for lab in missing),
                        "missing_count": len(missing),
                    })
                else:
                    rejected.append({
                        "rule_id": rid, "scope_declared": True,
                        "reason": "unit's " + ", ".join(" ".join(lab) for lab in wrong)
                                  + " does not carry the value the rule's scope declares",
                        "missing_count": len(wrong),
                    })
                continue
            needs = rule_needs[rid]
            if not needs:
                ambiguous.append(rid)
                continue
            missing = needs - have
            if not missing:
                paired.append({
                    "rule_id": rid,
                    "reason": "unit carries every field the rule names: "
                              + ", ".join(" ".join(f) for f in sorted(needs)),
                })
            else:
                rejected.append({
                    "rule_id": rid,
                    "reason": "unit lacks " + ", ".join(" ".join(f) for f in sorted(missing)),
                    "missing_count": len(missing),
                })
        if ambiguous and rank is not None:
            ordered = rank(unit.get("text", ""),
                           [(r["id"], r.get("rule", "")) for r in rules if r["id"] in set(ambiguous)])
            for rid in list(ordered)[:rank_cap]:
                paired.append({"rule_id": rid,
                               "reason": "no field the rule names is used by this document; "
                                         "ranked by similarity among the undecided"})
            ambiguous = [r for r in ambiguous if r not in set(list(ordered)[:rank_cap])]
        entries.append({
            "unit_id": unit["unit_id"],
            "title": unit.get("title", ""),
            "kind": unit.get("kind", ""),
            "index": unit.get("index"),
            "fields_present": sorted(" ".join(f) for f in have),
            "paired": paired,
            "rejected": rejected,
            "undecided": ambiguous,
        })
    return entries


def unmatched_findings(entries, rules, *, convention_registry=None):
    """A unit that no rule matched becomes a missing_field Finding.

    A unit nothing applies to usually means a missing field, not an irrelevant
    unit, so silence there is the wrong answer. The finding is raised against the
    NEAREST MISS, the rule that wanted the fewest fields the unit does not have,
    because a Finding record's rule_id has to be a real registry id and the
    nearest miss is the one that says something true: this unit lacks exactly
    what that rule needed. A unit with no rejected rules at all yields nothing,
    since there is no rule to name.
    """
    out = []
    for entry in entries:
        if entry["paired"]:
            continue
        candidates = sorted(entry["rejected"], key=lambda r: r.get("missing_count", 99))
        if not candidates:
            continue
        nearest = candidates[0]
        source = finding_record.source_rule_id_for(nearest["rule_id"], convention_registry) \
            if convention_registry else ""
        item = {
            "ref": "document-level",
            "kind": "finding",
            "confidence": "CONFIDENT",
            "rule_id": nearest["rule_id"],
            "unit_id": entry["unit_id"],
            "relation": "missing_field",
            "record_verdict": "irregular",
            "source_refs": [],
            "explanation": ("No rule could be applied to this unit. The closest, "
                            f"{nearest['rule_id']}, needs fields this unit does not carry: "
                            f"{nearest['reason'].replace('unit lacks ', '')}."),
        }
        if source:
            item["source_rule_id"] = source
        out.append(item)
    return out


def build_pairing_map(text, rules, *, document_id="", rank=None,
                      convention_registry=None):
    """Units, pairs, rejections with reasons, and a finding per unmatched unit."""
    units = split_units(text, document_id=document_id)
    vocabulary = field_vocabulary(units)
    entries = pair_units(units, rules, vocabulary=vocabulary, rank=rank)
    findings = unmatched_findings(entries, rules, convention_registry=convention_registry)
    return {
        "document_id": document_id,
        "unit_count": len(units),
        "rule_count": len(rules),
        "field_vocabulary": sorted(" ".join(f) for f in vocabulary),
        "pair_count": sum(len(e["paired"]) for e in entries),
        "rejected_count": sum(len(e["rejected"]) for e in entries),
        "undecided_count": sum(len(e["undecided"]) for e in entries),
        "unmatched_units": [e["unit_id"] for e in entries if not e["paired"]],
        "units": entries,
        "missing_field_findings": findings,
    }


def write_pairing_map(run_context, document_id, pairing):
    """Write the map to <run>/audit/pairing_map.json, one object per document."""
    audit_dir = Path(run_context.audit_dir())
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / "pairing_map.json"
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    existing[str(document_id)] = pairing
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def embedding_ranker(embed_store):
    """Adapt the existing embedding store into the `rank` callable.

    Returns None when there is no store, so the deterministic pass stands alone
    and nothing has to pretend a ranker exists.
    """
    if embed_store is None:
        return None

    def rank(unit_text, candidates):
        if not candidates:
            return []
        try:
            hits = embed_store.query(unit_text, top_k=len(candidates))
        except Exception:
            return [rid for rid, _ in candidates]
        order = []
        seen = set()
        for hit in hits or []:
            rid = (hit or {}).get("rule_id") if isinstance(hit, dict) else None
            if rid and rid not in seen:
                order.append(rid)
                seen.add(rid)
        order += [rid for rid, _ in candidates if rid not in seen]
        return order

    return rank
