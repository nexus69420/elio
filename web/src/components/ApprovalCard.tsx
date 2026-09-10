import { useState } from "react";
import { Loader2, ShieldAlert } from "lucide-react";
import { Approval, preview } from "../api";

export function ApprovalCard({
  approval,
  busy,
  onResolve,
}: {
  approval: Approval;
  busy?: boolean;
  onResolve: (id: string, action: string, extra?: Record<string, string>) => void;
}) {
  const [modify, setModify] = useState("");
  const [showModify, setShowModify] = useState(false);

  return (
    <div className="approval-card">
      <div className="approval-card-head">
        <ShieldAlert size={16} />
        <div>
          <strong>Needs your OK</strong>
          <span className="muted"> · {approval.level.replace(/_/g, " ")}</span>
        </div>
      </div>
      <p className="approval-reason">{approval.reason}</p>
      <pre className="approval-body">{preview(approval.proposed_action, 900)}</pre>
      {showModify && (
        <textarea
          className="prompt-input"
          value={modify}
          onChange={(e) => setModify(e.target.value)}
          placeholder="Modified action / plan…"
          rows={3}
        />
      )}
      <div className="actions">
        <button
          className="btn btn-primary"
          disabled={busy}
          type="button"
          onClick={() => onResolve(approval.id, "approve")}
        >
          {busy ? <Loader2 size={14} className="spin" /> : null}
          Approve
        </button>
        <button
          className="btn btn-secondary"
          disabled={busy}
          type="button"
          onClick={() => {
            if (!showModify) {
              setShowModify(true);
              setModify(approval.proposed_action || "");
              return;
            }
            onResolve(approval.id, "modify", { modified_action: modify });
          }}
        >
          {showModify ? "Submit modify" : "Modify"}
        </button>
        <button
          className="btn btn-danger"
          disabled={busy}
          type="button"
          onClick={() => onResolve(approval.id, "reject")}
        >
          Reject
        </button>
      </div>
    </div>
  );
}
