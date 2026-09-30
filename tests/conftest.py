"""Shared fixtures for the Kharido test suite."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from kharido.config import Settings, get_settings


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch):
    """
    Override settings to use a temporary directory for cache and DB.

    Applied automatically to every test (autouse=True).
    """
    test_settings = Settings(
        _env_file=None,  # don't read .env in tests
        cache_dir=tmp_path / "cache",
        db_path=tmp_path / "test.db",
        offline_dataset_dir=Path("data/offline_dataset"),
    )
    test_settings.cache_dir.mkdir(parents=True, exist_ok=True)

    # Clear the lru_cache so tests get the patched settings
    get_settings.cache_clear()
    monkeypatch.setattr("kharido.config.get_settings", lambda: test_settings)

    yield test_settings

    get_settings.cache_clear()
