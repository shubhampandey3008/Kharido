"""
Node 4 — Review Analysis.

Uses the LangGraph Send API for fan-out: one parallel sub-task per candidate.

Fan-out architecture
--------------------
review_analysis_fanout_node
    Reads state["candidates"] and state["criteria"].
    Returns list[Send], each routing to "review_analysis_worker".
    LangGraph executes all workers in parallel.

review_analysis_worker_node
    Receives {"product": Product, "criteria": CategoryCriteria}.
    Runs structured extraction over the candidate's reviews.
    Returns {"evidence": [CandidateEvidence]} — accumulated via operator.add reducer.

review_analysis_collect_node
    Fan-in: evidence list is already accumulated in state["evidence"] by
    the reducer. This node validates and logs the collected results.

Send API note
-------------
The worker node signature differs from standard nodes — it receives a plain
dict (the Send payload), not the full GraphState. Register it with add_node
as usual; LangGraph handles the routing.
"""

from __future__ import annotations

import structlog
from langgraph.types import Send

from kharido.models import (
    CandidateEvidence,
    CategoryCriteria,
    CriterionEvidence,
    EvidenceStatus,
    Product,
)
from kharido.state import GraphState

log = structlog.get_logger(__name__)

_EXTRACTION_PROMPT = """
You are a product review analyst. For each criterion below, determine whether
the product reviews CONFIRM it, CONTRADICT it, or do NOT MENTION it.

Product: {product_title}
Reviews:
{reviews}

Criteria to evaluate:
{criteria_list}

For each criterion return:
- criterion_name: exact name from the list
- status: confirmed | contradicted | not_mentioned
- supporting_quote: short direct quote from a review (empty if not_mentioned)
- confidence: 0.0 to 1.0
"""


def _build_extraction_chain():
    """Build the structured-output chain for review extraction."""
    from langchain_anthropic import ChatAnthropic
    from langchain_core.prompts import ChatPromptTemplate

    from kharido.config import get_settings
    from kharido.models import CandidateEvidence

    settings = get_settings()
    llm = ChatAnthropic(
        model=settings.extraction_model,
        anthropic_api_key=settings.anthropic_api_key,
    )
    prompt = ChatPromptTemplate.from_messages([("human", _EXTRACTION_PROMPT)])
    return prompt | llm.with_structured_output(CandidateEvidence)


# ---------------------------------------------------------------------------
# Fan-out node
# ---------------------------------------------------------------------------


def review_analysis_fanout_node(state: GraphState) -> list[Send]:
    """
    Emit one Send per candidate to the review_analysis_worker node.

    LangGraph executes all Sends in parallel. Each worker's return value
    is merged into state["evidence"] via the operator.add reducer.
    """
    candidates: list[Product] = state.get("candidates", [])
    criteria: CategoryCriteria | None = state.get("criteria")

    log.info("review_analysis.fanout", num_candidates=len(candidates))

    return [
        Send(
            "review_analysis_worker",
            {"product": candidate, "criteria": criteria},
        )
        for candidate in candidates
    ]


# ---------------------------------------------------------------------------
# Worker node (invoked via Send, not directly as a graph node entry)
# ---------------------------------------------------------------------------


def review_analysis_worker_node(payload: dict) -> dict:
    """
    Extract per-criterion evidence for one candidate product.

    Receives payload dict with keys "product" and "criteria".
    Returns {"evidence": [CandidateEvidence]} to be accumulated by the reducer.

    TODO
    ----
    - Call _build_extraction_chain().invoke({...}) with product reviews + criteria
    - Handle empty reviews gracefully (return all NOT_MENTIONED)
    - Use extraction_model (fast/cheap) for classification
    """
    product: Product = payload["product"]
    criteria: CategoryCriteria | None = payload.get("criteria")

    log.info("review_analysis.worker", product_id=product.product_id)

    # TODO: call LLM extraction chain with product.raw_reviews + criteria
    stub_evidence = CandidateEvidence(
        product_id=product.product_id,
        criterion_evidence=[
            CriterionEvidence(
                criterion_name=c.name,
                status=EvidenceStatus.NOT_MENTIONED,
                supporting_quote="",
                confidence=0.0,
            )
            for c in (criteria.criteria if criteria else [])
        ],
    )

    # Return as list so operator.add reducer accumulates across workers
    return {"evidence": [stub_evidence]}


# ---------------------------------------------------------------------------
# Fan-in / collect node
# ---------------------------------------------------------------------------


def review_analysis_collect_node(state: GraphState) -> dict:
    """
    Validate and log the accumulated evidence list after all workers finish.

    The operator.add reducer on state["evidence"] already collected all
    CandidateEvidence objects — this node just confirms the count and logs.
    """
    evidence: list[CandidateEvidence] = state.get("evidence", [])
    log.info("review_analysis.collect", num_evidence_records=len(evidence))
    return {}
