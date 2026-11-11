"""Gate check 325, D-S70 (benchmark/baselines/system_test.py, a draft for the checker's attack). No model,
no real key, no real batch: fresh_test_checks' invented set built by the ContraDoc adapter, an invented
sealed batch (one entry per document, its seal and status), canned B1 replies and invented B3 rows, in
a temporary folder with its own git repository. Each proof is neutralise, fail, restore, pass.

1. the bar's figures and attempt are the code's (alpha neither lowered nor raised), the set's size and
   the stated power are checked; an edited set key, groups or comparator rule in a bar is refused, and
   a later attempt than the first is refused;
2. the batch's entries are the fresh documents, one each, ContraDoc B3 only;
3. B1's prompts are the pinned fresh prompts file's two groups, prompt for prompt, on the base model
   with no adapter; every entry's workload is the declared build's bundle with [compare: passages],
   and its status and evidence are fixed in the bar; every fresh item is labelled, CLEAR where the
   labeller gave none; the read commits its key on the loop branch, in that branch's own worktree
   (index clean, the scans passing), before any figure is written; no fresh key's items or gold are
   read before the count;
4. a fresh id named in an items, ids, groups, parts, assignment or prompts file outside the expected
   ones refuses the bar;
5. the set opens once (fresh_once): its key is the set alone, so a second bar with other B1 prompts
   and re-spaced inputs are refused; the read writes its key into the tracked marker file; a key in
   any tracked file of any ref refuses, and so does git that cannot answer; the attempt is the
   ledger's; everything the read needs is checked before the count (every fresh document in a
   source file, every fresh item with both B1 prompts), and the count comes before any fresh key;
   the judge's figure is computed inside the same opening, descriptive only;
7. the ContraDoc build adds CONV-CDOC-01's [compare: passages] only when asked (D-331), the parser
   reads it, and no other declaration is admitted; the SciTab build adds [compare: cells] only when
   asked (D-471), the rule then the claim alone, and neither build adds the other's declaration;
   the system's rows are labelled in the mode declared per benchmark (D-476: ContraDoc v2_primary,
   SciTab detection_dev), and a benchmark with none declared is refused; the gate scorer's system
   arm (gate_score.system_arm) is labelled in its own benchmark's mode and inside its set file; the
   cut is computed from the as-shipped rules, so under a token counter and limits a declared build's
   items, parts and keys are the as-shipped build's (D-478);
6. the comparator is C_BAR's, keep needs the sign test, item 1, precision, the chance tail and the
   flagged share; void under 95 percent of entries passed or a B1 group under 95 percent readable.
"""
import contextlib
import importlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "benchmark" / "baselines"), str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "adapters")):
    if path not in sys.path:
        sys.path.insert(0, path)

import fresh_once  # noqa: E402
import fresh_test_checks as ftc  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

st = importlib.import_module("system_test")
cr = importlib.import_module("choice_read")
doc_judge = importlib.import_module("doc_judge")
patched, with_source, caught = ftc.patched, ftc.with_source, ftc.caught
SMALL = dict(st.FIGURES, documents=len(ftc.GOLD))
with patched(st, "FIGURES", SMALL), st._figures():
    SMALL["power"] = ftc.ft.stated_power()


def batch(folder, documents, build, passed=None):
    """An invented sealed batch's session bundle: one B3 entry per document, each with its execution
    manifest (its workload the build's bundle, LF digests), its seal, its status and a run to read."""
    session = Path(folder) / "session"
    for n, document in enumerate(sorted(documents)):
        entry = session / "batch" / ("%02d_contradoc_%s_B3" % (n, document))
        entry.mkdir(parents=True)
        bundle = Path(build) / document
        files = {q.relative_to(bundle).as_posix(): st._lf_sha(q) for sub in ("context", "conventions") for q in (bundle / sub).rglob("*")
                 if q.is_file() and q.name != "_review_targets.json"}
        (entry / "execution_manifest.json").write_text(json.dumps({"arm": "B3", "workload": {"files": files}}), encoding="utf-8")
        (entry / "seal_entry.json").write_text(json.dumps({"arm": "B3", "item": "contradoc_" + document,
                                                           "execution_manifest_sha256": st._sha(entry / "execution_manifest.json")}), encoding="utf-8")
        ok = passed is None or document in passed
        (entry / "downloaded" / "evidence" / "run" / "audit").mkdir(parents=True)
        (entry / "FINAL_STATUS.json").write_text(json.dumps({"report": {"Execution assessment": "passed" if ok else "failed"}}), encoding="utf-8")
    return session


def b1_file(folder, value):
    """B1's prompts alone, byte for byte as the fresh prompts file holds them."""
    prompts = [p for p in value["prompts"] if p["group"] in st.B1_GROUPS]
    b1 = dict(value, prompts=prompts, prompt_count=len(prompts))
    path = Path(folder) / "b1_prompts.json"
    doc_judge._write_json(path, b1)
    return path


GOLD = {}


def invented_rows(right=None, drop=()):
    """B3 rows as the adapter would label them: right on the documents in `right` (all by default),
    none for the documents in `drop`."""
    def rows_of(runs, by_key):
        rows = []
        for document in sorted(runs):
            if document in drop:
                continue
            gold = GOLD[document]
            cls = gold if right is None or document in right else ("CLEAR" if gold == "FLAG" else "FLAG")
            rows.append({"document_id": document, "item_id": ITEMS[document], "gold": gold, "cls": cls, "source": "b3_label", "was_refused": False, "written_cls": cls})
        return rows
    return rows_of


ITEMS = {}


@contextlib.contextmanager
def session(folder, passed=None, judge=False, declaration=st.DECLARATION, ledger=None):
    folder = Path(folder)
    built = ftc.sample(folder / "set", declaration=declaration)
    staged = built["fresh_staged"]
    for n, source in enumerate(built["fresh_ids"]):
        GOLD[staged[source]] = "FLAG" if ftc.GOLD[n] else "CLEAR"
    for row in json.loads(Path(built["inputs"]["items"]).read_text(encoding="utf-8"))["items"]:
        ITEMS[row["document_id"]] = row["item_id"]
    b1 = b1_file(folder, built["value"])
    run = folder / "b1_run"
    doc_judge.run(b1, run, backend_factory=lambda reader, context: ftc.Canned(reader), reader_for=lambda g, a: dict(ftc.cdc.READER))
    exposure = folder / "exposure"
    exposure.mkdir()
    inputs = {"batch": str(batch(folder, staged.values(), built["build"], passed)), "b1_prompts": str(b1), "fresh_prompts": built["inputs"]["prompts"],
              "build": str(built["build"]), "keys": built["inputs"]["keys"],
              "ids": built["inputs"]["ids"], "items": built["inputs"]["items"], "parts": built["inputs"]["parts"],
              "sources": built["inputs"]["sources"], "exposure_roots": [str(exposure)], "exposure_expected": [], "effect": None, "judge": None}
    root = ftc.repository(folder / "repository", built["fresh_ids"])
    if ledger is not None:
        (root / fresh_once.ATTEMPTS_FILE).write_text(json.dumps({"attempts": ledger}), encoding="utf-8")
        (root / fresh_once.MARKER_FILE).write_text("".join("- %s t r\n" % row["set_key"] for row in ledger), encoding="utf-8")
        ftc.git(root, "add", "-A")
        ftc.git(root, "commit", "-q", "-m", "earlier reads")
    pinned = ftc.write_groups(root, built["fresh_ids"])
    real_scans(root)
    with patched(st, "FIGURES", SMALL), patched(ftc.ft, "FIGURES", ftc.SMALL), patched(cr, "repository_root", lambda: root), \
            patched(doc_judge, "_pinned", lambda path: True), patched(fresh_once, "GROUP_FILES", pinned), \
            patched(st, "FRESH_PROMPTS_SHA256", st._sha(built["inputs"]["prompts"])), \
            patched(st, "B1_BASE_DIGESTS", {"unsloth/phi-4-bnb-4bit": "fixture"}):
        if judge:
            judge_run = folder / "judge_run"
            doc_judge.run(built["inputs"]["prompts"], judge_run, backend_factory=lambda reader, context: ftc.Canned(reader), reader_for=ftc.trained_reader)
            ftc.CURRENT.update(calibration=built["inputs"]["calibration"], drift=0.0)
            judge_bar = folder / "judge_bar.json"
            judge_bar.write_text(json.dumps(ftc.ft.bar_value(built["inputs"])), encoding="utf-8")
            inputs["judge"] = {"bar": str(judge_bar), "run": str(judge_run), "inputs": built["inputs"]}
        yield inputs, run, root, built


REAL_SCAN = Path(cr.repository_root()) / fresh_once.PRECOMMIT_SCAN   # the main checkout, through git, before any patch
REAL_GUARD = ROOT / "scripts" / "guard_secrets.py"


def real_scans(root):
    """The real precommit scan and guard_secrets, copied into the fixture repository where the read
    runs them (fresh_once.precommit), committed with it."""
    import shutil
    for source, target in ((REAL_SCAN, Path(root) / fresh_once.PRECOMMIT_SCAN), (REAL_GUARD, Path(root) / "scripts" / "guard_secrets.py")):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    ftc.git(root, "add", "-A")
    ftc.git(root, "commit", "-q", "-m", "the scans")


def as_attempt_one():
    """fresh_once.attempt as it reads before any read: the proofs of the opening itself use it, since
    after a read the ledger and the marker differ until the lead adds the row, which refuses first."""
    return patched(fresh_once, "attempt", lambda: {"number": 1, "earlier": [], "ledger_sha256": "fixture"})


def commit_read(key):
    """The procedure after a read: the marker and the ledger's row, committed on the loop branch."""
    root = cr.repository_root()
    ledger = json.loads((root / fresh_once.ATTEMPTS_FILE).read_text(encoding="utf-8"))
    ledger["attempts"].append({"attempt": len(ledger["attempts"]) + 1, "set_key": key})
    (root / fresh_once.ATTEMPTS_FILE).write_text(json.dumps(ledger), encoding="utf-8")
    ftc.git(root, "add", fresh_once.MARKER_FILE, fresh_once.ATTEMPTS_FILE)
    ftc.git(root, "commit", "-q", "-m", "the read")


def do_read(inputs, run, out, rows_of=None):
    """Bar and read: the read commits the marker on the loop branch itself before it writes a figure."""
    bar = Path(out).parent / (Path(out).name + "_bar.json")

    def done():
        bar.write_text(json.dumps(st.bar_value(inputs)), encoding="utf-8")
        return st.read(bar, run, inputs, out, rows_of=rows_of or invented_rows(), calibrate=ftc.same_refit, effect=ftc.fixed_effect)
    return caught(done)

def observe_bar():
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        out = {}
        with patched(st, "FIGURES", dict(SMALL, documents=100)):
            out["size"] = caught(lambda: st.bar_value(inputs) and "barred")
        with patched(st, "FIGURES", dict(SMALL, power=dict(SMALL["power"], **{"6": .9}))):
            out["power"] = caught(lambda: st.bar_value(inputs) and "barred")
        good = st.bar_value(inputs)
        key = good["set_key"]
        for name, change in (("figures", {"figures": dict(SMALL, alpha_one_sided=.0125)}), ("alpha raised", {"figures": dict(SMALL, alpha_one_sided=.5)}),
                             ("attempt", {"attempt": dict(good["attempt"], number=3)}),
                             ("ids", {"inputs": dict(good["inputs"], ids="x")}), ("entries", {"entries": {}}),
                             ("set key", {"set_key": ("0" if key[0] != "0" else "1") + key[1:]}), ("groups", {"groups": good["groups"] + 1}),
                             ("comparator rule", {"comparator_rule": "the lower accuracy"})):
            path = Path(folder) / ("bar_" + name + ".json")
            path.write_text(json.dumps(dict(good, **change)), encoding="utf-8")
            out[name] = caught(lambda: st.open_bar(path, inputs) and "read")
        path = Path(folder) / "bar_good.json"
        path.write_text(json.dumps(good), encoding="utf-8")
        status = next(Path(inputs["batch"], "batch").iterdir()) / "FINAL_STATUS.json"
        status.write_text(json.dumps({"report": {"Execution assessment": "passed"}, "swapped": True}), encoding="utf-8")
        out["status swapped"] = caught(lambda: st.open_bar(path, inputs) and "read")
        return out


def expected_bar():
    return {"size": "ValueError: the test is sized for 100 documents; this set has 6",
            "power": "ValueError: the stated power is not the power of the stated effect",
            "figures": "ValueError: the bar states other figures than the code's", "attempt": "ValueError: the bar states other figures than the code's",
            "alpha raised": "ValueError: the bar states other figures than the code's",
            "ids": "ValueError: the bar names other inputs: ids", "entries": "ValueError: the bar names other batch entries",
            "set key": "ValueError: the bar's set key is not this set's", "groups": "ValueError: the bar's groups are not this set's",
            "comparator rule": "ValueError: the bar states another comparator rule", "status swapped": "ValueError: the bar names other batch entries"}


def observe_entries():
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        out = {"good": caught(lambda: bool(st.bar_value(inputs)))}
        entries = sorted(Path(inputs["batch"], "batch").iterdir())
        extra = entries[0].parent / "99_contradoc_000000000000_B3"
        extra.mkdir()
        (extra / "seal_entry.json").write_text(json.dumps({"arm": "B3", "item": "contradoc_000000000000", "execution_manifest_sha256": "m"}), encoding="utf-8")
        out["one too many"] = caught(lambda: st.bar_value(inputs) and "barred")
        (extra / "seal_entry.json").write_text(json.dumps({"arm": "B1", "item": "contradoc_000000000000"}), encoding="utf-8")
        out["a B1 entry"] = caught(lambda: st.bar_value(inputs) and "barred")
        extra.rename(Path(folder) / "set_aside")
        entry = sorted(Path(inputs["batch"], "batch").iterdir())[0]
        manifest = json.loads((entry / "execution_manifest.json").read_text(encoding="utf-8"))
        name = next(n for n in manifest["workload"]["files"] if n.startswith("conventions/"))
        manifest["workload"]["files"][name] = "0" * 64
        (entry / "execution_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        seal = json.loads((entry / "seal_entry.json").read_text(encoding="utf-8"))
        (entry / "seal_entry.json").write_text(json.dumps(dict(seal, execution_manifest_sha256=st._sha(entry / "execution_manifest.json"))), encoding="utf-8")
        out["another build's workload"] = caught(lambda: st.bar_value(inputs) and "barred").split(":")[1].strip()
    with tempfile.TemporaryDirectory() as folder, session(folder, declaration=None) as (inputs, run, root, built):
        out["no declaration"] = caught(lambda: st.bar_value(inputs) and "barred").split(":")[1].strip()
        rules = next(Path(inputs["build"]).glob("*/conventions/rules.md"))
        text = rules.read_text(encoding="utf-8")
        rules.write_text(text.replace("Consistency [required] [conformance]\n\n", "Consistency [required] [conformance]\n\nSee [compare: passages]. "), encoding="utf-8")
        out["the declaration in the text alone"] = caught(lambda: st.bar_value(inputs) and "barred").split(":")[1].strip()
    return out


def expected_entries():
    return {"good": True, "one too many": "ValueError: the batch's entries are not the fresh documents",
            "a B1 entry": "ValueError: a batch entry that is not a ContraDoc B3 entry: 99_contradoc_000000000000_B3",
            "another build's workload": "a batch entry's workload is not the declared build's bundle",
            "no declaration": "the declared build's rule does not carry [compare", "the declaration in the text alone": "the declared build's rule does not carry [compare"}


def observe_b1_groups():
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        value = doc_judge.read_file(inputs["b1_prompts"])
        fresh = inputs["fresh_prompts"]
        other = dict(value, prompts=value["prompts"] + [p for p in built["value"]["prompts"] if p["group"] == ftc.ft.UNTRAINED][:1])
        other["prompt_count"] = len(other["prompts"])
        path = Path(folder) / "other_b1.json"
        doc_judge._write_json(path, other)
        out = {"two groups": len(st.b1_questions(inputs["b1_prompts"], fresh)), "another group": caught(lambda: st.b1_questions(path, fresh) and "kept")}
        fewer = dict(value, prompts=value["prompts"][1:], prompt_count=len(value["prompts"]) - 1)
        path = Path(folder) / "fewer_b1.json"
        doc_judge._write_json(path, fewer)
        out["not the fresh file's prompts"] = caught(lambda: st.b1_questions(path, fresh) and "kept")
        with patched(st, "FRESH_PROMPTS_SHA256", "0" * 64):
            out["not the pinned fresh file"] = caught(lambda: st.b1_questions(inputs["b1_prompts"], fresh) and "kept")
        adapted = Path(folder) / "b1_adapted_run"
        doc_judge.run(inputs["b1_prompts"], adapted, backend_factory=lambda reader, context: ftc.Canned(reader),
                      reader_for=lambda g, a: ftc.trained_reader(g, a, on=("judge_direct",)))
        out["an adapter on B1"] = caught(lambda: st.b1_models(adapted, inputs["b1_prompts"]) or "base")
        out["base"] = caught(lambda: st.b1_models(run, inputs["b1_prompts"]) or "base")
        with patched(st, "B1_BASE_DIGESTS", {"unsloth/phi-4-bnb-4bit": "snapshot:other"}):
            out["other weights"] = caught(lambda: st.b1_models(run, inputs["b1_prompts"]) or "base")
        with patched(st, "B1_BASE_DIGESTS", {}):
            out["no pinned weights"] = caught(lambda: st.b1_models(run, inputs["b1_prompts"]) or "base")
        import shutil
        nodigest = Path(folder) / "b1_run_no_digest"
        shutil.copytree(run, nodigest)
        measured = json.loads((nodigest / doc_judge.MEASUREMENT_FILE).read_text(encoding="utf-8"))
        for model in measured["models"].values():
            model["digest"] = None
        (nodigest / doc_judge.MEASUREMENT_FILE).write_text(json.dumps(measured), encoding="utf-8")
        with patched(st, "B1_BASE_DIGESTS", {"unsloth/phi-4-bnb-4bit": None}):
            out["a digest of None"] = caught(lambda: st.b1_models(nodigest, inputs["b1_prompts"]) or "base")
        return out


def expected_b1_groups():
    return {"two groups": 12, "another group": "ValueError: the B1 prompts file holds groups other than judge_direct and judge_reason",
            "not the fresh file's prompts": "ValueError: the B1 prompts are not the fresh prompts file's, prompt for prompt",
            "not the pinned fresh file": "ValueError: the fresh prompts file is not the pinned one",
            "an adapter on B1": "ValueError: B1 group judge_direct had an adapter applied", "base": "base",
            "other weights": "ValueError: B1 group judge_direct loaded other weights than the pinned base",
            "no pinned weights": "ValueError: B1 group judge_direct names a model with no pinned weights: 'unsloth/phi-4-bnb-4bit'",
            "a digest of None": "ValueError: B1 group judge_direct loaded other weights than the pinned base"}


def observe_exposure():
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        out = {"clean": caught(lambda: bool(st.bar_value(inputs)))}
        planted = Path(inputs["exposure_roots"][0]) / "old_items.json"
        planted.write_text(json.dumps({"items": [{"source_document_id": built["fresh_ids"][0]}]}), encoding="utf-8")
        out["planted"] = caught(lambda: st.bar_value(inputs) and "barred").split(":")[1].strip() if True else None
        out["expected"] = caught(lambda: bool(st.bar_value(dict(inputs, exposure_expected=[str(planted)]))))
        key = Path(inputs["exposure_roots"][0]) / "answer_key.json"
        planted.unlink()
        key.write_text(json.dumps({"document": built["fresh_ids"][0]}), encoding="utf-8")
        out["a key is never read"] = caught(lambda: bool(st.bar_value(inputs)))
        return out


def expected_exposure():
    return {"clean": True, "planted": "a fresh document is named outside the expected files", "expected": True, "a key is never read": True}


def observe_once():
    out = {}
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        first = do_read(inputs, run, Path(folder) / "out")
        out["first"] = first if isinstance(first, str) else first["result"]
        key = first["set_key"] if isinstance(first, dict) else None
        out["marker committed"] = bool(key) and fresh_once.committed_on_loop(key)
        guard = as_attempt_one()
        guard.__enter__()
        value = doc_judge.read_file(inputs["b1_prompts"])
        other = Path(folder) / "b1_other.json"
        doc_judge._write_json(other, dict(value, prompts=list(reversed(value["prompts"]))))
        other_run = Path(folder) / "b1_other_run"
        doc_judge.run(other, other_run, backend_factory=lambda reader, context: ftc.Canned(reader), reader_for=lambda g, a: dict(ftc.cdc.READER))
        out["another bar, other B1 prompts"] = do_read(dict(inputs, b1_prompts=str(other)), other_run, Path(folder) / "out2")
        for path in [inputs["ids"], inputs["items"]] + inputs["keys"]:
            ftc.respace(path)
        out["re-spaced"] = do_read(inputs, run, Path(folder) / "out3")
        fresh_once.reads_path().unlink()
        out["the marker file alone"] = do_read(inputs, run, Path(folder) / "out4")
        guard.__exit__(None, None, None)
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        key = st.bar_value(inputs)["set_key"]
        ftc.git(root, "checkout", "-q", "-b", "elsewhere")
        (root / "notes.txt").write_text("a note naming %s\n" % key, encoding="utf-8")
        ftc.git(root, "add", "notes.txt")
        ftc.git(root, "commit", "-q", "-m", "a note")
        ftc.git(root, "checkout", "-q", "-")
        with as_attempt_one():
            out["named in another ref's file"] = do_read(inputs, run, Path(folder) / "out")
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        bar = Path(folder) / "bar.json"
        bar.write_text(json.dumps(st.bar_value(inputs)), encoding="utf-8")
        bare = Path(folder) / "not_a_repository"
        bare.mkdir()
        (bare / fresh_once.ATTEMPTS_FILE).parent.mkdir(parents=True)
        pinned = ftc.write_groups(bare, built["fresh_ids"])
        with patched(cr, "repository_root", lambda: bare), patched(fresh_once, "GROUP_FILES", pinned),                 patched(fresh_once, "attempt", lambda: json.loads(bar.read_text(encoding="utf-8"))["attempt"]):
            out["no git"] = caught(lambda: st.read(bar, run, inputs, Path(folder) / "out", rows_of=invented_rows()))
    return out


def expected_once():
    once = "ValueError: the fresh set has been read: it is read once"
    return {"first": "drop", "marker committed": True, "another bar, other B1 prompts": once, "re-spaced": once,
            "the marker file alone": once, "named in another ref's file": once, "no git": "ValueError: git cannot list the worktrees: no read"}


def observe_marker_commit():
    """The committed marker is the count: the key on the loop branch before any figure is written, the
    marker path alone committed, the real scans run; a failing scan, a failing commit or a dirty index
    leaves no marker and no count, and the read may be tried again."""
    out = {}
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        real_precommit = fresh_once.precommit

        def stage_another(worktree):
            (Path(worktree) / "other.txt").write_text("another file\n", encoding="utf-8")
            ftc.git(worktree, "add", "other.txt")
            return real_precommit(worktree)
        with patched(fresh_once, "precommit", stage_another):
            result = do_read(inputs, run, Path(folder) / "out")
        out["result written"] = (Path(folder) / "out" / st.RESULT).is_file()
        out["on the loop branch"] = fresh_once.committed_on_loop(result["set_key"]) if isinstance(result, dict) else result
        out["committed paths"] = ftc.git_out(root, "show", "--name-only", "--format=", fresh_once.LOOP_REF).split()
        out["the other file still staged"] = "other.txt" in ftc.git_out(root, "diff", "--cached", "--name-only").split()
        message = ftc.git_out(root, "log", "-1", "--format=%B", fresh_once.LOOP_REF)
        out["attribution"] = fresh_once.ATTRIBUTION in message
        ftc.git(root, "reset", "-q")
        out["a second attempt"] = caught(lambda: st.bar_value(inputs) and "barred")
        (root / "notes.txt").write_text("a note naming %s\n" % ("f" * 64), encoding="utf-8")
        ftc.git(root, "add", "notes.txt")
        ftc.git(root, "commit", "-q", "-m", "a note")
        out["a key in another file"] = fresh_once.committed_on_loop("f" * 64)
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        real_write = fresh_once.write_marker

        def write_bad(key, what, worktree):
            real_write(key, what, worktree)
            (Path(worktree) / "bad.txt").write_text("a dash \u2014 the scan refuses\n", encoding="utf-8")
            ftc.git(worktree, "add", "bad.txt")
        with patched(fresh_once, "write_marker", write_bad):
            out["a failing scan"] = do_read(inputs, run, Path(folder) / "out")
        ftc.git(root, "reset", "-q")
        (root / "bad.txt").unlink()
        out["no marker after a failing scan"] = not (root / fresh_once.MARKER_FILE).exists()
        out["reads after a failing scan"] = cr.reads_of(fresh_once.reads_path(), st.bar_value(inputs)["set_key"])
        hook = root / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        out["a failing commit"] = do_read(inputs, run, Path(folder) / "out2")
        out["no marker after a failing commit"] = not (root / fresh_once.MARKER_FILE).exists()
        hook.unlink()
        retried = do_read(inputs, run, Path(folder) / "out3")
        out["tried again"] = retried if isinstance(retried, str) else retried["result"]
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        key = st.bar_value(inputs)["set_key"]
        with patched(fresh_once, "committed_on_loop", lambda key: False):
            out["the key missing after the commit"] = do_read(inputs, run, Path(folder) / "out")
        out["spent by the commit"] = fresh_once.marker_named(key)
        out["reads when the key is missing"] = cr.reads_of(fresh_once.reads_path(), key)
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        (root / "staged.txt").write_text("staged\n", encoding="utf-8")
        ftc.git(root, "add", "staged.txt")
        out["a dirty index"] = do_read(inputs, run, Path(folder) / "out")
        out["reads after a dirty index"] = cr.reads_of(fresh_once.reads_path(), st.bar_value(inputs)["set_key"])
    return out


def observe_marker_alone():
    """A marker line in the loop worktree's file, never committed, and no reads file: the marker file
    as it stands refuses."""
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        key = st.bar_value(inputs)["set_key"]
        fresh_once.write_marker(key, "written by hand", root)
        second = do_read(inputs, run, Path(folder) / "out")
    return {"second": second if isinstance(second, str) else second.get("result")}


def expected_marker_alone():
    return {"second": "ValueError: the fresh set has been read: it is read once"}


def expected_marker_commit():
    return {"result written": True, "on the loop branch": True, "committed paths": [fresh_once.MARKER_FILE], "the other file still staged": True,
            "attribution": True, "a key in another file": False,
            "a second attempt": "ValueError: the attempts ledger and the reads marker name different reads",
            "a failing scan": "ValueError: the marker's scan failed: no read", "no marker after a failing scan": True, "reads after a failing scan": 0,
            "a failing commit": "ValueError: the marker commit failed: no read", "no marker after a failing commit": True, "tried again": "drop",
            "the key missing after the commit": "ValueError: the marker commit is not on the loop branch: the set is spent, no figure is read",
            "spent by the commit": True, "reads when the key is missing": 0,
            "a dirty index": "ValueError: the loop worktree's index is not clean: no read", "reads after a dirty index": 0}


def observe_recheck():
    """The keys' digests checked again just before the first gold read: a key changed after the
    marker commit is refused, no figure written."""
    real = fresh_once.opened

    @contextlib.contextmanager
    def swapping(key, line):
        with real(key, line):
            path = Path(INPUTS["keys"][0])
            value = json.loads(path.read_text(encoding="utf-8"))
            value["items"][0]["gold"] = "swapped after the count"
            path.write_text(json.dumps(value), encoding="utf-8")
            yield
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        INPUTS.update(inputs)
        with patched(fresh_once, "opened", swapping):
            refused = do_read(inputs, run, Path(folder) / "out")
        written = (Path(folder) / "out" / st.RESULT).is_file()
    return {"refused": refused if isinstance(refused, str) else refused.get("result"), "written": written}


INPUTS = {}


def expected_recheck():
    return {"refused": "ValueError: a fresh key changed after the bar: no figure is read", "written": False}


def observe_attempt():
    with tempfile.TemporaryDirectory() as folder, session(folder, ledger=[{"attempt": 1, "set_key": "e" * 64}]) as (inputs, run, root, built):
        return {"bar": caught(lambda: st.bar_value(inputs) and "barred")}


def expected_attempt():
    return {"bar": "ValueError: attempt 2: this test's alpha is set for attempt 1 alone"}


def observe_effect():
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        out = {}
        for name, value in (("no label", {"wins": 5, "losses": 1, "documents": 30, "read_on": "development"}),
                            ("another label", {"wins": 5, "losses": 1, "documents": 30, "read_on": "development", "label": "tuned"}),
                            ("labelled", {"wins": 5, "losses": 1, "documents": 30, "read_on": "development", "label": "out-of-sample"})):
            path = Path(folder) / (name.replace(" ", "_") + ".json")
            path.write_text(json.dumps(value), encoding="utf-8")
            out[name] = caught(lambda: st.power_before(st.development_effect(str(path)))["label"])
        return out


def expected_effect():
    return {"no label": "ValueError: an effect file states wins, losses, documents, read_on and label",
            "another label": "ValueError: an effect's label is 'out-of-sample' or 'in-sample, threshold chosen on these rows'", "labelled": "out-of-sample"}


def observe_no_label():
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        dropped = sorted(GOLD)[0]
        result = do_read(inputs, run, Path(folder) / "out", rows_of=invented_rows(drop=(dropped,)))
    if isinstance(result, str):
        return result
    return {"items with no system label": result["items_with_no_system_label"], "items": result["system"]["items"]}


def expected_no_label():
    return {"items with no system label": 1, "items": 6}


def observe_before():
    """Everything the read needs is checked before the count, so a missing piece spends nothing."""
    out = {}
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        source = Path(inputs["sources"][0])
        value = json.loads(source.read_text(encoding="utf-8"))
        dropped = built["fresh_ids"][0]
        for container in value.values():
            container.pop(dropped, None)
        short = Path(folder) / "short_source.json"
        short.write_text(json.dumps(value), encoding="utf-8")
        out["a document in no source"] = do_read(dict(inputs, sources=[str(short)]), run, Path(folder) / "out") == (
            "ValueError: a fresh document is in no source file: " + dropped)
        prompts = doc_judge.read_file(inputs["b1_prompts"])
        item = prompts["prompts"][0]["item_id"]
        fewer = dict(prompts, prompts=[p for p in prompts["prompts"] if not (p["group"] == "judge_reason" and p["item_id"] == item)])
        fewer["prompt_count"] = len(fewer["prompts"])
        path = Path(folder) / "b1_fewer.json"
        doc_judge._write_json(path, fewer)
        fewer_run = Path(folder) / "b1_fewer_run"
        doc_judge.run(path, fewer_run, backend_factory=lambda reader, context: ftc.Canned(reader), reader_for=lambda g, a: dict(ftc.cdc.READER))
        with patched(st, "b1_questions", lambda *a: []):
            out["an item with no B1 prompt"] = do_read(dict(inputs, b1_prompts=str(path)), fewer_run, Path(folder) / "out2").split(":")[1].strip()
        other = Path(folder) / "b1_respaced.json"
        other.write_text(json.dumps(doc_judge.read_file(inputs["b1_prompts"]), indent=3), encoding="utf-8")
        with patched(st, "b1_questions", lambda *a: []):
            out["a B1 pass of other prompts"] = do_read(dict(inputs, b1_prompts=str(other)), run, Path(folder) / "out3")
        entries = sorted(Path(inputs["batch"], "batch").iterdir())
        status = entries[0] / "FINAL_STATUS.json"
        saved = status.read_text(encoding="utf-8")
        status.write_text("{not json", encoding="utf-8")
        out["a status that cannot be read"] = do_read(inputs, run, Path(folder) / "out4").split(":")[1].strip()
        status.write_text(saved, encoding="utf-8")
        (entries[0] / "downloaded" / "evidence" / "run" / "audit").rmdir()
        out["an entry with no run"] = do_read(inputs, run, Path(folder) / "out5").split(":")[1].strip()
        out["reads"] = cr.reads_of(fresh_once.reads_path(), st.bar_value(inputs)["set_key"])
    return out


def expected_before():
    return {"a document in no source": True, "an item with no B1 prompt": "a fresh item has no judge_reason prompt",
            "a B1 pass of other prompts": "ValueError: the pass folder is not a pass of these prompts",
            "a status that cannot be read": "a batch entry's status cannot be read", "an entry with no run": "a batch entry has no run to read", "reads": 0}


def observe_judge():
    with tempfile.TemporaryDirectory() as folder, session(folder, judge=True) as (inputs, run, root, built):
        result = do_read(inputs, run, Path(folder) / "out")
    if isinstance(result, str):
        return result
    judge = result.get("judge_descriptive") or {}
    return {"system": result["result"], "judge descriptive": judge.get("descriptive"), "judge reading": judge.get("reading"),
            "judge right": (judge.get("trained") or {}).get("right"), "reads": result["reads"]}


def expected_judge():
    return {"system": "drop", "judge descriptive": True, "judge reading": "descriptive only: not shown at this size", "judge right": 3, "reads": 1}


def observe_order():
    """No fresh key's item table or labels are read before the count (the lead's ruling on item 9);
    only the scorer's digests are."""
    events = []
    sc = doc_judge._score_corpus()
    real_labels, real_table, real_count = sc.benchmark_labels, sc.item_table, cr.count_read

    def gold(*args, **kwargs):
        events.append("gold")
        return real_labels(*args, **kwargs)

    def table(*args, **kwargs):
        events.append("items")
        return real_table(*args, **kwargs)

    def counted(*args):
        events.append("count")
        return real_count(*args)
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        bar = Path(folder) / "bar.json"
        bar.write_text(json.dumps(st.bar_value(inputs)), encoding="utf-8")
        with patched(sc, "benchmark_labels", gold), patched(sc, "item_table", table), patched(cr, "count_read", counted):
            result = caught(lambda: st.read(bar, run, inputs, Path(folder) / "out", rows_of=invented_rows()))
    return {"result": result if isinstance(result, str) else result["result"], "first": events[0] if events else None}


def observe_guard():
    """Any read of a fresh key before the count but the three allowed (item tables, content digests,
    raw-byte digests) is refused: its labels, its score, a direct read."""
    sc = doc_judge._score_corpus()
    out = {}
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        key = inputs["keys"][0]
        real = st.validate_before

        def item_table():
            return sc._read_key_file(key)
        for name, early in (("labels", lambda: sc.benchmark_labels(key, Path(folder), arm="B3")),
                            ("score", lambda: sc.score(None, str(folder), key_path=key)),
                            ("direct", lambda: sc._read_key_file(key)), ("a function named item_table", lambda: item_table())):
            def validate(*args, early=early):
                early()
                return real(*args)
            with patched(st, "validate_before", validate):
                out[name] = do_read(inputs, run, Path(folder) / ("out_" + name))
        out["allowed"] = caught(lambda: bool(st.bar_value(inputs)))
        out["reads"] = cr.reads_of(fresh_once.reads_path(), st.bar_value(inputs)["set_key"])
    return {k: (v.split(" by ")[0] if isinstance(v, str) else v) for k, v in out.items()}


def expected_guard():
    refused = "ValueError: a fresh key is read before the count"
    return {"labels": refused, "score": refused, "direct": refused, "a function named item_table": refused, "allowed": True, "reads": 0}


def observe_key_mismatch():
    """A key file whose content is not the one the bar's key digest names refuses before the count."""
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        bar = Path(folder) / "bar.json"
        bar.write_text(json.dumps(st.bar_value(inputs)), encoding="utf-8")
        key = Path(inputs["keys"][0])
        value = json.loads(key.read_text(encoding="utf-8"))
        value["items"][0]["gold"] = "changed after the bar"
        key.write_text(json.dumps(value), encoding="utf-8")
        refused = caught(lambda: st.read(bar, run, inputs, Path(folder) / "out", rows_of=invented_rows()))
        reads = cr.reads_of(fresh_once.reads_path(), json.loads(bar.read_text(encoding="utf-8"))["set_key"])
    return {"refused": refused if isinstance(refused, str) else refused.get("result"), "reads": reads}


def expected_key_mismatch():
    return {"refused": "ValueError: the bar names other inputs: keys", "reads": 0}


def observe_reset():
    """Round 2 gap 6, a residual: the loop ref reset to before the marker commit, the reads file still
    present, refuses a second read."""
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        first = do_read(inputs, run, Path(folder) / "out")
        ftc.git(root, "reset", "-q", "--hard", "HEAD~1")
        marker_gone = not fresh_once.committed_on_loop(first["set_key"]) if isinstance(first, dict) else first
        second = do_read(inputs, run, Path(folder) / "out2")
    return {"marker gone from the ref": marker_gone, "second": second if isinstance(second, str) else second.get("result")}


def expected_reset():
    return {"marker gone from the ref": True, "second": "ValueError: the fresh set has been read: it is read once"}


def expected_order():
    return {"result": "drop", "first": "count"}


def observe_verdict():
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        perfect = do_read(inputs, run, Path(folder) / "out")
    return {"result": perfect["result"], "reading": perfect["reading"], "comparator": perfect["comparator"], "wins": perfect["wins"],
            "losses": perfect["losses"], "system right": perfect["system"]["right"], "power": perfect["power_before_read"]["power"],
            "attempt": perfect["attempt"]["number"]}


def expected_verdict():
    # B1 canned replies are right on every document, so is the invented B3: no discordant document; the ledger is empty, so attempt 1
    return {"result": "drop", "reading": "not shown at this size", "comparator": "judge_reason", "wins": 0, "losses": 0,
            "system right": 3, "power": None, "attempt": 1}


def observe_declaration():
    """D-331: the ContraDoc build adds the operator's declaration to CONV-CDOC-01's heading only when
    asked, the convention parser reads it, and a declaration no build may add is refused."""
    import convention_parser
    from common import bundle
    out = {}
    with tempfile.TemporaryDirectory() as folder:
        source = ftc.source_file(Path(folder) / "source.json", [(sid, True, n) for n, sid in enumerate(ftc.development_ids("decl-", 2))])
        for name, declaration in (("as shipped", None), ("declared", "compare: passages")):
            build = Path(folder) / name.replace(" ", "_")
            ftc.cli.build(ftc.contradoc, source, build, development=True, **({"rule_declaration": declaration} if declaration else {}))
            rules_file = next(next(build.glob("*/conventions")).glob("*.md"))
            out[name] = [r.compare for r in convention_parser._parse_text(rules_file, [0])]
        out["another declaration"] = caught(lambda: ftc.cli.build(ftc.contradoc, source, Path(folder) / "other", development=True,
                                                                  rule_declaration="scope: class=A") and "built")
        # D-471: the SciTab build adds `compare: cells` to every claim's heading, the rule's text then the
        # claim alone (the cell step's claim), the items, keys and parts files unchanged; neither
        # benchmark's build adds the other's declaration.
        scitab = _scitab()
        claims = Path(scitab.__file__).resolve().parent / "fixtures" / "synthetic_items.json"
        rules, files = {}, {}
        for name, declaration in (("as shipped", None), ("declared", "compare: cells")):
            build = Path(folder) / ("scitab_" + name.replace(" ", "_"))
            ftc.cli.build(scitab, claims, build, development=True, synthetic=True, **({"rule_declaration": declaration} if declaration else {}))
            rules[name] = [r for f in sorted(build.glob("*/conventions/*.md")) for r in convention_parser._parse_text(f, [0])]
            files[name] = {f.relative_to(build).as_posix(): f.read_bytes() for f in sorted(build.rglob("*.json"))}
        head, tail = scitab.RULE_TEMPLATE.split("{claim}")
        out["scitab as shipped"] = sorted({r.compare for r in rules["as shipped"]})
        out["scitab declared"] = sorted({r.compare for r in rules["declared"]})
        out["scitab claim alone"] = (len(rules["declared"]) > 0 and
                                     [head + r.rule + tail for r in rules["declared"]] == [r.rule for r in rules["as shipped"]])
        out["scitab items, keys and parts unchanged"] = bool(files["declared"]) and files["declared"] == files["as shipped"]
        out["scitab with passages"] = caught(lambda: ftc.cli.build(scitab, claims, Path(folder) / "s_other", development=True, synthetic=True,
                                                                   rule_declaration="compare: passages") and "built")
        out["contradoc with cells"] = caught(lambda: ftc.cli.build(ftc.contradoc, source, Path(folder) / "c_other", development=True,
                                                                   rule_declaration="compare: cells") and "built")
    out["admitted"] = list(bundle.RULE_DECLARATIONS)
    return out


class _PromptWords:
    """A stand-in token counter whose prompt count depends on the prompt's own words, as a real
    tokenizer's does: a rule's heading and text change the overhead."""

    def count(self, text):
        return len(text.split())

    def count_prompt(self, system, user):
        return len((system + " " + user).split())


def observe_cut():
    """D-478: under the token counter and limits the cut is computed from the as-shipped rules in every
    build, so a declared build's items, parts and keys are byte for byte the as-shipped build's, with
    documents really cut; only the rules file differs."""
    out = {}
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        scitab = _scitab()
        sources = {"contradoc": (ftc.contradoc, ftc.source_file(folder / "source.json", [(sid, n % 2 == 0, n) for n, sid in enumerate(ftc.development_ids("cut-", 4))]),
                                 "compare: passages", {}),
                   "scitab": (scitab, Path(scitab.__file__).resolve().parent / "fixtures" / "synthetic_items.json", "compare: cells", {"synthetic": True})}
        for benchmark, (adapter, source, declaration, extra) in sources.items():
            def build(name, max_context, declared):
                target = folder / ("%s_%s" % (benchmark, name))
                ftc.cli.build(adapter, source, target, development=True, max_context=max_context, output_allowance=10,
                              token_counter=_PromptWords(), **dict(extra, **({"rule_declaration": declaration} if declared else {})))
                return target
            probe = json.loads((build("probe", 100000, False) / "parts.json").read_text(encoding="utf-8"))["documents"]
            # the widest context under which the as-shipped build still cuts a document (the fixtures are
            # a few dozen words long); the declared build is then made under that same context
            base = max(d["cut"]["prompt_overhead"] for d in probe) + 10 + 32
            limit = None
            for room in range(38, 12, -2):
                try:
                    tried = json.loads((build("try%d" % room, base + room, False) / "parts.json").read_text(encoding="utf-8"))["documents"]
                except ValueError:
                    continue
                if any(d["cut"]["cut"] for d in tried):
                    limit = base + room
                    break
            files = {}
            for name, declared in (("shipped", False), ("declared", True)):
                target = build(name, limit, declared)
                files[name] = {f.relative_to(target).as_posix(): f.read_bytes() for f in sorted(target.rglob("*")) if f.is_file()}
            parts = json.loads(files["declared"]["parts.json"].decode("utf-8"))["documents"]
            differ = sorted(n for n in files["shipped"] if files["shipped"][n] != files["declared"].get(n))
            out[benchmark] = {"same files": sorted(files["shipped"]) == sorted(files["declared"]),
                              "documents cut": any(d["cut"]["cut"] for d in parts),
                              "the cut applied to every document": all(d["cut"]["applied"] for d in parts),
                              "only the rules files differ": bool(differ) and all(n.endswith("conventions/rules.md") for n in differ),
                              "parts.json identical": files["shipped"]["parts.json"] == files["declared"]["parts.json"]}
    return out


def expected_cut():
    row = {"same files": True, "documents cut": True, "the cut applied to every document": True,
           "only the rules files differ": True, "parts.json identical": True}
    return {"contradoc": dict(row), "scitab": dict(row)}


_SCITAB = []


def _scitab():
    """The SciTab adapter, loaded once from its file (the name `adapter` is ContraDoc's here)."""
    if not _SCITAB:
        import importlib.util
        path = Path(__file__).resolve().parents[1] / "benchmark" / "adapters" / "scitab" / "adapter.py"
        spec = importlib.util.spec_from_file_location("benchmark_adapter_scitab_declaration", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _SCITAB.append(module)
    return _SCITAB[0]


def observe_scoring():
    """D-476: the system's rows are labelled in the mode declared for their benchmark. On synthetic run
    folders (the adapter checks' own): a SciTab claim the cell step could not settle is UNDECIDED and
    one with no decision and no record ABSTAIN (detection_dev, D-472); a ContraDoc document nothing
    was raised on is CLEAR (v2_primary); a benchmark with no declared mode is refused."""
    import adapter_checks as ac
    det = ac._det()
    unit = "u01-p-00001"
    out = {}
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        cases = {"scitab": (["CONV-holds", "CONV-unsettled", "CONV-silent"],
                            {det.CELL_CLAIMS_KEY: [{"rule_id": "CONV-holds", "decisions": [{"unit_id": unit, "decided": "holds", "settled": True}]},
                                                   {"rule_id": "CONV-unsettled", "decisions": [{"unit_id": unit, "decided": "holds", "settled": False}]}]}),
                 "contradoc": (["CONV-CDOC-01"], {})}
        for benchmark, (rules, extra) in cases.items():
            doc = "d-" + benchmark
            ac._incomplete_run(folder / benchmark, doc, completion=ac._completion(), pairing=dict(ac._units_pairing([unit]), **extra),
                               bus_lines=[ac._bus_line("PRACTICE_AUDITOR", doc, [], ac._MODEL_BACKEND, ac._MODEL_ID)])
            key = folder / (benchmark + "_key.json")
            key.write_text(json.dumps({"benchmark": benchmark, "document": doc + ".md",
                                       "items": [{"item_id": "i-" + r, "rule_id": r, "gold": None} for r in rules]}), encoding="utf-8")
            rows = st.system_rows({doc: folder / benchmark / doc}, {doc: key}, benchmark)
            out[benchmark] = {r["item_id"]: r["cls"] for r in rows}
        out["default"] = st.system_rows.__defaults__
        out["undeclared"] = caught(lambda: st.system_rows({}, {}, "cuad"))
    return out


def observe_gate_arm():
    """D-478 item 2: the system's arm as the gate scorer takes it (gate_score.system_arm, the rows
    gate_score.figures and compute read) is labelled in its own benchmark's mode: on SciTab a claim
    the cell step could not settle is "not enough info" and one with no decision and no record
    ABSTAIN, never "supports"; on ContraDoc a document nothing was raised on is "no contradiction"."""
    import adapter_checks as ac
    import gate_score
    det = ac._det()
    unit = "u01-p-00001"
    out = {}
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        cases = {"scitab": ([("CONV-holds", "supports"), ("CONV-unsettled", "not enough info"), ("CONV-silent", "refutes")],
                            {det.CELL_CLAIMS_KEY: [{"rule_id": "CONV-holds", "decisions": [{"unit_id": unit, "decided": "holds", "settled": True}]},
                                                   {"rule_id": "CONV-unsettled", "decisions": [{"unit_id": unit, "decided": "holds", "settled": False}]}]}),
                 "contradoc": ([("CONV-CDOC-01", gate_score._adapter("contradoc").SPEC.labels["CLEAR"])], {})}
        for benchmark, (rules, extra) in cases.items():
            doc = "d-" + benchmark
            ac._incomplete_run(folder / benchmark, doc, completion=ac._completion(), pairing=dict(ac._units_pairing([unit]), **extra),
                               bus_lines=[ac._bus_line("PRACTICE_AUDITOR", doc, [], ac._MODEL_BACKEND, ac._MODEL_ID)])
            key = folder / (benchmark + "_key.json")
            key.write_text(json.dumps({"benchmark": benchmark, "document": doc + ".md",
                                       "items": [{"item_id": "i-" + r, "rule_id": r, "gold": gold} for r, gold in rules]}), encoding="utf-8")
            item_ids = ["i-" + r for r, _gold in rules]
            set_file = folder / (benchmark + "_set.json")
            set_file.write_text(json.dumps({"contradoc": [{"item_id": item_ids[0], "document_id": doc}]} if benchmark == "contradoc"
                                           else {"scitab": [{"document_id": doc, "item_ids": item_ids}]}), encoding="utf-8")
            arm = gate_score.system_arm(benchmark, {doc: folder / benchmark / doc}, {doc: key}, set_file)
            out[benchmark] = sorted((r["item_id"], r["cluster"], r["label"], r["gold"]) for r in arm)
            # the scorer takes these rows as they are
            setting = "3-class" if benchmark == "scitab" else None
            out[benchmark + " scored"] = gate_score.compute(benchmark, {"system": arm, "b1": arm}, setting, draws=20)["arms"]["system"]["items"]
        out["outside the set"] = caught(lambda: gate_score.system_arm(
            "contradoc", {"d-contradoc": folder / "contradoc" / "d-contradoc"}, {"d-contradoc": folder / "contradoc_key.json"}, folder / "scitab_set.json"))
    return out


def expected_gate_arm():
    clear = "no contradiction"
    import gate_score
    clear = gate_score._adapter("contradoc").SPEC.labels["CLEAR"]
    return {"scitab": [("i-CONV-holds", "d-scitab", "supports", "supports"), ("i-CONV-silent", "d-scitab", "ABSTAIN", "refutes"),
                       ("i-CONV-unsettled", "d-scitab", "not enough info", "not enough info")],
            "scitab scored": 3, "contradoc": [("i-CONV-CDOC-01", "d-contradoc", clear, clear)], "contradoc scored": 1,
            "outside the set": "ValueError: item i-CONV-CDOC-01 is not in the set file"}


def expected_scoring():
    return {"scitab": {"i-CONV-holds": "CLEAR", "i-CONV-unsettled": "UNDECIDED", "i-CONV-silent": "ABSTAIN"},
            "contradoc": {"i-CONV-CDOC-01": "CLEAR"}, "default": ("contradoc",),
            "undeclared": "ValueError: no scoring mode is declared for the system's labels on 'cuad'"}


def expected_declaration():
    return {"as shipped": [""], "declared": ["passages"], "another declaration": "ValueError: a rule declaration no build may add: 'scope: class=A' (CONV-CDOC-01)",
            "scitab as shipped": [""], "scitab declared": ["cells"], "scitab claim alone": True,
            "scitab items, keys and parts unchanged": True,
            "scitab with passages": "ValueError: a rule declaration a scitab build may not add: 'compare: passages'",
            "contradoc with cells": "ValueError: a rule declaration a contradoc build may not add: 'compare: cells'",
            "admitted": ["compare: passages", "compare: cells"]}


CANDIDATE = dict(ftc.CANDIDATE)
OTHER = dict(ftc.OTHER)


def observe_grep():
    real = fresh_once._git

    def failing(root, *args, **kwargs):
        done = real(root, *args, **kwargs)
        if args and args[0] == "grep":
            done.returncode = 2
        return done
    with tempfile.TemporaryDirectory() as folder, session(folder) as (inputs, run, root, built):
        with patched(fresh_once, "_git", failing):
            refused = do_read(inputs, run, Path(folder) / "out")
        reads = cr.reads_of(fresh_once.reads_path(), st.bar_value(inputs)["set_key"])
    return {"refused": refused, "reads": reads}


def expected_grep():
    return {"refused": "ValueError: git cannot say whether a commit names this read: no read", "reads": 0}


def observe_tests():
    keep = lambda c=None, o=None, w=6, l=0: (lambda t: "keep" if all(t.values()) else sorted(k for k, v in t.items() if not v))(
        st.tests(c or CANDIDATE, o or OTHER, w, l))
    return {"keep": keep(), "more losses": keep(w=2, l=6), "three of three": keep(w=3, l=0), "accuracy not above": keep(c=dict(CANDIDATE, accuracy=.6)),
            "precision": keep(c=dict(CANDIDATE, right=14, false=6, precision=.7)), "chance": keep(c=dict(CANDIDATE, chance_tail=.06)),
            "flagged": keep(c=dict(CANDIDATE, flagged=55, right=50, false=5))}


def expected_tests():
    return {"keep": "keep", "more losses": ["sign_test"], "three of three": ["sign_test"], "accuracy not above": ["above_b1"], "precision": ["precision"], "chance": ["chance"],
            "flagged": ["flagged"]}


def observe_void():
    passed = {"d%d" % n: n >= 1 for n in range(20)}
    return {"one entry failed": st.void_reasons(passed, {"judge_direct": 1.0, "judge_reason": 1.0}, "judge_reason"),
            "two entries failed": st.void_reasons(dict(passed, d1=False), {"judge_direct": 1.0, "judge_reason": 1.0}, "judge_reason"),
            "one B1 group": st.void_reasons({d: True for d in passed}, {"judge_direct": 1.0, "judge_reason": .9}, "judge_reason"),
            "no comparator": st.void_reasons({d: True for d in passed}, {"judge_direct": 1.0, "judge_reason": 1.0}, None)}


def expected_void():
    return {"one entry failed": [], "two entries failed": ["batch entries passed execution integrity 0.900"],
            "one B1 group": ["judge_reason prompts readable 0.900"], "no comparator": ["no B1 group is a comparator"]}


def run_checks():
    proofs = [
        ("the bar's figures", observe_bar, expected_bar, lambda: with_source(st, "open_bar", 'or bar.get("figures") != FIGURES', "")),
        ("the size", observe_bar, expected_bar, lambda: with_source(st, "_bar_value", 'if len(documents) != FIGURES["documents"]:', "if False:")),
        ("the power stated", observe_bar, expected_bar, lambda: with_source(st, "_bar_value", 'if FIGURES["power"] != ft.stated_power():', "if False:")),
        ("the attempt", observe_bar, expected_bar, lambda: with_source(st, "open_bar", ' or bar.get("attempt") != first_attempt()', "")),
        ("the batch entries", observe_bar, expected_bar, lambda: with_source(st, "open_bar", 'if entry_digests(entries(inputs["batch"]), inputs["build"]) != bar.get("entries"):', "if False:")),
        ("one entry per document", observe_entries, expected_entries, lambda: with_source(st, "_bar_value", "if set(folders) != set(documents):", "if False:")),
        ("B3 entries only", observe_entries, expected_entries, lambda: with_source(
            st, "entries", 'if arm != "B3" or not str(item or "").startswith(BENCHMARK + "_"):', 'if not str(item or "").startswith(BENCHMARK + "_"):')),
        ("B1's two groups", observe_b1_groups, expected_b1_groups, lambda: with_source(st, "b1_questions", 'if {p["group"] for p in value["prompts"]} != set(B1_GROUPS):', "if False:")),
        ("exposure", observe_exposure, expected_exposure, lambda: with_source(st, "_bar_value", "if seen:", "if False:")),
        ("counted before any fresh key", observe_order, expected_order, lambda: with_source(
            fresh_once, "opened", "        commit_marker(key, line.get(\"what\", \"read\"))\n        cr.count_read(reads_path(), key, dict(line, inputs_sha256=key), True)\n        yield",
            "        yield\n        commit_marker(key, line.get(\"what\", \"read\"))\n        cr.count_read(reads_path(), key, dict(line, inputs_sha256=key), True)")),
        ("only the allowed readers before the count", observe_guard, expected_guard, lambda: with_source(
            st, "before_count", "    sc._read_key_file = guarded\n", "")),
        ("a key unlike the bar's digest refuses before the count", observe_key_mismatch, expected_key_mismatch, lambda: patched(
            st, "open_bar", lambda bar_path, inputs: json.loads(Path(bar_path).read_text(encoding="utf-8")))),
        ("a reset ref, the reads file present", observe_reset, expected_reset, lambda: with_source(
            fresh_once, "opened", "if cr.reads_of(reads_path(), key) or marker_named(key):", "if marker_named(key):")),
        ("the key in the marker file alone", observe_marker_commit, expected_marker_commit, lambda: with_source(
            fresh_once, "committed_on_loop", 'found = _git(root, "grep", "-F", "-q", "-e", key, LOOP_REF, "--", MARKER_FILE)',
            'found = _git(root, "grep", "-F", "-q", "-e", key, LOOP_REF)')),
        ("no item table before the count", observe_order, expected_order, lambda: with_source(
            st, "_bar_value", "    documents = documents_before(inputs)\n", "    documents = either_test.universe(inputs[\"keys\"], inputs[\"ids\"], inputs[\"items\"])[0]\n")),
        ("the key is the set's alone", observe_once, expected_once, lambda: with_source(
            st, "_bar_value", '"set_key": fresh_once.set_key(inputs["ids"], inputs["keys"])',
            '"set_key": doc_judge._sha(fresh_once.set_key(inputs["ids"], inputs["keys"]) + _sha(inputs["b1_prompts"]))')),
        ("the marker committed before any figure", observe_marker_commit, expected_marker_commit, lambda: with_source(
            fresh_once, "opened", '        commit_marker(key, line.get("what", "read"))\n', "")),
        ("a failing scan refuses", observe_marker_commit, expected_marker_commit, lambda: with_source(
            fresh_once, "commit_marker", "        if not precommit(worktree):\n", "        if False:\n")),
        ("a failing commit takes the marker back", observe_marker_commit, expected_marker_commit, lambda: with_source(
            fresh_once, "commit_marker", "        if before is None:\n            path.unlink(missing_ok=True)\n", "        if False:\n            pass\n")),
        ("the key confirmed after the commit", observe_marker_commit, expected_marker_commit, lambda: with_source(
            fresh_once, "commit_marker", "    if not committed_on_loop(key):", "    if False:")),
        ("the marker path alone committed", observe_marker_commit, expected_marker_commit, lambda: with_source(
            fresh_once, "commit_marker", 'done = _git(worktree, "commit", "-q", "-m", message, "--", MARKER_FILE, timeout=120)',
            'done = _git(worktree, "commit", "-q", "-m", message, timeout=120)')),
        ("the count after the commit", observe_marker_commit, expected_marker_commit, lambda: with_source(
            fresh_once, "opened", "        commit_marker(key, line.get(\"what\", \"read\"))\n        cr.count_read(reads_path(), key, dict(line, inputs_sha256=key), True)\n",
            "        cr.count_read(reads_path(), key, dict(line, inputs_sha256=key), True)\n        commit_marker(key, line.get(\"what\", \"read\"))\n")),
        ("the keys checked again before gold", observe_recheck, expected_recheck, lambda: with_source(
            st, "read", '            if doc_judge.keys_digest(doc_judge._score_corpus(), inputs["keys"]) != bar["inputs"]["keys"]:', "            if False:")),
        ("B1 pinned weights or refused", observe_b1_groups, expected_b1_groups, lambda: with_source(
            st, "b1_models", "if named not in B1_BASE_DIGESTS:", "if False:")),
        ("a digest of None refused", observe_b1_groups, expected_b1_groups, lambda: with_source(
            st, "b1_models", 'if not model.get("digest") or model.get("digest") != B1_BASE_DIGESTS[named]:', 'if model.get("digest") != B1_BASE_DIGESTS.get(named):')),
        ("readers by identity", observe_guard, expected_guard, lambda: with_source(
            st, "before_count", "if str(Path(path).resolve()) in fresh and caller not in allowed:",
            "if str(Path(path).resolve()) in fresh and caller.co_name not in BEFORE_COUNT_READERS:")),
        ("a dirty index refuses", observe_marker_commit, expected_marker_commit, lambda: with_source(
            fresh_once, "opened", "        if not index_clean(loop_worktree()):", "        if False:")),
        ("every tracked file of every ref", observe_once, expected_once, lambda: with_source(
            fresh_once, "marker_named", 'found = _git(root, "grep", "-F", "-q", "-e", key, *tips)', 'found = _git(root, "grep", "-F", "-q", "-e", key, "HEAD", "--", MARKER_FILE)')),
        ("git that cannot answer", observe_once, expected_once, lambda: with_source(
            fresh_once, "loop_worktree", "if listed is None or listed.returncode != 0:", "if listed is None:")),
        ("every fresh document in a source", observe_before, expected_before, lambda: with_source(st, "validate_before", "if missing:", "if False:")),
        ("every fresh item with both B1 prompts", observe_before, expected_before, lambda: with_source(st, "validate_before", "if lacking:", "if False:")),
        ("the judge inside the one opening", observe_judge, expected_judge, lambda: with_source(
            st, "read", '            result["judge_descriptive"] = ft.judge_figures(judge_bar, judge["run"], judge["inputs"], out / "judge")\n', "            pass\n")),
        ("the verdict end to end", observe_verdict, expected_verdict, lambda: with_source(st, "_read", 'reading="shown" if kept else "not shown at this size"', 'reading="no effect"')),
        ("the declaration on the heading", observe_declaration, expected_declaration, lambda: with_source(
            importlib.import_module("common.bundle"), "render_rules", '        heading += "".join(" [%s]" % d for d in rule.get("declarations") or ())\n', "")),
        ("only an admitted declaration", observe_declaration, expected_declaration, lambda: with_source(
            importlib.import_module("common.bundle"), "check_rule", "        if declaration not in RULE_DECLARATIONS:", "        if False:")),
        ("the gate's SciTab arm in SciTab's mode", observe_gate_arm, expected_gate_arm, lambda: with_source(
            importlib.import_module("gate_score"), "system_arm",
            "    for row in system_test.system_rows(runs, by_key, benchmark):", "    for row in system_test.system_rows(runs, by_key):")),
        ("the gate's arm inside its set", observe_gate_arm, expected_gate_arm, lambda: with_source(
            importlib.import_module("gate_score"), "system_arm", '        if row["item_id"] not in listed:', "        if False:")),
        ("SciTab's rows under detection_dev", observe_scoring, expected_scoring, lambda: patched(st, "SCORING", dict(st.SCORING, scitab=None))),
        ("ContraDoc's rows under v2_primary", observe_scoring, expected_scoring, lambda: patched(st, "SCORING", dict(st.SCORING, contradoc="detection_dev"))),
        ("no mode guessed", observe_scoring, expected_scoring, lambda: with_source(st, "scoring_of", "    if benchmark not in SCORING:", "    if False:")),
        ("the cut from the as-shipped rules", observe_cut, expected_cut, lambda: with_source(
            importlib.import_module("common.bundle"), "shipped_rules",
            'return [{"rule_id": r["rule_id"], "name": r["name"], "text": r.get("shipped_text", r["text"])} for r in rules]', "return rules")),
        ("each benchmark its own declaration", observe_declaration, expected_declaration, lambda: with_source(
            importlib.import_module("common.bundle"), "build_declaration",
            "    if declaration in RULE_DECLARATIONS and BENCHMARK_DECLARATIONS.get(benchmark) != declaration:", "    if False:")),
        ("the claim alone under the cells declaration", observe_declaration, expected_declaration, lambda: with_source(
            _scitab(), "rule_text", "    return claim if declaration else RULE_TEMPLATE.format(claim=claim)", "    return RULE_TEMPLATE.format(claim=claim)")),
        ("the sign test at .05", observe_tests, expected_tests, lambda: patched(st, "FIGURES", dict(st.FIGURES, alpha_one_sided=.0125))),
        ("alpha not above .05", observe_tests, expected_tests, lambda: patched(st, "FIGURES", dict(st.FIGURES, alpha_one_sided=.2))),
        ("the set key recomputed", observe_bar, expected_bar, lambda: with_source(
            st, "open_bar", 'if bar.get("set_key") != fresh_once.set_key(inputs["ids"], inputs["keys"]):', "if False:")),
        ("the groups recomputed", observe_bar, expected_bar, lambda: with_source(st, "open_bar", 'if bar.get("groups") != ft.one_per_group(inputs, documents):', "if False:")),
        ("the comparator rule", observe_bar, expected_bar, lambda: with_source(st, "open_bar", 'if bar.get("comparator_rule") != COMPARATOR_RULE:', "if False:")),
        ("B1 the fresh file's prompts", observe_b1_groups, expected_b1_groups, lambda: with_source(
            st, "b1_questions", 'if sorted(value["prompts"], key=lambda p: p["prompt_id"]) != pinned or value["config"] != fresh["config"]:', "if False:")),
        ("the fresh file pinned", observe_b1_groups, expected_b1_groups, lambda: with_source(st, "b1_questions", "if _sha(fresh_prompts) != FRESH_PROMPTS_SHA256:", "if False:")),
        ("B1 on the base model", observe_b1_groups, expected_b1_groups, lambda: with_source(
            st, "b1_models", 'if model.get("adapter_applied") or model.get("adapter_sha256"):', "if False:")),
        ("the workload is the build's", observe_entries, expected_entries, lambda: with_source(st, "entry_digests", "if files != expected:", "if False:")),
        ("the build carries the declaration", observe_entries, expected_entries, lambda: with_source(st, "entry_digests", "if not declared(bundle):", "if False:")),
        ("the declaration on the heading", observe_entries, expected_entries, lambda: with_source(
            st, "declared", 'return any(r.category == "conv-cdoc-01" and r.compare == DECLARATION.split(": ")[1] for r in rules)',
            'return any("[%s]" % DECLARATION in path.read_text(encoding="utf-8") for path in (Path(bundle) / "conventions").glob("*.md"))')),
        ("B1 on the pinned weights", observe_b1_groups, expected_b1_groups, lambda: with_source(
            st, "b1_models", 'if not model.get("digest") or model.get("digest") != B1_BASE_DIGESTS[named]:', "if False:")),
        ("status and evidence fixed", observe_bar, expected_bar, lambda: with_source(
            st, "entry_digests", '"status": _sha(folder / "FINAL_STATUS.json"),', '"status": None,')),
        ("every item labelled", observe_no_label, expected_no_label, lambda: with_source(st, "every_item", "    if not missing:\n", "    if True:\n")),
        ("the first attempt alone", observe_attempt, expected_attempt, lambda: with_source(
            st, "first_attempt", 'if value["number"] != FIGURES["attempt"]:', "if False:")),
        ("a labelled effect", observe_effect, expected_effect, lambda: with_source(st, "development_effect", 'if value["label"] not in EFFECT_LABELS:', "if False:")),
        ("the marker file as it stands", observe_marker_alone, expected_marker_alone, lambda: with_source(
            fresh_once, "marker_named", 'if marker.is_file() and key in marker.read_text(encoding="utf-8"):', "if False:")),
        ("a B1 pass of these prompts", observe_before, expected_before, lambda: with_source(
            st, "validate_before", '    pair_judge.finished_pass(inputs["b1_prompts"], b1_run)\n    b1_models', "    b1_models")),
        ("a status that reads", observe_before, expected_before, lambda: with_source(
            st, "validate_before", "raise ValueError(\"a batch entry's status cannot be read: \" + document) from None", 'assessment = "passed"')),
        ("a run to read", observe_before, expected_before, lambda: with_source(st, "validate_before", 'if resolved["run_dir"] is None:', "if False:")),
        ("git grep that fails", observe_grep, expected_grep, lambda: with_source(
            fresh_once, "marker_named", "if found is None or found.returncode not in (0, 1):", "if found is None:")),
        ("C_BAR item 1", observe_tests, expected_tests, lambda: with_source(st, "tests", '"above_b1": cr.above(BENCHMARK, system, None, other)', '"above_b1": True')),
        ("precision", observe_tests, expected_tests, lambda: with_source(st, "tests", "precision = ft.precision_holds(system, other)", "precision = True")),
        ("the chance tail", observe_tests, expected_tests, lambda: patched(st, "FIGURES", dict(st.FIGURES, chance_at_most=1.0))),
        ("the flagged share", observe_tests, expected_tests, lambda: patched(st, "FIGURES", dict(st.FIGURES, flagged_share_at_most=1.0))),
        ("void: entries passed", observe_void, expected_void, lambda: with_source(st, "void_reasons", 'if share < FIGURES["entries_passed_at_least"]:', "if False:")),
        ("void: each B1 group", observe_void, expected_void, lambda: with_source(
            st, "void_reasons", 'for g, v in sorted(b1_readable.items()) if v < FIGURES["readable_at_least"]]',
            'for g, v in [("b1", sum(b1_readable.values()) / len(b1_readable))] if v < FIGURES["readable_at_least"]]')),
    ]
    results = []
    for name, observe, expected, neutralise in proofs:
        observe = ftc.whole(observe)
        results.append(prove_effect(name=name, validate=lambda: st.FIGURES["documents"] == 100, observe=observe,
                                    check=lambda: ("PASS" if observe() == expected() else "FAIL", name), neutralise=neutralise))
    return "PASS", ("%d proofs on an invented fresh set, an invented sealed batch, canned B1 replies and invented B3 rows, no model and no "
                    "real key: the bar's figures, attempt, size, power and entries, B1's groups, the exposure search, the read key by "
                    "content, the committed marker, the count before any fresh key, the verdict, and the void") % len(results)


if __name__ == "__main__":
    print(run_checks())
