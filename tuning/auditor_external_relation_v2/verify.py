"""Offline byte verification and fail-closed receipt check, no weights/tokenizer."""
from local_utils import *
def main():
    f=read(HERE/'freeze.json')
    for path,h in f['files'].items():assert sha(ROOT/path)==h,path
    for path,h in f['input_bindings'].items():assert sha(ROOT/path)==h,path
    assert not read(HERE/'holdout_receipt.json')['consumed']
    e=read(HERE/'experiment.json');assert not e['execution_authorized'] and not e['training_authorized'] and not e['cloud_authorized']
    from access import load_split
    for s in ['train','dev','holdout']:
        try:load_split(s,{'approved':True})
        except PermissionError:pass
        else:raise AssertionError('Unauthorized data access')
    print(json.dumps(dict(files_verified=len(f['files']),inputs_verified=len(f['input_bindings']),holdout_unconsumed=True,verdict=f['verdict'])))
if __name__=='__main__':main()
