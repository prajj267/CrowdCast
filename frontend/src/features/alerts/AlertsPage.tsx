/**
 * Alerts page (doc 15 Page 7; WORKFLOW 8.2): filters (status, level, zone on the server; type
 * in the browser), the alert history table newest first with "Load more", and a detail panel
 * with acknowledge / resolve. No users column: there is no authentication (D7).
 */
import { ApiHint, ErrorState, Loading } from "../../components/States";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { type AlertAction, useAlertAction } from "../../hooks/mutations";
import { type AlertFilters, useAlertHistory, useEvent, useZones } from "../../hooks/queries";
import { AlertDetail } from "./AlertDetail";
import { AlertsTable } from "./AlertsTable";
import { type TypeFilter, byType } from "./alertFormat";

const STATUSES = [
  ["OPEN", "Open"],
  ["ACKNOWLEDGED", "Acknowledged"],
  ["RESOLVED", "Resolved"],
] as const;

export function AlertsPage() {
  const eventId = Number(useParams().eventId);
  const event = useEvent(eventId);
  const zones = useZones(event.data?.venue_id);
  const [filters, setFilters] = useState<AlertFilters>({
    status: ["OPEN", "ACKNOWLEDGED"],
    level: null,
    zoneId: null,
  });
  const [type, setType] = useState<TypeFilter>("ALL");
  const [selected, setSelected] = useState<number | null>(null);
  const history = useAlertHistory(eventId, filters);
  const act = useAlertAction(eventId);

  const all = history.data?.pages.flatMap((p) => p.alerts) ?? [];
  const shown = byType(all, type);
  const current = all.find((a) => a.alert_id === selected) ?? null;

  const toggleStatus = (s: AlertFilters["status"][number]) =>
    setFilters((f) => ({
      ...f,
      status: f.status.includes(s) ? f.status.filter((x) => x !== s) : [...f.status, s],
    }));
  const onAction = (action: AlertAction, note: string) =>
    current && act.mutate({ id: current.alert_id, action, note: note.trim() || undefined });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Alerts</h1>

      <form
        aria-label="Filters"
        className="flex flex-wrap items-end gap-x-6 gap-y-3 rounded-md border border-line bg-surface p-3"
        onSubmit={(e) => e.preventDefault()}
      >
        <fieldset className="flex gap-3">
          <legend className="mb-1 text-xs text-muted">Status</legend>
          {STATUSES.map(([value, label]) => (
            <label key={value} className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={filters.status.includes(value)}
                onChange={() => toggleStatus(value)}
              />
              {label}
            </label>
          ))}
        </fieldset>
        <label className="flex flex-col text-xs text-muted">
          Level
          <select
            className="mt-1 rounded border border-line bg-surface px-2 py-1 text-sm text-ink"
            value={filters.level ?? ""}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                level: (e.target.value || null) as AlertFilters["level"],
              }))
            }
          >
            <option value="">Any</option>
            <option value="HIGH">High</option>
            <option value="CRITICAL">Critical</option>
            <option value="ELEVATED">Elevated</option>
          </select>
        </label>
        <label className="flex flex-col text-xs text-muted">
          Zone
          <select
            className="mt-1 rounded border border-line bg-surface px-2 py-1 text-sm text-ink"
            value={filters.zoneId ?? ""}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                zoneId: e.target.value ? Number(e.target.value) : null,
              }))
            }
          >
            <option value="">All zones</option>
            {zones.data?.zones.map((z) => (
              <option key={z.zone_id} value={z.zone_id}>
                {z.name} ({z.code})
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col text-xs text-muted">
          Type
          <select
            className="mt-1 rounded border border-line bg-surface px-2 py-1 text-sm text-ink"
            value={type}
            onChange={(e) => setType(e.target.value as TypeFilter)}
          >
            <option value="ALL">Now and forecast</option>
            <option value="CURRENT">Now (current level)</option>
            <option value="PREDICTED">Forecast</option>
          </select>
        </label>
      </form>

      {history.isError && !history.data && (
        <ErrorState>
          <ApiHint />
        </ErrorState>
      )}
      {history.isLoading ? (
        <Loading what="alerts" />
      ) : (
        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="min-w-0 space-y-2">
            <AlertsTable alerts={shown} selected={selected} onSelect={setSelected} />
            <p className="text-xs text-muted">
              {shown.length} alert{shown.length === 1 ? "" : "s"} shown, newest first. Opened and
              onset times are event time.
            </p>
            {history.hasNextPage && (
              <button
                type="button"
                onClick={() => history.fetchNextPage()}
                disabled={history.isFetchingNextPage}
                className="rounded border border-line px-3 py-1 hover:border-accent"
              >
                {history.isFetchingNextPage ? "Loading…" : "Load more"}
              </button>
            )}
          </div>
          {current && (
            <AlertDetail
              key={current.alert_id}
              alert={current}
              busy={act.isPending}
              error={act.isError ? act.error.message : null}
              onAction={onAction}
              onClose={() => setSelected(null)}
            />
          )}
        </div>
      )}
    </div>
  );
}
