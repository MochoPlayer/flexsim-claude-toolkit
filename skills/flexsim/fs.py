"""Run FlexScript against a FlexSim model with no GUI, and print what the script writes.

Usage:
  python -I -X utf8 fs.py run <model.fsm> <script.fs> [--gui] [--timeout 300]
  python -I -X utf8 fs.py new <script.fs>                 run a script on an empty model (build a model by script)
  python -I -X utf8 fs.py summary <model.fsm>
  python -I -X utf8 fs.py dump <model.fsm> [<path below model, e.g. Processor1>]
  python -I -X utf8 fs.py sim <model.fsm> <hours> [--reps N]
  python -I -X utf8 fs.py reps <model.fsm> [script.fs] --seeds 1-20 [--jobs 6] [--hours 40] [--outdir D] [--work W]
      One FlexSim per seed, --jobs at the same time (one work folder per job). The script gets {{SEED}} and
      {{HOURS}} (default script: scripts/rep.fs = seeded stats per object). Output: <outdir>/out_<seed>.txt.

Settings (environment variables):
  FLEXSIM_EXE    path to flexsim.exe (default: the newest C:/Program Files/**/FlexSim*/program/flexsim.exe)
  FLEXSIM_WORK   work folder, ASCII, no hyphens, no spaces (default: ~/fsharness/work, or C:/fsharness/work)
  FLEXSIM_JOBS   FlexSim runs at the same time for reps and experiments (default 6)

How it works:
- Copies the model into the work folder: FlexSim cuts the /scriptpath value at the first hyphen.
- Replaces {{OUT}} in the script with the output file path, {{WORK}} with the work folder, {{KEY}} with params.
- Starts flexsim.exe with subprocess (never from Git Bash: it rewrites "/maintenance" into a file path).
- A wrapper runs the script with executefsfile() and then calls cmdexit(), so scripts need no cmdexit().
- A script with a compile error is skipped silently: "no output". Find the line with flexsim-bisect.
- The original model is never written. Nothing is saved unless a script saves it.
"""
import glob
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DEFAULT_JOBS = int(os.environ.get("FLEXSIM_JOBS", 6))  # parallel FlexSim runs (reps, experiments)


def safe(p):
    """FlexSim cuts /scriptpath at the first hyphen; spaces and accents also break paths."""
    return p.isascii() and "-" not in p and " " not in p


def find_exe():
    exe = os.environ.get("FLEXSIM_EXE")
    if exe:
        return exe
    hits = []
    for root in (os.environ.get("ProgramFiles", r"C:\Program Files"), r"C:\Program Files (x86)"):
        hits += glob.glob(os.path.join(root, "Autodesk", "FlexSim *", "program", "flexsim.exe"))
        hits += glob.glob(os.path.join(root, "FlexSim *", "program", "flexsim.exe"))
    return sorted(hits)[-1] if hits else r"C:\Program Files\Autodesk\FlexSim 2027\program\flexsim.exe"


def default_work():
    w = os.environ.get("FLEXSIM_WORK")
    if w:
        return w.replace("\\", "/")
    home = os.path.expanduser("~/fsharness").replace("\\", "/")
    return (home if safe(home) else "C:/fsharness") + "/work"


EXE = find_exe()
WORK = default_work()


def kill_tree(pid):
    """Close only the FlexSim this script started (and its children). Other FlexSim windows stay open."""
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=NOWIN)


def run(model, script_path, gui=False, timeout=300, params=None, work=None, quiet=False):
    """Run script_path inside FlexSim on a copy of model (None = empty model). Returns the text the script
    wrote to {{OUT}}, or None. work: own work folder, so several runs can go at the same time."""
    work = (work or WORK).replace("\\", "/")
    if not safe(work):
        sys.exit(f"[fs.py] work folder must be ASCII with no hyphen or space: {work} (set FLEXSIM_WORK)")
    os.makedirs(work, exist_ok=True)
    work_model = work + "/model.fsm"
    if model and os.path.abspath(model) != os.path.abspath(work_model):
        shutil.copyfile(model, work_model)
    out = work + "/out.txt"
    status = work + "/status.txt"
    for f in (out, status):
        if os.path.exists(f):
            os.remove(f)
    text = open(script_path, encoding="utf-8").read()
    for k, v in (params or {}).items():  # params first: a param value may contain {{OUT}}
        text = text.replace("{{" + k + "}}", str(v))
    text = text.replace("{{OUT}}", out).replace("{{WORK}}", work)
    script = work + "/script.fs"
    open(script, "w", encoding="utf-8").write(text)
    # The wrapper always runs: it marks the start, runs the user script with executefsfile
    # (a compile error there does not stop the wrapper), marks the end and closes FlexSim.
    wrapper = work + "/wrapper.fs"
    open(wrapper, "w", encoding="utf-8").write(
        f'fileopen("{status}", "w"); fpt("started"); fpr(); fileclose();\n'
        f'executefsfile("{script}", 1);\n'
        f'fileopen("{status}", "a"); fpt("finished t=" + string.fromNum(time())); fpr(); fileclose();\n'
        'cmdexit();\n')
    flags = "disablemsg_runscript" if gui else "nogui_disablemsg_runscript"
    cmd = [EXE] + ([work_model.replace("/", "\\")] if model else []) + [
        "/maintenance", flags, "/scriptpath", wrapper.replace("/", "\\")]
    t0 = time.time()
    p = subprocess.Popen(cmd)
    try:
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(p.pid)
        print(f"[fs.py] TIMEOUT after {timeout}s (endless model or script)", file=sys.stderr)
    dt = time.time() - t0
    st = open(status, encoding="utf-8", errors="replace").read() if os.path.exists(status) else ""
    if "finished" not in st:
        print(f"[fs.py] wrapper status: {st.strip() or 'never started'}", file=sys.stderr)
    if not os.path.exists(out):
        print(f"[fs.py] no output after {dt:.0f}s: the script did not compile, or failed before fileclose()",
              file=sys.stderr)
        return None
    if not quiet:
        print(f"[fs.py] done in {dt:.0f}s", file=sys.stderr)
    return open(out, encoding="utf-8", errors="replace").read()


def seed_list(text):
    """'1-20' or '1,3,5' or '1-5,9' -> [1, 2, ...]"""
    seeds = []
    for part in str(text).split(","):
        a, _, b = part.partition("-")
        seeds += list(range(int(a), int(b or a) + 1))
    return seeds


def run_jobs(model, script_path, jobs_params, jobs=DEFAULT_JOBS, timeout=300, gui=False, work=None, on_done=None):
    """Run one FlexSim per params dict, `jobs` at the same time, each in its own folder <work>/j<n>.
    on_done(params, text_or_None) is called after each run. Returns the list of texts (None = failed)."""
    from concurrent.futures import ThreadPoolExecutor
    import queue
    base = (work or WORK).replace("\\", "/")
    folders = queue.Queue()
    for j in range(1, jobs + 1):
        folders.put(f"{base}/j{j}")

    def one(params):
        w = folders.get()
        try:
            res = run(model, script_path, gui, timeout, params, work=w, quiet=True)
            if on_done:
                on_done(params, res)
            return res
        finally:
            folders.put(w)

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        return list(ex.map(one, jobs_params))


def run_reps(model, script_path, seeds, jobs, hours, outdir, timeout, gui=False, work=None):
    """One FlexSim per seed; output in <outdir>/out_<seed>.txt. Seeds with an output file are skipped."""
    os.makedirs(outdir, exist_ok=True)
    todo = [s for s in seeds if not os.path.exists(os.path.join(outdir, f"out_{s}.txt"))]
    if len(todo) < len(seeds):
        print(f"[fs.py] {len(seeds) - len(todo)} seeds have output already: skipped", flush=True)
    t0 = time.time()

    def done(params, res):
        seed = params["SEED"]
        if res is None:
            print(f"[fs.py] seed {seed}: FAILED", flush=True)
            return
        open(os.path.join(outdir, f"out_{seed}.txt"), "w", encoding="utf-8").write(res)
        print(f"[fs.py] seed {seed}: done", flush=True)

    res = run_jobs(model, script_path, [{"SEED": s, "HOURS": hours} for s in todo], jobs, timeout, gui, work, done)
    ok = sum(r is not None for r in res)
    print(f"[fs.py] reps: {ok}/{len(todo)} ok in {time.time() - t0:.0f}s, {jobs} jobs -> {outdir}", flush=True)
    return ok == len(todo)


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, model = argv[1], argv[2]
    gui = "--gui" in argv
    arg = lambda k, d: argv[argv.index(k) + 1] if k in argv else d
    timeout = int(arg("--timeout", 300))
    if cmd == "run":
        res = run(model, argv[3], gui, timeout)
    elif cmd == "new":
        res = run(None, model, gui, timeout)
    elif cmd == "summary":
        res = run(model, os.path.join(HERE, "scripts", "summary.fs"), gui, timeout)
    elif cmd == "dump":
        path = argv[3] if len(argv) > 3 and not argv[3].startswith("--") else ""
        res = run(model, os.path.join(HERE, "scripts", "dump.fs"), gui, timeout, {"PATH": path})
    elif cmd == "sim":
        res = run(model, os.path.join(HERE, "scripts", "sim.fs"), gui, timeout,
                  {"HOURS": argv[3], "REPS": int(arg("--reps", 1))})
    elif cmd == "reps":
        pos = [a for i, a in enumerate(argv[3:], 3) if not a.startswith("--") and not argv[i - 1].startswith("--")]
        script = pos[0] if pos else os.path.join(HERE, "scripts", "rep.fs")
        work = arg("--work", None)
        outdir = arg("--outdir", (work or WORK) + "/reps")
        ok = run_reps(model, script, seed_list(arg("--seeds", "1-10")), int(arg("--jobs", DEFAULT_JOBS)),
                      arg("--hours", "40"), outdir, timeout, gui, work)
        return 0 if ok else 1
    else:
        print(__doc__)
        return 2
    if res is None:
        return 1
    sys.stdout.write(res)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
