"""Future GPU backend. Imported locally for syntax only; no model imports at module scope."""
import hashlib
import math
from contextlib import contextmanager
import auditor_optuna_hpo as h


class TorchBackend:
    def __init__(self, torch, np, model, head, mean, std, records, split, frozen_audit, emit):
        self.t=torch;self.np=np;self.model=model;self.head=head;self.mean=mean;self.std=std
        self.rows={r['example_id']:r for r in records}
        self.splits={r['example_id']:r['split'] for r in split['assignments']}
        self.audit=frozen_audit;self.emit=emit;self.opt=None;self.admitted=False
        self.lora={n:p for n,p in model.named_parameters() if '.lora_A.classifier_fork.' in n or '.lora_B.classifier_fork.' in n}
        self.heads=dict(head.named_parameters())
        h.require(len(self.lora)==448 and sum(p.numel() for p in self.lora.values())==14942208,'LoRA inventory')
        h.require(sum(p.numel() for p in self.heads.values())==12292,'head inventory')
        h.require(all(p.dtype==torch.float32 for p in self.parameters()),'trainable dtype')

    def parameters(self):
        return list(self.lora.values())+list(self.heads.values())

    def snapshot(self):
        return {**{n:p.detach().cpu().clone() for n,p in self.lora.items()},**{'head.'+n:p.detach().cpu().clone() for n,p in self.heads.items()}}

    def state_hash(self):
        digest=hashlib.sha256()
        for name,value in sorted(self.snapshot().items()):
            digest.update(name.encode());digest.update(value.contiguous().numpy().tobytes())
        return digest.hexdigest()

    def restore(self, state):
        h.require(set(state)==set(self.lora)|{'head.'+n for n in self.heads},'snapshot keys')
        with self.t.no_grad():
            for n,p in self.lora.items():p.copy_(state[n])
            for n,p in self.heads.items():p.copy_(state['head.'+n])
        h.require(self.audit.unchanged(full=True),'base changed between trials')

    def discard_optimizer(self):
        self.opt=None

    def clear_gradients(self):
        self.model.zero_grad(set_to_none=True);self.head.zero_grad(set_to_none=True)

    def gradients_empty(self):
        return all(p.grad is None for p in self.model.parameters()) and all(p.grad is None for p in self.head.parameters())

    def set_dropout(self, value):
        h.require(value in (0.,.05),'dropout selection')
        count=0
        for module in self.model.modules():
            slots=getattr(module,'lora_dropout',None)
            if slots is not None and 'classifier_fork' in slots:
                slots['classifier_fork']=self.t.nn.Dropout(p=value)
                count+=1
        h.require(count==224,'LoRA dropout module inventory')
        self.model.peft_config['classifier_fork'].lora_dropout=value
        self.dropout=value

    def seed(self, value):
        import random
        random.seed(value);self.np.random.seed(value);self.t.manual_seed(value);self.t.cuda.manual_seed_all(value)

    def new_optimizer(self, params):
        import auditor_classifier_lora_fork as fork
        fork.activate_fork_training(self.model,self.head)
        self.opt=self.t.optim.AdamW([dict(params=list(self.lora.values()),lr=h.lora_lr(params,1)),dict(params=list(self.heads.values()),lr=params['head_lr'])],betas=(.9,.999),eps=1e-8,weight_decay=0.)

    def optimizer_empty(self):
        return self.opt is not None and len(self.opt.state)==0

    def set_lrs(self, lora, head):
        self.opt.param_groups[0]['lr']=lora;self.opt.param_groups[1]['lr']=head

    def summary(self, tensor, gate):
        v=tensor.detach().float()
        if not bool(self.t.isfinite(v).all()):raise h.Instability('nonfinite_tensor')
        return dict(dtype=str(tensor.dtype),norm=float(self.t.linalg.vector_norm(v,dtype=self.t.float64)),min=float(v.min()),max=float(v.max()),max_abs=float(v.abs().max()))

    def forward(self, identifier, gate, diagnostic_only=False):
        row=self.rows[identifier];t=self.t
        ids=t.tensor([row['input_ids']],dtype=t.long,device=self.head.weight.device)
        with t.autocast('cuda',dtype=t.bfloat16):
            hidden=self.model.get_base_model().model(input_ids=ids,attention_mask=t.ones_like(ids),use_cache=False,return_dict=True).last_hidden_state[:,-1,:]
        hidden=hidden.float()
        with t.autocast('cuda',enabled=False):
            z=(hidden-self.mean)/self.std;logits=self.head(z)
            ce=t.nn.functional.cross_entropy(logits,t.tensor([h.CLASSES.index(row['relation'])],device=ids.device))
        summary={k:self.summary(v,gate) for k,v in [('hidden',hidden),('standardized',z),('logits',logits),('ce',ce)]}
        summary.update(train_mode=self.model.training,head_train_mode=self.head.training,lora_dropout=getattr(self,'dropout',.05),backbone_autocast='bfloat16',classifier_autocast=False)
        self.emit(dict(event='forward_boundary',trial=getattr(self,'trial_number',None),example_id=identifier,**summary))
        # Matched controls do not make finite-CE pruning/performance decisions.
        # Nonfinite tensors still trigger the mandatory global numerical gate.
        if not diagnostic_only:gate.micro(float(ce.detach()))
        return hidden,z,logits,ce,summary

    def observe(self, row):
        self.model.eval();self.head.eval()
        with self.t.no_grad():
            # Compatibility checks do not consume labels or apply loss gates.
            ids=self.t.tensor([row['input_ids']],dtype=self.t.long,device=self.head.weight.device)
            with self.t.autocast('cuda',dtype=self.t.bfloat16):
                hidden=self.model.get_base_model().model(input_ids=ids,attention_mask=self.t.ones_like(ids),use_cache=False,return_dict=True).last_hidden_state[:,-1,:].float()
            with self.t.autocast('cuda',enabled=False):
                z=(hidden-self.mean)/self.std;logits=self.head(z)
            for value in [hidden,z,logits]:
                h.require(bool(self.t.isfinite(value).all()),'nonfinite compatibility features')
        return dict(hidden=hidden[0].cpu().numpy().copy(),standardized=z[0].cpu().numpy().copy(),logits=logits[0].cpu().numpy().copy())

    def norms(self, params, gradients=False):
        values=[p.grad if gradients else p for p in params]
        if gradients:h.require(all(x is not None for x in values),'missing gradients')
        if not all(bool(self.t.isfinite(v).all()) for v in values):raise h.Instability('nonfinite_gradients_or_parameters')
        return math.sqrt(sum(float(self.t.sum(v.detach().double().square())) for v in values))

    def update(self, ids, update, gate):
        h.require(1<=update<=80 and len(ids)==4,'trial update contract')
        h.require(all(self.splits[i]=='inner_train' for i in ids),'INNER_VAL gradients denied')
        self.clear_gradients();self.model.train();self.head.train();before=self.snapshot();ces=[]
        for micro,identifier in enumerate(ids,1):
            self.norms(self.parameters())
            hidden,z,logits,ce,summary=self.forward(identifier,gate)
            with self.t.autocast('cuda',enabled=False):
                loss=(ce+.001*self.head.weight.square().mean())/4
            self.summary(loss,gate);loss.backward();ces.append(float(ce.detach()))
            hn=self.norms(list(self.heads.values()),True);ln=self.norms(list(self.lora.values()),True)
            self.emit(dict(event='microbatch',update=update,microbatch=micro,example_id=identifier,head_gradient_norm=hn,lora_gradient_norm=ln,combined_gradient_norm=math.hypot(hn,ln),**summary))
        gate.update(ces)
        hn=self.norms(list(self.heads.values()),True);ln=self.norms(list(self.lora.values()),True)
        try:
            self.t.nn.utils.clip_grad_norm_(self.parameters(),1.,error_if_nonfinite=True)
        except RuntimeError as exc:
            if 'non-finite' in str(exc).lower() or 'nonfinite' in str(exc).lower():
                raise h.Instability('nonfinite_clip_norm') from exc
            raise
        hc=self.norms(list(self.heads.values()),True);lc=self.norms(list(self.lora.values()),True)
        self.opt.step()
        headnorm=self.norms(list(self.heads.values()));loranorm=self.norms(list(self.lora.values()))
        after=self.snapshot()
        delta=lambda names:math.sqrt(sum(float((after[n].double()-before[n].double()).square().sum()) for n in names))
        receipt=dict(ce=sum(ces)/4,head_gradient_norm=hn,lora_gradient_norm=ln,pre_clip_norm=math.hypot(hn,ln),post_clip_norm=math.hypot(hc,lc),head_gradient_post_clip=hc,lora_gradient_post_clip=lc,
            head_parameter_norm=headnorm,lora_parameter_norm=loranorm,head_parameter_delta_norm=delta(['head.'+n for n in self.heads]),lora_parameter_delta_norm=delta(list(self.lora)),
            actual_lora_lr=self.opt.param_groups[0]['lr'],actual_head_lr=self.opt.param_groups[1]['lr'],train_mode=True,dropout=self.dropout)
        self.clear_gradients()
        h.require(self.audit.unchanged(full=update in (20,40,80)),'frozen base changed')
        return receipt

    @contextmanager
    def diagnostic_context(self):
        import random
        rng=(random.getstate(),self.np.random.get_state(),self.t.get_rng_state(),self.t.cuda.get_rng_state_all())
        modules=list(self.model.modules())+list(self.head.modules());modes=[m.training for m in modules]
        before=self.state_hash();h.require(self.gradients_empty(),'diagnostic gradient boundary')
        try:
            with self.t.no_grad():yield
        finally:
            random.setstate(rng[0]);self.np.random.set_state(rng[1]);self.t.set_rng_state(rng[2]);self.t.cuda.set_rng_state_all(rng[3])
            for module,mode in zip(modules,modes):module.training=mode
            h.require(self.state_hash()==before and self.gradients_empty(),'diagnostic mutation')

    def diagnostic(self, identifier, update, gate):
        h.require(self.splits[identifier]=='inner_train','diagnostic TRAIN control')
        with self.diagnostic_context():
            self.seed(7007)  # fixed probe mask; restore all RNG streams afterward
            self.model.eval();self.head.eval();eh,ez,el,ec,es=self.forward(identifier,gate,diagnostic_only=True)
            self.model.train();self.head.train();th,tz,tl,tc,ts=self.forward(identifier,gate,diagnostic_only=True)
            vectors={k:v[0].detach().cpu().numpy().copy() for k,v in [('eval_hidden',eh),('eval_standardized',ez),('eval_logits',el),('train_hidden',th),('train_standardized',tz),('train_logits',tl)]}
            telemetry=dict(example_id=identifier,eval=es,train=ts,hidden_difference_l2=float(self.t.linalg.vector_norm(th-eh)),standardized_difference_l2=float(self.t.linalg.vector_norm(tz-ez)),logit_difference_l2=float(self.t.linalg.vector_norm(tl-el)),
                vectors={k:v.tolist() for k,v in vectors.items()},rng_restored=True,no_grad=True)
        return dict(telemetry=telemetry,**vectors)

    def drift(self, baseline, current):
        # Fixed tie-break: maximum over scheduled eval-mode standardized control displacement.
        return float(self.np.linalg.norm(current['eval_standardized'].astype('float64')-baseline['eval_standardized'].astype('float64')))

    def evaluate(self, ids, gate):
        h.require(len(ids)==360 and all(self.splits[i]=='inner_val' for i in ids),'INNER_VAL only')
        labels=[];predictions=[];ces=[]
        with self.diagnostic_context():
            self.model.eval();self.head.eval()
            for identifier in ids:
                hidden,z,logits,ce,summary=self.forward(identifier,gate)
                labels.append(self.rows[identifier]['relation']);predictions.append(h.CLASSES[int(logits.argmax())]);ces.append(float(ce))
        return h.metrics(labels,predictions,ces)
