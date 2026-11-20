"""Public interface of the venue-graph module (M5). Other modules import only from here.

The module also owns the configuration file formats (venue and event YAML, doc 12 §6).
"""

from crowdcast.venue_graph.camera_config import (
    CameraConfig,
    load_camera_config,
)
from crowdcast.venue_graph.config import (
    DEFAULT_THRESHOLDS,
    FORMAT_VERSION,
    OUTSIDE,
    ConnectionConfig,
    Thresholds,
    VenueConfig,
    VenueInfo,
    ZoneConfig,
    load_venue_config,
)
from crowdcast.venue_graph.event_config import (
    EventConfig,
    EventInfo,
    ScheduleItem,
    load_event_config,
)
from crowdcast.venue_graph.graph import (
    Connection,
    GraphIssue,
    InvalidVenueGraphError,
    IssueCode,
    Severity,
    VenueGraph,
)

__all__ = [
    "DEFAULT_THRESHOLDS",
    "FORMAT_VERSION",
    "OUTSIDE",
    "CameraConfig",
    "Connection",
    "ConnectionConfig",
    "EventConfig",
    "EventInfo",
    "GraphIssue",
    "InvalidVenueGraphError",
    "IssueCode",
    "ScheduleItem",
    "Severity",
    "Thresholds",
    "VenueConfig",
    "VenueGraph",
    "VenueInfo",
    "ZoneConfig",
    "load_camera_config",
    "load_event_config",
    "load_venue_config",
]
