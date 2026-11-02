"""The panels of figure 1 drawn again for the video, from their sidecars, in large type.

The committed figures are drawn for a page: at 1080p their 8 pt labels are 20 px tall and one
panel fills half the frame. Each shot of the video gets its own panel at the stage's size
(15.2 x 8.55 in, 100 px per inch) with 22 pt type: the same values, read from
``reports/figures/*.json`` (the contract of the figures, every plotted value with its source),
the same markers and wording, and no neighbour cut at an edge. The theme is the video's: a
near-black ground, light text, neon green for the calibration half and orange for the held-out
half (circles and squares as in the figures; the two keep a clear lightness gap under a
deuteranopia simulation, which green and the palette's light orange do not).
Nothing here reads a report; the committed SVGs are not touched.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import matplotlib
import matplotlib.style
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from ac2fb import figures
from ac2fb.figures import CAL, HELD, MARKER, STYLE

SIZE = (15.2, 8.55)  # inches: the stage of the video at 100 px per inch
BG, PANEL, BORDER = "#0B0F0D", "#0A0E0C", "#26302A"
TEXT, MUTED, FAINT = "#DDE5DF", "#93A198", "#7D8C83"
AXES = "#5F6E65"
GREEN, ORANGE = "#32FE6B", "#FF8A3D"
COLOUR = {CAL: GREEN, HELD: ORANGE}
HEADING = "Chakra Petch"  # the heading face when its files are given; DejaVu Sans otherwise
RC: dict[str, Any] = {
    "font.family": ["DejaVu Sans"],
    "font.size": 22,
    "axes.titlesize": 24,
    "axes.titleweight": "bold",
    "xtick.labelsize": 22,
    "ytick.labelsize": 22,
    "axes.edgecolor": AXES,
    "axes.linewidth": 1.2,
    "axes.unicode_minus": False,
    "text.color": TEXT,
    "axes.labelcolor": TEXT,
    "axes.titlecolor": TEXT,
    "xtick.color": AXES,
    "ytick.color": AXES,
    "xtick.labelcolor": TEXT,
    "ytick.labelcolor": TEXT,
    "legend.labelcolor": TEXT,
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "savefig.facecolor": BG,
}
Box = tuple[float, float, float, float]  # left, top, right, bottom, inches from the top left


@dataclass(frozen=True)
class Drawn:
    """A panel and the axes a window of the video can name."""

    fig: Figure
    axes: dict[str, Axes]

    def window(
        self,
        name: str,
        x: tuple[float, float],
        y: tuple[float, float],
        pad: Box = (0.0, 0.0, 0.0, 0.0),
    ) -> Box:
        """The data rectangle of axes ``name`` as inches from the top left, padded outwards."""
        points = self.axes[name].transData.transform([(x[0], y[0]), (x[1], y[1])]) / self.fig.dpi
        (x0, y0), (x1, y1) = points.tolist()
        height = float(self.fig.get_figheight())
        return x0 - pad[0], height - y1 - pad[1], x1 + pad[2], height - y0 + pad[3]

    def save(self, path: Path, dpi: int) -> None:
        with matplotlib.style.context("default"), matplotlib.rc_context(cast("Any", RC)):
            self.fig.savefig(path, dpi=dpi)


def _axes(fig: Figure, left: float, bottom: float, width: float, height: float) -> Axes:
    """An axes at a place in inches from the lower left corner, as ``ac2fb.figures`` places them."""
    w, h = fig.get_size_inches()
    ax = fig.add_axes((left / w, bottom / h, width / w, height / h))
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=6, width=1.2, color=AXES, labelcolor=TEXT, pad=8)
    return ax


def _text(fig: Figure, x: float, y: float, s: str, **kw: Any) -> None:
    w, h = fig.get_size_inches()
    kw.setdefault("color", TEXT)
    fig.text(x / w, y / h, s, **kw)


def _series(doc: Mapping[str, Any], panel: str) -> list[dict[str, Any]]:
    return [s for s in doc["series"] if s["panel"] == panel]


def panel_a(doc: Mapping[str, Any]) -> Drawn:
    """Figure 1, panel a: detection by distance to the ball, a line per match, medians thick."""
    fig = Figure(figsize=SIZE)
    ax = _axes(fig, 1.9, 1.45, 12.7, 6.1)
    index = {name: i for i, (_, name) in enumerate(figures.BINS)}
    for s in _series(doc, "a"):
        med, g = s["kind"] == "median", s["group"]
        ax.plot(
            [index[p["x"]] for p in s["points"]],
            [p["value"] for p in s["points"]],
            color=COLOUR[g],
            ls=STYLE[g] if med else "-",
            lw=5 if med else 1.8,
            alpha=1.0 if med else 0.5,
            marker=MARKER[g] if med else None,
            ms=12,
            zorder=3 if med else 2,
        )
    ax.set_xticks(range(len(figures.BINS)), [name for _, name in figures.BINS])
    ax.set_ylim(0, 1.0)
    ax.set_xlabel("distance of the player to the ball (m)")
    ax.set_ylabel("share of player-frames detected")
    ax.set_title("The camera loses the players far from the ball", loc="left", pad=16)
    key = [
        Line2D([], [], color=COLOUR[g], ls=STYLE[g], lw=5, marker=MARKER[g], ms=12, label=label)
        for g, label in ((CAL, doc["labels"][0]["text"]), (HELD, doc["labels"][1]["text"]))
    ]
    key.append(Line2D([], [], color=MUTED, lw=1.8, alpha=0.8, label="thin: one match"))
    ax.legend(handles=key, loc="upper right", frameon=False, handlelength=2.2)
    return Drawn(fig, {"a": ax})


def strips(doc: Mapping[str, Any], keys: Sequence[str]) -> Drawn:
    """Figure 1, panel c, the strips of ``keys``: V1 minus V0 per match, calibration above, over a
    grey band of panel d's fill-in error (amputation), from 0 to its worst match of the split."""
    fig = Figure(figsize=SIZE)
    names = dict(figures.METRICS)
    height, gap = 2.0, 1.2  # the strip, then its tick labels
    total = len(keys) * height + (len(keys) - 1) * gap
    head, foot = 2.3, 0.5  # the four title lines above the strips; the last tick labels below
    top = SIZE[1] - head - (SIZE[1] - head - foot - total) / 2  # centred between the two
    _text(fig, 0.7, SIZE[1] - 0.7, "Seen whole minus all moments, per match", weight="bold")
    # The definition the sentence leans on, in the text colour (21 pt here is 29 px on screen).
    _text(
        fig,
        0.7,
        SIZE[1] - 1.15,
        "seen whole: every player of the metric seen · all moments: the fill-in kept",
        fontsize=21,
    )
    for line, words in enumerate(
        (
            "in the metric's own unit · grey band: the fill-in's mean absolute error, worst match",
            "upper strip: calibration, lower strip: held-out, tick: median, line: no change",
        )
    ):
        _text(fig, 0.7, SIZE[1] - 1.55 - 0.4 * line, words, fontsize=21, color=MUTED)
    axes = {}
    for i, key in enumerate(keys):
        bottom = top - height - i * (height + gap)
        ax = _axes(fig, 4.7, bottom, 10.0, height)
        ax.spines["left"].set_visible(False)
        ax.set_yticks([])
        ax.set_ylim(-0.5, 0.5)
        mine = [s for s in _series(doc, "c") if s["match"] == key]
        values = [p["value"] for s in mine for p in s["points"]]
        error = {  # panel d: each match's mean absolute amputation error, its worst per split
            s["group"]: max(p["value"] for p in s["points"])
            for s in _series(doc, "d")
            if s["match"] == key and s["kind"] == "match"
        }
        for g, (low, high) in ((CAL, (0.5, 1.0)), (HELD, (0.0, 0.5))):
            ax.axvspan(-error[g], error[g], low, high, color=TEXT, alpha=0.16, lw=0, zorder=0)
        ax.axvline(0, color=MUTED, lw=1.5, zorder=1)
        ax.set_xlim(*figures._strip_xlim([*values, *error.values(), *(-e for e in error.values())]))
        ax.ticklabel_format(useOffset=False, style="plain", axis="x")
        for s in mine:
            g, y = s["group"], 0.2 if s["group"] == CAL else -0.2
            xs = [p["value"] for p in s["points"]]
            if s["kind"] == "median":
                ax.plot(xs, [y], ls="", marker="|", ms=50, mew=6, c=COLOUR[g], zorder=3)
            else:
                ax.plot(
                    xs,
                    [y] * len(xs),
                    ls="",
                    marker=MARKER[g],
                    ms=13,
                    c=COLOUR[g],
                    mec=BG,
                    mew=1.0,
                    alpha=0.9,
                    zorder=2,
                )
        _text(fig, 4.4, bottom + height / 2, names[key], ha="right", va="center", fontsize=26)
        axes[key] = ax
    return Drawn(fig, axes)


def draw_all(folder: Path, fonts: Mapping[str, Path] | None = None) -> dict[str, Drawn]:
    """Every panel the video shows, keyed by its name in the storyboard, from ``folder``'s JSON.

    ``fonts`` are TTF files to register; with them the heading face is used, without them the
    panels are drawn in DejaVu Sans (the geometry the tests check does not depend on the face).
    """
    doc1 = json.loads((folder / "fig1_layer2.json").read_text(encoding="utf-8"))
    rc = dict(RC)
    if fonts:
        for path in fonts.values():
            font_manager.fontManager.addfont(str(path))
        rc["font.family"] = [HEADING]
    with matplotlib.style.context("default"), matplotlib.rc_context(cast("Any", rc)):
        return {
            "panel_a": panel_a(doc1),
            "line_height": strips(doc1, ["line_height_m"]),
            "block_length": strips(doc1, ["block_length_m"]),
            "pressure_rival": strips(doc1, ["pressure_index", "nearest_rival_m"]),
        }
