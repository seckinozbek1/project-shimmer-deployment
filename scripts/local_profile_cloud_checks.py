"""Gate check: no local-profile path constructs a cloud provider client (S10, outside audit
finding 1, LAW-IV).

INC-031 was one site: the draft memo called call_claude whatever backend the drafter
resolved, so a local-profile draft with a key present would have sent the document to a paid
provider. The S10 sweep looked for every direct call of call_claude, call_gpt or a provider
SDK client made outside AgentWrapper.dispatch and its backend functions; this check runs the
local-profile paths that sweep found, with the two provider SDKs replaced by stand-ins whose
client construction raises and is recorded. Both credentials are set to placeholders, so a
path that reached a cloud backend would get as far as building the client. Nothing reaches a
network, a weight or the real stores: the local model is the recording stand-in of
scripts/reply_records_checks.py, and every run folder is a temporary directory.

  registry      every agent the registry puts on a provider backend is remapped to a local
                backend by pipeline._LOCAL_PROFILE (the table pipeline.main applies), and
                every other agent is already local;
  model gate    model_registry.enforce_current_models over the local-profile registry (the
                pipeline's start-of-run gate) lists no provider's models;
  every agent   dispatch for every agent of the local-profile registry (the one place that
                picks the backend function: run_task, the editorial board, the redaction
                stage and multi-round all reach a model through it);
  draft memo    pipeline._draft_generate_with_evidence for the local drafter (INC-031);
  polish pass   pipeline._polish_findings (--amendment-polish) on one irregular finding, the
                local model's two wording fields merged;
  harness       harness.run_agent.run_one under its local profile, from the registry as
                shipped (cloud backends).

Each passes only with zero clients constructed and the local stand-in answering. Then three
neutralisations, each required to fail and then pass again restored: the draft memo with its
old direct call_claude put back, the polish pass with a direct call_claude put back in place
of dispatch, and _LOCAL_PROFILE with AMENDMENT_DRAFTER left out.
"""
from __future__ import annotations

import ast
import asyncio
import contextlib
import importlib.machinery
import json
import os
import sys
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PROVIDER_BACKENDS = ("claude_api", "openai_api")
_PLACEHOLDER = "TEST_CREDENTIAL_PLACEHOLDER"
KEYS = {"ANTHROPIC_API_KEY": _PLACEHOLDER, "OPENAI_API_KEY": _PLACEHOLDER}
POLISHED = "POLISHED SENTENCE FROM THE LOCAL STAND-IN"
POLISH_FUNCTION = "_polish_findings"
POLISH_WRAPPER = 'wrapper = _build_wrapper("AMENDMENT_DRAFTER", orch, keys)\n'
POLISH_DIRECT = POLISH_WRAPPER + "    wrapper.dispatch = lambda stable, dynamic='', **kw: wrapper.call_claude(stable, dynamic)\n"


class ProviderClientConstructed(Exception):
    """Raised by a stand-in provider client on construction."""


def raising_sdks(built):
    """The two provider SDK modules, each with a client class whose construction is recorded
    in BUILT and raises."""
    def module(sdk, client_name):
        class APITimeoutError(Exception):
            pass

        def construct(*args, **kwargs):
            built.append(sdk)
            raise ProviderClientConstructed("%s client constructed under the local profile" % sdk)
        stand_in = types.ModuleType(sdk)
        # a spec, so a library that probes for the package by name (transformers does) reads it
        stand_in.__spec__ = importlib.machinery.ModuleSpec(sdk, None)
        setattr(stand_in, client_name, construct)
        stand_in.APITimeoutError = APITimeoutError
        return stand_in
    return {"anthropic": module("anthropic", "Anthropic"), "openai": module("openai", "OpenAI")}


@contextlib.contextmanager
def stand_ins(local_replies, built, seen_local):
    """Patch every model boundary: the provider SDKs raise on construction (also when imported
    by name), the local model answers LOCAL_REPLIES in order."""
    import agent_wrapper
    import decoding_policy
    import reply_records_checks as rrc
    real_import = rrc._REAL_IMPORT
    # The envelope constraint (DECODING-B) imports this inside the call; loaded here, before
    # torch is replaced below, so the library's own lazy loader runs on the real modules.
    from transformers import LogitsProcessorList  # noqa: F401
    model = rrc.LocalModel(list(local_replies), seen_local)
    modules = dict(raising_sdks(built), torch=rrc.TORCH, transformers=object())
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(agent_wrapper.importlib, "import_module",
                                         side_effect=lambda n, *a: modules[n] if n in modules else real_import(n, *a)))
        stack.enter_context(patch.dict(sys.modules, {"anthropic": modules["anthropic"], "openai": modules["openai"]}))
        stack.enter_context(patch.object(agent_wrapper, "_load_qwen", return_value=(model, model)))
        stack.enter_context(patch.object(decoding_policy, "policy", return_value=dict(rrc.POLICY)))
        stack.enter_context(patch.dict(os.environ, SHIMMER_MODEL_MODE="base", SHIMMER_PROVIDER_TIMEOUT_S="5",
                                       SHIMMER_BACKEND_PROFILE="local"))
        yield


def shipped_registry():
    return json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]


def local_registry(profile=None):
    """The registry as pipeline.main remaps it under the local profile (the same table, the
    same overwrite)."""
    import pipeline
    profile = pipeline._LOCAL_PROFILE if profile is None else profile
    agents = shipped_registry()
    for name, (backend, model) in profile.items():
        if name in agents:
            agents[name] = dict(agents[name], backend=backend, model=model)
    return agents


class Run:
    """A temporary run folder with the objects a pipeline function is handed."""

    def __init__(self, root, registry):
        import agent_activation
        from constitution import Constitution
        from message_bus import MessageBus
        from run_context import RunContext
        self.ctx = RunContext(project_root=Path(root), run_id="localprofilefixture", run_dir=Path(root) / "run")
        self.ctx.ensure()
        self.registry = registry
        self.audit = agent_activation.initialize(self.ctx, sorted(registry))
        self.orch = SimpleNamespace(constitution=Constitution.load(ROOT / "config" / "constitution.json"),
                                    bus=MessageBus.open(self.ctx.bus_path()), registry=registry, contracts={},
                                    cost_tracker=None, run_context=self.ctx, outbound_masker=None, sensitive=False)

    def wrapper(self, name):
        import pipeline
        return pipeline._build_wrapper(name, self.orch, KEYS)


def envelope(agent, items):
    return json.dumps({"agent": agent, "doc_id": "doc-1", "items": items})


def _registry_case(profile):
    problems = []
    agents = local_registry(profile)
    for name, spec in sorted(shipped_registry().items()):
        if spec.get("backend") in PROVIDER_BACKENDS and name not in profile:
            problems.append("%s is on %s and the local profile does not remap it" % (name, spec["backend"]))
    for name, spec in sorted(agents.items()):
        if spec.get("backend") in PROVIDER_BACKENDS:
            problems.append("%s resolves %s under the local profile" % (name, spec["backend"]))
    return problems, "%d agents, none on a provider backend" % len(agents)


def _model_gate_case(profile, root):
    import model_registry
    built, seen = [], []
    with stand_ins([], built, seen):
        gate = model_registry.enforce_current_models(Path(root), local_registry(profile), KEYS, interactive=False)
    problems = []
    if built:
        problems.append("the model gate constructed %s" % built)
    if not gate.get("ok"):
        problems.append("the model gate stopped: %r" % gate.get("findings"))
    return problems, "model gate: %d agents unverifiable (local), no provider listed" % len(gate.get("skipped") or [])


def _every_agent_case(profile, root):
    import decoding_policy
    agents = local_registry(profile)
    built, seen = [], []
    replies = [envelope(name, []) for name in sorted(agents)]
    problems = []
    with stand_ins(replies, built, seen):
        run = Run(root, agents)
        for name in sorted(agents):
            before = len(built)
            budget = ({"max_new_tokens": 8} if agents[name]["backend"] in decoding_policy.LOCAL_BACKENDS
                      else {"max_tokens": 8})
            result = run.wrapper(name).dispatch("stable", "dynamic", **budget)
            if len(built) != before:
                problems.append("%s (%s) constructed %s" % (name, agents[name]["backend"], built[before:]))
            elif not getattr(result, "ok", False):
                problems.append("%s (%s) failed: %s" % (name, agents[name]["backend"], getattr(result, "error", "")))
    if len(seen) != len(agents) and not problems:
        problems.append("the local stand-in saw %d prompt(s), expected %d" % (len(seen), len(agents)))
    return problems, "dispatch for all %d agents on the local stand-in" % len(agents)


def _draft_case(function, profile, root):
    agents = local_registry(profile)
    built, seen = [], []
    memo, error = None, None
    with stand_ins(["LOCAL DRAFT MEMO"], built, seen):
        run = Run(root, agents)
        try:
            memo = function(run.wrapper("AMENDMENT_DRAFTER"), "Draft a memo.", "## Question\nA question",
                            passages=[], run_ctx=run.ctx)
        except Exception as exc:
            error = "%s: %s" % (type(exc).__name__, exc)
    problems = []
    if built:
        problems.append("the draft memo constructed %s" % built)
    if error:
        problems.append("the draft memo raised (%s)" % error)
    if memo != "LOCAL DRAFT MEMO":
        problems.append("memo %r, expected the local stand-in's" % memo)
    return problems, "draft memo on %s" % agents["AMENDMENT_DRAFTER"]["backend"]


def _polish_case(function, profile, root):
    import finding_record
    import reply_records_checks as rrc
    agents = local_registry(profile)
    built, seen = [], []
    item = dict(rrc.finding("template sentence"), item_id="PRACTICE_AUDITOR:doc-1:u01", revision=1)
    reply = envelope("AMENDMENT_DRAFTER", [{"ref": "REF-0001", "kind": "finding", "confidence": "CONFIDENT",
                                            "explanation": POLISHED, "proposed_text": "corrected line"}])
    out, count, error = None, None, None
    with stand_ins([reply], built, seen):
        run = Run(root, agents)
        try:
            out, count = asyncio.run(function(
                run.orch, KEYS, {"id": "doc-1"}, [item], {"CONV-001": {"id": "CONV-001", "rule": "A rule."}},
                {"u01": {"text": "Unit text."}}, "Objectives.", {"conventions": []}))
        except Exception as exc:
            error = "%s: %s" % (type(exc).__name__, exc)
    problems = []
    if built:
        problems.append("the polish pass constructed %s" % built)
    if error:
        problems.append("the polish pass raised (%s)" % error)
    if len(seen) != 1:
        problems.append("the local stand-in saw %d prompt(s), expected 1" % len(seen))
    if count != 1 or not out or out[0].get("explanation") != POLISHED \
            or out[0].get("explanation_by") != finding_record.WRITTEN_BY_MODEL:
        problems.append("polished %r, explanation %r" % (count, (out or [{}])[0].get("explanation")))
    return problems, "polish pass on %s, 1 finding polished" % agents["AMENDMENT_DRAFTER"]["backend"]


def _harness_case(profile, root):
    import pipeline
    from harness import run_agent
    built, seen = [], []
    registry = shipped_registry()  # as shipped: the harness applies its own local profile
    reply = envelope("LEGAL_ANALYST", [])
    result, error = None, None
    with stand_ins([reply], built, seen), patch.object(pipeline, "_LOCAL_PROFILE", profile):
        run = Run(root, registry)
        try:
            result = run_agent.run_one("LEGAL_ANALYST", unit_id="u01", unit_text="Unit text.", rule_id="CONV-001",
                                       rule_text="A rule.", profile=run_agent.LOCAL, orch=run.orch, keys=KEYS)
        except (Exception, SystemExit) as exc:  # apply_profile exits when the agent is not in the table
            error = "%s: %s" % (type(exc).__name__, exc)
    problems = []
    if built:
        problems.append("the harness constructed %s" % built)
    if error:
        problems.append("the harness raised (%s)" % error)
    if not result or result.get("backend") in PROVIDER_BACKENDS or len(seen) != 1:
        problems.append("harness record %r, local stand-in saw %d" % (
            (result or {}).get("backend"), len(seen)))
    return problems, "harness run_one (local) on %s" % (result or {}).get("backend")


def _cases(draft, polish, profile):
    """Every case; returns (problems by case, summaries)."""
    problems, summaries = {}, []
    with tempfile.TemporaryDirectory(prefix="shimmer_local_cloud_", ignore_cleanup_errors=True) as td:
        for label, run in (("registry", lambda r: _registry_case(profile)),
                           ("model gate", lambda r: _model_gate_case(profile, r)),
                           ("every agent", lambda r: _every_agent_case(profile, r)),
                           ("draft memo", lambda r: _draft_case(draft, profile, r)),
                           ("polish pass", lambda r: _polish_case(polish, profile, r)),
                           ("harness", lambda r: _harness_case(profile, r))):
            folder = Path(td) / label.replace(" ", "_")
            folder.mkdir()
            found, summary = run(folder)
            if found:
                problems[label] = found
            summaries.append(summary)
    return problems, summaries


def _polish_with_direct_call_claude():
    """_polish_findings with its wrapper's dispatch replaced by a direct call_claude, compiled
    in the pipeline's own namespace."""
    import pipeline
    source = (ROOT / "scripts" / "pipeline.py").read_text(encoding="utf-8")
    node = next(n for n in ast.parse(source).body
                if isinstance(n, ast.AsyncFunctionDef) and n.name == POLISH_FUNCTION)
    segment = ast.get_source_segment(source, node)
    if segment.count(POLISH_WRAPPER) != 1:
        raise AssertionError("cannot neutralise: the polish wrapper is not built as %r" % POLISH_WRAPPER)
    namespace = dict(vars(pipeline))
    exec(compile(segment.replace(POLISH_WRAPPER, POLISH_DIRECT), "pipeline_neutralised", "exec"), namespace)
    return namespace[POLISH_FUNCTION]


def _detail(problems):
    return "; ".join("%s: %s" % (label, ", ".join(found)) for label, found in problems.items())


def check():
    """(status, detail) for the gate."""
    import draft_backend_checks
    import pipeline
    draft, polish, profile = pipeline._draft_generate_with_evidence, pipeline._polish_findings, pipeline._LOCAL_PROFILE
    problems, summaries = _cases(draft, polish, profile)
    if problems:
        return "FAIL", "a local-profile path reached a cloud client: " + _detail(problems)
    try:
        neutralised = (
            ("draft memo with its direct call_claude", "draft memo",
             (draft_backend_checks._neutralised_function(), polish, profile)),
            ("polish pass with a direct call_claude", "polish pass", (draft, _polish_with_direct_call_claude(), profile)),
            ("_LOCAL_PROFILE without AMENDMENT_DRAFTER", "registry",
             (draft, polish, {k: v for k, v in profile.items() if k != "AMENDMENT_DRAFTER"})),
            ("_LOCAL_PROFILE without LEGAL_ANALYST", "harness",
             (draft, polish, {k: v for k, v in profile.items() if k != "LEGAL_ANALYST"})))
    except AssertionError as exc:
        return "FAIL", str(exc)
    proofs = []
    for label, case, args in neutralised:
        broken, _ = _cases(*args)
        if case not in broken:
            return "FAIL", "neutralised (%s), the %s case still passed; the check proves nothing" % (label, case)
        again, _ = _cases(draft, polish, profile)
        if again:
            return "FAIL", "after restoring (%s): %s" % (label, _detail(again))
        proofs.append("%s FAILS (%s)" % (label, _detail(broken)))
    return "PASS", ("%s; provider clients constructed: 0; neutralise: %s; restore PASSES"
                    % ("; ".join(summaries), " | ".join(proofs)))


if __name__ == "__main__":
    print(json.dumps(check()))
