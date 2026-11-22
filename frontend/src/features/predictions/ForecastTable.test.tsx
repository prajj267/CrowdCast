import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Schemas } from "../../api/client";
import { ForecastTable } from "./ForecastTable";
import { maxRisk } from "./forecastSeries";

function zone(id: number, code: string, fallback: boolean): Schemas["ZoneForecasts"] {
  return {
    zone_id: id,
    code,
    current: { occupancy: 100, occupancy_ratio: 0.5, level: "NORMAL" },
    forecasts: [5, 15, 30].map((h) => ({
      horizon_min: h,
      target_time: "2026-05-01T12:00:00Z",
      p10: 90 + h,
      p50: 100 + h,
      p90: 110 + h,
      level: h === 30 ? "HIGH" : "NORMAL",
      risk_score: h / 100,
      is_fallback: fallback,
    })),
  };
}

describe("ForecastTable", () => {
  it("shows P50 with its interval, the level word and the fallback flag", () => {
    render(
      <ForecastTable
        zones={[zone(1, "FC", false), zone(2, "EX", true)]}
        names={new Map([[1, "Food court"]])}
        selected={1}
        onSelect={() => {}}
      />,
    );
    expect(screen.getAllByText("130")).toHaveLength(2); // P50 at +30 for both zones
    expect(screen.getAllByText("(120–140)")).toHaveLength(2);
    expect(screen.getAllByText("High:")).toHaveLength(2); // level is also given in words
    expect(screen.getAllByText("Persistence fallback")).toHaveLength(3); // only EX, 3 horizons
    expect(screen.getByRole("button", { name: /Food court/ }).getAttribute("aria-pressed")).toBe(
      "true",
    );
    expect(screen.getByRole("button", { name: /EX/ }).getAttribute("aria-pressed")).toBe("false");
  });

  it("selects a zone when its name is clicked", async () => {
    const onSelect = vi.fn();
    render(
      <ForecastTable
        zones={[zone(1, "FC", false), zone(2, "EX", false)]}
        names={new Map()}
        selected={1}
        onSelect={onSelect}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /EX/ }));
    expect(onSelect).toHaveBeenCalledWith(2);
  });

  it("takes the largest risk score over the horizons", () => {
    expect(maxRisk(zone(1, "FC", false))).toBe(0.3);
    expect(maxRisk({ ...zone(1, "FC", false), forecasts: [] })).toBeNull();
  });
});
