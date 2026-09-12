"""Two rule sets: the operator's conventions, and rules found outside.

THE SEPARATION, and why it is not one pile.

The operator's conventions carry AUTHORITY: the operator wrote them and the run
applies them. A rule found outside carries only INFORMATION: it may be true, it
may be relevant, and nothing about its origin makes it binding. Merging the two
would let something nobody approved acquire the force of something the operator
wrote, which is the same failure as a usage-derived fact sitting in the pile with
an operator rule (docs/fix/KNOWLEDGE_CATEGORIES.md).

So they stay apart, and three rules follow from that:

  BOTH APPLY where they do not conflict. An external rule that says nothing the
  operator's conventions contradict is extra information and is used as such.

  A CONFLICT IS REFUSED, not resolved. Where an operator convention and an
  external rule disagree about the same thing, the run does not pick. It refuses
  that pair, lists it, and puts it to the operator. Choosing silently is how a
  system acquires rules nobody agreed to.

  AN ANSWER IS REMEMBERED. The operator's answer is stored against a stable
  conflict id, so the same disagreement is never raised twice. A conflict whose
  SIDES changed is a different question and is asked again.

PROMOTION. An external rule is a PROPOSAL until the operator accepts it. On
acceptance it becomes an operator rule WITH AN OWNER recorded, and from then on
it carries authority like any other convention. It never applies on its own.

NO DISCOVERY, NO SEARCH, DELIBERATELY. Nothing here reaches outside the machine.
This module takes external rules as given and says nothing about where they come
from; the question of a source is left open on purpose. Today the only external
rules that exist are declared fixtures, and there is no code path that fetches
one.

WHY THIS IS ALSO ITEM ONE. The conflict record is the only record in the system
carrying both a target and a human verdict, and it had zero rows because nothing
raised a conflict. This is what raises them. The two were built to meet rather
than as unconnected pieces: an answer recorded here is written through
ontology_conflicts' own resolution shape, so one reader serves both.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pairing_map

# An external rule's standing. A rule is a proposal until the operator accepts
# it; acceptance is the only route to authority, and it is recorded with an
# owner so a later reader knows who took responsibility for it.
STATUS_PROPOSED = "proposed"
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED = "rejected"
STATUSES = (STATUS_PROPOSED, STATUS_ACCEPTED, STATUS_REJECTED)

# What the operator can answer about a conflict. Deliberately the same three
# words ontology_conflicts already uses, so an operator learns one vocabulary:
#   convention  the operator's own rule governs; the external rule is set aside
#   external    the external rule is right; it is promoted and gains an owner
#   refuse      neither applies for this pair and the run reports it unresolved
ANSWER_CONVENTION = "convention"
ANSWER_EXTERNAL = "external"
ANSWER_REFUSE = "refuse"
ANSWERS = (ANSWER_CONVENTION, ANSWER_EXTERNAL, ANSWER_REFUSE)


def external_conflict_id(*, subject, convention_rule_id, external_rule_id):
    """A stable id for one convention-versus-external disagreement.

    Same shape and same reasoning as ontology_conflicts.conflict_id: the same
    disagreement in a later run yields the same id so it is recognised and not
    re-asked, and a conflict whose sides changed yields a different id because
    it is a different question. Identifiers only, never text."""
    raw = "|".join([str(subject or ""), str(convention_rule_id or ""),
                    str(external_rule_id or "")])
    return "xconflict-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _subject_of(rule):
    """What a rule is ABOUT, as a set of normalised label TOKEN TUPLES, for
    deciding whether two rules address the same thing.

    Read from the rule's own declarations rather than its prose: the scope
    labels it names, plus the required labels. Two rules with no declared
    overlap are not about the same thing as far as this module can tell, and it
    says so rather than guessing from wording.

    Each element is `pairing_map._norm_label`'s output, a TUPLE of words, not a
    string, so overlap is WHOLE-LABEL and not word-level: "Reading date" does not
    meet "Reading", which is right, because two rules about different fields are
    not in conflict merely for sharing a word. Case, accents and a trailing
    plural are folded by that one tokeniser, so "READING" and "Readings" do meet
    "Reading". Using the project's single tokeniser is deliberate: a second
    normaliser here would be the two-tokenisers defect CLAUDE.md names, with the
    two sides of a containment test disagreeing silently."""
    out = set()
    for entry in (rule.get("scope") or []):
        label = entry.get("label") if isinstance(entry, dict) else entry
        key = pairing_map._norm_label(str(label or ""))
        if key:
            out.add(key)
    for label in (rule.get("requires") or []):
        key = pairing_map._norm_label(str(label or ""))
        if key:
            out.add(key)
    return out


def detect_external_conflicts(conventions, external_rules):
    """Where an operator convention and an external rule disagree.

    A conflict requires two things, both structural, neither read from prose:
      1. the two rules are ABOUT the same thing: their declared subjects
         (scope plus requires) overlap
      2. they say DIFFERENT things about it: their declared severity or action
         differ, or one declares a conditional suspension the other does not

    Rules that overlap and agree are not a conflict, and both apply. Rules that
    do not overlap are not a conflict either, and both apply. Only genuine
    disagreement about a shared subject is refused, because refusing more than
    that would make the operator arbitrate questions nobody is asking.

    An external rule that is not `proposed` is skipped: an accepted one is
    already an operator rule and a rejected one is not in play.
    """
    out = []
    for ext in external_rules or []:
        if str(ext.get("status") or STATUS_PROPOSED) != STATUS_PROPOSED:
            continue
        ext_subject = _subject_of(ext)
        if not ext_subject:
            continue
        for conv in conventions or []:
            shared = ext_subject & _subject_of(conv)
            if not shared:
                continue
            differences = []
            for field in ("severity", "action"):
                a = str(conv.get(field) or "").strip().lower()
                b = str(ext.get(field) or "").strip().lower()
                if a and b and a != b:
                    differences.append({"field": field, "convention": a, "external": b})
            conv_unless = bool(conv.get("unless"))
            ext_unless = bool(ext.get("unless"))
            if conv_unless != ext_unless:
                differences.append({"field": "unless",
                                    "convention": "declared" if conv_unless else "none",
                                    "external": "declared" if ext_unless else "none"})
            if not differences:
                continue
            subject = " ".join(sorted(" ".join(t) for t in shared))
            out.append({
                "conflict_id": external_conflict_id(
                    subject=subject,
                    convention_rule_id=conv.get("id"),
                    external_rule_id=ext.get("id")),
                "subject": subject,
                "convention_rule_id": conv.get("id"),
                "external_rule_id": ext.get("id"),
                "differences": differences,
            })
    return out


# THREE-C. What the overlap test CANNOT see, in the operator's own terms.
#
# A conflict is detected from DECLARED subjects: the scope and requires labels a
# rule names. Two rules about the same thing in different words therefore never
# register as conflicting, and the run will apply both without ever asking. The
# limit is deliberate (guessing a subject from prose is the same mistake the
# band reader's rules forbid), but it is invisible exactly where it matters: an
# operator reading a SHORT conflict list will reasonably conclude the rules
# mostly agree, when the truth may be that the detector could not see the
# disagreement at all.
#
# So it travels WITH the list rather than living in a document nobody opens.
OVERLAP_LIMIT_NOTICE = (
    "How this list was built, and what it cannot contain: a conflict is found by "
    "comparing the subjects the two rules DECLARE (their scope and requires "
    "labels), not by reading what they say. Two rules about the same thing in "
    "different words do not appear here, and both will be applied. A short list "
    "is therefore not evidence that the rules agree: it may mean the subjects "
    "were written differently. Where you know two rules touch the same subject, "
    "declaring that subject the same way in both is what makes the disagreement "
    "visible.")


def conflict_report(conflicts, *, external_rules=None):
    """The conflict list as the operator meets it, carrying its own limit.

    The notice is part of the return value rather than something a caller may
    add, so there is no path that shows an operator this list without telling
    them what it cannot contain. `compared` names how many rules were actually
    examined, since a list of zero from one rule and a list of zero from forty
    are different facts."""
    return {
        "conflicts": list(conflicts or []),
        "count": len(conflicts or []),
        "external_rules_compared": len(external_rules or []),
        "limit_notice": OVERLAP_LIMIT_NOTICE,
    }


def apply_external_resolutions(conflicts, resolutions):
    """Split conflicts into those already answered and those still to ask.

    Returns (applied, to_ask). An answer this module does not recognise is
    treated as UNANSWERED rather than obeyed, because an unrecognised
    instruction is not an instruction. That is ontology_conflicts' own rule and
    it is kept here deliberately."""
    applied, to_ask = [], []
    for c in conflicts or []:
        answer = ((resolutions or {}).get(c["conflict_id"]) or {}).get("answer")
        if answer not in ANSWERS:
            to_ask.append(c)
            continue
        entry = dict(c)
        entry["answer"] = answer
        if answer == ANSWER_CONVENTION:
            entry["effect"] = ("the operator's own rule governs this subject; the "
                               "external rule is set aside for it")
        elif answer == ANSWER_EXTERNAL:
            entry["effect"] = ("the external rule is accepted and becomes an operator "
                               "rule with an owner; it carries authority from now on")
        else:
            entry["effect"] = ("neither rule is applied to this subject; the pair is "
                               "reported unresolved")
        applied.append(entry)
    return applied, to_ask


def promote(external_rule, *, owner, run_id="", now_iso=None):
    """An accepted external rule becomes an operator rule WITH AN OWNER.

    The owner is required and is not defaulted: a rule that acquired authority
    with nobody named is exactly what the separation exists to prevent. The
    returned rule carries its origin, so a later reader can tell a promoted rule
    from one the operator wrote, which matters when the two are being audited
    even though both now carry the same force."""
    if not str(owner or "").strip():
        raise ValueError("an accepted external rule needs an owner: a rule that "
                         "gains authority with nobody named is what the separation "
                         "between the two rule sets exists to prevent")
    out = dict(external_rule)
    out["status"] = STATUS_ACCEPTED
    out["owner"] = str(owner).strip()
    out["promoted_at"] = now_iso or datetime.now(timezone.utc).isoformat()
    out["promoted_in_run"] = str(run_id or "")
    out["origin"] = "external:accepted"
    return out


def applicable(conventions, external_rules, conflicts):
    """The rules a run may apply, with the two sets kept apart.

    Returns {"conventions": [...], "external": [...], "withheld": [...]}.
    Conventions always apply: they carry the operator's authority and an
    external rule cannot displace one. An external rule applies as INFORMATION
    only when it is in no unanswered conflict. One in an open conflict is
    withheld and named, so a reader can see what was set aside and why rather
    than finding a rule quietly absent."""
    open_ids = {c["external_rule_id"] for c in (conflicts or [])}
    external, withheld = [], []
    for ext in external_rules or []:
        status = str(ext.get("status") or STATUS_PROPOSED)
        if status == STATUS_REJECTED:
            withheld.append({"external_rule_id": ext.get("id"), "reason": "rejected"})
            continue
        if ext.get("id") in open_ids:
            withheld.append({"external_rule_id": ext.get("id"),
                             "reason": "in an unanswered conflict with an operator "
                                       "convention; put to the operator rather than "
                                       "applied"})
            continue
        external.append(ext)
    return {"conventions": list(conventions or []), "external": external,
            "withheld": withheld}


# The store node type for an answer about a convention-versus-external conflict.
# Deliberately NOT ontology_conflicts.RESOLUTION_NODE: that node answers a
# different question (does the ontology's memory or the current rule govern this
# provision), and the two share a store. One node type for two questions would
# let an answer about one be read as an answer about the other, and the ids
# cannot collide by luck either, since they carry different prefixes.
EXTERNAL_RESOLUTION_NODE = "ExternalRuleResolution"


def resolutions_in(store):
    """{conflict_id: resolution record} for convention-versus-external answers.

    Read through the storage layer, so another scope's answers are never visible
    here, the same as every other read. Only this module's node type is
    returned, so an ontology-versus-rule answer is never mistaken for one of
    these."""
    out = {}
    for r in store.current():
        if r.get("node") != EXTERNAL_RESOLUTION_NODE:
            continue
        cid = r.get("conflict_id")
        if cid:
            out[cid] = r
    return out


def resolution_records(answers, *, run_id, provenance, conflicts_by_id=None):
    """Shape the operator's answers as store records, so the next run finds them
    and the same conflict is never put to the operator twice.

    `answers`: {conflict_id: answer}. An answer this module does not recognise is
    REFUSED HERE rather than written, which is ontology_conflicts' own rule:
    writing it would make every later run either ask again or, worse, act on an
    unrecognised instruction. The refusal is returned so the caller can report
    it rather than discover a silently dropped answer.

    The record carries BOTH RULE IDS and the subject, never any rule text: a
    store record is an identifier record, so document or rule prose cannot ride
    along into durable state."""
    conflicts_by_id = conflicts_by_id or {}
    out, rejected = [], []
    for cid, answer in sorted((answers or {}).items()):
        if answer not in ANSWERS:
            rejected.append({"conflict_id": cid, "answer": answer,
                             "reason": "not one of %s" % (", ".join(ANSWERS),)})
            continue
        c = conflicts_by_id.get(cid) or {}
        out.append({
            "node": EXTERNAL_RESOLUTION_NODE,
            "id": "xresolution::" + cid,
            "conflict_id": cid,
            "answer": answer,
            "subject": c.get("subject"),
            "convention_rule_id": c.get("convention_rule_id"),
            "external_rule_id": c.get("external_rule_id"),
            "answered_in_run": run_id,
            "answered_at": _now_iso(),
            "provenance": provenance,
        })
    return out, rejected


def write_resolutions(store, answers, *, run_id, agent=None, conflicts_by_id=None):
    """Write the operator's answers into the ontology through the scoped store.

    Returns (summary, rejected). A re-answered conflict supersedes its earlier
    answer by the storage layer's own rule, so an operator can change their mind
    and the latest answer is the one a later run reads. This is the half of item
    THREE that makes "the same conflict is never raised twice" true across runs
    rather than only within one."""
    import ontology_store
    prov = ontology_store.provenance(time=ontology_store.now_iso(), agent=agent,
                                     run=run_id)
    records, rejected = resolution_records(answers, run_id=run_id, provenance=prov,
                                           conflicts_by_id=conflicts_by_id)
    written = store.append(records) if records else {"written": 0, "superseded": 0}
    return {"written": written.get("written", 0),
            "superseded": written.get("superseded", 0),
            "rejected": len(rejected)}, rejected


def _now_iso():
    try:
        import ontology_store
        return ontology_store.now_iso()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def open_store(stores_dir=None, *, scope=None, live_path=None):
    """Open the scoped store the same way every other reader does, so a caller
    never constructs a path itself. Shares ontology_conflicts' scope default, so
    both kinds of answer live in one place and one reset clears both."""
    import ontology_conflicts
    if scope is None:
        scope = ontology_conflicts.DEFAULT_SCOPE
    return ontology_conflicts.open_store(stores_dir, scope=scope, live_path=live_path)


def unanswered(conflicts, store):
    """The conflicts still to put to the operator, reading stored answers.

    This is the whole point of persistence: a conflict answered in an earlier run
    does not come back. A conflict whose SIDES changed has a different id and is
    a new question, so it is asked, which is correct rather than a miss."""
    applied, to_ask = apply_external_resolutions(conflicts, resolutions_in(store))
    return applied, to_ask


def load_external_rules(path):
    """External rules from ONE file the operator supplied. Returns [] when the
    file does not exist, which is the normal state.

    A malformed file is NOT silently empty: it raises, because an operator who
    wrote a rules file and got no rules would conclude the mechanism is off
    rather than that their JSON is broken. A missing file is a different fact
    and is the quiet one."""
    p = Path(path)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(
            "external rules file %s is not valid JSON: %s. It is refused rather "
            "than read as empty, because a file you wrote producing no rules "
            "silently is worse than one that stops the run." % (p.name, exc))
    rules = data.get("external_rules") if isinstance(data, dict) else data
    return [r for r in (rules or []) if isinstance(r, dict)]


# Where an operator hands over a rule found outside. THREE-B: this is the entry
# point, and it needs no discovery and no network. The operator drops a file in,
# exactly as they do for input/conventions/, and the rules in it arrive as
# PROPOSALS. Nothing in this system reaches out to find one; the only route in
# is an operator putting a file here.
EXTERNAL_RULES_DIR = ("input", "external_rules")


def external_rules_dir(project_root):
    return Path(project_root).joinpath(*EXTERNAL_RULES_DIR)


def load_external_rules_dir(project_root):
    """Every external rule the operator has supplied, with its source file.

    Returns (rules, sources). Mirrors convention_parser.parse_conventions: a
    directory the operator drops files into, read at load time, with an
    unrecognised file WARNED rather than silently dropped, so a rules file in
    the wrong format is visible instead of absent.

    Every rule is forced to `proposed` on the way in, whatever the file claims,
    and carries the file it came from. A file cannot declare its own rules
    accepted: acceptance is the operator's act, recorded with an owner through
    `promote`, and a self-accepting file would be the whole separation defeated
    by an attribute."""
    d = external_rules_dir(project_root)
    rules, sources = [], []
    if not d.is_dir():
        return rules, sources
    seen = set()
    for path in sorted(d.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() != ".json":
            import text_extract
            text_extract.warn_unsupported(path, where="/".join(EXTERNAL_RULES_DIR))
            continue
        found = load_external_rules(path)
        if not found:
            continue
        sources.append(path.name)
        for r in found:
            rule = dict(r)
            rid = str(rule.get("id") or "").strip()
            if not rid:
                continue
            if rid in seen:
                # Two files claiming the same id is ambiguous, and picking one
                # would make the answer depend on filename order. Refused.
                raise ValueError(
                    "external rule id %r appears in more than one file under %s; "
                    "ids must be unique, because a stored answer is keyed to the "
                    "rule it was about" % (rid, "/".join(EXTERNAL_RULES_DIR)))
            seen.add(rid)
            rule["status"] = STATUS_PROPOSED
            rule["origin"] = "external:operator_supplied"
            rule["source_file"] = path.name
            rules.append(rule)
    return rules, sources
