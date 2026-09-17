"""Local artifact inspection and prospective update0 protocol; no model loader."""
import hashlib
import json
import math
import struct
from pathlib import Path
import auditor_classifier_lora_stable as stable

SOURCE_SHA='733eb0005f898d1ff61aa72a92d84c1b35f11d52a9a09f3b0aafa73dfb35ade6'
CONFIG_SHA='af6a53d6c24938eeaa74b5aaf753ebe7b67cf2b5be76d9fd5454fa6fdaa4d8b6'
REFERENCE='historical_reference'
CANDIDATE='classifier_fork'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def token_hash(ids):return hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest()


def inventory(path):
    """Parse safetensors header and hash raw tensor bytes, never deserialize weights."""
    with Path(path).open('rb') as f:
        n=struct.unpack('<Q',f.read(8))[0]
        if n>16*1024*1024:raise stable.NumericalStop('invalid_tensor_header')
        header=json.loads(f.read(n));start=8+n;result={}
        for name,meta in sorted(header.items()):
            if name=='__metadata__':continue
            a,b=meta['data_offsets'];f.seek(start+a);raw=f.read(b-a)
            if len(raw)!=b-a:raise stable.NumericalStop('truncated_tensor')
            result[name]=dict(shape=meta['shape'],dtype=meta['dtype'],bytes=b-a,sha256=hashlib.sha256(raw).hexdigest())
    return result


def create_fork(source,destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if source==destination or source in destination.parents or destination in source.parents:
        raise stable.NumericalStop('fork_path_isolation')
    expected={'adapter_model.safetensors':SOURCE_SHA,'adapter_config.json':CONFIG_SHA}
    for name,h in expected.items():stable.verify_bound(source/name,h)
    destination.mkdir(parents=True,exist_ok=True)
    for name,h in expected.items():
        target=destination/name
        if target.is_symlink():raise stable.NumericalStop('fork_symlink')
        if target.exists():stable.verify_bound(target,h)
        else:
            with target.open('xb') as out:out.write((source/name).read_bytes())
        if (source/name).samefile(target):raise stable.NumericalStop('fork_alias')
        stable.verify_bound(target,h);stable.verify_bound(source/name,h)
    left=inventory(source/'adapter_model.safetensors');right=inventory(destination/'adapter_model.safetensors')
    if left!=right:raise stable.NumericalStop('tensor_copy')
    return dict(source_adapter_sha256=SOURCE_SHA,fork_adapter_sha256=sha(destination/'adapter_model.safetensors'),config_sha256=CONFIG_SHA,
                tensors=left,tensors_compared=len(left),parameters=sum(math.prod(t['shape']) for t in left.values()),exact_equal=True,source_unchanged=True)


def trainable_fork_only(model,head):
    """Called after reference deletion, and again immediately before optimizer creation."""
    if set(model.peft_config)!={CANDIDATE}:raise stable.NumericalStop('reference_not_removed')
    active=model.active_adapters
    if active!=[CANDIDATE]:raise stable.NumericalStop('dual_adapter_path')
    params=[]
    for name,p in model.named_parameters():
        candidate=('.lora_A.'+CANDIDATE+'.' in name or '.lora_B.'+CANDIDATE+'.' in name)
        if p.requires_grad!=candidate:raise stable.NumericalStop('unauthorized_trainable_parameter')
        if REFERENCE in name:raise stable.NumericalStop('reference_parameter_retained')
        if candidate:params.append(p)
    if not params or not all(p.requires_grad for p in head.parameters()):raise stable.NumericalStop('missing_trainable')
    return params


def freeze_slots(model,head):
    for p in model.parameters():p.requires_grad_(False)
    for p in head.parameters():p.requires_grad_(False)
    model.eval();head.eval()


def activate_fork_training(model,head):
    model.set_adapter(CANDIDATE)
    for name,p in model.named_parameters():
        p.requires_grad_('.lora_A.'+CANDIDATE+'.' in name or '.lora_B.'+CANDIDATE+'.' in name)
    for p in head.parameters():p.requires_grad_(True)
    return trainable_fork_only(model,head)


def torch_observe(torch,np,model,head,mean,std,row):
    """Future GPU callback. Eval/inference only; never invoked during local preparation."""
    stable.require_training_split(row['split'])
    model.eval();head.eval()
    if any(p.requires_grad for p in model.parameters()) or any(p.requires_grad for p in head.parameters()):
        raise stable.NumericalStop('preflight_not_frozen')
    with torch.inference_mode():
        ids=torch.tensor([row['input_ids']],dtype=torch.long,device=head.weight.device)
        with torch.autocast(device_type=ids.device.type,dtype=torch.bfloat16):
            h=model.get_base_model().model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False,return_dict=True).last_hidden_state[:,-1,:]
        with torch.autocast(device_type=ids.device.type,enabled=False):
            h=h.float();z=(h-mean)/std;logits=head(z)
        return dict(input_ids=ids[0].cpu().tolist(),hidden=h[0].cpu().numpy().copy(),normalized=z[0].cpu().numpy().copy(),logits=logits[0].float().cpu().numpy().copy())


class Preflight:
    """Sticky protocol: reference -> candidate -> remove reference -> TRAIN -> optimizer."""
    def __init__(self,np,controls,baseline,emit):
        self.np=np;self.controls=controls;self.baseline=baseline;self.emit=emit
        self.failed=False;self.passed=False;self.optimizer_created=False

    def check(self,value,stage):
        if self.failed:raise stable.NumericalStop('NO_RETRY_AFTER_FAILURE')
        if not value:
            self.failed=True;self.emit(dict(event='NO_GO',stage=stage));raise stable.NumericalStop(stage)

    def observe(self,row,callback):
        self.check(row['split']=='train','train_only')
        value=callback(row);self.check(value['input_ids']==row['input_ids'],'prompt_tokens')
        for key in ['hidden','normalized','logits']:
            arr=value[key];self.check(arr.dtype==self.np.float32 and arr.ndim==1 and self.np.isfinite(arr).all(),key+'_finite_fp32')
        self.check(value['hidden'].shape==value['normalized'].shape and value['logits'].shape==(4,),'shapes')
        label=self.baseline['classes'].index(row['relation'])
        value['ce']=float(stable.ce_numpy(self.np,value['logits'][None,:],self.np.array([label]))[0])
        return value

    def run(self,rows,select,observe,remove_reference,verify_removed):
        self.check(not self.passed,'duplicate_preflight')
        try:
            self.check([r['example_id'] for r in rows]==self.baseline['example_ids'],'bound_train_ids')
            self.check([token_hash(r['input_ids']) for r in rows]==self.baseline['input_id_hashes'],'bound_train_tokens')
            self.check([r['relation'] for r in rows]==self.baseline['labels'],'bound_train_labels')
            by={r['example_id']:r for r in rows};control=[by[i] for i in self.controls['example_ids']]
            select(REFERENCE);reference=[self.observe(r,observe) for r in control]
            select(CANDIDATE);candidate=[self.observe(r,observe) for r in control]
            for row,a,b in zip(control,reference,candidate):
                errors={}
                for key in ['hidden','normalized','logits']:
                    self.check(a[key].shape==b[key].shape and self.np.allclose(a[key],b[key],rtol=1e-4,atol=2e-4),'reference_fork_'+key)
                    errors[key]=float(self.np.max(self.np.abs(a[key]-b[key])))
                self.check(int(a['logits'].argmax())==int(b['logits'].argmax()),'reference_fork_argmax')
                self.check(math.isclose(a['ce'],b['ce'],rel_tol=1e-4,abs_tol=2e-4),'reference_fork_ce')
                self.emit(dict(event='control_parity',example_id=row['example_id'],max_errors=errors,ce_error=abs(a['ce']-b['ce'])))
            labels=self.np.array(self.controls['labels'])
            stable.update0(self.np,self.controls,self.np.stack([x['logits'] for x in candidate]),self.controls['example_ids'],labels)
            remove_reference();self.check(verify_removed(),'reference_not_removed')
            logits=self.np.stack([self.observe(r,observe)['logits'] for r in rows])
            predictions=logits.argmax(axis=1).tolist()
            self.check(predictions==self.baseline['predicted_indices'],'full_train_predictions')
            labels=self.np.array([self.baseline['classes'].index(r['relation']) for r in rows])
            ce=float(stable.ce_numpy(self.np,logits,labels).mean(dtype=self.np.float32))
            self.check(self.baseline['ce_range'][0]<=ce<=self.baseline['ce_range'][1],'full_train_ce')
            import auditor_v2_execution as previous
            metric=previous.metrics(self.baseline['labels'],[self.baseline['classes'][i] for i in predictions])
            self.check(metric==self.baseline['metrics'],'full_train_metrics')
            self.passed=True;self.emit(dict(event='UPDATE0_PASS',train_count=len(rows),ce=ce,reference_removed=True))
            return dict(passed=True,ce=ce)
        except Exception:
            if not self.failed:self.failed=True;self.emit(dict(event='NO_GO',stage='preflight_exception'))
            raise

    def optimizer(self,torch,model,head,health):
        self.check(self.passed and not self.optimizer_created,'optimizer_before_preflight_or_duplicate')
        try:
            params=trainable_fork_only(model,head)
            optimizer=stable.optimizer_groups(torch,params,head.parameters())
            health.admit_initial(True);self.optimizer_created=True
            return optimizer
        except Exception:
            self.failed=True;raise


def verify_loaded(torch,np,model,head,mean,std,artifact_root,bindings,receipt):
    """Bind actual runtime tensors to the reviewed artifact identities before inference."""
    from safetensors.numpy import load_file
    root=Path(artifact_root)
    for name,expected in bindings.items():stable.verify_bound(root/name,expected)
    for slot in [REFERENCE,CANDIDATE]:
        seen={}
        for name,p in model.named_parameters():
            if '.lora_A.'+slot+'.' not in name and '.lora_B.'+slot+'.' not in name:continue
            canonical=name.replace('.'+slot+'.','.')
            if p.dtype!=torch.float32:raise stable.NumericalStop('adapter_runtime_dtype')
            raw=p.detach().cpu().contiguous().numpy().tobytes()
            seen[canonical]=dict(shape=list(p.shape),dtype='F32',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if seen!=receipt['tensors']:raise stable.NumericalStop('adapter_runtime_identity')
        config=model.peft_config[slot]
        if not (config.r==8 and config.lora_alpha==16 and config.lora_dropout==.05 and config.bias=='none' and not config.fan_in_fan_out and not config.use_rslora and not config.use_dora and not config.modules_to_save and not config.rank_pattern and not config.alpha_pattern and set(config.target_modules)=={'q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj'}):
            raise stable.NumericalStop('adapter_runtime_config')
    paths={Path(p).name:root/p for p in bindings}
    saved=load_file(str(paths['head-200.safetensors']))
    for actual,expected in [(head.weight,saved['weight']),(head.bias,saved['bias']),(mean,np.load(paths['mean.npy'],allow_pickle=False)),(std,np.load(paths['std.npy'],allow_pickle=False))]:
        if actual.dtype!=torch.float32 or not np.array_equal(actual.detach().cpu().numpy(),expected):raise stable.NumericalStop('loaded_classifier_identity')


def remote_preflight(torch,np,model,head,mean,std,rows,controls,baseline,emit,artifact_root,bindings,receipt):
    """Model already loaded with exactly two byte-bound adapters; optimizer must not exist."""
    gate=Preflight(np,controls,baseline,emit)
    verify_loaded(torch,np,model,head,mean,std,artifact_root,bindings,receipt)
    gate.check(set(model.peft_config)=={REFERENCE,CANDIDATE},'adapter_slots')
    gate.check(all(x.dtype==torch.float32 and not x.requires_grad for x in [mean,std]),'fixed_normalization')
    gate.check(bool(torch.isfinite(mean).all()) and bool(torch.isfinite(std).all()) and bool((std>=1e-6).all()),'normalization_finite')
    gate.check(all(p.dtype==torch.float32 for p in head.parameters()),'head_fp32')
    def select(name):
        model.set_adapter(name);freeze_slots(model,head)
        gate.check(model.active_adapters==[name],'single_active_adapter')
    def remove():
        verify_loaded(torch,np,model,head,mean,std,artifact_root,bindings,receipt)
        model.delete_adapter(REFERENCE);select(CANDIDATE)
    gate.run(rows,select,lambda r:torch_observe(torch,np,model,head,mean,std,r),remove,
             lambda:set(model.peft_config)=={CANDIDATE} and model.active_adapters==[CANDIDATE] and not any(REFERENCE in n for n,_ in model.named_parameters()))
    activate_fork_training(model,head)
    return gate


def prospective_update(torch,model,head,mean,std,rows,batch,optimizer,health,unauthorized_unchanged):
    """Recheck single-fork isolation at every update; retain all stabilization checks."""
    try:trainable_fork_only(model,head)
    except stable.NumericalStop:health.stop('fork_isolation_before_update')
    return stable.prospective_update(torch,model,head,mean,std,rows,batch,optimizer,health,unauthorized_unchanged)
