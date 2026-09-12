#!/usr/bin/env python3
"""Score a run's deliverable against a held-out answer key. Domain-free.

The key lives in benchmark/corpora/<name>/answer_key.json, which the pipeline
never reads. Matching is MECHANICAL and prose-free, on typed fields only:

  recall        a planted entry is LOCATED when a typed Finding on the run's bus
                (logs/agent_bus.jsonl) names its unit and carries its relation, or
                when an amendment in review_data.json names its unit and carries
                its operator rule id. Relation and unit id are typed; nothing here
                reads a sentence.
  reason        located is NOT the same as detected. When the key's planted entry
                carries a typed `claim` (relation, field_label, value_a/value_b,
                in the Finding record's own vocabulary) the located finding is
                asked whether it states the SAME REASON. Three outcomes, never
                two: reason confirmed, RIGHT PLACE WRONG REASON, and unverifiable
                (located only through an amendment, which carries no typed
                reason). Only the first counts as a detection.

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

    py -3.9 -X utf8 tools/score_corpus.py --corpus <name> --run output/runs/<run-dir>
"""
from __future__ import annotations

import argparse
import glob
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


def _load_amendments(run_dir):
    hits = glob.glob(str(Path(run_dir) / "deliverables" / "*" / "review_data.json"))
    if not hits:
        # A run stopped or crashed before synthesis has no deliverable. Score what
        # exists (the typed findings on the bus) rather than refusing outright, and
        # say so: with no amendments, via_rule, attribution, false positives and
        # distractor hits are all necessarily 0 and say nothing about the run.
        print("NOTE            : no review_data.json under %s (no deliverable: the run "
              "ended before synthesis); scoring bus findings only, amendments = 0" % run_dir)
        return []
    data = json.loads(Path(hits[0]).read_text(encoding="utf-8"))
    return [a for a in data.get("amendments") or [] if isinstance(a, dict)]


def _load_bus_findings(run_dir):
    """Typed Finding records off the append-only bus: unit_id, relation, rule_id."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import finding_record  # noqa: E402

    path = Path(run_dir) / "logs" / "agent_bus.jsonl"
    out = []
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        body = msg.get("body")
        payload = body.get("payload") if isinstance(body, dict) else None
        for item in (payload.get("items") if isinstance(payload, dict) else None) or []:
            if finding_record.is_finding(item):
                out.append(item)
    return out


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


def _print_relation_breakdown(findings):
    """Every relation the run's typed findings actually carry, counted.

    Named from the data, not from a list in this file: when a relation is
    appended to the Finding record (date_window, the duration comparison, was
    the most recent) it appears here the first run that produces one, with no
    edit. A scorer that enumerated relations would have gone silent on exactly
    the newest mechanism, which is what happened before this: date_window was
    computed, posted and scored toward recall, while every per-relation view
    in this file could only see the two band relations.
    """
    counts = {}
    for f in findings:
        rel = str(f.get("relation") or "(none)")
        counts[rel] = counts.get(rel, 0) + 1
    if not counts:
        return
    print("relations found : %s" % ", ".join(
        "%s=%d" % (rel, n) for rel, n in sorted(counts.items())))


def _completeness_note(run_dir, amendments):
    """What can honestly be said about whether this run finished.

    A run directory carries NO completion marker: the bus has a BOOT event and
    no closing one, and nothing else on disk records an exit. So a run that
    was stopped mid-phase and a run that finished with nothing to say look
    identical from the artifacts alone, and this says which of the two facts
    are actually knowable rather than guessing between them. The server knows
    (it holds state and outcome per job, and derives is_partial), but the
    scorer reads a directory, not the server.
    """
    has_deliverable = bool(glob.glob(str(Path(run_dir) / "deliverables" / "*" / "review_data.json")))
    if has_deliverable:
        return ("a deliverable exists, so synthesis was reached (%d amendment(s)); "
                "whether every phase after it completed is not recorded on disk"
                % len(amendments))
    return ("NO deliverable: synthesis was never reached. From the run's own "
            "artifacts a stopped run and a completed run that produced nothing "
            "are indistinguishable (no completion marker is written), so every "
            "amendment-derived figure below is 0 by absence, not by measurement")


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


def _print_twin_check(corpus, key, findings):
    """Claims this run made that a run of the twin made IDENTICALLY.

    The twins differ exactly where the defects are, so a claim worded the same
    against both did not come from the document. This is the signal that
    exposed UNIT-VETCH on 2026-09-11, where the model said the document "does
    not mention the next calibration visit" about the flawed twin AND about the
    clean twin, whose entry states it in plain words. It was found by a person
    reading two logs side by side; this makes it something the scorer runs."""
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
    hits = glob.glob(str(Path(run_dir) / "deliverables" / "*" / "review_data.json"))
    return json.loads(Path(hits[0]).read_text(encoding="utf-8")) if hits else {}


def score_rounds(corpus, key, run_dir):
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
    false_pos = [f for f in prior
                 if norm_label(f.get("field_label")) not in key_labels
                 or not any(norm_label(r["field_label"]) == norm_label(f.get("field_label"))
                            and r["relation"] == f.get("relation") for r in rows)]
    stray_refusals = [x for x in refusals if norm_label(x.get("label")) not in key_labels]

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

    print("corpus            : %s" % corpus)
    print("run               : %s" % run_dir)
    print("task              : %s" % key.get("task", ""))
    print("prior records     : %d on the bus (computed), %d in review_data.json"
          % (len(prior), len(data.get("prior_comparisons") or [])))
    print("recall, exact     : %d/%d   (label + relation + figures)" % (exact, len(rows)))
    print("recall, relation  : %d/%d   (label + relation, figures differ)" % (relation_only, len(rows)))
    print("false positives   : %d   (a record for a label or relation the key does not give)" % len(false_pos))
    print("stray refusals    : %d   (refusals or orphans for labels the key does not list)" % len(stray_refusals))
    print("band irregular    : %d/%d found, %d/%d attributed to the operator rule; %d false positives; "
          "%d amendments" % (band_found, len(band_rows), band_attr, len(band_rows), len(band_fp), len(amendments)))
    # Every relation the run produced, including any this path has no dedicated
    # section for (a duration comparison is neither a prior record nor a band):
    # without this, a finding of a newer kind is computed, posted, and invisible
    # in the only view of the run a reader sees.
    _print_relation_breakdown(findings)
    print()
    print("  %-42s %-22s %-28s %-10s refs" % ("field", "expected", "result", "cited"))
    for field, rel, status, cited, nrefs in table:
        print("  %-42s %-22s %-28s %-10s %d" % (field, rel, status, cited, nrefs))
    if band_table:
        print()
        print("  %-42s %-22s %-10s %-10s %s" % ("band field", "expected", "result", "cited", "deliverable"))
        for field, rel, status, own, deliv in band_table:
            print("  %-42s %-22s %-10s %-10s %s" % (field, rel, status, own, deliv))
    for title, items in (("false positives", false_pos), ("stray refusals", stray_refusals),
                         ("band false positives", band_fp)):
        if items:
            print()
            print("  %s:" % title)
            for f in items:
                print("    %-42s %s" % (f.get("field_label") or f.get("label") or "", f.get("relation") or f.get("reason") or ""))
    return 0


def score(corpus, run_dir):
    key = _load_key(corpus)
    if key.get("prior_records") is not None:
        return score_rounds(corpus, key, run_dir)
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
        if is_found and ok is None and via_rule and not via_bus and p.get("claim"):
            # Located through an AMENDMENT only. Amendments carry no typed
            # relation or figures (finding_type is a coarse label such as
            # "factual", not the Finding record's relation), so the reason
            # cannot be checked from this artifact. Reported as unknown, never
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
    print("recall          : %d/%d   (every planted entry, LOCATION ONLY)"
          % (sum(found), len(planted)))
    # The third outcome. A located finding whose stated reason is not the key's
    # reason is neither a catch nor a miss, and counting it as a catch is what
    # inflated every recall figure this project has reported.
    checkable = [i for i in range(len(planted)) if reason_ok[i] is not None]
    confirmed = [i for i in checkable if reason_ok[i]]
    wrong_reason = [i for i in checkable if not reason_ok[i]]
    if checkable:
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
    _print_relation_breakdown(findings)
    _print_twin_check(corpus, key, findings)
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
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--run", required=True)
    a = ap.parse_args(argv)
    return score(a.corpus, a.run)


if __name__ == "__main__":
    sys.exit(main())
