# Elio

**Chat-first AI workspace** that runs agentic workflows across your tools — from quick asks to multi-agent jobs with human-in-the-loop.

Local-first by default (Docker + [Ollama](https://ollama.com)). OpenAI / Anthropic (or OpenRouter via OpenAI-compatible base URL) optional.

> Work in progress — single-workspace product MVP, not multi-tenant SaaS yet.

## What you get

- **Chat** home: ask Elio to do things; intensity + pack + “ask before acting” controls
- **Tasks**: every run, open back into the thread
- **Connections**: GitHub (OAuth), Slack, filesystem — writes pause for approval in chat
- **Agents & packs**: personalize prompts, tools, HITL; apply workflow packs from chat
- Under the hood: LangGraph supervisor → specialists → reviewer → HITL, Celery, Redis, Postgres, Chroma, OTel

## Stack

| Layer | Tech |
|-------|------|
| Orchestration | LangGraph |
| API | FastAPI |
| Workers | Celery + Redis |
| State | PostgreSQL |
| Memory | Redis + Chroma |
| UI | React (Vite) · Elio workspace |
| LLMs | Ollama / OpenAI / Anthropic |
| Tools | Built-ins + MCP connectors |

## Quick start

```bash
cp .env.example .env   # Windows: copy .env.example .env

docker compose up -d postgres redis jaeger

python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
export PYTHONPATH=src   # PowerShell: $env:PYTHONPATH="src"

uvicorn orchestrator.main:app --reload --app-dir src --port 8000

# separate terminal — Windows needs --pool=solo
celery -A orchestrator.worker.celery_app worker --loglevel=INFO --pool=solo

cd web && npm install && npm run dev
```

Open **http://127.0.0.1:5173** — Chat is the default.

Pull models if using Ollama:

```bash
ollama pull qwen2.5:7b
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

## Product notes

- One chat message → one orchestrated task (approvals appear inline).
- Intensity maps client-side to HITL / pack selection; packs come from `/v1/agents` presets.
- Optional API gate: set `ORCHESTRATOR_API_TOKEN` and paste it in Settings.

## Repo

Formerly “agent-orchestration / Mission Control.” Same runtime; Elio is the product shell.
