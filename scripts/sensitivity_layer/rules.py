"""LAW-IV PII-rule production (Mechanism 1 input, relocated in Phase 1b).

Compiles the OPERATOR REDACTION RULES the scrubber applies. This is privacy in
PURPOSE: it decides which spans are marked for masking. It RECEIVES the operator's
convention registry as a plain DATA dict (passed by the pipeline) and reads its
fields; it does NOT import convention_parser or any editorial schema/code, so there
is no dependency edge from the privacy home into editorial logic. Editorial-convention
PARSING stays in convention_parser; this module only consumes the compiled registry
data and hands back compiled rules.
"""

from __future__ import annotations

import re

# Redact-verb regex. Self-contained copy: this module owns redaction-phrasing
# detection and deliberately does NOT import the editorial _ACTION_PATTERNS from
# convention_parser (that would be a privacy->editorial edge).
_REDACT_VERB_RE = re.compile(
    r"\b(redact|mask|conceal|withhold|remove\s+from\s+output|do not (?:print|publish|disclose|reveal))\b",
    re.IGNORECASE)

# A convention is an OPERATOR REDACTION RULE: a machine-usable instruction the
# redactors APPLY to document spans (LAW-IV's own phrase, "content marked for
# redaction"). This replaces the phantom of a model JUDGING what is "sensitive";
# the operator declares the rules, the redactors apply them.
#
# A convention is recognized as REDACTION-INTENT if EITHER:
#   - its category OR id CONTAINS a redaction keyword (substring match, deliberately
#     narrow — only these keywords; not every mention of "confidential" elsewhere), or
#   - its rule text has redaction phrasing (an explicit redact verb OR prohibition
#     phrasing that implies redaction), or its action is already 'redact'.
# So `## CONV-CONFIDENTIALITY` (category slug "conv-confidentiality", contains
# "confiden") and a rule worded "must not contain …" both qualify.
_REDACTION_KEYWORDS = ("confiden", "redact", "privacy", "pii")

# Prohibition phrasing that implies redaction without an explicit redact verb.
_PROHIBITION_RE = re.compile(
    r"\b(?:must|shall|may)\s+not\s+(?:contain|include|appear|carry|state|name|be\s+"
    r"(?:published|disclosed|printed|included|shown|present))"
    r"|\bnot\s+be\s+(?:published|disclosed|printed|included|shown)\b",
    re.IGNORECASE)

# Built-in redaction categories. These are NOT an automatic floor (that would be
# the engine asserting sensitivity on its own — forbidden by operator-sovereignty,
# the 3a phantom). They remain ONLY as a named ruleset an operator can CONSCIOUSLY
# opt into (see `redaction_rules(..., opt_in_default_ruleset=True)`); nothing
# applies them automatically. With no operator rule in force, redaction hard-stops
# (the caller refuses the run or the operator declares redact-nothing) — it never
# silently substitutes these.
DEFAULT_REDACTION_RULES = [
    {"id": "RED-DFLT-001", "category": "confidentiality", "action": "redact", "severity": "required",
     "rule": "National identity / passport / tax / similar government ID numbers."},
    {"id": "RED-DFLT-002", "category": "confidentiality", "action": "redact", "severity": "required",
     "rule": "Named natural persons (private individuals) attached to identifying data."},
    {"id": "RED-DFLT-003", "category": "confidentiality", "action": "redact", "severity": "required",
     "rule": "Confidential turnover / revenue / financial figures not in the public record."},
    {"id": "RED-DFLT-004", "category": "confidentiality", "action": "redact", "severity": "required",
     "rule": "Business secrets / proprietary commercial terms marked confidential."},
]


def _is_redaction_category(category, conv_id) -> bool:
    """True if the category OR id contains a redaction keyword (substring match)."""
    blob = f"{str(category)} {str(conv_id)}".lower()
    return any(k in blob for k in _REDACTION_KEYWORDS)


# TWO-I. What a redaction verb acts ON, and why that decides the question.
#
# A redaction rule instructs the redactors to do something TO A SPAN OF THE
# DOCUMENT: redact the client name, withhold the turnover figure, do not publish
# the address. The verb's OBJECT is document content.
#
# A review convention can use the same verbs about something else entirely: what
# a REVIEWER may conclude, record, or assert. "Findings must withhold judgement
# about equipment condition" uses `withhold`, and its object is the reviewer's
# own judgement, not a span. Nothing in that rule asks for anything to be removed
# from the output.
#
# The verb alone cannot tell these apart, and that is the whole of the defect: a
# rule about reviewer restraint compiled into a live redaction rule. So the
# object is read as well. These are the words a review convention uses when it is
# restraining the REVIEWER rather than marking content, taken from the corpus's
# own vocabulary for reviewer-facing rules.
_REVIEWER_OBJECT_RE = re.compile(
    r"\b(?:judgement|judgment|opinion|speculation|conclusion|inference|assessment|"
    r"appraisal|comment|finding|findings|recommendation|diagnosis)\b",
    re.IGNORECASE)

# The subject of a reviewer-restraint rule: the rule is about what the REVIEW
# produces, not about the document under review.
_REVIEWER_SUBJECT_RE = re.compile(
    r"\b(?:finding|findings|reviewer|reviewers|review|comment|comments)\b",
    re.IGNORECASE)


# A redaction rule names CONTENT to remove: a name, a figure, an address, an
# identifier. A reviewer-restraint rule names a CONCLUSION the reviewer may not
# reach. When a rule names content, it is a redaction rule whatever else it
# mentions, because the operator has pointed at something removable.
_REDACTABLE_OBJECT_RE = re.compile(
    r"\b(?:name|names|address|addresses|identifier|identifiers|figure|figures|"
    r"number|numbers|turnover|revenue|salary|date\s+of\s+birth|individual|"
    r"individual's|person|persons|client|client's|supplier|supplier's|account)\b",
    re.IGNORECASE)


def _is_reviewer_restraint(text) -> bool:
    """True when a redaction VERB is being used about what a reviewer may
    CONCLUDE, rather than about content to remove from a document.

    Three conditions, and the third was added after measuring rather than
    reasoning. Requiring only a reviewer-facing subject AND object wrongly
    suppressed genuine redaction rules that merely MENTION the review:
        "Do not disclose the finding's subject name."
        "Redact any comment that names an individual."
    Both name removable CONTENT, and both were being read as restraint.

    So: a rule is reviewer restraint only when it has a reviewer-facing subject
    AND a reviewer-facing object AND names NO redactable content. The moment it
    points at a name, a figure or an address, the operator has pointed at
    something to remove and it is a redaction rule.

    Built to say NO when unsure, deliberately. A false positive here means a
    redaction rule SILENTLY DOES NOT COMPILE, which is the more dangerous
    direction by far: an over-eager redaction is visible in the output, a
    missing one is not."""
    t = text or ""
    if _REDACTABLE_OBJECT_RE.search(t):
        return False
    return bool(_REVIEWER_SUBJECT_RE.search(t)) and bool(_REVIEWER_OBJECT_RE.search(t))


def _has_redaction_phrasing(text) -> bool:
    """True if the rule text expresses redaction INTENT: an explicit redact verb
    (the redact-verb regex) OR prohibition phrasing ('must not contain', 'shall not
    include', 'may not appear', …).

    TWO-I: a redaction verb whose object is the REVIEWER'S OWN OUTPUT is not
    redaction intent. See _is_reviewer_restraint."""
    t = text or ""
    if not (bool(_REDACT_VERB_RE.search(t)) or bool(_PROHIBITION_RE.search(t))):
        return False
    return not _is_reviewer_restraint(t)


def _ensemble_redaction_intent(rule_text):
    """The five-voter verdict on whether this rule is redaction intent.

    Returns (is_intent, record). `record` carries ALL FIVE VOTES with their
    scores and matched reference (WORDS-A constraint 1) so a decision is always
    readable, or the refusal reason when the ensemble could not run.

    A REFUSAL IS NOT A NO. It leaves the regex verdict standing and is recorded,
    because an ensemble that cannot run must not silently narrow what compiles as
    a redaction rule. The import is local so the sensitivity layer keeps its
    no-editorial-imports property: semantic_ensemble reads config and an
    embedding model, and imports nothing editorial."""
    if not str(rule_text or "").strip():
        return False, None
    try:
        import semantic_ensemble as _se
    except Exception as exc:
        return False, {"available": False,
                       "reason": "semantic_ensemble unavailable: %s" % type(exc).__name__}
    try:
        rec = _se.decide(rule_text, "redaction_intent")
    except Exception as exc:
        # EnsembleRefusal included: fewer than five voters, or no references.
        return False, {"available": False, "reason": str(exc)[:400]}
    return bool(rec["result"]), {
        "available": True,
        "result": rec["result"],
        "yes": rec["yes"], "of": rec["of"], "majority": rec["majority"],
        "votes": rec["votes"],
        "safety_veto": rec.get("safety_veto"),
    }


def redaction_rules(registry, *, opt_in_default_ruleset=False) -> dict:
    """Compile OPERATOR REDACTION RULES from the convention registry and REPORT
    whether the operator's rules are in force or only the defaults apply.

    A convention is REDACTION-INTENT when it is in a redaction category (keyword in
    category/id) OR its rule text has redaction phrasing OR its action is 'redact'.
    A redaction-intent convention with non-empty rule text COMPILES to an operator
    rule (action=redact; its text carries the targets, e.g. company turnover, named
    individual + ID number). A redaction-intent convention that does NOT compile
    (no usable rule text) is NEVER silently dropped: it raises a WARNING naming the
    id and reason, surfaced by the caller (console + bus).

    `registry` is a plain DATA dict (the parsed convention registry); this function
    reads its fields and imports nothing from convention_parser.

    Returns a report dict:
      rules:             the rules the redactors APPLY = the compiled OPERATOR rules
                         (NO automatic default floor — operator-sovereignty). Empty
                         when no operator rule is in force; the caller then hard-stops.
      operator_rules:    the compiled operator rules (may be [])
      operator_in_force: bool — True iff at least one operator rule compiled
      source:            "operator" (rules in force) | "none" (caller must hard-stop)
      warnings:          [{id, category, reason}] for redaction-intent that failed
                         to compile (loud, never silent)
    1c (operator-sovereignty): there is NO silent fallback to engine-defined default
    categories. The built-in DEFAULT_REDACTION_RULES are applied ONLY when the
    operator CONSCIOUSLY opts in (opt_in_default_ruleset=True); otherwise they never
    appear in `rules`. When no operator rule is in force, redaction does not quietly
    apply defaults — the caller refuses the run unless the operator declares
    redact-nothing for the run (logged to the governance ledger)."""
    convs = (registry.get("conventions") if isinstance(registry, dict) else None) or []
    operator, warnings = [], []
    # TWO-K / WORDS-A constraint 1: every ensemble decision is recorded with all
    # five votes, so a caller can always read WHY a rule was or was not taken as
    # redaction intent, rather than only the outcome.
    semantic_votes = []
    for c in convs:
        cid = str(c.get("id", ""))
        cat = str(c.get("category", "")).strip().lower()
        act = str(c.get("action", "")).strip().lower()
        rule_text = str(c.get("rule", "")).strip()
        is_cat = _is_redaction_category(cat, cid)
        is_phrase = _has_redaction_phrasing(rule_text)
        # TWO-K. The five-voter ensemble decides redaction intent from what the
        # rule MEANS, against the operator's own reference text, and is UNIONED
        # with the regexes rather than replacing them.
        #
        # Union, not replacement, and that is a deliberate conservative choice.
        # The regexes have a measured hole (the ACTIVE prohibition: "the reviewer
        # must not publish the client's address" never compiled while the passive
        # form did), and under LAW-IV a silent non-compile publishes content the
        # operator marked for removal. Replacing them would close that hole and
        # open the risk of a new one wherever the ensemble is weaker than a
        # regex. A union can only ever ADD redaction, never remove it.
        #
        # A refusal (fewer than five voters, missing references, no model) leaves
        # the regex verdict standing and is LOGGED, never silently treated as a
        # no. The container question this raises is item SIXTEEN's and is
        # answered in the README and the debt list rather than left here.
        is_semantic, semantic_record = _ensemble_redaction_intent(rule_text)
        if is_semantic and not _is_reviewer_restraint(rule_text):
            is_phrase = True
        if semantic_record is not None:
            semantic_votes.append(dict(semantic_record, id=cid))
        # TWO-G. `action` is INFERRED FROM PROSE by convention_parser's keyword
        # table, never declared: a heading bracket reads severity and subjects
        # only. So `act == "redact"` was not the operator saying "redact this",
        # it was a regex finding a word. Established by running it: an ordinary
        # review convention reading "Findings must withhold judgement about
        # equipment condition" classifies as `redact` and compiled here into a
        # LIVE redaction rule, matched_by="action".
        #
        # That is not a cosmetic misclassification. With no operator redaction
        # rule in force a run HARD-STOPS for a conscious operator choice
        # (operator-sovereignty, 1c above). One spurious rule flips
        # operator_in_force to True, so the run proceeds instead of stopping AND
        # hands the redactor a nonsense rule to apply to real spans.
        #
        # An inferred value must not decide a LAW-IV matter. Redaction intent is
        # taken from what the operator DECLARED (the category or id, which they
        # wrote) or from the rule's own explicit phrasing, never from a keyword
        # table's guess about a verb. The shipped corpora are unaffected: none of
        # the 8 device rules triggers on any path, before or after.
        #
        # NOTE the phrasing trigger fires independently, so dropping this one
        # does not close everything: "withhold" is in the redact-verb regex too.
        # What it does close is the path where a REVIEW convention's inferred
        # action field decides a redaction question, which is what was asked.
        declared_redact = act == "redact" and bool(c.get("action_declared"))
        if not (is_cat or is_phrase or declared_redact):
            continue  # not redaction-intent — leave it as an ordinary convention
        if not rule_text:
            warnings.append({"id": cid, "category": cat,
                             "reason": "redaction-intent convention has no rule text to compile"})
            continue
        operator.append({"id": cid, "category": cat or "confidentiality",
                         "rule": rule_text, "severity": c.get("severity", "required"),
                         "action": "redact",
                         "matched_by": ("category" if is_cat
                                        else "declared_action" if declared_redact
                                        else "phrasing")})
    operator_in_force = bool(operator)
    # 1c: NO automatic default floor. Defaults are included ONLY on conscious opt-in.
    rules = list(operator)
    if opt_in_default_ruleset:
        rules += list(DEFAULT_REDACTION_RULES)
    if operator_in_force:
        source = "operator+optin_defaults" if opt_in_default_ruleset else "operator"
    else:
        source = "optin_defaults" if opt_in_default_ruleset else "none"
    return {
        "rules": rules,
        "operator_rules": operator,
        "operator_in_force": operator_in_force,
        "source": source,
        "defaults_available": True,   # named ruleset exists for conscious opt-in (never auto)
        "warnings": warnings,
        # WORDS-A constraint 1: all five votes, per convention, with scores and
        # matched reference. Empty when the ensemble could not run at all; an
        # entry with available=False carries the refusal reason, so "the model
        # was missing" and "the ensemble said no" are never confused.
        "semantic_votes": semantic_votes,
    }
