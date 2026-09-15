# Domain-agnostic semantic task seed v1

This is a public, authored benchmark/data seed for the existing compact Shimmer
PROCESSOR and VERIFIER adapters. It contains no training job or model loader.
Labels remain outside `scripts/`, `tools/`, operational input and durable state.
The historical public capacity/date A/B fixture is regression-only; no private
corpus or answer key was used.

## Run offline

From the repository root with the existing Python 3.12 environment and its
`jsonschema` dependency:

```powershell
& 'C:\Users\secki\anaconda3\python.exe' benchmark/task_semantics/run_gate.py
```

The gate blocks network/model imports, verifies production contract hashes and
the frozen dataset, validates every record and split, runs deterministic tests,
scores gold/negative candidates separately, and reproduces the four preserved
model failures. Results default to `output/domain_agnostic_tuning/`.

`build_seed.py` reproduces the public seed from `split_plan.json`'s construction
logic. Split allocation is written before descendants. Changed frozen code or
data requires review and a version bump; rebuilding cannot silently bless a
changed v1. `frozen_dataset.json` hashes the code/schema/targets/splits/candidates
and the config contract manifest. Production files are referenced and hashed,
not copied into a competing validator.

## Score saved outputs

`evaluate_outputs.py INPUT.json --split dev --out OUTPUT.json` accepts saved
responses with `example_id`, `raw`, `truncated`, `completed`, `provenance`, and
`source_run_id`. Provenance is `authored_diagnostic` or `generated_model`; the
latter also requires `model_id` and `model_revision`. It never generates text.
Missing examples are reported, never counted as passing. Authored and generated
metrics stay separate. The public seed cannot approve a checkpoint.

`core.render_task(record)` uses the frozen production prompt builders and only
input fields. Producer context remains context-only. Auditor ORIGINAL is the
owned source; EXTRACTION is the candidate extraction to compare, not its gold
judgment. Supplied neighboring refs are explicit distractors in the record.
Use `core.select_for_tuning(records)` for train/dev data; test, adversarial and
regression requests are rejected. This is an API discipline, not file encryption.

## Meaning of scores

- Transport completion, strict contract validity, semantic correctness and
  accepted outcome are separate. `semantic_accepted` also excludes refusal.
- Refusal is valid outcome syntax, while production acceptance remains false.
- Claim/question/uncertainty scores use exact canonical atoms (alias plus value).
  This conservative seed rubric does not prove paraphrase equivalence.
- Evidence IDs are exact; missing, extra supplied, invented and unrouted refs
  remain distinct. No citation repair or prefix recovery occurs.
- Reason correctness is true only for the authored canonical rationale or a
  hash-bound independent review. Other wording is unassessed, not fluent truth.
  Single-review historical diagnostic observations remain separate.
- Confidence in a fidelity judgment is distinct from uncertainty expressed in
  the source. A faithful preservation of an uncertain statement can be confidently
  MATCH. Producer targets preserve the original uncertainty text.
- Boolean rates, micro evidence/atom counts, per-class relations, refusals,
  catastrophic errors and per-family results are retained. Wilson intervals are
  descriptive only; related authored rows are not independent model trials.

## Limitations and access

448 single-authored examples: 96 producer, 352 auditor, eight domains, 32 document
families, **only four template/renaming families**. Every split has 112 examples.
The 112 adversarial rows are public framework examples, not an independently
blind/sealed final test. All rows are English. Seed-only perfect self-consistency
does not establish model performance, statistical adequacy, or multilingual skill.

Independent adjudication is supported by `core.adjudicate`; disagreement requires
an explicit final resolution. Seed records honestly retain `authored_single`.
The unregistered acceptance template deliberately has no convenient thresholds.
Model acceptance requires preregistration, a matching dataset/run registration,
verified independent labels, blind evaluation and governance; public seed results
cannot satisfy that path. None of this authorizes training.

See [the maintained report](../../docs/fix/DOMAIN_AGNOSTIC_TUNING_DATASET.md).
