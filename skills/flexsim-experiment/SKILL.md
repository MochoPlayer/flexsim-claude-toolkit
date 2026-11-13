---
name: flexsim-experiment
description: Run what-if scenarios x seeded replications of a FlexSim model with no GUI, in parallel, and get the results as CSV and Excel (mean, standard deviation, 95 % confidence interval per scenario). Scenarios change object variables, labels, code fields or global table cells. Use when the user wants to compare scenarios, run replications, says "experiment", "what if", "replications", "confidence interval" or "compare configurations" for a FlexSim model.
---

# FlexSim experiment

Needs the `flexsim` skill next to this one (it uses `../flexsim/fs.py`).

```
python -I -X utf8 experiment.py <model.fsm> <scenarios.json> --out <dir> [--seeds 1-10] [--hours 8] [--jobs 6] [--kpi REGEX] [--script my_rep.fs]
```

## scenarios.json

```json
{
  "hours": 8, "seeds": "1-10",
  "scenarios": {
    "base": {},
    "faster": {"Processor1/cycletime": 20},
    "busy":   {"Source1/interarrivaltime": "exponential(0, 26, 1)"},
    "shift2": {"Processor1.Shift": 2},
    "table":  {"table:Params[2][1]": 5}
  }
}
```

| Key | Changes |
|---|---|
| `Object/variable` + number | an object variable (cycletime, capacity, ...) |
| `Object/variable` + text | a code field: the text is the returned expression |
| `Object.label` | a label on the object (created if missing) |
| `table:Name[row][col]` | a global table cell |

Scenario names: letters, digits, `_`. A key that names a missing object, variable or table stops that run with
`ERROR ...`, and the tool exits with code 1.

## What one run does

Copy of the model, scenario changes, `resetmodel()`, seed all random streams 0-99 from the seed, run to `--hours`
(converted to the model time unit), write stats per object. All scenarios use the same seeds (common random
numbers), so differences between scenarios are not just noise.

## Output (in --out)

- `raw/<scenario>_<seed>.txt`: FlexSim output per run. Runs with a file are skipped: run again to resume or add seeds.
- `runs.csv`: one row per run, one column per metric (`Queue1.stay_avg`, `Processor1.pct_processing`, ...).
- `summary.csv`: per scenario and metric: n, mean, sd, ci95_half, min, max.
- `results.xlsx`: sheets summary, runs, scenarios (written with the standard library, no packages).

Metrics per object: `in`, `out`, `stay_avg`, `content_avg`, and `pct_<state>` (share of time per state). Limit with
`--kpi "Sink|Processor"`. A custom `--script` (gets `{{SEED}}`, `{{HOURS}}`) may also write `KPI\t<name>\t<value>` lines.

## Tips

- Measured on a 4-object model: 15 runs of 8 h, 6 at a time, 25-40 s.
- Report the confidence interval, not only the mean. If the intervals of two scenarios overlap, add seeds.
- Charts from the results: `flexsim-charts` (`charts.py <out dir> --out <dir> --metric <metric>`).
