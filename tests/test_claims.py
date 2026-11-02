"""The README's and the video's comparison of the selection with the fill-in's own error.

Figure 1's sidecar holds, per match of each split, V1 minus V0 (panel c, the selection) and the
mean absolute amputation error (panel d, the fill-in). The README and the video (row 9 of
``docs/video_script.md``) say pressure and nearest rival move less than the fill-in's error, and
line depth and block length far more; these tests hold both on the committed sidecar, match by
match, and a mutated copy shows that one match out of line is caught.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

SIDECAR = Path(__file__).resolve().parent.parent / "reports" / "figures" / "fig1_layer2.json"
MATCH = re.compile(r"match_id=(\d+)")
MATCHES = 20  # ten per split


def per_match(doc: dict[str, Any], panel: str, metric: str) -> dict[tuple[str, str], float]:
    """``(split, match id) -> value`` of one metric's per-match series in one panel."""
    out: dict[tuple[str, str], float] = {}
    for s in doc["series"]:
        if s["panel"] == panel and s["match"] == metric and s["kind"] == "match":
            for p in s["points"]:
                (found,) = {m for ref in p["refs"] for m in MATCH.findall(ref)}
                out[(s["group"], found)] = p["value"]
    return out


def out_of_line(doc: dict[str, Any], metric: str, smaller: bool) -> list[tuple[str, str]]:
    """The matches whose |V1 - V0| is not below (``smaller``) or not above the fill-in's error."""
    shift, error = per_match(doc, "c", metric), per_match(doc, "d", metric)
    assert shift.keys() == error.keys() and len(shift) == MATCHES, metric
    return sorted(k for k in shift if (abs(shift[k]) < error[k]) != smaller)


@pytest.fixture(scope="module")
def doc() -> dict[str, Any]:
    return json.loads(SIDECAR.read_text(encoding="utf-8"))


@pytest.mark.parametrize("metric", ["pressure_index", "nearest_rival_m"])
def test_pressure_and_nearest_rival_move_less_than_the_fill_ins_error(
    doc: dict[str, Any], metric: str
) -> None:
    assert out_of_line(doc, metric, smaller=True) == []


@pytest.mark.parametrize("metric", ["line_height_m", "block_length_m"])
def test_line_depth_and_block_length_move_more_than_the_fill_ins_error(
    doc: dict[str, Any], metric: str
) -> None:
    assert out_of_line(doc, metric, smaller=False) == []


@pytest.mark.parametrize(
    ("metric", "smaller", "point", "past"),
    [("pressure_index", True, 0, 1e-9), ("block_length_m", False, -1, -1e-9)],
)
def test_one_match_just_across_its_error_is_named(
    doc: dict[str, Any], metric: str, smaller: bool, point: int, past: float
) -> None:
    mutated = copy.deepcopy(doc)
    shifts = next(
        s
        for s in mutated["series"]
        if s["panel"] == "c" and s["match"] == metric and s["kind"] == "match"
    )
    planted = shifts["points"][point]
    (match,) = {m for ref in planted["refs"] for m in MATCH.findall(ref)}
    error = per_match(doc, "d", metric)[(shifts["group"], match)]
    planted["value"] = -(error + past)  # a hair outside (pressure) or inside (block) the error
    assert out_of_line(mutated, metric, smaller) == [(shifts["group"], match)]
