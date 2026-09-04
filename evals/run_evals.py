from __future__ import annotations

"""Offline eval harness for agent orchestration runs.

Usage:
  set ORCHESTRATOR_STUB_LLM=1
  set ORCHESTRATOR_AUTO_APPROVE=1
  set PYTHONPATH=src
  python -m evals.run_evals
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("ORCHESTRATOR_STUB_LLM", "1")
os.environ.setdefault("ORCHESTRATOR_AUTO_APPROVE", "1")
os.environ.setdefault("OTEL_ENABLED", "0")
os.environ.setdefault("MCP_ENABLED", "0")


@dataclass
class EvalCase:
    id: str
    prompt: str
    expect_status: str = "completed"
    require_deliverable: bool = True
    min_spans: int = 3
    min_transcript_turns: int = 1
    must_contain: list[str] | None = None


CASES = [
    EvalCase(
        id="brief_local_agents",
        prompt="Research local multi-agent tradeoffs and write a brief",
        must_contain=["stub", "brief"],
    ),
    EvalCase(
        id="cloud_vs_local",
        prompt="Compare fully local multi-agent stacks versus paid cloud APIs and recommend one.",
        must_contain=["local"],
    ),
]


async def run_case(case: EvalCase) -> dict:
    from orchestrator.graph.workflow import run_task
    from orchestrator.llm.transcript import transcript_store
    from orchestrator.schemas import TaskRecord, TaskStatus
    from orchestrator.store import task_store
    from orchestrator.tracing.spans import trace_store

    task = TaskRecord(prompt=case.prompt, force_hitl=True, status=TaskStatus.queued)
    task_store.save(task)
    final = await run_task(task.id, case.prompt, force_hitl=True)
    saved = task_store.get(task.id)
    spans = trace_store.list_spans(task.id)
    turns = transcript_store.list_turns(task.id)
    deliverable = (saved.deliverable if saved else "") or final.get("deliverable") or ""

    checks = {
        "status_ok": saved is not None and saved.status.value == case.expect_status,
        "deliverable_ok": (not case.require_deliverable) or bool(deliverable.strip()),
        "spans_ok": len(spans) >= case.min_spans,
        "transcript_ok": len(turns) >= case.min_transcript_turns,
        "contains_ok": True,
    }
    if case.must_contain:
        low = deliverable.lower()
        checks["contains_ok"] = all(x.lower() in low for x in case.must_contain)

    passed = all(checks.values())
    return {
        "id": case.id,
        "passed": passed,
        "checks": checks,
        "task_id": task.id,
        "span_count": len(spans),
        "transcript_turns": len(turns),
        "deliverable_preview": deliverable[:240],
    }


async def main() -> int:
    results = []
    for case in CASES:
        results.append(await run_case(case))
    passed = sum(1 for r in results if r["passed"])
    report = {"passed": passed, "total": len(results), "results": results}
    print(json.dumps(report, indent=2))
    out = ROOT / "data" / "eval_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
