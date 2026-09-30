"""
Node 3 — Product Search.

V1: fixed call to ScrapingBee (or offline dataset fallback) with one
    relaxation retry when results are too few.
V2: upgraded to a full agent loop that evaluates results and chooses
    recovery actions (relax price, drop soft filter, rephrase, switch source).
"""

from __future__ import annotations

import structlog

from kharido.config import get_settings
from kharido.models import ParsedQuery, Product
from kharido.state import GraphState

log = structlog.get_logger(__name__)

_MIN_CANDIDATES = 3


def product_search_node(state: GraphState) -> dict:
    """
    Fetch a candidate product list for the structured query.

    Flow
    ----
    1. Build search parameters from ParsedQuery.
    2. Call ScraperClient (ScrapingBee or offline fallback).
    3. If result count < _MIN_CANDIDATES, relax price range and drop soft
       filters once, then retry.
    4. Filter out must_avoid violations.
    5. Return up to MAX_CANDIDATES products.

    Returns dict with key "candidates" (list[Product]).
    Sets "error" key when no candidates are found after retries.

    TODO
    ----
    - Instantiate ScraperClient and call search_products(category, price_min, price_max, ...)
    - Implement must_avoid post-filter
    - Implement relaxation: widen price_range by 20%, drop optional filters, retry once
    - Fetch reviews for top MAX_CANDIDATES via scraper.fetch_reviews(product_url)
    - V2: replace with agent loop using LLM to decide recovery action
    """
    settings = get_settings()
    parsed: ParsedQuery | None = state.get("parsed_query")

    if not parsed:
        return {"error": "product_search: no parsed_query in state", "candidates": []}

    log.info("product_search.start", category=parsed.category)

    # TODO: call ScraperClient — for now load from offline dataset via ScraperClient
    from kharido.services.scraper import ScraperClient

    scraper = ScraperClient()
    candidates: list[Product] = scraper.search_products(
        category=parsed.category,
        price_min=parsed.price_range.min_inr,
        price_max=parsed.price_range.max_inr,
        must_avoid=parsed.must_avoid,
        max_results=settings.max_candidates,
    )

    if not candidates:
        log.warning("product_search.no_results", category=parsed.category)
        return {
            "candidates": [],
            "error": f"No products found for '{parsed.category}'. Try broadening your query.",
        }

    log.info("product_search.done", num_candidates=len(candidates))
    return {"candidates": candidates}
