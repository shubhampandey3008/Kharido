"""
Preference Memory service — Mem0 integration.

Stores and retrieves per-user preference signals that personalise the
Recommendation node's scoring weights.

V1: returns cold-start PreferenceProfile with neutral defaults.
    Logs accept/reject events to a JSONL file for V2 seeding.
V2: reads from and writes to Mem0 (cloud or local mode).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog

from kharido.config import get_settings
from kharido.models import PreferenceProfile

log = structlog.get_logger(__name__)


class PreferenceMemoryService:
    """
    Interface to Mem0 for per-user preference storage.

    Design: this is a service (lookup + update), not an agent, because the
    workflow calls it at fixed points — no decide-and-loop required.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._mem0 = None

    def _ensure_mem0(self) -> None:
        """
        Lazily initialise the Mem0 client.

        TODO (V2)
        ---------
        if self._mem0 is None:
            from mem0 import MemoryClient
            self._mem0 = MemoryClient(api_key=self._settings.mem0_api_key)
        or for local mode:
            from mem0 import Memory
            self._mem0 = Memory()
        """
        pass

    def load_profile(self, user_id: str) -> PreferenceProfile:
        """
        Load preference profile for a user.

        Returns cold-start defaults when no history exists (V1).

        TODO (V2)
        ---------
        - Query Mem0 for memories associated with user_id
        - Map memory entries to PreferenceProfile fields
        - Merge with cold-start defaults for missing fields
        """
        log.info("preference_memory.load", user_id=user_id)
        return PreferenceProfile(user_id=user_id)

    def record_accept(self, user_id: str, product_id: str) -> None:
        """
        Record that a user accepted a recommendation.

        TODO (V2)
        ---------
        - Extract brand, price tier, key features from the accepted product
        - Write positive memory entry to Mem0
        """
        log.info("preference_memory.record_accept", user_id=user_id, product_id=product_id)
        self._append_to_log(user_id, product_id, action="accept")

    def record_reject(self, user_id: str, product_id: str) -> None:
        """
        Record that a user rejected a recommendation (asked for alternative).

        TODO (V2)
        ---------
        - Extract brand, price tier, key features from the rejected product
        - Write negative memory entry to Mem0
        """
        log.info("preference_memory.record_reject", user_id=user_id, product_id=product_id)
        self._append_to_log(user_id, product_id, action="reject")

    def _append_to_log(self, user_id: str, product_id: str, action: str) -> None:
        """Append an accept/reject event to a JSONL log for V2 seeding."""
        log_path = self._settings.cache_dir / "preference_log.jsonl"
        entry = {
            "user_id": user_id,
            "product_id": product_id,
            "action": action,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        with log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
