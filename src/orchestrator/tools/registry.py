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

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in self._tools.values()
        ]

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
            return {
                "name": name,
                "arguments": args,
                "ok": True,
                "result": result,
                "latency_ms": (time.time() - started) * 1000,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "name": name,
                "arguments": args,
                "ok": False,
                "error": str(exc),
                "latency_ms": (time.time() - started) * 1000,
            }

    def schemas_for_prompt(self) -> str:
        lines = []
        for t in self._tools.values():
            lines.append(f"- {t.name}: {t.description} | params={t.parameters}")
        return "\n".join(lines)


tool_registry = ToolRegistry()
