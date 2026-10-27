"""Audit synthesis + DELTA proposal logic (genesis Part X)."""

from __future__ import annotations

import localization
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from message_bus import MessageBus


@dataclass
class DeltaProposal:
    id: str
    kind: str
    trigger: str
    evidence: dict
    proposed_change: dict
    requires_operator_approval: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self): return self.__dict__


@dataclass
class AuditFinding:
    category: str
    severity: str
    summary: str
    evidence: dict


@dataclass
class AuditSynthesizer:
    project_root: Path
    bus: MessageBus
    # Per-run context (run_context.RunContext). When set, audit_synthesis.md and
    # delta_proposals.json are written into the current run's audit/ folder
    # (Part XXVII §A); otherwise they fall back to output/audit for standalone use.
    run_context: Any = None

    def synthesize(self, *, write_outputs=True, verifier_findings=None,
                   fact_check_findings=None, practice_findings=None):
        bus_messages = self.bus.read_all()
        findings, deltas = [], []
        seq = [1]
        def next_id():
            s = seq[0]; seq[0] += 1
            return f"DELTA-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{s:03d}"

        disputed_by_source = _count_disputed_by_source(fact_check_findings or [])
        for source, n in disputed_by_source.items():
            if n >= 3:
                findings.append(AuditFinding("claim_verification", "medium",
                                             f"source {source!r} produced {n} DISPUTED",
                                             {"source": source, "count": n}))
                deltas.append(DeltaProposal(id=next_id(), kind="reduce_ttl",
                                            trigger=f"{n} disputed from {source}",
                                            evidence={"source": source, "disputed_count": n},
                                            proposed_change={"target": "verification_cache.TTL_DAYS",
                                                             "action": "reduce_for_source",
                                                             "scope": source, "factor": 0.5,
                                                             "reason": "high dispute rate"}))

        anti = [f for f in (practice_findings or []) if f.get("verdict") in ("ANTI_PATTERN", "VIOLATION")]
        groups = {}
        for f in anti:
            key = (f.get("recommendation") or f.get("procedure_text") or "")[:80]
            groups.setdefault(key, []).append(f)
        for pattern, instances in groups.items():
            if len(instances) >= 2:
                findings.append(AuditFinding("practice", "medium",
                                             f"repeated anti-pattern: {pattern[:60]!r} ({len(instances)})",
                                             {"pattern": pattern, "count": len(instances)}))
                deltas.append(DeltaProposal(id=next_id(), kind="append_project_rule",
                                            trigger=f"anti-pattern recurred {len(instances)} times",
                                            evidence={"pattern": pattern, "instances": instances[:5]},
                                            proposed_change={"target": "prompts/project_rules.md",
                                                             "action": "append_rule",
                                                             "rule_text": f"AVOID: {pattern}",
                                                             "reason": "repeated PRACTICE_AUDITOR verdict"}))

        escalations = [m for m in bus_messages if m.get("type") == "ESCALATE"]
        # Reader check RD3: a recurrence is a DISTINCT escalation (topic and its
        # payload), never a repeated copy of one message; an escalation with no
        # topic or no payload says nothing to recur on, so it is counted apart and
        # never becomes a pattern or a proposal. What a pattern or a proposal IS
        # stays exactly as it was; nothing here is ever applied.
        topic_counts, content_free, seen = {}, 0, set()
        for m in escalations:
            key = escalation_key(m.get("body"))
            if key is None:
                content_free += 1
                continue
            if key in seen:
                continue
            seen.add(key)
            topic_counts[key[0]] = topic_counts.get(key[0], 0) + 1
        for topic, count in topic_counts.items():
            if count >= 3:
                findings.append(AuditFinding("governance", "high",
                                             f"escalation topic {topic!r} recurred {count} times",
                                             {"topic": topic, "count": count}))
                deltas.append(DeltaProposal(id=next_id(), kind="propose_amendment",
                                            trigger=f"repeated escalation: {topic}",
                                            evidence={"topic": topic, "count": count},
                                            proposed_change={"target": "config/constitution.json#amendments",
                                                             "action": "add_amendment", "topic": topic,
                                                             "draft_text": (f"Codify default ruling for "
                                                                            f"recurring escalations on {topic!r}."),
                                                             "reason": f"{count} escalation messages on this topic"}))

        charter_proposals = [m for m in bus_messages if m.get("type") == "CHARTER_PROPOSE"]
        mission_counts = {}
        for m in charter_proposals:
            mission = ((m.get("body") or {}).get("charter") or {}).get("mission", "")
            mission_counts[mission] = mission_counts.get(mission, 0) + 1
        for mission, count in mission_counts.items():
            if count >= 2 and mission:
                findings.append(AuditFinding("governance", "low",
                                             f"charter pattern proposed {count} times: {mission[:60]!r}",
                                             {"mission": mission, "count": count}))
                deltas.append(DeltaProposal(id=next_id(), kind="codify_tf_law",
                                            trigger=f"charter repeated {count} times",
                                            evidence={"mission": mission, "count": count},
                                            proposed_change={"target": "constitution.task_force_laws",
                                                             "action": "codify_pattern", "mission": mission,
                                                             "reason": "pattern has reuse value"}))

        if verifier_findings:
            high_omissions = [f for f in verifier_findings
                              if f.get("finding") == "OMISSION" and f.get("severity") == "high"]
            if len(high_omissions) >= 2:
                findings.append(AuditFinding("content", "high",
                                             f"{len(high_omissions)} high-severity OMISSIONs",
                                             {"count": len(high_omissions)}))
                deltas.append(DeltaProposal(id=next_id(), kind="tighten_processor_prompt",
                                            trigger=f"{len(high_omissions)} high omissions",
                                            evidence={"count": len(high_omissions)},
                                            proposed_change={"target": "PROCESSOR draft prompt",
                                                             "action": "add_completeness_check",
                                                             "reason": "repeated source omissions"}))

        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "bus_messages": len(bus_messages),
            "content_free_escalations": content_free,
            "findings": [f.__dict__ for f in findings],
            "delta_proposals": [d.as_dict() for d in deltas],
            "stats": {
                "verifier_findings": len(verifier_findings or []),
                "fact_check_findings": len(fact_check_findings or []),
                "practice_findings": len(practice_findings or []),
                "escalations": len(escalations), "charter_proposals": len(charter_proposals),
            },
        }
        if write_outputs: self._write_outputs(summary)
        return summary

    def _write_outputs(self, summary):
        # Master-and-derived (Part XXVII §E / INFRA-033): both files are views of
        # the single `summary` dict computed in synthesize(). audit_synthesis.md is
        # the human-readable view; delta_proposals.json is the machine view of its
        # delta_proposals. Neither is an independent source: both render from
        # `summary`, so they cannot disagree.
        if self.run_context is not None:
            synthesis_path = self.run_context.audit_synthesis_path()
            deltas_path = self.run_context.delta_proposals_path()
        else:
            audit_dir = self.project_root / "output" / "audit"
            synthesis_path = audit_dir / "audit_synthesis.md"
            deltas_path = audit_dir / "delta_proposals.json"
        synthesis_path.parent.mkdir(parents=True, exist_ok=True)
        import run_options
        synthesis_path.write_text(_render_md(summary, output_language=run_options.for_context(self.run_context).output_language), encoding="utf-8")
        deltas_path.write_text(
            json.dumps({"generated_at": summary["generated_at"], "proposals": summary["delta_proposals"]},
                       indent=2, ensure_ascii=False), encoding="utf-8")


def escalation_key(body):
    """(topic, payload) of one escalation, or None when it carries no topic or no
    payload (reader check RD3: nothing to recur on). Repeated copies of one
    escalation share a key, so they are counted once."""
    body = body if isinstance(body, dict) else {}
    topic, payload = body.get("topic"), body.get("payload")
    if not topic or payload in (None, "", {}, []):
        return None
    return (str(topic), json.dumps(payload, sort_keys=True, default=str))


def _count_disputed_by_source(findings):
    from urllib.parse import urlparse
    out = {}
    for f in findings:
        if f.get("verdict") != "DISPUTED": continue
        src = f.get("source_url") or f.get("evidence", "")
        host = ""
        if src:
            try: host = urlparse(src).netloc.lower()
            except ValueError: host = ""
        out[host or "unknown"] = out.get(host or "unknown", 0) + 1
    return out


AUDIT_COUNT_NOTE = (" (patterns in this run's audit trail, such as repeated escalations; "
                    "not findings about the document under review, which are in each "
                    "document's document_summary.md)")
# Reader check RC9: how a governance proposal and its priority READ in this file.
# The kinds and actions themselves (propose_amendment, add_amendment, ...) are the
# governance vocabulary and stay exactly as they are in delta_proposals.json; only
# the words a reader sees here change, so "amendment" never collides with the
# document amendments in review_findings.md.
KIND_WORDS = {"propose_amendment": "rule-book (constitution) change proposal",
              "append_project_rule": "project rule proposal",
              "codify_tf_law": "task-force law proposal",
              "reduce_ttl": "verification cache proposal",
              "tighten_processor_prompt": "extraction prompt proposal"}
ACTION_WORDS = {"add_amendment": "add a constitution amendment (the operator decides)",
                "append_rule": "add a project rule (the operator decides)",
                "codify_pattern": "write the pattern down as a task-force law (the operator decides)",
                "reduce_for_source": "shorten how long this source's checks are cached",
                "add_completeness_check": "add a completeness check to the extraction prompt"}


@localization.presentation
def _render_md(summary):
    # S2a, item 6: the count here is of PATTERNS in the run's audit trail (repeated
    # escalations, repeated verdicts, repeated proposals), never of findings about
    # the document under review, and it says so where the number is shown.
    lines = [localization.text('# Audit synthesis'), "", f'{localization.text('- generated: ')}{summary['generated_at']}',
             f'{localization.text('- bus messages: ')}{summary['bus_messages']}',
             f'{localization.text('- audit-trail patterns: ')}{len(summary['findings'])}{localization.text(AUDIT_COUNT_NOTE)}',
             f'{localization.text('- DELTA proposals: ')}{len(summary['delta_proposals'])}',
             *([f"{localization.text('- escalation messages with no topic or no content (not counted as a pattern): ')}"
                f"{summary['content_free_escalations']}"] if summary.get('content_free_escalations') else []), "",
             localization.text('## Audit-trail patterns (not document findings)')]
    if not summary["findings"]: lines.append(localization.text('_no audit-trail patterns this run_'))
    else:
        for f in summary["findings"]:
            lines.append(f"- {localization.text('pattern priority: ')}{localization.label(str(f['severity'])).lower()}; "
                         f"{localization.text('area: ')}{localization.label(str(f['category'])).lower()}; "
                         f"{localization.message(f['summary'])}")
    lines.append(localization.text('\n## DELTA proposals'))
    if not summary["delta_proposals"]: lines.append(localization.text('_no DELTAs proposed this run_'))
    else:
        for d in summary["delta_proposals"]:
            kind, action = d['kind'], d['proposed_change'].get('action')
            lines.append(f"### {d['id']}: {localization.text(KIND_WORDS.get(kind, kind))}")
            lines.append(f'{localization.text('- trigger: ')}{localization.message(d['trigger'])}')
            lines.append(f'{localization.text('- proposed change: ')}{localization.text(ACTION_WORDS.get(action, str(action)))}')
            lines.append(f'{localization.text('- target: ')}{d['proposed_change'].get('target')}')
            lines.append(f'{localization.text('- requires operator approval: ')}'
                         f'{localization.text('yes' if d['requires_operator_approval'] else 'no')}\n')
    return "\n".join(lines)
