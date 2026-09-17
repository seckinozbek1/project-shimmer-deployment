"""Final bounded joint updates; reuses the proven HPO numerical backend."""
import math
import auditor_optuna_hpo as h
from auditor_optuna_hpo_backend import TorchBackend


class FinalBackend(TorchBackend):
    def update(self, ids, update, gate):
        h.require(1<=update<=896 and len(ids)==4,'final update contract')
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
        h.require(self.audit.unchanged(full=update in (20,448,896)),'frozen base changed')
        return receipt

