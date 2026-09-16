"""Render quantitative Markdown reports from local deterministic evidence."""
from runtime import *


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows])


def run():
    audit=read(HERE/'run1_audit.json');statistics=read(HERE/'statistics.json');tokens=read(HERE/'token_analysis.json')
    dry=read(HERE/'dry_run_evidence.json');splits=read(HERE/'splits.json')
    configs={role:read(HERE/role/'experiment.json') for role in ('producer','auditor')}
    corpus=read(HERE/'dataset.json')
    overview=[]
    for role in ('producer','auditor'):
        s=statistics[role];overview.append([role,s['rows'],s['substantive'],s['document_families'],s['template_families'],240,60])
    token_rows=[]
    for role in ('producer','auditor'):
        before=audit['roles'][role]['train']['supervised_component_percent'];after=tokens[role]['canonical_train_supervised_percent']
        for k in sorted(set(before)|set(after)):token_rows.append([role,k,f'{before.get(k,0):.2f}%',f'{after.get(k,0):.2f}%'])
    failures=[]
    for r in audit['producer_rows']:
        if r['accepted']:continue
        counts=Counter(e['category'] for e in r['errors'])
        failures.append([r['example_id'],'; '.join(f'{k}={v}' for k,v in counts.items()) or 'No gap error',
            f"TP/FP/FN {r['uncertainty']['tp']}/{r['uncertainty']['fp']}/{r['uncertainty']['fn']}"])
    folds=[]
    for f in splits['folds']:
        st=f['statistics'];folds.append([f['fold'],', '.join(f['validation_groups']),240,60,240,60,'80/20','12 each'])
    text=f'''# Second tuning data and failure audit

`{dry['verdict']}`

Local design release based on repository HEAD `2ef0ae091c448e21fc23d2e5280fcad15009e449` after `e65324c`. No run-1 evidence was rewritten. Readiness means a reviewed synthetic dataset, frozen validation/configuration and passing no-model infrastructure; it is not model acceptance or authorization to train.

## Corpus and sample size

{table(['Role','Raw rows','Substantive plans','Source document families','Conservative structural families','Canonical TRAIN','Canonical DEV'],overview)}

The substantive total is **560**, versus 134 role-specific run-1 rows: **4.18x**. Producer contributes 260/64 = **4.06x**; Auditor contributes 300/70 = **4.29x**. Forty Producer calibration rows (20 examined-empty, 20 out-of-ontology quantitative-value refusals) receive **zero** substantive expansion credit. Raw combined count is 600, not the denominator for the 4x claim.

There are 600 fresh source-document/derivation IDs, 300 per role. These are authored compositional document families, **not 600 independently collected natural documents**. There are only **five conservative structural leakage groups**. Twenty rendering layouts are nested inside these five families; cosmetic wrappers do not count as independent semantic expansion. Domains, names, units, numbers and field order are excluded from the substantive signature. Producer has 260 distinct semantic atom sets even after removing ownership and claim counts. Auditor has 300 distinct comparison plans built from twelve proposition structures, decision-bearing mutations and differing gap/uncertainty configurations. Reused primitive clauses are disclosed; CV tests structural-family generalization, not unseen ontology primitives.

Both roles have 30 rows in each of ten domains: negotiation, contracts, regulation, clinical-style synthetic records, device records, procurement, catalogue, synthetic nonsense, astronomy and ecology. Domains are mixed strata, not held-out domains. New astronomy/ecology material is independently authored; run-1's domain restrictions and historical interpretation remain unchanged. Domain knowledge is unnecessary for the labels.

Producer: **260 gap-bearing rows / 547 gap atoms**; 23 one-gap, 187 two-gap and 50 three-gap rows; **173 uncertainty-bearing rows / 173 uncertainty atoms**; **130 multi-claim rows**, **108 multi-span rows**, 20 refusals and 20 empty rows. The corpus covers all 16 supported gap attributes, including role-specific dates, entry order/content, recording/submission/event nonoccurrence, referents, absence versus unknown and explicit questions. Quantitative values outside the finite ontology trigger refusal instead of fabricated date/presence atoms. Twenty-two substantive rows preserve conflicting numeric claims; conflict is not converted into epistemic uncertainty. All 300 packets contain a context-only claim/reference trap, so the reported 300 hard-negative exposures are boundary traps, not 300 independently invented adversarial mechanisms.

Auditor: **60 MATCH / 60 DIVERGENCE / 60 OMISSION / 60 ADDITION / 60 INSUFFICIENT_EVIDENCE**, with 48/12 of each class in every TRAIN/validation split. Source structures include unequal faithful numbers, identical numbers with different labels, attributed conflicts, event versus recording date, submitted versus recorded, nonoccurrence, conditional rules, scope, units and cross-entry referents. Changes exercise core claims, evidence attribution, uncertainty, qualifiers and simultaneous omissions. Preserving a qualified or conflicting source can still be MATCH; such source difficulty is not a reason to refuse. Supplied references vary from zero to three owned references, with context-only distractors throughout. All 300 comparisons have explicit hard-negative boundaries. Five synthetic insufficiency forms are useful coverage, not broad natural ambiguity coverage.

## Run-1 Producer: every step-16 failure

Step 16 remains **31/32 contract-valid and 10/32 accepted**. Claims/evidence F1 remain 0.9917; typed uncertainty F1 remains 0.8519; typed-gap F1 remains 0.3913. The strict parser failure is extra data after the JSON value on `v2-chronological_events-catalogue-primary`. It is not repaired or promoted to a selected checkpoint.

Exclusive gap diagnosis on parseable outputs: **12 omissions, 8 wrong referents, 4 wrong attributes, 3 gaps placed in the uncertainty field, 1 wrong type/state, 6 raw-question rendering failures, 0 extra gaps**. One whole-output contract failure makes its three expected gaps unobservable. These account for all 37 historical gap false negatives: 34 diagnosed semantic/rendering failures plus three from the invalid output. The nineteen gap false positives are eight referent substitutions, four attribute substitutions, one type/state substitution and six raw strings. Raw questions are matched to finite-policy meanings only to classify rendering failures; historical strict scores remain unchanged. Multiple failures can occur within one row.

TRAIN contained only five distinct canonical gap atoms. DEV contained seven, including **three absent from TRAIN**: amendment-referent effective time (8 instances), first-entry content (8), and next-entry order (8). Those **24/55 DEV gold gap instances** all missed exact canonical matching. This directly supports a coverage/generalization failure; it does not prove a learning-rate or rank cause. Existing TRAIN gaps occupied 40.17% of JSON target tokens, so lack of aggregate gap-token mass is not the explanation. More varied targets, referents and compositions are the V2 intervention.

The original 32/32 split devoted **50%** of the tiny corpus to validation and exposed only 32 examples to gradients. It was validation-heavy relative to the requested grouped 80/20 design; the missing semantic atoms show why row totals alone were misleading. CV has not yet established whether the failure was split-specific.

{table(['DEV failure ID','Gap/contract taxonomy','Uncertainty counts'],failures)}

The remaining ten rows were accepted. The machine-readable audit preserves all 32 rows, claim/evidence/uncertainty counts, exact expected/predicted gap pairs and hashes of every read run-1 input. Besides the invalid output's claim/evidence loss, claims and evidence are preserved; uncertainty errors include spurious recording-time uncertainty and gaps misplaced into uncertainty.

## Run-1 Auditor: refusal collapse and objective evidence

TRAIN classes were **11 MATCH, 9 DIVERGENCE, 9 OMISSION, 9 ADDITION, 8 refusal**. DEV classes were **1 MATCH, 5 DIVERGENCE, 5 OMISSION, 5 ADDITION, 8 refusal**. TRAIN class dominance therefore does **not** explain all-refusal behavior.

At step 12: **23 refusals, one invalid UNCERTAIN finding**, 23/24 valid contracts, 15 over-refusals, 8 accepted outcomes. At step 24: **24 refusals**, 24/24 valid contracts, 16 over-refusals, 8 accepted outcomes. Step-24 refusal precision is **8/24 = 33.33%**, recall **8/8 = 100%**, over-refusal is **16/16 = 100% among cases that should not refuse** (66.67% of all DEV rows), and substantive non-refusal coverage is **0%**. Evidence F1 is zero. The frozen run-1 structural selection admitted step 24; that historical decision remains unchanged.

Refusal targets were exactly **11 JSON tokens** (12 with native termination). Substantive class mean JSON lengths were MATCH 79.09, DIVERGENCE 81.44, OMISSION 70.89, ADDITION 77.56. The objective averages loss per example, not globally over all target tokens, so the short fixed refusal receives the same example weight as a long substantive judgment. Run-1 relation-value tokens were just 3.40% of the JSON target stream. All eight TRAIN refusal inputs had zero required refs, whereas every substantive TRAIN input had one or two: a perfect metadata shortcut existed. The prompt also conflated incomplete transport with semantic omission. Short repetitive targets, structured-token loss, a metadata shortcut and permissive selection are **plausible supports**, not causally isolated explanations of the learned collapse. No counterfactual training was run.

V2 removes the universal empty-required-refs shortcut, distinguishes complete-delivery omissions from interrupted transport in the prospective prompt, balances classes and adds hard anti-collapse gates. Existing prompts/history are not edited.

## Grouped split and cross-validation

The deterministic allocator uses seed **29**, with equal-size conservative structural groups ordered by a SHA-256 seed/group tie-break. Each group contains four rendering layouts, 60 Producer rows, 60 Auditor rows and all domains/classes. This already satisfies the multi-label representation constraints; ordinary random-row stratification is not used. Source document, conservative template family, derivation group, paraphrase family, renamed family and structural leakage group are bound before splitting. No actual paraphrase or renamed sibling is given a new independent-family credit.

{table(['Fold','Held-out group','P TRAIN','P DEV','A TRAIN','A DEV','Groups/rows','Auditor DEV classes'],folds)}

Canonical membership is **fold 0**, frozen now, before any CV outcome. Every eligible row is in validation exactly once. Training uses four of five structural groups and validation one: exactly 80/20 at group and row levels. Role separation is enforced in every optimizer schedule. Domain is intentionally not a leakage grouping variable; otherwise a domain-balanced structural design would be connected into one component. Domains are not claimed held out.

## Leakage and preservation

All deterministic checks pass: exact input/source duplicates across splits; family/template crossings; known and unknown ancestry; paraphrase/renamed crossings; normalized substantive-signature crossings; duplicate membership; complete CV validation coverage; legacy/protected/regression identifier and family exclusions; available legacy review packet fingerprints. Fourteen injected bad cases are rejected. The first empty-form duplicate findings were fixed before freezing; final findings are zero.

Protected exclusion uses existing **metadata and packet fingerprints only**, plus new-authoring provenance. It does not perform a semantic-similarity scan of protected text. The original 114 targets are never opened. Existing R06/protected control hashes verify unchanged, and the protected one-shot receipt remains absent/unconsumed. No run-1 raw output, checkpoint, selected Auditor adapter, Producer-selection failure or historical metric was changed. Protected BASE-versus-tuned evaluation remains a separately governed future action; V2 has no protected evaluator.

## Machine review and token composition

Fresh input-only machine-agent contexts reviewed all 300 packets per role, with exact packet/review hashes. Producer review independently specified atom mappings but shares frozen ontology/structural parsing. Auditor review compared source/extraction text independently of authored labels. Final per-row labels agree, with zero remaining identified content-label blockers. Revision records preserve issues about attribution, ambiguous substitutions, contradictory annex scopes and refusal shortcuts and their resolution. Author-written target rationales are mechanically checked and grounded in the visible deltas; they are not falsely described as blind rationale adjudication. **Human reviews: 0.** Shared filesystem access is disclosed; there is no OS-isolation claim.

The table partitions **all supervised assistant tokens including native termination**, using the pinned local tokenizer's offsets. Tokens crossing component boundaries are assigned by midpoint. Keys/punctuation, span, confidence and severity are structural; the full escaped JSON inside typed gap/uncertainty strings belongs to that component. This measures supervision mass, not independent semantic information bits. JSON-only percentages and all individual lengths are retained separately.

{table(['Role','Component','Run-1 TRAIN','V2 canonical TRAIN'],token_rows)}

## Prospective selection and one frozen configuration per role

Both roles keep **100% contract validity** and zero limits on invented evidence, invented rules, confident wrong MATCH/DIVERGENCE, truncation, Producer source copying and governance violations. Producer additionally requires typed-gap F1 >=0.80, semantic completeness >=0.75, accepted outcomes >=0.75, claim/evidence F1 >=0.95, typed-uncertainty F1 >=0.80, refusal precision >=0.90, refusal recall >=0.80, over-refusal <=0.05. Auditor requires refusal precision >=0.90, recall >=0.80, over-refusal <=0.05, substantive non-refusal coverage >=0.90, every class recall >=0.60, accepted outcomes >=0.70, macro relation F1 >=0.75 and evidence F1 >=0.85. Undefined/nonfinite metrics fail closed. These are prospective engineering requirements, not statistically calibrated thresholds; the small per-fold refusal populations make them discrete and strict.

Each role retains **rank 8, alpha 16, dropout 0.05, the same seven attention/MLP projections, AdamW lr 1e-4, microbatch 1, accumulation 4, seed 7, one warmup update, linear decay, BF16 and two data passes**. There is no evidence isolating rank or LR as the cause, so they are retained with an explicit rationale. No component reweighting is introduced: gaps were already prominent, and class/token imbalance alone does not prove causation. The frozen objective remains per-example mean target-only cross entropy, including native termination. Data, prompt clarification and selection gates are the targeted changes.

Two passes of 240 TRAIN examples give **120 updates**, with DEV at **60 and 120**, identically in every fold and canonical run. Producer sequence ceiling / generation cap: **{configs['producer']['max_seq_length']} / {configs['producer']['generation']['max_new_tokens']}**. Auditor: **{configs['auditor']['max_seq_length']} / {configs['auditor']['generation']['max_new_tokens']}**. Ceilings derive from tokenizer measurement with no truncation; generation caps include a 32-token margin and round to 32. Model/revision/quantization, adapter module counts and base-weight hashes remain those verified for run 1. No sweep or per-fold retuning exists.

## Future metrics, workload and limits

The implemented collector reports all five folds at **both fixed checkpoints**, then mean, median, minimum, maximum and population standard deviation. Producer reports contract, claim/gap/uncertainty/evidence F1, completeness, refusal and accepted outcomes; Auditor reports contract, relation accuracy, macro F1, per-class recall, refusal precision/recall, over-refusal, evidence F1 and accepted outcomes. Both report every catastrophic count and document-family accepted-rate variability. These are separate metrics, never one configuration-selection score. Canonical checkpoint selection uses only canonical DEV after all gates. Alternative generated Auditor rationales remain unassessed unless separately adjudicated; exact authored-reason fixtures do not prove model semantic performance.

Five-fold CV plans **10 role runs, 1,200 optimizer updates, 4,800 example visits and 1,200 validation generations**. Canonical plans **2 role runs, 240 updates, 960 visits and 240 validation generations**. Combined upper bounds are 720 Producer generations x 288 = **207,360 output tokens** and 720 Auditor generations x 192 = **138,240 output tokens**. No runtime/cost guarantee is inferred from run-1's unusually short collapsed Auditor outputs. All these are future workloads, not performed work.

No-model dry-run encoded all 600 examples, verified all twelve role/split schedules, checked prompt masking/EOS/ceilings, tested perfect-target and all-refusal metric fixtures, rejected malformed/nonfinite metrics and leakage/access faults, and confirmed run-1 evidence hashes. Fixture scores are labeled tests, not V2 model results. The future local executor is implemented with separate release/role/split authorization, pinned dependencies/weights, no network, fresh output directories and no protected path. It was parsed but **not model-tested or executed**.

Confirmed: no protected target access, no cloud, no paid API, no model generation, no training, no weight changes, no full pipeline, no multi-round and no push.

Artifacts: `tuning/second_domain_agnostic_v2/` contains the dataset, statistics, row-level audit, tokenizer measurements, split manifests, machine reviews, selection rules, role configurations, execution plans, dry-run evidence and final freeze manifest.
'''
    (ROOT/'docs/fix/SECOND_TUNING_DATA_AND_FAILURE_AUDIT.md').write_text(text,encoding='utf8')
    if dry['verdict']=='SECOND_TUNING_EXPERIMENT_DESIGN_READY':
        implementation='''# Second tuning experiment implementation

`SECOND_TUNING_EXPERIMENT_DESIGN_READY`

This is a local design/dry-run release. Training remains unauthorized and has not run. See [the quantitative audit](SECOND_TUNING_DATA_AND_FAILURE_AUDIT.md) for exact counts, failure taxonomy, token proportions and limitations.

## Files and responsibilities

- `author.py`: new semantic plans and explicit provenance; no legacy/protected data input. The 40 Producer calibration rows do not count toward substantive expansion.
- `audit_run1.py`: immutable TRAIN/DEV-only failure and token audit, with read-input hashes.
- `release.py`: group-first authoring, deterministic canonical/five-fold membership, tokenizer measurement, exact role configuration and release freeze.
- `runtime.py`: stable ontology/contract reuse, explicit multi-span ownership, target-only encoding, metrics, fail-closed leakage and semantic gates.
- `runner.py`: verified canonical/fold schedules. Its only CLI mode is `--dry-run`.
- `train.py`: future local executor requiring separate operator authorization bound to one role, one split and the exact release hash. No provider client, download, protected evaluator, resume or automatic retry. Never called during this task.
- `collect_cv.py`: verify future run bindings and raw validation evidence, recompute scores and aggregate both fixed checkpoints over all five folds. No result exists yet.
- `dry_run.py`: irreversible process audit hook blocks benchmark target reads, model weights, subprocesses and networking; metadata-only contamination checks, full tokenizer checks, metric fixtures and fault injection.
- `report.py`: quantitative documentation from saved evidence.

Frozen inputs are `dataset.json`, `splits.json`, `selection_rules.json`, role `experiment.json` files and `review_adjudication.json`. `freeze.json` binds the release and frozen reused code/config dependencies. Runtime evidence and fixture evidence are distinct. Earlier review rounds are retained as review provenance, not alternative training corpora.

## Reproduce no-model verification

From repository root, using the local interpreter with Transformers 4.51.3/tokenizers 0.21.1:

```text
python -B tuning/second_domain_agnostic_v2/dry_run.py
python -B tuning/second_domain_agnostic_v2/runner.py --role producer --split canonical --dry-run
python -B tuning/second_domain_agnostic_v2/runner.py --role auditor --split 0 --dry-run
```

Splits `0` through `4` each use 240 TRAIN/60 validation rows per role; `canonical` is the already-frozen fold-0 membership. Every schedule contains two deterministic passes, 120 optimizer updates and validation at 60/120. All role configurations are identical across folds. Each role/fold has a separate future output directory; validation IDs cannot enter its optimizer schedule. CV is upstream robustness assessment and cannot change the canonical split or hyperparameters.

The optional rebuild commands (`audit_run1.py`, `release.py`, `report.py`, `release.py --freeze`) create a new local design artifact and are not training commands. Do not rebuild a release after model results to silently alter selection rules. Any substantive change requires a new reviewed release.

## Execution boundary and validation

No authorization file was created, and `train.py` was not run. Future execution requires the pinned Linux/Python/CUDA/dependency environment, local pinned model assets, an exact role/split/release permit, and a fresh run directory. Weight hashes are checked only after that future authorization. The current dry-run reads tokenizers/configuration, never weights. Executable model integration remains untested; design readiness does not establish runtime feasibility or semantic success.

All 600 targets pass the frozen role contracts; all 300 Producer labels pass the canonical renderer. Every fold passes grouped isolation, exact-once validation and class/domain checks. Fourteen deliberate leakage/access faults are rejected. Perfect-target, all-refusal, malformed-output and nonfinite-metric fixtures exercise the semantic gates; none is presented as a model result. Final input-only reviews cover all 600 packets with zero unresolved content-label disagreements, and human review remains zero.

Five structural superfamilies are the effective held-out groups, despite 600 document IDs and 20 rendering layouts. This synthetic compositional corpus has limited language diversity. Protected contamination checking uses existing metadata/fingerprints and provenance; it does not open protected text for similarity comparisons. The existing protected one-shot receipt is unconsumed and R06 controls are unchanged.

Future CV reports both fixed checkpoints, full per-fold metrics and separate aggregate distributions. No single composite score hides class collapse. Canonical candidate selection uses only canonical DEV and the prospective gates. No automatic protected evaluation follows selection.
'''
        (ROOT/'docs/fix/SECOND_TUNING_EXPERIMENT_IMPLEMENTATION.md').write_text(implementation,encoding='utf8')
    print(dry['verdict'])


if __name__=='__main__':run()
