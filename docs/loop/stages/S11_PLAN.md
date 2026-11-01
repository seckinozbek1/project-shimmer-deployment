# S11 plan: release-readiness (image, README and documents)

Drafted 2026-11-01 (system clock, +03:00); revised the same day after plan check 1. Branch `loop/s11`, created from the loop branch at the S7 merge commit once it is tagged `loop-s07-v1` (D-159). This plan is committed as `docs/loop/stages/S11_PLAN.md` on `loop/s11` before any building. Part V makes S11 depend on S9 and S10. D-S18 moves S9 after v1 (a short hardware summary goes into the README instead), so S11 does not wait for S9; that is recorded as a departure from Part V's dependency table that D-S18 requires. S11 waits for S10's merge before its own merge (stage-number order, IV.1), and merges the loop branch into `loop/s11` in a commit of its own once `loop-s10-v1` (or `-open`) exists, so that the README describes the tree S10 proved (IV.1, "waiting on another stage's merge"); from then on its checkers diff against `git merge-base loop/2026-10-27 loop/s11`. Opus, medium effort from 28 October 2026 (Annex D, D-S11). v1 is due Monday 2 November 2026 at 12:00 +03:00 (D-S18 item 1).

## Start of stage

1. Open items read at the branch point and reported. Those touching S11: item 19 part 2 (`reviewed_document.md`, settled by the parallel track's PATCH_2 after v1, D-158), and any item a README sentence would describe as fixed.
2. The S11 ledger rows read (stage column S11): S11 items 1 to 8, D-S18 items 2d and 4, D-S17 item 3's "S11's README promises no package release", the README defects and image commands S10 hands over (S10 plan item 1.7), and S13's request for a "History of this repository" section (S13 plan step 6.4). Each gets an issue under the S11 milestone if it has none (D-S16 item 3b).
3. Read-only trace (one subagent), at the `loop/s11` tip after both the lane/v1-int merge and the loop-branch merge (item 0): every file under `docs/` by folder (at lane/v1-int: 11 at the top level, `docs/api/` 9, `docs/benchmarks/` 5, `docs/history/` 2, `docs/loop/` 47, `docs/fix/` 3,887), which statements in each are contradicted by the code at that tip, and which name a feature changed since S1.
4. Plan check by a fresh `loop-checker` (I.3 step 5); this revision closes plan check 1.

## Lanes (IV.5)

| Lane | Branch | Items | Files it owns |
|---|---|---|---|
| README and results (existing) | `lane/v1-int` (tip `0cbe4de`; holds `lane/v1-readme` `8c9f45b` and `lane/v1-results` `69de0ee`) | 1 to 4 first pass, D-S18 item 4 | `README.md`, `docs/RESULTS.md`, `docs/PRODUCTIZATION_STATE.md`, `docs/api/` six files (one line each), `docs/fix/ROUTING_UI_AUDIT.md`, `docs/history/README_PRE_ROUTING_AUDIT.md` (dated note), `compose.yaml` (one message string), `CHANGELOG.md` and `CLAUDE.md` (lane edits, applied in the merge) |
| Documents | `lane/s11-docs`, `.claude/worktrees/s11-docs`, from `loop/s11` after item 0 | 5 | every file under `docs/` that no other lane owns: `docs/*.md` except `docs/RUNTIME_REFERENCE.md`, `docs/api/`, `docs/benchmarks/`, dated notes in `docs/history/`, the current documents under `docs/fix/` listed in item 5.2; not `docs/loop/` |
| Image | `lane/s11-image` | 7 | none unless a defect needs one (`Dockerfile`, `.dockerignore`, with S10's lane/s10-image changes already merged) |
| Lead | `loop/s11` | merges, items 1 to 6 final pass, 8, records | `README.md` (after the lane/v1-int merge), `CLAUDE.md`, `docs/RUNTIME_REFERENCE.md`, `CHANGELOG.md`, `CITATION.cff`, `VERSION`, `docs/loop/*` |

Merge order: lane/v1-int; the loop branch (after S10's tag); lane/s11-docs; lane/s11-image if it changed a file. The documents lane drafts any `README.md`, `CLAUDE.md`, `RUNTIME_REFERENCE.md` or `CHANGELOG.md` change in its report and the lead applies it (IV.5). Every lane commit checks each new file with `git check-ignore -v` before staging (T1).

## Item 0. Merge lane/v1-int (D-159), then the loop branch

1. Merge `lane/v1-int` into `loop/s11` in a commit of its own. Its base with loop/s07 is `d19613c`; `d19613c..loop/s07` holds 37 commits (counted 2026-11-01; recounted at the branch point and recorded). Expected conflicts (files both sides changed since `d19613c`): `CHANGELOG.md`, `CLAUDE.md`, `README.md`, `docs/api/CONSOLE_PLAN.md`, `docs/api/CONSOLE_STATE_AUDIT.md`, `docs/api/SURFACE_DESIGN.md`, `docs/api/SURFACE_INVENTORY.md`. Each is resolved by keeping both sides' content and then checking the result against the code at the merge (not by preferring one side).
2. Check after the merge that it brought no code: `git diff <branch point> loop/s11 --stat` lists only documents and `compose.yaml` (a message string pointing at `docs/RUNTIME_REFERENCE.md`, Server environment, in place of "README section I"). Any other file is a finding.
3. Merge the loop branch once S10 is tagged, in a commit of its own (IV.1).
4. The README at `0cbe4de` says `VERSION` is `0.1.0.dev4` "at this commit"; the tree after S7 says `0.1.0.dev5` or later. Every such line is brought to the tree S11 merges (item 1).

## Items

### 1. README, rewritten from start to finish against the code (spec item 1)

Every sentence is checked against code or artifacts at the S11 tip, by the lead with one subagent per section (read-only), each sentence given a source (file and line, commit, or run record) in a private working table. lane/v1-int already has the sections: what Shimmer is; what it does and does not do; how a review works; what has been measured; limitations; hardware and cost; install; quickstart; configuration; the constitution and agents; privacy; access; testing rules; reproducing the evaluation; development and validation; citation and licence. Per spec section:

1. **What Shimmer is:** a composition of established mechanisms, not new ones (multi-agent cross-family verification in the multi-agent-debate lineage, under a runtime constitution with a formal amendment process, for defect-intolerant review of regulated documents), citing the related work already in the repository. v1.
2. **What it does and does not do.** v1.
3. **What has been measured.** For v1: the development results of D-S18 item 4 (`docs/RESULTS.md`), every figure "development, exposed", the commit they were measured on, the pilot labels, the contamination note (FinDVer's held-out labels public since 14 July 2026, D-S13 item 7), the limitation line, the ordering line (ordering attested only by local records), history labelled as history with dates and caveats, and the sentence that the benchmark-mode rule was chosen after development scores were seen (D-S13 item 9). After v1 (D-S18 items 3 and 5): the S8 results with every Annex A, 11.12 field, and the release-candidate commit and how it differs from the frozen commit (S12 left the loop, D-S17 item 3, so the README says there is no release candidate yet); these are added by a later README pass, recorded as SCHEDULED rows (stage S14 or S8).
4. **Limitations,** stated plainly. v1.
5. **Install (package and image).** No package is released or promised (D-S17 item 3): the install section names the source install and the image only, and says the package is future work without a date. The source install steps are the ones S10 executes on a fresh clone; S10's handed-over README defects (S10 plan item 1.7) are fixed here. The image part gets its build and run commands (`docker build .`, the `docker run` line with `--network none` and the token hash, the `serve`, `run` and `verify` entry points), as S10 item 2 runs them. A word-for-word comparison of the README's commands with S10's recorded commands is attached to the stage report. The hardware summary (D-S18 item 3, in place of S9) is one short section with measured figures only. v1.
6. **Quickstart; configuration; the constitution and agents; the testing rules (Annex A as amended); how to reproduce the evaluation; costs; citation; licence.** v1, each checked against code; "reproduce the evaluation" describes the development runs and says the sealed evaluation comes after v1.
7. **History of this repository.** A new short section, asked for by S13 (step 6.4): where the history lives, and room for S13's note on the commit map. S11 writes the section with a placeholder sentence that is true before the rewrite; S13 adds the map note in the mirror's commit. v1.
8. The literal text `docs/RUNTIME_REFERENCE.md` stays in the README (check 260, T6).

### 2. Claims that must never appear (spec item 2)

Searched over the whole README and every changed document (not only the diff), by fixed strings and by a reading pass: "87 percent recall"; "5 of 6"; any EU AI Act accuracy result; a second domain called "Pakistan"; "small models found four of five" or any wording crediting models with Python's catches (P5); "privacy masking works"; "domain-agnostic" without its narrow meaning (`CLAUDE.md` line 8 at loop/s07 still says "a standalone, domain-agnostic document processing swarm"; lane/v1-int narrows it at its line 9; the merge keeps the narrowed sentence); "0.06 USD per defect" as a fact; "19 of 19 on a real negotiation" without its caveats; the old name SILICA-Bench (the current name is "Qual Quant Causal Inference Extension for Shimmer", a proof of concept); "error propagation"; any collaborator or client name (the H5 hex pattern and every pattern in `.claude/loop_private_patterns.txt`, counts and file names only; if the patterns file is missing, the search is labelled incomplete); any reviewer or publisher engagement. A first fixed-string count on lane/v1-int's README, `docs/RESULTS.md` and `CLAUDE.md` found none of the fixed phrases; the reading pass is still required. v1.

### 3. Privacy layer (spec item 3)

The README states that LAW-IV today is a startup refusal of sensitive mode, not in-flight masking, and that activating masking needs its own DELTA (lane/v1-int section "Privacy (LAW-IV)"; checked against `scripts/sensitivity_layer/`, `LAYER_ACTIVE` False, the startup refusal, exit 6). v1.

### 4. Identity (spec item 4)

The README states one shared token, so a single-operator system today (lane/v1-int section "Access (one operator)"; checked against `scripts/server.py` and `SHIMMER_TOKEN_HASH`). v1.

### 5. CLAUDE.md, every file in docs/, CHANGELOG.md (spec item 5; documents lane, lead for the shared files)

1. `CLAUDE.md` brought current against the code (lead; the documents lane drafts).
2. Every file under `docs/` brought current, all of it in S11 (no "if time allows"). DS11-1 (Class R): `docs/history/` stays as history with dated notes where contradicted. Under `docs/fix/`, the CURRENT documents are brought current: `RESUME.md`, `LEDGER.md`, `PERSONAL_PATH_INVENTORY.md`, `OPEN_ITEMS.md`, `TUNING_BACKLOG.md`, `REPORT_RECOMMENDATIONS_IMPLEMENTATION.md` (named by CLAUDE.md), and any other the loop's current documents point a reader to; the trace of start step 3 lists them all, and the list goes in the stage report. The run records under `docs/fix/` (many hash-bound, S1 Part 2 class (a)) stay history: never rewritten; where one is contradicted, the dated note goes into the current document that points at it, never into a hash-bound file. `docs/loop/` records are the loop's and are not edited here except the stage's own.
3. `docs/RUNTIME_REFERENCE.md` (lead): keeps the 18-agent roster table, the text "`--activation-profile dense` is the default", every deliverable file name from `run_context` (check 260), and its route table equals the app's routes (checks 167 and 104), its variables table check 116's rule (T5).
4. `CHANGELOG.md` (lead): one entry per product version (IV.1). S11 changes README and documents only (and the CITATION check of item 6, see there), so `VERSION` stays unless item 6's gate check counts as product code; if `VERSION` does not change, S11 adds no new version entry and the current entry (dev6 or dev7) carries one line on S11's documents.
5. No em dashes in any text written or changed (I.4); existing em dashes in untouched text stay. lane/v1-int's README and `docs/RESULTS.md` hold none today.
6. v1: the README, `docs/RESULTS.md`, `CLAUDE.md`, `CHANGELOG.md`, `docs/RUNTIME_REFERENCE.md` and the rest of `docs/` as above.

### 6. CITATION.cff (spec item 6; DS11-2)

The spec says add the version `0.1.0rc1`; S12, which builds `0.1.0rc1`, left the loop (D-S17 item 3), so that version does not exist. Decided (lead, option (ii)): `CITATION.cff` gets a `version` equal to `VERSION` (`0.1.0.devN` at the time), a new gate check compares the two (as S12 item 2 asks; neutralise, fail, restore, pass; it skips when either file is absent, for the image), and `date-released` is corrected from `2026-01-01` to the date of the v1 tag. A fresh `loop-checker` attacks the decision before it takes effect (III.2 step 3: a public-facing text and a gate check). `0.1.0rc1` and its date stay S12's. The new check is product code, so `VERSION` and `CHANGELOG.md` follow item 5.4. v1: needed (the v1 citation names the version shipped).

### 7. Docker image (spec item 7)

Rebuild the image on the S11 tip, run the offline gate inside it (network blocked, nothing mounted, as S10 item 2), record image size and build time. The Dockerfile keeps the exact line `RUN python scripts/ship_gate.py` (check 252; restored by S10 under open item 7). Needs at least 4 GB free memory with Docker Desktop running and disk above the 30 GB floor plus the image. Compared with S10's container baseline. v1: not needed (D-S18 item 2 names S11's README and results page only). If no 4 GB window opens before the S11 close, item 7 is a "not now" for memory under D-S15 item 2 (`FOR_SECKIN.md`, DEFERRED row, `deferred` issue), SCHEDULED after v1 together with S10 item 2 if that was deferred too, and the stage is tagged `loop-s11-v1-open` (the image criterion unmet, IV.1).

### 8. Claims and hygiene auditor over the whole README and every changed document (spec item 8)

A fresh `loop-checker` with the claims and hygiene brief (IV.4) reads the whole README, the whole of `docs/RESULTS.md`, `CLAUDE.md`, `CHANGELOG.md` and every document changed in S11, against the code and the run artifacts, not the diff only: em dashes, personal paths, the collaborator's name (it is handed the H5 hex pattern and the private patterns file, counts only), real names, the banned claims of item 2. This is in addition to the claims checker of the three close checkers. v1: needed.

### 9. The v1 results page (D-S18 item 4)

`docs/RESULTS.md` (lane/v1-results `69de0ee`, merged in lane/v1-int) is checked line by line against its runs (L4a to L12b, the S4 and S5 labels): development results only, every figure "development, exposed", never called held-out or sealed; for each benchmark and the synthetic suite precision, recall, F1, the correct-refusal rate, the cost per finding and the time per document; Shimmer in benchmark mode and as shipped (D-S13 item 9) beside B1; the counts and the sample size behind each figure; a short paragraph on what the figures do not show; FinDVer's public-label statement; that the benchmark-mode rule was chosen after development scores were seen. Built from runs already done; nothing is launched for it. If L12b's or L14b's records change a figure after `69de0ee`, the figure is rebuilt from the record. v1: needed.

### 10. The v1 report (D-S18 item 2f)

Not S11's item; S13 writes `docs/loop/V1_REPORT.md` (S13 plan close step 8). S11 supplies its results paragraph from item 9.

## Gate runs and environments

| Run | Where | Baseline | Memory |
|---|---|---|---|
| G1 one full gate with the side gates at the `loop/s11` tip after the last merge (lane/v1-int, the loop branch, lane/s11-docs, lane/s11-image), under D-159's one-gate-for-several-commits departure; each lane's own checks run in its lane | `loop/s11`, lead worktree | lane-worktree baseline (check 28) | 2.6 to 3.0 GB free |
| G2 container, item 7 | the rebuilt image | S10's container baseline | 4 GB with Docker Desktop |
| G3 after the S11 merge | loop branch, main checkout | main-checkout baseline with D-159's recorded exceptions | 2.6 to 3.0 GB |
| G4 S10's final fresh-clone proof (S10 plan item 1) | new clone of the loop branch after S11's merge | S10's fresh-clone baseline | 2.6 to 3.0 GB; 4 GB for its install |

Checks 104, 116 and 167 need fastapi and run in the loop venv (`<USER_HOME>\local\shimmer-fresh-clone\venv_gate312`) as in S7 (D-054). No pinned-baseline amendment is expected. Secret scan on every staged diff.

## Close (IV.4, D-S12 item 3, D-S15 item 7, D-S16 items 2 and 4)

1. Three fresh checkers (completeness, adversarial, claims and hygiene) on the diff from the merge base; the claims checker is handed the H5 pattern and the private patterns, counts only; at most three rounds; tie-break after round three. Item 8's auditor runs before them.
2. Look-back sweep over S11 (D-S12 item 3b), count line in the report.
3. Records consistency check (D-S15 item 7).
4. Loop-until-certain (III.2 step 4).
5. Stage gate (D-S16 item 2): request ledger check PASS; every S11 row and every issue in the S11 milestone DONE or closed, or DEFERRED or BLOCKED with its `FOR_SECKIN.md` entry and label; the milestone holds no open issue without `deferred` or `blocked` (item 3d).
6. Outside audit request `docs/loop/private/audit/REQUEST_S11.md` (stage, `loop/s11` tip, time); S13's preparation goes on meanwhile; fix every finding of `AUDIT_S11.md`, "N found, N fixed", then merge, tag `loop-s11-v1` (or `-open`, item 7), push (ordinary, D-S5 rules 1 and 2). If no audit arrives within 8 hours, write that in `FOR_SECKIN.md` and go ahead; past v1's date, D-S18 item 1.
7. Records: `VERSION` (item 5.4), `VERSIONS.md`, `CHANGELOG.md`, `S11_REPORT.md`, `LOOP_STATE.md`, the stage-boundary instance list (H4) and storage re-forecast (IV.3).

## Money

None. Item 9 is built from runs already done (D-S18 item 4); no instance is launched in S11.

## What v1 needs from S11, and what moves after v1 (D-S18)

| Item | v1 | After v1 |
|---|---|---|
| 0 lane/v1-int and loop-branch merges | yes | |
| 1 README (development results, no package, image commands, hardware summary, history section) | yes | S8 results, the release-candidate commit and its diff: a later README pass |
| 2 banned claims | yes | repeated in S14's claims audit |
| 3 privacy, 4 identity | yes | |
| 5 CLAUDE.md, CHANGELOG, RUNTIME_REFERENCE, all of `docs/` | yes | |
| 6 CITATION.cff version from `VERSION`, its check, date corrected | yes | `0.1.0rc1` with S12 |
| 7 image rebuild | no | with S10 item 2 if deferred (`-open` tag) |
| 8 claims auditor | yes | |
| 9 results page | yes | sealed results added beside it (D-S18 item 5) |

## Exit criteria (spec) and evidence

| Criterion | Evidence |
|---|---|
| README current and audited | item 1 source table; item 8 auditor report |
| Docs current and audited | the documents lane report with its list of current `docs/fix/` documents; item 8 |
| Image current | item 7 records and G2 (or its recorded deferral and `-open` tag) |
| Checkers closed | three checker reports and closures |
| Tag | `loop-s11-v1` (or `-open`) |

## Decisions this plan needs (III.2)

- **DS11-1** Current documents under `docs/fix/` are brought current; run records stay history (item 5.2). Class R.
- **DS11-2** (lead's decision, option (ii)) CITATION.cff's version read from `VERSION` with a gate check comparing them; `date-released` set to the v1 tag date (item 6). Class R, attacked by a fresh checker.
- **DS11-3** S11 starts before S9 (moved after v1); departure from Part V's table required by D-S18. Recorded.

## Specification lines this plan maps

- S11 item 1 (README rewritten against the code, every listed section, check 260's literal): items 1.1 to 1.8, item 0.4.
- S11 item 2 (banned claims, H5 and private patterns, counts only): item 2.
- S11 item 3 (privacy layer statement): item 3.
- S11 item 4 (one shared token): item 4.
- S11 item 5 (CLAUDE.md, every file in docs/, CHANGELOG; docs/history dated notes; RUNTIME_REFERENCE's three literals and route table, checks 260, 167, 104; no em dashes): item 5.
- S11 item 6 (CITATION.cff version; date in S12): item 6, DS11-2.
- S11 item 7 (rebuild, offline gate, size and time, check 252's line): item 7.
- S11 item 8 (claims auditor over the whole README and every changed doc): item 8.
- S11 exit criteria: the table above.
- I.3 step 5 (plan check): start step 4.
- IV.1 (branch, waiting on S10's merge, merge base for checkers, tag, `-open` tag, version, CHANGELOG per version): header, items 0.3, 5.4, 7, close step 7.
- IV.4 items 1 to 6 and the claims auditor's brief: header, start step 4, item 8, close.
- IV.5 (lanes; shared files with the lead): lanes table.
- IV.7 (gates, side gates, baselines, new checks proven, T1, T5, T6, T7, T8, T15, secret scan): gate table, lanes table, items 5.3, 6, 7.
- I.4 (style, no em dashes, no personal paths, no collaborator name): items 2, 5.5.
- H5 (hex pattern and private patterns, counts only): items 2, 8, close step 1.
- D-S5 rules 1 and 2: close step 6.
- D-S8 items 2 and 5: start step 2.
- D-S11 (effort line): header.
- D-S12 item 3b: close step 2.
- D-S13 items 7 and 9 (FinDVer's public labels; benchmark mode and as shipped): items 1.3, 9.
- D-S15 items 2 and 7: item 7; close step 3.
- D-S16 items 2, 3b, 3d, 4: start step 2; close steps 5 and 6.
- D-S17 item 3 (no package promised; S12 out): items 1.5, 6.
- D-S18 items 1, 2d, 2f, 3, 4, 5: header, items 1.3, 9, 10, the v1 table.
- D-133, D-159 (lane/v1-int into S11; outside audit wait beside the next stage; one gate for several commits): item 0, G1, close step 6.
- III.2 steps 3 and 4: DS11-2, close step 4.
