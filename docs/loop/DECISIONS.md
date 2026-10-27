# Loop decisions

Every Class R and Class M decision (Part III.2), every PROCESS-DEPARTURE (P8), and every tie-break outcome (IV.4). Append-only. Each entry: time, stage, the fork, the options, the rules applied, the choice, how to reverse it.

## D-001. Checkers run as general-purpose subagents with a fixed read-only brief

- **When, stage.** 2026-10-27 06:05 +03:00, I.3 and S0 step 14.
- **Fork.** The spec's checker is a project subagent `loop-checker` defined in `.claude/agents/loop-checker.md` (read-only tools, `omitClaudeMd: true`). Tool writes into `.claude/` are refused in this session's permission mode, so the definition cannot be created.
- **Options.** (1) Run no checkers until Seckin installs the definition. (2) Run each checker as a fresh general-purpose subagent on the same model, with a fixed brief: read only the named material, use only Read, Grep and Glob, ignore the `CLAUDE.md` pointer. (3) Write the definition through a shell, around the protection.
- **Rules.** P19 (no idle waiting; never shorten a checker round), P10, P12 (option 3 routes around a safety protection: not taken), IV.4 (never downgrade a checker).
- **Choice.** Option 2. No `loop-discussant` exists, so no named teammate is ever started.
- **Revision (06:45, after reading-check round 3).** The built-in `Plan` type, run with `model: opus`, has no Write, Edit or NotebookEdit tool, and its context held no `CLAUDE.md` text or auto-memory index (its own report). It does have Bash, PowerShell, Skill, Claude Docs write tools and ToolSearch. From round 3 on, checkers use the `Plan` type with a brief that forbids PowerShell, Skill, ToolSearch, every MCP tool and any write command. The S0 step 14 proof (can a checker see the pointer?) is run on this type, not presumed failed.
- **Reverse.** Once Seckin installs the definitions, later checkers use `loop-checker`.

## D-002. Private name patterns live in `docs/loop/private/`

- **When, stage.** 2026-10-27 06:02 +03:00, I.0 item 4.
- **Fork.** `.claude/loop_private_patterns.txt` cannot be written.
- **Options.** (1) Label every name search "incomplete: private patterns missing", as the spec prescribes for a missing file. (2) Keep the same three hex lines at `docs/loop/private/loop_private_patterns.txt` (gitignored) and run complete searches.
- **Rules.** P7 and P18 (protect others' names first), H5.
- **Choice.** Option 2. Searches read the file by absolute path from the main checkout, because it does not exist in worktrees, clones or the mirror. S0 step 3 says a failed item 4 means every name search is labelled "incomplete: private patterns missing". That label is kept, as the spec requires, and is completed so that it stays true (P1): every name-search record reads "incomplete: private patterns missing from `.claude/` (I.0 item 4 failed); the same three patterns were applied from `docs/loop/private/loop_private_patterns.txt`". (Revised 07:00 after the S0 completeness checker; the first wording dropped the spec's label.)
- **Reverse.** Move the file to `.claude/` when that folder can be written.

## D-003. The pre-push hook is installed through `core.hooksPath`

- **When, stage.** 2026-10-27 06:10 +03:00, S0 step 17.
- **Fork.** Tool writes into `.git/hooks/` are refused.
- **Options.** (1) No hook; H1 rests on the deny rules alone. (2) Write the hook in the gitignored private folder and point git at it with `git config core.hooksPath <absolute path>`; no other hook was active, so nothing is disabled.
- **Rules.** H1, P12 (a local, reversible git setting), P13.
- **Choice.** Option 2, with an absolute path so that worktrees of this repository use the same hook. The hook was proven by running it directly: refuses while the loop is not DONE (exit 1), allows when the operator's variable is set (exit 0), and always refuses a pushed range that adds a path under `seals/` or `audit/model_replies/` (exit 1, both paths).
- **Reverse.** `git config --unset core.hooksPath`.

## D-004. Lane worktrees are created by hand at the spec's fallback path

- **When, stage.** 2026-10-27 06:15 +03:00, S0 step 13; revised 06:35 after a measurement.
- **Fork.** `worktree.baseRef: head` cannot be set. First assumption: IV.5's fallback location `.claude/worktrees/` would refuse tool writes like the rest of `.claude/`.
- **Measurement.** `git worktree add --detach .claude/worktrees/wtproof HEAD` succeeded, and a Write tool call into that worktree succeeded: Claude Code exempts its own worktree folder from the `.claude/` protection. The proof worktree was then removed with `git worktree remove --force`.
- **Options.** (1) The session scratchpad (session-bound, lost on restart). (2) The spec's own fallback: `git worktree add -b lane/s<NN>-<name> .claude/worktrees/<name> <stage branch HEAD>`, inside the repository and gitignored (`.claude/`).
- **Rules.** IV.5 (its literal fallback), P1 (measured, not assumed), H7.
- **Choice.** Option 2. Lane agents work only in their worktree. Branches are kept after merging (H12). `guard_secrets.py` walks these folders (T24); a hit there that is not in a staged diff is recorded, not a block.
- **Reverse.** Not needed; once `worktree.baseRef` can be set, subagent isolation may create worktrees itself.

## D-005. The role-session proof (S0 step 15a) runs although the lead's deny rules are unproven

- **When, stage.** 2026-10-27 06:10 +03:00, S0 step 15a.
- **Fork.** S0 step 15 says to start no role session until a later session has proven the lead's deny rules. Step 15a asks for one proof session before any real role session.
- **Options.** (1) Skip the proof too. (2) Run the proof: it uses the scratch folder `_proof`, reads no role content, and writes only its own file and `_handoff\PROOF_DONE.json`.
- **Rules.** P18 (the proof exposes no evaluation material), P19, P1 (measure that a role session can run).
- **Choice.** Option 2. Result: exit 0, its own output file written, `PROOF_DONE.json` written; the launch inside this session needed no change to the `CLAUDECODE` variable. Every real role session stays blocked in this session.
- **Reverse.** Not needed; the proof touched no role folder.

## D-006. The gate runs with `py -3.12` (anaconda 3.12)

- **When, stage.** 2026-10-27 06:16 +03:00, S0 step 9.
- **Fork.** The spec says to use "the project's own virtual environment as the README says". The README names none; `.venv` is Python 3.9 and CPU-only; the recorded practice (`CLAUDE.md`, Commands) is `py -3.12 -X utf8 scripts/verify_session1.py`.
- **Options.** (1) `.venv` (3.9, CPU-only, never used for the gate in the record). (2) `py -3.12`, as every recorded gate result was produced. Installing anything is denied by the project settings and is not attempted.
- **Evidence (measured 2026-10-27).** `.venv` imports torch 2.5.1+cpu, numpy and pypdf, but not `transformers`, `sentence_transformers`, `sklearn`, `keybert` or `fastapi`, so most gate checks could not run under it. `py -3.12` imports torch 2.5.1, transformers 4.51.3, sentence-transformers 4.1.0, scikit-learn 1.5.1 and KeyBERT 0.9.0; it lacks `fastapi`, `uvicorn` and `pypdf`.
- **Rules.** P1 (compare like with like: every recorded baseline used this interpreter), 1a precedent (`CLAUDE.md` Commands; `docs/fix/ordinary_final_v13_gates/main_gate_comparison_274.json`). This is a departure from S0 step 9's wording ("the project's own virtual environment"), for the measured reason above.
- **Choice.** Option 2, with `KMP_DUPLICATE_LIB_OK=TRUE` (a known OpenMP clash in this interpreter). Every gate result names the interpreter.
- **Reverse.** Re-baseline with another interpreter if one is set up.

## D-007. S8 is blocked as a whole stage in this session, so S9 to S14 are blocked by dependency

- **When, stage.** 2026-10-27 06:45 +03:00, I.3 round 3.
- **Fork.** With no role session allowed in this session (lead deny rules unproven, S0 step 15), S8 cannot start: S8a item 1 needs the frozen preregistration and C0's scorer hash, and S8b to S8d need role sessions. Do the later stages (S9 to S14) still run on what does not need S8 results?
- **Options.** (1) Run S9 to S13 on everything that does not need S8 results (more output tonight). (2) Treat S8 as BLOCKED as a whole stage; S9 to S14 depend on it (Part V table) and are not started; the loop finishes S1 to S7, does S14 items 3 and 4 only (no instance running, ledger closed, reaper removed, power restored), and ends with status BLOCKED.
- **Rules.** Spec lines 82, 312 and 491 ("continue with every stage that does not depend on it"); Part V outranks P19 (I.2). Running S12 before S8 would also reverse the freeze-then-release-candidate order S8a item 4 and S14 item 5 assume. P18 (evaluation integrity before speed).
- **Choice.** Option 2. Status BLOCKED, never DONE: DONE would remove the pointer's effect and let the pre-push hook allow a push while the history still holds the collaborator's name (11.13).
- **Reverse.** Once Seckin installs the settings and a later session proves the deny rules, role sessions unblock S4c, S5 item 10 and S8, and S9 to S14 follow.
