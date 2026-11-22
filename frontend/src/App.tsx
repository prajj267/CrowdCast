import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AlertsPage } from "./features/alerts/AlertsPage";
import { EventPage } from "./features/event/EventPage";
import { LivePage } from "./features/live/LivePage";

import { Shell } from "./routes/Shell";
import { Home } from "./routes/pages";

// Chart pages load on demand so the Live page does not pay for the charting library.
const PredictionsPage = lazy(() =>
  import("./features/predictions/PredictionsPage").then((m) => ({ default: m.PredictionsPage })),
);
const HistoryPage = lazy(() =>
  import("./features/history/HistoryPage").then((m) => ({ default: m.HistoryPage })),
);

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/events/:eventId" element={<Shell />}>
            <Route index element={<Navigate to="live" replace />} />
            <Route path="live" element={<LivePage />} />
            <Route
              path="predictions"
              element={
                <Suspense fallback={<p className="text-muted">Loading…</p>}>
                  <PredictionsPage />
                </Suspense>
              }
            />
            <Route path="alerts" element={<AlertsPage />} />
            <Route
              path="history"
              element={
                <Suspense fallback={<p className="text-muted">Loading…</p>}>
                  <HistoryPage />
                </Suspense>
              }
            />
            <Route path="event" element={<EventPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
