"""D-S70 (D-322): the full system as shipped against B1 on the fresh ContraDoc set, read once.

Development, exposed. DRAFT for the checker's attack; nothing here has run on a real batch. One
confirmatory test, one benchmark, one comparator: B3, the pipeline on each of the 100 fresh bundles
(one sealed batch), labelled by the ContraDoc adapter's own B3 labeller through tools/score_corpus.py
(`benchmark_labels(..., arm="B3")`), against the better of B1's two groups on the same documents
(judge_direct and judge_reason, the bare base model in J1's form, from a replay pass of their 200
prompts alone, byte for byte the fresh prompts file's), by the exact one-sided sign test at .05.
The comparator rule is fixed here, before anything is read (C_BAR's: the higher accuracy, a tie to
the reasoning group, a group past D-241's abstain floor no comparator). The trained judge alone and
the untrained choice judge are not read here (descriptive only, D-S70); fresh_prompts.json stays
built and unread.

The set is opened once whatever reads it (fresh_once.py, D-326): the key is the set alone (its
source ids and each key's content), the count and the marker (a line in the tracked
docs/loop/FRESH_READS.md, searched in every tracked file of every ref) are fresh_once's, the groups
are pinned there, and the attempt is read from its tracked ledger. One document per group and the
power are fresh_test's. The trained judge's figure, when its bar and pass are given, is computed
inside the same opening, descriptive only.

  bar (no model)
      py -3.12 benchmark/baselines/system_test.py bar --batch SESSION --b1-prompts P --fresh-prompts F
          --key K [...] --ids F --items I --build B --parts P [...] --source S [...]
          --exposure-root R [...] --exposure-expected E [...] [--effect EFFECT.json] --out BAR
    SESSION is the sealed batch's session bundle (its batch/ folder holds one entry per fresh
    document); B the declared build (every bundle's rule carrying [compare: passages], D-331). The
    bar refuses: a set of other than 100 documents; a stated power that is not its effect's; a later
    attempt than the first; two fresh documents of one group; a fresh source id in any items, ids,
    groups, parts, assignment or prompts file under the exposure roots outside the expected files; a
    batch entry for no fresh document, or whose manifest is not its seal's or whose workload is not
    the declared build's bundle; B1 prompts that are not the pinned fresh prompts file's two groups,
    prompt for prompt; an effect without its label. It names every input by its bytes (keys by the
    scorer's key_digest), each entry's manifest, status and evidence, the set by its key, the groups
    and the comparator rule; open_bar recomputes every one.
  read (no model; the keys through the scorer)
      py -3.12 benchmark/baselines/system_test.py read --bar BAR --b1-run R [the bar's inputs] --out DIR
    Before the count, with fresh keys touched only through the scorer's digests: the bar and every
    field it fixes; every fresh document in a source file, every fresh item with a prompt in both B1
    groups, the B1 pass complete, of these prompts and on the base model with no adapter, every
    entry's status parsed and its run resolved; the power at the system's own labelled development
    effect, or undefined with its reason; the judge's part when given. Then the set is opened once:
    counted, and its key committed on the loop branch in that branch's own worktree (index clean, the
    precommit scan and guard_secrets passing). Only then are a fresh key's items and gold read and the
    result written and printed. The attempts ledger's row is the lead's to add, by hand.

The result: keep (shown), drop (not shown at this size) or void (fewer than 95 percent of the batch
entries passed execution integrity, a B1 group under 95 percent readable, or no comparator). Keep
needs the sign test, C_BAR's item 1 (accuracy above the comparator's, net at least its), precision
at least its, the chance tail at .05 and at most 80 percent flagged. An entry that did not pass
execution integrity is labelled as the adapter labels it (an incomplete run is no detection), and
counted against the void.
"""
from __future__ import annotations

import argparse
import contextlib
import inspect
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _path in (str(HERE.parents[1] / "scripts"), str(HERE.parents[1] / "tools"), str(HERE), str(HERE.parent / "adapters")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import choice_read as cr  # noqa: E402
import doc_judge  # noqa: E402
import either_test  # noqa: E402
import fresh_once  # noqa: E402
import fresh_test as ft  # noqa: E402
import pair_judge  # noqa: E402

BAR_SCHEMA = "system-bar-v1"
RESULT = "system_result.json"
BENCHMARK = "contradoc"
B1_GROUPS = either_test.B1_GROUPS
# D-S70: one test at .05 one-sided, set for the system's FIRST attempt at the fresh set; a later
# attempt has no alpha set here and is refused (round 1 item 7).
FIGURES = {"alpha_one_sided": .05, "chance_at_most": .05, "flagged_share_at_most": .8, "readable_at_least": .95,
           "entries_passed_at_least": .95, "documents": 100, "power": ft.FIGURES["power"], "power_effect": ft.FIGURES["power_effect"],
           "power_from": ft.FIGURES["power_from"] + "; a judge method's effect, not the system's: stated, not the system's power",
           "attempt": 1}
EXPOSURE_KINDS = ("items", "ids", "groups", "parts", "assignment", "prompts")
# The fresh prompts file B1's prompts come from, byte for byte (built 2026-11-08 20:27, D-316).
FRESH_PROMPTS_SHA256 = "b3059fef83f0138e25818120246aa21e1273c78d3ee448c249b28105685734b8"
# The rule heading every sealed entry must carry (D-S76 item 2, D-331).
DECLARATION = "compare: passages"
COMPARATOR_RULE = "C_BAR: the higher accuracy of judge_direct and judge_reason, a tie to judge_reason, a group past D-241's abstain floor no comparator"
EFFECT_LABELS = ("out-of-sample", ft.IN_SAMPLE)
BEFORE_COUNT_READERS = ("item_table", "key_content_digest", "key_digest")
# B1's base model, by the digest the replay records of it (J1 and C base: unsloth/phi-4-bnb-4bit).
B1_BASE_DIGESTS = {"unsloth/phi-4-bnb-4bit": "snapshot:098ea917f967c8811e6f579cc38872b2bf3d4bf4"}
# The lead's rulings on round 1 item 9 and round 2 gap 3: before the count a fresh key is read only
# by the scorer's item_table, key_content_digest and key_digest (BEFORE_COUNT_READERS); its labels,
# its score or any other read come after the count alone, and before_count() refuses them. Before it, the documents come from the items file and each key is found by its path in
# the declared build (<build>/<document>/answer_key.json), never by reading it.


def _sha(path):
    return cr._sha(path)


@contextlib.contextmanager
def before_count(keys):
    """Within it, the scorer reads a fresh key (one of `keys`) only for BEFORE_COUNT_READERS, the
    scorer's own functions by identity (their code objects, not their names): any other reader (its
    labels, its score, a direct read) is refused, naming itself."""
    sc = doc_judge._score_corpus()
    fresh = {str(Path(k).resolve()) for k in keys}
    real = sc._read_key_file
    allowed = {getattr(sc, name).__code__ for name in BEFORE_COUNT_READERS}

    def guarded(path, *args, **kwargs):
        caller = inspect.currentframe().f_back.f_code
        if str(Path(path).resolve()) in fresh and caller not in allowed:
            raise ValueError("a fresh key is read before the count by %s" % caller.co_name)
        return real(path, *args, **kwargs)
    sc._read_key_file = guarded
    try:
        yield
    finally:
        sc._read_key_file = real


def _lf_sha(path):
    """The SHA-256 of a text file with its line endings made LF, as the sealer records a workload member."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def entries(session):
    """{staged document id: entry folder} of a sealed batch's session bundle, from each entry's own
    seal (item `contradoc_<document id>`, arm B3). Any other arm or benchmark is refused."""
    import miss_diagnosis
    out = {}
    for folder in sorted(Path(session, "batch").iterdir()):
        if not folder.is_dir():
            continue
        item, arm = miss_diagnosis._entry_identity(folder)
        if arm != "B3" or not str(item or "").startswith(BENCHMARK + "_"):
            raise ValueError("a batch entry that is not a ContraDoc B3 entry: " + folder.name)
        document = str(item)[len(BENCHMARK) + 1:]
        if document in out:
            raise ValueError("two batch entries for one document: " + document)
        out[document] = folder
    return out


def _tree_digest(folder, keys_by_scorer=False):
    """A folder by its files' digests. With `keys_by_scorer`, an answer key is digested by the scorer's
    key_digest and never read here (round 3 item 3)."""
    folder = Path(folder)
    sc = doc_judge._score_corpus() if keys_by_scorer else None
    rows = []
    for p in sorted(folder.rglob("*")):
        if p.is_file():
            digest = sc.key_digest(p) if sc is not None and p.name == "answer_key.json" else _sha(p)
            rows.append("%s %s" % (p.relative_to(folder).as_posix(), digest))
    return doc_judge._sha("\n".join(rows))


def declared(bundle):
    """Whether the bundle's CONV-CDOC-01, as the convention parser reads its heading, compares
    passages (round 2 gap 5): the declaration on the heading, not words in the rule's text."""
    import convention_parser
    rules = [r for path in sorted((Path(bundle) / "conventions").glob("*.md")) for r in convention_parser._parse_text(path, [0])]
    return any(r.category == "conv-cdoc-01" and r.compare == DECLARATION.split(": ")[1] for r in rules)


def entry_digests(folders, build):
    """{document: {manifest, status, evidence}} of each entry: its execution manifest (held to the seal
    entry's digest, and its workload held to the declared build's bundle: the document and the rule
    file, which must carry DECLARATION), its FINAL_STATUS.json and its evidence."""
    out = {}
    for document, folder in folders.items():
        folder = Path(folder)
        seal = json.loads((folder / "seal_entry.json").read_text(encoding="utf-8"))
        manifest = folder / "execution_manifest.json"
        if not manifest.is_file() or _sha(manifest) != seal.get("execution_manifest_sha256"):
            raise ValueError("a batch entry's manifest is not the one its seal names: " + document)
        files = json.loads(manifest.read_text(encoding="utf-8"))["workload"]["files"]
        bundle = Path(build) / document
        if not declared(bundle):
            raise ValueError("the declared build's rule does not carry [%s]: %s" % (DECLARATION, document))
        expected = {p.relative_to(bundle).as_posix(): _lf_sha(p) for sub in ("context", "conventions") for p in (bundle / sub).rglob("*")
                    if p.is_file() and p.name != "_review_targets.json"}
        if files != expected:
            raise ValueError("a batch entry's workload is not the declared build's bundle: " + document)
        evidence = folder / "collected_evidence.tar.gz"
        out[document] = {"manifest": seal["execution_manifest_sha256"], "status": _sha(folder / "FINAL_STATUS.json"),
                         "evidence": _sha(evidence) if evidence.is_file() else _tree_digest(folder / "downloaded" / "evidence")}
    return out


def b1_questions(path, fresh_prompts):
    """B1's prompts, the fresh prompts file's two B1 groups prompt for prompt (D-316's build, pinned):
    [(prompt id, user digest)]. Refused for any other group, any prompt that differs, or another file."""
    if _sha(fresh_prompts) != FRESH_PROMPTS_SHA256:
        raise ValueError("the fresh prompts file is not the pinned one")
    value, fresh = doc_judge.read_file(path), doc_judge.read_file(fresh_prompts)
    if {p["group"] for p in value["prompts"]} != set(B1_GROUPS):
        raise ValueError("the B1 prompts file holds groups other than judge_direct and judge_reason")
    pinned = sorted((p for p in fresh["prompts"] if p["group"] in B1_GROUPS), key=lambda p: p["prompt_id"])
    if sorted(value["prompts"], key=lambda p: p["prompt_id"]) != pinned or value["config"] != fresh["config"]:
        raise ValueError("the B1 prompts are not the fresh prompts file's, prompt for prompt")
    return sorted((p["prompt_id"], p["user_sha256"]) for p in value["prompts"])


def b1_models(run, prompts):
    """B1's pass loaded the base model each group names, with no adapter."""
    groups = {g["group"]: g for g in doc_judge.read_file(prompts)["config"]["models"]}
    models = json.loads((Path(run) / doc_judge.MEASUREMENT_FILE).read_text(encoding="utf-8")).get("models") or {}
    if set(models) != set(B1_GROUPS):
        raise ValueError("the B1 pass did not load the two B1 groups alone")
    for group, model in models.items():
        if model.get("adapter_applied") or model.get("adapter_sha256"):
            raise ValueError("B1 group %s had an adapter applied" % group)
        named = groups[group].get("model_id")
        if named not in B1_BASE_DIGESTS:
            raise ValueError("B1 group %s names a model with no pinned weights: %r" % (group, named))
        if model.get("model_id") != named or model.get("checkpoint") not in (None, "base"):
            raise ValueError("B1 group %s did not load its base model" % group)
        if not model.get("digest") or model.get("digest") != B1_BASE_DIGESTS[named]:
            raise ValueError("B1 group %s loaded other weights than the pinned base" % group)


def exposure(roots, expected, fresh):
    """{file: fresh ids it names} of every items, ids, groups, parts, assignment or prompts file under
    `roots`, outside `expected`, by the file's name: a key (answer_key.json) and a benchmark source carry
    none of those names, so neither is read. The bar requires none."""
    found = {}
    wanted = ['"%s"' % d for d in fresh]
    expected = {str(Path(e).resolve()) for e in expected}
    for root in roots:
        for path in sorted(Path(root).rglob("*.json")):
            name = path.name.lower()
            if not path.is_file() or str(path.resolve()) in expected:
                continue
            if not any(kind in name for kind in EXPOSURE_KINDS):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            hits = sum(1 for w in wanted if w in text)
            if hits:
                found[str(path)] = hits
    return found


def input_digests(inputs):
    sc = doc_judge._score_corpus()
    out = {name: _sha(inputs[name]) for name in ("ids", "items", "b1_prompts", "fresh_prompts")}
    out["keys"] = doc_judge.keys_digest(sc, inputs["keys"])
    for name in ("parts", "sources"):
        out[name] = doc_judge._sha("\n".join(sorted(_sha(p) for p in inputs[name])))
    out["build"] = _tree_digest(inputs["build"], keys_by_scorer=True)
    out["effect"] = _sha(inputs["effect"]) if inputs.get("effect") else None
    out["judge_bar"] = _sha(inputs["judge"]["bar"]) if inputs.get("judge") else None
    return out


class _figures:
    """fresh_test's helpers read fresh_test.FIGURES; within this, they read this test's."""

    def __enter__(self):
        self.saved = ft.FIGURES
        ft.FIGURES = dict(ft.FIGURES, **{k: FIGURES[k] for k in ("alpha_one_sided", "documents", "power", "power_effect")})

    def __exit__(self, *exc):
        ft.FIGURES = self.saved


def first_attempt():
    """The ledger's attempt, refused unless it is the first: alpha is set for attempt 1 alone."""
    value = fresh_once.attempt()
    if value["number"] != FIGURES["attempt"]:
        raise ValueError("attempt %d: this test's alpha is set for attempt %d alone" % (value["number"], FIGURES["attempt"]))
    return value


def documents_before(inputs):
    """{document: [item rows]} from the items file, held to the ids file and to the keys by their
    paths in the declared build; no key is read."""
    rows = json.loads(Path(inputs["items"]).read_text(encoding="utf-8"))["items"]
    documents = {}
    for row in rows:
        documents.setdefault(row["document_id"], []).append({"item_id": row["item_id"], "document_id": row["document_id"],
                                                             "rule_id": row["rule_id"], "benchmark": row["benchmark"]})
    listed = json.loads(Path(inputs["ids"]).read_text(encoding="utf-8"))["documents"]
    if sorted({r["source_document_id"] for r in rows}) != sorted(listed):
        raise ValueError("the items are not the fresh set's documents")
    expected = sorted(str((Path(inputs["build"]) / d / "answer_key.json").resolve()) for d in documents)
    if sorted(str(Path(k).resolve()) for k in inputs["keys"]) != expected:
        raise ValueError("the keys are not the declared build's, one per fresh document")
    return documents


def bar_value(inputs):
    with before_count(inputs["keys"]):
        return _bar_value(inputs)


def _bar_value(inputs):
    documents = documents_before(inputs)
    if len(documents) != FIGURES["documents"]:
        raise ValueError("the test is sized for %d documents; this set has %d" % (FIGURES["documents"], len(documents)))
    with _figures():
        if FIGURES["power"] != ft.stated_power():
            raise ValueError("the stated power is not the power of the stated effect")
        groups = ft.one_per_group(inputs, documents)
    folders = entries(inputs["batch"])
    if set(folders) != set(documents):
        raise ValueError("the batch's entries are not the fresh documents")
    fresh = json.loads(Path(inputs["ids"]).read_text(encoding="utf-8"))["documents"]
    seen = exposure(inputs["exposure_roots"], inputs["exposure_expected"], fresh)
    if seen:
        raise ValueError("a fresh document is named outside the expected files: " + sorted(seen)[0])
    b1_questions(inputs["b1_prompts"], inputs["fresh_prompts"])
    development_effect(inputs.get("effect"))
    return {"schema": BAR_SCHEMA, "figures": FIGURES, "attempt": first_attempt(), "inputs": input_digests(inputs),
            "entries": entry_digests(folders, inputs["build"]), "set_key": fresh_once.set_key(inputs["ids"], inputs["keys"]),
            "groups": groups, "exposure": {"roots": len(inputs["exposure_roots"]), "unexpected": 0}, "comparator_rule": COMPARATOR_RULE}


def open_bar(bar_path, inputs):
    """The bar, every field it fixes recomputed: its figures, attempt, inputs by their bytes, entries,
    set key, groups and comparator rule."""
    bar = json.loads(Path(bar_path).read_text(encoding="utf-8"))
    if bar.get("schema") != BAR_SCHEMA or bar.get("figures") != FIGURES or bar.get("attempt") != first_attempt():
        raise ValueError("the bar states other figures than the code's")
    got = input_digests(inputs)
    for name, value in got.items():
        if (bar.get("inputs") or {}).get(name) != value:
            raise ValueError("the bar names other inputs: " + name)
    if entry_digests(entries(inputs["batch"]), inputs["build"]) != bar.get("entries"):
        raise ValueError("the bar names other batch entries")
    if bar.get("set_key") != fresh_once.set_key(inputs["ids"], inputs["keys"]):
        raise ValueError("the bar's set key is not this set's")
    documents = documents_before(inputs)
    with _figures():
        if bar.get("groups") != ft.one_per_group(inputs, documents):
            raise ValueError("the bar's groups are not this set's")
    if bar.get("comparator_rule") != COMPARATOR_RULE:
        raise ValueError("the bar states another comparator rule")
    return bar


def development_effect(path):
    """The system's own effect on read development material, as the operator's file states it:
    {wins, losses, documents, read_on, label}, the label "out-of-sample" or the in-sample label (round
    1 item 10), or None when no file is given."""
    if not path:
        return None
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if set(value) != {"wins", "losses", "documents", "read_on", "label"} or not all(type(value[k]) is int and value[k] >= 0 for k in ("wins", "losses", "documents")):
        raise ValueError("an effect file states wins, losses, documents, read_on and label")
    if value["label"] not in EFFECT_LABELS:
        raise ValueError("an effect's label is %s" % " or ".join(repr(x) for x in EFFECT_LABELS))
    return value


def power_before(effect):
    if effect is None:
        return {"power": None, "means": "undefined: no development read of the full system against B1 on ContraDoc was given", "stated": FIGURES["power"][str(FIGURES["documents"])]}
    with _figures():
        row = ft.power_at_effect(effect["wins"], effect["losses"], effect["documents"])
    return dict(row, read_on=effect["read_on"], label=effect["label"], stated=FIGURES["power"][str(FIGURES["documents"])])


# D-476: the scoring mode the system's B3 labels are read in, per benchmark. ContraDoc under
# v2_primary (None: a document the pair step raised nothing on is CLEAR); SciTab under detection_dev
# (a claim with no kept claim is ABSTAIN, and the cell step's decisions in the pairing map are read,
# D-472). A benchmark with no entry is refused: the mode is never guessed.
SCORING = {"contradoc": None, "scitab": "detection_dev"}


def scoring_of(benchmark):
    if benchmark not in SCORING:
        raise ValueError("no scoring mode is declared for the system's labels on %r" % (benchmark,))
    return SCORING[benchmark]


def system_rows(runs, by_key, benchmark=BENCHMARK):
    """Each document's B3 labels, by the adapter's own labeller through the scorer, in the mode
    declared for its benchmark (`SCORING`)."""
    sc = doc_judge._score_corpus()
    scoring = scoring_of(benchmark)
    rows = []
    for document, run in sorted(runs.items()):
        labelled = sc.benchmark_labels(by_key[document], run, arm="B3", scoring=scoring)
        rows += [{"document_id": document, "item_id": i["item_id"], "gold": i["gold_class"], "cls": i["b3_class"], "source": "b3_label",
                  "was_refused": False, "written_cls": i["b3_class"]}
                 for i in labelled["items"]]
    return rows


def every_item(rows, documents, keys, out):
    """Round 1 item 3: every fresh item has a row; one the labeller gave none is CLEAR (no detection),
    its gold read through the scorer, marked."""
    have = {r["item_id"] for r in rows}
    missing = [{"document_id": d, "item_id": i["item_id"], "cls": cr.CLEAR, "source": "no_system_label"}
               for d, items in documents.items() for i in items if i["item_id"] not in have]
    if not missing:
        return rows, 0
    filled = either_test.judge_read.label_rows(missing, keys, out, set(), "system_no_label")
    return rows + filled, len(filled)


def tests(system, other, wins, losses):
    precision = ft.precision_holds(system, other)
    return {"sign_test": cr.sign_test(wins, losses) <= FIGURES["alpha_one_sided"], "above_b1": cr.above(BENCHMARK, system, None, other),
            "precision": precision, "chance": system["chance_tail"] <= FIGURES["chance_at_most"],
            "flagged": system["flagged"] <= FIGURES["flagged_share_at_most"] * system["items"]}


def void_reasons(passed, b1_readable, group):
    reasons = []
    share = sum(passed.values()) / max(len(passed), 1)
    if share < FIGURES["entries_passed_at_least"]:
        reasons.append("batch entries passed execution integrity %.3f" % share)
    reasons += ["%s prompts readable %.3f" % (g, v) for g, v in sorted(b1_readable.items()) if v < FIGURES["readable_at_least"]]
    if group is None:
        reasons.append("no B1 group is a comparator")
    return reasons


def source_ids(paths):
    """The record ids of the benchmark's source files, ids only (a record's container is never kept)."""
    adapter = doc_judge._score_corpus()._adapter_for(BENCHMARK)
    return {str(r[adapter.DOCUMENT_ID_FIELD]) for path in paths for r in adapter.read_source(path)}


def validate_before(inputs, b1_run, workdir):
    """Everything the read needs, checked with no key opened, so a failure after the count cannot
    spend the set: every fresh document in a source file; every fresh item with a prompt in both B1
    groups; the B1 pass complete, of these prompts, on the base model; every entry's status parsed and
    its run resolved. Returns ({document: run folder}, {document: passed})."""
    import miss_diagnosis
    items = json.loads(Path(inputs["items"]).read_text(encoding="utf-8"))["items"]
    missing = sorted({r["source_document_id"] for r in items} - source_ids(inputs["sources"]))
    if missing:
        raise ValueError("a fresh document is in no source file: " + missing[0])
    value = doc_judge.read_file(inputs["b1_prompts"])
    for group in B1_GROUPS:
        asked = {p["item_id"] for p in value["prompts"] if p["group"] == group}
        lacking = sorted({r["item_id"] for r in items} - asked)
        if lacking:
            raise ValueError("a fresh item has no %s prompt: %s" % (group, lacking[0]))
    pair_judge.finished_pass(inputs["b1_prompts"], b1_run)
    b1_models(b1_run, inputs["b1_prompts"])
    runs, passed = {}, {}
    for document, folder in entries(inputs["batch"]).items():
        try:
            status = json.loads((Path(folder) / "FINAL_STATUS.json").read_text(encoding="utf-8"))
            assessment = status["report"]["Execution assessment"]
        except (OSError, ValueError, KeyError, TypeError):
            raise ValueError("a batch entry's status cannot be read: " + document) from None
        try:
            resolved = miss_diagnosis.resolve_run(str(folder), Path(workdir) / document)
        except Exception as exc:
            raise ValueError("a batch entry's run cannot be read: %s (%s)" % (document, type(exc).__name__)) from None
        if resolved["run_dir"] is None:
            raise ValueError("a batch entry has no run to read: %s (%s)" % (document, resolved["reason"]))
        runs[document], passed[document] = resolved["run_dir"], assessment == "passed"
    return runs, passed


def read(bar_path, b1_run, inputs, out, *, rows_of=system_rows, calibrate=None, effect=ft.half_a_effect):
    """The one read of the fresh set. Before the count, with fresh keys touched only through the
    scorer's digests: the bar and every field it fixes, every input the read needs, the system's power
    at its own development effect, and the judge's part when given. Then the set is opened once
    (fresh_once.opened: counted, the marker committed on the loop branch in its own worktree), and
    only then does the scorer read a fresh key's items and gold, and the result is written."""
    out = Path(out)
    if (out / RESULT).exists():
        raise ValueError("this folder already holds a result")
    with tempfile.TemporaryDirectory() as workdir:
        with before_count(inputs["keys"]):
            bar = open_bar(bar_path, inputs)
            runs, passed = validate_before(inputs, b1_run, workdir)
            judge = inputs.get("judge")
            judge_bar = None
            if judge:
                judge_bar, _ = ft.prepare_judge(judge["bar"], judge["run"], judge["inputs"], out / "judge", calibrate=calibrate, effect=effect)
                if judge_bar["set_key"] != bar["set_key"]:
                    raise ValueError("the judge's bar is of another set")
            before = dict(power_before(development_effect(inputs.get("effect"))), written="before the read")
            doc_judge._write_json(out / "before_read.json", before)
        key = bar["set_key"]
        with fresh_once.opened(key, {"bar_sha256": _sha(bar_path), "what": "system read (D-S70)"}):
            if doc_judge.keys_digest(doc_judge._score_corpus(), inputs["keys"]) != bar["inputs"]["keys"]:
                raise ValueError("a fresh key changed after the bar: no figure is read")
            result = _read(bar, b1_run, inputs, out, rows_of(runs, _by_key(inputs)), passed)
            if judge:
                result["judge_descriptive"] = ft.judge_figures(judge_bar, judge["run"], judge["inputs"], out / "judge")
    result.update(reads=cr.reads_of(fresh_once.reads_path(), key), set_key=key, power_before_read=before,
                  marker="committed on %s: %s" % (fresh_once.LOOP_REF, fresh_once.MARKER_FILE),
                  ledger="the attempts ledger's row for this key is the lead's to add, by hand")
    doc_judge._write_json(out / RESULT, result)
    return result


def _by_key(inputs):
    return either_test.universe(inputs["keys"], inputs["ids"], inputs["items"])[1]


def _read(bar, b1_run, inputs, out, rows, passed):
    keys = inputs["keys"]
    documents, by_key = either_test.universe(keys, inputs["ids"], inputs["items"])
    rows, unlabelled = every_item([r for r in rows if r["document_id"] in documents], documents, keys, out)
    system = cr.figures(rows)
    value, seen, records = pair_judge.finished_pass(inputs["b1_prompts"], b1_run)
    b1, b1_readable = {}, {}
    for group in B1_GROUPS:
        replies = either_test.b1_group_rows(value, seen, records, group)
        scored = either_test.judge_read.label_rows(replies, keys, out, set(), group + "_b1")
        b1[group] = {"scored": scored, "figures": cr.figures(scored)}
        b1_readable[group] = round(sum(not r["abstain"] for r in replies) / max(len(replies), 1), 6)
    group = either_test.comparator({g: v["figures"] for g, v in b1.items()})
    result = {"schema": "system-result-v1", "figures": FIGURES, "attempt": bar["attempt"], "documents": len(documents),
              "entries_passed": sum(passed.values()), "items_with_no_system_label": unlabelled, "system": system,
              "b1": {g: v["figures"] for g, v in b1.items()}, "b1_readable": b1_readable, "comparator": group,
              "means": "a keep says the system goes on; it never says the target is met"}
    reasons = void_reasons(passed, b1_readable, group)
    if reasons:
        return dict(result, result="void", void_reasons=reasons, reading="void: nothing is said of the system at this size")
    wins, losses = cr.discordant(rows, b1[group]["scored"])
    checks = tests(system, b1[group]["figures"], wins, losses)
    kept = all(checks.values())
    return dict(result, wins=wins, losses=losses, sign_test=cr.sign_test(wins, losses), tests=checks, result="keep" if kept else "drop",
                reading="shown" if kept else "not shown at this size")


def _inputs(args):
    return {"batch": args.batch, "b1_prompts": args.b1_prompts, "fresh_prompts": args.fresh_prompts, "keys": args.key, "ids": args.ids,
            "items": args.items, "build": args.build, "parts": args.parts, "sources": args.source, "exposure_roots": args.exposure_root,
            "exposure_expected": args.exposure_expected or [], "effect": args.effect, "judge": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("bar", "read"):
        p = sub.add_parser(name)
        for flag in ("--batch", "--b1-prompts", "--fresh-prompts", "--ids", "--items", "--build", "--out"):
            p.add_argument(flag, required=True)
        for flag in ("--key", "--parts", "--source", "--exposure-root"):
            p.add_argument(flag, action="append", required=True)
        p.add_argument("--exposure-expected", action="append")
        p.add_argument("--effect")
        if name == "read":
            p.add_argument("--bar", required=True)
            p.add_argument("--b1-run", required=True)
    args = parser.parse_args(argv)
    if args.command == "bar":
        print(json.dumps(cr.write_once(args.out, bar_value(_inputs(args)))))
    else:
        result = read(args.bar, args.b1_run, _inputs(args), args.out)
        print(json.dumps({k: result.get(k) for k in ("result", "reading", "comparator", "wins", "losses", "sign_test", "tests", "set_key", "marker")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
