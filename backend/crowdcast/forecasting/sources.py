"""Turn configuration into FeatureBuilder inputs (WORKFLOW 5.1).

- ``venue_info``: zone order, static facts and graph matrices from a venue file.
- ``published_schedule``: the PUBLISHED schedule of an event file in minutes since the start.
  This is the only schedule features may see (doc 10 §7); there is deliberately no function
  that accepts a realised schedule.
- ``outflow_shares``: pi[j, i] = share of zone j's outflow that went to zone i, estimated from
  per-connection flows of TRAINING events only (doc 10 §7). Default: equal shares over j's exits.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from crowdcast.common.enums import ZoneType
from crowdcast.forecasting.features import Arr, SchedItem, VenueInfo
from crowdcast.venue_graph.interfaces import (
    OUTSIDE,
    Connection,
    EventConfig,
    VenueConfig,
    VenueGraph,
)


def _uniform_shares(adjacency: Arr, exits_outside: Arr) -> Arr:
    """Equal split of j's outflow over its zone neighbours and (if any) the outside."""
    out_degree = adjacency.sum(axis=1) + exits_outside
    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(out_degree[:, None] > 0, adjacency / out_degree[:, None], 0.0)
    return np.asarray(share, dtype=np.float64)


@dataclass(frozen=True)
class ZoneRow:
    code: str
    capacity: float
    area: float
    zone_type: ZoneType
    is_entry: bool
    is_exit: bool


@dataclass(frozen=True)
class ConnectionRow:
    from_code: str  # OUTSIDE for the virtual outside node
    to_code: str
    width_m: float
    travel_time_s: float
    bidirectional: bool


def venue_info_from_rows(
    zones: Sequence[ZoneRow], connections: Sequence[ConnectionRow], outflow_share: Arr | None = None
) -> VenueInfo:
    """The one way to build VenueInfo - from a venue file (training) or DB rows (online)."""
    codes = tuple(z.code for z in zones)
    graph = VenueGraph.from_connections(
        codes,
        [
            Connection(c.from_code, c.to_code, c.width_m, c.travel_time_s, c.bidirectional)
            for c in connections
        ],
    )
    idx = {c: k for k, c in enumerate(codes)}
    n = len(codes)
    width = np.zeros((n, n))
    travel = np.zeros((n, n))
    exits_outside = np.zeros(n)
    for c in connections:
        pairs = [(c.from_code, c.to_code)] + ([(c.to_code, c.from_code)] if c.bidirectional else [])
        for a, b in pairs:
            if a in idx and b in idx:
                width[idx[a], idx[b]] = c.width_m
                travel[idx[a], idx[b]] = c.travel_time_s / 60.0
            elif a in idx and b == OUTSIDE:
                exits_outside[idx[a]] = 1.0
    adjacency = graph.adjacency()
    return VenueInfo(
        codes=codes,
        capacity=np.array([z.capacity for z in zones], dtype=np.float64),
        area=np.array([z.area for z in zones], dtype=np.float64),
        zone_type=tuple(z.zone_type for z in zones),
        is_entry=np.array([float(z.is_entry) for z in zones]),
        is_exit=np.array([float(z.is_exit) for z in zones]),
        adjacency=adjacency,
        width=width,
        travel_min=travel,
        outflow_share=outflow_share
        if outflow_share is not None
        else _uniform_shares(adjacency, exits_outside),
    )


def venue_info(cfg: VenueConfig, outflow_share: Arr | None = None) -> VenueInfo:
    """From a venue YAML file, via the same function the online cycle uses for DB rows."""
    order = VenueGraph.from_config(cfg).zone_codes
    zones = {z.code: z for z in cfg.zones}
    return venue_info_from_rows(
        [
            ZoneRow(
                c,
                float(cfg.capacity_of(c)),
                zones[c].area_m2,
                zones[c].type,
                cfg.is_entry(c),
                cfg.is_exit(c),
            )
            for c in order
        ],
        [
            ConnectionRow(c.from_, c.to, c.width_m, c.travel_time_s, c.bidirectional)
            for c in cfg.connections
        ],
        outflow_share,
    )


def published_schedule(event: EventConfig, codes: Sequence[str]) -> tuple[SchedItem, ...]:
    start = event.event.start_time
    idx = {c: k for k, c in enumerate(codes)}
    return tuple(
        SchedItem(
            zone=None if it.zone is None else idx[it.zone],
            category=it.category,
            start_min=(it.start - start).total_seconds() / 60,
            end_min=(it.end - start).total_seconds() / 60,
            expected_attendance=None
            if it.expected_attendance is None
            else float(it.expected_attendance),
            attraction=it.attraction_weight,
        )
        for it in event.schedule
    )


def outflow_shares(
    codes: Sequence[str],
    edge_flows: Sequence[tuple[str, str, float]],
) -> Arr:
    """pi[j, i] from summed (from, to, flow) records of TRAINING events; OUTSIDE counts in the
    denominator (people leaving the venue are part of j's outflow) but gets no column."""
    idx = {c: k for k, c in enumerate(codes)}
    n = len(codes)
    to_zone = np.zeros((n, n))
    total = np.zeros(n)
    for a, b, f in edge_flows:
        if a not in idx:
            continue
        total[idx[a]] += f
        if b != OUTSIDE and b in idx:
            to_zone[idx[a], idx[b]] += f
    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(total[:, None] > 0, to_zone / total[:, None], 0.0)
    return np.asarray(share, dtype=np.float64)
