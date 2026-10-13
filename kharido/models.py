"""
Domain models for Kharido.

All models use Pydantic v2. They serve as:
  1. Structured LLM output schemas (via .with_structured_output)
  2. GraphState field types
  3. Data transfer objects between services and the API layer
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EvidenceStatus(str, Enum):
    CONFIRMED = "confirmed"
    CONTRADICTED = "contradicted"
    NOT_MENTIONED = "not_mentioned"


# ---------------------------------------------------------------------------
# Step 1 — Query Understanding
# ---------------------------------------------------------------------------


class PriceRange(BaseModel):
    min_inr: Optional[float] = Field(None, description="Minimum price in INR")
    max_inr: Optional[float] = Field(None, description="Maximum price in INR")


class PriorityWeights(BaseModel):
    """Relative importance of each scoring dimension. Values should sum to ~1.0."""

    price: float = Field(0.25, ge=0.0, le=1.0)
    quality: float = Field(0.35, ge=0.0, le=1.0)
    features: float = Field(0.25, ge=0.0, le=1.0)
    brand_trust: float = Field(0.15, ge=0.0, le=1.0)


class ParsedQuery(BaseModel):
    """Structured representation of the user's free-form shopping request."""

    category: str = Field(
        ...,
        description="Normalised product category slug, e.g. 'running_shoes', 'earbuds'",
    )
    price_range: PriceRange = Field(default_factory=PriceRange)
    must_have: list[str] = Field(
        default_factory=list,
        description="Hard requirements, e.g. ['waterproof', 'size_uk_9']",
    )
    must_avoid: list[str] = Field(
        default_factory=list,
        description="Hard exclusions, e.g. ['white_color', 'brand_X']",
    )
    use_case_context: str = Field(
        "",
        description="Context that shapes criteria weights, e.g. 'rainy season commute'",
    )
    priority_weights: PriorityWeights = Field(default_factory=PriorityWeights)
    raw_query: str = Field("", description="Original user query, preserved for tracing")


# ---------------------------------------------------------------------------
# Step 2 — Criteria Research
# ---------------------------------------------------------------------------


class Criterion(BaseModel):
    """One checkable buying criterion for a product category."""

    name: str = Field(..., description="Short label, e.g. 'wet_grip'")
    description: str = Field(..., description="What this criterion measures")
    how_to_check: str = Field(
        ..., description="How to verify from a spec sheet or review text"
    )
    source_urls: list[str] = Field(default_factory=list)
    weight: float = Field(
        1.0,
        ge=0.0,
        le=3.0,
        description="Use-case-adjusted importance multiplier (1.0 = baseline)",
    )


class CategoryCriteria(BaseModel):
    """Full criteria set for one product category, as stored in the cache."""

    category: str
    criteria: list[Criterion] = Field(default_factory=list)
    use_case_context: str = ""
    cached_at: Optional[str] = None
    cache_expires_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Step 3 — Product Search
# ---------------------------------------------------------------------------


class Product(BaseModel):
    """Normalised product record returned by the Product Search agent."""

    product_id: str = Field(..., description="Unique ID (URL slug or scraper ID)")
    title: str
    brand: str = ""
    price_inr: Optional[float] = None
    rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    rating_count: Optional[int] = None
    key_specs: dict[str, str] = Field(
        default_factory=dict,
        description="Flat key-value spec sheet, e.g. {'sole': 'rubber', 'weight': '280g'}",
    )
    image_url: str = ""
    product_url: str = ""
    source: Literal["apify", "offline_dataset", "unknown"] = "unknown"
    raw_reviews: list[str] = Field(
        default_factory=list,
        description="Up to 20 raw review snippets",
    )


# ---------------------------------------------------------------------------
# Step 4 — Review Analysis
# ---------------------------------------------------------------------------


class CriterionEvidence(BaseModel):
    """Evidence for one criterion extracted from one product's reviews."""

    criterion_name: str
    status: EvidenceStatus = EvidenceStatus.NOT_MENTIONED
    supporting_quote: str = ""
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class CandidateEvidence(BaseModel):
    """Full evidence record for one product candidate."""

    product_id: str
    criterion_evidence: list[CriterionEvidence] = Field(default_factory=list)
    must_avoid_violations: list[str] = Field(
        default_factory=list,
        description="Any must_avoid attributes detected in this product",
    )
    composite_score: float = 0.0


# ---------------------------------------------------------------------------
# Step 5 — Recommendation
# ---------------------------------------------------------------------------


class Recommendation(BaseModel):
    """The app's final decisive recommendation for the user."""

    product: Product
    composite_score: float
    reasoning: str = Field(
        ...,
        description="LLM-generated plain-language justification citing review evidence",
    )
    key_evidence: list[str] = Field(
        default_factory=list,
        description="2–4 bullet-point evidence items shown in the UI",
    )
    criteria_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Per-criterion score breakdown for transparency",
    )


# ---------------------------------------------------------------------------
# Preference Memory
# ---------------------------------------------------------------------------


class PreferenceProfile(BaseModel):
    """User preference signals stored in and retrieved from Mem0."""

    user_id: str
    price_sensitivity: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="0 = price-insensitive, 1 = extremely price-sensitive",
    )
    liked_brands: list[str] = Field(default_factory=list)
    disliked_brands: list[str] = Field(default_factory=list)
    feature_priorities: dict[str, float] = Field(
        default_factory=dict,
        description="Feature → relative importance, e.g. {'battery_life': 0.8}",
    )
    rating_risk_tolerance: float = Field(
        0.3, ge=0.0, le=1.0, description="0 = only highly rated, 1 = ok with lower ratings"
    )
    delivery_sensitivity: float = Field(
        0.5, ge=0.0, le=1.0, description="0 = not important, 1 = same-day delivery priority"
    )
    accept_log: list[str] = Field(default_factory=list, description="Accepted product_ids")
    reject_log: list[str] = Field(default_factory=list, description="Rejected product_ids")
