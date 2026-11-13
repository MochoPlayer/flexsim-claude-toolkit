"""Look up FlexScript commands in FlexSim's local help (Commands.xml).

Usage:
  python -I -X utf8 cmdref.py <name> [<name> ...]     full entry for exact command names
  python -I -X utf8 cmdref.py --grep <regex>          list command names matching regex
Class API (Object, Table, Model...): grep the XML files in
  <FlexSim folder>/help/FlexScriptAPIReference/<Group>/<Class>.xml
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fs  # noqa: E402  (finds flexsim.exe; the help folder is next to program/)

XML = os.path.join(os.path.dirname(os.path.dirname(fs.EXE)), "help", "CommandReference", "Commands.xml")


def main(argv):
    x = open(XML, encoding="utf-8-sig").read()
    blocks = re.findall(r"<command>(.*?)</command>", x, re.S)
    if len(argv) > 2 and argv[1] == "--grep":
        rx = re.compile(argv[2], re.I)
        names = [re.search(r"<name>(.*?)</name>", b).group(1) for b in blocks if "<name>" in b]
        print(" ".join(n for n in names if rx.search(n)))
        return 0
    for name in argv[1:]:
        hit = [b for b in blocks if re.search(r"<name>" + re.escape(name) + r"</name>", b)]
        if not hit:
            print(f"===== {name}: not found")
            continue
        text = re.sub(r"<[^>]+>", " ", hit[0])
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text).strip()
        print(f"===== {name}\n{text[:2500]}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
