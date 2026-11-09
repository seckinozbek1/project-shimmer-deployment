"""The public progress page (D-S98, D-S102): charts and tables of every measured attempt, from records only.

    py -3.12 -X utf8 tools/progress_charts.py --root <the loop worktree> --scoreboard <file>
        --ledger <file> --item-sets <folder> --out docs/progress
    py -3.12 -X utf8 tools/progress_charts.py --print-schema

`--root` is the checkout that holds the committed records (the loop worktree). The private records are
named on the command line, each required and with no default, and never named in this file:
`--scoreboard` the private scoreboard file, `--ledger` the budget ledger (`--r-ledger` role R's, when
it exists) and `--item-sets` the item-set folder, which is read for nothing and only refused in the
output. `--out` is the folder the page is written to (`docs/progress/` of the branch that is pushed).
Nothing is typed by hand: every figure comes from one of these records, and a record that is missing
leaves its section saying so. `--print-schema` prints the scoreboard's three tables as this script
reads them (D-S102 item 4), each column with its meaning, for the lead to adopt into the scoreboard.

- The benchmarks (D-S92, D-S94, D-S102 items 2, 4 and 14): the scoreboard's table headed "Row", one
  line per measurement and benchmark. Per benchmark and probe, four things on the same items: the
  system, B1 and the cloud reference over attempts, each with its 95 percent interval and the unit the
  interval resamples, and the published figure as a labelled reference line with its source and its
  setting differences. The gate's two carry the D-S92 bars as dashed lines, read from the scoreboard's
  own text. A row on a sealed, test or fresh set is refused here: the fresh set appears only after its
  single read, through its own record. A benchmark whose rows name two metrics or class settings is
  refused, so no axis mixes them.
- The model-backed roles (D-S102 item 6): every agent of `config/agent_registry.json` and every trained
  part, with the scoreboard's table headed "Role" where it has a row (trained and untrained figures,
  the margin, the held-out value with its interval, the attempt, or the reason it is not trained).
- The trained parts: committed read records `docs/loop/stages/*_HALF_A_*.json` of a schema this script
  declares (`TRAINED_SCHEMAS`), against the untrained form and the written margin, labelled in-sample
  (the tuning half chose the candidate); held-out openings from `docs/loop/HELDOUT_OPENINGS.md`.
- Other measured evaluations (D-S102 item 10): the scoreboard's table headed "Evaluation"; each one
  D-S102 names and the scoreboard does not yet hold is listed as such.
- Thresholds (D-S102 item 9): the bars, every margin, the D-S80 time targets and the budget lines; and
  each figure's factor record and machine change.
- Cost: every ledger with launch lines (the budget ledger, and role R's ledger when `--r-ledger`
  names it): cumulative actual spend at each run's end against the budget and the hard stop
  now in force, and the cumulative forecast at each launch. A launch is counted once across ledgers.
- Time: `docs/loop/stages/TIME_BUDGET.md`'s targets table, measured before the measurements were
  standardised, so a table only (D-S98 item 5).
- Earlier results: `docs/loop/stages/REPORT_COMPARABILITY.md`'s inventory, a table only.

Charts hold standardised measurements only and start at the first one (D-S98 item 5); everything earlier
is in a labelled table, never on the same axes. The page is one file, `index.html`, the interactive
dashboard (D-S98 items 6 and 7: every chart and table on one page, HTML only, no PNG and no Markdown
fallback; Plotly, one pinned version from its CDN), served by GitHub Pages from `docs/`. Hovering a point
shows what the scoreboard holds for it and says "not recorded" for the rest; the self-test holds the
hover text to the scoreboard's cells. The output carries no local path, no evidence path and no em dash,
and `check_output` refuses to leave it otherwise. Two runs on the same records write the same files.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

PLOTLY = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"  # pinned, jsDelivr
OPENINGS = Path("docs/loop/HELDOUT_OPENINGS.md")
TIME_BUDGET = Path("docs/loop/stages/TIME_BUDGET.md")
COMPARABILITY = Path("docs/loop/stages/REPORT_COMPARABILITY.md")
STAGES = Path("docs/loop/stages")
REGISTRY = Path("config/agent_registry.json")
TRAINED_SCHEMAS = {"auditor-rule-check-half-a-v1": "half_a_macro_f1"}
BENCHMARKS = ("ContraDoc", "SciTab")  # the gate's two
PROBE = ("CLadder", "Corr2Cause")  # the causal-readiness probe: an indicator, not a Shimmer benchmark (D-S78)
PROBE_LABEL = "indicator, not a Shimmer benchmark"
# Every benchmark in use (D-S98 item 8); one not yet measured is listed as such, never left out.
BENCHMARKS_IN_USE = ("ContraDoc", "SciTab", "PUBHEALTH", "CLadder", "Corr2Cause")
# Each benchmark's own paper's primary metric with its class setting (D-S99, D-376, D-S102 item 5), as
# the rules written before any read name it; a scoreboard row's own metric and setting are shown first.
METRIC = {"ContraDoc": "binary judgment accuracy, 2 classes", "SciTab": "macro-F1, 3 classes",
          "PUBHEALTH": "macro-F1, 4 classes", "CLadder": "accuracy over yes and no answers, 2 classes",
          "Corr2Cause": "F1 of the valid class, 2 classes"}
OTHER_RULES = Path("docs/loop/stages/targets/OTHER_DOMAIN_RULES.md")
TARGETS = Path("docs/loop/stages/targets/TARGET_TABLE.md")
CAUSAL_PLAN = Path("docs/loop/stages/CAUSAL_PROBE_PLAN.md")
# The published figure drawn as each other benchmark's reference line: the open model with no training on
# the task, zero-shot, in the paper's primary metric. The figure is read from the record, never typed here;
# the full tables are listed beside the chart. (benchmark: (record, row's first cell starts with, column))
REFERENCE_ROWS = {"PUBHEALTH": (OTHER_RULES, ("Zero-shot, single prompt", "Mistral-7B"), "Figure"),
                  "CLadder": (CAUSAL_PLAN, ("LLaMa",), "Overall"),
                  "Corr2Cause": (CAUSAL_PLAN, ("RoBERTa MNLI (open",), "F1")}
PRE_STANDARD = re.compile(r"direction only|pre-standard|not a gate figure", re.I)
BAR_DEFAULTS = (10.0, 5.0)  # D-S92's defaults; the scoreboard's own sentences are read first
REFUSED_SETS = re.compile(r"seal|test|fresh", re.I)
LOCAL_PATH = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/](?!/)|/Users/|/home/|\\Users\\")
EM_DASH = chr(0x2014)
NOT_RECORDED = "not recorded"

# ---- the scoreboard's schema (D-S102 item 4) ------------------------------------------------------
# Three tables, each found by its first header cell. A figure is a percentage written "value [low, high]",
# the 95 percent interval over the column "Bootstrap unit". The page reads only the columns that exist.

BENCH_COLUMNS = (
    ("Row", "the attempt's id; every benchmark line of one measurement carries the same one"),
    ("Time", "local time the figures were read, YYYY-MM-DD HH:MM"),
    ("What changed", "the one change this attempt measures, in plain words; \"direction only\" keeps the "
                     "line off the charts"),
    ("Set", "the items read (the held-out quick subset, the claim set, ...); never a sealed, test or fresh set"),
    ("Benchmark", "ContraDoc, SciTab, PUBHEALTH, CLadder or Corr2Cause, one line each"),
    ("Primary metric (D-S99)", "the paper's own metric named in full, never bare accuracy"),
    ("Class setting", "the label set it is read in, for example 3 classes"),
    ("n", "the items scored"),
    ("Bootstrap unit", "what the interval resamples: items, or the unit items share when they are not "
                       "independent (SciTab: tables, a cluster bootstrap; D-S102 item 14)"),
    ("System (95% CI)", "the whole system as it would ship, value [low, high], in percent"),
    ("B1 (95% CI)", "the bare model on the same items, value [low, high], in percent"),
    ("Cloud reference (95% CI)", "the cloud reference model on the same items, value [low, high], in percent"),
    ("Gap to (a) / (b)", "points to bar (a) and to bar (b); the gate's two benchmarks only"),
    ("Machine type", "the rented type the system arm ran on; an arm on another type says so in Factor record"),
    ("Price (USD/h)", "that type's hourly price at launch"),
    ("Region", "the provider region"),
    ("Minutes", "the run's minutes, launch to end"),
    ("Speed (items/h)", "items scored an hour"),
    ("Run cost (USD)", "this run's actual cost"),
    ("Cumulative cost (USD)", "the loop's spend after this run"),
    ("Evidence", "the run folder or record holding the figures; a private path shows on the page as (record)"),
    ("Factor record", "the D-S82 factor record"),
    ("Since last", "each arm's change since this benchmark's last line"),
)
ROLE_COLUMNS = (
    ("Role", "a registry agent's name, or a trained part's name"),
    ("Trained", "yes or no"),
    ("Attempt", "the attempt number"),
    ("Metric and setting", "the metric the part is read in, with its class setting"),
    ("Untrained (95% CI)", "the untrained form on the tuning half, value [low, high]"),
    ("Trained (95% CI)", "the chosen candidate on the tuning half (in-sample), value [low, high]"),
    ("Margin written", "the margin written before the read"),
    ("Held-out value (95% CI)", "the held-out read as a value, value [low, high]"),
    ("Held-out n", "the held-out items scored"),
    ("Bootstrap unit", "what the held-out interval resamples"),
    ("Result", "pass or fail, as the opening was read"),
    ("Evidence", "the read record; a private path shows on the page as (record)"),
    ("Reason not trained", "for a role with no training, the stated reason"),
)
EVAL_COLUMNS = (
    ("Evaluation", "its name, as D-S102 item 10 lists it"),
    ("Time", "local time it was read"),
    ("Set", "the items read"),
    ("Metric and setting", "the metric, with its class setting"),
    ("n", "the items scored"),
    ("Bootstrap unit", "what the interval resamples"),
    ("Value (95% CI)", "value [low, high]"),
    ("Evidence", "the record; a private path shows on the page as (record)"),
    ("Factor record", "the D-S82 factor record"),
    ("State", "requested, in progress, done or verified (D-S101), with its evidence for the last two"),
)
SCHEMA = (("Benchmark rows", BENCH_COLUMNS), ("Model-backed roles", ROLE_COLUMNS),
          ("Other measured evaluations", EVAL_COLUMNS))
EVALUATIONS_EXPECTED = ("Development-case recall", "Clean-twin false positives", "Meaningful-output sample",
                        "Computed path scored apart", "Flag precision", "Fresh-read scorer",
                        "S8 sealed evaluation")
HOVER_FIELDS = ("n", "Bootstrap unit", "System (95% CI)", "B1 (95% CI)", "Cloud reference (95% CI)",
                "Gap to (a) / (b)", "Machine type", "Price (USD/h)", "Region", "Minutes", "Speed (items/h)",
                "Run cost (USD)", "Cumulative cost (USD)", "Factor record", "Since last")


def schema_text():
    out = []
    for title, columns in SCHEMA:
        names = [c for c, _ in columns]
        out.append("## %s\n" % title)
        out.append("| %s |" % " | ".join(names))
        out.append("|%s" % ("---|" * len(names)))
        out.append("| (none yet) |%s\n" % (" |" * (len(names) - 1)))
        out += ["- **%s**: %s." % (c, meaning) for c, meaning in columns]
        out.append("")
    return "\n".join(out)


# ---- reading the records -------------------------------------------------------------------------

def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def table_rows(text, first_header):
    """The rows of the first Markdown table whose header starts with `first_header`, as cell lists."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("| " + first_header):
            rows = []
            for row in lines[i + 2:]:
                if not row.startswith("|"):
                    break
                rows.append(_cells(row))
            return rows
    return []


def named_rows(text, first_header):
    """(header, rows as {column: cell}) of the table whose first header cell is `first_header`; a row
    whose first cell is in brackets, such as "(none yet)", is not a row."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("| %s |" % first_header):
            head, rows = _cells(line), []
            for row in lines[i + 2:]:
                if not row.startswith("|"):
                    break
                cells = _cells(row)
                if cells and not cells[0].startswith("("):
                    rows.append(dict(zip(head, cells)))
            return head, rows
    return None, []


def field(row, column):
    value = row.get(column)
    return value.strip() if value and value.strip() else None


FIGURE = re.compile(r"^\s*(-?[0-9]+(?:\.[0-9]+)?)\s*%?\s*(?:\[\s*(-?[0-9]+(?:\.[0-9]+)?)\s*%?\s*,\s*"
                    r"(-?[0-9]+(?:\.[0-9]+)?)\s*%?\s*\])?")


def figure(cell):
    """'61.0 [55.2, 66.8]' as (61.0, 55.2, 66.8); the interval parts None when not written."""
    found = FIGURE.match(cell or "")
    if not found:
        return None, None, None
    return tuple(float(g) if g is not None else None for g in found.groups())


def scoreboard(path):
    """The scoreboard's three tables and its two bars, as written there."""
    board = {"rows": [], "earlier": [], "roles": [], "evals": [], "bars": BAR_DEFAULTS,
             "bars_from": "D-S92's defaults (the scoreboard does not state them)", "note": None}
    if not path.is_file():
        board["note"] = "the scoreboard file was not found"
        return board
    text = path.read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", text)
    above = re.search(r"at least ([0-9.]+) points above B1", flat)
    below = re.search(r"at most ([0-9.]+) points below the cloud reference", flat)
    if above and below:
        board["bars"] = (float(above.group(1)), float(below.group(1)))
        board["bars_from"] = "the scoreboard's own sentences (D-S92)"
    head, rows = named_rows(text, "Row")
    if head is None:
        board["note"] = "the scoreboard is not yet in the D-S102 form (no table headed Row)"
    for row in rows:
        if REFUSED_SETS.search(row.get("Set", "")):
            raise SystemExit("refused: a scoreboard row names a sealed, test or fresh set: %r" % row.get("Set"))
        # A line the scoreboard itself marks pre-standard goes to the earlier table, never on the charts.
        (board["earlier"] if PRE_STANDARD.search(" ".join(row.values())) else board["rows"]).append(row)
    if head is not None and not board["rows"]:
        board["note"] = "the scoreboard holds no standardised measurement yet"
    board["roles"] = named_rows(text, "Role")[1]
    board["evals"] = named_rows(text, "Evaluation")[1]
    return board


def other_published(root):
    """The published-figure table of each other-domain benchmark, as its rules file writes it."""
    path = root / OTHER_RULES
    if not path.is_file():
        return []
    rows = table_rows(path.read_text(encoding="utf-8"), "System")
    return [["PUBHEALTH"] + [_plain(c) for c in r[:6]] for r in rows if len(r) >= 6]


def causal_published(root):
    """The causal plan's published-figure tables (its section 6), each named by the benchmark its lead-in
    line names: listed beside the probe, since none is like for like."""
    path = root / CAUSAL_PLAN
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    start = text.find("## 6.")
    if start < 0:
        return {}
    end = text.find("### 6.1", start)
    lines = text[start:end if end > 0 else len(text)].splitlines()
    out, last_named = {}, None
    for i, line in enumerate(lines):
        named = [b for b in PROBE if b in line and not line.startswith("|")]
        if named:
            last_named = named[0]
        if line.startswith("| Model") and last_named:
            head = _cells(line)
            rows = []
            for row in lines[i + 2:]:
                if not row.startswith("|"):
                    break
                rows.append([_plain(c) for c in _cells(row)])
            out["causal_%s published figures (not like for like)" % last_named] = (head, rows)
    return out


def reference_lines(root):
    """{benchmark: (value in percent, sentence)}: the gate's two from the target table's bold "Comparable
    bar" lines; the others from the row `REFERENCE_ROWS` names, with the record's own statement of why
    it is not like for like."""
    out = {}
    path = root / TARGETS
    if path.is_file():
        text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
        for bench, value, rest in re.findall(r"\*\*Comparable bar, (\w+): ([0-9.]+) (.*?)\*\*", text):
            out[bench] = (round(float(value) * 100, 4) if float(value) <= 1 else float(value),
                          "published comparable bar (D-S73): %s %s" % (value, rest.rstrip(".")))
    for bench, (record, starts, column) in REFERENCE_ROWS.items():
        path = root / record
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if record == CAUSAL_PLAN:
            section = text[text.find("## 6."):]
            section = section[:section.find("### 6.1")] if "### 6.1" in section else section
            begin = section.find(bench)
            block = section[begin:] if begin >= 0 else ""
            unlike = re.search(r"(None of these is like for like:[^.]*)\.", re.sub(r"\s+", " ", section))
        else:
            block = text
            unlike = re.search(r"never a like-for-like comparison \(([^)]*)\)", re.sub(r"\s+", " ", text))
        lines = block.splitlines()
        head = next((_cells(l) for l in lines if l.startswith("| ") and column in _cells(l)), None)
        if head is None:
            continue
        start = next(i for i, l in enumerate(lines) if l.startswith("| ") and _cells(l) == head)
        for row in lines[start + 2:]:
            if not row.startswith("|"):
                break
            cells = dict(zip(head, _cells(row)))
            if all(any(c.startswith(s) for c in list(cells.values())[:2]) for s in starts):
                value, _, _ = figure(cells.get(column, ""))
                if value is None:
                    break
                # the row's words (system, model, setting, source), not its other figures
                described = ", ".join(_plain(c) for h, c in cells.items()
                                      if h != column and c and figure(c)[0] is None)
                out[bench] = (value, "published figure (D-S73), a reference, not like for like: %s; %s %s. %s"
                              % (described, column, cells[column],
                                 _plain(unlike.group(1)) if unlike else "its setting differences are in the table"))
                break
    return out


def registry_roles(root):
    """Every agent of the registry, with its backend and model under the local profile."""
    path = root / REGISTRY
    if not path.is_file():
        return []
    agents = json.loads(path.read_text(encoding="utf-8")).get("agents", {})
    out = []
    for name in sorted(agents):
        spec = agents[name] if isinstance(agents[name], dict) else {}
        local = spec.get("local") if isinstance(spec.get("local"), dict) else {}
        out.append((name, "%s, %s" % (local.get("backend") or spec.get("backend") or NOT_RECORDED,
                                      local.get("model") or spec.get("model") or NOT_RECORDED)))
    return out


def trained_records(root):
    out = []
    for path in sorted((root / STAGES).glob("*_HALF_A_*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        key = TRAINED_SCHEMAS.get(record.get("schema"))
        if key is None:
            continue
        figures = record.get(key) or {}
        selected = record.get("selected")
        out.append({"part": record.get("part"), "attempt": record.get("attempt"), "metric": key,
                    "untrained": figures.get("base"), "selected": selected,
                    "trained": figures.get(selected), "margin": record.get("margin_required"),
                    "passed": record.get("passed_half_a"), "source": path.name})
    return sorted(out, key=lambda r: (str(r["part"]), r["attempt"] or 0))


def openings(root):
    path = root / OPENINGS
    if not path.is_file():
        return []
    return [{"part": c[0], "k": c[1], "alpha": c[2], "attempt": c[3], "written": c[6],
             "result": c[7].split("(")[0].split(":")[0].strip() or "not read yet"}
            for c in table_rows(path.read_text(encoding="utf-8"), "Part") if len(c) >= 8]


def ledger_lines(paths):
    lines = []
    for path in paths:
        if path is None or not Path(path).is_file():
            continue
        for raw in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                lines.append(json.loads(raw))
            except ValueError:
                continue
    return lines


def cost_series(lines):
    """Spent and forecast points, each launch counted once, and the budget lines in order."""
    def once(event):
        seen, out = set(), []
        for r in sorted((r for r in lines if r.get("event") == event), key=lambda r: r.get("time_utc", "")):
            key = (r.get("launch_requested_utc"), r.get("purpose"))
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out
    spend, total = [], 0.0
    for r in once("termination"):
        if r.get("actual_cost") in (None, ""):
            continue
        total += float(r["actual_cost"])
        spend.append({"time": r.get("time_utc", ""), "total": round(total, 4), "purpose": r.get("purpose") or "",
                      "cost": float(r["actual_cost"]), "minutes": r.get("actual_minutes") or NOT_RECORDED,
                      "type": r.get("type") or NOT_RECORDED, "price": r.get("price_usd_per_hour") or NOT_RECORDED,
                      "region": r.get("region") or NOT_RECORDED})
    forecast, ftotal = [], 0.0
    for r in once("launch_intent"):
        if r.get("forecast_usd") in (None, ""):
            continue
        ftotal += float(r["forecast_usd"])
        forecast.append({"time": r.get("time_utc", ""), "total": round(ftotal, 4), "purpose": r.get("purpose") or ""})
    budget = [(float(r["budget_usd"]), float(r.get("hard_stop_usd") or float(r["budget_usd"]) - 1),
               r.get("time_utc", ""))
              for r in sorted((r for r in lines if r.get("event") in ("budget_open", "budget_change")),
                              key=lambda r: r.get("time_utc", ""))]
    return spend, forecast, budget


HIDDEN_FOLDERS = []  # the private inputs' folders (last two parts), set by `build` from its arguments


def _plain(cell):
    """A record's cell as page text: no evidence path, no markup line break, no backticks. A backticked
    path in a private input's folder, an evidence folder or a JSON record is shown as "(record)"."""
    parts = ["/evidence/", r"\.json"] + [re.escape(name + "/") for name in HIDDEN_FOLDERS]
    text = re.sub(r"`[^`]*(?:%s)[^`]*`" % "|".join(parts), "(record)", cell)
    text = text.replace("<br>", " ").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def _evidence(cell):
    """An evidence cell as page text: a path in a private input's folder or an evidence folder, written
    bare or in backticks, is "(record)"."""
    if cell is None:
        return NOT_RECORDED
    text = _plain(cell)
    if any(name + "/" in text for name in HIDDEN_FOLDERS) or "/evidence/" in text or LOCAL_PATH.search(text):
        return "(record)"
    return text


def time_targets(root):
    path = root / TIME_BUDGET
    if not path.is_file():
        return []
    return [{"target": _plain(c[0]), "measured": _plain(c[1])}
            for c in table_rows(path.read_text(encoding="utf-8"), "Target (D-S80)") if len(c) >= 2]


def earlier_results(root):
    path = root / COMPARABILITY
    if not path.is_file():
        return []
    out = []
    for c in table_rows(path.read_text(encoding="utf-8"), "Run (purpose)"):
        if len(c) < 6:
            continue
        out.append({"run": _plain(c[0]), "measured": _plain(c[2]), "integrity": _plain(c[4]), "outcome": _plain(c[5])})
    return out


# ---- charts --------------------------------------------------------------------------------------

def _panel(panels, name, title, traces, layout, caption):
    layout = dict({"title": {"text": title}, "hovermode": "closest", "margin": {"t": 48}}, **layout)
    panels.append({"id": name, "title": title, "traces": traces, "layout": layout, "caption": caption})


def _shown(row, column):
    value = field(row, column)
    return html.escape(_plain(value)) if value is not None else NOT_RECORDED


def bench_points(rows, bench):
    """The standardised lines of one benchmark with a system figure, oldest first, and its one metric."""
    points = sorted((r for r in rows if r.get("Benchmark") == bench and figure(r.get("System (95% CI)"))[0] is not None),
                    key=lambda r: r.get("Time", ""))
    named = {(field(r, "Primary metric (D-S99)"), field(r, "Class setting")) for r in points}
    named.discard((None, None))
    if len(named) > 1:
        raise SystemExit("refused: %s's lines name more than one metric or class setting: %r" % (bench, sorted(named)))
    metric = ", ".join(p for p in next(iter(named)) if p) if named else METRIC.get(bench, NOT_RECORDED)
    return points, metric


def hover_text(row, bench, metric, previous_type):
    machine = field(row, "Machine type")
    change = (NOT_RECORDED if machine is None else "first line of this benchmark" if previous_type is False
              else "same type as the line before" if machine == previous_type
              else "changed from %s" % html.escape(previous_type or NOT_RECORDED))
    return "<br>".join((
        "%s, %s, set %s" % (_shown(row, "Row"), _shown(row, "Time"), _shown(row, "Set")),
        "what changed: %s" % _shown(row, "What changed"),
        "%s, %s, n %s" % (html.escape(bench), html.escape(metric), _shown(row, "n")),
        "system %s; B1 %s; cloud reference %s" % (_shown(row, "System (95% CI)"), _shown(row, "B1 (95% CI)"),
                                                  _shown(row, "Cloud reference (95% CI)")),
        "95 percent intervals by bootstrap over %s" % _shown(row, "Bootstrap unit"),
        "gap to bar (a) / (b): %s" % _shown(row, "Gap to (a) / (b)"),
        "machine %s at %s USD an hour, %s; machine change: %s" % (_shown(row, "Machine type"),
                                                                  _shown(row, "Price (USD/h)"),
                                                                  _shown(row, "Region"), change),
        "%s minutes, %s items an hour" % (_shown(row, "Minutes"), _shown(row, "Speed (items/h)")),
        "run cost %s USD, cumulative %s USD" % (_shown(row, "Run cost (USD)"), _shown(row, "Cumulative cost (USD)")),
        "evidence: %s; factor record: %s" % (html.escape(_evidence(field(row, "Evidence"))), _shown(row, "Factor record")),
        "since last: %s" % _shown(row, "Since last")))


def machine_changes(rows, benches):
    """(benchmark, row, the machine before it or False for the first line) for every standardised line."""
    out = []
    for bench in benches:
        before = False
        for row in bench_points(rows, bench)[0]:
            out.append((bench, row, before))
            before = field(row, "Machine type")
    return out


def bench_charts(board, panels, refs):
    rows = board["rows"]
    bar_a_points, bar_b_points = board["bars"]
    benches = list(BENCHMARKS_IN_USE) + sorted({r.get("Benchmark") for r in rows if r.get("Benchmark")}
                                               - set(BENCHMARKS_IN_USE))
    made = []
    for bench in benches:
        points, metric = bench_points(rows, bench)
        if not points:
            continue
        x = list(range(1, len(points) + 1))
        before = [False] + [field(r, "Machine type") for r in points[:-1]]
        hover = [hover_text(r, bench, metric, b) for r, b in zip(points, before)]
        traces = []
        for column, label in (("System (95% CI)", "Shimmer"), ("B1 (95% CI)", "B1"),
                              ("Cloud reference (95% CI)", "Cloud reference")):
            figs = [figure(r.get(column)) for r in points]
            traces.append({"x": x, "y": [f[0] for f in figs], "name": label, "mode": "lines+markers", "text": hover,
                           "error_y": {"type": "data", "symmetric": False, "visible": True,
                                       "array": [round(f[2] - f[0], 6) if f[2] is not None else None for f in figs],
                                       "arrayminus": [round(f[0] - f[1], 6) if f[1] is not None else None for f in figs]},
                           "hovertemplate": "%{text}<br>" + label + ": %{y}<extra></extra>"})
        gate = bench in BENCHMARKS  # D-S92's two bars hold for the gate's two benchmarks only
        if gate:
            b1 = [figure(r.get("B1 (95% CI)"))[0] for r in points]
            cloud = [figure(r.get("Cloud reference (95% CI)"))[0] for r in points]
            traces += [{"x": x, "y": bar, "name": label, "mode": "lines", "line": {"dash": "dash"},
                        "hoverinfo": "skip"}
                       for bar, label in (([b + bar_a_points if b is not None else None for b in b1],
                                           "Bar (a): B1 + %g" % bar_a_points),
                                          ([c - bar_b_points if c is not None else None for c in cloud],
                                           "Bar (b): cloud reference - %g" % bar_b_points))]
        if bench in refs:
            value, sentence = refs[bench]
            traces.append({"x": [x[0], x[-1]], "y": [value, value],
                           "name": "Published comparable bar (reference)" if gate else "Published figure (reference)",
                           "mode": "lines", "line": {"dash": "dot"}, "text": [sentence, sentence],
                           "hovertemplate": "%{text}<extra></extra>"})
        kind = ("the gate" if gate else "causal probe, %s" % PROBE_LABEL if bench in PROBE
                else "out-of-domain check")
        name = "gate_%s" % bench.lower()
        _panel(panels, name, "%s: %s (%s)" % (bench, kind, metric), traces,
               {"xaxis": {"title": {"text": "Attempt"}, "dtick": 1}, "yaxis": {"title": {"text": "%s (percent)" % metric}}},
               "%s, in %s's own paper's primary metric (D-S99), attempt by attempt on the same items: the whole "
               "system, B1 (the bare model) and the cloud reference model (a reference, never Shimmer), each with "
               "its 95 percent interval (the bootstrap unit is in the hover). Dotted: the published figure, whose "
               "setting differs (hover it). %s"
               % (metric, bench, "Dashed: the two bars; look for the system line crossing both." if gate else
                  "Its bar is B1 (D-S73 item 2); look for the system line above B1's interval."))
        made.append((bench, name))
    return made


def cost_chart(spend, forecast, budget, panels):
    if not spend:
        return None
    xs = list(range(1, len(spend) + 1))
    fx = list(range(1, len(forecast) + 1))
    traces = [{"x": xs, "y": [s["total"] for s in spend], "name": "Spent", "mode": "lines+markers",
               "text": ["%s UTC, %s<br>run cost %.2f USD, %s minutes<br>machine %s at %s USD an hour, %s"
                        % (s["time"][:16].replace("T", " "), s["purpose"], s["cost"], s["minutes"], s["type"],
                           s["price"], s["region"]) for s in spend],
               "hovertemplate": "%{text}<br>cumulative %{y:.2f} USD<extra></extra>"},
              {"x": fx, "y": [f["total"] for f in forecast], "name": "Forecast", "mode": "lines",
               "line": {"dash": "dot"},
               "text": ["%s UTC, %s" % (f["time"][:16].replace("T", " "), f["purpose"]) for f in forecast],
               "hovertemplate": "%{text}<br>cumulative forecast %{y:.2f} USD<extra></extra>"}]
    shapes = []
    if budget:
        shapes = [{"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": v, "y1": v, "line": {"dash": d}}
                  for v, d in ((budget[-1][0], "dash"), (budget[-1][1], "dashdot"))]
    _panel(panels, "cost", "Cloud cost", traces,
           {"xaxis": {"title": {"text": "Run, in order"}, "dtick": 5}, "yaxis": {"title": {"text": "USD"}}, "shapes": shapes},
           "Cumulative spend at each run's end and cumulative forecast at each launch, against the budget "
           "(dashed) and the hard stop (dash-dot) now in force.")
    return "cost"


# ---- the page and the dashboard -----------------------------------------------------------------

INTRO = ("Written by `tools/progress_charts.py` from the project's own records; no figure here is typed by "
         "hand. Figures are labelled development (read while building), held-out development (kept apart from "
         "tuning) or fresh (read once, at the end), and never mixed. No sealed or benchmark test material "
         "appears here. Every figure names its benchmark's own metric and class setting and carries its 95 "
         "percent interval where the record gives one. Charts start at the first standardised measurement; "
         "everything measured before it is in the tables further down, never on the same axes.")
GATE_PENDING = ("No standardised measurement yet (%s). The first one is the starting gap of the whole system "
                "against B1 and the cloud reference on the held-out development items.")
ONTOLOGY = ("No standardised ontology measurement has a machine-readable record yet; its held-out openings are "
            "in the openings table.")
TIME_NOTE = ("No standardised timed measurement yet; the time-focused work starts after the gate. The figures "
             "below were measured on 8 November 2026 from saved runs on the A10, before the measurements were "
             "standardised, so they are a table only.")
OTHER_NOTE = ("PUBHEALTH (an out-of-domain check) and CLadder and Corr2Cause (the causal probe, an indicator, not a "
              "Shimmer benchmark) are measured as the gate's two are: the system, B1 and the cloud reference on the "
              "same items, each with its interval, and the published figure drawn as a labelled reference line, its "
              "source and setting differences in its hover and in the tables below. No comparable published system "
              "exists for them, so their bar is B1 (D-S73 item 2); the gate's two bars do not apply. A benchmark "
              "with no measurement yet is listed as not yet measured.")
ROLES_NOTE = ("Every model-backed role: each agent of the registry and each trained part. Where the scoreboard "
              "has a row, its trained and untrained figures, the margin written before the read, the held-out "
              "value with its interval and the attempt; otherwise the stated reason it is not trained, or that "
              "the scoreboard has no row for it yet.")
TRAINED_NOTE = ("Each trained part's figures on its tuning half, where the candidate was chosen: in-sample, so a "
                "table, never a chart (D-S98 item 5). The held-out value with its interval is in the roles table "
                "above; the openings table gives each opening's result as it was written.")
EVALS_NOTE = ("Every other measured evaluation, with its metric, n and interval as the scoreboard writes them. One "
              "the scoreboard does not yet hold is listed as such.")
THRESHOLDS_NOTE = ("Every threshold a figure here is read against: the gate's bars, each part's margin, the time "
                   "targets (D-S80) and the budget lines.")
FACTORS_NOTE = ("Each standardised line's machine and its D-S82 factor record, with every change of machine "
                "beside the figures it touches.")
SCOREBOARD_EARLIER_NOTE = ("Lines the scoreboard itself marks as direction only (a first signal on a set that is not "
                           "untuned): a table, never on the charts.")
EARLIER_NOTE = ("Development runs measured before the gate set, the scoreboard and the comparability rule. Each "
                "says how it was measured and how the rule counts it; none is plotted.")


def _figure_cell(text):
    return _plain(text) if text else NOT_RECORDED


def roles_table(board, registry, trained, open_rows):
    head = ["Role", "Local backend and model", "Trained", "Attempt", "Metric and setting", "Untrained (95% CI)",
            "Trained (95% CI)", "Margin written", "Held-out value (95% CI)", "Held-out n", "Bootstrap unit",
            "Result", "Evidence", "Reason not trained"]
    backends = dict(registry)
    rows, named = [], set()
    for r in board["roles"]:
        name = field(r, "Role") or NOT_RECORDED
        named.add(name)
        rows.append([name, backends.get(name, "a trained part, not a registry agent")]
                    + [_evidence(field(r, c)) if c == "Evidence" else _figure_cell(field(r, c)) for c in head[2:]])
    parts = sorted({str(t["part"]) for t in trained} | {o["part"] for o in open_rows})
    for name, backend in registry + [(p, "a trained part, not a registry agent") for p in parts]:
        if name not in named:
            named.add(name)
            rows.append([name, backend] + [NOT_RECORDED] * (len(head) - 3)
                        + ["the scoreboard has no row for it yet"])
    return head, rows


def evals_table(board):
    head = [c for c, _ in EVAL_COLUMNS]
    rows, seen = [], set()
    for r in board["evals"]:
        seen.add((field(r, "Evaluation") or "").lower())
        rows.append([_evidence(field(r, c)) if c == "Evidence" else _figure_cell(field(r, c)) for c in head])
    for name in EVALUATIONS_EXPECTED:
        if name.lower() not in seen:
            rows.append([name] + [NOT_RECORDED] * (len(head) - 2) + ["not on the scoreboard yet"])
    return head, rows


def thresholds_table(board, trained, times, budget):
    a, b = board["bars"]
    rows = [["Bar (a), the gate's two benchmarks", "the system at least %g points above B1 in the primary "
             "metric" % a, board["bars_from"]],
            ["Bar (b), the gate's two benchmarks", "the system at most %g points below the cloud reference" % b,
             board["bars_from"]]]
    rows += [["Margin, %s attempt %s" % (t["part"], t["attempt"]), str(t["margin"]), t["source"]] for t in trained]
    rows += [["Margin, %s attempt %s" % (field(r, "Role"), field(r, "Attempt") or NOT_RECORDED),
              _plain(field(r, "Margin written")), "the scoreboard"] for r in board["roles"] if field(r, "Margin written")]
    rows += [["Time target (D-S80)", t["target"], "TIME_BUDGET.md"] for t in times]
    rows += [["Budget line %d" % (i + 1), "budget %.2f USD, hard stop %.2f USD" % (v, h),
              "the budget ledger, %s UTC" % (when[:16].replace("T", " ") or NOT_RECORDED)]
             for i, (v, h, when) in enumerate(budget)]
    return ["Threshold", "Value", "From"], rows


def factors_table(changes):
    rows = []
    for bench, row, before in changes:
        machine = field(row, "Machine type")
        change = (NOT_RECORDED if machine is None else "first line" if before is False
                  else "same" if machine == before else "changed from %s" % (before or NOT_RECORDED))
        rows.append([_figure_cell(field(row, "Row")), _figure_cell(field(row, "Time")), bench,
                     _figure_cell(machine), change, _figure_cell(field(row, "Factor record"))])
    return ["Row", "Time", "Benchmark", "Machine type", "Machine change", "Factor record (D-S82)"], rows


def tables(open_rows, times, earlier, made, board, other_pub, trained, causal, registry, budget):
    out = {
        "roles": roles_table(board, registry, trained, open_rows),
        "trained": (["Part", "Attempt", "Candidate chosen on the tuning half", "Metric", "Trained", "Untrained",
                     "Margin required", "Passed the tuning half", "Record"],
                    [[r["part"], r["attempt"], r["selected"], r["metric"].replace("_", " "),
                      "%.3f" % r["trained"] if r["trained"] is not None else NOT_RECORDED,
                      "%.3f" % r["untrained"] if r["untrained"] is not None else NOT_RECORDED,
                      r["margin"], r["passed"], r["source"]] for r in trained]),
        "other_published": (["Benchmark", "System", "Model (size)", "Setting", "Metric", "Figure", "Source"],
                            other_pub),
        "benchmarks": benchmark_list(made),
        "evaluations": evals_table(board),
        "thresholds": thresholds_table(board, trained, times, budget),
        "factors": factors_table(machine_changes(board["rows"], [b for b, _ in made])),
        "scoreboard_earlier": (["Row", "Time", "What changed", "Set", "Benchmark", "Primary metric (D-S99)",
                                "System (95% CI)", "B1 (95% CI)", "Cloud reference (95% CI)"],
                               [[_figure_cell(field(r, c)) for c in ("Row", "Time", "What changed", "Set", "Benchmark")]
                                + [_figure_cell(", ".join(p for p in (field(r, "Primary metric (D-S99)"),
                                                                      field(r, "Class setting")) if p))]
                                + [_figure_cell(field(r, c)) for c in ("System (95% CI)", "B1 (95% CI)",
                                                                       "Cloud reference (95% CI)")]
                                for r in board["earlier"]]),
        "openings": (["Part", "Opening", "Alpha", "Attempt", "Written", "Result"],
                     [[r[k] for k in ("part", "k", "alpha", "attempt", "written", "result")] for r in open_rows]),
        "time": (["Target", "Measured (8 November, before standardisation)"],
                 [[t["target"], t["measured"]] for t in times]),
        "earlier": (["Run", "What it measured", "Integrity", "How the rule counts it"],
                    [[r[k] for k in ("run", "measured", "integrity", "outcome")] for r in earlier]),
    }
    for key, (head, rows) in causal.items():
        out[key] = (head, rows)
    return out


def _html_table(head, rows):
    cells = "".join("<th>%s</th>" % html.escape(h) for h in head)
    body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % html.escape(str(c)) for c in row) for row in rows)
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (cells, body or
                                                                          "<tr><td colspan=\"%d\">none yet</td></tr>" % len(head))


def benchmark_list(made):
    """Every benchmark in use with its kind, metric and state, so none is left out (D-S98 item 8)."""
    charted = {b for b, _ in made}
    return (["Benchmark", "Kind", "Primary metric (D-S99) and class setting", "State"],
            [[b, "the gate" if b in BENCHMARKS else "causal probe, %s" % PROBE_LABEL if b in PROBE
              else "out-of-domain check", METRIC.get(b, "its paper's primary metric, to be confirmed against the paper"),
              "charted below" if b in charted else "not yet measured"] for b in BENCHMARKS_IN_USE])


def dashboard(panels, made, gate_note, cost_made, tabs):
    gate_ids = {"gate_%s" % b.lower() for b in BENCHMARKS}
    sections = [("Every benchmark in use", [], "", "benchmarks"),
                ("The gate", [p for p in panels if p["id"] in gate_ids],
                 "" if any(b in BENCHMARKS for b, _ in made) else GATE_PENDING % gate_note, None),
                ("Out-of-domain check and causal probe",
                 [p for p in panels if p["id"].startswith("gate_") and p["id"] not in gate_ids],
                 OTHER_NOTE, ["other_published"] + sorted(k for k in tabs if k.startswith("causal_"))),
                ("Model-backed roles", [], ROLES_NOTE, "roles"),
                ("Trained parts", [], TRAINED_NOTE, ["trained", "openings"]),
                ("Other measured evaluations", [], EVALS_NOTE, "evaluations"),
                ("Thresholds", [], THRESHOLDS_NOTE, "thresholds"),
                ("Factor records and machine changes", [], FACTORS_NOTE, "factors"),
                ("The ontology", [], ONTOLOGY, None),
                ("Cost", [p for p in panels if p["id"] == "cost"], "" if cost_made else "No ledger in this checkout.", None),
                ("Time", [], TIME_NOTE, "time"),
                ("Scoreboard lines before standardisation", [], SCOREBOARD_EARLIER_NOTE, "scoreboard_earlier"),
                ("Earlier results, before standardisation", [], EARLIER_NOTE, "earlier")]
    body = []
    for title, ps, note, table in sections:
        body.append("<section><h2>%s</h2>" % html.escape(title))
        if note:
            body.append("<p class=\"note\">%s</p>" % html.escape(note))
        for p in ps:
            body.append("<figure><div id=\"%s\" class=\"chart\"></div><figcaption>%s</figcaption></figure>"
                        % (p["id"], html.escape(p["caption"])))
        for key in ([table] if isinstance(table, str) else table or []):
            if key.startswith("causal_"):
                body.append("<h3>%s</h3>" % html.escape(key[len("causal_"):]))
            body.append(_html_table(*tabs[key]))
        body.append("</section>")
    script = "".join("Plotly.newPlot(%s, %s, %s, {responsive: true});\n"
                     % (json.dumps(p["id"]), json.dumps(p["traces"], sort_keys=True),
                        json.dumps(p["layout"], sort_keys=True)) for p in panels)
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "<title>Shimmer progress</title>\n<script src=\"%s\"></script>\n<style>\n"
            ":root{--fg:#1d1d1b;--bg:#fbfaf7;--muted:#5b5a55;--line:#d9d6cc}\n"
            "@media (prefers-color-scheme: dark){:root{--fg:#ecebe6;--bg:#161615;--muted:#a9a79f;--line:#3a3934}}\n"
            "body{margin:0 auto;max-width:72rem;padding:16px;background:var(--bg);color:var(--fg);"
            "font:16px/1.5 system-ui,sans-serif}\n.chart{width:100%%;height:420px}\n.note{color:var(--muted)}\n"
            "table{border-collapse:collapse;width:100%%;font-size:14px}th,td{border-bottom:1px solid var(--line);"
            "padding:6px;text-align:left;vertical-align:top}\n"
            "section{overflow-x:auto}\n</style></head>\n<body>\n"
            "<h1>Progress: charts of every measured attempt</h1>\n<p>%s</p>\n%s\n<script>\n%s</script>\n</body></html>\n"
            % (PLOTLY, html.escape(INTRO), "\n".join(body), script))


def private_names(paths):
    """What the output must never name of the private inputs: each file's name and, for each file's
    folder and the item-set folder, its last two path parts (read from the arguments, never typed)."""
    names = set()
    for given, is_folder in paths:
        if not given:
            continue
        given = Path(given).resolve()
        folder = given if is_folder else given.parent
        if not is_folder:
            names.add(given.name)
        names.add("/".join(folder.parts[-2:]))
    return sorted(n for n in names if n)


def check_output(out, refused=()):
    for path in sorted(out.rglob("*")):
        if path.suffix in (".md", ".html"):
            text = path.read_text(encoding="utf-8")
            if EM_DASH in text or chr(92) + "u2014" in text:  # literal, or escaped inside the charts' JSON
                raise SystemExit("refused: an em dash in %s" % path.name)
            found = LOCAL_PATH.search(text)
            if found:
                raise SystemExit("refused: a local, private or evidence path in %s: %r" % (path.name, found.group(0)))
            for name in refused:
                if name in text or name.replace("/", chr(92)) in text:
                    raise SystemExit("refused: a private input named in %s: %r" % (path.name, name))


def build(root, out, scoreboard_file, ledger, item_sets, r_ledger=None):
    root, out = Path(root), Path(out)
    refused = private_names([(scoreboard_file, False), (ledger, False), (r_ledger, False), (item_sets, True)])
    HIDDEN_FOLDERS[:] = [name for name in refused if "/" in name]
    out.mkdir(parents=True, exist_ok=True)
    panels = []
    board = scoreboard(Path(scoreboard_file))
    made = bench_charts(board, panels, reference_lines(root))
    trained = trained_records(root)
    spend, forecast, budget = cost_series(ledger_lines([Path(ledger), r_ledger]))
    cost_made = cost_chart(spend, forecast, budget, panels)
    times = time_targets(root)
    tabs = tables(openings(root), times, earlier_results(root), made, board, other_published(root), trained,
                  causal_published(root), registry_roles(root), budget)
    (out / "index.html").write_text(dashboard(panels, made, board["note"], cost_made, tabs),
                                    encoding="utf-8", newline="\n")
    check_output(out, refused)
    return {"bench_charts": len(made), "trained_rows": len(trained), "cost_runs": len(spend),
            "roles": len(tabs["roles"][1]), "evaluations": len(tabs["evaluations"][1])}


# ---- the script's own proofs ----------------------------------------------------------------------

def _traces(page, panel_id):
    line = page[page.index("Plotly.newPlot(%s, " % json.dumps(panel_id)):]
    line = line[:line.index("\n")]
    return json.JSONDecoder().raw_decode(line[len("Plotly.newPlot(%s, " % json.dumps(panel_id)):])[0]


def _board_line(**cells):
    return "| %s |" % " | ".join(cells.get(c, "") for c, _ in BENCH_COLUMNS)


def self_test():
    """Runs `build` on records written here, in a temporary folder."""
    import tempfile
    results = []
    names = [c for c, _ in BENCH_COLUMNS]
    head = "| %s |\n|%s\n" % (" | ".join(names), "---|" * len(names))
    preamble = ("(a) the system at least 10 points above B1; (b) the system at most 5 points below the cloud "
                "reference.\n\n")
    common = {"Set": "held-out quick", "n": "60", "Bootstrap unit": "items", "Machine type": "gpu_1x_a10",
              "Price (USD/h)": "0.75", "Region": "us-east-1", "Minutes": "42", "Speed (items/h)": "85.7",
              "Run cost (USD)": "0.53", "Cumulative cost (USD)": "158.32", "Evidence": "dev-first-signal run folder",
              "Factor record": "F-0001", "Since last": "first line"}
    first = dict(common, Row="A1", Time="2026-11-10 09:00", **{"What changed": "the first signal",
                 "Benchmark": "ContraDoc", "Primary metric (D-S99)": "binary judgment accuracy",
                 "Class setting": "2 classes", "System (95% CI)": "61.0 [48.3, 73.3]", "B1 (95% CI)": "55.0 [41.7, 66.7]",
                 "Cloud reference (95% CI)": "70.0 [58.3, 81.7]", "Gap to (a) / (b)": "4.0 / 4.0"})
    second = dict(first, Row="A2", Time="2026-11-10 12:00", **{"What changed": "the judge calibrated",
                  "System (95% CI)": "64.0 [51.7, 76.7]", "Machine type": "gpu_1x_h100_pcie", "Price (USD/h)": "2.49",
                  "Factor record": "F-0002", "Since last": "system +3.0"})
    scitab = dict(first, Benchmark="SciTab", **{"Primary metric (D-S99)": "macro-F1", "Class setting": "3 classes",
                  "Bootstrap unit": "tables", "n": "47", "System (95% CI)": "50.0 [38.1, 61.2]",
                  "B1 (95% CI)": "48.0 [36.0, 60.0]", "Cloud reference (95% CI)": "66.0 [54.0, 77.0]"})
    probe = dict(first, Benchmark="CLadder", **{"Primary metric (D-S99)": "accuracy over yes and no answers",
                 "Gap to (a) / (b)": "", "System (95% CI)": "52.0 [47.0, 57.0]", "B1 (95% CI)": "50.0 [45.0, 55.0]",
                 "Cloud reference (95% CI)": "63.0 [58.0, 68.0]"})
    early = dict(first, Row="A0", Time="2026-11-09 18:00", **{"What changed": "direction only, not a gate figure",
                 "Set": "interim"})
    roles = ("\n| Role | Trained | Attempt | Metric and setting | Untrained (95% CI) | Trained (95% CI) | Margin written "
             "| Held-out value (95% CI) | Held-out n | Bootstrap unit | Result | Evidence | Reason not trained |\n"
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
             "| JUDGE | yes | 2 | macro-F1, 3 classes | 70.3 [61.0, 79.0] | 79.7 [71.0, 87.0] | 5 points | "
             "66.1 [55.0, 76.0] | 120 | tables | fail | the read record | |\n"
             "| REDACTOR | no | | | | | | | | | | | rules only, no labelled spans to train on |\n")
    evals = ("\n| Evaluation | Time | Set | Metric and setting | n | Bootstrap unit | Value (95% CI) | Evidence | "
             "Factor record | State |\n|---|---|---|---|---|---|---|---|---|---|\n"
             "| Flag precision | 2026-11-10 10:00 | development cases | precision of flags, 2 classes | 40 | items | "
             "82.5 [70.0, 92.5] | the cases record | F-0003 | done (the cases record) |\n")
    target = ("**Comparable bar, ContraDoc: 0.681 binary judgment accuracy.** Source: a planted line.\n")
    causal = ("## 6. Published figures\n\nNone of these is like for like: the prompts differ.\n\nCLadder v1, in "
              "percent:\n\n| Model (label per D-S73) | Overall | Rung 1 |\n|---|---|---|\n"
              "| Random | 49.27 | 50.28 |\n| LLaMa (open model) | 45.22 | 63.33 |\n\n### 6.1 Search\n")
    registry = {"agents": {"JUDGE": {"model": "m-judge", "backend": "local_auditor"},
                           "REDACTOR": {"model": "m-red", "backend": "qwen_local"},
                           "VERIFIER": {"model": "m-cloud", "backend": "openai_api",
                                        "local": {"backend": "local_auditor", "model": "m-local"}}}}
    with tempfile.TemporaryDirectory(prefix="progress_selftest_") as td:
        root = Path(td) / "root"
        board_file = Path(td) / "kept" / "board.md"
        ledger_file = Path(td) / "kept" / "ledger.jsonl"
        item_sets = Path(td) / "sets" / "items"
        board_file.parent.mkdir(parents=True)
        for rel, text in ((TARGETS, target), (CAUSAL_PLAN, causal), (REGISTRY, json.dumps(registry))):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        planted = {"schema": "auditor-rule-check-half-a-v1", "part": "planted_part", "attempt": 1,
                   "selected": "planted_candidate", "half_a_macro_f1": {"base": 0.5, "planted_candidate": 0.6},
                   "margin_required": 0.05, "passed_half_a": True}
        (root / STAGES / "PLANTED_HALF_A_1.json").write_text(json.dumps(planted), encoding="utf-8")
        lines = [first, second, scitab, probe, early]

        def write(rows, extra=roles + evals):
            board_file.write_text(preamble + head + "\n".join(_board_line(**r) for r in rows) + "\n" + extra,
                                  encoding="utf-8")

        def run(name):
            summary = build(root, Path(td) / name, board_file, ledger_file, item_sets)
            return summary, (Path(td) / name / "index.html").read_text(encoding="utf-8")

        write(lines)
        summary, page_a = run("a")
        results.append(("each benchmark with a standardised line charted", summary["bench_charts"] == 3))
        traces = _traces(page_a, "gate_contradoc")
        system = traces[0]
        hover_ok = all(html.escape(row[c]) in text for row, text in zip((first, second), system["text"])
                       for c in HOVER_FIELDS if row.get(c))
        results.append(("every hover holds the scoreboard's cells for its line", hover_ok and len(system["text"]) == 2))
        results.append(("each arm drawn with its interval",
                        [t["name"] for t in traces[:3]] == ["Shimmer", "B1", "Cloud reference"]
                        and system["error_y"]["array"] == [12.3, 12.7] and system["error_y"]["arrayminus"] == [12.7, 12.3]))
        results.append(("the machine change named in the hover and the factors table",
                        "changed from gpu_1x_a10" in system["text"][1] and "changed from gpu_1x_a10" in page_a))
        results.append(("the gate's bars read from the scoreboard's sentences",
                        any(t["name"] == "Bar (a): B1 + 10" for t in traces)
                        and "the scoreboard&#x27;s own sentences (D-S92)" in page_a))
        results.append(("the published bar drawn", any(t["name"] == "Published comparable bar (reference)" for t in traces)))
        probe_traces = _traces(page_a, "gate_cladder")
        results.append(("the probe: four series, its published figure read from the plan, no gate bars, labelled",
                        [t["name"] for t in probe_traces] == ["Shimmer", "B1", "Cloud reference",
                                                              "Published figure (reference)"]
                        and probe_traces[3]["y"] == [45.22, 45.22] and "the prompts differ" in probe_traces[3]["text"][0]
                        and PROBE_LABEL in page_a))
        results.append(("the bootstrap unit stated per line", "bootstrap over tables" in
                        _traces(page_a, "gate_scitab")[0]["text"][0]))
        results.append(("the direction-only line in the table, not the chart",
                        "direction only, not a gate figure" in page_a and "A0" not in json.dumps(system)))
        results.append(("every registry role and trained part has a row, held-out values as values",
                        all(n in page_a for n in ("VERIFIER", "local_auditor, m-local", "planted_part",
                                                  "66.1 [55.0, 76.0]", "rules only, no labelled spans to train on"))
                        and summary["roles"] == 4))
        results.append(("every evaluation D-S102 names listed, the held one with its figure",
                        "82.5 [70.0, 92.5]" in page_a and summary["evaluations"] == len(EVALUATIONS_EXPECTED)
                        and page_a.count("not on the scoreboard yet") == len(EVALUATIONS_EXPECTED) - 1))
        results.append(("the thresholds: bars, margins and the part margin from the scoreboard",
                        "Margin, JUDGE attempt 2" in page_a and "Margin, planted_part attempt 1" in page_a))
        results.append(("no bare accuracy in the page", not re.search(
            r"(?<!judgment )accuracy(?! over yes and no)", re.sub(r"<script>.*", "", page_a, flags=re.S))))
        results.append(("a trained part's in-sample figures in the table, never a chart",
                        "planted_candidate" in page_a and "0.600" in page_a and 'Plotly.newPlot("trained_' not in page_a))
        results.append(("two builds identical", page_a == run("b")[1]))
        write(lines + [dict(first, Benchmark="NewBench")])
        summary, page_e = run("e")
        results.append(("a benchmark added on the scoreboard is charted, with no gate bars",
                        summary["bench_charts"] == 4 and not any(t["name"].startswith("Bar")
                                                                 for t in _traces(page_e, "gate_newbench"))))
        write([first, dict(second, **{"Class setting": "3 classes"})])
        try:
            run("m")
            results.append(("two metrics on one benchmark refused", False))
        except SystemExit:
            results.append(("two metrics on one benchmark refused", True))
        write([dict(first, Set="sealed test")])
        try:
            run("c")
            results.append(("a sealed set refused", False))
        except SystemExit:
            results.append(("a sealed set refused", True))
        for planted_text, what in ((chr(0x2014), "an em dash"), ("C:" + chr(92) + "Users" + chr(92) + "x", "a local path"),
                                   ("see sets/items/x", "the item-set folder"),
                                   ("see " + board_file.name, "the scoreboard's name")):
            write([dict(first, **{"What changed": planted_text})])
            try:
                run("d")
                results.append(("%s refused at the output" % what, False))
            except SystemExit:
                results.append(("%s refused at the output" % what, True))
        write([dict(first, Evidence=str(item_sets / "run" / "result.json"))])
        results.append(("an evidence path in a private folder shown as (record)",
                        "evidence: (record)" in _traces(run("f")[1], "gate_contradoc")[0]["text"][0]))
        board_file.write_text(preamble + "| Time | What changed | Set |\n|---|---|---|\n", encoding="utf-8")
        results.append(("an earlier-form scoreboard says so", "not yet in the D-S102 form" in run("g")[1]))
    for what, ok in results:
        print("%s %s" % ("PASS" if ok else "FAIL", what))
    return 0 if all(ok for _, ok in results) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write the public progress page from the records (D-S98, D-S102).")
    parser.add_argument("--root", help="the checkout that holds the records (the loop worktree)")
    parser.add_argument("--out", help="the folder the page is written to, docs/progress")
    parser.add_argument("--self-test", action="store_true", help="run the script's own proofs on planted records")
    parser.add_argument("--print-schema", action="store_true", help="print the scoreboard tables this script reads")
    parser.add_argument("--scoreboard", help="the private scoreboard file (required, no default)")
    parser.add_argument("--ledger", help="the budget ledger (required, no default)")
    parser.add_argument("--item-sets", help="the item-set folder, refused in the output (required, no default)")
    parser.add_argument("--r-ledger", default=None, help="role R's ledger, when it exists")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.print_schema:
        print(schema_text())
        return 0
    missing = [flag for flag, value in (("--root", args.root), ("--out", args.out), ("--scoreboard", args.scoreboard),
                                        ("--ledger", args.ledger), ("--item-sets", args.item_sets)) if not value]
    if missing:
        parser.error("required: %s" % ", ".join(missing))
    print(json.dumps(build(args.root, args.out, args.scoreboard, args.ledger, args.item_sets, args.r_ledger),
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
