/**
 * ScheduleStrip (doc 15 §2.3): the published schedule as one row per zone across the event,
 * with venue-wide items in their own row and an hourly scale. Positions are percentages of the
 * event duration, so the strip needs no charting library.
 */
import type { Schemas } from "../../api/client";
import { hhmm, stripLayout } from "./eventFormat";

interface Props {
  items: Schemas["ScheduleItemOut"][];
  zones: { zone_id: number; code: string; name: string }[];
  start: number;
  end: number;
}

export function ScheduleStrip({ items, zones, start, end }: Props) {
  const rows = [
    ...zones
      .map((z) => ({ key: String(z.zone_id), label: z.code, title: z.name, zoneId: z.zone_id }))
      .filter((r) => items.some((i) => i.zone_id === r.zoneId)),
    ...(items.some((i) => i.zone_id === null)
      ? [{ key: "venue", label: "Venue", title: "Venue-wide", zoneId: null }]
      : []),
  ];
  const hours: number[] = [];
  for (let t = Math.ceil(start / 3_600_000) * 3_600_000; t <= end; t += 3_600_000) hours.push(t);

  return (
    <figure aria-label="Schedule timeline" className="space-y-1">
      {rows.map((r) => (
        <div key={r.key} className="flex items-center gap-2">
          <span className="w-14 shrink-0 text-xs text-muted" title={r.title}>
            {r.label}
          </span>
          <div className="relative h-6 flex-1 rounded bg-bg">
            {items
              .filter((i) => i.zone_id === r.zoneId)
              .map((i) => {
                const { left, width } = stripLayout(i, start, end);
                return (
                  <span
                    key={i.item_id}
                    title={`${i.title}, ${hhmm(i.start_time)}–${hhmm(i.end_time)}`}
                    className="absolute top-0.5 bottom-0.5 overflow-hidden rounded-sm border border-accent/40 bg-accent/15 px-1 text-[11px] leading-5 whitespace-nowrap text-ink"
                    style={{ left: `${left}%`, width: `${width}%` }}
                  >
                    {i.title}
                  </span>
                );
              })}
          </div>
        </div>
      ))}
      <div className="flex gap-2" aria-hidden="true">
        <span className="w-14 shrink-0" />
        <div className="relative h-4 flex-1">
          {hours.map((t) => (
            <span
              key={t}
              className="absolute -translate-x-1/2 text-[11px] text-muted"
              style={{ left: `${((t - start) / (end - start)) * 100}%` }}
            >
              {hhmm(new Date(t).toISOString())}
            </span>
          ))}
        </div>
      </div>
    </figure>
  );
}
