"""
Preferences routes.

GET   /preferences/{user_id}  — load preference profile
PATCH /preferences/{user_id}  — update preference fields
"""

from __future__ import annotations

from fastapi import APIRouter

from api.schemas import PreferenceResponse, PreferenceUpdateRequest
from kharido.services.preference_memory import PreferenceMemoryService

router = APIRouter(prefix="/preferences", tags=["preferences"])

_memory = PreferenceMemoryService()


@router.get("/{user_id}", response_model=PreferenceResponse)
async def get_preferences(user_id: str) -> PreferenceResponse:
    """Return the stored preference profile for a user (cold-start defaults in V1)."""
    profile = _memory.load_profile(user_id)
    return PreferenceResponse(
        user_id=profile.user_id,
        price_sensitivity=profile.price_sensitivity,
        liked_brands=profile.liked_brands,
        disliked_brands=profile.disliked_brands,
        feature_priorities=profile.feature_priorities,
        rating_risk_tolerance=profile.rating_risk_tolerance,
        accept_count=len(profile.accept_log),
        reject_count=len(profile.reject_log),
    )


@router.patch("/{user_id}", response_model=PreferenceResponse)
async def update_preferences(
    user_id: str, body: PreferenceUpdateRequest
) -> PreferenceResponse:
    """
    Manually update preference fields for a user.

    TODO
    ----
    - Implement real update logic once Mem0 is wired in V2
    - For V1: write fields directly into a local preferences store
    """
    profile = _memory.load_profile(user_id)

    if body.price_sensitivity is not None:
        profile.price_sensitivity = body.price_sensitivity
    if body.liked_brands is not None:
        profile.liked_brands = body.liked_brands
    if body.disliked_brands is not None:
        profile.disliked_brands = body.disliked_brands

    return PreferenceResponse(
        user_id=profile.user_id,
        price_sensitivity=profile.price_sensitivity,
        liked_brands=profile.liked_brands,
        disliked_brands=profile.disliked_brands,
        feature_priorities=profile.feature_priorities,
        rating_risk_tolerance=profile.rating_risk_tolerance,
        accept_count=len(profile.accept_log),
        reject_count=len(profile.reject_log),
    )
