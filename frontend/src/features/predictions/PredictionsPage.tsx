/**
 * Prediction dashboard (doc 15 Page 5; WORKFLOW 8.1): zone selector -> ForecastChart, and the
 * zone x horizon table with P10/P50/P90, level, risk score, fallback flag and model version.
 * The selected zone lives in the URL (?zone=CODE) so a view can be linked. No "Why?" panel:
 * feature attributions are not stored.
 */
import { useParams, useSearchParams } from "react-router-dom";
import { useEvent, useHistory, usePredictions, useSchedule, useZones } from "../../hooks/queries";
import { ForecastChart } from "./ForecastChart";
import { ForecastTable } from "./ForecastTable";
import {
  forecastPoints,
  hhmm,
  maxRisk,
  mergeSeries,
  observedPoints,
  scheduleBands,
  thresholdLines,
  chartWindow,
} from "./forecastSeries";

export function PredictionsPage() {
  const eventId = Number(useParams().eventId);
  const [search, setSearch] = useSearchParams();
  const event = useEvent(eventId);
  const predictions = usePredictions(eventId);
  const zones = useZones(event.data?.venue_id);
  const schedule = useSchedule(eventId);

  const latest = predictions.data;
  const byRisk = [...(latest?.zones ?? [])].sort((a, b) => (maxRisk(b) ?? -1) - (maxRisk(a) ?? -1));
  const zoneInfo = new Map(zones.data?.zones.map((z) => [z.zone_id, z]) ?? []);
  const names = new Map([...zoneInfo].map(([id, z]) => [id, z.name]));
  const wanted = search.get("zone");
  const selected = byRisk.find((z) => z.code === wanted) ?? byRisk[0]; // default: the riskiest zone
  const info = selected ? zoneInfo.get(selected.zone_id) : undefined;

  const now = latest?.issued_at ? Date.parse(latest.issued_at) : undefined;
  const span = now === undefined ? undefined : chartWindow(now);
  const history = useHistory(
    eventId,
    selected ? [selected.zone_id] : [],
    span && new Date(span.from).toISOString(),
    now === undefined ? undefined : new Date(now).toISOString(),
  );

  if (predictions.isLoading) return <p className="text-muted">Loading forecasts…</p>;
  if (predictions.isError && !latest)
    return <p>Cannot load forecasts. Check that the API is running.</p>;
  if (!latest || latest.issued_at === null || byRisk.length === 0)
    return (
      <section className="space-y-2">
        <h1 className="text-xl font-semibold">Predictions</h1>
        <p>
          No forecasts for this event yet. Run prediction cycles with{" "}
          <code>uv run python -m tools.run_predictions --event-id {eventId}</code> in{" "}
          <code>backend/</code>.
        </p>
      </section>
    );

  const select = (zoneId: number) => {
    const z = byRisk.find((x) => x.zone_id === zoneId);
    if (z) setSearch({ zone: z.code }, { replace: true });
  };
  const series =
    selected && span && now !== undefined
      ? mergeSeries(
          observedPoints(history.data?.series[0]?.points ?? []),
          forecastPoints(now, selected.current.occupancy, selected.forecasts),
        )
      : [];
  const allFallback = latest.zones.every((z) => z.forecasts.every((f) => f.is_fallback));

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <h1 className="text-xl font-semibold">Predictions</h1>
        <span className="text-muted">
          Issued {hhmm(now as number)} UTC (event time) ·{" "}
          {latest.model ? `model ${latest.model.name} ${latest.model.version}` : "no trained model"}
          {allFallback && " · persistence fallback for every zone"}
        </span>
      </header>
      {predictions.isError && (
        <p role="status" className="rounded-md border border-line bg-surface px-3 py-2">
          Connection lost. Showing the forecasts issued at {hhmm(now as number)}.
        </p>
      )}

      <section
        aria-labelledby="chart-title"
        className="rounded-md border border-line bg-surface p-4"
      >
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <h2 id="chart-title" className="text-base font-semibold">
            {info?.name ?? selected?.code}
          </h2>
          <label className="flex items-center gap-2 text-muted">
            Zone
            <select
              className="rounded border border-line bg-surface px-2 py-1 text-ink"
              value={selected?.zone_id}
              onChange={(e) => select(Number(e.target.value))}
            >
              {byRisk.map((z) => (
                <option key={z.zone_id} value={z.zone_id}>
                  {names.get(z.zone_id) ?? z.code} ({z.code})
                </option>
              ))}
            </select>
          </label>
          {info && <span className="text-xs text-muted">capacity {info.planning_capacity}</span>}
        </div>
        {selected && info && span && now !== undefined ? (
          <ForecastChart
            data={series}
            now={now}
            from={span.from}
            to={span.to}
            capacity={info.planning_capacity}
            thresholds={thresholdLines(info.planning_capacity, info.thresholds)}
            bands={scheduleBands(schedule.data?.items ?? [], selected.zone_id, span.from, span.to)}
            zoneName={info.name}
          />
        ) : (
          <div className="h-80 rounded bg-bg" aria-hidden="true" />
        )}
      </section>

      <section aria-label="Forecast table">
        <ForecastTable
          zones={byRisk}
          names={names}
          selected={selected?.zone_id}
          onSelect={select}
        />
        <p className="mt-2 text-xs text-muted">
          Sorted by risk score. Intervals are 80 % (P10–P90), conformal-calibrated when the active
          model has calibration offsets.
        </p>
      </section>
    </div>
  );
}
