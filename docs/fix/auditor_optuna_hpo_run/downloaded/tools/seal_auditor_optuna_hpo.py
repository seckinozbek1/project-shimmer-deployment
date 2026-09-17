"""Local cost envelope, tests and hash seal. Does not package or launch a paid run."""
import ast
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path
import auditor_optuna_hpo as h
from prepare_auditor_optuna_hpo import ROOT,D,B,E,write


def costs():
    norm=json.loads((E/'normalization.json').read_bytes())
    with (E/'training.jsonl').open() as f:training=json.loads(next(f))
    acquisition=json.loads((B/'acquisition_timing.json').read_bytes())
    launch=json.loads((B/'launch.json').read_bytes())
    initialization=json.loads((E/'initialization.json').read_bytes())
    rate=1.29;row=norm['feature_seconds']/1792;update=training['update_seconds']
    # launch.json epoch is the historical launch, not a new provider request.
    setup=acquisition['start_epoch']+acquisition['seconds']-launch['epoch']+initialization['load_seconds']
    def trial(n, conservative=False):
        u=6. if conservative else update;r=.5 if conservative else row
        evals=sum(x<=n for x in h.EVALUATIONS);diagnostics=sum(x<=n for x in h.DIAGNOSTICS)
        overhead=90. if conservative else 30.
        seconds=n*u+evals*360*r+diagnostics*2*r+overhead
        return dict(seconds=seconds,minutes=seconds/60,cost_usd=seconds*rate/3600,updates=n,evaluation_rows=evals*360,diagnostic_forwards=diagnostics*2,reset_hash_logging_allowance=overhead)
    def scenario(counts,conservative=False):
        startup=900. if conservative else setup;compatibility=896. if conservative else norm['feature_seconds'];control=32*(.5 if conservative else row)
        seconds=startup+compatibility+control+600+sum(count*trial(n,conservative)['seconds'] for n,count in counts.items())
        return dict(trials_by_stop_update=counts,seconds=seconds,minutes=seconds/60,cost_usd=seconds*rate/3600,setup_seconds=startup,one_train_pass_seconds=compatibility,control_seconds=control,teardown_reserve_seconds=600)
    return dict(historical_hourly_rate=rate,live_price_queried=False,calibration=dict(update_seconds=update,completed_joint_update_samples=1,inference_row_seconds=row,setup_seconds=setup),
        per_trial={str(n):trial(n) for n in [20,40,80]},conservative_per_trial={str(n):trial(n,True) for n in [20,40,80]},
        low=scenario({20:14,80:1}),typical=scenario({20:8,40:4,80:3}),worst=scenario({80:15},True),
        recommended_soft_budget_usd=7.,recommended_hard_ceiling_usd=9.,
        limitations='One joint update is not a throughput distribution. Reset/hash/telemetry allowances and pruning mix are projections; no HPO performance or runtime measured. Budget stop overrides trial completion; no second instance or retry.')


def seal():
    from cloud_run_common import credential_locations
    dependencies=ROOT/'.tmp/auditor_hpo_deps'
    sys.path.insert(0,str(dependencies))
    pins={name:importlib.metadata.version(name) for name in ['optuna','alembic','colorlog','sqlalchemy','Mako','typing_extensions','greenlet','colorama','MarkupSafe','packaging','tqdm','PyYAML','scipy']}
    h.require(pins['optuna']=='4.5.0','pinned Optuna')
    write(D/'optuna_dependencies.json',pins);write(D/'cost_projection.json',costs())
    files=list(D.glob('*.json'))+list((D/'clean_initialization').glob('*.json'))+[D/'.gitattributes']
    files=[p for p in files if p.name not in ('seal.json','LOCAL_VALIDATION.json','current_train_baseline.json')]
    names=['clean_auditor_hpo_initialization.py','test_auditor_optuna_hpo_clean.py','auditor_optuna_hpo.py','auditor_optuna_hpo_backend.py','auditor_optuna_hpo_remote.py','prepare_auditor_optuna_hpo.py','seal_auditor_optuna_hpo.py','test_auditor_optuna_hpo.py',
           'auditor_classifier_lora_core.py','auditor_classifier_lora_fork.py','auditor_classifier_lora_stable.py','auditor_classifier_lora_current_core.py']
    files += [ROOT/'tools'/n for n in names]
    for p in files:
        if p.suffix=='.py':ast.parse(p.read_text())
        h.require(not credential_locations(p.read_bytes(),p.as_posix()),'Possible credential in '+p.as_posix())
    write(D/'seal.json',dict(files={p.relative_to(ROOT).as_posix():h.sha(p) for p in files},paid_execution_authorized=False,immutable_prior_source='00d5dcd',artifact_reuse='hash-only verification locally; future live compatibility mandatory'))
    test=subprocess.run([sys.executable,'-m','unittest','discover','-s','tools','-p','test_auditor_optuna_hpo*.py','-v'],cwd=ROOT,capture_output=True)
    h.require(not credential_locations(test.stdout+test.stderr,'local test log'),'Possible credential in test log')
    (D/'local_tests.log').write_bytes(test.stdout+test.stderr)
    h.require(test.returncode==0,'Local tests failed: see local_tests.log')
    scope=subprocess.run([sys.executable,'tools/auditor_optuna_hpo_remote.py','scope'],cwd=ROOT,capture_output=True)
    h.require(scope.returncode==0,'Scope failed: '+scope.stderr.decode())
    (D/'scope.log').write_bytes(scope.stdout+scope.stderr)
    import re
    count=int(re.search(rb'Ran (\d+) tests',test.stderr).group(1))
    write(D/'LOCAL_VALIDATION.json',dict(verdict='AUDITOR_OPTUNA_HPO_CLEAN_READY',tests=count,passed=count,scope_passed=True,seal_sha256=h.sha(D/'seal.json'),
        cloud_resources_created=0,cloud_queried=False,real_model_inference=False,real_model_training=False,real_model_weights_deserialized=False,cached_feature_linear_head_fitted=True,initialization_inner_val_exposure=0,existing_dev_access=0,holdout_access=0,protected_access=0,producer_execution=False,push=False,
        limits='Local deterministic fixtures prove orchestration/contracts, not actual GPU compatibility or stability. No HPO trial on real data has run.'))
    print(json.dumps(dict(tests=count,scope=True,seal_sha256=h.sha(D/'seal.json'),costs=costs()),indent=2))


if __name__=='__main__':seal()
