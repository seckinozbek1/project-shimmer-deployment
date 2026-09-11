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

    found, attributed, how = [], [], []
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

    print("corpus          : %s" % corpus)
    print("run             : %s" % run_dir)
    print("task            : %s" % key.get("task_given_to_the_pipeline", ""))
    print("amendments      : %d   (typed findings on the bus: %d)" % (len(amendments), len(findings)))
    print("recall          : %d/%d" % (sum(found), len(planted)))
    if kinds != ["unspecified"]:
        for k in kinds:
            idx = [i for i, p in enumerate(planted) if str(p.get("kind") or "unspecified") == k]
            print("  recall, %-20s : %d/%d" % (k, sum(found[i] for i in idx), len(idx)))
    print("false positives : %d" % len(false_pos))
    print("distractor hits : %d" % len(distractor))
    print("attribution     : %d of %d" % (sum(attributed), sum(found)))
    print()
    print("  planted      rule      kind                  found  attributed  matched via")
    for p, f, a, h in zip(planted, found, attributed, how):
        print("  %-12s %-9s %-21s %-6s %-11s %s" % (p["unit"], p["rule"],
                                                    str(p.get("kind") or "unspecified"),
                                                    "yes" if f else "no",
                                                    "yes" if a else "no", h))
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
