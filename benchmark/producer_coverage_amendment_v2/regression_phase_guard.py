"""Require a committed label freeze before any authored-data regression."""
import json
import semantics as s

def require_label_commit(commit,base=None,git_reader=None):
 base=s.HERE if base is None else base
 manifest=base/'blind_evidence/PRE_GOLD_FREEZE.json'
 if not manifest.is_file():raise ValueError('Label freeze required before authored-data regression')
 if not commit or len(commit)!=40:raise ValueError('Full label-freeze commit required')
 if git_reader is None:
  s.sys.path.insert(0,str(s.ROOT/'tools'));from prepare_cloud_run import git
  git_reader=lambda ref:git(s.ROOT,'show',ref)
 relative=manifest.relative_to(s.ROOT).as_posix()
 if json.loads(git_reader(commit+':'+relative))!=s.read(manifest):raise ValueError('Label freeze not present in supplied commit')
 return True

if __name__=='__main__':
 import argparse,subprocess,sys
 parser=argparse.ArgumentParser();parser.add_argument('--label-commit',required=True);args=parser.parse_args();require_label_commit(args.label_commit)
 raise SystemExit(subprocess.run([str(__import__('pathlib').Path(sys.executable).resolve()),str(s.ROOT/'benchmark/first_tuning_review_cohort_v2/gate.py'),'--out',str(s.ROOT/'output/producer_coverage_amendment_v2_post_label_cohort_gate')],cwd=s.ROOT).returncode)
