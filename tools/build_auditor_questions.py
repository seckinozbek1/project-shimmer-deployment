"""The rule check's development questions (D-S57 item 3, D-S62 item 1): read development material,
each question exactly the call the pipeline makes.

    py -3.12 -X utf8 tools/build_auditor_questions.py --contractnli-dev <dev.json> --out <questions.json>

ContractNLI's development split (exposed development, read before in L4b; never the test split, and
never a training row) is built into bundles the way its adapter builds them (one `## P-NNNNN` unit per
part, one rule per hypothesis, benchmark/adapters/contractnli/adapter.py and common/bundle.py), and
each question is the rule check on one unit and one rule as the pipeline renders it: the unit's text
as pairing_map.split_units reads the rendered document (paired_review.unit_texts_for), the rule's
text as convention_parser reads the rendered rules, auditor_questions.render_rule_check, one user
turn. So a replay of a question is byte for byte the pipeline's call on that unit and rule (the
proof in scripts/auditor_roles_checks.py renders both and compares).

The answer of a question is read from the release's own annotation of the unit's hypothesis:
    met               the hypothesis is Entailment and the unit holds one of its evidence spans
    not_met           Contradiction, and the unit holds one of its evidence spans
    cannot be settled NotMentioned (no unit settles it)
A unit of an Entailment or Contradiction item that holds none of its evidence is not a question:
whether such a part meets the rule is not what the annotation says. Documents are split into two
halves by the SHA-256 of their id (`half` A or B): calibration reads A, the measurement B, both
development and reported as such.
"""
import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "benchmark" / "adapters", ROOT / "benchmark" / "adapters" / "contractnli"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import auditor_questions  # noqa: E402
import convention_parser  # noqa: E402
import pairing_map  # noqa: E402

SCHEMA = "auditor-rule-check-questions-v1"
SEED = "20261108"
PER_CLASS = {"met": 300, "not_met": 300, "cannot be settled": 300}
# The adapter's own gold values (contractnli/adapter.py GOLD_VALUES), as rule-check answers.
GOLD = {"entailment": "met", "contradiction": "not_met", "not mentioned": "cannot be settled"}


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _adapter():
    import adapter
    return adapter


def rule_texts(rules):
    """{operator rule id: the rule's text as the pipeline's registry holds it}, read by the
    pipeline's own parser from the rules file the bundle writes."""
    from common import bundle
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "input" / "conventions"
        folder.mkdir(parents=True)
        (folder / bundle.RULES_NAME).write_text(bundle.render_rules(rules), encoding="utf-8", newline="\n")
        registry = convention_parser.parse_conventions(Path(tmp))
    out = {}
    for convention in registry.conventions:
        record = convention.as_dict()
        out[str(record.get("category") or "").upper()] = record.get("rule")
    return out


def questions_of(doc, question):
    """Every question of one adapter document: (unit_id, rule id, answer, user)."""
    from common import bundle
    text = bundle.render_document(doc["document_id"], [p["text"] for p in doc["parts"]])
    units = {u["unit_id"]: u for u in pairing_map.split_units(text, document_id=doc["document_id"])}
    ids = [bundle.unit_id(k) for k in range(1, len(doc["parts"]) + 1)]
    texts = rule_texts(doc["rules"])
    out = []
    for item in doc["items"]:
        rule = texts.get(item["rule_id"].upper())
        if rule is None:
            raise ValueError("a rule the parser did not read: " + item["rule_id"])
        evidence = {ids[k - 1] for k in item.get("evidence_parts") or []}
        gold = GOLD[item["gold"]]
        for uid in ids:
            if uid not in units:
                raise ValueError("a unit the splitter did not make: " + uid)
            if gold == "cannot be settled":
                label = gold
            elif uid in evidence:
                label = gold
            else:
                continue
            out.append((uid, item["rule_id"], label,
                        auditor_questions.render_rule_check(question, rule, units[uid]["text"])))
    return out


def build(dev_path, out, question=None):
    question = question or auditor_questions.load_config()["rule_check"]
    a = _adapter()
    data = a.read_source(dev_path)
    pool = []
    for doc in a.documents(data, {"side": "development"}):
        half = "A" if int(_sha(SEED + ":" + str(doc["source_document_id"]))[:8], 16) % 2 == 0 else "B"
        for uid, rid, label, user in questions_of(doc, question):
            pool.append({"question_id": _sha("%s|%s|%s" % (doc["document_id"], uid, rid))[:16], "document_id": doc["document_id"],
                         "unit_id": uid, "rule_id": rid, "answer": label, "half": half, "user": user,
                         "user_sha256": _sha(user)})
    chosen = []
    for label, n in PER_CLASS.items():
        rows = sorted((r for r in pool if r["answer"] == label), key=lambda r: _sha(SEED + r["question_id"]))
        chosen += rows[:n]
    chosen.sort(key=lambda r: r["question_id"])
    value = {"schema": SCHEMA, "status": "development, exposed: ContractNLI's development split (D-S62 item 1)",
             "form": "rule_check", "question_sha256": _question_sha(question), "source_sha256": _sha(Path(dev_path).read_text(encoding="utf-8")),
             "pool": dict(sorted(Counter(r["answer"] for r in pool).items())),
             "chosen": {h: dict(sorted(Counter(r["answer"] for r in chosen if r["half"] == h).items())) for h in ("A", "B")},
             "questions": chosen}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8", newline="\n")
    return value


def _question_sha(question):
    import build_auditor_training
    return build_auditor_training.question_digest(question)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--contractnli-dev", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    value = build(args.contractnli_dev, args.out)
    print(json.dumps({"pool": value["pool"], "chosen": value["chosen"]}))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "tools"))
    sys.exit(main())
