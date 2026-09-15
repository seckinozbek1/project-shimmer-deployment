import sys,tempfile,runpy,os
# Windows exposes O_RDONLY/O_WRONLY/O_RDWR but not the POSIX mask name.
if not hasattr(os,"O_ACCMODE"):os.O_ACCMODE=os.O_RDONLY|os.O_WRONLY|os.O_RDWR
from pathlib import Path
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'benchmark/producer_coverage_amendment_v3'))
# Pre-create the stdlib-only loopback wakeup pair. No source/target import here.
# The single deterministic asyncio test receives this loop; the installed guard
# continues to deny every subsequent socket creation and connection.
if sys.argv[1]=='production':
 import asyncio
 prepared_loop=asyncio.new_event_loop()
 asyncio.get_event_loop_policy()._loop_factory=lambda:prepared_loop
import access_guard
access_guard.install('POST_GOLD')
tempfile.tempdir=str(root/'output/producer_coverage_amendment_v3/test_fixtures')
task=sys.argv[1]
if task=='cohort':
 entry=root/'benchmark/first_tuning_review_cohort_v2/gate.py'
 sys.path.insert(0,str(entry.parent))
 sys.argv=[str(entry),'--out',str(root/'output/producer_coverage_amendment_v3/cohort_gate')]
 runpy.run_path(str(entry),run_name='__main__')
elif task=='production':
 sys.path.insert(0,str(root/'scripts'))
 import compact_contract_no_generation_gate as gate
 gate.OUT=root/'output/producer_coverage_amendment_v3/production_gate_retry'
 gate.OUT.mkdir(exist_ok=True)
 raise SystemExit(gate.main())
else:raise ValueError('Unregistered post task')
