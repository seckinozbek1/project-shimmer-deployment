"""One agent, one unit of material, one rule, one backend.

The point of this module is that it does NOT build its own prompt. It builds the
wrapper the pipeline builds, with the pipeline's own `_build_wrapper`, and calls
`AgentWrapper.run_task`, so the bytes that reach the model are the bytes the
pipeline would send for the same inputs. Gate check 146 holds that property in
place: if this module ever grows its own prompt assembly, the check fails.

Backends
  local   the profile the pipeline uses under SHIMMER_BACKEND_PROFILE=local,
          same checkpoints, same loader, same role anchor
  api     the agent's own cloud spec from config/agent_registry.json, which
          stays the sole owner of model choice; --api-model overrides it for a
          controlled comparison and is recorded in the result

Nothing here writes the prompt or the unit text to disk (W8). Results carry the
model's own output, its length and its hash, never the material it was given.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

LOCAL = "local"
API = "api"
PROFILES = (LOCAL, API)

# The narrow task the harness asks for. Same shape as the pipeline's own
# convention_review payload (pipeline.phase_5_5_convention_review), narrowed to
# one unit and one rule, which is what paired review mode will send.
TASK_NAME = "convention_review"


def _pipeline():
    """Imported lazily: the pipeline module is heavy and the harness is not a phase."""
    import pipeline
    return pipeline


def build_orchestrator(root=None, out_root=None, *, registry=None, cost_tracker=None):
    """A real TopOrchestrator, with its run artifacts under `out_root`.

    out_root defaults to the repository, which puts the harness bus in a normal
    output/runs/ folder. A gate check passes a tempdir instead, so the gate stays
    non-mutating. Pass a CostTracker when the calls cost money: every cloud call
    the harness makes has to be countable against the operator's cap.
    """
    from orchestrator import TopOrchestrator
    import run_context as _rc
    root = Path(root or ROOT)
    ctx = _rc.create_run(Path(out_root or root))
    return TopOrchestrator.boot(root, interactive=False, run_adaptive_spawn=False,
                                run_context=ctx, registry=registry,
                                cost_tracker=cost_tracker)


def apply_profile(agents, agent, profile, *, api_backend=None, api_model=None):
    """Rewrite one agent's backend and model for the chosen profile.

    `agents` is the {name: spec} mapping an orchestrator carries as .registry.
    Local uses pipeline._LOCAL_PROFILE, the same table and the same overwrite the
    pipeline performs at startup, so the harness cannot drift from it. Api leaves
    the registry's own cloud spec alone unless the caller names an override.
    """
    spec = agents[agent]
    if profile == LOCAL:
        table = _pipeline()._LOCAL_PROFILE
        if agent not in table:
            raise SystemExit("agent %s has no local-profile mapping" % agent)
        backend, model = table[agent]
        spec["backend"], spec["model"] = backend, model
    elif profile == API:
        if api_backend:
            spec["backend"] = api_backend
        if api_model:
            spec["model"] = api_model
    else:
        raise SystemExit("unknown profile %r" % profile)
    return spec["backend"], spec["model"]


def make_payload(*, unit_id, unit_text, rule_id, rule_text, document_name="",
                 extra=None):
    """The work payload for one (unit, rule) pair."""
    payload = {
        "task": TASK_NAME,
        "document_id": unit_id,
        "document_name": document_name or unit_id,
        "document_text": unit_text,
        "evaluate_against": [rule_id],
        "rule_text": rule_text,
    }
    if extra:
        payload.update(extra)
    return payload


def make_registry_excerpt(rule_id, rule_text, *, category="", severity="", action=""):
    """A one-rule convention registry, in the shape bus_reader._render_conventions reads."""
    return {"conventions": [{"id": rule_id, "rule": rule_text, "category": category,
                             "severity": severity, "action": action}]}


def run_one(agent, *, unit_id, unit_text, rule_id, rule_text, profile=LOCAL,
            orch=None, keys=None, convention_registry=None,
            reference_index_excerpt=None, run_objectives="", max_tokens=2048,
            api_backend=None, api_model=None, document_name=""):
    """Run one agent once and return a flat result record.

    The record carries latency, the backend and model actually used, whether the
    envelope parsed, which contract fields were missing, how many items came back,
    and the model's raw output. It never carries the prompt or the unit text.
    """
    pipeline = _pipeline()
    from agent_wrapper import load_api_keys, is_envelope

    own_orch = orch is None
    if own_orch:
        orch = build_orchestrator()
    if keys is None:
        keys = load_api_keys()

    backend, model = apply_profile(orch.registry, agent, profile,
                                   api_backend=api_backend, api_model=api_model)
    if convention_registry is None:
        convention_registry = make_registry_excerpt(rule_id, rule_text)
    payload = make_payload(unit_id=unit_id, unit_text=unit_text, rule_id=rule_id,
                           rule_text=rule_text, document_name=document_name)

    prior_profile = os.environ.get("SHIMMER_BACKEND_PROFILE")
    if profile == LOCAL:
        os.environ["SHIMMER_BACKEND_PROFILE"] = "local"
    else:
        os.environ.pop("SHIMMER_BACKEND_PROFILE", None)
    wrapper = pipeline._build_wrapper(agent, orch, keys)
    t0 = time.monotonic()
    try:
        result = wrapper.run_task(
            work_payload=payload, run_objectives=run_objectives, channel="main",
            max_tokens=max_tokens, convention_registry=convention_registry,
            reference_index_excerpt=reference_index_excerpt,
            phase="harness", doc_id=str(unit_id),
        )
    finally:
        elapsed = time.monotonic() - t0
        if prior_profile is None:
            os.environ.pop("SHIMMER_BACKEND_PROFILE", None)
        else:
            os.environ["SHIMMER_BACKEND_PROFILE"] = prior_profile

    raw = result.get("raw_text") or ""
    parsed = result.get("parsed")
    missing = result.get("contract_missing") or []
    return {
        "agent": agent,
        "profile": profile,
        "backend": backend,
        "model": model,
        "unit_id": unit_id,
        "rule_id": rule_id,
        "ok": bool(result.get("ok")),
        "error": result.get("error"),
        "envelope_ok": bool(parsed is not None and is_envelope(parsed) and not missing),
        "contract_missing": missing,
        "item_count": len((parsed or {}).get("items", []) or []),
        "latency_s": round(elapsed, 3),
        # structure H2a: which JSON candidate the recovery scan took, and how many
        # valid-but-empty ones it passed over. Counts only, no text (W8).
        "parse_trace": result.get("parse_trace") or {},
        "raw_len": len(raw),
        "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest() if raw else "",
        "raw_text": raw,
        "parsed": parsed,
    }


def run_batch(agents, *, unit_id, unit_text, rule_id, rule_text, profile=LOCAL,
              orch=None, keys=None, **kw):
    """Run several agents against the same (unit, rule) on one orchestrator."""
    from agent_wrapper import load_api_keys
    if orch is None:
        orch = build_orchestrator()
    if keys is None:
        keys = load_api_keys()
    out = []
    for agent in agents:
        try:
            out.append(run_one(agent, unit_id=unit_id, unit_text=unit_text,
                               rule_id=rule_id, rule_text=rule_text, profile=profile,
                               orch=orch, keys=keys, **kw))
        except Exception as e:  # one agent failing must not lose the batch
            out.append({"agent": agent, "profile": profile, "ok": False,
                        "envelope_ok": False, "error": "%s: %s" % (type(e).__name__, e),
                        "latency_s": 0.0, "item_count": 0, "contract_missing": [],
                        "raw_text": "", "raw_len": 0, "raw_sha256": "", "parsed": None,
                        "unit_id": unit_id, "rule_id": rule_id,
                        "backend": "", "model": ""})
    return out


def _read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def main(argv=None):
    p = argparse.ArgumentParser(description="Run one agent on one unit against one rule.")
    p.add_argument("--agent", action="append", required=True,
                   help="agent name; repeat for a batch")
    p.add_argument("--unit-file", required=True, help="file holding the unit of material")
    p.add_argument("--unit-id", default="unit-1")
    p.add_argument("--rule-file", required=True, help="file holding the rule text")
    p.add_argument("--rule-id", default="CONV-001")
    p.add_argument("--profile", choices=PROFILES, default=LOCAL)
    p.add_argument("--api-backend", default=None,
                   help="api profile only: override the registry backend for a "
                        "controlled comparison; the override is recorded in the result")
    p.add_argument("--api-model", default=None,
                   help="api profile only: override the registry model, same reason")
    p.add_argument("--max-tokens", type=int, default=2048)
    p.add_argument("--out", default=None, help="write the result records as JSON here")
    a = p.parse_args(argv)

    results = run_batch(a.agent, unit_id=a.unit_id, unit_text=_read_text(a.unit_file),
                        rule_id=a.rule_id, rule_text=_read_text(a.rule_file),
                        profile=a.profile, max_tokens=a.max_tokens,
                        api_backend=a.api_backend, api_model=a.api_model)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    for r in results:
        print("%-26s %-6s %-16s envelope=%-5s items=%-3d %7.1fs %s" % (
            r["agent"], r["profile"], r.get("model") or "-", r["envelope_ok"],
            r["item_count"], r["latency_s"], r.get("error") or ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
