from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # llm provider: ollama | openai | anthropic (stub via ORCHESTRATOR_STUB_LLM)
    llm_provider: str = "ollama"
    ollama_host: str = "http://127.0.0.1:11434"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str = ""
    supervisor_model: str = "qwen2.5:7b"
    specialist_model: str = "qwen2.5:3b"
    embed_model: str = "nomic-embed-text"
    # When provider != ollama, these defaults apply unless overridden
    openai_supervisor_model: str = "gpt-4o-mini"
    openai_specialist_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    anthropic_supervisor_model: str = "claude-3-5-haiku-latest"
    anthropic_specialist_model: str = "claude-3-5-haiku-latest"

    # When set, /v1/* requires Authorization: Bearer <token> or X-API-Key
    orchestrator_api_token: str = ""

    orchestrator_stub_llm: bool = False
    orchestrator_auto_approve: bool = False
    hitl_force_final: bool = True
    max_specialist_retries: int = 2
    review_pass_threshold: float = 0.6
    plan_confidence_threshold: float = 0.55
    code_exec_timeout_sec: int = 8
    search_max_results: int = 5

    database_url: str = "postgresql+psycopg://orchestrator:orchestrator@127.0.0.1:5432/orchestrator"
    redis_url: str = "redis://127.0.0.1:6379/0"
    celery_broker_url: str = "redis://127.0.0.1:6379/1"
    celery_result_backend: str = "redis://127.0.0.1:6379/2"

    otel_service_name: str = "agent-orchestration"
    otel_exporter_otlp_endpoint: str = "http://127.0.0.1:4318"
    otel_enabled: bool = True

    # Optional LangSmith (free Developer tier) — off by default
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "agent-orchestration"

    code_sandbox: str = "local"  # local | e2b
    e2b_api_key: str = ""

    # JSON list: [{"name":"demo","command":"python","args":["mcp_servers/demo_server.py"]}]
    mcp_servers: str = ""
    mcp_enabled: bool = True

    # GitHub OAuth (Connect with GitHub) — optional; can also be set in Mission Control
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""
    orchestrator_public_url: str = "http://127.0.0.1:8000"
    frontend_public_url: str = "http://127.0.0.1:5173"

    data_dir: Path = Path("./data")
    workspace_dir: Path = Path("./data/workspace")
    chroma_dir: Path = Path("./data/chroma")

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)

    def resolve_chat_model(self, role: str = "supervisor") -> str:
        provider = (self.llm_provider or "ollama").lower()
        if provider == "openai":
            return self.openai_supervisor_model if role == "supervisor" else self.openai_specialist_model
        if provider == "anthropic":
            return self.anthropic_supervisor_model if role == "supervisor" else self.anthropic_specialist_model
        return self.supervisor_model if role == "supervisor" else self.specialist_model

    def resolve_embed_model(self) -> str:
        if (self.llm_provider or "ollama").lower() == "openai":
            return self.openai_embed_model
        return self.embed_model


settings = Settings()
