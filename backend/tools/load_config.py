"""Load venue / event YAML configuration into the database (WORKFLOW 2.3.1).

Usage (from backend/, with Postgres running and migrated):
  uv run python -m tools.load_config venue ../configs/venues/v1.yaml
  uv run python -m tools.load_config event ../configs/events/v1_spring_fest_day1.yaml

An event file names its venue by file stem (``venue: v1``); that venue file is read from
configs/venues/ to check zone codes, and the venue must already be loaded.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from crowdcast.common.config import REPO_ROOT
from crowdcast.storage.interfaces import load_event, load_venue, session_scope
from crowdcast.venue_graph.interfaces import (
    InvalidVenueGraphError,
    load_event_config,
    load_venue_config,
)

VENUE_DIR = REPO_ROOT / "configs" / "venues"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["venue", "event"])
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.kind == "venue":
            venue_cfg = load_venue_config(args.path)
            with session_scope() as session:
                r = load_venue(session, venue_cfg)
            print(
                f"loaded venue {venue_cfg.venue.name!r}: venue_id={r.venue_id}, "
                f"{len(r.zone_ids)} zones, {r.connection_count} connections"
                + (" [ILLUSTRATIVE values]" if venue_cfg.illustrative else "")
            )
            for w in r.warnings:
                print(f"  warning {w.code} {w.subject}: {w.message}")
        else:
            event_cfg = load_event_config(args.path)
            venue_cfg = load_venue_config(VENUE_DIR / f"{event_cfg.event.venue}.yaml")
            with session_scope() as session:
                er = load_event(session, event_cfg, venue_cfg)
            print(
                f"loaded event {event_cfg.event.name!r}: event_id={er.event_id}, "
                f"{er.schedule_item_count} schedule items"
                + (" [ILLUSTRATIVE values]" if event_cfg.illustrative else "")
            )
    except (ValidationError, InvalidVenueGraphError, ValueError, LookupError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
