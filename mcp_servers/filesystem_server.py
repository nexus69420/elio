#!/usr/bin/env python3
"""Filesystem MCP server — agents can read/write under a configured root.

Env:
  FILESYSTEM_ROOT  absolute or relative path (default: ./data/workspace)
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("orchestrator-filesystem")

ROOT = Path(os.environ.get("FILESYSTEM_ROOT") or "./data/workspace").expanduser().resolve()
ROOT.mkdir(parents=True, exist_ok=True)


def _safe(rel: str) -> Path:
    rel = (rel or ".").replace("\\", "/").lstrip("/")
    target = (ROOT / rel).resolve()
    if not str(target).startswith(str(ROOT)):
        raise PermissionError(f"Path escapes FILESYSTEM_ROOT: {rel}")
    return target


@mcp.tool()
def fs_info() -> dict[str, Any]:
    """Return the configured filesystem root agents can access."""
    return {"root": str(ROOT), "exists": ROOT.exists()}


@mcp.tool()
def fs_list(path: str = ".", glob: Optional[str] = None) -> list[dict[str, Any]]:
    """List files and directories under a relative path."""
    base = _safe(path)
    if not base.exists():
        raise FileNotFoundError(path)
    if not base.is_dir():
        raise NotADirectoryError(path)
    entries = sorted(base.glob(glob)) if glob else sorted(base.iterdir())
    out = []
    for p in entries[:200]:
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        out.append(
            {
                "path": rel,
                "type": "dir" if p.is_dir() else "file",
                "size": p.stat().st_size if p.is_file() else None,
            }
        )
    return out


@mcp.tool()
def fs_read(path: str, max_chars: int = 12000) -> dict[str, Any]:
    """Read a text file relative to FILESYSTEM_ROOT."""
    target = _safe(path)
    if not target.is_file():
        raise FileNotFoundError(path)
    text = target.read_text(encoding="utf-8", errors="replace")
    return {
        "path": path,
        "content": text[:max_chars],
        "truncated": len(text) > max_chars,
        "chars": len(text),
    }


@mcp.tool()
def fs_write(path: str, content: str) -> dict[str, Any]:
    """Write a text file (creates parents). Requires human approval in Mission Control."""
    target = _safe(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": path, "bytes": target.stat().st_size, "root": str(ROOT)}


@mcp.tool()
def fs_mkdir(path: str) -> dict[str, Any]:
    """Create a directory. Requires human approval in Mission Control."""
    target = _safe(path)
    target.mkdir(parents=True, exist_ok=True)
    return {"path": path, "ok": True}


@mcp.tool()
def fs_delete(path: str) -> dict[str, Any]:
    """Delete a file or empty directory. Requires human approval in Mission Control."""
    target = _safe(path)
    if not target.exists():
        raise FileNotFoundError(path)
    if target.is_dir():
        shutil.rmtree(target)
        kind = "dir"
    else:
        target.unlink()
        kind = "file"
    return {"path": path, "deleted": kind}


if __name__ == "__main__":
    mcp.run(transport="stdio")
