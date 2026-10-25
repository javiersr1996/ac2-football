# What the camera saw: a reliability tag for defensive metrics

**Broadcast tracking shows about half the player-frames; SkillCorner fills the rest. For seven defensive metrics, this entry measures how much of the value is the camera's choice of what to show, and tags every metric with how many of its players were seen.** Two things can move a metric: the fill (a hidden player placed wrongly) and the selection (the camera shows whole the moments near the ball). The fill error is measured by hiding seen players and refilling them with a straight line (amputation); the selection, as the metric on moments seen whole (V1) minus the metric on all moments (V0).

## Try it in 9 seconds

One match, 96 MB of SkillCorner data, timed on a GitHub runner with packages cached. You get `../reports-quick/layer2.json`: how much the camera saw, by distance to the ball, and how often the back line and the block were seen whole.

<!-- clean-clone:quick:start -->
```bash
git clone https://github.com/javiersr1996/ac2-football
cd ac2-football
uv sync --locked
uv run ftbase ingest --match 1874553
uv run ftbase bronze && uv run ftbase silver && uv run ac2fb layer2 --match 1874553 --reports-dir ../reports-quick
```
<!-- clean-clone:quick:end -->

## What the camera does to seven metrics

In the 20 A-League 2024/25 matches of the Analytics Cup 2.0 the camera saw about half the player-frames: a per-match median of 56% in the calibration half and 57% in the held-out half. Seven metrics: pressure on the receiver, nearest rival, line height, the line's reaction to the incoming ball, block width, length and area, each on its units, receptions (pressure, rival, line) or defensive phases (block). Each is computed on every unit (V0 in the figures), on the units seen whole (V1) and split by how many of its players were seen.

![Figure 1](reports/figures/fig1_layer2.svg)

*Figure 1, per match: (a) detection by distance to the ball, (b) filled frames by gap length, (c) seen-only minus all (V1 minus V0), (d) straight-line fill error.*

**The fill behaves as an interpolation.** A predictor's error grows with the gap, so a re-detection would jump. It does not: after a gap over 20 s a player reappears a median 0.19 to 0.20 m from its filled position (held-out, calibration), the size of a step between two detections (0.20 m). A straight-line refill of seen players, the same kind of fill, errs 0.8 to 1.4 m per match on line height (Figure 1d). kloppy drops `is_detected` on SkillCorner tracking ([reported upstream](https://github.com/PySport/kloppy/issues/639)).

**The selection is large.** The camera follows the ball (Figure 1a), so the units seen whole are near it. On those, line height is 7 to 14 m higher and block length 17 to 37 m shorter in every match of both halves; area, reaction and pressure keep their sign everywhere, nearest rival in 9 of 10, width is mixed. The block was seen whole in 2% to 3% of phases (per-match medians), the four-man back line in a third of receptions (33% and 36%). For analysts: block length and area are mostly what the camera chose to show, line height and reaction follow it, pressure and nearest rival survive.

## One question, killed by its own rule

Layer 3 is the method on trial: one pre-registered question (does pressure on the receiver reduce the ball's advance over the next 1.3 s?) with a kill rule committed before any outcome (`protocol/protocol.json`). The rule fired and the result is published as killed: the effect, -0.19 sd, is matched 95% by a difference that was already there before the ball arrived (0.18 sd); seen-only players give the same effect (-0.20 sd), so the camera is not the cause; the held-out never opened for it.

![Figure 2](reports/figures/fig2_layer3.svg)

*Figure 2. (a) Effect per calibration match; grey band, the floor the rule set before any outcome. (b) The same difference before the reception.*

## Use it on your data

A metric is a function of a window of frames that returns its value and the players it used (`ac2fb.reliability.sensitivity.Metric`); `sensitivity` tags it:

```python
from ac2fb.reliability.long import long_table
from ac2fb.reliability.match import build_match
from ac2fb.reliability.metrics import metric_units
from ac2fb.reliability.sensitivity import sensitivity

match = build_match(match_id, frames, events, team_periods)  # silver tables in ftbase's shape
metric, units = metric_units(match)["line_height_m"]  # or your own Metric
tagged = sensitivity(metric, long_table(frames), units)[match_id]
tagged.v0.mean, tagged.v1.mean, [(s.detected_players, s.n, s.mean) for s in tagged.v2]
```

`examples/sensitivity.py` runs this on a synthetic match; `ac2fb.reliability` lists the public names; `CONTRIBUTING.md` says how to propose a metric. `ac2fb layer2`, `reliability` and `amputation` take `--match ID` for any calibration match; the data door refuses the held-out ones.

## Reproduce

Needs [uv](https://docs.astral.sh/uv/), git, Python 3.13 or later and ffmpeg (`ac2fb clip`, tests); tested on Windows and GitHub's Linux and macOS runners. The full build (1.9 GB, about 3.5 min on a GitHub runner with data cached; mind SkillCorner's quota):

<!-- clean-clone:full:start -->
```bash
git clone https://github.com/javiersr1996/ac2-football
cd ac2-football
uv sync --locked
uv run ftbase ingest
uv run ftbase bronze && uv run ftbase silver && uv run ac2fb layer2 && uv run ac2fb reliability && uv run ac2fb amputation && uv run ac2fb calibration
```
<!-- clean-clone:full:end -->

Every command has `--check`; `ac2fb figures` redraws them. The held-out opens only inside `ac2fb heldout read`, at the reading commit (recipe in `docs/heldout.md`); it reproduced byte for byte on my Windows machine; on Linux one player-frame crosses a band edge, pinned in `scripts/heldout_linux_diff.txt`.

## Provenance

Ingestion and the conformed data come from [`ftbase`](https://github.com/javiersr1996/football-tracking-base), my open-source (MIT) pipeline for SkillCorner data, pinned at tag `v0.1.0` (commit `53080bc`) and extracted in October 2026 from my private repository *tracklab* (its `docs/provenance.md` lists every file). tracklab measured the proportion of detected rows; everything here was written for the Cup.

## License and data

Code: MIT (`LICENSE.md`; `CITATION.cff` to cite). Data: SkillCorner's, downloaded by the commands above, not redistributed. Synthetic fixtures are used only for tests and produce no figure in this README.

Clone it, run one match, tag your metrics.
