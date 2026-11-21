"""SYN-noisy inputs for every generated event (WORKFLOW 7.2.3; doc 12 §5.3).

For each CROWDSIM run: observed occupancy from the calibrated noise model, and observed
crossings per connection (thinned by p_det, plus false crossings at r_fp) turned into zone
inflow / outflow. Written next to the clean output as ``zone_minutes_noisy.parquet`` with
method SIM_NOISY; the clean ``zone_minutes.parquet`` stays the target (doc 12 §5.3).
One seeded stream per event: SeedSequence([2027, event index, 2]).

Usage (from backend/):  uv run python -m tools.crowdsim.make_noisy
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import yaml

from crowdcast.common.config import REPO_ROOT
from crowdcast.venue_graph.interfaces import OUTSIDE, load_venue_config
from tools.crowdsim.generate import DATA
from tools.crowdsim.noise import NoiseParams, noisy_edge_flows, noisy_occupancy
from tools.crowdsim.run import MASTER_SEED

CALIBRATED = REPO_ROOT / "configs" / "crowdsim" / "noise_calibrated.yaml"


def load_params() -> NoiseParams:
    d = yaml.safe_load(CALIBRATED.read_text(encoding="utf-8"))
    return NoiseParams(
        d["m0"], d["m1"], d["sigma_r"], d["p_det"], d["r_fp"], f"calibrated ({CALIBRATED.name})"
    )


def noisy_zone_minutes(
    zm: pd.DataFrame,
    ef: pd.DataFrame,
    area: dict[str, float],
    params: NoiseParams,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Clean zone minutes + edge flows of one run -> the same rows with observed values."""
    occ = zm.pivot(index="bucket_start", columns="zone_code", values="occupancy").sort_index()
    codes = list(occ.columns)
    observed = noisy_occupancy(occ.to_numpy(float), np.array([area[c] for c in codes]), params, rng)

    flows = ef.pivot_table(
        index="bucket_start", columns=["from_code", "to_code"], values="flow", aggfunc="sum"
    ).sort_index()
    seen = noisy_edge_flows(flows.to_numpy(float), params, rng)
    inflow = pd.DataFrame(0.0, index=flows.index, columns=codes)
    outflow = pd.DataFrame(0.0, index=flows.index, columns=codes)
    pairs = [(str(c[0]), str(c[1])) for c in flows.columns.to_list()]
    for j, (a, b) in enumerate(pairs):
        if b != OUTSIDE:
            inflow[b] += seen[:, j]
        if a != OUTSIDE:
            outflow[a] += seen[:, j]

    obs = pd.DataFrame(observed, index=occ.index, columns=codes)

    def long(frame: pd.DataFrame, name: str) -> pd.DataFrame:
        wide = frame.rename_axis(index="bucket_start", columns=None).reset_index()
        return wide.melt(id_vars="bucket_start", var_name="zone_code", value_name=name)

    keys = ["bucket_start", "zone_code"]
    noisy = long(obs, "occupancy").merge(long(inflow, "inflow"), on=keys, how="outer")
    noisy = noisy.merge(long(outflow, "outflow"), on=keys, how="outer")
    out = zm.drop(columns=["occupancy", "inflow", "outflow"]).merge(
        noisy, on=["bucket_start", "zone_code"], how="left", validate="one_to_one"
    )
    out[["occupancy", "inflow", "outflow"]] = (
        out[["occupancy", "inflow", "outflow"]].fillna(0).astype(int)
    )
    out["mean_speed_mps"] = np.nan  # uncalibrated cameras give no speed (doc 09 §6.3)
    out["method"] = "SIM_NOISY"
    return out[list(zm.columns)]


def noisy_run(run_dir_: str, venue_stem: str, global_index: int, params: NoiseParams) -> None:
    run = DATA / "crowdsim" / "regime_a" / run_dir_
    zm = pd.read_parquet(run / "zone_minutes.parquet")
    ef = pd.read_parquet(run / "edge_flows.parquet")
    venue = load_venue_config(REPO_ROOT / "configs" / "venues" / f"{venue_stem}.yaml")
    area = {z.code: z.area_m2 for z in venue.zones}
    rng = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([MASTER_SEED, global_index, 2]))
    )
    out = noisy_zone_minutes(zm, ef, area, params, rng)
    out.to_parquet(run / "zone_minutes_noisy.parquet", index=False)


def main() -> int:
    params = load_params()
    index = json.loads((DATA / "index_regime_a.json").read_text(encoding="utf-8"))["events"]
    for e in index:
        noisy_run(e["event_id"], e["venue"], e["global_index"], params)
    print(f"SYN-noisy written for {len(index)} events with {params}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
