"""Public interface of the aggregation module (M3). Other modules import only from here.

Turns per-frame zone counts and line crossings into per-zone, per-minute observation rows
(doc 09 §6-7). Track ids are held only for the debounce window (doc 19).
"""

from crowdcast.aggregation.counting import (
    Crossing,
    CrossingCounter,
    FrameStats,
    LineSpec,
    MinuteAggregator,
    RegionSpec,
    occupancy,
    orient_line,
)

__all__ = [
    "Crossing",
    "CrossingCounter",
    "FrameStats",
    "LineSpec",
    "MinuteAggregator",
    "RegionSpec",
    "occupancy",
    "orient_line",
]
