from __future__ import annotations

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class AgentAppSettings(BaseSettings):
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None
    LLM_MODEL: str = "gpt-4o-mini"

    RAG_API_BASE_URL: str = "http://127.0.0.1:8000"
    RAG_REQUEST_TIMEOUT_SEC: float = 30.0

    AGENT_DEFAULT_TEAM_ID: str = "team_test"
    AGENT_DEFAULT_TOP_K: int = 5
    AGENT_DEFAULT_RETRIEVAL_MODE: str = "hybrid_rerank"

    WEB_SEARCH_PROVIDER: str = "tavily"  # tavily / mock
    WEB_SEARCH_TOP_K_DEFAULT: int = 3
    TAVILY_API_KEY: str | None = None
    TAVILY_SEARCH_DEPTH: str = "basic"  # basic / advanced

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


agent_settings = AgentAppSettings()
