"""Only maintained V3 command gateway. Install access boundary before imports."""
import sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import access_guard as ag

def main():
 task=sys.argv[1]
 if task=='guard_checks':
  # This module installs a synthetic isolated guard itself before planted reads.
  from phase_guard_checks import run_checks
  print(run_checks());return
 guard=ag.install('PRE_GOLD' if task in ('checks','population','collect','freeze','method_freeze','workspaces','enable_post') else 'auto')
 if task=='checks':
  import unittest,checks,heading_checks,json
  suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (checks,heading_checks))
  result=unittest.TextTestRunner(verbosity=2).run(suite)
  out=dict(phase='PRE_GOLD_SAFE',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors))
  (HERE.parents[1]/'output/producer_coverage_amendment_v3/pre_checks.json').write_text(json.dumps(out,indent=2))
  if not result.wasSuccessful():raise SystemExit(1)
 elif task=='method_freeze':
  import method_freeze;method_freeze.main()
 elif task=='workspaces':
  import population;population.create_workspaces()
 elif task=='population':
  import population;population.main()
 elif task in ('collect','freeze'):
  import review_flow;getattr(review_flow,task)()
 elif task=='enable_post':
  print(guard.enable_post_phase(sys.argv[2]))
 elif task=='compare':
  import compare_legacy;print(compare_legacy.run())
 elif task=='post_checks':
  import post_checks;print(post_checks.run())
 else:raise ValueError('Unregistered task')
if __name__=='__main__':main()
