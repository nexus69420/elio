from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/health")
async def health():
    llm = await llm_client.health()
    register_default_tools()
    tool_names = [t["name"] for t in tool_registry.list_tools()]
    return {
        "ok": True,
        "stub_llm": settings.orchestrator_stub_llm,
        "llm_provider": settings.llm_provider,
        "llm": llm,
        "postgres": ping_db(),
        "redis": working_memory.ping(),
        "otel_enabled": settings.otel_enabled,
        "langsmith_tracing": settings.langsmith_tracing,
        "mcp_enabled": settings.mcp_enabled,
        "mcp_tools": [n for n in tool_names if n.startswith("mcp_")],
        "code_sandbox": settings.code_sandbox,
        "jaeger_ui": "http://localhost:16686",
        "data_dir": str(settings.data_dir.resolve()),
    }
