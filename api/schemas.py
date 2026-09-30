"""
Request / response Pydantic schemas for the FastAPI layer.

Separate from kharido/models.py which defines internal domain models.
These schemas are the API contract between the frontend and backend.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Free-form shopping query")
    user_id: str = Field("default", description="User identifier for preference memory")


class AlternativeRequest(BaseModel):
    thread_id: str = Field(..., description="Thread ID from the original search response")
    user_id: str = Field("default")


class PreferenceUpdateRequest(BaseModel):
    price_sensitivity: Optional[float] = Field(None, ge=0.0, le=1.0)
    liked_brands: Optional[list[str]] = None
    disliked_brands: Optional[list[str]] = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class ProductResponse(BaseModel):
    product_id: str
    title: str
    brand: str = ""
    price_inr: Optional[float] = None
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    image_url: str = ""
    product_url: str = ""
    key_specs: dict[str, str] = {}


class RecommendationResponse(BaseModel):
    product: ProductResponse
    composite_score: float
    reasoning: str
    key_evidence: list[str] = []
    criteria_scores: dict[str, float] = {}


class SearchResponse(BaseModel):
    thread_id: str
    recommendation: Optional[RecommendationResponse] = None
    has_alternative: bool = False
    error: Optional[str] = None


class AlternativeResponse(BaseModel):
    thread_id: str
    recommendation: Optional[RecommendationResponse] = None
    error: Optional[str] = None


class PreferenceResponse(BaseModel):
    user_id: str
    price_sensitivity: float
    liked_brands: list[str]
    disliked_brands: list[str]
    feature_priorities: dict[str, float]
    rating_risk_tolerance: float
    accept_count: int
    reject_count: int
