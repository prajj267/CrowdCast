"""Event-level splits (WORKFLOW 5.2.3; experimental_design.md §3)."""

from __future__ import annotations

import json

import pytest

from tools.training.splits import (
    INDEX_FILE,
    SPLITS_FILE,
    load_splits,
    make_splits,
    split_of,
)


def test_committed_splits_are_disjoint_and_sized_as_designed() -> None:
    splits = load_splits()
    owner = split_of(splits)  # raises if an event is in two splits
    assert {k: len(v) for k, v in splits.items()} == {
        "train": 84, "validation": 18, "test_in_venue": 18, "test_new_venue": 60,
    }  # fmt: skip
    assert len(owner) == 180
    for name in ("train", "validation", "test_in_venue"):
        venues = [e.split("_")[0] for e in splits[name]]
        assert venues.count("v1") == venues.count("v2")  # 42/9/9 per venue
        assert "v3" not in venues  # the held-out venue never leaks into training
    assert all(e.startswith("v3_") for e in splits["test_new_venue"])


def test_an_event_in_two_splits_is_rejected() -> None:
    with pytest.raises(ValueError, match="v1_e001 is in both"):
        split_of({"train": ["v1_e001"], "validation": ["v1_e001"]})


def test_split_is_reproducible_from_the_seed() -> None:
    if not INDEX_FILE.exists():
        pytest.skip("synthetic dataset not generated (uv run python -m tools.crowdsim.generate)")
    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    by_venue: dict[str, list[str]] = {}
    for e in index["events"]:
        by_venue.setdefault(e["venue"], []).append(e["event_id"])
    assert make_splits(by_venue) == load_splits()
    assert json.loads(SPLITS_FILE.read_text(encoding="utf-8"))["seed"] == 2027
