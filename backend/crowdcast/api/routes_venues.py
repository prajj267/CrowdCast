"""Venue, zone, connection and graph-validation read endpoints (doc 14 §2, §3.6)."""

from __future__ import annotations

from fastapi import APIRouter

from crowdcast.api.deps import SessionDep
from crowdcast.api.errors import ApiError
from crowdcast.api.schemas import (
    ConnectionList,
    ConnectionOut,
    GraphIssueOut,
    GraphValidation,
    ThresholdsOut,
    VenueOut,
    ZoneList,
    ZoneOut,
)
from crowdcast.storage.interfaces import Venue, Zone, ZoneConnection, repository
from crowdcast.venue_graph.interfaces import DEFAULT_THRESHOLDS, Severity

router = APIRouter(prefix="/api/venues", tags=["venues"])


def _venue_or_404(session: SessionDep, venue_id: int) -> Venue:
    venue = repository.get_venue(session, venue_id)
    if venue is None:
        raise ApiError(404, "NOT_FOUND", f"venue {venue_id} not found")
    return venue


def _thresholds(z: Zone) -> ThresholdsOut:
    overrides = (z.threshold_elevated, z.threshold_high, z.threshold_critical)
    defaults = (
        DEFAULT_THRESHOLDS["elevated"],
        DEFAULT_THRESHOLDS["high"],
        DEFAULT_THRESHOLDS["critical"],
    )
    e, h, c = (float(o) if o is not None else d for o, d in zip(overrides, defaults, strict=True))
    source = "DEFAULT" if all(o is None for o in overrides) else "ZONE"
    return ThresholdsOut(elevated=e, high=h, critical=c, source=source)


def _neighbours(zone_id: int, conns: list[ZoneConnection]) -> dict[str, list[int]]:
    """Zone ids one step away; OUTSIDE (NULL) is omitted - see is_entry / is_exit."""
    ins: set[int] = set()
    outs: set[int] = set()
    for c in conns:
        for src, dst in [(c.from_zone_id, c.to_zone_id)] + (
            [(c.to_zone_id, c.from_zone_id)] if c.bidirectional else []
        ):
            if dst == zone_id and src is not None:
                ins.add(src)
            if src == zone_id and dst is not None:
                outs.add(dst)
    return {"in": sorted(ins), "out": sorted(outs)}


@router.get("/{venue_id}", response_model=VenueOut)
def get_venue(venue_id: int, session: SessionDep) -> Venue:
    return _venue_or_404(session, venue_id)


@router.get("/{venue_id}/zones", response_model=ZoneList)
def list_zones(venue_id: int, session: SessionDep) -> ZoneList:
    _venue_or_404(session, venue_id)
    conns = repository.list_connections(session, venue_id)
    zones = [
        ZoneOut(
            zone_id=z.zone_id,
            code=z.code,
            name=z.name,
            zone_type=z.zone_type,
            usable_area_m2=float(z.usable_area_m2),
            planning_capacity=z.planning_capacity,
            polygon=z.polygon,
            is_entry=z.is_entry,
            is_exit=z.is_exit,
            thresholds=_thresholds(z),
            neighbours=_neighbours(z.zone_id, conns),
        )
        for z in repository.list_zones(session, venue_id)
    ]
    return ZoneList(venue_id=venue_id, zones=zones)


@router.get("/{venue_id}/connections", response_model=ConnectionList)
def list_connections(venue_id: int, session: SessionDep) -> ConnectionList:
    _venue_or_404(session, venue_id)
    conns = [
        ConnectionOut.model_validate(c) for c in repository.list_connections(session, venue_id)
    ]
    return ConnectionList(venue_id=venue_id, connections=conns)


@router.get("/{venue_id}/graph/validate", response_model=GraphValidation)
def validate_graph(venue_id: int, session: SessionDep) -> GraphValidation:
    """Graph rules of doc 11 §9 (FR-ZON-05)."""
    _venue_or_404(session, venue_id)
    issues = repository.venue_graph(session, venue_id).validate()
    return GraphValidation(
        venue_id=venue_id,
        valid=not any(i.severity is Severity.ERROR for i in issues),
        issues=[
            GraphIssueOut(
                code=i.code, severity=i.severity.value, subject=i.subject, message=i.message
            )
            for i in issues
        ],
    )
