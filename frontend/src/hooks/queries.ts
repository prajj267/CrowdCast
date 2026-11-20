/**
 * TanStack Query hooks over the typed client. Refresh rates follow doc 15 (Page 4): current
 * state and alerts every 5 s, predictions every 10 s. TanStack pauses interval refetching while
 * the tab is hidden (refetchIntervalInBackground defaults to false).
 */
import { useQuery } from "@tanstack/react-query";
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
