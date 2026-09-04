from __future__ import annotations

from typing import Any

from orchestrator.config import settings


def web_search(query: str, max_results: int | None = None) -> list[dict[str, Any]]:
    """Search the web via DuckDuckGo (no API key)."""
    max_results = max_results or settings.search_max_results
    try:
        try:
            from ddgs import DDGS
        except ImportError:  # pragma: no cover
            from duckduckgo_search import DDGS  # type: ignore

        results: list[dict[str, Any]] = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                results.append(
                    {
                        "title": item.get("title"),
                        "href": item.get("href"),
                        "body": item.get("body"),
                    }
                )
        if results:
            return results
    except Exception as exc:  # noqa: BLE001
        return [
            {
                "title": "Search unavailable (offline fallback)",
                "href": "",
                "body": f"Query={query}. Error={exc}. Use local knowledge.",
            }
        ]
    return [
        {
            "title": "No results",
            "href": "",
            "body": f"No DuckDuckGo hits for: {query}",
        }
    ]
