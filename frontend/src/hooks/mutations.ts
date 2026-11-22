/**
 * Operator actions on alerts (doc 14 §3.13): acknowledge / resolve with an optional note.
 * Optimistic (doc 17 TC-FE-05): every cached alert list of the event shows the new status at
 * once; if the API refuses (e.g. 409 already resolved) the previous lists are put back. Both
 * pages that show alerts use this hook.
 */
import { type QueryClient, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Schemas, unwrap } from "../api/client";

export type AlertAction = "acknowledge" | "resolve";
type AlertList = Schemas["AlertList"];
type Paged = { pages: AlertList[]; pageParams: unknown[] };

function patchList(list: AlertList, id: number, action: AlertAction): AlertList {
  return {
    ...list,
    alerts: list.alerts.map((a) =>
      a.alert_id !== id
        ? a
        : action === "acknowledge"
          ? { ...a, status: "ACKNOWLEDGED" }
          : { ...a, status: "RESOLVED", auto_resolved: false },
    ),
  };
}

/** Apply the action to a cached value of either shape (plain list or paged list). */
export function patchAlertData(data: unknown, id: number, action: AlertAction): unknown {
  if (!data || typeof data !== "object") return data;
  if ("pages" in data) {
    const paged = data as Paged;
    return { ...paged, pages: paged.pages.map((p) => patchList(p, id, action)) };
  }
  if ("alerts" in data) return patchList(data as AlertList, id, action);
  return data;
}

export function alertActionOptions(qc: QueryClient, eventId: number) {
  const key = ["alerts", eventId]; // prefix: the Live list and every filtered Alerts query
  return {
    mutationFn: async ({ id, action, note }: { id: number; action: AlertAction; note?: string }) =>
      unwrap(
        await api.POST(`/api/alerts/{alert_id}/${action}`, {
          params: { path: { alert_id: id } },
          body: note ? { note } : {},
        }),
      ),
    onMutate: async ({ id, action }: { id: number; action: AlertAction }) => {
      await qc.cancelQueries({ queryKey: key });
      const previous = qc.getQueriesData({ queryKey: key });
      qc.setQueriesData({ queryKey: key }, (d: unknown) => patchAlertData(d, id, action));
      return { previous };
    },
    onError: (
      _e: Error,
      _v: unknown,
      ctx: { previous: [readonly unknown[], unknown][] } | undefined,
    ) => {
      for (const [k, d] of ctx?.previous ?? []) qc.setQueryData(k, d);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  };
}

export function useAlertAction(eventId: number) {
  const qc = useQueryClient();
  return useMutation(alertActionOptions(qc, eventId));
}
