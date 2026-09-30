"""
ScrapingBee product and review scraper client.

Provides a unified interface that tries the disk cache first, then
ScrapingBee, and falls back to the offline JSON dataset.

In V1 development the offline dataset is the primary source (ScrapingBee
call is stubbed) to avoid burning free API credits during iteration.
Flip to API-first in Week 2 once the normalisation logic is solid.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import structlog

from kharido.config import get_settings
from kharido.models import Product

log = structlog.get_logger(__name__)


class ScraperClient:
    """
    Normalised product-search client.

    Search flow (V1)
    ----------------
    1. Always use offline dataset (ScrapingBee stubbed).
    2. V2: Check ScraperCache → ScrapingBee API → offline fallback.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def search_products(
        self,
        category: str,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        must_have: Optional[list[str]] = None,
        must_avoid: Optional[list[str]] = None,
        max_results: int = 10,
    ) -> list[Product]:
        """
        Search for products matching the given filters.

        Returns a list of normalised Product objects.

        TODO
        ----
        - Check ScraperCache for this query fingerprint
        - On cache miss: call ScrapingBee, parse HTML with trafilatura/BeautifulSoup
        - Normalise raw fields into Product schema
        - Cache raw API response before returning
        - Implement must_avoid post-filter
        - Fall back to offline dataset on API failure
        """
        log.info("scraper.search", category=category, price_min=price_min, price_max=price_max)

        # V1: use offline dataset only
        products = self._load_offline_dataset(category)

        # Basic price filter
        if price_max is not None:
            products = [p for p in products if p.price_inr is None or p.price_inr <= price_max]
        if price_min is not None:
            products = [p for p in products if p.price_inr is None or p.price_inr >= price_min]

        # must_avoid filter (simple substring match on title + specs)
        if must_avoid:
            filtered = []
            for p in products:
                text = (p.title + " " + " ".join(p.key_specs.values())).lower()
                if not any(term.lower() in text for term in must_avoid):
                    filtered.append(p)
            products = filtered

        return products[:max_results]

    def fetch_reviews(self, product_url: str, max_reviews: int = 20) -> list[str]:
        """
        Fetch raw review snippets for a product URL.

        TODO
        ----
        - Call ScrapingBee with the product URL (JS rendering enabled)
        - Extract review elements from the HTML
        - Return up to max_reviews text snippets
        """
        log.info("scraper.fetch_reviews", url=product_url)
        # TODO: implement ScrapingBee call
        return []

    def _load_offline_dataset(self, category: str) -> list[Product]:
        """
        Load products from the local JSON fallback dataset.

        Files: data/offline_dataset/{category}.json
        Each file is a JSON array of Product-compatible dicts.
        """
        file_path = Path(self._settings.offline_dataset_dir) / f"{category}.json"
        if not file_path.exists():
            log.warning("scraper.offline_dataset.missing", path=str(file_path))
            return []

        with file_path.open() as f:
            raw_data = json.load(f)

        products = []
        for item in raw_data:
            try:
                item.setdefault("source", "offline_dataset")
                products.append(Product(**item))
            except Exception as exc:
                log.warning("scraper.offline_dataset.parse_error", error=str(exc), item=item)

        log.info(
            "scraper.offline_dataset.loaded",
            category=category,
            num_products=len(products),
        )
        return products
