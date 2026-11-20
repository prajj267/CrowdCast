"""Camera pipeline: frames -> detector -> ByteTrack -> zone counts + crossings -> minute rows
(doc 09 §2; WORKFLOW 6.2.3, 6.3).

Privacy (doc 19, WORKFLOW 6.2.3): frames, boxes and track ids exist only in memory inside this
function; what it returns is per-minute, per-zone aggregates. Nothing is written to disk here.
"""

from __future__ import annotations

from collections.abc import Iterable

from shapely.geometry import Polygon

from crowdcast.aggregation.counting import (
    CrossingCounter,
    FrameStats,
    MinuteAggregator,
    RegionSpec,
    occupancy,
    orient_line,
)
from crowdcast.venue_graph.interfaces import CameraConfig
from crowdcast.vision.frames import Frame
from crowdcast.vision.interfaces import PersonDetector
from crowdcast.vision.tracking import ByteTracker

COUNT_SCORE = 0.5  # detections at/above this are "confident" for the density check


def process(
    camera: CameraConfig,
    detector: PersonDetector,
    frames: Iterable[Frame],
    sample_fps: float,
) -> list[dict[str, object]]:
    """Observation rows (zone code, minute, occupancy, flows, quality) for one camera.

    Occupancy is produced for zones with a PRIMARY region in this camera (doc 09 §8); flows
    for zones on either side of a counting line, merged into those rows.
    """
    regions = [
        RegionSpec(r.zone, list(r.polygon_px), r.coverage_fraction)
        for r in camera.regions
        if r.primary
    ]
    polygons = {r.zone: Polygon(r.polygon_px) for r in camera.regions}
    lines = [
        orient_line(
            ln.p1,
            ln.p2,
            ln.positive_side,
            ln.to if ln.positive_side == ln.from_ else ln.from_,
            polygons,
        )
        for ln in camera.lines
    ]
    tracker = ByteTracker()
    counter = CrossingCounter(lines)
    minutes = MinuteAggregator(regions, sample_fps)

    for frame in frames:
        det = detector.detect(frame.image)
        people = tracker.update(det)
        confident = det.scores >= COUNT_SCORE
        heights = (det.boxes[confident, 3] - det.boxes[confident, 1]).tolist()
        minutes.add(
            frame.time,
            FrameStats(occupancy([p.foot for p in people], regions), int(confident.sum()), heights),
        )
        counter.update(frame.time, {p.track_id: p.foot for p in people})
    return minutes.observations(counter.flows())
