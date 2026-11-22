/**
 * Alert history table (doc 15 Page 7): level (shape + word), zone, type, opened / onset in event
 * time, status and resolution. A row's zone button opens the detail panel.
 */
import { LevelBadge } from "../../components/LevelBadge";
import type { Level } from "../../components/levels";
import { type Alert, hhmm, resolvedText, statusLabel, typeLabel } from "./alertFormat";

interface Props {
  alerts: Alert[];
  selected: number | null;
  onSelect: (alertId: number) => void;
}

export function AlertsTable({ alerts, selected, onSelect }: Props) {
  if (alerts.length === 0)
    return (
      <p className="rounded-md border border-line bg-surface p-4 text-muted">
        No alerts match these filters.
      </p>
    );
  return (
    <div className="overflow-x-auto rounded-md border border-line bg-surface">
      <table className="w-full text-left">
        <caption className="sr-only">Alerts, newest first</caption>
        <thead className="border-b border-line text-xs text-muted">
          <tr>
            {["Level", "Zone", "Type", "Opened", "Onset", "Status", "Resolved"].map((h) => (
              <th key={h} scope="col" className="px-3 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {alerts.map((a) => {
            const isSel = a.alert_id === selected;
            return (
              <tr
                key={a.alert_id}
                aria-selected={isSel}
                className={`border-b border-line last:border-0 ${isSel ? "bg-bg" : ""} ${a.status === "RESOLVED" ? "text-muted" : ""}`}
              >
                <td className="px-3 py-2">
                  <LevelBadge level={a.level as Level} />
                </td>
                <th scope="row" className="px-3 py-2 font-normal">
                  <button
                    type="button"
                    onClick={() => onSelect(a.alert_id)}
                    aria-pressed={isSel}
                    className="font-medium text-ink hover:text-accent"
                  >
                    {a.zone_code}
                  </button>
                </th>
                <td className="px-3 py-2">{typeLabel(a)}</td>
                <td className="px-3 py-2">{hhmm(a.opened_at)}</td>
                <td className="px-3 py-2">{hhmm(a.predicted_onset)}</td>
                <td className="px-3 py-2">{statusLabel(a)}</td>
                <td className="px-3 py-2 text-xs">{resolvedText(a)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
