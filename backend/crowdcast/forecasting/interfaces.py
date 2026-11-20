"""Public interface of the forecasting module (M6). Other modules import only from here."""

from crowdcast.forecasting.baselines import (
    HORIZONS,
    all_baselines,
    b0_persistence,
    b1_moving_average,
    b2_linear_trend,
    b3_conservation,
    forward_fill,
)

__all__ = [
    "HORIZONS",
    "all_baselines",
    "b0_persistence",
    "b1_moving_average",
    "b2_linear_trend",
    "b3_conservation",
    "forward_fill",
]
