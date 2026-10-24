# Mutation script cited by the record of task 28 in tasks/todo.md.
# Not run by pytest or CI (the name does not start with test_ and tests/ is the only testpath).
# How to run, from anywhere: `python scripts/mutations/mutate28.py [substring ...]`. It plants each
#   fault in a COPY of the tree (under a temporary directory; the real tree is only read), runs
#   tests/test_report_checks.py and tests/test_layer2_check.py there and prints CAUGHT or SURVIVED.
#   Needs the repository's .venv (the copy runs with PYTHONPATH on its own src).

"""Plant faults in the `--check` of the commands that write a report; the tests must fail."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REAL = Path(__file__).resolve().parents[2]
PY = str(REAL / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
TESTS = ["tests/test_report_checks.py", "tests/test_layer2_check.py"]
CLI, REPORT = "cli.py", "reliability/report.py"

# (name, file under src/ac2fb, old text (exactly once), new text)
MUTATIONS = [
    ("the comparison compares nothing", REPORT,
     "    return JsonCheck(len(compared), tuple(problems))",
     "    return JsonCheck(len(compared), ())"),
    ("a changed value is not reported", REPORT,
     "    problems += [f\"{p}: file {disk[p]!r}, code {code[p]!r}\" for p in compared if disk[p] != code[p]]",
     "    problems += []"),
    ("a value only in the file is not reported", REPORT,
     "    problems += [f\"not produced by the code: {p}\" for p in disk if p not in code]",
     "    problems += []"),
    ("a value only in the code is not reported", REPORT,
     "    problems += [f\"missing from the file: {p}\" for p in code if p not in disk]",
     "    problems += []"),
    ("a carriage return is accepted", REPORT,
     "    problems = [\"the file has a carriage return\"] if b\"\\r\" in raw else []",
     "    problems = []"),
    ("a file rendered otherwise is accepted", REPORT,
     "    if not problems and raw.decode(\"utf-8\") != fresh:",
     "    if False:"),
    ("a missing file passes", REPORT,
     "        return JsonCheck(0, (f\"{name} does not exist\",))",
     "        return JsonCheck(0, ())"),
    ("the values verified are not counted", REPORT,
     "    return JsonCheck(len(compared), tuple(problems))",
     "    return JsonCheck(0, tuple(problems))"),
    ("the check exits 0 when it fails", CLI,
     "    print(f\"{name}: OK\" if result.ok else f\"{name}: FAILED\")\n    return 0 if result.ok else 1",
     "    print(f\"{name}: OK\" if result.ok else f\"{name}: FAILED\")\n    return 0"),
    ("the check does not say OK or FAILED", CLI,
     "    print(f\"{name}: OK\" if result.ok else f\"{name}: FAILED\")\n    return 0 if result.ok else 1",
     "    return 0 if result.ok else 1"),
    ("the problems are not listed", CLI,
     "        print(f\"  - {problem}\")\n    partial = _coverage(ids, heldout_artefact=heldout_artefact)",
     "        pass\n    partial = _coverage(ids, heldout_artefact=heldout_artefact)"),
    ("the PARTIAL line is not printed", CLI,
     "    if partial:\n        print(partial)\n    print(f\"{name}: OK\" if result.ok else f\"{name}: FAILED\")",
     "    print(f\"{name}: OK\" if result.ok else f\"{name}: FAILED\")"),
    ("the share counts only the calibration matches as the total", CLI,
     "    total = len(split.calibration) + len(split.heldout)",
     "    total = len(split.calibration)"),
    ("the share says full coverage with 20 asked of 2", CLI,
     "    if len(ids) >= total:\n        return None",
     "    if len(ids) >= 0:\n        return None"),
    ("the held-out half of layer 2 is said to not exist", CLI,
     "    partial = _coverage(ids, heldout_artefact=True)\n    if partial:\n        print(partial)\n    print(\"layer2: OK\"",
     "    partial = _coverage(ids, heldout_artefact=False)\n    if partial:\n        print(partial)\n    print(\"layer2: OK\""),
    ("the check of cadence reads the file of s1", CLI,
     "cadence.check(ids, _committed(reports_dir / cadence.REPORT_NAME))",
     "cadence.check(ids, _committed(reports_dir / probe_s1.REPORT_NAME))"),
    ("the check of s2 recomputes the report of s1", CLI,
     "probe_s2.check(ids, _committed(reports_dir / probe_s2.REPORT_NAME))",
     "probe_s1.check(ids, _committed(reports_dir / probe_s2.REPORT_NAME))"),
    ("the check of design reads the file of calibration", CLI,
     "design.check(ids, _committed(reports_dir / design.REPORT_NAME))",
     "design.check(ids, _committed(reports_dir / calibration.REPORT_NAME))"),
    ("the check of power takes the probe reports of the repo, not the ones beside the file", CLI,
     "        alive = _probe_verdicts(reports_dir)",
     "        alive = _probe_verdicts(_REPORTS)"),
    ("the check of calibration writes the report", CLI,
     "        result = calibration.check(ids, _committed(reports_dir / calibration.REPORT_NAME))",
     "        write_calibration_report(ids, reports_dir)\n"
     "        result = calibration.check(ids, _committed(reports_dir / calibration.REPORT_NAME))"),
    ("the check of s3 rewrites the file first", CLI,
     "        result = probe_s3.check(ids, _committed(reports_dir / probe_s3.REPORT_NAME))",
     "        write_s3_report(ids, reports_dir)\n"
     "        result = probe_s3.check(ids, _committed(reports_dir / probe_s3.REPORT_NAME))"),
    ("s1 --check does not refuse a held-out match", CLI,
     "        result = probe_s1.check(ids, _committed(reports_dir / probe_s1.REPORT_NAME))\n    except HeldOutLocked as exc:",
     "        result = probe_s1.check(ids, _committed(reports_dir / probe_s1.REPORT_NAME))\n    except ZeroDivisionError as exc:"),
    ("the check of s1 verifies one match fewer than it says", "defence/probe_s1.py",
     "    report = s1_report([load_inputs(m) for m in match_ids])\n    return check_json",
     "    report = s1_report([load_inputs(m) for m in match_ids[1:]])\n    return check_json"),
    ("the check of cadence recomputes with the previous rounding", "reliability/cadence.py",
     "    return check_json(REPORT_NAME, render_report(report), raw)",
     "    return check_json(REPORT_NAME, render_report(report).replace('.0,', ','), raw)"),
    ("the check of the earlier layer2 counts nothing", REPORT,
     "    return Check(len(match_ids), result.values, result.problems)",
     "    return Check(len(match_ids), 0, result.problems)"),
]


COMMANDS = ("cadence", "s1", "s2", "s3", "power", "design", "calibration")


def selector(name: str) -> list[str]:
    """A fault inside one command's check is run against that command's tests only (-x: the
    first failing test kills it); a fault in the shared code is run against all of them."""
    for command in COMMANDS:
        if f"check of {command}" in name or f"{command} --check" in name:
            return ["-k", command]
    if "layer2" in name:
        return ["-k", "layer2 or earlier"]
    return []


def run(work: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=str(work / "src"), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(args, cwd=work, env=env, capture_output=True, text=True)


def main() -> None:
    only = sys.argv[1:]
    work = Path(tempfile.mkdtemp(prefix="ac2fb-mutate28-")) / "tree"
    ignore = shutil.ignore_patterns(
        ".venv", ".git", "data", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"
    )
    shutil.copytree(REAL, work, ignore=ignore)
    # some tests read protocol/split.json from HEAD, so the copy needs a repository of its own
    for git in (["init", "-q"], ["add", "-A"], ["-c", "user.name=m", "-c", "user.email=m@m",
                                                 "commit", "-q", "-m", "copy"]):
        subprocess.run(["git", *git], cwd=work, check=True, capture_output=True)
    pristine = {
        f: (work / "src" / "ac2fb" / f).read_text(encoding="utf-8")
        for f in {m[1] for m in MUTATIONS}
    }
    for name, file, old, _ in MUTATIONS:  # every fault must find its place before any test runs
        assert pristine[file].count(old) == 1, f"{name}: {pristine[file].count(old)} matches"
    base = run(work, [PY, "-m", "pytest", *TESTS, "-q", "-p", "no:cacheprovider"])
    print("baseline:", base.stdout.strip().splitlines()[-1], flush=True)
    if base.returncode != 0:
        print(os.linesep.join(ln for ln in base.stdout.splitlines() if "FAILED" in ln or "Error" in ln))
        sys.exit("the baseline must pass before a mutation means anything")
    for name, file, old, new in MUTATIONS:
        if only and not any(o in name for o in only):
            continue
        text = pristine[file]
        assert text.count(old) == 1, f"{name}: {text.count(old)} matches"
        for f, t in pristine.items():
            (work / "src" / "ac2fb" / f).write_text(t, encoding="utf-8", newline="\n")
        (work / "src" / "ac2fb" / file).write_text(
            text.replace(old, new), encoding="utf-8", newline="\n"
        )
        result = run(
            work, [PY, "-m", "pytest", *TESTS, "-q", "-x", "-p", "no:cacheprovider", *selector(name)]
        )
        failed = sorted(
            {
                ln.split("::")[1].split(" ")[0].split("[")[0]
                for ln in result.stdout.splitlines()
                if ln.startswith("FAILED")
            }
        )
        verdict = "CAUGHT" if result.returncode != 0 else "SURVIVED"
        print(f"{verdict}: {name} -> {len(failed)} failing: {', '.join(failed)[:150]}", flush=True)
    shutil.rmtree(work.parent, ignore_errors=True)


main()
