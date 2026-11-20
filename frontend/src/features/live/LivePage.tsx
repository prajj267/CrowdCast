/**
 * Live monitoring (doc 15 Page 4): zone cards sorted by risk and the active alerts. The venue map
 * joins the left column in task 4.5.5.
 */
import { useParams } from "react-router-dom";
import { useAlerts, useCurrent, useEvent, usePredictions, useZones } from "../../hooks/queries";
import { AlertList } from "./AlertList";
import { ZoneCard } from "./ZoneCard";

export function LivePage() {
  const eventId = Number(useParams().eventId);
  const event = useEvent(eventId);
  const current = useCurrent(eventId);
  const predictions = usePredictions(eventId);
  const alerts = useAlerts(eventId);
  const zones = useZones(event.data?.venue_id);

  if (current.isLoading) return <p className="text-muted">Loading the latest counts…</p>;
  if (!current.data) return <p>Cannot load the latest counts. Check that the API is running.</p>;

  const forecastsBy = new Map(predictions.data?.zones.map((z) => [z.zone_id, z.forecasts]) ?? []);
  const thresholdsBy = new Map(zones.data?.zones.map((z) => [z.zone_id, z.thresholds]) ?? []);
  const risk = (zoneId: number) =>
    Math.max(0, ...(forecastsBy.get(zoneId) ?? []).map((f) => f.risk_score ?? 0));
  const sorted = [...current.data.zones].sort((a, b) => risk(b.zone_id) - risk(a.zone_id));
  const hasData = current.data.as_of !== null;
  const allFallback =
    (predictions.data?.zones.length ?? 0) > 0 &&
    predictions.data?.zones.every((z) => z.forecasts.every((f) => f.is_fallback));

  return (
    <div className="space-y-3">
      {current.isError && (
        <p role="status" className="rounded-md border border-line bg-surface px-3 py-2">
          Connection lost. Showing data from {current.data.as_of?.slice(11, 16) ?? "earlier"}.
        </p>
      )}
      {allFallback && (
        <p className="text-muted">
          Forecasts use persistence (the latest count carried forward) until a trained model is
          active.
        </p>
      )}
      {!hasData && (
        <p>
          No counts for this event yet. Replay a CROWDSIM run or start the CV pipeline to see zones
          fill in.
        </p>
      )}

      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <section
          aria-label="Zones"
          className="grid content-start gap-3 sm:grid-cols-2 2xl:grid-cols-3"
        >
          {sorted.map((z) => (
            <ZoneCard
              key={z.zone_id}
              zone={z}
              thresholds={thresholdsBy.get(z.zone_id)}
              forecasts={forecastsBy.get(z.zone_id) ?? []}
              showFallback={!allFallback}
            />
          ))}
        </section>
        <section aria-label="Active alerts" className="min-w-0">
          <h2 className="mb-2 text-base font-semibold">Active alerts</h2>
          <AlertList
            eventId={eventId}
            alerts={alerts.data?.alerts ?? []}
            asOf={current.data.as_of}
          />
        </section>
      </div>
    </div>
  );
}
