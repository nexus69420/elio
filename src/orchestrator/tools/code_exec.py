from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from orchestrator.config import settings

FORBIDDEN_SNIPPETS = (
    "import socket",
    "import urllib",
    "import requests",
    "import httpx",
    "from urllib",
    "subprocess",
    "os.system",
    "shutil.rmtree",
    "__import__",
    "open('/",
    'open("/',
)


def _local_exec(code: str) -> dict:
    lowered = code.lower()
    for bad in FORBIDDEN_SNIPPETS:
        if bad in lowered:
            raise ValueError(f"Forbidden pattern in code: {bad}")

    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "snippet.py"
        script.write_text(code, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=settings.code_exec_timeout_sec,
            cwd=tmp,
        )
        return {
            "sandbox": "local",
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-2000:],
        }


def _e2b_exec(code: str) -> dict:
    if not settings.e2b_api_key:
        raise RuntimeError("E2B_API_KEY not set")
    from e2b_code_interpreter import Sandbox

    with Sandbox.create(api_key=settings.e2b_api_key) as sandbox:
        execution = sandbox.run_code(code)
        stdout = ""
        stderr = ""
        if execution.logs:
            stdout = "\n".join(execution.logs.stdout or [])
            stderr = "\n".join(execution.logs.stderr or [])
        err = ""
        if execution.error:
            err = f"{execution.error.name}: {execution.error.value}"
        return {
            "sandbox": "e2b",
            "returncode": 1 if execution.error else 0,
            "stdout": (stdout or str(execution.text or ""))[-4000:],
            "stderr": (stderr or err)[-2000:],
        }


def code_exec(code: str) -> dict:
    """Execute code in E2B cloud sandbox when configured, else restricted local jail."""
    mode = (settings.code_sandbox or "local").lower()
    if mode == "e2b":
        try:
            return _e2b_exec(code)
        except Exception as exc:  # noqa: BLE001
            # Never break demos if credits/key missing
            local = _local_exec(code)
            local["fallback_from_e2b_error"] = str(exc)
            return local
    return _local_exec(code)
