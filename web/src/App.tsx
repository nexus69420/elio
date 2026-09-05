import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  Bot,
  CheckCircle2,
  ExternalLink,
  Brain,
  GitBranch,
  KeyRound,
  LayoutDashboard,
  ListTodo,
  Loader2,
  Play,
  Plug,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import {
  API,
  AgentProfile,
  AgentsConfig,
  Approval,
  AuditEvent,
  CostRollup,
  Health,
  LLMSettings,
  Task,
  api,
  formatUsd,
  getActor,
  getApiToken,
  preview,
  setActor,
  setApiToken,
  shortId,
  statusTone,
  taskLabel,
} from "./api";

const DEFAULT_PROMPT =
  "Research the tradeoffs of running multi-agent LLM systems fully locally versus paid cloud APIs. Analyze cost, latency, quality, and privacy. Write a short executive brief with a recommendation.";

type Page = "overview" | "runs" | "approvals" | "inspect" | "memory" | "agents" | "connectors" | "settings";

export default function App() {
  const [page, setPage] = useState<Page>("overview");
  const [health, setHealth] = useState<Health | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [memories, setMemories] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [filter, setFilter] = useState("all");
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [forceHitl, setForceHitl] = useState(true);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [resolvingId, setResolvingId] = useState("");
  const [awaitingApprovalFor, setAwaitingApprovalFor] = useState("");
  const [error, setError] = useState("");
  const [trace, setTrace] = useState<any>(null);
  const [replay, setReplay] = useState<any>(null);
  const [inspectTab, setInspectTab] = useState<"timeline" | "replay" | "output">("timeline");
  const [modifyText, setModifyText] = useState<Record<string, string>>({});
  const [takeoverText, setTakeoverText] = useState<Record<string, string>>({});
  const [llmSettings, setLlmSettings] = useState<LLMSettings | null>(null);
  const [openaiKeyDraft, setOpenaiKeyDraft] = useState("");
  const [anthropicKeyDraft, setAnthropicKeyDraft] = useState("");
  const [settingsMsg, setSettingsMsg] = useState("");
  const [settingsBusy, setSettingsBusy] = useState(false);
  const [apiTokenDraft, setApiTokenDraft] = useState(getApiToken());
  const [actorDraft, setActorDraft] = useState(getActor());
  const [costs, setCosts] = useState<CostRollup | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
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
  const [dispatchPreset, setDispatchPreset] = useState("");
  const [agentsMsg, setAgentsMsg] = useState("");
  const [agentsBusy, setAgentsBusy] = useState(false);
  const [savePresetName, setSavePresetName] = useState("");
  const [savePresetId, setSavePresetId] = useState("");

  const selected = useMemo(
    () => tasks.find((t) => t.id === selectedId) || null,
    [tasks, selectedId]
  );

  const RUNNING = ["queued", "planning", "executing", "reviewing", "synthesizing"] as const;

  const stats = useMemo(() => {
    const completed = tasks.filter((t) => t.status === "completed").length;
    const failed = tasks.filter((t) => t.status === "failed" || t.status === "rejected").length;
    const active = tasks.filter((t) =>
      [...RUNNING, "awaiting_approval"].includes(t.status) &&
      (t.status !== "awaiting_approval" || approvals.some((a) => a.task_id === t.id))
    ).length;
    return { completed, failed, active, approvals: approvals.length };
  }, [tasks, approvals]);

  const hasActiveRuns = useMemo(
    () => tasks.some((t) => (RUNNING as readonly string[]).includes(t.status)) || busy || !!awaitingApprovalFor,
    [tasks, busy, awaitingApprovalFor]
  );

  const liveTask = useMemo(() => {
    const isLive = (t: Task) =>
      (RUNNING as readonly string[]).includes(t.status) ||
      (t.status === "awaiting_approval" && approvals.some((a) => a.task_id === t.id));
    if (selected && isLive(selected)) return selected;
    return tasks.find(isLive) || null;
  }, [tasks, selected, approvals]);

  const filtered = useMemo(() => {
    if (filter === "all") return tasks;
    if (filter === "active") {
      return tasks.filter((t) =>
        (RUNNING as readonly string[]).includes(t.status) ||
        (t.status === "awaiting_approval" && approvals.some((a) => a.task_id === t.id))
      );
    }
    return tasks.filter((t) => t.status === filter);
  }, [tasks, filter, approvals]);

  function applyTasks(t: Task[]) {
    setTasks(t);
    if (!selectedId && t[0]) setSelectedId(t[0].id);
  }

  /** Fast poll — tasks + approvals only. No spinner. */
  async function softPoll() {
    try {
      const [tRes, aRes] = await Promise.allSettled([
        api<Task[]>("/v1/tasks"),
        api<Approval[]>("/v1/approvals"),
      ]);
      if (tRes.status === "fulfilled") applyTasks(tRes.value);
      if (aRes.status === "fulfilled") setApprovals(aRes.value);
    } catch {
      /* ignore background poll errors */
    }
  }

  /** Full refresh for manual Refresh / page load. */
  async function refresh() {
    try {
      setRefreshing(true);
      setError("");
      const results = await Promise.allSettled([
        api<Health>("/health"),
        api<Task[]>("/v1/tasks"),
        api<Approval[]>("/v1/approvals"),
        api<any[]>("/v1/memory"),
        api<LLMSettings>("/v1/settings/llm"),
        api<CostRollup>("/v1/costs?limit=20"),
        api<AuditEvent[]>("/v1/audit?limit=30"),
        api<any>("/v1/connectors"),
        api<AgentsConfig>("/v1/agents"),
      ]);
      const labels = ["health", "tasks", "approvals", "memory", "llm", "costs", "audit", "connectors", "agents"];
      const errors: string[] = [];
      results.forEach((r, i) => {
        if (r.status === "rejected") errors.push(`${labels[i]}: ${r.reason?.message || r.reason}`);
      });

      const val = <T,>(i: number): T | undefined =>
        results[i].status === "fulfilled" ? (results[i] as PromiseFulfilledResult<T>).value : undefined;

      const h = val<Health>(0);
      const t = val<Task[]>(1);
      const a = val<Approval[]>(2);
      const m = val<any[]>(3);
      const s = val<LLMSettings>(4);
      const c = val<CostRollup>(5);
      const au = val<AuditEvent[]>(6);
      const conn = val<any>(7);
      const ag = val<AgentsConfig>(8);

      if (h) setHealth(h);
      if (t) applyTasks(t);
      if (a) setApprovals(a);
      if (m) setMemories(m);
      if (s) setLlmSettings(s);
      if (c) setCosts(c);
      if (au) setAuditEvents(au);
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
      setSettingsMsg("Saved. Celery workers pick this up on the next LLM call.");
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
      if (res.ok) {
        setSettingsMsg(`Connected · ${res.provider}/${res.model} · ${preview(res.sample, 80)}`);
      } else {
        setSettingsMsg(res.error || "Provider check failed");
      }
    } catch (e: any) {
      setSettingsMsg(String(e.message || e));
    } finally {
      setSettingsBusy(false);
    }
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

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    const ms = hasActiveRuns ? 2000 : 8000;
    const id = setInterval(() => {
      softPoll();
    }, ms);
    return () => clearInterval(id);
  }, [hasActiveRuns]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("connected");
    if (connected === "github") {
      setPage("connectors");
      setExpandedConnector("github");
      const err = params.get("error");
      const user = params.get("user");
      if (err) setConnectorsMsg(`GitHub OAuth failed: ${err}`);
      else setConnectorsMsg(user ? `Connected to GitHub as ${user}` : "Connected to GitHub");
      window.history.replaceState({}, "", window.location.pathname);
      refresh();
    }
  }, []);

  // Jump to Approvals only once an approval actually exists for this run
  useEffect(() => {
    if (!awaitingApprovalFor) return;
    const hit = approvals.some((a) => a.task_id === awaitingApprovalFor);
    if (hit) {
      setPage("approvals");
      setAwaitingApprovalFor("");
    }
    // Clear watch if the run finished/failed without a gate
    const task = tasks.find((t) => t.id === awaitingApprovalFor);
    if (task && ["completed", "failed", "rejected"].includes(task.status)) {
      setAwaitingApprovalFor("");
    }
  }, [approvals, awaitingApprovalFor, tasks]);

  useEffect(() => {
    if (!selectedId || page !== "inspect") return;
    loadInspect(selectedId);
  }, [selectedId, page]);

  async function runTask() {
    if (!prompt.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const body: Record<string, unknown> = { prompt, force_hitl: forceHitl };
      if (dispatchPreset) body.preset_id = dispatchPreset;
      const task = await api<Task>("/v1/tasks", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setSelectedId(task.id);
      setInspectTab("timeline");
      setPage("inspect");
      if (forceHitl) setAwaitingApprovalFor(task.id);
      await softPoll();
    } catch (e: any) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
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
      const ag = await api<AgentsConfig>("/v1/agents");
      setAgentsConfig(ag);
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
      const preset = snap.presets.find((p) => p.id === presetId);
      if (preset) {
        setDispatchPreset(presetId);
        setForceHitl(preset.force_hitl);
      }
      setAgentsMsg(`Applied preset · ${preset?.name || presetId}`);
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
      setDispatchPreset("");
      setAgentsMsg("Reset to code defaults");
    } catch (e: any) {
      setAgentsMsg(String(e.message || e));
    } finally {
      setAgentsBusy(false);
    }
  }

  async function saveCurrentAsPreset() {
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
          description: "Saved from Mission Control",
          force_hitl: forceHitl,
        }),
      });
      setAgentsConfig(snap);
      setDispatchPreset(savePresetId.trim());
      setAgentsMsg(`Saved preset · ${savePresetName.trim()}`);
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

  async function resolve(id: string, action: string, extra: Record<string, string> = {}) {
    const target = approvals.find((a) => a.id === id);
    // Optimistic: remove from queue immediately so Approve feels instant
    setApprovals((prev) => prev.filter((a) => a.id !== id));
    setResolvingId(id);
    try {
      await api(`/v1/approvals/${id}`, {
        method: "POST",
        body: JSON.stringify({ action, note: "mission-control", actor: getActor(), ...extra }),
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
    setError("");
    setTrace(null);
    setReplay(null);
    const [trRes, rpRes] = await Promise.allSettled([
      api(`/v1/traces/${taskId}`),
      api(`/v1/replay/${taskId}`),
    ]);
    const errors: string[] = [];
    if (trRes.status === "fulfilled") setTrace(trRes.value);
    else errors.push(`traces: ${trRes.reason?.message || trRes.reason}`);
    if (rpRes.status === "fulfilled") setReplay(rpRes.value);
    else errors.push(`replay: ${rpRes.reason?.message || rpRes.reason}`);
    if (errors.length) setError(errors.join(" · "));
  }

  const nav = [
    { id: "overview" as Page, label: "Overview", icon: LayoutDashboard },
    { id: "runs" as Page, label: "Runs", icon: ListTodo, count: tasks.length },
    { id: "approvals" as Page, label: "Approvals", icon: ShieldAlert, count: approvals.length, hot: approvals.length > 0 },
    { id: "inspect" as Page, label: "Inspect", icon: GitBranch },
    { id: "memory" as Page, label: "Memory", icon: Brain, count: memories.length },
    { id: "agents" as Page, label: "Agents", icon: Bot, count: agentsConfig?.agents.length },
    { id: "connectors" as Page, label: "Connectors", icon: Plug, count: (health?.mcp_tools || []).length, hot: (health?.mcp_tools || []).length > 0 },
    { id: "settings" as Page, label: "Settings", icon: KeyRound },
  ];

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">O</div>
          <div>
            <h1>Orchestrator</h1>
            <p>Mission Control</p>
          </div>
        </div>

        <nav className="nav">
          {nav.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={`nav-btn ${page === item.id ? "active" : ""}`}
                onClick={() => setPage(item.id)}
              >
                <Icon size={16} />
                {item.label}
                {typeof item.count === "number" && (
                  <span className={`count ${item.hot ? "hot" : ""}`}>{item.count}</span>
                )}
              </button>
            );
          })}
          <a className="nav-btn" href={health?.jaeger_ui || "http://localhost:16686"} target="_blank" rel="noreferrer">
            <ExternalLink size={16} />
            Jaeger
          </a>
        </nav>

        <div className="sidebar-foot">
          <h3>System</h3>
          <HealthLine label="API" on={!!health?.ok} />
          <HealthLine label="Postgres" on={!!health?.postgres} />
          <HealthLine label="Redis" on={!!health?.redis} />
          <HealthLine label="OTel" on={!!health?.otel_enabled} />
          <div className="health-row">
            <span>LLM</span>
            <span>{health?.llm?.ok ? health.llm_provider || health.llm.mode : "down"}</span>
          </div>
          <div className="health-row" style={{ cursor: "pointer" }} onClick={() => setPage("connectors")}>
            <span>MCP tools</span>
            <span>{(health?.mcp_tools || []).length}</span>
          </div>
        </div>
      </aside>

      <main className="main">
        {error && <div className="alert">{error}</div>}

        {liveTask && (
          <div className={`run-banner tone-${statusTone(liveTask.status)}`}>
            {(RUNNING as readonly string[]).includes(liveTask.status) ? (
              <Loader2 size={16} className="spin" />
            ) : (
              <ShieldAlert size={16} />
            )}
            <div className="run-banner-body">
              <strong>{taskLabel(liveTask)}</strong>
              <span>
                {liveTask.status.replace(/_/g, " ")}
                {liveTask.status === "awaiting_approval" ? " · action needed in Approvals" : ""}
              </span>
            </div>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => {
                setSelectedId(liveTask.id);
                setPage(
                  liveTask.status === "awaiting_approval" && approvals.some((a) => a.task_id === liveTask.id)
                    ? "approvals"
                    : "inspect"
                );
              }}
            >
              Open
            </button>
          </div>
        )}

        {page === "overview" && (
          <>
            <div className="topbar">
              <div>
                <h2>Operations overview</h2>
                <p>Dispatch missions, gate sensitive steps with HITL, and inspect agent timelines — LangSmith/Langfuse-style control plane for your local stack.</p>
              </div>
              <div className="actions">
                <button className="btn btn-secondary" disabled={refreshing} onClick={refresh}>
                  <RefreshCw size={15} className={refreshing ? "spin" : undefined} /> Refresh
                </button>
                <button className="btn btn-primary" onClick={() => setPage("runs")}><Sparkles size={15} /> New run</button>
              </div>
            </div>

            <div className="kpi-grid">
              <div className="kpi"><div className="label">Active</div><div className="value">{stats.active}</div><div className="sub">in-flight</div></div>
              <div className="kpi"><div className="label">Pending approvals</div><div className="value">{stats.approvals}</div><div className="sub">HITL queue</div></div>
              <div className="kpi"><div className="label">Completed</div><div className="value">{stats.completed}</div><div className="sub">successful</div></div>
              <div className="kpi"><div className="label">Est. spend</div><div className="value">{formatUsd(costs?.total_cost_usd)}</div><div className="sub">recent · Ollama $0</div></div>
            </div>

            <div className="grid-2">
              <div className="panel">
                <div className="panel-head">
                  <h3>Dispatch mission</h3>
                </div>
                <div className="field">
                  <label>Prompt</label>
                  <PromptInput value={prompt} onChange={setPrompt} disabled={busy} />
                </div>
                <div className="field">
                  <label>Team preset (optional)</label>
                  <select
                    value={dispatchPreset}
                    onChange={(e) => {
                      const id = e.target.value;
                      setDispatchPreset(id);
                      const p = agentsConfig?.presets.find((x) => x.id === id);
                      if (p) setForceHitl(p.force_hitl);
                    }}
                  >
                    <option value="">Current team config</option>
                    {(agentsConfig?.presets || []).map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}{p.builtin ? "" : " (custom)"}
                      </option>
                    ))}
                  </select>
                  {dispatchPreset && (
                    <p className="muted">
                      {(agentsConfig?.presets.find((p) => p.id === dispatchPreset)?.description) || ""}
                    </p>
                  )}
                </div>
                <label className="check">
                  <input type="checkbox" checked={forceHitl} onChange={(e) => setForceHitl(e.target.checked)} />
                  <span>Force human approval before final deliverable</span>
                </label>
                <div className="actions" style={{ marginTop: 14 }}>
                  <button className="btn btn-primary" disabled={busy || !prompt.trim()} onClick={runTask}>
                    {busy ? <Loader2 size={15} className="spin" /> : <Play size={15} />}
                    {busy ? "Queuing…" : "Run via Celery"}
                  </button>
                  <button className="btn btn-secondary" type="button" onClick={() => setPage("agents")}>
                    <Bot size={15} /> Edit agents
                  </button>
                </div>
                {busy && <p className="muted run-hint">Queued — opening Inspect so you can watch progress.</p>}
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h3>Needs attention</h3>
                  <button className="btn btn-ghost btn-sm" onClick={() => setPage("approvals")}>Open queue</button>
                </div>
                {approvals.length === 0 ? (
                  <div className="empty">No pending approvals. Agents are either idle or still working.</div>
                ) : (
                  <div className="list">
                    {approvals.slice(0, 4).map((a) => (
                      <div className="run-item" key={a.id} onClick={() => setPage("approvals")}>
                        <div className="run-meta">
                          <span className="id">{shortId(a.id)}</span>
                          <span className="pill warn">{a.level}</span>
                        </div>
                        <div className="prompt">{preview(a.reason, 100)}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {page === "runs" && (
          <>
            <div className="topbar">
              <div>
                <h2>Runs</h2>
                <p>Inbox of agent missions. Select a run to inspect timeline, replay, and output.</p>
              </div>
              <div className="actions">
                <button className="btn btn-secondary" disabled={refreshing} onClick={refresh}>
                  <RefreshCw size={15} className={refreshing ? "spin" : undefined} /> Refresh
                </button>
              </div>
            </div>

            <div className="grid-runs">
              <div className="panel">
                <div className="panel-head"><h3>Dispatch</h3></div>
                <div className="field">
                  <label>Prompt</label>
                  <PromptInput value={prompt} onChange={setPrompt} disabled={busy} />
                </div>
                <div className="field">
                  <label>Team preset (optional)</label>
                  <select
                    value={dispatchPreset}
                    onChange={(e) => {
                      const id = e.target.value;
                      setDispatchPreset(id);
                      const p = agentsConfig?.presets.find((x) => x.id === id);
                      if (p) setForceHitl(p.force_hitl);
                    }}
                  >
                    <option value="">Current team config</option>
                    {(agentsConfig?.presets || []).map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}{p.builtin ? "" : " (custom)"}
                      </option>
                    ))}
                  </select>
                </div>
                <label className="check">
                  <input type="checkbox" checked={forceHitl} onChange={(e) => setForceHitl(e.target.checked)} />
                  <span>Force human approval (HITL) before final deliverable</span>
                </label>
                <div className="actions" style={{ marginTop: 12 }}>
                  <button className="btn btn-primary" disabled={busy || !prompt.trim()} onClick={runTask}>
                    {busy ? <Loader2 size={15} className="spin" /> : <Play size={15} />}
                    {busy ? "Queuing…" : "Run"}
                  </button>
                </div>

                <div className="filters" style={{ marginTop: 18 }}>
                  {["all", "active", "completed", "failed", "awaiting_approval"].map((f) => (
                    <button key={f} className={`chip ${filter === f ? "active" : ""}`} onClick={() => setFilter(f)}>
                      {f.replace("_", " ")}
                    </button>
                  ))}
                </div>

                <div className="list" style={{ maxHeight: 420, overflow: "auto" }}>
                  {filtered.map((t) => (
                    <div
                      key={t.id}
                      className={`run-item ${selectedId === t.id ? "active" : ""}`}
                      onClick={() => {
                        setSelectedId(t.id);
                        setPage("inspect");
                      }}
                    >
                      <div className="run-meta">
                        <span className="id">{taskLabel(t)}</span>
                        <span className={`pill ${statusTone(t.status)}`}>{t.status}</span>
                      </div>
                      <div className="prompt">{preview(t.prompt)}</div>
                      <div className="muted">{shortId(t.id)}</div>
                    </div>
                  ))}
                  {!filtered.length && <div className="empty">No runs match this filter.</div>}
                </div>
              </div>

              <div className="panel">
                {!selected ? (
                  <div className="empty">Select a run to preview output.</div>
                ) : (
                  <>
                    <div className="panel-head">
                      <h3>{taskLabel(selected)}</h3>
                      <span className={`pill ${statusTone(selected.status)}`}>{selected.status}</span>
                    </div>
                    <div className="muted" style={{ marginBottom: 10 }}>{shortId(selected.id)}</div>
                    <div className="field">
                      <label>Prompt</label>
                      <div className="code">{selected.prompt}</div>
                    </div>
                    {selected.error && (
                      <div className="field">
                        <label>Error</label>
                        <div className="code">{selected.error}</div>
                      </div>
                    )}
                    {selected.deliverable && (
                      <div className="field">
                        <label>Deliverable</label>
                        <div className="code">{selected.deliverable}</div>
                      </div>
                    )}
                    <div className="actions">
                      <button className="btn btn-ghost" onClick={() => setPage("inspect")}>
                        <Activity size={15} /> Open inspect
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </>
        )}

        {page === "approvals" && (
          <>
            <div className="topbar">
              <div>
                <h2>Human-in-the-loop</h2>
                <p>Approve, reject, edit, or take over when agents hit a confidence or sensitivity gate.</p>
              </div>
              <button className="btn btn-secondary" disabled={refreshing} onClick={refresh}>
                <RefreshCw size={15} className={refreshing ? "spin" : undefined} /> Refresh
              </button>
            </div>

            <div className="list">
              {approvals.map((item) => (
                <div className="panel" key={item.id}>
                  <div className="panel-head">
                    <h3>{shortId(item.id)} · task {shortId(item.task_id)}</h3>
                    <span className="pill warn">{item.level}</span>
                  </div>
                  <p style={{ color: "var(--muted)", marginTop: 0 }}>{item.reason}</p>
                  <div className="code">{item.proposed_action}</div>
                  <div className="actions" style={{ marginTop: 12 }}>
                    <button
                      className="btn btn-primary"
                      disabled={!!resolvingId}
                      onClick={() => resolve(item.id, "approve")}
                    >
                      {resolvingId === item.id ? <Loader2 size={15} className="spin" /> : <CheckCircle2 size={15} />}
                      Approve
                    </button>
                    <button
                      className="btn btn-danger"
                      disabled={!!resolvingId}
                      onClick={() => resolve(item.id, "reject")}
                    >
                      Reject
                    </button>
                  </div>
                  <div className="field" style={{ marginTop: 12 }}>
                    <label>Modify deliverable</label>
                    <PromptInput
                      value={modifyText[item.id] || ""}
                      onChange={(v) => setModifyText({ ...modifyText, [item.id]: v })}
                      minRows={3}
                      maxHeight={180}
                    />
                    <button
                      className="btn btn-ghost btn-sm"
                      style={{ marginTop: 8 }}
                      disabled={!!resolvingId}
                      onClick={() => resolve(item.id, "modify", { modified_action: modifyText[item.id] || "" })}
                    >
                      Modify & approve
                    </button>
                  </div>
                  <div className="field">
                    <label>Take over</label>
                    <PromptInput
                      value={takeoverText[item.id] || ""}
                      onChange={(v) => setTakeoverText({ ...takeoverText, [item.id]: v })}
                      minRows={3}
                      maxHeight={180}
                    />
                    <button
                      className="btn btn-secondary btn-sm"
                      style={{ marginTop: 8 }}
                      disabled={!!resolvingId}
                      onClick={() => resolve(item.id, "take_over", { human_output: takeoverText[item.id] || "" })}
                    >
                      Take over
                    </button>
                  </div>
                </div>
              ))}
              {!approvals.length && (
                <div className="panel empty-panel">
                  {awaitingApprovalFor && tasks.some((t) => t.id === awaitingApprovalFor && (RUNNING as readonly string[]).includes(t.status)) ? (
                    <div className="empty waiting">
                      <Loader2 size={22} className="spin" />
                      <div>
                        <strong>Waiting for the first approval gate</strong>
                        <p>Your run is in progress. This page will fill when agents need you.</p>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          style={{ marginTop: 10 }}
                          onClick={() => {
                            setSelectedId(awaitingApprovalFor);
                            setPage("inspect");
                          }}
                        >
                          Watch progress in Inspect
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="empty">No pending approvals. Queue is clear.</div>
                  )}
                </div>
              )}
            </div>
          </>
        )}

        {page === "inspect" && (
          <>
            <div className="topbar">
              <div>
                <h2>Inspect</h2>
                <p>Timeline spans + conversation replay for a selected run (LangSmith Studio vibes, local stack).</p>
              </div>
              <div className="actions">
                <select
                  value={selectedId}
                  onChange={(e) => setSelectedId(e.target.value)}
                  style={{ minWidth: 220 }}
                >
                  <option value="">Select run…</option>
                  {tasks.map((t) => (
                    <option key={t.id} value={t.id}>{taskLabel(t)} · {t.status}</option>
                  ))}
                </select>
                <button className="btn btn-secondary" disabled={!selectedId} onClick={() => loadInspect(selectedId)}>
                  <RefreshCw size={15} /> Reload
                </button>
              </div>
            </div>

            {!selectedId ? (
              <div className="panel"><div className="empty">Pick a run from the dropdown or Runs page.</div></div>
            ) : (
              <div className="panel">
                <div className="filters">
                  {(["timeline", "replay", "output"] as const).map((t) => (
                    <button key={t} className={`chip ${inspectTab === t ? "active" : ""}`} onClick={() => setInspectTab(t)}>
                      {t}
                    </button>
                  ))}
                  {trace?.tokens && (
                    <span className="pill" style={{ marginLeft: "auto" }}>
                      tokens {trace.tokens.total_tokens ?? 0}
                      {trace.cost_proxy_usd != null ? ` · ${formatUsd(Number(trace.cost_proxy_usd))}` : ""}
                    </span>
                  )}
                </div>

                {inspectTab === "timeline" && (
                  <div className="timeline">
                    {(trace?.spans || []).map((s: any, i: number, arr: any[]) => (
                      <div className="tl-item" key={s.id}>
                        <div className="tl-rail">
                          <div className="tl-dot" />
                          {i < arr.length - 1 && <div className="tl-line" />}
                        </div>
                        <div className="tl-card">
                          <div className="title">
                            <strong>{s.name}</strong>
                            <span className={`pill ${s.status === "error" ? "bad" : "good"}`}>{s.status}</span>
                          </div>
                          <div className="meta">
                            {s.agent || "system"} · {Math.round(s.duration_ms || 0)}ms · in {s.input_tokens} / out {s.output_tokens}
                          </div>
                          {s.attributes && Object.keys(s.attributes).length > 0 && (
                            <div className="code" style={{ marginTop: 8, maxHeight: 160 }}>
                              {JSON.stringify(s.attributes, null, 2)}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    {!trace?.spans?.length && <div className="empty">No spans yet — wait for the worker or reload.</div>}
                  </div>
                )}

                {inspectTab === "replay" && (
                  <div>
                    <div style={{ color: "var(--muted)", marginBottom: 10, fontSize: "0.85rem" }}>
                      {replay?.turn_count ?? 0} LLM turns · API {API}/v1/replay/{shortId(selectedId)}
                    </div>
                    {(replay?.turns || []).map((turn: any, idx: number) => (
                      <div key={`${turn.ts}-${idx}`} className={`bubble ${idx % 2 ? "assistant" : "user"}`}>
                        <div className="who">
                          #{idx + 1} · {turn.agent} · {turn.provider}/{turn.model} · {turn.ts}
                        </div>
                        <div className="code" style={{ maxHeight: 180 }}>{JSON.stringify(turn.messages, null, 2)}</div>
                        <div className="code" style={{ marginTop: 8, maxHeight: 220 }}>{turn.response}</div>
                      </div>
                    ))}
                    {!replay?.turns?.length && <div className="empty">No transcript yet for this run.</div>}
                  </div>
                )}

                {inspectTab === "output" && selected && (
                  <div>
                    <div className="field">
                      <label>Status</label>
                      <span className={`pill ${statusTone(selected.status)}`}>{selected.status}</span>
                    </div>
                    {selected.error && <div className="field"><label>Error</label><div className="code">{selected.error}</div></div>}
                    <div className="field">
                      <label>Deliverable</label>
                      <div className="code">{selected.deliverable || "—"}</div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {page === "memory" && (
          <>
            <div className="topbar">
              <div>
                <h2>Long-term memory</h2>
                <p>Semantic lessons stored after completed missions (Chroma).</p>
              </div>
              <button className="btn btn-secondary" disabled={refreshing} onClick={refresh}>
                <RefreshCw size={15} className={refreshing ? "spin" : undefined} /> Refresh
              </button>
            </div>
            <div className="list">
              {memories.map((m) => (
                <div className="panel" key={m.id}>
                  <div className="panel-head">
                    <h3>{shortId(m.id)}</h3>
                    <span className="pill">hits {m.metadata?.hit_count ?? 1}</span>
                  </div>
                  <div className="code">{m.document}</div>
                </div>
              ))}
              {!memories.length && <div className="panel"><div className="empty">No memories yet — complete a run first.</div></div>}
            </div>
          </>
        )}

        {page === "agents" && (
          <>
            <div className="topbar">
              <div>
                <h2>Agents</h2>
                <p>
                  Your team of agents — edit prompts, tool allowlists, model overrides, and HITL flags.
                  Technical ids stay stable; display names and instructions are yours.
                </p>
              </div>
              <div className="actions">
                <button className="btn btn-secondary" disabled={agentsBusy} onClick={resetAgents}>Reset defaults</button>
                <button className="btn btn-secondary" disabled={refreshing} onClick={refresh}>
                  <RefreshCw size={15} className={refreshing ? "spin" : undefined} /> Refresh
                </button>
                <button className="btn btn-primary" disabled={agentsBusy || !agentDraft} onClick={saveAgent}>
                  {agentsBusy ? <><Loader2 size={15} className="spin" /> Saving…</> : "Save agent"}
                </button>
              </div>
            </div>

            {agentsMsg && (
              <div className={agentsMsg.startsWith("Saved") || agentsMsg.startsWith("Applied") || agentsMsg.startsWith("Reset") ? "settings-ok" : "alert"}>
                {agentsMsg}
              </div>
            )}

            <div className="panel" style={{ marginBottom: 12 }}>
              <div className="panel-head">
                <h3>Team presets</h3>
                {agentsConfig?.active_preset_id && (
                  <span className="pill good">active: {agentsConfig.active_preset_id}</span>
                )}
              </div>
              <div className="preset-grid">
                {(agentsConfig?.presets || []).map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className={`preset-card ${agentsConfig?.active_preset_id === p.id ? "active" : ""}`}
                    disabled={agentsBusy}
                    onClick={() => applyPreset(p.id)}
                  >
                    <strong>{p.name}</strong>
                    <span>{p.description}</span>
                    <em>{p.builtin ? "built-in" : "custom"} · HITL {p.force_hitl ? "on" : "off"}</em>
                  </button>
                ))}
              </div>
              <div className="preset-save">
                <input
                  placeholder="preset id (e.g. my_team)"
                  value={savePresetId}
                  onChange={(e) => setSavePresetId(e.target.value)}
                />
                <input
                  placeholder="display name"
                  value={savePresetName}
                  onChange={(e) => setSavePresetName(e.target.value)}
                />
                <button className="btn btn-secondary" disabled={agentsBusy} onClick={saveCurrentAsPreset}>
                  Save current as preset
                </button>
              </div>
            </div>

            <div className="agents-layout">
              <div className="panel agents-list">
                <div className="panel-head"><h3>Team</h3></div>
                <div className="list">
                  {(agentsConfig?.agents || []).map((a) => (
                    <button
                      key={a.id}
                      type="button"
                      className={`agent-row ${selectedAgentId === a.id ? "active" : ""}`}
                      onClick={() => selectAgent(a.id)}
                    >
                      <div>
                        <strong>{a.display_name}</strong>
                        <span className="muted"> · {a.id}</span>
                      </div>
                      <div className="agent-row-meta">
                        <span className="pill">{a.kind}</span>
                        {a.requires_hitl && <span className="pill warn">HITL</span>}
                        {!a.enabled && <span className="pill bad">off</span>}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="panel">
                {!agentDraft ? (
                  <div className="empty">Select an agent</div>
                ) : (
                  <>
                    <div className="panel-head">
                      <h3>{agentDraft.display_name}</h3>
                      <span className="pill muted">{agentDraft.id}</span>
                    </div>
                    <div className="field">
                      <label>Display name</label>
                      <input
                        value={agentDraft.display_name}
                        onChange={(e) => setAgentDraft({ ...agentDraft, display_name: e.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label>Instructions (persona / style)</label>
                      <PromptInput
                        value={agentDraft.instructions}
                        onChange={(v) => setAgentDraft({ ...agentDraft, instructions: v })}
                        minRows={5}
                        maxHeight={220}
                      />
                    </div>
                    <div className="field">
                      <label>Output contract</label>
                      <input
                        value={agentDraft.output_contract}
                        onChange={(e) => setAgentDraft({ ...agentDraft, output_contract: e.target.value })}
                        placeholder="e.g. Always 5 bullets with sources"
                      />
                    </div>
                    <div className="field">
                      <label>Model override (blank = Settings default)</label>
                      <input
                        value={agentDraft.model}
                        onChange={(e) => setAgentDraft({ ...agentDraft, model: e.target.value })}
                        placeholder="e.g. qwen2.5:3b or gpt-4o-mini"
                      />
                    </div>
                    {agentDraft.kind === "specialist" && (
                      <div className="field">
                        <label>Tool allowlist</label>
                        <div className="tool-checks">
                          {(agentsConfig?.available_tools || []).map((t) => (
                              <label key={t} className="check tool-check">
                                <input
                                  type="checkbox"
                                  checked={agentDraft.tools.includes(t)}
                                  onChange={() => toggleAgentTool(t)}
                                />
                                <span>{t}</span>
                              </label>
                            ))}
                        </div>
                        <p className="muted">Registered MCP tools are also appended at runtime when available.</p>
                      </div>
                    )}
                    <div className="agents-flags">
                      <label className="check">
                        <input
                          type="checkbox"
                          checked={agentDraft.requires_hitl}
                          onChange={(e) => setAgentDraft({ ...agentDraft, requires_hitl: e.target.checked })}
                        />
                        <span>Requires HITL (marks work sensitive / gates final)</span>
                      </label>
                      <label className="check">
                        <input
                          type="checkbox"
                          checked={agentDraft.enabled}
                          onChange={(e) => setAgentDraft({ ...agentDraft, enabled: e.target.checked })}
                        />
                        <span>Enabled</span>
                      </label>
                    </div>
                  </>
                )}
              </div>
            </div>
          </>
        )}

        {page === "connectors" && (
          <>
            <div className="topbar">
              <div>
                <h2>Connectors</h2>
                <p>
                  Plug in apps people actually use. Agents get real tools; write actions pause for your approval in Approvals.
                </p>
              </div>
              <div className="actions">
                <button className="btn btn-secondary" disabled={connectorsBusy} onClick={reloadMcpConnectors}>
                  <RefreshCw size={15} /> Reload
                </button>
              </div>
            </div>

            {connectorsMsg && (
              <div className={connectorsMsg.startsWith("Connected") || connectorsMsg.startsWith("Reloaded") || connectorsMsg.startsWith("Disconnected") || connectorsMsg.startsWith("Saved") ? "settings-ok" : "alert"}>
                {connectorsMsg}
              </div>
            )}

            <div className="panel" style={{ marginBottom: 12 }}>
              <div className="panel-head">
                <h3>App connectors</h3>
                <span className="pill">{(connectors?.catalog || []).filter((c: any) => c.connected).length} connected</span>
              </div>
              <div className="connector-grid">
                {(connectors?.catalog || []).map((c: any) => (
                  <div key={c.id} className={`connector-card ${c.connected ? "connected" : ""}`}>
                    <div className="connector-card-head">
                      <div>
                        <strong>{c.name}</strong>
                        <span className="muted"> · {c.category}</span>
                      </div>
                      <span className={`pill ${c.connected ? "good" : "muted"}`}>
                        {c.connected ? "connected" : "off"}
                      </span>
                    </div>
                    <p>{c.description}</p>
                    <div className="connector-caps">
                      {(c.capabilities || []).map((cap: string) => (
                        <span key={cap} className="chip">{cap}</span>
                      ))}
                    </div>
                    {c.hitl_writes && (
                      <p className="muted" style={{ marginTop: 8 }}>Writes require HITL approval before they run.</p>
                    )}
                    <div className="actions" style={{ marginTop: 10 }}>
                      {c.id === "github" && c.connected && (
                        <span className="pill good connected-pill">
                          Connected{c.config?.GITHUB_DEFAULT_OWNER ? ` · ${c.config.GITHUB_DEFAULT_OWNER}` : ""}
                        </span>
                      )}
                      {c.id === "github" && !c.connected && (
                        <button
                          className="btn btn-primary"
                          type="button"
                          disabled={connectorsBusy || !connectors?.github_oauth?.configured}
                          onClick={() => {
                            if (connectors?.github_oauth?.configured) connectGithubOAuth();
                            else setExpandedConnector("github");
                          }}
                        >
                          Connect with GitHub
                        </button>
                      )}
                      <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={() => setExpandedConnector(expandedConnector === c.id ? null : c.id)}
                      >
                        {expandedConnector === c.id
                          ? "Hide"
                          : c.id === "github"
                            ? c.connected
                              ? "Manage"
                              : "Setup"
                            : c.connected
                              ? "Update"
                              : "Connect"}
                      </button>
                      {c.connected && (
                        <button
                          className="btn btn-secondary"
                          type="button"
                          disabled={connectorsBusy}
                          onClick={() => disableAppConnector(c.id)}
                        >
                          Disconnect
                        </button>
                      )}
                      {c.docs_url && (
                        <a className="btn btn-secondary" href={c.docs_url} target="_blank" rel="noreferrer">
                          Docs
                        </a>
                      )}
                    </div>
                    {expandedConnector === c.id && c.id === "github" && (
                      <div className="connector-form">
                        {c.connected ? (
                          <p className="muted" style={{ marginBottom: 10 }}>
                            GitHub is linked
                            {c.config?.GITHUB_DEFAULT_OWNER ? ` as ${c.config.GITHUB_DEFAULT_OWNER}` : ""}.
                            Re-authorize only if you need fresh scopes, or update the OAuth App credentials below.
                          </p>
                        ) : (
                          <>
                            <p className="muted" style={{ marginBottom: 10 }}>
                              One-time: create a GitHub OAuth App, then Connect with GitHub opens GitHub’s consent screen.
                            </p>
                            <ol className="oauth-steps">
                              <li>
                                Open{" "}
                                <a href={connectors?.github_oauth?.create_app_url || "https://github.com/settings/applications/new"} target="_blank" rel="noreferrer">
                                  New OAuth App
                                </a>
                              </li>
                              <li>Homepage URL: <code>{connectors?.github_oauth?.frontend_url || "http://127.0.0.1:5173"}</code></li>
                              <li>
                                Authorization callback URL:{" "}
                                <code>{connectors?.github_oauth?.authorize_callback_url || "http://127.0.0.1:8000/oauth/github/callback"}</code>
                              </li>
                              <li>Paste Client ID + Client Secret below and save</li>
                            </ol>
                          </>
                        )}
                        <div className="field">
                          <label>
                            Client ID
                            {connectors?.github_oauth?.client_id_masked
                              ? ` (saved: ${connectors.github_oauth.client_id_masked})`
                              : ""}
                          </label>
                          <input
                            value={oauthClientId}
                            onChange={(e) => setOauthClientId(e.target.value)}
                            placeholder={connectors?.github_oauth?.client_id_set ? "Leave blank to keep" : "Ov23…"}
                          />
                        </div>
                        <div className="field">
                          <label>Client secret {connectors?.github_oauth?.client_secret_set ? "(saved)" : ""}</label>
                          <input
                            type="password"
                            value={oauthClientSecret}
                            onChange={(e) => setOauthClientSecret(e.target.value)}
                            placeholder={connectors?.github_oauth?.client_secret_set ? "Leave blank to keep" : "••••••••"}
                          />
                        </div>
                        <div className="field">
                          <label>Default owner / org (optional)</label>
                          <input
                            placeholder="your-username"
                            value={(connectorConfigDrafts.github || {}).GITHUB_DEFAULT_OWNER ?? c.config?.GITHUB_DEFAULT_OWNER ?? ""}
                            onChange={(e) => patchConnectorConfig("github", "GITHUB_DEFAULT_OWNER", e.target.value)}
                          />
                        </div>
                        <div className="actions">
                          <button className="btn btn-secondary" type="button" disabled={connectorsBusy} onClick={saveGithubOauthApp}>
                            Save OAuth App
                          </button>
                          <button
                            className="btn btn-primary"
                            type="button"
                            disabled={connectorsBusy || !connectors?.github_oauth?.configured}
                            onClick={connectGithubOAuth}
                          >
                            {c.connected ? "Re-authorize GitHub" : "Connect with GitHub"}
                          </button>
                        </div>
                        <details style={{ marginTop: 14 }}>
                          <summary className="muted">Advanced: paste a personal access token instead</summary>
                          {(c.secret_fields || []).map((f: any) => (
                            <div className="field" key={f.key} style={{ marginTop: 10 }}>
                              <label>
                                {f.label}
                                {c.secrets_masked?.[f.key] ? ` (saved: ${c.secrets_masked[f.key]})` : ""}
                              </label>
                              <input
                                type="password"
                                placeholder={c.secrets_set?.[f.key] ? "Leave blank to keep current" : f.placeholder}
                                value={(connectorDrafts[c.id] || {})[f.key] || ""}
                                onChange={(e) => patchConnectorSecret(c.id, f.key, e.target.value)}
                              />
                            </div>
                          ))}
                          <button
                            className="btn btn-secondary"
                            type="button"
                            disabled={connectorsBusy}
                            onClick={() => enableAppConnector(c.id)}
                            style={{ marginTop: 8 }}
                          >
                            Enable with PAT
                          </button>
                        </details>
                      </div>
                    )}
                    {expandedConnector === c.id && c.id !== "github" && (
                      <div className="connector-form">
                        {(c.secret_fields || []).map((f: any) => (
                          <div className="field" key={f.key}>
                            <label>
                              {f.label}
                              {c.secrets_masked?.[f.key] ? ` (saved: ${c.secrets_masked[f.key]})` : ""}
                            </label>
                            <input
                              type="password"
                              placeholder={c.secrets_set?.[f.key] ? "Leave blank to keep current" : f.placeholder}
                              value={(connectorDrafts[c.id] || {})[f.key] || ""}
                              onChange={(e) => patchConnectorSecret(c.id, f.key, e.target.value)}
                            />
                            {f.help && <p className="muted">{f.help}</p>}
                          </div>
                        ))}
                        {(c.config_fields || []).map((f: any) => (
                          <div className="field" key={f.key}>
                            <label>{f.label}</label>
                            <input
                              placeholder={f.placeholder}
                              value={(connectorConfigDrafts[c.id] || {})[f.key] ?? c.config?.[f.key] ?? ""}
                              onChange={(e) => patchConnectorConfig(c.id, f.key, e.target.value)}
                            />
                            {f.help && <p className="muted">{f.help}</p>}
                          </div>
                        ))}
                        <button
                          className="btn btn-primary"
                          type="button"
                          disabled={connectorsBusy}
                          onClick={() => enableAppConnector(c.id)}
                        >
                          {connectorsBusy ? "Working…" : c.connected ? "Save & reload" : "Enable connector"}
                        </button>
                      </div>
                    )}
                  </div>
                ))}
                {!connectors?.catalog?.length && (
                  <div className="empty">Catalog loading… Restart the API if this stays empty.</div>
                )}
              </div>
            </div>

            <div className="grid-2">
              <div className="panel">
                <div className="panel-head">
                  <h3>Built-in tools</h3>
                  <span className="pill good">{(connectors?.builtins || []).length}</span>
                </div>
                <div className="list">
                  {(connectors?.builtins || []).map((t: any) => (
                    <div className="run-item" key={t.name} style={{ cursor: "default" }}>
                      <div className="run-meta">
                        <span className="id">{t.name}</span>
                        <span className="pill good">on</span>
                      </div>
                      <div className="prompt">{t.description}</div>
                    </div>
                  ))}
                  {!connectors?.builtins?.length && <div className="empty">Loading…</div>}
                </div>
                <div className="settings-active" style={{ marginTop: 12 }}>
                  Code sandbox: <strong>{connectors?.code_sandbox || health?.code_sandbox || "local"}</strong>
                </div>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h3>Advanced · raw MCP JSON</h3>
                  <span className={`pill ${mcpEnabled ? "good" : "muted"}`}>{mcpEnabled ? "enabled" : "off"}</span>
                </div>
                <label className="check">
                  <input type="checkbox" checked={mcpEnabled} onChange={(e) => setMcpEnabled(e.target.checked)} />
                  <span>Enable MCP tool bridge for agents</span>
                </label>
                <div className="field">
                  <label>Servers JSON (stdio MCP)</label>
                  <textarea
                    value={mcpServersJson}
                    onChange={(e) => setMcpServersJson(e.target.value)}
                    style={{ minHeight: 140, fontFamily: "var(--mono)" }}
                  />
                </div>
                <div className="actions">
                  <button className="btn btn-primary" disabled={connectorsBusy} onClick={saveMcpConnectors}>
                    {connectorsBusy ? "Saving…" : "Save MCP JSON"}
                  </button>
                </div>
              </div>
            </div>

            <div className="panel" style={{ marginTop: 14 }}>
              <div className="panel-head">
                <h3>Live MCP tools</h3>
                <span className="pill">{(connectors?.mcp?.registered_tools || []).length} tools</span>
              </div>
              <div className="list">
                {(connectors?.mcp?.servers || []).map((s: any) => (
                  <div className="run-item" key={s.name} style={{ cursor: "default" }}>
                    <div className="run-meta">
                      <span className="id">{s.name}</span>
                      <span className={`pill ${s.ok ? "good" : "bad"}`}>{s.ok ? "connected" : "error"}</span>
                    </div>
                    <div className="prompt">
                      {s.ok
                        ? `${(s.tools || []).length} tools · ${(s.tools || []).map((t: any) => t.name).join(", ") || "none"}`
                        : s.error || "Failed to connect"}
                    </div>
                  </div>
                ))}
                {!connectors?.mcp?.servers?.length && (
                  <div className="empty">Enable an app connector above, then Reload.</div>
                )}
              </div>
              {(connectors?.mcp?.registered_tools || []).length > 0 && (
                <div className="settings-active">
                  {(connectors.mcp.registered_tools as any[]).map((t) => (
                    <span key={t.name} className="pill" style={{ marginRight: 6, marginBottom: 6, display: "inline-block" }}>
                      {t.name}{t.requires_approval ? " · HITL" : ""}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {page === "settings" && (
          <>
            <div className="topbar">
              <div>
                <h2>LLM provider</h2>
                <p>Pick a provider, choose models, and paste your own API key. Keys stay in local Redis — never returned in full.</p>
              </div>
              <div className="actions">
                <button className="btn btn-secondary" disabled={settingsBusy} onClick={testLlmSettings}>Test</button>
                <button className="btn btn-primary" disabled={settingsBusy || !llmSettings} onClick={saveLlmSettings}>
                  {settingsBusy ? "Saving…" : "Save"}
                </button>
              </div>
            </div>

            {!llmSettings ? (
              <div className="panel"><div className="empty">Loading settings…</div></div>
            ) : (
              <div className="panel settings-panel">
                <div className="field">
                  <label>Provider</label>
                  <select
                    value={llmSettings.llm_provider}
                    onChange={(e) => onProviderChange(e.target.value)}
                  >
                    {Object.entries(llmSettings.presets).map(([id, p]) => (
                      <option key={id} value={id}>{p.label}</option>
                    ))}
                  </select>
                </div>

                {llmSettings.presets[llmSettings.llm_provider]?.note && (
                  <p className="hint">{llmSettings.presets[llmSettings.llm_provider].note}</p>
                )}

                {llmSettings.llm_provider === "ollama" && (
                  <>
                    <div className="field">
                      <label>Ollama host</label>
                      <input
                        value={llmSettings.ollama_host}
                        onChange={(e) => patchSettings({ ollama_host: e.target.value })}
                      />
                    </div>
                    <div className="grid-2">
                      <ModelSelect
                        label="Supervisor model"
                        value={llmSettings.supervisor_model}
                        options={mergeOpts(llmSettings.presets.ollama?.supervisor_models, health?.llm?.models)}
                        onChange={(v) => patchSettings({ supervisor_model: v })}
                      />
                      <ModelSelect
                        label="Specialist model"
                        value={llmSettings.specialist_model}
                        options={mergeOpts(llmSettings.presets.ollama?.specialist_models, health?.llm?.models)}
                        onChange={(v) => patchSettings({ specialist_model: v })}
                      />
                    </div>
                    <ModelSelect
                      label="Embed model"
                      value={llmSettings.embed_model}
                      options={llmSettings.presets.ollama?.embed_models || []}
                      onChange={(v) => patchSettings({ embed_model: v })}
                    />
                  </>
                )}

                {llmSettings.llm_provider === "openai" && (
                  <>
                    <div className="field">
                      <label>OpenAI API key {llmSettings.openai_api_key_set ? `(saved: ${llmSettings.openai_api_key_masked})` : ""}</label>
                      <input
                        type="password"
                        autoComplete="off"
                        placeholder={llmSettings.openai_api_key_set ? "Leave blank to keep current key" : "sk-..."}
                        value={openaiKeyDraft}
                        onChange={(e) => setOpenaiKeyDraft(e.target.value)}
                      />
                    </div>
                    <div className="field">
                      <label>Base URL</label>
                      <input
                        value={llmSettings.openai_base_url}
                        onChange={(e) => patchSettings({ openai_base_url: e.target.value })}
                      />
                    </div>
                    <div className="grid-2">
                      <ModelSelect
                        label="Supervisor model"
                        value={llmSettings.openai_supervisor_model}
                        options={llmSettings.presets.openai?.supervisor_models || []}
                        onChange={(v) => patchSettings({ openai_supervisor_model: v })}
                      />
                      <ModelSelect
                        label="Specialist model"
                        value={llmSettings.openai_specialist_model}
                        options={llmSettings.presets.openai?.specialist_models || []}
                        onChange={(v) => patchSettings({ openai_specialist_model: v })}
                      />
                    </div>
                    <ModelSelect
                      label="Embed model"
                      value={llmSettings.openai_embed_model}
                      options={llmSettings.presets.openai?.embed_models || []}
                      onChange={(v) => patchSettings({ openai_embed_model: v })}
                    />
                  </>
                )}

                {llmSettings.llm_provider === "anthropic" && (
                  <>
                    <div className="field">
                      <label>Anthropic API key {llmSettings.anthropic_api_key_set ? `(saved: ${llmSettings.anthropic_api_key_masked})` : ""}</label>
                      <input
                        type="password"
                        autoComplete="off"
                        placeholder={llmSettings.anthropic_api_key_set ? "Leave blank to keep current key" : "sk-ant-..."}
                        value={anthropicKeyDraft}
                        onChange={(e) => setAnthropicKeyDraft(e.target.value)}
                      />
                    </div>
                    <div className="grid-2">
                      <ModelSelect
                        label="Supervisor model"
                        value={llmSettings.anthropic_supervisor_model}
                        options={llmSettings.presets.anthropic?.supervisor_models || []}
                        onChange={(v) => patchSettings({ anthropic_supervisor_model: v })}
                      />
                      <ModelSelect
                        label="Specialist model"
                        value={llmSettings.anthropic_specialist_model}
                        options={llmSettings.presets.anthropic?.specialist_models || []}
                        onChange={(v) => patchSettings({ anthropic_specialist_model: v })}
                      />
                    </div>
                  </>
                )}

                {llmSettings.llm_provider === "stub" && (
                  <div className="empty">Stub mode returns canned responses — no API key or GPU needed.</div>
                )}

                <div className="settings-active">
                  Active: <strong>{llmSettings.active_chat_models.supervisor}</strong> (supervisor) ·{" "}
                  <strong>{llmSettings.active_chat_models.specialist}</strong> (specialist) ·{" "}
                  <strong>{llmSettings.active_chat_models.embed}</strong> (embed)
                </div>

                {settingsMsg && <div className={settingsMsg.startsWith("Connected") || settingsMsg.startsWith("Saved") ? "settings-ok" : "alert"}>{settingsMsg}</div>}
              </div>
            )}

            <div className="panel settings-panel" style={{ marginTop: 16 }}>
              <h3 style={{ marginTop: 0 }}>Access &amp; actor</h3>
              <p className="hint">
                Set <code>ORCHESTRATOR_API_TOKEN</code> on the server to require a key.
                {health?.auth_required ? " Auth is currently required." : " Auth is currently open (no server token)."}
              </p>
              <div className="grid-2">
                <div className="field">
                  <label>Your display name (X-Actor)</label>
                  <input value={actorDraft} onChange={(e) => setActorDraft(e.target.value)} placeholder="operator" />
                </div>
                <div className="field">
                  <label>API token (sent as X-API-Key)</label>
                  <input
                    type="password"
                    autoComplete="off"
                    value={apiTokenDraft}
                    onChange={(e) => setApiTokenDraft(e.target.value)}
                    placeholder={health?.auth_required ? "required" : "optional"}
                  />
                </div>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setActor(actorDraft);
                  setApiToken(apiTokenDraft);
                  setSettingsMsg("Access settings saved in this browser.");
                  refresh();
                }}
              >
                Save access settings
              </button>
            </div>

            <div className="panel" style={{ marginTop: 16 }}>
              <div className="panel-head">
                <h3>Cost rollup</h3>
                <span className="pill">{formatUsd(costs?.total_cost_usd)}</span>
              </div>
              <p className="hint">{costs?.note || "Estimated from transcript tokens × price sheet."}</p>
              <div className="list">
                {(costs?.tasks || []).slice(0, 8).map((row) => (
                  <div className="run-item" key={row.task_id} onClick={() => { setSelectedId(row.task_id); setPage("inspect"); }}>
                    <div>
                      <strong>{shortId(row.task_id)}</strong>
                      <div className="muted">{preview(row.prompt_preview, 80)}</div>
                    </div>
                    <div className="muted">{formatUsd(row.cost_usd)} · {row.total_tokens} tok</div>
                  </div>
                ))}
                {!costs?.tasks?.length && <div className="empty">No cost data yet.</div>}
              </div>
            </div>

            <div className="panel" style={{ marginTop: 16 }}>
              <div className="panel-head">
                <h3>Audit log</h3>
                <span className="pill">{auditEvents.length}</span>
              </div>
              <div className="list">
                {auditEvents.slice(0, 12).map((ev) => (
                  <div className="run-item" key={ev.id}>
                    <div>
                      <strong>{ev.action}</strong>
                      <div className="muted">{ev.actor} · {ev.task_id ? shortId(ev.task_id) : "—"} · {ev.created_at}</div>
                    </div>
                    <span className="pill">{ev.resource_type || "event"}</span>
                  </div>
                ))}
                {!auditEvents.length && <div className="empty">No audit events yet.</div>}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function mergeOpts(presets: string[] = [], live?: string[]) {
  return Array.from(new Set([...(presets || []), ...(live || []).filter(Boolean)]));
}

function ModelSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  const opts = value && !options.includes(value) ? [value, ...options] : options;
  return (
    <div className="field">
      <label>{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {opts.map((m) => (
          <option key={m} value={m}>{m}</option>
        ))}
      </select>
      <input
        className="model-custom"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Or type a custom model id"
      />
    </div>
  );
}

function PromptInput({
  value,
  onChange,
  disabled,
  minRows = 4,
  maxHeight = 280,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  minRows?: number;
  maxHeight?: number;
  placeholder?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    const next = Math.min(el.scrollHeight, maxHeight);
    el.style.height = `${Math.max(next, minRows * 22)}px`;
  }, [value, maxHeight, minRows]);
  return (
    <textarea
      ref={ref}
      className="prompt-input"
      rows={minRows}
      value={value}
      disabled={disabled}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

function HealthLine({ label, on }: { label: string; on: boolean }) {
  return (
    <div className="health-row">
      <span><span className={`dot ${on ? "on" : "off"}`} />{label}</span>
      <span>{on ? "up" : "down"}</span>
    </div>
  );
}
