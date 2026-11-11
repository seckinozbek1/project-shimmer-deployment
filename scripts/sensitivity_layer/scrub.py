"""LAW-IV privacy SCRUBBER + leak gate (Mechanism 1, relocated in Phase 1b).

Masking of operator-marked spans to [REDACTED], when the sensitivity layer is active,
across every operator-facing
artifact, plus the post-apply grep that VERIFIES no span survives (a survivor BLOCKs,
a span located nowhere BLOCKs). Deterministic and LOCAL: no model, no web. This is the
testable privacy core the live phase and the verify gate both exercise.

BOUNDARY (shape a, INFRA-039 corrective): this module PRODUCES scrubbed content and the
survivor verdict and HANDS THEM BACK to the pipeline; it NEVER renders the deliverable
or looks up convention categories. The editorial render (amendment_render.
write_amendment_deliverables) and convention-category lookup stay on the pipeline side.
There is no dependency edge from here into editorial logic. text_extract is neutral
infrastructure (reads a .docx so the survivor grep can see rendered text).

Mechanism 2 (the dormant mask_for_external engine, LAYER_ACTIVE=False) is a SEPARATE
concern in this package; this scrubber does NOT call it and does NOT depend on it.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import text_extract
from . import redaction_detect

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_REDACTION_PLACEHOLDER = "[REDACTED]"
# The deliverable keys (run_context.DELIVERABLE_FILENAMES, as the pipeline's per-document
# info dict carries them) of the text artifacts scrubbed on disk: not rendered from the
# master, so the master scrub does not reach them. When the sensitivity layer is active
# the reviewed document is rendered again from scrubbed inputs before this step
# (run_redaction_phase's render callback), so no span reaches it to be escaped or split;
# it stays here as the second net. A multi-round run's two deliverables are here too: that run
# refuses any sensitive or redaction-enabled run before it writes them (exit 8), so no render
# from scrubbed inputs is needed, and should that ever change they are scrubbed like the rest.
TEXT_ARTIFACT_KEYS = ("per_agent_deliverable", "reviewed_document", "context_summary",
                      "operative_summary", "version_changes", "case_positions")
# Every final on-disk artifact the survivor grep re-reads after the scrub.
VERIFY_KEYS = ("amendments_json", "amendments_md", "amendments_docx") + TEXT_ARTIFACT_KEYS


# --- Robust, deterministic, LOCAL span matching (no model, no web; LAW-IV) ------
# A 7B clerk's span rarely matches the document byte-for-byte: it drops a leading
# definite article, merges a name with an adjacent id across connective text, and
# varies whitespace/diacritics. Literal `target in text` silently misses those. The
# tolerant matcher below stays deterministic and bounded; it is LANGUAGE-NEUTRAL by
# construction - every script/diacritic/article string it needs comes from the DATA
# resource (redaction_detect.normalization_classes), never from a literal in code.
_NORM_CLASSES = None


def _norm_classes():
    """Language-neutral normalization building blocks, loaded once from the per-
    language DATA resource (config/language_redaction_cues.json). No literals here."""
    global _NORM_CLASSES
    if _NORM_CLASSES is None:
        _NORM_CLASSES = redaction_detect.normalization_classes(_PROJECT_ROOT)
    return _NORM_CLASSES


# The universal ASCII separators a connective gap admits, as a character-class body: the
# hyphen, underscore and dot that join words in an identifier, and the backslash of a JSON
# escape (a line break written `\\n` in a record's JSON is a backslash and a letter).
_SEPARATORS = r",/\-_.\\"
# Characters a reader cannot see, as a character-class body: the soft hyphen, the zero-width
# and direction marks, the word joiner and the byte-order mark. They may stand anywhere.
_INVISIBLE = "\u00ad\u200b-\u200f\u2060\ufeff"


def _redaction_span_regex(span):
    """Compile a tolerant, BOUNDED regex for one redaction span: an optional leading
    definite article (DATA) whether or not the span writes one, tokens read with their
    diacritics (DATA) optional on either side, invisible characters tolerated anywhere, and
    a bounded connective gap between tokens (whitespace + the configured script range from
    DATA + `_SEPARATORS`). Each gap and the token after it are one atomic group: the
    connective class holds the script's letters, so a free gap could swallow whole tokens
    and the match backtrack exponentially on repetitive text (6.9 s on 179 characters before
    this). The gap takes the NEAREST next token and is not reconsidered, which gives up a
    match only where a token repeats inside a gap of its own; matching still restarts at
    every position. Returns a compiled pattern, or None for an empty span. Deterministic and
    local - no model, no language literal in code."""
    nc = _norm_classes()
    diac = nc.get("diacritics_class") or ""
    script = nc.get("script_class") or ""
    articles = [a for a in (nc.get("definite_articles") or []) if a]
    plain = re.sub("[%s]" % diac, "", str(span or "")) if diac else str(span or "")
    toks = [t for t in re.split(r"\s+", plain.strip()) if t]
    if not toks:
        return None
    for article in articles:
        if toks[0].startswith(article) and len(toks[0]) > len(article):
            toks[0] = toks[0][len(article):]
            break
    fill = "[%s%s]*" % (diac, _INVISIBLE)
    tok_pats = [fill.join(re.escape(ch) for ch in tok) for tok in toks]
    # connective gap: whitespace + configured script chars (covers script-native
    # punctuation, e.g. Arabic comma/semicolon, which fall inside the script range)
    # + universal ASCII separators. Bounded so a match can never run away.
    gap = r"[\s%s%s%s]{0,24}?" % (script, _SEPARATORS, _INVISIBLE)
    body = tok_pats[0] + "".join("(?>%s%s)" % (gap, pat) for pat in tok_pats[1:])
    prefix = ("(?:%s)?" % "|".join(re.escape(a) for a in articles)) if articles else ""
    try:
        return re.compile(prefix + body, re.IGNORECASE)
    except re.error:
        return None


def _sub_span(text, span, repl):
    """Replace `span` in `text`, tolerating benign Arabic variation. Returns
    (new_text, n_substitutions). Literal first (fast, exact), then the tolerant
    bounded regex."""
    if not isinstance(text, str) or not span:
        return text, 0
    if span in text:                                 # exact path
        return text.replace(span, repl), text.count(span)
    rx = _redaction_span_regex(span)                 # tolerant path
    if rx is None:
        return text, 0
    return rx.subn(repl, text)


def _count_span(text, span):
    """The largest count of `span` in `text` under any one of the forms used to scrub it
    (`_span_forms`), so the post-apply grep sees what the apply targets - never a vacuous
    zero; above zero is what it needs. Counts without mutating."""
    if not isinstance(text, str) or not span:
        return 0
    return max((len(rx.findall(text)) for rx in _span_forms(span)), default=0)


_QUOTED_LINE = re.compile(r"^ {0,3}>.*(?:\n|$)", re.M)
_MARKDOWN_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")


def _unescaped(text):
    """A Markdown file with every backslash escape undone (the characters it shows)."""
    if not isinstance(text, str):
        return text
    return _MARKDOWN_ESCAPE.sub(r"\1", text)


def _reader_view(text):
    """A Markdown file as its reader reads the running text: every quoted line (a
    block set into the text, such as a finding under a passage) removed, so the text
    on either side of it joins again, and every backslash escape undone. A span split
    by an inserted block, or by an escape, is whole here. Structural only: no
    deliverable's layout is known to this module."""
    if not isinstance(text, str):
        return text
    return _unescaped(_QUOTED_LINE.sub("", text))


def _running_views(text):
    """Every reading of a Markdown file the survivor grep checks besides the file as
    written: the file with its escapes undone and its running text (`_reader_view`)."""
    return [_unescaped(text), _reader_view(text)]


def _exact_form_regex(span):
    """The span's own tokens in order with any amount of whitespace between them,
    ignoring case: linear, whatever the text. None for an empty span."""
    toks = [t for t in re.split(r"\s+", str(span or "").strip()) if t]
    if not toks:
        return None
    return re.compile(r"\s+".join(re.escape(tok) for tok in toks), re.IGNORECASE)


_FIGURE_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _figure_of(span):
    """(index of the token that is a plain number, that number without its grouping) when
    exactly one token of the span is one, else None."""
    toks = str(span or "").split()
    hits = [i for i, tok in enumerate(toks) if _FIGURE_TOKEN.fullmatch(tok)]
    return (hits[0], toks[hits[0]].replace(",", "")) if len(hits) == 1 else None


def _figure_form_regex(span):
    """The form a record writes a figure in: the span with its number grouped or not, and
    a whole number with or without a decimal zero (`1,250,000 USD` and `1250000.0 USD`). A
    figure reaches a deliverable as a number, formatted by the renderer, so the span's own
    writing is not the only one to look for. None for a span with no single plain number."""
    found = _figure_of(span)
    if found is None:
        return None
    index, digits = found
    whole, _, fraction = digits.partition(".")
    number = ",?".join(whole) + (r"\." + fraction + "0*" if fraction else r"(?:\.0+)?")
    parts = [re.escape(tok) for tok in str(span).split()]
    parts[index] = r"(?<![\d.,])" + number + r"(?!\d|\.\d)"
    return re.compile(r"\s*".join(parts), re.IGNORECASE)


def _span_forms(span):
    """Every form the scrub matches a span in: `_exact_form_regex`, the tolerant
    `_redaction_span_regex` and `_figure_form_regex`, each for the span as written and in
    both Unicode normal forms, since the same letter can be stored composed or not."""
    variants = {str(span or "")} | {unicodedata.normalize(form, str(span or "")) for form in ("NFC", "NFD")}
    forms = [build(variant) for variant in sorted(variants)
             for build in (_exact_form_regex, _redaction_span_regex, _figure_form_regex)]
    return [rx for rx in forms if rx is not None]


def _scrub_one_pass(text, reds):
    """ONE matching pass: every match of every span, in every form, is found on the
    text as it stands; overlapping and touching matches merge into one range; each range
    is replaced by the marker of the earliest-listed span it holds. So neither the
    list's order nor a shorter span can leave part of a longer one. A span counts once
    for each merged range one of its matches fell in. Returns (new_text, {span: n})."""
    spans = _span_list(reds)
    counts = {span: 0 for span, _ in spans}
    if not isinstance(text, str) or not spans or not text:
        return text, counts
    hits = []
    for order, (span, _) in enumerate(spans):
        for rx in _span_forms(span):
            hits += [(m.start(), m.end(), order) for m in rx.finditer(text) if m.end() > m.start()]
    if not hits:
        return text, counts
    merged = []
    for start, end, order in sorted(hits):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
            merged[-1][2].add(order)
        else:
            merged.append([start, end, {order}])
    out, cursor = [], 0
    for start, end, orders in merged:
        out += [text[cursor:start], spans[min(orders)][1]]
        cursor = end
        for span in {spans[o][0] for o in orders}:
            counts[span] += 1
    out.append(text[cursor:])
    return "".join(out), counts


def _norm_span_key(span):
    """A normalized de-dupe key for a span (LANGUAGE-NEUTRAL): lowercased, diacritics
    removed (DATA), leading definite article stripped (DATA), whitespace collapsed.
    So a model span and a deterministic span for the same text de-dupe to one. No
    language literal in code - the diacritics/article strings come from the resource."""
    s = " ".join(str(span or "").split()).strip().lower()
    nc = _norm_classes()
    diac = nc.get("diacritics_class") or ""
    if diac:
        s = re.sub("[%s]" % diac, "", s)
    for art in (nc.get("definite_articles") or []):
        a = str(art).lower()
        if a and s.startswith(a):
            s = s[len(a):]
            break
    return s.strip()


def _merge_redaction_proposals(*lists):
    """UNION redaction proposals from multiple sources (deterministic detectors +
    the clerk model), de-duped by NORMALIZED span (reuse the Task 1 normalization).
    Earlier lists win on a key collision, so deterministic items (passed first)
    keep their rule_id/category attribution. Never replaces - it merges, so the
    model still contributes spans the detectors do not cover, and the detectors
    guarantee authorized regular shapes are present regardless of model recall."""
    merged, seen = [], set()
    for lst in lists:
        for it in (lst or []):
            if not isinstance(it, dict):
                continue
            span = str(it.get("span") or it.get("text") or "").strip()
            if not span:
                continue
            key = _norm_span_key(span)
            if key in seen:
                continue
            seen.add(key)
            merged.append(it)
    return merged


def _span_list(reds):
    """Normalize a redaction list into [(span, replacement), ...], dropping items
    with no span. `text` is accepted as a span alias (INFRA-037 tolerance). The
    replacement is always the placeholder: an item's own `replacement` comes from the
    model, which could keep what it was told to remove. Only `neutral_id` differs, set by
    Python alone (redaction_stage) when a unit id carries a span."""
    out = []
    for red in reds or []:
        if not isinstance(red, dict):
            continue
        span = str(red.get("span") or red.get("text") or "").strip()
        if span:
            out.append((span, red.get("neutral_id") or _REDACTION_PLACEHOLDER))
    return out


def _redact_text(text, reds):
    """Scrub every redaction span from a flat text in one matching pass
    (`_scrub_one_pass`). Returns (new_text, {span: n})."""
    return _scrub_one_pass(text, reds)


# Fields a run's own code reads as enumerated values, never free text. A span that happens to
# match one (`Python`, in `written_by`) must not change what the record is. They are left
# as they are; the survivor grep still reads them, so a span truly written there BLOCKS.
_STRUCTURAL_FIELDS = frozenset({"written_by", "explanation_by", "relation", "finding_relation", "derived_from",
                                "kind", "record_verdict", "action", "finding_type", "severity", "status",
                                "outcome", "plan_kind", "provenance"})

def _redact_obj(obj, reds):
    """Recursively scrub every redaction span from every free-text string leaf of a
    JSON-like object (the amendments master, a render's inputs), each leaf in one matching
    pass (`_scrub_one_pass`; the docx and the findings file are rendered from this master,
    so they are scrubbed the same way). `_STRUCTURAL_FIELDS` are left alone. A number is
    left too: what a renderer writes from it is read by `_figure_form_regex`, and BLOCKS in a
    file rendered from the master (open item 86). Returns (new_obj, n_substitutions)."""
    total = 0

    def walk(o, key=None):
        nonlocal total
        if key in _STRUCTURAL_FIELDS:
            return o
        if isinstance(o, str):
            t, counts = _scrub_one_pass(o, reds)
            total += sum(counts.values())
            return t
        if isinstance(o, list):
            return [walk(x, key) for x in o]
        if isinstance(o, dict):
            return {k: walk(v, k) for k, v in o.items()}
        return o

    return walk(obj), total


# --- shape (a) hand-back: produce scrubbed content, pipeline renders, then verify ---

def scrub_master_and_body(master, reds, doc_text, own=None):
    """PRIVACY (shape a, step 1): scrub the canonical amendments master and the body
    canvas. Returns (scrubbed_master, body_red, located, by_artifact). Contains NO
    editorial logic: it does not render or look up convention categories - the
    pipeline renders the scrubbed master AFTER this returns.

    `reds` is every span to scrub (every written form in the run,
    redaction_stage._run_spans); `own` is this document's own spans (default: all of
    `reds`), the ones `located` counts and a span located nowhere BLOCKS for. A span of
    another document need not occur in this one."""
    located = {span: 0 for span, _ in _span_list(reds if own is None else own)}
    scrubbed_master, n_master = _redact_obj(master, reds)
    body_red, body_counts = _redact_text(doc_text or "", reds)
    for span, n in (body_counts or {}).items():
        if span in located:
            located[span] += n
    for span in located:
        before = _count_span(json.dumps(master, ensure_ascii=False), span)
        after = _count_span(json.dumps(scrubbed_master, ensure_ascii=False), span)
        located[span] += max(0, before - after)
    by_artifact = {"amendments_master": n_master}
    return scrubbed_master, body_red, located, by_artifact


def scrub_text_artifacts_and_verify(reds, info, located, by_artifact, also=()):
    """PRIVACY (shape a, step 2): scrub the INDEPENDENT text artifacts on disk, then
    VERIFY by re-grepping EVERY final artifact (incl. the rendered docx) for any
    surviving span. The pipeline has already rendered the master deliverables before
    calling this. Returns the report dict (dropped/survivors/...) the caller turns
    into BLOCKs. Reads/writes files and uses text_extract (neutral infra); makes no
    editorial call. Every span of `reds` (redaction_stage._run_spans) is scrubbed and
    grepped for; `located` holds the document's own spans, the ones proposed, applied
    or dropped. `also` names more keys to scrub on disk: the master's own files, when
    their render failed and they stand as they were."""
    def _bump(counts):
        for span, n in (counts or {}).items():
            if span in located:
                located[span] += n

    # (2) independent text artifacts (NOT master-derived): scrub on disk.
    for key in TEXT_ARTIFACT_KEYS + tuple(also):
        p = info.get(key)
        if not p or not Path(p).exists():
            continue
        try:
            original = Path(p).read_text(encoding="utf-8")
        except Exception:
            continue
        new, counts = _redact_text(original, reds)
        _bump(counts)
        by_artifact[key] = sum(counts.values())
        if new != original:
            Path(p).write_text(new, encoding="utf-8")

    # (3) THE REAL GATE: re-read EVERY final on-disk artifact (incl. rendered docx
    #     text) and grep each span. Verify the OUTCOME, not the process.
    survivors = {}
    for key in VERIFY_KEYS:
        p = info.get(key)
        if not p or not Path(p).exists():
            continue
        try:
            text = (text_extract.extract_text(Path(p))
                    if str(p).lower().endswith(".docx")
                    else Path(p).read_text(encoding="utf-8"))
        except Exception:
            # if we cannot read an artifact to verify it, we cannot confirm it
            # clean -> treat as a survivor of every span (fail safe, LAW-IV).
            for span, _ in _span_list(reds):
                survivors.setdefault(span, []).append(f"{key} (unreadable)")
            continue
        for span, _ in _span_list(reds):
            if _count_span(text, span) > 0:
                survivors.setdefault(span, []).append(key)
            elif not str(p).lower().endswith(".docx") and any(
                    _count_span(view, span) > 0 for view in _running_views(text)):
                # The span is whole only once the file's escapes are undone or its
                # quoted blocks removed. Rendering from scrubbed inputs should leave no
                # such thing, so this is the net: it cannot be scrubbed in place, so it
                # BLOCKS (LAW-IV).
                survivors.setdefault(span, []).append(key + " (split by a quoted block or an escape)")

    dropped = [span for span in located if located[span] == 0]
    return {
        "proposed": len(located),
        "applied": sum(1 for span in located if located[span] > 0),
        "dropped": dropped,
        "survivors": survivors,
        "by_artifact": by_artifact,
        "total_subs": sum(by_artifact.values()),
        "located": located,
    }
