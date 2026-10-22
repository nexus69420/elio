# Developing Elio

The [README](../README.md) describes current capabilities; the [product plan](../ELIO_PRODUCT_PLAN.md) describes planned work.

## Prerequisites and configuration

- Docker with Docker Compose for PostgreSQL, Redis, and Jaeger.
- For host API/worker development: Python 3.11+ and a virtual environment.
- For host UI development: Node.js 22 and npm (Compose also uses Node 22).
- Ollama for default chat/embedding models, or configured provider credentials. Anthropic chat currently falls back to Ollama for embeddings.

Copy configuration before starting:

```bash
cp .env.example .env
```

For default Ollama configuration, pull the models on the host:

```bash
ollama pull qwen2.5:7b
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

These names match `.env.example`; they are configuration defaults rather than a current model recommendation. Configure provider/model names and credentials in `.env` or Settings. `OPENAI_BASE_URL` supports an OpenAI-compatible endpoint.

Set `ORCHESTRATOR_API_TOKEN` to enable the optional API gate, and enter the same token in the UI's Settings. An empty value leaves the local demo API open. This gate is not multi-user authentication or workspace isolation.

## Container development stack

From the repository root:

```bash
docker compose up -d
```

Compose mounts source and installs Python/npm dependencies on startup. This is a development setup.

| Service | Host address |
|---------|--------------|
| UI | http://localhost:5174 |
| API / API docs | http://localhost:8000 / http://localhost:8000/docs |
| Jaeger | http://localhost:16686 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

The container API/worker use `host.docker.internal:11434` for host Ollama.

### GitHub OAuth return URL

Compose publishes UI port 5174 but explicitly sets `FRONTEND_PUBLIC_URL` to `http://localhost:5173` on API and worker. For the container UI, change that value to `http://localhost:5174` in both services and recreate them. Service `environment` values override `env_file`; editing `.env` alone is insufficient.

The GitHub callback is `http://localhost:8000/oauth/github/callback`; configure the OAuth app accordingly. Keep the browser hostname consistent with configured return/callback URLs.

## Host development: macOS/Linux

From the repository root:

```bash
docker compose up -d postgres redis jaeger
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Start each process in a separate terminal. API/worker terminals should use the repository root and virtual environment.

API:

```bash
source .venv/bin/activate
export PYTHONPATH=src
uvicorn orchestrator.main:app --reload --app-dir src --port 8000
```

Worker:

```bash
source .venv/bin/activate
export PYTHONPATH=src
celery -A orchestrator.worker.celery_app worker --loglevel=INFO
```

UI:

```bash
cd web
npm install
npm run dev
```

The host UI runs at http://localhost:5173. Align `FRONTEND_PUBLIC_URL` with the actual browser origin for OAuth. Avoid running full Compose API/worker/UI services alongside host processes on the same ports.

## Windows PowerShell

From the repository root:

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
docker compose up -d postgres redis jaeger
```

API terminal:

```powershell
$env:PYTHONPATH = 'src'
.\.venv\Scripts\uvicorn orchestrator.main:app --reload --app-dir src --port 8000
```

Worker terminal (use Celery's solo pool on Windows):

```powershell
$env:PYTHONPATH = 'src'
.\.venv\Scripts\celery -A orchestrator.worker.celery_app worker --loglevel=INFO --pool=solo
```

UI terminal:

```powershell
cd web
npm install
npm run dev
```

The existing `scripts/dev.ps1` prints host development commands after environment setup.

## Verification

With the virtual environment active, PostgreSQL/Redis running, and the repository root as the working directory:

```bash
python -m pytest
python -m evals.run_evals
```

Existing tests/evaluations use a stub LLM. They do not validate real model quality, OAuth, or live connectors. The session fixture requires PostgreSQL/Redis and skips tests when unavailable, including existing tool tests. Check for skips before treating a run as successful validation.

The evaluation harness also needs runtime dependencies and infrastructure; “stub” does not mean infrastructure-free. It writes its report under `data/`.

UI build and type checking, from `web/`:

```bash
npm run build
npx tsc --noEmit
```

The build script runs Vite; TypeScript checking is separate.

Use `/health` to inspect database, Redis, and provider information. Its top-level `ok` alone is not an end-to-end readiness check.

The 22 October documentation refresh was checked against source and local links. The application stack, provider calls, and integrations were not started or validated during that update.
