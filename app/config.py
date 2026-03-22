from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_name: str = "Benefits Digger"
    api_v1_prefix: str = "/api/v1"
    database_url: str = f"sqlite:///{(BASE_DIR / 'benefits_digger.db').as_posix()}"
    cors_origins: list[str] = ["*"]
    request_timeout_seconds: float = 20.0
    auto_sync_remote: bool = True
    max_results_per_section: int = 12
    admin_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite-preview"
    gemini_structured_temperature: float = 0.3
    gemini_chat_temperature: float = 0.7
    crawl_max_depth: int = 1
    crawl_max_pages_per_site: int = 8
    crawl_relevant_page_limit: int = 4
    crawl_max_programs_per_sync: int = 18
    static_dir: Path = BASE_DIR / "app" / "static"

    model_config = SettingsConfigDict(
        env_prefix="BENEFITS_DIGGER_",
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
