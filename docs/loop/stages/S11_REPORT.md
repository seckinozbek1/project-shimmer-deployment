# S11 report: release readiness (README and documents)

Stage S11 of the autonomous loop of 27 October 2026, on branch `loop/s11`, created from `loop/s10` at `cf19d5d` before S10's merge so that S10's outside-audit wait was not idle (D-171, a recorded departure from IV.1); the loop branch is merged into it once S10 is tagged. Plan: `docs/loop/stages/S11_PLAN.md`, checked (D-163). Opus, medium effort from 28 October 2026 (Annex D, D-S11).

## At the start

Open items read at the branch point: item 19 part 2 (a readable reviewed document, PATCH_2 after v1), items 56 to 69 (S6), item 71 (new, below). The S11 rows of the request ledger (C-R16, D-S18.4) are SCHEDULED until this stage merges; issues for them already exist.

## What was done

- **Item 1, the README rewritten against the code.** Lane s11-readme (four commits, merged at `2965b54` and `da99cb8`): lane/v1-int merged (the README rewrite and the v1 results page, D-S18 items 2d and 4), every claim read against the code and the records, the install and container commands (the container ones marked not yet run in this loop), the history placeholder S13 fills, the ordering sentence, the narrowed 11.12 fields; round 2 and 3 fixes (D-173, D-174): all four model-text reviews with the benchmark each covers.
- **Item 2, banned claims.** None stands as a claim (lane scans, and the claims auditor in every round).
- **Items 3 and 4.** The privacy layer's status and the single shared token are stated.
- **Item 5, CLAUDE.md, every file in `docs/`, CHANGELOG.** The current documents read against the code (top-level `docs/`, `docs/benchmarks/`, `docs/api/`, the current `docs/fix/` records); dated notes in history only; PREREGISTRATION.md, frozen, left as it is. CLAUDE.md read whole and corrected (the constitution guard, ASSET-COPY-A, three arms, the image's copy list, the ontology's node types, the no-gap rule for INFRA-NNN).
- **Item 6, CITATION.cff.** Version from `VERSION` (0.1.0.dev8), held by new gate check 314; `date-released` 2026-11-02, which must equal the v1 tag's date (D-172).
- **Item 7, the image.** Not rebuilt: it waits for S10's addendum (the pip purge frees the disk), so this stage is tagged `loop-s11-v1-open` until it is.
- **Item 8, the claims and hygiene auditor** over the whole README, the results page and every changed document: round 1 (D-172), with rounds 2 and 3 on the changes since.
- **The format drafts.** The lane's corrections to `docs/INPUT_FORMAT.md` and `docs/OUTPUT_FORMAT.md` were put back byte for byte (S3a item 5 allows only additions the scorer does not read after C0's last run); the 16 verified corrections are open item 71, for preregistration version 3 (D-172).
- **Item 0.3.** The loop branch is merged into `loop/s11` after S10's tag (pending at this draft).

## Decisions

D-171 (S11 starts before S10's merge; the lane merged), D-172 (round 1; the formats put back; dev8), D-173 (D-S21 applied; round 2, run as one combined checker, a recorded departure), D-174 (round 3).

## Gate

At `79ff34d` (traced runner, after run 1 at `dca0f4a` died with the Tk abort, INC-029): PASS 273, WARN 1, SKIP 12, FAIL/ERROR 29 of 315, equal to S10's tip set apart from check 256 (flaky, open item 70; passes alone here). The gate after the loop-branch merge covers the commits after it.

## Checkers

Round 1: completeness 17 gaps, adversarial 6 SERIOUS and 5 MINOR, claims 9, sweep 23 (D-172). Round 2 (one combined checker): 1 SERIOUS, 4 MINOR, 3 claims (D-173). Round 3 (three checkers): 2 SERIOUS, 5 MINOR, 6 claims (D-174). Every item fixed or recorded; no tie-break needed. Private reports `analysis/s11close-round1.md` to `-round3.md`.

## Spend

None (S11 launches nothing).

## Count line

S11 items 1 to 8: done 1 to 6 and 8; open under the tag: 7 (the image). Not now, each with its issue: open items 70 to 73 (S6 and, for 71, preregistration version 3).

## Stage boundary

Instances: none (reaper 0 listed). Storage as in S10's report. Loop-until-certain, three rounds: the image is the one open exit criterion; the uncertainties are check 256's flakiness and the Tk abort (INC-029), neither caused by S11.

## Effort

Opus, medium effort from 28 October 2026 (Annex D, D-S11).
