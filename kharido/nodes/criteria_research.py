"""
Node 2 — Criteria Research.

V1: single web-search + one LLM call returning 5–8 checkable criteria.
V2: upgraded to a full agent loop (multi-source, two-independent-source rule,
    category-wide review mining).

Results are cached per normalised category in SQLite via CriteriaCache.
"""

from __future__ import annotations

import structlog

from kharido.models import CategoryCriteria, Criterion
from kharido.state import GraphState

log = structlog.get_logger(__name__)

_CRITERIA_EXTRACTION_PROMPT = """
You are a product research expert. Based on the web search results below,
extract {min_criteria}–{max_criteria} buying criteria for the product category
"{category}" with use-case context: "{use_case}".

For each criterion include:
- name: short snake_case label
- description: what it measures
- how_to_check: how to verify from spec sheet or review text
- weight: importance multiplier adjusted for the use-case (1.0 = baseline)

Focus on criteria that are checkable from specs or review evidence.
Only include criteria confirmed by at least one of the sources below.

Sources:
{search_results}
"""


def _build_extraction_chain():
    """Build the structured-output chain for criteria extraction."""
    from langchain_anthropic import ChatAnthropic
    from langchain_core.prompts import ChatPromptTemplate

    from kharido.config import get_settings

    settings = get_settings()
    llm = ChatAnthropic(
        model=settings.reasoning_model,
        anthropic_api_key=settings.anthropic_api_key,
    )
    prompt = ChatPromptTemplate.from_messages(
        [("human", _CRITERIA_EXTRACTION_PROMPT)]
    )
    return prompt | llm.with_structured_output(CategoryCriteria)


def criteria_research_node(state: GraphState) -> dict:
    """
    Return evidence-backed buying criteria for the query's product category.

    Flow
    ----
    1. Normalise the category name.
    2. Check the SQLite criteria cache (CriteriaCache).
    3. Cache hit  → adjust weights for the use-case context, return.
    4. Cache miss → search expert sources via Tavily, extract criteria via LLM,
       cache the result, return.

    Returns dict with key "criteria" containing a CategoryCriteria instance.

    TODO
    ----
    - Instantiate CriteriaCache and call cache.get(category)
    - On cache miss, call TavilySearchClient.search(f"best {category} buying guide criteria")
    - Call _build_extraction_chain().invoke({...}) with search results
    - Call cache.set(category, criteria) after extraction
    - Adjust criterion weights based on use_case_context
    - V2: loop search until ≥2 independent sources confirm each criterion
    """
    parsed = state.get("parsed_query")
    category = parsed.category if parsed else "unknown"
    use_case = parsed.use_case_context if parsed else ""

    log.info("criteria_research.start", category=category, use_case=use_case)

    # TODO: check CriteriaCache, call TavilySearchClient, call LLM
    stub_criteria = CategoryCriteria(
        category=category,
        use_case_context=use_case,
        criteria=[
            Criterion(
                name="stub_criterion",
                description="Placeholder — criteria research not yet implemented",
                how_to_check="N/A",
                weight=1.0,
            )
        ],
    )

    log.info("criteria_research.done", num_criteria=len(stub_criteria.criteria))
    return {"criteria": stub_criteria}
