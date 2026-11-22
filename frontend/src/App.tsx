import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { LivePage } from "./features/live/LivePage";

import { Shell } from "./routes/Shell";
import { Home, NotBuiltYet } from "./routes/pages";

// Chart pages load on demand so the Live page does not pay for the charting library.
const PredictionsPage = lazy(() =>
  import("./features/predictions/PredictionsPage").then((m) => ({ default: m.PredictionsPage })),
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
            <Route path="alerts" element={<NotBuiltYet title="Alerts" task="8" />} />
            <Route path="history" element={<NotBuiltYet title="History" task="8" />} />
            <Route path="event" element={<NotBuiltYet title="Event & venue" task="8" />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
