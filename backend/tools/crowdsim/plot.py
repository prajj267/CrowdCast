"""Occupancy profiles of one CROWDSIM run, for checking by eye (WORKFLOW 3.4.2).

Small multiples: one panel per zone (own y-scale), occupancy N(t) as a single line, planning
capacity C as a dashed reference, actual schedule items in that zone as light bands.
The figure is labelled SYNTHETIC (CLAUDE.md §6).

Usage (from backend/):
  uv run python -m tools.crowdsim.plot ../data/synthetic/crowdsim/regime_a/v1_spring_fest_day1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from crowdcast.common.config import REPO_ROOT
from crowdcast.venue_graph.interfaces import load_venue_config

# Reference palette (dataviz skill, light surface): one series colour + ink + recessive grid.
SURFACE = "#fcfcfb"
SERIES = "#2a78d6"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e6e5e0"
BAND = "#ecebe6"


def plot_run(run_dir: Path, out_file: Path) -> Path:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    zm = pd.read_parquet(run_dir / "zone_minutes.parquet")
    actual = pd.read_parquet(run_dir / "schedule_actual.parquet")
    venue = load_venue_config(REPO_ROOT / "configs" / "venues" / manifest["venue_file"])
    codes = [z.code for z in venue.zones]
    names = {z.code: z.name for z in venue.zones}

    plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID, "text.color": INK})
    fig, axes = plt.subplots(4, 2, figsize=(11, 10), sharex=True, facecolor=SURFACE)
    for ax, code in zip(axes.flat, codes, strict=False):
        ax.set_facecolor(SURFACE)
        z = zm[zm["zone_code"] == code]
        for _, item in actual[actual["zone_code"] == code].iterrows():
            ax.axvspan(item["start"], item["end"], color=BAND, lw=0, zorder=0)
        capacity = venue.capacity_of(code)
        ax.axhline(capacity, color=INK_2, lw=1, ls=(0, (4, 3)), zorder=1)
        ax.plot(z["bucket_start"], z["occupancy"], color=SERIES, lw=2, zorder=2)
        ax.text(
            0.995, capacity, f" C = {capacity}", transform=ax.get_yaxis_transform(),
            ha="right", va="bottom", color=INK_2, fontsize=8,
        )  # fmt: skip
        ax.set_title(f"{code} - {names[code]}", loc="left", color=INK, fontsize=10)
        ax.set_ylim(bottom=0, top=max(capacity, z["occupancy"].max()) * 1.15)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.tick_params(colors=INK_2, length=0)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz="UTC"))  # type: ignore[no-untyped-call]
    for ax in axes.flat[len(codes) :]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("event time (UTC)", color=INK_2)
    for ax in axes[:, 0]:
        ax.set_ylabel("occupancy N (persons)", color=INK_2)

    fig.suptitle(
        f"SYNTHETIC - CROWDSIM regime {manifest['regime']} (placeholder parameters): "
        f"{manifest['event_name']}",
        x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK,
    )  # fmt: skip
    fig.text(
        0.01, 0.955,
        "Occupancy at the start of each minute; dashed = planning capacity C; shaded = actual "
        "schedule items in the zone. Y-scales differ per panel. "
        f"Seed {manifest['master_seed']}/{manifest['event_index']}, "
        f"commit {manifest['git_commit'][:7]}.",
        ha="left", fontsize=8.5, color=INK_2,
    )  # fmt: skip
    fig.tight_layout(rect=(0, 0, 1, 0.945))
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_file, dpi=110, facecolor=SURFACE)
    plt.close(fig)
    return out_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    manifest = json.loads((args.run_dir / "manifest.json").read_text(encoding="utf-8"))
    default = (
        REPO_ROOT
        / "reports"
        / "figures"
        / f"crowdsim_{args.run_dir.name}_regime{manifest['regime'].lower()}_seed"
        f"{manifest['master_seed']}-{manifest['event_index']}.png"
    )
    print(f"written {plot_run(args.run_dir, args.out or default)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
