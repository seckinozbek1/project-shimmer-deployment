"""False-negative evidence classification.

Every expected defect the system failed to produce is put into exactly one of four
classes, from saved artifacts and nothing else:

  EVIDENCE_PRESENT_IN_MODEL_PAYLOAD
      What was needed was exposed to a model: a recorded call (logs/call_evidence.jsonl)
      carried the rule and showed the unit, as the reviewed unit, as a supplied
      neighbour, or inside an unclipped whole-document payload. This may be a
      reasoning failure.
  EVIDENCE_PRESENT_UPSTREAM_BUT_NOT_IN_PAYLOAD
      The unit exists in the parsed document (audit/pairing_map.json) and the rule was
      loaded (audit/convention_assignment.json), but no call carried both: the pairing
      map never paired them (a rejection, or no plan), or a plan exists and the
      evidence file, present for the run, records no call for it. A missed defect for
      a rule that was never paired is this class, never the first.
  EVIDENCE_ABSENT_FROM_CORPUS
      The key names a unit no unit of the parsed document contains, or a rule the run
      never loaded. A gold-key problem.
  UNKNOWN
      Whenever the first three cannot be proven from what was saved: no pairing map,
      a rule id the saved artifacts cannot map to a registry id, or a planned pair on
      a run that predates the evidence recording (the call may have happened; nothing
      saved says what it saw).

Nothing here infers. Every classification cites the artifact it rests on in `basis`.
This module never opens an answer key: it takes the expected defect as a dict the
scorer (the only reader of a key) hands it, and reads only the run's own saved files.
"""

from __future__ import annotations

import json
from pathlib import Path

import call_evidence

PRESENT_IN_PAYLOAD = "EVIDENCE_PRESENT_IN_MODEL_PAYLOAD"
PRESENT_UPSTREAM = "EVIDENCE_PRESENT_UPSTREAM_BUT_NOT_IN_PAYLOAD"
ABSENT_FROM_CORPUS = "EVIDENCE_ABSENT_FROM_CORPUS"
UNKNOWN = "UNKNOWN"
CLASSES = (PRESENT_IN_PAYLOAD, PRESENT_UPSTREAM, ABSENT_FROM_CORPUS, UNKNOWN)


def _load_json(path, default):
    p = Path(path)
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _bus_rule_pairs(run_dir):
    """(source_rule_id -> rule_id) pairs any typed Finding on the bus carries; a
    second, weaker source for the operator-id to registry-id mapping."""
    path = Path(run_dir) / "logs" / "agent_bus.jsonl"
    pairs = {}
    if not path.is_file():
        return pairs
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        body = msg.get("body") if isinstance(msg, dict) else None
        payload = body.get("payload") if isinstance(body, dict) else None
        for item in (payload.get("items") if isinstance(payload, dict) else None) or []:
            if not isinstance(item, dict):
                continue
            src, rid = item.get("source_rule_id"), item.get("rule_id")
            if isinstance(src, str) and isinstance(rid, str) and src and rid:
                pairs.setdefault(src.upper(), rid)
    return pairs


def load_run_artifacts(run_dir):
    """Everything the classifier may consult, loaded once. `pairing` is None when
    the run has no pairing map; `evidence` is None when the run predates the
    recording (call_evidence.load's own distinction)."""
    run_dir = Path(run_dir)
    pairing = _load_json(run_dir / "audit" / "pairing_map.json", None)
    assignment = _load_json(run_dir / "audit" / "convention_assignment.json", {}) or {}
    return {
        "run_dir": run_dir,
        "pairing": pairing if isinstance(pairing, dict) else None,
        "assignment": assignment if isinstance(assignment, dict) else {},
        "evidence": call_evidence.load(run_dir),
        "bus_rule_pairs": _bus_rule_pairs(run_dir),
    }


def resolve_units(expected_unit, artifacts):
    """The parsed document's unit ids the key's `unit` names, by the scorer's own
    rule (a case-insensitive substring of the unit id). None when no pairing map
    exists to resolve against; [] when the map has no such unit."""
    pairing = artifacts.get("pairing")
    if pairing is None:
        return None
    needle = str(expected_unit or "").lower()
    out = []
    for _doc, entry in pairing.items():
        for u in (entry.get("units") if isinstance(entry, dict) else None) or []:
            uid = str(u.get("unit_id") or "")
            if needle and needle in uid.lower() and uid not in out:
                out.append(uid)
    return out


def resolve_rule(expected_rule, artifacts):
    """The registry id (CONV-NNN) for the key's rule id, from the assignment file's
    own source_rule_id column first, then from any typed Finding's
    (source_rule_id, rule_id) pair on the bus. None when nothing saved maps it."""
    wanted = str(expected_rule or "").upper()
    by_rule = (artifacts.get("assignment") or {}).get("by_rule") or {}
    if wanted in by_rule:
        return wanted
    for rid, row in by_rule.items():
        if str((row or {}).get("source_rule_id") or "").upper() == wanted:
            return rid
    return artifacts.get("bus_rule_pairs", {}).get(wanted)


def _loaded_rule_ids(artifacts):
    ids = set((artifacts.get("assignment") or {}).get("by_rule") or {})
    for _doc, entry in (artifacts.get("pairing") or {}).items():
        for u in (entry.get("units") if isinstance(entry, dict) else None) or []:
            for k in ("paired", "rejected", "undecided"):
                for p in u.get(k) or []:
                    if isinstance(p, dict) and p.get("rule_id"):
                        ids.add(p["rule_id"])
    return ids


def _pair_status(artifacts, unit_id, rule_id):
    """What the pairing map recorded for (unit, rule): ("paired", reason),
    ("rejected", reason), ("undecided", reason) or ("absent", "")."""
    for _doc, entry in (artifacts.get("pairing") or {}).items():
        for u in (entry.get("units") if isinstance(entry, dict) else None) or []:
            if u.get("unit_id") != unit_id:
                continue
            for k in ("paired", "rejected", "undecided"):
                for p in u.get(k) or []:
                    if isinstance(p, dict) and p.get("rule_id") == rule_id:
                        return k, str(p.get("reason") or "")
    return "absent", ""


def classify(expected, artifacts):
    """Classify one missed expected defect ({unit, rule, ...}, the scorer's planted
    entry) against a run's saved artifacts. Returns {class, unit_ids,
    registry_rule_id, basis: [..]}; basis names the artifact behind every step."""
    basis = []
    units = resolve_units(expected.get("unit"), artifacts)
    if units is None:
        basis.append("no audit/pairing_map.json: the parsed document's units are not on record")
        return {"class": UNKNOWN, "unit_ids": [], "registry_rule_id": None, "basis": basis}
    if not units:
        basis.append("no unit of the parsed document contains %r (audit/pairing_map.json)"
                     % str(expected.get("unit")))
        return {"class": ABSENT_FROM_CORPUS, "unit_ids": [], "registry_rule_id": None, "basis": basis}
    basis.append("unit(s) %s in audit/pairing_map.json" % ", ".join(units))
    rid = resolve_rule(expected.get("rule"), artifacts)
    if rid is None:
        basis.append("rule %r maps to no registry id in audit/convention_assignment.json "
                     "(source_rule_id) or on the bus" % str(expected.get("rule")))
        return {"class": UNKNOWN, "unit_ids": units, "registry_rule_id": None, "basis": basis}
    if rid not in _loaded_rule_ids(artifacts):
        basis.append("rule %s (%s) was not loaded by this run (not in the assignment or the "
                     "pairing map)" % (rid, expected.get("rule")))
        return {"class": ABSENT_FROM_CORPUS, "unit_ids": units, "registry_rule_id": rid, "basis": basis}
    basis.append("rule %s is %s" % (rid, expected.get("rule")))
    evidence = artifacts.get("evidence")
    if evidence is not None:
        exposed = []
        for uid in units:
            exposed.extend(call_evidence.calls_exposing(evidence, rule_id=rid, unit_id=uid))
        if exposed:
            basis.append("logs/call_evidence.jsonl: call(s) %s carried rule %s and showed the unit"
                         % (", ".join(r.get("call_id", "?") for r in exposed), rid))
            return {"class": PRESENT_IN_PAYLOAD, "unit_ids": units, "registry_rule_id": rid,
                    "basis": basis}
        statuses = [(uid,) + _pair_status(artifacts, uid, rid) for uid in units]
        for uid, st, reason in statuses:
            basis.append("pairing map: (%s, %s) %s%s" % (uid, rid, st, (": " + reason) if reason else ""))
        basis.append("logs/call_evidence.jsonl exists for this run and records no call carrying "
                     "rule %s that showed the unit" % rid)
        return {"class": PRESENT_UPSTREAM, "unit_ids": units, "registry_rule_id": rid, "basis": basis}
    # No evidence file: the run predates the recording. Only the pairing map speaks.
    statuses = [(uid,) + _pair_status(artifacts, uid, rid) for uid in units]
    for uid, st, reason in statuses:
        basis.append("pairing map: (%s, %s) %s%s" % (uid, rid, st, (": " + reason) if reason else ""))
    if all(st != "paired" for _uid, st, _r in statuses):
        basis.append("never paired, so the rule never reached a call for this unit; no "
                     "logs/call_evidence.jsonl (the run predates the recording)")
        return {"class": PRESENT_UPSTREAM, "unit_ids": units, "registry_rule_id": rid, "basis": basis}
    basis.append("a plan existed but no logs/call_evidence.jsonl was recorded for this run: "
                 "whether the call happened and what it saw is not on record")
    return {"class": UNKNOWN, "unit_ids": units, "registry_rule_id": rid, "basis": basis}


def classify_missed(missed, run_dir):
    """Classify every missed expected defect of one run. `missed` is the list of
    planted entries the scorer found no hit for."""
    artifacts = load_run_artifacts(run_dir)
    return [dict(expected=e, **classify(e, artifacts)) for e in missed]


def summary(rows):
    counts = {c: 0 for c in CLASSES}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    return counts
