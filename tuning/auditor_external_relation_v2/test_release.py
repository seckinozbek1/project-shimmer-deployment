"""Mechanical, leakage and authorization tests; no label judgments or training."""
import copy,json,random,sys,unittest
from collections import Counter
from local_utils import *
import filters,leakage
from build import guard,preserve

class Tests(unittest.TestCase):
    def test_paws_orientation_and_invalids(self):
        raw=dict(id=1,sentence1='The large vessel arrived at the northern port yesterday.',sentence2='Yesterday the vessel arrived at the large port in the north.',label=1)
        a,reason=filters.paws(raw);self.assertIsNone(reason);self.assertEqual(a['relation'],'MATCH')
        raw['label']=0;b,reason=filters.paws(raw);self.assertIsNone(reason);self.assertEqual(b['relation'],'DIVERGENCE')
        self.assertEqual(a['pair_id'],b['pair_id'])
        self.assertIsNotNone(filters.paws(dict(raw,sentence2=raw['sentence1']))[1])
        self.assertIsNotNone(filters.paws(dict(raw,sentence2='Invalid <NUM> placeholder.'))[1])

    def test_atomic_exact_reconstruction(self):
        src='The vessel arrived at the northern port before sunset .'.split()
        pos=2;tgt=src[:pos]+['safely']+src[pos:]
        r=dict(id=1,src=src,tgt=tgt,changed=['safely'],src_tag=['equal']*pos+['insert']+['equal']*(len(src)-pos),
               yin_before=src[:pos]+['__EMPTY__']+src[pos:],yin_after=tgt)
        converted,reason=filters.atomic(r);self.assertIsNone(reason);self.assertEqual(converted['relation'],'ADDITION')
        d=dict(r,src=tgt,tgt=src,src_tag=['delete' if x=='insert' else x for x in r['src_tag']],yin_before=tgt,yin_after=r['yin_before'])
        converted,reason=filters.atomic(d);self.assertIsNone(reason);self.assertEqual(converted['relation'],'OMISSION')
        for bad in [dict(r,changed=['different']),dict(r,tgt=tgt+['extra']),dict(r,yin_before=src)]:self.assertIsNotNone(filters.atomic(bad)[1])
        bad=copy.deepcopy(r);bad['yin_after'][0]='Changed';self.assertIsNotNone(filters.atomic(bad)[1])

    def test_prefix_index_against_exhaustive(self):
        rng=random.Random(13);texts=[]
        for i in range(25):
            base=['w'+str(rng.randrange(100)) for _ in range(40)]
            texts += [' '.join(base),' '.join(base+['extra']),' '.join(base[:19]+['changed']+base[20:])]
        rows=[dict(source=t,candidate=t,pair_id=str(i)) for i,t in enumerate(texts)]
        grouped,_=leakage.group(rows,[]);by={r['pair_id']:r['group_id'] for r in grouped}
        for i,a in enumerate(texts):
            for j,b in enumerate(texts):
                if leakage.similarity(leakage.shingles(a),leakage.shingles(b))>=leakage.THRESHOLD:self.assertEqual(by[str(i)],by[str(j)])

    def test_balance_challenges_and_no_refusals(self):
        rows=[json.loads(x) for x in (HERE/'external_four_way_view.jsonl').read_text(encoding='utf8').splitlines()]
        self.assertGreaterEqual(len(rows),1200);self.assertLessEqual(len(rows),3000)
        self.assertEqual(len(set(Counter(r['relation'] for r in rows).values())),1)
        self.assertEqual(len({r['lineage_id'] for r in rows}),len(rows))
        by={r['example_id']:r for r in rows}
        for sign,c in read(HERE/'dev_challenges.json').items():
            selected=[by[i] for i in c['example_ids']]
            self.assertEqual({r['features']['sign'] for r in selected},{sign})
            self.assertEqual({r['split'] for r in selected},{'dev'})
            self.assertEqual(len(set(Counter(r['relation'] for r in selected).values())),1)
        self.assertTrue(all(not r['input']['required_refs'] and not r['input']['supplied_refs'] for r in rows))

    def test_exact_prompt_metadata_exclusion(self):
        from tokenizer_check import load,CEILING
        lengths=load();r=json.loads((HERE/'external_four_way_view.jsonl').read_text(encoding='utf8').splitlines()[0]);v=lengths(r)
        changed={k:('arbitrary' if k not in {'role','input'} else val) for k,val in r.items()}
        self.assertEqual(v,lengths(changed));changed=copy.deepcopy(r);changed['input']['extraction']='larger words '*3000
        self.assertGreater(lengths(changed)['prompt_tokens'],CEILING)

    def test_denials_and_v1_preservation(self):
        from access import load_split
        for s in ['train','dev','holdout']:
            with self.assertRaises(PermissionError):load_split(s,{'approved':True})
        self.assertFalse(read(HERE/'holdout_receipt.json')['consumed'])
        self.assertEqual(preserve(),read(HERE/'dry_run_evidence.json')['preservation'])
        for event,args in [('socket.connect',(None,None)),('subprocess.Popen',('denied',)),('open',('fake.safetensors','r',0)),('open',('x/auditor_external_relation_v1/fake','w',0))]:
            with self.assertRaises(PermissionError):sys.audit(event,*args)
        self.assertNotIn('torch',sys.modules)

if __name__=='__main__':
    guard();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    write('test_evidence.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors)))
    sys.exit(0 if result.wasSuccessful() else 1)
