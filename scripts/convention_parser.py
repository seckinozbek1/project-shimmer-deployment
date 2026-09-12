"""Convention parser (genesis Part XVIII Section E).

Reads files in input/conventions/, extracts individual rules from markdown
headers / numbered lists / prose, classifies into categories discovered
from the document structure (no predefined list), assigns severity and
action via language cues, writes config/convention_registry.json.

Deterministic. No LLM call. Idempotent: a rerun produces the same IDs
when the source files have not changed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import text_extract


_TEXT_EXTENSIONS = {".md", ".txt", ".rst", ".log"}
_JSON_EXTENSIONS = {".json"}
# Binary / markup formats: extract plain text via the shared extractor, then
# parse it with the same markdown / list / prose logic as native text files.
_EXTRACT_EXTENSIONS = {".pdf", ".docx", ".html", ".htm"}


_SEVERITY_PATTERNS = [
    ("required",    re.compile(r"\b(must|shall|required|mandatory|prohibited|forbidden|no\s+exception)\b", re.IGNORECASE)),
    ("recommended", re.compile(r"\b(should|recommended|expected|ought to|encouraged)\b", re.IGNORECASE)),
    ("advisory",    re.compile(r"\b(may|consider|optional|where applicable|if appropriate)\b", re.IGNORECASE)),
]


_ACTION_PATTERNS = [
    ("redact",   re.compile(r"\b(redact|mask|conceal|withhold|remove\s+from\s+output|do not (?:print|publish|disclose|reveal))\b", re.IGNORECASE)),
    ("reject",   re.compile(r"\b(reject|do not accept|disallow|prohibit)\b", re.IGNORECASE)),
    ("rephrase", re.compile(r"\b(rephrase|rewrite|replace|substitute|use\s+\S+\s+instead)\b", re.IGNORECASE)),
    ("flag",     re.compile(r"\b(flag|alert|warn|require\s+review|escalate)\b", re.IGNORECASE)),
    ("annotate", re.compile(r"\b(annotate|note|comment|footnote|add\s+citation)\b", re.IGNORECASE)),
]


_DEFAULT_CATEGORY = "unclassified"


@dataclass
class ConventionRule:
    id: str
    category: str
    rule: str
    source_file: str
    source_location: str
    severity: str
    action: str
    subjects: list = field(default_factory=list)
    # D, option 2 (2026-09-11): the operator's own declarations on the heading.
    # scope: the field labels (each optionally with a value) that identify the
    # units the rule governs, [{"label": "class", "value": "a"}, {"label":
    # "device", "value": None}]; requires: the field labels whose absence from a
    # unit in scope is a finding Python decides. Both empty when not declared.
    scope: list = field(default_factory=list)
    requires: list = field(default_factory=list)
    # A CONDITIONAL SUSPENSION: when the condition holds, this rule does not
    # fire. [{"kind": "rule"|"field", "target": str}]. A field condition
    # resolves against the unit the way scope does; a rule condition resolves
    # against the rule it names, and the agent payload then carries both rules
    # together, since a model asked about an exception in isolation from the
    # rule it qualifies gives the wrong answer however well it reads.
    unless: list = field(default_factory=list)

    def as_dict(self):
        return {"id": self.id, "category": self.category, "rule": self.rule,
                "source_file": self.source_file, "source_location": self.source_location,
                "severity": self.severity, "action": self.action,
                "subjects": self.subjects, "scope": self.scope, "requires": self.requires,
                "unless": self.unless}


@dataclass
class ConventionRegistry:
    source_files: list = field(default_factory=list)
    conventions: list = field(default_factory=list)

    def as_dict(self):
        return {
            "schema_version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_files": self.source_files,
            "conventions": [c.as_dict() for c in self.conventions],
        }


def parse_conventions(project_root: Path) -> ConventionRegistry:
    """Parse every file in input/conventions/ into a registry."""
    in_dir = project_root / "input" / "conventions"
    registry = ConventionRegistry()
    if not in_dir.exists():
        return registry
    seq = [0]
    for path in sorted(in_dir.iterdir()):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext in _JSON_EXTENSIONS:
            registry.source_files.append(path.name)
            registry.conventions.extend(_parse_json(path, seq))
        elif ext in _TEXT_EXTENSIONS:
            registry.source_files.append(path.name)
            registry.conventions.extend(_parse_text(path, seq))
        elif ext in _EXTRACT_EXTENSIONS:
            registry.source_files.append(path.name)
            registry.conventions.extend(_parse_extracted(path, seq))
        else:
            # No silent drop: an unrecognized file in input/conventions/ warns.
            text_extract.warn_unsupported(path, where="input/conventions")
    return registry


def write_registry(project_root: Path, registry: ConventionRegistry) -> Path:
    path = project_root / "config" / "convention_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _next_id(seq):
    seq[0] += 1
    return f"CONV-{seq[0]:03d}"


def _classify_severity(text):
    for label, rx in _SEVERITY_PATTERNS:
        if rx.search(text):
            return label
    return "advisory"


def _classify_action(text):
    for label, rx in _ACTION_PATTERNS:
        if rx.search(text):
            return label
    return "flag"


def _parse_json(path, seq):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict) and "conventions" in data:
        items = data["conventions"]
    elif isinstance(data, list):
        items = data
    else:
        return []
    out = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        rule = str(item.get("rule") or item.get("text") or "").strip()
        if not rule:
            continue
        subjects = item.get("subjects")
        out.append(ConventionRule(
            id=item.get("id") or _next_id(seq),
            category=str(item.get("category") or _DEFAULT_CATEGORY).strip().lower(),
            rule=rule, source_file=path.name,
            source_location=str(item.get("source_location") or f"item {i+1}"),
            severity=str(item.get("severity") or _classify_severity(rule)).lower(),
            action=str(item.get("action") or _classify_action(rule)).lower(),
            subjects=[str(s).strip().lower() for s in subjects] if isinstance(subjects, list) else [],
            scope=_scope_entries(item.get("scope")),
            requires=[str(s).strip().lower() for s in (item.get("requires") or [])
                      if str(s).strip()] if isinstance(item.get("requires"), list) else [],
            unless=_unless_entries(item.get("unless")),
        ))
    return out


def _unless_entries(raw):
    """Normalise an unless declaration into [{"kind", "target"}], from a JSON
    file giving strings or dicts. The kind is decided by the target's own shape,
    exactly as the heading path decides it, so a rule declared in JSON and one
    declared on a heading mean the same thing."""
    out = []
    for entry in (raw or []) if isinstance(raw, list) else []:
        if isinstance(entry, dict):
            target = str(entry.get("target") or "").strip().lower()
        else:
            target = str(entry).strip().lower()
        if not target:
            continue
        item = {"kind": "rule" if _HEADING_RULE_ID.match(target) else "field",
                "target": target}
        if item not in out:
            out.append(item)
    return out


def _scope_entries(raw):
    """Normalise a scope declaration into [{"label", "value"}]: a list of strings
    ("class", "class=a") or of dicts, as a JSON file or the heading bracket gives it."""
    out = []
    for entry in (raw or []) if isinstance(raw, list) else []:
        if isinstance(entry, dict):
            label, value = entry.get("label"), entry.get("value")
        else:
            label, _, value = str(entry).partition("=")
        label = str(label or "").strip().lower()
        value = str(value).strip().lower() if value not in (None, "") else None
        if label:
            out.append({"label": label, "value": value})
    return out


def _parse_text(path, seq):
    text = path.read_text(encoding="utf-8", errors="replace")
    return _parse_text_lines(text, path.name, seq)


def _parse_text_lines(text, source_name, seq):
    out = []
    current_category = _DEFAULT_CATEGORY
    current_section = "preamble"
    current_severity = None
    current_subjects: list = []
    # True until the first heading that carries the OPERATOR'S OWN rule id
    # (never merely the first heading in the file: a conventions file opened
    # directly with a real, id-less rule section, as check_32's own seed text
    # does, must parse exactly as it always has). While true, a PARAGRAPH is
    # preamble prose, not a rule: this is what fixes the file's title
    # sentence and scope statement being minted as real CONV-* entries. A
    # LIST ITEM is never suppressed by this: an operator who writes a list
    # item under any heading, titled or not, plainly means it as a rule.
    before_first_operator_heading = True
    line_num = 0
    para_buffer = []

    current_scope: list = []
    current_requires: list = []

    def flush(buffer, suppress_paragraph, severity, subjects, location):
        if not buffer or suppress_paragraph:
            return []
        joined = " ".join(b.strip() for b in buffer).strip()
        if not joined:
            return []
        return [ConventionRule(
            id=_next_id(seq), category=current_category, rule=joined,
            source_file=source_name, source_location=location,
            severity=severity or _classify_severity(joined),
            action=_classify_action(joined), subjects=list(subjects),
            scope=[dict(s) for s in current_scope], requires=list(current_requires),
            unless=[dict(u) for u in current_unless],
        )]

    for raw_line in text.splitlines():
        line_num += 1
        line = raw_line.rstrip()
        if _is_markdown_heading(line):
            out.extend(flush(para_buffer, before_first_operator_heading,
                             current_severity, current_subjects,
                             f"line {line_num - len(para_buffer)}"))
            para_buffer = []
            current_category = _normalize_category(line)
            current_section = line.lstrip("# ").strip().lower()
            current_severity, current_subjects = _heading_bracket_tags(line)
            current_scope, current_requires, current_unless = _heading_bracket_declarations(line)
            if before_first_operator_heading and heading_carries_rule_id(line):
                before_first_operator_heading = False
            continue
        if _is_list_item(line):
            out.extend(flush(para_buffer, before_first_operator_heading,
                             current_severity, current_subjects,
                             f"line {line_num - len(para_buffer)}"))
            para_buffer = []
            stripped = _strip_list_marker(line)
            if stripped:
                out.append(ConventionRule(
                    id=_next_id(seq), category=current_category, rule=stripped,
                    source_file=source_name, source_location=f"line {line_num}",
                    severity=current_severity or _classify_severity(stripped),
                    action=_classify_action(stripped), subjects=list(current_subjects),
                    scope=[dict(s) for s in current_scope], requires=list(current_requires),
                    unless=[dict(u) for u in current_unless],
                ))
            continue
        if not line.strip():
            out.extend(flush(para_buffer, before_first_operator_heading,
                             current_severity, current_subjects,
                             f"line {line_num - len(para_buffer)}"))
            para_buffer = []
            continue
        para_buffer.append(line)
    out.extend(flush(para_buffer, before_first_operator_heading, current_severity,
                     current_subjects, f"line {line_num - len(para_buffer) + 1}"))
    return [r for r in out if r.rule and len(r.rule) >= 16]


def _parse_extracted(path, seq):
    # .pdf / .docx / .html / .htm: pull plain text via the shared extractor and
    # run it through the same structural parser as native text files. No temp
    # file is written (the source name is preserved on each rule).
    text = text_extract.extract_text(path)
    if not text.strip():
        return []
    return _parse_text_lines(text, path.name, seq)


def _is_markdown_heading(line):
    return bool(re.match(r"^#{1,6}\s+\S", line))


def _is_list_item(line):
    return bool(re.match(r"^\s*(?:[-*+]|\d+[.)])\s+\S", line))


def _strip_list_marker(line):
    return re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", line).strip()


_CATEGORY_KEYWORDS = {
    "terminology":     ("terminology", "term", "vocabulary", "wording"),
    "red_flags":       ("red flag", "flag", "warning", "alert"),
    "rephrasing":      ("rephrase", "rewrite", "rephrasing", "language"),
    "citation_style":  ("citation", "cite", "reference", "borrowing"),
    "structural":      ("structure", "structural", "format", "section"),
    "value_alignment": ("value", "alignment", "ethics", "principles"),
    "borrowing":       ("borrow", "external", "foreign", "attribution"),
}


_HEADING_RULE_ID = re.compile(r"\bconv-[a-z0-9]+(?:-[a-z0-9]+)*\b", re.IGNORECASE)


def heading_carries_rule_id(line):
    """True when this line is a markdown heading carrying the operator's own
    rule id. This is the parser's load-bearing test (it is what flips
    before_first_operator_heading below), exposed so intake classifies a file
    by the same signal the parser will read it with. Intake used to match two
    exact filenames while this module read every file in the directory
    regardless of name, so a convention file the operator named anything else
    was filed as a document under review and its rules were never compiled.
    Two detectors that must agree are one detector."""
    if not _is_markdown_heading(line):
        return False
    return bool(_HEADING_RULE_ID.search(_normalize_category(line)))


def text_carries_rule_headings(text):
    """True when any line of this text is an operator rule heading."""
    for line in str(text).splitlines():
        if heading_carries_rule_id(line.rstrip()):
            return True
    return False

# The bracket slot an operator already writes on a heading and this parser used
# to discard entirely ("## CONV-D01 , conv-value-in-range [required]"). Every
# [...] on the heading is now read structurally: a token this module already
# knows as a severity label (_SEVERITY_PATTERNS' own three names) sets the
# rule's severity directly, overriding the text-classified default; every
# other token is the operator's own subject tag, carried verbatim (lowercased)
# for the convention-assignment comparison, which contains no subject name of
# its own. No subject vocabulary is declared here: this module only knows the
# bracket SHAPE and the three severity words it already knew.
_HEADING_BRACKET = re.compile(r"\[([^\[\]]+)\]")
_SEVERITY_LABELS = frozenset(label for label, _rx in _SEVERITY_PATTERNS)


def _heading_bracket_tags(heading):
    """(severity_or_none, subjects) read from every [...] on a heading line.

    Each bracket token is lowercased and stripped once; a token equal to one
    of this module's own severity labels (required/recommended/advisory) is
    the severity (the LAST such token wins, matching how a human would read
    a heading left to right), and is excluded from subjects. Every other
    token is a subject, order preserved, duplicates dropped."""
    severity = None
    subjects = []
    for m in _HEADING_BRACKET.finditer(heading):
        token = m.group(1).strip().lower()
        if not token or _DECLARATION_PREFIX.match(token):
            continue  # a scope/requires/unless declaration is not a subject (below)
        shaped = _DECLARATION_SHAPED.match(token)
        if shaped:
            # Declaration-shaped and not one this parser knows. Refuse it rather
            # than absorbing it as a subject: the operator wrote an instruction
            # and it would otherwise be silently reinterpreted.
            raise ConventionDeclarationError(
                "unrecognised declaration %r on heading %r: this parser knows "
                "scope, requires and unless. A declaration it cannot honour is "
                "refused rather than read as a subject tag."
                % (shaped.group(1), heading.strip()))
        if token in _SEVERITY_LABELS:
            severity = token
        elif token not in subjects:
            subjects.append(token)
    return severity, subjects


# D, option 2 (2026-09-11): two more bracket forms, read by their leading word and
# nothing else. "[scope: class, device]" or "[scope: class=a, device]" declares the
# field labels (each optionally pinned to a value) that identify the units the rule
# governs; "[requires: calibration authority signature]" declares the field labels
# whose absence from a unit in scope is a finding Python decides without a model.
# The labels and values are the operator's own words, carried verbatim
# (lowercased) and normalised by the pairing map the way it normalises the
# document's own labels; this module knows the two prefixes and no label at all.
#
# "[unless: <target>]" declares a CONDITIONAL SUSPENSION: when the target holds,
# this rule does not fire. The operator writes one declaration and the parser
# decides which kind of target it is from what is written, because a second
# syntax for a second kind of target is a second thing to learn and to get
# wrong. A target matching the convention id shape (CONV-*, the operator's own
# id form) is a RULE condition, resolved against that rule; anything else is a
# FIELD condition, resolved against the unit the way scope and requires are.
#
# CONV-D01 is the working field case: its own words say a reading must fall in
# the band "UNLESS a locally adjusted range ... has been stated in the entry",
# which survived only as an opaque substring that nothing parsed.
_DECLARATION_PREFIX = re.compile(r"^(scope|requires|unless)\s*:\s*(.*)$")

# A bracket that looks like a declaration (it carries a colon) but whose leading
# word this parser does not know. Absorbing it as a subject tag is what happened
# before: "[overrides: CONV-D02]" became the subject "overrides: conv-d02" and
# nothing said so. A declaration the parser cannot honour is REFUSED, because a
# silently swallowed instruction is worse than a rejected one.
_DECLARATION_SHAPED = re.compile(r"^([a-z][a-z_-]*)\s*:\s*\S")


class ConventionDeclarationError(ValueError):
    """A heading carries a declaration this parser does not recognise.

    Raised rather than absorbed. The operator wrote an instruction in
    declaration form and the parser cannot honour it, so the run stops here
    instead of proceeding with the instruction silently reinterpreted as a
    subject tag."""


def _heading_bracket_declarations(heading):
    """(scope entries, required labels, unless conditions) from the declaration
    brackets on a heading line.

    scope    [{"label", "value"}] (value None for a bare label)
    requires [label, ...]
    unless   [{"kind": "rule"|"field", "target": str}, ...]

    Comma-separated, order kept, duplicates dropped. A heading without them
    yields ([], [], []). An `unless` target is classified by its own shape: one
    matching the convention id form is a rule condition, anything else is a
    field condition. The parser therefore needs no second syntax and no hint
    from the operator beyond what they already write."""
    scope, requires, unless = [], [], []
    for m in _HEADING_BRACKET.finditer(heading):
        d = _DECLARATION_PREFIX.match(m.group(1).strip().lower())
        if not d:
            continue
        kind, body = d.group(1), d.group(2)
        parts = [p.strip() for p in body.split(",") if p.strip()]
        if kind == "scope":
            for entry in _scope_entries(parts):
                if entry not in scope:
                    scope.append(entry)
        elif kind == "requires":
            for p in parts:
                if p not in requires:
                    requires.append(p)
        else:  # unless
            for p in parts:
                entry = {"kind": "rule" if _HEADING_RULE_ID.match(p) else "field",
                         "target": p}
                if entry not in unless:
                    unless.append(entry)
    return scope, requires, unless


def _normalize_category(heading):
    """The category a convention heading declares.

    An OPERATOR'S OWN RULE ID, when the heading carries one, is the category and
    nothing else is consulted. That id is what finding_record.source_rule_id_for
    reads back so a finding can be attributed to the rule as the operator wrote
    it, and it must survive verbatim.

    It did not, before this: the keyword table below was consulted FIRST, on the
    whole heading, so an operator slug that happened to contain one of a handful
    of English words was silently reclassified. The second corpus this parser was
    ever pointed at wrote "conv-value-in-range", the word "value" matched the
    "value_alignment" bucket (which is about ethics), the operator's id was
    overwritten, and attribution for every finding under that rule was lost.
    Nothing warned. The keyword table is English and is kept only for a heading
    that carries no id at all, where it is the sole signal there is.
    """
    h = heading.lstrip("# ").strip().lower()
    own = _HEADING_RULE_ID.search(h)
    if own:
        return own.group(0)
    for cat, keys in _CATEGORY_KEYWORDS.items():
        if any(k in h for k in keys):
            return cat
    return h.split()[0] if h else _DEFAULT_CATEGORY
