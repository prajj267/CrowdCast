/**
 * Zone x horizon table (doc 15 Page 5): P50 with the P10-P90 interval, level, risk score and
 * the fallback flag per cell. Choosing a zone selects it for the chart.
 */
import type { Schemas } from "../../api/client";
import { LevelShape } from "../../components/LevelBadge";
import { LEVELS, type Level } from "../../components/levels";
import { HORIZONS, maxRisk } from "./forecastSeries";

interface Props {
  zones: Schemas["ZoneForecasts"][];
  names: Map<number, string>;
  selected: number | undefined;
  onSelect: (zoneId: number) => void;
}

export function ForecastTable({ zones, names, selected, onSelect }: Props) {
  return (
    <div className="overflow-x-auto rounded-md border border-line bg-surface">
      <table className="w-full text-left">
        <caption className="sr-only">Forecasts per zone and horizon</caption>
        <thead className="border-b border-line text-xs text-muted">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">
              Zone
            </th>
            <th scope="col" className="px-3 py-2 text-right font-medium">
              Now
            </th>
            {HORIZONS.map((h) => (
              <th key={h} scope="col" className="px-3 py-2 font-medium">
                +{h} min <span className="font-normal">P50 (P10–P90)</span>
              </th>
            ))}
            <th scope="col" className="px-3 py-2 text-right font-medium">
              Risk
            </th>
          </tr>
        </thead>
        <tbody>
          {zones.map((z) => {
            const risk = maxRisk(z);
            const isSel = z.zone_id === selected;
            return (
              <tr
                key={z.zone_id}
                aria-selected={isSel}
                className={`border-b border-line last:border-0 ${isSel ? "bg-bg" : ""}`}
              >
                <th scope="row" className="px-3 py-2 font-normal">
                  <button
                    type="button"
                    onClick={() => onSelect(z.zone_id)}
                    aria-pressed={isSel}
                    className={`text-left hover:text-accent ${isSel ? "font-semibold" : ""}`}
                  >
                    {names.get(z.zone_id) ?? z.code}{" "}
                    <span className="text-xs text-muted">{z.code}</span>
                  </button>
                </th>
                <td className="px-3 py-2 text-right">
                  {z.current.occupancy ?? <span className="text-muted">—</span>}
                </td>
                {HORIZONS.map((h) => {
                  const f = z.forecasts.find((x) => x.horizon_min === h);
                  if (!f)
                    return (
                      <td key={h} className="px-3 py-2 text-muted">
                        —
                      </td>
                    );
                  const lvl = f.level as Level;
                  return (
                    <td key={h} className="px-3 py-2">
                      <span className="inline-flex items-center gap-1.5">
                        <LevelShape level={lvl} />
                        <span className="sr-only">{LEVELS[lvl].label}:</span>
                        <span className="font-medium">{Math.round(f.p50)}</span>
                        <span className="text-xs text-muted">
                          ({Math.round(f.p10)}–{Math.round(f.p90)})
                        </span>
                      </span>
                      {f.is_fallback && (
                        <span className="block text-xs text-muted">Persistence fallback</span>
                      )}
                    </td>
                  );
                })}
                <td className="px-3 py-2 text-right">{risk === null ? "—" : risk.toFixed(2)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
