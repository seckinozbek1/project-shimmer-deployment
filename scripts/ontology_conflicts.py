"""Ontology-versus-rule conflicts, and the operator's answers (ontology chain, job 3).

THE OPERATOR'S DECISION THIS IMPLEMENTS, in their own words: when the ontology
conflicts with a rule, the conflicted pair is REFUSED in that run, never guessed;
the refusals are listed and put to the operator together at the end; the next run
applies their answers; the answer is written to the ontology so the same conflict
is never put to them twice. Track the override rate, with the caveat that at
single-operator volume it is not statistically meaningful.

WHAT A CONFLICT IS HERE. The ontology holds what a past run captured about a
provision (which rule governed it). A rule in the current registry says what should
govern it now. A conflict is the narrow, structural case where those two disagree
about the SAME provision: the store says this provision was governed by one rule,
the current run says another. Nothing semantic is inferred: this module compares
identifiers, never meanings, and it never asks whether a rule is "right".

WHAT REFUSAL MEANS. The conflicted pair produces no finding in that run. Not a
guess, not the store's answer, not the rule's answer: nothing, recorded as refused
with both sides named. That is the whole point of the decision, and it is why this
module cannot resolve a conflict on its own even when one side looks obviously
better.

NEVER ASKED TWICE. An answered conflict is written into the ontology store as a
Resolution record under the same scoped storage layer everything else uses, keyed
by a stable conflict id. A later run that meets the same conflict finds the
resolution and applies it without asking. A conflict whose sides have CHANGED gets
a different id and is therefore a different question, which is correct: it is a
different conflict.

THE OVERRIDE RATE, and its caveat, recorded here rather than only in a report: the
rate is answered-against-the-store over answered-total. At single-operator volume
it is not statistically meaningful and must never be presented as a quality metric.
It is reported because a trend an operator can see is worth more than a number
nobody computes, not because the number is sound.

NOT MEASURED. No run has ever produced a conflict, because the store is empty. Every
path here is proved on fixtures in the verify gate. Deterministic, local, stdlib
only, no model calls.
"""

from __future__ import annotations

import hashlib

import ontology_store
from ontology_store import DEFAULT_SCOPE

# The node type resolutions are stored under, beside Provision and Relation, in the
# same scoped store. One store, one scope rule, one supersession rule.
RESOLUTION_NODE = "Resolution"

# What the operator can answer. Deliberately three, not two: "refuse again" is a real
# answer (the operator may want the pair to keep producing nothing) and is not the
# same as never having answered.
ANSWER_RULE = "rule"          # the current rule wins; the store's memory is overridden
ANSWER_STORE = "store"        # the store's memory wins; the rule does not apply here
ANSWER_REFUSE = "refuse"      # keep refusing this pair; produce nothing, permanently
ANSWERS = (ANSWER_RULE, ANSWER_STORE, ANSWER_REFUSE)


def conflict_id(*, provision_id, store_rule, rule_id):
    """A stable id for one conflict: the same disagreement in a later run yields the
    same id, so it is recognised and not re-asked. A conflict whose SIDES changed
    yields a different id, because it is a different question.

    Hashed rather than concatenated so an id is a fixed length whatever the operator's
    identifiers look like, and the inputs are identifiers only (never text)."""
    raw = "|".join([str(provision_id or ""), str(store_rule or ""), str(rule_id or "")])
    return "conflict-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def detect_conflicts(store_records, current_by_provision):
    """The narrow structural comparison: for each provision the current run has a rule
    for, does the store remember a DIFFERENT governing rule?

    `store_records`: what the scoped store currently holds (provisions).
    `current_by_provision`: {provision_id: rule_id} the current run would apply.

    A provision the store has never seen is not a conflict (nothing to disagree with).
    A provision whose stored rule matches is not a conflict. A stored record with no
    rule at all is not a conflict: an absent memory is not a disagreement.
    """
    stored = {}
    for r in store_records:
        if (r.get("node") or "Provision") != "Provision":
            continue
        pid, rule = r.get("id"), r.get("convention_ref")
        if pid and rule:
            stored[pid] = rule
    out = []
    for pid, rule_id in sorted((current_by_provision or {}).items()):
        if not pid or not rule_id:
            continue
        remembered = stored.get(pid)
        if not remembered or remembered == rule_id:
            continue
        out.append({
            "conflict_id": conflict_id(provision_id=pid, store_rule=remembered,
                                       rule_id=rule_id),
            "provision_id": pid,
            "store_rule": remembered,
            "rule_id": rule_id,
        })
    return out


def resolutions_in(store):
    """{conflict_id: resolution record} for this scope. Read through the storage layer,
    so another scope's answers are never visible here, the same as every other read."""
    out = {}
    for r in store.current():
        if r.get("node") != RESOLUTION_NODE:
            continue
        cid = r.get("conflict_id")
        if cid:
            out[cid] = r
    return out


def apply_resolutions(conflicts, resolutions):
    """Split detected conflicts into those the operator has already answered and those
    still to ask. Returns (applied, to_ask).

    `applied` entries carry the answer and what it means for this run, so the caller
    applies a recorded decision rather than re-deriving one. `to_ask` is what goes to
    the operator at the end of the run. An answer this module does not recognise is
    treated as unanswered rather than obeyed, because an unrecognised instruction is
    not an instruction."""
    applied, to_ask = [], []
    for c in conflicts:
        res = resolutions.get(c["conflict_id"])
        answer = (res or {}).get("answer")
        if res is not None and answer in ANSWERS:
            entry = dict(c)
            entry["answer"] = answer
            entry["answered_at"] = res.get("answered_at")
            entry["effective_rule"] = (c["rule_id"] if answer == ANSWER_RULE else
                                       c["store_rule"] if answer == ANSWER_STORE else None)
            entry["produces_finding"] = answer != ANSWER_REFUSE
            applied.append(entry)
        else:
            to_ask.append(dict(c))
    return applied, to_ask


def refusal_records(conflicts, *, run_id):
    """What a refused pair leaves behind in the run: both sides named, nothing guessed.
    These are what the operator is shown at the end of the run and what the deliverable
    reports as not decided."""
    return [{
        "conflict_id": c["conflict_id"],
        "provision_id": c["provision_id"],
        "store_rule": c["store_rule"],
        "rule_id": c["rule_id"],
        "run_id": run_id,
        "reason": ("the ontology remembers this provision governed by %s and this run "
                   "would apply %s; refused rather than guessed"
                   % (c["store_rule"], c["rule_id"])),
    } for c in conflicts]


def resolution_records(answers, *, run_id, provenance, conflicts_by_id=None):
    """Shape the operator's answers as store records, so the next run finds them and
    the same conflict is never put to the operator twice.

    `answers`: {conflict_id: answer}. An answer this module does not recognise is
    REFUSED here rather than written, because writing it would make every later run
    treat an unrecognised instruction as an unanswered question and ask again, or
    worse, act on it."""
    conflicts_by_id = conflicts_by_id or {}
    out, rejected = [], []
    for cid, answer in sorted((answers or {}).items()):
        if answer not in ANSWERS:
            rejected.append({"conflict_id": cid, "answer": answer,
                             "reason": "not one of %s" % (", ".join(ANSWERS),)})
            continue
        c = conflicts_by_id.get(cid) or {}
        out.append({
            "node": RESOLUTION_NODE,
            "id": "resolution::" + cid,
            "conflict_id": cid,
            "answer": answer,
            "provision_id": c.get("provision_id"),
            "store_rule": c.get("store_rule"),
            "rule_id": c.get("rule_id"),
            "answered_in_run": run_id,
            "answered_at": ontology_store.now_iso(),
            "provenance": provenance,
        })
    return out, rejected


def override_rate(store):
    """Answered-against-the-store over answered-total, with its own caveat carried in
    the return value so no caller can report the number without it.

    `overrode_store` counts answers where the current rule won over the store's memory,
    which is the direction an operator cares about: how often the remembered answer was
    wrong. Returns None for the rate when nothing has been answered, never 0.0, because
    "no answers yet" and "never overrode" are different facts.
    """
    resolutions = resolutions_in(store)
    total = len(resolutions)
    overrode = sum(1 for r in resolutions.values() if r.get("answer") == ANSWER_RULE)
    kept = sum(1 for r in resolutions.values() if r.get("answer") == ANSWER_STORE)
    refused = sum(1 for r in resolutions.values() if r.get("answer") == ANSWER_REFUSE)
    return {
        "answered": total,
        "overrode_store": overrode,
        "kept_store": kept,
        "kept_refusing": refused,
        "override_rate": (overrode / total) if total else None,
        "caveat": ("at single-operator volume this rate is not statistically meaningful "
                   "and must not be read as a quality measure; it is a trend an operator "
                   "can watch, nothing more"),
    }


def write_resolutions(store, answers, *, run_id, agent=None, conflicts_by_id=None):
    """Write the operator's answers into the ontology through the scoped store. Returns
    (summary, rejected). A re-answered conflict supersedes its earlier answer by the
    storage layer's own rule, so an operator can change their mind and the latest answer
    is the one a later run reads."""
    prov = ontology_store.provenance(time=ontology_store.now_iso(), agent=agent,
                                     run=run_id)
    records, rejected = resolution_records(answers, run_id=run_id, provenance=prov,
                                           conflicts_by_id=conflicts_by_id)
    written = store.append(records) if records else {"written": 0, "superseded": 0}
    return {"written": written.get("written", 0),
            "superseded": written.get("superseded", 0),
            "rejected": len(rejected)}, rejected


def open_store(stores_dir=None, *, scope=DEFAULT_SCOPE, live_path=None):
    """Open the scoped store the same way every other reader does, so a caller never
    constructs a path itself."""
    import ontology_reader
    return ontology_reader.read_store(stores_dir, scope=scope, live_path=live_path)
