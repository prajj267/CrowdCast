/**
 * Data preparation for the History page (doc 15 Page 6), free of React so it can be tested:
 * occupancy ratio per zone over the event, peaks per zone (max, time, minutes in HIGH or
 * CRITICAL), predicted-vs-actual error, colour slots that stay with a zone, and CSV export.
 */
import type { Schemas } from "../../api/client";

const MIN = 60_000;
export const MAX_SERIES = 4; // categorical slots (tokens.css --series-1..4)

export interface ZoneMeta {
  zone_id: number;
  code: string;
  name: string;
  capacity: number;
  high: number; // theta_HIGH as an occupancy ratio
}

/** Bucket START -> state at the bucket END (doc 10 §1.1), as epoch ms. */
export function bucketEnd(t: string): number {
  return Date.parse(t) + MIN;
}

/** Wide rows {t, [zoneId]: ratio} for the selected zones, time-sorted. */
export function ratioRows(
  series: Schemas["Series"][],
  zones: Map<number, ZoneMeta>,
  selected: number[],
): Record<string, number>[] {
  const byT = new Map<number, Record<string, number>>();
  for (const s of series) {
    const z = zones.get(s.zone_id);
    if (!z || !selected.includes(s.zone_id)) continue;
    for (const p of s.points) {
      if (p.occupancy === null) continue;
      const t = bucketEnd(p.t);
      const row = byT.get(t) ?? { t };
      row[String(s.zone_id)] = p.occupancy / z.capacity;
      byT.set(t, row);
    }
  }
  return [...byT.values()].sort((a, b) => (a.t ?? 0) - (b.t ?? 0));
}

export interface Peak {
  zone_id: number;
  max: number | null;
  at: number | null; // epoch ms of the (first) maximum
  maxRatio: number | null;
  minutesHigh: number; // minutes with u >= theta_HIGH (HIGH or CRITICAL)
}

export function peaks(series: Schemas["Series"][], zones: Map<number, ZoneMeta>): Peak[] {
  return series.flatMap((s) => {
    const z = zones.get(s.zone_id);
    if (!z) return [];
    let max: number | null = null;
    let at: number | null = null;
    let minutesHigh = 0;
    for (const p of s.points) {
      if (p.occupancy === null) continue;
      if (max === null || p.occupancy > max) {
        max = p.occupancy;
        at = bucketEnd(p.t);
      }
      if (p.occupancy / z.capacity >= z.high) minutesHigh += 1;
    }
    return [
      {
        zone_id: s.zone_id,
        max,
        at,
        maxRatio: max === null ? null : max / z.capacity,
        minutesHigh,
      },
    ];
  });
}

/** Default chart zones: the highest peaks (ratio), at most MAX_SERIES. */
export function defaultSelection(p: Peak[]): number[] {
  return [...p]
    .filter((x) => x.maxRatio !== null)
    .sort((a, b) => (b.maxRatio ?? 0) - (a.maxRatio ?? 0))
    .slice(0, MAX_SERIES)
    .map((x) => x.zone_id);
}

/**
 * Colour slots that follow the zone, not its rank: a zone keeps its slot while it stays
 * selected; a newly added zone takes the lowest free slot.
 */
export function assignSlots(
  previous: Map<number, number>,
  selected: number[],
): Map<number, number> {
  const out = new Map<number, number>();
  for (const id of selected) {
    const slot = previous.get(id);
    if (slot !== undefined) out.set(id, slot);
  }
  for (const id of selected) {
    if (out.has(id)) continue;
    const used = new Set(out.values());
    const free = [...Array(MAX_SERIES).keys()].find((k) => !used.has(k));
    if (free !== undefined) out.set(id, free);
  }
  return out;
}

/** Predicted vs actual for one zone and horizon; MAE over points whose actual is known. */
export function predVsActual(points: Schemas["TimelinePoint"][]): {
  rows: { t: number; actual?: number; p50: number; band: [number, number] }[];
  mae: number | null;
  n: number;
} {
  const rows = points
    .map((p) => ({
      t: Date.parse(p.target_time),
      ...(p.actual === null ? {} : { actual: p.actual }),
      p50: p.p50,
      band: [p.p10, p.p90] as [number, number],
    }))
    .sort((a, b) => a.t - b.t);
  const errs = rows
    .filter((r) => r.actual !== undefined)
    .map((r) => Math.abs(r.p50 - (r.actual as number)));
  return {
    rows,
    mae: errs.length ? errs.reduce((a, b) => a + b, 0) / errs.length : null,
    n: errs.length,
  };
}

/** CSV of the 1-min history of every zone; one row per zone and minute (bucket end). */
export function historyCsv(
  series: Schemas["Series"][],
  zones: Map<number, ZoneMeta>,
  origin: string | null,
): string {
  const lines = ["time_utc,zone_code,occupancy,inflow,outflow,data_origin"];
  for (const s of series) {
    const code = zones.get(s.zone_id)?.code ?? String(s.zone_id);
    for (const p of s.points) {
      const cells = [p.occupancy, p.inflow, p.outflow].map((v) => (v === null ? "" : String(v)));
      lines.push([new Date(bucketEnd(p.t)).toISOString(), code, ...cells, origin ?? ""].join(","));
    }
  }
  return lines.join("\n") + "\n";
}

export function hhmm(ms: number | null): string {
  return ms === null ? "—" : new Date(ms).toISOString().slice(11, 16);
}
