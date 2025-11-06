"""Simple in-memory cache keyed by PDF hash + schema fingerprint."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional


class MemoryCache:
    """Stores extraction payloads for quick reuse."""

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_pdf_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Return a cached extraction payload if available."""

        payload = self._cache.get(cache_key)
        return deepcopy(payload) if payload is not None else None

    def set_pdf_result(self, cache_key: str, result_payload: Dict[str, Any]) -> None:
        """Store an extraction payload for future requests."""

        self._cache[cache_key] = deepcopy(result_payload)
