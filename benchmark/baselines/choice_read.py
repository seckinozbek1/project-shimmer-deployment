"""The reading of the judging path (D-S41, D-S42 C and M): docs/loop/stages/C_BAR.md, in code.

Development, exposed. Reads saved replay passes of choice_judge.py's prompts, no model. The figures
are FIGURES below; a bar file names the inputs by digest and states the same figures, and a read
refuses anything else. Labels and gold come through tools/score_corpus.py alone. Two stages, by
construction:

  read-a   half A only: gold and reach per half (counts), the mass test, the threshold, the
           checkpoint. No half-B decision is opened.
  read-b   half B. Refused unless both trained mixes are given with their training provenance and
           the frozen recipe digest is theirs, recomputed from the recipe files by judge_train, or
           --base-alone reads the base alone, said so in the result. It recomputes half A from the
           passes and refuses any difference from read-a's file, and refuses when every candidate
           is closed. Half B is read once: a read is keyed on what half B is (its documents and
           items, the keys' contents and the B1 labels of its items), the file is fixed in code
           under the repository's root, held under a lock, and any earlier read of that half B
           refuses another, whatever the bar file is called, written as or spaced.

      py -3.12 benchmark/baselines/choice_read.py read-a --bar BAR --pass base=PROMPTS,RUN [--pass ...]
          --key K [--key ...] --b1 LABELS --source S --items G1 --out DIR
      py -3.12 benchmark/baselines/choice_read.py read-b ... --read-a RESULT
          (--frozen-recipe SHA256 --bar-b BAR_B --provenance dev_mix=RESULT_JSON --provenance permissive_mix=RESULT_JSON
           --recipe dev_mix=RECIPE_JSON --recipe permissive_mix=RECIPE_JSON
           --trained-on TEXT --benchmarks-in-training-data yes|no | --base-alone) [--cost-usd N]

      py -3.12 benchmark/baselines/choice_read.py bar --prompts P [--prompts ...] --key K [--key ...]
          --b1 LABELS --source S --items G1 --out BAR
      py -3.12 benchmark/baselines/choice_read.py bar-b --bar BAR --recipe SHA256 --steps dev_mix:N [...] --steps permissive_mix:N [...]
          --out BAR_B
      py -3.12 benchmark/baselines/choice_read.py split-report --bar BAR --prompts P [--prompts ...] --key K [--key ...]
          --b1 LABELS --source S --items G1 --out REPORT

split-report counts, per benchmark and half, the documents, the gold and the gold a proposed pair
can reach, through the scorer, from the bar's own inputs and no pass: it opens no reply, so it is
reported before anything is read. read-a reports the same counts.

`bar` and `bar-b` write those files from their inputs and never overwrite one, so neither is
assembled by hand. The keys are digested through doc_judge.keys_digest alone.

BAR_B is the second bar file, written before half B is opened: the first bar's digest, the recipe's
`recipe_sha256` and each trained candidate's `checkpoint_steps` fixed before training, one recipe
for both. read-b compares both with what it
is given, and carries the file's digest in the result and in the count of reads.

--pass is NAME[:STEPS]=PROMPTS,RUN, repeated for a second file of the same candidate. `base` is the
base model; any other name is trained, bound to `base` by prompt_id and user_sha256, and its
checkpoints differ by STEPS. A row's `source` says where its label came from: top_answer, threshold,
tie, refusal or failed. A tie or a failed call is never a label; an item with no prompt is ABSTAIN.

A prompt marked `order_control` asks the same question with its answer lines in another order, on
half A only. It enters no label, no threshold and no verdict: read-a reports how far the answers
moved, per form. read-a also reports ties, the readable share and the whole-document share, and a
candidate under the void lines there is `void`, with half B closed, before any of it is spent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _path in (str(ROOT / "scripts"), str(ROOT / "tools"), str(HERE), str(HERE.parent / "adapters")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import choice_decision as cd  # noqa: E402
import doc_judge  # noqa: E402
import judge_read  # noqa: E402
import pair_judge  # noqa: E402
import passage_pairs  # noqa: E402

BASE = "base"
DEV_MIX, PERMISSIVE_MIX = "dev_mix", "permissive_mix"     # the two trained candidates, read together
TRAINED = (DEV_MIX, PERMISSIVE_MIX)
MAX_CHECKPOINTS = 4          # the last and at most three earlier (C_BAR)
FLOAT32 = "torch.float32"
READS_FILE = "external/s05/P2A/choice_half_b_reads.jsonl"   # fixed in code, under the repository's own root
BENCHMARKS = {"contradoc": "pair", "scitab": "claim"}
ABSTAIN, FLAG, CLEAR, UNDECIDED = doc_judge.ABSTAIN, "FLAG", "CLEAR", "UNDECIDED"
TOP, THRESHOLD, TIE, REFUSAL, FAILED = "top_answer", "threshold", "tie", "refusal", "failed"
READ, COMPARATORS, REASONING = "read", ("judge_direct", "judge_reason"), "judge_reason"
RESULT_A, RESULT_B = "choice_read_a.json", "choice_read_b.json"
BAR_SCHEMA = "choice-bar-v1"
BAR_B_SCHEMA = "choice-bar-b-v1"
FIGURES = {"salt": "20261106:", "mass_floor": .5, "mass_share_at_most": .2,
           "thresholds": [.5, .6, .7, .8, .9, .95, .99, .999], "flagged_share_at_most": .8, "chance_at_most": .0125,
           "b1_flags_for_precision": 5, "contradoc_b1_precision": .75, "placed_at_least": 3, "document_readable_at_least": .95,
           "prompts_readable_at_least": .95, "whole_documents_at_least": .9, "sign_test_at_most": .0125,
           "clearly_worse_documents": 3, "clearly_worse_macro_f1": .05, "contradoc_b1_flags": 8}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def labels_digest(root):
    """One digest over every B1 label file, by its path under `root`."""
    root = Path(root)
    rows = sorted("%s %s" % (p.relative_to(root).as_posix(), _sha(p)) for p in root.rglob("*.json") if "_b1" in p.relative_to(root).parts[0])
    return doc_judge._sha("\n".join(rows))


def repository_root():
    """The repository's own root, the same from any of its worktrees: the parent of git's common
    folder. When git cannot name it a read is refused: a worktree's own file would count apart."""
    try:
        common = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                capture_output=True, text=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        common = None
    if common is None or common.returncode != 0 or not common.stdout.strip():
        raise ValueError("git cannot name the repository's common folder: half B's reads have nowhere fixed to be counted")
    return Path(common.stdout.strip()).parent


def reads_path():
    """Where every read of half B is counted: fixed in code, never an argument or a bar's to say."""
    return repository_root() / READS_FILE


def _content(path):
    """A JSON file's content, canonical, or None when there is none."""
    path = Path(path)
    if not path.is_file():
        return None
    return doc_judge._sha(json.dumps(json.loads(path.read_text(encoding="utf-8")), sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def half_b_key(ctx):
    """What a read of half B is a read of, by content: per benchmark its document and item ids, each
    of its documents' key by its content, and each B1 label of its items by its content. A bar
    written again, a file spaced otherwise or a stray file elsewhere is the same half B."""
    sc = doc_judge._score_corpus()
    value = {}
    for benchmark, (_, half) in ctx["halves"].items():
        items = {d: sorted(i["item_id"] for i in ctx["universe"][benchmark][d]) for d in sorted(half)}
        value[benchmark] = {"items": items, "keys": {d: sc.key_content_digest(ctx["by_key"][d]) for d in sorted(half)},
                            "b1": {"%s/%s/%s" % (g, d, i): _content(Path(ctx["b1"]) / (g + "_b1") / d / "labels" / (i + ".json"))
                                   for g in COMPARATORS for d in sorted(half) for i in items[d]}}
    return doc_judge._sha(json.dumps(value, sort_keys=True))


def bar_value(prompts, keys, b1_root, source, items_path):
    """The bar of these inputs: the code's figures and each input's digest."""
    universe(keys, items_path)
    return {"schema": BAR_SCHEMA, "figures": FIGURES, "prompts_sha256": sorted(_sha(p) for p in prompts),
            "keys_sha256": doc_judge.keys_digest(doc_judge._score_corpus(), keys), "b1_labels_sha256": labels_digest(b1_root),
            "source_sha256": _sha(source), "items_sha256": _sha(items_path)}


def write_once(path, value):
    if Path(path).exists():
        raise ValueError("this file already exists: a bar is written once")
    doc_judge._write_json(path, value)
    return value


def checked_steps(fixed):
    """Both trained mixes, each with one to MAX_CHECKPOINTS checkpoints, or ValueError."""
    if set(fixed) != set(TRAINED):
        raise ValueError("the second bar names both trained mixes, dev_mix and permissive_mix, and no other")
    if any(not 1 <= len(set(steps)) <= MAX_CHECKPOINTS for steps in fixed.values()):
        raise ValueError("a mix has one to %d checkpoints, the last and at most three earlier" % MAX_CHECKPOINTS)
    return fixed


def bar_b_value(bar_path, recipe, steps):
    """The second bar of a written bar: the recipe by its digest and, per trained candidate, the
    checkpoints fixed for it. `steps` is a list of NAME:N."""
    if not re.fullmatch(r"[0-9a-f]{64}", str(recipe)):
        raise ValueError("the frozen recipe is named by its SHA-256")
    fixed = {}
    for spec in steps or []:
        name, _, number = str(spec).partition(":")
        if not (name and number.isdigit()):
            raise ValueError("a checkpoint is NAME:N")
        fixed.setdefault(name, []).append(int(number))
    return {"schema": BAR_B_SCHEMA, "bar_sha256": _sha(bar_path), "recipe_sha256": recipe,
            "checkpoint_steps": {name: sorted(numbers) for name, numbers in sorted(checked_steps(fixed).items())}}


def open_bar(bar_path, passes, keys, b1_root, source, items_path):
    """The bar, or ValueError: the figures must be FIGURES and every input the one it names. A
    candidate other than the base is held to the base by binding, not by its file's digest."""
    bar = json.loads(Path(bar_path).read_text(encoding="utf-8"))
    if bar.get("schema") != BAR_SCHEMA or bar.get("figures") != FIGURES:
        raise ValueError("the bar states other figures than the code's")
    sc = doc_judge._score_corpus()
    named = {"keys_sha256": doc_judge.keys_digest(sc, keys), "b1_labels_sha256": labels_digest(b1_root),
             "source_sha256": _sha(source), "items_sha256": _sha(items_path)}
    for name, got in named.items():
        if bar.get(name) != got:
            raise ValueError("the bar names other inputs: " + name)
    if sorted(_sha(entry[0]) for entry in passes[BASE][0]["files"]) != sorted(bar.get("prompts_sha256") or []):
        raise ValueError("the bar names other inputs: prompts_sha256")
    return bar


def parse_passes(specs):
    """{name: [{steps, files: [(prompts, run)]}]} from NAME[:STEPS]=PROMPTS,RUN."""
    out = {}
    for spec in specs:
        head, _, tail = spec.partition("=")
        name, _, steps = head.partition(":")
        prompts, _, run = tail.partition(",")
        if not (name and prompts and run):
            raise ValueError("a pass is NAME[:STEPS]=PROMPTS,RUN")
        rows = out.setdefault(name, [])
        steps = int(steps) if steps else None
        entry = next((r for r in rows if r["steps"] == steps), None)
        if entry is None:
            entry = {"steps": steps, "files": []}
            rows.append(entry)
        entry["files"].append((prompts, run))
    if BASE not in out or len(out[BASE]) != 1:
        raise ValueError("one base candidate")
    return out


def pass_identity(name, prompts, measurement):
    """What a pass is: its files' digests and its models. The base has no adapter applied and a
    trained candidate has one, with its digest, or the pass is refused."""
    models = json.loads(Path(measurement).read_text(encoding="utf-8")).get("models") or {}
    if not models:
        raise ValueError("the pass names no model")
    for model in models.values():
        applied, digest = model.get("adapter_applied") is True, model.get("adapter_sha256")
        if name == BASE and (applied or digest):
            raise ValueError("the base pass had an adapter applied")
        if name != BASE and not (applied and re.fullmatch(r"[0-9a-f]{64}", str(digest))):
            raise ValueError("a trained pass has no adapter with a digest")
    return {"prompts_sha256": _sha(prompts), "measurement_sha256": _sha(measurement),
            "models": {g: {"model_id": m.get("model_id"), "adapter_sha256": m.get("adapter_sha256")} for g, m in sorted(models.items())}}


def load(name, entry):
    """{rows, controls, documents, forms, identity} of a candidate's passes. A row is a prompt with
    its decision, None for a failed call, and what the pass measured of it; `controls` are the
    order_control rows, kept apart so that nothing else can read them."""
    rows, controls, documents, forms, identity = [], [], {}, {}, []
    for prompts, run in entry["files"]:
        value, seen, records = pair_judge.finished_pass(prompts, run)
        identity.append(pass_identity(name, prompts, Path(run) / doc_judge.MEASUREMENT_FILE))
        documents.update(value["documents"])
        forms.update(value["config"]["choice"]["forms"])
        for p in value["prompts"]:
            if p.get("form") != doc_judge.CHOICE_FORM:
                continue
            row = seen.get(p["prompt_id"]) or {}
            record = records.get(row.get("call_id")) or {}
            kept = ({k: p.get(k) for k in ("prompt_id", "user_sha256", "choice", "benchmark", "document_id", "item_id", "rule_id", "pair", "order", "selection")}
                    | {"seconds": row.get("seconds"), "decision": record.get("decision") if record.get("backend_ok") else None})
            kept["undeclared_above_top"] = above_top(kept)
            (controls if p.get("order_control") else rows).append(kept)
    return {"rows": rows, "controls": controls, "documents": documents, "forms": forms, "identity": identity}


def bound(base_rows, rows):
    """A trained pass is read beside the base only on the same questions."""
    if {r["prompt_id"]: r["user_sha256"] for r in base_rows} != {r["prompt_id"]: r["user_sha256"] for r in rows}:
        raise ValueError("the pass does not bind to the base by prompt_id and user_sha256")


def within(rows, benchmark, documents):
    """The rows of this form on the universe's own items: a left-out claim's prompt counts nowhere."""
    items = {i["item_id"] for listed in documents.values() for i in listed}
    return [r for r in rows if r["choice"] == BENCHMARKS[benchmark] and r["document_id"] in documents and r["item_id"] in items]


def split(documents):
    """{benchmark: (half A, half B)} of documents {id: {benchmark, ...}}: the one split, for every
    use of it (choice_judge's order controls and decisions, the reader's halves)."""
    return {b: halves([d for d, doc in documents.items() if doc.get("benchmark") == b]) for b in BENCHMARKS}


def halves(document_ids):
    """(half A, half B): hash order under the salt, the lower half A, an odd one to A."""
    ordered = sorted(document_ids, key=lambda d: hashlib.sha256((FIGURES["salt"] + d).encode("utf-8")).hexdigest())
    cut = (len(ordered) + 1) // 2
    return set(ordered[:cut]), set(ordered[cut:])


def universe(keys, items_path):
    """{benchmark: {document: [item table rows]}} of the bar's items, and the left-out ids. The items
    file is the pinned one, and no key is given twice, by its path or by its document."""
    sc = doc_judge._score_corpus()
    if not doc_judge._pinned(items_path):
        raise ValueError("the items file is not the pinned one (doc_judge.BAR_ITEMS_SHA256)")
    if len({str(Path(k).resolve()) for k in keys}) != len(keys):
        raise ValueError("a key is given twice")
    seen_documents = set()
    listed = json.loads(Path(items_path).read_text(encoding="utf-8"))
    left_out = set(listed.get("left_out") or [])
    out = {b: {} for b in BENCHMARKS}
    by_key = {}
    for key in keys:
        table = sc.item_table(key)
        wanted = set(listed.get(table["benchmark"]) or [])
        mine = [i for i in table["items"] if i["item_id"] in wanted and i["item_id"] not in left_out]
        if table["document_id"] in seen_documents:
            raise ValueError("two keys name document " + table["document_id"])
        seen_documents.add(table["document_id"])
        if mine:
            out[table["benchmark"]][table["document_id"]] = mine
            by_key[table["document_id"]] = key
    return out, left_out, by_key


def state(row):
    decision = row["decision"]
    if decision is None:
        return FAILED
    return TIE if decision.get("why") == cd.TIE else READ


def answer_class(forms, kind, label):
    return next(a["class"] for a in forms[kind]["answers"] if a["label"] == label)


def read_at(row, forms, threshold):
    """(class of the top answer, whether it stands at `threshold`) of a call that was read."""
    made = cd.settle(row["decision"], threshold)
    return answer_class(forms, row["choice"], made["top"]), made["settled"]


def pair_flags(rows, forms, threshold):
    """(flagged pairs, pairs both orders call contradicts below the threshold, pair count, readable
    pair count) of one document's calls."""
    pairs = {}
    for r in rows:
        pairs.setdefault(tuple(r["pair"]), []).append(r)
    flagged, below, readable = set(), set(), 0
    for pair, calls in pairs.items():
        if len(calls) != 2 or any(state(c) != READ for c in calls):
            continue
        readable += 1
        read = [read_at(c, forms, threshold) for c in calls]
        if all(cls == FLAG for cls, _ in read):
            (flagged if all(stands for _, stands in read) else below).add(pair)
    return flagged, below, len(pairs), readable


def read_document(document, item, rows, forms, threshold):
    """One ContraDoc document's row: FLAG on a flagged pair, CLEAR with enough pairs readable, else
    ABSTAIN. A tie or a failed call is no label of any kind."""
    flagged, below, total, readable = pair_flags(rows, forms, threshold)
    if flagged:
        cls, source = FLAG, TOP
    elif total and readable / total >= FIGURES["document_readable_at_least"]:
        cls, source = CLEAR, THRESHOLD if below else TOP
    else:
        cls = ABSTAIN
        source = TIE if any(state(r) == TIE for r in rows) else FAILED if rows else REFUSAL
    return {"document_id": document, "item_id": item, "cls": cls, "source": source, "pairs": sorted(flagged), "unreadable_pairs": total - readable}


def read_claim(document, item, row, forms, threshold):
    """One claim's row: its top answer, below the threshold cannot be settled, a tie or a failed
    call ABSTAIN, and a claim with no prompt (Python's selection refused it) ABSTAIN."""
    if row is None:
        return {"document_id": document, "item_id": item, "cls": ABSTAIN, "source": REFUSAL}
    if state(row) != READ:
        return {"document_id": document, "item_id": item, "cls": ABSTAIN, "source": state(row)}
    cls, stands = read_at(row, forms, threshold)
    return {"document_id": document, "item_id": item, "cls": cls if stands else UNDECIDED, "source": TOP if stands else THRESHOLD}


def view(benchmark, documents, rows, forms, threshold):
    """Every item of `documents` ({document: item rows}) read at `threshold`."""
    by_doc, by_item = {}, {}
    for r in rows:
        by_doc.setdefault(r["document_id"], []).append(r)
        by_item[r["item_id"]] = r
    out = []
    for document, items in sorted(documents.items()):
        if benchmark == "contradoc":
            out.append(read_document(document, items[0]["item_id"], by_doc.get(document, []), forms, threshold))
        else:
            out += [read_claim(document, i["item_id"], by_item.get(i["item_id"]), forms, threshold) for i in items]
    return out


# The bar's halves are G1's items: their declared class setting (D-380).
SETTINGS = judge_read.G1_SETTINGS


def score(rows, keys, out, left_out, tag):
    """The labels through the scorer: each row with its gold, and the figures of that view."""
    scored = judge_read.label_rows(rows, keys, out, left_out, tag)
    benchmarks = {r["benchmark"] for r in scored}
    if len(benchmarks) > 1:
        raise ValueError("one benchmark's rows at a time, not %s" % ", ".join(sorted(benchmarks)))
    return scored, figures(scored, judge_read.class_setting(SETTINGS, benchmarks.pop()) if benchmarks else None)


def figures(scored, setting):
    """One benchmark's figures, its macro-F1 and class F1 in the set's declared class setting (D-380)."""
    m = doc_judge.metrics(scored)
    from common import metrics as measures
    if scored and setting not in judge_read.CLASS_SETTINGS:
        raise ValueError("the class setting is declared per item set (D-380): give 2-class or 3-class, not %r" % (setting,))
    pairs = [(r["cls"], r["gold"]) for r in scored]
    flags = m["flag_tp"] + m["flag_fp"]
    return {"items": m["items"], "right": m["flag_tp"], "false": m["flag_fp"], "flagged": flags, "net": m["flag_tp"] - m["flag_fp"],
            "abstain": m["abstain"], "accuracy": m["accuracy"], "macro_f1": judge_read.macro_f1(scored, setting) if setting else None, "class_setting": setting,
            "precision": m["precision"] if flags else None, "chance_tail": round(doc_judge.chance_tail(m["strata"], m["flag_tp"]), 6),
            "class_f1": {c: measures.class_scores(pairs, c)["f1"] for c in judge_read.CLASS_SETTINGS[setting]} if setting else {},
            "labels_by_source": m["labels_by_source"], "correct_by_source": m["correct_by_source"]}


def b1_rows(group, documents, by_key, b1_root, left_out):
    """B1's own labels on `documents`, through the scorer."""
    sc = doc_judge._score_corpus()
    rows = []
    for document in sorted(documents):
        labelled = sc.benchmark_labels(by_key[document], Path(b1_root) / (group + "_b1") / document, arm="B1")
        rows += [{"document_id": document, "item_id": i["item_id"], "gold": i["gold_class"], "cls": i["b1_class"], "source": "b1_label",
                  "was_refused": False, "written_cls": i["b1_class"]} for i in labelled["items"] if i["item_id"] not in left_out]
    return rows


def measure(benchmark, row):
    return row["accuracy"] if benchmark == "contradoc" else row["macro_f1"]


def comparator(benchmark, documents, by_key, b1_root, left_out):
    """(the group to beat, every group): the higher measure, a tie taking the reasoning group, a
    group past D-241's abstain floor being no comparator. The first is None with none left."""
    setting = judge_read.class_setting(SETTINGS, benchmark)
    rows = {g: figures(b1_rows(g, documents, by_key, b1_root, left_out), setting) for g in COMPARATORS}
    fit = [g for g in COMPARATORS if rows[g]["abstain"] <= doc_judge.BAR_MAX_B1_ABSTAIN * rows[g]["items"]]
    if not fit:
        return None, rows
    best = max(fit, key=lambda g: (measure(benchmark, rows[g]), g == REASONING))
    return dict(rows[best], group=best), rows


def precision_gate(benchmark, b1):
    """Which precision item 4 holds a candidate to on this half."""
    if benchmark == "contradoc":
        return "contradoc_whole_sample"
    return "b1_on_the_half" if b1["flagged"] >= FIGURES["b1_flags_for_precision"] else "none: B1 raised under 5 flags on the half"


def precision_holds(benchmark, row, b1):
    """Item 4: precision at least B1's, and none false where B1 raises none. SciTab with under 5
    B1 flags on the half has no gate of precision, and precision_gate says so."""
    if row["precision"] is None:
        return False
    if benchmark == "contradoc":
        # B1's record here is the whole sample's, .75 on 8 flags: it raises false alarms, so the
        # rule of none where B1 raises none does not apply to ContraDoc.
        whole_false = FIGURES["contradoc_b1_flags"] * (1 - FIGURES["contradoc_b1_precision"])
        if whole_false == 0 and row["false"]:
            return False
        return row["precision"] >= FIGURES["contradoc_b1_precision"]
    if b1["false"] == 0 and row["false"]:
        return False
    return b1["flagged"] < FIGURES["b1_flags_for_precision"] or row["precision"] >= b1["precision"]


def flag_share_holds(row):
    return row["flagged"] <= FIGURES["flagged_share_at_most"] * row["items"]


def mass_share(rows):
    """The share of `rows` whose answers held under the floor of the mass; a failed call holds none."""
    under = sum(1 for r in rows if not r["decision"] or r["decision"]["declared_mass"] < FIGURES["mass_floor"])
    return round(under / len(rows), 6) if rows else 1.0


def _rank(benchmark, row, value):
    """A threshold's place: the bar's figure, net breaking a tie on ContraDoc, then the higher value."""
    return (row["accuracy"], row["net"], value) if benchmark == "contradoc" else (row["macro_f1"], value)


def ungated_threshold(benchmark, documents, rows, forms, keys, out, left_out, tag):
    """A closed base's threshold, beside a trained model: its best on half A with no gate applied,
    since .5 would flatter the trained model. A value that flags nothing is no choice while one
    flags something, and when none does the result says so. (threshold, flags nothing)."""
    table = [(value, score(view(benchmark, documents, rows, forms, value), keys, out, left_out, "%s_%s" % (tag, value))[1])
             for value in FIGURES["thresholds"]]
    flagging = [(value, row) for value, row in table if row["flagged"]]
    best = max(flagging or table, key=lambda pair: _rank(benchmark, pair[1], pair[0]))
    return best[0], not flagging


def choose_threshold(benchmark, documents, rows, forms, keys, out, left_out, b1, tag):
    """(threshold, its figures) by the bar, or (None, None) when no value qualifies."""
    best = None
    for value in FIGURES["thresholds"]:
        _, row = score(view(benchmark, documents, rows, forms, value), keys, out, left_out, "%s_%s" % (tag, value))
        if not (row["flagged"] >= 1 and flag_share_holds(row) and precision_holds(benchmark, row, b1)):
            continue
        rank = _rank(benchmark, row, value)
        if best is None or rank > best[0]:
            best = (rank, value, row)
    return (best[1], best[2]) if best else (None, None)


def reach(benchmark, documents, by_key, source, passes_rows, texts):
    """Gold on `documents`, and on ContraDoc the gold a proposed pair can reach: a pair holding the
    marked passage and its partner. Counts only."""
    sc = doc_judge._score_corpus()
    gold, reachable = 0, 0
    for document, items in documents.items():
        for item in items:
            if not sc.item_is_flag(by_key[document], item["item_id"]):
                continue
            gold += 1
            if benchmark == "contradoc":
                marks = sc.marked_passages(by_key[document], item["item_id"],
                                           [p["text"] for p in passage_pairs.passages(texts[document]["text"])], source)
                held = {tuple(r["pair"]) for r in passes_rows if r["document_id"] == document}
                reachable += any((a in marks["marked"] and b in marks["partner"]) or (a in marks["partner"] and b in marks["marked"])
                                 for a, b in held)
    return {"gold": gold, "reachable": reachable if benchmark == "contradoc" else None, "documents": len(documents)}


def _flag_share(row, forms):
    return sum(a["probability"] for a in row["decision"]["answers"] if answer_class(forms, row["choice"], a["label"]) == FLAG)


def order_shift(rows, controls, forms, benchmark, documents):
    """How far the answers moved with the answer lines in another order, on the calls read both
    ways: the top answer changed, and the mean move of the probability of the flagging answer. It
    is reported and decides nothing."""
    plain = {(r["item_id"], tuple(r["pair"] or ()), r["order"]): r for r in rows}
    compared, moved, shifts = 0, 0, []
    mine = within(controls, benchmark, documents)
    for control in mine:
        row = plain.get((control["item_id"], tuple(control["pair"] or ()), control["order"]))
        if row is None or state(row) != READ or state(control) != READ:
            continue
        compared += 1
        moved += row["decision"]["top"] != control["decision"]["top"]
        shifts.append(abs(_flag_share(row, forms) - _flag_share(control, forms)))
    return {"form": BENCHMARKS[benchmark], "controls": len(mine), "compared": compared, "top_answer_changed": moved,
            "top_answer_changed_share": round(moved / compared, 6) if compared else None,
            "mean_flag_probability_shift": round(statistics.mean(shifts), 6) if shifts else None}


def undeclared_tokens(rows, count=5):
    """The commonest likeliest tokens outside the answers, by id, with their mean probability."""
    seen = {}
    for r in rows:
        top = (r["decision"] or {}).get("undeclared_top")
        if top:
            seen.setdefault(top["token_id"], []).append(top["probability"])
    ranked = sorted(seen.items(), key=lambda pair: (-len(pair[1]), pair[0]))[:count]
    return [{"token_id": token, "calls": len(values), "mean_probability": round(statistics.mean(values), 6)} for token, values in ranked]


def split_counts(ctx, base_rows, documents):
    """{benchmark: {A, B}} of documents, gold and reach, through the scorer."""
    counts = {}
    for benchmark, (a, b) in ctx["halves"].items():
        known = ctx["universe"][benchmark]
        counts[benchmark] = {name: reach(benchmark, {d: known[d] for d in half}, ctx["by_key"], ctx["source"], base_rows, documents)
                             for name, half in (("A", a), ("B", b))}
    return counts


def split_report(bar_path, prompts, keys, b1, source, items_path, out):
    """The counts C_BAR reports before anything is read, from the bar's inputs and no pass."""
    if Path(out).exists():
        raise ValueError("this file already exists: a report is written once")
    passes = {BASE: [{"steps": None, "files": [(p, None) for p in prompts]}]}
    ctx = context(bar_path, passes, keys, b1, source, items_path, Path(out).parent)
    rows, documents = [], {}
    for path in prompts:
        value = doc_judge.read_file(path)
        documents.update(value["documents"])
        rows += [{"document_id": p["document_id"], "pair": p.get("pair")} for p in value["prompts"]
                 if p.get("form") == doc_judge.CHOICE_FORM and p.get("choice") == "pair" and not p.get("order_control")]
    report = {"schema": "choice-split-report-v1", "bar_sha256": ctx["bar_sha256"], "counts": split_counts(ctx, rows, documents),
              "half_a_documents": {b: sorted(a) for b, (a, _) in ctx["halves"].items()},
              "reads": "the bar's inputs only: no pass, no reply, no decision"}
    doc_judge._write_json(out, report)
    return report


def dtypes(rows):
    return {"logits_dtype": sorted({str(r["decision"].get("logits_dtype")) for r in rows if r["decision"]}),
            "model_logits_dtype": sorted({str(r["decision"].get("model_logits_dtype")) for r in rows if r["decision"]})}


def above_top(row):
    """Whether the likeliest token outside the answers is likelier than the top answer, both of the
    whole vocabulary: the model wanted another word more than any it was allowed."""
    decision = row["decision"]
    other = (decision or {}).get("undeclared_top")
    if not other:
        return False
    top = max(a["probability"] for a in decision["answers"]) * decision["declared_mass"]
    return other["probability"] > top


def _candidate_a(name, entry, base, benchmark, half, ctx):
    data = load(name, entry)
    rows, forms = data["rows"], data["forms"]
    if base is not None:
        bound(base["rows"] + base["controls"], rows + data["controls"])
    documents = {d: ctx["universe"][benchmark][d] for d in half}
    mine = within(rows, benchmark, documents)
    # C_BAR's mass test is on the prompts, every one of the candidate's file, controls among them.
    share = mass_share(rows + data["controls"])
    refused = refused_prompts(benchmark, mine, documents)
    void, readable, whole = is_void(mine, documents, refused)
    result = {"steps": entry["steps"], "identity": data["identity"], "prompts": len(mine), "mass_share_under_floor": share,
              "mass_share_under_floor_here": mass_share(mine), "undeclared_above_top": sum(above_top(r) for r in mine), **dtypes(mine),
              "read_b": ("refused: decisions not read from float32 logits" if any(r["decision"] and r["decision"].get("logits_dtype") != FLOAT32
                                                                                 for r in rows + data["controls"]) else "admitted: float32 logits"),
              "ties": sum(state(r) == TIE for r in mine), "failed": sum(state(r) == FAILED for r in mine), "refused_prompts": len(refused),
              "prompts_readable": readable, "documents_whole": whole, "undeclared_tokens": undeclared_tokens(mine),
              "order_control": order_shift(mine, data["controls"], forms, benchmark, documents)}

    def closed(**fields):
        """A closed candidate's row; the base keeps its ungated threshold for a trained model beside it."""
        if name == BASE:
            value, none = ungated_threshold(benchmark, documents, mine, forms, ctx["keys"], ctx["out"], ctx["left_out"],
                                            "%s_%s_ungated" % (name, benchmark))
            fields.update(ungated_threshold=value, flags_nothing=none)
        return dict(result, **fields)
    if share > FIGURES["mass_share_at_most"]:
        return closed(state="void", why="the fixed answers hold too little mass; half B stays closed")
    if void:
        return closed(state="void", why="half A is under the void lines; half B stays closed")
    b1, _ = comparator(benchmark, documents, ctx["by_key"], ctx["b1"], ctx["left_out"])
    if b1 is None:
        return closed(state="void", why="no B1 group is a comparator")
    result["precision_gate"] = precision_gate(benchmark, b1)
    value, row = choose_threshold(benchmark, documents, mine, forms, ctx["keys"], ctx["out"], ctx["left_out"], b1,
                                  "%s_%s_%s" % (name, entry["steps"], benchmark))
    if value is None:
        return closed(state="drop", why="no usable threshold; half B stays closed")
    return dict(result, state="ready", threshold=value, figures=row, b1=b1)


def _chosen(benchmark, rows):
    """The checkpoint: the base's one, or the best on half A, a tie taking the fewest steps."""
    ready = [r for r in rows if r["state"] == "ready"]
    if not ready:
        return rows[0]
    rank = lambda r: (measure(benchmark, r["figures"]), r["figures"]["net"] if benchmark == "contradoc" else 0, -(r["steps"] or 0))
    return max(ready, key=rank)


def context(bar_path, passes, keys, b1, source, items_path, out):
    bar = open_bar(bar_path, passes, keys, b1, source, items_path)
    known, left_out, by_key = universe(keys, items_path)
    return {"bar": bar, "bar_sha256": _sha(bar_path), "universe": known, "left_out": left_out, "by_key": by_key, "keys": keys, "b1": b1,
            "source": source, "out": Path(out), "halves": {b: halves(known[b]) for b in BENCHMARKS}}


def half_a(ctx, passes):
    """{name: {benchmark: the chosen checkpoint's row, with every checkpoint}} on half A."""
    base = load(BASE, passes[BASE][0])
    out = {}
    for name, entries in passes.items():
        out[name] = {}
        for benchmark, (a, _) in ctx["halves"].items():
            rows = [_candidate_a(name, e, None if name == BASE else base, benchmark, a, ctx) for e in entries]
            out[name][benchmark] = dict(_chosen(benchmark, rows), checkpoints=[{k: r.get(k) for k in HALF_A_FIELDS} for r in rows])
    return out


def read_a(bar_path, passes, keys, b1, source, items_path, out):
    ctx = context(bar_path, passes, keys, b1, source, items_path, out)
    if (ctx["out"] / RESULT_A).exists():
        raise ValueError("this folder already holds a result")
    base = load(BASE, passes[BASE][0])
    counts = split_counts(ctx, base["rows"], base["documents"])
    result = {"schema": "choice-read-a-v1", "half": "A", "bar_sha256": ctx["bar_sha256"], "counts": counts, "candidates": half_a(ctx, passes),
              "means": "half A only: the report carries no verdict"}
    doc_judge._write_json(ctx["out"] / RESULT_A, result)
    return result


def sign_test(wins, losses):
    """P(at least `wins` of the discordant items go one way, each way evens): one-sided, since the
    only claim it can carry is that training helped."""
    n = wins + losses
    return round(sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n, 6) if n else 1.0


def discordant(mine, other):
    """(items only `mine` is right on, items only `other` is right on)."""
    theirs = {r["item_id"]: r for r in other}
    wins = sum(1 for r in mine if r["cls"] == r["gold"] and theirs[r["item_id"]]["cls"] != r["gold"])
    losses = sum(1 for r in mine if r["cls"] != r["gold"] and theirs[r["item_id"]]["cls"] == r["gold"])
    return wins, losses


def refused_prompts(benchmark, rows, documents):
    """The bar's items with no prompt: a claim Python's selection refused is an unreadable prompt,
    though no pass holds a row of it. A document's pairs have no item each, so none here."""
    if benchmark != "scitab":
        return {}
    asked = {r["item_id"] for r in rows}
    return {i["item_id"]: d for d, items in documents.items() for i in items if i["item_id"] not in asked}


def is_void(rows, documents, refused=None):
    refused = refused or {}
    total = len(rows) + len(refused)
    readable = sum(state(r) == READ for r in rows) / total if total else 0
    by_doc = {}
    for r in rows:
        by_doc.setdefault(r["document_id"], []).append(state(r) == READ)
    for document in refused.values():
        by_doc.setdefault(document, []).append(False)
    whole = sum(1 for d in documents if by_doc.get(d) and all(by_doc[d])) / max(len(documents), 1)
    return readable < FIGURES["prompts_readable_at_least"] or whole < FIGURES["whole_documents_at_least"], round(readable, 6), round(whole, 6)


def above(benchmark, row, top_row, other, other_top=None):
    """Item 1 against `other`: strictly above it, on what the bar names."""
    if benchmark == "contradoc":
        return row["accuracy"] > other["accuracy"] and row["net"] >= other["net"]
    return row["macro_f1"] > other["macro_f1"] and top_row["macro_f1"] > (other_top or other)["macro_f1"]


def placed(view_rows, scored, by_key, source, texts, value_documents):
    """Item 5's figures on the half: the places, and the Python-only control on the same flags."""
    sc = doc_judge._score_corpus()
    gold = {r["document_id"]: r["gold"] == FLAG for r in scored}
    flags = {r["document_id"]: set(map(tuple, r.get("pairs") or [])) for r in view_rows}
    places, on_mark = {}, 0
    for r in view_rows:
        if gold[r["document_id"]]:
            marks = sc.marked_passages(by_key[r["document_id"]], r["item_id"],
                                       [p["text"] for p in passage_pairs.passages(texts[r["document_id"]]["text"])], source)
            places[r["document_id"]] = pair_judge.place(flags[r["document_id"]], marks)
            on_mark += sum(1 for pair in flags[r["document_id"]] if set(pair) & set(marks["marked"]))
    row = dict(pair_judge.counts(flags, gold, places), pairs_on_mark=on_mark)
    return row, pair_judge.control({"documents": value_documents}, gold, row["flagged"])


def tests(benchmark, row, top_row, b1, place_row=None, python=None):
    """Every item of the verdict."""
    out = {"above_b1": above(benchmark, row, top_row, b1), "flagged": flag_share_holds(row),
           "chance": row["chance_tail"] <= FIGURES["chance_at_most"], "precision": precision_holds(benchmark, row, b1)}
    if benchmark == "contradoc":
        out.update(placed=place_row["placed"] >= FIGURES["placed_at_least"],
                   placed_share=2 * place_row["placed"] >= place_row["flagged_with_two_marks"],
                   above_python=row["net"] > python["net"])
    return out


def _deciles(pairs):
    """{decile: [items, right]} of (confidence, right) pairs."""
    out = {}
    for confidence, right in pairs:
        row = out.setdefault(str(min(int(confidence * 10), 9)), [0, 0])
        row[0] += 1
        row[1] += bool(right)
    return dict(sorted(out.items()))


def reported(benchmark, rows, view_rows, scored, forms, threshold):
    """What the bar reports beside every verdict that a pass records."""
    read = [r for r in rows if state(r) == READ]
    masses = [r["decision"]["declared_mass"] for r in rows if r["decision"]]
    seconds = [r["seconds"] for r in rows if isinstance(r["seconds"], (int, float))]
    gold = {r["document_id"] if benchmark == "contradoc" else r["item_id"]: r["gold"] for r in scored}
    out = {"prompts": len(rows), "unreadable": len(rows) - len(read), "ties": sum(state(r) == TIE for r in rows),
           "failed": sum(state(r) == FAILED for r in rows), "declared_mass_median": statistics.median(masses) if masses else None,
           "declared_mass_share_under_floor": mass_share(rows), "logits_dtype": sorted({str(r["decision"].get("logits_dtype")) for r in rows if r["decision"]}),
           "model_logits_dtype": sorted({str(r["decision"].get("model_logits_dtype")) for r in rows if r["decision"]}), "undeclared_tokens": undeclared_tokens(rows),
           "undeclared_above_top": sum(above_top(r) for r in rows),
           "clear_with_an_unreadable_pair": sum(1 for r in view_rows if r["cls"] == CLEAR and r.get("unreadable_pairs")),
           "seconds_per_prompt": round(statistics.mean(seconds), 4) if seconds else None}
    if benchmark == "scitab":
        tops = [(r["decision"]["confidence"], read_at(r, forms, 0)[0] == gold.get(r["item_id"])) for r in read if r["item_id"] in gold]
        selected = {}
        for r in rows:
            name = (r.get("selection") or {}).get("selected_by")
            selected[str(name)] = selected.get(str(name), 0) + 1
        return dict(out, confidence_deciles=_deciles(tops), selected_by=selected)
    orders, tops, clear = {}, [], [0, 0]
    for r in read:
        orders.setdefault((r["document_id"], tuple(r["pair"])), []).append(r)
        if gold.get(r["document_id"]) == CLEAR:
            clear[0] += 1
            clear[1] += read_at(r, forms, 0)[0] == FLAG
    both = [c for c in orders.values() if len(c) == 2]
    best = {}
    for calls in both:
        low = min(next(a["probability"] for a in c["decision"]["answers"] if answer_class(forms, "pair", a["label"]) == FLAG) for c in calls)
        document = calls[0]["document_id"]
        best[document] = max(best.get(document, 0), low)
    flagged = [r for r in view_rows if r["cls"] == FLAG]
    return dict(out, orders_agree=round(sum(read_at(c[0], forms, 0)[0] == read_at(c[1], forms, 0)[0] for c in both) / max(len(both), 1), 6),
                flagged_pairs_per_flagged_document=round(sum(len(r["pairs"]) for r in flagged) / max(len(flagged), 1), 3),
                contradict_rate_on_clear=round(clear[1] / max(clear[0], 1), 6),
                confidence_deciles=_deciles((v, gold.get(d) == FLAG) for d, v in best.items() if d in gold))


def _candidate_b(name, entry, benchmark, half, threshold, ctx, documents_text):
    data = load(name, entry)
    forms = data["forms"]
    documents = {d: ctx["universe"][benchmark][d] for d in half}
    mine = within(data["rows"], benchmark, documents)
    view_rows = view(benchmark, documents, mine, forms, threshold)
    scored, row = score(view_rows, ctx["keys"], ctx["out"], ctx["left_out"], "%s_%s_B" % (name, benchmark))
    top_scored, top_row = score(view(benchmark, documents, mine, forms, 0), ctx["keys"], ctx["out"], ctx["left_out"], "%s_%s_B_top" % (name, benchmark))
    return {"rows": mine, "view": view_rows, "scored": scored, "figures": row, "top_figures": top_row, "top_scored": top_scored,
            "documents": documents, "forms": forms, "threshold": threshold}


def verdict(name, read, benchmark, ctx, base, documents_text):
    """The verdict on one candidate and benchmark, void first."""
    refused = refused_prompts(benchmark, read["rows"], read["documents"])
    void, readable, whole = is_void(read["rows"], read["documents"], refused)
    b1, b1_groups = comparator(benchmark, read["documents"], ctx["by_key"], ctx["b1"], ctx["left_out"])
    out = {"threshold": read["threshold"], "figures": read["figures"], "top_answer_macro_f1": read["top_figures"]["macro_f1"], "b1": b1,
           "b1_groups": b1_groups, "prompts_readable": readable, "documents_whole": whole,
           "refused_prompts": len(refused), "precision_gate": precision_gate(benchmark, b1) if b1 else None, "reported": reported(benchmark, read["rows"], read["view"], read["scored"], read["forms"], read["threshold"])}
    if void or b1 is None:
        return dict(out, result="void")
    place_row = python = None
    if benchmark == "contradoc":
        place_row, python = placed(read["view"], read["scored"], ctx["by_key"], ctx["source"], documents_text, documents_text)
        out.update(places=place_row, python_control=python)
    checks = tests(benchmark, read["figures"], read["top_figures"], b1, place_row, python)
    if name != BASE and base is not None:
        checks["above_base"] = above(benchmark, read["figures"], read["top_figures"], base["figures"], base["top_figures"])
        wins, losses = discordant(read["scored"], base["scored"])
        p = sign_test(wins, losses)
        out.update(against_base={"wins": wins, "losses": losses, "sign_test": p, "training_helped": p <= FIGURES["sign_test_at_most"] and wins > losses})
    return dict(out, tests=checks, result="keep" if all(checks.values()) else "drop",
                means="a keep says the candidate goes on; it never says the target is met")


def count_read(path, inputs, row, opened):
    """How many reads of half B of these inputs the file holds, this one appended first when it opens."""
    path = Path(path)
    if opened:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(row, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())), sort_keys=True) + "\n")
    return reads_of(path, inputs)


class ReadsLock:
    """An exclusive lock beside the reads file, from the check through the append: a second read
    started meanwhile is refused, never let through. The lock is never removed but by its holder."""

    def __init__(self, path):
        self.path = Path(str(path) + ".lock")

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise ValueError("the reads file is locked by another read: " + str(self.path)) from None
        os.write(handle, json.dumps({"pid": os.getpid(), "at": time.time()}).encode("utf-8"))
        os.close(handle)
        return self

    def __exit__(self, *exc):
        self.path.unlink()


def open_bar_b(path, bar_sha256, frozen_recipe, passes, recipes=None):
    """The second bar, or ValueError: of this bar, naming this recipe and these checkpoints."""
    if not path:
        raise ValueError("a frozen recipe needs the second bar file")
    bar_b = json.loads(Path(path).read_text(encoding="utf-8"))
    if bar_b.get("schema") != BAR_B_SCHEMA or bar_b.get("bar_sha256") != bar_sha256:
        raise ValueError("the second bar is not of this bar")
    if bar_b.get("recipe_sha256") != frozen_recipe:
        raise ValueError("the second bar names another recipe")
    fixed = checked_steps(bar_b.get("checkpoint_steps") or {})
    for name, entries in passes.items():
        if name != BASE and {entry["steps"] for entry in entries} != set(fixed.get(name) or []):
            raise ValueError("the second bar names other checkpoints")
    for name, trained in (recipes or {}).items():
        if set(fixed.get(name) or []) != set(trained["updates"]):
            raise ValueError("the second bar's checkpoints of %s are not the updates its training saved" % name)
    return _sha(path)


def right_count(scored):
    return sum(r["cls"] == r["gold"] for r in scored)


def clearly_worse(benchmark, permissive, dev):
    """The rule, written before any number: the permissive mix is clearly worse when it loses a
    `keep` dev_mix has, or stands lower on half B by at least 3 documents' accuracy on ContraDoc or
    .05 macro-F1 on SciTab. `permissive` and `dev` are {result, read}; a closed candidate has no read."""
    if dev["result"] == "keep" and permissive["result"] != "keep":
        return True
    if permissive["read"] is None or dev["read"] is None:
        return False
    if benchmark == "contradoc":
        return right_count(dev["read"]["scored"]) - right_count(permissive["read"]["scored"]) >= FIGURES["clearly_worse_documents"]
    return dev["read"]["figures"]["macro_f1"] - permissive["read"]["figures"]["macro_f1"] >= FIGURES["clearly_worse_macro_f1"]


def mix_comparison(benchmark, permissive, dev):
    """The permissive mix beside dev_mix on one benchmark: both results, the figures, the sign test
    between them where both were read, and the rule."""
    row = {"permissive_mix": permissive["result"], "dev_mix": dev["result"], "clearly_worse": clearly_worse(benchmark, permissive, dev)}
    if permissive["read"] is not None and dev["read"] is not None:
        wins, losses = discordant(permissive["read"]["scored"], dev["read"]["scored"])
        row.update(permissive_figures=permissive["read"]["figures"], dev_figures=dev["read"]["figures"], permissive_only_right=wins, dev_only_right=losses,
                   sign_test_permissive_above=sign_test(wins, losses), sign_test_dev_above=sign_test(losses, wins))
    return row


def reads_of(path, inputs):
    """The reads of half B of these inputs the file holds."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    return sum(1 for line in lines if line.strip() and json.loads(line).get("inputs_sha256") == inputs)


def judge_train():
    import importlib
    return importlib.import_module("judge_train")


def checked_provenance(passes, provenance, frozen_recipe, recipe_files):
    """{mix: {recipe, updates}} or ValueError. Both mixes and only they. Each recipe file is read by
    judge_train, which holds it to its own digest, and the frozen recipe is judge_train's pair digest
    of the two. Each training result.json is of its own mix and names that recipe; every adapter a
    pass applied is one it saved, and the pass's steps are that adapter's update."""
    if set(passes) != {BASE, *TRAINED}:
        raise ValueError("a frozen recipe reads both trained mixes, dev_mix and permissive_mix, beside the base")
    if set(provenance or {}) != set(TRAINED) or set(recipe_files or {}) != set(TRAINED):
        raise ValueError("each trained mix needs its training provenance (result.json) and its recipe file")
    trainer = judge_train()
    recipes = {name: trainer.read_file(recipe_files[name]) for name in TRAINED}
    if trainer.pair_digest(recipes[DEV_MIX], recipes[PERMISSIVE_MIX]) != frozen_recipe:
        raise ValueError("the frozen recipe is not the two mixes' recipe")
    out = {}
    for name in TRAINED:
        value = json.loads(Path(provenance[name]).read_text(encoding="utf-8"))
        if (value.get("publication") or {}).get("mix") != name or (recipes[name].get("publication") or {}).get("mix") != name:
            raise ValueError("the provenance of %s is not that mix's training result" % name)
        if value.get("recipe_sha256") != trainer.recipe_digest(recipes[name]):
            raise ValueError("the training result of %s names another recipe than its recipe file" % name)
        updates = {a.get("weights_sha256"): a.get("update") for a in value.get("adapters") or []}
        for entry in passes[name]:
            for identity in load(name, entry)["identity"]:
                for model in identity["models"].values():
                    if model["adapter_sha256"] not in updates:
                        raise ValueError("a pass of %s applied an adapter its training did not save" % name)
                    if entry["steps"] != updates.get(model["adapter_sha256"]):
                        raise ValueError("a pass of %s names other steps than its adapter's update" % name)
        out[name] = {"recipe": value["recipe_sha256"], "updates": sorted(set(updates.values()))}
    return out


def float32_only(passes):
    """Every decision of every pass read from float32 logits, or ValueError: a float16 head ties
    answers that differ."""
    for name, entries in passes.items():
        for entry in entries:
            data = load(name, entry)
            if any(r["decision"] and r["decision"].get("logits_dtype") != FLOAT32 for r in data["rows"] + data["controls"]):
                raise ValueError("a pass of %s holds decisions not read from float32 logits" % name)


HALF_A_FIELDS = ("steps", "state", "threshold", "identity", "ungated_threshold")


def same_half_a(first, again):
    """read-a's file against half A computed again from the passes: every candidate, benchmark and
    checkpoint the same in what read-b rests on."""
    pick = lambda cell: [{k: c.get(k) for k in HALF_A_FIELDS} for c in [cell] + list(cell.get("checkpoints") or [])]
    for name, cells in again.items():
        for benchmark, cell in cells.items():
            if pick(((first.get("candidates") or {}).get(name) or {}).get(benchmark) or {}) != pick(cell):
                raise ValueError("half A computed again differs from read-a's file: %s on %s" % (name, benchmark))


def same_passes(passes, first):
    """Every pass is the one half A read, by its steps and its digests, whatever else it claims."""
    for name, entries in passes.items():
        for entry in entries:
            identity = load(name, entry)["identity"]
            for cell in (first["candidates"].get(name) or {"none": {}}).values():
                if not any(c["steps"] == entry["steps"] and c["identity"] == identity for c in cell.get("checkpoints") or []):
                    raise ValueError("a pass differs from the one half A read")


def read_b(bar_path, read_a_path, passes, keys, b1, source, items_path, out, frozen_recipe=None, base_alone=False,
           trained_on=None, in_training_data=None, cost_usd=None, bar_b_path=None, provenance=None, recipe_files=None):
    if bool(frozen_recipe) == bool(base_alone):
        raise ValueError("half B needs T's frozen recipe digest or --base-alone, one of them")
    if frozen_recipe and not re.fullmatch(r"[0-9a-f]{64}", frozen_recipe):
        raise ValueError("the frozen recipe is named by its SHA-256")
    if base_alone and set(passes) != {BASE}:
        raise ValueError("--base-alone reads the base alone")
    ctx = context(bar_path, passes, keys, b1, source, items_path, out)
    if (ctx["out"] / RESULT_B).exists():
        raise ValueError("this folder already holds a result")
    first = json.loads(Path(read_a_path).read_text(encoding="utf-8"))
    if first.get("bar_sha256") != ctx["bar_sha256"]:
        raise ValueError("the half A result is of another bar")
    recipes = None
    if frozen_recipe:
        recipes = checked_provenance(passes, provenance, frozen_recipe, recipe_files)
        if not (trained_on and in_training_data in ("yes", "no")):
            raise ValueError("a trained candidate's result states what it was trained on and whether the benchmarks were in it")
    bar_b_sha256 = open_bar_b(bar_b_path, ctx["bar_sha256"], frozen_recipe, passes, recipes) if frozen_recipe else None
    inputs = half_b_key(ctx)
    with ReadsLock(reads_path()):
        if reads_of(reads_path(), inputs):
            raise ValueError("half B of these inputs has been read: it is read once")
        return _read_b_locked(ctx, first, read_a_path, passes, inputs, recipes, frozen_recipe, base_alone, trained_on, in_training_data,
                              cost_usd, bar_b_sha256)


def _read_b_locked(ctx, first, read_a_path, passes, inputs, recipes, frozen_recipe, base_alone, trained_on, in_training_data, cost_usd, bar_b_sha256):
    float32_only(passes)
    again = half_a(ctx, passes)
    same_half_a(first, again)
    first = dict(first, candidates=again)
    base = load(BASE, passes[BASE][0])
    documents_text = base["documents"]
    for name, entries in passes.items():
        for entry in entries:
            if name != BASE:
                data = load(name, entry)
                bound(base["rows"] + base["controls"], data["rows"] + data["controls"])
    same_passes(passes, first)
    # Half B is opened only for a candidate half A left ready; with none it is not spent. A closed
    # base beside a ready trained one has its figure computed for that one's item 1 (C_BAR).
    if not any(c["state"] == "ready" for cells in first["candidates"].values() for c in cells.values()):
        raise ValueError("every candidate is closed on half A: there is nothing to read, and half B is not spent")
    opened = True
    reads = count_read(reads_path(), inputs, {"inputs_sha256": inputs, "bar_sha256": ctx["bar_sha256"], "bar_b_sha256": bar_b_sha256,
                                               "candidates": sorted(passes), "frozen_recipe": frozen_recipe, "base_alone": bool(base_alone)}, opened)
    result = {"schema": "choice-read-b-v1", "half": "B", "bar_sha256": ctx["bar_sha256"], "inputs_sha256": inputs, "read_a_sha256": _sha(read_a_path),
              "half_b_reads": reads, "reads_path": str(reads_path()), "bar_b_sha256": bar_b_sha256, "frozen_recipe": frozen_recipe,
              "recipes": recipes, "base_alone": bool(base_alone),
              "base_alone_statement": "the base's half B is read alone: T did not run by the milestone" if base_alone else None,
              "trained_on": trained_on,
              "benchmarks_in_training_data": in_training_data == "yes" if trained_on else None, "cost_usd": cost_usd, "candidates": {}}
    for benchmark, (_, half) in ctx["halves"].items():
        base_read, trained = None, {}
        for name in sorted(passes, key=lambda n: n != BASE):
            chosen = first["candidates"][name][benchmark]
            entry = next((e for e in passes[name] if e["steps"] == chosen.get("steps") and load(name, e)["identity"] == chosen["identity"]), None)
            if entry is None:
                raise ValueError("the pass half A chose for %s is not given" % name)
            ready = chosen["state"] == "ready"
            # The base's figure is computed even when it is closed, for a trained model beside it,
            # at its best half A threshold with no gate applied.
            if ready or (name == BASE and set(passes) != {BASE}):
                value = chosen["threshold"] if ready else chosen["ungated_threshold"]
                read = _candidate_b(name, entry, benchmark, half, value, ctx, documents_text)
                if name == BASE:
                    base_read = read
            trained[name] = read if ready else None
            cell = result["candidates"].setdefault(name, {})
            cell[benchmark] = (verdict(name, read, benchmark, ctx, base_read, documents_text) if ready
                               # C_BAR: "the base's figure is computed even if the base is `void` or
                               # `drop`" for a trained model's item 1. That is no verdict on the base.
                               else {"result": chosen["state"], "why": chosen.get("why"), "half_b": "closed", "half_b_verdict": None,
                                     "note": ("a figure computed for the trained models' item 1 (C_BAR), no verdict on the base"
                                              if name == BASE and set(passes) != {BASE} else None),
                                     "figures_for_comparison": read["figures"] if name == BASE and set(passes) != {BASE} else None,
                                     "compared_at": read["threshold"] if name == BASE and set(passes) != {BASE} else None,
                                     "ungated_threshold": chosen.get("ungated_threshold"), "flags_nothing": chosen.get("flags_nothing")})
        if {DEV_MIX, PERMISSIVE_MIX} <= set(passes):
            mixes = {n: {"result": result["candidates"][n][benchmark]["result"], "read": trained[n]} for n in (PERMISSIVE_MIX, DEV_MIX)}
            result.setdefault("permissive_beside_dev", {})[benchmark] = mix_comparison(benchmark, mixes[PERMISSIVE_MIX], mixes[DEV_MIX])
    doc_judge._write_json(ctx["out"] / RESULT_B, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    w = sub.add_parser("bar")
    w.add_argument("--prompts", action="append", required=True)
    w.add_argument("--key", action="append", required=True)
    w.add_argument("--b1", required=True)
    w.add_argument("--source", required=True)
    w.add_argument("--items", required=True)
    w.add_argument("--out", required=True)
    w = sub.add_parser("bar-b")
    w.add_argument("--bar", required=True)
    w.add_argument("--recipe", required=True)
    w.add_argument("--steps", action="append")
    w.add_argument("--out", required=True)
    w = sub.add_parser("split-report")
    for flag in ("--bar", "--b1", "--source", "--items", "--out"):
        w.add_argument(flag, required=True)
    w.add_argument("--prompts", action="append", required=True)
    w.add_argument("--key", action="append", required=True)
    for name in ("read-a", "read-b"):
        p = sub.add_parser(name)
        p.add_argument("--bar", required=True)
        p.add_argument("--pass", dest="passes", action="append", required=True)
        p.add_argument("--key", action="append", required=True)
        p.add_argument("--b1", required=True)
        p.add_argument("--source", required=True)
        p.add_argument("--items", required=True)
        p.add_argument("--out", required=True)
        if name == "read-b":
            p.add_argument("--read-a", required=True)
            p.add_argument("--frozen-recipe")
            p.add_argument("--bar-b")
            p.add_argument("--base-alone", action="store_true")
            p.add_argument("--provenance", action="append", default=[])
            p.add_argument("--recipe", action="append", default=[])
            p.add_argument("--trained-on")
            p.add_argument("--benchmarks-in-training-data", choices=("yes", "no"))
            p.add_argument("--cost-usd", type=float)
    args = parser.parse_args(argv)
    if args.command == "bar":
        print(json.dumps({k: v for k, v in write_once(args.out, bar_value(args.prompts, args.key, args.b1, args.source, args.items)).items()
                          if k.endswith("sha256")}))
        return 0
    if args.command == "split-report":
        print(json.dumps(split_report(args.bar, args.prompts, args.key, args.b1, args.source, args.items, args.out)["counts"]))
        return 0
    if args.command == "bar-b":
        print(json.dumps(write_once(args.out, bar_b_value(args.bar, args.recipe, args.steps))))
        return 0
    passes = parse_passes(args.passes)
    if args.command == "read-a":
        result = read_a(args.bar, passes, args.key, args.b1, args.source, args.items, args.out)
        print(json.dumps({n: {b: c[b]["state"] for b in c} for n, c in result["candidates"].items()}))
    else:
        provenance = dict(spec.partition("=")[::2] for spec in args.provenance)
        recipe_files = dict(spec.partition("=")[::2] for spec in args.recipe)
        result = read_b(args.bar, args.read_a, passes, args.key, args.b1, args.source, args.items, args.out, args.frozen_recipe,
                        args.base_alone, args.trained_on, args.benchmarks_in_training_data, args.cost_usd, args.bar_b, provenance, recipe_files)
        print(json.dumps({n: {b: c[b]["result"] for b in c} for n, c in result["candidates"].items()}), "reads", result["half_b_reads"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
