from __future__ import annotations

import json
from typing import Any, Optional

import redis

from orchestrator.config import settings
from orchestrator.schemas import utc_now


class TranscriptStore:
    """Persist LLM conversation turns per task for replay / eval."""

    def __init__(self, url: Optional[str] = None) -> None:
        self.url = url or settings.redis_url
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(self.url, decode_responses=True)
        return self._client

    def _key(self, task_id: str) -> str:
        return f"transcript:{task_id}"

    def append(
        self,
        *,
        task_id: str,
        agent: str,
        messages: list[dict[str, str]],
        response: str,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        format_json: bool = False,
    ) -> dict[str, Any]:
        turn = {
            "ts": utc_now(),
            "agent": agent,
            "model": model,
            "provider": provider,
            "format_json": format_json,
            "messages": messages,
            "response": response,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        self.client.rpush(self._key(task_id), json.dumps(turn))
        self.client.expire(self._key(task_id), 86400 * 14)
        return turn

    def list_turns(self, task_id: str) -> list[dict[str, Any]]:
        raw = self.client.lrange(self._key(task_id), 0, -1)
        return [json.loads(x) for x in raw]


transcript_store = TranscriptStore()
