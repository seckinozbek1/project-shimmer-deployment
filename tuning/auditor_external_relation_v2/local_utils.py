"""Stable local serialization and text statistics; no model or network imports."""
import hashlib,json,math,re,unicodedata
from pathlib import Path
from statistics import mean,median
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RAW=ROOT/'data/external/auditor_relations_v2/raw'
CLASSES=('MATCH','DIVERGENCE','OMISSION','ADDITION')
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def write(name,x):(HERE/name).write_bytes((json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode())
def jsonl(name,rows):(HERE/name).write_bytes((''.join(canonical(r)+'\n' for r in rows)).encode())
def norm(x):return ' '.join(unicodedata.normalize('NFKC',x).casefold().split())
def words(x):return re.findall(r"\w+(?:['’-]\w+)*",norm(x))
def pair_key(a,b):return digest(sorted([norm(a),norm(b)]))
def describe(x):
    x=sorted(x)
    return dict(count=len(x),min=x[0],median=median(x),mean=mean(x),p95=x[math.ceil(.95*len(x))-1],p99=x[math.ceil(.99*len(x))-1],max=x[-1]) if x else dict(count=0)
def features(a,b):
    m,n=len(words(a)),len(words(b))
    return dict(source_words=m,candidate_words=n,sign='shorter' if n<m else 'longer' if n>m else 'equal',
                word_ratio=n/m,character_ratio=len(b)/len(a),source_characters=len(a),candidate_characters=len(b),
                source_punctuation=len(re.findall(r'[^\w\s]',a)),candidate_punctuation=len(re.findall(r'[^\w\s]',b)))
def stratum(r):
    f=r['features']
    return (int(abs(math.log(f['word_ratio']))/.025),min(f['source_words'],f['candidate_words'])//10)
def model_input(a,b):
    return dict(role='auditor',production_contract='semantic-task-v1',delivery_complete=True,
        source_spans=[dict(alias='s0',text=a)],extraction=b,context_only_spans=[],required_refs=[],supplied_refs=[],routed_rules=[])
