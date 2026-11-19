"""Proofs for tools/loop/seckin_language_check.py (D-780), on fixture files in a temporary folder only;
nothing private is read. `check()` runs the tests, then neutralises each rule in turn, requires a failure,
restores it and requires a pass.

    py -3.12 -X utf8 tools/loop/seckin_language_checks.py
"""
from __future__ import annotations

import io
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seckin_language_check as slc  # noqa: E402

CLEAN = ('## 2026-11-19 13:30 +0300: Lütfen başlat: iki oturum yeniden hazır\n'
         'Hedefe uzaklık: Müzakerede çatışma bulma 0 (hedef 0,60); bütçe kalan 90,43 USD.\n'
         '- Durum: iki oturum da durmuştu. Nedenini buldum.\n'
         '- Soru: ikisini şimdi başlatayım mı?\n'
         '- Öneri: evet, ikisi aynı anda çalışabilir; ve/veya sırayla.\n'
         'Mod turbo (düşük kullanım düzeni).\n'
         'Bildirim kaydı: anlık bildirim gönderilmedi (soru yok).\n'
         'Teknik satır: start_n_s41d.cmd (docs\\loop\\private\\role_starts), karar D-780, commit bce2ff37.\n')
DIRTY = ('## 2026-11-19 13:40 +0300: Silme bitti\n'
         '- Kayıt deletion_log.txt dosyasında; bu karar D-777 ile geldi \u2014 hepsi bu.\n'
         'Teknik satır: safe_delete.py, D-776.\n')
OLD = ('## 2026-11-19 13:03 +0300: Silme bitti (D-777): kayıt deletion_log.txt\n'
       'Teknik satır: yok.\n')


def write(folder, for_seckin, alert='# ALERT\n'):
    (Path(folder) / slc.FOR_SECKIN_NAME).write_text(for_seckin, encoding='utf-8')
    (Path(folder) / slc.ALERT_NAME).write_text(alert, encoding='utf-8')


class SeckinLanguageChecks(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.private = Path(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def test_a_clean_entry_passes_and_its_technical_line_is_exempt(self):
        write(self.private, '# For Seckin\n\n' + CLEAN)
        code, lines = slc.check(self.private)
        self.assertEqual(code, 0, lines)
        self.assertIn('FOR_SECKIN.md: 1 entries since 2026-11-19 13:09 +0300 read, 0 with a finding', lines[0])
        self.assertTrue(lines[-1].endswith('nothing flagged: PASS'), lines)

    def test_a_file_name_a_decision_number_and_an_em_dash_fail(self):
        write(self.private, '# For Seckin\n\n' + DIRTY + CLEAN)
        code, lines = slc.check(self.private)
        self.assertEqual(code, 1)
        items, read, untimed = slc.scan_for_seckin((self.private / slc.FOR_SECKIN_NAME).read_text(encoding='utf-8'))
        self.assertEqual((read, untimed), (2, 0))
        self.assertEqual(items, [('2026-11-19 13:40 +0300: Silme bitti',
                                  {'file_name': 1, 'decision_number': 1, 'em_dash': 1})])
        self.assertIn('  2026-11-19 13:40 +0300: Silme bitti | decision_number 1, file_name 1, em_dash 1', lines)
        self.assertNotIn('deletion_log', '\n'.join(lines))   # counts and headings only, never the text

    def test_the_technical_line_is_exempt_only_as_the_one_closing_line(self):
        moved = CLEAN.replace('Mod turbo', 'Teknik satır: start_x.cmd\nMod turbo')
        counts = slc.scan_for_seckin(moved)[0][0][1]
        self.assertEqual(counts.get('technical_line_not_closing'), 2)
        self.assertGreaterEqual(counts.get('file_name', 0), 2)
        bare = CLEAN.replace('Teknik satır:', 'Teknik bilgi:')
        counts = slc.scan_for_seckin(bare)[0][0][1]
        self.assertEqual((counts['file_name'], counts['decision_number'], counts['commit_id'],
                          counts['backslash_path']), (1, 1, 1, 1))

    def test_header_lines_are_exempt(self):
        text = CLEAN.replace('bütçe kalan 90,43 USD.', 'bütçe D-708, durum.json.')
        self.assertEqual(slc.scan_for_seckin(text)[0], [])
        self.assertEqual(slc.scan_for_seckin(text.replace('Hedefe uzaklık:', 'Uzaklık:'))[0][0][1],
                         {'decision_number': 1, 'file_name': 1})

    def test_entries_before_the_decision_time_are_not_read(self):
        items, read, untimed = slc.scan_for_seckin('# For Seckin\n\n' + OLD + '## no time here\nD-1 x.py\n')
        self.assertEqual((items, read, untimed), ([], 0, 1))
        self.assertEqual(len(slc.scan_for_seckin(OLD, since=slc._time('2026-11-19 13:00', '+0300'))[0]), 1)

    def test_paths_and_commit_ids(self):
        scan = slc.scan_text
        self.assertEqual(scan('_xfer/N_to_lead/S41c_HANDBACK.json'), {'file_name': 1, 'slash_path': 1})
        self.assertEqual(scan('external/s05 klasörü'), {'slash_path': 1})
        self.assertEqual(scan('ve/veya, 0,435/0,60, 15,71 GiB, 2026-11-19 13:09 +0300, 2026-11-19T05:40:43+00:00'),
                         {})
        self.assertEqual(scan('C:\\Users\\x klasörü'), {'backslash_path': 1})
        self.assertEqual(scan('birleşti: bce2ff37 ve 7d322ae5'), {'commit_id': 2})
        self.assertEqual(scan('deadbeef 1234567 abcdef0123'), {'commit_id': 1})
        self.assertEqual(scan('D-S110 ve D-780'), {'decision_number': 2})

    def test_alert_lines_since_the_decision_time(self):
        alert = ('# ALERT\n\n'
                 '2026-11-19 13:20 +0300: Disk 25 GiB boş; bir şey silinmedi.\n\n'
                 '2026-11-19 13:21 +0300: Rol dönüşü alınmadı: _xfer/N_to_lead/S41c_HANDBACK.json\n\n'
                 '2026-11-19 13:22 +0300: Disk doldu. Teknik satır: disk_sweep.py, D-770.\n\n'
                 'CLEARED 13:25 (x.py): 2026-11-19 13:07 +0300: eski satır D-1.\n\n'
                 'Earlier lines, kept as they were:\n')
        write(self.private, '# For Seckin\n', alert)
        items, read, untimed = slc.scan_alert(alert)
        self.assertEqual((read, untimed), (3, 1))
        self.assertEqual(items, [('2026-11-19 13:21 +0300', {'file_name': 1, 'slash_path': 1})])
        code, lines = slc.check(self.private)
        self.assertEqual(code, 1)
        self.assertIn('ALERT.md: 3 lines since 2026-11-19 13:09 +0300 read, 1 with a finding, 1 untimed not read',
                      lines)

    def test_an_unreadable_file_is_unable(self):
        (self.private / slc.FOR_SECKIN_NAME).write_text('# For Seckin\n', encoding='utf-8')
        code, lines = slc.check(self.private)
        self.assertEqual(code, 2)
        self.assertTrue(lines[-1].endswith('UNABLE'))


NEUTRALISED = (
    ('PATTERNS', tuple(p for p in slc.PATTERNS if p[0] != 'em_dash'), ('test_a_file_name_a_decision_number_and_an_em_dash_fail',)),
    ('PATTERNS', tuple(p for p in slc.PATTERNS if p[0] != 'decision_number'), ('test_a_file_name_a_decision_number_and_an_em_dash_fail',)),
    ('PATTERNS', tuple(p for p in slc.PATTERNS if p[0] != 'file_name'), ('test_a_file_name_a_decision_number_and_an_em_dash_fail',)),
    ('PATTERNS', tuple(p for p in slc.PATTERNS if p[0] != 'commit_id'), ('test_paths_and_commit_ids',)),
    ('PATTERNS', tuple(p for p in slc.PATTERNS if p[0] != 'backslash_path'), ('test_paths_and_commit_ids',)),
    ('_slash_path_counts', lambda token: True, ('test_paths_and_commit_ids',)),
    ('TECHNICAL', 'no such line:', ('test_a_clean_entry_passes_and_its_technical_line_is_exempt',)),
    ('HEADER_LINES', ('Mod ',), ('test_header_lines_are_exempt',)),
    ('SINCE', slc._time('2026-11-01 00:00', '+0300'), ('test_entries_before_the_decision_time_are_not_read',)),
    ('is_header_line', lambda line: True, ('test_a_file_name_a_decision_number_and_an_em_dash_fail',)),
    ('FULL_TIME', re.compile(r'(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) (\+0400)'), ('test_alert_lines_since_the_decision_time',)),
)


def passes(*names):
    suite = unittest.TestSuite(SeckinLanguageChecks(n) for n in names) if names else \
        unittest.defaultTestLoader.loadTestsFromTestCase(SeckinLanguageChecks)
    return unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(suite).wasSuccessful()


def check():
    if not passes():
        return 'FAIL', 'tools/loop/seckin_language_checks.py does not pass'
    proofs = []
    for name, mutant, names in NEUTRALISED:
        with patch.object(slc, name, mutant):
            failed = not passes(*names)
        restored = passes(*names)
        if not (failed and restored):
            return 'FAIL', 'seckin_language_check.%s neutralised: failed=%s, restored pass=%s' % (name, failed, restored)
        proofs.append(name)
    return 'PASS', ('the D-780 form check passes a clean FOR_SECKIN entry with its one closing Teknik satır line '
                    'exempt, fails an entry with a file name, a decision number and an em dash in the main text, '
                    'exempts the header lines, reads only entries and ALERT lines at or after 13:09, and prints '
                    'counts and headings only; neutralised, failed, restored, passed: %d (%s)'
                    % (len(proofs), ', '.join(proofs)))


if __name__ == '__main__':
    status, detail = check()
    print(status, detail)
    sys.exit(0 if status == 'PASS' else 1)
