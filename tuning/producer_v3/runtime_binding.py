"""Local V3 binding to unchanged V2.1 mechanisms; no model executor."""
from local_common import *
RUNTIME = ROOT/'tuning/second_tuning_eval_runtime_v2_1'
RUNTIME_SHA = '8d1fd41d1ab059e47b1297c1c39cd29711acd8fa5446a60780f9a97faef1d1fa'
sys.path.insert(0,str(RUNTIME))
import eval_runtime as runtime

def verify_runtime():
    assert sha(RUNTIME/'freeze.json')==RUNTIME_SHA
    freeze=read(RUNTIME/'freeze.json')
    # Pure code dependencies are pinned separately in the V3 freeze as well.
    for section in ('files','dependency_files'):
        for name,expected in freeze.get(section,{}).items():
            p=ROOT/name
            if p.suffix=='.py':assert sha(p)==expected,name
    return RUNTIME_SHA

def prepare(rows, split, tok):
    by={r['example_id']:r for r in rows};records=[]
    for identifier in split['validation']:
        row=by[identifier];messages=v2.task_messages(row)
        prompt=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
        ids=tok.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)
        assert tok(prompt,add_special_tokens=False)['input_ids']==ids
        records.append(dict(example_id=identifier,role='producer',split='canonical',prompt=prompt,input_ids=ids,attention_mask=[1]*len(ids)))
    historical=read(RUNTIME/'protocol.json')
    protocol=dict(experiment='producer-targeted-v3',runtime_release_sha256=verify_runtime(),dev_ids=split['validation'],
        control_ids=[records[i]['example_id'] for i in (0,14,28,42,56,70)],
        prompt_bindings={r['example_id']:dict(prompt_sha256=hashlib.sha256(r['prompt'].encode()).hexdigest(),input_ids_sha256=runtime.digest(r['input_ids'])) for r in records},
        generation_kwargs=historical['generation_kwargs'],
        minimum_prefill_inclusive_tokens_per_second=historical['speed_gate']['minimum_tokens_per_second'],
        required_stages=['verified checkpoint identity','context preflight without generation','cache probe first two forwards',
            'six fixed optimized duplicate controls with exact token/decoded/semantic/stop identity','full fresh 84-row DEV'],
        control_policy='Two optimized passes per checkpoint, no observer tracing. Historical 4.6299x observer-removal proof is preserved, not redundantly remeasured.',
        context_function='eval_runtime.real_runtime_context_preflight',state_function='eval_runtime.evaluation_state',
        generation_function='eval_runtime.evaluate_records',cache_probe_function='eval_runtime.cache_probe',
        raw_before_score=True,telemetry='separate-process, only in separately authorized future execution',
        adapter_binding='Future fresh V3 adapter hashes must bind each checkpoint; the V2 checkpoint120 adapter is never a V3 initializer.',
        executor_status='NOT_IMPLEMENTED_OR_AUTHORIZED: this release is a local design and dry-run only',
        legacy_harness_constraints='V2.1 EvaluationSession/authorize/control_gate bind checkpoint120 and 60 rows. Do not reuse that harness for V3.',
        required_future_metadata_adapter='Use V3RawSink before persistence to replace legacy checkpoint=120 with actual V3 step (84 or168), attach fresh adapter hashes and exact prompt/IDs; verify 84 rows. No change to generation mechanism.',
        no_go='Stop on context/cache/control/speed/identity failure; no retry/resume, preserve evidence and terminate.')
    runtime.validate_records(records,protocol);runtime.validate_generation(protocol['generation_kwargs'],protocol)
    return records,protocol

class V3RawSink:
    """Metadata-only adapter around frozen low-level persistence; never generates."""
    def __init__(self, sink, step, adapter, records):
        assert step in (84,168) and adapter['experiment']=='producer-targeted-v3' and adapter['step']==step
        assert set(adapter['files'])=={'adapter_config.json','adapter_model.safetensors'}
        assert all(len(h)==64 and all(c in '0123456789abcdef' for c in h) for h in adapter['files'].values())
        self.sink,self.step,self.adapter,self.records=sink,step,adapter,{r['example_id']:r for r in records}
        self.written=set()
    def append(self, evidence):
        assert 'metrics' not in evidence,'Raw persistence must precede scoring'
        identifier=evidence['example_id'];assert identifier not in self.written
        row=self.records[identifier]
        assert evidence['adapter']==self.adapter and evidence['runtime']=='second-tuning-eval-runtime-v2_1'
        assert evidence['prompt_sha256']==hashlib.sha256(row['prompt'].encode()).hexdigest()
        assert evidence['input_ids_sha256']==runtime.digest(row['input_ids'])
        evidence.update(checkpoint=self.step,experiment='producer-targeted-v3',prompt=row['prompt'],input_ids=row['input_ids'],attention_mask=row['attention_mask'])
        self.sink.append(evidence);self.written.add(identifier)

def optimized_control_gate(first,second,protocol,adapter,step):
    """V3 controls: duplicate optimized runs; no tracing/observer reintroduction."""
    import math
    expected=protocol['control_ids']
    assert [r['example_id'] for r in first]==[r['example_id'] for r in second]==expected
    for a,b in zip(first,second):
        for row in (a,b):
            assert row['checkpoint']==step and row['adapter']==adapter
            assert row['runtime']=='second-tuning-eval-runtime-v2_1'
            for k in ('prompt_sha256','input_ids_sha256'):assert row[k]==protocol['prompt_bindings'][row['example_id']][k]
            assert math.isfinite(row['generation_seconds']) and row['generation_seconds']>0
        for k in ('output_token_ids','raw_output','raw_output_with_special_tokens','metrics','stop_reason'):assert a[k]==b[k]
    rate=sum(len(r['output_token_ids']) for r in first+second)/sum(r['generation_seconds'] for r in first+second)
    assert rate>=protocol['minimum_prefill_inclusive_tokens_per_second']
    return dict(pass_gate=True,token_identity=6,semantic_identity=6,tokens_per_second=rate,reference_speedup_remeasured=False)

def prepare_checkpoint_plan(step, spec, protocol):
    assert step in spec['checkpoint_steps']
    assert len(protocol['dev_ids'])==spec['dev_count']
    return dict(checkpoint=step,dev_ids=protocol['dev_ids'],control_ids=protocol['control_ids'],
                generation_kwargs=protocol['generation_kwargs'],context_function=protocol['context_function'],
                evaluation_state_function=protocol['state_function'],stages=protocol['required_stages'],
                model_execution_authorized=False)
