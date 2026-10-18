import cv2
import numpy as np

from .tracker import Track

CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]
PALETTE = [(240, 201, 76), (133, 37, 247), (93, 243, 184), (3, 183, 255)]
FONT = cv2.FONT_HERSHEY_SIMPLEX
INK = (22, 17, 14)


def track_color(track_id: int) -> tuple[int, int, int]:
    return PALETTE[(track_id - 1) % len(PALETTE)]


def draw(frame: np.ndarray, tracks: list[Track], options: dict, banner: str):
    h, w = frame.shape[:2]
    for track in tracks:
        color = track_color(track.id)
        points = [(int(x * w), int(y * h)) for x, y in track.landmarks[:, :2]]
        if options.get("trails") and len(track.trail) > 1:
            _trail(frame, [(int(x * w), int(y * h)) for _, x, y in track.trail], color)
        if options.get("landmarks"):
            for a, b in CONNECTIONS:
                cv2.line(frame, points[a], points[b], (255, 255, 255), 2, cv2.LINE_AA)
            for point in points:
                cv2.circle(frame, point, 4, color, -1, cv2.LINE_AA)
        if options.get("boxes"):
            _box(frame, track, points, color)
    if banner:
        _banner(frame, banner)


def _trail(frame: np.ndarray, trail: list[tuple[int, int]], color: tuple[int, int, int]):
    n = len(trail)
    for i in range(1, n):
        cv2.line(frame, trail[i - 1], trail[i], color, max(1, int(1 + 7 * i / n)), cv2.LINE_AA)
    cv2.circle(frame, trail[-1], 7, color, -1, cv2.LINE_AA)


def _box(frame: np.ndarray, track: Track, points: list[tuple[int, int]], color: tuple[int, int, int]):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    x0, y0, x1, y1 = min(xs) - 20, min(ys) - 20, max(xs) + 20, max(ys) + 20
    cv2.rectangle(frame, (x0, y0), (x1, y1), color, 2, cv2.LINE_AA)
    text = f"#{track.id} {track.handedness}  {track.label}"
    if track.moving:
        text += "  moving"
    elif track.label not in ("None", "Pinch"):
        text += f" {track.score:.0%}"
    (tw, th), _ = cv2.getTextSize(text, FONT, 0.6, 2)
    top = max(y0, th + 12)
    cv2.rectangle(frame, (x0, top - th - 12), (x0 + tw + 12, top), color, -1)
    cv2.putText(frame, text, (x0 + 6, top - 7), FONT, 0.6, INK, 2, cv2.LINE_AA)


def _banner(frame: np.ndarray, text: str):
    w = frame.shape[1]
    (tw, th), _ = cv2.getTextSize(text, FONT, 1.3, 3)
    x, y = (w - tw) // 2, 30 + th
    region = frame[y - th - 16:y + 18, x - 20:x + tw + 20]
    region[:] = (region * 0.35).astype(np.uint8)
    cv2.putText(frame, text, (x, y), FONT, 1.3, (255, 255, 255), 3, cv2.LINE_AA)
