import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Schemas } from "../../api/client";
import { ScheduleStrip } from "./ScheduleStrip";
import { minutes, stripLayout, words } from "./eventFormat";

const START = Date.parse("2027-03-12T10:00:00Z");
const END = Date.parse("2027-03-12T14:00:00Z");

function item(id: number, zone: number | null, s: string, e: string): Schemas["ScheduleItemOut"] {
  return {
    item_id: id,
    zone_id: zone,
    zone_code: null,
    title: `Item ${id}`,
    category: "PERFORMANCE",
    start_time: `2027-03-12T${s}:00Z`,
    end_time: `2027-03-12T${e}:00Z`,
    expected_attendance: null,
    attraction_weight: 1,
  };
}

describe("event page helpers", () => {
  it("positions items as % of the event and clips them to it", () => {
    expect(stripLayout(item(1, 1, "11:00", "12:00"), START, END)).toEqual({ left: 25, width: 25 });
    expect(stripLayout(item(2, 1, "09:00", "10:30"), START, END)).toEqual({
      left: 0,
      width: 12.5,
    });
  });

  it("formats durations and enum codes", () => {
    expect(minutes(45)).toBe("45 s");
    expect(minutes(150)).toBe("2.5 min");
    expect(words("ENTRY_EXIT")).toBe("Entry exit");
  });

  it("draws one row per zone with items plus a venue-wide row", () => {
    render(
      <ScheduleStrip
        items={[item(1, 1, "11:00", "12:00"), item(2, null, "13:00", "13:30")]}
        zones={[
          { zone_id: 1, code: "MS", name: "Main stage" },
          { zone_id: 2, code: "FC", name: "Food court" },
        ]}
        start={START}
        end={END}
      />,
    );
    expect(screen.getByText("MS")).toBeTruthy();
    expect(screen.queryByText("FC")).toBeNull(); // no items -> no row
    expect(screen.getByText("Venue")).toBeTruthy();
    expect(screen.getByTitle("Item 1, 11:00–12:00")).toBeTruthy();
  });
});
