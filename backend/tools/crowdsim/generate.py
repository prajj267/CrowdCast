"""Randomised synthetic events for the experiment dataset (DESIGN.md §9; WORKFLOW 5.2.3).

For each venue, ``EVENTS_PER_VENUE`` events are generated from a fixed seed per event, written
as event files (published schedule) and simulated with CROWDSIM. Everything is SYNTHETIC and
reproducible from (master seed, event index). All ranges are placeholders [PH].

Usage (from backend/):  uv run python -m tools.crowdsim.generate [--regime a]
Writes data/synthetic/events/<id>.yaml and data/synthetic/crowdsim/regime_<r>/<id>/ (git-ignored).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import yaml

from crowdcast.common.config import REPO_ROOT
from crowdcast.common.enums import ScheduleCategory, ZoneType
from crowdcast.venue_graph.interfaces import EventConfig, VenueConfig, load_venue_config
from tools.crowdsim.output import write_run
from tools.crowdsim.params import load_regime
from tools.crowdsim.run import MASTER_SEED, event_rng
from tools.crowdsim.sim import simulate

VENUES = {"v1": 0, "v2": 100, "v3": 200}  # venue file stem -> first global event index
EVENTS_PER_VENUE = 60  # RESEARCH/experimental_design.md §2
DATA = REPO_ROOT / "data" / "synthetic"

# Which zone types can host which item category [PH].
HOSTS: dict[ScheduleCategory, tuple[ZoneType, ...]] = {
    ScheduleCategory.PERFORMANCE: (ZoneType.STAGE,),
    ScheduleCategory.ANNOUNCEMENT: (ZoneType.STAGE,),
    ScheduleCategory.MEAL: (ZoneType.FOOD,),
    ScheduleCategory.OTHER: (ZoneType.EXHIBITION, ZoneType.OPEN_AREA),
}


def event_id(venue: str, k: int) -> str:
    return f"{venue}_e{k:03d}"


def schedule_rng(global_index: int) -> np.random.Generator:
    """Separate stream from the simulation's, so schedules and dynamics vary independently."""
    return np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([MASTER_SEED, global_index, 1]))
    )


def generate_event(
    venue_stem: str, venue: VenueConfig, k: int, global_index: int
) -> dict[str, Any]:
    """Event file content (published schedule) for event k of a venue [PH ranges]."""
    rng = schedule_rng(global_index)
    hours = int(rng.integers(4, 9))  # U{4..8} h
    start = datetime(2027, 1, 1, tzinfo=UTC) + timedelta(
        days=global_index, hours=int(rng.integers(9, 15))
    )
    end = start + timedelta(hours=hours)
    total_cap = sum(venue.capacity_of(z.code) for z in venue.zones)
    attendance = int(rng.uniform(0.6, 1.6) * total_cap)

    hosts = {cat: [z.code for z in venue.zones if z.type in types] for cat, types in HOSTS.items()}
    categories = [c for c, zones in hosts.items() if zones]
    items: list[dict[str, Any]] = [
        {
            "title": "Gates open",
            "category": "ENTRY_OPEN",
            "start": start,
            "end": start + timedelta(minutes=60),
            "attraction_weight": 0.5,
        },
        {
            "title": "Close and exit",
            "category": "EXIT_WAVE",
            "start": end - timedelta(minutes=30),
            "end": end,
            "attraction_weight": 0.5,
        },
    ]
    busy: dict[str, list[tuple[datetime, datetime]]] = {}
    for n in range(int(rng.integers(4, 11))):  # 4-10 items
        cat = categories[int(rng.integers(len(categories)))]
        zone = str(rng.choice(hosts[cat]))
        length = timedelta(minutes=int(rng.integers(4, 19)) * 5)  # 20-90 min
        for _ in range(20):  # place without overlapping another item in the same zone
            latest = (end - timedelta(minutes=30) - length - start).total_seconds() / 60
            if latest <= 30:
                break
            s = start + timedelta(minutes=5 * int(rng.integers(6, int(latest // 5) + 1)))
            e = s + length
            if all(e <= a or s >= b for a, b in busy.get(zone, [])):
                busy.setdefault(zone, []).append((s, e))
                cap = venue.capacity_of(zone)
                items.append(
                    {
                        "title": f"{cat.value.title()} {n + 1}",
                        "category": cat.value,
                        "zone": zone,
                        "start": s,
                        "end": e,
                        "expected_attendance": int(rng.uniform(0.3, 0.9) * cap),
                        "attraction_weight": round(float(rng.uniform(0.3, 1.0)) * 20) / 20,
                    }
                )
                break
    items.sort(key=lambda it: it["start"])
    return {
        "format_version": 1,
        "illustrative": True,
        "event": {
            "name": f"Synthetic {event_id(venue_stem, k)}",
            "venue": venue_stem,
            "start_time": start,
            "end_time": end,
            "expected_attendance": attendance,
            "is_synthetic": True,
        },
        "schedule": items,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regime", default="a")
    parser.add_argument("--venues", nargs="*", default=list(VENUES))
    parser.add_argument("--count", type=int, default=EVENTS_PER_VENUE)
    args = parser.parse_args(argv)
    regime = load_regime(args.regime)
    (DATA / "events").mkdir(parents=True, exist_ok=True)
    index: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    for stem in args.venues:
        venue_file = REPO_ROOT / "configs" / "venues" / f"{stem}.yaml"
        venue = load_venue_config(venue_file)
        for k in range(args.count):
            gi = VENUES[stem] + k
            eid = event_id(stem, k)
            content = generate_event(stem, venue, k, gi)
            event = EventConfig.model_validate(content)  # same validation as hand-written files
            event.check_against_venue(venue)
            event_file = DATA / "events" / f"{eid}.yaml"
            event_file.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")
            result = simulate(venue, event, regime, event_rng(MASTER_SEED, gi))
            write_run(
                result,
                DATA / "crowdsim" / f"regime_{regime.regime.lower()}" / eid,
                event_name=event.event.name,
                regime=regime.regime,
                master_seed=MASTER_SEED,
                event_index=gi,
                venue_file=venue_file,
                event_file=event_file,
            )
            index.append(
                {
                    "event_id": eid,
                    "venue": stem,
                    "global_index": gi,
                    "minutes": len(result.bucket_starts),
                    "arrivals": result.arrivals_total,
                }
            )
        print(f"{stem}: {args.count} events simulated ({time.perf_counter() - t0:.0f} s so far)")
    out = DATA / f"index_regime_{regime.regime.lower()}.json"
    out.write_text(
        json.dumps(
            {
                "data_origin": "SYNTHETIC",
                "regime": regime.regime,
                "master_seed": MASTER_SEED,
                "events": index,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"written {out} ({len(index)} events)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
