"""Post-termination, no-generation recomputation of the authorized experiment."""
from collections import Counter
import json
from pathlib import Path
import statistics
import sys
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/fix/first_real_tuning_20260916'
DATA=OUT/'downloaded'
FROZEN=ROOT/'tuning/first_domain_agnostic_v1'
sys.path.insert(0,str(FROZEN))
import common as c
import evaluation as ev

def mean(values):return statistics.mean(values) if values else None
def ratio(n,d):return n/d if d else None

def analyze():
    c.require(c.read(OUT/'instances_after.json')==[] and (OUT/'TERMINATION_VERIFIED.json').exists(),'Terminate before local analysis')
    c.frozen()
    roles={}
    for role in c.PINS:
        spec=c.read(FROZEN/role/'experiment.json');run=DATA/'runs/first-domain-agnostic-tuning-v1'/role
        records=c.load_rows(role,'dev');results=c.read(run/'checkpoint_results.json')
        summaries=[]
        for result in results:
            saved=c.checked(run/result['evidence_file'],result['evidence_sha256'])
            c.require([v['example_id'] for v in saved]==[r['example_id'] for r in records],'DEV population mismatch')
            scores=[ev.score(r,v['raw_output'],v['truncated']) for r,v in zip(records,saved)]
            c.require(ev.selection_metrics(role,scores)==result['metrics'],'Recomputed metrics mismatch')
            c.require(all(v['semantic_metrics']==s and v['identity']==result['identity'] for v,s in zip(saved,scores)),'Saved evidence binding mismatch')
            c.verify_adapter(run/('checkpoint-'+str(result['step'])),result['identity'],role)
            fields=['evidence']+(['claims','information_gaps','uncertainty'] if role=='producer' else [])
            micro={}
            for field in fields:
                counts={k:sum(s[field][k] for s in scores) for k in ('tp','fp','fn')}
                tp,fp,fn=(counts[k] for k in ('tp','fp','fn'))
                micro[field]=dict(counts,precision=ratio(tp,tp+fp),recall=ratio(tp,tp+fn),f1=ratio(2*tp,2*tp+fp+fn))
            invalid=[]
            for row,item,s in zip(records,saved,scores):
                if s['contract_valid']:continue
                reason='truncated' if s['truncated'] else 'malformed'
                try:
                    cc,_,_,core=c.dependencies();obj=core.strict_json(item['raw_output']);record=c.scoring_record(row)
                    if role=='producer':cc.producer(obj,core.owned(record),row['example_id'])
                    else:cc.auditor(obj,row['example_id'],record['required_refs'],record['supplied_refs'])
                except Exception as exc:reason=str(exc)
                invalid.append(dict(example_id=row['example_id'],reason=reason))
            summaries.append(dict(step=result['step'],adapter_sha256=result['identity']['sha256'],**result['metrics'],
                count=len(scores),contract_valid=sum(s['contract_valid'] for s in scores),
                accepted_outcomes=sum(s['accepted_outcome'] for s in scores),
                expected_refusals=sum(s['expected_refusal'] for s in scores),predicted_refusals=sum(s['predicted_refusal'] for s in scores),
                refusal_correct=sum(s['refusal_correct'] for s in scores),
                relation_correct=sum(s.get('relation_correct',False) for s in scores),
                reason_correct=sum(s.get('reason_correct') is True for s in scores),
                semantic_completeness=sum(s.get('semantic_completeness',False) for s in scores),
                micro_metrics=micro,invalid_outputs=invalid,
                generation_seconds=sum(v['latency_seconds'] for v in saved),
                mean_generation_seconds=mean([v['latency_seconds'] for v in saved]),
                output_tokens=sum(v['output_tokens'] for v in saved),
                output_tokens_per_second=sum(v['output_tokens'] for v in saved)/sum(v['latency_seconds'] for v in saved),
                stop_reasons=dict(Counter(v['stop_reason'] for v in saved))))
        status=c.read(DATA/'evidence'/(role+'_status.json'))
        events=c.read(DATA/'evidence'/(role+'_events.json'))
        samples=[json.loads(line) for line in (DATA/'evidence'/(role+'_telemetry.jsonl')).read_text().splitlines()]
        loss=c.read(run/'train_loss_diagnostic.json')
        selected=None
        try:selected=ev.verify_selection(role,run)['selected']
        except FileNotFoundError:
            try:ev.select(role,results,spec)
            except ValueError as exc:c.require(str(exc)=='No checkpoint passes catastrophic and contract gates','Unexpected selection failure')
            else:raise ValueError('Selection freeze missing despite eligible checkpoint')
        steps=[e for e in events if e['kind']=='optimizer_step']
        c.require(len(steps)==spec['training']['max_steps']==status['optimizer_steps'],'Optimizer count mismatch')
        module=next(e for e in events if e['kind']=='module_resolution')
        trainable=next(e for e in events if e['kind']=='trainable_parameters')
        c.require(module['count']==len(spec['architecture']['resolved_modules']) and trainable['count']==spec['architecture']['adapter_parameters'] and trainable['lora_only'],'Structure proof mismatch')
        ordinary_steps=[e['step_wall_seconds'] for e in steps if e['step'] not in (1,spec['checkpoint_steps'][0]+1)]
        roles[role]=dict(status=status['status'],optimizer_steps=status['optimizer_steps'],
            load_seconds=sum(e['seconds'] for e in events if e['kind']=='model_load'),
            total_role_wall_seconds=status['seconds'],dev_generation_seconds=sum(v['generation_seconds'] for v in summaries),
            non_generation_role_wall_seconds=status['seconds']-sum(v['generation_seconds'] for v in summaries),
            ordinary_training_step_wall_median=statistics.median(ordinary_steps),
            ordinary_step_definition='excludes first step initialization and step immediately after DEV; those intervals contain non-training work',
            optimizer_call_seconds=sum(e['optimizer_seconds'] for e in steps),
            loss_start=loss[0]['mean_loss'],loss_end=loss[-1]['mean_loss'],loss_entries=len(loss),
            source_train_examples=sum(v['examples'] for v in loss),
            module_count=module['count'],trainable_parameters=trainable['count'],lora_only=True,
            peak_allocated_vram_gib=status['peak_allocated_vram_bytes']/2**30,
            peak_reserved_vram_gib=status['peak_reserved_vram_bytes']/2**30,
            nvidia_peak_memory_mib=max(float(v['gpu'].split(',')[1]) for v in samples if v['gpu']),
            gpu_utilization_mean=mean([float(v['gpu'].split(',')[0]) for v in samples if v['gpu']]),
            gpu_utilization_max=max(float(v['gpu'].split(',')[0]) for v in samples if v['gpu']),
            peak_process_rss_gib=max(v['rss'] for v in samples)/2**30,
            peak_host_ram_used_gib=max(v['host_ram_used'] for v in samples)/2**30,
            cpu_percent_mean=mean([v['cpu_percent'] for v in samples]),cpu_percent_max=max(v['cpu_percent'] for v in samples),
            telemetry_samples=len(samples),checkpoints=summaries,
            selected_step=selected['step'] if selected else None,selected_adapter_sha256=selected['identity']['sha256'] if selected else None,
            tuning_signal='INDETERMINATE')
    c.require(not (DATA/'runs/first-domain-agnostic-tuning-v1/PROTECTED_ACCESS_CONSUMED.json').exists(),'Unexpected protected access')
    c.require(not (OUT/'protected_control.zip').exists(),'Unexpected protected transfer')
    termination=c.read(OUT/'TERMINATION_VERIFIED.json')
    summary=dict(status='FIRST_TUNING_EXPERIMENT_COMPLETED',roles=roles,protected_admitted=False,
        protected_receipt_consumed=False,protected_population_registered=114,protected_population_executed=0,
        protected_metrics=None,protected_R06=None,protected_acceptance_criteria='NOT_MEASURED; 27 criteria unchanged, human criteria pending/zero',
        producer_signal='INDETERMINATE',auditor_signal='INDETERMINATE',BALANCED_TUNING_FOLLOWUP_RECOMMENDED=False,
        rationale='Both bounded training plans and DEV evaluations completed. Producer has no contract-perfect checkpoint; protected evaluation was therefore not permitted. No BASE/tuned protected comparison exists.',
        human_review_status='FIRST_TUNING_EXPERIMENT_HUMAN_REVIEW_STATUS=PENDING',human_reviews=0,
        billable_seconds_upper_bound=termination['billable_duration_upper_bound_seconds'],cost_usd_upper_bound=termination['estimated_cost_upper_bound_usd'],
        instance_count=1,provider_confirmed_terminated=True,remaining_instances=0,
        no_second_instance=True,no_paid_inference=True,model_pin_quantization_changes=False,
        hyperparameter_changes=False,post_protected_training=False,full_pipeline=False,multi_round=False,push=False)
    c.write(OUT/'RECOMPUTED_RESULTS.json',summary)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':analyze()
