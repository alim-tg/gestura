import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from .config import Settings
from .recognizer import Hand

PALM = [0, 5, 9, 13, 17]
SMOOTHING = 0.6
SPEED_WINDOW = 0.15


@dataclass
class Track:
    id: int
    handedness: str
    x: float
    y: float
    born: float
    seen: float
    landmarks: np.ndarray
    raw: str = "None"
    score: float = 0.0
    label: str = "None"
    candidate: str = "None"
    streak: int = 0
    last_swipe: float = 0.0
    speed: float = 0.0
    moving: bool = False
    trail: deque = field(default_factory=deque)
    side_votes: dict = field(default_factory=lambda: {"Left": 0.0, "Right": 0.0})

    def as_dict(self, now: float) -> dict:
        return {
            "id": self.id,
            "hand": self.handedness,
            "gesture": self.label,
            "raw": self.raw,
            "moving": self.moving,
            "speed": round(self.speed, 2),
            "score": round(self.score, 3),
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "age": round(now - self.born, 1),
        }


class Tracker:
    def __init__(self, settings: Settings):
        self.s = settings
        self.tracks: list[Track] = []
        self._next_id = 1

    def update(self, hands: list[Hand], now: float, aspect: float) -> list[dict]:
        events = []
        centers = [hand.landmarks[PALM, :2].mean(axis=0) for hand in hands]
        pairs = sorted(
            (self._distance(track, hand, center, aspect), ti, hi)
            for ti, track in enumerate(self.tracks)
            for hi, (hand, center) in enumerate(zip(hands, centers))
        )
        used_tracks, assignment = set(), {}
        for distance, ti, hi in pairs:
            if distance > self.s.track_distance or ti in used_tracks or hi in assignment:
                continue
            used_tracks.add(ti)
            assignment[hi] = self.tracks[ti]

        for hi, (hand, center) in enumerate(zip(hands, centers)):
            track = assignment.get(hi)
            if track is None:
                track = Track(self._next_id, hand.handedness, float(center[0]), float(center[1]), now, now, hand.landmarks)
                self._next_id += 1
                self.tracks.append(track)
                events.append(self._event("enter", "hand_enter", track))
            self._advance(track, hand, center, now, aspect, events)

        for track in [t for t in self.tracks if now - t.seen > self.s.track_ttl]:
            self.tracks.remove(track)
            events.append(self._event("leave", "hand_leave", track))
        return events

    def _distance(self, track: Track, hand: Hand, center: np.ndarray, aspect: float) -> float:
        dx = (track.x - center[0]) * aspect
        dy = track.y - center[1]
        penalty = 0.1 if hand.handedness != track.handedness else 0.0
        return float(np.hypot(dx, dy)) + penalty

    def _advance(self, track: Track, hand: Hand, center: np.ndarray, now: float, aspect: float, events: list[dict]):
        track.x += (float(center[0]) - track.x) * SMOOTHING
        track.y += (float(center[1]) - track.y) * SMOOTHING
        track.seen = now
        track.landmarks = hand.landmarks
        track.handedness = self._vote_side(track, hand)
        track.trail.append((now, track.x, track.y))
        while track.trail and now - track.trail[0][0] > self.s.trail_seconds:
            track.trail.popleft()
        track.speed = self._speed(track, now, aspect)
        track.moving = track.speed > self.s.still_speed

        track.raw = self._classify(hand, aspect)
        track.score = 1.0 if track.raw == "Pinch" else hand.score
        if track.moving:
            track.candidate, track.streak = "None", 0
        elif track.raw == track.candidate:
            track.streak += 1
        else:
            track.candidate, track.streak = track.raw, 1
        if not track.moving and track.streak >= self.s.hold_frames and track.candidate != track.label:
            track.label = track.candidate
            if track.label != "None":
                events.append(self._event("gesture", track.label, track))

        swipe = self._swipe(track, now, aspect)
        if swipe:
            events.append(self._event("swipe", swipe, track))

    def _vote_side(self, track: Track, hand: Hand) -> str:
        votes = track.side_votes
        for side in votes:
            votes[side] *= self.s.side_decay
        if hand.handedness in votes:
            votes[hand.handedness] += hand.side_score
        best = max(votes, key=votes.get)
        return best if votes[best] > 0 else hand.handedness

    def _speed(self, track: Track, now: float, aspect: float) -> float:
        window = [p for p in track.trail if now - p[0] <= SPEED_WINDOW]
        if len(window) < 2 or window[-1][0] <= window[0][0]:
            return 0.0
        path = sum(
            float(np.hypot((b[1] - a[1]) * aspect, b[2] - a[2]))
            for a, b in zip(window, window[1:])
        )
        return path / (window[-1][0] - window[0][0])

    def _classify(self, hand: Hand, aspect: float) -> str:
        points = hand.landmarks[:, :2] * np.array([aspect, 1.0], dtype=np.float32)
        scale = float(np.linalg.norm(points[9] - points[0])) or 1e-6
        pinch = float(np.linalg.norm(points[4] - points[8])) / scale
        if pinch < self.s.pinch_ratio and hand.gesture != "Closed_Fist":
            return "Pinch"
        return hand.gesture if hand.score >= self.s.min_score else "None"

    def _swipe(self, track: Track, now: float, aspect: float) -> str | None:
        if now - track.born < self.s.swipe_min_age or now - track.last_swipe < self.s.swipe_cooldown:
            return None
        window = [p for p in track.trail if now - p[0] <= self.s.swipe_window]
        if len(window) < 3:
            return None
        dx = (window[-1][1] - window[0][1]) * aspect
        dy = window[-1][2] - window[0][2]
        if max(abs(dx), abs(dy)) < self.s.swipe_distance:
            return None
        if abs(dx) > 2 * abs(dy):
            name = "swipe_right" if dx > 0 else "swipe_left"
        elif abs(dy) > 2 * abs(dx):
            name = "swipe_down" if dy > 0 else "swipe_up"
        else:
            return None
        track.last_swipe = now
        return name

    def _event(self, kind: str, name: str, track: Track) -> dict:
        return {"type": kind, "name": name, "track": track.id, "hand": track.handedness, "ts": time.time()}
