"""Run CROWDSIM for one event file (WORKFLOW 3.3).

Usage (from backend/):
  uv run python -m tools.crowdsim.run --event ../configs/events/v1_spring_fest_day1.yaml
Writes data/synthetic/crowdsim/<regime>/<event file stem>/ (git-ignored). Output is SYNTHETIC.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from crowdcast.common.config import REPO_ROOT
from crowdcast.venue_graph.interfaces import load_event_config, load_venue_config
from tools.crowdsim.output import write_run
from tools.crowdsim.params import load_regime
from tools.crowdsim.sim import simulate

MASTER_SEED = 2027  # CLAUDE.md §5


def event_rng(master_seed: int, event_index: int) -> np.random.Generator:
    """Independent, reproducible stream per event (DESIGN.md §11)."""
    seq = np.random.SeedSequence(master_seed).spawn(event_index + 1)[event_index]
    return np.random.Generator(np.random.PCG64(seq))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--regime", default="a")
    parser.add_argument("--seed", type=int, default=MASTER_SEED)
    parser.add_argument("--event-index", type=int, default=0)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "synthetic" / "crowdsim")
    args = parser.parse_args(argv)

    event = load_event_config(args.event)
    venue_file = REPO_ROOT / "configs" / "venues" / f"{event.event.venue}.yaml"
    venue = load_venue_config(venue_file)
    event.check_against_venue(venue)
    regime = load_regime(args.regime)

    t0 = time.perf_counter()
    result = simulate(venue, event, regime, event_rng(args.seed, args.event_index))
    elapsed = time.perf_counter() - t0
    out = write_run(
        result,
        args.out / f"regime_{regime.regime.lower()}" / args.event.stem,
        event_name=event.event.name,
        regime=regime.regime,
        master_seed=args.seed,
        event_index=args.event_index,
        venue_file=venue_file,
        event_file=args.event,
    )
    peak = dict(zip(result.zone_codes, result.occupancy.max(axis=0).tolist(), strict=True))
    print(
        f"SYNTHETIC run (regime {regime.regime}, seed {args.seed}/{args.event_index}): "
        f"{len(result.bucket_starts)} min simulated in {elapsed:.1f} s, "
        f"{result.arrivals_total} arrivals; peak N {peak}"
    )
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
