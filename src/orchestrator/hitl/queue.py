from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from orchestrator.config import settings
from orchestrator.db import SessionLocal, init_db
from orchestrator.db_models import ApprovalRow
from orchestrator.schemas import ApprovalRequest, ApprovalResolve, ApprovalStatus, utc_now


class ApprovalQueue:
    def __init__(self) -> None:
        init_db()
        self._events: dict[str, asyncio.Event] = {}

    def _event(self, approval_id: str) -> asyncio.Event:
        if approval_id not in self._events:
            self._events[approval_id] = asyncio.Event()
        return self._events[approval_id]

    def enqueue(self, req: ApprovalRequest) -> ApprovalRequest:
        with SessionLocal() as session:
            session.add(
                ApprovalRow(
                    id=req.id,
                    task_id=req.task_id,
                    payload_json=req.model_dump_json(),
                    status=req.status.value,
                )
            )
            session.commit()
        self._event(req.id).clear()
        if settings.orchestrator_auto_approve:
            self.resolve(
                req.id,
                ApprovalResolve(action="approve", note="auto-approved (ORCHESTRATOR_AUTO_APPROVE)"),
            )
        # Cross-process wake: also publish on Redis pubsub channel
        try:
            import redis
            from orchestrator.config import settings as s

            r = redis.Redis.from_url(s.redis_url, decode_responses=True)
            if settings.orchestrator_auto_approve:
                r.publish(f"approval:{req.id}", "resolved")
        except Exception:  # noqa: BLE001
            pass
        return req

    def get(self, approval_id: str) -> Optional[ApprovalRequest]:
        with SessionLocal() as session:
            row = session.get(ApprovalRow, approval_id)
            if not row:
                return None
            return ApprovalRequest.model_validate_json(row.payload_json)

    def list_pending(self, task_id: Optional[str] = None) -> list[ApprovalRequest]:
        with SessionLocal() as session:
            q = session.query(ApprovalRow).filter(ApprovalRow.status == ApprovalStatus.pending.value)
            if task_id:
                q = q.filter(ApprovalRow.task_id == task_id)
            rows = q.order_by(ApprovalRow.created_at.asc()).all()
            return [ApprovalRequest.model_validate_json(r.payload_json) for r in rows]

    def resolve(self, approval_id: str, body: ApprovalResolve) -> ApprovalRequest:
        req = self.get(approval_id)
        if not req:
            raise KeyError(f"Unknown approval {approval_id}")
        if req.status != ApprovalStatus.pending:
            return req

        mapping = {
            "approve": ApprovalStatus.approved,
            "modify": ApprovalStatus.modified,
            "reject": ApprovalStatus.rejected,
            "take_over": ApprovalStatus.taken_over,
        }
        req.status = mapping[body.action]
        req.resolution_note = body.note
        if body.modified_action:
            req.proposed_action = body.modified_action
        if body.human_output:
            req.human_output = body.human_output
        req.resolved_at = utc_now()

        with SessionLocal() as session:
            row = session.get(ApprovalRow, approval_id)
            if row:
                row.payload_json = req.model_dump_json()
                row.status = req.status.value
                row.resolved_at = datetime.now(timezone.utc)
                session.commit()

        self._event(approval_id).set()
        try:
            import redis

            r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            r.publish(f"approval:{approval_id}", "resolved")
        except Exception:  # noqa: BLE001
            pass
        return req

    async def wait(self, approval_id: str, timeout: float = 3600.0) -> ApprovalRequest:
        # Works across Celery worker processes via Redis pub/sub + DB poll
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"approval:{approval_id}")
        try:
            # Already resolved?
            current = self.get(approval_id)
            if current and current.status != ApprovalStatus.pending:
                return current

            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    raise TimeoutError(f"Approval {approval_id} timed out")
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=min(1.0, remaining))
                current = self.get(approval_id)
                if current and current.status != ApprovalStatus.pending:
                    return current
                if msg is None:
                    await asyncio.sleep(0.2)
        finally:
            await pubsub.unsubscribe(f"approval:{approval_id}")
            await pubsub.aclose()
            await r.aclose()


approval_queue = ApprovalQueue()
