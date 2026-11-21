"""Observation-noise model for SYN-noisy inputs (doc 12 §5.3; WORKFLOW 7.2.2).

Occupancy:  N_obs = round(N * (1 - m(rho)) + eps),  m(rho) = min(0.6, m0 + m1 * rho),
            eps ~ Normal(0, (sigma_r * N)^2),  rho = N / area (persons / m2).
Crossings:  each true crossing on a connection is detected with probability p_det; false
            crossings arrive at rate r_fp per connection and minute (Poisson).

Calibration (``calibrate_occupancy``) uses the public counting evaluation (7.1.2): per sample
the miss fraction 1 - pred / true. The public datasets have no measured areas, so density is
taken from doc 16 §2.1's pairing of count bands with density bands, each band placed at its
density midpoint - an ASSUMPTION, reported wherever the calibrated values are used. Targets for
training always stay the clean simulator N (doc 12 §5.3).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import numpy.typing as npt

from tools.vision.count_metrics import band_of

Arr = npt.NDArray[np.float64]

# doc 16 §2.1: count bands 0-10 / 11-30 / 31-60 / >60 paired with density bands
# <0.5 / 0.5-1.5 / 1.5-3 / >3 persons/m2; band midpoints (">3" taken as 3.5) - an assumption.
BAND_DENSITY = {"0-10": 0.25, "11-30": 1.0, "31-60": 2.25, ">60": 3.5}
M_CAP = 0.6  # doc 12 §5.3


@dataclass(frozen=True)
class NoiseParams:
    m0: float
    m1: float
    sigma_r: float
    p_det: float
    r_fp: float
    source: str  # where each value came from (calibrated / placeholder)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


PLACEHOLDER = NoiseParams(0.05, 0.08, 0.05, 0.90, 0.2, "doc 12 §5.3 placeholders (uncalibrated)")


def calibrate_occupancy(true: list[int], pred: list[float]) -> tuple[float, float, float]:
    """(m0, m1, sigma_r) from per-sample counts. Weighted least squares of the band-level miss
    fraction on the band's assumed density; sigma_r = spread of the per-sample relative error
    around the fitted model."""
    t = np.asarray(true, dtype=np.float64)
    p = np.asarray(pred, dtype=np.float64)
    keep = t > 0
    t, p = t[keep], p[keep]
    bands = np.array([band_of(int(v)) for v in t])
    xs, ys, ws = [], [], []
    for name, rho in BAND_DENSITY.items():
        sel = bands == name
        if sel.any():
            xs.append(rho)
            ys.append(1 - p[sel].sum() / t[sel].sum())  # pooled miss fraction of the band
            ws.append(float(sel.sum()))
    x, y, w = np.array(xs), np.array(ys), np.array(ws)
    if len(x) >= 2:
        slope, intercept = np.polyfit(x, y, 1, w=np.sqrt(w))
        m0, m1 = float(intercept), float(slope)
    else:
        m0, m1 = float(y[0]), 0.0
    m0, m1 = float(np.clip(m0, 0.0, M_CAP)), float(max(m1, 0.0))
    sample_rho = np.array([BAND_DENSITY[b] for b in bands])
    expected = t * (1 - np.minimum(M_CAP, m0 + m1 * sample_rho))
    sigma_r = float(np.std((p - expected) / t))
    return m0, m1, sigma_r


def noisy_occupancy(n: Arr, area: Arr, params: NoiseParams, rng: np.random.Generator) -> Arr:
    """(T, Z) true occupancy -> observed counts (non-negative integers as floats)."""
    rho = n / area[None, :]
    miss = np.minimum(M_CAP, params.m0 + params.m1 * rho)
    eps = rng.normal(0.0, 1.0, size=n.shape) * params.sigma_r * n
    return np.asarray(np.maximum(0.0, np.round(n * (1 - miss) + eps)), dtype=np.float64)


def noisy_edge_flows(flows: Arr, params: NoiseParams, rng: np.random.Generator) -> Arr:
    """(T, E) true crossings per connection and minute -> detected crossings."""
    detected = rng.binomial(flows.astype(np.int64), params.p_det)
    false = rng.poisson(params.r_fp, size=flows.shape)
    return np.asarray(detected + false, dtype=np.float64)
