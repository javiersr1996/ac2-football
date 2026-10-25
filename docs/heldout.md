# Reproducing the held-out reading

The held-out half opens only inside `ac2fb heldout read`, in a checkout whose `HEAD` is the
reading commit, `4cb9351` ("Read the held-out for layer 2: the single reading"): the code frozen
for the reading, with its own `uv.lock`. `.github/workflows/full-build.yml` runs these commands on
`ubuntu-26.04` after the full README block; by hand, from a full build (`data/` holds the 20
matches), with the clone named `ac2-football`:

```bash
git worktree add ../reading 4cb9351
cd ../reading
uv sync --locked
FTBASE_DATA_ROOT=../ac2-football/data uv run ac2fb heldout read --reports-dir ../heldout-check
cd ../ac2-football
bash scripts/compare_heldout_reading.sh --expect-diff scripts/heldout_linux_diff.txt ../heldout-check
```

The reading was made on Windows and reproduces there byte for byte: on Windows, drop
`--expect-diff scripts/heldout_linux_diff.txt`. On Linux (`ubuntu-26.04`, the runner of
`full-build.yml`) one player-frame crosses the 10 m edge of the ball-distance bands, because
`np.hypot` goes through the platform libm; `scripts/heldout_linux_diff.txt` pins that difference
and `--expect-diff` accepts exactly it, nothing else. Afterwards, `git worktree remove ../reading`.
