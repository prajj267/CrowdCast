import { Navigate } from "react-router-dom";
import { useEvents } from "../hooks/queries";

/** "/" opens the newest event's Live page. */
export function Home() {
  const events = useEvents();
  if (events.isLoading) return <p className="p-6 text-muted">Loading events…</p>;
  if (events.isError)
    return (
      <p className="p-6">
        Cannot reach the API. Start it with{" "}
        <code>uv run uvicorn crowdcast.api.app:app --reload</code> in <code>backend/</code>.
      </p>
    );
  const newest = events.data?.events[0];
  if (!newest)
    return (
      <p className="p-6">
        No events yet. Load one with{" "}
        <code>uv run python -m tools.load_config event ../configs/events/…</code>.
      </p>
    );
  return <Navigate to={`/events/${newest.event_id}/live`} replace />;
}

/** Pages that later tasks fill in. */
export function NotBuiltYet({ title, task }: { title: string; task: string }) {
  return (
    <section>
      <h1 className="text-xl font-semibold">{title}</h1>
      <p className="mt-2 text-muted">This page arrives in task {task}.</p>
    </section>
  );
}
