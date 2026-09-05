from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Optional

import redis
from pydantic import BaseModel, Field

from orchestrator.config import settings

REDIS_KEY = "orchestrator:agents_runtime"

SPECIALIST_IDS = ("research", "analysis", "writing", "code")
ALL_AGENT_IDS = ("supervisor", "research", "analysis", "writing", "code", "reviewer")

DEFAULT_ROLE_TOOLS: dict[str, list[str]] = {
    "research": ["web_search", "file_write"],
    "analysis": ["file_read", "code_exec", "file_write"],
    "writing": ["file_read", "file_write"],
    "code": ["code_exec", "file_read", "file_write"],
}


def _default_agents() -> dict[str, dict[str, Any]]:
    return {
        "supervisor": {
            "id": "supervisor",
            "display_name": "Supervisor",
            "kind": "supervisor",
            "instructions": (
                "Prefer lean plans. Prefer 3 subtasks: research, analysis, writing. "
                "Mark the final writing subtask sensitive when the deliverable is user-facing."
            ),
            "output_contract": "",
            "tools": [],
            "model": "",
            "requires_hitl": False,
            "enabled": True,
        },
        "research": {
            "id": "research",
            "display_name": "Research",
            "kind": "specialist",
            "instructions": (
                "Produce sourced bullet facts, not essays. "
                "For the user's own apps/accounts (GitHub repos, Slack, local files), "
                "prefer mcp_* connector tools over web_search. "
                "Use web_search only for public web research. Keep it tight."
            ),
            "output_contract": "Bulleted facts with sources.",
            "tools": list(DEFAULT_ROLE_TOOLS["research"]),
            "model": "",
            "requires_hitl": False,
            "enabled": True,
        },
        "analysis": {
            "id": "analysis",
            "display_name": "Analysis",
            "kind": "specialist",
            "instructions": (
                "Produce tradeoffs / comparisons / a clear recommendation grounded in prior research. "
                "Do NOT use code_exec just to print strings — only for real computation. "
                "Stay structured and concise."
            ),
            "output_contract": "Tradeoffs + recommendation.",
            "tools": list(DEFAULT_ROLE_TOOLS["analysis"]),
            "model": "",
            "requires_hitl": False,
            "enabled": True,
        },
        "writing": {
            "id": "writing",
            "display_name": "Writing",
            "kind": "specialist",
            "instructions": (
                "Produce the final user-facing text in EXACTLY the format the user asked for "
                "(e.g. if they asked for 3 bullets, output exactly 3 bullets — nothing else). "
                'file_write args MUST be {"path": "...", "content": "..."}.'
            ),
            "output_contract": "Match the user's requested format exactly.",
            "tools": list(DEFAULT_ROLE_TOOLS["writing"]),
            "model": "",
            "requires_hitl": True,
            "enabled": True,
        },
        "code": {
            "id": "code",
            "display_name": "Code",
            "kind": "specialist",
            "instructions": (
                "Write and run real code to verify claims. Prefer code_exec with actual logic, not print-only stubs."
            ),
            "output_contract": "Verified code + results.",
            "tools": list(DEFAULT_ROLE_TOOLS["code"]),
            "model": "",
            "requires_hitl": False,
            "enabled": True,
        },
        "reviewer": {
            "id": "reviewer",
            "display_name": "Reviewer",
            "kind": "reviewer",
            "instructions": (
                "Be strict. Prefer failing for retry over rubber-stamping. "
                "Fail when format constraints are ignored or tool failures are papered over."
            ),
            "output_contract": 'JSON only: {"passed": bool, "score": 0-1, "feedback": string}',
            "tools": [],
            "model": "",
            "requires_hitl": False,
            "enabled": True,
        },
    }


def _builtin_presets() -> dict[str, dict[str, Any]]:
    return {
        "research_brief": {
            "id": "research_brief",
            "name": "Research brief",
            "description": "Sourced research → tradeoffs → short executive brief with a recommendation.",
            "force_hitl": True,
            "builtin": True,
            "agent_overlays": {
                "research": {
                    "display_name": "Research",
                    "instructions": (
                        "Gather only the highest-signal facts. Prefer web_search. "
                        "Cite titles/URLs. No essays."
                    ),
                    "output_contract": "5–8 sourced bullets.",
                    "tools": ["web_search", "file_write"],
                    "requires_hitl": False,
                },
                "analysis": {
                    "display_name": "Analysis",
                    "instructions": (
                        "Compare options with explicit tradeoffs. End with one clear recommendation."
                    ),
                    "output_contract": "Tradeoffs table + 1 recommendation paragraph.",
                    "tools": ["file_read", "code_exec", "file_write"],
                    "requires_hitl": False,
                },
                "writing": {
                    "display_name": "Writing",
                    "instructions": (
                        "Write a short executive brief for a busy decision-maker. "
                        "Lead with the recommendation, then 3 supporting points."
                    ),
                    "output_contract": "≤1 page: recommendation + 3 bullets + risks.",
                    "tools": ["file_read", "file_write"],
                    "requires_hitl": True,
                },
            },
        },
        "code_review": {
            "id": "code_review",
            "name": "Code review",
            "description": "Security-minded review: research patterns, analyze risks, write actionable findings.",
            "force_hitl": True,
            "builtin": True,
            "agent_overlays": {
                "research": {
                    "display_name": "Threat research",
                    "instructions": (
                        "Identify relevant failure modes, CVEs patterns, and best practices. Cite sources."
                    ),
                    "output_contract": "Bulleted risk catalogue with sources.",
                    "tools": ["web_search", "file_read", "file_write"],
                },
                "analysis": {
                    "display_name": "Security analysis",
                    "instructions": (
                        "Prioritize findings by severity. Prefer concrete evidence over speculation. "
                        "Use code_exec only if needed to validate logic."
                    ),
                    "output_contract": "Severity-ordered findings (Critical/High/Med/Low).",
                    "tools": ["file_read", "code_exec", "file_write"],
                },
                "writing": {
                    "display_name": "Review writeup",
                    "instructions": (
                        "Write a blunt code-review memo: findings, evidence, suggested fixes. No fluff."
                    ),
                    "output_contract": "Markdown review: summary, findings list, next steps.",
                    "tools": ["file_read", "file_write"],
                    "requires_hitl": True,
                },
                "code": {
                    "display_name": "Repro",
                    "instructions": "Reproduce or disprove claims with minimal runnable snippets via code_exec.",
                    "output_contract": "Minimal repro + observed result.",
                    "tools": ["code_exec", "file_read", "file_write"],
                },
                "reviewer": {
                    "instructions": (
                        "Fail reviews that lack severity ranking, evidence, or actionable fixes."
                    ),
                },
            },
        },
        "job_application": {
            "id": "job_application",
            "name": "Job application",
            "description": "Research the role/company, analyze fit, draft a tailored application brief.",
            "force_hitl": True,
            "builtin": True,
            "agent_overlays": {
                "research": {
                    "display_name": "Company research",
                    "instructions": (
                        "Research company, role, and recent news. Prefer web_search. Cite sources."
                    ),
                    "output_contract": "Company/role facts with sources.",
                    "tools": ["web_search", "file_write"],
                },
                "analysis": {
                    "display_name": "Fit analysis",
                    "instructions": (
                        "Map candidate strengths to the role. Call out gaps honestly."
                    ),
                    "output_contract": "Fit matrix + gaps + talking points.",
                    "tools": ["file_read", "file_write"],
                },
                "writing": {
                    "display_name": "Application writer",
                    "instructions": (
                        "Draft a tailored cover note and 3 interview talking points. "
                        "Tone: professional, specific, no buzzword salad."
                    ),
                    "output_contract": "Cover note (≤250 words) + 3 talking points.",
                    "tools": ["file_read", "file_write"],
                    "requires_hitl": True,
                },
            },
        },
    }


class AgentProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    instructions: Optional[str] = None
    output_contract: Optional[str] = None
    tools: Optional[list[str]] = None
    model: Optional[str] = None
    requires_hitl: Optional[bool] = None
    enabled: Optional[bool] = None


class AgentsBulkUpdate(BaseModel):
    agents: dict[str, AgentProfileUpdate] = Field(default_factory=dict)
    active_preset_id: Optional[str] = None
    clear_active_preset: bool = False


def _merge_agent(base: dict[str, Any], overlay: dict[str, Any] | None) -> dict[str, Any]:
    out = deepcopy(base)
    if not overlay:
        return out
    for key in (
        "display_name",
        "instructions",
        "output_contract",
        "tools",
        "model",
        "requires_hitl",
        "enabled",
    ):
        if key in overlay and overlay[key] is not None:
            out[key] = overlay[key]
    out["id"] = base["id"]
    out["kind"] = base.get("kind", out.get("kind", "specialist"))
    return out


class RuntimeAgentsConfig:
    """Redis-backed agent profiles + team presets. Defaults in code; overlays win."""

    def __init__(self) -> None:
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        return self._client

    def _store(self) -> dict[str, Any]:
        try:
            raw = self.client.get(REDIS_KEY)
            if not raw:
                return {}
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001
            return {}

    def _save(self, store: dict[str, Any]) -> None:
        self.client.set(REDIS_KEY, json.dumps(store))

    def _user_presets(self) -> dict[str, dict[str, Any]]:
        store = self._store()
        raw = store.get("presets") or {}
        return raw if isinstance(raw, dict) else {}

    def list_presets(self) -> list[dict[str, Any]]:
        builtins = _builtin_presets()
        merged = {**builtins, **self._user_presets()}
        out = []
        for p in merged.values():
            item = {
                "id": p["id"],
                "name": p.get("name") or p["id"],
                "description": p.get("description") or "",
                "force_hitl": bool(p.get("force_hitl", True)),
                "builtin": bool(p.get("builtin", False)),
                "agent_ids": list((p.get("agent_overlays") or {}).keys()),
            }
            out.append(item)
        out.sort(key=lambda x: (not x["builtin"], x["name"].lower()))
        return out

    def get_preset(self, preset_id: str) -> Optional[dict[str, Any]]:
        if not preset_id:
            return None
        if preset_id in _builtin_presets():
            return deepcopy(_builtin_presets()[preset_id])
        user = self._user_presets().get(preset_id)
        return deepcopy(user) if user else None

    def resolved_agents(self, preset_id: Optional[str] = None) -> dict[str, dict[str, Any]]:
        """Defaults ← Redis overlays ← optional run-scoped preset overlays."""
        defaults = _default_agents()
        store = self._store()
        overlays = store.get("agents") or {}
        if not isinstance(overlays, dict):
            overlays = {}

        agents = {
            aid: _merge_agent(defaults[aid], overlays.get(aid) if isinstance(overlays.get(aid), dict) else None)
            for aid in ALL_AGENT_IDS
        }

        if preset_id:
            preset = self.get_preset(str(preset_id))
            if preset:
                for aid, ov in (preset.get("agent_overlays") or {}).items():
                    if aid in agents and isinstance(ov, dict):
                        agents[aid] = _merge_agent(agents[aid], ov)

        return agents

    def get_agent(self, agent_id: str, preset_id: Optional[str] = None) -> dict[str, Any]:
        agents = self.resolved_agents(preset_id=preset_id)
        if agent_id not in agents:
            raise KeyError(agent_id)
        return agents[agent_id]

    def public_snapshot(self, available_tools: Optional[list[str]] = None) -> dict[str, Any]:
        store = self._store()
        agents = self.resolved_agents()
        return {
            "agents": list(agents.values()),
            "presets": self.list_presets(),
            "active_preset_id": store.get("active_preset_id"),
            "available_tools": available_tools or [],
            "defaults": list(_default_agents().values()),
        }

    def update_agent(self, agent_id: str, body: AgentProfileUpdate) -> dict[str, Any]:
        if agent_id not in ALL_AGENT_IDS:
            raise KeyError(agent_id)
        store = self._store()
        agents = store.get("agents") if isinstance(store.get("agents"), dict) else {}
        current = dict(agents.get(agent_id) or {})
        data = body.model_dump(exclude_unset=True)
        for k, v in data.items():
            if v is not None:
                current[k] = v
        agents[agent_id] = current
        store["agents"] = agents
        # Editing customizes team — clear active preset label if drifting
        if store.get("active_preset_id"):
            store["active_preset_id"] = None
        self._save(store)
        return self.get_agent(agent_id)

    def update_many(self, body: AgentsBulkUpdate) -> dict[str, Any]:
        store = self._store()
        agents = store.get("agents") if isinstance(store.get("agents"), dict) else {}
        for aid, patch in body.agents.items():
            if aid not in ALL_AGENT_IDS:
                continue
            current = dict(agents.get(aid) or {})
            for k, v in patch.model_dump(exclude_unset=True).items():
                if v is not None:
                    current[k] = v
            agents[aid] = current
        store["agents"] = agents
        if body.clear_active_preset:
            store["active_preset_id"] = None
        elif body.active_preset_id is not None:
            store["active_preset_id"] = body.active_preset_id
        self._save(store)
        return self.public_snapshot()

    def apply_preset(self, preset_id: str) -> dict[str, Any]:
        preset = self.get_preset(preset_id)
        if not preset:
            raise KeyError(preset_id)
        store = self._store()
        agents = store.get("agents") if isinstance(store.get("agents"), dict) else {}
        for aid, ov in (preset.get("agent_overlays") or {}).items():
            if aid not in ALL_AGENT_IDS or not isinstance(ov, dict):
                continue
            current = dict(agents.get(aid) or {})
            for k, v in ov.items():
                if k in {"display_name", "instructions", "output_contract", "tools", "model", "requires_hitl", "enabled"}:
                    current[k] = v
            agents[aid] = current
        store["agents"] = agents
        store["active_preset_id"] = preset_id
        self._save(store)
        return self.public_snapshot()

    def reset_defaults(self) -> dict[str, Any]:
        self._save({"agents": {}, "active_preset_id": None, "presets": self._user_presets()})
        return self.public_snapshot()

    def save_preset_from_current(
        self,
        preset_id: str,
        name: str,
        description: str = "",
        force_hitl: bool = True,
    ) -> dict[str, Any]:
        if not preset_id or preset_id in _builtin_presets():
            raise ValueError("Choose a new non-builtin preset id")
        agents = self.resolved_agents(preset_id=None)
        overlays = {
            aid: {
                "display_name": a["display_name"],
                "instructions": a["instructions"],
                "output_contract": a.get("output_contract") or "",
                "tools": list(a.get("tools") or []),
                "model": a.get("model") or "",
                "requires_hitl": bool(a.get("requires_hitl")),
                "enabled": bool(a.get("enabled", True)),
            }
            for aid, a in agents.items()
        }
        store = self._store()
        presets = store.get("presets") if isinstance(store.get("presets"), dict) else {}
        presets[preset_id] = {
            "id": preset_id,
            "name": name or preset_id,
            "description": description,
            "force_hitl": force_hitl,
            "builtin": False,
            "agent_overlays": overlays,
        }
        store["presets"] = presets
        store["active_preset_id"] = preset_id
        self._save(store)
        return self.public_snapshot()

    def role_rules(self, role: str, preset_id: Optional[str] = None) -> str:
        agent = self.get_agent(role, preset_id=preset_id)
        parts = [agent.get("instructions") or "Stay concise and factual."]
        contract = (agent.get("output_contract") or "").strip()
        if contract:
            parts.append(f"Output contract: {contract}")
        return " ".join(parts)

    def tool_names_for_role(self, role: str, preset_id: Optional[str] = None, mcp_tools: Optional[list[str]] = None) -> list[str]:
        agent = self.get_agent(role, preset_id=preset_id)
        mcp = list(mcp_tools or [])
        configured = list(agent.get("tools") or [])
        if "*" in configured:
            allow = list(DEFAULT_ROLE_TOOLS.get(role, ["file_read", "file_write"]))
        else:
            allow = [t for t in configured if t != "*"]
        # Live MCP tools stay available (Connectors page controls which exist).
        for m in mcp:
            if m not in allow:
                allow.append(m)
        return allow

    def model_for(self, agent_id: str, preset_id: Optional[str] = None) -> Optional[str]:
        agent = self.get_agent(agent_id, preset_id=preset_id)
        model = (agent.get("model") or "").strip()
        return model or None

    def requires_hitl(self, agent_id: str, preset_id: Optional[str] = None) -> bool:
        return bool(self.get_agent(agent_id, preset_id=preset_id).get("requires_hitl"))


runtime_agents = RuntimeAgentsConfig()
