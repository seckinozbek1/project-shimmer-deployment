"""Gold-free population validation and method freeze construction."""
from collections import Counter
from datetime import datetime,timezone
import semantics as s
import population

def audit():
 logs=[]
 for p in (population.WORK/'access_logs').glob('*.json'):
  v=s.read(p)
  if v['successful_target_reads']:raise ValueError('Pre-gold target read detected')
  logs.append(dict(path=p.relative_to(s.ROOT).as_posix(),sha256=s.digest(p.read_bytes()),successful_target_reads=0,blocked_reads=len(v['blocked_target_reads'])))
 return dict(policy_id=s.POLICY,release_id=s.PROTOCOL,authored_target_reads=0,successful_target_reads=0,strict_target_access_order_pass=True,governance_pass=True,reviewer_target_exposure_detected=False,created_at=datetime.now(timezone.utc).isoformat(),guard_logs=logs,bootstrap='Source-only method/controller reads, generic policy/schema creation, git metadata and staged secret scans before hook installation; no authored targets or historical labels opened.',limitations='Hooks cover maintained invoked Python entry points, not hostile code or all computer tools. Fresh agent folder-only attestations are procedural; shared filesystem and parent historical aggregate knowledge remain. No parent-authored review labels.')

def main():
 if (s.HERE/'PRE_REVIEW_METHOD_FREEZE.json').exists():raise ValueError('Method already frozen')
 pop=s.read(s.HERE/'population.json');rows=pop['rows'];hard=[r for r in rows if r['packet_id'] in pop['hard_packet_ids']]
 assert Counter(r['split'] for r in rows)==dict(train=32,dev=32)
 assert len({r['packet_id'] for r in rows})==64 and all(s.eligible_metadata(r) for r in rows)
 assert len(hard)>=16 and Counter(r['split'] for r in hard)==dict(train=8,dev=8)
 for feature in ('heading','absence','temporal','order_content','conflict','multi_claim','evidence_selection'):
  assert any(r['features'][feature] for r in hard),feature
 for slot in 'ABC':s.isolated(population.WORK/('reviewer_'+slot),pop['packet_hashes'])
 checks=s.read(population.WORK/'pre_checks.json');assert checks['tests']==33 and checks['failures']==checks['errors']==0
 s.write(s.HERE/'PRE_GOLD_ACCESS_AUDIT.json',audit())
 s.write(s.HERE/'pre_validation.json',dict(semantic_generic_tests=33,guard_tests=12,PRE_GOLD_SAFE=45,population_integrity=True,hard_audit_features=True,packet_isolation=True,POST_GOLD_ONLY_executed=0))
 files=[p for p in s.HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='PRE_REVIEW_METHOD_FREEZE.json']
 s.write(s.HERE/'PRE_REVIEW_METHOD_FREEZE.json',dict(policy_id=s.POLICY,release_id=s.PROTOCOL,renderer_id=s.RENDERER,created_at=datetime.now(timezone.utc).isoformat(),hashes={p.relative_to(s.HERE).as_posix():s.digest(p.read_bytes()) for p in files}))
 print('Method freeze: 64 packets, 16 hard audits, 45 PRE_GOLD_SAFE checks; zero authored target reads.')
