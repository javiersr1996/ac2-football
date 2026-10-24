# Mutation script cited by the record of task 22 (review 22's fixes, commit c0eefa9) in
#   tasks/todo.md.
# Archived as it was written, from a session scratchpad; not run by pytest or CI (the
# name does not start with test_ and tests/ is the only testpath).
# How to run: from the root of the repository, `python scripts/mutations/mutate22.py`; it edits
#   the working tree and restores each file byte for byte. Found in the scratchpad of the
#   football-tracking-base project, not of this one.

"""Apply each annotated mutation of review 22's fixes, run its test, restore the file.

Run from the root of ac2-football. Each mutation is (file, old, new, tests); the file is backed
up byte for byte and restored after the run, whatever happens.
"""
import subprocess
import sys
from pathlib import Path

MUTATIONS = [
    ("outcome across the break", "src/ac2fb/defence/effect.py",
     "if now < 0 or end < 0 or match.ball_period[now] != match.ball_period[end]:",
     "if now < 0 or end < 0:",
     ["tests/test_effect.py::test_no_window_crosses_a_period_break"]),
    ("pre across the break", "src/ac2fb/defence/power.py",
     "if then < 0 or now < 0 or match.ball_period[then] != match.ball_period[now]:",
     "if then < 0 or now < 0:",
     ["tests/test_effect.py::test_no_window_crosses_a_period_break"]),
    ("stratum across the break", "src/ac2fb/defence/pressure.py",
     "        or match.ball_period[rows[0]] != match.ball_period[rows[1]]\n",
     "",
     ["tests/test_effect.py::test_no_window_crosses_a_period_break"]),
    ("direction cut without the tie", "src/ac2fb/defence/pressure.py",
     "    cut = BACKWARD_CUT + TIE\n", "    cut = BACKWARD_CUT\n",
     ["tests/test_pressure_s1.py::test_the_stratum_of_the_incoming_ball"]),
    ("length cut without the tie", "src/ac2fb/defence/pressure.py",
     "straight >= LONG_BALL - TIE", "straight >= LONG_BALL",
     ["tests/test_pressure_s1.py::test_the_stratum_of_the_incoming_ball"]),
    ("pre without the attack sign", "src/ac2fb/defence/design.py",
     "pre=power.ball_advance(match, r.frame, sign, W),",
     "pre=power.ball_advance(match, r.frame, 1, W),",
     ["tests/test_design.py::test_a_mirrored_pitch_in_the_second_period_gives_the_same_units"]),
    ("sign of period 1 always", "src/ac2fb/defence/design.py",
     "sign = match.attack_sign[(r.period, r.team)]",
     "sign = match.attack_sign.get((1, r.team), 1)",
     ["tests/test_design.py::test_a_mirrored_pitch_in_the_second_period_gives_the_same_units"]),
    ("exclusion against every labelled reception", "src/ac2fb/defence/design.py",
     "excluded = excluded_by_gap(receptions)",
     "excluded = excluded_by_gap(list(inputs.s1.receptions))",
     ["tests/test_design.py::test_a_reception_that_is_not_a_unit_excludes_nothing"]),
    ("never blocked", "src/ac2fb/defence/calibration.py",
     "blocked = bool(simulated[\"blocked\"])", "blocked = False",
     ["tests/test_calibration.py::test_a_correlated_possession_blocks_the_null"]),
    ("V1 null on V0 units", "src/ac2fb/defence/effect.py",
     "    p = _prepare(select_units(units, variant))\n    if len(p.cell_keys) == 0:\n        return Null(",
     "    p = _prepare(list(units))\n    if len(p.cell_keys) == 0:\n        return Null(",
     ["tests/test_calibration.py::test_the_v1_null_permutes_only_the_v1_units"]),
    ("exclusion gap 12 in the code", "src/ac2fb/defence/design.py",
     "EXCLUSION_GAP = W", "EXCLUSION_GAP = 12",
     ["tests/test_protocol.py::test_the_committed_protocol_passes_the_check"]),
]

failed_to_kill = []
for name, path, old, new, tests in MUTATIONS:
    file = Path(path)
    original = file.read_bytes()
    text = original.decode("utf-8")
    if text.count(old) != 1:
        print(f"!! {name}: pattern found {text.count(old)} times in {path}")
        failed_to_kill.append(name)
        continue
    try:
        file.write_bytes(text.replace(old, new).encode("utf-8"))
        done = subprocess.run(
            ["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", "-x", *tests],
            capture_output=True, text=True,
        )
    finally:
        file.write_bytes(original)
    killed = done.returncode != 0
    last = [l for l in done.stdout.splitlines() if l.strip()][-1:]
    print(f"{'killed' if killed else 'SURVIVED'}: {name} -> {last}")
    if not killed:
        failed_to_kill.append(name)
sys.exit(1 if failed_to_kill else 0)
