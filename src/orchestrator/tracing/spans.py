from __future__ import annotations

import json
from typing import Any, Optional

from opentelemetry import trace

from orchestrator.config import settings
from orchestrator.schemas import SpanRecord, utc_now


class TraceStore:
    """Dual sink: OpenTelemetry → Jaeger + Redis index for API/UI convenience."""

    def __init__(self) -> None:
        self._redis = None
        self._live: dict[str, Any] = {}

    @property
    def redis(self):
        if self._redis is None:
            import redis

            self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    def _tracer(self):
        from orchestrator.tracing.otel import get_tracer

        return get_tracer("orchestrator.spans")

    def start_span(
        self,
        *,
        task_id: str,
        name: str,
        agent: str = "",
        parent_id: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> SpanRecord:
        span = SpanRecord(
            task_id=task_id,
            parent_id=parent_id,
            name=name,
            agent=agent,
            attributes=attributes or {},
        )
        otel_span = self._tracer().start_span(name)
        otel_span.set_attribute("task.id", task_id)
        otel_span.set_attribute("agent", agent)
        if attributes:
            for k, v in attributes.items():
                if isinstance(v, (str, int, float, bool)):
                    otel_span.set_attribute(f"orch.{k}", v)
        span.attributes["_otel_context"] = {
            "trace_id": format(otel_span.get_span_context().trace_id, "032x"),
            "span_id": format(otel_span.get_span_context().span_id, "016x"),
        }
        self._live[span.id] = otel_span
        self.redis.hset(f"trace:{task_id}", span.id, span.model_dump_json())
        self.redis.expire(f"trace:{task_id}", 86400 * 7)
        return span

    def end_span(
        self,
        span: SpanRecord,
        *,
        status: str = "ok",
        input_tokens: int = 0,
        output_tokens: int = 0,
        attributes: Optional[dict[str, Any]] = None,
    ) -> SpanRecord:
        span.status = status  # type: ignore[assignment]
        span.ended_at = utc_now()
        span.input_tokens = input_tokens
        span.output_tokens = output_tokens
        if attributes:
            span.attributes.update(attributes)
        try:
            from datetime import datetime

            s = datetime.fromisoformat(span.started_at)
            e = datetime.fromisoformat(span.ended_at)
            span.duration_ms = (e - s).total_seconds() * 1000
        except Exception:  # noqa: BLE001
            span.duration_ms = 0.0

        otel_span = self._live.pop(span.id, None)
        if otel_span is not None:
            otel_span.set_attribute("tokens.input", input_tokens)
            otel_span.set_attribute("tokens.output", output_tokens)
            otel_span.set_attribute("status", status)
            if status == "error":
                otel_span.set_status(trace.Status(trace.StatusCode.ERROR))
            otel_span.end()

        self.redis.hset(f"trace:{span.task_id}", span.id, span.model_dump_json())
        pipe = self.redis.pipeline()
        pipe.hincrby(f"tokens:{span.task_id}", "input_tokens", input_tokens)
        pipe.hincrby(f"tokens:{span.task_id}", "output_tokens", output_tokens)
        pipe.expire(f"tokens:{span.task_id}", 86400 * 7)
        pipe.execute()
        return span

    def list_spans(self, task_id: str) -> list[dict[str, Any]]:
        raw = self.redis.hgetall(f"trace:{task_id}")
        spans = [json.loads(v) for v in raw.values()]
        spans.sort(key=lambda s: s.get("started_at") or "")
        return spans

    def token_summary(self, task_id: str) -> dict[str, int]:
        data = self.redis.hgetall(f"tokens:{task_id}") or {}
        tin = int(data.get("input_tokens") or 0)
        tout = int(data.get("output_tokens") or 0)
        return {"input_tokens": tin, "output_tokens": tout, "total_tokens": tin + tout}


trace_store = TraceStore()
