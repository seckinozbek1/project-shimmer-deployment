"""No-model integration and counterfactual gate proofs with real tokenizers."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_TORCH='0',USE_TF='0',USE_FLAX='0')
import copy
from contextlib import nullcontext
import json
from pathlib import Path
import sys
import tempfile
import types
import subprocess
import zipfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
from common import *
import evaluation as ev
import bundle
import train
import protected_eval

CHECKS=[]
EFFECTS=[]
ACCESS={'protected_target_reads':0,'model_weight_reads':0,'network_calls':0}

def access_guard(event,args):
    if event in ('socket.connect','socket.getaddrinfo'):
        ACCESS['network_calls']+=1
        raise PermissionError('Dry-run network access forbidden')
    if event=='open' and isinstance(args[0],(str,bytes)):
        p=Path(os.fsdecode(args[0])).resolve()
        n=p.as_posix().lower()
        forbidden=('/task_semantics/seed.json','/task_semantics_v2/extension.json',
                   '/legacy_comparison.json','/review_admin_mapping.json','/shimmer_handoff.md')
        if any(n.endswith(x) for x in forbidden) or '/durable/' in n:
            ACCESS['protected_target_reads']+=1
            raise PermissionError('Protected/private read forbidden in dry-run')
        if p.name.endswith(('.safetensors','.bin','.pt','.pth')) and 'synthetic-' not in n:
            ACCESS['model_weight_reads']+=1
            raise PermissionError('Real model weights forbidden in dry-run')

def check(name,fn):
    fn();CHECKS.append(name)

def denies(fn):
    try:fn()
    except (ValueError,PermissionError,FileNotFoundError):return
    raise AssertionError('Guard did not reject forbidden action')

def effect(name,proof,mutation):
    proof()
    failed=False
    with mutation:
        try:proof()
        except (AssertionError,ValueError):failed=True
    require(failed,'Neutralized effect did not fail: '+name)
    proof()
    EFFECTS.append(dict(name=name,neutralized='FAIL',restored='PASS'))

def suppress(message):
    original=c.require
    return patch.object(c,'require',side_effect=lambda value,msg:None if msg==message else original(value,msg))

def synthetic_train(role,tok,temp):
    """Execute the real bounded orchestration with inert optimizer/model objects."""
    spec=read(HERE/role/'experiment.json');stats={'optimizer_steps':0,'forward_calls':0,'backward_calls':0,'saved':0}
    class Scalar:
        def __init__(self,n=1.):self.n=n
        def __truediv__(self,v):return Scalar(self.n/v)
        def backward(self):stats['backward_calls']+=1
        def detach(self):return self.n
        def item(self):return True
        def __float__(self):return self.n
    class Tensor:
        def to(self,device):return self
    class Param:
        requires_grad=True
        def numel(self):return spec['architecture']['adapter_parameters']
    class Model:
        device='synthetic';is_loaded_in_4bit=True
        config=types.SimpleNamespace(model_type=spec['architecture']['family'],use_cache=False,quantization_config=spec['quantization'])
        peft_config={'default':types.SimpleNamespace()}
        def named_modules(self):return [(n,types.SimpleNamespace(in_features=1,out_features=1)) for n in spec['architecture']['resolved_modules']]
        def named_parameters(self):return [('lora_mock',Param())]
        def train(self):return self
        def eval(self):return self
        def __call__(self,**kw):stats['forward_calls']+=1;return types.SimpleNamespace(loss=Scalar())
        def save_pretrained(self,path,**kw):
            stats['saved']+=1;Path(path).mkdir()
            write(Path(path)/'adapter_config.json',dict(base_model_name_or_path=PINS[role][0],revision=PINS[role][1]))
            (Path(path)/'adapter_model.safetensors').write_bytes(b'SYNTHETIC INERT ADAPTER; NOT MODEL WEIGHTS')
    class Optim:
        def __init__(self,*a,**kw):pass
        def zero_grad(self,**kw):pass
        def step(self):stats['optimizer_steps']+=1
    torch=types.SimpleNamespace(manual_seed=lambda _:None,cuda=types.SimpleNamespace(manual_seed_all=lambda _:None,
        get_device_name=lambda:'SYNTHETIC',max_memory_allocated=lambda:0),
        use_deterministic_algorithms=lambda _:None,backends=types.SimpleNamespace(cuda=types.SimpleNamespace(matmul=types.SimpleNamespace(allow_tf32=False))),
        bfloat16='bf16',long='int64',tensor=lambda *a,**kw:Tensor(),
        optim=types.SimpleNamespace(AdamW=Optim,lr_scheduler=types.SimpleNamespace(LambdaLR=lambda *a,**kw:types.SimpleNamespace(step=lambda:None))),
        autocast=lambda *a,**kw:nullcontext(),isfinite=lambda _:Scalar(),
        nn=types.SimpleNamespace(utils=types.SimpleNamespace(clip_grad_norm_=lambda *a:None)),
        __version__='SYNTHETIC',version=types.SimpleNamespace(cuda='SYNTHETIC'))
    fake_tf=types.SimpleNamespace(AutoModelForCausalLM=types.SimpleNamespace(from_pretrained=lambda *a,**kw:Model()))
    fake_peft=types.SimpleNamespace(LoraConfig=lambda **kw:kw,get_peft_model=lambda m,cfg:m,prepare_model_for_kbit_training=lambda m,**kw:m)
    fixtures={tok.apply_chat_template(messages(r),tokenize=False,add_generation_prompt=True):target(r) for r in load_rows(role,'dev')}
    def generator(*a):
        return lambda prompt:dict(raw_output=fixtures[prompt],input_tokens=1,output_tokens=1,
            latency_seconds=0.,stop_reason='synthetic_fixture',truncated=False,ttft_seconds=None)
    permit=temp/'permit.json'
    write(permit,dict(experiment=EXPERIMENT,action='train',roles=[role],operator_authorized=True,
        experiment_freeze_sha256=digest((HERE/'freeze.json').read_bytes()),synthetic_only=True))
    with patch.dict(sys.modules,{'torch':torch,'transformers':fake_tf,'peft':fake_peft}), \
         patch.object(train,'runtime',return_value=torch),patch.object(train,'ROOT',temp), \
         patch.object(train,'tokenizer',return_value=tok),patch.object(ev,'LocalGenerator',side_effect=generator), \
         patch.dict(os.environ,read(HERE/'experiment.json')['environment']):
        train.train(role,permit)
    require(stats['optimizer_steps']==spec['training']['max_steps'],'Synthetic orchestration step mismatch')
    require(stats['forward_calls']==2*len(load_rows(role,'train')),'Unexpected resampling')
    require(stats['saved']==len(spec['checkpoint_steps']),'Checkpoint schedule mismatch')
    root=temp/spec['output_directory'];ev.verify_selection(role,root)
    return dict(role=role,**stats,real_optimizer_updates=0,synthetic_only=True),root

def main():
    sys.addaudithook(access_guard)
    frozen()
    for p in HERE.glob('*.py'):compile(p.read_text(encoding='utf8'),str(p),'exec')
    tokenizers={r:tokenizer(r) for r in PINS}
    token_checks={};examples={}
    for role in PINS:
        tok=tokenizers[role];spec=read(HERE/role/'experiment.json');encoded=[]
        for split in ('train','dev'):
            rows=load_rows(role,split,gradient=split=='train')
            for row in rows:
                x=encode(row,tok,spec['max_seq_length']);encoded.append(x)
                require(all(v==-100 for v in x['labels'][:x['prompt_length']]),'Prompt loss leak')
                require(x['labels'][x['prompt_length']:]==x['input_ids'][x['prompt_length']:],'Target loss omitted')
                require(score_exact(row),'Exact canonical target does not score correctly')
        collator=TargetOnlyCollator(tok.pad_token_id,spec['max_seq_length'])
        batch=collator([encoded[0],max(encoded,key=lambda v:len(v['input_ids']))])
        require(all(a==1 or label==-100 for mask,labels in zip(batch['attention_mask'],batch['labels']) for a,label in zip(mask,labels)),'Padding loss leak')
        token_checks[role]=dict(rows=len(encoded),contract_valid=len(encoded),truncated=0,
            target_mask_pass=True,prompt_loss_tokens=0,terminal=encoded[0]['terminal'],
            max_seq_length=spec['max_seq_length'],max_observed=max(len(x['input_ids']) for x in encoded),
            sample_boundary=dict(prompt_tokens=encoded[0]['prompt_length'],
                prompt_tail=tok.decode(encoded[0]['input_ids'][encoded[0]['prompt_length']-8:encoded[0]['prompt_length']]),
                first_target_tokens=tok.decode(encoded[0]['input_ids'][encoded[0]['prompt_length']:encoded[0]['prompt_length']+8]),
                first_target_label=encoded[0]['labels'][encoded[0]['prompt_length']],
                preceding_prompt_label=encoded[0]['labels'][encoded[0]['prompt_length']-1]))
        examples[role]=encoded[0]
        CHECKS.extend([role+' target contracts / native templates / lengths / masks',role+' dynamic padding',role+' canonical scoring'])
    effect('DEV cannot enter gradient loader',lambda:denies(lambda:load_rows('producer','dev',gradient=True)),suppress('DEV/evaluation cannot enter gradient dataset'))
    row=copy.deepcopy(load_rows('producer','train')[0]);row['domain']='astronomy';hashes={row['example_id']:digest(row)}
    effect('held-out domain excluded',lambda:denies(lambda:validate_row(row,'producer','train',hashes)),suppress('Held-out domain'))
    collator=TargetOnlyCollator(tokenizers['producer'].pad_token_id,10000)
    x=copy.deepcopy(examples['producer']);x['labels'][x['prompt_length']]=-100
    effect('assistant target tokens trained',lambda:denies(lambda:collator([x])),suppress('Target-only mask mismatch'))
    x=copy.deepcopy(examples['producer']);x['labels'][0]=x['input_ids'][0]
    effect('prompt excluded from loss',lambda:denies(lambda:collator([x])),suppress('Target-only mask mismatch'))
    row=copy.deepcopy(load_rows('producer','train')[0]);row['role']='auditor';hashes={row['example_id']:digest(row)}
    effect('role separation',lambda:denies(lambda:validate_row(row,'producer','train',hashes)),suppress('Role/split contamination'))
    all_ids=[r['example_id'] for role in PINS for split in ('train','dev') for r in load_rows(role,split)]
    require(len(all_ids)==134 and len(set(all_ids))==134,'Cross-role/split overlap')
    require(read(HERE/'producer/experiment.json')['architecture']['family']!=read(HERE/'auditor/experiment.json')['architecture']['family'],'Family separation lost')
    CHECKS.append('exact disjoint 78 TRAIN / 56 DEV identities and model families')
    with tempfile.TemporaryDirectory(prefix='synthetic-',dir=HERE) as tmp:
        temp=Path(tmp)
        def protected_denied():
            reached=[]
            try:protected_eval.claim_access(temp,lambda:reached.append(True))
            except (ValueError,FileNotFoundError):pass
            require(not reached,'Protected source opened before selection freeze')
            marker=temp/'PROTECTED_ACCESS_CONSUMED.json'
            if marker.exists():marker.unlink()
        effect('protected read denied before selection freezes',protected_denied,patch.object(protected_eval,'verify_selection',return_value={}))
        path=temp/'adapter';path.mkdir()
        write(path/'adapter_config.json',dict(base_model_name_or_path=PINS['producer'][0],revision=PINS['producer'][1]))
        (path/'adapter_model.safetensors').write_bytes(b'SYNTHETIC')
        ident=adapter_identity(path,'producer',1);(path/'adapter_model.safetensors').write_bytes(b'SYNTHETIC CHANGED')
        effect('adapter identity binding',lambda:denies(lambda:verify_adapter(path,ident,'producer')),suppress('Adapter identity/hash mismatch'))
        effect('bundle rejects protected extras',lambda:denies(lambda:bundle.build(temp/'bad.zip',extra=['benchmark/task_semantics/seed.json'])),patch.object(bundle,'require',side_effect=lambda cond,msg:None if msg=='Additional bundle inputs forbidden' else c.require(cond,msg)))
        integrations=[];runs={}
        for role in PINS:
            result,path=synthetic_train(role,tokenizers[role],temp);integrations.append(result);runs[role]=path
            spec=read(HERE/role/'experiment.json');results=read(path/'checkpoint_results.json')
            require(ev.select(role,results,spec)['step']==spec['checkpoint_steps'][0],'Earliest tie break failed')
            altered=copy.deepcopy(results);altered[1]['metrics']['semantic_score']=2.
            altered[1]['metrics']['catastrophic_pass']=False
            require(ev.select(role,altered,spec)['step']==spec['checkpoint_steps'][0],'Catastrophic gate hidden by score')
            altered[1]['metrics']['catastrophic_pass']=True;altered[1]['metrics']['contract_rate']=.99
            require(ev.select(role,altered,spec)['step']==spec['checkpoint_steps'][0],'Contract gate hidden by score')
            CHECKS.append(role+' selection gates / earliest-step tie break')
        root=runs['producer'].parent
        reached=[];protected_eval.claim_access(root,lambda:reached.append(True))
        require(reached==[True],'Post-selection gate did not open')
        try:protected_eval.claim_access(root,lambda:reached.append(True))
        except FileExistsError:pass
        require(reached==[True],'Protected evaluation repeat allowed')
        CHECKS.extend(['synthetic producer training orchestration','synthetic auditor training orchestration',
            'checkpoint identity / DEV evidence rescore / freeze verification','protected one-shot consumption'])
        from contextlib import contextmanager
        state={'adapter':True};observed=[]
        @contextmanager
        def disabled():
            state['adapter']=False
            try:yield
            finally:state['adapter']=True
        for variant,ctx in ev.paired_variants(types.SimpleNamespace(disable_adapter=disabled)):
            with ctx:observed.append((variant,state['adapter']))
        require(observed==[('base',False),('tuned',True)],'BASE control did not disable adapter')
        CHECKS.append('same-model BASE/TUNED adapter toggle interface')
        check('missing authorization rejects before runtime',lambda:denies(lambda:train.authorization(None,'train')))
        check('unexpected module names fail closed',lambda:denies(lambda:train.validate_modules(types.SimpleNamespace(named_modules=lambda:[]),read(HERE/'producer/experiment.json'))))
        check('dataset mutation rejected',lambda:denies(lambda:validate_row(dict(load_rows('producer','train')[0],split='test'),'producer','train',read(HERE/'producer/dataset.json')['splits']['train']['row_hashes'])))
        archive=temp/'standalone.zip';bundle.build(archive)
        extracted=temp/'extracted';extracted.mkdir()
        with zipfile.ZipFile(archive) as z:z.extractall(extracted)
        script="import sys;from pathlib import Path;sys.path.insert(0,str(Path(sys.argv[1])/'tuning/first_domain_agnostic_v1'));from common import *;frozen();rows=[r for role in PINS for split in ('train','dev') for r in load_rows(role,split)];[target(r) for r in rows];print(len(rows))"
        result=subprocess.run([sys.executable,'-I','-S','-B','-c',script,str(extracted)],capture_output=True,text=True,timeout=30)
        require(result.returncode==0,'Standalone bundle dependency failure: '+result.stderr[-1500:])
        require(result.stdout.strip()=='134','Standalone bundle population mismatch')
        CHECKS.append('standalone extracted bundle: all 134 targets without repository access')
    sys.path.insert(0,str(ROOT/'benchmark/machine_adjudication_v1'))
    import r06
    meta=read(HERE/'protected_population.json')['metadata'];ids=[r['example_id'] for r in meta]
    require(len(ids)==114 and len(set(ids))==114,'R06 membership changed')
    scores=[dict(example_id=i,accepted_outcome=True) for i in ids]
    baseline=r06.family_metric(scores,meta,ids)
    extra=dict(example_id='synthetic-train',split='train',document_family=meta[0]['document_family'])
    def r06proof():
        value=r06.family_metric(scores+[dict(example_id='synthetic-train',accepted_outcome=False)],meta+[extra],ids+['synthetic-train'])
        require(value==baseline,'TRAIN influenced R06')
    effect('R06 TRAIN exclusion',r06proof,patch.object(r06,'non_train',return_value=True))
    acceptance=checked(ROOT/'benchmark/first_tuning_experiment_v1/acceptance_registration.json',read(HERE/'experiment.json')['acceptance_sha256'])
    require(len(acceptance['criteria'])==27 and len(acceptance['catastrophic_limits'])==6 and all(v==0 for v in acceptance['catastrophic_limits'].values()),'Acceptance changed')
    CHECKS.append('27 criteria / six zero limits / R07 / exact 114 R06 membership')
    require(not any(ACCESS.values()),'Forbidden access attempted')
    result=dict(kind='training_pipeline_dry_run',real_model_training=False,real_optimizer_updates=0,
        real_generation_calls=0,checks=CHECKS,check_count=len(CHECKS),effects=EFFECTS,effect_count=len(EFFECTS),
        tokens=token_checks,synthetic_integration=integrations,access=ACCESS,
        human_reviews=0,status='PASS',note='Synthetic adapters/results are temporary and deleted; no measured model quality.')
    write(HERE/'dry_run_evidence.json',result)
    print(json.dumps(result,indent=2))

def score_exact(row):
    s=ev.score(row,target(row))
    return s['accepted_outcome'] and s['contract_valid']

if __name__=='__main__':main()
