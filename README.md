# Agent Orchestration System

Multi-agent runtime with **supervisor → specialists → reviewer → HITL**, backed by the same infra you’d list on a resume — still **$0/month** (local Docker + Ollama).

## Resume stack (no dumb tradeoffs)

| Layer | Tech |
|-------|------|
| Orchestration | LangGraph multi-agent graph |
| API | FastAPI |
| Workers | **Celery** |
| Broker / working memory | **Redis** |
| Durable state | **PostgreSQL** |
| Observability | **OpenTelemetry → Jaeger** (+ optional LangSmith) |
| Long-term memory | Chroma |
| UI | **React (Vite)** — tasks, HITL, traces, **replay**, memory |
| Tools | Built-ins + **MCP** demo server |
| LLMs | **Multi-provider**: Ollama default; OpenAI/Anthropic via env |
| Code sandbox | Local jail + optional **E2B** free Hobby tier |
| Evals | `python -m evals.run_evals` |

## Architecture

```
React UI ──► FastAPI ──► Celery (Redis broker) ──► LangGraph agents
                │                │
                ├─ Postgres      ├─ Redis working memory
                ├─ Chroma        └─ tool calls (search / files / sandbox)
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
copy .env.example .env

# Infra: Postgres + Redis + Jaeger
docker compose up -d postgres redis jaeger

python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# API
uvicorn orchestrator.main:app --reload --app-dir src --port 8000

# Celery worker (separate terminal)
celery -A orchestrator.worker.celery_app worker --loglevel=INFO
# (set PYTHONPATH=src on Windows: $env:PYTHONPATH="src")

# React UI
cd web
npm install
npm run dev
```

Open:
- UI: http://localhost:5173
- API docs: http://localhost:8000/docs
- Jaeger: http://localhost:16686

Stub / offline (no Ollama):

```bash
$env:ORCHESTRATOR_STUB_LLM=1
$env:ORCHESTRATOR_AUTO_APPROVE=1
```

Optional E2B cloud sandbox (Hobby free credits):

```bash
$env:CODE_SANDBOX="e2b"
$env:E2B_API_KEY="..."
```

Falls back to local sandbox automatically if E2B is unavailable.

## Multi-LLM providers

Default is local Ollama (`LLM_PROVIDER=ollama`). To swap:

```bash
# OpenAI
$env:LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="sk-..."

# Anthropic (embeds still use Ollama locally)
$env:LLM_PROVIDER="anthropic"
$env:ANTHROPIC_API_KEY="..."
```

## MCP tools

With `MCP_ENABLED=1`, the demo MCP server (`mcp_servers/demo_server.py`) auto-registers tools like `mcp_demo_get_time`. Point `MCP_SERVERS` JSON at any stdio MCP server to add more.

## Evals + conversation replay

```bash
$env:PYTHONPATH="src"
$env:ORCHESTRATOR_STUB_LLM=1
$env:ORCHESTRATOR_AUTO_APPROVE=1
$env:MCP_ENABLED=0
python -m evals.run_evals
```

Replay any task in the UI **replay** tab or `GET /v1/replay/{task_id}`.

## LangSmith (optional)

**LangSmith** is LangChain’s hosted tracing/eval product (not the same as LangGraph).  
We already ship **Jaeger** for $0 always-on traces. LangSmith’s free Developer tier (~5k traces/mo) is optional for nicer LLM-centric eval UI:

```bash
$env:LANGSMITH_TRACING=1
$env:LANGSMITH_API_KEY="..."
```

Use Jaeger as the source of truth; turn on LangSmith only when you want their dashboard.

## Backlog

See [BACKLOG.md](BACKLOG.md) for deferred governance (auth/audit) and cost-model work.

## Demo

```bash
python demos/research_brief.py
```

## Interview line

> I built a multi-agent orchestration platform on LangGraph with Celery, Redis, Postgres, OpenTelemetry/Jaeger, MCP tool bridges, multi-provider LLM routing, conversation replay + eval harness, and a React HITL console — defaulting to fully local $0 inference.
