"""The camera page's build and check without data (storyboard 8.2).

The geometry (which player lies in the camera's frame, where the frame's side edges meet), the
frame statistics on a planted bronze, the sidecar's bytes and the page's assembly, the cross-check
of the committed sidecar against the committed reports and the README, and the rules that need no
data (the payload against the sidecar, the template's typed numbers, the network).
Each rule has its planted case; the mutations that kill them are logged in scripts/mutations/.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import shutil
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "camera_page.py"

_spec = importlib.util.spec_from_file_location("camera_page", SCRIPT)
assert _spec is not None and _spec.loader is not None
cp: ModuleType = importlib.util.module_from_spec(_spec)
sys.modules["camera_page"] = cp
_spec.loader.exec_module(cp)

SQUARE = [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]]


# --- which point lies in the frame -------------------------------------------------------------


def _inside(points: list[list[float]], quad: list[list[float]]) -> list[bool]:
    quads = np.array([quad] * len(points), dtype=np.float64)
    return [bool(v) for v in cp.inside(np.array(points, dtype=np.float64), quads)]


def test_inside_takes_points_in_out_and_on_the_edge() -> None:
    points = [[1.0, 1.0], [3.0, 1.0], [2.0, 1.0], [0.0, 0.0], [-1e-9, 1.0], [1.0, 2.0 + 1e-9]]
    assert _inside(points, SQUARE) == [True, False, True, True, False, False]


def test_inside_does_not_depend_on_the_orientation() -> None:
    points = [[1.0, 1.0], [3.0, 1.0], [2.0, 1.0], [1.9, 0.1]]
    assert _inside(points, SQUARE[::-1]) == _inside(points, SQUARE) == [True, False, True, True]


def test_inside_a_thin_slanted_quad() -> None:
    quad = [[0.0, 0.0], [10.0, 1.0], [10.0, 2.0], [0.0, 1.0]]
    assert _inside([[5.0, 1.0], [5.0, 0.4], [5.0, 1.6], [9.0, 0.95]], quad) == [
        True,
        False,
        False,
        True,
    ]


def test_a_quad_with_a_nan_corner_holds_no_point() -> None:
    quad = [[0.0, 0.0], [2.0, 0.0], [math.nan, 2.0], [0.0, 2.0]]
    assert _inside([[1.0, 1.0], [0.5, 0.5]], quad) == [False, False]


# --- where the side edges meet ------------------------------------------------------------------


def _footprint(
    eye: tuple[float, float, float], heading: float, tilt: float, hfov: float, vfov: float
) -> list[list[float]]:
    """The corners of a camera's image on the ground (z = 0), bottom left, bottom right, top
    right, top left; the camera heads `heading` radians from +y toward +x, tilted down `tilt`,
    with no roll."""
    f = np.array(
        [math.sin(heading) * math.cos(tilt), math.cos(heading) * math.cos(tilt), -math.sin(tilt)]
    )
    r = np.array([math.cos(heading), -math.sin(heading), 0.0])
    u = np.cross(r, f)
    out = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        ray = f + sx * math.tan(hfov / 2) * r + sy * math.tan(vfov / 2) * u
        t = -eye[2] / ray[2]
        out.append([eye[0] + t * ray[0], eye[1] + t * ray[1]])
    return out


@pytest.mark.parametrize("heading", [0.0, 0.5, -0.3])
def test_the_side_edges_meet_behind_the_foot_of_a_tilted_camera(heading: float) -> None:
    # The frame's side edges meet on the line through the camera along the image's vertical, not
    # under the camera: behind its foot by its height times the tangent of its tilt.
    eye, tilt = (3.0, -70.0, 28.0), math.radians(20.0)
    quad = _footprint(eye, heading, tilt, math.radians(40.0), math.radians(23.0))
    found = cp.apex(quad)
    assert found is not None
    back = eye[2] * math.tan(tilt)
    want = (eye[0] - back * math.sin(heading), eye[1] - back * math.cos(heading))
    assert found == pytest.approx(want, abs=1e-6)
    assert math.hypot(found[0] - eye[0], found[1] - eye[1]) == pytest.approx(back, abs=1e-6)


def test_side_edges_that_never_meet_have_no_apex() -> None:
    assert cp.apex([[0.0, 0.0], [4.0, 0.0], [4.0, 3.0], [0.0, 3.0]]) is None
    assert cp.apex([[0.0, 0.0], [4.0, 0.0], [math.nan, 3.0], [0.0, 3.0]]) is None


def test_area_is_the_shoelace_whatever_the_orientation() -> None:
    quads = np.array([SQUARE, SQUARE[::-1], [[0, 0], [4, 0], [3, 2], [1, 2]]], dtype=np.float64)
    assert cp.area(quads).tolist() == [4.0, 4.0, 6.0]


# --- the frame statistics on a planted bronze ----------------------------------------------------


def _planted() -> tuple[Any, dict[str, np.ndarray]]:
    """40 frames: 0..24 with a frame around the origin, its near edge 10 m wide at y = -10 and its
    far edge 20 m wide at y = 10 (at y = 8 in frames 20..24), so its side edges meet at
    (0, -30) (at (0, -28) there), 25..34 with no corners and no player listed, 35..39 with no
    corners and two players listed. Player rows: in each frame with corners one detected at the
    origin (inside) and one filled at x = 50 (outside); one more detected outside in frames
    0..4 and one more filled inside in frames 5..6; in the frames without corners and with
    players, two filled rows, plus one detected in frame 35."""
    n = 40
    corners = np.full((n, 4, 2), np.nan)
    for f in range(25):
        top = 10.0 if f < 20 else 8.0
        corners[f] = [[-5.0, -10.0], [5.0, -10.0], [10.0, top], [-10.0, top]]
    n_players = np.array([3] * 25 + [0] * 10 + [2] * 5, dtype=np.int64)
    bronze = cp.Bronze(np.arange(n, dtype=np.int64), np.zeros(n), n_players, corners)
    rows: list[tuple[int, float, float, bool]] = []
    for f in range(25):
        rows += [(f, 0.0, 0.0, True), (f, 50.0, 0.0, False)]
    rows += [(f, 50.0, 0.0, True) for f in range(5)] + [(f, 1.0, 1.0, False) for f in (5, 6)]
    for f in range(35, 40):
        rows += [(f, 0.0, 0.0, f == 35), (f, 1.0, 1.0, False)]
    cols = list(zip(*rows, strict=True))
    players = {
        "frame": np.array(cols[0], dtype=np.int64),
        "x": np.array(cols[1]),
        "y": np.array(cols[2]),
        "detected": np.array(cols[3], dtype=np.bool_),
    }
    return bronze, players


def test_frame_stats_count_frames_and_rows_on_a_planted_bronze() -> None:
    bronze, players = _planted()
    s = cp.frame_stats(bronze, players, np.arange(10), 3, 400.0, 5.0)
    assert (s["frames"], s["with_corners"], s["without_corners"]) == (40, 25, 15)
    assert (s["without_no_player"], s["without_with_players"]) == (10, 5)
    assert s["without_players_listed"] == [2]
    assert s["without_rows_detected"] == round(1 / 10, 6)
    assert (s["seen_rows"], s["seen_inside"]) == (30, round(25 / 30, 6))
    assert (s["filled_rows"], s["filled_inside"]) == (27, round(2 / 27, 6))
    assert (s["far_cut_y_m"], s["far_cut_share"]) == (10.0, round(20 / 25, 6))
    assert s["far_cut_beyond_touchline_m"] == 5.0
    assert s["area_m2"]["median"] == 300.0 and s["area_m2"]["reception_share"] == 0.75
    assert s["apex"]["median"] == [0.0, -30.0] and s["apex"]["behind_near_touchline_m"] == 25.0
    assert s["clip"] == {
        "without_corners": 0,
        "max_corner_step_m": 0.0,
        "far_cut_share": 1.0,
        "area_m2": [300.0, 300.0],
    }


# --- the sidecar's bytes and the page's assembly -------------------------------------------------


def test_canonical_bytes_are_sorted_with_one_space_of_indent_and_a_final_lf() -> None:
    body = cp.canonical({"b": [1, 2.5], "a": "é"})
    assert body == '{\n "a": "é",\n "b": [\n  1,\n  2.5\n ]\n}\n'.encode()
    with pytest.raises(ValueError):
        cp.canonical({"a": math.nan})


def test_assemble_fills_each_marker_once_and_escapes_the_end_of_a_script() -> None:
    template = (
        "<style>/*FONTS*/</style>"
        '<script type="application/json" id="payload">/*PAYLOAD*/</script><script></script>'
    )
    faces = cp.font_faces([("F", 400, b"\0\1")])
    page = cp.assemble(template, {"x": "</script>", "y": [1, 2]}, faces)
    assert "/*PAYLOAD*/" not in page and "/*FONTS*/" not in page
    assert page.count("</script>") == 2 and "<\\/script>" in page
    assert cp.payload_of(page) == cp.canonical({"x": "</script>", "y": [1, 2]})
    assert (
        cp.inlined_fonts(page)
        == faces
        == (
            '@font-face{font-family:"F";font-weight:400;font-style:normal;font-display:swap;'
            'src:url(data:font/woff2;base64,AAE=) format("woff2")}\n'
        )
    )
    assert cp.assemble(template, {"y": [1, 2]}) == cp.assemble(template, {"y": [1, 2]})


@pytest.mark.parametrize(
    "template",
    [
        "/*PAYLOAD*/ /*PAYLOAD*/ /*FONTS*/",
        "<script></script>/*FONTS*/",
        "/*PAYLOAD*/ /*FONTS*/ /*FONTS*/",
    ],
)
def test_assemble_refuses_a_marker_twice_or_none(template: str) -> None:
    with pytest.raises(SystemExit, match="exactly once"):
        cp.assemble(template, {})


def test_vendored_fonts_are_read_by_their_hashes(tmp_path: Path) -> None:
    fonts = cp.vendored_fonts(cp.FONTS_DIR)
    assert [(f, w) for f, w, _ in fonts] == [(f, w) for f, w, _ in cp.FACES]
    assert all(data[:4] == b"wOF2" for _, _, data in fonts)
    folder = tmp_path / "fonts"
    shutil.copytree(cp.FONTS_DIR, folder)
    name = cp.FACES[0][2]
    (folder / name).write_bytes((folder / name).read_bytes() + b"\0")
    with pytest.raises(SystemExit, match="does not hash"):
        cp.vendored_fonts(folder)
    readme = (folder / "README").read_text(encoding="utf-8")
    (folder / "README").write_text(readme.replace(name, "other.woff2"), encoding="utf-8")
    with pytest.raises(SystemExit, match="must name the sha256"):
        cp.vendored_fonts(folder)


def test_check_finite_refuses_nan_and_a_missing_value_but_not_an_absent_teammate() -> None:
    with pytest.raises(SystemExit, match="nan"):
        cp.check_finite({"a": [1.0, math.nan]})
    with pytest.raises(SystemExit, match="missing"):
        cp.check_finite({"units": {"value": None}})
    cp.check_finite({"entities": {"mates": {"xy": [[None, None]]}}})


# --- the committed sidecar against the committed reports -----------------------------------------


@pytest.fixture(scope="module")
def committed() -> tuple[dict[str, Any], dict[str, bytes]]:
    doc = json.loads((cp.OUT_DIR / cp.SIDECAR).read_bytes())
    return doc, cp.read_reports(cp.REPORTS)


def test_the_committed_sidecar_holds_to_the_committed_reports(committed: Any) -> None:
    doc, reports = committed
    assert cp.cross_check(doc, reports) == []


def _mutated(doc: dict[str, Any], path: str, change: Any) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    *head, last = path.split(".")
    node: Any = out
    for part in head:
        node = node[int(part)] if isinstance(node, list) else node[part]
    key: Any = int(last) if isinstance(node, list) else last
    node[key] = change(node[key])
    return out


@pytest.mark.parametrize(
    ("path", "change", "named"),
    [
        ("match.rows.2.V0.mean", lambda v: v + 0.01, "line_height_m V0 mean"),
        ("match.rows.5.V1.n", lambda v: v + 1, "block_length_m V1 n"),
        ("match.rows.2.diff", lambda v: v + 1e-6, "line_height_m V1 - V0"),
        (
            "strips.metrics.line_height_m.held-out.points.3.value",
            lambda v: v + 0.5,
            "the point of line_height_m",
        ),
        (
            "strips.metrics.block_length_m.calibration.median",
            lambda v: v - 1,
            "median of block_length_m",
        ),
        ("strips.claim.line_height_m.least", lambda v: v + 1, "the strips' sentence"),
        ("key.frame", lambda v: v + 1, "clip.json: key"),
        ("entities.rivals.detected.30.0", lambda v: not v, "clip.json: defenders"),
        ("frame_stats.seen_inside", lambda v: 0.5, "would be false"),
        ("frame_stats.filled_inside", lambda v: 0.2, "would be false"),
        ("frame_stats.clip.without_corners", lambda v: 1, "has no corners"),
        ("fps", lambda v: v + 1, "fps is not the clip's"),
        ("match.rows", lambda v: v[:-1], "6 metrics, reliability.csv 7"),
        ("context.player_detected", lambda v: v + 0.01, "context.player_detected is"),
        ("context.block.phases", lambda v: v + 1, "context.block.phases is"),
        ("context.ball_distance.40_plus", lambda v: v - 0.01, "context.ball_distance.40_plus"),
        (
            "findings.numbers.effect_sd.value",
            lambda v: v + 0.01,
            "findings.numbers.effect_sd.value is",
        ),
        ("findings.numbers.gap_s.value", lambda v: v + 1, "findings.numbers.gap_s.value is"),
        (
            "findings.signs.block_width_m.calibration",
            lambda v: v + 1,
            "findings.signs.block_width_m.calibration is",
        ),
        (
            "findings.numbers.seen_cal.value",
            lambda v: v + 0.01,
            "findings.numbers.seen_cal.value is",
        ),
        ("findings.readme.fill", lambda v: v + " And more.", "findings.readme.fill is"),
        ("findings.readme.quick", lambda v: v.replace("uv sync", "uv pip"), "readme.quick is"),
        ("findings.keep", lambda v: "Keep the fill.", "findings.keep is"),
        ("findings.verdict.0.words", lambda v: v.split(" (")[0], "findings.verdict is"),
        ("sources.layer2\\.json", None, None),
    ],
)
def test_the_cross_check_names_each_broken_number(
    committed: Any, path: str, change: Any, named: str | None
) -> None:
    doc, reports = committed
    if change is None:  # a source hash: its key holds a dot
        bad = copy.deepcopy(doc)
        bad["sources"]["layer2.json"] = "0" * 64
        named = "the hash of layer2.json"
    else:
        bad = _mutated(doc, path, change)
    problems = cp.cross_check(bad, reports)
    assert problems and any(named in p for p in problems), problems


def test_the_second_reception_holds_to_its_rule_and_counts_in_v1(committed: Any) -> None:
    doc, _ = committed
    second = doc["second"]
    assert cp.second_problems(doc) == []
    assert all(u["v1"] for u in second["units"].values())
    assert not doc["units"]["line"]["v1"] and second["reception"] != doc["reception"]
    assert second["rule"] == cp.second_reception().describe()
    assert second["earlier"] == sum(second["rejected"].values()) > 0


def _filled_in_at_the_reception(doc: dict[str, Any], unit: str) -> tuple[dict[str, Any], list[str]]:
    """The sidecar with the first player of a unit of the second reception filled in at the
    reception, everywhere the sidecar says it (the defender, every unit read there that reads him,
    the key's counts): what a second reception that does not count in V1 would look like; and the
    units that read him."""
    out = copy.deepcopy(doc)
    s = out["second"]
    key = s["key"]["index"]
    player = s["units"][unit]["player_ids"][0]
    j = s["entities"]["rivals"]["ids"].index(player)
    s["entities"]["rivals"]["detected"][key][j] = False
    s["entities"]["rivals"]["gap"][key][j] = 12
    hit = []
    for name, u in s["units"].items():
        if u["index"] == key and player in u["player_ids"]:
            i = u["player_ids"].index(player)
            u["seen"][i], u["gap_len"][i], u["n_seen"], u["v1"] = False, 12, u["n_seen"] - 1, False
            hit.append(name)
    k = s["key"]
    k["defenders_extrapolated"] += 1
    k["defenders_seen"] -= 1
    k["defenders_extrapolated_by_frame"][key] += 1
    k["longest_gap_len"], k["longest_gap_player_id"] = 12, player
    return out, hit


@pytest.mark.parametrize("unit", ["line", "pressure", "nearest"])
def test_a_second_reception_with_a_defender_filled_in_is_named(committed: Any, unit: str) -> None:
    # The planted case of the rule's one test the sidecar can show: a unit read at the reception
    # with a player the camera did not see, consistent everywhere else. Mutation (V1 not asked of
    # the second's units): no problem is named.
    doc, _ = committed
    bad, hit = _filled_in_at_the_reception(doc, unit)
    assert unit in hit
    assert sorted(cp.second_problems(bad)) == sorted(
        f"camera.json: second.units.{name} does not count in V1" for name in hit
    )


@pytest.mark.parametrize(
    ("path", "change", "named"),
    [
        ("second.rule", lambda v: v.replace("at least 4", "at least 3"), "second.rule is not"),
        ("second.frames", lambda v: v[:-1], "second's window is not the rule's"),
        ("second.key.index", lambda v: v + 1, "second's window is not the rule's"),
        ("second.key.defenders_seen", lambda v: v - 1, "second.key.defenders_seen is not"),
        ("second.key.defenders_extrapolated_by_frame.0", lambda v: v + 1, "by_frame is not"),
        ("second.reception.frame", lambda v: v + 1, "second.reception is not"),
        ("second.n_defenders", lambda v: v + 1, "second.reception is not"),
        ("second.entities.me.detected.30", lambda v: False, "not a candidate of the rule"),
        ("second.entities.ball.detected.30", lambda v: False, "not a candidate of the rule"),
        ("second.entities.rivals.gap.50.0", lambda v: -1, "second's window has a hole"),
        ("second.entities.ball.xy.70", lambda v: [None, None], "second's window has a hole"),
        ("second.camera.corners.10.0", lambda v: [None, None], "a frame of second has no corners"),
        ("second.units.line.frame", lambda v: v + 1, "second.units.line is not read where"),
        ("second.units.block.frame", lambda v: v + 1, "second.units.block is not read where"),
        ("second.units.block.metric", lambda v: "block_width_m", "second.units.block is not read"),
        ("second.units.block.phase.frame_end", lambda v: v - 100, "does not hold it"),
        ("second.units.pressure.gap_len.0", lambda v: v + 3, "pressure's players are not"),
        ("second.units.nearest.player_ids.0", lambda v: 1, "nearest's players are not"),
        ("second.units.nearest.v1", lambda v: False, "second.units.nearest does not count"),
        ("second.units.line.n_seen", lambda v: v - 1, "second.units.line's counts are not"),
        ("units.block.n_players", lambda v: v + 1, "units.block's counts are not"),
        ("units.line.v1", lambda v: True, "the video's reception counts in V1"),
        ("second.rejected.v1", lambda v: v + 1, "earlier their sum"),
        ("second.earlier", lambda v: v - 1, "earlier their sum"),
    ],
)
def test_the_static_check_names_each_broken_rule_of_the_second_reception(
    committed: Any, path: str, change: Any, named: str
) -> None:
    doc, _ = committed
    problems = cp.second_problems(_mutated(doc, path, change))
    assert any(named in p for p in problems), problems


def test_a_sidecar_without_the_second_reception_is_named(committed: Any) -> None:
    doc, reports = committed
    gone = {k: v for k, v in doc.items() if k != "second"}
    assert cp.second_problems(gone) == ["camera.json: no second reception"]
    assert "camera.json: no second reception" in cp.cross_check(gone, reports)


def test_a_clip_json_with_another_reception_is_named(committed: Any) -> None:
    doc, reports = committed
    clip = json.loads(reports["clip/clip.json"])
    clip["key"]["frame"] += 10
    problems = cp.cross_check(doc, {**reports, "clip/clip.json": json.dumps(clip).encode()})
    assert any("clip.json: key differs" in p and "another reception" in p for p in problems)


def test_a_findings_number_moved_in_its_artifact_is_named(committed: Any) -> None:
    # the Findings tab's effect, read by the README's key: the artifact moves, the sidecar does not
    doc, reports = committed
    calibration = json.loads(reports["calibration.json"])
    calibration["criteria"]["D3"]["values"]["effect"] -= 0.01
    moved = {**reports, "calibration.json": json.dumps(calibration).encode()}
    problems = cp.cross_check(doc, moved)
    assert any(p.startswith("camera.json: findings.numbers.effect_sd.value is") for p in problems)


def test_findings_refuse_a_key_the_readme_does_not_cite(committed: Any) -> None:
    _, reports = committed
    strip = cp.strips(reports)
    found = cp.findings(reports, strip, cp.readme_keys(), cp.readme_text())
    assert found["numbers"]["window_s"]["value"] == 1.3
    assert found["numbers"]["nearest_below_held"]["value"] == 9
    assert 0.5 < found["numbers"]["seen_cal"]["value"] < 0.6  # the README's "56%"
    with pytest.raises(SystemExit, match="is not a key of README.src.json"):
        cp.findings(reports, strip, cp.readme_keys() - {cp.FINDINGS[0][1]}, cp.readme_text())


def test_findings_quote_the_readme_verbatim(committed: Any) -> None:
    # the details fold the README's own paragraphs and code, and the verdict closes in its words
    _, reports = committed
    found = cp.findings(reports, cp.strips(reports), cp.readme_keys(), cp.readme_text())
    quotes = found["readme"]
    assert set(quotes) == {"fill", "layer3", "quick_lead", "use_lead", "quick", "use"}
    assert quotes["fill"].startswith("**The fill behaves as an interpolation.**")
    assert quotes["layer3"].startswith("Layer 3's question and kill rule")
    assert quotes["quick"].startswith("git clone") and "uv run ftbase ingest" in quotes["quick"]
    assert quotes["use"].startswith("from ac2fb") and "sensitivity(" in quotes["use"]
    assert "\n\n" not in quotes["fill"] and not quotes["quick"].endswith("\n")
    assert found["keep"] == cp.KEEP == "Keep the fill; never report only what was seen."


@pytest.mark.parametrize(
    ("broken", "named"),
    [
        ("**The fill behaves as an interpolation.**", "paragraphs start with"),
        ("Layer 3's question and kill rule", "paragraphs start with"),
        ("<!-- clean-clone:quick:end -->", "no fenced code"),
        ("## Use it on your data", "no fenced code"),
        ("Keep the fill; never report only what was seen.", "README.md does not say"),
    ],
)
def test_findings_refuse_a_readme_without_what_the_page_quotes(
    committed: Any, broken: str, named: str
) -> None:
    _, reports = committed
    readme = cp.readme_text()
    assert readme.count(broken) == 1
    with pytest.raises(SystemExit, match=named):
        cp.findings(reports, cp.strips(reports), cp.readme_keys(), readme.replace(broken, "x"))


def test_findings_refuse_a_readme_whose_lead_opens_two_paragraphs(committed: Any) -> None:
    _, reports = committed
    readme = cp.readme_text() + "\n\nLayer 3's question and kill rule, again.\n"
    with pytest.raises(SystemExit, match="2 paragraphs start with"):
        cp.findings(reports, cp.strips(reports), cp.readme_keys(), readme)


@pytest.mark.parametrize(
    "words",
    [
        "line depth and reaction follow it",
        "pressure and nearest rival survive, below the fill's mean absolute error everywhere",
        "width is mixed",
        "(report their share seen whole)",
    ],
)
def test_findings_refuse_a_verdict_the_readme_does_not_say(committed: Any, words: str) -> None:
    # the grouping is the README's reading: a README that reads otherwise fails the build
    _, reports = committed
    readme = cp.readme_text()
    assert words in readme
    with pytest.raises(SystemExit, match="README.md does not say"):
        cp.findings(reports, cp.strips(reports), cp.readme_keys(), readme.replace(words, "x"))


@pytest.mark.parametrize(
    ("metric", "flip", "named"),
    [
        ("block_area_m2", 1, "does not keep its sign in every match"),
        ("block_width_m", None, "'mixed' would be false"),
    ],
)
def test_findings_refuse_a_verdict_the_strips_contradict(
    committed: Any, metric: str, flip: int | None, named: str
) -> None:
    _, reports = committed
    strip = copy.deepcopy(cp.strips(reports))
    points = strip[metric]["calibration"]["points"]
    if flip is not None:  # one match of the half against the metric's sign
        points[0]["value"] = -points[0]["value"]
    else:  # every match of both halves with one sign: no longer mixed
        for group in cp.GROUPS:
            for p in strip[metric][group]["points"]:
                p["value"] = -abs(p["value"])
    with pytest.raises(SystemExit, match=named):
        cp.findings(reports, strip, cp.readme_keys(), cp.readme_text())


def test_findings_refuse_a_nearest_rival_count_that_is_not_the_readmes(committed: Any) -> None:
    # one held-out match of nearest rival turned to the other sign: 8 against the README's 9
    _, reports = committed
    strip = copy.deepcopy(cp.strips(reports))
    point = next(p for p in strip["nearest_rival_m"]["held-out"]["points"] if p["value"] < 0)
    point["value"] = -point["value"]
    with pytest.raises(SystemExit, match="nearest rival's held-out count is not the README's"):
        cp.findings(reports, strip, cp.readme_keys(), cp.readme_text())


def test_a_strip_point_that_is_not_its_cells_difference_is_named(committed: Any) -> None:
    doc, reports = committed
    rows = reports["reliability.csv"].decode().splitlines()
    line = next(i for i, r in enumerate(rows) if r.startswith("1886347,line_height_m,all,V1,"))
    cells = rows[line].split(",")
    cells[5] = str(float(cells[5]) + 1)
    rows[line] = ",".join(cells)
    problems = cp.cross_check(
        doc, {**reports, "reliability.csv": ("\n".join(rows) + "\n").encode()}
    )
    assert any("1886347 is not V1 minus V0 of the cells it cites" in p for p in problems)


def test_compare_names_the_file_and_its_first_different_line(committed: Any) -> None:
    body = (cp.OUT_DIR / cp.SIDECAR).read_bytes()
    lines = body.decode().split("\n")
    for needle in ('"xy": [', '"corners": [', '"value": -1.1175'):
        k = next(i for i, line in enumerate(lines) if needle in line)
        j = k + 3 if needle != '"value": -1.1175' else k
        bad = list(lines)
        bad[j] = bad[j].replace("1", "2", 1) if "1" in bad[j] else bad[j] + " "
        found = cp.compare(cp.SIDECAR, "\n".join(bad).encode(), body)
        assert found == [f"camera.json: differs from the recomputation (first at line {j + 1})"]
    assert cp.compare(cp.SIDECAR, body, body) == []
    assert cp.compare(cp.PAGE, None, body) == [f"{cp.PAGE}: missing"]


# --- what needs no data -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def page() -> tuple[str, bytes, str]:
    return (
        (cp.OUT_DIR / cp.PAGE).read_text(encoding="utf-8"),
        (cp.OUT_DIR / cp.SIDECAR).read_bytes(),
        cp.TEMPLATE.read_text(encoding="utf-8"),
    )


def test_the_committed_page_passes_every_static_rule(page: Any) -> None:
    text, side, template = page
    assert cp.static_problems(text, side, template) == []
    assert cp.static_problems(text, side, template, cp.read_reports(cp.REPORTS)) == []


@pytest.mark.parametrize(
    ("path", "change", "named"),
    [
        (
            "findings.numbers.effect_sd.value",
            lambda v: -0.25,
            "findings.numbers.effect_sd.value is",
        ),
        (
            "findings.verdict.0.metrics",
            lambda v: ["line_height_m", "line_reaction_m"],
            "findings.verdict",
        ),
        (
            "strips.metrics.line_height_m.calibration.median",
            lambda v: v + 1,
            "median of line_height_m",
        ),
        ("context.player_detected", lambda v: v + 0.01, "context.player_detected is"),
        ("findings.readme.layer3", lambda v: v.replace("0.0005", "0.005"), "readme.layer3 is"),
        ("findings.keep", lambda v: v.replace("never", "do not"), "findings.keep is"),
    ],
)
def test_the_static_check_holds_the_sidecar_to_the_versioned_reports(
    page: Any, path: str, change: Any, named: str
) -> None:
    # what Pages deploys after --check-static alone: a moved number or word of the sidecar is named
    text, side, template = page
    bad = cp.canonical(_mutated(json.loads(side), path, change))
    problems = cp.static_problems(text, bad, template, cp.read_reports(cp.REPORTS))
    assert any(named in p for p in problems), problems


def test_a_page_whose_payload_is_not_the_sidecar_is_named(page: Any) -> None:
    text, side, template = page
    bad = text.replace('"fps":10,', '"fps":11,', 1)
    assert bad != text
    assert cp.static_problems(bad, side, template) == [
        f"{cp.PAGE}: its payload differs from {cp.SIDECAR}"
    ]


def test_a_page_whose_fonts_are_not_the_vendored_ones_is_named(page: Any, tmp_path: Path) -> None:
    text, side, template = page
    faces = cp.inlined_fonts(text)
    assert faces.count("@font-face") == len(cp.FACES) and faces in text
    bad = text.replace(faces, faces.replace("base64,", "base64,AAAA", 1), 1)
    assert cp.static_problems(bad, side, template) == [
        f"{cp.PAGE}: the inlined fonts are not vendor/fonts' (by their hashes)"
    ]
    gone = text.replace(faces, "", 1)
    assert cp.static_problems(gone, side, template) == [
        f"{cp.PAGE}: the inlined fonts are not vendor/fonts' (by their hashes)"
    ]
    folder = tmp_path / "fonts"
    shutil.copytree(cp.FONTS_DIR, folder)
    readme = (folder / "README").read_text(encoding="utf-8")
    (folder / "README").write_text(readme.replace("sha256 27d2", "sha256 37d2"), encoding="utf-8")
    assert cp.static_problems(text, side, template, fonts=folder) == [
        f"fonts: refused: {folder / cp.FACES[0][2]} does not hash to the sha256 in its README"
    ]


def test_a_byte_of_the_page_is_named(page: Any) -> None:
    text = page[0].encode("utf-8")
    bad = text.replace(b"What the camera saw</h1>", b"What the camera sees</h1>")
    assert cp.compare(cp.PAGE, bad, text)[0].startswith(f"{cp.PAGE}: differs")


@pytest.mark.parametrize(
    ("typed", "found"),
    [
        ("<p>7 of 11 filled in</p>", "the count '7 of 11'"),
        ('<p id="x"></p><script>const a = "1.8 m";</script>', "'1.8 m'"),
        ("<script>const lead = `unseen for 121 s`;</script>", "'121 s'"),
        ("<p>the camera saw 58 percent</p>", "HTML types '58'"),
        ("<p>the Cup's A-League 2024/25 matches</p>", "HTML types '2024/25'"),
        ("<p>drawn in 3D</p>", "HTML types '3D'"),
    ],
)
def test_the_template_may_not_type_a_number(page: Any, typed: str, found: str) -> None:
    template = page[2]
    assert cp.template_rules(template) == []
    bad = template.replace("</main>", typed + "</main>")
    problems = cp.template_rules(bad)
    assert any(found in p for p in problems), problems


@pytest.mark.parametrize(
    "load",
    [
        '<img src="https://example.org/x.png">',
        '<img src="data:image/png;base64,AAAA">',
        '<img src="data:image/png;base64,AAAA" srcset="https://example.org/x.png">',
        '<script src="data:text/javascript,fetch(1)"></script>',
        '<frame src="data:text/html;base64,AAAA">',
        '<img src="data:image/svg+xml,AAAA">',
        '<link rel="stylesheet" href="a.css">',
        "<script>fetch('data.json')</script>",
        "<style>a{background:url(x.png)}</style>",
        "<style>a{background:url(data:image/png;base64,AAAA)}</style>",
        "<style>@font-face{font-family:x;src:url(https://example.org/x.woff2)}</style>",
        "<style>@font-face{font-family:x;src:url(data:font/ttf;base64,AAAA)}</style>",
    ],
)
def test_a_page_that_loads_something_is_refused(page: Any, load: str) -> None:
    text = page[0]
    assert cp.network_rules(text) == []
    assert cp.network_rules(text.replace("</main>", load + "</main>"))


def test_the_inlined_woff2_faces_load_nothing(page: Any) -> None:
    text = page[0]
    assert text.count("url(data:font/woff2;base64,") == len(cp.FACES)
    assert cp.network_rules(text) == []


def test_links_load_nothing(page: Any) -> None:
    text = page[0].replace("</main>", '<a href="https://example.org/">a link</a></main>')
    assert cp.network_rules(text) == []


def test_the_page_inlines_no_script_and_its_fonts_only(page: Any) -> None:
    # the 3D page inlined three.js; the page from above runs its own script alone, its two faces
    # inlined from vendor/fonts and none fetched
    text = page[0]
    assert text.count("<script") == 2 and "THREE" not in text
    assert text.count("@font-face") == len(cp.FACES) and "fonts.googleapis" not in text


def test_the_sidecar_carries_the_drawing_constants(committed: Any) -> None:
    doc, _ = committed
    assert doc["label_gap_s"] == cp.LABEL_GAP_S == 5.0
    assert doc["crop"]["pad_m"] == cp.CROP_PAD_M and doc["camera"]["cut_step_m"] == cp.CUT_STEP_M


def test_counts_say_what_was_verified(committed: Any) -> None:
    doc, _ = committed
    n = cp.counts(doc)
    assert (n["frames"], n["entities"], n["units"]) == (100, 23, 4)
    assert n["positions"] == 100 * (11 + 10 + 1 + 1 + 4) and n["numbers"] > 200
    mates = len(doc["second"]["entities"]["mates"]["ids"])
    assert (n["second_frames"], n["second_units"]) == (100, 4)
    assert n["second_positions"] == 100 * (doc["second"]["n_defenders"] + mates + 1 + 1 + 4)


def test_bronze_refuses_frames_out_of_order() -> None:
    table = {
        "frame": SimpleNamespace(to_numpy=lambda **_: np.array([0, 2, 1])),
    }
    with pytest.raises(SystemExit, match="ascending"):
        cp.Bronze.of(table)
