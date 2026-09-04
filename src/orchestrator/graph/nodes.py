from __future__ import annotations

import json
from typing import Any

from orchestrator.config import settings
from orchestrator.hitl.queue import approval_queue
from orchestrator.llm.client import current_agent, current_task_id, llm_client
from orchestrator.memory.semantic import semantic_memory
from orchestrator.memory.working import working_memory
from orchestrator.schemas import (
    ApprovalLevel,
    ApprovalRequest,
    Plan,
    SpecialistRole,
    Subtask,
    TaskStatus,
)
from orchestrator.store import task_store
from orchestrator.tools import register_default_tools, tool_registry
from orchestrator.tracing.spans import trace_store


def _bind_context(task_id: str, agent: str):
    current_task_id.set(task_id)
    current_agent.set(agent)


PLAN_SYSTEM = """You are the Supervisor Agent. Create an execution plan as JSON only.
Return object with keys:
goal (string), confidence (0-1), rationale (string), requires_human_plan_approval (bool),
subtasks (array of objects with: description, specialist one of research|analysis|writing|code,
depends_on array of subtask descriptions already listed, expected_output, sensitive bool).
Prefer 3 subtasks: research, analysis, writing. Mark the final writing subtask sensitive=true.
CRITICAL: If the user specifies format constraints (e.g. "3 bullets", "one paragraph", "TL;DR"),
put those constraints verbatim into the writing subtask expected_output and keep the plan lean.
Do not expand a short-answer request into a full report.
"""


REVIEW_SYSTEM = """You are a strict Reviewer Agent. Return JSON only:
{"passed": bool, "score": 0-1 number, "feedback": string}

FAIL (passed=false, score <= 0.45) when ANY apply:
- empty / off-topic / no concrete content
- user asked for a specific format (N bullets, short brief, etc.) and the output ignores it
- any tool call has ok=false and the output still depends on that failed write/search
- analysis used code_exec only to print prose instead of real computation
- writing produced a long essay when the user asked for a short structured answer

PASS only when the output is on-topic, concrete, and format-compliant.
Prefer failing for retry over rubber-stamping.
"""


SPECIALIST_SYSTEM = """You are a specialist agent ({role}).
{role_rules}

You may call tools by returning JSON:
{{
  "thought": "...",
  "tool_calls": [{{"name": "tool_name", "arguments": {{...}}}}],
  "final_answer": "..."
}}
If you can answer without tools, set tool_calls to [] and fill final_answer.
Tool schemas (use exact argument names):
{tools}

Obey the ORIGINAL user task format constraints in final_answer.
"""


ROLE_RULES = {
    "research": (
        "Produce sourced bullet facts, not essays. Prefer web_search. "
        "Cite titles/URLs from tool results. Keep it tight."
    ),
    "analysis": (
        "Produce tradeoffs / comparisons / a clear recommendation grounded in prior research. "
        "Do NOT use code_exec just to print strings — only for real computation. "
        "Stay structured and concise."
    ),
    "writing": (
        "Produce the final user-facing text in EXACTLY the format the user asked for "
        "(e.g. if they asked for 3 bullets, output exactly 3 bullets — nothing else). "
        "file_write args MUST be {\"path\": \"...\", \"content\": \"...\"}."
    ),
    "code": (
        "Write and run real code to verify claims. Prefer code_exec with actual logic, not print-only stubs."
    ),
}

SYNTHESIZE_SYSTEM = """You are the Supervisor synthesizing the final deliverable.
Match the ORIGINAL user task format EXACTLY.
If they asked for N bullets / a short answer, output that — not a long report.
Use specialist outputs as evidence only; do not invent a different structure.
"""


def _save_task_progress(task_id: str, **fields: Any) -> None:
    from orchestrator.schemas import AgentResult, ReviewVerdict

    task = task_store.get(task_id)
    if not task:
        return
    for k, v in fields.items():
        if k == "results" and v is not None:
            task.results = [AgentResult.model_validate(x) if not isinstance(x, AgentResult) else x for x in v]
        elif k == "reviews" and v is not None:
            task.reviews = [ReviewVerdict.model_validate(x) if not isinstance(x, ReviewVerdict) else x for x in v]
        else:
            setattr(task, k, v)
    task_store.save(task)


async def retrieve_memory_node(state: dict[str, Any]) -> dict[str, Any]:
    task_id = state["task_id"]
    _bind_context(task_id, "supervisor")
    span = trace_store.start_span(task_id=task_id, name="retrieve_memory", agent="supervisor", parent_id=state.get("root_span_id"))
    memories = await semantic_memory.retrieve(state["prompt"], k=3)
    working_memory.set(task_id, "memories", memories)
    trace_store.end_span(span, attributes={"count": len(memories)})
    return {"memories": memories, "status": TaskStatus.planning.value}


async def plan_node(state: dict[str, Any]) -> dict[str, Any]:
    task_id = state["task_id"]
    _bind_context(task_id, "supervisor")
    _save_task_progress(task_id, status=TaskStatus.planning)
    span = trace_store.start_span(task_id=task_id, name="plan", agent="supervisor", parent_id=state.get("root_span_id"))

    memory_block = "\n\n".join(m.get("document", "") for m in state.get("memories") or []) or "(none)"
    user = f"User task:\n{state['prompt']}\n\nRelevant past memories:\n{memory_block}"
    try:
        parsed, resp = await llm_client.chat_json(
            system=PLAN_SYSTEM,
            user=user,
            model=settings.supervisor_model,
        )
        # Normalize subtasks
        raw_subs = parsed.get("subtasks") or []
        subtasks: list[Subtask] = []
        for item in raw_subs:
            specialist = item.get("specialist", "research")
            try:
                role = SpecialistRole(specialist)
            except ValueError:
                role = SpecialistRole.research
            subtasks.append(
                Subtask(
                    description=item.get("description") or "Work on task",
                    specialist=role,
                    depends_on=[],
                    expected_output=item.get("expected_output") or "",
                    sensitive=bool(item.get("sensitive", False)),
                )
            )
        if not subtasks:
            subtasks = [
                Subtask(description="Research the topic", specialist=SpecialistRole.research, expected_output="facts"),
                Subtask(description="Analyze findings", specialist=SpecialistRole.analysis, expected_output="analysis"),
                Subtask(
                    description="Write the brief",
                    specialist=SpecialistRole.writing,
                    expected_output="brief",
                    sensitive=True,
                ),
            ]
        plan = Plan(
            goal=parsed.get("goal") or state["prompt"][:200],
            subtasks=subtasks,
            confidence=float(parsed.get("confidence", 0.7)),
            rationale=parsed.get("rationale") or "",
            requires_human_plan_approval=bool(parsed.get("requires_human_plan_approval", False)),
        )
        working_memory.set(task_id, "plan", plan.model_dump())
        _save_task_progress(task_id, plan=plan)
        trace_store.end_span(
            span,
            input_tokens=resp.get("input_tokens", 0),
            output_tokens=resp.get("output_tokens", 0),
            attributes={"confidence": plan.confidence, "n_subtasks": len(plan.subtasks)},
        )
        return {"plan": plan.model_dump(), "status": TaskStatus.executing.value}
    except Exception as exc:  # noqa: BLE001
        trace_store.end_span(span, status="error", attributes={"error": str(exc)})
        return {"error": f"Planning failed: {exc}", "status": TaskStatus.failed.value}


async def maybe_approve_plan_node(state: dict[str, Any]) -> dict[str, Any]:
    plan = Plan.model_validate(state["plan"])
    task_id = state["task_id"]
    needs = (
        plan.requires_human_plan_approval
        or plan.confidence < settings.plan_confidence_threshold
    )
    if not needs:
        return {}

    req = ApprovalRequest(
        task_id=task_id,
        level=ApprovalLevel.approve_plan,
        reason="Plan confidence low or explicit plan approval requested",
        proposed_action=json.dumps(plan.model_dump(), indent=2),
        context={"goal": plan.goal, "confidence": plan.confidence},
    )
    approval_queue.enqueue(req)
    _save_task_progress(task_id, status=TaskStatus.awaiting_approval)
    span = trace_store.start_span(task_id=task_id, name="hitl_plan", agent="hitl", parent_id=state.get("root_span_id"))
    resolved = await approval_queue.wait(req.id)
    trace_store.end_span(span, attributes={"status": resolved.status.value})
    if resolved.status.value == "rejected":
        return {"status": TaskStatus.rejected.value, "error": "Human rejected plan", "approval": resolved.model_dump()}
    if resolved.status.value == "modified" and resolved.proposed_action:
        try:
            modified = json.loads(resolved.proposed_action)
            plan = Plan.model_validate(modified)
            working_memory.set(task_id, "plan", plan.model_dump())
            return {"plan": plan.model_dump(), "approval": resolved.model_dump()}
        except Exception:  # noqa: BLE001
            pass
    return {"approval": resolved.model_dump()}


def _tool_names_for_role(role: SpecialistRole) -> list[str]:
    mcp_tools = [t["name"] for t in tool_registry.list_tools() if t["name"].startswith("mcp_")]
    if role == SpecialistRole.research:
        return ["web_search", "file_write", *mcp_tools]
    if role == SpecialistRole.analysis:
        return ["file_read", "code_exec", "file_write", *mcp_tools]
    if role == SpecialistRole.writing:
        return ["file_read", "file_write", *mcp_tools]
    return ["code_exec", "file_read", "file_write", *mcp_tools]


async def execute_specialists_node(state: dict[str, Any]) -> dict[str, Any]:
    register_default_tools()
    task_id = state["task_id"]
    _bind_context(task_id, "specialist")
    _save_task_progress(task_id, status=TaskStatus.executing)
    plan = Plan.model_validate(state["plan"])
    retry_ids = set(state.get("retry_subtask_ids") or [])
    failures = dict(state.get("specialist_failures") or {})
    prior_outputs = {r.get("subtask_id"): r.get("output", "") for r in state.get("results") or []}

    new_results: list[dict[str, Any]] = []

    for sub in plan.subtasks:
        if retry_ids and sub.id not in retry_ids:
            # keep previous success; skip
            if prior_outputs.get(sub.id):
                continue
        if not retry_ids and prior_outputs.get(sub.id) and sub.id not in retry_ids:
            continue

        span = trace_store.start_span(
            task_id=task_id,
            name=f"specialist:{sub.specialist.value}",
            agent=sub.specialist.value,
            parent_id=state.get("root_span_id"),
            attributes={"subtask_id": sub.id, "description": sub.description},
        )
        _bind_context(task_id, sub.specialist.value)
        context_bits = [f"Overall goal: {plan.goal}", f"Your subtask: {sub.description}"]
        for other in plan.subtasks:
            if other.id != sub.id and prior_outputs.get(other.id):
                context_bits.append(f"Prior ({other.specialist.value}): {prior_outputs[other.id][:800]}")
        for r in new_results:
            context_bits.append(f"Prior ({r['specialist']}): {r['output'][:800]}")

        allowed = _tool_names_for_role(sub.specialist)
        tool_prompt = "\n".join(
            f"- {t['name']}: {t['description']} | params={json.dumps(t['parameters'])}"
            for t in tool_registry.list_tools()
            if t["name"] in allowed
        )
        role = sub.specialist.value
        system = SPECIALIST_SYSTEM.format(
            role=role,
            role_rules=ROLE_RULES.get(role, "Stay concise and factual."),
            tools=tool_prompt,
        )
        tool_calls_log: list[dict[str, Any]] = []
        final_answer = ""
        total_in = total_out = 0

        try:
            for _round in range(3):
                parsed, resp = await llm_client.chat_json(
                    system=system,
                    user=(
                        f"ORIGINAL USER TASK:\n{state['prompt']}\n\n"
                        + "\n".join(context_bits)
                        + f"\n\nTool results so far:\n{json.dumps(tool_calls_log)[:3000]}"
                    ),
                    model=settings.specialist_model if settings.llm_provider == "ollama" else None,
                    role="specialist",
                )
                total_in += resp.get("input_tokens", 0)
                total_out += resp.get("output_tokens", 0)
                calls = parsed.get("tool_calls") or []
                if calls:
                    for call in calls:
                        name = call.get("name")
                        args = call.get("arguments") or {}
                        if name not in allowed:
                            tool_calls_log.append({"name": name, "ok": False, "error": "tool not allowed for role"})
                            continue
                        result = tool_registry.invoke(name, args)
                        tool_calls_log.append(result)
                    continue
                final_answer = parsed.get("final_answer") or parsed.get("answer") or ""
                if not final_answer and isinstance(parsed, dict):
                    final_answer = json.dumps(parsed)
                break

            if not final_answer:
                # fallback: ask for prose answer
                prose = await llm_client.chat(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                f"You are the {sub.specialist.value} specialist. "
                                f"{ROLE_RULES.get(role, '')} Match the ORIGINAL user task format."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"ORIGINAL USER TASK:\n{state['prompt']}\n\n" + "\n".join(context_bits),
                        },
                    ],
                    model=settings.specialist_model if settings.llm_provider == "ollama" else None,
                    role="specialist",
                )
                total_in += prose.get("input_tokens", 0)
                total_out += prose.get("output_tokens", 0)
                final_answer = prose["content"]

            failed_tools = [t for t in tool_calls_log if not t.get("ok", True)]
            result = {
                "subtask_id": sub.id,
                "specialist": sub.specialist.value,
                "output": final_answer,
                "tool_calls": tool_calls_log,
                "success": True,
                "error": "",
            }
            if failed_tools and not final_answer.strip():
                result["success"] = False
                result["error"] = f"{len(failed_tools)} tool call(s) failed and no answer"
            prior_outputs[sub.id] = final_answer
            new_results.append(result)
            trace_store.end_span(
                span,
                input_tokens=total_in,
                output_tokens=total_out,
                attributes={"tool_calls": len(tool_calls_log), "failed_tools": len(failed_tools)},
            )
        except Exception as exc:  # noqa: BLE001
            failures[sub.id] = failures.get(sub.id, 0) + 1
            result = {
                "subtask_id": sub.id,
                "specialist": sub.specialist.value,
                "output": "",
                "tool_calls": tool_calls_log,
                "success": False,
                "error": str(exc),
            }
            new_results.append(result)
            trace_store.end_span(span, status="error", attributes={"error": str(exc)})

    working_memory.set(task_id, "results", (state.get("results") or []) + new_results)
    _save_task_progress(task_id, results=[*(state.get("results") or []), *new_results])  # type: ignore[arg-type]
    return {
        "results": new_results,
        "specialist_failures": failures,
        "retry_subtask_ids": [],
        "status": TaskStatus.reviewing.value,
    }


async def review_node(state: dict[str, Any]) -> dict[str, Any]:
    task_id = state["task_id"]
    _bind_context(task_id, "reviewer")
    _save_task_progress(task_id, status=TaskStatus.reviewing)
    plan = Plan.model_validate(state["plan"])
    # Review only latest results for each subtask
    latest: dict[str, dict] = {}
    for r in state.get("results") or []:
        latest[r["subtask_id"]] = r

    reviews: list[dict[str, Any]] = []
    retry_ids: list[str] = []
    failures = dict(state.get("specialist_failures") or {})

    for sub in plan.subtasks:
        result = latest.get(sub.id)
        if not result:
            continue
        span = trace_store.start_span(
            task_id=task_id,
            name="review",
            agent="reviewer",
            parent_id=state.get("root_span_id"),
            attributes={"subtask_id": sub.id},
        )
        tool_calls = result.get("tool_calls") or []
        failed_tools = [t for t in tool_calls if isinstance(t, dict) and not t.get("ok", True)]
        tool_summary = [
            {
                "name": t.get("name"),
                "ok": t.get("ok"),
                "error": t.get("error", ""),
            }
            for t in tool_calls
            if isinstance(t, dict)
        ]
        user = (
            f"ORIGINAL USER TASK:\n{state['prompt']}\n\n"
            f"Subtask: {sub.description}\nExpected: {sub.expected_output}\n"
            f"Specialist: {result.get('specialist')}\n"
            f"Success flag: {result.get('success')}\n"
            f"Failed tool calls: {len(failed_tools)}\n"
            f"Tool call summary: {json.dumps(tool_summary)[:1500]}\n"
            f"Output:\n{result.get('output','')[:3000]}"
        )
        try:
            parsed, resp = await llm_client.chat_json(
                system=REVIEW_SYSTEM,
                user=user,
                model=settings.supervisor_model,
            )
            score = float(parsed.get("score", 0.5))
            passed = bool(parsed.get("passed", score >= settings.review_pass_threshold))
            feedback = parsed.get("feedback") or ""

            # Deterministic hard fails — do not let the LLM rubber-stamp these.
            hard_fail_reasons: list[str] = []
            output = (result.get("output") or "").strip()
            if not result.get("success"):
                hard_fail_reasons.append("specialist success=false")
            if not output:
                hard_fail_reasons.append("empty output")
            if failed_tools:
                hard_fail_reasons.append(f"{len(failed_tools)} failed tool call(s)")
            if result.get("specialist") == "analysis":
                print_only = []
                for t in tool_calls:
                    if not isinstance(t, dict) or t.get("name") != "code_exec":
                        continue
                    code = str((t.get("arguments") or {}).get("code", "")).strip()
                    if "print(" in code and len(code) < 220:
                        print_only.append(t)
                if len(print_only) >= 2:
                    hard_fail_reasons.append("analysis used code_exec mainly to print prose")

            if hard_fail_reasons:
                passed = False
                score = min(score, 0.35)
                feedback = (feedback + " | HARD FAIL: " + "; ".join(hard_fail_reasons)).strip(" |")

            if not passed:
                failures[sub.id] = failures.get(sub.id, 0) + 1
                if failures[sub.id] <= settings.max_specialist_retries:
                    retry_ids.append(sub.id)
            reviews.append(
                {
                    "subtask_id": sub.id,
                    "passed": passed,
                    "score": score,
                    "feedback": feedback,
                }
            )
            trace_store.end_span(
                span,
                input_tokens=resp.get("input_tokens", 0),
                output_tokens=resp.get("output_tokens", 0),
                attributes={"passed": passed, "score": score, "hard_fail": bool(hard_fail_reasons)},
            )
        except Exception as exc:  # noqa: BLE001
            # Fail closed — do not rubber-stamp review errors.
            failures[sub.id] = failures.get(sub.id, 0) + 1
            if failures[sub.id] <= settings.max_specialist_retries:
                retry_ids.append(sub.id)
            reviews.append(
                {
                    "subtask_id": sub.id,
                    "passed": False,
                    "score": 0.3,
                    "feedback": f"review error (fail-closed): {exc}",
                }
            )
            trace_store.end_span(span, status="error", attributes={"error": str(exc)})

    working_memory.set(task_id, "reviews", reviews)
    _save_task_progress(task_id, reviews=reviews)
    return {"reviews": reviews, "retry_subtask_ids": retry_ids, "specialist_failures": failures}


async def synthesize_node(state: dict[str, Any]) -> dict[str, Any]:
    task_id = state["task_id"]
    _bind_context(task_id, "supervisor")
    _save_task_progress(task_id, status=TaskStatus.synthesizing)
    span = trace_store.start_span(task_id=task_id, name="synthesize", agent="supervisor", parent_id=state.get("root_span_id"))
    latest: dict[str, dict] = {}
    for r in state.get("results") or []:
        latest[r["subtask_id"]] = r
    parts = [f"## {v['specialist']}\n{v['output']}" for v in latest.values()]
    user = f"Original task:\n{state['prompt']}\n\nSpecialist outputs:\n\n" + "\n\n".join(parts)
    resp = await llm_client.chat(
        messages=[
            {"role": "system", "content": SYNTHESIZE_SYSTEM},
            {"role": "user", "content": user},
        ],
        model=settings.supervisor_model,
    )
    deliverable = resp["content"]
    working_memory.set(task_id, "draft_deliverable", deliverable)
    trace_store.end_span(span, input_tokens=resp.get("input_tokens", 0), output_tokens=resp.get("output_tokens", 0))
    return {"deliverable": deliverable}


async def hitl_final_node(state: dict[str, Any]) -> dict[str, Any]:
    task_id = state["task_id"]
    plan = Plan.model_validate(state["plan"])
    failures = state.get("specialist_failures") or {}
    reviews = state.get("reviews") or []
    low_review = any(float(r.get("score", 1)) < settings.review_pass_threshold for r in reviews)
    double_fail = any(v >= 2 for v in failures.values())
    sensitive = any(s.sensitive for s in plan.subtasks) or state.get("force_hitl", True)

    if not (sensitive or low_review or double_fail or settings.hitl_force_final):
        return {}

    reason_bits = []
    if sensitive or settings.hitl_force_final:
        reason_bits.append("final deliverable requires human approval")
    if low_review:
        reason_bits.append("reviewer score below threshold")
    if double_fail:
        reason_bits.append("specialist failed twice")

    req = ApprovalRequest(
        task_id=task_id,
        level=ApprovalLevel.approve_action,
        reason="; ".join(reason_bits),
        proposed_action=state.get("deliverable") or "",
        context={"prompt": state["prompt"]},
    )
    approval_queue.enqueue(req)
    _save_task_progress(task_id, status=TaskStatus.awaiting_approval)
    span = trace_store.start_span(task_id=task_id, name="hitl_final", agent="hitl", parent_id=state.get("root_span_id"))
    resolved = await approval_queue.wait(req.id)
    trace_store.end_span(span, attributes={"status": resolved.status.value})

    if resolved.status.value == "rejected":
        return {"status": TaskStatus.rejected.value, "error": "Human rejected deliverable", "approval": resolved.model_dump()}
    if resolved.status.value == "taken_over" and resolved.human_output:
        return {"deliverable": resolved.human_output, "approval": resolved.model_dump()}
    if resolved.status.value == "modified" and resolved.proposed_action:
        return {"deliverable": resolved.proposed_action, "approval": resolved.model_dump()}
    return {"approval": resolved.model_dump()}


async def persist_memory_node(state: dict[str, Any]) -> dict[str, Any]:
    task_id = state["task_id"]
    if state.get("status") in {TaskStatus.rejected.value, TaskStatus.failed.value}:
        return {"status": state.get("status")}

    span = trace_store.start_span(task_id=task_id, name="persist_memory", agent="memory", parent_id=state.get("root_span_id"))
    tools_used: list[str] = []
    for r in state.get("results") or []:
        for tc in r.get("tool_calls") or []:
            if tc.get("name"):
                tools_used.append(tc["name"])
    tools_used = sorted(set(tools_used))
    summary = (state.get("deliverable") or "")[:1000]
    await semantic_memory.add_lesson(
        task_id=task_id,
        prompt=state["prompt"],
        summary=summary,
        approach=(state.get("plan") or {}).get("rationale", "multi-agent plan"),
        tools_used=tools_used,
    )
    _save_task_progress(
        task_id,
        status=TaskStatus.completed,
        deliverable=state.get("deliverable") or "",
    )
    working_memory.clear(task_id)
    trace_store.end_span(span, attributes={"tools_used": tools_used})
    return {"status": TaskStatus.completed.value}


def route_after_plan(state: dict[str, Any]) -> str:
    if state.get("status") == TaskStatus.failed.value:
        return "end_fail"
    return "maybe_approve_plan"


def route_after_plan_approval(state: dict[str, Any]) -> str:
    if state.get("status") == TaskStatus.rejected.value:
        return "end_fail"
    return "execute"


def route_after_review(state: dict[str, Any]) -> str:
    retries = state.get("retry_subtask_ids") or []
    failures = state.get("specialist_failures") or {}
    # escalate to HITL if any subtask exceeded retries still failing
    for sid in retries:
        if failures.get(sid, 0) > settings.max_specialist_retries:
            return "synthesize"
    if retries:
        return "execute"
    return "synthesize"


def route_after_hitl(state: dict[str, Any]) -> str:
    if state.get("status") == TaskStatus.rejected.value:
        return "end_fail"
    return "persist"
