from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from orchestrator.db import SessionLocal, init_db
from orchestrator.db_models import AuditRow
from orchestrator.schemas import new_id, utc_now


class AuditLog:
    """Append-only audit trail in Postgres."""

    def __init__(self) -> None:
        init_db()

    def record(
        self,
        *,
        action: str,
        actor: str = "system",
        task_id: str = "",
        resource_type: str = "",
        resource_id: str = "",
        detail: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        event_id = new_id("audit")
        payload = detail or {}
        # Never persist raw secrets
        safe = {k: ("***" if "key" in k.lower() or "token" in k.lower() else v) for k, v in payload.items()}
        row = AuditRow(
            id=event_id,
            actor=actor or "system",
            action=action,
            task_id=task_id or "",
            resource_type=resource_type or "",
            resource_id=resource_id or "",
            detail_json=json.dumps(safe),
            created_at=datetime.now(timezone.utc),
        )
        with SessionLocal() as session:
            session.add(row)
            session.commit()
        return {
            "id": event_id,
            "actor": actor or "system",
            "action": action,
            "task_id": task_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "detail": safe,
            "created_at": utc_now(),
        }

    def list_recent(
        self,
        *,
        limit: int = 50,
        task_id: Optional[str] = None,
        action: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        with SessionLocal() as session:
            q = session.query(AuditRow).order_by(AuditRow.created_at.desc())
            if task_id:
                q = q.filter(AuditRow.task_id == task_id)
            if action:
                q = q.filter(AuditRow.action == action)
            rows = q.limit(limit).all()
            out = []
            for r in rows:
                try:
                    detail = json.loads(r.detail_json or "{}")
                except Exception:  # noqa: BLE001
                    detail = {}
                out.append(
                    {
                        "id": r.id,
                        "actor": r.actor,
                        "action": r.action,
                        "task_id": r.task_id,
                        "resource_type": r.resource_type,
                        "resource_id": r.resource_id,
                        "detail": detail,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                )
            return out


audit_log = AuditLog()
