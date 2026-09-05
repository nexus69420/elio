from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_DIR = REPO_ROOT / "mcp_servers"
PYTHON = sys.executable

# Tool name suffixes (after mcp_{server}_) that mutate external state → HITL gate
SENSITIVE_TOOL_SUFFIXES = (
    "create_issue",
    "comment_on_issue",
    "create_or_update_file",
    "fs_write",
    "fs_mkdir",
    "fs_delete",
    "post_message",
    "slack_post_message",
    "github_create_issue",
    "github_comment_on_issue",
    "github_create_or_update_file",
)


def tool_requires_approval(reg_name: str, raw_tool_name: str = "") -> bool:
    blob = f"{reg_name} {raw_tool_name}".lower()
    if any(s in blob for s in ("_write", "_delete", "_mkdir", "post_message", "create_issue", "comment_on", "create_or_update")):
        return True
    # Built-ins that leave the process sandbox with side effects outside "answer only"
    if reg_name in {"file_write"}:
        return False  # still sandboxed under data/workspace; filesystem MCP is the real escape hatch
    return False


def _server_script(name: str) -> str:
    return str((MCP_DIR / name).resolve())


CONNECTOR_CATALOG: list[dict[str, Any]] = [
    {
        "id": "github",
        "name": "GitHub",
        "description": "Connect with GitHub (OAuth consent) — issues, PRs, and repo files via the real API.",
        "category": "dev",
        "docs_url": "https://github.com/settings/applications/new",
        "server_name": "github",
        "capabilities": ["OAuth connect", "read issues", "create issues", "comment", "read/write files", "list PRs"],
        "hitl_writes": True,
        "secret_fields": [
            {
                "key": "GITHUB_TOKEN",
                "label": "Personal access token (fallback)",
                "placeholder": "ghp_… or github_pat_…",
                "help": "Prefer Connect with GitHub. PAT is only for advanced/manual setup.",
            }
        ],
        "config_fields": [
            {
                "key": "GITHUB_DEFAULT_OWNER",
                "label": "Default owner / org",
                "placeholder": "your-username",
                "optional": True,
            }
        ],
        "script": "github_server.py",
    },
    {
        "id": "filesystem",
        "name": "Filesystem",
        "description": "Read and write files under a folder you choose — beyond the built-in sandbox workspace.",
        "category": "local",
        "docs_url": "",
        "server_name": "filesystem",
        "capabilities": ["list", "read", "write", "mkdir", "delete"],
        "hitl_writes": True,
        "secret_fields": [],
        "config_fields": [
            {
                "key": "FILESYSTEM_ROOT",
                "label": "Root folder",
                "placeholder": str((REPO_ROOT / "data" / "workspace").resolve()),
                "optional": False,
                "help": "Agents cannot escape this directory.",
            }
        ],
        "script": "filesystem_server.py",
    },
    {
        "id": "slack",
        "name": "Slack",
        "description": "List channels, read recent history, and post messages with a Slack bot token.",
        "category": "comms",
        "docs_url": "https://api.slack.com/apps",
        "server_name": "slack",
        "capabilities": ["auth test", "list channels", "post message", "channel history"],
        "hitl_writes": True,
        "secret_fields": [
            {
                "key": "SLACK_BOT_TOKEN",
                "label": "Bot token",
                "placeholder": "xoxb-…",
                "help": "Needs channels:read, chat:write, channels:history (and invite the bot to channels).",
            }
        ],
        "config_fields": [],
        "script": "slack_server.py",
    },
    {
        "id": "demo",
        "name": "Demo (smoke test)",
        "description": "Local echo / time tools — no external account. Use to verify MCP wiring.",
        "category": "local",
        "docs_url": "",
        "server_name": "demo",
        "capabilities": ["get_time", "echo", "add_numbers"],
        "hitl_writes": False,
        "secret_fields": [],
        "config_fields": [],
        "script": "demo_server.py",
    },
]


def catalog_public() -> list[dict[str, Any]]:
    return [
        {
            "id": c["id"],
            "name": c["name"],
            "description": c["description"],
            "category": c["category"],
            "docs_url": c.get("docs_url") or "",
            "server_name": c["server_name"],
            "capabilities": c.get("capabilities") or [],
            "hitl_writes": bool(c.get("hitl_writes")),
            "secret_fields": [
                {k: v for k, v in f.items() if k != "value"} for f in (c.get("secret_fields") or [])
            ],
            "config_fields": list(c.get("config_fields") or []),
        }
        for c in CONNECTOR_CATALOG
    ]


def get_pack(connector_id: str) -> Optional[dict[str, Any]]:
    for c in CONNECTOR_CATALOG:
        if c["id"] == connector_id:
            return c
    return None


def build_server_config(
    connector_id: str,
    *,
    secrets: dict[str, str],
    config: dict[str, str],
) -> dict[str, Any]:
    pack = get_pack(connector_id)
    if not pack:
        raise KeyError(connector_id)
    env: dict[str, str] = {}
    for field in pack.get("secret_fields") or []:
        key = field["key"]
        val = (secrets.get(key) or "").strip()
        if not val and not field.get("optional"):
            # allow empty only if already stored elsewhere — caller merges
            pass
        if val:
            env[key] = val
    for field in pack.get("config_fields") or []:
        key = field["key"]
        val = (config.get(key) or "").strip()
        if not val and key == "FILESYSTEM_ROOT":
            val = str((REPO_ROOT / "data" / "workspace").resolve())
        if val:
            env[key] = val
    return {
        "name": pack["server_name"],
        "command": PYTHON,
        "args": [_server_script(pack["script"])],
        "env": env,
        "connector_id": connector_id,
    }
