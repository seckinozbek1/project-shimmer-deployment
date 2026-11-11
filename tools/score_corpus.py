#!/usr/bin/env python3
"""Score a run's deliverable against a held-out answer key. Domain-free.

The key lives in benchmark/corpora/<name>/answer_key.json, which the pipeline
never reads. Matching is MECHANICAL and prose-free, on typed fields only:

  recall        a planted entry is LOCATED when a typed Finding on the run's bus
                (logs/agent_bus.jsonl) names its unit and carries its relation, or
                when an amendment in review_data.json names its unit and carries
                its operator rule id. Relation and unit id are typed; nothing here
                reads a sentence. A judged absence is read from Python's stamped
                copy only: the model's raw reply to that call (refused answers
                included) locates nothing, and its records and the refused answers
                are counted apart (docs/OUTPUT_FORMAT.md section 5.5; D-184).
  reason        located is NOT the same as detected. When the key's planted entry
                carries a typed `claim` (relation, field_label, value_a/value_b,
                in the Finding record's own vocabulary) the located finding is
                asked whether it states the SAME REASON. Three outcomes, never
                two: reason confirmed, RIGHT PLACE WRONG REASON, and unverifiable
                (located through an older amendment without typed reason fields).
                Current computed amendments retain those fields and can confirm
                the reason without a bus finding. Only confirmed reasons count
                as detections.

                This exists because location alone inflated every recall figure
                this project reported. Measured 2026-09-11: the model emitted a
                near-identical missing_field sentence on UNIT-SPRUCE and
                UNIT-VETCH in BOTH the flawed and the clean twin, false in both
                (on VETCH it said the document does not mention the next
                calibration visit when the entry states it plainly). Two of those
                wrong sentences landed on units the key calls flawed and scored
                as catches. A key with no `claim` scores exactly as before and
                says the reason check is unavailable, so no other corpus silently
                changes meaning.
  attribution   of the found entries, how many have an amendment carrying the
                OPERATOR'S OWN rule id (source_convention_ref). Kept separate from
                recall, as the frozen wheat scorer keeps it: a correct finding that
                has lost its attribution is a correct finding with a defect, not a
                false positive. The first version of this scorer conflated the two
                and scored three correct findings as three false positives.
  false positives  amendments that match no planted entry on unit
  distractor hits  amendments against a unit the key lists as clean
  recall per kind  when a planted entry carries `kind`, recall is also given per
                kind: a corpus may plant several kinds of flaw on purpose, to
                separate what a mechanism catches from what it does not. A key
                with no `kind` field prints the overall figure alone, as before.
  review state  assignment, unit suspension and recorded call exposure are
                separate facts. A rule may be unassigned, lack a consumer, be
                suspended for this unit, or have been shown with the unit in a
                recorded call to an assigned consumer. Assignment alone does not prove a call. Missing
                or ambiguous evidence remains unknown. Raw recall retains every
                planted entry; asked recall includes only recorded exposure and
                excludes suspended units. A recorded call does not prove a
                successful response or correct reasoning.

Relations are read from finding_record, never listed here: a relation appended
to the record (date_window, the duration comparison, was the most recent) is
scored the moment it exists, and the per-relation breakdown below names every
relation the run actually produced rather than a set fixed when this was
written.

A key carrying `prior_records` (a round-N comparison, R6) is scored by score_rounds:
exact recall on label + relation + figures, relation-only matches reported apart,
false positives for any record the key does not give, stray refusals for labels
the key does not list, and the band irregularities with their attribution.

    py -3.12 -X utf8 tools/score_corpus.py --corpus <name> --run output/runs/<run-dir>

A key outside benchmark/corpora/ (a generated development bundle, a sealed test's
key handed over by path) is read with --key instead of --corpus, and its twin, when
one is to be compared, with --twin-key and --twin-run together: the twin's key file
and the folder of a run of the twin, both anywhere. The twin pairing is checked, never
assumed: the scored key must name the twin (its `twin_of` equals the twin key's
folder name or file stem), and the twin run must be a run of the twin's document (a
deliverable folder named after it). Under --key the scorer never searches
output/runs/ for a twin; without the two twin options it says the twin check was not
asked for. --corpus behaves exactly as before, an absolute path included.

    py -3.12 -X utf8 tools/score_corpus.py --key <bundle>/answer_key.json --run <run-dir> \
        [--twin-key <twin-bundle>/answer_key.json --twin-run <twin-run-dir>]

Three parts of a key (docs/INPUT_FORMAT.md section 9, D-042) are read as the format
states, and nothing else changes for a key that carries none of them:

  expected_refusals  (a negotiation-style key) each renamed term is satisfied by a
                refusal in prior_refusals on its earlier label and unit (reason_kind
                not null), reported as the expected kind or as another kind, or by a
                matched rename (a change record Python wrote on the later label, not
                absent_since_prior, with the row's figures and measure), which is then
                no false positive; the same record written by a model satisfies nothing,
                is reported apart and stays a false positive; an absent_since_prior on
                the earlier label is a fabricated withdrawal and stays a false positive;
                a refusal where none is expected, a refusal on another unit and an
                orphan are counted and satisfy nothing; a refusal or orphan of a listed
                label is not a stray refusal.
  multi-round   a run holding audit/multi_round.json is scored against the key's
                multi-round entries (its `multi_round` object, else planted and clean
                entries carrying round_id): only Python's round findings on bus channel
                multi_round count, each for the entry of its own round and document. A
                key with top-level round-scoped entries is refused on any other run
                (input format section 12, item 4). No twin check is run on a multi-round
                run, `twin_of` inside `multi_round` is not read, and no key's `archives`
                is checked.
  relations Python never writes  a planted relation the Finding record does not
                declare (unit_mismatch, rate_mismatch, copy_mismatch, carry_mismatch)
                is reported in its own section: located only by a model-written record,
                which is marked and never counted as a Python catch, else by an
                amendment on its unit under its rule (another relation's), else not.
                Since INFRA-045 the record declares all four, so the section is printed
                only by a checkout whose record does not.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPORA = ROOT / "benchmark" / "corpora"


def _load_key(corpus):
    path = CORPORA / corpus / "answer_key.json"
    if not path.is_file():
        raise SystemExit("no answer key at %s" % path)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_key_file(path):
    """A key named by path (--key, --twin-key): a JSON object, or a refusal."""
    path = Path(path)
    if not path.is_file():
        raise SystemExit("no answer key at %s" % path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("the answer key at %s is not a JSON object" % path)
    return data


def explicit_twin(key, twin_key_path, twin_run):
    """The twin named by path: (findings, run, twin name), or a refusal.

    Nothing is guessed. The scored key must declare a twin, and that twin must be
    the one named: its `twin_of` equals the twin key's folder name or file stem.
    The twin run must be a run of the twin's own document (a deliverable folder
    named after it, the rule twin_findings applies under output/runs/) and must
    hold a bus, so the comparison has something to compare."""
    twin = str(key.get("twin_of") or "")
    if not twin:
        raise SystemExit("--twin-key given, but the scored key declares no twin_of")
    twin_key_path = Path(twin_key_path)
    if twin not in (twin_key_path.parent.name, twin_key_path.stem):
        raise SystemExit("the scored key's twin is %s; %s is not that twin's key"
                         % (twin, twin_key_path))
    twin_key = _read_key_file(twin_key_path)
    stem = str(twin_key.get("document") or "").rsplit(".", 1)[0]
    if not stem:
        raise SystemExit("the twin key at %s names no document" % twin_key_path)
    run = Path(twin_run)
    if not (run / "logs" / "agent_bus.jsonl").is_file():
        raise SystemExit("no bus at %s" % (run / "logs" / "agent_bus.jsonl"))
    names = [Path(p).name for p in glob.glob(str(run / "deliverables" / "*"))]
    if stem not in names:
        raise SystemExit("%s is not a run of the twin's document %s (no deliverables/%s)"
                         % (run, twin_key.get("document"), stem))
    return _load_bus_findings(run), str(run), twin


def _load_amendments(run_dir):
    hits = glob.glob(str(Path(run_dir) / "deliverables" / "*" / "review_data.json"))
    if not hits:
        # Absence alone cannot prove where execution stopped. Completion evidence
        # is reported separately; amendment-derived zeros are not measurements.
        print("NOTE            : no review_data.json under %s (no deliverable); "
              "scoring bus findings only, amendments = 0 by absence" % run_dir)
        return []
    data = _load_review_data(run_dir)
    return [a for a in data.get("amendments") or [] if isinstance(a, dict)]


# docs/OUTPUT_FORMAT.md section 5.5: a judged absence reaches the bus twice, the model's raw
# reply (a post whose call_id a judging-call record names with this plan kind) and, when
# Python kept the answer, Python's stamped copy (body.stamped_by python). Only the stamped
# copy is read; the raw reply, refused answers included, locates nothing (issue #32, D-184;
# the benchmark adapters' record reader has read it so since D-092).
JUDGED_ABSENCE_PLAN = "absence_judged"


def _bus_lines(run_dir):
    path = Path(run_dir) / "logs" / "agent_bus.jsonl"
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if isinstance(msg, dict):
            out.append(msg)
    return out


def judged_absences(run_dir):
    """The run's judged-absence calls: {calls: their call ids, refused: the answers Python
    refused}, read from audit/pairing_map.json (one object per document) and from the bus
    lines' body.judging_calls. The refused count is the pairing map's absence_refused list
    where the map has one, else the judging-call records' absence_refused."""
    calls, refused_by_call, refused_in_map = set(), {}, None
    sources = []
    path = Path(run_dir) / "audit" / "pairing_map.json"
    if path.is_file():
        try:
            pairing = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            pairing = None
        if isinstance(pairing, dict):
            documents = [d for d in pairing.values() if isinstance(d, dict)] or [pairing]
            for document in documents:
                sources.extend(document.get("judging_calls") or [])
                if isinstance(document.get("absence_refused"), list):
                    refused_in_map = (refused_in_map or 0) + len(document["absence_refused"])
    for msg in _bus_lines(run_dir):
        body = msg.get("body")
        if isinstance(body, dict):
            sources.extend(body.get("judging_calls") or [])
    for call in sources:
        if isinstance(call, dict) and call.get("plan_kind") == JUDGED_ABSENCE_PLAN and call.get("call_id"):
            calls.add(str(call["call_id"]))
            try:
                refused_by_call[str(call["call_id"])] = int(call.get("absence_refused") or 0)
            except (TypeError, ValueError):
                refused_by_call.setdefault(str(call["call_id"]), 0)
    refused = refused_in_map if refused_in_map is not None else sum(refused_by_call.values())
    return {"calls": calls, "refused": refused}


def is_raw_judged_absence(body, calls):
    """True for the model's raw reply to a judged-absence call: not Python's stamped copy,
    and its call id is a judged-absence call's."""
    return (isinstance(body, dict) and not body.get("stamped_by") and bool(body.get("call_id"))
            and str(body["call_id"]) in calls)


def raw_judged_absence_records(run_dir):
    """How many typed records the raw judged-absence replies carry, none of them read."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import finding_record  # noqa: E402
    calls = judged_absences(run_dir)["calls"]
    count = 0
    for msg in _bus_lines(run_dir):
        body = msg.get("body")
        payload = body.get("payload") if isinstance(body, dict) else None
        if is_raw_judged_absence(body, calls) and isinstance(payload, dict):
            count += sum(1 for item in payload.get("items") or [] if finding_record.is_finding(item))
    return count


def _print_judged_absences(run_dir):
    """One line when the run made judged-absence calls: the stamped copy is what is counted,
    the raw replies' records and the refused answers are counted apart and locate nothing."""
    judged = judged_absences(run_dir)
    if not judged["calls"]:
        return
    print("judged absences : %d call(s); only Python's stamped copy is counted; %d record(s) in the "
          "models' raw replies not counted; %d answer(s) Python refused, counted apart, locating nothing"
          % (len(judged["calls"]), raw_judged_absence_records(run_dir), judged["refused"]))


def _load_bus_findings(run_dir):
    """Typed Finding records off the append-only bus: unit_id, relation, rule_id. A judged
    absence is read from Python's stamped copy only, never from the model's raw reply."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import finding_record  # noqa: E402

    out = []
    calls = judged_absences(run_dir)["calls"]
    predates = run_predates_infra_045(run_dir)
    for msg in _bus_lines(run_dir):
        body = msg.get("body")
        if is_raw_judged_absence(body, calls):
            continue
        payload = body.get("payload") if isinstance(body, dict) else None
        # S2a, item 7: who wrote each record, read off the post it travelled in,
        # kept beside the record (underscore: the scorer's own annotation).
        who = finding_record.written_by(body.get("backend"), body.get("model")) \
            if isinstance(body, dict) else finding_record.WRITTEN_BY_MODEL
        for item in (payload.get("items") if isinstance(payload, dict) else None) or []:
            if finding_record.is_finding(item):
                # D-198: on a run made before INFRA-045 the four relations were not the
                # record's, so a record carrying one is read as it was then: in the
                # section for relations Python never writes, never as a finding.
                if predates and item.get("relation") in NEVER_WRITTEN_RELATIONS:
                    continue
                item["_written_by"] = who
                out.append(item)
    return out


def _bus_items(run_dir):
    """Every item on the bus with the line it travelled in: (line, item, written by). A
    judged absence's raw model reply is skipped, as in _load_bus_findings."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import finding_record  # noqa: E402

    calls = judged_absences(run_dir)["calls"]
    for msg in _bus_lines(run_dir):
        body = msg.get("body")
        if is_raw_judged_absence(body, calls):
            continue
        payload = body.get("payload") if isinstance(body, dict) else None
        if not isinstance(payload, dict):
            continue
        who = finding_record.written_by(body.get("backend"), body.get("model"))
        for item in payload.get("items") or []:
            if isinstance(item, dict):
                yield msg, item, who


# The key relations the input format (section 9, the table of relations) says Python
# never writes. They are KEY vocabulary, named by the format, not Finding-record
# relations: finding_record.is_finding does not read them, so _load_bus_findings can
# never locate such an entry. An older key's own relation outside the record (the
# catalogue corpus's `vocabulary`) is not one of them and scores exactly as before.
# Constitution amendment INFRA-045 (RELATIONS-A, 2026-10-31) appended all four to the
# record, so under the current record none of them is in this set any more and each is
# scored like every other relation; the set stays so that a record without them (an
# older checkout) still reports them apart.
NEVER_WRITTEN_RELATIONS = ("unit_mismatch", "rate_mismatch", "copy_mismatch", "carry_mismatch")


def run_predates_infra_045(run_dir):
    """D-198: whether the run was made by code before constitution amendment INFRA-045
    appended the four relations. Every paired review since writes `relation_refusals`
    (empty or not) into each document of its pairing map, and every round review into each
    document of audit/round_reuse.json; a run whose saved maps hold documents and none
    carries it was made before. A run with neither file tells nothing and is not read as
    older (the same reading as tools/miss_diagnosis.written_after_run)."""
    run_dir = Path(run_dir)
    docs = []
    pm = run_dir / "audit" / "pairing_map.json"
    try:
        data = json.loads(pm.read_text(encoding="utf-8")) if pm.is_file() else {}
    except (OSError, ValueError):
        data = {}
    docs += [e for e in (data.values() if isinstance(data, dict) else []) if isinstance(e, dict)]
    rr = run_dir / "audit" / "round_reuse.json"
    try:
        reuse = json.loads(rr.read_text(encoding="utf-8")) if rr.is_file() else {}
    except (OSError, ValueError):
        reuse = {}
    for rnd in (reuse.get("rounds") if isinstance(reuse, dict) else None) or []:
        docs += [d for d in (rnd.get("documents") if isinstance(rnd, dict) else None) or []
                 if isinstance(d, dict) and d.get("availability") != "missing_document"]
    return bool(docs) and not any("relation_refusals" in d for d in docs)


def unwritten_relations(entries, run_dir=None):
    """The planted relations of NEVER_WRITTEN_RELATIONS that the Finding record still does
    not declare, in key order. A relation the record comes to declare leaves this set and
    is scored like every other the moment it does, except on a run made before INFRA-045
    (run_predates_infra_045, D-198), where the four are read as the record read them then."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import finding_record  # noqa: E402
    declared = set(finding_record.relations())
    if run_dir is not None and run_predates_infra_045(run_dir):
        declared -= set(NEVER_WRITTEN_RELATIONS)
    out = []
    for p in entries:
        rel = str(p.get("relation") or "")
        if rel in NEVER_WRITTEN_RELATIONS and rel not in declared and rel not in out:
            out.append(rel)
    return out


def load_unwritten_records(run_dir, relations):
    """Bus items carrying one of `relations` and a record_verdict, the Finding record's
    shape on a relation it does not declare, each with who wrote it and its envelope's
    document id, read the way section 5.3 of the output format reads a finding."""
    out = []
    for msg, item, who in _bus_items(run_dir):
        if item.get("relation") in relations and "record_verdict" in item:
            rec = dict(item)
            rec["_written_by"] = who
            rec["_doc_id"] = str(((msg.get("body") or {}).get("payload") or {}).get("doc_id") or "")
            rec["_channel"] = str(msg.get("channel") or "")
            out.append(rec)
    return out


def score_unwritten(entries, records, located_by_amendment, matches):
    """One row per planted entry whose relation Python never writes.

    `records` are the bus items of load_unwritten_records; `matches(entry, record)` says
    whether a record is on the entry's unit (and round and document, for a multi-round
    key) with its relation; `located_by_amendment(i)` whether the entry was located by
    an amendment on its unit under its rule. A model-written record locates the entry and
    may confirm its reason (the input format's claim test); it is a model's, marked as
    such, never a Python catch. A record on a Python post is counted nowhere: Python
    writes no such relation, so it is reported as an anomaly."""
    rows = []
    for i, p in entries:
        hits = [r for r in records if matches(p, r)]
        model = [r for r in hits if r.get("_written_by") != "python"]
        python = [r for r in hits if r.get("_written_by") == "python"]
        reason = _reason_matches(p.get("claim"), model)[0] if model else None
        if model:
            status = "model"
        elif located_by_amendment(i):
            status = "amendment"
        else:
            status = "none"
        rows.append({"entry": p, "status": status, "reason": reason,
                     "model_records": len(model), "python_records": len(python)})
    return rows


def _print_unwritten(rows, mark, amendments_possible=True):
    """The section for the relations Python never writes, printed only when the key has
    such an entry, so a key without one prints exactly what it printed before."""
    if not rows:
        return
    counts = {}
    for r in rows:
        rel = str(r["entry"].get("relation"))
        counts[rel] = counts.get(rel, 0) + 1
    print("relations Python never writes : %d planted entr%s (%s); never counted as a "
          "Python catch" % (len(rows), "y" if len(rows) == 1 else "ies",
                            ", ".join("%s=%d" % kv for kv in sorted(counts.items()))))
    print("  located by a model's record : %d   (%s)"
          % (sum(r["status"] == "model" for r in rows), mark))
    print("  reason confirmed by a model's record : %d" % sum(r["reason"] is True for r in rows))
    if amendments_possible:
        print("  located by an amendment only : %d   (an amendment on the unit under the "
              "entry's rule, built from a finding of another relation: not this flaw's "
              "relation)" % sum(r["status"] == "amendment" for r in rows))
    print("  not located   : %d" % sum(r["status"] == "none" for r in rows))
    stamped = sum(r["python_records"] for r in rows)
    if stamped:
        print("  on a Python post : %d record(s)   (Python writes no such relation; "
              "counted nowhere)" % stamped)
    for r in rows:
        p = r["entry"]
        where = " ".join(str(p.get(k)) for k in ("round_id", "document_id") if p.get(k))
        what = {"model": "located by a model's record (%d), reason %s"
                         % (r["model_records"], {True: "confirmed", False: "WRONG",
                                                 None: "not checkable"}[r["reason"]]),
                "amendment": "located by an amendment only",
                "none": "not located"}[r["status"]]
        print("      %-12s %-9s %-14s %s%s" % (p.get("unit"), p.get("rule"), p.get("relation"),
                                             (where + "  ") if where else "", what))


def _lower(*parts):
    return " ".join(str(p or "") for p in parts).lower()


def _load_assignment(run_dir):
    """audit/convention_assignment.json's by_rule map, or None when the run
    predates the assignment (every run before 2026-09-11) or never wrote one.
    An absent file is not an error: it means the question this reader answers
    cannot be answered for that run, and the caller says so rather than
    reporting a confident zero."""
    path = Path(run_dir) / "audit" / "convention_assignment.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    by_rule = data.get("by_rule")
    return by_rule if isinstance(by_rule, dict) else None


def _print_relation_breakdown(findings, confirmed=()):
    """Every relation the run's typed findings actually carry, counted.

    S2a, item 7: "relations found" counts only a relation Python computed or the
    key confirmed (`confirmed`: model findings whose stated reason matched a
    planted entry's claim). A relation only a model's unconfirmed finding carries
    is printed on its own line and marked, so a model's "sum_mismatch" is never
    read as a sum the run found wrong.

    Named from the data, not from a list in this file: when a relation is
    appended to the Finding record (date_window, the duration comparison, was
    the most recent) it appears here the first run that produces one, with no
    edit. A scorer that enumerated relations would have gone silent on exactly
    the newest mechanism, which is what happened before this: date_window was
    computed, posted and scored toward recall, while every per-relation view
    in this file could only see the two band relations.
    """
    counts, model_only = {}, {}
    confirmed_ids = {id(f) for f in confirmed}
    for f in findings:
        rel = str(f.get("relation") or "(none)")
        python_made = f.get("_written_by", "model") == "python"
        target = counts if (python_made or id(f) in confirmed_ids) else model_only
        target[rel] = target.get(rel, 0) + 1
    if not counts and not model_only:
        return
    print("relations found : %s" % (", ".join(
        "%s=%d" % (rel, n) for rel, n in sorted(counts.items())) or "(none)"))
    if model_only:
        print("model-only relations (written by a model, not confirmed by Python or "
              "the key; not counted above): %s" % ", ".join(
                  "%s=%d" % (rel, n) for rel, n in sorted(model_only.items())))


def _completeness_note(run_dir, amendments):
    """Completion evidence and deliverable presence answer different questions."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_completion
    record = run_completion.read(run_dir)
    has_deliverable = bool(glob.glob(str(Path(run_dir) / "deliverables" / "*" / "review_data.json")))
    artifact = ("deliverable present (%d amendment(s))" % len(amendments) if has_deliverable
                else "NO deliverable; amendment-derived zeros are by absence, not by measurement")
    if record is not None:
        if record["state"] == "completed":
            result = "COMPLETED: pipeline reached its end and returned 0"
            if record.get("amendment_count") == 0:
                result += "; completed with zero reported amendments"
            if not has_deliverable:
                result += "; saved completion does not supply the missing deliverable"
        elif record["state"] == "running":
            result = "INCOMPLETE: started with no recorded finish; may still be running or have been killed"
        else:
            label = "FINISHED WITHOUT SUCCESS" if record.get("reached_end") else "INCOMPLETE"
            result = "%s: %s (exit_code=%s, reached_end=%s)" % (
                label, record["state"], record.get("exit_code"), record.get("reached_end"))
        return result + "; " + artifact
    # Older server runs already persist process state. It does not establish that
    # every pipeline phase ran: historical early returns can also have exit code 0.
    try:
        job = json.loads((Path(run_dir) / "status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        job = None
    if isinstance(job, dict) and isinstance(job.get("status"), str):
        return ("server recorded process status=%s, exit_code=%s; pipeline end-of-work "
                "completion is unrecorded; %s" % (job["status"], job.get("exit_code"), artifact))
    if has_deliverable:
        return ("a deliverable exists, so synthesis was reached (%d amendment(s)); "
                "whether every phase after it completed is not recorded on disk"
                % len(amendments))
    return ("completion UNKNOWN: no valid pipeline or server record; " + artifact)


def _claim_signature(finding):
    """What a finding CLAIMS, as a comparable tuple, with the unit stripped out.

    Unit id is deliberately excluded: the same hallucinated sentence lands on
    the same unit in both twins, so including it would make every pair match
    and prove nothing. What is compared is the claim itself, and the model's
    own sentence, whitespace-folded and lowercased."""
    expl = " ".join(str(finding.get("explanation") or "").split()).lower()
    return (str(finding.get("relation") or ""),
            str(finding.get("field_label") or finding.get("stated_field") or "").lower(),
            expl)


def twin_findings(corpus, key):
    """Typed findings from the most recent scored run of this corpus's TWIN, or
    None when the key declares no twin or no run of it exists on disk.

    Returns None rather than an empty list when the comparison cannot be made,
    so the caller says "not available" instead of "nothing matched"."""
    twin = key.get("twin_of")
    if not twin:
        return None, None
    runs = sorted(glob.glob(str(ROOT / "output" / "runs" / "*")), reverse=True)
    for run in runs:
        bus = Path(run) / "logs" / "agent_bus.jsonl"
        if not bus.is_file():
            continue
        # The run must be OF the twin: its deliverable folder is named after the
        # twin's document, which the twin's own key states.
        names = [Path(p).name for p in glob.glob(str(Path(run) / "deliverables" / "*"))]
        twin_key_path = CORPORA / twin / "answer_key.json"
        if not twin_key_path.is_file():
            return None, None
        twin_doc = str(json.loads(twin_key_path.read_text(encoding="utf-8"))
                       .get("document") or "")
        stem = twin_doc.rsplit(".", 1)[0]
        if stem and any(stem == n for n in names):
            return _load_bus_findings(run), run
    return None, None


def _print_twin_check(corpus, key, findings, twin=None, by_path=False):
    """Claims this run made that a run of the twin made IDENTICALLY.

    The twins differ exactly where the defects are, so a claim worded the same
    against both did not come from the document. This is the signal that
    exposed UNIT-VETCH on 2026-09-11, where the model said the document "does
    not mention the next calibration visit" about the flawed twin AND about the
    clean twin, whose entry states it in plain words. It was found by a person
    reading two logs side by side; this makes it something the scorer runs.

    `twin` is explicit_twin's result when the twin was named by path; `by_path`
    says the key itself was read by path (--key)."""
    if twin is not None:
        twin_hits, twin_run, _name = twin
    elif by_path:
        # A key read by path never borrows a twin from output/runs/: the twin's
        # name there is a bundle folder, not a corpus, and a run found by name
        # could be a run of another bundle that happens to share it.
        if key.get("twin_of"):
            print("twin check      : not asked (the key names twin %s; pass --twin-key "
                  "and --twin-run to compare)" % key.get("twin_of"))
        return
    else:
        twin_hits, twin_run = twin_findings(corpus, key)
    if twin_hits is None:
        if key.get("twin_of"):
            print("twin check      : unavailable (no scored run of %s on disk)"
                  % key.get("twin_of"))
        return
    mine = {}
    for f in findings:
        sig = _claim_signature(f)
        if sig[2]:
            mine.setdefault(sig, []).append(f)
    theirs = {}
    for f in twin_hits:
        sig = _claim_signature(f)
        if sig[2]:
            theirs.setdefault(sig, []).append(f)
    shared = [s for s in mine if s in theirs]
    print("twin check      : %d claim(s) worded identically in both twins (%s)"
          % (len(shared), Path(twin_run).name))
    if shared:
        print("                  a claim identical across both twins did not come from "
              "the document: the twins differ exactly where the defects are")
    for sig in shared[:6]:
        units = sorted({str(f.get("unit_id") or "?") for f in mine[sig]})
        print("    %-14s %-16s %s" % (sig[0], ",".join(units)[:16], sig[2][:78]))


def p_claim(entry):
    """The typed claim on a planted entry, or None."""
    c = entry.get("claim") if isinstance(entry, dict) else None
    return c if isinstance(c, dict) and c else None


def _claim_figures(claim):
    """The two figures a typed claim states, as a set, ignoring order.

    A claim that states 61 against a stated band of 60 and a finding that says
    60 against 61 are the same claim read from opposite ends, so the pair is
    compared as a set rather than positionally."""
    out = set()
    for k in ("value_a", "value_b"):
        v = claim.get(k)
        if v is None:
            continue
        try:
            out.add(round(float(v), 6))
        except (TypeError, ValueError):
            out.add(str(v).strip().lower())
    return out


def _reason_matches(claim, bus_hits):
    """Does a located finding state the SAME REASON the key states?

    Returns (ok, why): ok is True when a finding agrees on the reason, False
    when one was located but says something else, and None when the question
    cannot be asked (no typed claim in the key, or nothing located).

    The scorer used to match a planted entry on unit and relation alone and
    call that a catch. Measured on 2026-09-11: the model produced a
    near-identical missing_field sentence on UNIT-SPRUCE and UNIT-VETCH in BOTH
    the flawed and the clean twin, and on VETCH the sentence is false in both
    (it says the document does not mention the next calibration visit when the
    entry states it in plain words). Two of those wrong sentences landed on
    units the key calls flawed and were counted as catches. A coincidence that
    scores is worse than a miss, because it inflates the figure the whole
    project is judged on.

    What is compared, all typed, no prose:
      - the relation must be the one the key states
      - the field_label, when both state one, must normalise equal
      - the figures, when the key states them, must appear on the finding

    A key with no `claim` yields None everywhere and the corpus scores exactly
    as it did before, so no other corpus changes meaning."""
    if not isinstance(claim, dict) or not claim:
        return None, "key states no typed claim"
    if not bus_hits:
        return None, ""
    want_rel = str(claim.get("relation") or "").strip().lower()
    want_field = str(claim.get("field_label") or "").strip().lower()
    want_figs = _claim_figures(claim)
    misses = []
    for f in bus_hits:
        if want_rel and str(f.get("relation") or "").strip().lower() != want_rel:
            misses.append("relation %r, key says %r"
                          % (str(f.get("relation") or ""), want_rel))
            continue
        if want_field:
            got_field = str(f.get("field_label") or f.get("stated_field") or "").strip().lower()
            if got_field and got_field != want_field:
                misses.append("field %r, key says %r" % (got_field, want_field))
                continue
        if want_figs:
            got = set()
            for k in ("value_a", "value_b"):
                v = f.get(k)
                if v is None:
                    continue
                try:
                    got.add(round(float(v), 6))
                except (TypeError, ValueError):
                    got.add(str(v).strip().lower())
            if not (want_figs <= got):
                misses.append("figures %s, key states %s"
                              % (sorted(got) or "none", sorted(want_figs)))
                continue
        return True, ""
    return False, "; ".join(misses[:2]) or "no finding states the key's reason"


def _suspension_for(entry, unit_id, rule_id, source_rule_id):
    """Read the planner's persisted withdrawal; never re-evaluate a condition."""
    for row in entry.get("suspended") or []:
        if not isinstance(row, dict) or row.get("unit_id") != unit_id:
            continue
        if (str(row.get("rule_id") or "").upper() == rule_id.upper()
                or (source_rule_id and str(row.get("source_rule_id") or "").upper()
                    == source_rule_id.upper())):
            return row
    return None


def _review_state(expected, assignment, artifacts):
    """State of one expected (unit, rule), from saved artifacts only.

    Suspension describes the paired review's withdrawal even if an earlier
    broad prompt exposed the rule. It does not erase any finding from raw recall.
    A shorthand matching several units/documents is ambiguous, never a reason
    to extend one unit's suspension to another.
    """
    import call_evidence

    if assignment is None:
        return "unknown"
    wanted = str(expected.get("rule") or "").upper()
    rows = [(rid, row) for rid, row in assignment.items() if isinstance(row, dict)
            and (str(rid).upper() == wanted
                 or str(row.get("source_rule_id") or "").upper() == wanted)]
    if len(rows) != 1:
        return "unknown"
    rid, row = rows[0]
    status = row.get("status")
    if status == "unassigned":
        return "never_assigned"
    if status == "assigned_no_consumer":
        return "no_consumer"
    if status not in ("assigned", "untagged"):
        return "unknown"
    needle = str(expected.get("unit") or "").lower()
    matches = [(doc_id, entry, u.get("unit_id"))
               for doc_id, entry in (artifacts.get("pairing") or {}).items()
               if isinstance(entry, dict)
               for u in entry.get("units") or [] if isinstance(u, dict)
               and needle and needle in str(u.get("unit_id") or "").lower()]
    if len(matches) != 1:
        return "unknown"
    doc_id, entry, uid = matches[0]
    if _suspension_for(entry, uid, rid, str(row.get("source_rule_id") or "")):
        return "suspended"
    evidence = artifacts.get("evidence")
    if evidence is None:
        return "unknown"
    consumers = row.get("consumer_agents")
    if not isinstance(consumers, list) or not consumers:
        # Older/untagged assignments may not record their fallback consumers.
        # Do not infer a judging role from an unrelated production call.
        return "unknown"
    # Paired-call logging historically writes the numeric document position,
    # not its name. The unique unit match above supplies the identity in that
    # case. A numeric value that is an actual document key keeps that identity.
    scoped = [r for r in evidence if isinstance(r, dict)
              and (r.get("doc_id") in (None, "", doc_id)
                   or (str(r.get("doc_id")).isdecimal()
                       and str(r.get("doc_id")) not in artifacts["pairing"]))
              and r.get("agent") in consumers]
    if call_evidence.calls_exposing(scoped, rule_id=rid, unit_id=uid):
        return "asked"
    return "assigned_not_asked"


def _load_review_data(run_dir):
    """Read every document's master, matching the run-wide scope of bus findings.

    Keep the full single-document object for compatibility. For multiple masters,
    combine only the record collections the scorer consumes, without deduplicating
    findings or inventing any missing typed fields.
    """
    hits = sorted(Path(run_dir).glob("deliverables/*/review_data.json"))
    if not hits:
        return {}
    records = [json.loads(path.read_text(encoding="utf-8")) for path in hits]
    if len(records) == 1:
        return records[0]
    return {field: [item for record in records for item in (record.get(field) or [])]
            for field in ("amendments", "prior_comparisons", "prior_refusals", "prior_orphans")}


def python_written(record):
    """True for a record whose bus post was Python's (finding_record.written_by, kept by
    _load_bus_findings as `_written_by`). Only such a change record can match a rename."""
    return record.get("_written_by") == "python"


def read_expected_refusals(rows, prior_refusals, prior, norm_label, norm_unit, close,
                           prior_orphans=()):
    """Each `expected_refusals` row of a negotiation-style key, as section 9 counts it.

    A REFUSAL satisfies the row when the row's reason_kind is not null and
    prior_refusals holds an entry whose label normalises to the row's field_label and
    whose unit_id is the row's unit_id; its kind is reported beside it, and a refusal of
    another kind still satisfies the row but is never counted as the expected kind. A
    MATCHED RENAME satisfies the row whatever its reason_kind: a computed change record
    WRITTEN BY PYTHON on later_field_label, any relation but absent_since_prior, whose
    value_a and value_b are the row's within the comparison tolerance, in the row's
    measure. The same record written by a model satisfies nothing: it is reported apart,
    marked as a model's, and stays a false positive. An absent_since_prior on field_label
    is a FABRICATED WITHDRAWAL. Counted and named, never satisfying: a refusal where the
    key expects none (reason_kind null), a refusal of field_label on another unit, and an
    orphan (prior_orphans) of field_label.

    Returns (results, matched): one dict per row, and the Python change records matched
    as renames, which the caller does not count as false positives."""
    results, matched = [], []
    for r in rows:
        if not isinstance(r, dict) or not r.get("field_label") or not r.get("later_field_label"):
            raise SystemExit("every expected_refusals row needs field_label and later_field_label")
        label, later = norm_label(r["field_label"]), norm_label(r["later_field_label"])
        want = r.get("reason_kind")
        on_label = [x for x in prior_refusals if isinstance(x, dict)
                    and norm_label(x.get("label")) == label]
        refused = [x for x in on_label if str(x.get("unit_id") or "") == str(r.get("unit_id") or "")]
        elsewhere = [x for x in on_label if str(x.get("unit_id") or "") != str(r.get("unit_id") or "")]
        orphaned = [x for x in prior_orphans if isinstance(x, dict)
                    and norm_label(x.get("label")) == label]
        got = sorted({str(x.get("reason_kind")) for x in refused})
        candidates = [f for f in prior if norm_label(f.get("field_label")) == later
                      and f.get("relation") != "absent_since_prior"
                      and close(f.get("value_a"), r.get("value_a"))
                      and close(f.get("value_b"), r.get("value_b"))
                      and norm_unit(f.get("unit_b")) == norm_unit(r.get("unit"))]
        renames = [f for f in candidates if python_written(f)]
        model_renames = [f for f in candidates if not python_written(f)]
        withdrawn = [f for f in prior if norm_label(f.get("field_label")) == label
                     and f.get("relation") == "absent_since_prior"]
        by_refusal = want is not None and bool(refused)
        kind_ok = by_refusal and any(x.get("reason_kind") == want for x in refused)
        status = []
        if by_refusal:
            status.append("refused, %s as expected" % want if kind_ok
                          else "refused as %s, OTHER KIND (key: %s)" % ("/".join(got), want))
        elif refused:
            status.append("refused as %s, key expects none" % "/".join(got))
        if elsewhere:
            status.append("refused on another unit (%s)"
                          % ",".join(sorted({str(x.get("unit_id") or "") for x in elsewhere})))
        if orphaned:
            status.append("orphaned")
        if renames:
            status.append("matched rename")
        if model_renames:
            status.append("rename matched by a model's record only (not counted)")
        if withdrawn:
            status.append("FABRICATED WITHDRAWAL")
        matched.extend(renames)
        results.append({"row": r, "want": want, "satisfied": by_refusal or bool(renames),
                        "by_refusal": by_refusal, "kind_ok": kind_ok, "renamed": bool(renames),
                        "refused_none": want is None and bool(refused),
                        "other_unit": bool(elsewhere), "orphaned": bool(orphaned),
                        "model_renamed": len(model_renames),
                        "fabricated": len(withdrawn), "status": "; ".join(status) or "missing"})
    return results, matched


def listed_labels(results, norm_label):
    """The earlier labels expected_refusals lists: their refusals and orphans are not stray."""
    return {norm_label(x["row"]["field_label"]) for x in results}


def _print_expected_refusals(results, mark):
    satisfied = sum(x["satisfied"] for x in results)
    print("expected refusals : %d/%d satisfied (%d refused with the expected kind, %d refused "
          "with another kind, %d matched renames); %d fabricated withdrawal(s) "
          "(absent_since_prior on a renamed term's earlier label, counted in false positives); "
          "not satisfying: %d refused where none is expected, %d refused on another unit, "
          "%d orphaned"
          % (satisfied, len(results), sum(x["kind_ok"] for x in results),
             sum(x["by_refusal"] and not x["kind_ok"] for x in results),
             sum(x["renamed"] for x in results), sum(x["fabricated"] for x in results),
             sum(x["refused_none"] for x in results), sum(x["other_unit"] for x in results),
             sum(x["orphaned"] for x in results)))
    kinds = []
    for x in results:
        if x["want"] not in kinds:
            kinds.append(x["want"])
    parts = []
    for k in kinds:
        idx = [x for x in results if x["want"] == k]
        if k is None:
            parts.append("null %d/%d satisfied (no refusal expected; only a matched rename "
                         "satisfies)" % (sum(x["satisfied"] for x in idx), len(idx)))
        else:
            parts.append("%s %d/%d satisfied, %d refused with that kind"
                         % (k, sum(x["satisfied"] for x in idx), len(idx),
                            sum(x["kind_ok"] for x in idx)))
    print("  by expected kind  : %s" % "; ".join(parts))
    print("  renames matched by a model's record only : %d   (%s; satisfy no row and stay "
          "false positives)" % (sum(x["model_renamed"] for x in results), mark))


def score_rounds(corpus, key, run_dir, twin=None, result=None):
    """Score a round-N comparison key (`prior_records`, `band_irregularities`).

    Mechanical, on typed fields only: a key row is FOUND when a computed prior-version
    record on the bus carries the same normalised field label, the same relation and
    the same figures (value_b, value_a, unit); a row whose label and relation match but
    whose figures differ is reported separately, never as found. A record for a label
    the key does not list, or with a relation the key does not give for that label, is
    a FALSE POSITIVE. A band row is found when an irregular above_band / below_band
    record carries the key's label and figure; its attribution is the operator rule id
    the record cites. Refusals and records for labels outside the key are the count the
    key's expected silences are checked against.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import finding_record  # noqa: E402
    import paired_review  # noqa: E402
    import pairing_map  # noqa: E402

    def norm_label(text):
        return " ".join(pairing_map._norm_label(text))

    def norm_unit(u):
        return paired_review._unit_str(paired_review.unit_exponents(u or ""))

    def close(a, b):
        # A model-written record may put a STRING in a numeric field ("38.0%"), which
        # the contract forbids and validate_finding rejects. The scorer must not die
        # on it: an unparseable value simply does not match.
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        try:
            return paired_review._close(float(a), float(b))
        except (TypeError, ValueError):
            return False

    findings = _load_bus_findings(run_dir)
    data = _load_review_data(run_dir)
    amendments = [a for a in data.get("amendments") or [] if isinstance(a, dict)]
    prior = [f for f in findings if f.get("relation") in finding_record.PRIOR_RELATIONS
             and f.get("provenance") == "computed"]
    bands = [f for f in findings if f.get("relation") in finding_record.OUTSIDE_BAND_RELATIONS
             and str(f.get("record_verdict") or "").lower() == "irregular"]
    refusals = list(data.get("prior_refusals") or []) + list(data.get("prior_orphans") or [])

    rows = key.get("prior_records") or []
    key_labels = {norm_label(r["field_label"]) for r in rows}
    exact, relation_only, table = 0, 0, []
    for r in rows:
        label = norm_label(r["field_label"])
        cands = [f for f in prior if norm_label(f.get("field_label")) == label]
        same_rel = [f for f in cands if f.get("relation") == r["relation"]]
        hit = next((f for f in same_rel
                    if close(f.get("value_b"), r.get("value_b")) and close(f.get("value_a"), r.get("value_a"))
                    and norm_unit(f.get("unit_b")) == norm_unit(r.get("unit"))), None)
        if hit is not None:
            exact += 1
            status = "found"
        elif same_rel:
            relation_only += 1
            status = "figures differ"
        elif cands:
            status = "wrong relation: " + ",".join(sorted({str(f.get("relation")) for f in cands}))
        else:
            status = "missing"
        cited = (hit or (same_rel or cands or [{}])[0])
        table.append((r["field_label"], r["relation"], status,
                      cited.get("source_rule_id") or cited.get("rule_id") or "",
                      len(cited.get("source_refs") or [])))
    # A key with no expected_refusals reads no row here, matches no rename and lists no
    # label, so its false positives and stray refusals are exactly what they were.
    expected = key.get("expected_refusals")
    renamed, matched = read_expected_refusals(
        expected or [], list(data.get("prior_refusals") or []), prior, norm_label, norm_unit, close,
        list(data.get("prior_orphans") or []))
    matched_ids = {id(f) for f in matched}
    listed = listed_labels(renamed, norm_label)
    false_pos = [f for f in prior if id(f) not in matched_ids
                 and (norm_label(f.get("field_label")) not in key_labels
                      or not any(norm_label(r["field_label"]) == norm_label(f.get("field_label"))
                                 and r["relation"] == f.get("relation") for r in rows))]
    stray_refusals = [x for x in refusals if norm_label(x.get("label")) not in key_labels
                      and norm_label(x.get("label")) not in listed]

    band_rows = key.get("band_irregularities") or []
    band_found, band_attr, band_table = 0, 0, []
    for r in band_rows:
        label = norm_label(r["field_label"])
        hit = next((f for f in bands if f.get("relation") == r["relation"]
                    and norm_label(f.get("field_label")) == label
                    and close(f.get("value_a"), r.get("value_a"))), None)
        amend = next((a for a in amendments if str(a.get("finding_rule_id") or a.get("convention_ref"))
                      == str((hit or {}).get("rule_id"))), None) if hit else None
        own = (hit or {}).get("source_rule_id") or (amend or {}).get("source_convention_ref") or ""
        ok_attr = hit is not None and str(own).upper() == str(r.get("rule", "")).upper()
        band_found += hit is not None
        band_attr += ok_attr
        band_table.append((r["field_label"], r["relation"], "found" if hit else "missing", own,
                           "amendment" if amend else ""))
    band_fp = [f for f in bands if norm_label(f.get("field_label"))
               not in {norm_label(r["field_label"]) for r in band_rows}]
    if result is not None:
        for r, row in zip(rows, table):
            result["entries"].append({"entry": r, "found": row[2] == "found", "status": row[2]})
        for r, row in zip(band_rows, band_table):
            result["entries"].append({"entry": r, "found": row[2] == "found", "status": row[2]})
        result.update(path="rounds", planted=len(rows) + len(band_rows),
                      false_positives=len(false_pos) + len(band_fp), distractor_hits=0)

    print("corpus            : %s" % corpus)
    print("run               : %s" % run_dir)
    print("task              : %s" % key.get("task", ""))
    print("run completeness  : %s" % _completeness_note(run_dir, amendments))
    print("prior records     : %d on the bus (computed), %d in review_data.json"
          % (len(prior), len(data.get("prior_comparisons") or [])))
    print("recall, exact     : %d/%d   (label + relation + figures)" % (exact, len(rows)))
    print("recall, relation  : %d/%d   (label + relation, figures differ)" % (relation_only, len(rows)))
    print("false positives   : %d   (a record for a label or relation the key does not give)" % len(false_pos))
    print("stray refusals    : %d   (refusals or orphans for labels the key does not list)" % len(stray_refusals))
    print("band irregular    : %d/%d found, %d/%d attributed to the operator rule; %d false positives; "
          "%d amendments" % (band_found, len(band_rows), band_attr, len(band_rows), len(band_fp), len(amendments)))
    if expected is not None:
        _print_expected_refusals(renamed, finding_record.MODEL_FINDING_MARK)
    # Every relation the run produced, including any this path has no dedicated
    # section for (a duration comparison is neither a prior record nor a band):
    # without this, a finding of a newer kind is computed, posted, and invisible
    # in the only view of the run a reader sees.
    _print_relation_breakdown(findings)
    if twin is not None:
        print("twin check        : not run (a round-comparison key has no twin check; "
              "--twin-key and --twin-run were read and not compared)")
    print()
    print("  %-42s %-22s %-28s %-10s refs" % ("field", "expected", "result", "cited"))
    for field, rel, status, cited, nrefs in table:
        print("  %-42s %-22s %-28s %-10s %d" % (field, rel, status, cited, nrefs))
    if band_table:
        print()
        print("  %-42s %-22s %-10s %-10s %s" % ("band field", "expected", "result", "cited", "deliverable"))
        for field, rel, status, own, deliv in band_table:
            print("  %-42s %-22s %-10s %-10s %s" % (field, rel, status, own, deliv))
    if renamed:
        print()
        print("  %-24s %-24s %-22s %-28s %s" % ("renamed field", "later field", "unit id",
                                               "expected kind", "result"))
        for x in renamed:
            r = x["row"]
            print("  %-24s %-24s %-22s %-28s %s" % (r["field_label"], r["later_field_label"],
                                                   r.get("unit_id") or "", x["want"] or "null",
                                                   x["status"]))
    for title, items in (("false positives", false_pos), ("stray refusals", stray_refusals),
                         ("band false positives", band_fp)):
        if items:
            print()
            print("  %s:" % title)
            for f in items:
                print("    %-42s %s" % (f.get("field_label") or f.get("label") or "", f.get("relation") or f.get("reason") or ""))
    return 0


def is_multi_round_run(run_dir):
    """audit/multi_round.json is the file that marks a multi-round run (output format,
    section 2); no other run writes it."""
    return (Path(run_dir) / "audit" / "multi_round.json").is_file()


def round_scoped_key(key):
    """True when any top-level planted or clean entry carries round_id: the key of a
    multi-round case that is not negotiation-style (input format, section 9). A twin
    with no planted flaw is still such a key when only its clean entries carry it."""
    return any(isinstance(e, dict) and "round_id" in e
               for e in list(key.get("planted") or []) + list(key.get("clean") or []))


def multi_round_entries(key):
    """(planted, clean) of a multi-round key, or None when the key has none.

    A key that is also negotiation-style keeps them in its top-level `multi_round`
    object; any other multi-round key scopes its own planted and clean entries by
    round. Every entry must name its round, its document and its unit, or the key is
    refused: an entry without them could only be matched against every round."""
    block = key.get("multi_round")
    if isinstance(block, dict):
        planted, clean = block.get("planted") or [], block.get("clean") or []
    elif round_scoped_key(key):
        planted, clean = key.get("planted") or [], key.get("clean") or []
    else:
        return None
    for which, entries in (("planted", planted), ("clean", clean)):
        for n, e in enumerate(entries):
            if not isinstance(e, dict) or not all(e.get(k) for k in ("round_id", "document_id", "unit")):
                raise SystemExit("multi-round %s entry %d needs round_id, document_id and unit"
                                 % (which, n + 1))
    return planted, clean


def load_round_findings(run_dir):
    """The round findings: Finding records on bus channel multi_round, each with who
    wrote it and its envelope's doc_id (the document id). Output format section 10.2."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import finding_record  # noqa: E402
    out = []
    for msg, item, who in _bus_items(run_dir):
        if msg.get("channel") == "multi_round" and finding_record.is_finding(item):
            rec = dict(item)
            rec["_written_by"] = who
            rec["_doc_id"] = str(((msg.get("body") or {}).get("payload") or {}).get("doc_id") or "")
            out.append(rec)
    return out


def round_scope(entry, finding):
    """A finding is in an entry's scope when its round_id is the entry's round, its
    envelope's doc_id the entry's document, and the entry's unit a case-insensitive
    substring of its unit id. A finding reused into a later round belongs to the round
    it is posted in."""
    return (str(finding.get("round_id") or "") == str(entry.get("round_id"))
            and finding.get("_doc_id") == str(entry.get("document_id"))
            and str(entry.get("unit")).lower() in _lower(finding.get("unit_id")))


def _multi_round_health(run_dir):
    try:
        rec = json.loads((Path(run_dir) / "audit" / "multi_round.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rec = None
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_completion
    done = run_completion.read(run_dir)
    state = done["state"] if done is not None else "UNKNOWN (no valid audit/run_completion.json)"
    if not isinstance(rec, dict):
        return "audit/multi_round.json unreadable; completion %s" % state
    act = rec.get("activation") if isinstance(rec.get("activation"), dict) else {}
    review = rec.get("round_review") if isinstance(rec.get("round_review"), dict) else {}
    healthy = (rec.get("outcome") == "reviewed" and act.get("activated") is True
               and review.get("availability") == "recorded" and state == "completed")
    return ("%s: outcome=%s, activated=%s, round review=%s, completion=%s"
            % ("HEALTHY" if healthy else "NOT HEALTHY", rec.get("outcome", "(missing)"),
               act.get("activated"), review.get("availability", "(missing)"), state))


def score_multi_round(corpus, key, run_dir, planted, clean, twin=None, result=None):
    """Score a multi-round run against the key's multi-round entries (input format,
    section 9, "Multi-round keys").

    Only Python's round findings count (the format scores "the Python round findings
    of each round"); a model-written item on channel multi_round is counted apart. An
    entry is LOCATED by a round finding in its scope (round_scope) with its relation,
    and its reason CONFIRMED as for a single-version entry (field_label and both
    figures). A multi-round run writes no amendments, so nothing is located by one,
    and false positives and distractor hits are counted on irregular round findings:
    a false positive on a (round, document, unit) no planted entry names, a distractor
    hit on one a clean entry names. Attribution is not checked: round findings carry
    the registry id only, and a key travels without the conventions that number it."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import finding_record  # noqa: E402
    every = load_round_findings(run_dir)
    findings = [f for f in every if f.get("_written_by") == "python"]
    model_items = len(every) - len(findings)
    found, reason_ok, reason_why, how, confirmed_hits = [], [], [], [], []
    for p in planted:
        hits = [f for f in findings if round_scope(p, f)
                and str(f.get("relation")) == str(p.get("relation") or "")]
        ok, why = _reason_matches(p.get("claim"), hits)
        if ok:
            confirmed_hits.extend(hits)
        found.append(bool(hits))
        reason_ok.append(ok if hits else None)
        reason_why.append(why)
        how.append("round:%s" % p.get("relation") if hits else "")
    irregular = [f for f in findings if str(f.get("record_verdict") or "").lower() == "irregular"]
    false_pos = [f for f in irregular if not any(round_scope(p, f) for p in planted)]
    distractor = [f for f in irregular if any(round_scope(c, f) for c in clean)]
    if result is not None:
        for i, p in enumerate(planted):
            result["entries"].append({
                "entry": p, "found": found[i], "reason_ok": reason_ok[i], "reason_why": reason_why[i],
                "matched_via": how[i],
                "relations_on_unit": sorted({str(f.get("relation")) for f in findings
                                             if round_scope(p, f)})})
        result.update(path="multi_round", planted=len(planted), false_positives=len(false_pos),
                      distractor_hits=len(distractor), model_items_not_counted=model_items,
                      claims_stated=any(p_claim(e) for e in planted))

    print("corpus          : %s" % corpus)
    print("run             : %s" % run_dir)
    print("task            : %s" % (key.get("task_given_to_the_pipeline") or key.get("task") or ""))
    print("multi-round run : %s" % _multi_round_health(run_dir))
    print("round findings  : %d on bus channel multi_round written by python; %d written by "
          "a model, not counted" % (len(findings), model_items))
    print("recall          : %d/%d   (every planted entry of every round, LOCATION ONLY: round, "
          "document, unit and relation)" % (sum(found), len(planted)))
    checkable = [i for i in range(len(planted)) if reason_ok[i] is not None]
    wrong_reason = [i for i in checkable if not reason_ok[i]]
    if any(p_claim(entry) for entry in planted):
        print("  RIGHT PLACE, WRONG REASON : %d   (located in the right round, document, unit "
              "and relation, but the finding does not state the key's own reason)"
              % len(wrong_reason))
        print("  recall, reason confirmed  : %d/%d   (THIS is the figure that says a defect "
              "was actually detected)" % (sum(1 for i in checkable if reason_ok[i]), len(planted)))
        for i in wrong_reason:
            print("      %-4s %-12s %-9s %s" % (planted[i]["round_id"], planted[i]["unit"],
                                               planted[i].get("rule"), reason_why[i][:90]))
    rounds = []
    for p in planted:
        if p["round_id"] not in rounds:
            rounds.append(p["round_id"])
    for rnd in rounds:
        idx = [i for i, p in enumerate(planted) if p["round_id"] == rnd]
        print("  recall, round %-11s : %d/%d" % (rnd, sum(found[i] for i in idx), len(idx)))
    kinds = []
    for p in planted:
        k = str(p.get("kind") or "unspecified")
        if k not in kinds:
            kinds.append(k)
    if kinds != ["unspecified"]:
        for k in kinds:
            idx = [i for i, p in enumerate(planted) if str(p.get("kind") or "unspecified") == k]
            print("  recall, %-20s : %d/%d" % (k, sum(found[i] for i in idx), len(idx)))
    print("false positives : %d   (irregular round findings on a round, document and unit no "
          "planted entry names)" % len(false_pos))
    print("distractor hits : %d" % len(distractor))
    print("attribution     : not checked (round findings carry the registry id only; the case's "
          "conventions are needed to number the rules, input format section 9)")
    unwritten = unwritten_relations(planted, run_dir)
    if unwritten:
        rows = score_unwritten(
            [(i, p) for i, p in enumerate(planted) if p.get("relation") in unwritten],
            load_unwritten_records(run_dir, unwritten), lambda i: False,
            lambda p, r: round_scope(p, r) and r.get("relation") == p.get("relation"))
        _print_unwritten(rows, finding_record.MODEL_FINDING_MARK, amendments_possible=False)
    _print_relation_breakdown(findings, confirmed_hits)
    if twin is not None:
        print("twin check      : not run (a multi-round key has no twin check; --twin-key and "
              "--twin-run were read and not compared)")
    print()
    print("  round  document         planted      rule      kind                       found  reason  matched via")
    for i, p in enumerate(planted):
        rcell = "-" if reason_ok[i] is None else ("yes" if reason_ok[i] else "WRONG")
        print("  %-6s %-16s %-12s %-9s %-26s %-6s %-7s %s" % (
            p["round_id"], p["document_id"], p["unit"], p.get("rule"),
            str(p.get("kind") or "unspecified"), "yes" if found[i] else "no", rcell, how[i]))
    for title, items in (("false positives", false_pos), ("distractor hits", distractor)):
        if items:
            print()
            print("  %s:" % title)
            for f in items:
                print("    %-6s %-16s %-28s %-9s %s" % (f.get("round_id"), f.get("_doc_id"),
                                                     str(f.get("unit_id"))[:28], f.get("rule_id"),
                                                     f.get("relation")))
    return 0


def refuse_round_scoped_on_ordinary(key, run_dir):
    """Input format section 12, item 4: round-scoped entries are scored from the
    multi-round run only. Scoring them on an ordinary review would match a flaw of one
    round against a document of another, so such a key is refused on any other run."""
    if round_scoped_key(key):
        raise SystemExit("%s is not a multi-round run (no audit/multi_round.json), and the "
                         "key's entries are scoped by round: they are scored from the "
                         "multi-round run only (docs/INPUT_FORMAT.md section 12, item 4)" % run_dir)


ADAPTERS = ROOT / "benchmark" / "adapters"


def _adapter_for(benchmark):
    """The benchmark adapter module whose BENCHMARK is `benchmark`
    (benchmark/adapters/<name>/adapter.py), loaded from its file, or None."""
    import importlib.util
    for path in sorted(ADAPTERS.glob("*/adapter.py")):
        if path.parent.name != benchmark:
            continue
        if str(ADAPTERS) not in sys.path:
            sys.path.insert(0, str(ADAPTERS))
        spec = importlib.util.spec_from_file_location("shimmer_adapter_" + benchmark, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module if getattr(module, "BENCHMARK", None) == benchmark else None
    return None


LABEL_ARMS = ("B3", "B1")


def benchmark_items(key, run_dir, arm="B3", scoring=None):
    """An adapter key's items (benchmark/adapters/common/bundle.py: item_id, rule_id,
    gold, evidence_unit_ids), each labelled from the run by the adapter's own B3
    labeller (mapping.label_pipeline_arm, under v2_primary) and set beside its gold class.
    With `arm` B1, `run_dir` is a bare_model.py output folder (labels/<item id>.json,
    which benchmark/baselines/doc_judge.py also writes) labelled by the adapter's own
    mapping.label_b1; each row then carries `b1_class` in place of `b3_class`.
    Nothing here decides a label: the adapter does, and the key's gold is only read.
    The document is read whole: a document the adapter would read in segments
    (FinDVer's long filings) is labelled from its whole run, which the result says.
    `scoring` "detection_dev" (B3 only) labels by the adapters' development mode instead
    (common/detection.py, DETECTION-DEV-A): an item with no kept claim is ABSTAIN, never
    CLEAR, and the cell step's decisions in the pairing map are read (D-472). None keeps
    v2_primary; anything else is refused."""
    if arm not in LABEL_ARMS:
        raise ValueError("benchmark items are labelled for arm B3 or B1")
    if scoring not in (None, "detection_dev") or (scoring and arm != "B3"):
        raise ValueError("benchmark items are labelled under v2_primary, or B3 under detection_dev")
    adapter = _adapter_for(str(key.get("benchmark")))
    if adapter is None:
        return {"availability": "no adapter under benchmark/adapters/ names %r" % key.get("benchmark")}
    mapping = adapter.mapping
    doc_id = str(key.get("document") or "").rsplit(".", 1)[0]
    items = [{"item_id": i["item_id"], "document_id": doc_id, "rule_id": i["rule_id"]}
             for i in key["items"] if isinstance(i, dict) and i.get("item_id") and i.get("rule_id")]
    if arm == "B1":
        labels = mapping.label_b1(adapter.SPEC, items, None, run_dirs={doc_id: str(run_dir)})
    elif scoring:
        labels = adapter.detection.label_pipeline_arm(adapter.SPEC, items, None, arm="B3",
                                                      run_dirs={doc_id: str(run_dir)})
    else:
        labels = mapping.label_pipeline_arm(adapter.SPEC, items, None, arm="B3",
                                            run_dirs={doc_id: str(run_dir)})
    by_id = {r["item_id"]: r for r in labels.get("labels") or []}
    out = []
    for i in key["items"]:
        row = by_id.get(i.get("item_id")) if isinstance(i, dict) else None
        if row is None:
            continue
        try:
            gold = adapter.SPEC.gold_class(i.get("gold"))
        except ValueError:
            gold = None
        out.append({"item_id": i["item_id"], "rule_id": i["rule_id"], "gold_class": gold,
                    "%s_class" % arm.lower(): row["class"], "basis": row["basis"],
                    "cited_unit_ids": list(row.get("cited_unit_ids") or []),
                    "evidence_unit_ids": list(i.get("evidence_unit_ids") or []),
                    "evidence_beyond_cut": bool(i.get("evidence_beyond_cut")),
                    # as the key states it, None when it does not: whether the gold marks a
                    # location, which tells a whole-document item from one whose marked
                    # evidence matched no part
                    "location_measurable": i.get("location_measurable")})
    doc = next((d for d in labels.get("documents") or [] if d.get("document_id") == doc_id), {})
    return {"availability": "labelled", "arm": arm, "document_id": doc_id, "flag": mapping.FLAG,
            "clear": mapping.CLEAR, "read": "whole document (segments not read)",
            "excluded_bases": list(getattr(mapping, "EXCLUDED_BASES", ())),
            "over_context_basis": getattr(mapping, "OVER_CONTEXT_BASIS", None),
            "setup_failure_basis": getattr(mapping, "SETUP_FAILURE_BASIS", None),
            "run_failure": bool(doc.get("run_failure")),
            "failure_reasons": list(doc.get("failure_reasons") or []), "items": out}


def item_table(key_path):
    """An adapter key's item table as an adapter's items.json states it (item_id,
    document_id, rule_id, benchmark), WITHOUT its gold: what a caller that writes labels by
    item id (benchmark/baselines/doc_judge.py) needs, handed back by the one reader of a key."""
    key = _read_key_file(key_path)
    if not isinstance(key.get("benchmark"), str) or not isinstance(key.get("items"), list):
        raise SystemExit("%s is not an adapter key (no benchmark and items)" % key_path)
    doc_id = str(key.get("document") or "").rsplit(".", 1)[0]
    items = [{"item_id": i["item_id"], "document_id": doc_id, "rule_id": i["rule_id"],
              "benchmark": key["benchmark"]}
             for i in key["items"] if isinstance(i, dict) and i.get("item_id") and i.get("rule_id")]
    return {"document_id": doc_id, "benchmark": key["benchmark"], "items": items}


def _overlap(passage, wanted):
    """The longest stretch a passage and a marked sentence share, as a share of the shorter,
    whitespace-normalised: holds a sentence cut across two passages or joined to another."""
    import difflib
    a, b = " ".join(str(passage).split()), " ".join(str(wanted).split())
    if not a or not b:
        return 0.0
    block = difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return block.size / min(len(a), len(b))


def marked_passages(key_path, item_id, passages, source_path=None):
    """Which of `passages` (a list of texts) an item's marks fall on, as positions, so a caller
    scoring where a flag stands (benchmark/baselines/pair_judge.py) learns no gold text:
    {"marked": [...], "partner": [...], "references": n}. `marked` comes from the key's evidence.
    The key keeps no text of the sentence the evidence contradicts, so `partner` is read from the
    benchmark's own source file (`source_path`), through its adapter, here and nowhere else;
    `references` counts the sentences the source gives (0: the record states none)."""
    key = _read_key_file(key_path)
    item = next((i for i in key.get("items") or [] if isinstance(i, dict) and i.get("item_id") == item_id), None)
    evidence, references = [str((item or {}).get("evidence_sentence") or "")], []
    if source_path:
        adapter = _adapter_for(key["benchmark"])
        record = next((r for r in adapter.read_source(source_path)
                       if adapter.ids.opaque_item_id(adapter.BENCHMARK, r.get(adapter.DOCUMENT_ID_FIELD)) == item_id), None)
        if record is None:
            raise SystemExit("no source record for item %s" % item_id)
        evidence = adapter._texts(record.get(adapter.EVIDENCE_FIELD)) or evidence
        references = adapter._texts(record.get(adapter.REFERENCE_FIELD))
    def on(sentences):
        # Each sentence falls on its best passage alone: a contradicting sentence is often a
        # near copy of the one it contradicts, so a share test would mark both for either.
        found = set()
        for sentence in (s for s in sentences if s.strip()):
            share, best = max(((_overlap(text, sentence), n) for n, text in enumerate(passages)), default=(0.0, None))
            if share >= 0.6:
                found.add(best)
        return sorted(found)
    return {"marked": on(evidence), "partner": on(references), "references": len(references)}


def item_is_flag(key_path, item_id):
    """True when the key's gold for one item is the adapter's FLAG class: one fact, read here."""
    key = _read_key_file(key_path)
    item = next((i for i in key.get("items") or [] if isinstance(i, dict) and i.get("item_id") == item_id), None)
    if item is None:
        raise SystemExit("no item %s in %s" % (item_id, key_path))
    adapter = _adapter_for(key["benchmark"])
    return adapter.SPEC.gold_class(item.get("gold")) == "FLAG"


def key_digest(key_path):
    """The SHA-256 of a key file: what a caller records of a key it may not read."""
    return hashlib.sha256(Path(key_path).read_bytes()).hexdigest()


def key_content_digest(key_path):
    """The SHA-256 of a key's content, not its bytes: the same however the file is spaced or keyed in
    order, so a caller can tell one key's content from another's without reading it."""
    content = json.dumps(_read_key_file(key_path), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def benchmark_labels(key_path, labels_dir, arm="B1", scoring=None):
    """benchmark_items for one key file and one label folder (by default a bare_model.py
    output folder), the key read here."""
    return benchmark_items(_read_key_file(key_path), labels_dir, arm=arm, scoring=scoring)


def key_family(key):
    """The family a key belongs to, as the key itself names it: an adapter key's
    `benchmark`, a generated key's `generator.family`, else None. Read here because
    the scorer is the only reader of a key; a caller is handed the label."""
    bench = key.get("benchmark")
    if isinstance(bench, str) and bench:
        return bench
    gen = key.get("generator")
    fam = gen.get("family") if isinstance(gen, dict) else None
    return fam if isinstance(fam, str) and fam else None


def score(corpus, run_dir, key_path=None, twin_key=None, twin_run=None, result=None):
    """Score one run. `corpus` names a folder under benchmark/corpora/ (or an
    absolute path, as before); `key_path`, when given, is the key file itself and
    `corpus` is only its label. `twin_key` and `twin_run` come together or not at
    all, and name the twin's key and a run of the twin by path.

    `result`, when a dict is given, is filled with the same scoring as structured
    data (tools/miss_diagnosis.py reads it): `path` (ordinary, rounds, multi_round),
    `family` (key_family), `entries` (one row per planted or key row: the entry as
    the key states it, whether it was found, the reason check, the review state,
    the relations Python or a model wrote on its unit, and for a missed entry
    fn_evidence's class and basis), the false positive and distractor counts, and
    for an adapter key its benchmark items (benchmark_items). The printed report is
    unchanged by it."""
    if (twin_key is None) != (twin_run is None):
        raise SystemExit("--twin-key and --twin-run are given together or not at all")
    key = _read_key_file(key_path) if key_path is not None else _load_key(corpus)
    twin = explicit_twin(key, twin_key, twin_run) if twin_key is not None else None
    if result is not None:
        result.update(family=key_family(key), document=key.get("document"), entries=[])
    if is_multi_round_run(run_dir):
        entries = multi_round_entries(key)
        if entries is None:
            raise SystemExit("%s is a multi-round run (audit/multi_round.json), and the key "
                             "has no multi-round entries to score it against" % run_dir)
        return score_multi_round(corpus, key, run_dir, entries[0], entries[1], twin, result=result)
    refuse_round_scoped_on_ordinary(key, run_dir)
    if key.get("prior_records") is not None:
        return score_rounds(corpus, key, run_dir, twin, result=result)
    amendments = _load_amendments(run_dir)
    findings = _load_bus_findings(run_dir)
    planted = key.get("planted") or []
    clean = [str(u).lower() for u in key.get("clean") or []]

    assignment = _load_assignment(run_dir)
    sys.path.insert(0, str(ROOT / "scripts"))
    import fn_evidence
    artifacts = fn_evidence.load_run_artifacts(run_dir)

    found, attributed, how, review_states = [], [], [], []
    reason_ok, reason_why = [], []
    confirmed_hits = []
    for p in planted:
        unit, rule = str(p["unit"]).lower(), str(p["rule"]).upper()
        relation = str(p.get("relation") or "")
        bus_hits = [f for f in findings
                    if unit in _lower(f.get("unit_id")) and
                    (not relation or str(f.get("relation")) == relation)]
        via_bus = bool(bus_hits)
        on_unit = [a for a in amendments
                   if unit in _lower(a.get("finding_unit_id"), a.get("original_text"))]
        via_rule = any(str(a.get("source_convention_ref") or "").upper() == rule for a in on_unit)
        is_found = via_bus or via_rule
        found.append(is_found)
        attributed.append(is_found and via_rule)
        how.append("bus:%s" % relation if via_bus else ("rule" if via_rule else ""))
        # THE REASON, not only the location. A key entry carrying a typed
        # `claim` states what is actually wrong in the Finding record's own
        # vocabulary, so a located finding can be asked whether it says the
        # same thing. Without a claim the question is unanswerable and the
        # entry keeps exactly its old meaning, never a confident pass.
        # An amendment now carries the typed record it was built from
        # (finding_relation and the figures), so a claim located only through an
        # amendment can still be checked. Amendments written before that change
        # carry none of these keys and contribute nothing here, so an old run
        # stays honestly unverifiable rather than scored on absent fields.
        amend_typed = [{"relation": a.get("finding_relation"),
                        "field_label": a.get("finding_field_label"),
                        "value_a": a.get("finding_value_a"),
                        "value_b": a.get("finding_value_b")}
                       for a in on_unit
                       if str(a.get("source_convention_ref") or "").upper() == rule
                       and a.get("finding_relation")]
        ok, why = _reason_matches(p.get("claim"), bus_hits + amend_typed)
        if ok:
            confirmed_hits.extend(bus_hits)
        if is_found and ok is None and via_rule and not via_bus and p.get("claim"):
            # Located through an older AMENDMENT without typed reason fields.
            # Its coarse finding_type alone cannot establish the reason.
            # Reported as unknown, never
            # as confirmed: an unverifiable catch must not count as a verified
            # one, which is the whole point of this change.
            why = "located via amendment only; amendments carry no typed reason"
        reason_ok.append(ok if is_found else None)
        reason_why.append(why)
        review_states.append(_review_state(p, assignment, artifacts))

    planted_units = {str(p["unit"]).lower() for p in planted}
    false_pos = [a for a in amendments
                 if not any(u in _lower(a.get("finding_unit_id"), a.get("original_text"))
                            for u in planted_units)]
    distractor = [a for a in amendments
                  if any(c in _lower(a.get("finding_unit_id"), a.get("original_text"))
                         for c in clean)]

    # Recall per KIND of planted flaw, when the key labels its entries with one.
    # A corpus may plant several kinds on purpose, to separate what a mechanism
    # catches from what it does not; one overall figure would hide that
    # separation. The kind is the key's own label, read here and nowhere else;
    # a key with no `kind` field yields a single "unspecified" bucket and the
    # overall figure alone, so every other corpus scores exactly as before.
    kinds = []
    for p in planted:
        k = str(p.get("kind") or "unspecified")
        if k not in kinds:
            kinds.append(k)

    # Raw recall remains over all entries. The separate asked denominator counts
    # only recorded exposure to an assigned consumer, never mere eligibility.
    missed_not_asked = [i for i, f in enumerate(found) if not f
                        and review_states[i] in ("never_assigned", "no_consumer")]
    asked_idx = [i for i, state in enumerate(review_states) if state == "asked"]
    asked_found = sum(found[i] for i in asked_idx)

    print("corpus          : %s" % corpus)
    print("run             : %s" % run_dir)
    print("task            : %s" % key.get("task_given_to_the_pipeline", ""))
    print("run completeness: %s" % _completeness_note(run_dir, amendments))
    print("amendments      : %d   (typed findings on the bus: %d)" % (len(amendments), len(findings)))
    _print_judged_absences(run_dir)
    print("recall          : %d/%d   (every planted entry, LOCATION ONLY)"
          % (sum(found), len(planted)))
    # The third outcome. A located finding whose stated reason is not the key's
    # reason is neither a catch nor a miss, and counting it as a catch is what
    # inflated every recall figure this project has reported.
    checkable = [i for i in range(len(planted)) if reason_ok[i] is not None]
    confirmed = [i for i in checkable if reason_ok[i]]
    wrong_reason = [i for i in checkable if not reason_ok[i]]
    # A key can state a claim even when every located artifact lacks typed
    # evidence. Report those as unverifiable instead of blaming the key.
    if any(p_claim(entry) for entry in planted):
        print("  RIGHT PLACE, WRONG REASON : %d   (located on the right unit and "
              "relation, but the finding does not state the key's own reason; "
              "counted as neither a catch nor a miss)" % len(wrong_reason))
        print("  recall, reason confirmed  : %d/%d   (THIS is the figure that says a "
              "defect was actually detected)" % (len(confirmed), len(planted)))
        unverifiable = [i for i in range(len(planted))
                        if found[i] and reason_ok[i] is None and p_claim(planted[i])]
        if unverifiable:
            print("  reason unverifiable       : %d   (located, but from an artifact that "
                  "carries no typed reason; NOT counted as confirmed)" % len(unverifiable))
            for i in unverifiable:
                print("      %-12s %-9s %s" % (planted[i]["unit"], planted[i]["rule"],
                                               reason_why[i][:96]))
        for i in wrong_reason:
            print("      %-12s %-9s %s" % (planted[i]["unit"], planted[i]["rule"],
                                           reason_why[i][:96]))
    else:
        print("  reason check  : unavailable   (this key states no typed `claim` per "
              "planted entry, so a finding can only be matched by location; see "
              "the answer key's claim_note)")
    if assignment is None:
        print("  not asked     : unknown   (this run wrote no "
              "audit/convention_assignment.json, so whether a rule reached an "
              "agent cannot be read from its artifacts)")
    else:
        print("  not asked     : %d   (planted entries whose rule no agent could act on: "
              "unassigned or assigned_no_consumer)" % len(missed_not_asked))
    if review_states:
        print("  suspended     : %d   (rule withdrawn for this unit in audit/pairing_map.json)"
              % review_states.count("suspended"))
        print("  assigned, no call : %d   (no assigned consumer has recorded rule-and-unit exposure)"
              % review_states.count("assigned_not_asked"))
        print("  asked, no matched finding : %d   (recorded exposure; response success is not inferred)"
              % sum(not found[i] for i in asked_idx))
        print("  review unknown: %d   (missing or ambiguous evidence)" % review_states.count("unknown"))
    if asked_idx:
        print("  recall, asked : %d/%d   (recorded assigned-consumer exposure only; suspended, "
              "uncalled and unknown entries excluded; LOCATION ONLY)" % (asked_found, len(asked_idx)))
    if kinds != ["unspecified"]:
        for k in kinds:
            idx = [i for i, p in enumerate(planted) if str(p.get("kind") or "unspecified") == k]
            print("  recall, %-20s : %d/%d" % (k, sum(found[i] for i in idx), len(idx)))
    print("false positives : %d" % len(false_pos))
    print("distractor hits : %d" % len(distractor))
    print("attribution     : %d of %d" % (sum(attributed), sum(found)))
    unwritten = unwritten_relations(planted, run_dir)
    if unwritten:
        import finding_record
        rows = score_unwritten(
            [(i, p) for i, p in enumerate(planted) if p.get("relation") in unwritten],
            load_unwritten_records(run_dir, unwritten), lambda i: attributed[i],
            lambda p, r: (str(p["unit"]).lower() in _lower(r.get("unit_id"))
                          and r.get("relation") == p.get("relation")))
        _print_unwritten(rows, finding_record.MODEL_FINDING_MARK)
    _print_relation_breakdown(findings, confirmed_hits)
    _print_twin_check(corpus, key, findings, twin, by_path=key_path is not None)
    print()
    print("  planted      rule      kind                  found  reason  attributed  review state        matched via")
    for i, (p, f, a, h) in enumerate(zip(planted, found, attributed, how)):
        rcell = "-" if reason_ok[i] is None else ("yes" if reason_ok[i] else "WRONG")
        print("  %-12s %-9s %-21s %-6s %-7s %-11s %-19s %s" % (p["unit"], p["rule"],
                                                         str(p.get("kind") or "unspecified"),
                                                         "yes" if f else "no", rcell,
                                                         "yes" if a else "no",
                                                         review_states[i], h))
    if false_pos:
        print()
        print("  false positives:")
        for a in false_pos:
            print("  %-28s %-9s %s" % (_lower(a.get("finding_unit_id"))[:28],
                                       a.get("convention_ref"), (a.get("comment") or "")[:70]))

    # False-negative evidence: every planted entry the run did not produce is put
    # into one of four classes from the run's saved artifacts alone (the pairing
    # map, the assignment, the call evidence, the bus), so a rule the model was
    # never asked and a rule it failed to answer stop landing in one number. The
    # scorer is the only reader of the key; the classifier receives the planted
    # entry as a dict and never opens the key itself.
    missed = [p for p, f, state in zip(planted, found, review_states)
              if not f and state != "suspended"]
    rows = []
    if missed:
        rows = fn_evidence.classify_missed(missed, run_dir)
        counts = fn_evidence.summary(rows)
        print()
        print("  false-negative evidence (per missed entry, from saved artifacts only):")
        for c in fn_evidence.CLASSES:
            print("    %-46s %d" % (c, counts.get(c, 0)))
        for r in rows:
            e = r["expected"]
            print("  %-12s %-9s %-46s" % (e["unit"], e["rule"], r["class"]))
            for b in r["basis"]:
                print("      - %s" % b)
    if result is not None:
        by_entry = {id(r["expected"]): r for r in rows}
        for i, p in enumerate(planted):
            unit = str(p["unit"]).lower()
            ev = by_entry.get(id(p))
            result["entries"].append({
                "entry": p, "found": found[i], "reason_ok": reason_ok[i],
                "reason_why": reason_why[i], "attributed": attributed[i],
                "review_state": review_states[i], "matched_via": how[i],
                "relations_on_unit": sorted({str(f.get("relation")) for f in findings
                                             if unit in _lower(f.get("unit_id"))}),
                "evidence": None if ev is None else {k: ev[k] for k in
                                                     ("class", "unit_ids", "registry_rule_id", "basis")}})
        result.update(path="ordinary", planted=len(planted), false_positives=len(false_pos),
                      distractor_hits=len(distractor), amendments=len(amendments),
                      findings=len(findings), claims_stated=any(p_claim(e) for e in planted))
        if key.get("benchmark") and isinstance(key.get("items"), list) and key["items"]:
            result["benchmark_items"] = benchmark_items(key, run_dir)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--corpus", help="a folder under benchmark/corpora/ (or its absolute path)")
    source.add_argument("--key", help="an answer key file anywhere (a bundle's answer_key.json)")
    ap.add_argument("--run", required=True)
    ap.add_argument("--twin-key", help="the twin's answer key file, anywhere (with --twin-run)")
    ap.add_argument("--twin-run", help="the folder of a run of the twin, anywhere (with --twin-key)")
    a = ap.parse_args(argv)
    if (a.twin_key is None) != (a.twin_run is None):
        ap.error("--twin-key and --twin-run are given together or not at all")
    if a.key is not None:
        return score(a.key, a.run, key_path=a.key, twin_key=a.twin_key, twin_run=a.twin_run)
    return score(a.corpus, a.run, twin_key=a.twin_key, twin_run=a.twin_run)


if __name__ == "__main__":
    sys.exit(main())
