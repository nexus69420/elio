from __future__ import annotations

import pytest

from orchestrator.graph.workflow import run_task
from orchestrator.schemas import TaskRecord, TaskStatus
from orchestrator.store import task_store
from orchestrator.tools import register_default_tools, tool_registry
from orchestrator.tools.code_exec import code_exec
from orchestrator.tools.files import file_read, file_write
from orchestrator.tracing.spans import trace_store


def test_tools_sandbox(tmp_path, monkeypatch):
    from orchestrator.config import settings

    monkeypatch.setattr(settings, "workspace_dir", tmp_path)
    written = file_write("notes/hello.txt", "hi")
    assert written["bytes"] > 0
    assert file_read("notes/hello.txt")["content"] == "hi"
    with pytest.raises(ValueError):
        file_write("../escape.txt", "nope")
    assert "4" in code_exec("print(2+2)")["stdout"]
    with pytest.raises(ValueError):
        code_exec("import socket\nprint(1)")


def test_tool_registry():
    register_default_tools()
    names = {t["name"] for t in tool_registry.list_tools()}
    assert {"web_search", "file_read", "file_write", "code_exec"} <= names


@pytest.mark.asyncio
async def test_end_to_end_stub_graph():
    task = TaskRecord(
        prompt="Research local multi-agent tradeoffs and write a brief",
        force_hitl=True,
        status=TaskStatus.queued,
    )
    task_store.save(task)
    final = await run_task(task.id, task.prompt, force_hitl=True)
    assert final.get("deliverable")
    saved = task_store.get(task.id)
    assert saved.status == TaskStatus.completed
    spans = trace_store.list_spans(task.id)
    assert {s["name"] for s in spans} >= {"plan", "synthesize", "hitl_final"}
    from orchestrator.llm.transcript import transcript_store

    turns = transcript_store.list_turns(task.id)
    assert len(turns) >= 1
