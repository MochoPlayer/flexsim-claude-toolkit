"""Export FlexSim's own dashboard charts to PNG, any model, in ONE FlexSim session.

Run:
  python -I -X utf8 dashboard_png.py <model.fsm> <charts.fs> --out <dir> [--hours 5] [--only a,b] [--timeout 600] [--stall 60]

charts.fs: FlexScript in blocks. Each block starts with a marker line:
  //@setup                     optional, runs once before the charts (for example label or stop-trigger patches)
  //@chart <name> [w h]        one chart; <name> becomes <name>.png; size in logical px (default 420 370)
{{LOG}} in the code = the progress log (fileopen("{{LOG}}","a"); fpt("x"); fpr(); fileclose();).
In a chart block the variable `dash` is the one export dashboard. The block makes ONE chart on it:
  treenode ch = function_s(dash, "createGraphWindow", maintree().find("project/exec/globals/ChartTemplateDefinitions/State/StateBar"), 1, 420, 370);
  ... replacements ...; function_s(ch, "onApply");
Example for any model: charts_example.fs (next to this file).

How it works:
1. FlexSim starts WITH its window (charts are HTML in an embedded browser; no window = no image) on a copy of
   the model in <FLEXSIM_WORK>/../charts (no hyphens: FlexSim cuts /scriptpath at the first hyphen).
2. The script builds all charts on one dashboard, runs the model once to --hours, then ONE repeating 3 s timer
   shows the charts one by one (chart k at (4,4), the others moved out of view), waits 9 s for the browser to
   draw, and writes a "ready" line.
3. Python captures the graph panel with Win32 PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT=2). This works with
   FlexSim behind other windows (not minimised). Never viewtofile(): it is a screen grab, black when the window is behind.
4. Fail fast: a capture with < 5 % non-black pixels, or the same image as an earlier chart, stops the whole
   export with exit code 2. No new log line for --stall seconds (outside the model run) stops it with exit code 3.
   --timeout (whole job) stops it with exit code 3.
5. Closes only the FlexSim it started (process tree). Your own FlexSim windows stay open.
Never overwrites: a PNG that exists in --out is skipped. Test with --hours 5 (about 1 min); full horizon only for the final export.
"""
import ctypes
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "flexsim"))
import fs  # noqa: E402

D = fs.WORK.rsplit("/", 1)[0] + "/charts"
EXE = fs.EXE
FF = os.path.join(os.path.dirname(EXE), "ffmpeg", "ffmpeg.exe")  # FlexSim ships ffmpeg; used to crop
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
MIN_LIT = 0.05

u = ctypes.windll.user32
g = ctypes.windll.gdi32
try:
    u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2: rectangles in physical pixels
except Exception:
    pass
ENUM = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

# One repeating 3 s timer on the dashboard drives everything (tested 12 Nov: FlexSim timers repeat, a timer on a
# second dashboard did not fire, makeactive() did not change the front tab). Step s: chart k = s / 5 + 1,
# phase s % 5: 0 = show chart k, 3 = (9 s later) write its ready line. After the last chart: ALLDONE.
TIMER = r'''int s = getvarnum(c, "step");
int n = getvarnum(c, "nwins");
int k = Math.floor(s / 5) + 1;
int ph = s % 5;
setvarnum(c, "step", s + 1);
if (k > n) {
	if (ph == 0) { fileopen("{{DONE}}", "a"); fpt("ALLDONE"); fpr(); fileclose(); }
	return 0;
}
treenode wg = tonode(getvarnum(c, "w" + string.fromNum(k)));
treenode gp = node("GraphPanel", c);
if (ph == 0) {
	for (int j = 1; j <= n; j++) { treenode o = tonode(getvarnum(c, "w" + string.fromNum(j))); set(spatialx(o), j == k ? 4 : 5000); refreshview(o); }
	refreshview(gp);
	fileopen("{{LOG}}", "a"); fpt("show " + string.fromNum(k)); fpr(); fileclose();
}
if (ph == 3) {
	function_s(wg, "hideSizers");
	fileopen("{{DONE}}", "a");
	fpt(getvarstr(c, "png" + string.fromNum(k)) + "|" + string.fromNum(get(spatialsx(gp))) + "|" + string.fromNum(get(spatialsy(gp))) + "|" + string.fromNum(get(spatialx(wg))) + "|" + string.fromNum(get(spatialy(wg))) + "|" + string.fromNum(get(spatialsx(wg))) + "|" + string.fromNum(get(spatialsy(wg))));
	fpr(); fileclose();
}'''


def say(msg):
    print(msg, flush=True)


def fs_str(code):
    return '"' + code.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", " ") + '"'


def parse_charts(path):
    """charts.fs -> (setup code, [(name, w, h, code)])."""
    setup, charts, cur = [], [], None
    for line in open(path, encoding="utf-8").read().splitlines():
        m = re.match(r"\s*//@(setup|chart)\b\s*(.*)", line)
        if m:
            if m.group(1) == "setup":
                cur = setup
            else:
                parts = m.group(2).split()
                if not parts:
                    sys.exit(f"{path}: //@chart needs a name")
                w, h = (int(parts[1]), int(parts[2])) if len(parts) >= 3 else (420, 370)
                charts.append((parts[0], w, h, []))
                cur = charts[-1][3]
            continue
        if cur is not None:
            cur.append(line)
    return "\n".join(setup), [(n, w, h, "\n".join(c)) for n, w, h, c in charts]


def log_line(log, text):
    return f'fileopen("{log}", "a"); fpt({fs_str(text)}); fpr(); fileclose();'


def build_script(setup, charts, sim_s, log, done):
    setup = setup.replace("{{LOG}}", log)  # chart code may write progress lines to {{LOG}}
    charts = [(n, w, h, c.replace("{{LOG}}", log)) for n, w, h, c in charts]
    s = [f'fileopen("{log}", "w"); fpt("export start"); fpr(); fileclose();']
    if setup.strip():
        s += ["{", setup, "}", log_line(log, "setup done")]
    s += ["windowmove(systemwindow(8), 0, 0, 1920, 1160, 1);",
          'treenode dash = applicationcommand("adddashboard");',
          'setname(model().find("Tools/Dashboards").last, "Export");',
          # the docked dashboard pane is narrow (about 390 px); a wider chart is cut by the Properties pane.
          # Widening the pane by script did not work (13 Nov 2026), so each chart width is capped to the visible part.
          "double VIS = get(spatialsx(dash)) - 24;",
          "Array charts = [];"]
    for name, w, h, code in charts:
        s += ["{", code, "}",
              '{ treenode wg = dash.find("GraphPanel").last;',
              f"set(spatialx(wg), 4); set(spatialy(wg), 4); set(spatialsx(wg), Math.min({w}, VIS)); set(spatialsy(wg), {h}); refreshview(wg);",
              "charts.push(wg);",
              f'setnodestr(assertvariable(dash, "png" + string.fromNum(charts.length), DATATYPE_STRING), "{name}"); }}',
              log_line(log, f"chart built {name}")]
    timer = TIMER.replace("{{DONE}}", done).replace("{{LOG}}", log)
    s += ['treenode ef = dash.find(">eventfunctions/OnTimerEvent");',
          f"setnodestr(ef, {fs_str(timer)}); buildnodeflexscript(ef);",
          'setnodenum(assertvariable(dash, "step", DATATYPE_NUMBER), 0);',
          'setnodenum(assertvariable(dash, "nwins", DATATYPE_NUMBER), charts.length);',
          'for (int k = 1; k <= charts.length; k++) setnodenum(assertvariable(dash, "w" + string.fromNum(k), DATATYPE_NUMBER), tonum(charts[k]));',
          log_line(log, "running"),
          f"double STOP = convert(getmodelunit(START_TIME) + {sim_s}, FS_DATETIME, MODEL_TIME);",
          "resetmodel(); stoptime(STOP); runfunction(1);",
          f'fileopen("{log}", "a"); fpt("ran t=" + string.fromNum(time())); fpr(); fileclose();',
          'applicationcommand("settimer", dash, 3000);',
          log_line(log, "timer chain started")]
    return "\n".join(s) + "\n"


def rect(h):
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def main_window(pid):
    found = []

    def cb(h, _):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        t = ctypes.create_unicode_buffer(300)
        u.GetWindowTextW(h, t, 300)
        if p.value == pid and u.IsWindowVisible(h) and "FlexSim" in t.value:
            found.append(h)
        return True
    u.EnumWindows(ENUM(cb), 0)
    return found[0] if found else None


def children(h):
    out = []

    def cb(c, _):
        if u.IsWindowVisible(c):
            out.append((c, rect(c)))
        return True
    u.EnumChildWindows(h, ENUM(cb), 0)
    return out


def print_window(h, bmp_path):
    """Window -> 32-bit BMP file. Returns (PrintWindow result, share of non-black pixels)."""
    _, _, w, hh = rect(h)
    sdc = u.GetDC(0)
    mdc = g.CreateCompatibleDC(sdc)
    bmp = g.CreateCompatibleBitmap(sdc, w, hh)
    g.SelectObject(mdc, bmp)
    ok = u.PrintWindow(h, mdc, 2)  # PW_RENDERFULLCONTENT
    hdr = struct.pack("<IiiHHIIiiII", 40, w, -hh, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * hh * 4)
    bi = ctypes.create_string_buffer(hdr, 40 + 12)
    g.GetDIBits(mdc, bmp, 0, hh, buf, bi, 0)
    g.DeleteObject(bmp)
    g.DeleteDC(mdc)
    u.ReleaseDC(0, sdc)
    data = buf.raw
    with open(bmp_path, "wb") as f:
        f.write(b"BM" + struct.pack("<IHHI", 54 + len(data), 0, 0, 54) + hdr + data)
    step = max(4, (len(data) // 4 // 20000) * 4)
    sample = [data[i:i + 3] for i in range(0, len(data), step)]
    lit = sum(1 for p in sample if p != b"\x00\x00\x00") / max(1, len(sample))
    return ok, lit


class ExportError(Exception):
    pass


def capture(h, line):
    """Capture the chart named in a ready line -> cropped PNG path. Raises ExportError on a bad capture."""
    f = line.split("|")
    name = f[0]
    s = (u.GetDpiForWindow(h) or 96) / 96
    gw, gh = float(f[1]) * s, float(f[2]) * s
    mx, my, mw, mh = rect(h)
    # the graph panel: same height, width closest to the reported panel width (its width can change with the layout)
    for _ in range(20):  # the layout can still be settling: retry for up to 10 s
        panel = sorted((c for c in children(h) if abs(c[1][3] - gh) <= 30 and abs(c[1][2] - gw) <= max(6, 0.6 * gw)
                        and mx <= c[1][0] < mx + mw), key=lambda c: abs(c[1][2] - gw))
        if panel:
            break
        time.sleep(0.5)
    if not panel:
        near = [c[1] for c in children(h) if abs(c[1][3] - gh) <= 60]
        raise ExportError(f"{name}: no visible graph panel inside the FlexSim window (minimised?). "
                          f"Wanted about {gw:.0f}x{gh:.0f} px; windows of that height: {near[:6]}")
    bmp = f"{D}/pw-{name}.bmp"
    ok, lit = print_window(panel[0][0], bmp)
    if lit < MIN_LIT:
        raise ExportError(f"{name}: capture is black (non-black {lit:.0%}, PrintWindow={ok})")
    x, y, cw, ch = (int(float(v) * s) for v in f[3:7])
    crop = f"{D}/crop-{name}.png"
    if os.path.exists(crop):
        os.remove(crop)
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", bmp, "-vf", f"crop={cw}:{ch}:{x}:{y}", crop],
                   creationflags=NOWIN)
    if not os.path.exists(crop):
        raise ExportError(f"{name}: ffmpeg crop failed")
    say(f"  {name}: saved (non-black {lit:.0%})")
    return crop


def arg(argv, k, d):
    return argv[argv.index(k) + 1] if k in argv else d


def main(argv):
    opts = ("--timeout", "--hours", "--out", "--only", "--stall")
    args = [a for i, a in enumerate(argv[1:], 1) if a not in opts and argv[i - 1] not in opts]
    if len(args) < 2 or "--out" not in argv:
        print(__doc__)
        return 1
    model, charts_fs = args[0], args[1]
    out = arg(argv, "--out", None)
    hours = float(arg(argv, "--hours", 5))
    timeout = int(arg(argv, "--timeout", 600))
    stall = int(arg(argv, "--stall", 60))
    only = [x for x in arg(argv, "--only", "").split(",") if x]
    setup, charts = parse_charts(charts_fs)
    charts = [c for c in charts if (not only or c[0] in only) and not os.path.exists(os.path.join(out, c[0] + ".png"))]
    if not charts:
        say("nothing to do (no charts, or all PNGs exist)")
        return 0
    os.makedirs(out, exist_ok=True)
    os.makedirs(D, exist_ok=True)
    say(f"charts ({len(charts)}): {', '.join(c[0] for c in charts)}; run {hours:g} h")
    log, done = D + "/log.txt", D + "/done.txt"
    for f in (log, done):
        if os.path.exists(f):
            os.remove(f)
    wm = D + "/model_in.fsm"
    shutil.copyfile(model, wm)
    open(D + "/script_run.fs", "w", encoding="utf-8").write(build_script(setup, charts, int(hours * 3600), log, done))
    open(D + "/wrapper.fs", "w", encoding="utf-8").write(
        f'executefsfile("{D}/script_run.fs", 1);\n{log_line(log, "script returned")}\n')
    p = subprocess.Popen([EXE, wm.replace("/", "\\"), "/maintenance", "disablemsg_runscript",
                          "/scriptpath", (D + "/wrapper.fs").replace("/", "\\")])
    t0 = last = time.time()
    seen_done = seen_log = saved = 0
    hashes = {}
    try:
        while True:
            now = time.time()
            if p.poll() is not None:
                raise ExportError(f"FlexSim closed early (exit {p.returncode})")
            if now - t0 > timeout:
                raise TimeoutError(f"timeout {timeout} s")
            loglines = open(log, encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(log) else []
            for l in loglines[seen_log:]:
                say(f"  [{now - t0:4.0f} s] {l}")
                last = now
            seen_log = len(loglines)
            running = bool(loglines) and loglines[-1] == "running"  # the model run itself writes no lines
            if not running and now - last > stall:
                raise TimeoutError(f"no progress for {stall} s (last line: {loglines[-1] if loglines else 'none'})")
            lines = open(done, encoding="utf-8").read().splitlines() if os.path.exists(done) else []
            for line in lines[seen_done:]:
                last = now
                if line == "ALLDONE":
                    say(f"done in {time.time() - t0:.0f} s: {saved}/{len(charts)} PNGs in {out}")
                    return 0
                h = main_window(p.pid)
                if not h:
                    raise ExportError("FlexSim window not found")
                crop = capture(h, line)
                md5 = hashlib.md5(open(crop, "rb").read()).hexdigest()
                name = line.split("|")[0]
                if md5 in hashes:
                    raise ExportError(f"{name}: same image as {hashes[md5]} (chart did not change)")
                hashes[md5] = name
                shutil.copyfile(crop, os.path.join(out, name + ".png"))
                saved += 1
            seen_done = len(lines)
            time.sleep(0.3)
    except ExportError as e:
        say(f"STOPPED (bad output): {e}. Saved {saved}/{len(charts)}.")
        return 2
    except TimeoutError as e:
        say(f"STOPPED: {e}. Saved {saved}/{len(charts)}. Log: {' | '.join(open(log, encoding='utf-8', errors='replace').read().splitlines()[-5:]) if os.path.exists(log) else 'none'}")
        return 3
    finally:
        # close only the FlexSim this script started (and its child processes)
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, creationflags=NOWIN)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
