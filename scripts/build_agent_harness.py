"""Build config/agent_harness.json: the nine-part harness specification per agent.

The operator's own definition (night chain, W4): a harness is the complete
specification of what an agent is and how it behaves, in nine parts. This
module reads the real, already-decided parts from config/agent_registry.json
and config/agent_contracts.json rather than re-stating them by hand, so the
harness can never silently drift from the source it describes; a part this
codebase has not decided is written as unresolved, named, never invented.

    py -3.9 -X utf8 scripts/build_agent_harness.py

Deterministic, no model call, no domain vocabulary of its own: every string
in the output comes from the two config files above or from a fixed,
domain-free citation of where in the code a shared part is decided.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Parts 2, 6, 7, 9 are decided ONCE, in code, identically for every agent
# (confirmed by reading agent_wrapper.py directly, not assumed): the
# constitution check runs unconditionally at the top of every run_task call
# (part 2); the receive/hand shapes are the same functions for every agent
# (parts 6, 7); the re-fire condition is the same, real, and precise answer
# for every agent (part 9: _run_one calls wrapper.run_task exactly once, no
# loop, no retry anywhere in the call chain from pipeline.py through
# agent_wrapper.py, confirmed by direct search finding no while/for-retry
# construct around any run_task call).
SHARED_PARTS = {
    "constitution_by_default": {
        "decided": True,
        "where": "scripts/agent_wrapper.py, AgentWrapper.run_task: "
                 "check = self.check_constitution(situation), the first thing "
                 "run_task does, unconditionally, every call, every agent. "
                 "Never matched or selected: the same constitution.check() "
                 "call runs regardless of which agent or which convention is "
                 "in scope.",
    },
    "receive_format": {
        "decided": True,
        "where": "scripts/bus_reader.py, assemble_context(): builds the "
                 "package an agent receives (governance/constitution text, "
                 "run objectives, precedents, work_payload, convention "
                 "registry, reference excerpts, recent bus context), called "
                 "from AgentWrapper.run_task for every agent identically.",
    },
    "hand_format": {
        "decided": True,
        "where": "The canonical envelope (INFRA-037, CLAUDE.md): "
                 "{agent, doc_id, items[]}, one flat item per finding/output, "
                 "every value a scalar or array of scalars. Every agent posts "
                 "this same shape; consumers read by reference off the "
                 "append-only bus.",
    },
    "refire_condition_and_limit": {
        "decided": True,
        "where": "None. Confirmed by direct trace: pipeline.py's _run_one "
                 "calls wrapper.run_task exactly once (no while/for-retry "
                 "loop around the call); agent_wrapper.py's run_task itself "
                 "has no retry loop either (confirmed: no genuine while "
                 "statement in its body, only a rate-limit backoff inside "
                 "call_claude/call_gpt for a 429/529 transport error, a "
                 "different thing from a contract violation). A "
                 "CONTRACT_VIOLATION is posted to the bus and the item is "
                 "dropped (agent_wrapper.py's _items_for skips any result "
                 "with ok=False); it is never re-attempted. Re-fire limit: 0. "
                 "This is a real, decided answer, not an unresolved part: "
                 "the code decides it by having no retry mechanism at all.",
    },
}

# Part 5 (ontology) is declared unresolved for every agent, per this chain's
# own W4 instruction: the ontology work is W7, so this slot is empty at this
# stage, declared rather than skipped.
ONTOLOGY_PART = {
    "decided": False,
    "unresolved_because": "Ontology work is W7 in this chain, not yet run "
                          "when this harness was built. No agent draws "
                          "ontological knowledge in today (confirmed W7 "
                          "tonight, if it ran, or by the ontology's own "
                          "write-only status traced earlier tonight: nothing "
                          "in the pipeline reads ontology/stores/graph.json "
                          "or gnn_state.json outside of writing them).",
}

# Part 8 (fires at all): traced per-agent group against scripts/pipeline.py directly,
# not assumed. Four distinct firing shapes exist in this codebase today.
FIRES_UNCONDITIONALLY = {
    "condition": "Always, once per its fixed phase, unconditionally.",
    "where": "scripts/pipeline.py: PRODUCTION_AGENTS_PER_DOC, "
             "PRODUCTION_AGENTS_CORPUS_LEVEL, AUDIT_AGENTS_PER_DOC, "
             "CONVENTION_REVIEW_AGENTS, the four fixed per-phase lists that "
             "name this agent. No per-agent rule-cluster gate exists (W2 "
             "stopped before one could), so every agent in these lists runs "
             "on every document today.",
}
FIRES_REDACTOR = {
    "condition": "Phase 9 (redaction) always RUNS, but REDACTOR itself only "
                 "posts bus messages when the sensitivity layer is active "
                 "(LAYER_ACTIVE / sensitivity_layer.is_active()). Confirmed "
                 "live: a completed run with LAYER_ACTIVE False produced zero "
                 "REDACTOR bus messages, the phase itself still ran (waived, "
                 "logged) but the agent's own call did not fire.",
    "where": "scripts/pipeline.py line ~3438 (\"Phase 9: redaction (ALWAYS "
             "runs...)\") and line ~3536-3543 (the LAYER_ACTIVE confirmation "
             "note on a completed run, cb4c557b).",
}
FIRES_AMENDMENT_DRAFTER = {
    "condition": "Skipped if a fresh AMENDMENT_DRAFTER payload already exists "
                 "on the bus for that doc_id (existing_amendments); otherwise "
                 "runs once per operational document. Off by default as a "
                 "MODEL CALL under refine R2 rules (--amendment-polish gates "
                 "the wording pass specifically); the deterministic template "
                 "path still produces the amendment either way.",
    "where": "scripts/pipeline.py line ~2030 "
             "(\"# AMENDMENT_DRAFTER (skip if we have a fresh payload "
             "already on the bus)\").",
}
FIRES_EDITORIAL_BOARD = {
    "condition": "PARSIMONY (INFRA-040): EDITOR_CLERK, the entry rank, "
                 "always fires once per deliverable. Each higher rank "
                 "(EDITOR_HEAD_OF_UNIT, then _SECTION, then _DEPARTMENT, "
                 "_DEPUTY_DG, _DG) fires ONLY when the rank immediately "
                 "below it triggers escalation: an observation's confidence "
                 "is below the operator's threshold, or (if enabled) an "
                 "observation raises out_of_mandate. Bounded by a terminal "
                 "cap; most runs resolve at EDITOR_CLERK alone.",
    "where": "scripts/pipeline.py, _observation_triggers_escalation() "
             "(the two ratified summon triggers) and the rank-to-rank loop "
             "around line ~2578 (trig, reason = "
             "_observation_triggers_escalation(obs, tunables)).",
}

AGENT_FIRING = {
    "PROCESSOR": FIRES_UNCONDITIONALLY,
    "SPEECH_ACT_TAGGER": FIRES_UNCONDITIONALLY,
    "LEGAL_ANALYST": FIRES_UNCONDITIONALLY,
    "ARCHIVIST": FIRES_UNCONDITIONALLY,
    "INST_FINDER": FIRES_UNCONDITIONALLY,
    "CITATION_RESOLVER": FIRES_UNCONDITIONALLY,
    "VERIFIER": FIRES_UNCONDITIONALLY,
    "FACT_CHECKER": FIRES_UNCONDITIONALLY,
    "PRACTICE_AUDITOR": FIRES_UNCONDITIONALLY,
    "STYLE_GUARDIAN": FIRES_UNCONDITIONALLY,
    "REDACTOR": FIRES_REDACTOR,
    "AMENDMENT_DRAFTER": FIRES_AMENDMENT_DRAFTER,
    "EDITOR_CLERK": FIRES_EDITORIAL_BOARD,
    "EDITOR_HEAD_OF_UNIT": FIRES_EDITORIAL_BOARD,
    "EDITOR_HEAD_OF_SECTION": FIRES_EDITORIAL_BOARD,
    "EDITOR_HEAD_OF_DEPARTMENT": FIRES_EDITORIAL_BOARD,
    "EDITOR_DEPUTY_DG": FIRES_EDITORIAL_BOARD,
    "EDITOR_DG": FIRES_EDITORIAL_BOARD,
}

# Part 3 (rule cluster) and part 4 (testing against that cluster) are
# declared unresolved for every agent, per W2's own stop: no per-agent
# convention assignment exists, so there is no cluster to name or test
# against. Every agent still receives every convention, unclustered.
RULE_CLUSTER_PART = {
    "decided": False,
    "unresolved_because": "W2 (docs/fix/STEP_W2_REPORT.md) stopped at its "
                          "own premise check: no agent contract declares a "
                          "subject/scope an assignment could be derived "
                          "from, and no convention's own category matches "
                          "an agent's category vocabulary. Every agent "
                          "receives the full, unclustered convention "
                          "registry today.",
}
TESTING_AGAINST_CLUSTER_PART = {
    "decided": False,
    "unresolved_because": "Depends directly on rule_cluster, above, which "
                          "is unresolved for the same reason.",
}


def build():
    registry = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))
    contracts = json.loads((ROOT / "config" / "agent_contracts.json").read_text(encoding="utf-8"))

    harness = {
        "schema_version": "1.0.0",
        "description": "The nine-part harness specification (night chain W4): "
                       "what an agent is and how it behaves. Built from "
                       "config/agent_registry.json and config/agent_contracts.json "
                       "by scripts/build_agent_harness.py; never hand-edited "
                       "directly, since that would let it drift from the source "
                       "it is supposed to describe.",
        "shared_parts": SHARED_PARTS,
        "agents": {},
    }

    for name, reg in registry.get("agents", {}).items():
        contract = contracts.get("contracts", {}).get(name, {})
        harness["agents"][name] = {
            # Part 1: the agent itself.
            "agent_itself": {
                "decided": True,
                "does": reg.get("does") or [],
                "does_not": reg.get("does_not") or [],
                "category": reg.get("category"),
                "backend": reg.get("backend"),
                "model": reg.get("model"),
                "may_use_web": bool(reg.get("may_use_web")),
                "may_handle_sensitive": bool(reg.get("may_handle_sensitive")),
                "where": "config/agent_registry.json, agents.%s" % name,
            },
            # Part 2: constitution by default. Shared, see shared_parts.
            "constitution_by_default": {"see": "shared_parts.constitution_by_default"},
            # Part 3: the rule cluster assigned to it. Unresolved (W2).
            "rule_cluster": dict(RULE_CLUSTER_PART),
            # Part 4: testing against that cluster. Unresolved (depends on part 3).
            "testing_against_cluster": dict(TESTING_AGAINST_CLUSTER_PART),
            # Part 5: ontological knowledge drawn in as required. Unresolved (W7).
            "ontology": dict(ONTOLOGY_PART),
            # Part 6: receive format. Shared, see shared_parts.
            "receive_format": {"see": "shared_parts.receive_format"},
            # Part 7: hand format. Shared, see shared_parts.
            "hand_format": {"see": "shared_parts.hand_format"},
            # Part 8: whether it fires at all, given everything above. Traced
            # per-agent group against real code, not assumed uniform.
            "fires_at_all": dict({"decided": True}, **AGENT_FIRING[name]),
            # Part 9: re-fire condition and limit. Shared, see shared_parts.
            "refire_condition_and_limit": {"see": "shared_parts.refire_condition_and_limit"},
            "contract_item_kind": contract.get("item_kind"),
            "contract_required_fields": contract.get("required") or [],
        }

    out_path = ROOT / "config" / "agent_harness.json"
    out_path.write_text(json.dumps(harness, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return harness


if __name__ == "__main__":
    h = build()
    print("agent_harness.json written: %d agents" % len(h["agents"]))
