"""The live case manifest a multi-round test carries (family 4), built and checked here.

A multi-round test declares its rounds in `case_manifest.json` at the top of the bundle,
beside `answer_key.json`: the manifest a declared multi-round Review is sealed and run
with (`--multi-round --multi-round-manifest case_manifest.json`). Its schema is the live
one: schema_version 1, exactly the live top-level fields, `fixture` false, every round
naming the documents the pipeline loads from `context/`, every source a span measured on
that document's text.

The generators never import Shimmer, so `validate` restates the controller's rules
(`validate_live_case_manifest` in the ordinary final controller, which applies the
multi-round module's own manifest check and then measures every span on the documents
the bound pipeline loads). The gate check proves the two agree: every generated manifest
is accepted by both, and every mutation in its list is refused by both.

What a case declares, here: rounds r1..rN in version order (the last is the target, the
one before it the prior, a third round's first document the earliest version); one actor,
the party whose versions they are; one issue per term, keyed by the term's earliest
label, so a renamed term keeps its issue across the rename (an operator declaration: a
multi-round run is told the identity a blind two-version review has to refuse); one
source per round in which the term is stated, quoting its whole label line, on the unit
that holds it.
"""
import json
import re

from . import textrules as tr

FILE = "case_manifest.json"
LIVE_FIELDS = frozenset({"schema_version", "case_id", "fixture", "allow_recommendations",
                         "decision_support_mode", "rounds", "actors", "issues", "sources"})
STATES = frozenset({"accepted", "rejected", "refused", "unresolved", "insufficient_evidence",
                    "not_comparable", "unknown"})
MODES = frozenset({"trajectory_only", "decision_support", "strategic_options", "recommendation"})
ACTOR = "counterparty"
# The document formats the pipeline's corpus loader reads as plain text; the generators
# write only .md, and the structure check refuses any other context file.
TEXT_SUFFIXES = (".txt", ".md", ".rst", ".log", ".json")
LINE = re.compile(r"^([A-Za-z][A-Za-z0-9 ()/%._-]{1,48}): \S")


def identifier(value):
    return (isinstance(value, str) and 0 < len(value) <= 128
            and all(c.isascii() and (c.isalnum() or c in "_-.") for c in value))


def documents_as_loaded(context):
    """{document id: text} for {file name under context/: text}, as the pipeline's corpus
    loader reads them: top-level files only, names starting with '_' skipped, empty text
    skipped, the id the file's stem, or stem__ext when two files share a stem."""
    loaded = []
    for name in sorted(context):
        if "/" in name or name.startswith("_"):
            continue
        stem, dot, ext = name.rpartition(".")
        if not dot or ("." + ext.lower()) not in TEXT_SUFFIXES:
            continue
        text = context[name]
        if not text.strip():
            continue
        loaded.append((stem, ext.lower(), text))
    counts = {}
    for stem, _, _ in loaded:
        counts[stem] = counts.get(stem, 0) + 1
    return {(stem if counts[stem] <= 1 else "%s__%s" % (stem, ext)): text for stem, ext, text in loaded}


def _index(rows, key, errors, what):
    if not isinstance(rows, list):
        errors.append("%s: expected_list" % what)
        return {}
    out = {}
    for row in rows:
        if not (isinstance(row, dict) and identifier(row.get(key))):
            errors.append("%s: invalid_identity" % what)
            continue
        if row[key] in out:
            errors.append("%s: duplicate_identity %s" % (what, row[key]))
        out[row[key]] = row
    return out


def validate(value, documents=None):
    """The controller's rules for a live case manifest; [] when accepted, else the reasons."""
    errors = []
    if not isinstance(value, dict):
        return ["case manifest must be an object"]
    if not set(value) <= LIVE_FIELDS:
        errors.append("a field outside the live schema: %s" % sorted(set(value) - LIVE_FIELDS))
    if value.get("fixture") is not False:
        errors.append("fixture case manifest refused in a live run")
    if value.get("schema_version") != 1:
        errors.append("schema_version")
    if not identifier(value.get("case_id")):
        errors.append("case_identity")
    if type(value.get("allow_recommendations", False)) is not bool:
        errors.append("advice_declaration")
    mode = value.get("decision_support_mode", "trajectory_only")
    if not (isinstance(mode, str) and mode in MODES):
        errors.append("decision_support_mode")
    elif mode == "recommendation" and value.get("allow_recommendations") is not True:
        errors.append("recommendations_require_explicit_permission")
    rounds = _index(value.get("rounds"), "round_id", errors, "rounds")
    actors = _index(value.get("actors"), "actor_id", errors, "actors")
    issues = _index(value.get("issues"), "issue_id", errors, "issues")
    sources = _index(value.get("sources"), "source_id", errors, "sources")
    if len(rounds) < 2 or not actors or not issues:
        errors.append("case_needs_rounds_actors_issues")
    orders, docs = set(), set()
    for r in rounds.values():
        n = r.get("sequence")
        if not (type(n) is int and 0 < n <= 10000 and n not in orders):
            errors.append("round_order %s" % r["round_id"])
        orders.add(n)
        ids = r.get("document_ids")
        if not (isinstance(ids, list) and all(identifier(x) for x in ids)):
            errors.append("round_documents %s" % r["round_id"])
            continue
        if len(ids) != len(set(ids)) or docs.intersection(ids):
            errors.append("document_round_collision %s" % r["round_id"])
        docs.update(ids)
    for s in sources.values():
        sid = s["source_id"]
        if not (s.get("round_id") in rounds and s.get("actor_id") in actors and s.get("issue_id") in issues):
            errors.append("source_identity_link %s" % sid)
            continue
        if s.get("document_id") not in (rounds[s["round_id"]].get("document_ids") or []):
            errors.append("source_round_link %s" % sid)
        if not identifier(s.get("unit_id")):
            errors.append("source_unit %s" % sid)
        if not (type(s.get("char_start")) is int and type(s.get("char_end")) is int
                and 0 <= s["char_start"] < s["char_end"]):
            errors.append("source_span %s" % sid)
        if not (isinstance(s.get("quote"), str) and s["quote"]):
            errors.append("source_quote %s" % sid)
        if s.get("state") not in STATES:
            errors.append("source_state %s" % sid)
    if errors or documents is None:
        return errors
    for r in rounds.values():
        for doc in r["document_ids"]:
            if doc not in documents:
                errors.append("a round names an absent document: %s" % doc)
    for s in sources.values():
        text = documents.get(s["document_id"])
        if text is None or text[s["char_start"]:s["char_end"]] != s["quote"]:
            errors.append("source span does not match the document text: %s" % s["source_id"])
    return errors


def _units(text):
    """(unit id, start offset) for every level-2 heading, in reading order (section 2)."""
    out, pos, n = [], 0, 0
    for ln in text.split("\n"):
        if ln.startswith("## "):
            n += 1
            out.append((tr.unit_id(n, ln[3:]), pos))
        pos += len(ln) + 1
    return out


def unit_at(text, offset):
    """The id of the unit holding a character offset; None in the preamble."""
    found = None
    for uid, start in _units(text):
        if start <= offset:
            found = uid
    return found


def build(case_id, round_docs, issue_of):
    """The case manifest for [(document file name, text)] in round order. Every label line
    of every round document is one source, on the issue issue_of(label) names."""
    documents = documents_as_loaded({name: text for name, text in round_docs})
    rounds, sources, issues = [], [], set()
    for i, (name, text) in enumerate(round_docs, start=1):
        rid = "r%d" % i
        doc_id = name.rsplit(".", 1)[0]
        if documents.get(doc_id) != text:
            raise ValueError("round document %s is not loaded as written" % name)
        rounds.append({"round_id": rid, "sequence": i, "document_ids": [doc_id]})
        pos = 0
        for ln in text.split("\n"):
            m = LINE.match(ln)
            if m and unit_at(text, pos) is not None:
                issue = issue_of(m.group(1))
                issues.add(issue)
                sources.append({"source_id": "%s-%s" % (rid, issue), "round_id": rid,
                                "actor_id": ACTOR, "issue_id": issue, "document_id": doc_id,
                                "unit_id": unit_at(text, pos), "char_start": pos,
                                "char_end": pos + len(ln), "quote": ln, "state": "accepted"})
            pos += len(ln) + 1
    return {"schema_version": 1, "case_id": case_id, "fixture": False,
            "allow_recommendations": False, "decision_support_mode": "trajectory_only",
            "rounds": rounds, "actors": [{"actor_id": ACTOR}],
            "issues": [{"issue_id": i} for i in sorted(issues)], "sources": sources}


def round_reuse(round_texts, parse):
    """The units a later round would reuse from an earlier one, by the per-round review's
    own rule (S2b item 3): a unit is reused when an earlier round's document has a unit with
    the same text, the two documents state the same set of labels (the field vocabulary,
    which also decides which rules pair) and write the same measures. Unit ids are not part
    of the rule. [{round_id, unit_id, from_round, from_unit}] for rounds 2..N."""
    rounds = []
    for i, text in enumerate(round_texts, start=1):
        doc = parse(text, "r%d" % i)
        labels, measures = set(), set()
        for u in doc["units"]:
            labels |= u["labels"]
            for ln in u["lines"]:
                if ln["kind"][0] == "figure" and ln["kind"][2]:
                    measures.add(ln["kind"][2])
        rounds.append({"round_id": "r%d" % i, "labels": labels, "measures": measures,
                       "units": unit_texts(text)})
    out, first = [], {}
    for r in rounds:
        sig_doc = (frozenset(r["labels"]), frozenset(r["measures"]))
        for uid, body in r["units"]:
            src = first.get((sig_doc, body))
            if src is not None:
                out.append({"round_id": r["round_id"], "unit_id": uid,
                            "from_round": src[0], "from_unit": src[1]})
            else:
                first[(sig_doc, body)] = (r["round_id"], uid)
    return out


def unit_texts(text):
    """[(unit id, stripped text)] with the preamble unit first when it carries content
    beyond the title line (u00 plus the title's slug, section 2)."""
    lines = text.split("\n")
    title = lines[0][2:].strip() if lines and lines[0].startswith("# ") else ""
    parts, cur, n = [], ("pre", []), 0
    for ln in lines:
        if ln.startswith("## "):
            parts.append(cur)
            n += 1
            cur = (tr.unit_id(n, ln[3:]), [ln])
        else:
            cur[1].append(ln)
    parts.append(cur)
    out = []
    for uid, body in parts:
        text_ = "\n".join(body).strip()
        if uid == "pre":
            rest = [ln for ln in body if ln.strip() and not ln.startswith("# ")]
            if not rest:
                continue
            uid = "u00-" + tr.slug(title)
        out.append((uid, text_))
    return out


def dump(value):
    return json.dumps(value, indent=2, ensure_ascii=True) + "\n"
