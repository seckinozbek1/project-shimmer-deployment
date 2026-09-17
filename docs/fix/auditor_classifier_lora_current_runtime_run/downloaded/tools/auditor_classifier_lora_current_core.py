"""Current-runtime-only head rebase and live parity; no historical cached anchor."""
import hashlib
import math
import auditor_classifier_lora_core as c
import auditor_classifier_lora_fork as fork
import auditor_classifier_lora_stable as stable


def ceilings(current_ce):
    if not math.isfinite(current_ce) or current_ce<0:raise stable.NumericalStop('invalid_current_ce')
    mean=max(10*math.log(4),20*current_ce)
    return dict(mean_update_ce_ceiling=mean,microbatch_ce_ceiling=4*mean,current_update0_train_ce=current_ce,formula='max(10*ln(4),20*CURRENT_UPDATE0_TRAIN_CE)')


def normalize(np,features,rows):
    if len(rows)!=1792 or any(r['split']!='train' for r in rows) or features.shape!=(1792,3072) or features.dtype!=np.float32 or not np.isfinite(features).all():
        raise stable.NumericalStop('TRAIN_only_feature_normalization')
    mean=features.mean(axis=0,dtype=np.float32);std=np.maximum(features.std(axis=0,ddof=0,dtype=np.float32),np.float32(1e-6))
    return mean,std


def verify_adapter(torch,model,slot,expected):
    seen={}
    for name,p in model.named_parameters():
        if '.lora_A.'+slot+'.' not in name and '.lora_B.'+slot+'.' not in name:continue
        if p.dtype!=torch.float32:raise stable.NumericalStop('loaded_adapter_dtype')
        raw=p.detach().cpu().contiguous().numpy().tobytes()
        seen[name.replace('.'+slot+'.','.')]=dict(shape=list(p.shape),dtype='F32',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    if seen!=expected:raise stable.NumericalStop('loaded_adapter_identity')
    cfg=model.peft_config[slot]
    if not (cfg.r==8 and cfg.lora_alpha==16 and cfg.lora_dropout==.05 and cfg.bias=='none' and not cfg.use_dora and not cfg.use_rslora and not cfg.fan_in_fan_out and not cfg.modules_to_save and not cfg.rank_pattern and not cfg.alpha_pattern and set(cfg.target_modules)==set(c.TARGETS)):
        raise stable.NumericalStop('loaded_adapter_configuration')


def fit_head(torch,x,labels,callback):
    """Exactly the validated 200-update full-population Adam fit, with finite gates."""
    assert x.shape==(1792,3072) and x.dtype==torch.float32 and not x.requires_grad
    assert labels.shape==(1792,) and labels.bincount(minlength=4).tolist()==[448]*4
    assert torch.are_deterministic_algorithms_enabled()
    torch.manual_seed(7)
    head=torch.nn.Linear(3072,4,device=x.device,dtype=torch.float32)
    with torch.no_grad():head.weight.zero_();head.bias.zero_()
    opt=torch.optim.Adam(head.parameters(),lr=.01,betas=(.9,.999),eps=1e-8,weight_decay=0)
    callback(0,head,None,None)
    for step in range(1,201):
        opt.zero_grad(set_to_none=True)
        logits=head(x);ce=torch.nn.functional.cross_entropy(logits,labels);reg=.001*head.weight.square().mean()
        if not bool(torch.isfinite(logits).all()) or not bool(torch.isfinite(ce+reg)):raise stable.NumericalStop('head_fit_loss')
        repeated=head(x)
        if not torch.equal(logits,repeated):raise stable.NumericalStop('head_fit_repeat_forward')
        repeated_loss=torch.nn.functional.cross_entropy(repeated,labels)+.001*head.weight.square().mean()
        reference_gradients=torch.autograd.grad(repeated_loss,tuple(head.parameters()))
        (ce+reg).backward()
        if not all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in head.parameters()):raise stable.NumericalStop('head_fit_gradients')
        if not all(torch.equal(p.grad,g) for p,g in zip(head.parameters(),reference_gradients)):raise stable.NumericalStop('head_fit_repeat_gradients')
        opt.step()
        if not all(bool(torch.isfinite(p).all()) for p in head.parameters()):raise stable.NumericalStop('head_fit_parameters')
        callback(step,head,float(ce.detach()),float(reg.detach()))
    opt.zero_grad(set_to_none=True)
    return head


class CurrentPreflight(fork.Preflight):
    """Only CURRENT reference/fork and CURRENT fitted-head baseline are anchors."""
    def run(self,rows,select,observe,remove_reference,verify_removed):
        self.check(not self.passed,'duplicate_preflight')
        try:
            self.check([r['example_id'] for r in rows]==self.baseline['example_ids'],'bound_train_ids')
            self.check([fork.token_hash(r['input_ids']) for r in rows]==self.baseline['input_id_hashes'],'bound_train_tokens')
            self.check([r['relation'] for r in rows]==self.baseline['labels'],'bound_train_labels')
            by={r['example_id']:r for r in rows};control=[by[i] for i in self.controls['example_ids']]
            select(fork.REFERENCE);reference=[self.observe(r,observe) for r in control]
            select(fork.CANDIDATE);candidate=[self.observe(r,observe) for r in control]
            for row,a,b in zip(control,reference,candidate):
                errors={}
                for key in ['hidden','normalized','logits']:
                    self.check(a[key].shape==b[key].shape and self.np.allclose(a[key],b[key],rtol=1e-4,atol=2e-4),'reference_fork_'+key)
                    errors[key]=float(self.np.max(self.np.abs(a[key]-b[key])))
                self.check(int(a['logits'].argmax())==int(b['logits'].argmax()),'reference_fork_argmax')
                self.check(math.isclose(a['ce'],b['ce'],rel_tol=1e-4,abs_tol=2e-4),'reference_fork_ce')
                self.emit(dict(event='control_parity',example_id=row['example_id'],max_errors=errors,ce_error=abs(a['ce']-b['ce'])))
            remove_reference();self.check(verify_removed(),'reference_not_removed')
            logits=self.np.stack([self.observe(r,observe)['logits'] for r in rows])
            predictions=logits.argmax(axis=1).tolist()
            self.check(predictions==self.baseline['predicted_indices'],'current_full_train_predictions')
            labels=self.np.array([self.baseline['classes'].index(r['relation']) for r in rows])
            ce=float(stable.ce_numpy(self.np,logits,labels).mean(dtype=self.np.float32))
            self.check(self.baseline['ce_range'][0]<=ce<=self.baseline['ce_range'][1],'current_full_train_ce')
            metric=c.metrics(self.baseline['labels'],[self.baseline['classes'][i] for i in predictions])
            self.check(metric==self.baseline['metrics'],'current_full_train_metrics')
            self.passed=True;self.result=dict(passed=True,ce=ce,metrics=metric,reference_removed=True)
            self.emit(dict(event='UPDATE0_PASS',train_count=len(rows),**self.result))
            return self.result
        except Exception:
            if not self.failed:self.failed=True;self.emit(dict(event='NO_GO',stage='preflight_exception'))
            raise
