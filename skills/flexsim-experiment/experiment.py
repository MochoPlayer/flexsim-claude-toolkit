"""Run scenarios x replications of a FlexSim model with no GUI and write the results to CSV and Excel.

Usage:
  python -I -X utf8 experiment.py <model.fsm> <scenarios.json> --out <dir> [--seeds 1-10] [--hours 8]
                                  [--jobs 6] [--timeout 300] [--script my_rep.fs] [--kpi REGEX]

scenarios.json:
  {
    "hours": 8, "seeds": "1-10",                          optional defaults for --hours and --seeds
    "scenarios": {
      "base": {},
      "faster": {"Processor1/cycletime": 20},             object variable (number)
      "busy":   {"Source1/interarrivaltime": "exponential(0, 26, 1)"},   text = FlexScript code field
      "shift2": {"Processor1.Shift": 2},                  object label
      "table":  {"table:Params[2][1]": 5}                 global table cell [row][col]
    }
  }

Each run: copy of the model, scenario changes, resetmodel(), seed (randinit streams 0-99 from the seed),
run to --hours (converted to model time), stats per object (in, out, stay_avg, content_avg, % time per state).
A custom --script gets {{SEED}} and {{HOURS}} and may write "OBJ\t<name>\t<class>\tkey=value..." lines like
the default (skills/flexsim/scripts/rep.fs) and/or "KPI\t<name>\t<value>" lines.

Output in --out:
  raw/<scenario>_<seed>.txt   FlexSim output per run (runs with a file are skipped: re-run to resume)
  runs.csv                    one row per run: scenario, seed, then one column per metric (Object.metric)
  summary.csv                 per scenario and metric: n, mean, sd, 95 % confidence half-width, min, max
  results.xlsx                sheets summary, runs, scenarios (no extra Python packages needed)
"""
import csv
import json
import math
import os
import re
import statistics
import sys
import time
import zipfile
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "flexsim"))
import fs  # noqa: E402

T95 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145,
       2.131, 2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


def fs_str(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def prelude(changes):
    """Scenario changes -> FlexScript that runs before the replication script."""
    out = []

    def fail(msg):
        return f'{{ fileopen("{{{{OUT}}}}", "w"); fpt({fs_str("ERROR " + msg)}); fpr(); fileclose(); return 0; }}'

    for key, val in changes.items():
        m = re.fullmatch(r"table:(.+)\[(\d+)\]\[(\d+)\]", key)
        if m:
            name, r, c = m.groups()
            out.append(f'if (!objectexists(model().find("Tools/GlobalTables/{name}"))) {fail("no global table " + name)}')
            v = fs_str(val) if isinstance(val, str) else repr(float(val))
            out.append(f'Table("{name}")[{r}][{c}] = {v};')
            continue
        m = re.fullmatch(r"([^/.]+)([/.])(.+)", key)
        if not m:
            sys.exit(f"bad key {key!r}: use Object/variable, Object.label or table:Name[row][col]")
        obj, kind, field = m.groups()
        out.append("{")
        out.append(f'treenode o = model().find("{obj}");')
        out.append(f'if (!objectexists(o)) {fail("no object " + obj)}')
        if kind == ".":
            if isinstance(val, str):
                out.append(f'assertlabel(o, "{field}", DATATYPE_STRING).value = {fs_str(val)};')
            else:
                out.append(f'assertlabel(o, "{field}", DATATYPE_NUMBER).value = {float(val)!r};')
        else:
            out.append(f'treenode v = getvarnode(o, "{field}");')
            out.append(f'if (!objectexists(v)) {fail("no variable " + key)}')
            if isinstance(val, str):
                code = "Object current = ownerobject(c);\nObject item = param(1);\nreturn " + val.rstrip(";") + ";\n"
                out.append(f"v.dataType = DATATYPE_STRING; setnodestr(v, {fs_str(code)});")
                out.append("switch_flexscript(v, 1); buildnodeflexscript(v);")
            else:
                out.append(f"switch_flexscript(v, 0); v.dataType = DATATYPE_NUMBER; setnodenum(v, {float(val)!r});")
        out.append("}")
    return "\n".join(out)


def parse(text):
    """FlexSim output -> {metric: value}. OBJ lines give Object.in/out/stay_avg/content_avg and Object.pct_<state>."""
    row = {}
    for line in text.splitlines():
        p = line.rstrip("\n").split("\t")
        if p[0] == "OBJ" and len(p) >= 3:
            kv = {}
            for x in p[3:]:
                k, _, v = x.partition("=")
                try:
                    kv[k] = float(v)
                except ValueError:
                    pass
            base = ("in", "out", "stay_avg", "content_avg", "content_max")
            states = {k: v for k, v in kv.items() if k not in base}
            for k in base:
                if k in kv:
                    row[f"{p[1]}.{k}"] = kv[k]
            total = sum(states.values())
            for k, v in states.items():
                row[f"{p[1]}.pct_{k}"] = 100 * v / total if total else 0.0
        elif p[0] == "KPI" and len(p) >= 3:
            row[p[1]] = float(p[2])
    return row


def summarize(values):
    n = len(values)
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if n > 1 else 0.0
    half = (T95[n - 2] if n - 1 <= len(T95) else 1.96) * sd / math.sqrt(n) if n > 1 else 0.0
    return n, mean, sd, half, min(values), max(values)


def col_name(i):
    s = ""
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(path, sheets):
    """Minimal .xlsx writer: sheets = [(name, [row, ...])], cells are str or numbers. Standard library only."""
    def sheet_xml(rows):
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
               '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for r, row in enumerate(rows, 1):
            cells = []
            for c, v in enumerate(row, 1):
                ref = f"{col_name(c)}{r}"
                if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
                    cells.append(f'<c r="{ref}"><v>{v!r}</v></c>')
                elif v is not None and v != "":
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>')
            out.append(f'<row r="{r}">{"".join(cells)}</row>')
        out.append("</sheetData></worksheet>")
        return "".join(out)

    ns = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                             for i in range(1, len(sheets) + 1)) + "</Types>")
        z.writestr("_rels/.rels", f'<?xml version="1.0" encoding="UTF-8"?><Relationships {ns}>'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + "".join(f'<sheet name="{escape(n[:31])}" sheetId="{i}" r:id="rId{i}"/>' for i, (n, _) in enumerate(sheets, 1))
                   + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", f'<?xml version="1.0" encoding="UTF-8"?><Relationships {ns}>'
                   + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                             for i in range(1, len(sheets) + 1)) + "</Relationships>")
        for i, (_, rows) in enumerate(sheets, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml(rows))


def main(argv):
    opts = ("--out", "--seeds", "--hours", "--jobs", "--timeout", "--script", "--kpi", "--work")
    pos = [a for i, a in enumerate(argv[1:], 1) if a not in opts and argv[i - 1] not in opts]
    if len(pos) < 2 or "--out" not in argv:
        print(__doc__)
        return 2
    arg = lambda k, d: argv[argv.index(k) + 1] if k in argv else d
    model, spec_path = pos
    spec = json.load(open(spec_path, encoding="utf-8"))
    scenarios = spec["scenarios"]
    for name in scenarios:
        if not re.fullmatch(r"[A-Za-z0-9_]+", name):
            sys.exit(f"scenario name {name!r}: use letters, digits and _ only")
    out = arg("--out", None)
    seeds = fs.seed_list(arg("--seeds", spec.get("seeds", "1-10")))
    hours = float(arg("--hours", spec.get("hours", 8)))
    jobs = int(arg("--jobs", fs.DEFAULT_JOBS))
    timeout = int(arg("--timeout", 300))
    kpi = re.compile(arg("--kpi", ".*"))
    script_src = arg("--script", os.path.join(HERE, "..", "flexsim", "scripts", "rep.fs"))
    work = arg("--work", fs.WORK.rsplit("/", 1)[0] + "/exp")
    raw = os.path.join(out, "raw")
    os.makedirs(raw, exist_ok=True)

    # one script for all runs: {{PRELUDE}} (scenario changes) + the replication script
    os.makedirs(work, exist_ok=True)
    script = work + "/exp_script.fs"
    open(script, "w", encoding="utf-8").write("{{PRELUDE}}\n" + open(script_src, encoding="utf-8").read())
    preludes = {name: prelude(ch) for name, ch in scenarios.items()}
    todo = [(s, seed) for s in scenarios for seed in seeds
            if not os.path.exists(os.path.join(raw, f"{s}_{seed}.txt"))]
    total = len(scenarios) * len(seeds)
    print(f"{len(scenarios)} scenarios x {len(seeds)} seeds = {total} runs, {hours:g} h each; "
          f"{total - len(todo)} done already; {jobs} at the same time", flush=True)
    t0 = time.time()
    failed = []

    def done(params, res):
        tag = f"{params['_S']}_{params['SEED']}"
        if res is None or res.startswith("ERROR"):
            failed.append(tag)
            print(f"  {tag}: FAILED {res.strip() if res else '(no output)'}", flush=True)
            return
        open(os.path.join(raw, tag + ".txt"), "w", encoding="utf-8").write(res)
        print(f"  {tag}: done [{time.time() - t0:.0f} s]", flush=True)

    fs.run_jobs(model, script, [{"_S": s, "SEED": seed, "HOURS": hours, "PRELUDE": preludes[s]} for s, seed in todo],
                jobs, timeout, work=work, on_done=done)

    rows, metrics = [], []
    for s in scenarios:
        for seed in seeds:
            p = os.path.join(raw, f"{s}_{seed}.txt")
            if not os.path.exists(p):
                continue
            r = parse(open(p, encoding="utf-8").read())
            r = {k: v for k, v in r.items() if kpi.search(k)}
            for k in r:
                if k not in metrics:
                    metrics.append(k)
            rows.append((s, seed, r))
    if not rows:
        print("no results")
        return 1
    runs_tab = [["scenario", "seed"] + metrics] + [[s, seed] + [r.get(m, "") for m in metrics] for s, seed, r in rows]
    summ_tab = [["scenario", "metric", "n", "mean", "sd", "ci95_half", "min", "max"]]
    for s in scenarios:
        for m in metrics:
            vals = [r[m] for sc, _, r in rows if sc == s and m in r]
            if vals:
                summ_tab.append([s, m] + [round(x, 6) for x in summarize(vals)])
    for name, tab in (("runs.csv", runs_tab), ("summary.csv", summ_tab)):
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(tab)
    scen_tab = [["scenario", "change", "value"]] + [[s, k, str(v)] for s, ch in scenarios.items() for k, v in ch.items()] \
        + [[s, "(none)", ""] for s, ch in scenarios.items() if not ch]
    write_xlsx(os.path.join(out, "results.xlsx"), [("summary", summ_tab), ("runs", runs_tab), ("scenarios", scen_tab)])
    print(f"{len(rows)}/{total} runs in {time.time() - t0:.0f} s -> {out} (runs.csv, summary.csv, results.xlsx)")
    if failed:
        print(f"FAILED runs: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
