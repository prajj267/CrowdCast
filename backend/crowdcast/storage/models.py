"""SQLAlchemy 2 ORM models: the database schema of DOCUMENTATION/13_DATABASE_DESIGN.md.

Solo-scope changes (WORKFLOW.md decisions D6/D7, mirrored in doc 13 §8):
- no `users` / `event_operators` tables and no `created_by` / `*_by` user foreign keys;
- `congestion_alerts.auto_resolved` replaces `resolved_by` (NULL meant "auto");
- `audit_log.actor` ('USER' | 'SYSTEM') replaces `user_id`;
- `camera_sources.uri` is a plain local file path instead of a Fernet-encrypted `uri_encrypted`.

Privacy (NFR-PRV-02): only aggregates are stored. There is deliberately no table for
detections, tracks, faces or images.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from crowdcast.common.enums import (
    AlertStatus,
    AlertType,
    CameraKind,
    CongestionLevel,
    DataOrigin,
    EventStatus,
    ObsMethod,
    ObsQuality,
    ScheduleCategory,
    ZoneType,
)

# Deterministic constraint names, so Alembic migrations are stable and reviewable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """PostgreSQL ENUM type that stores the enum *values* (e.g. 'LIVE')."""
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


def pk() -> Mapped[int]:
    return mapped_column(BigInteger, Identity(always=False), primary_key=True)


TZ = DateTime(timezone=True)


# --------------------------------------------------------------------------- configuration


class Venue(Base):
    __tablename__ = "venues"

    venue_id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    floor_plan_path: Mapped[str | None] = mapped_column(Text)
    plan_width: Mapped[int | None] = mapped_column(Integer)
    plan_height: Mapped[int | None] = mapped_column(Integer)
    rho_plan: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())


class Zone(Base):
    __tablename__ = "zones"
    __table_args__ = (
        UniqueConstraint("venue_id", "code"),
        CheckConstraint("usable_area_m2 > 0", name="area_positive"),
        CheckConstraint("planning_capacity > 0", name="capacity_positive"),
        # Ordered thresholds; an unset threshold takes its default (0.60 / 0.80 / 0.95).
        CheckConstraint(
            "COALESCE(threshold_elevated, 0.600) < COALESCE(threshold_high, 0.800) "
            "AND COALESCE(threshold_high, 0.800) < COALESCE(threshold_critical, 0.950)",
            name="thresholds_ordered",
        ),
        Index("ix_zones_venue_id", "venue_id"),
    )

    zone_id: Mapped[int] = pk()
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.venue_id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(Text)
    zone_type: Mapped[ZoneType] = mapped_column(pg_enum(ZoneType, "zone_type"))
    usable_area_m2: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    planning_capacity: Mapped[int] = mapped_column(Integer)
    polygon: Mapped[list[list[float]]] = mapped_column(JSONB)
    is_entry: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_exit: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    threshold_elevated: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    threshold_high: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    threshold_critical: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))


class ZoneConnection(Base):
    __tablename__ = "zone_connections"
    __table_args__ = (
        # NULL zone = "outside" (omega). NULLS NOT DISTINCT so "outside -> G1" cannot be
        # inserted twice (PostgreSQL >= 15).
        UniqueConstraint(
            "venue_id", "from_zone_id", "to_zone_id", postgresql_nulls_not_distinct=True
        ),
        CheckConstraint("from_zone_id IS DISTINCT FROM to_zone_id", name="no_self_loop"),
        CheckConstraint(
            "from_zone_id IS NOT NULL OR to_zone_id IS NOT NULL", name="not_both_outside"
        ),
        CheckConstraint("boundary_width_m > 0", name="width_positive"),
        CheckConstraint("travel_time_s > 0", name="travel_time_positive"),
        Index("ix_zone_connections_venue_id", "venue_id"),
    )

    connection_id: Mapped[int] = pk()
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.venue_id", ondelete="CASCADE"))
    from_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("zones.zone_id", ondelete="CASCADE")
    )
    to_zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.zone_id", ondelete="CASCADE"))
    boundary_width_m: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    travel_time_s: Mapped[int] = mapped_column(Integer)
    bidirectional: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="end_after_start"),
        CheckConstraint(
            "expected_attendance IS NULL OR expected_attendance >= 0",
            name="attendance_non_negative",
        ),
    )

    event_id: Mapped[int] = pk()
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.venue_id"))
    name: Mapped[str] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(TZ)
    end_time: Mapped[datetime] = mapped_column(TZ)
    expected_attendance: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[EventStatus] = mapped_column(
        pg_enum(EventStatus, "event_status"), server_default=EventStatus.PLANNED.value
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    active_model_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_versions.model_version_id")
    )


class EventScheduleItem(Base):
    __tablename__ = "event_schedule_items"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="end_after_start"),
        CheckConstraint(
            "attraction_weight >= 0 AND attraction_weight <= 1", name="attraction_in_unit_range"
        ),
        Index("ix_event_schedule_items_event_start", "event_id", "start_time"),
    )

    item_id: Mapped[int] = pk()
    event_id: Mapped[int] = mapped_column(ForeignKey("events.event_id", ondelete="CASCADE"))
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.zone_id"))  # NULL = venue-wide
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[ScheduleCategory] = mapped_column(
        pg_enum(ScheduleCategory, "schedule_category")
    )
    start_time: Mapped[datetime] = mapped_column(TZ)
    end_time: Mapped[datetime] = mapped_column(TZ)
    expected_attendance: Mapped[int | None] = mapped_column(Integer)
    attraction_weight: Mapped[Decimal] = mapped_column(Numeric(3, 2), server_default=text("0.5"))
    # Features read the schedule version valid at issue time (leakage rule, 10 §7).
    updated_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())


# --------------------------------------------------------------------------- cameras


class CameraSource(Base):
    __tablename__ = "camera_sources"

    camera_id: Mapped[int] = pk()
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.venue_id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[CameraKind] = mapped_column(pg_enum(CameraKind, "camera_kind"))
    uri: Mapped[str] = mapped_column(Text)  # local video file path (D6: no live cameras)
    target_fps: Mapped[int] = mapped_column(SmallInteger, server_default=text("5"))
    image_size: Mapped[int] = mapped_column(SmallInteger, server_default=text("640"))
    homography: Mapped[list[list[float]] | None] = mapped_column(JSONB)
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class CameraZoneRegion(Base):
    __tablename__ = "camera_zone_regions"
    __table_args__ = (
        CheckConstraint(
            "coverage_fraction > 0 AND coverage_fraction <= 1", name="coverage_in_unit_range"
        ),
        # One primary camera per zone.
        Index(
            "uq_camera_zone_regions_primary_per_zone",
            "zone_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )

    region_id: Mapped[int] = pk()
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("camera_sources.camera_id", ondelete="CASCADE")
    )
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.zone_id", ondelete="CASCADE"))
    polygon_px: Mapped[list[list[float]]] = mapped_column(JSONB)
    coverage_fraction: Mapped[Decimal] = mapped_column(Numeric(4, 3), server_default=text("1"))
    is_primary: Mapped[bool] = mapped_column(Boolean)


class CountingLine(Base):
    __tablename__ = "counting_lines"

    line_id: Mapped[int] = pk()
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("camera_sources.camera_id", ondelete="CASCADE")
    )
    # UNIQUE: one line per connection, so a crossing is never counted twice.
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("zone_connections.connection_id", ondelete="CASCADE"), unique=True
    )
    p1: Mapped[list[float]] = mapped_column(JSONB)
    p2: Mapped[list[float]] = mapped_column(JSONB)
    positive_side_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("zones.zone_id")
    )  # NULL = outside


# --------------------------------------------------------------------------- time series


class CrowdObservation(Base):
    __tablename__ = "crowd_observations"
    __table_args__ = (
        UniqueConstraint("event_id", "zone_id", "bucket_start", "data_origin"),  # upsert key
        CheckConstraint(
            "date_trunc('minute', bucket_start) = bucket_start", name="bucket_minute_aligned"
        ),
        CheckConstraint("occupancy IS NULL OR occupancy >= 0", name="occupancy_non_negative"),
        CheckConstraint("occupancy IS NOT NULL OR quality = 'MISSING'", name="null_only_missing"),
        CheckConstraint("inflow IS NULL OR inflow >= 0", name="inflow_non_negative"),
        CheckConstraint("outflow IS NULL OR outflow >= 0", name="outflow_non_negative"),
        Index("ix_crowd_observations_event_bucket", "event_id", text("bucket_start DESC")),
        Index("ix_crowd_observations_bucket_brin", "bucket_start", postgresql_using="brin"),
    )

    observation_id: Mapped[int] = pk()
    event_id: Mapped[int] = mapped_column(ForeignKey("events.event_id", ondelete="CASCADE"))
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.zone_id"))
    bucket_start: Mapped[datetime] = mapped_column(TZ)
    occupancy: Mapped[int | None] = mapped_column(Integer)
    occupancy_raw: Mapped[int | None] = mapped_column(Integer)
    inflow: Mapped[int | None] = mapped_column(Integer)
    outflow: Mapped[int | None] = mapped_column(Integer)
    mean_speed_mps: Mapped[float | None] = mapped_column(REAL)
    quality: Mapped[ObsQuality] = mapped_column(pg_enum(ObsQuality, "obs_quality"))
    method: Mapped[ObsMethod] = mapped_column(pg_enum(ObsMethod, "obs_method"))
    data_origin: Mapped[DataOrigin] = mapped_column(pg_enum(DataOrigin, "data_origin"))
    ingested_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("name", "version"),
        # Exactly one globally active model at most.
        Index(
            "uq_model_versions_one_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    model_version_id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(Text)  # e.g. xgb_A4
    version: Mapped[str] = mapped_column(Text)  # e.g. v3
    model_family: Mapped[str] = mapped_column(Text)  # PERSISTENCE, XGBOOST, LSTM, GNN
    feature_set: Mapped[str | None] = mapped_column(Text)  # A1..A5; NULL for baselines
    artifact_path: Mapped[str] = mapped_column(Text)
    trained_on: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("event_id", "zone_id", "issued_at", "horizon_min", "model_version_id"),
        CheckConstraint("horizon_min IN (5, 15, 30)", name="horizon_allowed"),
        CheckConstraint(
            "target_time = issued_at + make_interval(mins => horizon_min)",
            name="target_is_issued_plus_horizon",
        ),
        CheckConstraint("p10 <= p50 AND p50 <= p90", name="quantiles_ordered"),
        CheckConstraint("p10 >= 0", name="p10_non_negative"),
        CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1)",
            name="risk_in_unit_range",
        ),
        Index("ix_predictions_event_issued", "event_id", text("issued_at DESC")),
        Index(
            "ix_predictions_event_zone_horizon_target",
            "event_id",
            "zone_id",
            "horizon_min",
            "target_time",
        ),
    )

    prediction_id: Mapped[int] = pk()
    event_id: Mapped[int] = mapped_column(ForeignKey("events.event_id", ondelete="CASCADE"))
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.zone_id"))
    issued_at: Mapped[datetime] = mapped_column(TZ)
    horizon_min: Mapped[int] = mapped_column(SmallInteger)
    target_time: Mapped[datetime] = mapped_column(TZ)
    p10: Mapped[float] = mapped_column(REAL)
    p50: Mapped[float] = mapped_column(REAL)
    p90: Mapped[float] = mapped_column(REAL)
    predicted_level: Mapped[CongestionLevel] = mapped_column(
        pg_enum(CongestionLevel, "congestion_level")
    )
    risk_score: Mapped[float | None] = mapped_column(REAL)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.model_version_id"))
    is_fallback: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class CongestionAlert(Base):
    __tablename__ = "congestion_alerts"
    __table_args__ = (
        # FR-ALR-04: at most one unresolved alert per (event, zone, type).
        Index(
            "uq_congestion_alerts_one_unresolved",
            "event_id",
            "zone_id",
            "alert_type",
            unique=True,
            postgresql_where=text("status <> 'RESOLVED'"),
        ),
        CheckConstraint(
            "(alert_type = 'CURRENT' AND horizon_min IS NULL AND predicted_onset IS NULL) "
            "OR (alert_type = 'PREDICTED' AND horizon_min IS NOT NULL "
            "AND predicted_onset IS NOT NULL)",
            name="horizon_matches_type",
        ),
        Index("ix_congestion_alerts_event_status_opened", "event_id", "status", "opened_at"),
    )

    alert_id: Mapped[int] = pk()
    event_id: Mapped[int] = mapped_column(ForeignKey("events.event_id", ondelete="CASCADE"))
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.zone_id"))
    alert_type: Mapped[AlertType] = mapped_column(pg_enum(AlertType, "alert_type"))
    level: Mapped[CongestionLevel] = mapped_column(pg_enum(CongestionLevel, "congestion_level"))
    horizon_min: Mapped[int | None] = mapped_column(SmallInteger)
    predicted_onset: Mapped[datetime | None] = mapped_column(TZ)
    trigger_value: Mapped[float | None] = mapped_column(REAL)
    status: Mapped[AlertStatus] = mapped_column(
        pg_enum(AlertStatus, "alert_status"), server_default=AlertStatus.OPEN.value
    )
    message: Mapped[str] = mapped_column(Text)
    opened_at: Mapped[datetime] = mapped_column(TZ)
    acknowledged_at: Mapped[datetime | None] = mapped_column(TZ)
    resolved_at: Mapped[datetime | None] = mapped_column(TZ)
    auto_resolved: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    prediction_id: Mapped[int | None] = mapped_column(
        ForeignKey("predictions.prediction_id", ondelete="SET NULL")
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (CheckConstraint("actor IN ('USER', 'SYSTEM')", name="actor_allowed"),)

    audit_id: Mapped[int] = pk()
    actor: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)  # e.g. ALERT_ACK, MODEL_ACTIVATE
    entity: Mapped[str | None] = mapped_column(Text)
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())
