# Mutation script cited by the record of task 23b in tasks/todo.md.
# Archived as it was written, from a session scratchpad; not run by pytest or CI (the
# name does not start with test_ and tests/ is the only testpath).
# How to run: `python scripts/mutations/mutate23b.py <repository root>`; in-memory copies, as 23a.

"""Mutations of task 23b: each must make its tests fail. Files restored from an in-memory copy."""

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
DATA = "src/ac2fb/protocol/data.py"
LOCK = "src/ac2fb/protocol/lock.py"
CLI = "src/ac2fb/cli.py"
T_GATE = "tests/test_data_gate.py"
T_READ = "tests/test_heldout.py"
T_LOCK = "tests/test_lock.py"

COMMIT_BEFORE = """        (_repo_root() / LAYER2_PATH).write_bytes(_record(layer2, head, heldout))
        _git("add", "--", LAYER2_PATH)
        _git("commit", "-q", "-m", READ_MESSAGE, "--", LAYER2_PATH)
    after = guard_status()"""
RUN = """        written = tuple(commands[name](list(heldout), reports_dir) for name in reads)
    finally:
        _READING.reset(token)"""
RUN_THEN_COMMIT = RUN + """
    if not reproduced:
        (_repo_root() / LAYER2_PATH).write_bytes(_record(layer2, head, heldout))
        _git("add", "--", LAYER2_PATH)
        _git("commit", "-q", "-m", READ_MESSAGE, "--", LAYER2_PATH)"""

MUTATIONS: list[tuple[str, str, list[tuple[str, str]], list[str]]] = [
    ("the gate opens in frozen", DATA,
     [('OPEN_STAGES: tuple[str, ...] = ("read",)', 'OPEN_STAGES: tuple[str, ...] = ("frozen", "read")')],
     [T_GATE]),
    ("the gate serves outside the reading", DATA,
     [("if not _READING.get():", "if False:")], [T_GATE]),
    ("layer 3 need not be dead", DATA,
     [("if protocol_stage != _LAYER3_DEAD:", "if False:")], [T_GATE, T_READ]),
    ("the reading does not compare versions", DATA,
     [("problems += lock.lock_mismatches(locked, lock.installed_packages())", "problems += []")],
     [T_READ]),
    ("the reading commits after computing (with frozen open)", DATA,
     [('OPEN_STAGES: tuple[str, ...] = ("read",)', 'OPEN_STAGES: tuple[str, ...] = ("frozen", "read")'),
      (COMMIT_BEFORE, "        pass\n    after = _guard(_READABLE_STAGES)"),
      (RUN, RUN_THEN_COMMIT)],
     [T_READ]),
    ("the reads are not compared with the code", DATA,
     [(" or set(reads) != set(commands)", "")], [T_READ]),
    ("a reproduction is taken for a first reading", DATA,
     [('reproduced = status.stage == "read"', "reproduced = False")], [T_READ]),
    ("the record forgets the frozen commit", DATA,
     [('"frozen_commit": frozen_commit,', '"frozen_commit": None,')], [T_READ]),
    ("the lock ignores the git commit", LOCK,
     [("if pin.commit is not None and dist.commit != pin.commit:", "if False:")], [T_LOCK, T_READ]),
    ("the lock does not require the run-time closure", LOCK,
     [("for name in sorted(_closure(locked, ROOT_PACKAGE) - set(installed)):", "for name in []:")],
     [T_LOCK, T_READ]),
    ("the lock follows edges with a marker", LOCK,
     [('if "marker" not in d', "if True")], [T_LOCK]),
    ("the lock allows a package it does not list", LOCK,
     [('found.append(f"{name} {dist.version} is installed but not in uv.lock")', "pass")],
     [T_LOCK]),
    ("the reading runs layer 3 code", CLI,
     [("    write_long(match_ids)\n    return write_report",
       "    write_long(match_ids)\n"
       "    __import__('ac2fb.defence.pressure', fromlist=['_']).distance_weight("
       "__import__('numpy').array([0.0]))\n    return write_report")],
     [T_READ]),
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    survivors = []
    for name, rel, swaps, tests in MUTATIONS:
        path = ROOT / rel
        original = path.read_bytes()
        before = digest(path)
        text = original.decode("utf-8")
        for old, new in swaps:
            assert text.count(old) == 1, (name, old, text.count(old))
            text = text.replace(old, new)
        path.write_bytes(text.encode("utf-8"))
        try:
            done = subprocess.run(
                ["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", *tests],
                cwd=ROOT, capture_output=True, text=True,
            )
        finally:
            path.write_bytes(original)
        assert digest(path) == before, f"{rel} not restored"
        lines = done.stdout.strip().splitlines()
        tail = lines[-1] if lines else done.stderr[-300:]
        failed = sorted({ln.split(" - ")[0].removeprefix("FAILED ") for ln in lines if ln.startswith("FAILED")})
        killed = done.returncode != 0
        print(f"{'KILLED ' if killed else 'SURVIVED'} {name}: {tail}")
        for f in failed[:4]:
            print(f"    {f}")
        if not killed:
            survivors.append(name)
    print(f"{len(MUTATIONS) - len(survivors)} of {len(MUTATIONS)} killed; survivors: {survivors}")


main()
