from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from orchestrator.config import settings


def _safe_path(rel_path: str) -> Path:
    settings.ensure_dirs()
    root = settings.workspace_dir.resolve()
    target = (root / rel_path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("Path escapes workspace sandbox")
    return target


def _resolve_path_arg(
    path: Optional[str] = None,
    filename: Optional[str] = None,
    file: Optional[str] = None,
    name: Optional[str] = None,
    **_: Any,
) -> str:
    resolved = path or filename or file or name
    if not resolved or not str(resolved).strip():
        raise ValueError("path is required (aliases: filename, file, name)")
    return str(resolved).strip()


def file_write(
    path: Optional[str] = None,
    content: str = "",
    filename: Optional[str] = None,
    file: Optional[str] = None,
    name: Optional[str] = None,
    **kwargs: Any,
) -> dict:
    """Write text into the workspace. Accepts path aliases: filename, file, name."""
    if content is None and "text" in kwargs:
        content = kwargs["text"]
    if content is None:
        content = ""
    rel = _resolve_path_arg(path=path, filename=filename, file=file, name=name, **kwargs)
    target = _safe_path(rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(content), encoding="utf-8")
    return {
        "path": str(target.relative_to(settings.workspace_dir.resolve())),
        "bytes": len(str(content).encode("utf-8")),
    }


def file_read(
    path: Optional[str] = None,
    filename: Optional[str] = None,
    file: Optional[str] = None,
    name: Optional[str] = None,
    **kwargs: Any,
) -> dict:
    rel = _resolve_path_arg(path=path, filename=filename, file=file, name=name, **kwargs)
    target = _safe_path(rel)
    if not target.exists():
        raise FileNotFoundError(f"No such file: {rel}")
    content = target.read_text(encoding="utf-8")
    return {"path": rel, "content": content}
