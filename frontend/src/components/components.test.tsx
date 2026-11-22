/** TC-FE-01 (doc 17 §2.7) and the shared states / forecast notices (doc 15 §4). */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LevelBadge } from "./LevelBadge";
import { LEVELS, type Level } from "./levels";
import { forecastNotice, noticeText } from "./notices";
import { EmptyState, ErrorState, Notice } from "./States";

describe("TC-FE-01 LevelBadge", () => {
  it.each(Object.keys(LEVELS) as Level[])("%s shows its shape and its word", (lvl) => {
    const { container } = render(<LevelBadge level={lvl} />);
    expect(screen.getByText(LEVELS[lvl].label)).toBeTruthy(); // never colour alone
    expect(container.textContent).toContain(LEVELS[lvl].shape);
  });

  it("says No data without a level", () => {
    render(<LevelBadge level={null} />);
    expect(screen.getByText("No data")).toBeTruthy();
  });

  it("uses a distinct colour and shape per level", () => {
    const all = Object.values(LEVELS);
    expect(new Set(all.map((l) => l.colour)).size).toBe(4);
    expect(new Set(all.map((l) => l.shape)).size).toBe(4);
  });
});

describe("forecast notices (doc 15 §4)", () => {
  const start = "2027-03-12T10:30:00Z";
  it("warms up for the first 15 minutes", () => {
    const n = forecastNotice({
      eventStart: start,
      asOf: "2027-03-12T10:40:00Z",
      issuedAt: "2027-03-12T10:40:00Z",
      allFallback: true,
    });
    expect(n).toEqual({ kind: "warmup" });
    expect(noticeText({ kind: "warmup" })).toContain("warming up");
  });

  it("flags forecasts more than 3 min behind the counts, before the fallback note", () => {
    expect(
      forecastNotice({
        eventStart: start,
        asOf: "2027-03-12T12:10:00Z",
        issuedAt: "2027-03-12T12:05:00Z",
        allFallback: true,
      }),
    ).toEqual({ kind: "stale", minutes: 5 });
    expect(
      forecastNotice({
        eventStart: start,
        asOf: "2027-03-12T12:10:00Z",
        issuedAt: "2027-03-12T12:08:00Z",
        allFallback: true,
      }),
    ).toEqual({ kind: "fallback" });
  });

  it("is silent when forecasts are fresh and learned, or absent", () => {
    const fresh = { eventStart: start, asOf: "2027-03-12T12:10:00Z", allFallback: false };
    expect(forecastNotice({ ...fresh, issuedAt: "2027-03-12T12:10:00Z" })).toBeNull();
    expect(forecastNotice({ ...fresh, issuedAt: null })).toBeNull();
  });
});

describe("shared states", () => {
  it("announce themselves to assistive technology", () => {
    render(
      <>
        <EmptyState title="Nothing yet">hint</EmptyState>
        <ErrorState>try again</ErrorState>
        <Notice tone="warn">stale</Notice>
      </>,
    );
    expect(screen.getByRole("heading", { name: "Nothing yet" })).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("try again");
    expect(screen.getByRole("status").textContent).toBe("stale");
  });
});
