from __future__ import annotations

import json
from typing import Any, Optional

import redis
from pydantic import BaseModel, Field

from orchestrator.config import settings

REDIS_KEY = "orchestrator:llm_runtime"


class LLMSettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None  # ollama | openai | anthropic | stub
    ollama_host: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    supervisor_model: Optional[str] = None
    specialist_model: Optional[str] = None
    embed_model: Optional[str] = None
    openai_supervisor_model: Optional[str] = None
    openai_specialist_model: Optional[str] = None
    openai_embed_model: Optional[str] = None
    anthropic_supervisor_model: Optional[str] = None
    anthropic_specialist_model: Optional[str] = None
    clear_openai_key: bool = False
    clear_anthropic_key: bool = False


PROVIDER_PRESETS: dict[str, Any] = {
    "ollama": {
        "label": "Ollama (local)",
        "needs_api_key": False,
        "supervisor_models": ["qwen2.5:7b", "qwen2.5:14b", "llama3.1:8b", "mistral:7b"],
        "specialist_models": ["qwen2.5:3b", "qwen2.5:7b", "llama3.2:3b"],
        "embed_models": ["nomic-embed-text"],
    },
    "openai": {
        "label": "OpenAI",
        "needs_api_key": True,
        "supervisor_models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "o4-mini"],
        "specialist_models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
        "embed_models": ["text-embedding-3-small", "text-embedding-3-large"],
    },
    "anthropic": {
        "label": "Anthropic",
        "needs_api_key": True,
        "supervisor_models": [
            "claude-3-5-haiku-latest",
            "claude-3-5-sonnet-latest",
            "claude-sonnet-4-20250514",
        ],
        "specialist_models": ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"],
        "embed_models": ["nomic-embed-text"],  # embeds still via Ollama locally
        "note": "Chat uses Anthropic; embeddings fall back to local Ollama.",
    },
    "stub": {
        "label": "Stub (offline demo)",
        "needs_api_key": False,
        "supervisor_models": ["stub"],
        "specialist_models": ["stub"],
        "embed_models": ["stub"],
    },
}


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••••••"
    return f"{value[:3]}…{value[-4:]}"


class RuntimeLLMConfig:
    """Redis-backed LLM overrides so API + Celery workers share user-set keys/models."""

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

    def _base(self) -> dict[str, Any]:
        return {
            "llm_provider": (settings.llm_provider or "ollama").lower(),
            "ollama_host": settings.ollama_host,
            "openai_api_key": settings.openai_api_key or "",
            "openai_base_url": settings.openai_base_url,
            "anthropic_api_key": settings.anthropic_api_key or "",
            "supervisor_model": settings.supervisor_model,
            "specialist_model": settings.specialist_model,
            "embed_model": settings.embed_model,
            "openai_supervisor_model": settings.openai_supervisor_model,
            "openai_specialist_model": settings.openai_specialist_model,
            "openai_embed_model": settings.openai_embed_model,
            "anthropic_supervisor_model": settings.anthropic_supervisor_model,
            "anthropic_specialist_model": settings.anthropic_specialist_model,
            "stub": bool(settings.orchestrator_stub_llm),
        }

    def get(self) -> dict[str, Any]:
        overlay = self._overlay()
        merged = {**self._base(), **overlay}
        if "llm_provider" in overlay:
            provider = str(overlay["llm_provider"]).lower()
        elif settings.orchestrator_stub_llm:
            provider = "stub"
        else:
            provider = str(merged.get("llm_provider") or "ollama").lower()
        if provider not in PROVIDER_PRESETS:
            provider = "ollama"
        merged["llm_provider"] = provider
        merged["stub"] = provider == "stub"
        return merged

    def update(self, body: LLMSettingsUpdate) -> dict[str, Any]:
        overlay = self._overlay()
        data = body.model_dump(exclude_unset=True)

        if data.pop("clear_openai_key", False):
            overlay["openai_api_key"] = ""
        if data.pop("clear_anthropic_key", False):
            overlay["anthropic_api_key"] = ""

        for key, value in data.items():
            if value is None:
                continue
            if key in {"openai_api_key", "anthropic_api_key"}:
                text = str(value).strip()
                # Ignore masked / blank keep-current submissions
                if not text or "…" in text or text.startswith("••") or text.startswith("***"):
                    continue
                overlay[key] = text
                continue
            if key == "llm_provider":
                provider = str(value).lower().strip()
                if provider not in PROVIDER_PRESETS:
                    raise ValueError(f"Unknown provider: {provider}")
                overlay["llm_provider"] = provider
                overlay["stub"] = provider == "stub"
                continue
            overlay[key] = value

        self.client.set(REDIS_KEY, json.dumps(overlay))
        return self.public_view()

    def public_view(self) -> dict[str, Any]:
        cfg = self.get()
        return {
            "llm_provider": cfg["llm_provider"],
            "ollama_host": cfg["ollama_host"],
            "openai_base_url": cfg["openai_base_url"],
            "openai_api_key_set": bool(cfg.get("openai_api_key")),
            "openai_api_key_masked": _mask(cfg.get("openai_api_key") or ""),
            "anthropic_api_key_set": bool(cfg.get("anthropic_api_key")),
            "anthropic_api_key_masked": _mask(cfg.get("anthropic_api_key") or ""),
            "supervisor_model": cfg["supervisor_model"],
            "specialist_model": cfg["specialist_model"],
            "embed_model": cfg["embed_model"],
            "openai_supervisor_model": cfg["openai_supervisor_model"],
            "openai_specialist_model": cfg["openai_specialist_model"],
            "openai_embed_model": cfg["openai_embed_model"],
            "anthropic_supervisor_model": cfg["anthropic_supervisor_model"],
            "anthropic_specialist_model": cfg["anthropic_specialist_model"],
            "stub": bool(cfg.get("stub")),
            "presets": PROVIDER_PRESETS,
            "active_chat_models": {
                "supervisor": self.resolve_chat_model("supervisor"),
                "specialist": self.resolve_chat_model("specialist"),
                "embed": self.resolve_embed_model(),
            },
        }

    def resolve_chat_model(self, role: str = "supervisor") -> str:
        cfg = self.get()
        provider = cfg["llm_provider"]
        if provider == "openai":
            return cfg["openai_supervisor_model"] if role == "supervisor" else cfg["openai_specialist_model"]
        if provider == "anthropic":
            return (
                cfg["anthropic_supervisor_model"] if role == "supervisor" else cfg["anthropic_specialist_model"]
            )
        if provider == "stub":
            return "stub"
        return cfg["supervisor_model"] if role == "supervisor" else cfg["specialist_model"]

    def resolve_embed_model(self) -> str:
        cfg = self.get()
        if cfg["llm_provider"] == "openai":
            return cfg["openai_embed_model"]
        return cfg["embed_model"]


runtime_llm = RuntimeLLMConfig()
