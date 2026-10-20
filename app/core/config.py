from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    langsmith_api_key: str = ""
    langsmith_tracing: bool = True
    langsmith_project: str = "icecream-intel"

    model_fast: str = "claude-haiku-5-5"
    model_smart: str = "claude-sonnet-5-5"

    data_dir: Path = Path("./data/store")
    max_question_chars: int = 2000
    max_upload_mb: int = 25


@lru_cache
def get_settings() -> Settings:
    return Settings()
