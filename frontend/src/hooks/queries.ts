/**
 * TanStack Query hooks over the typed client. Refresh rates follow doc 15 (Page 4): current
 * state and alerts every 5 s, predictions every 10 s. TanStack pauses interval refetching while
 * the tab is hidden (refetchIntervalInBackground defaults to false).
 */
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../api/client";

export function useEvents() {
  return useQuery({
    queryKey: ["events"],
    queryFn: async () =>
      unwrap(await api.GET("/api/events", { params: { query: { limit: 100 } } })),
    staleTime: 60_000,
  });
}

export function useEvent(eventId: number) {
  return useQuery({
    queryKey: ["event", eventId],
    queryFn: async () =>
      unwrap(await api.GET("/api/events/{event_id}", { params: { path: { event_id: eventId } } })),
    refetchInterval: 30_000,
  });
}

export function useCurrent(eventId: number) {
  return useQuery({
    queryKey: ["current", eventId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/crowd/current/{event_id}", { params: { path: { event_id: eventId } } }),
      ),
    refetchInterval: 5_000,
  });
}

export function usePredictions(eventId: number) {
  return useQuery({
    queryKey: ["predictions", eventId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/predictions/{event_id}", { params: { path: { event_id: eventId } } }),
      ),
    refetchInterval: 10_000,
  });
}

export function useAlerts(eventId: number) {
  return useQuery({
    queryKey: ["alerts", eventId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/alerts/{event_id}", {
          params: { path: { event_id: eventId }, query: { limit: 200 } },
        }),
      ),
    refetchInterval: 5_000,
  });
}

/** Observed occupancy and flows of some zones between two event times (1-min buckets). */
export function useHistory(
  eventId: number,
  zoneIds: number[],
  from: string | undefined,
  to: string | undefined,
  resolution: "1m" | "5m" = "1m",
) {
  return useQuery({
    queryKey: ["history", eventId, zoneIds, from, to, resolution],
    enabled: zoneIds.length > 0 && from !== undefined && to !== undefined,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/crowd/history/{event_id}", {
          params: {
            path: { event_id: eventId },
            query: { zone_id: zoneIds, from, to, resolution },
          },
        }),
      ),
    placeholderData: (previous) => previous, // keep the chart while the window slides
  });
}

/** Issued forecasts of one zone and horizon joined with what happened (doc 14 §3.11). */
export function useZoneTimeline(eventId: number, zoneId: number | undefined, horizon: number) {
  return useQuery({
    queryKey: ["timeline", eventId, zoneId, horizon],
    enabled: zoneId !== undefined,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/predictions/{event_id}/zones/{zone_id}", {
          params: {
            path: { event_id: eventId, zone_id: zoneId as number },
            query: { horizon_min: [horizon] },
          },
        }),
      ),
    refetchInterval: 30_000,
  });
}

export function useGraphValidation(venueId: number | undefined) {
  return useQuery({
    queryKey: ["graph-validation", venueId],
    enabled: venueId !== undefined,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/venues/{venue_id}/graph/validate", {
          params: { path: { venue_id: venueId as number } },
        }),
      ),
    staleTime: 5 * 60_000,
  });
}

export function useSchedule(eventId: number) {
  return useQuery({
    queryKey: ["schedule", eventId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/events/{event_id}/schedule", {
          params: { path: { event_id: eventId } },
        }),
      ),
    staleTime: 5 * 60_000,
  });
}

export interface AlertFilters {
  status: ("OPEN" | "ACKNOWLEDGED" | "RESOLVED")[];
  level: "ELEVATED" | "HIGH" | "CRITICAL" | null;
  zoneId: number | null;
}

/** Filtered alert history, newest first, paged with the API cursor ("Load more"). */
export function useAlertHistory(eventId: number, f: AlertFilters) {
  return useInfiniteQuery({
    queryKey: ["alerts", eventId, f],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/alerts/{event_id}", {
          params: {
            path: { event_id: eventId },
            query: {
              status: f.status.length ? f.status : null,
              level: f.level,
              zone_id: f.zoneId,
              limit: 100,
              cursor: pageParam,
            },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor,
    refetchInterval: 5_000,
  });
}

export function useZones(venueId: number | undefined) {
  return useQuery({
    queryKey: ["zones", venueId],
    enabled: venueId !== undefined,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/venues/{venue_id}/zones", {
          params: { path: { venue_id: venueId as number } },
        }),
      ),
    staleTime: 5 * 60_000,
  });
}

export function useVenue(venueId: number | undefined) {
  return useQuery({
    queryKey: ["venue", venueId],
    enabled: venueId !== undefined,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/venues/{venue_id}", {
          params: { path: { venue_id: venueId as number } },
        }),
      ),
    staleTime: 5 * 60_000,
  });
}

export function useConnections(venueId: number | undefined) {
  return useQuery({
    queryKey: ["connections", venueId],
    enabled: venueId !== undefined,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/venues/{venue_id}/connections", {
          params: { path: { venue_id: venueId as number } },
        }),
      ),
    staleTime: 5 * 60_000,
  });
}
