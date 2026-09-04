from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("ORCHESTRATOR_STUB_LLM", "1")
os.environ.setdefault("ORCHESTRATOR_AUTO_APPROVE", "1")
os.environ.setdefault("OTEL_ENABLED", "0")
os.environ.setdefault("MCP_ENABLED", "0")
os.environ.setdefault("DATA_DIR", str(Path(__file__).resolve().parent / "_testdata"))
os.environ.setdefault("WORKSPACE_DIR", str(Path(__file__).resolve().parent / "_testdata" / "workspace"))


@pytest.fixture(scope="session", autouse=True)
def _infra_or_skip():
    """Require Postgres + Redis (docker compose up -d postgres redis)."""
    import redis
    from sqlalchemy import create_engine, text

    db = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://orchestrator:orchestrator@127.0.0.1:5432/orchestrator",
    )
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    try:
        eng = create_engine(db)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        assert redis.Redis.from_url(redis_url).ping()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Infra not up (docker compose up -d postgres redis): {exc}")


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_STUB_LLM", "1")
    monkeypatch.setenv("ORCHESTRATOR_AUTO_APPROVE", "1")
    monkeypatch.setenv("OTEL_ENABLED", "0")
    monkeypatch.setenv("MCP_ENABLED", "0")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path / "data" / "workspace"))
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "data" / "chroma"))

    from orchestrator import config
    from orchestrator.llm import client as llm_mod
    from orchestrator.memory import semantic as sem_mod
    from orchestrator.memory import working as work_mod
    from orchestrator.hitl import queue as hitl_mod
    from orchestrator import store as store_mod
    from orchestrator.tracing import spans as span_mod
    import orchestrator.graph.nodes as nodes
    import orchestrator.graph.workflow as wf

    config.settings = config.Settings()
    config.settings.ensure_dirs()
    store_mod.task_store = store_mod.TaskStore()
    hitl_mod.approval_queue = hitl_mod.ApprovalQueue()
    work_mod.working_memory = work_mod.WorkingMemory()
    span_mod.trace_store = span_mod.TraceStore()
    sem_mod.semantic_memory = sem_mod.SemanticMemory()
    llm_mod.llm_client = llm_mod.LLMClient()

    nodes.task_store = store_mod.task_store
    nodes.approval_queue = hitl_mod.approval_queue
    nodes.working_memory = work_mod.working_memory
    nodes.semantic_memory = sem_mod.semantic_memory
    nodes.trace_store = span_mod.trace_store
    nodes.llm_client = llm_mod.llm_client
    nodes.settings = config.settings

    wf.task_store = store_mod.task_store
    wf.trace_store = span_mod.trace_store
    wf._graph = None
    yield
