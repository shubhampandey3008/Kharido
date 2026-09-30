"""Tests for CriteriaCache — SQLite-backed criteria storage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from kharido.models import CategoryCriteria, Criterion
from kharido.services.cache import CriteriaCache


@pytest.fixture
def cache(tmp_path: Path) -> CriteriaCache:
    return CriteriaCache(db_path=tmp_path / "test_criteria.db")


def _make_criteria(category: str = "running_shoes") -> CategoryCriteria:
    return CategoryCriteria(
        category=category,
        criteria=[
            Criterion(
                name="wet_grip",
                description="Grip on wet surfaces",
                how_to_check="Check for rubber sole, rain reviews",
                weight=1.5,
            )
        ],
    )


def test_set_and_get(cache: CriteriaCache):
    criteria = _make_criteria()
    cache.set("running_shoes", criteria)
    result = cache.get("running_shoes")
    assert result is not None
    assert result.category == "running_shoes"
    assert len(result.criteria) == 1
    assert result.criteria[0].name == "wet_grip"


def test_miss_returns_none(cache: CriteriaCache):
    assert cache.get("nonexistent_category") is None


def test_expired_returns_none(cache: CriteriaCache, tmp_path: Path):
    """Write with ttl=0 so it expires immediately."""
    criteria = _make_criteria()
    cache.set("running_shoes", criteria, ttl_days=0)
    # With ttl_days=0 the expiry is now — it should be expired
    result = cache.get("running_shoes")
    assert result is None


def test_overwrite(cache: CriteriaCache):
    criteria1 = _make_criteria()
    cache.set("earbuds", criteria1)

    criteria2 = CategoryCriteria(
        category="earbuds",
        criteria=[
            Criterion(name="battery_life", description="Hours of use", how_to_check="Check spec sheet")
        ],
    )
    cache.set("earbuds", criteria2)

    result = cache.get("earbuds")
    assert result is not None
    assert result.criteria[0].name == "battery_life"


def test_delete(cache: CriteriaCache):
    cache.set("backpacks", _make_criteria("backpacks"))
    cache.delete("backpacks")
    assert cache.get("backpacks") is None
