export const API = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export type Task = {
  id: string;
  prompt: string;
  status: string;
  deliverable?: string;
  error?: string;
  created_at?: string;
  force_hitl?: boolean;
};

export type Approval = {
  id: string;
  task_id: string;
  level: string;
  reason: string;
  proposed_action: string;
  status: string;
};

export type Health = {
  ok: boolean;
  postgres?: boolean;
  redis?: boolean;
  otel_enabled?: boolean;
  llm_provider?: string;
  llm?: { ok?: boolean; mode?: string; provider?: string; models?: string[] };
  mcp_tools?: string[];
  code_sandbox?: string;
  langsmith_tracing?: boolean;
  jaeger_ui?: string;
};

export function statusTone(status: string): "good" | "warn" | "bad" | "muted" {
  if (["completed", "approved"].includes(status)) return "good";
  if (["failed", "rejected"].includes(status)) return "bad";
  if (["awaiting_approval", "reviewing", "executing", "planning", "queued"].includes(status)) return "warn";
  return "muted";
}

export function shortId(id: string) {
  return id.length > 16 ? `${id.slice(0, 12)}…` : id;
}

export function preview(text?: string, n = 120) {
  if (!text) return "";
  return text.length > n ? `${text.slice(0, n)}…` : text;
}
