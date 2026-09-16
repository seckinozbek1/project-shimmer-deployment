"""Local mechanical rejection and isolation tests; no dataset label judgments."""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path=[p for p in sys.path if Path(p or '.').resolve()!=HERE]
import statistics
sys.path.insert(0,str(HERE))
import copy
import json
import unittest
from build import fixtures, guard, sha
from conversion import digest, quartet
from validators import candidates, validate
from rendering import PAIRS, render, reverse
from leakage import cluster, cross_split
from tokenizer_check import load, CEILING

class ReleaseTests(unittest.TestCase):
    def test_invalid_relations(self):
        self.assertEqual(len(fixtures()),12)

    def test_all_renderers_reversible(self):
        for pair in PAIRS:
            for style in pair:
                text='  Exact words.\nA second line!  '
                self.assertEqual(reverse(render(text,style),style),text)
        with self.assertRaises(ValueError):reverse('No bullet','bullet')

    def test_document_and_near_duplicate_grouping(self):
        a=' '.join('word'+str(i) for i in range(100))
        b=a+' altered'
        groups,audit=cluster({'a':a,'b':b,'c':'Completely separate content has different words.'},{},[])
        self.assertEqual(groups['a'],groups['b'])
        self.assertNotEqual(groups['a'],groups['c'])
        self.assertTrue(audit['near_duplicate_edges'])
        groups,_=cluster({'a':a,'b':a},{},[])
        self.assertEqual(groups['a'],groups['b'])

    def test_holdout_and_execution_denied(self):
        from access import load_split
        for split in ['train','dev','holdout']:
            with self.assertRaises(PermissionError):load_split(split,{'approved':True})
        receipt=json.loads((HERE/'holdout_receipt.json').read_text(encoding='utf8'))
        self.assertFalse(receipt['consumed'])

    def test_quartet_isolation_and_balance(self):
        rows=[json.loads(x) for x in (HERE/'examples.jsonl').read_text(encoding='utf8').splitlines()]
        groups={}
        for r in rows:groups.setdefault(r['lineage_id'],[]).append(r)
        self.assertTrue(groups)
        for rs in groups.values():
            self.assertEqual({r['relation'] for r in rs},{'MATCH','DIVERGENCE','OMISSION','ADDITION'})
            self.assertEqual(len({r['split'] for r in rs}),1)
            self.assertEqual(len({tuple(r['rendering_pair']) for r in rs}),1)
            self.assertEqual(len({r['input']['source_spans'][0]['text'] for r in rs}),1)
            self.assertTrue(all(not r['input']['required_refs'] and not r['input']['supplied_refs'] for r in rs))

    def test_metadata_exclusion_canonicalizer_and_no_truncation(self):
        lengths=load()
        row=json.loads((HERE/'examples.jsonl').read_text(encoding='utf8').splitlines()[0])
        before=lengths(row)
        changed=copy.deepcopy(row)
        for k in set(row)-{'input','role'}:changed[k]='arbitrary changed metadata'
        self.assertEqual(before,lengths(changed))
        changed['input']['extraction']='large text '*3000
        self.assertGreater(lengths(changed)['prompt_tokens'],CEILING)
        self.assertTrue(any(x>CEILING for x in [before['prompt_tokens']]*3+[lengths(changed)['prompt_tokens']]))
        from auditor_linear_core import normalized_input
        v=copy.deepcopy(row['input']);v['source_spans'][0]['text']='Text REF-9347';v['required_refs']=['REF-9347'];v['supplied_refs']=['REF-9347']
        w=copy.deepcopy(v);w['source_spans'][0]['text']='Text REF-111';w['required_refs']=['REF-111'];w['supplied_refs']=['REF-111']
        self.assertEqual(normalized_input(v)[0],normalized_input(w)[0])

    def test_runtime_denials_without_attempting_access(self):
        for event,args in [('socket.connect',(None,None)),('subprocess.Popen',('denied',)),
                           ('open',('fixture.safetensors','r',0)),('open',('x/benchmark/keys/fixture','r',0))]:
            with self.assertRaises(PermissionError):sys.audit(event,*args)
        self.assertNotIn('torch',sys.modules)

if __name__=='__main__':
    guard()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    (HERE/'test_evidence.json').write_bytes((json.dumps(dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful()),indent=2)+'\n').encode())
    sys.exit(0 if result.wasSuccessful() else 1)
