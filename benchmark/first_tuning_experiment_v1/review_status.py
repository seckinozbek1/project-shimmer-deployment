"""Rebuild cohort coverage from actual review journals, without submissions."""
import argparse
from pathlib import Path
import json
import registration as r


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--journal',type=Path,required=True)
    parser.add_argument('--reviewers',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();r.verify_frozen()
    rows=r.records();cohort=r.read(r.HERE/'cohort.json')['ids'];double=r.read(r.HERE/'double_review.json')['ids']
    coverage=r.review_coverage(rows,cohort,double,args.journal,r.read(args.reviewers))
    r.write(args.out/'coverage.json',{k:v for k,v in coverage.items() if k!='accepted_targets'})
    # This admin file must never be given to training; only the child selection
    # directory contains eligible TRAIN/DEV targets.
    r.write(args.out/'admin_review_targets.json',coverage['accepted_targets'])
    manifest=r.export_training_labels(rows,coverage,args.out/'training_access')
    print(json.dumps(dict(status=coverage['status'],reviewed=coverage['reviewed_accepted'],eligible_training=len(manifest['allowed_ids']),training_executed=False)))


if __name__=='__main__':main()
