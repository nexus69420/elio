import { Loader2, RefreshCw } from "lucide-react";
import { PromptInput } from "../components/FormBits";
import { useWorkspace } from "../workspace/WorkspaceContext";

export function AgentsPage() {
  const {
    agentsConfig,
    selectedAgentId,
    agentDraft,
    setAgentDraft,
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
    refresh,
    refreshing,
  } = useWorkspace();

  return (
    <div className="page">
      <div className="topbar">
        <div>
          <h2>Agents & packs</h2>
          <p>Personalities and workflow packs Elio can apply from chat.</p>
        </div>
        <div className="actions">
          <button className="btn btn-secondary" type="button" disabled={agentsBusy} onClick={resetAgents}>
            Reset defaults
          </button>
          <button className="btn btn-secondary" type="button" disabled={refreshing} onClick={refresh}>
            <RefreshCw size={15} className={refreshing ? "spin" : undefined} /> Refresh
          </button>
          <button className="btn btn-primary" type="button" disabled={agentsBusy || !agentDraft} onClick={saveAgent}>
            {agentsBusy ? (
              <>
                <Loader2 size={15} className="spin" /> Saving…
              </>
            ) : (
              "Save agent"
            )}
          </button>
        </div>
      </div>

      {agentsMsg && (
        <div className={/^(Saved|Applied|Reset)/.test(agentsMsg) ? "settings-ok" : "alert"}>{agentsMsg}</div>
      )}

      <div className="panel" style={{ marginBottom: 12 }}>
        <div className="panel-head">
          <h3>Packs</h3>
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
              <em>
                {p.builtin ? "built-in" : "custom"} · HITL {p.force_hitl ? "on" : "off"}
              </em>
            </button>
          ))}
        </div>
        <div className="preset-save">
          <input placeholder="pack id" value={savePresetId} onChange={(e) => setSavePresetId(e.target.value)} />
          <input placeholder="display name" value={savePresetName} onChange={(e) => setSavePresetName(e.target.value)} />
          <button className="btn btn-secondary" type="button" disabled={agentsBusy} onClick={() => saveCurrentAsPreset(true)}>
            Save current as pack
          </button>
        </div>
      </div>

      <div className="agents-layout">
        <div className="panel agents-list">
          <div className="panel-head">
            <h3>Team</h3>
          </div>
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
                <label>Instructions</label>
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
                />
              </div>
              <div className="field">
                <label>Model override</label>
                <input
                  value={agentDraft.model}
                  onChange={(e) => setAgentDraft({ ...agentDraft, model: e.target.value })}
                  placeholder="blank = Settings default"
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
                </div>
              )}
              <div className="agents-flags">
                <label className="check">
                  <input
                    type="checkbox"
                    checked={agentDraft.requires_hitl}
                    onChange={(e) => setAgentDraft({ ...agentDraft, requires_hitl: e.target.checked })}
                  />
                  <span>Requires HITL</span>
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
    </div>
  );
}
