from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    langsmith_api_key: str = ""
    langsmith_tracing: bool = True
    langsmith_project: str = "icecream-intel"

    model_fast: str = "claude-haiku-5-5"
    model_smart: str = "claude-sonnet-5-5"

    data_dir: Path = Path("./data/store")
    max_question_chars: int = 2000
    max_upload_mb: int = 25
    max_sql_rows: int = 1000
    sql_timeout_s: float = 10.0

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
    s.docs_dir.mkdir(parents=True, exist_ok=True)
    return s
