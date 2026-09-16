"""Auditor metadata and prospective duplicate controls; no generation implementation."""
import hashlib,math

class RawSink:
    def __init__(self,sink,step,adapter,records):
        assert step in (60,120) and adapter['step']==step and adapter['experiment']=='auditor-canonical-v2'
        self.sink,self.step,self.adapter,self.records=sink,step,adapter,{x['example_id']:x for x in records}
        self.written=set()
    def append(self,evidence):
        assert 'metrics' not in evidence and evidence['example_id'] not in self.written
        row=self.records[evidence['example_id']]
        assert evidence['role']=='auditor' and evidence['adapter']==self.adapter and evidence['checkpoint']==self.step
        assert evidence['runtime']=='auditor-canonical-scoped-v1'
        assert evidence['prompt_sha256']==hashlib.sha256(row['prompt'].encode()).hexdigest()
        evidence.update(experiment='auditor-canonical-v2',prompt=row['prompt'],input_ids=row['input_ids'],attention_mask=row['attention_mask'])
        self.sink.append(evidence);self.written.add(evidence['example_id'])

def control_gate(first,second,protocol,adapter,step):
    assert [x['example_id'] for x in first]==[x['example_id'] for x in second]==protocol['control_ids']
    for a,b in zip(first,second):
        for row in (a,b):
            assert row['adapter']==adapter and row['checkpoint']==step and row['role']=='auditor'
            assert math.isfinite(row['generation_seconds']) and row['generation_seconds']>0
        for k in ('prompt','input_ids','attention_mask','output_token_ids','raw_output','raw_output_with_special_tokens','metrics','stop_reason'):
            assert a[k]==b[k],k
    return dict(passed=True,identical_pairs=5,optimized_only=True)
