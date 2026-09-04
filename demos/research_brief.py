from __future__ import annotations

"""Submit flagship demo; resolves HITL via API if needed."""

import os
import sys
import time

import httpx

API = os.getenv("ORCHESTRATOR_API", "http://127.0.0.1:8000")
PROMPT = (
    "Research the tradeoffs of running multi-agent LLM systems fully locally "
    "versus using paid cloud APIs. Analyze cost, latency, quality, and privacy. "
    "Write a short executive brief with a recommendation."
)


def main() -> int:
    client = httpx.Client(base_url=API, timeout=30.0)
    print("health:", client.get("/health").json())
    task = client.post("/v1/tasks", json={"prompt": PROMPT, "force_hitl": True}).json()
    task_id = task["id"]
    print("queued via Celery:", task_id)

    for _ in range(300):
        for item in client.get("/v1/approvals", params={"task_id": task_id}).json():
            print("approving", item["id"])
            client.post(f"/v1/approvals/{item['id']}", json={"action": "approve", "note": "demo"})
        t = client.get(f"/v1/tasks/{task_id}").json()
        print("status:", t["status"])
        if t["status"] in {"completed", "failed", "rejected"}:
            print(t.get("deliverable") or t.get("error"))
            print("tokens:", client.get(f"/v1/traces/{task_id}").json().get("tokens"))
            return 0 if t["status"] == "completed" else 1
        time.sleep(1)
    print("timeout", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
