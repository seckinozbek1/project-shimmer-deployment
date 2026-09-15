"""Review selection revision only; frozen acceptance and benchmark are imported."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import sys
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'benchmark/first_tuning_experiment_v1'))
import registration as old
h = old.h
read, write, digest = old.read, old.write, old.digest
REVISION = 'first-tuning-review-cohort-v2'
SEED = 'shimmer-review-rebalance-20260915-v2'
PROFILE = old.VERSION
HELD = ('astronomy', 'ecology')


def is_held(row):
    return row['domain'] in HELD


def risk(row):
    """Admin-only source difficulty proxies; never reviewer-visible answers."""
    f = old.feature_set(row)
    return (4 * row['expected_refusal'] + 3 * row['expected_uncertainty'] +
            3 * ('information_gap' in f) + 3 * ('contradictory_source' in f) +
            2 * ('context_ownership' in f) + 2 * ('multi_span' in f) +
            2 * ('evidence_selection' in f) + len(row['hard_negative_tags']))


def choose(rows, size, roles, double=False):
    """Hard role caps; semantic coverage deficits, family diversity, then risk.

    TRAIN/DEV producers are substantive only. Auditor refusal coverage is
    reserved before diversity filling. Second review reserves four refusals per
    role, twelve gaps and twelve uncertainty cases before maximizing families,
    templates/domains/relations and source difficulty. Stable SHA-256 breaks ties.
    """
    chosen = []
    pool = {r['example_id']: r for r in rows}
    while len(chosen) < size:
        rc = Counter(r['role'] for r in chosen)
        fam = Counter(r['document_family'] for r in chosen)
        templates = Counter(r['template_family'] for r in chosen)
        domains = Counter(r['domain'] for r in chosen)
        rel = Counter(r['abstract_relation'] for r in chosen)
        refusals = Counter(r['role'] for r in chosen if r['expected_refusal'])
        gaps = sum('information_gap' in old.feature_set(r) for r in chosen)
        uncertain = sum(r['expected_uncertainty'] for r in chosen)
        def key(r):
            f = old.feature_set(r)
            refusal_need = r['expected_refusal'] and refusals[r['role']] < (4 if double or r['role'] == 'auditor' else 0)
            gap_need = double and gaps < 12 and 'information_gap' in f
            uncertainty_need = double and uncertain < 12 and r['expected_uncertainty']
            return (refusal_need, gap_need, uncertainty_need,
                    r['document_family'] not in fam, r['template_family'] not in templates,
                    r['domain'] not in domains, r['abstract_relation'] not in rel,
                    -fam[r['document_family']], risk(r), -rel[r['abstract_relation']],
                    -domains[r['domain']], digest((SEED+r['example_id']).encode()))
        candidates = [r for r in pool.values() if rc[r['role']] < roles[r['role']]]
        if not candidates:
            raise ValueError('Selection role constraints infeasible')
        row = max(candidates, key=key)
        chosen.append(row)
        del pool[row['example_id']]
    return sorted(r['example_id'] for r in chosen)


def selection(rows):
    index = {r['example_id']: r for r in rows}
    held = sorted(r['example_id'] for r in rows if is_held(r))
    if len(held) != 72:
        raise ValueError('Frozen held-out population changed')
    parts = {'held_out': held}
    for split, size, producers in [('train', 78, 32), ('dev', 40, 16)]:
        candidates = [r for r in rows if r['split'] == split and not is_held(r)
                      and (r['role'] == 'auditor' or r['abstract_relation'] == 'EXTRACTED')]
        parts[split] = choose(candidates, size, {'producer': producers, 'auditor': size-producers})
    extra = []
    for split, template in [('test', 'attributed_dialogue'), ('sealed_adversarial', 'scope_notice')]:
        candidates = [r for r in rows if r['split'] == split and r['template_family'] == template and r['role'] == 'auditor']
        extra += choose(candidates, 1, {'producer': 0, 'auditor': 1})
    parts['additional_evaluation'] = extra
    first = sorted(i for ids in parts.values() for i in ids)
    second = choose([index[i] for i in first], 48, {'producer': 24, 'auditor': 24}, double=True)
    return first, second, parts


def verify_frozen():
    old.verify_frozen()
    frozen = read(HERE/'freeze.json')
    for name, expected in frozen['hashes'].items():
        if digest((HERE/name).read_bytes()) != expected:
            raise ValueError('Cohort revision freeze drift: '+name)
    if frozen['acceptance_sha256'] != digest((old.HERE/'acceptance_registration.json').read_bytes()):
        raise ValueError('Acceptance profile drift')
    active = read(ROOT/'benchmark/first_tuning_review_active.json')
    if (active['revision'] != REVISION or active['directory'] != HERE.relative_to(ROOT).as_posix() or
        active['freeze_sha256'] != digest((HERE/'freeze.json').read_bytes())):
        raise ValueError('This is not the active frozen review cohort')
    return True


def manifests():
    return read(HERE/'cohort.json'), read(HERE/'double_review.json'), read(HERE/'export_admin_manifest.json')


def cohort_hash():
    return digest((HERE/'cohort.json').read_bytes())


def export_binding(ids):
    index = {r['example_id']: r for r in old.records()}
    return dict(revision=REVISION, cohort_sha256=cohort_hash(),
                payload_sha256=digest(dict(instructions_sha256=digest((HERE/'reviewer_instructions.md').read_bytes()),
                                           packets=[h.packet(index[i]) for i in sorted(ids)])))


def packet(row, binding):
    p = h.packet(row)
    p['response_template'] = dict(binding=binding, review=p['response_template'])
    return p


def export_files(ids):
    """Explicit byte allowlist from frozen legitimate input plus opaque binding."""
    index = {r['example_id']: r for r in old.records()}
    binding = export_binding(ids)
    files = {'INSTRUCTIONS.md': (HERE/'reviewer_instructions.md').read_bytes()}
    for ident in ids:
        p = packet(index[ident], binding)
        files[p['packet_id']+'.json'] = (json.dumps(p, indent=2, ensure_ascii=False)+'\n').encode('utf-8')
        text = '# Independent semantic review\n\nPacket: '+p['packet_id']+'\n\n'+p['instructions']+'\n\n'
        text += '```json\n'+json.dumps(p['input'], indent=2, ensure_ascii=False)+'\n```\n\n'
        text += '## Response template (pending, not a submitted review)\n\n```json\n'+json.dumps(p['response_template'], indent=2)+'\n```\n'
        files[p['packet_id']+'.md'] = text.encode('utf-8')
    return files


def check_names(actual, expected):
    if set(actual) != set(expected):
        raise ValueError('Unapproved export file set')


def check_bytes(actual, expected):
    if actual != expected:
        raise ValueError('Export differs from approved blank material')


def audit_export(folder, ids):
    folder = Path(folder)
    expected = export_files(ids)
    paths = list(folder.rglob('*'))
    if any(p.is_symlink() or not p.is_file() or p.parent != folder for p in paths):
        raise ValueError('Unexpected export entry')
    check_names([p.name for p in paths], expected)
    for p in paths:
        if p.name in expected:
            check_bytes(p.read_bytes(), expected[p.name])
    return {'files': len(paths), 'packets': len(ids), 'leakage_findings': 0}


def check_binding(envelope, exports=None):
    """No packet-ID-only compatibility: unbound and obsolete returns fail closed."""
    exports = exports if exports is not None else manifests()[2]
    if not isinstance(envelope, dict) or set(envelope) != {'binding', 'review'}:
        raise ValueError('Obsolete or unbound review envelope')
    for name, manifest in exports.items():
        if envelope['binding'] == manifest['binding']:
            review = envelope['review']
            if not isinstance(review, dict) or review.get('packet_id') not in manifest['packet_ids']:
                raise ValueError('Packet is not assigned in this export')
            return name
    raise ValueError('Obsolete cohort or export hash; review rejected')


def training_candidates(rows, accepted_targets):
    """Only the prospectively selected TRAIN/DEV; held-out takes precedence."""
    selected = set(read(HERE/'cohort.json')['ids'])
    return [r for r in rows if r['example_id'] in selected and r['example_id'] in accepted_targets
            and not is_held(r) and r['split'] in ('train', 'dev')]
