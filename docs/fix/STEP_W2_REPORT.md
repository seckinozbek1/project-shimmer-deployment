# STEP W2 REPORT: distribute conventions to agents

## Premise check, per this step's own instruction: "verify the premise and report it... if either does not, stop"

**Does each agent's contract declare what it does in a form an assignment can be derived
from?** Checked `config/agent_contracts.json` directly: every one of the 18 agent contracts
carries only `item_kind`, `fields`, `required`, and (for a few) `directives`/`field_forms`/
`max_output_tokens`/`note`. None declares a subject, scope, or domain field. The closest
thing that exists is in a DIFFERENT file, `config/agent_registry.json`: each agent has `does`
(free-text English sentences, e.g. PRACTICE_AUDITOR's "Check procedures against current best
practice," "Flag anti-patterns"), `does_not` (the same, negated), and `category` (one of
`verification`, `privacy`, `content_production`, `editorial`, `organization`, `style`,
`amendment`, `analysis`; confirmed by reading every agent's own `category` value directly).
`does`/`does_not` is prose, not a matching key. `category` is structured, but coarse (8
values across 18 agents) and, critically, unrelated to rule content, see below.

**Does each convention declare what it governs, in a form that could match an agent?**
Checked `config/convention_registry.json` and `scripts/convention_parser.py` directly. A
convention carries `id`, `category`, `rule` (prose), `source_file`, `source_location`,
`severity`, `action`. Its `category` comes from `_normalize_category` (`convention_parser.py`):
either the operator's own rule id (when the heading carries one, kept verbatim, never
reclassified, per the R6 fresh-eyes fix this codebase already carries), or, absent an id, one
of a fixed keyword-matched vocabulary: `terminology`, `red_flags`, `rephrasing`,
`citation_style`, `structural`, `value_alignment`, `borrowing` (`_CATEGORY_KEYWORDS`, read
directly from the source, confirmed complete).

**The two `category` vocabularies share zero terms.** A convention's `category` describes
what KIND OF RULE the text is (terminology, structural, citation style). An agent's
`category` describes what KIND OF WORK the agent does (verification, editorial, amendment).
Neither was built to match the other, and nothing in either file establishes a correspondence
between them today.

## Stop, per this step's own instruction

Both halves of the premise fail: neither side declares what it concerns in a form an
assignment could be mechanically derived from, and the one structured field that does exist
on each side (agent `category`, convention `category`) is two unrelated vocabularies, not
one shared one.

Building the distribution mechanism from here would require one of two things, neither
decided by anything written in this chain's own instructions:

1. A hardcoded mapping from convention subject matter to agent identity (e.g. "a rule
   mentioning citations goes to CITATION_RESOLVER"). Explicitly forbidden: "Do not invent a
   hardcoded subject mapping, which would breach S5" (nothing domain-specific in code,
   config or prompts; a mapping keyed on rule CONTENT would be exactly that, baked in for
   whatever domain today's operator happens to be reviewing).
2. A new, third vocabulary both agent contracts and convention entries would need to declare
   themselves in, built and adopted on both sides before any assignment logic could run at
   all. This is a real, additional design decision (what the vocabulary's terms are, who
   assigns an agent's terms, who assigns a convention's terms, whether an operator writes
   them or they are inferred) that this step's own text does not settle, and per this chain's
   own C5 rule, "where a choice needs the operator's authority, stop the step" rather than
   invent it unattended.

Nothing was built. No file outside this report and `docs/fix/STEP_W2_REPORT.md` itself was
touched in this step. The gate was not re-run since nothing changed; the W1 baseline still
holds (`PASS=193`, same two pre-existing failures).

## What this means for the rest of the chain, stated plainly

W3 ("firing, and the fourth visible state") is explicitly written to follow FROM W2's own
assignment mechanism ("Follows from W2, not a separate mechanism. An agent with no
conventions assigned does not run"). With no assignment built, W3 has nothing to attach to:
building a fourth visible state for "an agent with nothing assigned" when nothing can ever
BE assigned would be dead scaffolding, the exact thing this project's own standing discipline
rules out ("No dormant-but-claimed-built scaffold is acceptable"). W3 is skipped for the same
reason, not attempted separately.

W4 (the harness) references "the rule cluster assigned to it," part three of the nine-part
specification, which also depends on W2. The harness can still be built with this one part
declared unresolved (per W4's own instruction: "Where a part is not decided, write it as
unresolved and name it"), which is a real, honest thing to build; W4 is not skipped for this
reason, only its rule-cluster part is marked unresolved, and W2's own unresolved decision
(which vocabulary, whose authority) is named as the reason.

---

STEP W2 COMPLETE (stopped, per premise check; nothing built beyond this report)
