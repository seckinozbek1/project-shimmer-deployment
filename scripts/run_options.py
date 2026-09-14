"""Run-level public language and brief configuration. No language guessing."""
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import threading
import localization

_LOCK = threading.RLock()


@dataclass(frozen=True)
class Options:
    input_language: str = "auto"
    output_language: str = "en"
    agent_briefs: str = "enabled"

    def __post_init__(self):
        if not isinstance(self.input_language, str) or self.input_language not in {"auto", "en", "tr"}:
            raise ValueError("invalid_input_language")
        if not isinstance(self.output_language, str) or self.output_language not in {"en", "tr"}:
            raise ValueError("invalid_output_language")
        if not isinstance(self.agent_briefs, str) or self.agent_briefs not in {"enabled", "disabled"}:
            raise ValueError("invalid_agent_briefs")


def normalize(input_language=None, output_language=None, agent_briefs=None):
    return Options(input_language if input_language is not None else "auto",
                   output_language if output_language is not None else "en",
                   agent_briefs if agent_briefs is not None else "enabled")


def configure(ctx, input_language="auto", output_language="en", agent_briefs="enabled"):
    options = Options(input_language, output_language, agent_briefs)
    ctx.run_options = options
    path = ctx.audit_dir() / "run_options.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(schema_version=1, **asdict(options)), indent=2) + "\n", encoding="utf-8")
    return options


def for_context(ctx):
    return getattr(ctx, "run_options", Options())


def saved(run_dir):
    path = Path(run_dir) / "audit/run_options.json"
    if not path.exists():
        return Options()
    value = json.loads(path.read_text(encoding="utf-8"))
    version = value.pop("schema_version", None)
    if type(version) is not int or version != 1:
        raise ValueError("invalid_run_options_schema")
    return Options(**value)


def instruction(options):
    language = {"en": "English", "tr": "Turkish (Türkçe)"}[options.output_language]
    return ("## Run output language\nWrite user-facing explanations, summaries, trajectory narratives "
            "and requested advisory options in " + language + ". "
            "Input language is " + options.input_language + "; auto means read the supplied multilingual "
            "text directly, including mixed-language material, without a forced language classification. "
            "Keep source quotations in their original language. Never translate identifiers, JSON field names, "
            "enums, numbers, units or provenance. This controls public output only, not internal reasoning. "
            "Missing evidence stays missing in every language.")


LABELS = {
    "en": {"OBSERVED": "Observed evidence", "INTERPRETED": "Interpretation", "DERIVED": "Derived comparison",
           "STRATEGIC_OPTION": "Strategic option", "RECOMMENDATION": "Recommendation", "evidence": "Evidence",
           "trajectory": "Trajectory", "options": "Strategic options", "assumptions": "Assumptions",
           "risk": "Principal risk", "upside": "Expected upside", "uncertainty": "Uncertainty",
           "concession": "Concession", "hardening": "Hardening", "review": "Review", "references": "References"},
    "tr": {"OBSERVED": "Gözlemlenen kanıt", "INTERPRETED": "Yorum", "DERIVED": "Türetilmiş karşılaştırma",
           "STRATEGIC_OPTION": "Stratejik seçenek", "RECOMMENDATION": "Öneri", "evidence": "Kanıt",
           "trajectory": "Süreç içindeki değişim", "options": "Stratejik seçenekler", "assumptions": "Varsayımlar",
           "risk": "Başlıca risk", "upside": "Beklenen yarar", "uncertainty": "Belirsizlik",
           "concession": "Taviz", "hardening": "Tutumun sertleşmesi", "review": "İnceleme", "references": "Kaynaklar"}}
LABELS["en"].update(accepted="Accepted", rejected="Rejected", refused="Refused", unresolved="Unresolved",
                    insufficient_evidence="Insufficient evidence", recommendation_unavailable="Recommendation unavailable",
                    strategic_options="Strategic options", recommendation="Recommendation", unknown="Unknown",
                    not_comparable="Not comparable", trajectory_only="Trajectory only", decision_support="Decision support")
LABELS["tr"].update(accepted="Kabul edildi", rejected="Reddedildi", refused="Yanıt verilemedi", unresolved="Çözümlenmedi",
                    insufficient_evidence="Kanıt yetersiz", recommendation_unavailable="Öneri sunulamıyor",
                    strategic_options="Stratejik seçenekler", recommendation="Öneri", unknown="Bilinmiyor",
                    not_comparable="Karşılaştırılamaz", trajectory_only="Yalnızca süreç analizi", decision_support="Karar desteği")


def label(key, language="en"):
    Options(output_language=language)
    return LABELS[language].get(key, localization.label(key, language))


def review_markdown(payload, document_name="", language="tr"):
    """Localized headings around the unchanged canonical master, including all fields.

    JSON blocks preserve numeric values, quotations, IDs and enums verbatim.
    A fence longer than any content backtick run prevents source text escaping it.
    """
    import re
    Options(output_language=language)
    def block(value):
        text = json.dumps(value, ensure_ascii=False, indent=2)
        fence = "`" * max(3, 1 + max((len(m[0]) for m in re.finditer(r"`+", text)), default=0))
        return fence + "json\n" + text + "\n" + fence
    lines = ["# " + label("review", language), block(document_name or payload.get("document_id", "")), ""]
    for i, amendment in enumerate(payload.get("amendments", []), 1):
        title = "Değişiklik" if language == "tr" else "Amendment"
        headings = ({"original_text": "Özgün metin", "proposed_text": "Önerilen metin", "comment": "Gerekçe"}
                    if language == "tr" else {"original_text": "Original", "proposed_text": "Proposed", "comment": "Justification"})
        lines.append(f"### {title} {i}")
        for field, heading in headings.items():
            if amendment.get(field):
                shown = localization.message(amendment[field], language) if field == "comment" else amendment[field]
                lines.extend(["**" + heading + ":**", block(shown), ""])
        lines.extend(["**" + label("evidence", language) + ":**",
                      block({k: v for k, v in amendment.items() if k not in headings}), ""])
    lines.extend(["## " + label("evidence", language) + " / " + label("references", language),
                  block({k: v for k, v in payload.items() if k != "amendments"})])
    return "\n".join(lines)


def record_prompt(ctx, call_id, agent, stable, dynamic):
    if ctx is None:
        return
    options = for_context(ctx)
    value = dict(schema_version=1, run_id=ctx.run_id, call_id=call_id, agent=agent, brief_version=1,
                 **asdict(options), static_chars=len(stable), dynamic_chars=len(dynamic),
                 static_sha256=hashlib.sha256(stable.encode("utf-8")).hexdigest(),
                 cache_hit=None, note="Prefix identity only; cache benefit unmeasured")
    path = ctx.logs_dir() / "prompt_structure.jsonl"
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def direct_prefix(wrapper, stable, ctx):
    """Free-text Draft has its own output contract, not an agent JSON envelope."""
    import agent_briefs
    selected = for_context(ctx)
    if selected.agent_briefs == "enabled":
        stable += "\n\nYou are " + wrapper.name + ".\n" + "\n".join(wrapper.spec.get("does", []))
        stable += "\nExcluded: " + "; ".join(wrapper.spec.get("does_not", []))
        stable += "\n" + agent_briefs.render(wrapper.name, wrapper.spec, {"item_kind": "free_text_memo"})
        stable += "\nThis call returns the requested free-text memo, not a JSON envelope."
    return stable + "\n\n" + instruction(selected)
