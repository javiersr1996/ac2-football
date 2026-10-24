# Video script

The one-minute video of the entry, in Javier's voice. One row per sentence: the time window at
150 words per minute, the shot, the sentence as spoken, and for every number in it the artefact
and key it comes from, in the `src` syntax of `README.src.json`, one backticked citation per
number, in order. `scripts/video_script_check.py` counts the spoken words (at most 150), keeps
the line below true and checks every number of the Sentence column against its citation; the
other columns are not checked.

**146 spoken words, 58 s at 150 words per minute.**

Shots: the clip is `reports/clip/clip.mp4` (match 1874553, 10 s at 10 fps; the reception is at
second 3.0 and `reports/clip/clip_still.png` is that frame), figure 1 is
`reports/figures/fig1_layer2.svg` (panels a to d), figure 2 is `reports/figures/fig2_layer3.svg`
(panels a and b), the README is `README.md` on screen. Numerals are read as words; `-0.19` is
"minus zero point one nine".

| # | Time | Shot | Sentence | Sources |
|---|---|---|---|---|
| 1 | 0:00 to 0:05 | Clip, seconds 0 to 3, then frozen at second 3.0, the reception (`clip_still.png`): the counter reads 7 of 11 | In SkillCorner's broadcast tracking, the camera saw 4 of these 11 defenders. | `reports/clip/clip.json:key.defenders_seen`, `reports/clip/clip.json:n_defenders` |
| 2 | 0:05 to 0:11 | Clip, seconds 3 to 10: hollow markers fill in as the camera finds the players again | The model filled in the other 7, each labelled with the seconds to its nearest detection. | `reports/clip/clip.json:key.defenders_extrapolated` |
| 3 | 0:11 to 0:15 | Figure 1, panel a: detection falls with the distance to the ball | Across 20 matches, the camera saw about half the player-frames. | `protocol/split.json:calibration,heldout` |
| 4 | 0:15 to 0:22 | Figure 1, panel c, the line height strip | Keep only what the camera saw: in every match the defensive line sits 7 to 14 metres higher | `reports/figures/fig1_layer2.json:series.63.points.0.of.*(min)`, `reports/figures/fig1_layer2.json:series.61.points.0.of.*(max)` |
| 5 | 0:22 to 0:25 | Figure 1, panel c, the block length strip | and the block 17 to 37 metres shorter. | `reports/figures/fig1_layer2.json:series.87.points.0.of.*(max)`, `reports/figures/fig1_layer2.json:series.87.points.0.of.*(min)` |
| 6 | 0:25 to 0:32 | Figure 1, panel c, the pressure and nearest rival strips, both near zero | Block length and area are mostly what the camera chose to show; pressure and nearest rival survive. | |
| 7 | 0:32 to 0:36 | Javier on camera | Tag every metric with how many of its players were seen. | |
| 8 | 0:36 to 0:41 | Figure 2, panel a | Layer 3 asked whether pressure on the receiver reduces the ball's advance. | |
| 9 | 0:41 to 0:46 | Figure 2, panel a: the pooled effect against the grey D3 floor | The effect was -0.19 standard deviations, but the pre-registered rule killed it. | `reports/calibration.json:criteria.D3.values.effect` |
| 10 | 0:46 to 0:51 | Figure 2, panel b | Pressed and free receptions already differed by 0.18 before the ball arrived. | `reports/calibration.json:criteria.D3.values.pretrend` |
| 11 | 0:51 to 0:53 | Javier on camera | That is the published result. | |
| 12 | 0:53 to 0:58 | README on screen, the Reproduce section | Code and protocol are on GitHub; one match builds in about 9 seconds. | `Full build run 39782141426, step README block quick, CLEAN CLONE OK in 9 s` |
