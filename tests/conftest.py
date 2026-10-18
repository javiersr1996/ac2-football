"""A skipped test is a failure here; and the fixtures of the tests on the data door.

Nothing in the gate has a reason to skip. A skip would mean a test that no longer runs and no
longer protects anything: the session ends with a failing exit status and names what was skipped.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from gate_helpers import Checkout, build_silver_pair, make_checkout, poisoned_copy

from ac2fb.protocol import data


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    skipped = reporter.stats.get("skipped", []) if reporter is not None else []
    if skipped:
        names = ", ".join(sorted({getattr(r, "nodeid", str(r)) for r in skipped}))
        if reporter is not None:
            reporter.write_line(
                f"FAILED: {len(skipped)} skipped test(s) count as failures: {names}"
            )
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


# --- the data door: synthetic silver under real split ids, and a throwaway checkout ---


@pytest.fixture(scope="session")
def silver_pair(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Data dir with the base's silver for the synthetic ``CAL`` and ``HELD`` matches."""
    return build_silver_pair(tmp_path_factory.mktemp("pair"))


@pytest.fixture(scope="session")
def poisoned_pair(silver_pair: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The same, with every per-match file of ``HELD`` replaced by garbage."""
    return poisoned_copy(silver_pair, tmp_path_factory.mktemp("poisoned") / "data")


@pytest.fixture
def checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Checkout:
    """A checkout in stage ``design``, which the gate takes for its own."""
    repo = make_checkout(tmp_path / "repo")
    monkeypatch.setattr(data, "_repo_root", lambda: repo.root)
    return repo


@pytest.fixture
def gate(checkout: Checkout, silver_pair: Path, monkeypatch: pytest.MonkeyPatch) -> Checkout:
    """The checkout, with the gate reading the readable pair."""
    monkeypatch.setenv(data.DATA_ROOT_ENV, str(silver_pair))
    return checkout


@pytest.fixture
def poisoned_gate(
    checkout: Checkout, poisoned_pair: Path, monkeypatch: pytest.MonkeyPatch
) -> Checkout:
    """The checkout, with the gate reading the pair whose held-out files are garbage."""
    monkeypatch.setenv(data.DATA_ROOT_ENV, str(poisoned_pair))
    return checkout
