"""Task 19: the protocol file and its check.

The committed protocol passes the check; every constant the code fixes is compared (a protocol
that differs in any of them fails, naming the field and the code's value); the coherence rules
and the schema are exercised by mutating a copy; no number of the protocol comes from a results
file (the check takes the parsed protocol and opens nothing under ``reports/``, and every
numeric field is checked against the code, derived or declared protocol-only, so a number that
is none of the three fails the check). Mutations annotated in the task's record.
"""

from __future__ import annotations

import builtins
import copy
import io
import json
from pathlib import Path
from typing import Any

import pytest

from ac2fb import cli
from ac2fb.defence import bar, power, pressure, probe_s1
from ac2fb.protocol import check

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_FILE = ROOT / "protocol" / "protocol.json"


def protocol() -> dict[str, Any]:
    return cli._read_protocol(PROTOCOL_FILE)


def put(doc: dict[str, Any], path: str, value: object) -> dict[str, Any]:
    """A deep copy of ``doc`` with the dotted ``path`` set to ``value``."""
    out = copy.deepcopy(doc)
    node: Any = out
    *parents, last = path.split(".")
    for part in parents:
        node = node[part]
    node[last] = value
    return out


def drop(doc: dict[str, Any], path: str) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    node: Any = out
    *parents, last = path.split(".")
    for part in parents:
        node = node[part]
    del node[last]
    return out


# --- the committed protocol --------------------------------------------------------------------


def test_the_committed_protocol_passes_the_check() -> None:
    report = check.check(protocol())
    assert report.problems == ()
    assert report.ok


def test_the_check_says_how_much_it_verified() -> None:
    report = check.check(protocol())
    assert report.schema_fields == len(check.SCHEMA) + 1
    assert report.coherence_rules >= 20
    assert report.code_constants == len(check.CODE_CHECKS) >= 20
    accounted = {c.path for c in check.CODE_CHECKS} | set(check.DERIVED) | set(check.PROTOCOL_ONLY)
    leaves = set(check.numeric_leaves(protocol()))
    assert leaves <= accounted and report.numeric_leaves == len(leaves) >= 20


def test_the_protocol_file_is_lf_and_in_stage_design() -> None:
    raw = PROTOCOL_FILE.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    doc = json.loads(raw.decode("utf-8"))
    assert doc["stage"] == "design" and doc["code_tree_sha"] is None
    assert doc["candidate"] == "C1" and doc["written_before_any_outcome"] is True


def test_the_plan_text_of_every_death_criterion_is_quoted() -> None:
    criteria = protocol()["death_criteria"]
    assert criteria["immovable"] is True
    for name in ("D1", "D2", "D3", "D4", "D5", "D6"):
        assert criteria[name]["plan_text"].startswith(name + " ")
        assert criteria[name]["evaluation"]


def test_the_protocol_fixes_what_the_plan_fixes() -> None:
    doc = protocol()
    assert doc["window"]["frames"] == pressure.INCOMING_WINDOW == 13
    assert doc["cause"]["treatment"]["pressed_if_index_at_least"] == pressure.PRESSED_INDEX == 0.5
    assert doc["null"]["draws"] == bar.N_PERMUTATIONS == 2000
    assert doc["null"]["block_by_possession_if_rho_above"] == bar.BLOCK_RHO == 0.1
    assert doc["null"]["blocked"] is False
    assert doc["bars"]["calibration"]["same_sign_matches_at_least"] == bar.BAR_SAME_SIGN == 8
    assert doc["bars"]["calibration"]["p_at_most"] == bar.BAR_P == 0.00135
    assert doc["bars"]["heldout"] | {"definition": ""} == {
        "same_sign_matches_at_least": 8,
        "alpha": 0.01,
        "holm_family": ["V0", "V1"],
        "definition": "",
    }
    assert doc["death_criteria"]["D2"]["mde80_at_most_sd"] == power.MDE_LIMIT == 0.3
    assert doc["death_criteria"]["D3"]["ratio"] == power.D3_RATIO == 0.5
    assert doc["death_criteria"]["D3"]["units"].startswith("sd of the cell")
    assert doc["death_criteria"]["D4"]["ratio"] == 0.5
    assert doc["death_criteria"]["D1"]["min_matches"] == probe_s1.MIN_MATCHES == 9
    assert doc["units"]["exclusion"]["gap_frames_at_most"] == 13
    assert doc["units"]["exclusion"]["applies_to"] == "the later unit"
    assert doc["statistic"]["effect_in_cell"].startswith("tau_c: the least-squares coefficient")
    assert "y - x" in doc["statistic"]["why_adjusted"]  # the change from before is rejected


# --- the code checks ---------------------------------------------------------------------------


def mutated(value: object) -> object:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, float):
        return value * 2 + 0.001
    if isinstance(value, list):
        return list(reversed(value)) if len(value) > 1 else [*value, "x"]
    assert isinstance(value, str)
    return value + "x"


@pytest.mark.parametrize("item", [pytest.param(c, id=c.path) for c in check.CODE_CHECKS])
def test_a_protocol_that_differs_from_the_code_fails(item: check.CodeCheck) -> None:
    doc = protocol()
    _, value = check._get(doc, item.path)
    report = check.check(put(doc, item.path, mutated(value)))
    assert any(p.startswith(item.path) and item.source in p for p in report.problems), (
        item.path,
        report.problems,
    )


def test_a_missing_checked_field_is_a_problem() -> None:
    report = check.check(drop(protocol(), "null.draws"))
    assert any("missing field null.draws" in p for p in report.problems)


def test_an_int_is_not_a_float_in_a_checked_field() -> None:
    # The code fixes a float cut; 1 (int) is not 1.0 either way, and 0.5 as "0.5" is a string.
    doc = protocol()
    assert check.check(put(doc, "cause.treatment.pressed_if_index_at_least", "0.5")).problems
    assert check.check(put(doc, "strata.direction.cut_m", 2)).problems


# --- coherence and schema ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "value", "words"),
    [
        ("window.seconds", 1.4, "window.seconds"),
        ("units.exclusion.gap_frames_at_most", 12, "gap_frames_at_most"),
        ("units.exclusion.applies_to", "the earlier unit", "later unit"),
        ("strata.cells", 17, "strata.cells"),
        ("bars.heldout.holm_family", ["V0"], "Holm family"),
        ("bars.heldout.holm_family", ["V0", "V1", "V2"], "Holm family"),
        ("bars.calibration.holm", True, "no Holm"),
        ("bars.calibration.null_draws_as_extreme_at_most", 2, "null_draws_as_extreme_at_most"),
        ("bars.heldout.alpha", 0.001, "stricter"),
        ("bars.heldout.same_sign_matches_at_least", 7, "same sign agreement"),
        ("null.blocked", True, "not blocked"),
        ("null.stream", "one stream", "seed"),
        ("death_criteria.D4.ratio", 0.4, "halves"),
        ("death_criteria.D3.units", "metres", "sd of the cell"),
        ("death_criteria.immovable", False, "immovable"),
        ("outcome.expected_sign_of_effect", "positive", "negative"),
        ("candidate", "C2", "C1"),
        ("written_before_any_outcome", False, "written_before_any_outcome"),
        ("stage", "frozen", "code_tree_sha"),
        ("stage", "open", "stage"),
        ("code_tree_sha", "a" * 64, "code_tree_sha"),
        ("cause.treatment.pressed_if_index_at_least", 1.5, "between 0 and 1"),
        ("cause.label_levels", ["a", "b"], "five levels"),
        ("death_criteria.D1.min_matches", 11, "matches per half"),
    ],
)
def test_an_incoherent_protocol_fails(path: str, value: object, words: str) -> None:
    report = check.check(put(protocol(), path, value))
    assert any(words in p for p in report.problems), (path, report.problems)


@pytest.mark.parametrize(
    ("path", "value", "source"),
    [
        ("null.seed", 20, "ac2fb.defence.effect.SEED"),
        ("bars.heldout.alpha", 0.02, "ac2fb.defence.effect.HELDOUT_ALPHA"),
        ("death_criteria.D4.ratio", 0.6, "ac2fb.defence.effect.D4_RATIO"),
    ],
)
def test_the_estimators_constants_are_checked_against_the_code(
    path: str, value: object, source: str
) -> None:
    # Since task 20 the seed, the held-out level and D4's ratio are fixed by the estimator.
    assert any(source in p for p in check.check(put(protocol(), path, value)).problems)


def test_a_frozen_protocol_needs_a_real_sha() -> None:
    doc = put(protocol(), "stage", "frozen")
    assert any("code_tree_sha" in p for p in check.check(doc).problems)
    sha = "0123456789abcdef" * 4
    frozen = check.check(put(doc, "code_tree_sha", sha))
    assert not any("code_tree_sha" in p or "stage" in p for p in frozen.problems)
    short = check.check(put(doc, "code_tree_sha", "abc"))
    assert any("hexadecimal" in p for p in short.problems)


@pytest.mark.parametrize(
    ("path", "words"),
    [
        ("death_criteria.D5", "death_criteria holds"),
        ("window.frames", "missing field window.frames"),
        ("code_tree_sha", "missing field code_tree_sha"),
        ("null.seed", "missing field null.seed"),
        ("statistic.why_adjusted", "missing field statistic.why_adjusted"),
    ],
)
def test_a_missing_field_is_a_problem(path: str, words: str) -> None:
    assert any(words in p for p in check.check(drop(protocol(), path)).problems)


def test_an_empty_or_misnamed_plan_text_is_a_problem() -> None:
    doc = protocol()
    assert any(
        "D3.plan_text is empty" in p
        for p in check.check(put(doc, "death_criteria.D3.plan_text", " ")).problems
    )
    renamed = put(doc, "death_criteria.D3.plan_text", "D2 otra cosa")
    assert any("does not start with D3" in p for p in check.check(renamed).problems)
    assert any(
        "D7" in p
        for p in check.check(
            put(doc, "death_criteria.D7", {"plan_text": "D7 x", "evaluation": "y"})
        ).problems
    )


def test_a_mistyped_field_is_a_problem() -> None:
    doc = protocol()
    assert any(
        "window.frames is str" in p for p in check.check(put(doc, "window.frames", "13")).problems
    )
    assert any(
        "null.blocked is int" in p for p in check.check(put(doc, "null.blocked", 0)).problems
    )
    assert any(
        "window.frames is bool" in p for p in check.check(put(doc, "window.frames", True)).problems
    )


# --- no number from a results file -------------------------------------------------------------


def test_every_number_of_the_protocol_is_accounted_for() -> None:
    doc = protocol()
    leaves = check.numeric_leaves(doc)
    checked = {c.path for c in check.CODE_CHECKS}
    for path in leaves:
        assert path in checked or path in check.DERIVED or path in check.PROTOCOL_ONLY, path
    # A number nobody accounts for fails the check, wherever it hides.
    extra = check.check(put(doc, "about", {"text": doc["about"], "n": 3}))
    assert any("numeric field about.n = 3" in p for p in extra.problems)
    nested = copy.deepcopy(doc)
    nested["reading_order"].append({"step": 7})
    assert any("reading_order[6].step" in p for p in check.check(nested).problems)


def test_numeric_leaves_see_numbers_and_not_booleans() -> None:
    got = check.numeric_leaves({"a": 1, "b": True, "c": {"d": 2.5, "e": [3, "x", {"f": 4}]}})
    assert got == {"a": 1, "c.d": 2.5, "c.e[0]": 3, "c.e[2].f": 4}


def test_the_code_checks_come_from_the_code_not_from_a_report() -> None:
    # Every expected value is a code attribute or the split at HEAD: reports/ is never opened.
    for item in check.CODE_CHECKS:
        assert item.source.startswith(("ac2fb.", "1 / ac2fb.", "the sizes of the two sets"))
    # Every number no code fixes is declared with its reason.
    assert check.PROTOCOL_ONLY == {}


def test_the_check_opens_nothing_under_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    real_open = builtins.open

    def recording(file: Any, *args: Any, **kwargs: Any) -> Any:
        if not isinstance(file, int):  # subprocess wraps its pipes with io.open(fd)
            opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", recording)
    monkeypatch.setattr(io, "open", recording)
    doc = protocol()
    opened.clear()
    assert check.check(doc).ok
    assert opened == [], opened  # the check reads no file at all
    assert cli.main(["protocol", "--check"]) == 0
    inside = [p for p in opened if Path(p).resolve().is_relative_to(ROOT)]
    assert inside and all(Path(p).resolve() == PROTOCOL_FILE.resolve() for p in inside), inside
    assert not any("reports" in Path(p).parts for p in opened), opened


def test_no_module_writes_the_protocol_file() -> None:
    # The protocol is hand-written: no code under src writes protocol/protocol.json.
    package = ROOT / "src" / "ac2fb"
    for path in package.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for line in source.splitlines():
            if "protocol.json" in line and ("write" in line or "dump" in line):
                raise AssertionError(f"{path.relative_to(ROOT)}: {line.strip()}")


# --- the command line --------------------------------------------------------------------------


def test_the_command_line_check_passes_on_the_committed_protocol(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["protocol", "--check"]) == 0
    out = capsys.readouterr().out
    assert "stage in the working tree: design" in out
    assert f"{len(check.CODE_CHECKS)} constants against the code" in out
    assert "every one accounted for" in out and out.rstrip().endswith("protocol: OK")


def test_the_command_line_check_fails_on_a_wrong_protocol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    wrong = put(protocol(), "window.frames", 14)
    wrong = put(wrong, "window.seconds", 1.4)
    wrong = put(wrong, "units.exclusion.gap_frames_at_most", 14)
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(wrong), encoding="utf-8")
    monkeypatch.setattr(cli, "_PROTOCOL", path)
    assert cli.main(["protocol", "--check"]) == 1
    out = capsys.readouterr().out
    assert "window.frames is 14; ac2fb.defence.pressure.INCOMING_WINDOW gives 13" in out
    assert out.rstrip().endswith("protocol: FAILED")


def test_the_command_line_without_check_only_prints_the_stage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["protocol"]) == 0
    out = capsys.readouterr().out
    assert "stage in the working tree: design" in out and "verified" not in out


def test_read_protocol_rejects_a_non_object(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        cli._read_protocol(path)
