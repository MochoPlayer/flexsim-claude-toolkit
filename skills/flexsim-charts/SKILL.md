---
name: flexsim-charts
description: Make PNG charts of FlexSim results. charts.py draws state bars, mean with 95 % confidence interval per scenario and box plots from replication results (no FlexSim window). dashboard_png.py exports FlexSim's own dashboard charts to PNG from one FlexSim session. Use when the user wants charts, plots, graphs or figures of a FlexSim model or experiment, says "flexsim charts", "dashboard to png" or "plot the replications".
---

# FlexSim charts

Needs the `flexsim` skill next to this one (it uses `../flexsim/fs.py`).

**Before you make charts:** list "chart -> what it helps explain" and let the user pick. Make no chart they did not pick.

## 1. Charts from results (matplotlib, no FlexSim window)

```
uv run --with matplotlib python -I -X utf8 charts.py <results dir> --out <dir> [--metric Queue1.stay_avg ...] [--objects Queue1,Processor1] [--scenario base]
```

`<results dir>` = the `--out` of `flexsim-experiment` or the `--outdir` of `fs.py reps`.

| File | Shows |
|---|---|
| `states_<scenario>.png` | % of time in each state per object, mean over the seeds |
| `metric_<metric>.png` | mean per scenario with the 95 % confidence interval |
| `box_<metric>.png` | spread over the seeds per scenario, each seed as a dot |

Colours: one fixed colour per state name (processing blue, blocked orange, idle grey...), so charts of different
scenarios read the same way.

## 2. FlexSim dashboard charts to PNG

```
python -I -X utf8 dashboard_png.py <model.fsm> charts_example.fs --out <dir> [--hours 5] [--only a,b] [--timeout 600]
```

A charts file is FlexScript in blocks: `//@setup` (optional, runs once) and `//@chart <name> [w h]` (one chart on
the dashboard `dash`). Template list: `ChartTemplateDefinitions/<Content|Output|Staytime|State|...>/<Name>`.
Full format: the docstring of `dashboard_png.py`; working example: `charts_example.fs`.

How it works: FlexSim opens WITH its window (dashboard charts are HTML in an embedded browser), builds all charts
on one dashboard, runs the model once, then a timer shows each chart in turn and Python captures the graph panel
with Win32 `PrintWindow(PW_RENDERFULLCONTENT)`. Works with FlexSim behind other windows, not minimised.

Rules:
- Test with `--hours 5` (about 45 s for 2 charts). Use the full horizon only for the final export.
- Chart width is capped to the visible dashboard pane (about 360 px); the height is kept.
- It stops (exit 2) on a black capture or two identical PNGs; exit 3 = timeout or no progress for `--stall` s.
- Dashboard collectors keep making events, so set a stop time (the tool does) or a `stop()` in a trigger.
- Bar charts hide rows with value 0: `getvarnode(function_s(ch, "getChart"), "barSettings").find("showZeroColumns").value = 1`.
- Never `viewtofile()`: it is a screen grab, black when the window is behind others.
- A PNG that exists in `--out` is skipped: delete it to make it again.
