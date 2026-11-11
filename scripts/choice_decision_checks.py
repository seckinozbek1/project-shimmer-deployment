"""Gate check: a narrow question decided from a model's own probabilities (D-S41). No model, no
provider, no key: invented logits, a character tokenizer and a stand-in model that refuses to
generate, in a temporary folder. Nothing here says what a real model does.

Each proof is neutralise, fail, restore, pass (scripts/effect_proof.py):
1. the probabilities are renormalised over the declared answers, and the mass they held is kept,
   with the likeliest token outside them;
2. a confidence below the threshold is cannot be settled, at the threshold it is settled;
3. a tie is never broken by the declaration's order;
4. a family with no measured threshold decides nothing, and the probabilities stand;
5. two answers sharing a first token are refused, and an answer is scored on the token that writes
   it after the prompt, not at the start of a text;
6. score_fn is called once: the route runs one forward pass, keeps no cache, generates nothing;
7. the route writes exactly one reply record, with the probabilities and no reply, also when its
   run is sensitive, inside the pinned attention, one shot; a plain head is applied again in
   float32, which tells apart what float16 ties, and any other head is left alone;
8. a prompt over the context runs nothing, a refused declaration and a provider are failed calls,
   recorded, and a raised failure is recorded once and raised by name;
9. a replay pass decides by forward pass, saves probabilities, applies no threshold, writes a
   failed row for logits it cannot read and goes on, stops on a refused declaration, and is not
   stopped for having no text; a stopped pass is not read; the file passes the sealer's replay
   declaration, the replay tool's own `run` hands it over, and the runner counts one record a prompt;
10. LocalBackend.choose is the same forward pass on the backend the replay uses; an adapter is a
    change to the config alone, held to its digests before it is read, and never outlives its group;
11. pairs are built in both orders, or taken as they stand from a pair_judge.py file; a claim is
    read out of its adapter's template and put on the cells named by labels, a side nothing names
    staying whole; a tampered prompt is refused; a prompt is one narrow question and the evidence
    (D-S42: no contract text, no worked example); --permuted-half-a adds half A's questions with the
    answer lines moved, after the others, which stay as they were, and leaves the forms alone;
12. the runtime's question and answers are the measured ones, word for word;
13. the shipped form is the reply, a reply-form review carries nothing of a decision, an unknown
    form is refused;
14. a pair is a record only when both orders are settled and say contradicts, and the row holds
    each order's probabilities;
15. with no threshold nothing is asked, and the reader says why;
16. the real phase 5.5 and 6: the finding is a model's, marked, unpromoted, the passages Python chose
    its quotes, no "The model wrote" line, the decision and confidence shown, in both languages,
    no field added;
17. the question is masked before the backend sees it (LAW-IV), and every call leaves its trail
    with the outcome `decided`.
"""
import contextlib
import importlib
import inspect
import json
import sys
import tempfile
import textwrap
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "benchmark" / "baselines"
for path in (str(BASELINES), str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "adapters")):
    if path not in sys.path:
        sys.path.insert(0, path)

import agent_activation  # noqa: E402
import agent_wrapper  # noqa: E402
import cell_selection  # noqa: E402
import choice_decision as cd  # noqa: E402
import final_models  # noqa: E402
import finding_record  # noqa: E402
import localization  # noqa: E402
import pair_judge_checks as pjc  # noqa: E402
import paired_review  # noqa: E402
import passage_pairs  # noqa: E402
import reply_records  # noqa: E402
import reviewed_document  # noqa: E402
from constitution import Constitution  # noqa: E402
from effect_proof import prove_effect  # noqa: E402
from message_bus import MessageBus  # noqa: E402

# benchmark/baselines is no package and not under scripts/, so these are loaded by name (check 118).
bare_model = importlib.import_module("bare_model")
choice_judge = importlib.import_module("choice_judge")
doc_judge = importlib.import_module("doc_judge")
pair_judge = importlib.import_module("pair_judge")

patched, with_source = pjc.patched, pjc._with_source
ANSWERS = [{"label": "contradicts", "surface": "Yes"}, {"label": "does not", "surface": "No"},
           {"label": "cannot tell", "surface": "Unclear"}]
VOCABULARY = 256


def method_with_source(owner, module, name, old, new):
    """`owner.name` with one line of its own source changed, as a neutralisation."""
    source = textwrap.dedent(inspect.getsource(getattr(owner, name)))
    assert source.count(old) == 1, old
    space = dict(vars(module))
    exec(source.replace(old, new), space)
    return patched(owner, name, space[name])


def encode(text):
    return [ord(c) % VOCABULARY for c in text]


def logits(**by_letter):
    """Logits of a character vocabulary: 0 everywhere, the named first letters as given."""
    row = [0.0] * VOCABULARY
    for letter, value in by_letter.items():
        row[ord(letter)] = value
    return row


def bound(text="<a>"):
    return cd.bind(cd.declare(text, ANSWERS), encode)


def caught(function):
    """What an observer returns for a refusal: the text, so a neutralised run is an observation."""
    try:
        return function()
    except (ValueError, RuntimeError, MemoryError) as exc:
        return type(exc).__name__ + ": " + str(exc)


# 1 to 4: the decision itself


def observe_renormalised():
    decision = cd.decide(lambda p: logits(Y=9.0, N=8.0, U=7.0), bound(), .1)
    rows = [round(a["probability"], 4) for a in decision["answers"]]
    return {"rows": rows, "sum": round(sum(rows), 3), "mass": round(decision["declared_mass"], 3), "top": decision["top"],
            "confidence": round(decision["confidence"], 4), "schema": decision["schema"]}


def expected_renormalised():
    return {"rows": [.6652, .2447, .09], "sum": 1.0, "mass": .98, "top": "contradicts", "confidence": .6652,
            "schema": cd.SCHEMA}


def _whole_vocabulary(row, ids):
    shares, mass = REAL_PROBABILITIES(row, ids)
    return [p * mass for p in shares], mass


REAL_PROBABILITIES = cd.probabilities


def observe_undeclared():
    made = cd.decide(lambda p: logits(Y=2.0, N=1.0, U=1.0, q=5.0), bound(), .1)
    top = made["undeclared_top"]
    return {"token": top["token_id"], "share": round(top["probability"], 3), "only numbers": sorted(top),
            "none left": cd.undeclared_top([1.0, 2.0], [0, 1])}


def expected_undeclared():
    return {"token": ord("q"), "share": .359, "only numbers": ["probability", "token_id"], "none left": None}


def observe_threshold():
    made = cd.decide(lambda p: logits(Y=9.0, N=8.0, U=7.0), bound(), .7)
    at = cd.settle(made, made["confidence"])
    return {"below": (made["decided"], made["settled"], made["why"], made["top"]),
            "at": (at["decided"], at["settled"], at["why"]), "kept": at["answers"] == made["answers"]}


def expected_threshold():
    return {"below": (cd.UNSETTLED, False, cd.BELOW_THRESHOLD, "contradicts"), "at": ("contradicts", True, None), "kept": True}


def observe_tie():
    made = cd.decide(lambda p: logits(Y=5.0, N=5.0, U=1.0), bound(), 0)
    return [made["decided"], made["why"], made["top"], made["settled"]]


def expected_tie():
    return [cd.UNSETTLED, cd.TIE, None, False]


def observe_no_threshold():
    made = cd.decide(lambda p: logits(Y=9.0), bound(), None)
    return {"family": cd.threshold("no_such_family"), "shipped": cd.threshold("passage_pair"), "decided": made["decided"],
            "why": made["why"], "probabilities": made["answers"][0]["probability"] > .9}


def expected_no_threshold():
    return {"family": None, "shipped": None, "decided": cd.UNSETTLED, "why": cd.NO_THRESHOLD, "probabilities": True}


def _settle_ignoring(decision, threshold):
    return REAL_SETTLE(decision, 0 if threshold is not None else threshold)


REAL_SETTLE = cd.settle


# 5: the tokens


def observe_collision():
    shared = [{"label": "one", "surface": "Maybe"}, {"label": "two", "surface": "Most"}]
    return caught(lambda: cd.bind(cd.declare("<a>", shared), encode)["answers"][0]["token_id"])


def expected_collision():
    return "ChoiceRefused: answers 'one' and 'two' share their first token"


def _spaced(text):
    """A tokenizer that writes a word differently at the start of a text: token 1 opens it."""
    return [1] + encode(text)


def observe_token_after_prompt():
    """The token is the surface's after the prompt; alone, the tokenizer's opening token wins and
    all three answers collide or read another token."""
    return caught(lambda: [a["token_id"] for a in cd.bind(cd.declare("<a>", ANSWERS), _spaced)["answers"]])


def expected_token_after_prompt():
    return [ord("Y"), ord("N"), ord("U")]


def _bind_alone(question, encoder):
    return dict(question, answers=[dict(a, token_id=encoder(a["surface"])[0]) for a in question["answers"]])


def _joining(text):
    """A tokenizer in which the surface's first letter joins the prompt's last token."""
    ids = encode(text)
    return ids[:2] + [999] + ids[3:] if len(ids) > 3 else ids


def observe_joined():
    return caught(lambda: cd.bind(cd.declare("<a>", ANSWERS), _joining) and "bound")


# 6 to 8: the route, on a stand-in model that refuses to generate


class Logits:
    dtype = "torch.bfloat16"

    def __init__(self, row):
        self.row = row

    def __getitem__(self, key):
        return self

    def float(self):
        return self

    def tolist(self):
        return list(self.row)


class Ids:
    def __init__(self, ids):
        self.ids, self.shape = ids, (1, len(ids))


class Inputs(dict):
    def to(self, device):
        return self


class Tok:
    chat_template = "fixture"

    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        assert add_generation_prompt and not tokenize
        return "".join("<%s>%s" % (m["role"][0], m["content"]) for m in messages) + "<a>"

    def __call__(self, text, return_tensors=None, add_special_tokens=True):
        ids = encode(text)
        return Inputs(input_ids=Ids(ids), attention_mask=Ids(ids)) if return_tensors else {"input_ids": ids}


class Model:
    device = "cpu"

    def __init__(self, row=None, context=10 ** 6, raises=None):
        self.row, self.raises = row or logits(Y=9.0, N=1.0, U=1.0), raises
        self.config = types.SimpleNamespace(max_position_embeddings=context)
        self.forwards, self.generated, self.options, self.inside = 0, 0, [], []

    def __call__(self, **kwargs):
        self.forwards += 1
        self.options.append({k: v for k, v in kwargs.items() if k in ("use_cache", "logits_to_keep")})
        self.inside.append(ATTENTION["open"])
        if self.raises:
            raise self.raises
        return types.SimpleNamespace(logits=Logits(self.row))

    def generate(self, **kwargs):
        self.generated += 1
        raise RuntimeError("a decision generates nothing")


ATTENTION = {"open": False}


@contextlib.contextmanager
def _pinned(model, decision=None):
    ATTENTION["open"] = True
    try:
        yield {"attention_implementation": "sdpa", "sdpa_backend": "EFFICIENT_ATTENTION", "attention_decision": decision, "pinned": True}
    finally:
        ATTENTION["open"] = False


FAKE_TORCH = types.ModuleType("torch")
FAKE_TORCH.no_grad = contextlib.nullcontext
FAKE_TORCH.cuda = types.SimpleNamespace(is_available=lambda: False)


def _wrapper(context, folder, name="PRACTICE_AUDITOR", backend=None, sensitive=False):
    registry = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
    entry = dict(registry[name], backend=backend or "local_auditor", model="fixture/model")
    return agent_wrapper.AgentWrapper(name, Constitution.load(ROOT / "config" / "constitution.json"),
                                      MessageBus.open(Path(folder) / "bus.jsonl"), {name: entry}, {}, keys={"fixture": True},
                                      run_context=context, sensitive=sensitive)


def _route(model, *, answers=ANSWERS, threshold=.5, backend=None, sensitive=False, tok=None):
    """call_choice on `model`: (result or the raised failure, the reply records, the model)."""
    with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {"torch": FAKE_TORCH}), \
            patched(agent_wrapper, "_load_qwen", lambda model_id: (tok or Tok(), model)), patched(final_models, "pinned_attention", _pinned):
        context = bare_model.RunContext(folder, "run-choice")
        wrapper = _wrapper(context, folder, backend=backend, sensitive=sensitive)
        wrapper._cost_call_id = "call-1"
        try:
            result = wrapper.call_choice("The question.", answers, threshold)
        except Exception as exc:
            result = types.SimpleNamespace(ok=None, error=type(exc).__name__, parsed=None, raised=exc)
        return result, reply_records.records(Path(folder) / "audit" / "model_replies")


def observe_one_pass():
    model = Model()
    calls = []
    current = cd.decide

    def counted(score_fn, question, threshold):
        return current(lambda text: calls.append(1) or score_fn(text), question, threshold)
    with patched(cd, "decide", counted):
        result, _ = _route(model)
    return {"ok": result.ok, "decided": (result.parsed or {}).get("decided"), "score_calls": len(calls),
            "forwards": model.forwards, "generated": model.generated, "options": model.options}


def expected_one_pass():
    return {"ok": True, "decided": "contradicts", "score_calls": 1, "forwards": 1, "generated": 0,
            "options": [{"use_cache": False, "logits_to_keep": 1}]}


REAL_DECIDE = cd.decide


def _decide_twice(score_fn, question, threshold):
    score_fn(question["text"])
    return REAL_DECIDE(score_fn, question, threshold)


def _generating(model, inputs):
    return model.generate(**inputs)


def _pick(record):
    return {"reply": record.get("reply"), "payload": (record.get("payload") or {}).get("text"), "ok": record.get("backend_ok"),
            "hashed": record.get("sensitive"), "allowance": (record.get("decoding") or {}).get("max_new_tokens"),
            "attention": (record.get("attention") or {}).get("pinned"), "prefill": (record.get("attention") or {}).get("prefill"),
            "chunks": (record.get("prefill") or {}).get("chunks"),
            "decision": [(a["label"], round(a["probability"], 3)) for a in (record.get("decision") or {}).get("answers") or []],
            "mass": round((record.get("decision") or {}).get("declared_mass") or 0, 2), "threshold": (record.get("decision") or {}).get("threshold"),
            "dtype": (record.get("decision") or {}).get("logits_dtype")}


def observe_record():
    model = Model()
    _, plain = _route(model)
    _, hidden = _route(Model(), sensitive=True)
    return {"count": len(plain), "plain": _pick(plain[0]) if plain else None, "hidden": _pick(hidden[0]) if hidden else None,
            "inside": model.inside}


def expected_record():
    row = {"reply": None, "ok": True, "allowance": 0, "attention": True, "prefill": "one_shot", "chunks": 0,
           "decision": [("contradicts", .999), ("does not", 0.0), ("cannot tell", 0.0)], "mass": .97, "threshold": .5,
           "dtype": "torch.bfloat16"}
    return {"count": 1, "plain": dict(row, payload="<u>The question.<a>", hashed=False), "hidden": dict(row, payload=None, hashed=True),
            "inside": [True]}


def observe_head():
    """Real torch, a tiny float16 head: two answers its float16 output ties, told apart in float32.
    Skips nothing: the gate's interpreter has torch, as check 288's CPU model needs."""
    import torch

    class Tiny(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.lm_head = torch.nn.Linear(2, 3, bias=False).half()
            self.lm_head.weight.data = torch.tensor([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=torch.float16)
            self.lm_head.weight.data[1, 1] = 2 ** -10
            self.state = torch.tensor([[[20.0, 1.0]]], dtype=torch.float16)

        def get_output_embeddings(self):
            return self.lm_head

        def forward(self, input_ids=None, attention_mask=None, use_cache=None, logits_to_keep=None):
            return types.SimpleNamespace(logits=self.lm_head(self.state))
    model = Tiny()
    inputs = {"input_ids": torch.zeros((1, 2), dtype=torch.long)}
    values, measured = final_models.next_token_logits(model, inputs)
    plain = model.lm_head(model.state)[0, -1].float().tolist()
    return {"own tie": plain[0] == plain[1], "told apart": values[1] > values[0], "dtype": measured["logits_dtype"], "own": measured["model_logits_dtype"],
            "hooks left": len(model.lm_head._forward_pre_hooks), "wrapped": final_models.plain_head(types.SimpleNamespace(get_output_embeddings=lambda: types.SimpleNamespace(weight=None)))}


def expected_head():
    return {"own tie": True, "told apart": True, "dtype": "torch.float32", "own": "torch.float16", "hooks left": 0, "wrapped": None}


def observe_peft_head():
    """A head an adapter wraps is no plain head, whatever its class is called."""
    import torch

    class Linear(torch.nn.Linear):
        pass
    wrapped = Linear(2, 3)
    wrapped.lora_A = torch.nn.ModuleDict()
    plain = torch.nn.Linear(2, 3)
    holder = lambda head: types.SimpleNamespace(get_output_embeddings=lambda: head)
    peft_like = type("Linear", (torch.nn.Module,), {"__module__": "peft.tuners.lora.layer"})()
    return {"plain": final_models.plain_head(holder(plain)) is plain, "lora refused": final_models.plain_head(holder(wrapped)) is None,
            "peft module refused": final_models.plain_head(holder(peft_like)) is None}


def expected_peft_head():
    return {"plain": True, "lora refused": True, "peft module refused": True}


def observe_decisions_half_a():
    """choice_judge decisions lists half A's documents alone, by the reader's split."""
    choice_read = importlib.import_module("choice_read")
    with tempfile.TemporaryDirectory() as folder:
        works = [_workload(folder, "pairs%d" % n, PAIR_TEXT, {"CONV-%d" % n: "No passage may state what another rules out."}) for n in range(4)]
        out = Path(folder) / "prompts.json"
        with patched(pair_judge, "_words_allowed", True):
            value = choice_judge.build(out, pair_workloads=[w for w, _ in works], pair_items=[i for _, i in works], embed=lambda items: None)
        doc_judge.run(out, Path(folder) / "run", backend_factory=lambda reader, context: ChoiceBackend(reader), reader_for=lambda group, allowance: dict(READER))
        listed = {r["document_id"] for r in choice_judge.decisions(out, Path(folder) / "run")}
        half_a = choice_read.split(value["documents"])["contradoc"][0]
    return {"listed": sorted(listed) == sorted(half_a), "fewer": len(listed) < 4, "some": bool(listed)}


def expected_decisions_half_a():
    return {"listed": True, "fewer": True, "some": True}


def _write_without(name):
    real = reply_records.write

    def write(*args, **kwargs):
        kwargs.pop(name, None)
        return real(*args, **kwargs)
    return patched(reply_records, "write", write)


class NoTemplate(Tok):
    chat_template = None


def observe_not_rendered():
    """A question the tokenizer cannot render is a failed call, recorded, not a raised one."""
    result, records = _route(Model(), tok=NoTemplate())
    return {"ok": result.ok, "error": result.error, "records": [(r["backend_ok"], r["error_category"]) for r in records]}


def expected_not_rendered():
    return {"ok": False, "error": "choice_not_rendered: ValueError", "records": [(False, "choice_not_rendered")]}


def observe_unjudged():
    """A rule no question reached says so; one answered from another rule's calls does not."""
    pairs = {"passages": 1, "made": 0, "reused": 0, "failed": 0, "stopped": None, "not_asked": None}
    cells = {"tables": 0, "made": 0, "failed": 0, "stopped": None, "not_asked": None, "selection_refused": [], "decisions": []}
    picked = lambda row: row and (row["why"], row["reason"])
    return {"no pair": picked(passage_pairs.unjudged("R", pairs, [])), "reused": passage_pairs.unjudged("R", dict(pairs, reused=4), []),
            "no table": picked(cell_selection.unjudged("R", cells)), "asked": cell_selection.unjudged("R", dict(cells, made=1)),
            "reader": [reviewed_document._why_not_checked({"_why": k}) for k in ("pairs_none", "cells_none")]}


def expected_unjudged():
    return {"no pair": ("pairs_none", "no pair to ask: 1 passages"), "reused": None, "no table": ("cells_none", "no question asked: 0 tables, 0 selections refused"),
            "asked": None, "reader": [reviewed_document.WHY_PAIRS_NONE, reviewed_document.WHY_CELLS_NONE]}


def observe_counted():
    decided = {"decisions": [{"settled": True}, {"settled": False}], "not_met": 1}
    return {"both": reviewed_document.decided_counts({"passage_pairs": [{"decisions": [{"settled": True}]}], "cell_claims": [decided]}),
            "reply form": reviewed_document.decided_counts({"passage_pairs": [{"made": 4}], "cell_claims": []}),
            "row dtype": cell_selection._row({"unit_id": "u"}, {"selected_by": "labels", "rows": 1, "columns": 1, "of_rows": 1, "of_columns": 1, "ranked_by": "words"},
                                             dict(_decision("does not", .9), logits_dtype="torch.float32")).get("logits_dtype")}


def expected_counted():
    return {"both": ["Questions decided from a model's answer probabilities, with no text written: 3, of which 1 could not be settled.",
                     "Claims a model's probabilities say a table's cells do not meet: 1. No finding is written for these until a relation is ratified."],
            "reply form": [], "row dtype": "torch.float32"}


def observe_refusals():
    over = Model(context=4)
    _, over_records = _route(over)
    shared = [{"label": "one", "surface": "Maybe"}, {"label": "two", "surface": "Most"}]
    collided, collided_records = _route(Model(), answers=shared)
    provider, provider_records = _route(Model(), backend="claude_api")
    return {"over": (over.forwards, len(over_records), over_records[0]["backend_ok"] if over_records else None,
                     (over_records[0].get("context") or {}).get("over_context") if over_records else None),
            "collided": (collided.ok, collided.error, len(collided_records)),
            "provider": (provider.ok, str(provider.error).split(":")[0], len(provider_records))}


def expected_refusals():
    return {"over": (0, 1, False, True),
            "collided": (False, "choice_refused: answers 'one' and 'two' share their first token", 1),
            "provider": (False, "choice_needs_local_backend", 1)}


class OutOfMemoryError(RuntimeError):
    """Named as torch names it: generation_failure_kind reads the class name."""


def observe_raised():
    result, records = _route(Model(raises=OutOfMemoryError("full")))
    return {"raised": type(getattr(result, "raised", None)).__name__, "records": len(records),
            "category": records[0]["error_category"] if records else None}


def expected_raised():
    return {"raised": "GenerationOutOfMemory", "records": 1, "category": "out_of_memory"}


# 9 and 10: the replay


class ChoiceBackend:
    """A canned model on the replay's backend: decides, and refuses to generate."""

    row = logits(Y=3.0, N=2.0, U=1.0)

    def __init__(self, reader):
        self.reader = reader

    def prepare(self):
        return {"model_id": self.reader["model_id"], "digest": "fixture", "checkpoint": {"checkpoint": "base"}}

    def max_context(self):
        return 10 ** 6

    def count_prompt(self, system, user):
        return len(user.split())

    def generate(self, system, user, max_new_tokens):
        raise AssertionError("a choice prompt generates nothing")

    def choose(self, system, user, answers):
        question = cd.bind(cd.declare(user, answers), encode)
        decision = dict(cd.decide(lambda p: self.row, question, None), logits_dtype="torch.bfloat16")
        return {"decision": decision, "payload": user, "form": "rendered_prompt",
                "attention": {"pinned": True}, "prefill": {"prefill_seconds": .01, "chunks": 0}}

    def release(self):
        pass


READER = {"backend": "local_auditor", "agent": "PRACTICE_AUDITOR", "model_id": "fixture/model", "model_mode": "base",
          "decoding": {"kwargs": {"do_sample": False, "eos_token_id": [1], "pad_token_id": 1}, "status": "restored", "source": "fixture", "sha256": "0" * 64}}
PAIR_TEXT = "\n\n".join("The northern quay was leased to tenant number %d of the harbour." % n for n in range(1, 9)) + "\n"
TABLE_TEXT = ("Table 2: Scores of the compared systems.\n\n| Model | Acc | F1 score |\n|---|---|---|\n| GloVe vectors | 71.2 | 60 |\n"
              "| BERT large | 80.1 | 70 |\n| Word2Vec | 50 | 40 |\n")
CLAIM = "BERT large has a higher F1 score than GloVe vectors."


def _workload(folder, name, text, rules=None, benchmark="contradoc"):
    folder = Path(folder) / name
    (folder / "context").mkdir(parents=True)
    (folder / "conventions").mkdir()
    (folder / "context" / (name + ".md")).write_text(text, encoding="utf-8")
    (folder / "context" / "_review_targets.json").write_text(json.dumps({"targets": [name + ".md"]}), encoding="utf-8")
    rules = rules or {"CONV-X": "No passage may state what another rules out."}
    (folder / "conventions" / "review_conventions.md").write_text(
        "\n".join("## %s\n\n%s\n" % (k, v) for k, v in rules.items()), encoding="utf-8")
    items = folder / "items.json"
    items.write_text(json.dumps([{"document_id": name, "item_id": "i-" + k, "rule_id": k, "benchmark": benchmark} for k in rules]), encoding="utf-8")
    return folder, items


def _rule(claim):
    return doc_judge._adapter("scitab").RULE_TEMPLATE.format(claim=claim)


def _built(folder):
    pair_folder, pair_items = _workload(folder, "pairs", PAIR_TEXT)
    claim_folder, claim_items = _workload(folder, "claims", TABLE_TEXT, {"CONV-1": _rule(CLAIM)}, "scitab")
    out = Path(folder) / "prompts.json"
    with patched(pair_judge, "_words_allowed", True):
        value = choice_judge.build(out, pair_workloads=[pair_folder], pair_items=[pair_items], claim_workloads=[claim_folder],
                                   claim_items=[claim_items], embed=lambda items: None)
    return out, value


def _pass(folder, run=None):
    out, value = _built(folder)
    run = Path(folder) / (run or "run")
    measurement = doc_judge.run(out, run, backend_factory=lambda reader, context: ChoiceBackend(reader), reader_for=lambda group, allowance: dict(READER))
    return out, value, run, measurement


def observe_replay():
    with tempfile.TemporaryDirectory() as folder:
        out, value, run, measurement = _pass(folder)
        records = reply_records.records(run / "audit" / "model_replies")
        read = choice_judge.decisions(out, run)
        return {"complete": measurement["complete"], "failures": measurement["failures"][doc_judge.PATH],
                "records": len(records) == value["prompt_count"], "replies": sorted({str(r["reply"]) for r in records}),
                "read": len(read) == value["prompt_count"], "with_probabilities": sum(len((r["decision"] or {}).get("answers") or []) == 3 for r in read) == value["prompt_count"],
                "threshold": sorted({str((r["decision"] or {}).get("threshold")) for r in read}),
                "why": sorted({str((r["decision"] or {}).get("why")) for r in read}),
                "kinds": sorted({r["choice"] for r in read})}


def expected_replay():
    return {"complete": True, "failures": 0, "records": True, "replies": ["None"], "read": True, "with_probabilities": True,
            "threshold": ["None"], "why": [cd.NO_THRESHOLD], "kinds": ["claim", "pair"]}


def observe_sealed():
    """The sealed road, no bound file changed: the sealer's declaration, replay_prompts.py's own
    `run` and the runner's count of a pass's records."""
    import ordinary_final_run
    import prepare_ordinary_final_run
    import replay_prompts
    with tempfile.TemporaryDirectory() as folder:
        out, value = _built(folder)
        declared = prepare_ordinary_final_run.replay_declaration(out.read_bytes())
        run = Path(folder) / "evidence" / "b1" / "choice"
        with patched(doc_judge, "make_backend", lambda reader, context: ChoiceBackend(reader)), \
                patched(bare_model, "resolve_reader", lambda **kwargs: dict(READER)):
            code = caught(lambda: replay_prompts.main(["run", "--prompts", str(out), "--out", str(run), "--paths", "sdpa"]))
        seen = ordinary_final_run.replay_observation(run, declared["prompt_count"], ["sdpa"])
        return {"declared": declared["prompt_count"] == value["prompt_count"], "code": code, "missing": seen["items_without_one_record"],
                "records": seen["reply_records"] == value["prompt_count"], "summary": seen["summary_written"]}


def expected_sealed():
    return {"declared": True, "code": 0, "missing": [], "records": True, "summary": True}


def observe_unreadable():
    """Logits that cannot be read fail their own prompt and the pass goes on; a declaration the
    tokenizer refuses still stops it."""
    state = {"calls": 0}

    class Spoiled(ChoiceBackend):
        def choose(self, system, user, answers):
            state["calls"] += 1
            if state["calls"] == 3:
                question = cd.bind(cd.declare(user, answers), encode)
                cd.decide(lambda p: logits(Y=float("nan")), question, None)
            return ChoiceBackend.choose(self, system, user, answers)

    class Colliding(ChoiceBackend):
        def choose(self, system, user, answers):
            cd.bind(cd.declare(user, [{"label": "one", "surface": "Maybe"}, {"label": "two", "surface": "Most"}]), encode)
    with tempfile.TemporaryDirectory() as folder:
        out, value = _built(folder)
        run = lambda name, backend: doc_judge.run(out, Path(folder) / name, backend_factory=lambda reader, context: backend(reader),
                                                  reader_for=lambda group, allowance: dict(READER))
        made = caught(lambda: run("run", Spoiled))
        if isinstance(made, str):
            return made
        failed = [r for r in made["rows"] if r["failure"]]
        records = reply_records.records(Path(folder) / "run" / "audit" / "model_replies")
        return {"complete": made["complete"], "rows": len(made["rows"]) == value["prompt_count"], "failed": [r["failure"] for r in failed],
                "record": sorted({(r["backend_ok"], r["error_category"]) for r in records if not r["backend_ok"]}),
                "stops": caught(lambda: run("again", Colliding) and "ran")}


def expected_unreadable():
    return {"complete": True, "rows": True, "failed": ["unreadable_logits"], "record": [(False, "unreadable_logits")],
            "stops": "ChoiceRefused: answers 'one' and 'two' share their first token"}


def observe_ties():
    """A pass counts its ties and carries each row's mass and dtype, with no reply record opened."""
    with tempfile.TemporaryDirectory() as folder, patched(ChoiceBackend, "row", logits(Y=3.0, N=3.0, U=1.0)):
        _, value, _, tied = _pass(folder)
        expected = value["prompt_count"]
    with tempfile.TemporaryDirectory() as folder:
        _, _, _, clear = _pass(folder)
    row = tied["rows"][0]
    return {"tied": tied["ties"] == expected, "clear": clear["ties"], "row": (row.get("tie"), row.get("declared_mass", 0) > 0, row.get("logits_dtype"))}


def expected_ties():
    return {"tied": True, "clear": 0, "row": (True, True, "torch.bfloat16")}


def observe_stopped_pass():
    with tempfile.TemporaryDirectory() as folder:
        out, _, run, _ = _pass(folder)
        path = run / doc_judge.MEASUREMENT_FILE
        path.write_text(json.dumps(dict(json.loads(path.read_text(encoding="utf-8")), complete=False)), encoding="utf-8")
        return caught(lambda: len(choice_judge.decisions(out, run)))


def expected_stopped_pass():
    return "ValueError: the pass is not complete"


def _no_complete_check(prompts_path, run_dir):
    path = Path(run_dir) / doc_judge.MEASUREMENT_FILE
    path.write_text(json.dumps(dict(json.loads(path.read_text(encoding="utf-8")), complete=True)), encoding="utf-8")
    return REAL_FINISHED(prompts_path, run_dir)


REAL_FINISHED = pair_judge.finished_pass


@contextlib.contextmanager
def _observed_attention(model, implementation=None):
    ATTENTION["open"] = True
    try:
        yield lambda: {"attention_implementation": implementation}
    finally:
        ATTENTION["open"] = False


def observe_backend():
    model = Model()
    backend = bare_model.LocalBackend(dict(READER, attention=bare_model.attention_record()), bare_model.RunContext(".", "r"))
    backend._tok, backend._mdl = Tok(), model
    with patch.dict(sys.modules, {"torch": FAKE_TORCH}), patched(bare_model, "b1_attention", _observed_attention):
        result = caught(lambda: backend.choose(None, "The question.", ANSWERS))
    if isinstance(result, str):
        return result
    return {"forwards": model.forwards, "generated": model.generated, "inside": model.inside, "payload": result["payload"], "text": "text" in result,
            "top": result["decision"]["top"], "threshold": result["decision"]["threshold"],
            "attention": result["attention"]["attention_implementation"], "chunks": result["prefill"]["chunks"],
            "dtype": result["decision"].get("logits_dtype")}


def expected_backend():
    return {"forwards": 1, "generated": 0, "inside": [True], "payload": "<u>The question.<a>", "text": False, "top": "contradicts",
            "threshold": None, "attention": "sdpa", "chunks": 0, "dtype": "torch.bfloat16"}


class PeftStandIn:
    """The peft module, as far as apply_adapter reads it."""
    calls = []

    class PeftModel:
        @staticmethod
        def from_pretrained(model, path, is_trainable=True):
            PeftStandIn.calls.append(is_trainable)
            return types.SimpleNamespace(eval=lambda: None, config=model.config, base=model)


def _adapter_folder(folder, weights=b"weights"):
    path = Path(folder) / "adapter"
    path.mkdir()
    (path / bare_model.ADAPTER_WEIGHTS).write_bytes(weights)
    (path / bare_model.ADAPTER_CONFIG).write_bytes(b"{}")
    return {"path": str(path), "weights_sha256": final_models.sha(path / bare_model.ADAPTER_WEIGHTS),
            "config_sha256": final_models.sha(path / bare_model.ADAPTER_CONFIG)}


def _prepared(adapter):
    """prepare and release of a LocalBackend on a stand-in base: what was applied and evicted."""
    import huggingface_hub
    evicted = []
    PeftStandIn.calls = []
    backend = bare_model.LocalBackend(dict(READER, adapter=adapter) if adapter else dict(READER), bare_model.RunContext(".", "r"))
    base = Model()
    with patch.dict(sys.modules, {"peft": PeftStandIn}), patched(agent_wrapper, "_load_qwen", lambda model_id: (Tok(), base)), \
            patched(huggingface_hub, "snapshot_download", lambda model_id, local_files_only: "snapshot"), \
            patched(agent_wrapper, "_evict_generation_models", lambda keep_model_id=None: evicted.append(True)):
        try:
            loaded = backend.prepare()
        except bare_model.SetupError as exc:
            return {"refused": str(exc), "read": len(PeftStandIn.calls)}
        wrapped = backend._mdl is not base
        backend.release()
    record = loaded["checkpoint"]
    return {"wrapped": wrapped, "applied": record["adapter_applied"], "sha": bool(record["adapter_sha256"]), "digest": "+adapter:" in loaded["digest"],
            "trainable": PeftStandIn.calls, "evicted": len(evicted)}


def observe_adapter():
    with tempfile.TemporaryDirectory() as folder:
        adapter = _adapter_folder(folder)
        return {"base": _prepared(None), "tuned": _prepared(adapter), "wrong": _prepared(dict(adapter, weights_sha256="0" * 64))}


def expected_adapter():
    return {"base": {"wrapped": False, "applied": False, "sha": False, "digest": False, "trainable": [], "evicted": 0},
            "tuned": {"wrapped": True, "applied": True, "sha": True, "digest": True, "trainable": [False], "evicted": 1},
            "wrong": {"refused": "the adapter's adapter_model.safetensors is not the declared file", "read": 0}}


def observe_adapter_config():
    """A trained judge is a config: the group's adapter reaches the reader, the loaded identity
    reaches the measurement, and a half-declared adapter is refused when the file is read."""
    seen = []

    class Named(ChoiceBackend):
        def prepare(self):
            seen.append(self.reader.get("adapter"))
            return dict(ChoiceBackend.prepare(self), checkpoint={"checkpoint": "base", "adapter_applied": True, "adapter_sha256": "a" * 64})
    with tempfile.TemporaryDirectory() as folder:
        config = json.loads(choice_judge.CONFIG_PATH.read_text(encoding="utf-8"))
        adapter = {"path": "tuning/judge/checkpoint-1", "weights_sha256": "a" * 64, "config_sha256": "b" * 64}
        group = dict(config["models"][0], group="choice_tuned", adapter=adapter)
        path = Path(folder) / "config.json"
        path.write_text(json.dumps(dict(config, models=config["models"] + [group])), encoding="utf-8")
        pair_folder, pair_items = _workload(folder, "pairs", PAIR_TEXT)
        out = Path(folder) / "prompts.json"
        with patched(pair_judge, "_words_allowed", True):
            choice_judge.build(out, pair_workloads=[pair_folder], pair_items=[pair_items], config_path=path, embed=lambda items: None)
        measured = doc_judge.run(out, Path(folder) / "run", backend_factory=lambda reader, context: Named(reader),
                                 reader_for=lambda g, allowance: dict(READER))
        bad = dict(config, models=[dict(group, adapter={"path": "x"})])
    return {"readers": seen, "models": {k: v["adapter_sha256"] for k, v in measured["models"].items()},
            "half": caught(lambda: doc_judge.check_config(bad) and "read")}


def observe_adapter_in_process():
    """An adapter made on the instance: no digest in the file, the caller's reader carries it."""
    seen = []

    class Named(ChoiceBackend):
        def prepare(self):
            seen.append(self.reader.get("adapter"))
            return ChoiceBackend.prepare(self)
    made = {"path": "/made/here", "weights_sha256": "c" * 64, "config_sha256": "d" * 64}
    with tempfile.TemporaryDirectory() as folder:
        out, _ = _built(folder)
        doc_judge.run(out, Path(folder) / "run", backend_factory=lambda reader, context: Named(reader),
                      reader_for=lambda group, allowance: dict(READER, adapter=made))
    return seen == [made]


def expected_adapter_config():
    adapter = {"path": "tuning/judge/checkpoint-1", "weights_sha256": "a" * 64, "config_sha256": "b" * 64}
    return {"readers": [None, adapter], "models": {"choice_direct": "a" * 64, "choice_tuned": "a" * 64},
            "half": "ValueError: an adapter belongs to a group naming its model, and states its path and both SHA-256 digests (D-S42)"}


def _named_group(folder, count):
    """A pass of `count` choice prompts in a group naming its own model: no reply is a stop only
    for a form that writes one."""
    pair_folder, pair_items = _workload(folder, "pairs", PAIR_TEXT)
    out = Path(folder) / "prompts.json"
    with patched(pair_judge, "_words_allowed", True):
        value = choice_judge.build(out, pair_workloads=[pair_folder], pair_items=[pair_items], embed=lambda items: None)
    assert value["prompt_count"] > count and any(g.get("model_id") for g in value["config"]["models"])
    return out


def observe_no_stop():
    with tempfile.TemporaryDirectory() as folder:
        out = _named_group(folder, doc_judge.EARLY_STOP)
        return caught(lambda: doc_judge.run(out, Path(folder) / "run", backend_factory=lambda reader, context: ChoiceBackend(reader),
                                            reader_for=lambda group, allowance: dict(READER))["complete"])


# 11 and 12: the prompts


def observe_build():
    with tempfile.TemporaryDirectory() as folder:
        _, value = _built(folder)
    prompts = value["prompts"]
    pairs = [p for p in prompts if p["choice"] == "pair"]
    claims = [p for p in prompts if p["choice"] == "claim"]
    first = {(p["pair_id"].rsplit("-", 1)[0], p["order"]) for p in pairs}
    return {"both_orders": all((key, order) in first for key, _ in first for order in ("ab", "ba")), "max_new_tokens": sorted({p["max_new_tokens"] for p in prompts}),
            "claim": claims[0]["claim"], "selection": claims[0]["selection"], "shown": ["Word2Vec" in claims[0]["user"], "BERT large" in claims[0]["user"], "71.2" in claims[0]["user"]],
            "caption": "Table 2:" in claims[0]["user"], "template_left": "UNCERTAIN" in claims[0]["user"], "reads": value["reads"]}


def expected_build():
    return {"both_orders": True, "max_new_tokens": [0], "claim": CLAIM,
            "selection": {"rows": 3, "of_rows": 3, "columns": 2, "of_columns": 3, "selected_by": "labels"},
            "shown": [True, True, False], "caption": True, "template_left": False,
            "reads": "the staged workloads only: no answer key, no reply, no label"}


def observe_pairs_from():
    """The pairs of a file pair_judge.py built, as they stand there, encoding nothing."""
    with tempfile.TemporaryDirectory() as folder:
        pair_folder, pair_items = _workload(folder, "pairs", PAIR_TEXT)
        source = Path(folder) / "source.json"
        with patched(pair_judge, "_words_allowed", True):
            built = pair_judge.build([pair_folder], [pair_items], source, embed=lambda items: None)
        made = caught(lambda: choice_judge.build(Path(folder) / "out.json", pairs_from=source, embed=None))
        if isinstance(made, str):
            return made
    key = lambda p: (p["document_id"], p["pair_id"], p["span_a"], p["span_b"], p["item_id"], p["rule_id"])
    return {"same": sorted(map(key, made["prompts"])) == sorted(map(key, built["prompts"])), "count": made["prompt_count"] == built["prompt_count"],
            "documents": made["documents"] == built["documents"], "form": sorted({p["form"] for p in made["prompts"]})}


def expected_pairs_from():
    return {"same": True, "count": True, "documents": True, "form": [doc_judge.CHOICE_FORM]}


def observe_narrow():
    """D-S42: all a prompt holds beside the evidence is one question and the answers, in words a
    contract would not use. Read on what is left once the evidence is taken out."""
    config = json.loads(choice_judge.CONFIG_PATH.read_text(encoding="utf-8"))
    out = {}
    for kind, slots in (("pair", {"passage_a": "", "passage_b": ""}), ("claim", {"cells": "", "claim": ""})):
        left = doc_judge.render_choice(config, kind, slots)
        out[kind] = {"questions": left.count("?"), "words": len(left.split()) <= 70,
                     "contract": [w for w in ("json", "{", "contract", "item_id", "example", "conv-", "ref-", "rule") if w in left.lower()]}
    return out


def expected_narrow():
    row = {"questions": 1, "words": True, "contract": []}
    return {"pair": row, "claim": row}


def _with_example(config, kind, slots, real=doc_judge.render_choice):
    return real(config, kind, slots) + " For example, answer in JSON under rule CONV-1: is this right?"


def observe_permuted():
    """Half A's prompts again with their answer lines moved; nothing else in the file changes."""
    choice_read = importlib.import_module("choice_read")
    with tempfile.TemporaryDirectory() as folder:
        pair_folder, pair_items = _workload(folder, "pairs", PAIR_TEXT)
        claim_folder, claim_items = _workload(folder, "claims", TABLE_TEXT, {"CONV-1": _rule(CLAIM)}, "scitab")
        args = dict(pair_workloads=[pair_folder], pair_items=[pair_items], claim_workloads=[claim_folder], claim_items=[claim_items], embed=lambda items: None)
        with patched(pair_judge, "_words_allowed", True):
            plain = choice_judge.build(Path(folder) / "plain.json", **args)
            moved = choice_judge.build(Path(folder) / "moved.json", permuted_half_a=True, **args)
    controls = [p for p in moved["prompts"] if p.get("order_control")]
    first = next(p for p in controls if p["choice"] == "pair")
    original = next(p for p in plain["prompts"] if p["choice"] == "pair" and p["pair"] == first["pair"] and p["order"] == first["order"])
    tail = lambda p: p["user"].split("Answer with one word.")[1].split()
    return {"the others stand": [p["user_sha256"] for p in moved["prompts"][:plain["prompt_count"]]] == [p["user_sha256"] for p in plain["prompts"]],
            "the others' ids": [p["prompt_id"] for p in moved["prompts"][:plain["prompt_count"]]] == [p["prompt_id"] for p in plain["prompts"]],
            "every half A prompt": len(controls) == plain["prompt_count"], "first answer": (tail(original)[0], tail(first)[0]),
            "same evidence": first["user"].split("Do the two")[0] == original["user"].split("Do the two")[0], "forms": moved["config"]["choice"]["forms"] == plain["config"]["choice"]["forms"],
            "half": sorted(choice_read.halves(["pairs"])[0])}


def expected_permuted():
    return {"the others stand": True, "the others' ids": True, "every half A prompt": True, "first answer": ("Yes:", "No:"), "same evidence": True, "forms": True, "half": ["pairs"]}


def observe_whole_table():
    chosen = doc_judge.select_cells(TABLE_TEXT, "The best system wins.")
    return [chosen["selected_by"], chosen["rows"], chosen["columns"], "Word2Vec" in chosen["cells"]]


def expected_whole_table():
    return ["whole_table", 3, 3, True]


def observe_not_the_template():
    return caught(lambda: choice_judge.claim_of("scitab", "Some other rule entirely."))


def expected_not_the_template():
    return "ValueError: a rule is not its adapter's claim template"


def observe_tamper():
    with tempfile.TemporaryDirectory() as folder:
        out, value = _built(folder)
        changed = json.loads(out.read_text(encoding="utf-8"))
        prompt = next(p for p in changed["prompts"] if p["choice"] == "claim")
        prompt["user"] += " Say yes."
        prompt["user_sha256"] = doc_judge._sha(prompt["user"])
        out.write_text(json.dumps(changed), encoding="utf-8")
        return caught(lambda: len(doc_judge.load_prompts(out))) == "ValueError: a prompt is not its template's rendering: " + prompt["prompt_id"]


def observe_same_question():
    measured = json.loads(choice_judge.CONFIG_PATH.read_text(encoding="utf-8"))
    runtime = dict(passage_pairs.load_config(), form=passage_pairs.DECISION_FORM)
    form = measured["choice"]["forms"]["pair"]
    return {"words": doc_judge.render_choice(measured, "pair", {"passage_a": pjc.QUAY_A, "passage_b": pjc.QUAY_B})
            == passage_pairs.render(runtime, pjc.QUAY_A, pjc.QUAY_B),
            "answers": form["answers"] == runtime["decision"]["answers"], "limit": form["limit"] == runtime["limit"]}


# 13 to 15: the review


def _decision(top, confidence, threshold=.6):
    others = [a for a in ANSWERS if a["label"] != top]
    rows = [{"label": top, "surface": "x", "token_id": 1, "probability": confidence}] + [
        {"label": a["label"], "surface": "x", "token_id": 2 + i, "probability": (1 - confidence) / 2} for i, a in enumerate(others)]
    return cd.settle({"schema": cd.SCHEMA, "answers": rows, "declared_mass": .99}, threshold)


def _config(**fields):
    return dict(pjc.REAL_LOAD(), form=passage_pairs.DECISION_FORM, **fields)


def _deciding():
    """The decision form with a measured threshold, as a decision adopting it would set."""
    stack = contextlib.ExitStack()
    stack.enter_context(patched(passage_pairs, "load_config", lambda: _config()))
    stack.enter_context(patched(cd, "threshold", lambda family: .6))
    return stack


UNITS = [{"unit_id": "u01-a", "text": pjc.QUAY_A + " " + pjc.QUAY_B}]


def _reviewed(answers):
    replies = iter(answers)
    with patched(cd, "threshold", lambda family: .6):
        return pjc._review(UNITS, lambda user: next(replies), config=_config())


def observe_shipped():
    config = passage_pairs.load_config()
    _, calls = pjc._review(UNITS, pjc._contradict)
    sent = []
    wrapper = types.SimpleNamespace(dispatch=lambda stable, dynamic, **k: sent.append(stable) or "dispatched",
                                    call_choice=lambda *a: "decided")
    return {"form": config["form"], "default": passage_pairs.form_of({}), "call": passage_pairs.call(wrapper, "s", "", config, {}),
            "added": sorted(set(calls) & {"form", "unsettled", "decisions", "decision_notes"}), "template": "JSON" in passage_pairs.render(config, "a", "b")}


def expected_shipped():
    return {"form": "reply", "default": "reply", "call": "dispatched", "added": [], "template": True}


def observe_unknown_form():
    return caught(lambda: passage_pairs.form_of({"form": "reply_or_so"}))


def observe_both_orders():
    yes, no, low = _decision("contradicts", .9), _decision("does not", .9), _decision("contradicts", .5)
    kept, calls = _reviewed([yes, _decision("contradicts", .8)])
    one, one_calls = _reviewed([yes, no])
    unsure, unsure_calls = _reviewed([yes, low])
    row = calls["decisions"][0]
    return {"kept": [(k["quote"], k["quote_b"], k["relation"], k["explanation"], k.get("text_screened")) for k in kept],
            "one": (len(one), one_calls["one_order_only"], one_calls["unsettled"]), "unsure": (len(unsure), unsure_calls["one_order_only"], unsure_calls["unsettled"]),
            "row": {"passages": row["passages"], "decided": row["decided"], "confidence": row["confidence"], "threshold": row["threshold"],
                    "mass": row["declared_mass"], "labels": sorted(row["answers"])},
            "orders": [d["passages"] for d in calls["decisions"]], "text": "harbour" in json.dumps(calls),
            "notes": list(calls["decision_notes"].values())}


def expected_both_orders():
    return {"kept": [(pjc.QUAY_A, pjc.QUAY_B, "contradiction", "", True)], "one": (0, 1, 0), "unsure": (0, 1, 1),
            "row": {"passages": [0, 1], "decided": "contradicts", "confidence": .9, "threshold": .6, "mass": .99,
                    "labels": ["cannot tell", "contradicts", "does not"]},
            "orders": [[0, 1], [1, 0]], "text": False,
            "notes": ["Decided from the model's own answer probabilities; it wrote no text. In both orders: contradicts, confidence 0.900 and 0.800; "
                      "the fixed answers held at least 0.990 of its probability."]}


def _read_top(decision, config):
    """A reader that takes the top answer however low its confidence."""
    return REAL_READ(dict(decision, settled=True, decided=decision["answers"][0]["label"]), config)


REAL_READ = passage_pairs.read_decision


POSTED = {"as": None}     # a proof's switch: the backend and model a decision's call reports


def _choice_call(calls):
    def call_choice(self, prompt, answers, threshold):
        calls.append((prompt, self._cost_phase, self._cost_doc_id, bool(self._cost_call_id), threshold))
        both = pjc.QUAY_A in prompt and pjc.QUAY_B in prompt
        decision = _decision("contradicts" if both else "does not", .9, threshold)
        backend, model = POSTED["as"] or (self.backend, "fixture-auditor")
        return agent_wrapper.CallResult(backend, model, "", parsed=decision)
    return call_choice


@contextlib.contextmanager
def _posted_as_python():
    POSTED["as"] = ("paired", "python")
    try:
        yield
    finally:
        POSTED["as"] = None


def observe_no_measure():
    calls = []
    with patched(passage_pairs, "load_config", lambda: _config()), \
            patch.object(agent_wrapper.AgentWrapper, "call_choice", _choice_call(calls)):
        rows, unjudged, _, reader, incomplete = pjc._phase_run(pjc._contradict_call([]))
    return {"calls": len(calls), "rows": [(r["not_asked"], r.get("why")) for r in rows], "not_judged": [e.get("why") for e in unjudged],
            "reader": "no threshold has been measured" in reader, "incomplete": incomplete}


def expected_no_measure():
    said = "no pair asked: no threshold measured for passage_pair"
    return {"calls": 0, "rows": [(said, "no_threshold")], "not_judged": ["no_threshold"], "reader": True, "incomplete": False}


# 16 and 17: the deliverables


def observe_phase():
    calls = []
    with _deciding(), patch.object(agent_wrapper.AgentWrapper, "call_choice", _choice_call(calls)):
        rows, _, data, reader, incomplete = pjc._phase_run(pjc._contradict_call([]))
    found = [f for f in data.get("model_findings_not_promoted") or [] if f.get("relation") == "contradiction"]
    item = found[0] if found else {}
    note = "In both orders: contradicts, confidence 0.900 and 0.900; the fixed answers held at least 0.990"
    return {"found": len(found), "quotes": (item.get("quote"), item.get("quote_b")), "who": (item.get("written_by"), item.get("promoted")),
            "explanation": item.get("explanation"), "confidence_field": "confidence" in item,
            "note": any(note in n for n in item.get("reader_notes") or []), "reader_note": note in reader,
            "mark": finding_record.MODEL_FINDING_MARK in reader, "counted": "with no text written: 4, of which 0 could not be settled." in reader, "model_wrote": 'The model wrote: "' in _block_of(reader),
            "amended": any(pjc.QUAY_A in json.dumps(a) for a in data.get("amendments") or []),
            "row": [(r["form"], r["made"], r["unsettled"], len(r["decisions"]), len(r["decision_notes"])) for r in rows],
            "incomplete": incomplete, "thresholds": sorted({c[4] for c in calls}), "added": _added_fields(item)}


def _block_of(reader):
    """The lines of the reader's file about the pair."""
    lines = reader.splitlines()
    at = [i for i, line in enumerate(lines) if "one passage says" in line]
    return "\n".join(lines[at[0]:at[0] + 3]) if at else ""


READER_FIELDS = {"agent", "reader_notes", "figures_in_unit", "model_claimed_verdict", "checked_by_python", "promoted", "written_by", "item_id",
                 "revision", "judged_path", "text_screened", "ts", "mark", "doc_id"}


def _added_fields(item):
    contract = json.loads((ROOT / "config" / "agent_contracts.json").read_text(encoding="utf-8"))["finding_record"]
    return sorted(set(item) - set(contract["fields"]) - READER_FIELDS)


def expected_phase():
    return {"found": 1, "quotes": (pjc.QUAY_A, pjc.QUAY_B), "who": ("model", False), "explanation": "", "confidence_field": False,
            "note": True, "reader_note": True, "mark": True, "counted": True, "model_wrote": False, "amended": False, "row": [("decision", 4, 0, 4, 1)],
            "incomplete": False, "thresholds": [.6], "added": []}


def observe_turkish():
    note = passage_pairs.DECISION_NOTE % ("contradicts", .9, .8, .97)
    return [localization.message(note, "tr"), localization.message(note, "en") == note,
            localization.message(reviewed_document.WHY_NO_THRESHOLD, "tr") != reviewed_document.WHY_NO_THRESHOLD]


def expected_turkish():
    return ["Modelin kendi yanıt olasılıklarından karar verildi; model metin yazmadı. İki sırada da: çelişiyor, güven 0.900 ve 0.800; "
            "sabit yanıtlar olasılığının en az 0.970 kadarını taşıdı.", True, True]


def observe_masked():
    import harness.run_agent as run_agent
    import honest_output_checks as hoc
    text = chr(10).join((hoc.DOC_TEXT, "## Entry Quay", "", pjc.QUAY_A, "", pjc.QUAY_B, ""))
    seen, calls = [], []

    def masker(stable, dynamic, *, backend, agent, context=""):
        seen.append(stable)
        return stable.replace("harbour", "[PLACE]"), dynamic
    real = run_agent.build_orchestrator

    def masked_orchestrator(**kwargs):
        orch = real(**kwargs)
        orch.outbound_masker = masker
        return orch
    with tempfile.TemporaryDirectory() as td, _deciding(), patch.object(agent_wrapper.AgentWrapper, "call_choice", _choice_call(calls)), \
            patch.object(run_agent, "build_orchestrator", masked_orchestrator), patch.object(passage_pairs, "embed", lambda items: None):
        hoc.mocked_run(Path(td), style_guardian=False, text=text, rules=hoc.RULES + [pjc.COMPARE_RULE])
    return {"masker_saw": any(pjc.QUAY_A in s for s in seen), "sent": bool(calls), "raw_sent": any("harbour" in c[0] for c in calls)}


def expected_masked():
    return {"masker_saw": True, "sent": True, "raw_sent": False}


def observe_trail():
    import call_evidence
    import honest_output_checks as hoc
    text = chr(10).join((hoc.DOC_TEXT, "## Entry Quay", "", pjc.QUAY_A, "", pjc.QUAY_B, ""))
    calls = []
    with tempfile.TemporaryDirectory() as td, _deciding(), patch.object(agent_wrapper.AgentWrapper, "call_choice", _choice_call(calls)), \
            patch.object(passage_pairs, "embed", lambda items: None):
        run = hoc.mocked_run(Path(td), style_guardian=False, text=text, rules=hoc.RULES + [pjc.COMPARE_RULE])
        folder = Path(run["run_dir"])
        ids = {e["call_id"] for e in pjc._lines(call_evidence.evidence_path(folder)) if e.get("task") == "passage_pair"}
        rows = json.loads((folder / "audit" / "agent_activation.json").read_text(encoding="utf-8"))["decisions"]
        rows = [r for r in rows if r["reason"] == "passage_pair"]
        outcomes = reply_records.outcomes(folder / "audit" / "model_replies")
    return {"costs": sorted({c[1:4] for c in calls}), "evidence": len(ids), "activation": sorted({r.get("outcome") for r in rows}),
            "outcomes": sorted(outcomes[i] for i in ids)}


def expected_trail():
    return {"costs": [("5.5", "batch_sheet", True)], "evidence": 4, "activation": ["decided"],
            "outcomes": ["decided", "decided", "not_promoted", "not_promoted"]}


def run_checks():
    proofs = [
        ("renormalised", observe_renormalised, expected_renormalised,
         lambda: patched(cd, "probabilities", _whole_vocabulary)),
        ("the likeliest token outside", observe_undeclared, expected_undeclared, lambda: with_source(cd, "undeclared_top", "value, token = max(rest)", "value, token = min(rest)")),
        ("threshold", observe_threshold, expected_threshold, lambda: patched(cd, "settle", _settle_ignoring)),
        ("tie", observe_tie, expected_tie, lambda: with_source(cd, "settle", 'if top["probability"] == ranked[1]["probability"]:', "if False:")),
        ("no threshold", observe_no_threshold, expected_no_threshold,
         lambda: with_source(cd, "settle", "why = NO_THRESHOLD", "why = None")),
        ("no threshold in a file", observe_no_threshold, expected_no_threshold,
         lambda: patched(cd, "threshold", lambda family, path=None: .5)),
        ("first tokens collide", observe_collision, expected_collision, lambda: with_source(cd, "bind", "if token in held:", "if False:")),
        ("the token after the prompt", observe_token_after_prompt, expected_token_after_prompt, lambda: patched(cd, "bind", _bind_alone)),
        ("a surface joining the prompt", observe_joined, lambda: "ChoiceRefused: the surface of answer 'contradicts' joins the prompt's last token",
         lambda: with_source(cd, "bind", "or whole[:len(prompt)] != prompt", "")),
        ("one score call", observe_one_pass, expected_one_pass, lambda: patched(cd, "decide", _decide_twice)),
        ("no generation", observe_one_pass, expected_one_pass, lambda: patched(final_models, "next_token_logits", _generating)),
        ("the record: probabilities", observe_record, expected_record, lambda: _write_without("decision")),
        ("the record: no reply", observe_record, expected_record,
         lambda: method_with_source(agent_wrapper.AgentWrapper, agent_wrapper, "_write_reply", 'not sent.get("no_reply")', "True")),
        ("the record: pinned", observe_record, expected_record,
         lambda: patched(agent_wrapper.AgentWrapper, "_choice_forward", _unpinned_forward())),
        ("float32 from the head", observe_head, expected_head, lambda: patched(final_models, "plain_head", lambda model: None)),
        ("a question not rendered", observe_not_rendered, expected_not_rendered, lambda: with_source_method_raising()),
        ("a rule no question reached", observe_unjudged, expected_unjudged, lambda: with_source(passage_pairs, "unjudged", 'elif not calls["made"] and not calls.get("reused"):', "elif False:")),
        ("a table no question reached", observe_unjudged, expected_unjudged, lambda: with_source(cell_selection, "unjudged", 'elif not calls["made"]:', "elif False:")),
        ("decided rules counted", observe_counted, expected_counted, lambda: patched(reviewed_document, "COUNT_DECIDED", "Nothing to count.")),
        ("the cell row's dtype", observe_counted, expected_counted, lambda: with_source(cell_selection, "_row", '"logits_dtype": decision.get("logits_dtype"),', "")),
        ("a wrapped head is refused", observe_peft_head, expected_peft_head, lambda: with_source(
            final_models, "plain_head", "if head is None or type(head).__module__.split('.')[0] == 'peft' or hasattr(head, 'base_layer') or hasattr(head, 'lora_A'):",
            "if head is None:")),
        ("decisions: half A alone", observe_decisions_half_a, expected_decisions_half_a, lambda: with_source(
            choice_judge, "decisions", 'if p["document_id"] not in half_a:', "if False:")),
        ("over the context", observe_refusals, expected_refusals, lambda: patched(final_models, "context_record", lambda m, p, n: dict(
            prompt_tokens=p, max_new_tokens=n, model_context=None, over_context=None))),
        ("a provider has no logits", observe_refusals, expected_refusals,
         lambda: patched(agent_wrapper.decoding_policy, "LOCAL_BACKENDS", ("local_auditor", "claude_api"))),
        ("raised by name, recorded once", observe_raised, expected_raised,
         lambda: patched(final_models, "named_generation_failure", lambda exc: None)),
        ("the replay", observe_replay, expected_replay, lambda: _write_without("decision")),
        ("the replay applies no threshold", observe_backend, expected_backend,
         lambda: patched(cd, "decide", lambda score, question, threshold: REAL_DECIDE(score, question, .5 if threshold is None else threshold))),
        ("the sealed road", observe_sealed, expected_sealed, lambda: patched(doc_judge, "run", lambda *a, **k: {"complete": False})),
        ("a stopped pass", observe_stopped_pass, expected_stopped_pass, lambda: patched(pair_judge, "finished_pass", _no_complete_check)),
        ("the replay's backend", observe_backend, expected_backend, lambda: patched(final_models, "next_token_logits", _generating)),
        ("an adapter: applied", observe_adapter, expected_adapter, lambda: patched(bare_model, "apply_adapter", lambda model, adapter: model)),
        ("an adapter: its digests", observe_adapter, expected_adapter, lambda: patched(final_models, "sha", lambda path: "0" * 64)),
        ("an adapter: gone with its group", observe_adapter, expected_adapter, lambda: method_with_source(
            bare_model.LocalBackend, bare_model, "release", "if self._adapter:", "if False:")),
        ("an adapter is a config", observe_adapter_config, expected_adapter_config, lambda: with_source(
            doc_judge, "run", 'reader["adapter"] = group["adapter"]', "pass")),
        ("an adapter made on the instance", observe_adapter_in_process, lambda: True, lambda: with_source(
            doc_judge, "run", 'reader = dict(reader, model_id=group["model_id"], decoding=own_stops(reader["decoding"], group))',
            'reader = dict({k: v for k, v in reader.items() if k != "adapter"}, model_id=group["model_id"], decoding=own_stops(reader["decoding"], group))')),
        ("unreadable logits go on", observe_unreadable, expected_unreadable, lambda: patched(doc_judge, "failure_kind", final_models.generation_failure_kind)),
        ("a refused declaration stops", observe_unreadable, expected_unreadable, lambda: with_source(
            doc_judge, "failure_kind", "isinstance(exc, choice_decision.ChoiceUnreadable)", "isinstance(exc, choice_decision.ChoiceRefused)")),
        ("ties are counted", observe_ties, expected_ties, lambda: with_source(doc_judge, "run", 'tie=decision["why"] == "tie"', "tie=False")),
        ("the logits' dtype", observe_record, expected_record, lambda: patched(Logits, "dtype", "unstated")),
        ("no text is no stop", observe_no_stop, lambda: True, lambda: with_source(
            doc_judge, "run", 'r["group"] == group["group"] and r["form"] != CHOICE_FORM', 'r["group"] == group["group"]')),
        ("the build", observe_build, expected_build, lambda: patched(doc_judge, "select_cells", lambda text, claim, real=doc_judge.select_cells: dict(real(text, claim), rows=1))),
        ("the claim alone", observe_build, expected_build, lambda: patched(choice_judge, "claim_of", lambda benchmark, rule: rule)),
        ("answer lines moved", observe_permuted, expected_permuted, lambda: patched(doc_judge, "answers_moved", lambda form: form["template"])),
        ("the pairs of a measured file", observe_pairs_from, expected_pairs_from, lambda: with_source(
            choice_judge, "_pairs_from", 'span_a=p["span_a"], span_b=p["span_b"]', 'span_a=p["span_b"], span_b=p["span_a"]')),
        ("one narrow question", observe_narrow, expected_narrow, lambda: patched(doc_judge, "render_choice", _with_example)),
        ("nothing named stays whole", observe_whole_table, expected_whole_table, lambda: patched(doc_judge, "select_cells", lambda text, claim: {"selected_by": "labels", "rows": 1, "columns": 1, "cells": ""})),
        ("not the template", observe_not_the_template, expected_not_the_template,
         lambda: with_source(choice_judge, "claim_of", "if not (rule_text.startswith(head) and rule_text.endswith(tail)) or len(rule_text) <= len(head) + len(tail):", "if False:")),
        ("a tampered prompt", observe_tamper, lambda: True, lambda: with_source(
            doc_judge, "load_prompts", 'if p.get("user") != user or p.get("user_sha256") != _sha(user) or p.get("system") != system:', "if False:")),
        ("the measured question", observe_same_question, lambda: {"words": True, "answers": True, "limit": True},
         lambda: patched(passage_pairs, "render", lambda config, a, b: "another question")),
        ("the reply stays the default", observe_shipped, expected_shipped, lambda: patched(passage_pairs, "form_of", lambda config: passage_pairs.DECISION_FORM)),
        ("an unknown form", observe_unknown_form, lambda: "ValueError: config/passage_pairs.json: form is reply or decision",
         lambda: with_source(passage_pairs, "form_of", "if form not in (REPLY_FORM, DECISION_FORM):", "if False:")),
        ("both orders", observe_both_orders, expected_both_orders, lambda: patched(passage_pairs, "read_decision", _read_top)),
        ("each order in the row", observe_both_orders, expected_both_orders, lambda: patched(passage_pairs, "decision_row", lambda a, b, d: {
            "passages": [0, 1], "decided": "?", "confidence": 0, "threshold": 0, "declared_mass": 0, "answers": {}})),
        ("no measure, no question", observe_no_measure, expected_no_measure, lambda: patched(cd, "threshold", lambda family: .6)),
        ("no measure, in the reader's words", observe_no_measure, expected_no_measure,
         lambda: patched(reviewed_document, "WHY_BY_KIND", {k: v for k, v in reviewed_document.WHY_BY_KIND.items() if k != "no_threshold"})),
        ("the note", observe_phase, expected_phase, lambda: with_source(paired_review, "model_item_notes", 'if note:', "if False:")),
        ("the quotes are Python's", observe_phase, expected_phase, lambda: patched(passage_pairs, "record", _record_with_words)),
        ("no field added", observe_phase, expected_phase, lambda: patched(passage_pairs, "record", lambda *a: dict(pjc.REAL_RECORD(*a), decision_confidence=.9))),
        ("a model's by its post", observe_phase, expected_phase, _posted_as_python),
        ("the note in the second output language", observe_turkish, expected_turkish, lambda: patched(localization, "catalog", lambda: {})),
        ("masked", observe_masked, expected_masked, lambda: patched(passage_pairs, "outbound", lambda wrapper, text: (text, ""))),
        ("the trail", observe_trail, expected_trail, lambda: patched(passage_pairs, "outcome_of", lambda r, c: "free_text")),
        ("the activation row", observe_trail, expected_trail, lambda: patched(agent_activation, "direct_call", _direct_call_as_free_text)),
    ]
    results = []
    for name, observe, expected, neutralise in proofs:
        results.append(prove_effect(name=name, validate=lambda: choice_judge.CONFIG_PATH.is_file(), observe=observe,
                                    check=lambda: ("PASS" if observe() == expected() else "FAIL", name), neutralise=neutralise))
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass, on invented logits and a stand-in model (no real model has run): "
                    "probabilities renormalised with the declared mass kept, a threshold, a tie and no threshold unsettled, colliding first "
                    "tokens refused, the token read after the prompt, one forward pass and no generation, one reply record with the "
                    "probabilities and no reply, the replay's form and its prompts, the reply still the default, both orders settled for "
                    "a record, nothing asked with no measured threshold, the finding a model's with Python's quotes and note, masked") % len(results)


def with_source_method_raising():
    """call_choice with its rendering outside the recorded failure again."""
    return method_with_source(agent_wrapper.AgentWrapper, agent_wrapper, "call_choice", """return _finish(CallResult(self.backend, model_id, "", ok=False, error=f"choice_not_rendered: {type(e).__name__}"))""", "raise")


def _unpinned_forward():
    """_choice_forward with the pinned attention taken away."""
    real = agent_wrapper.AgentWrapper._choice_forward

    def forward(self, mdl, inputs, sent, model_id):
        def score(prompt):
            with patched(final_models, "pinned_attention", lambda m, d=None: contextlib.nullcontext({"pinned": False})):
                return real(self, mdl, inputs, sent, model_id)(prompt)
        return score
    return forward


def _direct_call_as_free_text(wrapper, call_id, call, *, real=agent_activation.direct_call, **kwargs):
    return real(wrapper, call_id, call, **{k: v for k, v in kwargs.items() if k != "outcome"})


def _record_with_words(first, second, rule_id, source_rule_id, reason):
    return dict(pjc.REAL_RECORD(first, second, rule_id, source_rule_id, reason), quote_b=second["text"][:-1], explanation="A sentence the model wrote.")


if __name__ == "__main__":
    print(run_checks())
