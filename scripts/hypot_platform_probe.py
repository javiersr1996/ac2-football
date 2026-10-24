"""Does np.hypot give different bits on two platforms? Evidence for the held-out Linux difference.

    python scripts/hypot_platform_probe.py write OUT.npz     # on each platform
    python scripts/hypot_platform_probe.py compare A.npz B.npz

`write` computes np.hypot and np.sqrt(dx*dx + dy*dy) on the same seeded pairs (a pitch-sized range,
the seed fixes the pairs on any platform) and stores the float64 bits. `compare` counts the results
whose bits differ between the two files, for each formula. No data of the project is read.
"""

from __future__ import annotations

import sys

import numpy as np

N = 4_000_000
SEED = 20261024
SPAN = 120.0  # metres: both coordinates of a difference between two points on a pitch


def pairs() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(SEED)
    return rng.uniform(-SPAN, SPAN, N), rng.uniform(-SPAN, SPAN, N)


def write(out: str) -> None:
    dx, dy = pairs()
    np.savez(
        out,
        hypot=np.hypot(dx, dy).view(np.uint64),
        sqrt=np.sqrt(dx * dx + dy * dy).view(np.uint64),
    )
    print(f"numpy {np.__version__}: wrote {N} pairs to {out}")


def compare(a: str, b: str) -> None:
    fa, fb = np.load(a), np.load(b)
    for name in ("hypot", "sqrt"):
        print(
            f"{name}: {int(np.count_nonzero(fa[name] != fb[name]))} of {N} results differ in bits"
        )


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "write":
        write(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == "compare":
        compare(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
