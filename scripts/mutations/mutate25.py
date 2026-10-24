# Mutation script cited by the record of task 25 (38 mutations) in tasks/todo.md.
# Archived as it was written, from a session scratchpad; not run by pytest or CI (the
# name does not start with test_ and tests/ is the only testpath).
# How to run: `python scripts/mutations/mutate25.py [substring ...]`; works on a COPY of the tree
#   under a `work` directory next to the script; REPO and PY point at this repository.

"""Mutations of task 25, each applied to a COPY of the tree (the working tree is never touched).

Usage: python mutate25.py [substring ...]  (all mutations without arguments).
Writes mutate25.log next to this file. A mutation is killed when the pytest run on the copy
fails; the failing tests are listed. The baseline (unmutated copy) must pass first.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\javie\Desktop\proyectos\ac2-football")
HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
PY = REPO / ".venv" / "Scripts" / "python.exe"
TESTS = ["tests/test_reliability_metrics.py", "tests/test_reliability_table.py"]

PRESS = "src/ac2fb/defence/pressure.py"
MET = "src/ac2fb/reliability/metrics.py"
TAB = "src/ac2fb/reliability/table.py"
CLI = "src/ac2fb/cli.py"
SENS = "src/ac2fb/reliability/sensitivity.py"

SIGN = "match.attack_sign.get((r.period, r.team))"
SIGN_E = "match.attack_sign.get((e.period, int(e.team or 0)))"
STABLE = 'np.argsort(-(window.x[outfield, -1] * sign), kind="stable")'

# name: (file, old text, new text, which occurrence of old text, 0-based)
MUTATIONS = {
    # the two pending of review 22 (sign of period 1 always, no sign) and the team, on make_metric
    "make_metric: sign of period 1 always": (PRESS, SIGN, "match.attack_sign.get((1, r.team))", 1),
    "make_metric: no sign (always +1)": (PRESS, "sign = " + SIGN, "sign = 1", 1),
    "make_metric: sign of team 1 always": (PRESS, SIGN, "match.attack_sign.get((r.period, 1))", 1),
    # the same three on each new reader of attack_sign
    "pressure_index: sign of period 1 always": (MET, SIGN_E, "match.attack_sign.get((1, int(e.team or 0)))", 0),
    "pressure_index: no sign (always +1)": (MET, "sign = " + SIGN_E, "sign = 1", 0),
    "pressure_index: sign of team 1 always": (MET, SIGN_E, "match.attack_sign.get((e.period, 1))", 0),
    "line: sign of period 1 always": (MET, SIGN_E, "match.attack_sign.get((1, int(e.team or 0)))", 1),
    "line: no sign (always +1)": (MET, "sign = " + SIGN_E, "sign = 1", 1),
    "line: sign of team 1 always": (MET, SIGN_E, "match.attack_sign.get((e.period, 1))", 1),
    # is_detected
    "sensitivity ignores is_detected (V1 = V0)": (
        SENS,
        '"detected": keep["is_detected"].to_numpy(zero_copy_only=False).astype(np.bool_)[order],',
        '"detected": np.ones(len(order), dtype=np.bool_),',
        0,
    ),
    "line metric reports no players": (
        MET,
        "return Reading(height, tuple(int(p) for p in window.player_ids[line]))",
        "return Reading(height, ())",
        0,
    ),
    "pressure_index reports no players": (
        MET,
        "return Reading(float(weights.sum()), tuple(int(p) for p in window.player_ids[rivals][near]))",
        "return Reading(float(weights.sum()), ())",
        0,
    ),
    "block reports no players": (MET, "return Reading(value, tuple(sorted(set(fixers))))", "return Reading(value, ())", 0),
    # the near cut
    "make_metric: near = weights > 0": (PRESS, "near = weights > NEAR_WEIGHT", "near = weights > 0", 1),
    "score_receptions: near = weights > 0": (PRESS, "near = weights > NEAR_WEIGHT", "near = weights > 0", 0),
    "pressure_index: near = weights > 0": (MET, "near = weights > NEAR_WEIGHT", "near = weights > 0", 0),
    "tolerance as large as a real weight (1e-9)": (MET, "NEAR_WEIGHT = 1e-12", "NEAR_WEIGHT = 1e-9", 0),
    # the line
    "line keeps the goalkeeper": (MET, "outfield = rivals[window.player_ids[rivals] != keeper]", "outfield = rivals", 0),
    "line ranks by x without the sign": (MET, STABLE, 'np.argsort(-window.x[outfield, -1], kind="stable")', 0),
    "line takes the shallowest four": (MET, STABLE, 'np.argsort(window.x[outfield, -1] * sign, kind="stable")', 0),
    "reaction does not need the line at t - W": (MET, "if not window.present[line, 0].all():", "if False:", 0),
    "reaction subtracts a height without the sign": (
        MET,
        "height -= float(np.mean(window.x[line, 0] * sign))",
        "height -= float(np.mean(window.x[line, 0]))",
        0,
    ),
    # the block
    "block of four players is a block": (MET, "MIN_BLOCK = 5", "MIN_BLOCK = 4", 0),
    "block extremes by percentiles": (
        MET,
        "float(values[order[-1]] - values[order[0]])",
        "float(np.percentile(values, 95) - np.percentile(values, 5))",
        0,
    ),
    "block area as the sum": (MET, "Reading(width[0] * length[0],", "Reading(width[0] + length[0],", 0),
    "block ties: second of the lowest": (
        MET,
        "[int(ids[order[0]]), int(ids[order[-1]])]",
        "[int(ids[order[1]]), int(ids[order[-1]])]",
        0,
    ),
    "nearest rival: the farthest": (MET, "nearest = int(np.argmin(d))", "nearest = int(np.argmax(d))", 0),
    "weights: cos without the half": (MET, "((1.0 + cos) / 2.0)", "(1.0 + cos)", 0),
    # the table and its check
    "check compares no cell": (TAB, "if ours != theirs:", "if False:", 0),
    "check compares only the first four columns": (
        TAB,
        "for column, ours, theirs in zip(COLUMNS, row, disk[k], strict=True):",
        "for column, ours, theirs in list(zip(COLUMNS, row, disk[k], strict=True))[:4]:",
        0,
    ),
    "check stops at the first row": (
        TAB,
        "    for k, row in code.items():\n        if k not in disk:",
        "    for k, row in list(code.items())[:1]:\n        if k not in disk:",
        0,
    ),
    "check ignores a missing row": (
        TAB,
        "problems += [f\"missing from the file: {'/'.join(k)}\" for k in code if k not in disk]",
        "pass",
        0,
    ),
    "check ignores a carriage return": (TAB, 'problems.append("the file has a carriage return")', "pass", 0),
    "check does not count cells": (TAB, "cells += 1\n", "cells += 0\n", 0),
    "writer ends lines with CRLF": (TAB, 'lineterminator="\\n"', 'lineterminator="\\r\\n"', 0),
    "writer leaves NaN": (TAB, "if value is None or (isinstance(value, float) and not math.isfinite(value)):", "if value is None:", 0),
    "command prints no counts": (
        CLI,
        'print(f"verified: {report.rows} rows, {report.cells} cells, {report.matches} matches")',
        'print("verified")',
        0,
    ),
    "command exits 0 on a failed check": (CLI, "return 0 if report.ok else 1\n\n\ndef _status", "return 0\n\n\ndef _status", 0),
}


def nth_replace(text: str, old: str, new: str, n: int) -> str:
    i = -1
    for _ in range(n + 1):
        i = text.index(old, i + 1)  # raises if the pattern is not there enough times
    return text[:i] + new + text[i + len(old) :]


def fresh_copy() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()
    for name in ("src", "tests", "protocol", "reports", "pyproject.toml", "uv.lock"):
        src = REPO / name
        if src.is_dir():
            shutil.copytree(src, WORK / name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy(src, WORK / name)


def run_tests() -> tuple[int, str]:
    env = dict(os.environ, PYTHONPATH=str(WORK / "src"), PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run(
        [str(PY), "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
        cwd=WORK,
        env=env,
        capture_output=True,
        text=True,
    )
    return r.returncode, r.stdout + r.stderr


def main() -> None:
    only = sys.argv[1:]
    fresh_copy()
    code, out = run_tests()
    log = [f"BASELINE (unmutated copy): exit {code}; {out.strip().splitlines()[-1]}"]
    print(log[0], flush=True)
    assert code == 0, out
    chosen = {k: v for k, v in MUTATIONS.items() if not only or any(o in k for o in only)}
    killed = 0
    for name, (rel, old, new, n) in chosen.items():
        path = WORK / rel
        original = path.read_text(encoding="utf-8")
        path.write_text(nth_replace(original, old, new, n), encoding="utf-8", newline="\n")
        code, out = run_tests()
        path.write_text(original, encoding="utf-8", newline="\n")
        failing = re.findall(r"^FAILED (\S+)", out, re.M)
        killed += code != 0
        line = f"{'KILLED' if code else 'SURVIVED'}: {name} | {out.strip().splitlines()[-1]} | {', '.join(failing[:2])}"
        log.append(line)
        print(line, flush=True)
    log.append(f"TOTAL: {killed} of {len(chosen)} killed")
    print(log[-1])
    (HERE / "mutate25.log").write_text("\n".join(log) + "\n", encoding="utf-8")


main()
