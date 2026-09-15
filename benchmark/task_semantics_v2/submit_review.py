"""Ingest a real independent reviewer response; no authored target rewriting."""
import argparse
from pathlib import Path
import json
import hardening as h


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('response',type=Path,nargs='?')
    parser.add_argument('--journal',type=Path,required=True);parser.add_argument('--resolution',type=Path)
    parser.add_argument('--resolve-packet')
    args=parser.parse_args()
    h.verify_baseline();h.verify_freeze()
    rows=h.read(h.V1/'seed.json')+h.read(h.HERE/'extension.json')
    resolution=h.read(args.resolution) if args.resolution else None
    if args.resolve_packet:
        if args.response or not resolution:parser.error('Resolution mode requires --resolution and no new response')
        result=h.resolve_review(args.resolve_packet,rows,args.journal,resolution)
    else:
        if not args.response:parser.error('A response file is required')
        response=h.baseline.strict_json(args.response.read_text(encoding='utf-8'))
        result=h.ingest_review(response,rows,args.journal,resolution)
    print(json.dumps(result))
