# Mutation script cited by the record of task 27 (18 mutations of the figures) in tasks/todo.md.
# Archived as it was written, from a session scratchpad; not run by pytest or CI (the
# name does not start with test_ and tests/ is the only testpath).
# How to run: `python scripts/mutations/mutate27.py`; plants faults in a COPY of the tree, redraws
#   the figures there and runs tests/test_figures.py.

"""Plant faults in a COPY of the tree, redraw the committed figures there, run tests/test_figures.py.

Usage: python mutate27.py  (from anywhere). The real tree is only read.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REAL = Path(r"C:\Users\javie\Desktop\proyectos\ac2-football")
WORK = Path(r"C:\Users\javie\AppData\Local\Temp\claude\C--Users-javie-Desktop-proyectos-ac2-football\c4e76610-7b6e-4b56-9286-04e4ae87873c\scratchpad\tree27")
PY = str(REAL / ".venv" / "Scripts" / "python.exe")

MUTATIONS = [
    # (name, file, old, new, redraw)
    ("label number printed off by 0.001", "figures.py", 'f"{value:.{decimals}f}"', 'f"{value + 0.001:.{decimals}f}"', True),
    ("D3 floor rounded to 2 decimals", "figures.py", '"D3 floor {0}", ("value", [floor], 3)', '"D3 floor {0}", ("value", [floor], 2)', True),
    ("floor label drawn but not in the sidecar", "figures.py", '"labels": [l_floor, l_v2, verdict[1], bar[1], empty[1]]', '"labels": [l_v2, verdict[1], bar[1], empty[1]]', True),
    ("typed 10 in the calibration label", "figures.py", '    t_cal, l_cal = _label(rep, "calibration, {0} matches", ("count", ["layer2.json#matches"], 0))', '    t_cal, l_cal = _label(rep, "calibration, 10 matches")', True),
    ("panel b reads the wrong column", "figures.py", '"reacquisition/by_band/{}/frame_share"', '"reacquisition/by_band/{}/jump_median"', True),
    ("panel d reads the p90 not the mean", "figures.py", 'column="mean_abs_error"', 'column="p90_abs_error"', True),
    ("panel c reads stratum backward", "figures.py", 'where = {"match_id": m, "metric": metric, "ball_stratum": "all"}', 'where = {"match_id": m, "metric": metric, "ball_stratum": "backward"}', True),
    ("thick line is the mean, not the median", "figures.py", 'return round(statistics.median(values), 9)', 'return round(statistics.fmean(values), 9)', True),
    ("V1 plotted from V0 effect", "figures.py", '"V1": "variants/V1"', '"V1": "variants/V0"', True),
    ("held-out half read from the calibration file", "figures.py", 'PREFIX = {CAL: "", HELD: "heldout/"}', 'PREFIX = {CAL: "", HELD: ""}', True),
    ("sidecar written with CRLF", "figures.py", 'ensure_ascii=False) + "\\n").encode()', 'ensure_ascii=False) + "\\n").replace("\\n", "\\r\\n").encode()', True),
    ("check ignores the SVG", "figures.py", 'for name in OUTPUTS:\n        old = committed.get(name)', 'for name in OUTPUTS:\n        if name.endswith(".svg"):\n            continue\n        old = committed.get(name)', False),
    ("check exits 0 on a difference", "cli.py", 'return 0 if result.ok else 1\n\n\ndef _status', 'return 0\n\n\ndef _status', False),
    ("check also writes the files", "cli.py", '    result = figures.check(files, {name: _committed(out_dir / name) for name in figures.OUTPUTS})', '    for name, content in figures.build(files).files.items():\n        (out_dir / name).write_bytes(content)\n    result = figures.check(files, {name: _committed(out_dir / name) for name in figures.OUTPUTS})', False),
    ("check does not say how much it verified", "cli.py", 'f"verified: {result.files} files, {result.points} plotted values and {result.labels} "', 'f"verified: {result.files} files, 0 plotted values and {result.labels} "', False),
    ("a held-out match dropped from the lines", "figures.py", 'return sorted(rep.json(f"{PREFIX[group]}layer2.json")["matches"])', 'return sorted(rep.json(f"{PREFIX[group]}layer2.json")["matches"])[:9 if group == HELD else 10]', True),
    ("hash salt moved by the clock", "figures.py", '"svg.hashsalt": "ac2fb-figures"', '"svg.hashsalt": __import__("time").strftime("%H%M%S")', False),
    ("diamond marker for the held-out half (portability)", "figures.py", 'MARKER = {CAL: "o", HELD: "s"}', 'MARKER = {CAL: "o", HELD: "D"}', True),
]


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=str(WORK / "src"), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(args, cwd=WORK, env=env, capture_output=True, text=True)


def main() -> None:
    only = sys.argv[1:]
    if WORK.exists():
        shutil.rmtree(WORK)
    ignore = shutil.ignore_patterns(".venv", ".git", "data", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")
    shutil.copytree(REAL, WORK, ignore=ignore)
    pristine = {f: (WORK / "src" / "ac2fb" / f).read_text(encoding="utf-8") for f in ("figures.py", "cli.py")}
    figures_dir = WORK / "reports" / "figures"
    committed = {p.name: p.read_bytes() for p in figures_dir.iterdir()}
    base = run([PY, "-m", "pytest", "tests/test_figures.py", "-q", "-x", "-p", "no:cacheprovider"])
    print("baseline:", base.stdout.strip().splitlines()[-1], flush=True)
    for name, file, old, new, redraw in MUTATIONS:
        if only and not any(o in name for o in only):
            continue
        path = WORK / "src" / "ac2fb" / file
        text = pristine[file]
        assert text.count(old) == 1, f"{name}: {text.count(old)} matches"
        for f, t in pristine.items():
            (WORK / "src" / "ac2fb" / f).write_text(t, encoding="utf-8", newline="\n")
        for n, b in committed.items():
            (figures_dir / n).write_bytes(b)
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
        if redraw:
            drawn = run([PY, "-m", "ac2fb.cli", "figures"])
            if drawn.returncode != 0:
                print(f"{name}: REDRAW FAILED {drawn.stderr.strip().splitlines()[-1:]}", flush=True)
                continue
        result = run([PY, "-m", "pytest", "tests/test_figures.py", "-q", "-p", "no:cacheprovider"])
        tail = result.stdout.strip().splitlines()
        failed = [ln.split("::")[1].split(" ")[0] for ln in tail if ln.startswith("FAILED")]
        verdict = "CAUGHT" if result.returncode != 0 else "SURVIVED"
        print(f"{verdict}: {name} -> {len(failed)} failing: {', '.join(sorted(set(f.split('[')[0] for f in failed)))[:150]}", flush=True)


main()
