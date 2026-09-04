# Iteration backlog (article criteria 6–7)

## 4. Governance (deferred)
- API key / admin token auth
- Actor field on approvals
- Append-only `audit_events` table (task created, tool called, approval resolved)
- Optional RBAC roles later

## 5. TCO / cost model (deferred)
- Price sheet for Ollama ($0) vs OpenAI/Anthropic token rates
- Real `cost_proxy_usd` on `/v1/traces` and UI
- Aggregate `/v1/costs` rollup

Keep Jaeger as the always-on $0 observability path. LangSmith is optional (see README).
