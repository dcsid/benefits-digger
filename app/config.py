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

