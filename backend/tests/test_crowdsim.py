"""CROWDSIM tests (WORKFLOW 3.3, 3.4.1; doc 17 TC-GR-04). All data here is SYNTHETIC."""

from __future__ import annotations

import json
import math
import time
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from crowdcast.venue_graph.interfaces import (
    OUTSIDE,
    EventConfig,
    VenueConfig,
    load_event_config,
    load_venue_config,
)
from tools.crowdsim.output import write_run
from tools.crowdsim.params import load_regime
from tools.crowdsim.run import event_rng
from tools.crowdsim.schedule import actual_items
from tools.crowdsim.sim import SimResult, simulate

CONFIGS = Path(__file__).resolve().parents[2] / "configs"
VENUE_FILE = CONFIGS / "venues" / "v1.yaml"
EVENT_FILE = CONFIGS / "events" / "v1_spring_fest_day1.yaml"


@pytest.fixture(scope="module")
def venue() -> VenueConfig:
    return load_venue_config(VENUE_FILE)


@pytest.fixture(scope="module")
def event() -> EventConfig:
    return load_event_config(EVENT_FILE)


@pytest.fixture(scope="module")
def run_a(venue: VenueConfig, event: EventConfig) -> SimResult:
    return simulate(venue, event, load_regime("a"), event_rng(2027, 0))


# ------------------------------------------------------------------ conservation (TC-GR-04)
@pytest.mark.parametrize(("regime", "index"), [("a", 0), ("a", 7), ("b", 3)])
def test_conservation_holds_exactly(
    venue: VenueConfig, event: EventConfig, regime: str, index: int
) -> None:
    r = simulate(venue, event, load_regime(regime), event_rng(2027, index))
    n = r.occupancy
    # per zone: N(t+1) = N(t) + inflow(t) - outflow(t)
    np.testing.assert_array_equal(n[1:] - n[:-1], r.inflow[:-1] - r.outflow[:-1])
    # venue: sum_i dN_i = entries - exits (doc 11 §5.1)
    np.testing.assert_array_equal(n[1:].sum(1) - n[:-1].sum(1), r.entries[:-1] - r.exits[:-1])
    # everybody who arrived also left
    assert r.entries.sum() == r.exits.sum() == r.arrivals_total
    assert r.left_inside_at_stop == 0 and n[0].sum() == 0


# ------------------------------------------------------------------ reproducibility
def test_same_seed_same_output(venue: VenueConfig, event: EventConfig, run_a: SimResult) -> None:
    again = simulate(venue, event, load_regime("a"), event_rng(2027, 0))
    np.testing.assert_array_equal(again.occupancy, run_a.occupancy)
    np.testing.assert_array_equal(again.edge_flow, run_a.edge_flow)


def test_different_seed_different_output(
    venue: VenueConfig, event: EventConfig, run_a: SimResult
) -> None:
    other = simulate(venue, event, load_regime("a"), event_rng(2027, 1))
    assert other.occupancy.shape != run_a.occupancy.shape or not np.array_equal(
        other.occupancy, run_a.occupancy
    )


# ------------------------------------------------------------------ mechanisms
def test_flows_only_on_real_edges(run_a: SimResult) -> None:
    assert (OUTSIDE, "G2") not in run_a.edges  # G2 is exit-only (doc 11 §6)
    assert ("G2", OUTSIDE) in run_a.edges
    assert run_a.edge_flow.min() >= 0
    entry_cols = [e for e, (a, _) in enumerate(run_a.edges) if a == OUTSIDE]
    assert [run_a.edges[e][1] for e in entry_cols] == ["G1"]


def test_occupancy_never_exceeds_jam_capacity(venue: VenueConfig, run_a: SimResult) -> None:
    factor = load_regime("a").movement.jam_capacity_factor
    for z, code in enumerate(run_a.zone_codes):
        assert run_a.occupancy[:, z].max() <= math.ceil(factor * venue.capacity_of(code))


def test_spillback_when_downstream_is_jammed(venue: VenueConfig, event: EventConfig) -> None:
    # Tiny main stage: admission into MS stops at the jam limit, so the corridor fills up instead.
    data = venue.model_dump(by_alias=True)
    for z in data["zones"]:
        if z["code"] == "MS":
            z["capacity"] = 20
    tiny = VenueConfig.model_validate(data)
    r = simulate(tiny, event, load_regime("a"), event_rng(2027, 0))
    ms = r.zone_codes.index("MS")
    assert r.occupancy[:, ms].max() <= 30  # 1.5 x 20
    base = simulate(venue, event, load_regime("a"), event_rng(2027, 0))
    c1 = r.zone_codes.index("C1")
    # the queue for the stage backs up into the corridor: more person-minutes spent in C1
    assert r.occupancy[:, c1].sum() > 1.2 * base.occupancy[:, c1].sum()
    assert r.left_inside_at_stop == 0  # no gridlock: everyone still gets out after closing


def test_headline_item_draws_a_crowd(run_a: SimResult) -> None:
    ms = run_a.zone_codes.index("MS")
    headline = next(i for i in run_a.actual if i.title == "Headline band")
    minutes = [t for t in run_a.bucket_starts if headline.start <= t < headline.end]
    during = [run_a.occupancy[run_a.bucket_starts.index(t), ms] for t in minutes]
    two_h_before = run_a.bucket_starts.index(
        min(run_a.bucket_starts, key=lambda t: abs(t - (headline.start - timedelta(hours=2))))
    )
    assert np.mean(during) > 2 * run_a.occupancy[two_h_before, ms]


# ------------------------------------------------------------------ schedule perturbation
def test_actual_schedule_perturbation_ranges(venue: VenueConfig, event: EventConfig) -> None:
    regime = load_regime("a")
    for seed in range(20):
        items = actual_items(event, venue, regime, event_rng(2027, seed))
        planned = [i for i in items if not i.is_popup]
        assert len(planned) == len(event.schedule)
        for pub, act in zip(event.schedule, planned, strict=True):
            shift = (act.start - pub.start).total_seconds() / 60
            assert -5 <= shift <= 10
            assert act.end - act.start == pub.end - pub.start
            assert act.popularity > 0
        for pop in (i for i in items if i.is_popup):
            assert pop.zone_code is not None and pop.start < pop.end <= event.event.end_time


def test_published_schedule_is_untouched(run_a: SimResult, event: EventConfig) -> None:
    assert [(i.title, i.start) for i in run_a.published] == [
        (i.title, i.start) for i in event.schedule
    ]


# ------------------------------------------------------------------ speed and output
def test_six_hour_event_generates_in_seconds(venue: VenueConfig, event: EventConfig) -> None:
    six_h = event.model_copy(
        update={
            "event": event.event.model_copy(
                update={"end_time": event.event.start_time + timedelta(hours=6)}
            ),
            "schedule": [
                i for i in event.schedule if i.end <= event.event.start_time + timedelta(hours=6)
            ],
        }
    )
    t0 = time.perf_counter()
    simulate(venue, six_h, load_regime("a"), event_rng(2027, 0))
    assert time.perf_counter() - t0 < 10  # Phase 3 exit criterion


def test_write_run(tmp_path: Path, run_a: SimResult) -> None:
    out = write_run(
        run_a,
        tmp_path / "run",
        event_name="test",
        regime="A",
        master_seed=2027,
        event_index=0,
        venue_file=VENUE_FILE,
        event_file=EVENT_FILE,
    )
    zm = pd.read_parquet(out / "zone_minutes.parquet")
    assert set(zm["data_origin"]) == {"SYNTHETIC"} and set(zm["method"]) == {"SIM_CLEAN"}
    assert len(zm) == len(run_a.bucket_starts) * len(run_a.zone_codes)
    actual = pd.read_parquet(out / "schedule_actual.parquet")
    assert {"popularity", "is_popup"} <= set(actual.columns)
    assert "popularity" not in pd.read_parquet(out / "schedule_published.parquet").columns
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_origin"] == "SYNTHETIC" and manifest["master_seed"] == 2027
