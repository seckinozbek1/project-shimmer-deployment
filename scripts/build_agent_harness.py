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

# Shared descriptions refer to the structured run_task path. The Draft memo
# has a separate free-text path, documented explicitly rather than implied uniform.
SHARED_PARTS = {
    "constitution_by_default": {
        "decided": True,
        "summary": "Every structured agent task checks the constitution before dispatch. Draft memo generation has a separate free-text path after startup governance.",
        "where": "scripts/agent_wrapper.py: AgentWrapper.run_task calls check_constitution unconditionally. scripts/pipeline.py: _draft_generate_with_evidence calls call_claude directly, bypassing run_task.",
    },
    "receive_format": {
        "decided": True,
        "summary": "Structured tasks receive governing rules, task objectives, work material, conventions and budgeted recent bus context. Each phase supplies its own work payload; Draft uses separate prompts.",
        "where": "scripts/bus_reader.py: assemble_context, called by AgentWrapper.run_task. scripts/pipeline.py constructs each phase payload; editorial objectives and the free-text Draft prompt are separate.",
    },
    "hand_format": {
        "decided": True,
        "summary": "Accepted structured tasks return a common envelope containing flat output items. Malformed replies are recorded as failures. The initial Draft memo is free text.",
        "where": "scripts/agent_wrapper.py: run_task validates {agent, doc_id, items[]} against agent_contracts.json and posts accepted items or CONTRACT_VIOLATION. Draft generation bypasses the envelope contract.",
    },
    "refire_condition_and_limit": {
        "decided": True,
        "summary": "A malformed reply is not automatically retried. Separate documents, bounded legal follow-ups, per-finding polish and editorial escalation can ask an agent for additional work. Provider transport backoff is separate.",
        "where": "scripts/pipeline.py: _run_one has zero contract-failure retries; _deepen_legal_analyst_findings_local, _polish_findings and phase_6_5_editorial_review own their work bounds. agent_wrapper.py call_claude/call_gpt can back off on transport errors. audit/agent_activation.json records actual calls and additional-work triggers.",
    },
}

# No review agent currently retrieves ontology/GNN knowledge into its work payload.
# End-of-run capture and human/API readers exist; this is not a write-only store.
ONTOLOGY_PART = {
    "decided": False,
    "unresolved_because": "No review agent currently draws knowledge from ontology/stores into its task. End-of-run capture, graph/GNN maintenance and console/API readers exist. GNN candidates rank structure, with no demonstrated learned relevance; an agent review feedback path is not implemented.",
}

# Part 8 (fires at all): traced per-agent group against scripts/pipeline.py directly,
# not assumed. Six distinct firing shapes exist in this codebase today: production
# and audit agents (unconditional), the two convention-review agents (the W3 firing
# gate and the subject-chosen paired judging agent), LEGAL_ANALYST (production plus
# the D6 pass-two calls under the local profile), REDACTOR (layer-gated),
# AMENDMENT_DRAFTER (bus-dedup-gated) and the editorial board (parsimony escalation).
FIRES_UNCONDITIONALLY = {
    "summary": "Runs whenever its scheduled stage has work to process.",
    "condition": "Always, once per its fixed phase, unconditionally.",
    "where": "scripts/pipeline.py: PRODUCTION_AGENTS_PER_DOC, "
             "PRODUCTION_AGENTS_CORPUS_LEVEL and AUDIT_AGENTS_PER_DOC, the "
             "fixed per-phase lists that name this agent. A production or "
             "audit agent has no per-agent gate: it produces the material the "
             "convention review consumes, so gating it on rules would starve "
             "the review (docs/api/CONVENTION_ASSIGNMENT_DESIGN.md, W3).",
}
FIRES_CONVENTION_REVIEW = {
    "summary": "In whole-document review, runs when it receives a matching rule "
               "or a rule without a subject label. In passage-by-passage review, "
               "a rule goes to the first eligible reviewer for its subject; a "
               "rule without a subject goes to PRACTICE_AUDITOR. A rule with no "
               "eligible reviewer stays unreviewed, with the reason recorded.",
    "condition": "Wide mode: fires if at least one rule is assigned to it by "
                 "the convention assignment OR at least one loaded rule is "
                 "untagged (an untagged rule keeps today's default routing to "
                 "every convention-review agent); only with zero assigned "
                 "rules and zero untagged rules does it not run. Paired mode: "
                 "each plan's judging agent is chosen by its rule's subject, "
                 "the first convention-review agent among the rule's "
                 "consumer_agents; an untagged rule keeps PRACTICE_AUDITOR; a "
                 "rule with no convention-review consumer gets no judging agent "
                 "at all, its plan recorded in the pairing map as not judged "
                 "(convention distribution step A, built without measurement).",
    "where": "scripts/pipeline.py: _convention_review_firing_agents (the "
             "wide-mode loop of phase_5_5_convention_review, its registry "
             "excerpt filtered per agent by _wide_registry_for_agent) and "
             "_paired_judging_agent (_paired_convention_review); the "
             "assignment is <run>/audit/convention_assignment.json, computed "
             "once at BOOT by scripts/convention_assignment.assign_conventions. "
             "Gate checks 199 and 206 prove both, executed, neutralised and restored.",
}
FIRES_LEGAL_ANALYST = {
    "summary": "Reviews each document once. With local models, it can then "
               "receive a limited number of follow-up questions about its "
               "findings, one at a time. The other findings retain their first review.",
    "condition": "Once in phase 3 per operational document, unconditionally, "
                 "as a production agent; under the local backend profile ALSO "
                 "once per finding up to DEEPEN_MAX_FINDINGS (D6, the two-pass "
                 "split: a second, narrower question per selected finding, "
                 "always serial; other findings keep their pass-one form). Not a retry: the "
                 "re-fire limit on a contract violation stays 0.",
    "where": "scripts/pipeline.py: PRODUCTION_AGENTS_PER_DOC and "
             "_deepen_legal_analyst_findings_local (D6). Observed live on "
             "run 3d3142c8 (2026-09-11): 1 phase-3 call producing 5 findings, "
             "then 5 pass-two calls, 6 in all.",
}
FIRES_REDACTOR = {
    "summary": "Runs only with an active sensitivity layer, no redaction waiver, compiled redaction rules and a document master. Skipped, none, applied, blocked and held-warning outcomes remain distinct.",
    "condition": "Phase 9 is reached after audit synthesis and before phase 8 end-work. The REDACTOR call needs LAYER_ACTIVE, no waiver, compiled rules and review_data.json; phase entry alone does not imply a call. A held format warning does not become a clean-redaction certificate.",
    "where": "scripts/pipeline.py: main phase 9; scripts/sensitivity_layer/redaction_stage.py: run_redaction_phase; scripts/agent_activation.py records the reached gates and dispatch outcomes.",
}
FIRES_AMENDMENT_DRAFTER = {
    "summary": "Amendments are normally built directly from computed findings. "
               "This agent is asked to polish the wording only when you enable "
               "that option and no fresh amendment reply is already available "
               "for the document.",
    "condition": "A fresh bus amendment payload bypasses polishing. Otherwise "
                 "--amendment-polish enables one narrow call per typed irregular "
                 "finding, not one call per document. Empty, untyped and non-irregular "
                 "findings make no call. Failure retains the original finding. "
                 "The deterministic template builds amendments either way. "
                 "Separately, Draft task mode uses this identity for one free-text "
                 "memo through the direct Claude call path before review.",
    "where": "scripts/pipeline.py: phase_6_synthesis, _polish_findings, "
             "main's Draft branch and _draft_generate_with_evidence.",
}
FIRES_EDITORIAL_BOARD = {
    "summary": "The clerk reviews each deliverable. A higher level is called "
               "only if the level below reports confidence below the configured "
               "threshold or, when enabled, an issue beyond its authority. "
               "Escalation stops at the configured highest level.",
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
             "in phase_6_5_editorial_review (trig, reason = "
             "_observation_triggers_escalation(obs, tunables)).",
}

AGENT_FIRING = {
    "PROCESSOR": FIRES_UNCONDITIONALLY,
    "SPEECH_ACT_TAGGER": FIRES_UNCONDITIONALLY,
    "LEGAL_ANALYST": FIRES_LEGAL_ANALYST,
    "ARCHIVIST": FIRES_UNCONDITIONALLY,
    "INST_FINDER": FIRES_UNCONDITIONALLY,
    "CITATION_RESOLVER": FIRES_UNCONDITIONALLY,
    "VERIFIER": FIRES_UNCONDITIONALLY,
    "FACT_CHECKER": FIRES_UNCONDITIONALLY,
    "PRACTICE_AUDITOR": FIRES_CONVENTION_REVIEW,
    "STYLE_GUARDIAN": FIRES_CONVENTION_REVIEW,
    "REDACTOR": FIRES_REDACTOR,
    "AMENDMENT_DRAFTER": FIRES_AMENDMENT_DRAFTER,
    "EDITOR_CLERK": FIRES_EDITORIAL_BOARD,
    "EDITOR_HEAD_OF_UNIT": FIRES_EDITORIAL_BOARD,
    "EDITOR_HEAD_OF_SECTION": FIRES_EDITORIAL_BOARD,
    "EDITOR_HEAD_OF_DEPARTMENT": FIRES_EDITORIAL_BOARD,
    "EDITOR_DEPUTY_DG": FIRES_EDITORIAL_BOARD,
    "EDITOR_DG": FIRES_EDITORIAL_BOARD,
}

# Parts 3 (the rule cluster assigned to it) and 4 (testing against that
# cluster) were unresolved while W2 stood stopped at its premise check. The
# convention assignment (docs/api/CONVENTION_ASSIGNMENT_DESIGN.md, the
# operator's ten answers, commits "convention assignment 1" to "3") decides
# both: an agent's cluster is the set of subjects it declares in
# config/agent_registry.json (empty, by the operator's decision, for the six
# agents no convention-review path reaches), and per run the rules matched to
# it are by_agent[<name>] in <run>/audit/convention_assignment.json. Both
# parts are read from the registry here so the harness cannot drift from it.
def _rule_cluster_part(name, reg):
    subjects = list(reg.get("subjects") or [])
    part = {
        "decided": True,
        "declared_subjects": subjects,
        "where": "config/agent_registry.json agents.%s.subjects (the one-way "
                 "label the agent declares); per run, the rules assigned to it "
                 "are by_agent[%s] in <run>/audit/convention_assignment.json, "
                 "computed once at BOOT by scripts/convention_assignment."
                 "assign_conventions (any overlap between a rule's bracket tags "
                 "and this list, exact token equality, no subject name in code)."
                 % (name, name),
    }
    if not subjects:
        part["empty_by_decision"] = True
        part["subjects_note"] = reg.get("subjects_note") or ""
    return part


def _testing_against_cluster_part(name, reg):
    subjects = list(reg.get("subjects") or [])
    summary = ("Checks verify how rules are assigned and which reviewer is called. "
               "A separate tool can try this agent on a passage and a rule you "
               "choose. No test of this agent's entire assigned rule group is recorded.")
    how = ("Gate check 198 proves the comparison, its route and its console state "
           "on fixture registries; gate check 199 proves the firing gate and the "
           "subject-chosen paired judging agent executed against the real "
           "_paired_convention_review, neutralised and restored. Both test the "
           "mechanism, not this agent in particular. The harness runner "
           "scripts/harness/run_agent.py runs this agent on one unit against one "
           "rule the operator names (--rule-file, --rule-id); it does not select "
           "the rule by subject, so it exercises the agent, not the cluster. No "
           "other per-agent cluster test exists; per run, the rules this agent "
           "was actually given are read from <run>/audit/convention_assignment.json.")
    if not subjects:
        summary += " This agent has no rule group by design."
        how += (" This agent declares no subjects, so there is no cluster to test "
                "against.")
    return {
        "decided": True,
        "summary": summary,
        "how": how,
        "cluster_is_empty_by_decision": not subjects,
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
            # Part 3: the rule cluster assigned to it. Decided: the subjects the
            # agent declares in the registry (convention assignment).
            "rule_cluster": _rule_cluster_part(name, reg),
            # Part 4: testing against that cluster. Decided: gate checks 198/199
            # and the single-agent harness against the agent's own subjects.
            "testing_against_cluster": _testing_against_cluster_part(name, reg),
            # Part 5: ontological knowledge drawn in as required. Unresolved (W7).
            "ontology": dict(ONTOLOGY_PART),
            # Part 6: receive format. Shared, see shared_parts.
            "receive_format": {"see": "shared_parts.receive_format"},
            # Part 7: hand format. Shared, see shared_parts.
            "hand_format": {"see": "shared_parts.hand_format"},
            # Part 8: whether it fires at all, given everything above. Traced
            # per-agent group against real code, not assumed uniform.
            "fires_at_all": dict({"decided": True,
                "activation_audit": "scripts/agent_activation.py records eligibility, activation, "
                    "actual dispatch and outcome in audit/agent_activation.json. "
                    "--activation-profile dense retains reference firing; sparse currently "
                    "retains the same conservative policy and existing phase gates. "
                    "Neither profile forces prohibited or unavailable paths. "
                    "A phase not reached has unknown eligibility, not a successful skip. "
                    "Legal follow-ups and editorial climbs are bounded additional work, "
                    "distinct from the zero contract-failure retry limit."}, **AGENT_FIRING[name]),
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
