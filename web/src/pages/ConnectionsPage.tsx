import { RefreshCw } from "lucide-react";
import { useWorkspace } from "../workspace/WorkspaceContext";

export function ConnectionsPage() {
  const w = useWorkspace();
  const {
    connectors,
    health,
    connectorsMsg,
    connectorsBusy,
    mcpEnabled,
    setMcpEnabled,
    mcpServersJson,
    setMcpServersJson,
    expandedConnector,
    setExpandedConnector,
    connectorDrafts,
    connectorConfigDrafts,
    oauthClientId,
    setOauthClientId,
    oauthClientSecret,
    setOauthClientSecret,
    reloadMcpConnectors,
    saveMcpConnectors,
    enableAppConnector,
    disableAppConnector,
    saveGithubOauthApp,
    connectGithubOAuth,
    patchConnectorSecret,
    patchConnectorConfig,
  } = w;

  return (
    <div className="page">
      <div className="topbar">
        <div>
          <h2>Connections</h2>
          <p>Wire the tools Elio can use. Writes pause for your approval in chat.</p>
        </div>
        <button className="btn btn-secondary" type="button" disabled={connectorsBusy} onClick={reloadMcpConnectors}>
          <RefreshCw size={15} /> Reload
        </button>
      </div>

      {connectorsMsg && (
        <div
          className={
            /^(Connected|Reloaded|Disconnected|Saved)/.test(connectorsMsg) ? "settings-ok" : "alert"
          }
        >
          {connectorsMsg}
        </div>
      )}

      <div className="panel" style={{ marginBottom: 12 }}>
        <div className="panel-head">
          <h3>Apps</h3>
          <span className="pill">
            {(connectors?.catalog || []).filter((c: any) => c.connected).length} connected
          </span>
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
                  <span key={cap} className="chip">
                    {cap}
                  </span>
                ))}
              </div>
              {c.hitl_writes && (
                <p className="muted" style={{ marginTop: 8 }}>
                  Writes require approval in chat before they run.
                </p>
              )}
              <div className="actions" style={{ marginTop: 10 }}>
                {c.id === "github" && c.connected && (
                  <span className="pill good">
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
                  {expandedConnector === c.id ? "Hide" : c.connected ? "Manage" : "Setup"}
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
              </div>

              {expandedConnector === c.id && c.id === "github" && (
                <div className="connector-form">
                  {!c.connected && (
                    <ol className="oauth-steps">
                      <li>
                        Open{" "}
                        <a
                          href={
                            connectors?.github_oauth?.create_app_url ||
                            "https://github.com/settings/applications/new"
                          }
                          target="_blank"
                          rel="noreferrer"
                        >
                          New OAuth App
                        </a>
                      </li>
                      <li>
                        Homepage: <code>{connectors?.github_oauth?.frontend_url || "http://127.0.0.1:5173"}</code>
                      </li>
                      <li>
                        Callback:{" "}
                        <code>
                          {connectors?.github_oauth?.authorize_callback_url ||
                            "http://127.0.0.1:8000/oauth/github/callback"}
                        </code>
                      </li>
                    </ol>
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
                    <label>Default owner / org</label>
                    <input
                      placeholder="your-username"
                      value={
                        (connectorConfigDrafts.github || {}).GITHUB_DEFAULT_OWNER ??
                        c.config?.GITHUB_DEFAULT_OWNER ??
                        ""
                      }
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
                      {c.connected ? "Re-authorize" : "Connect with GitHub"}
                    </button>
                  </div>
                  <details style={{ marginTop: 14 }}>
                    <summary className="muted">Advanced: personal access token</summary>
                    {(c.secret_fields || []).map((f: any) => (
                      <div className="field" key={f.key} style={{ marginTop: 10 }}>
                        <label>
                          {f.label}
                          {c.secrets_masked?.[f.key] ? ` (saved: ${c.secrets_masked[f.key]})` : ""}
                        </label>
                        <input
                          type="password"
                          placeholder={c.secrets_set?.[f.key] ? "Leave blank to keep" : f.placeholder}
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
                        placeholder={c.secrets_set?.[f.key] ? "Leave blank to keep" : f.placeholder}
                        value={(connectorDrafts[c.id] || {})[f.key] || ""}
                        onChange={(e) => patchConnectorSecret(c.id, f.key, e.target.value)}
                      />
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
                    </div>
                  ))}
                  <button
                    className="btn btn-primary"
                    type="button"
                    disabled={connectorsBusy}
                    onClick={() => enableAppConnector(c.id)}
                  >
                    {c.connected ? "Save & reload" : "Enable"}
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
              <div className="run-item static" key={t.name}>
                <div>
                  <strong>{t.name}</strong>
                  <div className="muted">{t.description}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="settings-active" style={{ marginTop: 12 }}>
            Sandbox: <strong>{connectors?.code_sandbox || health?.code_sandbox || "local"}</strong>
          </div>
        </div>
        <div className="panel">
          <div className="panel-head">
            <h3>Advanced · MCP JSON</h3>
            <span className={`pill ${mcpEnabled ? "good" : "muted"}`}>{mcpEnabled ? "on" : "off"}</span>
          </div>
          <label className="check">
            <input type="checkbox" checked={mcpEnabled} onChange={(e) => setMcpEnabled(e.target.checked)} />
            <span>Enable MCP tool bridge</span>
          </label>
          <div className="field">
            <label>Servers JSON</label>
            <textarea
              value={mcpServersJson}
              onChange={(e) => setMcpServersJson(e.target.value)}
              style={{ minHeight: 140, fontFamily: "var(--mono)" }}
            />
          </div>
          <button className="btn btn-primary" type="button" disabled={connectorsBusy} onClick={saveMcpConnectors}>
            Save MCP JSON
          </button>
        </div>
      </div>
    </div>
  );
}
