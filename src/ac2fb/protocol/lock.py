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

Names are compared normalised (PEP 503). This module reads no data.
"""

from __future__ import annotations

import importlib.metadata
import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

__all__ = [
    "Installed",
    "Locked",
    "installed_packages",
    "lock_mismatches",
    "locked_packages",
    "normalise",
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
