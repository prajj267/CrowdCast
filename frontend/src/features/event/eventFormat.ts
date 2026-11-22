/** Formatting helpers for the Event & venue page. Times are event time (UTC). */
import type { Schemas } from "../../api/client";

export function hhmm(iso: string | null): string {
  return iso ? new Date(iso).toISOString().slice(11, 16) : "—";
}

export function dateTime(iso: string): string {
  return `${iso.slice(0, 10)} ${hhmm(iso)}`;
}

export function minutes(seconds: number): string {
  return seconds < 60 ? `${Math.round(seconds)} s` : `${(seconds / 60).toFixed(1)} min`;
}

export function pct(u: number): string {
  return `${Math.round(u * 100)} %`;
}

/** "CLOSE_EXIT" -> "Close exit" */
export function words(code: string): string {
  const s = code.toLowerCase().replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Position of a schedule item on the strip, in % of the event; clipped to the event. */
export function stripLayout(
  item: Pick<Schemas["ScheduleItemOut"], "start_time" | "end_time">,
  start: number,
  end: number,
): { left: number; width: number } {
  const span = end - start;
  const s = Math.max(start, Date.parse(item.start_time));
  const e = Math.min(end, Date.parse(item.end_time));
  return { left: ((s - start) / span) * 100, width: (Math.max(0, e - s) / span) * 100 };
}
