# BDEV: how to start it (IV.10a item 9 form)

> **Dated note, 2026-10-27 16:05 +0300 (commit 3014810).** This file is the earlier blocked form. Role sessions became allowed (D-027), and B-dev ran on 27 October 2026 from 12:56:05 to 13:07:26 +0300 with the IV.10a item 4 flags (`--restricted`), started detached by the lead (D-032). `ROLE_BDEV.md` beside this file now holds the instructions actually used (SHA-256 `047d4f845148451865c11e74d0a0e6b8eb0ee87f43708bc93a5d98a79682beb5`): the same mechanical assembly as the earlier draft (`984e2a1a...`) plus Annex D's heading, its opening sentence and D-S3, word for word, because D-S3 amends H13 for ContractNLI, and without the earlier draft's two `---` separator lines (the one after B.15, before Part II, and the one after H17, at the end).

This session could not run role sessions (D-007: the lead's deny rules were not proven in this session, S0 step 15), so the B-dev step of S4c is BLOCKED here. `ROLE_BDEV.md` beside this file was assembled mechanically by IV.10a item 2; its SHA-256 is in `docs/loop/stages/S04_REPORT.md`.

## Before starting

1. Copy into `<USER_HOME>\local\shimmer-roles\B\inputs_BDEV\`: `docs/INPUT_FORMAT.md`, `docs/benchmarks/PREREGISTRATION.md`, `docs/benchmarks/SELECTION.md`.
2. Copy `ROLE_BDEV.md` into `<USER_HOME>\local\shimmer-roles\B\`.
3. Write `<USER_HOME>\local\shimmer-roles\B\role_settings_BDEV.json` as IV.10a item 3 says for B (Read on `B\` and `_handoff\`; Edit on `B\`, `_handoff\` and `_xfer\B_to_lead_dev\`; allow `Bash`, `WebFetch`, `WebSearch`, `Read`, `Edit`, `Write`; deny the repository, the other role folders and the H7 folders; `autoMemoryEnabled: false`; `disableClaudeAiConnectors: true`; `effortLevel: high`; `permissions.blockReadsOutsideWorkingDirectories: true`), with real paths in Claude Code's form.

## Start (in `<USER_HOME>\local\shimmer-roles\B\`, in the background)

Environment: `CLAUDE_CODE_EFFORT_LEVEL=high`, `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0`, `BASH_MAX_TIMEOUT_MS=2700000`.

```
claude -p "Read ROLE_BDEV.md in this folder and carry it out completely. Your inputs are in the folder inputs_BDEV." --restricted --tools "Read,Edit,Write,Bash,WebFetch,WebSearch" --allowedTools "Read,Edit,Write,Bash,WebFetch,WebSearch" --add-dir "<USER_HOME>\local\shimmer-roles\_handoff" --add-dir "<USER_HOME>\local\shimmer-roles\_xfer\B_to_lead_dev" --append-system-prompt-file ROLE_BDEV.md --settings role_settings_BDEV.json --permission-mode acceptEdits --model opus --effort high --output-format json > session_result_BDEV.json
```

## After it ends

The lead reads only `_handoff\BDEV_DONE.json` (its time must be later than the start), `_handoff\BDEV_PREREG_SHA256.txt`, `_xfer\B_to_lead_dev\` and the exit code, and copies the development items to `external/<name>/dev/` (gitignored). On a non-zero exit, restart once after the limit resets with the same command plus `--continue` and the prompt "Continue ROLE_BDEV.md from where you stopped." (IV.10a item 8).
