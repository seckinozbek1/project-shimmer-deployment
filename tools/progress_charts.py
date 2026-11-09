"""The public progress page (D-S98): charts and tables of every measured attempt, from records only.

    py -3.12 -X utf8 tools/progress_charts.py --root <the loop worktree> --out docs/progress

`--root` is the checkout that holds the committed records (the loop worktree); `--private-root` the one
that holds the gitignored private records (`docs/loop/private/`, the main checkout; default `--root`);
`--out` is the folder the page is written to (`docs/progress/` of the branch that is pushed). Nothing is typed by hand: every figure comes
from one of these records under `--root`, and a record that is missing leaves its section saying so.

- The gate (D-S92, D-S94): `docs/loop/private/GATE_SCOREBOARD.md`, its table rows, newest first. Per
  benchmark, the system, B1 and the cloud reference over attempts, with the two bars as dashed lines
  (B1 + 10 points, the cloud reference - 5 points). A row on a sealed, test or fresh set is refused here:
  the fresh set appears only after its single read, through its own record.
- The trained parts: committed read records `docs/loop/stages/*_HALF_A_*.json` of a schema this script
  declares (`TRAINED_SCHEMAS`), against the untrained form and the written margin, labelled in-sample
  (the tuning half chose the candidate); held-out openings, pass or fail only, from
  `docs/loop/HELDOUT_OPENINGS.md`, in a table.
- Cost: every ledger with launch lines (`docs/loop/private/budget_ledger.jsonl`, and role R's ledger when
  `--r-ledger` names it): cumulative actual spend at each run's end against the budget and the hard stop
  now in force, and the cumulative forecast at each launch. A launch is counted once across ledgers.
- Time: `docs/loop/stages/TIME_BUDGET.md`'s targets table, measured before the measurements were
  standardised, so a table only (D-S98 item 5).
- Earlier results: `docs/loop/stages/REPORT_COMPARABILITY.md`'s inventory, a table only.

Charts hold standardised measurements only and start at the first one (D-S98 item 5); everything earlier
is in a labelled table, never on the same axes. The page is one file, `index.html`, the interactive
dashboard (D-S98 items 6 and 7: every chart and table on one page, HTML only, no PNG and no Markdown
fallback; Plotly, one pinned version from its CDN), served by GitHub Pages from `docs/`. Hovering a point
shows what the records hold for it and says "not recorded" for the rest. The output carries no local path, no evidence path and no em dash, and
`check_output` refuses to leave it otherwise. Two runs on the same records write the same files.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

PLOTLY = "https://cdn.plot.ly/plotly-2.35.2.min.js"
SCOREBOARD = Path("docs/loop/private/GATE_SCOREBOARD.md")
LEDGER = Path("docs/loop/private/budget_ledger.jsonl")
OPENINGS = Path("docs/loop/HELDOUT_OPENINGS.md")
TIME_BUDGET = Path("docs/loop/stages/TIME_BUDGET.md")
COMPARABILITY = Path("docs/loop/stages/REPORT_COMPARABILITY.md")
STAGES = Path("docs/loop/stages")
TRAINED_SCHEMAS = {"auditor-rule-check-half-a-v1": "half_a_macro_f1"}
BENCHMARKS = ("ContraDoc", "SciTab")  # the gate's two, on the scoreboard
# Every benchmark in use (D-S98 item 8); one not yet measured is listed as such, never left out.
BENCHMARKS_IN_USE = ("ContraDoc", "SciTab", "PUBHEALTH", "CLadder", "Corr2Cause")
# Each benchmark's own paper's primary metric (D-S99); the bars are read in it.
METRIC = {"ContraDoc": "binary judgment accuracy", "SciTab": "macro-F1"}
TARGETS = Path("docs/loop/stages/targets/TARGET_TABLE.md")
PRE_STANDARD = re.compile(r"direction only|pre-standard|not a gate figure", re.I)
BAR_ABOVE_B1, BAR_BELOW_CLOUD = 10.0, 5.0  # D-S92's defaults, as the scoreboard states them
REFUSED_SETS = re.compile(r"seal|test|fresh", re.I)
LOCAL_PATH = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/](?!/)|/Users/|/home/|\\Users\\|external/s05|docs/loop/private")
EM_DASH = chr(0x2014)
NOT_RECORDED = "not recorded"


# ---- reading the records -------------------------------------------------------------------------

def table_rows(text, first_header):
    """The rows of the first Markdown table whose header starts with `first_header`, as cell lists."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("| " + first_header):
            rows = []
            for row in lines[i + 2:]:
                if not row.startswith("|"):
                    break
                rows.append([c.strip() for c in row.strip().strip("|").split("|")])
            return rows
    return []


def _numbers(cell):
    """'61.0 / 50.5 / 70' (percent signs allowed) as three floats, None where a part is not a number."""
    out = []
    for part in cell.split("/"):
        try:
            out.append(float(part.strip().rstrip("%")))
        except ValueError:
            out.append(None)
    return (out + [None, None, None])[:3]


def gate_rows(root):
    path = root / SCOREBOARD
    if not path.is_file():
        return [], [], "the scoreboard is not in this checkout"
    out, earlier = [], []
    for cells in reversed(table_rows(path.read_text(encoding="utf-8"), "Time")):  # newest first in the file
        if len(cells) < 8 or cells[0].startswith("("):
            continue
        if REFUSED_SETS.search(cells[2]):
            raise SystemExit("refused: a scoreboard row names a sealed, test or fresh set: %r" % cells[2])
        row = {"time": cells[0], "changed": cells[1], "set": cells[2] or NOT_RECORDED}
        for name, cell in (("ContraDoc", cells[3]), ("SciTab", cells[5])):
            system, b1, cloud = _numbers(cell)
            row[name] = {"system": system, "b1": b1, "cloud": cloud, "cell": cell}
        # A row the scoreboard itself marks pre-standard (a first signal on a set that is not untuned)
        # goes to the earlier table, never on the charts (D-S98 item 5).
        (earlier if PRE_STANDARD.search(" ".join(cells)) else out).append(row)
    return out, earlier, None if out else "the scoreboard holds no standardised measurement yet"


def published_bars(root):
    """{benchmark: (value in percent, sentence)} from the target table's bold "Comparable bar" lines."""
    path = root / TARGETS
    if not path.is_file():
        return {}
    text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
    out = {}
    for bench, value, rest in re.findall(r"\*\*Comparable bar, (\w+): ([0-9.]+) (.*?)\*\*", text):
        out[bench] = (float(value) * 100 if float(value) <= 1 else float(value),
                      "published comparable bar (D-S73): %s %s" % (value, rest.rstrip(".")))
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
    budget = [(float(r["budget_usd"]), float(r.get("hard_stop_usd") or float(r["budget_usd"]) - 1))
              for r in sorted((r for r in lines if r.get("event") in ("budget_open", "budget_change")),
                              key=lambda r: r.get("time_utc", ""))]
    return spend, forecast, budget


def _plain(cell):
    """A record's cell as page text: no evidence path, no markup line break, no backticks."""
    text = re.sub(r"`[^`]*(?:external/|/evidence/|private/|\.json)[^`]*`", "(record)", cell)
    text = text.replace("<br>", " ").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


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


def gate_charts(rows, panels, bars):
    made = []
    for bench in BENCHMARKS:
        points = [(i + 1, r) for i, r in enumerate(rows) if r[bench]["system"] is not None]
        if not points:
            continue
        x = [i for i, _ in points]
        series = {k: [r[bench][k] for _, r in points] for k in ("system", "b1", "cloud")}
        bar_a = [b + BAR_ABOVE_B1 if b is not None else None for b in series["b1"]]
        bar_b = [c - BAR_BELOW_CLOUD if c is not None else None for c in series["cloud"]]
        name = "gate_%s" % bench.lower()
        hover = ["%s, attempt %d, set %s<br>what changed: %s<br>as the scoreboard writes it (system / B1 / cloud "
                 "reference): %s<br>bars: (a) %s, (b) %s<br>run time, machine and evidence: %s on the scoreboard"
                 % (r["time"], i, r["set"], r["changed"], r[bench]["cell"], a, b, NOT_RECORDED)
                 for (i, r), a, b in zip(points, bar_a, bar_b)]
        traces = [{"x": x, "y": series[k], "name": label, "mode": "lines+markers", "text": hover,
                   "hovertemplate": "%{text}<br>" + label + ": %{y}<extra></extra>"}
                  for k, label in (("system", "Shimmer"), ("b1", "B1"), ("cloud", "Cloud reference"))]
        traces += [{"x": x, "y": bar, "name": label, "mode": "lines", "line": {"dash": "dash"}, "hoverinfo": "skip"}
                   for bar, label in ((bar_a, "Bar (a): B1 + %g" % BAR_ABOVE_B1),
                                      (bar_b, "Bar (b): cloud reference - %g" % BAR_BELOW_CLOUD))]
        if bench in bars:
            value, sentence = bars[bench]
            traces.append({"x": [x[0], x[-1]], "y": [value, value], "name": "Published comparable bar (reference)",
                           "mode": "lines", "line": {"dash": "dot"}, "text": [sentence, sentence],
                           "hovertemplate": "%{text}<extra></extra>"})
        metric = METRIC[bench]
        _panel(panels, name, "%s: the gate (%s)" % (bench, metric), traces,
               {"xaxis": {"title": {"text": "Attempt"}, "dtick": 1}, "yaxis": {"title": {"text": "%s (percent)" % metric}}},
               "%s, in %s's own paper's primary metric (D-S99), on the held-out development items, attempt by "
               "attempt: the whole system, B1 (the bare model) and the cloud reference model (a reference, never "
               "Shimmer). Dashed: the two bars; dotted: the published comparable figure, whose setting differs "
               "(hover it). Look for the system line crossing both dashed bars." % (metric, bench))
        made.append((bench, name))
    return made


def trained_charts(records, panels):
    made = []
    for part in sorted({r["part"] for r in records}):
        rs = [r for r in records if r["part"] == part]
        x = [r["attempt"] for r in rs]
        label_metric = rs[0]["metric"].replace("_", " ")
        name = "trained_%s" % part
        hover = ["attempt %s, candidate %s<br>passed the tuning half: %s<br>record %s<br>date, item count, machine: "
                 "%s in this record" % (r["attempt"], r["selected"], r["passed"], r["source"], NOT_RECORDED) for r in rs]
        traces = [{"x": x, "y": [r[k] for r in rs], "name": label, "mode": "lines+markers", "text": hover,
                   "hovertemplate": "%{text}<br>" + label + ": %{y:.3f}<extra></extra>"}
                  for k, label in (("trained", "Trained candidate"), ("untrained", "Untrained form"))]
        traces.append({"x": x, "y": [r["untrained"] + r["margin"] for r in rs], "name": "Untrained + margin",
                       "mode": "lines", "line": {"dash": "dash"}, "hoverinfo": "skip"})
        _panel(panels, name, "%s: tuning half (in-sample)" % part.replace("_", " "), traces,
               {"xaxis": {"title": {"text": "Attempt"}, "dtick": 1}, "yaxis": {"title": {"text": label_metric}}},
               "The trained candidate against its untrained form on the tuning half, where it was chosen, "
               "so these figures are in-sample. The held-out result is pass or fail only, in the openings table.")
        made.append((part, name))
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
         "appears here. Charts start at the first standardised measurement; everything measured before it is "
         "in the tables further down, never on the same axes.")
GATE_PENDING = ("No standardised measurement yet (%s). The first one is the starting gap of the whole system "
                "against B1 and the cloud reference on the held-out development items.")
ONTOLOGY = ("No standardised ontology measurement has a machine-readable record yet; its held-out openings are "
            "in the openings table.")
TIME_NOTE = ("No standardised timed measurement yet; the time-focused work starts after the gate. The figures "
             "below were measured on 8 November 2026 from saved runs on the A10, before the measurements were "
             "standardised, so they are a table only.")
SCOREBOARD_EARLIER_NOTE = ("Rows the scoreboard itself marks as direction only (a first signal on a set that is not "
                           "untuned): a table, never on the charts.")
EARLIER_NOTE = ("Development runs measured before the gate set, the scoreboard and the comparability rule. Each "
                "says how it was measured and how the rule counts it; none is plotted.")


def _cell(text):
    return str(text).replace("|", "/").replace("\n", " ")


def tables(open_rows, times, earlier, gate_made, scoreboard_earlier):
    return {
        "benchmarks": benchmark_list(gate_made),
        "scoreboard_earlier": (["Time", "What changed", "Set", "ContraDoc (system / B1 / cloud reference)",
                                "SciTab (system / B1 / cloud reference)"],
                               [[r["time"], r["changed"], r["set"], r["ContraDoc"]["cell"], r["SciTab"]["cell"]]
                                for r in scoreboard_earlier]),
        "openings": (["Part", "Opening", "Alpha", "Attempt", "Written", "Result"],
                     [[r[k] for k in ("part", "k", "alpha", "attempt", "written", "result")] for r in open_rows]),
        "time": (["Target", "Measured (8 November, before standardisation)"],
                 [[t["target"], t["measured"]] for t in times]),
        "earlier": (["Run", "What it measured", "Integrity", "How the rule counts it"],
                    [[r[k] for k in ("run", "measured", "integrity", "outcome")] for r in earlier]),
    }


def _html_table(head, rows):
    cells = "".join("<th>%s</th>" % html.escape(h) for h in head)
    body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % html.escape(str(c)) for c in row) for row in rows)
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (cells, body or
                                                                          "<tr><td colspan=\"%d\">none yet</td></tr>" % len(head))


def benchmark_list(gate_made):
    """Every benchmark in use with its state, so none is left out (D-S98 item 8)."""
    made = {b for b, _ in gate_made}
    return (["Benchmark", "Primary metric (D-S99)", "State"],
            [[b, METRIC.get(b, "its paper's primary metric, to be confirmed against the paper"),
              "charted below" if b in made else "not yet measured"] for b in BENCHMARKS_IN_USE])


def dashboard(panels, gate_made, gate_note, trained_made, cost_made, tabs):
    sections = [("Every benchmark in use", [], "", "benchmarks"),
                ("The gate", [p for p in panels if p["id"].startswith("gate_")],
                 "" if gate_made else GATE_PENDING % gate_note, None),
                ("Trained parts", [p for p in panels if p["id"].startswith("trained_")],
                 "" if trained_made else "No trained part has a read record yet.", "openings"),
                ("The ontology", [], ONTOLOGY, None),
                ("Cost", [p for p in panels if p["id"] == "cost"], "" if cost_made else "No ledger in this checkout.", None),
                ("Time", [], TIME_NOTE, "time"),
                ("Scoreboard rows before standardisation", [], SCOREBOARD_EARLIER_NOTE, "scoreboard_earlier"),
                ("Earlier results, before standardisation", [], EARLIER_NOTE, "earlier")]
    body = []
    for title, ps, note, table in sections:
        body.append("<section><h2>%s</h2>" % html.escape(title))
        if note:
            body.append("<p class=\"note\">%s</p>" % html.escape(note))
        for p in ps:
            body.append("<figure><div id=\"%s\" class=\"chart\"></div><figcaption>%s</figcaption></figure>"
                        % (p["id"], html.escape(p["caption"])))
        if table:
            body.append(_html_table(*tabs[table]))
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
            "padding:6px;text-align:left;vertical-align:top}\n</style></head>\n<body>\n"
            "<h1>Progress: charts of every measured attempt</h1>\n<p>%s</p>\n%s\n<script>\n%s</script>\n</body></html>\n"
            % (PLOTLY, html.escape(INTRO), "\n".join(body), script))


def check_output(out):
    for path in sorted(out.rglob("*")):
        if path.suffix in (".md", ".html"):
            text = path.read_text(encoding="utf-8")
            if EM_DASH in text or chr(92) + "u2014" in text:  # literal, or escaped inside the charts' JSON
                raise SystemExit("refused: an em dash in %s" % path.name)
            found = LOCAL_PATH.search(text)
            if found:
                raise SystemExit("refused: a local, private or evidence path in %s: %r" % (path.name, found.group(0)))


def build(root, out, private_root=None, r_ledger=None):
    root, out = Path(root), Path(out)
    private_root = Path(private_root) if private_root else root
    out.mkdir(parents=True, exist_ok=True)
    panels = []
    rows, scoreboard_earlier, note = gate_rows(private_root)
    gate_made = gate_charts(rows, panels, published_bars(root))
    trained_made = trained_charts(trained_records(root), panels)
    spend, forecast, budget = cost_series(ledger_lines([private_root / LEDGER, r_ledger]))
    cost_made = cost_chart(spend, forecast, budget, panels)
    tabs = tables(openings(root), time_targets(root), earlier_results(root), gate_made, scoreboard_earlier)
    (out / "index.html").write_text(dashboard(panels, gate_made, note, trained_made, cost_made, tabs),
                                    encoding="utf-8", newline="\n")
    check_output(out)
    return {"gate_charts": len(gate_made), "trained_charts": len(trained_made), "cost_runs": len(spend)}


def self_test():
    """Runs `build` on records written here, in a temporary folder: a standardised row is charted with its
    bars and the published bar, a row marked direction only goes to the table, a sealed set is refused,
    an em dash or a local path in a record is refused at the output, and two builds are identical."""
    import tempfile
    results = []
    board = ("| Time | What changed | Set | ContraDoc: system / B1 / cloud ref | gap to (a) / (b) | "
             "SciTab: system / B1 / cloud ref | gap to (a) / (b) | Since last |\n|---|---|---|---|---|---|---|---|\n%s")
    standard = "| 2026-11-10 09:00 | the first signal | held-out quick | 61.0 / 55.0 / 70.0 | | 50.0 / 48.0 / 66.0 | | |\n"
    early = "| 2026-11-09 18:00 | direction only, not a gate figure | interim | 58.0 / 55.0 / 68.0 | | 47.0 / 48.0 / 65.0 | | |\n"
    target = "**Comparable bar, ContraDoc: 0.681 document-level accuracy.** Source: a planted line.\n"
    with tempfile.TemporaryDirectory(prefix="progress_selftest_") as td:
        root = Path(td) / "root"
        (root / SCOREBOARD).parent.mkdir(parents=True)
        (root / TARGETS).parent.mkdir(parents=True)
        (root / TARGETS).write_text(target, encoding="utf-8")
        (root / SCOREBOARD).write_text(board % (standard + early), encoding="utf-8")
        summary = build(root, Path(td) / "a")
        page_a = (Path(td) / "a" / "index.html").read_text(encoding="utf-8")
        build(root, Path(td) / "b")
        results.append(("one standardised row charted per benchmark", summary["gate_charts"] == 2))
        results.append(("the published bar drawn", "Published comparable bar" in page_a))
        results.append(("the direction-only row in the table, not the chart",
                        "direction only, not a gate figure" in page_a and page_a.count('"x": [1]') >= 2))
        results.append(("two builds identical", page_a == (Path(td) / "b" / "index.html").read_text(encoding="utf-8")))
        (root / SCOREBOARD).write_text(board % standard.replace("held-out quick", "sealed test"), encoding="utf-8")
        try:
            build(root, Path(td) / "c")
            results.append(("a sealed set refused", False))
        except SystemExit:
            results.append(("a sealed set refused", True))
        for planted, what in ((chr(0x2014), "an em dash"), ("C:" + chr(92) + "Users" + chr(92) + "x", "a local path")):
            (root / SCOREBOARD).write_text(board % standard.replace("the first signal", planted), encoding="utf-8")
            try:
                build(root, Path(td) / "d")
                results.append(("%s refused at the output" % what, False))
            except SystemExit:
                results.append(("%s refused at the output" % what, True))
    for what, ok in results:
        print("%s %s" % ("PASS" if ok else "FAIL", what))
    return 0 if all(ok for _, ok in results) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write the public progress page from the records (D-S98).")
    parser.add_argument("--root", help="the checkout that holds the records (the loop worktree)")
    parser.add_argument("--out", help="the folder the page is written to, docs/progress")
    parser.add_argument("--self-test", action="store_true", help="run the script's own proofs on planted records")
    parser.add_argument("--private-root", default=None,
                        help="the checkout that holds docs/loop/private (the main checkout); default --root")
    parser.add_argument("--r-ledger", default=None, help="role R's ledger, when it exists")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not (args.root and args.out):
        parser.error("--root and --out are required")
    print(json.dumps(build(args.root, args.out, args.private_root, args.r_ledger), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
