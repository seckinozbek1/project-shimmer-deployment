"""Interface awareness, never an instruction to trust an adjacent conclusion.

Responsibilities/exclusions and output shapes remain registry/contract-owned.
The routing map names current artifacts, not new dependencies or activation rules.
"""

import agent_activation

VERSION = 1
INTERFACES = {
    "PROCESSOR": ("source documents; ARCHIVIST structural inventory when supplied; explicit case records when requested", "typed draft or explicitly requested case interpretations/advisory proposals", "VERIFIER; FACT_CHECKER; per-agent report; explicit case projection"),
    "ARCHIVIST": ("corpus digest and document population", "structural inventory", "LEGAL_ANALYST; wide PRACTICE_AUDITOR; bus"),
    "INST_FINDER": ("corpus digest", "institution registry", "audit bus context; no direct amendment consumer"),
    "CITATION_RESOLVER": ("document and reference passages", "citation graph", "audit bus context; no direct amendment consumer"),
    "SPEECH_ACT_TAGGER": ("document text", "speech-act tags", "per-agent report and bus; no policy decision consumer"),
    "LEGAL_ANALYST": ("document; structural inventory; retrieved references; parent finding for deepening", "legal findings", "legal deepening; amendments; per-agent report; bus"),
    "VERIFIER": ("PROCESSOR typed draft and source excerpts; explicitly supplied review proposals", "fidelity findings", "audit synthesis; amendments; report; bus"),
    "FACT_CHECKER": ("PROCESSOR draft; provided sources and configured evidence access", "factual findings", "audit synthesis; amendments; web reference index; report; bus"),
    "PRACTICE_AUDITOR": ("document; convention registry; structural inventory in wide review", "conformance findings", "amendments; audit synthesis; bus"),
    "STYLE_GUARDIAN": ("document; assigned wording conventions; scoped reference excerpts", "wording findings", "amendments; bus"),
    "REDACTOR": ("operator redaction rules and document spans", "proposed redaction spans", "local privacy scrub and validation"),
    "AMENDMENT_DRAFTER": ("accepted referenced findings from auditors and LEGAL_ANALYST", "allowed amendment wording fields", "canonical amendment master and tracked-change renderer")}
_RANKS = ("EDITOR_CLERK", "EDITOR_HEAD_OF_UNIT", "EDITOR_HEAD_OF_SECTION", "EDITOR_HEAD_OF_DEPARTMENT", "EDITOR_DEPUTY_DG", "EDITOR_DG")
for _i, _rank in enumerate(_RANKS):
    INTERFACES[_rank] = ("assembled master" + ("; accumulated observations from " + _RANKS[_i-1] if _i else ""),
                        "advisory editorial observations",
                        "board consolidation and report" + ("; conditional " + _RANKS[_i+1] if _i+1 < len(_RANKS) else "; terminal board verdict"))


def brief(name, spec, contract):
    upstream, artifact, downstream = INTERFACES.get(name, (
        "only the calling subsystem's supplied payload", "the declared output contract",
        "calling subsystem; no additional agent interface declared"))
    return dict(version=VERSION, agent=name, responsibility=list(spec.get("does", [])),
                excluded=list(spec.get("does_not", [])), upstream=upstream, artifact=artifact,
                downstream=downstream, consumer_contract=agent_activation._PURPOSES.get(name, "advisory_board_and_deliverable"),
                output_required=list(contract.get("required", [])),
                output_kind=contract.get("item_kind"))


def render(name, spec, contract):
    item = brief(name, spec, contract)
    # DO/DO NOT and full output schema already occur in the stable agent block.
    return ("## Agent execution brief v1\n"
            "RECEIVES: " + item["upstream"] + ".\n"
            "PRODUCES: " + item["artifact"] + ". CONSUMERS: " + item["downstream"] + ".\n"
            "Use only typed artifacts actually supplied; interface names do not imply their availability, "
            "correctness or authority. Check evidence independently within your registered responsibility. "
            "Do not repeat adjacent deliverables or adopt their conclusions merely because of their author. "
            "Preserve competing interpretations and identify missing evidence. Cite supplied evidence IDs; "
            "never invent sources. Follow the current call's output contract and registered exclusions. "
            "Report insufficiency/refusal using that contract; an empty list is not a shortcut. "
            "Governed editorial rank authority, where applicable, remains distinct from factual proof.")
