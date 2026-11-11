"""The D-S92 gate set's draw and its SciTab class setting, as `docs/loop/stages/GATE_SET.md` writes them.

Run by role B on its own pool, after `common/gate_leakage.py check`, and before any label is read:

  draw-contradoc --leakage <check result> --input <release file> --assignment <split file> --out <ids file>
  draw-scitab --leakage <check result> --input <release file> --out <ids file>
  class-setting --counts <counts file>

The draw reads ids, group keys and the leakage result only: no text, no label (D-458). The class
setting reads the gold-class counts of the drawn SciTab claim set, counted by role B after the draw,
and nothing else; it never changes the draw.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _path in (str(ROOT / "benchmark" / "adapters"),):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from common import gate_leakage as leakage, ids  # noqa: E402

SALT_CLAIM = "20261109-D-S92:"
SALT_QUICK = "20261109-gate-quick:"
# D-454 and D-458 (D-S120 option A, replacing D-S118's maximum; D-458 replaces D-454 item 2 and D-457),
# written before role B and before any count: the v3 share is held back first, then the quick subset by
# its own salt, then the claim set by SALT_CLAIM, whole groups or papers taken until it reaches its size,
# the draw stopping at the first that does: ContraDoc 230 documents (one a group); SciTab 352 claims
# whatever the class setting (250 / 0.71, the paper's own not-enough-info share), counted as drawn. The
# draw never reads a label: the class setting is declared afterwards on the drawn claim set (D-380), and
# under 2-class about 250 are scored after removal, under 3-class all 352. The size is the floor: a pool
# that cannot reach it refuses the draw, never filled; no size, floor or threshold changes after any count.
CONTRADOC_QUICK_GROUPS = 40
CONTRADOC_CLAIM_GROUPS = 230
SCITAB_QUICK = {"tables": 8, "claims": 48}
SCITAB_CLAIM_CLAIMS = 352   # D-458; no table floor
# D-440: preregistration v3's SciTab sealed share is kept. Its size is the preregistration's (version 2,
# section 2: "SciTab 30 documents", a document being one table; sha256 0c1884fb... at aee36aaa), read
# there, not chosen here. It is held back from the whole holdout pool, by its own salt, whole papers until
# it holds that many tables, before the leakage check's result is read and before the quick subset.
SALT_V3_SEALED = "20261109-v3-sealed:"
V3_SCITAB_TABLES = 30
# The parts every gate check must have been fingerprinted with (GATE_SET.md section 9).
# Each part by name and by the paths its files must come from (GATE_SET.md section 9): a part's every
# fingerprinted file lies under one of them, and a part holds at least one file (gap 6: by path; the
# expected fingerprints digest pins every file's digest).
PART_PATHS = {
    "judge_mix_2e": ("external/s05/T2E/replay_prompts.json",),
    "judge_mix_1": ("external/s05/T/T_TRAIN/replay_prompts.json",),
    "judge": ("external/s05/T/", "external/s05/T2E/", "external/s05/P2A/"),
    "auditor": ("external/s05/AUD/",),
    "auditor_tuning": ("tuning/auditor_", "tuning/first_domain_agnostic_v1/", "tuning/second_domain_agnostic_v2/",
                       "tuning/second_tuning_eval_runtime_v2"),
    "producer": ("tuning/producer_v3/", "tuning/producer_v4/", "external/s05/P1/"),
    "verifier": ("external/s05/VER/",),
    "ontology": ("shimmer-scratch/ontology_pairs/",),
    "dev_cases": ("benchmark/dev_cases/",),
    "development": ("external/contradoc/dev/", "external/contradoc/dev_moved/", "external/scitab/dev/")
    + tuple("external/s05/%s/" % f for f in ("B2_suite", "C", "C1", "CASES", "D-S45", "G1", "J1", "L10", "L11", "L12", "L12b",
                                             "L12c", "L13", "L2", "L3e", "L4a", "L4b", "L5v", "L6", "L6m", "L6s", "L6s2", "L7",
                                             "L8", "L9a", "L9b", "R1", "R2", "R_constraint", "SAVINGS_PROOF", "labels", "miss_diag",
                                             "staging_records_d092", "suite_gen"))
    + ("external/s05/suite_staging.json",),
}


def under(label, prefix) -> bool:
    """Whether a fingerprinted file's label lies under `prefix`, matched as a path prefix starting at a
    path component of the label (never as a substring inside a component), archive members cut off."""
    path = label.replace("\\", "/").split("!")[0]
    starts = [0] + [i + 1 for i, ch in enumerate(path) if ch == "/"]
    return any(path.startswith(prefix, i) for i in starts)
REQUIRED_PARTS = tuple(PART_PATHS)
NEI = "not enough info"
NEI_MIN_CLAIMS = 30              # the 3-class setting needs this many not-enough-info claims
NEI_MIN_SHARE = 0.15             # and this share of the claim set (half the paper's 356 of 1,224)
SETTINGS = ("2-class", "3-class")


def order(keys, salt) -> list:
    return sorted(keys, key=lambda k: (hashlib.sha256((salt + k).encode("utf-8")).hexdigest(), k))


EXPECTED = ("input_sha256", "fingerprints_sha256", "exclude_ids_sha256", "cosine_step_sha256")


def _kept(leak, input_sha256=None, required_parts=REQUIRED_PARTS, expected=None) -> set:
    """The groups a leakage result kept, refused unless it is this tool's, applied the cosine rule,
    ran rule 4 on an exclusion file, ran on this input, was fingerprinted with every required part, and
    ran on exactly the files `expected` names by digest (audit gap 6: the fingerprints, the exclusion
    file, step 2's record and, for ContraDoc, the assignment)."""
    if leak.get("format") != leakage.FORMAT or leak.get("thresholds") != leakage.THRESHOLDS:
        raise ValueError("the leakage result was made with another format or other thresholds")
    if leak.get("cosine_rule") != "applied":
        raise ValueError("the leakage result did not apply the cosine rule: the draw is refused")
    provenance = leak.get("provenance") or {}
    if not provenance.get("exclude_ids_sha256"):
        raise ValueError("the leakage result names no exclusion file: rule 4 did not run, the draw is refused")
    if input_sha256 is not None and provenance.get("input_sha256") != input_sha256:
        raise ValueError("the leakage result was made on another input than this draw's")
    for key, value in sorted((expected or {}).items()):
        if provenance.get(key) != value:
            raise ValueError("the leakage result's %s is not the one this draw expects" % key)
    missing = sorted(set(required_parts) - set(leak.get("fingerprint_parts") or ()))
    if missing:
        raise ValueError("the fingerprints lack parts: " + ", ".join(missing))
    files = leak.get("fingerprint_files") or {}
    for part in sorted(required_parts):
        labels = [f["file"].replace("\\", "/").split("!")[0] for f in files.get(part, [])]
        if not labels or any(not any(under(label, q) for q in PART_PATHS.get(part, ())) for label in labels):
            raise ValueError("part %s was fingerprinted from other paths than section 9 names" % part)
    return set(leak["kept_group_keys"])


def draw_contradoc(candidates, leak, n_quick=CONTRADOC_QUICK_GROUPS, n_claim=CONTRADOC_CLAIM_GROUPS, input_sha256=None,
                   required_parts=REQUIRED_PARTS, expected=None) -> dict:
    """Whole groups the leakage check kept: the first `n_quick` in SALT_QUICK order are the quick
    subset; then whole groups in SALT_CLAIM order until the claim set holds `n_claim` documents, one a
    group (the lowest SHA-256 of SALT_CLAIM plus its id), so the draw stops at the group that reaches it
    (D-454 item 1, D-458). A pool that cannot reach `n_claim` is refused, never filled."""
    kept = _kept(leak, input_sha256, required_parts, expected)
    members = {}
    for c in candidates:
        if c["group"] in kept:
            members.setdefault(c["group"], []).append(c["id"])
    if set(members) != kept:
        raise ValueError("the leakage result keeps groups the input does not hold")
    quick = order(members, SALT_QUICK)[:n_quick]
    claim = order(set(members) - set(quick), SALT_CLAIM)[:n_claim]
    if len(quick) < n_quick or len(claim) < n_claim:
        raise ValueError("%d groups kept; the quick subset needs %d and the claim set %d" % (len(members), n_quick, n_claim))

    def pick(groups):
        return [{"group": g, "document": order(members[g], SALT_CLAIM)[0]} for g in groups]
    return {"benchmark": "contradoc", "salts": [SALT_CLAIM, SALT_QUICK], "groups_kept": len(members),
            "claim": pick(claim), "quick": pick(quick)}


def hold_back_v3(candidates, tables=V3_SCITAB_TABLES, demonstration=()) -> list:
    """The papers held back for preregistration v3's SciTab sealed evaluation (D-440): every holdout
    paper in SALT_V3_SEALED order, taken whole until they hold `tables` usable tables, a demonstration
    table (the paper's in-context examples, role B's list) not counted. Ids only; leakage not consulted,
    so the share does not depend on what the loop's parts hold."""
    demonstration = {ids.key_string(t) for t in demonstration}
    papers = {}
    for c in candidates:
        papers.setdefault(c["group"], set())
        if c["table"] not in demonstration:
            papers[c["group"]].add(c["table"])
    held, count = [], 0
    for p in order(papers, SALT_V3_SEALED):
        if count >= tables:
            break
        held.append(p)
        count += len(papers[p])
    if count < tables:
        raise ValueError("the pool holds %d usable tables; preregistration v3 keeps %d" % (count, tables))
    return held


def draw_scitab(candidates, leak, quick_min=SCITAB_QUICK, n_claims=None, input_sha256=None,
                required_parts=REQUIRED_PARTS, v3_tables=V3_SCITAB_TABLES, expected=None, demonstration=()) -> dict:
    """Whole papers the leakage check kept, every claim of every table: v3's share held back first;
    papers in SALT_QUICK order until the quick subset holds both minima; then papers in SALT_CLAIM order
    until the claim set holds `n_claims` claims as drawn (D-458: 352 whatever the class setting), the
    draw stopping at the first paper that reaches it. It reads ids only, never a label. A pool that
    cannot reach the size is refused, never filled."""
    n_claims = SCITAB_CLAIM_CLAIMS if n_claims is None else n_claims
    kept = _kept(leak, input_sha256, required_parts, expected)
    held = hold_back_v3(candidates, v3_tables, demonstration) if v3_tables else []
    papers = {}
    for c in candidates:
        if c["group"] in kept:
            papers.setdefault(c["group"], {}).setdefault(c["table"], []).append(c["id"])
    if set(papers) != kept:
        raise ValueError("the leakage result keeps papers the input does not hold")
    papers = {p: v for p, v in papers.items() if p not in set(held)}

    def size(chosen):
        return sum(len(papers[p]) for p in chosen), sum(len(v) for p in chosen for v in papers[p].values())

    quick = []
    for p in order(papers, SALT_QUICK):
        tables, claims = size(quick)
        if tables >= quick_min["tables"] and claims >= quick_min["claims"]:
            break
        quick.append(p)
    claim = []
    for p in order(set(papers) - set(quick), SALT_CLAIM):
        if size(claim)[1] >= n_claims:
            break
        claim.append(p)
    qt, qc = size(quick)
    ct, cc = size(claim)
    if qt < quick_min["tables"] or qc < quick_min["claims"] or cc < n_claims:
        raise ValueError("the kept papers give a quick subset of %d tables and %d claims and a claim set of %d and %d; "
                         "%s and %d claims are needed" % (qt, qc, ct, cc, quick_min, n_claims))

    def listing(chosen):
        return [{"paper": p, "table": t, "claims": sorted(papers[p][t])} for p in chosen for t in sorted(papers[p])]
    return {"benchmark": "scitab", "salts": [SALT_V3_SEALED, SALT_CLAIM, SALT_QUICK], "papers_kept": len(papers),
            "v3_sealed_papers": sorted(held), "v3_sealed_tables": v3_tables,
            "claims_drawn": cc, "claims_needed": n_claims,
            "v3_papers_the_check_flagged": sorted(set(held) - kept),
            "claim": listing(claim), "quick": listing(quick)}


def class_setting(counts) -> dict:
    """The claim set's declared setting from its gold-class counts (D-380): 3-class when it holds
    at least NEI_MIN_CLAIMS not-enough-info claims and at least NEI_MIN_SHARE of its claims,
    otherwise 2-class, its not-enough-info claims then left out of both sets by id."""
    known = {"supports", "refutes", NEI}
    if set(counts) - known or not all(isinstance(v, int) and v >= 0 for v in counts.values()):
        raise ValueError("counts are {supports, refutes, not enough info: a whole number}")
    total = sum(counts.values())
    nei = counts.get(NEI, 0)
    three = nei >= NEI_MIN_CLAIMS and total and nei / total >= NEI_MIN_SHARE
    return {"setting": "3-class" if three else "2-class", "counts": dict(sorted(counts.items())), "claims": total,
            "rule": "3-class when not enough info >= %d claims and >= %.2f of the claim set" % (NEI_MIN_CLAIMS, NEI_MIN_SHARE),
            "not_enough_info_left_out": 0 if three else nei}


def exclude_ids(contradoc_assignments, fresh_ids, scitab_development) -> dict:
    """The leakage check's rule 4 list, ids only: every ContraDoc development document and group key
    (each assignment file `{assignments: {id: {group, side}}}`, the development split and the moved
    one), every fresh-set id, and every SciTab development paper and table id (the adapter's own
    fields; no claim, no label read into the output)."""
    from contradoc import adapter as cd
    from scitab import adapter as st
    keys, counts = set(), {}
    for path in contradoc_assignments:
        # sides are not checked here: a moved group keeps its holdout hash with a development side
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if str(data.get("benchmark", "")).lower() != cd.BENCHMARK:
            raise ValueError("not a ContraDoc assignment file: " + Path(path).name)
        if isinstance(data.get("assignments"), dict):
            rows = {ids.key_string(d): ids.key_string(r["group"]) for d, r in data["assignments"].items()}
        elif isinstance(data.get("documents"), list):
            rows = {ids.key_string(r["source_document_id"]): ids.key_string(r["split_key"]) for r in data["documents"]}
        else:
            raise ValueError("an assignment file holds `assignments` or `documents`: " + Path(path).name)
        keys |= set(rows) | set(rows.values())
        counts[Path(path).name] = len(rows)
    leakage.guard(fresh_ids, fresh_ids=True)
    if _digest(fresh_ids) != leakage.FRESH_IDS_SHA256:
        raise ValueError("the fresh ids file is not the pinned one (%s...): refused wherever it is" % leakage.FRESH_IDS_SHA256[:8])
    fresh = json.loads(Path(fresh_ids).read_text(encoding="utf-8"))["documents"]
    keys |= {ids.key_string(d) for d in fresh}
    records = st.read_source(scitab_development)
    papers = {ids.key_string(r[st.PAPER_ID_FIELD]) for r in records}
    tables = {ids.key_string(r[st.TABLE_ID_FIELD]) for r in records}
    keys |= papers | tables
    counts.update(fresh=len(fresh), scitab_papers=len(papers), scitab_tables=len(tables))
    return {"group_keys": sorted(keys), "counts": counts,
            "inputs": {Path(p).name: _digest(p) for p in [*contradoc_assignments, fresh_ids, scitab_development]},
            "fresh_ids_provenance": {"path": leakage.FRESH_IDS_FILE, "sha256": _digest(fresh_ids),
                                     "read": "ids only (its `documents` list), admitted by digest (D-442)"}}


def freeze(contradoc_ids, scitab_ids, setting) -> dict:
    """The claim set and the quick subset as two separate files' contents (D-444), ids only, from the
    draw's ids files: their SHA-256 are gate_score's CLAIM_SET_SHA256 and QUICK_SET_SHA256. `setting` is
    SciTab's class-setting result with the not-enough-info item ids role B listed (`not_enough_info_ids`,
    source claim ids): under 2-class those claims leave both sets, and a table left with none leaves too;
    under 3-class the list must be empty. Each file carries the opaque item and document ids the scorer
    gives, so a read can check its arms against it."""
    from common import ids as common_ids
    declared = setting.get("setting")
    nei = {common_ids.key_string(i) for i in setting.get("not_enough_info_ids") or ()}
    if declared not in SETTINGS:
        raise ValueError("the freeze needs SciTab's declared class setting")
    if declared == "3-class" and nei:
        raise ValueError("a 3-class set keeps its not-enough-info claims: no ids are left out")
    claim_ids = {common_ids.key_string(c) for r in scitab_ids["claim"] for c in r["claims"]}
    quick_ids = {common_ids.key_string(c) for r in scitab_ids["quick"] for c in r["claims"]}
    if nei - claim_ids - quick_ids:
        raise ValueError("not-enough-info ids that are in neither set: " + ", ".join(sorted(nei - claim_ids - quick_ids)[:5]))
    # class_setting is declared on the drawn claim set (D-380, D-458): its count is the claim set's;
    # the ids list both sets (request step 6)
    if declared == "2-class" and len(nei & claim_ids) != setting.get("not_enough_info_left_out", 0):
        raise ValueError("the claim set's not-enough-info ids are not as many as the class-setting result counted")
    out = {}
    for name in ("claim", "quick"):
        contradoc = [{"group": r["group"], "document": r["document"],
                      "item_id": common_ids.opaque_item_id("contradoc", r["document"]),
                      "document_id": common_ids.opaque_document_id("contradoc", r["document"])} for r in contradoc_ids[name]]
        scitab = []
        for r in scitab_ids[name]:
            claims = [c for c in r["claims"] if common_ids.key_string(c) not in nei]
            if claims:
                scitab.append({"paper": r["paper"], "table": r["table"], "claims": claims,
                               "document_id": common_ids.opaque_document_id("scitab", r["table"]),
                               "item_ids": [common_ids.opaque_item_id("scitab", c) for c in claims]})
        out[name] = {"schema": "shimmer-gate-%s-set-v2" % name, "set": name, "scitab_class_setting": declared,
                     "not_enough_info_left_out": sorted(nei & {common_ids.key_string(c) for r in scitab_ids[name] for c in r["claims"]}),
                     "contradoc": contradoc, "scitab": scitab}
    if {r["group"] for r in out["claim"]["contradoc"]} & {r["group"] for r in out["quick"]["contradoc"]}:
        raise ValueError("the claim set and the quick subset share a document group")
    if {r["paper"] for r in out["claim"]["scitab"]} & {r["paper"] for r in out["quick"]["scitab"]}:
        raise ValueError("the claim set and the quick subset share a paper")
    for name in ("claim", "quick"):   # D-458: the scored count is reported as it falls, with no floor after removal
        out[name]["scored_claims"] = sum(len(r["claims"]) for r in out[name]["scitab"])
        out[name]["drawn_claims"] = sum(len(r["claims"]) for r in scitab_ids[name])
    return out


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("draw-contradoc", "draw-scitab"):
        d = sub.add_parser(name)
        d.add_argument("--leakage", required=True)
        d.add_argument("--input", required=True)
        d.add_argument("--out", required=True)
        for flag in ("--fingerprints-sha256", "--exclude-ids-sha256", "--cosine-step-sha256"):
            d.add_argument(flag, required=True, help="the digest the leakage result must have run on")
        if name == "draw-contradoc":
            d.add_argument("--assignment", required=True)
        else:
            d.add_argument("--demonstration-tables", required=True, help="role B's in-context example table ids")

    k = sub.add_parser("class-setting")
    k.add_argument("--counts", required=True)
    z = sub.add_parser("freeze")
    z.add_argument("--contradoc-ids", required=True)
    z.add_argument("--scitab-ids", required=True)
    z.add_argument("--out-dir", required=True)
    z.add_argument("--class-setting", required=True, help="the class-setting result with role B's not_enough_info_ids")
    x = sub.add_parser("exclude-ids")
    x.add_argument("--contradoc-assignment", action="append", required=True)
    x.add_argument("--fresh-ids", required=True)
    x.add_argument("--scitab-development", required=True)
    x.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        leakage.guard_args(args)
        if args.command == "freeze":
            sets = freeze(_json(args.contradoc_ids), _json(args.scitab_ids), _json(args.class_setting))
            digests = {}
            for name, value in sets.items():
                target = Path(args.out_dir) / ("%s_set_ids.json" % name)
                target.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
                digests[name] = _digest(target)
            print(json.dumps(digests, indent=2))
            return 0
        if args.command == "exclude-ids":
            value = exclude_ids(args.contradoc_assignment, args.fresh_ids, args.scitab_development)
            Path(args.out).write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
            print(json.dumps(value["counts"]))
            return 0
        if args.command == "class-setting":
            print(json.dumps(class_setting(_json(args.counts)), indent=2))
            return 0
        leak = _json(args.leakage)
        expected = {"fingerprints_sha256": args.fingerprints_sha256, "exclude_ids_sha256": args.exclude_ids_sha256,
                    "cosine_step_sha256": args.cosine_step_sha256}
        if args.command == "draw-contradoc":
            expected["assignment_sha256"] = _digest(args.assignment)
            from contradoc import adapter as cd
            cands = leakage.candidates_contradoc(cd.read_source(args.input), args.assignment, ids.HOLDOUT)
            result = draw_contradoc(cands, leak, input_sha256=_digest(args.input), expected=expected)
            result["assignment_sha256"] = _digest(args.assignment)
        else:
            from scitab import adapter as st
            cands = leakage.candidates_scitab(st.read_source(args.input), ids.HOLDOUT)
            demonstration = leakage._ids_file(args.demonstration_tables)
            result = draw_scitab(cands, leak, input_sha256=_digest(args.input), expected=expected, demonstration=demonstration)
            result["demonstration_tables_sha256"] = _digest(args.demonstration_tables)
        result.update(input_sha256=_digest(args.input), leakage_sha256=_digest(args.leakage))
        Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"claim": len(result["claim"]), "quick": len(result["quick"])}))
        return 0
    except ValueError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
