/**
 * ZoneCard (doc 15 §2.3): occupancy / capacity, ratio bar with the zone's thresholds, level,
 * predicted levels at +5/+15/+30, flows and staleness (doc 15 §4).
 */
import type { Schemas } from "../../api/client";
import { LevelBadge, LevelShape } from "../../components/LevelBadge";
import { LEVELS, type Level } from "../../components/levels";

const STALE_S = 180; // doc 14 §3.9: grey out data older than 3 min

interface Props {
  zone: Schemas["ZoneNow"];
  thresholds: Schemas["ThresholdsOut"] | undefined;
  forecasts: Schemas["Forecast"][];
  /** false when the page already says that every forecast is a fallback */
  showFallback?: boolean;
}

export function ZoneCard({ zone, thresholds, forecasts, showFallback = true }: Props) {
  const level = (zone.level ?? null) as Level | null;
  const stale = zone.staleness_s !== null && zone.staleness_s > STALE_S;
  const noData = zone.occupancy === null;
  const ratio = zone.occupancy_ratio ?? 0;
  const barMax = Math.max(1.2, ratio); // leave room above capacity
  const edge = noData || stale ? "var(--unknown)" : level ? LEVELS[level].colour : "var(--unknown)";
  const fallback = showFallback && forecasts.some((f) => f.is_fallback);

  return (
    <article
      aria-label={`${zone.name}, ${noData ? "no data" : `${zone.occupancy} of ${zone.capacity}`}, ${level ? LEVELS[level].label : "unknown level"}`}
      className={`rounded-md border border-line bg-surface p-4 ${noData || stale ? "hatch-unknown" : ""}`}
      style={{ boxShadow: `inset 4px 0 0 ${edge}` }}
    >
      <header className="flex items-baseline justify-between gap-2">
        <h2 className="truncate font-medium">{zone.name}</h2>
        <span className="text-xs text-muted">{zone.code}</span>
      </header>

      <p className="mt-2 flex items-baseline gap-1.5">
        <span className="text-2xl font-semibold">{noData ? "—" : zone.occupancy}</span>
        <span className="text-muted">/ {zone.capacity}</span>
        {!noData && (
          <span className="ml-auto text-muted">{Math.round(ratio * 100)}% of capacity</span>
        )}
      </p>

      <div className="relative mt-2 h-2 rounded-full bg-line" aria-hidden="true">
        <div
          className="h-2 rounded-full"
          style={{ width: `${Math.min(100, (ratio / barMax) * 100)}%`, background: edge }}
        />
        {thresholds &&
          [thresholds.elevated, thresholds.high, thresholds.critical].map((t) => (
            <span
              key={t}
              className="absolute -top-0.5 h-3 w-px bg-ink/40"
              style={{ left: `${(t / barMax) * 100}%` }}
            />
          ))}
      </div>

      <div className="mt-3 flex items-center justify-between gap-2">
        <LevelBadge level={noData ? null : level} />
        <ol className="flex items-center gap-2 text-xs text-muted" aria-label="Forecast levels">
          {[5, 15, 30].map((h) => {
            const f = forecasts.find((x) => x.horizon_min === h);
            return (
              <li
                key={h}
                className="flex items-center gap-1"
                title={f ? `${Math.round(f.p50)} people` : "no forecast"}
              >
                <span>+{h}</span>
                <LevelShape level={(f?.level ?? null) as Level | null} size={11} />
              </li>
            );
          })}
        </ol>
      </div>

      <footer className="mt-2 flex flex-wrap gap-x-3 text-xs text-muted">
        <span>
          In {zone.inflow ?? "—"} · out {zone.outflow ?? "—"} /min
        </span>
        {stale && (
          <span className="text-ink">Stale ({Math.round((zone.staleness_s ?? 0) / 60)} min)</span>
        )}
        {noData && <span className="text-ink">No data</span>}
        {zone.quality === "LOW_CONFIDENCE" && (
          <span className="text-ink">Dense scene: count may be low</span>
        )}
        {fallback && <span>Persistence fallback</span>}
      </footer>
    </article>
  );
}
