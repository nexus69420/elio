from __future__ import annotations

"""In-process GitHub tools (no MCP subprocess).

Celery on Windows cannot reliably spawn MCP stdio servers (LoggingProxy.fileno).
These tools call the GitHub API directly with the OAuth token stored in Redis.
"""

import base64
from typing import Any, Optional

import httpx

from orchestrator.tools.registry import ToolSpec, tool_registry

API_BASE = "https://api.github.com"
NATIVE_PREFIX = "github_"


def _creds() -> tuple[str, str]:
    from orchestrator.runtime_mcp import runtime_mcp

    secrets = runtime_mcp._secrets().get("github") or {}  # noqa: SLF001
    cfg = (runtime_mcp._overlay().get("connector_config") or {}).get("github") or {}  # noqa: SLF001
    # Also merge live server env if present
    for s in runtime_mcp.get().get("servers") or []:
        if (s.get("connector_id") or s.get("name")) == "github":
            env = s.get("env") or {}
            if env.get("GITHUB_TOKEN"):
                secrets = {**secrets, **{k: v for k, v in env.items() if v}}
            if env.get("GITHUB_DEFAULT_OWNER"):
                cfg = {**cfg, "GITHUB_DEFAULT_OWNER": env["GITHUB_DEFAULT_OWNER"]}
    token = (secrets.get("GITHUB_TOKEN") or "").strip()
    owner = (cfg.get("GITHUB_DEFAULT_OWNER") or "").strip()
    return token, owner


def _github_connected() -> bool:
    from orchestrator.runtime_mcp import runtime_mcp

    for s in runtime_mcp.get().get("servers") or []:
        if (s.get("connector_id") or s.get("name")) == "github":
            return True
    token, _ = _creds()
    return bool(token)


def _headers(token: str) -> dict[str, str]:
    if not token:
        raise RuntimeError("GitHub is not connected — use Connectors → Connect with GitHub")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "agent-orchestration",
    }


def _get(path: str, params: Optional[dict] = None) -> Any:
    token, _ = _creds()
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{API_BASE}{path}", headers=_headers(token), params=params or {})
        r.raise_for_status()
        return r.json()


def _post(path: str, body: dict[str, Any]) -> Any:
    token, _ = _creds()
    with httpx.Client(timeout=30.0) as client:
        r = client.post(f"{API_BASE}{path}", headers=_headers(token), json=body)
        r.raise_for_status()
        return r.json()


def _put(path: str, body: dict[str, Any]) -> Any:
    token, _ = _creds()
    with httpx.Client(timeout=30.0) as client:
        r = client.put(f"{API_BASE}{path}", headers=_headers(token), json=body)
        r.raise_for_status()
        return r.json()


def _repo(owner: Optional[str], repo: str) -> str:
    _, default_owner = _creds()
    o = (owner or default_owner or "").strip()
    if not o:
        raise ValueError("owner is required (set default owner when connecting GitHub)")
    return f"{o}/{repo}"


def github_whoami() -> dict[str, Any]:
    u = _get("/user")
    return {"login": u.get("login"), "name": u.get("name"), "html_url": u.get("html_url")}


def github_list_repos(per_page: int = 20) -> list[dict[str, Any]]:
    """List repositories for the authenticated GitHub user. Use this to answer 'list my repos'."""
    repos = _get("/user/repos", {"per_page": min(int(per_page or 20), 50), "sort": "updated"})
    return [
        {
            "full_name": r.get("full_name"),
            "private": r.get("private"),
            "html_url": r.get("html_url"),
            "description": (r.get("description") or "")[:200],
        }
        for r in repos
    ]


def github_list_issues(
    repo: str,
    owner: Optional[str] = None,
    state: str = "open",
    per_page: int = 10,
) -> list[dict[str, Any]]:
    full = _repo(owner, repo)
    items = _get(f"/repos/{full}/issues", {"state": state, "per_page": min(int(per_page or 10), 30)})
    out = []
    for i in items:
        if i.get("pull_request"):
            continue
        out.append(
            {
                "number": i.get("number"),
                "title": i.get("title"),
                "state": i.get("state"),
                "html_url": i.get("html_url"),
            }
        )
    return out


def github_create_issue(
    repo: str,
    title: str,
    body: str = "",
    owner: Optional[str] = None,
) -> dict[str, Any]:
    full = _repo(owner, repo)
    i = _post(f"/repos/{full}/issues", {"title": title, "body": body or ""})
    return {"number": i.get("number"), "html_url": i.get("html_url"), "title": i.get("title")}


def github_list_pull_requests(
    repo: str,
    owner: Optional[str] = None,
    state: str = "open",
    per_page: int = 10,
) -> list[dict[str, Any]]:
    full = _repo(owner, repo)
    items = _get(f"/repos/{full}/pulls", {"state": state, "per_page": min(int(per_page or 10), 30)})
    return [
        {
            "number": p.get("number"),
            "title": p.get("title"),
            "state": p.get("state"),
            "html_url": p.get("html_url"),
        }
        for p in items
    ]


def github_get_file(
    repo: str,
    path: str,
    owner: Optional[str] = None,
    ref: Optional[str] = None,
) -> dict[str, Any]:
    full = _repo(owner, repo)
    params = {"ref": ref} if ref else None
    data = _get(f"/repos/{full}/contents/{path.lstrip('/')}", params)
    if isinstance(data, list):
        return {"error": "path is a directory", "entries": [e.get("path") for e in data[:50]]}
    content = data.get("content") or ""
    text = base64.b64decode(content).decode("utf-8", errors="replace") if data.get("encoding") == "base64" else ""
    return {
        "path": data.get("path"),
        "html_url": data.get("html_url"),
        "content": text[:8000],
        "truncated": len(text) > 8000,
    }


def register_native_github_tools(*, reload: bool = False) -> list[str]:
    """Register in-process GitHub tools when the connector has a token."""
    if reload:
        tool_registry.unregister_prefix(NATIVE_PREFIX)

    if not _github_connected():
        return []

    token, _ = _creds()
    if not token:
        return []

    specs = [
        ToolSpec(
            name="github_whoami",
            description="Return the authenticated GitHub user (login, name, url).",
            parameters={"type": "object", "properties": {}},
            handler=github_whoami,
        ),
        ToolSpec(
            name="github_list_repos",
            description="List the authenticated user's GitHub repositories. Prefer this for 'list my repos'. Returns full_name, private, html_url.",
            parameters={
                "type": "object",
                "properties": {"per_page": {"type": "integer", "description": "Max repos (default 20)"}},
            },
            handler=github_list_repos,
        ),
        ToolSpec(
            name="github_list_issues",
            description="List issues for a repository (excludes PRs).",
            parameters={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "owner": {"type": "string"},
                    "state": {"type": "string"},
                    "per_page": {"type": "integer"},
                },
                "required": ["repo"],
            },
            handler=github_list_issues,
        ),
        ToolSpec(
            name="github_create_issue",
            description="Create a GitHub issue. Requires human approval.",
            parameters={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "owner": {"type": "string"},
                },
                "required": ["repo", "title"],
            },
            handler=github_create_issue,
            requires_approval=True,
        ),
        ToolSpec(
            name="github_list_pull_requests",
            description="List pull requests for a repository.",
            parameters={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "owner": {"type": "string"},
                    "state": {"type": "string"},
                    "per_page": {"type": "integer"},
                },
                "required": ["repo"],
            },
            handler=github_list_pull_requests,
        ),
        ToolSpec(
            name="github_get_file",
            description="Read a file from a GitHub repository.",
            parameters={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "path": {"type": "string"},
                    "owner": {"type": "string"},
                    "ref": {"type": "string"},
                },
                "required": ["repo", "path"],
            },
            handler=github_get_file,
        ),
    ]

    registered: list[str] = []
    for spec in specs:
        if any(t["name"] == spec.name for t in tool_registry.list_tools()) and not reload:
            registered.append(spec.name)
            continue
        tool_registry.register(spec)
        registered.append(spec.name)
    return registered
