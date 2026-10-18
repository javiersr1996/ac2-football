# ac2-football

Football entry to the SkillCorner Analytics Cup 2.0 (provisional README).

## Setup

    uv sync --locked

Ingestion, bronze and silver come from [`ftbase`](https://github.com/javiersr1996/football-tracking-base),
pinned at tag `v0.1.0` in `pyproject.toml` (`[tool.uv.sources]`) and at its commit in `uv.lock`.
Never use a `path` source: a clean clone must resolve the base from GitHub.

## Trying a change to the base without a tag

With the base cloned next to this repo, run any command against it without touching the lock:

    uv run --with-editable ../football-tracking-base pytest -q

A fix in the base needs a new tag and a re-pin here (`uv lock --upgrade-package ftbase`).
