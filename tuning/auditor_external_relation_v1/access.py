"""Fail-closed future data admission, including separately authorized HOLDOUT."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def load_split(split, admission=None):
    if split not in {'train','dev','holdout'}:
        raise ValueError('unknown split')
    # No execution is authorized by this preparation task, even with a made-up receipt.
    experiment=json.loads((HERE/'experiment.json').read_text(encoding='utf8'))
    if not experiment['execution_authorized'] or not experiment['data_admitted']:
        raise PermissionError('Data release not admitted; no training/evaluation authorization')
    if split=='holdout':
        raise PermissionError('Separate HOLDOUT admission and implementation required; receipt unconsumed')
    if not admission:
        raise PermissionError('Separate experiment admission required')
    return [json.loads(line) for line in (HERE/'examples.jsonl').read_text(encoding='utf8').splitlines() if json.loads(line)['split']==split]
