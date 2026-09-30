"""
Node 5 — Recommendation.

Deterministic weighted scoring in Python + one LLM call for plain-language
reasoning. Picks the top product and holds a backup in reserve.
"""

from __future__ import annotations

import structlog

from kharido.models import (
    CandidateEvidence,
    CategoryCriteria,
    EvidenceStatus,
    ParsedQuery,
    Product,
    Recommendation,
)
from kharido.state import GraphState

log = structlog.get_logger(__name__)

_REASONING_PROMPT = """
You are a confident shopping advisor. Write 2–3 sentences recommending the
product below for the user's specific need. Be concrete, cite evidence from
buyer reviews, and avoid hedging.

User query: {raw_query}
Top product: {product_title}
Price: ₹{price}
Rating: {rating}/5 ({rating_count} reviews)
Key evidence from reviews:
{key_evidence}
"""

_EVIDENCE_SCORE = {
    EvidenceStatus.CONFIRMED: 1.0,
    EvidenceStatus.NOT_MENTIONED: 0.4,
    EvidenceStatus.CONTRADICTED: 0.0,
}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _score_candidate(
    product: Product,
    evidence: CandidateEvidence,
    criteria: CategoryCriteria | None,
    parsed_query: ParsedQuery | None,
) -> tuple[float, dict[str, float]]:
    """
    Compute a deterministic composite score for one candidate.

    Returns (composite_score, per_criterion_scores).

    Scoring formula (V1)
    --------------------
    criteria_score = Σ (criterion.weight × evidence_score) / Σ criterion.weight
    quality_factor = rating / 5.0  (or 0.6 default when rating missing)
    price_factor   = 1.0 if no price constraint, else 1 - (price / max_price)

    composite = 0.5 × criteria_score + 0.3 × quality_factor + 0.2 × price_factor

    TODO
    ----
    - Apply preference_profile weights from state (V2)
    - Penalise must_avoid violations (score → 0.0)
    - Weight price_factor by parsed_query.priority_weights.price
    """
    # Must-avoid violation → disqualify
    if evidence.must_avoid_violations:
        return 0.0, {}

    criterion_map = {c.name: c for c in (criteria.criteria if criteria else [])}
    ev_map = {e.criterion_name: e for e in evidence.criterion_evidence}

    weighted_sum = 0.0
    weight_total = 0.0
    per_criterion: dict[str, float] = {}

    for name, criterion in criterion_map.items():
        ev = ev_map.get(name)
        score = _EVIDENCE_SCORE.get(ev.status, 0.4) if ev else 0.4
        per_criterion[name] = score
        weighted_sum += criterion.weight * score
        weight_total += criterion.weight

    criteria_score = (weighted_sum / weight_total) if weight_total > 0 else 0.5

    quality_factor = (product.rating / 5.0) if product.rating else 0.6

    price_factor = 1.0
    if parsed_query and parsed_query.price_range.max_inr and product.price_inr:
        ratio = product.price_inr / parsed_query.price_range.max_inr
        price_factor = max(0.0, 1.0 - ratio)

    composite = 0.5 * criteria_score + 0.3 * quality_factor + 0.2 * price_factor
    return round(composite, 4), per_criterion


def _score_all(state: GraphState) -> list[tuple[Product, CandidateEvidence, float, dict]]:
    """Return (product, evidence, score, per_criterion_scores) sorted descending."""
    candidates: list[Product] = state.get("candidates", [])
    evidence_list: list[CandidateEvidence] = state.get("evidence", [])
    criteria: CategoryCriteria | None = state.get("criteria")
    parsed: ParsedQuery | None = state.get("parsed_query")

    ev_by_id = {e.product_id: e for e in evidence_list}
    results = []

    for product in candidates:
        ev = ev_by_id.get(product.product_id, CandidateEvidence(product_id=product.product_id))
        score, per_criterion = _score_candidate(product, ev, criteria, parsed)
        results.append((product, ev, score, per_criterion))

    return sorted(results, key=lambda x: x[2], reverse=True)


# ---------------------------------------------------------------------------
# LLM reasoning
# ---------------------------------------------------------------------------


def _generate_reasoning(product: Product, key_evidence: list[str], raw_query: str) -> str:
    """
    Call the reasoning LLM to write plain-language justification.

    TODO
    ----
    - Build ChatPromptTemplate from _REASONING_PROMPT
    - Call ChatAnthropic with reasoning_model
    - Return the string content
    """
    # TODO: replace with real LLM call
    return (
        f"[STUB] {product.title} is the top pick for your query '{raw_query}'. "
        "Full reasoning will be generated once the LLM call is implemented."
    )


# ---------------------------------------------------------------------------
# Node entry point
# ---------------------------------------------------------------------------


def recommendation_node(state: GraphState) -> dict:
    """
    Score all candidates and select the top pick + backup.

    Returns dict with keys "recommendation" and "backup".

    TODO
    ----
    - Wire _generate_reasoning to real LLM call
    - Read preference_profile weights from state (V2)
    - Expose key_evidence bullets to the LLM reasoning prompt
    """
    log.info("recommendation.start")

    scored = _score_all(state)

    if not scored:
        log.warning("recommendation.no_scoreable_candidates")
        return {"error": "No scoreable candidates available.", "recommendation": None, "backup": None}

    top_product, _top_ev, top_score, top_per_criterion = scored[0]
    raw_query = state.get("raw_query", "")

    reasoning = _generate_reasoning(top_product, [], raw_query)

    recommendation = Recommendation(
        product=top_product,
        composite_score=top_score,
        reasoning=reasoning,
        key_evidence=[],
        criteria_scores=top_per_criterion,
    )

    backup: Recommendation | None = None
    if len(scored) >= 2:
        backup_product, _bev, backup_score, backup_per_criterion = scored[1]
        backup = Recommendation(
            product=backup_product,
            composite_score=backup_score,
            reasoning=f"[STUB] {backup_product.title} is the alternative pick.",
            criteria_scores=backup_per_criterion,
        )

    log.info(
        "recommendation.done",
        top_product=top_product.title,
        top_score=top_score,
        has_backup=backup is not None,
    )
    return {"recommendation": recommendation, "backup": backup}
