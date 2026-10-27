# Changelog

One entry per product version, in plain English. The version number lives in `VERSION` until the Python package carries it. A version ending in `.devN` is a development snapshot; `rcN` is a release candidate.

## 0.1.0.dev2 (2026-10-27)

- **Model findings are marked, never hidden and never promoted.** The markdown deliverables, the run summary and the console mark a finding a model wrote as "Written by a model. Not promoted to an amendment. Not checked by Python." `review_data.json` lists them apart under `model_findings_not_promoted`, without a confidence or verdict field, and `GET /runs/{run_id}/findings` says who wrote each record (`written_by`). Only Python's records enter the comparison with an earlier version and its band list. The sentence naming who produced the findings is generated from what actually ran.
- **Amendments read as plain English and sit at their unit's own passage.** One sentence names the unit, the rule, both figures with their units and the relation (a sum names what it added); the rule is quoted; a model's sentence comes last, labelled. A unit Python cannot place sits at document level, cites no other passage, and the comment says so. Rows in the second output language (tr) were added for every new sentence.
- **Reports no longer overstate.** Relations only a model reported are listed apart, in the run summary and in the scorer; `audit_synthesis.md` counts audit-trail patterns, not findings; deliverable headings use colons instead of em dashes. The unused Turkish renderer `run_options.review_markdown` was removed.
- **Multi-round runs review each round in Python and reuse unchanged units.** A later round recomputes only the units whose text, rules, field labels or units of measure changed, records the reuse in `audit/round_reuse.json` and posts the round findings on the run bus. Nothing reads them yet, so no model call is saved. A term renamed with a moved value, or a figure with no unit renamed, is refused as a possible rename, not reported as withdrawn, until a measured rule decides it.
- **The frozen final models accept a declared multi-round Review** (the flag and its case manifest together); Draft and a half-declared request stay refused. The cloud controller admits a multi-round bundle only when it is declared, sealed with a live case manifest and run under `reference_serial`.
- **Every ordinary final launch is a budgeted loop launch.** A new budget guard (`tools/loop_budget_guard.py`) reads the loop ledger and refuses a launch the budget cannot carry or while another loop instance runs; the instance is named `shimmer-loop-...`; launch and termination lines go to the ledger; instance type, rate cap and caps are sealed from the live price. The general cloud path refuses loop names and ledgers, and no budget cap is a code default anywhere.
- **The controller can run detached, run sealed tests and run batches.** A sealed run prints counts only and writes nothing in the repository except ledger lines; a batch runs B3 and B1 item by item in one session; every run gets a `RUN_REPORT.md` with the Annex A 11.12 fields. The asset-copy declaration must name the bundle's own archive. The sealer refuses an unratified `SHIMMER_INST_FINDER=off`.
- **Every bundle sealed before this version must be sealed again**: six controller files it is bound to changed, so it refuses with "Controller source changed".
- Gate checks 278 and 279 added and check 185 replaced; a mocked end-to-end proof of a multi-round launch added (`tools/multi_round_launch_checks.py`).

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
