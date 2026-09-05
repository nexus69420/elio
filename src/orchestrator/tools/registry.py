from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    timeout_sec: float = 30.0
    rate_limit_per_min: int = 30
    requires_approval: bool = False
    _calls: list[float] = field(default_factory=list)

    def check_rate_limit(self) -> None:
        now = time.time()
        self._calls = [t for t in self._calls if now - t < 60]
        if len(self._calls) >= self.rate_limit_per_min:
            raise RuntimeError(f"Rate limit exceeded for tool {self.name}")
        self._calls.append(now)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def unregister_prefix(self, prefix: str) -> int:
        names = [n for n in list(self._tools) if n.startswith(prefix)]
        for n in names:
            del self._tools[n]
        return len(names)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "requires_approval": bool(t.requires_approval),
            }
            for t in self._tools.values()
        ]

    def requires_approval(self, name: str) -> bool:
        try:
            return bool(self.get(name).requires_approval)
        except KeyError:
            return False

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def invoke(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        spec = self.get(name)
        spec.check_rate_limit()
        started = time.time()
        args = dict(arguments or {})
        # Common LLM param aliases for file tools
        if name in {"file_write", "file_read"} and "path" not in args:
            for alias in ("filename", "file", "name", "filepath", "file_path"):
                if alias in args and args[alias]:
                    args["path"] = args[alias]
                    break
        if name == "file_write" and "content" not in args and "text" in args:
            args["content"] = args["text"]
        try:
            result = spec.handler(**args)
            out = {
                "name": name,
                "arguments": args,
                "ok": True,
                "result": result,
                "latency_ms": (time.time() - started) * 1000,
            }
        except Exception as exc:  # noqa: BLE001
            out = {
                "name": name,
                "arguments": args,
                "ok": False,
                "error": str(exc),
                "latency_ms": (time.time() - started) * 1000,
            }
        try:
            from orchestrator.audit import audit_log
            from orchestrator.llm.client import current_task_id

            task_id = current_task_id.get() or ""
            # Avoid logging huge file contents
            safe_args = {k: (f"<{len(str(v))} chars>" if k in {"content", "code", "text"} else v) for k, v in args.items()}
            audit_log.record(
                action="tool.invoked",
                actor="agent",
                task_id=task_id,
                resource_type="tool",
                resource_id=name,
                detail={"ok": out.get("ok"), "arguments": safe_args, "error": out.get("error", "")},
            )
        except Exception:  # noqa: BLE001
            pass
        return out

    def schemas_for_prompt(self) -> str:
        lines = []
        for t in self._tools.values():
            lines.append(f"- {t.name}: {t.description} | params={t.parameters}")
        return "\n".join(lines)


tool_registry = ToolRegistry()
