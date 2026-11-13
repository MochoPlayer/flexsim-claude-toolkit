"""Find the first statement of a FlexScript file that does not compile or stops the script.

FlexSim skips a script with a compile error and says nothing. This tool runs shorter and shorter
prefixes of the script, each with a marker line at the end, and does a binary search for the first
prefix whose marker never appears.

Usage:
  python -I -X utf8 bisect.py <model.fsm> <script.fs> [--param KEY=VALUE ...] [--timeout 60]

  --param  fills {{KEY}} in the script (for scripts made for `fs.py reps`, e.g. --param SEED=1 --param HOURS=1)
Cut points are top-level lines (not inside { }), so an error inside a block reports the whole block.
Exit code: 0 = the whole script runs, 1 = a failing statement was found.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "flexsim"))
import fs  # noqa: E402

MARK = "BISECT_OK"


def cut_points(lines):
    """Line counts after which the brace depth is 0 (a whole statement or block ends there)."""
    depth, pts = 0, []
    for i, line in enumerate(lines):
        code = line.split("//", 1)[0]
        depth += code.count("{") - code.count("}")
        if depth == 0 and code.strip():
            pts.append(i + 1)
    return pts


def runs_to(model, lines, n, params, timeout, work):
    """True if the first n lines compile and run up to the marker."""
    os.makedirs(work, exist_ok=True)
    part = work + "/bisect_part.fs"
    with open(part, "w", encoding="utf-8") as f:
        f.write("\n".join(lines[:n]) + f'\nfileopen("{{{{OUT}}}}", "a"); fpt("{MARK}"); fpr(); fileclose();\n')
    out = fs.run(model, part, timeout=timeout, params=params, work=work + "/run", quiet=True)
    return out is not None and MARK in out


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    model, script = argv[1], argv[2]
    params = dict(a.split("=", 1) for i, a in enumerate(argv) if i > 0 and argv[i - 1] == "--param")
    timeout = int(argv[argv.index("--timeout") + 1]) if "--timeout" in argv else 60
    work = fs.WORK.rsplit("/", 1)[0] + "/bisect"
    lines = open(script, encoding="utf-8").read().splitlines()
    pts = cut_points(lines)
    if not pts:
        print("no statements found")
        return 2
    print(f"{len(pts)} top-level statements; about {max(1, len(pts)).bit_length() + 1} FlexSim runs", flush=True)
    if runs_to(model, lines, pts[-1], params, timeout, work):
        print("whole script compiles and runs to the end")
        return 0
    if not runs_to(model, lines, pts[0], params, timeout, work):
        print(f"first failing statement: lines 1-{pts[0]}")
        for line in lines[:pts[0]]:
            print("   ", line[:600])
        return 1
    lo, hi = 0, len(pts) - 1  # prefix pts[lo] runs, prefix pts[hi] fails
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if runs_to(model, lines, pts[mid], params, timeout, work):
            lo = mid
        else:
            hi = mid
        print(f"  ok up to line {pts[lo]}, fails by line {pts[hi]}", flush=True)
    print(f"first failing statement: lines {pts[lo] + 1}-{pts[hi]}")
    for line in lines[pts[lo]:pts[hi]]:
        print("   ", line[:600])
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
