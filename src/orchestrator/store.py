from __future__ import annotations

from typing import Optional

from orchestrator.db import SessionLocal, init_db
from orchestrator.db_models import TaskRow
from orchestrator.schemas import TaskRecord, TaskStatus, utc_now


class TaskStore:
    def __init__(self) -> None:
        init_db()

    def save(self, task: TaskRecord) -> TaskRecord:
        task.updated_at = utc_now()
        with SessionLocal() as session:
            row = session.get(TaskRow, task.id)
            if row is None:
                row = TaskRow(
                    id=task.id,
                    payload_json=task.model_dump_json(),
                    status=task.status.value,
                )
                session.add(row)
            else:
                row.payload_json = task.model_dump_json()
                row.status = task.status.value
            session.commit()
        return task

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with SessionLocal() as session:
            row = session.get(TaskRow, task_id)
            if not row:
                return None
            return TaskRecord.model_validate_json(row.payload_json)

    def list_recent(self, limit: int = 20) -> list[TaskRecord]:
        with SessionLocal() as session:
            rows = (
                session.query(TaskRow)
                .order_by(TaskRow.created_at.desc())
                .limit(limit)
                .all()
            )
            return [TaskRecord.model_validate_json(r.payload_json) for r in rows]

    def set_status(self, task_id: str, status: TaskStatus) -> TaskRecord:
        task = self.get(task_id)
        if not task:
            raise KeyError(task_id)
        task.status = status
        return self.save(task)


task_store = TaskStore()
