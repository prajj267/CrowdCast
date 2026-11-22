/**
 * Display rules for alerts (doc 15 Page 7). Times: ``opened_at``, ``predicted_onset`` and an
 * AUTO resolution are event time (the prediction cycle's clock); an operator's acknowledge or
 * resolve is stamped with the wall clock (doc 14 §6), so those are labelled as such.
 */
import type { Schemas } from "../../api/client";

export type Alert = Schemas["AlertOut"];
export type TypeFilter = "ALL" | "CURRENT" | "PREDICTED";

export function hhmm(iso: string | null): string {
  return iso ? new Date(iso).toISOString().slice(11, 16) : "—";
}

export function typeLabel(a: Alert): string {
  return a.alert_type === "CURRENT" ? "Now" : `Forecast +${a.horizon_min ?? "?"} min`;
}

export function statusLabel(a: Alert): string {
  if (a.status === "RESOLVED") return a.auto_resolved ? "Resolved (auto)" : "Resolved";
  return a.status === "ACKNOWLEDGED" ? "Acknowledged" : "Open";
}

/** "13:05 event time" or "18:42 UTC wall clock" for the resolution. */
export function resolvedText(a: Alert): string {
  if (!a.resolved_at) return "—";
  return a.auto_resolved
    ? `${hhmm(a.resolved_at)} event time`
    : `${hhmm(a.resolved_at)} UTC wall clock`;
}

export function percent(u: number | null): string {
  return u === null ? "—" : `${Math.round(u * 100)} %`;
}

export function byType(alerts: Alert[], t: TypeFilter): Alert[] {
  return t === "ALL" ? alerts : alerts.filter((a) => a.alert_type === t);
}
