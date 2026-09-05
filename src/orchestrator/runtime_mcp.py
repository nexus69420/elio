from __future__ import annotations

import json
from typing import Any, Optional

import redis
from pydantic import BaseModel, Field

from orchestrator.config import settings
from orchestrator.connector_catalog import build_server_config, catalog_public, get_pack

REDIS_KEY = "orchestrator:mcp_runtime"


class McpServerConfig(BaseModel):
    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: Optional[dict[str, str]] = None
    connector_id: Optional[str] = None


class McpRuntimeUpdate(BaseModel):
    enabled: Optional[bool] = None
    servers: Optional[list[McpServerConfig]] = None


class ConnectorEnableBody(BaseModel):
    secrets: dict[str, str] = Field(default_factory=dict)
    config: dict[str, str] = Field(default_factory=dict)


def _default_demo() -> dict[str, Any]:
    from orchestrator.connector_catalog import build_server_config

    return build_server_config("demo", secrets={}, config={})


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••••••"
    return f"{value[:3]}…{value[-4:]}"


class RuntimeMcpConfig:
    def __init__(self) -> None:
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        return self._client

    def _overlay(self) -> dict[str, Any]:
        try:
            raw = self.client.get(REDIS_KEY)
            if not raw:
                return {}
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001
            return {}

    def _save(self, overlay: dict[str, Any]) -> None:
        self.client.set(REDIS_KEY, json.dumps(overlay))

    def _env_servers(self) -> list[dict[str, Any]]:
        raw = (settings.mcp_servers or "").strip()
        if raw:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
            raise ValueError("MCP_SERVERS must be a JSON list")
        return [_default_demo()]

    def _secrets(self) -> dict[str, dict[str, str]]:
        overlay = self._overlay()
        raw = overlay.get("secrets") or {}
        return raw if isinstance(raw, dict) else {}

    def get(self) -> dict[str, Any]:
        """Runtime config with secrets merged into each server's env (for MCP spawn)."""
        overlay = self._overlay()
        enabled = overlay["enabled"] if "enabled" in overlay else bool(settings.mcp_enabled)
        if "servers" in overlay and isinstance(overlay["servers"], list):
            servers = [dict(s) for s in overlay["servers"]]
        else:
            try:
                servers = self._env_servers()
            except Exception:  # noqa: BLE001
                servers = [_default_demo()]

        secrets_by_connector = self._secrets()
        for s in servers:
            cid = s.get("connector_id") or s.get("name")
            stored = secrets_by_connector.get(cid) or secrets_by_connector.get(s.get("name") or "") or {}
            env = dict(s.get("env") or {})
            for k, v in stored.items():
                if v and (k not in env or not env.get(k)):
                    env[k] = v
                elif v:
                    env[k] = v
            # Never leave empty token placeholders
            s["env"] = {k: v for k, v in env.items() if v}
        return {"enabled": bool(enabled), "servers": servers}

    def public_view(self) -> dict[str, Any]:
        """Safe for API: masks secrets, exposes connector status."""
        cfg = self.get()
        overlay = self._overlay()
        secrets = self._secrets()
        servers_safe = []
        for s in cfg.get("servers") or []:
            env = s.get("env") or {}
            servers_safe.append(
                {
                    "name": s.get("name"),
                    "command": s.get("command"),
                    "args": s.get("args") or [],
                    "connector_id": s.get("connector_id"),
                    "env_keys": list(env.keys()),
                }
            )
        connected_ids = {s.get("connector_id") or s.get("name") for s in cfg.get("servers") or []}
        catalog = []
        for pack in catalog_public():
            cid = pack["id"]
            sec = secrets.get(cid) or {}
            catalog.append(
                {
                    **pack,
                    "connected": cid in connected_ids or pack["server_name"] in connected_ids,
                    "secrets_set": {f["key"]: bool(sec.get(f["key"])) for f in pack.get("secret_fields") or []},
                    "secrets_masked": {k: _mask(v) for k, v in sec.items() if v},
                    "config": (overlay.get("connector_config") or {}).get(cid) or {},
                }
            )
        return {
            "enabled": cfg.get("enabled"),
            "servers": servers_safe,
            "catalog": catalog,
            "github_oauth": __import__("orchestrator.github_oauth", fromlist=["oauth_status"]).oauth_status(),
        }

    def update(self, body: McpRuntimeUpdate) -> dict[str, Any]:
        overlay = self._overlay()
        data = body.model_dump(exclude_unset=True)
        if "enabled" in data and data["enabled"] is not None:
            overlay["enabled"] = bool(data["enabled"])
        if "servers" in data and data["servers"] is not None:
            # Strip secret values from stored server env; keep non-secret config
            cleaned = []
            for s in data["servers"]:
                item = dict(s) if isinstance(s, dict) else s
                if hasattr(s, "model_dump"):
                    item = s.model_dump()
                env = dict(item.get("env") or {})
                # Move known secret keys into secrets store
                cid = item.get("connector_id") or item.get("name") or "custom"
                secrets = overlay.get("secrets") if isinstance(overlay.get("secrets"), dict) else {}
                bucket = dict(secrets.get(cid) or {})
                for key in list(env.keys()):
                    if key.endswith("_TOKEN") or key.endswith("_KEY") or key == "GITHUB_TOKEN":
                        if env[key]:
                            bucket[key] = env[key]
                        env.pop(key, None)
                if bucket:
                    secrets[cid] = bucket
                    overlay["secrets"] = secrets
                item["env"] = env
                cleaned.append(item)
            overlay["servers"] = cleaned
        self._save(overlay)
        return self.get()

    def enable_connector(self, connector_id: str, body: ConnectorEnableBody) -> dict[str, Any]:
        pack = get_pack(connector_id)
        if not pack:
            raise KeyError(connector_id)
        overlay = self._overlay()
        secrets = overlay.get("secrets") if isinstance(overlay.get("secrets"), dict) else {}
        bucket = dict(secrets.get(connector_id) or {})
        for k, v in (body.secrets or {}).items():
            if (v or "").strip():
                bucket[k] = v.strip()
        # Validate required secrets present
        for field in pack.get("secret_fields") or []:
            if not field.get("optional") and not bucket.get(field["key"]):
                raise ValueError(f"Missing required secret: {field['key']}")
        secrets[connector_id] = bucket
        overlay["secrets"] = secrets

        configs = overlay.get("connector_config") if isinstance(overlay.get("connector_config"), dict) else {}
        cfg_bucket = dict(configs.get(connector_id) or {})
        for k, v in (body.config or {}).items():
            if v is not None and str(v).strip():
                cfg_bucket[k] = str(v).strip()
        configs[connector_id] = cfg_bucket
        overlay["connector_config"] = configs

        server = build_server_config(connector_id, secrets=bucket, config=cfg_bucket)
        # Persist server without secret env values
        persist = {
            "name": server["name"],
            "command": server["command"],
            "args": server["args"],
            "env": {k: v for k, v in (server.get("env") or {}).items() if not (k.endswith("_TOKEN") or k.endswith("_KEY") or k == "GITHUB_TOKEN")},
            "connector_id": connector_id,
        }

        servers = overlay.get("servers") if isinstance(overlay.get("servers"), list) else []
        servers = [s for s in servers if (s.get("connector_id") or s.get("name")) not in {connector_id, pack["server_name"]}]
        servers.append(persist)
        overlay["servers"] = servers
        overlay["enabled"] = True
        self._save(overlay)
        return self.public_view()

    def disable_connector(self, connector_id: str) -> dict[str, Any]:
        pack = get_pack(connector_id)
        overlay = self._overlay()
        name = pack["server_name"] if pack else connector_id
        servers = overlay.get("servers") if isinstance(overlay.get("servers"), list) else []
        overlay["servers"] = [
            s for s in servers if (s.get("connector_id") or s.get("name")) not in {connector_id, name}
        ]
        self._save(overlay)
        return self.public_view()


runtime_mcp = RuntimeMcpConfig()
