"""Read-only progress from the one authorized instance; secret-safe projection."""
import json
import subprocess
import sys
from pathlib import Path
from cloud_run_common import credential_locations,require
B=Path(__file__).resolve().parents[1]/'docs/fix/auditor_optuna_hpo_run'


def main():
    for name in ['CURRENT_PHASE.json','cost.json','controller_failure.json','TERMINATION_VERIFIED.json']:
        p=B/name
        if p.exists():print(name,p.read_text().strip())
    if not (B/'activation.json').exists() or (B/'TERMINATION_VERIFIED.json').exists():return
    state=json.loads((B/'activation.json').read_text())['metadata']
    code="""import json,pathlib
p=pathlib.Path('/home/ubuntu/shimmer-auditor-optuna-hpo/evidence/events.jsonl')
if p.exists():
    with p.open('rb') as f:
        f.seek(max(0,p.stat().st_size-2000000));lines=f.read().splitlines()
    rows=[]
    for line in lines:
        try:rows.append(json.loads(line))
        except Exception:pass
    last=rows[-1] if rows else {}
    print(json.dumps({'bytes':p.stat().st_size,'last':{k:last[k] for k in ['event','trial','update','example_id'] if k in last},'last_update':[{k:r[k] for k in ['trial','update','ce','post_clip_norm'] if k in r} for r in rows if r.get('event')=='update'][-1:], 'recent_milestones':[{'event':r['event'],'trial':r.get('trial'),'update':r.get('update'),'reason':r.get('reason'),'macro_f1':r.get('metrics',{}).get('macro_f1'),'min_recall':r.get('metrics',{}).get('minimum_class_recall'),'objective':r.get('objective')} for r in rows if r.get('event') in ['reuse_admitted','inner_val','numerical_prune']][-3:]}))
else:print('No HPO events yet')
"""
    import shlex
    cmd=['ssh','-i',str(B/'ssh_identity'),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(B/'known_hosts'),'-o','ConnectTimeout=10','ubuntu@'+state['public_ip'], '/usr/bin/python3.12 -c '+shlex.quote(code)]
    r=subprocess.run(cmd,capture_output=True,timeout=25)
    require(not credential_locations(r.stdout+r.stderr,'progress'),'Possible credential in output')
    print(r.stdout.decode());print('SSH status',r.returncode)


if __name__=='__main__':main()
