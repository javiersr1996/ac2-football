"""One door to the data: only ``ac2fb.protocol.data`` reaches the base or opens a data file.

The check walks the syntax tree of every module under ``src/ac2fb`` except the door and
rejects: importing ``ftbase`` (any part of it: silver, bronze and raw hold the held-out matches
too), ``duckdb``, ``pandas``, ``polars`` or ``fastparquet``; importing any part of ``pyarrow``
but the in-memory ``pyarrow`` and ``pyarrow.compute`` and ``pyarrow.parquet`` (kept for
writing: ``reliability.long``), or reaching a private or input module of ``pyarrow`` through
an alias (``pa._parquet``, ``pa.ipc``); calling, importing or naming a file reader (a Parquet,
CSV, JSON, IPC or NumPy reader, a memory map, a stream); opening or listing a file (``open``,
``read_text``, ``read_bytes``, ``glob``, ``listdir`` and the like) outside
:data:`ALLOWED_FILE_SITES`; naming the data root (``data_dir``, ``DATA_ROOT_ENV``) outside
:data:`ALLOWED_DATA_ROOT`; reaching a private name of the door; and any string, outside
docstrings, that names ``ftbase``, ``duckdb``, ``silver``, ``bronze``, ``pandas``, ``polars``,
``jsonl`` or ``_parquet`` (the way to a dynamic import or to a data path). The one allowance
(:data:`ALLOWED_FILE_SITES`) is a site, not a module: one function, one call, one receiver. The
checker is itself tested on snippets it must reject and snippets it must let through. A
determined bypass (a subprocess, a path spelt in pieces) is out of its reach: the check catches
the plain ways.
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

FORBIDDEN_MODULES = (
    "ftbase",
    "duckdb",
    "pandas",
    "polars",
    "fastparquet",
    "fileinput",
    "linecache",
)
# The parts of pyarrow a module may import: tables in memory, compute, and Parquet writing.
PYARROW_ALLOWED = ("pyarrow", "pyarrow.compute", "pyarrow.parquet")
PYARROW_INPUT = frozenset(
    {"csv", "cuda", "dataset", "feather", "flight", "fs", "hdfs", "ipc", "json", "orc"}
)
READERS = frozenset(
    {
        "FileIO",
        "OSFile",
        "ParquetDataset",
        "ParquetFile",
        "ParquetReader",
        "PythonFile",
        "create_memory_map",
        "fromfile",
        "genfromtxt",
        "input_stream",
        "load",
        "loadtxt",
        "memmap",
        "memory_map",
        "copyfile",
        "copyfileobj",
        "open_file",
        "open_input_file",
        "open_code",
        "open_input_stream",
        "open_stream",
        "read_csv",
        "read_feather",
        "read_ipc",
        "read_json",
        "read_metadata",
        "read_ndjson",
        "read_pandas",
        "read_parquet",
        "read_schema",
        "read_table",
        "scan_csv",
        "scan_ndjson",
        "scan_parquet",
    }
)
# Names that open or list a file, called or merely mentioned (``f = open; f(p)``).
FILE_CALLS = frozenset(
    {"glob", "iterdir", "listdir", "open", "read_bytes", "read_text", "rglob", "scandir", "walk"}
)
STATUS_FIELD = ("status", "open")  # the guard's `status.open` flag, read in `cli` and the door
# The one allowance, by site: (module, function, call, receiver). The command line reads the
# three probe reports there, and hands the verdicts to `power`, which opens nothing.
ALLOWED_FILE_SITES = frozenset(
    {
        ("ac2fb.cli", "_probe_verdicts", "read_text", "probes_dir / name"),
        ("ac2fb.cli", "_read_protocol", "read_text", "path"),
    }
)
DATA_ROOT_NAMES = frozenset({"DATA_ROOT_ENV", "data_dir"})
# `cli` prints the data root; `reliability.long` writes layer 2's Parquet under it.
ALLOWED_DATA_ROOT = frozenset({"ac2fb.cli", "ac2fb.reliability.long"})
FORBIDDEN_TEXT = re.compile(
    r"ftbase|duckdb|silver|bronze|pandas|polars|jsonl|_parquet", re.IGNORECASE
)


def module_name(path: Path) -> str:
    parts = path.relative_to(PACKAGE.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _under(name: str, module: str) -> bool:
    return name == module or name.startswith(module + ".")


def _forbidden(name: str) -> bool:
    if any(_under(name, m) for m in FORBIDDEN_MODULES):
        return True
    if not _under(name, "pyarrow") or name == "pyarrow":
        return False
    return not any(_under(name, m) for m in PYARROW_ALLOWED[1:])


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


def _enclosing(tree: ast.AST) -> dict[int, str]:
    """The innermost function around each node, by node id ("" at module level)."""
    where: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for child in ast.walk(node):
                where[id(child)] = node.name
    return where


def violations(source: str, module: str, is_package: bool = False) -> list[str]:
    """Every way ``source`` reaches the data without the door, one line each."""
    tree = ast.parse(source)
    docstrings = _docstrings(tree)
    door_aliases = {"ac2fb.protocol.data"}
    arrow_aliases = {"pyarrow"}
    root_allowed = module in ALLOWED_DATA_ROOT
    enclosing = _enclosing(tree)
    called: set[int] = set()  # the attributes that are called
    permitted: set[int] = set()  # the openers of an allowed site
    found: list[str] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _forbidden(alias.name):
                    found.append(f"{line}: import {alias.name}")
                if alias.name == DOOR_MODULE:
                    door_aliases.add(alias.asname or alias.name)
                if _under(alias.name, "pyarrow"):
                    arrow_aliases.add(alias.asname or alias.name.partition(".")[0])
        elif isinstance(node, ast.ImportFrom):
            base = _absolute(node, module, is_package)
            for alias in node.names:
                full = f"{base}.{alias.name}"
                if _forbidden(base) or _forbidden(full):
                    found.append(f"{line}: from {base} import {alias.name}")
                if alias.name in READERS or alias.name in FILE_CALLS:
                    found.append(f"{line}: imports the file reader {alias.name}")
                if base == DOOR_MODULE and alias.name.startswith("_"):
                    found.append(f"{line}: imports the door's private {alias.name}")
                if alias.name in DATA_ROOT_NAMES and not root_allowed:
                    found.append(f"{line}: imports the data root {alias.name}")
                if full == DOOR_MODULE:
                    door_aliases.add(alias.asname or alias.name)
                if _under(full, "pyarrow"):
                    arrow_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                called.add(id(func))
                site = (module, enclosing.get(id(node), ""), func.attr, ast.unparse(func.value))
                if site in ALLOWED_FILE_SITES:
                    permitted.add(id(func))
        elif isinstance(node, ast.Attribute):
            owner_attr = (ast.unparse(node.value), node.attr)
            exempt = owner_attr == STATUS_FIELD and id(node) not in called
            if node.attr in FILE_CALLS and id(node) not in permitted and not exempt:
                found.append(f"{line}: opens or lists a file with {node.attr}")
            if node.attr in READERS:
                found.append(f"{line}: calls the file reader {node.attr}")
            if node.attr in DATA_ROOT_NAMES and not root_allowed:
                found.append(f"{line}: reaches the data root {node.attr}")
        elif isinstance(node, ast.Name) and node.id in FILE_CALLS:
            found.append(f"{line}: names the file opener {node.id}")
        elif isinstance(node, ast.Name) and node.id in READERS:
            found.append(f"{line}: calls the file reader {node.id}")
        elif isinstance(node, ast.Name) and node.id in DATA_ROOT_NAMES and not root_allowed:
            found.append(f"{line}: reaches the data root {node.id}")
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and FORBIDDEN_TEXT.search(node.value)
        ):
            found.append(f"{line}: string {node.value!r}")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        private = node.attr.startswith("_") and not node.attr.startswith("__")
        owner = ast.unparse(node.value)
        if private and owner in door_aliases:
            found.append(f"{node.lineno}: reaches the door's private {node.attr}")
        if (private or node.attr in PYARROW_INPUT) and owner in arrow_aliases:
            found.append(f"{node.lineno}: reaches pyarrow's {node.attr}")
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
    # The holes of review 18: pyarrow's private Parquet reader, and a raw file opened by hand.
    "import pyarrow._parquet as pp\npp.ParquetReader()",
    "from pyarrow._parquet import ParquetReader",
    "from pyarrow import _parquet",
    "import pyarrow as pa\npa._parquet.ParquetReader().open(path)",
    "import pyarrow as pa\nreader = pa._parquet",
    "with open(path) as f:\n    rows = [json.loads(line) for line in f]",
    "import io\nio.open(path)",
    "from pathlib import Path\nPath(path).read_bytes()",
    "from pathlib import Path\nPath(path).read_text(encoding='utf-8')",
    "import os\nos.listdir(path)",
    "from pathlib import Path\nlist(Path(path).rglob('*.parquet'))",
    "from ac2fb.protocol.data import data_dir\nroot = data_dir()",
    "from ac2fb.protocol import data\nroot = data.data_dir() / 'raw'",
    "from ac2fb.protocol import data\nimport os\nos.environ[data.DATA_ROOT_ENV]",
    "import pandas as pd",
    "import polars",
    "from fastparquet import ParquetFile",
    "from pyarrow import csv",
    "import pyarrow.ipc",
    "import pyarrow.json as pj",
    "import pyarrow as pa\npa.memory_map(path)",
    "import pyarrow as pa\npa.OSFile(path)",
    "import pyarrow as pa\npa.input_stream(path)",
    "reader = ParquetReader()",
    "import numpy as np\nnp.fromfile(path)",
    "import pyarrow as pa\npa.ipc.open_file(path)",
    "import pyarrow as pa\npa.dataset.dataset(path)",
    "import pyarrow.parquet as pq\npq.ParquetDataset(path)",
    "import numpy as np\nnp.load(path)",
    "import importlib\nimportlib.import_module('pyarrow._parquet')",
    "name = 'match.jsonl'",
    # Review 18, pass 2: openers named without a call, and readers the list did not know.
    "from pathlib import Path\nPath(path).read_text()",
    "import io\nio.FileIO(path)",
    "from io import FileIO",
    "import io\nio.open_code(path)",
    "import linecache\nlinecache.getlines(path)",
    "from linecache import getlines",
    "import fileinput\nfileinput.input(path)",
    "import shutil\nshutil.copyfile(path, other)",
    "from shutil import copyfile",
    "f = open\nf(path)",
    "import io\nf = io.open\nf(path)",
    "from pathlib import Path\nf = Path(path).read_bytes\nf()",
    "import os\nf = os.listdir\nf(path)",
    "import io\nio.open(path) ",
    "x = f'{root}/bronze/football'",
    # Review 18, pass 3: the status flag is exempt only when read; aliased opener imports.
    "from pathlib import Path\nstatus = Path(p)\nstatus.open().read()",
    "import io as status\nstatus.open(p)",
    "from io import open as o\no(path)",
    "from os import listdir as ls\nls(path)",
]

ACCEPTED = [
    "from ac2fb.protocol.data import read_frames\nread_frames([1874553])",
    "from ..protocol import data\ndata.read_events([1874553])",
    '"""Reads the base\'s silver through ac2fb.protocol.data."""',
    'def f() -> None:\n    """Silver frames, via the door."""',
    "import pyarrow.parquet as pq\npq.write_table(table, 'reports/out.parquet')",
    "import pyarrow as pa\npa.table({'x': [1]})",
    "import pyarrow.compute as pc\npc.equal(table['a'], 1)",
    "class A:\n    def __init__(self) -> None:\n        self._cache = {}",
    "print('held-out: open' if status.open else 'held-out: locked')",
    "from pathlib import Path\nPath(path).write_bytes(body)",
]


def test_the_allowances_are_by_site() -> None:
    # Reading the probe reports is one function of the CLI's; the data root is the CLI's and
    # layer 2's.
    site = (
        "import json\n"
        "def _probe_verdicts(probes_dir):\n"
        "    return json.loads((probes_dir / name).read_text(encoding='utf-8'))"
    )
    assert violations(site, "ac2fb.cli") == []
    # Another module, another function, another receiver or another call: none is the site.
    assert violations(site, "ac2fb.defence.power") != []
    assert violations(site.replace("_probe_verdicts", "_other"), "ac2fb.cli") != []
    assert violations(site.replace("probes_dir / name", "Path(any)"), "ac2fb.cli") != []
    assert (
        violations(site.replace("read_text(encoding='utf-8')", "read_bytes()"), "ac2fb.cli") != []
    )
    root = "from ac2fb.protocol import data\nout = data.data_dir() / 'layer2'"
    assert violations(root, "ac2fb.reliability.long") == []
    assert violations("from ac2fb.protocol.data import data_dir", "ac2fb.cli") == []
    assert violations(root, "ac2fb.reliability.match") != []
    assert violations("open(path)", "ac2fb.cli") != []


@pytest.mark.parametrize("source", REJECTED)
def test_the_check_rejects(source: str) -> None:
    assert violations(source, "ac2fb.reliability.gaps") != []


@pytest.mark.parametrize("source", ACCEPTED)
def test_the_check_lets_through(source: str) -> None:
    assert violations(source, "ac2fb.reliability.gaps") == []
