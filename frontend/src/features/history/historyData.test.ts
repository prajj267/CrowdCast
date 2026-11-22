import { describe, expect, it } from "vitest";
import type { Schemas } from "../../api/client";
import {
  type ZoneMeta,
  assignSlots,
  defaultSelection,
  historyCsv,
  peaks,
  predVsActual,
  ratioRows,
} from "./historyData";

const T0 = Date.parse("2027-03-12T12:00:00Z");
const iso = (m: number) => new Date(T0 + m * 60_000).toISOString();

const zones = new Map<number, ZoneMeta>([
  [1, { zone_id: 1, code: "FC", name: "Food court", capacity: 100, high: 0.8 }],
  [2, { zone_id: 2, code: "EX", name: "Exhibition", capacity: 200, high: 0.8 }],
]);

function s(zone: number, occ: (number | null)[]): Schemas["Series"] {
  return {
    zone_id: zone,
    points: occ.map((o, m) => ({ t: iso(m), occupancy: o, inflow: 1, outflow: null })),
  };
}

describe("history data", () => {
  it("builds ratio rows at the bucket end for the chosen zones only", () => {
    const rows = ratioRows([s(1, [50, null]), s(2, [100, 120])], zones, [1, 2]);
    expect(rows).toEqual([
      { t: T0 + 60_000, "1": 0.5, "2": 0.5 },
      { t: T0 + 120_000, "2": 0.6 },
    ]);
    expect(ratioRows([s(1, [50])], zones, [2])).toEqual([]);
  });

  it("finds the first peak and counts minutes at or above HIGH", () => {
    const [p] = peaks([s(1, [70, 85, 90, 90, null, 80])], zones);
    expect(p).toEqual({
      zone_id: 1,
      max: 90,
      at: T0 + 3 * 60_000, // bucket 2 ends at minute 3
      maxRatio: 0.9,
      minutesHigh: 4, // 85, 90, 90, 80 (inclusive bound)
    });
  });

  it("selects the highest peaks by default and keeps colour slots with their zone", () => {
    const p = [
      { zone_id: 1, max: 1, at: 0, maxRatio: 0.3, minutesHigh: 0 },
      { zone_id: 2, max: 1, at: 0, maxRatio: 0.9, minutesHigh: 0 },
      { zone_id: 3, max: null, at: null, maxRatio: null, minutesHigh: 0 },
    ];
    expect(defaultSelection(p)).toEqual([2, 1]);
    const first = assignSlots(new Map(), [5, 6, 7]);
    expect([...first]).toEqual([
      [5, 0],
      [6, 1],
      [7, 2],
    ]);
    // removing zone 5 must not repaint 6 and 7; a new zone takes the freed slot
    const next = assignSlots(first, [6, 7, 9]);
    expect([...next]).toEqual([
      [6, 1],
      [7, 2],
      [9, 0],
    ]);
  });

  it("computes MAE only where the outcome is known", () => {
    const pt = (m: number, p50: number, actual: number | null): Schemas["TimelinePoint"] => ({
      issued_at: iso(m - 15),
      target_time: iso(m),
      horizon_min: 15,
      p10: p50 - 5,
      p50,
      p90: p50 + 5,
      actual,
      is_fallback: false,
    });
    const r = predVsActual([pt(2, 10, 14), pt(1, 20, 18), pt(3, 30, null)]);
    expect(r.rows.map((x) => x.t)).toEqual([T0 + 60_000, T0 + 120_000, T0 + 180_000]);
    expect(r.mae).toBe(3); // (2 + 4) / 2
    expect(r.n).toBe(2);
    expect(predVsActual([]).mae).toBeNull();
  });

  it("exports CSV with empty cells for missing values and the data origin", () => {
    const csv = historyCsv([s(1, [5, null])], zones, "SYNTHETIC")
      .trim()
      .split("\n");
    expect(csv[0]).toBe("time_utc,zone_code,occupancy,inflow,outflow,data_origin");
    expect(csv[1]).toBe("2027-03-12T12:01:00.000Z,FC,5,1,,SYNTHETIC");
    expect(csv[2]).toBe("2027-03-12T12:02:00.000Z,FC,,1,,SYNTHETIC");
  });
});
