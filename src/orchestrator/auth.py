from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, Request

from orchestrator.config import settings


async def require_actor(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_actor: Optional[str] = Header(default=None, alias="X-Actor"),
) -> str:
    """
    When ORCHESTRATOR_API_TOKEN is set, require Bearer or X-API-Key.
    Always returns an actor string (from X-Actor, or 'api' / 'anonymous').
    """
    expected = (settings.orchestrator_api_token or "").strip()
    provided = (x_api_key or "").strip()
    if authorization and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()

    if expected:
        if not provided or provided != expected:
            raise HTTPException(status_code=401, detail="Invalid or missing API token")
        return (x_actor or "api").strip() or "api"

    # Auth disabled — still honor actor header for audit trails
    return (x_actor or "anonymous").strip() or "anonymous"
