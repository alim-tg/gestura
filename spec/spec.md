# gestura — product spec

Written post-factum: the app grew in one conversation (2026-10-18); this spec
records the current behavior and from here on lives by the usual rule —
updated in the same commit as the code. Technical decisions live in
[architecture.md](architecture.md); recognition and tracking rules in
[gestures.md](gestures.md).

## Problem

The owner wants to control things with hand gestures in front of a camera:
lights, music, a TV, and later the owner's harness agent (a separate
project: Telegram-driven automation with zero inbound ports). Every one
of those is a different consumer with its own protocol. Building gesture
recognition into each of them means solving the hard part — camera, model,
tracking, false positives — again and again.

gestura is the one piece that turns a camera into a stream of clean,
debounced gesture events. Consumers subscribe to the stream or receive
HTTP calls; what a gesture *means* is decided by the consumer.

## Behavior

### What it sees

- One local camera. Up to two hands at a time.
- Static gestures: open palm, fist, index up, thumb up, thumb down,
  victory, "I love you" (from the model), pinch (thumb and index tips
  together, derived).
- Dynamic gestures: swipe left, right, up, down.
- Presence: a hand entering and leaving the frame.
- For each hand: a persistent id while it stays in frame, which hand it is
  (left/right), the current gesture with confidence, palm position, speed,
  and its recent trail.

### What counts as a gesture

- A static gesture fires once, when a still hand has held it for 5
  consecutive frames (~0.25 s at 20 fps). Holding it does not repeat the
  event; changing to another gesture and back does.
- While a hand moves fast (waving, reaching), static gestures are not
  recognized at all: on blurred frames the model is confidently wrong. The
  hand's last stable gesture stays displayed but no new one fires. Swipes are
  exactly fast motion and keep working.
- A swipe fires when the palm travels about a third of the frame height in
  ~0.35 s along one dominant axis. One swipe per hand per 0.8 s. A hand that
  just entered the frame cannot swipe for 0.3 s, so walking in is not a
  swipe.
- Left/right is the owner's real hand, not the side of the picture. It is a
  vote over the hand's lifetime, so a few misread frames never flip it.
- Directions are as the owner sees the mirrored picture: moving the hand to
  the owner's right is `swipe_right`.

### What the owner sees

A local web page: the live annotated video (hand skeleton, box with id, side
and gesture, palm trail, a banner with the latest gesture), a card per hand,
the event feed including action results, and the gesture legend marking which
gestures have actions configured. Layers of the overlay can be switched off.
Both rates are shown: processing fps and camera fps.

### What consumers get

Every event has a sequential id, a type (`gesture`, `swipe`, `enter`,
`leave`, `action`), a name from a closed set, the hand id and side, and a
wall-clock timestamp. Three ways to consume:

1. **Push over HTTP (actions).** A JSON file maps event names to HTTP
   requests (URL, method, headers, body). Secrets come from environment
   variables, not the file. The result of each call shows up in the feed.
   This is how Home Assistant, a TV bridge or any webhook is driven today,
   without code changes.
2. **Pull by cursor.** `GET /api/events?after=<id>` returns everything newer
   than the cursor. Fits consumers with no inbound ports — the harness rule.
3. **Live stream.** A WebSocket pushes the full state and new events ~15
   times a second; this is what the page itself uses.

A consumer only ever sees event names and numbers — never free text, never
pixels.

## Consumers in view

| Consumer | How it would connect | Status |
|---|---|---|
| Home Assistant (lights, media players, TV integrations) | actions → HA REST services | works, example in `actions.example.json` |
| A TV directly (Samsung, LG, Android TV, CEC, IR) | actions → a small bridge, or a TV driver inside gestura | not built |
| harness | harness polls `/api/events` by cursor, turns events into InboundEvents | not built |
| Anything else with a webhook | actions | works |

### Notes for harness

- **Pull, not push.** harness keeps zero inbound ports, so it reads the event
  stream by cursor; gestura must be reachable from the harness host
  (`--host 0.0.0.0` on a trusted network, see limits below).
- **Events are not foreign text** in the prompt-injection sense: names are a
  closed enum, no string from the outside world reaches the model.
- **But a gesture is not the owner.** gestura does not know whose hand it
  sees: a guest, a child or a TV on the wall behind can produce events. A
  gesture is an unauthenticated trigger — fine for reversible actions
  (volume, lights, pause), never enough on its own for anything that needs
  the owner's confirmation.
- **Restart resets ids** (see known gaps): a cursor kept across a gestura
  restart silently misses events until the counter catches up.

## Acceptance criteria

Measured on the owner's laptop (integrated 720p webcam, Windows 11,
MediaPipe 1.1.1), 2026-10-18:

- Inference ≈ 17 ms per frame; processing keeps up with the camera
  (20/20 fps in an evening-lit room; the camera, not the model, is the
  ceiling).
- From holding a gesture to the event in the feed: ≈ 0.25 s of hold plus up
  to 66 ms of push interval.
- Waving at 1.5–3 Hz produces no static gesture events; side stays correct
  with a quarter of frames misread (synthetic test).
- An action call never stalls the video, even against a dead host
  (timeout reported as `error: ConnectTimeout` in the feed).
- The process opens no outbound connections unless actions are configured;
  the server listens on 127.0.0.1 only by default (checked with the OS
  connection table).

Verified live: hand detection, open palm, pinch, enter/leave, corrected
left/right, overlay toggles, HTTP actions against a local listener.
Not yet verified live: fast-waving suppression, swipes, two hands at once,
the remaining static gestures, distances beyond arm's length.

## Known gaps

- **Event ids are not stable across restarts.** The counter lives in memory
  and starts at 1; only the last 300 events are kept. A polling consumer
  cannot tell a restart from silence. Needs an instance id in every event
  and state, so a consumer resets its cursor when it changes.
- **No authentication.** Anyone who can reach the port can watch the camera
  and read events. Acceptable on 127.0.0.1; with `--host 0.0.0.0` it relies
  entirely on the network being trusted.
- **Distance.** The palm detector loses small hands; from a sofa 3 m away
  recognition is unreliable with a 720p camera. Not measured.
- **No activation gesture.** In front of a TV people gesticulate, eat and
  talk; without a "wake" gesture opening a short command window, false
  triggers are a matter of time. Each consumer has to tolerate that today.
- **Actions are read at startup only.** Editing `actions.json` needs a
  restart.
- **Gestures are fixed** to the model's seven plus pinch and swipes. Custom
  gestures need either a retrained classifier or a small classifier over
  the 21 landmarks the model already returns.
- **Windows needs the power-throttling opt-out**, otherwise inference is ~6×
  slower; it is applied automatically by `gestura serve`.

## What it does not do

- Does not decide what a gesture means. No TV, music or light logic inside —
  that is the consumers' job, through actions or the event stream.
- Does not identify people. No face recognition, no "only the owner's hand".
- Does not record. No video, frames or landmarks are written to disk or
  sent anywhere; the only network traffic is the actions the owner
  configured and the one-time model download.
- Does not run in the cloud. Recognition happens next to the camera; a
  remote server can consume events but cannot see the room.
- Does not support multiple cameras or more than two hands.
- Does not provide continuous controls yet (e.g. pinch-and-drag volume) —
  only discrete events.
