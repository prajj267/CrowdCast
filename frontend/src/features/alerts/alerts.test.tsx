import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AlertDetail } from "./AlertDetail";
import { AlertsTable } from "./AlertsTable";
import { type Alert, byType, resolvedText, statusLabel, typeLabel } from "./alertFormat";

function alert(over: Partial<Alert> = {}): Alert {
  return {
    alert_id: 7,
    zone_id: 1,
    zone_code: "FC",
    alert_type: "PREDICTED",
    level: "HIGH",
    horizon_min: 15,
    predicted_onset: "2027-03-12T13:20:00Z",
    trigger_value: 0.86,
    status: "OPEN",
    message: "Food Court: HIGH forecast in 15 min",
    opened_at: "2027-03-12T13:05:00Z",
    acknowledged_at: null,
    resolved_at: null,
    auto_resolved: false,
    ...over,
  };
}

describe("alert formatting", () => {
  it("labels type, status and the clock of each time", () => {
    expect(typeLabel(alert())).toBe("Forecast +15 min");
    expect(typeLabel(alert({ alert_type: "CURRENT", horizon_min: null }))).toBe("Now");
    expect(statusLabel(alert({ status: "RESOLVED", auto_resolved: true }))).toBe("Resolved (auto)");
    // auto resolution comes from the cycle (event time); operator actions use the wall clock
    expect(resolvedText(alert({ resolved_at: "2027-03-12T13:40:00Z", auto_resolved: true }))).toBe(
      "13:40 event time",
    );
    expect(resolvedText(alert({ resolved_at: "2026-11-22T11:02:00Z" }))).toBe(
      "11:02 UTC wall clock",
    );
    const both = [alert(), alert({ alert_id: 8, alert_type: "CURRENT" })];
    expect(byType(both, "CURRENT").map((a) => a.alert_id)).toEqual([8]);
    expect(byType(both, "ALL")).toHaveLength(2);
  });
});

describe("AlertsTable", () => {
  it("shows level as shape plus word and opens the detail from the zone", async () => {
    const onSelect = vi.fn();
    render(<AlertsTable alerts={[alert()]} selected={null} onSelect={onSelect} />);
    expect(screen.getByText("High")).toBeTruthy();
    expect(screen.getByText("Forecast +15 min")).toBeTruthy();
    expect(screen.getByText("13:20")).toBeTruthy(); // predicted onset
    await userEvent.click(screen.getByRole("button", { name: "FC" }));
    expect(onSelect).toHaveBeenCalledWith(7);
  });

  it("says when nothing matches", () => {
    render(<AlertsTable alerts={[]} selected={null} onSelect={() => {}} />);
    expect(screen.getByText("No alerts match these filters")).toBeTruthy();
  });
});

describe("AlertDetail", () => {
  it("acknowledges with the typed note", async () => {
    const onAction = vi.fn();
    render(
      <AlertDetail
        alert={alert()}
        busy={false}
        error={null}
        onAction={onAction}
        onClose={() => {}}
      />,
    );
    expect(screen.getByText("86 % of planning capacity")).toBeTruthy();
    await userEvent.type(screen.getByRole("textbox"), "steward sent");
    await userEvent.click(screen.getByRole("button", { name: "Acknowledge" }));
    expect(onAction).toHaveBeenCalledWith("acknowledge", "steward sent");
  });

  it("offers only Resolve once acknowledged, and no actions once resolved", () => {
    const { rerender } = render(
      <AlertDetail
        alert={alert({ status: "ACKNOWLEDGED", acknowledged_at: "2026-11-22T11:00:00Z" })}
        busy={false}
        error={null}
        onAction={() => {}}
        onClose={() => {}}
      />,
    );
    expect(screen.queryByRole("button", { name: "Acknowledge" })).toBeNull();
    expect(screen.getByRole("button", { name: "Resolve" })).toBeTruthy();
    rerender(
      <AlertDetail
        alert={alert({
          status: "RESOLVED",
          resolved_at: "2027-03-12T13:40:00Z",
          auto_resolved: true,
        })}
        busy={false}
        error={null}
        onAction={() => {}}
        onClose={() => {}}
      />,
    );
    expect(screen.queryByRole("button", { name: "Resolve" })).toBeNull();
  });
});
