import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  AgentProfile,
  AgentsConfig,
  Approval,
  AuditEvent,
  CostRollup,
  Health,
  LLMSettings,
  Task,
  api,
  getActor,
  getApiToken,
  preview,
  setActor,
  setApiToken,
} from "../api";
import { Intensity, resolveTaskOptions } from "../lib/intensity";

export type Page = "chat" | "tasks" | "connections" | "agents" | "settings";

const RUNNING = ["queued", "planning", "executing", "reviewing", "synthesizing"] as const;

type WorkspaceValue = {
  page: Page;
  setPage: (p: Page) => void;
  health: Health | null;
  tasks: Task[];
  approvals: Approval[];
  selectedId: string;
  setSelectedId: (id: string) => void;
  selected: Task | null;
  error: string;
  setError: (e: string) => void;
  refreshing: boolean;
  busy: boolean;
  resolvingId: string;
  softPoll: () => Promise<void>;
  refresh: () => Promise<void>;
  sendMessage: (prompt: string, opts: { intensity: Intensity; askBeforeActing: boolean; packId: string }) => Promise<void>;
  resolve: (id: string, action: string, extra?: Record<string, string>) => Promise<void>;
  pendingForSelected: Approval[];
  hasActiveRuns: boolean;
  connectedCount: number;
  // agents
  agentsConfig: AgentsConfig | null;
  selectedAgentId: string;
  agentDraft: AgentProfile | null;
  agentsMsg: string;
  agentsBusy: boolean;
  savePresetId: string;
  setSavePresetId: (v: string) => void;
  savePresetName: string;
  setSavePresetName: (v: string) => void;
  selectAgent: (id: string) => void;
  saveAgent: () => Promise<void>;
  applyPreset: (id: string) => Promise<void>;
  resetAgents: () => Promise<void>;
  saveCurrentAsPreset: (forceHitl: boolean) => Promise<void>;
  toggleAgentTool: (tool: string) => void;
  setAgentDraft: React.Dispatch<React.SetStateAction<AgentProfile | null>>;
  // connectors
  connectors: any;
  mcpEnabled: boolean;
  setMcpEnabled: (v: boolean) => void;
  mcpServersJson: string;
  setMcpServersJson: (v: string) => void;
  connectorsMsg: string;
  connectorsBusy: boolean;
  connectorDrafts: Record<string, Record<string, string>>;
  connectorConfigDrafts: Record<string, Record<string, string>>;
  expandedConnector: string | null;
  setExpandedConnector: (v: string | null) => void;
  oauthClientId: string;
  setOauthClientId: (v: string) => void;
  oauthClientSecret: string;
  setOauthClientSecret: (v: string) => void;
  saveMcpConnectors: () => Promise<void>;
  reloadMcpConnectors: () => Promise<void>;
  enableAppConnector: (id: string) => Promise<void>;
  disableAppConnector: (id: string) => Promise<void>;
  saveGithubOauthApp: () => Promise<void>;
  connectGithubOAuth: () => Promise<void>;
  patchConnectorSecret: (id: string, key: string, value: string) => void;
  patchConnectorConfig: (id: string, key: string, value: string) => void;
  // settings
  llmSettings: LLMSettings | null;
  openaiKeyDraft: string;
  setOpenaiKeyDraft: (v: string) => void;
  anthropicKeyDraft: string;
  setAnthropicKeyDraft: (v: string) => void;
  settingsMsg: string;
  settingsBusy: boolean;
  apiTokenDraft: string;
  setApiTokenDraft: (v: string) => void;
  actorDraft: string;
  setActorDraft: (v: string) => void;
  costs: CostRollup | null;
  auditEvents: AuditEvent[];
  memoryItems: Array<{ id: string; document?: string; metadata?: Record<string, unknown> }>;
  toolCatalog: Array<{ name: string; description?: string; requires_approval?: boolean }>;
  workingMemory: any;
  saveLlmSettings: () => Promise<void>;
  testLlmSettings: () => Promise<void>;
  patchSettings: (partial: Partial<LLMSettings>) => void;
  onProviderChange: (provider: string) => void;
  saveAccess: () => void;
  // inspect
  trace: any;
  replay: any;
  loadInspect: (taskId: string) => Promise<void>;
};

const Ctx = createContext<WorkspaceValue | null>(null);

export function useWorkspace() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useWorkspace outside provider");
  return v;
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [page, setPage] = useState<Page>("chat");
  const [health, setHealth] = useState<Health | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [resolvingId, setResolvingId] = useState("");

  const [llmSettings, setLlmSettings] = useState<LLMSettings | null>(null);
  const [openaiKeyDraft, setOpenaiKeyDraft] = useState("");
  const [anthropicKeyDraft, setAnthropicKeyDraft] = useState("");
  const [settingsMsg, setSettingsMsg] = useState("");
  const [settingsBusy, setSettingsBusy] = useState(false);
  const [apiTokenDraft, setApiTokenDraft] = useState(getApiToken());
  const [actorDraft, setActorDraft] = useState(getActor());
  const [costs, setCosts] = useState<CostRollup | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [memoryItems, setMemoryItems] = useState<
    Array<{ id: string; document?: string; metadata?: Record<string, unknown> }>
  >([]);
  const [toolCatalog, setToolCatalog] = useState<
    Array<{ name: string; description?: string; requires_approval?: boolean }>
  >([]);
  const [workingMemory, setWorkingMemory] = useState<any>(null);

  const [connectors, setConnectors] = useState<any>(null);
  const [mcpEnabled, setMcpEnabled] = useState(true);
  const [mcpServersJson, setMcpServersJson] = useState("[]");
  const [connectorsMsg, setConnectorsMsg] = useState("");
  const [connectorsBusy, setConnectorsBusy] = useState(false);
  const [connectorDrafts, setConnectorDrafts] = useState<Record<string, Record<string, string>>>({});
  const [connectorConfigDrafts, setConnectorConfigDrafts] = useState<Record<string, Record<string, string>>>({});
  const [expandedConnector, setExpandedConnector] = useState<string | null>(null);
  const [oauthClientId, setOauthClientId] = useState("");
  const [oauthClientSecret, setOauthClientSecret] = useState("");

  const [agentsConfig, setAgentsConfig] = useState<AgentsConfig | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState("research");
  const [agentDraft, setAgentDraft] = useState<AgentProfile | null>(null);
  const [agentsMsg, setAgentsMsg] = useState("");
  const [agentsBusy, setAgentsBusy] = useState(false);
  const [savePresetName, setSavePresetName] = useState("");
  const [savePresetId, setSavePresetId] = useState("");

  const [trace, setTrace] = useState<any>(null);
  const [replay, setReplay] = useState<any>(null);

  const selected = useMemo(() => tasks.find((t) => t.id === selectedId) || null, [tasks, selectedId]);

  const hasActiveRuns = useMemo(
    () => tasks.some((t) => (RUNNING as readonly string[]).includes(t.status)) || busy,
    [tasks, busy]
  );

  const pendingForSelected = useMemo(
    () => (selectedId ? approvals.filter((a) => a.task_id === selectedId) : approvals),
    [approvals, selectedId]
  );

  const connectedCount = useMemo(
    () => (connectors?.catalog || []).filter((c: any) => c.connected).length,
    [connectors]
  );

  const applyTasks = useCallback((t: Task[]) => {
    setTasks(t);
  }, []);

  const softPoll = useCallback(async () => {
    try {
      const calls: Promise<any>[] = [api<Task[]>("/v1/tasks"), api<Approval[]>("/v1/approvals")];
      if (selectedId) calls.push(api<Task>(`/v1/tasks/${selectedId}`));
      const settled = await Promise.allSettled(calls);
      if (settled[0].status === "fulfilled") applyTasks(settled[0].value);
      if (settled[1].status === "fulfilled") setApprovals(settled[1].value);
      if (selectedId && settled[2]?.status === "fulfilled") {
        const detail = settled[2].value as Task;
        setTasks((prev) => {
          const idx = prev.findIndex((t) => t.id === detail.id);
          if (idx < 0) return [detail, ...prev];
          const next = prev.slice();
          next[idx] = { ...next[idx], ...detail };
          return next;
        });
      }
    } catch {
      /* ignore */
    }
  }, [applyTasks, selectedId]);

  const refresh = useCallback(async () => {
    try {
      setRefreshing(true);
      setError("");
      const results = await Promise.allSettled([
        api<Health>("/health"),
        api<Task[]>("/v1/tasks"),
        api<Approval[]>("/v1/approvals"),
        api<LLMSettings>("/v1/settings/llm"),
        api<CostRollup>("/v1/costs?limit=20"),
        api<AuditEvent[]>("/v1/audit?limit=30"),
        api<any>("/v1/connectors"),
        api<AgentsConfig>("/v1/agents"),
        api<Array<{ id: string; document?: string; metadata?: Record<string, unknown> }>>("/v1/memory?limit=40"),
        api<Array<{ name: string; description?: string; requires_approval?: boolean }>>("/v1/tools"),
      ]);
      const labels = ["health", "tasks", "approvals", "llm", "costs", "audit", "connectors", "agents", "memory", "tools"];
      const errors: string[] = [];
      results.forEach((r, i) => {
        if (r.status === "rejected") errors.push(`${labels[i]}: ${(r as PromiseRejectedResult).reason?.message || (r as PromiseRejectedResult).reason}`);
      });
      const val = <T,>(i: number): T | undefined =>
        results[i].status === "fulfilled" ? (results[i] as PromiseFulfilledResult<T>).value : undefined;

      const h = val<Health>(0);
      const t = val<Task[]>(1);
      const a = val<Approval[]>(2);
      const s = val<LLMSettings>(3);
      const c = val<CostRollup>(4);
      const au = val<AuditEvent[]>(5);
      const conn = val<any>(6);
      const ag = val<AgentsConfig>(7);
      const mem = val<Array<{ id: string; document?: string; metadata?: Record<string, unknown> }>>(8);
      const tools = val<Array<{ name: string; description?: string; requires_approval?: boolean }>>(9);

      if (h) setHealth(h);
      if (t) applyTasks(t);
      if (a) setApprovals(a);
      if (s) setLlmSettings(s);
      if (c) setCosts(c);
      if (au) setAuditEvents(au);
      if (mem) setMemoryItems(mem);
      if (tools) setToolCatalog(tools);
      if (conn) {
        setConnectors(conn);
        setMcpEnabled(!!conn?.mcp?.enabled);
        setMcpServersJson(JSON.stringify(conn?.mcp?.servers_config || [], null, 2));
      }
      if (ag) {
        setAgentsConfig(ag);
        setAgentDraft((prev) => {
          if (!prev) return ag.agents.find((x) => x.id === selectedAgentId) || ag.agents[0] || null;
          return prev;
        });
      }
      if (errors.length) setError(errors.join(" · "));
    } catch (e: any) {
      setError(String(e.message || e));
    } finally {
      setRefreshing(false);
    }
  }, [applyTasks, selectedAgentId]);

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    const ms = hasActiveRuns ? 2000 : 8000;
    const id = setInterval(() => softPoll(), ms);
    return () => clearInterval(id);
  }, [hasActiveRuns, softPoll]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("connected") === "github") {
      setPage("connections");
      setExpandedConnector("github");
      const err = params.get("error");
      const user = params.get("user");
      if (err) setConnectorsMsg(`GitHub OAuth failed: ${err}`);
      else setConnectorsMsg(user ? `Connected to GitHub as ${user}` : "Connected to GitHub");
      window.history.replaceState({}, "", window.location.pathname);
      refresh();
    }
  }, [refresh]);

  async function sendMessage(
    prompt: string,
    opts: { intensity: Intensity; askBeforeActing: boolean; packId: string }
  ) {
    if (!prompt.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const mapped = resolveTaskOptions(opts.intensity, opts.askBeforeActing, opts.packId);
      const body: Record<string, unknown> = { prompt, force_hitl: mapped.force_hitl };
      if (mapped.preset_id) body.preset_id = mapped.preset_id;
      const task = await api<Task>("/v1/tasks", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setSelectedId(task.id);
      setPage("chat");
      await softPoll();
    } catch (e: any) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function resolve(id: string, action: string, extra: Record<string, string> = {}) {
    const target = approvals.find((a) => a.id === id);
    setApprovals((prev) => prev.filter((a) => a.id !== id));
    setResolvingId(id);
    try {
      await api(`/v1/approvals/${id}`, {
        method: "POST",
        body: JSON.stringify({ action, note: "elio", actor: getActor(), ...extra }),
      });
      if (target?.task_id) {
        setTasks((prev) =>
          prev.map((t) =>
            t.id === target.task_id && t.status === "awaiting_approval"
              ? { ...t, status: action === "reject" ? "rejected" : "executing" }
              : t
          )
        );
      }
      await softPoll();
    } catch (e: any) {
      setError(String(e.message || e));
      await softPoll();
    } finally {
      setResolvingId("");
    }
  }

  async function loadInspect(taskId: string) {
    setTrace(null);
    setReplay(null);
    setWorkingMemory(null);
    const [trRes, rpRes, wmRes, detailRes] = await Promise.allSettled([
      api(`/v1/traces/${taskId}`),
      api(`/v1/replay/${taskId}`),
      api(`/v1/memory/working/${taskId}`),
      api<Task>(`/v1/tasks/${taskId}`),
    ]);
    if (trRes.status === "fulfilled") setTrace(trRes.value);
    if (rpRes.status === "fulfilled") setReplay(rpRes.value);
    if (wmRes.status === "fulfilled") setWorkingMemory(wmRes.value);
    if (detailRes.status === "fulfilled") {
      const detail = detailRes.value;
      setTasks((prev) => {
        const idx = prev.findIndex((t) => t.id === detail.id);
        if (idx < 0) return [detail, ...prev];
        const next = prev.slice();
        next[idx] = { ...next[idx], ...detail };
        return next;
      });
    }
  }

  async function saveLlmSettings() {
    if (!llmSettings) return;
    setSettingsBusy(true);
    setSettingsMsg("");
    try {
      const body: Record<string, any> = {
        llm_provider: llmSettings.llm_provider,
        ollama_host: llmSettings.ollama_host,
        openai_base_url: llmSettings.openai_base_url,
        supervisor_model: llmSettings.supervisor_model,
        specialist_model: llmSettings.specialist_model,
        embed_model: llmSettings.embed_model,
        openai_supervisor_model: llmSettings.openai_supervisor_model,
        openai_specialist_model: llmSettings.openai_specialist_model,
        openai_embed_model: llmSettings.openai_embed_model,
        anthropic_supervisor_model: llmSettings.anthropic_supervisor_model,
        anthropic_specialist_model: llmSettings.anthropic_specialist_model,
      };
      if (openaiKeyDraft.trim()) body.openai_api_key = openaiKeyDraft.trim();
      if (anthropicKeyDraft.trim()) body.anthropic_api_key = anthropicKeyDraft.trim();
      const saved = await api<LLMSettings>("/v1/settings/llm", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setLlmSettings(saved);
      setOpenaiKeyDraft("");
      setAnthropicKeyDraft("");
      setSettingsMsg("Saved. Workers pick this up on the next LLM call.");
      await refresh();
    } catch (e: any) {
      setSettingsMsg(String(e.message || e));
    } finally {
      setSettingsBusy(false);
    }
  }

  async function testLlmSettings() {
    setSettingsBusy(true);
    setSettingsMsg("");
    try {
      const res = await api<{ ok: boolean; sample?: string; error?: string; model?: string; provider?: string }>(
        "/v1/settings/llm/test",
        { method: "POST", body: "{}" }
      );
      if (res.ok) setSettingsMsg(`Connected · ${res.provider}/${res.model} · ${preview(res.sample, 80)}`);
      else setSettingsMsg(res.error || "Provider check failed");
    } catch (e: any) {
      setSettingsMsg(String(e.message || e));
    } finally {
      setSettingsBusy(false);
    }
  }

  function patchSettings(partial: Partial<LLMSettings>) {
    setLlmSettings((prev) => (prev ? { ...prev, ...partial } : prev));
  }

  function onProviderChange(provider: string) {
    if (!llmSettings) return;
    const preset = llmSettings.presets[provider];
    const next: Partial<LLMSettings> = { llm_provider: provider };
    if (preset) {
      if (provider === "openai") {
        next.openai_supervisor_model = preset.supervisor_models[0];
        next.openai_specialist_model = preset.specialist_models[0];
        next.openai_embed_model = preset.embed_models[0];
      } else if (provider === "anthropic") {
        next.anthropic_supervisor_model = preset.supervisor_models[0];
        next.anthropic_specialist_model = preset.specialist_models[0];
      } else if (provider === "ollama") {
        next.supervisor_model = preset.supervisor_models[0];
        next.specialist_model = preset.specialist_models[0];
        next.embed_model = preset.embed_models[0];
      }
    }
    patchSettings(next);
  }

  function saveAccess() {
    setActor(actorDraft);
    setApiToken(apiTokenDraft);
    setSettingsMsg("Access settings saved in this browser.");
    refresh();
  }

  async function saveMcpConnectors() {
    setConnectorsBusy(true);
    setConnectorsMsg("");
    try {
      const servers = JSON.parse(mcpServersJson);
      if (!Array.isArray(servers)) throw new Error("MCP servers must be a JSON array");
      const res = await api("/v1/connectors/mcp", {
        method: "PUT",
        body: JSON.stringify({ enabled: mcpEnabled, servers }),
      });
      setConnectorsMsg(`Saved · ${(res.status?.registered || []).length} MCP tools registered`);
      await refresh();
    } catch (e: any) {
      setConnectorsMsg(String(e.message || e));
    } finally {
      setConnectorsBusy(false);
    }
  }

  async function reloadMcpConnectors() {
    setConnectorsBusy(true);
    setConnectorsMsg("");
    try {
      const res = await api("/v1/connectors/mcp/reload", { method: "POST", body: "{}" });
      setConnectorsMsg(`Reloaded · ${(res.registered || []).length} tools`);
      await refresh();
    } catch (e: any) {
      setConnectorsMsg(String(e.message || e));
    } finally {
      setConnectorsBusy(false);
    }
  }

  async function enableAppConnector(connectorId: string) {
    setConnectorsBusy(true);
    setConnectorsMsg("");
    try {
      const res = await api(`/v1/connectors/${connectorId}/enable`, {
        method: "POST",
        body: JSON.stringify({
          secrets: connectorDrafts[connectorId] || {},
          config: connectorConfigDrafts[connectorId] || {},
        }),
      });
      setConnectorsMsg(`Connected · ${(res.status?.registered || []).length} MCP tools live`);
      setConnectorDrafts((prev) => ({ ...prev, [connectorId]: {} }));
      await refresh();
    } catch (e: any) {
      setConnectorsMsg(String(e.message || e));
    } finally {
      setConnectorsBusy(false);
    }
  }

  async function disableAppConnector(connectorId: string) {
    setConnectorsBusy(true);
    setConnectorsMsg("");
    try {
      await api(`/v1/connectors/${connectorId}/disable`, { method: "POST", body: "{}" });
      setConnectorsMsg(`Disconnected ${connectorId}`);
      await refresh();
    } catch (e: any) {
      setConnectorsMsg(String(e.message || e));
    } finally {
      setConnectorsBusy(false);
    }
  }

  async function saveGithubOauthApp() {
    setConnectorsBusy(true);
    setConnectorsMsg("");
    try {
      const body: Record<string, string> = {};
      if (oauthClientId.trim()) body.client_id = oauthClientId.trim();
      if (oauthClientSecret.trim()) body.client_secret = oauthClientSecret.trim();
      await api("/v1/connectors/github/oauth", { method: "PUT", body: JSON.stringify(body) });
      setOauthClientId("");
      setOauthClientSecret("");
      setConnectorsMsg("Saved GitHub OAuth App — you can Connect with GitHub now");
      await refresh();
    } catch (e: any) {
      setConnectorsMsg(String(e.message || e));
    } finally {
      setConnectorsBusy(false);
    }
  }

  async function connectGithubOAuth() {
    setConnectorsBusy(true);
    setConnectorsMsg("");
    try {
      const owner = (connectorConfigDrafts.github || {}).GITHUB_DEFAULT_OWNER || "";
      const res = await api<{ authorize_url: string }>("/v1/connectors/github/oauth/start", {
        method: "POST",
        body: JSON.stringify({ default_owner: owner }),
      });
      window.location.href = res.authorize_url;
    } catch (e: any) {
      setConnectorsMsg(String(e.message || e));
      setConnectorsBusy(false);
    }
  }

  function patchConnectorSecret(connectorId: string, key: string, value: string) {
    setConnectorDrafts((prev) => ({
      ...prev,
      [connectorId]: { ...(prev[connectorId] || {}), [key]: value },
    }));
  }

  function patchConnectorConfig(connectorId: string, key: string, value: string) {
    setConnectorConfigDrafts((prev) => ({
      ...prev,
      [connectorId]: { ...(prev[connectorId] || {}), [key]: value },
    }));
  }

  function selectAgent(id: string) {
    const a = agentsConfig?.agents.find((x) => x.id === id);
    setSelectedAgentId(id);
    if (a) setAgentDraft({ ...a, tools: [...(a.tools || [])] });
  }

  async function saveAgent() {
    if (!agentDraft) return;
    setAgentsBusy(true);
    setAgentsMsg("");
    try {
      const saved = await api<AgentProfile>(`/v1/agents/${agentDraft.id}`, {
        method: "PUT",
        body: JSON.stringify({
          display_name: agentDraft.display_name,
          instructions: agentDraft.instructions,
          output_contract: agentDraft.output_contract,
          tools: agentDraft.tools,
          model: agentDraft.model,
          requires_hitl: agentDraft.requires_hitl,
          enabled: agentDraft.enabled,
        }),
      });
      setAgentDraft(saved);
      setAgentsMsg(`Saved ${saved.display_name}`);
      setAgentsConfig(await api<AgentsConfig>("/v1/agents"));
    } catch (e: any) {
      setAgentsMsg(String(e.message || e));
    } finally {
      setAgentsBusy(false);
    }
  }

  async function applyPreset(presetId: string) {
    setAgentsBusy(true);
    setAgentsMsg("");
    try {
      const snap = await api<AgentsConfig>(`/v1/agents/presets/${presetId}/apply`, {
        method: "POST",
        body: "{}",
      });
      setAgentsConfig(snap);
      const a = snap.agents.find((x) => x.id === selectedAgentId) || snap.agents[0];
      if (a) setAgentDraft({ ...a, tools: [...(a.tools || [])] });
      setAgentsMsg(`Applied pack · ${snap.presets.find((p) => p.id === presetId)?.name || presetId}`);
    } catch (e: any) {
      setAgentsMsg(String(e.message || e));
    } finally {
      setAgentsBusy(false);
    }
  }

  async function resetAgents() {
    setAgentsBusy(true);
    setAgentsMsg("");
    try {
      const snap = await api<AgentsConfig>("/v1/agents/reset", { method: "POST", body: "{}" });
      setAgentsConfig(snap);
      const a = snap.agents.find((x) => x.id === selectedAgentId) || snap.agents[0];
      if (a) setAgentDraft({ ...a, tools: [...(a.tools || [])] });
      setAgentsMsg("Reset to defaults");
    } catch (e: any) {
      setAgentsMsg(String(e.message || e));
    } finally {
      setAgentsBusy(false);
    }
  }

  async function saveCurrentAsPreset(forceHitl: boolean) {
    if (!savePresetId.trim() || !savePresetName.trim()) {
      setAgentsMsg("Preset id and name required");
      return;
    }
    setAgentsBusy(true);
    setAgentsMsg("");
    try {
      const snap = await api<AgentsConfig>("/v1/agents/presets", {
        method: "POST",
        body: JSON.stringify({
          id: savePresetId.trim(),
          name: savePresetName.trim(),
          description: "Saved from Elio",
          force_hitl: forceHitl,
        }),
      });
      setAgentsConfig(snap);
      setAgentsMsg(`Saved pack · ${savePresetName.trim()}`);
      setSavePresetId("");
      setSavePresetName("");
    } catch (e: any) {
      setAgentsMsg(String(e.message || e));
    } finally {
      setAgentsBusy(false);
    }
  }

  function toggleAgentTool(tool: string) {
    setAgentDraft((prev) => {
      if (!prev) return prev;
      const has = prev.tools.includes(tool);
      return {
        ...prev,
        tools: has ? prev.tools.filter((t) => t !== tool) : [...prev.tools, tool],
      };
    });
  }

  const value: WorkspaceValue = {
    page,
    setPage,
    health,
    tasks,
    approvals,
    selectedId,
    setSelectedId,
    selected,
    error,
    setError,
    refreshing,
    busy,
    resolvingId,
    softPoll,
    refresh,
    sendMessage,
    resolve,
    pendingForSelected,
    hasActiveRuns,
    connectedCount,
    agentsConfig,
    selectedAgentId,
    agentDraft,
    agentsMsg,
    agentsBusy,
    savePresetId,
    setSavePresetId,
    savePresetName,
    setSavePresetName,
    selectAgent,
    saveAgent,
    applyPreset,
    resetAgents,
    saveCurrentAsPreset,
    toggleAgentTool,
    setAgentDraft,
    connectors,
    mcpEnabled,
    setMcpEnabled,
    mcpServersJson,
    setMcpServersJson,
    connectorsMsg,
    connectorsBusy,
    connectorDrafts,
    connectorConfigDrafts,
    expandedConnector,
    setExpandedConnector,
    oauthClientId,
    setOauthClientId,
    oauthClientSecret,
    setOauthClientSecret,
    saveMcpConnectors,
    reloadMcpConnectors,
    enableAppConnector,
    disableAppConnector,
    saveGithubOauthApp,
    connectGithubOAuth,
    patchConnectorSecret,
    patchConnectorConfig,
    llmSettings,
    openaiKeyDraft,
    setOpenaiKeyDraft,
    anthropicKeyDraft,
    setAnthropicKeyDraft,
    settingsMsg,
    settingsBusy,
    apiTokenDraft,
    setApiTokenDraft,
    actorDraft,
    setActorDraft,
    costs,
    auditEvents,
    memoryItems,
    toolCatalog,
    workingMemory,
    saveLlmSettings,
    testLlmSettings,
    patchSettings,
    onProviderChange,
    saveAccess,
    trace,
    replay,
    loadInspect,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
