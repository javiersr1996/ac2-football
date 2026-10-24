"""The committed clip, on the real match of the quick block.

Deselected by default (``pytest -m realdata``): it needs match 1874553 built under
``$FTBASE_DATA_ROOT`` or ``data/``. The rule picks the same reception that ``reports/clip/``
records, the committed files pass their check, and a held-out match is refused.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_split import HELDOUT

from ac2fb import clip
from ac2fb.cli import CLIP_FILES, main
from ac2fb.reliability.match import load_match

pytestmark = pytest.mark.realdata

COMMITTED = Path(__file__).resolve().parent.parent / "reports" / "clip"


def test_the_rule_picks_the_recorded_reception_and_the_committed_files_pass_the_check() -> None:
    built = clip.build(load_match(clip.DEFAULT_MATCH), clip.DEFAULT_RULE)
    side = json.loads(built.sidecar)
    assert side["reception"] == {
        "event_subtype": "pass",
        "frame": 14562,
        "period": 1,
        "receiver_id": 50968,
        "team_id": 866,
    }
    assert side["key"]["frame"] == 14562
    assert side["key"]["defenders_extrapolated"] == 7 and side["key"]["defenders_seen"] == 4
    committed = [(COMMITTED / name).read_bytes() for name in CLIP_FILES]
    got = clip.check(built, *committed)
    assert got.ok, got.problems
    assert 0 < len(committed[2]) < 3_000_000


def test_a_heldout_match_is_refused() -> None:
    assert main(["clip", "--match", str(HELDOUT[0]), "--out-dir", str(COMMITTED / "refused")]) == 2
    assert not (COMMITTED / "refused").exists()
