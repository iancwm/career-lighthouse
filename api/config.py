# api/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""
    allowed_origins: str = "http://localhost:3000"
    data_path: str = "/data/qdrant"
    query_log_path: str = "./logs/query_log.jsonl"

settings = Settings()
