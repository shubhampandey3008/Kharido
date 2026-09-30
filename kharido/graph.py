"""
Kharido LangGraph pipeline.

Graph topology (V1 — sequential branches)
------------------------------------------

        [START]
           │
    query_understanding
           │
    criteria_research
           │
    product_search ──── (no candidates) ──► error_node ──► [END]
           │
    review_analysis_fanout     ← emits Send objects (one per candidate)
    review_analysis_worker     ← runs in parallel via Send API
    review_analysis_collect    ← fan-in aggregation
           │
    recommendation
           │ (interrupt here — waits for user response)
           │
    ┌──────┴───────┐
    │              │
  accept    show_alternative
    │              │
  [END]          [END]

V2 upgrade path
---------------
- Run criteria_research and product_search in parallel by adding two edges
  from query_understanding instead of chaining them sequentially.
- Add a join node that waits for both branches before continuing.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph as CompiledGraph

from kharido.nodes.criteria_research import criteria_research_node
from kharido.nodes.product_search import product_search_node
from kharido.nodes.query_understanding import query_understanding_node
from kharido.nodes.recommendation import recommendation_node
from kharido.nodes.review_analysis import (
    review_analysis_collect_node,
    review_analysis_fanout_node,
    review_analysis_worker_node,
)
from kharido.state import GraphState


# ---------------------------------------------------------------------------
# Conditional edge functions
# ---------------------------------------------------------------------------


def route_after_product_search(state: GraphState) -> str:
    if not state.get("candidates"):
        return "error_node"
    return "review_analysis_fanout"


def route_after_recommendation(state: GraphState) -> str:
    """
    Routes based on the user's response after the interrupt.

    The caller resumes the graph by passing {"action": "accept"} or
    {"action": "show_alternative"} in the state update.
    Defaults to "accept" when no action is set (e.g. direct API call).
    """
    # TODO: read from interrupt payload or state once human-in-the-loop is wired
    return "accept"


# ---------------------------------------------------------------------------
# Terminal / utility nodes
# ---------------------------------------------------------------------------


def accept_node(state: GraphState) -> dict:
    """User accepted the recommendation. Logs to PreferenceMemory."""
    # TODO: call preference_memory.record_accept(state["recommendation"].product.product_id)
    return {}


def show_alternative_node(state: GraphState) -> dict:
    """Promotes the backup to recommendation and logs the rejection."""
    # TODO: call preference_memory.record_reject(state["recommendation"].product.product_id)
    return {"recommendation": state.get("backup")}


def error_node(state: GraphState) -> dict:
    """Terminal node reached when a critical step fails."""
    return {"error": state.get("error", "An unexpected error occurred.")}


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph() -> CompiledGraph:
    """
    Construct, compile, and return the Kharido StateGraph.

    Uses MemorySaver for V1 development.
    Swap to SqliteSaver for persistence across process restarts:

        from langgraph.checkpoint.sqlite import SqliteSaver
        from kharido.config import get_settings
        checkpointer = SqliteSaver.from_conn_string(str(get_settings().db_path))
    """
    checkpointer = MemorySaver()

    builder = StateGraph(GraphState)

    # ── Register nodes ──────────────────────────────────────────────────────
    builder.add_node("query_understanding", query_understanding_node)
    builder.add_node("criteria_research", criteria_research_node)
    builder.add_node("product_search", product_search_node)
    builder.add_node("review_analysis_fanout", review_analysis_fanout_node)
    builder.add_node("review_analysis_worker", review_analysis_worker_node)
    builder.add_node("review_analysis_collect", review_analysis_collect_node)
    builder.add_node("recommendation", recommendation_node)
    builder.add_node("accept", accept_node)
    builder.add_node("show_alternative", show_alternative_node)
    builder.add_node("error_node", error_node)

    # ── Edges ────────────────────────────────────────────────────────────────
    builder.add_edge(START, "query_understanding")
    # V1: sequential — criteria first, then product search
    builder.add_edge("query_understanding", "criteria_research")
    builder.add_edge("criteria_research", "product_search")

    # Conditional: no candidates → error
    builder.add_conditional_edges(
        "product_search",
        route_after_product_search,
        {
            "error_node": "error_node",
            "review_analysis_fanout": "review_analysis_fanout",
        },
    )

    # Fan-out → workers → fan-in
    # review_analysis_fanout returns list[Send] which routes to review_analysis_worker
    builder.add_edge("review_analysis_fanout", "review_analysis_collect")
    builder.add_edge("review_analysis_collect", "recommendation")

    # Interrupt after recommendation; resume routes based on user action
    builder.add_conditional_edges(
        "recommendation",
        route_after_recommendation,
        {
            "accept": "accept",
            "show_alternative": "show_alternative",
        },
    )

    builder.add_edge("accept", END)
    builder.add_edge("show_alternative", END)
    builder.add_edge("error_node", END)

    return builder.compile(
        checkpointer=checkpointer,
        interrupt_after=["recommendation"],
    )
