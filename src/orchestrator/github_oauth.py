from __future__ import annotations

import secrets
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
import redis

from orchestrator.config import settings

OAUTH_STATE_PREFIX = "orchestrator:github_oauth_state:"
OAUTH_STATE_TTL = 600


def _redis() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def get_oauth_app() -> dict[str, str]:
    """OAuth App credentials from Redis overlay or env."""
    from orchestrator.runtime_mcp import runtime_mcp

    overlay = runtime_mcp._overlay()  # noqa: SLF001
    stored = overlay.get("oauth") if isinstance(overlay.get("oauth"), dict) else {}
    gh = stored.get("github") if isinstance(stored.get("github"), dict) else {}
    client_id = (gh.get("client_id") or settings.github_oauth_client_id or "").strip()
    client_secret = (gh.get("client_secret") or settings.github_oauth_client_secret or "").strip()
    return {"client_id": client_id, "client_secret": client_secret}


def save_oauth_app(client_id: str, client_secret: str = "") -> dict[str, Any]:
    from orchestrator.runtime_mcp import runtime_mcp

    overlay = runtime_mcp._overlay()  # noqa: SLF001
    oauth = overlay.get("oauth") if isinstance(overlay.get("oauth"), dict) else {}
    bucket = dict(oauth.get("github") or {})
    if client_id.strip():
        bucket["client_id"] = client_id.strip()
    if client_secret.strip():
        bucket["client_secret"] = client_secret.strip()
    oauth["github"] = bucket
    overlay["oauth"] = oauth
    runtime_mcp._save(overlay)  # noqa: SLF001
    return oauth_status()


def oauth_status() -> dict[str, Any]:
    app = get_oauth_app()
    api_base = (settings.orchestrator_public_url or "http://127.0.0.1:8000").rstrip("/")
    frontend = (settings.frontend_public_url or "http://127.0.0.1:5173").rstrip("/")
    return {
        "configured": bool(app["client_id"] and app["client_secret"]),
        "client_id_set": bool(app["client_id"]),
        "client_secret_set": bool(app["client_secret"]),
        "client_id_masked": _mask(app["client_id"]) if app["client_id"] else "",
        "authorize_callback_url": f"{api_base}/oauth/github/callback",
        "frontend_url": frontend,
        "scopes": "repo read:user",
        "create_app_url": "https://github.com/settings/applications/new",
    }


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••••••"
    return f"{value[:4]}…{value[-4:]}"


def start_authorize(*, actor: str = "", default_owner: str = "") -> dict[str, str]:
    app = get_oauth_app()
    if not app["client_id"] or not app["client_secret"]:
        raise ValueError(
            "GitHub OAuth App not configured. Create one on GitHub, then save Client ID and Secret in Connectors."
        )
    state = secrets.token_urlsafe(24)
    api_base = (settings.orchestrator_public_url or "http://127.0.0.1:8000").rstrip("/")
    redirect_uri = f"{api_base}/oauth/github/callback"
    payload = {
        "actor": actor or "operator",
        "default_owner": default_owner or "",
        "redirect_uri": redirect_uri,
    }
    r = _redis()
    r.setex(f"{OAUTH_STATE_PREFIX}{state}", OAUTH_STATE_TTL, __import__("json").dumps(payload))
    params = {
        "client_id": app["client_id"],
        "redirect_uri": redirect_uri,
        "scope": "repo read:user",
        "state": state,
        "allow_signup": "true",
    }
    return {
        "authorize_url": f"https://github.com/login/oauth/authorize?{urlencode(params)}",
        "state": state,
        "redirect_uri": redirect_uri,
    }


async def finish_callback(*, code: str, state: str) -> dict[str, Any]:
    import json

    r = _redis()
    raw = r.get(f"{OAUTH_STATE_PREFIX}{state}")
    if not raw:
        raise ValueError("Invalid or expired OAuth state — try Connect again")
    r.delete(f"{OAUTH_STATE_PREFIX}{state}")
    meta = json.loads(raw)
    app = get_oauth_app()
    if not app["client_id"] or not app["client_secret"]:
        raise ValueError("OAuth App credentials missing")

    async with httpx.AsyncClient(timeout=30.0) as client:
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": app["client_id"],
                "client_secret": app["client_secret"],
                "code": code,
                "redirect_uri": meta.get("redirect_uri") or "",
            },
        )
        token_res.raise_for_status()
        token_data = token_res.json()
        access_token = (token_data.get("access_token") or "").strip()
        if not access_token:
            raise ValueError(token_data.get("error_description") or token_data.get("error") or "No access_token from GitHub")

        user_res = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "agent-orchestration",
            },
        )
        user_res.raise_for_status()
        user = user_res.json()

    login = user.get("login") or ""
    from orchestrator.runtime_mcp import ConnectorEnableBody, runtime_mcp

    owner = (meta.get("default_owner") or login or "").strip()
    runtime_mcp.enable_connector(
        "github",
        ConnectorEnableBody(
            secrets={"GITHUB_TOKEN": access_token},
            config={"GITHUB_DEFAULT_OWNER": owner} if owner else {},
        ),
    )
    try:
        from orchestrator.tools.mcp_bridge import register_mcp_tools

        register_mcp_tools(reload=True)
    except Exception:  # noqa: BLE001
        pass

    frontend = (settings.frontend_public_url or "http://127.0.0.1:5173").rstrip("/")
    return {
        "ok": True,
        "login": login,
        "redirect": f"{frontend}/?connected=github&user={login}",
        "actor": meta.get("actor") or "",
    }
