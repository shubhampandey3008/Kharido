"""
Node 3 — Product Search.

V1: fixed call to Apify Flipkart scrapers (or offline dataset fallback) with
    one relaxation retry when results are too few.
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
    2. Call ScraperClient (Apify Flipkart scraper or offline fallback).
    3. If result count < _MIN_CANDIDATES, relax price range and drop soft
       filters once, then retry.
    4. Filter out must_avoid violations.
    5. Return up to MAX_CANDIDATES products.

    Returns dict with key "candidates" (list[Product]).
    Sets "error" key when no candidates are found after retries.

    TODO
    ----
    - Implement relaxation: widen price_range by 20%, drop optional filters, retry once
    - Fetch reviews for top MAX_CANDIDATES via scraper.fetch_reviews(product_url)
    - V2: replace with agent loop using LLM to decide recovery action
    """
    settings = get_settings()
    parsed: ParsedQuery | None = state.get("parsed_query")

    if not parsed:
        return {"error": "product_search: no parsed_query in state", "candidates": []}

    log.info("product_search.start", category=parsed.category)

    # Calls Apify Flipkart Product Scraper; falls back to offline dataset when token is absent
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


if __name__ == "__main__":
    # Run this node in isolation:
    #   .venv/bin/python -m kharido.nodes.product_search "earbuds under 2000 for gym"
    import sys

    from kharido.config import configure_tracing
    from kharido.nodes.query_understanding import query_understanding_node

    configure_tracing()
    query = " ".join(sys.argv[1:]) or "earbuds under 2000 for gym"

    print(f"Query: {query}\n")
    state = query_understanding_node({"raw_query": query})
    print(f"Parsed: category={state['parsed_query'].category}, "
          f"price_max={state['parsed_query'].price_range.max_inr}\n")

    result = product_search_node(state)
    candidates = result.get("candidates", [])
    error = result.get("error")

    if error:
        print(f"Error: {error}")
    else:
        print(f"Found {len(candidates)} candidates:\n")
        for p in candidates:
            price_str = f"₹{p.price_inr:.0f}" if p.price_inr else "price N/A"
            rating_str = f"{p.rating:.1f}★ ({p.rating_count} reviews)" if p.rating else "no rating"
            print(f"  [{p.source}] {p.title}")
            print(f"    {price_str}  {rating_str}")
            print(f"    {p.product_url[:80]}")
            print()
