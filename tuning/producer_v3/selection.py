"""Prospective quality-first selection; undefined/nonfinite metrics fail closed."""
import math
CATASTROPHIC=('invented_evidence','invented_rule','confident_wrong_match_divergence','truncation','producer_source_copy','governance_violations')

def passes(metrics,gates):
    if metrics.get('count')!=84:return False
    if set(metrics.get('catastrophic',{}))!=set(CATASTROPHIC):return False
    if any(metrics['catastrophic'][k]!=0 for k in CATASTROPHIC):return False
    for direction,thresholds in gates.items():
        for name,bound in thresholds.items():
            value=metrics.get(name)
            if type(value) not in (int,float) or not math.isfinite(value):return False
            if direction=='minimum' and value<bound:return False
            if direction=='maximum' and value>bound:return False
    return True

def select(checkpoints,spec):
    if sorted(x['step'] for x in checkpoints)!=spec['checkpoint_steps']:raise ValueError('Incomplete V3 schedule')
    candidates=[x for x in checkpoints if passes(x['metrics'],spec['selection_gates'])]
    if not candidates:return dict(verdict='PRODUCER_V3_FAIL',action=spec['final_stop_rule'])
    best=sorted(candidates,key=lambda x:(-x['metrics']['semantic_completeness'],-x['metrics']['typed_gaps_f1'],x['step'],x['adapter_sha256']))[0]
    return dict(verdict='PRODUCER_V3_PASS',selected_step=best['step'],adapter_sha256=best['adapter_sha256'])
