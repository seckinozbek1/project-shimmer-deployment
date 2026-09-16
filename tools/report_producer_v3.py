"""Render the completed V3 result and handoff from independently verified evidence."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/fix/producer_tuning_v3_run'


def main():
    x = json.loads((BASE / 'RECOMPUTED_RESULTS.json').read_text())
    assert json.loads((BASE / 'POST_RUN_VERIFICATION.json').read_text())['passed']
    t = x['training']; cloud = x['cloud']; term = cloud['termination']; cps = x['checkpoints']
    lines = []
    def p(text=''):
        lines.append(text)
    def table(headers, values):
        p('| ' + ' | '.join(headers) + ' |')
        p('| ' + ' | '.join('---' for _ in headers) + ' |')
        for row in values:
            p('| ' + ' | '.join(str(v) for v in row) + ' |')
        p()
    p('# Producer tuning V3 results')
    p()
    p('`PRODUCER_TUNING_V3_FAIL`')
    p()
    p('The single authorized fresh Producer V3 run completed all 168 updates and both fresh 84-row DEV evaluations validly. Neither checkpoint passes every frozen gate. No checkpoint is selected. Stop the Producer LoRA branch: no automatic V4, added data, hyperparameter sweep, or retraining. Any architecture/model-choice review requires a separate task.')
    p()
    p('## Cloud and cleanup')
    p()
    p(f"Tested cloud/executor commit: `{x['source_commit']}`. V3 design commit: `eb958cd4d25a667ad2744cba01ac87c90270883f`. One Lambda Cloud A10 24 GB, x86-64, us-east-1, at **$1.29/hour**.")
    p()
    p(f"Launch-to-confirmed-termination upper bound: **{term['billable_duration_upper_bound_seconds']:.3f} seconds (80 minutes 10 seconds)**. Estimated upper-bound compute cost: **${term['estimated_cost_upper_bound_usd']:.6f}**, not a provider invoice. The $3 soft budget was never reached. Termination confirmed at `{term['utc']}`; independent subsequent inventory was empty. Temporary SSH registration and local key material were removed. Zero billable experiment resources remain.")
    p()
    p('Before launch the actual price allowed 139.535 minutes to $3 and 279.070 minutes to $6. The workload cutoff was 269.070 minutes, preserving ten minutes for evidence/teardown. A separate operator watchdog was armed to terminate before the hard ceiling. All durable progress projections remained within the cutoff.')
    p()
    p('## Identity and execution')
    p()
    p(f"Dataset `producer-targeted-v3.0` SHA-256: `{x['dataset_sha256']}`. V3 freeze: `68afb77a9a5ff7c9360075c2699e6cb1d4cc57e1828728496a6648c49a3b7850`. Evaluation runtime `second-tuning-eval-runtime-v2_1` freeze: `8d1fd41d1ab059e47b1297c1c39cd29711acd8fa5446a60780f9a97faef1d1fa`.")
    p()
    p('Base: `unsloth/Qwen2.5-7B-Instruct-bnb-4bit`, revision `bdd404162d94997f390efbfa660eb3f21cbbc81d`, weight SHA-256 `99b85155b7bb40344d8c3938c8ec1147b27028804bca5d2e5559cb8e6533747d`. Acquisition hashes, frozen configuration, and executed source hashes were verified. Base identity is bound by the acquisition/configuration receipts, rather than repeated in each low-level raw generation row.')
    p()
    p('Fresh seed-7 LoRA initialization was verified, including all-zero initial LoRA-B tensors and 20,185,088 trainable parameters. No V2 adapter was uploaded or loaded. The 420-row frozen corpus contains 336 TRAIN and 84 DEV rows, with no leakage-group overlap. The exact prospective four-example update order was verified: every TRAIN example appears twice, 672 exposures total, and no DEV example enters gradients. No update follows 168.')
    p()
    p('Optimization remained AdamW, LR 0.0001, betas 0.9/0.999, epsilon 1e-8, zero weight decay, linear schedule, one warmup update, clipping 1, microbatch 1 and accumulation 4. LoRA r8/alpha16/dropout0.05/bias-none and all seven frozen projection modules remained unchanged. Per-example mean target-only assistant-plus-native-termination loss retained equal example weights. Runtime remained BF16/eager, gradient checkpointing, deterministic algorithms, TF32 off, pinned NF4/double quantization; all 420 encodings fit 992 tokens, with observed maximum 988 and no truncation.')
    p()
    p('At each checkpoint, the real-object context preflight generated nothing; cache probes and both optimized six-ID control passes passed. All prompt/input IDs, output IDs, decoded strings, semantic/contract scores and stop reasons matched within each control pair. Each pass independently exceeded 4.438538339317307 output tokens/second. No historical traced-reference pass or observer-removal ratio was used. Exact parameter/gradient/optimizer/scheduler/adapter/training-counter and RNG restoration passed, including before update 85. Raw rows were fsynced before scoring; all 196 outputs were independently decoded and rescored locally after termination.')
    p()
    p('## Training telemetry')
    p()
    table(['Measure', 'Value'], [
        ('Optimizer updates', t['updates']), ('Training wall excluding DEV', f"{t['training_seconds']:.3f} s / {t['training_seconds']/60:.3f} min"),
        ('First / final update loss', f"{t['initial_loss']:.9f} / {t['final_loss']:.9f}"),
        ('Update wall median / p95', f"{t['update_seconds']['median']:.6f} / {t['update_seconds']['p95']:.6f} s"),
        ('Peak CUDA allocated / reserved', f"{t['peak_vram_allocated_bytes']} / {t['peak_vram_reserved_bytes']} bytes ({t['peak_vram_allocated_bytes']/2**30:.3f} / {t['peak_vram_reserved_bytes']/2**30:.3f} GiB)"),
        ('Training GPU utilization mean / median / p95', f"{t['telemetry']['gpu_utilization_percent']['mean']:.3f}% / 100% / 100% ({t['telemetry']['samples']} samples)"),
        ('Overall GPU utilization mean / median', f"{t['overall_telemetry']['gpu_utilization_percent']['mean']:.3f}% / 30% ({t['overall_telemetry']['samples']} samples)"),
        ('Training process CPU mean', f"{t['telemetry']['cpu_percent']['mean']:.3f}% (100% corresponds to one logical CPU)"),
        ('Peak sampled process RSS / host RAM used', f"{t['overall_telemetry']['rss_bytes']['max']} / {t['overall_telemetry']['host_ram_used_bytes']['max']} bytes")])
    p('Update losses use different scheduled examples and are descriptive training telemetry, not a held-out loss comparison. CUDA peaks are allocator counters; the separate telemetry process additionally records device memory and utilization.')
    p()
    p('## Checkpoint identity and runtime')
    p()
    for step in ('84', '168'):
        p(f"Checkpoint {step} adapter SHA-256: `{cps[step]['identity']['files']['adapter_model.safetensors']}`.")
        p()
    p(f"Shared adapter-config SHA-256: `{cps['84']['identity']['files']['adapter_config.json']}`. Initialization adapter SHA-256: `{t['identities']['0']['files']['adapter_model.safetensors']}`.")
    p()
    table(['Measure', 'Checkpoint 84', 'Checkpoint 168'], [
        ('Deterministic controls', '6/6', '6/6'),
        ('Control pass 1 / pass 2 tok/s', *[' / '.join(f'{v:.6f}' for v in cps[s]['controls']['per_pass_tokens_per_second']) for s in ('84','168')]),
        ('Fresh complete DEV', '84/84', '84/84'),
        ('DEV generation wall (s)', *[f"{cps[s]['generation_seconds']:.6f}" for s in ('84','168')]),
        ('DEV aggregate output tok/s', *[f"{cps[s]['tokens_per_second']:.6f}" for s in ('84','168')]),
        ('Generated DEV output tokens', *[cps[s]['output_tokens'] for s in ('84','168')]),
        ('Every frozen quality gate passed', 'FAIL', 'FAIL')])
    p('Generation timing includes prefill; decode-only latency and TTFT were not measured. CUDA synchronization bounded each generation. Full DEV throughput excludes cache/control probes.')
    p()
    p('## Frozen quality gates')
    p()
    spec=json.loads((ROOT/'tuning/producer_v3/experiment.json').read_text())
    gate_rows=[]
    for direction,bounds in spec['selection_gates'].items():
        for name,bound in bounds.items():
            gate_rows.append((name, ('>=' if direction=='minimum' else '<=')+str(bound), *[f"{cps[s]['metrics'][name]:.9f}" for s in ('84','168')]))
    table(['Metric', 'Required', 'Checkpoint 84', 'Checkpoint 168'], gate_rows)
    p('Checkpoint 84 has 83/84 valid contracts and 48/84 accepted/complete outcomes. Checkpoint 168 has 84/84 valid contracts and 59/84 accepted/complete outcomes; at least 63/84 are required. Refusals: checkpoint 84 correctly refuses 8/8 required refusals, but also refuses 13/76 non-refusal rows; checkpoint 168 correctly refuses 5/8 and incorrectly refuses 4/76 non-refusal rows.')
    p()
    table(['Semantic atoms', '84 precision / recall / F1', '168 precision / recall / F1'], [
        (name,*[' / '.join(f"{cps[s]['atom_metrics'][name][k]:.9f}" for k in ('precision','recall','f1')) for s in ('84','168')]) for name in ('claims','evidence','typed_gaps','typed_uncertainty')])
    table(['Catastrophic category', 'Checkpoint 84', 'Checkpoint 168'], [(k,cps['84']['metrics']['catastrophic'][k],cps['168']['metrics']['catastrophic'][k]) for k in cps['84']['metrics']['catastrophic']])
    p('These are the unchanged frozen scorer categories; zero counts are scoped to this canonical DEV evaluation, not a broader safety claim. DEV was used for selection and is not an independent final benchmark.')
    p()
    p('## Output efficiency')
    p()
    table(['Output tokens', 'Checkpoint 84', 'Checkpoint 168'], [(k,*[f"{cps[s]['efficiency']['output_tokens'][k]:.6f}" for s in ('84','168')]) for k in ('min','median','mean','p90','p95','p99','max')])
    p('Both checkpoints: EOS before cap 84/84 (100%); cap hits 0/84 (0%); trailing prose 0; second JSON 0; code fences 0; exact/canonical duplicate atoms 0 in every atom category. Quantiles use linear interpolation at (n-1)q.')
    p()
    table(['Correct semantic atoms / all generated DEV tokens', 'Checkpoint 84', 'Checkpoint 168'], [(k,*[f"{cps[s]['efficiency']['aggregate_correct_atoms_per_output_token'][k]:.9f}" for s in ('84','168')]) for k in ('claims','typed_gaps','typed_uncertainty','evidence')])
    p('The denominator includes all 84 outputs, including failures and refusals; the numerator is exact micro-counted true-positive atoms. Per-row efficiency distributions are also preserved in RECOMPUTED_RESULTS.json. Efficiency never overrides a quality gate.')
    p()
    table(['Accepted category', 'Checkpoint', 'Count', 'Total tokens', 'Mean', 'Median', 'Min / p90 / p95 / p99 / max'], [
        (name,s,cps[s]['accepted_groups'][name]['count'],cps[s]['accepted_groups'][name]['total_tokens'],
         f"{cps[s]['accepted_groups'][name]['token_cost']['mean']:.6f}",f"{cps[s]['accepted_groups'][name]['token_cost']['median']:.6f}",
         ' / '.join(f"{cps[s]['accepted_groups'][name]['token_cost'][k]:.2f}" for k in ('min','p90','p95','p99','max')))
        for name in ('correct_refusals','correct_empty','substantive_successes') for s in ('84','168')])
    p('Small refusal/empty groups have descriptive tail quantiles only; they are not stable population-tail estimates. Accepted-output cost conditions on correctness and is not a cost-per-attempt measure.')
    p()
    p('## Selection and stop rule')
    p()
    p('Passing checkpoints: none. Selected checkpoint: none. Selected adapter SHA-256: not applicable. Both complete checkpoints fail at least one gate, so the quality-first eligibility filter yields no candidates; completeness/gap/earlier-step/hash tie-breaks do not apply. The better-scoring checkpoint 168 is retained as evidence, not selected for deployment.')
    p()
    p('`PRODUCER_TUNING_V3_FAIL` — stop Producer LoRA. No V4, automatic data expansion, rank/LR changes, sweeps, or retraining. Recommend only a separately scoped architecture/model-choice review. Auditor is not the next automatically authorized action.')
    p()
    p('## Preservation, durability, and verification')
    p()
    p('The post-run frozen release verifier passed all 36 V3 bound files and dependencies, 436 historical byte hashes, three protected-artifact metadata checks, and two historical adapter metadata checks. Protected target labels were not opened; historical adapter tensors were not loaded. Historical `PRODUCER_CHECKPOINT120_FAIL`, `SECOND_TUNING_CANONICAL_PILOT_INDETERMINATE`, runtime-V2 NO_GO and runtime-V2.1 evidence remain unchanged. Historical protected-wrapper inventory details remain documented in the pre-existing preservation receipt; this run used metadata-only protected checks.')
    p()
    p('`AUDITOR_STATUS=UNTOUCHED`  \n`PROTECTED_RECEIPT_STATUS=UNCONSUMED`')
    p()
    p('Exactly one instance and one GPU were used. No second GPU, protected evaluation/access, Auditor acquisition/execution, folds 1-4, paid inference API, full Shimmer pipeline, multi-round run, or push occurred. Zero billable resources remain.')
    p()
    p(f"Downloaded archive: `producer_tuning_v3_run/evidence.tar.gz`, 182,859,528 bytes, SHA-256 `{x['archive_sha256']}`. Archive hash matched before termination. Path-safe extraction and all checkpoint/config hashes passed afterward. Bulk archive and three adapter-weight files remain local and ignored; their hashes and all reviewable text evidence are committed. Copy those local binaries separately if moving to another machine.")
    p()
    p('Primary evidence under `producer_tuning_v3_run/`: `RECOMPUTED_RESULTS.json`, `RECOMPUTED_PER_ROW.json`, `POST_RUN_VERIFICATION.json`, `EVIDENCE_MANIFEST.json`, `final_inventory_confirmation.json`, `TERMINATION_VERIFIED.json`, and `downloaded/evidence/`. The latter contains exact training order/loss/LR records, adapter/config identities, state/RNG receipts, cache/control/raw DEV/scoring records, telemetry, and budget timeline. The execution bundle is hash-bound and contains only reviewed Producer scope. No old authorization was reused.')
    p()
    p('Local verification commands: `python -B tools/analyze_producer_v3.py`; `python -B tools/producer_v3_checks.py`; `python -B tuning/producer_v3/release.py`. The independent verifier requires the preserved local archive and adapters. It recomputed 196 raw outputs (168 full DEV + 24 control + 4 cache), all gates and selection, exact schedule, learning rates, fresh initialization tensors, checkpoint hashes, state restoration, and cleanup. Text evidence was scanned without printing credential values; zero findings.')
    p()
    p('Reproduction limitation: a checked-out repository contains the text evidence and identities; rerunning the full local verifier additionally needs the preserved local binary archive/adapters and existing pinned tokenizer assets. No new model generation is performed by the verifier.')
    (ROOT/'docs/fix/PRODUCER_TUNING_V3_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    (BASE/'HANDOFF.md').write_text('\n'.join([
        '# Producer V3 completed handoff','',x['verdict'],'',
        'Both checkpoints completed validly: 168 updates, 84/84 fresh DEV at each, no passing checkpoint and no selected adapter.',
        'Stop Producer LoRA branch. No automatic V4, data expansion, sweep, or retraining; architecture/model-choice review only under a separate task.',
        'One Lambda us-east-1 A10 at $1.29/hour; confirmed terminated; upper-bound cost $1.723579; inventory empty; temporary SSH registration/key material removed.',
        'AUDITOR_STATUS=UNTOUCHED','PROTECTED_RECEIPT_STATUS=UNCONSUMED','No push.',
        '', 'Read ../PRODUCER_TUNING_V3_RESULTS.md and RECOMPUTED_RESULTS.json for complete metrics and identities.',
        'evidence.tar.gz and downloaded/evidence/checkpoint-{0,84,168}/adapter_model.safetensors remain locally preserved, ignored binary evidence. Text evidence and checksums are committed.',
        'The immutable design HANDOFF and unrelated root SHIMMER_HANDOFF.md were not edited.',
        'Tested executor commit: '+x['source_commit'],
        'Result commit: locate by subject "Record complete Producer V3 failure and verified cloud cleanup".', ''
    ]),encoding='utf8')
    print('Rendered V3 result report and run-specific handoff')


if __name__ == '__main__':
    main()
