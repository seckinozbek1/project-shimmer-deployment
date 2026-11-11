# Brief for the author agent: synthetic held-out negotiation cases (D-S102 item 8)

Written by the `cases` lane on 9 November 2026 under `docs/loop/stages/NEGOTIATION_MEASUREMENT_PLAN.md`
section 2. It was revised after the plan's vekil checks and the lead's rulings (D-389, D-395).

Role B starts the agent and gives it this brief as written, from the published input format only
(H17, Part III). Neither the lead nor the lane starts it. This file is committed before the agent
drafts anything, and any change to it is a new commit first. Everything below the line is the brief.

**Role B sets four things before starting the agent** (plan section 2.2, one rule in both files):

- **The number of synthetic cases:** 12 less the number of real cases role B kept.
- **F and S, equal shares:** F, the free cases, is that number halved and rounded up; S, the shaped
  cases, is the rest. For example, 8 synthetic cases give F 4 and S 4, and 9 give F 5 and S 4.
- **The fields, by a seeded draw.** Sort the twelve fields below by the SHA-256 of
  `20261109-fields:` followed by the field's name as written. The first F go to the free cases and
  the next S to the shaped cases. Role B gives the agent the two lists, in that order. The fields:
  procurement, wages, a fishing quota, a lease, a service-level agreement, a research grant, a
  schedule of tariffs, a boundary commission, a water-sharing agreement, a pension scheme, an airport
  slot allocation, broadcasting rights.
- **The output folder:** role B's own folder, outside the repository and never under `external/`.
  Role B moves the frozen set into place only after the leakage pass.

The agent is given no access to the repository. It may write only in its output folder and run
Python there.

---

## Your task

Write F free cases and then S shaped cases. You are given both numbers and both lists of fields, one
case per field, in the order given. Each case is a synthetic negotiation, for testing a system that
follows two parties' positions across rounds. You have not seen the system and must not try to.

Write as a person who has drafted negotiation records would: varied, natural, unpredictable
wording, with no pattern a program could learn from the cases themselves.

Everything is fictional: parties, organisations, people and places. No real organisation, person or
company is named. Each case's first context file says at its top, in one line: "Synthetic case
written for testing; every party and figure is fictional."

## Every case: the files

In `<output folder>/<case_id>/`, where `case_id` is lower case with hyphens. A free case's `case_id`
ends in `-free`, for example `grant-three-rounds-free`.

- **`context/<case_id>_round_<n>_<party_id>.md`:** one note per party per round, UTF-8, LF line
  ends.
- **`case_manifest.json`,** in exactly this form (JSON, no comments):

```json
{
  "schema_version": 1,
  "case_id": "<case_id>",
  "fixture": false,
  "rounds": [{"round_id": "r1", "sequence": 1, "document_ids": ["<file stem>", "<file stem>"]},
             {"round_id": "r2", "sequence": 2, "document_ids": ["..."]},
             {"round_id": "r3", "sequence": 3, "document_ids": ["..."]}],
  "actors": [{"actor_id": "<party_id>"}, {"actor_id": "<party_id>", "supported": true}],
  "issues": [{"issue_id": "<issue id>", "unit": "<only when both parties write its figures in one measure>"},
             {"issue_id": "<open issue>", "open": true, "position": "...", "fallback": "..."}],
  "sources": [{"source_id": "<unique>", "round_id": "r1", "actor_id": "<party_id>", "issue_id": "<issue id>",
               "document_id": "<file stem>", "unit_id": "u01", "char_start": 0, "char_end": 0,
               "quote": "<the exact words>", "state": "accepted"}]
}
```

  **The rules for the manifest:**
  - Ids use only ASCII letters, digits, `_`, `-` and `.`.
  - `unit` is the measure in the words the notes write right after the figure. It has no digit,
    single spaces, and no leading or trailing space. Give an issue a `unit` only when every figure on
    it, by both parties, is written with exactly those words right after it. An issue whose parties
    use different measures has no `unit`.
  - One source per round, party and issue where that party states the issue, and none where it says
    nothing. The `quote` is the sentence or clause stating the position, copied exactly.
  - `char_start` and `char_end` are the quote's offsets in the file's text, so that
    `text[char_start:char_end] == quote`. `unit_id` is `u01`, `u02`, ... for the first, second, ...
    heading of that file under which the quote stands.
  - Compute every offset with Python, never by hand:

```python
from pathlib import Path
def span(path, quote):
    text = Path(path).read_text(encoding="utf-8")
    start = text.index(quote)
    assert text.count(quote) == 1, "quote appears more than once"
    return start, start + len(quote)
```

- **`declarations.json`:** for each open issue, `text_headings` (the exact round-3 headings, in the
  supported party's note, that hold the issue) and `closed_headings` (the exact round-3 headings of
  the parts both sides recorded as agreed).
- **`KEY_MOVEMENT.json`:** `{"rows": [...]}`, one row `{"issue_id", "rounds", "label", "why"}` for
  each issue and each pair of consecutive rounds (`["r1", "r2"]` and `["r2", "r3"]`). Each label is
  decided as a careful reader would:
  - **The gap** is the absolute difference between the two parties' figures on the issue in one
    round. A party's own movement does not decide the row; the gap does.
  - **Where the notes give enough to put both figures in one measure,** do so before comparing.
  - `moved_toward`: the gap is smaller in the later round.
  - `moved_away`: the gap is larger.
  - `unchanged_from_prior`: the two gaps are equal within 0.5 percent of the larger, or exactly equal.
  - `not_computable`: only where a careful reader cannot tell. That is, a party says nothing on the
    issue in either round; a position has no figure and no quantity in words; a note states more than
    one figure on the issue and does not say which is its position; or the figures cannot be put in
    one measure from what the notes say.

  Decide each row by what the notes mean, never by how a sentence is worded, and give each row one
  line of `why`.
- **`KEY_ROUND3.json`:** for each open issue, the round-3 passages (quoted exactly) a good suggestion
  for the supported party could rest on, and the agreed text it must leave alone.

## The free cases: write these first, and read no further until they are finished

Write the F free cases as such records are written in their field. Each has:

- two parties, three rounds, and one note per party per round;
- at least six issues, at least two of them still open after round 3, with the supported party's
  position and fallback for those, one sentence each;
- some text both sides agreed in round 3.

Follow no other list. Write every file above for each free case, keys included, before you read the
next section.

## The shaped cases: what each must contain

1. Two parties and three rounds. In each round each party writes one short note (Markdown, 150 to 500
   words, with headings) setting out where it stands.
2. **At least six issues.** Across them, all of the following:
   - at least two issues where both parties state a figure in a shared measure, in every round;
   - at least one issue stated in words only (no figure) by at least one party;
   - at least one issue on which one party says nothing at all in one round;
   - at least one note that states two figures on one issue in one sentence, for example a figure it
     rejects and the figure it offers;
   - at least one issue where the two parties write their figures in different measures (a monthly
     against a yearly figure, a percentage against an amount, days against weeks). The difference is
     said in varied ways: inside the subject ("The monthly fee is..."), before the figure, in
     brackets, after a comma or a dash, or in the next sentence;
   - at least one issue where converting is what tells the movement (3 months against 90 days);
   - movement of every kind across the case: the gap between the parties narrowing, widening and
     staying the same, and a party moving away from the other.
3. **At least two issues still open after round 3,** for the party you choose as the one being
   advised. For each, write that party's position (what it wants) and fallback (the least it will
   accept), in one sentence each.
4. **Text both sides agreed.** Round 3 records at least two parts as agreed by both sides, under their
   own headings.

## Checks before you finish

For every case, with Python:

- every `quote` equals its span;
- every `document_ids` entry is a file stem in `context/`;
- every issue in `KEY_MOVEMENT.json` is in the manifest, with both pairs of rounds;
- for each shaped case, the quotas above are met. List them, each with the issue that meets it. The
  free cases have no quotas.

Then write `<output folder>/AUTHOR_DONE.md`. It holds one line per case with:

- its `case_id`, whether it is free or shaped, and its field;
- its numbers of issues, open issues, sources and key rows;
- the SHA-256 of its `case_manifest.json`, `KEY_MOVEMENT.json` and `KEY_ROUND3.json`.

After those lines, add the quota list.

Show no case text in your final message: only the path of `AUTHOR_DONE.md` and the counts.
