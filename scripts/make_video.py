"""The one-minute video of the entry: the script's shots, the clip, the figures and a voice (J7).

    uv run python scripts/make_video.py                                   # preview, no audio
    uv run --with faster-whisper python scripts/make_video.py --voice memo.m4a   # the submission

One shot per row of ``docs/video_script.md``, whose Sentence column is the caption burned in (the
transcript is never shown). The preview plays each shot at the planned window of the table. With
``--voice`` (a phone memo: m4a, mp3, wav, ogg or opus) the recording is transcribed with word
timestamps by an open-source local model (faster-whisper, pulled in with ``--with``), the eleven
sentences are aligned to the words heard (tolerant to a misread word, a filler and a pause; a
sentence that is not heard stops the build and is named), every shot is retimed to start when its
sentence starts, the voice is trimmed to its words, normalised to -16 LUFS (EBU R128, two passes)
and muxed. The build fails if the video would exceed 60 s; ``--speed-up`` allows up to 5 % of
atempo, off by default. Output: 1920x1080, 30 fps, H.264 + AAC, yuv420p, faststart.

What is on screen comes from the repository and nothing else: ``reports/clip/clip.mp4`` and its
still, the panels of figure 1 drawn again by ``scripts/video_panels.py`` from the figure's
sidecar at the stage's size in large type (the committed SVGs are not touched), and six
typographic cards (rows 1, 3, 5, 6, 10 and 11) whose words are the script's plus the repository
URL, the licence, the author, the data's name and, on row 3, the README's call to
``sensitivity`` with the V0 and V1 of the clip's match as ``reports/camera/camera.json`` holds
them (``match.rows``). The look is a dark theme in two Google
Fonts, Chakra Petch for headings, labels and cards and Roboto for the captions, fetched once into
``build/`` from pinned commits and checked by hash; no logo and no image but the repository's own.
Everything is written under ``build/video``.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib
import json
import math
import re
import shutil
import subprocess
import sys
import urllib.request
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
vsc: Any = importlib.import_module("video_script_check")
panels: Any = importlib.import_module("video_panels")

SCRIPT = Path("docs") / "video_script.md"
SIDECARS = Path("reports") / "figures"
CLIP = Path("reports") / "clip" / "clip.mp4"
STILL = Path("reports") / "clip" / "clip_still.png"
BUILD = Path("build") / "video"
# The faces, fetched once into build/fonts (never committed) from pinned commits of their
# repositories: Chakra Petch (OFL) for headings, labels and cards, Roboto (Apache 2.0) for the
# captions. Each file is checked against its sha256 before use.
GOOGLE_FONTS = (
    "https://raw.githubusercontent.com/google/fonts/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0"
)
ROBOTO = (
    "https://raw.githubusercontent.com/googlefonts/roboto/38062f4b4a0be4346d07a928408da21602545e9e"
)
FONTS = {
    "heading": (
        f"{GOOGLE_FONTS}/ofl/chakrapetch/ChakraPetch-Bold.ttf",
        "65fbf76d95651697275e19db4d717c0e95a789ddd3476478b05292104db278a0",
    ),
    "label": (
        f"{GOOGLE_FONTS}/ofl/chakrapetch/ChakraPetch-Regular.ttf",
        "98fcd638baa5c81ff0316b7538ce330ee3b23b1302726de3526d5933a8ecf986",
    ),
    "body": (
        f"{ROBOTO}/src/hinted/Roboto-Regular.ttf",
        "56a45233d29f11b4dfb86d248e921939d115778f87325e7ae8cc108383d6664d",
    ),
}


# The code card's face: DejaVu Sans Mono as the pinned matplotlib ships it, nothing fetched.
MONO = Path(panels.matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSansMono.ttf"


def _rgb(colour: str) -> tuple[int, int, int]:
    return int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)


WIDTH, HEIGHT, FPS = 1920, 1080, 30
STAGE = (200, 24, 1720, 879)  # left, top, right, bottom: the clip, the figures and the cards
CAPTION_SIZE, CAPTION_WIDTH, CAPTION_BOTTOM, CAPTION_LEADING = 48, 1500, 1024, 60
BG, BORDER, GREEN = _rgb(panels.BG), _rgb(panels.BORDER), _rgb(panels.GREEN)  # the panels' theme
INK, GREY, FAINT = _rgb(panels.TEXT), _rgb(panels.MUTED), _rgb(panels.FAINT)
MARK_EDGE = (*GREEN, 240)
CLIP_RADIUS = 24  # the clip keeps its light pitch, as a card with rounded corners and a border
CARD_STYLE = {  # style: face, size in px, colour
    "title": ("heading", 84, INK),
    "url": ("heading", 56, GREEN),
    "plain": ("label", 60, INK),
    "small": ("label", 40, GREY),
    "faint": ("label", 36, FAINT),
    "code": ("mono", 34, INK),
    "codehl": ("mono", 34, GREEN),
    "codedim": ("mono", 34, GREY),
}
# The panels are drawn at the stage's size (100 px per inch) and rendered at 150, never upscaled.
PANEL_DPI = 150
FULL = (0.0, 0.0, *panels.SIZE)  # a whole panel, and the same inset by 3 %: a slow zoom in
INSET = (0.03 * panels.SIZE[0], 0.03 * panels.SIZE[1], 0.97 * panels.SIZE[0], 0.97 * panels.SIZE[1])
CLIP_FPS, CLIP_FRAMES = 10, 100
LANCZOS = Image.Resampling.LANCZOS  # sharp at 1.19x for the clip; the figures only shrink
FADE, MOVE, MARK_IN = 0.25, 0.6, 0.35  # seconds: cross-fade, camera glide, highlight fade-in
LEAD, PAD, TAIL = 0.3, 0.4, 1.2  # seconds kept before the first word, after the last, then held
LIMIT = 60.0
MAX_SPEED_UP = 1.05
MODEL = "small.en"
SILENCE = 1.0  # seconds of silence padded around the recording before it is transcribed
LOUDNESS = "loudnorm=I=-16:TP=-1.5:LRA=11"

Box = tuple[float, float, float, float]  # left, top, right, bottom


@dataclass(frozen=True)
class Window:
    """A rectangle in the data coordinates of a named axes of a panel, padded outwards in inches.

    Resolved to a ``Box`` once the panel is drawn, so a crop sits on whole rows of the data and
    never cuts a marker.
    """

    axes: str
    x: tuple[float, float]
    y: tuple[float, float]
    pad: Box = (0.0, 0.0, 0.0, 0.0)  # left, top, right, bottom


@dataclass(frozen=True)
class Scene:
    """What a row shows: a source, how the shot enters, where the camera looks and what it marks.

    Boxes are inches of the panel from its top left corner, or a ``Window`` of its data. ``box`` is
    where the shot ends; it starts ``zoom`` times wider (or at ``start``) and closes in slowly.
    ``mark`` is the element the sentence talks about. ``enter`` is ``fade`` (cross-fade), ``move``
    (the camera glides over the same panel) or ``cut``. Clip shots play from ``clip_from`` and
    freeze at ``clip_stop``; card shots are ``card`` lines of (style, text).
    """

    source: str
    enter: str = "fade"
    box: Box | Window | None = None
    start: Box | None = None
    zoom: float = 1.0
    mark: Box | Window | None = None
    clip_from: float = 0.0
    clip_stop: float | None = None
    card: tuple[tuple[str, str], ...] = ()


# The panels are those of scripts/video_panels.py.
STORYBOARD: dict[int, Scene] = {
    1: Scene(
        "card",
        card=(
            ("plain", "Your block length from broadcast tracking"),
            ("title", "may describe the camera,"),
            ("title", "not your team."),
        ),
    ),
    2: Scene("clip", enter="cut", clip_from=0.0, clip_stop=3.0),
    3: Scene(
        "card",
        card=(
            ("plain", "The tag: block length, match 1874553"),
            ("small", "its 2 players are the two ends of the block"),
            ("codedim", ">>> tagged = sensitivity(metric, long_table(frames), units)[match_id]"),
            ("code", ">>> tagged.v0.n, round(tagged.v0.mean, 2)  # every phase             "),
            ("codehl", "(405, 51.95)                                                         "),
            ("code", ">>> tagged.v1.n, round(tagged.v1.mean, 2)  # both ends seen          "),
            ("codehl", "(17, 21.83)                                                          "),
        ),
    ),
    4: Scene("panel_a", box=INSET, start=FULL),
    5: Scene(
        "card",
        card=(
            ("plain", "Fill check: hide seen players, refill them"),
            ("title", "line depth: about 1 metre off"),
        ),
    ),
    6: Scene(
        "card",
        card=(
            ("plain", "The bigger problem: the back four or block"),
            ("title", "are fully seen"),
            ("title", "mostly near the ball."),
        ),
    ),
    7: Scene("line_height", box=INSET, start=FULL),
    8: Scene("block_length", box=INSET, start=FULL),
    9: Scene("pressure_rival", box=INSET, start=FULL),
    10: Scene(
        "card",
        card=(
            ("plain", "Block length is mostly the camera's choice;"),
            ("plain", "line depth follows."),
            ("title", "report both with their tag."),
            (
                "small",
                "Pressure and nearest rival survive. Tagged: 7 Defensive Positioning metrics",
            ),
        ),
    ),
    11: Scene(
        "card",
        card=(
            ("plain", "Clone it, run one match, tag your metrics"),
            ("url", "github.com/javiersr1996/ac2-football"),
            ("small", "Code and protocol under MIT"),
            ("small", "Presented by Javier Sánchez Rueda"),
            ("faint", "Data: SkillCorner open data, A-League 2024/25"),
        ),
    ),
}


# --- the script table and the shots --------------------------------------------------------------


@dataclass(frozen=True)
class Row:
    number: int
    start: float  # planned seconds
    end: float
    shot: str
    sentence: str


TIME = re.compile(r"^(\d+):(\d\d) to (\d+):(\d\d)$")


def rows_of(text: str) -> list[Row]:
    """The rows of the script table: number, planned window, shot and sentence."""
    header, cells = vsc.table(text)
    wanted = ("#", "Time", "Shot", "Sentence")
    if any(column not in header for column in wanted):
        raise ValueError(f"no table with the columns {', '.join(wanted)}")
    at = {column: header.index(column) for column in wanted}
    rows = []
    for i, row in enumerate(cells, 1):
        if len(row) != len(header):
            raise ValueError(f"row {i}: {len(row)} cells, the header has {len(header)}")
        m = TIME.match(row[at["Time"]])
        if m is None:
            raise ValueError(f"row {i}: time {row[at['Time']]!r} is not 'm:ss to m:ss'")
        a, b, c, d = (int(g) for g in m.groups())
        rows.append(
            Row(int(row[at["#"]]), a * 60 + b, c * 60 + d, row[at["Shot"]], row[at["Sentence"]])
        )
    for i, (one, two) in enumerate(zip(rows, rows[1:], strict=False), 1):
        if one.end != two.start:
            raise ValueError(
                f"row {i} ends at {one.end:.0f} s, row {i + 1} starts at {two.start:.0f} s"
            )
    if [r.number for r in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("the rows are not numbered 1 to n")
    return rows


@dataclass(frozen=True)
class Shot:
    row: Row
    scene: Scene
    start: float
    end: float

    @property
    def length(self) -> float:
        return self.end - self.start


def shots_of(
    rows: Sequence[Row],
    starts: Sequence[float],
    end: float,
    scenes: Mapping[int, Scene] = STORYBOARD,
) -> list[Shot]:
    """One shot per row, from its start to the next one's; the last ends at ``end``."""
    if [r.number for r in rows] != sorted(scenes):
        raise ValueError(f"the script has {len(rows)} rows, the storyboard {len(scenes)}")
    if len(starts) != len(rows) or any(a >= b for a, b in zip(starts, starts[1:], strict=False)):
        raise ValueError(f"the starts must be one per row and increasing: {starts}")
    ends = [*starts[1:], end]
    shots = [Shot(r, scenes[r.number], s, e) for r, s, e in zip(rows, starts, ends, strict=True)]
    for one, two in zip(shots, shots[1:], strict=False):
        if two.scene.enter == "move" and one.scene.source != two.scene.source:
            raise ValueError(f"row {two.row.number} moves the camera from another source")
    return shots


def planned(rows: Sequence[Row], scenes: Mapping[int, Scene] = STORYBOARD) -> list[Shot]:
    return shots_of(rows, [r.start for r in rows], rows[-1].end + TAIL, scenes)


def resolve(scenes: Mapping[int, Scene], drawn: Mapping[str, Any]) -> dict[int, Scene]:
    """The scenes with every ``Window`` turned into inches of its drawn panel."""
    out = {}
    for number, scene in scenes.items():
        changes = {}
        for field in ("box", "mark"):
            value = getattr(scene, field)
            if isinstance(value, Window):
                changes[field] = drawn[scene.source].window(value.axes, value.x, value.y, value.pad)
        out[number] = replace(scene, **changes) if changes else scene
    return out


# --- the voice: words heard, sentences found, the clock -------------------------------------------


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Span:
    """Where a sentence is in the recording, and how many of its words were heard."""

    start: float
    end: float
    heard: int
    words: int


class NotFound(ValueError):
    pass


class TooLong(ValueError):
    pass


ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen"
).split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
TOKEN = re.compile(r"[-−]?\d+(?:\.\d+)?|[a-zà-ÿ]+")


def _number_words(token: str) -> list[str]:
    """``-0.19`` as it is read: minus zero point one nine; ``37``: thirty seven."""
    out = ["minus"] if token[0] in "-−" else []
    whole, _, fraction = token.lstrip("-−").partition(".")
    n = int(whole)
    if n < 20:
        out.append(ONES[n])
    elif n < 100:
        out.append(TENS[n // 10])
        if n % 10:
            out.append(ONES[n % 10])
    else:
        out.extend(ONES[int(d)] for d in whole)
    if fraction:
        out.append("point")
        out.extend(ONES[int(d)] for d in fraction)
    return out


def tokens_of(text: str) -> list[str]:
    """The words compared: lower case, no punctuation, numerals as the words that read them."""
    out: list[str] = []
    for token in TOKEN.findall(text.lower().replace("'", "").replace("’", "")):
        out.extend(_number_words(token) if token[-1].isdigit() else [token])
    return out


EQUAL, SIMILAR, MISMATCH, EXTRA, MISSING = 3.0, 2.0, -1.0, -1.0, -1.5


def _score(a: str, b: str) -> float:
    if a == b:
        return EQUAL
    if min(len(a), len(b)) >= 4 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.7:
        return SIMILAR  # a misread or a variant spelling: metres, meters
    return MISMATCH


def align(words: Sequence[Word], sentences: Sequence[str]) -> list[Span]:
    """When each sentence is spoken: a global alignment of the script's words with the words heard.

    Fillers are extra words, skipped words are missing ones, a misread word is a similar one; the
    alignment is monotonic, so a sentence cannot borrow words from its neighbours. A sentence is
    found when at least half of its words were heard equal or similar.
    """
    script = [(k, token) for k, s in enumerate(sentences) for token in tokens_of(s)]
    heard = [(token, w) for w in words for token in tokens_of(w.text)]
    n, m = len(script), len(heard)
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        best[i][0] = i * MISSING
    for j in range(1, m + 1):
        best[0][j] = j * EXTRA
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best[i][j] = max(
                best[i - 1][j - 1] + _score(script[i - 1][1], heard[j - 1][0]),
                best[i - 1][j] + MISSING,
                best[i][j - 1] + EXTRA,
            )
    pairs: dict[int, tuple[int, float]] = {}  # script word -> (word heard, score)
    i, j = n, m
    while i > 0 and j > 0:
        score = _score(script[i - 1][1], heard[j - 1][0])
        if best[i][j] == best[i - 1][j - 1] + score:
            pairs[i - 1] = (j - 1, score)
            i, j = i - 1, j - 1
        elif best[i][j] == best[i - 1][j] + MISSING:
            i -= 1
        else:
            j -= 1
    spans = []
    for k, sentence in enumerate(sentences):
        mine = [i for i, (kk, _) in enumerate(script) if kk == k]
        found = [pairs[i] for i in mine if i in pairs]
        good = sum(1 for _, score in found if score >= SIMILAR)
        if good < max(1, math.ceil(len(mine) / 2)):
            raise NotFound(
                f"sentence {k + 1} not found in the recording ({good} of {len(mine)} words "
                f"heard): {sentence!r}"
            )
        first, last = min(j for j, _ in found), max(j for j, _ in found)
        spans.append(Span(heard[first][1].start, heard[last][1].end, good, len(mine)))
    return spans


@dataclass(frozen=True)
class Timing:
    """The cut of the recording and its tempo; the video is the voice plus the final hold."""

    trim_start: float
    trim_end: float
    factor: float

    @property
    def voice(self) -> float:
        return (self.trim_end - self.trim_start) / self.factor

    @property
    def total(self) -> float:
        return self.voice + TAIL

    def clock(self, second: float) -> float:
        """A second of the recording as a second of the video."""
        return (second - self.trim_start) / self.factor


def fit(
    spans: Sequence[Span], sentences: Sequence[str], speed_up: bool = False, limit: float = LIMIT
) -> Timing:
    """Trim the voice to its words and check the minute; ``speed_up`` allows up to 5 % of tempo."""
    trim_start, trim_end = max(0.0, spans[0].start - LEAD), spans[-1].end + PAD
    voice = trim_end - trim_start
    factor = 1.0
    if speed_up and voice + TAIL > limit:
        factor = min(MAX_SPEED_UP, voice / (limit - TAIL))
    timing = Timing(trim_start, trim_end, factor)
    if timing.total > limit + 1e-9:
        longest = sorted(range(len(spans)), key=lambda k: spans[k].start - spans[k].end)[:3]
        lines = [
            f"  {k + 1}: {spans[k].end - spans[k].start:.1f} s  {sentences[k]}" for k in longest
        ]
        if speed_up:
            hint = f" even at {factor:.3f} of tempo"
        else:
            fastest = voice / MAX_SPEED_UP + TAIL
            hint = f"; --speed-up (at most {MAX_SPEED_UP:.2f}) would give {fastest:.1f} s"
        raise TooLong(
            f"the voice lasts {voice:.1f} s after trimming; with the {TAIL} s hold at the end the "
            f"video would last {timing.total:.1f} s, over {limit:.0f} s{hint}. Longest sentences:\n"
            + "\n".join(lines)
        )
    return timing


def voiced(
    rows: Sequence[Row],
    spans: Sequence[Span],
    timing: Timing,
    scenes: Mapping[int, Scene] = STORYBOARD,
) -> list[Shot]:
    """The shots retimed: the first at zero, each other one when its sentence starts."""
    starts = [0.0, *(timing.clock(s.start) for s in spans[1:])]
    return shots_of(rows, starts, timing.total, scenes)


# --- the recording: transcribed, cut, normalised -------------------------------------------------


def transcribe(voice: Path, model_name: str) -> list[Word]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit(
            "faster-whisper is not installed: run with "
            "`uv run --with faster-whisper python scripts/make_video.py ...`"
        ) from None
    # Decoded by ffmpeg (any format a phone writes), not by the model's own reader.
    decoded = run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(voice)]
        + ["-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        text=False,
    ).stdout
    # A second of silence each side, so a last word at the very end is heard; beam search at
    # temperature zero only, so the same recording always gives the same words and times.
    pad = np.zeros(int(SILENCE * 16000), dtype=np.float32)
    audio = np.concatenate([pad, np.frombuffer(decoded, dtype=np.float32), pad])
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        audio,
        language="en",
        word_timestamps=True,
        beam_size=5,
        temperature=0.0,
        condition_on_previous_text=False,
    )
    return [
        Word(w.word.strip(), max(0.0, float(w.start) - SILENCE), max(0.0, float(w.end) - SILENCE))
        for segment in segments
        for w in segment.words or []
    ]


def run(args: Sequence[str], text: bool = True) -> subprocess.CompletedProcess[Any]:
    """``args`` with its output captured; a non-zero exit raises with the tool's own stderr."""
    proc = subprocess.run(
        list(args),
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
    )
    if proc.returncode != 0:
        stderr = proc.stderr if text else proc.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"{args[0]} failed with {proc.returncode}:\n{stderr.strip()}")
    return proc


def prepare_voice(voice: Path, timing: Timing, out: Path) -> None:
    """The recording cut to its words, at tempo, at -16 LUFS in two passes, padded to the video."""
    cut = f"atrim=start={timing.trim_start:.3f}:end={timing.trim_end:.3f},asetpts=PTS-STARTPTS"
    if timing.factor != 1.0:
        cut += f",atempo={timing.factor:.4f}"
    ffmpeg = ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-i", str(voice)]
    measured = run(
        [*ffmpeg, "-af", f"{cut},{LOUDNESS}:print_format=json", "-f", "null", "-"]
    ).stderr
    stats = json.loads(measured[measured.rindex("{") : measured.rindex("}") + 1])
    linear = (
        f"{LOUDNESS}:measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
        f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
        f":offset={stats['target_offset']}:linear=true"
    )
    run(
        [
            *ffmpeg,
            "-af",
            f"{cut},{linear},aresample=48000,apad=whole_dur={timing.total:.3f}",
            "-ar",
            "48000",
            "-ac",
            "1",
            str(out),
        ]
    )


# --- the pictures ---------------------------------------------------------------------------------


def fetch_fonts(build: Path) -> dict[str, Path]:
    """The faces of ``FONTS`` under ``build/fonts``, downloaded once and checked by sha256, and
    ``MONO`` for the code card."""
    folder = build / "fonts"
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, (url, digest) in FONTS.items():
        path = folder / url.rsplit("/", 1)[1]
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            print(f"fetching {path.name} from {url}")
            try:
                with urllib.request.urlopen(url, timeout=60) as response:
                    data = response.read()
            except OSError as exc:
                raise SystemExit(f"could not fetch the font {path.name} from {url}: {exc}") from exc
            if hashlib.sha256(data).hexdigest() != digest:
                raise SystemExit(f"{path.name} from {url} does not match its sha256 in FONTS")
            path.write_bytes(data)
        out[name] = path
    out["mono"] = MONO
    return out


def render_panels(
    root: Path, build: Path, fonts: Mapping[str, Path]
) -> tuple[dict[str, tuple[Image.Image, int]], dict[int, Scene]]:
    """The panels of the video as PNG, each with its pixels per inch, and the scenes in inches."""
    drawn = panels.draw_all(root / SIDECARS, fonts)
    out = {}
    for name, panel in drawn.items():
        dpi = PANEL_DPI
        path = build / f"{name}.png"
        panel.save(path, dpi)
        out[name] = (Image.open(path).convert("RGB"), dpi)
    return out, resolve(STORYBOARD, drawn)


def extract_clip(root: Path, build: Path) -> Path:
    folder = build / "clip"
    folder.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-nostdin",
            "-loglevel",
            "error",
            "-i",
            str(root / CLIP),
            str(folder / "%03d.png"),
        ]
    )
    if len(list(folder.glob("*.png"))) != CLIP_FRAMES:
        raise RuntimeError(f"{root / CLIP}: expected {CLIP_FRAMES} frames")
    return folder


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def wrap(text: str, face: ImageFont.FreeTypeFont, width: int = CAPTION_WIDTH) -> list[str]:
    """The caption in at most two lines of ``width`` pixels."""
    lines: list[str] = []
    line = ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if not line or face.getlength(trial) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    lines.append(line)
    if len(lines) > 2:
        raise ValueError(f"caption needs {len(lines)} lines: {text!r}")
    return lines


def _smooth(p: float) -> float:
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


def _lerp(a: Box, b: Box, p: float) -> Box:
    left, top, right, bottom = (x + (y - x) * p for x, y in zip(a, b, strict=True))
    return left, top, right, bottom


def _grow(box: Box, zoom: float) -> Box:
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    w, h = (box[2] - box[0]) * zoom / 2, (box[3] - box[1]) * zoom / 2
    return cx - w, cy - h, cx + w, cy + h


def camera(scene: Scene, second: float, length: float) -> Box:
    """Where the camera is ``second`` into a shot of ``length``: from the start box to ``box``."""
    assert isinstance(scene.box, tuple), "a scene is resolved before it is drawn"
    start = scene.start or _grow(scene.box, scene.zoom)
    return _lerp(start, scene.box, min(1.0, second / length) if length > 0 else 1.0)


class Pictures:
    """The sources, loaded once, and the stage of a shot at a second (a full frame, no caption)."""

    def __init__(self, root: Path, build: Path) -> None:
        self.fonts = fetch_fonts(build)
        self.fig, self.scenes = render_panels(root, build, self.fonts)
        self.clip = extract_clip(root, build)
        self.still = Image.open(root / STILL).convert("RGB")
        self.size = (STAGE[2] - STAGE[0], STAGE[3] - STAGE[1])
        self._clip_mask = Image.new("L", self.size, 0)
        ImageDraw.Draw(self._clip_mask).rounded_rectangle(
            (0, 0, self.size[0] - 1, self.size[1] - 1), radius=CLIP_RADIUS, fill=255
        )
        self._clip_frame: tuple[int, Image.Image] | None = None
        self._cards: dict[int, Image.Image] = {}
        self._captions: dict[str, Image.Image] = {}

    def face(self, name: str, size: int) -> ImageFont.FreeTypeFont:
        return font(self.fonts[name], size)

    def stage(
        self, shot: Shot, second: float, box: Box | None = None, mark_alpha: float | None = None
    ) -> Image.Image:
        scene = shot.scene
        if scene.source == "card":
            return self._card(shot)
        canvas = Image.new("RGB", (WIDTH, HEIGHT), BG)
        if scene.source == "clip":
            canvas.paste(self._clip(scene, second), STAGE[:2], self._clip_mask)
            ImageDraw.Draw(canvas).rounded_rectangle(
                (STAGE[0] - 2, STAGE[1] - 2, STAGE[2] + 1, STAGE[3] + 1),
                radius=CLIP_RADIUS + 2,
                outline=BORDER,
                width=3,
            )
            return canvas
        if box is None:
            box = camera(scene, second, shot.length)
        if mark_alpha is None:
            mark_alpha = _smooth((second - (MOVE if scene.enter == "move" else 0.0)) / MARK_IN)
        assert not isinstance(scene.mark, Window), "a scene is resolved before it is drawn"
        image, dpi = self.fig[scene.source]
        self._figure(canvas, image, dpi, box, scene.mark, mark_alpha)
        return canvas

    def _clip(self, scene: Scene, second: float) -> Image.Image:
        shown = scene.clip_from + second
        if scene.clip_stop is not None and shown >= scene.clip_stop:
            index = -1  # frozen: the committed still of the reception
        else:
            index = min(int(shown * CLIP_FPS), CLIP_FRAMES - 1)
        if self._clip_frame is None or self._clip_frame[0] != index:
            source = self.still if index < 0 else Image.open(self.clip / f"{index + 1:03d}.png")
            self._clip_frame = (index, source.convert("RGB").resize(self.size, LANCZOS))
        return self._clip_frame[1]

    def _figure(
        self,
        canvas: Image.Image,
        image: Image.Image,
        dpi: int,
        box: Box,
        mark: Box | None,
        alpha: float,
    ) -> None:
        px = [v * dpi for v in box]
        w, h = px[2] - px[0], px[3] - px[1]
        dx = max(0.0, -px[0]) + min(0.0, image.width - px[2])  # shifted back inside the figure
        dy = max(0.0, -px[1]) + min(0.0, image.height - px[3])
        px = [px[0] + dx, px[1] + dy, px[2] + dx, px[3] + dy]
        px = [max(0.0, px[0]), max(0.0, px[1]), min(image.width, px[2]), min(image.height, px[3])]
        w, h = px[2] - px[0], px[3] - px[1]
        scale = min(self.size[0] / w, self.size[1] / h)
        dw, dh = max(1, round(w * scale)), max(1, round(h * scale))
        region = image.resize((dw, dh), LANCZOS, box=(px[0], px[1], px[2], px[3]))
        if mark is not None and alpha > 0:
            overlay = Image.new("RGBA", (dw, dh), (0, 0, 0, 0))
            left, top, right, bottom = (
                (mark[0] * dpi - px[0]) * scale,
                (mark[1] * dpi - px[1]) * scale,
                (mark[2] * dpi - px[0]) * scale,
                (mark[3] * dpi - px[1]) * scale,
            )
            edge = (*MARK_EDGE[:3], round(MARK_EDGE[3] * alpha))
            ImageDraw.Draw(overlay).rounded_rectangle(
                (left, top, right, bottom), radius=14, outline=edge, width=5
            )
            region = Image.alpha_composite(region.convert("RGBA"), overlay).convert("RGB")
        canvas.paste(
            region, (STAGE[0] + (self.size[0] - dw) // 2, STAGE[1] + (self.size[1] - dh) // 2)
        )

    def _card(self, shot: Shot) -> Image.Image:
        if shot.row.number not in self._cards:
            canvas = Image.new("RGB", (WIDTH, HEIGHT), BG)
            draw = ImageDraw.Draw(canvas)
            faces = [
                (self.face(CARD_STYLE[style][0], CARD_STYLE[style][1]), text, style)
                for style, text in shot.scene.card
            ]
            heights = [
                round(size * 1.35) for _, _, style in faces for size in [CARD_STYLE[style][1]]
            ]
            total = sum(heights) + 36  # the accent bar and its gap
            y = STAGE[1] + (self.size[1] - total) // 2
            draw.rectangle((WIDTH // 2 - 60, y, WIDTH // 2 + 60, y + 8), fill=GREEN)
            y += 36
            for (face, text, style), height in zip(faces, heights, strict=True):
                width = face.getlength(text)
                if width > self.size[0]:
                    raise ValueError(f"card line wider than the stage: {text!r}")
                draw.text(((WIDTH - width) / 2, y), text, font=face, fill=CARD_STYLE[style][2])
                y += height
            self._cards[shot.row.number] = canvas
        return self._cards[shot.row.number]

    def caption(self, text: str) -> Image.Image:
        if text not in self._captions:
            face = self.face("body", CAPTION_SIZE)
            lines = wrap(text, face)
            image = Image.new("RGBA", (WIDTH, CAPTION_LEADING * len(lines)), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            for i, line in enumerate(lines):
                draw.text(
                    ((WIDTH - face.getlength(line)) / 2, i * CAPTION_LEADING),
                    line,
                    font=face,
                    fill=INK,
                )
            self._captions[text] = image
        return self._captions[text]


def compose(second: float, shots: Sequence[Shot], pictures: Pictures) -> Image.Image:
    """The frame at ``second``: the shot's stage, its entry from the previous one, its caption."""
    k = max(i for i, s in enumerate(shots) if s.start <= second + 1e-9)
    shot, u = shots[k], second - shots[k].start
    prev = shots[k - 1] if k else None
    if prev is not None and shot.scene.enter == "move" and u < MOVE:
        box = _lerp(
            camera(prev.scene, second - prev.start, prev.length),
            camera(shot.scene, u, shot.length),
            _smooth(u / MOVE),
        )
        canvas = pictures.stage(shot, u, box=box, mark_alpha=0.0)
    else:
        canvas = pictures.stage(shot, u)
        if prev is not None and shot.scene.enter == "fade" and u < FADE:
            canvas = Image.blend(pictures.stage(prev, second - prev.start), canvas, u / FADE)
    if shot.scene.source != "card":
        caption = pictures.caption(shot.row.sentence)
        canvas.paste(caption, (0, CAPTION_BOTTOM - caption.height), caption)
    return canvas


def frames(shots: Sequence[Shot], pictures: Pictures) -> Iterator[bytes]:
    for n in range(round(shots[-1].end * FPS)):
        yield compose(n / FPS, shots, pictures).tobytes()


def encode(stream: Iterator[bytes], out: Path, audio: Path | None) -> None:
    """H.264 (yuv420p, BT.709, faststart) from raw frames on a pipe, with the voice as AAC."""
    command = [
        "ffmpeg", "-y", "-nostdin", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS),
        "-i", "pipe:0",
    ]  # fmt: skip
    if audio is not None:
        command += ["-i", str(audio)]
    command += [
        "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-movflags", "+faststart",
    ]  # fmt: skip
    command += ["-c:a", "aac", "-b:a", "160k"] if audio is not None else ["-an"]
    with subprocess.Popen([*command, str(out)], stdin=subprocess.PIPE) as proc:
        assert proc.stdin is not None
        for frame in stream:
            proc.stdin.write(frame)
        proc.stdin.close()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed with {proc.returncode}")


def probe(path: Path) -> tuple[float, int, int, bool]:
    """Duration, width, height and whether there is an audio stream."""
    data = json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,width,height",
                "-of",
                "json",
                str(path),
            ]  # fmt: skip
        ).stdout
    )
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    audio = any(s["codec_type"] == "audio" for s in data["streams"])
    return float(data["format"]["duration"]), int(video["width"]), int(video["height"]), audio


# --- the command ----------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--voice", type=Path, help="the recording (m4a, mp3, wav, ogg or opus)")
    parser.add_argument(
        "--words", type=Path, help="words.json of an earlier run, instead of transcribing"
    )
    parser.add_argument("--model", default=MODEL, help=f"faster-whisper model (default {MODEL})")
    parser.add_argument(
        "--speed-up", action="store_true", help="allow up to 5 %% of atempo to fit 60 s"
    )
    parser.add_argument(
        "--out", type=Path, help="the MP4 (default build/video/preview.mp4 or video.mp4)"
    )
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            print(f"{tool} not found on PATH", file=sys.stderr)
            return 2
    # Checked before a font is fetched or a panel drawn: with --words the file is first read by
    # ffmpeg at the very end, and without it the missing model would be blamed instead.
    if args.voice is not None and not args.voice.is_file():
        print(f"the recording {args.voice} does not exist", file=sys.stderr)
        return 2
    root: Path = args.root
    build = root / BUILD
    build.mkdir(parents=True, exist_ok=True)
    rows = rows_of((root / SCRIPT).read_text(encoding="utf-8"))
    sentences = [r.sentence for r in rows]
    audio: Path | None = None
    rebuild = "uv run python scripts/make_video.py"
    pictures = Pictures(root, build)

    if args.voice is None:
        shots = planned(rows, pictures.scenes)
        out = args.out or build / "preview.mp4"
    else:
        if args.words is not None:
            words = [Word(**w) for w in json.loads(args.words.read_text(encoding="utf-8"))["words"]]
        else:
            print(f"transcribing {args.voice} with {args.model}")
            words = transcribe(args.voice, args.model)
            saved = build / "words.json"
            saved.write_text(
                json.dumps(
                    {
                        "voice": str(args.voice),
                        "model": args.model,
                        "words": [w.__dict__ for w in words],
                    },
                    indent=1,
                )
                + "\n",
                encoding="utf-8",
            )
            print(f"{len(words)} words heard, saved to {saved}")
        try:
            spans = align(words, sentences)
            timing = fit(spans, sentences, speed_up=args.speed_up)
        except (NotFound, TooLong) as exc:
            print(f"FAIL {exc}")
            return 1
        for k, (span, sentence) in enumerate(zip(spans, sentences, strict=True), 1):
            print(
                f"  {k:2d}  {timing.clock(span.start):5.2f} to {timing.clock(span.end):5.2f} s  "
                f"{span.heard}/{span.words} words  {sentence}"
            )
        tempo = f", at {timing.factor:.3f} of tempo" if timing.factor != 1.0 else ""
        print(f"voice: {timing.voice:.1f} s after trimming{tempo}; video: {timing.total:.1f} s")
        audio = build / "voice.wav"
        prepare_voice(args.voice, timing, audio)
        shots = voiced(rows, spans, timing, pictures.scenes)
        out = args.out or build / "video.mp4"
        rebuild = f"uv run --with faster-whisper python scripts/make_video.py --voice {args.voice}"
        if args.speed_up:
            rebuild += " --speed-up"

    print(f"rendering {round(shots[-1].end * FPS)} frames at {FPS} fps")
    encode(frames(shots, pictures), out, audio)
    seconds, width, height, has_audio = probe(out)
    print(f"wrote {out}: {seconds:.2f} s, {width}x{height}, {'with' if has_audio else 'no'} audio")
    print(f"rebuild: {rebuild}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
