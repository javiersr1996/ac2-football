"""The pure parts of ``scripts/make_video.py``, without ffmpeg, the figures or the speech model.

The aligner on a fake list of words heard, built from the committed script with made-up times,
then one change at a time: a misread word, a filler, a long pause, numerals read as words, a
missing sentence (named). The minute: the trim, the hold, ``--speed-up`` at 5 % at most. The shot
timeline from the script table, the storyboard against it, every caption in two lines, and the
teleprompter saying the script's sentences. Last, the command: a recording that does not exist
is refused before a font is fetched or a panel drawn, and a tool that fails is reported with its
own stderr (the one test here that runs ffmpeg, on a file that is not audio).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import matplotlib
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "make_video.py"

_spec = importlib.util.spec_from_file_location("make_video", SCRIPT)
assert _spec is not None and _spec.loader is not None
mv: ModuleType = importlib.util.module_from_spec(_spec)
sys.modules["make_video"] = mv
_spec.loader.exec_module(mv)

ROWS = mv.rows_of((ROOT / "docs" / "video_script.md").read_text(encoding="utf-8"))
SENTENCES = [r.sentence for r in ROWS]


def heard(
    sentences: list[str], pause: float = 0.5, pauses: dict[int, float] | None = None
) -> tuple[list[mv.Word], list[float]]:
    """Words at 0.3 s each with 0.05 s between them, ``pause`` between sentences (or ``pauses``
    before a sentence, from 1), and the second each sentence starts at."""
    words, starts, t = [], [], 0.4
    for k, sentence in enumerate(sentences, 1):
        t += (pauses or {}).get(k, pause) if k > 1 else 0.0
        starts.append(round(t, 3))
        for word in sentence.split():
            words.append(mv.Word(word, t, t + 0.3))
            t += 0.35
    return words, starts


def starts_of(spans: list[mv.Span]) -> list[float]:
    return [round(s.start, 3) for s in spans]


# --- the aligner ---------------------------------------------------------------------------------


def test_the_script_read_verbatim_is_found_where_it_is_spoken() -> None:
    words, starts = heard(SENTENCES)
    spans = mv.align(words, SENTENCES)
    assert starts_of(spans) == starts
    assert all(s.heard == s.words for s in spans)
    assert spans[0].end == pytest.approx(words[len(SENTENCES[0].split()) - 1].end)


def test_a_misread_word_a_filler_and_a_long_pause_do_not_move_the_starts() -> None:
    # "defenders" read as "defendants" in sentence 1, "metres" as "meters" in 6 and 7.
    spoken = [s.replace("defenders", "defendants").replace("metres", "meters") for s in SENTENCES]
    words, starts = heard(spoken)
    assert starts_of(mv.align(words, SENTENCES)) == starts
    # Fillers: "um" before sentence 4 and "you know" inside sentence 8.
    spoken = list(SENTENCES)
    spoken[3] = "um " + spoken[3]
    spoken[7] = spoken[7].replace("choice;", "choice; you know,")
    words, starts = heard(spoken)
    expected = list(starts)
    expected[3] += 0.35  # the sentence starts at its own first word, after the filler
    assert starts_of(mv.align(words, SENTENCES)) == [round(s, 3) for s in expected]
    # A 4 s pause before sentence 7 and a 2.5 s one before 11.
    words, starts = heard(SENTENCES, pauses={7: 4.0, 11: 2.5})
    assert starts_of(mv.align(words, SENTENCES)) == starts
    assert starts[6] - starts[5] > 4.0


def test_numerals_read_as_words_match_the_script() -> None:
    assert mv.tokens_of("filled in 7 of these 11 defenders.") == mv.tokens_of(
        "filled in seven of these eleven defenders"
    )
    assert (
        mv.tokens_of("-0.19 and 0.18")
        == "minus zero point one nine and zero point one eight".split()
    )
    assert mv.tokens_of("17 to 37 metres") == "seventeen to thirty seven metres".split()
    assert mv.tokens_of("SkillCorner's player-frames") == ["skillcorners", "player", "frames"]
    spoken = [
        s.replace("4 of these 11", "four of these eleven")
        .replace("filled in 7", "filled in seven")
        .replace("In 20", "In twenty")
        .replace("for 7", "for seven")
        .replace("about 1 metre", "about one metre")
        .replace("17 to 37", "seventeen to thirty-seven")
        .replace("7 to 14", "seven to fourteen")
        for s in SENTENCES
    ]
    assert not any(c.isdigit() for s in spoken for c in s)  # every numeral of the script is read
    words, starts = heard(spoken)
    spans = mv.align(words, SENTENCES)
    assert starts_of(spans) == starts
    assert all(s.heard == s.words for s in spans)


def test_a_skipped_word_is_tolerated_and_a_missing_sentence_is_named() -> None:
    spoken = list(SENTENCES)
    spoken[1] = spoken[1].replace("about half", "half")
    words, starts = heard(spoken)
    spans = mv.align(words, SENTENCES)
    assert starts_of(spans) == starts and spans[1].heard == spans[1].words - 1
    spoken = [s for k, s in enumerate(SENTENCES, 1) if k != 11]
    words, _ = heard(spoken)
    with pytest.raises(mv.NotFound) as caught:
        mv.align(words, SENTENCES)
    assert str(caught.value).startswith("sentence 11 not found in the recording")
    assert SENTENCES[10] in str(caught.value)


# --- the minute ----------------------------------------------------------------------------------


def spans_lasting(voice: float) -> list[mv.Span]:
    """Twelve spans whose trimmed voice (lead, pad included) lasts ``voice`` seconds; the 6th is
    the longest and the 12th the second longest."""
    each = (voice - mv.LEAD - mv.PAD - 11 * 0.5) / 12
    spans, t = [], 1.0
    for k in range(1, 13):
        length = each + (1.0 if k == 6 else 0.5 if k == 12 else -1.5 / 10)
        spans.append(mv.Span(t, t + length, 10, 10))
        t += length + 0.5
    return spans


def test_the_voice_is_trimmed_to_its_words_and_the_hold_added() -> None:
    spans = spans_lasting(55.0)
    timing = mv.fit(spans, SENTENCES)
    assert timing.trim_start == pytest.approx(spans[0].start - mv.LEAD)
    assert timing.trim_end == pytest.approx(spans[-1].end + mv.PAD)
    assert timing.factor == 1.0 and timing.voice == pytest.approx(55.0)
    assert timing.total == pytest.approx(55.0 + mv.TAIL)
    assert timing.clock(spans[0].start) == pytest.approx(mv.LEAD)
    # A recording that starts speaking at once cannot be trimmed before zero.
    early = [mv.Span(0.1, 3.0, 5, 5), *spans[1:]]
    assert mv.fit(early, SENTENCES).trim_start == 0.0


def test_sixty_seconds_pass_and_a_frame_more_fails_naming_the_longest() -> None:
    assert mv.fit(spans_lasting(60.0 - mv.TAIL), SENTENCES).total == pytest.approx(60.0)
    with pytest.raises(mv.TooLong) as caught:
        mv.fit(spans_lasting(60.0 - mv.TAIL + 0.1), SENTENCES)
    message = str(caught.value)
    assert "would last 60.1 s, over 60 s" in message and "--speed-up" in message
    lines = message.split("Longest sentences:\n")[1].splitlines()
    assert lines[0].startswith("  6:") and lines[1].startswith("  12:")
    assert SENTENCES[5] in lines[0]


def test_speed_up_is_off_by_default_and_gives_five_percent_at_most() -> None:
    spans = spans_lasting(60.0)  # 1.2 s over with the hold
    with pytest.raises(mv.TooLong):
        mv.fit(spans, SENTENCES)
    timing = mv.fit(spans, SENTENCES, speed_up=True)
    assert 1.0 < timing.factor <= mv.MAX_SPEED_UP
    assert timing.total == pytest.approx(60.0)
    assert timing.clock(timing.trim_end) == pytest.approx(timing.voice)
    # Under the limit the flag changes nothing; too far over, it is not enough and says so.
    assert mv.fit(spans_lasting(50.0), SENTENCES, speed_up=True).factor == 1.0
    with pytest.raises(mv.TooLong) as caught:
        mv.fit(spans_lasting(63.0), SENTENCES, speed_up=True)
    assert "even at 1.050 of tempo" in str(caught.value)


# --- the shots -----------------------------------------------------------------------------------


def test_the_committed_script_gives_twelve_planned_shots() -> None:
    assert [r.number for r in ROWS] == list(range(1, 13))
    shots = mv.planned(ROWS)
    assert [s.start for s in shots] == [0, 5, 10, 14, 18, 24, 30, 35, 41, 45, 50, 54]
    assert shots[-1].end == ROWS[-1].end + mv.TAIL <= 60.0
    assert all(s.end == t.start for s, t in zip(shots, shots[1:], strict=False))
    assert all(s.scene is mv.STORYBOARD[s.row.number] for s in shots)
    assert "4 of these 11" in shots[0].row.sentence


def test_the_shots_follow_the_voice() -> None:
    spans = spans_lasting(52.0)
    timing = mv.fit(spans, SENTENCES)
    shots = mv.voiced(ROWS, spans, timing)
    assert shots[0].start == 0.0
    assert [s.start for s in shots[1:]] == [pytest.approx(timing.clock(x.start)) for x in spans[1:]]
    assert shots[-1].end == pytest.approx(timing.total)


def test_a_broken_table_is_refused() -> None:
    text = (ROOT / "docs" / "video_script.md").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="row 3: time '0:10 - 0:14'"):
        mv.rows_of(text.replace("0:10 to 0:14", "0:10 - 0:14"))
    with pytest.raises(ValueError, match="row 2 ends at 10 s, row 3 starts at 11 s"):
        mv.rows_of(text.replace("| 0:10 to 0:14 |", "| 0:11 to 0:14 |"))
    with pytest.raises(ValueError, match="the storyboard"):
        mv.shots_of(ROWS[:-1], [r.start for r in ROWS[:-1]], 50.0)
    with pytest.raises(ValueError, match="increasing"):
        mv.shots_of(ROWS, [0, 6, 10, 14, 20, 23, 29, 33, 38, 42, 46, 46], 50.0)


def test_the_storyboard_is_consistent() -> None:
    """Every panel shot names a drawn panel; once resolved, every box lies inside the panel, every
    start box holds its end box and every mark lies inside its box."""
    drawn = mv.panels.draw_all(ROOT / "reports" / "figures")
    scenes = mv.resolve(mv.STORYBOARD, drawn)
    width, height = mv.panels.SIZE
    for number, scene in scenes.items():
        if scene.source == "card":
            assert scene.card and scene.box is None, number
        elif scene.source == "clip":
            assert scene.box is None and not scene.card, number
        else:
            assert scene.source in drawn and isinstance(scene.box, tuple), number
            left, top, right, bottom = scene.box
            assert 0 <= left < right <= width and 0 <= top < bottom <= height, number
            if scene.start is not None:
                assert scene.start[0] <= left and scene.start[1] <= top, number
                assert right <= scene.start[2] and bottom <= scene.start[3], number
            if scene.mark is not None:
                assert isinstance(scene.mark, tuple), number
                assert left <= scene.mark[0] < scene.mark[2] <= right, number
                assert top <= scene.mark[1] < scene.mark[3] <= bottom, number
    # A window is inches only once its panel is drawn.
    assert isinstance(mv.STORYBOARD[11].box, mv.Window) and isinstance(scenes[11].box, tuple)
    # The question, the seven metrics and the recommendation are cards; the last one carries the
    # repository and names the data, in words only.
    assert all(mv.STORYBOARD[k].source == "card" for k in (3, 4, 9, 12))
    last = [t for _, t in mv.STORYBOARD[12].card]
    assert any("github.com/javiersr1996/ac2-football" in t for t in last)
    assert any(t.startswith("Data: SkillCorner open data") for t in last)


def test_the_d3_floor_label_of_the_video_is_crossed_by_no_line() -> None:
    """It sat centred on the zero line; it must stay between the zero line and the band edge."""
    drawn = mv.panels.draw_all(ROOT / "reports" / "figures")["layer3"]
    with matplotlib.rc_context(mv.panels.RC):
        renderer = FigureCanvasAgg(drawn.fig).get_renderer()
        drawn.fig.draw(renderer)
    ax = drawn.axes["a"]
    label = next(t for t in ax.texts if t.get_text().startswith("D3 floor"))
    box = label.get_window_extent(renderer)
    floor = float(label.get_text().split()[-1])
    for x in (0.0, -floor, floor):
        px = ax.transData.transform((x, 0))[0]
        assert not (box.x0 <= px <= box.x1), f"the line at {x} crosses the label"


def face(name: str, size: int) -> mv.ImageFont.FreeTypeFont:
    """The video's face when a render fetched it into build/fonts, else DejaVu Sans, which is
    wider than Chakra Petch and Roboto at the same size, so a width that passes here passes."""
    fetched = ROOT / "build" / "fonts" / mv.FONTS[name][0].rsplit("/", 1)[1]
    dejavu = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    stand_in = dejavu / ("DejaVuSans-Bold.ttf" if name == "heading" else "DejaVuSans.ttf")
    return mv.font(fetched if fetched.exists() else stand_in, size)


def test_every_caption_fits_in_two_lines_and_every_card_line_in_the_stage() -> None:
    body = face("body", mv.CAPTION_SIZE)
    for sentence in SENTENCES:
        assert 1 <= len(mv.wrap(sentence, body)) <= 2, sentence
    with pytest.raises(ValueError, match="4 lines"):
        mv.wrap(" ".join(SENTENCES[:3]), body)
    stage = mv.STAGE[2] - mv.STAGE[0]
    for scene in mv.STORYBOARD.values():
        for style, text in scene.card:
            name, size, _ = mv.CARD_STYLE[style]
            assert size >= 28 and face(name, size).getlength(text) <= stage, text


def test_the_teleprompter_says_the_script() -> None:
    lines = (ROOT / "docs" / "voice_recording.md").read_text(encoding="utf-8").splitlines()
    spoken = [line[3:] for line in lines if line.startswith("## ")]
    assert len(spoken) == len(SENTENCES)
    for line, sentence in zip(spoken, SENTENCES, strict=True):
        assert mv.tokens_of(line) == mv.tokens_of(sentence), line
        assert not any(c.isdigit() for c in line), line  # numerals written as they are read


# --- the command and the tools it runs ------------------------------------------------------------


def test_a_missing_recording_is_refused_before_anything_is_drawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With or without ``--words``, a ``--voice`` that does not exist stops the build at once,
    naming the file, with exit 2: no font is fetched, no panel is drawn, and faster-whisper is
    not blamed."""
    monkeypatch.setattr(mv.shutil, "which", lambda tool: f"/usr/bin/{tool}")

    def drawn(*args: object, **kwargs: object) -> None:
        raise AssertionError("the pictures were built before the recording was checked")

    monkeypatch.setattr(mv, "Pictures", drawn)
    missing = tmp_path / "memo.m4a"
    words = tmp_path / "words.json"
    words.write_text('{"words": []}', encoding="utf-8")
    for extra in ([], ["--words", str(words)]):
        assert mv.main(["--root", str(ROOT), "--voice", str(missing), *extra]) == 2
        out, err = capsys.readouterr()
        assert str(missing) in err and "faster-whisper" not in out + err


def test_a_tool_that_fails_is_reported_with_its_stderr(tmp_path: Path) -> None:
    """``run`` raises one error that carries the exit code and the tool's stderr, text or bytes;
    ``prepare_voice`` on a file that is not audio shows ffmpeg's own reason."""
    boom = "import sys; sys.stderr.write('boom: not a file'); sys.exit(3)"
    fake = [sys.executable, "-c", boom]
    for text in (True, False):
        with pytest.raises(RuntimeError, match="failed with 3") as caught:
            mv.run(fake, text=text)
        assert "boom: not a file" in str(caught.value)
    assert mv.run(fake[:2] + ["pass"]).returncode == 0
    garbage = tmp_path / "voice.m4a"
    garbage.write_bytes(b"not audio at all\n")
    with pytest.raises(RuntimeError, match="ffmpeg failed with") as caught:
        mv.prepare_voice(garbage, mv.Timing(0.0, 1.0, 1.0), tmp_path / "voice.wav")
    assert "Invalid data found when processing input" in str(caught.value)
