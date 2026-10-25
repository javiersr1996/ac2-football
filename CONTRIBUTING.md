# Contributing

## Run the checks

```bash
uv sync --locked                             # uv, git, Python 3.13 or later; ffmpeg for the clip's tests
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run python scripts/readme_check.py        # README.md: words, figures, every number against its source
uv run python scripts/video_script_check.py  # docs/video_script.md: spoken words, every number likewise
uv run pytest -q                             # synthetic data only; a skipped test fails the run
```

The suite is slow (it builds synthetic matches and encodes a video): run the files you touched, and let
`.github/workflows/ci.yml` run them all. `uv run pytest -m realdata` runs the tests on the real matches
and needs a full build (README, "Reproduce") under `data/` or `FTBASE_DATA_ROOT`;
`full-build.yml` does that build and every `--check` on GitHub.

## Propose a metric

A metric is a function of one unit, a window of frames of one match
(`ac2fb.reliability.sensitivity.WindowFrames`), that returns its value and the ids of the players it
was computed from (`Reading`), or `None` when the unit cannot be measured. That contract is what lets
`sensitivity` tag it with how many of those players the camera saw.

1. Write it in `src/ac2fb/reliability/metrics.py` next to the seven there, with its units (a `Window`
   per reception or phase), and add it to `METRICS` and `metric_units`.
2. Test it in `tests/test_reliability_metrics.py` on a planted world whose expected value is written by
   hand, never taken from the code under test; plant one mutation the test must catch and name it in
   the test's docstring.
3. A new public name (in an `__all__`) needs an entry in `tests/test_public_routes.py` saying how it is
   driven with a match id, so the held-out matches stay refused; `tests/test_public_api.py` holds the
   names `ac2fb.reliability` documents.
4. Open a pull request, or an issue with the "Tag a metric" template if you only want to share the
   definition.

The held-out half of the data was read once, for layer 2, and is never read for a new question: new
work runs on the calibration matches. Every number in `README.md` and `docs/video_script.md` needs an
entry (`README.src.json`, the script's Sources column) pointing at the artefact it comes from.

Line endings are LF (`.gitattributes`); commit messages are imperative, under 72 characters, one
logical change each.
