"""Basic Pydantic model instantiation and validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kharido.models import (
    CandidateEvidence,
    CategoryCriteria,
    CriterionEvidence,
    EvidenceStatus,
    ParsedQuery,
    PreferenceProfile,
    PriceRange,
    PriorityWeights,
    Product,
    Recommendation,
)


class TestParsedQuery:
    def test_minimal(self):
        q = ParsedQuery(category="running_shoes")
        assert q.category == "running_shoes"
        assert q.must_have == []
        assert q.must_avoid == []
        assert q.use_case_context == ""

    def test_full(self):
        q = ParsedQuery(
            category="earbuds",
            price_range=PriceRange(min_inr=1000, max_inr=5000),
            must_have=["noise_cancellation"],
            must_avoid=["white"],
            use_case_context="office commute",
            priority_weights=PriorityWeights(price=0.4, quality=0.4, features=0.1, brand_trust=0.1),
            raw_query="earbuds with anc under 5000",
        )
        assert q.price_range.max_inr == 5000
        assert "noise_cancellation" in q.must_have

    def test_category_required(self):
        with pytest.raises(ValidationError):
            ParsedQuery()


class TestProduct:
    def test_defaults(self):
        p = Product(product_id="test-001", title="Test Product")
        assert p.brand == ""
        assert p.price_inr is None
        assert p.key_specs == {}
        assert p.raw_reviews == []
        assert p.source == "unknown"

    def test_rating_bounds(self):
        with pytest.raises(ValidationError):
            Product(product_id="x", title="x", rating=6.0)

    def test_full(self):
        p = Product(
            product_id="rs-001",
            title="Adidas Duramo",
            brand="Adidas",
            price_inr=3999.0,
            rating=4.3,
            rating_count=2840,
            key_specs={"sole": "rubber"},
            product_url="https://example.com",
            source="offline_dataset",
            raw_reviews=["Great grip on wet roads."],
        )
        assert p.price_inr == 3999.0
        assert p.source == "offline_dataset"


class TestCriterionEvidence:
    def test_default_status(self):
        ev = CriterionEvidence(criterion_name="wet_grip")
        assert ev.status == EvidenceStatus.NOT_MENTIONED
        assert ev.confidence == 0.0

    def test_confirmed(self):
        ev = CriterionEvidence(
            criterion_name="wet_grip",
            status=EvidenceStatus.CONFIRMED,
            supporting_quote="Great grip on wet roads.",
            confidence=0.9,
        )
        assert ev.status.value == "confirmed"


class TestCandidateEvidence:
    def test_defaults(self):
        ev = CandidateEvidence(product_id="rs-001")
        assert ev.criterion_evidence == []
        assert ev.must_avoid_violations == []
        assert ev.composite_score == 0.0


class TestRecommendation:
    def test_construction(self):
        product = Product(product_id="rs-001", title="Test Shoe")
        rec = Recommendation(
            product=product,
            composite_score=0.78,
            reasoning="This is a great shoe because...",
        )
        assert rec.composite_score == 0.78
        assert rec.key_evidence == []


class TestPreferenceProfile:
    def test_cold_start_defaults(self):
        profile = PreferenceProfile(user_id="user-123")
        assert profile.price_sensitivity == 0.5
        assert profile.liked_brands == []
        assert profile.accept_log == []

    def test_sensitivity_bounds(self):
        with pytest.raises(ValidationError):
            PreferenceProfile(user_id="x", price_sensitivity=1.5)


class TestEvidenceStatus:
    def test_enum_values(self):
        assert EvidenceStatus.CONFIRMED.value == "confirmed"
        assert EvidenceStatus.CONTRADICTED.value == "contradicted"
        assert EvidenceStatus.NOT_MENTIONED.value == "not_mentioned"
