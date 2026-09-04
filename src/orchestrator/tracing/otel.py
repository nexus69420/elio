from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from orchestrator.config import settings

_initialized = False


def setup_tracing(app=None) -> None:
    global _initialized
    if _initialized or not settings.otel_enabled:
        if app is not None and settings.otel_enabled:
            FastAPIInstrumentor.instrument_app(app)
        return

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/") + "/v1/traces"
    try:
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except Exception:  # noqa: BLE001
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()
    CeleryInstrumentor().instrument()
    if app is not None:
        FastAPIInstrumentor.instrument_app(app)
    _initialized = True


def get_tracer(name: str = "orchestrator"):
    return trace.get_tracer(name)
