# Gestures and tracking

All tunables live in `Settings` (`config.py`).

## Static gestures

MediaPipe's canned model gives one of `None`, `Closed_Fist`, `Open_Palm`, `Pointing_Up`, `Thumb_Down`, `Thumb_Up`, `Victory`, `ILoveYou` with a score per hand.

`Pinch` is derived by the tracker: distance between thumb tip (4) and index tip (8) divided by hand size (wrist 0 to middle MCP 9), measured in aspect-corrected coordinates. Below `pinch_ratio` (0.28) and not a `Closed_Fist`, the raw label becomes `Pinch`. It takes priority over the model's label.

A model label below `min_score` (0.6) counts as `None`.

## Motion gating

Fast movement blurs the frame and the model then reports confident but wrong gestures. Per track, speed = palm path length over the last 0.15 s divided by time, in frame heights per second (x scaled by aspect; path length, not net displacement, so back-and-forth waving still counts as fast). While speed exceeds `still_speed` (1.0) the track is `moving`: the stabilization streak is reset and no `gesture` event can fire; the stable label keeps its last value. Swipes are unaffected. The UI shows "в движении" and the video label shows `moving`.

## Stabilization

Per track, the raw label must repeat for `hold_frames` (5) consecutive still frames before it becomes the track's `gesture`. A `gesture` event is emitted once when the stable label changes to something other than `None`; holding a gesture does not repeat the event. The UI shows the raw label as "сейчас" while it differs from the stable one.

## Handedness

MediaPipe Tasks (1.1.1) labels handedness for the image as given, contrary to its docs that assume a mirrored input; confirmed on the live camera (right hand labeled `Left` in the mirrored view). So `recognizer.py` swaps Left/Right when `mirror` is on (default) and keeps the label as is with `--no-mirror`.

The per-frame label is noisy during fast motion, so a track's side is a vote: every frame both votes decay by `side_decay` (0.9) and the observed side gains its handedness score; the track shows the side with the larger vote. A few wrong frames never flip it.

## Tracking

- Palm center = mean of landmarks 0, 5, 9, 13, 17.
- Each frame, tracks and detected hands are matched greedily by distance (x scaled by aspect ratio), with +0.1 penalty when the hand's raw side differs from the track's voted side; pairs farther than `track_distance` (0.35 of frame height) are not matched.
- Unmatched hands open a new track with the next id (`hand_enter`); tracks unseen for `track_ttl` (0.5 s) are dropped (`hand_leave`).
- The center is smoothed with EMA (α 0.6) and appended to the trail, which keeps the last `trail_seconds` (1.2 s).

## Swipes

From the trail: take the points of the last `swipe_window` (0.35 s); displacement between the first and last point, x scaled by aspect ratio, so distances are in frame heights.

- Needs at least 3 points, a track older than `swipe_min_age` (0.3 s, so a hand entering the frame is not a swipe) and `swipe_cooldown` (0.8 s) since the previous swipe of that track.
- Dominant axis must exceed `swipe_distance` (0.3) and be at least twice the other axis.
- Directions are in screen space of the mirrored view: moving your hand to your right is `swipe_right`; `y` grows downward.
