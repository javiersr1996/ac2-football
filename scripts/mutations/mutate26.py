# Mutation script cited by the record of task 26 (28 mutations) in tasks/todo.md.
# Archived as it was written, from a session scratchpad; not run by pytest or CI (the
# name does not start with test_ and tests/ is the only testpath).
# How to run: `python scripts/mutations/mutate26.py [substring ...]`; works on a COPY of the tree,
#   as mutate25.py.

"""Mutations of task 26, each applied to a COPY of the tree (the working tree is never touched).

Usage: python mutate26.py [substring ...]  (all mutations without arguments).
Writes mutate26.log next to this file. A mutation is killed when the pytest run on the copy
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
TESTS = [
    "tests/test_amputate.py",
    "tests/test_layer2_check.py",
    "tests/test_reliability_table.py",
    "tests/test_reliability_metrics.py",
]

AMP = "src/ac2fb/reliability/amputate.py"
MET = "src/ac2fb/reliability/metrics.py"
TAB = "src/ac2fb/reliability/table.py"
REP = "src/ac2fb/reliability/report.py"
CLI = "src/ac2fb/cli.py"

# name: (file, old text, new text, which occurrence of old text, 0-based)
MUTATIONS = {
    # the fill
    "fill holds the last detected position": (
        AMP,
        "x[row, inside] = e.lo_x + w * (e.hi_x - e.lo_x)",
        "x[row, inside] = e.lo_x",
        0,
    ),
    "fill leaves the hidden frames detected": (AMP, "detected[row, inside] = False", "pass", 0),
    "error with the sign flipped": (
        AMP,
        "errors.append(filled.value - seen.value)",
        "errors.append(seen.value - filled.value)",
        0,
    ),
    # the ends
    "ends stay where the gap was put (no move out)": (
        AMP,
        "lo = int(before[lo]) if lo >= 0 and match.player[lo] == player else -1",
        "lo = lo if lo >= 0 and match.player[lo] == player else -1",
        0,
    ),
    "ends cross the break between periods": (
        AMP,
        "not match.period[lo] == match.period[here] == match.period[hi]",
        "False",
        0,
    ),
    # the hiding
    "hiding probability is the detected share": (
        AMP,
        "probability.append(int(gone[in_bin].sum()) / n if n else 0.0)",
        "probability.append(int((~gone[in_bin]).sum()) / n if n else 0.0)",
        0,
    ),
    "pool keeps the open gaps": (
        AMP,
        "closed = gone & (before[rows] >= 0) & (after[rows] >= 0)",
        "closed = gone & ((before[rows] >= 0) | (after[rows] >= 0))",
        0,
    ),
    "pool keeps every sampled frame": (
        AMP,
        "closed = gone & (before[rows] >= 0) & (after[rows] >= 0)",
        "closed = (before[rows] >= 0) & (after[rows] >= 0)",
        0,
    ),
    "hidden when the draw is above the probability": (
        AMP,
        "if rng.random() >= hide.probability[k]",
        "if rng.random() < hide.probability[k]",
        0,
    ),
    # the units and the bands
    "unit binned by its shortest gap": (AMP, "longest = max(", "longest = min(", 0),
    "every V0 unit amputated, not only V1": (
        AMP,
        "if data is None or seen is None or not _whole(data, seen):",
        "if data is None or seen is None:",
        0,
    ),
    "a unit without the ball at t is not skipped": (
        AMP,
        "if ball >= len(match.ball_frame) or match.ball_frame[ball] != t:",
        "if ball >= len(match.ball_frame):",
        0,
    ),
    # the draws
    "one stream for every match (seed without the match)": (
        AMP,
        "np.random.default_rng([SEED, match_id, metrics.METRICS.index(name)])",
        "np.random.default_rng([SEED, metrics.METRICS.index(name)])",
        0,
    ),
    "every metric on the stream of the first": (
        AMP,
        "np.random.default_rng([SEED, match_id, metrics.METRICS.index(name)])",
        "np.random.default_rng([SEED, match_id, 0])",
        0,
    ),
    # the strata of the reaction
    "direction without the attack sign": (
        MET,
        "dx = sign * float(match.ball_x[rows[1]] - match.ball_x[rows[0]])",
        "dx = float(match.ball_x[rows[1]] - match.ball_x[rows[0]])",
        0,
    ),
    "direction without the tolerance at its cut": (
        MET,
        "cut = BACKWARD_CUT + TIE",
        "cut = BACKWARD_CUT",
        0,
    ),
    "direction across the break between periods": (
        MET,
        "        or match.ball_period[rows[0]] != match.ball_period[rows[1]]\n",
        "",
        0,
    ),
    "each stratum given every unit": (
        TAB,
        "rows += _rows(name, direction, sensitivity(metric, long, part)[match_id])",
        "rows += _rows(name, direction, sensitivity(metric, long, windows)[match_id])",
        0,
    ),
    # the CSV check (shared) and writer
    "check_csv compares one column fewer": (
        TAB,
        "for column, ours, theirs in zip(columns, row, disk[k], strict=True):",
        "for column, ours, theirs in zip(columns[:-1], row, disk[k], strict=False):",
        0,
    ),
    "check_csv does not see a missing row": (
        TAB,
        "problems += [f\"missing from the file: {'/'.join(k)}\" for k in code if k not in disk]",
        "problems += []",
        0,
    ),
    "writer with CRLF": (TAB, 'lineterminator="\\n"', 'lineterminator="\\r\\n"', 0),
    "amputation command exits 0 on a failed check": (
        CLI,
        "return 0 if result.ok else 1\n\n\ndef _status",
        "return 0\n\n\ndef _status",
        0,
    ),
    # the layer2 check
    "layer2 check compares only the numbers": (
        REP,
        "    else:\n        return {prefix: node}",
        "    else:\n        keep = isinstance(node, int | float) and not isinstance(node, bool)\n"
        "        return {prefix: node} if keep else {}",
        0,
    ),
    "layer2 check ignores a missing value": (
        REP,
        'problems += [f"missing from the file: {p}" for p in code if p not in disk]',
        "problems += []",
        0,
    ),
    "layer2 check ignores a carriage return": (
        REP,
        'problems = ["the file has a carriage return"] if b"\\r" in raw else []',
        "problems: list[str] = []",
        0,
    ),
    "layer2 check accepts another rendering": (
        REP,
        'if not problems and raw.decode("utf-8") != fresh:',
        "if False:",
        0,
    ),
    "layer2 --check writes the long Parquet": (
        CLI,
        "            result = report.check(ids, _committed(reports_dir / report.REPORT_NAME))",
        "            write_long(ids)\n"
        "            result = report.check(ids, _committed(reports_dir / report.REPORT_NAME))",
        0,
    ),
    "layer2 --check does not say how much it verified": (
        CLI,
        'print(f"verified: {result.values} values, {result.matches} matches")',
        'print("verified")',
        0,
    ),
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
        last = out.strip().splitlines()[-1]
        line = f"{'KILLED' if code else 'SURVIVED'}: {name} | {last} | {', '.join(failing[:2])}"
        log.append(line)
        print(line, flush=True)
    log.append(f"TOTAL: {killed} of {len(chosen)} killed")
    print(log[-1])
    suffix = "_" + "_".join(only) if only else ""
    (HERE / f"mutate26{suffix}.log").write_text("\n".join(log) + "\n", encoding="utf-8")


main()
