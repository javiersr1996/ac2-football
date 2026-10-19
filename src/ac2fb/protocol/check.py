"""The check of ``protocol/protocol.json``: schema, coherence, and the constants the code fixes.

The protocol is a hand-written file of literals: no number in it is read from a results file,
and this module reads no file at all (it takes the parsed protocol; the command line reads the
file and prints what :func:`check` returns). Three things are verified, and the report says how
many of each:

1. *Schema*: every field of :data:`SCHEMA` exists with its type, and the six death criteria
   are there with the plan's text.
2. *Coherence*: the rules of :func:`coherence_problems`, inside the protocol (the window in
   seconds is the frames over the frame rate, the exclusion gap is the window, the bar's count
   of null draws follows from its p and the number of draws, the Holm family is the two
   variants, a frozen protocol records a code tree sha, ...).
3. *The code*: every constant the code already fixes equals the one written in the protocol
   (:data:`CODE_CHECKS`: the window, the index's radius, goal and cut, the strata cuts, the
   label levels, the null's draws, seed and blocking threshold, the bars, the minimum per group,
   D1 to D4's numbers, the frame rate, the size of a half, the split committed at ``HEAD``).

Every numeric leaf of the protocol is accounted for: it is checked against the code
(:data:`CODE_CHECKS`), derived from other fields by a coherence rule (:data:`DERIVED`), or
declared in :data:`PROTOCOL_ONLY` (numbers no code uses yet; empty since the estimator of task
20, :mod:`ac2fb.defence.effect`, fixes the seed of the null, the held-out level and D4's ratio
and extends :data:`CODE_CHECKS`). A numeric
leaf that is none of the three is a problem, so no number enters the protocol unaccounted for.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from ac2fb.defence import bar, effect, power, pressure, probe_s1, probe_s2
from ac2fb.protocol import data

__all__ = [
    "CODE_CHECKS",
    "DERIVED",
    "PROTOCOL_ONLY",
    "SCHEMA",
    "STAGES",
    "CodeCheck",
    "Report",
    "check",
    "code_problems",
    "coherence_problems",
    "numeric_leaves",
    "schema_problems",
]

STAGES: tuple[str, ...] = ("design", "frozen", "read")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_CRITERIA = ("D1", "D2", "D3", "D4", "D5", "D6")

# Field path -> expected type(s). Booleans are not ints here, and ints are not floats.
SCHEMA: dict[str, type | tuple[type, ...]] = {
    "stage": str,
    "candidate": str,
    "title": str,
    "question": str,
    "written_before_any_outcome": bool,
    "date_written": str,
    "about": str,
    "split.file": str,
    "split.matches_per_half": int,
    "frame_rate_hz": int,
    "instant.definition": str,
    "instant.source": str,
    "instant.reason": str,
    "window.frames": int,
    "window.seconds": float,
    "window.floor_source": str,
    "window.reason": str,
    "units.population": str,
    "units.requirements": list,
    "units.exclusion.rule": str,
    "units.exclusion.gap_frames_at_most": int,
    "units.exclusion.applies_to": str,
    "units.exclusion.reason": str,
    "units.outcome_undefined": str,
    "units.possession": str,
    "cause.instrument.definition": str,
    "cause.instrument.radius_m": float,
    "cause.instrument.goal_x_m": float,
    "cause.instrument.contrast": str,
    "cause.treatment.pressed_if_index_at_least": float,
    "cause.treatment.reason": str,
    "cause.label_levels": list,
    "cause.label_role": str,
    "outcome.definition": str,
    "outcome.sign": str,
    "outcome.window": str,
    "outcome.ball_rows": str,
    "outcome.period_end": str,
    "outcome.possession_change": str,
    "outcome.expected_sign_of_effect": str,
    "strata.direction.cut_m": float,
    "strata.third.cut_m": float,
    "strata.length.cut_m": float,
    "strata.cells": int,
    "variants.V0": str,
    "variants.V1": str,
    "variants.V2": str,
    "statistic.cell": str,
    "statistic.min_per_group": int,
    "statistic.effect_in_cell": str,
    "statistic.why_adjusted": str,
    "statistic.scale": str,
    "statistic.weights": str,
    "statistic.match_effect": str,
    "statistic.pooled_effect": str,
    "pretrend.statistic": str,
    "pretrend.in_cell": str,
    "pretrend.pooled": str,
    "null.kind": str,
    "null.draws": int,
    "null.seed": int,
    "null.stream": str,
    "null.p_value": str,
    "null.block_by_possession_if_rho_above": float,
    "null.blocked": bool,
    "null.blocked_basis": str,
    "null.blocked_null": str,
    "bars.calibration.same_sign_matches_at_least": int,
    "bars.calibration.p_at_most": float,
    "bars.calibration.null_draws_as_extreme_at_most": int,
    "bars.calibration.holm": bool,
    "bars.calibration.definition": str,
    "bars.heldout.same_sign_matches_at_least": int,
    "bars.heldout.alpha": float,
    "bars.heldout.holm_family": list,
    "bars.heldout.definition": str,
    "death_criteria.immovable": bool,
    "death_criteria.D1.min_matches": int,
    "death_criteria.D1.min_per_level": int,
    "death_criteria.D2.mde80_at_most_sd": float,
    "death_criteria.D3.ratio": float,
    "death_criteria.D3.units": str,
    "death_criteria.D3.why_sd": str,
    "death_criteria.D3.other_reading": str,
    "death_criteria.D4.ratio": float,
    "reading_order": list,
    "published": list,
    "conventions_left_open_by_the_plan_and_decided_here": list,
}


@dataclass(frozen=True)
class CodeCheck:
    """A protocol field that must equal a value the code fixes; ``source`` names that value."""

    path: str
    source: str
    expected: Callable[[], object]


def _split_size() -> tuple[int, int]:
    split = data.load_split()
    return len(split.calibration), len(split.heldout)


CODE_CHECKS: tuple[CodeCheck, ...] = (
    CodeCheck("split.file", "ac2fb.protocol.data.SPLIT_PATH", lambda: data.SPLIT_PATH),
    CodeCheck(
        "split.matches_per_half",
        "ac2fb.defence.probe_s1.CALIBRATION_MATCHES",
        lambda: probe_s1.CALIBRATION_MATCHES,
    ),
    CodeCheck(
        "split.matches_per_half",
        "the sizes of the two sets of protocol/split.json at HEAD",
        lambda: _split_size(),
    ),
    CodeCheck(
        "frame_rate_hz",
        "1 / ac2fb.defence.probe_s2.FRAME_SECONDS",
        lambda: round(1 / probe_s2.FRAME_SECONDS),
    ),
    CodeCheck(
        "window.frames", "ac2fb.defence.pressure.INCOMING_WINDOW", lambda: pressure.INCOMING_WINDOW
    ),
    CodeCheck(
        "cause.instrument.radius_m", "ac2fb.defence.pressure.RADIUS", lambda: pressure.RADIUS
    ),
    CodeCheck(
        "cause.instrument.goal_x_m", "ac2fb.defence.pressure.GOAL_X", lambda: pressure.GOAL_X
    ),
    CodeCheck(
        "cause.treatment.pressed_if_index_at_least",
        "ac2fb.defence.pressure.PRESSED_INDEX",
        lambda: pressure.PRESSED_INDEX,
    ),
    CodeCheck(
        "cause.label_levels",
        "ac2fb.defence.pressure.LEVELS, in order of the provider's id",
        lambda: [pressure.LEVELS[k] for k in sorted(pressure.LEVELS)],
    ),
    CodeCheck(
        "strata.direction.cut_m",
        "ac2fb.defence.pressure.BACKWARD_CUT",
        lambda: pressure.BACKWARD_CUT,
    ),
    CodeCheck("strata.third.cut_m", "ac2fb.defence.pressure.THIRD_CUT", lambda: pressure.THIRD_CUT),
    CodeCheck(
        "strata.length.cut_m", "ac2fb.defence.pressure.LONG_BALL", lambda: pressure.LONG_BALL
    ),
    CodeCheck("statistic.min_per_group", "ac2fb.defence.bar.MIN_CELL", lambda: bar.MIN_CELL),
    CodeCheck("null.draws", "ac2fb.defence.bar.N_PERMUTATIONS", lambda: bar.N_PERMUTATIONS),
    CodeCheck(
        "null.block_by_possession_if_rho_above",
        "ac2fb.defence.bar.BLOCK_RHO",
        lambda: bar.BLOCK_RHO,
    ),
    CodeCheck(
        "bars.calibration.same_sign_matches_at_least",
        "ac2fb.defence.bar.BAR_SAME_SIGN",
        lambda: bar.BAR_SAME_SIGN,
    ),
    CodeCheck("bars.calibration.p_at_most", "ac2fb.defence.bar.BAR_P", lambda: bar.BAR_P),
    CodeCheck(
        "bars.calibration.null_draws_as_extreme_at_most",
        "ac2fb.defence.bar.BAR_COUNT_AT_MOST",
        lambda: bar.BAR_COUNT_AT_MOST,
    ),
    CodeCheck(
        "bars.heldout.same_sign_matches_at_least",
        "ac2fb.defence.bar.BAR_SAME_SIGN",
        lambda: bar.BAR_SAME_SIGN,
    ),
    CodeCheck(
        "death_criteria.D1.min_matches",
        "ac2fb.defence.probe_s1.MIN_MATCHES",
        lambda: probe_s1.MIN_MATCHES,
    ),
    CodeCheck(
        "death_criteria.D1.min_per_level",
        "ac2fb.defence.probe_s1.MIN_PER_LEVEL",
        lambda: probe_s1.MIN_PER_LEVEL,
    ),
    CodeCheck(
        "death_criteria.D2.mde80_at_most_sd",
        "ac2fb.defence.power.MDE_LIMIT",
        lambda: power.MDE_LIMIT,
    ),
    CodeCheck("death_criteria.D3.ratio", "ac2fb.defence.power.D3_RATIO", lambda: power.D3_RATIO),
    CodeCheck("null.seed", "ac2fb.defence.effect.SEED", lambda: effect.SEED),
    CodeCheck(
        "bars.heldout.alpha", "ac2fb.defence.effect.HELDOUT_ALPHA", lambda: effect.HELDOUT_ALPHA
    ),
    CodeCheck("death_criteria.D4.ratio", "ac2fb.defence.effect.D4_RATIO", lambda: effect.D4_RATIO),
)

# Numeric fields a coherence rule derives from other fields of the protocol.
DERIVED: dict[str, str] = {
    "window.seconds": "window.frames / frame_rate_hz",
    "units.exclusion.gap_frames_at_most": "window.frames",
    "strata.cells": "three directions by three thirds by two lengths",
    "bars.calibration.null_draws_as_extreme_at_most": (
        "the largest c with (1 + c) / (1 + null.draws) <= bars.calibration.p_at_most"
    ),
}

# Numbers no code fixes: none since the estimator (task 20) took the seed, the held-out level and
# D4's ratio. A number a later task adds to the protocol before its code exists is declared here.
PROTOCOL_ONLY: dict[str, str] = {}


@dataclass(frozen=True)
class Report:
    """What the check found, and how much it verified."""

    problems: tuple[str, ...]
    schema_fields: int
    coherence_rules: int
    code_constants: int
    derived_numbers: int
    protocol_only_numbers: int
    numeric_leaves: int

    @property
    def ok(self) -> bool:
        return not self.problems


def _get(protocol: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    """The value at a dotted path, and whether it exists."""
    node: Any = protocol
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return False, None
        node = node[part]
    return True, node


def numeric_leaves(node: object, prefix: str = "") -> dict[str, int | float]:
    """Every number in the protocol by its dotted path (list items as ``path[i]``)."""
    found: dict[str, int | float] = {}
    if isinstance(node, Mapping):
        for key, value in node.items():
            found.update(numeric_leaves(value, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found.update(numeric_leaves(value, f"{prefix}[{i}]"))
    elif isinstance(node, int | float) and not isinstance(node, bool):
        found[prefix] = node
    return found


def _typed(value: object, expected: type | tuple[type, ...]) -> bool:
    kinds = expected if isinstance(expected, tuple) else (expected,)
    if isinstance(value, bool):
        return bool in kinds
    if isinstance(value, int):
        return int in kinds
    if isinstance(value, float):
        return float in kinds
    return isinstance(value, kinds)


def schema_problems(protocol: Mapping[str, Any]) -> list[str]:
    """Missing or mistyped fields, and the death criteria without the plan's text."""
    found: list[str] = []
    for path, expected in SCHEMA.items():
        exists, value = _get(protocol, path)
        if not exists:
            found.append(f"missing field {path}")
        elif not _typed(value, expected):
            names = [k.__name__ for k in (expected if isinstance(expected, tuple) else (expected,))]
            found.append(f"{path} is {type(value).__name__}, not {' or '.join(names)}")
    if "code_tree_sha" not in protocol:
        found.append("missing field code_tree_sha")
    exists, criteria = _get(protocol, "death_criteria")
    if exists and isinstance(criteria, Mapping):
        keys = {k for k in criteria if k != "immovable"}
        if keys != set(_CRITERIA):
            found.append(f"death_criteria holds {sorted(keys)}, not {list(_CRITERIA)}")
        for name in _CRITERIA:
            item = criteria.get(name)
            if not isinstance(item, Mapping):
                continue
            for field in ("plan_text", "evaluation"):
                if not isinstance(item.get(field), str) or not item[field].strip():
                    found.append(f"death_criteria.{name}.{field} is empty")
            if isinstance(item.get("plan_text"), str) and not item["plan_text"].startswith(name):
                found.append(f"death_criteria.{name}.plan_text does not start with {name}")
    return found


def coherence_problems(protocol: Mapping[str, Any]) -> tuple[list[str], int]:
    """Rules inside the protocol; returns the problems and how many rules were applied."""
    p = protocol
    found: list[str] = []
    rules = 0

    def rule(ok: bool, message: str) -> None:
        nonlocal rules
        rules += 1
        if not ok:
            found.append(message)

    _, stage = _get(p, "stage")
    _, sha = _get(p, "code_tree_sha")
    rule(stage in STAGES, f"stage {stage!r} is not one of {STAGES}")
    rule(
        (stage == "design") == (sha is None),
        "code_tree_sha must be null in stage design and only there",
    )
    rule(
        sha is None or (isinstance(sha, str) and bool(_SHA.match(sha))),
        "code_tree_sha must be a 64-character hexadecimal sha256",
    )
    rule(_get(p, "candidate")[1] == "C1", "the candidate chosen at CP1 is C1")
    rule(
        _get(p, "written_before_any_outcome")[1] is True, "written_before_any_outcome must be true"
    )
    rule(_get(p, "death_criteria.immovable")[1] is True, "death_criteria.immovable must be true")
    _, frames = _get(p, "window.frames")
    _, seconds = _get(p, "window.seconds")
    _, hz = _get(p, "frame_rate_hz")
    rule(
        isinstance(frames, int) and isinstance(hz, int) and hz > 0 and seconds == frames / hz,
        "window.seconds must be window.frames / frame_rate_hz",
    )
    rule(
        _get(p, "units.exclusion.gap_frames_at_most")[1] == frames,
        "units.exclusion.gap_frames_at_most must be the window in frames",
    )
    rule(
        _get(p, "units.exclusion.applies_to")[1] == "the later unit",
        "the exclusion drops the later unit",
    )
    rule(
        _get(p, "strata.cells")[1] == 3 * 3 * 2,
        "strata.cells must be 3 directions x 3 thirds x 2 lengths",
    )
    _, levels = _get(p, "cause.label_levels")
    rule(isinstance(levels, list) and len(levels) == 5, "cause.label_levels must list five levels")
    _, cut = _get(p, "cause.treatment.pressed_if_index_at_least")
    _, radius = _get(p, "cause.instrument.radius_m")
    rule(
        isinstance(cut, float) and isinstance(radius, float) and 0 < cut < 1,
        "the cut must be a share of one rival equivalent, between 0 and 1",
    )
    _, draws = _get(p, "null.draws")
    _, p_max = _get(p, "bars.calibration.p_at_most")
    _, at_most = _get(p, "bars.calibration.null_draws_as_extreme_at_most")
    if isinstance(draws, int) and isinstance(p_max, float) and draws > 0:
        expected = max((c for c in range(draws + 1) if (1 + c) / (1 + draws) <= p_max), default=-1)
        rule(
            at_most == expected,
            f"null_draws_as_extreme_at_most must be {expected} for {draws} draws",
        )
    else:
        rule(False, "null.draws and bars.calibration.p_at_most must be an int and a float")
    rule(
        _get(p, "null.blocked")[1] is False,
        "the null is not blocked: the measured correlation is below the threshold",
    )
    rule(
        isinstance(_get(p, "null.stream")[1], str) and "seed" in _get(p, "null.stream")[1],
        "null.stream must say how the seed is used",
    )
    _, family = _get(p, "bars.heldout.holm_family")
    _, variants = _get(p, "variants")
    rule(family == ["V0", "V1"], "the Holm family is {V0, V1}")
    rule(
        isinstance(variants, Mapping) and set(variants) >= {"V0", "V1", "V2"},
        "variants must define V0, V1 and V2",
    )
    rule(
        _get(p, "bars.calibration.holm")[1] is False, "the calibration bar is per variant (no Holm)"
    )
    _, cal_p = _get(p, "bars.calibration.p_at_most")
    _, held_alpha = _get(p, "bars.heldout.alpha")
    rule(
        isinstance(cal_p, float) and isinstance(held_alpha, float) and cal_p < held_alpha,
        "the calibration bar is stricter than the held-out level",
    )
    rule(
        _get(p, "bars.heldout.same_sign_matches_at_least")[1]
        == _get(p, "bars.calibration.same_sign_matches_at_least")[1],
        "both bars ask the same sign agreement",
    )
    rule(
        _get(p, "death_criteria.D3.ratio")[1] == _get(p, "death_criteria.D4.ratio")[1] == 0.5,
        "D3 and D4 are the plan's halves",
    )
    rule(
        _get(p, "death_criteria.D3.units")[1]
        == "sd of the cell: P in sd of x in its cell, T in sd of y in its cell",
        "D3 is read in sd of the cell",
    )
    rule(
        _get(p, "outcome.expected_sign_of_effect")[1] is not None
        and str(_get(p, "outcome.expected_sign_of_effect")[1]).startswith("negative"),
        "C1 expects a negative effect",
    )
    _, half = _get(p, "split.matches_per_half")
    _, same = _get(p, "bars.calibration.same_sign_matches_at_least")
    _, d1 = _get(p, "death_criteria.D1.min_matches")
    rule(
        isinstance(half, int)
        and isinstance(same, int)
        and isinstance(d1, int)
        and same <= d1 <= half,
        "sign agreement <= D1's matches <= matches per half",
    )
    return found, rules


def code_problems(protocol: Mapping[str, Any]) -> list[str]:
    """Every protocol field that differs from the value the code fixes."""
    found: list[str] = []
    for item in CODE_CHECKS:
        exists, value = _get(protocol, item.path)
        if not exists:
            found.append(f"missing field {item.path} (checked against {item.source})")
            continue
        expected = item.expected()
        if isinstance(expected, tuple):
            ok = all(e == value for e in expected)
        else:
            ok = expected == value and type(expected) is type(value)
        if not ok:
            found.append(f"{item.path} is {value!r}; {item.source} gives {expected!r}")
    return found


def check(protocol: Mapping[str, Any]) -> Report:
    """Schema, coherence and code checks of a parsed protocol, with the counts of each."""
    problems = schema_problems(protocol)
    coherence, rules = coherence_problems(protocol)
    problems += coherence
    problems += code_problems(protocol)
    leaves = numeric_leaves(protocol)
    checked = {c.path for c in CODE_CHECKS}
    for path in sorted(leaves):
        if path not in checked and path not in DERIVED and path not in PROTOCOL_ONLY:
            problems.append(
                f"numeric field {path} = {leaves[path]!r} is neither checked against the code, "
                "derived by a coherence rule nor declared protocol-only"
            )
    for path in (*checked, *DERIVED, *PROTOCOL_ONLY):
        if path not in leaves and path in SCHEMA and SCHEMA[path] in (int, float):
            problems.append(f"declared numeric field {path} is absent")
    return Report(
        problems=tuple(problems),
        schema_fields=len(SCHEMA) + 1,  # plus code_tree_sha
        coherence_rules=rules,
        code_constants=len(CODE_CHECKS),
        derived_numbers=len(DERIVED),
        protocol_only_numbers=len(PROTOCOL_ONLY),
        numeric_leaves=len(leaves),
    )
