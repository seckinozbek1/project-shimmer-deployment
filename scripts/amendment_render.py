"""Canonical-master amendment renders (genesis Part XXVII §E / INFRA-033).

THE SINGLE CANONICAL MASTER for a document's convention-review result is the
`amendments_payload` dict, the same object serialized verbatim as
`deliverables/<doc_id>/review_data.json` (BP-16 per-document subfolder, doc-name
prefix stripped). The human-facing renders (`.md`, `.docx`) are PURE
FUNCTIONS of that master: master in → format out. They read amendment content
from NOWHERE else, so the three files cannot disagree.

`write_amendment_deliverables()` is the SINGLE ENTRY POINT that writes all three
formats from one `payload` object. Every per-run deliverable writer routes
through it; nothing else writes amendments.* files. This is the drift guard: a
future edit cannot reintroduce independent generation without going through (and
contradicting) this one function, which asserts the renders reflect the master.

Presentation-only inputs (NOT amendment content; they cannot change which
amendments appear):
  - document_name : heading text (cosmetic).
  - body_text     : the ORIGINAL document text, the canvas the .docx anchors
                    tracked-change marks into. It positions revision marks; it
                    never supplies an amendment. Amendments that do not anchor in
                    the body still render (in an "Additional amendments" section),
                    so the .docx always reflects the FULL master amendment set.
  - category_for_conv : optional callable conv_id -> human-readable category
                    label, used only to decorate a convention_ref that is ALREADY
                    in the master. Injected so this module stays decoupled from
                    the convention-registry shape.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# BP-16: the per-document deliverable layout (subfolder + stripped basenames)
# is owned by run_context, so the writer and the pipeline agree on one source.
from run_context import DELIVERABLE_FILENAMES
import finding_record
import run_options
import localization

# Master fields every render reads. The renders consult only these keys for
# content; anything else they receive is presentation-only (see module docstring).
# R6 / INFRA-044: the prior-version comparison (ok-verdict records, refusals and
# orphans) is part of the master too, rendered in its own section of the .md and
# never counted as an amendment; the .docx tracked changes read amendments only.
CANONICAL_CONTENT_KEYS = ("document_id", "amendments", "_validator_errors",
                          "prior_comparisons", "prior_refusals", "prior_orphans",
                          "model_findings_not_promoted")
# S2a: the master's list of findings a MODEL wrote for this document. None of them
# became an amendment (only Python's computed findings are promoted, check 269);
# they are kept in the master and rendered, labelled, never removed from view.
MODEL_FINDINGS_KEY = "model_findings_not_promoted"
MODEL_FINDINGS_HEADING = "## Written by a model: not checked by Python, not promoted"


@localization.presentation
def render_model_findings(findings) -> list:
    """The labelled section for the master's model findings, as lines. [] when
    there are none, so a run with no model finding renders exactly as before.
    Reader check RC6/RC7: plain fields, no verdict, the model's sentence quoted
    as the model's, and a note when the unit it names does not state its figures."""
    findings = [f for f in findings or [] if isinstance(f, dict)]
    if not findings:
        return []
    mark = localization.text(finding_record.MODEL_FINDING_MARK)
    lines = ["", localization.text(MODEL_FINDINGS_HEADING), "", mark, ""]
    for f in findings:
        agent = f.get("agent") or "?"
        lines.append(f"- [{agent}] {finding_record.reader_line(f)} ({mark})")
        prose = str(f.get("explanation") or f.get("reasoning") or "").strip()
        if prose:
            lines.append(f'  - {localization.text("The model wrote: ")}"{prose[:240]}"')
        # Reader check RD2: what Python can say about the item, in words.
        for note in f.get("reader_notes") or []:
            lines.append(f"  - {localization.message(note)}")
        if f.get("figures_in_unit") is False and not f.get("reader_notes"):
            lines.append(f'  - {localization.text("The unit it names does not state these figures.")}')
    return lines


def render_amendments_md(payload: dict, *, document_name: str = "",
                         category_for_conv: Callable[[str], Any] | None = None,
                         output_language: str = "en") -> str:
    """Pure render of the canonical master `payload` to Markdown.

    Content comes solely from `payload`; `document_name` is the cosmetic heading
    and `category_for_conv` only decorates a convention_ref already in the master.
    """
    run_options.Options(output_language=output_language)
    return _render_md(payload, document_name, category_for_conv, output_language=output_language)


# The amendment fields the layout shows under their own labels, and (RD8) the
# fields of the typed record the evidence sentence says in words. Any OTHER field
# is listed after it, so the rendered file still carries the whole master.
_SHOWN_FIELDS = ("convention_ref", "location", "action", "original_text", "proposed_text",
                 "comment", "context_refs", "severity", "finding_type", "uncertain")
_EVIDENCE_FIELDS = ("ref", "kind", "confidence", "ref_ids", "derived_from", "finding_unit_id",
                    "finding_rule_id", "finding_relation", "finding_field_label", "finding_value_a",
                    "finding_unit_a", "finding_value_b", "finding_unit_b", "agent",
                    "source_convention_ref", "unit_id_repaired_to")


@localization.presentation
def evidence_sentence(amendment) -> str:
    """Reader check RD8: the typed record behind an amendment, in words."""
    if not amendment.get("finding_relation"):
        return ""
    record = {"rule_id": amendment.get("finding_rule_id") or amendment.get("convention_ref"),
              "source_rule_id": amendment.get("source_convention_ref"),
              "unit_id": amendment.get("finding_unit_id"),
              "relation": amendment.get("finding_relation"), "record_verdict": "irregular",
              "field_label": amendment.get("finding_field_label"),
              "value_a": amendment.get("finding_value_a"), "unit_a": amendment.get("finding_unit_a"),
              "value_b": amendment.get("finding_value_b"), "unit_b": amendment.get("finding_unit_b"),
              "source_refs": amendment.get("ref_ids") or [],
              # RD18: figures as the passage and the comment (which quotes the rule) write them
              "_written_tokens": re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])",
                                            str(amendment.get("original_text") or "") + " "
                                            + str(amendment.get("comment") or "")),
              "written_by": (finding_record.WRITTEN_BY_PYTHON
                             if amendment.get("derived_from") == "computed_finding"
                             else finding_record.WRITTEN_BY_MODEL)}
    who = (localization.text("Python's record: ") if record["written_by"] == finding_record.WRITTEN_BY_PYTHON
           else localization.text("A model's record: "))
    return who + finding_record.reader_line(record) + localization.text(" (the full record is in review_data.json)")


@localization.presentation
def _render_md(payload, document_name, category_for_conv):
    """Reader check RC14: ONE layout for every output language (the Turkish file
    used to be JSON blocks with literal newlines and no counts). Labels go through
    the catalog; the document's own text, ids and figures are kept exactly."""
    t = localization.text
    amendments = payload.get("amendments", [])
    validator_errors = payload.get("_validator_errors", [])
    n_uncertain = sum(1 for a in amendments if a.get("uncertain"))
    title_name = document_name or payload.get("document_id", "document")
    # Reader check RD18: a file whose every entry is a flag with no proposed text
    # says it holds flagged passages, not proposed edits.
    only_flags = all(str(a.get("action") or "flag") == "flag" and not a.get("proposed_text")
                     for a in amendments)
    lines = [f"# {title_name}: {t('Flagged passages') if only_flags else t('Proposed amendments')}", "",
             f"{t('- generated: ')}{datetime.now(timezone.utc).isoformat()}",
             f"{t('- amendments: ')}{len(amendments)}",
             f"{t('- uncertain: ')}{n_uncertain}",
             f"{t('- validator errors: ')}{len(validator_errors)}"]
    if MODEL_FINDINGS_KEY in payload:
        lines.append(f"{t('- model findings not promoted: ')}{len(payload.get(MODEL_FINDINGS_KEY) or [])}")
    if validator_errors:
        lines.append("\n" + t("## Validator errors") + "\n")
        for e in validator_errors:
            lines.append(f"- {e}")
    lines.append("\n" + t("## Amendments") + "\n")
    word = "Amendment" if localization.current() != "tr" else "Değişiklik"
    for i, a in enumerate(amendments, 1):
        conv = a.get("convention_ref", "?"); loc = a.get("location", "?")
        cat = (category_for_conv(conv) if category_for_conv else None) or "?"
        sev = a.get("severity", "?")
        # Genesis Part XXV: uncertain findings carry an explicit tag in every
        # deliverable section so the operator never sees them silently merged.
        uncertain_tag = t("[UNCERTAIN] ") if a.get("uncertain") else ""
        lines.append(f"### {uncertain_tag}{word} {i} [{conv}]: "
                     f"{localization.label(str(a.get('finding_type', cat)))} ({localization.label(str(sev))})")
        lines.append("")
        lines.append(f"{t('**Location:**')} [{loc}]")
        lines.append(f"{t('**Action:**')} {localization.label(str(a.get('action', 'flag')))}")
        original = a.get('original_text') or t('(unspecified)')
        lines.append(f"{t('**Original:**')} {str(original)[:500]}")
        proposed = a.get('proposed_text')
        if proposed:
            lines.append(f"{t('**Proposed:**')} {str(proposed)[:500]}")
        lines.append("")
        lines.append(t("**Justification:**"))
        comment = a.get("comment", "(missing comment)")
        shown = localization.message(comment)
        if a.get("uncertain") and not comment.lstrip().startswith("[UNCERTAIN]"):
            shown = t("[UNCERTAIN] ") + shown
        lines.append(shown)
        lines.append("")
        if a.get("context_refs"):
            lines.append(f"{t('**Context references:**')} {', '.join(a['context_refs'])}")
        # Every other field of the master stays visible, as plain "name: value"
        # pairs (the master is canonical; nothing is hidden by the layout).
        said = evidence_sentence(a)
        rest = [f"{k}: {v}" for k, v in a.items()
                if k not in _SHOWN_FIELDS and v not in (None, "", [])
                and not (said and k in _EVIDENCE_FIELDS)]
        if said or rest:
            lines.append(f"{t('**Evidence and references:**')} " + "; ".join(
                ([said] if said else []) + ([t("other recorded fields: ") + "; ".join(rest)] if rest else [])))
        lines.append("")
    # R6: the comparison with the earlier version, from the master, through the one
    # renderer document_summary.md also uses. Its headings never carry the token
    # "Amendment ", so the drift guard's section count is unaffected.
    lines.extend(finding_record.render_prior_comparison(
        payload.get("prior_comparisons") or [],
        refusals=payload.get("prior_refusals") or [],
        orphans=payload.get("prior_orphans") or [],
        heading="## Compared with the earlier version"))
    lines.extend(render_model_findings(payload.get(MODEL_FINDINGS_KEY) or []))
    return "\n".join(lines)


@localization.presentation
def render_amendments_docx(payload: dict, output_path: Path, *,
                           title: str | None = None, body_text: str = "") -> Path:
    """Pure render of the canonical master `payload` to a tracked-changes .docx.

    The amendment set is taken from `payload["amendments"]`; `body_text` is the
    original-document canvas (see module docstring) and `title` is cosmetic.
    docx_builder is imported lazily so python-docx stays an optional dependency.
    """
    from docx_builder import build_amendments_docx
    title = title or (str(payload.get('document_id', 'document')) + ": " +
                      localization.text("Convention review (tracked changes)"))
    return build_amendments_docx(
        title=title,
        body_text=body_text or "",
        amendments=payload.get("amendments", []),
        output_path=output_path,
    )


def _md_amendment_count(md_text: str) -> int:
    """Count rendered amendment sections in a Markdown render (lines like
    '### [UNCERTAIN] Amendment 3 [CONV-1]: ...')."""
    return sum(1 for ln in md_text.splitlines()
               if ln.startswith("### ") and ("Amendment " in ln or "Değişiklik " in ln))


def write_amendment_deliverables(payload: dict, *, deliv_dir: Path, doc_id: str,
                                 document_name: str = "", body_text: str = "",
                                 category_for_conv: Callable[[str], Any] | None = None) -> dict:
    """SINGLE ENTRY POINT: write json (master) + md + docx, all DERIVED from the
    one `payload` object passed here. Returns a paths/metadata dict.

    Drift guard: the .md and .docx are produced from the SAME `payload` local
    below (there is no second content source) and an assertion confirms the .md
    reflects the master's amendment count before we return. The .docx amendment
    set is `payload["amendments"]` by construction. If a future edit tries to feed
    a render from elsewhere, it must change THIS function, and the assertion will
    fire if the render stops matching the master.
    """
    # BP-16: artifacts land in deliverables/<doc_id>/ with the doc-name prefix
    # stripped (the folder already names the document).
    doc_dir = Path(deliv_dir) / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    amendments = payload.get("amendments", [])

    json_path = doc_dir / DELIVERABLE_FILENAMES["amendments_json"]
    md_path = doc_dir / DELIVERABLE_FILENAMES["amendments_md"]
    docx_path = doc_dir / DELIVERABLE_FILENAMES["amendments_docx"]

    # (1) master, verbatim
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    # (2) markdown render, pure function of the master
    md_text = render_amendments_md(payload, document_name=document_name,
                                   category_for_conv=category_for_conv,
                                   output_language=run_options.saved(Path(deliv_dir).parent).output_language)
    md_path.write_text(md_text, encoding="utf-8")
    # (3) docx render, pure function of the master (+ body_text canvas)
    docx_error = None
    try:
        language = run_options.saved(Path(deliv_dir).parent).output_language
        render_amendments_docx(
            payload, docx_path,
            title=f"{document_name or payload.get('document_id', 'document')}: "
                  + localization.text("Convention review (tracked changes)", language),
            body_text=body_text,
            output_language=language,
        )
    except Exception as e:  # python-docx missing or build failure: never fatal
        docx_error = f"{type(e).__name__}: {e}"

    # Drift guard: the md MUST reflect the master amendment count.
    assert _md_amendment_count(md_text) == len(amendments), (
        "amendment render drifted from canonical master "
        f"(md sections={_md_amendment_count(md_text)}, master amendments={len(amendments)})"
    )

    return {
        "amendments_json": str(json_path),
        "amendments_md": str(md_path),
        "amendments_docx": str(docx_path) if docx_path.exists() else None,
        "amendment_count": len(amendments),
        "docx_error": docx_error,
    }
