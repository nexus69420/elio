from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict

from orchestrator.schemas import AgentResult, ApprovalRequest, Plan, ReviewVerdict


def _merge_list(a: list, b: list) -> list:
    return a + b


class GraphState(TypedDict, total=False):
    task_id: str
    prompt: str
    force_hitl: bool
    preset_id: str
    memories: list[dict[str, Any]]
    plan: Optional[dict[str, Any]]
    results: Annotated[list[dict[str, Any]], _merge_list]
    reviews: Annotated[list[dict[str, Any]], _merge_list]
    retry_subtask_ids: list[str]
    specialist_failures: dict[str, int]
    deliverable: str
    approval: Optional[dict[str, Any]]
    status: str
    error: str
    root_span_id: str
