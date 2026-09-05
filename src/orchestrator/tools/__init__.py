from orchestrator.tools.code_exec import code_exec
from orchestrator.tools.files import file_read, file_write
from orchestrator.tools.mcp_bridge import register_mcp_tools
from orchestrator.tools.native_github import register_native_github_tools
from orchestrator.tools.registry import ToolRegistry, ToolSpec, tool_registry
from orchestrator.tools.web_search import web_search

_BUILTINS_READY = False


def register_default_tools() -> ToolRegistry:
    global _BUILTINS_READY
    if not _BUILTINS_READY:
        tool_registry.register(
            ToolSpec(
                name="web_search",
                description="Search the public web for recent or factual information",
                parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                handler=web_search,
                timeout_sec=20,
            )
        )
        tool_registry.register(
            ToolSpec(
                name="file_write",
                description=(
                    "Write a text file inside the sandboxed workspace. "
                    "Use arguments {\"path\": \"relative/file.txt\", \"content\": \"...\"}. "
                    "Alias accepted: filename → path."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path under workspace"},
                        "filename": {"type": "string", "description": "Alias for path"},
                        "content": {"type": "string"},
                    },
                    "required": ["content"],
                },
                handler=file_write,
            )
        )
        tool_registry.register(
            ToolSpec(
                name="file_read",
                description=(
                    "Read a text file from the sandboxed workspace. "
                    "Use {\"path\": \"relative/file.txt\"} (filename alias ok)."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "filename": {"type": "string", "description": "Alias for path"},
                    },
                    "required": [],
                },
                handler=file_read,
            )
        )
        tool_registry.register(
            ToolSpec(
                name="code_exec",
                description="Execute a short Python snippet in a restricted local sandbox",
                parameters={"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
                handler=code_exec,
                timeout_sec=10,
            )
        )
        _BUILTINS_READY = True

    # Native first-party connectors (work inside Celery; no MCP stdio)
    register_native_github_tools(reload=True)
    # Optional third-party / demo MCP servers
    register_mcp_tools()
    return tool_registry


__all__ = ["tool_registry", "register_default_tools", "ToolRegistry", "ToolSpec", "register_mcp_tools"]
