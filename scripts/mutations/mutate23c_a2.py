# Mutation script cited by the record of task 23c, front A, pass 2 (the 7 new ones) in
#   tasks/todo.md.
# Archived as it was written, from a session scratchpad; not run by pytest or CI (the
# name does not start with test_ and tests/ is the only testpath).
# How to run: as mutate23c_a.py.

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
    ("P1 history simplified", D, '"--full-history", ', ""),
    ("P2 frozen sees HEAD only", D, '_layer2_history("--all")', "_layer2_history(head)"),
    ("P3 shallow clone admitted", D, '!= b"false"', '== b"never"'),
    ("P4 a name installed twice", L, "        if len(homes) > 1:", "        if False:"),
    ("P5 imports from anywhere", L,
     "        outside = [p for p in places if not _in_site(p)]", "        outside: list[str] = []"),
    ("P6 read stage sees every branch", D,
     "    history = _layer2_history(head)", '    history = _layer2_history("--all")'),
    ("P7 RECORD of the git packages only", L,
     "        edited = _edited(copies[name][0])",
     "        edited = [] if name != 'ftbase' else _edited(copies[name][0])"),
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
