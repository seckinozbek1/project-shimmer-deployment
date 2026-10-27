"""Bundles, keys, the clean twin, the four probes, self-validation and writing.

A family returns a spec (see families' build()). This module turns it into six
bundles in memory (the test, its clean twin, and the four probes of section 11),
validates all of them with the package's own audit (audit.py), and only then can
anything be written. A spec that fails validation writes nothing.

Every bundle is a mapping {relative path: text}. The key of each bundle says what it
is: a probe carries a top-level "probe" field (section 11); the twin has no planted
flaw; the test names its twin in "twin_of" and the twin names the test.
"""
import difflib
import json
import os
import random
import re

from . import audit as au
from . import family_declaration as fd
from . import family_ledger as fl
from . import family_provisions as fp
from . import family_result_sheet as fr
from . import family_statement as fs
from . import family_terms as ft
from . import ground_truth as gt
from . import model as md
from . import multi_round_case as mc
from . import textrules as tr

PROBES = ("reworded_labels", "reordered_sections", "term_only_in_later_version",
          "value_in_different_format")
NEUTRAL_NAME = re.compile(r"^[A-Za-z0-9_-]+\.(md|json)$")
NEUTRAL_FOLDER = re.compile(r"^[A-Za-z0-9_-]+$")
KEY_FILE = "answer_key.json"
# The required top-level fields of each key form (INPUT_FORMAT section 9); a bundle that
# is also a multi-round case adds `multi_round`.
KEY_FORMS = {"single": ("document", "task_given_to_the_pipeline", "planted", "clean"),
             "negotiation": ("document", "task_given_to_the_pipeline", "prior_records",
                             "band_irregularities")}
MANIFEST = "context/_review_targets.json"
_LETTERS = "bcdfghjkmnpqrstvwxz"


class ValidationError(Exception):
    pass


def _tag(rng, n=4):
    return "".join(rng.choice(_LETTERS) for _ in range(n))


def _dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=True) + "\n"


def _ids(doc, order):
    """{original unit index: unit id} for a doc whose units are `order` (original indices)."""
    return {orig: tr.unit_id(pos + 1, doc.units[pos].heading) for pos, orig in enumerate(order)}


def _rename_label(doc, old, new):
    for u in doc.units:
        for b in u.blocks:
            if b[0] == "lines":
                for pair in b[1]:
                    if pair[0] == old:
                        pair[0] = new
            elif b[0] == "table":
                for i, h in enumerate(b[1]):
                    lab, meas = au._split_header(h)
                    if lab == old:
                        b[1][i] = new + (" (%s)" % meas if meas else "")


def _manifest(target, grounding, prior):
    return {"targets": [target], "grounding": sorted(grounding), "prior": [prior] if prior else [],
            "source": "operator", "resolved_at": ""}


def _planted_entries(spec, ids):
    out = []
    for p in spec["planted"]:
        e = {"unit": ids[p["unit"]], "rule": p["rule"], "relation": p["relation"],
             "kind": p["kind"],
             "claim": {"relation": p["relation"], "field_label": p["field_label"],
                       "value_a": tr.r6(p["value_a"]), "value_b": tr.r6(p["value_b"])}}
        for k in ("unit_a", "unit_b"):
            if k in p:
                e["claim"][k] = p[k]
        for k, v in sorted(p.get("links", {}).items()):
            e[k] = ids[v]
        for k, v in sorted(p.get("extra", {}).items()):
            e[k] = v
        if "long_range" in spec.get("key_extra", {}) and "related_unit" in e:
            e["distance"] = unit_distance(e["unit"], e["related_unit"])
        out.append(e)
    return out


def unit_distance(a, b):
    """How many units apart two unit ids are (their positions, section 2)."""
    return abs(int(a[1:3]) - int(b[1:3]))


RECORD_RELATIONS = ("unchanged_from_prior", "changed_from_prior", "moved_toward", "moved_away",
                    "absent_since_prior")


def prior_records_from(plan):
    """The change records a correct reviewer writes, from the family's own plan: every
    label both versions state, and every withdrawn term. A renamed term has no row: its
    expected_refusals row says what satisfies it."""
    rows = [{"field_label": v["field_label"], "relation": v["expect"], "value_a": v["value_a"],
             "value_b": v["value_b"], "unit": v["unit"]}
            for v in plan if v["expect"] in RECORD_RELATIONS]
    return sorted(rows, key=lambda r: (r["field_label"], r["relation"]))


def expected_refusals_from(rename_rows):
    """One row per renamed term (INPUT_FORMAT section 9): the earlier label, the unit its
    refusal sits on (the target unit with the earlier statement's heading), the later
    label a matched rename names, the figures a matched rename compares (`value_a` the
    later, `value_b` the earlier) and their measure (`unit`), and the typed kind of the
    expected refusal (null: Python is expected to refuse nothing, and only a matched
    rename satisfies the row)."""
    return [{"field_label": r["field_label"], "later_field_label": r["later_field_label"],
             "unit_id": r["prior_unit_id"], "reason_kind": r["refusal_kind"],
             "value_a": r["value_after"], "value_b": r["value_before"], "unit": r["unit"],
             "kind": r["kind"]}
            for r in rename_rows if r.get("expect") == "not_withdrawn"]


EARLIER_ROUND_KIND = "breach_in_earlier_round"


def multi_round_key(spec, rounds, alias=None):
    """The multi-round form of the key (INPUT_FORMAT section 9, "Multi-round keys"), from
    the family's own terms: in every round, every term outside the band of the mandate
    rule that governs it is a planted entry scoped by `round_id` and `document_id`, on
    that document's unit id. The rule governs the term's issue, so an earlier round that
    writes a renamed term under its earlier label is governed by the same rule. `rounds`
    is [(round_id, document_id, Doc, is_target)]; `alias` maps a reworded label to the
    label it rewords. The clean entry of each round is the unit holding the term on its
    bound, unless a breach sits there in that round."""
    alias = alias or {}
    kinds = {b["field_label"]: b["kind"] for b in spec["bands"]}
    planted, clean = [], []
    for rid, did, doc, last in rounds:
        hit, clean_here = set(), None
        for pos, u in enumerate(doc.units):
            uid = tr.unit_id(pos + 1, u.heading)
            for b in u.blocks:
                if b[0] != "lines":
                    continue
                for label, value in b[1]:
                    orig = alias.get(label, label)
                    if orig == spec["clean_label"]:
                        clean_here = uid
                    term = spec["term_bands"].get(orig)
                    k = tr.classify_value(value)
                    if term is None or k[0] != "figure" or term["lo"] <= k[1] <= term["hi"]:
                        continue
                    above = k[1] > term["hi"]
                    rel = "above_band" if above else "below_band"
                    hit.add(uid)
                    planted.append({
                        "round_id": rid, "document_id": did, "unit": uid, "rule": term["rule"],
                        "relation": rel,
                        "kind": kinds[tr.norm(orig)] if last else EARLIER_ROUND_KIND,
                        "claim": {"relation": rel, "field_label": tr.norm(label), "value_a": tr.r6(k[1]),
                                  "value_b": tr.r6(term["hi"] if above else term["lo"])},
                        "issue_id": term["issue"]})
        if clean_here is not None and clean_here not in hit:
            clean.append({"round_id": rid, "document_id": did, "unit": clean_here})
    return {"planted": planted, "clean": clean}


def _band_rows(spec, ids, which="bands"):
    out = []
    for b in spec[which]:
        out.append({"field_label": b["field_label"], "relation": b["relation"],
                    "value_a": tr.r6(b["value_a"]), "rule": b["rule"],
                    "unit_id": ids[b["unit"]], "value_b": tr.r6(b["value_b"]),
                    "kind": b["kind"]})
    return out


def build_bundles(spec):
    """Return {folder: {relpath: text}} for the test, its twin and the four probes."""
    rng = random.Random("names:%s:%s" % (spec["family"], spec["seed"]))
    test_id = "%s_s%s" % (spec["family"], spec["seed"])
    folders = {}
    used = set()
    for role in ("base", "twin") + PROBES:
        while True:
            name = "%s_%s" % (test_id, _tag(rng))
            if name not in used:
                used.add(name)
                folders[role] = name
                break
    stem = spec["doc_stem"]
    docs = {}
    for role in ("base", "twin") + PROBES:
        while True:
            name = "%s_%s.md" % (stem, _tag(rng, 3) + str(rng.randint(1, 9)))
            if name not in docs.values():
                docs[role] = name
                break
    ref_names = ["%s_%s.md" % (r[0], _tag(rng, 3)) for r in spec["references"]]
    conv_name = "%s_%s.md" % (spec["conv_stem"], _tag(rng, 3))
    prior_name = "%s_%s.md" % (stem, _tag(rng, 3) + "0")
    # A three-round case's earliest version: drawn last, so a two-round test's names
    # are unchanged.
    earliest_doc = spec.get("earliest")
    earliest_name = None
    while earliest_doc is not None:
        earliest_name = "%s_%s.md" % (stem, _tag(rng, 3) + "0")
        if earliest_name != prior_name and earliest_name not in docs.values():
            break
    ref_texts = {n: md.render_reference(r[1], r[2]) for n, r in zip(ref_names, spec["references"])}
    conv_text = md.render_conventions(spec["conventions"])
    negotiation = spec["mode"] == "negotiation"
    n_units = len(spec["doc"].units)
    identity = list(range(n_units))
    gen = {"family": spec["family"], "family_name": spec["family_name"], "seed": spec["seed"],
           "format": tr.FORMAT_VERSION,
           "note": "generated by benchmark/generators; exposed by construction, development and regression only"}
    if spec.get("attempt"):
        # A retried seed (generators.generate): the derived sub-seed that was kept.
        gen["attempt"] = spec["attempt"]

    def bundle(role, doc, order, prior_doc=None, key_extra=None, prior_for_key=None,
               early_doc=None, aliases=None, term_alias=None):
        files = {}
        target = docs[role]
        files["context/" + target] = md.render_doc(doc)
        for n, t in ref_texts.items():
            files["context/" + n] = t
        grounding = list(ref_texts)
        if early_doc is not None:
            files["context/" + earliest_name] = md.render_doc(early_doc)
            grounding.append(earliest_name)
        if prior_doc is not None:
            files["context/" + prior_name] = md.render_doc(prior_doc)
            grounding.append(prior_name)
        files[MANIFEST] = _dump(_manifest(target, grounding, prior_name if prior_doc is not None else None))
        files["conventions/" + conv_name] = conv_text
        ids = _ids(doc, order)
        # One task field name for every key form (INPUT_FORMAT section 9).
        key = {"document": target, "task_given_to_the_pipeline": spec["task"]}
        if role == "base":
            key["twin_of"] = folders["twin"]
        elif role == "twin":
            key["twin_of"] = folders["base"]
        if negotiation:
            plan = spec[{"twin": "twin_version_changes",
                         "term_only_in_later_version": "term_version_changes"}.get(role, "version_changes")]
            key["prior_records"] = prior_records_from(plan)
            key["band_irregularities"] = [] if role == "twin" else _band_rows(spec, ids)
            key["clean"] = [ids[i] for i in spec["clean"]]
            key["version_changes"] = plan
            if spec.get("rename_probes") is not None:
                key["rename_probes"] = [
                    dict(r, unit_id=ids[r["unit_id"]] if r["unit_id"] is not None else None,
                         prior_unit_id=ids[r["prior_unit_id"]] if r["prior_unit_id"] is not None else None,
                         prior_order=[ids[i] for i in r["prior_order"]])
                    for r in spec["twin_rename_probes" if role == "twin" else "rename_probes"]]
                key["expected_refusals"] = expected_refusals_from(key["rename_probes"])
        else:
            key["planted"] = [] if role == "twin" else _planted_entries(spec, ids)
            key["clean"] = [ids[i] for i in spec["clean"]]
            key["ground_truth_checks"] = spec.get("ground_truth_checks", [])
        if role in PROBES:
            key["probe"] = role
            key["probe_change"] = key_extra
        for k, v in sorted(spec.get("key_extra", {}).items()):
            key[k] = v
        key["generator"] = gen
        if spec.get("rounds") and prior_doc is not None:
            # The declared multi-round case: rounds in version order, the live case
            # manifest beside the key, and what the per-round review should reuse.
            round_names = ([earliest_name] if early_doc is not None else []) + [prior_name, target]
            round_docs = [(n, files["context/" + n]) for n in round_names]
            versions = (["earliest"] if early_doc is not None else []) + ["prior", "target"]
            key["case_manifest"] = mc.FILE
            key["rounds"] = [{"round_id": "r%d" % i, "sequence": i, "version": v}
                             for i, v in enumerate(versions, start=1)]
            if early_doc is not None:
                key["round_changes"] = [
                    {"field_label": c["field_label"], "round_id": "r2", "from_round": "r1",
                     "unit_id": tr.unit_id(c["prior_position"] + 1, prior_doc.units[c["prior_position"]].heading),
                     "value_before": c["value_before"], "value_after": c["value_after"], "unit": c["unit"]}
                    for c in spec["round_changes"]]
            key["round_reuse"] = mc.round_reuse([t for _, t in round_docs], au.parse_document)
            models = ([early_doc] if early_doc is not None else []) + [prior_doc, doc]
            key["multi_round"] = multi_round_key(
                spec, [("r%d" % i, n.rsplit(".", 1)[0], m, i == len(models))
                       for i, (n, m) in enumerate(zip(round_names, models), start=1)], term_alias)
            alias = dict(aliases or {})
            files[mc.FILE] = mc.dump(mc.build(
                folders[role], round_docs,
                lambda label: alias.get(label) or spec["issues"].get(label) or "issue-" + tr.slug(label)))
        files[KEY_FILE] = _dump(key)
        return files

    out = {}
    base_prior = spec.get("prior")
    ed = earliest_doc
    out[folders["base"]] = bundle("base", spec["doc"], identity, base_prior, early_doc=ed)
    out[folders["twin"]] = bundle("twin", spec["twin"], identity, base_prior, early_doc=ed)
    pr = spec["probes"]
    # 1. reworded labels (in every version; the case keeps the term's issue)
    d1 = spec["doc"].clone()
    _rename_label(d1, pr["reword"]["old"], pr["reword"]["new"])
    p1 = e1 = None
    if base_prior is not None:
        p1 = base_prior.clone()
        _rename_label(p1, pr["reword"]["old"], pr["reword"]["new"])
    if ed is not None:
        e1 = ed.clone()
        _rename_label(e1, pr["reword"]["old"], pr["reword"]["new"])
    aliases = None
    if spec.get("issues"):
        aliases = {pr["reword"]["new"]: spec["issues"][pr["reword"]["old"]]}
    b1 = bundle("reworded_labels", d1, identity, p1,
                {"label_from": pr["reword"]["old"], "label_to": pr["reword"]["new"]},
                early_doc=e1, aliases=aliases, term_alias={pr["reword"]["new"]: pr["reword"]["old"]})
    k1 = json.loads(b1[KEY_FILE])
    old_n, new_n = tr.norm(pr["reword"]["old"]), tr.norm(pr["reword"]["new"])
    if negotiation:
        for row in k1["band_irregularities"]:
            if row["field_label"] == old_n:
                row["field_label"] = new_n
        base_rows = json.loads(out[folders["base"]][KEY_FILE])["prior_records"]
        k1["prior_records"] = [dict(r, field_label=(new_n if r["field_label"] == old_n else r["field_label"]))
                               for r in base_rows]
    else:
        for e in k1["planted"]:
            e["claim"]["field_label"] = gt.reword_field(e["claim"]["field_label"], old_n, new_n)
        k1["ground_truth_checks"] = gt.reword_checks(k1["ground_truth_checks"], old_n, new_n)
    b1[KEY_FILE] = _dump(k1)
    out[folders["reworded_labels"]] = b1
    # 2. reordered sections
    order = list(pr["reorder"])
    d2 = md.Doc(spec["doc"].title, spec["doc"].preamble, [spec["doc"].units[i].clone() for i in order])
    out[folders["reordered_sections"]] = bundle(
        "reordered_sections", d2, order, base_prior,
        {"moved_from": [tr.unit_id(i + 1, spec["doc"].units[i].heading) for i in order]},
        early_doc=ed)
    # 3. a term only in the later version
    t = pr["term"]
    if negotiation:
        # The term is dropped from every earlier version; the target is unchanged, so
        # the keyed breach on it now sits on a term only in the later version.
        heading = spec["doc"].units[t["unit"]].heading
        p3, e3 = base_prior.clone(), (ed.clone() if ed is not None else None)
        for version in [p3] + ([e3] if e3 is not None else []):
            [u for u in version.units if u.heading == heading][0].remove_line(t["label"])
        out[folders["term_only_in_later_version"]] = bundle(
            "term_only_in_later_version", spec["doc"], identity, p3,
            {"term": t["label"], "unit": tr.unit_id(t["unit"] + 1, heading)},
            early_doc=e3)
    else:
        prior3 = spec["doc"].clone()
        prior3.units[t["unit"]].remove_line(t["label"])
        out[folders["term_only_in_later_version"]] = bundle(
            "term_only_in_later_version", spec["doc"], identity, prior3,
            {"term": t["label"], "unit": tr.unit_id(t["unit"] + 1, spec["doc"].units[t["unit"]].heading)})
    # 4. a value in a different format
    f = pr["reformat"]
    d4 = spec["doc"].clone()
    u4 = d4.units[f["unit"]]
    if "label" in f:
        u4.set_line(f["label"], f["text"])
    else:
        bi, ri, ci = f["cell"]
        u4.blocks[bi][2][ri][ci] = f["text"]
    out[folders["value_in_different_format"]] = bundle(
        "value_in_different_format", d4, identity, base_prior,
        {"unit": tr.unit_id(f["unit"] + 1, u4.heading), "written_as": f["text"]}, early_doc=ed)
    return out


# ----------------------------------------------------------------------------------
# validation

def _key(files):
    return json.loads(files[KEY_FILE])


def _target(files):
    man = json.loads(files[MANIFEST])
    return man["targets"][0], man


def _audit_bundle(files, enforce=True):
    target, man = _target(files)
    convs = sorted(n for n in files if n.startswith("conventions/"))
    conv_text = "\n".join(files[n] for n in convs) if len(convs) == 1 else None
    if conv_text is None:
        raise ValidationError("exactly one conventions file expected")
    grounding = {n[len("context/"):]: t for n, t in files.items()
                 if n.startswith("context/") and n.endswith(".md") and n != "context/" + target}
    prior = man["prior"][0] if man["prior"] else None
    return au.audit(files["context/" + target], target, files[convs[0]], convs[0], grounding,
                    prior, enforce_section5=enforce, earlier_names=_earlier_versions(files))


def _earlier_versions(files):
    """The grounding files a case manifest declares as rounds, other than the target and
    the declared prior (the earliest version of a three-round case)."""
    if mc.FILE not in files:
        return ()
    try:
        case = json.loads(files[mc.FILE])
        target, man = _target(files)
        ids = {d for r in case.get("rounds", []) for d in r.get("document_ids", [])}
    except (ValueError, AttributeError, TypeError):
        return ()
    names = [p[len("context/"):] for p in files if p.startswith("context/")]
    return tuple(n for n in names if n.rsplit(".", 1)[0] in ids
                 and n != target and n not in man["prior"])


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


# What each family's keyed kinds require their rule's text to state (the families'
# RULE_STATEMENTS), by the family code a key's `generator.family` carries.
RULE_STATEMENTS = {"f1": fr.RULE_STATEMENTS, "f2": fd.RULE_STATEMENTS, "f3": fs.RULE_STATEMENTS,
                   "f4": ft.RULE_STATEMENTS, "f5": fp.RULE_STATEMENTS, "f5lr": fp.RULE_STATEMENTS,
                   "f6": fl.RULE_STATEMENTS}


def rule_texts(conv_text):
    """{operator id: rule text} of a rendered conventions file, read with plain string
    handling (no audit): each `## ` heading's first word is the id, and the paragraphs
    under it, lowercased with runs of spaces joined, are its text."""
    out = {}
    for block in conv_text.split("\n## ")[1:]:
        heading, _, body = block.partition("\n")
        out[heading.split(" ", 1)[0]] = " ".join(body.lower().split())
    return out


def check_rule_statements(name, files, errs):
    """Every keyed entry's rule, read from the bundle's own conventions file, still
    states what is keyed: each phrase its family declares for the entry's kind is in
    that rule's text (so a rule reworded back to something the planted flaw does not
    break, as a duty "on the summed line values" would be, is caught). A keyed kind with
    no declared statement is refused too. Single-version entries, negotiation-style band
    rows and multi-round entries alike."""
    key = _key(files)
    statements = RULE_STATEMENTS.get(key.get("generator", {}).get("family"))
    if statements is None:
        errs.append("%s: no rule statements for this family" % name)
        return
    convs = [p for p in files if p.startswith("conventions/")]
    texts = rule_texts(files[convs[0]]) if len(convs) == 1 else {}
    entries = list(key.get("planted", [])) + list(key.get("band_irregularities", []))
    entries += list((key.get("multi_round") or {}).get("planted", []))
    for e in entries:
        want = statements.get(e.get("kind"))
        text = texts.get(e.get("rule"))
        if want is None:
            errs.append("%s: keyed kind %s declares no rule statement" % (name, e.get("kind")))
        elif text is None:
            errs.append("%s: keyed rule %s is not in the conventions" % (name, e.get("rule")))
        else:
            missing = [w for w in want if " ".join(w.lower().split()) not in text]
            if missing:
                errs.append("%s: rule %s no longer states what %s keys: %s"
                            % (name, e.get("rule"), e.get("kind"), missing))


def check_structure(name, files, errs):
    if not NEUTRAL_FOLDER.match(name):
        errs.append("%s: folder name is not neutral" % name)
    for path in files:
        parts = path.split("/")
        if path in (KEY_FILE, mc.FILE):
            continue
        if len(parts) != 2 or parts[0] not in ("context", "conventions"):
            errs.append("%s: unexpected file %s" % (name, path))
            continue
        if not NEUTRAL_NAME.match(parts[1]):
            errs.append("%s: file name %s is not neutral" % (name, path))
        if parts[0] == "context" and parts[1].endswith(".json") and parts[1] != "_review_targets.json":
            errs.append("%s: a json file in context/ is read as a document" % name)
        if parts[0] == "conventions" and not parts[1].endswith(".md"):
            errs.append("%s: a non-Markdown conventions file" % name)
    if KEY_FILE not in files or MANIFEST not in files:
        errs.append("%s: missing key or manifest" % name)
        return
    try:
        man = json.loads(files[MANIFEST])
    except ValueError:
        errs.append("%s: manifest is not JSON" % name)
        return
    if set(man) != {"targets", "grounding", "prior", "source", "resolved_at"}:
        errs.append("%s: manifest fields" % name)
    if man.get("source") != "operator" or man.get("resolved_at") != "":
        errs.append("%s: manifest source/resolved_at" % name)
    ctx = sorted(p[len("context/"):] for p in files if p.startswith("context/") and p != MANIFEST)
    named = sorted(man["targets"] + man["grounding"])
    if len(man["targets"]) != 1 or named != ctx or man["targets"][0] in man["grounding"]:
        errs.append("%s: the manifest does not name every context file exactly once" % name)
    if any(p not in man["grounding"] for p in man["prior"]):
        errs.append("%s: a prior that is not grounding" % name)
    key = _key(files)
    if key.get("document") != man["targets"][0]:
        errs.append("%s: key document is not the target" % name)
    # INPUT_FORMAT section 9: the required top-level fields of each key form.
    form = KEY_FORMS["negotiation" if "prior_records" in key else "single"]
    if "case_manifest" in key:
        form = form + ("multi_round",)
    absent = [f for f in form if f not in key]
    if absent:
        errs.append("%s: the key lacks %s" % (name, absent))
    for t in files.values():
        if not tr.is_ascii_clean(t):
            errs.append("%s: a file that is not plain ASCII with LF endings" % name)


def _claim_complete(e):
    c = e.get("claim") or {}
    return (isinstance(e.get("unit"), str) and re.match(r"^u\d\d-", e["unit"])
            and isinstance(e.get("rule"), str) and e["rule"].startswith("CONV-")
            and e.get("relation") and e.get("relation") == c.get("relation")
            and isinstance(e.get("kind"), str) and e["kind"]
            and isinstance(c.get("field_label"), str) and c["field_label"]
            and c["field_label"] == tr.norm(c["field_label"])
            and _num(c.get("value_a")) and _num(c.get("value_b")))


def check_single(name, files, errs, enforce=True, compare=True):
    """`compare` False (the reworded-labels probe) skips the figure audit's comparisons,
    which by design stop pairing through a reworded label; the ground-truth scan runs on
    every bundle all the same, since a reworded label leaves every planted flaw in place."""
    key = _key(files)
    res = _audit_bundle(files, enforce)
    errs.extend("%s: %s" % (name, e) for e in res["errors" if compare else "parse_errors"])
    ids = {u["id"] for u in res["doc"]["units"]}
    planted = key.get("planted", [])
    for e in planted:
        if not _claim_complete(e):
            errs.append("%s: incomplete typed reason %r" % (name, e))
        elif e["unit"] not in ids:
            errs.append("%s: planted unit %s is not a unit" % (name, e["unit"]))
    for c in key.get("clean", []):
        if c not in ids:
            errs.append("%s: clean unit %s is not a unit" % (name, c))
        if any(e["unit"] == c for e in planted):
            errs.append("%s: %s is both planted and clean" % (name, c))
    # Ground truth Python does not compute: every instance the family's own scanners
    # find in the text must be keyed, and every keyed one found (D-042).
    checks = key.get("ground_truth_checks", [])
    truth_kinds = gt.kinds(checks)
    found = sorted(gt.signature(x) for x in gt.scan(res, checks))
    keyed = sorted(gt.signature(e) for e in planted if e.get("kind") in truth_kinds)
    if found != keyed:
        errs.append("%s: ground-truth flaws differ from the key: unkeyed %s, not in the text %s"
                    % (name, sorted(set(found) - set(keyed)), sorted(set(keyed) - set(found))))
    if not compare:
        return res
    unmatched = list(res["findings"])
    for e in planted:
        if e.get("kind") in gt.kinds(checks):
            continue
        c = e["claim"]
        want = sorted([tr.r6(c["value_a"]), tr.r6(c["value_b"])])
        hit = [f for f in unmatched if f["unit"] == e["unit"] and f["relation"] == e["relation"]
               and f["field_label"] == c["field_label"] and not f["ratio"]
               and sorted([f["value_a"], f["value_b"]]) == want]
        if len(hit) != 1:
            errs.append("%s: planted %s %s %s is produced %d times (want 1)"
                        % (name, e["unit"], e["relation"], c["field_label"], len(hit)))
            continue
        f = hit[0]
        if f["rule"] != e["rule"]:
            errs.append("%s: %s %s is attributed to %s, the key says %s"
                        % (name, e["unit"], e["relation"], f["rule"], e["rule"]))
        if f["conditional"]:
            errs.append("%s: planted %s is a conditional finding" % (name, e["unit"]))
        unmatched.remove(f)
    for f in unmatched:
        dup = f["ratio"] and any(e["unit"] == f["unit"] and e["relation"] == f["relation"]
                                 and sorted([tr.r6(e["claim"]["value_a"]), tr.r6(e["claim"]["value_b"])])
                                 == sorted([f["value_a"], f["value_b"]]) for e in planted)
        if not dup:
            errs.append("%s: unintended comparison %s %s %s %s/%s under %s"
                        % (name, f["unit"], f["relation"], f["field_label"], f["value_a"],
                           f["value_b"], f["rule"]))
    return res


def check_negotiation(name, files, errs, enforce=True, compare=True):
    key = _key(files)
    res = _audit_bundle(files, enforce)
    errs.extend("%s: %s" % (name, e) for e in res["errors" if compare else "parse_errors"])
    for row in key.get("band_irregularities", []):
        if not (row.get("field_label") and row.get("relation") in ("above_band", "below_band")
                and _num(row.get("value_a")) and _num(row.get("value_b"))
                and str(row.get("rule", "")).startswith("CONV-") and row.get("kind")
                and row.get("unit_id")):
            errs.append("%s: incomplete band row %r" % (name, row))
    seen = set()
    for row in key.get("band_irregularities", []):
        sig = (tr.norm(row.get("field_label", "")), row.get("relation"), repr(tr.r6(row.get("value_a", 0))))
        if sig in seen:
            errs.append("%s: two band rows share label, relation and figure %r" % (name, sig))
        seen.add(sig)
    for row in key.get("prior_records", []):
        if set(row) != {"field_label", "relation", "value_a", "value_b", "unit"}:
            errs.append("%s: prior record fields %r" % (name, row))
    if not compare:
        return res
    got = []
    for f in res["findings"]:
        if f["relation"] in ("above_band", "below_band") and not f["ratio"]:
            got.append((f["field_label"], f["relation"], f["value_a"], f["rule"], f["unit"], f["value_b"]))
        else:
            errs.append("%s: unintended comparison %s %s %s under %s"
                        % (name, f["unit"], f["relation"], f["field_label"], f["rule"]))
    want = [(r["field_label"], r["relation"], tr.r6(r["value_a"]), r["rule"], r["unit_id"],
             tr.r6(r["value_b"])) for r in key.get("band_irregularities", [])]
    if sorted(got, key=repr) != sorted(want, key=repr):
        errs.append("%s: band findings differ from the key: got %s, key %s"
                    % (name, sorted(set(got) - set(want), key=repr), sorted(set(want) - set(got), key=repr)))
    records, refusals, vanished = au.prior_records(res)
    rk = lambda r: (r["field_label"], r["relation"], repr(r["value_a"]), repr(r["value_b"]), r["unit"])
    plan = key.get("version_changes", [])
    if key.get("prior_records") != prior_records_from(plan):
        errs.append("%s: prior_records are not the family's plan" % name)
    # The comparisons of labels both versions state are mechanical: the audit reads
    # them from the text and they must be the plan's.
    have = sorted(rk(r) for r in records)
    planned = sorted(rk(dict(v, relation=v["expect"])) for v in plan
                     if v["expect"] in RECORD_RELATIONS and v["expect"] != "absent_since_prior")
    if have != planned:
        errs.append("%s: change records differ from the family's plan: audit %s, plan %s"
                    % (name, sorted(set(have) - set(planned)), sorted(set(planned) - set(have))))
    # A vanished label is withdrawn or renamed by the family's ground truth; the audit
    # only states the facts, which must be the plan's.
    gone = {v["field_label"]: v for v in vanished}
    want_gone = {v["field_label"]: v for v in plan
                 if v["expect"] in ("absent_since_prior", "not_withdrawn")}
    if sorted(gone) != sorted(want_gone):
        errs.append("%s: vanished labels %s, plan %s" % (name, sorted(gone), sorted(want_gone)))
    for lab, v in want_gone.items():
        g = gone.get(lab)
        if g is not None and not (tr.same(g["value_b"], v["value_b"]) and g["unit"] == v["unit"]):
            errs.append("%s: the earlier figure of %s is not the plan's" % (name, lab))
    new = au.new_labels(res)
    want_new = {v["field_label"] for v in plan if v["expect"] == "none"}
    want_new |= {v["later_field_label"] for v in plan if v["expect"] == "not_withdrawn"}
    if sorted(new) != sorted(want_new):
        errs.append("%s: labels new in the later version %s, plan %s" % (name, sorted(new), sorted(want_new)))
    if refusals:
        errs.append("%s: unplanned refusals %s" % (name, refusals))
    if "rename_probes" in key:
        _check_rename_probes(name, key, res, gone, new, errs)
        if key.get("expected_refusals") != expected_refusals_from(key["rename_probes"]):
            errs.append("%s: expected_refusals are not the renamed terms" % name)
    return res


RENAME_PROBE_KINDS = ("new_in_later_version", "renamed_moved_to_other_section", "renamed_value_moved",
                      "renamed_value_unchanged", "reordered_sections", "value_in_different_format",
                      "withdrawn", "withdrawn_beside_newcomer")
RENAMED = {"renamed_value_unchanged": "same", "renamed_value_moved": "same",
           "renamed_moved_to_other_section": "other"}


def _line_values(doc):
    return {ln["norm"]: ln["value"] for u in doc["units"] for ln in u["lines"]}


def _check_rename_probes(name, key, res, gone, new, errs):
    """Every rename-probe row holds in the rendered versions: the facts the generator
    planted, read back from the text by the audit (D-042: ground truth, never Shimmer's
    refusal rule)."""
    rows = key["rename_probes"]
    kinds = sorted({r.get("kind") for r in rows})
    if kinds != sorted(RENAME_PROBE_KINDS):
        errs.append("%s: rename probe kinds %s" % (name, kinds))
    target, prior = res["doc"], res["prior"]
    now_v, then_v = _line_values(target), _line_values(prior)
    plan = {v["field_label"]: v for v in key.get("version_changes", [])}
    for r in rows:
        k, lab, later = r.get("kind"), r.get("field_label"), r.get("later_field_label")
        ok = True
        if k in RENAMED:
            g = gone.get(lab)
            ok = (r.get("expect") == "not_withdrawn" and g is not None and later in new
                  and lab in then_v and lab not in now_v and later not in then_v
                  and r.get("satisfied_by") == (["refusal", "matched_rename"] if RENAMED[k] == "same"
                                                else ["matched_rename"])
                  and r.get("false_positive_if") == "absent_since_prior"
                  and g["unit_id"] == r.get("prior_unit_id") and new[later][0] == r.get("unit_id")
                  and (r.get("unit_id") == r.get("prior_unit_id")) == (RENAMED[k] == "same")
                  and then_v[lab] == r.get("written_before") and now_v[later] == r.get("written_after")
                  and r.get("moved_percent") == round(abs(r["value_after"] - r["value_before"]) * 100.0
                                                      / abs(r["value_before"]), 2)
                  and (r["moved_percent"] == 0) == (k == "renamed_value_unchanged")
                  # a moved rename moves by 2.05 to 45 percent in every bundle, the twin
                  # included, and the expected refusal kind is the one its figures support
                  and (k == "renamed_value_unchanged" or ft.in_move_range(r["value_before"], r["value_after"]))
                  and r.get("refusal_kind") == ft.expected_refusal_kind(
                      r["value_before"], r["value_after"], RENAMED[k] == "same"))
            if k == "renamed_moved_to_other_section" and g is not None:
                ok = ok and not g["newcomers_same_measure"]
        elif k in ("withdrawn", "withdrawn_beside_newcomer"):
            g = gone.get(lab)
            unrelated = [n for n in (g or {}).get("newcomers_same_measure", [])
                         if plan.get(n, {}).get("expect") == "none"]
            ok = (r.get("expect") == "absent_since_prior" and g is not None and later is None
                  and lab in then_v and lab not in now_v
                  and (bool(unrelated) == (k == "withdrawn_beside_newcomer"))
                  and (k == "withdrawn_beside_newcomer"
                       or not g["newcomers_same_measure"]))
        elif k == "new_in_later_version":
            ok = (r.get("reason") == "not_stated_in_earlier_version" and r.get("expect") == "none"
                  and lab == later and lab in new and lab not in then_v)
        elif k == "value_in_different_format":
            ok = (r.get("reason") == "comma_grouped_digits" and lab == later
                  and plan.get(lab, {}).get("expect") == r.get("expect") and "," in now_v.get(lab, "")
                  and then_v.get(lab) == r.get("written_before") and now_v.get(lab) == r.get("written_after"))
        elif k == "reordered_sections":
            by_slug = {u["id"][4:]: u["id"] for u in target["units"] if not u["preamble"]}
            order = [by_slug.get(u["id"][4:]) for u in prior["units"] if not u["preamble"]]
            ok = (r.get("reason") == "unit_identity_by_heading" and r.get("prior_order") == order
                  and order != [u["id"] for u in target["units"] if not u["preamble"]])
        else:
            ok = False
        if not ok:
            errs.append("%s: rename probe %s %s does not hold in the versions" % (name, k, lab))


def check_case(name, files, errs):
    """A multi-round test's live case manifest: the controller's rules (multi_round_case
    .validate, restated), then this family's own declaration: the rounds the key names in
    version order, one source per label line of every round document, on its unit, a
    renamed term kept on one issue, and the reuse and round changes the key states."""
    key = _key(files)
    if "case_manifest" not in key and mc.FILE not in files:
        return
    if key.get("case_manifest") != mc.FILE or mc.FILE not in files:
        errs.append("%s: the key and the bundle disagree on the case manifest" % name)
        return
    try:
        case = json.loads(files[mc.FILE])
    except ValueError:
        errs.append("%s: the case manifest is not JSON" % name)
        return
    context = {p[len("context/"):]: t for p, t in files.items() if p.startswith("context/")}
    documents = mc.documents_as_loaded(context)
    errs.extend("%s: case manifest: %s" % (name, e) for e in mc.validate(case, documents))
    if errs and any(e.startswith(name + ": case manifest") for e in errs):
        return
    target, man = _target(files)
    rounds = sorted(case["rounds"], key=lambda r: r["sequence"])
    names = {n.rsplit(".", 1)[0]: n for n in context}
    round_names = [names.get(r["document_ids"][0]) if len(r["document_ids"]) == 1 else None for r in rounds]
    want = [{"round_id": r["round_id"], "sequence": r["sequence"]} for r in rounds]
    have = [{"round_id": r.get("round_id"), "sequence": r.get("sequence")} for r in key.get("rounds", [])]
    versions = [r.get("version") for r in key.get("rounds", [])]
    if case.get("case_id") != name or want != have or len(rounds) not in (2, 3):
        errs.append("%s: the case rounds are not the key's rounds" % name)
        return
    expect_versions = (["earliest"] if len(rounds) == 3 else []) + ["prior", "target"]
    if (versions != expect_versions or round_names[-1] != target or not man["prior"]
            or round_names[-2] != man["prior"][0]
            or (len(rounds) == 3 and (round_names[0] not in man["grounding"]
                                      or round_names[0] in man["prior"]))):
        errs.append("%s: the case rounds are not earliest, prior and target in order" % name)
        return
    # INPUT_FORMAT section 12: a multi-round bundle's context/ holds only case documents.
    others = sorted(n for n in context if n != MANIFEST[len("context/"):] and n not in round_names)
    if others:
        errs.append("%s: context/ holds files no round names: %s" % (name, others))
    by_doc = {}
    for s in case["sources"]:
        by_doc.setdefault(s["document_id"], []).append(s)
    issue_at = []
    for r, rn in zip(rounds, round_names):
        text = context[rn]
        want_spans, pos = [], 0
        for ln in text.split("\n"):
            if mc.LINE.match(ln) and mc.unit_at(text, pos) is not None:
                want_spans.append((pos, pos + len(ln), ln, mc.unit_at(text, pos)))
            pos += len(ln) + 1
        got = sorted((s["char_start"], s["char_end"], s["quote"], s["unit_id"])
                     for s in by_doc.get(r["document_ids"][0], []))
        if got != want_spans or any(s["round_id"] != r["round_id"] for s in by_doc.get(r["document_ids"][0], [])):
            errs.append("%s: round %s does not declare one source per label line on its unit"
                        % (name, r["round_id"]))
        issue_at.append({s["quote"].split(":", 1)[0]: s["issue_id"]
                         for s in by_doc.get(r["document_ids"][0], [])})
    for a, b in zip(issue_at, issue_at[1:]):
        for label in set(a) & set(b):
            if a[label] != b[label]:
                errs.append("%s: %s changes issue between rounds" % (name, label))
    raw = {}
    for d in issue_at:
        for label in d:
            raw[tr.norm(label)] = label
    for r in key.get("rename_probes", []):
        if r.get("kind", "").startswith("renamed_"):
            old, new = raw.get(r["field_label"]), raw.get(r["later_field_label"])
            if old is None or new is None or issue_at[-2].get(old) != issue_at[-1].get(new):
                errs.append("%s: the renamed term %s is not one issue across the rename"
                            % (name, r["field_label"]))
    texts = [context[n] for n in round_names]
    if key.get("round_reuse") != mc.round_reuse(texts, au.parse_document):
        errs.append("%s: round_reuse differs from the round documents" % name)
    if len(rounds) == 3:
        first, second = au.parse_document(texts[0], "r1"), au.parse_document(texts[1], "r2")
        if ([u["heading"] for u in first["units"]] != [u["heading"] for u in second["units"]]
                or [u["labels"] for u in first["units"]] != [u["labels"] for u in second["units"]]):
            errs.append("%s: the earliest version is not the prior's sections and labels" % name)
        changes = []
        for u1, u2 in zip(first["units"], second["units"]):
            v1 = {ln["norm"]: ln["kind"] for ln in u1["lines"]}
            for ln in u2["lines"]:
                a, b = v1.get(ln["norm"]), ln["kind"]
                if a != b and a is not None and a[0] == b[0] == "figure":
                    changes.append({"field_label": ln["norm"], "round_id": "r2", "from_round": "r1",
                                    "unit_id": u2["id"], "value_before": tr.r6(a[1]),
                                    "value_after": tr.r6(b[1]), "unit": b[2]})
        changes.sort(key=lambda c: c["field_label"])
        if not changes or key.get("round_changes") != changes:
            errs.append("%s: round_changes differ from the earliest and prior versions" % name)
        reused = {x["unit_id"] for x in key.get("round_reuse", []) if x["round_id"] == "r2"}
        changed = {c["unit_id"] for c in changes}
        if not reused or reused & changed:
            errs.append("%s: round r2 reuses no unit, or reuses a changed one" % name)
    _check_multi_round_key(name, files, key, case, context, rounds, round_names, errs)


def _check_multi_round_key(name, files, key, case, context, rounds, round_names, errs):
    """The multi-round key, read back from the rendered round documents, the conventions
    and the case manifest alone: every label line whose figure lies outside the band of
    the mandate rule governing its issue (the rule naming the target's label of that
    issue) is exactly one planted entry, in its round and document, on its unit; the
    target round's entries are the band breaches the negotiation-style key lists, with
    their kinds; the clean entries are units of their documents with no planted entry
    there, and the target round's are the key's `clean`."""
    mr = key.get("multi_round")
    if not isinstance(mr, dict) or set(mr) != {"planted", "clean"}:
        errs.append("%s: no multi-round key" % name)
        return
    alias = {}
    if key.get("probe") == "reworded_labels":
        ch = key["probe_change"]
        alias = {tr.norm(ch["label_to"]): tr.norm(ch["label_from"])}
    convs = [p for p in files if p.startswith("conventions/")]
    conv = au.parse_conventions(files[convs[0]], convs[0])
    docs = [au.parse_document(context[n], n) for n in round_names]
    universe = set()
    for u in docs[-1]["units"]:
        universe |= u["labels"]
    universe |= set(alias.values())
    rule_of = {}
    for r in conv["rules"]:
        for lab in au._named(r, universe):
            if lab in rule_of:
                errs.append("%s: %s is named by two mandate rules" % (name, lab))
            rule_of[lab] = r
    src = {}
    for s in case["sources"]:
        src[(s["document_id"], s["unit_id"], tr.norm(s["quote"].split(":", 1)[0]))] = s["issue_id"]
    target_doc = rounds[-1]["document_ids"][0]
    issue_rule = {}
    for (doc_id, _, lab), issue in src.items():
        if doc_id == target_doc and alias.get(lab, lab) in rule_of:
            issue_rule[issue] = rule_of[alias.get(lab, lab)]
    want = []
    for r, d in zip(rounds, docs):
        doc_id = r["document_ids"][0]
        for u in d["units"]:
            for ln in u["lines"]:
                k = ln["kind"]
                rule = issue_rule.get(src.get((doc_id, u["id"], ln["norm"])))
                if rule is None or k[0] != "figure":
                    continue
                bands = [b for b in rule["own_bands"] if b["powers"] == tr.measure_powers(k[2])]
                if len(bands) != 1:
                    errs.append("%s: %s has no single band in its measure" % (name, rule["id"]))
                    continue
                lo, hi = bands[0]["lo"], bands[0]["hi"]
                if lo <= k[1] <= hi:
                    continue
                rel = "above_band" if k[1] > hi else "below_band"
                want.append((r["round_id"], doc_id, u["id"], rule["id"], rel, ln["norm"], repr(tr.r6(k[1])),
                             repr(tr.r6(hi if k[1] > hi else lo)), src[(doc_id, u["id"], ln["norm"])]))
    def sig(e):
        c = e.get("claim") or {}
        return (e.get("round_id"), e.get("document_id"), e.get("unit"), e.get("rule"), e.get("relation"),
                c.get("field_label"), repr(tr.r6(c.get("value_a", 0))), repr(tr.r6(c.get("value_b", 0))),
                e.get("issue_id"))
    have = [sig(e) for e in mr["planted"]]
    if sorted(have) != sorted(want):
        errs.append("%s: multi-round planted entries differ from the round documents: unkeyed %s, "
                    "not in the documents %s" % (name, sorted(set(want) - set(have))[:4],
                                                  sorted(set(have) - set(want))[:4]))
    last = rounds[-1]["round_id"]
    on_target = sorted((e["unit"], e["claim"]["field_label"], e["relation"], e["kind"])
                       for e in mr["planted"] if e.get("round_id") == last)
    bands_key = sorted((b["unit_id"], b["field_label"], b["relation"], b["kind"])
                       for b in key.get("band_irregularities", []))
    if on_target != bands_key:
        errs.append("%s: the target round's multi-round entries are not the band breaches" % name)
    if any(e.get("kind") != EARLIER_ROUND_KIND for e in mr["planted"] if e.get("round_id") != last):
        errs.append("%s: an earlier round's entry has another kind" % name)
    ids = {r["round_id"]: (r["document_ids"][0], {u["id"] for u in d["units"]}) for r, d in zip(rounds, docs)}
    hit = {(e["round_id"], e["unit"]) for e in mr["planted"]}
    for c in mr["clean"]:
        doc_id, units = ids.get(c.get("round_id"), (None, set()))
        if c.get("document_id") != doc_id or c.get("unit") not in units or (c["round_id"], c["unit"]) in hit:
            errs.append("%s: multi-round clean entry %r" % (name, c))
    if sorted(c["unit"] for c in mr["clean"] if c.get("round_id") == last) != sorted(key.get("clean", [])):
        errs.append("%s: the target round's clean entries are not the key's clean list" % name)


def _chain_figures(u, label):
    """(carried first row, every row, stated figure) of a unit whose first table column
    with a measure is summed into the label line `label`."""
    stated = None
    for ln in u["lines"]:
        if ln["norm"] == label and ln["kind"][0] == "figure":
            stated = ln["kind"][1]
    for t in u["tables"]:
        for c, hd in enumerate(t["headers"]):
            if hd["measure"]:
                rows = [row[c][1] for row in t["rows"] if row[c][0] == "number"]
                if rows and stated is not None:
                    return rows[0], rows, stated
    return None


def _neighbour_checks(name, res, planted, errs, twin_res=None):
    """Independent arithmetic for neighbour-dependent flaws: the carried figure, read in
    both units, must disagree exactly as the key says, and every other neighbour pair
    (and the whole twin) must carry its figure across."""
    deps = [e for e in planted if "depends_on_unit" in e]
    if not deps:
        return
    labels = [e["claim"]["field_label"] for e in deps if e["relation"] == "sum_mismatch"]
    label = labels[0] if labels else deps[0].get("chain_label")
    units = [u for u in res["doc"]["units"] if not u["preamble"]]
    pos = {u["id"]: i for i, u in enumerate(units)}
    broken = set()
    for e in deps:
        a, b = pos.get(e["unit"]), pos.get(e["depends_on_unit"])
        if a is None or b is None or abs(a - b) != 1:
            errs.append("%s: %s does not sit beside %s" % (name, e["unit"], e["depends_on_unit"]))
            continue
        me, nb = _chain_figures(units[a], label), _chain_figures(units[b], label)
        if me is None or nb is None:
            errs.append("%s: %s carries no chain figure" % (name, e["unit"]))
            continue
        total = tr.r6(sum(me[1]))
        nb_total = tr.r6(sum(nb[1]))
        if e["relation"] == "carry_mismatch":
            # Wrong only beside its neighbour: both units add up on their own, and the
            # carried figure differs from the column sum of the unit before.
            ok = (b == a - 1 and not tr.same(me[0], nb_total) and tr.same(total, me[2])
                  and tr.same(nb_total, nb[2])
                  and tr.same(e["claim"]["value_a"], nb_total) and tr.same(e["claim"]["value_b"], me[0]))
            broken.add((b, a))
        elif b < a:    # carried in from the unit before
            ok = (not tr.same(me[0], nb_total) and tr.same(nb_total + sum(me[1][1:]), me[2])
                  and tr.same(e["claim"]["value_a"], total) and tr.same(e["claim"]["value_b"], me[2]))
            broken.add((b, a))
        else:          # carried out to the unit after
            ok = (tr.same(nb[0], total) and not tr.same(total, me[2])
                  and tr.same(e["claim"]["value_a"], total) and tr.same(e["claim"]["value_b"], me[2]))
            broken.add((a, b))
        if not ok:
            errs.append("%s: the neighbour arithmetic of %s does not hold" % (name, e["unit"]))
    for i in range(1, len(units)):
        if (i - 1, i) in broken:
            continue
        # The rule as written: the first row carries the column sum of the unit before.
        p, q = _chain_figures(units[i - 1], label), _chain_figures(units[i], label)
        if p and q and not tr.same(q[0], tr.r6(sum(p[1]))):
            errs.append("%s: %s does not carry the figure of the unit before" % (name, units[i]["id"]))
    if twin_res is not None:
        tunits = [u for u in twin_res["doc"]["units"] if not u["preamble"]]
        for i in range(1, len(tunits)):
            p, q = _chain_figures(tunits[i - 1], label), _chain_figures(tunits[i], label)
            if p and q and not (tr.same(q[0], p[2]) and tr.same(p[2], tr.r6(sum(p[1])))):
                errs.append("twin: %s does not carry the figure of the unit before" % tunits[i]["id"])


def long_range_baselines(files):
    """The baselines of family_provisions.baselines, read from a written long-range
    bundle: the units and their labels from the rendered document, the planted entries
    and their related units from the key."""
    key = _key(files)
    target, _ = _target(files)
    doc = au.parse_document(files["context/" + target], target)
    units = []
    for u in doc["units"]:
        if not u["preamble"]:
            fields = {lab: "" for lab in u["labels"]}
            fields.update((ln["norm"], ln["value"]) for ln in u["lines"])
            units.append((u["id"], fields))
    planted = [(e["unit"], e["related_unit"], e["relation"]) for e in key.get("planted", [])]
    lr = key["long_range"]
    return fp.baselines(units, planted, lr["decided_by_label"], lr["decided_by_term"])


def check_long_range(name, files, errs):
    """A long-range bundle (every one: the test, its twin and the four probes): every
    planted entry names its related unit, its stated distance is the true distance and
    at least `min_distance`; `definitions_first` is what the text shows; the related
    units are definitions and units that are no definition; the deciding figures live
    only in the document (no grounding file but a declared earlier version carries a
    digit); a cross-reference line sits on some uses only, as the key says; and the
    positional, label-only and track-and-term baselines all score below 1."""
    key = _key(files)
    lr = key["long_range"]
    target, _ = _target(files)
    doc = au.parse_document(files["context/" + target], target)
    units = [u for u in doc["units"] if not u["preamble"]]
    by_id = {u["id"]: u for u in units}
    far = int(lr.get("min_distance", 0))
    dists = []
    for e in key.get("planted", []):
        rel = e.get("related_unit")
        if rel not in by_id or e["unit"] not in by_id:
            errs.append("%s: %s names no related unit" % (name, e["unit"]))
            continue
        d = unit_distance(e["unit"], rel)
        dists.append(d)
        if e.get("distance") != d or d < far:
            errs.append("%s: %s is %d units from %s (key %s, at least %d)"
                        % (name, e["unit"], d, rel, e.get("distance"), far))
        xref = [ln for ln in by_id[e["unit"]]["lines"] if ln["norm"] == "cross reference"]
        has = bool(xref) and xref[0]["value"] == by_id[rel]["heading"]
        if bool(xref) != has or e.get("cross_reference_line") is not has:
            errs.append("%s: %s cross reference line %s, key %s"
                        % (name, e["unit"], has, e.get("cross_reference_line")))
    flags = {e.get("cross_reference_line") for e in key.get("planted", [])}
    if key.get("planted") and flags != {True, False}:
        errs.append("%s: every planted use has a cross reference, or none does" % name)
    is_def = [any(ln["norm"] == "defined term" for ln in u["lines"]) for u in units]
    defs_first = all(is_def[:sum(is_def)])
    if lr.get("definitions_first") is not defs_first:
        errs.append("%s: definitions_first is %s in the text, %s in the key"
                    % (name, defs_first, lr.get("definitions_first")))
    rel_kinds = {is_def[[u["id"] for u in units].index(e["related_unit"])]
                 for e in key.get("planted", []) if e.get("related_unit") in by_id}
    if key.get("planted") and rel_kinds != {True, False}:
        errs.append("%s: the related units are all definitions, or none is" % name)
    if key.get("planted"):
        scores = long_range_baselines(files)
        if not fp.baselines_below_one(scores):
            errs.append("%s: a baseline that reads no value finds every related unit: %s" % (name, scores))
    # the uses: units with a provision type and no table (a fee table is no use)
    uses = [u for u in units if any(ln["norm"] == "provision type" for ln in u["lines"]) and not u["tables"]]
    share = round(sum(any(ln["norm"] == "cross reference" for ln in u["lines"]) for u in uses)
                  / float(len(uses) or 1), 2)
    if lr.get("cross_reference_share") != share or not 0.3 <= share <= 0.7:
        errs.append("%s: cross reference share %s, key %s" % (name, share, lr.get("cross_reference_share")))
    for n, t in files.items():
        if (n.startswith("context/") and n.endswith(".md") and n != "context/" + target
                and n[len("context/"):] not in json.loads(files[MANIFEST])["prior"] and re.search(r"\d", t)):
            errs.append("%s: grounding file %s states a figure" % (name, n))


def _roles(test):
    roles = {}
    for folder, files in test.items():
        key = _key(files)
        if key.get("probe"):
            roles[key["probe"]] = folder
        elif key.get("planted") or key.get("band_irregularities"):
            roles["base"] = folder
        else:
            roles["twin"] = folder
    return roles


def _strip(key):
    k = dict(key)
    for f in ("document", "twin_of", "probe", "probe_change"):
        k.pop(f, None)
    return k


def _lines_diff(a, b):
    """Lines removed from a and lines added in b, by a sequence diff."""
    la, lb = a.split("\n"), b.split("\n")
    gone, new = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, la, lb, autojunk=False).get_opcodes():
        if op in ("replace", "delete"):
            gone.extend(la[i1:i2])
        if op in ("replace", "insert"):
            new.extend(lb[j1:j2])
    return gone, new


def validate_test(test, min_flaws=10, min_kinds=3):
    """All checks of S3 item 8 on one generated test ({folder: {path: text}}).
    Returns a list of errors; empty means valid."""
    errs = []
    roles = _roles(test)
    needed = ("base", "twin") + PROBES
    missing = [r for r in needed if r not in roles]
    if missing or len(test) != len(needed):
        return ["roles found %s, missing %s" % (sorted(roles), missing)]
    for folder, files in test.items():
        check_structure(folder, files, errs)
    if errs:
        return errs
    for folder in sorted(test):
        check_case(folder, test[folder], errs)
        check_rule_statements(folder, test[folder], errs)
    base, twin = test[roles["base"]], test[roles["twin"]]
    bkey, tkey = _key(base), _key(twin)
    negotiation = "prior_records" in bkey
    check = check_negotiation if negotiation else check_single
    bres = check(roles["base"], base, errs)
    # counts and kinds
    if negotiation:
        flaws = bkey["band_irregularities"]
        kinds = {r["kind"] for r in flaws}
    else:
        flaws = bkey["planted"]
        kinds = {e["kind"] for e in flaws}
    if len(flaws) < min_flaws:
        errs.append("base: %d planted flaws (want at least %d)" % (len(flaws), min_flaws))
    if len(kinds) < min_kinds:
        errs.append("base: %d kinds (want at least %d)" % (len(kinds), min_kinds))
    if len(bkey.get("clean", [])) < 1:
        errs.append("base: no clean distractor")
    # the twin
    check(roles["twin"], twin, errs)
    if bkey.get("twin_of") != roles["twin"] or tkey.get("twin_of") != roles["base"]:
        errs.append("twin: the two keys do not name each other")
    if (tkey.get("planted") or tkey.get("band_irregularities")):
        errs.append("twin: the twin key plants a flaw")
    if bkey["document"] == tkey["document"]:
        errs.append("twin: the twin's document has the same name")
    if bkey.get("clean") != tkey.get("clean"):
        errs.append("twin: the clean lists differ")
    for path in base:
        if path.startswith("conventions/") or (path.startswith("context/") and path != MANIFEST
                                               and path != "context/" + bkey["document"]):
            if twin.get(path) != base[path]:
                errs.append("twin: %s differs from the test" % path)
    tres = _audit_bundle(twin, True)
    if [u["id"] for u in tres["doc"]["units"]] != [u["id"] for u in bres["doc"]["units"]]:
        errs.append("twin: unit ids do not line up")
    if not negotiation:
        _neighbour_checks("base", bres, bkey["planted"], errs, tres)
    for folder in sorted(test):
        if "long_range" in _key(test[folder]):
            check_long_range(folder, test[folder], errs)
    # probes
    bdoc = base["context/" + bkey["document"]]
    for probe in PROBES:
        files = test[roles[probe]]
        key = _key(files)
        doc = files["context/" + key["document"]]
        if probe == "reworded_labels":
            check(roles[probe], files, errs, enforce=False, compare=False)
            ch = key["probe_change"]
            gone, new = _lines_diff(bdoc, doc)
            if not gone or len(gone) != len(new) or any(
                    g.replace(ch["label_from"], ch["label_to"], 1) != n for g, n in zip(gone, new)):
                errs.append("%s: the document differs by more than the label" % probe)
            exp = _strip(bkey)
            old_n, new_n = tr.norm(ch["label_from"]), tr.norm(ch["label_to"])
            if old_n == new_n:
                errs.append("%s: the new label normalises to the old one" % probe)
            if negotiation:
                exp["band_irregularities"] = [dict(r, field_label=new_n if r["field_label"] == old_n else r["field_label"])
                                              for r in exp["band_irregularities"]]
                exp["prior_records"] = [dict(r, field_label=new_n if r["field_label"] == old_n else r["field_label"])
                                        for r in exp["prior_records"]]
                touched = any(r["field_label"] == new_n for r in exp["band_irregularities"] + exp["prior_records"])
                if "multi_round" in exp:
                    exp["multi_round"] = key.get("multi_round")   # checked against the documents
            else:
                exp["planted"] = [dict(e, claim=dict(e["claim"], field_label=gt.reword_field(
                    e["claim"]["field_label"], old_n, new_n))) for e in exp["planted"]]
                exp["ground_truth_checks"] = gt.reword_checks(exp["ground_truth_checks"], old_n, new_n)
                touched = any(e["claim"]["field_label"] == new_n
                              or e["claim"]["field_label"].startswith(new_n + " row") for e in exp["planted"])
            if not touched:
                errs.append("%s: the reworded label is in no keyed reason" % probe)
            if _strip(key) != exp:
                errs.append("%s: the key differs from the test's by more than the label" % probe)
        elif probe == "reordered_sections":
            # Fully re-audited, the carry scanner included: family 6 reorders by a
            # rotation that creates no neighbour pair breaking the chain (section 11.2).
            res = check(roles[probe], files, errs)
            if sorted(bdoc.split("\n")) != sorted(doc.split("\n")) or bdoc == doc:
                errs.append("%s: not a reordering of the same sections" % probe)
            by_head = {u["heading"]: u["id"] for u in res["doc"]["units"]}
            base_by_id = {u["id"]: u["heading"] for u in bres["doc"]["units"]}
            exp = _strip(bkey)
            def remap(x):
                return by_head[base_by_id[x]]
            exp["clean"] = [remap(c) for c in exp["clean"]]
            if negotiation:
                exp["band_irregularities"] = [dict(r, unit_id=remap(r["unit_id"])) for r in exp["band_irregularities"]]
                if "rename_probes" in exp:
                    exp["rename_probes"] = [
                        dict(r, unit_id=remap(r["unit_id"]) if r["unit_id"] else None,
                             prior_unit_id=remap(r["prior_unit_id"]) if r["prior_unit_id"] else None,
                             prior_order=[remap(x) for x in r["prior_order"]])
                        for r in exp["rename_probes"]]
                    exp["expected_refusals"] = expected_refusals_from(exp["rename_probes"])
                if "round_reuse" in exp:
                    last = exp["rounds"][-1]["round_id"]
                    exp["round_reuse"] = [dict(r, unit_id=remap(r["unit_id"])) if r["round_id"] == last else r
                                          for r in exp["round_reuse"]]
                if "multi_round" in exp:
                    exp["multi_round"] = key.get("multi_round")   # checked against the documents
            else:
                new_pl = []
                for e in exp["planted"]:
                    e2 = dict(e, unit=remap(e["unit"]))
                    for lk in gt.LINKS:
                        if lk in e2:
                            e2[lk] = remap(e2[lk])
                    if "distance" in e2:
                        e2["distance"] = unit_distance(e2["unit"], e2["related_unit"])
                    new_pl.append(e2)
                exp["planted"] = new_pl
                for e in new_pl:
                    if "depends_on_unit" in e:
                        a, b = int(e["unit"][1:3]), int(e["depends_on_unit"][1:3])
                        if abs(a - b) != 1:
                            errs.append("%s: a neighbour-dependent flaw left its neighbour" % probe)
            if _strip(key) != exp:
                errs.append("%s: the key ids are not the test's ids after the move" % probe)
        elif probe == "term_only_in_later_version":
            check(roles[probe], files, errs)
            man = json.loads(files[MANIFEST])
            if not man["prior"]:
                errs.append("%s: no earlier version declared" % probe)
                continue
            prior_text = files["context/" + man["prior"][0]]
            term = key["probe_change"]["term"]
            exp = _strip(bkey)
            if negotiation:
                # Every earlier version is the test's less the one term; the target is the
                # test's; the term carries a keyed breach (D-042, decision 6).
                bman = json.loads(base[MANIFEST])
                bprior = base["context/" + bman["prior"][0]]
                gone, new = _lines_diff(bprior, prior_text)
                gone = [g for g in gone if g.strip()]    # a unit left with no line loses its blank line too
                if doc != bdoc or new or len(gone) != 1 or not gone[0].startswith(term + ": "):
                    errs.append("%s: the earlier version is not the test's less the one term" % probe)
                for n in sorted(set(bman["grounding"]) - set(bman["prior"])):
                    if "context/" + n in files:
                        g2, n2 = _lines_diff(base["context/" + n], files["context/" + n])
                        g2 = [g for g in g2 if g.strip()]
                        if n2 or len(g2) != 1 or not g2[0].startswith(term + ": "):
                            errs.append("%s: %s is not the test's less the one term" % (probe, n))
                tn = tr.norm(term)
                if not any(r["field_label"] == tn for r in bkey["band_irregularities"]):
                    errs.append("%s: the term carries no keyed flaw" % probe)
                exp["version_changes"] = [
                    dict(v, change="new_in_later_version", expect="none", value_b=None)
                    if v["field_label"] == tn else v for v in exp["version_changes"]]
                exp["prior_records"] = prior_records_from(exp["version_changes"])
                exp["round_reuse"] = key.get("round_reuse")   # checked against the documents
                exp["multi_round"] = key.get("multi_round")   # likewise
            else:
                gone, new = _lines_diff(bdoc, prior_text)
                if doc != bdoc or new or len(gone) != 1 or not gone[0].startswith(term + ": "):
                    errs.append("%s: the earlier version is not the test less the one term" % probe)
                if not re.search(r"\d", gone[0] if gone else ""):
                    errs.append("%s: the term carries no figure" % probe)
                unit = key["probe_change"]["unit"]
                if not any(e["unit"] == unit and e["claim"]["field_label"] == tr.norm(term)
                           for e in bkey["planted"]):
                    errs.append("%s: the term carries no keyed flaw" % probe)
            if _strip(key) != exp:
                errs.append("%s: the key differs from the test's" % probe)
        else:
            check(roles[probe], files, errs)
            gone, new = _lines_diff(bdoc, doc)
            if len(gone) != 1 or len(new) != 1 or gone[0] == new[0]:
                errs.append("%s: not exactly one value rewritten" % probe)
            else:
                a, b = re.findall(tr.NUMBER, gone[0]), re.findall(tr.NUMBER, new[0])
                if (len(a) != len(b) or not a or a == b
                        or [tr.to_number(x) for x in a] != [tr.to_number(x) for x in b]):
                    errs.append("%s: the rewritten value does not read the same" % probe)
            exp = _strip(bkey)
            if "multi_round" in exp:
                exp["multi_round"] = key.get("multi_round")   # checked against the documents
            if _strip(key) != exp:
                errs.append("%s: the key differs from the test's" % probe)
    return errs


def generate(spec):
    """Build and validate; raise ValidationError (and write nothing) on any failure."""
    test = build_bundles(spec)
    errs = validate_test(test)
    if errs:
        raise ValidationError("%s seed %s: %d problem(s):\n  %s"
                              % (spec["family"], spec["seed"], len(errs), "\n  ".join(errs[:40])))
    return test


def write_test(test, out_dir):
    """Write one validated test under out_dir/<test id>/<bundle>/..."""
    written = []
    for folder in sorted(test):
        for path in sorted(test[folder]):
            full = os.path.join(out_dir, folder, *path.split("/"))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(test[folder][path])
            written.append(full)
    return written


def read_test(test_dir):
    """Read every bundle folder under test_dir back into {folder: {path: text}}."""
    test = {}
    for folder in sorted(os.listdir(test_dir)):
        root = os.path.join(test_dir, folder)
        if not os.path.isdir(root):
            continue
        files = {}
        for dirpath, _, names in os.walk(root):
            for n in names:
                full = os.path.join(dirpath, n)
                rel = os.path.relpath(full, root).replace(os.sep, "/")
                with open(full, "r", encoding="utf-8", newline="") as fh:
                    files[rel] = fh.read()
        test[folder] = files
    return test
