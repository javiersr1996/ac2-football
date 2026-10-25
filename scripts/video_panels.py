"""The panels of the two figures drawn again for the video, from their sidecars, in large type.

The committed figures are drawn for a page: at 1080p their 8 pt labels are 20 px tall and one
panel fills half the frame. Each shot of the video gets its own panel at the stage's size
(15.2 x 8.55 in, 100 px per inch) with 22 pt type: the same values, read from
``reports/figures/*.json`` (the contract of the figures, every plotted value with its source),
the same colours, markers and wording, and no neighbour cut at an edge. Nothing here reads a
report; the committed SVGs are not touched.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import matplotlib
import matplotlib.style
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from ac2fb import figures
from ac2fb.figures import CAL, COLOUR, GREY, HELD, INK, MARKER, STYLE, VARIANTS

SIZE = (15.2, 8.55)  # inches: the stage of the video at 100 px per inch
RC: dict[str, Any] = {
    "font.family": ["DejaVu Sans"],
    "font.size": 22,
    "axes.titlesize": 24,
    "axes.titleweight": "bold",
    "xtick.labelsize": 22,
    "ytick.labelsize": 22,
    "axes.edgecolor": "#444444",
    "axes.linewidth": 1.2,
    "axes.unicode_minus": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
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
    ax.tick_params(length=6, width=1.2, colors=INK, pad=8)
    return ax


def _text(fig: Figure, x: float, y: float, s: str, **kw: Any) -> None:
    w, h = fig.get_size_inches()
    kw.setdefault("color", INK)
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
            alpha=1.0 if med else 0.45,
            marker=MARKER[g] if med else None,
            ms=12,
            zorder=3 if med else 2,
        )
    ax.set_xticks(range(len(figures.BINS)), [name for _, name in figures.BINS])
    ax.set_ylim(0, 1.0)
    ax.set_xlabel("distance of the player to the ball (m)")
    ax.set_ylabel("share of player-frames detected")
    ax.set_title("a. The camera loses the players far from the ball", loc="left", pad=16)
    key = [
        Line2D([], [], color=COLOUR[g], ls=STYLE[g], lw=5, marker=MARKER[g], ms=12, label=label)
        for g, label in ((CAL, doc["labels"][0]["text"]), (HELD, doc["labels"][1]["text"]))
    ]
    key.append(Line2D([], [], color=GREY, lw=1.8, alpha=0.6, label="thin: one match"))
    ax.legend(handles=key, loc="upper right", frameon=False, handlelength=2.2)
    return Drawn(fig, {"a": ax})


def strips(doc: Mapping[str, Any], keys: Sequence[str]) -> Drawn:
    """Figure 1, panel c, the strips of ``keys``: V1 minus V0 per match, calibration above."""
    fig = Figure(figsize=SIZE)
    names = dict(figures.METRICS)
    height, gap = 2.0, 1.2  # the strip, then its tick labels
    total = len(keys) * height + (len(keys) - 1) * gap
    top = (SIZE[1] - 1.7 + total) / 2  # centred under the three title lines
    _text(
        fig, 0.7, SIZE[1] - 0.7, "c. V1 minus V0: players seen throughout the window", weight="bold"
    )
    for line, words in enumerate(
        (
            "per match, in the metric's own unit; line = no change",
            "upper strip: calibration, lower strip: held-out, tick: median",
        )
    ):
        _text(fig, 0.7, SIZE[1] - 1.15 - 0.4 * line, words, fontsize=21, color=GREY)
    axes = {}
    for i, key in enumerate(keys):
        bottom = top - height - i * (height + gap)
        ax = _axes(fig, 4.7, bottom, 10.0, height)
        ax.spines["left"].set_visible(False)
        ax.set_yticks([])
        ax.set_ylim(-0.5, 0.5)
        mine = [s for s in _series(doc, "c") if s["match"] == key]
        values = [p["value"] for s in mine for p in s["points"]]
        ax.axvline(0, color=GREY, lw=1.5, zorder=1)
        ax.set_xlim(*figures._strip_xlim(values))
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
                    mec="white",
                    mew=1.0,
                    alpha=0.85,
                    zorder=2,
                )
        _text(fig, 4.4, bottom + height / 2, names[key], ha="right", va="center", fontsize=26)
        axes[key] = ax
    return Drawn(fig, axes)


def layer3(doc: Mapping[str, Any]) -> Drawn:
    """Figure 2: the effect and the pre-trend per match and pooled, V0, V1 and V2, the D3 floor."""
    fig = Figure(figsize=SIZE)
    v0 = next(s for s in _series(doc, "a") if s["group"] == "V0" and s["kind"] == "match")
    matches = [p["x"] for p in v0["points"]]
    floor_label, v2_label = doc["labels"][0], doc["labels"][1]
    floor = float(floor_label["numbers"][0]["value"])
    order = [*matches, "pooled"]
    ypos = {m: len(matches) - 1 - i for i, m in enumerate(matches)} | {"pooled": -1.0}
    shift = {"V0": 0.3, "V1": 0.0, "V2": -0.3}
    style = {v: (colour, marker) for v, _, colour, marker in VARIANTS}
    names = {v: name for v, name, _, _ in VARIANTS} | {"V2": v2_label["text"]}
    axes = {}
    for panel, left, title in (
        ("a", 2.1, "a. Effect of pressure\non the ball's advance"),
        ("b", 9.3, "b. Same difference\nbefore the reception"),
    ):
        ax = _axes(fig, left, 1.5, 5.6, 4.6)  # the two-line title clears the two-row key
        for s in _series(doc, panel):
            colour, marker = style[s["group"]]
            pooled = s["kind"] == "pooled"
            for p in s["points"]:
                ax.plot(
                    [p["value"]],
                    [ypos[p["x"]] + shift[s["group"]] * (1.0 if pooled else 0.75)],
                    ls="",
                    marker=marker,
                    ms=16 if pooled else 9,
                    c=colour,
                    mec="black" if pooled else "white",
                    mew=1.6 if pooled else 0.6,
                    zorder=3,
                )
        ax.axvline(0, color=GREY, lw=1.5, zorder=1)
        ax.axhline(-0.35, color="#BBBBBB", lw=1.0, ls=":", zorder=1)
        ax.set_ylim(-1.6, len(matches) + 0.5)
        ax.set_xlim(-0.5, 0.5)
        ax.set_xlabel("sd of the ball's advance")
        ax.set_title(title, loc="left", pad=14)
        if panel == "a":
            ax.axvspan(-floor, floor, color="#DDDDDD", alpha=0.7, lw=0, zorder=0)
            ax.text(0, len(matches) + 0.4, floor_label["text"], ha="center", va="top", color=GREY)
            ax.set_yticks([ypos[m] for m in order], order)
        else:
            ax.set_yticks([])
            ax.spines["left"].set_visible(False)
        axes[panel] = ax
    key = [
        Line2D([], [], ls="", marker=marker, ms=12, color=colour, label=names[v])
        for v, _, colour, marker in VARIANTS
    ]
    fig.legend(handles=key, loc="upper left", ncol=2, frameon=False, bbox_to_anchor=(0.04, 0.97))
    return Drawn(fig, axes)


def draw_all(folder: Path) -> dict[str, Drawn]:
    """Every panel the video shows, keyed by its name in the storyboard, from ``folder``'s JSON."""
    doc1 = json.loads((folder / "fig1_layer2.json").read_text(encoding="utf-8"))
    doc2 = json.loads((folder / "fig2_layer3.json").read_text(encoding="utf-8"))
    with matplotlib.style.context("default"), matplotlib.rc_context(cast("Any", RC)):
        return {
            "panel_a": panel_a(doc1),
            "line_height": strips(doc1, ["line_height_m"]),
            "block_length": strips(doc1, ["block_length_m"]),
            "pressure_rival": strips(doc1, ["pressure_index", "nearest_rival_m"]),
            "layer3": layer3(doc2),
        }
