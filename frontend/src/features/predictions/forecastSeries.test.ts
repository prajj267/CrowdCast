import { describe, expect, it } from "vitest";
import type { Schemas } from "../../api/client";
import {
  forecastPoints,
  mergeSeries,
  observedPoints,
  scheduleBands,
  thresholdLines,
  chartWindow,
} from "./forecastSeries";

const T0 = Date.parse("2026-05-01T12:00:00Z");
const iso = (minutes: number) => new Date(T0 + minutes * 60_000).toISOString();

function fc(h: number, p10: number, p50: number, p90: number): Schemas["Forecast"] {
  return {
    horizon_min: h,
    target_time: iso(h),
    p10,
    p50,
    p90,
    level: "NORMAL",
    risk_score: 0,
    is_fallback: false,
  };
}

describe("forecast series", () => {
  it("places observed occupancy at the bucket END and drops missing counts", () => {
    const pts = observedPoints([
      { t: iso(-2), occupancy: 10, inflow: 1, outflow: 0 },
      { t: iso(-3), occupancy: null, inflow: null, outflow: null },
      { t: iso(-1), occupancy: 12, inflow: 2, outflow: 0 },
    ]);
    expect(pts).toEqual([
      { t: T0 - 60_000, observed: 10 },
      { t: T0, observed: 12 },
    ]);
  });

  it("starts the fan at the current count with a zero-width band, sorted by horizon", () => {
    const pts = forecastPoints(T0, 12, [fc(15, 10, 20, 30), fc(5, 11, 14, 17)]);
    expect(pts.map((p) => p.t)).toEqual([T0, T0 + 5 * 60_000, T0 + 15 * 60_000]);
    expect(pts[0]).toEqual({ t: T0, p50: 12, band: [12, 12] });
    expect(pts[2]?.band).toEqual([10, 30]);
    expect(forecastPoints(T0, null, [fc(5, 1, 2, 3)])).toHaveLength(1);
    expect(forecastPoints(T0, 12, [])).toEqual([]);
  });

  it("merges the last observation and the fan start into one point at now", () => {
    const merged = mergeSeries([{ t: T0, observed: 12 }], forecastPoints(T0, 12, [fc(5, 1, 2, 3)]));
    expect(merged[0]).toEqual({ t: T0, observed: 12, p50: 12, band: [12, 12] });
    expect(merged).toHaveLength(2);
  });

  it("converts thresholds to persons and clips schedule bands to the window", () => {
    expect(
      thresholdLines(500, { elevated: 0.6, high: 0.8, critical: 0.95, source: "DEFAULT" }).map(
        (t) => t.y,
      ),
    ).toEqual([300, 400, 475]);
    const { from, to } = chartWindow(T0);
    expect(to - from).toBe(90 * 60_000);
    const item = (zone: number | null, s: number, e: number): Schemas["ScheduleItemOut"] => ({
      item_id: s,
      zone_id: zone,
      zone_code: null,
      title: `item ${s}`,
      category: "PERFORMANCE",
      start_time: iso(s),
      end_time: iso(e),
      expected_attendance: null,
      attraction_weight: 1,
    });
    const bands = scheduleBands(
      [item(1, -90, -30), item(2, 0, 10), item(null, 20, 60), item(1, 40, 50)],
      1,
      from,
      to,
    );
    expect(bands).toEqual([
      { from, to: T0 - 30 * 60_000, title: "item -90" }, // clipped at the window start
      { from: T0 + 20 * 60_000, to, title: "item 20" }, // venue-wide item, clipped at the end
    ]);
  });
});
