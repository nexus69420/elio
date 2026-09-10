import { useMemo, useState } from "react";
import {
  Bug,
  ChevronDown,
  Code2,
  Loader2,
  Plug,
  Search,
  Sparkles,
  Wrench,
} from "lucide-react";
import { ApprovalCard } from "../components/ApprovalCard";
import { ComposerBar } from "../components/ComposerBar";
import { Intensity } from "../lib/intensity";
import { taskLabel } from "../api";
import { useWorkspace } from "../workspace/WorkspaceContext";

const STARTERS = [
  {
    id: "explore",
    icon: Search,
    tone: "amber",
    label: "Explore and understand code",
    prompt: "Explore this workspace and explain the main architecture in plain language.",
  },
  {
    id: "build",
    icon: Wrench,
    tone: "violet",
    label: "Build a new feature, app, or tool",
    prompt: "Help me plan and build a small feature end-to-end, starting with a short design.",
  },
  {
    id: "review",
    icon: Code2,
    tone: "green",
    label: "Review code and suggest changes",
    prompt: "Review recent changes and suggest the highest-impact improvements.",
  },
  {
    id: "fix",
    icon: Bug,
    tone: "rose",
    label: "Fix issues and failures",
    prompt: "Help me diagnose and fix the most likely failures in this project.",
  },
] as const;

export function ChatPage({
  inspectOpen,
  onToggleInspect,
}: {
  inspectOpen?: boolean;
  onToggleInspect?: () => void;
}) {
  const {
    selected,
    selectedId,
    approvals,
    busy,
    sendMessage,
    resolve,
    resolvingId,
    error,
    setPage,
    connectedCount,
    agentsConfig,
  } = useWorkspace();

  const [draft, setDraft] = useState("");
  const [intensity, setIntensity] = useState<Intensity>("assist");
  const [askBeforeActing, setAskBeforeActing] = useState(true);
  const [packId, setPackId] = useState("");

  const threadApprovals = useMemo(
    () => (selectedId ? approvals.filter((a) => a.task_id === selectedId) : []),
    [approvals, selectedId]
  );

  async function onSend() {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    await sendMessage(text, { intensity, askBeforeActing, packId });
  }

  const running = selected && !["completed", "failed", "rejected"].includes(selected.status);
  const title = selected ? taskLabel(selected) : "New chat";

  return (
    <section className="chat">
      <header className="chat-bar">
        <button type="button" className="chat-title">
          {title} <ChevronDown size={14} />
        </button>
        <div className="chat-bar-right">
          {connectedCount === 0 && (
            <button type="button" className="chip-plus" onClick={() => setPage("connections")}>
              + Connect
            </button>
          )}
          <button
            type="button"
            className={`chip-quiet btnish ${inspectOpen ? "on" : ""}`}
            onClick={onToggleInspect}
          >
            Inspect
          </button>
        </div>
      </header>

      {error && <div className="alert">{error}</div>}

      <div className="chat-scroll">
        {!selected && (
          <div className="chat-empty">
            <div className="chat-empty-mark">
              <Sparkles size={22} />
            </div>
            <h3>What should we work on?</h3>
            <p>Pick a starter or type anything below.</p>
            <div className="starter-grid">
              {STARTERS.map((s) => {
                const Icon = s.icon;
                return (
                  <button
                    key={s.id}
                    type="button"
                    className={`starter-card tone-${s.tone}`}
                    onClick={() => setDraft(s.prompt)}
                  >
                    <span className="starter-ico">
                      <Icon size={15} strokeWidth={2} />
                    </span>
                    <span>{s.label}</span>
                  </button>
                );
              })}
            </div>
            {connectedCount === 0 && (
              <button type="button" className="pill-btn" onClick={() => setPage("connections")}>
                <Plug size={14} /> Connect a tool
              </button>
            )}
          </div>
        )}

        {selected && (
          <div className="chat-msgs">
            <div className="msg user">{selected.prompt}</div>

            {running && (
              <div className="msg-status">
                <Loader2 size={13} className="spin" /> {selected.status.replace(/_/g, " ")}…
              </div>
            )}

            {threadApprovals.map((a) => (
              <ApprovalCard key={a.id} approval={a} busy={resolvingId === a.id} onResolve={resolve} />
            ))}

            {selected.deliverable && <div className="msg ai">{selected.deliverable}</div>}
            {selected.error && <div className="msg err">{selected.error}</div>}
          </div>
        )}
      </div>

      <ComposerBar
        value={draft}
        onChange={setDraft}
        onSend={onSend}
        busy={busy}
        intensity={intensity}
        onIntensity={setIntensity}
        packId={packId}
        onPack={setPackId}
        askBeforeActing={askBeforeActing}
        onAskBeforeActing={setAskBeforeActing}
        presets={agentsConfig?.presets || []}
      />
    </section>
  );
}
