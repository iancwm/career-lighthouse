# api/config.py
from dataclasses import dataclass

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - fallback for lightweight test envs
    BaseSettings = object
    SettingsConfigDict = None

from services.runtime_paths import default_data_path, default_query_log_path


class Settings(BaseSettings):
    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""
    allowed_origins: str = "http://localhost:3000"
    qdrant_url: str = ""          # set to http://host:6333 to use Qdrant server
    data_path: str = str(default_data_path())  # fallback: embedded client for local dev
    query_log_path: str = str(default_query_log_path())
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    # Admin key for protecting /api/kb/* and /api/sessions/* endpoints.
    # If empty, auth is bypassed (development mode only). Must be set in production.
    admin_key: str = ""
    llm_timeout_seconds: float = 30.0  # LLM_TIMEOUT_SECONDS env var
    llm_session_timeout_seconds: float = 90.0  # LLM_SESSION_TIMEOUT_SECONDS env var


if SettingsConfigDict is None:
    @dataclass
    class Settings:  # type: ignore[no-redef]
        anthropic_api_key: str = ""
        allowed_origins: str = "http://localhost:3000"
        qdrant_url: str = ""
        data_path: str = str(default_data_path())
        query_log_path: str = str(default_query_log_path())
        max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
        admin_key: str = ""
        llm_timeout_seconds: float = 30.0  # LLM_TIMEOUT_SECONDS env var
        llm_session_timeout_seconds: float = 90.0  # LLM_SESSION_TIMEOUT_SECONDS env var


settings = Settings()
