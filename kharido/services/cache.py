"""
Caching layer.

Two backends:
  1. diskcache.Cache  — raw scraper API responses (disk-based KV store, 24h TTL)
  2. SQLite (direct)  — structured CategoryCriteria objects with expiry dates

Both are keyed on normalised strings (category slug, URL, query fingerprint).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import diskcache

from kharido.config import get_settings
from kharido.models import CategoryCriteria


# ---------------------------------------------------------------------------
# Scraper response cache (diskcache)
# ---------------------------------------------------------------------------


class ScraperCache:
    """
    Disk-based cache for raw Apify API responses.

    Caching every raw response means repeated dev runs cost zero API credits.
    Default TTL is 24 hours (products change daily).
    """

    DEFAULT_TTL_SECONDS = 24 * 60 * 60

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        settings = get_settings()
        self._cache = diskcache.Cache(str(cache_dir or settings.cache_dir / "scraper"))

    def get(self, key: str) -> Optional[dict]:
        return self._cache.get(key)

    def set(self, key: str, value: dict, ttl: int = DEFAULT_TTL_SECONDS) -> None:
        self._cache.set(key, value, expire=ttl)

    def make_key(self, source: str, query_params: dict) -> str:
        """Deterministic cache key from source name + sorted query parameters."""
        params_str = "&".join(f"{k}={v}" for k, v in sorted(query_params.items()))
        return f"{source}::{params_str}"

    def close(self) -> None:
        self._cache.close()


# ---------------------------------------------------------------------------
# Criteria cache (SQLite)
# ---------------------------------------------------------------------------


class CriteriaCache:
    """
    SQLite-backed cache for CategoryCriteria objects.

    Schema
    ------
    criteria_cache (
        category       TEXT PRIMARY KEY,
        criteria_json  TEXT NOT NULL,
        cached_at      TEXT NOT NULL,   -- ISO-8601 UTC
        expires_at     TEXT NOT NULL    -- ISO-8601 UTC
    )
    """

    DEFAULT_TTL_DAYS = 30

    def __init__(self, db_path: Optional[Path] = None) -> None:
        settings = get_settings()
        self._db_path = str(db_path or settings.db_path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS criteria_cache (
                    category      TEXT PRIMARY KEY,
                    criteria_json TEXT NOT NULL,
                    cached_at     TEXT NOT NULL,
                    expires_at    TEXT NOT NULL
                )
                """
            )

    def get(self, category: str) -> Optional[CategoryCriteria]:
        """Return cached CategoryCriteria or None on miss or expiry."""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT criteria_json, expires_at FROM criteria_cache WHERE category = ?",
                (category,),
            ).fetchone()

        if row is None:
            return None

        criteria_json, expires_at = row
        if datetime.fromisoformat(expires_at) < datetime.now(tz=timezone.utc):
            return None  # expired

        return CategoryCriteria.model_validate_json(criteria_json)

    def set(
        self,
        category: str,
        criteria: CategoryCriteria,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> None:
        """Store CategoryCriteria with expiry timestamp."""
        now = datetime.now(tz=timezone.utc)
        expires = now + timedelta(days=ttl_days)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO criteria_cache
                    (category, criteria_json, cached_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    category,
                    criteria.model_dump_json(),
                    now.isoformat(),
                    expires.isoformat(),
                ),
            )

    def delete(self, category: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM criteria_cache WHERE category = ?", (category,))
