"""End-to-end tests: every tool runs for real against FlexSim and the demo model.

Run (Windows, FlexSim installed):
  python -I -X utf8 tests/run_tests.py [--skip-dashboard]
Needs uv (https://docs.astral.sh/uv/) for the matplotlib and openpyxl checks.
--skip-dashboard skips the dashboard PNG export (it opens a FlexSim window for about 45 s).
Each test prints PASS or FAIL; the exit code is the number of failures.
"""
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(ROOT, "skills")
DEMO = os.path.join(ROOT, "examples", "demo.fsm")
PY = [sys.executable, "-I", "-X", "utf8"]
sys.path.insert(0, os.path.join(SK, "flexsim"))
import fs  # noqa: E402

TMP = fs.WORK.rsplit("/", 1)[0] + "/tests"
results = []


def sh(args, timeout=900):
    t0 = time.time()
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, r.stdout + r.stderr, time.time() - t0


def check(name, cond, detail, dt):
    results.append(cond)
    print(f"{'PASS' if cond else 'FAIL'}  {name}  ({dt:.0f} s)  {detail}", flush=True)


def main():
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP)
    print(f"FlexSim: {fs.EXE}\nwork: {fs.WORK}\ntemp: {TMP}\n", flush=True)

    # 1. build the demo model from its script and compare it with the shipped one
    code, out, dt = sh(PY + [os.path.join(SK, "flexsim", "fs.py"), "new", os.path.join(ROOT, "examples", "build_demo.fs")])
    check("build demo model by script", code == 0 and "saved" in out and os.path.exists(fs.WORK + "/demo.fsm"),
          out.strip().splitlines()[-1] if out.strip() else "", dt)

    # 2. summary
    code, out, dt = sh(PY + [os.path.join(SK, "flexsim", "fs.py"), "summary", DEMO])
    ok = all(s in out for s in ("## Source1 (Source)", "## Queue1 (Queue)", "## Processor1 (Processor)",
                                "## Sink1 (Sink)", "out: 1=Sink1", "cycletime=25"))
    check("summary", code == 0 and ok, "4 objects, ports and cycle time found", dt)

    # 3. dump
    code, out, dt = sh(PY + [os.path.join(SK, "flexsim", "fs.py"), "dump", DEMO, "Processor1"])
    check("dump", code == 0 and "cycletime = 25" in out, f"{len(out.splitlines())} lines", dt)

    # 4. sim: 8 h, the processor must be busy about 25/30 = 83 % of the time
    code, out, dt = sh(PY + [os.path.join(SK, "flexsim", "fs.py"), "sim", DEMO, "8"])
    line = next((l for l in out.splitlines() if "\tProcessor1\t" in l), "")
    kv = dict(x.split("=") for x in line.split("\t")[3:] if "=" in x)
    busy = float(kv.get("processing", 0)) / 28800 * 100
    check("sim 8 h", code == 0 and "END rep1 t=28800" in out and 70 < busy < 95, f"processor busy {busy:.1f} %", dt)

    # 5. reps in parallel: 4 seeds, results must differ between seeds and repeat for the same seed
    rd = TMP + "/reps"
    code, out, dt = sh(PY + [os.path.join(SK, "flexsim", "fs.py"), "reps", DEMO, "--seeds", "1-4", "--jobs", "4",
                             "--hours", "8", "--outdir", rd, "--work", TMP + "/repwork"])
    sinks = []
    for s in range(1, 5):
        p = f"{rd}/out_{s}.txt"
        txt = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
        sinks.append(next((l.split("\tin=")[1].split("\t")[0] for l in txt.splitlines() if "\tSink1\t" in l), None))
    code2, out2, _ = sh(PY + [os.path.join(SK, "flexsim", "fs.py"), "reps", DEMO, "--seeds", "1", "--jobs", "1",
                              "--hours", "8", "--outdir", TMP + "/reps_again", "--work", TMP + "/repwork"])
    again = open(TMP + "/reps_again/out_1.txt", encoding="utf-8").read() if code2 == 0 else ""
    same = again == open(f"{rd}/out_1.txt", encoding="utf-8").read() if os.path.exists(f"{rd}/out_1.txt") else False
    check("reps (4 seeds, parallel)", code == 0 and None not in sinks and len(set(sinks)) > 1 and same,
          f"Sink1 input per seed {sinks}; seed 1 repeats exactly: {same}", dt)

    # 6. bisect: finds the planted bug on line 13 of examples/broken.fs, and passes a good script
    code, out, dt = sh(PY + [os.path.join(SK, "flexsim-bisect", "bisect.py"), DEMO, os.path.join(ROOT, "examples", "broken.fs")])
    check("bisect finds the bug", code == 1 and "lines 13-13" in out, out.strip().splitlines()[-1].strip(), dt)
    code, out, dt = sh(PY + [os.path.join(SK, "flexsim-bisect", "bisect.py"), DEMO, os.path.join(SK, "flexsim", "scripts", "dump.fs"),
                             "--param", "PATH=Queue1"])
    check("bisect passes a good script", code == 0 and "whole script" in out, out.strip().splitlines()[-1], dt)

    # 7. experiment: 3 scenarios x 5 seeds; the faster machine must cut the queue time
    ed = TMP + "/exp"
    code, out, dt = sh(PY + [os.path.join(SK, "flexsim-experiment", "experiment.py"), DEMO,
                             os.path.join(ROOT, "examples", "scenarios.json"), "--out", ed, "--jobs", "6"])
    summ = {}
    if os.path.exists(ed + "/summary.csv"):
        import csv
        for r in csv.DictReader(open(ed + "/summary.csv", encoding="utf-8")):
            summ[(r["scenario"], r["metric"])] = float(r["mean"])
    q = {s: summ.get((s, "Queue1.stay_avg")) for s in ("base", "fast_machine", "more_orders")}
    ok = code == 0 and None not in q.values() and q["fast_machine"] < q["base"] < q["more_orders"]
    check("experiment (3 scenarios x 5 seeds)", ok, f"Queue1 mean stay {q}", dt)
    code, out, dt = sh(["uv", "run", "--quiet", "--with", "openpyxl", "python", "-I", "-X", "utf8",
                        os.path.join(ROOT, "tests", "check_xlsx.py"), ed + "/results.xlsx"])
    check("experiment Excel file opens", code == 0 and "sheet summary" in out and "sheet runs: 16 rows" in out,
          " | ".join(out.strip().splitlines()[-3:]), dt)

    # 8. experiment rejects a scenario that names a missing object
    bad = TMP + "/bad.json"
    open(bad, "w").write('{"scenarios": {"oops": {"NoSuchObject/cycletime": 3}}}')
    code, out, dt = sh(PY + [os.path.join(SK, "flexsim-experiment", "experiment.py"), DEMO, bad, "--out", TMP + "/expbad",
                             "--seeds", "1", "--jobs", "1"])
    check("experiment reports a bad scenario", code == 1 and "ERROR no object NoSuchObject" in out,
          next((l.strip() for l in out.splitlines() if "ERROR" in l), ""), dt)

    # 9. charts from the experiment results
    cd = TMP + "/charts"
    code, out, dt = sh(["uv", "run", "--quiet", "--with", "matplotlib", "python", "-I", "-X", "utf8",
                        os.path.join(SK, "flexsim-charts", "charts.py"), ed, "--out", cd,
                        "--metric", "Queue1.stay_avg", "--objects", "Queue1,Processor1"])
    pngs = sorted(f for f in os.listdir(cd) if f.endswith(".png")) if os.path.isdir(cd) else []
    big = all(os.path.getsize(os.path.join(cd, f)) > 10000 for f in pngs)
    check("charts (matplotlib)", code == 0 and len(pngs) == 5 and big, ", ".join(pngs), dt)

    # 10. FlexSim dashboard charts to PNG (opens a FlexSim window)
    if "--skip-dashboard" not in sys.argv:
        dd = TMP + "/dash"
        code, out, dt = sh(PY + [os.path.join(SK, "flexsim-charts", "dashboard_png.py"), DEMO,
                                 os.path.join(SK, "flexsim-charts", "charts_example.fs"), "--out", dd, "--hours", "5"])
        pngs = sorted(f for f in os.listdir(dd) if f.endswith(".png")) if os.path.isdir(dd) else []
        check("dashboard charts to PNG", code == 0 and len(pngs) == 2, out.strip().splitlines()[-1] if out.strip() else "", dt)

    # 11. command reference lookup
    code, out, dt = sh(PY + [os.path.join(SK, "flexsim", "cmdref.py"), "stoptime"])
    check("cmdref", code == 0 and "===== stoptime" in out and "not found" not in out, "stoptime entry found", dt)

    fails = results.count(False)
    print(f"\n{len(results) - fails}/{len(results)} passed")
    return fails


if __name__ == "__main__":
    sys.exit(main())
