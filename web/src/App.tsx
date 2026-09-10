import {
  Bot,
  ChevronDown,
  ChevronRight,
  Filter,
  ListTodo,
  Moon,
  Plus,
  Plug,
  Settings,
  RefreshCw,
  Search,
  Sun,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { statusTone, taskLabel } from "./api";
import { AgentsPage } from "./pages/AgentsPage";
import { ChatPage } from "./pages/ChatPage";
import { ConnectionsPage } from "./pages/ConnectionsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TasksPage } from "./pages/TasksPage";
import { useWorkspace, WorkspaceProvider } from "./workspace/WorkspaceContext";

/** Cursor-style sidebar toggle: panel frame + chevron (left = collapse, right = expand). */
function SidebarToggleIcon({ direction }: { direction: "left" | "right" }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="1.75" y="2.25" width="12.5" height="11.5" rx="2" stroke="currentColor" strokeWidth="1.4" />
      <path d="M6.25 2.25v11.5" stroke="currentColor" strokeWidth="1.4" />
      {direction === "left" ? (
        <path
          d="M11.1 5.6L8.75 8l2.35 2.4"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ) : (
        <path
          d="M8.4 5.6L10.75 8 8.4 10.4"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
    </svg>
  );
}

function timeAgo(iso?: string) {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const mins = Math.max(0, Math.round((Date.now() - t) / 60000));
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hrs = Math.round(mins / 60);
  if (hrs < 48) return `${hrs}h`;
  return `${Math.round(hrs / 24)}d`;
}

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    try {
      const saved = localStorage.getItem("elio_theme");
      if (saved === "light" || saved === "dark") return saved;
    } catch {
      /* ignore */
    }
    return "dark";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("elio_theme", theme);
  }, [theme]);

  return { theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) };
}

function Sidebar({
  collapsed,
  setCollapsed,
}: {
  collapsed: boolean;
  setCollapsed: (v: boolean) => void;
}) {
  const {
    page,
    setPage,
    approvals,
    tasks,
    selectedId,
    setSelectedId,
    connectedCount,
    health,
    refresh,
    refreshing,
    actorDraft,
    connectors,
  } = useWorkspace();
  const { theme, toggle } = useTheme();
  const [query, setQuery] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const [chatsOpen, setChatsOpen] = useState(true);

  const history = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return tasks.slice(0, 60);
    return tasks.filter((t) => (t.title || t.prompt || t.id).toLowerCase().includes(q)).slice(0, 60);
  }, [tasks, query]);

  const online = !!health?.ok;
  const githubConnected = !!(connectors?.catalog || []).find((c: any) => c.id === "github" && c.connected);

  function openNewChat() {
    setSelectedId("");
    setPage("chat");
  }

  const ICON = 16;

  return (
    <aside className={`sb ${collapsed ? "collapsed" : ""}`}>
      <div className="sb-chrome">
        <div
          className="sb-brand"
          onClick={openNewChat}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter") openNewChat();
          }}
        >
          <strong>Elio</strong>
        </div>
        <div className="sb-chrome-actions">
          <button
            type="button"
            className="sb-mini"
            title="Search"
            onClick={() => {
              if (collapsed) setCollapsed(false);
              setShowSearch((v) => !v);
            }}
          >
            <Search size={15} />
          </button>
          <button
            type="button"
            className="sb-mini sb-toggle"
            onClick={() => setCollapsed(!collapsed)}
            title={collapsed ? "Show sidebar" : "Hide sidebar"}
          >
            <SidebarToggleIcon direction={collapsed ? "right" : "left"} />
          </button>
        </div>
      </div>

      <div className="sb-top">
        <button type="button" className="sb-nav" onClick={openNewChat} title="New chat">
          <span className="sb-ico-slot">
            <Plus size={ICON} strokeWidth={1.75} />
          </span>
          <span className="sb-label">New chat</span>
        </button>
        <button
          type="button"
          className={`sb-nav ${page === "connections" ? "on" : ""}`}
          title="Connections"
          onClick={() => setPage("connections")}
        >
          <span className="sb-ico-slot">
            <Plug size={ICON} strokeWidth={1.75} />
          </span>
          <span className="sb-label">Connections</span>
          {connectedCount > 0 && <span className="sb-badge">{connectedCount}</span>}
        </button>
        <button
          type="button"
          className={`sb-nav ${page === "tasks" ? "on" : ""}`}
          title="Tasks"
          onClick={() => setPage("tasks")}
        >
          <span className="sb-ico-slot">
            <ListTodo size={ICON} strokeWidth={1.75} />
          </span>
          <span className="sb-label">Tasks</span>
        </button>
        <button
          type="button"
          className={`sb-nav ${page === "agents" ? "on" : ""}`}
          title="Agents"
          onClick={() => setPage("agents")}
        >
          <span className="sb-ico-slot">
            <Bot size={ICON} strokeWidth={1.75} />
          </span>
          <span className="sb-label">Agents</span>
        </button>
        <button
          type="button"
          className={`sb-nav ${page === "settings" ? "on" : ""}`}
          title="Customize"
          onClick={() => setPage("settings")}
        >
          <span className="sb-ico-slot">
            <Settings size={ICON} strokeWidth={1.75} />
          </span>
          <span className="sb-label">Customize</span>
        </button>
      </div>

      {showSearch && !collapsed && (
        <div className="sb-search">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats…"
            autoFocus
          />
        </div>
      )}

      <div className="sb-section">
        <div className="sb-section-head">
          <button type="button" className="sb-section-toggle" onClick={() => setChatsOpen((v) => !v)}>
            {chatsOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <span className="sb-label">Recents</span>
          </button>
          <div className="sb-section-actions">
            <button type="button" className="sb-mini" title="Filter" onClick={() => setShowSearch(true)}>
              <Filter size={13} />
            </button>
            <button type="button" className="sb-mini" title="New chat" onClick={openNewChat}>
              <Plus size={13} />
            </button>
          </div>
        </div>

        {chatsOpen && (
          <div className="sb-list">
            {history.map((t) => {
              const pending = approvals.some((a) => a.task_id === t.id);
              const active = selectedId === t.id && page === "chat";
              return (
                <button
                  key={t.id}
                  type="button"
                  className={`sb-item ${active ? "on" : ""}`}
                  title={taskLabel(t)}
                  onClick={() => {
                    setSelectedId(t.id);
                    setPage("chat");
                  }}
                >
                  <div className="sb-item-text">
                    <span className="sb-item-title">{taskLabel(t)}</span>
                    <span className={`sb-item-sub ${pending ? "warn" : statusTone(t.status)}`}>
                      {pending ? "needs you" : t.status.replace(/_/g, " ")}
                    </span>
                  </div>
                  <span className="sb-item-meta">{timeAgo(t.created_at || t.updated_at)}</span>
                </button>
              );
            })}
            {!history.length && <div className="sb-empty">No chats</div>}
          </div>
        )}
      </div>

      <div className="sb-bottom">
        {!githubConnected && (
          <button type="button" className="sb-cta" onClick={() => setPage("connections")} title="Connect GitHub">
            <span className="sb-ico-slot">
              <Plug size={ICON} strokeWidth={1.75} />
            </span>
            <span className="sb-label">Connect GitHub</span>
          </button>
        )}
        <div className="sb-status">
          <span className={`dot ${online ? "on" : "off"}`} />
          <span className="sb-label">{online ? "Backend online" : "Backend offline"}</span>
          <button type="button" className="sb-mini" onClick={refresh} disabled={refreshing} title="Refresh">
            <RefreshCw size={12} className={refreshing ? "spin" : undefined} />
          </button>
        </div>
        <div className="sb-user">
          <div className="sb-avatar">{(actorDraft || "E").slice(0, 1).toUpperCase()}</div>
          <div className="sb-user-meta">
            <strong>{actorDraft || "you"}</strong>
            <button type="button" onClick={toggle}>
              {theme === "dark" ? "Dark" : "Light"} · switch
            </button>
          </div>
          <button type="button" className="sb-mini" onClick={() => setPage("settings")} title="Settings">
            <Settings size={14} />
          </button>
        </div>
        <button type="button" className="sb-nav sb-theme-rail" onClick={toggle} title="Theme">
          <span className="sb-ico-slot">
            {theme === "dark" ? <Sun size={ICON} strokeWidth={1.75} /> : <Moon size={ICON} strokeWidth={1.75} />}
          </span>
          <span className="sb-label">Theme</span>
        </button>
      </div>
    </aside>
  );
}

function InspectPane({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { selected, selectedId, loadInspect, trace, replay, workingMemory } = useWorkspace();
  useEffect(() => {
    if (open && selectedId) loadInspect(selectedId);
  }, [open, selectedId]);

  return (
    <aside className={`rp ${open ? "open" : ""}`} aria-hidden={!open}>
      <div className="rp-inner">
        <div className="rp-tabs">
          <span className="rp-tab on">Inspect</span>
          <button type="button" className="sb-mini" onClick={onClose}>
            <X size={14} />
          </button>
        </div>
        <div className="rp-body">
          <h2>{selected ? taskLabel(selected) : "Inspect"}</h2>
          <p className="muted">{selected?.status?.replace(/_/g, " ") || "Pick a chat"}</p>
          {selected?.deliverable && (
            <div className="rp-card">
              <h3>Output</h3>
              <pre>{selected.deliverable.slice(0, 4000)}</pre>
            </div>
          )}
          <div className="rp-card">
            <h3>Working memory</h3>
            <pre>{JSON.stringify(workingMemory ?? {}, null, 2).slice(0, 6000)}</pre>
          </div>
          <div className="rp-card">
            <h3>Timeline / replay</h3>
            <pre>{JSON.stringify({ trace, replay }, null, 2).slice(0, 12000)}</pre>
          </div>
        </div>
      </div>
    </aside>
  );
}

function Shell() {
  const { page } = useWorkspace();
  const [collapsed, setCollapsed] = useState(false);
  const [inspectOpen, setInspectOpen] = useState(false);

  return (
    <div className="shell">
      <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} />
      <main className={`main ${page === "chat" ? "main-chat" : ""}`}>
        {page === "chat" && (
          <ChatPage inspectOpen={inspectOpen} onToggleInspect={() => setInspectOpen((v) => !v)} />
        )}
        {page === "tasks" && <TasksPage />}
        {page === "connections" && <ConnectionsPage />}
        {page === "agents" && <AgentsPage />}
        {page === "settings" && <SettingsPage />}
      </main>
      {page === "chat" && <InspectPane open={inspectOpen} onClose={() => setInspectOpen(false)} />}
    </div>
  );
}

export default function App() {
  return (
    <WorkspaceProvider>
      <Shell />
    </WorkspaceProvider>
  );
}
