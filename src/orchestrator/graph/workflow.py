from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, StateGraph

from orchestrator.graph import nodes
from orchestrator.graph.state import GraphState
from orchestrator.schemas import TaskStatus
from orchestrator.store import task_store
from orchestrator.tracing.spans import trace_store


def build_graph():
    g: StateGraph = StateGraph(GraphState)
    g.add_node("retrieve_memory", nodes.retrieve_memory_node)
    g.add_node("plan", nodes.plan_node)
    g.add_node("maybe_approve_plan", nodes.maybe_approve_plan_node)
    g.add_node("execute", nodes.execute_specialists_node)
    g.add_node("review", nodes.review_node)
    g.add_node("synthesize", nodes.synthesize_node)
    g.add_node("hitl_final", nodes.hitl_final_node)
    g.add_node("persist_memory", nodes.persist_memory_node)

    g.set_entry_point("retrieve_memory")
    g.add_edge("retrieve_memory", "plan")
    g.add_conditional_edges(
        "plan",
        nodes.route_after_plan,
        {"maybe_approve_plan": "maybe_approve_plan", "end_fail": END},
    )
    g.add_conditional_edges(
        "maybe_approve_plan",
        nodes.route_after_plan_approval,
        {"execute": "execute", "end_fail": END},
    )
    g.add_edge("execute", "review")
    g.add_conditional_edges(
        "review",
        nodes.route_after_review,
        {"execute": "execute", "synthesize": "synthesize"},
    )
    g.add_edge("synthesize", "hitl_final")
    g.add_conditional_edges(
        "hitl_final",
        nodes.route_after_hitl,
        {"persist": "persist_memory", "end_fail": END},
    )
    g.add_edge("persist_memory", END)
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


async def run_task(task_id: str, prompt: str, force_hitl: bool = True) -> dict[str, Any]:
    root = trace_store.start_span(task_id=task_id, name="task", agent="orchestrator")
    graph = get_graph()
    initial: GraphState = {
        "task_id": task_id,
        "prompt": prompt,
        "force_hitl": force_hitl,
        "results": [],
        "reviews": [],
        "retry_subtask_ids": [],
        "specialist_failures": {},
        "root_span_id": root.id,
        "status": TaskStatus.queued.value,
    }
    try:
        final = await graph.ainvoke(initial)
        status = final.get("status") or TaskStatus.completed.value
        if status == TaskStatus.rejected.value:
            task = task_store.get(task_id)
            if task:
                task.status = TaskStatus.rejected
                task.error = final.get("error") or "rejected"
                task.deliverable = final.get("deliverable") or ""
                task_store.save(task)
            trace_store.end_span(root, status="warning", attributes={"status": status})
        elif status == TaskStatus.failed.value:
            task = task_store.get(task_id)
            if task:
                task.status = TaskStatus.failed
                task.error = final.get("error") or "failed"
                task_store.save(task)
            trace_store.end_span(root, status="error", attributes={"status": status})
        else:
            # persist_memory already marks completed; ensure deliverable
            task = task_store.get(task_id)
            if task and final.get("deliverable"):
                task.deliverable = final["deliverable"]
                if task.status != TaskStatus.completed:
                    task.status = TaskStatus.completed
                task_store.save(task)
            tokens = trace_store.token_summary(task_id)
            trace_store.end_span(root, attributes={"status": status, **tokens})
        return final
    except Exception as exc:  # noqa: BLE001
        task = task_store.get(task_id)
        if task:
            task.status = TaskStatus.failed
            task.error = str(exc)
            task_store.save(task)
        trace_store.end_span(root, status="error", attributes={"error": str(exc)})
        raise
