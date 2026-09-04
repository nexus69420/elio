#!/usr/bin/env python3
"""Minimal MCP stdio server exposing demo tools (time + echo).

Run via MCP client config — no paid APIs.
Requires: pip install mcp
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("orchestrator-demo")


@mcp.tool()
def get_time() -> str:
    """Return the current UTC timestamp."""
    return dt.datetime.now(dt.timezone.utc).isoformat()


@mcp.tool()
def echo(message: str) -> str:
    """Echo a message back (useful for MCP wiring smoke tests)."""
    return f"echo: {message}"


@mcp.tool()
def add_numbers(a: float, b: float) -> dict[str, Any]:
    """Add two numbers and return the sum."""
    return {"a": a, "b": b, "sum": a + b}


if __name__ == "__main__":
    mcp.run(transport="stdio")
