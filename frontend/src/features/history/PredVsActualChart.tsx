/**
 * Predicted vs actual for one zone and horizon (doc 15 Page 6): what happened (observed
 * occupancy at the target time) against the forecast issued h minutes earlier, with its
 * P10-P90 band. Single series pair, so the identity is in the caption, not a legend box.
 */
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { hhmm } from "./historyData";

type Row = { t: number; actual?: number; p50: number; band: [number, number] };

function TooltipBody({
  active,
  payload,
}: {
  active?: boolean;
  payload?: readonly { payload?: Row }[];
}) {
  const r = payload?.[0]?.payload;
  if (!active || !r) return null;
  return (
    <div className="rounded border border-line bg-surface px-2 py-1 text-xs shadow">
      <p className="font-medium">{hhmm(r.t)}</p>
      <p>Actual {r.actual === undefined ? "—" : Math.round(r.actual)}</p>
      <p>
        Forecast {Math.round(r.p50)}{" "}
        <span className="text-muted">
          ({Math.round(r.band[0])}–{Math.round(r.band[1])})
        </span>
      </p>
    </div>
  );
}

export function PredVsActualChart({ rows, horizon }: { rows: Row[]; horizon: number }) {
  if (rows.length === 0)
    return <p className="text-muted">No forecasts at this horizon for this zone.</p>;
  const first = rows[0]?.t ?? 0;
  const end = rows[rows.length - 1]?.t ?? 0;
  const step = end - first > 4 * 3_600_000 ? 3_600_000 : 1_800_000;
  const ticks: number[] = [];
  for (let t = Math.ceil(first / step) * step; t <= end; t += step) ticks.push(t);
  return (
    <figure aria-label={`Forecast ${horizon} min ahead against what happened`} className="w-full">
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={[first, end]}
              ticks={ticks}
              tickFormatter={hhmm}
              stroke="var(--text-muted)"
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            />
            <YAxis
              allowDecimals={false}
              width={48}
              stroke="var(--text-muted)"
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            />
            <Area
              dataKey="band"
              stroke="none"
              fill="var(--accent)"
              fillOpacity={0.18}
              isAnimationActive={false}
            />
            <Line
              dataKey="p50"
              stroke="var(--accent)"
              strokeWidth={2}
              strokeDasharray="6 3"
              dot={false}
              isAnimationActive={false}
            />
            <Line
              dataKey="actual"
              stroke="var(--text)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Tooltip content={<TooltipBody />} cursor={{ stroke: "var(--text-muted)" }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 flex flex-wrap gap-x-4 text-xs text-muted">
        <span>
          <span aria-hidden="true">━</span> actual
        </span>
        <span>
          <span aria-hidden="true" className="text-accent">
            ╌
          </span>{" "}
          forecast median, issued {horizon} min earlier
        </span>
        <span>
          <span aria-hidden="true" className="text-accent">
            ▇
          </span>{" "}
          P10–P90
        </span>
      </figcaption>
    </figure>
  );
}
