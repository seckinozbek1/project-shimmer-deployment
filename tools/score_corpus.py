#!/usr/bin/env python3
"""Score a run's deliverable against a held-out answer key. Domain-free.

The key lives in benchmark/corpora/<name>/answer_key.json, which the pipeline
never reads. Matching is MECHANICAL and prose-free, on typed fields only:

  recall        a planted entry is FOUND when a typed Finding on the run's bus
                (logs/agent_bus.jsonl) names its unit and carries its relation, or
                when an amendment in review_data.json names its unit and carries
                its operator rule id. Relation and unit id are typed; nothing here
                reads a sentence.
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
  not asked     a planted entry whose rule NO agent could act on is reported
                apart from one that was asked and answered nothing. Read from
                audit/convention_assignment.json: a rule whose status is
                `unassigned` (it carries subject tags, none matched an agent)
                or `assigned_no_consumer` (an agent declared its tag, but that
                agent consumes no rule in this mode) was never put to anything.
                Scoring those as ordinary misses says the mechanism failed
                when nothing ran, which is the opposite of what happened.

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


# A rule with one of these statuses reached no agent that could act on it, so
# nothing was ever asked about it. Read from the assignment the run itself
# wrote; the two names are convention_assignment's own vocabulary, not a set
# invented here (untagged is deliberately NOT in this set: an untagged rule
# keeps the pre-assignment routing and IS put to every review agent).
NOT_ASKED_STATUSES = ("unassigned", "assigned_no_consumer")


def _load_assignment(run_dir):
    """audit/convention_assignment.json's by_rule map, or {} when the run
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


def _not_asked_rules(assignment):
    """{operator-or-registry rule id (upper): status} for every rule no agent
    could act on. Keyed by BOTH the registry id and the operator's own id when
    the assignment carries one, since a key names the operator's id and the
    assignment is keyed by the registry's."""
    out = {}
    for rid, row in (assignment or {}).items():
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "")
        if status not in NOT_ASKED_STATUSES:
            continue
        out[str(rid).upper()] = status
        own = row.get("source_rule_id")
        if own:
            out[str(own).upper()] = status
    return out


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
    not_asked = _not_asked_rules(assignment)

    found, attributed, how, asked = [], [], [], []
    for p in planted:
        unit, rule = str(p["unit"]).lower(), str(p["rule"]).upper()
        relation = str(p.get("relation") or "")
        via_bus = any(unit in _lower(f.get("unit_id")) and
                      (not relation or str(f.get("relation")) == relation)
                      for f in findings)
        on_unit = [a for a in amendments
                   if unit in _lower(a.get("finding_unit_id"), a.get("original_text"))]
        via_rule = any(str(a.get("source_convention_ref") or "").upper() == rule for a in on_unit)
        is_found = via_bus or via_rule
        found.append(is_found)
        attributed.append(is_found and via_rule)
        how.append("bus:%s" % relation if via_bus else ("rule" if via_rule else ""))
        # Was this entry's rule put to anything at all? None when the run wrote
        # no assignment (the question is unanswerable for that run, never a
        # confident "yes"), True when the rule reached an agent that consumes
        # rules, False when the assignment says no agent could act on it.
        asked.append(None if assignment is None else rule not in not_asked)

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

    # A missed entry whose rule nothing could act on is NOT evidence the
    # mechanism failed: nothing ran. Reported apart from the misses that were
    # genuinely asked and answered nothing, and excluded from the denominator
    # of the "asked" recall figure below, which is the figure that says
    # anything about the mechanism.
    missed_not_asked = [i for i, f in enumerate(found) if not f and asked[i] is False]
    asked_idx = [i for i in range(len(planted)) if asked[i] is not False]
    asked_found = sum(found[i] for i in asked_idx)

    print("corpus          : %s" % corpus)
    print("run             : %s" % run_dir)
    print("task            : %s" % key.get("task_given_to_the_pipeline", ""))
    print("run completeness: %s" % _completeness_note(run_dir, amendments))
    print("amendments      : %d   (typed findings on the bus: %d)" % (len(amendments), len(findings)))
    print("recall          : %d/%d   (every planted entry)" % (sum(found), len(planted)))
    if assignment is None:
        print("  not asked     : unknown   (this run wrote no "
              "audit/convention_assignment.json, so whether a rule reached an "
              "agent cannot be read from its artifacts)")
    else:
        print("  not asked     : %d   (planted entries whose rule no agent could act on: "
              "unassigned or assigned_no_consumer)" % len(missed_not_asked))
        print("  recall, asked : %d/%d   (excluding the not-asked entries; THIS is the "
              "figure about the mechanism)" % (asked_found, len(asked_idx)))
    if kinds != ["unspecified"]:
        for k in kinds:
            idx = [i for i, p in enumerate(planted) if str(p.get("kind") or "unspecified") == k]
            print("  recall, %-20s : %d/%d" % (k, sum(found[i] for i in idx), len(idx)))
    print("false positives : %d" % len(false_pos))
    print("distractor hits : %d" % len(distractor))
    print("attribution     : %d of %d" % (sum(attributed), sum(found)))
    _print_relation_breakdown(findings)
    print()
    print("  planted      rule      kind                  found  attributed  asked  matched via")
    for i, (p, f, a, h) in enumerate(zip(planted, found, attributed, how)):
        asked_cell = "?" if asked[i] is None else ("yes" if asked[i] else "NO")
        print("  %-12s %-9s %-21s %-6s %-11s %-6s %s" % (p["unit"], p["rule"],
                                                         str(p.get("kind") or "unspecified"),
                                                         "yes" if f else "no",
                                                         "yes" if a else "no",
                                                         asked_cell, h))
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
    sys.path.insert(0, str(ROOT / "scripts"))
    import fn_evidence  # noqa: E402

    missed = [p for p, f in zip(planted, found) if not f]
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
