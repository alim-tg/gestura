from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "models"
MODEL_PATH = MODELS / "gesture_recognizer.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task"
ACTIONS_PATH = ROOT / "actions.json"


@dataclass
class Settings:
    camera: int = 0
    width: int = 1280
    height: int = 720
    mirror: bool = True
    max_hands: int = 2
    min_score: float = 0.6
    hold_frames: int = 5
    still_speed: float = 1.0
    side_decay: float = 0.9
    pinch_ratio: float = 0.28
    swipe_window: float = 0.35
    swipe_distance: float = 0.3
    swipe_cooldown: float = 0.8
    swipe_min_age: float = 0.3
    track_distance: float = 0.35
    track_ttl: float = 0.5
    trail_seconds: float = 1.2
    host: str = "127.0.0.1"
    port: int = 8800
