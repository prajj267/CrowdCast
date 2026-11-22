/**
 * Event & venue (doc 15 Pages 2-3, reduced per D1; WORKFLOW 8.4): READ-ONLY. Event facts and
 * active model, the published schedule (strip + table), zones with capacity and thresholds,
 * connections, and the venue-graph validation result. Changes are made in the YAML files and
 * loaded with tools.load_config (no polygon editor, no create/edit forms, no authentication).
 */
import { ApiHint, ErrorState, Loading } from "../../components/States";
import { useParams } from "react-router-dom";
import {
  useConnections,
  useEvent,
  useGraphValidation,
  useSchedule,
  useVenue,
  useZones,
} from "../../hooks/queries";
import { ScheduleStrip } from "./ScheduleStrip";
import { dateTime, hhmm, minutes, pct, words } from "./eventFormat";

const card = "rounded-md border border-line bg-surface p-4";
const th = "px-3 py-2 font-medium";
const td = "px-3 py-2";

export function EventPage() {
  const eventId = Number(useParams().eventId);
  const event = useEvent(eventId);
  const venueId = event.data?.venue_id;
  const venue = useVenue(venueId);
  const zones = useZones(venueId);
  const connections = useConnections(venueId);
  const schedule = useSchedule(eventId);
  const validation = useGraphValidation(venueId);

  if (event.isLoading) return <Loading what="the event" />;
  if (!event.data)
    return (
      <ErrorState>
        <ApiHint />
      </ErrorState>
    );
  const ev = event.data;
  const zoneList = zones.data?.zones ?? [];
  const code = new Map(zoneList.map((z) => [z.zone_id, z.code]));
  const items = [...(schedule.data?.items ?? [])].sort((a, b) =>
    a.start_time.localeCompare(b.start_time),
  );
  const facts: [string, string][] = [
    ["Status", words(ev.status)],
    ["Data", ev.is_synthetic ? "Synthetic (CROWDSIM)" : "Real (camera counts)"],
    ["Start", `${dateTime(ev.start_time)} UTC`],
    ["End", `${dateTime(ev.end_time)} UTC`],
    ["Expected attendance", ev.expected_attendance?.toLocaleString("en") ?? "—"],
    [
      "Active model (now)",
      ev.active_model
        ? `${ev.active_model.name} ${ev.active_model.version}`
        : "none (persistence fallback)",
    ],
    [
      "Zones · cameras · schedule items",
      `${ev.zone_count} · ${ev.camera_count} · ${ev.schedule_item_count}`,
    ],
  ];

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">{ev.name}</h1>
        <p className="text-muted">
          {venue.data?.name ?? "Venue"} · read-only. Edit the YAML files in <code>configs/</code>{" "}
          and load them with <code>uv run python -m tools.load_config venue|event …</code>.
        </p>
      </header>

      <div className="grid items-start gap-4 lg:grid-cols-2">
        <section aria-labelledby="facts" className={card}>
          <h2 id="facts" className="mb-2 text-base font-semibold">
            Event
          </h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
            {facts.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted">{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section aria-labelledby="graph" className={card}>
          <h2 id="graph" className="mb-2 text-base font-semibold">
            Venue graph check
          </h2>
          {!validation.data ? (
            <p className="text-muted">Checking…</p>
          ) : validation.data.issues.length === 0 ? (
            <p>No problems: every zone is reachable and connections are consistent.</p>
          ) : (
            <>
              <p className="mb-2">
                {validation.data.valid
                  ? "Valid, with warnings:"
                  : "Not valid: fix the errors before running forecasts."}
              </p>
              <ul className="space-y-1 text-sm">
                {validation.data.issues.map((i) => (
                  <li key={`${i.code}-${i.subject}`}>
                    <span className="font-medium">{words(i.severity)}</span> {i.subject}:{" "}
                    {i.message}
                  </li>
                ))}
              </ul>
            </>
          )}
          {venue.data && (
            <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
              <dt className="text-muted">Venue</dt>
              <dd>{venue.data.name}</dd>
              <dt className="text-muted">Address</dt>
              <dd>{venue.data.address ?? "—"}</dd>
              <dt className="text-muted">Planning density</dt>
              <dd>{venue.data.rho_plan === null ? "—" : `${venue.data.rho_plan} persons/m²`}</dd>
            </dl>
          )}
        </section>
      </div>

      <section aria-labelledby="sched" className={card}>
        <h2 id="sched" className="mb-3 text-base font-semibold">
          Published schedule
        </h2>
        {items.length === 0 ? (
          <p className="text-muted">No schedule items.</p>
        ) : (
          <>
            <ScheduleStrip
              items={items}
              zones={zoneList}
              start={Date.parse(ev.start_time)}
              end={Date.parse(ev.end_time)}
            />
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left">
                <thead className="border-b border-line text-xs text-muted">
                  <tr>
                    <th scope="col" className={th}>
                      Time
                    </th>
                    <th scope="col" className={th}>
                      Item
                    </th>
                    <th scope="col" className={th}>
                      Zone
                    </th>
                    <th scope="col" className={th}>
                      Category
                    </th>
                    <th scope="col" className={`${th} text-right`}>
                      Expected
                    </th>
                    <th scope="col" className={`${th} text-right`}>
                      Attraction
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((i) => (
                    <tr key={i.item_id} className="border-b border-line last:border-0">
                      <td className={td}>
                        {hhmm(i.start_time)}–{hhmm(i.end_time)}
                      </td>
                      <th scope="row" className={`${td} font-normal`}>
                        {i.title}
                      </th>
                      <td className={td}>{i.zone_code ?? "Venue-wide"}</td>
                      <td className={td}>{words(i.category)}</td>
                      <td className={`${td} text-right`}>
                        {i.expected_attendance?.toLocaleString("en") ?? "—"}
                      </td>
                      <td className={`${td} text-right`}>{i.attraction_weight}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <section aria-labelledby="zones" className={card}>
        <h2 id="zones" className="mb-2 text-base font-semibold">
          Zones
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="border-b border-line text-xs text-muted">
              <tr>
                <th scope="col" className={th}>
                  Zone
                </th>
                <th scope="col" className={th}>
                  Type
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Area
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Capacity
                </th>
                <th scope="col" className={th}>
                  Thresholds (Elevated / High / Critical)
                </th>
                <th scope="col" className={th}>
                  Entry / exit
                </th>
              </tr>
            </thead>
            <tbody>
              {zoneList.map((z) => (
                <tr key={z.zone_id} className="border-b border-line last:border-0">
                  <th scope="row" className={`${td} font-normal`}>
                    {z.name} <span className="text-xs text-muted">{z.code}</span>
                  </th>
                  <td className={td}>{words(z.zone_type)}</td>
                  <td className={`${td} text-right`}>{z.usable_area_m2.toLocaleString("en")} m²</td>
                  <td className={`${td} text-right`}>{z.planning_capacity.toLocaleString("en")}</td>
                  <td className={td}>
                    {pct(z.thresholds.elevated)} / {pct(z.thresholds.high)} /{" "}
                    {pct(z.thresholds.critical)}
                    <span className="ml-1 text-xs text-muted">
                      {z.thresholds.source === "DEFAULT" ? "default" : "zone override"}
                    </span>
                  </td>
                  <td className={td}>
                    {[z.is_entry && "entry", z.is_exit && "exit"].filter(Boolean).join(", ") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="conns" className={card}>
        <h2 id="conns" className="mb-2 text-base font-semibold">
          Connections
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="border-b border-line text-xs text-muted">
              <tr>
                <th scope="col" className={th}>
                  From → to
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Boundary width
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Travel time
                </th>
                <th scope="col" className={th}>
                  Direction
                </th>
              </tr>
            </thead>
            <tbody>
              {(connections.data?.connections ?? []).map((c) => (
                <tr key={c.connection_id} className="border-b border-line last:border-0">
                  <th scope="row" className={`${td} font-normal`}>
                    {c.from_zone_id === null ? "Outside" : code.get(c.from_zone_id)} →{" "}
                    {c.to_zone_id === null ? "Outside" : code.get(c.to_zone_id)}
                  </th>
                  <td className={`${td} text-right`}>{c.boundary_width_m} m</td>
                  <td className={`${td} text-right`}>{minutes(c.travel_time_s)}</td>
                  <td className={td}>{c.bidirectional ? "both ways" : "one way"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
