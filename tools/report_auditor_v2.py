"""Write the local diagnostic report only after verified resource cleanup."""
from pathlib import Path
import auditor_v2_execution as c
from cloud_run_common import write_json

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'docs/fix/auditor_v2_diagnostic_run'


def report():
    r=c.read(B/'RECOMPUTED_RESULTS.json');m=c.read(B/'manifest.json')
    assert c.read(B/'final_inventory_confirmation.json')['zero_billable_resources']
    preserved=c.read(B/'preservation_before.json')
    for name,digest in preserved.items():assert c.sha(ROOT/name)==digest,name
    write_json(B/'preservation_after.json',dict(unchanged=True,files=preserved))
    p=r['performance'];h=r['head'];t=r['cloud'];telemetry=c.read(B/'telemetry_summary.json')
    lines=['# Auditor V2 expanded-data classification diagnostic', '',
        '**'+r['verdict']+'**', '', '**'+r['conclusion']+'**', '',
        'This is a one-off diagnostic on quarantined data. V2 remains `AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY`. The PAWS/WikiAtomic source-family confound remains unresolved; this result does not admit V2 or select/deploy an Auditor.', '',
        '## Cloud and tested implementation', '',
        '- Tested implementation: `'+r['tested_commit']+'`.',
        '- Lambda Cloud / '+m['region']+' / exactly one A10 24GB / x86-64 / one GPU.',
        f"- Live hourly rate: ${m['hourly_rate']:.2f}; soft budget $0.75; hard ceiling $1.50.",
        f"- Launch-to-confirmed-termination upper bound: {t['billable_duration_upper_bound_seconds']:.3f} seconds ({t['billable_duration_upper_bound_seconds']/60:.2f} minutes).",
        f"- Estimated compute-cost upper bound: ${t['estimated_cost_upper_bound_usd']:.6f}; this is a duration estimate, not an invoice or tax calculation.",
        '- Termination confirmed: '+t['utc']+'. Independent final inventory is empty; temporary SSH registration and local key material were removed.',
        '- Initial automatic approval review blocked launch; the operator subsequently approved the exact destination, payload and budget directly. The single instance was created only after that confirmation.', '',
        '## Features and normalization', '',
        '- TRAIN 1,792/1,792; external DEV 200/200; historical substantive DEV 48/48; total 2,040 vectors of 3,072 FP32 values.',
        '- Frozen backbone plus frozen checkpoint-120 LoRA, eval/no-grad, final normalized hidden state at the last prompt token, before assistant generation. All row/feature hashes verified locally.',
        '- Mean/std fitted only on the 1,792 TRAIN vectors; ddof=0; std clamp=1e-6. Local recomputation exactly matches saved statistics.',
        f"- Model load and initial frozen-state check: {p['load_seconds']:.3f}s; feature wall: {p['feature_seconds']:.3f}s; input tokens: {p['feature_tokens']:,}; input tokens/sec: {p['input_tokens_per_second']:.2f}.",
        f"- Peak allocated/reserved VRAM: {p['peak_allocated_gib']:.3f}/{p['peak_reserved_gib']:.3f} GiB. GPU utilization, CPU and RAM samples are in `downloaded/evidence/telemetry.jsonl`.", '',
        f"- Telemetry: {telemetry['samples']} samples; mean/max GPU utilization {telemetry['mean_gpu_utilization_percent']:.2f}%/{telemetry['max_gpu_utilization_percent']:.0f}%; peak process RSS {telemetry['peak_process_rss_gib']:.3f} GiB; peak host RAM used {telemetry['peak_host_ram_used_gib']:.3f} GiB. Mean process CPU {telemetry['mean_process_cpu_percent']:.2f}% (psutil multicore scale, so values may exceed 100%).", '',
        '## One linear head', '',
        '- Exactly 12,292 trainable parameters, W=(4,3072), b=(4,), FP32, zero initialization, seed=7. No hidden layer, dropout, calibration, class weighting, scheduler or early stopping.',
        '- Exactly 200 full-population Adam updates; lr=.01, betas=(.9,.999), epsilon=1e-8, weight decay=0; cross entropy + .001*mean(W**2). Only final update200 evaluated.',
        f"- Training wall: {h['seconds']:.6f}s; updates/sec: {h['updates_per_second']:.2f}; initial/final CE: {h['initial_ce']:.8f}/{h['final_ce']:.8f}.",
        f"- TRAIN accuracy: {r['train']['accuracy']:.8f}; macro F1: {r['train']['macro_f1']:.8f}.",
        '- Initial zero weights, final head, all 200 losses, normalization, feature arrays and logits are preserved. Frozen backbone/LoRA state hashes match before and after; neither has trainable parameters.', '']
    for key,title,count,gate in [('external','External DEV',200,r['external_pass']),('historical','Historical canonical substantive DEV — co-primary',48,r['historical_pass'])]:
        v=r[key]
        lines += ['## '+title,'',f"Complete: {v['count']}/{count}; accuracy {v['accuracy']:.8f}; macro precision {v['macro_precision']:.8f}; macro recall {v['macro_recall']:.8f}; macro F1 **{v['macro_f1']:.8f}**.",'',
            '| Class | Precision | Recall | F1 |','|---|---:|---:|---:|']
        for label in c.CLASSES:
            s=v['per_class'][label]
            lines.append(f"| {label} | {s['precision']:.8f} | {s['recall']:.8f} | {s['f1']:.8f} |")
        lines += ['', 'Confusion matrix: rows are gold; columns are predictions.', '', '| Gold / predicted | MATCH | DIVERGENCE | OMISSION | ADDITION |','|---|---:|---:|---:|---:|']
        for label in c.CLASSES:lines.append('| '+label+' | '+' | '.join(str(v['confusion'][label][p]) for p in c.CLASSES)+' |')
        if key=='external':
            principal=c.d.passes(v,.75,.60)
            lines += ['',f"Principal gate (macro F1 >= .75, every recall >= .60): {'PASS' if principal else 'FAIL'}. External including both challenges: {'PASS' if gate else 'FAIL'}."]
        else:
            lines += ['',f"Historical co-primary gate (macro F1 >= .70, every recall >= .60): {'PASS' if gate else 'FAIL'}.",
                f"Previous saved-probe four-way macro F1: {r['baseline_macro_f1']:.10f}; new-minus-previous delta: **{r['historical_macro_f1_delta']:+.10f}**. Baseline predictions were not regenerated."]
        lines += ['',f"Classification wall: {p['classification_seconds'][key+'_dev']:.6f}s.",'']
    lines += ['## External challenges','', '| Challenge | Evaluated | Three-class macro F1 | Gate >= .70 |','|---|---:|---:|---|']
    for name,v in r['challenges'].items():lines.append(f"| {name.upper()} | {v['count']}/75 | {v['macro_f1']:.8f} | {'PASS' if v['macro_f1']>=.70 else 'FAIL'} |")
    lines += ['', 'SHORTER uses MATCH/DIVERGENCE/OMISSION; LONGER uses MATCH/DIVERGENCE/ADDITION; 25 rows per supported class. Predictions outside the supported classes still count as errors. Full precision/recall/F1 and confusion matrices for each challenge are in `RECOMPUTED_RESULTS.json`.', '',
        '## Interpretation and boundaries','',
        'Both DEV sets are co-primary. Success requires external macro F1 >= .75, each external recall >= .60, both challenge macro F1 >= .70, historical macro F1 >= .70, and each historical recall >= .60. No thresholds were lowered. No statistical-significance claim is made.', '',
        'Under this one predeclared configuration, expanded labeled data did not support the generalization hypothesis: external MATCH recall was .54, historical MATCH/DIVERGENCE recalls were .4167/.3333, and historical macro F1 declined by .03265. Both principal gates and both challenges failed despite near-perfect TRAIN performance. This does not establish that every possible head or representation would fail.', '',
        'Only prompt token IDs entered the model. Provenance, source family, split, gold label, ID and row position were outside the prompt. Textual source inferability has not been ruled out. External scores alone cannot establish generalization.', '',
        '`V2_CORPUS_STATUS=AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY`  ',
        '`HOLDOUT_STATUS=UNCONSUMED`  ',
        '`PRODUCER_STATUS=PRESERVED_UNEXECUTED`', '',
        'No backbone, LM-head or Auditor LoRA updates; no explanation or refusal generation/retraining; no new data, HOLDOUT access/evaluation, Producer execution, protected-data access, paid inference API, full pipeline, governance run, folds 1–4, multi-round, second candidate or second instance. Execution consumed the bound records without reopening the mixed V2 corpus. Historical reports/manifests and HOLDOUT receipt identities remain unchanged. No push. Zero billable resources remain.', '',
        '## Evidence and local verification','',
        'The downloaded archive SHA-256 matched the remote archive before teardown. After confirmed termination, local NumPy recomputation verified every feature identity, TRAIN-only normalization, final-head logits and metrics, both co-primary gates, both challenges, baseline delta, 200 updates and frozen-state equality. No local model inference or training was used.', '',
        'Key artifacts in `docs/fix/auditor_v2_diagnostic_run/`: `execution_manifest.json`, `training_authorization.json`, `DIRECT_OPERATOR_CONFIRMATION.json`, `collection_integrity.json`, `TERMINATION_VERIFIED.json`, `final_inventory_confirmation.json`, `cleanup.json`, `RECOMPUTED_RESULTS.json`, `preservation_after.json`, and `EVIDENCE_MANIFEST.json`. Bulk arrays/adapters/archives remain local; text evidence is committed after secret scanning.', '']
    (ROOT/'docs/fix/AUDITOR_V2_DIAGNOSTIC_RESULTS.md').write_bytes(('\n'.join(lines)).encode())
    (B/'HANDOFF.md').write_bytes((f"# Auditor V2 diagnostic handoff\n\n{r['verdict']}\n\n{r['conclusion']}\n\nTested commit: `{r['tested_commit']}`. Final results: `docs/fix/AUDITOR_V2_DIAGNOSTIC_RESULTS.md`. Both DEV sets and both challenges were recomputed locally after verified termination. Zero billable resources. No run authorization remains for a second instance or candidate. V2 remains NOT_READY; HOLDOUT unconsumed; Producer preserved and unexecuted. No push.\n").encode())
    print('Results report and run-specific handoff written.')


if __name__=='__main__':report()
