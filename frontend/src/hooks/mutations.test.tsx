/** TC-FE-05 (doc 17 §2.7): acknowledge calls the API, updates optimistically, rolls back on error. */
import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Schemas } from "../api/client";

const post = vi.hoisted(() => vi.fn());
vi.mock("../api/client", async (orig) => ({
  ...(await orig<typeof import("../api/client")>()),
  api: { POST: post },
}));

import { alertActionOptions, patchAlertData } from "./mutations";

const alert = (id: number, status: Schemas["AlertOut"]["status"]): Schemas["AlertOut"] => ({
  alert_id: id,
  zone_id: 1,
  zone_code: "FC",
  alert_type: "CURRENT",
  level: "HIGH",
  horizon_min: null,
  predicted_onset: null,
  trigger_value: 0.85,
  status,
  message: "m",
  opened_at: "2027-03-12T13:00:00Z",
  acknowledged_at: null,
  resolved_at: null,
  auto_resolved: false,
});

const live = { alerts: [alert(1, "OPEN"), alert(2, "OPEN")], next_cursor: null };
const paged = { pages: [{ alerts: [alert(1, "OPEN")], next_cursor: null }], pageParams: [null] };

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(["alerts", 9], live);
  qc.setQueryData(["alerts", 9, { status: ["OPEN"] }], paged);
  qc.setQueryData(["alerts", 10], live); // another event: never touched
  return qc;
}

const statusOf = (qc: QueryClient, key: unknown[], id: number) => {
  const d = qc.getQueryData(key) as {
    alerts?: Schemas["AlertOut"][];
    pages?: { alerts: Schemas["AlertOut"][] }[];
  };
  const list = d.alerts ?? d.pages?.[0]?.alerts ?? [];
  return list.find((a) => a.alert_id === id)?.status;
};

describe("TC-FE-05 alert actions", () => {
  beforeEach(() => post.mockReset());

  it("patches plain and paged caches", () => {
    expect(
      statusOf(
        { getQueryData: () => patchAlertData(live, 1, "resolve") } as unknown as QueryClient,
        [],
        1,
      ),
    ).toBe("RESOLVED");
    const p = patchAlertData(paged, 1, "acknowledge") as typeof paged;
    expect(p.pages[0]?.alerts[0]?.status).toBe("ACKNOWLEDGED");
    expect(patchAlertData(undefined, 1, "resolve")).toBeUndefined();
  });

  it("calls the API, shows the new status at once in every list of the event", async () => {
    const qc = setup();
    post.mockResolvedValue({ data: alert(1, "ACKNOWLEDGED"), response: new Response() });
    const opts = alertActionOptions(qc, 9);
    const ctx = await opts.onMutate({ id: 1, action: "acknowledge" });
    expect(statusOf(qc, ["alerts", 9], 1)).toBe("ACKNOWLEDGED");
    expect(statusOf(qc, ["alerts", 9, { status: ["OPEN"] }], 1)).toBe("ACKNOWLEDGED");
    expect(statusOf(qc, ["alerts", 9], 2)).toBe("OPEN");
    expect(statusOf(qc, ["alerts", 10], 1)).toBe("OPEN");
    await opts.mutationFn({ id: 1, action: "acknowledge", note: "on it" });
    expect(post).toHaveBeenCalledWith("/api/alerts/{alert_id}/acknowledge", {
      params: { path: { alert_id: 1 } },
      body: { note: "on it" },
    });
    expect(ctx.previous.length).toBe(2);
  });

  it("rolls back when the API refuses", async () => {
    const qc = setup();
    post.mockResolvedValue({
      error: { error: { code: "CONFLICT", message: "alert is already resolved" } },
      response: new Response(null, { status: 409 }),
    });
    const opts = alertActionOptions(qc, 9);
    const ctx = await opts.onMutate({ id: 1, action: "resolve" });
    expect(statusOf(qc, ["alerts", 9], 1)).toBe("RESOLVED");
    await expect(opts.mutationFn({ id: 1, action: "resolve" })).rejects.toThrow(
      "alert is already resolved",
    );
    opts.onError(new Error("409"), undefined, ctx);
    expect(statusOf(qc, ["alerts", 9], 1)).toBe("OPEN");
    expect(statusOf(qc, ["alerts", 9, { status: ["OPEN"] }], 1)).toBe("OPEN");
  });
});
