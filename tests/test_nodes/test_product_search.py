"""Tests for the product_search node (ScraperClient mocked — no network)."""

from __future__ import annotations

import pytest

from kharido.models import ParsedQuery, PriceRange, Product
from kharido.nodes.product_search import product_search_node


def _make_product(product_id: str, title: str, price_inr: float | None = None) -> Product:
    return Product(
        product_id=product_id,
        title=title,
        price_inr=price_inr,
        source="offline_dataset",
    )


@pytest.fixture
def fake_scraper(monkeypatch):
    """Patch ScraperClient.search_products to return a fixed list."""
    products = [
        _make_product("eb-001", "boAt Airdopes 141", 999),
        _make_product("eb-002", "Sony WF-C500", 3990),
        _make_product("eb-003", "JBL Tune 215BT", 1999),
    ]

    from kharido.services import scraper as scraper_mod

    class _FakeScraper:
        def __init__(self):
            self.calls: list[dict] = []

        def search_products(self, **kwargs) -> list[Product]:
            self.calls.append(kwargs)
            return products

    fake = _FakeScraper()
    monkeypatch.setattr(scraper_mod, "ScraperClient", lambda: fake)
    return fake


def _state_with_query(
    category: str = "earbuds",
    price_max: float | None = 2000,
) -> dict:
    return {
        "raw_query": f"earbuds under {price_max}",
        "parsed_query": ParsedQuery(
            category=category,
            price_range=PriceRange(max_inr=price_max),
            raw_query=f"earbuds under {price_max}",
        ),
    }


def test_returns_candidates(fake_scraper):
    result = product_search_node(_state_with_query())
    assert "candidates" in result
    assert len(result["candidates"]) == 3
    assert result.get("error") is None


def test_passes_filters_to_scraper(fake_scraper):
    product_search_node(_state_with_query(category="earbuds", price_max=2000))
    assert fake_scraper.calls[0]["category"] == "earbuds"
    assert fake_scraper.calls[0]["price_max"] == 2000


def test_no_parsed_query_returns_error():
    result = product_search_node({"raw_query": "earbuds"})
    assert result["error"] is not None
    assert result["candidates"] == []


def test_empty_results_returns_error(monkeypatch):
    from kharido.services import scraper as scraper_mod

    monkeypatch.setattr(scraper_mod, "ScraperClient", lambda: type("F", (), {"search_products": lambda self, **kw: []})())
    result = product_search_node(_state_with_query())
    assert result.get("error") is not None
    assert result["candidates"] == []
