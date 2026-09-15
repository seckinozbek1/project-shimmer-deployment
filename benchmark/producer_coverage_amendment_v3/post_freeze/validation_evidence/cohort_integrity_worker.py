"""Independent read-only catalog verification under the frozen V3 guard."""
import sys,json
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'benchmark/producer_coverage_amendment_v3'))
import access_guard
G=access_guard.install('POST_GOLD')
import semantics as s
key=sys.argv[1]
if key=='historical_contract_ab':root=ROOT/'docs/fix/contract_model_ab_20260915';name='ARTIFACT_HASHES.json';member=None
else:
 root=ROOT/'benchmark'/key;name='freeze.json' if key.startswith('first_tuning_') else 'release_freeze.json';member='hashes'
manifest=s.read(root/name);values=manifest[member] if member else manifest
entries={}
for relative,expected in values.items():
 path=(root/relative).resolve()
 assert path.is_relative_to(root.resolve())
 actual=s.digest(path.read_bytes())
 if actual!=expected:raise ValueError('Historical hash drift: '+relative)
 entries[relative]=actual
binding=G.verify_post_phase()
report=dict(catalog=key,root=root.relative_to(ROOT).as_posix(),manifest_name=name,manifest_sha256=s.digest((root/name).read_bytes()),count=len(entries),actual_hashes=entries,label_freeze_commit=binding['commit'],worker_sha256=s.digest(Path(__file__).read_bytes()))
s.write(ROOT/'output/producer_coverage_amendment_v3/catalog_proofs'/(key+'.json'),report)
print(json.dumps(dict(catalog=key,verified=len(entries),mismatches=0)))
