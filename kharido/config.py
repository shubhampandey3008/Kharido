"""
Application configuration.

Loads environment variables from .env and exposes a single Settings singleton.
All other modules import from here rather than reading os.environ directly.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv(override=False)


class Settings(BaseSettings):
    # LLM
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")

    # Web search
    tavily_api_key: str = Field("", alias="TAVILY_API_KEY")

    # Scraping
    apify_api_token: str = Field("", alias="APIFY_API_TOKEN")

    # Tracing
    langchain_api_key: str = Field("", alias="LANGCHAIN_API_KEY")
    langchain_tracing_v2: str = Field("false", alias="LANGCHAIN_TRACING_V2")
    langchain_project: str = Field("kharido-dev", alias="LANGCHAIN_PROJECT")

    # Preference memory
    mem0_api_key: str = Field("", alias="MEM0_API_KEY")

    # App
    env: str = Field("development", alias="KHARIDO_ENV")
    log_level: str = Field("INFO", alias="KHARIDO_LOG_LEVEL")
    cache_dir: Path = Field(Path(".cache/kharido"), alias="KHARIDO_CACHE_DIR")
    db_path: Path = Field(Path(".cache/kharido.db"), alias="KHARIDO_DB_PATH")
    offline_dataset_dir: Path = Field(
        Path("data/offline_dataset"), alias="KHARIDO_OFFLINE_DATASET_DIR"
    )

    # Model selection
    reasoning_model: str = Field("claude-sonnet-4-6", alias="KHARIDO_REASONING_MODEL")
    extraction_model: str = Field(
        "claude-haiku-4-5-20251001", alias="KHARIDO_EXTRACTION_MODEL"
    )

    # Pipeline constants
    max_candidates: int = 8
    product_search_retry_budget: int = 3
    criteria_cache_ttl_days: int = 30
    criteria_min_per_category: int = 5
    criteria_max_per_category: int = 8

    model_config = {"populate_by_name": True}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.cache_dir.mkdir(parents=True, exist_ok=True)
    s.db_path.parent.mkdir(parents=True, exist_ok=True)
    return s


def configure_tracing() -> None:
    """Enable LangSmith tracing when LANGCHAIN_API_KEY is present."""
    s = get_settings()
    if s.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = s.langchain_api_key
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = s.langchain_project
