"""The ontology storage layer (night chain W7, ontology foundations).

Four things live here and nowhere else:

  SCOPE, enforced at the storage layer. Every record written carries the scope it
  was written under and every read returns only the records of the scope the store
  was opened with. The scope is bound ONCE, when the store object is made, so no
  caller has a filter to remember: a ProvisionStore opened under scope A cannot
  return a record written under scope B, whatever the caller does. The operator's
  unit of isolation is the engagement (one operator may carry two clients), but no
  engagement concept exists in the system yet and none is invented here: the
  identifier defaults to a single value (DEFAULT_SCOPE) so isolation is structural
  from the first day and the identifier can be bound to a real engagement later.
  The MECHANISM is built; the CONCEPT is not.

  PROVENANCE. Each provision record carries a small struct {time, agent, run, type}.
  type is PROVENANCE_TYPE_DOCUMENT for records that come from a document under
  review. The rule-derived path has never been exercised in any run (it is skipped
  when conventions are not loaded), so the shape of a rule-derived record is not
  known: PROVENANCE_TYPE_RULE is declared and left unfilled (None), and provenance()
  refuses to mint it until the rule path has been run and observed. There is no
  confidence field, by decision: a model-reported confidence is a number that looks
  like evidence and is not.

  DUAL TRACK. A live store (provisions.jsonl) and an immutable log
  (provisions_log.jsonl). Writing a record whose id is already current in the scope
  SUPERSEDES the current one: the new record gets the next revision and names the
  record it supersedes; the query layer (current()) returns only the highest revision
  per id, so a superseded entry is excluded at the storage query layer, never by a
  caller. Every supersession is appended to the log as an event. compact() moves the
  superseded revisions out of the live store and into the log. Nothing in this module
  rewrites or truncates the log: it is only ever appended to.

  SUPERSEDE is built. DELETE is not: the user-facing deletion case is an operator
  decision not yet finalised. delete() is declared so the intent is visible and
  refuses so nothing can rely on it; when it is built, a deletion is logged the way a
  supersession is.

Deterministic, local, no model calls, stdlib only.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OGE_STORES_DIR = ROOT / "ontology" / "stores"

# The single scope value every store is keyed by until an engagement concept exists.
DEFAULT_SCOPE = "default"

LIVE_FILENAME = "provisions.jsonl"
LOG_FILENAME = "provisions_log.jsonl"

# Provenance types. The rule case is declared and unfilled on purpose (see the module
# docstring); it is populated once the rule-derived path has been run and observed.
PROVENANCE_TYPE_DOCUMENT = "document"
PROVENANCE_TYPE_RULE = None
PROVENANCE_FIELDS = ("time", "agent", "run", "type")

# Fields the storage layer stamps on every live record. A caller-supplied value under
# one of these names is overwritten: the layer, not the caller, says what scope and
# revision a record has.
STORAGE_FIELDS = ("scope", "record_id", "revision", "supersedes", "written_at")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def provenance(*, time, agent, run, type=PROVENANCE_TYPE_DOCUMENT):
    """Build the provenance struct. Only the document type can be minted today; the
    rule type is declared (PROVENANCE_TYPE_RULE) but unfilled, and asking for it is
    refused rather than guessed. No confidence field exists and none is accepted."""
    if type != PROVENANCE_TYPE_DOCUMENT:
        raise ValueError(
            "provenance type %r cannot be minted: only %r is observed today; the "
            "rule-derived type is declared unfilled (PROVENANCE_TYPE_RULE) until that "
            "path has been run and its record shape observed" % (type, PROVENANCE_TYPE_DOCUMENT))
    if not time:
        raise ValueError("provenance needs a time")
    if not run:
        raise ValueError("provenance needs a run id")
    return {"time": str(time), "agent": agent, "run": str(run), "type": type}


def _read_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _append_jsonl(path, records):
    if not records:
        return 0
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(records)


class ProvisionStore:
    """The scoped provision store: one live file, one immutable log, one scope."""

    def __init__(self, stores_dir=None, *, scope=DEFAULT_SCOPE, live_path=None):
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("a store must be opened under a non-empty scope identifier")
        self.scope = scope
        d = Path(stores_dir) if stores_dir else OGE_STORES_DIR
        self.live_path = Path(live_path) if live_path else d / LIVE_FILENAME
        self.log_path = self.live_path.with_name(LOG_FILENAME)

    # ---- reads (every one of them is scope-filtered here, not by the caller) ----

    def _live_all_scopes(self):
        """Every record in the live file, all scopes. Private: the only reason to see
        another scope's records is to write them back untouched on compaction."""
        return _read_jsonl(self.live_path)

    def _live_in_scope(self):
        return [r for r in self._live_all_scopes() if r.get("scope") == self.scope]

    def current(self):
        """The current records of this scope: the highest revision per id. Superseded
        revisions are excluded here, at the query layer. A record carrying no scope, or
        another scope, is never returned."""
        best = {}
        for r in self._live_in_scope():
            pid = r.get("id")
            if not pid:
                continue
            prev = best.get(pid)
            if prev is None or int(r.get("revision") or 0) > int(prev.get("revision") or 0):
                best[pid] = r
        return [best[k] for k in sorted(best)]

    def superseded(self):
        """The live records of this scope that a later revision has superseded (still in
        the live file until compact() moves them to the log)."""
        current_ids = {(r["id"], r.get("record_id")) for r in self.current()}
        return [r for r in self._live_in_scope()
                if r.get("id") and (r["id"], r.get("record_id")) not in current_ids]

    def history(self, provision_id):
        """Every revision of one id in this scope, live and log, oldest first."""
        rows = [r for r in self._live_in_scope() if r.get("id") == provision_id]
        rows += [r for r in self.log_entries()
                 if r.get("event") == "compacted" and r.get("id") == provision_id]
        return sorted(rows, key=lambda r: int(r.get("revision") or 0))

    def log_entries(self):
        """The immutable log, this scope only."""
        return [r for r in _read_jsonl(self.log_path) if r.get("scope") == self.scope]

    # ---- writes ----

    def _append_log(self, entries):
        """The ONLY writer of the log, and it only appends."""
        for e in entries:
            e["scope"] = self.scope
        return _append_jsonl(self.log_path, entries)

    def append(self, records):
        """Write records under this scope. A record whose id is already current in the
        scope supersedes it (next revision, `supersedes` naming the record it replaces,
        a supersede event in the log); a new id starts at revision 1. Returns a summary."""
        current = {r["id"]: r for r in self.current()}
        written, superseded, events = [], 0, []
        for rec in records or []:
            if not isinstance(rec, dict) or not rec.get("id"):
                continue
            out = {k: v for k, v in rec.items() if k not in STORAGE_FIELDS}
            prev = current.get(out["id"])
            out["scope"] = self.scope
            out["record_id"] = uuid.uuid4().hex
            out["revision"] = int(prev.get("revision") or 0) + 1 if prev else 1
            out["supersedes"] = prev.get("record_id") if prev else None
            out["written_at"] = now_iso()
            if prev:
                superseded += 1
                events.append({"event": "supersede", "id": out["id"],
                               "from_record_id": prev.get("record_id"),
                               "to_record_id": out["record_id"],
                               "from_revision": prev.get("revision"),
                               "to_revision": out["revision"], "time": out["written_at"]})
            current[out["id"]] = out
            written.append(out)
        n = _append_jsonl(self.live_path, written)
        self._append_log(events)
        return {"scope": self.scope, "written": n, "superseded": superseded,
                "record_ids": [r["record_id"] for r in written]}

    def supersede(self, provision_id, record):
        """The explicit form: replace the current record of `provision_id` with `record`.
        Refuses when nothing current carries that id in this scope (a supersession of
        nothing is a plain write, and the caller should say so by calling append)."""
        if not any(r["id"] == provision_id for r in self.current()):
            raise KeyError("nothing current under id %r in scope %r to supersede"
                           % (provision_id, self.scope))
        rec = dict(record)
        rec["id"] = provision_id
        return self.append([rec])

    def compact(self):
        """Move this scope's superseded revisions from the live store into the log.
        Records of other scopes, and this scope's current records, are written back
        exactly as they were. Returns how many moved."""
        moved = self.superseded()
        if not moved:
            return {"scope": self.scope, "moved": 0}
        moved_ids = {(r["id"], r.get("record_id")) for r in moved}
        keep = [r for r in self._live_all_scopes()
                if not (r.get("scope") == self.scope
                        and (r.get("id"), r.get("record_id")) in moved_ids)]
        t = now_iso()
        entries = []
        for r in moved:
            e = dict(r)
            e["event"] = "compacted"
            e["moved_at"] = t
            entries.append(e)
        self._append_log(entries)
        lines = [json.dumps(r, ensure_ascii=False) for r in keep]
        self.live_path.parent.mkdir(parents=True, exist_ok=True)
        self.live_path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
        return {"scope": self.scope, "moved": len(moved)}

    def delete(self, provision_id):
        """NOT BUILT. Supersede and delete are both intended operations; the user-facing
        deletion case is an operator decision not yet finalised, so deletion is declared
        here and refused. When built, a deletion is appended to the log as an event the
        way a supersession is, and the live record is excluded at the query layer."""
        raise NotImplementedError(
            "delete is declared but not built (night W7 e): the operator has not finalised "
            "the user-facing deletion case; supersede is the only built operation")


# ---- the proposal accumulator, scoped the same way ----

def read_accumulator(path, *, scope):
    """{dedup_key: record} for one scope of the DELTA proposal accumulator. Records of
    another scope, or carrying none, are never returned."""
    out = {}
    for r in _read_jsonl(path):
        if r.get("scope") != scope:
            continue
        k = r.get("dedup_key")
        if k:
            out[k] = r
    return out


def write_accumulator(path, *, scope, by_key):
    """Rewrite one scope of the accumulator. Every record of every OTHER scope is
    written back untouched; every record written for this scope carries it."""
    others = [r for r in _read_jsonl(path) if r.get("scope") != scope and r.get("scope")]
    mine = []
    for r in by_key.values():
        r = dict(r)
        r["scope"] = scope
        mine.append(r)
    lines = [json.dumps(r, ensure_ascii=False) for r in others + mine]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
    return len(mine)
