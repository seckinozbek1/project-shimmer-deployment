"""Project Shimmer pipeline driver (genesis Parts XI + XVIII).

Lifecycle:
  - BOOT: load constitution, bus, adaptive_spawn, convention_parser, reference_builder
  - DATE CASCADE: resolve dates for input/context/ documents; apply review_scope cutoff;
                  populate input/operational/ from the operational subset
  - PHASE 1: situation assessment
  - PHASE 3-4: content production (per-doc + corpus-level)
  - PHASE 5: verification + fact-check
  - PHASE 5.5: convention review (PRACTICE_AUDITOR + STYLE_GUARDIAN against conventions)
  - PHASE 6: synthesis, context_summary, operative_summary, amendments JSON, amendments docx
  - PHASE 7: DELTA proposals -> operator escalation
  - PHASE 8: persist, run summary

CLI shortcuts (also): --save-snapshot, --load-snapshot, --reset-snapshot, --list-snapshots
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import re
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))  # repo root, so the corpus_ingest package is importable (M1)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import agent_wrapper
from agent_wrapper import (AgentWrapper, load_api_keys, decode_items,
                           current_items, make_envelope, is_envelope)
import amendment_render
from audit_synthesizer import AuditSynthesizer
from constitution import Constitution
from message_bus import MessageBus
import ontology_capture
import ontology_graph
import ontology_gnn
import ontology_store
from convention_parser import parse_conventions, write_registry
import convention_assignment
from sensitivity_layer import redaction_rules
import sensitivity_layer
from corpus_validator import extract_distinctive_terms, validate_corpus_entry
import embedding_store
from cost_tracker import CostTracker, estimate_cost
from document_dating import resolve_dates, write_dates
from model_registry import enforce_current_models
from snapshot_manager import (
    list_snapshots, load_snapshot, reset_snapshot, save_snapshot,
)
from shimmer_logging import get_logger, log_phase_done, log_event
from orchestrator import OperatorDecision, TopOrchestrator
import finding_record
import paired_review as paired_review_mod
import pairing_map as pairing_map_mod
import reference_tables as reference_tables_mod
from pipeline_amendment_validator import validate_amendment_payload
import verifiability_gate
from reference_builder import ReferenceIndex
import reference_builder
import constitution_guard
from sensitivity_layer.redaction_stage import run_redaction_phase
import redaction_gate
import role_resolution
import run_context as run_context_mod
from review_scope import apply_cutoff
from search_router import SearchRouter
from summary_generators import render_context_summary, render_operative_summary
import text_extract


# Distinctive-term extraction is delegated to corpus_validator.extract_distinctive_terms,
# which runtime-detects CJK content and switches between whitespace tokens and
# character bigrams. A single function serves both the context-summary filter
# (FIX 2) and the corpus integrity check (FIX 4).


def _filter_context_refs_for_doc(
    all_context_refs: list[dict],
    doc_text: str,
    min_overlap: int = 2,
    fallback_first_n: int = 30,
    cap: int = 30,
) -> list[dict]:
    """Return context refs whose text_excerpt shares >= min_overlap distinctive
    words with doc_text. Falls back to the first fallback_first_n refs if
    fewer than 5 pass the filter."""
    if not all_context_refs:
        return []
    distinctive = set(extract_distinctive_terms(doc_text, n=20))
    if not distinctive:
        return all_context_refs[:cap]
    kept = []
    for ref in all_context_refs:
        excerpt = (ref.get("text_excerpt") or "").casefold()
        if not excerpt:
            continue
        hits = sum(1 for w in distinctive if w in excerpt)
        if hits >= min_overlap:
            kept.append((hits, ref))
    if len(kept) < 5:
        return all_context_refs[:fallback_first_n]
    kept.sort(key=lambda kv: -kv[0])
    return [ref for _, ref in kept[:cap]]


def _semantic_filter_context_refs(
    all_context_refs: list[dict],
    doc_text: str,
    embed_store: dict | None,
    *,
    n: int = 20,
) -> list[dict] | None:
    """Per Part XXI: when an embedding store is available, retrieve top-n
    context passages by cosine similarity to the operational document's
    first-page text. Map each result's ref_id back to an entry in the
    existing reference_index so citations remain consistent.

    Returns the filtered list, or None if the store isn't available
    (caller falls back to Zipfian filtering).
    """
    if embed_store is None or not all_context_refs or not doc_text:
        return None
    by_ref = {r.get("ref_id"): r for r in all_context_refs if r.get("ref_id")}
    if not by_ref:
        return None
    head = doc_text[:4000]  # the doc's first-page-equivalent slice as the query
    try:
        results = embedding_store.query_store(embed_store, head, n=n)
    except Exception as e:
        print(f"[pipeline] WARN: embedding query failed ({type(e).__name__}: {e}); "
              "Zipfian fallback active", file=sys.stderr, flush=True)
        return None
    if not results:
        return None
    out: list[dict] = []
    seen = set()
    for r in results:
        rid = r.get("ref_id")
        if rid in seen:
            continue
        seen.add(rid)
        if rid in by_ref:
            out.append(by_ref[rid])
        else:
            # Embedding store may have minted its own ref_ids (e.g. when built
            # without a shared reference_index); construct a ref dict so the
            # downstream summary still receives the passage with citation.
            out.append({
                "ref_id": rid, "input_type": "context",
                "document_id": r.get("doc_id", "?"),
                "document_name": r.get("doc_name", "?"),
                "location": {"page": r.get("page", "?"), "paragraph": 0},
                "text_excerpt": reference_builder.excerpt(r.get("text") or ""),
            })
    return out or None


def _hit_to_ref_dict(hit: dict, baseline_by_ref: dict) -> dict:
    """Map an embedding-store hit to the reference-dict shape that
    downstream code (context_summary, agent context) expects."""
    rid = hit.get("ref_id")
    if rid and rid in baseline_by_ref:
        merged = dict(baseline_by_ref[rid])
        merged.setdefault("similarity", hit.get("similarity"))
        return merged
    return {
        "ref_id": rid, "input_type": "context",
        "document_id": hit.get("doc_id", "?"),
        "document_name": hit.get("doc_name", "?"),
        "location": {"page": hit.get("page", "?"), "paragraph": 0},
        "text_excerpt": reference_builder.excerpt(hit.get("text") or ""),
        "similarity": hit.get("similarity"),
    }


def _provision_aware_context_refs(
    all_context_refs: list[dict],
    doc_text: str,
    provision_texts: list[str],
    embed_store: dict | None,
    *,
    n_baseline: int = 10,
    n_per_provision: int = 5,
    cap: int = 30,
) -> list[dict] | None:
    """Per Part XXI amendment: combine a per-document baseline query with
    per-provision queries (top n_per_provision each) to give agents diverse
    context. Deduplicates by ref_id; preserves baseline-first order.

    Returns the combined list, or None when the embedding store isn't
    available (caller falls back to Zipfian filtering)."""
    if embed_store is None or not doc_text:
        return None
    baseline_by_ref = {r.get("ref_id"): r for r in (all_context_refs or [])
                       if r.get("ref_id")}
    head = doc_text[:4000]
    try:
        baseline_hits = embedding_store.query_store(embed_store, head, n=n_baseline)
    except Exception as e:
        print(f"[pipeline] WARN: baseline embedding query failed "
              f"({type(e).__name__}: {e})", file=sys.stderr, flush=True)
        return None
    out: list[dict] = []
    seen: set[str] = set()
    for h in baseline_hits:
        rid = h.get("ref_id")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        out.append(_hit_to_ref_dict(h, baseline_by_ref))
    # Per-provision queries: each adds up to n_per_provision new refs.
    for prov in (provision_texts or []):
        if not prov:
            continue
        try:
            hits = embedding_store.query_store(embed_store, prov, n=n_per_provision)
        except Exception:
            continue
        for h in hits:
            rid = h.get("ref_id")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            out.append(_hit_to_ref_dict(h, baseline_by_ref))
            if len(out) >= cap:
                return out
    return out[:cap] or None


def _segment_doc_text(text: str, n_segments: int = 5) -> list[str]:
    """Split text into n roughly-equal segments. Used as fallback provision
    texts when no convention list is available."""
    if not text:
        return []
    total = len(text)
    if total <= 500:
        return [text]
    seg_len = max(800, total // n_segments)
    return [text[i:i + seg_len] for i in range(0, total, seg_len) if text[i:i + seg_len].strip()]


def _convention_provision_texts(convention_registry: dict | None) -> list[str]:
    """Treat each convention rule's text as a 'provision' for embedding queries."""
    if not convention_registry:
        return []
    return [c.get("rule", "") for c in convention_registry.get("conventions", [])
            if c.get("rule")]


def _typed_for_agent(payload):
    """structure H3: project an agent output for an INTER-AGENT payload.

    Accepts either a canonical envelope or a bare list of items, and returns the
    same shape with every prose field stripped from every item
    (finding_record.strip_reasoning). Anything else is returned untouched, so a
    caller passing None or a string is unaffected."""
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        out = dict(payload)
        out["items"] = finding_record.strip_reasoning(payload["items"])
        return out
    if isinstance(payload, list):
        return finding_record.strip_reasoning(payload)
    return payload


def _stamp_source_rule_ids(items, convention_registry):
    """Carry the operator's own rule id alongside the registry id.

    The convention parser mints CONV-NNN because that is the only form the
    amendment validator accepts, and keeps the operator's own heading in the
    rule's `category`. Without this, a finding can only ever be attributed to the
    renumbered id, and a reader comparing the review against the operator's own
    rule list has to do the mapping by hand. Items that carry no recognisable rule
    id are returned untouched."""
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            out.append(item)
            continue
        rule = finding_record.resolved_rule_id(item)
        source = finding_record.source_rule_id_for(rule, convention_registry)
        if source and not item.get("source_rule_id"):
            item = dict(item)
            item["source_rule_id"] = source
        out.append(item)
    return out


def _normalize_finding(f: dict) -> dict:
    """Merge cross-agent field-name variants into the canonical reasoning +
    verdict fields the operative summary template expects.

    PRACTICE_AUDITOR uses recommendation/procedure_text; STYLE_GUARDIAN uses
    rationale/suggested_edit; VERIFIER uses finding for the verdict slot.
    """
    out = dict(f)
    out["reasoning"] = (
        # structure H3: `explanation` is the typed record's own human-facing
        # field, so it is the first thing a reader should see when present.
        f.get("explanation")
        or f.get("reasoning")
        or f.get("recommendation")
        or f.get("rationale")
        or f.get("suggested_edit")
        or f.get("procedure_text")
        or "(no reasoning provided)"
    )
    out["verdict"] = (
        f.get("verdict")
        or f.get("deviation")
        or f.get("finding")
        or "?"
    )
    return out


PRODUCTION_AGENTS_PER_DOC = ["PROCESSOR", "SPEECH_ACT_TAGGER", "LEGAL_ANALYST"]
PRODUCTION_AGENTS_CORPUS_LEVEL = ["ARCHIVIST", "INST_FINDER", "CITATION_RESOLVER"]
AUDIT_AGENTS_PER_DOC = ["VERIFIER", "FACT_CHECKER"]
CONVENTION_REVIEW_AGENTS = ["PRACTICE_AUDITOR", "STYLE_GUARDIAN"]

# Job B: an output budget per CALL TYPE, not one blanket number for every call.
# Before this, every local call (agent_wrapper.py's own hardcoded ceiling) was
# capped at 1024 output tokens regardless of what the call was asking for.
# Measured on a real run against the device corpus (output/runs/20260911T123328Z
# __d5728e4b/logs/cost_tracker.jsonl): 9 of 16 calls hit exactly 1024, several
# producing zero usable items (parse_trace showed dozens of "recovery
# candidates" mostly empty_valid_skipped, the shape a response cut mid-item
# leaves behind), and the one preserved raw truncated response lost its sixth
# finding entirely, cut mid-string with no closing quote. The five calls that
# did NOT hit the cap (PRACTICE_AUDITOR's paired judging, the one call type
# answering about exactly one unit and one rule) ranged 202 to 645 tokens, so
# its true ceiling is known with real headroom; every other call type that hit
# the cap has an UNKNOWN true ceiling, which is why those are raised rather
# than left as they were. See docs/fix/WORKLOAD_AND_COST.md's Part One and
# check 216 for the measurement and the fixture proof of the recording.
PAIRED_JUDGING_MAX_TOKENS = 768       # PRACTICE_AUDITOR etc: one unit, one rule,
                                       # a handful of findings at most; the
                                       # largest of 5 real, uncapped calls was
                                       # 645 tokens (see above)
AUDIT_MAX_TOKENS = 2048               # VERIFIER, FACT_CHECKER: an open-ended
                                       # audit of one document's whole draft,
                                       # capped at 1024 with direct evidence of
                                       # a lost finding (VERIFIER's contract
                                       # violation, 13:11:26Z on the run above)
PRODUCTION_MAX_TOKENS = 2048          # ARCHIVIST, INST_FINDER, CITATION_RESOLVER,
                                       # PROCESSOR, SPEECH_ACT_TAGGER, LEGAL_ANALYST
                                       # pass one: 4 of 6 on the run above hit
                                       # 1024 and produced zero items; true
                                       # ceiling unmeasured, so raised rather
                                       # than guessed lower
DEEPEN_MAX_TOKENS = 2048              # D6 pass two, LEGAL_ANALYST: one finding
                                       # deepened into three labelled parts
                                       # (provision, comparison, amendment);
                                       # same unmeasured-true-ceiling reasoning
                                       # as PRODUCTION_MAX_TOKENS, since this
                                       # call also hit 1024 on the run above
WIDE_REVIEW_MAX_TOKENS = 2048         # wide-mode convention review: unchanged
                                       # from its prior value, since wide mode
                                       # was not exercised on the run this
                                       # measurement comes from and lowering it
                                       # without evidence would be a guess


def _convention_review_firing_agents(convention_assignment):
    """night chain W3, the firing gate (docs/api/CONVENTION_ASSIGNMENT_DESIGN.md).
    Which of CONVENTION_REVIEW_AGENTS actually has work to do this document,
    given the BOOT-computed assignment.

    An agent fires if EITHER is true: it has at least one rule genuinely
    assigned to it (assignment["by_agent"][name] non-empty), OR at least one
    loaded rule is untagged (status "untagged" in by_rule), since an
    untagged rule keeps today's default routing to every convention-review
    agent unchanged, per the operator's own instruction that tagging a
    corpus is what changes call behavior, never the mere existence of the
    assignment mechanism. Only when both are false, this agent has zero
    assigned rules and zero untagged rules exist anywhere in the loaded
    set, does it have nothing to do.

    With convention_assignment None (a caller that predates W3, mainly the
    gate's own older fixtures), every agent in CONVENTION_REVIEW_AGENTS
    fires, identical to every commit before this one.

    night W8: the rule itself lives in convention_assignment
    .firing_convention_review_agents, so the server's convention-assignment
    route (and through it the console's "did not run" list) reads the gate's
    own answer rather than a second computation of it. This function keeps
    its name and its behavior (checks 157 and 199) and delegates. The local
    import is deliberate: the parameter shadows the module name here."""
    import convention_assignment as _ca
    return _ca.firing_convention_review_agents(convention_assignment, CONVENTION_REVIEW_AGENTS)

# local RUNDAY: the local-profile checkpoint ids are operator-selectable via
# config/local_models.json (active_producer / active_auditor) so the original
# full-precision checkpoints stay available by editing one file. The literals below are
# the FALLBACK used when that file is absent or unreadable, so deleting it restores the
# pre-existing behaviour byte for byte. _resolve_local_models() rewrites the ids at
# import time; the backend column (which decides the LAW-III family split) is never
# touched by config, only the model id is.
_LOCAL_PROFILE = {
    "PROCESSOR":               ("local_producer", "Qwen/Qwen2.5-7B-Instruct"),
    "LEGAL_ANALYST":           ("local_producer", "Qwen/Qwen2.5-7B-Instruct"),
    "STYLE_GUARDIAN":          ("local_producer", "Qwen/Qwen2.5-7B-Instruct"),
    "ARCHIVIST":               ("local_producer", "Qwen/Qwen2.5-7B-Instruct"),
    "INST_FINDER":             ("local_producer", "Qwen/Qwen2.5-7B-Instruct"),
    "CITATION_RESOLVER":       ("local_producer", "Qwen/Qwen2.5-7B-Instruct"),
    "SPEECH_ACT_TAGGER":       ("local_producer", "Qwen/Qwen2.5-7B-Instruct"),
    "AMENDMENT_DRAFTER":       ("local_producer", "Qwen/Qwen2.5-7B-Instruct"),
    "EDITOR_CLERK":            ("local_producer", "Qwen/Qwen2.5-7B-Instruct"),
    "EDITOR_HEAD_OF_UNIT":     ("local_producer", "Qwen/Qwen2.5-7B-Instruct"),
    "EDITOR_HEAD_OF_SECTION":  ("local_producer", "Qwen/Qwen2.5-7B-Instruct"),
    "VERIFIER":                ("local_auditor", "microsoft/Phi-3.5-mini-instruct"),
    "FACT_CHECKER":            ("local_auditor", "microsoft/Phi-3.5-mini-instruct"),
    "PRACTICE_AUDITOR":        ("local_auditor", "microsoft/Phi-3.5-mini-instruct"),
    "EDITOR_HEAD_OF_DEPARTMENT": ("local_auditor", "microsoft/Phi-3.5-mini-instruct"),
    "EDITOR_DEPUTY_DG":        ("local_auditor", "microsoft/Phi-3.5-mini-instruct"),
    "EDITOR_DG":               ("local_auditor", "microsoft/Phi-3.5-mini-instruct"),
}


def _resolve_local_models(profile: dict, project_root: Path) -> dict:
    """Apply config/local_models.json's active_producer/active_auditor over the
    _LOCAL_PROFILE fallback, by BACKEND (local_producer -> producer id,
    local_auditor -> auditor id). Returns a new dict; never mutates the argument.

    Degrades to the fallback silently-but-loudly: a missing file, unreadable JSON, or a
    missing/blank key leaves that role's original id in place and logs which id is in
    force, so a config typo can never quietly load a model the operator did not choose.
    The backend column is NEVER read from config, so LAW-III's producer/auditor family
    split cannot be reconfigured away (gate check 87 keeps its meaning)."""
    cfg = {}
    path = project_root / "config" / "local_models.json"
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    producer = (cfg.get("active_producer") or "").strip()
    auditor = (cfg.get("active_auditor") or "").strip()
    out = {}
    for agent, (backend, model) in profile.items():
        if backend == "local_producer" and producer:
            out[agent] = (backend, producer)
        elif backend == "local_auditor" and auditor:
            out[agent] = (backend, auditor)
        else:
            out[agent] = (backend, model)
    return out


_LOCAL_PROFILE = _resolve_local_models(_LOCAL_PROFILE, ROOT)

# Structured progress (consumed by chat.py and server.py). Emitted to stderr ALONGSIDE
# the existing human log lines, never replacing them. One parseable line per event:
#   [progress] phase=N/TOTAL doc=M/DOCS agent=NAME status=running|done
#   [progress] event=start docs=N status=running
#   [progress] event=complete docs=N amendments=X cost=Y.YY status=done
#   [progress] event=block|warning phase=N/TOTAL note=... status=warning
# The phase numbers are the pipeline's own labels (1, 3, 5, 5.5, 6, 6.5, 7, 9) against a
# nominal total of 9; consumers parse the leading number for a progress fraction.
TOTAL_PHASES = 9

# productization STEP 4: structured JSON-lines logging (scripts/shimmer_logging.py),
# stderr, separate from the [progress] contract above (which stays byte-identical,
# W5). Module-level so every phase-timing call site below shares one logger.
_LOG = get_logger("shimmer.pipeline")


def _run_id_of(orch) -> str:
    """The run id to stamp on a log event from inside a phase function, or ""
    when no run context is attached (a stubbed orchestrator in a gate check).
    main() has run_ctx in hand directly and does not need this."""
    return getattr(getattr(orch, "run_context", None), "run_id", "") or ""


def _emit_progress(*, phase=None, doc=None, docs=None, agent=None, status="running",
                   event=None, **fields):
    parts = ["[progress]"]
    if event is not None:
        parts.append(f"event={event}")
    if phase is not None:
        parts.append(f"phase={phase}/{TOTAL_PHASES}")
    if doc is not None and docs is not None:
        parts.append(f"doc={doc}/{docs}")
    elif docs is not None:
        parts.append(f"docs={docs}")
    if agent:
        parts.append(f"agent={agent}")
    for k, v in fields.items():
        parts.append(f"{k}={v}")
    parts.append(f"status={status}")
    print(" ".join(parts), file=sys.stderr, flush=True)


# ---------- local progress display (ADDITIVE ONLY) -------------------------------------------
# A second, entirely separate event family for local-profile runs, prefixed [local-progress]
# (never [progress]). Confirmed non-colliding by reading both existing parsers directly:
# server.py::_progress_string and chat.py::parse_progress both gate on
# `line.strip().startswith("[progress]")`, an exact literal-prefix match, and
# "[local-progress] ...".startswith("[progress]") is False. Neither parser is touched by
# anything below; every existing [progress] call site and its exact text is unchanged.
#
# Scope, stated plainly rather than silently: this covers every agent call that flows
# through _run_one (corpus-level and per-doc production, the D6 two-pass split, audit,
# convention review, AMENDMENT_DRAFTER). It does NOT cover the editorial review board
# (phase 6.5, _dispatch_rank calls wrapper.run_task directly, not through _run_one) or
# REDACTOR (a separate call path in sensitivity_layer/redaction_stage.py). Both are
# real, out of scope for this version, not silently missed.
_LOCAL_PROGRESS = {"completed": 0, "expected": 0, "peak_ram_gb": 0.0, "peak_vram_mb": 0.0}
_LOCAL_PROGRESS_LOCK = threading.Lock()
_LOCAL_PROGRESS_STOP = threading.Event()


def _emit_local_progress(*, event, **fields):
    parts = ["[local-progress]", f"event={event}"]
    for k, v in fields.items():
        parts.append(f"{k}={v}")
    print(" ".join(parts), file=sys.stderr, flush=True)


def _local_progress_reset(expected: int) -> None:
    """Called once, local profile only, as soon as op_docs is known (before phase 3-4
    starts). `expected` is the KNOWN-MINIMUM total call count (see _local_progress_baseline
    below); work discovered later (a D6 pass-two call per finding) grows it via
    _local_progress_bump_expected rather than being guessed up front."""
    with _LOCAL_PROGRESS_LOCK:
        _LOCAL_PROGRESS["completed"] = 0
        _LOCAL_PROGRESS["expected"] = expected
        _LOCAL_PROGRESS["peak_ram_gb"] = 0.0
        _LOCAL_PROGRESS["peak_vram_mb"] = 0.0
    _LOCAL_PROGRESS_STOP.clear()


def _local_progress_baseline(num_op_docs: int) -> int:
    """The known-minimum agent-call count for the calls _run_one covers (see the scope
    note above): corpus-level (always 3), per-doc production/audit/convention-review
    (always run once per op doc), AMENDMENT_DRAFTER (usually once per doc; the rare
    bus-reuse skip is not subtracted, an accepted small overcount for a progress display,
    not a correctness-critical count)."""
    return (len(PRODUCTION_AGENTS_CORPUS_LEVEL)
            + len(PRODUCTION_AGENTS_PER_DOC) * num_op_docs
            + len(AUDIT_AGENTS_PER_DOC) * num_op_docs
            + len(CONVENTION_REVIEW_AGENTS) * num_op_docs
            + num_op_docs)  # AMENDMENT_DRAFTER


def _local_progress_bump_expected(n: int) -> None:
    """Call when new work is DISCOVERED to exist (a D6 pass-two call per LEGAL_ANALYST
    finding): grows the denominator, rather than guessing a ceiling up front that would
    overcount every run where the discovered work does not happen."""
    if n <= 0:
        return
    with _LOCAL_PROGRESS_LOCK:
        _LOCAL_PROGRESS["expected"] += n


def _local_contract_outcome(r: dict) -> tuple[str, int]:
    """Classify a run_task result for display. Reads ONLY fields run_task already
    returns (agent_wrapper.py, D4b's item_count): never re-parses raw_text, never
    re-derives anything the wrapper did not already decide. Four outcomes, not the three
    named in the request ("violated", "held with zero items", "held with N items"):
    backend_error is a real, distinct return shape from run_task (a dispatch/model-load
    failure, result.ok=False with no "contract_violation" marker, agent_wrapper.py's
    `if not result.ok:` branch) and labelling it "violated" would misreport what actually
    happened, so it gets its own name instead of being folded silently into one of the
    three."""
    if r.get("error") == "contract_violation":
        return "violated", 0
    if not r.get("ok"):
        return "backend_error", 0
    n = r.get("item_count")
    if n is None:
        n = len(((r.get("parsed") or {}).get("items")) or [])
    return ("held_empty" if n == 0 else "held_n"), n


def _local_progress_memory_sampler(stop_event: threading.Event) -> None:
    """Background daemon thread, local profile only. Samples system RAM every 5s via
    psutil (no CUDA touch, ever). Reads VRAM ONLY if torch is already present in
    sys.modules -- this NEVER forces the torch import itself, so it never changes WHEN or
    WHETHER CUDA gets initialised; it only reads a number that is already there once the
    first local model call has imported torch on its own. Emits a running peak so a climb
    is visible while it is happening, not only discoverable after a kill."""
    import psutil
    while not stop_event.is_set():
        vm = psutil.virtual_memory()
        used_gb = (vm.total - vm.available) / 1024**3
        vram_mb = None
        torch_mod = sys.modules.get("torch")
        if torch_mod is not None:
            try:
                if torch_mod.cuda.is_available():
                    vram_mb = torch_mod.cuda.memory_allocated(0) / 1024**2
            except Exception:
                vram_mb = None
        with _LOCAL_PROGRESS_LOCK:
            _LOCAL_PROGRESS["peak_ram_gb"] = max(_LOCAL_PROGRESS["peak_ram_gb"], used_gb)
            if vram_mb is not None:
                _LOCAL_PROGRESS["peak_vram_mb"] = max(_LOCAL_PROGRESS["peak_vram_mb"], vram_mb)
            snap = dict(_LOCAL_PROGRESS)
        _emit_local_progress(event="memory", peak_ram_gb=f"{snap['peak_ram_gb']:.2f}",
                             peak_vram_mb=f"{snap['peak_vram_mb']:.1f}",
                             completed=f"{snap['completed']}/{snap['expected']}")
        stop_event.wait(5.0)


# ---------- corpus loading -----------------------------------------------------------------

def _load_corpus(input_dir: Path) -> list[dict]:
    docs = []
    if not input_dir.exists():
        return docs
    # Count stems first so collisions can be disambiguated. The doc id keys every
    # deliverable (output/runs/<run>/deliverables/<id>__*.md); two files sharing a
    # stem (e.g. policy.pdf and policy.docx) would clobber each other if both
    # keyed "policy". Collision-safe rule (Part XXVII §A): keep the bare stem when
    # unique; qualify only on collision as "<stem>__<ext>".
    stem_counts: dict[str, int] = {}
    loaded = []  # (path, name, text)
    for p in sorted(input_dir.iterdir()):
        if not p.is_file():
            continue
        # `_`-prefixed files are metadata (sidecars, manifests), never corpus
        # documents: skip silently before the supported-type check so they are
        # neither loaded nor warned as "unsupported".
        if p.name.startswith("_"):
            continue
        # Shared format family (.pdf/.docx/.html/.htm/.txt/.md/.rst/.log/.json).
        # Unsupported types warn (never silently skipped).
        if not text_extract.is_corpus_file(p):
            text_extract.warn_unsupported(p, where=str(input_dir.name))
            continue
        text = text_extract.extract_text(p)
        if not text.strip():
            continue
        loaded.append((p, p.name, text))
        stem_counts[p.stem] = stem_counts.get(p.stem, 0) + 1
    for p, name, text in loaded:
        doc_id = p.stem if stem_counts.get(p.stem, 0) <= 1 else f"{p.stem}__{p.suffix.lstrip('.').lower()}"
        docs.append({"id": doc_id, "name": name, "text": text,
                     "char_count": len(text), "path": str(p)})
    return docs


def _prewarm_qwen(project_root):
    """BP-6 pre-warm: populate the shared resident Qwen model cache in the background
    at BOOT so the redaction phase (phase 9) finds the model already on the GPU,
    instead of paying the cold load (~90s) on the first redaction call. Best-effort:
    any failure is swallowed here (the real redaction call surfaces a genuine load
    error). Reads the REDACTOR backend/model from the agent registry; warms ONLY a
    local qwen backend."""
    try:
        reg = json.loads((Path(project_root) / "config" / "agent_registry.json")
                         .read_text(encoding="utf-8"))
        red = (reg.get("agents") or {}).get("REDACTOR") or {}
        if red.get("backend") != "qwen_local" or not red.get("model"):
            return
        import agent_wrapper
        agent_wrapper._load_qwen(red["model"])
    except Exception as e:
        print(f"[qwen] pre-warm skipped (non-fatal): {type(e).__name__}: {e}",
              file=sys.stderr, flush=True)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n... [truncated for token budget] ...\n" + text[-half:]


# ---------- cutoff + operational population --------------------------------------------------

def _resolve_review_scope(project_root: Path) -> dict:
    path = project_root / "config" / "review_scope.json"
    if not path.exists():
        return {"cutoff_type": "all"}
    try: return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError: return {"cutoff_type": "all"}


# ---------- draft mode (phase 0) ----------------------------------------------

DRAFT_SYSTEM_PROMPT = (
    "Draft a formal legal memo answering the question below. Cite specific provisions "
    "from the reference corpus using the REF-* identifiers exactly as they appear in the "
    "corpus. Structure the memo with numbered sections. Use a formal legal register. Do "
    "not invent citations: cite only REF-* identifiers that appear in the reference corpus "
    "provided here. If the corpus does not support a point, say so rather than fabricating "
    "a citation."
)


def _draft_generate_with_evidence(drafter, stable, dynamic, *, passages, run_ctx):
    """The draft memo's one model call, with its call evidence recorded. This call
    bypasses AgentWrapper.run_task (the memo is free text, not an envelope), so
    run_task's own recording never sees it; the same record is written here:
    agent, backend, model, run, a fresh call id (also on the cost row through
    _cost_call_id), the REF-* ids of the passages the prompt carried, the prompt
    length. No unit, rule or document map exists for this call. Recording failure
    is logged and never takes the call down. Returns the memo text, or "" on a
    failed call (as before)."""
    import uuid as _uuid
    import call_evidence as _ce
    call_id = _uuid.uuid4().hex
    try:
        _ce.record(run_ctx, _ce.extract(
            {"task": "draft_memo"}, call_id=call_id,
            run_id=getattr(run_ctx, "run_id", "") or "", phase="0", doc_id="",
            agent=drafter.name, backend=drafter.backend, model=drafter.model or "",
            reference_index_excerpt=[{"ref_id": p.get("ref_id") or p.get("ref")}
                                     for p in (passages or []) if isinstance(p, dict)],
            prompt_chars=len(stable) + len(dynamic)))
    except Exception as e:
        log_event(_LOG, f"call_evidence_write_error error_type={type(e).__name__}",
                  level="warning", agent=drafter.name,
                  run_id=getattr(run_ctx, "run_id", "") or "")
    drafter._cost_call_id = call_id
    try:
        # CallResult carries the response text in .raw_text (there is no .text).
        r = drafter.call_claude(stable, dynamic, max_tokens=4096)
    finally:
        drafter._cost_call_id = ""
    return r.raw_text if getattr(r, "ok", False) else ""


def build_draft_prompt(question: str, passages: list) -> tuple:
    """Build the (stable_prefix, dynamic_suffix) generation prompt from the retrieved
    grounding passages and the operator's question. Pure and testable: no model call,
    no I/O. Each passage contributes its REF-* identifier and text so the model can
    cite it by reference."""
    lines = ["## Reference corpus (cite these REF-* identifiers)"]
    if passages:
        for p in passages:
            ref = p.get("ref_id") or p.get("ref") or "(unlabeled)"
            text = (p.get("text") or "").strip()
            lines.append(f"[{ref}] {text}")
    else:
        lines.append("(no grounding passages retrieved; cite nothing you cannot support)")
    stable = DRAFT_SYSTEM_PROMPT + "\n\n" + "\n\n".join(lines)
    dynamic = f"## Question\n{question.strip()}\n\n## Task\nWrite the memo now."
    return stable, dynamic


# Words dropped when slugging a draft question into a filename / run-folder name.
_SLUG_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "of", "on", "in", "for", "to",
    "with", "and", "or", "whether", "what", "how", "do", "does", "did", "me", "my",
    "about", "regarding", "re", "please", "draft", "write", "prepare", "compose", "memo",
    "brief", "note", "question", "against", "supporting", "case", "cases",
}


def _slug_from_question(question: str, max_words: int = 6) -> str:
    """The first few meaningful words of the question, lowercased and underscored, as a
    filesystem-safe slug (for the draft memo name and the run folder name)."""
    words = re.findall(r"[a-z0-9]+", (question or "").lower())
    meaningful = [w for w in words if w not in _SLUG_STOPWORDS]
    chosen = (meaningful or words)[:max_words]
    return "_".join(chosen)[:60] or "draft"


DEFAULT_RUN_OBJECTIVES = (
    "Review each operational document against the convention registry. "
    "Produce all deliverables specified in Part XVIII Sections C and D. "
    "Every finding must cite convention rules (CONV-*) and source passages (REF-*)."
)


def _question_suffix(task, question):
    """R6: a review run's optional framing question, as the line appended to the run
    objectives. Empty for draft (the question IS the brief there) and for no question."""
    q = (question or "").strip()
    return ("\nOperator question: " + q) if task == "review" and q else ""


def _effective_run_objectives(run_objectives, task, question):
    """The run objectives every agent call receives: the operator's own, or the
    default sentence, plus the framing question for a review run. The question is
    never parsed; it rides the RUN_OBJECTIVES prompt section, which bus_reader caps
    at 200 tokens, so an over-long text is warned about rather than silently cut."""
    text = (run_objectives or DEFAULT_RUN_OBJECTIVES) + _question_suffix(task, question)
    try:
        import bus_reader
        cap_chars = 200 * bus_reader.CHARS_PER_TOKEN
    except Exception:
        cap_chars = 800
    if len(text) > cap_chars:
        print(f"[pipeline] WARNING: run objectives are {len(text)} characters; the "
              f"RUN_OBJECTIVES prompt section is capped at 200 tokens (about {cap_chars} "
              f"characters) and the tail will be cut", file=sys.stderr, flush=True)
    return text


def _review_slug(op_docs: list) -> str:
    """The run-folder slug for a review run: document count plus type."""
    return f"{len(op_docs)}doc_review"


def _draft_memo_filename(question: str) -> str:
    """The generated draft memo's filename. Carries a stable `draft_memo_` prefix so it is
    matched by the `.gitignore` rule (`input/context/draft_memo_*`) and is never accidentally
    committed if a crashed run leaves it behind; the slug keeps it readable. Its stem becomes
    the doc id, so the review deliverables share the same name."""
    return f"draft_memo_{_slug_from_question(question)}.md"


def run_draft_phase0(project_root: Path, question: str, *, retrieve, generate,
                     now_iso: str) -> "Path | None":
    """Draft mode phase 0: retrieve grounding for the question, generate a formal legal
    memo via the strong model, write it to input/context/, and mark it as the review
    target (source=system_draft) so the resolution chain promotes it. Returns the memo
    path, or None if generation produced nothing.

    `retrieve(question) -> list[passage]` and `generate(stable, dynamic) -> str` are
    injected, so this is testable without an embedding store or a paid model call."""
    passages = retrieve(question) or []
    stable, dynamic = build_draft_prompt(question, passages)
    memo_text = generate(stable, dynamic) or ""
    if not memo_text.strip():
        print("[pipeline] draft generation returned no text; aborting the draft.",
              file=sys.stderr, flush=True)
        return None
    context_dir = project_root / "input" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    memo_path = context_dir / _draft_memo_filename(question)
    memo_path.write_text(memo_text, encoding="utf-8")
    # Tier 1 (system as operator): the generated memo is the document under review.
    role_resolution.write_manifest(context_dir, [memo_path.name], "system_draft",
                                   now_iso=now_iso)
    words = len(memo_text.split())
    cited = len(set(re.findall(r"REF-[A-Za-z0-9-]+", memo_text)))
    print(f"[pipeline] Draft memo generated ({words} words, {cited} grounding passages "
          f"cited). Proceeding to review.", file=sys.stderr, flush=True)
    return memo_path


def _populate_operational(project_root: Path, search_router: SearchRouter,
                          *, sensitive: bool = False,
                          mode: str = "standalone",
                          infer_roles: bool = False) -> tuple[list[dict], list[dict]]:
    """Returns (context_records, operational_records). Each record:
       {filename, date, date_source, title, abs_path}.

    `sensitive` (INFRA-041 P2, chokepoint 4) suppresses the date cascade's web last-resort:
    under sensitive mode no document title is sent to the web (the cascade stays local)."""
    context_dir = project_root / "input" / "context"
    operational_dir = project_root / "input" / "operational"
    operational_dir.mkdir(parents=True, exist_ok=True)
    # Clear operational/ before repopulating per spec. Skip the tracked .gitkeep
    # placeholder so a run never deletes it (it must persist for fresh-clone dir structure).
    for f in operational_dir.glob("*"):
        if f.is_file() and f.name != ".gitkeep": f.unlink()
    # Same format family as _load_corpus. Unsupported files are warned there
    # (this loader also scans context_dir); here we just filter to candidates.
    candidate_files = sorted(p for p in context_dir.iterdir()
                             if p.is_file() and text_extract.is_corpus_file(p))
    # M2: the M1 promotion exclusion is integration behavior, run ONLY when the
    # operator declares an integrated (externally-fed) run. Files marked
    # role=context_grounding in the ingestion sidecar are retrieved precedent, never
    # the document under review, so they must never be promoted to operational. In
    # standalone mode the corpus_ingest import never happens and base Shimmer
    # behavior is preserved exactly. Mismatch between the declared mode and the
    # sidecar's presence is a WARNING only (the run still proceeds).
    sidecar_present = (context_dir / "_corpus_ingest.json").is_file()
    if mode == "integrated":
        from corpus_ingest.grounding_files import context_grounding_filenames
        grounding = context_grounding_filenames(context_dir)
        if grounding:
            candidate_files = [p for p in candidate_files if p.name not in grounding]
            print(f"[pipeline] excluding {len(grounding)} context-grounding file(s) "
                  "from operational promotion", file=sys.stderr, flush=True)
        if not sidecar_present:
            print("[pipeline] WARNING: mode is integrated but no sidecar found in "
                  "input/context/; promotion exclusion has nothing to act on.",
                  file=sys.stderr, flush=True)
    elif sidecar_present:
        print("[pipeline] WARNING: sidecar found but mode is standalone; ingested "
              "grounding files will not be excluded from operational promotion. "
              "Use --mode integrated if this is an ingested-corpus run.",
              file=sys.stderr, flush=True)
    if not candidate_files:
        return [], []
    dated = resolve_dates(candidate_files, search_router=search_router, sensitive=sensitive)
    for record, path in zip(dated, candidate_files):
        record["abs_path"] = str(path)
    write_dates(project_root, dated)

    # 4-tier document role resolution (replaces the date-cutoff-only split). The
    # chain refreshes/writes _review_targets.json: tier 1 = a pre-existing operator
    # manifest, tier 2 = a convention `review_targets:` field, tier 3 = sidecar +
    # date cutoff (writes nothing), tier 4 = a guarded stub. We then read the
    # manifest: named targets are forced operational, named grounding forced context,
    # and every file the manifest did NOT resolve falls to the date cutoff exactly as
    # before. No manifest = the forced sets are empty = the original behavior.
    role_resolution.resolve_review_roles(project_root, infer_roles=infer_roles)
    manifest = role_resolution.read_manifest(context_dir)
    # R6: an operator-declared EARLIER VERSION is forced grounding too, never promoted.
    forced_targets, forced_grounding = _forced_roles(manifest)
    scope = _resolve_review_scope(project_root)
    cutoff_op_names = {r["filename"] for r in apply_cutoff(dated, scope)}

    def _is_operational(rec: dict) -> bool:
        fn = rec["filename"]
        if fn in forced_targets:
            return True
        if fn in forced_grounding:
            return False
        return fn in cutoff_op_names

    operational = [r for r in dated if _is_operational(r)]
    operational_filenames = {r["filename"] for r in operational}
    context_only = [r for r in dated if r["filename"] not in operational_filenames]
    if forced_targets or forced_grounding:
        print(f"[pipeline] role resolution: {len(forced_targets)} forced under review, "
              f"{len(forced_grounding)} forced grounding; the rest by date cutoff",
              file=sys.stderr, flush=True)
    # Copy operational files into input/operational/ and run the content
    # validator on each. The validator is language-agnostic: it derives
    # keywords from the document's own first page (Zipfian filter) and
    # confirms at least 1 of them appears in the filename slug. Failures
    # do NOT skip the document; they record a content_validated flag in
    # document_dates.json so downstream agents and the operator know.
    for record in operational:
        src = Path(record["abs_path"])
        dst = operational_dir / src.name
        shutil.copy2(src, dst)
        record["abs_path"] = str(dst)
        try:
            valid, excerpt, matched = validate_corpus_entry(dst)
        except Exception as e:
            valid, excerpt, matched = False, "", []
            record["validation_error"] = f"{type(e).__name__}: {e}"
        record["content_validated"] = bool(valid)
        record["validation_note"] = (
            f"matched={matched}; first_page_excerpt={excerpt[:200]!r}"
            if matched or excerpt
            else "no first-page text extracted"
        )
        if not valid:
            print(
                f"[pipeline] WARN: {dst.name} may be misclassified: first page does not "
                f"match expected content ({len(matched)} keywords matched)",
                file=sys.stderr, flush=True,
            )
    # Rewrite document_dates.json with validation fields populated (operational
    # entries replace the originals; context-only entries pass through unchanged).
    by_filename = {r["filename"]: r for r in operational}
    merged = [by_filename.get(r["filename"], r) for r in dated]
    write_dates(project_root, merged)
    return context_only, operational


# ---------- agent helpers ------------------------------------------------------------------

def _build_wrapper(name: str, orch: TopOrchestrator, keys: dict) -> AgentWrapper:
    return AgentWrapper(name=name, constitution=orch.constitution, bus=orch.bus,
                        registry=orch.registry, contracts=orch.contracts,
                        keys=keys, cost_tracker=orch.cost_tracker,
                        # productization STEP 4: thread the current run's RunContext so a
                        # contract-violation dump lands under <run>/audit/contract_violations/
                        # (BP-16) instead of falling back to the shared output/audit/
                        # contract_violations/ (agent_wrapper.py::_persist_contract_violation_
                        # raw_text's own fallback, unchanged, still fires if orch.run_context
                        # is ever None).
                        run_context=orch.run_context,
                        # LAW-IV outbound masking (INFRA-041 P2, chokepoint 1): inject the
                        # prompt masker the pipeline built from the operator rules. Defaults to
                        # None (no masking) until the injector is set, so wrappers built before
                        # the injector exists, and every non-sensitive run, are unchanged.
                        outbound_masker=getattr(orch, "outbound_masker", None),
                        # productization STEP 4: same getattr-with-default pattern as
                        # outbound_masker, so a wrapper built before orch.sensitive is set
                        # (or in a gate check that never sets it) safely defaults to False
                        # (contract violations kept as text, prior behavior).
                        sensitive=getattr(orch, "sensitive", False))


def apply_backend_profile(named_profile):
    """Resolve the backend profile and MAKE THE ENVIRONMENT AGREE WITH IT.

    --backend-profile used only to be read INTO args, while six behaviours were
    keyed to the SHIMMER_BACKEND_PROFILE environment variable instead: agent
    serialisation, the local document clip and the local progress display (all
    via _is_local_profile), the role anchor (agent_wrapper) and cpu embedding
    (embedding_store). A run started with the flag alone therefore loaded local
    models and then ran their agents CONCURRENTLY, which is the one thing the
    local profile exists to prevent. It cost a 47 minute run at H7, killed in
    phase 3 of 9 with 11922 MB of VRAM and not one [local-progress] line.

    CLAUDE.md already documents the intended behaviour: "Also settable via
    SHIMMER_BACKEND_PROFILE env var; the CLI flag takes precedence." Now it does.
    With no flag the environment still decides, and with neither it is cloud,
    exactly as before."""
    profile = named_profile or os.environ.get("SHIMMER_BACKEND_PROFILE", "cloud")
    os.environ["SHIMMER_BACKEND_PROFILE"] = profile
    return profile


def resolve_review_mode(review_mode, backend_profile):
    """W5 rollback lever: which review mode a run uses when the operator named none.

    paired becomes the default only where it has been measured. The cloud profile
    keeps wide until the operator's paid baseline says otherwise, and an explicit
    --review-mode always wins over both. Split out of main so the rule itself can
    be driven by a check rather than inferred from a whole run."""
    if review_mode:
        return review_mode
    return "paired" if backend_profile == "local" else "wide"


def _is_local_profile():
    return os.environ.get("SHIMMER_BACKEND_PROFILE") == "local"


# local D3. _truncate discards the MIDDLE of the text, so a binding clip removes operative
# text from the centre of a document rather than its tail. The D2 dump implicated this for
# the auditing agents: against the real corpus (5827 to 7607 chars) the 3500-char
# FACT_CHECKER clip removed up to 4107 chars, 62% of a document, and the 5500-char VERIFIER
# clip removed up to 2107. Under the LOCAL profile the ceiling is raised so a corpus
# document reaches the agent whole. Headroom is not the constraint: Qwen2.5-7B-Instruct has
# max_position_embeddings=32768 and the measured producer prompt was 8769 tokens, while the
# KV cache costs 56 KiB/token, so the added text costs well under 0.1 GiB.
LOCAL_DOC_CLIP_CHARS = 12000


def _truncate_doc(text: str, max_chars: int) -> str:
    """Clip for the DOCUMENT UNDER REVIEW. On the local profile the ceiling is raised to
    LOCAL_DOC_CLIP_CHARS; the cloud path keeps its existing limits exactly (W5). The
    corpus-level digest deliberately does NOT use this helper: that clip is applied per
    document across the whole corpus, so raising it would multiply that one prompt."""
    if _is_local_profile():
        max_chars = max(max_chars, LOCAL_DOC_CLIP_CHARS)
    return _truncate(text, max_chars)


async def _gather_or_serial(tasks):
    """Run tasks concurrently on cloud, sequentially on local (VRAM safety)."""
    if _is_local_profile():
        return [await t for t in tasks]
    return await asyncio.gather(*tasks)


async def _run_one(wrapper, work_payload, run_objectives, channel="main", max_tokens=2048,
                   convention_registry=None, reference_index_excerpt=None, _progress=None):
    # _progress, when set, is (phase, doc, docs, agent): emit a running/done pair around
    # the agent call so chat.py and server.py can show per-doc-per-agent progress.
    # productization STEP 4: this is also the cost-dimension signal (phase, doc_id),
    # threaded straight into run_task -> CostEvent.phase / .doc_id, since _progress
    # is the one place this call already carries both. `doc` here is whatever the
    # caller passed as the per-doc identifier (a filename or doc id depending on
    # phase); with no _progress (corpus-level calls), phase/doc_id stay "".
    phase_name, doc_id = "", ""
    if _progress is not None:
        ph, dc, dcs, ag = _progress
        phase_name, doc_id = str(ph or ""), str(dc or "")
        _emit_progress(phase=ph, doc=dc, docs=dcs, agent=ag, status="running")
    # local progress display (additive, W5: this block never runs off the local profile,
    # so the cloud path's behavior and timing are byte-identical to before it existed).
    local = _is_local_profile()
    _t_agent0 = time.monotonic()
    if local:
        resident = sorted(agent_wrapper._QWEN_MODELS.keys())  # best-effort read, no lock:
        # a diagnostic display tolerates a momentarily stale snapshot; nothing here gates
        # real control flow, so this never needs _QWEN_LOAD_LOCK.
        swap = bool(resident) and bool(wrapper.model) and wrapper.model not in resident
        _emit_local_progress(event="agent_start", agent=wrapper.name,
                             phase=(phase_name or "-"), model=(wrapper.model or "-"),
                             resident_before=("|".join(resident) if resident else "-"),
                             swap=("yes" if swap else "no"))
    r = await asyncio.to_thread(
        wrapper.run_task, work_payload=work_payload, run_objectives=run_objectives,
        channel=channel, max_tokens=max_tokens,
        convention_registry=convention_registry,
        reference_index_excerpt=reference_index_excerpt,
        phase=phase_name, doc_id=doc_id,
    )
    if _progress is not None:
        ph, dc, dcs, ag = _progress
        _emit_progress(phase=ph, doc=dc, docs=dcs, agent=ag, status="done")
    if local:
        elapsed = time.monotonic() - _t_agent0
        outcome, items = _local_contract_outcome(r)
        with _LOCAL_PROGRESS_LOCK:
            _LOCAL_PROGRESS["completed"] += 1
            snap_completed = _LOCAL_PROGRESS["completed"]
            snap_expected = _LOCAL_PROGRESS["expected"]
        _emit_local_progress(event="agent_done", agent=wrapper.name,
                             phase=(phase_name or "-"), elapsed_s=f"{elapsed:.1f}",
                             outcome=outcome, items=items,
                             completed=f"{snap_completed}/{snap_expected}")
    return r


async def _gather_docs(op_docs, process_doc, max_concurrent_docs):
    """BP-5: run `process_doc(doc)` concurrently across operational documents,
    bounded by a semaphore (default 4 to stay under a single-key Claude rate limit).
    Documents are independent within a per-doc phase, so this collapses the phase's
    wall-clock from sum-of-docs toward slowest-doc. Each `process_doc` is an async
    function that returns THIS doc's result (a list of records, or a (key, value)
    pair); the caller assembles the returned values. Results are collected via
    return values, never shared-list mutation, so order is deterministic by op_docs."""
    sem = asyncio.Semaphore(max(1, int(max_concurrent_docs or 1)))

    async def _guarded(doc):
        async with sem:
            return await process_doc(doc)

    return await asyncio.gather(*[_guarded(d) for d in op_docs])


async def _deepen_legal_analyst_findings_local(wrapper, findings, doc, embed_store,
                                               run_objectives):
    """D6, local profile only: pass two of the two-pass split. Pass one (the existing
    single call) asks LEGAL_ANALYST to find an issue, analyse it, and justify it, all at
    once -- too wide a question for a 7B (D6's own diagnosis). This asks a second,
    narrower question per finding, one call each: the specific provision text, the
    comparison against retrieved material, and a concrete proposed amendment. Same
    agent, same envelope contract (no new field: all three land inside the existing
    `reasoning` field), one finding per call.

    ALWAYS serial (a plain for-loop with await, never asyncio.gather), regardless of
    caller: this is the "at most one agent call in flight at a time" guarantee for pass
    two specifically, on top of _gather_or_serial's existing per-doc serialization and
    max_concurrent_docs=1's existing per-document serialization. Wall clock is free
    locally (D6), so there is no reason to relax this.

    Item continuity (INFRA-037): the model is not trusted to reproduce a finding's
    item_id verbatim (make_envelope stamps a fresh one, index-derived, per call --
    small models are not reliable at echoing ids). The code stitches instead: pass
    two's returned item is forced to the ORIGINAL finding's item_id with revision+1,
    so _items_for's current_items reduction shows only the deepened version, never
    both. This mutates the in-process result dict only; the AGENT_OUTPUT bus message
    already posted by run_task keeps the freshly-stamped id (a known, stated audit-
    trail gap, not a functional one: deliverables read from `results`, never re-read
    the bus)."""
    _local_progress_bump_expected(len(findings))  # this many extra _run_one calls now known
    out = []
    for finding in findings:
        query = " ".join(str(finding.get(k, "")) for k in ("claim_id", "reasoning")).strip()
        hits = embedding_store.query_store(embed_store, query, n=5) if (embed_store and query) else []
        refs_excerpt = [_hit_to_ref_dict(h, {}) for h in hits] or None
        payload = {
            "task": "deepen_finding",
            "document_id": doc["id"], "document_name": doc["name"],
            "finding": {k: finding.get(k) for k in
                       ("ref", "kind", "claim_id", "verdict", "reasoning", "confidence")
                       if finding.get(k) is not None},
        }
        objectives = (
            f"{run_objectives}\nDocument: {doc['name']}\n"
            "Deepen ONLY the single finding in the work payload, nothing else. In the "
            "reasoning field, write three labelled parts on their own lines: "
            "PROVISION: the exact provision text this finding is about, quoted from the "
            "document you were given earlier in this prompt. COMPARISON: how it "
            "compares to the retrieved reference material below, if any is present. "
            "AMENDMENT: one concrete proposed change. Keep the same ref, kind and "
            "claim_id as the finding given to you."
        )
        r = await _run_one(wrapper, payload, objectives, max_tokens=DEEPEN_MAX_TOKENS,
                           reference_index_excerpt=refs_excerpt)
        parsed = r.get("parsed")
        if is_envelope(parsed) and parsed.get("items"):
            item = parsed["items"][0]
            if finding.get("item_id"):
                item["item_id"] = finding["item_id"]
            try:
                item["revision"] = int(finding.get("revision", 1)) + 1
            except (TypeError, ValueError):
                item["revision"] = 2
        out.append({"scope": "doc", "doc_id": doc["id"], "agent": wrapper.name,
                    "pass": 2, **r})
    return out


# ---------- pipeline phases ----------------------------------------------------------------

async def phase_3_4_content_production(orch, keys, op_docs, ctx_docs,
                                        run_objectives, convention_registry,
                                        reference_index, ctx_refs_excerpt,
                                        embed_store=None, max_concurrent_docs=4):
    """Run corpus-level and per-doc production agents."""
    results = []
    # Corpus-level uses both context and operational docs (everything in input/).
    # Per-doc digest is held to 1200 chars to keep large corpora affordable.
    all_docs = op_docs + ctx_docs
    digest = "\n\n=========\n\n".join(
        f"### Document: {d['name']}\n\n{_truncate(d['text'], 1200)}" for d in all_docs
    )
    for agent_name in PRODUCTION_AGENTS_CORPUS_LEVEL:
        wrapper = _build_wrapper(agent_name, orch, keys)
        payload = {"task": "corpus_level_analysis",
                   "documents": [d["name"] for d in all_docs],
                   "corpus_text": digest}
        result = await _run_one(wrapper, payload, run_objectives, channel="main",
                                max_tokens=PRODUCTION_MAX_TOKENS,
                                convention_registry=convention_registry,
                                reference_index_excerpt=ctx_refs_excerpt,
                                _progress=(3, None, None, agent_name))
        results.append({"scope": "corpus", "agent": agent_name, **result})
    # Per-doc only for OPERATIONAL docs (context is reference only).
    # Per Part XXI amendment, LEGAL_ANALYST gets provision-aware context refs.
    # Per Part XXVI, LEGAL_ANALYST also receives the structural inventory
    # extracted from the just-completed ARCHIVIST corpus output.
    all_context_refs = [e.as_dict() for e in reference_index.entries
                        if e.input_type == "context"]
    convention_provisions = _convention_provision_texts(convention_registry)
    structural_inventory = _structural_inventory(results)
    if structural_inventory:
        log_event(_LOG, f"structural_inventory elements={len(structural_inventory)} source=ARCHIVIST",
                  run_id=_run_id_of(orch), phase="3-4", agent="ARCHIVIST")
    # BP-5: per-doc production runs concurrently across documents (bounded), then
    # results are flattened from the gather returns (no shared-list mutation inside
    # the doc body). The corpus-level block above stays serial (cross-doc).
    doc_pos = {d["id"]: i + 1 for i, d in enumerate(op_docs)}
    n_docs = len(op_docs)

    async def _process_doc(doc):
        payload = {"task": "per_document_analysis",
                   "document_id": doc["id"], "document_name": doc["name"],
                   "document_text": _truncate_doc(doc["text"], 7000),
                   "structural_inventory": structural_inventory}
        provisions = convention_provisions or _segment_doc_text(doc["text"])
        provision_refs = _provision_aware_context_refs(
            all_context_refs, doc["text"], provisions, embed_store, cap=30,
        )
        tasks = []
        for agent_name in PRODUCTION_AGENTS_PER_DOC:
            wrapper = _build_wrapper(agent_name, orch, keys)
            if agent_name == "LEGAL_ANALYST" and provision_refs:
                refs_excerpt = provision_refs
            else:
                refs_excerpt = _doc_refs_excerpt(reference_index, doc['id'])
            tasks.append(_run_one(wrapper, payload,
                                  f"{run_objectives}\nDocument: {doc['name']}",
                                  max_tokens=PRODUCTION_MAX_TOKENS,
                                  convention_registry=convention_registry,
                                  reference_index_excerpt=refs_excerpt,
                                  _progress=(3, doc_pos[doc["id"]], n_docs, agent_name)))
        doc_results = await _gather_or_serial(tasks)
        results_this_doc = [{"scope": "doc", "doc_id": doc["id"], "agent": name, **r}
                            for name, r in zip(PRODUCTION_AGENTS_PER_DOC, doc_results)]
        # D6, local profile only: pass two deepens each LEGAL_ANALYST finding from pass
        # one. LEGAL_ANALYST alone, not all three per-doc agents: its contract
        # (claim_id/verdict/reasoning) is the one that matches D6's own diagnosis --
        # find an issue, analyse it, justify it, all in one call -- PROCESSOR
        # (extraction) and SPEECH_ACT_TAGGER (tagging) are single-purpose calls that
        # do not have this shape. Cloud path untouched (W5): this block never runs
        # off the local profile.
        if _is_local_profile():
            la_result = next((r for r in results_this_doc if r["agent"] == "LEGAL_ANALYST"), None)
            if la_result is not None and la_result.get("ok"):
                findings = decode_items(la_result.get("parsed"))
                if findings:
                    la_wrapper = _build_wrapper("LEGAL_ANALYST", orch, keys)
                    deepened = await _deepen_legal_analyst_findings_local(
                        la_wrapper, findings, doc, embed_store, run_objectives)
                    results_this_doc.extend(deepened)
        return results_this_doc

    for sub in await _gather_docs(op_docs, _process_doc, max_concurrent_docs):
        results.extend(sub)
    return results


async def phase_5_audit(orch, keys, op_docs, production, run_objectives,
                        convention_registry, reference_index, max_concurrent_docs=4):
    by_doc_agent = {(r["doc_id"], r["agent"]): r
                    for r in production if r.get("scope") == "doc"}
    out = []
    doc_pos = {d["id"]: i + 1 for i, d in enumerate(op_docs)}
    n_docs = len(op_docs)

    async def _process_doc(doc):
        proc = by_doc_agent.get((doc["id"], "PROCESSOR"))
        draft = proc.get("parsed") if proc else None
        # structure H3: what one agent hands another is typed. PROCESSOR's draft
        # reaches VERIFIER and FACT_CHECKER with every prose field removed, so the
        # auditors judge the draft's fields and citations rather than reading its
        # author's reasoning about them. The document under review is unaffected:
        # source_text and source_excerpt are the operator's material, not an
        # agent's opinion of it.
        draft_typed = _typed_for_agent(draft)
        verifier_payload = {"task": "verify_draft_against_source",
                            "document_name": doc["name"],
                            "source_text": _truncate_doc(doc["text"], 5500),
                            "processor_draft": draft_typed}
        fc_payload = {"task": "extract_and_verify_claims",
                      "document_name": doc["name"], "processor_draft": draft_typed,
                      "source_excerpt": _truncate_doc(doc["text"], 3500)}
        tasks = []
        for name, payload in (("VERIFIER", verifier_payload), ("FACT_CHECKER", fc_payload)):
            wrapper = _build_wrapper(name, orch, keys)
            tasks.append(_run_one(wrapper, payload,
                                  f"{run_objectives}\nDocument: {doc['name']}",
                                  max_tokens=AUDIT_MAX_TOKENS,
                                  convention_registry=convention_registry,
                                  reference_index_excerpt=_doc_refs_excerpt(reference_index, doc['id']),
                                  _progress=(5, doc_pos[doc["id"]], n_docs, name)))
        audit_results = await _gather_or_serial(tasks)
        return [{"scope": "doc", "doc_id": doc["id"], "agent": name, **r}
                for name, r in zip(("VERIFIER", "FACT_CHECKER"), audit_results)]

    for sub in await _gather_docs(op_docs, _process_doc, max_concurrent_docs):
        out.extend(sub)
    return out


def _prior_docs_for(ctx_docs, manifest, op_docs):
    """The earlier versions the operator declared, as loaded documents (R6).

    Returns (prior_docs, conflicts). A file named both as a target and as a prior
    is reviewed, not compared: it is dropped from the prior set and returned in
    `conflicts` so the caller can warn by filename (a filename, not content)."""
    names = role_resolution.manifest_prior(manifest)
    op_names = {d["name"] for d in op_docs or []}
    conflicts = sorted(names & op_names)
    docs = [d for d in ctx_docs or [] if d["name"] in (names - op_names)]
    return docs, conflicts


def _forced_roles(manifest):
    """(forced targets, forced grounding) from the manifest. An earlier version is
    grounding: it is never promoted to input/operational/, even when the date
    cutoff would promote it, because a document compared against is not a
    document under review."""
    return (role_resolution.manifest_targets(manifest),
            role_resolution.manifest_grounding(manifest) | role_resolution.manifest_prior(manifest))


def _prior_comparison(orch, doc, pairing, convention_registry, prior_docs, reference_index,
                      context_refs):
    """Compare every labelled figure of this document with the same field in the
    operator-declared earlier version(s), in Python, and mint ok-verdict records
    (R6 / INFRA-044).

    Runs in BOTH review modes (it sits before the mode branch), builds its own
    reference tables because in wide mode the paired path never runs, writes what
    it could and could not compare into the pairing map (`prior_comparisons` per
    unit, `prior_orphans` for the document), posts the records to the bus, and
    returns at most one computed envelope for the convention-review agent. It never
    takes the review down: any failure is logged by type and yields nothing.
    """
    if not pairing or not prior_docs:
        return []
    try:
        agent = CONVENTION_REVIEW_AGENTS[0]
        rules_by_id = {c["id"]: c for c in convention_registry.get("conventions", [])}
        unit_text = {u["unit_id"]: u for u in
                     pairing_map_mod.split_units(doc["text"], document_id=doc["id"])}
        vocabulary = set()
        for u in unit_text.values():
            vocabulary |= pairing_map_mod.unit_fields(u.get("text", ""))

        def needed(text):
            return pairing_map_mod.needed_fields(text, vocabulary)

        # The unit vocabulary is the UNION of this document's and the earlier
        # version's: a prose unit written in the earlier version must validate
        # against the same set, or a unit the newer text abbreviates is lost.
        known_units = set(reference_tables_mod.document_unit_tokens(doc["text"]))
        for pd in prior_docs:
            known_units |= reference_tables_mod.document_unit_tokens(pd["text"])
        index = {"lines": [], "tables": []}
        for pd in prior_docs:
            by_para = {int((e.location or {}).get("paragraph") or 0): e.ref_id
                       for e in reference_index.find_by_document(pd["id"])}
            idx = paired_review_mod.prior_index(
                pd["text"], lambda i, m=by_para: m.get(i, ""), known_units=known_units)
            index["lines"] += idx["lines"]
            index["tables"] += idx["tables"]
        # A rule "names" a field when the field is in the vocabulary tested against.
        # A term the earlier version states and this document dropped is not in
        # this document's vocabulary, so the earlier version's labels are added,
        # or no rule could ever be found to cite for a dropped term.
        vocabulary |= {e["label"] for e in index["lines"]}
        for t in index["tables"]:
            table = t["table"]
            for i in reference_tables_mod.key_column_indexes(table):
                if i == table.get("unit_column"):
                    continue
                for row in table["rows"]:
                    label = pairing_map_mod._norm_label(row[i])
                    if label:
                        vocabulary.add(label)
        ref_tables = reference_tables_mod.tables_from_entries(
            context_refs, exclude_document_id=doc["id"], known_units=known_units)
        # Every label ANY unit of this document carries: a term is "absent" only
        # when no unit states it any more, not when it moved between headings.
        present_all = set()
        for u in unit_text.values():
            present_all |= pairing_map_mod.unit_fields(u.get("text", ""))

        records, n_checks, n_refused = [], 0, 0
        for entry in pairing.get("units", []):
            unit = unit_text.get(entry["unit_id"])
            if unit is None:
                continue
            scalars, _, _ = paired_review_mod.extract_fields(unit.get("text", ""),
                                                             known_units=known_units)
            slug = entry["unit_id"].split("-", 1)[1] if "-" in entry["unit_id"] else ""
            hits, refused = paired_review_mod.prior_lookup(index, scalars, slug)
            rule_ids = [p["rule_id"] for p in entry.get("paired", [])
                        if p.get("rule_id") in rules_by_id]
            bands_by_label = {}
            for rid in rule_ids:
                rule = rules_by_id[rid]
                named = needed(rule.get("rule", ""))
                if not named:
                    continue
                bands = []
                b = paired_review_mod.bounds_from_rule(rule.get("rule", ""))
                if b:
                    bands.append({"low": b[0], "high": b[1], "unit": b[2], "rule_id": rid})
                for band in reference_tables_mod.bands_for_unit(
                        ref_tables, unit.get("text", ""), rule.get("rule", "")):
                    bands.append({"low": band["low"], "high": band["high"],
                                  "unit": band["unit"], "rule_id": rid})
                for label in named:
                    if label in scalars:
                        bands_by_label.setdefault(label, []).extend(bands)
            checks, refused2 = paired_review_mod.prior_checks(scalars, hits, bands_by_label)
            absent, refused3 = paired_review_mod.absent_checks(
                index, present_all, slug, scalars=scalars, hits=hits)
            checks += absent
            refused2 += refused3
            minted = paired_review_mod.prior_findings(
                unit, rule_ids, rules_by_id, checks,
                needed_fields_for=needed,
                source_rule_id_for=lambda rid: finding_record.source_rule_id_for(
                    rid, convention_registry),
                agent=agent, all_rules_by_id=rules_by_id)
            minted_fields = {m.get("field_label") for m in minted}
            for c in checks:
                if c.get("stated_field") not in minted_fields:
                    refused2.append({"label": c.get("stated_field", ""),
                                     "reason": "no rule to cite for this comparison",
                                     "ref_ids": list(c.get("ref_ids") or [])})
            entry["prior_comparisons"] = {
                "hit_count": len(hits),
                "checks": [{k: c.get(k) for k in (
                    "stated_field", "relation", "computed", "stated", "computed_unit",
                    "delta", "band_distance_change", "ref_ids")} for c in checks],
                "refused": refused + refused2,
            }
            records += minted
            n_checks += len(checks)
            n_refused += len(refused) + len(refused2)
        # A term the earlier version stated under a heading this document no
        # longer has is not silently lost: it is refused on the record, at the
        # document level of the map.
        slugs_here = {e["unit_id"].split("-", 1)[1] for e in pairing.get("units", [])
                      if "-" in e["unit_id"]}
        orphan = [{"label": " ".join(x["label"]), "unit_slug": x.get("unit_slug", ""),
                   "reason": "the earlier document's heading has no counterpart here"}
                  for x in index["lines"]
                  if x["label"] not in present_all and x.get("unit_slug") not in slugs_here]
        if orphan:
            pairing["prior_orphans"] = orphan
            n_refused += len(orphan)
        try:
            pairing_map_mod.write_pairing_map(orch.run_context, doc["id"], pairing)
        except Exception as e:
            log_event(_LOG, f"pairing_map_rewrite_error error_type={type(e).__name__}",
                      run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
        log_event(_LOG,
                  f"prior_comparison prior_docs={len(prior_docs)} checks={n_checks} "
                  f"records={len(records)} refused={n_refused}",
                  run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
        if not records:
            return []
        items = paired_review_mod.dedupe(records)
        envelope = agent_wrapper.make_envelope(agent, str(doc["id"]), items)
        try:
            _build_wrapper(agent, orch, {}).post_to_bus(
                recipient="ORCHESTRATOR", channel="main", msg_type="INFORM",
                body={"event": "AGENT_OUTPUT", "backend": "computed", "model": "python",
                      "item_count": len(items), "parse_trace": {}, "payload": envelope},
                constitution_check={"laws_consulted": ["LAW-V"], "result": "RESOLVED",
                                    "resolution": "compared in code with the operator-declared "
                                                  "earlier version; no model judged these values"})
        except Exception as e:
            log_event(_LOG, f"prior_comparison_bus_post_error error_type={type(e).__name__}",
                      run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
        return [{"scope": "doc", "doc_id": doc["id"], "agent": agent, "ok": True,
                 "parsed": envelope, "raw_text": "", "contract_missing": [],
                 "error": None, "item_count": len(items),
                 "backend": "computed", "model": "python"}]
    except Exception as e:  # the comparison must never take the review down (W8: type only)
        log_event(_LOG, f"prior_comparison_error error_type={type(e).__name__}",
                  run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
        return []


async def phase_5_5_convention_review(orch, keys, op_docs, run_objectives,
                                      convention_registry, reference_index,
                                      embed_store=None, structural_inventory=None,
                                      max_concurrent_docs=4, review_mode="wide",
                                      pairs_per_unit=None, prior_docs=(),
                                      convention_assignment=None):
    """Convention-driven review: PRACTICE_AUDITOR + STYLE_GUARDIAN against the registry.

    Per Part XXI amendment, both agents receive provision-aware context refs
    (baseline doc query + per-convention-rule queries merged). Per Part XXVI,
    PRACTICE_AUDITOR additionally receives the structural inventory in its
    work payload so its absence-detection directive has data to work with.

    `convention_assignment` (docs/api/CONVENTION_ASSIGNMENT_DESIGN.md, night
    chain W3) is the BOOT-computed comparison's `by_rule`/`by_agent` result,
    or None for a caller that predates it (the gate's own fixtures, mainly):
    with None, wide mode's firing gate and paired mode's per-pair agent
    choice both fall back to exactly today's behavior (every
    CONVENTION_REVIEW_AGENTS agent dispatched; PRACTICE_AUDITOR judges every
    pair), so this parameter changes nothing for a caller that does not pass
    it.
    """
    out = []
    all_context_refs = [e.as_dict() for e in reference_index.entries
                        if e.input_type == "context"]
    convention_provisions = _convention_provision_texts(convention_registry)
    doc_pos = {d["id"]: i + 1 for i, d in enumerate(op_docs)}
    n_docs = len(op_docs)

    async def _process_doc(doc):
        # structure H4: decide which rules could apply to which units BEFORE any
        # agent judges anything, and record the reason for every pairing and every
        # non-pairing. Written to <run>/audit/pairing_map.json. Nothing consumes it
        # to drive calls yet (that is paired review mode, H5); it is produced here
        # so the map is a real per-run artifact rather than a scaffold, and so the
        # counts can be read against a run that actually happened.
        pairing = None
        try:
            pairing = pairing_map_mod.build_pairing_map(
                doc["text"], convention_registry.get("conventions", []),
                document_id=doc["id"],
                rank=pairing_map_mod.embedding_ranker(embed_store),
                convention_registry=convention_registry,
            )
            pairing_map_mod.write_pairing_map(orch.run_context, doc["id"], pairing)
            doc["_pairing"] = pairing
            log_event(_LOG,
                      f"pairing_map units={pairing['unit_count']} rules={pairing['rule_count']} "
                      f"pairs={pairing['pair_count']} rejected={pairing['rejected_count']} "
                      f"undecided={pairing['undecided_count']} "
                      f"unmatched={len(pairing['unmatched_units'])}",
                      run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
        except Exception as e:  # a map that fails must not take the review down
            # The exception TYPE only: the message could carry document text, and
            # nothing this chain adds may log content (W8).
            log_event(_LOG, f"pairing_map_error error_type={type(e).__name__}",
                      run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
        # R6: the comparison with the operator-declared earlier version, in BOTH
        # modes, before the mode branch. Empty when no prior was declared.
        prior_results = _prior_comparison(orch, doc, pairing, convention_registry,
                                          prior_docs, reference_index, all_context_refs)
        provisions = convention_provisions or _segment_doc_text(doc["text"])
        provision_refs = _provision_aware_context_refs(
            all_context_refs, doc["text"], provisions, embed_store, cap=30,
        )
        refs_excerpt = provision_refs or _doc_refs_excerpt(reference_index, doc['id'])
        base_payload = {"task": "convention_review",
                        "document_id": doc["id"], "document_name": doc["name"],
                        "document_text": _truncate_doc(doc["text"], 6500),
                        "evaluate_against": [c.get("id") for c in convention_registry.get("conventions", [])]}
        # Boundary fix: a wide-mode finding's own unit_id used to be whatever the
        # agent called the thing it was looking at (a document identifier field,
        # e.g. "CAT-BIRCH"), never the pipeline's own split_units id (e.g.
        # "u02-record-cat-birch") that a downstream lookup (amendment_from_finding's
        # unit_texts) is keyed by. The two agents were never SHOWN the pipeline's own
        # ids, so no wording fix in the contract could have closed this: an agent
        # cannot copy an id it was never given. document_units carries exactly the
        # id and title pairing_map.split_units already produced (never the full
        # unit text, so this costs nothing beyond one short line per unit); the
        # contract (config/agent_contracts.json, finding_record.says.unit_id) now
        # tells both convention-review agents to copy one of these ids verbatim.
        # None when the pairing map itself failed to build (caught above): the
        # agents still see the document, they just have no id list to draw from,
        # same as before this fix.
        if pairing and pairing.get("units"):
            base_payload["document_units"] = [
                {"unit_id": u["unit_id"], "title": u.get("title", "")}
                for u in pairing["units"]
            ]
        if review_mode == "paired":
            return prior_results + await _paired_convention_review(
                orch, keys, doc, pairing, convention_registry, refs_excerpt,
                run_objectives, doc_pos, n_docs, pairs_per_unit,
                context_refs=all_context_refs,
                convention_assignment=convention_assignment)

        # night chain W3: the firing gate. An agent with a real, live rule
        # assignment fires; an agent with none STILL fires as long as at
        # least one loaded rule is untagged, since an untagged rule keeps
        # today's default routing (every convention-review agent), per the
        # operator's own instruction that this changes nothing until a
        # corpus is tagged. Only when BOTH are false, zero assigned rules
        # and zero untagged rules exist, does the agent have nothing to do.
        # With no assignment computed at all (convention_assignment is
        # None, a caller that predates W3), every agent fires, exactly as
        # before this gate existed.
        firing_agents = _convention_review_firing_agents(convention_assignment)

        # Convention distribution, step A: wide mode's registry excerpt is
        # filtered per agent (its assigned rules plus every untagged rule), so a
        # rule assigned to the board only reaches neither convention-review agent
        # here, and the pairing map records those rules as not judged in this
        # phase. Built without measurement; no run has scored it.
        if pairing is not None and convention_assignment is not None:
            pairing["not_judged"] = _wide_not_judged(convention_registry, convention_assignment)
            pairing["not_judged_count"] = len(pairing["not_judged"])
            if pairing["not_judged"]:
                log_event(_LOG, f"convention_review_not_judged mode=wide "
                                f"count={pairing['not_judged_count']}",
                          run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
                try:
                    pairing_map_mod.write_pairing_map(orch.run_context, doc["id"], pairing)
                except Exception as e:
                    log_event(_LOG, f"pairing_map_rewrite_error error_type={type(e).__name__}",
                              run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])

        tasks = []
        for name in firing_agents:
            wrapper = _build_wrapper(name, orch, keys)
            payload = dict(base_payload)
            registry_for_agent = _wide_registry_for_agent(convention_registry,
                                                          convention_assignment, name)
            payload["evaluate_against"] = [c.get("id") for c in
                                           registry_for_agent.get("conventions", [])]
            if name == "PRACTICE_AUDITOR" and structural_inventory:
                payload["structural_inventory"] = structural_inventory
            tasks.append(_run_one(wrapper, payload,
                                  f"{run_objectives}\nDocument: {doc['name']}\n"
                                  f"Evaluate against the convention registry. Every finding "
                                  f"MUST cite both CONV-* and REF-*.",
                                  max_tokens=WIDE_REVIEW_MAX_TOKENS,
                                  convention_registry=registry_for_agent,
                                  reference_index_excerpt=refs_excerpt,
                                  _progress=(5.5, doc_pos[doc["id"]], n_docs, name)))
        rev_results = await _gather_or_serial(tasks)
        return prior_results + [{"scope": "doc", "doc_id": doc["id"], "agent": name, **r}
                                for name, r in zip(firing_agents, rev_results)]

    for sub in await _gather_docs(op_docs, _process_doc, max_concurrent_docs):
        out.extend(sub)
    return out


async def _polish_findings(orch, keys, doc, findings, rules_by_id, unit_texts,
                           run_objectives, convention_registry):
    """refine R2: one NARROW call per finding, for wording only.

    The old drafter call was handed the whole document, every finding from five
    agents, the whole registry and thirty reference excerpts, and asked to
    "produce a complete amendments object". It answered by re-deriving fields
    Python had already computed, and by dropping the figures out of the sentence a
    reader checks. Measured: recall 2/9 with its sentences against 5/9 with
    figure-bearing ones, on identical arithmetic.

    Here it gets one finding, that finding's own unit, and that finding's own
    rule, and is asked for exactly two things it can do and Python cannot: one
    sentence for a person, and the corrected text where a correction is
    determinable. Nothing it returns becomes an amendment. Its two values are
    merged into the typed record (paired_review.apply_polish) and the
    deterministic template builds the amendment from there, so the figures, the
    rule id, the location and the refs stay Python's.

    A call that fails, times out, or answers with nothing leaves the record
    untouched and the template writes the amendment exactly as it would have
    (R2c: the run never depends on this agent succeeding).
    """
    if not findings:
        return findings, 0
    wrapper = _build_wrapper("AMENDMENT_DRAFTER", orch, keys)
    out, polished_count = [], 0
    for item in findings:
        if not finding_record.is_finding(item):
            out.append(item)
            continue
        if str(item.get("record_verdict") or "").lower() != "irregular":
            # R6: an ok-verdict record (a comparison with the earlier version) is
            # never an amendment, so it never buys a drafter call.
            out.append(item)
            continue
        unit = unit_texts.get(str(item.get("unit_id") or "")) or {}
        rule = rules_by_id.get(str(item.get("rule_id") or "")) or {}
        payload = {
            "task": "polish_amendment",
            "unit_id": item.get("unit_id"),
            "unit_text": _truncate_doc(unit.get("text", ""), 1200),
            "rule_id": item.get("rule_id"),
            "rule_text": rule.get("rule", ""),
            # The computed comparison, as typed fields. The model is shown what was
            # computed so it can describe it; it is never asked to recompute it.
            "relation": item.get("relation"),
            "value_a": item.get("value_a"), "unit_a": item.get("unit_a"),
            "value_b": item.get("value_b"), "unit_b": item.get("unit_b"),
            "record_verdict": item.get("record_verdict"),
            "answer_only": list(paired_review_mod.POLISHABLE_FIELDS),
        }
        try:
            result = await _run_one(
                wrapper, payload,
                f"{run_objectives}\nOne finding. Return ONLY "
                f"{', '.join(paired_review_mod.POLISHABLE_FIELDS)}. Do not restate the "
                f"figures, do not recompute them, and do not name a rule or a "
                f"reference: those are already recorded. `explanation` is one "
                f"sentence for a person. `proposed_text` is the corrected line as it "
                f"should read, or an empty string where the correction is not "
                f"determinable from this unit alone.",
                channel="main", max_tokens=512,
                convention_registry={"conventions": [rule]} if rule else convention_registry,
            )
        except Exception as e:
            log_event(_LOG, f"amendment_polish_error error_type={type(e).__name__}",
                      run_id=_run_id_of(orch), phase="6",
                      agent="AMENDMENT_DRAFTER", doc_id=doc["id"])
            out.append(item)
            continue
        parsed = (result or {}).get("parsed") or {}
        candidates = parsed.get("items") if isinstance(parsed, dict) else None
        merged = item
        for candidate in (candidates or [])[:1]:
            if isinstance(candidate, dict):
                merged = paired_review_mod.apply_polish(item, candidate)
        if merged is not item:
            polished_count += 1
        out.append(merged)
    return out, polished_count


def _paired_judging_agent(rule, convention_assignment):
    """night chain W3, answer 7: the SUBJECT chooses the judging agent for a
    paired-mode pair, replacing the fixed CONVENTION_REVIEW_AGENTS[0] pin.
    Never filters a pair out: every rule still gets judged, only by whichever
    agent the assignment names, so a wording-subject rule now reaches
    STYLE_GUARDIAN instead of being silently dropped by a fixed-agent filter.

    Deterministic: the first of the rule's own real, live consumer agents
    (by_rule[rule_id].consumer_agents, already sorted by
    convention_assignment.assign_conventions) that is a CONVENTION-REVIEW
    agent wins. Only a convention-review agent can judge a paired call: a
    rule whose consumers all sit outside phase 5.5 (a [redaction] rule is
    REDACTOR's, read in phase 9 by its own path; an [editorial] rule is the
    board's, read in phase 6.5 by escalation) is still judged here by
    PRACTICE_AUDITOR exactly as every rule is today, never dispatched to a
    rank that is summoned by escalation, and never dropped from the review.
    Convention distribution, step A (2026-09-11, built without measurement):
    the fallback that sent every other rule to PRACTICE_AUDITOR is gone. With
    an assignment computed, a rule whose consumers hold no convention-review
    agent (assigned to the editorial board only, or matched by no agent at
    all) gets NO judging agent: this returns None, the caller makes no call
    and records the plan in the pairing map as not judged, never silently
    dropped. An UNTAGGED rule keeps today's routing (PRACTICE_AUDITOR), per
    the operator's answer 1. With no assignment computed (None: a caller that
    predates W3, the gate's older fixtures) every rule is judged by
    PRACTICE_AUDITOR exactly as before. A rule id the assignment does not
    know at all (the registry and the assignment disagree, which BOOT never
    produces) also keeps the default, so a bookkeeping gap can never drop a
    rule from the review."""
    if convention_assignment is None:
        return CONVENTION_REVIEW_AGENTS[0]
    row = (convention_assignment.get("by_rule") or {}).get(rule.get("id"))
    if row is None or row.get("status") == "untagged":
        return CONVENTION_REVIEW_AGENTS[0]
    for name in row.get("consumer_agents") or []:
        if name in CONVENTION_REVIEW_AGENTS:
            return name
    return None


def _not_judged_reason(rule, convention_assignment):
    """Why a plan gets no judging agent, read off the assignment row, for the
    pairing map's own record (structural words only, no rule text)."""
    row = ((convention_assignment or {}).get("by_rule") or {}).get(rule.get("id")) or {}
    consumers = list(row.get("consumer_agents") or [])
    status = row.get("status") or "unknown"
    if consumers:
        return ("no convention-review consumer: assigned to %s only (status %s)"
                % (", ".join(consumers), status)), consumers, status
    return ("no convention-review consumer: matched no agent that can act on it "
            "(status %s)" % status), consumers, status


def _reattribute_computed_plan(plan, pairing, rules_by_id, convention_assignment):
    """A rule-INDEPENDENT computed plan (a sum, a product, a missing field: the
    comparison is the same whichever rule prompted it, paired_review.plan_calls)
    attributed by _rule_for_check to a rule with no judging agent is re-attributed
    to another rule paired on the same unit that HAS one, so the arithmetic is not
    lost to a bookkeeping choice. Prefers a rule naming the check's field, as
    _rule_for_check does. Returns the new rule, or None when no paired rule on the
    unit has a judging agent (then the plan is not judged, and recorded)."""
    unit_id = plan["unit"]["unit_id"]
    entry = next((u for u in (pairing or {}).get("units", []) if u.get("unit_id") == unit_id), None)
    candidates = [rules_by_id.get(p.get("rule_id")) for p in (entry or {}).get("paired", [])]
    candidates = [r for r in candidates if r and r.get("id") != plan["rule"].get("id")
                  and _paired_judging_agent(r, convention_assignment) is not None]
    if not candidates:
        return None
    field = str((plan.get("checks") or [{}])[0].get("stated_field") or "").lower()
    words = {w for w in field.split() if w}
    for r in candidates:
        if words and words <= set(str(r.get("rule", "")).lower().split()):
            return r
    return candidates[0]


def _wide_registry_for_agent(convention_registry, convention_assignment, agent_name):
    """The registry excerpt a wide-mode convention-review agent is shown: the
    rules the assignment gave it, plus every untagged rule (today's routing),
    plus any rule the assignment does not know (never dropped by a bookkeeping
    gap). With no assignment computed, the whole registry, as before. A rule
    assigned to the editorial board only, or to no agent, reaches neither
    convention-review agent here; it is the board's, read in phase 6.5."""
    if convention_assignment is None:
        return convention_registry
    by_rule = convention_assignment.get("by_rule") or {}
    mine = set((convention_assignment.get("by_agent") or {}).get(agent_name) or [])
    keep = []
    for c in convention_registry.get("conventions", []):
        cid = c.get("id")
        row = by_rule.get(cid)
        if cid in mine or row is None or row.get("status") == "untagged":
            keep.append(c)
    out = dict(convention_registry)
    out["conventions"] = keep
    return out


def _wide_not_judged(convention_registry, convention_assignment):
    """The rules no convention-review agent is shown in wide mode, for the
    pairing map's record: one entry per rule, no unit (wide mode has no plans)."""
    if convention_assignment is None:
        return []
    out = []
    for c in convention_registry.get("conventions", []):
        if _paired_judging_agent(c, convention_assignment) is None:
            reason, consumers, status = _not_judged_reason(c, convention_assignment)
            out.append({"unit_id": None, "rule_id": c.get("id"), "kind": "wide",
                        "reason": reason, "consumer_agents": consumers, "status": status})
    return out


async def _paired_convention_review(orch, keys, doc, pairing, convention_registry,
                                    refs_excerpt, run_objectives, doc_pos, n_docs,
                                    pairs_per_unit, *, context_refs=(),
                                    convention_assignment=None):
    """structure H5. One narrow call per (unit, rule) pair, arithmetic in Python.

    Three outcomes per pair, and only one of them costs a call:

      the figures disagree   Python has already computed the comparison. The model
                             is shown the computed values and asked ONLY whether the
                             difference is material and how to state it. The finding
                             carries Python's numbers whatever the model says.
      nothing computable     Python could compute no comparison for this pair, which
                             is what happens when the band lives in the reference
                             corpus rather than in the rule. The model judges on the
                             text, on ONE unit against ONE rule.
      the figures agree      No finding and NO CALL. This is where the saving is.

    A pair the cap drops is counted and logged, never silently skipped.

    night chain W3, answer 7: the judging agent is chosen PER PLAN by
    _paired_judging_agent, not fixed to CONVENTION_REVIEW_AGENTS[0]. Plans
    are grouped by their chosen agent after judging, so each agent that
    actually judged at least one pair posts its own envelope and its own
    bus message, one result dict per agent that fired, instead of always
    exactly one result for the whole document."""
    if not pairing:
        return []
    rules_by_id = {c["id"]: c for c in convention_registry.get("conventions", [])}
    # There used to be a second unit map here (units_by_id, keyed off
    # pairing.get("units", []), the pairing map's OWN entries, which carry no
    # "text" field at all). It was assigned and never read again in this
    # function: every real call is built from unit_text below, the single
    # split_units() call that actually feeds plan_calls. Two parallel maps of
    # "the same units," one live and one dead, is exactly the shape of trap
    # that makes an order- or index-based fix (the adjacent-neighbor lookup)
    # silently land on the wrong one. One map, sourced once, here.
    unit_text = {}
    for unit in pairing_map_mod.split_units(doc["text"], document_id=doc["id"]):
        unit_text[unit["unit_id"]] = unit
    vocabulary = set()
    for unit in unit_text.values():
        vocabulary |= pairing_map_mod.unit_fields(unit.get("text", ""))

    pairs, dropped = paired_review_mod.pairs_from_map(pairing, cap_per_unit=pairs_per_unit)
    # structure H7: ONE call per distinct computed disagreement, not one per pair.
    # Measuring the plan showed the first version making 40 calls on the operator's
    # document, a projected 52 to 57 minutes against the 40.3 minute wide run it
    # replaces, because a sum does not depend on which rule is being applied and was
    # being recomputed and re-judged once per paired rule. The same document now
    # plans 4 calls.
    # R1: the bands that decide most of this review live in TABLES in the reference
    # corpus, not in the rules. Parse them once per document, excluding the document
    # under review (its own tables are the figures being checked, not the reference).
    known_units = reference_tables_mod.document_unit_tokens(doc["text"])
    ref_tables = reference_tables_mod.tables_from_entries(
        context_refs, exclude_document_id=doc["id"], known_units=known_units)
    log_event(_LOG,
              f"reference_tables tables={len(ref_tables)} "
              f"ranged={sum(1 for t in ref_tables if 'range' in t['kinds'])}",
              run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])

    def _bands_for(text, rule):
        return reference_tables_mod.bands_for_unit(ref_tables, text, rule.get("rule", ""))

    # The pairing map records what the band check could and could not decide, per
    # unit, BEFORE any verdict fires. Written into the map that is already
    # persisted, so the reason a low figure was or was not stated as a finding is
    # on the record.
    rules = convention_registry.get("conventions", [])
    for entry in pairing.get("units", []):
        unit = unit_text.get(entry["unit_id"])
        if unit is None:
            continue
        entry["band_conditions"] = reference_tables_mod.band_conditions_for_unit(
            ref_tables, unit.get("text", ""), rules, vocabulary=vocabulary)
    try:
        pairing_map_mod.write_pairing_map(orch.run_context, doc["id"], pairing)
    except Exception as e:  # a map that fails to rewrite must not take the review down
        log_event(_LOG, f"pairing_map_rewrite_error error_type={type(e).__name__}",
                  run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])

    plans = paired_review_mod.plan_calls(
        unit_text, pairs, rules_by_id, vocabulary,
        needed_fields_for=lambda text: pairing_map_mod.needed_fields(text, vocabulary),
        reference_bands_for=_bands_for, known_units=known_units)

    log_event(_LOG,
              f"paired_review pairs={len(pairs)} dropped_by_cap={len(dropped)} "
              f"calls={len(plans)} saved={len(pairs) - len(plans)}",
              run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])

    # night chain W3, answer 7: the judging agent is chosen PER PLAN by its
    # rule's own subject, never a single fixed agent for the whole document.
    # computed_items_by_agent accumulates each agent's own findings, so each
    # agent that actually judged something posts its own envelope below,
    # instead of one envelope always posted under a single fixed name.
    computed_items_by_agent: dict = {}
    results = []
    # Convention distribution, step A: a plan whose rule has no judging agent
    # (assigned to the board only, or to no agent) makes no call and is recorded
    # here, never silently dropped. A rule-independent computed plan is first
    # re-attributed to a paired rule on the same unit that has a judging agent,
    # since the arithmetic is the same whichever rule prompted it.
    not_judged = []
    reattributed = []
    absence = []
    judged_items_by_agent: dict = {}
    judged_provenance: dict = {}
    for plan in plans:
        unit, rule, checks = plan["unit"], plan["rule"], plan["checks"]
        agent = _paired_judging_agent(rule, convention_assignment)
        if agent is None and plan.get("kind") == "computed":
            alt = _reattribute_computed_plan(plan, pairing, rules_by_id, convention_assignment)
            if alt is not None:
                log_event(_LOG, f"paired_review_reattributed unit={unit['unit_id']} "
                                f"from={rule['id']} to={alt['id']}",
                          run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
                reattributed.append({"unit_id": unit["unit_id"], "from_rule_id": rule["id"],
                                     "to_rule_id": alt["id"], "kind": plan.get("kind")})
                rule = plan["rule"] = alt
                agent = _paired_judging_agent(rule, convention_assignment)
        if agent is None:
            reason, consumers, status = _not_judged_reason(rule, convention_assignment)
            not_judged.append({"unit_id": unit["unit_id"], "rule_id": rule["id"],
                               "kind": plan.get("kind"), "reason": reason,
                               "consumer_agents": consumers, "status": status})
            continue
        source_rule_id = finding_record.source_rule_id_for(rule["id"], convention_registry)
        refs = [r.get("ref_id") for r in (refs_excerpt or [])[:3] if r.get("ref_id")]
        # D, option 2, Python first: a declared required field absent from a unit
        # in scope is a finding Python decides, no call made; the record says so.
        if plan.get("kind") == "absence_computed":
            check = checks[0]
            item = paired_review_mod.finding_from_check(
                unit_id=unit["unit_id"], rule=rule, check=check,
                source_rule_id=source_rule_id, refs=refs)
            item["absence_path"] = "computed"
            computed_items_by_agent.setdefault(agent, []).append(item)
            absence.append({"unit_id": unit["unit_id"], "rule_id": rule["id"],
                            "field": check.get("stated_field"), "path": "computed"})
            log_event(_LOG, f"paired_review_absence unit={unit['unit_id']} rule={rule['id']} "
                            f"path=computed",
                      run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
            continue
        wrapper = _build_wrapper(agent, orch, keys)
        # docs/api/UNIT_CONTEXT_DESIGN.md, option B reached through D's scaffold:
        # unit_text (this document's own units, every one carrying index since
        # the order fix) lets build_pair_payload find this unit's real
        # neighbors; pairing["units"] (the SAME ordered id/title list wide
        # mode's document_units already reuses, not rebuilt here) is the
        # structural map. Both optional on the function's own contract; both
        # given here because a paired call is exactly the narrow question this
        # design was built to answer without reopening wide mode's whole-
        # document framing.
        payload = paired_review_mod.build_pair_payload(
            unit=unit, rule=rule, checks=checks, refs=refs,
            source_rule_id=source_rule_id, unit_texts=unit_text,
            document_units=pairing.get("units"))
        if plan.get("kind") == "absence_judged":
            # D, option 2, the model only where Python cannot settle it: the rule
            # declares its scope and this unit is in it, but the requirement is
            # conditional in the rule's own words, so the question goes to the model
            # on this unit alone. The answer's unit and rule are stamped by Python,
            # which knows them by construction, and the path is recorded.
            payload["absence_question"] = (
                "This unit is inside the rule's declared scope. From this unit's own "
                "text alone, decide whether the rule's requirement applies to it and, "
                "if it applies, whether it is met. Answer as a finding on this unit "
                "under this rule; state which condition in the rule decided it.")
        r = await _run_one(
            wrapper, payload,
            f"{run_objectives}\nOne unit, one rule. Do not perform arithmetic.",
            max_tokens=PAIRED_JUDGING_MAX_TOKENS, convention_registry={"conventions": [rule]},
            reference_index_excerpt=refs_excerpt,
            _progress=(5.5, doc_pos[doc["id"]], n_docs, agent))
        if plan.get("kind") == "absence_judged":
            judged = _stamped_judged_items(r, agent, unit["unit_id"], rule["id"], source_rule_id)
            judged_items_by_agent.setdefault(agent, []).extend(judged)
            judged_provenance[agent] = (r.get("backend") if isinstance(r, dict) else None,
                                        r.get("model") if isinstance(r, dict) else None)
            absence.append({"unit_id": unit["unit_id"], "rule_id": rule["id"], "field": None,
                            "path": "judged", "items": len(judged),
                            "call_id": (r.get("call_id") if isinstance(r, dict) else None)})
            log_event(_LOG, f"paired_review_absence unit={unit['unit_id']} rule={rule['id']} "
                            f"path=judged items={len(judged)}",
                      run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
            results.append(r)
            continue
        explanation = _first_explanation(r)
        for check in paired_review_mod.disagreements(checks):
            computed_items_by_agent.setdefault(agent, []).append(
                paired_review_mod.finding_from_check(
                    unit_id=unit["unit_id"], rule=rule, check=check,
                    source_rule_id=source_rule_id, refs=refs, explanation=explanation))
        results.append(r)

    # Every unit the map matched to nothing is still a finding, not a
    # silence, routed by its own nearest-miss rule's subject the same way a
    # judged pair is; a rule id the assignment does not recognise falls back
    # to the paired-mode default, same as _paired_judging_agent's own fallback.
    for finding in pairing.get("missing_field_findings", []):
        rule = rules_by_id.get(finding.get("rule_id")) or {"id": finding.get("rule_id")}
        agent = _paired_judging_agent(rule, convention_assignment)
        if agent is None:
            reason, consumers, status = _not_judged_reason(rule, convention_assignment)
            not_judged.append({"unit_id": finding.get("unit_id"), "rule_id": rule.get("id"),
                               "kind": "missing_field", "reason": reason,
                               "consumer_agents": consumers, "status": status})
            continue
        computed_items_by_agent.setdefault(agent, []).append(finding)

    # The record of what this phase did NOT judge, in the map that is already
    # persisted, beside the plans it did: a reader (and the classifier) can tell a
    # rule the review never asked from one it asked and got nothing back on.
    pairing["not_judged"] = not_judged
    pairing["not_judged_count"] = len(not_judged)
    pairing["reattributed"] = reattributed
    # D, option 2: which path decided each declared absence, computed or judged,
    # in the map beside the plans, so a reader can tell the two apart later.
    pairing["absence"] = absence
    pairing["absence_computed_count"] = sum(1 for a in absence if a["path"] == "computed")
    pairing["absence_judged_count"] = sum(1 for a in absence if a["path"] == "judged")
    log_event(_LOG, f"paired_review_not_judged count={len(not_judged)} "
                    f"reattributed={len(reattributed)} absence_computed="
                    f"{pairing['absence_computed_count']} absence_judged="
                    f"{pairing['absence_judged_count']}",
              run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
    try:
        pairing_map_mod.write_pairing_map(orch.run_context, doc["id"], pairing)
    except Exception as e:  # a map that fails to rewrite must not take the review down
        log_event(_LOG, f"pairing_map_rewrite_error error_type={type(e).__name__}",
                  run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])

    out_results = []
    for agent, raw_items in computed_items_by_agent.items():
        items = paired_review_mod.dedupe(raw_items)
        log_event(_LOG, f"paired_review_findings agent={agent} count={len(items)}",
                  run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
        envelope = agent_wrapper.make_envelope(agent, str(doc["id"]), items)
        # The COMPUTED findings go on the bus. They did not, before this: the envelope
        # was returned in memory to phase 6 and never posted, so the bus carried only
        # the model's raw judging responses. Everything that reads the bus was blind to
        # the findings Python actually made: GET /findings, the held-out scorer, and
        # INFRA-037's own promise that consumers read by reference. Found by scoring the
        # first unseen corpus, where three correct findings could not be proven from
        # any typed record. Posted through the same wrapper method and message shape
        # as a model's output, with backend "paired" and model "python" so provenance
        # is not misstated: these are Python's records under the agent's name.
        if items:
            try:
                _build_wrapper(agent, orch, keys).post_to_bus(
                    recipient="ORCHESTRATOR", channel="main", msg_type="INFORM",
                    body={"event": "AGENT_OUTPUT", "backend": "paired", "model": "python",
                          "item_count": len(items), "parse_trace": {}, "payload": envelope},
                    constitution_check={"laws_consulted": ["LAW-V"], "result": "RESOLVED",
                                        "resolution": "computed in code from the unit's own "
                                                      "figures; no model judged these values"})
            except Exception as e:  # a bus that refuses must not take the review down
                log_event(_LOG, f"paired_review_bus_post_error agent={agent} "
                                f"error_type={type(e).__name__}",
                          run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
        out_results.append({"scope": "doc", "doc_id": doc["id"], "agent": agent, "ok": True,
                            "parsed": envelope, "raw_text": "", "contract_missing": [],
                            "error": None, "item_count": len(items),
                            "backend": "paired", "model": "python+model"})

    # D, option 2: the model's judged absence findings, stamped with the unit and
    # rule Python knows by construction and with absence_path=judged, posted under
    # the judging agent with the MODEL's own backend and model (never "python"),
    # so provenance is not misstated, and returned for phase 6 like any other item.
    for agent, raw_items in judged_items_by_agent.items():
        items = paired_review_mod.dedupe(raw_items)
        backend, model = judged_provenance.get(agent, (None, None))
        log_event(_LOG, f"paired_review_judged_findings agent={agent} count={len(items)}",
                  run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
        envelope = agent_wrapper.make_envelope(agent, str(doc["id"]), items)
        if items:
            try:
                _build_wrapper(agent, orch, keys).post_to_bus(
                    recipient="ORCHESTRATOR", channel="main", msg_type="INFORM",
                    body={"event": "AGENT_OUTPUT", "backend": backend or "", "model": model or "",
                          "item_count": len(items), "parse_trace": {}, "payload": envelope,
                          "stamped_by": "python", "absence_path": "judged"},
                    constitution_check={"laws_consulted": ["LAW-V"], "result": "RESOLVED",
                                        "resolution": "a judged absence: the model's own "
                                                      "finding, its unit and rule stamped "
                                                      "by the pipeline that asked"})
            except Exception as e:
                log_event(_LOG, f"paired_review_bus_post_error agent={agent} "
                                f"error_type={type(e).__name__}",
                          run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
        out_results.append({"scope": "doc", "doc_id": doc["id"], "agent": agent, "ok": True,
                            "parsed": envelope, "raw_text": "", "contract_missing": [],
                            "error": None, "item_count": len(items),
                            "backend": backend or "", "model": model or ""})

    # No plan and no missing-field finding at all: the document had nothing to
    # pair, but the phase still owes a result so downstream progress counting
    # and _items_for's per-agent lookups behave exactly as before this
    # per-agent split (an empty envelope under the paired-mode default agent,
    # the same shape a zero-plan document always returned).
    # Step B (paired-mode firing): the empty result is owed under an agent the
    # firing gate lets fire, never under one it kept from running; with no such
    # agent, the phase made no call and returns no result at all, and says so.
    if not out_results:
        firing = _convention_review_firing_agents(convention_assignment)
        if not firing:
            log_event(_LOG, "paired_review_no_firing_agent",
                      run_id=_run_id_of(orch), phase="5.5", doc_id=doc["id"])
            return out_results
        default_agent = firing[0]
        envelope = agent_wrapper.make_envelope(default_agent, str(doc["id"]), [])
        out_results.append({"scope": "doc", "doc_id": doc["id"], "agent": default_agent,
                            "ok": True, "parsed": envelope, "raw_text": "",
                            "contract_missing": [], "error": None, "item_count": 0,
                            "backend": "paired", "model": "python+model"})
    return out_results


def _stamped_judged_items(result, agent, unit_id, rule_id, source_rule_id):
    """The typed Finding items a judged-absence call returned (D, option 2), each
    stamped with the unit and rule Python asked about (never invented: the plan
    was one unit against one rule), the operator's own rule id, and
    absence_path=judged. The item id names the unit and rule so two judged plans
    can never collide on the derived id the wrapper would otherwise mint. A
    malformed or empty reply yields no items, never a dead run."""
    if not isinstance(result, dict):
        return []
    parsed = result.get("parsed")
    if isinstance(parsed, dict):
        raw = parsed.get("items") or []
    elif isinstance(parsed, list):
        raw = parsed
    else:
        raw = []
    out = []
    for idx, it in enumerate(raw):
        if not isinstance(it, dict) or not finding_record.is_finding(it):
            continue
        item = dict(it)
        item["unit_id"] = unit_id
        if not finding_record.resolved_rule_id(item):
            item["rule_id"] = rule_id
        if source_rule_id and not item.get("source_rule_id"):
            item["source_rule_id"] = source_rule_id
        item["absence_path"] = "judged"
        item["item_id"] = f"{agent}:finding:{unit_id}:{rule_id}:{idx}"
        item["revision"] = 1
        out.append(item)
    return out


def _first_explanation(result):
    """The model's sentence, if it produced one. Its numbers are never used.

    Defensive about the SHAPE of what came back, and it has to be: the second unseen
    corpus (no figures anywhere, so all 41 pairs went to the model) had one local
    reply arrive with `parsed` as a bare list of items rather than an envelope dict,
    and `.get` on it raised AttributeError, which killed the run in phase 5.5 after
    21 minutes. A judging call is only ever asked for a sentence; a malformed reply
    is worth an empty sentence, never a dead run.
    """
    if not isinstance(result, dict):
        return ""
    parsed = result.get("parsed")
    if isinstance(parsed, dict):
        items = parsed.get("items") or []
    elif isinstance(parsed, list):
        items = parsed
    else:
        return ""
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            for field in ("explanation", "recommendation", "reasoning", "rationale"):
                text = item.get(field)
                if isinstance(text, str) and text.strip():
                    return text.strip()
    return ""


def _doc_refs_excerpt(reference_index, document_id):
    return [e.as_dict() for e in reference_index.find_by_document(document_id)[:30]]


def _items_for(results, agent, *, doc_id=None, scope=None):
    """THE single results-level adapter over the canonical decoder (INFRA-037).

    Decode every matching agent result's wrapper (body.payload) into its CURRENT
    items (highest revision per item_id) via agent_wrapper.decode_items, and
    concatenate. Replaces the three former normalizers (_filter_doc, _flatten,
    _extract_structural_inventory). There is no other reader of agent items.

    D6: an agent can now appear as MULTIPLE separate results for the same
    doc_id (pass one and pass two of the local-profile two-pass split are two
    separate run_task calls, each its own envelope). decode_items only reduces
    revisions WITHIN one call's own items; a second current_items pass over the
    full concatenation is what makes pass two's higher-revision item actually
    supersede pass one's matching item_id across calls, not just within one.
    Idempotent for the normal one-result-per-agent-per-doc case (nothing to
    supersede), so this changes nothing for any pre-D6 caller."""
    out = []
    for r in results:
        if r.get("agent") != agent or not r.get("ok"):
            continue
        if doc_id is not None and r.get("doc_id") != doc_id:
            continue
        if scope is not None and r.get("scope") != scope:
            continue
        out.extend(decode_items(r.get("parsed")))
    return current_items(out)


def _structural_inventory(production_results: list) -> list[dict]:
    """Per Part XXVI: ARCHIVIST's corpus-level inventory is now one item per
    governance element (kind='inventory'); decode them via the canonical decoder."""
    return [it for it in _items_for(production_results, "ARCHIVIST", scope="corpus")
            if it.get("kind") == "inventory"]


# ---------- phase 6: synthesis ---------------------------------------------------------------


def _harvest_amendment_payloads_from_bus(orch) -> dict:
    """Return {document_id: amendments_master} for any AMENDMENT_DRAFTER outputs
    already on the bus, so phase 6 can skip re-running them. Reads the canonical
    wrapper (INFRA-037) via the decoder and builds the INFRA-033 amendments MASTER
    ({document_id, amendments:[items]}). The master shape is unchanged."""
    out = {}
    for msg in orch.bus.read_all():
        if msg.get("sender") != "AMENDMENT_DRAFTER" or msg.get("type") != "INFORM":
            continue
        body = msg.get("body") or {}
        if body.get("event") != "AGENT_OUTPUT":
            continue
        payload = body.get("payload")
        if is_envelope(payload):
            out[payload["doc_id"]] = {"document_id": payload["doc_id"],
                                      "amendments": decode_items(payload)}
    return out


def _mint_web_references(results, reference_index) -> int:
    """INFRA-042: mint a WEB-REF-NNNN id for each STRUCTURED web-source value on FACT_CHECKER /
    PRACTICE_AUDITOR findings (source_url, reference_url, reference_source) and append it to the
    finding's ref_ids via INFRA-037 supersession (a revision+1 item), so a web-grounded finding is
    seen as grounded by the OPT-1 gate and is citable by AMENDMENT_DRAFTER. Inline free-text URLs
    are out of scope. Mutates the wrappers in place; returns the count of WEB-REF ids minted."""
    minted = 0
    for r in (results or []):
        if not (isinstance(r, dict) and r.get("ok")):
            continue
        agent = r.get("agent")
        if agent not in reference_builder.WEB_SOURCE_FIELDS:
            continue
        parsed = r.get("parsed")
        if not (isinstance(parsed, dict) and isinstance(parsed.get("items"), list)):
            continue
        supersessions = []
        for item in decode_items(parsed):
            sources = reference_builder.web_sources_in(agent, item)
            if not sources:
                continue
            existing = list(item.get("ref_ids") or [])
            new_ids = []
            for _field, value in sources:
                entry = reference_index.add_web_reference(url=value)
                reference_index.cite_web(entry.web_ref_id, agent)
                if entry.web_ref_id not in existing and entry.web_ref_id not in new_ids:
                    new_ids.append(entry.web_ref_id)
            if not new_ids:
                continue
            sup = dict(item)
            sup["revision"] = int(item.get("revision", 1)) + 1
            sup["ts"] = datetime.now(timezone.utc).isoformat()
            sup["ref_ids"] = existing + new_ids
            supersessions.append(sup)
            minted += len(new_ids)
        parsed["items"].extend(supersessions)
    return minted


def write_deliverables_run_summary(deliv_dir, op_docs, deliverables, *,
                                   total_cost_usd, task, question=""):
    """BP-16: write the top-level deliverables/_run_summary.md index. Lists what was
    reviewed, the amendment count per document, the total cost, and a markdown link to
    each per-document subfolder. Pure function of its inputs (testable). Returns the path.
    `question` (R6): the operator's framing question, echoed when given."""
    deliv_dir = Path(deliv_dir)
    deliv_dir.mkdir(parents=True, exist_ok=True)
    total_amendments = sum((deliverables.get(d["id"]) or {}).get("amendment_count", 0)
                           for d in op_docs)
    lines = [
        f"# Run summary ({task})",
        "",
    ]
    if (question or "").strip():
        lines.append(f"- question: {question.strip()}")
    lines += [
        f"- generated: {datetime.now(timezone.utc).isoformat()}",
        f"- documents reviewed: {len(op_docs)}",
        f"- total amendments: {total_amendments}",
        f"- total cost: ${total_cost_usd:.4f}",
        "",
        "## Documents",
        "",
    ]
    if not op_docs:
        lines.append("(no documents under review)")
    for doc in op_docs:
        info = deliverables.get(doc["id"]) or {}
        n = info.get("amendment_count", 0)
        # The folder already names the document; link to it for the per-doc artifacts.
        suffix = ""
        compared = info.get("prior_comparison_count", 0)
        if compared:
            suffix = f", {compared} term(s) compared with the earlier version"
            absent = info.get("prior_absent_count", 0)
            if absent:
                suffix += f", {absent} absent since it"
        lines.append(f"- [{doc['name']}]({doc['id']}/): {n} amendment(s){suffix}")
    path = deliv_dir / run_context_mod.RUN_SUMMARY_NAME
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


async def phase_6_synthesis(orch, keys, op_docs, production, audit, conv_review,
                            run_objectives, convention_registry, reference_index,
                            embed_store=None, max_concurrent_docs=4,
                            amendment_polish=False, question=""):
    """Produce context_summary, operative_summary, amendments JSON+md, amendments.docx.

    `question` (R6) is the operator's framing question for a review run, echoed in
    document_summary.md and never parsed.

    `amendment_polish` (refine R2) turns the AMENDMENT_DRAFTER model call back on.
    OFF by default: every amendment is rendered deterministically from the typed
    Finding records instead, because the model's wording was measured to lose
    findings the arithmetic had already got right.

    `embed_store` (genesis Part XXI): when provided, per-doc context filtering
    uses cosine-similarity retrieval instead of Zipfian term matching. The
    REF-* citation format is identical regardless of which path runs.
    """
    # Per-run deliverables folder (Part XXVII §A): output/runs/<run>/deliverables/.
    deliv_dir = orch.run_context.deliverables_dir()
    deliv_dir.mkdir(parents=True, exist_ok=True)
    deliverables = {}
    existing_amendments = _harvest_amendment_payloads_from_bus(orch)
    conventions_by_category = {}
    for c in convention_registry.get("conventions", []):
        conventions_by_category.setdefault(c.get("category", "unclassified"), []).append(c)

    all_context_refs = [e.as_dict() for e in reference_index.entries
                        if e.input_type == "context"]
    n_total_conventions = len(convention_registry.get("conventions", []))
    retrieval_mode = "semantic" if embed_store else "zipfian"
    log_event(_LOG, f"retrieval_mode mode={retrieval_mode}",
              run_id=_run_id_of(orch), phase="6")

    # INFRA-042: mint WEB-REF ids from the structured web-source fields BEFORE the OPT-1 gate, so a
    # web-grounded finding is seen as grounded (its WEB-REF id is in ref_ids) and is citable.
    web_results = (production or []) + (audit or []) + (conv_review or [])
    minted = _mint_web_references(web_results, reference_index)
    if minted:
        reference_index.save()
        log_event(_LOG, f"web_refs_minted count={minted}",
                  run_id=_run_id_of(orch), phase="6")

    # OPT-1 verifiability gate: a CONFIDENT positive affirmation that cites nothing is
    # downgraded to UNCERTAIN via INFRA-037 supersession, before findings feed synthesis,
    # the amendment drafter, and render. Operates on the canonical result wrappers that
    # every _items_for/decode_items consumer reads (production: LEGAL_ANALYST; audit:
    # FACT_CHECKER; conv_review: PRACTICE_AUDITOR). Flagged-and-kept, never dropped.
    vg = verifiability_gate.apply_verifiability_gate(web_results)
    if vg["downgraded"]:
        log_event(_LOG, f"verifiability_gate_downgraded count={vg['downgraded']} to=UNCERTAIN",
                  run_id=_run_id_of(orch), phase="6")

    # BP-5: synthesis runs concurrently across documents (bounded). Each doc writes
    # its OWN per-doc deliverable files (unique paths keyed by doc id, no collision)
    # and returns (doc_id, info); the deliverables map is assembled from the returns.
    # The cross-doc steps above (WEB-REF minting, verifiability gate) stay serial.
    async def _process_doc(doc):
        # Findings first: they determine the topical scope for context_summary too.
        pa_findings = _stamp_source_rule_ids(
            _items_for(conv_review, "PRACTICE_AUDITOR", doc_id=doc["id"]) or [], convention_registry)
        sg_findings = _stamp_source_rule_ids(
            _items_for(conv_review, "STYLE_GUARDIAN", doc_id=doc["id"]) or [], convention_registry)
        findings = []
        categories_with_findings = set()
        for agent, raw_findings in (("PRACTICE_AUDITOR", pa_findings),
                                     ("STYLE_GUARDIAN", sg_findings)):
            for f in raw_findings:
                cat = _category_for_conv(finding_record.resolved_rule_id(f), convention_registry) or "unclassified"
                normalized = _normalize_finding(f)
                normalized["category"] = cat
                normalized["agent"] = agent
                findings.append(normalized)
                categories_with_findings.add(cat)

        # Context summary: doc-specific topical filter on refs + topics from
        # categories where findings actually fired. When a semantic embedding
        # store is available, use cosine similarity (Part XXI); otherwise fall
        # back to Zipfian term matching. Both paths produce REF-* citations.
        ctx_refs = _semantic_filter_context_refs(
            all_context_refs, doc["text"], embed_store, n=20,
        ) or _filter_context_refs_for_doc(all_context_refs, doc["text"])
        topics = sorted(categories_with_findings) if categories_with_findings \
            else list(conventions_by_category.keys())
        ctx_body = (
            f"This document was reviewed against {n_total_conventions} conventions. "
            f"{len(findings)} findings were produced by PRACTICE_AUDITOR and STYLE_GUARDIAN. "
            f"The context references below are filtered for topical relevance to {doc['name']}."
        )
        # BP-16: every artifact for this doc goes into deliverables/<doc_id>/,
        # with the doc-name prefix stripped from the filename.
        doc_dir = orch.run_context.doc_deliverables_dir(doc["id"])
        doc_dir.mkdir(parents=True, exist_ok=True)
        names = run_context_mod.DELIVERABLE_FILENAMES

        ctx_summary = render_context_summary(
            document_id=doc["id"], document_name=doc["name"],
            context_refs=ctx_refs, topics=topics, body_text=ctx_body,
        )
        (doc_dir / names["context_summary"]).write_text(ctx_summary, encoding="utf-8")

        op_summary = render_operative_summary(
            document_id=doc["id"], document_name=doc["name"],
            conventions_by_category=conventions_by_category, findings=findings,
            body_text="Findings are produced by PRACTICE_AUDITOR and STYLE_GUARDIAN in PHASE 5.5 "
                       "against the convention registry. Each finding cites the convention ID and "
                       "the operational reference ID(s).",
            question=question, prior_refusals=_prior_refusals_for(doc),
            prior_orphans=_prior_orphans_for(doc),
        )
        (doc_dir / names["operative_summary"]).write_text(op_summary, encoding="utf-8")

        # AMENDMENT_DRAFTER (skip if we have a fresh payload already on the bus)
        if doc["id"] in existing_amendments:
            amendments_payload = dict(existing_amendments[doc["id"]])
            log_event(_LOG,
                      f"amendment_drafter_reused amendments={len(amendments_payload.get('amendments', []))}",
                      run_id=_run_id_of(orch), phase="6", agent="AMENDMENT_DRAFTER",
                      doc_id=doc["id"])
        else:
            # refine R2: the drafter's only remaining job is WORDING, and wording
            # was measured to subtract. With the arithmetic held identical and only
            # the amendment prose changed, recall moved 2/9 to 5/9, and a true band
            # finding whose comment named no figure scored as a false positive:
            # the deterministic template states "8.8 t/ha against a stated range of
            # 1.6 to 3.4", the model said "exceeds the typical yield range" and
            # named nothing. So the call is OFF by default and the template
            # renderer (ensure_amendments_for_findings) writes every amendment from
            # the typed Findings. --amendment-polish turns the model back on as an
            # optional pass; even then it may not introduce an amendment no typed
            # Finding stands behind.
            #
            # The second effect is operational and was not the reason, but it is
            # real: this call is the run's last load of the 7B producer and its
            # largest prefill, and two local runs died inside it or beside it to a
            # GPU engine timeout. Removing it removes that exposure. It does not
            # remove TDR, which also hit a Phi-3.5 generation with no swap at all.
            upstream_findings = {
                "PRACTICE_AUDITOR": _stamp_source_rule_ids(
                    _items_for(conv_review, "PRACTICE_AUDITOR", doc_id=doc["id"]), convention_registry),
                "STYLE_GUARDIAN": _stamp_source_rule_ids(
                    _items_for(conv_review, "STYLE_GUARDIAN", doc_id=doc["id"]), convention_registry),
                "VERIFIER": _stamp_source_rule_ids(
                    _items_for(audit, "VERIFIER", doc_id=doc["id"]), convention_registry),
                "FACT_CHECKER": _stamp_source_rule_ids(
                    _items_for(audit, "FACT_CHECKER", doc_id=doc["id"]), convention_registry),
                "LEGAL_ANALYST": _stamp_source_rule_ids(
                    _items_for(production, "LEGAL_ANALYST", doc_id=doc["id"]), convention_registry),
            }
            # refine R2: NO amendment is ever taken from the model. The template
            # builds every one of them from the typed Findings below, so an
            # amendment the arithmetic did not produce cannot exist by
            # construction, which is stronger than validating one away afterwards.
            raw_amendments = []
            # console fresh-eyes fix: computed once here (was computed twice in
            # this same function, once for the polish pass and again below for
            # suppress_contradicted_amendments, both from the same doc["text"]/
            # doc["id"]); now also threaded into ensure_amendments_for_findings
            # so a computed amendment's original_text is the document's actual
            # passage, not its bare unit id. The text was already being
            # computed in this scope; it was simply never passed to the one
            # call that needed it to describe the passage it is about.
            _unit_texts = paired_review_mod.unit_texts_for(doc["text"], doc["id"])
            _polish_rules = {c["id"]: c for c in convention_registry.get("conventions", [])}
            if amendment_polish:
                for _agent_name, _group in list(upstream_findings.items()):
                    _group2, _n = await _polish_findings(
                        orch, keys, doc, _group, _polish_rules, _unit_texts,
                        run_objectives, convention_registry)
                    upstream_findings[_agent_name] = _group2
                    if _n:
                        log_event(_LOG, f"amendment_polished count={_n}",
                                  run_id=_run_id_of(orch), phase="6",
                                  agent="AMENDMENT_DRAFTER", doc_id=doc["id"])
            else:
                log_event(_LOG, "amendment_drafter_skipped reason=template_path",
                          run_id=_run_id_of(orch), phase="6",
                          agent="AMENDMENT_DRAFTER", doc_id=doc["id"])
            # structure H3: location, convention_ref and ref_ids are COPIED from
            # the Finding record the amendment rests on, never re-derived from
            # prose. Only amendments whose source finding is unambiguous are
            # touched; the rest pass through exactly as the model wrote them.
            # night W7 b: each Finding carries the name of the agent that produced it
            # (the key of upstream_findings, i.e. the envelope's own agent), so the
            # amendment built from it, and the ontology record captured from that
            # amendment, can name the agent in their provenance. Stamped only where
            # absent; an item that already names its agent is left alone.
            all_upstream = [
                (dict(f, agent=name) if isinstance(f, dict) and not f.get("agent") else f)
                for name, group in upstream_findings.items() for f in group]
            raw_amendments, copied = finding_record.apply_typed_fields(
                raw_amendments, all_upstream)
            # structure H7: a finding Python computed must not depend on a model
            # writing valid JSON. The first scored run had AMENDMENT_DRAFTER fail
            # its contract and four certain arithmetic findings were discarded.
            _amendment_refusals = []
            raw_amendments, synthesised = paired_review_mod.ensure_amendments_for_findings(
                raw_amendments, all_upstream, unit_texts=_unit_texts,
                refusal_sink=_amendment_refusals)
            # Never silently drop a finding this function could not turn into
            # an amendment: a real, irregular finding a model wrote under a
            # field name this pipeline did not yet recognise is not an error
            # to swallow, it is a real irregularity that deserves a record,
            # even the record that the pipeline could not act on it. Posted
            # the same way paired mode's own computed findings already are
            # (backend/model naming the mechanism, never a model's own voice),
            # so GET /findings and the console can surface it, not just this
            # log line. A bus that refuses a post must not take the run down.
            if _amendment_refusals:
                log_event(_LOG, f"amendment_refused count={len(_amendment_refusals)}",
                          run_id=_run_id_of(orch), phase="6", doc_id=doc["id"])
                try:
                    _build_wrapper("AMENDMENT_DRAFTER", orch, keys).post_to_bus(
                        recipient="ORCHESTRATOR", channel="main", msg_type="INFORM",
                        body={"event": "AMENDMENT_REFUSED", "backend": "computed",
                              "model": "python", "item_count": len(_amendment_refusals),
                              "parse_trace": {},
                              "payload": {"agent": "AMENDMENT_DRAFTER", "doc_id": doc["id"],
                                         "items": _amendment_refusals}},
                        constitution_check={"laws_consulted": ["LAW-V"], "result": "RESOLVED",
                                            "resolution": "a real irregular finding could "
                                                          "not be built into an amendment; "
                                                          "refused visibly rather than "
                                                          "dropped"})
                except Exception as e:
                    log_event(_LOG, f"amendment_refusal_post_error error_type={type(e).__name__}",
                              run_id=_run_id_of(orch), phase="6", doc_id=doc["id"])
            # structure H7: arithmetic outranks the model where arithmetic can
            # decide. The control run had the drafter invent a sum violation on a
            # clean document that Python had already computed as correct.
            _vocab = set()
            for _u in _unit_texts.values():
                _vocab |= pairing_map_mod.unit_fields(_u.get("text", ""))
            raw_amendments, _refused = paired_review_mod.suppress_contradicted_amendments(
                raw_amendments, _unit_texts,
                {c["id"]: c for c in convention_registry.get("conventions", [])}, _vocab)
            for _a, _why in _refused:
                log_event(_LOG,
                          f"amendment_refused_contradicted_by_arithmetic "
                          f"convention_ref={_a.get('convention_ref')}",
                          run_id=_run_id_of(orch), phase="6", agent="AMENDMENT_DRAFTER",
                          doc_id=doc["id"])
            if synthesised:
                log_event(_LOG, f"amendments_built_from_findings count={synthesised}",
                          run_id=_run_id_of(orch), phase="6", agent="AMENDMENT_DRAFTER",
                          doc_id=doc["id"])
            if copied:
                log_event(_LOG, f"amendment_fields_copied_from_findings count={copied}",
                          run_id=_run_id_of(orch), phase="6", agent="AMENDMENT_DRAFTER",
                          doc_id=doc["id"])
            # refine R2 follow-up: the contract-violation salvage filter that used to
            # sit here is GONE, not patched. It dropped any amendment missing
            # location, convention_ref or comment, which only ever happened when
            # the DRAFTER returned a broken envelope. No amendment comes from the
            # model now; every one is built by amendment_from_finding, which always
            # sets those three. The filter had nothing left to filter, and it read
            # `result`, the drafter call's return value, which R2 removed. That left
            # a NameError on a line no gate check executed. Found by the first run
            # that got past phase 5.5 on this code, in about thirty seconds, which
            # is the argument for running the thing end to end.
            # R6 / INFRA-044: the comparison with the earlier version travels in the
            # MASTER too, so review_data.json and review_findings.md carry it in its
            # own section. Never an amendment: every such record is ok-verdict.
            _prior_records = [f for f in all_upstream
                              if f.get("relation") in finding_record.PRIOR_RELATIONS
                              and f.get("provenance") == "computed"]
            amendments_payload = {"document_id": doc["id"], "amendments": raw_amendments,
                                  "prior_comparisons": _prior_records,
                                  "prior_refusals": _prior_refusals_for(doc),
                                  "prior_orphans": _prior_orphans_for(doc)}

        # INFRA-042: in the empty-registry state the CONV-* requirement is relaxed (an amendment
        # grounds on >=1 REF-* or >=1 WEB-REF-*); when conventions exist the rule holds unchanged.
        ok_payload, errs = validate_amendment_payload(
            amendments_payload, registry_empty=(n_total_conventions == 0))
        amendments_payload["_validator_errors"] = errs

        # Single canonical master -> on-demand renders (Part XXVII §E / INFRA-033).
        # amendments_payload (also written verbatim as <doc_id>/review_data.json) is the
        # MASTER; the .md and .docx are pure renders DERIVED from it through the one
        # entry point in amendment_render. No render reads amendment content from an
        # independent source, so the three files cannot drift.
        amend = amendment_render.write_amendment_deliverables(
            amendments_payload, deliv_dir=deliv_dir, doc_id=doc["id"],
            document_name=doc["name"], body_text=doc["text"],
            category_for_conv=lambda c: _category_for_conv(c, convention_registry),
        )
        if amend.get("docx_error"):
            print(f"[pipeline] WARN: docx build failed for {doc['name']}: {amend['docx_error']}",
                  file=sys.stderr)
        docx_path = doc_dir / names["amendments_docx"]

        # Per-agent deliverable (the reviewed document record)
        per_agent_path = doc_dir / names["per_agent_deliverable"]
        per_agent_path.write_text(_render_per_agent_md(doc, production, audit, conv_review),
                                  encoding="utf-8")

        # The dict KEYS below are internal identifiers consumed by the redaction stage and
        # OGE capture (by key, not by filename); the VALUES are the BP-16 per-doc subdir paths.
        return doc["id"], {
            "context_summary": str(doc_dir / names["context_summary"]),
            "operative_summary": str(doc_dir / names["operative_summary"]),
            "amendments_json": str(doc_dir / names["amendments_json"]),
            "amendments_md": str(doc_dir / names["amendments_md"]),
            "amendments_docx": str(docx_path) if docx_path.exists() else None,
            "per_agent_deliverable": str(per_agent_path),
            "validator_errors": errs,
            "amendment_count": len(amendments_payload.get("amendments", [])),
            "prior_comparison_count": len(amendments_payload.get("prior_comparisons") or []),
            "prior_absent_count": sum(
                1 for f in (amendments_payload.get("prior_comparisons") or [])
                if f.get("relation") == "absent_since_prior"),
        }

    for doc_id, info in await _gather_docs(op_docs, _process_doc, max_concurrent_docs):
        deliverables[doc_id] = info
    return deliverables


def _prior_refusals_for(doc):
    """The comparisons the prior-version step refused, per unit, read from the
    pairing map phase 5.5 left on the document (R6). Empty when no earlier version
    was declared, so every existing caller renders as before."""
    out = []
    for entry in ((doc.get("_pairing") or {}).get("units") or []):
        for r in ((entry.get("prior_comparisons") or {}).get("refused") or []):
            out.append({"unit_id": entry.get("unit_id"), "label": r.get("label", ""),
                        "reason": r.get("reason", "")})
    return out


def _prior_orphans_for(doc):
    """Earlier-version terms whose heading has no counterpart in this document (R6)."""
    return list((doc.get("_pairing") or {}).get("prior_orphans") or [])


def _category_for_conv(conv_id, registry):
    if not conv_id:
        return None
    for c in registry.get("conventions", []):
        if c.get("id") == conv_id:
            return c.get("category")
    return None


# ---------- EDITORIAL review house (INFRA-039) ----------------------------------------------
# Privacy-free. Imports NOTHING from sensitivity_layer and reuses no privacy mechanic.
# The single EDITOR_CLERK agent gives an ADVISORY senior editorial review of the assembled
# deliverable. It NEVER masks/detects/scrubs, NEVER modifies the master, and NEVER gates
# shipping. No name here contains "redact" in any spelling.

_EDITORIAL_VALID_VERDICTS = ("sound", "concern", "serious_concern")


def _is_editorial_observation(it) -> bool:
    """STRUCTURAL detection (INFRA-039 borrowed doctrine): an editorial observation is
    recognized by carrying ref + verdict + rationale, regardless of any free-text label
    (e.g. `kind`) the model attaches. The verdict VALUE is validated separately."""
    if not isinstance(it, dict):
        return False
    has_ref = bool(str(it.get("ref", "")).strip())
    has_verdict = bool(str(it.get("verdict", "")).strip())
    has_rationale = bool(str(it.get("rationale", "")).strip())
    return has_ref and has_verdict and has_rationale


def _post_editorial(orch, doc_id, event, body):
    """Post an auditable editorial-review event to the run bus (advisory; editorial house)."""
    orch._post_orchestrator(
        recipient="OPERATOR", channel="main", msg_type="INFORM",
        body={"event": event, "document_id": doc_id, **body},
        constitution_check={"laws_consulted": ["LAW-V"], "result": "RESOLVED",
                            "resolution": "advisory editorial review of the assembled deliverable"})


def _persist_rank_output(run_ctx, doc_id, name, payload) -> "str | None":
    """Persist a rank's (or the consolidated board's) output on EVERY path (normal,
    all-sound, failed-parse, skipped-sensitive), PER RANK, so the board is diagnosable
    from disk (INFRA-040 borrowed doctrine: raw persisted on every path AND per rank).
    Writes into the run audit dir under editorial/ as <name>_<doc_id>.json. Best-effort;
    never raises."""
    if run_ctx is None:
        return None
    try:
        out_dir = run_ctx.audit_dir() / "editorial"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{name}_{doc_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)
    except Exception:
        return None


# ---------- editorial review BOARD: the bounded rank-to-rank loop (INFRA-040 Build B) -------
# Privacy-free intra-phase control flow on the run bus ONLY. It does NOT use the operator-
# escalation ESCALATE path (orchestrator.escalate_to_operator), which blocks on a human; the
# board never blocks on the operator. Dispatch is purely registry-driven (claude_api ranks ->
# call_claude, openai_api ranks -> call_gpt); no rank name is special-cased anywhere here.

# Ascending authority. Bottom three are Claude, top three GPT (set in the registry).
_EDITORIAL_RANKS = ("EDITOR_CLERK", "EDITOR_HEAD_OF_UNIT", "EDITOR_HEAD_OF_SECTION",
                    "EDITOR_HEAD_OF_DEPARTMENT", "EDITOR_DEPUTY_DG", "EDITOR_DG")

# Per-rank mandate (widening in-house scope; NO web at ANY rank, including DG).
_RANK_MANDATE = {
    "EDITOR_CLERK": "editorial review of drafting and soundness at provision-and-neighbors scope",
    "EDITOR_HEAD_OF_UNIT": "editorial review of drafting and soundness at provision-and-neighbors scope",
    "EDITOR_HEAD_OF_SECTION": "editorial review of drafting and soundness at provision-and-neighbors scope",
    "EDITOR_HEAD_OF_DEPARTMENT": "whole-deliverable coherence",
    "EDITOR_DEPUTY_DG": "the necessity and proportionality of the deliverable's content",
    "EDITOR_DG": "the existential question: do we need this content at all?",
}

# Operator tunables (config/editorial_board.json); defaults used if the file is absent.
_EDITORIAL_BOARD_DEFAULTS = {"max_rounds": 5, "confidence_threshold": 0.7,
                             "out_of_mandate_trigger": True, "max_tokens": 8192}

# Categorical model confidence -> numeric, so the operator's numeric threshold applies.
_CONFIDENCE_LABELS = {"CONFIDENT": 1.0, "UNCERTAIN": 0.4}


def _resolve_editorial_board(project_root: Path) -> dict:
    """Load config/editorial_board.json (operator tunables), mirroring _resolve_review_scope.
    Falls back to _EDITORIAL_BOARD_DEFAULTS for any missing/invalid key (no silent surprise:
    the defaults match the ratified INFRA-040 values)."""
    path = project_root / "config" / "editorial_board.json"
    cfg = dict(_EDITORIAL_BOARD_DEFAULTS)
    if not path.exists():
        return cfg
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return cfg
    for k in _EDITORIAL_BOARD_DEFAULTS:
        if k in data:
            cfg[k] = data[k]
    return cfg


def _confidence_value(it) -> float:
    """Numeric confidence for an observation. Accepts a number, a numeric string, or the
    categorical labels (CONFIDENT|UNCERTAIN). Unknown/missing -> treated as confident (1.0)
    so the board does not over-escalate on a malformed confidence (parsimony)."""
    raw = it.get("confidence")
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return _CONFIDENCE_LABELS.get(s.upper(), 1.0)


def _observation_triggers_escalation(observations, tunables):
    """The TWO ratified summon triggers (and ONLY these): (a) any observation's confidence
    is below the operator threshold, or (b) an observation raises an explicit out_of_mandate
    flag (only when the operator enables that trigger). Returns (triggered, reason)."""
    thr = float(tunables.get("confidence_threshold", 0.7))
    for it in observations:
        if _confidence_value(it) < thr:
            return True, f"confidence<{thr}"
    if tunables.get("out_of_mandate_trigger", True):
        for it in observations:
            if bool(it.get("out_of_mandate")):
                return True, "out_of_mandate"
    return False, ""


def _rank_run_objectives(rank, prior_obs):
    """Per-rank prompt. The entry rank reviews fresh; a summoned higher rank reads the
    accumulated lower-rank observation(s) + rationale (it does NOT recompute from scratch)
    and confirms / overrides / escalates. Its verdict governs; the lower rank is preserved."""
    mandate = _RANK_MANDATE[rank]
    base = ("Emit ONE observation per item, each with: ref (what you comment on), verdict "
            "(EXACTLY one of 'sound', 'concern', 'serious_concern'), rationale (your editorial "
            "reasoning in prose), and confidence (CONFIDENT or UNCERTAIN). If a matter is "
            "outside your mandate, additionally set out_of_mandate true on that item. If you "
            "have no concerns, emit one item with verdict 'sound'. You ANNOTATE only; you do "
            "NOT modify the deliverable and you do NOT mask, detect, or scrub anything.")
    if not prior_obs:
        return (f"You are {rank}, the entry rank of the editorial review board. Your mandate: "
                f"{mandate}. Conduct a senior editorial review of the assembled deliverable's "
                f"SUBSTANCE and DRAFTING. " + base)
    prior_txt = "\n".join(
        f"- [{o.get('rank')}] {o.get('ref')}: verdict={o.get('verdict')} ({o.get('rationale')})"
        for o in prior_obs)
    return (f"You are {rank}, a senior rank of the editorial review board, summoned on "
            f"escalation. Your mandate: {mandate}. A lower rank escalated; read their "
            f"observation(s) and rationale below and CONFIRM, OVERRIDE, or escalate further. "
            f"Your verdict GOVERNS the outcome; the lower rank's observation is preserved, not "
            f"deleted.\nPRIOR OBSERVATIONS (accumulating state, lowest rank first):\n"
            f"{prior_txt}\n\n" + base)


def _dispatch_rank(orch, keys, rank, doc, master, prior_passes, run_ctx, convention_registry,
                   max_tokens):
    """Dispatch ONE rank (registry-driven backend; no name special-casing), persist its raw
    output per rank on every path, and run the stage-1 silent-pass guard + structural
    detection. Returns (ok, observations, raw_path, error). The output budget `max_tokens` is
    the board tunable resolved from config/editorial_board.json (NOT a hardcoded value): upper
    ranks re-review ALL accumulated lower-rank observations, so their output grows with rank
    and the stage-1 single-reviewer budget truncated them (INFRA-040 Build F). If a rank STILL
    exceeds this ceiling, its output truncates and the guard below fires a LOUD failure -- the
    larger budget reduces truncation, it does NOT mask a genuine one as success."""
    prior_obs = [{"rank": p["rank"], "ref": o.get("ref"), "verdict": o.get("verdict"),
                  "rationale": o.get("rationale"), "confidence": o.get("confidence")}
                 for p in prior_passes for o in p["observations"]]
    wrapper = _build_wrapper(rank, orch, keys)
    result = wrapper.run_task(
        work_payload={"task": "editorial_review", "document_id": doc["id"],
                      "document_name": doc["name"],
                      "amendments_master": master.get("amendments", []),
                      "prior_observations": prior_obs},
        run_objectives=_rank_run_objectives(rank, prior_obs),
        channel="main", max_tokens=max_tokens, convention_registry=convention_registry,
        # productization STEP 4: cost dimensions. The editorial board is a
        # per-document phase; doc["id"] is the same id used for _persist_rank_
        # output just below.
        phase="editorial_board", doc_id=str(doc["id"]))
    raw_path = _persist_rank_output(run_ctx, doc["id"], rank, {
        "state": "RAW", "rank": rank, "ok": result.get("ok"), "error": result.get("error"),
        "parsed": result.get("parsed"), "raw_text": result.get("raw_text", "")})
    items = (decode_items(result.get("parsed"))
             if (result.get("ok") and is_envelope(result.get("parsed"))) else [])
    obs = [it for it in items if _is_editorial_observation(it)]
    valid = bool(obs) and all(
        str(it.get("verdict", "")).strip().lower() in _EDITORIAL_VALID_VERDICTS for it in obs)
    ok = bool(result.get("ok") and valid)
    error = None if ok else (result.get("error") or "no valid editorial observation")
    return ok, obs, raw_path, error


def _consolidate_board(passes):
    """Group every observation by ref across all ranks that ran. AUTHORITY BY RANK: the
    highest rank that touched a ref GOVERNS it (passes are appended lowest-first, so the last
    entry in a ref's chain is the governing one). Lower-rank observations are RETAINED as
    'superseded', never dropped (conserve-or-surface). Returns a list, one entry per ref."""
    by_ref, order = {}, []
    for p in passes:
        for o in p["observations"]:
            ref = str(o.get("ref", ""))
            rec = {"rank": p["rank"], "verdict": o.get("verdict"),
                   "verdict_l": str(o.get("verdict", "")).strip().lower(),
                   "rationale": o.get("rationale"), "confidence": o.get("confidence")}
            if ref not in by_ref:
                by_ref[ref] = []
                order.append(ref)
            by_ref[ref].append(rec)
    consolidated = []
    for ref in order:
        chain = by_ref[ref]
        consolidated.append({"ref": ref, "governing": chain[-1],
                             "superseded": chain[:-1], "chain": chain})
    return consolidated


def _append_board_to_deliverable(info, consolidated):
    """Append the advisory editorial-board section to the per-agent reviewed_document.md,
    grouping observations by ref: per ref it shows the GOVERNING verdict and the rank that
    set it, plus any SUPERSEDED lower-rank verdict (visible, not dropped). Does NOT touch the
    amendments master (advisory annotation only). Best-effort."""
    p = info.get("per_agent_deliverable")
    if not p or not Path(p).exists():
        return
    try:
        lines = ["", "## Editorial review board (advisory)", ""]
        if not consolidated:
            lines.append("_(no observations)_")
        for c in consolidated:
            g = c["governing"]
            lines.append(f"- **{g['verdict']}** [{c['ref']}] (governing rank: {g['rank']})")
            lines.append(f"    - {g['rank']}: {g['rationale']}")
            for s in c["superseded"]:
                lines.append(f"    - (superseded) {s['rank']} -> {s['verdict']}: {s['rationale']}")
        with Path(p).open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except Exception:
        pass


def phase_6_5_editorial_review(orch, keys, op_docs, deliverables, run_ctx,
                               convention_registry, *, run_is_non_sensitive,
                               board_tunables=None):
    """Phase 6.5 (EXECUTION ORDER: immediately after phase_6_synthesis, before phase 7 and
    before the phase 9 privacy scrub). The editorial review BOARD (INFRA-040) runs a BOUNDED
    rank-to-rank escalation loop per deliverable over the CLEAN, pre-scrub master at
    <run>/deliverables/<doc_id>/review_data.json. The board ANNOTATES only: it never modifies
    the master and never gates shipping.

    THE BOUNDED LOOP (the one new mechanism; intra-phase, on the run bus ONLY -- it does NOT
    use orchestrator.escalate_to_operator, which blocks on a human):
      - PARSIMONY: start at EDITOR_CLERK. A higher rank is summoned ONLY when the current
        rank's observation triggers escalation -- (a) confidence below the operator threshold
        or (b) an explicit out_of_mandate flag. Otherwise the call resolves at the current
        rank and the loop stops (most resolve at the clerk).
      - ACCUMULATING STATE: a summoned higher rank reads the lower rank's observation +
        rationale (passed forward and posted to the bus), it does not recompute from scratch.
      - AUTHORITY BY RANK: the higher rank's verdict GOVERNS; the lower rank's observation is
        preserved, not deleted (conserve-or-surface). Family split is decorrelation, not
        authority -- dispatch is purely registry-driven (no name special-casing).
      - BOUNDED STOP: never exceed max_rounds climbs; after the cap a TERMINAL decision is
        rendered at the highest rank reached (no infinite climb). EDITOR_DG's existential
        question fires only if DG is actually summoned.

    Option-B sensitive-run gate: phase 6.5 is an API egress point for pre-scrub content (and
    the top three ranks add GPT egress), so the WHOLE board runs ONLY when the run is declared
    non-sensitive (the --no-redaction-override waiver is in force). Otherwise the whole board
    is SKIPPED and the skip is recorded LOUDLY. Sensitive-mode editorial review is deferred
    until the LAW-IV masking layer is activated.

    Safety doctrine (carried per rank): a rank whose output does not parse into items each
    carrying a VALID verdict (sound|concern|serious_concern) is a LOUD 'editorial review
    failed' (advisory, so it does NOT halt the pipeline and does NOT withhold the deliverable).
    Raw output is persisted on EVERY path AND per rank."""
    tunables = board_tunables or dict(_EDITORIAL_BOARD_DEFAULTS)
    max_rounds = int(tunables.get("max_rounds", 5))
    board_max_tokens = int(tunables.get("max_tokens", 8192))  # rank-aware output budget (config)
    summary = {}
    if not run_is_non_sensitive:
        note = "editorial review skipped: sensitive run, awaiting masking-layer activation"
        for doc in op_docs:
            _post_editorial(orch, doc["id"], "EDITORIAL_SKIPPED",
                            {"reason": "sensitive_run", "note": note})
            raw_path = _persist_rank_output(run_ctx, doc["id"], "BOARD",
                                            {"state": "SKIPPED", "reason": "sensitive_run", "note": note})
            summary[doc["id"]] = {"state": "SKIPPED", "reason": "sensitive_run",
                                  "note": note, "raw_output_path": raw_path}
        return summary
    for doc in op_docs:
        info = deliverables.get(doc["id"]) or {}
        master_path = info.get("amendments_json")
        if not master_path or not Path(master_path).exists():
            summary[doc["id"]] = {"state": "NO_DELIVERABLE"}
            continue
        try:
            # The CLEAN, pre-scrub master (phase 9 has not run yet).
            master = json.loads(Path(master_path).read_text(encoding="utf-8"))
        except Exception:
            summary[doc["id"]] = {"state": "NO_DELIVERABLE"}
            continue

        passes = []            # accumulating state: one record per rank that ran (lowest-first)
        rounds = 0             # climbs performed; HARD-bounded by max_rounds
        rank_idx = 0
        failed = None
        terminal_cap = False
        while True:
            rank = _EDITORIAL_RANKS[rank_idx]
            ok, obs, raw_path, error = _dispatch_rank(
                orch, keys, rank, doc, master, passes, run_ctx, convention_registry,
                board_max_tokens)
            if not ok:
                # LOUD failure at this rank: advisory, never halts/withholds. Earlier ranks'
                # observations remain on the bus (conserve-or-surface).
                _post_editorial(orch, doc["id"], "EDITORIAL_FAILED",
                                {"rank": rank, "round": rounds,
                                 "reason": error, "raw_output_path": raw_path})
                failed = {"rank": rank, "reason": error or "no_valid_observation",
                          "raw_output_path": raw_path}
                break
            all_sound = all(str(it.get("verdict", "")).strip().lower() == "sound" for it in obs)
            _post_editorial(orch, doc["id"], "EDITORIAL_REVIEW",
                            {"rank": rank, "round": rounds, "observations": len(obs),
                             "all_sound": all_sound,
                             "verdicts": [it.get("verdict") for it in obs]})
            passes.append({"rank": rank, "round": rounds, "observations": obs,
                           "raw_output_path": raw_path})
            trig, reason = _observation_triggers_escalation(obs, tunables)
            if not trig:
                break                          # resolved at this rank (parsimony)
            if rounds >= max_rounds:
                terminal_cap = True            # bounded stop: terminal at highest reached
                break
            if rank_idx >= len(_EDITORIAL_RANKS) - 1:
                break                          # DG reached; cannot climb further
            rank_idx += 1
            rounds += 1                        # one climb (summon the next rank)

        consolidated = _consolidate_board(passes)
        board_raw = _persist_rank_output(run_ctx, doc["id"], "BOARD", {
            "state": "FAILED" if failed else "REVIEWED",
            "rounds": rounds, "ranks_run": [p["rank"] for p in passes],
            "terminal_cap_reached": terminal_cap, "failed": failed,
            "consolidated": consolidated})
        if failed:
            summary[doc["id"]] = {"state": "FAILED", "reason": failed["reason"],
                                  "rank": failed["rank"], "ranks_run": [p["rank"] for p in passes],
                                  "rounds": rounds, "raw_output_path": board_raw}
            continue
        if not passes:
            summary[doc["id"]] = {"state": "FAILED", "reason": "no_rank_ran",
                                  "raw_output_path": board_raw}
            continue
        governing_rank = passes[-1]["rank"]
        all_sound = bool(consolidated) and all(
            c["governing"]["verdict_l"] == "sound" for c in consolidated)
        _append_board_to_deliverable(info, consolidated)  # advisory; master untouched
        summary[doc["id"]] = {"state": "REVIEWED",
                              "ranks_run": [p["rank"] for p in passes],
                              "governing_rank": governing_rank, "rounds": rounds,
                              "escalated": rounds > 0, "terminal_cap_reached": terminal_cap,
                              "observations": sum(len(p["observations"]) for p in passes),
                              "all_sound": all_sound, "raw_output_path": board_raw}
    return summary


def _render_per_agent_md(doc, production, audit, conv_review):
    lines = [f"# {doc['name']}: per-agent deliverable", "",
             f"- generated: {datetime.now(timezone.utc).isoformat()}"]
    all_results = (production + audit + conv_review)
    by_agent = {}
    for r in all_results:
        if r.get("doc_id") == doc["id"]:
            by_agent.setdefault(r["agent"], []).append(r)
    for agent in ("PROCESSOR", "SPEECH_ACT_TAGGER", "LEGAL_ANALYST",
                  "VERIFIER", "FACT_CHECKER",
                  "PRACTICE_AUDITOR", "STYLE_GUARDIAN"):
        lines.append(f"\n## {agent}")
        if agent not in by_agent:
            lines.append("_(agent did not run)_"); continue
        for r in by_agent[agent]:
            if not r.get("ok"):
                lines.append(f"_(failed: {r.get('error')})_"); continue
            lines.append("```json")
            lines.append(json.dumps(r.get("parsed"), indent=2, ensure_ascii=False))
            lines.append("```")
    return "\n".join(lines)


# ---------- BOOT helpers --------------------------------------------------------------------

def _build_reference_index(project_root, ctx_docs, op_docs, conv_registry, run_context=None):
    # Per-run, regenerated, disposable (Part XXVII §A): write into the current
    # run's audit/ folder when a run context is given; else legacy output/audit.
    index_path = run_context.reference_index_path() if run_context is not None else None
    idx_path = index_path or (project_root / "output" / "audit" / "reference_index.json")
    if idx_path.exists(): idx_path.unlink()
    idx = ReferenceIndex.open(project_root, index_path=index_path)
    for d in ctx_docs:
        idx.index_document(input_type="context", document_id=d["id"],
                           document_name=d["name"], text=d["text"], max_paragraphs=120)
    for d in op_docs:
        idx.index_document(input_type="operational", document_id=d["id"],
                           document_name=d["name"], text=d["text"], max_paragraphs=200)
    for c in conv_registry.get("conventions", []):
        idx.add(input_type="convention", document_id=c.get("source_file", "conventions"),
                document_name=c.get("source_file", "conventions"),
                location={"page": 1, "paragraph": c.get("id", "?"),
                          "sentence": 1, "char_start": 0, "char_end": 0},
                text_excerpt=c.get("rule", "")[:200])
    idx.save()
    return idx


# ---------- escalation handler --------------------------------------------------------------

def _interactive_handler(topic, payload):
    print(f"\n=== OPERATOR ESCALATION: {topic} ===", file=sys.stderr)
    print(json.dumps(payload, indent=2, ensure_ascii=False)[:4000], file=sys.stderr)
    try:
        decision = input("Decision (APPROVE / DENY / DEFER): ").strip()
        rationale = input("Rationale: ").strip()
    except EOFError:
        decision, rationale = "DEFERRED", "no input available"
    return OperatorDecision(decision=decision or "DEFERRED", rationale=rationale or "")


# productization STEP 6: file-backed operator channel. --operator-channel file (only
# meaningful together with --non-interactive; see main()'s wiring) installs
# _make_file_operator_handler(run_ctx)'s closure in place of _interactive_handler /
# None, so a server-driven run (which always passes --non-interactive) can still
# surface a governed decision to a human through the filesystem instead of a
# terminal prompt. This handler NEVER evaluates the decision itself: evaluation
# stays entirely in model_registry.enforce_current_models and
# constitution_guard._is_approved (both repaired in STEP 1a/1b to accept an
# OperatorDecision or a bare string). It only WRITES the pending question, WAITS
# (polling, mirroring block_gate.BlockHandle's wait(timeout) shape) for a decision
# file, and returns whatever decision it finds (or DEFERRED on timeout) verbatim.
def _make_file_operator_handler(run_ctx):
    import os as _os
    pending_path = run_ctx.audit_dir() / "pending_approval.json"
    decision_path = run_ctx.audit_dir() / "approval_decision.json"
    wait_s = float(_os.environ.get("SHIMMER_APPROVAL_WAIT_S", "3600") or 3600)
    poll_s = 2.0

    def _handler(topic, payload):
        pending_path.parent.mkdir(parents=True, exist_ok=True)
        # A stale decision file from an earlier topic must never be read as this
        # topic's answer; each escalation gets a fresh pending/decision pair.
        try:
            decision_path.unlink()
        except FileNotFoundError:
            pass
        asked_at = datetime.now(timezone.utc).isoformat()
        pending_path.write_text(json.dumps(
            {"topic": topic, "payload": payload, "asked_at": asked_at},
            indent=2, ensure_ascii=False), encoding="utf-8")
        # The existing ESCALATE bus message shape (orchestrator.py::escalate_to_operator
        # posts the same shape); posted here too so the file channel and the interactive
        # channel both leave the same audit trail on the bus.
        try:
            _bus = MessageBus.open(run_ctx.bus_path())
            _bus.post(recipient="OPERATOR", channel="escalation", msg_type="ESCALATE",
                      body={"topic": topic, "payload": payload},
                      constitution_check={"laws_consulted": ["LAW-0"], "result": "UNRESOLVED",
                                          "resolution": "operator must decide (file channel)"})
        except Exception:
            pass  # the bus post is a courtesy trail; never block the wait on it.
        # [progress] contract (W5): append a key, never alter the existing ones.
        _emit_progress(status="running", awaiting_approval=1)
        deadline = time.monotonic() + wait_s
        while time.monotonic() < deadline:
            if decision_path.exists():
                try:
                    rec = json.loads(decision_path.read_text(encoding="utf-8"))
                    return OperatorDecision(
                        decision=str(rec.get("decision", "")).strip() or "DEFERRED",
                        rationale=str(rec.get("rationale", "")),
                        timestamp=str(rec.get("decided_at") or datetime.now(timezone.utc).isoformat()))
                except (json.JSONDecodeError, OSError):
                    pass  # a decision file mid-write; poll again rather than fail the run.
            time.sleep(min(poll_s, max(0.0, deadline - time.monotonic())) or poll_s)
        return OperatorDecision(decision="DEFERRED", rationale="no decision within wait")

    return _handler


def _resolve_operator_handler(args, run_ctx):
    """The single place that decides which operator handler a governed-decision
    call site gets: --operator-channel file (only meaningful together with
    --non-interactive, per the flag's own help text) installs the file-backed
    handler; every other combination (interactive, or --operator-channel none)
    preserves the exact behavior before this step: None under --non-interactive
    (denial stays unconditional), _interactive_handler otherwise."""
    if args.non_interactive and args.operator_channel == "file":
        return _make_file_operator_handler(run_ctx)
    return None if args.non_interactive else _interactive_handler


# ---------- main ----------------------------------------------------------------------------

def _cost_projection(num_op_docs, num_ctx_docs):
    # Editorial review board (INFRA-040): WORST-CASE ceiling = all six ranks fire on every
    # operational deliverable, split by family 3 Claude (EDITOR_CLERK / EDITOR_HEAD_OF_UNIT /
    # EDITOR_HEAD_OF_SECTION) + 3 GPT (EDITOR_HEAD_OF_DEPARTMENT / EDITOR_DEPUTY_DG /
    # EDITOR_DG) per doc. This is a CEILING, deliberately an over-count: the EXPECTED case is
    # far lower because the loop is parsimonious -- most runs resolve at EDITOR_CLERK only
    # (one Claude call/doc, zero GPT ranks). On a sensitive run the whole board is skipped, so
    # its real contribution is 0. We project the ceiling so the estimate never under-counts.
    board_claude_calls = 3 * num_op_docs   # WORST CASE: CLERK + HEAD_OF_UNIT + HEAD_OF_SECTION
    board_gpt_calls = 3 * num_op_docs      # WORST CASE: HEAD_OF_DEPARTMENT + DEPUTY_DG + DG
    claude_calls = (len(PRODUCTION_AGENTS_PER_DOC) * num_op_docs
                    + len(PRODUCTION_AGENTS_CORPUS_LEVEL)
                    + len(CONVENTION_REVIEW_AGENTS) * num_op_docs  # style_guardian via Claude
                    + num_op_docs  # AMENDMENT_DRAFTER
                    + board_claude_calls)  # editorial board, Claude ranks (worst-case ceiling)
    gpt_calls = ((len(AUDIT_AGENTS_PER_DOC) + 1) * num_op_docs  # +1 for PRACTICE_AUDITOR (gpt)
                 + board_gpt_calls)  # editorial board, GPT ranks (worst-case ceiling)
    return estimate_cost(claude_calls=claude_calls, claude_in=5500, claude_out=1800,
                         gpt_calls=gpt_calls, gpt_in=5500, gpt_out=1500)


def _build_arg_parser() -> argparse.ArgumentParser:
    """The pipeline's whole CLI surface, built here instead of inline in main()
    so the verify gate can construct and inspect it without starting a run
    (productization STEP 8d).

    Every option string must be registered exactly ONCE: argparse raises
    argparse.ArgumentError("conflicting option string") at CONSTRUCTION time on
    a duplicate, which makes main() unstartable for every invocation.
    --operator-channel was registered twice before STEP 8d (once here, once at
    the end of the list) and nothing caught it, because no gate check built the
    parser. check_115_pipeline_parser_builds_every_flag_once now does."""
    parser = argparse.ArgumentParser(description="Project Shimmer pipeline")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--skip-confirmation", action="store_true")
    parser.add_argument("--max-docs", type=int, default=0)
    parser.add_argument("--reset-bus", action="store_true")
    parser.add_argument("--reset-cost", action="store_true")
    parser.add_argument("--run-objectives", default="")
    parser.add_argument("--save-snapshot", metavar="NAME")
    parser.add_argument("--load-snapshot", metavar="NAME")
    parser.add_argument("--reset-snapshot", action="store_true")
    parser.add_argument("--list-snapshots", action="store_true")
    parser.add_argument("--overwrite-snapshot", action="store_true",
                        help="allow --save-snapshot to overwrite existing")
    parser.add_argument("--skip-model-check", action="store_true",
                        help="skip the live deprecated-model gate (e.g. offline runs)")
    parser.add_argument("--no-redaction-override", action="store_true",
                        help="per-run waiver: declare THIS run non-sensitive and run with NO "
                             "redaction (required to proceed when the Qwen backend is unavailable; "
                             "each use is logged to the governance ledger)")
    parser.add_argument("--sensitivity-layer-inactive-override", action="store_true",
                        help="per-run override: the FULL LAW-IV sensitivity layer is built and "
                             "wired (INFRA-041) but not activated (LAYER_ACTIVE is False); "
                             "declare THIS run non-sensitive to proceed with it inactive. Each "
                             "use is logged to the governance ledger.")
    parser.add_argument("--amendment-polish", action="store_true",
                        help="refine R2: run the AMENDMENT_DRAFTER model as an optional wording "
                             "pass. OFF by default. Every amendment is otherwise rendered "
                             "deterministically from the typed Finding records, because the "
                             "model's wording was measured to LOSE findings the arithmetic had "
                             "already got right (recall 2/9 with the model's sentences against "
                             "5/9 with figure-bearing ones, same arithmetic). Even with this "
                             "flag the model may not introduce an amendment that no typed "
                             "Finding stands behind.")
    parser.add_argument("--output-dir", default=None,
                        help="write this run's output INTO the given folder (used as the run "
                             "folder verbatim) instead of auto-creating output/runs/<stamp>__<id>/. "
                             "Lets a caller (e.g. the M3 server) pin and locate the run folder. "
                             "Omit for the default per-run folder, exactly as before.")
    parser.add_argument("--mode", choices=["standalone", "integrated"], default="standalone",
                        help="M2: declare run intent. standalone (default) is base Shimmer: the "
                             "corpus_ingest promotion-exclusion hook is skipped entirely. integrated "
                             "is an ingested-corpus run: grounding files listed in the sidecar are "
                             "excluded from operational promotion. Omitting the flag preserves base "
                             "behavior.")
    parser.add_argument("--task", choices=["review", "draft"], default="review",
                        help="task mode. review (default): review an existing document. "
                             "draft: generate a memo from --question (phase 0), then review it "
                             "exactly as an operator-provided document.")
    parser.add_argument("--question", default="",
                        help="the question or brief for --task draft (required there); for "
                             "--task review an optional framing question that is appended to "
                             "the run objectives of every agent call and echoed in "
                             "document_summary.md and _run_summary.md; never parsed by the code.")
    parser.add_argument("--infer-roles", action="store_true",
                        help="enable tier 4 of the document role resolution chain (content "
                             "inference). A guarded STUB today: it logs 'tier 4 not enabled' "
                             "and leaves unresolved files to the date cutoff. Off by default to "
                             "avoid nondeterministic classification on production runs.")
    parser.add_argument("--max-concurrent-docs", type=int, default=4,
                        help="BP-5: how many operational documents to process concurrently within "
                             "the per-doc content phases (3-4, 5, 5.5, 6). Default 4 is safe for a "
                             "single-key Claude rate limit; raise it if your limits allow, lower to "
                             "1 for fully serial behavior. Redaction and the editorial board stay serial.")
    parser.add_argument("--backend-profile", choices=["cloud", "local"], default=None,
                        help="backend profile. cloud (default): agents use their configured "
                             "cloud backends (claude_api, openai_api). local: all inference "
                             "runs on local models (local_producer for claude_api agents, "
                             "local_auditor for openai_api agents). REDACTOR stays qwen_local "
                             "in both profiles. Also settable via SHIMMER_BACKEND_PROFILE env var; "
                             "the CLI flag takes precedence.")
    parser.add_argument("--review-mode", choices=["wide", "paired"], default=None,
                        help="structure H5. wide: convention review sends the whole "
                             "document and the whole registry in one call per agent, "
                             "exactly as before. paired: one narrow call per (unit, rule) "
                             "pair chosen by the pairing map, with every sum, product and "
                             "ratio computed in Python and the model asked only whether "
                             "the discrepancy is material. Default: paired on the local "
                             "profile, wide on the cloud profile, because the cloud "
                             "profile's paid baseline has not validated paired yet.")
    parser.add_argument("--pairs-per-unit", type=int, default=None,
                        help="structure H5: cap the (unit, rule) pairs reviewed per unit "
                             "in paired mode. Pairs dropped by the cap are counted and "
                             "logged, never silently skipped. Default: no cap.")
    parser.add_argument("--operator-channel", choices=["none", "file"], default="none",
                        help="productization STEP 6: how a governed decision (model approval, "
                             "constitution amendment) reaches a human on a --non-interactive run. "
                             "none (default): no channel; --non-interactive keeps the operator "
                             "handler None exactly as before, so a denial stays unconditional. "
                             "file: only meaningful together with --non-interactive; installs a "
                             "file-backed handler (see _make_file_operator_handler) that writes "
                             "<run>/audit/pending_approval.json, posts the existing ESCALATE bus "
                             "message, and waits up to SHIMMER_APPROVAL_WAIT_S (default 3600) for "
                             "<run>/audit/approval_decision.json. It never evaluates the decision "
                             "itself (that stays in enforce_current_models / "
                             "constitution_guard._is_approved); it only relays what a human wrote.")
    return parser


def main(argv=None):
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    args.backend_profile = apply_backend_profile(args.backend_profile)
    args.review_mode = resolve_review_mode(args.review_mode, args.backend_profile)

    # M2: announce the declared mode so the run log records operator intent.
    print(f"[pipeline] mode: {args.mode}", file=sys.stderr, flush=True)

    # Snapshot shortcuts: take action and exit.
    if args.list_snapshots:
        for o in list_snapshots(ROOT):
            print(f"{o['name']:30s} saved_at={o.get('saved_at', '?')} files={len(o.get('files', []))}")
        return 0
    if args.reset_snapshot:
        summary = reset_snapshot(ROOT)
        print("[snapshot] reset:", json.dumps(summary, indent=2))
        return 0
    if args.load_snapshot:
        # Thread the operator handler so the amendment tripwire can prompt for
        # approval if a snapshot's constitution would change existing amendments.
        summary = load_snapshot(
            ROOT, args.load_snapshot,
            operator_handler=(None if args.non_interactive else _interactive_handler),
            interactive=not args.non_interactive,
        )
        print(f"[snapshot] loaded {args.load_snapshot!r}:", json.dumps(summary, indent=2))
        return 0
    if args.save_snapshot:
        try:
            target = save_snapshot(ROOT, args.save_snapshot, overwrite=args.overwrite_snapshot)
        except FileExistsError as e:
            print(f"[snapshot] {e}", file=sys.stderr); return 2
        print(f"[snapshot] saved to {target}")
        return 0

    # Per-run output isolation (Part XXVII §A): every run gets its own folder
    # output/runs/<UTC-timestamp>__<run-id>/. Two runs never overwrite each other.
    # Durable/protected assets live under durable/ and are never written here.
    # --output-dir (M3): a caller can pin the run folder so it knows where results
    # land (the server passes output/runs/<run_id>/ and serves from it). When the
    # flag is absent the behavior is exactly as before (auto-created run folder).
    if args.output_dir:
        run_ctx = run_context_mod.for_run_dir(ROOT, args.output_dir).ensure()
    else:
        run_ctx = run_context_mod.create_run(ROOT)
    try:
        _run_dir_shown = run_ctx.run_dir.relative_to(ROOT)
    except ValueError:
        _run_dir_shown = run_ctx.run_dir
    print(f"[pipeline] run folder: {_run_dir_shown}", file=sys.stderr)

    # Meta-law tripwire (INFRA-043). (1) genesis integrity: surface a tampered immutable core
    # (genesis Part I must mirror the guarded constitution seed_laws). Surfaced and logged, never a
    # hard block of the operator (the operator owns genesis.md; the verify gate asserts the invariant).
    gi = constitution_guard.check_genesis_integrity(ROOT)
    if not gi["ok"]:
        print(f"[meta-law-tripwire] WARNING: genesis integrity: {gi['violations']}", file=sys.stderr)
        constitution_guard.log_guard_event(ROOT, "GENESIS_INTEGRITY", {"violations": gi["violations"]})
    # (2) OPERATOR-path signature scan on the operator's run objectives. LAW-0: NEVER a hard block.
    # Interactive: confirm-and-proceed. Non-interactive: log-and-proceed (the operator already
    # declared intent by running the pipeline). Agents are handled separately (refuse-and-route).
    # R6: the review question is operator input too, so it is scanned with the objectives.
    _operator_text = (args.run_objectives or "") + _question_suffix(args.task, args.question)
    _meta_hits = constitution_guard.scan_for_meta_signature(_operator_text, project_root=ROOT)
    if _meta_hits:
        print(f"[meta-law-tripwire] operator input matched the meta-law signature: {_meta_hits}",
              file=sys.stderr)
        constitution_guard.log_guard_event(ROOT, "META_SIGNATURE_OPERATOR_INPUT",
                                            {"signature": _meta_hits, "interactive": not args.non_interactive})
        _confirmed = None
        if not args.non_interactive:
            try:
                _confirmed = input("[meta-law-tripwire] This reads like a meta-level change attempt. "
                                   "Confirm you intend it (yes/no): ").strip().lower() in {"yes", "y"}
            except EOFError:
                _confirmed = False
        _mv = constitution_guard.operator_input_verdict(
            _operator_text, interactive=not args.non_interactive, confirmed=_confirmed, project_root=ROOT)
        if _mv["action"] == "abort":
            print("[meta-law-tripwire] operator declined; aborting this run.", file=sys.stderr)
            return 7  # the operator's OWN choice to stop, not a guard cage

    # Sensitivity-layer inactive HARD GATE (INFRA-038). The FULL LAW-IV sensitivity
    # layer (reasoning about sensitivity as a first-class concept; masking sensitive
    # content from API/web; may_handle_sensitive routing) is BUILT AND WIRED
    # (INFRA-041) but NOT ACTIVATED: LAYER_ACTIVE is False, so every wired call site
    # no-ops. Corrected in productization STEP 9; this comment said "BUILT BUT
    # UNWIRED" long after INFRA-041 wired the four chokepoints. Until the operator
    # activates it, the run REFUSES to start unless the operator declares THIS run
    # non-sensitive via --sensitivity-layer-inactive-override, mirroring the Qwen
    # redaction hard-gate-plus-logged-override. (Operator redaction rules still apply
    # locally; only the outbound masking layer awaits activation, see README.)
    if not sensitivity_layer.is_active():
        print("[sensitivity-gate] WARNING: the full LAW-IV sensitivity layer is BUILT AND "
              "WIRED (INFRA-041) but NOT ACTIVATED; masking of outbound payloads is inert "
              "until the operator activates it. Operator redaction rules still apply locally.",
              file=sys.stderr)
        if not args.sensitivity_layer_inactive_override:
            print("[sensitivity-gate] STOP: refusing to start with the full sensitivity layer "
                  "inactive. Re-run with --sensitivity-layer-inactive-override to declare THIS run "
                  "non-sensitive and proceed (logged to the governance ledger).", file=sys.stderr)
            return 6
        if not args.non_interactive:
            try:
                confirm = input("--sensitivity-layer-inactive-override: declare THIS run "
                                "NON-SENSITIVE and proceed with the full sensitivity layer "
                                "inactive? (yes/no): ").strip().lower()
            except EOFError:
                confirm = "no"
            if confirm not in {"yes", "y"}:
                print("[sensitivity-gate] override not confirmed; aborting.", file=sys.stderr)
                return 6
        led = sensitivity_layer.record_sensitivity_override(
            ROOT, run_ctx.run_id, reason="operator_declared_non_sensitive_layer_inactive")
        print(f"[sensitivity-gate] OVERRIDE accepted for this run; logged to {led.name}.",
              file=sys.stderr)

    # Reset toggles. With per-run folders each run starts empty, so these only
    # matter if a caller re-points at an existing run; they act on this run's paths.
    if args.reset_bus:
        bp = run_ctx.bus_path()
        if bp.exists(): bp.unlink()
    if args.reset_cost:
        for p in (run_ctx.cost_jsonl_path(), run_ctx.cost_json_path()):
            if p.exists(): p.unlink()

    # Cost tracker (must exist before any agent fires)
    cost_tracker = CostTracker.open(run_ctx.logs_dir(), print_live=True)

    # Search router (used by date cascade + downstream agents)
    keys = load_api_keys()
    search_router = SearchRouter.open(ROOT, keys=keys)

    # Deprecated-model gate + self-resolution (INFRA-026): resolve every agent's
    # configured FAMILY KEY against the provider's CURRENT live list. A family key
    # that matches exactly one concrete live id binds to it automatically (in-memory
    # only -- never written to the tracked registry); zero or ambiguous matches STOP
    # and require operator approval. Never swaps to a different model. Backends whose
    # live list is unavailable (no key / local Qwen) are skipped gracefully.
    resolved_agents = None  # threaded into boot so agents run the bound concrete ids
    if not args.skip_model_check:
        registry_path = ROOT / "config" / "agent_registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if args.backend_profile == "local":
            for agent_name, (new_backend, new_model) in _LOCAL_PROFILE.items():
                if agent_name in registry["agents"]:
                    registry["agents"][agent_name]["backend"] = new_backend
                    registry["agents"][agent_name]["model"] = new_model
            print(f"[pipeline] backend-profile=local: {len(_LOCAL_PROFILE)} agents "
                  f"remapped to local backends (REDACTOR stays qwen_local)",
                  file=sys.stderr, flush=True)
        # profile applied before the model gate; local backends are "unverifiable"
        # (list_available_models returns None), so the gate skips them gracefully.
        handler = _resolve_operator_handler(args, run_ctx)
        gate = enforce_current_models(
            ROOT, registry, keys, interactive=not args.non_interactive,
            operator_handler=handler, registry_path=registry_path,
        )
        for s in gate["skipped"]:
            print(f"[model-gate] skipped {s['agent']} ({s['backend']}): "
                  f"cannot verify {s['model']!r} (no key / local backend)", file=sys.stderr)
        for a in gate["approved"]:
            print(f"[model-gate] operator-approved swap: {a['agent']} "
                  f"{a['from']!r} -> {a['to']!r}", file=sys.stderr)
        if not gate["ok"]:
            dead = [f"{f['agent']}={f['dead_model']!r}" for f in gate["findings"]]
            print(f"[model-gate] STOP: models not auto-resolvable / not approved: {dead}. "
                  f"Approve a replacement, pin a live snapshot in agent_registry.json, "
                  f"or pass --skip-model-check to override.", file=sys.stderr)
            return 3
        # Apply live family-key -> concrete-id bindings to the in-memory registry
        # ONLY (the tracked file keeps family keys). The gate's own persist already
        # ran above with family keys intact, so this never writes a dated id to disk.
        bindings = gate.get("bindings", [])
        for b in bindings:
            registry["agents"][b["agent"]]["model"] = b["to"]
            print(f"[model-gate] resolved {b['agent']} ({b['backend']}): "
                  f"{b['from']!r} -> {b['to']!r} (live binding)", file=sys.stderr)
        if bindings:
            # Log the bindings to the run record (per-run, gitignored; not a tracked file).
            rec = run_ctx.logs_dir() / "model_bindings.json"
            rec.parent.mkdir(parents=True, exist_ok=True)
            rec.write_text(json.dumps({"bindings": bindings}, indent=2, ensure_ascii=False),
                           encoding="utf-8")
        resolved_agents = registry["agents"]

    if args.backend_profile == "local" and resolved_agents is None:
        reg = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))
        for agent_name, (new_backend, new_model) in _LOCAL_PROFILE.items():
            if agent_name in reg["agents"]:
                reg["agents"][agent_name]["backend"] = new_backend
                reg["agents"][agent_name]["model"] = new_model
        print(f"[pipeline] backend-profile=local (skip-model-check): {len(_LOCAL_PROFILE)} "
              f"agents remapped to local backends", file=sys.stderr, flush=True)
        resolved_agents = reg["agents"]

    # Qwen-required startup gate (INFRA-035): redaction is the always-on final pass
    # (INFRA-034) and runs on the local Qwen backend. Refuse to start if Qwen is not
    # reachable/configured, UNLESS the operator waives redaction for THIS run.
    qstat = redaction_gate.qwen_backend_status(ROOT)
    waive = bool(args.no_redaction_override)
    redaction_enabled = True
    if waive and not args.non_interactive:
        # A waiver must be confirmed in interactive mode (conscious, per-run choice).
        try:
            confirm = input("--no-redaction-override: declare THIS run NON-SENSITIVE and run with "
                            "NO redaction? (yes/no): ").strip().lower()
        except EOFError:
            confirm = "no"
        if confirm not in {"yes", "y"}:
            print("[redaction-gate] override not confirmed; aborting.", file=sys.stderr)
            return 4
    if not qstat["configured"] and not waive:
        print(f"[redaction-gate] STOP: the local Qwen redaction backend is not reachable/configured "
              f"({qstat['detail']}). Redaction is a required final pass. Set up Qwen "
              f"(install torch + transformers and the model Qwen/Qwen2.5-7B-Instruct), or re-run "
              f"with --no-redaction-override to declare this run non-sensitive and proceed without "
              f"redaction. Pre-run check verifies: {qstat['verified_now']}; actual model load is "
              f"verified at first call.", file=sys.stderr)
        return 4
    if waive:
        redaction_enabled = False
        reason = "operator_declared_non_sensitive" if qstat["configured"] else "qwen_unavailable"
        ledger = sensitivity_layer.record_redaction_waiver(ROOT, run_ctx.run_id, reason=reason)
        print(f"[redaction-gate] WAIVED for this run (no redaction; reason={reason}); "
              f"logged to {ledger.name}.", file=sys.stderr)
    elif qstat["configured"] and not qstat["gpu"]:
        # SOFT reminder only: never blocks, never recorded.
        print("[redaction-gate] note: Qwen reachable but no GPU detected, redaction will be slow "
              "on CPU.", file=sys.stderr)

    # BP-6 pre-warm: kick off the Qwen model load NOW, in a daemon thread, so it
    # loads onto the GPU while the date cascade and phases 1-7 run. By the time the
    # redaction phase (phase 9) runs, the model is resident and the first redaction
    # call skips the cold load. Only when redaction will ACTUALLY run: it is gated on
    # the sensitivity layer being active (non-sensitive mode skips the scrub phase),
    # and not waived, so there is no point loading a multi-GB model otherwise.
    if redaction_enabled and sensitivity_layer.is_active():
        threading.Thread(target=_prewarm_qwen, args=(ROOT,), daemon=True).start()

    # Draft mode phase 0: generate a memo from the question and mark it as the review
    # target BEFORE population, so the existing phases review it like any document. The
    # generation uses the AMENDMENT_DRAFTER (strong Claude) model; the embedding store is
    # built from the current grounding in input/context/ to retrieve passages to cite.
    if args.task == "draft":
        if not (args.question or "").strip():
            print("[pipeline] STOP: --task draft requires --question \"<your question>\".",
                  file=sys.stderr, flush=True)
            return 5
        draft_registry = resolved_agents or json.loads(
            (ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
        draft_contracts = json.loads(
            (ROOT / "config" / "agent_contracts.json").read_text(encoding="utf-8")).get("contracts", {})
        drafter = AgentWrapper(
            name="AMENDMENT_DRAFTER", constitution=Constitution.load(ROOT / "config" / "constitution.json"),
            bus=MessageBus.open(run_ctx.bus_path()), registry=draft_registry,
            contracts=draft_contracts, keys=keys, cost_tracker=cost_tracker,
            # productization STEP 4: same run-awareness fix as _build_wrapper, so a
            # draft-mode contract violation also lands under <run>/audit/
            # contract_violations/ instead of the shared output/ fallback.
            run_context=run_ctx,
            # redaction_enabled is already resolved by this point in main (set at
            # :1821/:1841, before this draft-mode block at :1864), so the drafter gets
            # the same real run signal as _build_wrapper's wrappers, not a placeholder.
            sensitive=redaction_enabled)

        def _draft_retrieve(q):
            store = embedding_store.get_or_build(ROOT)
            return embedding_store.query_store(store, q, n=8) if store else []

        _draft_passages = []

        def _draft_retrieve_recorded(q):
            # Kept for the evidence record: which REF-* ids the memo call was shown.
            _draft_passages[:] = _draft_retrieve(q) or []
            return list(_draft_passages)

        def _draft_generate(stable, dynamic):
            return _draft_generate_with_evidence(drafter, stable, dynamic,
                                                 passages=_draft_passages, run_ctx=run_ctx)

        memo_path = run_draft_phase0(
            ROOT, args.question, retrieve=_draft_retrieve_recorded, generate=_draft_generate,
            now_iso=datetime.now(timezone.utc).isoformat())
        if memo_path is None:
            print("[pipeline] draft phase 0 failed (no memo generated); aborting.",
                  file=sys.stderr, flush=True)
            return 5
        print(f"[pipeline] draft memo written to {memo_path.relative_to(ROOT).as_posix()}; "
              "it is the review target.", file=sys.stderr, flush=True)

    # Date cascade + cutoff -> populate input/operational/
    log_event(_LOG, "phase_start phase=0 step=date_cascade_cutoff", run_id=run_ctx.run_id,
              phase="0")
    # chokepoint 4 (INFRA-041 P2): suppress the BOOT date-web egress under sensitive mode.
    context_records, operational_records = _populate_operational(
        ROOT, search_router, sensitive=sensitivity_layer.is_active() and redaction_enabled,
        mode=args.mode, infer_roles=args.infer_roles)

    # Load text for context + operational
    ctx_docs = _load_corpus(ROOT / "input" / "context")
    op_docs = _load_corpus(ROOT / "input" / "operational")
    if args.max_docs > 0:
        op_docs = op_docs[: args.max_docs]
    # R6: the earlier version(s) the operator declared in the manifest, loaded from the
    # context corpus. A file named both as a target and as a prior is reviewed, not
    # compared, and the warning names the file (a filename, never content).
    _manifest = role_resolution.read_manifest(ROOT / "input" / "context")
    prior_docs, _prior_conflicts = _prior_docs_for(ctx_docs, _manifest, op_docs)
    for _name in _prior_conflicts:
        print(f"[pipeline] WARNING: {_name} is named both as a target and as an earlier "
              f"version; it is reviewed, not compared.", file=sys.stderr, flush=True)
    log_event(_LOG, f"prior_versions declared={len(role_resolution.manifest_prior(_manifest))} "
                    f"loaded={len(prior_docs)} conflict={len(_prior_conflicts)}",
              run_id=run_ctx.run_id, phase="0")
    if not op_docs:
        log_event(_LOG, "no_operational_docs source=cutoff", level="warning",
                  run_id=run_ctx.run_id, phase="0")
        # Still complete BOOT so the operator can inspect state
    log_event(_LOG, f"corpus_loaded context_docs={len(ctx_docs)} operational_docs={len(op_docs)}",
              run_id=run_ctx.run_id, phase="0")

    projection = _cost_projection(len(op_docs), len(ctx_docs))
    print("\n=== PROJECT SHIMMER: pre-run estimate ===", file=sys.stderr)
    print(f"  Operational documents: {len(op_docs)}", file=sys.stderr)
    print(f"  Context documents:     {len(ctx_docs)}", file=sys.stderr)
    print(f"  Estimated Claude:      ${projection['claude_cost_usd']:.4f}", file=sys.stderr)
    print(f"  Estimated GPT-4o:      ${projection['gpt_cost_usd']:.4f}", file=sys.stderr)
    print(f"  Estimated TOTAL:       ${projection['total_usd']:.4f}", file=sys.stderr)
    print("===========================================\n", file=sys.stderr)

    if not args.skip_confirmation and not args.non_interactive:
        try: ans = input("Proceed with live API calls? (yes/no): ").strip().lower()
        except EOFError: ans = "no"
        if ans not in {"yes", "y"}:
            print("[pipeline] aborted by operator.", file=sys.stderr); return 0

    # BOOT orchestrator (adaptive_spawn fires if first run)
    handler = _resolve_operator_handler(args, run_ctx)
    orch = TopOrchestrator.boot(ROOT, interactive=not args.non_interactive,
                                 operator_handler=handler, cost_tracker=cost_tracker,
                                 run_adaptive_spawn=True, run_context=run_ctx,
                                 registry=resolved_agents)
    orch.run_objectives = args.run_objectives

    # Parse conventions -> registry
    conv_registry = parse_conventions(ROOT)
    write_registry(ROOT, conv_registry)
    conv_registry_dict = conv_registry.as_dict()
    convention_review_enabled = bool(conv_registry_dict.get("conventions"))
    log_event(_LOG, f"convention_registry rules={len(conv_registry_dict.get('conventions', []))} "
                    f"review_enabled={convention_review_enabled}", run_id=run_ctx.run_id, phase="0")

    # Convention assignment (docs/api/CONVENTION_ASSIGNMENT_DESIGN.md): the one-way
    # subject comparison, computed ONCE here at BOOT, never per call, never per
    # document. `resolved_agents` may still be None (cloud backend with
    # --skip-model-check, the one path that never sets it above); fall back to the
    # tracked file, the same idiom already used at line ~3134 for the same reason.
    assignment_agents = resolved_agents or json.loads(
        (ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
    convention_assignment_result = convention_assignment.assign_conventions(
        conv_registry_dict.get("conventions", []), assignment_agents)
    # False-negative evidence (scripts/fn_evidence.py): the operator's own rule id
    # is written beside every registry id in the saved assignment, so a run's
    # artifacts alone can map a key's rule to the registry id the pairing map and
    # the call evidence speak in. Without it the mapping would have to be inferred
    # from a registry regenerated at some later BOOT, which is not evidence.
    for _rid, _row in convention_assignment_result.get("by_rule", {}).items():
        _row["source_rule_id"] = finding_record.source_rule_id_for(_rid, conv_registry_dict)
    convention_assignment.write_assignment(run_ctx, convention_assignment_result)
    _untagged = convention_assignment.untagged_count(convention_assignment_result)
    _unassigned = convention_assignment.unassigned_summary(convention_assignment_result)
    for _row in _unassigned:
        _row["source_rule_id"] = finding_record.source_rule_id_for(
            _row["rule_id"], conv_registry_dict)
        _row["reason"] = ("no agent declares: " + ", ".join(_row["subjects"])
                          if _row["status"] == "unassigned" else
                          "matched " + ", ".join(_row["agents"]) + ", no rule-consuming "
                          "path today")
    log_event(_LOG, f"convention_assignment rules={len(convention_assignment_result['by_rule'])} "
                    f"untagged={_untagged} unassigned={len(_unassigned)}",
              run_id=run_ctx.run_id, phase="0")
    # A convention matching no agent, or matching only an agent with no rule-
    # consuming path today, is never dropped: it is surfaced on the bus (the
    # same "post it, never swallow it" discipline as AMENDMENT_REFUSED), so
    # /runs/{run_id}/convention-assignment and the console can read it, not
    # only this log line. Document-independent (computed once at BOOT, before
    # any document is in scope), so doc_id is empty, matching the design
    # document's own stated shape.
    if _unassigned:
        orch._post_orchestrator(
            recipient="BROADCAST", channel="main", msg_type="INFORM",
            body={"event": "CONVENTION_UNASSIGNED", "backend": "computed",
                  "model": "python", "item_count": len(_unassigned), "parse_trace": {},
                  "payload": {"agent": "ORCHESTRATOR", "doc_id": "", "items": _unassigned}},
            constitution_check={"laws_consulted": ["LAW-V"], "result": "RESOLVED",
                                "resolution": "a convention no agent can act on is "
                                              "surfaced visibly rather than silently "
                                              "routed nowhere"})

    # 1c: OPERATOR-RULE HARD-STOP (operator-sovereignty, mirrors the qwen / sensitivity
    # gates). Redaction may act ONLY on what a compiled operator rule declares redactable;
    # there is NO silent fallback to engine-defined default categories. If redaction is
    # required (not waived) but no operator rule compiles, REFUSE the run here, before
    # any paid agent, unless the operator consciously declared redact-nothing via
    # --no-redaction-override (which already logged the waiver to the governance ledger).
    if redaction_enabled and op_docs:
        rr_pre = redaction_rules(conv_registry_dict)
        if not rr_pre["operator_in_force"]:
            warn = "; ".join(f"{w['id']}: {w['reason']}" for w in rr_pre["warnings"]) or "none"
            print("[redaction-rules] STOP: no operator redaction rule in force; the engine does "
                  "NOT apply default categories on its own (operator-sovereignty). Supply a "
                  "compiling redaction convention (a confidentiality/redaction category or "
                  "'must not contain …' phrasing with rule text), or re-run with "
                  "--no-redaction-override to consciously declare redact-nothing for THIS run "
                  f"(logged to the governance ledger). Redaction-intent that failed to compile: {warn}.",
                  file=sys.stderr)
            return 4

    # LAW-IV outbound masking injectors (INFRA-041 P2): build the prompt masker (chokepoint 1,
    # injected into every agent wrapper via orch) and the web-query masker (chokepoint 2, injected
    # into the search router) from the compiled operator rules. Both are gated on the layer being
    # active AND the run being sensitive; the layer is inactive today, so they are inert and this
    # is byte-for-byte unchanged until activation (P5). sensitive = redaction_enabled (the
    # established run signal); operator rules are the sole sensitivity source (no model judge).
    _masking_operator_rules = redaction_rules(conv_registry_dict).get("rules", [])
    orch.outbound_masker = sensitivity_layer.make_outbound_prompt_masker(
        sensitive=redaction_enabled, operator_rules=_masking_operator_rules, project_root=ROOT,
        registry=orch.registry, run_id=run_ctx.run_id)
    search_router.query_masker = sensitivity_layer.make_query_masker(
        sensitive=redaction_enabled, operator_rules=_masking_operator_rules, project_root=ROOT,
        run_id=run_ctx.run_id)
    # productization STEP 4: same established run signal, threaded onto orch (the
    # same dynamic-attribute pattern as outbound_masker above) so _build_wrapper
    # can set AgentWrapper.sensitive without changing its own signature.
    orch.sensitive = redaction_enabled

    # Reference index
    reference_index = _build_reference_index(ROOT, ctx_docs, op_docs, conv_registry_dict,
                                             run_context=run_ctx)
    log_event(_LOG, f"reference_index entries={len(reference_index.entries)}",
              run_id=run_ctx.run_id, phase="0")

    # Semantic retrieval layer (genesis Part XXI). Loads from
    # durable/cache/embedding_store.pkl if present, otherwise tries to build
    # from input/context/. Graceful degradation: None means Zipfian fallback.
    embed_store = embedding_store.get_or_build(ROOT, reference_index=reference_index)
    if embed_store is not None:
        # local D5: embed_store.get("passages", []) is always [] for a real (schema-2,
        # per-language sub-store) store, so this log line reported passages=0 on every
        # populated run. embedding_store.passages() reads the real schema-2 shape; wrapped
        # in len(...) here so this stays a count, never the passages themselves (check 112).
        log_event(_LOG, f"embedding_store_loaded passages={len(embedding_store.passages(embed_store))}",
                  run_id=run_ctx.run_id, phase="0")
    else:
        log_event(_LOG, "embedding_store_unavailable retrieval=zipfian", level="warning",
                  run_id=run_ctx.run_id, phase="0")

    # local progress display: the baseline denominator is known as soon as op_docs is
    # known, before phase 3-4 starts; grown later via _local_progress_bump_expected as
    # D6 pass-two work is discovered. The memory sampler thread runs for the life of the
    # run (stopped at the "complete" emission below); daemon=True so it can never keep
    # the process alive on its own.
    if _is_local_profile():
        _local_progress_reset(_local_progress_baseline(len(op_docs)))
        threading.Thread(target=_local_progress_memory_sampler,
                         args=(_LOCAL_PROGRESS_STOP,), daemon=True).start()

    # PHASE 1
    _emit_progress(event="start", docs=len(op_docs), status="running")
    _emit_progress(phase=1, status="running")
    orch.deliberation_round({"phase": "situation_assessment",
                             "context_count": len(ctx_docs),
                             "operational_count": len(op_docs),
                             "convention_count": len(conv_registry_dict.get("conventions", []))})

    # R6: the default sentence, plus the review question when the operator gave one.
    run_objectives = _effective_run_objectives(args.run_objectives, args.task, args.question)

    production, audit, conv_review = [], [], []
    deliverables = {}
    if op_docs:
        log_event(_LOG, "phase_start phase=3-4 step=content_production", run_id=run_ctx.run_id,
                  phase="3-4")
        _emit_progress(phase=3, status="running")
        _t3 = time.perf_counter()
        production = asyncio.run(phase_3_4_content_production(
            orch, keys, op_docs, ctx_docs, run_objectives,
            conv_registry_dict, reference_index,
            [e.as_dict() for e in reference_index.entries if e.input_type == "context"][:30],
            embed_store=embed_store, max_concurrent_docs=args.max_concurrent_docs,
        ))
        log_phase_done(_LOG, "3-4", run_id=run_ctx.run_id,
                       duration_ms=int((time.perf_counter() - _t3) * 1000))
        # Part XXVI: pull the structural inventory ARCHIVIST produced during
        # the corpus-level phase so downstream phases can pass it to
        # PRACTICE_AUDITOR / LEGAL_ANALYST per Part XXIII's directive.
        structural_inventory = _structural_inventory(production)
        log_event(_LOG, f"structural_inventory_pulled elements={len(structural_inventory)}",
                  run_id=run_ctx.run_id, phase="3-4")
        log_event(_LOG, "phase_start phase=5 step=verification_fact_check", run_id=run_ctx.run_id,
                  phase="5")
        _emit_progress(phase=5, status="running")
        _t5 = time.perf_counter()
        audit = asyncio.run(phase_5_audit(orch, keys, op_docs, production, run_objectives,
                                          conv_registry_dict, reference_index,
                                          max_concurrent_docs=args.max_concurrent_docs))
        log_phase_done(_LOG, "5", run_id=run_ctx.run_id,
                       duration_ms=int((time.perf_counter() - _t5) * 1000))
        if convention_review_enabled:
            log_event(_LOG, "phase_start phase=5.5 step=convention_review",
                      run_id=run_ctx.run_id, phase="5.5")
            _emit_progress(phase=5.5, status="running")
            _t55 = time.perf_counter()
            conv_review = asyncio.run(phase_5_5_convention_review(
                orch, keys, op_docs, run_objectives, conv_registry_dict, reference_index,
                embed_store=embed_store, structural_inventory=structural_inventory,
                max_concurrent_docs=args.max_concurrent_docs,
                review_mode=args.review_mode, pairs_per_unit=args.pairs_per_unit,
                prior_docs=prior_docs,
                convention_assignment=convention_assignment_result))
            log_phase_done(_LOG, "5.5", run_id=run_ctx.run_id,
                           duration_ms=int((time.perf_counter() - _t55) * 1000))
        else:
            log_event(_LOG, "phase_skipped phase=5.5 reason=no_conventions",
                      run_id=run_ctx.run_id, phase="5.5")

        cost_tracker.finalize_line()
        log_event(_LOG, "phase_start phase=6 step=synthesis_deliverables", run_id=run_ctx.run_id,
                  phase="6")
        _emit_progress(phase=6, status="running")
        _t6 = time.perf_counter()
        deliverables = asyncio.run(phase_6_synthesis(
            orch, keys, op_docs, production, audit, conv_review,
            run_objectives, conv_registry_dict, reference_index,
            embed_store=embed_store, max_concurrent_docs=args.max_concurrent_docs,
            amendment_polish=args.amendment_polish, question=args.question))
        log_phase_done(_LOG, "6", run_id=run_ctx.run_id,
                       duration_ms=int((time.perf_counter() - _t6) * 1000))
        for doc_id, paths in deliverables.items():
            log_event(_LOG, f"deliverables_written files={len(paths)} "
                            f"amendments={paths['amendment_count']} "
                            f"validator_errors={len(paths['validator_errors'])}",
                      run_id=run_ctx.run_id, phase="6", doc_id=doc_id)

        # Phase 6.5: EDITORIAL review (INFRA-039). Execution order: AFTER phase_6
        # synthesis (the master is assembled), BEFORE phase 7 and BEFORE the phase 9
        # privacy scrub, so EDITOR_CLERK reads the CLEAN pre-scrub master. Advisory only:
        # never modifies the master, never gates shipping. Option B: runs only on a
        # run declared non-sensitive (the --no-redaction-override waiver in force, i.e.
        # redaction is waived); otherwise EDITOR_CLERK is skipped LOUDLY. Editorial house:
        # no sensitivity_layer import, no privacy mechanic.
        run_is_non_sensitive = not redaction_enabled  # waiver in force => declared non-sensitive
        board_tunables = _resolve_editorial_board(ROOT)  # operator config, read once at phase start
        log_event(_LOG, f"phase_start phase=6.5 step=editorial_review_board "
                        f"max_rounds={board_tunables['max_rounds']} "
                        f"confidence_threshold={board_tunables['confidence_threshold']} "
                        f"sensitive_skip={0 if run_is_non_sensitive else 1}",
                  run_id=run_ctx.run_id, phase="6.5")
        _emit_progress(phase=6.5, status="running")
        _t65 = time.perf_counter()
        editorial_summary = phase_6_5_editorial_review(
            orch, keys, op_docs, deliverables, run_ctx, conv_registry_dict,
            run_is_non_sensitive=run_is_non_sensitive, board_tunables=board_tunables)
        log_phase_done(_LOG, "6.5", run_id=run_ctx.run_id,
                       duration_ms=int((time.perf_counter() - _t65) * 1000))

        def _ed_count(*states):
            return sum(1 for v in editorial_summary.values() if v.get("state") in states)
        n_reviewed = _ed_count("REVIEWED")
        n_ed_failed = _ed_count("FAILED")
        n_ed_skipped = _ed_count("SKIPPED")
        n_sound = sum(1 for v in editorial_summary.values()
                      if v.get("state") == "REVIEWED" and v.get("all_sound"))
        if not run_is_non_sensitive:
            log_event(_LOG, f"phase_skipped phase=6.5 reason=sensitive_run_masking_layer_inactive "
                            f"deliverables={n_ed_skipped}", run_id=run_ctx.run_id, phase="6.5")
        else:
            log_event(_LOG, f"editorial_summary reviewed={n_reviewed} all_sound={n_sound} "
                            f"failed={n_ed_failed} total={len(editorial_summary)} advisory=1",
                      run_id=run_ctx.run_id, phase="6.5")
            if n_ed_failed:
                failed_docs = [d for d, v in editorial_summary.items() if v.get("state") == "FAILED"]
                print(f"[pipeline] editorial review failed (advisory, deliverable still ships): "
                      f"{failed_docs}", file=sys.stderr)

        # Phase 7: audit synthesis + DELTA escalations
        _emit_progress(phase=7, status="running")
        _t7 = time.perf_counter()
        synth = AuditSynthesizer(project_root=ROOT, bus=orch.bus, run_context=run_ctx)
        audit_summary = synth.synthesize(
            verifier_findings=_items_for(audit, "VERIFIER"),
            fact_check_findings=_items_for(audit, "FACT_CHECKER"),
            practice_findings=_items_for(conv_review, "PRACTICE_AUDITOR"),
        )
        log_phase_done(_LOG, "7", run_id=run_ctx.run_id,
                       duration_ms=int((time.perf_counter() - _t7) * 1000))
        log_event(_LOG, f"audit_synthesis findings={len(audit_summary['findings'])} "
                        f"deltas={len(audit_summary['delta_proposals'])}",
                  run_id=run_ctx.run_id, phase="7")
        if audit_summary["delta_proposals"]:
            log_event(_LOG, f"delta_escalation_start count={len(audit_summary['delta_proposals'])}",
                      run_id=run_ctx.run_id, phase="7")
            decisions = orch.escalate_delta_proposals(audit_summary["delta_proposals"])
            for d in decisions:
                print(f"  -> {d['delta_id']} {d['kind']}: {d['decision']} (approved={d['approved']})",
                      file=sys.stderr)

    # Phase 9: redaction (ALWAYS runs, final privacy pass over the deliverables,
    # LAW-IV). The privacy redaction stage now lives in the sensitivity_layer home
    # (Phase 1c); the pipeline calls INTO it (editorial->privacy) and injects the two
    # editorial-side callbacks it needs: build_wrapper (closes over the orchestrator +
    # keys) and render_deliverable (the shape-(a) RENDER step: write_amendment_
    # deliverables + _category_for_conv stay editorial). The single REDACTOR agent
    # proposes spans; the deterministic detector catches authorized shapes; the
    # scrubber applies + verifies. No privacy->editorial edge.
    log_event(_LOG, f"phase_start phase=9 step=redaction_screening "
                    f"waived={0 if redaction_enabled else 1}",
              run_id=run_ctx.run_id, phase="9")
    _emit_progress(phase=9, status="running")

    def _render_redaction_deliverable(scrubbed_master, body_text, doc, info):
        amendment_render.write_amendment_deliverables(
            scrubbed_master, deliv_dir=run_ctx.deliverables_dir(), doc_id=doc["id"],
            document_name=doc["name"], body_text=body_text,
            category_for_conv=lambda c: _category_for_conv(c, conv_registry_dict))

    # ARCHITECTURE: the LAW-IV redaction (scrub/apply) phase now lives UNDER the
    # sensitivity layer. In non-sensitive mode (the layer is INACTIVE) the entire
    # scrub phase is skipped: the review agents still FLAG PII upstream
    # (CONV-CONFIDENTIALITY findings in phases 5/5.5/6 are unchanged), they simply do
    # not scrub. Only the scrubbing/application phase is gated. When the sensitivity
    # layer is ACTIVE the phase runs exactly as before (strict LAW-IV).
    if not sensitivity_layer.is_active():
        log_event(_LOG, "phase_skipped phase=9 reason=non_sensitive_mode",
                  run_id=run_ctx.run_id, phase="9")
        n_blocked = 0
    else:
        _t9 = time.perf_counter()
        redaction_summary = run_redaction_phase(
            orch, op_docs, deliverables, run_ctx, conv_registry_dict,
            build_wrapper=lambda name: _build_wrapper(name, orch, keys),
            render_deliverable=_render_redaction_deliverable,
            redaction_enabled=redaction_enabled)
        log_phase_done(_LOG, "9", run_id=run_ctx.run_id,
                       duration_ms=int((time.perf_counter() - _t9) * 1000))

        def _count_state(*states):
            return sum(1 for v in redaction_summary.values() if v.get("state") in states)
        n_total = len(redaction_summary)
        n_applied = sum(1 for v in redaction_summary.values() if v.get("redacted"))
        n_none = _count_state("NONE")
        n_blocked = _count_state("BLOCKED")
        n_held = _count_state("HELD_WARNING")        # M5: redactor FORMAT failure (not a privacy violation)
        n_skipped = _count_state("SKIPPED")          # operator-waived (conscious no-op)
        # M5: a HELD_WARNING is a redactor-OUTPUT format failure (unparseable / missing-field
        # JSON), which is the local model misbehaving, NOT a confirmed privacy violation. It
        # HOLDS the deliverable with a logged warning but does NOT hard-stop the run (only a
        # real survivor BLOCKs). The pipeline owns the durable governance-ledger write here;
        # the redaction stage writes only inside the run folder.
        if n_held:
            held_docs = [d for d, v in redaction_summary.items() if v.get("state") == "HELD_WARNING"]
            for d in held_docs:
                esc = redaction_summary[d].get("escalation") or {}
                sensitivity_layer.record_redaction_format_warning(
                    ROOT, run_ctx.run_id, doc_id=d,
                    document_name=esc.get("document_name", d),
                    failure_kind=redaction_summary[d].get("failure_kind", "contract_violation"),
                    raw_output_path=esc.get("raw_output_path"))
            print(f"[pipeline] redaction WARNING: {n_held} deliverable(s) HELD (redactor format "
                  f"failure, not a privacy violation): {held_docs}. Logged to the governance ledger; "
                  f"the run continues. Repair the redaction model/prompt if it persists.",
                  file=sys.stderr)
            _emit_progress(event="warning", phase=9, note="redaction_held", count=n_held,
                           status="warning")
        # BLOCKED is visibly distinct from "nothing to redact" (NONE), a format-failure HELD
        # warning, and a waiver.
        # (1c: no NOT_APPLIED state, the dropped AUTHORITY/GATE model-veto path is gone;
        # every detected/proposed span is applied and verified-absent.)
        log_event(_LOG, f"redaction_summary applied={n_applied} none={n_none} "
                        f"blocked={n_blocked} held_warning={n_held} skipped_waived={n_skipped} "
                        f"total={n_total}", run_id=run_ctx.run_id, phase="9")
        if n_blocked:
            blocked_docs = [d for d, v in redaction_summary.items() if v.get("state") == "BLOCKED"]
            print(f"[pipeline] LAW-IV BLOCK: {n_blocked} deliverable(s) could not be confirmed "
                  f"clean by redaction and were BLOCKED (not skipped): {blocked_docs}. "
                  f"See the REDACTION BLOCK notice(s) above and the ESCALATE message(s) on the "
                  f"bus (channel 'escalation'). Run exits non-zero.", file=sys.stderr)
            _emit_progress(event="block", phase=9, note="redaction_block", count=n_blocked,
                           status="warning")

    # Phase 8: persist
    log_event(_LOG, "phase_start phase=8 step=persist_run_summary", run_id=run_ctx.run_id,
              phase="8")
    summary = orch.run_summary()
    final = cost_tracker.get_live_state()
    print("\n=== final cost ===", file=sys.stderr)
    print(f"  Claude:   ${final['by_family'].get('claude', {}).get('cost_usd', 0):.4f}", file=sys.stderr)
    print(f"  GPT-4o:   ${final['by_family'].get('gpt', {}).get('cost_usd', 0):.4f}", file=sys.stderr)
    print(f"  TOTAL:    ${final['total_cost_usd']:.4f}", file=sys.stderr)
    print(f"  calls: {final['total_calls']}  failures: {final['total_failures']}", file=sys.stderr)
    print(f"  bus messages: {summary.get('total', 0)}", file=sys.stderr)

    # OGE capture-at-run-end (build B1; ontology/SCHEMA.md Q1). The run is finalized: append
    # this run's provisions (amendments master) + DELTA proposals into the durable cross-run
    # OGE stores under ontology/. Masked-write gate keyed on whether the sensitivity layer
    # ACTUALLY RAN this run (sensitivity_layer.is_active(), the same signal phase 9's own
    # gate above reads), not on redaction_enabled. redaction_enabled is the operator's
    # declared redaction POLICY for the run (flips True whenever --no-redaction-override is
    # omitted, whether or not anything downstream ever masks a byte); is_active() is whether
    # LAYER_ACTIVE is actually on. Confirmed live on the completed run (cb4c557b,
    # post-run diagnosis): redaction_enabled was True (the operator omitted the waiver on
    # purpose, to test REDACTOR) while LAYER_ACTIVE was still False (an operator DELTA never
    # made, so phase 9 was skipped and REDACTOR never ran, zero bus messages) -- yet OGE, keyed
    # to redaction_enabled, masked its own durable copy of a deliverable that itself held real,
    # unmasked text one directory over. Best-effort: a capture failure never fails a completed run.
    try:
        oge_sensitive = sensitivity_layer.is_active()
        # night W7 c: the storage scope. One value today (ontology_store.DEFAULT_SCOPE);
        # this is the single place a real engagement identifier will be bound later.
        # The store enforces it on every read and write; nothing here filters.
        oge_scope = ontology_store.DEFAULT_SCOPE
        oge = ontology_capture.capture_run(
            run_ctx, op_docs, deliverables, sensitive=oge_sensitive, scope=oge_scope)
        log_event(_LOG, f"oge_capture scope={oge['scope']} "
                        f"provisions_appended={oge['provisions_appended']} "
                        f"provisions_superseded={oge['provisions_superseded']} "
                        f"stubs_skipped={oge['stubs_skipped']} "
                        f"accumulator_size={oge['accumulator_size']} sensitive={oge['sensitive']}",
                  run_id=run_ctx.run_id, phase="8")
        # OGE Tier-1 graph rebuild (build B2). The capture above just updated the durable stores,
        # so rebuild ontology/stores/graph.json from them (build_graph defaults = the real durable
        # sources + the real out_path). The graph is built from ALREADY-STORED data (already masked
        # if the run was sensitive), so no new masking decision is introduced here. Best-effort: a
        # rebuild failure never fails a completed run (the graph is a derived artifact).
        try:
            # INFRA-041 P4: mask Convention.rule + CitationForm.examples under sensitive mode.
            # Same signal as capture_run just above (oge_sensitive = is_active()), not
            # redaction_enabled -- see the fix note above capture_run.
            g = ontology_graph.build_graph(sensitive=oge_sensitive, scope=oge_scope)
            log_event(_LOG, f"oge_graph_rebuilt scope={g['scope']} "
                            f"nodes={g['stats']['nodes_total']} "
                            f"edges={g['stats']['edges_total']}",
                      run_id=run_ctx.run_id, phase="8")
            # OGE GNN incremental update (build B3). Sequence: capture_run -> build_graph -> gnn.
            # MACHINERY not learning: one fwd + one delta-only backprop over the rebuilt graph, then
            # persist weights + high-water mark. GPU optional (warn-not-fail). Best-effort: a GNN
            # failure (or a missing GPU) NEVER fails a completed run -- the GNN state is a derived asset.
            try:
                gs = ontology_gnn.gnn_update()
                log_event(_LOG, f"oge_gnn_updated delta={gs['delta_size']} nodes={gs['nodes']} "
                                f"loss={gs['loss']:.6f} device={gs['device']}",
                          run_id=run_ctx.run_id, phase="8")
            except Exception as e:
                print(f"[pipeline] OGE GNN update skipped (non-fatal): {type(e).__name__}: {e}",
                      file=sys.stderr)
        except Exception as e:
            print(f"[pipeline] OGE graph rebuild skipped (non-fatal): {type(e).__name__}: {e}",
                  file=sys.stderr)
    except Exception as e:
        print(f"[pipeline] OGE capture skipped (non-fatal): {type(e).__name__}: {e}", file=sys.stderr)

    # Draft run-end: PRESERVE then CLEAN. First copy the generated memo into this run's
    # deliverables folder so the run keeps the complete record (the generated memo plus its
    # review amendments). ONLY THEN clear the system_draft memo + _review_targets.json from
    # input/context/, so the source never leaks into the next run as a stale tier-1 target.
    # The copy MUST happen before clear_system_draft (which deletes the memo).
    if args.task == "draft":
        context_dir = ROOT / "input" / "context"
        manifest = role_resolution.read_manifest(context_dir)
        if manifest and manifest.get("source") == "system_draft":
            for fname in sorted(role_resolution.manifest_targets(manifest)):
                src = context_dir / fname
                if src.is_file():
                    # BP-16: the memo lands in its own per-doc subfolder as memo.md
                    # (the doc id is the memo's stem), alongside its review artifacts.
                    doc_id = Path(fname).stem
                    dest_dir = run_ctx.doc_deliverables_dir(doc_id)
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest_dir / run_context_mod.DRAFT_MEMO_NAME)
                    print(f"[pipeline] draft memo preserved in deliverables: "
                          f"{doc_id}/{run_context_mod.DRAFT_MEMO_NAME}",
                          file=sys.stderr, flush=True)
        if role_resolution.clear_system_draft(context_dir):
            print("[pipeline] draft run-end: cleared the system_draft memo and manifest "
                  "from input/context/.", file=sys.stderr, flush=True)

    # BP-16: write the top-level deliverables/_run_summary.md index. Done after the draft
    # memo is preserved and the cost is final, but BEFORE the folder rename so it moves with
    # the run. A no-op-safe pure write keyed on the deliverables already produced this run.
    write_deliverables_run_summary(
        run_ctx.deliverables_dir(), op_docs, deliverables,
        total_cost_usd=final["total_cost_usd"], task=args.task, question=args.question)

    # Rename the run folder from its provisional timestamp name to a human-readable
    # <date>__<slug>, but ONLY when this run created its own folder (auto-created). A
    # server-pinned --output-dir keeps its name (the server tracks runs by that path).
    # Draft slug comes from the question; review slug from the document count and type.
    # Done LAST, after every run write (cost tracker, bus, summary, OGE, draft preserve),
    # so no open handle blocks the move; rename_run is a no-op if the move fails.
    if args.output_dir is None:
        slug = _slug_from_question(args.question) if args.task == "draft" else _review_slug(op_docs)
        renamed = run_context_mod.rename_run(run_ctx, slug)
        if renamed.run_dir != run_ctx.run_dir:
            run_ctx = renamed
            print(f"[pipeline] run folder: output/runs/{run_ctx.run_dir.name}",
                  file=sys.stderr, flush=True)

    # Structured completion line: total amendments across deliverables and the run cost.
    total_amendments = sum(p.get("amendment_count", 0) for p in deliverables.values())
    _emit_progress(event="complete", docs=len(op_docs), amendments=total_amendments,
                   cost=f"{final['total_cost_usd']:.2f}",
                   blocked=n_blocked, status="done")
    _LOCAL_PROGRESS_STOP.set()  # local progress display: stop the memory sampler thread

    # LAW-IV: a redaction BLOCK must not be silent, so fail the run so it surfaces.
    return 5 if n_blocked else 0


if __name__ == "__main__":
    sys.exit(main())
