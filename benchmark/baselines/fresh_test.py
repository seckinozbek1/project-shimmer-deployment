"""D-S56 item 4, D-S62 item 1, D-S70 (D-316, D-322, D-326): the trained judge on the fresh ContraDoc set.

Development, exposed. Since D-S70 the fresh set is read once by the FULL SYSTEM (system_test.py),
and this judge's figure is descriptive only, computed inside that one read. The judge-alone read
here REFUSES outright. What stays here is the judge's part:

  build (no model but the embedding model that ranks the pairs)
      py -3.12 benchmark/baselines/fresh_test.py build --workload W [...] --items I --out P [--config F]
          [--calibration-prompts R1]
    One prompts file for the training session: the choice pairs of every fresh document in both
    orders, once for group choice_trained and once, the same bytes, for choice_direct; and B1's own
    prompt for each item in J1's form, groups judge_direct and judge_reason. --calibration-prompts
    adds, to choice_trained alone, half A's choice questions from a file already read on half A, as
    they stand there (prompt_id and user_sha256 unchanged, order controls left out), so the session
    can fit its calibration after the pass; no read counts them.
  bar (no model)
      py -3.12 benchmark/baselines/fresh_test.py bar --prompts P --key K [...] --ids F --items I
          --calibration C --parts P [...] --calibration-key K [...] --calibration-items I
          --calibration-build-items I --calibration-source S --source S [...] --b1 B --out BAR
    The judge's bar, which the system bar names: the size, the stated power, one document per group
    (the groups pinned in fresh_once.py, against each build's parts record), the calibration's
    documents (source ids: none fresh, each one staged document of the calibration build, half A's
    alone), every input by its bytes, the set's key and the attempt from the tracked ledger.
  read: refused (D-326 item 2).

prepare_judge runs before the system read's count (the pass's form, the refit by
judge_calibration.calibrate, the power at the judge's own half A effect, labelled in-sample with
D-294's half B figure beside it); judge_figures runs inside its one opening. The pair question is the
pipeline's own (config/passage_pairs.json's decision block, passage_pairs.render); keys are opened
only by tools/score_corpus.py.

A calibration file (`judge-calibration-v1`) is written by the training session
(benchmark/baselines/judge_calibration.py): `adapter_weights_sha256`, `temperature`, `threshold`,
`fitted_on_documents` (source ids of the half A documents) and `development_only` true.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _path in (str(HERE.parents[1] / "scripts"), str(HERE.parents[1] / "tools"), str(HERE), str(HERE.parent / "adapters")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import choice_decision as cd  # noqa: E402
import choice_judge  # noqa: E402
import choice_read as cr  # noqa: E402
import doc_judge  # noqa: E402
import either_test  # noqa: E402
import fresh_once  # noqa: E402
import pair_judge  # noqa: E402
import passage_pairs  # noqa: E402

CONFIG_PATH = HERE / "fresh_prompt.json"
BAR_SCHEMA = "fresh-bar-v1"
CALIBRATION_SCHEMA = "judge-calibration-v1"
BENCHMARK = "contradoc"
TRAINED, UNTRAINED = "choice_trained", "choice_direct"
B1_GROUPS = either_test.B1_GROUPS
# D-303, D-S62 item 1: one test, the trained judge against B1, so .05 one-sided and no split; the
# chance tail at .05 for the same reason; at most 80 percent flagged; void under 95 percent readable
# (the trained group's prompts and each B1 group apart) or under 90 percent of documents with every
# pair readable (choice_read.is_void). C_BAR's item 5: at least 3 placed. The set is sized for power
# .8: 100 groups, one document each. The stated power is computed from half A's only measured effect
# before training (either against judge_direct: 6 wins, 2 losses of 30 documents), exact sign test,
# and the bar computes it again (stated_power).
FIGURES = {"alpha_one_sided": .05, "chance_at_most": .05, "flagged_share_at_most": .8, "readable_at_least": .95,
           "whole_documents_at_least": cr.FIGURES["whole_documents_at_least"], "placed_at_least": cr.FIGURES["placed_at_least"],
           "documents": 100, "power": {"62": .59, "100": .80}, "power_effect": [6, 2, 30],
           "power_from": "half A: 8 discordant of 30, 6 wins, either against judge_direct (the only effect measured)",
           "untrained_threshold": .9, "untrained_temperature": 1}
# D-326 item 6: an effect read on half A is in-sample (the threshold was chosen on those rows), and
# D-294's half B figure stands beside it. That figure is the lead's to state from D-294's record;
# until it is, it is said to be not stated.
HALF_B_POWER = {"power": None, "means": "not stated: D-294's half B wins and losses against B1 are to be stated by the lead"}
IN_SAMPLE = "in-sample, threshold chosen on these rows"


def _sha(path):
    return cr._sha(path)


def pipeline_question(config):
    """The pipeline's pair question (config/passage_pairs.json's decision block) as a config to
    render with, refused unless the prompts config's pair form is the same template and answers."""
    pipeline = dict(passage_pairs.load_config(), form=passage_pairs.DECISION_FORM)
    form = config["choice"]["forms"]["pair"]
    if form["template"] != pipeline["decision"]["template"] or form["answers"] != pipeline["decision"]["answers"]:
        raise ValueError("the config's pair question is not the pipeline's (config/passage_pairs.json, decision)")
    return pipeline


def half_a(path, config, group):
    """(documents, prompts) of half A's choice questions in a choice prompts file already read on
    half A (choice_judge.py's, P2A's r1), for the calibration the session fits after its pass: each
    prompt as it stands there, its prompt_id and user_sha256 unchanged, moved to `group`. The order
    controls stay out (they measure the answer lines, not the judge), and so does every half B
    document and prompt: the split is choice_read's. Only the PAIR questions come: the calibration fits
    ContraDoc's pairs (judge_calibration.py), and the claim form has since gained its tools block
    (judge-agent, 13efac68), so an older file's claims are not this config's question and the older
    file no longer passes this config's loader as a whole. The file is read as JSON; its pair
    questions are held to this config's template when build writes the fresh file and loads it.
    Refused unless the file asks the same pair form."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value["config"]["choice"]["forms"]["pair"] != config["choice"]["forms"]["pair"]:
        raise ValueError("half A's file asks another pair form than this config")
    halves = cr.split(value["documents"])
    keep = {d for benchmark in halves for d in halves[benchmark][0]}
    prompts = [dict(p, group=group["group"], backend=group["backend"], agent=group["agent"], checkpoint=group["checkpoint"])
               for p in value["prompts"] if p.get("form") == doc_judge.CHOICE_FORM and p.get("choice") == "pair"
               and not p.get("order_control") and p["document_id"] in keep]
    return {d: value["documents"][d] for d in sorted({p["document_id"] for p in prompts})}, prompts


def build(workloads, items_path, out, config_path=CONFIG_PATH, embed=passage_pairs.embed, calibration_prompts=None):
    """The one prompts file of the session (see the module text)."""
    import python_only
    from common import prompt as rules_text
    config = doc_judge.check_config(json.loads(Path(config_path).read_text(encoding="utf-8")))
    groups = {g["group"]: g for g in config["models"]}
    if set(groups) != {TRAINED, UNTRAINED, *B1_GROUPS}:
        raise ValueError("the config names both choice groups and both B1 groups, and no other")
    if any("adapter" in g for g in groups.values()):
        raise ValueError("no group declares an adapter: the trained one takes it at run time")
    pipeline = pipeline_question(config)
    documents, prompts, cases = {}, [], []
    for workload in workloads:
        doc_id, document, item, passages, pairs = pair_judge.proposed(workload, items_path, config["choice"]["forms"]["pair"]["limit"], embed)
        document["conventions"] = [list(c) for c in rules_text.conventions_from_bundle(Path(workload))]
        documents[doc_id] = document
        for group in (TRAINED, UNTRAINED):
            for pair in pairs:
                a, b = passages[pair["a"]], passages[pair["b"]]
                for order, first, second in (("ab", a, b), ("ba", b, a)):
                    user = passage_pairs.render(pipeline, first["text"], second["text"])
                    prompts.append(choice_judge._prompt(groups[group], doc_id, item, "pair", user, pair_id="%d-%d-%s" % (pair["a"], pair["b"], order),
                                                        pair=[pair["a"], pair["b"]], order=order, span_a=[first["start"], first["end"]],
                                                        span_b=[second["start"], second["end"]]))
        cases.append({"document_id": doc_id, "benchmark": item["benchmark"], "rule_id": item["rule_id"],
                      "rule_text": doc_judge.workload_rules(Path(workload))[item["rule_id"]], "item_id": item["item_id"]})
    spec = rules_text.load_prompt()
    b1_config = dict(config, models=[groups[g] for g in B1_GROUPS])
    prompts += doc_judge._comparator_prompts(cases, documents, b1_config, spec, int(python_only.pipeline_literal("PRODUCTION_MAX_TOKENS")))
    for number, prompt in enumerate(prompts, 1):
        prompt["prompt_id"] = "f%06d" % number
    if calibration_prompts is not None:
        more_documents, more = half_a(calibration_prompts, config, groups[TRAINED])
        if set(more_documents) & set(documents) or {p["prompt_id"] for p in more} & {p["prompt_id"] for p in prompts}:
            raise ValueError("half A shares a document or a prompt id with the fresh set")
        documents.update(more_documents)
        prompts += more
    value = {"schema": doc_judge.SCHEMA, "kind": doc_judge.KIND, "config": config, "config_sha256": doc_judge._sha(doc_judge._canonical(config)),
             "documents": documents, "prompts": prompts, "prompt_count": len(prompts), "b1_prompt": spec,
             "b1_prompt_sha256": doc_judge._sha(doc_judge._canonical(spec)), "ranked_by": "embedding",
             "pair_question": "config/passage_pairs.json decision, rendered by passage_pairs.render",
             "reads": "the staged workloads only: no answer key, no reply, no label"}
    doc_judge._write_json(out, value)
    doc_judge.load_prompts(out)
    return value


def calibration(path):
    """The training session's calibration, checked field by field."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    fields = {"schema", "adapter_weights_sha256", "temperature", "threshold", "fitted_on_documents", "development_only"}
    if not (isinstance(value, dict) and set(value) == fields and value["schema"] == CALIBRATION_SCHEMA):
        raise ValueError("a calibration names exactly " + ", ".join(sorted(fields)))
    if not re.fullmatch(r"[0-9a-f]{64}", str(value["adapter_weights_sha256"])):
        raise ValueError("a calibration names its adapter's weights by SHA-256")
    t = value["temperature"]
    if not (type(t) in (int, float) and 0 < t < float("inf")):
        raise ValueError("a calibration's temperature is a positive number")
    if not (type(value["threshold"]) in (int, float) and 0 <= value["threshold"] <= 1):
        raise ValueError("a calibration's threshold is a probability")
    listed = value["fitted_on_documents"]
    if not (isinstance(listed, list) and listed and all(isinstance(d, str) and d for d in listed)):
        raise ValueError("a calibration names the documents it was fitted on")
    if value["development_only"] is not True:
        raise ValueError("a calibration is fitted on development material only (D-S54 item 1)")
    return value




def pass_models(run, adapter):
    """The pass's models, held to the session's form: choice_trained with `adapter` applied, every
    other group with none."""
    models = json.loads((Path(run) / doc_judge.MEASUREMENT_FILE).read_text(encoding="utf-8")).get("models") or {}
    if set(models) != {TRAINED, UNTRAINED, *B1_GROUPS}:
        raise ValueError("the pass did not load all four groups")
    for group, model in models.items():
        applied, digest = model.get("adapter_applied") is True, model.get("adapter_sha256")
        if group == TRAINED and not (applied and digest == adapter):
            raise ValueError("choice_trained was not read with the calibrated adapter")
        if group != TRAINED and (applied or digest):
            raise ValueError("group %s had an adapter applied" % group)
    return {g: {"model_id": m.get("model_id"), "adapter_sha256": m.get("adapter_sha256")} for g, m in sorted(models.items())}


def choice_rows(value, seen, records, group, temperature):
    """A choice group's rows as choice_read reads them, each decision under `temperature`."""
    rows = []
    for p in value["prompts"]:
        if p.get("form") != doc_judge.CHOICE_FORM or p["group"] != group:
            continue
        row = seen.get(p["prompt_id"]) or {}
        record = records.get(row.get("call_id")) or {}
        decision = record.get("decision") if record.get("backend_ok") else None
        rows.append({k: p.get(k) for k in ("prompt_id", "user_sha256", "choice", "benchmark", "document_id", "item_id", "rule_id", "pair", "order")}
                    | {"decision": cd.tempered(decision, temperature) if decision else None})
    return rows


def same_questions(trained, untrained):
    """Both choice groups were asked the same questions, byte for byte."""
    key = lambda rows: sorted((r["document_id"], tuple(r["pair"]), r["order"], r["user_sha256"]) for r in rows)
    if key(trained) != key(untrained):
        raise ValueError("the two choice groups were not asked the same questions")




def power(n, p_discordant, p_win, alpha):
    """The exact one-sided sign test's power on `n` documents, each discordant with probability
    `p_discordant` and, when discordant, a win with probability `p_win`."""
    if not 0 <= p_discordant <= 1 or not 0 <= p_win <= 1:
        raise ValueError("a power is computed from probabilities")
    total = 0.0
    for m in range(n + 1):
        weight = math.comb(n, m) * p_discordant ** m * (1 - p_discordant) ** (n - m)
        if weight < 1e-15:
            continue
        critical = next((w for w in range(m + 1) if cr.sign_test(w, m - w) <= alpha), None)
        if critical is not None:
            total += weight * math.fsum(math.comb(m, k) * p_win ** k * (1 - p_win) ** (m - k) for k in range(critical, m + 1))
    return total


def stated_power():
    """FIGURES' power, computed again from the effect it names; the bar refuses a stated figure that
    is not this, rounded to two places."""
    wins, losses, documents = FIGURES["power_effect"]
    return {str(n): round(power(n, (wins + losses) / documents, wins / (wins + losses), FIGURES["alpha_one_sided"]), 2)
            for n in (62, FIGURES["documents"])}


def _clopper_pearson(k, n, level=.95):
    """The exact interval of a binomial proportion, by bisection on the binomial tails."""
    tail = (1 - level) / 2

    def upper_tail(p):
        return math.fsum(math.comb(n, j) * p ** j * (1 - p) ** (n - j) for j in range(k, n + 1))

    def lower_tail(p):
        return math.fsum(math.comb(n, j) * p ** j * (1 - p) ** (n - j) for j in range(0, k + 1))

    def solve(f, rising):
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if (f(mid) < tail) == rising:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    low = 0.0 if k == 0 else solve(upper_tail, True)
    high = 1.0 if k == n else solve(lower_tail, False)
    return low, high


def power_at_effect(wins, losses, documents):
    """Item 6 (D-316): the power at a measured effect, with its interval: the point, and the power at
    the low and the high ends of both proportions' exact 95 percent intervals together."""
    n, alpha = FIGURES["documents"], FIGURES["alpha_one_sided"]
    discordant = wins + losses
    if not documents or not discordant:
        return {"wins": wins, "losses": losses, "documents": documents, "power": None, "low": None, "high": None,
                "means": "undefined: the trained judge and the comparator B1 group disagree on no half A document, so there is no effect to size"}
    d_low, d_high = _clopper_pearson(discordant, documents)
    w_low, w_high = _clopper_pearson(wins, discordant)
    return {"wins": wins, "losses": losses, "documents": documents,
            "power": round(power(n, discordant / documents, wins / discordant, alpha), 4),
            "low": round(power(n, d_low, w_low, alpha), 4), "high": round(power(n, d_high, w_high, alpha), 4),
            "interval": "exact 95 percent intervals of the discordant share and of the wins among them"}


# The bar's inputs: name, then whether it is one file, a list of files or a folder of B1 labels.
INPUTS = (("prompts", "file"), ("ids", "file"), ("items", "file"), ("calibration", "file"),
          ("parts", "files"), ("keys", "files"), ("calibration_keys", "files"), ("calibration_items", "file"),
          ("calibration_build_items", "file"), ("calibration_source", "file"), ("sources", "files"), ("b1", "labels"))


def input_digests(inputs):
    """{name: digest} of every input by its bytes, the fresh keys through the scorer's own key_digest
    (the lead's ruling on round 1 item 9), so the read checks them before it is counted. A list is
    digested in sorted order."""
    out = {}
    for name, kind in INPUTS:
        value = inputs[name]
        if name == "keys":
            out[name] = doc_judge.keys_digest(doc_judge._score_corpus(), value)
        elif kind == "file":
            out[name] = _sha(value)
        elif kind == "files":
            out[name] = doc_judge._sha("\n".join(sorted(_sha(p) for p in value)))
        else:
            out[name] = cr.labels_digest(value)
    return out


def _sources_of(items_path):
    return {r["document_id"]: r["source_document_id"] for r in json.loads(Path(items_path).read_text(encoding="utf-8"))["items"]}


def one_per_group(inputs, documents):
    """Item 13: every fresh document's group, as its build's parts record states it, is a group of the
    pinned groups (fresh_once.groups: D-S45's fresh groups and role B's moved assignment) holding it, no two fresh documents share one, and each is its group's lowest SHA-256
    of `20261108:` plus its id."""
    groups = fresh_once.groups()
    cluster = {}
    for path in inputs["parts"]:
        for row in json.loads(Path(path).read_text(encoding="utf-8"))["documents"]:
            cluster[row["source_document_id"]] = row["cluster"]
    sources = _sources_of(inputs["items"])
    seen = {}
    for document in documents:
        source = sources[document]
        group = cluster.get(source)
        if group is None or source not in groups.get(group, []):
            raise ValueError("a fresh document's group is not in the groups file: " + source)
        if group in seen:
            raise ValueError("two fresh documents of one group: %s and %s" % (seen[group], source))
        seen[group] = source
        if source != min(groups[group], key=lambda d: doc_judge._sha("20261108:" + d)):
            raise ValueError("a fresh document is not its group's lowest SHA-256: " + source)
    return len(seen)


def calibration_documents(inputs, fitted):
    """Item 1: the calibration's documents (source ids, as judge_calibration writes them) are none of
    them a fresh document by source id, each is one staged document of the calibration build (its
    items file), and those are half A's alone, never half B's."""
    fresh = set(json.loads(Path(inputs["ids"]).read_text(encoding="utf-8"))["documents"]) | set(_sources_of(inputs["items"]).values())
    if fresh & set(fitted["fitted_on_documents"]):
        raise ValueError("the calibration was fitted on a fresh document")
    staged = {}
    for document, source in _sources_of(inputs["calibration_build_items"]).items():
        staged.setdefault(source, set()).add(document)
    missing = [d for d in fitted["fitted_on_documents"] if len(staged.get(d, ())) != 1]
    if missing:
        raise ValueError("a calibration document is in no calibration build: " + missing[0])
    documents = {next(iter(staged[d])) for d in fitted["fitted_on_documents"]}
    known, _, _ = cr.universe(inputs["calibration_keys"], inputs["calibration_items"])
    half_a, half_b = cr.halves(known[BENCHMARK])
    if documents & half_b:
        raise ValueError("the calibration was fitted on a half B document")
    if not documents <= half_a:
        raise ValueError("the calibration was fitted on a document outside half A")
    return len(documents)


def documents_before(inputs):
    """{document: [item rows]} from the items file, held to the ids file and to the keys by their paths
    (<build>/<document>/answer_key.json, one per document); no fresh key is read before the count."""
    rows = json.loads(Path(inputs["items"]).read_text(encoding="utf-8"))["items"]
    documents = {}
    for row in rows:
        documents.setdefault(row["document_id"], []).append({k: row[k] for k in ("item_id", "document_id", "rule_id", "benchmark")})
    if sorted({r["source_document_id"] for r in rows}) != sorted(json.loads(Path(inputs["ids"]).read_text(encoding="utf-8"))["documents"]):
        raise ValueError("the items are not the fresh set's documents")
    if sorted(Path(k).parent.name for k in inputs["keys"]) != sorted(documents) or any(Path(k).name != "answer_key.json" for k in inputs["keys"]):
        raise ValueError("the keys are not one per fresh document")
    return documents


def bar_value(inputs):
    documents = documents_before(inputs)
    if len(documents) != FIGURES["documents"]:
        raise ValueError("the test is sized for %d documents (power %.2f); this set has %d (power at 62: %.2f)"
                         % (FIGURES["documents"], FIGURES["power"][str(FIGURES["documents"])], len(documents), FIGURES["power"]["62"]))
    if FIGURES["power"] != stated_power():
        raise ValueError("the stated power is not the power of the stated effect")
    fitted = calibration(inputs["calibration"])
    groups = one_per_group(inputs, documents)
    fitted_count = calibration_documents(inputs, fitted)
    return {"schema": BAR_SCHEMA, "figures": FIGURES, "attempt": fresh_once.attempt(), "inputs": input_digests(inputs),
            "set_key": fresh_once.set_key(inputs["ids"], inputs["keys"]), "groups": groups,
            "calibration_documents": fitted_count, "calibration": {k: fitted[k] for k in ("adapter_weights_sha256", "temperature", "threshold")}}


def open_bar(bar_path, inputs):
    """The bar, its figures the code's and every input byte for byte the one it names."""
    bar = json.loads(Path(bar_path).read_text(encoding="utf-8"))
    if bar.get("schema") != BAR_SCHEMA or bar.get("figures") != FIGURES or bar.get("attempt") != fresh_once.attempt():
        raise ValueError("the bar states other figures than the code's")
    got = input_digests(inputs)
    for name, _ in INPUTS:
        if (bar.get("inputs") or {}).get(name) != got[name]:
            raise ValueError("the bar names other inputs: " + name)
    return bar


def precision_holds(candidate, other):
    """D-326 item 5, C_BAR item 4's rule: with at least 5 flags from the comparator B1 group on these
    items, precision at least its; with fewer, at least B1's whole-sample ContraDoc precision (.75,
    choice_read.FIGURES), since a precision of under 5 flags is not a figure to be held to."""
    if candidate["precision"] is None:
        return False
    if other["flagged"] >= cr.FIGURES["b1_flags_for_precision"]:
        return candidate["right"] * other["flagged"] >= other["right"] * candidate["flagged"]
    return candidate["precision"] >= cr.FIGURES["contradoc_b1_precision"]


def tests(candidate, other, wins, losses, place_row=None, python=None):
    """Every item of the bar: the sign test, C_BAR's item 1 (accuracy above and net at least the
    comparator's), precision at least its, the chance tail, the flagged share, and item 5 (placed,
    the placed share and above the Python-only control)."""
    precision = precision_holds(candidate, other)
    out = {"sign_test": cr.sign_test(wins, losses) <= FIGURES["alpha_one_sided"], "above_b1": cr.above(BENCHMARK, candidate, None, other),
           "precision": precision, "chance": candidate["chance_tail"] <= FIGURES["chance_at_most"],
           "flagged": candidate["flagged"] <= FIGURES["flagged_share_at_most"] * candidate["items"]}
    if place_row is not None:
        out.update(placed=place_row["placed"] >= FIGURES["placed_at_least"],
                   placed_share=2 * place_row["placed"] >= place_row["flagged_with_two_marks"],
                   above_python=candidate["net"] > python["net"])
    return out


def refit(inputs, run, out, calibrate=None):
    """Item 5: the calibration fitted again from the half A questions of this very pass, by the
    training session's own calibrator, and held to the given one value by value."""
    if calibrate is None:
        import judge_calibration
        calibrate = judge_calibration.calibrate
    folder = Path(out) / "refit"
    record = calibrate(inputs["prompts"], run, inputs["calibration_keys"], inputs["calibration_items"], inputs["calibration_source"],
                       inputs["b1"], folder, inputs["calibration_build_items"])
    again = folder / "calibration.json"
    if not record.get("written") or not again.is_file():
        raise ValueError("the refit wrote no calibration: no read")
    mine, given = calibration(again), calibration(inputs["calibration"])
    if any(mine[k] != given[k] for k in ("adapter_weights_sha256", "temperature", "threshold", "fitted_on_documents")):
        raise ValueError("the calibration is not the refit's: no read")
    return record


def half_a_effect(inputs, run, fitted, out):
    """Item 6: the trained judge's own effect on half A: group choice_trained of this very pass (the
    session's last checkpoint), on half A's documents, at its own temperature and threshold, against
    the comparator B1 group of half A (C_BAR's rule), as wins and losses. Never another method's
    counts. No fresh key."""
    known, left_out, by_key = cr.universe(inputs["calibration_keys"], inputs["calibration_items"])
    half, _ = cr.halves(known[BENCHMARK])
    documents = {d: known[BENCHMARK][d] for d in half}
    value, seen, records = pair_judge.finished_pass(inputs["prompts"], run)
    rows = [r for r in choice_rows(value, seen, records, TRAINED, fitted["temperature"]) if r["choice"] == "pair" and r["document_id"] in documents]
    view = cr.view(BENCHMARK, documents, rows, value["config"]["choice"]["forms"], fitted["threshold"])
    scored, _ = cr.score(view, inputs["calibration_keys"], Path(out) / "half_a", left_out, "half_a_trained")
    comparator, _ = cr.comparator(BENCHMARK, documents, by_key, inputs["b1"], left_out)
    if comparator is None:
        raise ValueError("no B1 group is a comparator on half A")
    wins, losses = cr.discordant(scored, cr.b1_rows(comparator["group"], documents, by_key, inputs["b1"], left_out))
    return {"wins": wins, "losses": losses, "documents": len(documents), "comparator": comparator["group"]}


def read(*args, **kwargs):
    """Refused outright (D-326 item 2): the fresh set is opened once, by the system read
    (system_test.py), which computes this judge's figure beside its own, descriptive only."""
    raise ValueError("the judge-alone read is refused: the fresh set is read once, by the system read (D-S70, D-326)")


def prepare_judge(bar_path, run, inputs, out, *, calibrate=None, effect=half_a_effect):
    """The judge's part of the system read, before the count, with no fresh key opened: the bar and
    every input by its bytes, the pass's form, the refit, and the power at the trained judge's own
    half A effect (in-sample, with D-294's half B beside it), written to the folder. Returns the bar
    and that power."""
    bar = open_bar(bar_path, inputs)
    out = Path(out)
    fitted = bar["calibration"]
    pass_models(run, fitted["adapter_weights_sha256"])
    pair_judge.finished_pass(inputs["prompts"], run)
    refit(inputs, run, out, calibrate)
    measured = effect(inputs, run, fitted, out)
    before = dict(power_at_effect(measured["wins"], measured["losses"], measured["documents"]), comparator=measured.get("comparator"),
                  label=IN_SAMPLE, half_b=HALF_B_POWER, stated=FIGURES["power"][str(FIGURES["documents"])], written="before the read")
    doc_judge._write_json(out / "judge_before_read.json", before)
    return bar, before


def void_reasons(trained, documents, b1_readable):
    """(why the read is void, the trained prompts' readable share, the share of documents with every
    pair readable): under 95 percent of the trained group's prompts readable, under 90 percent of the
    documents with every pair readable (choice_read.is_void's figures), or any B1 group under 95
    percent readable, each B1 group on its own (item 8)."""
    _, readable, whole = cr.is_void(trained, documents)
    floor = FIGURES["readable_at_least"]
    reasons = []
    if readable < floor:
        reasons.append("trained prompts readable %.3f" % readable)
    if whole < FIGURES["whole_documents_at_least"]:
        reasons.append("documents with every pair readable %.3f" % whole)
    reasons += ["%s prompts readable %.3f" % (g, v) for g, v in sorted(b1_readable.items()) if v < floor]
    return reasons, readable, whole


def _readable(rows):
    return round(sum(cr.state(r) == cr.READ for r in rows) / max(len(rows), 1), 6)


def _marks(sc, key, item, sentences, sources):
    """The scorer's marks of an item, read from whichever source file holds its record."""
    for source in sources:
        try:
            return sc.marked_passages(key, item, sentences, source)
        except SystemExit:
            continue
    raise ValueError("no source file holds the record of item " + item)


def placed(view_rows, scored, by_key, sources, texts, value_documents):
    """C_BAR item 5 on the fresh set: where the trained judge's flags stand, and the Python-only
    control on the same number of flags (choice_read.placed, its source per document)."""
    sc = doc_judge._score_corpus()
    gold = {r["document_id"]: r["gold"] == cr.FLAG for r in scored}
    flags = {r["document_id"]: set(map(tuple, r.get("pairs") or [])) for r in view_rows}
    places, on_mark = {}, 0
    for r in view_rows:
        if gold[r["document_id"]]:
            marks = _marks(sc, by_key[r["document_id"]], r["item_id"],
                           [p["text"] for p in passage_pairs.passages(texts[r["document_id"]]["text"])], sources)
            places[r["document_id"]] = pair_judge.place(flags[r["document_id"]], marks)
            on_mark += sum(1 for pair in flags[r["document_id"]] if set(pair) & set(marks["marked"]))
    row = dict(pair_judge.counts(flags, gold, places), pairs_on_mark=on_mark)
    return row, pair_judge.control({"documents": value_documents}, gold, row["flagged"])


def judge_figures(bar, run, inputs, out):
    """The judge alone on the fresh set, descriptive only: called inside the system read's one opening."""
    keys = inputs["keys"]
    documents, by_key = either_test.universe(keys, inputs["ids"], inputs["items"])
    if len(documents) != FIGURES["documents"]:
        raise ValueError("the test is sized for %d documents; this set has %d" % (FIGURES["documents"], len(documents)))
    fitted = bar["calibration"]
    models = pass_models(run, fitted["adapter_weights_sha256"])
    value, seen, records = pair_judge.finished_pass(inputs["prompts"], run)
    forms = value["config"]["choice"]["forms"]
    trained = cr.within(choice_rows(value, seen, records, TRAINED, fitted["temperature"]), BENCHMARK, documents)
    untrained = cr.within(choice_rows(value, seen, records, UNTRAINED, FIGURES["untrained_temperature"]), BENCHMARK, documents)
    same_questions(trained, untrained)
    left_out = set()
    trained_view = cr.view(BENCHMARK, documents, trained, forms, fitted["threshold"])
    trained_scored, trained_figures = cr.score(trained_view, keys, out, left_out, "trained")
    untrained_scored, untrained_figures = cr.score(cr.view(BENCHMARK, documents, untrained, forms, FIGURES["untrained_threshold"]), keys, out,
                                                   left_out, "untrained")
    b1, b1_readable = {}, {}
    for group in B1_GROUPS:
        replies = either_test.b1_group_rows(value, seen, records, group)
        scored = either_test.judge_read.label_rows(replies, keys, out, left_out, group + "_b1")
        b1[group] = {"scored": scored, "figures": cr.figures(scored)}
        b1_readable[group] = round(sum(not r["abstain"] for r in replies) / max(len(replies), 1), 6)
    reasons, readable, whole = void_reasons(trained, documents, b1_readable)
    readable = {"trained_prompts": readable, "trained_whole_documents": whole, "b1_prompts": b1_readable}
    group = either_test.comparator({g: v["figures"] for g, v in b1.items()})
    beside = cr.discordant(trained_scored, untrained_scored)
    place_row, python = placed(trained_view, trained_scored, by_key, inputs["sources"], value["documents"], value["documents"])
    result = {"schema": "fresh-judge-v1", "descriptive": True, "figures": FIGURES, "attempt": bar["attempt"], "documents": len(documents), "models": models,
              "calibration": fitted, "readable": readable, "untrained_readable": _readable(untrained),
              "trained": trained_figures, "untrained": untrained_figures, "b1": {g: v["figures"] for g, v in b1.items()}, "comparator": group,
              "placed": place_row, "python_control": python, "power_stated": FIGURES["power"][str(FIGURES["documents"])],
              "beside": {"trained_against_untrained": {"wins": beside[0], "losses": beside[1], "tested": False},
                         "untrained_against_comparator": None},
              "means": "a keep says the trained judge goes on; it never says the target is met"}
    if group is not None:
        w, l = cr.discordant(untrained_scored, b1[group]["scored"])
        result["beside"]["untrained_against_comparator"] = {"wins": w, "losses": l, "tested": False}
    if group is None:
        reasons.append("no B1 group is a comparator")
    if reasons:
        return dict(result, result="void", void_reasons=reasons, reading="descriptive only: void, nothing is said of the trained judge")
    wins, losses = cr.discordant(trained_scored, b1[group]["scored"])
    checks = tests(trained_figures, b1[group]["figures"], wins, losses, place_row, python)
    kept = all(checks.values())
    return dict(result, wins=wins, losses=losses, sign_test=cr.sign_test(wins, losses), tests=checks, result="keep" if kept else "drop",
                reading="descriptive only: " + ("the bar's items hold" if kept else "not shown at this size"))


def _inputs(args):
    return {"prompts": args.prompts, "ids": args.ids, "items": args.items, "calibration": args.calibration,
            "parts": args.parts, "keys": args.key, "calibration_keys": args.calibration_key, "calibration_items": args.calibration_items,
            "calibration_build_items": args.calibration_build_items, "calibration_source": args.calibration_source,
            "sources": args.source, "b1": args.b1}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--workload", action="append", required=True)
    b.add_argument("--items", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--config", default=str(CONFIG_PATH))
    b.add_argument("--calibration-prompts", help="a choice prompts file read on half A, whose half A questions join group choice_trained")
    for name in ("bar", "read"):
        p = sub.add_parser(name)
        for flag in ("--prompts", "--ids", "--items", "--calibration", "--calibration-items", "--calibration-build-items",
                     "--calibration-source", "--b1", "--out"):
            p.add_argument(flag, required=True)
        for flag in ("--key", "--parts", "--calibration-key", "--source"):
            p.add_argument(flag, action="append", required=True)
        if name == "read":
            p.add_argument("--bar")
            p.add_argument("--run")
            for action in p._actions:
                action.required = False
    args = parser.parse_args(argv)
    if args.command == "build":
        value = build(args.workload, args.items, args.out, args.config, calibration_prompts=args.calibration_prompts)
        print("prompts", value["prompt_count"], "documents", len(value["documents"]))
    elif args.command == "bar":
        print(json.dumps(cr.write_once(args.out, bar_value(_inputs(args)))))
    else:
        read()
    return 0


if __name__ == "__main__":
    sys.exit(main())
