/**
 * Historical analytics (doc 15 Page 6; WORKFLOW 8.3): occupancy vs time for up to 4 zones with
 * schedule bands, predicted vs actual for a chosen zone and horizon with the period MAE, peaks
 * per zone, and a CSV export of the 1-min history. Everything is event time.
 */
import { useState } from "react";
import { useParams } from "react-router-dom";
import { useEvent, useHistory, useSchedule, useZoneTimeline, useZones } from "../../hooks/queries";
import { OccupancyChart } from "./OccupancyChart";
import { PredVsActualChart } from "./PredVsActualChart";
import {
  MAX_SERIES,
  type ZoneMeta,
  assignSlots,
  defaultSelection,
  hhmm,
  historyCsv,
  peaks,
  predVsActual,
  ratioRows,
} from "./historyData";

const HORIZONS = [5, 15, 30] as const;

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function HistoryPage() {
  const eventId = Number(useParams().eventId);
  const event = useEvent(eventId);
  const zonesQ = useZones(event.data?.venue_id);
  const schedule = useSchedule(eventId);
  const zoneList: ZoneMeta[] = (zonesQ.data?.zones ?? []).map((z) => ({
    zone_id: z.zone_id,
    code: z.code,
    name: z.name,
    capacity: z.planning_capacity,
    high: z.thresholds.high,
  }));
  const zones = new Map(zoneList.map((z) => [z.zone_id, z]));
  const history = useHistory(
    eventId,
    zoneList.map((z) => z.zone_id),
    event.data?.start_time,
    event.data?.end_time,
  );

  const [chosen, setChosen] = useState<{ ids: number[]; slots: Map<number, number> } | null>(null);
  const [pvaZone, setPvaZone] = useState<number | undefined>(undefined);
  const [horizon, setHorizon] = useState<number>(15);

  const series = history.data?.series ?? [];
  const peakList = peaks(series, zones);
  const fallbackIds = defaultSelection(peakList);
  const selection = chosen ?? { ids: fallbackIds, slots: assignSlots(new Map(), fallbackIds) };
  const pvaZoneId = pvaZone ?? selection.ids[0] ?? zoneList[0]?.zone_id;
  const timeline = useZoneTimeline(eventId, pvaZoneId, horizon);
  const pva = predVsActual(timeline.data?.points ?? []);

  if (event.isLoading || zonesQ.isLoading) return <p className="text-muted">Loading…</p>;
  if (!event.data) return <p>Cannot load the event. Check that the API is running.</p>;

  const from = Date.parse(event.data.start_time);
  const to = Date.parse(event.data.end_time);
  const toggle = (id: number) => {
    const ids = selection.ids.includes(id)
      ? selection.ids.filter((x) => x !== id)
      : [...selection.ids, id];
    setChosen({ ids, slots: assignSlots(selection.slots, ids) });
  };
  const bands = (schedule.data?.items ?? [])
    .filter((i) => i.zone_id === null || selection.ids.includes(i.zone_id))
    .map((i) => ({ from: Date.parse(i.start_time), to: Date.parse(i.end_time), title: i.title }));
  const hasData = series.some((s) => s.points.length > 0);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-xl font-semibold">History</h1>
        <button
          type="button"
          disabled={!hasData}
          onClick={() =>
            download(
              `crowdcast_event${eventId}_history.csv`,
              historyCsv(series, zones, history.data?.origin ?? null),
            )
          }
          className="rounded border border-line px-3 py-1 hover:border-accent disabled:opacity-50"
        >
          Export CSV (1-min, all zones)
        </button>
      </header>

      {history.isError && <p>Cannot load the history. Check that the API is running.</p>}
      {!history.isLoading && !hasData && (
        <p>No observations for this event yet. Replay a CROWDSIM run or run the CV pipeline.</p>
      )}

      {hasData && (
        <>
          <section
            aria-labelledby="occ-title"
            className="rounded-md border border-line bg-surface p-4"
          >
            <h2 id="occ-title" className="mb-2 text-base font-semibold">
              Occupancy over the event
            </h2>
            <fieldset className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
              <legend className="mb-1 text-xs text-muted">
                Zones on the chart (up to {MAX_SERIES})
              </legend>
              {zoneList.map((z) => {
                const on = selection.ids.includes(z.zone_id);
                return (
                  <label key={z.zone_id} className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={on}
                      disabled={!on && selection.ids.length >= MAX_SERIES}
                      onChange={() => toggle(z.zone_id)}
                    />
                    {z.name}
                  </label>
                );
              })}
            </fieldset>
            <OccupancyChart
              rows={ratioRows(series, zones, selection.ids)}
              zones={selection.ids.flatMap((id) => zones.get(id) ?? [])}
              slots={selection.slots}
              from={from}
              to={to}
              bands={bands}
            />
          </section>

          <section
            aria-labelledby="pva-title"
            className="rounded-md border border-line bg-surface p-4"
          >
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <h2 id="pva-title" className="text-base font-semibold">
                Predicted vs actual
              </h2>
              <label className="flex items-center gap-2 text-muted">
                Zone
                <select
                  className="rounded border border-line bg-surface px-2 py-1 text-ink"
                  value={pvaZoneId}
                  onChange={(e) => setPvaZone(Number(e.target.value))}
                >
                  {zoneList.map((z) => (
                    <option key={z.zone_id} value={z.zone_id}>
                      {z.name} ({z.code})
                    </option>
                  ))}
                </select>
              </label>
              <div role="radiogroup" aria-label="Horizon" className="flex">
                {HORIZONS.map((h) => (
                  <button
                    key={h}
                    type="button"
                    role="radio"
                    aria-checked={horizon === h}
                    onClick={() => setHorizon(h)}
                    className={`border border-line px-3 py-1 first:rounded-l last:rounded-r ${horizon === h ? "bg-bg font-medium text-ink shadow-[inset_0_-2px_0_var(--accent)]" : "text-muted"}`}
                  >
                    +{h} min
                  </button>
                ))}
              </div>
              <span className="text-muted">
                {pva.mae === null
                  ? "MAE: no forecasts with a known outcome yet"
                  : `MAE ${pva.mae.toFixed(1)} persons over ${pva.n} forecasts`}
              </span>
            </div>
            <PredVsActualChart rows={pva.rows} horizon={horizon} />
          </section>

          <section aria-labelledby="peaks-title">
            <h2 id="peaks-title" className="mb-2 text-base font-semibold">
              Peaks per zone
            </h2>
            <div className="overflow-x-auto rounded-md border border-line bg-surface">
              <table className="w-full text-left">
                <thead className="border-b border-line text-xs text-muted">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Zone
                    </th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">
                      Peak / capacity
                    </th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">
                      Peak %
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      At
                    </th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">
                      Minutes at High or Critical
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {[...peakList]
                    .sort((a, b) => (b.maxRatio ?? -1) - (a.maxRatio ?? -1))
                    .map((p) => {
                      const z = zones.get(p.zone_id);
                      return (
                        <tr key={p.zone_id} className="border-b border-line last:border-0">
                          <th scope="row" className="px-3 py-2 font-normal">
                            {z?.name} <span className="text-xs text-muted">{z?.code}</span>
                          </th>
                          <td className="px-3 py-2 text-right">
                            {p.max ?? "—"} / {z?.capacity}
                          </td>
                          <td className="px-3 py-2 text-right">
                            {p.maxRatio === null ? "—" : `${Math.round(p.maxRatio * 100)} %`}
                          </td>
                          <td className="px-3 py-2">{hhmm(p.at)}</td>
                          <td className="px-3 py-2 text-right">{p.minutesHigh}</td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
