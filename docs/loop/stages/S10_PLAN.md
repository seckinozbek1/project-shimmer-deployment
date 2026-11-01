# S10 plan: fresh-clone smoke test (laptop and Docker)

Drafted 2026-11-01 (system clock, +03:00); revised the same day after plan check 1. Branch `loop/s10`, created from the loop branch `loop/2026-10-27` at the S7 merge commit once it is tagged `loop-s07-v1` (D-159: S10, S11 and S13 each get their own branch from that point). This plan is committed as `docs/loop/stages/S10_PLAN.md` on `loop/s10` before any building. Part V puts S10 after S8; D-S18 moves S8 and S9 after v1, so S10 starts before them, recorded as a departure from Part V's dependency table that the operator's D-S18 requires (as D-154 did for S7 before S6). Opus, medium effort from 28 October 2026 (Annex D, D-S11). v1 is due Monday 2 November 2026 at 12:00 +03:00 (D-S18 item 1); the date is not a cut-off: a step in hand is finished, then what is left goes to `FOR_SECKIN.md`.

## Start of stage

1. Open items read (`docs/fix/OPEN_ITEMS.md` at the branch point) and reported in the stage report. Those touching S10: item 7 (check 252 fails on the Dockerfile's own text, issue #7; settled in item 2.1 e); item 20 (the frozen launchers, issue #25, closed by lane/s06-launchers, which merges here); item 54 (`shimmer.sh` from a non-login Git Bash, fixed in lane s07-r3fix per D-159; its state is re-read at the branch point).
2. The request ledger rows of S10 read (`SECKIN_REQUESTS.md`, stage column S10): S10 items 1 to 4, D-S13 item 2 (the launcher retirement merge), D-S13 item 6b, D-S15 item 1 and D-S17 item 3 (the pip cache purge), D-S18 item 2c. Each gets an issue under the S10 milestone if it has none (D-S16 item 3b).
3. Read-only trace before building (one subagent): every gate check added since the image's last offline gate (11 September, 210 checks; now the length of `CHECKS` at the branch point) that reads a file outside the Dockerfile's copy list (`Dockerfile` lines 130 to 150, T15). Known candidates from a first read: the adapter, generator and baseline checks (they already SKIP when `benchmark/adapters/`, `benchmark/generators/` or `benchmark/baselines/` is absent), the score-corpus check (`docs/INPUT_FORMAT.md` section 9), check 296 (`tools/loop/request_ledger_check_checks.py`, fixtures only per CLAUDE.md), check 302 (`docs/test_change_requests.md`), checks 307 to 311 (the root launchers; their docstrings say they skip without `shimmer.sh`), and anything reading `VERSION`, `CHANGELOG.md`, `docs/loop/`, `archive/` or `pyproject.toml` (none exists yet).
4. Plan check by a fresh `loop-checker` (I.3 step 5); this revision closes plan check 1.

## Lanes (IV.5)

| Lane | Branch, worktree | Items | Files it owns |
|---|---|---|---|
| Launchers retirement (existing) | `lane/s06-launchers` (tip `2513cec`, based on `abd288c`) | D-S13 item 2 (release cleanliness, D-133, D-154) | `archive/frozen_launchers/` (35 files moved with `git mv`, bytes unchanged, its README and `.gitattributes`), `tools/.gitattributes` (9 lines out), `docs/fix/OPEN_ITEMS.md` (item 20 closed) |
| Fresh clone | `lane/s10-fresh`, `.claude/worktrees/s10-fresh`, from `loop/s10` after the launchers merge | 1, 4 (and D-S13 6b) | works in `<USER_HOME>\local\shimmer-fresh-clone\` only; in the repository, only the fixes a defect needs (`shimmer.bat`, `shimmer.sh`, `start_shimmer.bat`, `requirements.txt`, `tools/runtime_contract.py`, `scripts/launcher_checks.py`), each named in its report |
| Image | `lane/s10-image`, `.claude/worktrees/s10-image` | 2 | `Dockerfile`, `.dockerignore`, `tools/entrypoint.sh`, the skip guards in the check modules the trace names, `scripts/verify_session1.py` (registration of any new check only) |
| Lead | `loop/s10` | merges, gates, records | `README.md` (S10 does not edit it; see item 1.7), `CLAUDE.md`, `docs/RUNTIME_REFERENCE.md`, `CHANGELOG.md`, `docs/loop/*`, `VERSION` |

Merge order: lane/s06-launchers, then lane/s10-image, then lane/s10-fresh. The fresh-clone and image lanes share no file; if a defect fix needs a file the other lane owns, the lane describes it in its report and the lead applies it in the merge. Every lane commit checks each new file with `git check-ignore -v` before staging (T1: `**/*key*`, `**/*config*.py`, `**/*secret*` and `**/*credential*` silently drop matching names).

## Items

### 0. Merge lane/s06-launchers (D-133, D-154, D-159)

1. Merge it into `loop/s10` in a commit of its own. Expected conflict: `docs/fix/OPEN_ITEMS.md` only (both sides changed it since `abd288c`); resolved by keeping both sides.
2. A note for the merge: D-154 says the lane "touches `shimmer.bat`, `shimmer.sh` and `start_shimmer.bat`". `git diff --stat loop/2026-10-27...lane/s06-launchers` shows it does not: 39 files, all under `archive/frozen_launchers/`, plus `tools/.gitattributes` and `docs/fix/OPEN_ITEMS.md`. The re-walk is still done (D-154 requires it), and D-154's sentence is corrected by a dated line in the new D-number.
3. Upstream and downstream trace on the merged tree (IV.4 item 2): no live caller of a moved file (`git grep` for each of the 35 module names in `scripts/`, `tools/`, `Dockerfile`, `shimmer.*`, `start_shimmer.bat`, the side gates, `.github/` if present); `tools/.gitattributes` still carries the attributes of the 11 files that stay in `tools/`; the moved files' records under `docs/fix/` are unchanged; T14's frozen test (`tools/test_auditor_feature_remote.py`) now lives under `archive/` and is run by nothing.
4. Re-walk the three launchers as S7 item 5 drove them (`shimmer.bat` through `cmd /c` with piped input ending in `Q`, `shimmer.sh` under Git Bash, `start_shimmer.bat --check-entry --no-browser`), with `SHIMMER_SKIP_INSTALL=1` (the install is item 1's), and re-run checks 307 to 311 and the console view checks 298 to 306 in the loop venv (`<USER_HOME>\local\shimmer-fresh-clone\venv_gate312`). Memory: model-free, 2 GB free (D-135), except check 311's archive test, which starts the real pipeline to its first question (run at 2.73 GB in D-159).
5. Issue #25 (open item 20) is closed with a comment naming the merge commit, after the request ledger check has resolved it (D-S16 item 3c).
6. v1: needed (D-133 counts it as release cleanliness).

### 0b. Defects the S7 close found on the launcher path (S10 item 1 "fix what fails"; D-161, D-162)

1. INC-030: `shimmer.sh` under Git Bash passes `$PWD/.venv/Scripts/python.exe` (a Git Bash path) to Windows Python at line 65, so it refuses the venv it just made. Fix: a path Windows Python can open (relative to the launcher's folder, or `cygpath -w` where present); a launcher check (308's family) that runs the venv step under Git Bash with a Windows interpreter; neutralise, fail, restore, pass; check 311 run once (it drives `shimmer.sh` on Linux).
2. The chat window's model path (private `analysis/s7_6e_plain_language.md`): the startup "Local AI model available" line checks only imports and a registry id (`scripts/redaction_gate.py:50`), and a failed model load or parse falls back to the keyword parser without telling the person (`scripts/chat.py:548-551`). Fix: the startup line says what was checked (model configured, weights not yet loaded), and a reply that came from the keyword parser after a model failure says so; check 310 extended with both, neutralise, fail, restore, pass. The other findings in that report (no memory guard before the first load, raw prompt with no chat template, no `qa` action offered to the model, a model's review mode replacing the person's, "set cutoff" writing a tracked file) are recorded as open items for S6 with their evidence.
3. 6b again: `shimmer.sh`'s own install on a new fresh clone (`s10-sh-3`) after item 1; `shimmer.bat`'s was done at `376f333` (D-160).
4. 6e, plain-language mode: needs about 6 GB free memory to load the 7B model from full-size weights (the run stopped at the 1 GB floor at 4.84 GB free, D-162); run at a 6 GB window if one comes, otherwise it goes to Seckin's person list.

### 1. Laptop fresh clone (spec item 1; D-S13 item 6b; D-157; D-S18 item 2c)

1. **Which tree the proof runs on (DS10-1 as decided by the lead).** The install, the gate and the README-steps check must run on a tree that holds the README being followed. The README that ships is lane/v1-int's, which merges in S11. So S10 item 1's final proof runs in a NEW fresh clone of the loop branch after S11's merge (for example `<USER_HOME>\local\shimmer-fresh-clone\s10-final`), with no `.venv` and nothing copied in. The existing clone `s10-v1` (README install at `3e0de3d`, D-157) is never reused or changed: it stays as a record (H12). S10's own early clone, on the S10 tip, may still run the launchers' installs of item 1.3, since those test `shimmer.bat` and `shimmer.sh`, not the README.
2. **Fresh environment, README steps only (final proof).** In the new clone, run exactly the README's install steps as the tree's README writes them (today, lane/v1-int `0cbe4de`, section "Install", "Manual install (Windows)": `py -3.12 -m venv .venv`, `pip install -r requirements.txt`, and the torch CUDA step only when torch reports no CUDA), then the Quickstart's steps as far as they go without a pipeline run. Record each command, its time and its result. Needs at least 4 GB free memory (D-S13 item 6b, D-013) and free disk above the 30 GB floor plus the install's size (measured on the first install; torch's CUDA wheel alone is about 2.5 GB). No gate or other install runs meanwhile.
3. **Launchers' own install (D-S13 item 6b).** Two fresh clones of the S10 tip with no `.venv`: `shimmer.bat` without `SHIMMER_SKIP_INSTALL`, then `shimmer.sh` under Git Bash (WSL is checked for and recorded as present or absent), hidden, input closed, one at a time, each at 4 GB free and the disk floor above. Existing folders under `<USER_HOME>\local\shimmer-fresh-clone\` (names only; their records are the lead's to read): `d-s13-install`, `d-s13-install-s07`, `d-s13-install-s07-sh`, `d-s13-install-sh`, `s10-bat`. D-158 item 3 queued this on loop/s07. If the lead's records show both installs done on loop/s07 and nothing they run changed between that commit and the S10 tip (`shimmer.bat`, `shimmer.sh`, `requirements.txt`, `tools/runtime_contract.py`, `tools/cloud_run/runtime.json`), the earlier result is cited with its commit and the step is not repeated; otherwise both run again. Record times and results.
4. **Gate in the final clone.** The full gate (`scripts/verify_session1.py`) and the six side gates (IV.7) once, with the clone's own `.venv` interpreter. It is the first gate in this environment, so it is the fresh-clone baseline (IV.7), written to `docs/loop/GATE_BASELINE.md` under "fresh clone, S10". Differences from the main-checkout baseline are explained, not counted as defects; expected: the fastapi and pypdf checks pass here (the clone's venv has them); checks 01 and 145 skip on a tree without `prompts/` or the planted-figure fixture; checks 28 and 31 depend on whether the runtime folders exist, so the record says whether the gate ran before or after Quickstart step 1. The final-integration side gate (`scripts/final_integration_no_generation_gate.py`) rewrites a tracked file when it runs: after it, the file is restored and `git status` must be clean before the image build of item 2 starts from that clone. Memory: about 2.6 to 3.0 GB free (D-151 ran clean at 2.62 GB; D-159 option b), nothing else running; a Claude Code stop for memory is not restarted (D-157), it waits for 4 GB free. Measured progress in every update (IV.9).
5. **Defects.** Every missing step, hidden cache, machine-specific path or undocumented setting found in 1.2 to 1.4 is a defect (spec item 1). A code or launcher defect is fixed in lane/s10-fresh (or, after S11's merge, in a fix lane from the loop branch) with a check where a check can hold it, upstream and downstream traced.
6. **Repeat until clean.** After any fix, the README steps are re-run on another NEW fresh clone of the fixed tree; S10's criterion "a fresh clone passes with only README steps" is marked met only on a clone where no fix was needed. Each clone stays as a record.
7. **README defects.** S10 does not edit README.md (DS10-4). A defect in the README's install text, and the image build and run commands the README must carry for item 2 (S11 item 1.5), are handed to S11 as a numbered list in the lane report; S11 fixes them before its merge, and the final proof of 1.1 then follows the fixed README.
8. **Order this creates.** S10 merges for v1 with items 0, 1.3 and 2 (or 2 deferred) done; item 1's final proof (1.1, 1.2, 1.4, 1.6) runs after S11's merge, and its result is recorded as S10 item 1's evidence in the S10 report's addendum and in the ledger row. If S10 must merge before that proof, its tag is `loop-s10-v1-open` until the proof is recorded (IV.1), and the row stays SCHEDULED with stage S10.
9. v1: needed (D-S18 item 2c: the clean install proven by the loop on a fresh clone; the operator has no second computer).

### 2. Docker image (spec item 2)

1. **Copy list and ignores.**
   - (a) Every check the trace of start step 3 names, that reads generators, adapters, baselines, `external/`, `docs/INPUT_FORMAT.md`, `VERSION`, `pyproject.toml` or another file the image lacks, gets a SKIP with its reason when the file is absent, never a FAIL. Each guard is proven by neutralise, fail, restore, pass (IV.7) on that check alone, plus a no-skip proof: with the file present the check runs its assertions and does not skip. No assertion is removed (H9), and each commit describes the check's old behaviour (IV.6).
   - (b) `VERSION`, the single version source (IV.1), joins the Dockerfile's copy list next to the root markdown files.
   - (c) `seals/` is added to `.dockerignore`; `external/` is already there (`/external/`, `.dockerignore` line 27), so it is confirmed, not added twice.
   - (d) Whether `tools/loop/` ships (DS10-2): it holds 10 tracked files, with 0 personal-path hits and 0 name-pattern hits. Options: (i) ship it as today (`COPY tools/` takes all of it; check 296 runs on fixtures inside the image); (ii) exclude it in `.dockerignore` and make every check that imports it skip. By P13 and P16 (no change the release does not need) and P2 (record it visibly), chosen (i), with a line in `docs/RUNTIME_REFERENCE.md`'s image section saying it is loop machinery that ships inert. Class R.
   - (e) The `ship_gate.py` line: open item 7 (issue #7). Check 252 requires a Dockerfile line exactly `RUN python scripts/ship_gate.py`; `Dockerfile:153` reads `RUN /opt/shimmer-runtime/bin/python scripts/ship_gate.py`, so the check fails on the host (open item 7's evidence). The check guards a ship rule, so the check is not edited (H9, IV.6): the Dockerfile line is restored to exactly `RUN python scripts/ship_gate.py`. This is the same interpreter, since `ENV PATH=/opt/shimmer-runtime/bin:$PATH` is set at line 19; the build log shows the shipping gate ran. Proven by check 252 failing before and passing after. Open item 7 is closed in `docs/fix/OPEN_ITEMS.md` and issue #7 with a comment naming the commit, after the request ledger check has resolved it.
2. **Build.** From S10's early fresh clone (item 1.3's tree, `git status` clean), not the main checkout, `docker build .` with `BAKE_WEIGHTS=false`, the build the 11 September step used (`docs/fix/STEP_DOCKER_REPORT.md`; the baked image was 31.9 GB). Record build time and image size. Needs: Docker Desktop started (its WSL2 virtual machine takes memory of its own), at least 4 GB free memory before it starts, measured, no gate running; free disk above the 30 GB floor plus the image (measured after the build; the torch CUDA layer is its largest part).
3. **Offline gate in the container.** `docker run --rm --network none --gpus all` with a throwaway token hash and nothing mounted, entry point `verify` (`verify_session1.py --offline`). Conflict, surfaced: the spec says "nothing mounted, as the project did on 11 September", but the 11 September run mounted the host's Hugging Face cache (`STEP_DOCKER_REPORT.md` line 41). Resolution (DS10-3, Class R): run as the spec's words say, nothing mounted; record every model-loading check that fails for lack of weights in the container baseline with that reason; then, only if 4 GB free memory remains, run once more with the cache mounted read-only to compare with 11 September's figures, and record both. Never overlap a container gate with a host gate (CLAUDE.md). Record the container baseline in `GATE_BASELINE.md`.
4. **If memory never allows it.** Item 2 is not part of v1 by D-S18 item 2. If no 4 GB window opens before the S10 close, item 2 is a "not now" for memory: under D-S15 item 2 it goes to `FOR_SECKIN.md` with its reason, its row is DEFERRED (stage S10), its issue labelled `deferred`; the image criterion of S10's exit is then unmet and the stage is tagged `loop-s10-v1-open` (IV.1). The work is done after v1 together with S11 item 7.

### 3. Lambda (spec item 3)

The smoke run moved to S12 item 8, and S12 leaves the loop (D-S17 item 3). Nothing to do in S10; the stage report says so and cites D-S17. v1: not needed. Money: none.

### 4. Every defect recorded (spec item 4)

Every defect from items 0 to 2 goes into the S10 report with what found it, the fix and its commit, and the check that holds it. A defect not fixed in S10 goes to `docs/fix/OPEN_ITEMS.md` with an issue (D-S8 item 2) and, for a "not now", a `FOR_SECKIN.md` line with its P9 reason. v1: needed.

### 5. Pip cache purge (D-S15 item 1, D-S17 item 3)

Run `py -3.12 -m pip cache purge` once (the operator's approval for that one command), after the last fresh install that S10 or S11 needs (item 1.6's last clean clone), so no install pays to download again; record the freed size and the free disk before and after. No memory need. v1: not needed.

### 6. D-S13 item 6, the other letters (status only)

6a's loop-end walk of `start_shimmer.bat` is S14's (D-158 item 7); S10's re-walk (item 0.4) is the D-154 one. 6c (the Python 3.12 `.venv` in the main checkout) runs before the S7 merge (D-158 item 7); S10 records its status and, if it has not run, runs it at the first 4 GB window after the S7 merge. 6d and 6e are S7's.

## Gate runs and environments

| Run | Where | Environment, baseline | Memory |
|---|---|---|---|
| G1 after item 0's and item 2's merges (one gate for both under D-159's one-gate-for-several-commits departure if memory allows only one) | `loop/s10` in the lead worktree | lane-worktree baseline (check 28 differs in a worktree); with the side gates | 2.6 to 3.0 GB free |
| G2 final fresh clone, item 1.4 (after S11's merge) | new clone of the loop branch | new fresh-clone baseline | 2.6 to 3.0 GB; 4 GB for the installs before it |
| G3 container, item 2.3 | the built image | new container baseline | 4 GB free with Docker Desktop running |
| G4 after the S10 merge | loop branch, main checkout | main-checkout baseline, "equal to the baseline apart from the recorded exceptions (check 28 in a worktree, the route checks under py -3.12, check 257)" (D-159), with check 252 now expected to pass | 2.6 to 3.0 GB |

One gate at a time, only the lead runs it, never twice at an unchanged HEAD (IV.7). Secret scan on every staged diff (IV.7, `scripts/guard_secrets.py --staged`). No pinned-baseline amendment is expected (no `scripts/pipeline.py` function changes); if one is needed it goes through IV.7.

## Close (IV.4, D-S12 item 3, D-S15 item 7, D-S16 items 2 and 4)

1. Three fresh checkers in parallel (completeness, adversarial, claims and hygiene), on the diff from the S10 branch point, with the outputs (gate logs, install records). The claims and hygiene checker is handed the H5 hex pattern and `.claude/loop_private_patterns.txt` and prints counts only. At most three rounds; tie-break after round three.
2. Look-back sweep over S10 (D-S12 item 3b), its count line in the report.
3. Records consistency check (D-S15 item 7), "N found, N fixed".
4. Loop-until-certain (III.2 step 4).
5. `tools/loop/request_ledger_check.py` PASS; every S10 ledger row and every issue in the S10 milestone DONE or closed, or DEFERRED or BLOCKED with its `FOR_SECKIN.md` entry and label (the stage gate, D-S16 item 2 and item 3d).
6. Outside audit request: `docs/loop/private/audit/REQUEST_S10.md` with the stage, the `loop/s10` tip and the time; work that does not need S10's merge goes on. Fix every finding of `AUDIT_S10.md`, "N found, N fixed" in `DECISIONS.md`, then merge, tag `loop-s10-v1` (or `-open`, items 1.8 and 2.4) and push (ordinary; D-S5 rules 1 and 2, the per-commit range scan first). If no audit arrives 8 hours after the request, write that in `FOR_SECKIN.md` and go ahead; where the 8 hours would pass v1's date, D-S18 item 1 applies.
7. Records: `VERSION` bumped (the Dockerfile and check guards are product), the `VERSIONS.md` row, `CHANGELOG.md`, `S10_REPORT.md`, `LOOP_STATE.md`, the stage-boundary instance list (H4) and storage re-forecast (IV.3).

## Money

None. S10 launches no instance (item 3). Free memory and disk are the binding limits; each step above states its need.

## What v1 needs from S10, and what moves after v1 (D-S18)

| Item | v1 | After v1 |
|---|---|---|
| 0 lane/s06-launchers merge and re-walk | yes | |
| 1 fresh clone, README install, launchers' install (6b), gate | yes (D-S18 item 2c); final proof after S11's merge | |
| 2 Docker image and container gate | no | if no 4 GB window before the close, deferred with S11 item 7 (`-open` tag) |
| 3 Lambda smoke | no | left the loop with S12 (D-S17 item 3) |
| 4 defects recorded | yes | |
| 5 pip cache purge | no | after the last fresh install |

## Exit criteria (spec) and evidence

| Criterion | Evidence |
|---|---|
| Fresh clone passes with README steps only | item 1 records on the final clean clone; G2 log |
| Image passes with README steps only | item 2 records; G3 log (or the recorded deferral and `-open` tag) |
| A gate baseline for each environment | `GATE_BASELINE.md` rows for the fresh clone and the container |
| Checkers closed | three checker reports and closures |
| Tag | `loop-s10-v1` (or `-open`) on the merge commit |

## Decisions this plan needs (III.2)

- **DS10-1** (lead's decision) The final fresh-clone proof runs in a new clone of the loop branch after S11's merge; `s10-v1` is kept as a record. Class R.
- **DS10-2** `tools/loop/` ships in the image, inert (10 tracked files, 0 path hits, 0 name hits). Class R.
- **DS10-3** The container gate runs with nothing mounted; a second, cache-mounted run only if memory allows. Class R.
- **DS10-4** S10 does not edit README.md; README defects and the image commands go to S11. Class R.
- **DS10-5** Check 252 settled by restoring the exact Dockerfile line, not by editing the check (open item 7). Class R, attacked by the adversarial checker (it touches a gate check's subject).

## Specification lines this plan maps

- S10 item 1 (clone, fresh venv, README install, full gate with side gates, fresh-clone baseline, defects fixed until only README steps): items 1.1 to 1.8, G2.
- S10 item 2 (build from the fresh clone, offline gate, network blocked, nothing mounted, container baseline): items 2.2, 2.3, G3.
- S10 item 2 bullet 1 (skip, not fail): item 2.1 a, start step 3.
- S10 item 2 bullet 2 (version source in the copy list): item 2.1 b.
- S10 item 2 bullet 3 (`external/` and `seals/` in `.dockerignore`): item 2.1 c.
- S10 item 2 bullet 4 (`tools/loop/` decided by Part III): item 2.1 d, DS10-2.
- S10 item 2 bullet 5 (keep the `ship_gate.py` line, check 252): item 2.1 e, DS10-5.
- S10 item 3 (Lambda smoke moved): item 3.
- S10 item 4 (record every defect): item 4.
- S10 exit criteria: the table above.
- I.3 step 5 (plan check): start step 4.
- IV.1 (stage branch, merge, tag, `-open` tag, version): header, items 1.8, 2.4, close steps 6 and 7.
- IV.4 items 1 to 6 (plan committed, build, gate, three checkers, close items, merge and report): header, start step 4, close.
- IV.5 (lanes, files owned, shared files with the lead): lanes table.
- IV.6 (failure reasoning; a gate check corrected only on evidence; old behaviour in the commit): items 2.1 a, 2.1 e.
- IV.7 (full gate plus side gates, per-environment baselines, once per commit, secret scan, new checks proven by neutralise, fail, restore, pass, pinned baselines): gate table, item 2.1 a.
- IV.7 T1, T8, T14, T15: lanes table, items 2.1 e, 0.3, 2.1.
- IV.9 (measured progress): item 1.4.
- H5 (patterns to the claims checker): close step 1.
- H12 (`s10-v1` and every clone kept): items 1.1, 1.6.
- D-S5 rules 1 and 2 (checks before the push; ordinary push of branch and tag): close step 6.
- D-S8 items 2 and 5 (issues for open items, kept in step): item 4, start step 2, items 0.5, 2.1 e.
- D-S11 (effort line): header.
- D-S12 item 3b (look-back sweep at the close): close step 2.
- D-S13 item 2 (frozen launchers): item 0.
- D-S13 item 6 a, b, c: items 0.4, 1.3, 6.
- D-S15 item 1 (pip cache purge after S10): item 5.
- D-S15 item 2 (every "not now", including for memory, in `FOR_SECKIN.md`): item 2.4, item 4.
- D-S15 item 7 (records consistency check at the close): close step 3.
- D-S16 item 2 (stage gate): close step 5.
- D-S16 item 3 b, c and d (issues for scheduled rows; closing with evidence; milestone): start step 2, items 0.5, 2.1 e, close step 5.
- D-S16 item 4 (outside audit at the close): close step 6.
- D-S17 item 3 (S12 out; purge once S10 passes): items 3, 5.
- D-S18 items 1, 2c, 3: header, item 1.9, the v1 table.
- D-133, D-154, D-157, D-159 (s06-launchers into S10, its re-walk and checks 307 to 311, the clone at `3e0de3d` kept as a record, one gate for several commits): items 0, 1.1, G1.
- III.2 step 4 (loop-until-certain): close step 4.
