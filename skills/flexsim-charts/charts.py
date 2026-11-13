"""Make PNG charts from FlexSim replication results, with matplotlib. No FlexSim window needed.

Usage:
  uv run --with matplotlib python -I -X utf8 charts.py <results dir> --out <dir> [--metric Sink1.in ...]
                                                       [--objects Queue1,Processor1] [--scenario base]

<results dir>: the --out folder of flexsim-experiment (reads raw/<scenario>_<seed>.txt), or the --outdir of
`fs.py reps` (reads out_<seed>.txt; one scenario called "reps"). Lines read: "OBJ\t<name>\t<class>\tkey=value..."
and "KPI\t<name>\t<value>".

Charts:
  states_<scenario>.png   % of time in each state per object (mean over the seeds), one bar per object
  metric_<metric>.png     mean per scenario with the 95 % confidence interval (only with --metric)
  box_<metric>.png        spread over the seeds per scenario (only with --metric)
Metric names: <Object>.in / out / stay_avg / content_avg / content_max / pct_<state>, or a KPI name.
"""
import glob
import math
import os
import re
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

INK, INK2, MUTED, GRID, AXIS, SURF = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
# fixed colour per state name (colour follows the state, not its rank); unknown states take the next free slot
STATE_COLOR = {"processing": "#2a78d6", "releasing": "#1baf7a", "setup": "#eda100", "blocked": "#eb6834",
               "waiting for operator": "#6250d6", "waiting for transporter": "#e87ba4", "down": "#e34948",
               "idle": "#c3c2b7", "empty": "#9e9d96", "generating": "#1baf7a", "collecting": "#008300"}
BASE = ("in", "out", "stay_avg", "content_avg", "content_max")
T95 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145,
       2.131, 2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
                     "figure.facecolor": SURF, "axes.facecolor": SURF, "figure.dpi": 150, "savefig.bbox": "tight",
                     "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlecolor": INK, "legend.frameon": False})


def parse(text):
    """-> (metrics {name: value}, states {object: {state: time}}, object order)."""
    metrics, states, order = {}, {}, []
    for line in text.splitlines():
        p = line.rstrip("\n").split("\t")
        if p[0] == "OBJ" and len(p) >= 3:
            name = p[1]
            order.append(name)
            st = {}
            for x in p[3:]:
                k, _, v = x.partition("=")
                try:
                    v = float(v)
                except ValueError:
                    continue
                if k in BASE:
                    metrics[f"{name}.{k}"] = v
                else:
                    st[k] = v
            tot = sum(st.values())
            states[name] = st
            for k, v in st.items():
                metrics[f"{name}.pct_{k}"] = 100 * v / tot if tot else 0.0
        elif p[0] == "KPI" and len(p) >= 3:
            metrics[p[1]] = float(p[2])
    return metrics, states, order


def load(folder):
    """-> {scenario: [(seed, metrics, states)]}, object order."""
    runs, order = {}, []
    files = glob.glob(os.path.join(folder, "raw", "*.txt")) or glob.glob(os.path.join(folder, "out_*.txt"))
    for path in sorted(files):
        m = re.fullmatch(r"(.+)_(\d+)\.txt", os.path.basename(path))
        if not m:
            continue
        scen = "reps" if m.group(1) == "out" else m.group(1)
        met, st, ob = parse(open(path, encoding="utf-8", errors="replace").read())
        if not met:
            continue
        runs.setdefault(scen, []).append((int(m.group(2)), met, st))
        order += [o for o in ob if o not in order]
    for v in runs.values():
        v.sort(key=lambda r: r[0])
    return runs, order


def ci(vals):
    n = len(vals)
    if n < 2:
        return statistics.fmean(vals), 0.0
    t = T95[n - 2] if n - 1 <= len(T95) else 1.96
    return statistics.fmean(vals), t * statistics.stdev(vals) / math.sqrt(n)


def state_chart(scen, rows, objects, out):
    """Horizontal 100 % stacked bars: share of time per state, mean over the seeds."""
    pct = {}
    for o in objects:
        acc = {}
        for _, _, st in rows:
            tot = sum(st.get(o, {}).values())
            for k, v in st.get(o, {}).items():
                acc[k] = acc.get(k, 0) + (100 * v / tot if tot else 0) / len(rows)
        if acc:
            pct[o] = acc
    if not pct:
        return None
    objs = list(pct)
    states = []
    for o in objs:
        states += [s for s in pct[o] if s not in states]
    states.sort(key=lambda s: list(STATE_COLOR).index(s) if s in STATE_COLOR else 99)
    free = [c for c in SERIES if c not in STATE_COLOR.values()] + SERIES
    colors = {s: STATE_COLOR.get(s) or free.pop(0) for s in states}
    fig, ax = plt.subplots(figsize=(7.5, 0.55 * len(objs) + 1.6))
    y = range(len(objs))[::-1]
    left = [0.0] * len(objs)
    for s in states:
        w = [pct[o].get(s, 0) for o in objs]
        ax.barh(list(y), w, left=left, color=colors[s], height=0.55, label=s, edgecolor=SURF, linewidth=1.5)
        for yi, l, wi in zip(y, left, w):
            if wi >= 9:
                txt = "#0b0b0b" if colors[s] in ("#eda100", "#c3c2b7", "#9e9d96") else "#ffffff"
                ax.text(l + wi / 2, yi, f"{wi:.0f}%", ha="center", va="center", fontsize=8, color=txt)
        left = [a + b for a, b in zip(left, w)]
    ax.set_yticks(list(y), objs)
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of time")
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Time in each state ({scen}, mean of {len(rows)} runs)", loc="left")
    ax.legend(ncol=min(4, len(states)), loc="upper left", bbox_to_anchor=(0, -0.18 - 0.02 * len(objs)),
              fontsize=8, labelcolor=INK2)
    path = os.path.join(out, f"states_{scen}.png")
    fig.savefig(path)
    plt.close(fig)
    return path


def metric_charts(metric, runs, out):
    scens = [s for s in runs if any(metric in r[1] for r in runs[s])]
    if not scens:
        print(f"  no data for metric {metric}")
        return []
    vals = {s: [r[1][metric] for r in runs[s] if metric in r[1]] for s in scens}
    safe = re.sub(r"[^A-Za-z0-9_.]+", "_", metric)
    paths = []
    # mean + 95 % CI per scenario (one series: one colour, no legend; the title names the metric)
    fig, ax = plt.subplots(figsize=(1.3 * len(scens) + 2.5, 3.6))
    means, halfs = zip(*(ci(vals[s]) for s in scens))
    ax.bar(scens, means, color=SERIES[0], width=0.55)
    ax.errorbar(scens, means, yerr=halfs, fmt="none", ecolor=INK, elinewidth=1.2, capsize=5)
    for i, (m, h) in enumerate(zip(means, halfs)):
        ax.text(i, m + h, f"{m:.4g}", ha="center", va="bottom", fontsize=8, color=INK2,
                bbox=dict(facecolor=SURF, edgecolor="none", pad=1))
    ax.grid(axis="x", visible=False)
    ax.set_title(f"{metric}: mean and 95 % confidence interval", loc="left")
    ax.set_ylabel(metric)
    p = os.path.join(out, f"metric_{safe}.png")
    fig.savefig(p)
    plt.close(fig)
    paths.append(p)
    # spread over seeds
    fig, ax = plt.subplots(figsize=(1.3 * len(scens) + 2.5, 3.6))
    ax.boxplot([vals[s] for s in scens], widths=0.45, patch_artist=True,
               boxprops=dict(facecolor="#cde2fb", edgecolor=SERIES[0]), medianprops=dict(color=SERIES[0], linewidth=2),
               whiskerprops=dict(color=INK2), capprops=dict(color=INK2), flierprops=dict(markeredgecolor=INK2))
    for i, s in enumerate(scens, 1):
        ax.scatter([i] * len(vals[s]), vals[s], s=14, color=INK2, zorder=3)
    ax.set_xticks(range(1, len(scens) + 1), scens)
    ax.grid(axis="x", visible=False)
    ax.set_title(f"{metric}: spread over {max(len(v) for v in vals.values())} seeds", loc="left")
    ax.set_ylabel(metric)
    p = os.path.join(out, f"box_{safe}.png")
    fig.savefig(p)
    plt.close(fig)
    paths.append(p)
    return paths


def main(argv):
    opts = ("--out", "--metric", "--objects", "--scenario")
    pos = [a for i, a in enumerate(argv[1:], 1) if a not in opts and argv[i - 1] not in opts]
    if not pos or "--out" not in argv:
        print(__doc__)
        return 2
    out = argv[argv.index("--out") + 1]
    metrics = [argv[i + 1] for i, a in enumerate(argv) if a == "--metric"]
    runs, order = load(pos[0])
    if not runs:
        print(f"no result files in {pos[0]} (raw/*.txt or out_*.txt with OBJ lines)")
        return 1
    objects = argv[argv.index("--objects") + 1].split(",") if "--objects" in argv else order
    scen_only = argv[argv.index("--scenario") + 1] if "--scenario" in argv else None
    os.makedirs(out, exist_ok=True)
    made = []
    for scen, rows in runs.items():
        if scen_only and scen != scen_only:
            continue
        p = state_chart(scen, rows, objects, out)
        if p:
            made.append(p)
    for m in metrics:
        made += metric_charts(m, runs, out)
    for p in made:
        print("  wrote", p)
    print(f"{len(made)} charts from {sum(len(v) for v in runs.values())} runs, {len(runs)} scenarios -> {out}")
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
