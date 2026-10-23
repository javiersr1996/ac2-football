# ac2-football

**How much of a defensive metric computed from broadcast tracking did the camera actually see?** In the 10 calibration matches<!-- src: protocol/split.json:calibration -->, 56.2<!-- src: reports/layer2.json:summary.detection.player_detected.median -->% of player rows are detected, but a typical reception sees only 50.0<!-- src: reports/layer2.json:summary.line.detected.median -->% of the four-player defensive line, and all eleven defenders of a block are detected in just 2.4<!-- src: reports/layer2.json:summary.block.all_detected.median -->% of phases. The provider's "extrapolated" positions are in fact interpolated, so they look smooth and cannot be told apart by step size; every metric here is therefore reported as listed and restricted to what the camera saw.

Entry to the SkillCorner Analytics Cup 2.0 (football, A-League 2024/25 open data). The 20 matches are split in 10 for calibration and 10 held out<!-- src: protocol/split.json:calibration,heldout -->. All figures below come from the calibration half; held-out figures are PENDING(held-out reading), because that half is opened once, for layer 2 only.

## Provenance

Ingestion, bronze and conformed frames and events come from [`ftbase`](https://github.com/javiersr1996/football-tracking-base), the author's open-source pipeline for SkillCorner open data (MIT), pinned at tag `v0.1.0`<!-- src: pyproject.toml:tool.uv.sources.ftbase.tag --> and extracted in October 2026 from the author's private repository *tracklab*; its `docs/provenance.md` lists every file and what changed. tracklab measured the proportion of detected rows. Everything in this repository was written for the Cup: the sensitivity analysis, the interpolation finding, the defensive question, its protocol, figures and tests. kloppy 3.19.1 drops `is_detected` when it loads SkillCorner tracking<!-- src: docs/kloppy_issue_draft.md:kloppy version -->, which is why layer 2 reads the base instead.

## Layer 2: what the camera saw

Each player-frame carries `is_detected`. We add `gap_len`, the frames to the nearest detection. Seven metrics are computed in three variants: V0 (positions as listed), V1 (only units whose players are all detected) and V2 (grouped by how many are extrapolated). The metrics are local pressure, nearest rival, line height, block width, length and area, and the line's reaction to the incoming ball (`reports/reliability.csv`).

**Extrapolated is interpolated.** A predictor would accumulate error with gap length. Here it does not: when a player is re-detected after a gap of more than 20 s, the position jumps by a median of 0.217<!-- src: reports/layer2.json:summary.runs.by_band.gt_20s.closed_jump_median.median --> m, slightly above the 0.198<!-- src: reports/layer2.json:summary.steps.detected_to_detected.p50.median --> m of an ordinary detected step, and the same holds for shorter gaps (Figure 1). Inside gaps the steps are smaller, 0.130<!-- src: reports/layer2.json:summary.steps.extrapolated_to_extrapolated.p50.median --> m, so filled positions are smoother than seen ones. The provider appears to interpolate with the future it has seen. Such gaps hold 31.7<!-- src: reports/layer2.json:summary.runs.by_band.gt_20s.frame_share.median -->% of extrapolated positions, over 214<!-- src: reports/layer2.json:summary.runs.by_band.gt_20s.n_closed.median --> closed gaps per match (median over matches).

![Figure 1](figures/fig1_layer2.png)

*Figure 1. Median jump on re-detection by gap length: up to 1 s 0.224<!-- src: reports/layer2.json:summary.runs.by_band.le_1s.closed_jump_median.median --> m, 1 to 5 s 0.196<!-- src: reports/layer2.json:summary.runs.by_band.1_5s.closed_jump_median.median --> m, 5 to 20 s 0.192<!-- src: reports/layer2.json:summary.runs.by_band.5_20s.closed_jump_median.median --> m, over 20 s 0.217<!-- src: reports/layer2.json:summary.runs.by_band.gt_20s.closed_jump_median.median --> m, against 0.198<!-- src: reports/layer2.json:summary.steps.detected_to_detected.p50.median --> m between detected frames. Calibration half, closed gaps.*

The reliability map, which metrics hold up and which are mostly model, is in `reports/reliability.csv`; its summary is PENDING(task 27). The amputation reference (seen players hidden as the camera hides them, filled by linear interpolation, error measured per gap length) is in `reports/amputation.csv`; its summary is PENDING(task 27).

## Layer 3: a question that died, as designed

We asked whether pressure on the ball carrier at reception reduces the ball's advance over the next 1.3 s<!-- src: protocol/protocol.json:window.seconds -->, within strata of the incoming ball. The protocol was committed as code before any outcome was computed. In calibration the pooled effect is 0.19<!-- src: reports/calibration.json:criteria.D3.values.effect --> standard deviations, negative in 8 of 10<!-- src: reports/calibration.json:variants.V0.matches.*.effect (count below zero) --> matches, permutation p = 0.0005<!-- src: reports/calibration.json:variants.V0.bar.p -->. The effect passes the bar, and the protocol still rejects it: before the reception, pressed and free units already differ in how far the ball had advanced, by 0.18<!-- src: reports/calibration.json:criteria.D3.values.pretrend --> sd, which is 95%<!-- src: reports/calibration.json:criteria.D3.values.pretrend / criteria.D3.values.effect --> of the effect and above the 50% limit written in advance<!-- src: protocol/protocol.json:death_criteria.D3.ratio -->. Restricting to detected players changes nothing (0.20<!-- src: reports/calibration.json:criteria.D4.values.t_v1 --> sd), so tracking gaps do not explain it. The held-out stays shut for this question. That is the method working: the rule fired before any held-out match was read.

![Figure 2](figures/fig2_layer3.png)

*Figure 2. Effect of pressure per calibration match, from -0.36<!-- src: reports/calibration.json:variants.V0.matches.*.effect (min) --> to +0.09<!-- src: reports/calibration.json:variants.V0.matches.*.effect (max) --> sd; the pre-reception difference that rejected it is 0.18<!-- src: reports/calibration.json:criteria.D3.values.pretrend --> sd.*

## Method in short

We do not impute positions. Each metric is recomputed on detected-only units and compared with the listed value, by match and gap length. Hypotheses, thresholds and kill criteria are fixed before the outcomes in `protocol/`. The held-out matches are served only through one recorded reading.

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

Full, 85 files and 1.9 GB<!-- src: Full build run 39782141426, step README block full, sum of the `downloaded:` lines = 1,919,842,163 B; the manifest lists 1,823,448,331 B of it in the 20 Git LFS files --> (1.8 GB of it Git LFS), about 3 min on a GitHub runner<!-- src: same run, `CLEAN CLONE OK in 174 s` -->; mind SkillCorner's quota:

<!-- clean-clone:full:start -->
```bash
git clone https://github.com/javiersr1996/ac2-football
cd ac2-football
uv sync --locked
uv run ftbase ingest
uv run ftbase bronze && uv run ftbase silver && uv run ac2fb layer2 && uv run ac2fb reliability && uv run ac2fb amputation && uv run ac2fb calibration
```
<!-- clean-clone:full:end -->

Held-out matches stay locked until `ac2fb heldout read`, which runs once.

## Reuse

`ac2fb layer2 --match ID` writes `gap_len` and the per-match visibility report for any SkillCorner match; `ac2fb reliability` does the same for the seven metrics. Add a metric by defining it on a unit and letting V0, V1 and V2 run on it.

## License and data

Code under MIT (`LICENSE.md`). Data are SkillCorner's open data, downloaded by the commands above and not redistributed. Synthetic fixtures are used only for tests and produce no figure in this README.
