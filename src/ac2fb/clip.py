"""The 10 s clip of the video: one reception, defenders the camera saw and ones the model filled.

``choose`` picks the reception by a rule written here (:class:`Rule`), not by hand; ``build`` draws
it. Positions, detection flags and ``gap_len`` come from the long table of layer 2 (``MatchData``),
so a held-out match is refused by the door before this module sees a row. The module is pure
with respect to files: it returns the bytes of the sidecar JSON and of the still PNG, and
:func:`encode_mp4` pipes the frames to ``ffmpeg`` for the video (the command line writes the rest).

The rule. Candidates are the ``player_possession`` events with a team and a player (the receiver)
whose receiver and the ball are detected at the first frame of the event and with at least
``min_seen`` rivals detected there. They rank by the number of rivals extrapolated at that frame
(more first), then by the longest ``gap_len`` among the rivals (longer first), then by period and
frame (earlier first). The first candidate whose window is complete wins: ``frames`` frames
(10 Hz, so 100 are 10 s) from ``before`` frames before the reception, inside one period, with
the receiver, the ball and each rival present in every frame, and a ``gap_len`` for each rival in
every frame. "Defenders" are the receiver's rivals, goalkeeper included.

The picture. Defenders detected are filled markers; extrapolated ones are hollow and carry their
``gap_len`` in seconds (``gap_len`` / 10, one decimal). Teammates are small blue dots, hollow when
extrapolated and with no label; the receiver has a black ring; the pitch is turned so the
receiver's team attacks to the right. The sidecar lists, per frame, the detection and ``gap_len``
of every defender, the receiver and the ball, so each number drawn is in it, plus the hash of the
raw pixels of all frames: the encoder decides the bytes of the MP4, the pixels it was given are
what the hash fixes.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import matplotlib
import matplotlib.image
import matplotlib.patheffects
import matplotlib.style
import numpy as np
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Arc, Circle, Rectangle
from numpy.typing import NDArray

from ac2fb.reliability.match import MatchData, locate_rows, players_at

__all__ = [
    "DEFAULT_MATCH",
    "DEFAULT_RULE",
    "Built",
    "CheckResult",
    "NoReception",
    "Rule",
    "Scene",
    "build",
    "check",
    "choose",
    "describe",
    "encode_mp4",
    "ffmpeg",
]

DEFAULT_MATCH = 1874553  # the match of the README's quick block, so a judge can regenerate it
HZ = 10  # the provider's frames per second
FPS = 10  # the clip plays in real time
WIDTH, HEIGHT = 1280, 720
PITCH_LENGTH, PITCH_WIDTH = 105.0, 68.0
MP4_TAG = (
    "ac2fb clip frames_sha256="  # in the MP4's comment: ties the file to the pixels it was given
)
VERMILION, BLUE, INK, GREY = "#D55E00", "#0072B2", "#222222", "#777777"

RC: dict[str, Any] = {
    "axes.unicode_minus": False,
    "font.family": ["DejaVu Sans"],
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
}


@dataclass(frozen=True)
class Rule:
    """The window and the one threshold of the rule above."""

    before: int = 30  # frames before the reception
    frames: int = 100  # frames in the clip: 10 s at 10 Hz
    min_seen: int = 4  # rivals detected at the reception, so the clip shows both kinds


DEFAULT_RULE = Rule()


class NoReception(ValueError):
    """No reception of the match has a complete window under the rule."""


@dataclass(frozen=True)
class Scene:
    """What the clip draws, in the match's frame, per window frame (``n`` frames)."""

    match_id: int
    period: int
    receiver: int
    team: int
    subtype: str | None
    sign: int
    rule: Rule
    key: int  # index of the reception within the window
    frame: NDArray[np.int64]
    ball: NDArray[np.float64]  # (n, 2)
    ball_detected: NDArray[np.bool_]
    ball_gap: NDArray[np.int64]
    me: NDArray[np.float64]  # the receiver, (n, 2)
    me_detected: NDArray[np.bool_]
    me_gap: NDArray[np.int64]
    rivals: NDArray[np.int64]  # (k,) player ids, ascending
    rival_xy: NDArray[np.float64]  # (n, k, 2)
    rival_detected: NDArray[np.bool_]  # (n, k)
    rival_gap: NDArray[np.int64]
    mates: NDArray[np.int64]  # (m,) the receiver's teammates present at the reception
    mate_xy: NDArray[np.float64]  # (n, m, 2), nan where the provider lists no row
    mate_detected: NDArray[np.bool_]


@dataclass(frozen=True)
class Built:
    """The sidecar and the still as bytes, the hash of the pixels, and what to re-render."""

    sidecar: bytes
    still: bytes
    still_pixels: NDArray[np.uint8]
    frames_sha256: str
    n_frames: int
    scene: Scene


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    problems: list[str]
    frames: int  # frames re-rendered and hashed
    video_bytes: int | None  # size of the committed video, None if it is missing


def describe(rule: Rule) -> str:
    """The rule in words, with its numbers: it goes into the sidecar."""
    return (
        "Receptions are the player_possession events with a team and a player whose receiver and "
        f"the ball are detected at the first frame and with at least {rule.min_seen} rivals "
        "detected there. They rank by the number of rivals extrapolated at that frame (more "
        "first), then by the longest gap_len among the rivals (longer first), then by period "
        f"and frame (earlier first). The first whose window is complete wins: {rule.frames} "
        f"frames at {HZ} Hz from {rule.before} frames before the reception, inside one period, "
        "with the receiver, the ball and each rival present and each rival with a gap_len in "
        "every frame. Defenders are the receiver's rivals, goalkeeper included."
    )


def _complete(
    match: MatchData,
    frames: NDArray[np.int64],
    period: int,
    receiver: int,
    rivals: NDArray[np.int64],
) -> tuple[NDArray[np.int64], NDArray[np.int64]] | None:
    """Row indices of the receiver (n,) and of the rivals (n, k); None if the window has a hole."""
    n = len(frames)
    ids = np.concatenate([[receiver], rivals]).astype(np.int64)
    rows = locate_rows(match, np.repeat(ids, n), np.tile(frames, len(ids))).reshape(len(ids), n)
    if (rows < 0).any():
        return None
    if (match.period[rows] != period).any() or (match.gap[rows[1:]] < 0).any():
        return None
    where = np.searchsorted(match.ball_frame, frames)
    if (where >= len(match.ball_frame)).any():
        return None
    if (match.ball_frame[where] != frames).any() or (match.ball_period[where] != period).any():
        return None
    return rows[0], rows[1:].T


def choose(match: MatchData, rule: Rule = DEFAULT_RULE) -> Scene:
    """The scene of the reception the rule picks; :class:`NoReception` if none has a window."""
    ranked: list[tuple[int, int, int, int, int, str | None, NDArray[np.int64]]] = []
    for e in match.events:
        if e.family != "player_possession" or e.player is None or e.team is None:
            continue
        car = locate_rows(match, np.array([e.player]), np.array([e.frame_start]))[0]
        ball = int(np.searchsorted(match.ball_frame, e.frame_start))
        if car < 0 or not match.detected[car] or ball >= len(match.ball_frame):
            continue
        if match.ball_frame[ball] != e.frame_start or not match.ball_detected[ball]:
            continue
        rows = players_at(match, e.frame_start)
        rival = rows[match.team[rows] != e.team]
        if int(match.detected[rival].sum()) < rule.min_seen:
            continue
        out = rival[~match.detected[rival]]
        longest = int(match.gap[out].max()) if len(out) else 0
        ranked.append((-len(out), -longest, e.period, e.frame_start, e.player, e.subtype, rival))
    ranked.sort(key=lambda r: r[:4])
    for _, _, period, key, player, subtype, rival in ranked:
        team = _team_of(match, player, key)
        ids = np.sort(match.player[rival])
        frames = np.arange(key - rule.before, key - rule.before + rule.frames, dtype=np.int64)
        found = _complete(match, frames, period, player, ids)
        if found is None:
            continue
        return _scene(match, rule, period, key, player, team, subtype, frames, ids, found)
    raise NoReception(
        f"no reception of match {match.match_id} has a complete window of {rule.frames} frames"
    )


def _team_of(match: MatchData, player: int, frame: int) -> int:
    return int(match.team[locate_rows(match, np.array([player]), np.array([frame]))[0]])


def _scene(
    match: MatchData,
    rule: Rule,
    period: int,
    key: int,
    player: int,
    team: int,
    subtype: str | None,
    frames: NDArray[np.int64],
    rivals: NDArray[np.int64],
    found: tuple[NDArray[np.int64], NDArray[np.int64]],
) -> Scene:
    me_rows, rival_rows = found
    n = len(frames)
    sign = match.attack_sign[(period, team)]
    where = np.searchsorted(match.ball_frame, frames)

    def turned(x: NDArray[np.float64], y: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.stack([x * sign, y * sign], axis=-1)

    at_key = players_at(match, key)
    mates = np.sort(
        match.player[at_key[(match.team[at_key] == team) & (match.player[at_key] != player)]]
    )
    mate_rows = locate_rows(match, np.repeat(mates, n), np.tile(frames, len(mates)))
    mate_rows = mate_rows.reshape(len(mates), n).T
    safe = np.maximum(mate_rows, 0)
    mate_xy = turned(match.x[safe], match.y[safe])
    mate_xy[mate_rows < 0] = np.nan
    return Scene(
        match_id=match.match_id,
        period=period,
        receiver=player,
        team=team,
        subtype=subtype,
        sign=sign,
        rule=rule,
        key=rule.before,
        frame=frames,
        ball=turned(match.ball_x[where], match.ball_y[where]),
        ball_detected=match.ball_detected[where],
        ball_gap=match.ball_gap[where],
        me=turned(match.x[me_rows], match.y[me_rows]),
        me_detected=match.detected[me_rows],
        me_gap=match.gap[me_rows],
        rivals=rivals,
        rival_xy=turned(match.x[rival_rows], match.y[rival_rows]),
        rival_detected=match.detected[rival_rows],
        rival_gap=match.gap[rival_rows],
        mates=mates,
        mate_xy=mate_xy,
        mate_detected=match.detected[safe] & (mate_rows >= 0),
    )


# --- drawing ---------------------------------------------------------------------------------


def _pitch(ax: Axes) -> None:
    half_l, half_w = PITCH_LENGTH / 2, PITCH_WIDTH / 2
    line: dict[str, Any] = {"fill": False, "edgecolor": "#8A9A83", "linewidth": 2.0, "zorder": 1}
    ax.add_patch(Rectangle((-half_l, -half_w), PITCH_LENGTH, PITCH_WIDTH, **line))
    ax.plot([0, 0], [-half_w, half_w], color="#8A9A83", linewidth=2.0, zorder=1)
    ax.add_patch(Circle((0, 0), 9.15, **line))
    for side in (-1, 1):
        for depth, width in ((16.5, 40.32), (5.5, 18.32)):
            x0 = side * half_l if side < 0 else half_l - depth
            ax.add_patch(Rectangle((x0, -width / 2), depth, width, **line))
        spot = side * (half_l - 11.0)
        ax.add_patch(Circle((spot, 0), 0.35, facecolor="#8A9A83", edgecolor="none", zorder=1))
        theta = (-53.0, 53.0) if side < 0 else (127.0, 233.0)
        ax.add_patch(
            Arc(
                (spot, 0),
                18.3,
                18.3,
                theta1=theta[0],
                theta2=theta[1],
                **{k: v for k, v in line.items() if k != "fill"},
            )
        )
    ax.set_facecolor("#F1F5EC")
    ax.set_xlim(-half_l - 1.5, half_l + 1.5)
    ax.set_ylim(-half_w - 1.5, half_w + 1.5)
    ax.set_aspect("equal")
    ax.axis("off")


def _fig_text(fig: Figure, x: float, y: float, s: str, **kw: Any) -> Any:
    """Text at a place in inches from the lower left corner."""
    w, h = fig.get_size_inches()
    kw.setdefault("color", INK)
    return fig.text(x / w, y / h, s, **kw)


def _fig_marker(fig: Figure, x: float, y: float, **kw: Any) -> None:
    w, h = fig.get_size_inches()
    ax = fig.add_axes((0, 0, 1, 1), facecolor="none")
    ax.set_axis_off()
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.scatter([x], [y], **kw)


class _Painter:
    """One figure, drawn once and moved frame by frame."""

    def __init__(self, scene: Scene) -> None:
        self.scene = scene
        fig = Figure(figsize=(WIDTH / 100, HEIGHT / 100), dpi=100)
        self.fig, self.canvas = fig, FigureCanvasAgg(fig)
        w, h = fig.get_size_inches()
        halo = [matplotlib.patheffects.withStroke(linewidth=4, foreground="white")]
        _fig_text(
            fig,
            0.4,
            h - 0.62,
            "Defenders the camera saw, and the ones the model filled in",
            fontsize=22,
            fontweight="bold",
        )
        _fig_text(
            fig,
            0.4,
            h - 1.02,
            f"SkillCorner broadcast tracking, match {scene.match_id}, reception by player "
            f"{scene.receiver}",
            fontsize=17,
            color=GREY,
        )
        self.clock = _fig_text(fig, 0.4, 0.28, "", fontsize=30, fontweight="bold")
        self.ax = fig.add_axes((0.3 / w, 0.85 / h, 8.55 / w, 5.35 / h))
        _pitch(self.ax)
        self.ax.annotate(
            "",
            xy=(0.97, -0.03),
            xytext=(0.62, -0.03),
            xycoords="axes fraction",
            arrowprops={"arrowstyle": "-|>", "color": GREY, "linewidth": 2},
        )
        self.ax.text(
            0.60,
            -0.03,
            "receiver's team attacks",
            transform=self.ax.transAxes,
            ha="right",
            va="center",
            fontsize=16,
            color=GREY,
        )
        ax = self.ax
        self.mates_filled = ax.scatter(
            [], [], s=70, c=BLUE, edgecolors="white", linewidths=1, zorder=3
        )
        self.mates_hollow = ax.scatter(
            [], [], s=70, facecolors="white", edgecolors=BLUE, linewidths=1.6, zorder=3
        )
        self.filled = ax.scatter(
            [], [], s=330, c=VERMILION, edgecolors="white", linewidths=1.5, zorder=5
        )
        self.hollow = ax.scatter(
            [], [], s=330, facecolors="white", edgecolors=VERMILION, linewidths=3.4, zorder=5
        )
        self.me = ax.scatter([], [], s=230, c=BLUE, edgecolors="white", linewidths=1, zorder=6)
        self.ring = ax.scatter(
            [], [], s=560, facecolors="none", edgecolors=INK, linewidths=3.2, zorder=7
        )
        self.ball = ax.scatter([], [], s=130, c=INK, edgecolors="white", linewidths=1.6, zorder=8)
        self.labels = [
            ax.text(
                0,
                0,
                "",
                ha="center",
                va="bottom",
                fontsize=19,
                fontweight="bold",
                color=VERMILION,
                zorder=9,
                path_effects=halo,
            )
            for _ in scene.rivals
        ]
        # the right-hand panel: the live count, then the key
        x0 = 9.1
        self.count = _fig_text(fig, x0, 5.05, "", fontsize=54, fontweight="bold", color=VERMILION)
        _fig_text(fig, x0, 4.3, "defenders filled in\nby the model", fontsize=20, linespacing=1.15)
        rows = [
            (3.35, "filled", "Seen by the camera"),
            (2.6, "hollow", "Filled in by\nthe model"),
            (1.35, "me", "Receiver"),
            (0.85, "ball", "Ball"),
            (0.4, "mate", "Teammates"),
        ]
        for y, kind, words in rows:
            self._key(fig, x0, y, kind)
            _fig_text(fig, x0 + 0.5, y, words, fontsize=20, va="center", linespacing=1.15)
        _fig_text(
            fig, x0 + 0.5, 1.95, "number = seconds to\nthe nearest detection",
            fontsize=16, va="center", color=GREY, linespacing=1.15,
        )  # fmt: skip

    @staticmethod
    def _key(fig: Figure, x: float, y: float, kind: str) -> None:
        mx, my = x + 0.13, y
        if kind == "filled":
            _fig_marker(fig, mx, my, s=260, c=VERMILION, edgecolors="white", linewidths=1.5)
        elif kind == "hollow":
            _fig_marker(
                fig, mx, my + 0.28, s=260, facecolors="white", edgecolors=VERMILION, linewidths=3.2
            )
        elif kind == "me":
            _fig_marker(fig, mx, my, s=200, c=BLUE, edgecolors="white", linewidths=1)
            _fig_marker(fig, mx, my, s=470, facecolors="none", edgecolors=INK, linewidths=3.0)
        elif kind == "ball":
            _fig_marker(fig, mx, my, s=120, c=INK, edgecolors="white", linewidths=1.4)
        else:
            _fig_marker(fig, mx, my, s=70, c=BLUE, edgecolors="white", linewidths=1)

    def draw(self, i: int) -> NDArray[np.uint8]:
        s = self.scene
        seen = s.rival_detected[i]
        self.filled.set_offsets(s.rival_xy[i][seen])
        self.hollow.set_offsets(s.rival_xy[i][~seen])
        mates = ~np.isnan(s.mate_xy[i][:, 0])
        self.mates_filled.set_offsets(s.mate_xy[i][mates & s.mate_detected[i]])
        self.mates_hollow.set_offsets(s.mate_xy[i][mates & ~s.mate_detected[i]])
        self.me.set_offsets(s.me[i : i + 1])
        self.ring.set_offsets(s.me[i : i + 1])
        self.ball.set_offsets(s.ball[i : i + 1])
        for j, label in enumerate(self.labels):
            label.set_visible(not bool(seen[j]))
            if not seen[j]:
                x, y = s.rival_xy[i, j]
                label.set_position((x, y + 2.3))
                label.set_text(f"{s.rival_gap[i, j] / HZ:.1f} s")
        k = len(s.rivals)
        self.count.set_text(f"{int((~seen).sum())} of {k}")
        rel = (int(s.frame[i]) - int(s.frame[s.key])) / HZ
        self.clock.set_text(f"{rel:+.1f} s" + ("   RECEPTION" if i == s.key else ""))
        canvas = cast("Any", self.canvas)  # matplotlib's Agg canvas is untyped
        canvas.draw()
        return np.ascontiguousarray(np.asarray(canvas.buffer_rgba())[:, :, :3])


def _frames(scene: Scene) -> Iterator[NDArray[np.uint8]]:
    """The RGB frames of the clip, drawn in the default style so no user setting moves a pixel."""
    with matplotlib.style.context("default"), matplotlib.rc_context(cast("Any", RC)):
        painter = _Painter(scene)
        for i in range(len(scene.frame)):
            yield painter.draw(i)


# --- the sidecar, build, check ---------------------------------------------------------------


def _canonical(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _document(scene: Scene, frames_sha256: str, still_sha256: str) -> dict[str, Any]:
    n, key = len(scene.frame), scene.key
    out = ~scene.rival_detected
    gaps = np.where(out, scene.rival_gap, 0)
    longest = int(gaps[key].max())
    return {
        "about": (
            "Every number drawn in the clip of the video. gap_len is in frames at 10 Hz; the "
            "label of a hollow marker is gap_len / 10, one decimal, in seconds; the counter is "
            "defenders_extrapolated of n_defenders; the clock is (frame - key_frame) / 10."
        ),
        "ball": {
            "detected": scene.ball_detected.tolist(),
            "gap_len": scene.ball_gap.tolist(),
        },
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
        "n_frames": n,
        "pixels": {
            "frames_sha256": frames_sha256,
            "height": HEIGHT,
            "still_sha256": still_sha256,
            "width": WIDTH,
        },
        "reception": {
            "event_subtype": scene.subtype,
            "frame": int(scene.frame[key]),
            "period": scene.period,
            "receiver_id": scene.receiver,
            "team_id": scene.team,
        },
        "receiver": {
            "detected": scene.me_detected.tolist(),
            "gap_len": scene.me_gap.tolist(),
        },
        "rule": describe(scene.rule),
        "video": {"codec": "H.264", "fps": FPS, "frames": n, "seconds": n / FPS},
    }


def build(match: MatchData, rule: Rule = DEFAULT_RULE) -> Built:
    """Choose the reception, draw every frame, and return the sidecar, the still and the hashes."""
    scene = choose(match, rule)
    digest = hashlib.sha256()
    still: NDArray[np.uint8] | None = None
    count = 0
    for i, frame in enumerate(_frames(scene)):
        digest.update(frame.tobytes())
        if i == scene.key:
            still = frame
        count += 1
    if still is None:
        raise NoReception("the window has no key frame")
    document = _document(scene, digest.hexdigest(), hashlib.sha256(still.tobytes()).hexdigest())
    buffer = io.BytesIO()
    matplotlib.image.imsave(buffer, still, format="png")
    return Built(_canonical(document), buffer.getvalue(), still, digest.hexdigest(), count, scene)


def ffmpeg() -> str | None:
    """The path of ``ffmpeg`` if it is installed."""
    return shutil.which("ffmpeg")


def encode_mp4(built: Built, path: Path) -> int:
    """Re-render the frames into ``ffmpeg`` (H.264, yuv420p) and return the size of ``path``.

    The comment of the file holds the hash of the raw pixels, so a check can tie the video to a
    render without decoding it. Raises :class:`FileNotFoundError` without ``ffmpeg``.
    """
    exe = ffmpeg()
    if exe is None:
        raise FileNotFoundError("ffmpeg is not on PATH: the video cannot be encoded")
    command = [
        exe, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "veryslow", "-crf", "27", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-fflags", "+bitexact", "-flags:v", "+bitexact",
        "-map_metadata", "-1", "-metadata", f"comment={MP4_TAG}{built.frames_sha256}",
        str(path),
    ]  # fmt: skip
    with subprocess.Popen(command, stdin=subprocess.PIPE) as process:
        assert process.stdin is not None
        for frame in _frames(built.scene):
            process.stdin.write(frame.tobytes())
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("ffmpeg failed")
    return path.stat().st_size


def _first_difference(was: bytes, now: bytes) -> int:
    old, new = was.splitlines(), now.splitlines()
    pairs = enumerate(zip(old, new, strict=False), start=1)
    return next((i for i, (a, b) in pairs if a != b), min(len(old), len(new)) + 1)


def check(
    built: Built, sidecar: bytes | None, still: bytes | None, video: bytes | None
) -> CheckResult:
    """Compare the committed files with the recomputation.

    The sidecar byte for byte (it holds the hash of the pixels of every frame); the still by its
    decoded pixels; the video by the hash its comment carries (the pixels were hashed in the
    recomputation, the MP4 bytes depend on the encoder and are not compared).
    """
    problems = []
    if sidecar is None:
        problems.append("clip.json: missing")
    elif sidecar != built.sidecar:
        line = _first_difference(sidecar, built.sidecar)
        problems.append(f"clip.json: differs from the recomputation (first at line {line})")
    if still is None:
        problems.append("clip_still.png: missing")
    else:
        pixels = np.rint(matplotlib.image.imread(io.BytesIO(still), format="png")[:, :, :3] * 255)
        if pixels.shape != built.still_pixels.shape or (pixels != built.still_pixels).any():
            problems.append("clip_still.png: its pixels differ from the key frame drawn again")
    if video is None:
        problems.append("clip.mp4: missing")
    elif f"{MP4_TAG}{built.frames_sha256}".encode() not in video:
        problems.append("clip.mp4: does not carry the hash of the frames drawn again")
    return CheckResult(
        not problems, problems, built.n_frames, None if video is None else len(video)
    )
