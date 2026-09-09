# Corpus Ingestion Contract (graph-ready corpus boundary)

This is the boundary contract for an external, source-verified case corpus
landing at Shimmer's CORPUS BOUNDARY. There is no code merge: a collaborator's
retrieval and source-verification agent produces cases, and Project Shimmer, a
constitutional document-review swarm, only validates their intake. A
collaborator's own retrieval schema and emitter are outside this contract's
scope; a collaborator's intellectual property in that schema stays theirs.

This document defines what Shimmer requires so an external source can emit to
it. Item 1 ships this spec, an executable validator, fixtures, and a gate
check. It does NOT ship a collaborator-specific adapter (a collaborator's own
emitter to conforming files): that needs the collaborator's actual output
schema, which is outside this contract's scope.

## WHERE

Conforming files land in `input/context/`, Shimmer's domain learning corpus.
They are read at BOOT as grounding context. They are NEVER hand-placed in
`input/operational/` and NEVER receive amendments. They are retrieved precedent
and reference cases that GROUND the review; they are not the document under
review. Amending a precedent is nonsensical.

## THE PER-CASE FILE

Exactly one Markdown (`.md`) file per case.

- Filename: ASCII-safe stem only (letters, digits, underscore, hyphen),
  matching `^[A-Za-z0-9_-]+$`. No spaces, no non-ASCII characters in the
  filename. Rationale: the framework requires ASCII-only path names with no
  unicode in paths. The Arabic or other non-Latin content lives INSIDE the file,
  never in its name.
- Filename MUST contain a 4-digit year matching the case date, and that year MUST
  be DELIMITED. The repo's date cascade reads the filename year as its
  authoritative, highest-confidence (tier-1) source via the `_FILENAME_PATTERNS`
  in `scripts/document_dating.py`. The bare-year patterns are word-boundary
  anchored (`\b(20\d{2})\b` / `\b(19\d{2})\b`), and the regex underscore is a
  WORD character, so a year glued to letters by an underscore (`case_alpha_2021`)
  is NOT read by the cascade. The year must therefore be set off by a hyphen
  (`case_alpha-2021.md`) or appear in `YYYY-MM-DD` / `YYYY-MM` form
  (`case_alpha-2021-03-14.md`). A space also delimits it, but spaces are barred
  by the ASCII-safe rule above, so use a hyphen. Rationale: only a delimited year
  resolves the case date locally with high confidence and no web lookup, and lets
  the date-cutoff machinery see the case date deterministically. An underscore is
  fine ELSEWHERE in the stem; only the year boundary needs a hyphen.
- Body: UTF-8, original language(s) preserved. Arabic and other right-to-left
  scripts are fully supported. Preserve the case's article, section, and
  paragraph structure with blank-line-separated paragraphs, so the reference
  index can cite individual provisions (REF-* granularity is per paragraph).
- Body must be non-empty.

## THE SIDECAR

One file `input/context/_corpus_ingest.json`, a JSON object. The leading
underscore is the exclusion mechanism: Item 1a added an `is_corpus_file`
predicate (`scripts/text_extract.py`) that skips any file whose name starts with
`_` at every corpus-intake site. So `_corpus_ingest.json` is invisible to every
corpus loader, the date cascade, and the embedding store. It keeps the `.md`
bodies clean and gives the graph engine a structured ingest surface. Front-matter
YAML inside the `.md` was rejected: nothing parses it today, so it would be inert.

Top level:

- `ingest_run_id`: string. The ingestion run that produced this bundle.
- `generated_at`: ISO-8601 string. When the bundle was generated.
- `cases`: list. One entry per `.md` case file.

Each entry in `cases`:

- `file`: the exact `.md` filename, which must exist in `input/context/`.
- `case_id`: stable unique id from the source system.
- `title`: human-readable case title.
- `citation`: formal citation string.
- `jurisdiction`: jurisdiction string.
- `date`: ISO-8601 date `YYYY-MM-DD`. Its year MUST equal the 4-digit year in
  the `file` name. Rationale: prevents a date/slug mismatch from confusing the
  cutoff.
- `language`: BCP-47 primary language tag of the body (for example `ar`, `en`).
- `source_verification`: object `{ "status": one of "verified", "unverified",
  "failed", "url": source URL string }`. The `url` may be empty only when
  `status` is not `verified`. Rationale: the source's verification result is the
  grounding provenance, and it travels with the case so the graph engine and the
  audit trail can record where each grounded fact came from.
- `role`: MUST be the exact string `context_grounding`. Rationale: marks the file
  as grounding-only so later mode and cutoff logic keeps it out of operational.
  The contract carries the signal; enforcement is M1/M2 (see deferred
  enforcements below).

## BIJECTION

Every case `.md` in `input/context/` has exactly one sidecar entry, and every
sidecar entry names an existing `.md`. The sidecar file itself and `.gitkeep` are
not cases.

- HARD FAIL (one direction only): a sidecar entry whose named `.md` is missing.
- SOFT WARNING: a `.md` in the directory with no sidecar entry. The operator may
  legitimately keep non-ingested corpus files in the same directory, so this is a
  warning, not a failure.

## GRAPH-READINESS

The sidecar is the graph-ingest surface. The graph engine, once wired in a later
step, reads `_corpus_ingest.json` to populate Document/Case nodes with `case_id`,
`citation`, `jurisdiction`, `date`, and `source_verification` provenance. Item 1
does not wire the graph engine. It defines the surface. The graph engine's
`build_graph` already accepts a `sources` override
(`scripts/ontology_graph.py`), so the later step can register the sidecar as an
additional source without rewriting the loader.

## SENSITIVITY SCOPING

An external grounding corpus of this shape is expected to be PUBLIC,
source-verified case law and NON-sensitive by nature, stored at full fidelity.
LAW-IV masking applies to the operator's documents under review, not to this
public grounding corpus. There is no masking of public case law.

## TWO DEFERRED ENFORCEMENTS (stated so the boundary is honest)

1. Promotion exclusion. The date cutoff would otherwise promote a recent
   ingested case into operational and attempt to amend it. The
   `role=context_grounding` marker is the signal; the cutoff hook that honors it
   is M1/M2 work, not Item 1. Today the marker is carried and validated but not
   yet enforced by the cutoff.
2. Graph-engine sidecar read. Nothing reads `_corpus_ingest.json` yet.
   Graph-readiness is realized when the graph engine ingests it (later step).
