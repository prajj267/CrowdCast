"""Venue YAML format, version 1 (WORKFLOW 2.1.1; specification in doc 12 §6.1).

These Pydantic models both *define* the format and *validate* a file. Field limits mirror the
database columns (doc 13) and the zone rules of the API (doc 14 §3.7), so a file that passes here
can be loaded into PostgreSQL without constraint errors.

Scope of this module: field-level rules and cross-references *within one file* (codes unique,
connections point at existing zones, no duplicate directed edges). Whole-graph rules such as
reachability from/to the outside are checked by the graph module (doc 11 §9, task 2.2.1).
"""

from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from shapely.geometry import Polygon

from crowdcast.common.enums import ZoneType

FORMAT_VERSION = 1
OUTSIDE = "OUTSIDE"  # the virtual node omega (doc 11 §1); stored as NULL zone_id in the DB
DEFAULT_THRESHOLDS = {"elevated": 0.60, "high": 0.80, "critical": 0.95}  # doc 11 §4

ZoneCode = Annotated[str, Field(pattern=r"^[A-Z0-9_]{1,16}$")]


class _Strict(BaseModel):
    # Unknown keys are errors, so a typo such as "capcity" is caught instead of ignored.
    model_config = ConfigDict(extra="forbid", frozen=True)


class Thresholds(_Strict):
    """Occupancy-ratio thresholds u = N / C (doc 11 §4). Unset values take the defaults."""

    elevated: float | None = Field(None, gt=0, lt=10)
    high: float | None = Field(None, gt=0, lt=10)
    critical: float | None = Field(None, gt=0, lt=10)

    def resolved(self) -> tuple[float, float, float]:
        e = self.elevated if self.elevated is not None else DEFAULT_THRESHOLDS["elevated"]
        h = self.high if self.high is not None else DEFAULT_THRESHOLDS["high"]
        c = self.critical if self.critical is not None else DEFAULT_THRESHOLDS["critical"]
        return e, h, c

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        e, h, c = self.resolved()
        if not e < h < c:
            raise ValueError(f"thresholds must satisfy elevated < high < critical, got {e}/{h}/{c}")
        return self


class ZoneConfig(_Strict):
    code: ZoneCode
    name: str = Field(min_length=1)
    type: ZoneType
    area_m2: float = Field(gt=0, lt=1e8)  # usable area A_i, excluding stages/stalls (doc 11 §2)
    capacity: int | None = Field(None, gt=0)  # C_i; null -> floor(A_i * rho_plan)
    polygon: list[tuple[float, float]] = Field(min_length=3, max_length=100)
    thresholds: Thresholds = Thresholds()

    @field_validator("polygon")
    @classmethod
    def _valid_polygon(cls, v: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if not all(math.isfinite(x) and math.isfinite(y) for x, y in v):
            raise ValueError("polygon coordinates must be finite numbers")
        shape = Polygon(v)
        if not shape.is_valid or shape.area <= 0:
            raise ValueError("polygon must be a simple, non-self-intersecting area")
        return v


class ConnectionConfig(_Strict):
    from_: ZoneCode = Field(alias="from")
    to: ZoneCode
    width_m: float = Field(gt=0, lt=10_000)  # boundary width w_ji (doc 11 §3)
    travel_time_s: int = Field(gt=0)  # typical travel time tau_ji
    bidirectional: bool = True

    def directed_edges(self) -> list[tuple[str, str]]:
        edges = [(self.from_, self.to)]
        if self.bidirectional:
            edges.append((self.to, self.from_))
        return edges


class VenueInfo(_Strict):
    name: str = Field(min_length=1)
    address: str | None = None
    rho_plan: float | None = Field(None, gt=0, lt=100)  # persons/m2; organiser-entered (doc 11 §4)
    plan_width: int | None = Field(None, gt=0)
    plan_height: int | None = Field(None, gt=0)
    floor_plan_path: str | None = None


class VenueConfig(_Strict):
    """A whole venue file."""

    format_version: Literal[1]
    # Research integrity (CLAUDE.md §6): every file states whether its numbers are made up.
    illustrative: bool
    venue: VenueInfo
    zones: list[ZoneConfig] = Field(min_length=1)
    connections: list[ConnectionConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def _cross_references(self) -> Self:
        codes = [z.code for z in self.zones]
        duplicates = sorted({c for c in codes if codes.count(c) > 1})
        if duplicates:
            raise ValueError(f"duplicate zone codes: {duplicates}")
        if OUTSIDE in codes:
            raise ValueError(f"{OUTSIDE!r} is reserved for the virtual outside node")

        known = set(codes) | {OUTSIDE}
        seen: set[tuple[str, str]] = set()
        for i, c in enumerate(self.connections):
            where = f"connections[{i}] {c.from_}->{c.to}"
            for end in (c.from_, c.to):
                if end not in known:
                    raise ValueError(f"{where}: unknown zone code {end!r}")
            if c.from_ == c.to:
                raise ValueError(f"{where}: a zone cannot connect to itself")
            for edge in c.directed_edges():
                if edge in seen:
                    raise ValueError(f"{where}: duplicate directed edge {edge[0]}->{edge[1]}")
                seen.add(edge)

        w, h = self.venue.plan_width, self.venue.plan_height
        for z in self.zones:
            if z.capacity is None and self.venue.rho_plan is None:
                raise ValueError(f"zone {z.code}: capacity missing and venue rho_plan not set")
            inside = (
                w is None or h is None or all(0 <= x <= w and 0 <= y <= h for x, y in z.polygon)
            )
            if not inside:
                raise ValueError(f"zone {z.code}: polygon outside the {w}x{h} plan")
        return self

    # ------------------------------------------------------------------ derived values
    def capacity_of(self, code: str) -> int:
        """C_i as given, else floor(A_i * rho_plan) (doc 14 §3.7), computed in decimal."""
        zone = next(z for z in self.zones if z.code == code)
        if zone.capacity is not None:
            return zone.capacity
        assert self.venue.rho_plan is not None  # guaranteed by _cross_references
        return math.floor(Decimal(str(zone.area_m2)) * Decimal(str(self.venue.rho_plan)))

    def directed_edges(self) -> list[tuple[str, str]]:
        return [e for c in self.connections for e in c.directed_edges()]

    def is_entry(self, code: str) -> bool:
        """A zone is an entry when people can step in directly from outside."""
        return (OUTSIDE, code) in self.directed_edges()

    def is_exit(self, code: str) -> bool:
        return (code, OUTSIDE) in self.directed_edges()


def load_venue_config(path: Path) -> VenueConfig:
    """Parse and validate a venue YAML file; raises ``pydantic.ValidationError`` on bad input."""
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return VenueConfig.model_validate(raw)
