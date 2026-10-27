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


# S2a, item 2: the sentences that name who produced a document's findings are
# generated from the findings themselves (each stamped `written_by` from the
# envelope it was posted under), never from a fixed list of agent names. Both
# sentences have a rendering in the second output language (tr) in
# scripts/ui/localization_catalog.js.
NO_MODEL_AGENT = "no model agent"
# Reader check RD1/RD4: a model's note beside Python's figures names the model the
# record says wrote it; with none recorded, it says so
# (finding_record.NOTE_MODEL_NOT_RECORDED).
NO_NOTE_MODEL = "none"
RULES_APPLIED_HEADING = "## Rules applied"
RULE_TEXT_LABEL = "rule text: "


def model_note_line(text, model=None) -> str:
    return (localization.text("A model's note (model: ") + str(model or localization.text(finding_record.NOTE_MODEL_NOT_RECORDED))
            + localization.text("), not checked by Python: ") + '"' + str(text) + '"')


def findings_provenance(findings) -> dict:
    """Counts by who wrote them: Python's findings, the items a model wrote (and
    the agents whose replies carried them), and the model-written NOTES attached
    to Python's findings with the models the records name for them (RD4)."""
    findings = [f for f in findings or [] if isinstance(f, dict)]
    model = [f for f in findings if finding_record.is_model_written(f)]
    notes = [f for f in findings if not finding_record.is_model_written(f)
             and f.get("explanation_by") == finding_record.WRITTEN_BY_MODEL]
    return {"total": len(findings), "computed": len(findings) - len(model),
            "model": len(model),
            "model_agents": sorted({str(f.get("agent") or "?") for f in model}),
            "notes": len(notes),
            "note_models": sorted({str(f.get("explanation_model") or finding_record.NOTE_MODEL_NOT_RECORDED) for f in notes})}


def _agents_text(provenance):
    return ", ".join(provenance["model_agents"]) or NO_MODEL_AGENT


def _note_models_text(provenance):
    return ", ".join(provenance.get("note_models") or []) or NO_NOTE_MODEL


def context_findings_sentence(n_conventions, provenance, document_name) -> str:
    # Reader check RC10/RD4: no bare total that mixes the kinds; the model-written
    # notes on Python's findings are counted and their models named apart.
    return ("This document was reviewed against %d conventions. Findings computed by Python "
            "from the document's figures: %d. Items written by a model (%s), not checked by "
            "Python and not promoted: %d. Model-written notes attached to Python's findings "
            "(model: %s), not checked by Python: %d. The context references below are filtered "
            "for topical relevance to %s." % (n_conventions, provenance["computed"],
                                              _agents_text(provenance), provenance["model"],
                                              _note_models_text(provenance), provenance.get("notes", 0),
                                              document_name))


def topic_line(category, conventions) -> str:
    """Reader check RC16/RD12/RD16: a rule group named by its rules and their
    quoted words, labelled as the rule's own text."""
    rules = [c for c in conventions or [] if isinstance(c, dict) and c.get("id")]
    if not rules:
        return str(category)
    shown = "; ".join('%s, %s"%s"' % (c["id"], localization.text(RULE_TEXT_LABEL),
                                       " ".join(str(c.get("rule") or "").split())[:120])
                      for c in rules[:3])
    return "%s (%s)" % (category, shown)


def relation_counts(findings) -> dict:
    """{relation: count} over typed Finding records, named from the data."""
    counts = {}
    for f in findings or []:
        # A model's record reaches the deliverables without record_verdict
        # (model_finding_for_reader), so the relation is what counts it.
        if isinstance(f, dict) and f.get("relation") in finding_record.relations():
            rel = str(f.get("relation"))
            counts[rel] = counts.get(rel, 0) + 1
    return dict(sorted(counts.items()))


RELATIONS_FOUND_HEADING = "## Relations found (computed by Python)"
RELATIONS_MODEL_HEADING = "## Relations a model reported (written by a model, not checked by Python)"


@localization.presentation
def relation_report_lines(deliverables, op_docs) -> list:
    """S2a, item 7: the run report's relations, in two lists that cannot mix.

    A relation reaches "Relations found" only from a finding Python computed. A
    relation that only a model's finding carries is listed apart and marked, so
    "sum_mismatch" written by a model is never read as a sum Python found wrong."""
    computed, model_only = {}, {}
    for doc in op_docs or []:
        info = (deliverables or {}).get(doc["id"]) or {}
        for rel, n in (info.get("relations_computed") or {}).items():
            computed[rel] = computed.get(rel, 0) + n
        for rel, n in (info.get("relations_model_only") or {}).items():
            model_only[rel] = model_only.get(rel, 0) + n
    if not computed and not model_only:
        return []
    lines = ["", localization.text(RELATIONS_FOUND_HEADING), ""]
    lines += ([f"- {finding_record.relation_words(rel)}: {n}" for rel, n in sorted(computed.items())]
              or [localization.text('- (none)')])
    lines += ["", localization.text(RELATIONS_MODEL_HEADING), ""]
    if model_only:
        mark = localization.text(finding_record.MODEL_FINDING_MARK)
        lines += [f"- {finding_record.relation_words(rel)}: {n} ({mark})" for rel, n in sorted(model_only.items())]
    else:
        lines.append(localization.text('- (none)'))
    return lines


def operative_findings_sentence(provenance) -> str:
    return ("Findings below come from the convention review. Computed by Python from the "
            "document's figures: %d. Written by a model (%s), not checked by Python and not "
            "promoted, listed apart under each category: %d. Model-written notes attached to "
            "Python's findings (model: %s), not checked by Python: %d. Each finding cites the "
            "convention ID and the reference ID(s) and says who wrote it."
            % (provenance["computed"], _agents_text(provenance), provenance["model"],
               _note_models_text(provenance), provenance.get("notes", 0)))


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
    lines = [f'# {document_name}{localization.text(': Context summary')}', "",
             f'{localization.text('- generated: ')}{_now()}',
             f'{localization.text('- document id: ')}{document_id}',
             f'{localization.text('- context references cited: ')}{len(context_refs)}',
             "",
             ""]
    # Reader check RD12: the list is the operator's rule book, said so; the
    # reference corpus has its own section below.
    if topics:
        lines += [localization.text(RULES_APPLIED_HEADING), ""]
        for t in topics:
            lines.append(f"- {t}")
        lines.append("")
    if body_text.strip():
        lines.append(localization.message(body_text.strip()))
        lines.append("")
    lines.append(localization.text('## Reference corpus passages cited'))
    lines.append("")
    if not context_refs:
        lines.append(localization.text('_no context references cited_'))
    else:
        for ref in context_refs:
            loc = ref.get("location", {}) or {}
            # Reader check RC15/RC13: a position part that is not on record is left
            # out rather than shown as "?", and the passage is shown as a quotation.
            where = ""
            if loc.get("page") is not None:
                where += f'{localization.text(' (p')}{loc['page']}'
                if loc.get("paragraph") is not None:
                    where += f'{localization.text(', para ')}{loc['paragraph']}'
                where += ")"
            lines.append(
                f'- **[{ref.get('ref_id')}]** {ref.get('document_name', '?')}{where}: "{ref.get('text_excerpt', '')[:240]}"'
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
    stamped = any(isinstance(f, dict) and "written_by" in f for f in findings)
    count_lines = [f'{localization.text('- findings: ')}{len(findings)}']
    if stamped:
        # Reader check RC10: never one total that mixes Python's findings with
        # items a model wrote.
        n_model = sum(1 for f in findings if finding_record.is_model_written(f))
        count_lines = [f'{localization.text('- findings computed by Python: ')}{len(findings) - n_model}',
                       f'{localization.text('- items written by a model (not checked by Python): ')}{n_model}']
    lines = [f'# {document_name}{localization.text(': Operative summary')}', "",
             f'{localization.text('- generated: ')}{_now()}',
             f'{localization.text('- document id: ')}{document_id}',
             f'{localization.text('- convention categories evaluated: ')}{len(conventions_by_category)}',
             *count_lines,
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
        # Reader check RD18: the heading says what the slug is (the operator's
        # own rule group id); the rules and their words follow.
        lines.append(f"### {localization.text('Rule group ')}{category}" if stamped else f"### {category}")
        lines.append("")
        if conventions:
            for c in conventions:
                # Reader check RC15: a part the registry does not carry is left out,
                # never shown as "?"; the rule's own words are quoted.
                declared = "/".join(localization.label(str(c[k])) for k in ("severity", "action") if c.get(k))
                lines.append(f"- **[{c.get('id')}]**" + (f" ({declared})" if declared else "")
                             + f': {localization.text(RULE_TEXT_LABEL)}"{c.get('rule', '')[:240]}"' if stamped else
                             f"- **[{c.get('id')}]** ({c.get('severity', '?')}/{c.get('action', '?')}): "
                             f"{c.get('rule', '')[:240]}")
        else:
            lines.append(localization.text('_no conventions in this category_'))
            lines.append("")
        category_findings = [f for f in findings if (f.get("category") or "unclassified") == category]
        if category_findings and stamped:
            # Reader check RC6: Python's findings and a model's items are listed
            # apart, in plain fields, the model's without a verdict, its sentence
            # quoted as the model's, and with a note when the unit it names does
            # not state its figures.
            computed = [f for f in category_findings if not finding_record.is_model_written(f)]
            model = [f for f in category_findings if finding_record.is_model_written(f)]
            if computed:
                lines += ["", localization.text('**Findings computed by Python:**')]
                for f in computed:
                    lines.append(f"- {finding_record.reader_line(f)} ({finding_record.provenance_mark(f)})")
                    prose = str(f.get("explanation") or f.get("reasoning") or "")[:240]
                    if prose and f.get("explanation_by") == finding_record.WRITTEN_BY_MODEL:
                        # The judging model's sentence beside Python's figures is the
                        # model's, said so and quoted (reader check RC5).
                        lines.append("  - " + model_note_line(prose, f.get("explanation_model")))
                    elif prose:
                        lines.append(f"  - {localization.message(prose)}")
                    rendered_count += 1
            if model:
                lines += ["", localization.text('**Written by a model, not checked by Python, not promoted:**')]
                for f in model:
                    lines.append(f"- {finding_record.reader_line(f)} ({finding_record.provenance_mark(f)})")
                    prose = str(f.get("explanation") or f.get("reasoning") or "").strip()[:240]
                    if prose:
                        lines.append(f'  - {localization.text("The model wrote: ")}"{prose}"')
                    # Reader check RD2: what Python can say about the item, in words.
                    for note in f.get("reader_notes") or []:
                        lines.append(f"  - {localization.message(note)}")
                    if f.get("figures_in_unit") is False and not f.get("reader_notes"):
                        lines.append(f'  - {localization.text("The unit it names does not state these figures.")}')
                    rendered_count += 1
        elif category_findings:
            lines.append("")
            lines.append(localization.text('**Findings:**'))
            for f in category_findings:
                refs = ", ".join(f.get("ref_ids", []) or [])
                # structure H3: a typed Finding record is rendered from its FIELDS,
                # with `explanation` as the prose, rather than from whichever
                # free-text field happened to survive normalisation. A finding that
                # is not a typed record renders exactly as it did before.
                typed = finding_record.typed_line(f) if finding_record.is_finding(f) else ""
                # S2a: every finding says who wrote it. A model's finding is never
                # removed from view; it is labelled, in this file as in every other.
                mark = finding_record.provenance_mark(f) if "written_by" in f else ""
                if typed:
                    prose = (f.get("explanation") or f.get("reasoning") or "")[:240]
                    if prose and not finding_record.is_model_written(f):
                        # Python's own sentence has a catalog rendering; a model's
                        # sentence is source content and stays exactly as written.
                        prose = localization.message(prose)
                    lines.append(f"- {typed}" + (f" ({mark})" if mark else ""))
                    if prose:
                        lines.append(f"  - {prose}")
                else:
                    lines.append(f'- {f.get('verdict', '?')}{localization.text(' on [')}{f.get('conv_id', '?')}{localization.text('] at refs [')}{refs}]: {f.get('reasoning', '')[:240]}'
                                 + (f" ({mark})" if mark else ""))
                rendered_count += 1
        lines.append("")
    # R6 / INFRA-044: the comparison with the operator-declared earlier version, an
    # UNCOUNTED section (every prior record is already rendered once above under its
    # category, so the header count still equals the rendered count). Rendered only
    # when there is a comparison to show, so every existing caller is byte-stable.
    has_prior = (prior_refusals or prior_orphans or any(
        f.get("relation") in finding_record.PRIOR_RELATIONS and f.get("provenance") == "computed"
        and f.get("written_by") != finding_record.WRITTEN_BY_MODEL
        for f in findings))
    if has_prior:
        # S2 checker A5: a model's band claim is listed (marked) under the model
        # items, never here, where every line is Python's.
        outside = [f for f in findings
                   if f.get("relation") in finding_record.OUTSIDE_BAND_RELATIONS
                   and str(f.get("record_verdict") or "").lower() == "irregular"
                   and f.get("written_by") != finding_record.WRITTEN_BY_MODEL]
        lines.extend(finding_record.render_prior_comparison(
            findings, refusals=prior_refusals, orphans=prior_orphans, outside=outside,
            heading=localization.text('## Compared with the earlier version')))
    if rendered_count != len(findings):
        raise RuntimeError(
            f'{localization.text('render_operative_summary: header claims ')}{len(findings)}{localization.text(' findings but only ')}{rendered_count}{localization.text(' were rendered; a finding would have been silently dropped')}')
    return "\n".join(lines)
