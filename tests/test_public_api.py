"""Task 29: the public API for reuse is documented once, in code, and its example runs.

The names the docs point at are resolved here (a name that goes away fails), the long Parquet
schema is the constant ``LONG_SCHEMA`` and its docstring is held to it, and
``examples/sensitivity.py`` runs as a subprocess on its synthetic match without reading any data.
No new route: the public names are existing ones, in ``tests/test_public_routes.py``.

Mutations (each planted on a copy, seen to fail, then dropped):

* a name in the ``reliability`` docstring that is not exported: ``test_every_documented_name_...``;
* a column added to ``LONG_SCHEMA`` and not to its docstring or to ``LONG_COLUMNS``:
  ``test_the_long_schema_is_one_thing_in_code_and_in_its_docstring``;
* the example without its disclaimer, or reading ``data/`` or the data door:
  ``test_the_example_runs_on_the_synthetic_match_and_says_it_is_not_a_finding``,
  ``test_the_example_reads_no_file``.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import os
import re
import subprocess
import sys
from pathlib import Path

import pyarrow as pa

import ac2fb.reliability
from ac2fb.reliability import long

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "sensitivity.py"
NAME = re.compile(r"ac2fb(?:\.\w+)+")


def documented_names() -> list[str]:
    found = NAME.findall(ac2fb.reliability.__doc__ or "")
    return sorted({n for n in found if n != "ac2fb.reliability"})


def test_every_documented_name_resolves_and_is_exported() -> None:
    names = documented_names()
    assert len(names) >= 12, names  # the reading steps and the API they name
    for name in names:
        try:
            importlib.import_module(name)  # a module, such as ``ac2fb.protocol.data``
            continue
        except ModuleNotFoundError:
            pass
        module_name, _, attribute = name.rpartition(".")
        module = importlib.import_module(module_name)
        assert attribute in module.__all__, f"{name} is not in the __all__ of {module_name}"
        assert hasattr(module, attribute), name
    assert "ac2fb.reliability.amputate.amputate" in names
    assert "ac2fb.protocol.data.read_frames" in names
    assert "ac2fb.reliability.sensitivity.sensitivity" in names


def test_the_package_re_exports_nothing_so_no_module_is_shadowed() -> None:
    # ``amputate`` and ``sensitivity`` are a module and its main function; ``cli.py`` and
    # ``reading.py`` import the module from the package, so a re-export would break them.
    assert ac2fb.reliability.__all__ == []
    for name in ("amputate", "sensitivity"):
        module = getattr(ac2fb.reliability, name)
        assert inspect.ismodule(module) and callable(getattr(module, name)), name


def test_the_long_schema_is_one_thing_in_code_and_in_its_docstring() -> None:
    assert long.LONG_SCHEMA.names == list(long.LONG_COLUMNS)
    doc = long.__doc__ or ""
    assert "gap_len" in long.LONG_COLUMNS
    assert pa.types.is_int32(long.LONG_SCHEMA.field("gap_len").type)
    kinds = {
        pa.types.is_string: "string",
        pa.types.is_int16: "int16",
        pa.types.is_int32: "int32",
        pa.types.is_int64: "int64",
        pa.types.is_float64: "float64",
        pa.types.is_boolean: "bool",
    }
    for field in long.LONG_SCHEMA:
        wanted = next(word for is_kind, word in kinds.items() if is_kind(field.type))
        pattern = rf"``{field.name}``(?: and ``\w+``)? \({wanted}(?![a-z0-9])"
        assert re.search(pattern, doc.replace("\n", " ")), (
            f"{field.name} ({wanted}) in the docstring"
        )


def run_example(env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(EXAMPLE)],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        timeout=300,
    )


def test_the_example_runs_on_the_synthetic_match_and_says_it_is_not_a_finding(
    tmp_path: Path,
) -> None:
    # Pointed at a data root that does not exist and run from an empty directory: a read of the
    # data, or of the checkout, would fail.
    env = {**os.environ, "FTBASE_DATA_ROOT": str(tmp_path / "no-data")}
    done = run_example(env, tmp_path)
    assert done.returncode == 0, done.stderr
    lines = done.stdout.splitlines()
    assert len(lines) == 1, done.stdout
    assert re.fullmatch(
        r"line_height_m: V0 n=\d+ mean=-?\d+\.\d\d m, V1 n=\d+ mean=-?\d+\.\d\d m, "
        r"extrapolated=\d\.\d{3}, amputation n=\d+ mean_abs_error=\d\.\d{3} m "
        r"\(synthetic numbers, not findings\)",
        lines[0],
    ), lines[0]
    v0, v1 = (int(n) for n in re.findall(r"n=(\d+)", lines[0])[:2])
    assert 0 < v1 < v0  # V1 is a strict selection of V0: gaps exist and so do whole units


def test_the_example_reads_no_file() -> None:
    tree = ast.parse(EXAMPLE.read_text(encoding="utf-8"))
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in (node.names if isinstance(node, ast.Import) else [None])
    }
    assert not any(str(m).startswith("ac2fb.protocol") for m in imported), imported
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert not {n for n in called if n == "open" or n.startswith(("read", "write"))}, called
