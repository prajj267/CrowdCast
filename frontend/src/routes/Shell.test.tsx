/** TC-FE-04 (synthetic banner on every event page, doc 17 §2.7), data origin, connection lost. */
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  synthetic: true,
  currentError: false,
}));

vi.mock("../hooks/queries", () => ({
  useEvents: () => ({ data: { events: [{ event_id: 5, name: "Fest" }] } }),
  useEvent: () => ({
    data: {
      event_id: 5,
      venue_id: 1,
      name: "Fest",
      status: "LIVE",
      is_synthetic: state.synthetic,
    },
  }),
  useCurrent: () => ({
    isError: state.currentError,
    dataUpdatedAt: Date.parse("2026-11-22T11:00:00Z"),
    data: { as_of: "2027-03-12T14:02:00Z", zones: [] },
  }),
}));

import { Shell } from "./Shell";

const PAGES = ["live", "predictions", "alerts", "history", "event"];

function at(page: string) {
  return render(
    <MemoryRouter initialEntries={[`/events/5/${page}`]}>
      <Routes>
        <Route path="/events/:eventId" element={<Shell />}>
          {PAGES.map((p) => (
            <Route key={p} path={p} element={<p>{p} page</p>} />
          ))}
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("TC-FE-04 Shell", () => {
  beforeEach(() => {
    state.synthetic = true;
    state.currentError = false;
  });

  it.each(PAGES)("shows the synthetic banner and origin on the %s page", (page) => {
    at(page);
    expect(screen.getByText(`${page} page`)).toBeTruthy();
    expect(screen.getByRole("note").textContent).toContain("SYNTHETIC DATA: not a real crowd");
    expect(screen.getByText("SYNTHETIC")).toBeTruthy();
  });

  it("shows REAL and no synthetic banner for a real event", () => {
    state.synthetic = false;
    at("live");
    expect(screen.queryByRole("note")).toBeNull();
    expect(screen.getByText("REAL")).toBeTruthy();
  });

  it("announces a lost connection with the time of the data on screen", () => {
    state.currentError = true;
    at("live");
    const banner = screen.getByRole("status");
    expect(banner.textContent).toContain("Connection lost.");
    expect(banner.textContent).toContain("Showing data from 14:02 event time");
  });
});
