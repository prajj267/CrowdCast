"""Published vs actual schedule (doc 12 §5.1 step 7; DESIGN.md §8).

The published schedule comes from the event file and is the only schedule forecasting may use
as features. The actual schedule - shifted starts, popularity multipliers, pop-ups - drives the
simulated agents and is written out for analysis only (leakage rule, doc 10 §7).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from crowdcast.common.enums import ScheduleCategory, ZoneType
from crowdcast.venue_graph.interfaces import EventConfig, VenueConfig
from tools.crowdsim.params import Regime

GATE_TYPES = {ZoneType.ENTRY, ZoneType.EXIT, ZoneType.ENTRY_EXIT}


@dataclass(frozen=True)
class SimItem:
    title: str
    category: ScheduleCategory
    zone_code: str | None  # None = venue-wide
    start: datetime
    end: datetime
    expected_attendance: int | None
    attraction_weight: float
    popularity: float = 1.0
    is_popup: bool = False


def published_items(event: EventConfig) -> list[SimItem]:
    return [
        SimItem(
            i.title,
            i.category,
            i.zone,
            i.start,
            i.end,
            i.expected_attendance,
            i.attraction_weight,
        )
        for i in event.schedule
    ]


def actual_items(
    event: EventConfig, venue: VenueConfig, regime: Regime, rng: np.random.Generator
) -> list[SimItem]:
    """Perturb the published schedule and add random pop-up attractions."""
    p = regime.perturbation
    out: list[SimItem] = []
    for item in published_items(event):
        shift = timedelta(minutes=float(rng.uniform(*p.start_offset_min)))
        popularity = float(rng.lognormal(0.0, p.popularity_sigma))
        out.append(
            SimItem(
                item.title,
                item.category,
                item.zone_code,
                item.start + shift,
                item.end + shift,  # duration kept
                item.expected_attendance,
                item.attraction_weight,
                popularity,
            )
        )

    candidates = [z.code for z in venue.zones if z.type not in GATE_TYPES]
    start, end = event.event.start_time, event.event.end_time
    hours = int((end - start).total_seconds() // 3600)
    for h in range(hours):
        if candidates and rng.random() < p.popup_prob_per_hour:
            begin = start + timedelta(hours=h, minutes=float(rng.uniform(0, 60)))
            length = timedelta(minutes=float(rng.uniform(*p.popup_duration_min)))
            out.append(
                SimItem(
                    f"Pop-up {h + 1}",
                    ScheduleCategory.OTHER,
                    str(rng.choice(candidates)),
                    begin,
                    min(begin + length, end),
                    None,
                    p.popup_attraction,
                    1.0,
                    is_popup=True,
                )
            )
    return out
