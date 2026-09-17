"""TRAIN-only sequential Optuna contracts. No model imports or cloud operations."""
import copy
import hashlib
import json
import math
from pathlib import Path
from collections import Counter

CLASSES = ['MATCH', 'DIVERGENCE', 'OMISSION', 'ADDITION']
PARAMS = {'lora_peak_lr', 'head_lr', 'warmup_steps', 'dropout'}
DIAGNOSTICS = (0, 1, 2, 5, 10, 20, 40, 80)
EVALUATIONS = (20, 40, 80)
OPTUNA_VERSION = '4.5.0'
FORBIDDEN = ('external_dev', 'historical_dev', 'shorter', 'longer', 'holdout', 'protected')
ARTIFACT_HASHES = {
    'hpo_head-200.safetensors': '8a9f94c6a78c01c15ddb4ac07e7e80586a7d1515aefcfc6f68040fc9181aa6e3',
    'hpo_mean.npy': 'f812e63fec063220b9eaf27c3e9782005abad3cb66293491b55f93b38ad8aecf',
    'hpo_std.npy': 'be4270e87f7df6ae7f9312bbeabc894c2f794ec897d4e9c5deeb52d84cdd2b68',
    'current_train_features.npy': '06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


class DataBoundary:
    """Reject forbidden paths BEFORE open; only explicitly bound data may deserialize."""
    def __init__(self, bindings):
        self.bindings = {str(Path(p).resolve()): h for p, h in bindings.items()}
        self.access_counts = dict.fromkeys(FORBIDDEN, 0)
        self.allowed_reads = Counter()
        self.denials = []

    def check(self, path):
        p = str(Path(path).resolve())
        low = p.lower().replace('\\', '/')
        kind = next((k for k in FORBIDDEN if k in low), None)
        mixed = any(k in low for k in ('/auditor_classifier_lora/records.json', '/auditor_v2_diagnostic/records.json', '/auditor_canonical_execution/dataset.json', 'challenges.json'))
        if kind or mixed or p not in self.bindings:
            self.denials.append(kind or 'unbound_or_mixed')
            raise PermissionError('HPO data access denied before open')
        return Path(p)

    def read(self, path, jsonl=False):
        p = self.check(path)
        raw = p.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == self.bindings[str(p)], 'data hash mismatch')
        self.allowed_reads[str(p)] += 1
        return [json.loads(x) for x in raw.splitlines()] if jsonl else json.loads(raw)

    def receipt(self):
        return dict(access_counts=self.access_counts, allowed_reads=dict(self.allowed_reads), denied_attempts=self.denials)


def source_family(row):
    if row['example_id'].startswith('shimmer2-auditor-'):
        return 'historical'
    dataset = row.get('dataset', '').lower()
    if 'paws' in dataset:
        return 'PAWS'
    if 'wikiatomic' in dataset:
        return 'WikiAtomic'
    raise ValueError('Unknown TRAIN source family')


def freeze_split(rows):
    require(len(rows) == 1792 and len({r['example_id'] for r in rows}) == 1792, 'TRAIN population')
    require(Counter(r['relation'] for r in rows) == Counter(dict.fromkeys(CLASSES, 448)), 'class balance')
    assignments = []
    for label in CLASSES:
        group = [r for r in rows if r['relation'] == label]
        for historical, nval, total in [(True, 10, 48), (False, 80, 400)]:
            stratum = [r for r in group if (source_family(r) == 'historical') == historical]
            require(len(stratum) == total, 'source balance')
            ordered = sorted(stratum, key=lambda r: (digest(['inner-split', 7, label, source_family(r), r['example_id']]), r['example_id']))
            for i, r in enumerate(ordered):
                assignments.append(dict(example_id=r['example_id'], relation=label, source_family=source_family(r), split='inner_val' if i < nval else 'inner_train'))
    assignments.sort(key=lambda r: r['example_id'])
    train = [r for r in assignments if r['split'] == 'inner_train']
    val = [r for r in assignments if r['split'] == 'inner_val']
    return dict(seed=7, method='sha256(canonical([inner-split,7,class,source_family,id])); ascending per historical/external class stratum', assignments=assignments,
                inner_train_sha256=digest(train), inner_val_sha256=digest(val), split_sha256=digest(assignments))


def config():
    return dict(optuna_version=OPTUNA_VERSION, sampler=dict(name='TPESampler', seed=7, n_startup_trials=10),
        pruner=dict(name='SuccessiveHalvingPruner', min_resource=20, reduction_factor=2, min_early_stopping_rate=0, bootstrap_count=0),
        max_trials=15, max_updates=80, n_jobs=1, microbatch=1, accumulation=4,
        search=dict(lora_peak_lr=dict(low=1e-6, high=1e-4, log=True), head_lr=dict(low=1e-4, high=1e-3, log=True), warmup_steps=[0, 5, 10, 20, 40], dropout=[0.0, 0.05]),
        optimizer=dict(name='AdamW', betas=[.9, .999], eps=1e-8, weight_decay=0, max_grad_norm=1., scheduler_after_warmup=None, head_regularization=.001),
        diagnostic_updates=list(DIAGNOSTICS), evaluation_updates=list(EVALUATIONS), seed=7,
        objective='0.75*macro_f1 + 0.25*minimum_class_recall', candidate=dict(macro_f1=.60, every_class_recall=.45),
        ceiling=dict(mean_formula='max(10*ln(4),20*current_compatibility_train_ce)', micro_multiplier=4, prior_failure_ce=134.57772827148438),
        initial_head_exposed_to_inner_val=False, normalization_exposed_to_inner_val=False,
        full_training_auto_execute=False, cloud_authorized=False)


def sample(trial):
    p = dict(lora_peak_lr=trial.suggest_float('lora_peak_lr', 1e-6, 1e-4, log=True),
             head_lr=trial.suggest_float('head_lr', 1e-4, 1e-3, log=True),
             warmup_steps=trial.suggest_categorical('warmup_steps', [0, 5, 10, 20, 40]),
             dropout=trial.suggest_categorical('dropout', [0.0, 0.05]))
    validate_params(p)
    return p


def validate_params(p):
    require(set(p) == PARAMS, 'exactly four parameters')
    require(1e-6 <= p['lora_peak_lr'] <= 1e-4 and 1e-4 <= p['head_lr'] <= 1e-3, 'LR bounds')
    require(p['warmup_steps'] in [0, 5, 10, 20, 40] and p['dropout'] in [0., .05], 'categorical bounds')


def lora_lr(p, update):
    validate_params(p)
    require(1 <= update <= 80, 'update cap')
    return p['lora_peak_lr'] * (min(1., update / p['warmup_steps']) if p['warmup_steps'] else 1.)


def schedule(split):
    ids = [r['example_id'] for r in split['assignments'] if r['split'] == 'inner_train']
    require(len(ids) == 1432, 'inner train schedule')
    ids.sort(key=lambda i: (digest(['trial-training-order', 7, i]), i))
    return [ids[i:i+4] for i in range(0, 320, 4)]


def metrics(labels, predictions, ces):
    require(len(labels) == len(predictions) == len(ces) and len(labels) > 0, 'evaluation lengths')
    matrix = [[0]*4 for _ in CLASSES]
    for y, p in zip(labels, predictions):
        matrix[CLASSES.index(y)][CLASSES.index(p)] += 1
    recall = {}; f1 = []
    for i, label in enumerate(CLASSES):
        tp = matrix[i][i]; actual = sum(matrix[i]); predicted = sum(r[i] for r in matrix)
        recall[label] = tp/actual if actual else 0.
        f1.append(2*tp/(actual+predicted) if actual+predicted else 0.)
    require(all(math.isfinite(x) and x >= 0 for x in ces), 'finite evaluation CE')
    return dict(accuracy=sum(matrix[i][i] for i in range(4))/len(labels), macro_f1=sum(f1)/4, per_class_recall=recall,
                minimum_class_recall=min(recall.values()), ce=sum(ces)/len(ces), confusion_matrix=matrix)


def objective_value(m):
    require(all(math.isfinite(m[k]) for k in ('macro_f1', 'minimum_class_recall', 'ce')), 'finite metric')
    return .75*m['macro_f1'] + .25*m['minimum_class_recall']


class Instability(Exception):
    pass


class Stability:
    def __init__(self, baseline_ce):
        require(math.isfinite(baseline_ce) and baseline_ce >= 0, 'baseline CE')
        self.mean_ceiling = max(10*math.log(4), 20*baseline_ce)
        self.micro_ceiling = 4*self.mean_ceiling

    def finite(self, *values):
        if not all(math.isfinite(float(x)) for x in values):
            raise Instability('nonfinite')

    def micro(self, ce):
        self.finite(ce)
        if ce > self.micro_ceiling:
            raise Instability('microbatch_ce_explosion')

    def update(self, ces):
        require(len(ces) == 4, 'accumulation')
        for ce in ces:
            self.micro(ce)
        if sum(ces)/4 > self.mean_ceiling:
            raise Instability('mean_update_ce_explosion')


class CleanReset:
    """Immutable numeric snapshots. Backend supplies byte-exact hashes and fresh optimizer."""
    def __init__(self, backend):
        self.initial = copy.deepcopy(backend.snapshot())
        self.initial_hash = backend.state_hash()

    def reset(self, backend, params):
        backend.discard_optimizer()
        backend.restore(copy.deepcopy(self.initial))
        backend.clear_gradients()
        backend.set_dropout(params['dropout'])
        backend.seed(7)
        require(backend.state_hash() == self.initial_hash, 'trial reset identity')
        require(backend.gradients_empty(), 'stale gradients')
        backend.new_optimizer(params)
        require(backend.optimizer_empty(), 'optimizer state leakage')


def winner_key(result):
    m = result['metrics']
    return (-objective_value(m), -m['macro_f1'], -m['minimum_class_recall'], m['ce'], result['representation_drift'], result['params']['lora_peak_lr'], result['trial_number'])


def freeze_winner(results):
    eligible = [r for r in results if r['stable'] and r['updates'] == 80 and r['metrics']['macro_f1'] >= .60 and r['metrics']['minimum_class_recall'] >= .45]
    if not eligible:
        return dict(verdict='AUDITOR_OPTUNA_HPO_NO_CANDIDATE', full_training_auto_execute=False)
    winner = min(eligible, key=winner_key)
    return dict(verdict='AUDITOR_OPTUNA_HPO_CANDIDATE', trial_number=winner['trial_number'], hyperparameters={k:winner['params'][k] for k in sorted(PARAMS)},
                metrics=winner['metrics'], full_training_auto_execute=False,
                future_separate_design=dict(train_rows=1792, normalization_fit_rows=1792, head_fit_rows=1792, head_updates=200, clean_classifier_fork=True, reuse_hpo_head=False, updates=896, checkpoints=[448,896], authorization_required=True))


def create_study(optuna, storage=None):
    require(optuna.__version__ == OPTUNA_VERSION, 'Optuna version')
    return optuna.create_study(direction='maximize', study_name='auditor-inner-train-stability-seed7', storage=storage, load_if_exists=False,
        sampler=optuna.samplers.TPESampler(seed=7, n_startup_trials=10),
        pruner=optuna.pruners.SuccessiveHalvingPruner(min_resource=20, reduction_factor=2, min_early_stopping_rate=0, bootstrap_count=0))


def run_study(optuna, backend, split, baseline_ce, emit, storage=None):
    """Backend admission must finish before entering; no cloud/model loader here."""
    require(backend.admitted, 'reuse admission required')
    study = create_study(optuna, storage)
    reset = CleanReset(backend); plan = schedule(split); completed = []
    control = min((r['example_id'] for r in split['assignments'] if r['split']=='inner_train'), key=lambda i:(digest(['control',7,i]),i))
    val = [r['example_id'] for r in split['assignments'] if r['split']=='inner_val']
    def objective(trial):
        require(trial.number < 15, 'trial cap')
        params = sample(trial); backend.trial_number=trial.number; reset.reset(backend, params)
        gate = Stability(baseline_ce); drift = 0.
        try:
            baseline = backend.diagnostic(control, 0, gate)
            emit(dict(event='diagnostic', trial=trial.number, update=0, **baseline['telemetry']))
            for update, ids in enumerate(plan, 1):
                backend.set_lrs(lora_lr(params, update), params['head_lr'])
                receipt = backend.update(ids, update, gate)
                emit(dict(event='update', trial=trial.number, update=update, **receipt))
                if update in DIAGNOSTICS:
                    diagnostic = backend.diagnostic(control, update, gate)
                    drift = max(drift, backend.drift(baseline, diagnostic))
                    emit(dict(event='diagnostic', trial=trial.number, update=update, **diagnostic['telemetry']))
                if update in EVALUATIONS:
                    m = backend.evaluate(val, gate)
                    value = objective_value(m)
                    emit(dict(event='inner_val', trial=trial.number, update=update, metrics=m, objective=value))
                    trial.report(value, update)
                    if update in (20,40) and trial.should_prune():
                        trial.set_user_attr('reason','successive_halving')
                        raise optuna.TrialPruned('successive_halving')
            result = dict(trial_number=trial.number, params=params, metrics=m, representation_drift=drift, stable=True, updates=80)
            completed.append(result); trial.set_user_attr('completed_result',result)
            return value
        except Instability as exc:
            emit(dict(event='numerical_prune', trial=trial.number, reason=str(exc)))
            trial.set_user_attr('reason',str(exc))
            raise optuna.TrialPruned(str(exc)) from exc
        finally:
            backend.clear_gradients()
            backend.discard_optimizer()
    study.optimize(objective, n_trials=15, n_jobs=1, gc_after_trial=True, catch=())
    return study, freeze_winner(completed)


class ReuseAdmission:
    """One full TRAIN pass plus 16 paired controls, against the current cache."""
    def __init__(self, np, features, mean, std, weight, bias, rows, controls, expected_runtime, baseline):
        self.np=np;self.features=features;self.mean=mean;self.std=std;self.weight=weight;self.bias=bias
        self.rows=rows;self.controls=controls;self.expected_runtime=expected_runtime;self.baseline=baseline
        self.passed=False;self.full_rows=0

    def run(self, runtime, observe, select, remove_reference):
        require(not self.passed and self.full_rows==0,'duplicate compatibility pass')
        require(runtime==self.expected_runtime,'exact runtime mismatch')
        require(len(self.rows)==1792 and len(self.controls)==16,'compatibility population')
        by={r['example_id']:r for r in self.rows};index={r['example_id']:i for i,r in enumerate(self.rows)}
        def check(row, live):
            i=index[row['example_id']];h=self.features[i];z=(h-self.mean)/self.std;logits=z@self.weight.T+self.bias
            for name,target in [('hidden',h),('standardized',z),('logits',logits)]:
                value=live[name]
                require(value.shape==target.shape and self.np.isfinite(value).all() and self.np.allclose(value,target,rtol=1e-4,atol=2e-4),'current-cache '+name)
            require(int(live['logits'].argmax())==int(logits.argmax()),'current-cache prediction')
        select('reference')
        reference={i:observe(by[i]) for i in self.controls}
        select('classifier_fork')
        for i in self.controls:
            candidate=observe(by[i]);check(by[i],reference[i]);check(by[i],candidate)
            for key in ('hidden','standardized','logits'):
                require(self.np.allclose(reference[i][key],candidate[key],rtol=1e-4,atol=2e-4),'reference/fork '+key)
        remove_reference()
        predictions=[];ces=[];labels=[]
        fit_ids=set(self.baseline['example_ids'])
        for row in self.rows:
            live=observe(row);check(row,live);self.full_rows+=1
            if row['example_id'] not in fit_ids:continue
            logits=live['logits'].astype(self.np.float64);label=CLASSES.index(row['relation']);mx=logits.max()
            labels.append(row['relation'])
            ces.append(float(mx+self.np.log(self.np.exp(logits-mx).sum())-logits[label]))
            predictions.append(CLASSES[int(logits.argmax())])
        m=metrics(labels,predictions,ces)
        require(predictions==[CLASSES[i] for i in self.baseline['predicted_indices']],'INNER_TRAIN HPO head prediction equality')
        require(self.baseline['ce_range'][0]<=m['ce']<=self.baseline['ce_range'][1],'INNER_TRAIN HPO head CE')
        require(abs(m['macro_f1']-self.baseline['metrics']['macro_f1'])<1e-12,'INNER_TRAIN HPO head F1')
        self.passed=True
        return dict(passed=True,full_train_passes=1,rows=self.full_rows,controls=16,ce=m['ce'],metrics=m)
