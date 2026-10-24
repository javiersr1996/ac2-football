# Mutation script cited by the record of task 23c, the 26 final mutations in tasks/todo.md.
# Archived as it was written, from a session scratchpad; not run by pytest or CI (the
# name does not start with test_ and tests/ is the only testpath).
# How to run: from the root of a clean, committed tree with its own .venv: `python
#   scripts/mutations/mutate23c_final.py`; restores with `git checkout`.

"""Mutations of the reading's guard after review 23c (passes 1 to 3): each must fail its test.

Run from the repository root on a clean, committed tree. Each mutation edits one file, runs
only the tests named for it, and restores the file with ``git checkout``.
"""

import os
import subprocess
import sys

PY = os.path.abspath(".venv/Scripts/python.exe")
D, L, C = "src/ac2fb/protocol/data.py", "src/ac2fb/protocol/lock.py", "src/ac2fb/cli.py"
H, K = "tests/test_heldout.py", "tests/test_lock.py"
REFUSED = f"{H}::test_a_reading_that_cannot_hold_is_refused_unrecorded_and_unopened"
AFTER = f"{H}::test_after_the_reading_editing_layer2_does_not_open_it_again"

MUTATIONS = [
    ("M1 no history check in read", D,
     '        if readings != [last] or not before or before[0][2] != "frozen":',
     "        if not before:", [f"{AFTER}[new code with its sha in layer2.json]"]),
    ("M3 no freeze before the reading", D, ' or before[0][2] != "frozen"', "",
     [f"{REFUSED}[a reading with no freeze before it]"]),
    ("M4 several readings", D, "if readings != [last] or", "if last not in readings or",
     [f"{AFTER}[a second reading by hand on new code]",
      f"{H}::test_a_reading_by_hand_on_a_branch_from_the_freeze_is_not_a_reproduction"]),
    ("M5 frozen after a reading", D, "        if readings:", "        if False:",
     [f"{AFTER}[layer2.json frozen again on new code]",
      f"{H}::test_a_branch_from_the_freeze_cannot_read_again"]),
    ("M6 no diff since the freeze", D, "    if changed != allowed:", "    if False:",
     [f"{AFTER}[the split changed after the reading]",
      f"{REFUSED}[the split changed after the freeze]"]),
    ("M7 record need not name the freeze", D,
     '        if not isinstance(reading, dict) or reading.get("frozen_commit") != freeze:',
     "        if not isinstance(reading, dict):",
     [f"{REFUSED}[a reading that names another freeze]"]),
    ("M8 record names HEAD", D, "_record(layer2, frozen_commit, heldout)",
     "_record(layer2, head, heldout)", [f"{H}::test_the_record_names_the_freeze_not_a_later_commit"]),
    ("M9 no import check", D, "    problems += lock.import_mismatches(locked)\n", "",
     [f"{REFUSED}[the base imported from elsewhere]"]),
    ("M10 no interpreter check", D, "lock.python_mismatches(_git(", "(lambda pin: [])(_git(",
     [f"{REFUSED}[another interpreter]"]),
    ("M11 reads a subset", D, "and set(reads) == set(commands)", "and set(reads) <= set(commands)",
     [f"{REFUSED}[fewer reads than the code's]"]),
    ("M12 duplicate reads", D, "        and len(set(reads)) == len(reads)\n", "",
     [f"{REFUSED}[a read listed twice]"]),
    ("M14 a gone file is not edited", L,
     "        except OSError:\n            edited.append(path)\n            continue",
     "        except OSError:\n            continue",
     [f"{K}::test_a_file_edited_or_gone_since_install_is_found"]),
    ("M16 interpreter as a string prefix", L,
     '    if have.split(".")[: len(want)] != want:', '    if not have.startswith(".".join(want)):',
     [f"{K}::test_the_interpreter_is_held_to_the_pin"]),
    ("M17 a failure as a refusal", C,
     '        print(f"failed: {exc}", file=sys.stderr)\n        return 1',
     '        print(f"refused: {exc}", file=sys.stderr)\n        return 2',
     [f"{H}::test_the_command_says_a_failure_is_not_a_refusal"]),
    ("M18 the caller's commands accepted", D,
     "def read_heldout(reports_dir: Path) -> HeldOutReading:",
     "def read_heldout(reports_dir: Path, commands: Any = None) -> HeldOutReading:",
     [f"{H}::test_the_reading_takes_no_function_from_its_caller"]),
    ("P1 HEAD's history through every parent", D,
     '    flags = ("--full-history",) if full else ()', '    flags = ("--full-history",)',
     [f"{H}::test_a_merge_after_the_freeze_is_not_taken_for_the_freeze",
      f"{H}::test_a_split_merged_in_after_the_freeze_shuts_it"]),
    ("P1b readings simplified", D, '_layer2_history("--all", full=True)', '_layer2_history("--all")',
     [f"{H}::test_a_merge_that_discards_the_reading_cannot_read_again"]),
    ("P2 readings of HEAD only", D, '_layer2_history("--all", full=True)',
     "_layer2_history(head, full=True)",
     [f"{H}::test_a_branch_from_the_freeze_cannot_read_again",
      f"{H}::test_a_reading_by_hand_on_a_branch_from_the_freeze_is_not_a_reproduction"]),
    ("P3 shallow clone admitted", D, '!= b"false"', '== b"never"',
     [f"{H}::test_a_shallow_clone_is_refused"]),
    ("P4 a name installed twice", L, "        if len(homes) > 1:", "        if False:",
     [f"{K}::test_a_base_shadowed_from_the_path_is_found"]),
    ("P4b one place seen twice is two", L,
     '        homes = sorted({str(Path(str(dist.locate_file(""))).resolve()) for dist in copies[name]})',
     '        homes = [str(dist.locate_file("")) for dist in copies[name]]',
     [f"{K}::test_one_place_seen_twice_is_one_copy"]),
    ("P5 imports from anywhere", L,
     "        outside = [p for p in places if not _in_site(p)]", "        outside: list[str] = []",
     [f"{REFUSED}[the base imported from elsewhere]",
      f"{K}::test_a_base_shadowed_from_the_path_is_found"]),
    ("P6 read stage sees every branch", D,
     "    history = _layer2_history(head)", '    history = _layer2_history("--all", full=True)',
     [f"{H}::test_a_worktree_at_the_reading_reproduces_it_after_main_moves_on"]),
    ("P7 RECORD of the git packages only", L,
     "        edited = _edited(copies[name][0])",
     "        edited = [] if name != 'ftbase' else _edited(copies[name][0])",
     [f"{REFUSED}[a library edited since install]"]),
    ("Q1 a reading by its stage alone", D,
     'if subject == READ_MESSAGE and s == "read"]', 'if s == "read"]',
     [f"{H}::test_a_work_branch_that_is_not_a_reading_does_not_block_it"]),
    ("Q2 a broken layer2.json elsewhere stops the guard", D,
     "    except (RuntimeError, ValueError, AttributeError):\n        return None",
     "    except KeyboardInterrupt:\n        return None",
     [f"{H}::test_a_work_branch_that_is_not_a_reading_does_not_block_it"]),
]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, check=True, text=True).stdout


assert git("status", "--short") == "", "tree not clean"
survived = []
for name, path, old, new, tests in MUTATIONS:
    text = open(path, encoding="utf-8", newline="").read()
    assert text.count(old) == 1, (name, text.count(old))
    open(path, "w", encoding="utf-8", newline="").write(text.replace(old, new))
    results = []
    try:
        for test in tests:
            done = subprocess.run(
                [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", test],
                capture_output=True, text=True,
            )
            results.append(done.returncode != 0)
    finally:
        git("checkout", "--", path)
    verdict = "killed" if all(results) else "SURVIVED"
    if not all(results):
        survived.append(name)
    print(f"{verdict}: {name} :: {sum(results)} of {len(tests)} named tests fail", flush=True)
assert git("status", "--short") == "", "tree not clean after"
print(f"{len(MUTATIONS) - len(survived)} of {len(MUTATIONS)} killed; survived: {survived}")
sys.exit(1 if survived else 0)
