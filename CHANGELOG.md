# Changelog

One entry per product version, in plain English. The version number lives in `VERSION` until the Python package carries it. A version ending in `.devN` is a development snapshot; `rcN` is a release candidate.

## 0.1.0.dev1 (2026-10-27)

- **Every model reply is saved.** Each model call writes one record into the run's `audit/model_replies/` folder (the reply, the exact payload, the model and decoding settings), with what became of the reply in `outcomes.jsonl`. With redaction on, only hashes and lengths are kept. The records are never committed.
- **INST_FINDER can be switched off, but only after the operator ratifies it.** `SHIMMER_INST_FINDER=off` takes effect only under an approved constitution amendment; until then a run with it refuses to start. The amendment is drafted, not ratified.
- **The cloud controller no longer contains a credential path.** It finds the credential file through the project's existing lookup, at the moment of use. Bundles sealed before this change must be sealed again.
- **The secret guard refuses seal manifests and saved replies** staged for a commit, by path or inside a staged archive (`scripts/guard_secrets.py --staged`).
- The external collaborator's project name was removed from the two files that held it (it remains in git history until the planned history rewrite).
- New records: a log of proposed test changes, a personal-path inventory for the history rewrite, and a multi-round readiness report.
- Gate checks 275 to 277 added; a pre-existing failure of check 112 fixed.

## 0.1.0.dev0 (2026-10-27)

- Start of versioning. The code is the same as commit `f31eff4` on `main`. Later entries list what each version changes.
