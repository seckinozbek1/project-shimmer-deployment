# S13 plan: history rewrite, prepared on a mirror, force-pushed only under D-S5 rule 4

Drafted 2026-11-01 (system clock, +03:00); revised the same day after plan check 1, and again on 2026-11-02 after plan check 2 (12 gaps, D-187). Branch `loop/s13`, which starts at `f07667b` (the commit that records the S11 tag `loop-s11-v1-open`, D-186; equal to `origin/loop/2026-10-27`). This plan is committed as `docs/loop/stages/S13_PLAN.md` on `loop/s13` before any step is taken. `loop/s13` holds only this plan, the stage report and the stage's committed records; the rewrite itself happens on a mirror outside the repository, and S13 commits nothing to the loop branch's product files (S14's opening line), with one recorded departure: the v1 report commit sets `CITATION.cff`'s date (see "Before step 0", D-187). Part V makes S13 depend on S12; S12 left the loop (D-S17 item 3), and D-S18 item 2e puts S13's rewrite and push in v1, so S13 follows S11's merge, recorded as a departure from Part V's table that D-S18 requires. Opus, medium effort from 28 October 2026 (Annex D, D-S11). v1 is due Monday 2 November 2026 at 12:00 +03:00 (D-S18 item 1).

The rehearsal of D-142 (2026-10-31, a throwaway mirror under the rules folder; git-filter-repo 2.47.0 rewrote 621 of 660 commits and all 6 tags in 34 seconds with 12 rules; the wider search went from 15,180 hits to 0, the name pattern from 3 to 0; 88 binary or compressed blobs and 61 images checked, 0 hits) is the basis of this plan. Each of its "the real run will" points is adopted below and marked (D-142).

H5 governs every step: the collaborator's project name is never written in any file, command, pattern, commit message, log or reply. It is searched for only with `git grep -lP '(?i)(?<!lla)\x6d\x61\x61\x74(?!tention)'` over a working tree, and, over objects and messages, with the same expression read from a file in the rules folder; only file names, object ids and counts are printed, never a matching line. The personal name and client names are searched only with the hex patterns in `.claude/loop_private_patterns.txt`, the same way. If that file is missing, it goes to the top of `FOR_SECKIN.md` and every name search is labelled incomplete. Path forms are written in this plan by their labels (F1 to F8 of `docs/fix/PERSONAL_PATH_INVENTORY.md`) only; their literal text lives in `<USER_HOME>\local\shimmer-rewrite-rules\forms.txt`, never in a tracked file.

Folders S13 uses outside the repository (three of the five outside folders I.0 permits; H7 lists the forbidden ones, and none of them is touched): `<USER_HOME>\local\shimmer-history-backup\` (empty at drafting), `<USER_HOME>\local\shimmer-mirror\` (empty), `<USER_HOME>\local\shimmer-rewrite-rules\` (holds `forms.txt`, `rehearsal`, `scratch`).

## Start of stage

1. Open items read; S13 ledger rows read (S13 steps 0 to 10, D-S5 rule 4, D-S8 item 6, D-S7's "S13 does not remove them", D-S18 items 2e and 2f), each with an issue under the S13 milestone that passes D-S8 item 3 (D-S16 item 3b).
2. Read the private records the step list needs: `FOR_SECKIN.md` entries S1 Part 1 wrote for hash-bound private-pattern hits; the forms file; the rehearsal's private report (`analysis/lane_s13_rehearse_report.md`, D-142), including where its filter-repo environment is and its 12 rules (cited, never redone blindly).
3. Re-count, at the S11 merge tip, every form (F1 to F8, case variants) over the tracked files and over history (`git log --all -S` per form, reading the literal from `forms.txt`), because the inventory was counted at `loop-base` and the loop has added several hundred commits since. Any new hit added by the loop itself is a defect of that commit and is listed.
4. Plan check by a fresh `loop-checker` (I.3 step 5); this revision closes plan check 1 and plan check 2 (12 gaps, D-187, D-188).

## Lanes

None. Every step writes outside the repository or into private records, and only the lead may write `docs/loop/private/` (IV.5). Read-only subagents (no writes) may run the counts of steps 4, 5 and 8 in parallel, each told the H5 rule and handed only the paths and patterns files. Each commit S13 makes in the repository (this plan, `docs/loop/V1_REPORT.md`, the stage report) checks its new files with `git check-ignore -v` (T1).

## Before step 0: the v1 report, the cut-off and the v1 tag

`docs/loop/V1_REPORT.md` (D-S18 item 2f), short, committed on the loop branch `loop/2026-10-27` after S11's merge and before step 0, so that it is in the rewritten history that step 10 publishes: what v1 holds (S5's close, S7, S10, S11, S13), what moved after v1, what is left and when, and that the rewritten history is published under D-S5 rule 4 once step 10's preconditions hold. It lists the open v1 items: the image (S11 item 7) and issues #37, #48, #134, #106 and #169 (D-184, D-186). Per D-S22 item 5 it says that the README-only fresh-clone proof is the last step before S14's final report, and that the installs already done (D-157, D-160) stand for v1. Under DS13-3 (d) it says that nothing after v1 is published until S14 item 8. The push record itself goes to the private `PUSH_RECORD.md` and later the final report. Its commit is checked with the step 5 searches before the mirror is made.

In the same commit, `CITATION.cff`'s `date-released` is set to the system date of that commit, so the release date names the day v1 was cut (outside audit S11 finding 2, D-178; #165); gate check 314 still holds its version against `VERSION`. If the push lands on a later day, `V1_REPORT.md` already says the date v1 was cut and that it was published at the push; neither file is edited a second time. This commit touches a product file (`CITATION.cff`): a recorded departure from this plan's header and from S14's opening line (D-187). It is covered by G1, the full gate on the pre-rewrite tip, which is this commit and which includes check 314.

**The cut-off.** The mirror is made from one named commit: the V1_REPORT commit, `loop/2026-10-27` at that point, recorded by its full id in `docs/loop/private/` as the cut-off. From step 0 until the push, nothing is pushed from the local repository. Work committed after the cut-off (S13's own records on `loop/s13`, or anything else) is not in v1 and reaches GitHub only through S14 item 8 (DS13-3). Step 10 item 8 checks the cut-off and the remote just before the push.

**The v1 tag.** v1 is the tag `loop-v1`: an annotated tag created in the mirror after the rewrite, on the rewritten commit that holds `docs/loop/V1_REPORT.md` and the `CITATION.cff` date (the cut-off's new id, read from filter-repo's `commit-map`), and published at step 10.

## Steps

### Step 0. Refs on the public remote

1. `git ls-remote <public repository URL>` (read-only). Step 0's `ls-remote` and `fetch`, the stage gate's `gh` reads (the fresh issue list and the S13 milestone, step 10 item 5 and close step 5) and the `ls-remote` of step 10 item 8 are the only contacts with GitHub before the push, and all of them only read. Record every ref with its commit in `docs/loop/private/S13_REMOTE_REFS.txt`. The rehearsal saw 9 branches and 5 tags on the remote (D-142); by S13 `loop/s07`, `loop/s10`, `loop/s11` and their tags will have been pushed too (D-S5 rule 2), so step 0 reads the real list. `refs/pull/*` refs, if any, are listed for `FOR_SECKIN.md` (GitHub Support).
2. `git fetch origin` with explicit refspecs for every branch and tag in that list, so no ref that exists only on the remote keeps a form or the name.
3. Every local ref is listed too (`git for-each-ref`): `refs/heads/` (`main`, `api`, `console`, `docker`, `night-2026-09-11`, `lane-s05-mr-work`, `worktree-agent-ac8b3c3ee7ca191f3`, the `lane/*` branches, the `loop/*` branches), `refs/tags/` and the refs under `refs/codex/turn-diffs/checkpoints/` (written by another tool; they point at trees, not commits), each count recounted at step 0 and recorded there rather than fixed in this plan.

### Step 1. Backup

`git bundle create <USER_HOME>\local\shimmer-history-backup\pre_rewrite_<YYYYMMDD-HHMM>.bundle --branches --tags --remotes` from the local repository after step 0's fetch (never `--all`, which would take the tree refs, D-142), then `git bundle verify` on it, which D-S5 rule 4 needs; record its result and the bundle's ref list (`git bundle list-heads`). Record the bundle's SHA-256 and size in `docs/loop/private/`, never in a tracked file. Never committed, never uploaded. Disk: about the size of the repository's packed objects, measured before; the 30 GB floor holds.

### Step 2. Mirror

1. `git clone --mirror --no-local <local repository> <USER_HOME>\local\shimmer-mirror\repo.git` (`--no-local`, D-142, so objects are copied and not hard-linked to the live repository). Work only under `<USER_HOME>\local\shimmer-mirror\`.
2. In the MIRROR only, before the rewrite: record the 9 `refs/codex/` refs' names and object ids in `docs/loop/private/`, then delete them from the mirror (`git update-ref -d`). filter-repo skips refs that point at trees, so they would keep the hits (D-142). They are never deleted from the local repository and never pushed (DS13-1).
3. `git clone --mirror` sets `remote.origin.mirror = true`, so a plain push from the mirror would act as `--mirror`, which D-S5 rule 4 forbids; filter-repo removes the mirror's `origin` remote anyway. Every push in step 10 goes to the explicit URL of the public repository (the same repository as `origin`; no other remote, D-S5 rule 5) with one explicit refspec per ref (D-142). `git config --get remote.origin.mirror` must print nothing before the push (recorded).
4. Install the `pre-push` hook in `repo.git/hooks/`: it refuses every push unless `SHIMMER_PUSH_OK=1` is set, and refuses any push that adds a path under `seals/` or `audit/model_replies/` (as the main checkout's hook does, D-S5 rule 6). The lead session is started with `SHIMMER_PUSH_OK=1` (D-S5 rule 6), so the hook is a second guard, not a stop.
5. Worktrees: after the rewrite, `git -C <mirror> worktree add <USER_HOME>\local\shimmer-mirror\checkout <rewritten loop branch>` for the gate (step 5) and the commit (step 6). For the pre-rewrite gate, a plain clone of the local repository at the same tip, `<USER_HOME>\local\shimmer-mirror\pre_checkout`. `core.autocrlf` is recorded in both and must be equal, because some hash-bound files match only on their CRLF working-tree hash (inventory section 2).
6. When to make the mirror: from the cut-off, once the v1 report is committed after `loop-s11-v1-open` (D-186), so it holds S10, S11 and the v1 report. The mirror's loop branch is checked to equal the cut-off commit (recorded); a local commit made after the cut-off does not move the mirror. S13's own records stay on `loop/s13` until its close and reach the public history through S14 item 8 (step 11).

### Step 3. Rewrite with git filter-repo

1. **Environment.** `git filter-repo` is not installed in the main checkout's Git. Reuse the rehearsal's environment if its report records it (git-filter-repo 2.47.0, D-142); otherwise install it with pip into a new virtual environment the loop creates, `<USER_HOME>\local\shimmer-rewrite-rules\venv` (D-S2: only into loop-made environments). Record the version.
2. **The expression file** `<USER_HOME>\local\shimmer-rewrite-rules\expressions.txt`, outside both repositories, never committed, used for both `--replace-text` and `--replace-message` (start from the rehearsal's 12 rules):
   - one `literal:` rule per path form exactly as `forms.txt` writes it, with its separators: F1 to F8 and every case variant, even where the inventory counted none (a rule that matches nothing costs nothing); each becomes `<USER_HOME>`, and F5, the slug, becomes a neutral slug written in the file;
   - order: longer forms first: F7 (the WSL form) before F6 (the Git Bash form, which it contains), and every prefixed variant before its bare form; each form is tested on its own (step 3.3);
   - no rule on the bare account name or the public GitHub account name (T23): they would also hit the author's name and the account in `CITATION.cff` and `LICENSE`;
   - the name: a `regex:` rule built from the hex pattern by a script, so it is never typed, that replaces the WHOLE token containing the match (as S1 Part 1 did; D-142), not only its four letters, with a neutral phrase that reads in both places it occurred (a remote name and a folder name), for example "an external project";
   - a hazard check before the run: for each path form, the count of its matches followed directly by a letter or digit (a longer account name would become `<USER_HOME>` plus a remainder); expected zero, recorded.
3. **Test first** on a throwaway copy (`<USER_HOME>\local\shimmer-mirror\test.git`): the name rule on the six `LlamaAttention` files (24 hits must stay) and on the old versions of the two known files (`docs/fix/SESSION_HANDOFF.md` from `d1aca5c`, `docs/fix/WORDS_D_INVENTORY.md` from `e1fbad7`): the whole token gone, counts only; each path rule on one file per form, in the order above.
4. **File and folder names.** List every path in history (`git log --all --name-only --format=`). The inventory found no form and no name in any of 9,968 paths at `loop-base`; the list is re-made at the mirror's tip. A path holding a form is renamed with `--path-rename` (forms are not H5); a path holding the name only with a `--filename-callback` that finds it by the hex pattern, never `--path-rename`. Expected: none of either.
5. **Run** on `repo.git`: every branch (`main`, `api`, `console`, `docker`, every fetched remote branch, `loop/*`, `lane/*`, the three other local branches) and every tag. Author names and emails unchanged (no mailmap, no name callback). Save filter-repo's `filter-repo/commit-map` and `ref-map` files to the rules folder.
6. **Hazards (T23).** Class (b) code in old commits (for example `tools/ordinary_final_rehearsal.py` `LINUX_ROOT`, which fed an `rm -rf`) becomes the literal `<USER_HOME>`: history only, never run; S1 Part 3 fixed the live tree. The tracked v5 to v8 evidence that gate checks replay (`tools/ordinary_final_correction_checks.py`) carries no form and must not move; the rewrite moves no file. Files lane/s06-launchers moved to `archive/frozen_launchers/` are rewritten where they hold a form, like any other.

### Step 4. Binary and compressed files

1. List every binary or compressed blob in history at the mirror (by extension and by content for blobs with no extension). Known at `loop-base` (inventory section 4, counted by path; the spec counts blobs; both are recorded): docx 5, npy 4, pkl 5, png 14, safetensors 2, tar.gz 11, zip 5 (46 paths). The rehearsal found 88 blobs and 61 images in a mirror of 660 commits (D-142); the loop has added more since (the S7 console screenshots, any evidence archive force-added under `docs/fix/`).
2. Unpack each blob to `<USER_HOME>\local\shimmer-rewrite-rules\scratch\<object id>\` (outside both repositories), archives within archives too, and search the contents for every form, the name pattern and the private patterns, counts only. Look at each image; record for each: no form, no name, no real name, no secret, or the hit.
3. Alter none of them. Each hit goes to `FOR_SECKIN.md` (removing or replacing a file in history is a separate decision). The SummEdits files under `tuning/auditor_external_relation_v1/` stay (D-S7); a hit there is reported, not removed.
4. Disk: measured before unpacking; unpacked copies are emptied from the scratch folder after the counts are recorded (recreatable, not covered by H12).

### Step 5. Verify, wider than the replacement list

1. Over every object in the rewritten mirror (read by a small script kept in the rules folder from `git cat-file --batch-all-objects`, after filter-repo's own repack and reflog expiry), every commit and tag message, and every path: the wider expression of S13 step 5 (read from `verify_expression.txt` in the rules folder, written there from the specification), the name pattern and the private patterns. Expected: zero hits. Print counts and object ids only.
2. D-S5 rule 1, over the whole rewritten history, because a force-push publishes every commit: no added line with a personal path; the secret scan (the key patterns of IV.7 over every blob, and `scripts/guard_secrets.py`'s pattern logic on the checkout); and no path in any commit under `seals/`, `audit/model_replies/`, `docs/loop/private/`, `external/` or `prompts/` (expected zero). Every committed file under `docs/loop/` passes the same checks.
3. **Gates.** The full gate with the six side gates on the pre-rewrite tip (`pre_checkout`, the cut-off commit) and then on the rewritten tip (`checkout`), one after the other, with the same interpreter (named in the report) and the same `core.autocrlf`. The pre-rewrite run is this environment's baseline. Memory follows the rule under "Gate runs and environments" (D-S25, D-135, D-141), nothing else running; about 12 to 18 minutes each plus the side gates when run whole (D-159), measured progress in every update (IV.9). The only new red checks allowed are those that verify hashes of files the rewrite changed (S1 Part 2 class (a)); each is listed with the file and the record it checks, and not fixed. Any other new red is a defect in the rewrite: fix the expression file and redo steps 3 to 5 on a fresh mirror (`repo.git` is never edited by hand).

### Step 6. Commit map and commit numbers

1. Write `docs/history/COMMIT_MAP.md` in the rewritten mirror's `checkout`: old commit to new commit for every commit, from filter-repo's `commit-map` (full hashes, and a column for the 7-character short form).
2. In one new commit on the rewritten loop branch in the mirror (never on the local loop branch), update the commit numbers cited in the prose documents of S1 Part 2's class (d), as the spec says, and no others: `docs/fix/LEDGER.md`, `docs/fix/SESSION_HANDOFF.md`, `docs/fix/STEP_DOCKER_REPORT.md`, `docs/fix/STEP_W7_REPORT.md` (the inventory's list; re-checked at the tip). Only whole-word matches of a full hash, or a short hash that is a unique prefix in the map, are replaced. Every file changed is listed. Hash-bound records (class (a)) and generated logs (class (c)) stay as they are (step 7).
3. DS13-2: the loop's append-only records (`docs/loop/DECISIONS.md`, `docs/loop/VERSIONS.md`, `docs/loop/BUDGET.md`, the stage reports) keep their cited hashes, and in the same mirror commit one dated line is appended to each saying the hashes before the rewrite map through `docs/history/COMMIT_MAP.md`. Those appended lines exist only in the mirror commit; S14 item 8 rebuilds them on the final tip.
4. The README's history note: S11 adds a new short section "History of this repository" (S11 plan item 1.7); in this commit S13 adds there the short note explaining the map.
5. The walkthrough deck and the evaluation document live outside the repository: listed in `PUSH_INSTRUCTIONS.md`.
6. Before step 10, the step 6 tip passes step 5's searches, and either the full gate with the side gates or, at least, checks 260, 104, 116 and 167 with the side gates (the README and documents changed); the result is one of step 10's preconditions.

### Step 7. Hash-bound records

73 to 78 path-bearing files (the inventory's two counting methods, which supersede the spec's "about 53") bound by about 25 to 40 records. They are left as they are. The note that they describe pre-rewrite content and can be verified against the private backup bundle goes into `docs/history/COMMIT_MAP.md`, with the list of those records, not into the records themselves, since a note inside a record would change its hash and the records that hash it (DS13-4).

### Step 8. Wider public-content sweep (read-only)

Over every object and message of the rewritten history: the S11 banned-claims list; client or authority engagement documents; the negotiation corpus's real file names (the private patterns). Counts and paths only. Each hit goes to `FOR_SECKIN.md`, changing nothing (D-142: the rehearsal found banned-claim strings in old records and one engagement phrase). H6 holds: only the anonymised corpus may be public.

### Step 9. Push instructions

`docs/loop/private/PUSH_INSTRUCTIONS.md`, written for Seckin and kept current, even though D-S5 lets the loop push:

- (a) refs on the public remote from step 0, each with its old commit, new commit and the exact `git push <URL> --force-with-lease=<ref>:<old commit> <new commit>:<ref>` line;
- (b) the loop's refs: `loop/*`, `lane/*`, `loop/failed/*`, `loop/pre-existing-*`, `loop-base`, the `loop-s*` tags (no release-candidate tag exists: S12 left the loop, D-S17), and the local refs no pattern names (`night-2026-09-11`, `lane-s05-mr-work`, `worktree-agent-ac8b3c3ee7ca191f3`, which stay local, D-142; the `refs/codex/` refs, local repository only), each marked "never pushed" or "pushed under D-S5 rule 2";
- `loop/s13` and `loop/s06c` are never pushed in S13 (step 10): `loop/s13`'s records go out with S14 item 8 (step 11.5), and `loop/s06c` was never pushed and is unmerged;
- which branches are meant for the public remote (`main`, `api`, `console`, `docker`), and that the loop branch reaches `main` by a merge after S14's final checkers (D-S5 rule 3);
- never `git push --mirror`, `--all` or `--tags`;
- pull-request refs, forks and cached views of old commits need GitHub Support;
- every local clone must be re-cloned afterwards, and which ignored local files to move out of the old clone first (the v12 evidence archive, `docs/loop/private/`, `seals/`, `external/`, the main checkout's `.venv` and `.venv_py39_kept_d-s13/`, `durable/`, `output/`);
- the deck and the evaluation document cite old commit numbers and should be updated from the map;
- the `pre-push` hooks refuse pushes until `SHIMMER_PUSH_OK=1` is set, and after step 10 the main checkout's hook refuses every push (DS13-3 b);
- whether the committed `docs/loop/` records go public is his choice (they go with the loop branch under D-S5 rule 2 already; the instructions say so).

### Step 10. The push, under D-S5 rule 4 (this amends spec step 10)

Spec step 10 says never push; D-S5 amends H1 and S13: the loop force-pushes the rewritten history itself, and D-S18 item 2e puts that push in v1. The push happens only if all of these hold, each recorded with its evidence:

1. the backup bundle passes `git bundle verify` (step 1);
2. the zero-hit verification passed on this mirror (steps 5.1 and 5.2);
3. the gate on the rewritten tip shows only the expected hash-check changes (step 5.3);
4. the step 6 tip passed its searches and its gate or checks (step 6.6);
5. D-S16 item 2's stage gate for S13 passes before the push: the request ledger check (`tools/loop/request_ledger_check.py`), `tools/loop/issue_deferral_check.py` (gate check 315, D-180) run on a fresh `gh issue list` saved for it, and the S13 milestone (its issues DONE or closed, or DEFERRED or BLOCKED with their `FOR_SECKIN.md` entry and label);
6. S13's checkers are closed, and the outside audit file `AUDIT_S13.md` has arrived and every finding is fixed (D-S16 item 4). An audit finding that changes the expression file or the mirror redoes steps 3 to 6 on a fresh mirror, with their verification (steps 4, 5.1, 5.2) and their gates (G2, G3), and the auditor is told the new tip. The 8-hour go-ahead of D-S16 item 4 is refused for this push, because the force push cannot be undone (P12, P18); since that can hold v1 back, the refusal is a Class R departure, recorded as D-188 (DS13-5). With no audit file, the push waits and `FOR_SECKIN.md` says so;
7. the pre-push checks of IV.7 on the rewritten range (D-S5 rule 1, covered by step 5.2);
8. the cut-off still holds: just before the push, a fresh `git ls-remote <URL>` is compared ref for ref with step 0's record, and the local loop branch with the cut-off commit (both recorded). If the remote moved, steps 0 to 6 are redone on a fresh mirror, with their verification and gates. Local commits after the cut-off do not move the mirror; they are not in v1 (see "The cut-off").

Then:

- What is pushed, each ref rewritten, one ref per command, to the public repository's explicit URL (D-142): the rewritten `main` and the other public branches of group (a) (`api`, `console`, `docker`, as step 0 lists them); the loop branch `loop/2026-10-27`; the stage branches already on the remote (as step 0 lists them); the stage tags; and `loop-v1`. Never `loop/s13` (its records go out with S14 item 8, step 11.5), never `loop/s06c` (never pushed, unmerged), never `lane/*`, `loop/failed/*`, `loop/pre-existing-*`, the three unnamed local branches or the `refs/codex/` refs. Never `--mirror`, `--all` or `--tags`.
- Leases. A branch: `--force-with-lease=refs/heads/<b>:<its commit from step 0>` with `<new commit>:refs/heads/<b>`. An annotated tag: `--force-with-lease=refs/tags/<t>:<the tag object id from step 0's ls-remote>`, taken from the `refs/tags/<t>` line and not from the peeled `refs/tags/<t>^{}` line (which names the commit), with the rewritten tag object as the new side, `<new tag object>:refs/tags/<t>`. `loop-v1`, which the remote does not hold, is pushed with `--force-with-lease=refs/tags/loop-v1:` (empty: the ref must not exist).
- Record every pushed ref with its old and new commit in `docs/loop/private/PUSH_RECORD.md` (and later in the final report).
- What only GitHub Support can do (pull-request refs, cached views of old commits, forks) goes to `FOR_SECKIN.md` as information, not as a question.
- **D-S8 item 6.** After the push, add one comment per open issue that cites a commit, giving the new hash from `COMMIT_MAP.md`; each comment passes D-S8 item 3's checks (H5 pattern and private patterns over the text first). Closed issues are not touched.

### Step 11. After the push: what the local repository may push (DS13-3)

1. The local repository keeps the old history, and the loop goes on there (S6's moved items, S8, S9, S14). Any ordinary push from it after step 10 would publish old commits again, bringing the name and the paths back.
2. Options: (i) after step 10, no push of any ref from the unrewritten local repository; later stages reach GitHub only through S14 item 8's final rewrite and its push; (ii) move the loop's work into a clone of the rewritten mirror (every worktree, venv, private record and role folder path would move mid-loop); (iii) keep pushing ordinarily (re-publishes the old history).
3. Chosen (i) by P7, P18, P12 and P3, Class R, attacked by a fresh checker (III.2 step 3: it changes when public text is updated), with these four corrections:
   - (a) Its basis is D-S5 rule 1 (no added line may carry a personal path or the name, which every old commit would). It departs from D-S5 rule 2 ("push after each stage merge") and from D-S16 item 2's "merged, tagged and pushed" for the stages between S13 and S14 item 8: recorded as such in `DECISIONS.md`.
   - (b) After step 10, the main checkout's `pre-push` hook refuses every push from the local repository and all its worktrees (a lead-private file; the change is recorded). Reverse: remove that refusal.
   - (c) In that window, issues and comments cite stage tags or D-numbers, not commit hashes; D-S8 item 6 is scheduled again after S14's push.
   - (d) A ledger row (stage S14) records the window; the v1 report and `FOR_SECKIN.md` say that nothing after v1 is published until S14 item 8.
4. S14 item 8's push is itself a D-S5 rule 4 force-push: its leases are taken from a fresh `ls-remote` at that time, not from this step's list. `git filter-repo` is deterministic for the same input and the same expressions, so the final rewrite should reproduce this rewrite's commits with the later ones on top; S14 item 8 records whether the step 10 refs are ancestors of the final refs.
5. S13's own records (`S13_REPORT.md` and the stage merge) are committed on the local loop branch and published by S14 item 8.

## Gate runs and environments

| Run | Where | Baseline | Memory |
|---|---|---|---|
| G1 pre-rewrite tip (the cut-off, the v1 report commit), full and side gates; includes check 314 | `<USER_HOME>\local\shimmer-mirror\pre_checkout` | new environment; this run is its baseline | the memory rule below |
| G2 rewritten tip, full and side gates | `<USER_HOME>\local\shimmer-mirror\checkout` | G1 (same interpreter, same `core.autocrlf`) | the memory rule, after G1 ends |
| G3 step 6 tip: full and side gates, or checks 260, 104, 116, 167 and the side gates | `checkout` after the step 6 commit | G2 | the memory rule |
| G4 after S13's merge into the loop branch | main checkout | not needed: S13's commits on `loop/s13` change only `docs/loop/` (IV.7), so the record cites the last loop-branch gate | none |

**Memory, for every gate in S13 (D-S25, D-135, D-141).** Free memory is read before each run. The whole gate runs at once only at 4 GB free or more. Below that it runs in chunks with the scratchpad runner, which takes `<progress> [start] [stop]` (its progress file and the first and last check of the chunk): model-free checks only at 1 GB free or more, model-loading checks only at 4 GB or more, waiting for memory between chunks. If the host stops a gate for memory, the gate resumes in chunks from the check where it stopped, without asking the operator again (D-185), and `FOR_SECKIN.md` says so. The side gates' model-loading parts run only at 4 GB free or more. Nothing else that loads a model runs beside a gate.

Other needs: filter-repo over the whole history (a few hundred MB of memory, 34 seconds in the rehearsal); disk for the mirror and the test copy, each about the repository's packed size; the bundle (same order); step 4's unpacking (measured before). No step loads a model except the gates.

## Close (IV.4, D-S12 item 3, D-S15 item 7, D-S16 items 2 and 4)

1. Three fresh checkers in parallel on S13's outputs (the counts, the expression file's rule list without the name, the commit map, the gate comparison, `PUSH_INSTRUCTIONS.md`), each told H5 and handed the hex pattern and the private patterns file, with read access to the mirror and rules folders; at most three rounds; tie-break after round three.
2. Look-back sweep over S13 (D-S12 item 3b).
3. Records consistency check (D-S15 item 7).
4. Loop-until-certain (III.2 step 4).
5. Stage gate (D-S16 item 2), run before the push (step 10 item 5) and again here: request ledger check PASS; `tools/loop/issue_deferral_check.py` (check 315, D-180) PASS on a fresh `gh issue list`; S13 rows and the S13 milestone issues DONE or closed, or DEFERRED or BLOCKED with `FOR_SECKIN.md` entry and label; and a `FOR_SECKIN.md` block listing every loop-deferred issue opened or moved in S13 (D-S24 item 5).
6. Outside audit request `docs/loop/private/audit/REQUEST_S13.md` with the stage, the `loop/s13` tip, the mirror's rewritten tip and the time. The step 10 push waits for `AUDIT_S13.md` and its fixes ("N found, N fixed" in `DECISIONS.md`) with no 8-hour go-ahead (step 10 item 6, D-188); a finding that changes the expression file or the mirror redoes steps 3 to 6 on a fresh mirror with their verification and gates, and the auditor is told the new tip. The stage merge and tag that are local may go ahead after 8 hours under D-S16 item 4 as usual, with a `FOR_SECKIN.md` line.
7. Merge `loop/s13` into the loop branch, tag `loop-s13-v1` (local; published through S14 item 8 under DS13-3).
8. Records: the stage-boundary instance list (H4), the storage re-forecast (IV.3), the `VERSIONS.md` row, `S13_REPORT.md`, `LOOP_STATE.md`.

## Money

None. No instance is launched in S13.

## What v1 needs from S13, and what moves after v1 (D-S18)

All of steps 0 to 10 and the v1 report are v1 (D-S18 items 2e and 2f: the rewrite and its push, so the name leaves the public history). After v1: the repeat at S14 item 8 on the final tip, in `<USER_HOME>\local\shimmer-mirror\final\`, with a second backup bundle, and its push under rule 4 (step 11); D-S8 item 6 again after that push.

## Decisions this plan needs (III.2)

- **DS13-1** The 9 `refs/codex/` tree refs are recorded and deleted in the mirror only, before the rewrite; never deleted from the local repository, never bundled, never pushed (D-142). The three unnamed local branches are rewritten and never pushed. Class R.
- **DS13-2** Append-only loop records keep their hashes and get one appended pointer line each, in the mirror commit only, rebuilt at S14 item 8 (step 6.3). Class R.
- **DS13-3** No push from the unrewritten local repository after step 10 until S14 item 8, with corrections (a) to (d) (step 11). Class R, attacked by a fresh checker; a departure from D-S5 rule 2 and D-S16 item 2's "pushed", recorded.
- **DS13-4** The note for hash-bound records lives in `COMMIT_MAP.md`, not inside the records (step 7). Class R.
- **DS13-5** The push waits for the outside audit and its fixes; D-S16 item 4's 8-hour go-ahead is refused for it, because the force push cannot be undone (P12, P18). It can hold v1 back, so it is a Class R departure, recorded as D-188 (step 10 item 6).
- The cut-off, the `loop-v1` tag and the `CITATION.cff` departure (before step 0) are recorded in D-187 with the rest of plan check 2's fixes.

## Specification lines this plan maps

- S13 opening (the 26 October decision; commit numbers from a map): header, step 6.
- Step 0 (ls-remote, fetch every remote branch, record the list): step 0.
- Step 1 (bundle of every branch and tag, in the backup folder, never committed or uploaded; P3): step 1.
- Step 2 (`git clone --mirror` into `shimmer-mirror\repo.git`, work only there, worktree for the gate and step 6, `pre-push` hook with `SHIMMER_PUSH_OK`): step 2.
- Step 3 bullet 1 (expression file outside both repositories, same file for text and messages): step 3.2.
- Step 3 bullet 2 (each form exactly as the inventory wrote it, each case variant its own rule, to `<USER_HOME>`, the slug to a neutral slug): step 3.2.
- Step 3 bullet 3 (never the bare account name or the account): step 3.2.
- Step 3 bullet 4 (the name by the hex regex; test on the six `LlamaAttention` files and the two known files): steps 3.2, 3.3.
- Step 3 bullet 5 (every path; `--filename-callback` for the name, never `--path-rename`): step 3.4.
- Step 3 bullet 6 (every branch including `api`, `console`, `docker` and fetched remote branches, every loop tag; authors unchanged): step 3.5.
- Step 3 bullet 7 (hazards: class (b) code, `LINUX_ROOT`; v5 to v8 evidence not moved): step 3.6.
- Step 4 (list every binary and compressed blob, unpack under the rules folder's scratch, search, look at each image, alter none, hits to `FOR_SECKIN.md`): step 4.
- Step 5 (the wider search over every blob, message and path, zero hits; full gate with side gates on the rewritten tip against the pre-rewrite tip; only class (a) hash checks may turn red, listed not fixed): step 5.
- Step 6 (`COMMIT_MAP.md`; one commit updating class (d) commit numbers; list the files; README history note; deck and document in `PUSH_INSTRUCTIONS.md`): step 6.
- Step 7 (hash-bound records left as they are, with a note): step 7.
- Step 8 (banned claims, engagement documents, real file names; counts and paths; `FOR_SECKIN.md`): step 8.
- Step 9 (`PUSH_INSTRUCTIONS.md`, groups (a) and (b), public branches, the merge into `main`, no `--mirror`/`--all`/`--tags`, GitHub Support, re-clone, ignored files to move, deck and document, hooks, `docs/loop/` choice): step 9.
- Step 10 (never push), as amended by D-S5 rule 4 and D-S18 item 2e: step 10.
- S13 exit criteria (refs listed and fetched; bundle; zero hits; compressed files and images checked; gate compared; map and class (d) update; sweep; push instructions; checkers closed): steps 0 to 9, close.
- H1 as amended by D-S5; H5; H6; H7 (no forbidden folder touched) and I.0 (only the five permitted outside folders); H12 (nothing deleted that cannot be recreated; the tree refs kept in the local repository): header, steps 2.2, 4.4, 8, 11.
- I.3 step 5 (plan check): start step 4.
- IV.1 (stage tag; records): close steps 7 and 8.
- IV.4 (plan committed, checkers, close): header, start step 4, close.
- IV.7 (gate plus side gates, baselines, docs-only commits need no gate, secret scan) and T1, T23: lanes paragraph, steps 3.6, 5, 6.6, gate table.
- IV.9 (measured progress): step 5.3.
- H4 and IV.3 (instance list, storage re-forecast at the stage boundary): close step 8.
- D-S2 (installs only into loop-made environments): step 3.1.
- D-S5 rules 1, 2, 4, 5, 6: steps 2.3, 2.4, 5.2, 10, 11.
- D-S7 (SummEdits stays): step 4.3.
- D-S8 items 3 and 6 (issue text checks; new hashes on open issues after the push; again after S14): steps 10, 11.3 c.
- D-S11 (effort line): header.
- D-S12 item 3b; D-S15 item 7; D-S16 items 2, 3b, 4: close steps 2, 3, 5, 6; start step 1; step 10 items 5 and 6.
- D-S22 item 5 (the README-only fresh-clone proof before S14's final report; the installs of D-157 and D-160 stand for v1): the v1 report.
- D-S24 item 5 (loop-deferred issues listed for the operator) and D-180 (the deferral check, check 315): close step 5, step 10 item 5.
- D-S25, D-135, D-141, D-185 (gate memory, chunked resume): the memory rule under "Gate runs and environments", step 5.3.
- D-187 (plan check 2), D-188 (the go-ahead refused for the push): header, before step 0, step 10, DS13-5.
- D-S17 item 3 (no release-candidate tag): step 9.
- D-S18 items 1, 2e, 2f, 3: header, the v1 report, step 10, the v1 section.
- D-142 (the rehearsal's "the real run will" points): steps 1, 2.1, 2.2, 2.3, 3.1, 3.2, 8, 9, 10.
- D-159 (S13 on `loop/s13` with steps 0 to 9 and rule 4's preconditions; audit per stage): header, step 10, close step 6.
- III.2 steps 3 and 4: DS13-3, close step 4.
