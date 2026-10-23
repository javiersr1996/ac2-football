"""What is installed against what ``uv.lock`` pins, for the reading of the held-out.

The frozen ``code_tree_sha`` covers ``uv.lock``, not the environment that runs the code: a
``uv pip install`` after ``uv sync`` changes what runs without changing a byte under git. So
before the reading opens anything, :func:`lock_mismatches` compares the two, and any difference
refuses the reading. The rules:

1. every installed distribution is a package of the lock, at the locked version; one locked
   from git (the base) is installed from the locked commit (its ``direct_url.json``);
2. every package that ``ac2fb`` needs at run time is installed: the closure of its dependencies
   in the lock, without the development group, following only the edges without a marker (an
   edge with a marker, such as ``colorama`` on Windows only, is required by rule 1 when present
   and not required when absent, as no marker is evaluated here).

Metadata can match while other code runs, so :func:`import_mismatches` and
:func:`python_mismatches` add:

3. every one of those run-time packages is installed once, in the environment's own
   site-packages, with every file its ``RECORD`` hashes unchanged, and each of its top-level
   modules imports from there, not from a path that shadows it (``PYTHONPATH``, a ``.pth``,
   a ``pip install --target`` with its own ``dist-info``);
4. the interpreter is the one ``.python-version`` pins (``3.13`` admits any ``3.13.x``).

Names are compared normalised (PEP 503). This module reads no data.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.metadata
import importlib.util
import platform
import re
import sysconfig
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "Installed",
    "Locked",
    "import_mismatches",
    "installed_packages",
    "lock_mismatches",
    "locked_packages",
    "normalise",
    "python_mismatches",
]

ROOT_PACKAGE = "ac2fb"


@dataclass(frozen=True)
class Locked:
    """One package of ``uv.lock``: its version, the commit if it comes from git, and its needs."""

    version: str | None
    commit: str | None
    needs: tuple[str, ...]  # dependencies without a marker, normalised


@dataclass(frozen=True)
class Installed:
    """One installed distribution: its version and, if installed from git, the commit."""

    version: str
    commit: str | None


def normalise(name: str) -> str:
    """The PEP 503 form of a distribution name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def locked_packages(lock_text: str) -> dict[str, Locked]:
    """The packages of a ``uv.lock``, by normalised name."""
    found: dict[str, Locked] = {}
    for package in tomllib.loads(lock_text)["package"]:
        git = package.get("source", {}).get("git")
        needs = tuple(
            normalise(d["name"]) for d in package.get("dependencies", []) if "marker" not in d
        )
        found[normalise(package["name"])] = Locked(
            version=package.get("version"),
            commit=git.rsplit("#", 1)[1] if git and "#" in git else None,
            needs=needs,
        )
    return found


def _commit(dist: importlib.metadata.Distribution) -> str | None:
    """The commit of a distribution installed from git (``direct_url.json``), else ``None``."""
    vcs = getattr(dist.origin, "vcs_info", None)
    commit = getattr(vcs, "commit_id", None)
    return commit if isinstance(commit, str) else None


def installed_packages(
    distributions: Iterable[importlib.metadata.Distribution] | None = None,
) -> dict[str, Installed]:
    """The distributions of the running environment, by normalised name."""
    dists = importlib.metadata.distributions() if distributions is None else distributions
    return {
        normalise(d.metadata["Name"]): Installed(version=d.version, commit=_commit(d))
        for d in dists
    }


def _closure(locked: Mapping[str, Locked], root: str) -> set[str]:
    seen: set[str] = set()
    todo = [root]
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        if name in locked:
            todo.extend(locked[name].needs)
    return seen


def lock_mismatches(lock_text: str, installed: Mapping[str, Installed]) -> list[str]:
    """Every way the installed environment differs from the lock; empty when it matches."""
    locked = locked_packages(lock_text)
    found: list[str] = []
    for name, dist in sorted(installed.items()):
        pin = locked.get(name)
        if pin is None:
            found.append(f"{name} {dist.version} is installed but not in uv.lock")
            continue
        if dist.version != pin.version:
            found.append(f"{name} is installed at {dist.version}; uv.lock pins {pin.version}")
        if pin.commit is not None and dist.commit != pin.commit:
            found.append(f"{name} is installed from {dist.commit}; uv.lock pins {pin.commit}")
    for name in sorted(_closure(locked, ROOT_PACKAGE) - set(installed)):
        found.append(f"{name} is needed at run time (uv.lock) but not installed")
    return found


def _edited(dist: importlib.metadata.Distribution) -> list[str]:
    """The files of a distribution that its ``RECORD`` hashes and that are gone or differ.

    ``RECORD`` is read as written: ``Distribution.files`` leaves out the files that are gone.
    """
    edited = []
    for path, hashed, *_ in csv.reader((dist.read_text("RECORD") or "").splitlines()):
        mode, _, value = hashed.partition("=")
        if not value:
            continue
        try:
            body = Path(str(dist.locate_file(path))).read_bytes()
        except OSError:
            edited.append(path)
            continue
        digest = base64.urlsafe_b64encode(hashlib.new(mode, body).digest()).rstrip(b"=")
        if digest.decode("ascii") != value:
            edited.append(path)
    return edited


def _in_site(path: str | Path) -> bool:
    """Whether ``path`` is under the environment's own site-packages (``purelib``, ``platlib``)."""
    site = {Path(sysconfig.get_paths()[key]).resolve() for key in ("purelib", "platlib")}
    return any(Path(path).resolve().is_relative_to(s) for s in site)


def import_mismatches(lock_text: str) -> list[str]:
    """Rule 3: every run-time package installed once, in site-packages, imported from there and
    unedited."""
    needed = _closure(locked_packages(lock_text), ROOT_PACKAGE) - {ROOT_PACKAGE}
    found: list[str] = []
    copies: dict[str, list[importlib.metadata.Distribution]] = {}
    for dist in importlib.metadata.distributions():
        copies.setdefault(normalise(dist.metadata["Name"]), []).append(dist)
    for name in sorted(needed & set(copies)):
        # One place seen twice (a `lib64 -> lib` link) is one copy; one outside site-packages is
        # caught by its modules, below.
        homes = sorted({str(Path(str(dist.locate_file(""))).resolve()) for dist in copies[name]})
        if len(homes) > 1:
            found.append(f"{name} is installed at {', '.join(homes)}, not once in site-packages")
            continue
        edited = _edited(copies[name][0])
        if edited:
            found.append(f"{name} has {len(edited)} file(s) edited since install: {edited[:3]}")
    for module, names in sorted(importlib.metadata.packages_distributions().items()):
        if not {normalise(n) for n in names} & needed:
            continue
        spec = importlib.util.find_spec(module) if module.isidentifier() else None
        if spec is None:
            continue  # a data directory of the distribution, not a module
        places = [spec.origin] if spec.origin else list(spec.submodule_search_locations or [])
        outside = [p for p in places if not _in_site(p)]
        if outside or not places:
            where = ", ".join(outside) or "nowhere"
            found.append(f"{module} is imported from {where}, not from site-packages")
    return found


def python_mismatches(pin: str, running: str | None = None) -> list[str]:
    """Rule 4: the running interpreter against the pin of ``.python-version``."""
    want = pin.strip().split(".")
    have = platform.python_version() if running is None else running
    if have.split(".")[: len(want)] != want:
        return [f"Python {have} runs; .python-version pins {'.'.join(want)}"]
    return []
