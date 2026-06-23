// Thin REST client. The browser persists only the session id; the whole model
// is synced back to the backend (which owns it).

import type {
  HazardCatalog,
  Libraries,
  MeasureSpec,
  Portfolio,
  Run,
  TransitionResult,
} from "../types";

const SESSION_KEY = "climaterisk.sessionId";

async function http<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    throw new Error(`${init?.method ?? "GET"} ${url} → ${resp.status}`);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

/** Fetch the existing session (from localStorage) or create a fresh one. */
export async function ensureSession(): Promise<Portfolio> {
  const existing = localStorage.getItem(SESSION_KEY);
  if (existing) {
    try {
      return await http<Portfolio>(`/api/session/${existing}`);
    } catch {
      localStorage.removeItem(SESSION_KEY); // stale id (e.g. backend cleared)
    }
  }
  const created = await http<Portfolio>("/api/session", { method: "POST" });
  localStorage.setItem(SESSION_KEY, created.id);
  return created;
}

/** Persist the whole portfolio model (full-model sync). */
export async function saveModel(model: Portfolio): Promise<Portfolio> {
  return http<Portfolio>(`/api/session/${model.id}`, {
    method: "PUT",
    body: JSON.stringify(model),
  });
}

export async function getLibraries(): Promise<Libraries> {
  return http<Libraries>("/api/libraries");
}

export async function getHazardCatalog(): Promise<HazardCatalog> {
  return http<HazardCatalog>("/api/hazard-catalog");
}

export async function submitRun(sessionId: string): Promise<Run> {
  return http<Run>(`/api/session/${sessionId}/run`, { method: "POST" });
}

export async function getRun(sessionId: string, runId: string): Promise<Run> {
  return http<Run>(`/api/session/${sessionId}/run/${runId}`);
}

export async function submitTransition(sessionId: string): Promise<TransitionResult> {
  return http<TransitionResult>(`/api/session/${sessionId}/transition`, { method: "POST" });
}

export async function submitCostBenefit(sessionId: string, measures: MeasureSpec[]): Promise<Run> {
  return http<Run>(`/api/session/${sessionId}/cost-benefit`, {
    method: "POST",
    body: JSON.stringify(measures),
  });
}

export async function submitUncertainty(sessionId: string, nSamples = 50): Promise<Run> {
  return http<Run>(`/api/session/${sessionId}/uncertainty?n_samples=${nSamples}`, {
    method: "POST",
  });
}

export async function submitLitPop(sessionId: string, country: string): Promise<Run> {
  return http<Run>(`/api/session/${sessionId}/litpop?country=${encodeURIComponent(country)}`, {
    method: "POST",
  });
}

export async function submitSupplyChain(
  sessionId: string,
  mriotType = "WIOD16",
  mriotYear = 2010,
): Promise<Run> {
  return http<Run>(
    `/api/session/${sessionId}/supplychain?mriot_type=${mriotType}&mriot_year=${mriotYear}`,
    { method: "POST" },
  );
}

export interface IngestBody {
  source: "dataapi" | "aqueduct";
  peril?: string;
  scenario?: string;
  year?: number;
}

export async function submitIngest(sessionId: string, body: IngestBody): Promise<Run> {
  return http<Run>(`/api/session/${sessionId}/ingest`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
