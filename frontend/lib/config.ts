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
/** Models one experiment can compare, and total runs across them (mirrors MAX_TOTAL_RUNS). */
export const MAX_MODELS = 4;
export const MAX_TOTAL_RUNS = 20;
/** Past-bug replay: bugs per experiment (mirrors MAX_REPLAY_CASES) and runs per bug per model. */
export const MAX_REPLAY_CASES = 6;
export const REPLAY_RUN_OPTIONS = [1, 2, 3, 5] as const;
export const DEFAULT_REPLAY_RUNS = 2;
