# Request to role B: four real multi-round negotiation cases, held out (D-S102 item 8)

Written by the `cases` lane on 9 November 2026 for the lead to hand to role B, under
`docs/loop/stages/NEGOTIATION_MEASUREMENT_PLAN.md` section 2. It was revised after the plan's vekil
checks and the lead's rulings (D-389, D-395). The lead starts role B; the lane does not.

The cases are development material, exposed after the freeze. Under H17 nothing in the loop (the lead
or any agent it starts) opens these cases before then.

## Why role B

The cases must be material no development work has seen (D-S100 item 1). Role B already works apart
from the loop's lanes. It finds the records, builds the cases and hands over only digests and counts.
The loop reads a case for the first time at the recorded opening (`docs/loop/HELDOUT_OPENINGS.md`).

## What a usable record is

A public record of one negotiation:

- **two parties.** A record with more parties is reduced to the two it names first, in its own order
  (the order of its first document's list of participants, or else of first mention). That order is
  written in `SOURCE.md` before the record is read past its first page. The case then holds those two
  parties' statements only.
- **at least three rounds,** each a dated document, or a part of one, that states where each party
  stands;
- **at least six issues** on which the two parties state where they stand;
- **at least two issues** on which both parties state a figure in at least two consecutive rounds;
- **texts that may be redistributed for research** (an official public document, or a licence that
  allows it). The source and the licence are recorded.

A record that does not meet all five is rejected, with a one-line reason and no quote from it.

Examples of where such records are published (role B chooses; none is required):

- a public body's collective bargaining updates, where the employer and the union each publish
  their proposal and counter-proposal per session, with pay or leave in figures;
- an intergovernmental negotiating text and its revisions, where named delegations' bracketed
  proposals carry figures (a quota, a date, a rate, an amount);
- a public procurement or concession dialogue whose rounds are published with each side's figures.

**Not usable:** anything in the loop's development material (listed in the plan's section 1); the
two documents behind `benchmark/dev_cases/draft_resolution_revision/` (A/C.2/74/L.34 and its Rev.1),
or any other version of that resolution; anything written for this project.

## How the four are chosen, by a rule fixed before any record is read in full

1. List every candidate found that appears to meet the five conditions above from its title, date
   and description alone. Give each its canonical source URL.
2. Sort the candidates by the SHA-256 of `20261109-negotiation-heldout:` followed by the URL.
3. Take candidates in that order. Read each and keep it when it meets all five conditions. Otherwise
   record why it was passed over, in one line, with no quote from it. Stop at four kept.
4. If fewer than four can be kept, stop, and report how many and why. The author agent's synthetic
   cases make up the rest; the plan records the shortfall.

## What to build for each kept record

In role B's own folder, outside the repository and never under `external/`, as
`real/<case_id>/` in the layout the sealer's workload folder takes (STAGE-A). Role B moves the frozen
set into place only after the leakage pass and the freeze:

- `context/`: one plain-text Markdown file per round document, UTF-8 with LF line ends, the
  record's own words. Keep to the parts that state the parties' positions, and keep each part's own
  headings. Name each file `<case_id>_round_<n>_<party>.md`, or `<case_id>_round_<n>.md` when one
  document holds both parties.
- `case_manifest.json`, schema 1, `fixture` false, with:
  - `rounds` (each `round_id`, `sequence`, `document_ids` being the file stems), `actors` (the two
    parties, one of them `supported: true`) and `issues`;
  - for each issue, a `unit` only when both parties write every figure on it in one measure, in the
    record's own words as they stand after the figure;
  - `open: true` on at least two issues still open after the last round, with `position` and
    `fallback` left out (the declarer writes them, below);
  - `sources`: one per round, party and issue where a party states the issue, each an exact span:
    `quote` equal to the file's text between `char_start` and `char_end`, `state` `accepted`, and
    `unit_id` the identifier of the part holding it (`u01`, `u02`, ... in heading order).
- `declarations.json`: for each open issue, `text_headings` (the exact last-round headings that hold
  the issue) and `closed_headings` (the exact last-round headings of text both sides recorded as
  agreed). The lead's freeze tool turns these into the manifest's `text_units` and `closed_units`,
  mechanically, with the pipeline's own slug rule.
- `SOURCE.md`: the URL, title, date, publisher and licence of each document, and what was left out
  and why.

Take each record as it is. Never edit a record to add a shape the shaped synthetic cases carry.
Write no movement label and no judgement of any position yourself.

## The agents role B starts (plan, sections 2.1 and 2.5)

All are fresh and none is the lead's. Each is given only what is named here:

1. **The author agent**, with `NEGOTIATION_AUTHOR_BRIEF.md` as written. Role B sets its four inputs
   as the brief says: the synthetic count (12 less the real cases kept), F and S in equal shares with
   an odd one to F, the fields by the seeded draw, and the output folder in role B's own folder.
2. **The declarer**, one per real case, given the record's files and the manifest. It writes the
   supported party's `position` and `fallback` for each open issue, from the record only, each
   labelled in `declarations.json` as "declared for the test, not the party's own".
3. **Labeller 1 for the real cases**, given the files, the manifest and the key definitions of the
   plan's section 2.5. It writes `KEY_MOVEMENT.json` and `KEY_ROUND3.json` as the author brief
   describes.
4. **Labeller 2, for every case**, given the same, never labeller 1's labels or notes. Then come the
   agreement check, its floor and labeller 3 if needed, as the plan's section 2.5 says.

Role B then runs **the leakage pass and the freeze** of the plan's section 2.6 itself, with
`tools/freeze_negotiation_set.py` on the laptop's CPU with the network off. It commits the corpus
list with the freeze, and the tool records bge-m3's path and digest. A case over a threshold is
replaced and checked again.

The real cases' licence lines are in each `SOURCE.md`.

## What to hand back

A file `docs/loop/private/ROLE_B_NEGOTIATION_DONE.md` with:

- for each case, real and synthetic: its `case_id`; its subset (R, F or S); its numbers of rounds,
  issues, open issues, sources and key rows; and the SHA-256 of its `case_manifest.json`, of its keys
  and of a tar of its folder;
- the agreement (kappa) and whether labeller 3 was needed, each class's share of the key, and the
  leakage counts per corpus and threshold;
- the candidates passed over, with their one-line reasons;
- the shortfall, if any.

Print no quote and no position anywhere else.
