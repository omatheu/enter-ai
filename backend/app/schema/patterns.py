"""Stores lightweight heuristics learned per label."""

from __future__ import annotations

from typing import Any, Dict, Optional


class SchemaLearner:
    """Captures observed extraction strategies per label/field."""

    MAX_PATTERNS_PER_LABEL = 50  # Prevent unbounded growth
    MAX_LABELS = 100

    def __init__(self) -> None:
        self.learned: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def learn_from_result(
        self,
        label: str,
        schema: Dict[str, str],
        results: Dict[str, Any],
        source_analysis: Dict[str, str],
    ) -> None:
        """Store how each field was extracted for future hints."""

        # Prevent unbounded growth of labels
        if len(self.learned) >= self.MAX_LABELS:
            return

        label_store = self.learned.setdefault(label, {})

        # Prevent unbounded growth of patterns per label
        if len(label_store) >= self.MAX_PATTERNS_PER_LABEL:
            return

        for field, value in results.items():
            if value in (None, "", [], {}, ()):
                continue
            label_store[field] = {
                "last_source": source_analysis.get(field, "unknown"),
                "example": value,
                "description": schema.get(field, ""),
            }

    def get_patterns(self, label: str) -> Dict[str, Dict[str, Any]]:
        """Return stored patterns for ``label`` if present."""

        return self.learned.get(label, {})

    def suggest_source_for_field(self, label: str, field: str) -> str:
        """Suggest whether a field historically worked better via heuristics or LLM."""

        patterns = self.get_patterns(label)
        field_pattern = patterns.get(field)
        if not field_pattern:
            return "unknown"
        return field_pattern.get("last_source", "unknown") or "unknown"
