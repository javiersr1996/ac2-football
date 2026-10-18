"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from ac2fb import __version__
from ac2fb.protocol.data import (
    GUARDED_CODE,
    HeldOutLocked,
    data_dir,
    guard_status,
    load_split,
)
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
    return parser


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
    return 0


if __name__ == "__main__":
    sys.exit(main())
