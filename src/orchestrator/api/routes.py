from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from orchestrator.hitl.queue import approval_queue
from orchestrator.memory.semantic import semantic_memory
from orchestrator.memory.working import working_memory
from orchestrator.schemas import ApprovalResolve, TaskCreate, TaskRecord, TaskStatus
from orchestrator.store import task_store
from orchestrator.tools import register_default_tools, tool_registry
from orchestrator.tracing.spans import trace_store
from orchestrator.worker import run_task_job

router = APIRouter(prefix="/v1")


@router.post("/tasks", response_model=TaskRecord)
async def create_task(body: TaskCreate) -> TaskRecord:
    register_default_tools()
    task = TaskRecord(prompt=body.prompt, force_hitl=body.force_hitl, status=TaskStatus.queued)
    task_store.save(task)
    # Celery worker picks this up (Redis broker)
    run_task_job.delay(task.id, body.prompt, body.force_hitl)
    return task


@router.get("/tasks", response_model=list[TaskRecord])
async def list_tasks(limit: int = 20) -> list[TaskRecord]:
    return task_store.list_recent(limit=limit)


@router.get("/tasks/{task_id}", response_model=TaskRecord)
async def get_task(task_id: str) -> TaskRecord:
    task = task_store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.get("/approvals")
async def list_approvals(task_id: Optional[str] = None):
    return [a.model_dump() for a in approval_queue.list_pending(task_id=task_id)]


@router.post("/approvals/{approval_id}")
async def resolve_approval(approval_id: str, body: ApprovalResolve):
    try:
        req = approval_queue.resolve(approval_id, body)
    except KeyError:
        raise HTTPException(404, "Approval not found") from None
    return req.model_dump()


@router.get("/traces/{task_id}")
async def get_trace(task_id: str):
    spans = trace_store.list_spans(task_id)
    tokens = trace_store.token_summary(task_id)
    return {
        "task_id": task_id,
        "spans": spans,
        "tokens": tokens,
        "cost_proxy_usd": 0.0,  # backlog: honest cost model
        "jaeger_ui": "http://localhost:16686",
    }


@router.get("/replay/{task_id}")
async def replay_task(task_id: str):
    from orchestrator.llm.transcript import transcript_store

    turns = transcript_store.list_turns(task_id)
    return {
        "task_id": task_id,
        "turns": turns,
        "turn_count": len(turns),
    }


@router.get("/memory")
async def browse_memory(limit: int = 50):
    return semantic_memory.list_all(limit=limit)


@router.get("/memory/working/{task_id}")
async def working(task_id: str):
    return working_memory.dump(task_id)


@router.get("/tools")
async def list_tools():
    register_default_tools()
    return tool_registry.list_tools()
