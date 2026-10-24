"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ac2fb import __version__, figures
from ac2fb.defence import calibration, design, power, probe_s1, probe_s2, probe_s3
from ac2fb.defence.calibration import write_calibration_report
from ac2fb.defence.design import write_design_report
from ac2fb.defence.power import probe_verdicts, write_power_report
from ac2fb.defence.probe_s1 import write_s1_report
from ac2fb.defence.probe_s2 import write_s2_report
from ac2fb.defence.probe_s3 import write_s3_report
from ac2fb.protocol import check as protocol_check
from ac2fb.protocol.data import (
    GUARDED_CODE,
    LAYER2_PATH,
    HeldOutLocked,
    data_dir,
    guard_status,
    load_split,
    read_heldout,
)
from ac2fb.reliability import amputate, cadence, report, table
from ac2fb.reliability.cadence import write_cadence_report
from ac2fb.reliability.long import write_long
from ac2fb.reliability.reading import LAYER2_READS
from ac2fb.reliability.report import layer2_report, write_report

__all__ = ["build_parser", "main"]

_REPORTS = Path(__file__).resolve().parents[2] / "reports"
_PROTOCOL = Path(__file__).resolve().parents[2] / "protocol" / "protocol.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ac2fb",
        description="Football entry to the SkillCorner Analytics Cup 2.0.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="command")
    commands.add_parser(
        "status",
        help="print the split and whether the held-out matches are open, and why not",
        description="Reads git only, never the data.",
    )
    layer2 = commands.add_parser(
        "layer2",
        help="write the long Parquet with gap_len and reports/layer2.json for the given matches",
        description=(
            "Layer 2, descriptive: per match, how much of the tracking the camera saw. "
            "Reads through the guarded door, so a held-out match is refused while it is locked. "
            "Without --match, the calibration matches. --check recomputes the report and "
            "compares every value with the file, and says how many it verified (exit 1 if any "
            "differs); it writes nothing, not even the long Parquet."
        ),
    )
    layer2.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    layer2.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where layer2.json goes, or is read from with --check (default: reports/)",
    )
    layer2.add_argument(
        "--check", action="store_true", help="compare the file with a recomputation, write nothing"
    )
    reliability = commands.add_parser(
        "reliability",
        help="write reports/reliability.csv: each metric in V0, V1 and V2 for the given matches",
        description=(
            "Layer 2, descriptive: per match and metric (local pressure, nearest rival, line "
            "height, block width, length and area, the line's reaction to the incoming ball), "
            "the metric in V0, V1 and V2 with the extrapolated fraction behind it and its "
            "gap_len. Reads through the guarded door. Without --match, the calibration "
            "matches. --check recomputes the rows and compares every cell with the file, and "
            "says how many it verified (exit 1 if any differs)."
        ),
    )
    reliability.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    reliability.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where reliability.csv goes, or is read from with --check (default: reports/)",
    )
    reliability.add_argument(
        "--check", action="store_true", help="compare the file with a recomputation, write nothing"
    )
    amputation = commands.add_parser(
        "amputation",
        help="write reports/amputation.csv: each metric's error when seen players are hidden",
        description=(
            "Layer 2, the amputation reference: in the units where a metric's players were all "
            "detected, hide them as the camera hides players at their distance from the ball, "
            "with gaps copied from the match's real ones, fill each gap by a straight line "
            "between the detections on either side, and report the metric's error by gap band "
            "and match. Reads through the guarded door. Without --match, the calibration "
            "matches. --check recomputes the rows and compares every cell with the file, and "
            "says how many it verified (exit 1 if any differs)."
        ),
    )
    amputation.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    amputation.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where amputation.csv goes, or is read from with --check (default: reports/)",
    )
    amputation.add_argument(
        "--check", action="store_true", help="compare the file with a recomputation, write nothing"
    )
    figs = commands.add_parser(
        "figures",
        help="draw the two figures of the README from reports/ into reports/figures/",
        description=(
            "Figure 1 (layer 2, the 20 matches) and figure 2 (layer 3, calibration: it died "
            "before any held-out reading), each an SVG and a sidecar JSON with every plotted "
            "value and label number and the artefact cell it comes from. Reads only the "
            "committed files of reports/ and reports/heldout/. --check draws them again and "
            "compares every byte with the committed files (exit 1 if any differs); it writes "
            "nothing."
        ),
    )
    figs.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where the reports are read from (default: reports/)",
    )
    figs.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="where the figures go, or are read from with --check (default: REPORTS_DIR/figures)",
    )
    figs.add_argument(
        "--check", action="store_true", help="compare the files with a recomputation, write nothing"
    )
    cadence = commands.add_parser(
        "cadence",
        help="write reports/probe_cadence.json: gaps between kinks of detected players",
        description=(
            "Cadence probe, descriptive: how often detected paths bend, and the shortest "
            "admissible window. Reads through the guarded door. Without --match, the "
            "calibration matches."
            " --check recomputes the report and compares every value with the file, says "
            "how many it verified and that the held-out half is not among them (PARTIAL "
            "n/20), and exits 1 if any differs; it writes nothing."
        ),
    )
    cadence.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    cadence.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where probe_cadence.json goes, or is read from with --check (default: reports/)",
    )
    cadence.add_argument(
        "--check", action="store_true", help="compare the file with a recomputation, write nothing"
    )
    s1 = commands.add_parser(
        "s1",
        help="write reports/probe_s1.json: the pressure index at the reception against the label",
        description=(
            "Probe S1 (candidate C1), descriptive: does the geometric pressure index grow with "
            "the provider's pressure label, how much of it extrapolated rivals carry, and the "
            "incoming-ball strata. Reads through the guarded door. Without --match, the "
            "calibration matches."
            " --check recomputes the report and compares every value with the file, says "
            "how many it verified and that the held-out half is not among them (PARTIAL "
            "n/20), and exits 1 if any differs; it writes nothing."
        ),
    )
    s1.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    s1.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where probe_s1.json goes, or is read from with --check (default: reports/)",
    )
    s1.add_argument(
        "--check", action="store_true", help="compare the file with a recomputation, write nothing"
    )
    s2 = commands.add_parser(
        "s2",
        help="write reports/probe_s2.json: the last line at the reception and its pre-trend",
        description=(
            "Probe S2 (candidate C2), descriptive: does the last line agree with the provider's "
            "and follow the incoming ball, how large is its pre-trend within incoming-ball "
            "strata, and how many receptions keep the whole line in view. No position after "
            "the reception enters a figure. Reads through the guarded door. Without --match, the "
            "calibration matches."
            " --check recomputes the report and compares every value with the file, says "
            "how many it verified and that the held-out half is not among them (PARTIAL "
            "n/20), and exits 1 if any differs; it writes nothing."
        ),
    )
    s2.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    s2.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where probe_s2.json goes, or is read from with --check (default: reports/)",
    )
    s2.add_argument(
        "--check", action="store_true", help="compare the file with a recomputation, write nothing"
    )
    s3 = commands.add_parser(
        "s3",
        help="write reports/probe_s3.json: the block's width and length against the provider's",
        description=(
            "Probe S3 (candidate C3), descriptive: which definition of the block reproduces the "
            "provider's width and length at the start of a phase, how much of the players that "
            "fix its ends the camera saw, and whether the block looks wider when more of it is "
            "seen. Nothing after the phase's start frame enters a figure. Reads through the "
            "guarded door. Without --match, the calibration matches."
            " --check recomputes the report and compares every value with the file, says "
            "how many it verified and that the held-out half is not among them (PARTIAL "
            "n/20), and exits 1 if any differs; it writes nothing."
        ),
    )
    s3.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    s3.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where probe_s3.json goes, or is read from with --check (default: reports/)",
    )
    s3.add_argument(
        "--check", action="store_true", help="compare the file with a recomputation, write nothing"
    )
    power = commands.add_parser(
        "power",
        help="write reports/power.json: the power of the calibration bar per live candidate",
        description=(
            "Task 17: simulates the protocol's calibration bar on the real design of each "
            "candidate alive after its probe (verdicts read from the committed probe reports), "
            "with the within-possession correlation of the statistic before the instant t. "
            "Computes no outcome. Reads through the guarded door. Without --match, the "
            "calibration matches."
            " --check recomputes the report and compares every value with the file, says "
            "how many it verified and that the held-out half is not among them (PARTIAL "
            "n/20), and exits 1 if any differs; it writes nothing."
        ),
    )
    power.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    power.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where power.json goes, or is read from with --check (default: reports/)",
    )
    power.add_argument(
        "--check", action="store_true", help="compare the file with a recomputation, write nothing"
    )
    design = commands.add_parser(
        "design",
        help="write reports/design.json: the protocol's units, groups, exclusions and pre-trend",
        description=(
            "Task 19: the protocol's design on the given matches before any outcome: units "
            "after the window-overlap exclusion, groups by the index cut, V1, the correlation "
            "of the statistic before t, the MDE80 and the pooled pre-trend in sd and metres. "
            "Computes no outcome. Reads through the guarded door. Without --match, the "
            "calibration matches."
            " --check recomputes the report and compares every value with the file, says "
            "how many it verified and that the held-out half is not among them (PARTIAL "
            "n/20), and exits 1 if any differs; it writes nothing."
        ),
    )
    design.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    design.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where design.json goes, or is read from with --check (default: reports/)",
    )
    design.add_argument(
        "--check", action="store_true", help="compare the file with a recomputation, write nothing"
    )
    calibration = commands.add_parser(
        "calibration",
        help="write reports/calibration.json: effects, null, bars and the verdict D1 to D5",
        description=(
            "Task 21: the calibration half judged by the protocol: the design before any "
            "outcome, then the outcomes, the effect of V0 and V1 per match with its permutation "
            "p and the calibration bar, V2 and the ball-detected units beside them, and D1 to "
            "D5, mechanical. Reads through the guarded door. Without --match, the calibration "
            "matches."
            " --check recomputes the report and compares every value with the file, says "
            "how many it verified and that the held-out half is not among them (PARTIAL "
            "n/20), and exits 1 if any differs; it writes nothing."
        ),
    )
    calibration.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    calibration.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where calibration.json goes, or is read from with --check (default: reports/)",
    )
    calibration.add_argument(
        "--check", action="store_true", help="compare the file with a recomputation, write nothing"
    )
    protocol = commands.add_parser(
        "protocol",
        help="print the protocol's stage and, with --check, validate protocol/protocol.json",
        description=(
            "The protocol of layer 3 (protocol/protocol.json, working tree). --check validates "
            "its schema, its internal coherence and that every constant the code fixes equals "
            "the one written there, and says how much it verified; exit 1 with the problems "
            "listed. Reads the protocol file and git, never the data nor a report."
        ),
    )
    protocol.add_argument("--check", action="store_true", help="validate the protocol")
    heldout = commands.add_parser(
        "heldout",
        help="the single reading of the held-out matches, for layer 2 only",
        description=f"Layer 3 is dead (D5); the held-out is read once, under {LAYER2_PATH}.",
    )
    heldout_commands = heldout.add_subparsers(
        dest="heldout_command", metavar="command", required=True
    )
    read = heldout_commands.add_parser(
        "read",
        help="commit the reading, then run the layer 2 commands on the held-out matches",
        description=(
            f"Irreversible. From stage frozen of {LAYER2_PATH}: checks that layer 3 is dead, "
            "that HEAD holds the frozen code with a clean tree and that the installed packages "
            "are those of uv.lock; commits the reading (stage read) before computing any "
            f"figure; then runs the commands {LAYER2_PATH} lists ({', '.join(LAYER2_READS)}) on "
            "the held-out matches and nothing else. From stage read it reproduces the reading "
            "without a new commit. Exit 2 with the reasons when refused."
        ),
    )
    read.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS / "heldout",
        help="where the held-out artefacts go (default: reports/heldout/)",
    )
    return parser


def _heldout_read(reports_dir: Path) -> int:
    try:
        reading = read_heldout(reports_dir)
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:  # a git or command failure; `ac2fb status` says if it was recorded
        print(f"failed: {exc}", file=sys.stderr)
        return 1
    verb = "reproduced the reading of" if reading.reproduced else "read"
    print(f"{verb} {len(reading.heldout)} held-out matches at {reading.commit}")
    print(f"frozen at {reading.frozen_commit}")
    for path in reading.written:
        print(f"wrote {path}")
    return 0


_PROBE_REPORTS = ("probe_s1.json", "probe_s2.json", "probe_s3.json")


def _probe_verdicts(probes_dir: Path) -> dict[str, bool]:
    """The one place that reads a file on the way to ``power.json``: the three probe reports."""
    reports = {
        name: json.loads((probes_dir / name).read_text(encoding="utf-8")) for name in _PROBE_REPORTS
    }
    return probe_verdicts(reports)


def _read_protocol(path: Path) -> dict[str, Any]:
    """The one place that reads the protocol file: the working-tree copy, for its check."""
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(protocol, dict):
        raise ValueError(f"{path} does not hold a JSON object")
    return protocol


def _protocol(do_check: bool) -> int:
    protocol = _read_protocol(_PROTOCOL)
    status = guard_status()
    print(f"protocol: {_PROTOCOL}")
    print(f"stage in the working tree: {protocol.get('stage')}; at HEAD: {status.protocol_stage}")
    print(f"candidate: {protocol.get('candidate')}; written: {protocol.get('date_written')}")
    if not do_check:
        return 0
    report = protocol_check.check(protocol)
    print(
        f"verified: {report.schema_fields} schema fields, {report.coherence_rules} coherence "
        f"rules, {report.code_constants} constants against the code, {report.derived_numbers} "
        f"derived numbers, {report.protocol_only_numbers} protocol-only numbers; "
        f"{report.numeric_leaves} numeric fields in all, every one accounted for"
        if report.ok
        else f"problems: {len(report.problems)}"
    )
    for problem in report.problems:
        print(f"  - {problem}")
    print("protocol: OK" if report.ok else "protocol: FAILED")
    return 0 if report.ok else 1


def _coverage(ids: Sequence[int], *, heldout_artefact: bool) -> str | None:
    """The line that says what share of the 20 matches a ``--check`` verified, if not all."""
    split = load_split()
    total = len(split.calibration) + len(split.heldout)
    if len(ids) >= total:
        return None
    rest = (
        f"the {len(split.heldout)} held-out ones reproduce only from the reading commit, in a "
        "git worktree (full-build.yml)"
        if heldout_artefact
        else "this artefact has no held-out half: layer 3 died before any held-out reading"
    )
    return f"PARTIAL {len(ids)}/{total} matches: {rest}"


def _verdict(
    name: str, result: report.JsonCheck, ids: Sequence[int], *, heldout_artefact: bool = False
) -> int:
    """Print what a JSON ``--check`` verified, its problems and its PARTIAL line; the exit code."""
    print(f"verified: {result.values} values, {len(ids)} matches")
    for problem in result.problems:
        print(f"  - {problem}")
    partial = _coverage(ids, heldout_artefact=heldout_artefact)
    if partial:
        print(partial)
    print(f"{name}: OK" if result.ok else f"{name}: FAILED")
    return 0 if result.ok else 1


def _calibration(match_ids: Sequence[int] | None, reports_dir: Path, do_check: bool) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        if not do_check:
            print(f"wrote {write_calibration_report(ids, reports_dir)}")
            return 0
        result = calibration.check(ids, _committed(reports_dir / calibration.REPORT_NAME))
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return _verdict("calibration", result, ids)


def _design(match_ids: Sequence[int] | None, reports_dir: Path, do_check: bool) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        if not do_check:
            print(f"wrote {write_design_report(ids, reports_dir)}")
            return 0
        result = design.check(ids, _committed(reports_dir / design.REPORT_NAME))
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return _verdict("design", result, ids)


def _power(match_ids: Sequence[int] | None, reports_dir: Path, do_check: bool) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        if not do_check:
            print(f"wrote {write_power_report(ids, reports_dir, _probe_verdicts(_REPORTS))}")
            return 0
        # the probe reports beside the file checked, so a probe verdict edited there is seen
        absent = [name for name in _PROBE_REPORTS if not (reports_dir / name).is_file()]
        if absent:
            print(f"missing in {reports_dir}: {', '.join(absent)}", file=sys.stderr)
            return 2
        alive = _probe_verdicts(reports_dir)
        result = power.check(ids, alive, _committed(reports_dir / power.REPORT_NAME))
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return _verdict("power", result, ids)


def _s3(match_ids: Sequence[int] | None, reports_dir: Path, do_check: bool) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        if not do_check:
            print(f"wrote {write_s3_report(ids, reports_dir)}")
            return 0
        result = probe_s3.check(ids, _committed(reports_dir / probe_s3.REPORT_NAME))
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return _verdict("s3", result, ids)


def _s2(match_ids: Sequence[int] | None, reports_dir: Path, do_check: bool) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        if not do_check:
            print(f"wrote {write_s2_report(ids, reports_dir)}")
            return 0
        result = probe_s2.check(ids, _committed(reports_dir / probe_s2.REPORT_NAME))
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return _verdict("s2", result, ids)


def _s1(match_ids: Sequence[int] | None, reports_dir: Path, do_check: bool) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        if not do_check:
            print(f"wrote {write_s1_report(ids, reports_dir)}")
            return 0
        result = probe_s1.check(ids, _committed(reports_dir / probe_s1.REPORT_NAME))
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return _verdict("s1", result, ids)


def _cadence(match_ids: Sequence[int] | None, reports_dir: Path, do_check: bool) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        if not do_check:
            print(f"wrote {write_cadence_report(ids, reports_dir)}")
            return 0
        result = cadence.check(ids, _committed(reports_dir / cadence.REPORT_NAME))
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return _verdict("cadence", result, ids)


def _layer2(match_ids: Sequence[int] | None, reports_dir: Path, do_check: bool) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        if do_check:
            result = report.check(ids, _committed(reports_dir / report.REPORT_NAME))
        else:
            longs = write_long(ids)
            path = write_report(layer2_report(ids), reports_dir)
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    if not do_check:
        print(f"wrote {len(longs)} long Parquet file(s) under {longs[0].parent}")
        print(f"wrote {path}")
        return 0
    print(f"verified: {result.values} values, {result.matches} matches")
    for problem in result.problems:
        print(f"  - {problem}")
    partial = _coverage(ids, heldout_artefact=True)
    if partial:
        print(partial)
    print("layer2: OK" if result.ok else "layer2: FAILED")
    return 0 if result.ok else 1


def _committed(path: Path) -> bytes | None:
    """The one place that reads a committed report (layer2.json or a CSV), for its check."""
    return path.read_bytes() if path.exists() else None


def _reliability(match_ids: Sequence[int] | None, reports_dir: Path, do_check: bool) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        if not do_check:
            print(f"wrote {table.write_table(ids, reports_dir)}")
            return 0
        result = table.check(ids, _committed(reports_dir / table.REPORT_NAME))
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(f"verified: {result.rows} rows, {result.cells} cells, {result.matches} matches")
    for problem in result.problems:
        print(f"  - {problem}")
    partial = _coverage(ids, heldout_artefact=True)
    if partial:
        print(partial)
    print("reliability: OK" if result.ok else "reliability: FAILED")
    return 0 if result.ok else 1


def _amputation(match_ids: Sequence[int] | None, reports_dir: Path, do_check: bool) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        if not do_check:
            print(f"wrote {amputate.write_table(ids, reports_dir)}")
            return 0
        result = amputate.check(ids, _committed(reports_dir / amputate.REPORT_NAME))
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(f"verified: {result.rows} rows, {result.cells} cells, {result.matches} matches")
    for problem in result.problems:
        print(f"  - {problem}")
    partial = _coverage(ids, heldout_artefact=True)
    if partial:
        print(partial)
    print("amputation: OK" if result.ok else "amputation: FAILED")
    return 0 if result.ok else 1


def _figures(reports_dir: Path, out_dir: Path, do_check: bool) -> int:
    sources = {name: _committed(reports_dir / name) for name in figures.INPUTS}
    absent = [name for name, content in sources.items() if content is None]
    if absent:
        print(f"missing in {reports_dir}: {', '.join(absent)}", file=sys.stderr)
        return 2
    files = {name: content for name, content in sources.items() if content is not None}
    if not do_check:
        out_dir.mkdir(parents=True, exist_ok=True)
        built = figures.build(files)
        for name, content in built.files.items():
            (out_dir / name).write_bytes(content)
            print(f"wrote {out_dir / name}")
        return 0
    result = figures.check(files, {name: _committed(out_dir / name) for name in figures.OUTPUTS})
    print(
        f"verified: {result.files} of {len(figures.OUTPUTS)} files found, {result.points} plotted "
        f"values and {result.labels} labels, each from its artefact cell, "
        f"{len(files)} reports read"
    )
    for problem in result.problems:
        print(f"  - {problem}")
    print("figures: OK" if result.ok else "figures: FAILED")
    return 0 if result.ok else 1


def _status() -> int:
    split = load_split()
    status = guard_status()
    print(f"data: {data_dir()}")
    print(f"split at HEAD: {len(split.calibration)} calibration, {len(split.heldout)} held-out")
    print(f"HEAD: {status.head}")
    print(f"stage of protocol/protocol.json (layer 3) at HEAD: {status.protocol_stage}")
    print(f"stage of {LAYER2_PATH} at HEAD: {status.stage}")
    print(f"code_tree_sha of {' and '.join(GUARDED_CODE)} at HEAD: {status.code_tree_sha}")
    print(f"code_tree_sha frozen in {LAYER2_PATH}: {status.frozen_code_tree_sha}")
    print(f"working tree: {'clean' if not status.dirty else f'{len(status.dirty)} path(s)'}")
    print("held-out: open inside `ac2fb heldout read` only" if status.open else "held-out: locked")
    for reason in status.reasons:
        print(f"  - {reason}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        return _status()
    if args.command == "layer2":
        return _layer2(args.match, args.reports_dir, args.check)
    if args.command == "reliability":
        return _reliability(args.match, args.reports_dir, args.check)
    if args.command == "amputation":
        return _amputation(args.match, args.reports_dir, args.check)
    if args.command == "figures":
        return _figures(args.reports_dir, args.out_dir or args.reports_dir / "figures", args.check)
    if args.command == "cadence":
        return _cadence(args.match, args.reports_dir, args.check)
    if args.command == "s1":
        return _s1(args.match, args.reports_dir, args.check)
    if args.command == "s2":
        return _s2(args.match, args.reports_dir, args.check)
    if args.command == "s3":
        return _s3(args.match, args.reports_dir, args.check)
    if args.command == "power":
        return _power(args.match, args.reports_dir, args.check)
    if args.command == "design":
        return _design(args.match, args.reports_dir, args.check)
    if args.command == "calibration":
        return _calibration(args.match, args.reports_dir, args.check)
    if args.command == "protocol":
        return _protocol(args.check)
    if args.command == "heldout" and args.heldout_command == "read":
        return _heldout_read(args.reports_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
