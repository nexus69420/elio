from __future__ import annotations

from typing import Any, Optional


# USD per 1M tokens (approximate public list prices; update as needed)
# Local Ollama / stub are $0 by definition for this project's TCO story.
PRICE_SHEET: dict[str, dict[str, dict[str, float]]] = {
    "ollama": {"*": {"input": 0.0, "output": 0.0}},
    "stub": {"*": {"input": 0.0, "output": 0.0}},
    "openai": {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
        "gpt-4.1": {"input": 2.00, "output": 8.00},
        "o4-mini": {"input": 1.10, "output": 4.40},
        "text-embedding-3-small": {"input": 0.02, "output": 0.0},
        "text-embedding-3-large": {"input": 0.13, "output": 0.0},
        "*": {"input": 0.50, "output": 1.50},
    },
    "anthropic": {
        "claude-3-5-haiku-latest": {"input": 0.80, "output": 4.00},
        "claude-3-5-sonnet-latest": {"input": 3.00, "output": 15.00},
        "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
        "*": {"input": 3.00, "output": 15.00},
    },
}


def _rates(provider: str, model: str) -> dict[str, float]:
    provider = (provider or "ollama").lower()
    model = (model or "").strip()
    sheet = PRICE_SHEET.get(provider) or PRICE_SHEET["ollama"]
    if model in sheet:
        return sheet[model]
    # prefix match e.g. gpt-4o-mini-2024-07-18
    for key, rates in sheet.items():
        if key != "*" and model.startswith(key):
            return rates
    return sheet.get("*") or {"input": 0.0, "output": 0.0}


def cost_usd(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    rates = _rates(provider, model)
    return (input_tokens / 1_000_000.0) * float(rates["input"]) + (output_tokens / 1_000_000.0) * float(
        rates["output"]
    )


def estimate_task_cost(turns: list[dict[str, Any]]) -> dict[str, Any]:
    """Honest cost from transcript turns (provider + model + tokens per call)."""
    total = 0.0
    by_model: dict[str, dict[str, Any]] = {}
    input_tokens = output_tokens = 0
    for turn in turns:
        provider = turn.get("provider") or "ollama"
        model = turn.get("model") or "unknown"
        tin = int(turn.get("input_tokens") or 0)
        tout = int(turn.get("output_tokens") or 0)
        c = cost_usd(provider=provider, model=model, input_tokens=tin, output_tokens=tout)
        total += c
        input_tokens += tin
        output_tokens += tout
        key = f"{provider}/{model}"
        bucket = by_model.setdefault(
            key,
            {"provider": provider, "model": model, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        )
        bucket["input_tokens"] += tin
        bucket["output_tokens"] += tout
        bucket["cost_usd"] = round(bucket["cost_usd"] + c, 8)

    return {
        "cost_usd": round(total, 8),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "by_model": list(by_model.values()),
        "price_sheet_note": "USD list prices per 1M tokens; Ollama/stub = $0",
    }


def price_sheet_public() -> dict[str, Any]:
    return PRICE_SHEET
