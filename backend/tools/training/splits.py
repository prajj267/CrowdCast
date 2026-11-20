"""Event-level splits (RESEARCH/experimental_design.md §3; doc 10 §7-8; WORKFLOW 5.2.3).

Whole events go to exactly one split - never single minutes - because consecutive minutes of
one event are strongly correlated. V1 and V2 events: 42 train / 9 validation / 9 test-in-venue
each; every V3 event: test-new-venue (a venue never seen in training). Seed 2027.

The file is written ONCE and committed before the first training run (CLAUDE.md §5); training
code reads it and never re-draws it.

Usage (from backend/):  uv run python -m tools.training.splits   (refuses to overwrite)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from crowdcast.common.config import REPO_ROOT

SEED = 2027
SPLITS_FILE = REPO_ROOT / "configs" / "splits.json"
INDEX_FILE = REPO_ROOT / "data" / "synthetic" / "index_regime_a.json"
COUNTS = {"train": 42, "validation": 9, "test_in_venue": 9}  # per venue V1, V2
SPLIT_NAMES = ("train", "validation", "test_in_venue", "test_new_venue")


def make_splits(events_by_venue: dict[str, list[str]], seed: int = SEED) -> dict[str, list[str]]:
    rng = np.random.default_rng(seed)
    out: dict[str, list[str]] = {name: [] for name in SPLIT_NAMES}
    for venue in ("v1", "v2"):  # fixed order -> deterministic draws
        ids = sorted(events_by_venue[venue])
        if len(ids) != sum(COUNTS.values()):
            raise ValueError(f"{venue}: expected {sum(COUNTS.values())} events, got {len(ids)}")
        shuffled = [ids[i] for i in rng.permutation(len(ids))]
        k = 0
        for name, n in COUNTS.items():
            out[name].extend(sorted(shuffled[k : k + n]))
            k += n
    out["test_new_venue"] = sorted(events_by_venue["v3"])
    return out


def load_splits(path: Path = SPLITS_FILE) -> dict[str, list[str]]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    splits: dict[str, list[str]] = data["splits"]
    return splits


def split_of(splits: dict[str, list[str]]) -> dict[str, str]:
    """event id -> split name; raises if an event appears in two splits."""
    owner: dict[str, str] = {}
    for name, ids in splits.items():
        for eid in ids:
            if eid in owner:
                raise ValueError(f"{eid} is in both {owner[eid]} and {name}")
            owner[eid] = name
    return owner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    if SPLITS_FILE.exists():
        print(f"{SPLITS_FILE} already exists and is frozen; not overwriting")
        return 1
    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    by_venue: dict[str, list[str]] = {}
    for e in index["events"]:
        by_venue.setdefault(e["venue"], []).append(e["event_id"])
    splits = make_splits(by_venue)
    split_of(splits)  # sanity: disjoint
    payload = {
        "seed": SEED,
        "data_origin": "SYNTHETIC",
        "source": "CROWDSIM regime A events from tools.crowdsim.generate (master seed 2027)",
        "rule": "event-level; V1/V2: 42 train / 9 validation / 9 test_in_venue each; V3: all "
        "test_new_venue. Frozen before the first training run (CLAUDE.md §5).",
        "counts": {k: len(v) for k, v in splits.items()},
        "splits": splits,
    }
    SPLITS_FILE.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"written {SPLITS_FILE}: {payload['counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
