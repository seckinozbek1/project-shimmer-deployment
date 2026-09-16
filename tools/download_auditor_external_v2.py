"""Public dataset/documentation downloads only; no credentials or model artifacts."""
import datetime
import hashlib
import json
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/external/auditor_relations_v2/raw'
OUT=ROOT/'tuning/auditor_external_relation_v2'
PAWS='161ece9501cf0a11f3e48bd356eaa82de46d6a09'
URLS={
 'paws-README.md':f'https://raw.githubusercontent.com/google-research-datasets/paws/02b29f3af1143620d1b7f352247e65c0bdd2ec18/README.md',
 'paws-LICENSE.txt':f'https://raw.githubusercontent.com/google-research-datasets/paws/02b29f3af1143620d1b7f352247e65c0bdd2ec18/LICENSE',
 'paws-hf-README.md':f'https://huggingface.co/datasets/google-research-datasets/paws/resolve/{PAWS}/README.md?download=true',
 'paws-train.parquet':f'https://huggingface.co/datasets/google-research-datasets/paws/resolve/{PAWS}/labeled_final/train-00000-of-00001.parquet?download=true',
 'paws-dev.parquet':f'https://huggingface.co/datasets/google-research-datasets/paws/resolve/{PAWS}/labeled_final/validation-00000-of-00001.parquet?download=true',
 'paws-test.parquet':f'https://huggingface.co/datasets/google-research-datasets/paws/resolve/{PAWS}/labeled_final/test-00000-of-00001.parquet?download=true',
 'wikiatomic-README.md':'https://raw.githubusercontent.com/google-research-datasets/wiki-atomic-edits/1f6769f2f9d93b6bf5acb091eb509b2be36e8e79/README.md',
 'peer-hf-README.md':'https://huggingface.co/datasets/jvamvas/peer_wiki-atomic-sample/resolve/d2c115d1bc5316dc3ebb0fdc2fe3965522a37fe6/README.md?download=true',
 'peer-zenodo.json':'https://zenodo.org/api/records/4478267',
 'PEER.zip':'https://zenodo.org/api/records/4478267/files/PEER.zip/content',
 'CC-BY-SA-4.0.txt':'https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt',
 'CC-BY-4.0.txt':'https://creativecommons.org/licenses/by/4.0/legalcode.txt',
}

def main():
    RAW.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'download_manifest.json'
    manifest=json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
    for name,url in URLS.items():
        dest=RAW/name
        if name in manifest and dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()==manifest[name]['sha256']:continue
        print('Downloading '+name,flush=True)
        with requests.get(url,timeout=(20,120),stream=True) as response:
            response.raise_for_status()
            with dest.open('wb') as stream:
                for chunk in response.iter_content(1024*1024):stream.write(chunk)
        data=dest.read_bytes()
        manifest[name]=dict(url=url,path=dest.relative_to(ROOT).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                           downloaded_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        path.write_bytes((json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode())
    print('Public downloads complete',flush=True)

if __name__=='__main__':main()
