# Agent Orchestration

Local-first multi-agent runtime: **supervisor → specialists → reviewer → human-in-the-loop**, with durable queues, hybrid memory, tool use (including MCP), and full-run inspect/replay.

Default stack runs at **$0/month** via Docker + [Ollama](https://ollama.com).

## Features

- LangGraph workflow: plan → specialist tools → review → synthesize → HITL gates
- Celery workers on Redis, durable task/approval state in PostgreSQL
- Working memory (Redis) + semantic memory (Chroma)
- Built-in tools (web search, sandboxed files, code exec) + MCP bridge
- Multi-provider LLMs: Ollama (default), OpenAI, or Anthropic
- OpenTelemetry → Jaeger traces; optional LangSmith
- Mission Control UI (React/Vite): runs inbox, approvals, timeline, conversation replay
- Stub eval harness for offline CI-style smoke checks

## Stack

| Layer | Tech |
|-------|------|
| Orchestration | LangGraph |
| API | FastAPI |
| Workers | Celery |
| Broker / working memory | Redis |
| Durable state | PostgreSQL |
| Observability | OpenTelemetry → Jaeger (+ optional LangSmith) |
| Long-term memory | Chroma |
| UI | React (Vite) + TypeScript |
| Tools | Built-ins + MCP demo server |
| LLMs | Ollama / OpenAI / Anthropic |
| Code sandbox | Local jail (+ optional E2B) |

## Architecture

```
React UI ──► FastAPI ──► Celery (Redis broker) ──► LangGraph agents
                │                │
                ├─ Postgres      ├─ Redis working memory
                ├─ Chroma        └─ tools (search / files / sandbox / MCP)
                └─ OTel spans ──► Jaeger UI (:16686)
```

## Prerequisites

1. Docker Desktop
2. Python 3.11+ and Node 20+
3. [Ollama](https://ollama.com/download) + models:

```bash
ollama pull qwen2.5:7b
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

## Quick start

```bash
cp .env.example .env   # Windows: copy .env.example .env

# Infra
docker compose up -d postgres redis jaeger

python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
export PYTHONPATH=src   # Windows PowerShell: $env:PYTHONPATH="src"

# API
uvicorn orchestrator.main:app --reload --app-dir src --port 8000

# Celery worker (separate terminal; on Windows add --pool=solo)
celery -A orchestrator.worker.celery_app worker --loglevel=INFO --pool=solo

# UI
cd web && npm install && npm run dev
```

| Service | URL |
|---------|-----|
| Mission Control UI | http://localhost:5173 |
| API docs | http://localhost:8000/docs |
| Jaeger | http://localhost:16686 |

### Offline / stub mode (no Ollama)

```bash
export ORCHESTRATOR_STUB_LLM=1
export ORCHESTRATOR_AUTO_APPROVE=1
```

### Optional E2B sandbox

```bash
export CODE_SANDBOX=e2b
export E2B_API_KEY=...
```

Falls back to the local sandbox if E2B is unavailable.

## Provider settings (UI)

Open **Settings** in Mission Control to switch providers without editing `.env`:

1. Choose **Ollama**, **OpenAI**, **Anthropic**, or **Stub**
2. Pick supervisor / specialist / embed models from the dropdowns (or type a custom id)
3. Paste your API key for cloud providers → **Save** → optional **Test**

Keys are stored in local Redis (masked in the API response). Celery workers read the same runtime config on each LLM call.

You can still set defaults in `.env`; UI overrides win until Redis is cleared.

## Access control & audit

Set a server token to lock the API:

```bash
export ORCHESTRATOR_API_TOKEN=your-secret
```

Clients send `Authorization: Bearer …` or `X-API-Key`, plus optional `X-Actor` for HITL attribution.  
Mission Control **Settings → Access & actor** stores token/name in the browser.  
Append-only events: `GET /v1/audit` (task created, approval resolved, tools, LLM settings).

## Cost model

Transcripts carry provider/model/token counts. Costs use a local price sheet (`orchestrator/costing.py`):

- Ollama / stub → **$0**
- OpenAI / Anthropic → approximate public USD / 1M tokens

```http
GET /v1/traces/{task_id}   # cost_proxy_usd + by_model
GET /v1/costs              # rollup across recent tasks
```

## Configuration highlights

Copy `.env.example` → `.env`. Important knobs:

| Variable | Purpose |
|----------|---------|
| `LLM_PROVIDER` | `ollama` (default) \| `openai` \| `anthropic` |
| `ORCHESTRATOR_AUTO_APPROVE` | Skip HITL when `1` |
| `HITL_FORCE_FINAL` | Always gate final deliverable |
| `MCP_ENABLED` | Load MCP demo tools |
| `OTEL_ENABLED` | Export spans to Jaeger |

### Cloud LLM providers

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...

# or
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=...
```

Anthropic chat uses the API; embeddings still go through local Ollama by default.

## MCP tools

With `MCP_ENABLED=1`, `mcp_servers/demo_server.py` registers tools such as `mcp_demo_get_time`. Override with `MCP_SERVERS` (JSON list of stdio MCP servers) to plug in your own.

## Evals & replay

```bash
export PYTHONPATH=src
export ORCHESTRATOR_STUB_LLM=1
export ORCHESTRATOR_AUTO_APPROVE=1
export MCP_ENABLED=0
python -m evals.run_evals
```

Inspect any run in the UI (**Inspect → timeline / replay / output**) or:

```http
GET /v1/traces/{task_id}
GET /v1/replay/{task_id}
```

## Optional LangSmith

Jaeger is the default always-on tracer. To also send traces to LangSmith:

```bash
export LANGSMITH_TRACING=1
export LANGSMITH_API_KEY=...
```

## Demo script

```bash
python demos/research_brief.py
```

## License

Use freely for learning and demos. Add a formal license file if you need one for redistribution.
