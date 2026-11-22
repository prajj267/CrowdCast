/**
 * Occupancy vs time for up to 4 zones (doc 15 Page 6): occupancy as % of planning capacity
 * (one axis for zones of different size), schedule bands, the HIGH threshold when the chosen
 * zones share it, a crosshair tooltip, a legend and direct labels at the line ends.
 */
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { type ZoneMeta, hhmm } from "./historyData";

const SLOT = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)"];

interface Props {
  rows: Record<string, number>[];
  zones: ZoneMeta[]; // selected, in legend order
  slots: Map<number, number>;
  from: number;
  to: number;
  bands: { from: number; to: number; title: string }[];
}

function PeakLabel(props: {
  x?: number | string;
  y?: number | string;
  index?: number;
  last: number;
  text: string;
  colour: string;
}) {
  const { x, y, index, last, text, colour } = props;
  if (index !== last || x === undefined || y === undefined) return null;
  return (
    <g>
      <circle
        cx={Number(x)}
        cy={Number(y)}
        r={4}
        fill={colour}
        stroke="var(--surface)"
        strokeWidth={2}
      />
      <text x={Number(x)} y={Number(y) - 8} textAnchor="middle" fontSize={11} fill="var(--text)">
        {text}
      </text>
    </g>
  );
}

function TooltipBody(props: {
  active?: boolean;
  label?: number | string;
  payload?: readonly { dataKey?: unknown; value?: unknown; color?: string }[];
  zones: ZoneMeta[];
}) {
  const { active, label, payload, zones } = props;
  if (!active || !payload?.length) return null;
  const rows = payload
    .map((p) => ({
      z: zones.find((z) => String(z.zone_id) === String(p.dataKey)),
      v: p.value,
      c: p.color,
    }))
    .filter((r) => r.z && typeof r.v === "number")
    .sort((a, b) => (b.v as number) - (a.v as number));
  return (
    <div className="rounded border border-line bg-surface px-2 py-1 text-xs shadow">
      <p className="font-medium">{hhmm(Number(label))}</p>
      {rows.map((r) => (
        <p key={r.z?.zone_id} className="flex items-center gap-1.5">
          <span aria-hidden="true" style={{ color: r.c }}>
            ━
          </span>
          {r.z?.name} {Math.round((r.v as number) * 100)} %
        </p>
      ))}
    </div>
  );
}

export function OccupancyChart({ rows, zones, slots, from, to, bands }: Props) {
  const highs = new Set(zones.map((z) => z.high));
  const sharedHigh = highs.size === 1 ? [...highs][0] : undefined;
  const top = Math.max(1, ...rows.flatMap((r) => zones.map((z) => r[String(z.zone_id)] ?? 0)));
  const ticks: number[] = [];
  const step = to - from > 4 * 3_600_000 ? 3_600_000 : 1_800_000;
  for (let t = Math.ceil(from / step) * step; t <= to; t += step) ticks.push(t);
  // direct label at each zone's peak (line ends all meet near 0 when the venue empties)
  const peakIndex = (id: number) => {
    let best = -1;
    rows.forEach((r, i) => {
      const v = r[String(id)];
      if (v !== undefined && (best < 0 || v > (rows[best]?.[String(id)] ?? -1))) best = i;
    });
    return best;
  };
  const yTop = Math.ceil(top * 5) / 5;
  const yTicks = Array.from({ length: Math.round(yTop / 0.2) + 1 }, (_, i) => i * 0.2);

  return (
    <figure aria-label="Occupancy over the event, percent of capacity" className="w-full">
      <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs" aria-label="Legend">
        {zones.map((z) => (
          <li key={z.zone_id} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block h-0.5 w-4 rounded"
              style={{ background: SLOT[slots.get(z.zone_id) ?? 0] }}
            />
            {z.name} ({z.code})
          </li>
        ))}
      </ul>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 48, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={[from, to]}
              ticks={ticks}
              tickFormatter={hhmm}
              stroke="var(--text-muted)"
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            />
            <YAxis
              domain={[0, yTop]}
              ticks={yTicks}
              tickFormatter={(v: number) => `${Math.round(v * 100)} %`}
              width={52}
              stroke="var(--text-muted)"
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            />
            {bands.map((b) => (
              <ReferenceArea
                key={`${b.title}-${b.from}`}
                x1={b.from}
                x2={b.to}
                fill="var(--accent)"
                fillOpacity={0.04}
              />
            ))}
            {sharedHigh !== undefined && (
              <ReferenceLine
                y={sharedHigh}
                stroke="var(--lvl-high)"
                strokeDasharray="4 4"
                label={{
                  value: "◆ High",
                  position: "insideTopRight",
                  fill: "var(--text-muted)",
                  fontSize: 11,
                }}
              />
            )}
            {zones.map((z) => {
              const colour = SLOT[slots.get(z.zone_id) ?? 0] ?? "var(--series-1)";
              const last = peakIndex(z.zone_id);
              return (
                <Line
                  key={z.zone_id}
                  dataKey={String(z.zone_id)}
                  stroke={colour}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                  isAnimationActive={false}
                  label={(p: { x?: number | string; y?: number | string; index?: number }) => (
                    <PeakLabel {...p} last={last} text={z.code} colour={colour} />
                  )}
                />
              );
            })}
            <Tooltip
              content={(p) => <TooltipBody {...p} zones={zones} />}
              cursor={{ stroke: "var(--text-muted)" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-muted">
        Shaded columns: schedule items of the chosen zones. Times are event time (UTC).
      </figcaption>
    </figure>
  );
}
