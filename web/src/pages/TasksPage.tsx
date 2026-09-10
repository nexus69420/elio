import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { statusTone, taskLabel, preview } from "../api";
import { useWorkspace } from "../workspace/WorkspaceContext";

export function TasksPage() {
  const { tasks, approvals, setSelectedId, setPage, refresh, refreshing } = useWorkspace();
  const [filter, setFilter] = useState("all");

  const RUNNING = ["queued", "planning", "executing", "reviewing", "synthesizing", "awaiting_approval"];

  const filtered = useMemo(() => {
    if (filter === "all") return tasks;
    if (filter === "active") {
      return tasks.filter(
        (t) =>
          RUNNING.includes(t.status) &&
          (t.status !== "awaiting_approval" || approvals.some((a) => a.task_id === t.id))
      );
    }
    return tasks.filter((t) => t.status === filter);
  }, [tasks, filter, approvals]);

  return (
    <div className="page">
      <div className="topbar">
        <div>
          <h2>Tasks</h2>
          <p>Every run Elio started from chat. Open one to continue in the thread.</p>
        </div>
        <button className="btn btn-secondary" type="button" disabled={refreshing} onClick={refresh}>
          <RefreshCw size={15} className={refreshing ? "spin" : undefined} /> Refresh
        </button>
      </div>

      <div className="filter-row">
        {["all", "active", "completed", "failed", "awaiting_approval"].map((f) => (
          <button
            key={f}
            type="button"
            className={`chip-btn ${filter === f ? "active" : ""}`}
            onClick={() => setFilter(f)}
          >
            {f.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      <div className="panel">
        <div className="list">
          {filtered.map((t) => (
            <button
              key={t.id}
              type="button"
              className="run-item"
              onClick={() => {
                setSelectedId(t.id);
                setPage("chat");
              }}
            >
              <div>
                <strong>{taskLabel(t)}</strong>
                <div className="muted">{preview(t.prompt, 100)}</div>
              </div>
              <span className={`pill ${statusTone(t.status)}`}>{t.status.replace(/_/g, " ")}</span>
            </button>
          ))}
          {!filtered.length && <div className="empty">No tasks match this filter.</div>}
        </div>
      </div>
    </div>
  );
}
