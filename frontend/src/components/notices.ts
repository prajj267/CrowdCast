/**
 * Which forecast notice to show (doc 15 §4), as a pure function so the rules are testable:
 * - the first 15 min of an event: "Forecasts warming up - using persistence";
 * - forecasts issued more than 3 min before the latest counts: the cycle is not keeping up;
 * - every forecast a fallback: no trained model is active.
 */
export const WARMUP_MIN = 15;
export const STALE_MIN = 3;

export type ForecastNotice =
  { kind: "warmup" } | { kind: "stale"; minutes: number } | { kind: "fallback" } | null;

export function forecastNotice(args: {
  eventStart: string | undefined;
  asOf: string | null | undefined; // newest counts (event time)
  issuedAt: string | null | undefined; // newest forecasts (event time)
  allFallback: boolean;
}): ForecastNotice {
  const { eventStart, asOf, issuedAt, allFallback } = args;
  if (!issuedAt) return null; // pages show their own "no forecasts" empty state
  if (eventStart && asOf && Date.parse(asOf) - Date.parse(eventStart) < WARMUP_MIN * 60_000)
    return { kind: "warmup" };
  if (asOf) {
    const lag = (Date.parse(asOf) - Date.parse(issuedAt)) / 60_000;
    if (lag > STALE_MIN) return { kind: "stale", minutes: Math.round(lag) };
  }
  return allFallback ? { kind: "fallback" } : null;
}

export function noticeText(n: Exclude<ForecastNotice, null>): string {
  switch (n.kind) {
    case "warmup":
      return `Forecasts warming up: the first ${WARMUP_MIN} minutes of an event use persistence (the latest count carried forward).`;
    case "stale":
      return `Forecasts are ${n.minutes} min older than the latest counts: the prediction cycle is not keeping up.`;
    case "fallback":
      return "Forecasts use persistence (the latest count carried forward): no trained model is active.";
  }
}
