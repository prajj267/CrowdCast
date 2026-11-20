/**
 * App shell (doc 15 §3): top bar with event selector, status, event clock and data origin;
 * a permanent banner on synthetic events; navigation for the five pages (D1). No login or
 * user menu (D7).
 */
import { NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { useCurrent, useEvent, useEvents } from "../hooks/queries";

const PAGES = [
  { path: "live", label: "Live" },
  { path: "predictions", label: "Predictions" },
  { path: "alerts", label: "Alerts" },
  { path: "history", label: "History" },
  { path: "event", label: "Event & venue" },
] as const;

function eventClock(iso: string | null | undefined): string {
  if (!iso) return "--:--";
  return new Date(iso).toISOString().slice(11, 16);
}

export function Shell() {
  const { eventId = "" } = useParams();
  const page = useLocation().pathname.split("/")[3] ?? "live";
  const id = Number(eventId);
  const navigate = useNavigate();
  const events = useEvents();
  const event = useEvent(id);
  const current = useCurrent(id);
  const origin = current.data?.zones[0]?.data_origin;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line bg-surface px-4 py-2">
        <span className="text-base font-semibold tracking-tight">CROWDCAST</span>

        <label className="flex items-center gap-2 text-muted">
          <span className="sr-only">Event</span>
          <select
            className="rounded border border-line bg-surface px-2 py-1 text-ink"
            value={eventId}
            onChange={(e) => navigate(`/events/${e.target.value}/${page}`)}
          >
            {events.data?.events.map((ev) => (
              <option key={ev.event_id} value={ev.event_id}>
                {ev.name}
              </option>
            ))}
          </select>
        </label>

        {event.data && (
          <span className="rounded-full border border-line px-2 py-0.5 text-xs text-muted">
            {event.data.status === "LIVE"
              ? "Live"
              : event.data.status === "PLANNED"
                ? "Planned"
                : "Ended"}
          </span>
        )}

        <span className="text-muted">
          Event time{" "}
          <span className="text-lg font-medium text-ink">{eventClock(current.data?.as_of)}</span>{" "}
          UTC
        </span>

        {origin && (
          <span className="text-muted">
            Data: <span className="text-ink">{origin.toLowerCase()}</span>
          </span>
        )}
      </header>

      {event.data?.is_synthetic && (
        <div role="note" className="synthetic-strip px-4 py-1.5 text-ink">
          <strong className="font-semibold">Synthetic data.</strong> A simulated crowd from CROWDSIM
          with placeholder parameters, not real people.
        </div>
      )}

      <div className="flex flex-1">
        <nav aria-label="Pages" className="w-44 shrink-0 border-r border-line px-2 py-4">
          <ul className="space-y-1">
            {PAGES.map((p) => (
              <li key={p.path}>
                <NavLink
                  to={`/events/${eventId}/${p.path}`}
                  className={({ isActive }) =>
                    `block rounded px-3 py-1.5 ${isActive ? "bg-surface font-medium text-ink shadow-[inset_3px_0_0_var(--accent)]" : "text-muted hover:text-ink"}`
                  }
                >
                  {p.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main className="min-w-0 flex-1 p-4">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
