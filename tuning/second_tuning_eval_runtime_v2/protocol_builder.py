"""Local-only prospective protocol and exact tokenization; no model execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FROZEN = ROOT / 'tuning/second_domain_agnostic_v2'
PILOT = ROOT / 'docs/fix/second_tuning_canonical_pilot'
sys.path.insert(0, str(FROZEN))
import runtime as frozen
from eval_runtime import digest, require, validate_records, validate_generation


def filehash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def producer_rows():
    rows = {x['example_id']: x for x in frozen.read(FROZEN / 'dataset.json') if x['role'] == 'producer'}
    splits = frozen.read(FROZEN / 'splits.json')
    require(all(splits['canonical'][key] == splits['folds'][0][key] for key in ('train', 'validation')), 'Canonical fold changed')
    ids = [i for i in splits['canonical']['validation'] if i in rows]
    require(len(ids) == 60, 'Expected exactly 60 Producer DEV rows')
    return [rows[i] for i in ids]


def tokenize():
    tok = frozen.old.tokenizer('producer')  # Tokenizer/config assets only, offline.
    records = []
    for row in producer_rows():
        messages = frozen.task_messages(row)
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        encoded = tok(prompt, add_special_tokens=False)
        require(encoded['input_ids'] == tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=True), 'Prompt tokenization mismatch')
        records.append(dict(example_id=row['example_id'], role='producer', split='canonical',
                            prompt=prompt, input_ids=encoded['input_ids'], attention_mask=encoded['attention_mask']))
    return tok, records


def bind_adapter():
    # This explicit byte-hash phase is separate from the weight-denying dry-run.
    folder = PILOT / 'downloaded/runs/second-domain-agnostic-v2/canonical/producer/checkpoint-120'
    hashes = frozen.read(PILOT / 'EVIDENCE_HASHES.json')
    values = {}
    for name in ('adapter_config.json', 'adapter_model.safetensors'):
        path = folder / name
        expected = hashes[str(path.relative_to(PILOT / 'downloaded'))]
        require(filehash(path) == expected, 'Saved adapter artifact changed')
        values[name] = expected
    require(values['adapter_model.safetensors'] == '3f1e12d107f1206641902565b28ea6217d70ff2768c321a216227dbc21b702a6', 'Wrong checkpoint adapter')
    proof = dict(role='producer', checkpoint=120, split='canonical', files=values,
                 method='Streaming byte hashes only; no safetensors/tensor/model load',
                 verified=True, weights_modified=False)
    frozen.write(HERE / 'adapter_binding.json', proof)
    return proof


def build():
    from boundary import install
    install(ROOT, allowed_writes=[HERE])
    tok, records = tokenize()
    spec = frozen.read(FROZEN / 'producer/experiment.json')
    historical = frozen.read(PILOT / 'downloaded/runs/second-domain-agnostic-v2/canonical/producer/validation-60.json')
    require([x['example_id'] for x in records] == [x['example_id'] for x in historical], 'Historical DEV order mismatch')
    require(all(hashlib.sha256(x['prompt'].encode()).hexdigest() == h['prompt_sha256'] for x, h in zip(records, historical)), 'Historical prompts changed')
    audit = frozen.read(HERE / 'audit_results.json')
    run1 = audit['historical_throughput']['run1_combined']['prefill_inclusive_output_tokens_per_second']
    current = audit['historical_throughput']['pilot_120']['prefill_inclusive_output_tokens_per_second']
    floor = run1 / 2
    ids = [x['example_id'] for x in records]
    controls = [ids[i] for i in (0, 10, 20, 30, 40, 50)]
    protocol = dict(
        name='second-tuning-eval-runtime-v2', readiness='LOCAL_DESIGN_ONLY',
        source_experiment='second-domain-agnostic-v2',
        frozen_v2_sha256='bb27d49234fcc30cf02438ac0ce1c43dc690cf514aa9ebbe8d4ae4f6341aa78d',
        historical_pilot_verdict='SECOND_TUNING_CANONICAL_PILOT_INDETERMINATE',
        FULL_GROUPED_CV_CONTINUATION_RECOMMENDED=False,
        operator_authorized=False, cloud_authorized=False, role='producer', checkpoint=120,
        model_id=spec['model_id'], revision=spec['revision'], base_weight_hashes=spec['base_weight_hashes'],
        adapter=frozen.read(HERE / 'adapter_binding.json'),
        tokenizer_asset_hashes=spec['asset_hashes'],
        generation_kwargs=dict(spec['generation'], eos_token_id=spec['terminal_token_ids'], pad_token_id=tok.pad_token_id),
        architecture=spec['architecture']['family'], dtype='bfloat16', attention='eager', quantization=spec['quantization'],
        lora=spec['lora'], batch_size=1, no_adapter_merge=True,
        dev_ids=ids, control_ids=controls, control_positions_zero_based=[0, 10, 20, 30, 40, 50],
        historical_trace_ast_sha256=audit['observer_effect']['exact_callback_ast_sha256'],
        cache_preflight_id=controls[0], cache_preflight_calls=2,
        prompt_bindings={x['example_id']: dict(prompt_sha256=hashlib.sha256(x['prompt'].encode()).hexdigest(), input_ids_sha256=digest(x['input_ids']), input_length=len(x['input_ids'])) for x in records},
        speed_gate=dict(minimum_tokens_per_second=floor, minimum_paired_speedup=2.0,
                        rationale='Recover at least half the measured run-1 Producer aggregate rate and at least double a same-ID historical-observer reference; current pilot was about 4.7x slower. These are conservative prospective admission requirements, not measured speedup claims.',
                        historical_run1_tokens_per_second=run1, historical_pilot_prefix_tokens_per_second=current,
                        exact_token_identity_required=True, exact_metric_identity_required=True,
                        failure_action='NO_GO: stop; no full DEV, no changed threshold, no model/adapter updates'),
        controls=dict(order='For each of six fixed IDs: reference then optimized, same resident model and adapter; discard no measurements',
                      reference='Pinned historical generation task with the exact historical global trace callback enabled only over generate; no training, optimizer, source repair or old-output reuse',
                      optimized='Same task and tensors, no Python trace/profile callback, independent telemetry process',
                      equivalence='Compare exact output IDs, prompt/input IDs and frozen row metrics. Any mismatch is NO_GO; no automatic claim of a new valid protocol.',
                      partial_history='42 saved outputs are historical only; neither controls nor historical rows are stitched into complete DEV'),
        full_dev=dict(order='Regenerate every canonical ID from item 1 through 60 after control PASS; new exclusive output directory',
                      required_outputs=60, no_stitching=True, no_checkpoint_selection=True,
                      gate_evaluation='Evaluate checkpoint-120 frozen Producer gates on all 60 new outputs; report this new evaluation separately. No historical selection rewrite or Auditor/protected evaluation.'),
        runtime_preflight=dict(python='3.12.3', platform='linux_x86_64', dependency_lock='tuning/first_domain_agnostic_v1/dependency_lock.json',
                               deterministic_environment='tuning/first_domain_agnostic_v1/experiment.json:environment',
                               seed=7, deterministic_algorithms=True, allow_tf32=False, exactly_one_bf16_gpu=True,
                               model_loader='Fresh process; exact local pinned base, BF16/eager/device_map={empty:0}; same prepare_model_for_kbit_training(True) and get_peft_model(LoraConfig) as historical executor; load saved adapter via pinned PEFT adapter-state APIs with complete key/shape/dtype checks. No merge/cast shortcut/optimizer/gradient update. Verify all module devices, dtypes, trainable count and weight hashes.',
                               peft_source_limitation='PEFT 0.15.2 source not installed/cached locally; do not claim its internal behavior was directly inspected. Future preflight must record its source hashes and actual activation/forward/cache state before control admission.',
                               cache_effect_proof='On control first/second forward, record effective use_cache=True, nonempty returned cache after prefill, and one-token incremental input. Abort on failure. Use identical boundary probes for reference/optimized and exclude probing from reported speed trial only via a separately declared preflight pass, never deleting slow trial results.',
                               no_current_execution=True),
        projection=dict(label='PROJECTION_NOT_BENCHMARK_NOT_AUTHORIZATION',
                        historical_hourly_rate_usd=1.29, current_price_not_queried=True,
                        minimum_admitted_generation_tokens_per_second=floor,
                        full_dev_cap_bound_tokens=60 * 288,
                        full_dev_generation_seconds_at_floor=60 * 288 / floor,
                        control_reference_seconds_at_historical_rate=6 * 288 / current,
                        control_optimized_seconds_at_floor=6 * 288 / floor,
                        setup_allowance_seconds=600, teardown_reserve_seconds=600,
                        assumptions='Historical A10 rate only; no cloud authorization. Cap-based output bound, not extrapolation of missing semantic metrics. Future live price, capacity and preflight timing must pass a separately authorized budget.'),
        excluded=['training','auditor','protected','folds_1_4','paid_api','full_pipeline','multi_round','push'])
    # Cache-effect probes need real future forwards; plan one additional control pair,
    # charged at the same cap-based bounds, not silently removed from cost.
    projection = protocol['projection']
    projection['cache_preflight_reference_seconds'] = 288 / current
    projection['cache_preflight_optimized_seconds'] = 288 / floor
    projection['total_seconds_with_reserve_at_floor'] = sum(projection[k] for k in ('full_dev_generation_seconds_at_floor','control_reference_seconds_at_historical_rate','control_optimized_seconds_at_floor','setup_allowance_seconds','teardown_reserve_seconds','cache_preflight_reference_seconds','cache_preflight_optimized_seconds'))
    projection['estimated_cost_at_historical_rate_usd'] = projection['total_seconds_with_reserve_at_floor'] * 1.29 / 3600
    validate_records(records, protocol)
    validate_generation(protocol['generation_kwargs'], protocol)
    frozen.write(HERE / 'prepared_dev.json', records)
    frozen.write(HERE / 'protocol.json', protocol)
    frozen.write(HERE / 'dry_run_evidence.json', dict(status='PASS', prompts=60, historical_prompt_hash_matches=60,
                 tokenization_paths_equal=60, model_weight_opens=0, model_generations=0, network_calls=0,
                 auditor_executions=0, protected_accesses=0, note='Audit-hook enforced dry run; adapter byte hashing was a separate explicitly named phase'))
    print(json.dumps(dict(prompts=60, control_ids=controls, speed_floor=floor, projection=projection), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('bind-adapter', 'dry-run'))
    args = parser.parse_args()
    if args.action == 'bind-adapter':
        print(json.dumps(bind_adapter(), indent=2))
    else:
        build()
