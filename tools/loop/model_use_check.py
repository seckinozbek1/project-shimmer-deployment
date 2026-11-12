"""Tokens by model from this laptop's Claude Code session logs since a moment, and any use of a removed model (D-539).

Usage: py -3.12 -X utf8 tools/loop/model_use_check.py [--since 2026-11-12T13:46+03:00] [--removed fable]
Reads ~/.claude/projects/**/*.jsonl only (assistant records with a model and a usage block, deduplicated
by message and request id). Prints one line per model and one line per transcript that used a removed
model after --since; exit 1 when any removed-model token is found, else 0. No model runs, no network.
Chats outside Claude Code (claude.ai, the desktop app, other machines) are not in these logs.
"""
import argparse
import collections
import datetime
import glob
import json
import os
import sys


def scan(root, since):
    by_model = collections.Counter()
    by_file = collections.defaultdict(collections.Counter)
    last = {}
    seen = set()
    for path in glob.glob(os.path.join(root, '**', '*.jsonl'), recursive=True):
        try:
            if os.path.getmtime(path) < since.timestamp():
                continue
            fh = open(path, encoding='utf-8', errors='ignore')
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"usage"' not in line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                message = record.get('message') or {}
                usage, model, stamp = message.get('usage'), message.get('model'), record.get('timestamp')
                if not usage or not model or not stamp:
                    continue
                key = (message.get('id'), record.get('requestId'))
                if key in seen:
                    continue
                seen.add(key)
                when = datetime.datetime.fromisoformat(stamp.replace('Z', '+00:00'))
                if when < since:
                    continue
                tokens = sum(usage.get(k) or 0 for k in
                             ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens'))
                by_model[model] += tokens
                name = os.path.basename(path)
                by_file[name][model] += tokens
                last[(name, model)] = max(last.get((name, model), when), when)
    return by_model, by_file, last


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--since', default='2026-11-12T13:46:00+03:00')
    parser.add_argument('--removed', default='fable')
    parser.add_argument('--root', default=os.path.join(os.path.expanduser('~'), '.claude', 'projects'))
    args = parser.parse_args(argv)
    since = datetime.datetime.fromisoformat(args.since)
    by_model, by_file, last = scan(args.root, since)
    for model, tokens in by_model.most_common():
        print(f'{model}: {tokens:,} tokens since {args.since}')
    found = False
    for name, models in by_file.items():
        for model, tokens in models.items():
            if args.removed in model:
                found = True
                print(f'REMOVED MODEL {model} in {name}: {tokens:,} tokens, last {last[(name, model)].isoformat()}')
    print('removed model use: FOUND' if found else 'removed model use: none')
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
