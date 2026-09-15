"""Bounded AB admission and source-selection checks; no cloud or weights."""
import ast
import copy
import json
from pathlib import Path
import unittest
import remote_contract_ab_probe as probe
from contract_ab_prompts import OLD, EXPECTED_OLD_HASH, EXPECTED_NEW_HASH

ROOT=Path(__file__).resolve().parents[1]

class Checks(unittest.TestCase):
    def test_frozen_control_bytes(self):
        for role in ('producer','auditor'):
            self.assertEqual(OLD[role],(ROOT/f'docs/fix/compact_contract_ab/old_{role}_user.txt').read_bytes().decode())
        self.assertEqual(len(EXPECTED_OLD_HASH),2);self.assertEqual(len(EXPECTED_NEW_HASH),2)

    def test_strict_serial_admission(self):
        p=dict(accepted=True,raw_sha256='producer')
        a=dict(accepted=True,raw_sha256='auditor',usage=dict(finish_reason='eos',cap_hit=False))
        d=dict(producer_raw_sha256='producer',auditor_raw_sha256='auditor',producer_semantically_accepted=True,auditor_semantically_accepted=True)
        self.assertTrue(probe.serial_admitted(p,a,d))
        for key in d:
            bad=dict(d);bad[key]=False
            self.assertFalse(probe.serial_admitted(p,a,bad))
        self.assertFalse(probe.serial_admitted(dict(p,accepted=False),a,d))
        self.assertFalse(probe.serial_admitted(p,dict(a,accepted=False),d))
        for usage in [dict(finish_reason='length',cap_hit=True),dict(finish_reason='eos',cap_hit=True),dict(finish_reason='unknown',cap_hit=False)]:
            self.assertFalse(probe.serial_admitted(p,dict(a,usage=usage),d))

    def test_exact_four_arms_one_conditional_handoff(self):
        tree=ast.parse(Path(probe.__file__).read_text())
        labels=[n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='call_task']
        self.assertCountEqual(labels,['producer_old','producer_new','auditor_old','auditor_new','serial_auditor'])
        source=Path(probe.__file__).read_text()
        self.assertIn("call_task('serial_auditor','active_auditor',producer['parsed'])",source)
        self.assertNotIn('for capacity in',source)

    def test_budget_uses_manifest_hard_limit(self):
        source=(ROOT/'tools/run_remote_experiment.py').read_text()
        self.assertIn('soft_usd=0.5,hard_usd=1',source)
        self.assertNotIn('start+2/',source)
        self.assertIn("start+m['hard_usd']/rate*3600",source)
        self.assertIn('--contract-ab',source)
        self.assertIn('collected archive hash mismatch',source)

if __name__=='__main__':unittest.main()
