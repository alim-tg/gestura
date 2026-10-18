import logging
import threading
import time
from collections import deque
from typing import Iterator

import cv2

from .actions import Actions
from .camera import Camera
from .config import MODEL_PATH, Settings
from .overlay import draw
from .recognizer import Recognizer
from .tracker import Tracker

log = logging.getLogger("gestura.engine")
BANNER_SECONDS = 0.9


class Engine:
    def __init__(self, settings: Settings, actions: Actions):
        self.settings = settings
        self.actions = actions
        self.overlay = {"landmarks": True, "trails": True, "boxes": True}
        self._tracker = Tracker(settings)
        self._lock = threading.Lock()
        self._frame_ready = threading.Condition()
        self._jpeg: bytes | None = None
        self._frame_seq = 0
        self._events: deque[dict] = deque(maxlen=300)
        self._event_seq = 0
        self._banner = ("", 0.0)
        self._status = {"camera": "starting", "error": None, "fps": 0.0, "cameraFps": 0.0, "width": 0, "height": 0}
        self._hands: list[dict] = []
        self._running = False
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._running

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, name="engine", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        with self._frame_ready:
            self._frame_ready.notify_all()
        if self._thread:
            self._thread.join(timeout=3)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                **self._status,
                "hands": list(self._hands),
                "overlay": dict(self.overlay),
                "actions": self.actions.names(),
                "lastEvent": self._event_seq,
            }

    def events_after(self, last_id: int) -> list[dict]:
        with self._lock:
            return [e for e in self._events if e["id"] > last_id]

    def mjpeg(self) -> Iterator[bytes]:
        seq = 0
        while self._running:
            with self._frame_ready:
                self._frame_ready.wait_for(lambda: self._frame_seq != seq or not self._running, timeout=1.0)
                if self._frame_seq == seq or self._jpeg is None:
                    continue
                seq, jpeg = self._frame_seq, self._jpeg
            yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"

    def _run(self):
        recognizer = Recognizer(MODEL_PATH, self.settings.max_hands, self.settings.mirror)
        camera = Camera(self.settings.camera, self.settings.width, self.settings.height)
        camera.start()
        seq = 0
        last = time.monotonic()
        try:
            while self._running:
                seq, frame = camera.next_frame(seq)
                self._set_status(camera="on" if camera.on else "off", error=camera.error, cameraFps=round(camera.fps, 1))
                if frame is None:
                    continue
                self._process(recognizer, frame)
                now = time.monotonic()
                fps = 1.0 / max(now - last, 1e-6)
                last = now
                with self._lock:
                    self._status["fps"] = round(self._status["fps"] * 0.9 + fps * 0.1, 1)
        except Exception:
            log.exception("engine crashed")
            self._set_status(camera="off", error="engine crashed, see server log")
        finally:
            camera.stop()
            recognizer.close()

    def _process(self, recognizer: Recognizer, frame):
        if self.settings.mirror:
            frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        now = time.monotonic()
        hands = recognizer.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), int(now * 1000))
        for event in self._tracker.update(hands, now, w / h):
            self._publish(event)
        banner, until = self._banner
        draw(frame, self._tracker.tracks, self.overlay, banner if now < until else "")
        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            with self._frame_ready:
                self._jpeg = buffer.tobytes()
                self._frame_seq += 1
                self._frame_ready.notify_all()
        with self._lock:
            self._hands = [t.as_dict(now) for t in self._tracker.tracks]
            self._status["width"], self._status["height"] = w, h

    def _publish(self, event: dict):
        with self._lock:
            self._event_seq += 1
            event["id"] = self._event_seq
            self._events.append(event)
        log.info("%s %s #%s", event["type"], event["name"], event.get("track"))
        if event["type"] in ("gesture", "swipe"):
            self._banner = (event["name"].replace("_", " ").upper(), time.monotonic() + BANNER_SECONDS)
        if event["type"] != "action":
            self.actions.fire(event, self._on_action)

    def _on_action(self, name: str, status: str):
        self._publish({"type": "action", "name": name, "status": status, "track": None, "hand": None, "ts": time.time()})

    def _set_status(self, **values):
        with self._lock:
            self._status.update(values)
