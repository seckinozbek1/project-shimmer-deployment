"""Render completed Auditor canonical result and handoff from verified evidence."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/auditor_canonical_tuning_run'
def main():
    x=json.loads((BASE/'RECOMPUTED_RESULTS.json').read_text())
    assert json.loads((BASE/'POST_RUN_VERIFICATION.json').read_text())['passed']
    assert x['verdict']=='AUDITOR_TUNING_FAIL'
    t=x['training'];c=x['checkpoints'];cloud=x['cloud'];term=cloud['termination']
    lines=[]
    def p(v=''):lines.append(v)
    def table(headers,rows):
        p('| '+' | '.join(headers)+' |');p('| '+' | '.join('---' for _ in headers)+' |')
        for row in rows:p('| '+' | '.join(str(v) for v in row)+' |')
        p()
    p('# Auditor canonical tuning results');p()
    p('`AUDITOR_TUNING_FAIL`');p()
    p('The one authorized fresh Auditor run completed all 120 optimizer updates and both fresh 60-row canonical DEV evaluations validly. Neither checkpoint passes all frozen gates. No Auditor adapter is selected. No automatic redesign or retraining follows; the permitted follow-up is local failure diagnosis only. The Producer branch remains closed and checkpoint168 was preserved without execution. No governed Producer+Auditor system test ran.');p()
    p('## Cloud and cleanup');p()
    p(f"Tested executor commit: `{x['source_commit']}`. Provider: Lambda Cloud; region: us-east-1; one A10 24 GB, x86-64; queried price: **$1.29/hour**. Launch-to-confirmed-termination upper bound: **{term['billable_duration_upper_bound_seconds']:.6f} seconds (46m 34s)**. Estimated upper-bound compute cost: **${term['estimated_cost_upper_bound_usd']:.9f}**, not a provider invoice.");p()
    p(f"Termination confirmed at `{term['utc']}`. Subsequent independent inventory was empty, the ephemeral SSH registration was absent, and local key material was removed. **Zero billable resources remain.** The evidence archive was downloaded and hash-verified before termination; all analysis below occurred afterward.");p()
    p('The $1.50 soft budget was not reached. At launch, soft/hard durations were 4186.047/8372.093 seconds, workload cutoff 7772.093 seconds, with 600 seconds reserved for collection and teardown. A detached operator watchdog had a hard-minus-60-second termination deadline. The conservative prelaunch estimate was 7308 seconds/$2.6187, assuming 900-second setup, ten-second updates, all 144 generations at the 192-token cap and six output tok/s, plus reserve. Six tok/s was a planning assumption, not an Auditor quality gate. Every measured durable-boundary remaining-work projection passed.');p()
    p('## Frozen release and scope');p()
    p(f"Source release: `second-domain-agnostic-v2`, freeze SHA-256 `{x['source_release_sha256']}`. Original mixed-role dataset SHA-256: `{x['dataset_sha256']}`. Auditor-only exact row export SHA-256: `{x['auditor_export_sha256']}`. The original dataset/config/gates were not changed; the export is byte-bound through per-row canonical hashes and the source release. Canonical split SHA-256: `dc7760fbeb77e672d9ee8709b04763a39a82bae945d5370bf9ffedbc538ddb98`.");p()
    p('Auditor rows: 300, all marked substantive by the frozen corpus; 60 per relation class. Canonical TRAIN/DEV: 240/60, balanced 48/12 per class. Maintained Auditor tokenization, target-only labels, contract/semantic metric fixtures, canonical-plan and grouped leakage checks passed. All 300 sequences fit the frozen 1056-token ceiling (maximum 1052); maximum target length was 153, within the 192 generation cap. The legacy whole-release dry-run entry point was not called because it also enumerates Producer/noncanonical folds and opens protected metadata; its maintained Auditor primitives were exercised in isolation. Protected artifacts were checked through existing metadata receipts only.');p()
    p('Pinned base: `unsloth/Phi-3.5-mini-instruct-bnb-4bit`, revision `5c20803aa197416f43fb455e55c85178775320cb`, weight SHA-256 `e6c61d932846517fc3d5bf09abb69b8c6f657b673ff8380999b15fb20cfcb64a`. Loaded architecture: **LlamaForCausalLM**, model_type **llama**. Config SHA-256: `efc10243cb105a2fbb4069d1686dcffe52cce4bcb5acf3ddf17dff415939aca2`. Model naming did not override the pinned runtime evidence.');p()
    p('Fresh seed-7 LoRA: rank8, alpha16, dropout0.05, bias none, CAUSAL_LM, q/k/v/o/gate/up/down projections, 14,942,208 trainable parameters; all initial LoRA-B tensors verified zero. No prior Auditor or Producer adapter was loaded. AdamW LR1e-4, betas0.9/0.999, epsilon1e-8, weight decay0, linear scheduler, one warmup update, clipping1, microbatch1/accumulation4, two complete passes remain unchanged. The objective is equal-weight per-example mean assistant-target-plus-native-termination cross entropy. BF16, eager attention, gradient checkpointing, NF4/double quantization and deterministic algorithms were retained; TF32 was off.');p()
    p('Generation remained greedy, batch1, use_cache=true, max_new_tokens=192, EOS [32000,32007], and the pinned tokenizer pad ID. The scoped evaluation/state/cache mechanisms were tested against the unchanged V2.1 AST/bytes and passed real-object preflight. No ambient trace/profile or historical traced reference was used. V2 had no Auditor control IDs: before launch, one first-in-DEV-order ID per relation class was fixed and duplicate optimized passes required exact prompt/input/output/decoded/semantic/stop identity. Full DEV generations were separate and fresh.');p()
    p('## Training and runtime verification');p()
    table(['Measure','Value'],[
        ('TRAIN / DEV','240 / 60'),('Updates / example exposures','120 / 480; each TRAIN example exactly twice; zero DEV gradients'),
        ('Training wall excluding DEV',f"{t['training_seconds']:.6f} s / {t['training_seconds']/60:.6f} min"),
        ('First / final update loss',f"{t['initial_loss']:.9f} / {t['final_loss']:.9f}"),
        ('Update time median / p95',f"{t['update_seconds']['median']:.6f} / {t['update_seconds']['p95']:.6f} s"),
        ('Peak allocated / reserved VRAM',f"{t['peak_vram_allocated_bytes']} / {t['peak_vram_reserved_bytes']} bytes ({t['peak_vram_allocated_bytes']/2**30:.6f} / {t['peak_vram_reserved_bytes']/2**30:.6f} GiB)"),
        ('Training GPU utilization mean / median / p95',f"{t['telemetry']['gpu_utilization_percent']['mean']:.6f}% / 100% / 100% ({t['telemetry']['samples']} samples)"),
        ('Overall GPU utilization mean / median',f"{t['overall_telemetry']['gpu_utilization_percent']['mean']:.6f}% / 20% ({t['overall_telemetry']['samples']} samples)"),
        ('Training CPU utilization mean',f"{t['telemetry']['cpu_percent']['mean']:.6f}% (100% is one logical CPU)"),
        ('Peak sampled RSS / host RAM used',f"{t['overall_telemetry']['rss_bytes']['max']} / {t['overall_telemetry']['host_ram_used_bytes']['max']} bytes")])
    p('Loss endpoints use different training examples and are descriptive, not held-out loss comparisons. Separate-process telemetry avoided the per-token generation path. Exact optimizer order/LR, checkpoint schedule, no update after120, fresh initialization, adapter/config identities and state/RNG restoration at both checkpoints passed local verification. Restoration covered weights, gradients, optimizer, scheduler, training flags/counters, adapter activation, nullable configs and checkpointing state; step61 followed the midpoint restoration check.');p()
    p('## Checkpoints');p()
    for s in ('60','120'):p(f"Checkpoint {s} adapter SHA-256: `{c[s]['identity']['files']['adapter_model.safetensors']}`.");p()
    p(f"Shared adapter-config SHA-256: `{c['60']['identity']['files']['adapter_config.json']}`. Initialization adapter SHA-256: `{t['identities']['0']['files']['adapter_model.safetensors']}`.");p()
    table(['Measure','Checkpoint 60','Checkpoint 120'],[
        ('Fresh complete DEV','60/60','60/60'),('Deterministic control pairs','5/5 identical','5/5 identical'),
        ('Control pass1 / pass2 tok/s',*[' / '.join(f'{v:.6f}' for v in c[s]['controls']['per_pass_tokens_per_second']) for s in ('60','120')]),
        ('DEV generation wall seconds',*[f"{c[s]['generation_seconds']:.6f}" for s in ('60','120')]),
        ('DEV aggregate output tok/s',*[f"{c[s]['tokens_per_second']:.6f}" for s in ('60','120')]),
        ('DEV output tokens',*[c[s]['output_tokens'] for s in ('60','120')]),('Every frozen gate passed','FAIL','FAIL')])
    p('Timing includes prefill and synchronized generation, excluding controls/cache probes from full DEV totals. Decode-only speed and TTFT were not measured. Both actual cache preflights passed; all 144 raw outputs were persisted before scoring and independently decoded/rescored afterward.');p()
    table(['Frozen metric','Required','Checkpoint 60','Checkpoint 120'],[(name,bound,*[f"{c[s]['metrics'][name]:.9f}" for s in ('60','120')]) for name,bound in [
        ('contract_validity','1.0'),('macro_relation_f1','>=0.75'),('accepted_semantic_outcomes','>=0.70'),('evidence_f1','>=0.85'),
        ('refusal_precision','>=0.90'),('refusal_recall','>=0.80'),('over_refusal_rate','<=0.05'),('substantive_non_refusal_coverage','>=0.90')]])
    p('Accepted outcomes: **19/60** at step60 and **28/60** at step120; the threshold is **42/60**. Evidence precision/recall/F1 are **1/1/1** at both checkpoints (104 correct evidence atoms, zero false/missing atoms). All contract outputs are valid, but validity and correct evidence references do not establish a correct relation or justification.');p()
    p('## Confusion and per-class metrics');p()
    p('Confusion matrices use expected classes as rows and predicted classes as columns. Every class has support12. No invalid/unknown predictions occurred.');p()
    classes=['MATCH','DIVERGENCE','OMISSION','ADDITION','INSUFFICIENT_EVIDENCE']
    for s in ('60','120'):
        p(f'### Checkpoint {s}');p()
        diag=c[s]['diagnostics'];table(['Expected / predicted']+classes,[(k,*[diag['confusion_matrix'][k][j] for j in classes]) for k in classes])
        table(['Class','Precision','Recall','F1','Support'],[(k,*[f"{diag['per_class'][k][v]:.9f}" for v in ('precision','recall','f1')],12) for k in classes])
        p('Macro precision / recall / F1: '+' / '.join(f"{diag['macro'][k]:.9f}" for k in ('precision','recall','f1'))+'.');p()
    p('Every class must have recall >=0.60. Step60 fails MATCH, DIVERGENCE and ADDITION; step120 fails MATCH, DIVERGENCE and OMISSION. Diagnostic precision is shown as zero when a class has no predictions (step60 ADDITION, step120 OMISSION); this reporting convention does not alter any frozen F1, recall or eligibility gate.');p()
    p('## Refusals and catastrophic failures');p()
    table(['Refusal diagnostic','Checkpoint 60','Checkpoint 120'],[(k,*[c[s]['diagnostics']['refusal'][k] for s in ('60','120')]) for k in ('expected','predicted','correct','false','missed','over_refusal_rate')])
    p('All five classes have zero false refusals at both checkpoints; no class is affected by false refusal. The historical refusal-collapse pattern did not recur in this canonical DEV run. Short correct refusal outputs are separated from substantive successes in efficiency reporting.');p()
    table(['Frozen catastrophic category','Checkpoint 60','Checkpoint 120'],[(k,*[c[s]['metrics']['catastrophic'][k] for s in ('60','120')]) for k in c['60']['metrics']['catastrophic']])
    p('The **5 / 4 confident wrong MATCH-or-DIVERGENCE findings** independently disqualify the respective checkpoints. Categories retain the frozen scorer definitions; they are not a broader safety assessment.');p()
    p('## Measured failure pattern');p()
    p('Step60 predicts OMISSION on 39/60 rows, including 28 incorrect OMISSION predictions, and predicts ADDITION on none. Step120 shifts to ADDITION on 37/60 rows, including 27 incorrect ADDITION predictions, and predicts OMISSION on none. Required refusals remain exact at both steps. Relation accuracy is 27/60 and 29/60, respectively. Of those relation-correct rows, 8 at step60 and 1 at step120 fail the frozen reasoning requirement, leaving 19 and 28 accepted outcomes.');p()
    p('These observations establish unstable substantive relation classification despite perfect contract/evidence/refusal results. They do not isolate a causal explanation or justify changing labels, prompts, rank, learning rate or gates. No new data, runtime refusal hack, redesign, rescue or retraining was performed. Any Auditor redesign is a separate local task.');p()
    p('## Output efficiency');p()
    table(['Output-token statistic','Checkpoint 60','Checkpoint 120'],[(k,*[f"{c[s]['diagnostics']['efficiency']['output_tokens'][k]:.6f}" for s in ('60','120')]) for k in ('min','median','mean','p90','p95','max')])
    p('Both checkpoints: EOS-before-cap100%; cap-hit0%; trailing prose0; second JSON0; code fences0; duplicate refs0; duplicate finding items0. Quantiles use linear interpolation at (n-1)q. Quality overrides token efficiency.');p()
    table(['Efficiency','Checkpoint 60','Checkpoint 120'],[
        ('Correct evidence atoms / all output tokens',*[f"{c[s]['diagnostics']['efficiency']['correct_evidence_atoms_per_output_token']:.9f}" for s in ('60','120')]),
        ('Accepted-output token cost mean / median',*[' / '.join(f"{c[s]['diagnostics']['efficiency']['accepted_output_token_cost'][k]:.6f}" for k in ('mean','median')) for s in ('60','120')]),
        ('All attempt tokens / accepted outcome',*[f"{c[s]['diagnostics']['efficiency']['all_attempt_tokens_per_accepted_outcome']:.6f}" for s in ('60','120')])])
    table(['Accepted group','Checkpoint','Count','Total tokens','Mean / median / p95'],[(name,s,c[s]['diagnostics']['efficiency']['accepted_groups'][name]['count'],c[s]['diagnostics']['efficiency']['accepted_groups'][name]['total_tokens'],
        ' / '.join(f"{c[s]['diagnostics']['efficiency']['accepted_groups'][name]['token_cost'][k]:.6f}" for k in ('mean','median','p95'))) for name in ('correct_refusals','substantive_successes') for s in ('60','120')])
    p('Evidence density uses all generated DEV tokens as denominator. Accepted-output cost conditions on correctness; all-attempt token cost also includes rejected outputs. Small accepted subgroups have descriptive tail quantiles only. Full distributions, per-row errors, confusion counts and gate failures are preserved in the JSON evidence.');p()
    p('## Selection, preservation and next action');p()
    p('Eligible checkpoints: none. Selected checkpoint: none. Selected adapter SHA-256: not applicable. Frozen quality eligibility rejects both checkpoints before applying macro-relation-F1, accepted-outcome, earlier-step and adapter-identity-hash tie-breaks. A failing adapter was not selected or promoted.');p()
    p('`PRODUCER_STATUS=PRESERVED_UNEXECUTED`  \n`PROTECTED_RECEIPT_STATUS=UNCONSUMED`');p()
    p('Historical V2 release hashes and Producer V3 result text hashes passed. Historical Producer archives/adapters were checked by size and the existing preservation metadata, without loading Producer tensors; no Producer inference or training occurred. Producer V3 FAIL remains unchanged and the branch remains closed. No protected target was opened or uploaded, no protected evaluator ran, and no receipt was consumed.');p()
    p('Exactly one cloud instance and one GPU were used; no second GPU, Producer execution/training, protected access, folds1-4 execution, paid inference API, full Shimmer pipeline, governed system test, multi-round run, or push. Zero billable resources remain.');p()
    p(f"Archive SHA-256: `{x['archive_sha256']}`; size 136,498,916 bytes. The archive and initial/midpoint/final adapter binaries remain preserved locally outside Git. Their hashes and all reviewable text evidence are committed. Copy those binaries separately when migrating; the full local verifier also needs pinned tokenizer assets.");p()
    p('Evidence: `auditor_canonical_tuning_run/RECOMPUTED_RESULTS.json`, `RECOMPUTED_PER_ROW.json`, `POST_RUN_VERIFICATION.json`, `EVIDENCE_MANIFEST.json`, cleanup/inventory receipts, and `downloaded/evidence/`. Frozen execution artifacts are in `tuning/auditor_canonical_execution/`; canonical source artifacts remain unchanged. Run-specific HANDOFF.md records the stop decision without editing historical handoffs.');p()
    p('Verification: `python -B tools/analyze_auditor_canonical.py` recomputed 144 outputs (120 DEV, 20 duplicate controls, 4 cache), all metrics/gates, confusion/refusal diagnostics, adapter/config hashes, exact120-update order/LR and no DEV gradients. `python -B tools/auditor_canonical_checks.py` passed all nine integration checks. Text credential scans found zero keys.');p()
    p('**Next action: local failure diagnosis only; no automatic Auditor retraining.** A Producer168 + selected Auditor + existing governance/re-fire system test is not admitted because no Auditor checkpoint passed, and would require separate authorization in any case.');p()
    (ROOT/'docs/fix/AUDITOR_CANONICAL_TUNING_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    (BASE/'HANDOFF.md').write_text('\n'.join(['# Auditor canonical completed handoff','',x['verdict'],'',
        '120 updates completed; fresh DEV60/60 at steps60/120; neither checkpoint eligible; selected adapter none.',
        'Refusal collapse absent: both checkpoints have12/12 correct required refusals, no false/missed refusals, evidenceF1=1, contract1.',
        'Relation classification fails: macroF1 .377044/.434966; accepted19/60 and28/60; confident wrong MATCH/DIVERGENCE5/4.',
        'No automatic Auditor redesign/retraining. Local failure diagnosis only. No governed Producer+Auditor test authorized or admitted.',
        'PRODUCER_STATUS=PRESERVED_UNEXECUTED','PROTECTED_RECEIPT_STATUS=UNCONSUMED',
        'One Lambda A10 us-east-1 $1.29/hour; terminated, empty inventory, temporary SSH removed; upper-bound cost $1.001014.',
        'Tested commit: '+x['source_commit'],
        'Result commit: locate by subject "Record complete canonical Auditor failure and verified cleanup".',
        'Report: ../AUDITOR_CANONICAL_TUNING_RESULTS.md. Detailed metrics: RECOMPUTED_RESULTS.json.',
        'Archive and checkpoint-{0,60,120}/adapter_model.safetensors remain local ignored binaries; checksums/text evidence committed.',
        'No push. Historical and unrelated root handoffs untouched.','']),encoding='utf8')
    print('Rendered Auditor result report and run-specific handoff')
if __name__=='__main__':main()
