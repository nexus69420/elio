#!/usr/bin/env python3
"""Slack MCP server — list channels and post messages.

Env:
  SLACK_BOT_TOKEN  Bot User OAuth Token (xoxb-...)
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("orchestrator-slack")

TOKEN = (os.environ.get("SLACK_BOT_TOKEN") or "").strip()
API = "https://slack.com/api"


def _headers() -> dict[str, str]:
    if not TOKEN:
        raise RuntimeError("SLACK_BOT_TOKEN is not set — connect Slack in Mission Control → Connectors")
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json; charset=utf-8"}


def _api(method: str, payload: Optional[dict] = None) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        r = client.post(f"{API}/{method}", headers=_headers(), json=payload or {})
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("error") or "slack api error")
        return data


@mcp.tool()
def slack_auth_test() -> dict[str, Any]:
    """Verify the bot token and return team/user identity."""
    data = _api("auth.test")
    return {
        "team": data.get("team"),
        "user": data.get("user"),
        "bot_id": data.get("bot_id"),
        "url": data.get("url"),
    }


@mcp.tool()
def slack_list_channels(limit: int = 20) -> list[dict[str, Any]]:
    """List public channels the bot can see."""
    data = _api(
        "conversations.list",
        {"limit": min(limit, 100), "types": "public_channel", "exclude_archived": True},
    )
    return [
        {"id": c.get("id"), "name": c.get("name"), "is_member": c.get("is_member")}
        for c in (data.get("channels") or [])
    ]


@mcp.tool()
def slack_post_message(channel: str, text: str) -> dict[str, Any]:
    """Post a message to a channel (#name or C…). Requires human approval in Mission Control."""
    data = _api("chat.postMessage", {"channel": channel, "text": text})
    return {
        "channel": data.get("channel"),
        "ts": data.get("ts"),
        "message": ((data.get("message") or {}).get("text") or "")[:500],
    }


@mcp.tool()
def slack_get_channel_history(channel: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch recent messages from a channel the bot is in."""
    data = _api("conversations.history", {"channel": channel, "limit": min(limit, 50)})
    return [
        {
            "user": m.get("user"),
            "text": (m.get("text") or "")[:500],
            "ts": m.get("ts"),
        }
        for m in (data.get("messages") or [])
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")
