from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from orchestrator.audit import audit_log
from orchestrator.auth import require_actor
from orchestrator.costing import estimate_task_cost, price_sheet_public
from orchestrator.hitl.queue import approval_queue
from orchestrator.memory.semantic import semantic_memory
from orchestrator.memory.working import working_memory
from orchestrator.schemas import ApprovalResolve, TaskCreate, TaskRecord, TaskStatus
from orchestrator.store import task_store
from orchestrator.titles import title_from_prompt
from orchestrator.tools import register_default_tools, tool_registry
from orchestrator.tracing.spans import trace_store
from orchestrator.worker import run_task_job

router = APIRouter(prefix="/v1", dependencies=[Depends(require_actor)])


@router.post("/tasks", response_model=TaskRecord)
async def create_task(body: TaskCreate, actor: str = Depends(require_actor)) -> TaskRecord:
    register_default_tools()
    title = title_from_prompt(body.prompt)
    preset_id = (body.preset_id or "").strip()
    if preset_id:
        from orchestrator.runtime_agents import runtime_agents

        if not runtime_agents.get_preset(preset_id):
            raise HTTPException(400, f"Unknown preset_id: {preset_id}")
    task = TaskRecord(
        prompt=body.prompt,
        title=title,
        force_hitl=body.force_hitl,
        preset_id=preset_id,
        status=TaskStatus.queued,
        created_by=actor,
    )
    task_store.save(task)
    audit_log.record(
        action="task.created",
        actor=actor,
        task_id=task.id,
        resource_type="task",
        resource_id=task.id,
        detail={
            "force_hitl": body.force_hitl,
            "prompt_chars": len(body.prompt),
            "title": title,
            "preset_id": preset_id or None,
        },
    )
    run_task_job.delay(task.id, body.prompt, body.force_hitl, preset_id)
    return task


@router.get("/tasks", response_model=list[TaskRecord])
async def list_tasks(limit: int = 20) -> list[TaskRecord]:
    tasks = task_store.list_recent(limit=limit)
    for t in tasks:
        if not t.title:
            t.title = title_from_prompt(t.prompt)
        # Orphan gates: status stuck on awaiting_approval but nothing in the HITL queue
        if t.status == TaskStatus.awaiting_approval:
            pending = approval_queue.list_pending(task_id=t.id)
            if not pending:
                t.status = TaskStatus.failed
                t.error = t.error or "Stuck awaiting approval with no pending gate (worker likely restarted)."
                task_store.save(t)
        # Dead queue messages after worker restarts
        elif t.status == TaskStatus.queued:
            from datetime import datetime, timezone

            try:
                created = datetime.fromisoformat(t.created_at.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - created).total_seconds()
            except Exception:  # noqa: BLE001
                age = 0
            if age > 120:
                t.status = TaskStatus.failed
                t.error = t.error or "Task stayed queued too long — Celery worker was likely down."
                task_store.save(t)
    return tasks


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
async def resolve_approval(approval_id: str, body: ApprovalResolve, actor: str = Depends(require_actor)):
    if not body.actor:
        body.actor = actor
    try:
        req = approval_queue.resolve(approval_id, body)
    except KeyError:
        raise HTTPException(404, "Approval not found") from None
    audit_log.record(
        action="approval.resolved",
        actor=body.actor or actor,
        task_id=req.task_id,
        resource_type="approval",
        resource_id=approval_id,
        detail={"action": body.action, "status": req.status.value},
    )
    return req.model_dump()


@router.get("/traces/{task_id}")
async def get_trace(task_id: str):
    from orchestrator.llm.transcript import transcript_store

    spans = trace_store.list_spans(task_id)
    tokens = trace_store.token_summary(task_id)
    turns = transcript_store.list_turns(task_id)
    cost = estimate_task_cost(turns)
    return {
        "task_id": task_id,
        "spans": spans,
        "tokens": tokens,
        "cost_proxy_usd": cost["cost_usd"],
        "cost": cost,
        "jaeger_ui": "http://localhost:16686",
    }


@router.get("/costs")
async def list_costs(limit: int = 20):
    """Roll up estimated USD cost across recent tasks from transcripts."""
    tasks = task_store.list_recent(limit=limit)
    from orchestrator.llm.transcript import transcript_store

    rows = []
    total = 0.0
    for t in tasks:
        turns = transcript_store.list_turns(t.id)
        cost = estimate_task_cost(turns)
        total += cost["cost_usd"]
        rows.append(
            {
                "task_id": t.id,
                "status": t.status.value if hasattr(t.status, "value") else t.status,
                "prompt_preview": (t.prompt or "")[:120],
                "cost_usd": cost["cost_usd"],
                "total_tokens": cost["total_tokens"],
                "by_model": cost["by_model"],
            }
        )
    return {
        "tasks": rows,
        "total_cost_usd": round(total, 8),
        "price_sheet": price_sheet_public(),
        "note": "Ollama/stub priced at $0; cloud rates are approximate public list prices per 1M tokens.",
    }


@router.get("/replay/{task_id}")
async def replay_task(task_id: str):
    from orchestrator.llm.transcript import transcript_store

    turns = transcript_store.list_turns(task_id)
    return {
        "task_id": task_id,
        "turns": turns,
        "turn_count": len(turns),
        "cost": estimate_task_cost(turns),
    }


@router.get("/audit")
async def list_audit(limit: int = 50, task_id: Optional[str] = None, action: Optional[str] = None):
    return audit_log.list_recent(limit=limit, task_id=task_id, action=action)


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


@router.get("/settings/llm")
async def get_llm_settings():
    from orchestrator.runtime_llm import runtime_llm

    return runtime_llm.public_view()


@router.put("/settings/llm")
async def put_llm_settings(body: dict, actor: str = Depends(require_actor)):
    from orchestrator.runtime_llm import LLMSettingsUpdate, runtime_llm

    try:
        update = LLMSettingsUpdate.model_validate(body)
        view = runtime_llm.update(update)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    audit_log.record(
        action="settings.llm_updated",
        actor=actor,
        resource_type="settings",
        resource_id="llm",
        detail={"llm_provider": view.get("llm_provider")},
    )
    return view


@router.post("/settings/llm/test")
async def test_llm_settings():
    """Smoke-check the currently saved provider (after Save)."""
    from orchestrator.llm.client import llm_client

    health = await llm_client.health()
    if not health.get("ok"):
        return {"ok": False, "health": health}
    try:
        resp = await llm_client.chat(
            messages=[
                {"role": "system", "content": "Reply with exactly: pong"},
                {"role": "user", "content": "ping"},
            ],
            temperature=0,
            role="specialist",
        )
        return {
            "ok": True,
            "health": health,
            "sample": (resp.get("content") or "")[:200],
            "model": resp.get("model"),
            "provider": resp.get("provider"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "health": health, "error": str(exc)}


@router.get("/connectors")
async def get_connectors():
    """Built-in tools + MCP server status + app catalog for the Connectors page."""
    register_default_tools()
    from orchestrator.runtime_mcp import runtime_mcp
    from orchestrator.tools.mcp_bridge import register_mcp_tools

    mcp_status = register_mcp_tools(reload=False)
    builtins = [t for t in tool_registry.list_tools() if not t["name"].startswith("mcp_")]
    mcp_tools = [t for t in tool_registry.list_tools() if t["name"].startswith("mcp_")]
    public = runtime_mcp.public_view()
    cfg = runtime_mcp.get()
    return {
        "builtins": builtins,
        "mcp": {
            "enabled": cfg.get("enabled"),
            "servers_config": public.get("servers") or [],
            "servers": mcp_status.get("servers") or [],
            "registered_tools": mcp_tools,
        },
        "catalog": public.get("catalog") or [],
        "github_oauth": public.get("github_oauth") or {},
        "code_sandbox": __import__("orchestrator.config", fromlist=["settings"]).settings.code_sandbox,
    }


@router.post("/connectors/{connector_id}/enable")
async def enable_connector(connector_id: str, body: dict, actor: str = Depends(require_actor)):
    from orchestrator.runtime_mcp import ConnectorEnableBody, runtime_mcp
    from orchestrator.tools.mcp_bridge import register_mcp_tools

    try:
        update = ConnectorEnableBody.model_validate(body or {})
        public = runtime_mcp.enable_connector(connector_id, update)
    except KeyError as exc:
        raise HTTPException(404, f"Unknown connector: {connector_id}") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc
    status = register_mcp_tools(reload=True)
    audit_log.record(
        action="connectors.enabled",
        actor=actor,
        resource_type="connector",
        resource_id=connector_id,
        detail={"registered": len(status.get("registered") or [])},
    )
    return {"catalog": public.get("catalog"), "status": status, "mcp": public}


@router.post("/connectors/{connector_id}/disable")
async def disable_connector(connector_id: str, actor: str = Depends(require_actor)):
    from orchestrator.runtime_mcp import runtime_mcp
    from orchestrator.tools.mcp_bridge import register_mcp_tools

    public = runtime_mcp.disable_connector(connector_id)
    status = register_mcp_tools(reload=True)
    audit_log.record(
        action="connectors.disabled",
        actor=actor,
        resource_type="connector",
        resource_id=connector_id,
        detail={},
    )
    return {"catalog": public.get("catalog"), "status": status}


@router.get("/connectors/github/oauth")
async def github_oauth_info():
    from orchestrator.github_oauth import oauth_status

    return oauth_status()


@router.put("/connectors/github/oauth")
async def github_oauth_save(body: dict, actor: str = Depends(require_actor)):
    from orchestrator.github_oauth import save_oauth_app

    client_id = (body.get("client_id") or "").strip()
    client_secret = (body.get("client_secret") or "").strip()
    if not client_id and not client_secret:
        raise HTTPException(400, "Provide client_id and/or client_secret")
    status = save_oauth_app(client_id=client_id, client_secret=client_secret)
    audit_log.record(
        action="connectors.github_oauth_configured",
        actor=actor,
        resource_type="connector",
        resource_id="github",
        detail={"client_id_set": status.get("client_id_set")},
    )
    return status


@router.post("/connectors/github/oauth/start")
async def github_oauth_start(body: dict | None = None, actor: str = Depends(require_actor)):
    from orchestrator.github_oauth import start_authorize

    body = body or {}
    try:
        started = start_authorize(actor=actor, default_owner=(body.get("default_owner") or "").strip())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    audit_log.record(
        action="connectors.github_oauth_started",
        actor=actor,
        resource_type="connector",
        resource_id="github",
        detail={},
    )
    return started


@router.put("/connectors/mcp")
async def put_mcp_connectors(body: dict, actor: str = Depends(require_actor)):
    from orchestrator.runtime_mcp import McpRuntimeUpdate, runtime_mcp
    from orchestrator.tools.mcp_bridge import register_mcp_tools

    try:
        update = McpRuntimeUpdate.model_validate(body)
        cfg = runtime_mcp.update(update)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc
    status = register_mcp_tools(reload=True)
    audit_log.record(
        action="connectors.mcp_updated",
        actor=actor,
        resource_type="connectors",
        resource_id="mcp",
        detail={"enabled": cfg.get("enabled"), "server_count": len(cfg.get("servers") or [])},
    )
    return {"config": cfg, "status": status}


@router.post("/connectors/mcp/reload")
async def reload_mcp_connectors(actor: str = Depends(require_actor)):
    from orchestrator.tools.mcp_bridge import register_mcp_tools

    status = register_mcp_tools(reload=True)
    audit_log.record(
        action="connectors.mcp_reloaded",
        actor=actor,
        resource_type="connectors",
        resource_id="mcp",
        detail={"registered": len(status.get("registered") or [])},
    )
    return status


@router.get("/agents")
async def get_agents():
    register_default_tools()
    from orchestrator.runtime_agents import runtime_agents
    from orchestrator.tools.mcp_bridge import register_mcp_tools

    register_mcp_tools(reload=False)
    tools = [t["name"] for t in tool_registry.list_tools()]
    return runtime_agents.public_snapshot(available_tools=tools)


@router.put("/agents/{agent_id}")
async def put_agent(agent_id: str, body: dict, actor: str = Depends(require_actor)):
    from orchestrator.runtime_agents import AgentProfileUpdate, runtime_agents

    try:
        update = AgentProfileUpdate.model_validate(body)
        agent = runtime_agents.update_agent(agent_id, update)
    except KeyError as exc:
        raise HTTPException(404, f"Unknown agent: {agent_id}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc
    audit_log.record(
        action="agents.updated",
        actor=actor,
        resource_type="agent",
        resource_id=agent_id,
        detail={
            "display_name": agent.get("display_name"),
            "model": agent.get("model") or None,
            "tools": agent.get("tools"),
            "requires_hitl": agent.get("requires_hitl"),
            "instructions_chars": len(agent.get("instructions") or ""),
        },
    )
    return agent


@router.post("/agents/reset")
async def reset_agents(actor: str = Depends(require_actor)):
    from orchestrator.runtime_agents import runtime_agents

    snap = runtime_agents.reset_defaults()
    audit_log.record(
        action="agents.reset",
        actor=actor,
        resource_type="agents",
        resource_id="team",
        detail={},
    )
    register_default_tools()
    from orchestrator.tools.mcp_bridge import register_mcp_tools

    register_mcp_tools(reload=False)
    tools = [t["name"] for t in tool_registry.list_tools()]
    snap["available_tools"] = tools
    return snap


@router.post("/agents/presets/{preset_id}/apply")
async def apply_agent_preset(preset_id: str, actor: str = Depends(require_actor)):
    from orchestrator.runtime_agents import runtime_agents

    try:
        snap = runtime_agents.apply_preset(preset_id)
    except KeyError as exc:
        raise HTTPException(404, f"Unknown preset: {preset_id}") from exc
    audit_log.record(
        action="agents.preset_applied",
        actor=actor,
        resource_type="agent_preset",
        resource_id=preset_id,
        detail={"name": next((p["name"] for p in snap["presets"] if p["id"] == preset_id), preset_id)},
    )
    register_default_tools()
    from orchestrator.tools.mcp_bridge import register_mcp_tools

    register_mcp_tools(reload=False)
    snap["available_tools"] = [t["name"] for t in tool_registry.list_tools()]
    return snap


@router.post("/agents/presets")
async def save_agent_preset(body: dict, actor: str = Depends(require_actor)):
    from orchestrator.runtime_agents import runtime_agents

    preset_id = (body.get("id") or "").strip()
    name = (body.get("name") or "").strip()
    if not preset_id or not name:
        raise HTTPException(400, "id and name are required")
    try:
        snap = runtime_agents.save_preset_from_current(
            preset_id=preset_id,
            name=name,
            description=body.get("description") or "",
            force_hitl=bool(body.get("force_hitl", True)),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    audit_log.record(
        action="agents.preset_saved",
        actor=actor,
        resource_type="agent_preset",
        resource_id=preset_id,
        detail={"name": name},
    )
    register_default_tools()
    from orchestrator.tools.mcp_bridge import register_mcp_tools

    register_mcp_tools(reload=False)
    snap["available_tools"] = [t["name"] for t in tool_registry.list_tools()]
    return snap
