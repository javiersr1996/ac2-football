**Draft, not published.**

# SkillCorner deserializer drops per-player `is_detected` (and ball `is_detected`)

**kloppy version:** 3.19.1 (latest on PyPI when checked, 2026-10-18)

## Summary

The SkillCorner tracking deserializer reads `player_data[*].is_detected` and `ball_data.is_detected` from the raw JSONL, but does not keep either flag. A frame where a player is marked `is_detected: false` (interpolated or extrapolated position) is loaded exactly like a detected one. The flag is not exposed in `PlayerData.other_data`, `Frame.other_data`, or anywhere else on the `TrackingDataset`.

## Where

`kloppy/infra/serializers/tracking/skillcorner.py`, method `_get_frame_data_v3`:

- lines 224 to 233: the loop over `frame["player_data"]` builds `PlayerData(coordinates=player_coordinates)` and ignores `raw_player_data["is_detected"]`. `other_data` is left at its default (`{}`).
- line 215: `ball_coordinates` is built from `frame["ball_data"]` and `ball_data["is_detected"]` is ignored.
- line 241: `create_frame(..., other_data={})`, so there is no frame-level place for it either.

`_get_frame_data_v2` (around lines 165 to 185) has the same pattern for the v2 format.

## Reproduction

Two frames, one player, all values synthetic. Save as `repro.jsonl` and load with any SkillCorner v3 `match.json` (`meta_data`) that contains player 71 on the home team:

```jsonl
{"frame": 4, "timestamp": "00:00:00.40", "period": 1, "ball_data": {"x": -19.5, "y": -5.89, "z": 0.21, "is_detected": true}, "possession": {"player_id": 71, "group": "home team"}, "image_corners_projection": {"x_top_left": -39.56, "y_top_left": 24.92, "x_bottom_left": 32.3, "y_bottom_left": 39.29, "x_bottom_right": -31.07, "y_bottom_right": -13.83, "x_top_right": -40.83, "y_top_right": -5.34}, "player_data": [{"player_id": 71, "x": -8.0, "y": -19.5, "is_detected": true}]}
{"frame": 5, "timestamp": "00:00:00.50", "period": 1, "ball_data": {"x": -19.5, "y": -5.89, "z": 0.21, "is_detected": true}, "possession": {"player_id": 71, "group": "home team"}, "image_corners_projection": {"x_top_left": -39.56, "y_top_left": 24.92, "x_bottom_left": 32.3, "y_bottom_left": 39.29, "x_bottom_right": -31.07, "y_bottom_right": -13.83, "x_top_right": -40.83, "y_top_right": -5.34}, "player_data": [{"player_id": 71, "x": -8.0, "y": -19.5, "is_detected": false}]}
```

```python
import kloppy.skillcorner as sc

ds = sc.load(meta_data="match.json", raw_data="repro.jsonl")
for fr in ds.records:
    for player, pdata in fr.players_data.items():
        print(fr.frame_id, player.player_id, pdata.coordinates, pdata.other_data)
```

Actual output: frames 4 and 5 are identical, and `other_data` is `{}` in both.

```
4 71 0.42 0.79 other_data= {}
5 71 0.42 0.79 other_data= {}
```

(The `x`/`y` values are kloppy's transformed coordinates, not the raw ones.)

## Expected behaviour

Keep the flag per player and per frame, for example in `PlayerData.other_data["is_detected"]` and `ball` equivalent in `Frame.other_data["ball_is_detected"]`. Users can then filter or weight interpolated positions. The data is already in the source file, so no format change is needed. Frames where the flag is absent should keep today's behaviour.

## Proposed minimal change

In `_get_frame_data_v3`:

```python
players_data[player] = PlayerData(
    coordinates=player_coordinates,
    other_data={"is_detected": raw_player_data.get("is_detected")},
)
```

and pass `other_data={"ball_is_detected": frame["ball_data"].get("is_detected")}` to `create_frame`. The same change applies to the v2 branch. Tests: one fixture frame with `is_detected: false` asserting the value is exposed. Existing fixtures without the key would return `None`, so nothing changes for them.

## Environment

Python 3.13, kloppy 3.19.1 from PyPI, tested on Windows 11.
