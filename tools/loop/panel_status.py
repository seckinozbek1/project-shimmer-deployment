"""Compact status for Seckin's control panel (Seckin 19 November 2026 13:16 and 13:18; language rule of 13:09).

    py -3.12 -X utf8 tools/loop/panel_status.py            # write panel_status.json, panel_fragment.html, panel.html
    py -3.12 -X utf8 tools/loop/panel_status.py --print    # the JSON on screen, nothing written
    py -3.12 -X utf8 tools/loop/panel_status.py --proof    # the fixture proof (a temp folder of fake records)

Read only, from the loop's records in the main checkout (tools/loop/shared_paths.py, SHIMMER_MAIN_CHECKOUT):
the planned steps (read with promise_watch's reader and its existence checks), the v1.05 plan's part ids, the
reaper's spend reading against the cap in config/loop_spend_limits.json, the backup coverage result file when the
lead saved one, the newest bars table, the open questions in FOR_SECKIN (a heading whose title starts with SORU,
inside the window, with no answer line and no entry in panel_answers.json), and the usage reading. Every record
and target is named in config/panel_status.json. It writes only into its out folder (default
docs/loop/private/panel) and never publishes: the lead republishes the panel with the Artifact tool, once per event.

Every Turkish text passes through `plain()`: codes, decision numbers, commit ids, file names, paths and tool words
are removed, em and en dashes become commas. Technical names go only in the one closing `teknik` line.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import promise_watch as pw  # noqa: E402
import session_state  # noqa: E402  (D-791: session files, checked before they are taken)
import shared_paths  # noqa: E402
from cloud_run_common import no_window  # noqa: E402  (HIDDEN-A; shared_paths put the repo root on sys.path)

CONFIG = HERE.parents[1] / 'config' / 'panel_status.json'
MONTHS = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim',
          'Kasım', 'Aralık']

CODE = re.compile(r'\b(?:D-S?\d+[a-z]?|[A-Z][A-Z0-9]+-[A-Z0-9-]*\d[A-Za-z0-9-]*|[A-Z]{1,3}\d+[a-z]?'
                  r'|(?=[0-9a-f]*\d)[0-9a-f]{7,40})\b|#\d+')
FILE = re.compile(r'\S*[\\/]\S+|\b[\w.-]+\.(?:md|jsonl|json|py|ps1|cmd|bat|txt|html|log|err|lock|flag|sh|exe|dll)\b'
                  r'|\b\w+_\w+\b')
DASHES = re.compile('[\u2014\u2013]')
HEAD = re.compile(r'^## (\d{4}-\d\d-\d\d \d\d:\d\d [+-]\d{4}): (.*)$')


def load_config(path=None):
    return json.loads(Path(path or CONFIG).read_text(encoding='utf-8'))


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def newest(main, pattern):
    found = sorted(glob.glob(str(Path(main) / pattern)))
    return Path(found[-1]) if found else None


def num(x, places=2):
    return ('%.*f' % (places, x)).replace('.', ',')


def when(t):
    return '%d %s %d saat %02d:%02d' % (t.day, MONTHS[t.month - 1], t.year, t.hour, t.minute)


def plain(text, cfg, limit=None):
    """Seckin's language rule on one text: no codes, numbers of decisions, file names, tool words or dashes."""
    s = DASHES.sub(',', str(text or ''))
    s = s.replace('**', '').replace('`', '')
    words = re.compile(r'\b(?:%s)\b' % '|'.join(re.escape(w) for w in cfg['tool_words']), re.I)

    def bad(part):
        return bool(CODE.search(part) or FILE.search(part) or words.search(part))

    s = re.sub(r'\(([^()]*)\)', lambda m: '' if bad(m.group(1)) else m.group(0), s)
    s = FILE.sub('', s)
    s = CODE.sub('', s)
    s = words.sub('', s)
    s = re.sub(r"(^|\s)'\w*", r'\1', s)          # a suffix left behind by a removed code ("seal'i")
    s = re.sub(r'\(\s*[,;:]?\s*\)', '', s)
    s = re.sub(r'\s+([,.;:!?])', r'\1', s)
    s = re.sub(r'([,;:])\s*(?=[,;:.])', '', s)
    s = re.sub(r'\s{2,}', ' ', s).strip(' ,;:-')
    limit = limit or cfg['text_max_chars']
    if len(s) > limit:
        cut = s[:limit]
        end = max(cut.rfind('. '), cut.rfind('? '))
        s = cut[:end + 1] if end > 40 else cut.rsplit(' ', 1)[0] + '...'
    return s


def group_label(step, cfg):
    for g in cfg['step_groups']:
        if step.startswith(g['prefix']):
            return g['label']
    return 'Adım'


def read_steps(path):
    """[(step, newest line)] in first-seen order; a later line replaces an earlier one, a close line ends it."""
    steps = {}
    for line in pw.read_jsonl(path):
        if isinstance(line, dict) and isinstance(line.get('step'), str) and line['step']:
            steps.pop(line['step'], None)
            steps[line['step']] = line
    return list(steps.items())


def step_state(line, now, pcfg, main):
    if line.get('closed'):
        return 'bitti'
    if pw.validate(line, pcfg):
        return 'kaydı okunamadı'
    try:
        if pw.done(line, pcfg, main):
            return 'çıktısı hazır'
        if pw.missing_needs(line, pcfg, main):
            return 'önceki işi bekliyor'
    except (OSError, KeyError, TypeError):
        return 'kaydı okunamadı'
    start = pw.parse_time(line['expected_start'])
    if start and start > now:
        return 'sırada, başlama %02d:%02d' % (start.hour, start.minute)
    return 'sürüyor ya da başlamayı bekliyor'


def v105_label(step_id, cfg):
    m = re.match(r'([A-Z])(\d+)$', step_id)
    if not m:
        return None
    item = cfg['v105_items'].get(m.group(1))
    return '%s, %s. adım' % (item, m.group(2)) if item else None


def plan_part(main, cfg, now):
    pcfg = pw.load_config()
    rec = cfg['records']
    labels = read_json(Path(main) / rec['labels']) or {}
    steps = read_steps(Path(main) / rec['planned_steps'])
    rows, counts = [], {}
    seen = {}
    for step, line in steps:
        label = labels.get(step)
        if not label and step.startswith(cfg['v105_prefix']):
            label = v105_label(step[len(cfg['v105_prefix']):], cfg)
        if not label:
            g = group_label(step, cfg)
            seen[g] = seen.get(g, 0) + 1
            label = '%s %d' % (g, seen[g])
        state = step_state(line, now, pcfg, main)
        counts[state] = counts.get(state, 0) + 1
        if state != 'bitti' or cfg.get('show_done_rows'):
            rows.append({'ad': plain(label, cfg, 80), 'durum': state})
    total = len(steps)
    done = counts.get('bitti', 0)
    return steps, rows, total, done


def v105_part(main, cfg, steps):
    plan = newest(main, cfg['records']['v105_plan_glob'])
    ids = []
    if plan:
        for raw in plan.read_text(encoding='utf-8', errors='replace').splitlines():
            m = re.match(r'^\|\s*([A-E]\d+)\s', raw)
            if m and m.group(1) not in ids:
                ids.append(m.group(1))
    prefix = cfg['v105_prefix']
    state = {s[len(prefix):]: ('bitti' if ln.get('closed') else 'açık') for s, ln in steps if s.startswith(prefix)}
    if not ids:
        ids = list(state)
    items = []
    for letter, name in cfg['v105_items'].items():
        mine = [i for i in ids if i.startswith(letter)]
        if mine:
            items.append({'ad': name, 'biten': sum(state.get(i) == 'bitti' for i in mine), 'toplam': len(mine)})
    return items, sum(x['biten'] for x in items), len(ids)


def bar(name, value, target, percent, text):
    return {'ad': name, 'deger': value, 'hedef': target, 'yuzde': max(0, min(100, int(round(percent)))),
            'metin': text}


def spend_bar(main, cfg):
    limits = read_json(Path(main) / cfg['records']['spend_limits']) or {}
    status = read_json(Path(main) / cfg['records']['reaper_status']) or {}
    try:
        cap = float(limits['remaining_baseline_usd']) + float(limits['remaining_limit_usd'])
        spent = float(status['total_spend_usd'])
    except (KeyError, TypeError, ValueError):
        return bar('Harcama', None, None, 0, 'Harcama kaydı okunamadı.')
    return bar('Harcama', round(spent, 2), cap, 100.0 * spent / cap,
               '%s USD harcandı. Sınır %s USD. Kalan %s USD.' % (num(spent), num(cap, 0), num(cap - spent)))


def coverage_bar(main, cfg):
    report = read_json(Path(main) / cfg['records']['coverage'])
    parts = (report or {}).get('parts') if isinstance(report, dict) else None
    if not isinstance(parts, list) or not parts:
        return bar('Yedek kapsamı', None, cfg['targets']['coverage_percent'], 0,
                   'Yedek kapsamının son sonucu kaydedilmemiş.')
    ok = sum(1 for p in parts if isinstance(p, dict) and p.get('status') == 'COVERED')
    return bar('Yedek kapsamı', ok, len(parts), 100.0 * ok / len(parts),
               'Güvende olan parça: %d. Toplam parça: %d.' % (ok, len(parts)))


def quality_line(main, cfg):
    path = newest(main, cfg['records']['bars_glob'])
    if not path:
        return None
    met = unmet = other = 0
    for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
        cells = [c.strip() for c in raw.strip().strip('|').split('|')]
        if not raw.startswith('|') or len(cells) < 4 or set(cells[0]) <= set('-: ') or cells[0] == 'Hedef':
            continue
        last = cells[-1]
        if last.startswith('+'):
            met += 1
        elif last.startswith('-'):
            unmet += 1
        else:
            other += 1
    return {'karsilanan': met, 'karsilanmayan': unmet, 'olculemeyen': other,
            'metin': 'Kalite çıtaları. Karşılanan: %d. Henüz karşılanmayan: %d. Ölçülemeyen ya da kısmen tutan: %d.'
                     % (met, unmet, other)}


def entries(text):
    out, cur = [], None
    for raw in text.splitlines():
        m = HEAD.match(raw)
        if m:
            cur = {'time': m.group(1), 'title': m.group(2), 'body': []}
            out.append(cur)
        elif raw.startswith('## '):
            cur = None
        elif cur is not None:
            cur['body'].append(raw)
    return out


def body_line(body, starts):
    for raw in body:
        s = raw.strip().lstrip('-* ').replace('**', '').strip()
        for w in starts:
            if s.startswith(w):
                return s[len(w):].lstrip(' :').strip()
    return None


def questions(main, cfg, now):
    rec = cfg['records']
    try:
        text = (Path(main) / rec['for_seckin']).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    answered = read_json(Path(main) / rec['answers']) or {}
    since = now - dt.timedelta(hours=cfg['soru_window_hours'])
    out = []
    for e in entries(text):
        if not e['title'].startswith('SORU'):
            continue
        t = dt.datetime.strptime(e['time'], '%Y-%m-%d %H:%M %z')
        if t < since or e['time'] in answered:
            continue
        if body_line(e['body'], cfg['answer_line_starts']) is not None:
            continue
        m = re.match(r'SORU\s*(\(([^)]*)\))?\s*:?\s*(.*)$', e['title'])
        urgent = bool(m and m.group(2) and 'ACİL' in m.group(2).upper())
        title = m.group(3) if m else e['title']
        durum = body_line(e['body'], ['Durum']) or next(
            (r.strip().lstrip('-* ') for r in e['body'] if r.strip() and not r.startswith('Hedefe')
             and not r.strip().lstrip('-* ').replace('**', '').startswith(('Soru', 'Öneri', 'Mod ', 'Bildirim'))), '')
        soru = body_line(e['body'], ['Soru']) or title
        oneri = body_line(e['body'], ['Önerim', 'Öneri']) or 'Öneri ana kayıtta.'
        out.append({'zaman': when(t), 'acil': urgent, 'durum': plain(durum, cfg) or 'Ayrıntı ana kayıtta.',
                    'soru': plain(soru, cfg) or 'Ayrıntı ana kayıtta.', 'oneri': plain(oneri, cfg)})
        if len(out) >= cfg['max_questions']:
            break
    return out


def usage_line(main, cfg, tz=None):
    for rel in cfg['records']['loop_status']:
        data = read_json(Path(main) / rel)
        if isinstance(data, dict) and data.get('seven_day_used_percentage') is not None:
            text = 'Haftalık kullanım yüzde %s.' % data['seven_day_used_percentage']
            reset = data.get('seven_day_resets_at')
            if isinstance(reset, (int, float)):
                text += ' Sıfırlanma: %s.' % when(dt.datetime.fromtimestamp(reset, tz or dt.timezone.utc).astimezone(tz))
            return text
    return None


def money(main, cfg):
    """Spent and left of the capped budget, the remaining forecast per version, storage not yet in a budget."""
    limits = read_json(Path(main) / cfg['records']['spend_limits']) or {}
    status = read_json(Path(main) / cfg['records']['reaper_status']) or {}
    out = {'satirlar': []}
    try:
        cap = float(limits['remaining_baseline_usd']) + float(limits['remaining_limit_usd'])
        spent = float(status['total_spend_usd'])
        out['satirlar'].append('Ortak bütçe %s USD. Harcanan %s USD. Kalan %s USD.' % (num(cap, 0), num(spent),
                                                                                       num(cap - spent)))
    except (KeyError, TypeError, ValueError):
        out['satirlar'].append('Harcama kaydı okunamadı.')
        cap = spent = None
    path = newest(main, cfg['records']['spend_list_glob'])
    text = path.read_text(encoding='utf-8', errors='replace') if path else ''
    pat = cfg['spend_list_patterns']
    total = 0.0
    seen = []
    for ver, usd in re.findall(pat['version_forecast'], text):
        if ver in seen:
            continue
        seen.append(ver)
        total += float(usd)
        out['satirlar'].append('Sürüm %s için kalan tahmin %s USD.' % (ver[1:], num(float(usd))))
    if seen and cap is not None:
        out['satirlar'].append('Tahminlerden sonra pay %s USD.' % num(cap - spent - total))
    m = re.search(pat['storage_month'], text)
    if m:
        out['satirlar'].append('Depolama aylık yaklaşık %s USD; henüz bir bütçeye bağlanmadı.' % num(float(m.group(1))))
    m = re.search(pat['unset_budget'], text)
    if m:
        out['satirlar'].append('Sürüm %s bütçesi henüz belirlenmedi.' % m.group(2)[1:])
    if not seen:
        out['satirlar'].append('Sürüm başına kalan tahmin okunamadı.')
    return out


def git(main, args, runner=None):
    """stdout of a read-only local git call, or None; never a fetch."""
    runner = runner or subprocess.run
    try:
        done = runner(['git', '-C', str(main)] + args, capture_output=True, text=True, timeout=30,
                      stdin=subprocess.DEVNULL, creationflags=no_window())
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def push_part(main, cfg, runner=None):
    try:
        text = (Path(main) / cfg['records']['push_record']).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return {'metin': 'Herkese açık koda gönderim kaydı okunamadı.', 'teknik': None}
    head, last, moved = re.compile(cfg['push_heading']), None, None
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        m = head.match(raw)
        if m:
            t = dt.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M %z')
            if last is None or t >= last[0]:
                mv = re.search(cfg['push_main_move'], '\n'.join(lines[i + 1:i + 6]))
                last, moved = (t, m.group(2)), (mv.group(2) if mv else None)
    if not last:
        return {'metin': 'Herkese açık koda gönderim kaydı yok.', 'teknik': None}
    waiting = git(main, ['rev-list', '--count', '%s..HEAD' % last[1]], runner)
    text = 'Herkese açık koda son gönderim: %s.' % when(last[0])
    text += (' O zamandan beri bekleyen değişiklik: %s.' % waiting) if waiting is not None else \
        ' Bekleyen değişiklik sayısı okunamadı.'
    return {'metin': text, 'zaman_iso': last[0].isoformat(), 'bekleyen': int(waiting) if waiting else None,
            'teknik': 'son gönderim: loop %s, public main %s' % (last[1][:8], (moved or '?')[:8])}


def issues_part(main, cfg, steps):
    path = Path(main) / cfg['records']['issues']
    data = read_json(path)
    if not isinstance(data, list):
        return {'metin': 'Konu listesi henüz okunmadı.', 'teknik': None}
    read_at = when(dt.datetime.fromtimestamp(path.stat().st_mtime).astimezone())
    open_n = sum(1 for x in data if str(x.get('state', '')).upper() == 'OPEN')
    closed_n = len(data) - open_n
    by_ms = {}
    for x in data:
        ms = (x.get('milestone') or {}).get('title') if isinstance(x.get('milestone'), dict) else None
        ms = ms or 'kilometre taşı yok'
        o, c = by_ms.get(ms, (0, 0))
        by_ms[ms] = (o + 1, c) if str(x.get('state', '')).upper() == 'OPEN' else (o, c + 1)
    closed_steps = {s for s, ln in steps if ln.get('closed')}
    planned = {s for s, _ in steps}
    imap = read_json(Path(main) / cfg['records']['issue_map']) or {}
    by_issue = {}
    for step, num_ in (imap.get('map') or {}).items():
        by_issue.setdefault(int(num_), []).append(step)
    open_set = {int(x['number']) for x in data if str(x.get('state', '')).upper() == 'OPEN' and 'number' in x}
    looks_done = sorted(n for n, st in by_issue.items()
                        if n in open_set and all(s in planned and s in closed_steps for s in st))
    rows = ['Konular %s tarihinde okundu. Açık %d, kapalı %d.' % (read_at, open_n, closed_n)]
    for ms, (o, c) in sorted(by_ms.items()):
        name = ms if ms == 'kilometre taşı yok' else 'Sürüm %s' % plain(ms.lstrip('vV'), cfg, 30)
        rows.append('%s: açık %d, kapalı %d.' % (name, o, c))
    rows.append('Bitmiş görünen ama açık konu: %d.' % len(looks_done))
    return {'satirlar': rows, 'acik': open_n, 'kapali': closed_n, 'bitmis_gorunen': len(looks_done),
            'teknik': ('bitmiş görünen açık konular: ' + ', '.join('#%d' % n for n in looks_done)) if looks_done
            else None}


def build(main=None, now=None, cfg=None, runner=None):
    cfg = cfg or load_config()
    main = Path(main) if main else shared_paths.main_checkout()
    now = now or dt.datetime.now().astimezone()
    steps, rows, total, done = plan_part(main, cfg, now)
    items, v_done, v_total = v105_part(main, cfg, steps)
    bars = [
        bar('Plan', done, total, 100.0 * done / total if total else 0,
            'Biten adım: %d. Toplam adım: %d.' % (done, total)),
        bar('Yeni sürüm parçaları', v_done, v_total, 100.0 * v_done / v_total if v_total else 0,
            'Biten parça: %d. Toplam parça: %d.' % (v_done, v_total)),
        spend_bar(main, cfg),
        coverage_bar(main, cfg),
    ]
    extra = len(rows) - cfg['max_plan_rows']
    push = push_part(main, cfg, runner)
    issues = issues_part(main, cfg, steps)
    tech = [t for t in (push.pop('teknik', None), issues.pop('teknik', None)) if t]
    status = {
        'baslik': 'Shimmer kontrol paneli',
        'son_guncelleme': when(now),
        'son_guncelleme_iso': now.isoformat(timespec='seconds'),
        'cubuklar': bars,
        'kalite': quality_line(main, cfg),
        'kullanim': usage_line(main, cfg, now.tzinfo),
        'para': money(main, cfg),
        'gonderim': push,
        'konular': issues,
        'sorular': questions(main, cfg, now),
        'oturumlar': session_state.collect(main=main),   # D-791: technical, never rendered
        'surum_parcalari': items,
        'plan': rows[:cfg['max_plan_rows']],
        'plan_fazlasi': 'Gösterilmeyen adım: %d.' % extra if extra > 0 else None,
        'teknik': '; '.join(tech + ['kaynaklar: %s; kurallar: config/panel_status.json' % ', '.join(
            Path(v).name for k, v in cfg['records'].items() if isinstance(v, str))]),
    }
    return status


def e(x):
    return html.escape(str(x), quote=True)


STYLE = ('<style>.ps{--ps-fg:#1d1d1f;--ps-mute:#5b5b66;--ps-line:#d9d9e0;--ps-fill:#2f6fde;--ps-warn:#b3261e;'
         'font:15px/1.45 system-ui,sans-serif;color:var(--ps-fg)}'
         '@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .ps{--ps-fg:#ececf1;--ps-mute:#a5a5b2;'
         '--ps-line:#3a3a44;--ps-fill:#7aa7ff;--ps-warn:#ff8a80}}'
         ':root[data-theme=dark] .ps{--ps-fg:#ececf1;--ps-mute:#a5a5b2;--ps-line:#3a3a44;--ps-fill:#7aa7ff;'
         '--ps-warn:#ff8a80}'
         '.ps h2{font-size:17px;margin:18px 0 8px}.ps .t{color:var(--ps-mute);font-size:13px}'
         '.ps .b{margin:8px 0}.ps .tr{height:8px;border-radius:4px;background:var(--ps-line);overflow:hidden}'
         '.ps .fi{height:100%;background:var(--ps-fill)}.ps .q{border:1px solid var(--ps-line);border-radius:8px;'
         'padding:8px 10px;margin:8px 0}.ps .ac{color:var(--ps-warn);font-weight:600}'
         '.ps table{border-collapse:collapse;width:100%}.ps td{border-top:1px solid var(--ps-line);padding:4px 6px;'
         'vertical-align:top}.ps .tech{color:var(--ps-mute);font-size:12px;margin-top:16px}</style>')


def fragment(status):
    out = [STYLE, '<section class="ps" lang="tr">', '<p class="t">Son güncelleme: %s</p>' % e(status['son_guncelleme'])]
    out.append('<h2>İlerleme</h2>')
    for b in status['cubuklar']:
        out.append('<div class="b"><div>%s: %s</div><div class="tr" role="progressbar" aria-valuenow="%d" '
                   'aria-valuemin="0" aria-valuemax="100"><div class="fi" style="width:%d%%"></div></div></div>'
                   % (e(b['ad']), e(b['metin']), b['yuzde'], b['yuzde']))
    for key in ('kalite', 'kullanim'):
        val = status.get(key)
        if val:
            out.append('<p>%s</p>' % e(val['metin'] if isinstance(val, dict) else val))
    out.append('<h2>Para</h2>')
    out.extend('<p>%s</p>' % e(x) for x in status['para']['satirlar'])
    out.append('<h2>Kod ve konular</h2><p>%s</p>' % e(status['gonderim']['metin']))
    konular = status['konular']
    out.extend('<p>%s</p>' % e(x) for x in konular.get('satirlar', [konular.get('metin', '')]))
    out.append('<h2>Size sorular</h2>')
    if not status['sorular']:
        out.append('<p>Şu an cevap bekleyen soru yok.</p>')
    for q in status['sorular']:
        out.append('<div class="q"><div class="t">%s%s</div><p><b>Durum:</b> %s</p><p><b>Soru:</b> %s</p>'
                   '<p><b>Öneri:</b> %s</p></div>' % (e(q['zaman']), ' <span class="ac">Acil</span>' if q['acil'] else '',
                                                    e(q['durum']), e(q['soru']), e(q['oneri'])))
    out.append('<h2>Yeni sürüm</h2><table>')
    for it in status['surum_parcalari']:
        out.append('<tr><td>%s</td><td>%d / %d bitti</td></tr>' % (e(it['ad']), it['biten'], it['toplam']))
    out.append('</table><h2>Plan</h2><table>')
    for r in status['plan']:
        out.append('<tr><td>%s</td><td>%s</td></tr>' % (e(r['ad']), e(r['durum'])))
    out.append('</table>')
    if status.get('plan_fazlasi'):
        out.append('<p class="t">%s</p>' % e(status['plan_fazlasi']))
    out.append('<p class="tech">%s</p></section>' % e(status['teknik']))
    return '\n'.join(out)


def page(status):
    return ('<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1"><title>Shimmer kontrol paneli</title><style>'
            ':root{--bg:#ffffff}@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#16161a}}'
            ':root[data-theme=dark]{--bg:#16161a}body{background:var(--bg);margin:0;padding:16px;max-width:760px;'
            'margin-inline:auto}</style></head><body><h1 style="font:600 20px system-ui,sans-serif;'
            'color:inherit">Shimmer kontrol paneli</h1>\n%s\n</body></html>\n' % fragment(status))


def write(status, out_dir, cfg):
    if len(page(status).encode('utf-8')) > cfg['max_bytes']:   # too big: finished rows go first, counted
        done_rows = [r for r in status['plan'] if r['durum'] == 'bitti']
        status['plan'] = [r for r in status['plan'] if r['durum'] != 'bitti']
        status['plan_fazlasi'] = 'Gösterilmeyen biten adım: %d.' % len(done_rows)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {'panel_status.json': json.dumps(status, ensure_ascii=False, indent=1),
             'panel_fragment.html': fragment(status), 'panel.html': page(status)}
    sizes = {}
    for name, text in files.items():
        data = text.encode('utf-8')
        if len(data) > cfg['max_bytes']:
            raise SystemExit('%s is %d bytes, over the %d limit' % (name, len(data), cfg['max_bytes']))
        (out_dir / name).write_bytes(data)
        sizes[name] = len(data)
    return sizes


# ---------------------------------------------------------------- fixture proof

BANNED = [re.compile(r'\bD-S?\d+'), re.compile(r'\b[\w-]+\.(?:md|jsonl|json|py|ps1|cmd|txt|html)\b'),
          re.compile('[\u2014\u2013]'), re.compile(r'\b(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b')]


def turkish_texts(obj, key=None):
    if key in ('teknik', 'oturumlar'):
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from turkish_texts(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from turkish_texts(v, key)
    elif isinstance(obj, str) and not key.endswith('_iso'):
        yield obj


def make_fixture(root):
    root = Path(root)
    (root / '.git').mkdir(parents=True)
    priv = root / 'docs' / 'loop' / 'private'
    priv.mkdir(parents=True)
    (root / 'config').mkdir()
    (root / '.claude').mkdir()
    lines = [
        {'step': 'v105:A1', 'owner': 'lead', 'needs': [], 'expected_start': '2026-11-19T02:00:00+03:00',
         'expected_output': []},
        {'step': 'v105:A2', 'owner': 'lead', 'needs': ['nothing_here/*.flag'],
         'expected_start': '2026-11-19T02:00:00+03:00', 'expected_output': []},
        {'step': 'v105:C1', 'owner': 'lead', 'needs': [], 'expected_start': '2026-11-19T15:00:00+03:00',
         'expected_output': ['out/c1.txt']},
        {'step': 'lane:x-y', 'owner': 'lead', 'needs': [], 'expected_start': '2026-11-19T10:00:00+03:00',
         'expected_output': ['out/done.txt']},
        {'step': 'role_N:S41d', 'owner': 'lead', 'needs': [], 'expected_start': '2026-11-19T10:00:00+03:00',
         'expected_output': []},
        {'step': 'v105:A1', 'closed': '2026-11-19T03:00:00+03:00', 'why': 'ded58c6f checks 547'},
        {'step': 'lane:old', 'closed': '2026-11-19T03:00:00+03:00', 'why': 'replaced'},
    ]
    (priv / 'PLANNED_STEPS.jsonl').write_text('\n'.join(json.dumps(x) for x in lines) + '\n', encoding='utf-8')
    (root / 'out').mkdir()
    (root / 'out' / 'done.txt').write_text('x', encoding='utf-8')
    (priv / 'V105_PLAN_20261119.md').write_text(
        '# plan\n| Sub-step | Start |\n|---|---|\n| A1 Speed | x |\n| A2 vLLM | x |\n| C1 Design | x |\n'
        '| E1 Merge | x |\n', encoding='utf-8')
    (root / 'config' / 'loop_spend_limits.json').write_text(json.dumps(
        {'remaining_baseline_usd': 197.0, 'remaining_limit_usd': 203.0}), encoding='utf-8')
    (priv / 'reaper_status.json').write_text(json.dumps({'total_spend_usd': 309.5772}), encoding='utf-8')
    (priv / 'backup_coverage_last.json').write_text(json.dumps(
        {'parts': [{'status': 'COVERED'}, {'status': 'COVERED'}, {'status': 'STALE'}, {'status': 'COVERED'}]}),
        encoding='utf-8')
    (priv / 'BARS_STATUS_20261118.md').write_text(
        '# Çıtalar\n| Hedef | Çıta | Bugün | Fark |\n|---|---|---|---|\n| M1 | 0,60 | 0,419 | -0,181 |\n'
        '| M7 | 0,80 | 0,90 | +0,10 |\n| X | 1 | yok | ölçülemez |\n', encoding='utf-8')
    (root / '.claude' / 'loop_status.json').write_text(json.dumps(
        {'seven_day_used_percentage': 47, 'seven_day_resets_at': 1795593600}), encoding='utf-8')
    (priv / 'SPEND_LIST_20261119.md').write_text(
        '# Remaining\n| x | 17.65 (at 0.20 USD per GiB-month); 18.95 if billed |\n'
        '(a) 400 USD cap, v1.0 and v1.05 only: v1.0 forecast 45.65 (caps 68.47) + v1.05 forecast 32.83 (caps 49.26)\n'
        '(b) v1.1, budget NOT SET (Seckin sets it later)\n', encoding='utf-8')
    (priv / 'PUSH_RECORD.md').write_text(
        '# Push record (D-S5)\n\n## 2026-11-18 14:47 +0300: the code snapshot of loop 3ca7fe8e (gate)\n\n'
        'main 3680687 to 843112c2 (a fast-forward)\n\n'
        '## 2026-11-18 20:58 +0300: the code snapshot of loop 3efb3a37 (fourth gate)\n\n'
        'From the clean push clone, branch export-1115. main 843112c2 to 0e9974ad (a fast-forward)\n', encoding='utf-8')
    (priv / 'gh_issues_last.json').write_text(json.dumps([
        {'number': 241, 'state': 'OPEN', 'milestone': {'title': 'v1.05'}, 'title': 'speed'},
        {'number': 278, 'state': 'OPEN', 'milestone': {'title': 'v1.05'}, 'title': 'red lines'},
        {'number': 12, 'state': 'CLOSED', 'milestone': {'title': 'v1.0'}, 'title': 'x'},
        {'number': 13, 'state': 'OPEN', 'milestone': None, 'title': 'y'}]), encoding='utf-8')
    (priv / 'event_issue_map.json').write_text(json.dumps(
        {'version': 1, 'map': {'v105:A1': 241, 'v105:A2': 278}}), encoding='utf-8')
    (priv / 'FOR_SECKIN.md').write_text(
        '# For Seckin\n\n'
        '## 2026-11-19 12:06 +0300: SORU: SciTab D3 parçası çekilemedi (D-760, cell_claim); eşik ne olsun?\n'
        'Hedefe uzaklık: 0,615/0,60.\n'
        '- Durum: Rol B\'nin D3 çekimi 01:46\'da durmuş \u2014 havuzda uygun iddia yok (docs/loop/x.md, 9a079383).\n'
        '- Önerim (a): dürüst ve bedava; RemoteTrigger gerekmez, PLANNED_STEPS.jsonl değişmez.\n'
        '## 2026-11-19 11:00 +0300: SORU (ACİL, kurul): disk doluyor\n'
        '- Durum: Boş yer azalıyor.\n'
        'Soru: Eşitlemeyi durdurayım mı?\n'
        'Öneri: Durdurmak.\n'
        '## 2026-11-19 10:00 +0300: SORU: cevaplanmış soru\n'
        '- Durum: eski.\n'
        'Seckin: evet (10:05)\n'
        '## 2026-11-19 09:00 +0300: SORU: panel kaydında cevaplı\n'
        '- Durum: eski.\n'
        '## 2026-11-12 09:00 +0300: SORU: pencere dışında\n'
        '- Durum: çok eski.\n'
        '## 2026-11-19 08:00 +0300: Bilgi: soru değil\n', encoding='utf-8')
    (priv / 'panel_answers.json').write_text(json.dumps({'2026-11-19 09:00 +0300': 'answered 12:00'}),
                                             encoding='utf-8')
    (priv / 'panel_labels.json').write_text(json.dumps({'role_N:S41d': 'Müzakere ölçümünün yeniden okunması'}),
                                            encoding='utf-8')
    sess = priv / 'panel' / 'sessions'
    sess.mkdir(parents=True)
    (sess / 'lead.json').write_text(json.dumps({'project': root.name, 'session': 'lead', 'time': 'x', 'state': 'y'}),
                                    encoding='utf-8')
    (sess / 'other.json').write_text(json.dumps({'project': 'another-project', 'session': 'other'}), encoding='utf-8')
    return root


def proof():
    cfg = load_config()
    now = dt.datetime(2026, 11, 19, 13, 40, tzinfo=dt.timezone(dt.timedelta(hours=3)))
    with tempfile.TemporaryDirectory() as tmp:
        root = make_fixture(Path(tmp) / 'main')
        calls = []

        def fake_git(argv, **kw):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout='83\n', stderr='')
        status = build(main=root, now=now, cfg=cfg, runner=fake_git)
        sizes = write(status, root / 'docs' / 'loop' / 'private' / 'panel', cfg)
        frag = (root / 'docs' / 'loop' / 'private' / 'panel' / 'panel_fragment.html').read_text(encoding='utf-8')
    bars = {b['ad']: b for b in status['cubuklar']}
    assert status['son_guncelleme'] == '19 Kasım 2026 saat 13:40', status['son_guncelleme']
    assert (bars['Plan']['deger'], bars['Plan']['hedef']) == (2, 6), bars['Plan']
    assert (bars['Yeni sürüm parçaları']['deger'], bars['Yeni sürüm parçaları']['hedef']) == (1, 4)
    assert bars['Harcama']['hedef'] == 400.0 and bars['Harcama']['yuzde'] == 77, bars['Harcama']
    assert '309,58 USD' in bars['Harcama']['metin'] and '90,42 USD' in bars['Harcama']['metin']
    assert (bars['Yedek kapsamı']['deger'], bars['Yedek kapsamı']['hedef'], bars['Yedek kapsamı']['yuzde']) == (3, 4, 75)
    assert (status['kalite']['karsilanan'], status['kalite']['karsilanmayan'], status['kalite']['olculemeyen']) == (1, 1, 1)
    assert status['kullanim'] == 'Haftalık kullanım yüzde 47. Sıfırlanma: 25 Kasım 2026 saat 11:00.', status['kullanim']
    para = status['para']['satirlar']
    assert para[0] == 'Ortak bütçe 400 USD. Harcanan 309,58 USD. Kalan 90,42 USD.', para
    assert 'Sürüm 1.0 için kalan tahmin 45,65 USD.' in para and 'Sürüm 1.05 için kalan tahmin 32,83 USD.' in para
    assert 'Tahminlerden sonra pay 11,94 USD.' in para, para
    assert 'Depolama aylık yaklaşık 17,65 USD; henüz bir bütçeye bağlanmadı.' in para, para
    assert 'Sürüm 1.1 bütçesi henüz belirlenmedi.' in para, para
    g = status['gonderim']
    assert g['metin'] == ('Herkese açık koda son gönderim: 18 Kasım 2026 saat 20:58. '
                          'O zamandan beri bekleyen değişiklik: 83.'), g
    assert calls and calls[0][-2:] == ['--count', '3efb3a37..HEAD'] and 'fetch' not in calls[0], calls
    k = status['konular']
    assert (k['acik'], k['kapali'], k['bitmis_gorunen']) == (3, 1, 1), k
    assert 'Sürüm 1.05: açık 2, kapalı 0.' in k['satirlar'] and k['satirlar'][0].startswith('Konular '), k
    assert '#241' in status['teknik'] and '#278' not in status['teknik'] and '0e9974ad' in status['teknik']
    qs = status['sorular']
    assert len(qs) == 2, qs
    assert qs[0]['soru'].startswith('SciTab parçası çekilemedi') and 'eşik ne olsun?' in qs[0]['soru'], qs[0]
    assert qs[0]['durum'].startswith("Rol B'nin çekimi"), qs[0]
    assert 'Remote' not in qs[0]['oneri'] and 'dürüst ve bedava' in qs[0]['oneri'], qs[0]
    assert qs[1]['acil'] and qs[1]['soru'] == 'Eşitlemeyi durdurayım mı?' and qs[1]['oneri'] == 'Durdurmak.'
    states = {r['ad']: r['durum'] for r in status['plan']}
    assert states['Çalışma hızı iyileştirmeleri, 2. adım'] == 'önceki işi bekliyor', states
    assert states['Öğrenen ağ ve kavram haritası, 1. adım'] == 'sırada, başlama 15:00', states
    assert states['Yan çalışma 1'] == 'çıktısı hazır', states
    assert states['Müzakere ölçümünün yeniden okunması'] == 'sürüyor ya da başlamayı bekliyor', states
    assert states['Çalışma hızı iyileştirmeleri, 1. adım'] == 'bitti' and states['Yan çalışma 2'] == 'bitti', states
    assert len(status['plan']) == 6, status['plan']
    texts = list(turkish_texts(status))
    tech_free = frag.split('<p class="tech">')[0]
    for t in texts + [re.sub(r'<style>.*?</style>', '', tech_free, flags=re.S)]:
        for rx in BANNED:
            assert not rx.search(t), (rx.pattern, t)
    assert any(c in ''.join(texts) for c in 'çğıöşüİ')
    assert all(n < 20000 for n in sizes.values()), sizes
    o = status['oturumlar']
    assert (o['taken'], o['refused'], o['taken_names']) == (1, 1, ['lead']), o
    assert o['refused_files'] == [{'name': 'other.json', 'reason': 'project is not this repository'}], o
    print('panel_status proof: PASS (bars %d, questions %d, plan rows %d, sizes %s)'
          % (len(bars), len(qs), len(status['plan']), ', '.join('%s %d B' % kv for kv in sizes.items())))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--proof', action='store_true')
    ap.add_argument('--print', action='store_true')
    ap.add_argument('--out-dir')
    args = ap.parse_args(argv)
    if args.proof:
        return proof()
    cfg = load_config()
    main_root = shared_paths.main_checkout()
    status = build(main=main_root, cfg=cfg)
    if args.print:
        sys.stdout.buffer.write((json.dumps(status, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))
        return 0
    sizes = write(status, args.out_dir or (main_root / cfg['out_dir']), cfg)
    print('panel written: %s' % ', '.join('%s %d B' % kv for kv in sizes.items()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
