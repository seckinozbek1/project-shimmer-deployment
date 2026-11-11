"""Proofs of the judge's training rows and training pass, on fixtures only (T, D-S42 item 2).

    py -3.12 -X utf8 tools/judge_training_checks.py [--judge-source DIR]

No real model and no network. The builder runs on a planted set of every source; the training pass
runs on a tiny random Llama on the CPU with a stand-in for peft (a head left trainable), so what is
proved is the loop, the target, the schedule cut, the saved identities and the hand-over to the
questions, not 4-bit training, which only the first real run can show. Exit 1 on any failure.
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "benchmark" / "baselines")]
FAILED = []


PASSED = []


def proof(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    (PASSED if ok else FAILED).append(name)


def raises(fn, text=""):
    try:
        fn()
    except ValueError as exc:
        return text in str(exc)
    return False


def write_jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def plant(root):
    """Every source in its own layout, sized so each plan line can find rows on both sides. Labels
    are tied to length on purpose: contradictions short, the rest long, as a careless mix would be.
    MultiNLI's rows go to a JSON lines file read through the builder's seam, so no parquet reader
    is needed; `parquet_proofs` writes the same rows as parquet where one is installed."""
    raw = root / "raw"
    raw.mkdir(parents=True)
    n = 1500
    write_jsonl(raw / "multinli_planted.jsonl", [{"promptID": i, "pairID": "m%d" % i,
                                                 "premise": ("multi premise number %d stands here%s. " % (i, " in magazine" if i % 5 == 1 else ""))
                                                 * (1 if i % 3 == 2 else 1 + i % 6),
                                                 "hypothesis": "multi hypothesis %d" % i, "label": i % 3,
                                                 "genre": "fiction" if i % 5 == 0 else ("slate" if i % 5 == 1 else "travel")} for i in range(n)])
    write_jsonl(raw / "wanli_train.jsonl", [{"id": str(i), "pairID": "w%d" % i, "premise": "wanli premise %d." % i, "hypothesis": "wanli hyp %d" % i,
                                             "gold": ("entailment", "neutral", "contradiction")[i % 3]} for i in range(n)])
    labels = ("SUPPORTS", "REFUTES", "NOT ENOUGH INFO")
    vitamin = [{"unique_id": "v%d" % i, "case_id": "c%d" % i, "page": "Page_%d" % (i // 6), "label": labels[i % 3],
                "evidence": ("evidence sentence %d of a page. " % i) * (1 if i % 3 == 1 else 3), "claim": "claim %d" % i} for i in range(n)]
    vitamin.append({"unique_id": "vt", "case_id": "ct", "page": "Planted_Article", "label": "SUPPORTS", "evidence": "title hit", "claim": "title hit claim"})
    vitamin.append({"unique_id": "vs", "case_id": "cs", "page": "Elsewhere", "label": "REFUTES", "claim": "other",
                    "evidence": "one two three four five six seven eight nine ten from the planted development text"})
    vitamin.append({"unique_id": "vl", "case_id": "cl", "page": "Long", "label": "REFUTES", "claim": "long", "evidence": "word " * 5000})
    write_jsonl(raw / "vitaminc_train.jsonl", vitamin)
    tab = root / "tabfact"
    (tab / "csv").mkdir(parents=True)
    tables = {}
    for t in range(600):
        name = "t%d.csv" % t
        (tab / "csv" / name).write_text("team#points\nalpha%d#1\nbeta%d#2\ngamma%d#3\n" % (t, t, t), encoding="utf-8")
        tables[name] = [["alpha%d has 1 points" % t, "beta%d has 9 points" % t, "the total is 6", "gamma%d has 3 points" % t], [1, 0, 1, 1], "season %d" % t]
    (tab / "r1_training_all.json").write_text(json.dumps(tables), encoding="utf-8")
    (tab / "r2_training_all.json").write_text("{}", encoding="utf-8")
    (tab / "train_id.json").write_text(json.dumps(sorted(tables)), encoding="utf-8")
    dev = root / "dev"
    dev.mkdir()
    (dev / "contradoc.json").write_text(json.dumps({"pos": {"1": {"text": "= Planted Article =\n\none two three four five six seven eight nine ten"}}}), encoding="utf-8")
    (dev / "scitab.json").write_text(json.dumps([{"table_caption": "c", "claim": "x", "table_column_names": ["a"], "table_content_values": [["1"]], "label": "never read"}]),
                                     encoding="utf-8")


def planted_multinli(raw):
    return [json.loads(line) for line in (Path(raw) / "multinli_planted.jsonl").read_text(encoding="utf-8").splitlines()]


def parquet_proofs(source, root, args, count):
    """Where a parquet reader is installed: the real reader gives the planted rows, and a build
    through it writes the same bytes as one through the seam."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        print("SKIP builder parquet proofs: pyarrow not installed in this interpreter")
        return
    import build_judge_training as b
    rows = planted_multinli(root / "raw")
    pq.write_table(pa.table({k: [r[k] for r in rows] for k in b.MULTINLI_COLUMNS}), root / "raw" / "multinli_train.parquet")
    proof("the parquet reader gives the planted rows", b.multinli_parquet(root / "raw") == rows)
    own = b.source_pins(source, 1)
    b.build(*args, root / "p", source, count=count, forms=own[0], selector=own[1])
    proof("a build through the parquet reader writes the same bytes",
          all((root / "p" / n).read_bytes() == (root / "a" / n).read_bytes() for n in ("judge_dev_mix_train.jsonl", "judge_permissive_mix_train.jsonl")))


def rows_in(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def band_spread(rows):
    """The widest gap, over the answers of a form, between any cell's share and the form's own share,
    counting only cells of at least 30 rows, where one row cannot move a share far."""
    import build_judge_training as b
    worst = 0.
    for form in {r["form"] for r in rows}:
        mine = [r for r in rows if r["form"] == form]
        whole = {a: sum(r["answer"] == a for r in mine) / len(mine) for a in {r["answer"] for r in mine}}
        cells = {}
        for r in mine:
            cells.setdefault((r["padded"], b.band_of(r["tokens"])), []).append(r)
        for cell in cells.values():
            if len(cell) >= 30:
                worst = max(worst, *(abs(sum(r["answer"] == a for r in cell) / len(cell) - s) for a, s in whole.items()))
    return worst


SELECTOR_FIXTURE = """import pairing_map

LIMIT = 3


def helper(x):
    return pairing_map.norm(x)[:LIMIT]


def select(text, claim, config):
    return helper(text)


def tables(text):
    return [text]


def _rank(table, claim):
    return [1]


def _matched(score):
    return score > 0


def load_config():
    return {}


def finding(rule):
    return rule
"""


def selector_pin():
    """The pin moves with what a selection runs and with nothing else."""
    import build_judge_training as b
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        files = {"doc_judge": folder / "doc_judge.py", "cell_selection": folder / "cell_selection.py", "pairing_map": folder / "pairing_map.py"}
        files["doc_judge"].write_text("import cell_selection\n\n\ndef select_cells(text, claim):\n    return cell_selection.select(text, claim, None)\n\n\ndef unrelated():\n    return 1\n", encoding="utf-8")
        files["pairing_map"].write_text("def norm(x):\n    return x.lower()\n\n\ndef other():\n    return 2\n", encoding="utf-8")
        roots = [("doc_judge", "select_cells")] + [("cell_selection", n) for n in b.SELECTION_ROOTS]

        def digest(reach=b.reached):
            return b.sha("\n".join(sorted("%s.%s %s" % (m, n, d) for (m, n), d in reach(files, roots).items())))

        def write(text):
            files["cell_selection"].write_text(text, encoding="utf-8")
        write(SELECTOR_FIXTURE)
        first = digest()
        write(SELECTOR_FIXTURE.replace("def finding(rule):\n    return rule", "def finding(rule):\n    # a new comment\n    return [rule, 'changed']")
              + "\n\ndef review(units):\n    return units\n")
        proof("the pin ignores an edit to code no selection runs", digest() == first)
        write(SELECTOR_FIXTURE.replace("# nothing", ""))
        files["pairing_map"].write_text("def norm(x):\n    return x.lower()\n\n\ndef other():\n    return 3\n", encoding="utf-8")
        proof("the pin ignores another module's unreached code", digest() == first)
        write(SELECTOR_FIXTURE.replace("LIMIT = 3", "LIMIT = 4"))
        proof("the pin moves with a constant a selection reads", digest() != first)
        write(SELECTOR_FIXTURE)
        files["pairing_map"].write_text("def norm(x):\n    return x.upper()\n\n\ndef other():\n    return 3\n", encoding="utf-8")
        proof("the pin moves with the tokeniser a selection calls in another module", digest() != first)
        files["pairing_map"].write_text("def norm(x):\n    return x.lower()\n\n\ndef other():\n    return 2\n", encoding="utf-8")
        write(SELECTOR_FIXTURE.replace("return pairing_map.norm(x)[:LIMIT]", "return pairing_map.norm(x)[:LIMIT + 1]"))
        changed = digest()

        def roots_only(paths, roots_):
            trees = {m: b._definitions(b.ast.parse(Path(f).read_text(encoding="utf-8"))) for m, f in paths.items()}
            return {(m, n): b.ast.dump(trees[m][n]) for m, n in roots_ if n in trees[m]}
        write(SELECTOR_FIXTURE)
        base_only = digest(roots_only)
        write(SELECTOR_FIXTURE.replace("return pairing_map.norm(x)[:LIMIT]", "return pairing_map.norm(x)[:LIMIT + 1]"))
        proof("the pin moves with a helper a selection calls", changed != first)
        proof("neutralised: a pin of the roots alone misses that helper", digest(roots_only) == base_only)


def builder(source):
    import build_judge_training as b
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        plant(root)

        def count(text):
            return len(text.split())
        args = (root, root / "dev" / "contradoc.json", root / "dev" / "scitab.json")
        real_build = b.build
        own = b.source_pins(source, 1)

        def with_source_pins(*a, **k):
            # Each build is held to the source's own digests: which forms a lane ships is not under
            # proof here (the refusal proofs pass foreign ones).
            return real_build(*a, **dict({"multinli_rows": planted_multinli, "forms": own[0], "selector": own[1]}, **k))
        b.build = with_source_pins
        try:
            builder_proofs(b, source, root, args, count)
            attempt_two(b, source, root, args, count)
        finally:
            b.build = real_build
        parquet_proofs(source, root, args, count)


def plant_documents(root, n=2600):
    """C4-shaped documents: several sentences, two of which write one figure about one thing."""
    import gzip
    with gzip.open(root / "raw" / "c4_en_train_00000.json.gz", "wt", encoding="utf-8") as handle:
        for i in range(n):
            sentences = ["Station %d opened its doors to the public in spring." % i,
                         "The station %d served %d riders on its first day of service." % (i, 40 + i % 50),
                         "Officials said the station %d served %d riders on that first day." % (i, 40 + i % 50),
                         "Trains run every few minutes during the morning peak hours.",
                         "The building was designed by a local firm of architects.",
                         "A second entrance is planned for the northern side later."]
            handle.write(json.dumps({"url": "https://host%d.example/page%d" % (i % 37, i), "text": " ".join(sentences)}) + "\n")


def plant_tatqa(root, n=400):
    """TAT-QA-shaped tables: a table answer that writes a figure, and a question only the text answers."""
    entries = []
    for i in range(n):
        table = [["", "2019", "2018"], ["Revenue %d" % i, "%d.5" % (100 + i), "%d.0" % (90 + i)], ["Costs %d" % i, "%d" % (40 + i), "%d" % (30 + i)],
                 ["Margin %d" % i, "%d" % (5 + i % 9), "%d" % (4 + i % 9)]]
        entries.append({"table": {"uid": "t%d" % i, "table": table}, "paragraphs": [],
                         "questions": [{"uid": "q%da" % i, "question": "What was the revenue %d in 2019?" % i, "answer": "%d.5" % (100 + i),
                                        "answer_type": "span", "answer_from": "table", "scale": "million"},
                                       {"uid": "q%db" % i, "question": "What text question %d is answered by the text?" % i, "answer": "%d" % (7 + i),
                                        "answer_type": "span", "answer_from": "text", "scale": ""},
                                       {"uid": "q%dc" % i, "question": "Which items %d?" % i, "answer": ["a", "b"], "answer_type": "multi-span",
                                        "answer_from": "table", "scale": ""}]})
    (root / "raw" / "tatqa_dataset_train.json").write_text(json.dumps(entries), encoding="utf-8")


def attempt_two(b, source, root, args, count):
    """Attempt 2's rows: C's own passages and proposer, a figure changed against its twin."""
    plant_documents(root)
    real_share = b.C4_DOCUMENT_SHARE
    b.C4_DOCUMENT_SHARE = 1.0
    try:
        manifest = b.build(*args, root / "two", source, count=count, attempt=2)
        again = b.build(*args, root / "two_again", source, count=count, attempt=2)
    finally:
        b.C4_DOCUMENT_SHARE = real_share
    name = "judge_permissive_mix_train.jsonl"
    proof("attempt 2 builds byte-identically", (root / "two" / name).read_bytes() == (root / "two_again" / name).read_bytes())
    proof("attempt 2 builds the permissive mix alone", set(manifest["mixes"]) == {"permissive_mix"} and manifest["attempt"] == 2)
    rows = rows_in(root / "two" / name) + rows_in(root / "two" / "judge_permissive_mix_held_out.jsonl")
    sets = {r["set"] for r in rows}
    proof("attempt 2 rows hold the three document kinds", {"c4_alike", "c4_figure_changed", "c4_figure_twin"} <= sets)
    proof("attempt 2 has no padding and no share-alike row", not any(r["padded"] or r["share_alike"] for r in rows))
    changed = {(r["source_id"], r["order"]): r for r in rows if r["set"] == "c4_figure_changed"}
    twins = {(r["source_id"], r["order"]): r for r in rows if r["set"] == "c4_figure_twin"}
    import re as _re

    def figures(text):
        return _re.findall(r"\d+", text)
    paired = [k for k in changed if k in twins]
    proof("a changed pair and its twin differ in one figure only",
          bool(paired) and all(_re.sub(r"\d+", "#", changed[k]["user"]) == _re.sub(r"\d+", "#", twins[k]["user"])
                               and sum(x != y for x, y in zip(figures(changed[k]["user"]), figures(twins[k]["user"]))) == 1 for k in paired))
    proof("a changed pair is Yes and its twin No", all(changed[k]["surface"] == "Yes" and twins[k]["surface"] == "No" for k in paired))
    family = lambda r: (b.FAMILY.get(r["set"], r["set"]), r["group"])
    train, held = rows_in(root / "two" / name), rows_in(root / "two" / "judge_permissive_mix_held_out.jsonl")
    proof("a document's rows sit on one side", not ({family(r) for r in train} & {family(r) for r in held}))
    mix = manifest["domain_mix"]
    proof("the domain mix is counted from the data", mix["documents"] == 2600 and mix["hosts"] == 37 and mix["top_hosts"][0][1] >= 70)
    proof("a pair is two passages C's own splitter makes", all(r["user"].count("PASSAGE") == 2 for r in rows if r["set"].startswith("c4")))
    proof("attempt 2 keeps the slate genre", any("in magazine" in r["user"] for r in rows))
    claims = [r for r in rows if r["form"] == "claim"]
    if manifest.get("claim_tools_contract"):
        proof("with the tools form, a claim that writes a figure shows its FIGURES block",
              bool(claims) and all("\nFIGURES\n" in r["user"] for r in claims))
    else:
        proof("without the tools form, no claim shows a FIGURES block", bool(claims) and not any("FIGURES" in r["user"] for r in claims))
    real_share = b.C4_DOCUMENT_SHARE
    b.C4_DOCUMENT_SHARE = 1.0
    try:
        third = b.build(*args, root / "three", source, count=count, attempt=3)
    finally:
        b.C4_DOCUMENT_SHARE = real_share
    rows3 = rows_in(root / "three" / name) + rows_in(root / "three" / "judge_permissive_mix_held_out.jsonl")
    proof("attempt 2b leaves the slate genre out", rows3 and not any("in magazine" in r["user"] for r in rows3))
    claims2 = sum(r["form"] == "claim" for r in rows)
    claims3 = sum(r["form"] == "claim" for r in rows3)
    proof("attempt 2b cuts the claims to its plan", 0 < claims3 < claims2 and third["attempt"] == 3)
    plant_tatqa(root)
    b.C4_DOCUMENT_SHARE = 1.0
    try:
        fourth = b.build(*args, root / "four", source, count=count, attempt=4)
    finally:
        b.C4_DOCUMENT_SHARE = real_share
    rows4 = rows_in(root / "four" / name) + rows_in(root / "four" / "judge_permissive_mix_held_out.jsonl")
    tat = [r for r in rows4 if r["set"].startswith("tatqa")]
    proof("attempt 2c adds TAT-QA claims of all three answers",
          {r["answer"] for r in tat} == {"holds", "not met", "cannot be settled"} and fourth["attempt"] == 4)
    holds = {r["source_id"]: r for r in tat if r["set"] == "tatqa" and r["answer"] == "holds"}
    changed = {r["source_id"]: r for r in tat if r["set"] == "tatqa_changed"}
    both = [k for k in changed if k in holds]
    def claim_of(row):
        return row["user"].split("\nCLAIM\n", 1)[1].split("\n\n", 1)[0]
    proof("a changed TAT-QA answer differs from its held answer in one digit only",
          bool(both) and all(len(claim_of(holds[k])) == len(claim_of(changed[k]))
                             and sum(x != y for x, y in zip(claim_of(holds[k]), claim_of(changed[k]))) == 1 for k in both))
    proof("a text-only TAT-QA answer is cannot be settled", all(r["answer"] == "cannot be settled" for r in tat if "text question" in r["user"]))
    train4, held4 = rows_in(root / "four" / name), rows_in(root / "four" / "judge_permissive_mix_held_out.jsonl")
    proof("a TAT-QA table's claims sit on one side", not ({family(r) for r in train4} & {family(r) for r in held4}))


def builder_proofs(b, source, root, args, count):
    if True:
        first = b.build(*args, root / "a", source, count=count)
        b.build(*args, root / "b", source, count=count)
        names = ["judge_%s_%s.jsonl" % (m, s) for m in b.PLANS for s in ("train", "held_out")]
        for name in names:
            proof("two builds are byte-identical: " + name, (root / "a" / name).read_bytes() == (root / "b" / name).read_bytes())
        rows, held = rows_in(root / "a" / "judge_dev_mix_train.jsonl"), rows_in(root / "a" / "judge_dev_mix_held_out.jsonl")
        loose_rows, loose_held = rows_in(root / "a" / "judge_permissive_mix_train.jsonl"), rows_in(root / "a" / "judge_permissive_mix_held_out.jsonl")
        everything = rows + held
        proof("rows on both forms", {r["form"] for r in rows} == {"pair", "claim"})
        proof("a target is one of the three fixed surfaces", {r["surface"] for r in everything} <= {"Yes", "No", "Unclear"})
        proof("every answer of each form is present", {(r["form"], r["surface"]) for r in rows} == {(f, s) for f in ("pair", "claim") for s in ("Yes", "No", "Unclear")})
        both = {}
        for r in everything:
            if r["form"] == "pair":
                both.setdefault((r["set"], r["source_id"]), set()).add(r["order"])
        proof("each pair stands in both orders", all(v == {"ab", "ba"} for v in both.values()))
        family = lambda r: (b.FAMILY.get(r["set"], r["set"]), r["group"])
        proof("no group on both sides, derived sets with their source", not ({family(r) for r in rows} & {family(r) for r in held}))
        proof("a row is the question and its evidence, no example", all("Answer with one word." in r["user"] and ("PASSAGE A" in r["user"] or "CELLS" in r["user"]) for r in everything))
        text = " ".join(r["user"] for r in everything)
        proof("the title overlap is removed", "title hit" not in text and first["overlap"]["vitaminc"]["removed_title"] == 1)
        proof("the text overlap is removed", "planted development text" not in text and first["overlap"]["vitaminc"]["removed_text"] == 1)
        proof("no row over the cap", all(r["tokens"] <= b.MAX_TOKENS for r in everything))
        removed = [r for r in everything if r["set"] == "tabfact_rows_removed"]
        proof("a named row is gone from the cells of its Unclear", bool(removed) and all(r["surface"] == "Unclear" for r in removed)
              and not any(("| " + r["user"].split("CLAIM")[1].split()[0]) in r["user"].split("CLAIM")[0] for r in removed))
        proof("rows on padded and unpadded cells", {r["padded"] for r in rows if r["form"] == "pair"} == {True, False})
        proof("each padded cell holds every answer", all({a for a in c["shares"]} == {"contradicts", "does not", "cannot tell"}
              for k, c in first["mixes"]["dev_mix"]["train"]["band_shares"].items() if k.startswith("pair")))
        proof("label shares agree across length and padding", band_spread(rows) < .05)
        proof("share-alike rows are marked", all(r["share_alike"] for r in everything if r["set"].startswith("vitaminc"))
              and any(r["share_alike"] for r in everything if r["set"] == "multinli") and not any(r["share_alike"] for r in everything if r["set"] in ("wanli", "tabfact")))
        proof("the permissive mix holds no share-alike row", bool(loose_rows) and not any(r["share_alike"] for r in loose_rows + loose_held))
        proof("the permissive mix has no pair Unclear, as stated", not any(r["form"] == "pair" and r["surface"] == "Unclear" for r in loose_rows))
        proof("a changed form refuses", raises(lambda: b.build(*args, root / "c", source, count=count, forms="0" * 64), "forms are not the pinned"))
        proof("a changed selector refuses", raises(lambda: b.build(*args, root / "c", source, count=count, selector="0" * 64), "selector is not the pinned"))
        proof("the digests are in the manifest", (first["forms_sha256"], first["selector_sha256"]) == b.source_pins(source, 1))
        proof("each attempt has its own pins", set(b.FORMS_PINS) == set(b.SELECTOR_PINS) == set(b.ATTEMPT_PLANS)
              and b.FORMS_PINS[1] == b.FORMS_SHA256 and b.FORMS_PINS[2] == b.FORMS_PINS[3])
        # Neutralised: with the cut removed, the planted tie between label and length must show.
        real = b.stratify
        b.stratify = lambda rows_, seed, wanted: rows_
        try:
            b.build(*args, root / "n", source, count=count)
            caught = band_spread(rows_in(root / "n" / "judge_dev_mix_train.jsonl")) >= .05
        finally:
            b.stratify = real
        proof("neutralised: without stratify the label-length check fails", caught)
        real = b.FAMILY.copy()
        b.FAMILY.clear()
        try:
            b.build(*args, root / "f", source, count=count)
            caught = False
        except ValueError:
            caught = False
        finally:
            b.FAMILY.update(real)
        unsplit = [r for r in rows_in(root / "f" / "judge_dev_mix_train.jsonl")] if (root / "f" / "judge_dev_mix_train.jsonl").exists() else []
        unheld = rows_in(root / "f" / "judge_dev_mix_held_out.jsonl") if (root / "f" / "judge_dev_mix_held_out.jsonl").exists() else []
        proof("neutralised: without families a group crosses the split", bool({family(r) for r in unsplit} & {family(r) for r in unheld}))


class Tok:
    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        return "<u>" + messages[0]["content"] + "<a>"

    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": [ord(c) % 96 for c in text]}


def tiny_load(torch, saved):
    from transformers import LlamaConfig, LlamaForCausalLM

    class Stand(torch.nn.Module):
        def __init__(self):
            super().__init__()
            torch.manual_seed(7)
            self.inner = LlamaForCausalLM(LlamaConfig(vocab_size=96, hidden_size=16, intermediate_size=32, num_hidden_layers=1,
                                                      num_attention_heads=2, num_key_value_heads=2, attn_implementation="eager"))
            for name, p in self.inner.named_parameters():
                p.requires_grad = name.startswith("lm_head")

        def get_base_model(self):
            return self.inner

        def save_pretrained(self, directory, safe_serialization=True):
            saved.append(directory)
            Path(directory, "adapter_model.safetensors").write_bytes(self.inner.lm_head.weight.detach().numpy().tobytes())
            Path(directory, "adapter_config.json").write_text("{}", encoding="utf-8")
    return lambda training: (Tok(), Stand(), torch)


def rows_of(n, side):
    out = []
    for i in range(n):
        yes = i % 2 == 0
        out.append({"row_id": "%s%d" % (side, i), "form": "pair", "answer": "contradicts" if yes else "does not", "tokens": 10, "share_alike": False,
                    "user": ("%s same %d" % (side, i)) if yes else ("%s other thing %d" % (side, i))})
    return out


def fixture(j):
    rows, held = rows_of(64, "t"), rows_of(8, "h")
    forms = {"pair": {"answers": [{"label": "contradicts", "surface": "Yes"}, {"label": "does not", "surface": "No"}, {"label": "cannot tell", "surface": "Unclear"}]}}
    text = json.dumps({"config": {"choice": {"forms": forms}, "models": [{"group": "base"}]}, "prompt_count": 3,
                       "prompts": [{"prompt_id": "d00000%d" % i, "user_sha256": "s%d" % i} for i in (1, 2, 3)]}) + "\n"
    value = {"schema": j.SCHEMA, "training": dict(j.RECIPE, gradient_accumulation=2, warmup_updates=2, learning_rate=.05, max_train_seconds=1000.,
                                                  max_updates=32, model_id="m", revision="r"),
             "publication": j.PUBLICATION["dev_mix"], "checkpoints": {"half": .5, "full": 1.}, "question_passes": ["base", "half", "full"], "data_manifest": {"forms_sha256": j.forms_digest(forms)},
             "rows": rows, "rows_sha256": j._sha(j._canonical_rows(rows)), "held_out": held, "held_out_sha256": j._sha(j._canonical_rows(held)),
             "judge_prompts_text": text, "judge_prompts_sha256": j._sha(text)}
    return seal_it(j, value)


def seal_it(j, value):
    value["recipe_sha256"] = j.recipe_digest(value)
    return value


def training():
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    import torch
    import judge_train as j
    value = fixture(j)
    proof("a whole file passes", j.check(value) is value)
    for label, change, text in (("a changed row", lambda v: v["rows"][0].update(user="x"), "not the declared"),
                                ("an unknown answer", lambda v: (v["rows"][0].update(answer="maybe"), v.update(rows_sha256=j._sha(j._canonical_rows(v["rows"])))), "fixed answers"),
                                ("a prompt on both sides", lambda v: (v["held_out"][0].update(user=v["rows"][0]["user"]),
                                                                      v.update(held_out_sha256=j._sha(j._canonical_rows(v["held_out"])))), "both sides"),
                                ("no last checkpoint", lambda v: v["checkpoints"].update(full=.9), "the last and at most"),
                                ("five checkpoints", lambda v: v["checkpoints"].update(a=.1, b=.2, c=.3), "the last and at most"),
                                ("a pass of no checkpoint", lambda v: v["question_passes"].insert(0, "gone"), "question passes"),
                                ("passes not ending on the last", lambda v: v["question_passes"].reverse(), "question passes"),
                                ("a share-alike row in a publishable mix", lambda v: (v.update(publication=j.PUBLICATION["permissive_mix"]), v["rows"][0].update(share_alike=True),
                                                                                       v.update(rows_sha256=j._sha(j._canonical_rows(v["rows"])))), "publishable mix"),
                                ("a dev mix marked publishable", lambda v: v["publication"].update(publishable=True), "publication rule"),
                                ("more updates than rows", lambda v: v["training"].update(max_updates=33), "rows hold them"),
                                ("no time limit", lambda v: v["training"].update(max_train_seconds=0), "how long"),
                                ("rows built on other forms", lambda v: v["data_manifest"].update(forms_sha256="0" * 64), "other forms"),
                                ("a changed question", lambda v: v.update(judge_prompts_text=v["judge_prompts_text"] + " "), "not the declared")):
        broken = json.loads(json.dumps(value))
        change(broken)
        seal_it(j, broken)
        proof("refused: " + label, raises(lambda: j.check(broken), text))
    broken = json.loads(json.dumps(value))
    broken["training"]["seed"] = 8
    proof("refused: a changed seed under the old recipe digest", raises(lambda: j.check(broken), "recipe digest"))
    broken = json.loads(json.dumps(value))
    broken["checkpoints"]["half"] = .4
    proof("refused: a moved checkpoint under the old recipe digest", raises(lambda: j.check(broken), "recipe digest"))
    with tempfile.TemporaryDirectory() as folder:
        dev, loose = Path(folder) / "d.json", Path(folder) / "l.json"
        other = json.loads(json.dumps(value))
        other["publication"] = j.PUBLICATION["permissive_mix"]
        other["rows"] = rows_of(64, "x")
        other["rows_sha256"] = j._sha(j._canonical_rows(other["rows"]))
        seal_it(j, other)
        dev.write_text(json.dumps(value), encoding="utf-8")
        loose.write_text(json.dumps(other), encoding="utf-8")
        both = j.recipes_digest(dev, loose)
        proof("one digest covers both recipes", len(both) == 64)
        moved = json.loads(json.dumps(other))
        moved["rows"] = rows_of(64, "y")
        moved["rows_sha256"] = j._sha(j._canonical_rows(moved["rows"]))
        seal_it(j, moved)
        loose.write_text(json.dumps(moved), encoding="utf-8")
        proof("that digest moves with either file's rows", j.recipes_digest(dev, loose) != both)
        moved["training"]["seed"] = 8
        seal_it(j, moved)
        loose.write_text(json.dumps(moved), encoding="utf-8")
        proof("refused: two recipes differing beyond their rows", raises(lambda: j.recipes_digest(dev, loose), "more than their rows"))
        proof("refused: two files of one mix", raises(lambda: j.recipes_digest(dev, dev), "one dev_mix file"))
        loose.write_text(json.dumps(other), encoding="utf-8")
        # The fixture's questions are not a real doc_judge file: a stand-in reads their prompts.
        import types
        real_judge = j._doc_judge
        j._doc_judge = lambda: types.SimpleNamespace(load_prompts=lambda path: json.loads(Path(path).read_text(encoding="utf-8"))["prompts"])
        try:
            whole = j.session(dev, loose, Path(folder) / "s.json")
            session_count = len(j.load_prompts(Path(folder) / "s.json"))
        finally:
            j._doc_judge = real_judge
        proof("a session's digest is the two recipes' digest", whole["recipes_sha256"] == j.recipes_digest(dev, loose))
        proof("a session's prompt count is its last recipe's", session_count == 3)
        swapped = dict(whole, recipes=whole["recipes"][::-1])
        proof("refused: a session in the other order", raises(lambda: j.check(swapped), "dev_mix then permissive_mix"))
        bad = json.loads(json.dumps(whole))
        bad["recipes"][1]["rows"][0]["share_alike"] = True
        bad["recipes"][1]["rows_sha256"] = j._sha(j._canonical_rows(bad["recipes"][1]["rows"]))
        seal_it(j, bad["recipes"][1])
        bad["recipes_sha256"] = j.pair_digest(*bad["recipes"])
        proof("refused: a session whose permissive recipe holds a share-alike row", raises(lambda: j.check(bad), "publishable mix"))
        seen = []
        j.run(Path(folder) / "s.json", Path(folder) / "run", load=tiny_load(torch, []),
              judge=lambda path, out, **kw: seen.append(Path(out)) or {"prompts": 0}, reader=lambda adapter: adapter)
        base = Path(folder) / "run"
        proof("a session trains dev_mix under its own folder and permissive_mix at the top",
              (base / "dev_mix" / "training" / "result.json").is_file() and (base / "training" / "result.json").is_file()
              and seen == [base / "dev_mix" / "passes" / "base", base / "dev_mix" / "passes" / "half", base / "dev_mix",
                           base / "passes" / "base", base / "passes" / "half", base])
        dev_result = json.loads((base / "dev_mix" / "training" / "result.json").read_text(encoding="utf-8"))
        top_result = json.loads((base / "training" / "result.json").read_text(encoding="utf-8"))
        proof("each recipe's result names its own mix", dev_result["publication"]["mix"] == "dev_mix" and top_result["publication"]["mix"] == "permissive_mix")
    capped = json.loads(json.dumps(value))
    capped["training"]["max_updates"] = 10
    seal_it(j, capped)
    proof("a measured rate cuts the schedule", j.plan_after_measure(1000, [10.] * 20, 3000., 200.) == 300)
    proof("a fast machine keeps the plan", j.plan_after_measure(100, [1.] * 20, 3000., 20.) == 100)
    with tempfile.TemporaryDirectory() as folder:
        saved, seen = [], {}
        sealed = Path(folder) / "sealed.json"
        sealed.write_text(json.dumps(value), encoding="utf-8")

        def judge(path, out, paths, decision, max_new_tokens, reader_for):
            seen.setdefault("calls", []).append((Path(out), Path(path).read_bytes(), reader_for))
            return {"prompts": 0, "failures": {}, "seconds": {}}

        def reader(adapter):
            return adapter
        j.run(sealed, Path(folder) / "pass", load=tiny_load(torch, saved), judge=judge, reader=reader)
        out = Path(folder) / "pass" / "training"
        result = json.loads((out / "result.json").read_text(encoding="utf-8"))
        proof("every checkpoint is saved at its fraction", [a["group"] for a in result["adapters"]] == ["half", "full"]
              and [a["update"] for a in result["adapters"]] == [16, 32])
        proof("one pass over the rows", result["updates"] == 32 and result["rows_used"] == 64)
        with tempfile.TemporaryDirectory() as other_folder:
            short = j.train(capped, Path(other_folder) / "t", load=tiny_load(torch, []))
            proof("the stated updates bound the run", short["updates"] == 10)
        marked = json.loads((Path(result["adapters"][0]["path"]) / "PUBLICATION.json").read_text(encoding="utf-8"))
        proof("a dev_mix adapter says it is never published", marked["publishable"] is False and "never publish" in marked["rule"]
              and result["publication"]["mix"] == "dev_mix" and result["adapters"][0]["publication"] == marked)
        proof("the loss falls", result["last_32_mean_loss"] < result["first_loss"])
        reports = result["held_out"]
        proof("held out read before training and at each checkpoint", [r["update"] for r in reports] == [0, 16, 32])
        proof("held-out loss falls", reports[-1]["loss"] < reports[0]["loss"])
        proof("the evidence is on disk", all((out / n).is_file() for n in ("config.json", "losses.jsonl", "progress.json", "preflight.json", "result.json")))
        proof("each update is logged", len((out / "losses.jsonl").read_text(encoding="utf-8").splitlines()) == 32)
        digest = j._file_sha(Path(result["adapters"][1]["path"]) / "adapter_model.safetensors")
        proof("an identity is the file's digest", digest == result["adapters"][1]["weights_sha256"])
        proof("the two checkpoints differ", result["adapters"][0]["weights_sha256"] != result["adapters"][1]["weights_sha256"])
        calls = seen["calls"]
        proof("every pass asks the sealed bytes", [j._sha(c[1]) for c in calls] == [value["judge_prompts_sha256"]] * 3)
        proof("each pass has its own folder, the last the runner's", [c[0] for c in calls] == [Path(folder) / "pass" / "passes" / "base",
              Path(folder) / "pass" / "passes" / "half", Path(folder) / "pass"])
        proof("base has no adapter and each checkpoint its own", calls[0][2] is None
              and [c[2]["weights_sha256"] for c in calls[1:]] == [a["weights_sha256"] for a in result["adapters"]])
        sealed_ids = [(q["prompt_id"], q["user_sha256"]) for q in json.loads(calls[0][1])["prompts"]]
        proof("prompt ids and digests are the file's own in every pass", all([(q["prompt_id"], q["user_sha256"]) for q in json.loads(c[1])["prompts"]] == sealed_ids for c in calls))
        state = json.loads((out / "progress.json").read_text(encoding="utf-8"))
        proof("the progress file states the questions to come", state["phase"] == "questions" and state["questions_total"] == 9)
        # Neutralised: a logit read at the wrong position must stop the loss from falling on held-out rows.
        real = j.decision_logits

        def first_position(model, torch_, ids):
            return real(model, torch_, ids[:1])
        j.decision_logits = first_position
        try:
            flat = j.train(fixture(j), Path(folder) / "flat", load=tiny_load(torch, []))
        finally:
            j.decision_logits = real
        proof("neutralised: read before the question, held-out accuracy stays at chance", flat["held_out"][-1]["accuracy"] <= .625)
        proof("the real read beats that", reports[-1]["accuracy"] > flat["held_out"][-1]["accuracy"])
    return value


def groups_session():
    """A questions file of several groups: a trained group takes the adapter, earlier checkpoints
    ask its questions alone, the untrained groups run once in the last pass, ids never change."""
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    import torch
    import types
    import judge_train as j
    value = fixture(j)
    prompts = json.loads(value["judge_prompts_text"])
    prompts["config"]["models"] = [{"group": "choice_trained"}, {"group": "choice_direct"}, {"group": "judge_direct"}]
    prompts["prompts"] = [{"prompt_id": "d%06d" % n, "group": g, "user_sha256": "s%d" % n, "document_id": doc}
                          for n, (g, doc) in enumerate([("choice_trained", "halfA"), ("choice_trained", "fresh"), ("choice_direct", "fresh"),
                                                        ("judge_direct", "fresh")], 1)]
    prompts["prompt_count"] = 4
    value["judge_prompts_text"] = json.dumps(prompts) + "\n"
    value["judge_prompts_sha256"] = j._sha(value["judge_prompts_text"])
    value["question_passes"] = ["half", "full"]
    value["trained_groups"] = ["choice_trained"]
    seal_it(j, value)
    proof("a several-group file with its trained group passes", j.check(value) is value)
    bad = json.loads(json.dumps(value))
    bad["trained_groups"] = ["gone"]
    seal_it(j, bad)
    proof("refused: a trained group the questions lack", raises(lambda: j.check(bad), "trained groups"))
    legacy = json.loads(json.dumps(value))
    del legacy["trained_groups"]
    seal_it(j, legacy)
    proof("refused: several groups with no trained group named (attempt 1's rule)", raises(lambda: j.check(legacy), "one model group"))
    seen = []
    stand = types.SimpleNamespace(_sha=j._sha, _canonical=lambda v: json.dumps(v, sort_keys=True))
    real = j._doc_judge
    j._doc_judge = lambda: stand
    try:
        with tempfile.TemporaryDirectory() as folder:
            j.run_recipe(value, Path(folder) / "o", paths=("sdpa",), decision=None, max_new_tokens=None, load=tiny_load(torch, []),
                         judge=lambda path, out, **kw: seen.append((Path(out).name, json.loads(Path(path).read_text(encoding="utf-8")), kw["reader_for"])) or {},
                         reader=lambda adapter, groups=None: (adapter["weights_sha256"][:6], tuple(groups or ())))
    finally:
        j._doc_judge = real
    first, last = seen
    proof("an earlier checkpoint asks the trained group alone", [q["group"] for q in first[1]["prompts"]] == ["choice_trained", "choice_trained"]
          and first[1]["prompt_count"] == 2 and [g["group"] for g in first[1]["config"]["models"]] == ["choice_trained"])
    halved = json.loads(json.dumps(value))
    halved["earlier_pass_documents"] = ["halfA"]
    seal_it(j, halved)
    seen_half = []
    j._doc_judge = lambda: stand
    try:
        with tempfile.TemporaryDirectory() as folder:
            j.run_recipe(halved, Path(folder) / "o", paths=("sdpa",), decision=None, max_new_tokens=None, load=tiny_load(torch, []),
                         judge=lambda path, out, **kw: seen_half.append(json.loads(Path(path).read_text(encoding="utf-8"))) or {},
                         reader=lambda adapter, groups=None: None)
    finally:
        j._doc_judge = real
    proof("an earlier checkpoint named to half A is never asked the fresh set",
          [q["document_id"] for q in seen_half[0]["prompts"]] == ["halfA"] and seen_half[1] == prompts)
    stray = json.loads(json.dumps(value))
    stray["earlier_pass_documents"] = ["nowhere"]
    seal_it(j, stray)
    proof("refused: an earlier pass on a document the questions lack", raises(lambda: j.check(stray), "earlier pass"))
    proof("the last checkpoint asks the whole sealed file", last[1] == prompts)
    proof("ids and digests never change between passes", [(q["prompt_id"], q["user_sha256"]) for q in first[1]["prompts"]]
          == [(q["prompt_id"], q["user_sha256"]) for q in prompts["prompts"][:2]])
    proof("the adapter goes to the trained group only", first[2][1] == ("choice_trained",) and last[2][1] == ("choice_trained",))
    import types as _t
    stub = _t.ModuleType("bare_model")
    stub.resolve_reader = lambda agent, checkpoint, max_new_tokens: {"agent": agent}
    held, sys.modules["bare_model"] = sys.modules.get("bare_model"), stub
    try:
        reader_for = j.adapter_reader({"path": "p", "weights_sha256": "a", "config_sha256": "b"}, ["choice_trained"])
        trained = reader_for({"group": "choice_trained", "agent": "A", "checkpoint": "base"}, 1)
        untrained = reader_for({"group": "choice_direct", "agent": "A", "checkpoint": "base"}, 1)
    finally:
        if held is None:
            del sys.modules["bare_model"]
        else:
            sys.modules["bare_model"] = held
    proof("an untrained group of the same pass never reads the adapter", "adapter" in trained and "adapter" not in untrained)
    # Neutralised: attempt 1's reader, which gave every group the adapter, must fail that proof.
    real_reader = j.adapter_reader

    def every_group(adapter, groups=None):
        return real_reader(adapter, None)
    held, sys.modules["bare_model"] = sys.modules.get("bare_model"), stub
    try:
        j.adapter_reader = every_group
        leaked = j.adapter_reader({"path": "p", "weights_sha256": "a", "config_sha256": "b"}, ["choice_trained"])(
            {"group": "choice_direct", "agent": "A", "checkpoint": "base"}, 1)
    finally:
        j.adapter_reader = real_reader
        if held is None:
            del sys.modules["bare_model"]
        else:
            sys.modules["bare_model"] = held
    proof("neutralised: a reader giving every group the adapter is caught", "adapter" in leaked)


def questions():
    import judge_train as j
    import types
    stand = types.ModuleType("bare_model")
    stand.resolve_reader = lambda agent, checkpoint, max_new_tokens: {"agent": agent, "model_mode": "final"}
    held, sys.modules["bare_model"] = sys.modules.get("bare_model"), stand
    try:
        group = {"group": "g", "agent": "A", "checkpoint": "base"}
        adapter = {"path": "p", "weights_sha256": "a", "config_sha256": "b"}
        trained, base = j.adapter_reader(adapter)(group, 1), j.adapter_reader(None)(group, 1)
    finally:
        if held is None:
            del sys.modules["bare_model"]
        else:
            sys.modules["bare_model"] = held
    proof("a trained pass reads its adapter", trained["adapter"] == adapter)
    proof("the base pass never does", "adapter" not in base)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--judge-source", default=str(ROOT))
    args = parser.parse_args(argv)
    source = Path(args.judge_source).resolve()
    sys.path[:0] = [str(source), str(source / "benchmark" / "baselines"), str(source / "scripts")]
    # The judge source gives C's forms and selector; the trainer under proof is always this tree's.
    import importlib.util
    spec = importlib.util.spec_from_file_location("judge_train", ROOT / "benchmark" / "baselines" / "judge_train.py")
    sys.modules["judge_train"] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sys.modules["judge_train"])
    selector_pin()
    builder(source)
    training()
    questions()
    groups_session()
    print("judge training checks: %d proofs passed%s" % (len(PASSED), ", FAILED %d" % len(FAILED) if FAILED else ", all passed"))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
