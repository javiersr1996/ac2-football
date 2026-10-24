"""The clip of the video: the rule, what is drawn, the sidecar, the check and the command.

The clip is built here on the synthetic match (``CAL``) with a short window, because the
synthetic periods hold 60 frames; the real match is in ``test_realdata_clip.py``. The rule is
tested by planting detection and ``gap_len`` in copies of the match and asking which reception it
picks; what is drawn is tested against the long table read through the door (not against the
arrays the clip itself used), and the pixels of a hollow and a filled marker are looked at. Each
test names the mutation of ``src/ac2fb/clip.py`` that makes it fail.
"""

from __future__ import annotations

import dataclasses
import io
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.image
import matplotlib.style
import numpy as np
import pytest
from gate_helpers import CAL, HELD, Checkout
from numpy.typing import NDArray

from ac2fb import clip
from ac2fb.cli import main
from ac2fb.protocol import data
from ac2fb.reliability import long
from ac2fb.reliability.match import MatchData, load_match, locate_rows

SHORT = clip.Rule(before=10, frames=40, min_seen=1)
FRAME_COLUMNS = [
    "match_id", "native_match_id", "period", "frame_native", "entity_id", "entity_kind",
    "team_id", "x_m", "y_m", "is_detected",
]  # fmt: skip
# synthetic ``CAL``: periods 1 and 2 are frames 0-59 and 70-129; receptions at these frames
# (team 7: 71, 72, 73; team 8: 81, 82, 83). With SHORT, the windows of 15, 30 and 100 are whole.
RIVALS = {15: (81, 82, 83), 30: (71, 72, 73), 100: (81, 82, 83)}


@pytest.fixture(scope="module")
def match(silver_pair: Path) -> MatchData:
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(data.DATA_ROOT_ENV, str(silver_pair))
        return load_match(CAL)


@pytest.fixture(scope="module")
def built(match: MatchData) -> clip.Built:
    return clip.build(match, SHORT)


def plant(
    match: MatchData,
    *,
    out: dict[int, dict[int, int]] | None = None,
    receiver_out: tuple[int, int] | None = None,
    ball_out: int | None = None,
) -> MatchData:
    """A copy of the match: ``out[frame] = {rival: gap_len}`` extrapolated at that frame.

    ``receiver_out = (player, frame)`` makes that player extrapolated, ``ball_out`` the ball at
    that frame. Everything else stays as the synthetic match has it.
    """
    detected, gap, ball = match.detected.copy(), match.gap.copy(), match.ball_detected.copy()
    for frame, rivals in (out or {}).items():
        for player, g in rivals.items():
            row = locate_rows(match, np.array([player]), np.array([frame]))[0]
            detected[row], gap[row] = False, g
    if receiver_out is not None:
        row = locate_rows(match, np.array([receiver_out[0]]), np.array([receiver_out[1]]))[0]
        detected[row], gap[row] = False, 1
    if ball_out is not None:
        ball[int(np.searchsorted(match.ball_frame, ball_out))] = False
    return dataclasses.replace(match, detected=detected, gap=gap, ball_detected=ball)


def key_of(match: MatchData, rule: clip.Rule = SHORT) -> int:
    scene = clip.choose(match, rule)
    return int(scene.frame[scene.key])


def undetected(frame: int, n: int, gap: int) -> dict[int, dict[int, int]]:
    """``n`` of the rivals of the reception at ``frame`` extrapolated, each ``gap`` frames."""
    return {frame: {p: gap for p in RIVALS[frame][:n]}}


# --- the rule ----------------------------------------------------------------------------------


def test_the_rule_ranks_by_the_number_of_extrapolated_rivals_before_their_gap(
    match: MatchData,
) -> None:
    # Mutation (ranking by the longest gap first): the one-rival reception with gap 50 wins.
    planted = plant(match, out=undetected(15, 2, 5) | undetected(100, 1, 50))
    assert key_of(planted) == 15


def test_equal_counts_are_broken_by_the_longest_gap(match: MatchData) -> None:
    # Mutation (dropping the gap from the key): the earlier reception, 15, wins the tie.
    planted = plant(match, out=undetected(15, 1, 5) | undetected(100, 1, 9))
    assert key_of(planted) == 100


def test_equal_counts_and_gaps_are_broken_by_the_earlier_frame(match: MatchData) -> None:
    # Mutation (frame sorted descending): 100 wins.
    planted = plant(match, out=undetected(15, 1, 5) | undetected(100, 1, 5))
    assert key_of(planted) == 15


def test_a_window_with_a_hole_is_skipped_however_good_it_scores(match: MatchData) -> None:
    # Frames 60 to 69 do not exist: the window of 45 (35 to 74) has a hole, and so has the one of
    # 70. Mutation (no completeness check): the planted 45 wins.
    planted = plant(match, out={45: {71: 90, 72: 90}} | undetected(15, 1, 5))
    scene = clip.choose(planted, SHORT)
    assert int(scene.frame[scene.key]) == 15
    assert scene.frame.tolist() == list(range(5, 45))


def test_a_window_before_the_first_frame_is_skipped(match: MatchData) -> None:
    # The reception at frame 0 has no 10 frames before it. Mutation (window clipped to the data):
    # the planted 0 wins.
    first = {0: {81: 90, 82: 90, 83: 90}}
    assert key_of(plant(match, out=first | undetected(15, 1, 5))) == 15


def test_the_receiver_must_be_detected_at_the_reception(match: MatchData) -> None:
    # Mutation (receiver not tested): 15 wins with a receiver the camera did not see.
    planted = plant(match, out=undetected(15, 2, 5) | undetected(100, 1, 5), receiver_out=(72, 15))
    assert key_of(planted) == 100


def test_the_ball_must_be_detected_at_the_reception(match: MatchData) -> None:
    # Mutation (ball not tested): 15 wins with a ball the camera did not see.
    planted = plant(match, out=undetected(15, 2, 5) | undetected(100, 1, 5), ball_out=15)
    assert key_of(planted) == 100


def test_at_least_min_seen_rivals_must_be_detected_and_exactly_min_seen_is_enough(
    match: MatchData,
) -> None:
    # At 15, two of three rivals are extrapolated: one seen. Mutation (``<`` to ``<=``, or the
    # threshold off by one): the first assertion or the second fails.
    planted = plant(match, out=undetected(15, 2, 5) | undetected(100, 1, 5))
    assert key_of(planted, clip.Rule(before=10, frames=40, min_seen=1)) == 15
    assert key_of(planted, clip.Rule(before=10, frames=40, min_seen=2)) == 100


def test_no_reception_with_a_complete_window_is_an_error_naming_the_match(
    match: MatchData,
) -> None:
    with pytest.raises(clip.NoReception, match=str(CAL)):
        clip.choose(match, clip.Rule(before=10, frames=500, min_seen=1))


def test_the_default_match_is_a_calibration_match() -> None:
    # Mutation (a held-out id as the default): the clip would be asked for one by default.
    assert clip.DEFAULT_MATCH in data.load_split().calibration


# --- what is drawn comes from the long table ---------------------------------------------------


def test_every_number_drawn_is_the_long_tables(
    match: MatchData, built: clip.Built, silver_pair: Path
) -> None:
    # Read the long table again through the door and look every drawn row up in it, not in the
    # arrays the clip used. Mutation (gap_len of the next frame, or x and y swapped): a row differs.
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(data.DATA_ROOT_ENV, str(silver_pair))
        table = long.long_table(data.read_frames([CAL], columns=FRAME_COLUMNS)).to_pylist()
    rows = {(r["player_id"], r["frame"]): r for r in table if r["player_id"] is not None}
    ball = {r["frame"]: r for r in table if r["player_id"] is None}
    scene, side = built.scene, json.loads(built.sidecar)
    for j, who in enumerate(side["defenders"]):
        assert who["player_id"] == scene.rivals[j]
        for i, frame in enumerate(side["frames"]):
            row = rows[(who["player_id"], frame)]
            assert row["team_id"] != scene.team
            assert who["detected"][i] == row["is_detected"]
            assert who["gap_len"][i] == row["gap_len"]
            assert tuple(scene.rival_xy[i, j]) == (row["x"] * scene.sign, row["y"] * scene.sign)
    for i, frame in enumerate(side["frames"]):
        assert side["ball"]["gap_len"][i] == ball[frame]["gap_len"]
        assert tuple(scene.ball[i]) == (
            ball[frame]["x"] * scene.sign,
            ball[frame]["y"] * scene.sign,
        )
        me = rows[(side["reception"]["receiver_id"], frame)]
        assert side["receiver"]["detected"][i] == me["is_detected"]
        assert side["receiver"]["gap_len"][i] == me["gap_len"]
    assert side["match_id"] == CAL
    assert side["frames"] == list(range(side["frames"][0], side["frames"][0] + SHORT.frames))
    assert side["key"]["frame"] == side["frames"][side["key"]["index"]] == side["frames"][10]


def test_the_pitch_is_turned_so_the_receivers_team_attacks_to_the_right(
    match: MatchData, built: clip.Built
) -> None:
    # Period 1 of the synthetic match: team 7 attacks +x, team 8 -x. Mutation (sign not applied, or
    # taken from the other team): the receiver's x keeps the provider's sign.
    scene = built.scene
    assert scene.sign == match.attack_sign[(scene.period, scene.team)]
    row = locate_rows(match, np.array([scene.receiver]), np.array([scene.frame[scene.key]]))[0]
    assert scene.me[scene.key, 0] == match.x[row] * scene.sign
    assert {-1, 1} == {match.attack_sign[(1, 7)], match.attack_sign[(1, 8)]}


def test_the_sidecar_is_canonical_and_says_the_rule(built: clip.Built) -> None:
    # Mutation (CRLF, unsorted keys, a missing final newline, or a timestamp): one of these fails.
    text = built.sidecar.decode("utf-8")
    assert "\r" not in text and text.endswith("}\n")
    document = json.loads(text)
    assert text == json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    assert document["rule"] == clip.describe(SHORT)
    assert str(SHORT.frames) in document["rule"] and str(SHORT.before) in document["rule"]
    assert re.search(r"20\d\d-\d\d-\d\d", text) is None  # no date, no timestamp
    assert document["pixels"]["frames_sha256"] == built.frames_sha256
    assert document["n_frames"] == built.n_frames == SHORT.frames


def test_building_twice_gives_the_same_bytes_and_pixels(
    match: MatchData, built: clip.Built
) -> None:
    # Mutation (a fresh figure state leaking in, such as a user's rcParams or a changing hash salt).
    with matplotlib.rc_context({"font.size": 30, "figure.facecolor": "black"}):
        again = clip.build(match, SHORT)
    assert again.sidecar == built.sidecar and again.frames_sha256 == built.frames_sha256
    assert (again.still_pixels == built.still_pixels).all()


def test_a_hollow_marker_is_drawn_for_each_extrapolated_defender_with_its_gap_in_seconds(
    match: MatchData,
) -> None:
    # Plant three frames' worth of extrapolation and read the labels the painter wrote.
    # Mutation (gap_len printed in frames, or a label on a detected defender): a text differs.
    out = {15: {81: 5}, 20: {81: 37, 83: 4}, 21: {82: 100}}
    scene = clip.choose(plant(match, out=out), SHORT)
    assert int(scene.frame[scene.key]) == 15
    labelled = 0
    with matplotlib.style.context("default"), matplotlib.rc_context(clip.RC):
        paint = clip._Painter(scene)
        for i, frame in enumerate(scene.frame.tolist()):
            paint.draw(i)
            shown = {
                j: label.get_text() for j, label in enumerate(paint.labels) if label.get_visible()
            }
            wanted = {
                j: f"{scene.rival_gap[i, j] / 10:.1f} s"
                for j in range(len(scene.rivals))
                if not scene.rival_detected[i, j]
            }
            assert shown == wanted, frame
            labelled += len(wanted)
    assert labelled >= 4  # the frames above were not all empty


def pixel(paint: Any, frame: NDArray[np.uint8], x: float, y: float) -> tuple[int, ...]:
    col, row = paint.ax.transData.transform((x, y))
    return tuple(int(v) for v in frame[clip.HEIGHT - 1 - int(round(row)), int(round(col))])


def test_a_seen_defender_is_a_filled_marker_and_an_extrapolated_one_is_hollow(
    match: MatchData,
) -> None:
    # The centre of the marker is vermilion if seen and white if filled in by the model.
    # Mutation (the two masks swapped, or both kinds drawn filled): a centre has the wrong colour.
    scene = clip.choose(plant(match, out=undetected(15, 1, 5)), SHORT)
    i = scene.key
    assert scene.rival_detected[i].sum() == 2 and (~scene.rival_detected[i]).sum() == 1
    with matplotlib.style.context("default"), matplotlib.rc_context(clip.RC):
        paint = clip._Painter(scene)
        frame = paint.draw(i)
        vermilion = tuple(int(clip.VERMILION[k : k + 2], 16) for k in (1, 3, 5))
        for j in range(len(scene.rivals)):
            x, y = scene.rival_xy[i, j]
            colour = pixel(paint, frame, x, y)
            assert colour == (vermilion if scene.rival_detected[i, j] else (255, 255, 255)), j


# --- the check ---------------------------------------------------------------------------------


def png(pixels: NDArray[np.uint8], **kw: Any) -> bytes:
    buffer = io.BytesIO()
    matplotlib.image.imsave(buffer, pixels, format="png", **kw)
    return buffer.getvalue()


def tagged(built: clip.Built) -> bytes:
    """Stand-in video bytes: what ``encode_mp4`` puts in the comment, around other bytes."""
    return b"\x00\x00\x00 ftypisom" + f"{clip.MP4_TAG}{built.frames_sha256}".encode() + b"\x00"


def test_the_check_passes_on_the_files_it_would_write(built: clip.Built) -> None:
    got = clip.check(built, built.sidecar, built.still, tagged(built))
    assert got.ok and got.problems == [] and got.frames == SHORT.frames


def test_the_check_names_each_missing_file(built: clip.Built) -> None:
    # Mutation (a missing file taken as fine): the problem list is empty.
    got = clip.check(built, None, None, None)
    assert [p.split(":")[0] for p in got.problems] == ["clip.json", "clip_still.png", "clip.mp4"]
    assert got.video_bytes is None


def test_the_check_sees_a_changed_byte_in_the_sidecar(built: clip.Built) -> None:
    # Mutation (a prefix, or only the keys, compared): the change goes unseen.
    old = built.sidecar
    for at in (0, len(old) // 2, len(old) - 2):
        changed = old[:at] + bytes([old[at] ^ 1]) + old[at + 1 :]
        got = clip.check(built, changed, built.still, tagged(built))
        assert not got.ok and got.problems[0].startswith("clip.json: differs"), at


def test_the_check_compares_the_still_by_its_pixels_not_its_bytes(built: clip.Built) -> None:
    # The same pixels re-encoded pass; one pixel off, in any channel, fails. Mutation (bytes
    # compared: the first assertion fails; a tolerance or a sample: the second does).
    other_bytes = png(built.still_pixels, pil_kwargs={"compress_level": 0})
    assert other_bytes != built.still
    assert clip.check(built, built.sidecar, other_bytes, tagged(built)).ok
    for channel in range(3):
        nudged = built.still_pixels.copy()
        nudged[clip.HEIGHT // 2, clip.WIDTH // 2, channel] ^= 1
        got = clip.check(built, built.sidecar, png(nudged), tagged(built))
        assert not got.ok and "pixels differ" in got.problems[0], channel


def test_the_check_ties_the_video_to_the_hash_of_the_frames(built: clip.Built) -> None:
    # Mutation (any MP4 accepted, or only its presence checked): the stale hash passes.
    stale = tagged(built).replace(built.frames_sha256.encode(), b"0" * 64)
    got = clip.check(built, built.sidecar, built.still, stale)
    assert not got.ok and got.problems == [
        "clip.mp4: does not carry the hash of the frames drawn again"
    ]
    assert not clip.check(built, built.sidecar, built.still, b"").ok


def test_a_clip_of_another_rule_does_not_pass_as_this_one(
    match: MatchData, built: clip.Built
) -> None:
    # Mutation (rule left out of the sidecar and of the hash): the other clip's files pass.
    other = clip.build(match, clip.Rule(before=11, frames=39, min_seen=1))
    got = clip.check(built, other.sidecar, other.still, tagged(other))
    # the still is the same key frame of the same reception, so its pixels agree
    assert [p.split(":")[0] for p in got.problems] == ["clip.json", "clip.mp4"]


# --- the video ---------------------------------------------------------------------------------


def test_the_video_is_h264_with_every_frame_and_carries_the_hash(
    built: clip.Built, tmp_path: Path
) -> None:
    exe = clip.ffmpeg()
    assert exe is not None, "ffmpeg is needed to test the video: ci.yml installs it"
    path = tmp_path / "clip.mp4"
    size = clip.encode_mp4(built, path)
    video = path.read_bytes()
    assert size == len(video) > 1000 and video[4:8] == b"ftyp"
    assert clip.check(built, built.sidecar, built.still, video).ok
    probe = subprocess.run(
        [exe, "-v", "info", "-i", str(path), "-f", "null", "-"], capture_output=True, text=True
    )
    assert probe.returncode == 0 and "Video: h264" in probe.stderr
    assert "1280x720" in probe.stderr and "yuv420p" in probe.stderr
    assert [int(n) for n in re.findall(r"frame=\s*(\d+)", probe.stderr)][-1] == SHORT.frames


def test_without_ffmpeg_the_video_cannot_be_encoded(
    built: clip.Built, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(clip, "ffmpeg", lambda: None)
    with pytest.raises(FileNotFoundError, match="ffmpeg"):
        clip.encode_mp4(built, tmp_path / "clip.mp4")
    assert not (tmp_path / "clip.mp4").exists()


# --- the command -------------------------------------------------------------------------------


def test_the_command_refuses_a_heldout_match_and_writes_nothing(
    gate: Checkout, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Mutation (the match read outside the door, or the refusal swallowed): not exit 2.
    out = tmp_path / "clip"
    assert main(["clip", "--match", str(HELD), "--out-dir", str(out)]) == 2
    assert "held-out" in capsys.readouterr().err
    assert not out.exists()
    assert main(["clip", "--check", "--match", str(HELD), "--out-dir", str(out)]) == 2


def test_the_command_writes_the_three_files_and_its_check_passes_without_ffmpeg(
    gate: Checkout,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(clip, "DEFAULT_RULE", SHORT)
    out = tmp_path / "clip"
    assert main(["clip", "--out-dir", str(out)]) == 0  # the default match is CAL
    assert sorted(p.name for p in out.iterdir()) == sorted(
        ["clip.json", "clip_still.png", "clip.mp4"]
    )
    capsys.readouterr()
    monkeypatch.setattr(clip, "ffmpeg", lambda: None)  # a check never encodes
    assert main(["clip", "--check", "--out-dir", str(out)]) == 0
    assert "clip: OK" in capsys.readouterr().out
    side = out / "clip.json"
    side.write_bytes(side.read_bytes().replace(b'"seconds": 4.0', b'"seconds": 5.0'))
    assert main(["clip", "--check", "--out-dir", str(out)]) == 1
    assert "clip: FAILED" in capsys.readouterr().out
    (out / "clip.mp4").unlink()
    assert main(["clip", "--check", "--out-dir", str(out)]) == 1


def test_the_command_without_ffmpeg_writes_nothing(
    gate: Checkout,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mutation (the sidecar and still written before ffmpeg is looked for): the directory exists.
    monkeypatch.setattr(clip, "DEFAULT_RULE", SHORT)
    monkeypatch.setattr(clip, "ffmpeg", lambda: None)
    out = tmp_path / "clip"
    assert main(["clip", "--out-dir", str(out)]) == 1
    assert "ffmpeg" in capsys.readouterr().err
    assert not out.exists()


def test_the_command_says_when_no_reception_has_a_window(
    gate: Checkout, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The synthetic periods hold 60 frames: the real rule (100) finds none.
    out = tmp_path / "clip"
    assert main(["clip", "--out-dir", str(out)]) == 1
    assert "no reception" in capsys.readouterr().err
    assert not out.exists()
