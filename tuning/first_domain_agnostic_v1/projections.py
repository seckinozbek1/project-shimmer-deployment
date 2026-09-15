"""Static planning ranges, never measurements of QLoRA or model performance."""
from collections import Counter
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def project():
    memory={};work={}
    gib=2**30
    for role in PINS:
        cfg=read(cached(role)/'config.json');spec=read(HERE/role/'experiment.json')
        h=cfg['hidden_size'];kv=h//cfg['num_attention_heads']*cfg['num_key_value_heads'];i=cfg['intermediate_size'];layers=cfg['num_hidden_layers']
        linear=layers*(2*h*h+2*h*kv+3*h*i)
        # PEFT preparation may upcast embedding + output head to FP32.
        unquantized=2*cfg['vocab_size']*h*4/gib
        quantized=linear*.56/gib
        adapters=spec['architecture']['adapter_parameters']*16/gib # FP32 parameter, gradient, two Adam moments
        activation=[2.,5.] if role=='producer' else [1.5,4.]
        reserve=[2.,4.]
        total=[quantized+unquantized+adapters+activation[x]+reserve[x] for x in (0,1)]
        memory[role]=dict(classification='TRAINING_MEMORY_PROJECTION',quantized_linear_parameters=linear,
            quantized_linear_gib=round(quantized,3),fp32_embeddings_and_head_gib=round(unquantized,3),
            adapter_gradients_optimizer_gib=round(adapters,3),checkpointed_activation_gib=activation,
            cuda_workspace_allocator_gib=reserve,total_gib=[round(v,2) for v in total],
            host_ram_gib=[16,32],assumptions='one role, batch 1, eager attention, checkpointing, observed sequence ceiling; no model duplication')
        lengths=read(HERE/role/'token_lengths.json')['rows']
        train_tokens=2*sum(r['total'] for r in lengths if r['split']=='train')
        dev_tokens=2*sum(r['target'] for r in lengths if r['split']=='dev')
        # Wide engineering assumptions, explicitly not borrowed benchmark timings.
        work[role]=dict(train_sequence_tokens=train_tokens,dev_target_tokens_reference=dev_tokens,
            assumed_training_sequence_tokens_per_second=[80,250] if role=='producer' else [120,400],
            assumed_decode_tokens_per_second=[20,60] if role=='producer' else [30,90],
            training_minutes=([train_tokens/250/60+1,train_tokens/80/60+3] if role=='producer' else [train_tokens/400/60+1,train_tokens/120/60+3]))
    phases={
        'setup_including_model_acquisition_hydration':[5,15],
        'producer_training':work['producer']['training_minutes'],
        'producer_dev_evaluation':[2,8],
        'auditor_training':work['auditor']['training_minutes'],
        'auditor_dev_evaluation':[1,4],
        'protected_base_evaluation':[5,16],
        'protected_tuned_evaluation':[5,16],
        'teardown':[1,3],
    }
    total=[sum(v[i] for v in phases.values()) for i in (0,1)]
    return dict(classification='TRAINING_MEMORY_PROJECTION',measurements=False,
        recommended_first_candidate='one A10 24 GB class, sequential roles',
        prior_observed_vram_mib=23028,prior_reference_hourly_usd=1.29,current_inventory_queried=False,
        memory=memory,work=work,phase_minutes={k:[round(x,2) for x in v] for k,v in phases.items()},
        total_wall_minutes=[round(x,2) for x in total],gpu_rental_minutes=[round(x,2) for x in total],
        total_cost_usd=[round(x/60*1.29,2) for x in total],
        uncertainty='Planning assumptions, not benchmarks. Kernel compatibility, download throughput and generated length unmeasured. Stop on OOM; no automatic larger instance or parameter sweep.',
        minimum_higher_class_if_needed='single 40 GB GPU, only after separate revised authorization',
        inference_goal_separate=dict(marginal_ordinary_run_usd=[0,.10],wall_seconds=120,evidence_from_this_task=False),
        training_cost_is_one_time=True)

if __name__=='__main__':write(HERE/'projections.json',project())
