"""Build training / validation datasets from CROWDSIM events (WORKFLOW 5.3.2; doc 10 §5-8).

Every event goes through the shared ``build_features`` with its PUBLISHED schedule (read from
the event file). Outflow shares for F_NBR are estimated on TRAINING events only and reused for
every split (doc 10 §7). Inputs are clean simulator states (SYN-clean); the noisy variant comes
with the noise model in Phase 7.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from crowdcast.common.config import REPO_ROOT
from crowdcast.forecasting.features import (
    FeatureSet,
    History,
    VenueInfo,
    add_target,
    build_features,
)
from crowdcast.forecasting.sources import outflow_shares, published_schedule, venue_info
from crowdcast.venue_graph.interfaces import load_event_config, load_venue_config

DATA = REPO_ROOT / "data" / "synthetic"
VENUE_DIR = REPO_ROOT / "configs" / "venues"


@dataclass(frozen=True)
class EventData:
    event_id: str
    venue: str  # file stem
    hist: History


def run_dir(event_id: str, regime: str = "a") -> Path:
    return DATA / "crowdsim" / f"regime_{regime}" / event_id


VARIANT_FILES = {"clean": "zone_minutes.parquet", "noisy": "zone_minutes_noisy.parquet"}


def load_history(
    event_id: str, codes: tuple[str, ...], regime: str = "a", variant: str = "clean"
) -> History:
    """SYN-clean (true states) or SYN-noisy (calibrated CV-like noise) inputs of one event."""
    event = load_event_config(DATA / "events" / f"{event_id}.yaml")
    zm = pd.read_parquet(run_dir(event_id, regime) / VARIANT_FILES[variant])

    def grid(col: str) -> np.ndarray:
        wide = zm.pivot(index="bucket_start", columns="zone_code", values=col)
        return np.asarray(wide[list(codes)].sort_index(), dtype=np.float64)

    duration = (event.event.end_time - event.event.start_time).total_seconds() / 60
    first = pd.Timestamp(zm["bucket_start"].min())
    offset = int((first - pd.Timestamp(event.event.start_time)).total_seconds() // 60)
    return History(
        n=grid("occupancy"),
        inflow=grid("inflow"),
        outflow=grid("outflow"),
        speed=grid("mean_speed_mps"),
        offset=offset,
        duration_min=duration,
        schedule=published_schedule(event, codes),  # published only (doc 10 §7)
    )


def estimate_shares(train_ids: list[str], venue: str, codes: tuple[str, ...]) -> np.ndarray:
    totals: dict[tuple[str, str], float] = {}
    for eid in train_ids:
        if not eid.startswith(f"{venue}_"):
            continue
        ef = pd.read_parquet(run_dir(eid) / "edge_flows.parquet")
        summed = ef.groupby(["from_code", "to_code"], as_index=False)["flow"].sum()
        for a, b, f in zip(summed["from_code"], summed["to_code"], summed["flow"], strict=True):
            totals[(str(a), str(b))] = totals.get((str(a), str(b)), 0.0) + float(f)
    return outflow_shares(codes, [(a, b, f) for (a, b), f in totals.items()])


def venue_infos(train_ids: list[str], venues: list[str]) -> dict[str, VenueInfo]:
    out = {}
    for v in venues:
        cfg = load_venue_config(VENUE_DIR / f"{v}.yaml")
        base = venue_info(cfg)
        out[v] = venue_info(cfg, estimate_shares(train_ids, v, base.codes))
    return out


def build_split(
    ids: list[str],
    infos: dict[str, VenueInfo],
    feature_set: FeatureSet,
    horizon: int,
    variant: str = "clean",
) -> pd.DataFrame:
    """Feature rows of the events; with variant "noisy" the inputs are SYN-noisy while the
    target stays the clean simulator occupancy (doc 12 §5.3)."""
    frames = []
    for eid in ids:
        venue = eid.split("_")[0]
        info = infos[venue]
        hist = load_history(eid, info.codes, variant=variant)
        truth = None if variant == "clean" else load_history(eid, info.codes).n
        rows = add_target(
            build_features(hist, info, feature_set, horizon), hist, info, horizon, truth
        )
        rows.insert(0, "event_id", eid)
        rows.insert(1, "venue", venue)
        rows["capacity_abs"] = info.capacity[rows["zone"].to_numpy()]
        frames.append(rows)
    return pd.concat(frames, ignore_index=True)


def data_hash(ids: list[str], variant: str = "clean") -> str:
    """sha256 over the event ids and the bytes of their simulator outputs."""
    h = hashlib.sha256()
    for eid in sorted(ids):
        h.update(eid.encode())
        h.update((run_dir(eid) / "zone_minutes.parquet").read_bytes())
        if variant != "clean":
            h.update((run_dir(eid) / VARIANT_FILES[variant]).read_bytes())
        h.update((DATA / "events" / f"{eid}.yaml").read_bytes())
    return h.hexdigest()


def shares_for_manifest(infos: dict[str, VenueInfo]) -> dict[str, Any]:
    """Outflow shares keyed by venue NAME (what the online cycle can look up in the DB)."""
    out = {}
    for v, info in infos.items():
        name = load_venue_config(VENUE_DIR / f"{v}.yaml").venue.name
        out[name] = {"codes": list(info.codes), "matrix": info.outflow_share.round(6).tolist()}
    return out


def read_index() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((DATA / "index_regime_a.json").read_text(encoding="utf-8"))
    return data
