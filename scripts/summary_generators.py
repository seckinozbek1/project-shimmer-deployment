"""Context summary and operative summary generators (Part XVIII Section C).

Each summary cites specific references (REF-* and CONV-*) so the reader can
trace any claim back to its source. The actual prose is produced by PROCESSOR
in production runs; these helpers provide the deterministic structural shell
that always carries the citation grid.
"""

from __future__ import annotations

import localization
from datetime import datetime, timezone
from typing import Any, Iterable

import finding_record


def _now(): return datetime.now(timezone.utc).isoformat()


@localization.presentation
def render_context_summary(
    *,
    document_id: str,
    document_name: str,
    context_refs: list[dict],
    topics: list[str] | None = None,
    body_text: str = "",
) -> str:
    topics = topics or []
    lines = [f'# {document_name}{localization.text(' — Context summary')}', "",
             f'{localization.text('- generated: ')}{_now()}',
             f'{localization.text('- document id: ')}{document_id}',
             f'{localization.text('- context references cited: ')}{len(context_refs)}',
             "",
             localization.text("## What the reference corpus establishes about this document's topics"),
             ""]
    if topics:
        lines.append(localization.text('**Topics addressed:**'))
        for t in topics:
            lines.append(f"- {t}")
        lines.append("")
    if body_text.strip():
        lines.append(localization.message(body_text.strip()))
        lines.append("")
    lines.append(localization.text('## Reference citations (from context corpus)'))
    lines.append("")
    if not context_refs:
        lines.append(localization.text('_no context references cited_'))
    else:
        for ref in context_refs:
            loc = ref.get("location", {}) or {}
            page = loc.get("page", "?"); para = loc.get("paragraph", "?")
            lines.append(
                f'- **[{ref.get('ref_id')}]** {ref.get('document_name', '?')}{localization.text(' (p')}{page}{localization.text(', para ')}{para}): {ref.get('text_excerpt', '')[:240]}'
            )
    return "\n".join(lines)


@localization.presentation
def render_operative_summary(
    *,
    document_id: str,
    document_name: str,
    conventions_by_category: dict[str, list[dict]],
    findings: list[dict],
    body_text: str = "",
    question: str = "",
    prior_refusals: list | None = None,
    prior_orphans: list | None = None,
) -> str:
    """A finding must never disappear between the bus and this file. The category
    it was found under is only ever known via each finding's own `category` field
    (set by the caller: a real registry category, or "unclassified" when the
    source agent left conv_id unset -- see pipeline.py's _process_doc). This
    RENDERS every category any finding actually carries, not only the registry's
    own declared categories: a finding tagged "unclassified" has no matching entry
    in `conventions_by_category` (no registry convention IS "unclassified"), so
    iterating only conventions_by_category's own keys silently dropped it. The
    render loop below iterates the UNION instead, and the two counts in the
    header/body are asserted equal, not merely hoped equal: a RuntimeError beats
    a silently incomplete deliverable."""
    lines = [f'# {document_name}{localization.text(' — Operative summary')}', "",
             f'{localization.text('- generated: ')}{_now()}',
             f'{localization.text('- document id: ')}{document_id}',
             f'{localization.text('- convention categories evaluated: ')}{len(conventions_by_category)}',
             f'{localization.text('- findings: ')}{len(findings)}',
             ""]
    # R6: the operator's framing question for a review run is echoed, never parsed.
    if (question or "").strip():
        lines += [localization.text('## Operator question'), "", question.strip(), ""]
    lines += [localization.text('## What the document says, organized by convention category'), ""]
    if body_text.strip():
        lines.append(localization.message(body_text.strip()))
        lines.append("")
    categories = set(conventions_by_category) | {f.get("category") or "unclassified" for f in findings}
    rendered_count = 0
    for category in sorted(categories):
        conventions = conventions_by_category.get(category, [])
        lines.append(f"### {category}")
        lines.append("")
        if conventions:
            for c in conventions:
                lines.append(f"- **[{c.get('id')}]** ({c.get('severity', '?')}/{c.get('action', '?')}): "
                             f"{c.get('rule', '')[:240]}")
        else:
            lines.append(localization.text('_no conventions in this category_'))
            lines.append("")
        category_findings = [f for f in findings if (f.get("category") or "unclassified") == category]
        if category_findings:
            lines.append("")
            lines.append(localization.text('**Findings:**'))
            for f in category_findings:
                refs = ", ".join(f.get("ref_ids", []) or [])
                # structure H3: a typed Finding record is rendered from its FIELDS,
                # with `explanation` as the prose, rather than from whichever
                # free-text field happened to survive normalisation. A finding that
                # is not a typed record renders exactly as it did before.
                typed = finding_record.typed_line(f) if finding_record.is_finding(f) else ""
                if typed:
                    prose = (f.get("explanation") or f.get("reasoning") or "")[:240]
                    lines.append(f"- {typed}")
                    if prose:
                        lines.append(f"  - {prose}")
                else:
                    lines.append(f'- {f.get('verdict', '?')}{localization.text(' on [')}{f.get('conv_id', '?')}{localization.text('] at refs [')}{refs}]: {f.get('reasoning', '')[:240]}')
                rendered_count += 1
        lines.append("")
    # R6 / INFRA-044: the comparison with the operator-declared earlier version, an
    # UNCOUNTED section (every prior record is already rendered once above under its
    # category, so the header count still equals the rendered count). Rendered only
    # when there is a comparison to show, so every existing caller is byte-stable.
    has_prior = (prior_refusals or prior_orphans or any(
        f.get("relation") in finding_record.PRIOR_RELATIONS and f.get("provenance") == "computed"
        for f in findings))
    if has_prior:
        outside = [f for f in findings
                   if f.get("relation") in finding_record.OUTSIDE_BAND_RELATIONS
                   and str(f.get("record_verdict") or "").lower() == "irregular"]
        lines.extend(finding_record.render_prior_comparison(
            findings, refusals=prior_refusals, orphans=prior_orphans, outside=outside,
            heading=localization.text('## Compared with the earlier version')))
    if rendered_count != len(findings):
        raise RuntimeError(
            f'{localization.text('render_operative_summary: header claims ')}{len(findings)}{localization.text(' findings but only ')}{rendered_count}{localization.text(' were rendered; a finding would have been silently dropped')}')
    return "\n".join(lines)
