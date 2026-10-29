"""B's synthetic tests (preregistration section 13): items, the B1 item table, labels and scores.

A synthetic test is a set of bundles in the input format (docs/INPUT_FORMAT.md): the flawed
document, its clean twin and its perturbation probes, each bundle with its own
`answer_key.json` (section 9 of the format) beside its `context/` and `conventions/`. The
bundles exist already (role B writes them with benchmark/generators or by hand), so this
adapter has no build; it shares the record reader, the output-to-label lines and the
sensitivities with the five benchmark adapters (common/), and scores against the key.

  items   one item per (target document, rule): every document the bundle's targets file
          names under review, and every rule heading of its conventions carrying an
          operator id. The answer key is never read. Writes the item table (items.json)
          that bare_model.py and tools/stage_workload.py take: item_id, document_id (the
          target's file stem, the id the pipeline and B1 use), rule_id, benchmark
          `synthetic`, and beside them the bundle and the source ids.
  label   B0, B1, B2, B3 or B4 to one class per item through the shared core (section 5.1:
          records, D-066, the over-context exclusion, the rule-id map, the setup-failure
          rule of D-084, S-1 to S-8 where they apply): FLAG (`violated`) with the unit(s)
          that locate it, CLEAR (`holds`), UNDECIDED (ABSTAIN here: the test has no
          undecided class). Every record decides the rule it names (`attribute_as_named`:
          the input format makes a figure-audit record go to the rule the key names), so
          nothing is set aside and S-3 equals the primary. A FLAG of B2, B3 or B4 carries
          the records that decided it; a FLAG of B1 the units its quoted evidence lies in.
  score   against each bundle's key, per arm and analysis: location recall and
          reason-confirmed recall over the planted flaws (B2, B3, B4: a record that decided
          a FLAG of the document, under any rule, whose unit id contains the planted unit
          and whose relation is the planted relation; its reason confirmed when one such
          record states the key's claim: the matching of tools/score_corpus.py and of the
          input format, section 9, on deciding records only; the rule is the attribution,
          reported apart. B1: its FLAG on the item of the planted rule, with a quoted
          sentence in the planted unit), false positives (items flagged that the
          key does not plant, the records on units the key does not plant, unattached
          records), distractor hits, clean-twin false alarms when the twin's run is
          labelled, refusals and run failures. B1's reason is a reviewer's (section 3.3).

Standard library and the shared core only; nothing from the repository is imported.

Usage:
    py -3.12 benchmark/adapters/synthetic/adapter.py items --root <test folder> [--out items.json]
    py -3.12 benchmark/adapters/synthetic/adapter.py label --items <items.json> --bundles <test folder> --arm B0|B1|B2|B3|B4 [--runs <folder>] [--run-map <map.json>] --out <labels.json>
    py -3.12 benchmark/adapters/synthetic/adapter.py score --labels <labels.json> --bundles <test folder> --out <metrics.json> [--key-map <map.json>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from common import bundle, ids, mapping, prompt  # noqa: E402

BENCHMARK = "synthetic"
TARGETS_FILE = "_review_targets.json"
KEY_FILE = "answer_key.json"
CONTEXT_DIR, CONVENTIONS_DIR = "context", "conventions"
ITEM_PREFIX = "item:%s:" % BENCHMARK
SPEC = mapping.Spec(
    BENCHMARK,
    labels={mapping.FLAG: "violated", mapping.CLEAR: "holds", mapping.UNDECIDED: None},
    b1_labels={"violated": mapping.FLAG, "holds": mapping.CLEAR, "undecided": mapping.UNDECIDED},
    s2=True, attribute_as_named=True)
S3_NOTE = ("S-3 equals the primary analysis on B's synthetic tests: every record decides the "
           "rule it names (section 13), so nothing is set aside")
B1_REASON = "reviewer (section 3.3): B1 states no typed reason, so the adapter computes none"
NEGOTIATION_STYLE = "negotiation_style_key_not_scored"


class Refused(ValueError):
    """An input this adapter does not score."""


# ---------------------------------------------------------------------------
# bundles, targets, rules, units


def targets_path(folder: Path):
    """The bundle's targets file: `context/_review_targets.json` (the input format) or, in a
    staged workload, `_review_targets.json` at the top (tools/stage_workload.py)."""
    for path in (folder / CONTEXT_DIR / TARGETS_FILE, folder / TARGETS_FILE):
        if path.is_file():
            return path
    return None


def is_bundle(folder: Path) -> bool:
    return folder.is_dir() and (folder / CONVENTIONS_DIR).is_dir() and targets_path(folder) is not None


def bundles_under(root) -> list:
    """The bundle `root` is, or the bundles directly under it, by name."""
    root = Path(root)
    if is_bundle(root):
        return [root]
    return [p for p in sorted(root.iterdir(), key=lambda p: p.name) if is_bundle(p)] if root.is_dir() else []


def manifest(folder: Path) -> dict:
    data = json.loads(targets_path(folder).read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def target_names(folder: Path) -> list:
    return [str(t) for t in manifest(folder).get("targets") or []]


def rule_ids(folder: Path) -> list:
    """The operator ids of the bundle's rule headings, in reading order, each once."""
    seen = []
    for heading, _text in prompt.conventions_from_bundle(folder):
        rid = prompt.rule_id_of(heading)
        if rid and rid.casefold() not in {s.casefold() for s in seen}:
            seen.append(rid)
    return seen


_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.M)
_RULE_LINE = re.compile(r"^[\s\-*_=]+$")


def _slug(text, limit=40):
    value = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return value[:limit] or "unit"


def units(text: str) -> list:
    """[(unit id, text)] as Shimmer's splitter gives them for a document with headings below
    the top level (scripts/pairing_map.split_units, its heading branch and its preamble unit;
    held equal to it by scripts/adapter_checks.py): every heading of level 2 or more starts a
    unit `u<NN>-<slug>`; the text before the first one is the preamble unit `u00-<slug of the
    title>` when it holds anything but heading lines and rules. A document with no such
    heading gives no unit here (Shimmer splits it by tables; section 13 needs headings)."""
    text = text or ""
    body = [m for m in _HEADING.finditer(text) if len(m.group(1)) >= 2]
    if not body:
        return []
    out = []
    lead = text[:body[0].start()].strip()
    content = [line for line in lead.splitlines()
               if line.strip() and not _HEADING.match(line) and not _RULE_LINE.match(line)]
    if content:
        h1 = next((m.group(2).strip() for m in _HEADING.finditer(lead) if len(m.group(1)) == 1), None)
        out.append(("u00-" + _slug(h1 or "preamble"), lead))
    for i, m in enumerate(body):
        end = body[i + 1].start() if i + 1 < len(body) else len(text)
        out.append(("u%02d-%s" % (i + 1, _slug(m.group(2).strip())), text[m.start():end].strip()))
    return out


def item_id(source_item_id: str) -> str:
    return ids.sha256_hex(ITEM_PREFIX + source_item_id)[:ids.OPAQUE_LENGTH]


def item_rows(root) -> list:
    """One item per (target document, rule) of every bundle under `root`. Reads the
    targets file and the conventions only; the answer key is never opened."""
    rows, owner = [], {}
    for folder in bundles_under(root):
        rules = rule_ids(folder)
        if not rules:
            raise Refused("bundle %s has no rule heading with an operator id" % folder.name)
        for name in target_names(folder):
            doc = Path(name).stem
            if doc in owner and owner[doc] != folder.name:
                raise Refused("document id %s is under review in two bundles (%s, %s)"
                              % (doc, owner[doc], folder.name))
            owner[doc] = folder.name
            for rid in rules:
                source = "%s/%s/%s" % (folder.name, doc, rid)
                rows.append({"item_id": item_id(source), "document_id": doc, "rule_id": rid,
                             "benchmark": BENCHMARK, "bundle": folder.name,
                             "source_item_id": source,
                             "source_document_id": "%s/%s" % (folder.name, doc)})
    if not rows:
        raise Refused("no bundle with a targets file and conventions under %s" % root)
    return sorted(rows, key=lambda r: (r["bundle"], r["document_id"], r["item_id"]))


def write_items(root, out=None) -> dict:
    rows = item_rows(root)
    data = {"benchmark": BENCHMARK, "items": rows,
            "note": "one item per (target document, rule); the answer key was not read"}
    path = Path(out) if out else Path(root) / bundle.ITEM_TABLE_NAME
    bundle.write_json(path, data)
    return {"items": len(rows), "bundles": len({r["bundle"] for r in rows}), "out": str(path)}


def document_text(bundles_root, bundle_name, document_id) -> str:
    folder = Path(bundles_root) / bundle_name
    for name in target_names(folder):
        if Path(name).stem == document_id:
            return (folder / CONTEXT_DIR / name).read_text(encoding="utf-8").replace("\r\n", "\n")
    raise Refused("bundle %s names no target %s" % (bundle_name, document_id))


# ---------------------------------------------------------------------------
# labels


def b1_located_units(evidence, doc_units) -> tuple:
    """(units, ambiguous): the units B1's quoted evidence lies in. Each quoted sentence
    (section 1's sentence rule, whitespace-normalised, a closing `.`, `!` or `?` dropped,
    since a copied label line carries none) locates the one unit whose whitespace-normalised
    text holds it; a sentence held by more than one unit locates none and is counted."""
    texts = [(uid, bundle.normalise_space(text)) for uid, text in doc_units]
    found, ambiguous = set(), 0
    for sentence in bundle.sentences(evidence or ""):
        sentence = sentence.rstrip(".!?").strip()
        holders = [uid for uid, text in texts if sentence and sentence in text]
        if len(holders) == 1:
            found.add(holders[0])
        elif len(holders) > 1:
            ambiguous += 1
    return sorted(found), ambiguous


def _documents(items, bundles_root):
    by_doc = {}
    for item in items:
        by_doc.setdefault(item["document_id"], item["bundle"])
    return by_doc


def run_dirs_for(items, runs=None, run_map=None) -> dict:
    """{document id: run folder}: `run_map[bundle]` where a map is given, else
    `<runs>/<bundle>` (one run folder, or one bare_model.py output folder, per bundle)."""
    owner = {}
    for item in items:
        owner.setdefault(item["document_id"], item["bundle"])
    out = {}
    for doc, name in owner.items():
        if run_map is not None:
            if name not in run_map:
                raise Refused("the run map names no run for bundle " + name)
            out[doc] = Path(run_map[name])
        elif runs is not None:
            out[doc] = Path(runs) / name
        else:
            raise Refused("--runs or --run-map is required for this arm")
    return out


def read_synthetic_items(path) -> list:
    rows = mapping.read_items(path)
    for row in rows:
        if row.get("benchmark") != BENCHMARK or not row.get("bundle"):
            raise Refused("not an item of B's synthetic tests: " + str(row.get("item_id")))
    return rows


def label(items_path, arm, bundles_root, runs=None, run_map=None) -> dict:
    """Every analysis of one arm on the items (cli.label's set, for this adapter)."""
    items = read_synthetic_items(items_path)
    if arm == "B0":
        primary = mapping.label_b0(SPEC, items)
    elif arm == "B1":
        primary = mapping.label_b1(SPEC, items, None, run_dirs_for(items, runs, run_map))
        owner = _documents(items, bundles_root)
        cache = {}
        for row in primary["labels"]:
            row["b1_ambiguous_sentences"] = 0
            if row["class"] != mapping.FLAG:
                continue
            doc = row["document_id"]
            if doc not in cache:
                cache[doc] = units(document_text(bundles_root, owner[doc], doc))
            row["cited_unit_ids"], row["b1_ambiguous_sentences"] = b1_located_units(
                row.get("evidence"), cache[doc])
    elif arm in mapping.ARMS:
        primary = mapping.label_pipeline_arm(SPEC, items, None, arm,
                                             run_dirs_for(items, runs, run_map), detail=True)
    else:
        raise Refused("unknown arm " + repr(arm))
    owner = _documents(items, bundles_root)
    for row in primary["labels"]:
        row["bundle"] = owner[row["document_id"]]
    out = {"primary": primary, "S-1": mapping.sensitivity_s1(SPEC, primary),
           "S-2": mapping.sensitivity_s2(SPEC, primary),
           "S-3": dict(mapping.sensitivity_s3(SPEC, primary), note=S3_NOTE),
           "S-5": mapping.sensitivity_s5(SPEC, primary),
           "S-6": mapping.sensitivity_s6(SPEC, primary),
           "S-7": mapping.sensitivity_s7(SPEC, primary),
           "S-8": mapping.sensitivity_s8(SPEC, primary)}
    return out


# ---------------------------------------------------------------------------
# scoring


def read_key(folder: Path, key_map=None) -> dict:
    path = Path(key_map[folder.name]) if key_map and folder.name in key_map else folder / KEY_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise Refused("the key of %s is not a JSON object" % folder.name)
    return data


def _figures(record_or_claim) -> set:
    out = set()
    for k in ("value_a", "value_b"):
        v = record_or_claim.get(k)
        if v is None:
            continue
        try:
            out.add(round(float(v), 6))
        except (TypeError, ValueError):
            out.add(str(v).strip().lower())
    return out


def reason_matches(claim, record) -> bool:
    """tools/score_corpus.py's reason test on one record: the claim's relation, its field
    label when both state one (lowercased, trimmed), and both claim figures among the
    record's (rounded to 6 decimal places, order ignored)."""
    want_rel = str(claim.get("relation") or "").strip().lower()
    if want_rel and str(record.get("relation") or "").strip().lower() != want_rel:
        return False
    want_field = str(claim.get("field_label") or "").strip().lower()
    got_field = str(record.get("field_label") or "").strip().lower()
    if want_field and got_field and got_field != want_field:
        return False
    return _figures(claim) <= _figures(record)


def _on_unit(planted_unit: str, unit_id) -> bool:
    return bool(planted_unit) and planted_unit in str(unit_id or "").lower()


def _role(key) -> str:
    if key.get("probe"):
        return "probe"
    if not (key.get("planted") or []) and key.get("twin_of"):
        return "twin"
    return "base"


def _flagged_units(row) -> list:
    """[(unit id, written_by)] of a FLAG row: its deciding records (B2, B3, B4) or the
    units its quoted evidence lies in (B1)."""
    if row["class"] != mapping.FLAG:
        return []
    if row["arm"] == "B1":
        return [(u, "model") for u in row.get("cited_unit_ids") or []]
    return [(r.get("unit_id"), r.get("written_by")) for r in row.get("deciding_records") or []]


def score_bundle(folder, key, rows, arm) -> dict:
    """One bundle's measures from its rows of one analysis (section 13)."""
    planted = [p for p in key.get("planted") or [] if isinstance(p, dict)]
    clean = [str(c).lower() for c in key.get("clean") or []]
    by_rule = {}
    for row in rows:
        by_rule.setdefault(str(row["rule_id"]).casefold(), []).append(row)
    planted_rules = {str(p.get("rule") or "").casefold() for p in planted}
    out = {"bundle": folder.name, "role": _role(key), "probe": key.get("probe"),
           "twin_of": key.get("twin_of"), "items": len(rows),
           "gold_flag_items": sum(1 for r in rows if str(r["rule_id"]).casefold() in planted_rules),
           "flag_items": sum(1 for r in rows if r["class"] == mapping.FLAG),
           "planted": len(planted), "located": 0, "reason_confirmed": 0, "reason_checkable": 0,
           "reason_wrong": 0, "attributed": 0, "located_by": {"python": 0, "model": 0, "both": 0},
           "planted_rule_not_an_item": 0, "entries": []}
    # B2, B3, B4: every record that decided a FLAG of this document, with its item's rule
    # (docs/INPUT_FORMAT.md section 9: the rule is not used to locate a flaw or to confirm
    # its reason; it is the attribution, reported apart)
    deciding = [(str(row["rule_id"]).casefold(), r) for row in rows if row["class"] == mapping.FLAG
                for r in row.get("deciding_records") or []]
    for p in planted:
        unit = str(p.get("unit") or "").lower()
        relation = str(p.get("relation") or "")
        rule = str(p.get("rule") or "").casefold()
        claim = p.get("claim") if isinstance(p.get("claim"), dict) and p.get("claim") else None
        entry = {"unit": p.get("unit"), "rule": p.get("rule"), "relation": p.get("relation"),
                 "kind": p.get("kind"), "located": False, "reason": None, "attributed": False}
        if rule not in by_rule:
            out["planted_rule_not_an_item"] += 1
        if arm == "B1":
            # B1 states no relation: it is located on the item of the planted rule, by the
            # units its quoted evidence lies in
            row = (by_rule.get(rule) or [None])[0]
            entry["located"] = bool(row and row["class"] == mapping.FLAG and any(
                _on_unit(unit, u) for u in row.get("cited_unit_ids") or []))
            entry["attributed"] = entry["located"]
            if entry["located"]:
                out["located_by"]["model"] += 1
                entry["reason"] = B1_REASON
        else:
            hits = [(rid, r) for rid, r in deciding if _on_unit(unit, r.get("unit_id"))
                    and (not relation or str(r.get("relation") or "") == relation)]
            entry["located"] = bool(hits)
            entry["attributed"] = any(rid == rule for rid, _r in hits)
            if hits:
                stamps = {"python" if r.get("written_by") == "python" else "model" for _rid, r in hits}
                out["located_by"]["both" if len(stamps) == 2 else stamps.pop()] += 1
                if claim is not None:
                    out["reason_checkable"] += 1
                    ok = any(reason_matches(claim, r) for _rid, r in hits)
                    entry["reason"] = "confirmed" if ok else "wrong"
                    out["reason_confirmed" if ok else "reason_wrong"] += 1
                else:
                    entry["reason"] = "key states no claim"
        out["located"] += int(entry["located"])
        out["attributed"] += int(entry["attributed"])
        out["entries"].append(entry)
    if arm == "B1":
        out["reason_confirmed"] = None
    flagged = {(str(u or "").lower(), str(r["rule_id"]).upper()): w
               for r in rows for u, w in _flagged_units(r)}
    planted_units = {str(p.get("unit") or "").lower() for p in planted}
    out["item_false_positives"] = sum(1 for r in rows if r["class"] == mapping.FLAG
                                      and str(r["rule_id"]).casefold() not in planted_rules)
    out["records_on_unplanted_units"] = sum(1 for (u, _r) in flagged
                                            if not any(_on_unit(p, u) for p in planted_units))
    out["distractor_hits"] = sum(1 for (u, _r) in flagged if any(_on_unit(c, u) for c in clean))
    return out


def _bases(rows) -> dict:
    count = lambda pred: sum(1 for r in rows if pred(r))  # noqa: E731
    return {"refusals": count(lambda r: r["basis"] == "refusal"),
            "abstain": count(lambda r: r["label"] == mapping.ABSTAIN and r["basis"] not in mapping.EXCLUDED_BASES),
            "b1_parse_failures": count(lambda r: r["basis"] == "b1_parse_failure"),
            "run_failure_items": count(lambda r: r["basis"] == "run_failure"),
            "item_calls_failed": count(lambda r: r["basis"] == "item_calls_failed"),
            "silent": count(lambda r: r["basis"] == "silent")}


_SUMMED = ("planted", "located", "attributed", "reason_checkable", "reason_wrong", "items", "gold_flag_items",
           "flag_items", "item_false_positives", "records_on_unplanted_units", "distractor_hits",
           "unattached_records", "planted_rule_not_an_item")


def _total(rows, arm) -> dict:
    out = {k: sum(int(r.get(k) or 0) for r in rows) for k in _SUMMED}
    out["bundles"] = len(rows)
    out["reason_confirmed"] = None if arm == "B1" else sum(int(r.get("reason_confirmed") or 0) for r in rows)
    out["location_recall"] = out["located"] / out["planted"] if out["planted"] else None
    out["reason_confirmed_recall"] = (None if out["reason_confirmed"] is None or not out["planted"]
                                      else out["reason_confirmed"] / out["planted"])
    for k in ("python", "model", "both"):
        out.setdefault("located_by", {})[k] = sum(r["located_by"][k] for r in rows)
    return out


def score_analysis(result, bundles_root, key_map=None) -> dict:
    """One analysis of one arm: per bundle and totals, by role, and the twin's false alarms."""
    view = mapping.scored_view(SPEC, result)
    arm = result["arm"]
    rows_by_bundle = {}
    for row in view["labels"]:
        rows_by_bundle.setdefault(row["bundle"], []).append(row)
    docs = {d["document_id"]: d for d in view.get("documents") or []}
    labelled = {r["bundle"] for r in result["labels"]}
    left_out = sorted(labelled - set(rows_by_bundle))
    per_bundle, skipped = [], []
    for name in sorted(rows_by_bundle):
        folder = Path(bundles_root) / name
        key = read_key(folder, key_map)
        if key.get("prior_records") is not None:
            skipped.append({"bundle": name, "why": NEGOTIATION_STYLE})
            continue
        rows = rows_by_bundle[name]
        row = score_bundle(folder, key, rows, arm)
        mine = [docs[d] for d in {r["document_id"] for r in rows} if d in docs]
        row["unattached_records"] = sum(int((d.get("unattached") or {}).get("count") or 0) for d in mine)
        row["run_failure"] = any(d.get("run_failure") for d in mine)
        row["semantic_incomplete"] = any(d.get("semantic_incomplete") for d in mine)
        row.update(_bases(rows))
        per_bundle.append(row)
    names = {r["bundle"]: r for r in per_bundle}
    for row in per_bundle:
        twin = row.get("twin_of")
        if not twin or row["role"] == "twin":
            row["twin_false_alarms"] = None
            continue
        other = names.get(twin)
        row["twin_false_alarms"] = (None if other is None else
                                    {"twin": twin, "flag_items": other["flag_items"],
                                     "flagged_unit_rule_pairs": other["records_on_unplanted_units"]})
    roles = {}
    for row in per_bundle:
        roles.setdefault(row["role"], []).append(row)
    totals = _total(per_bundle, arm)
    totals["documents_semantic_incomplete"] = sum(1 for r in per_bundle if r["semantic_incomplete"])
    totals["documents_complete"] = len(per_bundle) - totals["documents_semantic_incomplete"]
    totals["run_failure_documents"] = sum(1 for r in per_bundle if r["run_failure"])
    return {"arm": arm, "analysis": result.get("analysis", "primary"), "totals": totals,
            "by_role": {k: _total(v, arm) for k, v in sorted(roles.items())},
            "bundles": per_bundle, "not_scored": skipped,
            "left_out_excluded": left_out,
            "setup_failure": result.get("setup_failure"), "over_context": result.get("over_context"),
            "note": result.get("note")}


def score(labels, bundles_root, key_map=None) -> dict:
    out = {name: score_analysis(result, bundles_root, key_map) for name, result in labels.items()}
    for name, result in labels.items():
        if "s8_applies" in result:
            out[name]["s8_applies"] = result["s8_applies"]
    return out


# ---------------------------------------------------------------------------


def _map(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog=BENCHMARK, description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    it = sub.add_parser("items")
    it.add_argument("--root", required=True, help="a bundle, or a folder of bundles (one test)")
    it.add_argument("--out", help="default: items.json in --root")
    lab = sub.add_parser("label")
    lab.add_argument("--items", required=True)
    lab.add_argument("--bundles", required=True, help="the folder the items' bundles are in")
    lab.add_argument("--arm", required=True, choices=mapping.ARMS)
    lab.add_argument("--runs", help="one run (B2, B3, B4) or bare_model.py output (B1) folder per bundle")
    lab.add_argument("--run-map", help="a JSON object {bundle: run folder}, instead of --runs")
    lab.add_argument("--out", required=True)
    sc = sub.add_parser("score")
    sc.add_argument("--labels", required=True)
    sc.add_argument("--bundles", required=True)
    sc.add_argument("--key-map", help="a JSON object {bundle: answer key file}; default: the "
                                      "bundle's own answer_key.json")
    sc.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "items":
            print(json.dumps(write_items(args.root, args.out), indent=2))
            return 0
        if args.command == "label":
            labels = label(args.items, args.arm, args.bundles, args.runs, _map(args.run_map))
            bundle.write_json(Path(args.out), labels)
            print(json.dumps(labels["primary"]["counts"], indent=2))
            return 0
        if args.command == "score":
            labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
            result = score(labels, args.bundles, _map(args.key_map))
            bundle.write_json(Path(args.out), result)
            print(json.dumps({k: {m: v["totals"][m] for m in ("planted", "located", "reason_confirmed",
                                                               "item_false_positives", "distractor_hits")}
                              for k, v in result.items()}, indent=2))
            return 0
    except (Refused, mapping.Refused, ValueError, OSError) as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 4
    return 2


if __name__ == "__main__":
    sys.exit(main())
