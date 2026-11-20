import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./routes/Shell";
import { Home, NotBuiltYet } from "./routes/pages";

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
            <Route path="live" element={<NotBuiltYet title="Live" task="4.5.4" />} />
            <Route path="predictions" element={<NotBuiltYet title="Predictions" task="8" />} />
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
