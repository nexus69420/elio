import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  CheckCircle2,
  ExternalLink,
  Brain,
  GitBranch,
  LayoutDashboard,
  ListTodo,
  Play,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import {
  API,
  Approval,
  Health,
  Task,
  api,
  preview,
  shortId,
  statusTone,
} from "./api";

const DEFAULT_PROMPT =
  "Research the tradeoffs of running multi-agent LLM systems fully locally versus paid cloud APIs. Analyze cost, latency, quality, and privacy. Write a short executive brief with a recommendation.";

type Page = "overview" | "runs" | "approvals" | "inspect" | "memory";

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
  const [error, setError] = useState("");
  const [trace, setTrace] = useState<any>(null);
  const [replay, setReplay] = useState<any>(null);
  const [inspectTab, setInspectTab] = useState<"timeline" | "replay" | "output">("timeline");
  const [modifyText, setModifyText] = useState<Record<string, string>>({});
  const [takeoverText, setTakeoverText] = useState<Record<string, string>>({});

  const selected = useMemo(
    () => tasks.find((t) => t.id === selectedId) || null,
    [tasks, selectedId]
  );

  const stats = useMemo(() => {
    const completed = tasks.filter((t) => t.status === "completed").length;
    const failed = tasks.filter((t) => t.status === "failed" || t.status === "rejected").length;
    const active = tasks.filter((t) =>
      ["queued", "planning", "executing", "reviewing", "synthesizing", "awaiting_approval"].includes(t.status)
    ).length;
    return { completed, failed, active, approvals: approvals.length };
  }, [tasks, approvals]);

  const filtered = useMemo(() => {
    if (filter === "all") return tasks;
    if (filter === "active") {
      return tasks.filter((t) =>
        ["queued", "planning", "executing", "reviewing", "synthesizing", "awaiting_approval"].includes(t.status)
      );
    }
    return tasks.filter((t) => t.status === filter);
  }, [tasks, filter]);

  async function refresh() {
    try {
      setError("");
      const [h, t, a, m] = await Promise.all([
        api<Health>("/health"),
        api<Task[]>("/v1/tasks"),
        api<Approval[]>("/v1/approvals"),
        api<any[]>("/v1/memory"),
      ]);
      setHealth(h);
      setTasks(t);
      setApprovals(a);
      setMemories(m);
      if (!selectedId && t[0]) setSelectedId(t[0].id);
    } catch (e: any) {
      setError(String(e.message || e));
    }
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3500);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!selectedId || page !== "inspect") return;
    loadInspect(selectedId);
  }, [selectedId, page]);

  async function runTask() {
    setBusy(true);
    try {
      const task = await api<Task>("/v1/tasks", {
        method: "POST",
        body: JSON.stringify({ prompt, force_hitl: forceHitl }),
      });
      setSelectedId(task.id);
      setPage(forceHitl ? "approvals" : "runs");
      await refresh();
    } catch (e: any) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function resolve(id: string, action: string, extra: Record<string, string> = {}) {
    await api(`/v1/approvals/${id}`, {
      method: "POST",
      body: JSON.stringify({ action, note: "mission-control", ...extra }),
    });
    await refresh();
  }

  async function loadInspect(taskId: string) {
    try {
      const [tr, rp] = await Promise.all([
        api(`/v1/traces/${taskId}`),
        api(`/v1/replay/${taskId}`),
      ]);
      setTrace(tr);
      setReplay(rp);
    } catch (e: any) {
      setError(String(e.message || e));
    }
  }

  const nav = [
    { id: "overview" as Page, label: "Overview", icon: LayoutDashboard },
    { id: "runs" as Page, label: "Runs", icon: ListTodo, count: tasks.length },
    { id: "approvals" as Page, label: "Approvals", icon: ShieldAlert, count: approvals.length, hot: approvals.length > 0 },
    { id: "inspect" as Page, label: "Inspect", icon: GitBranch },
    { id: "memory" as Page, label: "Memory", icon: Brain, count: memories.length },
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
          <div className="health-row">
            <span>MCP tools</span>
            <span>{(health?.mcp_tools || []).length}</span>
          </div>
        </div>
      </aside>

      <main className="main">
        {error && <div className="alert">{error}</div>}

        {page === "overview" && (
          <>
            <div className="topbar">
              <div>
                <h2>Operations overview</h2>
                <p>Dispatch missions, gate sensitive steps with HITL, and inspect agent timelines — LangSmith/Langfuse-style control plane for your local stack.</p>
              </div>
              <div className="actions">
                <button className="btn btn-secondary" onClick={refresh}><RefreshCw size={15} /> Refresh</button>
                <button className="btn btn-primary" onClick={() => setPage("runs")}><Sparkles size={15} /> New run</button>
              </div>
            </div>

            <div className="kpi-grid">
              <div className="kpi"><div className="label">Active</div><div className="value">{stats.active}</div><div className="sub">in-flight</div></div>
              <div className="kpi"><div className="label">Pending approvals</div><div className="value">{stats.approvals}</div><div className="sub">HITL queue</div></div>
              <div className="kpi"><div className="label">Completed</div><div className="value">{stats.completed}</div><div className="sub">successful</div></div>
              <div className="kpi"><div className="label">Failed</div><div className="value">{stats.failed}</div><div className="sub">need debug</div></div>
            </div>

            <div className="grid-2">
              <div className="panel">
                <div className="panel-head">
                  <h3>Dispatch mission</h3>
                </div>
                <div className="field">
                  <label>Prompt</label>
                  <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} />
                </div>
                <label className="check">
                  <input type="checkbox" checked={forceHitl} onChange={(e) => setForceHitl(e.target.checked)} />
                  Force human approval before final deliverable
                </label>
                <div className="actions" style={{ marginTop: 14 }}>
                  <button className="btn btn-primary" disabled={busy} onClick={runTask}>
                    <Play size={15} /> {busy ? "Queuing…" : "Run via Celery"}
                  </button>
                </div>
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
                <button className="btn btn-secondary" onClick={refresh}><RefreshCw size={15} /> Refresh</button>
              </div>
            </div>

            <div className="grid-runs">
              <div className="panel">
                <div className="panel-head"><h3>Dispatch</h3></div>
                <div className="field">
                  <label>Prompt</label>
                  <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} />
                </div>
                <label className="check">
                  <input type="checkbox" checked={forceHitl} onChange={(e) => setForceHitl(e.target.checked)} />
                  Force HITL
                </label>
                <div className="actions" style={{ marginTop: 12 }}>
                  <button className="btn btn-primary" disabled={busy} onClick={runTask}>
                    <Play size={15} /> {busy ? "Queuing…" : "Run"}
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
                        <span className="id">{shortId(t.id)}</span>
                        <span className={`pill ${statusTone(t.status)}`}>{t.status}</span>
                      </div>
                      <div className="prompt">{preview(t.prompt)}</div>
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
                      <h3>{shortId(selected.id)}</h3>
                      <span className={`pill ${statusTone(selected.status)}`}>{selected.status}</span>
                    </div>
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
              <button className="btn btn-secondary" onClick={refresh}><RefreshCw size={15} /> Refresh</button>
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
                    <button className="btn btn-primary" onClick={() => resolve(item.id, "approve")}>
                      <CheckCircle2 size={15} /> Approve
                    </button>
                    <button className="btn btn-danger" onClick={() => resolve(item.id, "reject")}>Reject</button>
                  </div>
                  <div className="field" style={{ marginTop: 12 }}>
                    <label>Modify deliverable</label>
                    <textarea
                      value={modifyText[item.id] || ""}
                      onChange={(e) => setModifyText({ ...modifyText, [item.id]: e.target.value })}
                    />
                    <button
                      className="btn btn-ghost btn-sm"
                      style={{ marginTop: 8 }}
                      onClick={() => resolve(item.id, "modify", { modified_action: modifyText[item.id] || "" })}
                    >
                      Modify & approve
                    </button>
                  </div>
                  <div className="field">
                    <label>Take over</label>
                    <textarea
                      value={takeoverText[item.id] || ""}
                      onChange={(e) => setTakeoverText({ ...takeoverText, [item.id]: e.target.value })}
                    />
                    <button
                      className="btn btn-secondary btn-sm"
                      style={{ marginTop: 8 }}
                      onClick={() => resolve(item.id, "take_over", { human_output: takeoverText[item.id] || "" })}
                    >
                      Take over
                    </button>
                  </div>
                </div>
              ))}
              {!approvals.length && (
                <div className="panel">
                  <div className="empty">
                    No pending approvals. If a run never reaches HITL, open <strong>Runs</strong> —
                    failed tasks (e.g. memory/embed errors) never enter this queue.
                  </div>
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
                    <option key={t.id} value={t.id}>{shortId(t.id)} · {t.status}</option>
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
              <button className="btn btn-secondary" onClick={refresh}><RefreshCw size={15} /> Refresh</button>
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
      </main>
    </div>
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
