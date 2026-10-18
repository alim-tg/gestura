# Architecture

One process, three threads of work:

```
webcam ─► camera thread (latest frame) ─► engine thread: mirror ─► MediaPipe GestureRecognizer ─► Tracker ─► overlay ─► JPEG
                                                                                  │
                                                                                  ▼
                                                                    events (deque, ids) ─► Actions (HTTP, thread pool)
FastAPI (uvicorn):  /stream.mjpg ◄─ latest JPEG      /ws ◄─ state + new events, 15 Hz
```

## Modules (`src/gestura`)

| Module | Role |
|---|---|
| `config.py` | `Settings` dataclass with every tunable, paths (`models/`, `actions.json`) |
| `model.py` | downloads `gesture_recognizer.task` (MediaPipe, float16, ~8 MB) into `models/` if missing |
| `recognizer.py` | wraps MediaPipe Tasks `GestureRecognizer` in VIDEO mode; returns `Hand(landmarks[21x3], handedness, gesture, score)` |
| `tracker.py` | persistent hand ids, smoothed palm center, trail, gesture stabilization, pinch, swipes; emits events |
| `overlay.py` | draws skeleton, trail, box and label per track, plus a banner for the latest gesture/swipe |
| `camera.py` | capture thread: opens the webcam, keeps only the latest frame, reconnects on failure |
| `engine.py` | processing thread: owns recognizer and tracker, takes the latest frame, publishes JPEG frames, state and events |
| `actions.py` | maps event names to HTTP requests from `actions.json` |
| `server.py` | FastAPI app: page, MJPEG, WebSocket, REST |
| `power.py` | opts the process out of Windows power throttling |
| `cli.py` | `gestura serve`, `gestura model` |
| `web/` | vanilla JS UI |

## Camera

The camera is read on its own thread so capture never waits for inference. The engine waits on the camera's frame counter and always processes the newest frame, dropping older ones if it falls behind; the UI shows both rates (`fps` processing, `cameraFps` capture).

## Power throttling (Windows)

`gestura serve` opts the process out of Windows power throttling (EcoQoS) via `SetProcessInformation(ProcessPowerThrottling)` (`power.py`). Without it, a windowless process that idles even briefly between frames gets throttled and MediaPipe inference drops from ≈17 ms to ≈110 ms per frame (measured on a hybrid 20-thread laptop CPU, MediaPipe 1.1.1), which looked like the camera slowing inference down.

OpenCV `VideoCapture` (DirectShow on Windows, buffer size 1). The MJPG fourcc is set last, after resolution and fps: setting either of those afterwards silently switches DirectShow back to uncompressed YUY2, which caps an integrated 720p webcam at ~10 fps instead of 25–30. The frame is flipped horizontally when `mirror` is on (default); handedness is corrected for that in `recognizer.py` (see [gestures.md](gestures.md#handedness)). If the camera is missing or stops delivering frames the engine reports `camera: "off"` with an `error` and retries.

## HTTP API

| Endpoint | Description |
|---|---|
| `GET /` | UI |
| `GET /stream.mjpg` | annotated video, `multipart/x-mixed-replace` |
| `GET /api/state` | snapshot (see below) |
| `GET /api/events?after=ID` | events with id greater than `ID` (last 300 kept) |
| `POST /api/overlay` | `{landmarks?, trails?, boxes?}` toggles overlay layers |
| `WS /ws` | every ~66 ms: `{state, events}` where `events` are new since the previous message |

State:

```json
{
  "camera": "on", "error": null, "fps": 28.4, "cameraFps": 29.9, "width": 1280, "height": 720,
  "hands": [{"id": 3, "hand": "Right", "gesture": "Thumb_Up", "raw": "Thumb_Up", "moving": false, "speed": 0.12, "score": 0.93, "x": 0.52, "y": 0.41, "age": 4.2}],
  "overlay": {"landmarks": true, "trails": true, "boxes": true},
  "actions": ["Thumb_Up", "swipe_right"],
  "lastEvent": 57
}
```

`x`, `y` are the smoothed palm center, normalized to the displayed (mirrored) frame.

## Events

```json
{"id": 57, "type": "gesture", "name": "Thumb_Up", "track": 3, "hand": "Right", "ts": 1760781234.12}
```

| type | names |
|---|---|
| `gesture` | `Open_Palm`, `Closed_Fist`, `Pointing_Up`, `Thumb_Up`, `Thumb_Down`, `Victory`, `ILoveYou`, `Pinch` |
| `swipe` | `swipe_left`, `swipe_right`, `swipe_up`, `swipe_down` |
| `enter` / `leave` | `hand_enter`, `hand_leave` |
| `action` | name of the fired rule, plus `status` (HTTP code or `error: ...`) |

Gesture semantics are in [gestures.md](gestures.md).

## Actions

`actions.json` in the project root (optional, git-ignored; template `actions.example.json`). Keys are event names, values:

| Field | Default | |
|---|---|---|
| `url` | required | `${VAR}` is expanded from the environment |
| `method` | `POST` | |
| `headers` | none | values expanded from the environment |
| `json` | the event itself | body to send; omit to forward the event |
| `timeout` | 3 | seconds |

Requests run in a 4-thread pool so a slow server never stalls the camera loop; each result is published as an `action` event. `action` events never trigger actions. The file is read at startup.
