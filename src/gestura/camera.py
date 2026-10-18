import logging
import sys
import threading
import time

import cv2
import numpy as np

log = logging.getLogger("gestura.camera")


class Camera:
    def __init__(self, index: int, width: int, height: int):
        self.index = index
        self.width = width
        self.height = height
        self.error: str | None = None
        self.fps = 0.0
        self._cond = threading.Condition()
        self._frame: np.ndarray | None = None
        self._seq = 0
        self._running = False
        self._thread: threading.Thread | None = None

    @property
    def on(self) -> bool:
        return self.error is None and self._seq > 0

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        with self._cond:
            self._cond.notify_all()
        if self._thread:
            self._thread.join(timeout=3)

    def next_frame(self, after: int, timeout: float = 1.0) -> tuple[int, np.ndarray | None]:
        with self._cond:
            self._cond.wait_for(lambda: self._seq != after or not self._running, timeout=timeout)
            return self._seq, self._frame if self._seq != after else None

    def _run(self):
        while self._running:
            try:
                cap = self._open()
            except RuntimeError as e:
                self._fail(str(e))
                time.sleep(2)
                continue
            self.error = None
            last = time.monotonic()
            try:
                while self._running:
                    ok, frame = cap.read()
                    if not ok:
                        self._fail("camera stopped delivering frames")
                        time.sleep(1)
                        break
                    now = time.monotonic()
                    self.fps = self.fps * 0.9 + 0.1 / max(now - last, 1e-6)
                    last = now
                    with self._cond:
                        self._frame = frame
                        self._seq += 1
                        self._cond.notify_all()
            finally:
                cap.release()

    def _open(self) -> cv2.VideoCapture:
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        cap = cv2.VideoCapture(self.index, backend)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"camera {self.index} is not available")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        log.info("camera %s opened", self.index)
        return cap

    def _fail(self, message: str):
        if message != self.error:
            log.warning(message)
        self.error = message
