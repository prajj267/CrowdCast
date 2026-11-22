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
from crowdcast.forecasting.cycle import CycleResult, origin_for, preload_active_model, run_cycle
from crowdcast.forecasting.features import FeatureSet
from crowdcast.forecasting.xgb import artifacts_complete

__all__ = [
    "HORIZONS",
    "CycleResult",
    "FeatureSet",
    "all_baselines",
    "artifacts_complete",
    "b0_persistence",
    "b1_moving_average",
    "b2_linear_trend",
    "b3_conservation",
    "forward_fill",
    "origin_for",
    "preload_active_model",
    "run_cycle",
]
