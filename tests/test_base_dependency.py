"""The base is a pinned git dependency, never a local path."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://github.com/javiersr1996/football-tracking-base"


def _toml(name: str) -> dict:  # type: ignore[type-arg]
    return tomllib.loads((ROOT / name).read_text(encoding="utf-8"))


def test_uv_sources_never_use_a_path() -> None:
    sources = _toml("pyproject.toml").get("tool", {}).get("uv", {}).get("sources", {})
    assert "ftbase" in sources, "ftbase must be declared in [tool.uv.sources]"
    for name, spec in sources.items():
        assert "path" not in spec, f"{name} uses a local path, which a clean clone cannot resolve"
        assert not spec.get("editable"), f"{name} is editable"
    assert sources["ftbase"]["git"] == BASE_URL
    assert re.fullmatch(r"v\d+\.\d+\.\d+", sources["ftbase"]["tag"])


def test_ftbase_is_a_declared_dependency() -> None:
    deps = _toml("pyproject.toml")["project"]["dependencies"]
    assert any(re.match(r"ftbase\b", d) for d in deps)


def test_lock_pins_ftbase_to_git_and_a_full_sha() -> None:
    packages = [p for p in _toml("uv.lock")["package"] if p["name"] == "ftbase"]
    assert len(packages) == 1
    git = packages[0]["source"].get("git")
    assert git is not None, f"ftbase is not a git source in uv.lock: {packages[0]['source']}"
    tag = _toml("pyproject.toml")["tool"]["uv"]["sources"]["ftbase"]["tag"]
    assert re.fullmatch(re.escape(f"{BASE_URL}?tag={tag}#") + r"[0-9a-f]{40}", git), git
