"""The camera page's build and check without data (storyboard 8.2).

The geometry (which player lies in the camera's frame, where the frame's side edges meet), the
frame statistics on a planted bronze, the sidecar's bytes and the page's assembly, the cross-check
of the committed sidecar against the committed reports, and the rules that need no data (the
payload against the sidecar, three.js by its hash, the template's typed numbers, the network).
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
    template = '<script type="application/json" id="payload">/*PAYLOAD*/</script>' + (
        '<script id="three-js">/*THREE*/</script>'
    )
    page = cp.assemble(template, {"x": "</script>", "y": [1, 2]}, "var three = 1;")
    assert "/*PAYLOAD*/" not in page and "/*THREE*/" not in page
    assert page.count("</script>") == 2 and "<\\/script>" in page
    assert cp.payload_of(page) == cp.canonical({"x": "</script>", "y": [1, 2]})
    assert cp.inlined_block(page) == "var three = 1;"
    assert cp.assemble(template, {"y": [1, 2]}, "t") == cp.assemble(template, {"y": [1, 2]}, "t")


def test_assemble_refuses_a_marker_twice() -> None:
    with pytest.raises(SystemExit, match="exactly once"):
        cp.assemble("/*PAYLOAD*/ /*PAYLOAD*/ /*THREE*/", {}, "")


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


def test_a_clip_json_with_another_reception_is_named(committed: Any) -> None:
    doc, reports = committed
    clip = json.loads(reports["clip/clip.json"])
    clip["key"]["frame"] += 10
    problems = cp.cross_check(doc, {**reports, "clip/clip.json": json.dumps(clip).encode()})
    assert any("clip.json: key differs" in p and "another reception" in p for p in problems)


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
    assert cp.static_problems(text, side, template, cp.VENDOR) == []


def test_a_page_whose_payload_is_not_the_sidecar_is_named(page: Any) -> None:
    text, side, template = page
    bad = text.replace('"fps":10,', '"fps":11,', 1)
    assert bad != text
    assert cp.static_problems(bad, side, template, cp.VENDOR) == [
        f"{cp.PAGE}: its payload differs from {cp.SIDECAR}"
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
        '<link rel="stylesheet" href="a.css">',
        "<script>fetch('data.json')</script>",
        "<style>a{background:url(x.png)}</style>",
    ],
)
def test_a_page_that_loads_something_is_refused(page: Any, load: str) -> None:
    text = page[0]
    assert cp.network_rules(text) == []
    assert cp.network_rules(text.replace("</main>", load + "</main>"))


def test_links_load_nothing(page: Any) -> None:
    text = page[0].replace("</main>", '<a href="https://example.org/">a link</a></main>')
    assert cp.network_rules(text) == []


# --- three.js ----------------------------------------------------------------------------------


def test_vendored_refuses_a_file_that_is_not_the_hashed_one(tmp_path: Path, page: Any) -> None:
    vendor = tmp_path / "three"
    shutil.copytree(cp.VENDOR, vendor)
    readme = (vendor / "README").read_text(encoding="utf-8")
    (vendor / "README").write_text(readme.replace("sha256 a681", "sha256 b681"), encoding="utf-8")
    with pytest.raises(SystemExit, match="does not hash"):
        cp.vendored(vendor, page[2])


def test_vendored_refuses_a_name_three_does_not_export(page: Any) -> None:
    text, release, digest = cp.vendored(cp.VENDOR, page[2])
    assert release == "0.185.1" and digest.startswith("a681da9a")
    with pytest.raises(SystemExit, match="NotAThing"):
        cp.vendored(cp.VENDOR, page[2] + "THREE.NotAThing")


def test_prove_loads_refuses_a_broken_block() -> None:
    broken = (
        '<script id="three-js">window.THREE = (function () { throw new Error("x"); })();</script>'
    )
    if shutil.which("node") is None:
        assert cp.prove_loads(broken, "0.185.1").startswith("node not found")
        return
    with pytest.raises(SystemExit, match="does not load"):
        cp.prove_loads(broken, "0.185.1")


def test_counts_say_what_was_verified(committed: Any) -> None:
    doc, _ = committed
    n = cp.counts(doc)
    assert (n["frames"], n["entities"], n["units"]) == (100, 23, 4)
    assert n["positions"] == 100 * (11 + 10 + 1 + 1 + 4) and n["numbers"] > 200


def test_bronze_refuses_frames_out_of_order() -> None:
    table = {
        "frame": SimpleNamespace(to_numpy=lambda **_: np.array([0, 2, 1])),
    }
    with pytest.raises(SystemExit, match="ascending"):
        cp.Bronze.of(table)
