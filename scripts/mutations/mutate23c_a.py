# Mutation script cited by the record of task 23c, front A (the 18 of pass 1) in tasks/todo.md.
# Archived as it was written, from a session scratchpad; not run by pytest or CI (the
# name does not start with test_ and tests/ is the only testpath).
# How to run: from the root of a clean worktree, with its own .venv: `python
#   scripts/mutations/mutate23c_a.py`; restores with `git checkout`.

"""Mutations of the 23c front A fixes: each one must make a test fail. Run from the worktree.

Each mutation edits one committed file, runs the tests with -x, and restores the file with
``git checkout``; the tree must be clean before and after.
"""

import subprocess
import sys

import os

PY = os.path.abspath(".venv/Scripts/python.exe")
TESTS = ["tests/test_heldout.py", "tests/test_lock.py"]
D, L, C = "src/ac2fb/protocol/data.py", "src/ac2fb/protocol/lock.py", "src/ac2fb/cli.py"

MUTATIONS = [
    ("M1 no history check in read", D,
     '        if reads != [last] or subject != READ_MESSAGE or not before or before[0][2] != "frozen":',
     "        if not before:"),
    ("M2 any subject", D, "subject != READ_MESSAGE or ", ""),
    ("M3 no freeze before the reading", D, ' or before[0][2] != "frozen"', ""),
    ("M4 several readings", D, "if reads != [last] or", "if last not in reads or"),
    ("M5 frozen after a reading", D, "        if reads:\n", "        if False:\n"),
    ("M6 no diff since the freeze", D, "    if changed != allowed:", "    if False:"),
    ("M7 record need not name the freeze", D,
     '        if not isinstance(reading, dict) or reading.get("frozen_commit") != freeze:',
     "        if not isinstance(reading, dict):"),
    ("M8 record names HEAD", D, "_record(layer2, frozen_commit, heldout)", "_record(layer2, head, heldout)"),
    ("M9 no import check", D, "    problems += lock.import_mismatches(locked)\n", ""),
    ("M10 no interpreter check", D,
     '    problems += lock.python_mismatches(_git("show", f"{head}:.python-version").decode("utf-8"))\n',
     ""),
    ("M11 reads a subset", D, "and set(reads) == set(commands)", "and set(reads) <= set(commands)"),
    ("M12 duplicate reads", D, "        and len(set(reads)) == len(reads)\n", ""),
    ("M14 a gone file is not edited", L,
     "        except OSError:\n            edited.append(path)\n            continue",
     "        except OSError:\n            continue"),
    ("M16 interpreter as a string prefix", L,
     '    if have.split(".")[: len(want)] != want:', '    if not have.startswith(".".join(want)):'),
    ("M17 a failure as a refusal", C,
     '        print(f"failed: {exc}", file=sys.stderr)\n        return 1',
     '        print(f"refused: {exc}", file=sys.stderr)\n        return 2'),
    ("M18 the caller's commands accepted", D,
     "def read_heldout(reports_dir: Path) -> HeldOutReading:",
     "def read_heldout(reports_dir: Path, commands: Any = None) -> HeldOutReading:"),
]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, check=True, text=True).stdout


assert git("status", "--short") == "", "tree not clean"
survived = []
for name, path, old, new in MUTATIONS:
    text = open(path, encoding="utf-8", newline="").read()
    assert text.count(old) == 1, (name, text.count(old))
    open(path, "w", encoding="utf-8", newline="").write(text.replace(old, new))
    try:
        done = subprocess.run(
            [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
            capture_output=True, text=True,
        )
    finally:
        git("checkout", "--", path)
    tail = [line for line in done.stdout.splitlines() if line.startswith(("FAILED", "ERROR"))]
    verdict = "killed" if done.returncode != 0 else "SURVIVED"
    if done.returncode == 0:
        survived.append(name)
    print(f"{verdict}: {name} :: {tail[:1]}", flush=True)
assert git("status", "--short") == "", "tree not clean after"
print(f"{len(MUTATIONS) - len(survived)} of {len(MUTATIONS)} killed; survived: {survived}")
sys.exit(1 if survived else 0)
