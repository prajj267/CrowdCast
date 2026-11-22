/** TC-FE-02 (stale ZoneCard) and TC-FE-03 (horizon selector drives the map), doc 17 §2.7. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Schemas } from "../../api/client";
import { VenueMap } from "./VenueMap";
import { ZoneCard } from "./ZoneCard";

function now(over: Partial<Schemas["ZoneNow"]> = {}): Schemas["ZoneNow"] {
  return {
    zone_id: 1,
    code: "FC",
    name: "Food Court",
    capacity: 900,
    occupancy: 450,
    occupancy_ratio: 0.5,
    level: "NORMAL",
    density_ppm2: 0.6,
    inflow: 10,
    outflow: 8,
    mean_speed_mps: null,
    quality: "OK",
    staleness_s: 30,
    data_origin: "SYNTHETIC",
    ...over,
  };
}

const forecast = (h: number, level: Schemas["Forecast"]["level"], p50: number) => ({
  horizon_min: h,
  target_time: "2027-03-12T12:00:00Z",
  p10: p50 - 10,
  p50,
  p90: p50 + 10,
  level,
  risk_score: 0.5,
  is_fallback: false,
});

describe("TC-FE-02 ZoneCard staleness and quality", () => {
  it("shows a stale indicator after 3 minutes", () => {
    render(<ZoneCard zone={now({ staleness_s: 240 })} thresholds={undefined} forecasts={[]} />);
    expect(screen.getByText("Stale (4 min)")).toBeTruthy();
  });

  it("shows no stale indicator for fresh data, and 'No data' without a count", () => {
    const { rerender } = render(
      <ZoneCard zone={now({ staleness_s: 170 })} thresholds={undefined} forecasts={[]} />,
    );
    expect(screen.queryByText(/Stale/)).toBeNull();
    rerender(
      <ZoneCard
        zone={now({ occupancy: null, occupancy_ratio: null, level: null })}
        thresholds={undefined}
        forecasts={[]}
      />,
    );
    expect(screen.getAllByText("No data").length).toBeGreaterThan(0);
  });

  it("warns about dense scenes and fallback forecasts", () => {
    render(
      <ZoneCard
        zone={now({ quality: "LOW_CONFIDENCE" })}
        thresholds={undefined}
        forecasts={[{ ...forecast(5, "NORMAL", 400), is_fallback: true }]}
      />,
    );
    expect(screen.getByText("Dense scene: count may be low")).toBeTruthy();
    expect(screen.getByText("Persistence fallback")).toBeTruthy();
  });
});

describe("TC-FE-03 VenueMap horizon selector", () => {
  const venue: Schemas["VenueOut"] = {
    venue_id: 1,
    name: "V",
    address: null,
    floor_plan_path: null,
    plan_width: 200,
    plan_height: 100,
    rho_plan: 1.5,
  };
  const zone: Schemas["ZoneOut"] = {
    zone_id: 1,
    code: "FC",
    name: "Food Court",
    zone_type: "FOOD",
    usable_area_m2: 800,
    planning_capacity: 900,
    polygon: [
      [10, 10],
      [90, 10],
      [90, 90],
    ],
    is_entry: false,
    is_exit: false,
    neighbours: {},
    thresholds: { elevated: 0.6, high: 0.8, critical: 0.95, source: "DEFAULT" },
  };

  it("fills zones from the current level, then from the chosen forecast horizon", async () => {
    render(
      <VenueMap
        venue={venue}
        zones={[zone]}
        connections={[]}
        current={[now()]}
        forecasts={new Map([[1, [forecast(5, "ELEVATED", 600), forecast(15, "HIGH", 760)]]])}
      />,
    );
    expect(screen.getByRole("img", { name: "Food Court, 450 of 900, Normal" })).toBeTruthy();
    await userEvent.click(screen.getByRole("radio", { name: "+15 min" }));
    expect(screen.getByRole("img", { name: "Food Court, 760 of 900, High" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "Venue map, forecast in 15 minutes" })).toBeTruthy();
    await userEvent.click(screen.getByRole("radio", { name: "+30 min" }));
    expect(screen.getByRole("img", { name: "Food Court, no data, unknown" })).toBeTruthy();
  });

  it("treats stale current data as unknown on the map", () => {
    render(
      <VenueMap
        venue={venue}
        zones={[zone]}
        connections={[]}
        current={[now({ staleness_s: 600 })]}
        forecasts={new Map()}
      />,
    );
    expect(screen.getByRole("img", { name: "Food Court, 450 of 900, unknown" })).toBeTruthy();
  });
});
