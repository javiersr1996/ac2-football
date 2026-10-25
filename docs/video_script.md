# Video script

The one-minute video of the entry, in Javier's voice. One row per sentence: the time window at
150 words per minute, the shot, the sentence as spoken, and for every number in it the artefact
and key it comes from, in the `src` syntax of `README.src.json`, one backticked citation per
number, in order. `scripts/video_script_check.py` counts the spoken words (at most 150), keeps
the line below true and checks every number of the Sentence column against its citation; the
other columns are not checked.

**134 spoken words, 54 s at 150 words per minute**; the margin is for the pauses over the clip and
a slower narrator.

Shots: the clip is `reports/clip/clip.mp4` (match 1874553, 10 s at 10 fps; the reception is at
second 3.0 and `reports/clip/clip_still.png` is that frame), figure 1 is
`reports/figures/fig1_layer2.svg` (panels a to d), figure 2 is `reports/figures/fig2_layer3.svg`
(panels a and b), the README is `README.md` on screen. Numerals are read as words; `-0.19` is
"minus zero point one nine".

| # | Time | Shot | Sentence | Sources |
|---|---|---|---|---|
| 1 | 0:00 to 0:06 | Clip, seconds 0 to 3, then frozen at second 3.0, the reception (`clip_still.png`): the counter reads 7 of 11 | In SkillCorner's broadcast tracking, the model filled in 7 of these 11 defenders. | `reports/clip/clip.json:key.defenders_extrapolated`, `reports/clip/clip.json:n_defenders` |
| 2 | 0:06 to 0:10 | Clip, seconds 3 to 10: hollow markers fill in as the camera finds the players again | The camera saw 4; hollow markers show seconds to the nearest detection. | `reports/clip/clip.json:key.defenders_seen` |
| 3 | 0:10 to 0:14 | Figure 1, panel a: detection falls with the distance to the ball | Across 20 matches, the camera saw about half the player-frames. | `protocol/split.json:calibration,heldout` |
| 4 | 0:14 to 0:20 | Figure 1, panel c, the line height strip | Seen players only: in every match the defensive line sits 7 to 14 metres higher, | `reports/figures/fig1_layer2.json:series.63.points.0.of.*(min)`, `reports/figures/fig1_layer2.json:series.61.points.0.of.*(max)` |
| 5 | 0:20 to 0:23 | Figure 1, panel c, the block length strip | the block 17 to 37 metres shorter. | `reports/figures/fig1_layer2.json:series.87.points.0.of.*(max)`, `reports/figures/fig1_layer2.json:series.87.points.0.of.*(min)` |
| 6 | 0:23 to 0:29 | Figure 1, panel c, the pressure and nearest rival strips, both near zero | Block length and area are mostly what the camera chose; pressure and nearest rival survive. | |
| 7 | 0:29 to 0:33 | Typographic card: the sentence in large type, no camera | Tag every metric with how many of its players were seen. | |
| 8 | 0:33 to 0:38 | Figure 2, panel a | Layer 3: does pressure on the receiver reduce the ball's advance? | |
| 9 | 0:38 to 0:42 | Figure 2, panel a: the pooled effect against the grey D3 floor | The pre-registered rule killed an effect of -0.19 standard deviations. | `reports/calibration.json:criteria.D3.values.effect` |
| 10 | 0:42 to 0:46 | Figure 2, panel b | Pressed and free receptions already differed by 0.18 before the ball arrived. | `reports/calibration.json:criteria.D3.values.pretrend` |
| 11 | 0:46 to 0:48 | Typographic card: the sentence in large type, no camera | That is the published result. | |
| 12 | 0:48 to 0:54 | Card: "Reproduce", the repo URL, "Code and protocol under MIT", the author | Code and protocol are on GitHub under MIT; one match builds in seconds. | |
