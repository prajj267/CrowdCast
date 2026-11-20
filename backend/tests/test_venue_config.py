"""Tests for the venue YAML format v1 (task 2.1.1)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from crowdcast.common.enums import ZoneType
from crowdcast.venue_graph.interfaces import OUTSIDE, VenueConfig, load_venue_config

SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10]]


def _minimal() -> dict[str, Any]:
    """Smallest valid venue: one gate open to the outside, plus a hall behind it."""
    return {
        "format_version": 1,
        "illustrative": True,
        "venue": {"name": "Test venue", "rho_plan": 1.5, "plan_width": 100, "plan_height": 100},
        "zones": [
            {"code": "G1", "name": "Gate", "type": "ENTRY_EXIT", "area_m2": 100, "capacity": 150,
             "polygon": SQUARE},
            {"code": "H1", "name": "Hall", "type": "OPEN_AREA", "area_m2": 801,
             "polygon": [[10, 0], [30, 0], [30, 10], [10, 10]]},
        ],
        "connections": [
            {"from": "OUTSIDE", "to": "G1", "width_m": 6, "travel_time_s": 20},
            {"from": "G1", "to": "H1", "width_m": 4, "travel_time_s": 30},
        ],
    }  # fmt: skip


def _invalid(data: dict[str, Any], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        VenueConfig.model_validate(data)


# ------------------------------------------------------------------ valid input
def test_minimal_venue_parses_and_derives_values() -> None:
    cfg = VenueConfig.model_validate(_minimal())
    assert [z.code for z in cfg.zones] == ["G1", "H1"]
    assert cfg.zones[1].type is ZoneType.OPEN_AREA
    assert cfg.capacity_of("G1") == 150  # given
    assert cfg.capacity_of("H1") == 1201  # floor(801 * 1.5), exact decimal arithmetic
    assert cfg.is_entry("G1") and cfg.is_exit("G1")  # OUTSIDE <-> G1 is bidirectional
    assert not cfg.is_entry("H1")
    assert sorted(cfg.directed_edges()) == sorted(
        [(OUTSIDE, "G1"), ("G1", OUTSIDE), ("G1", "H1"), ("H1", "G1")]
    )
    assert cfg.zones[0].thresholds.resolved() == (0.60, 0.80, 0.95)


def test_one_way_exit_is_exit_only() -> None:
    data = _minimal()
    data["connections"].append(
        {"from": "H1", "to": "OUTSIDE", "width_m": 3, "travel_time_s": 15, "bidirectional": False}
    )
    cfg = VenueConfig.model_validate(data)
    assert cfg.is_exit("H1") and not cfg.is_entry("H1")


def test_load_from_yaml_file(tmp_path: Path) -> None:
    path = tmp_path / "venue.yaml"
    path.write_text(yaml.safe_dump(_minimal()), encoding="utf-8")
    assert load_venue_config(path).venue.name == "Test venue"


# ------------------------------------------------------------------ field rules
@pytest.mark.parametrize("code", ["g1", "G-1", "", "ABCDEFGHIJKLMNOPQ"])
def test_bad_zone_code(code: str) -> None:
    data = _minimal()
    data["zones"][0]["code"] = code
    _invalid(data, "pattern")


def test_unknown_key_is_rejected() -> None:
    data = _minimal()
    data["zones"][0]["capcity"] = 100  # typo
    _invalid(data, "Extra inputs are not permitted")


def test_unknown_zone_type() -> None:
    data = _minimal()
    data["zones"][0]["type"] = "BAR"
    _invalid(data, "type")


@pytest.mark.parametrize(
    ("field", "value"), [("area_m2", 0), ("capacity", 0), ("area_m2", -5), ("capacity", -1)]
)
def test_non_positive_area_or_capacity(field: str, value: float) -> None:
    data = _minimal()
    data["zones"][0][field] = value
    _invalid(data, "greater than 0")


def test_self_intersecting_polygon() -> None:
    data = _minimal()
    data["zones"][0]["polygon"] = [[0, 0], [10, 10], [10, 0], [0, 10]]  # bow-tie
    _invalid(data, "non-self-intersecting")


def test_polygon_needs_three_vertices() -> None:
    data = _minimal()
    data["zones"][0]["polygon"] = [[0, 0], [10, 0]]
    _invalid(data, "at least 3")


def test_polygon_outside_plan() -> None:
    data = _minimal()
    data["zones"][0]["polygon"] = [[0, 0], [150, 0], [150, 10], [0, 10]]
    _invalid(data, "outside the 100x100 plan")


def test_thresholds_must_be_ordered_including_defaults() -> None:
    data = _minimal()
    data["zones"][0]["thresholds"] = {"high": 0.5}  # below default elevated 0.60
    _invalid(data, "elevated < high < critical")
    data["zones"][0]["thresholds"] = {"elevated": 0.5, "high": 0.7}
    assert VenueConfig.model_validate(data).zones[0].thresholds.resolved() == (0.5, 0.7, 0.95)


def test_capacity_needed_when_no_rho_plan() -> None:
    data = _minimal()
    data["venue"]["rho_plan"] = None
    _invalid(data, "capacity missing")


def test_format_version_and_illustrative_flag_required() -> None:
    data = _minimal()
    data["format_version"] = 2
    _invalid(data, "format_version")
    data = _minimal()
    del data["illustrative"]
    _invalid(data, "illustrative")


# ------------------------------------------------------------------ cross-references
def test_duplicate_zone_code() -> None:
    data = _minimal()
    data["zones"].append(copy.deepcopy(data["zones"][0]))
    _invalid(data, "duplicate zone codes")


def test_outside_is_reserved() -> None:
    data = _minimal()
    data["zones"][0]["code"] = "OUTSIDE"
    data["connections"] = [
        {"from": "OUTSIDE", "to": "H1", "width_m": 6, "travel_time_s": 20},
    ]
    _invalid(data, "reserved")


def test_connection_to_unknown_zone() -> None:
    data = _minimal()
    data["connections"][1]["to"] = "ZZ"
    _invalid(data, "unknown zone code 'ZZ'")


def test_self_loop_and_outside_to_outside() -> None:
    data = _minimal()
    data["connections"][1]["to"] = "G1"
    _invalid(data, "cannot connect to itself")
    data = _minimal()
    data["connections"][0]["to"] = "OUTSIDE"
    _invalid(data, "cannot connect to itself")


def test_duplicate_directed_edge_via_bidirectional() -> None:
    data = _minimal()
    # G1 -> H1 is already implied by the bidirectional G1 <-> H1
    data["connections"].append({"from": "H1", "to": "G1", "width_m": 4, "travel_time_s": 30})
    _invalid(data, "duplicate directed edge H1->G1")


@pytest.mark.parametrize(("field", "value"), [("width_m", 0), ("travel_time_s", 0)])
def test_connection_width_and_time_positive(field: str, value: float) -> None:
    data = _minimal()
    data["connections"][0][field] = value
    _invalid(data, "greater than 0")


# ------------------------------------------------------------------ reference venue V1 (2.1.2)
V1_PATH = Path(__file__).resolve().parents[2] / "configs" / "venues" / "v1.yaml"


def test_v1_reference_venue_matches_doc_11() -> None:
    cfg = load_venue_config(V1_PATH)
    assert cfg.illustrative is True
    # Areas and capacities from the table in doc 11 §6
    expected = {
        "G1": (300, 450), "C1": (400, 500), "MS": (2000, 3000), "FC": (800, 900),
        "EX": (600, 600), "C2": (250, 300), "G2": (200, 300), "WC": (100, 80),
    }  # fmt: skip
    assert {z.code: (z.area_m2, cfg.capacity_of(z.code)) for z in cfg.zones} == expected
    # 9 bidirectional connections x 2 + the one-way exit gate G2 -> OUTSIDE
    assert len(cfg.directed_edges()) == 19
    assert [z.code for z in cfg.zones if cfg.is_entry(z.code)] == ["G1"]
    assert sorted(z.code for z in cfg.zones if cfg.is_exit(z.code)) == ["G1", "G2"]
