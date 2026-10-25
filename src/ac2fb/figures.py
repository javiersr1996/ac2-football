"""The two figures of the README, drawn from the committed reports and from nothing else.

``figures`` is pure: it is handed the bytes of the files under ``reports/`` (and
``reports/heldout/``) and returns the bytes of four files, so it opens nothing (the command line
reads and writes; the door to the data stays single). Each figure is an SVG and a sidecar JSON.

- Figure 1 (layer 2, the 10 calibration and the 10 held-out matches, each one drawn): detection
  by distance to the ball; the share of the filled frames that lies in each gap-length band;
  per metric, V1 minus V0 and the error of amputation.
- Figure 2 (layer 3, branch B: calibration only, because layer 3 died before any held-out
  reading): the effect and the pre-trend per match in V0, V1 and V2 with no extrapolated player,
  and the death (D3), stated.

The sidecar lists every plotted value with the artefact cells it comes from (``refs``, the rule
that turns them into the value, and the value) and every number of every label with the same.
``reports/figures/*.json`` is the contract; the SVG is the same data drawn. Both are byte-stable:
the hash salt, the metadata and the font handling are fixed, and the axes sit at fixed places, so
no text metric moves a line. The artefacts of a reference are named ``file#path`` (JSON, parts
separated by ``/``) or ``file#column=value,...:column`` (CSV, one row selected).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, cast

import matplotlib
import matplotlib.style
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator

from ac2fb.reliability.runs import BANDS as BAND_CUTS
from ac2fb.reliability.visibility import BALL_DISTANCE_EDGES

__all__ = ["INPUTS", "OUTPUTS", "Built", "CheckResult", "build", "check"]

INPUTS = (
    "layer2.json",
    "reliability.csv",
    "amputation.csv",
    "calibration.json",
    "heldout/layer2.json",
    "heldout/reliability.csv",
    "heldout/amputation.csv",
)
FIG1 = "fig1_layer2"
FIG2 = "fig2_layer3"
OUTPUTS = (f"{FIG1}.svg", f"{FIG1}.json", f"{FIG2}.svg", f"{FIG2}.json")

CAL, HELD = "calibration", "held-out"
COLOUR = {CAL: "#0072B2", HELD: "#D55E00"}
MARKER = {CAL: "o", HELD: "s"}
STYLE = {CAL: "-", HELD: "--"}
PREFIX = {CAL: "", HELD: "heldout/"}


def _bins() -> list[tuple[str, str]]:
    """Key and axis label of each ball-distance bin, both read from the edges of the reports."""
    edges = [0, *(int(e) for e in BALL_DISTANCE_EDGES)]
    bins = [(f"{lo:02d}_{hi:02d}", f"{lo}-{hi}") for lo, hi in zip(edges, edges[1:], strict=False)]
    return [*bins, (f"{edges[-1]}_plus", f"{edges[-1]}+")]


def _bands() -> list[tuple[str, str]]:
    """Key and axis label of each gap band, read from the cuts (frames at 10 Hz) of the runs."""
    cuts = [0, *(cut // 10 for _, cut in BAND_CUTS[:-1])]
    first, *middle = BAND_CUTS[:-1]
    names = [(first[0], f"up to {cuts[1]} s")]
    names += [
        (k, f"{lo}-{hi} s") for (k, _), (lo, hi) in zip(middle, pairwise(cuts[1:]), strict=True)
    ]
    return [*names, (BAND_CUTS[-1][0], f"over {cuts[-1]} s")]


BINS = _bins()
BANDS = _bands()
METRICS = [
    ("pressure_index", "Pressure index"),
    ("nearest_rival_m", "Nearest rival (m)"),
    ("line_height_m", "Line height (m)"),
    ("line_reaction_m", "Line reaction (m)"),
    ("block_width_m", "Block width (m)"),
    ("block_length_m", "Block length (m)"),
    ("block_area_m2", "Block area (m²)"),
]
VARIANTS = [
    ("V0", "V0: every unit", "#0072B2", "o"),
    ("V1", "V1: players seen throughout", "#009E73", "s"),
    ("V2", "V2: none extrapolated", "#CC79A7", "^"),
]

SVG_RC: dict[str, Any] = {
    "svg.fonttype": "none",
    "svg.hashsalt": "ac2fb-figures",
    "axes.unicode_minus": False,
    "font.family": ["DejaVu Sans"],
    "font.size": 8.5,
    "axes.edgecolor": "#444444",
    "axes.linewidth": 0.8,
    "axes.titlesize": 9.5,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
}
# The strips of figure 1 (panels c and d): their ticks are the only scale, read at the README's
# width (about 900 px for 8 in), so they are larger than the rest and at most four intervals.
STRIP_TICK_SIZE = 12
STRIP_TICK_BINS = 4
STRIP_PITCH = 0.95  # inches from one strip to the next: the strip, its tick labels and air
SVG_METADATA: dict[str, str | None] = {"Date": None, "Creator": None}
INK = "#222222"
GREY = "#777777"


class _Reports:
    """The bytes of the committed reports, parsed on demand, and the one resolver of a reference."""

    def __init__(self, files: Mapping[str, bytes]) -> None:
        self.files = files
        self._json: dict[str, Any] = {}
        self._csv: dict[str, list[dict[str, str]]] = {}

    def json(self, name: str) -> Any:
        if name not in self._json:
            self._json[name] = json.loads(self.files[name].decode("utf-8"))
        return self._json[name]

    def csv(self, name: str) -> list[dict[str, str]]:
        if name not in self._csv:
            text = self.files[name].decode("utf-8")
            self._csv[name] = list(csv.DictReader(io.StringIO(text, newline="")))
        return self._csv[name]

    def resolve(self, ref: str) -> Any:
        name, _, path = ref.partition("#")
        if name.endswith(".json"):
            node = self.json(name)
            for part in path.split("/"):
                node = node[part]
            return node
        where, _, column = path.rpartition(":")
        wanted = [pair.split("=", 1) for pair in where.split(",")]
        rows = [r for r in self.csv(name) if all(r[k] == v for k, v in wanted)]
        if len(rows) != 1:
            raise KeyError(f"{ref}: {len(rows)} rows")
        cell = rows[0][column]
        return None if cell == "" else float(cell)

    def number(self, formula: str, refs: Sequence[str]) -> float | None:
        """The value of ``formula`` over ``refs``; ``None`` when a cell is empty."""
        found = [self.resolve(r) for r in refs]
        if formula == "count":
            return float(len(found[0]))
        if any(v is None for v in found):
            return None
        values = [float(v) for v in found]
        if formula == "value":
            return values[0]
        if formula == "diff":  # second minus first
            return round(values[1] - values[0], 9)
        if formula == "median":
            return round(statistics.median(values), 9)
        raise ValueError(f"unknown formula {formula!r}")


def _cell(file: str, **where: str) -> str:
    """Reference to a CSV cell: ``_cell("reliability.csv", match_id=..., ...)`` plus ``column``."""
    column = where.pop("column")
    return f"{file}#" + ",".join(f"{k}={v}" for k, v in where.items()) + f":{column}"


def _point(rep: _Reports, x: object, formula: str, refs: Sequence[str]) -> dict[str, Any] | None:
    value = rep.number(formula, refs)
    if value is None:
        return None
    return {"x": x, "formula": formula, "refs": list(refs), "value": value}


def _series(
    panel: str, group: str, match: str, kind: str, points: list[dict[str, Any] | None]
) -> dict[str, Any]:
    return {
        "panel": panel,
        "group": group,
        "match": match,
        "kind": kind,
        "points": [p for p in points if p is not None],
    }


def _label(
    rep: _Reports, template: str, *numbers: tuple[str, Sequence[str], int]
) -> tuple[str, dict[str, Any]]:
    """A label whose numbers are printed from their artefacts: ``template`` has ``{0}``, ``{1}``."""
    shown: list[dict[str, Any]] = []
    for formula, refs, decimals in numbers:
        value = rep.number(formula, refs)
        if value is None:
            raise ValueError(f"label {template!r}: empty cell in {refs}")
        shown.append(
            {
                "as": f"{value:.{decimals}f}",
                "decimals": decimals,
                "formula": formula,
                "refs": list(refs),
                "value": value,
            }
        )
    text = template.format(*[n["as"] for n in shown])
    return text, {"text": text, "numbers": shown}


def _strip_xlim(values: Sequence[float]) -> tuple[float, float]:
    """The x-limits of a strip of figure 1, panels c and d: anchored at 0, with a 6 % pad.

    Without the anchor an error of 0.8 to 1.4 m in d would fill its strip as -37 to +0.7 m
    fills c, and "filling costs little" would not be visible.
    """
    anchored = [*values, 0.0]
    low, high = min(anchored), max(anchored)
    pad = (high - low) * 0.06 or 1.0
    return low - pad, high + pad


def _matches(rep: _Reports, group: str) -> list[str]:
    return sorted(rep.json(f"{PREFIX[group]}layer2.json")["matches"])


def _canonical(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _svg(fig: Figure) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="svg", metadata=SVG_METADATA)
    return buffer.getvalue().replace(b"\r\n", b"\n")


def _digests(rep: _Reports, names: Sequence[str]) -> dict[str, str]:
    return {n: hashlib.sha256(rep.files[n]).hexdigest() for n in names}


def _axes(fig: Figure, left: float, bottom: float, width: float, height: float) -> Axes:
    """An axes at a place in inches from the lower left corner: no layout engine, no text metric."""
    w, h = fig.get_size_inches()
    ax = fig.add_axes((left / w, bottom / h, width / w, height / h))
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=3, width=0.8, colors=INK)
    return ax


def _text(fig: Figure, x: float, y: float, s: str, **kw: Any) -> None:
    w, h = fig.get_size_inches()
    kw.setdefault("color", INK)
    fig.text(x / w, y / h, s, **kw)


def _key(fig: Figure, x: float, y: float, group: str, s: str) -> None:
    """A legend entry drawn by hand: a sample line, then the words, at fixed places."""
    w, h = fig.get_size_inches()
    fig.add_artist(
        Line2D(
            [x / w, (x + 0.35) / w],
            [y / h, y / h],
            transform=fig.transFigure,
            color=COLOUR[group],
            ls=STYLE[group],
            lw=1.8,
            marker=MARKER[group],
            ms=4.5,
            markevery=[0, 0],
        )
    )
    _text(fig, x + 0.45, y, s, ha="left", va="center", fontsize=8.5)


# --- figure 1 ---


@dataclass(frozen=True)
class _Drawn:
    """A figure and the document that says where each of its values and numbers comes from."""

    fig: Figure
    document: dict[str, Any]

    @property
    def counts(self) -> tuple[int, int]:
        points = sum(len(s["points"]) for s in self.document["series"])
        return points, len(self.document["labels"])


def _ref(group: str, match: str, path: str) -> str:
    return f"{PREFIX[group]}layer2.json#matches/{match}/{path}"


def _lines(
    rep: _Reports,
    panel: str,
    cells: list[tuple[str, str]],
    path: str,
    matches: Mapping[str, list[str]],
) -> list[dict[str, Any]]:
    """Per match one line over the bins or bands, and the median of the half as a thick one."""
    out = []
    for g in (CAL, HELD):
        for m in matches[g]:
            points = [
                _point(rep, name, "value", [_ref(g, m, path.format(key))]) for key, name in cells
            ]
            out.append(_series(panel, g, m, "match", points))
        medians = [
            _point(rep, name, "median", [_ref(g, m, path.format(key)) for m in matches[g]])
            for key, name in cells
        ]
        out.append(_series(panel, g, "median", "median", medians))
    return out


def _dots(
    rep: _Reports, metric: str, matches: Mapping[str, list[str]]
) -> dict[str, list[dict[str, Any]]]:
    """Panels c and d for one metric: V1 minus V0, and the error of amputation, per match."""
    out: dict[str, list[dict[str, Any]]] = {"c": [], "d": []}
    for g in (CAL, HELD):
        rel, amp = f"{PREFIX[g]}reliability.csv", f"{PREFIX[g]}amputation.csv"
        panels: dict[str, list[dict[str, Any] | None]] = {"c": [], "d": []}
        for m in matches[g]:
            where = {"match_id": m, "metric": metric, "ball_stratum": "all"}
            v0 = _cell(rel, **where, variant="V0", column="mean")
            v1 = _cell(rel, **where, variant="V1", column="mean")
            panels["c"].append(_point(rep, m, "diff", [v0, v1]))
            error = _cell(amp, match_id=m, metric=metric, band="all", column="mean_abs_error")
            panels["d"].append(_point(rep, m, "value", [error]))
        for panel, points in panels.items():
            out[panel].append(_series(panel, g, metric, "match", points))
            kept = [p["value"] for p in points if p is not None]
            tick = {
                "x": "median",
                "formula": "median_of_points",
                "of": kept,
                "value": round(statistics.median(kept), 9),
            }
            out[panel].append(_series(panel, g, metric, "median", [tick]))
    return out


def _fig1(rep: _Reports) -> _Drawn:
    matches = {g: _matches(rep, g) for g in (CAL, HELD)}
    series = _lines(rep, "a", BINS, "ball_distance/{}/detected", matches)
    series += _lines(rep, "b", BANDS, "reacquisition/by_band/{}/frame_share", matches)
    for key, _ in METRICS:
        for panel_series in _dots(rep, key, matches).values():
            series += panel_series
    t_cal, l_cal = _label(rep, "calibration, {0} matches", ("count", ["layer2.json#matches"], 0))
    t_held, l_held = _label(
        rep, "held-out, {0} matches", ("count", ["heldout/layer2.json#matches"], 0)
    )

    height = 13.1
    fig = Figure(figsize=(8.0, height))
    _key(fig, 0.75, height - 0.3, CAL, t_cal)
    _key(fig, 3.2, height - 0.3, HELD, t_held)
    _text(fig, 5.55, height - 0.3, "thin: one match. thick: median", color=GREY, va="center")

    for panel, left, width, cells, ylim in (
        ("a", 0.75, 3.3, BINS, 1.0),
        ("b", 4.65, 3.1, BANDS, 0.8),
    ):
        ax = _axes(fig, left, height - 3.8, width, 2.9)
        index = {name: i for i, (_, name) in enumerate(cells)}
        for s in (s for s in series if s["panel"] == panel):
            med = s["kind"] == "median"
            ax.plot(
                [index[p["x"]] for p in s["points"]],
                [p["value"] for p in s["points"]],
                color=COLOUR[s["group"]],
                ls=STYLE[s["group"]] if med else "-",
                lw=2.6 if med else 0.9,
                alpha=1.0 if med else 0.45,
                marker=MARKER[s["group"]] if med else None,
                ms=4.5,
                zorder=3 if med else 2,
            )
        ax.set_xticks(range(len(cells)), [name for _, name in cells])
        ax.set_ylim(0, ylim)
    ax_a, ax_b = fig.axes
    ax_a.set_xlabel("distance of the player to the ball (m)")
    ax_a.set_ylabel("share of player-frames detected")
    ax_a.set_title("a. The camera loses the players far from the ball", loc="left")
    ax_b.set_xlabel("length of the gap the model fills")
    ax_b.set_ylabel("share of the filled frames")
    ax_b.set_title("b. Where the model fills in", loc="left")

    _text(fig, 0.2, height - 5.1, "Per metric and match, in the metric's own unit", weight="bold")
    for left, head, sub in (
        (1.7, "c. V1 minus V0", "players seen throughout the window; line = no change"),
        (4.9, "d. Error of amputation", "mean absolute error, gaps filled by a straight line"),
    ):
        _text(fig, left, height - 5.5, head, weight="bold")
        _text(fig, left, height - 5.75, sub, fontsize=8, color=GREY)
    for i, (key, name) in enumerate(METRICS):
        bottom = height - 6.7 - i * STRIP_PITCH
        _text(fig, 1.55, bottom + 0.25, name, ha="right", va="center", fontsize=10)
        for panel, left in (("c", 1.7), ("d", 4.9)):
            ax = _axes(fig, left, bottom, 2.7, 0.5)
            ax.tick_params(axis="x", labelsize=STRIP_TICK_SIZE)
            ax.spines["left"].set_visible(False)
            ax.set_yticks([])
            ax.set_ylim(-0.5, 0.5)
            mine = [s for s in series if s["panel"] == panel and s["match"] == key]
            values = [p["value"] for s in mine for p in s["points"]]
            if panel == "c":
                ax.axvline(0, color=GREY, lw=0.8, zorder=1)
            ax.set_xlim(*_strip_xlim(values))
            ax.xaxis.set_major_locator(MaxNLocator(STRIP_TICK_BINS))
            ax.ticklabel_format(useOffset=False, style="plain", axis="x")
            for s in mine:
                g, y = s["group"], 0.2 if s["group"] == CAL else -0.2
                xs = [p["value"] for p in s["points"]]
                if s["kind"] == "median":
                    ax.plot(xs, [y], ls="", marker="|", ms=15, mew=2.4, c=COLOUR[g], zorder=3)
                else:
                    ax.plot(
                        xs,
                        [y] * len(xs),
                        ls="",
                        marker=MARKER[g],
                        ms=4.2,
                        c=COLOUR[g],
                        mec="white",
                        mew=0.4,
                        alpha=0.85,
                        zorder=2,
                    )
    _text(
        fig,
        0.2,
        0.18,
        "Upper strip of each pair: calibration. Lower strip: held-out. Tick: median of the half.",
        fontsize=8,
        color=GREY,
        va="center",
    )
    sources = _digests(rep, INPUTS)
    document = {"figure": FIG1, "sources": sources, "series": series, "labels": [l_cal, l_held]}
    return _Drawn(fig, document)


# --- figure 2 ---


def _fig2(rep: _Reports) -> _Drawn:
    cal = "calibration.json"
    matches = [str(m) for m in rep.json(cal)["matches"]]
    where = {"V0": "variants/V0", "V1": "variants/V1", "V2": "beside/V2/classes/0"}
    series: list[dict[str, Any]] = []
    for panel, column, pooled in (("a", "effect", "t"), ("b", "pretrend", "pretrend_sd")):
        for v, _, _, _ in VARIANTS:
            points = []
            for m in matches:
                points.append(_point(rep, m, "value", [f"{cal}#{where[v]}/matches/{m}/{column}"]))
            series.append(_series(panel, v, "match", "match", points))
            total = _point(rep, "pooled", "value", [f"{cal}#{where[v]}/{pooled}"])
            series.append(_series(panel, v, "pooled", "pooled", [total]))

    floor = f"{cal}#criteria/D3/values/floor"
    t_floor, l_floor = _label(rep, "D3 floor {0}", ("value", [floor], 3))
    t_v2, l_v2 = _label(
        rep,
        "V2: none extrapolated ({0} of {1} matches)",
        ("count", [f"{cal}#beside/V2/classes/0/matches"], 0),
        ("count", [f"{cal}#matches"], 0),
    )
    verdict = _label(
        rep,
        "D3 kills layer 3 at the calibration half: effect {0} sd, floor {1} sd, pre-trend {2} sd.",
        ("value", [f"{cal}#criteria/D3/values/effect"], 3),
        ("value", [floor], 3),
        ("value", [f"{cal}#criteria/D3/values/pretrend"], 3),
    )
    passed = "passed" if rep.resolve(f"{cal}#variants/V0/bar/passed") else "failed"
    killing = rep.resolve(f"{cal}#criteria/D5/killing")
    alone = " alone" if len(killing) == 1 else ""
    bar = _label(
        rep,
        f"V0 {passed} its own bar (p = {{0}}, {{1}} of {{2}} matches agree): "
        f"the kill is {' and '.join(killing)}{alone}.",
        ("value", [f"{cal}#variants/V0/bar/p"], 4),
        ("value", [f"{cal}#variants/V0/bar/agreeing"], 0),
        ("value", [f"{cal}#variants/V0/bar/matches"], 0),
    )
    # The units with an extrapolated player at the reception fill no cell (used = 0 in both
    # classes) and the class with none is V1 unit for unit: said only when the artefact says so.
    none_used = all(
        rep.resolve(f"{cal}#beside/V2/classes/{c}/used") == 0 for c in ("1", "2_or_more")
    )
    v2_is_v1 = all(
        rep.resolve(f"{cal}#beside/V2/classes/0/matches/{m}/effect")
        == rep.resolve(f"{cal}#variants/V1/matches/{m}/effect")
        for m in matches
    )
    if none_used and v2_is_v1:
        wording = (
            "Units with an extrapolated player at the reception, {0} with one and {1} with two or "
            "more, fill no cell: V2 is V1, no estimate for them."
        )
    else:
        wording = "Units with an extrapolated player at the reception: {0} with one, {1} with more."
    empty = _label(
        rep,
        wording,
        ("value", [f"{cal}#beside/V2/classes/1/units"], 0),
        ("value", [f"{cal}#beside/V2/classes/2_or_more/units"], 0),
    )

    height = 7.9
    fig = Figure(figsize=(8.0, height))
    w, h = fig.get_size_inches()
    for i, (v, name, colour, marker) in enumerate(VARIANTS):
        x = (0.3, 1.9, 4.3)[i]
        fig.add_artist(
            Line2D(
                [x / w],
                [(height - 0.3) / h],
                transform=fig.transFigure,
                ls="",
                marker=marker,
                ms=6,
                color=colour,
            )
        )
        _text(fig, x + 0.15, height - 0.3, t_v2 if v == "V2" else name, va="center")

    order = [*matches, "pooled"]
    ypos = {m: len(matches) - 1 - i for i, m in enumerate(matches)} | {"pooled": -1.0}
    shift = {"V0": 0.3, "V1": 0.0, "V2": -0.3}
    style = {v: (colour, marker) for v, _, colour, marker in VARIANTS}
    for panel, left, title in (
        ("a", 1.15, "a. Effect of pressure on the ball's advance"),
        ("b", 4.95, "b. Same difference before the reception"),
    ):
        ax = _axes(fig, left, height - 5.5, 2.9, 4.6)
        for s in (s for s in series if s["panel"] == panel):
            colour, marker = style[s["group"]]
            pooled = s["kind"] == "pooled"
            for p in s["points"]:
                ax.plot(
                    [p["value"]],
                    [ypos[p["x"]] + shift[s["group"]] * (1.0 if pooled else 0.75)],
                    ls="",
                    marker=marker,
                    ms=8 if pooled else 5,
                    c=colour,
                    mec="black" if pooled else "white",
                    mew=1.0 if pooled else 0.4,
                    zorder=3,
                )
        ax.axvline(0, color=GREY, lw=0.8, zorder=1)
        ax.axhline(-0.35, color="#BBBBBB", lw=0.6, ls=":", zorder=1)
        ax.set_ylim(-1.6, len(matches) + 0.5)
        ax.set_xlim(-0.5, 0.5)
        ax.set_xlabel("sd of the ball's advance")
        ax.set_title(title, loc="left")
        if panel == "a":
            limit = rep.number("value", [floor]) or 0.0
            ax.axvspan(-limit, limit, color="#DDDDDD", alpha=0.7, lw=0, zorder=0)
            ax.text(0, len(matches) + 0.4, t_floor, ha="center", va="top", color=GREY, fontsize=8)
            ax.set_yticks([ypos[m] for m in order], order)
        else:
            ax.set_yticks([])
            ax.spines["left"].set_visible(False)

    _text(
        fig,
        0.2,
        height - 6.0,
        "Calibration matches. Effect left of the line: pressure reduces the advance. "
        "Outlined: pooled. Grey: D3 floor.",
        fontsize=8,
        color=GREY,
        va="center",
    )
    _text(
        fig,
        0.2,
        height - 6.45,
        "No held-out reading for layer 3: the protocol is dead, the held-out was read for layer 2.",
        weight="bold",
        va="center",
    )
    for i, (text, _) in enumerate((verdict, bar, empty)):
        _text(fig, 0.2, height - 6.85 - i * 0.33, text, va="center")
    document = {
        "figure": FIG2,
        "sources": _digests(rep, [cal]),
        "series": series,
        "labels": [l_floor, l_v2, verdict[1], bar[1], empty[1]],
    }
    return _Drawn(fig, document)


@dataclass(frozen=True)
class Built:
    files: dict[str, bytes]
    points: int
    labels: int


def build(files: Mapping[str, bytes]) -> Built:
    """The four output files from the bytes of the reports, and what they hold."""
    rep = _Reports(files)
    out: dict[str, bytes] = {}
    points = labels = 0
    # the defaults first, so a matplotlibrc of the user moves no byte
    with matplotlib.style.context("default"), matplotlib.rc_context(cast("Any", SVG_RC)):
        for name, draw in ((FIG1, _fig1), (FIG2, _fig2)):
            drawn = draw(rep)
            out[f"{name}.svg"] = _svg(drawn.fig)
            out[f"{name}.json"] = _canonical(drawn.document)
            points, labels = points + drawn.counts[0], labels + drawn.counts[1]
    return Built(out, points, labels)


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    problems: list[str]
    files: int  # of the committed files, how many exist
    points: int
    labels: int


def _first_difference(was: bytes, now: bytes) -> int:
    old, new = was.splitlines(), now.splitlines()
    pairs = enumerate(zip(old, new, strict=False), start=1)
    return next((i for i, (a, b) in pairs if a != b), min(len(old), len(new)) + 1)


def check(files: Mapping[str, bytes], committed: Mapping[str, bytes | None]) -> CheckResult:
    """Draw the figures again and compare them, byte for byte, with the committed files."""
    built = build(files)
    problems = []
    for name in OUTPUTS:
        old = committed.get(name)
        if old is None:
            problems.append(f"{name}: missing")
        elif old != built.files[name]:
            line = _first_difference(old, built.files[name])
            problems.append(f"{name}: differs from the recomputation (first at line {line})")
    found = sum(committed.get(name) is not None for name in OUTPUTS)
    return CheckResult(not problems, problems, found, built.points, built.labels)
