"""The two figures: regenerated from ``reports/`` and compared, and every number resolved.

The first half is the acceptance of task 27: the committed files are what the code draws from the
committed reports, byte for byte, and the check of the command says so. The second half does not
trust the code that wrote the sidecars: a small resolver of its own reads each artefact cell a
plotted value or a label number claims to come from, and the SVG text is walked for numbers that
no label of the sidecar owns. Each of those checks is run on a planted fault and must fail.
"""

from __future__ import annotations

import contextlib
import copy
import csv
import io
import json
import re
import shutil
import statistics
from collections.abc import Callable
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pytest

from ac2fb import figures
from ac2fb.cli import main

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
COMMITTED = REPORTS / "figures"
FIXED = re.compile(r"\b[VD]\d\b|[Ll]ayer \d")  # names, not claims: V0, D3, layer 2
SIDECARS = (f"{figures.FIG1}.json", f"{figures.FIG2}.json")
POINTS, NUMBERS = 594, 13


def read_inputs(root: Path) -> dict[str, bytes]:
    return {name: (root / name).read_bytes() for name in figures.INPUTS}


def copy_reports(tmp: Path) -> tuple[Path, Path]:
    """A copy of the inputs and of the committed figures: the real tree is never touched."""
    reports, out = tmp / "reports", tmp / "figures"
    for name in figures.INPUTS:
        (reports / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPORTS / name, reports / name)
    shutil.copytree(COMMITTED, out)
    return reports, out


def replace_in(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) >= 1, f"{old!r} not in {path.name}"
    path.write_bytes(text.replace(old, new, 1).encode("utf-8"))


def bump_amputation_error(path: Path) -> None:
    """Add 0.001 to the mean absolute error of match 1899585, pressure index, band all."""
    lines = path.read_text(encoding="utf-8").split("\n")
    at = next(i for i, ln in enumerate(lines) if ln.startswith("1899585,pressure_index,all,"))
    row = lines[at].split(",")
    row[5] = f"{float(row[5]) + 0.001:.6f}"
    lines[at] = ",".join(row)
    path.write_bytes("\n".join(lines).encode("utf-8"))


def run_check(reports: Path, out: Path) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = main(["figures", "--reports-dir", str(reports), "--out-dir", str(out), "--check"])
    return code, buffer.getvalue()


# --- an independent resolver (not figures.Reports) ---


def cell(ref: str) -> Any:
    name, _, path = ref.partition("#")
    file = REPORTS / name
    if name.endswith(".json"):
        node = json.loads(file.read_text(encoding="utf-8"))
        for part in path.split("/"):
            node = node[part]
        return node
    where, _, column = path.rpartition(":")
    wanted = dict(pair.split("=", 1) for pair in where.split(","))
    with file.open(encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if all(r[k] == v for k, v in wanted.items())]
    assert len(rows) == 1, ref
    return float(rows[0][column])


def apply(formula: str, refs: list[str]) -> float:
    found = [cell(r) for r in refs]
    if formula == "count":
        return float(len(found[0]))
    values = [float(v) for v in found]
    if formula == "value":
        return values[0]
    if formula == "diff":
        return values[1] - values[0]
    if formula == "median":
        return statistics.median(values)
    raise AssertionError(formula)


def sidecar_problems(document: dict[str, Any]) -> list[str]:
    """Every plotted value and label number of a sidecar, resolved against the reports."""
    found: list[str] = []
    for s in document["series"]:
        where = f"{s['panel']}/{s['group']}/{s['match']}/{s['kind']}"
        for p in s["points"]:
            if p["formula"] == "median_of_points":
                mates = [
                    q["value"]
                    for t in document["series"]
                    if (t["panel"], t["group"], t["match"], t["kind"])
                    == (s["panel"], s["group"], s["match"], "match")
                    for q in t["points"]
                ]
                if p["of"] != mates or abs(statistics.median(mates) - p["value"]) > 1e-9:
                    found.append(f"{where}: median of points differs")
            elif abs(apply(p["formula"], p["refs"]) - p["value"]) > 1e-9:
                found.append(f"{where}/{p['x']}: {p['value']} is not {p['formula']} of {p['refs']}")
    for label in document["labels"]:
        leftover, position = label["text"], 0
        for n in label["numbers"]:
            wanted = f"{apply(n['formula'], n['refs']):.{n['decimals']}f}"
            if wanted != n["as"] or abs(float(n["as"]) - n["value"]) > 10 ** -n["decimals"]:
                found.append(f"label {label['text']!r}: {n['as']} is not {wanted} from {n['refs']}")
            at = label["text"].find(n["as"], position)
            if at < 0:
                found.append(f"label {label['text']!r}: {n['as']} is not in the text")
            position = at + len(n["as"])
            leftover = leftover.replace(n["as"], "", 1)
        if re.search(r"\d", FIXED.sub("", leftover)):
            found.append(f"label {label['text']!r}: a number no artefact prints")
    return found


def svg_texts(svg: bytes) -> list[str]:
    tree = ElementTree.fromstring(svg)
    return ["".join(t.itertext()) for t in tree.iter("{http://www.w3.org/2000/svg}text")]


def svg_problems(svg: bytes, document: dict[str, Any], matches: set[str]) -> list[str]:
    """Every text of the SVG that holds a digit is a sidecar label, an axis tick, a category
    named by the sidecar, a match id of the reports or a fixed name (V0, D3, layer 2)."""
    owned = {label["text"] for label in document["labels"]}
    categories = {str(p["x"]) for s in document["series"] for p in s["points"]}
    found = []
    for text in svg_texts(svg):
        if not re.search(r"\d", FIXED.sub("", text)):
            continue
        if text in owned or text in categories or text in matches:
            continue
        if re.fullmatch(r"-?\d+(\.\d+)?", text):  # an axis tick: the scale, not a claim
            continue
        found.append(text)
    return found


def coverage_problems(documents: dict[str, dict[str, Any]]) -> list[str]:
    """Each half draws its 10 matches, each metric its 10 dots, each variant its 10 matches."""
    cal = json.loads((REPORTS / "layer2.json").read_text(encoding="utf-8"))["matches"]
    held = json.loads((REPORTS / "heldout" / "layer2.json").read_text(encoding="utf-8"))["matches"]
    calibration = json.loads((REPORTS / "calibration.json").read_text(encoding="utf-8"))
    found = []
    fig1 = documents[SIDECARS[0]]["series"]
    for panel, n_points in (("a", 6), ("b", 4)):
        for group, matches in (("calibration", cal), ("held-out", held)):
            mine = [s for s in fig1 if s["panel"] == panel and s["group"] == group]
            lines = {s["match"] for s in mine if s["kind"] == "match"}
            if lines != set(matches) or len(matches) != 10:
                found.append(f"{panel}/{group}: matches {sorted(lines)}")
            if any(len(s["points"]) != n_points for s in mine):
                found.append(f"{panel}/{group}: a line without its {n_points} points")
    for panel in ("c", "d"):
        for group in ("calibration", "held-out"):
            dots = [
                s for s in fig1 if (s["panel"], s["group"], s["kind"]) == (panel, group, "match")
            ]
            if len(dots) != 7 or any(len(s["points"]) != 10 for s in dots):
                found.append(f"{panel}/{group}: not 7 metrics of 10 dots")
    fig2 = documents[SIDECARS[1]]["series"]
    ids = {str(m) for m in calibration["matches"]}
    for panel in ("a", "b"):
        for v in ("V0", "V1", "V2"):
            mine = [s for s in fig2 if (s["panel"], s["group"], s["kind"]) == (panel, v, "match")]
            if {p["x"] for s in mine for p in s["points"]} != ids:
                found.append(f"{panel}/{v}: not the 10 calibration matches")
    return found


@pytest.fixture(scope="module")
def built() -> figures.Built:
    return figures.build(read_inputs(REPORTS))


@pytest.fixture(scope="module")
def documents() -> dict[str, dict[str, Any]]:
    return {n: json.loads((COMMITTED / n).read_text(encoding="utf-8")) for n in SIDECARS}


# --- acceptance: regenerate and compare ---


def test_committed_figures_are_what_the_code_draws(built: figures.Built) -> None:
    on_disk = sorted(p.name for p in COMMITTED.iterdir())
    assert sorted(built.files) == sorted(figures.OUTPUTS) == on_disk
    for name, content in built.files.items():
        assert (COMMITTED / name).read_bytes() == content, name
    assert b"\r" not in b"".join(built.files.values())
    assert (built.points, built.labels) == (POINTS, 7)


def test_check_says_what_it_verified_and_writes_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    before = {p.name: p.read_bytes() for p in COMMITTED.iterdir()}
    assert main(["figures", "--check"]) == 0
    out = capsys.readouterr().out
    assert f"verified: 4 files, {POINTS} plotted values and 7 labels" in out
    assert "7 reports read" in out and "figures: OK" in out
    assert {p.name: p.read_bytes() for p in COMMITTED.iterdir()} == before


SIGNED_ZERO = re.compile(rb"(?<![\d.(])-0(?![\d.])")  # rotate(-0 ...) is the same everywhere


def test_no_signed_zero_in_the_svg_which_linux_and_windows_spell_differently(
    built: figures.Built,
) -> None:
    """A rotated marker (the diamond) wrote ``-0`` on Linux and ``0`` on Windows: avoid it."""
    for name in (f"{figures.FIG1}.svg", f"{figures.FIG2}.svg"):
        assert SIGNED_ZERO.search(built.files[name]) is None, name


def test_the_command_writes_the_same_bytes_in_a_new_directory(tmp_path: Path) -> None:
    assert main(["figures", "--out-dir", str(tmp_path / "o")]) == 0
    for name in figures.OUTPUTS:
        assert (tmp_path / "o" / name).read_bytes() == (COMMITTED / name).read_bytes()


# --- the check fails on a planted fault (each one run on a copy) ---


def test_check_fails_when_an_artefact_value_changes(tmp_path: Path) -> None:
    reports, out = copy_reports(tmp_path)
    assert run_check(reports, out)[0] == 0
    replace_in(reports / "calibration.json", '"effect": -0.131169', '"effect": -0.131170')
    code, text = run_check(reports, out)
    assert code == 1 and "fig2_layer3.json: differs" in text and "figures: FAILED" in text


def test_check_fails_when_a_heldout_cell_changes(tmp_path: Path) -> None:
    reports, out = copy_reports(tmp_path)
    bump_amputation_error(reports / "heldout" / "amputation.csv")
    code, text = run_check(reports, out)
    assert code == 1 and "fig1_layer2.json: differs" in text


@pytest.mark.parametrize("name", [figures.OUTPUTS[0], figures.OUTPUTS[3]])
def test_check_fails_when_a_committed_file_is_missing_or_edited(tmp_path: Path, name: str) -> None:
    reports, out = copy_reports(tmp_path)
    (out / name).write_bytes((out / name).read_bytes() + b" ")
    code, text = run_check(reports, out)
    assert code == 1 and f"{name}: differs" in text
    (out / name).unlink()
    code, text = run_check(reports, out)
    assert code == 1 and f"{name}: missing" in text


def test_check_fails_when_a_drawn_number_changes_in_the_svg_only(tmp_path: Path) -> None:
    reports, out = copy_reports(tmp_path)
    replace_in(out / "fig2_layer3.svg", "D3 floor 0.364", "D3 floor 0.365")
    edited = (out / "fig2_layer3.svg").read_bytes()
    code, text = run_check(reports, out)
    assert code == 1 and "fig2_layer3.svg: differs" in text
    assert (out / "fig2_layer3.svg").read_bytes() == edited  # a check writes nothing


def test_a_missing_report_is_refused_not_drawn(tmp_path: Path) -> None:
    reports, out = copy_reports(tmp_path)
    (reports / "heldout" / "layer2.json").unlink()
    code, _ = run_check(reports, out)
    assert code == 2


def label_texts(files: dict[str, bytes]) -> list[str]:
    return [lab["text"] for lab in json.loads(figures.build(files).files[SIDECARS[1]])["labels"]]


def test_the_sentences_of_the_bar_and_the_empty_class_follow_the_artefact() -> None:
    files = read_inputs(REPORTS)
    calibration = json.loads(files["calibration.json"])
    now = label_texts(files)
    assert "V0 passed its own bar" in now[3] and now[3].endswith("the kill is D3 alone.")
    assert "has 0 usable units, with two or more 0: no estimate." in now[4]
    calibration["variants"]["V0"]["bar"]["passed"] = False
    calibration["criteria"]["D5"]["killing"] = ["D3", "D4"]
    calibration["beside"]["V2"]["classes"]["2_or_more"]["used"] = 7
    files["calibration.json"] = json.dumps(calibration).encode()
    planted = label_texts(files)
    assert "V0 failed its own bar" in planted[3] and "the kill is D3 and D4." in planted[3]
    assert "with two or more 7:" in planted[4]


def test_a_match_missing_from_a_variant_is_an_error_not_a_shorter_line() -> None:
    files = read_inputs(REPORTS)
    calibration = json.loads(files["calibration.json"])
    del calibration["beside"]["V2"]["classes"]["0"]["matches"][calibration["matches"][0].__str__()]
    files["calibration.json"] = json.dumps(calibration).encode()
    with pytest.raises(KeyError):
        figures.build(files)


def test_one_changed_cell_moves_one_plotted_value(tmp_path: Path) -> None:
    reports, _ = copy_reports(tmp_path)
    bump_amputation_error(reports / "heldout" / "amputation.csv")
    was = json.loads((COMMITTED / SIDECARS[0]).read_text(encoding="utf-8"))
    now = json.loads(figures.build(read_inputs(reports)).files[SIDECARS[0]])
    assert was["series"] != now["series"] and was["labels"] == now["labels"]
    moved = [
        (a["panel"], a["group"], a["match"], pa["x"], pa["value"], pb["value"])
        for a, b in zip(was["series"], now["series"], strict=True)
        for pa, pb in zip(a["points"], b["points"], strict=True)
        if pa != pb
    ]
    assert moved[0][:4] == ("d", "held-out", "pressure_index", "1899585")
    assert abs(moved[0][5] - moved[0][4] - 0.001) < 1e-9 and len(moved) <= 2
    # the resolver reads the unchanged reports: it agrees with the old sidecar, not the new one
    assert sidecar_problems(was) == [] and sidecar_problems(now) != []


# --- every number resolves, with a resolver that is not the code's ---


def test_every_plotted_value_and_label_number_resolves(
    documents: dict[str, dict[str, Any]],
) -> None:
    for name, document in documents.items():
        assert sidecar_problems(document) == [], name
    points = sum(len(s["points"]) for d in documents.values() for s in d["series"])
    numbers = sum(len(label["numbers"]) for d in documents.values() for label in d["labels"])
    assert (points, numbers) == (POINTS, NUMBERS)


def test_each_panel_reads_the_cell_it_names(documents: dict[str, dict[str, Any]]) -> None:
    """The column and the stratum of every cell behind a panel, not only that it resolves."""
    shapes = {
        "a": r"(heldout/)?layer2\.json#matches/\d+/ball_distance/\w+/detected",
        "b": r"(heldout/)?layer2\.json#matches/\d+/reacquisition/by_band/\w+/frame_share",
        "c": r"(heldout/)?reliability\.csv#match_id=\d+,metric=\w+,ball_stratum=all,"
        r"variant=V[01]:mean",
        "d": r"(heldout/)?amputation\.csv#match_id=\d+,metric=\w+,band=all:mean_abs_error",
    }
    seen = dict.fromkeys(shapes, 0)
    for s in documents[SIDECARS[0]]["series"]:
        for p in s["points"]:
            for ref in p.get("refs", []):
                assert re.fullmatch(shapes[s["panel"]], ref), ref
                seen[s["panel"]] += 1
                held = ref.startswith("heldout/")
                assert held == (s["group"] == "held-out"), ref
    assert all(n > 0 for n in seen.values())
    for s in documents[SIDECARS[1]]["series"]:
        column = {"a": "effect|t", "b": "pretrend|pretrend_sd"}[s["panel"]]
        for p in s["points"]:
            assert re.fullmatch(rf"calibration\.json#.*/({column})", p["refs"][0]), p["refs"]
            where = {"V0": "variants/V0/", "V1": "variants/V1/", "V2": "beside/V2/classes/0/"}
            assert where[s["group"]] in p["refs"][0], p["refs"]


def category_problems(document: dict[str, Any]) -> list[str]:
    """The numbers of an axis label of panels a and b are those of the key of its cell."""
    found = []
    for s in document["series"]:
        if s["panel"] not in ("a", "b"):
            continue
        for p in s["points"]:
            key = re.search(r"/(ball_distance|by_band)/([^/]+)", p["refs"][0])
            assert key, p["refs"]
            wanted = [int(n) for n in re.findall(r"\d+", key.group(2))]
            drawn = [int(n) for n in re.findall(r"\d+", p["x"])]
            if wanted != drawn:
                found.append(f"{p['x']!r} is not {key.group(2)}")
    return found


def test_each_axis_label_carries_the_numbers_of_its_key(built: figures.Built) -> None:
    """On what the code draws now, so a label typed apart from its key fails even if the
    committed files were regenerated from it."""
    document = json.loads(built.files[SIDECARS[0]])
    assert category_problems(document) == []
    for edit in (("5-10", "5-15"), ("up to 1 s", "up to 2 s"), ("40+", "45+")):
        planted = mutated(
            document,
            lambda d, e=edit: [
                p.update(x=e[1]) for s in d["series"] for p in s["points"] if p["x"] == e[0]
            ],
        )
        assert category_problems(planted) != [], edit


def test_the_sidecars_hold_every_match_of_both_halves(documents: dict[str, dict[str, Any]]) -> None:
    assert coverage_problems(documents) == []


def test_the_svg_has_no_number_without_an_artefact(documents: dict[str, dict[str, Any]]) -> None:
    calibration = json.loads((REPORTS / "calibration.json").read_text(encoding="utf-8"))
    ids = {str(m) for m in calibration["matches"]}
    for stem, name in ((figures.FIG1, SIDECARS[0]), (figures.FIG2, SIDECARS[1])):
        svg = (COMMITTED / f"{stem}.svg").read_bytes()
        assert svg_problems(svg, documents[name], ids) == [], stem
        drawn = set(svg_texts(svg))
        assert all(label["text"] in drawn for label in documents[name]["labels"]), stem


def test_the_death_is_stated_because_the_protocol_says_so() -> None:
    protocol = json.loads((ROOT / "protocol" / "protocol.json").read_text(encoding="utf-8"))
    assert protocol["stage"] == "dead" and protocol["verdict"]["heldout_read_for_layer3"] is False
    texts = svg_texts((COMMITTED / f"{figures.FIG2}.svg").read_bytes())
    assert any(t.startswith("No held-out reading for layer 3") for t in texts)


# --- the checks above, each on a planted fault ---


def mutated(document: dict[str, Any], change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    planted = copy.deepcopy(document)
    change(planted)
    return planted


def plant_value(d: dict[str, Any]) -> None:
    d["series"][0]["points"][0]["value"] += 0.001


def plant_ref(d: dict[str, Any]) -> None:
    refs = d["series"][0]["points"][0]["refs"]
    refs[0] = refs[0].replace("00_05", "05_10")


def plant_median_tick(d: dict[str, Any]) -> None:
    tick = next(s for s in d["series"] if s["panel"] == "c" and s["kind"] == "median")
    tick["points"][0]["value"] += 0.001


def plant_label_number(d: dict[str, Any]) -> None:
    d["labels"][0]["numbers"][0]["as"] = "11"
    d["labels"][0]["text"] = d["labels"][0]["text"].replace("10", "11")


def plant_label_rounding(d: dict[str, Any]) -> None:
    d["labels"][-1]["numbers"][0]["decimals"] = 1


def plant_typed_number(d: dict[str, Any]) -> None:
    d["labels"][0]["text"] += " 7"


@pytest.mark.parametrize(
    ("plant", "fig"),
    [
        (plant_value, 0),
        (plant_ref, 0),
        (plant_median_tick, 0),
        (plant_label_number, 0),
        (plant_label_rounding, 1),
        (plant_typed_number, 0),
        (plant_value, 1),
    ],
)
def test_the_resolver_flags_a_planted_fault(
    documents: dict[str, dict[str, Any]], plant: Callable[[dict[str, Any]], None], fig: int
) -> None:
    assert sidecar_problems(mutated(documents[SIDECARS[fig]], plant)) != []


def test_coverage_flags_a_dropped_match_a_dropped_variant_and_a_short_line(
    documents: dict[str, dict[str, Any]],
) -> None:
    def without(fig: int, drop: Callable[[dict[str, Any]], bool]) -> dict[str, dict[str, Any]]:
        planted = copy.deepcopy(documents)
        planted[SIDECARS[fig]]["series"] = [
            s for s in planted[SIDECARS[fig]]["series"] if not drop(s)
        ]
        return planted

    held_match = lambda s: (s["panel"], s["group"], s["match"]) == ("a", "held-out", "1899585")  # noqa: E731
    v2 = lambda s: s["group"] == "V2" and s["panel"] == "a" and s["kind"] == "match"  # noqa: E731
    assert coverage_problems(without(0, held_match)) != []
    assert coverage_problems(without(1, v2)) != []
    thinned = copy.deepcopy(documents)
    thinned[SIDECARS[0]]["series"][0]["points"].pop()
    assert coverage_problems(thinned) != []


def test_the_svg_walk_flags_a_typed_number_and_a_dropped_label(
    documents: dict[str, dict[str, Any]],
) -> None:
    svg = (COMMITTED / f"{figures.FIG2}.svg").read_bytes()
    document = documents[SIDECARS[1]]
    ids = {"1874553"}
    typed = svg.replace(b"D3 floor 0.364", b"D3 floor 0.400")
    assert svg_problems(typed, document, ids) == ["D3 floor 0.400"]
    dropped = mutated(document, lambda d: d["labels"].pop(0))
    assert "D3 floor 0.364" in svg_problems(svg, dropped, ids)
