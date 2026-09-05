from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse

from orchestrator.api.routes import router
from orchestrator.config import settings
from orchestrator.db import init_db, ping_db
from orchestrator.llm.client import llm_client
from orchestrator.memory.working import working_memory
from orchestrator.tools import register_default_tools, tool_registry
from orchestrator.tracing.otel import setup_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    if settings.langsmith_tracing and settings.langsmith_api_key:
        import os

        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    setup_tracing(app)
    init_db()
    register_default_tools()
    yield


app = FastAPI(title="Agent Orchestration System", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/oauth/github/callback")
async def github_oauth_callback(
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    error_description: Optional[str] = Query(default=None),
):
    """Browser return from GitHub — no API token (GitHub redirects here)."""
    frontend = (settings.frontend_public_url or "http://127.0.0.1:5173").rstrip("/")
    if error:
        desc = error_description or error
        from urllib.parse import quote

        return RedirectResponse(f"{frontend}/?connected=github&error={quote(str(desc)[:180])}")
    if not code or not state:
        return HTMLResponse("<h3>Missing code/state from GitHub</h3>", status_code=400)
    try:
        from orchestrator.github_oauth import finish_callback

        result = await finish_callback(code=code, state=state)
        return RedirectResponse(result["redirect"])
    except Exception as exc:  # noqa: BLE001
        from urllib.parse import quote

        return RedirectResponse(f"{frontend}/?connected=github&error={quote(str(exc)[:180])}")


@app.get("/health")
async def health():
    llm = await llm_client.health()
    register_default_tools()
    tool_names = [t["name"] for t in tool_registry.list_tools()]
    from orchestrator.runtime_llm import runtime_llm
    from orchestrator.runtime_mcp import runtime_mcp

    cfg = runtime_llm.get()
    mcp_cfg = runtime_mcp.get()
    return {
        "ok": True,
        "stub_llm": bool(cfg.get("stub")),
        "llm_provider": cfg.get("llm_provider"),
        "llm": llm,
        "postgres": ping_db(),
        "redis": working_memory.ping(),
        "otel_enabled": settings.otel_enabled,
        "langsmith_tracing": settings.langsmith_tracing,
        "mcp_enabled": bool(mcp_cfg.get("enabled")),
        "mcp_tools": [n for n in tool_names if n.startswith("mcp_")],
        "code_sandbox": settings.code_sandbox,
        "jaeger_ui": "http://localhost:16686",
        "data_dir": str(settings.data_dir.resolve()),
        "auth_required": bool((settings.orchestrator_api_token or "").strip()),
    }
