/**
 * Alert detail panel (doc 15 Page 7): message, trigger value, horizon and predicted onset, the
 * timeline of the alert, and acknowledge / resolve with an optional note (stored in the audit
 * log by the API). Notes and the audit trail cannot be read back yet: the API has no endpoint.
 */
import { useState } from "react";
import { LevelBadge } from "../../components/LevelBadge";
import type { Level } from "../../components/levels";
import type { AlertAction } from "../../hooks/mutations";
import { type Alert, hhmm, percent, resolvedText, statusLabel, typeLabel } from "./alertFormat";

interface Props {
  alert: Alert;
  busy: boolean;
  error: string | null;
  onAction: (action: AlertAction, note: string) => void;
  onClose: () => void;
}

export function AlertDetail({ alert, busy, error, onAction, onClose }: Props) {
  const [note, setNote] = useState("");
  const rows: [string, string][] = [
    ["Type", typeLabel(alert)],
    ["Trigger", `${percent(alert.trigger_value)} of planning capacity`],
    ["Opened", `${hhmm(alert.opened_at)} event time`],
    ...(alert.predicted_onset
      ? [["Predicted onset", `${hhmm(alert.predicted_onset)} event time`] as [string, string]]
      : []),
    ["Status", statusLabel(alert)],
    ["Acknowledged", alert.acknowledged_at ? `${hhmm(alert.acknowledged_at)} UTC wall clock` : "—"],
    ["Resolved", resolvedText(alert)],
  ];

  return (
    <aside
      aria-label={`Alert ${alert.alert_id}`}
      className="space-y-3 rounded-md border border-line bg-surface p-4"
    >
      <header className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold">
            {alert.zone_code} <span className="text-muted">#{alert.alert_id}</span>
          </h2>
          <LevelBadge level={alert.level as Level} />
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded border border-line px-2 py-0.5 text-xs hover:border-accent"
        >
          Close
        </button>
      </header>
      <p>{alert.message}</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted">{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      {alert.status !== "RESOLVED" && (
        <form
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
          }}
        >
          <label className="block text-sm text-muted">
            Note (optional, kept in the audit log)
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              maxLength={500}
              className="mt-1 block w-full rounded border border-line bg-bg px-2 py-1 text-ink"
            />
          </label>
          <div className="flex gap-2">
            {alert.status === "OPEN" && (
              <button
                type="button"
                disabled={busy}
                onClick={() => onAction("acknowledge", note)}
                className="rounded border border-line px-3 py-1 hover:border-accent disabled:opacity-50"
              >
                Acknowledge
              </button>
            )}
            <button
              type="button"
              disabled={busy}
              onClick={() => onAction("resolve", note)}
              className="rounded border border-line px-3 py-1 hover:border-accent disabled:opacity-50"
            >
              Resolve
            </button>
          </div>
          {error && (
            <p role="alert" className="text-sm">
              Action failed: {error}
            </p>
          )}
        </form>
      )}
    </aside>
  );
}
