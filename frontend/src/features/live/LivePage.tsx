/**
 * Live monitoring (doc 15 Page 4): venue map and active alerts side by side, zone cards sorted by
 * risk below.
 */
import { useParams } from "react-router-dom";
import {
  useAlerts,
  useConnections,
  useCurrent,
  useEvent,
  usePredictions,
  useVenue,
  useZones,
} from "../../hooks/queries";
import { forecastNotice, noticeText } from "../../components/notices";
import { ApiHint, EmptyState, ErrorState, Loading, Notice } from "../../components/States";
import { AlertList } from "./AlertList";
import { VenueMap } from "./VenueMap";
import { ZoneCard } from "./ZoneCard";

export function LivePage() {
  const eventId = Number(useParams().eventId);
  const event = useEvent(eventId);
  const current = useCurrent(eventId);
  const predictions = usePredictions(eventId);
  const alerts = useAlerts(eventId);
  const zones = useZones(event.data?.venue_id);
  const venue = useVenue(event.data?.venue_id);
  const connections = useConnections(event.data?.venue_id);

  if (current.isLoading) return <Loading what="the latest counts" />;
  if (!current.data)
    return (
      <ErrorState>
        <ApiHint />
      </ErrorState>
    );

  const forecastsBy = new Map(predictions.data?.zones.map((z) => [z.zone_id, z.forecasts]) ?? []);
  const thresholdsBy = new Map(zones.data?.zones.map((z) => [z.zone_id, z.thresholds]) ?? []);
  const risk = (zoneId: number) =>
    Math.max(0, ...(forecastsBy.get(zoneId) ?? []).map((f) => f.risk_score ?? 0));
  const sorted = [...current.data.zones].sort((a, b) => risk(b.zone_id) - risk(a.zone_id));
  const hasData = current.data.as_of !== null;
  const allFallback =
    (predictions.data?.zones.length ?? 0) > 0 &&
    (predictions.data?.zones.every((z) => z.forecasts.every((f) => f.is_fallback)) ?? false);
  const notice = forecastNotice({
    eventStart: event.data?.start_time,
    asOf: current.data.as_of,
    issuedAt: predictions.data?.issued_at,
    allFallback,
  });

  return (
    <div className="space-y-3">
      {notice && (
        <Notice tone={notice.kind === "stale" ? "warn" : "info"}>{noticeText(notice)}</Notice>
      )}
      {!hasData && (
        <EmptyState title="No counts for this event yet">
          Replay a CROWDSIM run or start the CV pipeline to see the zones fill in.
        </EmptyState>
      )}

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-4">
          {venue.data && zones.data ? (
            <VenueMap
              venue={venue.data}
              zones={zones.data.zones}
              connections={connections.data?.connections ?? []}
              current={current.data.zones}
              forecasts={forecastsBy}
            />
          ) : (
            <div
              className="aspect-[3/2] rounded-md border border-line bg-surface"
              aria-hidden="true"
            />
          )}
          <section aria-label="Zones" className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
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
        </div>
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
