# api/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    allowed_origins: str = "http://localhost:3000"
    data_path: str = "/data/qdrant"

    class Config:
        env_file = ".env"

settings = Settings()
