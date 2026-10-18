"""Every public route of ``ac2fb`` refuses a held-out match while the held-out is locked.

The routes are enumerated, not listed by hand: every function in the ``__all__`` of every
module of the package, and every command of the CLI. Each one must have an entry in
:data:`FUNCTION_ROUTES` or :data:`CLI_ROUTES` saying how to drive it with a match id, or that it
takes none; a new route without an entry fails :func:`test_the_route_tables_cover_every_route`.

The routes run against data whose held-out files are garbage (``poisoned_gate``): a route that
takes a match must raise :class:`HeldOutLocked` for ``HELD`` (an unguarded read would return
rows, or fail on the garbage with another error) and serve ``CAL``; a route that takes none must
finish (one that opened a held-out file would fail on the garbage).
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import inspect
import pkgutil
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from types import ModuleType
from typing import Any

import pyarrow as pa
import pytest
from ftbase import silver
from gate_helpers import CAL, HELD, POISON, Checkout

import ac2fb
from ac2fb import cli
from ac2fb.protocol import data
from ac2fb.protocol.data import HeldOutLocked

DIMS = ("dim_sport", "dim_period", "dim_team", "dim_match", "dim_team_period", "dim_entity")


@dataclass(frozen=True)
class Route:
    """How to drive one route: ``calls`` take a match id when ``takes_match``, else nothing."""

    takes_match: bool
    calls: tuple[Callable[..., Any], ...]


def by_match(*calls: Callable[[int], Any]) -> Route:
    return Route(True, calls)


def without_match(*calls: Callable[[], Any]) -> Route:
    return Route(False, calls)


FUNCTION_ROUTES: dict[str, Route] = {
    "ac2fb.cli.build_parser": without_match(cli.build_parser),
    "ac2fb.cli.main": without_match(lambda: cli.main([])),
    "ac2fb.protocol.data.code_tree_sha": without_match(data.code_tree_sha),
    "ac2fb.protocol.data.data_dir": without_match(data.data_dir),
    "ac2fb.protocol.data.guard_status": without_match(data.guard_status),
    "ac2fb.protocol.data.load_split": without_match(data.load_split),
    "ac2fb.protocol.data.read_frames": by_match(
        lambda m: data.read_frames([m]),
        lambda m: data.read_frames([m], attacking=True),
        lambda m: data.read_frames([m], columns=["native_match_id"]),
    ),
    "ac2fb.protocol.data.read_events": by_match(lambda m: data.read_events([m])),
    "ac2fb.protocol.data.read_dim": by_match(
        *[lambda m, name=name: data.read_dim(name, [m]) for name in DIMS]
    ),
}

CLI_ROUTES: dict[tuple[str, ...], Route] = {
    ("status",): without_match(lambda: cli.main(["status"])),
}


def modules() -> Iterator[ModuleType]:
    yield ac2fb
    for info in pkgutil.walk_packages(ac2fb.__path__, "ac2fb."):
        yield importlib.import_module(info.name)


def exported_functions() -> set[str]:
    return {
        f"{module.__name__}.{name}"
        for module in modules()
        for name in module.__all__
        if inspect.isfunction(getattr(module, name))
    }


def cli_commands(
    parser: argparse.ArgumentParser, prefix: tuple[str, ...] = ()
) -> set[tuple[str, ...]]:
    found: set[tuple[str, ...]] = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                found |= {prefix + (name,)} | cli_commands(sub, prefix + (name,))
    return found


def routes() -> list[tuple[str, Route]]:
    return [*FUNCTION_ROUTES.items(), *((" ".join(k), v) for k, v in CLI_ROUTES.items())]


def match_ids_in(table: pa.Table) -> set[str]:
    if "native_match_id" in table.column_names:
        return {f"fb:{m}" for m in table["native_match_id"].to_pylist()}
    if "match_id" in table.column_names:
        return set(table["match_id"].to_pylist())
    return set()


# --- the tables cover every route ----------------------------------------------------------------


def test_every_module_exports_all_its_public_names() -> None:
    # A public function left out of __all__ would also be left out of the enumeration.
    for module in modules():
        assert hasattr(module, "__all__"), f"{module.__name__} has no __all__"
        defined = {
            name
            for name, obj in vars(module).items()
            if not name.startswith("_")
            and (inspect.isfunction(obj) or inspect.isclass(obj))
            and obj.__module__ == module.__name__
        }
        assert defined <= set(module.__all__), (module.__name__, defined - set(module.__all__))


def test_exported_classes_hold_no_reader() -> None:
    # Routes are functions; an exported class may only be an exception or plain data.
    for module in modules():
        for name in module.__all__:
            obj = getattr(module, name)
            if not inspect.isclass(obj) or issubclass(obj, Exception):
                continue
            assert dataclasses.is_dataclass(obj), f"{module.__name__}.{name}"
            methods = [
                attr
                for attr, value in vars(obj).items()
                if not attr.startswith("_") and inspect.isfunction(value)
            ]
            assert methods == [], f"{module.__name__}.{name} has methods {methods}"


def test_the_route_tables_cover_every_route() -> None:
    functions = exported_functions()
    assert set(FUNCTION_ROUTES) == functions, (
        f"not in FUNCTION_ROUTES: {sorted(functions - set(FUNCTION_ROUTES))}; "
        f"no longer exported: {sorted(set(FUNCTION_ROUTES) - functions)}"
    )
    commands = cli_commands(cli.build_parser())
    assert set(CLI_ROUTES) == commands, (
        f"not in CLI_ROUTES: {sorted(commands - set(CLI_ROUTES))}; "
        f"gone: {sorted(set(CLI_ROUTES) - commands)}"
    )


def test_the_enumeration_sees_the_readers_and_the_cli() -> None:
    # Guard against an enumeration that finds nothing and so covers nothing.
    assert {"ac2fb.protocol.data.read_frames", "ac2fb.cli.main"} <= exported_functions()
    assert ("status",) in cli_commands(cli.build_parser())


# --- the sweep -----------------------------------------------------------------------------------


def test_the_poison_is_real(poisoned_pair: Any) -> None:
    assert (poisoned_pair / "silver" / "frames" / f"{HELD}.parquet").read_bytes() == POISON
    with pytest.raises(Exception, match="(?i)parquet|magic|invalid|corrupt"):
        silver.read_frames([HELD], data_dir=poisoned_pair)
    assert silver.read_frames([CAL], data_dir=poisoned_pair).num_rows > 0


@pytest.mark.parametrize("route", [pytest.param(r, id=n) for n, r in routes() if r.takes_match])
def test_every_route_that_takes_a_match_refuses_a_heldout_one(
    poisoned_gate: Checkout, route: Route
) -> None:
    for call in route.calls:
        with pytest.raises(HeldOutLocked):
            call(HELD)


@pytest.mark.parametrize("route", [pytest.param(r, id=n) for n, r in routes() if r.takes_match])
def test_every_route_that_takes_a_match_serves_a_calibration_one(
    poisoned_gate: Checkout, route: Route
) -> None:
    for call in route.calls:
        table = call(CAL)
        assert table.num_rows > 0
        assert match_ids_in(table) <= {f"fb:{CAL}"}


@pytest.mark.parametrize("route", [pytest.param(r, id=n) for n, r in routes() if not r.takes_match])
def test_every_route_without_a_match_never_opens_a_heldout_file(
    poisoned_gate: Checkout, route: Route
) -> None:
    for call in route.calls:
        call()


@pytest.mark.parametrize("route", [pytest.param(r, id=n) for n, r in routes() if r.takes_match])
def test_with_the_heldout_open_every_route_serves_it(gate: Checkout, route: Route) -> None:
    gate.freeze()
    for call in route.calls:
        table = call(HELD)
        assert table.num_rows > 0
        assert match_ids_in(table) <= {f"fb:{HELD}"}
