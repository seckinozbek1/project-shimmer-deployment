"""The auditor backend's training rows (D-S57 item 3): public training sets in the rule check's form.

    py -3.12 -X utf8 tools/build_auditor_training.py --train-root <external/train of the T lane> \
        --contradoc-dev D --scitab-dev S --dev-text <folder> [--dev-text <folder> ...] \
        --tokenizer <Phi-3.5 tokenizer.json> --out <folder>

Each row is one user turn exactly as the pipeline sends the rule check (config/auditor_questions.json,
rendered by auditor_questions.render_rule_check, one user turn through the model's own chat template
in agent_wrapper.call_choice) and one fixed answer as its target: met (Yes), not_met (No) or
cannot be settled (Unclear). The rule is a statement the part must bear out; the part is the
evidence text. The question's digest (`question_sha256`, its template and answers) is in the
manifest, and a build on another question refuses at assembly.

THE MIX, stated before training (D-S55 item 3, D-S56 item 2), per answer (train side):

    met          MultiNLI entailment (other genres 1,600; fiction 400), WANLI entailment 1,200,
                 TabFact entailed 800
    not_met      MultiNLI contradiction (other genres 1,600; fiction 400), WANLI contradiction
                 1,200, TabFact refuted 800
    cannot be    MultiNLI neutral (other genres 1,600; fiction 400), WANLI neutral 2,000
    settled

Domains: government reports, an online magazine, telephone conversations, travel guides and fiction
(MultiNLI's five genres), web-like generated text revised by people (WANLI), and Wikipedia tables
(TabFact). No benchmark family of this loop is a source in any split (ContraDoc, SciTab,
ContractNLI, CUAD, FinDVer), no development, test or sealed item is a row (D-S62 item 5), and a
text sharing an 8-word run with a development text given is removed and counted.

Two mixes to the same budget (the operator's publication rule, D-281): `dev_mix` holds MultiNLI's
fiction rows, marked share-alike (its card names one work under CC BY-SA 3.0 that cannot be told
apart), and is measured only, never published; `permissive_mix` takes the same number from
MultiNLI's other genres in their place. Terms of use as read by the T lane on 2026-11-06
(docs/loop/stages/TRAIN_JUDGE_DATA.md on lane/train): MultiNLI the OANC's permissive terms (fiction
share-alike), WANLI CC BY 4.0, TabFact MIT (repository) and CC BY 4.0 (hub card).

Deterministic: every choice is an order of SHA-256 digests of (seed, set, id), the held-out side is
cut by group before anything is chosen, and two builds of the same inputs are byte-identical. A
row over MAX_TOKENS prompt tokens is dropped and counted.
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import auditor_questions  # noqa: E402
import build_judge_training as t  # noqa: E402  (T's readers, hashing and overlap, unchanged)

SCHEMA = "auditor-training-rows-v1"
FORM = "rule_check"
SEED = 7
MAX_TOKENS = 2048
CHAT_OVERHEAD_TOKENS = 8
HELD_OUT_SHARE = 0.05
TABLE_ROWS_MAX = 30
ANSWER = {"entailment": "met", "contradiction": "not_met", "neutral": "cannot be settled"}
# (set, source label, answer, train rows, share-alike side)
PLAN = (
    ("multinli", "entailment", "met", 1600, False), ("multinli", "entailment", "met", 400, True),
    ("wanli", "entailment", "met", 1200, False), ("tabfact", "entailed", "met", 800, False),
    ("multinli", "contradiction", "not_met", 1600, False), ("multinli", "contradiction", "not_met", 400, True),
    ("wanli", "contradiction", "not_met", 1200, False), ("tabfact", "refuted", "not_met", 800, False),
    ("multinli", "neutral", "cannot be settled", 1600, False), ("multinli", "neutral", "cannot be settled", 400, True),
    ("wanli", "neutral", "cannot be settled", 2000, False),
)
MIXES = ("dev_mix", "permissive_mix")


def question_digest(question):
    keep = {"template": question["decision"]["template"], "answers": question["decision"]["answers"]}
    return t.sha(json.dumps(keep, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def held_out(name, group):
    return t.share_of(SEED, "split", name, group) < HELD_OUT_SHARE


class DevOverlap(t.Overlap):
    """T's overlap (ContraDoc's and SciTab's development texts) and the text of every file under
    each `--dev-text` folder (.md and .txt as written; .json by its string values named `text`)."""

    def __init__(self, contradoc_path, scitab_path, folders):
        super().__init__(contradoc_path, scitab_path)
        read = 0
        for folder in folders or ():
            for path in sorted(Path(folder).rglob("*")):
                if path.suffix in (".md", ".txt"):
                    self.shingles |= t.shingles(path.read_text(encoding="utf-8", errors="replace"))
                    read += 1
                elif path.suffix == ".json":
                    try:
                        value = json.loads(path.read_text(encoding="utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        continue
                    for text in _texts(value):
                        self.shingles |= t.shingles(text)
                    read += 1
        self.development["dev_text_files"] = read
        self.development["shingles"] = len(self.shingles)


def _texts(value):
    if isinstance(value, dict):
        for k, v in value.items():
            if k == "text" and isinstance(v, str):
                yield v
            else:
                yield from _texts(v)
    elif isinstance(value, list):
        for v in value:
            yield from _texts(v)


def markdown_table(caption, header, rows):
    """A table as the pipeline's units write one: its caption as a heading, then pipe rows."""
    def line(cells):
        return "| " + " | ".join(str(c).replace("|", "/").strip() for c in cells) + " |"
    body = [line(header), "|" + "---|" * len(header)] + [line(r) for r in rows]
    return "## " + str(caption).strip() + "\n\n" + "\n".join(body)


def read_sources(root, overlap, multinli_rows=t.multinli_parquet):
    """Every usable source row: {set, id, group, label, rule, part, share_alike}."""
    raw = Path(root) / "raw"
    out = []
    for row in multinli_rows(raw):
        label = t.MULTINLI_LABELS.get(row["label"])
        if label and overlap.keep("multinli", (row["premise"], row["hypothesis"])):
            out.append({"set": "multinli", "id": row["pairID"], "group": row["promptID"], "label": label,
                        "rule": row["hypothesis"], "part": row["premise"], "share_alike": row["genre"] == "fiction"})
    for row in t._jsonl(raw / "wanli_train.jsonl"):
        if row.get("gold") in ANSWER and overlap.keep("wanli", (row["premise"], row["hypothesis"])):
            out.append({"set": "wanli", "id": row["id"], "group": row["pairID"], "label": row["gold"],
                        "rule": row["hypothesis"], "part": row["premise"], "share_alike": False})
    folder = Path(root) / "tabfact"
    for table, (statements, labels, caption) in t._tabfact_tables(root):
        lines = (folder / "csv" / table).read_text(encoding="utf-8").splitlines()
        grid = [line.split("#") for line in lines if line.strip()]
        if len(grid) < 2 or len(grid) - 1 > TABLE_ROWS_MAX:
            continue
        part = markdown_table(caption, grid[0], grid[1:])
        if not overlap.keep("tabfact_table", (part,)):
            continue
        for i, (claim, label) in enumerate(zip(statements, labels)):
            if overlap.keep("tabfact", (claim,)):
                out.append({"set": "tabfact", "id": "%s:%d" % (table, i), "group": table,
                            "label": "entailed" if label == 1 else "refuted", "rule": claim, "part": part,
                            "share_alike": False})
    return out


def rows_for(sources, question, count, side, mix):
    """The rows of one side and mix, by the plan: per (set, label, share-alike), the lowest-ranked
    candidates. In permissive_mix a share-alike line takes the same number from the set's other rows."""
    taken, out = set(), []
    for name, label, answer, n, alike in PLAN:
        want = n if side == "train" else max(1, round(n * HELD_OUT_SHARE / (1 - HELD_OUT_SHARE)))
        use_alike = alike and mix == "dev_mix"
        pool = [r for r in sources if r["set"] == name and r["label"] == label
                and r["share_alike"] == use_alike and (side == "held_out") == held_out(name, r["group"])
                and (r["set"], r["id"]) not in taken]
        pool.sort(key=lambda r: t.rank(SEED, mix if alike else "", name, r["id"]))
        for r in pool:
            if want <= 0:
                break
            user = auditor_questions.render_rule_check(question, r["rule"], r["part"])
            tokens = count(user) + CHAT_OVERHEAD_TOKENS
            if tokens > MAX_TOKENS:
                continue
            taken.add((r["set"], r["id"]))
            out.append({"row_id": "%s:%s" % (r["set"], r["id"]), "form": FORM, "user": user, "answer": answer,
                        "share_alike": r["share_alike"], "tokens": tokens, "set": r["set"], "group": r["group"]})
            want -= 1
    out.sort(key=lambda r: t.rank(SEED, "order", side, r["row_id"]))
    return out


def summary(rows):
    return {"rows": len(rows), "by_answer": dict(sorted(Counter(r["answer"] for r in rows).items())),
            "by_set": dict(sorted(Counter(r["set"] for r in rows).items())),
            "share_alike": sum(r["share_alike"] for r in rows), "tokens": sum(r["tokens"] for r in rows),
            "max_tokens": max((r["tokens"] for r in rows), default=0)}


def write_rows(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
                    encoding="utf-8", newline="\n")


def tokenizer_count(path):
    from tokenizers import Tokenizer
    tok = Tokenizer.from_file(str(path))
    return lambda text: len(tok.encode(text, add_special_tokens=False).ids)


def build(train_root, contradoc_dev, scitab_dev, dev_texts, out, count, question=None, multinli_rows=t.multinli_parquet):
    question = question or auditor_questions.load_config()[FORM]
    overlap = DevOverlap(contradoc_dev, scitab_dev, dev_texts)
    sources = read_sources(train_root, overlap, multinli_rows)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": SCHEMA, "form": FORM, "question_sha256": question_digest(question), "seed": SEED,
                "plan": [list(p) for p in PLAN], "overlap": overlap.report(), "development": overlap.development,
                "sources_read": dict(sorted(Counter(s["set"] for s in sources).items())), "mixes": {}}
    for mix in MIXES:
        mix_rows = {side: rows_for(sources, question, count, side, mix) for side in ("train", "held_out")}
        if {r["row_id"] for r in mix_rows["train"]} & {r["row_id"] for r in mix_rows["held_out"]}:
            raise ValueError("a row sits on both sides")
        if mix == "permissive_mix" and any(r["share_alike"] for side in mix_rows.values() for r in side):
            raise ValueError("permissive_mix holds a share-alike row")
        for side, rows in mix_rows.items():
            write_rows(out / ("%s_%s.jsonl" % (mix, side)), rows)
        manifest["mixes"][mix] = {side: dict(summary(rows), sha256=t.sha((out / ("%s_%s.jsonl" % (mix, side))).read_bytes()))
                                  for side, rows in mix_rows.items()}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--train-root", required=True)
    parser.add_argument("--contradoc-dev", required=True)
    parser.add_argument("--scitab-dev", required=True)
    parser.add_argument("--dev-text", action="append", default=[])
    parser.add_argument("--tokenizer", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    manifest = build(args.train_root, args.contradoc_dev, args.scitab_dev, args.dev_text, args.out,
                     tokenizer_count(args.tokenizer))
    print(json.dumps({m: {s: v["rows"] for s, v in sides.items()} for m, sides in manifest["mixes"].items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
