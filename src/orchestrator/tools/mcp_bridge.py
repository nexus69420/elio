from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any

from orchestrator.runtime_mcp import runtime_mcp
from orchestrator.connector_catalog import tool_requires_approval
from orchestrator.tools.registry import ToolSpec, tool_registry

logger = logging.getLogger(__name__)


def _run_coro(coro):
    """Run async MCP I/O safely from sync callers (API lifespan / Celery / FastAPI)."""
    import sys

    # Celery replaces stdout/stderr with LoggingProxy (no fileno) — breaks MCP stdio on Windows.
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is not None and not hasattr(stream, "fileno"):
            real = getattr(sys, f"__{name}__", None)
            if real is not None:
                setattr(sys, name, real)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    def _in_thread():
        for name in ("stdout", "stderr"):
            stream = getattr(sys, name, None)
            if stream is not None and not hasattr(stream, "fileno"):
                real = getattr(sys, f"__{name}__", None)
                if real is not None:
                    setattr(sys, name, real)
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_in_thread).result(timeout=60)


def _make_handler(server_name: str, tool_name: str):
    def handler(**kwargs: Any) -> Any:
        return _run_coro(_call_mcp_tool(server_name, tool_name, kwargs))

    return handler


async def _call_mcp_tool(server_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    cfg_block = runtime_mcp.get()
    servers = {s["name"]: s for s in cfg_block.get("servers") or []}
    cfg = servers.get(server_name)
    if not cfg:
        raise KeyError(f"Unknown MCP server {server_name}")

    params = StdioServerParameters(
        command=cfg["command"],
        args=cfg.get("args") or [],
        env=cfg.get("env"),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            texts = []
            for block in result.content or []:
                text = getattr(block, "text", None)
                if text is not None:
                    texts.append(text)
                else:
                    texts.append(str(block))
            return {"server": server_name, "tool": tool_name, "content": texts, "isError": bool(result.isError)}


async def _list_mcp_tools(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=cfg["command"],
        args=cfg.get("args") or [],
        env=cfg.get("env"),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            out = []
            for tool in listed.tools:
                out.append(
                    {
                        "name": tool.name,
                        "description": tool.description or "",
                        "inputSchema": tool.inputSchema or {"type": "object", "properties": {}},
                    }
                )
            return out


def probe_mcp_server(cfg: dict[str, Any]) -> dict[str, Any]:
    name = cfg.get("name") or "mcp"
    try:
        tools = _run_coro(_list_mcp_tools(cfg))
        return {"name": name, "ok": True, "tools": tools, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"name": name, "ok": False, "tools": [], "error": str(exc)}


def register_mcp_tools(*, reload: bool = False) -> dict[str, Any]:
    """Discover MCP servers and register tools. Returns status payload for the Connectors UI."""
    if reload:
        tool_registry.unregister_prefix("mcp_")

    cfg = runtime_mcp.get()
    if not cfg.get("enabled"):
        return {"enabled": False, "registered": [], "servers": [], "error": None}

    registered: list[str] = []
    server_status: list[dict[str, Any]] = []
    for server in cfg.get("servers") or []:
        name = server.get("name") or "mcp"
        probe = probe_mcp_server(server)
        server_status.append(
            {
                **probe,
                "command": server.get("command"),
                "args": server.get("args") or [],
            }
        )
        if not probe["ok"]:
            logger.warning("Failed to load MCP server %s: %s", name, probe["error"])
            continue
        for tool in probe["tools"]:
            raw_name = tool["name"]
            # Avoid mcp_github_github_list_repos — strip redundant server prefix from tool name
            short = raw_name
            prefix = f"{name}_"
            if short.startswith(prefix):
                short = short[len(prefix) :]
            reg_name = f"mcp_{name}_{short}"
            if any(t["name"] == reg_name for t in tool_registry.list_tools()):
                registered.append(reg_name)
                continue
            tool_registry.register(
                ToolSpec(
                    name=reg_name,
                    description=f"[MCP:{name}] {tool.get('description') or raw_name}",
                    parameters=tool.get("inputSchema") or {"type": "object", "properties": {}},
                    handler=_make_handler(name, raw_name),
                    timeout_sec=45,
                    requires_approval=tool_requires_approval(reg_name, raw_name),
                )
            )
            registered.append(reg_name)

    return {"enabled": True, "registered": registered, "servers": server_status, "error": None}
