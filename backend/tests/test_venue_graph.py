"""Tests for the venue graph and its validation rules (task 2.2.1; doc 17 §2.2)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from crowdcast.venue_graph.interfaces import (
    OUTSIDE,
    InvalidVenueGraphError,
    IssueCode,
    Severity,
    VenueConfig,
    VenueGraph,
    load_venue_config,
)

V1 = Path(__file__).resolve().parents[2] / "configs" / "venues" / "v1.yaml"


def _venue(zones: list[str], connections: list[dict[str, Any]]) -> VenueGraph:
    """Small venue: square polygons side by side, capacity 100 each."""
    data = {
        "format_version": 1,
        "illustrative": True,
        "venue": {"name": "Test"},
        "zones": [
            {"code": c, "name": c, "type": "OTHER", "area_m2": 50, "capacity": 100,
             "polygon": [[10 * k, 0], [10 * k + 10, 0], [10 * k + 10, 10], [10 * k, 10]]}
            for k, c in enumerate(zones)
        ],
        "connections": [{"width_m": 2, "travel_time_s": 10, **c} for c in connections],
    }  # fmt: skip
    return VenueGraph.from_config(VenueConfig.model_validate(data))


def _codes(graph: VenueGraph) -> list[tuple[IssueCode, str]]:
    return [(i.code, i.subject) for i in graph.validate()]


# ------------------------------------------------------------------ construction
def test_v1_graph_structure() -> None:
    g = VenueGraph.from_config(load_venue_config(V1))
    assert len(g.edges()) == 19
    assert g.neighbours("C1") == ["EX", "FC", "G1", "MS"]
    assert g.neighbours("G2", "out") == ["C2", OUTSIDE]
    assert g.neighbours("G2", "in") == ["C2"]  # exit-only gate: nobody enters from outside
    assert g.neighbours(OUTSIDE, "out") == ["G1"]
    with pytest.raises(KeyError):
        g.neighbours("ZZ")


def test_v1_is_valid() -> None:
    g = VenueGraph.from_config(load_venue_config(V1))
    assert g.validate() == []
    assert g.require_valid() == []


# ------------------------------------------------------------------ rules (doc 11 §9)
def test_tc_gr_01_isolated_zone() -> None:
    g = _venue(["A", "B"], [{"from": OUTSIDE, "to": "A"}])
    assert _codes(g) == [(IssueCode.ISOLATED, "B")]  # reported once, not also as UNREACHABLE


def test_tc_gr_02_zone_not_reachable_from_outside() -> None:
    # B can only be left (B -> A), never entered
    g = _venue(
        ["A", "B"],
        [{"from": OUTSIDE, "to": "A"}, {"from": "B", "to": "A", "bidirectional": False}],
    )
    assert _codes(g) == [(IssueCode.UNREACHABLE, "B")]


def test_zone_without_path_out() -> None:
    # one-way passage into B: people who enter B cannot leave the venue
    g = _venue(
        ["A", "B"],
        [{"from": OUTSIDE, "to": "A"}, {"from": "A", "to": "B", "bidirectional": False}],
    )
    assert _codes(g) == [(IssueCode.NO_PATH_OUT, "B")]


def test_venue_without_any_outside_connection() -> None:
    g = _venue(["A", "B"], [{"from": "A", "to": "B"}])
    assert sorted(_codes(g)) == sorted(
        [
            (IssueCode.UNREACHABLE, "A"),
            (IssueCode.NO_PATH_OUT, "A"),
            (IssueCode.UNREACHABLE, "B"),
            (IssueCode.NO_PATH_OUT, "B"),
        ]
    )


def test_require_valid_rejects_invalid_venue() -> None:
    g = _venue(["A", "B"], [{"from": OUTSIDE, "to": "A"}])
    with pytest.raises(InvalidVenueGraphError, match="ISOLATED B") as exc:
        g.require_valid()
    assert [i.code for i in exc.value.issues] == [IssueCode.ISOLATED]


# ------------------------------------------------------------------ rule 4: counting lines
def test_counting_line_rule_skipped_without_camera_config() -> None:
    g = VenueGraph.from_config(load_venue_config(V1))
    assert g.validate(observed_connections=None) == []


def test_unobserved_connections_are_warnings() -> None:
    g = _venue(["A", "B"], [{"from": OUTSIDE, "to": "A"}, {"from": "A", "to": "B"}])
    issues = g.validate(observed_connections=[("B", "A")])  # either orientation counts
    assert [(i.code, i.severity, i.subject) for i in issues] == [
        (IssueCode.NO_COUNTING_LINE, Severity.WARNING, f"{OUTSIDE}->A")
    ]
    # warnings alone do not make the venue invalid
    assert g.require_valid() == []


# ------------------------------------------------------------------ matrices (task 2.2.2)
def test_tc_gr_03_v1_adjacency_matches_hand_built_matrix() -> None:
    g = VenueGraph.from_config(load_venue_config(V1))
    assert g.zone_codes == ("G1", "C1", "MS", "FC", "EX", "C2", "G2", "WC")
    # Built by hand from the doc 11 §6 diagram; rows = from, columns = to.
    # columns:     G1 C1 MS FC EX C2 G2 WC
    expected = [
        [0, 1, 0, 0, 0, 0, 0, 0],  # G1
        [1, 0, 1, 1, 1, 0, 0, 0],  # C1
        [0, 1, 0, 0, 0, 1, 0, 0],  # MS
        [0, 1, 0, 0, 0, 1, 0, 1],  # FC
        [0, 1, 0, 0, 0, 0, 0, 0],  # EX
        [0, 0, 1, 1, 0, 0, 1, 0],  # C2
        [0, 0, 0, 0, 0, 1, 0, 0],  # G2
        [0, 0, 0, 1, 0, 0, 0, 0],  # WC
    ]
    np.testing.assert_array_equal(g.adjacency(), np.array(expected, dtype=float))


def test_weighted_adjacency_is_width_over_max_width() -> None:
    g = VenueGraph.from_config(load_venue_config(V1))
    aw = g.adjacency(weighted=True)
    i = g.index()
    assert aw.max() == 1.0  # widest zone-to-zone passages: G1-C1 and C1-MS, 8 m
    assert aw[i["C1"], i["MS"]] == 1.0
    assert aw[i["FC"], i["WC"]] == pytest.approx(3 / 8)
    np.testing.assert_array_equal(aw > 0, g.adjacency() > 0)


def test_v1_shortest_travel_times() -> None:
    g = VenueGraph.from_config(load_venue_config(V1))
    assert g.travel_time_s("G1", "MS") == 75  # 30 + 45
    assert g.shortest_path("MS", "WC") == ["MS", "C1", "FC", "WC"]  # 105 s beats 110 via C2
    assert g.travel_time_s("MS", "WC") == 105
    assert g.travel_time_s(OUTSIDE, "G2") == 160  # 20+30+40+40+30, via the food court
    assert g.travel_time_s("EX", OUTSIDE) == 85  # leave by the main gate
    assert g.travel_time_s("G2", OUTSIDE) == 15


def test_outside_is_never_a_shortcut() -> None:
    # Two gates: A <-> OUTSIDE <-> B is short, but A -> B inside the venue is long (A-C-B).
    g = _venue(
        ["A", "B", "C"],
        [
            {"from": OUTSIDE, "to": "A", "travel_time_s": 1},
            {"from": OUTSIDE, "to": "B", "travel_time_s": 1},
            {"from": "A", "to": "C", "travel_time_s": 100},
            {"from": "C", "to": "B", "travel_time_s": 100},
        ],
    )
    assert g.shortest_path("A", "B") == ["A", "C", "B"]
    assert g.travel_time_s("A", "B") == 200


def test_travel_time_matrix_and_unreachable_pairs() -> None:
    g = VenueGraph.from_config(load_venue_config(V1))
    d = g.travel_time_matrix()
    i = g.index()
    assert np.all(np.diag(d) == 0)
    assert d[i["MS"], i["WC"]] == 105
    assert d[i["G1"], i["MS"]] == g.travel_time_s("G1", "MS")

    one_way = _venue(
        ["A", "B"],
        [{"from": OUTSIDE, "to": "A"}, {"from": "A", "to": "B", "bidirectional": False}],
    )
    assert one_way.travel_time_s("B", "A") == math.inf
    assert one_way.travel_time_matrix()[1, 0] == math.inf
