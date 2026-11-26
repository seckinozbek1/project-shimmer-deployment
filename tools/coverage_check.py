"""Coverage check before any score is written (D-871, Seckin 21 November 2026 02:43, G-20261121-0243).

A score may be written only when the system itself answered the items it is scored on. This reads an adapter's
label output (the `label` command's JSON: primary.labels rows with `basis` and `class`) and counts, per basis,
how many items the system answered and how many carry a default, an abstention or nothing:

    py -3.12 -X utf8 tools/coverage_check.py LABELS.json [LABELS.json ...] [--runs RUNS] [--limit 0.05] [--out REPORT.json]

With --runs (a folder of <document id> run folders), a `silent` row counts as the system's own answer, basis
`judged_absence`, only when that run's audit/pairing_map.json shows the passage pair step was asked for the document
(pairs made above 0, none failed or unreadable, none refused or stopped) and kept no pair: the model judged every
pair and found no contradiction. A silent row whose step was not asked, failed, or whose table decisions are
unsettled stays not answered. Under the pair step's decision form (D-887) a judged absence also needs every pair read
both orders CLEAR; a document whose pairs hold a low-confidence leaning (D-907, tools/contradoc_leaning.py) and no
kept pair is `leaning_only`: not answered, counted apart, never the system's own answer.

Bases counted as the system's own answer: `ok` (the run's own verdict), `post_hoc_threshold` (the alpha's declared
post hoc threshold on saved decisions, D-870; reported apart), `judged_absence` (above, with --runs). Every other basis (`silent`, the scorer's default
for an item the system left without a verdict; `run_failure`, `setup_failure`, `over_context_excluded`, `argmax`,
an ABSTAIN class, or any basis not named here) counts as not answered. When the not-answered share of any file is
above the limit (5 percent), the check prints the reason and exits 3: the score is not written. It prints counts
and shares only, never an item id, a label or a key. Exit 0: every file is within the limit. Exit 2: a file is
unreadable or not a label output.

Empty answers (beta list item 17, Seckin 23 November 2026): every not-answered row is tagged `empty`
(tools/empty_answers.py) with its basis as the reason, and its count printed beside the coverage line. This changes
no count and no verdict. With --empty-list PATH the item ids of the empty rows and of every scored row are written
to PATH (the only place an id is written; default, D-950: <--out stem>_empty.json in the report's own folder); with --recheck PREVIOUS (a listing an earlier run wrote) the previously
empty items are read against this run, counts printed, each item's status written into the --empty-list file.
Seckin 18:10 (G-20261123-1812): the empty count is printed on two lines, withheld by the system as unsupported and
plain silence (tools/empty_answers.kind_of); with --correct N (the scorer's count of right answers among the
answered, an accuracy-type figure only) the main figure N/answered is printed beside the figure counting each
empty answer wrong, N/items. Nothing else in the counting changes.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import empty_answers  # noqa: E402

ANSWERED = ('ok', 'post_hoc_threshold', 'judged_absence')
LIMIT = 0.05
DECISION_FORM = 'decision'        # scripts/passage_pairs.DECISION_FORM, the row's `form`
LEANING_ONLY = 'leaning_only'     # D-907: never in ANSWERED


def _pair_entry(runs, document_id):
    path = Path(runs) / str(document_id) / 'audit' / 'pairing_map.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    entry = data.get(str(document_id)) if isinstance(data, dict) else None
    if not isinstance(entry, dict):
        entry = next(iter(data.values()), None) if isinstance(data, dict) and len(data) == 1 else data
    return entry if isinstance(entry, dict) else None


def pair_state(runs, document_id):
    """'judged_absence', LEANING_ONLY or None for a silent row's document. Judged absence: the run asked the passage
    pair step, nothing failed, and no pair was kept; under the decision form (D-887) also every pair read both orders
    CLEAR as the run settled them. A decision-form document with no pair kept and a pair that is a leaning (D-907:
    its two orders neither both FLAG nor both CLEAR, tools/contradoc_leaning.py) is LEANING_ONLY: counted apart,
    never the system's own answer. A reply-form row reads as before."""
    if not runs or not document_id:
        return None
    entry = _pair_entry(runs, document_id)
    pairs = entry.get('passage_pairs') if isinstance(entry, dict) else None
    if not isinstance(pairs, list) or not pairs:
        return None
    for row in pairs:
        if not isinstance(row, dict) or not (row.get('made') or 0) > 0:
            return None
        if (row.get('failed') or row.get('unreadable') or row.get('refused') or row.get('stopped')
                or row.get('raised') or row.get('not_asked') or row.get('kept')):
            return None
    if any(row.get('form') == DECISION_FORM for row in pairs):
        import contradoc_leaning
        if contradoc_leaning.read_entry(entry, contradoc_leaning.answer_classes())['document'] != 'all_clear':
            return LEANING_ONLY
    return 'judged_absence'


def judged_absence(runs, document_id):
    """True when pair_state reads the document as a judged absence."""
    return pair_state(runs, document_id) == 'judged_absence'


def counts(path, runs=None):
    """{'items', 'answered', 'post_hoc', 'not_answered', 'by_basis'} for one label output."""
    return read_rows(path, runs)[0]


def read_rows(path, runs=None):
    """(counts, empty entries, scored keys) of one label output; the empty entries are its not-answered rows, each
    tagged `empty` with its basis (beta item 17), the same rows counts() counts as not answered."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    rows = data['primary']['labels']
    if not isinstance(rows, list):
        raise ValueError('primary.labels is not a list')
    by_basis = {}
    answered = post_hoc = leaning_only = 0
    empty, scored = [], []
    for row in rows:
        basis = str(row.get('basis'))
        if basis == 'silent':
            basis = pair_state(runs, row.get('document_id')) or basis
            leaning_only += basis == LEANING_ONLY
        if row.get('class') == 'ABSTAIN':
            basis = basis + '/ABSTAIN'
        by_basis[basis] = by_basis.get(basis, 0) + 1
        scored.append(empty_answers.key_of(row.get('item_id')))
        if basis in ANSWERED:
            answered += 1
            post_hoc += basis == 'post_hoc_threshold'
        else:
            # Item 17: a not-answered row is an empty answer, tagged with its basis; no count changes.
            empty.append(empty_answers.entry(row.get('item_id'), basis))
    out = {'items': len(rows), 'answered': answered, 'post_hoc': post_hoc, 'not_answered': len(rows) - answered,
           'by_basis': dict(sorted(by_basis.items()))}
    if leaning_only:
        # D-907: a silent row whose document's pairs hold a leaning and no detection, not answered, counted apart
        out[LEANING_ONLY] = leaning_only
    return out, empty, scored


def default_listing(out):
    """D-950: the empty-answers listing's path beside the --out report, in the same folder."""
    return str(Path(out).parent / (Path(out).stem + '_empty.json'))


def main(argv):
    limit, out, runs, files, empty_list, previous, correct = LIMIT, None, None, [], None, None, None
    i = 0
    while i < len(argv):
        if argv[i] == '--limit':
            limit, i = float(argv[i + 1]), i + 2
        elif argv[i] == '--runs':
            runs, i = argv[i + 1], i + 2
        elif argv[i] == '--out':
            out, i = argv[i + 1], i + 2
        elif argv[i] == '--empty-list':
            empty_list, i = argv[i + 1], i + 2
        elif argv[i] == '--recheck':
            previous, i = argv[i + 1], i + 2
        elif argv[i] == '--correct':
            correct, i = int(argv[i + 1]), i + 2
        else:
            files.append(argv[i])
            i += 1
    if out and not empty_list:
        # D-950 (Seckin 18:10, item b): the listing sits in the score report's own folder unless named.
        empty_list = default_listing(out)
    if not files or (previous and not empty_list):
        print(__doc__)
        return 2
    if previous:
        try:
            previous = empty_answers.read_listing(previous)
        except (OSError, ValueError) as e:
            print('%s: not an empty-answers listing (%s): stop' % (Path(previous).name, type(e).__name__))
            return 2
    report, refused = {'limit': limit, 'files': {}}, []
    all_empty, all_scored = [], []
    for f in files:
        try:
            c, empty, scored = read_rows(f, runs)
        except (OSError, ValueError, KeyError, TypeError) as e:
            print('%s: not a label output (%s): stop' % (Path(f).name, type(e).__name__))
            return 2
        c[empty_answers.TAG] = empty_answers.summary(empty, c['items'])
        all_empty += empty
        all_scored += scored
        share = c['not_answered'] / c['items'] if c['items'] else 1.0
        c['not_answered_share'] = round(share, 4)
        c['verdict'] = 'within' if share <= limit else 'refused'
        report['files'][Path(f).name] = c
        print('%s: %d items, answered by the system %d (post hoc threshold %d), not answered %d (%.1f percent); %s'
              % (Path(f).name, c['items'], c['answered'], c['post_hoc'], c['not_answered'], 100 * share,
                 json.dumps(c['by_basis'])))
        if c.get(LEANING_ONLY):
            print('%s: of the not answered, %d rest on low-confidence leanings alone (D-907), never the system\'s own '
                  'answer' % (Path(f).name, c[LEANING_ONLY]))
        print('%s: tagged %s (%s): %d of %d, by reason %s'
              % (Path(f).name, empty_answers.TAG, empty_answers.LABEL_TR, c['empty']['count'], c['items'],
                 json.dumps(c['empty']['by_reason'])))
        for line in empty_answers.kind_lines(c['empty']):
            print('%s: %s' % (Path(f).name, line))
        if share > limit:
            refused.append('%s: %.1f percent not answered by the system, above %.0f percent'
                           % (Path(f).name, 100 * share, 100 * limit))
    report['verdict'] = 'refused' if refused else 'within'
    report['reasons'] = refused
    items = sum(c['items'] for c in report['files'].values())
    answered = sum(c['answered'] for c in report['files'].values())
    if correct is not None:
        # Seckin 18:10 (G-20261123-1812) item (a): both figures side by side, from the scorer's count of right answers.
        report['figures'] = empty_answers.both_figures(correct, answered, items)
        print(empty_answers.figures_line(report['figures']))
    else:
        print('both figures: pass --correct N (the count of right answers the scorer gives among the %d answered) to print '
              'the main figure beside the one counting blanks wrong' % answered)
    if empty_list:
        report['listing'] = str(Path(empty_list).resolve())
        print('%s (%s) ids are listed in %s, not here' % (empty_answers.TAG, empty_answers.LABEL_TR, report['listing']))
    if empty_list:
        listed = empty_answers.listing('coverage', all_empty, all_scored, run=[Path(f).name for f in files])
        if previous:
            listed['recheck'] = empty_answers.recheck(previous, listed)
            report['recheck'] = listed['recheck']['counts']
            rc = report['recheck']
            print('previously empty %d: now answered %d, still empty %d, not in this run %d'
                  % (sum(rc.values()), rc['now_answered'], rc['still_empty'], rc['not_in_this_run']))
        Path(empty_list).write_text(json.dumps(listed, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    if out:
        Path(out).write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')
    if refused:
        print('COVERAGE REFUSED: no score is written. ' + '; '.join(refused))
        return 3
    print('coverage within the limit: the score may be written')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
