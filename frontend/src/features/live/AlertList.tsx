/**
 * Active alerts (doc 15 §2.3): sorted by level, then onset; acknowledge / resolve. Relative
 * times use the event clock (as_of), not the wall clock, so replays read correctly.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, type Schemas } from "../../api/client";
import { LevelShape } from "../../components/LevelBadge";
import type { Level } from "../../components/levels";

const RANK: Record<string, number> = { CRITICAL: 0, HIGH: 1, ELEVATED: 2, NORMAL: 3 };

type Alert = Schemas["AlertOut"];

function onset(a: Alert): string {
  return a.predicted_onset ?? a.opened_at;
}

function hhmm(iso: string): string {
  return new Date(iso).toISOString().slice(11, 16);
}

/** "in 12 min" while the onset is ahead of the event clock, "since 13:03" once it has passed. */
function when(iso: string, asOf: string | null | undefined): string {
  const min = asOf ? Math.round((Date.parse(iso) - Date.parse(asOf)) / 60_000) : 0;
  return min > 0 ? `in ${min} min` : `since ${hhmm(iso)}`;
}

export function AlertList({
  eventId,
  alerts,
  asOf,
}: {
  eventId: number;
  alerts: Alert[];
  asOf: string | null | undefined;
}) {
  const qc = useQueryClient();
  const act = useMutation({
    mutationFn: async ({ id, action }: { id: number; action: "acknowledge" | "resolve" }) =>
      unwrap(
        await api.POST(`/api/alerts/{alert_id}/${action}`, {
          params: { path: { alert_id: id } },
          body: {},
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts", eventId] }),
  });

  const active = alerts
    .filter((a) => a.status !== "RESOLVED")
    .sort(
      (a, b) => (RANK[a.level] ?? 9) - (RANK[b.level] ?? 9) || onset(a).localeCompare(onset(b)),
    );

  if (active.length === 0) {
    return <p className="text-muted">No active alerts. Zones above High appear here.</p>;
  }

  return (
    <ul className="space-y-2">
      {active.map((a) => (
        <li key={a.alert_id} className="rounded-md border border-line bg-surface p-3">
          <p className="flex items-start gap-2">
            <span className="mt-0.5">
              <LevelShape level={a.level as Level} />
            </span>
            <span>
              <span className="font-medium">{a.zone_code}</span>{" "}
              {a.alert_type === "PREDICTED"
                ? `forecast ${a.level.toLowerCase()} ${when(onset(a), asOf)}`
                : `${a.level.toLowerCase()} ${when(a.opened_at, asOf)}`}
              <span className="block text-xs text-muted">
                Opened {hhmm(a.opened_at)}
                {a.trigger_value != null && ` at ${Math.round(a.trigger_value * 100)}% of capacity`}
                {a.alert_type === "PREDICTED" &&
                  a.horizon_min != null &&
                  `, ${a.horizon_min} min ahead`}
                {a.status === "ACKNOWLEDGED" && ". Acknowledged"}
              </span>
            </span>
          </p>
          <div className="mt-2 flex gap-2">
            {a.status === "OPEN" && (
              <button
                type="button"
                className="rounded border border-line px-2 py-1 text-xs hover:border-accent"
                disabled={act.isPending}
                onClick={() => act.mutate({ id: a.alert_id, action: "acknowledge" })}
              >
                Acknowledge
              </button>
            )}
            <button
              type="button"
              className="rounded border border-line px-2 py-1 text-xs hover:border-accent"
              disabled={act.isPending}
              onClick={() => act.mutate({ id: a.alert_id, action: "resolve" })}
            >
              Resolve
            </button>
          </div>
        </li>
      ))}
      {act.isError && <li className="text-sm">Action failed: {act.error.message}</li>}
    </ul>
  );
}
