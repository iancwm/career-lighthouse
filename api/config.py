# api/config.py
from dataclasses import dataclass

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - fallback for lightweight test envs
    BaseSettings = object
    SettingsConfigDict = None

from services.runtime_paths import default_data_path, default_llm_trace_log_path, default_query_log_path


class Settings(BaseSettings):
    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""
    allowed_origins: str = "http://localhost:3000"
    qdrant_url: str = ""          # set to http://host:6333 to use Qdrant server
    data_path: str = str(default_data_path())  # fallback: embedded client for local dev
    query_log_path: str = str(default_query_log_path())
    llm_trace_log_path: str = str(default_llm_trace_log_path())
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    # Admin key for protecting /api/kb/* and /api/sessions/* endpoints.
    # If empty, auth is bypassed (development mode only). Must be set in production.
    admin_key: str = ""
    llm_timeout_seconds: float = 60.0  # LLM_TIMEOUT_SECONDS env var
    llm_session_timeout_seconds: float = 180.0  # LLM_SESSION_TIMEOUT_SECONDS env var
    llm_session_multi_pass_threshold_chars: int | None = None  # LLM_SESSION_MULTI_PASS_THRESHOLD_CHARS env var
    llm_session_multi_pass_chunk_tokens: int | None = None  # LLM_SESSION_MULTI_PASS_CHUNK_TOKENS env var
    llm_session_multi_pass_overlap_tokens: int | None = None  # LLM_SESSION_MULTI_PASS_OVERLAP_TOKENS env var
    llm_json_repair_enabled: bool | None = None
    llm_staged_extraction_enabled: bool | None = None
    llm_max_chunks_per_prompt: int | None = None
    llm_max_chunk_chars_for_prompt: int | None = None
    llm_chat_max_context_chars: int | None = None
    llm_chat_max_resume_chars: int | None = None
    llm_chat_max_chunks: int | None = None
    llm_chat_excerpt_preview_chars: int | None = None
    llm_brief_max_context_chars: int | None = None
    llm_brief_max_resume_chars: int | None = None
    llm_brief_max_chunks: int | None = None
    llm_brief_excerpt_preview_chars: int | None = None
    llm_analysis_max_input_chars: int | None = None
    llm_analysis_max_chunks: int | None = None
    llm_analysis_excerpt_preview_chars: int | None = None
    llm_track_draft_max_input_chars: int | None = None
    llm_track_draft_max_chunks: int | None = None
    llm_track_draft_excerpt_preview_chars: int | None = None
    llm_auto_complete_max_profile_chars: int | None = None
    langfuse_timeout_seconds: int = 30
    langfuse_flush_at: int = 1
    langfuse_flush_interval: float = 1.0
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = ""
    langfuse_host: str = ""
    langfuse_tracing_environment: str = "development"


if SettingsConfigDict is None:
    @dataclass
    class Settings:  # type: ignore[no-redef]
        anthropic_api_key: str = ""
        allowed_origins: str = "http://localhost:3000"
        qdrant_url: str = ""
        data_path: str = str(default_data_path())
        query_log_path: str = str(default_query_log_path())
        llm_trace_log_path: str = str(default_llm_trace_log_path())
        max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
        admin_key: str = ""
        llm_timeout_seconds: float = 60.0  # LLM_TIMEOUT_SECONDS env var
        llm_session_timeout_seconds: float = 180.0  # LLM_SESSION_TIMEOUT_SECONDS env var
        llm_session_multi_pass_threshold_chars: int | None = None
        llm_session_multi_pass_chunk_tokens: int | None = None
        llm_session_multi_pass_overlap_tokens: int | None = None
        llm_json_repair_enabled: bool | None = None
        llm_staged_extraction_enabled: bool | None = None
        llm_max_chunks_per_prompt: int | None = None
        llm_max_chunk_chars_for_prompt: int | None = None
        llm_chat_max_context_chars: int | None = None
        llm_chat_max_resume_chars: int | None = None
        llm_chat_max_chunks: int | None = None
        llm_chat_excerpt_preview_chars: int | None = None
        llm_brief_max_context_chars: int | None = None
        llm_brief_max_resume_chars: int | None = None
        llm_brief_max_chunks: int | None = None
        llm_brief_excerpt_preview_chars: int | None = None
        llm_analysis_max_input_chars: int | None = None
        llm_analysis_max_chunks: int | None = None
        llm_analysis_excerpt_preview_chars: int | None = None
        llm_track_draft_max_input_chars: int | None = None
        llm_track_draft_max_chunks: int | None = None
        llm_track_draft_excerpt_preview_chars: int | None = None
        llm_auto_complete_max_profile_chars: int | None = None
        langfuse_timeout_seconds: int = 30
        langfuse_flush_at: int = 1
        langfuse_flush_interval: float = 1.0
        langfuse_public_key: str = ""
        langfuse_secret_key: str = ""
        langfuse_base_url: str = ""
        langfuse_host: str = ""
        langfuse_tracing_environment: str = "development"


settings = Settings()
