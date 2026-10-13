"""
Apify product and review scraper client.

Provides a unified interface that tries Apify (Flipkart + Amazon scrapers)
first, then falls back to the offline JSON dataset when the API token is absent
or the call fails.  Results from both sources are merged and deduplicated before
price/must_avoid filters are applied.

Actors used
-----------
- Product search (Flipkart) : shahidirfan/flipkart-product-scraper  (TBFjma2NhVb30QONt)
- Review fetch   (Flipkart) : shahidirfan/flipkart-reviews-scraper  (MgqDrxBkXJGDF4P7I)
- Product search (Amazon)   : automly/amazon-scraper                (se6u51NCji6y89vBS)
- Review fetch   (Amazon)   : delicious_zebu/amazon-reviews-scraper (8vhDnIX6dStLlGVr7)

API pattern
-----------
POST https://api.apify.com/v2/acts/{actorId}/run-sync-get-dataset-items
  Authorization: Bearer <APIFY_API_TOKEN>
  Content-Type: application/json

  {input_body}

The sync endpoint blocks (up to 300 s) and returns dataset items as a JSON
array — no polling required.

Input schema — Flipkart product actor (TBFjma2NhVb30QONt)
----------------------------------------------------------
keyword            str    Search term (use this OR startUrl, not both)
startUrl           str    Flipkart category/search URL (alternative to keyword)
sort               str    relevance | popularity | price_asc | price_desc | newest
results_wanted     int    Max products to extract (default 20)
proxyConfiguration obj    Default: Apify RESIDENTIAL proxy

Output fields — Flipkart product actor
---------------------------------------
id, item_id, listing_id    str | null
title, brand, category     str | null
price                      number | null  — INR
original_price             number | null
discount_percent           number | null
rating                     number | null  — out of 5
rating_count, review_count number | null
specifications, key_specs  object/array | null
image_url, url             str | null

Input schema — Flipkart reviews actor (MgqDrxBkXJGDF4P7I)
----------------------------------------------------------
startUrl           str    Flipkart product or product-review URL
startUrls          list   Alternative: list of URLs for a batch run
results_wanted     int    Max reviews per product (default 20)
max_pages          int    Safety cap for pagination (default 200)
proxyConfiguration obj    Default: Apify RESIDENTIAL proxy

Output fields — Flipkart reviews actor
---------------------------------------
product_name, product_id, listing_id  str | null
review_id, rating, title, review_text str/number | null
author, date, verified_purchase        str/bool | null
helpful_count, unhelpful_count         number | null

Input schema — Amazon product actor (se6u51NCji6y89vBS)
---------------------------------------------------------
keywords     array   Search terms, e.g. ["office chair"] (required)
marketplace  str     Amazon TLD — "in" for amazon.in, "com" for amazon.com, etc.
maxItems     int     Max products to extract

Output fields — Amazon product actor
-------------------------------------
asin, url, title, brand              str | null
price                                str | null  — INR string e.g. "₹3,899" or "1 option from ₹3,899.00"
list_price                           str | null
discount_percent                     number | null
rating                               number | null  — out of 5
review_count                         number | null
specs                                object | null  — flat dict of spec key-value pairs
features                             list[str] | null
images                               list[str] | null  — image URLs
availability                         str | null

Input schema — Amazon reviews actor (8vhDnIX6dStLlGVr7)
---------------------------------------------------------
ASIN_or_URL                array   Product ASINs or URLs (required)
country                    str     Marketplace country (default "United States"); use "India" for INR
max_reviews                int     Per-ASIN limit (0 = up to 10,000; default 15)
sort_reviews_by            array   "Top reviews" | "Most recent"
filter_by_ratings          array   "all" | "five_star" ... "one_star" | "positive" | "critical"
filter_by_verified_purchase_only  array  "both" | "verified" | "not_verified"
get_customers_say          bool    Include AI-generated aspect summary (default true)

Output fields — Amazon reviews actor
--------------------------------------
ASIN, ProductTitle, AverageRating, TotalRatings  str/number | null
ReviewId, ReviewTitle, ReviewContent             str | null
ReviewScore, ReviewDate, ReviewCountry           number/str | null
HelpfulVotes, HelpfulCounts                      number/str | null
Verified                                         bool | null
Images, Videos                                   list | null
CustomersSay, ReviewAspects                      str/list | null
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import httpx
import structlog

from kharido.config import get_settings
from kharido.models import Product

log = structlog.get_logger(__name__)

_FK_PRODUCT_ACTOR = "TBFjma2NhVb30QONt"  # shahidirfan/flipkart-product-scraper
_FK_REVIEWS_ACTOR = "MgqDrxBkXJGDF4P7I"  # shahidirfan/flipkart-reviews-scraper
_AMZ_PRODUCT_ACTOR = "se6u51NCji6y89vBS"  # automly/amazon-scraper
_AMZ_REVIEWS_ACTOR = "8vhDnIX6dStLlGVr7"  # delicious_zebu/amazon-reviews-scraper

_APIFY_SYNC_URL = (
    "https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
)
_REQUEST_TIMEOUT = 120.0


class ScraperClient:
    """
    Normalised product-search client backed by Apify (Flipkart + Amazon).

    Search flow
    -----------
    1. If apify_api_token is set: call both Flipkart and Amazon product actors
       in sequence, merge and deduplicate results by product_url.
    2. On API failure or combined empty result: fall back to offline dataset.
    3. Apply price and must_have/must_avoid post-filters.
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
        """Search Flipkart + Amazon for products matching the given filters."""
        log.info("scraper.search", category=category, price_min=price_min, price_max=price_max)

        keyword = category.replace("_", " ")
        if must_have:
            keyword = f"{keyword} {' '.join(must_have)}"

        if self._settings.apify_api_token:
            fk = self._call_flipkart_products(keyword, max_results)
            amz = self._call_amazon_products(keyword, max_results)
            products = _merge_products(fk, amz)
        else:
            products = []

        if not products:
            log.info("scraper.offline_fallback", category=category)
            products = self._load_offline_dataset(category)

        # Price filter — only applied when price_inr is known
        if price_max is not None:
            products = [p for p in products if p.price_inr is None or p.price_inr <= price_max]
        if price_min is not None:
            products = [p for p in products if p.price_inr is None or p.price_inr >= price_min]

        # must_avoid filter (substring match on title + specs)
        if must_avoid:
            filtered = []
            for p in products:
                text = (p.title + " " + " ".join(p.key_specs.values())).lower()
                if not any(term.lower() in text for term in must_avoid):
                    filtered.append(p)
            products = filtered

        return products[:max_results]

    # ------------------------------------------------------------------
    # Flipkart
    # ------------------------------------------------------------------

    def _call_flipkart_products(self, keyword: str, max_results: int) -> list[Product]:
        """
        Run Flipkart Product Scraper and normalise results.

        Actor: shahidirfan/flipkart-product-scraper (TBFjma2NhVb30QONt)
        """
        log.info("scraper.flipkart.products.request", keyword=keyword)
        raw_items = self._apify_run(
            _FK_PRODUCT_ACTOR,
            {"keyword": keyword, "results_wanted": max_results},
        )
        if raw_items is None:
            return []

        products: list[Product] = []
        for item in raw_items:
            price = item.get("price")
            price_inr = float(price) if price is not None else None

            rating = _safe_float(item.get("rating"), max_val=5.0)
            rating_count = item.get("rating_count") or item.get("review_count")

            key_specs = _parse_specs(item.get("specifications") or item.get("key_specs"))

            product_url = item.get("url", "")
            product_id = (
                item.get("id") or item.get("item_id") or product_url or f"fk-{len(products)}"
            )

            products.append(
                Product(
                    product_id=str(product_id),
                    title=item.get("title", "Unknown"),
                    brand=item.get("brand", ""),
                    price_inr=price_inr,
                    rating=rating,
                    rating_count=int(rating_count) if rating_count is not None else None,
                    key_specs=key_specs,
                    image_url=item.get("image_url", ""),
                    product_url=product_url,
                    source="apify",
                )
            )

        log.info("scraper.flipkart.products.done", count=len(products))
        return products

    def _call_flipkart_reviews(self, product_url: str, max_reviews: int) -> list[str]:
        """
        Run Flipkart Reviews Scraper for one product URL.

        Actor: shahidirfan/flipkart-reviews-scraper (MgqDrxBkXJGDF4P7I)
        Input : {"startUrl": product_url, "results_wanted": max_reviews}
        Output: review_text strings.
        """
        log.info("scraper.flipkart.reviews.request", url=product_url)
        raw_items = self._apify_run(
            _FK_REVIEWS_ACTOR,
            {"startUrl": product_url, "results_wanted": max_reviews},
        )
        if raw_items is None:
            return []

        reviews = [
            item["review_text"].strip()
            for item in raw_items
            if item.get("review_text")
        ]
        log.info("scraper.flipkart.reviews.done", count=len(reviews))
        return reviews[:max_reviews]

    # ------------------------------------------------------------------
    # Amazon
    # ------------------------------------------------------------------

    def _call_amazon_products(self, keyword: str, max_results: int) -> list[Product]:
        """
        Run automly/amazon-scraper and normalise results.

        Actor: automly/amazon-scraper (se6u51NCji6y89vBS)
        Input : {"keywords": [keyword], "marketplace": "in", "maxItems": N}
        price field is an INR string e.g. "₹3,899" or "1 option from ₹3,899.00".
        """
        log.info("scraper.amazon.products.request", keyword=keyword)
        raw_items = self._apify_run(
            _AMZ_PRODUCT_ACTOR,
            {
                "keywords": [keyword],
                "marketplace": "in",
                "maxItems": max_results,
            },
        )
        if raw_items is None:
            return []

        products: list[Product] = []
        for item in raw_items:
            if not item.get("title"):
                continue

            price_inr = _parse_inr_price(item.get("price"))

            rating = _safe_float(item.get("rating"), max_val=5.0)
            rating_count = item.get("review_count")

            # specs is a flat dict; features is a list of strings
            key_specs = _parse_specs(item.get("specs"))
            for i, feat in enumerate(item.get("features") or []):
                if feat:
                    key_specs[f"feature_{i + 1}"] = str(feat)

            images = item.get("images") or []
            image_url = images[0] if images else ""

            product_url = item.get("url", "")
            product_id = item.get("asin") or product_url or f"amz-{len(products)}"

            products.append(
                Product(
                    product_id=str(product_id),
                    title=item.get("title", "Unknown"),
                    brand=item.get("brand", ""),
                    price_inr=price_inr,
                    rating=rating,
                    rating_count=int(rating_count) if rating_count is not None else None,
                    key_specs=key_specs,
                    image_url=image_url,
                    product_url=product_url,
                    source="apify",
                )
            )

        log.info("scraper.amazon.products.done", count=len(products))
        return products

    def _call_amazon_reviews(self, product_url: str, max_reviews: int) -> list[str]:
        """
        Run Amazon Reviews Scraper for one product URL.

        Actor: delicious_zebu/amazon-reviews-scraper (8vhDnIX6dStLlGVr7)
        Input : {"ASIN_or_URL": [product_url], "country": "India", "max_reviews": N}
        Output: ReviewContent strings.
        """
        log.info("scraper.amazon.reviews.request", url=product_url)
        raw_items = self._apify_run(
            _AMZ_REVIEWS_ACTOR,
            {
                "ASIN_or_URL": [product_url],
                "country": "India",
                "max_reviews": max_reviews,
            },
        )
        if raw_items is None:
            return []

        reviews = [
            item["ReviewContent"].strip()
            for item in raw_items
            if item.get("ReviewContent")
        ]
        log.info("scraper.amazon.reviews.done", count=len(reviews))
        return reviews[:max_reviews]

    # ------------------------------------------------------------------
    # Public review entry point — routes by URL domain
    # ------------------------------------------------------------------

    def fetch_reviews(self, product_url: str, max_reviews: int = 20) -> list[str]:
        """
        Fetch raw review snippets for a product URL.

        Routes to the Flipkart or Amazon reviews actor based on the URL domain.
        Returns up to max_reviews text strings.
        """
        if not self._settings.apify_api_token:
            log.info("scraper.fetch_reviews.skipped", reason="no apify token")
            return []

        if "amazon." in product_url:
            return self._call_amazon_reviews(product_url, max_reviews)
        return self._call_flipkart_reviews(product_url, max_reviews)

    # ------------------------------------------------------------------
    # Shared Apify helper
    # ------------------------------------------------------------------

    def _apify_run(self, actor_id: str, payload: dict) -> list[dict] | None:
        """POST to run-sync-get-dataset-items; returns items list or None on error."""
        url = _APIFY_SYNC_URL.format(actor_id=actor_id)
        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._settings.apify_api_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=_REQUEST_TIMEOUT,
            )
        except Exception as exc:
            log.warning("scraper.apify.exception", actor=actor_id, error=str(exc))
            return None

        if response.status_code not in (200, 201):
            log.warning(
                "scraper.apify.error",
                actor=actor_id,
                status=response.status_code,
                body=response.text[:200],
            )
            return None

        return response.json()

    # ------------------------------------------------------------------
    # Offline fallback
    # ------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_inr_price(price_str: object) -> Optional[float]:
    """Extract a float from INR price strings like '₹3,899', '1 option from ₹3,899.00'."""
    if not price_str or not isinstance(price_str, str):
        return None
    match = re.search(r"₹([\d,]+(?:\.\d+)?)", price_str)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _safe_float(value: object, max_val: float = 5.0) -> Optional[float]:
    if value is None:
        return None
    try:
        return min(float(value), max_val)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


def _parse_specs(specs: object) -> dict[str, str]:
    """Normalise Flipkart spec fields (dict or list of {key, value}) to a flat dict."""
    if isinstance(specs, dict):
        return {k: str(v) for k, v in specs.items() if v is not None}
    if isinstance(specs, list):
        result: dict[str, str] = {}
        for spec in specs:
            if isinstance(spec, dict):
                k = str(spec.get("key") or spec.get("name", ""))
                v = str(spec.get("value", ""))
                if k:
                    result[k] = v
        return result
    return {}


def _merge_products(fk: list[Product], amz: list[Product]) -> list[Product]:
    """Round-robin interleave Flipkart and Amazon results, deduplicate by product_url."""
    from itertools import zip_longest

    seen: set[str] = set()
    merged: list[Product] = []
    for fk_p, amz_p in zip_longest(fk, amz):
        for p in (fk_p, amz_p):
            if p is None:
                continue
            key = p.product_url or p.product_id
            if key and key not in seen:
                seen.add(key)
                merged.append(p)
    return merged
