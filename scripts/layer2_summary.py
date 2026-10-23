"""Per-match figures of layer 2 in one reports directory, as Markdown (task 24).

Usage: ``uv run python scripts/layer2_summary.py reports`` (calibration) or ``reports/heldout``
(the single reading). Reads ``reliability.csv`` and ``amputation.csv`` and nothing else: the
figures the plan records come from here, so anyone can print them again.
"""

from __future__ import annotations

import csv
import statistics
import sys
from pathlib import Path

PAIRS = list(
    zip(
        ["press", "rival", "line", "react", "width", "length", "area"],
        [
            "pressure_index",
            "nearest_rival_m",
            "line_height_m",
            "line_reaction_m",
            "block_width_m",
            "block_length_m",
            "block_area_m2",
        ],
        strict=True,
    )
)
BANDS = ["le_1s", "1_5s", "5_20s", "gt_20s"]  # `none` (no gap) and `all` left out


def rows(path: Path) -> dict[tuple[str, ...], dict[str, str]]:
    """The CSV keyed by its first three columns (match, metric, stratum or band) and variant."""
    found: dict[tuple[str, ...], dict[str, str]] = {}
    for row in csv.DictReader(path.read_text(encoding="utf-8").splitlines()):
        key = (row["match_id"], row["metric"], row.get("ball_stratum") or row["band"])
        found[(*key, row.get("variant", ""))] = row
    return found


def num(row: dict[str, str] | None, column: str) -> float | None:
    return None if row is None or row[column] == "" else float(row[column])


def spread(values: list[float | None]) -> str:
    v = sorted(x for x in values if x is not None)
    return f"{v[0]:.3f} / {statistics.median(v):.3f} / {v[-1]:.3f}" if v else "-"


def table(title: str, cells: dict[str, list[float | None]], fmt: str) -> None:
    print(f"\n{title}\n")
    print("| match | " + " | ".join(s for s, _ in PAIRS) + " |")
    print("|---" * (len(PAIRS) + 1) + "|")
    for i, match in enumerate(MATCHES):
        values = [cells[m][i] for _, m in PAIRS]
        print(
            f"| {match} | " + " | ".join("-" if v is None else fmt.format(v) for v in values) + " |"
        )
    print("\nmin / median / max: " + "; ".join(f"{s} {spread(cells[m])}" for s, m in PAIRS))


root = Path(sys.argv[1])
REL = rows(root / "reliability.csv")
AMP = rows(root / "amputation.csv")
MATCHES = sorted({key[0] for key in REL})
print(f"## {root.as_posix()} ({len(MATCHES)} matches)")

diffs: dict[str, list[float | None]] = {}
for _, m in PAIRS:
    diffs[m] = []
    for x in MATCHES:
        v0, v1 = (num(REL.get((x, m, "all", v)), "mean") for v in ("V0", "V1"))
        diffs[m].append(None if v0 is None or v1 is None else v1 - v0)
table("V1 - V0, stratum all (mean of V1 minus mean of V0):", diffs, "{:+.3f}")
print(
    "matches with V1 > V0: "
    + ", ".join(f"{s} {sum(1 for d in diffs[m] if d is not None and d > 0)}" for s, m in PAIRS)
)
extrapolated = {
    m: [num(REL[(x, m, "all", "V0")], "extrapolated_fraction") for x in MATCHES] for _, m in PAIRS
}
print(
    "extrapolated fraction of player-frames, min / median / max: "
    + "; ".join(f"{s} {spread(extrapolated[m])}" for s, m in PAIRS)
)

print("\nline_reaction_m by incoming ball, matches with V1 > V0:")
for stratum in ("backward", "forward", "lateral"):
    pairs = [
        (
            num(REL.get((x, "line_reaction_m", stratum, "V0")), "mean"),
            num(REL.get((x, "line_reaction_m", stratum, "V1")), "mean"),
        )
        for x in MATCHES
    ]
    both = [(a, b) for a, b in pairs if a is not None and b is not None]
    print(f"  {stratum}: {sum(1 for a, b in both if b > a)} of {len(both)}")

errors: dict[str, list[float | None]] = {}
for _, m in PAIRS:
    cells = [AMP.get((x, m, "all", "")) for x in MATCHES]
    errors[m] = [num(c, "mean_abs_error") if c and int(c["n"]) > 0 else None for c in cells]
table("Amputation, mean absolute error of band all:", errors, "{:.3f}")
grows = []
for s, m in PAIRS:
    count = 0
    for x in MATCHES:
        seq = []
        for band in BANDS:
            c = AMP.get((x, m, band, ""))
            if c is not None and int(c["n"]) > 0:
                seq.append(float(c["mean_abs_error"]))
        count += len(seq) >= 2 and all(a < b for a, b in zip(seq, seq[1:], strict=False))
    grows.append(f"{s} {count}")
print(
    "error strictly growing band to band (bands with units, le_1s to gt_20s): " + ", ".join(grows)
)
