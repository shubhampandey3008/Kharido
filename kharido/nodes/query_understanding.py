"""
Node 1 — Query Understanding.

Converts the user's free-form query into a validated ParsedQuery via a single
structured-output LLM call. No tools, no loop — pure workflow node.
"""

from __future__ import annotations

import structlog

from kharido.models import ParsedQuery
from kharido.state import GraphState

log = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """
You are a shopping query parser. Extract structured filters from the user's
free-form shopping description. Be conservative: only mark something as
must_avoid if the user explicitly excludes it. Infer priority_weights from
context clues (e.g. "under 2000" implies high price sensitivity).
Output a normalised category slug (snake_case, e.g. running_shoes, earbuds).
"""

_HUMAN_PROMPT = "User query: {raw_query}"


def _build_chain():
    """Build the structured-output chain. Imported lazily to avoid startup cost."""
    from langchain_anthropic import ChatAnthropic
    from langchain_core.prompts import ChatPromptTemplate

    from kharido.config import get_settings

    settings = get_settings()
    llm = ChatAnthropic(
        model=settings.reasoning_model,
        anthropic_api_key=settings.anthropic_api_key,
    )
    prompt = ChatPromptTemplate.from_messages(
        [("system", _SYSTEM_PROMPT), ("human", _HUMAN_PROMPT)]
    )
    return prompt | llm.with_structured_output(ParsedQuery)


def query_understanding_node(state: GraphState) -> dict:
    """
    Parse the raw user query into a structured ParsedQuery.

    Returns dict with key "parsed_query".

    TODO
    ----
    - Add one retry with a correction prompt if validation fails
    - Log token usage to LangSmith / structlog
    """
    raw_query = state["raw_query"]
    log.info("query_understanding.start", raw_query=raw_query)

    chain = _build_chain()
    parsed: ParsedQuery = chain.invoke({"raw_query": raw_query})
    # Don't trust the LLM to echo the query verbatim
    parsed = parsed.model_copy(update={"raw_query": raw_query})

    log.info("query_understanding.done", category=parsed.category)
    return {"parsed_query": parsed}


if __name__ == "__main__":
    # Run this node in isolation:
    #   .venv/bin/python -m kharido.nodes.query_understanding "earbuds under 2000 for gym"
    import sys

    from kharido.config import configure_tracing

    configure_tracing()
    query = " ".join(sys.argv[1:]) or "running shoes for rainy season, not white, under 5000 rupees"
    result = query_understanding_node({"raw_query": query})
    print(result["parsed_query"].model_dump_json(indent=2))
