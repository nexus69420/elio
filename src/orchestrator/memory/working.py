from __future__ import annotations

import json
from typing import Any, Optional

import redis

from orchestrator.config import settings


class WorkingMemory:
    """Task-scoped working memory on Redis (resume-grade short-term state)."""

    def __init__(self, url: Optional[str] = None) -> None:
        self.url = url or settings.redis_url
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(self.url, decode_responses=True)
        return self._client

    def _key(self, task_id: str, key: str) -> str:
        return f"wm:{task_id}:{key}"

    def set(self, task_id: str, key: str, value: Any, ttl_sec: int = 86400) -> None:
        self.client.set(self._key(task_id, key), json.dumps(value), ex=ttl_sec)

    def get(self, task_id: str, key: str, default: Any = None) -> Any:
        raw = self.client.get(self._key(task_id, key))
        if raw is None:
            return default
        return json.loads(raw)

    def dump(self, task_id: str) -> dict[str, Any]:
        pattern = f"wm:{task_id}:*"
        out: dict[str, Any] = {}
        for full in self.client.scan_iter(match=pattern, count=100):
            short = full.split(f"wm:{task_id}:", 1)[-1]
            raw = self.client.get(full)
            out[short] = json.loads(raw) if raw else None
        return out

    def clear(self, task_id: str) -> None:
        keys = list(self.client.scan_iter(match=f"wm:{task_id}:*", count=100))
        if keys:
            self.client.delete(*keys)

    def ping(self) -> bool:
        try:
            return bool(self.client.ping())
        except Exception:  # noqa: BLE001
            return False


working_memory = WorkingMemory()
