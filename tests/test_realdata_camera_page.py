"""The camera page on the real match (``-m realdata``): the build equals the committed files, the
scene is the clip's, the line at the reception is the four filled-in defenders, a broken
committed sidecar is named, and a held-out match exits 2."""

from __future__ import annotations

import json

import pytest
from test_camera_page import cp

from ac2fb import clip

pytestmark = pytest.mark.realdata


@pytest.fixture(scope="module")
def inputs() -> object:
    return cp.read_inputs(clip.DEFAULT_MATCH)


def test_the_page_check_passes_on_the_committed_files() -> None:
    assert cp.main(["--check"]) == 0


def test_the_scene_is_the_clips_and_the_line_is_four_filled_in_defenders(inputs: object) -> None:
    reports = cp.read_reports(cp.REPORTS)
    clip_json = json.loads(reports["clip/clip.json"])
    assert cp.against_clip(cp._clip_view(inputs.scene), clip_json) == []  # type: ignore[attr-defined]
    line = inputs.units["line"]  # type: ignore[attr-defined]
    assert line.frame == clip_json["key"]["frame"]
    assert line.player_ids == (69111, 51050, 560983, 50994) and line.seen == (False,) * 4
    block = inputs.units["block"]  # type: ignore[attr-defined]
    assert block.phase["keeper_id"] in block.player_ids


def test_a_broken_committed_sidecar_is_named_by_the_check(inputs: object) -> None:
    reports = cp.read_reports(cp.REPORTS)
    template = cp.TEMPLATE.read_text(encoding="utf-8")
    body = (cp.OUT_DIR / cp.SIDECAR).read_bytes()
    page = (cp.OUT_DIR / cp.PAGE).read_bytes()
    assert cp.check(inputs, reports, template, body, page)[0] == []
    bad = body.replace(b'"value": -1.1175', b'"value": -1.1275', 1)
    problems, _ = cp.check(inputs, reports, template, bad, page)
    assert any(p.startswith("camera.json: differs from the recomputation") for p in problems)
    assert f"{cp.PAGE}: its payload differs from {cp.SIDECAR}" in problems


def test_a_heldout_match_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    # refused by the guard, not missing: without the held-out's silver both exit 2
    assert cp.main(["--check", "--match", "1899585"]) == 2
    assert capsys.readouterr().err.startswith("refused: held-out match(es) [1899585]")
