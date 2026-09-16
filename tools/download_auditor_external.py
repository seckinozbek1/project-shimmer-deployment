"""Unauthenticated, pinned public dataset/documentation acquisition only."""
import datetime
import hashlib
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/external/auditor_relations/raw'
OUT = ROOT / 'tuning/auditor_external_relation_v1'
SOURCES = [
    ('summexecedit', 'd71ee27582afae29b1459b518229d9266ed4c8b2', 'defies_summedits_final_all_combined.json'),
    ('summedits', 'ce0c479aaf59259abb6b67e42248b2f49004b7d5', 'summedits.json'),
]

def main():
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for name, revision, filename in SOURCES:
        files = []
        for upstream in [filename, 'README.md']:
            url = f'https://huggingface.co/datasets/Salesforce/{name}/resolve/{revision}/{upstream}?download=true'
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            data = response.content
            path = RAW / (name + '-' + upstream)
            path.write_bytes(data)
            files.append(dict(url=url, path=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), downloaded_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
        records.append(dict(dataset='Salesforce/'+name, publisher='Salesforce', revision=revision, files=files))
    (OUT/'download_manifest.json').write_bytes((json.dumps(records, indent=2, sort_keys=True)+'\n').encode())
    print(json.dumps(records, indent=2))

if __name__ == '__main__':
    main()
