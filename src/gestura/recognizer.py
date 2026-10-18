from dataclasses import dataclass
from pathlib import Path

import mediapipe as mp
import numpy as np

SWAP_SIDE = {"Left": "Right", "Right": "Left"}


@dataclass
class Hand:
    landmarks: np.ndarray
    handedness: str
    side_score: float
    gesture: str
    score: float


class Recognizer:
    def __init__(self, model_path: Path, max_hands: int, mirrored: bool):
        options = mp.tasks.vision.GestureRecognizerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=max_hands,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.5,
        )
        self._recognizer = mp.tasks.vision.GestureRecognizer.create_from_options(options)
        self._mirrored = mirrored
        self._last_ts = 0

    def process(self, rgb: np.ndarray, ts_ms: int) -> list[Hand]:
        ts_ms = max(ts_ms, self._last_ts + 1)
        self._last_ts = ts_ms
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        result = self._recognizer.recognize_for_video(image, ts_ms)
        hands = []
        for i, landmarks in enumerate(result.hand_landmarks):
            points = np.array([[p.x, p.y, p.z] for p in landmarks], dtype=np.float32)
            side_top = result.handedness[i][0] if i < len(result.handedness) and result.handedness[i] else None
            side = side_top.category_name if side_top else "Unknown"
            if self._mirrored:
                side = SWAP_SIDE.get(side, side)
            top = result.gestures[i][0] if i < len(result.gestures) and result.gestures[i] else None
            gesture = top.category_name if top and top.category_name else "None"
            hands.append(Hand(points, side, float(side_top.score) if side_top else 0.0, gesture, float(top.score) if top else 0.0))
        return hands

    def close(self):
        self._recognizer.close()
