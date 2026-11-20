"""ByteTrack tests on synthetic boxes (WORKFLOW 6.2.2; doc 09 §5)."""

from __future__ import annotations

import numpy as np
import pytest

from crowdcast.vision.interfaces import Detections
from crowdcast.vision.tracking import ByteTracker, assign, iou_matrix


def dets(*items: tuple[float, float, float]) -> Detections:
    """(x, y, score) -> a 20 x 50 person box whose top-left corner is (x, y)."""
    if not items:
        return Detections.empty()
    boxes = np.array([[x, y, x + 20, y + 50] for x, y, _ in items], np.float32)
    return Detections(boxes, np.array([s for _, _, s in items], np.float32))


def test_iou_and_assignment() -> None:
    a = np.array([[0, 0, 10, 10]], float)
    b = np.array([[0, 0, 10, 10], [5, 0, 15, 10], [50, 50, 60, 60]], float)
    np.testing.assert_allclose(iou_matrix(a, b), [[1.0, 50 / 150, 0.0]])
    matches, free_r, free_c = assign(1 - iou_matrix(a, b), 0.8)
    assert matches == [(0, 0)] and free_r == [] and free_c == [1, 2]


def test_two_walkers_keep_their_ids() -> None:
    tr = ByteTracker()
    ids = []
    for f in range(20):
        out = tr.update(dets((100 + 3 * f, 100, 0.9), (400 - 3 * f, 300, 0.85)))
        ids.append(sorted((round(p.foot[0]), p.track_id) for p in out))
    first = {i for _, i in ids[0]}
    assert len(first) == 2 and all({i for _, i in frame} == first for frame in ids)


def test_low_score_detection_keeps_an_occluded_track() -> None:
    """ByteTrack's second association: a dip below 0.5 does not lose the person."""
    tr = ByteTracker()
    for f in range(5):
        (p,) = tr.update(dets((100 + 2 * f, 100, 0.9)))
    tid = p.track_id
    (p,) = tr.update(dets((110, 100, 0.3)))  # partly occluded: low score
    assert p.track_id == tid
    (p,) = tr.update(dets((112, 100, 0.9)))
    assert p.track_id == tid


def test_track_survives_short_gap_but_not_beyond_buffer() -> None:
    tr = ByteTracker(track_buffer=5)
    for f in range(5):
        (p,) = tr.update(dets((100 + 2 * f, 100, 0.9)))
    tid = p.track_id
    for _ in range(3):  # missed for 3 frames (< buffer)
        assert tr.update(Detections.empty()) == []
    (p,) = tr.update(dets((116, 100, 0.9)))  # where the motion model expects it
    assert p.track_id == tid
    for _ in range(7):  # now lost for longer than the buffer
        tr.update(Detections.empty())
    assert tr.tracks == []


def test_weak_detections_do_not_start_tracks_and_new_tracks_need_confirmation() -> None:
    tr = ByteTracker()
    tr.update(dets((100, 100, 0.9)))  # frame 1: confirmed at once (ByteTrack convention)
    assert tr.update(dets((100, 100, 0.9), (300, 300, 0.55))) != []  # 0.55 < new-track 0.6
    assert len(tr.tracks) == 1
    out = tr.update(dets((100, 100, 0.9), (300, 300, 0.95)))  # first sighting: unconfirmed
    assert len(out) == 1
    out = tr.update(dets((100, 100, 0.9), (301, 300, 0.95)))  # second sighting: confirmed
    assert len(out) == 2


def test_output_is_geometry_only() -> None:
    (p,) = ByteTracker().update(dets((100, 100, 0.9)))
    assert set(vars(p)) == {"track_id", "box", "foot", "score"}  # no image content
    assert p.foot == pytest.approx((110, 150))
