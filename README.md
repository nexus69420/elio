# Elio

**An everyday AI assistant, built around chat.**

Elio is being built as one place to ask for help with daily work and life: research a question, draft a document, organize information, work across your apps, or follow through on a recurring task. Tools and specialized agents provide the capabilities behind the conversation.

Describe the outcome, let Elio choose the appropriate tools and agents, follow its progress, approve actions when needed, and come back later to continue the work.

> Early prototype. The current app runs individual tasks from a chat interface. Continuing conversations, reminders, recurring tasks, and many capabilities below are planned.

## Where Elio is going

- **Everyday help:** research, writing, planning, information management, and personal admin alongside technical work.
- **Connected work:** use files, email, calendars, messaging, documents, and other apps from one conversation.
- **Appropriate capabilities:** answer simple questions directly and bring in specialists for work that needs them.
- **Work that continues:** preserve context, handle follow-ups, provide manageable memory, and support reminders and recurring work.
- **Visible actions:** show progress, tool results, proposed changes, approvals, and clear outcomes or failures.
- **Model choice:** retain local execution and local models while allowing optional cloud providers.

The target includes requests such as “research this and draft a brief,” “turn these meeting notes into actions,” and “summarize my inbox every morning.” Email access and scheduling are not implemented yet.

Read the [product vision](docs/VISION.md) and [implementation roadmap](ELIO_PRODUCT_PLAN.md).

## What exists today

The repository contains a single-workspace prototype with:

- React pages for Chat, Tasks, Connections, Agents, and Settings.
- FastAPI task APIs, Celery background jobs, and PostgreSQL task persistence.
- A LangGraph workflow for memory retrieval, planning, sequential specialists, review, synthesis, approval, and persistence.
- Editable agent profiles and packs for research briefs, code review, and job applications.
- Web search, workspace files, Python execution, native GitHub tools, and MCP integration with demo, filesystem, GitHub, and Slack servers.
- GitHub OAuth/PAT configuration, model settings, persisted approvals, task history, audit records, transcripts, cost estimates, and tracing.
- Ollama, OpenAI-compatible, Anthropic, and stub model paths.

These are capabilities present in source, not a claim that every integration has been validated end to end.

### Current limits

Each submission creates a new task; reopening a result does not provide a continuing conversation. Progress is polled rather than streamed, and there is no task cancellation API. Intensity controls primarily affect approval settings; they do not implement different reasoning depths or execution budgets.

Approval gates cover selected connector actions and final output. Built-in workspace file writes are currently ungated, so “ask before acting” is not a universal approval policy. Consistent action approvals are part of the first milestone.

## Run locally

See the [development guide](docs/DEVELOPMENT.md) for prerequisites, host/Windows setup, separate terminal commands, and verification.

For the container development stack, install Docker Compose and configure `.env`:

```bash
cp .env.example .env
```

With the default Ollama provider, install Ollama on the host and pull the configured models:

```bash
ollama pull qwen2.5:7b
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

Start the stack:

```bash
docker compose up -d
```

- UI: [localhost:5174](http://localhost:5174)
- API docs: [localhost:8000/docs](http://localhost:8000/docs)
- Jaeger: [localhost:16686](http://localhost:16686)

Compose publishes UI port 5174 but sets OAuth's frontend return URL to port 5173. Before using GitHub OAuth with the container UI, set `FRONTEND_PUBLIC_URL` to `http://localhost:5174` in **both** the `api` and `worker` service environment blocks. Editing only `.env` does not override those values. Host UI development uses port 5173.

## Stack and repository

| Area | Implementation |
|------|----------------|
| API and persistence | FastAPI, SQLAlchemy, PostgreSQL |
| Task execution | LangGraph, Celery, Redis |
| Memory | Redis working memory, Chroma semantic lessons |
| UI | React, TypeScript, Vite |
| Tools and apps | Built-in tools, native GitHub, MCP |
| Diagnostics | OpenTelemetry, Jaeger, transcripts, audit, cost estimates |

- `src/orchestrator/`: API, runtime, agents, tools, memory, and tracing.
- `web/`: chat workspace and supporting pages.
- `mcp_servers/`: connector servers.
- `tests/` and `evals/`: existing checks and stub evaluation cases.

Elio began as agent orchestration, became Mission Control, and evolved into a chat-first workspace. The next milestone is a continuing conversation that completes a connected task with visible progress and consistent approvals.
