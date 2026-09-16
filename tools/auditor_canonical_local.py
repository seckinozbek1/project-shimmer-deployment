"""Auditor-only canonical no-model verification and prospective execution binding."""
import ast
from collections import Counter
import hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'tuning/second_domain_agnostic_v2'
DEST=ROOT/'tuning/auditor_canonical_execution'
BASE=ROOT/'docs/fix/auditor_canonical_tuning_run'
os.environ.update(USE_TORCH='0',USE_TF='0',USE_FLAX='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
sys.path.insert(0,str(SOURCE))
import runtime as r
import runner
from cloud_run_common import credential_locations,write_json
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):write_json(p,v)

def verify_history():
    proc=subprocess.run([sys.executable,'-B',str(ROOT/'tuning/producer_v3/release.py')],capture_output=True,check=True)
    assert not credential_locations(proc.stdout+proc.stderr,'preservation')
    (BASE/'historical_preservation.log').write_bytes(proc.stdout+proc.stderr)
    freeze=read(SOURCE/'freeze.json')
    metadata=read(ROOT/'tuning/producer_v3/historical_preservation.json')['metadata_only']
    for section in ('files','dependency_files'):
        for name,expected in freeze[section].items():
            p=ROOT/name
            if 'protected' in p.name.lower():
                entry=metadata[name.replace('\\','/')];st=p.stat()
                assert st.st_size==entry['size'] and st.st_mtime_ns==entry['mtime_ns']
            else:assert sha(p)==expected,name
    assert sha(SOURCE/'freeze.json')=='bb27d49234fcc30cf02438ac0ce1c43dc690cf514aa9ebbe8d4ae4f6341aa78d'
    # Producer V3 result text and local binaries are immutable evidence. Hash
    # text and check binary metadata only; never load the Producer checkpoint.
    prior=ROOT/'docs/fix/producer_tuning_v3_run'
    m=read(prior/'EVIDENCE_MANIFEST.json')
    for name,entry in m['text_files'].items():assert sha(ROOT/name)==entry['sha256'],name
    for name,entry in m['local_only_binaries'].items():assert (ROOT/name).stat().st_size==entry['bytes'],name
    return dict(v2_release_sha256=sha(SOURCE/'freeze.json'),producer_text_files_verified=len(m['text_files']),producer_binary_sizes_verified=len(m['local_only_binaries']),protected_metadata_only=True)

def build():
    DEST.mkdir(exist_ok=True);BASE.mkdir(exist_ok=True)
    assert not (BASE/'LAUNCH_INTENT.json').exists(),'Authorization already consumed'
    history=verify_history();all_rows=read(SOURCE/'dataset.json');rows=[x for x in all_rows if x['role']=='auditor']
    spec=read(SOURCE/'auditor/experiment.json');source_split=read(SOURCE/'splits.json')['canonical']
    assert spec['model_id']=='unsloth/Phi-3.5-mini-instruct-bnb-4bit' and spec['revision']=='5c20803aa197416f43fb455e55c85178775320cb'
    assert spec['dataset_sha256']==sha(SOURCE/'dataset.json')=='0e7532aa9cbca8cffad99faae03656cbbdb0dbf3fc489b18d142b5a000dfbc12'
    assert spec['training']['max_steps']==120 and spec['checkpoint_steps']==[60,120] and spec['generation']['max_new_tokens']==192
    expected=dict(minimum=dict(contract_validity=1.,refusal_precision=.9,refusal_recall=.8,substantive_non_refusal_coverage=.9,accepted_semantic_outcomes=.7,macro_relation_f1=.75,evidence_f1=.85),maximum=dict(over_refusal_rate=.05),per_class_recall={c:.6 for c in r.CLASSES})
    assert spec['selection_gates']==expected
    assert spec['lora']==dict(r=8,lora_alpha=16,lora_dropout=.05,bias='none',task_type='CAUSAL_LM',target_modules=list(r.old.MODULES))
    plan=runner.plan('auditor','canonical',all_rows)
    split=dict(train=plan['train_ids'],validation=plan['validation_ids'])
    assert len(rows)==sum(x['substantive'] for x in rows)==300
    balance={name:dict(Counter(x['relation'] for x in rows if name=='all' or x['example_id'] in split[name])) for name in ('all','train','validation')}
    for name,n in (('all',60),('train',48),('validation',12)):assert balance[name]=={c:n for c in r.CLASSES}
    leakage=r.check_split(rows,split)
    assert Counter(i for u in plan['optimizer_schedule'] for i in u['example_ids'])==Counter({i:2 for i in split['train']})
    tok=r.old.tokenizer('auditor');encoded={x['example_id']:r.encode(x,tok) for x in rows}
    assert all(len(e['input_ids'])<=1056 and e['target_length']<=192 and all(v==-100 for v in e['labels'][:e['prompt_length']]) for e in encoded.values())
    assert all(r.contract(x,r.target(x)) for x in rows)
    oracle=r.aggregate([r.score(x,r.old.canonical(r.target(x)).decode()) for x in rows])
    collapse=r.aggregate([r.score(x,'{"items":[],"status":"refused"}') for x in rows])
    assert r.selection_pass(oracle,expected) and not r.selection_pass(collapse,expected)
    invalid=dict(oracle,macro_relation_f1=float('nan'));assert not r.selection_pass(invalid,expected)
    by={x['example_id']:x for x in rows};records=[]
    for i in split['validation']:
        prompt=tok.apply_chat_template(r.task_messages(by[i]),tokenize=False,add_generation_prompt=True)
        ids=tok.apply_chat_template(r.task_messages(by[i]),tokenize=True,add_generation_prompt=True)
        assert tok(prompt,add_special_tokens=False)['input_ids']==ids
        records.append(dict(example_id=i,role='auditor',split='canonical',prompt=prompt,input_ids=ids,attention_mask=[1]*len(ids)))
    controls=[next(i for i in split['validation'] if by[i]['relation']==c) for c in r.CLASSES]
    protocol=dict(dev_ids=split['validation'],control_ids=controls,control_rule='First canonical DEV ID of each frozen relation class in class order; two optimized passes per checkpoint, exact prompt/token/decoded/semantic/stop identity. No historical Auditor controls existed.',
        prompt_bindings={x['example_id']:dict(prompt_sha256=hashlib.sha256(x['prompt'].encode()).hexdigest(),input_ids_sha256=r.sha(x['input_ids'])) for x in records},
        generation_kwargs=dict(spec['generation'],eos_token_id=spec['terminal_token_ids'],pad_token_id=tok.pad_token_id),
        minimum_planning_tokens_per_second=6.,speed_policy='No inherited Producer speed/ratio quality gate. Positive finite timing and measured remaining-work budget admission are required.',
        runtime='auditor-canonical-scoped-v1',raw_before_score=True,controls_per_pass=5,total_generation_calls=144)
    rules=read(SOURCE/'selection_rules.json');assert rules['auditor_ranking']==['macro_relation_f1','accepted_semantic_outcomes','earliest_step','adapter_hash']
    for name,value in [('dataset.json',rows),('split.json',split),('experiment.json',spec),('execution_plan.json',plan),('prepared_dev.json',records),('evaluation_protocol.json',protocol),('selection_rules.json',dict(gates=expected,catastrophic_zero_limits=rules['catastrophic_zero_limits'],ranking=rules['auditor_ranking']))]:
        write(DEST/name,value)
    binding=dict(source_release_sha256=sha(SOURCE/'freeze.json'),source_dataset_sha256=sha(SOURCE/'dataset.json'),source_splits_sha256=sha(SOURCE/'splits.json'),source_config_sha256=sha(SOURCE/'auditor/experiment.json'),
        export_sha256=sha(DEST/'dataset.json'),rows_unchanged=True,row_hashes={x['example_id']:r.sha(x) for x in rows},canonical_only=True,producer_rows=0)
    write(DEST/'source_binding.json',binding)
    files={p.relative_to(ROOT).as_posix():sha(p) for p in DEST.iterdir() if p.is_file() and p.name!='freeze.json'}
    write(DEST/'freeze.json',dict(name='auditor-canonical-execution-v1',source_release_sha256=binding['source_release_sha256'],files=files,new_data=False,new_quality_gates=False,controls_bound_before_launch=True))
    report=dict(passed=True,history=history,balance=balance,train=240,dev=60,updates=120,checkpoints=[60,120],tokenizations=300,max_sequence=max(len(e['input_ids']) for e in encoded.values()),max_target=max(e['target_length'] for e in encoded.values()),leakage=leakage,oracle_passed=True,refusal_collapse_rejected=True,nonfinite_rejected=True,producer_execution=False,protected_access=False,folds_1_to_4_executed=False,freeze_sha256=sha(DEST/'freeze.json'))
    write(BASE/'local_auditor_checks.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('leakage','history')},indent=2))

if __name__=='__main__':build()
