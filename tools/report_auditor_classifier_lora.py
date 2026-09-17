"""Report a single completed/partial classifier-LoRA run after resource cleanup."""
import json
from pathlib import Path
import statistics
import auditor_classifier_lora_core as c
from cloud_run_common import write_json

ROOT=Path(__file__).resolve().parents[1];B=ROOT/'docs/fix/auditor_classifier_lora_run'


def report():
    r=c.read(B/'RECOMPUTED_RESULTS.json');m=c.read(B/'manifest.json');end=c.read(B/'TERMINATION_VERIFIED.json')
    assert c.read(B/'final_inventory_confirmation.json')['zero_billable_resources']
    preserve=c.read(B/'preservation_before.json')
    for name,digest in preserve.items():assert c.sha(ROOT/name)==digest,name
    write_json(B/'preservation_after.json',dict(unchanged=True,files=preserve))
    telemetry=B/'downloaded/evidence/telemetry.jsonl';samples=[json.loads(x) for x in telemetry.read_bytes().splitlines()] if telemetry.exists() else []
    gpu=[float(x['gpu'].split(',')[0]) for x in samples if x.get('gpu')]
    summary=dict(samples=len(samples),mean_gpu_utilization=statistics.mean(gpu) if gpu else None,
        peak_gpu_utilization=max(gpu) if gpu else None,peak_process_rss_gib=max((x['rss']/2**30 for x in samples),default=0),
        mean_process_cpu_percent=statistics.mean(x['cpu_percent'] for x in samples) if samples else None,
        peak_host_ram_used_gib=max((x['host_ram_used']/2**30 for x in samples),default=0))
    write_json(B/'telemetry_summary.json',summary)
    lines=['# Auditor classifier-specific LoRA results','', '**'+r['verdict']+'**','', '**'+r['diagnostic']+'**','',
        'One predeclared classification-only experiment. Historical verdicts and adapters are immutable; V2 remains quarantined and NOT_READY. This is not integrated Auditor acceptance or deployment.','',
        '## Cloud','',f"Tested commit: `{m['source_commit']}`. Lambda Cloud, {m['region']}, one A10 24GB, x86-64, one GPU. Live rate ${m['hourly_rate']:.2f}/hour; $2 soft budget and $3 hard ceiling.",'',
        f"Launch-to-confirmed-termination upper bound: {end['billable_duration_upper_bound_seconds']:.3f}s ({end['billable_duration_upper_bound_seconds']/60:.2f} minutes). Estimated compute cost ${end['estimated_cost_upper_bound_usd']:.6f}; not a provider invoice or tax calculation. Terminated {end['utc']}. Independent final inventory is empty, temporary SSH registration/key material removed. Zero billable resources.",'',
        'The initial approval-review rejection was resolved by direct operator confirmation before the one launch. No prior diagnostic authorization was reused.','',
        '## Bound architecture and data','',
        'Pinned base `unsloth/Phi-3.5-mini-instruct-bnb-4bit` at `5c20803aa197416f43fb455e55c85178775320cb` → fresh rank-8 classifier LoRA → final normalized hidden state at the last prompt token → four-way FP32 linear head. The historical step120 adapter was excluded from the payload and never loaded, stacked or modified. No old feature cache and no population feature standardization. Head zero-initialized; fresh PEFT LoRA B matrices zero; seed 7.','',
        'LoRA alpha 16, dropout .05, no bias; q/k/v/o/gate/up/down targets. Frozen base; classification CE + .001*mean(W**2). AdamW: LoRA LR 1e-4, head LR .01, betas .9/.999, epsilon 1e-8, weight decay 0, combined clip norm 1. Constant LR; no scheduler, class weights or calibration.','',
        'Exact TRAIN 1,792 (192 historical + 1,600 external), 448/class; external DEV 200, historical substantive DEV 48; SHORTER and LONGER each 75. Only preflight-bound token IDs enter the model. No provenance, gold-label, split or ID metadata in prompts. The mixed external file and HOLDOUT data were not opened.','']
    if 'training' in r:
        tr=r['training'];counts=r['trainable']
        lines+=['## Trainable state and training','',
            f"Base trainable parameters: {counts['base_trainable']:,}; classifier LoRA: {counts['classifier_lora_trainable']:,}; head: {counts['head_trainable']:,}; total: {counts['total']:,}. Historical adapter loaded: NO.",'',
            f"{tr['unique_examples']:,} unique TRAIN rows, {tr['examples']:,} presentations, {tr['passes']} complete passes, {tr['updates']} updates; microbatch 1, accumulation 4. Every update's row IDs match the frozen schedule; neither DEV set enters gradients or optimizer state.",'',
            f"First/final-update mean CE: {tr['first_ce']:.8f}/{tr['final_update_ce']:.8f}. These are the four microbatch losses measured before each update, not full-TRAIN reevaluations. Training wall {tr['training_seconds']:.3f}s; median/p95 update {tr['median_update_seconds']:.4f}/{tr['p95_update_seconds']:.4f}s. Peak allocated/reserved VRAM {tr['peak_allocated_gib']:.3f}/{tr['peak_reserved_gib']:.3f} GiB.",'',
            f"Telemetry: {summary['samples']} samples; mean/max GPU utilization {summary['mean_gpu_utilization']:.2f}%/{summary['peak_gpu_utilization']:.0f}%; peak process RSS {summary['peak_process_rss_gib']:.3f} GiB; mean process CPU {summary['mean_process_cpu_percent']:.2f}% on psutil's multicore scale; peak host RAM used {summary['peak_host_ram_used_gib']:.3f} GiB.",'']
        for cp in r['checkpoints']:
            met=cp['metrics'];lines += [f"## Checkpoint {cp['step']}",'',f"Required gates: **{'PASS' if met['passed'] else 'FAIL'}**.",'',
                f"LoRA SHA-256: `{cp['lora_sha256']}`  ",f"Head SHA-256: `{cp['head_sha256']}`",'',
                '| Evaluation | Count | Accuracy | Macro F1 | Gate |','|---|---:|---:|---:|---|']
            for group in ['external','historical']:
                v=met[group];lines.append(f"| {group} | {v['count']} | {v['accuracy']:.8f} | {v['macro_f1']:.8f} | {'PASS' if met['gates'][group] else 'FAIL'} |")
            for group in ['shorter','longer']:
                v=met['challenges'][group];lines.append(f"| {group} | {v['count']} | {v['accuracy']:.8f} | {v['macro_f1']:.8f} | {'PASS' if met['gates'][group] else 'FAIL'} |")
            for group in ['external','historical']:
                v=met[group];lines += ['',group+' per-class metrics:', '', '| Class | Precision | Recall | F1 |','|---|---:|---:|---:|']
                for label in c.CLASSES:
                    x=v['per_class'][label];lines.append(f"| {label} | {x['precision']:.8f} | {x['recall']:.8f} | {x['f1']:.8f} |")
                lines+=['','Confusion: gold rows / predicted columns.','', '| Gold | MATCH | DIVERGENCE | OMISSION | ADDITION |','|---|---:|---:|---:|---:|']
                for label in c.CLASSES:lines.append('| '+label+' | '+' | '.join(str(v['confusion'][label][p]) for p in c.CLASSES)+' |')
            lines+=['',f"Aspirational external (.80 macro F1, .70 each recall): {met['aspirational']['external']}; historical (.75 macro F1): {met['aspirational']['historical']}.",'']
    else:
        tr=r['partial_training'];counts=r['trainable']
        lines+=['## Incomplete execution','',
            f"**Numerical runtime failure during attempted update {tr['failed_attempted_update']}.** The finite-loss assertion rejected non-finite CE plus regularization before that microbatch's backward pass. Saved evidence does not isolate whether the originating problem was activations, logits, loss or parameter state. No root cause is asserted.",'',
            f"Only **{tr['completed_updates']}/896 optimizer updates** completed, covering **{tr['completed_update_examples']} TRAIN presentations** in completed updates. Zero complete passes. The number of microbatches attempted within update 4 was not recorded. Neither checkpoint 448 nor 896 exists; no DEV/challenge inference or scoring occurred. No passing result or selected checkpoint is asserted. No retry or fallback was run.",'',
            f"Verified initial trainable inventory: base {counts['base_trainable']}; classifier LoRA {counts['classifier_lora_trainable']:,}; head {counts['head_trainable']:,}; total {counts['total']:,}. Historical adapter loaded: NO. Optimizer groups exclude every base parameter.",'',
            f"First/last completed-update CE: {tr['first_ce']:.8f}/{tr['last_completed_update_ce']:.8f}; the second-update CE was 58.26807022. These are partial four-example losses, not a final training result. Completed-update wall {tr['training_seconds']:.4f}s; median/p95 {tr['median_update_seconds']:.4f}/{tr['p95_update_seconds']:.4f}s. Peak allocated/reserved VRAM in completed updates: {tr['peak_allocated_gib']:.3f}/{tr['peak_reserved_gib']:.3f} GiB.",'',
            f"Telemetry: {summary['samples']} samples; mean/max GPU utilization {summary['mean_gpu_utilization']:.2f}%/{summary['peak_gpu_utilization']:.0f}%; peak process RSS {summary['peak_process_rss_gib']:.3f} GiB.",'',
            'Initialization LoRA/head artifacts and their hashes were verified locally, including zero LoRA B matrices and zero head. Only checkpoint 0 was saved. **Post-update adapter/head weights and the final base-state comparison are unavailable** because the run aborted before a planned checkpoint. The initial inventory proves the base was frozen and excluded from the optimizer; a final bytewise state equality check cannot be claimed. Historical on-disk adapter/evidence preservation checks passed.','',
            '## Checkpoints 448 and 896','',
            '| Checkpoint | External F1/recalls | SHORTER | LONGER | Historical F1/recalls | LoRA/head hashes | Gate |',
            '|---|---|---|---|---|---|---|',
            '| 448 | Not evaluated | Not evaluated | Not evaluated | Not evaluated | Not produced | Not assessable |',
            '| 896 | Not evaluated | Not evaluated | Not evaluated | Not evaluated | Not produced | Not assessable |','']
    selected=r.get('selected')
    lines+=['## Selection and interpretation','',f"Passing checkpoints: {r.get('passing',[])}. Selected checkpoint: {selected['step'] if selected else 'none'}.",'']
    if selected:
        lines += [f"Selected LoRA: `{selected['lora_sha256']}`. Selected head: `{selected['head_sha256']}`. The verified pair is frozen in `SELECTED_CLASSIFIER.json`; integration remains separately authorized.",'']
    elif r['verdict']=='AUDITOR_CLASSIFIER_LORA_FAIL':
        lines+=['Both complete checkpoints failed. Stop automatic experiments in this base/task formulation and return to **MODEL / AUDITOR ARCHITECTURE CHOICE**. No data addition, CV, rank/LR sweep, hidden layer, generative retuning or fallback follows.','']
    lines += ['Required gates remain external macro F1 ≥ .75 and each recall ≥ .60, SHORTER/LONGER macro F1 ≥ .70, historical macro F1 ≥ .70 and each recall ≥ .60. Both DEV sets are co-primary. Checkpoint ranking uses historical F1, external F1, minimum recall across both DEV sets, earlier step, then hashes. A passing partial run cannot yield PASS. No statistical-significance claim is made.','',
        'The PAWS/WikiAtomic source-family confound remains unresolved; this experiment does not certify V2 as a clean benchmark or generally admitted corpus.','',
        '`V2_CORPUS_STATUS=AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY`  ', '`HOLDOUT_STATUS=UNCONSUMED`  ', '`PRODUCER_STATUS=PRESERVED_UNEXECUTED`','',
        'Exactly one instance/GPU; no base update or historical adapter modification. Only the fresh classifier LoRA and head were eligible for training. No explanation/refusal generation, new data, HOLDOUT, Producer, protected data, paid inference API, full pipeline, governance run, folds 1–4, multi-round, second candidate, retry, fallback or push. Zero billable resources remain.','',
        '## Evidence','',
        'The archive SHA-256 was verified locally before termination. After cleanup, the available evidence was checked locally. For this interrupted run that comprises initial trainable inventory, optimizer groups, checkpoint-0 hashes/zero initialization, the three completed updates and their TRAIN identities, partial telemetry and budget timeline, historical preservation and cleanup. There are no checkpoint DEV logits or metrics to recompute and no valid adaptation conclusion. No local model training or inference was performed.','',
        'Run directory: `docs/fix/auditor_classifier_lora_run/`. Key files: `RECOMPUTED_RESULTS.json`, `execution_manifest.json`, `training_authorization.json`, `DIRECT_OPERATOR_CONFIRMATION.json`, `collection_integrity.json`, `TERMINATION_VERIFIED.json`, `final_inventory_confirmation.json`, `cleanup.json`, `preservation_after.json`, `EVIDENCE_MANIFEST.json`. Binary adapters, heads and arrays remain local; text evidence is committed after secret scanning.','']
    (ROOT/'docs/fix/AUDITOR_CLASSIFIER_LORA_RESULTS.md').write_bytes(('\n'.join(lines)).encode())
    (B/'HANDOFF.md').write_bytes((f"# Classifier LoRA handoff\n\n{r['verdict']}\n\n{r['diagnostic']}\n\nSelected: {selected['step'] if selected else 'none'}. Tested commit `{m['source_commit']}`. See `docs/fix/AUDITOR_CLASSIFIER_LORA_RESULTS.md`. Zero billable resources. No retry or further automatic experiment authorized. Historical adapters/statuses preserved; V2 NOT_READY; HOLDOUT unconsumed; Producer unexecuted. No push.\n").encode())
    print('Results report and run handoff written.')


if __name__=='__main__':report()
