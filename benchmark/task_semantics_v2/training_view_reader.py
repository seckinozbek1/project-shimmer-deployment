"""Read only a frozen train/dev selection, with no sealed-store API exposed."""
import argparse
import json
import hardening as h


def load(split):
    if split not in ('train','dev'):raise PermissionError('Only train/dev selection is available')
    h.verify_baseline();h.verify_freeze()
    root=h.HERE/'training_view'
    return h.load_training_file(root,split+'.json',h.read(root/'manifest.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--split',required=True,choices=('train','dev'))
    args=parser.parse_args()
    rows=load(args.split)
    # Inspect selection without automatically dumping labels or launching jobs.
    print(json.dumps(dict(split=args.split,examples=len(rows),training_executed=False)))
