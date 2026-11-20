"""Enumerated types shared by the database, API schemas and engines.

Values mirror DOCUMENTATION/13_DATABASE_DESIGN.md §2. `user_role` is not defined:
decision D7 removed authentication (WORKFLOW.md).
"""

from enum import StrEnum


class EventStatus(StrEnum):
    PLANNED = "PLANNED"
    LIVE = "LIVE"
    ENDED = "ENDED"


class ZoneType(StrEnum):
    STAGE = "STAGE"
    CORRIDOR = "CORRIDOR"
    FOOD = "FOOD"
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ENTRY_EXIT = "ENTRY_EXIT"
    SEATING = "SEATING"
    EXHIBITION = "EXHIBITION"
    FACILITY = "FACILITY"
    OPEN_AREA = "OPEN_AREA"
    OTHER = "OTHER"


class ScheduleCategory(StrEnum):
    PERFORMANCE = "PERFORMANCE"
    MEAL = "MEAL"
    ENTRY_OPEN = "ENTRY_OPEN"
    EXIT_WAVE = "EXIT_WAVE"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    OTHER = "OTHER"


class DataOrigin(StrEnum):
    REAL = "REAL"
    MANUAL = "MANUAL"
    SYNTHETIC = "SYNTHETIC"


class ObsMethod(StrEnum):
    DETECTION = "DETECTION"
    DENSITY_MAP = "DENSITY_MAP"
    FUSED = "FUSED"
    MANUAL = "MANUAL"
    SIM_CLEAN = "SIM_CLEAN"
    SIM_NOISY = "SIM_NOISY"


class ObsQuality(StrEnum):
    OK = "OK"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"


class CongestionLevel(StrEnum):
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(StrEnum):
    CURRENT = "CURRENT"
    PREDICTED = "PREDICTED"


class AlertStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class CameraKind(StrEnum):
    FILE = "FILE"
    RTSP = "RTSP"
