"""Confidence scoring utilities for extracted fields."""

from __future__ import annotations

import math
from typing import Any


class ConfidenceScorer:
    """Computes confidence scores for extracted fields and retry policies."""

    SOURCE_BASE = {
        "cache": 0.98,
        "heuristic": 0.70,
        "heuristic_retry": 0.73,
        "template": 0.78,
        "llm": 0.88,
        "llm_retry": 0.90,
        "llm_refined": 0.92,
        "not_found": 0.0,
    }

    CRITICAL_FIELDS = {
        "cpf",
        "cnpj",
        "email",
        "telefone",
        "celular",
        "data",
        "nascimento",
        "emissao",
        "valor",
        "total",
    }

    @staticmethod
    def score_extraction(
        field: str,
        value: Any,
        description: str,
        source: str,
        context: str = "",
        validated: bool = False,
    ) -> float:
        """Return a 0.0-1.0 confidence score for a field."""

        if value in (None, "", [], {}, ()):
            return 0.0

        base = ConfidenceScorer.SOURCE_BASE.get(source, 0.6)

        if validated:
            base += 0.1

        if ConfidenceScorer._looks_numeric(value):
            base += 0.03

        field_lower = field.lower()
        if field_lower in ConfidenceScorer.CRITICAL_FIELDS:
            base -= 0.02  # critical fields require higher scrutiny

        if description and "aproximado" in description.lower():
            base -= 0.05

        if context and len(context) < 40:
            base += 0.02

        return round(max(0.0, min(base, 0.99)), 2)

    @staticmethod
    def should_retry_with_llm(confidence: float, field: str) -> bool:
        """Decide if we should attempt a more expensive recovery step."""

        field_lower = field.lower()
        threshold = 0.78
        if field_lower in ConfidenceScorer.CRITICAL_FIELDS:
            threshold = 0.85
        return confidence < threshold

    @staticmethod
    def _looks_numeric(value: Any) -> bool:
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            raw = value.replace(".", "").replace(",", "").replace(" ", "")
            return raw.isdigit()
        return False
