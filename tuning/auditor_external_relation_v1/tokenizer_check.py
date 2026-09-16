"""Pinned local tokenizer and original normalized classifier prompt; no weights."""
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CEILING=1056

def load():
    os.environ.update(USE_TORCH='0',USE_TF='0',USE_FLAX='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
    sys.path.insert(0,str(ROOT/'tools'))
    from auditor_linear_core import normalized_input
    sys.path.insert(0,str(ROOT/'tuning/second_domain_agnostic_v2'))
    import runtime
    tok=runtime.old.tokenizer('auditor')
    def lengths(row):
        value,aliases=normalized_input(row['input'])
        prompt=tok.apply_chat_template(runtime.task_messages(dict(role='auditor',input=value)),tokenize=False,add_generation_prompt=True)
        return dict(prompt_tokens=len(tok(prompt,add_special_tokens=False)['input_ids']),
            source_tokens=sum(len(tok(s['text'],add_special_tokens=False)['input_ids']) for s in value['source_spans']),
            candidate_tokens=len(tok(value['extraction'],add_special_tokens=False)['input_ids']),aliases=len(aliases))
    return lengths
