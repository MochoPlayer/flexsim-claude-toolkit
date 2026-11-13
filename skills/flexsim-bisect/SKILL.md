---
name: flexsim-bisect
description: Find the line of a FlexScript file that does not compile or stops the script, when FlexSim gives no error text (a script run with no GUI is skipped silently). Binary search over prefixes of the script, about log2(statements) FlexSim runs. Use when a FlexSim script gives "no output", says "bisect", "which line fails", or a script run with the flexsim skill does nothing.
---

# FlexSim bisect

Needs the `flexsim` skill next to this one (it uses `../flexsim/fs.py`).

```
python -I -X utf8 bisect.py <model.fsm> <script.fs> [--param SEED=1 --param HOURS=1] [--timeout 60]
```

- Runs prefixes of the script, each with a marker line at the end; the first prefix whose marker never appears
  holds the bad statement. Prints the line numbers and the code.
- Cut points are top-level lines (brace depth 0). An error inside a `{ }` block reports the whole block: then
  copy the block body into a small file and bisect that.
- `--param KEY=VALUE` fills `{{KEY}}` (scripts for `fs.py reps` need `SEED` and `HOURS`).
- Exit code 0 = the whole script runs; 1 = a failing statement was found.
- About 5 s per FlexSim run: 9 statements took 5 runs, 28 s.

Common causes it finds: `Model.find("X").location` (cast to `Object` first), a missing `;`, an undeclared
variable, a wrong command name (check with `../flexsim/cmdref.py --grep`).
