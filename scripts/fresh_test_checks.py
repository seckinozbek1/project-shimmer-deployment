"""Gate check 325, D-S56 item 4 and D-S62 item 1 (benchmark/baselines/fresh_test.py; D-316's thirteen
items). No model, no real key: invented fresh and calibration sets in ContraDoc's own release shape,
built by the adapter itself, an invented adapter digest and canned replies, in a temporary folder
with its own git repository. Each proof is neutralise, fail, restore, pass.

1. the bar's figures and attempt are the code's, the stated power is the power of the stated effect,
   alpha .05 and 100 documents among them, and a set of another size is refused;
2. one document per group, against the groups file and the build's parts record;
3. the calibration's documents (the real calibrator's own output form, staged ids) are mapped to
   source ids: one fresh by source id, one of half B, one outside half A are each refused;
4. the pair question is the pipeline's, byte for byte, and the whole rendered model input (the
   chat template's turns included) is what AgentWrapper.call_choice sends;
5. a fitted temperature changes the probabilities and not their order, and the read applies it;
6. the pass is held to its form: the calibrated adapter on choice_trained and on no other group;
7. half A's questions join choice_trained alone, unchanged, and the read never counts them;
8. the read key is the content: re-spaced inputs, or another calibration of the same adapter, are
   refused as read; a commit naming the key refuses the read, and so does git that cannot answer;
9. the read is counted before the scorer opens any fresh key, and the power at half A's effect is
   written before it is counted;
10. a byte mismatch under the bar refuses before the count and reads nothing; a refit that differs
    from the calibration refuses the read, and the refit runs before the count, so it reads nothing;
11. keep needs the sign test, C_BAR's items 1 and 5, precision, the chance tail and the flagged
    share; void under 95 percent readable per B1 group and under 90 percent of documents whole.
"""
import contextlib
import importlib
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "benchmark" / "baselines"), str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "adapters"),
             str(ROOT / "benchmark" / "adapters" / "contradoc")):
    if path not in sys.path:
        sys.path.insert(0, path)

import choice_decision as cd  # noqa: E402
import choice_decision_checks as cdc  # noqa: E402
import either_test_checks as etc  # noqa: E402
import fresh_once  # noqa: E402
import passage_pairs  # noqa: E402
import reply_records  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

ft = importlib.import_module("fresh_test")
cr = importlib.import_module("choice_read")
doc_judge = importlib.import_module("doc_judge")
pair_judge = importlib.import_module("pair_judge")
choice_judge = importlib.import_module("choice_judge")
bare_model = importlib.import_module("bare_model")
judge_calibration = importlib.import_module("judge_calibration")
from common import cli, ids  # noqa: E402
contradoc = importlib.import_module("adapter")
patched, with_source, caught = cdc.patched, cdc.with_source, cdc.caught
ADAPTER = {"path": "fixture/adapter", "weights_sha256": "a" * 64, "config_sha256": "c" * 64}
GOLD = [True, True, True, False, False, False]
TEXT = {True: "The quay of number %d was sold to the city in the year 1901.\n\nThe quay of number %d has never been sold to the city at all.\n",
        False: "The bakery of number %d sells bread to the town each day.\n\nThe bakery of number %d stands near the town market.\n"}


def small():
    """FIGURES for the invented set's size, the stated power computed as the bar computes it."""
    figures = dict(ft.FIGURES, documents=len(GOLD))
    with patched(ft, "FIGURES", figures):
        figures["power"] = ft.stated_power()
    return figures


SMALL = small()
REAL_FIGURES = ft.FIGURES


def development_ids(prefix, count, start=0):
    """Source ids whose hash side is development, so the adapter's own build takes them."""
    out, n = [], start
    while len(out) < count:
        sid = "%s%d" % (prefix, n)
        if ids.split_side(ids.key_string(sid)) == ids.DEVELOPMENT:
            out.append(sid)
        n += 1
    return out


def source_file(path, rows):
    """A ContraDoc release file ({pos, neg} of records) of (source id, contradicts, number)."""
    value = {"pos": {}, "neg": {}}
    for sid, gold, n in rows:
        text = TEXT[gold] % (n, n)
        record = {"text": text, "unique id": sid, "doc_type": "news"}
        if gold:
            first, second = [line for line in text.split("\n") if line]
            record.update(evidence=second, **{"ref sentences": [first]})
        value["pos" if gold else "neg"][sid] = record
    Path(path).write_text(json.dumps(value), encoding="utf-8")
    return path


def staged(folder, name, rows, declaration=None):
    """The adapter's own development build of `rows`: (bundle folder, items, keys, source file)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    source = source_file(folder / (name + "_source.json"), rows)
    out = folder / name
    cli.build(contradoc, source, out, development=True, **({"rule_declaration": declaration} if declaration else {}))
    items = out / "items.json"
    keys = sorted(str(p) for p in out.glob("*/answer_key.json"))
    return out, items, keys, source


class Canned(etc.Canned):
    """The trained group answers Yes with a margin a temperature below 1 sharpens past .95; the
    untrained group with a wide margin; B1 as either_test's checks, by the item each prompt names."""

    def prepare(self):
        adapter = self.reader.get("adapter")
        return {"model_id": self.reader["model_id"], "digest": "fixture",
                "checkpoint": {"checkpoint": "base", "adapter_applied": bool(adapter), "adapter_sha256": adapter["weights_sha256"] if adapter else None}}

    def choose(self, system, user, answers):
        question = cd.bind(cd.declare(user, answers), cdc.encode)
        strong = 3.0 if self.reader.get("adapter") else 12.0
        row = cdc.logits(Y=strong) if "never been sold" in user else cdc.logits(N=strong)
        decision = dict(cd.decide(lambda p: row, question, None), logits_dtype="torch.float32", model_logits_dtype="torch.float16")
        return {"decision": decision, "payload": user, "form": "rendered_prompt", "attention": {}, "prefill": {"prefill_seconds": .01, "chunks": 0}}


def trained_reader(group, allowance, on=(ft.TRAINED,)):
    return dict(cdc.READER, adapter=ADAPTER) if group["group"] in on else dict(cdc.READER)


def read_before(folder, value):
    """A choice prompts file 'already read on half A': this sample's choice questions under other
    document and prompt ids, with half A's order controls added as choice_judge.py adds them."""
    rename = lambda d: "h" + d
    prompts = [dict(p, document_id=rename(p["document_id"]), prompt_id="h" + p["prompt_id"]) for p in value["prompts"]
               if p.get("form") == doc_judge.CHOICE_FORM and p["group"] == ft.UNTRAINED]
    documents = {rename(d): doc for d, doc in value["documents"].items()}
    prompts += [dict(p, prompt_id="h-control-" + p["prompt_id"]) for p in choice_judge.order_controls(value["config"], documents, prompts)]
    old = dict(value, documents=documents, prompts=prompts, prompt_count=len(prompts))
    path = Path(folder) / "read_before.json"
    path.write_text(json.dumps(old), encoding="utf-8")
    return path, prompts


def git(folder, *args):
    subprocess.run(["git", "-C", str(folder), *args], check=True, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


LEDGER = {"attempts": []}


def write_groups(root, fresh_ids, unread=None, moved=None):
    """The two pinned group files under `root` (the first half unread, the rest moved), and the
    GROUP_FILES to pin them: {name: (path, digest)}."""
    half = len(fresh_ids) // 2
    unread = unread if unread is not None else {sid: [sid] for sid in fresh_ids[:half]}
    moved = moved if moved is not None else {sid: {"group": sid, "side": "development"} for sid in fresh_ids[half:]}
    pinned = {}
    for name, value in (("unread", {"fresh_groups": unread}), ("moved", {"assignments": moved})):
        path = Path(root) / fresh_once.GROUP_FILES[name][0]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        pinned[name] = (fresh_once.GROUP_FILES[name][0], fresh_once._sha(path))
    return pinned


def git_out(folder, *args):
    return subprocess.run(["git", "-C", str(folder), *args], check=True, capture_output=True, text=True,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout


def repository(folder, fresh_ids=()):
    """A git repository standing in for the repository root, with one commit: the attempts ledger
    and the two group files."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    git(folder, "init", "-q")
    git(folder, "checkout", "-q", "-b", fresh_once.LOOP_REF[len("refs/heads/"):])
    for name, value in (("user.email", "fixture@example.invalid"), ("user.name", "fixture"), ("commit.gpgsign", "false")):
        git(folder, "config", name, value)
    (folder / "docs" / "loop").mkdir(parents=True, exist_ok=True)
    (folder / fresh_once.ATTEMPTS_FILE).write_text(json.dumps(LEDGER), encoding="utf-8")
    write_groups(folder, list(fresh_ids))
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "-m", "start")
    return folder


def sample(folder, config=ft.CONFIG_PATH, calibration_prompts=None, shared=None, declaration=None):
    """{inputs, value, half_a, half_b, fresh_staged}: an invented fresh set of six documents and a
    calibration set of eight, both built by the adapter; with `shared`, the calibration set also holds
    the fresh document of that index under its own source id."""
    folder = Path(folder)
    fresh_ids = development_ids("fresh-", len(GOLD))
    build, items, keys, source = staged(folder, "fresh", [(sid, gold, n) for n, (sid, gold) in enumerate(zip(fresh_ids, GOLD))], declaration)
    cal_rows = [(sid, n % 2 == 0, 100 + n) for n, sid in enumerate(development_ids("cal-", 8))]
    if shared is not None:
        cal_rows.append((fresh_ids[shared], GOLD[shared], shared))
    cal, cal_build_items, cal_keys, cal_source = staged(folder, "cal", cal_rows)
    cal_items = folder / "cal_bar_items.json"
    item_ids = [r["item_id"] for r in json.loads(cal_build_items.read_text(encoding="utf-8"))["items"]]
    cal_items.write_text(json.dumps({"contradoc": item_ids, "scitab": [], "left_out": []}), encoding="utf-8")
    ids_path = folder / "ids.json"
    ids_path.write_text(json.dumps({"documents": sorted(fresh_ids)}), encoding="utf-8")
    with patched(doc_judge, "_pinned", lambda path: True):
        known, _, _ = cr.universe(cal_keys, cal_items)
    half_a, half_b = cr.halves(known[ft.BENCHMARK])
    calibration = folder / "calibration.json"
    sources = judge_calibration.source_ids(sorted(half_a), cal_build_items)
    calibration.write_text(json.dumps(judge_calibration.calibration_value(ADAPTER["weights_sha256"], .5, .95, sources)), encoding="utf-8")
    labels = folder / "b1_labels"
    labels.mkdir()
    prompts = folder / "prompts.json"
    workloads = sorted(str(p.parent) for p in build.glob("*/answer_key.json"))
    with patched(pair_judge, "_words_allowed", True):
        value = ft.build(workloads, items, prompts, config, embed=lambda passages: None, calibration_prompts=calibration_prompts)
    etc.CURRENT["items"] = {p["user"]: p["item_id"] for p in value["prompts"] if p.get("form") == doc_judge.B1_FORM}
    inputs = {"prompts": str(prompts), "ids": str(ids_path), "items": str(items), "calibration": str(calibration),
              "parts": [str(build / "parts.json")], "keys": keys, "calibration_keys": cal_keys, "calibration_items": str(cal_items),
              "calibration_build_items": str(cal_build_items), "calibration_source": str(cal_source), "sources": [str(source)], "b1": str(labels)}
    fresh_staged = {r["source_document_id"]: r["document_id"] for r in json.loads(items.read_text(encoding="utf-8"))["items"]}
    cal_sources = {r["document_id"]: r["source_document_id"] for r in json.loads(cal_build_items.read_text(encoding="utf-8"))["items"]}
    return {"inputs": inputs, "value": value, "half_a": half_a, "half_b": half_b, "fresh_staged": fresh_staged, "fresh_ids": fresh_ids, "build": build,
            "cal_sources": cal_sources}


def same_refit(prompts, run, keys, items, source, b1, out, build_items):
    """The training session's calibrator, as the fixture has it: it writes the calibration the
    session wrote (judge_calibration.calibration_value, the real writer)."""
    Path(out).mkdir(parents=True, exist_ok=True)
    given = json.loads(Path(CURRENT["calibration"]).read_text(encoding="utf-8"))
    value = judge_calibration.calibration_value(given["adapter_weights_sha256"], given["temperature"] + CURRENT["drift"], given["threshold"],
                                                given["fitted_on_documents"])
    (Path(out) / "calibration.json").write_text(json.dumps(value), encoding="utf-8")
    return {"written": True}


CURRENT = {"calibration": None, "drift": 0.0}


def fixed_effect(inputs, run, fitted, out):
    """An invented half A effect for the fixture (5 wins, 1 loss of 30); the real one is half_a_effect's."""
    return {"wins": 5, "losses": 1, "documents": 30, "comparator": "judge_direct"}


@contextlib.contextmanager
def session(folder, reader_for=trained_reader, **kwargs):
    """A sample, its pass under `reader_for`, the fixture repository and pinned items."""
    folder = Path(folder)
    built = sample(folder / "set", **kwargs)
    run = folder / "run"
    doc_judge.run(built["inputs"]["prompts"], run, backend_factory=lambda reader, context: Canned(reader), reader_for=reader_for)
    CURRENT.update(calibration=built["inputs"]["calibration"], drift=0.0)
    root = repository(folder / "repository", built["fresh_ids"])
    pinned = write_groups(root, built["fresh_ids"])
    with patched(ft, "FIGURES", SMALL), patched(cr, "repository_root", lambda: root), patched(doc_judge, "_pinned", lambda path: True), \
            patched(fresh_once, "GROUP_FILES", pinned):
        yield built, run, root


def do_read(built, run, out, **kwargs):
    """The judge's part as the system read runs it: its bar, then prepare_judge before the count, then
    judge_figures (here with no count at all: the count is fresh_once's, proved in system_test_checks)."""
    bar = Path(out).parent / (Path(out).name + "_bar.json")
    bar.write_text(json.dumps(ft.bar_value(built["inputs"])), encoding="utf-8")

    def judged():
        value, before = ft.prepare_judge(bar, run, built["inputs"], out, calibrate=kwargs.get("calibrate", same_refit), effect=kwargs.get("effect", fixed_effect))
        return dict(ft.judge_figures(value, run, built["inputs"], out), power_before_read=before)
    return caught(judged)


# 1: the bar


def observe_bar():
    with tempfile.TemporaryDirectory() as folder, session(folder) as (built, run, root):
        inputs = built["inputs"]
        with patched(ft, "FIGURES", REAL_FIGURES):
            out = {"size": caught(lambda: ft.bar_value(inputs) and "barred")}
        good = ft.bar_value(inputs)
        for name, change in (("alpha", {"figures": dict(SMALL, alpha_one_sided=.0125)}), ("attempt", {"attempt": dict(good["attempt"], number=3)}),
                             ("ids", {"inputs": dict(good["inputs"], ids="x")}), ("calibration", {"inputs": dict(good["inputs"], calibration="x")})):
            path = Path(folder) / ("bar_" + name + ".json")
            path.write_text(json.dumps(dict(good, **change)), encoding="utf-8")
            out[name] = caught(lambda: ft.open_bar(path, inputs) and "read")
        path = Path(folder) / "good.json"
        path.write_text(json.dumps(good), encoding="utf-8")
        out["good"] = caught(lambda: bool(ft.open_bar(path, inputs)))
        with patched(ft, "FIGURES", dict(SMALL, power=dict(SMALL["power"], **{"6": .9}))):
            out["power"] = caught(lambda: ft.bar_value(inputs) and "barred")
    out["figures"] = {k: ft.FIGURES[k] for k in ("alpha_one_sided", "documents", "power")}
    out["computed"] = ft.stated_power()
    return out


def expected_bar():
    return {"size": "ValueError: the test is sized for 100 documents (power 0.80); this set has 6 (power at 62: 0.59)",
            "alpha": "ValueError: the bar states other figures than the code's", "attempt": "ValueError: the bar states other figures than the code's",
            "ids": "ValueError: the bar names other inputs: ids", "calibration": "ValueError: the bar names other inputs: calibration", "good": True,
            "power": "ValueError: the stated power is not the power of the stated effect",
            "figures": {"alpha_one_sided": .05, "documents": 100, "power": {"62": .59, "100": .80}}, "computed": {"62": .59, "100": .80}}


# 2: one document per group


def observe_groups():
    with tempfile.TemporaryDirectory() as folder, session(folder) as (built, run, root):
        inputs = built["inputs"]
        fresh = built["fresh_ids"]
        first, second = fresh[:2]
        documents = list(built["fresh_staged"].values())
        out = {"good": caught(lambda: bool(ft.bar_value(inputs)))}
        lower = next(x for x in ("sibling-%d" % n for n in range(1000)) if doc_judge._sha("20261108:" + x) < doc_judge._sha("20261108:" + first))
        rest = {sid: [sid] for sid in fresh[2:]}
        for name, unread in (("shared", dict(rest, g=[first, second])), ("not lowest", dict(rest, **{first: [first, lower], second: [second]})),
                             ("missing", rest)):
            pinned = write_groups(root, fresh, unread=unread, moved={})
            parts = inputs["parts"]
            if name == "shared":
                record = json.loads(Path(parts[0]).read_text(encoding="utf-8"))
                for row in record["documents"]:
                    if row["source_document_id"] in (first, second):
                        row["cluster"] = "g"
                parts = [str(Path(folder) / "shared_parts.json")]
                Path(parts[0]).write_text(json.dumps(record), encoding="utf-8")
            with patched(fresh_once, "GROUP_FILES", pinned):
                out[name] = caught(lambda: ft.one_per_group(dict(inputs, parts=parts), documents) and "kept")
        write_groups(root, fresh, unread=rest, moved={})
        out["not the pinned file"] = caught(lambda: ft.one_per_group(inputs, documents) and "kept")
        return {k: (v.split(":")[0] + ": " + v.split(": ")[1].split(":")[0] if isinstance(v, str) and v.startswith("ValueError") else v) for k, v in out.items()}


def expected_groups():
    return {"good": True, "shared": "ValueError: two fresh documents of one group",
            "not lowest": "ValueError: a fresh document is not its group's lowest SHA-256",
            "missing": "ValueError: a fresh document's group is not in the groups file",
            "not the pinned file": "ValueError: the unread groups file is not the pinned one"}


# 3: the calibration's documents


def observe_calibration():
    with tempfile.TemporaryDirectory() as folder, session(folder, shared=None) as (built, run, root):
        inputs, out = built["inputs"], {}
        given = json.loads(Path(inputs["calibration"]).read_text(encoding="utf-8"))
        source = built["cal_sources"]
        for name, documents in (("half B", [source[d] for d in sorted(built["half_a"])[:1] + sorted(built["half_b"])[:1]]),
                                ("not built", [source[d] for d in sorted(built["half_a"])] + ["no-such-document"])):
            path = Path(folder) / (name.replace(" ", "_") + ".json")
            path.write_text(json.dumps(dict(given, fitted_on_documents=documents)), encoding="utf-8")
            out[name] = caught(lambda: ft.calibration_documents(dict(inputs, calibration=str(path)), ft.calibration(path)) and "kept")
        out["good"] = caught(lambda: ft.calibration_documents(inputs, ft.calibration(inputs["calibration"])))
    for index in range(len(GOLD)):
        with tempfile.TemporaryDirectory() as folder, session(folder, shared=index) as (built, run, root):
            staged_id = built["fresh_staged"][built["fresh_ids"][index]]
            if staged_id not in built["half_a"]:
                continue
            inputs = built["inputs"]
            given = json.loads(Path(inputs["calibration"]).read_text(encoding="utf-8"))
            path = Path(folder) / "fresh.json"
            path.write_text(json.dumps(dict(given, fitted_on_documents=sorted(built["cal_sources"][d] for d in built["half_a"]))), encoding="utf-8")
            out["fresh"] = caught(lambda: ft.calibration_documents(dict(inputs, calibration=str(path)), ft.calibration(path)) and "kept")
            break
    return out


def expected_calibration():
    return {"half B": "ValueError: the calibration was fitted on a half B document",
            "not built": "ValueError: a calibration document is in no calibration build: no-such-document", "good": 4,
            "fresh": "ValueError: the calibration was fitted on a fresh document"}


# 4: the pipeline's question, and the whole input


def observe_question():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        value = caught(lambda: sample(folder / "first")["value"])
        if isinstance(value, str):  # the replay's loader holds each prompt to its template too
            return {"built": value}
        template = passage_pairs.load_config()["decision"]["template"]
        same, count = True, 0
        for p in value["prompts"]:
            if p.get("form") != doc_judge.CHOICE_FORM:
                continue
            count += 1
            text = value["documents"][p["document_id"]]["text"]
            first, second = (text[slice(*p["span_a"])], text[slice(*p["span_b"])])
            same = same and p["user"] == template.replace("{passage_a}", first).replace("{passage_b}", second)
        config = json.loads(ft.CONFIG_PATH.read_text(encoding="utf-8"))
        config["choice"]["forms"]["pair"]["template"] += " Answer at once."
        other = folder / "other.json"
        other.write_text(json.dumps(config), encoding="utf-8")
        refused = caught(lambda: sample(folder / "again", other) and "built")
        return {"choice prompts": count, "the pipeline's bytes": same, "another question": refused}


def expected_question():
    return {"choice prompts": 24, "the pipeline's bytes": True,
            "another question": "ValueError: the config's pair question is not the pipeline's (config/passage_pairs.json, decision)"}


class TemplateTok(cdc.Tok):
    """A chat template that adds its own system turn when none is sent, as some models' do."""

    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        if messages[0]["role"] != "system":
            messages = [{"role": "system", "content": "DEFAULT"}] + list(messages)
        return super().apply_chat_template(messages, tokenize, add_generation_prompt)


def observe_whole_input():
    """One fresh question through LocalBackend.choose (the replay) and AgentWrapper.call_choice (the
    product), with the same tokenizer: the whole rendered input each sends, and the tokens scored."""
    with tempfile.TemporaryDirectory() as folder:
        value = sample(Path(folder) / "set")["value"]
    prompt = next(p for p in value["prompts"] if p.get("form") == doc_judge.CHOICE_FORM)
    answers = doc_judge.choice_answers(value["config"], prompt)
    model = cdc.Model()
    backend = bare_model.LocalBackend(dict(cdc.READER, attention=bare_model.attention_record()), bare_model.RunContext(".", "r"))
    backend._tok, backend._mdl = TemplateTok(), model
    with patch.dict(sys.modules, {"torch": cdc.FAKE_TORCH}), patched(bare_model, "b1_attention", cdc._observed_attention):
        replay = backend.choose(prompt.get("system"), prompt["user"], answers)
    with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {"torch": cdc.FAKE_TORCH}), \
            patched(cdc.agent_wrapper, "_load_qwen", lambda model_id: (TemplateTok(), cdc.Model())), patched(cdc.final_models, "pinned_attention", cdc._pinned):
        context = bare_model.RunContext(folder, "run-choice")
        wrapper = cdc._wrapper(context, folder)
        wrapper._cost_call_id = "call-1"
        product = wrapper.call_choice(prompt["user"], answers, .5)
        record = reply_records.records(Path(folder) / "audit" / "model_replies")[0]
    tokens = lambda d: [a["token_id"] for a in d["answers"]]
    return {"same input": replay["payload"] == record["payload"]["text"], "default turn kept": replay["payload"].startswith("<s>DEFAULT<u>"),
            "same tokens": tokens(replay["decision"]) == tokens(product.parsed), "product ok": product.ok}


def expected_whole_input():
    return {"same input": True, "default turn kept": True, "same tokens": True, "product ok": True}


# 5: the temperature


def observe_tempered():
    decision = cd.decide(lambda p: cdc.logits(Y=2.0, N=1.0), cdc.bound(), None)
    probs = lambda d: [round(a["probability"], 4) for a in d["answers"]]
    hot, cold = cd.tempered(decision, 2.0), cd.tempered(decision, .5)
    return {"one": probs(cd.tempered(decision, 1)) == probs(decision), "hot": probs(hot), "cold": probs(cold),
            "order": [a["label"] for a in sorted(cold["answers"], key=lambda a: -a["probability"])] == [a["label"] for a in sorted(decision["answers"], key=lambda a: -a["probability"])],
            "mass": hot["declared_mass"] == decision["declared_mass"], "zero": caught(lambda: cd.tempered(decision, 0))}


def expected_tempered():
    # logits 2, 1, 0: at 2 they are 1, .5, 0 (e, e**.5, 1 over their sum); at .5, 4, 2, 0
    return {"one": True, "hot": [0.5065, 0.3072, 0.1863], "cold": [0.8668, 0.1173, 0.0159], "order": True, "mass": True,
            "zero": "ChoiceRefused: a temperature is a positive number"}


# 6 to 10: the pass and the read


def observe_read():
    with tempfile.TemporaryDirectory() as folder:
        first = sample(Path(folder) / "first")["value"]
        before = read_before(Path(folder), first)[0]
        with session(Path(folder) / "s", calibration_prompts=before) as (built, run, root):
            result = do_read(built, run, Path(folder) / "out")
            if isinstance(result, str):
                return result
            forms = {}
            for p in built["value"]["prompts"]:
                forms[(p.get("form"), p["group"])] = forms.get((p.get("form"), p["group"]), 0) + 1
    return {"forms": sorted("%s %s %d" % (f, g, n) for (f, g), n in forms.items()), "result": result["result"], "reading": result["reading"],
            "comparator": result["comparator"], "trained right": result["trained"]["right"], "untrained right": result["untrained"]["right"],
            "placed": result["placed"]["placed"], "beside": result["beside"], "readable": result["readable"], "descriptive": result["descriptive"],
            "attempt": result["attempt"]["number"], "power before": result["power_before_read"]["power"],
            "label": result["power_before_read"]["label"], "half B": result["power_before_read"]["half_b"]["power"],
            "models": sorted(g for g, m in result["models"].items() if m["adapter_sha256"])}


def expected_read():
    # the power before the read is the power at the fixture's own size, 6 documents, at the invented 5 wins and 1 loss of 30
    return {"forms": ["b1 judge_direct 6", "b1 judge_reason 6", "choice choice_direct 12", "choice choice_trained 18"], "result": "drop",
            "reading": "descriptive only: not shown at this size", "comparator": "judge_reason", "trained right": 3, "untrained right": 3, "placed": 3,
            "beside": {"trained_against_untrained": {"wins": 0, "losses": 0, "tested": False}, "untrained_against_comparator": {"wins": 0, "losses": 0, "tested": False}},
            "readable": {"trained_prompts": 1.0, "trained_whole_documents": 1.0, "b1_prompts": {"judge_direct": 1.0, "judge_reason": 1.0}},
            "descriptive": True, "attempt": 1, "power before": 0.0006, "label": "in-sample, threshold chosen on these rows", "half B": None,
            "models": ["choice_trained"]}


def observe_form():
    out = {}
    for name, reader in (("no adapter", lambda g, a: dict(cdc.READER)),
                         ("adapter on the untrained group", lambda g, a: trained_reader(g, a, on=(ft.TRAINED, ft.UNTRAINED))),
                         ("adapter on a B1 group", lambda g, a: trained_reader(g, a, on=(ft.TRAINED, "judge_direct")))):
        with tempfile.TemporaryDirectory() as folder, session(folder, reader_for=reader) as (built, run, root):
            out[name] = do_read(built, run, Path(folder) / "out")
    return {k: v if isinstance(v, str) else v.get("result") for k, v in out.items()}


def expected_form():
    return {"no adapter": "ValueError: choice_trained was not read with the calibrated adapter",
            "adapter on the untrained group": "ValueError: group choice_direct had an adapter applied",
            "adapter on a B1 group": "ValueError: group judge_direct had an adapter applied"}


def observe_half_a():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        first = sample(folder / "first")["value"]
        path, before = read_before(folder, first)
        value = sample(folder / "second", calibration_prompts=path)["value"]
        added = [p for p in value["prompts"] if p["prompt_id"].startswith("h")]
        half = set(cr.split({d: {"benchmark": "contradoc"} for d in {p["document_id"] for p in before}})["contradoc"][0])
        source = {p["prompt_id"]: p for p in before}
        return {"added": len(added), "all of half A": {p["document_id"] for p in added} == half,
                "unchanged": all(p["user"] == source[p["prompt_id"]]["user"] and p["user_sha256"] == source[p["prompt_id"]]["user_sha256"] for p in added),
                "group": sorted({p["group"] for p in added}), "order controls": sum(1 for p in added if p.get("order_control")),
                "fresh documents": len([d for d in value["documents"] if not d.startswith("h")])}


def expected_half_a():
    # six documents, two questions each (one pair in both orders); half A holds three of them
    return {"added": 6, "all of half A": True, "unchanged": True, "group": ["choice_trained"], "order controls": 0, "fresh documents": 6}


def respace(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    Path(path).write_text(json.dumps(value, indent=3), encoding="utf-8")


def observe_ledger():
    """The attempt is one past the tracked ledger's rows; a modified or untracked ledger numbers none."""
    with tempfile.TemporaryDirectory() as folder, session(folder) as (built, run, root):
        out = {"number": fresh_once.attempt()["number"]}
        ledger = root / fresh_once.ATTEMPTS_FILE
        ledger.write_text(json.dumps({"attempts": [{"attempt": 1, "set_key": "x"}]}), encoding="utf-8")
        out["modified"] = caught(lambda: fresh_once.attempt()["number"])
        ledger.write_text(json.dumps(LEDGER), encoding="utf-8")
        (root / fresh_once.MARKER_FILE).write_text("- %s t r\n" % ("k" * 64), encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "a marked read with no ledger row")
        out["marker without its row"] = caught(lambda: fresh_once.attempt()["number"])
        git(root, "rm", "-q", fresh_once.ATTEMPTS_FILE)
        git(root, "commit", "-q", "-m", "no ledger")
        out["no ledger on the loop branch"] = caught(lambda: fresh_once.attempt()["number"])
    return out


def expected_ledger():
    return {"number": 1, "modified": "ValueError: the attempts ledger here differs from the loop branch's: " + fresh_once.ATTEMPTS_FILE,
            "marker without its row": "ValueError: the attempts ledger and the reads marker name different reads",
            "no ledger on the loop branch": "ValueError: the loop branch holds no attempts ledger: " + fresh_once.ATTEMPTS_FILE}


def observe_refused():
    return {"read": caught(lambda: ft.read() and "read"), "command": caught(lambda: ft.main(["read"]) and "read")}


def expected_refused():
    message = "ValueError: the judge-alone read is refused: the fresh set is read once, by the system read (D-S70, D-326)"
    return {"read": message, "command": message}


def observe_refit():
    with tempfile.TemporaryDirectory() as folder, session(folder) as (built, run, root):
        CURRENT["drift"] = .25
        refused = do_read(built, run, Path(folder) / "out")
    return {"refused": refused}


def expected_refit():
    return {"refused": "ValueError: the calibration is not the refit's: no read"}


CANDIDATE = dict(etc.CANDIDATE, accuracy=.7, net=16)
OTHER = dict(etc.OTHER, accuracy=.6, net=4)
PLACE = {"placed": 4, "flagged_with_two_marks": 6}


def observe_undefined():
    return {"none discordant": ft.power_at_effect(0, 0, 30)["power"], "why": ft.power_at_effect(0, 0, 30)["means"].split(":")[0],
            "one each": ft.power_at_effect(1, 1, 30)["power"] is not None}


def expected_undefined():
    return {"none discordant": None, "why": "undefined", "one each": True}


def observe_mismatch():
    """A byte mismatch under the bar refuses the judge's part before the count."""
    with tempfile.TemporaryDirectory() as folder, session(folder) as (built, run, root):
        bar = Path(folder) / "bar.json"
        bar.write_text(json.dumps(ft.bar_value(built["inputs"])), encoding="utf-8")
        respace(built["inputs"]["ids"])
        refused = caught(lambda: ft.prepare_judge(bar, run, built["inputs"], Path(folder) / "out", calibrate=same_refit, effect=fixed_effect) and "prepared")
    return {"refused": refused}


def expected_mismatch():
    return {"refused": "ValueError: the bar names other inputs: ids"}


def observe_tests():
    keep = lambda c=None, o=None, w=6, l=0: (lambda t: "keep" if all(t.values()) else sorted(k for k, v in t.items() if not v))(
        ft.tests(c or CANDIDATE, o or OTHER, w, l))
    return {"keep": keep(), "five of five": keep(w=5), "more losses": keep(w=2, l=6), "precision": keep(c=dict(CANDIDATE, right=14, false=6, precision=.7)),
            "chance": keep(c=dict(CANDIDATE, chance_tail=.06)), "flagged": keep(c=dict(CANDIDATE, flagged=55, right=50, false=5)),
            "no comparator flag": keep(o=dict(OTHER, flagged=0, right=0, false=0, precision=None)),
            "few comparator flags, under .75": keep(c=dict(CANDIDATE, right=14, false=6, precision=.7), o=dict(OTHER, flagged=3, right=3, false=0, precision=1.0)),
            "few comparator flags, at .8": keep(c=dict(CANDIDATE, right=16, false=4, precision=.8), o=dict(OTHER, flagged=3, right=3, false=0, precision=1.0))}


def expected_tests():
    # under 5 comparator flags the rule is B1's whole-sample ContraDoc precision, .75 (C_BAR item 4)
    return dict(etc.expected_tests(), **{"no comparator flag": "keep", "few comparator flags, under .75": ["precision"],
                                         "few comparator flags, at .8": "keep"})


def observe_c_bar():
    keep = lambda c=CANDIDATE, o=OTHER, p=PLACE, py=None: (lambda t: "keep" if all(t.values()) else sorted(k for k, v in t.items() if not v))(
        ft.tests(c, o, 6, 0, p, py or {"net": 10}))
    return {"keep": keep(), "accuracy not above": keep(c=dict(CANDIDATE, accuracy=.6)), "net below": keep(c=dict(CANDIDATE, net=3)),
            "two placed": keep(p=dict(PLACE, placed=2)), "placed share": keep(p={"placed": 3, "flagged_with_two_marks": 7}),
            "python": keep(py={"net": 16})}


def expected_c_bar():
    return {"keep": "keep", "accuracy not above": ["above_b1"], "net below": ["above_b1", "above_python"], "two placed": ["placed", "placed_share"],
            "placed share": ["placed_share"], "python": ["above_python"]}


def _rows(documents, failed):
    rows = []
    for d in range(documents):
        for n in range(10):
            decision = None if (d < failed and n == 0) else {"answers": [{"label": "x", "probability": .9}, {"label": "y", "probability": .1}]}
            rows.append({"document_id": "d%d" % d, "decision": decision})
    return rows, {"d%d" % d: [] for d in range(documents)}


def observe_void():
    two, three = _rows(20, 2), _rows(20, 3)
    return {"two documents": ft.void_reasons(*two, {"judge_direct": 1.0, "judge_reason": 1.0})[0],
            "three documents": ft.void_reasons(*three, {"judge_direct": 1.0, "judge_reason": 1.0})[0],
            "one B1 group": ft.void_reasons(*two, {"judge_direct": 1.0, "judge_reason": .9})[0]}


def expected_void():
    return {"two documents": [], "three documents": ["documents with every pair readable 0.850"], "one B1 group": ["judge_reason prompts readable 0.900"]}


def whole(observe):
    """`observe` with any failure as its observation. A neutralised function is compiled in a copy of
    the module's globals, so it can fail where the fixture's patches do not reach it; that is a
    changed observation, which the proof must see, never an error that stops it."""
    def observed():
        try:
            return observe()
        except Exception as exc:
            return "raised " + type(exc).__name__ + ": " + str(exc)
    return observed


def run_checks():
    proofs = [
        ("the bar's figures", observe_bar, expected_bar, lambda: with_source(ft, "open_bar", 'or bar.get("figures") != FIGURES', "")),
        ("the attempt", observe_bar, expected_bar, lambda: with_source(ft, "open_bar", ' or bar.get("attempt") != fresh_once.attempt()', "")),
        ("the attempt is the loop branch's ledger", observe_ledger, expected_ledger, lambda: with_source(
            fresh_once, "attempt", 'if working.is_file() and working.read_text(encoding="utf-8").replace("\\r\\n", "\\n") != text.replace("\\r\\n", "\\n"):', "if False:")),
        ("the ledger tied to the marker", observe_ledger, expected_ledger, lambda: with_source(
            fresh_once, "attempt", 'if marked != {r.get("set_key") for r in rows}:', "if False:")),
        ("the bar's inputs", observe_bar, expected_bar, lambda: with_source(ft, "open_bar", "if (bar.get(\"inputs\") or {}).get(name) != got[name]:", "if False:")),
        ("the set's size", observe_bar, expected_bar, lambda: with_source(ft, "bar_value", 'if len(documents) != FIGURES["documents"]:', "if False:")),
        ("the power stated", observe_bar, expected_bar, lambda: with_source(ft, "bar_value", 'if FIGURES["power"] != stated_power():', "if False:")),
        ("two of one group", observe_groups, expected_groups, lambda: with_source(ft, "one_per_group", "if group in seen:", "if False:")),
        ("the lowest of its group", observe_groups, expected_groups, lambda: with_source(
            ft, "one_per_group", 'if source != min(groups[group], key=lambda d: doc_judge._sha("20261108:" + d)):', "if False:")),
        ("a group the file lacks", observe_groups, expected_groups, lambda: with_source(
            ft, "one_per_group", "if group is None or source not in groups.get(group, []):", "if group is None:")),
        ("fresh by source id", observe_calibration, expected_calibration, lambda: with_source(
            ft, "calibration_documents", 'if fresh & set(fitted["fitted_on_documents"]):', "if False:")),
        ("half B", observe_calibration, expected_calibration, lambda: with_source(
            ft, "calibration_documents", "if documents & half_b:", "if False:")),
        ("a document no build holds", observe_calibration, expected_calibration, lambda: with_source(ft, "calibration_documents", "if missing:", "if False:")),
        ("the pipeline's bytes", observe_question, expected_question, lambda: with_source(
            ft, "build", 'user = passage_pairs.render(pipeline, first["text"], second["text"])', 'user = passage_pairs.render(pipeline, second["text"], first["text"])')),
        ("the pipeline's question", observe_question, expected_question, lambda: with_source(
            ft, "pipeline_question", 'if form["template"] != pipeline["decision"]["template"] or', 'if False and')),
        ("the whole input", observe_whole_input, expected_whole_input, lambda: cdc.method_with_source(
            bare_model.LocalBackend, bare_model, "_render", '([] if system is None else [{"role": "system", "content": system}])', '[{"role": "system", "content": ""}]')),
        ("the temperature", observe_tempered, expected_tempered, lambda: with_source(cd, "tempered", "held = _log_sum([v / temperature for v in logs])",
                                                                                     "held = _log_sum(logs); temperature = 1")),
        ("the read applies the temperature", observe_read, expected_read, lambda: with_source(
            ft, "choice_rows", '"decision": cd.tempered(decision, temperature) if decision else None', '"decision": decision')),
        ("the adapter on choice_trained", observe_form, expected_form, lambda: with_source(
            ft, "pass_models", "if group == TRAINED and not (applied and digest == adapter):", "if False:")),
        ("no adapter elsewhere", observe_form, expected_form, lambda: with_source(ft, "pass_models", "if group != TRAINED and (applied or digest):", "if False:")),
        ("half A only", observe_half_a, expected_half_a, lambda: with_source(ft, "half_a", ' and not p.get("order_control") and p["document_id"] in keep', "")),
        ("half A on the trained group", observe_half_a, expected_half_a, lambda: with_source(
            ft, "half_a", 'dict(p, group=group["group"], backend=group["backend"], agent=group["agent"], checkpoint=group["checkpoint"])', "dict(p)")),
        ("an undefined power", observe_undefined, expected_undefined, lambda: with_source(
            ft, "power_at_effect", '"power": None, "low": None, "high": None,', '"power": 0.0, "low": 0.0, "high": 0.0,')),
        ("a byte mismatch refuses", observe_mismatch, expected_mismatch, lambda: with_source(
            ft, "open_bar", "if (bar.get(\"inputs\") or {}).get(name) != got[name]:", "if False:")),
        ("the judge-alone read refuses", observe_refused, expected_refused, lambda: patched(ft, "read", lambda *a, **k: {"result": "read"})),
        ("the groups are pinned", observe_groups, expected_groups, lambda: with_source(
            fresh_once, "groups", "if _sha(path) != digest:", "if False:")),
        ("precision under 5 comparator flags", observe_tests, expected_tests, lambda: with_source(
            ft, "precision_holds", 'return candidate["precision"] >= cr.FIGURES["contradoc_b1_precision"]', "return True")),
        ("C_BAR item 5, the placed share", observe_c_bar, expected_c_bar, lambda: with_source(
            ft, "tests", 'placed_share=2 * place_row["placed"] >= place_row["flagged_with_two_marks"]', "placed_share=True")),
        ("the half A power labelled in-sample", observe_read, expected_read, lambda: with_source(ft, "prepare_judge", "label=IN_SAMPLE, ", "")),
        ("the refit", observe_refit, expected_refit, lambda: with_source(
            ft, "refit", 'if any(mine[k] != given[k] for k in ("adapter_weights_sha256", "temperature", "threshold", "fitted_on_documents")):', "if False:")),
        ("the sign test at .05", observe_tests, expected_tests, lambda: patched(ft, "FIGURES", dict(ft.FIGURES, alpha_one_sided=.0125))),
        ("precision", observe_tests, expected_tests, lambda: with_source(
            ft, "precision_holds", 'return candidate["right"] * other["flagged"] >= other["right"] * candidate["flagged"]', "return True")),
        ("the chance tail", observe_tests, expected_tests, lambda: patched(ft, "FIGURES", dict(ft.FIGURES, chance_at_most=1.0))),
        ("the flagged share", observe_tests, expected_tests, lambda: patched(ft, "FIGURES", dict(ft.FIGURES, flagged_share_at_most=1.0))),
        ("C_BAR item 1", observe_c_bar, expected_c_bar, lambda: with_source(ft, "tests", '"above_b1": cr.above(BENCHMARK, candidate, None, other)', '"above_b1": True')),
        ("C_BAR item 5, placed", observe_c_bar, expected_c_bar, lambda: with_source(
            ft, "tests", 'placed=place_row["placed"] >= FIGURES["placed_at_least"]', "placed=True")),
        ("C_BAR item 5, above Python", observe_c_bar, expected_c_bar, lambda: with_source(
            ft, "tests", 'above_python=candidate["net"] > python["net"]', "above_python=True")),
        ("void: whole documents", observe_void, expected_void, lambda: with_source(
            ft, "void_reasons", 'if whole < FIGURES["whole_documents_at_least"]:', "if False:")),
        ("void: each B1 group", observe_void, expected_void, lambda: with_source(
            ft, "void_reasons", 'for g, v in sorted(b1_readable.items()) if v < floor]',
            'for g, v in [("b1", sum(b1_readable.values()) / len(b1_readable))] if v < floor]')),
    ]
    results = []
    for name, observe, expected, neutralise in proofs:
        observe = whole(observe)
        results.append(prove_effect(name=name, validate=lambda: ft.CONFIG_PATH.is_file(), observe=observe,
                                    check=lambda: ("PASS" if observe() == expected() else "FAIL", name), neutralise=neutralise))
    return "PASS", ("%d proofs on invented fresh and calibration sets built by the ContraDoc adapter, an invented adapter and canned replies, "
                    "no model and no real key: the bar's figures, attempt, power, size and inputs, one document per group, the calibration's "
                    "documents by source id, the pipeline's question and whole input, the temperature, the pass's form, half A's questions, "
                    "the read key by content, the committed marker, the count before any fresh key, the refit, every item of keep with C_BAR's "
                    "items 1 and 5, and the void per B1 group and per whole document") % len(results)


if __name__ == "__main__":
    print(run_checks())
