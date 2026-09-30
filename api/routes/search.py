"""
Search routes.

POST /search        — run the pipeline, return top recommendation + thread_id
GET  /search/{id}/alternative — resume from checkpoint, return backup pick
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from api.schemas import (
    AlternativeRequest,
    AlternativeResponse,
    ProductResponse,
    RecommendationResponse,
    SearchRequest,
    SearchResponse,
)
from kharido.config import configure_tracing
from kharido.graph import build_graph
from kharido.models import Recommendation

router = APIRouter(prefix="/search", tags=["search"])

configure_tracing()
_graph = build_graph()


def _to_recommendation_response(rec: Recommendation) -> RecommendationResponse:
    return RecommendationResponse(
        product=ProductResponse(
            product_id=rec.product.product_id,
            title=rec.product.title,
            brand=rec.product.brand,
            price_inr=rec.product.price_inr,
            rating=rec.product.rating,
            rating_count=rec.product.rating_count,
            image_url=rec.product.image_url,
            product_url=rec.product.product_url,
            key_specs=rec.product.key_specs,
        ),
        composite_score=rec.composite_score,
        reasoning=rec.reasoning,
        key_evidence=rec.key_evidence,
        criteria_scores=rec.criteria_scores,
    )


@router.post("", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """
    Run the full Kharido pipeline for a free-form shopping query.

    Returns the top recommendation and a thread_id for follow-up calls.

    The graph runs until the interrupt after the recommendation node,
    then returns the current state without continuing to accept/show_alternative.

    TODO
    ----
    - Load preference_profile from PreferenceMemoryService(user_id)
    - Pass it into the initial state
    - Stream node progress events via SSE (V2)
    """
    thread_id = f"api-{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = _graph.invoke(
            {"raw_query": request.query, "thread_id": thread_id},
            config=config,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    error = result.get("error")
    rec = result.get("recommendation")
    backup = result.get("backup")

    return SearchResponse(
        thread_id=thread_id,
        recommendation=_to_recommendation_response(rec) if rec else None,
        has_alternative=backup is not None,
        error=error,
    )


@router.get("/{thread_id}/alternative", response_model=AlternativeResponse)
async def get_alternative(thread_id: str) -> AlternativeResponse:
    """
    Resume a paused graph run and reveal the backup recommendation.

    Resumes from the LangGraph checkpoint stored under thread_id.

    TODO
    ----
    - Log rejection of current recommendation to PreferenceMemoryService
    - Resume with {"action": "show_alternative"} state update
    """
    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Resume from checkpoint — pass None as input (graph reads from saved state)
        result = _graph.invoke(None, config=config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    rec = result.get("recommendation")

    return AlternativeResponse(
        thread_id=thread_id,
        recommendation=_to_recommendation_response(rec) if rec else None,
        error=result.get("error"),
    )
