import { formatUsd, preview, shortId } from "../api";
import { mergeOpts, ModelSelect } from "../components/FormBits";
import { useWorkspace } from "../workspace/WorkspaceContext";

export function SettingsPage() {
  const {
    health,
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
    saveLlmSettings,
    testLlmSettings,
    patchSettings,
    onProviderChange,
    saveAccess,
    setSelectedId,
    setPage,
  } = useWorkspace();

  return (
    <div className="page">
      <div className="topbar">
        <div>
          <h2>Workspace settings</h2>
          <p>Models, access, and usage. Keys stay local — never returned in full.</p>
        </div>
        <div className="actions">
          <button className="btn btn-secondary" type="button" disabled={settingsBusy} onClick={testLlmSettings}>
            Test
          </button>
          <button
            className="btn btn-primary"
            type="button"
            disabled={settingsBusy || !llmSettings}
            onClick={saveLlmSettings}
          >
            {settingsBusy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      {!llmSettings ? (
        <div className="panel">
          <div className="empty">Loading settings…</div>
        </div>
      ) : (
        <div className="panel settings-panel">
          <div className="field">
            <label>Provider</label>
            <select value={llmSettings.llm_provider} onChange={(e) => onProviderChange(e.target.value)}>
              {Object.entries(llmSettings.presets).map(([id, p]) => (
                <option key={id} value={id}>
                  {p.label}
                </option>
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
                <label>
                  API key {llmSettings.openai_api_key_set ? `(saved: ${llmSettings.openai_api_key_masked})` : ""}
                </label>
                <input
                  type="password"
                  autoComplete="off"
                  placeholder={llmSettings.openai_api_key_set ? "Leave blank to keep" : "sk-..."}
                  value={openaiKeyDraft}
                  onChange={(e) => setOpenaiKeyDraft(e.target.value)}
                />
              </div>
              <div className="field">
                <label>Base URL (OpenAI-compatible / OpenRouter)</label>
                <input
                  value={llmSettings.openai_base_url}
                  onChange={(e) => patchSettings({ openai_base_url: e.target.value })}
                />
              </div>
              <div className="grid-2">
                <ModelSelect
                  label="Supervisor"
                  value={llmSettings.openai_supervisor_model}
                  options={llmSettings.presets.openai?.supervisor_models || []}
                  onChange={(v) => patchSettings({ openai_supervisor_model: v })}
                />
                <ModelSelect
                  label="Specialist"
                  value={llmSettings.openai_specialist_model}
                  options={llmSettings.presets.openai?.specialist_models || []}
                  onChange={(v) => patchSettings({ openai_specialist_model: v })}
                />
              </div>
            </>
          )}

          {llmSettings.llm_provider === "anthropic" && (
            <>
              <div className="field">
                <label>
                  API key{" "}
                  {llmSettings.anthropic_api_key_set ? `(saved: ${llmSettings.anthropic_api_key_masked})` : ""}
                </label>
                <input
                  type="password"
                  autoComplete="off"
                  placeholder={llmSettings.anthropic_api_key_set ? "Leave blank to keep" : "sk-ant-..."}
                  value={anthropicKeyDraft}
                  onChange={(e) => setAnthropicKeyDraft(e.target.value)}
                />
              </div>
              <div className="grid-2">
                <ModelSelect
                  label="Supervisor"
                  value={llmSettings.anthropic_supervisor_model}
                  options={llmSettings.presets.anthropic?.supervisor_models || []}
                  onChange={(v) => patchSettings({ anthropic_supervisor_model: v })}
                />
                <ModelSelect
                  label="Specialist"
                  value={llmSettings.anthropic_specialist_model}
                  options={llmSettings.presets.anthropic?.specialist_models || []}
                  onChange={(v) => patchSettings({ anthropic_specialist_model: v })}
                />
              </div>
            </>
          )}

          {llmSettings.llm_provider === "stub" && (
            <div className="empty">Stub mode — canned responses, no GPU or API key.</div>
          )}

          <div className="settings-active">
            Active: <strong>{llmSettings.active_chat_models.supervisor}</strong> ·{" "}
            <strong>{llmSettings.active_chat_models.specialist}</strong>
          </div>
          {settingsMsg && (
            <div className={/^(Connected|Saved|Access)/.test(settingsMsg) ? "settings-ok" : "alert"}>
              {settingsMsg}
            </div>
          )}
        </div>
      )}

      <div className="panel settings-panel" style={{ marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Access</h3>
        <p className="hint">
          {health?.auth_required ? "Auth is required on this server." : "Auth is open (no server token)."}
        </p>
        <div className="grid-2">
          <div className="field">
            <label>Display name</label>
            <input value={actorDraft} onChange={(e) => setActorDraft(e.target.value)} />
          </div>
          <div className="field">
            <label>API token</label>
            <input
              type="password"
              value={apiTokenDraft}
              onChange={(e) => setApiTokenDraft(e.target.value)}
              placeholder="optional"
            />
          </div>
        </div>
        <button className="btn btn-secondary" type="button" onClick={saveAccess}>
          Save access
        </button>
      </div>

      <div className="panel" style={{ marginTop: 16 }}>
        <div className="panel-head">
          <h3>Cost rollup</h3>
          <span className="pill">{formatUsd(costs?.total_cost_usd)}</span>
        </div>
        <div className="list">
          {(costs?.tasks || []).slice(0, 8).map((row) => (
            <button
              key={row.task_id}
              type="button"
              className="run-item"
              onClick={() => {
                setSelectedId(row.task_id);
                setPage("chat");
              }}
            >
              <div>
                <strong>{shortId(row.task_id)}</strong>
                <div className="muted">{preview(row.prompt_preview, 80)}</div>
              </div>
              <div className="muted">
                {formatUsd(row.cost_usd)} · {row.total_tokens} tok
              </div>
            </button>
          ))}
          {!costs?.tasks?.length && <div className="empty">No cost data yet.</div>}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 16 }}>
        <div className="panel-head">
          <h3>Audit</h3>
          <span className="pill">{auditEvents.length}</span>
        </div>
        <div className="list">
          {auditEvents.slice(0, 12).map((ev) => (
            <div className="run-item static" key={ev.id}>
              <div>
                <strong>{ev.action}</strong>
                <div className="muted">
                  {ev.actor} · {ev.task_id ? shortId(ev.task_id) : "—"}
                </div>
              </div>
            </div>
          ))}
          {!auditEvents.length && <div className="empty">No audit events yet.</div>}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 16 }}>
        <div className="panel-head">
          <h3>Tools</h3>
          <span className="pill">{toolCatalog.length}</span>
        </div>
        <div className="list">
          {toolCatalog.slice(0, 24).map((tool) => (
            <div className="run-item static" key={tool.name}>
              <div>
                <strong>{tool.name}</strong>
                <div className="muted">{preview(tool.description, 100)}</div>
              </div>
              {tool.requires_approval && <span className="pill warn">HITL</span>}
            </div>
          ))}
          {!toolCatalog.length && <div className="empty">No tools registered yet.</div>}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 16 }}>
        <div className="panel-head">
          <h3>Semantic memory</h3>
          <span className="pill">{memoryItems.length}</span>
        </div>
        <div className="list">
          {memoryItems.slice(0, 12).map((item) => (
            <div className="run-item static" key={item.id}>
              <div>
                <strong>{shortId(item.id)}</strong>
                <div className="muted">{preview(item.document, 120)}</div>
              </div>
            </div>
          ))}
          {!memoryItems.length && <div className="empty">No memory entries yet.</div>}
        </div>
      </div>
    </div>
  );
}
