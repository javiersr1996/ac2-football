"""Smoke test: the pinned base builds bronze and silver on its synthetic match."""

from __future__ import annotations

from pathlib import Path

from ftbase.cli import main
from ftbase.fixtures import PLANTED_RUNS, write_synthetic_match
from ftbase.silver import read_frames


def test_extrapolated_runs_read_from_silver_are_the_planted_runs(tmp_path: Path) -> None:
    match = write_synthetic_match(tmp_path / "fx")
    data_dir = tmp_path / "data"
    args = ["--manifest", str(match.manifest), "--data-dir", str(data_dir)]
    assert main(["ingest", *args, "--from-existing", str(match.root)]) == 0
    assert main(["bronze", *args]) == 0
    assert main(["silver", *args]) == 0

    rows = read_frames(
        [match.match_id],
        columns=["entity_id", "entity_kind", "frame_native", "is_detected"],
        data_dir=data_dir,
    ).to_pylist()
    extrapolated = {(r["entity_id"], r["frame_native"]) for r in rows if not r["is_detected"]}
    planted = {(f"fb:{run.player_id}", f) for run in PLANTED_RUNS for f in run.frames}
    assert planted, "the generator must plant something for this test to mean anything"
    assert extrapolated == planted
    assert all(r["entity_kind"] == "player" for r in rows if not r["is_detected"])
