"""The page: the video's reception from above, inside the camera's measured frame.

    uv run ftbase ingest --match 1874553 && uv run ftbase bronze && uv run ftbase silver
    uv run python scripts/camera_page.py                 # writes reports/camera/
    uv run python scripts/camera_page.py --check         # recomputes and compares, writes nothing
    uv run python scripts/camera_page.py --check-static  # what needs no data (CI)
    uv run --with playwright python scripts/drive_camera_page.py [path-or-url]

The page is read top to bottom: the reception of the video (``reports/clip/clip.json``: the one
``ac2fb.clip.choose`` picks by its frozen rule) drawn from above over the clip's frames, the
camera's measured frame the only lit area of the pitch and the defenders filled in as rings; the
V0/V1 switch that moves this match's mean line and block; the verdict on the twenty matches of
figure 1, panel c, in the README's groups; and the details folded (the fill, layer 3's question,
the frame measured, the limits, the code, the twenty matches as a table).

Everything the page draws or prints is in the sidecar ``reports/camera/camera.json``, and the
template (``scripts/camera_template.html``) types none of it; the page's two faces (Barlow and
Barlow Condensed, ``vendor/fonts/``, OFL) are inlined as data: URIs, each checked by the sha256
its README names, so the page still loads nothing. The sidecar is built from the data of
the match, read through the guarded door (``ac2fb.protocol.data``: the players and the ball of
silver, and the bronze frame columns by ``read_bronze_frames``, the four corners of the camera's
image on the pitch among them) and from the committed reports, and the build refuses when they
disagree: the scene must be the clip's, the match's cells those of ``reliability.csv``, each strip
point that of ``fig1_layer2.json`` and the difference of the CSV cells it cites, the sentence over
the strips true of every point, the README's words and paragraphs the README's, and the frame of
the camera a window around what it saw (players detected inside it, players filled in outside it).

``--check`` recomputes the sidecar and the page and compares both byte for byte with the committed
ones, holds the committed sidecar to the reports again, holds the payload inlined in the committed
page to the sidecar, and checks the template; exit 0 when it all holds, 1 when it does not, 2 when
the data are missing or the match is held out. ``--check-static`` runs what needs no data: the
payload against the sidecar, the inlined fonts against the vendored files by their hashes, the
template's rules (no number with a unit typed in it) and a page that loads nothing from the
network.

Copied, with a declaration, from the author's basketball entry
(github.com/javiersr1996/nobody-helps-the-helper, ``scripts/wind_html.py``, MIT): ``Refused``,
``check_finite`` and ``assemble``, adapted to one payload and no mannequin.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import math
import re
import statistics
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUT_DIR = REPORTS / "camera"
SIDECAR = "camera.json"
PAGE = "what_the_camera_saw.html"
TEMPLATE = Path(__file__).with_name("camera_template.html")
PAYLOAD = "/*PAYLOAD*/"
#: The page's faces, vendored (``vendor/fonts/README`` names each file's sha256) and inlined as
#: data: URIs in @font-face at this marker of the template's <style>: family, weight, file.
FONTS_DIR = ROOT / "vendor" / "fonts"
FONTS = "/*FONTS*/"
FACES = (
    ("Barlow", 400, "barlow-latin-400.woff2"),
    ("Barlow", 600, "barlow-latin-600.woff2"),
    ("Barlow Condensed", 600, "barlowcondensed-latin-600.woff2"),
    ("Barlow Condensed", 700, "barlowcondensed-latin-700.woff2"),
)

#: The reports the page reads, by their path under ``reports/``.
SOURCES = (
    "clip/clip.json",
    "reliability.csv",
    "heldout/reliability.csv",
    "figures/fig1_layer2.json",
    "layer2.json",
    "heldout/layer2.json",
    "calibration.json",
    "../protocol/protocol.json",
)
#: Where the README pairs each of its numbers with the artifact key it is read by.
README_SRC = ROOT / "README.src.json"
#: The README's numbers the page quotes, each read by the very key README.src.json cites for it
#: (the build refuses a key the README does not cite), and which candidate of the key it is: the
#: value, the seconds in a band's name ("gt_20s"), or a ratio's size.
FINDINGS = (
    ("seen_cal", "reports/layer2.json:summary.detection.player_detected.median", "value"),
    ("seen_held", "reports/heldout/layer2.json:summary.detection.player_detected.median", "value"),
    ("block_whole_cal", "reports/layer2.json:summary.block.all_detected.median", "value"),
    ("block_whole_held", "reports/heldout/layer2.json:summary.block.all_detected.median", "value"),
    ("line_whole_cal", "reports/layer2.json:summary.line.all_detected.median", "value"),
    ("line_whole_held", "reports/heldout/layer2.json:summary.line.all_detected.median", "value"),
    (
        "gap_s",
        "reports/layer2.json:summary.reacquisition.by_band.gt_20s.closed_jump_median.median",
        "band",
    ),
    (
        "jump_cal",
        "reports/layer2.json:summary.reacquisition.by_band.gt_20s.closed_jump_median.median",
        "value",
    ),
    (
        "jump_held",
        "reports/heldout/layer2.json:summary.reacquisition.by_band.gt_20s.closed_jump_median.median",
        "value",
    ),
    ("step", "reports/layer2.json:summary.steps.detected_to_detected.p50.median", "value"),
    ("window_s", "protocol/protocol.json:window.seconds", "value"),
    ("effect_sd", "reports/calibration.json:criteria.D3.values.effect", "value"),
    ("pretrend_sd", "reports/calibration.json:criteria.D3.values.pretrend", "value"),
    (
        "pretrend_share",
        "reports/calibration.json:criteria.D3.values.pretrend / criteria.D3.values.effect",
        "size",
    ),
    (
        "nearest_below_cal",
        "reports/figures/fig1_layer2.json:series.53.points.0.of.*(count below zero)",
        "value",
    ),
    (
        "nearest_below_held",
        "reports/figures/fig1_layer2.json:series.55.points.0.of.*(count below zero)",
        "value",
    ),
)
#: Where the README says it: its verdict sentence (README.md, "The selection is large").
README = ROOT / "README.md"
#: The README's verdict on the seven metrics: a reading of the sign and the size of V1 minus V0,
#: not a computation. Its groups in its order, each with the README's own words, which the build
#: finds in README.md (a README that says otherwise fails the check), and what it says of their
#: signs: line depth, block length, area, reaction and pressure keep theirs in every match of both
#: splits, width does not, nearest rival in 9 of 10 (by the README's keys, ``nearest_below_*``).
VERDICT = (
    (
        "chosen",
        ("block_length_m", "block_area_m2"),
        "Block length and area are mostly what the camera chose to show (report their share "
        "seen whole)",
    ),
    ("follow", ("line_height_m", "line_reaction_m"), "line depth and reaction follow it"),
    (
        "survive",
        ("pressure_index", "nearest_rival_m"),
        "pressure and nearest rival survive, below the fill's mean absolute error everywhere",
    ),
    ("mixed", ("block_width_m",), "width is mixed"),
)
README_SAYS = (
    "in every match of both splits",
    "area, reaction and pressure keep their sign everywhere",
    "nearest rival in 9 of 10",
)
#: The README's closing sentence, printed under the verdict in its words.
KEEP = "Keep the fill; never report only what was seen."
#: The README's paragraphs the folded details quote verbatim (Markdown, rendered by the page),
#: each the one paragraph that starts with these words, and its fenced code between two markers
#: (the quick block, the call to ``sensitivity``): a README without them fails the build.
README_PARAGRAPHS = (
    ("fill", "**The fill behaves as an interpolation.**"),
    ("layer3", "Layer 3's question and kill rule"),
    ("quick_lead", "One match,"),
    ("use_lead", "A metric is a function of a window of frames"),
)
README_CODE = (
    ("quick", "<!-- clean-clone:quick:start -->", "<!-- clean-clone:quick:end -->"),
    ("use", "## Use it on your data", "`examples/sensitivity.py`"),
)
EVERYWHERE = (
    "line_height_m",
    "block_length_m",
    "block_area_m2",
    "line_reaction_m",
    "pressure_index",
)
MIXED = ("block_width_m",)
#: The bronze frame columns: the frame, the ball's height, the players listed, and the four
#: corners of the image on the pitch in polygon order (bottom left, bottom right, top right,
#: top left: the near edge first, as the camera sees it).
CORNER_COLUMNS = (
    ("x_bottom_left", "y_bottom_left"),
    ("x_bottom_right", "y_bottom_right"),
    ("x_top_right", "y_top_right"),
    ("x_top_left", "y_top_left"),
)
BRONZE_COLUMNS = ["frame", "ball_z", "n_players", *(c for pair in CORNER_COLUMNS for c in pair)]
#: The metrics of figure 1 in its order, with the page's words and the unit of each.
METRICS = (
    ("pressure_index", "pressure on the receiver", ""),
    ("nearest_rival_m", "nearest rival", "m"),
    ("line_height_m", "line depth", "m"),
    ("line_reaction_m", "line reaction", "m"),
    ("block_width_m", "block width", "m"),
    ("block_length_m", "block length", "m"),
    ("block_area_m2", "block area", "m²"),
)
GROUPS = ("calibration", "held-out")
GROUP_CSV = {"calibration": "reliability.csv", "held-out": "heldout/reliability.csv"}

#: Drawn, not measured: the margin around the plan's crop (metres), and the gap over which a
#: filled-in defender's label stays pinned on the plan (seconds; the rest show on tap or hover).
CROP_PAD_M = 3.0
LABEL_GAP_S = 5.0
#: The sentence of the page holds only while the frame is a window around what the camera saw:
#: at least this share of the detected player rows inside it and at most this share of the filled
#: ones (rule 9).
SEEN_INSIDE_MIN, FILLED_INSIDE_MAX = 0.9, 0.1
#: A corner that moves more than this between two frames is a cut of the camera, drawn as a cut.
CUT_STEP_M = 10.0


class Refused(SystemExit):
    """The build will not write a page whose numbers disagree with their sources."""

    def __init__(self, why: str) -> None:
        super().__init__(f"refused: {why}")


# --- geometry ----------------------------------------------------------------------------------


def inside(points: NDArray[np.float64], quads: NDArray[np.float64]) -> NDArray[np.bool_]:
    """Whether each point (n, 2) lies in its quadrilateral (n, 4, 2), its edges included.

    The quadrilateral is convex, in either orientation; one with a NaN corner holds no point.
    """
    pos = np.ones(len(points), dtype=np.bool_)
    neg = np.ones(len(points), dtype=np.bool_)
    for k in range(4):
        a, b = quads[:, k], quads[:, (k + 1) % 4]
        cross = (b[:, 0] - a[:, 0]) * (points[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (
            points[:, 0] - a[:, 0]
        )
        pos &= cross >= 0
        neg &= cross <= 0
    whole = ~np.isnan(quads).any(axis=(1, 2)) & ~np.isnan(points).any(axis=1)
    return (pos | neg) & whole


def apexes(quads: NDArray[np.float64]) -> NDArray[np.float64]:
    """Where the side edges (bottom left to top left, bottom right to top right) of each
    quadrilateral (n, 4, 2) meet, as lines; NaN where they are parallel or a corner is missing.
    """
    p, r = quads[:, 0], quads[:, 3] - quads[:, 0]
    s, t = quads[:, 1], quads[:, 2] - quads[:, 1]
    den = r[:, 0] * t[:, 1] - r[:, 1] * t[:, 0]
    scale = np.hypot(r[:, 0], r[:, 1]) * np.hypot(t[:, 0], t[:, 1])
    with np.errstate(divide="ignore", invalid="ignore"):
        u = ((s[:, 0] - p[:, 0]) * t[:, 1] - (s[:, 1] - p[:, 1]) * t[:, 0]) / den
        out = p + u[:, None] * r
    out[~(np.abs(den) > 1e-9 * scale)] = np.nan
    return out


def apex(quad: Sequence[Sequence[float]]) -> tuple[float, float] | None:
    """:func:`apexes` of one quadrilateral, or None."""
    found = apexes(np.asarray([quad], dtype=np.float64))[0]
    return None if np.isnan(found).any() else (float(found[0]), float(found[1]))


def area(quads: NDArray[np.float64]) -> NDArray[np.float64]:
    """The area of each quadrilateral (n, 4, 2), whatever its orientation (shoelace)."""
    x, y = quads[..., 0], quads[..., 1]
    return np.abs(0.5 * (x * np.roll(y, -1, -1) - np.roll(x, -1, -1) * y).sum(-1))


# --- what is read ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Bronze:
    """The bronze frame columns of one match, by frame, ascending."""

    frame: NDArray[np.int64]
    ball_z: NDArray[np.float64]
    n_players: NDArray[np.int64]
    corners: NDArray[np.float64]  # (n, 4, 2), the provider's frame, NaN where none

    @staticmethod
    def of(table: Any) -> Bronze:
        def col(name: str) -> NDArray[np.float64]:
            return np.asarray(table[name].to_numpy(zero_copy_only=False), dtype=np.float64)

        frame = np.asarray(table["frame"].to_numpy(), dtype=np.int64)
        if (np.diff(frame) <= 0).any():
            raise Refused("the bronze frames are not one row per frame in ascending order")
        corners = np.stack([np.stack([col(x), col(y)], axis=1) for x, y in CORNER_COLUMNS], 1)
        n_players = np.asarray(table["n_players"].to_numpy(), dtype=np.int64)
        return Bronze(frame, col("ball_z"), n_players, corners)

    def rows(self, frames: NDArray[np.int64]) -> NDArray[np.int64]:
        where = np.searchsorted(self.frame, frames)
        if (where >= len(self.frame)).any() or (
            self.frame[np.minimum(where, len(self.frame) - 1)] != frames
        ).any():
            raise Refused("a frame of the scene has no bronze row")
        return where


@dataclass(frozen=True)
class Unit:
    """One unit of a layer 2 metric at this reception, as the frozen code reads it."""

    metric: str
    frame: int
    value: float
    player_ids: tuple[int, ...]
    seen: tuple[bool, ...]
    gap_len: tuple[int, ...]
    x: tuple[float, ...]  # each player's x in the clip's frame at the unit's frame
    phase: dict[str, Any] | None = None


@dataclass(frozen=True)
class Inputs:
    """What the page is built from: the scene, the bronze frames, the units and the match."""

    scene: Any  # ac2fb.clip.Scene
    bronze: Bronze
    units: dict[str, Unit]
    players: dict[str, NDArray[Any]]  # frame, x, y, detected of every player row of the match


def read_inputs(match_id: int) -> Inputs:
    """The match through the guarded door: its scene (the clip's rule), bronze frames and units.

    Raises ``HeldOutLocked`` for a held-out match and ``FileNotFoundError`` without the data.
    """
    from ac2fb import clip
    from ac2fb.protocol import data
    from ac2fb.reliability import metrics
    from ac2fb.reliability.match import load_with_long, locate_rows
    from ac2fb.reliability.sensitivity import Window, window_frames
    from ac2fb.reliability.visibility import goalkeepers

    match, long = load_with_long(match_id)
    scene = clip.choose(match, clip.DEFAULT_RULE)
    bronze = Bronze.of(data.read_bronze_frames([match_id], columns=BRONZE_COLUMNS))
    key = int(scene.frame[scene.key])
    units_of = metrics.metric_units(match)
    windows = window_frames(long)
    sign = scene.sign

    def unit(name: str, frame: int, phase: dict[str, Any] | None = None) -> Unit:
        metric, _ = units_of[name]
        frames = windows(Window(match_id, frame, frame))
        reading = None if frames is None else metric(frames)
        if frames is None or reading is None:
            raise Refused(f"{name} has no unit at frame {frame}")
        index = {int(p): i for i, p in enumerate(frames.player_ids)}
        rows = [index[p] for p in reading.player_ids]
        return Unit(
            metric=name,
            frame=frame,
            value=reading.value,
            player_ids=tuple(int(p) for p in reading.player_ids),
            seen=tuple(bool(frames.detected[r].all()) for r in rows),
            gap_len=tuple(int(frames.gap_len[r, 0]) for r in rows),
            x=tuple(float(frames.x[r, 0]) * sign for r in rows),
            phase=phase,
        )

    holding = [
        e
        for e in metrics.phases(match.events)
        if e.team == scene.team and e.period == scene.period and e.frame_start <= key <= e.frame_end
    ]
    if len(holding) != 1:
        raise Refused(f"{len(holding)} phases of play of team {scene.team} hold frame {key}")
    phase = holding[0]
    row = locate_rows(match, scene.rivals[:1], np.array([key], dtype=np.int64))[0]
    keeper = goalkeepers(match).get((scene.period, int(match.team[row])))
    start = phase.frame_start
    if not scene.frame[0] <= start <= scene.frame[-1]:
        raise Refused(f"the phase that holds the reception starts at {start}, outside the clip")
    units = {
        "line": unit("line_height_m", key),
        "block": unit(
            "block_length_m",
            start,
            {
                "subtype": phase.subtype,
                "frame_start": start,
                "frame_end": phase.frame_end,
                "keeper_id": keeper,
            },
        ),
        "pressure": unit("pressure_index", key),
        "nearest": unit("nearest_rival_m", key),
    }
    players = {"frame": match.frame, "x": match.x, "y": match.y, "detected": match.detected}
    return Inputs(scene, bronze, units, players)


# --- the reports -------------------------------------------------------------------------------


def _csv_rows(text: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text.decode("utf-8"), newline="")))


def _cell(rows: list[dict[str, str]], match: str, metric: str, variant: str, col: str) -> float:
    found = [
        r
        for r in rows
        if r["match_id"] == match
        and r["metric"] == metric
        and r["ball_stratum"] == "all"
        and r["variant"] == variant
    ]
    if len(found) != 1 or found[0][col] == "":
        raise Refused(f"{match} {metric} {variant} {col}: {len(found)} rows in the CSV")
    return float(found[0][col])


def _resolve(ref: str, reports: Mapping[str, bytes]) -> float:
    """A ``file#k=v,...:column`` reference of figure 1 to its CSV cell (``file`` under reports/)."""
    name, _, path = ref.partition("#")
    where, _, column = path.rpartition(":")
    wanted = dict(pair.split("=", 1) for pair in where.split(","))
    rows = [r for r in _csv_rows(reports[name]) if all(r.get(k) == v for k, v in wanted.items())]
    if len(rows) != 1 or rows[0][column] == "":
        raise Refused(f"{ref}: {len(rows)} rows")
    return float(rows[0][column])


def match_table(reports: Mapping[str, bytes], match_id: int) -> list[dict[str, Any]]:
    """The match's V0 and V1 cells of ``reliability.csv`` for each metric, and V1 minus V0."""
    rows = _csv_rows(reports["reliability.csv"])
    out = []
    for metric, words, unit in METRICS:
        cells = {
            v: {
                "mean": _cell(rows, str(match_id), metric, v, "mean"),
                "n": int(_cell(rows, str(match_id), metric, v, "n")),
            }
            for v in ("V0", "V1")
        }
        diff = round(cells["V1"]["mean"] - cells["V0"]["mean"], 9)
        out.append({"metric": metric, "words": words, "unit": unit, **cells, "diff": diff})
    return out


def strips(reports: Mapping[str, bytes]) -> dict[str, Any]:
    """Figure 1, panel c: per metric and half, each match's V1 minus V0 and the median."""
    doc = json.loads(reports["figures/fig1_layer2.json"])
    out: dict[str, Any] = {}
    for metric, _, _ in METRICS:
        out[metric] = {}
        for group in GROUPS:
            series = [
                s
                for s in doc["series"]
                if s["panel"] == "c" and s["match"] == metric and s["group"] == group
            ]
            kinds = sorted(s["kind"] for s in series)
            if kinds != ["match", "median"]:
                raise Refused(f"fig1_layer2.json panel c {metric} {group}: series {kinds}")
            points = next(s for s in series if s["kind"] == "match")["points"]
            median = next(s for s in series if s["kind"] == "median")["points"][0]
            out[metric][group] = {
                "points": [
                    {"match": p["x"], "value": p["value"], "refs": p["refs"]} for p in points
                ],
                "median": median["value"],
            }
    return out


def strip_claim(points: Mapping[str, Any]) -> dict[str, Any]:
    """The sentence over the strips: line depth greater (the back four nearer their own goal) and
    block length shorter in every match of both halves, from the least to the most. Refused if a
    point breaks it."""
    claim: dict[str, Any] = {}
    for metric, sign in (("line_height_m", 1), ("block_length_m", -1)):
        values = [p["value"] for g in GROUPS for p in points[metric][g]["points"]]
        if len(values) != 20 or not all(v * sign > 0 for v in values):
            raise Refused(
                f"a point of {metric} in panel c is not {'above' if sign > 0 else 'below'} 0: "
                "'in every match of both halves' would be false"
            )
        mags = sorted(abs(v) for v in values)
        claim[metric] = {"least": mags[0], "most": mags[-1], "matches": len(values)}
    return claim


def _readme_check() -> Any:
    """scripts/readme_check.py, whose resolver reads the README's keys."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "readme_check", Path(__file__).with_name("readme_check.py")
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("readme_check", module)
    spec.loader.exec_module(module)
    return module


def readme_keys() -> set[str]:
    """Every key README.src.json cites."""
    return {n["src"] for n in json.loads(README_SRC.read_text(encoding="utf-8"))["numbers"]}


def finding(src: str, which: str, reports: Mapping[str, bytes]) -> float:
    """One README number, read from the reports by its README.src.json key with the README's own
    resolver (``scripts/readme_check.py``)."""
    rc = _readme_check()
    path, _, expr = src.partition(":")
    name = path.removeprefix("reports/") if path.startswith("reports/") else f"../{path}"
    data = json.loads(reports[name])
    cand = rc.Candidates()
    if " / " in expr:
        left, _, right = expr.partition(" / ")
        a, b = rc.key_values(data, left.strip(), cand), rc.key_values(data, right.strip(), cand)
        value = abs(a / b) if which == "size" else a / b
    else:
        value = rc.key_values(data, expr.strip(), cand)
    if which == "band":
        value = cand.numbers[0]
    return round(float(value), 6)


def readme_text() -> str:
    """README.md as committed (LF), for the verdict's words and the paragraphs the page quotes."""
    return README.read_text(encoding="utf-8").replace("\r\n", "\n")


def readme_quotes(readme: str) -> dict[str, str]:
    """The README's paragraphs and fenced code the details quote (``README_PARAGRAPHS``,
    ``README_CODE``), verbatim; refused if one is missing or a lead opens two paragraphs."""
    out = {}
    paragraphs = [p.strip() for p in readme.split("\n\n")]
    for name, lead in README_PARAGRAPHS:
        found = [p for p in paragraphs if p.startswith(lead)]
        if len(found) != 1:
            raise Refused(f"README.md: {len(found)} paragraphs start with {lead!r}, not one")
        out[name] = found[0]
    for name, start, end in README_CODE:
        head = readme.find(start)
        tail = readme.find(end, head) if head >= 0 else -1
        fence = re.search(r"```[a-z]*\n(.*?)```", readme[head:tail], flags=re.DOTALL)
        if head < 0 or tail < 0 or fence is None:
            raise Refused(f"README.md: no fenced code between {start!r} and {end!r}")
        out[name] = fence.group(1).rstrip()
    return out


def findings(
    reports: Mapping[str, bytes], strip: Mapping[str, Any], keys: set[str], readme: str
) -> dict[str, Any]:
    """What the page quotes of the README: its numbers by their keys, over the twenty matches
    each metric's count of matches per split whose V1 minus V0 has the sign of its median, its
    verdict in its words, its closing sentence and the paragraphs the details fold; refused if a
    key is not the README's, the README does not say the verdict, or what it says of the signs is
    false."""
    numbers = {}
    for name, src, which in FINDINGS:
        if src not in keys:
            raise Refused(f"findings {name}: {src!r} is not a key of README.src.json")
        numbers[name] = {"src": src, "value": finding(src, which, reports)}
    signs = {}
    for metric, _, _ in METRICS:
        values = [p["value"] for g in GROUPS for p in strip[metric][g]["points"]]
        sign = 1 if statistics.median(values) > 0 else -1
        signs[metric] = {
            "sign": sign,
            "of": len(strip[metric]["calibration"]["points"]),
            **{
                g: sum(1 for p in strip[metric][g]["points"] if p["value"] * sign > 0)
                for g in GROUPS
            },
        }
    whole = {m for m, c in signs.items() if all(c[g] == len(strip[m][g]["points"]) for g in GROUPS)}
    for metric in EVERYWHERE:
        if metric not in whole:
            raise Refused(
                f"{metric} does not keep its sign in every match: the verdict would be false"
            )
    for metric in MIXED:
        if metric in whole:
            raise Refused(f"{metric} keeps its sign in every match: 'mixed' would be false")
    if sorted(m for _, ms, _ in VERDICT for m in ms) != sorted(m for m, _, _ in METRICS):
        raise Refused("the verdict does not group the seven metrics once each")
    folded = " ".join(readme.split())
    for words in [w for _, _, w in VERDICT] + [*README_SAYS, KEEP]:
        if words not in folded:
            raise Refused(f"README.md does not say {words!r}: the page's verdict would not be its")
    for name, group in (("nearest_below_cal", "calibration"), ("nearest_below_held", "held-out")):
        if numbers[name]["value"] != signs["nearest_rival_m"][group]:
            raise Refused(f"nearest rival's {group} count is not the README's ({name})")
    return {
        "keep": KEEP,
        "numbers": numbers,
        "readme": readme_quotes(readme),
        "signs": signs,
        "verdict": [{"group": g, "metrics": list(ms), "words": w} for g, ms, w in VERDICT],
    }


def context(reports: Mapping[str, bytes], match_id: int) -> dict[str, Any]:
    """The match's detection figures of ``layer2.json`` the page quotes."""
    m = json.loads(reports["layer2.json"])["matches"][str(match_id)]
    return {
        "player_detected": m["detection"]["player_detected"],
        "ball_distance": {k: v["detected"] for k, v in sorted(m["ball_distance"].items())},
        "line": {
            "all_detected": m["line"]["all_detected"],
            "events": m["line"]["events"],
            "detected_count": m["line"]["detected_count"],
        },
        "block": {"all_detected": m["block"]["all_detected"], "phases": m["block"]["phases"]},
    }


# --- the sidecar -------------------------------------------------------------------------------


def _r(values: Any, d: int = 2) -> Any:
    """Rounded for the sidecar; NaN becomes None."""
    if isinstance(values, np.ndarray):
        values = values.tolist()
    if isinstance(values, list):
        return [_r(v, d) for v in values]
    if values is None or (isinstance(values, float) and math.isnan(values)):
        return None
    return round(float(values), d)


def frame_stats(
    bronze: Bronze,
    players: Mapping[str, NDArray[Any]],
    clip_rows: NDArray[np.int64],
    key_row: int,
    pitch_area: float,
    half_width: float,
) -> dict[str, Any]:
    """Section 4.3: the camera's frame over the whole match, and over the clip."""
    has = ~np.isnan(bronze.corners).any(axis=(1, 2))
    if not has.any():
        raise Refused("no frame of the match has corners")
    listed = bronze.n_players > 0
    where = np.searchsorted(bronze.frame, players["frame"])
    if (bronze.frame[np.minimum(where, len(bronze.frame) - 1)] != players["frame"]).any():
        raise Refused("a player row has no bronze frame")
    with_frame = has[where]
    pts = np.stack([players["x"], players["y"]], axis=1).astype(np.float64)
    ins = inside(pts, bronze.corners[where])
    det = players["detected"].astype(np.bool_)
    seen, filled, blind = det & with_frame, ~det & with_frame, ~with_frame
    top = bronze.corners[has][:, 2:, 1]
    cut = float(np.max(top))
    at_cut = (np.abs(top - cut) < 1e-9).all(axis=1)
    areas = area(bronze.corners[has])
    apex = apexes(bronze.corners[has])
    apex = apex[~np.isnan(apex).any(axis=1)]
    if not len(apex):
        raise Refused("no frame's side edges meet")
    clip_q = bronze.corners[clip_rows]
    steps = np.hypot(*np.diff(clip_q, axis=0).transpose(2, 0, 1))
    clip_top = clip_q[:, 2:, 1]
    key_area = float(area(bronze.corners[[key_row]])[0])
    return {
        "frames": len(bronze.frame),
        "with_corners": int(has.sum()),
        "without_corners": int((~has).sum()),
        "without_no_player": int((~has & ~listed).sum()),
        "without_with_players": int((~has & listed).sum()),
        "without_players_listed": sorted({int(n) for n in bronze.n_players[~has & listed]}),
        "without_rows_detected": _r(det[blind].mean() if blind.any() else 0.0, 6),
        "seen_rows": int(seen.sum()),
        "seen_inside": _r(ins[seen].mean(), 6),
        "filled_rows": int(filled.sum()),
        "filled_inside": _r(ins[filled].mean(), 6),
        "far_cut_y_m": _r(cut, 2),
        "far_cut_share": _r(at_cut.mean(), 6),
        "far_cut_beyond_touchline_m": _r(cut - half_width, 2),
        "area_m2": {
            "median": _r(np.median(areas), 1),
            "p5": _r(np.percentile(areas, 5), 1),
            "p95": _r(np.percentile(areas, 95), 1),
            "pitch": _r(pitch_area, 1),
            "median_share": _r(float(np.median(areas)) / pitch_area, 6),
            "reception": _r(key_area, 1),
            "reception_share": _r(key_area / pitch_area, 6),
        },
        "apex": {
            "median": _r(np.median(apex, axis=0), 2),
            "x_p10_p90": _r(np.percentile(apex[:, 0], [10, 90]), 2),
            "y_p10_p90": _r(np.percentile(apex[:, 1], [10, 90]), 2),
            "behind_near_touchline_m": _r(-half_width - float(np.median(apex[:, 1])), 1),
        },
        "clip": {
            "without_corners": int(np.isnan(clip_q).any(axis=(1, 2)).sum()),
            "max_corner_step_m": _r(steps.max(), 2),
            "far_cut_share": _r((np.abs(clip_top - cut) < 1e-9).all(axis=1).mean(), 6),
            "area_m2": [_r(area(clip_q).min(), 1), _r(area(clip_q).max(), 1)],
        },
    }


def _clip_view(scene: Any) -> dict[str, Any]:
    """The fields of clip.json that the scene decides, computed again from the scene."""
    out = ~scene.rival_detected
    key = scene.key
    gaps = np.where(out, scene.rival_gap, 0)
    longest = int(gaps[key].max())
    return {
        "ball": {"detected": scene.ball_detected.tolist(), "gap_len": scene.ball_gap.tolist()},
        "defenders": [
            {
                "detected": scene.rival_detected[:, j].tolist(),
                "gap_len": scene.rival_gap[:, j].tolist(),
                "player_id": int(scene.rivals[j]),
            }
            for j in range(len(scene.rivals))
        ],
        "defenders_extrapolated": out.sum(axis=1).tolist(),
        "frames": scene.frame.tolist(),
        "key": {
            "defenders_extrapolated": int(out[key].sum()),
            "defenders_seen": int((~out[key]).sum()),
            "frame": int(scene.frame[key]),
            "index": key,
            "longest_gap_len": longest,
            "longest_gap_player_id": int(scene.rivals[int(gaps[key].argmax())])
            if longest
            else None,
        },
        "match_id": scene.match_id,
        "n_defenders": len(scene.rivals),
        "n_frames": len(scene.frame),
        "reception": {
            "event_subtype": scene.subtype,
            "frame": int(scene.frame[key]),
            "period": scene.period,
            "receiver_id": scene.receiver,
            "team_id": scene.team,
        },
        "receiver": {"detected": scene.me_detected.tolist(), "gap_len": scene.me_gap.tolist()},
    }


def against_clip(view: Mapping[str, Any], clip_json: Mapping[str, Any]) -> list[str]:
    """Rule 4: the page's reception is the video's, field by field."""
    problems = []
    for name in sorted(view):
        if view[name] != clip_json.get(name):
            problems.append(
                f"clip.json: {name} differs from the scene: the page would show another "
                "reception than the video"
            )
    return problems


def sidecar(inputs: Inputs, reports: Mapping[str, bytes]) -> dict[str, Any]:
    """Every number and position the page draws, from the inputs and the reports."""
    from ac2fb import clip

    scene = inputs.scene
    clip_json = json.loads(reports["clip/clip.json"])
    view = _clip_view(scene)
    problems = against_clip(view, clip_json)
    if problems:
        raise Refused(problems[0])
    sign = int(scene.sign)
    rows = inputs.bronze.rows(scene.frame)
    key_row = int(rows[scene.key])
    corners = inputs.bronze.corners[rows] * sign  # into the clip's frame, as the scene is
    if np.isnan(corners).any():
        raise Refused("a frame of the clip has no corners: the page would draw no frame there")
    stats = frame_stats(
        inputs.bronze, inputs.players, rows, key_row,
        clip.PITCH_LENGTH * clip.PITCH_WIDTH, clip.PITCH_WIDTH / 2,
    )  # fmt: skip
    if stats["seen_inside"] < SEEN_INSIDE_MIN or stats["filled_inside"] > FILLED_INSIDE_MAX:
        raise Refused(
            f"{stats['seen_inside']:.3f} of the detected rows and {stats['filled_inside']:.3f} of "
            "the filled ones lie inside the frame: 'the window the camera saw' would be false"
        )
    steps = np.hypot(*np.diff(corners, axis=0).transpose(2, 0, 1)).max(axis=1)
    every = np.concatenate([scene.rival_xy, scene.me[:, None], scene.ball[:, None]], axis=1)
    every = np.concatenate([every, scene.mate_xy], axis=1)
    lo, hi = np.nanmin(every, axis=(0, 1)) - CROP_PAD_M, np.nanmax(every, axis=(0, 1)) + CROP_PAD_M
    table = match_table(reports, scene.match_id)
    strip = strips(reports)
    by_metric = {r["metric"]: r for r in table}
    for metric, _, _ in METRICS:
        for group in GROUPS:
            for p in strip[metric][group]["points"]:
                v0, v1 = (_resolve(ref, reports) for ref in p["refs"])
                if round(v1 - v0, 9) != p["value"]:
                    raise Refused(
                        f"fig1_layer2.json {metric} {p['match']}: not V1 minus V0 of its cells"
                    )
            values = [p["value"] for p in strip[metric][group]["points"]]
            if round(statistics.median(values), 9) != strip[metric][group]["median"]:
                raise Refused(f"fig1_layer2.json {metric} {group}: the median is not of its points")
        mine = [
            p for p in strip[metric]["calibration"]["points"] if p["match"] == str(scene.match_id)
        ]
        if len(mine) != 1 or mine[0]["value"] != by_metric[metric]["diff"]:
            raise Refused(f"fig1_layer2.json {metric}: this match's point is not its V1 minus V0")
    line, block = inputs.units["line"], inputs.units["block"]
    if any(line.seen):
        raise Refused("a player of the line is seen: 'the back four are all filled in' is false")
    keeper = (block.phase or {}).get("keeper_id")
    if keeper not in block.player_ids or block.seen[block.player_ids.index(keeper)]:
        raise Refused("the block is not fixed by the goalkeeper filled in: the lead would be false")
    units = {}
    for name, u in inputs.units.items():
        units[name] = {
            "frame": u.frame,
            "index": int(np.flatnonzero(scene.frame == u.frame)[0]),
            "metric": u.metric,
            "value": round(u.value, 6),
            "player_ids": list(u.player_ids),
            "seen": list(u.seen),
            "gap_len": list(u.gap_len),
            "x": _r(list(u.x), 2),
            "v1": all(u.seen),
            **({"phase": u.phase} if u.phase else {}),
        }
    return {
        "about": (
            "Every number and position the page draws. Positions are metres in the clip's frame: "
            "the provider's x and y times sign, so the receiver's team attacks toward +x; the "
            "camera stands on the side of the pitch where y times sign is below 0, and the page "
            "draws the provider's frame (x times sign, y times sign) so that side is at the "
            "bottom of the plan. corners: the four corners of the camera's image on the pitch "
            "(bronze x_/y_ bottom/top left/right), bottom left, bottom right, top right, top "
            "left. apex: where the frame's two side edges meet; a camera that does not roll stands "
            "above the line from it along the camera's heading, at a height and a distance the "
            "data do not give. gap is gap_len in frames at 10 Hz (a hollow marker's label is "
            "gap / 10, one decimal, in seconds; it stays pinned over label_gap_s seconds, a "
            "drawing choice). units: the layer 2 units of this reception, read "
            "by ac2fb.reliability.metrics at their frame; seen is is_detected there. match: the "
            "match's cells of reports/reliability.csv; strips: figure 1, panel c. findings: what "
            "the page quotes of the README: its numbers, each with the README.src.json key it is "
            "read by, per metric and half the matches whose V1 minus V0 has the sign of its "
            "median, its verdict, its closing sentence and the paragraphs the details fold, "
            "verbatim."
        ),
        "camera": {
            "apex": _r(apexes(corners), 2),
            "apex_median": _r(np.median(apexes(corners), axis=0), 2),
            "area_m2": _r(area(corners), 1),
            "corners": _r(corners, 2),
            "cut_step_m": CUT_STEP_M,
            "cuts": int((steps > CUT_STEP_M).sum()),
        },
        "context": context(reports, scene.match_id),
        "crop": {"x": _r([lo[0], hi[0]], 2), "y": _r([lo[1], hi[1]], 2), "pad_m": CROP_PAD_M},
        "entities": {
            "ball": {
                "detected": scene.ball_detected.tolist(),
                "gap": scene.ball_gap.tolist(),
                "xy": _r(scene.ball, 2),
                "z": _r(inputs.bronze.ball_z[rows], 2),
            },
            "mates": {
                "detected": scene.mate_detected.tolist(),
                "ids": scene.mates.tolist(),
                "xy": _r(scene.mate_xy, 2),
            },
            "me": {
                "detected": scene.me_detected.tolist(),
                "gap": scene.me_gap.tolist(),
                "id": int(scene.receiver),
                "xy": _r(scene.me, 2),
            },
            "rivals": {
                "detected": scene.rival_detected.tolist(),
                "gap": scene.rival_gap.tolist(),
                "ids": scene.rivals.tolist(),
                "xy": _r(scene.rival_xy, 2),
            },
        },
        "fps": clip_json["video"]["fps"],
        "frame_stats": stats,
        "frames": view["frames"],
        "key": {**view["key"], "defenders_extrapolated_by_frame": view["defenders_extrapolated"]},
        "label_gap_s": LABEL_GAP_S,
        "match": {"rows": table},
        "match_id": scene.match_id,
        "n_defenders": view["n_defenders"],
        "n_frames": view["n_frames"],
        "reception": view["reception"],
        "rule": clip_json["rule"],
        "sign": sign,
        "sources": {name: hashlib.sha256(reports[name]).hexdigest() for name in SOURCES},
        "strips": {"claim": strip_claim(strip), "metrics": strip},
        "findings": findings(reports, strip, readme_keys(), readme_text()),
        "units": units,
    }


def canonical(document: Mapping[str, Any]) -> bytes:
    """The sidecar's bytes: sorted keys, one space of indent, LF, as clip.json."""
    return (
        json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def check_finite(value: Any, where: str = "payload") -> None:
    """Every scalar the page injects must be a finite number, a string, a bool or a declared
    null (the teammates' rows the provider does not list)."""
    if isinstance(value, dict):
        for key, item in value.items():
            check_finite(item, f"{where}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            check_finite(item, f"{where}[{i}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise Refused(f"{where} is {value}")
    elif value is None and not (
        where.startswith("payload.entities.mates.xy") or where.endswith("longest_gap_player_id")
    ):
        raise Refused(f"{where} is missing")


# --- the cross-check of a committed sidecar -----------------------------------------------------


def _leaves(value: Any, path: str = "") -> dict[str, Any]:
    """Each scalar of a nested dict by its dotted path ("line.events")."""
    if not isinstance(value, Mapping):
        return {path: value}
    out: dict[str, Any] = {}
    for key, item in value.items():
        out.update(_leaves(item, f"{path}.{key}" if path else str(key)))
    return out


def cross_check(doc: Mapping[str, Any], reports: Mapping[str, bytes]) -> list[str]:
    """Rules 4 to 6 and 9 on a sidecar as committed: its reception is clip.json's, its cells are
    reliability.csv's, its strips are figure 1's and the difference of their cells, its context
    is layer2.json's figure by figure, its findings are the README's numbers read by the README's
    keys, and its frame statistics keep the page's sentence true.
    One problem per broken number, named."""
    problems: list[str] = []
    clip_json = json.loads(reports["clip/clip.json"])
    rivals = doc["entities"]["rivals"]
    seen = {
        "frames": doc["frames"],
        "reception": doc["reception"],
        "match_id": doc["match_id"],
        "n_defenders": doc["n_defenders"],
        "n_frames": doc["n_frames"],
        "key": {k: v for k, v in doc["key"].items() if k != "defenders_extrapolated_by_frame"},
        "defenders_extrapolated": doc["key"]["defenders_extrapolated_by_frame"],
        "defenders": [
            {
                "detected": [f[j] for f in rivals["detected"]],
                "gap_len": [f[j] for f in rivals["gap"]],
                "player_id": pid,
            }
            for j, pid in enumerate(rivals["ids"])
        ],
        "receiver": {
            "detected": doc["entities"]["me"]["detected"],
            "gap_len": doc["entities"]["me"]["gap"],
        },
        "ball": {
            "detected": doc["entities"]["ball"]["detected"],
            "gap_len": doc["entities"]["ball"]["gap"],
        },
    }
    problems += [p.replace("the scene", "camera.json") for p in against_clip(seen, clip_json)]
    if doc["fps"] != clip_json["video"]["fps"]:
        problems.append("camera.json: fps is not the clip's")
    try:
        table = match_table(reports, int(doc["match_id"]))
    except Refused as exc:
        return [*problems, f"reliability.csv: {exc}"]
    for want, got in zip(table, doc["match"]["rows"], strict=False):
        for v in ("V0", "V1"):
            for col in ("mean", "n"):
                if got.get(v, {}).get(col) != want[v][col]:
                    problems.append(
                        f"camera.json: {want['metric']} {v} {col} is "
                        f"{got.get(v, {}).get(col)}, reliability.csv {want[v][col]}"
                    )
        if got.get("diff") != want["diff"]:
            problems.append(f"camera.json: {want['metric']} V1 - V0 is not the cells' difference")
    if len(doc["match"]["rows"]) != len(table):
        problems.append(
            f"camera.json: {len(doc['match']['rows'])} metrics, reliability.csv {len(table)}"
        )
    try:
        strip = strips(reports)
    except Refused as exc:
        return [*problems, f"fig1_layer2.json: {exc}"]
    mine = doc["strips"]["metrics"]
    for metric, _, _ in METRICS:
        for group in GROUPS:
            ours, theirs = mine.get(metric, {}).get(group, {}), strip[metric][group]
            if ours.get("median") != theirs["median"]:
                problems.append(f"camera.json: the {group} median of {metric} is not figure 1's")
            if len(ours.get("points", [])) != len(theirs["points"]):
                problems.append(f"camera.json: {metric} {group} has another number of points")
            for p, q in zip(ours.get("points", []), theirs["points"], strict=False):
                if p != q:
                    problems.append(
                        f"camera.json: the point of {metric} {p.get('match')} is not figure 1's"
                    )
                    continue
                v0, v1 = (_resolve(ref, reports) for ref in p["refs"])
                if round(v1 - v0, 9) != p["value"]:
                    problems.append(
                        f"fig1_layer2.json: {metric} {p['match']} is not V1 minus V0 "
                        "of the cells it cites"
                    )
    try:
        if doc["strips"]["claim"] != strip_claim(mine):
            problems.append("camera.json: the strips' sentence is not read from its points")
    except Refused as exc:
        problems.append(f"camera.json: {exc}")
    try:
        want_f = _leaves(findings(reports, strip, readme_keys(), readme_text()))
    except Refused as exc:
        problems.append(f"findings: {exc}")
    else:
        got_f = _leaves(doc.get("findings", {}))
        for path in sorted(want_f.keys() | got_f.keys()):
            if got_f.get(path) != want_f.get(path):
                problems.append(
                    f"camera.json: findings.{path} is {got_f.get(path)}, "
                    f"the artifact {want_f.get(path)}"
                )
    stats = doc["frame_stats"]
    if stats["seen_inside"] < SEEN_INSIDE_MIN or stats["filled_inside"] > FILLED_INSIDE_MAX:
        problems.append(
            f"camera.json: {stats['seen_inside']} of the detected rows inside the frame and "
            f"{stats['filled_inside']} of the filled: 'the window the camera saw' would be false"
        )
    if stats["clip"]["without_corners"] != 0:
        problems.append("camera.json: a frame of the clip has no corners")
    # the thesis (the share seen) and the story's counts: each figure of layer2.json, by its path
    want, got = _leaves(context(reports, int(doc["match_id"]))), _leaves(doc.get("context", {}))
    for path in sorted(want.keys() | got.keys()):
        if got.get(path) != want.get(path):
            problems.append(
                f"camera.json: context.{path} is {got.get(path)}, layer2.json {want.get(path)}"
            )
    for name in SOURCES:
        if doc["sources"].get(name) != hashlib.sha256(reports[name]).hexdigest():
            problems.append(f"camera.json: the hash of {name} is not the committed file's")
    return problems


# --- the template, the page ----------------------------------------------------------------------


#: A number with a unit of the page (decimal: the storyboard's rule; or whole, outside the CSS),
#: a count "k of n", or a digit in the page's visible HTML other than V0 and V1: the template
#: types none of them, every one arrives in the payload.
UNIT_DECIMAL = re.compile(r"[0-9]+\.[0-9]+ ?(m|s|%|m²)")
UNIT_WHOLE = re.compile(r"(?<![\w.#-])[0-9]+(?:\.[0-9]+)? ?(?:m²|m|s|%)(?![\w²])")
COUNT = re.compile(r"\b[0-9]+ of [0-9]+\b")
ALLOWED_DIGITS = re.compile(r"\bV[01]\b|\bh[1-6]\b|\bdata-[a-z0-9-]+")


def template_rules(template: str) -> list[str]:
    """What the template must not type (section 1 of the storyboard)."""
    problems = []
    for m in UNIT_DECIMAL.finditer(template):
        problems.append(f"the template types {m.group(0)!r}")
    no_style = re.sub(r"<style>.*?</style>", "", template, flags=re.DOTALL)
    for m in UNIT_WHOLE.finditer(no_style):
        problems.append(f"the template types {m.group(0)!r}")
    for m in COUNT.finditer(template):
        problems.append(f"the template types the count {m.group(0)!r}")
    html = re.sub(r"<(script|style)\b.*?</\1>", "", template, flags=re.DOTALL)
    text = re.sub(r"<[^>]*>", " ", html)
    for m in re.finditer(r"\S*[0-9]\S*", ALLOWED_DIGITS.sub("", text)):
        problems.append(f"the template's HTML types {m.group(0)!r}")
    return problems


def vendored_fonts(folder: Path) -> list[tuple[str, int, bytes]]:
    """The vendored faces (``FACES``), each read after its bytes hash to the sha256 the folder's
    README names for it."""
    readme = (folder / "README").read_text(encoding="utf-8")
    out = []
    for family, weight, name in FACES:
        digest = re.search(rf"{re.escape(name)}\s+sha256 ([0-9a-f]{{64}})", readme)
        if digest is None:
            raise Refused(f"{folder / 'README'} must name the sha256 of {name}")
        data = (folder / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest.group(1):
            raise Refused(f"{folder / name} does not hash to the sha256 in its README")
        out.append((family, weight, data))
    return out


def font_faces(fonts: Sequence[tuple[str, int, bytes]]) -> str:
    """The @font-face rules that inline the faces as data: URIs (base64 holds no `<`)."""
    return "".join(
        f'@font-face{{font-family:"{family}";font-weight:{weight};font-style:normal;'
        f"font-display:swap;src:url(data:font/woff2;base64,{base64.b64encode(data).decode()})"
        ' format("woff2")}\n'
        for family, weight, data in fonts
    )


def inlined_fonts(page: str) -> str:
    """The @font-face rules of a page, as ``font_faces`` writes them."""
    return "".join(re.findall(r"@font-face\{[^}]*\}\n", page))


def assemble(template: str, data: Mapping[str, Any], faces: str = "") -> str:
    """The template with the payload and the faces in place of their markers, once each."""
    for marker in (PAYLOAD, FONTS):
        if template.count(marker) != 1:
            raise Refused(f"the template must hold {marker} exactly once")
    # `</` inside a <script> would close it early, whatever the JSON says it means.
    blob = json.dumps(
        data, allow_nan=False, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).replace("</", "<\\/")
    return template.replace(PAYLOAD, blob).replace(FONTS, faces)


def payload_of(page: str) -> bytes:
    """The payload inlined in a page, as canonical sidecar bytes."""
    found = re.search(
        r'<script type="application/json" id="payload">(.*?)</script>', page, flags=re.DOTALL
    )
    if found is None:
        raise Refused('the page has no <script id="payload"> element')
    return canonical(json.loads(found.group(1).replace("<\\/", "</")))


#: What would make the page load something: an element with a source, a stylesheet link, a CSS
#: url or import, a script call that fetches, imports or opens a connection. Links (<a href>) do
#: not load, nor does a CSS url that is a woff2 data: URI (the faces, bytes of the page itself,
#: held to the vendored files by their hashes); any other data: source is still refused.
NETWORK = re.compile(
    r"""\bsrc\s*=|\bsrcset\b|<link\b|url\((?!data:font/woff2;base64,)|@import|\bfetch\("""
    r"""|\bimport\(|XMLHttpRequest|WebSocket|EventSource|sendBeacon|new Worker|<iframe|<img\b"""
    r"""|<object|<embed""",
    re.IGNORECASE,
)


def network_rules(page: str) -> list[str]:
    """The page loads nothing from the network (its links are <a> and load nothing)."""
    return [f"the page would load something: {m.group(0)!r}" for m in NETWORK.finditer(page)]


def static_problems(
    page: str,
    sidecar_bytes: bytes,
    template: str,
    reports: Mapping[str, bytes] | None = None,
    fonts: Path = FONTS_DIR,
) -> list[str]:
    """Rules 3 and 10, the template's, the fonts' and the network's: everything that needs no
    data; with the versioned reports, the sidecar held to them too (its cells, strips, context,
    findings, frame statistics and the reports' hashes: the cross-check, which reads no data)."""
    problems = []
    if reports is not None:
        try:
            problems += cross_check(json.loads(sidecar_bytes), reports)
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"{SIDECAR}: cannot be read against the reports ({exc!r})")
    try:
        if payload_of(page) != sidecar_bytes:
            problems.append(f"{PAGE}: its payload differs from {SIDECAR}")
    except (Refused, ValueError) as exc:
        problems.append(f"{PAGE}: {exc}")
    try:
        if inlined_fonts(page) != font_faces(vendored_fonts(fonts)):
            problems.append(f"{PAGE}: the inlined fonts are not vendor/fonts' (by their hashes)")
    except Refused as exc:
        problems.append(f"fonts: {exc}")
    problems += [f"camera_template.html: {p}" for p in template_rules(template)]
    problems += [f"{PAGE}: {p}" for p in network_rules(page)]
    return problems


def first_difference(was: bytes, now: bytes) -> int:
    """The first line (from 1) where two texts differ."""
    old, new = was.splitlines(), now.splitlines()
    pairs = enumerate(zip(old, new, strict=False), start=1)
    return next((i for i, (a, b) in pairs if a != b), min(len(old), len(new)) + 1)


def compare(name: str, committed: bytes | None, recomputed: bytes) -> list[str]:
    """Rules 1 and 2: a committed file equals its recomputation byte for byte."""
    if committed is None:
        return [f"{name}: missing"]
    if committed != recomputed:
        return [
            f"{name}: differs from the recomputation (first at line "
            f"{first_difference(committed, recomputed)})"
        ]
    return []


# --- build and check -----------------------------------------------------------------------------


def read_reports(reports: Path) -> dict[str, bytes]:
    """The reports the sidecar hashes (``SOURCES``)."""
    missing = [name for name in SOURCES if not (reports / name).is_file()]
    if missing:
        raise FileNotFoundError(f"missing in {reports}: {', '.join(missing)}")
    return {name: (reports / name).read_bytes() for name in SOURCES}


def build(inputs: Inputs, reports: Mapping[str, bytes], template: str) -> tuple[bytes, str]:
    """The sidecar's bytes and the page, the vendored faces inlined."""
    faces = font_faces(vendored_fonts(FONTS_DIR))
    doc = sidecar(inputs, reports)
    check_finite(doc)
    body = canonical(doc)
    return body, assemble(template, json.loads(body), faces)


def counts(doc: Mapping[str, Any]) -> dict[str, int]:
    """What the check verified: frames, entities, positions, numbers, units, frame statistics."""
    ent = doc["entities"]
    positions = sum(len(f) for f in ent["rivals"]["xy"]) + sum(len(f) for f in ent["mates"]["xy"])
    positions += len(ent["me"]["xy"]) + len(ent["ball"]["xy"]) + 4 * len(doc["camera"]["corners"])

    def leaves(v: Any) -> int:
        if isinstance(v, dict):
            return sum(leaves(x) for x in v.values())
        if isinstance(v, list):
            return sum(leaves(x) for x in v)
        return 1 if isinstance(v, int | float) and not isinstance(v, bool) else 0

    numbers = sum(
        leaves(doc[k]) for k in ("match", "strips", "units", "frame_stats", "context", "findings")
    )

    def stats(v: Any) -> int:
        return sum(stats(x) for x in v.values()) if isinstance(v, dict) else 1

    return {
        "frames": len(doc["frames"]),
        "entities": len(ent["rivals"]["ids"]) + len(ent["mates"]["ids"]) + 2,
        "positions": positions,
        "numbers": numbers,
        "units": len(doc["units"]),
        "stats": stats(doc["frame_stats"]),
    }


def check(
    inputs: Inputs,
    reports: Mapping[str, bytes],
    template: str,
    committed_sidecar: bytes | None,
    committed_page: bytes | None,
) -> tuple[list[str], str]:
    """Every rule of the storyboard's section 8.1; the problems and what was verified."""
    problems: list[str] = []
    try:
        body, page = build(inputs, reports, template)
    except Refused as exc:
        return [str(exc.code)], "nothing: the recomputation was refused"
    problems += compare(SIDECAR, committed_sidecar, body)
    problems += compare(PAGE, committed_page, page.encode("utf-8"))
    if committed_sidecar is not None:
        problems += cross_check(json.loads(committed_sidecar), reports)
    if committed_page is not None and committed_sidecar is not None:
        problems += static_problems(committed_page.decode("utf-8"), committed_sidecar, template)
    n = counts(json.loads(body))
    equal = "differ" if compare(PAGE, committed_page, page.encode()) else "equal"
    said = (
        f"verified: {n['frames']} frames, {n['entities']} entities, {n['positions']} "
        f"positions, {n['numbers']} numbers, {n['units']} units, {n['stats']} frame "
        f"statistics; page bytes {equal}"
    )
    return problems, said


def main(argv: Sequence[str] | None = None) -> int:
    from ac2fb import clip
    from ac2fb.protocol.data import HeldOutLocked

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--match", type=int, default=clip.DEFAULT_MATCH)
    parser.add_argument("--reports", type=Path, default=REPORTS)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--check-static", action="store_true")
    args = parser.parse_args(argv)
    template = TEMPLATE.read_text(encoding="utf-8")
    side, page_path = args.out_dir / SIDECAR, args.out_dir / PAGE
    if args.check_static:
        problems = static_problems(
            page_path.read_text(encoding="utf-8"),
            side.read_bytes(),
            template,
            read_reports(args.reports),
        )
        print(
            "verified: the sidecar against the versioned reports (cells, strips, context, "
            f"findings, frame statistics, {len(SOURCES)} hashes), the payload against the sidecar, "
            f"the {len(FACES)} inlined fonts against vendor/fonts by their hashes, the template's "
            "rules, a page that loads nothing"
        )
        for problem in problems:
            print(f"  - {problem}")
        print("camera page static: OK" if not problems else "camera page static: FAILED")
        return 0 if not problems else 1
    try:
        reports = read_reports(args.reports)
        inputs = read_inputs(args.match)
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"missing data: {exc}", file=sys.stderr)
        return 2
    if args.check:
        committed = (
            side.read_bytes() if side.is_file() else None,
            page_path.read_bytes() if page_path.is_file() else None,
        )
        problems, said = check(inputs, reports, template, *committed)
        print(said)
        for problem in problems:
            print(f"  - {problem}")
        print("camera page: OK" if not problems else "camera page: FAILED")
        return 0 if not problems else 1
    body, page = build(inputs, reports, template)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    side.write_bytes(body)
    page_path.write_bytes(page.encode("utf-8"))
    print(f"wrote {side} ({len(body) / 1024:.0f} KB)")
    print(f"wrote {page_path} ({len(page.encode()) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
