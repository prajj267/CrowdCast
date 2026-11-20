"""Zone occupancy, line crossings and minute aggregation (doc 09 §6-7; WORKFLOW 6.3.1-6.3.3).

Pure logic on tracked foot points - no video, no I/O. Only aggregates leave this module:
counts per zone and minute; track ids live in memory for at most the debounce window (doc 19).

- Occupancy (§6.1): people whose FOOT point lies inside a zone's primary region; per minute
  N = median over the minute's frames / kappa (coverage fraction).
- Crossings (§6.2): the foot point changes side of a counting line, with three debounce rules:
  (1) a side only counts once the foot is more than ``band_px`` from the line;
  (2) at most one counted crossing per track, line and direction within ``window_s``;
  (3) a crossing back within ``window_s`` cancels the previous one (person stepped back).
- Quality (§7): LOW_CONFIDENCE when a minute is dense (mean detections per region > 40 or
  median box height < 25 px - doc 09's initial engineering guesses, placeholders);
  PARTIAL when fewer than half of the expected frames were processed.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import median

import numpy as np
import shapely
from shapely.geometry import Polygon

from crowdcast.common.enums import ObsQuality
from crowdcast.common.time import floor_to_minute

DENSE_MEAN_DETECTIONS = 40  # doc 09 §7 delta_max (placeholder)
DENSE_MEDIAN_BOX_HEIGHT_PX = 25  # doc 09 §7 (placeholder)
PARTIAL_FRACTION = 0.5


@dataclass(frozen=True)
class RegionSpec:
    zone: str
    polygon: list[tuple[float, float]]
    coverage: float  # kappa in (0, 1]


@dataclass(frozen=True)
class LineSpec:
    """A counting line; ``enter_zone`` is on the side where ``side_sign`` is +1."""

    p1: tuple[float, float]
    p2: tuple[float, float]
    enter_zone: str  # crossing towards the positive side enters this zone ...
    leave_zone: str  # ... and leaves this one (either may be OUTSIDE)
    side_sign: float = 1.0  # +1 if enter_zone is on the left of p1 -> p2, else -1

    def signed_distance(self, q: tuple[float, float]) -> float:
        """Positive on the ``enter_zone`` side, in pixels."""
        (x1, y1), (x2, y2) = self.p1, self.p2
        dx, dy = x2 - x1, y2 - y1
        cross = dx * (q[1] - y1) - dy * (q[0] - x1)
        return float(self.side_sign * cross / max(np.hypot(dx, dy), 1e-9))

    def within_segment(self, a: tuple[float, float], b: tuple[float, float]) -> bool:
        """Does the path a -> b cross the line between p1 and p2 (not its extension)?"""
        return bool(
            shapely.intersects(shapely.LineString([a, b]), shapely.LineString([self.p1, self.p2]))
        )


def orient_line(
    p1: tuple[float, float],
    p2: tuple[float, float],
    positive_zone: str,
    other_zone: str,
    regions: dict[str, Polygon],
) -> LineSpec:
    """Work out which geometric side is ``positive_zone`` from the camera's own regions."""
    probe = LineSpec(p1, p2, positive_zone, other_zone)
    if positive_zone in regions:
        c = regions[positive_zone].representative_point()
        sign = 1.0 if probe.signed_distance((c.x, c.y)) > 0 else -1.0
    elif other_zone in regions:
        c = regions[other_zone].representative_point()
        sign = -1.0 if probe.signed_distance((c.x, c.y)) > 0 else 1.0
    else:
        raise ValueError(
            f"line {other_zone}->{positive_zone}: neither zone has a region in this camera, "
            "so its entering side cannot be determined"
        )
    return LineSpec(p1, p2, positive_zone, other_zone, sign)


# ---------------------------------------------------------------------- per-frame occupancy
def occupancy(feet: Sequence[tuple[float, float]], regions: Sequence[RegionSpec]) -> dict[str, int]:
    """Number of foot points inside each region (6.3.1)."""
    if not feet:
        return {r.zone: 0 for r in regions}
    xs = np.array([f[0] for f in feet])
    ys = np.array([f[1] for f in feet])
    return {r.zone: int(shapely.contains_xy(Polygon(r.polygon), xs, ys).sum()) for r in regions}


# ---------------------------------------------------------------------- line crossings
@dataclass
class _TrackLineState:
    side: int  # last settled side: +1 enter side, -1 other side
    point: tuple[float, float]  # last foot position outside the band
    last: dict[int, datetime] = field(default_factory=dict)  # direction -> last counted time
    previous: tuple[datetime, int, datetime] | None = None  # (time, direction, bucket)


@dataclass(frozen=True)
class Crossing:
    time: datetime
    line: int
    direction: int  # +1 = into enter_zone, -1 = into leave_zone


class CrossingCounter:
    """Debounced crossings per line (6.3.2). Feed it every processed frame in time order."""

    def __init__(self, lines: list[LineSpec], band_px: float = 10.0, window_s: float = 10.0):
        self.lines = lines
        self.band = band_px
        self.window = timedelta(seconds=window_s)
        self.state: dict[tuple[int, int], _TrackLineState] = {}
        self.events: list[Crossing] = []

    def update(self, time: datetime, feet: dict[int, tuple[float, float]]) -> None:
        for tid, foot in feet.items():
            for li, line in enumerate(self.lines):
                d = line.signed_distance(foot)
                if abs(d) <= self.band:
                    continue  # inside the band: side unknown, wait (rule 1)
                side = 1 if d > 0 else -1
                st = self.state.get((tid, li))
                if st is None:
                    self.state[(tid, li)] = _TrackLineState(side, foot)
                    continue
                if side != st.side and line.within_segment(st.point, foot):
                    self._crossing(time, li, side, st)
                st.side, st.point = side, foot
        # forget tracks that left the scene long ago (keeps memory bounded)
        alive = set(feet)
        stale = time - self.window
        for key in [k for k, s in self.state.items() if k[0] not in alive]:
            st = self.state[key]
            if not st.last or max(st.last.values()) < stale:
                del self.state[key]

    def _crossing(self, time: datetime, li: int, direction: int, st: _TrackLineState) -> None:
        if st.previous is not None:
            t_prev, dir_prev, _ = st.previous
            if dir_prev == -direction and time - t_prev <= self.window:  # rule 3: stepped back
                self.events.remove(Crossing(t_prev, li, dir_prev))
                st.last.pop(dir_prev, None)
                st.previous = None
                return
        last = st.last.get(direction)
        if last is not None and time - last <= self.window:  # rule 2: duplicate
            return
        self.events.append(Crossing(time, li, direction))
        st.last[direction] = time
        st.previous = (time, direction, floor_to_minute(time))

    def flows(self) -> dict[tuple[datetime, str], tuple[int, int]]:
        """(minute, zone) -> (inflow, outflow) from all counted crossings."""
        out: dict[tuple[datetime, str], list[int]] = defaultdict(lambda: [0, 0])
        for c in self.events:
            line = self.lines[c.line]
            into, out_of = (
                (line.enter_zone, line.leave_zone)
                if c.direction > 0
                else (line.leave_zone, line.enter_zone)
            )
            minute = floor_to_minute(c.time)
            out[(minute, into)][0] += 1
            out[(minute, out_of)][1] += 1
        return {k: (v[0], v[1]) for k, v in out.items()}


# ---------------------------------------------------------------------- minute aggregation
@dataclass
class FrameStats:
    counts: dict[str, int]  # zone -> people in its region
    detections: int
    box_heights: list[float]


@dataclass
class MinuteAggregator:
    """Collects per-frame counts and produces one observation per (minute, zone) (6.3.3)."""

    regions: list[RegionSpec]
    sample_fps: float
    frames: dict[datetime, list[FrameStats]] = field(default_factory=lambda: defaultdict(list))

    def add(self, time: datetime, stats: FrameStats) -> None:
        self.frames[floor_to_minute(time)].append(stats)

    def observations(
        self, flows: dict[tuple[datetime, str], tuple[int, int]]
    ) -> list[dict[str, object]]:
        expected = 60 * self.sample_fps
        rows: list[dict[str, object]] = []
        for minute in sorted(self.frames):
            frames = self.frames[minute]
            heights = [h for f in frames for h in f.box_heights]
            dense = np.mean([f.detections for f in frames]) / max(
                len(self.regions), 1
            ) > DENSE_MEAN_DETECTIONS or (heights and median(heights) < DENSE_MEDIAN_BOX_HEIGHT_PX)
            quality = (
                ObsQuality.LOW_CONFIDENCE
                if dense
                else ObsQuality.PARTIAL
                if len(frames) < PARTIAL_FRACTION * expected
                else ObsQuality.OK
            )
            for r in self.regions:
                raw = median(f.counts[r.zone] for f in frames)
                fin, fout = flows.get((minute, r.zone), (0, 0))
                rows.append(
                    {
                        "zone": r.zone,
                        "bucket_start": minute,
                        "occupancy": round(raw / r.coverage),
                        "occupancy_raw": round(raw),
                        "inflow": fin,
                        "outflow": fout,
                        "mean_speed_mps": None,
                        "quality": quality.value,
                        "method": "DETECTION",
                    }
                )
        return rows
