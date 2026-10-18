# ac2-football

Football entry to the SkillCorner Analytics Cup 2.0 (provisional README).

## Reproduce the data

Ingestion, bronze and silver come from [`ftbase`](https://github.com/javiersr1996/football-tracking-base),
pinned at tag `v0.1.0` in `pyproject.toml` (`[tool.uv.sources]`) and at its commit in `uv.lock`.
The base is installed from GitHub, so a clean clone needs nothing next to it. Requires
[uv](https://docs.astral.sh/uv/) and git. Data goes under `data/` (or `$FTBASE_DATA_ROOT`).

Quick: one match (5 files, about 95.6 MB downloaded from SkillCorner's open data).

<!-- clean-clone:quick:start -->
```bash
git clone https://github.com/javiersr1996/ac2-football
cd ac2-football
uv sync --locked
uv run ftbase ingest --match 1874553
uv run ftbase bronze && uv run ftbase silver
```
<!-- clean-clone:quick:end -->

Full: all 20 matches (85 files, about 1.9 GB of Git LFS from SkillCorner; mind their quota).

<!-- clean-clone:full:start -->
```bash
git clone https://github.com/javiersr1996/ac2-football
cd ac2-football
uv sync --locked
uv run ftbase ingest
uv run ftbase bronze && uv run ftbase silver
```
<!-- clean-clone:full:end -->

`scripts/clean_clone_check.sh <quick|full>` runs the matching block above, verbatim, in a fresh
temporary directory and checks the receipt, the silver output and that the clone stays clean.

## Trying a change to the base without a tag

With the base cloned next to this repo, run any command against it without touching the lock:

    uv run --with-editable ../football-tracking-base pytest -q

A fix in the base needs a new tag and a re-pin here (`uv lock --upgrade-package ftbase`).
