from __future__ import annotations

import asyncio

from celery import Celery

from orchestrator.config import settings
from orchestrator.tracing.otel import setup_tracing

setup_tracing()

celery_app = Celery(
    "orchestrator",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)


@celery_app.task(name="orchestrator.run_task", bind=True)
def run_task_job(self, task_id: str, prompt: str, force_hitl: bool = True, preset_id: str = "") -> dict:
    from orchestrator.graph.workflow import run_task

    return asyncio.run(run_task(task_id, prompt, force_hitl=force_hitl, preset_id=preset_id or None))
