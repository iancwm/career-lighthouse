# api/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""
    allowed_origins: str = "http://localhost:3000"
    qdrant_url: str = ""          # set to http://host:6333 to use Qdrant server
    data_path: str = "./data/qdrant"  # fallback: embedded client for local dev
    query_log_path: str = "./logs/query_log.jsonl"

settings = Settings()
