"""Schema v1 constraint tests (DOCUMENTATION/13_DATABASE_DESIGN.md).

Each test checks that the database itself rejects data the design says is invalid,
so later modules cannot write such rows even if their own validation has a bug.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crowdcast.common.enums import (
    AlertType,
    CongestionLevel,
    DataOrigin,
    ObsMethod,
    ObsQuality,
    ZoneType,
)
from crowdcast.storage.models import (
    CongestionAlert,
    CrowdObservation,
    Event,
    ModelVersion,
    Prediction,
    Venue,
    Zone,
    ZoneConnection,
)

pytestmark = pytest.mark.db

T0 = datetime(2027, 3, 12, 13, 52, tzinfo=UTC)


@pytest.fixture
def world(db_session: Session) -> dict[str, int]:
    """Minimal venue (2 zones), event and model version, adapted from 13 §6."""
    venue = Venue(name="Test Grounds", plan_width=1200, plan_height=800)
    db_session.add(venue)
    db_session.flush()
    ms = Zone(
        venue_id=venue.venue_id,
        code="MS",
        name="Main Stage",
        zone_type=ZoneType.STAGE,
        usable_area_m2=Decimal("2000"),
        planning_capacity=3000,
        polygon=[[600, 100], [1100, 100], [1100, 450], [600, 450]],
    )
    c1 = Zone(
        venue_id=venue.venue_id,
        code="C1",
        name="Central Corridor",
        zone_type=ZoneType.CORRIDOR,
        usable_area_m2=Decimal("400"),
        planning_capacity=500,
        polygon=[[400, 300], [600, 300], [600, 380], [400, 380]],
    )
    model = ModelVersion(
        name="persistence", version="v1", model_family="PERSISTENCE", artifact_path="-"
    )
    db_session.add_all([ms, c1, model])
    db_session.flush()
    event = Event(
        venue_id=venue.venue_id,
        name="Test Event",
        start_time=T0 - timedelta(hours=3),
        end_time=T0 + timedelta(hours=4),
        is_synthetic=True,
    )
    db_session.add(event)
    db_session.flush()
    return {
        "venue": venue.venue_id,
        "ms": ms.zone_id,
        "c1": c1.zone_id,
        "event": event.event_id,
        "model": model.model_version_id,
    }


def expect_rejected(db_session: Session, make: Callable[[], object]) -> None:
    """Assert that flushing the object raises IntegrityError, inside a savepoint."""
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(make())
        db_session.flush()


def observation(w: dict[str, int], **overrides: object) -> CrowdObservation:
    values: dict[str, object] = {
        "event_id": w["event"],
        "zone_id": w["c1"],
        "bucket_start": T0,
        "occupancy": 312,
        "occupancy_raw": 287,
        "inflow": 64,
        "outflow": 41,
        "quality": ObsQuality.OK,
        "method": ObsMethod.SIM_CLEAN,
        "data_origin": DataOrigin.SYNTHETIC,
    }
    values.update(overrides)
    return CrowdObservation(**values)


def prediction(w: dict[str, int], **overrides: object) -> Prediction:
    values: dict[str, object] = {
        "event_id": w["event"],
        "zone_id": w["c1"],
        "issued_at": T0,
        "horizon_min": 15,
        "target_time": T0 + timedelta(minutes=15),
        "p10": 360.0,
        "p50": 418.0,
        "p90": 470.0,
        "predicted_level": CongestionLevel.HIGH,
        "risk_score": 0.76,
        "model_version_id": w["model"],
    }
    values.update(overrides)
    return Prediction(**values)


# ------------------------------------------------------------------ valid data round-trips


def test_valid_records_insert_and_read_back_in_utc(
    db_session: Session, world: dict[str, int]
) -> None:
    db_session.add_all([observation(world), prediction(world)])
    db_session.flush()
    obs = db_session.query(CrowdObservation).filter_by(event_id=world["event"]).one()
    assert obs.bucket_start == T0
    assert obs.bucket_start.utcoffset() == timedelta(0)
    assert obs.data_origin is DataOrigin.SYNTHETIC


# ------------------------------------------------------------------ observations


def test_unaligned_bucket_rejected(db_session: Session, world: dict[str, int]) -> None:
    expect_rejected(db_session, lambda: observation(world, bucket_start=T0 + timedelta(seconds=7)))


def test_duplicate_upsert_key_rejected(db_session: Session, world: dict[str, int]) -> None:
    db_session.add(observation(world))
    db_session.flush()
    expect_rejected(db_session, lambda: observation(world, occupancy=1))


def test_same_bucket_different_origin_allowed(db_session: Session, world: dict[str, int]) -> None:
    # SYNTHETIC and MANUAL rows for the same bucket coexist (provenance kept apart).
    db_session.add_all(
        [
            observation(world),
            observation(world, data_origin=DataOrigin.MANUAL, method=ObsMethod.MANUAL),
        ]
    )
    db_session.flush()


def test_null_occupancy_only_when_missing(db_session: Session, world: dict[str, int]) -> None:
    expect_rejected(db_session, lambda: observation(world, occupancy=None))
    db_session.add(observation(world, occupancy=None, quality=ObsQuality.MISSING))
    db_session.flush()


def test_negative_counts_rejected(db_session: Session, world: dict[str, int]) -> None:
    expect_rejected(db_session, lambda: observation(world, occupancy=-1))
    expect_rejected(db_session, lambda: observation(world, inflow=-3))


# ------------------------------------------------------------------ predictions


def test_quantile_crossing_rejected(db_session: Session, world: dict[str, int]) -> None:
    expect_rejected(db_session, lambda: prediction(world, p10=500.0))


def test_unknown_horizon_rejected(db_session: Session, world: dict[str, int]) -> None:
    expect_rejected(
        db_session,
        lambda: prediction(world, horizon_min=10, target_time=T0 + timedelta(minutes=10)),
    )


def test_target_time_must_equal_issued_plus_horizon(
    db_session: Session, world: dict[str, int]
) -> None:
    expect_rejected(db_session, lambda: prediction(world, target_time=T0 + timedelta(minutes=14)))


# ------------------------------------------------------------------ alerts


def test_only_one_unresolved_alert_per_zone_and_type(
    db_session: Session, world: dict[str, int]
) -> None:
    def alert() -> CongestionAlert:
        return CongestionAlert(
            event_id=world["event"],
            zone_id=world["c1"],
            alert_type=AlertType.CURRENT,
            level=CongestionLevel.HIGH,
            message="C1 above HIGH",
            opened_at=T0,
        )

    db_session.add(alert())
    db_session.flush()
    expect_rejected(db_session, alert)


def test_predicted_alert_needs_horizon(db_session: Session, world: dict[str, int]) -> None:
    expect_rejected(
        db_session,
        lambda: CongestionAlert(
            event_id=world["event"],
            zone_id=world["c1"],
            alert_type=AlertType.PREDICTED,
            level=CongestionLevel.HIGH,
            message="missing horizon",
            opened_at=T0,
        ),
    )


# ------------------------------------------------------------------ venue graph


def test_outside_connection_cannot_be_duplicated(
    db_session: Session, world: dict[str, int]
) -> None:
    def to_outside() -> ZoneConnection:
        return ZoneConnection(
            venue_id=world["venue"],
            from_zone_id=world["c1"],
            to_zone_id=None,  # outside
            boundary_width_m=Decimal("6"),
            travel_time_s=30,
        )

    db_session.add(to_outside())
    db_session.flush()
    expect_rejected(db_session, to_outside)


def test_self_loop_rejected(db_session: Session, world: dict[str, int]) -> None:
    expect_rejected(
        db_session,
        lambda: ZoneConnection(
            venue_id=world["venue"],
            from_zone_id=world["c1"],
            to_zone_id=world["c1"],
            boundary_width_m=Decimal("6"),
            travel_time_s=30,
        ),
    )


def test_thresholds_must_be_ordered(db_session: Session, world: dict[str, int]) -> None:
    expect_rejected(
        db_session,
        lambda: Zone(
            venue_id=world["venue"],
            code="BAD",
            name="Bad thresholds",
            zone_type=ZoneType.OTHER,
            usable_area_m2=Decimal("10"),
            planning_capacity=10,
            polygon=[[0, 0], [1, 0], [1, 1]],
            threshold_high=Decimal("0.5"),  # below the default elevated 0.60
        ),
    )


def test_only_one_active_model(db_session: Session, world: dict[str, int]) -> None:
    db_session.add(
        ModelVersion(
            name="a", version="v1", model_family="XGBOOST", artifact_path="-", is_active=True
        )
    )
    db_session.flush()
    expect_rejected(
        db_session,
        lambda: ModelVersion(
            name="b", version="v1", model_family="XGBOOST", artifact_path="-", is_active=True
        ),
    )
