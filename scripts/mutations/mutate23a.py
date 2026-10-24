# Mutation script cited by the record of task 23a in tasks/todo.md.
# Archived as it was written, from a session scratchpad; not run by pytest or CI (the
# name does not start with test_ and tests/ is the only testpath).
# How to run: `python scripts/mutations/mutate23a.py <repository root>`; each mutation is applied
#   from an in-memory copy of the file and restored from it.

"""Mutations of task 23a: each must make its test fail. Files restored from an in-memory copy."""

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
CHECK = "src/ac2fb/protocol/check.py"
DATA = "src/ac2fb/protocol/data.py"
PROTO = "protocol/protocol.json"
T_PROTO = "tests/test_protocol.py"
T_GATE = "tests/test_data_gate.py"

MUTATIONS = [
    ("the gate opens in dead", DATA,
     'OPEN_STAGES: tuple[str, ...] = ("frozen", "read")',
     'OPEN_STAGES: tuple[str, ...] = ("frozen", "read", "dead")', [T_GATE]),
    ("killed_by is not the report's", PROTO,
     '"killed_by": [\n      "D3"\n    ]', '"killed_by": [\n      "D4"\n    ]', [T_PROTO]),
    ("the report's sha256 is not the file's", PROTO,
     '"report_sha256": "7ec1', '"report_sha256": "8ec1', [T_PROTO]),
    ("no verdict-iff-dead rule", CHECK,
     '("verdict" in p) == (stage == "dead")', 'True', [T_PROTO]),
    ("empty killed_by accepted with the bar passed", CHECK,
     'and (bool(killed) or _get(p, "verdict.v0_bar_passed")[1] is False)', '', [T_PROTO]),
    ("killed_by may name D5", CHECK, "set(_CRITERIA[:4])", "set(_CRITERIA[:5])", [T_PROTO]),
    ("dead must record a code tree sha", CHECK,
     '_UNFROZEN = ("design", "dead")', '_UNFROZEN = ("design",)', [T_PROTO]),
    ("the verdict's fields are not in the schema of dead", CHECK,
     '{**SCHEMA, **VERDICT} if protocol.get("stage") == "dead" else SCHEMA', "SCHEMA", [T_PROTO]),
    ("heldout_read_for_layer3 not checked", CHECK,
     '_get(p, "verdict.heldout_read_for_layer3")[1] is False', "True", [T_PROTO]),
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    survivors = []
    for name, rel, old, new, tests in MUTATIONS:
        path = ROOT / rel
        original = path.read_bytes()
        before = digest(path)
        text = original.decode("utf-8")
        assert text.count(old) == 1, (name, text.count(old))
        path.write_bytes(text.replace(old, new).encode("utf-8"))
        try:
            done = subprocess.run(
                ["uv", "run", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
                cwd=ROOT, capture_output=True, text=True,
            )
        finally:
            path.write_bytes(original)
        assert digest(path) == before, f"{rel} not restored"
        tail = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else done.stderr[-200:]
        killed = done.returncode != 0
        print(f"{'KILLED ' if killed else 'SURVIVED'} {name}: {tail}")
        if not killed:
            survivors.append(name)
    print(f"{len(MUTATIONS) - len(survivors)} of {len(MUTATIONS)} killed; survivors: {survivors}")


main()
