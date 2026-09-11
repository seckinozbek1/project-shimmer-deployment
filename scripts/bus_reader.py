"""Context package assembly per genesis Part VI.

Builds a curated context package for an agent call:
  governance + objectives + precedents + charter + recent_bus + summary + payload
Token budgets per backend; Qwen restricted to LAW-II + LAW-IV with no bus history.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from typing import Any

import finding_record
import reference_builder
from constitution import Constitution
from message_bus import MessageBus


# NOTE (local D3): there is deliberately no "work" budget here. One existed and was never
# read by any code path, so L4's reduction of it changed nothing that any agent received.
# The document under review is sized by pipeline._truncate_doc / _truncate in CHARACTERS,
# not by a token budget in this table. Do not re-add a "work" key expecting it to bind.
BACKEND_BUDGETS = {
    "claude_api": {"governance": 3000, "bus": 2000},
    "openai_api": {"governance": 2000, "bus": 1500},
    "qwen_local": {"governance": 200, "bus": 0},
    "local_producer": {"governance": 1000, "bus": 500},
    "local_auditor": {"governance": 800, "bus": 500},
}
QWEN_ALLOWED_LAW_IDS = {"LAW-II", "LAW-IV"}
# structure H6: the floor and ceiling for a PROSE passage in the reference
# index. A table's allowance comes from reference_builder instead.
PROSE_MIN_CHARS = 160
PROSE_MAX_CHARS = 240
CHARS_PER_TOKEN = 4


def _estimate_tokens(text): return max(1, len(text) // CHARS_PER_TOKEN)


# Truncation capture (local D2). OFF by default: _CAPTURE.log is None unless a
# caller arms it, so every unmarked code path (and the whole cloud path) is
# byte-for-byte unchanged. Thread-local because cloud mode runs agents in
# parallel; each agent's assemble_context records into its own thread's log.
_CAPTURE = threading.local()


def begin_truncation_capture():
    """Arm before-and-after truncation recording for the CURRENT thread."""
    _CAPTURE.log = {}


def end_truncation_capture():
    """Disarm and return {section: {before_chars, after_chars, budget_tokens,
    truncated}}. Returns {} if capture was never armed."""
    log = getattr(_CAPTURE, "log", None)
    _CAPTURE.log = None
    return log or {}


def _record_truncation(label, before_chars, after_chars, budget_tokens):
    log = getattr(_CAPTURE, "log", None)
    if log is None or not label:
        return
    log[label] = {
        "before_chars": before_chars,
        "after_chars": after_chars,
        "cut_chars": max(0, before_chars - after_chars),
        "budget_tokens": budget_tokens,
        "truncated": after_chars < before_chars,
    }


def _truncate_by_tokens(text, max_tokens, label=None):
    max_chars = max_tokens * CHARS_PER_TOKEN
    out = text if len(text) <= max_chars else text[:max_chars] + "\n... [truncated]"
    _record_truncation(label, len(text), len(out), max_tokens)
    return out


@dataclass
class ContextPackage:
    backend: str
    governance_text: str
    objectives_text: str
    precedents_text: str
    charter_text: str
    recent_bus_text: str
    rolling_summary_text: str
    work_payload: Any
    convention_text: str = ""
    reference_index_text: str = ""
    # Call evidence (scripts/call_evidence.py): what the budgeted renderers above
    # actually KEPT, read off the finished section texts, never assumed: the
    # convention ids whose line survived whole, the reference ids whose block
    # survived whole, whether either section was clipped, and how many recent
    # bus messages were rendered or dropped for budget. The classifier treats a
    # rule that was requested but not rendered as never having reached the call.
    rendered: Any = None

    def token_estimate(self):
        return {
            "governance": _estimate_tokens(self.governance_text),
            "objectives": _estimate_tokens(self.objectives_text),
            "precedents": _estimate_tokens(self.precedents_text),
            "charter": _estimate_tokens(self.charter_text),
            "recent_bus": _estimate_tokens(self.recent_bus_text),
            "rolling_summary": _estimate_tokens(self.rolling_summary_text),
            "conventions": _estimate_tokens(self.convention_text),
            "references": _estimate_tokens(self.reference_index_text),
        }

    def as_prompt_sections(self):
        s = []
        if self.governance_text: s.append(("CONSTITUTION", self.governance_text))
        if self.objectives_text: s.append(("RUN_OBJECTIVES", self.objectives_text))
        if self.precedents_text: s.append(("PRECEDENTS", self.precedents_text))
        if self.charter_text: s.append(("TASK_FORCE_CHARTER", self.charter_text))
        if self.convention_text: s.append(("CONVENTION_REGISTRY", self.convention_text))
        if self.reference_index_text: s.append(("REFERENCE_INDEX", self.reference_index_text))
        if self.rolling_summary_text: s.append(("OLDER_BUS_SUMMARY", self.rolling_summary_text))
        if self.recent_bus_text: s.append(("RECENT_BUS", self.recent_bus_text))
        s.append(("WORK_PAYLOAD", _stringify(self.work_payload)))
        return s

    def as_text(self):
        return "\n\n".join(f"=== {h} ===\n{b}" for h, b in self.as_prompt_sections())

    # Prompt-caching split (INFRA-036): the context sections that are IDENTICAL
    # across an agent's calls within a run (constitution + compiled conventions)
    # vs. the per-call dynamic sections (objectives, precedents, retrieved
    # passages, recent bus, work payload). The stable sections join the agent's
    # stable prompt prefix; the dynamic sections go in the per-call suffix. NO
    # dynamic content (timestamp / run id / per-call text) may be classed stable.
    _STABLE_HEADERS = ("CONSTITUTION", "CONVENTION_REGISTRY")

    def stable_sections(self):
        return [(h, b) for h, b in self.as_prompt_sections() if h in self._STABLE_HEADERS]

    def dynamic_sections(self):
        return [(h, b) for h, b in self.as_prompt_sections() if h not in self._STABLE_HEADERS]

    def stable_text(self):
        return "\n\n".join(f"=== {h} ===\n{b}" for h, b in self.stable_sections())

    def dynamic_text(self):
        return "\n\n".join(f"=== {h} ===\n{b}" for h, b in self.dynamic_sections())


def _stringify(p):
    return p if isinstance(p, str) else json.dumps(p, ensure_ascii=False, indent=2)


def assemble_context(
    backend, constitution, bus, work_payload, run_objectives="", charter=None,
    relevant_precedent_ids=None, channel=None, recent_bus_limit=50,
    convention_registry=None, reference_index_excerpt=None,
):
    if backend not in BACKEND_BUDGETS:
        raise ValueError(f"unknown backend: {backend}")
    budgets = BACKEND_BUDGETS[backend]
    governance_text = _render_governance(constitution, backend, budgets["governance"])
    objectives_text = _truncate_by_tokens(run_objectives, 200, label="RUN_OBJECTIVES")
    precedents_text = _render_precedents(constitution, relevant_precedent_ids, budget=500 if backend != "qwen_local" else 0)
    charter_text = _render_charter(charter) if charter else ""
    # qwen_local gets a non-zero conventions budget (INFRA-038) so OPERATOR
    # REDACTION RULES reach the redactors; other backends get the fuller budget.
    convention_text = _render_conventions(convention_registry, budget=1500 if backend != "qwen_local" else 800)
    # structure H6: raised from 1500 so a band table can arrive whole. The block
    # is still hard-bounded by _truncate_by_tokens at this number.
    reference_index_text = _render_reference_index(reference_index_excerpt, budget=2500 if backend != "qwen_local" else 0)
    bus_counts = {"rendered": 0, "dropped": 0}
    if budgets["bus"] > 0:
        recent_bus_msgs = bus.recent(limit=recent_bus_limit, channel=channel)
        recent_bus_text, summary_text, bus_counts = _render_bus(recent_bus_msgs, budgets["bus"])
    else:
        recent_bus_text, summary_text = "", ""
    rendered = {
        "convention_ids": rendered_line_ids(convention_text),
        "convention_text_truncated": convention_text.endswith(TRUNCATION_MARKER),
        "reference_ids": rendered_line_ids(reference_index_text),
        "reference_text_truncated": reference_index_text.endswith(TRUNCATION_MARKER),
        "bus_messages_rendered": int(bus_counts.get("rendered", 0)),
        "bus_messages_dropped": int(bus_counts.get("dropped", 0)),
    }
    return ContextPackage(
        backend=backend, governance_text=governance_text, objectives_text=objectives_text,
        precedents_text=precedents_text, charter_text=charter_text,
        recent_bus_text=recent_bus_text, rolling_summary_text=summary_text,
        work_payload=work_payload, convention_text=convention_text,
        reference_index_text=reference_index_text, rendered=rendered,
    )


# The tail _truncate_by_tokens leaves on a clipped section.
TRUNCATION_MARKER = "\n... [truncated]"
_RENDERED_LINE_ID = re.compile(r"^- (\S+) \[")


def rendered_line_ids(section_text):
    """The identifiers of the entries a budgeted section actually carries WHOLE:
    every '- <id> [...' line of the finished text, minus the last such line when
    the section ends in the truncation marker (the clip falls mid-line, so the
    last entry may be a fragment and is not counted as rendered). Read off the
    text the model receives; nothing is assumed from the input list."""
    text = section_text or ""
    truncated = text.endswith(TRUNCATION_MARKER)
    body = text[:-len(TRUNCATION_MARKER)] if truncated else text
    ids = []
    for line in body.splitlines():
        m = _RENDERED_LINE_ID.match(line)
        if m:
            ids.append(m.group(1))
    if truncated and ids:
        ids = ids[:-1]
    return ids


def _render_governance(c, backend, budget_tokens):
    seed_laws = c.seed_laws()
    if backend == "qwen_local":
        seed_laws = [law for law in seed_laws if law.get("id") in QWEN_ALLOWED_LAW_IDS]
        lines = ["# Constitution (privacy-critical excerpt)", "Only LAW-II and LAW-IV are surfaced to local-model agents.", ""]
        for law in seed_laws:
            lines.append(f"## {law['id']} — {law['title']}"); lines.append(law["text"]); lines.append("")
        return _truncate_by_tokens("\n".join(lines), budget_tokens, label="CONSTITUTION")
    lines = ["# Constitution", "\n## Seed laws (immutable)\n"]
    for law in seed_laws:
        lines.append(f"### {law['id']} — {law['title']}"); lines.append(law["text"]); lines.append("")
    if c.task_force_laws():
        lines.append("## Task-force laws\n")
        for tfl in c.task_force_laws()[-10:]:
            mission = tfl.get("source_charter", {}).get("mission", "")
            lines.append(f"- {tfl.get('id')} (reuse={tfl.get('reuse_count', 0)}): {mission}")
        lines.append("")
    if c.amendments():
        lines.append("## Operator amendments\n")
        for a in c.amendments()[-20:]:
            lines.append(f"- {a.get('id')}: {a.get('title', '')} — {a.get('text', '')}")
        lines.append("")
    return _truncate_by_tokens("\n".join(lines), budget_tokens, label="CONSTITUTION")


def _render_precedents(c, ids, budget):
    if budget <= 0: return ""
    precs = c.precedents()
    if ids:
        idset = set(ids); precs = [p for p in precs if p.get("id") in idset]
    if not precs: return ""
    lines = ["# Relevant precedents"]
    for p in precs[-20:]:
        lines.append(f"- {p.get('id')}: {p.get('title', '')} — {p.get('ruling', p.get('text', ''))}")
    return _truncate_by_tokens("\n".join(lines), budget, label="PRECEDENTS")


def _render_charter(charter): return "# Task force charter\n" + json.dumps(charter, ensure_ascii=False, indent=2)


def _render_conventions(registry, budget):
    if budget <= 0 or not registry:
        return ""
    convs = registry.get("conventions") if isinstance(registry, dict) else []
    if not convs:
        return ""
    lines = ["# Convention registry", f"Total rules: {len(convs)}", ""]
    for c in convs[:40]:
        lines.append(f"- {c.get('id')} [{c.get('category', '?')}/{c.get('severity', '?')}/{c.get('action', '?')}]: "
                     f"{c.get('rule', '')[:240]}")
    return _truncate_by_tokens("\n".join(lines), budget, label="CONVENTION_REGISTRY")


def _render_reference_index(excerpt, budget):
    """structure H6: a table passage reaches the agent with its rows, not with one row.

    The per-passage allowance used to be a flat 160 characters, so a band table
    arrived as a header and about one row. It is now derived from the section's own
    budget and split by kind: a table gets enough room for whole rows, prose keeps
    what it had. The TOTAL stays bounded exactly as before, by the same
    _truncate_by_tokens call over the finished block, and tables are rendered first
    so that a binding total clips a prose fragment rather than half a band.
    """
    if budget <= 0 or not excerpt:
        return ""
    if isinstance(excerpt, str):
        return _truncate_by_tokens(excerpt, budget, label="REFERENCE_INDEX")
    refs = list(excerpt or [])[:30]
    tables = [r for r in refs if reference_builder.is_table_passage(r.get("text_excerpt") or "")]
    prose = [r for r in refs if r not in tables]
    budget_chars = budget * CHARS_PER_TOKEN
    table_allow = reference_builder.TABLE_EXCERPT_CHARS
    spent = table_allow * len(tables)
    prose_allow = max(PROSE_MIN_CHARS,
                      (budget_chars - spent) // max(1, len(prose)))
    prose_allow = min(prose_allow, PROSE_MAX_CHARS)
    lines = ["# Reference index excerpt"]
    used = len(lines[0]) + 1
    for ref in tables + prose:
        allow = table_allow if ref in tables else prose_allow
        body = reference_builder.table_aware_excerpt(ref.get("text_excerpt") or "", allow)
        head = (f"- {ref.get('ref_id')} [{ref.get('input_type', '?')}/{ref.get('document_name', '?')}"
                f"/p{ref.get('location', {}).get('page', '?')}/para{ref.get('location', {}).get('paragraph', '?')}]:")
        if ref in tables:
            # A table starts on its own line, or its header row would be glued to
            # the citation prefix and stop looking like a table at all.
            block = [head] + body.splitlines()
        else:
            block = [head + " " + body]
        cost = sum(len(ln) + 1 for ln in block)
        # The block is assembled WITHIN the budget rather than assembled and then
        # cut: a character-count clip at the end would slice a row in half, and
        # half a row of a band table reads as data and is not. A passage that
        # does not fit is left out whole, and the next one is still tried, since
        # a short prose passage may fit where a long table did not.
        if used + cost > budget_chars:
            continue
        lines.extend(block)
        used += cost
    return _truncate_by_tokens("\n".join(lines), budget, label="REFERENCE_INDEX")


def _render_bus(msgs, budget_tokens):
    """Returns (rendered text, summary of the dropped older traffic, counts): the
    counts say how many messages were rendered whole and how many were dropped for
    budget, for the call evidence record."""
    if not msgs: return "", "", {"rendered": 0, "dropped": 0}
    body_budget = int(budget_tokens * 0.85); summary_budget = budget_tokens - body_budget
    rendered = []; used = 0; older = []
    all_chars = 0
    for m in reversed(msgs):
        line = _format_bus_msg(m); cost = _estimate_tokens(line)
        all_chars += len(line)
        if used + cost > body_budget:
            older.append(m); continue
        rendered.append(line); used += cost
    rendered.reverse()
    # RECENT_BUS binds by DROPPING whole messages, not by clipping text, so it is
    # recorded here rather than in _truncate_by_tokens.
    _record_truncation("RECENT_BUS", all_chars, len("\n".join(rendered)), body_budget)
    summary = ""
    if older:
        by_type = {}
        by_relation = {}
        for m in older:
            by_type[m.get("type", "?")] = by_type.get(m.get("type", "?"), 0) + 1
            # structure H3: the summary of dropped traffic stays typed too. A
            # count by relation says what kind of disagreement was found and
            # dropped for budget; a narrative summary would say nothing usable.
            body = m.get("body")
            payload = body.get("payload") if isinstance(body, dict) else None
            items = payload.get("items") if isinstance(payload, dict) else None
            for item in items or []:
                if finding_record.is_finding(item):
                    rel = str(item.get("relation"))
                    by_relation[rel] = by_relation.get(rel, 0) + 1
        ts = ", ".join(f"{k}={v}" for k, v in sorted(by_type.items()))
        rel = ", ".join(f"{k}={v}" for k, v in sorted(by_relation.items()))
        text = f"Older bus traffic ({len(older)} messages): {ts}."
        if rel:
            text += f" Findings not shown, by relation: {rel}."
        summary = _truncate_by_tokens(text, summary_budget, label="OLDER_BUS_SUMMARY")
    return "\n".join(rendered), summary, {"rendered": len(rendered), "dropped": len(older)}


def _typed_body(body):
    """structure H3: an earlier agent's findings reach a later agent's prompt as
    COMPACT TYPED LINES, not as narrative.

    Before this, an AGENT_OUTPUT body was rendered by stringifying the whole
    payload and cutting it at 240 characters, which meant a downstream agent read
    a truncated fragment of JSON, usually ending mid-sentence inside somebody
    else's prose. Where the payload carries Finding records the body is rendered
    as one typed line per finding instead. A payload with no Finding records is
    rendered exactly as it was, so every other message on the bus is unchanged.
    Returns None when there is nothing typed to render."""
    if not isinstance(body, dict) or body.get("event") != "AGENT_OUTPUT":
        return None
    payload = body.get("payload")
    if not isinstance(payload, dict):
        return None
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    lines = finding_record.render_typed_lines(items)
    if not lines:
        return None
    n_typed = len([i for i in items if finding_record.is_finding(i)])
    head = f"{n_typed} finding(s) of {len(items)} item(s)"
    return head + "\n" + lines


def _format_bus_msg(m):
    cc = m.get("constitution_check", {})
    typed = _typed_body(m.get("body"))
    body_str = typed if typed is not None else _stringify(m.get('body', ''))[:240]
    return (f"[{m.get('timestamp', '')}] {m.get('sender', '?')} -> {m.get('recipient', '?')} "
            f"({m.get('channel', '?')}) {m.get('type', '?')}: {body_str}  "
            f"[check={cc.get('result', '?')}: {','.join(cc.get('laws_consulted', []) or [])}]")
