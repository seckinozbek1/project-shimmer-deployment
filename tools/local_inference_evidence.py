"""Fold bounded local evidence into the existing Report Recommendations projection."""
import json
from pathlib import Path
import sys
from local_inference_probe import SOURCE

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from run_projection import project


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def summarize(resources):
    phases = {}
    for name in sorted({s.get('phase', 'startup') for s in resources['samples']}):
        rows = [s for s in resources['samples'] if s.get('phase', 'startup') == name]
        phases[name] = dict(sampled_seconds=rows[-1]['time']-rows[0]['time'], samples=len(rows))
        for field, aggregate in [('available_ram_gib', min), ('process_rss_mib', max),
                                 ('process_cpu_percent', max), ('system_cpu_percent', max),
                                 ('gpu_utilization_percent', max), ('vram_used_mib', max),
                                 ('gpu_temperature_c', max)]:
            values = [r[field] for r in rows if field in r]
            phases[name][('min_' if aggregate is min else 'max_')+field] = aggregate(values) if values else None
    return dict(stop_reason=resources['stop_reason'], exit_code=resources['exit_code'], phases=phases,
                sampling=resources['sampling'])


def main():
    base = ROOT/'docs/fix/report_recommendations'
    destination = base/'local_inference'
    attempts = {}
    for name in ['local_validation', 'local_validation_auditor', 'local_validation_auditor_retry']:
        source = ROOT/'output/report_recommendations'/name
        resources = read(source/'resources.json')
        probe = read(source/'real_model_probe.json')
        write(destination/(name+'_resources.json'), resources)
        write(destination/(name+'_probe.json'), probe)
        attempts[name] = summarize(resources)
        attempts[name]['loads'] = probe['loads']
        attempts[name]['calls_recorded'] = len(probe['calls'])
    attempts['local_validation_auditor']['instrumentation_failure'] = (
        'Backend generation returned, but harness used text instead of raw_text. '
        'Token counts, output and finish reason were lost. One corrected repeat was authorized within scope.')
    diagnostics = dict(
        root_cause='Mixed host PyTorch files: Conda 2.5.1 record with pip 2.7.0 dist-info and extra bundled OpenMP DLLs.',
        causal_evidence=[
            'Isolated torch-only import fails; NumPy and sklearn are not required to trigger failure.',
            'Minimal PATH and -I do not resolve the failure.',
            'DLL trace loads torch/lib/libiomp5md.dll before failure during torch._C import.',
            'torch_cpu.dll imports Conda mkl_intel_thread.2.dll and libiomp5md.dll.',
            'Cached Conda torch package imports the complete stack with exactly one Conda Intel OpenMP DLL.',
            'All 12500 cached torch files passed their package manifest hashes; CPU/CUDA arithmetic passed.'],
        bundled_openmp_sha256='a9c9ddf4bb1477645120b481a14a9bcb02b8da6eece12032376e33a1ba96d2ea',
        conda_openmp_sha256='0ad71f466d115d353dce94ba32b63e288f48198e89f551d46dcce461fedbd195',
        fix='Process-local verified Conda package-cache overlay selected before torch import.',
        default_host_import_repaired=False, global_files_modified=False,
        authoritative_runtime='Host CPython 3.12.3 plus verified existing Conda PyTorch 2.5.1 CUDA 11.8 package via local_inference_runtime.configure().',
        venv_status='Python 3.9.13; Transformers and tokenizers absent. Not selected.',
        downloads=0, unsafe_suppression=False,
        standalone_integrity_verification_seconds=49.11795629999688,
        package_versions=dict(torch='2.5.1', transformers='4.51.3', numpy='1.26.4', sklearn='1.5.1', bitsandbytes='0.49.2', accelerate='1.13.0'),
        attempts=attempts,
        comparison_status=dict(processor_ab='blocked_by_producer_load_ram_guard',
            native_template_ab='blocked_by_producer_load_ram_guard',
            producer_auditor_path='not_measured',
            concurrency_1='auditor_only', concurrency_2='not_admitted_after_resource_guard',
            concurrency_4='not_admitted', model_residency='one model at most; producer initialization incomplete; auditor initialized'),
        boundaries=dict(cloud=False, paid_api=False, downloads=False, full_pipeline=False, full_model_run=False,
                        multi_round=False, push=False))
    write(destination/'summary.json', diagnostics)
    write(destination/'quality_review.json', dict(
        authored_source_characters=len(SOURCE),
        reviewed_attempt='local_validation_auditor_retry',
        contract_valid=False, accepted_semantic_output=False,
        observed_output_incomplete=True, observed_time_budget_truncation=True,
        backend_finish_reason='unknown', token_cap_contact=False,
        harness_max_time_seconds=25, harness_max_new_tokens=384,
        interpretation='Response ends inside a confidence string. No complete item, judgment, reason or evidence citation was returned.',
        typed_claim_correctness='not_assessable', reason_correctness='not_assessable',
        evidence_correctness='not_assessable', rule_attribution='not_applicable_to_fidelity_fixture',
        semantic_completeness=False, refusal_correctness='no_complete_refusal_returned',
        cross_family_path_integrity='configured_ids_preserved_but_producer_path_not_executed',
        concurrency_escalation='stopped_after_resource_and_output_validity_failures',
        earlier_auditor_attempt_output='lost_to_instrumentation_error_not_assessable'))
    spec = read(base/'projection_input.json')
    spec['resource_envelope'] = dict(gpu_total_mib=8192, attempts=attempts,
        interpretation='Sampled load/probe envelope only; producer load stopped for low available RAM.')
    spec['resource_gate_passed'] = False
    spec['quality_gate_passed'] = None
    spec['measured_truncation_count'] = None
    spec['measured_contract_refusal_risk'] = None
    note = ('Bounded inference continuation: OpenMP process-local repair verified; producer load aborted below '
            '1.25 GiB available RAM. Standalone auditor fixture cannot supply latencies for the ordinary task graph. '
            'Full-run warm/cold, retry, truncation and quality predictions remain unknown.')
    if note not in spec['assumptions']:
        spec['assumptions'].append(note)
    write(base/'projection_input.json', spec)
    result = project(spec)
    result['bounded_local_evidence'] = 'local_inference/summary.json'
    result['call_count_basis'] = 'Historical 20-task scenario; not a prediction for an unspecified input.'
    result['input_specific_call_count'] = None
    result['input_specific_call_count_formula'] = '19 + PROCESSOR partitions - deterministic comparison calls, plus retries and conditional work'
    write(base/'projection.json', result)
    print(json.dumps(dict(target=result['target_assessment'], projected_wall=result['projected_wall_seconds'],
                          evidence=str(destination))))


if __name__ == '__main__':
    main()
