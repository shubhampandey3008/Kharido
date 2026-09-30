"""
LangGraph GraphState definition.

All pipeline nodes read from and write into this TypedDict.
LangGraph merges partial dicts returned by each node into the running state.

The `evidence` field uses an `operator.add` reducer so that CandidateEvidence
objects returned by parallel review_analysis worker nodes are accumulated
into a list rather than overwriting each other.
"""

from __future__ import annotations

import operator
from typing import Annotated, Optional

from typing_extensions import TypedDict

from kharido.models import (
    CandidateEvidence,
    CategoryCriteria,
    ParsedQuery,
    PreferenceProfile,
    Product,
    Recommendation,
)


class GraphState(TypedDict, total=False):
    """
    Shared state threaded through every node in the Kharido pipeline.

    Field lifecycle
    ---------------
    raw_query           set at graph entry, never modified
    parsed_query        set by query_understanding node
    criteria            set by criteria_research node
    candidates          set by product_search node
    evidence            accumulated by review_analysis worker nodes (Send API fan-in)
    recommendation      set by recommendation node
    backup              set by recommendation node (revealed only on user request)
    preference_profile  read/written by recommendation node via PreferenceMemory
    thread_id           set at graph entry from LangGraph config
    error               set by any node on unrecoverable failure
    """

    raw_query: str
    parsed_query: Optional[ParsedQuery]
    criteria: Optional[CategoryCriteria]
    candidates: list[Product]
    # Annotated reducer: worker outputs are appended, not overwritten
    evidence: Annotated[list[CandidateEvidence], operator.add]
    recommendation: Optional[Recommendation]
    backup: Optional[Recommendation]
    preference_profile: Optional[PreferenceProfile]
    thread_id: str
    error: Optional[str]
