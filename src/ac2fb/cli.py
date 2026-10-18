"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from ac2fb import __version__
from ac2fb.defence.probe_s1 import write_s1_report
from ac2fb.defence.probe_s2 import write_s2_report
from ac2fb.defence.probe_s3 import write_s3_report
from ac2fb.protocol.data import (
    GUARDED_CODE,
    HeldOutLocked,
    data_dir,
    guard_status,
    load_split,
)
from ac2fb.reliability.cadence import write_cadence_report
from ac2fb.reliability.long import write_long
from ac2fb.reliability.report import layer2_report, write_report

__all__ = ["build_parser", "main"]

_REPORTS = Path(__file__).resolve().parents[2] / "reports"


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
            "Without --match, the calibration matches."
        ),
    )
    layer2.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    layer2.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where layer2.json goes (default: reports/)",
    )
    cadence = commands.add_parser(
        "cadence",
        help="write reports/probe_cadence.json: gaps between kinks of detected players",
        description=(
            "Cadence probe, descriptive: how often detected paths bend, and the shortest "
            "admissible window. Reads through the guarded door. Without --match, the "
            "calibration matches."
        ),
    )
    cadence.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    cadence.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where probe_cadence.json goes (default: reports/)",
    )
    s1 = commands.add_parser(
        "s1",
        help="write reports/probe_s1.json: the pressure index at the reception against the label",
        description=(
            "Probe S1 (candidate C1), descriptive: does the geometric pressure index grow with "
            "the provider's pressure label, how much of it extrapolated rivals carry, and the "
            "incoming-ball strata. Reads through the guarded door. Without --match, the "
            "calibration matches."
        ),
    )
    s1.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    s1.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where probe_s1.json goes (default: reports/)",
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
        ),
    )
    s2.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    s2.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where probe_s2.json goes (default: reports/)",
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
        ),
    )
    s3.add_argument(
        "--match", type=int, action="append", metavar="ID", help="native match id (repeatable)"
    )
    s3.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS,
        help="where probe_s3.json goes (default: reports/)",
    )
    return parser


def _s3(match_ids: Sequence[int] | None, reports_dir: Path) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        path = write_s3_report(ids, reports_dir)
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


def _s2(match_ids: Sequence[int] | None, reports_dir: Path) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        path = write_s2_report(ids, reports_dir)
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


def _s1(match_ids: Sequence[int] | None, reports_dir: Path) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        path = write_s1_report(ids, reports_dir)
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


def _cadence(match_ids: Sequence[int] | None, reports_dir: Path) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        path = write_cadence_report(ids, reports_dir)
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


def _layer2(match_ids: Sequence[int] | None, reports_dir: Path) -> int:
    ids = list(match_ids) if match_ids else list(load_split().calibration)
    try:
        longs = write_long(ids)
        path = write_report(layer2_report(ids), reports_dir)
    except HeldOutLocked as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {len(longs)} long Parquet file(s) under {longs[0].parent}")
    print(f"wrote {path}")
    return 0


def _status() -> int:
    split = load_split()
    status = guard_status()
    print(f"data: {data_dir()}")
    print(f"split at HEAD: {len(split.calibration)} calibration, {len(split.heldout)} held-out")
    print(f"HEAD: {status.head}")
    print(f"stage at HEAD: {status.stage}")
    print(f"code_tree_sha of {' and '.join(GUARDED_CODE)} at HEAD: {status.code_tree_sha}")
    print(f"code_tree_sha frozen in the protocol: {status.frozen_code_tree_sha}")
    print(f"working tree: {'clean' if not status.dirty else f'{len(status.dirty)} path(s)'}")
    print("held-out: open" if status.open else "held-out: locked")
    for reason in status.reasons:
        print(f"  - {reason}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        return _status()
    if args.command == "layer2":
        return _layer2(args.match, args.reports_dir)
    if args.command == "cadence":
        return _cadence(args.match, args.reports_dir)
    if args.command == "s1":
        return _s1(args.match, args.reports_dir)
    if args.command == "s2":
        return _s2(args.match, args.reports_dir)
    if args.command == "s3":
        return _s3(args.match, args.reports_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
