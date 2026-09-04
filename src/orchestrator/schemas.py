from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "") -> str:
    uid = uuid4().hex[:12]
    return f"{prefix}_{uid}" if prefix else uid


class SpecialistRole(str, Enum):
    research = "research"
    analysis = "analysis"
    writing = "writing"
    code = "code"


class ApprovalLevel(str, Enum):
    notify = "notify"
    approve_action = "approve_action"
    approve_plan = "approve_plan"
    take_over = "take_over"


class ApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    modified = "modified"
    rejected = "rejected"
    taken_over = "taken_over"


class TaskStatus(str, Enum):
    queued = "queued"
    planning = "planning"
    executing = "executing"
    reviewing = "reviewing"
    awaiting_approval = "awaiting_approval"
    synthesizing = "synthesizing"
    completed = "completed"
    failed = "failed"
    rejected = "rejected"


class Subtask(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sub"))
    description: str
    specialist: SpecialistRole
    depends_on: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    expected_output: str = ""
    sensitive: bool = False
    status: Literal["pending", "running", "done", "failed"] = "pending"
    output: str = ""
    error: str = ""
    attempts: int = 0


class Plan(BaseModel):
    goal: str
    subtasks: list[Subtask]
    confidence: float = 0.7
    rationale: str = ""
    requires_human_plan_approval: bool = False


class AgentResult(BaseModel):
    subtask_id: str
    specialist: SpecialistRole
    output: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    success: bool = True
    error: str = ""


class ReviewVerdict(BaseModel):
    subtask_id: str
    passed: bool
    score: float
    feedback: str = ""


class ApprovalRequest(BaseModel):
    id: str = Field(default_factory=lambda: new_id("appr"))
    task_id: str
    level: ApprovalLevel
    reason: str
    proposed_action: str
    context: dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.pending
    resolution_note: str = ""
    human_output: str = ""
    created_at: str = Field(default_factory=utc_now)
    resolved_at: Optional[str] = None


class TaskRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("task"))
    prompt: str
    status: TaskStatus = TaskStatus.queued
    plan: Optional[Plan] = None
    results: list[AgentResult] = Field(default_factory=list)
    reviews: list[ReviewVerdict] = Field(default_factory=list)
    deliverable: str = ""
    error: str = ""
    force_hitl: bool = True
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class TaskCreate(BaseModel):
    prompt: str
    force_hitl: bool = True


class ApprovalResolve(BaseModel):
    action: Literal["approve", "modify", "reject", "take_over"]
    note: str = ""
    modified_action: str = ""
    human_output: str = ""


class SpanRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("span"))
    task_id: str
    parent_id: Optional[str] = None
    name: str
    agent: str = ""
    status: Literal["ok", "error", "warning"] = "ok"
    started_at: str = Field(default_factory=utc_now)
    ended_at: Optional[str] = None
    duration_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    attributes: dict[str, Any] = Field(default_factory=dict)
