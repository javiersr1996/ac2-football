"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from ac2fb import __version__
from ac2fb.protocol.data import GUARDED_CODE, data_dir, guard_status, load_split

__all__ = ["build_parser", "main"]


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
    return parser


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
    return 0


if __name__ == "__main__":
    sys.exit(main())
