#!/usr/bin/env python3
"""Check 710 (D-955, NEG-SYNTH-A): the generator and the labeller share the OLMo family, under a stated rule.

Proofs, each run as built (passes), neutralised (must fail), restored and run again (passes), on fixtures only
(no model, no network, no real item):
  generator: the family is declared olmo; claude, gpt, qwen and phi never generate; a model id must belong to the
             declared family (the family string and the id cannot disagree); a dated id is refused;
  labeller:  a same-family id (OLMo) is accepted only while the labeller block carries the same-family rule and
             its forbidden-key list; without them it is refused; qwen, phi, claude and gpt stay refused;
  inputs:    a labelling file carrying a generator prompt, metadata or model id key at any depth is refused.
The Granite 8B fallback is declared and inactive.
"""
from __future__ import annotations

import contextlib
import copy
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "tools"), str(ROOT / "scripts"), str(ROOT / "benchmark" / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import neg_synth as ns  # noqa: E402
import neg_synth_label_pass as lp  # noqa: E402

CFG = ns.load_config()
OLMO = CFG["labeller"]["candidates"][0]


def _try(fn):
    try:
        fn()
        return "ok"
    except ValueError:
        return "refused"


def observe_generator():
    def gen(family, mid, cfg=CFG):
        return _try(lambda: ns.check_generator(family, mid, cfg))
    g = CFG["generation"]
    return {"family": g["generator_family"], "never": sorted(g["families_never_generator"]),
            "olmo": gen("olmo", "olmo-fixture"), "claude": gen("claude", "claude-opus"),
            "gpt": gen("olmo", "gpt-fixture"), "qwen": gen("olmo", "Qwen/Qwen2.5-7B"),
            "id_not_family": gen("olmo", "granite-8b-fixture"), "dated": gen("olmo", "olmo-fixture-20261101"),
            "fallback": [g["generator_fallback"]["family"], g["generator_fallback"]["active"]]}


def expected_generator():
    return {"family": "olmo", "never": ["claude", "gpt", "phi", "qwen"], "olmo": "ok", "claude": "refused",
            "gpt": "refused", "qwen": "refused", "id_not_family": "refused", "dated": "refused",
            "fallback": ["granite", False]}


def neutralise_generator():
    real = ns.check_generator

    def loose(family, model_id, cfg):
        return str(family).lower(), str(model_id)
    return patch.object(ns, "check_generator", loose)


def observe_labeller():
    lab = CFG["labeller"]
    bare = {k: v for k, v in lab.items() if k not in ("same_family_rule", "same_family_forbidden_keys")}

    def model(mid, labeller):
        return _try(lambda: lp.check_model(mid, labeller, "olmo"))
    return {"same_family_with_rule": model(OLMO, lab), "same_family_without_rule": model("allenai/olmo-x", bare),
            "qwen": model("Qwen/Qwen2.5-7B-Instruct", lab), "phi": model("microsoft/phi-3", lab),
            "claude": model("claude-olmo", lab), "gpt": model("gpt-olmo", lab),
            "dated": model("allenai/olmo-instruct-20261101", lab)}


def expected_labeller():
    return {"same_family_with_rule": "ok", "same_family_without_rule": "refused", "qwen": "refused",
            "phi": "refused", "claude": "refused", "gpt": "refused", "dated": "refused"}


def neutralise_labeller():
    return patch.object(lp, "check_model", lambda model_id, labeller, generator_family: model_id)


def observe_inputs():
    forbidden = set(CFG["labeller"]["same_family_forbidden_keys"])
    clean = {"sets": {"dev_1": {"items": 1}}, "prompts": [{"id": "p1", "text": "q"}], "generator_family": "olmo"}

    def with_key(key, deep):
        v = copy.deepcopy(clean)
        (v["sets"]["dev_1"] if deep else v)[key] = "x"
        return _try(lambda: lp.check_inputs_independent(v, forbidden))
    return {"clean": _try(lambda: lp.check_inputs_independent(clean, forbidden)),
            "prompt_top": with_key("generator_prompt", False), "model_id_deep": with_key("generator_model_id", True),
            "metadata": with_key("provenance", True)}


def expected_inputs():
    return {"clean": "ok", "prompt_top": "refused", "model_id_deep": "refused", "metadata": "refused"}


def neutralise_inputs():
    return patch.object(lp, "check_inputs_independent", lambda value, forbidden: None)


PROOFS = ("generator", "labeller", "inputs")


def run_group(number="710"):
    done = []
    for name in PROOFS:
        space = globals()
        observe, expected, neutralise = space["observe_" + name], space["expected_" + name], space["neutralise_" + name]
        try:
            first = observe()
            with neutralise():
                try:
                    broken = observe()
                except Exception as exc:  # noqa: BLE001 - a neutralised proof may raise; that is its failure
                    broken = "raised %s" % type(exc).__name__
            again = observe()
        except Exception as exc:  # noqa: BLE001
            return "FAIL", "%s: %s %s" % (name, type(exc).__name__, str(exc)[:300])
        if first != expected():
            return "FAIL", "%s as built: %s" % (name, str(first)[:600])
        if broken == expected():
            return "FAIL", "%s still passes when neutralised" % name
        if again != expected():
            return "FAIL", "%s after restore: %s" % (name, str(again)[:400])
        done.append(name)
    return "PASS", "%d proofs, each neutralise, fail, restore, pass, no model: the generator and the labeller share the OLMo family under the D-955 rule (%s)" % (len(done), ", ".join(done))


if __name__ == "__main__":
    print(run_group())
