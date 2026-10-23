"""The guard on the held-out matches, state by state, on synthetic silver.

Every refusal here is checked against files the gate could have opened: the first test reads
the held-out synthetic match straight from the base, so a refusal is the guard and never
missing data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pytest
from ftbase import silver
from gate_helpers import (
    CAL,
    FROZEN_FILES,
    GUARDED,
    HELD,
    ROOT,
    Checkout,
    inside_the_reading,
)

from ac2fb.protocol import data
from ac2fb.protocol.data import HeldOutLocked


def frames(match_id: int) -> pa.Table:
    return data.read_frames([match_id], columns=["native_match_id", "is_detected"])


def ids(table: pa.Table) -> set[int]:
    return set(table["native_match_id"].to_pylist())


def test_the_heldout_silver_is_there_to_refuse(silver_pair: Path) -> None:
    rows = silver.read_frames([HELD], columns=["native_match_id"], data_dir=silver_pair)
    assert rows.num_rows > 0 and ids(rows) == {HELD}


def test_cal_and_held_belong_to_their_sets_in_the_real_split() -> None:
    split = json.loads((ROOT / "protocol" / "split.json").read_bytes())
    assert CAL in split["calibration"] and HELD in split["heldout"]


# --- design: calibration served, held-out refused ---------------------------------------------


def test_in_design_calibration_is_served_and_the_heldout_refused(gate: Checkout) -> None:
    assert ids(frames(CAL)) == {CAL}
    with pytest.raises(HeldOutLocked, match="stage 'design'"):
        frames(HELD)
    assert not data.guard_status().open


def test_a_request_with_one_heldout_id_is_refused_whole(gate: Checkout) -> None:
    with pytest.raises(HeldOutLocked):
        data.read_frames([CAL, HELD])


def test_an_id_outside_the_split_is_refused(gate: Checkout) -> None:
    with pytest.raises(ValueError, match=r"not in protocol/split\.json"):
        data.read_frames([900001])


@pytest.mark.parametrize("bad", ["1899585", ["1899585"], [1899585.0]])
def test_match_ids_are_integers(gate: Checkout, bad: object) -> None:
    with pytest.raises(TypeError):
        data.read_frames(bad)  # type: ignore[arg-type]


# --- read, inside the reading: the held-out is served there and only there ---------------------


def test_in_stage_read_the_heldout_is_served_inside_the_reading_only(gate: Checkout) -> None:
    gate.freeze("read")
    status = data.guard_status()
    assert status.open, status.reasons
    assert status.code_tree_sha == status.frozen_code_tree_sha == gate.tree_sha()
    assert status.protocol_stage == "dead" and status.stage == "read"
    with pytest.raises(HeldOutLocked, match="only inside `ac2fb heldout read`"):
        frames(HELD)
    with inside_the_reading():
        assert ids(frames(HELD)) == {HELD}
        assert ids(data.read_frames([CAL, HELD], columns=["native_match_id"])) == {CAL, HELD}
    with pytest.raises(HeldOutLocked, match="only inside"):
        frames(HELD)


def test_in_stage_frozen_it_never_opens_not_even_inside_the_reading(gate: Checkout) -> None:
    gate.freeze("frozen")
    assert not data.guard_status().open
    with inside_the_reading(), pytest.raises(HeldOutLocked, match="stage 'frozen'"):
        frames(HELD)


@pytest.mark.parametrize("stage", ["design", "frozen", "read", "Dead"])
def test_a_layer3_protocol_that_is_not_dead_keeps_it_shut(gate: Checkout, stage: str) -> None:
    gate.set_protocol(stage)
    gate.freeze("read")
    status = data.guard_status()
    assert len(status.reasons) == 1 and "not 'dead'" in status.reasons[0]
    with inside_the_reading(), pytest.raises(HeldOutLocked, match="not 'dead'"):
        frames(HELD)


@pytest.mark.parametrize("path", [*FROZEN_FILES, "src/ac2fb/new_module.py"])
def test_a_code_change_after_the_freeze_closes_it(gate: Checkout, path: str) -> None:
    # Any file that reaches the frozen code: the analysis, the door, the CLI, the pins of the
    # base and the libraries, the interpreter pin, and a new module under src.
    gate.freeze("read")
    gate.write(path, "# changed after the freeze\n")
    gate.commit("change frozen code")
    status = data.guard_status()
    # Stage read and a clean tree: only the code tree, and its change since the freeze, keep
    # it shut.
    assert status.stage == "read" and status.dirty == ()
    assert len(status.reasons) == 2 and "code_tree_sha" in status.reasons[1]
    assert status.reasons[0].startswith(f"['{path}'] changed since the freeze")
    with inside_the_reading(), pytest.raises(HeldOutLocked, match="code_tree_sha"):
        frames(HELD)


def test_a_change_outside_the_guarded_code_leaves_it_open(gate: Checkout) -> None:
    gate.freeze("read")
    gate.write("README.md", "edited after the freeze\n")
    gate.commit("edit the readme")
    assert data.guard_status().open
    with inside_the_reading():
        assert ids(frames(HELD)) == {HELD}


@pytest.mark.parametrize("path", ["uv.lock", "pyproject.toml", ".python-version"])
def test_a_checkout_without_a_frozen_file_stays_shut(gate: Checkout, path: str) -> None:
    # Nor can it be frozen: its code_tree_sha would not cover the missing pin.
    gate.git("rm", "-q", path)
    gate.commit(f"drop {path}")
    with pytest.raises(RuntimeError, match="does not hold all of"):
        data.code_tree_sha()
    status = data.guard_status()
    assert not status.open and "does not hold" in status.reasons[0]
    with inside_the_reading(), pytest.raises(HeldOutLocked, match="does not hold"):
        frames(HELD)


def test_read_without_a_recorded_code_tree_sha_stays_shut(gate: Checkout) -> None:
    gate.set_layer2("read", None)
    with inside_the_reading(), pytest.raises(HeldOutLocked, match="records None"):
        frames(HELD)


@pytest.mark.parametrize("stage", ["Read", "read ", "design", "frozen", "reading", "dead"])
def test_any_other_stage_stays_shut(gate: Checkout, stage: str) -> None:
    gate.set_layer2(stage, gate.tree_sha())
    with inside_the_reading(), pytest.raises(HeldOutLocked, match="stage"):
        frames(HELD)


def test_without_a_layer2_protocol_it_stays_shut(gate: Checkout) -> None:
    gate.git("rm", "-q", "protocol/layer2.json")
    gate.commit("drop layer2.json")
    status = data.guard_status()
    assert not status.open and "cannot check" in status.reasons[0]
    with inside_the_reading(), pytest.raises(HeldOutLocked, match="layer2.json"):
        frames(HELD)


@pytest.mark.parametrize("dirt", ["modified", "staged", "untracked"])
def test_a_dirty_tree_keeps_it_shut(gate: Checkout, dirt: str) -> None:
    gate.freeze("read")
    target = "src/ac2fb/reliability/__init__.py" if dirt != "untracked" else "notes.txt"
    gate.write(target, "x = 1\n")
    if dirt == "staged":
        gate.git("add", target)
    status = data.guard_status()
    # Stages and code tree at HEAD are the frozen ones: only the tree keeps it shut.
    assert status.stage == "read" and status.code_tree_sha == status.frozen_code_tree_sha
    assert len(status.reasons) == 1 and "not clean" in status.reasons[0]
    with inside_the_reading(), pytest.raises(HeldOutLocked, match="not clean"):
        frames(HELD)


@pytest.mark.parametrize("flag", ["--skip-worktree", "--assume-unchanged"])
def test_an_edit_hidden_from_git_status_keeps_it_shut(gate: Checkout, flag: str) -> None:
    gate.freeze("read")
    target = "src/ac2fb/reliability/__init__.py"
    gate.git("update-index", flag, target)
    gate.write(target, "def changed() -> None: ...\n")
    assert gate.git("status", "--porcelain", "--untracked-files=all") == ""
    with inside_the_reading(), pytest.raises(HeldOutLocked, match="hidden from git status"):
        frames(HELD)


# --- HEAD, never the working tree --------------------------------------------------------------


def test_an_uncommitted_reading_does_not_open_it(gate: Checkout) -> None:
    sha = gate.tree_sha()
    body = {"stage": "read", "code_tree_sha": sha, "reads": ["layer2"]}
    gate.write("protocol/layer2.json", json.dumps(body))
    with inside_the_reading(), pytest.raises(HeldOutLocked, match="stage 'design'"):
        frames(HELD)


def test_an_uncommitted_split_cannot_move_a_heldout_match(gate: Checkout) -> None:
    split = json.loads((gate.root / "protocol" / "split.json").read_bytes())
    split["heldout"].remove(HELD)
    split["calibration"].append(HELD)
    gate.write("protocol/split.json", json.dumps(split))
    assert HELD in data.load_split().heldout
    with pytest.raises(HeldOutLocked):
        frames(HELD)


def test_a_split_with_a_match_in_both_sets_is_rejected(gate: Checkout) -> None:
    split = json.loads((gate.root / "protocol" / "split.json").read_bytes())
    split["calibration"].append(HELD)
    gate.write("protocol/split.json", json.dumps(split))
    gate.commit("overlap")
    with pytest.raises(RuntimeError, match="disjoint"):
        frames(CAL)


# --- outside its own checkout the gate serves nothing ------------------------------------------


def test_outside_a_git_checkout_nothing_is_served(
    tmp_path: Path, silver_pair: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = tmp_path / "plain"
    (plain / "protocol").mkdir(parents=True)
    (plain / "protocol" / "split.json").write_bytes((ROOT / "protocol" / "split.json").read_bytes())
    monkeypatch.setattr(data, "_repo_root", lambda: plain)
    monkeypatch.setenv(data.DATA_ROOT_ENV, str(silver_pair))
    for match_id in (CAL, HELD):
        with pytest.raises(RuntimeError, match="git"):
            frames(match_id)
    assert not data.guard_status().open


def test_a_folder_inside_another_checkout_is_not_a_checkout(
    gate: Checkout, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate.freeze("read")
    inner = gate.root / "src"
    monkeypatch.setattr(data, "_repo_root", lambda: inner)
    with pytest.raises(RuntimeError, match="own git checkout"):
        frames(CAL)
    assert not data.guard_status().open


# --- the definition of code_tree_sha ------------------------------------------------------------


def test_code_tree_sha_is_the_sha256_of_git_ls_tree_of_the_frozen_paths(gate: Checkout) -> None:
    assert data.GUARDED_CODE == GUARDED
    assert data.code_tree_sha() == gate.tree_sha()
    before = data.code_tree_sha()
    gate.write("protocol/notes.md", "not code\n")
    gate.commit("outside")
    assert data.code_tree_sha() == before
    gate.write("src/ac2fb/defence/metric.py", "X = 1\n")
    gate.commit("inside")
    assert data.code_tree_sha() != before
    assert data.code_tree_sha("HEAD~1") == before


# --- dimensions: only the rows of the matches asked for -----------------------------------------


@pytest.mark.parametrize("name", ["dim_match", "dim_period", "dim_team_period", "dim_entity"])
def test_a_dimension_comes_back_with_the_rows_of_the_asked_matches_only(
    gate: Checkout, silver_pair: Path, name: str
) -> None:
    whole = silver.read_dim(name, data_dir=silver_pair)  # type: ignore[arg-type]
    assert set(whole["match_id"].to_pylist()) == {f"fb:{CAL}", f"fb:{HELD}"}
    cut = data.read_dim(name, [CAL])  # type: ignore[arg-type]
    assert set(cut["match_id"].to_pylist()) == {f"fb:{CAL}"}
    assert 0 < cut.num_rows < whole.num_rows


def test_dim_team_keeps_the_teams_of_the_asked_matches_only(
    gate: Checkout, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The synthetic matches share their two teams, so this one is a hand-made table.
    dims = {
        "dim_match": pa.table(
            {
                "match_id": [f"fb:{CAL}", f"fb:{HELD}"],
                "home_team_id": ["fb:1", "fb:3"],
                "away_team_id": ["fb:2", "fb:4"],
            }
        ),
        "dim_team": pa.table({"team_id": ["fb:1", "fb:2", "fb:3", "fb:4"]}),
        "dim_sport": pa.table({"sport": ["football"]}),
    }
    monkeypatch.setattr(silver, "read_dim", lambda name, data_dir=None: dims[name])
    assert sorted(data.read_dim("dim_team", [CAL])["team_id"].to_pylist()) == ["fb:1", "fb:2"]
    assert data.read_dim("dim_sport", [CAL]).num_rows == 1
