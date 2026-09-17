"""Prospective numerical safety primitives. No model loader, launcher or training CLI."""
import math
import json
from pathlib import Path

PRE_STAGES=('hidden','normalized_hidden','logits','ce','regularization','total_loss')


class NumericalStop(RuntimeError):pass


class HealthGate:
    """Sticky failure state; callbacks are injectable for deterministic no-model tests."""
    def __init__(self,ceiling,emit):
        self.ceiling=float(ceiling);self.emit=emit;self.failed=False;self.next_update=1
        self.micro=0;self.stages=[];self.losses=[];self.update_means=[];self.initial_parity=False

    def stop(self,stage,**context):
        if not self.failed:self.emit(dict(event='STOP',first_failing_stage=stage,**context))
        self.failed=True
        raise NumericalStop(stage)

    def require(self,condition,stage,**context):
        if self.failed:raise NumericalStop('NO_RETRY_AFTER_FAILURE')
        if not condition:self.stop(stage,**context)

    def admit_initial(self,passed):
        self.require(self.next_update==1 and self.micro==0 and passed,'update0_parity')
        self.initial_parity=True

    def begin(self,update,micro):
        self.require(self.initial_parity,'update0_not_admitted')
        self.require(update==self.next_update and micro==self.micro+1 and 1<=micro<=4 and len(self.losses)==micro-1,'schedule')
        self.micro=micro;self.stages=[]

    def stage(self,name,finite,**summary):
        self.require(len(self.stages)<len(PRE_STAGES) and name==PRE_STAGES[len(self.stages)],'finite_check_order')
        self.emit(dict(event='microbatch_boundary',update=self.next_update,microbatch=self.micro,stage=name,finite=bool(finite),**summary))
        self.require(finite,name,update=self.next_update,microbatch=self.micro)
        self.stages.append(name)

    def backward(self,ce,action):
        self.require(tuple(self.stages)==PRE_STAGES,'backward_before_all_finite_checks')
        self.require(len(self.losses)==self.micro-1,'duplicate_backward')
        self.require(math.isfinite(ce) and ce<=4*self.ceiling,'microbatch_ce_explosion',ce=ce if math.isfinite(ce) else None)
        action();self.losses.append(float(ce))

    def gradients(self,finite,head_norm,lora_norm,combined_norm,clipped=False):
        stage='clipped_gradients' if clipped else 'gradients'
        self.emit(dict(event=stage,update=self.next_update,microbatch=self.micro,finite=bool(finite),head_gradient_norm=head_norm,lora_gradient_norm=lora_norm,combined_gradient_norm=combined_norm))
        self.require(finite and all(x is not None and math.isfinite(x) for x in [head_norm,lora_norm,combined_norm]),stage)
        if clipped:self.require(combined_norm<=1.00001,'clipping_bound')

    def step(self,precheck,clip,postcheck,optimizer_step,parameter_check,unauthorized_unchanged):
        self.require(self.micro==4 and len(self.losses)==4,'optimizer_before_four_microbatches')
        mean=sum(self.losses)/4
        self.require(mean<=self.ceiling,'update_ce_explosion',mean_ce=mean,ceiling=self.ceiling)
        precheck();clip();postcheck();optimizer_step();parameter_check()
        self.require(unauthorized_unchanged(),'unauthorized_parameter_change')
        self.update_means.append(mean)
        self.emit(dict(event='update_complete',update=self.next_update,mean_ce=mean,ceiling=self.ceiling))
        self.next_update+=1;self.micro=0;self.losses=[]
        if self.next_update==21:
            self.require(len(self.update_means)==20 and max(self.update_means)<=self.ceiling,'admission20')
            self.emit(dict(event='NUMERICAL_ADMISSION_20_PASS',updates=20,dev_evaluated=False))

    def admitted20(self):return not self.failed and self.next_update>=21 and len(self.update_means)>=20


def fp32_numpy(np,hidden,weight,bias,mean,std):
    """Reference arithmetic on preserved/synthetic features only, no statistics fit."""
    for x in [weight,bias,mean,std]:
        if x.dtype!=np.float32 or not np.isfinite(x).all():raise NumericalStop('initializer_dtype_or_finite')
    if not (std>=np.float32(1e-6)).all():raise NumericalStop('invalid_fixed_std')
    hidden=hidden.astype(np.float32,copy=False)
    if not np.isfinite(hidden).all():raise NumericalStop('hidden')
    z=(hidden-mean)/std
    if not np.isfinite(z).all():raise NumericalStop('normalized_hidden')
    logits=z@weight.T+bias
    if not np.isfinite(logits).all():raise NumericalStop('logits')
    assert z.dtype==logits.dtype==np.float32
    return z,logits


def ce_numpy(np,logits,labels):
    # Stable FP32 logsumexp, matching the future FP32 classification contract.
    value=logits.astype(np.float32,copy=False);shift=value-value.max(axis=1,keepdims=True)
    return (np.log(np.exp(shift).sum(axis=1,dtype=np.float32))-shift[np.arange(len(labels)),labels]).astype(np.float32)


def update0(np,expected,actual_logits,actual_ids,labels):
    if actual_ids!=expected['example_ids']:raise NumericalStop('update0_ids')
    target=np.asarray(expected['logits'],dtype=np.float32)
    if actual_logits.dtype!=np.float32 or actual_logits.shape!=target.shape or not np.isfinite(actual_logits).all():raise NumericalStop('update0_logits')
    if not np.allclose(actual_logits,target,rtol=expected['rtol'],atol=expected['atol']):raise NumericalStop('update0_logits_parity')
    if actual_logits.argmax(axis=1).tolist()!=expected['predicted_indices']:raise NumericalStop('update0_argmax')
    ce=float(ce_numpy(np,actual_logits,labels).mean(dtype=np.float32))
    if not expected['ce_range'][0]<=ce<=expected['ce_range'][1]:raise NumericalStop('update0_ce')
    return dict(passed=True,max_logit_error=float(np.max(np.abs(actual_logits-target))),ce=ce)


def require_training_split(split):
    if split!='train':raise NumericalStop('TRAIN_ONLY_GRADIENTS')


def deny_scope(name):
    lowered=str(name).lower().replace('\\','/')
    if any(term in lowered for term in ['holdout','producer','protected','checkpoint-120','features.npy']):
        raise NumericalStop('FORBIDDEN_RUNTIME_PAYLOAD')


def verify_bound(path,expected_sha256):
    import hashlib
    h=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if h!=expected_sha256:raise NumericalStop('artifact_binding')
    return h


def _summary(torch,value):
    v=value.detach().float();finite=bool(torch.isfinite(v).all().item())
    result=dict(dtype=str(value.dtype),finite=finite)
    if finite:
        norms=torch.linalg.vector_norm(v.reshape(-1,v.shape[-1]),dim=-1,dtype=torch.float64) if v.ndim else v.abs().reshape(1)
        result.update(min=float(v.min()),max=float(v.max()),max_abs=float(v.abs().max()),norm_min=float(norms.min()),norm_mean=float(norms.mean()),norm_max=float(norms.max()))
    return result


def torch_classification(torch,hidden,head,mean,std,label,gate):
    """Differentiable FP32 path; called only by a future separately reviewed runner."""
    with torch.autocast(device_type=hidden.device.type,enabled=False):
        for tensor in [head.weight,head.bias,mean,std]:
            gate.require(tensor.dtype==torch.float32,'classifier_dtype')
        gate.require(not mean.requires_grad and not std.requires_grad,'fixed_normalization')
        gate.require(bool(torch.isfinite(mean).all()) and bool(torch.isfinite(std).all()) and bool((std>=1e-6).all()),'normalization_initializer')
        hidden32=hidden.float()
        def boundary(name,v):
            summary=_summary(torch,v);finite=summary.pop('finite');gate.stage(name,finite,**summary)
        boundary('hidden',hidden32)
        standardized=(hidden32-mean)/std;boundary('normalized_hidden',standardized)
        logits=head(standardized);boundary('logits',logits)
        ce=torch.nn.functional.cross_entropy(logits,label);boundary('ce',ce)
        regularization=.001*head.weight.square().mean();boundary('regularization',regularization)
        loss=ce+regularization;boundary('total_loss',loss)
        gate.require(all(v.dtype==torch.float32 for v in [hidden32,standardized,logits,ce,regularization,loss]),'classification_fp32')
        return logits,ce,regularization,loss


def torch_norms(torch,params,gradients=False):
    values=[p.grad if gradients else p for p in params]
    values=[v.detach().float() for v in values if v is not None]
    finite=all(bool(torch.isfinite(v).all().item()) for v in values)
    norm=float(torch.linalg.vector_norm(torch.stack([torch.linalg.vector_norm(v,dtype=torch.float64) for v in values]))) if values and finite else 0. if not values else None
    return finite,norm


def torch_gradient_check(torch,head_params,lora_params,gate,clipped=False):
    hf,hn=torch_norms(torch,head_params,True);lf,ln=torch_norms(torch,lora_params,True)
    total=math.hypot(hn,ln) if hn is not None and ln is not None else None
    gate.gradients(hf and lf,hn,ln,total,clipped)


def torch_parameter_check(torch,head_params,lora_params,gate,phase='post_step_parameters'):
    hf,hn=torch_norms(torch,head_params);lf,ln=torch_norms(torch,lora_params)
    gate.emit(dict(event=phase,update=gate.next_update,head_finite=hf,lora_finite=lf,head_parameter_norm=hn,lora_parameter_norm=ln))
    gate.require(hf and lf,'parameters_after_step')


def optimizer_groups(torch,lora_params,head_params):
    lora_params=list(lora_params);head_params=list(head_params)
    if set(map(id,lora_params))&set(map(id,head_params)):raise NumericalStop('optimizer_overlap')
    if sum(p.numel() for p in lora_params)!=14942208 or sum(p.numel() for p in head_params)!=12292:raise NumericalStop('optimizer_inventory')
    if not all(p.requires_grad and p.dtype==torch.float32 for p in lora_params+head_params):raise NumericalStop('optimizer_dtype')
    return torch.optim.AdamW([dict(params=lora_params,lr=1e-4),dict(params=head_params,lr=1e-3)],betas=(.9,.999),eps=1e-8,weight_decay=0)


def prospective_update(torch,model,head,mean,std,rows,batch,optimizer,gate,unauthorized_unchanged):
    """Unexecuted future adapter hook; no loader, scheduler, retry or generation."""
    gate.require(batch['step']==gate.next_update and batch['example_ids']==[r['example_id'] for r in rows] and len(rows)==4,'bound_batch')
    gate.require(batch['step']<=896,'update_limit')
    if batch['step']>20:gate.require(gate.admitted20(),'admission20_required')
    lora_params=[p for n,p in model.named_parameters() if p.requires_grad and '.lora_' in n]
    head_params=list(head.parameters());params=lora_params+head_params
    gate.require(len(optimizer.param_groups)==2 and [g['lr'] for g in optimizer.param_groups]==[1e-4,1e-3],'optimizer_groups')
    gate.require({id(p) for p in optimizer.param_groups[0]['params']}==set(map(id,lora_params)) and {id(p) for p in optimizer.param_groups[1]['params']}==set(map(id,head_params)),'optimizer_parameter_membership')
    optimizer.zero_grad(set_to_none=True)

    model.train();head.train()
    for micro,row in enumerate(rows,1):
        require_training_split(row['split']);gate.begin(batch['step'],micro)
        torch_parameter_check(torch,head_params,lora_params,gate,phase='pre_forward_parameters')
        ids=torch.tensor([row['input_ids']],dtype=torch.long,device=head.weight.device)
        with torch.autocast(device_type=ids.device.type,dtype=torch.bfloat16):
            hidden=model.get_base_model().model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False,return_dict=True).last_hidden_state[:,-1,:]
        label=torch.tensor([['MATCH','DIVERGENCE','OMISSION','ADDITION'].index(row['relation'])],dtype=torch.long,device=ids.device)
        logits,ce,reg,loss=torch_classification(torch,hidden,head,mean,std,label,gate)
        gate.backward(float(ce.detach()),lambda:(loss/4).backward())
        torch_gradient_check(torch,head_params,lora_params,gate)
    def precheck():
        gate.require(all(p.grad is not None for p in params),'missing_gradient')
        torch_gradient_check(torch,head_params,lora_params,gate)
    def clip():
        try:norm=torch.nn.utils.clip_grad_norm_(params,1.,error_if_nonfinite=True)
        except RuntimeError:gate.stop('clipping_norm')
        gate.require(bool(torch.isfinite(norm).item()),'clipping_norm')
    gate.step(precheck,clip,
        lambda:torch_gradient_check(torch,head_params,lora_params,gate,True),optimizer.step,
        lambda:torch_parameter_check(torch,head_params,lora_params,gate),unauthorized_unchanged)
    optimizer.zero_grad(set_to_none=True)


class FrozenAudit:
    """Future runtime: cheap frozen-parameter checks plus full hashes at admissions."""
    def __init__(self,torch,model):
        self.torch=torch;self.model=model
        self.parameters=[(n,p) for n,p in model.named_parameters() if '.lora_' not in n]
        if any(p.requires_grad for _,p in self.parameters):raise NumericalStop('base_trainable')
        self.versions={n:(p._version,str(p.dtype),tuple(p.shape),p.data_ptr()) for n,p in self.parameters}
        self.initial_hash=self.hash()

    def hash(self):
        import hashlib
        h=hashlib.sha256()
        for name,value in self.model.state_dict().items():
            if '.lora_' in name:continue
            v=value.detach().cpu().contiguous()
            h.update(name.encode());h.update(str((v.dtype,tuple(v.shape))).encode())
            h.update(v.reshape(-1).view(self.torch.uint8).numpy().tobytes())
        return h.hexdigest()

    def unchanged(self,full=False):
        valid=all(not p.requires_grad and p.grad is None and self.versions[n]==(p._version,str(p.dtype),tuple(p.shape),p.data_ptr()) for n,p in self.parameters)
        return valid and (not full or self.hash()==self.initial_hash)
