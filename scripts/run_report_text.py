"""Fixed report wording shared by the run analysis and the console (loop S7, DS7-3).

One copy of the Annex B.4 reasons for withholding FACT_CHECKER: the ordinary run
analysis (tools/analyze_ordinary_final_run.py) writes them into RUN_REPORT.md and
FINAL_STATUS.json, and the server's GET /runs/{run_id}/switches serves them to the
console. Both import them from here; neither keeps its own copy.

Also the report rows a sealed run may show (Annex B.8: counts and timings only).
An allowlist, not a list of rows to drop: a report row added later is withheld
from a sealed run until someone decides it carries no per-flaw result.

No model, no file, no network. Text only.
"""
from __future__ import annotations

# Annex B.4: both reasons, every report, whenever the run's review scope withholds it.
FACT_CHECKER_REASONS = (
    'switched off, not deleted: deleting the agent needs operator approval under the constitution and cannot be '
    'undone without code, while keeping it leaves LAW-III checks 87 and 127 unchanged and one cleared declaration '
    'restores it',
    'stays off: it returned five substantively wrong items in v7 and v8, byte-identical, and none correct in v5 '
    '(runs 110990c1, 6f896263, a6649672)')

# The report rows (labels as tools/analyze_ordinary_final_run.py writes them) a
# sealed run's report view keeps. Every other row, the recall, attribution and
# per-flaw rows included, is withheld for a sealed run.
SEALED_REPORT_ROWS = (
    'Purpose',
    'Sealed or exposed',
    'Date and time (UTC)',
    'Code commit',
    'Test manifest hash',
    'Backend and machine',
    'Instance type and price',
    'Cost',
    'Role separation',
    'What the result does not show',
)

# What a sealed run's views say in place of what they withhold.
SEALED_NOTE = ('Sealed test: counts and timings only. Finding text, unit ids, rule ids, '
               'reasons and per-flaw results are withheld (Annex B.8).')
