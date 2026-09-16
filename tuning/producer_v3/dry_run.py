"""Offline tokenizer/label/schedule validation. Cannot load or train a model."""
from local_common import *
from copy import deepcopy
import math
import random
import statistics
import ast
from runtime_binding import prepare,prepare_checkpoint_plan,verify_runtime,RUNTIME

def distribution(values):
    v=sorted(values)
    def q(p):
        x=(len(v)-1)*p;lo=math.floor(x);hi=math.ceil(x)
        return v[lo]*(hi-x)+v[hi]*(x-lo) if hi!=lo else v[lo]
    return dict(n=len(v),min=min(v),median=statistics.median(v),mean=statistics.mean(v),p95=q(.95),max=max(v))

def signatures(row):
    return sorted({canonical({k:a[k] for k in ('kind','category','subject','attribute','ordinal','relation','state','scope','unit')})
        for i in row['typed_label']['items'] for a in i['gap_atoms']+i['uncertainty_atoms']})

def validate_review(rows):
    path=HERE/'blind_review/fresh_review.json'
    if not path.exists():return dict(passed=False,reason='Fresh input-only machine review pending')
    review=read(path);mapping=read(HERE/'review_mapping.json');by={r['example_id']:r for r in rows}
    assert review['input_sha256']==sha(HERE/'blind_review/packets.json'),'Stale review'
    reviewed=review['reviews']
    assert len(reviewed)==120 and {r['example_id'] for r in reviewed}==set(mapping)
    differences=[]
    for r in reviewed:
        gold=by[mapping[r['example_id']]];lab=gold['typed_label']
        expected='refused' if lab['status']=='refused' else 'extracted'
        if r['predicted_status']!=expected:differences.append(dict(id=gold['example_id'],field='status'));continue
        if expected=='refused':continue
        actual=[];predicted=[]
        for item in lab['items']:
            actual.append(dict(span=item['span'],claims=sorted(item['claims']),refs=sorted(item['refs']),
                atoms=sorted(canonical(v2.sem.normalize(a)) for a in item['gap_atoms']+item['uncertainty_atoms'])))
        for item in r['items']:
            predicted.append(dict(span=item['span'],claims=sorted(item['claims']),refs=sorted(item['refs']),
                atoms=sorted(canonical(v2.sem.normalize(a)) for a in item['atoms'])))
        if actual!=predicted:differences.append(dict(id=gold['example_id'],field='owned claims/refs/atoms',actual=actual,predicted=predicted))
    return dict(passed=not differences,rows=120,differences=differences,review_sha256=sha(path),
        human_reviewed=False,independent_final_benchmark=False,method='Fresh input-only agent, opaque IDs, independently specified clause mapping; shared ontology, shared filesystem, no OS isolation claim')

def run():
    write(HERE/'dry_run_evidence.json',dict(passed=False,status='RUNNING_OR_INCOMPLETE',dataset_sha256=sha(HERE/'dataset.json')))
    rows=read(HERE/'dataset.json');new=read(HERE/'augmentation.json');split=read(HERE/'split.json')
    base=[x for x in read(ROOT/'tuning/second_domain_agnostic_v2/dataset.json') if x['role']=='producer']
    assert rows[:len(base)]==base and rows[len(base):]==new
    assert len(rows)==420 and len(new)==120 and all(x['role']=='producer' for x in rows)
    stats=v2.check_split(rows,split)
    assert (len(split['train']),len(split['validation']))==(336,84)
    by={x['example_id']:x for x in rows}
    sigs=[canonical(signatures(x)) for x in rows if x['substantive']]
    assert len(sigs)==360 and len(set(sigs))==360,'Semantic duplicates after removing layout/names/refs/claims'
    oldsplit=read(ROOT/'tuning/second_domain_agnostic_v2/splits.json')['canonical']
    for part in ('train','validation'):
        assert {x['example_id'] for x in base if x['example_id'] in split[part]}=={x['example_id'] for x in base if x['example_id'] in oldsplit[part]}
    for x in new:
        assert v2.sem.validate_label(x['typed_label'],x['input'])==x['canonical_target']
        assert v2.contract(x,x['canonical_target'])
    # Positive oracle checks are only new-label internal consistency, never V2 rescoring.
    new_scores=[v2.score(x,v2.old.canonical(x['canonical_target']).decode()) for x in new]
    assert all(x['accepted_outcome'] for x in new_scores)
    token=v2.old.tokenizer('producer');encoded={x['example_id']:v2.encode(x,token) for x in rows}
    tokstats=[]
    for x in rows:
        e=encoded[x['example_id']]
        assert all(v==-100 for v in e['labels'][:e['prompt_length']])
        assert e['labels'][e['prompt_length']:]==e['input_ids'][e['prompt_length']:]
        assert e['labels'].count(token.eos_token_id)==1
        tokstats.append(dict(example_id=x['example_id'],prompt=e['prompt_length'],target=e['target_length'],sequence=len(e['input_ids']),refused=v2.refused(x['canonical_target']),substantive=x['substantive']))
    spec=deepcopy(read(ROOT/'tuning/second_domain_agnostic_v2/producer/experiment.json'))
    spec.update(experiment='producer-targeted-v3',dataset_version='producer-targeted-v3.0',dataset_sha256=sha(HERE/'dataset.json'),
        split_sha256=sha(HERE/'split.json'),train_count=336,dev_count=84,checkpoint_steps=[84,168],
        initialization='Fresh rank-8 adapter on the exact pinned base; no V2 adapter continuation',
        evaluation_runtime='second-tuning-eval-runtime-v2_1',evaluation_runtime_sha256=verify_runtime(),
        configuration_reason='DATA-ONLY: retain all optimization/objective/generation settings. Two full passes scale 120 to168 updates with 336 TRAIN rows; full DEV at each pass preserves collapse/overfit comparison. No LR/rank/weighting sweep.',
        final_stop_rule='If no complete V3 checkpoint passes every frozen gate, stop Producer LoRA branch; no automatic V4. Return to architecture/model choice under separate authorization.',
        training_authorized=False,execution_mode='dry_run_only',tokenizer_only=True)
    spec['training'].update(steps_per_epoch=84,max_steps=168,last_accumulation_group='actual group mean; 336 examples divide evenly into groups of four')
    assert max(x['sequence'] for x in tokstats)<=spec['max_seq_length'],('sequence cap',max(x['sequence'] for x in tokstats))
    assert max(x['target'] for x in tokstats)<=spec['generation']['max_new_tokens'],('generation cap',max(x['target'] for x in tokstats))
    assert spec['selection_gates']==read(ROOT/'tuning/second_domain_agnostic_v2/producer/experiment.json')['selection_gates']
    schedule=[]
    for epoch in range(2):
        ids=list(split['train']);random.Random(7+epoch).shuffle(ids)
        for start in range(0,len(ids),4):schedule.append(dict(step=len(schedule)+1,epoch=epoch+1,example_ids=ids[start:start+4],loss_divisor=4))
    assert len(schedule)==168 and Counter(i for s in schedule for i in s['example_ids'])==Counter({i:2 for i in split['train']})
    assert not set(split['validation'])&{i for s in schedule for i in s['example_ids']}
    records,protocol=prepare(rows,split,token)
    # No fake or real generation: tests exercise only state restoration and bindings.
    from types import SimpleNamespace
    from contextlib import contextmanager
    from runtime_binding import runtime
    class StateOnlyModel:
        def __init__(self):
            self.training=True;self.gradient_checkpointing=True;self._gradient_checkpointing_func=object()
            self.config=SimpleNamespace(use_cache=False);self.generation_config=None;self.active_adapters=['default']
            self.p=SimpleNamespace(dtype='float32',device='cpu',requires_grad=True,_version=0,grad=None)
        def modules(self):return [self]
        def parameters(self):return [self.p]
        def eval(self):self.training=False;return self
        def generate(self,*a,**kw):raise AssertionError('Generation forbidden in this dry-run')
    class StateOnlyTorch:
        @staticmethod
        def is_grad_enabled():return False
        @staticmethod
        @contextmanager
        def inference_mode():yield
    model=StateOnlyModel();receipt=runtime.real_runtime_context_preflight(model,StateOnlyTorch)
    assert receipt['passed'] and receipt['state_restored'] and model.training and model.generation_config is None
    # Fault injections test meaningful leakage/label/config/boundary failure modes.
    faults=[]
    def reject(name,fn):
        try:fn()
        except (ValueError,AssertionError,PermissionError):faults.append(name);return
        raise AssertionError('Accepted invalid fixture: '+name)
    bad=deepcopy(split);bad['train'].append(bad['validation'][0]);reject('DEV gradient contamination',lambda:v2.check_split(rows,bad))
    badrecords=deepcopy(records);badrecords[0]['input_ids'][0]+=1;reject('prompt-token mutation',lambda:runtime.validate_records(badrecords,protocol))
    badsettings=deepcopy(protocol['generation_kwargs']);badsettings['max_new_tokens']=287;reject('generation-cap mutation',lambda:runtime.validate_generation(badsettings,protocol))
    badlabel=deepcopy(next(x for x in new if x['substantive']));badlabel['typed_label']['items'][0]['gap_atoms'].pop();reject('single-atom omission',lambda:v2.sem.validate_label(badlabel['typed_label'],badlabel['input']))
    reject('model weight read',lambda:Path('blocked.safetensors').read_bytes())
    reject('benchmark data read',lambda:(ROOT/'benchmark/forbidden.json').read_bytes())
    reject('network',lambda:__import__('socket').getaddrinfo('example.invalid',443))
    from selection import passes,select,CATASTROPHIC
    fixture={k:1.0 for k in spec['selection_gates']['minimum']};fixture.update(count=84,over_refusal_rate=0.,catastrophic={k:0 for k in CATASTROPHIC})
    assert passes(fixture,spec['selection_gates'])
    for key in spec['selection_gates']['minimum']:
        bad=deepcopy(fixture);bad[key]=spec['selection_gates']['minimum'][key]-.0001
        assert not passes(bad,spec['selection_gates'])
    for key in ('typed_gaps_f1','semantic_completeness'):
        for invalid in (None,float('nan'),float('inf')):
            bad=deepcopy(fixture);bad[key]=invalid;assert not passes(bad,spec['selection_gates'])
    for key in CATASTROPHIC:
        bad=deepcopy(fixture);bad['catastrophic'][key]=1;assert not passes(bad,spec['selection_gates'])
    bad=deepcopy(fixture);bad['over_refusal_rate']=.050001;assert not passes(bad,spec['selection_gates'])
    reject('incomplete checkpoint selection',lambda:select([],spec))
    from runtime_binding import V3RawSink,optimized_control_gate
    adapter=dict(experiment='producer-targeted-v3',step=84,files={'adapter_config.json':'1'*64,'adapter_model.safetensors':'2'*64})
    sink=[];bound=V3RawSink(sink,84,adapter,records)
    example=dict(example_id=records[0]['example_id'],adapter=adapter,runtime='second-tuning-eval-runtime-v2_1',checkpoint=120,
                 **protocol['prompt_bindings'][records[0]['example_id']])
    bound.append(example);assert sink[0]['checkpoint']==84 and sink[0]['input_ids']==records[0]['input_ids']
    reject('duplicate raw persistence',lambda:bound.append(example))
    # Handwritten sentinel records exercise controls only; these are not generated outputs.
    controls=[dict(example_id=i,adapter=adapter,checkpoint=84,runtime='second-tuning-eval-runtime-v2_1',
        output_token_ids=[151645],raw_output='',raw_output_with_special_tokens='<sentinel>',metrics={},stop_reason='eos',generation_seconds=.1,
        **protocol['prompt_bindings'][i]) for i in protocol['control_ids']]
    assert optimized_control_gate(controls,deepcopy(controls),protocol,adapter,84)['pass_gate']
    bad=deepcopy(controls);bad[0]['output_token_ids']=[1];reject('control token mismatch',lambda:optimized_control_gate(controls,bad,protocol,adapter,84))
    assert 'torch' not in sys.modules
    # Saved training event timer includes an untrustworthy first-step warmup and
    # checkpoint evaluation in step61; use epoch timestamps for robust steady-state.
    events=read(ROOT/'docs/fix/second_tuning_canonical_pilot/downloaded/evidence/producer_events.json')
    steps=[x for x in events if x['kind']=='optimizer_step']
    intervals=[b['epoch']-a['epoch'] for a,b in zip(steps,steps[1:]) if b['step']!=61]
    measured=distribution(intervals)
    oldtrain=[encoded[x['example_id']] for x in base if x['example_id'] in split['train']]
    ratio=statistics.mean(len(encoded[i]['input_ids']) for i in split['train'])/statistics.mean(len(x['input_ids']) for x in oldtrain)
    throughput=read(ROOT/'docs/fix/producer_checkpoint120_eval_v2_1/RECOMPUTED_RESULTS.json')['full_dev']['tokens_per_second']
    devtargets=[encoded[i]['target_length'] for i in split['validation']]
    controltokens=sum(encoded[i]['target_length'] for i in protocol['control_ids'])*4  # 2 passes x2 checkpoints
    train_seconds=168*measured['median']*ratio
    eval_seconds=(2*sum(devtargets)+controltokens+4*288)/throughput
    projection=dict(label='PROJECTION, not a current quote or measured V3 runtime',historical_training_step_seconds=measured,
        sequence_length_ratio=ratio,training_seconds=train_seconds,dev_rows=84,full_dev_generations=168,control_generations=24,cache_probe_upper_bound_generations=4,
        expected_dev_target_tokens=distribution(devtargets),observed_v21_full_rate=throughput,
        evaluation_seconds=eval_seconds,setup_and_teardown_reserve_seconds=900,
        total_seconds=train_seconds+eval_seconds+900,total_cost_at_historical_1_29_per_hour=(train_seconds+eval_seconds+900)*1.29/3600,
        conservative_seconds=168*measured['p95']*max(1,ratio)+196*288/protocol['minimum_prefill_inclusive_tokens_per_second']+900,
        assumptions='Historical A10 rate only; sequence-linear training proxy, target-token lengths as output proxy; all generations cap-limited in conservative bound. Re-query pricing/capacity/budget before any separately authorized run.')
    projection['conservative_cost_at_historical_1_29_per_hour']=projection['conservative_seconds']*1.29/3600
    review=validate_review(new)
    write(HERE/'experiment.json',spec);write(HERE/'prepared_dev.json',records);write(HERE/'evaluation_protocol.json',protocol)
    write(HERE/'execution_plan.json',dict(optimizer_schedule=schedule,checkpoints=[prepare_checkpoint_plan(s,spec,protocol) for s in spec['checkpoint_steps']],training_authorized=False,model_execution_performed=False))
    write(HERE/'token_analysis.json',dict(rows=tokstats,all_targets=distribution(x['target'] for x in tokstats),
        refusal_targets=distribution(x['target'] for x in tokstats if x['refused']),substantive_targets=distribution(x['target'] for x in tokstats if x['substantive']),
        max_sequence=max(x['sequence'] for x in tokstats),no_truncation=True))
    write(HERE/'statistics.json',dict(total=v2.stats(rows)['producer'],augmentation=v2.stats(new)['producer'],split=stats))
    write(HERE/'projection.json',projection);write(HERE/'review_adjudication.json',review)
    write(HERE/'dry_run_evidence.json',dict(passed=review['passed'],dataset_sha256=sha(HERE/'dataset.json'),data_and_schedule_checks_passed=True,label_review_passed=review['passed'],
        rows_tokenized=420,train=336,dev=84,updates_planned=168,model_generations=0,training_steps_executed=0,weight_reads=0,network_calls_succeeded=0,
        protected_data_reads=0,auditor_execution=0,context_state_only_preflight=receipt,fault_injections_rejected=faults,
        no_historical_rescoring=True,old_rows_preserved=True,old_split_preserved=True,semantic_signature_duplicates=0))
    print(json.dumps(dict(review=review['passed'],max_sequence=max(x['sequence'] for x in tokstats),max_target=max(x['target'] for x in tokstats),projection=projection),indent=2))

if __name__=='__main__':run()
