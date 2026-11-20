/**
 * VenueMap (doc 15 §2.3): zone polygons from the venue YAML, filled by level now or at a chosen
 * horizon. Every polygon carries an aria-label and a tooltip (doc 15 §5); all of it is also in
 * the zone cards. Density mode and flow-weighted edges come later (Phase 8).
 */
import { useState } from "react";
import type { Schemas } from "../../api/client";
import { LEVELS, type Level } from "../../components/levels";

type Horizon = 0 | 5 | 15 | 30;
const HORIZONS: { value: Horizon; label: string }[] = [
  { value: 0, label: "Now" },
  { value: 5, label: "+5 min" },
  { value: 15, label: "+15 min" },
  { value: 30, label: "+30 min" },
];

interface Props {
  venue: Schemas["VenueOut"];
  zones: Schemas["ZoneOut"][];
  connections: Schemas["ConnectionOut"][];
  current: Schemas["ZoneNow"][];
  forecasts: Map<number, Schemas["Forecast"][]>;
}

function centroid(points: number[][]): [number, number] {
  const n = points.length || 1;
  const x = points.reduce((s, p) => s + (p[0] ?? 0), 0) / n;
  const y = points.reduce((s, p) => s + (p[1] ?? 0), 0) / n;
  return [x, y];
}

export function VenueMap({ venue, zones, connections, current, forecasts }: Props) {
  const [horizon, setHorizon] = useState<Horizon>(0);
  const now = new Map(current.map((z) => [z.zone_id, z]));
  const allPoints = zones.flatMap((z) => z.polygon);
  const width = venue.plan_width ?? Math.max(...allPoints.map((p) => p[0] ?? 0)) + 20;
  const height = venue.plan_height ?? Math.max(...allPoints.map((p) => p[1] ?? 0)) + 20;
  const centres = new Map(zones.map((z) => [z.zone_id, centroid(z.polygon)]));
  const font = Math.max(14, Math.round(width / 48)); // labels stay readable at any plan size

  function state(zoneId: number): { level: Level | null; count: number | null } {
    if (horizon === 0) {
      const z = now.get(zoneId);
      const stale = z?.staleness_s != null && z.staleness_s > 180;
      return {
        level: stale ? null : ((z?.level ?? null) as Level | null),
        count: z?.occupancy ?? null,
      };
    }
    const f = forecasts.get(zoneId)?.find((x) => x.horizon_min === horizon);
    return { level: (f?.level ?? null) as Level | null, count: f ? Math.round(f.p50) : null };
  }

  return (
    <figure className="rounded-md border border-line bg-surface p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <figcaption className="font-semibold">Venue map</figcaption>
        <div
          role="radiogroup"
          aria-label="Time"
          className="flex rounded border border-line text-xs"
        >
          {HORIZONS.map((h) => (
            <button
              key={h.value}
              type="button"
              role="radio"
              aria-checked={horizon === h.value}
              onClick={() => setHorizon(h.value)}
              className={`px-2.5 py-1 ${horizon === h.value ? "bg-accent text-white" : "text-muted hover:text-ink"}`}
            >
              {h.label}
            </button>
          ))}
        </div>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Venue map, ${horizon === 0 ? "now" : `forecast in ${horizon} minutes`}`}
      >
        <defs>
          <pattern
            id="no-data"
            width="9"
            height="9"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <rect width="9" height="9" fill="var(--surface)" />
            <rect width="4" height="9" fill="var(--unknown)" opacity="0.35" />
          </pattern>
        </defs>

        {connections.map((c) => {
          if (c.from_zone_id == null || c.to_zone_id == null) return null;
          const a = centres.get(c.from_zone_id);
          const b = centres.get(c.to_zone_id);
          if (!a || !b) return null;
          return (
            <line
              key={c.connection_id}
              x1={a[0]}
              y1={a[1]}
              x2={b[0]}
              y2={b[1]}
              stroke="var(--text-muted)"
              strokeWidth={Math.max(1.5, c.boundary_width_m / 2)}
              strokeDasharray={c.bidirectional ? undefined : "6 5"}
              opacity={0.45}
            />
          );
        })}

        {zones.map((z) => {
          const { level, count } = state(z.zone_id);
          const colour = level ? LEVELS[level].colour : "var(--unknown)";
          const [cx, cy] = centres.get(z.zone_id) ?? [0, 0];
          const label = `${z.name}, ${count === null ? "no data" : `${count} of ${z.planning_capacity}`}, ${level ? LEVELS[level].label : "unknown"}`;
          return (
            <g key={z.zone_id} aria-label={label} role="img">
              <title>{label}</title>
              <polygon
                points={z.polygon.map((p) => p.join(",")).join(" ")}
                fill={level ? colour : "url(#no-data)"}
                fillOpacity={level ? 0.3 : 1}
                stroke={colour}
                strokeWidth={2.5}
                strokeLinejoin="round"
              />
              <text
                x={cx}
                y={cy}
                textAnchor="middle"
                dominantBaseline="middle"
                fill="var(--text)"
                fontSize={font}
                fontWeight="600"
              >
                <tspan fill={colour}>{level ? LEVELS[level].shape : "○"}</tspan> {z.code}
              </text>
              {count !== null && (
                <text
                  x={cx}
                  y={cy + font * 1.15}
                  textAnchor="middle"
                  fill="var(--text-muted)"
                  fontSize={Math.round(font * 0.85)}
                >
                  {count}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
