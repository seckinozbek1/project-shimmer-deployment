"""Fail-closed data access: preparation never authorizes training/evaluation."""
from local_utils import HERE,read
def load_split(split,authorization=None):
    if split not in {'train','dev','holdout'}:raise ValueError('unknown split')
    if split=='holdout':raise PermissionError('Separate HOLDOUT admission required; receipt unconsumed')
    e=read(HERE/'experiment.json')
    if not e['execution_authorized'] or not e['data_admitted']:
        raise PermissionError('Experiment not authorized and V2 data not admitted')
    raise PermissionError('Future verified authorization loader must be implemented separately')
