/**
 * Data preparation for the ForecastChart (doc 15 §2.3, Page 5), kept free of React so it can be
 * tested: the observed last 60 min, the forecast fan from "now" to +5/+15/+30 (P50 line and
 * P10-P90 band), threshold lines and the schedule items that overlap the window.
 */
import type { Schemas } from "../../api/client";

export const HORIZONS = [5, 15, 30] as const;
export const LOOKBACK_MIN = 60;
export const AHEAD_MIN = 30;
const MIN = 60_000;

export interface ChartPoint {
  t: number; // epoch ms (event time)
  observed?: number;
  p50?: number;
  band?: [number, number];
}

export interface Band {
  from: number;
  to: number;
  title: string;
}

/** History points end at the bucket start; occupancy is the state at the bucket END. */
export function observedPoints(points: Schemas["HistoryPoint"][]): ChartPoint[] {
  return points
    .filter((p) => p.occupancy !== null)
    .map((p) => ({ t: Date.parse(p.t) + MIN, observed: p.occupancy as number }))
    .sort((a, b) => a.t - b.t);
}

/**
 * Forecast fan: the current count at "now" (zero-width band) joined to the P50 and P10-P90 of
 * each horizon, so the band widens with the horizon.
 */
export function forecastPoints(
  asOf: number,
  currentCount: number | null,
  forecasts: Schemas["Forecast"][],
): ChartPoint[] {
  const ahead = [...forecasts]
    .sort((a, b) => a.horizon_min - b.horizon_min)
    .map((f) => ({
      t: Date.parse(f.target_time),
      p50: f.p50,
      band: [f.p10, f.p90] as [number, number],
    }));
  if (ahead.length === 0) return [];
  const start: ChartPoint[] =
    currentCount === null
      ? []
      : [{ t: asOf, p50: currentCount, band: [currentCount, currentCount] }];
  return [...start, ...ahead];
}

/** One time-sorted array; a point at "now" carries both the last observation and the fan start. */
export function mergeSeries(observed: ChartPoint[], forecast: ChartPoint[]): ChartPoint[] {
  const byT = new Map<number, ChartPoint>();
  for (const p of [...observed, ...forecast]) byT.set(p.t, { ...byT.get(p.t), ...p });
  return [...byT.values()].sort((a, b) => a.t - b.t);
}

/** Threshold lines in persons: ratio x planning capacity. */
export function thresholdLines(
  capacity: number,
  t: Schemas["ThresholdsOut"],
): { level: "ELEVATED" | "HIGH" | "CRITICAL"; y: number }[] {
  return [
    { level: "ELEVATED", y: t.elevated * capacity },
    { level: "HIGH", y: t.high * capacity },
    { level: "CRITICAL", y: t.critical * capacity },
  ];
}

/** Schedule items of this zone (or venue-wide ones) that overlap [from, to], clipped to it. */
export function scheduleBands(
  items: Schemas["ScheduleItemOut"][],
  zoneId: number,
  from: number,
  to: number,
): Band[] {
  return items
    .filter((i) => i.zone_id === zoneId || i.zone_id === null)
    .map((i) => ({ s: Date.parse(i.start_time), e: Date.parse(i.end_time), title: i.title }))
    .filter((i) => i.e > from && i.s < to)
    .map((i) => ({ from: Math.max(i.s, from), to: Math.min(i.e, to), title: i.title }));
}

/** Largest risk score over the horizons (the table and the default zone sort by it). */
export function maxRisk(z: Schemas["ZoneForecasts"]): number | null {
  const r = z.forecasts.map((f) => f.risk_score).filter((x): x is number => x !== null);
  return r.length ? Math.max(...r) : null;
}

export function chartWindow(asOf: number): { from: number; to: number } {
  return { from: asOf - LOOKBACK_MIN * MIN, to: asOf + AHEAD_MIN * MIN };
}

export function hhmm(ms: number): string {
  return new Date(ms).toISOString().slice(11, 16);
}
