from __future__ import annotations

import re


_PREFIXES = (
    "in 3 bullets:",
    "in three bullets:",
    "please ",
    "can you ",
    "could you ",
    "i want you to ",
    "write a ",
    "write me ",
    "help me ",
    "research and ",
)


def title_from_prompt(prompt: str, max_len: int = 64) -> str:
    """ChatGPT-style conversation title from the user prompt (instant, no LLM)."""
    text = " ".join((prompt or "").strip().split())
    if not text:
        return "Untitled run"
    lower = text.lower()
    for p in _PREFIXES:
        if lower.startswith(p):
            text = text[len(p) :].strip(" :-—,.")
            lower = text.lower()
            break
    # Prefer first sentence / clause
    for sep in (". ", "? ", "! ", "\n"):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
            break
    text = re.sub(r"^[\W_]+", "", text)
    if not text:
        return "Untitled run"
    if len(text) > max_len:
        cut = text[: max_len + 1].rsplit(" ", 1)[0]
        text = (cut or text[:max_len]).rstrip(".,;:") + "…"
    # Title-ish: capitalize first letter only (keep model names / acronyms)
    return text[0].upper() + text[1:] if text else "Untitled run"


async def polish_title(prompt: str, fallback: str = "") -> str:
    """Short LLM title (3–7 words). Falls back to heuristic on any failure."""
    base = fallback or title_from_prompt(prompt)
    try:
        from orchestrator.llm.client import llm_client

        if llm_client.stub:
            return base
        resp = await llm_client.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate a short chat title for this user task. "
                        "3 to 7 words. No quotes. No trailing punctuation. "
                        "Title Case preferred. Do not start with 'Task' or 'Run'."
                    ),
                },
                {"role": "user", "content": prompt[:800]},
            ],
            temperature=0.2,
            role="specialist",
        )
        title = " ".join((resp.get("content") or "").strip().split())
        title = title.strip("\"'`").rstrip(".")
        if 2 <= len(title) <= 80:
            return title
    except Exception:  # noqa: BLE001
        pass
    return base
