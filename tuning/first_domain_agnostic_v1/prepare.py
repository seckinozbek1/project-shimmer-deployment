"""Local preparation: pinned tokenizer assets only; no weights or generation."""
import ast
import importlib.metadata
import math
import os
from pathlib import Path
import statistics
import sys
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_TORCH='0',USE_TF='0',USE_FLAX='0')
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def architecture(path, cfg):
    import transformers
    family=cfg['model_type']
    require(family in ('qwen2','llama'), 'Unregistered architecture')
    source=Path(transformers.__file__).parent/'models'/family/('modeling_'+family+'.py')
    tree=ast.parse(source.read_text(encoding='utf8'))
    found={}
    for cls in tree.body:
        if isinstance(cls,ast.ClassDef) and cls.name.endswith(('Attention','MLP')):
            for node in ast.walk(cls):
                if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call):
                    for dest in node.targets:
                        if isinstance(dest,ast.Attribute) and isinstance(dest.value,ast.Name) and dest.value.id=='self' and dest.attr in MODULES:
                            require(ast.unparse(node.value.func)=='nn.Linear','Expected linear projection')
                            found[dest.attr]=cls.name
    require(set(found)==set(MODULES),'Missing architecture target module')
    names=['model.layers.%d.%s.%s'%(i,'self_attn' if m in MODULES[:4] else 'mlp',m)
           for i in range(cfg['num_hidden_layers']) for m in MODULES]
    h=cfg['hidden_size']; inter=cfg['intermediate_size']; kv=h//cfg['num_attention_heads']*cfg['num_key_value_heads']
    # r*(in+out) for seven actual Linear projections in each layer.
    params=8*cfg['num_hidden_layers']*(4*h+2*(h+kv)+3*(h+inter))
    return dict(family=family,architecture=cfg['architectures'][0],source_sha256=digest(source.read_bytes()),
                source=source.name,resolved_modules=names,classes=found,adapter_parameters=params)

def summary(values):
    v=sorted(values)
    return dict(min=min(v),median=statistics.median(v),p90=v[math.ceil(.9*len(v))-1],p95=v[math.ceil(.95*len(v))-1],max=max(v))

def main():
    sys.path.insert(0,str(ROOT/'tools'))
    from prepare_cloud_run import git
    source_commit=git(ROOT,'rev-parse','HEAD').decode().strip()
    pool=read(ROOT/APPROVED)
    all_stats={}; selected_counts={}; artifacts=[]
    for role,splits in pool['roles'].items():
        out=HERE/role; ds=dict(role=role,approved_manifest=APPROVED,approved_manifest_sha256=digest((ROOT/APPROVED).read_bytes()),splits={})
        for split,spec in splits.items():
            source=checked(ROOT/spec['source'],spec['source_sha256'])
            rows=[r for r in source if r['role']==role and r['example_id'] in spec['allowed_ids']]
            require(len(rows)==spec['count'] and sorted(r['example_id'] for r in rows)==sorted(spec['allowed_ids']), 'Approved population mismatch')
            require(digest(rows)==spec['selected_rows_sha256'],'Curated selected rows changed')
            for r in rows:
                require(r['split']==split and not r.get('review_ambiguity',False),'Split/ambiguity violation')
                target(r)
            write(out/(split+'.json'),rows)
            ds['splits'][split]=dict(count=len(rows),ids=[r['example_id'] for r in rows],
                sha256=digest((out/(split+'.json')).read_bytes()),row_hashes={r['example_id']:digest(r) for r in rows},
                source=spec['source'],source_sha256=spec['source_sha256'])
        write(out/'dataset.json',ds)
        path=cached(role);cfg=read(path/'config.json');arch=architecture(path,cfg)
        n=ds['splits']['train']['count'];steps=math.ceil(n/4)
        exp=dict(experiment=EXPERIMENT,role=role,model_id=PINS[role][0],revision=PINS[role][1],
            dataset_sha256=digest((out/'dataset.json').read_bytes()),asset_hashes={n:digest((path/n).read_bytes()) for n in ASSETS if (path/n).is_file()},
            architecture=arch,quantization=cfg['quantization_config'],
            lora=dict(r=8,lora_alpha=16,lora_dropout=.05,bias='none',task_type='CAUSAL_LM',target_modules=list(MODULES)),
            training=dict(learning_rate=1e-4,microbatch=1,gradient_accumulation=4,effective_batch=4,
                steps_per_epoch=steps,max_steps=2*steps,warmup_steps=1,scheduler='linear',weight_decay=0.,
                optimizer='adamw_torch',seed=7,gradient_checkpointing=True,bf16=True),
            checkpoint_steps=[steps,2*steps],fallback=None,
            generation=dict(do_sample=False,num_beams=1,use_cache=True),
            output_directory='runs/'+EXPERIMENT+'/'+role,
            training_authorized=False,model_execution_performed=False)
        exp['training'].update(max_grad_norm=1.,adam_beta1=.9,adam_beta2=.999,adam_epsilon=1e-8,
            last_accumulation_group='actual group mean; auditor last group is 2 examples',data_epochs=2,
            attention_implementation='eager',allow_tf32=False,deterministic_algorithms=True)
        write(out/'experiment.json',exp)
        tok=tokenizer(role);lengths=[]
        for split in ('train','dev'):
            for r in load_rows(role,split):
                e=encode(r,tok);lengths.append(dict(example_id=r['example_id'],split=split,**e['lengths']))
        maximum=max(x['total'] for x in lengths)
        exp['max_seq_length']=32*math.ceil((maximum+32)/32)
        exp['generation']['max_new_tokens']=32*math.ceil((max(x['target'] for x in lengths)+32)/32)
        exp['tokenizer_class']=type(tok).__name__
        exp['terminal_token_ids']=[tok.eos_token_id]+([tok.convert_tokens_to_ids('<|end|>')] if role=='auditor' else [])
        write(out/'experiment.json',exp)
        all_stats[role]={split:{k:summary([r[k] for r in lengths if split=='all' or r['split']==split])
            for k in ('raw_input','rendered_prompt','target','total')} for split in ('all','train','dev')}
        write(out/'token_lengths.json',dict(rows=lengths,summary=all_stats[role],max_seq_length=exp['max_seq_length'],truncated=0))
        selected_counts[role]={s:ds['splits'][s]['count'] for s in ds['splits']}
    acceptance='benchmark/first_tuning_experiment_v1/acceptance_registration.json'
    r06='benchmark/machine_adjudication_v1/post_freeze/r06_population.json'
    protected=read(ROOT/r06)['eligible_evaluation_metadata']
    require(len(protected)==114,'R06 population changed')
    # Identity metadata only, no protected target/source access.
    base=read(ROOT/'benchmark/task_semantics_v2/baseline_reference.json')
    expansion=read(ROOT/'benchmark/task_semantics_v2/freeze.json')
    write(HERE/'protected_population.json',dict(source=r06,source_sha256=digest((ROOT/r06).read_bytes()),
        metadata=protected,counts={'dev':40,'test':37,'sealed_adversarial':37},
        target_source_hashes={'benchmark/task_semantics/seed.json':base['hashes']['benchmark/task_semantics/seed.json'],
            'benchmark/task_semantics_v2/extension.json':expansion['hashes']['extension.json']},
        evaluation_scope='development-inclusive registered non-TRAIN; not independent final evidence'))
    write(HERE/'experiment.json',dict(experiment=EXPERIMENT,source_commit=source_commit,
        approved_pool_sha256=digest((ROOT/APPROVED).read_bytes()),counts=selected_counts,
        use='training_pipeline_dry_run',training_authorized=False,real_model_training=False,
        human_review_status='PENDING',acceptance_source=acceptance,acceptance_sha256=digest((ROOT/acceptance).read_bytes()),
        acceptance_criteria=27,catastrophic_zero_limits=6,R07_preserved=True,
        selection_rule='zero catastrophic failures, then 100% contract validity; then role semantic mean; ties earliest step, then adapter hash',
        protected_rule='both role selection freezes verified before any protected read; exactly one paired BASE/TUNED evaluation; no feedback to selection',
        runtime=dict(python='3.12.3',platform='linux_x86_64',cuda='12.1',driver_minimum='525.60.13',gpu_count=1),
        environment={'PYTHONHASHSEED':'7','CUBLAS_WORKSPACE_CONFIG':':4096:8','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'},
        dry_run_runtime={n:importlib.metadata.version(n) for n in ('transformers','tokenizers','huggingface-hub','jinja2')},
        expected_commands=['python -B tuning/first_domain_agnostic_v1/dry_run.py',
            'python -B tuning/first_domain_agnostic_v1/train.py --role producer --authorization /secure/operator-authorization.json',
            'python -B tuning/first_domain_agnostic_v1/train.py --role auditor --authorization /secure/operator-authorization.json'],
        no_automatic_fallback=True))
    top=read(HERE/'experiment.json')
    protected_sources=['tuning/first_domain_agnostic_v1/protected_eval.py',
        'tuning/first_domain_agnostic_v1/protected_population.json',
        'benchmark/first_tuning_experiment_v1/registration.py','benchmark/machine_adjudication_v1/r06.py']
    top['protected_component_hashes']={n:digest((ROOT/n).read_bytes()) for n in protected_sources}
    write(HERE/'experiment.json',top)
    print('Prepared exact role datasets and tokenizer audit:',selected_counts)
    print('Token totals:',{k:v['all']['total'] for k,v in all_stats.items()})

if __name__=='__main__':main()
