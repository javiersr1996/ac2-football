# Mutation script cited by the record of task 23c, front B (same doubt as mutate23c_b.py) in
#   tasks/todo.md.
# Archived as it was written, from a session scratchpad; not run by pytest or CI (the
# name does not start with test_ and tests/ is the only testpath).
# How to run: `python scripts/mutations/mutate23c_b2.py <repository root>`; multi-replacement
#   mutations, with an optional full-calibration CLI check.

"""Multi-replacement mutations; optional full-calibration CLI check."""
import subprocess
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
M = {
    "fill_last_position": [("src/ac2fb/reliability/amputate.py",
        "        x[row, inside] = e.lo_x + w * (e.hi_x - e.lo_x)\n        y[row, inside] = e.lo_y + w * (e.hi_y - e.lo_y)\n",
        "        x[row, inside] = e.lo_x + 0 * w\n        y[row, inside] = e.lo_y + 0 * w\n")],
    "reaction_same_period_fix": [
        ("src/ac2fb/reliability/metrics.py",
         "from ac2fb.reliability.match import Event, MatchData\n",
         "from ac2fb.reliability.match import Event, MatchData, locate_rows\n"),
        ("src/ac2fb/reliability/metrics.py",
         "            if not window.present[line, 0].all():\n                return None\n",
         "            if not window.present[line, 0].all():\n                return None\n"
         "            ids = window.player_ids[line]\n"
         "            now = locate_rows(match, ids, np.full(len(ids), window.window.frame_end))\n"
         "            then = locate_rows(match, ids, np.full(len(ids), window.window.frame_start))\n"
         "            if (match.period[now] != match.period[then]).any():\n                return None\n")],
}
UNIT = ["tests/test_amputate.py", "tests/test_reliability_metrics.py", "tests/test_reliability_table.py"]
name, cmd, scope = sys.argv[2], sys.argv[3], sys.argv[4]
saved = {}
for path, old, new in M[name]:
    f = REPO / path
    text = saved.setdefault(f, f.read_bytes().decode("utf-8"))
    cur = f.read_bytes().decode("utf-8")
    assert cur.count(old) == 1, (name, old)
    f.write_bytes(cur.replace(old, new).encode("utf-8"))
try:
    unit = subprocess.run(["uv", "run", "pytest", "-q", "-x", "-p", "no:cacheprovider", *UNIT], cwd=REPO,
                          capture_output=True, text=True)
    tail = unit.stdout.strip().splitlines()[-1] if unit.stdout.strip() else unit.stderr[-300:]
    print(f"{name}: unit tests {'FAIL (killed)' if unit.returncode else 'PASS (survives)'}: {tail}", flush=True)
    args = ["uv", "run", "ac2fb", cmd, "--check", "--reports-dir", str(REPO / "reports")]
    if scope != "all":
        args += ["--match", scope]
    real = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    lines = real.stdout.strip().splitlines()
    print(f"{name}: realdata {cmd} --check ({scope}) exit {real.returncode}: {lines[0] if lines else real.stderr[-300:]}; "
          f"{len(lines) - 2} problem(s); first: {lines[1] if len(lines) > 2 else ''}", flush=True)
finally:
    for f, text in saved.items():
        f.write_bytes(text.encode("utf-8"))
