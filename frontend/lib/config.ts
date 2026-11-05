/**
 * Runtime configuration. NEXT_PUBLIC_* values are inlined at build time.
 *
 * apiUrl defaults to "/api": the browser talks to its own origin and the
 * request is proxied to the orchestrator (next.config rewrites in dev,
 * the reverse proxy on the Vultr VM in production). No CORS, no hardcoded hosts.
 */
export const config = {
  apiUrl: (process.env.NEXT_PUBLIC_API_URL || "/api").replace(/\/$/, ""),
  useMock: process.env.NEXT_PUBLIC_USE_MOCK === "true",
} as const;

/** Run counts offered in the experiment form. */
export const RUN_COUNT_OPTIONS = [3, 5, 8, 10] as const;
export const DEFAULT_RUN_COUNT = 5;
