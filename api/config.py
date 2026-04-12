# api/config.py
from dataclasses import dataclass

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - fallback for lightweight test envs
    BaseSettings = object
    SettingsConfigDict = None


class Settings(BaseSettings):
    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""
    allowed_origins: str = "http://localhost:3000"
    qdrant_url: str = ""          # set to http://host:6333 to use Qdrant server
    data_path: str = "./data/qdrant"  # fallback: embedded client for local dev
    query_log_path: str = "./logs/query_log.jsonl"
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB


if SettingsConfigDict is None:
    @dataclass
    class Settings:  # type: ignore[no-redef]
        anthropic_api_key: str = ""
        allowed_origins: str = "http://localhost:3000"
        qdrant_url: str = ""
        data_path: str = "./data/qdrant"
        query_log_path: str = "./logs/query_log.jsonl"
        max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB


settings = Settings()
