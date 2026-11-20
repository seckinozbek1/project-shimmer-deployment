"""Panel freshness: every section of the panel document (panel/durum) against the records (PANEL-FRESH-A).

    py -3.12 -X utf8 tools/loop/panel_freshness.py check DURUM_JSON [--status PANEL_STATUS_JSON] [--now ISO]
    py -3.12 -X utf8 tools/loop/panel_freshness.py mark DURUM_JSON      # record rows newly seen done (done_since.json)
    py -3.12 -X utf8 tools/loop/panel_freshness.py move DURUM_JSON OUT_JSON   # new OPEN, ISTEK and CHG for the builder
    py -3.12 -X utf8 tools/loop/panel_freshness.py alert                # the hourly task: newest saved copy, ALERT.md

Seckin 20 November 2026 (G-20261120-1220, G-20261120-1227). Rules in config/panel_freshness.json, read at call time.
One line per finding, readable by a person (the supervisor compares the panel with the records every hour):

  STALE      a row that is not finished (state not done, moved or off; KPIS and BARS cards always) whose time is over
             24 hours old. A row's time is the first saved copy holding it word for word (STAMP_ISO), and when the row
             is already in the oldest copy, the earliest of that and the newest date it names ("19 Kasım 18:41");
             with no copy, the date it names, else a bare HH:MM taken nearest the panel's own stamp.
  PAST       a time promised in a note ("tahmini başlangıç HH:MM", "tahmini bitiş HH:MM", "HH:MM civarı") that is
             more than 2 hours past; the clock is taken nearest the time the row was first seen.
  WORD       "yarın" in any row, "sürüyor" or "tahmini" in a finished row.
  NO-CHG     a decision of docs/loop/DECISIONS.md from decisions_from on with no CHG line: chg_decisions.json names,
             for each decision id, the CHG line(s) ("what" text, or "20 Kas|what") it entered as; the line must exist.
  BARS       a BARS number (plan and v1.05 counts, money spent and its cap, weekly usage) that differs from
             tools/loop/panel_status.py --print (money within spend_tolerance_usd).
  MOVE       an OPEN or ISTEK row done (or moved or off) for over 24 hours by done_since.json: it leaves the list
             and becomes one CHG line (`move` writes the new OPEN, ISTEK and CHG).
  UNRECORDED a finished OPEN or ISTEK row with no done_since.json entry (`mark` records it with the time now).

check exits 1 on any finding, 0 when every section is fresh; it writes nothing. mark writes only done_since.json,
move only its OUT_JSON. alert reads the newest saved copy (saved_copies globs under the main checkout, and the globs
in SHIMMER_PANEL_COPIES), writes one trace line (mechanism panel_freshness) and, when a section is stale or
contradicts a record, one ALERT.md line through mechanism_common.alert, at most once an hour per set of findings.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

NAME = 'panel_freshness'
CONFIG = HERE.parents[1] / 'config' / 'panel_freshness.json'
MONTHS = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım',
          'Aralık']
SHORT = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']
_MONTH_NO = {m: i + 1 for i, m in enumerate(MONTHS)}
_MONTH_NO.update({m: i + 1 for i, m in enumerate(SHORT)})
DATE = re.compile(r'\b(\d{1,2}) (%s)\b(?:\s+\d{4})?,?(?:\s+(?:saat\s+)?(\d{1,2}):(\d\d))?'
                  % '|'.join(MONTHS + SHORT))
CLOCK = re.compile(r'(?<![\d:,])(\d{1,2}):(\d\d)(?![\d:])')
DECISION = re.compile(r'^## (D-\d+)[:.]')
WRITTEN = re.compile(r'^Written (\d{4}-\d\d-\d\d \d\d:\d\d [+-]\d{4})')
COUNT = re.compile(r'(\d+)\D+?(\d+)')
H = 3600.0


def load_config(path=None):
    return json.loads(Path(path or CONFIG).read_text(encoding='utf-8'))


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def parse_iso(text):
    try:
        t = dt.datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.astimezone()


def stamp_of(panel, path=None):
    t = parse_iso((panel or {}).get('STAMP_ISO'))
    if t is None and path is not None:
        try:
            t = dt.datetime.fromtimestamp(Path(path).stat().st_mtime).astimezone()
        except OSError:
            t = None
    return t


# ------------------------------------------------------------------ rows

def rows(panel, section):
    value = (panel or {}).get(section)
    return value if isinstance(value, list) else []


def row_name(row, section, cfg):
    key = cfg['row_name'].get(section, 0)
    if isinstance(row, dict):
        return str(row.get(key, ''))
    if isinstance(row, list) and isinstance(key, int) and len(row) > key:
        return str(row[key])
    return ''


def row_state(row, section, cfg):
    key = cfg['row_state'].get(section)
    if isinstance(row, list) and isinstance(key, int) and len(row) > key:
        return str(row[key])
    return None


def row_text(row):
    if isinstance(row, dict):
        return ' '.join(str(row[k]) for k in sorted(row) if isinstance(row[k], (str, int, float)))
    if isinstance(row, list):
        return ' '.join(str(x) for x in row)
    return str(row)


def row_key(row):
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def nearest(hour, minute, anchor):
    """The datetime at HH:MM nearest the anchor (the day before, the day itself or the day after)."""
    if not (0 <= hour < 24 and 0 <= minute < 60):
        return None
    base = anchor.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return min((base + dt.timedelta(days=d) for d in (-1, 0, 1)), key=lambda c: abs((c - anchor).total_seconds()))


def named_dates(text, year, tz):
    """Every explicit date the text names ("19 Kasım 18:41", "20 Kas"); a date with no time counts to its end."""
    out = []
    for m in DATE.finditer(text):
        try:
            day = dt.datetime(year, _MONTH_NO[m.group(2)], int(m.group(1)), tzinfo=tz)
        except ValueError:
            continue
        if m.group(3):
            out.append(day.replace(hour=int(m.group(3)), minute=int(m.group(4))))
        else:
            out.append(day + dt.timedelta(hours=23, minutes=59))
    return out


def bare_clocks(text):
    clean = DATE.sub(' ', text)
    return [(int(h), int(m)) for h, m in CLOCK.findall(clean)]


# ------------------------------------------------------------------ saved copies

def copy_paths(cfg, main, extra=None):
    pats = [str(Path(main) / p) for p in cfg.get('saved_copies', [])]
    env = os.environ.get(cfg.get('copies_env') or '', '')
    pats += [p for p in env.split(os.pathsep) if p]
    pats += list(extra or [])
    found = set()
    for p in pats:
        found.update(glob.glob(p))
    return sorted(found)


def load_copies(paths):
    out = []
    for p in paths:
        data = read_json(p)
        if isinstance(data, dict):
            t = stamp_of(data, p)
            if t is not None:
                out.append((t, data, p))
    return sorted(out, key=lambda x: x[0])


def first_seen(copies, cfg):
    """{(section, row key): first stamp holding it}, and the oldest stamp of all."""
    seen = {}
    for t, data, _ in copies:
        for s in cfg['sections']:
            for r in rows(data, s):
                seen.setdefault((s, row_key(r)), t)
    return seen, (copies[0][0] if copies else None)


def newest_copy(cfg, main, extra=None):
    copies = load_copies(copy_paths(cfg, main, extra))
    return copies[-1] if copies else None


# ------------------------------------------------------------------ records

def read_decisions(path):
    """[(id, written time)] of DECISIONS.md headings that carry a Written line."""
    out, cur = [], None
    try:
        lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return out
    for raw in lines:
        m = DECISION.match(raw)
        if m:
            cur = m.group(1)
            continue
        w = WRITTEN.match(raw)
        if w and cur:
            out.append((cur, dt.datetime.strptime(w.group(1), '%Y-%m-%d %H:%M %z')))
            cur = None
    return out


def dnum(did):
    m = re.match(r'D-(\d+)$', str(did))
    return int(m.group(1)) if m else -1


def load_status(path=None, main=None):
    if path:
        return read_json(path)
    import panel_status
    return panel_status.build(main=main)


# ------------------------------------------------------------------ the check

def finding(kind, section, name, detail):
    return {'kind': kind, 'section': section, 'row': name, 'detail': detail}


def fmt_time(t):
    return '%d %s %02d:%02d' % (t.day, SHORT[t.month - 1], t.hour, t.minute)


def bar_findings(panel, status, cfg):
    out = []
    if not isinstance(status, dict):
        return [finding('BARS', 'BARS', '-', 'panel_status reading not available')]
    bars = {b.get('ad'): b for b in status.get('cubuklar') or [] if isinstance(b, dict)}
    for card in rows(panel, 'BARS'):
        if not isinstance(card, dict):
            continue
        title = str(card.get('t', ''))
        rule = next((v for k, v in cfg['bars'].items() if title.startswith(k)), None)
        if not rule:
            continue
        note = str(card.get('n', ''))
        if rule['kind'] == 'count':
            ref = bars.get(rule['status']) or {}
            m = COUNT.search(note)
            want = (ref.get('deger'), ref.get('hedef'))
            got = (int(m.group(1)), int(m.group(2))) if m else None
            if got != want:
                out.append(finding('BARS', 'BARS', title, 'panel says %s, panel_status says %s of %s'
                                   % ('%d of %d' % got if got else repr(note), want[0], want[1])))
            elif want[1] and abs(float(card.get('v') or 0) - float(want[0]) / float(want[1])) > 0.005:
                out.append(finding('BARS', 'BARS', title, 'bar length %s does not match %s of %s'
                                   % (card.get('v'), want[0], want[1])))
        elif rule['kind'] == 'spend':
            ref = bars.get(rule['status']) or {}
            m = re.search(r'(\d+) doların ([\d.]+,\d+|\d+)', note)
            if not m or ref.get('deger') is None:
                out.append(finding('BARS', 'BARS', title, 'money not readable: %r' % note))
                continue
            cap, spent = float(m.group(1)), float(m.group(2).replace('.', '').replace(',', '.'))
            if cap != float(ref['hedef']) or abs(spent - float(ref['deger'])) > cfg['spend_tolerance_usd']:
                out.append(finding('BARS', 'BARS', title, 'panel says %.2f of %.0f dolar, panel_status says %.2f of %.0f'
                                   % (spent, cap, ref['deger'], ref['hedef'])))
        elif rule['kind'] == 'usage':
            m = re.search(r'yüzde (\d+)', str(status.get('kullanim') or ''))
            p = re.search(r'%(\d+)', note)
            if m and (not p or int(p.group(1)) != int(m.group(1))):
                out.append(finding('BARS', 'BARS', title, 'panel says %s, the usage reading says %%%s'
                                   % (p.group(0) if p else repr(note), m.group(1))))
    return out


def chg_findings(panel, decisions, chg_map, cfg):
    out = []
    lines = [(str(r[0]), str(r[1])) for r in rows(panel, 'CHG') if isinstance(r, list) and len(r) >= 2]
    newest = max((x for x in lines), default=None)
    floor = dnum(cfg['decisions_from'])
    for did, written in decisions:
        if dnum(did) < floor:
            continue
        named = (chg_map or {}).get(did)
        if not named:
            out.append(finding('NO-CHG', 'CHG', did, 'decision written %s has no CHG line (newest CHG line %s); add '
                               'one and name it for %s in chg_decisions.json' % (fmt_time(written),
                                                                                  newest[0] if newest else 'none', did)))
            continue
        for want in ([named] if isinstance(named, str) else named):
            day, _, what = want.rpartition('|')
            if not any(w == what and (not day or d == day) for d, w in lines):
                out.append(finding('NO-CHG', 'CHG', did, 'chg_decisions.json names the CHG line %r, which the panel '
                                   'does not hold' % want))
    return out


def check(panel, cfg, now, status=None, copies=(), decisions=(), chg_map=None, done_since=None):
    """{'findings': [...], 'sections': {section: (oldest row, time, age hours)}}."""
    stamp = stamp_of(panel) or now
    tz, year = stamp.tzinfo, stamp.year
    seen, oldest_copy = first_seen(list(copies), cfg)
    terminal = set(cfg['terminal_states'])
    pats = [re.compile(p, re.I) for p in cfg['future_time_patterns']]
    any_words = re.compile(r'\b(%s)\b' % '|'.join(map(re.escape, cfg['stale_words_any'])), re.I) \
        if cfg['stale_words_any'] else None
    term_words = re.compile(r'\b(%s)\b' % '|'.join(map(re.escape, cfg['stale_words_terminal'])), re.I) \
        if cfg['stale_words_terminal'] else None
    max_age, slack = cfg['max_age_hours'] * H, cfg['past_slack_hours'] * H
    found, sections = [], {}
    for s in cfg['sections']:
        oldest = None
        for r in rows(panel, s):
            name, state, text = row_name(r, s, cfg), row_state(r, s, cfg), row_text(r)
            fs = seen.get((s, row_key(r)))
            dates = named_dates(text, year, tz)
            if fs is not None and fs != oldest_copy:
                t = fs
            elif fs is not None:
                t = min([fs] + [d for d in dates if d <= fs])
            elif dates:
                t = max(d for d in dates if d <= stamp) if any(d <= stamp for d in dates) else None
            else:
                clocks = [nearest(h, m, stamp) for h, m in bare_clocks(text)]
                clocks = [c for c in clocks if c is not None and c <= stamp]
                t = max(clocks) if clocks else None
            if s == 'CHG' and dates:
                t = max(dates)
            if t is not None and (oldest is None or t < oldest[1]):
                oldest = (name, t)
            if s in cfg['log_sections']:
                continue
            finished = state in terminal
            if t is not None and not finished and (now - t).total_seconds() > max_age:
                found.append(finding('STALE', s, name, 'unchanged since %s (%.0f h); rewrite it from the records'
                                     % (fmt_time(t), (now - t).total_seconds() / H)))
            anchor = fs or stamp
            for p in pats:
                for m in p.finditer(text):
                    when = nearest(int(m.group(1)), int(m.group(2)), anchor)
                    if when is not None and (now - when).total_seconds() > slack:
                        found.append(finding('PAST', s, name, '"%s" is %.0f h past (taken as %s)'
                                             % (m.group(0), (now - when).total_seconds() / H, fmt_time(when))))
            if any_words and any_words.search(text):
                found.append(finding('WORD', s, name, '"%s" in the row; write the date' % any_words.search(text).group(0)))
            if finished and term_words and term_words.search(text):
                found.append(finding('WORD', s, name, '"%s" in a %s row; give the result: figure, cost, date'
                                     % (term_words.search(text).group(0), state)))
            if s in cfg['move_sections'] and state in cfg['move_states']:
                rec = (done_since or {}).get('%s|%s' % (s, name))
                since = parse_iso(rec.get('since')) if isinstance(rec, dict) else None
                if since is None:
                    found.append(finding('UNRECORDED', s, name, '%s row with no done_since entry; run mark' % state))
                elif (now - since).total_seconds() > cfg['done_max_hours'] * H:
                    found.append(finding('MOVE', s, name, '%s since %s (%.0f h); move it to one CHG line'
                                         % (state, fmt_time(since), (now - since).total_seconds() / H)))
        sections[s] = (oldest[0], oldest[1].isoformat(timespec='minutes'),
                       round((now - oldest[1]).total_seconds() / H, 1)) if oldest else None
    found += bar_findings(panel, status, cfg)
    found += chg_findings(panel, decisions, chg_map, cfg)
    return {'findings': found, 'sections': sections}


def report(result):
    lines = []
    for s, v in result['sections'].items():
        lines.append('SECTION %-5s oldest line: %s' % (s, 'no dated line' if v is None else
                                                      '%s, %s (%.1f h)' % (v[0][:60], v[1].replace('T', ' '), v[2])))
    for f in result['findings']:
        lines.append('%-10s %-5s | %s | %s' % (f['kind'], f['section'], f['row'][:60], f['detail']))
    bad = sorted({f['section'] for f in result['findings']})
    lines.append('RESULT %s' % ('FRESH: every section agrees with the records' if not bad else
                                '%d finding(s) in %s: rewrite before posting' % (len(result['findings']), ', '.join(bad))))
    return '\n'.join(lines)


# ------------------------------------------------------------------ mark and move

def mark(panel, cfg, now, done_since):
    """done_since with every finished OPEN or ISTEK row recorded (first sighting kept); a row back to open is dropped."""
    out = dict(done_since or {})
    for s in cfg['move_sections']:
        for r in rows(panel, s):
            key, state = '%s|%s' % (s, row_name(r, s, cfg)), row_state(r, s, cfg)
            if state in cfg['move_states']:
                if not isinstance(out.get(key), dict) or out[key].get('state') != state:
                    out[key] = {'since': now.isoformat(timespec='seconds'), 'state': state, 'source': 'mark'}
            else:
                out.pop(key, None)
    return out


def move(panel, cfg, now, done_since):
    """{OPEN, ISTEK, CHG}: rows finished over done_max_hours leave their list and become one CHG line each."""
    out, new_chg = {}, []
    for s in cfg['move_sections']:
        keep = []
        for r in rows(panel, s):
            name, state = row_name(r, s, cfg), row_state(r, s, cfg)
            rec = (done_since or {}).get('%s|%s' % (s, name))
            since = parse_iso(rec.get('since')) if isinstance(rec, dict) else None
            if state in cfg['move_states'] and since and (now - since).total_seconds() > cfg['done_max_hours'] * H:
                note = str(r[2]) if isinstance(r, list) and len(r) > 2 else ''
                new_chg.append(['%d %s' % (since.day, SHORT[since.month - 1]), name,
                                'Açık iş' if s == 'OPEN' else 'İstek', note or state])
            else:
                keep.append(r)
        out[s] = keep
    def day(line):
        m = re.match(r'(\d{1,2}) (\w+)', str(line[0])) if isinstance(line, list) and line else None
        return (_MONTH_NO.get(m.group(2), 0), int(m.group(1))) if m else (0, 0)
    out['CHG'] = sorted(rows(panel, 'CHG') + new_chg, key=day)   # stable: same-day lines keep their order
    return out, new_chg


# ------------------------------------------------------------------ alert (the hourly task)

def run_alert(cfg, main, now, status=None, alert=None, trace=None, extra_copies=None):
    copies = load_copies(copy_paths(cfg, main, extra_copies))
    if not copies:
        text = ('Panel freshness: no saved copy of the panel found (%s); save one at every write.'
                % ', '.join(cfg.get('saved_copies', [])))
        written = alert('panel_fresh:no_copy', text, every=cfg['alert_every_s']) if alert else False
        if trace:
            trace(NAME, 'no_copy', alert_written=written)
        return {'result': 'no_copy', 'findings': [], 'alert_written': written}
    t, panel, path = copies[-1]
    status = status if status is not None else load_status(main=main)
    decisions = read_decisions(Path(main) / cfg['decisions_file'])
    res = check(panel, cfg, now, status=status, copies=copies, decisions=decisions,
                chg_map=read_json(Path(main) / cfg['chg_map']) or {},
                done_since=read_json(Path(main) / cfg['done_since']) or {})
    bad = sorted({f['section'] for f in res['findings']})
    written = False
    if bad and alert:
        kinds = sorted({f['kind'] for f in res['findings']})
        written = alert('panel_fresh:%s:%s' % (','.join(bad), ','.join(kinds)),
                        'Panel freshness (copy of %s): %d finding(s) in %s (%s); rewrite them from the records at the next '
                        'panel write: py -3.12 -X utf8 tools/loop/panel_freshness.py check %s'
                        % (fmt_time(t), len(res['findings']), ', '.join(bad), ', '.join(kinds), path),
                        every=cfg['alert_every_s'])
    if trace:
        trace(NAME, 'alert' if bad else 'ok', copy=str(path), stamp=t.isoformat(), sections=bad,
              findings=[(f['kind'], f['section'], f['row'][:60]) for f in res['findings']], alert_written=written)
    return {'result': 'alert' if bad else 'ok', 'findings': res['findings'], 'alert_written': written}


# ------------------------------------------------------------------ command line

def main_root(arg=None):
    if arg:
        return Path(arg)
    import shared_paths
    return shared_paths.main_checkout(start=HERE, fallback=HERE.parents[1])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('check', 'mark', 'move', 'alert'):
        p = sub.add_parser(name)
        if name != 'alert':
            p.add_argument('durum')
        if name == 'move':
            p.add_argument('out')
        p.add_argument('--main')
        p.add_argument('--now')
        p.add_argument('--status', help='a saved panel_status --print JSON instead of a live reading')
        p.add_argument('--copies', action='append', help='more saved copy globs')
        p.add_argument('--done-since')
        p.add_argument('--config')
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    root = main_root(args.main)
    now = parse_iso(args.now) if args.now else dt.datetime.now().astimezone()
    ds_path = Path(args.done_since) if args.done_since else root / cfg['done_since']
    if args.cmd == 'alert':
        import mechanism_common as mc
        status = read_json(args.status) if args.status else None
        res = run_alert(cfg, root, now, status=status, alert=mc.alert, trace=mc.trace, extra_copies=args.copies)
        print('%s: %d finding(s), alert written %s' % (res['result'], len(res['findings']), res['alert_written']))
        return 0
    panel = read_json(args.durum)
    if not isinstance(panel, dict):
        print('REFUSED %s is not a panel JSON object' % args.durum)
        return 2
    done_since = read_json(ds_path) or {}
    if args.cmd == 'mark':
        new = mark(panel, cfg, now, done_since)
        ds_path.parent.mkdir(parents=True, exist_ok=True)
        ds_path.write_text(json.dumps(new, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8',
                           newline='\n')
        print('MARKED %d finished row(s) in %s' % (len(new), ds_path))
        return 0
    if args.cmd == 'move':
        out, new = move(panel, cfg, now, done_since)
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
        for line in new:
            print('MOVED %s | %s -> CHG' % (line[1], line[2]))
        print('WRITTEN %s (%d row(s) moved)' % (args.out, len(new)))
        return 0
    copies = load_copies(copy_paths(cfg, root, args.copies) + [args.durum])
    res = check(panel, cfg, now, status=load_status(args.status, root), copies=copies,
                decisions=read_decisions(root / cfg['decisions_file']),
                chg_map=read_json(root / cfg['chg_map']) or {}, done_since=done_since)
    out = getattr(sys.stdout, 'buffer', None)
    if out is not None:
        out.write((report(res) + '\n').encode('utf-8'))
        out.flush()
    else:
        sys.stdout.write(report(res) + '\n')
    return 1 if res['findings'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
