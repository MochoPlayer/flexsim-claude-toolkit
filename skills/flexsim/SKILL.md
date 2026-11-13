---
name: flexsim
description: Read, check, build and run Autodesk FlexSim models (.fsm) from Claude Code with no GUI. Summarize a model (objects, ports, labels, global tables, changed code), dump any tree node, run the model to a time and collect statistics, run seeded replications in parallel, build a model by script, look up FlexScript commands in the local help. Use when the user works on a FlexSim model, says "flexsim", "check my model", "run the model", "what does this fsm do", or asks how to write a FlexScript trigger.
---

# FlexSim runner

Drives FlexSim with no window: it copies the model to a work folder, runs a FlexScript file inside FlexSim
(`flexsim.exe <model> /maintenance nogui_disablemsg_runscript /scriptpath <wrapper.fs>`) and reads back the
text file that the script writes. It never writes the user's model.

Settings (environment variables, all optional): `FLEXSIM_EXE` (default: newest FlexSim under Program Files),
`FLEXSIM_WORK` (default `~/fsharness/work`; ASCII, no hyphen, no space), `FLEXSIM_JOBS` (parallel runs, default 6).

## Commands

Run from this folder. Model paths with accents and spaces are fine (fs.py copies the model).

| Need | Command |
|---|---|
| What is in the model | `python -I -X utf8 fs.py summary "<model.fsm>"` |
| Raw tree below one node | `python -I -X utf8 fs.py dump "<model.fsm>" "Processor1"` (or `Tools/GlobalTables`) |
| Run N hours, stats per object | `python -I -X utf8 fs.py sim "<model.fsm>" 40` |
| N seeded replications in parallel | `python -I -X utf8 fs.py reps "<model.fsm>" [my.fs] --seeds 1-20 --hours 40 [--jobs 6] [--outdir D] [--work W]` |
| Own FlexScript on a model | `python -I -X utf8 fs.py run "<model.fsm>" my.fs` (write `{{OUT}}` where the output file goes) |
| Build a model from nothing | `python -I -X utf8 fs.py new build.fs` (empty model; the script saves with `cmdsavetree`) |
| FlexScript command docs | `python -I -X utf8 cmdref.py stoptime runfunction` or `cmdref.py --grep "table"` |
| Class API docs (Object, Table...) | grep `<FlexSim folder>/help/FlexScriptAPIReference/<Group>/<Class>.xml` |

Add `--gui` to watch FlexSim do it, `--timeout 600` for long runs. Each call takes about 5-10 s.
Related skills: `flexsim-experiment` (scenarios x seeds to CSV/Excel), `flexsim-charts` (PNG charts),
`flexsim-bisect` (find the line that does not compile).

## Script placeholders

`{{OUT}}` output file, `{{WORK}}` work folder; `reps` adds `{{SEED}}` and `{{HOURS}}`. Model hours to model time,
for any time unit: `double STOP = convert(getmodelunit(START_TIME) + H * 3600, FS_DATETIME, MODEL_TIME);`

## Rules (learned the hard way)

1. **Never start flexsim.exe from Git Bash with `/maintenance` args.** Git Bash turns `/maintenance` into a file
   path and FlexSim ignores the script. fs.py uses Python `subprocess`, which is safe.
2. **No hyphens in the script path.** FlexSim cuts `/scriptpath` at the first `-`. Hence the work folder rule.
3. **A compile error gives no message.** The wrapper runs the script with `executefsfile`; if it does not compile,
   it is skipped and fs.py says "no output". Use `flexsim-bisect`, or write progress lines:
   `fileopen("{{OUT}}","a"); fpt("step 3"); fpr(); fileclose();`.
4. **Run synchronously**: `resetmodel(); stoptime(T); runfunction(1);`. If `time()` after the run is less than `T`,
   the model ran out of events: something is blocked or all work is done.
5. **Do not edit the user's .fsm.** Give exact GUI steps (object, tab, field, code), or build a copy by script.
6. **Kill only your own FlexSim**: `taskkill /PID <pid> /T /F` (fs.py does this on timeout). Never
   `taskkill /IM flexsim.exe`: it closes the user's FlexSim and unsaved work.
7. **Parallel runs**: one work folder per run (`fs.py reps` does this). A loop of `fs.py run` shares one folder and
   the runs overwrite each other. Two sessions at once: give each its own `--work`.
8. **Code fields and triggers by script**: `treenode v = getvarnode(obj, "entrytrigger"); v.dataType = DATATYPE_STRING;
   setnodestr(v, code); switch_flexscript(v, 1); buildnodeflexscript(v);`. Works for triggers and for number fields
   turned into code (cycletime, setuptime, interarrivaltime).
9. **Building a model by script**: `createinstance(library().find("fixedresources/Queue"), model())` (the path matters:
   `library().find("?Sink")` returns the Process Flow Sink activity), `contextdragconnection(a, b, "A")` (port) or
   `"S"` (center), `assertlabel(obj, "Type", DATATYPE_NUMBER).value = 1`, then `resetmodel(); cmdsavetree(model(), "{{WORK}}/x.fsm");`.
   Example: `examples/build_demo.fs` in the toolkit repo.
10. **`Model.find()` returns a treenode**: cast first: `Object o = Model.find("M1"); o.location.x`.
    `Model.find("M1").location` is a compile error (and compile errors are silent).
11. **Global tables**: `Table("X")[row][col]`, `.numRows`, `.getColHeader(c)`; row 0 does not exist. For logs use
    `int r = t.numRows + 1; t.setSize(r, t.numCols);` (not `addRow`).
12. **Random streams**: `exponential(0, mean, stream)`, `normal(mean, sd, stream)`. Seed with
    `randinit(stream, seed)` after `resetmodel()` (see `scripts/rep.fs`).

## FlexScript notes

- Object API: `o.inObjects[k]`, `o.outObjects[k]`, `o.centerObjects[k]`, `o.location.x`, `o.stats.input.value`,
  `o.stats.output.value`, `o.stats.staytime.average`, `o.stats.content.average`, `o.stats.state().profile` (Table: name, time).
- Class of an object: `n.find(">classes").first.value.name` (`isclasstype(o, "Processor")` is also true for a Combiner).
- Attributes: `getvarnode(o, "cycletime")`, `n.find(">labels")`. Labels on items: `item.Type`.
- Combiner: set the lot size in On Entry when `port == 1` (Target Quantity + `setvarnum(current, "targetcomponentsum", n)`);
  changes made when a component enters (port 2) come too late.
- `pt("text"); pr();` goes to the Output Console, which you cannot see with no GUI: write to `{{OUT}}` instead.
