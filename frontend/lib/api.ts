/**
 * Every call to the orchestrator lives in this file.
 *
 * Components depend on the `TraceApi` interface, never on fetch/URLs directly.
 * With NEXT_PUBLIC_USE_MOCK=true the in-browser mock backend implements the same
 * interface, so the UI can be developed and demoed without the orchestrator.
 */
import { config } from "./config";
import { ApiError } from "./errors";
import { mockBackend } from "./mock/backend";
import type {
  Agent,
  CreatedExperiment,
  CreateExperimentRequest,
  Experiment,
  ExperimentSummary,
  Health,
  OverviewStats,
  ScanResult,
} from "./types";

export interface TraceApi {
  health(): Promise<Health>;
  listAgents(): Promise<Agent[]>;
  listExperiments(): Promise<ExperimentSummary[]>;
  getExperiment(id: string): Promise<Experiment>;
  createExperiment(req: CreateExperimentRequest): Promise<CreatedExperiment>;
  /** Stop / delete need the owner token handed out at creation (lib/owner.ts). */
  cancelExperiment(id: string, ownerToken: string): Promise<void>;
  deleteExperiment(id: string, ownerToken: string): Promise<void>;
  getOverview(): Promise<OverviewStats>;
  /** Past bug fixes in the repo's history (replay mode). */
  scanRepo(repo: string): Promise<ScanResult>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${config.apiUrl}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Orchestrator unreachable");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const httpApi: TraceApi = {
  health: () => request("/health"),
  listAgents: () => request("/agents"),
  listExperiments: () => request("/experiments"),
  getExperiment: (id) => request(`/experiments/${encodeURIComponent(id)}`),
  createExperiment: (req) => request("/experiments", { method: "POST", body: JSON.stringify(req) }),
  cancelExperiment: (id, ownerToken) =>
    request(`/experiments/${encodeURIComponent(id)}/cancel`, {
      method: "POST",
      headers: { "X-Owner-Token": ownerToken },
    }),
  deleteExperiment: (id, ownerToken) =>
    request(`/experiments/${encodeURIComponent(id)}`, { method: "DELETE", headers: { "X-Owner-Token": ownerToken } }),
  getOverview: () => request("/stats/overview"),
  scanRepo: (repo) => request("/replay/scan", { method: "POST", body: JSON.stringify({ repo }) }),
};

export const api: TraceApi = config.useMock ? mockBackend : httpApi;

/** URL of the SSE stream for an experiment (used by lib/sse.ts). */
export function liveUrl(id: string): string {
  return `${config.apiUrl}/live/${encodeURIComponent(id)}`;
}
