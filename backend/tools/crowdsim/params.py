"""CROWDSIM parameter regimes (configs/crowdsim/regime_*.yaml; DESIGN.md). Placeholders [PH]."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from crowdcast.common.config import REPO_ROOT

REGIME_DIR = REPO_ROOT / "configs" / "crowdsim"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Arrivals(_Strict):
    turnout: tuple[float, float]
    baseline_weight: float = Field(ge=0, le=1)
    ramp_up_min: float = Field(gt=0)
    stop_before_end_min: float = Field(ge=0)
    surge_lead_min: float
    surge_sigma_min: float = Field(gt=0)


class Choice(_Strict):
    beta_attraction: float
    beta_distance_per_min: float
    beta_crowding: float
    beta_leave: float
    item_rise_min: float = Field(gt=0)
    exit_wave_min: float = Field(ge=0)
    base_attraction: dict[str, float]


class Dwell(_Strict):
    sigma: float = Field(gt=0)
    after_item_median_min: float = Field(gt=0)
    after_item_sigma: float = Field(gt=0)
    median_min: dict[str, float]


class Movement(_Strict):
    specific_flow_p_per_m_min: float = Field(gt=0)
    jam_capacity_factor: float = Field(gt=0)
    v_free_mps: float = Field(gt=0)
    rho_jam_p_per_m2: float = Field(gt=0)


class Perturbation(_Strict):
    start_offset_min: tuple[float, float]
    popularity_sigma: float = Field(ge=0)
    popup_prob_per_hour: float = Field(ge=0, le=1)
    popup_duration_min: tuple[float, float]
    popup_attraction: float = Field(ge=0, le=1)


class Regime(_Strict):
    regime: str
    tick_s: int = Field(gt=0)
    tail_min: float = Field(ge=0)
    arrivals: Arrivals
    choice: Choice
    dwell: Dwell
    movement: Movement
    perturbation: Perturbation


def load_regime(name_or_path: str | Path = "a") -> Regime:
    """Load ``regime_<name>.yaml`` from configs/crowdsim, or an explicit path."""
    path = Path(name_or_path)
    if not path.suffix:
        path = REGIME_DIR / f"regime_{str(name_or_path).lower()}.yaml"
    with path.open(encoding="utf-8") as fh:
        return Regime.model_validate(yaml.safe_load(fh))
