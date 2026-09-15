# Semantic benchmark v2 hardening

**Dataset/evaluation version:** `semantic-benchmark-v2`.
**Unchanged production contract:** `semantic-task-v1`.

This release references all 448 immutable v1 examples and adds 288 public examples.
It does not re-freeze or modify the old dataset, production adapters, or old results.
Run the existing Python 3.12 environment locally:

```powershell
& 'C:\Users\secki\anaconda3\python.exe' benchmark/task_semantics_v2/hardening_gate.py
& 'C:\Users\secki\anaconda3\python.exe' benchmark/task_semantics_v2/training_view_reader.py --split train
```

Neither command generates text, trains, calls a provider, or reads a sealed vault.
The gate writes fresh evidence under `output/domain_agnostic_hardening`.
`build_expansion.py` reproduces the release only when its existing freeze matches;
changed frozen files require review and a new benchmark version. Baseline hashes
are verified before construction, so rebuilding cannot bless a changed v1.

## Independent review

Give reviewers **only the `review_packets/` directory**, or individual JSON/Markdown
packets. Do not provide `extension.json`, v1 labels, `metadata.json`, negative labels,
training views, split manifests, or `review_admin_mapping.json` during first review.
Packets carry exact input hashes and a blank response template. They expose source,
owned/context spans, refs, rules, and auditor extraction; no authored answer or split.

The administrator maps packet IDs back with `review_admin_mapping.json`. Import a
completed response using `adjudication_state(record, reviews, resolution)`; it checks
identity, human/independence attestation, date, version and exact input binding.
Human identity/independence is an attestation requiring operator verification, not
something software can prove. Machine feedback and author self-review cannot satisfy
independent-human status. A second reviewer receives the same blank packet, not the
first response. Disagreement remains unresolved until an explicit non-author human
resolution supplies final target, rationale, identity, date and input hash.

The command `submit_review.py RESPONSE.json --journal ADMIN_DIRECTORY` validates
and exclusively appends a response. Use `--resolution RESOLUTION.json` when the
second response requires adjudication. The journal cannot be placed in the reviewer
packet export. Duplicate reviewer submissions are rejected. Final reviewed targets
are stored separately; frozen authored labels are never overwritten.
To resolve a disagreement after both responses arrived, use
`submit_review.py --resolve-packet PACKET_ID --resolution RESOLUTION.json --journal ADMIN_DIRECTORY`.

All **736** examples remain pending; no reviewer submissions occurred in this task.
Synthetic tests of human-response interfaces do not count as actual human review.
Semantic and formatting judgments are separate fields. A valid semantic annotation
cannot silently promote malformed wire output.

Reason components are listed in `reason_rubric.json`. Alternate reason wording can
pass through `assess_reason` only with independent, input- and raw-output-bound human
review. Text similarity never establishes truth. Canonical text remains an authored
regression target, not the only possible valid paraphrase.

## Training selection and holdouts

`training_view/manifest.json` authorizes **368** public train/dev rows (184 each).
The loader verifies frozen hashes, exact names, IDs and domains and rejects path
escapes, symlinks, held-out files and injected rows. A future job should receive this
selection directory alone, never repository-wide access or an external sealed vault.
The selection is not authorization to train or evidence of reviewed labels.

Astronomy/ecology appear only in test/adversarial: **72 rows**, zero tuning access.
The 368 test/adversarial examples also have template families absent from train.
Domain holdout, document holdout and template holdout are distinct reported axes.
The new templates are paragraph, bullets, form fields, chronological events, Q/A,
memo sections, compact table, multi-row table, mixed prose/table, nested provisions,
transaction register and machine records. Domain variants share a template's one
split; they are not counted as independent structural samples.

## Sealed final infrastructure

`sealed_final_manifest.json` is **pending, with zero populated examples**. Public
adversarial examples are not relabeled blind. A real independent contributor must
provide reviewed synthetic material separately and an operator-controlled vault
**outside this repository**, protected with a separate account/ACL. That OS boundary
has not been provisioned here. Application checks cannot prevent an unrestricted
same-account Python process from reading arbitrary files.

`seal_contribution` requires independent-human attestation, authorization, distinct
reviewers and `independent_synthetic_sealed` provenance; it refuses this authored
public seed. It exclusively creates labels and a hash manifest. Development/training
APIs do not read this vault. `read_sealed`/`final_evaluate` require explicit
`final_evaluation` mode and an operator permit binding labels, saved candidate
outputs and acceptance registration. No inference runs in final evaluation.

Results contain aggregate counts only and are exclusive-created with a hash chain
under a write lock. Prior run IDs cannot be overwritten; edited chain links are
detected. Retention/ACL protection and external log anchoring remain the operator's
responsibility; a same-account filesystem administrator can still remove files.
Do not use final results for prompt/checkpoint selection. Each authorized candidate
must be registered before final access. Public-artifact audits can compare protected
answer hashes supplied by the contributor without opening the vault.

## Acceptance and statistics

`acceptance_specification.json` freezes zero catastrophic limits for invented
evidence/rules, confident semantic reversals, truncation, producer source copying
and governance violations, derived from existing invariants. All unsupported numeric
quality, coverage, family/domain and variability thresholds explicitly require
operator registration. No tuned model has been observed or used to fit thresholds.
The acceptance function fails closed; a prospectively registered release must bind
and implement the operator's quantitative rules before model acceptance.

`family_statistics` reports all existing metrics per document family, template and
domain, plus equal-weight macros and ranges. Its deterministic group bootstrap is
exploratory, with intervals withheld below eight groups. Authored perfect targets
do not establish model quality; rows share higher-level template/derivation structure.
The descriptive v1 row intervals remain preserved but must not be used as independent
sample confidence claims.

Current verdict: **DOMAIN_AGNOSTIC_TRAINING_EXPERIMENT_NOT_READY**. Remaining work:
independent human review, prospective operator threshold registration and implementation,
and genuinely independent sealed material with an external access boundary.
No cloud, paid API, training, LoRA/SFT, model change, full pipeline, multi-round or push.
