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


def load_external_rules(path):
    """External rules as given. Returns [] when the file does not exist, which is
    the normal state: nothing in this system produces an external rule, and no
    code path fetches one."""
    p = Path(path)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    rules = data.get("external_rules") if isinstance(data, dict) else data
    return [r for r in (rules or []) if isinstance(r, dict)]
