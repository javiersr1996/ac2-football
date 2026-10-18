"""One door to the data: only ``ac2fb.protocol.data`` reaches the base or opens Parquet.

The check walks the syntax tree of every module under ``src/ac2fb`` except the door and
rejects: importing ``ftbase`` (any part of it: silver, bronze and raw hold the held-out matches
too), ``duckdb`` or ``pyarrow.dataset``; calling or importing a Parquet reader by name; reaching
a private name of the door; and any string, outside docstrings, that names ``ftbase``,
``duckdb`` or ``silver`` (the way to a dynamic import or to a silver path). The checker is
itself tested on snippets it must reject and snippets it must let through.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from ac2fb.protocol import data

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "ac2fb"
DOOR = PACKAGE / "protocol" / "data.py"
DOOR_MODULE = "ac2fb.protocol.data"

FORBIDDEN_MODULES = ("ftbase", "duckdb", "pyarrow.dataset")
PARQUET_READERS = frozenset(
    {
        "ParquetDataset",
        "ParquetFile",
        "read_metadata",
        "read_pandas",
        "read_parquet",
        "read_schema",
        "read_table",
        "scan_parquet",
    }
)
FORBIDDEN_TEXT = re.compile(r"ftbase|duckdb|silver", re.IGNORECASE)


def module_name(path: Path) -> str:
    parts = path.relative_to(PACKAGE.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _forbidden(name: str) -> bool:
    return any(name == m or name.startswith(m + ".") for m in FORBIDDEN_MODULES)


def _absolute(node: ast.ImportFrom, module: str, is_package: bool) -> str:
    if node.level == 0:
        return node.module or ""
    package = module if is_package else module.rpartition(".")[0]
    for _ in range(node.level - 1):
        package = package.rpartition(".")[0]
    return f"{package}.{node.module}" if node.module else package


def _docstrings(tree: ast.AST) -> set[int]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                found.add(id(body[0].value))
    return found


def violations(source: str, module: str, is_package: bool = False) -> list[str]:
    """Every way ``source`` reaches the data without the door, one line each."""
    tree = ast.parse(source)
    docstrings = _docstrings(tree)
    door_aliases = {"ac2fb.protocol.data"}
    found: list[str] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _forbidden(alias.name):
                    found.append(f"{line}: import {alias.name}")
                if alias.name == DOOR_MODULE:
                    door_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _absolute(node, module, is_package)
            for alias in node.names:
                full = f"{base}.{alias.name}"
                if _forbidden(base) or _forbidden(full):
                    found.append(f"{line}: from {base} import {alias.name}")
                if alias.name in PARQUET_READERS:
                    found.append(f"{line}: imports the Parquet reader {alias.name}")
                if base == DOOR_MODULE and alias.name.startswith("_"):
                    found.append(f"{line}: imports the door's private {alias.name}")
                if full == DOOR_MODULE:
                    door_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.Attribute):
            if node.attr in PARQUET_READERS:
                found.append(f"{line}: calls the Parquet reader {node.attr}")
        elif isinstance(node, ast.Name) and node.id in PARQUET_READERS:
            found.append(f"{line}: calls the Parquet reader {node.id}")
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and FORBIDDEN_TEXT.search(node.value)
        ):
            found.append(f"{line}: string {node.value!r}")
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr.startswith("_")
            and not node.attr.startswith("__")
            and ast.unparse(node.value) in door_aliases
        ):
            found.append(f"{node.lineno}: reaches the door's private {node.attr}")
    return found


def test_no_module_but_the_door_reaches_the_base_or_opens_parquet() -> None:
    checked = [p for p in sorted(PACKAGE.rglob("*.py")) if p != DOOR]
    assert len(checked) >= 5, "the walk must see the package"
    found = {
        str(path.relative_to(ROOT)): problems
        for path in checked
        if (
            problems := violations(
                path.read_text(encoding="utf-8"), module_name(path), path.name == "__init__.py"
            )
        )
    }
    assert found == {}


def test_the_door_is_where_the_check_thinks() -> None:
    assert data.__file__ is not None and Path(data.__file__).resolve() == DOOR.resolve()
    assert any("ftbase" in v for v in violations(DOOR.read_text("utf-8"), DOOR_MODULE))


REJECTED = [
    "import ftbase.silver",
    "from ftbase.silver import read_frames",
    "from ftbase import silver",
    "from ftbase.silver.read import connect",
    "from ftbase.bronze.common import bronze_path",
    "import ftbase",
    "import duckdb",
    "import duckdb as db",
    "from pyarrow import dataset",
    "import pyarrow.dataset as ds",
    "import pyarrow.parquet as pq\npq.read_table('x')",
    "from pyarrow.parquet import ParquetFile",
    "import pandas as pd\npd.read_parquet('x')",
    "import polars as pl\npl.scan_parquet('x')",
    "import importlib\nimportlib.import_module('ftbase.silver')",
    "__import__('duck' 'db')",
    "from pathlib import Path\nPath('data') / 'silver' / 'frames'",
    "x = f'{root}/silver/frames'",
    "from ac2fb.protocol.data import _silver",
    "from ..protocol.data import _admit",
    "from ac2fb.protocol import data\ndata._silver.read_frames([1])",
    "import ac2fb.protocol.data as d\nd._admit([1])",
    "import ac2fb.protocol.data\nac2fb.protocol.data._silver",
]

ACCEPTED = [
    "from ac2fb.protocol.data import read_frames\nread_frames([1874553])",
    "from ..protocol import data\ndata.read_events([1874553])",
    '"""Reads the base\'s silver through ac2fb.protocol.data."""',
    'def f() -> None:\n    """Silver frames, via the door."""',
    "import pyarrow.parquet as pq\npq.write_table(table, 'reports/out.parquet')",
    "import pyarrow as pa\npa.table({'x': [1]})",
    "class A:\n    def __init__(self) -> None:\n        self._cache = {}",
]


@pytest.mark.parametrize("source", REJECTED)
def test_the_check_rejects(source: str) -> None:
    assert violations(source, "ac2fb.reliability.gaps") != []


@pytest.mark.parametrize("source", ACCEPTED)
def test_the_check_lets_through(source: str) -> None:
    assert violations(source, "ac2fb.reliability.gaps") == []
