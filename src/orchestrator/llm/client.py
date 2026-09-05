from __future__ import annotations

import json
import re
from contextvars import ContextVar
from typing import Any, Optional

import httpx

from orchestrator.config import settings
from orchestrator.runtime_llm import runtime_llm

# Set by graph nodes so transcripts can attribute turns to a task
current_task_id: ContextVar[Optional[str]] = ContextVar("current_task_id", default=None)
current_agent: ContextVar[str] = ContextVar("current_agent", default="")


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


class LLMClient:
    """Multi-provider chat + embed: ollama (default) | openai | anthropic | stub."""

    def __init__(self) -> None:
        pass

    @property
    def cfg(self) -> dict[str, Any]:
        return runtime_llm.get()

    @property
    def host(self) -> str:
        return str(self.cfg.get("ollama_host") or settings.ollama_host).rstrip("/")

    @property
    def stub(self) -> bool:
        cfg = self.cfg
        return bool(cfg.get("stub")) or cfg.get("llm_provider") == "stub"

    @property
    def provider(self) -> str:
        if self.stub:
            return "stub"
        return (self.cfg.get("llm_provider") or "ollama").lower()

    async def health(self) -> dict[str, Any]:
        if self.stub:
            return {"ok": True, "mode": "stub", "provider": "stub"}
        if self.provider == "openai":
            ok = bool(self.cfg.get("openai_api_key"))
            return {
                "ok": ok,
                "mode": "openai",
                "provider": "openai",
                "error": None if ok else "OPENAI_API_KEY missing",
                "model": runtime_llm.resolve_chat_model("supervisor"),
            }
        if self.provider == "anthropic":
            ok = bool(self.cfg.get("anthropic_api_key"))
            return {
                "ok": ok,
                "mode": "anthropic",
                "provider": "anthropic",
                "error": None if ok else "ANTHROPIC_API_KEY missing",
                "model": runtime_llm.resolve_chat_model("supervisor"),
            }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.host}/api/tags")
                r.raise_for_status()
                models = [m.get("name") for m in r.json().get("models", [])]
                return {"ok": True, "mode": "ollama", "provider": "ollama", "models": models}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "mode": "ollama", "provider": "ollama", "error": str(exc)}

    def _default_model(self, model: Optional[str], role: str = "supervisor") -> str:
        if model:
            return model
        return runtime_llm.resolve_chat_model(role)

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        format_json: bool = False,
        role: str = "supervisor",
    ) -> dict[str, Any]:
        model = self._default_model(model, role=role)
        if self.stub:
            resp = self._stub_chat(messages, format_json=format_json)
        elif self.provider == "openai":
            resp = await self._chat_openai(messages, model, temperature, format_json)
        elif self.provider == "anthropic":
            resp = await self._chat_anthropic(messages, model, temperature, format_json)
        else:
            resp = await self._chat_ollama(messages, model, temperature, format_json)

        resp["provider"] = "stub" if self.stub else self.provider
        await self._record_transcript(messages, resp, format_json=format_json)
        return resp

    async def _chat_ollama(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        format_json: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format_json:
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(f"{self.host}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
            content = data.get("message", {}).get("content", "")
            prompt_eval = int(
                data.get("prompt_eval_count")
                or estimate_tokens("".join(m["content"] for m in messages))
            )
            eval_count = int(data.get("eval_count") or estimate_tokens(content))
            return {
                "content": content,
                "model": model,
                "input_tokens": prompt_eval,
                "output_tokens": eval_count,
                "raw": data,
            }

    async def _chat_openai(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        format_json: bool,
    ) -> dict[str, Any]:
        if not self.cfg.get("openai_api_key"):
            raise RuntimeError("OPENAI_API_KEY not set — add it in Settings")
        headers = {"Authorization": f"Bearer {self.cfg['openai_api_key']}"}
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if format_json:
            body["response_format"] = {"type": "json_object"}
        base = self.cfg.get("openai_base_url") or settings.openai_base_url
        async with httpx.AsyncClient(timeout=180.0, base_url=base) as client:
            r = await client.post("/chat/completions", headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage") or {}
            return {
                "content": content,
                "model": model,
                "input_tokens": int(usage.get("prompt_tokens") or estimate_tokens("".join(m["content"] for m in messages))),
                "output_tokens": int(usage.get("completion_tokens") or estimate_tokens(content)),
                "raw": data,
            }

    async def _chat_anthropic(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        format_json: bool,
    ) -> dict[str, Any]:
        if not self.cfg.get("anthropic_api_key"):
            raise RuntimeError("ANTHROPIC_API_KEY not set — add it in Settings")
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        if format_json:
            system = (system + "\nRespond with valid JSON only.").strip()
        converted = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
        headers = {
            "x-api-key": self.cfg["anthropic_api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_tokens": 4096,
            "temperature": temperature,
            "system": system or "You are a helpful assistant.",
            "messages": converted or [{"role": "user", "content": "Hello"}],
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
            parts = data.get("content") or []
            content = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
            usage = data.get("usage") or {}
            return {
                "content": content,
                "model": model,
                "input_tokens": int(usage.get("input_tokens") or estimate_tokens(system + "".join(m["content"] for m in converted))),
                "output_tokens": int(usage.get("output_tokens") or estimate_tokens(content)),
                "raw": data,
            }

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self.stub:
            return [[float((hash(t) % 1000) / 1000.0)] * 8 for t in texts]
        if self.provider == "openai":
            return await self._embed_openai(texts)
        if self.provider == "anthropic":
            # Anthropic has no embeddings API — fall back to Ollama local embeds
            return await self._embed_ollama(texts)
        return await self._embed_ollama(texts)

    async def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        model = runtime_llm.resolve_embed_model()
        async with httpx.AsyncClient(timeout=60.0) as client:
            for text in texts:
                r = await client.post(
                    f"{self.host}/api/embeddings",
                    json={"model": model, "prompt": text},
                )
                r.raise_for_status()
                vectors.append(r.json()["embedding"])
        return vectors

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        if not self.cfg.get("openai_api_key"):
            raise RuntimeError("OPENAI_API_KEY not set — add it in Settings")
        headers = {"Authorization": f"Bearer {self.cfg['openai_api_key']}"}
        body = {"model": runtime_llm.resolve_embed_model(), "input": texts}
        base = self.cfg.get("openai_base_url") or settings.openai_base_url
        async with httpx.AsyncClient(timeout=60.0, base_url=base) as client:
            r = await client.post("/embeddings", headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
            ordered = sorted(data["data"], key=lambda x: x["index"])
            return [row["embedding"] for row in ordered]

    async def chat_json(
        self,
        *,
        system: str,
        user: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        role: str = "supervisor",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        resp = await self.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=model,
            temperature=temperature,
            format_json=True,
            role=role,
        )
        parsed = self._parse_json(resp["content"])
        return parsed, resp

    async def _record_transcript(
        self,
        messages: list[dict[str, str]],
        resp: dict[str, Any],
        *,
        format_json: bool,
    ) -> None:
        task_id = current_task_id.get()
        if not task_id:
            return
        try:
            from orchestrator.llm.transcript import transcript_store

            transcript_store.append(
                task_id=task_id,
                agent=current_agent.get() or "unknown",
                messages=messages,
                response=resp.get("content", ""),
                model=resp.get("model", ""),
                provider=resp.get("provider", self.provider),
                input_tokens=int(resp.get("input_tokens") or 0),
                output_tokens=int(resp.get("output_tokens") or 0),
                format_json=format_json,
            )
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise

    def _stub_chat(self, messages: list[dict[str, str]], format_json: bool = False) -> dict[str, Any]:
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        blob = (system + "\n" + user).lower()

        if format_json and ("execution plan" in blob or "subtasks" in blob or "supervisor agent" in blob):
            content = json.dumps(
                {
                    "goal": "Produce a research brief",
                    "confidence": 0.72,
                    "rationale": "Stub plan for offline demo",
                    "requires_human_plan_approval": False,
                    "subtasks": [
                        {
                            "description": "Research key facts about the topic",
                            "specialist": "research",
                            "depends_on": [],
                            "expected_output": "Bullet facts with sources",
                            "sensitive": False,
                        },
                        {
                            "description": "Analyze tradeoffs from the research",
                            "specialist": "analysis",
                            "depends_on": [],
                            "expected_output": "Tradeoff analysis",
                            "sensitive": False,
                        },
                        {
                            "description": "Write a concise executive brief",
                            "specialist": "writing",
                            "depends_on": [],
                            "expected_output": "1-page brief",
                            "sensitive": True,
                        },
                    ],
                }
            )
        elif format_json and "review" in blob:
            content = json.dumps({"passed": True, "score": 0.82, "feedback": "Stub review passed"})
        elif format_json and "tool results so far" in blob and "web_search" in blob:
            content = json.dumps(
                {
                    "thought": "I have search results",
                    "tool_calls": [],
                    "final_answer": (
                        "Key findings from research (stub):\n"
                        "- Local multi-agent systems reduce API spend to near-zero.\n"
                        "- HITL gates improve trust for sensitive deliverables.\n"
                        "- Hybrid memory (working + semantic) improves planning over time."
                    ),
                }
            )
        elif format_json and ("tool_calls" in blob or "available tools" in blob or "specialist agent" in blob):
            content = json.dumps(
                {
                    "thought": "Use web search then answer",
                    "tool_calls": [{"name": "web_search", "arguments": {"query": user[:120] or "AI agents"}}],
                    "final_answer": "",
                }
            )
        else:
            content = (
                "# Stub Deliverable\n\n"
                f"Topic context:\n{user[:500]}\n\n"
                "## Summary\nLocal stub LLM produced this offline brief for demo/testing.\n"
            )

        return {
            "content": content,
            "model": "stub",
            "input_tokens": estimate_tokens(user),
            "output_tokens": estimate_tokens(content),
            "raw": {},
        }


llm_client = LLMClient()
