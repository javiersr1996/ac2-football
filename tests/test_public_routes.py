"""Every public route of ``ac2fb`` refuses a held-out match outside the reading, in every stage.

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
import contextlib
import dataclasses
import importlib
import inspect
import io
import json
import pkgutil
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pyarrow as pa
import pytest
from ftbase import silver
from gate_helpers import CAL, HELD, POISON, ROOT, Checkout, inside_the_reading

import ac2fb
from ac2fb import cli
from ac2fb.defence import (
    bar,
    block,
    calibration,
    design,
    effect,
    line,
    m10,
    power,
    pressure,
    probe_s1,
    probe_s2,
    probe_s3,
)
from ac2fb.protocol import check as protocol_check
from ac2fb.protocol import data, lock
from ac2fb.protocol.data import HeldOutLocked
from ac2fb.reliability import (
    amputate,
    cadence,
    inventory,
    long,
    metrics,
    report,
    runs,
    table,
    visibility,
)
from ac2fb.reliability import match as match_module
from ac2fb.reliability.sensitivity import (
    Reading,
    Window,
    WindowFrames,
    sensitivity,
    sensitivity_by_size,
    window_frames,
)

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


OUT = tempfile.mkdtemp(prefix="ac2fb-routes-")  # where the routes that write put their files
FRAME_COLUMNS = [
    "match_id", "native_match_id", "period", "frame_native", "entity_id", "entity_kind",
    "team_id", "x_m", "y_m", "is_detected",
]  # fmt: skip


def served(match: int, ok: bool) -> pa.Table:
    """A route that returns something other than a table says it served the match this way."""
    assert ok
    return pa.table({"match_id": [f"fb:{match}"]})


def loaded(m: int) -> match_module.MatchData:
    return match_module.load_match(m)


def on_match(check: Callable[[match_module.MatchData], object]) -> Route:
    """A route driven by one loaded match: served when ``check`` returns something truthy."""
    return by_match(lambda m: served(m, bool(check(loaded(m)))))


def long_of(m: int) -> pa.Table:
    return long.long_table(data.read_frames([m], columns=FRAME_COLUMNS))


def layer2_command(m: int) -> pa.Table:
    """The ``layer2`` command for one match: exit 2 and a refusal on stderr is a refusal."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = cli.main(["layer2", "--match", str(m), "--reports-dir", OUT])
    if code == 2 and "held-out" in err.getvalue():
        raise HeldOutLocked(err.getvalue())
    assert code == 0, err.getvalue()
    return served(m, True)


def reliability_command(m: int) -> pa.Table:
    """The ``reliability`` command for one match: exit 2 and a refusal on stderr is a refusal."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = cli.main(["reliability", "--match", str(m), "--reports-dir", OUT])
    if code == 2 and "held-out" in err.getvalue():
        raise HeldOutLocked(err.getvalue())
    assert code == 0, err.getvalue()
    return served(m, True)


def checked_table(m: int) -> pa.Table:
    """The table's check for one match, against a file that holds only the header."""
    return served(m, table.check([m], table.render([]).encode("utf-8")).matches == 1)


def checked_amputation(m: int) -> pa.Table:
    """The amputation's check for one match, against a file that holds only the header."""
    header = table.render_csv(amputate.COLUMNS, []).encode("utf-8")
    return served(m, amputate.check([m], header).matches == 1)


def checked_csv(m: int) -> pa.Table:
    """The generic check for one match, its rows built by the table's guarded reader."""
    raw = table.render([]).encode("utf-8")
    got = table.check_csv("x.csv", table.COLUMNS, 4, [m], table.match_rows, raw)
    return served(m, got.rows > 0)


def checked_layer2(m: int) -> pa.Table:
    """The report's check for one match, against an empty JSON object."""
    return served(m, report.check([m], b"{}").values == 0)


def amputation_command(m: int) -> pa.Table:
    """The ``amputation`` command for one match: exit 2 and a refusal on stderr is a refusal."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = cli.main(["amputation", "--match", str(m), "--reports-dir", OUT])
    if code == 2 and "held-out" in err.getvalue():
        raise HeldOutLocked(err.getvalue())
    assert code == 0, err.getvalue()
    return served(m, True)


def layer2_check_command(m: int) -> pa.Table:
    """``layer2 --check`` for one match against an empty report: a refusal is exit 2.

    The file must exist: without one the check stops before it reads any match.
    """
    where = Path(tempfile.mkdtemp(prefix="ac2fb-layer2-check-"))
    (where / report.REPORT_NAME).write_bytes(b"{}\n")
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = cli.main(["layer2", "--check", "--match", str(m), "--reports-dir", str(where)])
    if code == 2 and "held-out" in err.getvalue():
        raise HeldOutLocked(err.getvalue())
    assert code in (0, 1), err.getvalue()
    return served(m, True)


def the_hiding(mt: match_module.MatchData) -> bool:
    return len(amputate.hiding(mt).probability) == len(visibility.BALL_DISTANCE_EDGES) + 1


def amputated(mt: match_module.MatchData) -> bool:
    """The amputation of one metric on a loaded match, with its long table rebuilt from it."""
    frames = window_frames(long_of(mt.match_id))
    metric, windows = metrics.metric_units(mt)["nearest_rival_m"]
    got = amputate.amputate(
        mt, frames, metric, windows, amputate.hiding(mt), np.random.default_rng(0)
    )
    return got.n_units >= 0


def first_ends(mt: match_module.MatchData) -> bool:
    sides = amputate.detected_sides(mt)
    amputate.ends_of(mt, sides, int(mt.player[0]), int(mt.frame[0]), 1, 1)
    return len(sides[0]) == len(mt.frame)


def first_window(m: int) -> pa.Table:
    """The matrices of the first 100 frames of the match."""
    long = long_of(m)
    first = int(np.min(long["frame"].to_numpy()))
    return served(m, window_frames(long)(Window(m, first, first + 99)) is not None)


def cadence_command(m: int) -> pa.Table:
    """The ``cadence`` command for one match: exit 2 and a refusal on stderr is a refusal."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = cli.main(["cadence", "--match", str(m), "--reports-dir", OUT])
    if code == 2 and "held-out" in err.getvalue():
        raise HeldOutLocked(err.getvalue())
    assert code == 0, err.getvalue()
    return served(m, True)


def s1_command(m: int) -> pa.Table:
    """The ``s1`` command for one match: exit 2 and a refusal on stderr is a refusal."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = cli.main(["s1", "--match", str(m), "--reports-dir", OUT])
    if code == 2 and "held-out" in err.getvalue():
        raise HeldOutLocked(err.getvalue())
    assert code == 0, err.getvalue()
    return served(m, True)


def s2_command(m: int) -> pa.Table:
    """The ``s2`` command for one match: exit 2 and a refusal on stderr is a refusal."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = cli.main(["s2", "--match", str(m), "--reports-dir", OUT])
    if code == 2 and "held-out" in err.getvalue():
        raise HeldOutLocked(err.getvalue())
    assert code == 0, err.getvalue()
    return served(m, True)


def s3_command(m: int) -> pa.Table:
    """The ``s3`` command for one match: exit 2 and a refusal on stderr is a refusal."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = cli.main(["s3", "--match", str(m), "--reports-dir", OUT])
    if code == 2 and "held-out" in err.getvalue():
        raise HeldOutLocked(err.getvalue())
    assert code == 0, err.getvalue()
    return served(m, True)


def power_command(m: int) -> pa.Table:
    """The ``power`` command for one match: exit 2 and a refusal on stderr is a refusal."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = cli.main(["power", "--match", str(m), "--reports-dir", OUT])
    if code == 2 and "held-out" in err.getvalue():
        raise HeldOutLocked(err.getvalue())
    assert code == 0, err.getvalue()
    return served(m, True)


def calibration_command(m: int) -> pa.Table:
    """The ``calibration`` command for one match: exit 2 and a refusal on stderr is a refusal."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = cli.main(["calibration", "--match", str(m), "--reports-dir", OUT])
    if code == 2 and "held-out" in err.getvalue():
        raise HeldOutLocked(err.getvalue())
    assert code == 0, err.getvalue()
    return served(m, True)


def design_command(m: int) -> pa.Table:
    """The ``design`` command for one match: exit 2 and a refusal on stderr is a refusal."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = cli.main(["design", "--match", str(m), "--reports-dir", OUT])
    if code == 2 and "held-out" in err.getvalue():
        raise HeldOutLocked(err.getvalue())
    assert code == 0, err.getvalue()
    return served(m, True)


REPORTS = Path(__file__).resolve().parent.parent / "reports"  # the committed probe verdicts
VERDICTS = cli._probe_verdicts(REPORTS)
PROBE_REPORTS = {
    name: json.loads((REPORTS / name).read_text(encoding="utf-8")) for name in cli._PROBE_REPORTS
}
PROTOCOL = cli._read_protocol(cli._PROTOCOL)


def tiny_design() -> bar.Design:
    """Two matches of twelve units, half pressed, in possessions of two."""
    n = 24
    return bar.Design(
        (1, 2),
        np.repeat(np.arange(2), 12).astype(np.int64),
        ("s",) * n,
        np.array([i % 2 == 0 for i in range(n)]),
        tuple(f"p{i // 2}" for i in range(n)),
    )


def tiny_units() -> dict[int, list[power.Unit]]:
    return {
        m: [power.Unit(k, "s", k % 2 == 0, f"p{k // 2}", float(k % 3), True) for k in range(12)]
        for m in (1, 2)
    }


def tiny_effect_units() -> list[effect.EffectUnit]:
    """Two matches of twelve kept units, half pressed, one stratum, with an outcome."""
    return [
        effect.EffectUnit(
            m,
            1,
            100 + 40 * k,
            "s",
            k % 2 == 0,
            f"p{k // 2}",
            float(k % 3),
            float(k * 7 % 5 + k % 2),
            0,
            True,
        )
        for m in (1, 2)
        for k in range(12)
    ]


def a_phase(mt: match_module.MatchData) -> probe_s3.Phase:
    return probe_s3.Phase(0, int(mt.period[0]), int(mt.frame[0]), int(mt.team[0]), None, None)


def s3_inputs(m: int) -> probe_s3.MatchInputs:
    return probe_s3.load_inputs(m)


def s2_inputs(m: int) -> probe_s2.MatchInputs:
    return probe_s2.load_inputs(m)


def one_unit(window: WindowFrames) -> Reading | None:
    return Reading(0.0, ())


LOCK_TEXT = (ROOT / "uv.lock").read_text(encoding="utf-8")


def refused_reading() -> None:
    """The reading in the poisoned checkout, whose layer2.json is in design: refused unopened."""
    with pytest.raises(HeldOutLocked, match="stage 'design'"):
        data.read_heldout(Path(OUT))


def built(m: int) -> match_module.MatchData:
    return match_module.build_match(
        m,
        data.read_frames([m], columns=FRAME_COLUMNS),
        data.read_events([m]),
        data.read_dim("dim_team_period", [m]),
    )


FUNCTION_ROUTES: dict[str, Route] = {
    "ac2fb.cli.build_parser": without_match(cli.build_parser),
    "ac2fb.cli.main": without_match(lambda: cli.main([])),
    "ac2fb.protocol.data.code_tree_sha": without_match(data.code_tree_sha),
    "ac2fb.protocol.data.data_dir": without_match(data.data_dir),
    "ac2fb.protocol.data.guard_status": without_match(data.guard_status),
    "ac2fb.protocol.data.load_split": without_match(data.load_split),
    "ac2fb.protocol.data.read_heldout": without_match(refused_reading),
    "ac2fb.protocol.lock.import_mismatches": without_match(
        lambda: lock.import_mismatches(LOCK_TEXT)
    ),
    "ac2fb.protocol.lock.installed_packages": without_match(lock.installed_packages),
    "ac2fb.protocol.lock.lock_mismatches": without_match(
        lambda: lock.lock_mismatches(LOCK_TEXT, lock.installed_packages())
    ),
    "ac2fb.protocol.lock.locked_packages": without_match(lambda: lock.locked_packages(LOCK_TEXT)),
    "ac2fb.protocol.lock.normalise": without_match(lambda: lock.normalise("Typing_Extensions")),
    "ac2fb.protocol.lock.python_mismatches": without_match(lambda: lock.python_mismatches("3.13")),
    "ac2fb.protocol.data.read_frames": by_match(
        lambda m: data.read_frames([m]),
        lambda m: data.read_frames([m], attacking=True),
        lambda m: data.read_frames([m], columns=["native_match_id"]),
    ),
    "ac2fb.protocol.data.read_events": by_match(lambda m: data.read_events([m])),
    "ac2fb.protocol.data.read_bronze_events": by_match(
        lambda m: served(m, data.read_bronze_events([m], columns=["event_id"]).num_rows > 0),
        lambda m: served(m, data.read_bronze_events([m]).num_rows > 0),
    ),
    "ac2fb.protocol.data.read_bronze_phases": by_match(
        lambda m: served(m, data.read_bronze_phases([m], columns=["frame_start"]).num_rows > 0),
        lambda m: served(m, data.read_bronze_phases([m]).num_rows > 0),
    ),
    "ac2fb.protocol.data.read_bronze_players": by_match(
        lambda m: served(m, data.read_bronze_players([m], columns=["id"]).num_rows > 0),
        lambda m: served(m, data.read_bronze_players([m]).num_rows > 0),
    ),
    "ac2fb.protocol.data.read_dim": by_match(
        *[lambda m, name=name: data.read_dim(name, [m]) for name in DIMS]
    ),
    "ac2fb.defence.pressure.distance_weight": without_match(
        lambda: pressure.distance_weight(np.array([0.0, 10.0]))
    ),
    "ac2fb.defence.pressure.extrapolated_share": without_match(
        lambda: pressure.extrapolated_share([])
    ),
    "ac2fb.defence.pressure.goal_side_weight": without_match(
        lambda: pressure.goal_side_weight(np.array([1.0]))
    ),
    "ac2fb.defence.pressure.incoming_ball": on_match(
        lambda mt: isinstance(pressure.incoming_ball(mt, int(mt.frame[0]), 1, 0.0), str)
    ),
    "ac2fb.defence.pressure.level_contrast": without_match(lambda: pressure.level_contrast([], 10)),
    "ac2fb.defence.pressure.make_metric": on_match(
        lambda mt: callable(pressure.make_metric(mt, []))
    ),
    "ac2fb.defence.pressure.rival_weights": without_match(
        lambda: pressure.rival_weights((0.0, 0.0), np.array([[1.0, 0.0]]), 1)
    ),
    "ac2fb.defence.pressure.score_receptions": on_match(
        lambda mt: pressure.score_receptions(mt, []) == []
    ),
    "ac2fb.defence.pressure.stratum_counts": without_match(lambda: pressure.stratum_counts([])),
    "ac2fb.defence.probe_s1.load_inputs": by_match(
        lambda m: served(m, probe_s1.load_inputs(m).match.player.size > 0)
    ),
    "ac2fb.defence.probe_s1.match_report": by_match(
        lambda m: served(m, "contrast" in probe_s1.match_report(probe_s1.load_inputs(m)))
    ),
    "ac2fb.defence.probe_s1.receptions_from": without_match(
        lambda: probe_s1.receptions_from(
            pa.table({k: pa.array([], pa.string()) for k in ("native_family",)}),
            pa.table({k: pa.array([], pa.string()) for k in ("event_id", "event_type")}),
        )
    ),
    "ac2fb.defence.probe_s1.s1_report": by_match(
        lambda m: served(m, "verdict" in probe_s1.s1_report([probe_s1.load_inputs(m)]))
    ),
    "ac2fb.defence.probe_s1.verdict": without_match(lambda: probe_s1.verdict({})),
    "ac2fb.defence.probe_s1.write_s1_report": by_match(
        lambda m: served(m, probe_s1.write_s1_report([m], Path(OUT)).is_file())
    ),
    "ac2fb.defence.block.measure": without_match(
        lambda: block.measure(
            np.zeros(5),
            np.arange(5.0),
            np.ones(5, dtype=bool),
            np.arange(5, dtype=np.int64),
            None,
            block.DEFINITIONS[0],
        )
    ),
    "ac2fb.defence.block.name_of": without_match(lambda: block.name_of(block.DEFINITIONS[0])),
    "ac2fb.defence.block.spearman": without_match(
        lambda: block.spearman(np.arange(4.0), np.arange(4.0))
    ),
    "ac2fb.defence.probe_s3.definition_stats": by_match(
        lambda m: served(
            m,
            "reproduces"
            in probe_s3.definition_stats(
                probe_s3.observe(s3_inputs(m).match, s3_inputs(m).phases), block.DEFINITIONS[0]
            ),
        )
    ),
    "ac2fb.defence.probe_s3.load_inputs": by_match(
        lambda m: served(m, s3_inputs(m).match.player.size > 0)
    ),
    "ac2fb.defence.probe_s3.make_metric": by_match(
        lambda m: served(
            m,
            callable(
                probe_s3.make_metric(
                    s3_inputs(m).match, s3_inputs(m).phases, block.DEFINITIONS[0], "width"
                )
            ),
        )
    ),
    "ac2fb.defence.probe_s3.match_figures": by_match(
        lambda m: served(m, "fixers" in probe_s3.match_figures(s3_inputs(m), block.DEFINITIONS[0]))
    ),
    "ac2fb.defence.probe_s3.observe": by_match(
        lambda m: served(m, len(probe_s3.observe(s3_inputs(m).match, s3_inputs(m).phases)) > 0)
    ),
    "ac2fb.defence.probe_s3.phases_from": without_match(
        lambda: probe_s3.phases_from(
            pa.table({k: pa.array([], pa.int64()) for k in ("index", "period", "frame_start")})
        )
    ),
    "ac2fb.defence.probe_s3.s3_report": by_match(
        lambda m: served(m, "verdict" in probe_s3.s3_report([s3_inputs(m)]))
    ),
    "ac2fb.defence.probe_s3.select_definition": without_match(
        lambda: probe_s3.select_definition(
            {
                0: {
                    block.name_of(d): {"reproduces": False, "abs_diff_sum": None}
                    for d in block.DEFINITIONS
                }
            }
        )
    ),
    "ac2fb.defence.probe_s3.verdict": without_match(lambda: probe_s3.verdict({})),
    "ac2fb.defence.probe_s3.write_s3_report": by_match(
        lambda m: served(m, probe_s3.write_s3_report([m], Path(OUT)).is_file())
    ),
    "ac2fb.defence.bar.bar_probability": without_match(
        lambda: bar.bar_probability(bar.prepare(tiny_design()), np.zeros((2, 24)), 0.0, False)
    ),
    "ac2fb.defence.bar.draw_noise": without_match(
        lambda: bar.draw_noise(bar.prepare(tiny_design()), [0.0, 0.0], 2, np.random.default_rng(0))
    ),
    "ac2fb.defence.bar.full_passes": without_match(
        lambda: bar.full_passes(
            bar.prepare(tiny_design()),
            np.zeros((2, 24)),
            0.0,
            True,
            bar.null_draws(bar.prepare(tiny_design()), True, np.random.default_rng(0), 5),
        )
    ),
    "ac2fb.defence.bar.mde80": without_match(
        lambda: bar.mde80(tiny_design(), [0.0, 0.0], False, (1,), replicates=2)
    ),
    "ac2fb.defence.bar.null_draws": without_match(
        lambda: bar.null_draws(bar.prepare(tiny_design()), False, np.random.default_rng(0), 3)
    ),
    "ac2fb.defence.bar.pass_probability": without_match(
        lambda: bar.pass_probability(np.array([3.0]))
    ),
    "ac2fb.defence.bar.pass_rates": without_match(
        lambda: bar.pass_rates(tiny_design(), [0.0, 0.0], True, [0.0], (1,), replicates=2)
    ),
    "ac2fb.defence.bar.prepare": without_match(lambda: bar.prepare(tiny_design())),
    "ac2fb.defence.bar.within_possession_correlation": without_match(
        lambda: bar.within_possession_correlation([0.0, 1.0, 2.0], ["s"] * 3, ["a", "a", "b"])
    ),
    "ac2fb.defence.power.ball_advance": on_match(
        lambda mt: power.ball_advance(mt, int(mt.frame[0]), 1, 0) is not None or True
    ),
    "ac2fb.defence.power.block_before": on_match(
        lambda mt: (
            power.block_before(mt, {}, a_phase(mt), 0, block.DEFINITIONS[0]) is not None or True
        )
    ),
    "ac2fb.defence.power.c1_units": by_match(
        lambda m: served(m, isinstance(power.c1_units(power.load_c1(m)), tuple))
    ),
    "ac2fb.defence.power.c3_units": by_match(
        lambda m: served(m, isinstance(power.c3_units(power.load_c3(m), "width", True), list))
    ),
    "ac2fb.defence.power.candidate_power": without_match(
        lambda: power.candidate_power(tiny_units(), "routes", False, replicates=2)
    ),
    "ac2fb.defence.power.cp1_rule": without_match(
        lambda: power.cp1_rule({"C1": True, "C2": False, "C3": True}, {})
    ),
    "ac2fb.defence.power.design_of": without_match(lambda: power.design_of(tiny_units(), "V1")),
    "ac2fb.defence.power.load_c1": by_match(
        lambda m: served(m, power.load_c1(m).s1.match.player.size > 0)
    ),
    "ac2fb.defence.power.load_c3": by_match(
        lambda m: served(m, power.load_c3(m).s3.match.player.size > 0)
    ),
    "ac2fb.defence.power.phase_runs": without_match(lambda: power.phase_runs([])),
    "ac2fb.defence.power.phase_types_by_third": by_match(
        lambda m: served(m, isinstance(power.phase_types_by_third(power.load_c3(m)), dict))
    ),
    "ac2fb.defence.power.window_overlap": without_match(lambda: power.window_overlap([])),
    "ac2fb.defence.power.phase_stratum": on_match(
        lambda mt: isinstance(power.phase_stratum(mt, a_phase(mt)), str)
    ),
    "ac2fb.defence.power.possessions_from": without_match(
        lambda: power.possessions_from(
            pa.table(
                {
                    k: pa.array([], pa.string())
                    for k in ("native_family", "native_event_id", "possession_id")
                }
            )
        )
    ),
    "ac2fb.defence.power.power_report": by_match(
        lambda m: served(m, "candidates" in power.power_report([m], VERDICTS))
    ),
    "ac2fb.defence.power.pressed_at": on_match(
        lambda mt: isinstance(
            power.pressed_at(
                mt,
                pressure.Reception(
                    "e", int(mt.period[0]), int(mt.frame[0]), int(mt.team[0]), int(mt.player[0]), 1
                ),
            ),
            bool,
        )
    ),
    "ac2fb.defence.power.probe_verdicts": without_match(
        lambda: power.probe_verdicts(PROBE_REPORTS)
    ),
    "ac2fb.defence.power.write_power_report": by_match(
        lambda m: served(m, power.write_power_report([m], Path(OUT), VERDICTS).is_file())
    ),
    "ac2fb.defence.design.design_report": by_match(
        lambda m: served(m, "units" in design.design_report([m]))
    ),
    "ac2fb.defence.design.design_units": by_match(
        lambda m: served(m, isinstance(design.design_units(power.load_c1(m)), list))
    ),
    "ac2fb.defence.design.excluded_by_gap": without_match(lambda: design.excluded_by_gap([])),
    "ac2fb.defence.design.match_counts": by_match(
        lambda m: served(
            m,
            "kept" in design.match_counts(power.load_c1(m), design.design_units(power.load_c1(m))),
        )
    ),
    "ac2fb.defence.design.pooled_pretrend": without_match(
        lambda: design.pooled_pretrend(tiny_units(), "V0")
    ),
    "ac2fb.defence.design.power_units": without_match(lambda: design.power_units([], "index")),
    "ac2fb.defence.design.write_design_report": by_match(
        lambda m: served(m, design.write_design_report([m], Path(OUT)).is_file())
    ),
    "ac2fb.defence.effect.read_outcome": on_match(
        lambda mt: isinstance(
            effect.read_outcome(mt, int(mt.frame[0]), 1), effect.Outcome | type(None)
        )
    ),
    "ac2fb.defence.effect.effect_units": on_match(lambda mt: effect.effect_units([], mt) == []),
    "ac2fb.defence.effect.select_units": without_match(
        lambda: effect.select_units(tiny_effect_units(), "V1")
    ),
    "ac2fb.defence.effect.estimate": without_match(lambda: effect.estimate(tiny_effect_units())),
    "ac2fb.defence.effect.null_effects": without_match(
        lambda: effect.null_effects(tiny_effect_units(), "calibration", "V0", draws=5),
        lambda: effect.null_effects(tiny_effect_units(), "heldout", "V1", blocked=True, draws=5),
    ),
    "ac2fb.defence.effect.possession_contributions": without_match(
        lambda: effect.possession_contributions(tiny_effect_units())
    ),
    "ac2fb.defence.effect.extreme_draws": without_match(
        lambda: effect.extreme_draws(0.5, np.array([0.1, -0.7]))
    ),
    "ac2fb.defence.effect.p_value": without_match(
        lambda: effect.p_value(0.5, np.array([0.1, -0.7]))
    ),
    "ac2fb.defence.effect.permutation_test": without_match(
        lambda: effect.permutation_test(tiny_effect_units(), "calibration", "V0", draws=5)
    ),
    "ac2fb.defence.effect.sign_agreement": without_match(
        lambda: effect.sign_agreement(effect.estimate(tiny_effect_units()))
    ),
    "ac2fb.defence.effect.calibration_bar": without_match(
        lambda: effect.calibration_bar(
            effect.permutation_test(tiny_effect_units(), "calibration", "V0", draws=5)
        )
    ),
    "ac2fb.defence.effect.heldout_bars": without_match(
        lambda: effect.heldout_bars(
            {
                v: effect.permutation_test(tiny_effect_units(), "heldout", v, draws=5)
                for v in effect.VARIANTS
            }
        )
    ),
    "ac2fb.defence.effect.holm": without_match(
        lambda: effect.holm({"V0": 0.001, "V1": None}, 0.01)
    ),
    "ac2fb.defence.effect.d3": without_match(
        lambda: effect.d3(effect.estimate(tiny_effect_units()))
    ),
    "ac2fb.defence.effect.d4": without_match(
        lambda: effect.d4(
            effect.estimate(tiny_effect_units()),
            effect.estimate(effect.select_units(tiny_effect_units(), "V1")),
        )
    ),
    "ac2fb.defence.effect.v2_effects": without_match(
        lambda: effect.v2_effects(tiny_effect_units())
    ),
    "ac2fb.defence.calibration.calibration_report": by_match(
        lambda m: served(m, "verdict" in calibration.calibration_report([m]))
    ),
    "ac2fb.defence.calibration.write_calibration_report": by_match(
        lambda m: served(m, calibration.write_calibration_report([m], Path(OUT)).is_file())
    ),
    "ac2fb.defence.calibration.variance_factor": without_match(
        lambda: calibration.variance_factor(effect.estimate(tiny_effect_units()))
    ),
    "ac2fb.defence.calibration.d1": without_match(lambda: calibration.d1({1: True})),
    "ac2fb.defence.calibration.d2": without_match(lambda: calibration.d2(0.13)),
    "ac2fb.defence.calibration.d5": without_match(
        lambda: calibration.d5(
            effect.calibration_bar(
                effect.permutation_test(tiny_effect_units(), "calibration", "V0", draws=5)
            ),
            [],
        )
    ),
    "ac2fb.protocol.check.check": without_match(lambda: protocol_check.check(PROTOCOL)),
    "ac2fb.protocol.check.code_problems": without_match(
        lambda: protocol_check.code_problems(PROTOCOL)
    ),
    "ac2fb.protocol.check.coherence_problems": without_match(
        lambda: protocol_check.coherence_problems(PROTOCOL)
    ),
    "ac2fb.protocol.check.numeric_leaves": without_match(
        lambda: protocol_check.numeric_leaves(PROTOCOL)
    ),
    "ac2fb.protocol.check.schema_problems": without_match(
        lambda: protocol_check.schema_problems(PROTOCOL)
    ),
    "ac2fb.defence.line.ball_extrapolated": on_match(
        lambda mt: isinstance(line.ball_extrapolated(mt, int(mt.frame[0]), int(mt.frame[0])), bool)
    ),
    "ac2fb.defence.line.build_units": by_match(
        lambda m: served(m, isinstance(line.build_units(s2_inputs(m).match, [], (13,)), tuple))
    ),
    "ac2fb.defence.line.concordance": without_match(lambda: line.concordance([], [])),
    "ac2fb.defence.line.seen_through": on_match(
        lambda mt: (
            line.seen_through(mt, [int(mt.player[0])], int(mt.frame[0]), int(mt.frame[0])) >= 0
        )
    ),
    "ac2fb.defence.line.within_strata": without_match(lambda: line.within_strata([], [], [], 5)),
    "ac2fb.defence.m10.ball_carrier": by_match(
        lambda m: served(m, m10.ball_carrier(s2_inputs(m).match, s2_inputs(m).receptions)["n"] >= 0)
    ),
    "ac2fb.defence.m10.compare": without_match(lambda: m10.compare({}, None)),
    "ac2fb.defence.m10.direction": without_match(lambda: m10.direction(3.0)),
    "ac2fb.defence.m10.m10_units": without_match(lambda: m10.m10_units([])),
    "ac2fb.defence.m10.match_figures": without_match(lambda: m10.match_figures([])),
    "ac2fb.defence.m10.pooled_figures": without_match(lambda: m10.pooled_figures([], 0)),
    "ac2fb.defence.probe_s2.line_receptions": without_match(
        lambda: probe_s2.line_receptions(
            pa.table({k: pa.array([], pa.string()) for k in ("native_family",)}),
            pa.table({k: pa.array([], pa.string()) for k in ("event_id", "event_type")}),
        )
    ),
    "ac2fb.defence.probe_s2.load_inputs": by_match(
        lambda m: served(m, s2_inputs(m).match.player.size > 0)
    ),
    "ac2fb.defence.probe_s2.match_report": by_match(
        lambda m: served(m, "instrument" in probe_s2.match_report(s2_inputs(m)))
    ),
    "ac2fb.defence.probe_s2.s2_report": by_match(
        lambda m: served(m, "verdict" in probe_s2.s2_report([s2_inputs(m)]))
    ),
    "ac2fb.defence.probe_s2.verdict": without_match(lambda: probe_s2.verdict({}, {}, {})),
    "ac2fb.defence.probe_s2.write_s2_report": by_match(
        lambda m: served(m, probe_s2.write_s2_report([m], Path(OUT)).is_file())
    ),
    "ac2fb.reliability.cadence.cadence_of": without_match(
        lambda: cadence.cadence_of(np.array([2, 2, 3], dtype=np.int64))
    ),
    "ac2fb.reliability.cadence.cadence_report": by_match(
        lambda m: served(m, "decision" in cadence.cadence_report([loaded(m)]))
    ),
    "ac2fb.reliability.cadence.kink_gaps": on_match(lambda mt: cadence.kink_gaps(mt).size >= 0),
    "ac2fb.reliability.cadence.match_cadence": on_match(
        lambda mt: "histogram" in cadence.match_cadence(mt)
    ),
    "ac2fb.reliability.cadence.min_window": without_match(lambda: cadence.min_window([1], [3])),
    "ac2fb.reliability.cadence.write_cadence_report": by_match(
        lambda m: served(m, cadence.write_cadence_report([m], Path(OUT)).is_file())
    ),
    "ac2fb.reliability.long.gap_len": without_match(
        lambda: long.gap_len(np.zeros(2, dtype=np.int64), np.arange(2), np.array([True, False]))
    ),
    "ac2fb.reliability.long.long_dir": without_match(long.long_dir),
    "ac2fb.reliability.long.long_table": by_match(long_of),
    "ac2fb.reliability.long.write_long": by_match(
        lambda m: served(m, len(long.write_long([m], Path(OUT))) == 1)
    ),
    "ac2fb.reliability.match.build_match": by_match(lambda m: served(m, built(m).player.size > 0)),
    "ac2fb.reliability.match.load_match": on_match(lambda mt: mt.player.size > 0),
    "ac2fb.reliability.match.locate_rows": on_match(
        lambda mt: match_module.locate_rows(mt, mt.player[:3], mt.frame[:3]).min() >= 0
    ),
    "ac2fb.reliability.match.players_at": on_match(
        lambda mt: len(match_module.players_at(mt, int(mt.frame[0]))) > 0
    ),
    "ac2fb.reliability.match.load_with_long": by_match(
        lambda m: served(m, match_module.load_with_long(m)[1].num_rows > 0)
    ),
    "ac2fb.reliability.metrics.incoming_direction": on_match(
        lambda mt: metrics.incoming_direction(mt, int(mt.frame[0]), 1) in metrics.DIRECTIONS
    ),
    "ac2fb.reliability.metrics.reaction_strata": on_match(
        lambda mt: list(metrics.reaction_strata(mt)) == list(metrics.DIRECTIONS)
    ),
    "ac2fb.reliability.metrics.block_extent": without_match(
        lambda: callable(metrics.block_extent([], "width"))
    ),
    "ac2fb.reliability.metrics.line_height": on_match(
        lambda mt: callable(metrics.line_height(mt, []))
    ),
    "ac2fb.reliability.metrics.line_reaction": on_match(
        lambda mt: callable(metrics.line_reaction(mt, []))
    ),
    "ac2fb.reliability.metrics.metric_units": on_match(
        lambda mt: set(metrics.metric_units(mt)) == set(metrics.METRICS)
    ),
    "ac2fb.reliability.metrics.nearest_rival": without_match(
        lambda: callable(metrics.nearest_rival([]))
    ),
    "ac2fb.reliability.metrics.phases": without_match(lambda: metrics.phases([])),
    "ac2fb.reliability.metrics.possessions": without_match(lambda: metrics.possessions([])),
    "ac2fb.reliability.metrics.pressure_index": on_match(
        lambda mt: callable(metrics.pressure_index(mt, []))
    ),
    "ac2fb.reliability.metrics.rival_weights": without_match(
        lambda: metrics.rival_weights((0.0, 0.0), np.array([[1.0, 0.0]]), 1)
    ),
    "ac2fb.reliability.runs.acceleration_summary": on_match(runs.acceleration_summary),
    "ac2fb.reliability.runs.band_of": without_match(lambda: runs.band_of(np.array([1, 99]))),
    "ac2fb.reliability.runs.extrapolated_runs": on_match(
        lambda mt: len(runs.extrapolated_runs(mt).length) > 0
    ),
    "ac2fb.reliability.runs.linear_rounding_floor": without_match(
        lambda: runs.linear_rounding_floor(n=100)
    ),
    "ac2fb.reliability.runs.run_summary": on_match(
        lambda mt: runs.run_summary(runs.extrapolated_runs(mt))
    ),
    "ac2fb.reliability.runs.second_differences": on_match(
        lambda mt: runs.second_differences(mt)[1].any()
    ),
    "ac2fb.reliability.runs.step_summary": on_match(runs.step_summary),
    "ac2fb.reliability.runs.unlisted_stretches": on_match(runs.unlisted_stretches),
    "ac2fb.reliability.visibility.block_detection": on_match(visibility.block_detection),
    "ac2fb.reliability.visibility.defensive_line_detection": on_match(
        visibility.defensive_line_detection
    ),
    "ac2fb.reliability.visibility.detection_by_ball_distance": on_match(
        visibility.detection_by_ball_distance
    ),
    "ac2fb.reliability.visibility.detection_shares": on_match(visibility.detection_shares),
    "ac2fb.reliability.visibility.engager_detection": on_match(visibility.engager_detection),
    "ac2fb.reliability.visibility.goalkeepers": on_match(visibility.goalkeepers),
    "ac2fb.reliability.visibility.reception_detection": on_match(visibility.reception_detection),
    "ac2fb.reliability.sensitivity.window_frames": by_match(first_window),
    "ac2fb.reliability.amputate.amputate": on_match(amputated),
    "ac2fb.reliability.amputate.check": by_match(checked_amputation),
    "ac2fb.reliability.amputate.detected_sides": on_match(first_ends),
    "ac2fb.reliability.amputate.ends_of": on_match(first_ends),
    "ac2fb.reliability.amputate.fill": without_match(
        lambda: amputate.fill(
            WindowFrames(
                Window(1, 0, 0),
                *(np.zeros(1, dtype=np.int64) for _ in range(3)),
                np.zeros((1, 1)),
                np.zeros((1, 1)),
                np.ones((1, 1), dtype=np.bool_),
                np.ones((1, 1), dtype=np.bool_),
                np.zeros((1, 1), dtype=np.int64),
            ),
            {},
        )
    ),
    "ac2fb.reliability.amputate.hiding": on_match(the_hiding),
    "ac2fb.reliability.amputate.match_rows": by_match(
        lambda m: served(m, len(amputate.match_rows(m)) > 0)
    ),
    "ac2fb.reliability.amputate.write_table": by_match(
        lambda m: served(m, amputate.write_table([m], Path(OUT)).is_file())
    ),
    "ac2fb.reliability.sensitivity.sensitivity": by_match(
        lambda m: served(m, m in sensitivity(one_unit, long_of(m)))
    ),
    "ac2fb.reliability.sensitivity.sensitivity_by_size": by_match(
        lambda m: served(m, m in sensitivity_by_size(one_unit, long_of(m)))
    ),
    "ac2fb.reliability.inventory.compare": without_match(lambda: inventory.compare({}, {})),
    "ac2fb.reliability.inventory.leaf": without_match(lambda: inventory.leaf({"a": 1}, "a")),
    "ac2fb.reliability.table.check": by_match(checked_table),
    "ac2fb.reliability.table.check_csv": by_match(checked_csv),
    "ac2fb.reliability.table.cell": without_match(lambda: table.cell(0.5)),
    "ac2fb.reliability.table.render_csv": without_match(lambda: table.render_csv(("a",), [])),
    "ac2fb.reliability.table.match_rows": by_match(
        lambda m: served(m, isinstance(table.match_rows(m), list))
    ),
    "ac2fb.reliability.table.render": without_match(lambda: table.render([])),
    "ac2fb.reliability.table.write_table": by_match(
        lambda m: served(m, table.write_table([m], Path(OUT)).is_file())
    ),
    "ac2fb.reliability.report.check": by_match(checked_layer2),
    "ac2fb.reliability.report.layer2_report": by_match(
        lambda m: served(m, "inventory" in report.layer2_report([m]))
    ),
    "ac2fb.reliability.report.match_report": on_match(lambda mt: "runs" in report.match_report(mt)),
    "ac2fb.reliability.report.render_report": without_match(lambda: report.render_report({})),
    "ac2fb.reliability.report.write_report": without_match(
        lambda: report.write_report({}, Path(OUT))
    ),
}

CLI_ROUTES: dict[tuple[str, ...], Route] = {
    ("status",): without_match(lambda: cli.main(["status"])),
    ("layer2",): by_match(layer2_command, layer2_check_command),
    ("reliability",): by_match(reliability_command),
    ("amputation",): by_match(amputation_command),
    ("cadence",): by_match(cadence_command),
    ("s1",): by_match(s1_command),
    ("s2",): by_match(s2_command),
    ("s3",): by_match(s3_command),
    ("power",): by_match(power_command),
    ("design",): by_match(design_command),
    ("calibration",): by_match(calibration_command),
    ("protocol",): without_match(lambda: cli.main(["protocol", "--check"])),
    ("heldout",): without_match(lambda: cli.main(["heldout", "read", "--reports-dir", OUT])),
    ("heldout", "read"): without_match(lambda: cli.main(["heldout", "read", "--reports-dir", OUT])),
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
def test_in_stage_read_outside_the_reading_every_route_refuses_a_heldout_match(
    poisoned_gate: Checkout, route: Route
) -> None:
    # After the reading, layer 3 and everything else still refuse the held-out: only the
    # commands of layer2.json, run by read_heldout, ever see it.
    poisoned_gate.freeze("read")
    assert data.guard_status().open
    for call in route.calls:
        with pytest.raises(HeldOutLocked, match="only inside"):
            call(HELD)


@pytest.mark.parametrize("route", [pytest.param(r, id=n) for n, r in routes() if r.takes_match])
def test_inside_the_reading_every_route_serves_it(gate: Checkout, route: Route) -> None:
    gate.freeze("read")
    with inside_the_reading():
        for call in route.calls:
            table = call(HELD)
            assert table.num_rows > 0
            assert match_ids_in(table) <= {f"fb:{HELD}"}
