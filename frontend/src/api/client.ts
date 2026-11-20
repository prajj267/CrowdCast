/**
 * Typed API client (WORKFLOW 4.5.2).
 *
 * Types come from the backend's OpenAPI schema: run `npm run gen:api` after any API change
 * (it re-exports openapi.json from FastAPI and regenerates schema.ts). In development the Vite
 * server proxies /api to the backend, so the base URL is the page's own origin.
 */
import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export const api = createClient<paths>({ baseUrl: "" });

export type Schemas = components["schemas"];

/** Error envelope of doc 14 §1.1. */
export interface ErrorBody {
  error: {
    code: string;
    message: string;
    details: { field: string; issue: string }[];
    request_id: string;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | undefined;

  constructor(status: number, body: unknown) {
    const err = (body as Partial<ErrorBody> | undefined)?.error;
    super(err?.message ?? `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.code = err?.code ?? "UNKNOWN";
    this.requestId = err?.request_id;
  }
}

/** Return the data of an openapi-fetch result, or throw an ApiError carrying the envelope. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined) {
    throw new ApiError(result.response.status, result.error);
  }
  return result.data;
}
