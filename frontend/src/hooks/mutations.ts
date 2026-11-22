/**
 * Operator actions on alerts (doc 14 §3.13): acknowledge / resolve with an optional note. Both
 * pages that show alerts use this hook, so every alert query of the event refreshes afterwards.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "../api/client";

export type AlertAction = "acknowledge" | "resolve";

export function useAlertAction(eventId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, action, note }: { id: number; action: AlertAction; note?: string }) =>
      unwrap(
        await api.POST(`/api/alerts/{alert_id}/${action}`, {
          params: { path: { alert_id: id } },
          body: note ? { note } : {},
        }),
      ),
    // prefix match: the Live list and every filtered Alerts-page query
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts", eventId] }),
  });
}
