import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_api_key: str = ""
    langsmith_api_key: str = ""
    langsmith_tracing: bool = True
    langsmith_project: str = "icecream-intel"

    groq_api_key: str = ""

    # "provider:model". Each tier falls back to the other provider on any error (quota, outage).
    model_fast: str = "groq:openai/gpt-oss-20b"
    model_fast_fallback: str = "google_genai:gemini-3.5-flash-lite"
    model_smart: str = "google_genai:gemini-3.5-flash"
    model_smart_fallback: str = "groq:openai/gpt-oss-120b"
    # Requests per minute per model. Free tiers: Gemini flash 5/min (20/day); Groq 30/min (1000/day).
    gemini_rpm: int = 5
    groq_rpm: int = 30

    data_dir: Path = Path("./data/store")
    max_question_chars: int = 2000
    max_upload_mb: int = 25
    max_sql_rows: int = 1000
    sql_timeout_s: float = 10.0

    gmaps_scraper_bin: Path | None = None  # default: first bin/google_maps_scraper* file
    gmaps_max_queries: int = 10
    gmaps_timeout_s: int = 900

    @property
    def db_path(self) -> Path:
        return self.data_dir / "brand.duckdb"

    @property
    def docs_dir(self) -> Path:
        return self.data_dir / "docs"


@lru_cache
def get_settings() -> Settings:
    # LangSmith and LiteLLM (used by PageIndex) read keys from os.environ, not from Settings
    load_dotenv()
    s = Settings()
    if s.google_api_key:
        os.environ.setdefault("GEMINI_API_KEY", s.google_api_key)  # the name LiteLLM looks for
    s.docs_dir.mkdir(parents=True, exist_ok=True)
    return s
