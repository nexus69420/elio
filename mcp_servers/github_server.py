#!/usr/bin/env python3
"""GitHub MCP server — issues, PRs, and repo files via the GitHub REST API.

Env:
  GITHUB_TOKEN          required (classic PAT or fine-grained with repo scope)
  GITHUB_DEFAULT_OWNER  optional default owner/org
  GITHUB_API_BASE       optional (default https://api.github.com)
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("orchestrator-github")

TOKEN = (os.environ.get("GITHUB_TOKEN") or "").strip()
DEFAULT_OWNER = (os.environ.get("GITHUB_DEFAULT_OWNER") or "").strip()
API_BASE = (os.environ.get("GITHUB_API_BASE") or "https://api.github.com").rstrip("/")


def _headers() -> dict[str, str]:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is not set — connect GitHub in Mission Control → Connectors")
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "agent-orchestration",
    }


def _repo(owner: Optional[str], repo: str) -> str:
    o = (owner or DEFAULT_OWNER or "").strip()
    if not o:
        raise ValueError("owner is required (or set GITHUB_DEFAULT_OWNER)")
    return f"{o}/{repo}"


def _get(path: str, params: Optional[dict] = None) -> Any:
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{API_BASE}{path}", headers=_headers(), params=params or {})
        r.raise_for_status()
        return r.json()


def _post(path: str, body: dict[str, Any]) -> Any:
    with httpx.Client(timeout=30.0) as client:
        r = client.post(f"{API_BASE}{path}", headers=_headers(), json=body)
        r.raise_for_status()
        return r.json()


def _put(path: str, body: dict[str, Any]) -> Any:
    with httpx.Client(timeout=30.0) as client:
        r = client.put(f"{API_BASE}{path}", headers=_headers(), json=body)
        r.raise_for_status()
        return r.json()


@mcp.tool()
def github_whoami() -> dict[str, Any]:
    """Return the authenticated GitHub user."""
    u = _get("/user")
    return {"login": u.get("login"), "name": u.get("name"), "html_url": u.get("html_url")}


@mcp.tool()
def github_list_repos(per_page: int = 10) -> list[dict[str, Any]]:
    """List repositories for the authenticated user."""
    repos = _get("/user/repos", {"per_page": min(per_page, 30), "sort": "updated"})
    return [
        {
            "full_name": r.get("full_name"),
            "private": r.get("private"),
            "html_url": r.get("html_url"),
            "description": (r.get("description") or "")[:200],
        }
        for r in repos
    ]


@mcp.tool()
def github_list_issues(
    repo: str,
    owner: Optional[str] = None,
    state: str = "open",
    per_page: int = 10,
) -> list[dict[str, Any]]:
    """List issues for a repository (excludes PRs)."""
    full = _repo(owner, repo)
    items = _get(f"/repos/{full}/issues", {"state": state, "per_page": min(per_page, 30)})
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
                "user": (i.get("user") or {}).get("login"),
            }
        )
    return out


@mcp.tool()
def github_get_issue(repo: str, number: int, owner: Optional[str] = None) -> dict[str, Any]:
    """Get a single issue by number."""
    full = _repo(owner, repo)
    i = _get(f"/repos/{full}/issues/{number}")
    return {
        "number": i.get("number"),
        "title": i.get("title"),
        "state": i.get("state"),
        "body": (i.get("body") or "")[:4000],
        "html_url": i.get("html_url"),
        "labels": [x.get("name") for x in (i.get("labels") or [])],
    }


@mcp.tool()
def github_create_issue(
    repo: str,
    title: str,
    body: str = "",
    owner: Optional[str] = None,
    labels: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create a GitHub issue. Requires human approval in Mission Control."""
    full = _repo(owner, repo)
    payload: dict[str, Any] = {"title": title, "body": body or ""}
    if labels:
        payload["labels"] = labels
    i = _post(f"/repos/{full}/issues", payload)
    return {"number": i.get("number"), "html_url": i.get("html_url"), "title": i.get("title")}


@mcp.tool()
def github_comment_on_issue(
    repo: str,
    number: int,
    body: str,
    owner: Optional[str] = None,
) -> dict[str, Any]:
    """Comment on an issue or PR. Requires human approval in Mission Control."""
    full = _repo(owner, repo)
    c = _post(f"/repos/{full}/issues/{number}/comments", {"body": body})
    return {"id": c.get("id"), "html_url": c.get("html_url")}


@mcp.tool()
def github_list_pull_requests(
    repo: str,
    owner: Optional[str] = None,
    state: str = "open",
    per_page: int = 10,
) -> list[dict[str, Any]]:
    """List pull requests for a repository."""
    full = _repo(owner, repo)
    items = _get(f"/repos/{full}/pulls", {"state": state, "per_page": min(per_page, 30)})
    return [
        {
            "number": p.get("number"),
            "title": p.get("title"),
            "state": p.get("state"),
            "html_url": p.get("html_url"),
            "user": (p.get("user") or {}).get("login"),
            "draft": p.get("draft"),
        }
        for p in items
    ]


@mcp.tool()
def github_get_file(
    repo: str,
    path: str,
    owner: Optional[str] = None,
    ref: Optional[str] = None,
) -> dict[str, Any]:
    """Read a file from a repository (decoded text, truncated)."""
    import base64

    full = _repo(owner, repo)
    params = {"ref": ref} if ref else None
    data = _get(f"/repos/{full}/contents/{path.lstrip('/')}", params)
    if isinstance(data, list):
        return {"error": "path is a directory", "entries": [e.get("path") for e in data[:50]]}
    content = data.get("content") or ""
    encoding = data.get("encoding")
    text = ""
    if encoding == "base64":
        text = base64.b64decode(content).decode("utf-8", errors="replace")
    return {
        "path": data.get("path"),
        "sha": data.get("sha"),
        "html_url": data.get("html_url"),
        "content": text[:8000],
        "truncated": len(text) > 8000,
    }


@mcp.tool()
def github_create_or_update_file(
    repo: str,
    path: str,
    content: str,
    message: str,
    owner: Optional[str] = None,
    branch: Optional[str] = None,
) -> dict[str, Any]:
    """Create or update a file via the Contents API. Requires human approval."""
    import base64

    full = _repo(owner, repo)
    # Need sha if updating
    sha = None
    try:
        existing = _get(f"/repos/{full}/contents/{path.lstrip('/')}", {"ref": branch} if branch else None)
        if isinstance(existing, dict):
            sha = existing.get("sha")
    except Exception:  # noqa: BLE001
        sha = None
    body: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
    }
    if sha:
        body["sha"] = sha
    if branch:
        body["branch"] = branch
    result = _put(f"/repos/{full}/contents/{path.lstrip('/')}", body)
    commit = result.get("commit") or {}
    return {
        "path": (result.get("content") or {}).get("path"),
        "html_url": (result.get("content") or {}).get("html_url"),
        "commit_sha": commit.get("sha"),
        "commit_url": commit.get("html_url"),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
