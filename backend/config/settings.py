"""
config/settings.py
Dynamic settings loaded from .env — nothing hardcoded.
All values come from environment variables with sensible defaults.
"""
from __future__ import annotations
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


_ROOT_ENV = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ROOT_ENV),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────
    app_name: str = Field(default="Echo", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    secret_key: str = Field(default="dev-secret-change-in-production", alias="SECRET_KEY")
    debug: bool = Field(default=True, alias="DEBUG")

    # ── API Server ───────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_reload: bool = Field(default=True, alias="API_RELOAD")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        alias="CORS_ORIGINS"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    # ── Ollama ───────────────────────────────────────────────
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.2", alias="OLLAMA_MODEL")
    ollama_embed_model: str = Field(default="nomic-embed-text", alias="OLLAMA_EMBED_MODEL")
    ollama_temperature: float = Field(default=0.3, alias="OLLAMA_TEMPERATURE")
    ollama_max_tokens: int = Field(default=2048, alias="OLLAMA_MAX_TOKENS")
    ollama_timeout: int = Field(default=60, alias="OLLAMA_TIMEOUT")

    # ── Database ─────────────────────────────────────────────
    sqlite_path: str = Field(default="data/echo_career.db", alias="SQLITE_PATH")

    # ── Vector Store ─────────────────────────────────────────
    vector_store_path: str = Field(default="data/vector_store", alias="VECTOR_STORE_PATH")
    vector_store_type: str = Field(default="faiss", alias="VECTOR_STORE_TYPE")
    embedding_dim: int = Field(default=768, alias="EMBEDDING_DIM")

    # ── Matching ─────────────────────────────────────────────
    match_threshold: float = Field(default=0.55, alias="MATCH_THRESHOLD")
    match_top_n: int = Field(default=20, alias="MATCH_TOP_N")
    llm_rerank_enabled: bool = Field(default=True, alias="LLM_RERANK_ENABLED")
    llm_rerank_min: float = Field(default=0.50, alias="LLM_RERANK_MIN")
    llm_rerank_max: float = Field(default=0.65, alias="LLM_RERANK_MAX")

    # ── Scraper ──────────────────────────────────────────────
    scrape_delay_seconds: int = Field(default=3, alias="SCRAPE_DELAY_SECONDS")
    scrape_max_retries: int = Field(default=2, alias="SCRAPE_MAX_RETRIES")
    scrape_random_delay: bool = Field(default=True, alias="SCRAPE_RANDOM_DELAY")
    agent_loop_hours: int = Field(default=6, alias="AGENT_LOOP_HOURS")

    # ── Candidate ────────────────────────────────────────────
    candidate_name: str = Field(default="", alias="CANDIDATE_NAME")
    candidate_email: str = Field(default="", alias="CANDIDATE_EMAIL")
    candidate_graduation_year: int = Field(default=2025, alias="CANDIDATE_GRADUATION_YEAR")
    candidate_experience_level: str = Field(default="fresher", alias="CANDIDATE_EXPERIENCE_LEVEL")

    # ── Reports ──────────────────────────────────────────────
    reports_dir: str = Field(default="data/reports", alias="REPORTS_DIR")
    report_time: str = Field(default="08:00", alias="REPORT_TIME")

    # ── Email ────────────────────────────────────────────────
    email_enabled: bool = Field(default=False, alias="EMAIL_ENABLED")
    email_smtp_host: str = Field(default="smtp.gmail.com", alias="EMAIL_SMTP_HOST")
    email_smtp_port: int = Field(default=587, alias="EMAIL_SMTP_PORT")
    email_sender: str = Field(default="", alias="EMAIL_SENDER")
    email_password: str = Field(default="", alias="EMAIL_PASSWORD")
    email_recipient: str = Field(default="", alias="EMAIL_RECIPIENT")

    # ── MCP ──────────────────────────────────────────────────
    mcp_host: str = Field(default="0.0.0.0", alias="MCP_HOST")
    mcp_port: int = Field(default=8001, alias="MCP_PORT")
    mcp_enabled: bool = Field(default=True, alias="MCP_ENABLED")

    # ── Derived paths (computed, not env) ────────────────────
    @property
    def db_path(self) -> Path:
        p = Path(self.sqlite_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def vs_path(self) -> Path:
        p = Path(self.vector_store_path)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def reports_path(self) -> Path:
        p = Path(self.reports_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


# Singleton
_settings: Settings | None = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
