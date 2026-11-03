# What the camera saw: a reliability tag for defensive metrics

**Broadcast tracking shows about half the player-frames; SkillCorner fills the rest. For seven metrics of Defensive Positioning, this entry measures how much of the value is the camera's choice of what to show, and tags every metric with how many of its players were seen.** A metric can go wrong two ways: a hidden player placed wrongly (the fill), or only moments near the ball seen whole (the selection). Terms: V0, the metric on all moments; V1, on moments seen whole; V2, split by how many players were filled (none: V1); the selection, V1 minus V0; amputation, hide seen players, refill linearly, measure the error; layer 2, this reliability measurement; layer 3, the pre-registered question.

## Try it on one match

One match, 96 MB of SkillCorner data, 9 s on a GitHub runner with packages cached. It writes `../reports-quick/layer2.json`: how much of the match the camera saw.

<!-- clean-clone:quick:start -->
```bash
git clone https://github.com/javiersr1996/what-the-camera-saw
cd what-the-camera-saw
uv sync --locked
uv run ftbase ingest --match 1874553
uv run ftbase bronze && uv run ftbase silver && uv run ac2fb layer2 --match 1874553 --reports-dir ../reports-quick
```
<!-- clean-clone:quick:end -->

## What the camera does to seven metrics

In the Cup's 20 A-League 2024/25 matches the camera saw 56% of the player-frames (per-match median, calibration) and 57% (held-out). Seven metrics, per reception (pressure on the receiver, nearest rival, line depth, line reaction to the ball) or per defensive phase (block width, length and area).

![Figure 1](reports/figures/fig1_layer2.svg)

*Figure 1, per match: (a) detection by distance to the ball, (b) filled frames by gap length, (c) V1 minus V0, (d) amputation error.*

[The page](https://javiersr1996.github.io/what-the-camera-saw/): two receptions from above inside the camera's measured frame, V0 against V1.

**The fill behaves as an interpolation.** A predictor's error grows with the gap, so a re-detection would jump; it does not: after a gap over 20 s a player reappears a median 0.19 to 0.20 m from its filled position, a step between two detections (0.20 m). So the fill reads the future: a model forecasting from filled positions sees part of its answer. In layer 3 the leak changes nothing (-0.20 sd seen-only against -0.19); a forecasting model should check it. Amputation, the same kind of fill, errs 0.8 to 1.4 m per match on line depth, at most 6 m on block length (Figure 1d, units seen whole). On gaps over 20 s (36% to 39% of filled frames; hollow marks) it errs 1.3 to 1.9 m on line depth, at most 9 m on block length. kloppy drops `is_detected` on SkillCorner tracking ([known upstream issue](https://github.com/PySport/kloppy/issues/639)).

**The selection is large.** The camera follows the ball (Figure 1a), so the units seen whole are near it, blocks only when they fit the frame: a different sample, not an error. On those, the back four sit 7 to 14 m deeper and block length 17 to 37 m shorter in every match of both splits; area, reaction and pressure keep their sign everywhere, nearest rival in 9 of 10, width is mixed. The block was seen whole in 2% to 3% of phases (per-match medians), the back four in 33% and 36% of receptions. Block length and area are mostly what the camera chose to show (report their share seen whole), line depth and reaction follow it, pressure and nearest rival survive, below the fill's mean absolute error everywhere. Keep the fill; never report only what was seen.

## One question, killed by its own rule

Layer 3's question and kill rule (`protocol/protocol.json`): does pressure on the receiver reduce the ball's advance over the next 1.3 s? The effect, -0.19 sd, passed its own bar (same sign in 8 of 10 matches, permutation p 0.0005) but the pre-registered rule killed it: pressed and free receptions differed by 0.18 sd (0.6 m) beforehand, 95% of it, and an effect needs twice that. The ball had advanced more before pressed receptions: the rule cannot tell pressure from the forward pass that preceded it (the data show the advance, not the pass). The held-out never opened for it.

![Figure 2](reports/figures/fig2_layer3.svg)

*Figure 2. (a) Effect per calibration match; grey, the rule's floor. (b) The same difference before the reception.*

## Use it on your data

A metric is a function of a window of frames returning its value and the players it used (`ac2fb.reliability.sensitivity.Metric`); `sensitivity` tags it:

```python
from ac2fb.reliability.long import long_table
from ac2fb.reliability.match import build_match
from ac2fb.reliability.metrics import metric_units
from ac2fb.reliability.sensitivity import sensitivity

match = build_match(match_id, frames, events, team_periods)  # ftbase's silver tables
metric, units = metric_units(match)["line_height_m"]  # line depth
tagged = sensitivity(metric, long_table(frames), units)[match_id]
tagged.v0.mean, tagged.v1.mean, [(s.detected_players, s.n, s.mean) for s in tagged.v2]
```

`examples/sensitivity.py` runs this on a synthetic match; `CONTRIBUTING.md`, how to propose a metric.

## Reproduce

Needs [uv](https://docs.astral.sh/uv/), git, Python 3.13+ and ffmpeg (clip, tests); CI on Windows, Linux and macOS. The full build (1.9 GB, about 3.5 min on a runner with data cached; mind SkillCorner's quota):

<!-- clean-clone:full:start -->
```bash
git clone https://github.com/javiersr1996/what-the-camera-saw
cd what-the-camera-saw
uv sync --locked
uv run ftbase ingest
uv run ftbase bronze && uv run ftbase silver && uv run ac2fb layer2 && uv run ac2fb reliability && uv run ac2fb amputation && uv run ac2fb calibration
```
<!-- clean-clone:full:end -->

`ac2fb` commands take `--check` (recompute, compare); `ac2fb figures` redraws the figures. The held-out opens only inside `ac2fb heldout read` (`docs/heldout.md`); it reproduced byte for byte on Windows, on Linux one player-frame crosses a band edge (`scripts/heldout_linux_diff.txt`).

## Provenance and license

Ingestion and conformed data come from [`ftbase`](https://github.com/javiersr1996/football-tracking-base), my MIT pipeline, pinned at `v0.1.0` (commit `53080bc`), extracted in October 2026 from my private repository *tracklab*, which measured the proportion of detected rows; everything here was written for the Cup.

Code: MIT (`LICENSE.md`, `CITATION.cff`). Data: SkillCorner's open data (MIT per `ftbase`'s manifest); `reports/` holds only derived numbers and two receptions, an excerpt redistributed with SkillCorner's licence (`DATA_LICENSE.md`). Synthetic fixtures are used only for tests and produce no figure in this README.
