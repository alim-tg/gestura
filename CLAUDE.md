# CLAUDE.md

gestura: local web app that recognizes hand gestures from the webcam (MediaPipe GestureRecognizer), tracks hands with persistent ids and trails, detects swipes and pinch, shows the annotated video with live events in the browser, and fires HTTP actions per gesture.

The specification lives in `spec/` and is the source of truth: `architecture.md` (modules, API, events, actions), `gestures.md` (recognition, stabilization, tracking, swipes). Update the relevant spec file in the same change as the code. `README.md` is the quickstart only.

## Commands

```powershell
.venv\Scripts\gestura serve                 # http://127.0.0.1:8800
.venv\Scripts\gestura serve --camera 1 --hands 1 --no-mirror
.venv\Scripts\gestura model                 # download models/gesture_recognizer.task
```

Install: `uv venv .venv --python 3.12` then `uv pip install --python .venv\Scripts\python.exe -e .`. The app does not hot-reload; restart it after code changes.

## Rules

- Never write comments or docstrings in code.
- Python 3.12, FastAPI + vanilla JS in `src/gestura/web`.
- The camera lives on its own thread (`camera.py`); MediaPipe runs only on the engine thread; the server only reads snapshots.
- Keep `disable_power_throttling()` at startup: without it Windows EcoQoS makes inference ~6× slower. Benchmarks run outside `gestura serve` must call it too, or they measure the throttled CPU.
- Actions never block the camera loop.
- Verify UI changes in the browser (Chrome tools) before reporting them done.
