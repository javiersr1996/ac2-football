# Video script

The one-minute video of the entry, in Javier's voice. One row per sentence: the time window at
150 words per minute, the shot, the sentence as spoken, and for every number in it the artefact
and key it comes from, in the `src` syntax of `README.src.json`, one backticked citation per
number, in order. `scripts/video_script_check.py` counts the spoken words (at most 150), keeps
the line below true and checks every number of the Sentence column against its citation; the
other columns are not checked.

**145 spoken words, 58 s at 150 words per minute**; the margin is for the pauses over the clip and
a slower narrator.

Shots: the clip is `reports/clip/clip.mp4` (match 1874553, 10 s at 10 fps; the reception is at
second 3.0 and `reports/clip/clip_still.png` is that frame) and figure 1 is
`reports/figures/fig1_layer2.svg` (panels a to d). Numerals are read as words; `37` is "thirty-seven".

| # | Time | Shot | Sentence | Sources |
|---|---|---|---|---|
| 1 | 0:00 to 0:06 | Typographic card: the claim in large type, aimed at the filter, not at the fill-in | Keep only what the camera saw, and your block length describes the camera, not your team. | |
| 2 | 0:06 to 0:11 | Clip, seconds 0 to 3, then frozen at second 3.0, the reception (`clip_still.png`): the counter reads 7 of 11 | SkillCorner filled in 7 of these 11 defenders; the camera saw 4. | `reports/clip/clip.json:key.defenders_extrapolated`, `reports/clip/clip.json:n_defenders`, `reports/clip/clip.json:key.defenders_seen` |
| 3 | 0:11 to 0:17 | Code card: the README's call to `sensitivity` and its V0 and V1 for block length in the clip's match, as `reports/camera/camera.json` holds them (`match.rows`) | This code tags each metric with how many of its players were seen: block length. | |
| 4 | 0:17 to 0:23 | Figure 1, panel a: detection falls with the distance to the ball | In 20 matches the camera saw about half the positions; it follows the ball. | `protocol/split.json:calibration,heldout` |
| 5 | 0:23 to 0:29 | Typographic card: the fill check, hide seen players and refill them; its mean absolute error per match, on the moments seen whole, on line depth and on block length | We tested the fill-in: on average about 1 metre off on line depth, at most 6 on block length. | `reports/figures/fig1_layer2.json:series.65.points.0.of.*(max)`, `reports/figures/fig1_layer2.json:series.91.points.0.of.*(max)` |
| 6 | 0:29 to 0:35 | Typographic card: the trap, keeping only the moments seen whole | The trap is that filter: whole lines are seen mostly near the ball. | |
| 7 | 0:35 to 0:40 | Figure 1, panel c, the line depth strip; the panel's title says "seen whole minus all moments" and its grey band is the fill-in's error (rows 7 to 9) | Seen whole, the back four sit 7 to 14 metres deeper than overall, | `reports/figures/fig1_layer2.json:series.63.points.0.of.*(min)`, `reports/figures/fig1_layer2.json:series.61.points.0.of.*(max)` |
| 8 | 0:40 to 0:44 | Figure 1, panel c, the block length strip | the block 17 to 37 metres shorter, in all 20 matches. | `reports/figures/fig1_layer2.json:series.87.points.0.of.*(max)`, `reports/figures/fig1_layer2.json:series.87.points.0.of.*(min)`, `protocol/split.json:calibration,heldout` |
| 9 | 0:44 to 0:48 | Figure 1, panel c, the pressure and nearest rival strips: every match inside the fill-in's band (`tests/test_claims.py` holds it) | Pressure and nearest rival move less than the fill-in's own error. | |
| 10 | 0:48 to 0:54 | Typographic card: the recommendation, and the seven metrics tagged | Keep the fill-in, don't filter it out, report each metric with its tag. | |
| 11 | 0:54 to 0:57 | Card: the call to action, the repo URL, "Code and protocol under MIT", "Presented by" and the author, the data's name | Clone it, run one match, tag your metrics. | |
