# ac2-football

**How much of a defensive metric computed from broadcast tracking did the camera actually see?** SkillCorner marks each player-frame as detected or extrapolated. In the 20<!-- src: protocol/split.json:calibration,heldout --> A-League 2024/25 matches of the Analytics Cup 2.0, the camera saw about half: a median per match of 56.2<!-- src: reports/layer2.json:summary.detection.player_detected.median -->% in the 10 calibration matches<!-- src: protocol/split.json:calibration --> and 57.0<!-- src: reports/heldout/layer2.json:summary.detection.player_detected.median -->% in the 10 held out<!-- src: protocol/split.json:heldout -->. Per match, I measure what each defensive metric does when restricted to what was seen, and find that the "extrapolated" positions are interpolated with the future: their motion does not give them away.

![Figure 1](reports/figures/fig1_layer2.svg)

*Figure 1. Per match: (a) detection by ball distance, (b) filled frames by gap length, (c) V1 minus V0, (d) amputation error.*

## Layer 2: what the camera saw

Each player-frame carries `is_detected`; I add `gap_len`, the frames to the nearest detection. Seven metrics (local pressure, nearest rival, line height, its reaction to the incoming ball, block width, length and area) come as V0, as listed; V1, only units whose players were all seen; and V2, by how many of the unit's n players were seen (`reports/reliability.csv`). The held-out was read once, for layer 2 only, with the code frozen (`protocol/layer2.json`).

**Extrapolated is interpolated.** A predictor's error grows with the gap, so a re-detection would jump. It does not: after a gap of more than 20 s a player moves a median 0.203<!-- src: reports/layer2.json:summary.reacquisition.by_band.gt_20s.closed_jump_median.median --> m in calibration, against 0.198<!-- src: reports/layer2.json:summary.steps.detected_to_detected.p50.median --> m for a detected-to-detected step; held-out, 0.190<!-- src: reports/heldout/layer2.json:summary.reacquisition.by_band.gt_20s.closed_jump_median.median --> m against 0.201<!-- src: reports/heldout/layer2.json:summary.steps.detected_to_detected.p50.median --> m. Inside gaps the steps are smaller (0.130<!-- src: reports/layer2.json:summary.steps.extrapolated_to_extrapolated.p50.median --> m and 0.125<!-- src: reports/heldout/layer2.json:summary.steps.extrapolated_to_extrapolated.p50.median --> m): filled positions are smoother than seen ones. Gaps longer than 20 s hold 38.7<!-- src: reports/layer2.json:summary.reacquisition.by_band.gt_20s.frame_share.median -->% and 36.0<!-- src: reports/heldout/layer2.json:summary.reacquisition.by_band.gt_20s.frame_share.median -->% of the filled frames (Figure 1b).

**Sensitivity, per match.** Every metric moves the same way in both halves (Figure 1c). Line height, V1 minus V0, is +7.2<!-- src: reports/figures/fig1_layer2.json:series.63.points.0.of.*(min) --> to +13.2<!-- src: reports/figures/fig1_layer2.json:series.63.points.0.of.*(max) --> m in the held-out (+8.7<!-- src: reports/figures/fig1_layer2.json:series.61.points.0.of.*(min) --> to +13.9<!-- src: reports/figures/fig1_layer2.json:series.61.points.0.of.*(max) --> m in calibration), positive in 10 of 10<!-- src: reports/figures/fig1_layer2.json:series.63.points.0.of.*(count below zero) --> in each half; block length is -37.3<!-- src: reports/figures/fig1_layer2.json:series.87.points.0.of.*(min) --> to -17.1<!-- src: reports/figures/fig1_layer2.json:series.87.points.0.of.*(max) --> m (-34.5<!-- src: reports/figures/fig1_layer2.json:series.85.points.0.of.*(min) --> to -21.8<!-- src: reports/figures/fig1_layer2.json:series.85.points.0.of.*(max) --> m), negative in 10 of 10<!-- src: reports/figures/fig1_layer2.json:series.87.points.0.of.*(count below zero) -->. Area, reaction and pressure also hold in 10 of 10<!-- src: reports/figures/fig1_layer2.json:series.95.points.0.of.*(count below zero) -->; the nearest rival in 9 of 10<!-- src: reports/figures/fig1_layer2.json:series.55.points.0.of.*(count below zero) --> and 9 of 10<!-- src: reports/figures/fig1_layer2.json:series.53.points.0.of.*(count below zero) -->; block width is mixed (narrower in 8 of 10<!-- src: reports/figures/fig1_layer2.json:series.79.points.0.of.*(count below zero) --> and 7 of 10<!-- src: reports/figures/fig1_layer2.json:series.77.points.0.of.*(count below zero) -->). This is selection: the camera follows the ball, so fully seen units are the ones near it, and a metric that needs the far players, like block length, is mostly model.

**What filling costs.** As a reference, I hide seen players as the camera does (gaps drawn from each match's own `gap_len` and detection by ball distance), fill them with a straight line and measure the error (`reports/amputation.csv`). Per held-out match: 0.90<!-- src: reports/figures/fig1_layer2.json:series.67.points.0.of.*(min) --> to 1.20<!-- src: reports/figures/fig1_layer2.json:series.67.points.0.of.*(max) --> m on line height, 2.1<!-- src: reports/figures/fig1_layer2.json:series.83.points.0.of.*(min) --> to 2.9<!-- src: reports/figures/fig1_layer2.json:series.83.points.0.of.*(max) --> m on width, 0.1<!-- src: reports/figures/fig1_layer2.json:series.91.points.0.of.*(min) --> to 6.0<!-- src: reports/figures/fig1_layer2.json:series.91.points.0.of.*(max) --> m on length, growing with gap length.

## Layer 3: a question that died, as designed

Does pressure on the receiver reduce the ball's advance over the next 1.3 s<!-- src: protocol/protocol.json:window.seconds -->, within strata of the incoming ball? Hypotheses, thresholds and kill criteria were committed in `protocol/` before any outcome. In calibration the pooled effect is -0.19<!-- src: reports/calibration.json:criteria.D3.values.effect --> sd, negative in 8 of 10<!-- src: reports/calibration.json:variants.V0.bar.agreeing,variants.V0.bar.matches --> matches, permutation p = 0.0005<!-- src: reports/calibration.json:variants.V0.bar.p -->: it passes the bar. The protocol still rejects it: before the reception, pressed and free units already differed in the ball's advance by 0.18<!-- src: reports/calibration.json:criteria.D3.values.pretrend --> sd, 95<!-- src: reports/calibration.json:criteria.D3.values.pretrend / criteria.D3.values.effect -->% of the effect and above the 50<!-- src: protocol/protocol.json:death_criteria.D3.ratio -->% limit written in advance. Restricting to seen players changes nothing (-0.20<!-- src: reports/calibration.json:criteria.D4.values.t_v1 --> sd), so tracking gaps do not explain it. The rule fired before any held-out match was read; the held-out was never opened for this question (`protocol/protocol.json`, stage `dead`). That is the result.

![Figure 2](reports/figures/fig2_layer3.svg)

*Figure 2. Effect per calibration match, -0.36<!-- src: reports/calibration.json:variants.V0.matches.*.effect (min) --> to +0.09<!-- src: reports/calibration.json:variants.V0.matches.*.effect (max) --> sd, and the pre-reception difference, 0.18<!-- src: reports/calibration.json:criteria.D3.values.pretrend --> sd, that rejected it.*

## Method in short

The held-out opens only inside `ac2fb heldout read`, which commits its record before computing. Every command has `--check`: it recomputes its artefact and compares it value by value. The reading reproduces byte for byte on Windows; on Linux (`ubuntu-26.04`<!-- src: .github/workflows/full-build.yml:runs-on -->) one player-frame crosses a ball-distance band edge (`np.hypot` through the platform libm), a difference pinned in `scripts/heldout_linux_diff.txt` and verified in CI.

## Provenance

Ingestion and conformed frames and events come from [`ftbase`](https://github.com/javiersr1996/football-tracking-base), my open-source pipeline for SkillCorner open data (MIT), pinned at tag `v0.1.0`<!-- src: pyproject.toml:tool.uv.sources.ftbase.tag --> and extracted in October 2026 from my private repository *tracklab*; its `docs/provenance.md` lists every file and what changed. tracklab had measured the proportion of detected rows; everything here (sensitivity, interpolation finding, amputation reference, question, protocol, reading, figures, tests) was written for the Cup. kloppy 3.19.1 drops `is_detected` when it loads SkillCorner tracking<!-- src: docs/kloppy_issue_draft.md:kloppy version -->, so layer 2 reads the base instead.

## Reproduce

Needs [uv](https://docs.astral.sh/uv/), git and Python 3.13 or later<!-- src: pyproject.toml:project.requires-python -->. Quick, one match, 5 files and 95.6 MB<!-- src: Full build run 39782141426, step README block quick, sum of the `downloaded:` lines = 95,624,493 B --> (about 9 s on a GitHub runner<!-- src: same run, `CLEAN CLONE OK in 9 s` -->):

<!-- clean-clone:quick:start -->
```bash
git clone https://github.com/javiersr1996/ac2-football
cd ac2-football
uv sync --locked
uv run ftbase ingest --match 1874553
uv run ftbase bronze && uv run ftbase silver && uv run ac2fb layer2 --match 1874553 --reports-dir ../reports-quick
```
<!-- clean-clone:quick:end -->

Full, 85 files and 1.9 GB<!-- src: Full build run 39782141426, step README block full, sum of the `downloaded:` lines = 1,919,842,163 B; the manifest lists 1,823,448,331 B of it in the 20 Git LFS files --> (1.8 GB of it Git LFS), about 3 min on a GitHub runner<!-- src: Full build run 40117288163, step README block full, `CLEAN CLONE OK in 202 s` with the raw files cached; the cold run 39782141426 took 174 s before `ac2fb amputation` joined the block -->; mind SkillCorner's quota:

<!-- clean-clone:full:start -->
```bash
git clone https://github.com/javiersr1996/ac2-football
cd ac2-football
uv sync --locked
uv run ftbase ingest
uv run ftbase bronze && uv run ftbase silver && uv run ac2fb layer2 && uv run ac2fb reliability && uv run ac2fb amputation && uv run ac2fb calibration
```
<!-- clean-clone:full:end -->

`ac2fb figures` redraws the figures; `full-build.yml` reproduces the held-out half from the reading commit.

## Reuse

`ac2fb layer2`, `ac2fb reliability` and `ac2fb amputation` take `--match ID` for any SkillCorner match. `ac2fb.reliability` documents the four Python steps (`long_table` with `gap_len`, `metric_units`, `sensitivity`, `amputate`); `examples/sensitivity.py` runs them on a synthetic match in memory. A new metric is a function on a unit that names its players; V0, V1 and V2 then run on it.

## License and data

Code under MIT (`LICENSE.md`). Data are SkillCorner's open data, downloaded by the commands above and not redistributed. Synthetic fixtures are used only for tests and produce no figure in this README.
