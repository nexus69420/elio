export const API = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

const LS_TOKEN = "orch_api_token";
const LS_ACTOR = "orch_actor";

export function getApiToken() {
  return localStorage.getItem(LS_TOKEN) || "";
}

export function setApiToken(token: string) {
  if (token) localStorage.setItem(LS_TOKEN, token);
  else localStorage.removeItem(LS_TOKEN);
}

export function getActor() {
  return localStorage.getItem(LS_ACTOR) || "operator";
}

export function setActor(actor: string) {
  localStorage.setItem(LS_ACTOR, actor || "operator");
}

export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  const token = getApiToken();
  if (token) headers["X-API-Key"] = token;
  headers["X-Actor"] = getActor();

  const res = await fetch(`${API}${path}`, {
    ...options,
    headers,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export type Task = {
  id: string;
  prompt: string;
  title?: string;
  status: string;
  deliverable?: string;
  error?: string;
  created_at?: string;
  force_hitl?: boolean;
  preset_id?: string;
  created_by?: string;
};

export type Approval = {
  id: string;
  task_id: string;
  level: string;
  reason: string;
  proposed_action: string;
  status: string;
  actor?: string;
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
  auth_required?: boolean;
};

export type LLMSettings = {
  llm_provider: string;
  ollama_host: string;
  openai_base_url: string;
  openai_api_key_set: boolean;
  openai_api_key_masked: string;
  anthropic_api_key_set: boolean;
  anthropic_api_key_masked: string;
  supervisor_model: string;
  specialist_model: string;
  embed_model: string;
  openai_supervisor_model: string;
  openai_specialist_model: string;
  openai_embed_model: string;
  anthropic_supervisor_model: string;
  anthropic_specialist_model: string;
  stub: boolean;
  presets: Record<
    string,
    {
      label: string;
      needs_api_key: boolean;
      supervisor_models: string[];
      specialist_models: string[];
      embed_models: string[];
      note?: string;
    }
  >;
  active_chat_models: { supervisor: string; specialist: string; embed: string };
};

export type CostRollup = {
  tasks: Array<{
    task_id: string;
    status: string;
    prompt_preview: string;
    cost_usd: number;
    total_tokens: number;
  }>;
  total_cost_usd: number;
  note?: string;
};

export type AuditEvent = {
  id: string;
  actor: string;
  action: string;
  task_id: string;
  resource_type: string;
  resource_id: string;
  detail: Record<string, unknown>;
  created_at?: string;
};

export type AgentProfile = {
  id: string;
  display_name: string;
  kind: string;
  instructions: string;
  output_contract: string;
  tools: string[];
  model: string;
  requires_hitl: boolean;
  enabled: boolean;
};

export type AgentPreset = {
  id: string;
  name: string;
  description: string;
  force_hitl: boolean;
  builtin: boolean;
  agent_ids: string[];
};

export type AgentsConfig = {
  agents: AgentProfile[];
  presets: AgentPreset[];
  active_preset_id?: string | null;
  available_tools: string[];
  defaults?: AgentProfile[];
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

export function taskLabel(t: { id: string; title?: string; prompt?: string }) {
  if (t.title?.trim()) return t.title.trim();
  if (t.prompt?.trim()) {
    const p = t.prompt.trim().replace(/\s+/g, " ");
    return p.length > 56 ? `${p.slice(0, 56)}…` : p;
  }
  return shortId(t.id);
}

export function preview(text?: string, n = 120) {
  if (!text) return "";
  return text.length > n ? `${text.slice(0, n)}…` : text;
}

export function formatUsd(n?: number) {
  if (n == null || Number.isNaN(n)) return "$0";
  if (n === 0) return "$0";
  if (n < 0.0001) return `$${n.toFixed(8)}`;
  if (n < 0.01) return `$${n.toFixed(6)}`;
  return `$${n.toFixed(4)}`;
}
