# Video script

The one-minute video of the entry, in Javier's voice. One row per sentence: the time window at
150 words per minute, the shot, the sentence as spoken, and for every number in it the artefact
and key it comes from, in the `src` syntax of `README.src.json`, one backticked citation per
number, in order. `scripts/video_script_check.py` counts the spoken words (at most 150), keeps
the line below true and checks every number of the Sentence column against its citation; the
other columns are not checked.

**142 spoken words, 57 s at 150 words per minute**; the margin is for the pauses over the clip and
a slower narrator.

Shots: the clip is `reports/clip/clip.mp4` (match 1874553, 10 s at 10 fps; the reception is at
second 3.0 and `reports/clip/clip_still.png` is that frame), figure 1 is
`reports/figures/fig1_layer2.svg` (panels a to d), figure 2 is `reports/figures/fig2_layer3.svg`
(panels a and b). Numerals are read as words; `37` is "thirty-seven".

| # | Time | Shot | Sentence | Sources |
|---|---|---|---|---|
| 1 | 0:00 to 0:05 | Clip, seconds 0 to 3, then frozen at second 3.0, the reception (`clip_still.png`): the counter reads 7 of 11 | The camera saw 4 of these 11 defenders; SkillCorner filled in 7. | `reports/clip/clip.json:key.defenders_seen`, `reports/clip/clip.json:n_defenders`, `reports/clip/clip.json:key.defenders_extrapolated` |
| 2 | 0:05 to 0:10 | Figure 1, panel a: detection falls with the distance to the ball | In 20 matches it saw about half the player positions; it follows the ball. | `protocol/split.json:calibration,heldout` |
| 3 | 0:10 to 0:14 | Typographic card: the question in large type | Is a defensive metric about the team, or the camera? | |
| 4 | 0:14 to 0:18 | Typographic card: the seven metrics by name | This entry measures that for 7 Defensive Positioning metrics. | `reports/camera/camera.json:findings.signs.*.of(min)` |
| 5 | 0:18 to 0:24 | Clip, seconds 3 to 10: hollow markers fill in as the camera finds the players again | One, the fill: hide seen players, refill them; line depth misses by about 1 metre. | `reports/figures/fig1_layer2.json:series.65.points.0.of.*(max)` |
| 6 | 0:24 to 0:30 | Figure 1, panel c, the line depth strip; the panel's title defines V1 and V0 on screen (rows 6 to 8) | Two: on moments seen whole the back four sit 7 to 14 metres deeper, | `reports/figures/fig1_layer2.json:series.63.points.0.of.*(min)`, `reports/figures/fig1_layer2.json:series.61.points.0.of.*(max)` |
| 7 | 0:30 to 0:35 | Figure 1, panel c, the block length strip | the block 17 to 37 metres shorter: a different sample, near the ball. | `reports/figures/fig1_layer2.json:series.87.points.0.of.*(max)`, `reports/figures/fig1_layer2.json:series.87.points.0.of.*(min)` |
| 8 | 0:35 to 0:41 | Figure 1, panel c, the pressure and nearest rival strips, both near zero | Block length and area are mostly the camera's choice; pressure and nearest rival survive. | |
| 9 | 0:41 to 0:45 | Typographic card: the sentence in large type, no camera | Tag every metric with how many of its players were seen. | |
| 10 | 0:45 to 0:50 | Figure 2, panels a and b | A pre-registered question: does pressure on the receiver reduce the ball's advance? | |
| 11 | 0:50 to 0:54 | Figure 2, panel a: the pooled effect against the grey floor the rule set | An effect, killed by its own rule, published as killed. | |
| 12 | 0:54 to 0:57 | Card: the call to action, the repo URL, "Code and protocol under MIT", "Presented by" and the author, the data's name | Clone it, run one match, tag your metrics. | |
