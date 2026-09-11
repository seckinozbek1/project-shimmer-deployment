# STEP README REPORT: the README audited start to finish against HEAD

**Built without measurement, like everything from 10 and 11 September. This step changes
documentation and one Dockerfile ordering; it changes no review behaviour. The README now
says, where a reader will see it, that every measured number predates the work of 10 and 11
September, that the last scored run predates all of it, and that the measurement is owed.**

## Method

Three read-only audit agents each took one range of the README (lines 1 to 560, 560 to 1000,
1000 to the end) and compared every claim in it with the code at `a3c666f`: the phase list
against `main()`, the route table against every registered route, the env table against
every `SHIMMER_*` read, the check count against `len(CHECKS)`, the console claims against
`scripts/ui/console.html`, the bracket syntax against `convention_parser`, the pairing
rules against `pairing_map`, the evidence record against `call_evidence.RECORD_FIELDS`,
and every measured number against `git log -S` for when it entered the file and which later
commits touched the code that produced it. They returned 65 findings with path:line
evidence. I re-verified the ones I state as facts (the tracked-file count from
`git ls-files`, the six corpus directories, the twelve tracked config files, the thirty-eight
tracked docs, the agents' declared subjects from the registry, the wide-mode clip sizes, the
absence of any `mkdir` in the launchers, the `families` keys of the vocabulary file, what
`_pairs_view` and `_project_finding` pass through, check 193's failure text) before writing
them in. Findings that only restated a claim already correct elsewhere in the README were
folded into the nearest correction rather than duplicated.

The set-level facts held: the env table has 21 rows and the server reads exactly those 21
names; the route table has 19 rows and the app registers exactly 19 routes (checks 116 and
167 pass at HEAD); `len(CHECKS)` is 210 as stated; the status and exit table matches the
code; the console section matches the page.

## What was wrong, and what it says now

Grouped by section. Every correction is in the working copy of `README.md`.

**Opening and inventory.** The opening claimed the corpora "prove the mechanism works"; it
now says they are what the gate exercises, and a new paragraph, second on the page, states
plainly that every measured number predates 10 September, that every mechanism from 10 and
11 September is proved on gate fixtures only, that the two device-corpus runs were stopped
before any deliverable, and that the measurement is owed. The tracked-file count was 127; it
is 178 at HEAD, said with the caveat that the exact figure has gone stale within a day
twice. The tree omitted the Dockerfile, compose.yaml, .dockerignore, .gitattributes,
tools/entrypoint.sh, tools/archive_ontology_stores.py, five docs/api files, docs/fix, the
state document, and five config files; it named "the 18 agent modules", which do not exist
(one wrapper runs all 18 registry agents); it said four corpora where six directories ship.
All corrected.

**Section B.** The agent table gained a Subjects column and a paragraph on what subjects
decide, including the six agents that declare none and why. The 47-minute run, the draft-mode
call chain, the "$0.00 and no network" claim (no network holds only since the local loader
fix of 10 September), the 1-of-37 figure (predates the rule-id resolver and the required
Finding fields), and the LAW-III sentence (the family split holds locally; what is weaker is
the auditor) were each corrected. The BOOT bullet now includes the convention assignment;
phase 5.5 names the firing gate and the per-plan judging agent; run end names the storage
scope. The wide bullet said every agent sees the whole document and the whole registry; it
now says each firing agent sees the document clipped (6500 or 12000 characters) and its
assigned rules plus the untagged ones. The paired bullet's "three outcomes" became the six
plan kinds the map actually records, plus one sentence on the per-call evidence record. The
Finding record paragraph gained the rule-id resolver and the required fields on
PRACTICE_AUDITOR. The phase label "4" became "3-4" in two places. A paragraph was added on
`AMENDMENT_REFUSED` and `CONTRACT_VIOLATION`: every convention-review call ends as exactly one
of an amendment, a refused finding or a failed contract.

**Section E.** The convention-assignment comparison was referred to as "(below)" and
described nowhere in E; it is described now. The parser's preamble rule was misdescribed
("the first heading in a file"); it is keyed on the operator rule id, and the correct rule
is stated with the list-item exception. "Four corpora" became five scenarios in six
directories, with the synthetic one named. The section now records that no shipped corpus
declares a scope yet and points at `STEP_DECL_REPORT.md` for why the first four declarations
are waiting.

**Section G.** The keyless path was claimed through the launcher; the launcher's preflight
stops without keys, so the keyless path is `tools/run_local_demo.py` with the two override
flags. Step 5 and the dependency list omitted bitsandbytes and accelerate. The ontology-stores
list omitted `delta_proposals.jsonl` and the per-scope keeping. "The earlier ontology checks
now write their fixtures through the store" was true of two checks (59 and 60), not all. A
new subsection, "Running in a container", covers the image's contents and exclusions, the
two build modes, the weight-layer ordering, the entry point's three commands, the offline
`docker run` line, the two compose profiles, the three defects the first container start
found, the measured offline gate inside the unbaked image, and what is not proven (no review
has run in a container).

**Section H.** The bare pipeline command exited 6 as written; both override flags are on it
now, with the reason, and on the local wrapper's line. The run-folder layout gained
`audit/convention_assignment.json` and the pairing map's `not_judged`, `reattributed` and
`absence` records. The call-evidence field list claimed "nothing else" while omitting seven
of the 27 fields; the list is complete now. The probe sentence read as if the arithmetic
probe wrote to the run's evidence file; it writes its own `--out` records. The harness
section now says a harness call leaves an evidence record and a cost row. Check 145's failure
text was misquoted. The corpora lead said all corpora are real public data. The staged-corpus
paragraph named one override where two are needed. The device corpus's missing manifest and
the date-lookup dependence are recorded. A paragraph on what the fifth corpus found (five
defects fixed on fixtures, two recorded open, and the classifier's all-UNKNOWN verdict on the
stopped run) was added, and the "eleven defects" count is scoped to the first four corpora.

**Section I.** The `/pairs` row and step-4 prose now say the declared-absence record and
`band_conditions` are on disk and not served by the route; the `/findings` row says
`absence_path`, `stamped_by` and `conditional_on` are on the bus and not in the projection;
the `/convention-assignment` row gained `rule_count` and `idle_agents`; the `/harness` row
gained `agent_count`, `unresolved_part_count` and the 500 case; the `/contract-violations` row
gained the entry shape. These two projection gaps are documented, not built: the operator's
plan named what to fix, and a route change on top of an unmeasured record is not in it.

**Sections J and K.** Section J opens with the dating statement (every number before 10
September; the paired path changed in more than a dozen commits since; the two stopped runs
with their numbers; the measurement owed) and no longer says the local figures "can be
reproduced here" (the standing rule forbids a run on the laptop; they can be reproduced on a
machine with the models cached and a free GPU). Each of the three tables gained a line saying
what the figures rest on and what has changed under them. The probe paragraph disagreed with
section K about the rename tolerance; reconciled. The catalogue paragraph called the
completeness gap an open decision; it names the declared-scope mechanism and says the 0 of 5
stands as the last measured figure. Section K opens with a bullet saying everything from 10
and 11 September is unmeasured; the laptop bullet carries the standing rule; the
completeness bullet describes the declared-scope path, that it is unmeasured, and the two
limits of the form the declarations probe found; the rename bullet says check 185 proves the
refusal, not the 5-of-13 count.

**Section L.** The `--offline` flag and the container's gate result were absent. The
fresh-clone paragraph claimed every other check passes after `pip install` (check 193 fails
without cached weights; 15 and 38 need network unless skipped) and that check 01 passes once
the launcher has run (nothing creates `prompts/` or `snapshots/`; the operator's own machine
fails 01 on exactly those two after every run). The `previous_domain` paragraph said the
family is "currently empty"; it is absent, and check 22 treats absent and empty alike. The
coverage paragraph stopped at check 184; checks 185 to 209 are now listed, with the note that
everything from 197 on was built on 10 and 11 September.

## The adversarial review, and the ten defects it found in this step's own work

Before committing, three read-only lenses reviewed the change set itself (the README diff
against the code, the README against itself, and the three reports plus the Dockerfile,
CLAUDE.md and the state document against their artifacts), with refuters set on each
finding. Twenty-two findings came back; ten survived and are fixed here. The refuter layer
partly failed, several of its agents hitting a model limit and its verdicts arriving
misaligned to their findings, so every one of the twenty-two was re-verified by hand against
the files before being accepted or dropped. That is worth recording: the verification
machinery failed quietly in a way that would have accepted or rejected findings at random
had its output been trusted as it arrived.

The ten, each a real defect in what this step wrote:

1. The container subsection said `.dockerignore` excludes `benchmark/`. It excludes
   `benchmark/keys/` only; the corpora stay out of the image because the `COPY` list never
   names them.
2. The build block offered `docker compose build`, which builds nothing: `compose.yaml`
   names an image and declares no `build:` key.
3. Section B said the pairs route carries "only their counts" for three records. It carries
   the `prior_*` counts only, and nothing at all of `absence` or `band_conditions`, which is
   what section I already said.
4. The paired bullet listed `not_judged` as a sixth plan kind. The planner records five; a
   plan of any kind whose rule has no judging agent is set aside under the map's
   `not_judged` list, keeping its own kind.
5. Section L dated the fixture-only checks from 197. Checks 186 to 196 were also added on 10
   and 11 September, and the README's own opening counts two of them.
6. Section L said nothing creates `snapshots/`. `--save-snapshot NAME` creates it; only
   `prompts/` is created by nothing.
7. Section J's dating sentence said every number in it predates 10 September, while the same
   paragraph carries the two stopped runs' counts from 11 September. Scoped to the benchmark
   figures, with the stopped-run counts named as the exception.
8. Section H called the two device runs "stopped before any score". Both were put through the
   scorer; what they lacked was a deliverable.
9. The local-profile paragraph said the unit-id mismatch is closed. The wide-mode one is; the
   paired-mode gap is open and section H says so.
10. The new amendment paragraph claimed every convention-review call ends as one of three
    outcomes. A valid reply with nothing irregular is a fourth.

Three more went to files beside the README: `compose.yaml` still pointed at Dockerfile stage
4 for `HF_HOME` (the reorder moved it to stage 2), `CLAUDE.md`'s command block still carried
the bare pipeline commands the README now says exit 6, and the state document still expected
two source-only failures on a clean clone where four is right. The baked report's size
paragraph mixed Docker's two size columns and invented an unexplained gap between the old
and new images; the declarations report claimed the judged call's reference excerpt comes
from the other context documents only, when the embedding selection spans every file in
`input/context/` including the log itself. Both corrected.

## Not changed, recorded

- The two route projection gaps above (`/pairs` without `absence`, `/findings` without
  `absence_path`, `stamped_by`, `conditional_on`) are documented as gaps, not closed.
- `docs/RUNBOOK.md` and `docs/THREAT_MODEL.md` were not audited in this step; the operator
  asked for the README.
- The em-dash scan on the README reads 0; no em dash anywhere in it.

## Gate

```
PASS=208  WARN=0  SKIP=0  FAIL/ERROR=2  TOTAL=210
```

`output/gate_readme.log`, run once on the host after the baked image's own gate finished (the
two must never share the card), on the tree carrying this README, the Dockerfile reorder and
the four applied declarations. The two failures are the documented pre-existing ones: check
01 (missing `prompts/` and `snapshots/`) and check 145 (no `tests/fixtures/` on this
machine). Checks 197, 208 and 209, the three that read what changed, all pass. No check was
added by this step.

Two things this gate does not cover, said plainly rather than left to be assumed: the
corrections made after it ran (the ten defects the adversarial review confirmed, all of them
in prose or comments, none in code or in a gate fixture), and the container's own gate, which
ran on the source copied into the image at build time and therefore predates every README
edit.

---

STEP README COMPLETE (65 audit findings resolved into the working copy; the unmeasured state of
10 and 11 September stated in the opening, in J, in K and in L; two projection gaps recorded
open)
