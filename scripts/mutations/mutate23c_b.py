# Mutation script cited by the record of task 23c, front B (the record says 5 mutations in B and
#   does not name the script) in tasks/todo.md.
# Archived as it was written, from a session scratchpad; not run by pytest or CI (the
# name does not start with test_ and tests/ is the only testpath).
# How to run: `python scripts/mutations/mutate23c_b.py <repository root>`. Identified by where it
#   was (r23c/B/scripts of the 23c session), not by the record: check it against mutate23c_b.log.

"""Apply one mutation to the copy, run the unit tests named and a one-match realdata check, restore."""
import subprocess
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
MUTATIONS = {
    "band_off_by_one": ("src/ac2fb/reliability/amputate.py",
                        "longest = max((e.hi - e.lo - 1 for e in ends.values()), default=0)",
                        "longest = max((e.hi - e.lo for e in ends.values()), default=0)"),
    "swap_back_ahead": ("src/ac2fb/reliability/amputate.py",
                        "found = ends_of(match, sides, player, t, int(hide.back[k][j]), int(hide.ahead[k][j]))",
                        "found = ends_of(match, sides, player, t, int(hide.ahead[k][j]), int(hide.back[k][j]))"),
    "fill_only_last_frame": ("src/ac2fb/reliability/amputate.py",
                             "        x[row, inside] = e.lo_x + w * (e.hi_x - e.lo_x)\n        y[row, inside] = e.lo_y + w * (e.hi_y - e.lo_y)\n",
                             "        last = window.frames[inside] == window.frames[-1]\n        x[row, np.flatnonzero(inside)[last]] = (e.lo_x + w * (e.hi_x - e.lo_x))[last]\n        y[row, np.flatnonzero(inside)[last]] = (e.lo_y + w * (e.hi_y - e.lo_y))[last]\n"),
    "ball_distance_at_window_start": ("src/ac2fb/reliability/amputate.py",
                                      "dx, dy = data.x[at, -1] - match.ball_x[ball], data.y[at, -1] - match.ball_y[ball]",
                                      "dx, dy = data.x[at, 0] - match.ball_x[ball], data.y[at, 0] - match.ball_y[ball]"),
    "area_players_width_only": ("src/ac2fb/reliability/metrics.py",
                                "return Reading(width[0] * length[0], tuple(sorted({*width[1], *length[1]})))",
                                "return Reading(width[0] * length[0], tuple(sorted({*width[1]})))"),
    "nearest_outfield_only": ("src/ac2fb/reliability/metrics.py",
                              "        d = np.hypot(window.x[rivals, -1] - carrier[0], window.y[rivals, -1] - carrier[1])\n",
                              "        d = np.hypot(window.x[rivals, -1] - carrier[0], window.y[rivals, -1] - carrier[1])\n        d = np.where(np.abs(window.x[rivals, -1]) > 47.0, np.inf, d) if np.isfinite(np.where(np.abs(window.x[rivals, -1]) > 47.0, np.inf, d)).any() else d\n"),
}
UNIT = ["tests/test_amputate.py", "tests/test_reliability_metrics.py", "tests/test_reliability_table.py",
        "tests/test_layer2_check.py"]

name = sys.argv[2]
path, old, new = MUTATIONS[name]
f = REPO / path
text = f.read_bytes().decode("utf-8")
assert text.count(old) == 1, (name, text.count(old))
f.write_bytes(text.replace(old, new).encode("utf-8"))
try:
    unit = subprocess.run(["uv", "run", "pytest", "-q", "-x", "-p", "no:cacheprovider", *UNIT],
                          cwd=REPO, capture_output=True, text=True)
    tail = unit.stdout.strip().splitlines()[-1] if unit.stdout.strip() else unit.stderr[-300:]
    print(f"{name}: unit tests {'FAIL (killed)' if unit.returncode else 'PASS (survives)'}: {tail}")
    if len(sys.argv) > 3:
        cmd = sys.argv[3]
        real = subprocess.run(["uv", "run", "ac2fb", cmd, "--check", "--match", "2010085", "--reports-dir",
                               str(REPO / "reports")], cwd=REPO, capture_output=True, text=True)
        lines = real.stdout.strip().splitlines()
        print(f"{name}: realdata {cmd} --check 2010085 exit {real.returncode}: {lines[0] if lines else real.stderr[-300:]}; "
              f"{len(lines) - 2} problem(s); first: {lines[1] if len(lines) > 2 else ''}")
finally:
    f.write_bytes(text.encode("utf-8"))
