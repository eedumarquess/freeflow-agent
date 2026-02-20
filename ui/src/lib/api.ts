import type { Gate, RunData, RunGraph, RunMetrics } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // fallback to default message
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function listRuns(): Promise<RunData[]> {
  const response = await fetch(`${API_BASE}/runs`);
  return parseResponse<RunData[]>(response);
}

export async function getRun(runId: string): Promise<RunData> {
  const response = await fetch(`${API_BASE}/runs/${runId}`);
  return parseResponse<RunData>(response);
}

export async function getRunGraph(runId: string): Promise<RunGraph> {
  const response = await fetch(`${API_BASE}/runs/${runId}/graph`);
  return parseResponse<RunGraph>(response);
}

export async function getRunMetrics(runId: string): Promise<RunMetrics> {
  const response = await fetch(`${API_BASE}/runs/${runId}/metrics`);
  return parseResponse<RunMetrics>(response);
}

export async function decideGate(
  runId: string,
  gate: Gate,
  approved: boolean,
  note: string,
): Promise<{ run: RunData; decision: "approved" | "rejected"; note?: string }> {
  const response = await fetch(`${API_BASE}/runs/${runId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ gate, approved, note }),
  });
  return parseResponse<{ run: RunData; decision: "approved" | "rejected"; note?: string }>(response);
}

export async function getArtifact(runId: string, name: string): Promise<string> {
  const response = await fetch(`${API_BASE}/runs/${runId}/artifacts/${name}`);
  if (!response.ok) {
    throw new Error(`Artifact ${name} not found`);
  }
  return response.text();
}
