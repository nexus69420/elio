from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from orchestrator.config import settings
from orchestrator.tools.registry import ToolSpec, tool_registry

logger = logging.getLogger(__name__)


def _default_demo_server() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]  # repo root from src/orchestrator/tools
    # src/orchestrator/tools -> parents[0]=tools, [1]=orchestrator, [2]=src, [3]=repo
    server = root / "mcp_servers" / "demo_server.py"
    return {
        "name": "demo",
        "command": sys.executable,
        "args": [str(server)],
    }


def _parse_servers() -> list[dict[str, Any]]:
    raw = (settings.mcp_servers or "").strip()
    if raw:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        raise ValueError("MCP_SERVERS must be a JSON list")
    # Default: ship the local demo MCP server when enabled
    return [_default_demo_server()]


def _make_handler(server_name: str, tool_name: str):
    def handler(**kwargs: Any) -> Any:
        return asyncio.run(_call_mcp_tool(server_name, tool_name, kwargs))

    return handler


async def _call_mcp_tool(server_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    servers = {s["name"]: s for s in _parse_servers()}
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
            # Normalize content blocks
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


def register_mcp_tools() -> list[str]:
    """Discover MCP servers and register tools into the shared registry. Returns registered names."""
    if not settings.mcp_enabled:
        return []
    registered: list[str] = []
    try:
        servers = _parse_servers()
    except Exception as exc:  # noqa: BLE001
        logger.warning("MCP config invalid: %s", exc)
        return []

    for cfg in servers:
        name = cfg.get("name") or "mcp"
        try:
            tools = asyncio.run(_list_mcp_tools(cfg))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load MCP server %s: %s", name, exc)
            continue
        for tool in tools:
            # Prefix to avoid collisions with built-ins
            reg_name = f"mcp_{name}_{tool['name']}"
            if any(t["name"] == reg_name for t in tool_registry.list_tools()):
                continue
            tool_registry.register(
                ToolSpec(
                    name=reg_name,
                    description=f"[MCP:{name}] {tool.get('description') or tool['name']}",
                    parameters=tool.get("inputSchema") or {"type": "object", "properties": {}},
                    handler=_make_handler(name, tool["name"]),
                    timeout_sec=30,
                )
            )
            registered.append(reg_name)
    return registered
