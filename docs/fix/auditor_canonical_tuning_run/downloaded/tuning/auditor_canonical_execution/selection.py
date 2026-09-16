"""Exact frozen Auditor quality eligibility and tie-break; no generation."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'second_domain_agnostic_v2'))
import runtime as r

def select(checkpoints,spec):
    assert sorted(x['step'] for x in checkpoints)==[60,120]
    assert all(x['metrics']['count']==60 for x in checkpoints)
    eligible=[x for x in checkpoints if r.selection_pass(x['metrics'],spec['selection_gates'])]
    if not eligible:return dict(verdict='AUDITOR_TUNING_FAIL',eligible_steps=[],selected_step=None)
    best=sorted(eligible,key=lambda x:(-x['metrics']['macro_relation_f1'],-x['metrics']['accepted_semantic_outcomes'],x['step'],x['adapter_sha256']))[0]
    return dict(verdict='AUDITOR_TUNING_PASS',eligible_steps=[x['step'] for x in eligible],selected_step=best['step'],adapter_sha256=best['identity']['files']['adapter_model.safetensors'],tie_break_adapter_identity_sha256=best['adapter_sha256'])
