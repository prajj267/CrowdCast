"""ByteTrack, motion-only (doc 09 §5; Zhang et al., ByteTrack, ECCV 2022; WORKFLOW 6.2.2).

Implemented here from the published algorithm instead of adding a library (deviation logged):
the method is ~150 lines and needs only scipy's assignment solver, and every step stays
explainable. No appearance features are computed, so no biometric-like vectors exist (doc 19).

Per frame:
  1. Kalman-predict every track (state: centre x/y, aspect w/h, height + their velocities).
  2. Match tracked + lost tracks to HIGH-score detections by IoU (Hungarian assignment).
  3. Match the remaining tracked tracks to LOW-score detections - ByteTrack's key step: a person
     partly occluded for a moment keeps their track instead of starting a new one.
  4. Unconfirmed tracks (seen once) get one more chance against the remaining high detections.
  5. Remaining high detections above ``new_track_thresh`` start new (unconfirmed) tracks.
  6. Tracks unmatched for more than ``track_buffer`` frames are removed.

Parameters follow doc 09 §5 (high 0.5, low 0.1, buffer 30 frames = 6 s at 5 FPS) and the
ByteTrack reference settings for the rest; the doc's "match IoU 0.8" is read as ByteTrack's
``match_thresh`` = 0.8 on the cost 1 - IoU.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count

import numpy as np
import numpy.typing as npt
from scipy.optimize import linear_sum_assignment

from crowdcast.vision.interfaces import Detections

Arr = npt.NDArray[np.float64]


# ---------------------------------------------------------------------- Kalman filter
class KalmanXYAH:
    """Constant-velocity Kalman filter on (cx, cy, aspect, height), as in SORT / ByteTrack."""

    std_pos = 1.0 / 20
    std_vel = 1.0 / 160

    def __init__(self) -> None:
        self.F = np.eye(8)
        self.F[:4, 4:] = np.eye(4)  # x += v (one frame)
        self.H = np.eye(4, 8)

    def initiate(self, z: Arr) -> tuple[Arr, Arr]:
        mean = np.r_[z, np.zeros(4)]
        h = z[3]
        std = [
            2 * self.std_pos * h,
            2 * self.std_pos * h,
            1e-2,
            2 * self.std_pos * h,
            10 * self.std_vel * h,
            10 * self.std_vel * h,
            1e-5,
            10 * self.std_vel * h,
        ]
        return mean, np.diag(np.square(std))

    def predict(self, mean: Arr, cov: Arr) -> tuple[Arr, Arr]:
        h = mean[3]
        std = [
            self.std_pos * h,
            self.std_pos * h,
            1e-2,
            self.std_pos * h,
            self.std_vel * h,
            self.std_vel * h,
            1e-5,
            self.std_vel * h,
        ]
        q = np.diag(np.square(std))
        return self.F @ mean, self.F @ cov @ self.F.T + q

    def update(self, mean: Arr, cov: Arr, z: Arr) -> tuple[Arr, Arr]:
        h = mean[3]
        r = np.diag(np.square([self.std_pos * h, self.std_pos * h, 1e-1, self.std_pos * h]))
        s = self.H @ cov @ self.H.T + r
        k = cov @ self.H.T @ np.linalg.inv(s)
        return mean + k @ (z - self.H @ mean), (np.eye(8) - k @ self.H) @ cov


def xyxy_to_xyah(b: Arr) -> Arr:
    w, h = b[2] - b[0], b[3] - b[1]
    return np.array([b[0] + w / 2, b[1] + h / 2, w / max(h, 1e-6), h])


def xyah_to_xyxy(m: Arr) -> Arr:
    w = m[2] * m[3]
    return np.array([m[0] - w / 2, m[1] - m[3] / 2, m[0] + w / 2, m[1] + m[3] / 2])


def iou_matrix(a: Arr, b: Arr) -> Arr:
    """(N, 4) x (M, 4) xyxy boxes -> (N, M) IoU."""
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return np.asarray(inter / np.maximum(area_a[:, None] + area_b[None, :] - inter, 1e-9))


def assign(cost: Arr, thresh: float) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Hungarian assignment keeping pairs with cost <= thresh -> (matches, free rows, free cols)."""
    if cost.size == 0:
        return [], list(range(cost.shape[0])), list(range(cost.shape[1]))
    rows, cols = linear_sum_assignment(cost)
    matches = [(int(r), int(c)) for r, c in zip(rows, cols, strict=True) if cost[r, c] <= thresh]
    mr = {r for r, _ in matches}
    mc = {c for _, c in matches}
    return (
        matches,
        [r for r in range(cost.shape[0]) if r not in mr],
        [c for c in range(cost.shape[1]) if c not in mc],
    )


# ---------------------------------------------------------------------- tracks
@dataclass
class Track:
    track_id: int
    mean: Arr
    cov: Arr
    score: float
    confirmed: bool
    last_seen: int  # frame number of the last match
    hits: int = 1

    @property
    def box(self) -> Arr:
        return xyah_to_xyxy(self.mean)

    @property
    def foot(self) -> tuple[float, float]:
        """Bottom-centre of the box: where the person stands (doc 09 §6.1)."""
        b = self.box
        return float((b[0] + b[2]) / 2), float(b[3])


@dataclass(frozen=True)
class TrackedPerson:
    """What leaves the tracker: an ephemeral id and geometry only (no image content)."""

    track_id: int
    box: tuple[float, float, float, float]
    foot: tuple[float, float]
    score: float


@dataclass
class ByteTracker:
    track_thresh: float = 0.5  # high / low split (doc 09 §5)
    low_thresh: float = 0.1  # below this a detection is ignored (doc 09 §5)
    new_track_thresh: float = 0.6  # ByteTrack: track_thresh + 0.1
    match_thresh: float = 0.8  # max cost 1 - IoU in the first association
    low_match_thresh: float = 0.5  # ByteTrack reference value for the second association
    unconfirmed_match_thresh: float = 0.7
    track_buffer: int = 30  # frames a lost track is kept (6 s at 5 FPS, doc 09 §5)
    kf: KalmanXYAH = field(default_factory=KalmanXYAH)
    tracks: list[Track] = field(default_factory=list)
    frame: int = 0
    _ids: count[int] = field(default_factory=lambda: count(1))

    def update(self, det: Detections) -> list[TrackedPerson]:
        """Advance one frame; returns the confirmed tracks matched in this frame."""
        self.frame += 1
        boxes = det.boxes.astype(np.float64)
        scores = det.scores.astype(np.float64)
        high = np.flatnonzero(scores >= self.track_thresh)
        low = np.flatnonzero((scores >= self.low_thresh) & (scores < self.track_thresh))

        for t in self.tracks:
            t.mean, t.cov = self.kf.predict(t.mean, t.cov)
        confirmed = [t for t in self.tracks if t.confirmed]
        unconfirmed = [t for t in self.tracks if not t.confirmed]
        matched: set[int] = set()

        def apply(t: Track, d: int) -> None:
            t.mean, t.cov = self.kf.update(t.mean, t.cov, xyxy_to_xyah(boxes[d]))
            t.score = float(scores[d])
            t.last_seen = self.frame
            t.hits += 1
            matched.add(t.track_id)

        # 1. confirmed tracks (tracked + recently lost) vs high-score detections
        pool = confirmed
        cost = 1 - iou_matrix(np.array([t.box for t in pool]).reshape(-1, 4), boxes[high])
        m1, free_t, free_high = assign(cost, self.match_thresh)
        for r, c in m1:
            apply(pool[r], int(high[c]))
        # 2. still-unmatched tracks that were seen last frame vs low-score detections
        pool2 = [pool[r] for r in free_t if pool[r].last_seen == self.frame - 1]
        cost = 1 - iou_matrix(np.array([t.box for t in pool2]).reshape(-1, 4), boxes[low])
        for r, c in assign(cost, self.low_match_thresh)[0]:
            apply(pool2[r], int(low[c]))
        # 3. unconfirmed tracks vs remaining high detections
        rest = high[free_high]
        cost = 1 - iou_matrix(np.array([t.box for t in unconfirmed]).reshape(-1, 4), boxes[rest])
        m3, _, free_rest = assign(cost, self.unconfirmed_match_thresh)
        for r, c in m3:
            apply(unconfirmed[r], int(rest[c]))
            unconfirmed[r].confirmed = True
        # 4. new tracks; drop unconfirmed tracks that missed their second chance
        self.tracks = [t for t in self.tracks if t.confirmed or t.track_id in matched]
        for c in free_rest:
            d = int(rest[c])
            if scores[d] >= self.new_track_thresh:
                mean, cov = self.kf.initiate(xyxy_to_xyah(boxes[d]))
                self.tracks.append(
                    Track(
                        next(self._ids),
                        mean,
                        cov,
                        float(scores[d]),
                        confirmed=self.frame == 1,
                        last_seen=self.frame,
                    )
                )
        # 5. forget tracks lost for too long
        self.tracks = [t for t in self.tracks if self.frame - t.last_seen <= self.track_buffer]

        return [
            TrackedPerson(t.track_id, tuple(float(v) for v in t.box), t.foot, t.score)  # type: ignore[arg-type]
            for t in self.tracks
            if t.confirmed and t.last_seen == self.frame
        ]
