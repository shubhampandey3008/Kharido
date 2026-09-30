"""
Tavily web-search client wrapper.

Used by the Criteria Research node to fetch expert buying guides and
category-level review pages for evidence-backed criteria extraction.
"""

from __future__ import annotations

import structlog

from kharido.config import get_settings

log = structlog.get_logger(__name__)


class TavilySearchClient:
    """
    Thin wrapper around the Tavily Python SDK.

    Used for:
    - Fetching expert buying criteria from specialist review sites and forums
    - Full-page text extraction via Tavily extract endpoint
    """

    def __init__(self) -> None:
        from tavily import TavilyClient

        settings = get_settings()
        self._client = TavilyClient(api_key=settings.tavily_api_key)

    def search(
        self,
        query: str,
        max_results: int = 5,
        include_raw_content: bool = False,
        search_depth: str = "advanced",
    ) -> list[dict]:
        """
        Run a Tavily search and return a list of result dicts.

        Each result dict contains: url, title, content, raw_content (optional).

        TODO
        ----
        - Implement: return self._client.search(query, max_results=max_results,
              search_depth=search_depth, include_raw_content=include_raw_content)["results"]
        - Add tenacity retry on TavilyError / rate-limit (max 3 attempts, 2s backoff)
        - Log query + result count to structlog
        """
        log.info("tavily.search", query=query, max_results=max_results)
        # TODO: implement
        return []

    def extract(self, urls: list[str]) -> list[dict]:
        """
        Extract clean page text from a list of URLs via Tavily extract.

        Returns list of dicts with "url" and "raw_content" keys.

        TODO
        ----
        - Implement: return self._client.extract(urls=urls)["results"]
        - Filter out empty or very short extracts (<200 chars)
        """
        log.info("tavily.extract", num_urls=len(urls))
        # TODO: implement
        return []
