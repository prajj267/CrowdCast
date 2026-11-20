"""Camera YAML format, version 1 (WORKFLOW 6.1.2; spec in doc 12 §6.3).

One file per camera: the recorded video, the event time of its first frame, the zone regions
it sees (pixel polygons) and its counting lines. Like the venue and event formats, it lives in
the venue-graph module and is checked against the venue it belongs to.

Rules (doc 09 §6, §8): each region names a venue zone; at most one PRIMARY region per zone
(the camera whose count is used for occupancy); each counting line observes one connection of
the venue graph and names which side of the line is the "entering" side.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator
from shapely.geometry import LineString, Polygon

from crowdcast.common.time import ensure_utc
from crowdcast.venue_graph.config import OUTSIDE, VenueConfig, ZoneCode

Point = tuple[float, float]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CameraInfo(_Strict):
    code: str = Field(pattern=r"^[A-Z0-9_]{1,16}$")
    venue: str = Field(min_length=1)  # venue file stem in configs/venues/
    source: str = Field(min_length=1)  # video path relative to the repo root (git-ignored)
    recording_start: AwareDatetime  # event time of frame 0
    sample_fps: float = Field(5.0, gt=0, le=30)  # doc 09 §3 default 5 FPS
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    detector: Literal["yolox_nano", "yolox_tiny", "yolox_s"] = "yolox_s"
    tiled: bool = True  # tiled detection for small, distant people (task 1.4.3)

    _utc = field_validator("recording_start")(ensure_utc)


class Region(_Strict):
    zone: ZoneCode
    polygon_px: list[Point] = Field(min_length=3, max_length=100)
    coverage_fraction: float = Field(1.0, gt=0, le=1)  # kappa: visible share of the zone
    primary: bool = True

    @field_validator("polygon_px")
    @classmethod
    def _simple(cls, v: list[Point]) -> list[Point]:
        if not Polygon(v).is_valid or Polygon(v).area <= 0:
            raise ValueError("polygon_px must be a simple, non-self-intersecting area")
        return v


class Line(_Strict):
    from_: ZoneCode = Field(alias="from")  # the connection this line observes (OUTSIDE allowed)
    to: ZoneCode
    p1: Point
    p2: Point
    positive_side: ZoneCode  # crossing toward this side of the line = entering this zone

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if LineString([self.p1, self.p2]).length <= 0:
            raise ValueError("counting line needs two different points")
        if self.positive_side not in (self.from_, self.to):
            raise ValueError("positive_side must be one end of the connection")
        return self


class CameraConfig(_Strict):
    format_version: Literal[1]
    camera: CameraInfo
    regions: list[Region] = Field(default_factory=list)
    lines: list[Line] = Field(default_factory=list)

    @model_validator(mode="after")
    def _in_image(self) -> Self:
        w, h = self.camera.image_width, self.camera.image_height
        points = [p for r in self.regions for p in r.polygon_px] + [
            p for ln in self.lines for p in (ln.p1, ln.p2)
        ]
        bad = [p for p in points if not (0 <= p[0] <= w and 0 <= p[1] <= h)]
        if bad:
            raise ValueError(f"points outside the {w}x{h} image: {bad[:3]}")
        primaries = [r.zone for r in self.regions if r.primary]
        dup = sorted({z for z in primaries if primaries.count(z) > 1})
        if dup:
            raise ValueError(f"more than one primary region for zones {dup}")
        return self

    def check_against_venue(self, venue: VenueConfig) -> None:
        """Raise ValueError if a region or line refers to something the venue does not have."""
        codes = {z.code for z in venue.zones}
        unknown = sorted({r.zone for r in self.regions} - codes)
        if unknown:
            raise ValueError(f"regions name zones not in the venue: {unknown}")
        edges = set(venue.directed_edges())
        for ln in self.lines:
            for end in (ln.from_, ln.to):
                if end != OUTSIDE and end not in codes:
                    raise ValueError(f"line {ln.from_}->{ln.to}: unknown zone {end}")
            if (ln.from_, ln.to) not in edges and (ln.to, ln.from_) not in edges:
                raise ValueError(f"line {ln.from_}->{ln.to}: no such connection in the venue")


def load_camera_config(path: Path) -> CameraConfig:
    with path.open(encoding="utf-8") as fh:
        return CameraConfig.model_validate(yaml.safe_load(fh))
