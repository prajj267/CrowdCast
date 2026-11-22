/**
 * Standard states for every data view (doc 15 §2.3 EmptyState / ErrorState, §4): one look for
 * "loading", "nothing yet" and "could not load", and a status notice for banners that must be
 * announced to screen readers without stealing focus.
 */
import type { ReactNode } from "react";

export function Loading({ what }: { what: string }) {
  return (
    <p role="status" className="text-muted">
      Loading {what}…
    </p>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <section className="rounded-md border border-dashed border-line bg-surface p-6">
      <h2 className="font-semibold">{title}</h2>
      {children && <div className="mt-1 text-muted">{children}</div>}
    </section>
  );
}

export function ErrorState({ children }: { children: ReactNode }) {
  return (
    <section role="alert" className="rounded-md border border-line bg-surface p-6">
      <h2 className="font-semibold">Could not load this view</h2>
      <div className="mt-1 text-muted">{children}</div>
    </section>
  );
}

/** A banner line; ``tone="warn"`` adds the hatched "attention" edge used for stale data. */
export function Notice({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: "info" | "warn";
}) {
  return (
    <p
      role="status"
      className={`rounded-md border border-line bg-surface px-3 py-2 ${tone === "warn" ? "shadow-[inset_4px_0_0_var(--unknown)]" : ""}`}
    >
      {children}
    </p>
  );
}

export function ApiHint() {
  return (
    <>
      Check that the API is running: <code>uv run uvicorn crowdcast.api.app:app</code> in{" "}
      <code>backend/</code>.
    </>
  );
}
