/**
 * ForecastChart (doc 15 §2.3): observed occupancy of the last 60 min, the forecast fan to +30
 * min (P50 line, shaded P10-P90 band), threshold lines, a "now" marker and schedule bands.
 * Level colours mark the threshold lines only; text stays in the text colours (doc 15 §2.1).
 */
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { LEVELS } from "../../components/levels";
import { type Band, type ChartPoint, hhmm } from "./forecastSeries";

interface Props {
  data: ChartPoint[];
  now: number;
  from: number;
  to: number;
  capacity: number;
  thresholds: { level: "ELEVATED" | "HIGH" | "CRITICAL"; y: number }[];
  bands: Band[];
  zoneName: string;
}

function TooltipBody({
  active,
  payload,
}: {
  active?: boolean;
  payload?: readonly { payload?: ChartPoint }[];
}) {
  const p = payload?.[0]?.payload;
  if (!active || !p) return null;
  return (
    <div className="rounded border border-line bg-surface px-2 py-1 text-xs shadow">
      <p className="font-medium">{hhmm(p.t)}</p>
      {p.observed !== undefined && <p>Observed {Math.round(p.observed)}</p>}
      {p.p50 !== undefined && p.band && p.band[0] !== p.band[1] && (
        <p>
          Forecast {Math.round(p.p50)}{" "}
          <span className="text-muted">
            (P10–P90 {Math.round(p.band[0])}–{Math.round(p.band[1])})
          </span>
        </p>
      )}
    </div>
  );
}

export function ForecastChart({
  data,
  now,
  from,
  to,
  capacity,
  thresholds,
  bands,
  zoneName,
}: Props) {
  const top = Math.max(
    capacity * 1.05,
    ...thresholds.map((t) => t.y * 1.05),
    ...data.map((d) => Math.max(d.observed ?? 0, d.band?.[1] ?? 0)),
  );
  const ticks: number[] = [];
  for (let t = Math.ceil(from / 900_000) * 900_000; t <= to; t += 900_000) ticks.push(t);

  return (
    <figure aria-label={`Occupancy and forecast for ${zoneName}`} className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 20, right: 76, bottom: 0, left: 0 }}>
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
            domain={[0, Math.ceil(top / 50) * 50]}
            allowDecimals={false}
            width={48}
            stroke="var(--text-muted)"
            tick={{ fill: "var(--text-muted)", fontSize: 12 }}
          />
          {bands.map((b) => (
            <ReferenceArea
              key={`${b.title}-${b.from}`}
              x1={b.from}
              x2={b.to}
              fill="var(--accent)"
              fillOpacity={0.07}
              label={{
                value: b.title,
                position: "insideTopLeft",
                fill: "var(--text-muted)",
                fontSize: 11,
              }}
            />
          ))}
          {thresholds.map((t) => (
            <ReferenceLine
              key={t.level}
              y={t.y}
              stroke={LEVELS[t.level].colour}
              strokeDasharray="4 4"
              label={{
                value: `${LEVELS[t.level].shape} ${LEVELS[t.level].label}`,
                position: "right",
                fill: "var(--text-muted)",
                fontSize: 11,
              }}
            />
          ))}
          <Area
            dataKey="band"
            stroke="none"
            fill="var(--accent)"
            fillOpacity={0.18}
            isAnimationActive={false}
            connectNulls
            name="P10–P90"
          />
          <Line
            dataKey="observed"
            stroke="var(--text)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            name="Observed"
          />
          <Line
            dataKey="p50"
            stroke="var(--accent)"
            strokeWidth={2}
            strokeDasharray="6 3"
            dot={{ r: 3, fill: "var(--accent)" }}
            isAnimationActive={false}
            connectNulls
            name="Forecast P50"
          />
          <ReferenceLine
            x={now}
            stroke="var(--text-muted)"
            label={{ value: "now", position: "top", fill: "var(--text-muted)", fontSize: 11 }}
          />
          <Tooltip content={<TooltipBody />} />
        </ComposedChart>
      </ResponsiveContainer>
      <figcaption className="mt-1 flex flex-wrap gap-x-4 text-xs text-muted">
        <span>
          <span aria-hidden="true">━</span> observed
        </span>
        <span>
          <span aria-hidden="true" className="text-accent">
            ╌
          </span>{" "}
          forecast median (P50)
        </span>
        <span>
          <span aria-hidden="true" className="text-accent">
            ▇
          </span>{" "}
          80 % interval (P10–P90)
        </span>
        <span>shaded columns: schedule items</span>
      </figcaption>
    </figure>
  );
}
