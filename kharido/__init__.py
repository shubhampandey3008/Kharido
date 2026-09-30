"""
Kharido — agentic shopping assistant.

Given a free-form natural-language query this package returns one decisive
top-product recommendation with evidence-backed reasoning.

Package layout
--------------
kharido/
    config.py            — environment / constants
    state.py             — LangGraph GraphState TypedDict
    models.py            — all Pydantic domain models
    graph.py             — assembles the LangGraph StateGraph
    nodes/               — one module per pipeline step
    services/            — external clients (scraper, search, cache, memory)
"""

__version__ = "0.1.0"
