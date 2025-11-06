"""Fallback strategies to recover values when initial extraction fails."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Tuple

from ..schema import SchemaLearner
from .heuristics import HeuristicExtractor
from .llm_extractor import LLMExtractor
from .validator import Validator

LOGGER = logging.getLogger(__name__)


async def extract_with_recovery(
    field: str,
    description: str,
    text: str,
    label: str,
    heuristic_extractor: HeuristicExtractor,
    validator: Validator,
    llm_extractor: LLMExtractor,
    schema_learner: SchemaLearner,
    tables: Optional[list] = None,
    context_text: Optional[str] = None,
) -> Tuple[Optional[Any], str, Dict[str, Any]]:
    """Attempt to recover a field value using progressively more expensive strategies.

    Returns a tuple ``(value, source, metadata)`` where ``metadata`` contains any LLM statistics.
    """

    LOGGER.info("Recovery flow started for field '%s'", field)

    # 1. Retry heuristics with relaxed matching
    heuristic_value = _retry_heuristics(field, description, text, heuristic_extractor)
    if heuristic_value is not None:
        is_valid, normalized = validator.validate_field(field, heuristic_value, description)
        if is_valid:
            LOGGER.info("Recovery success via heuristic retry for field '%s'", field)
            return normalized, "heuristic_retry", {}

    # 2. Template-based attempt using patterns learned previously
    template_value = _match_with_template(field, text, schema_learner.get_patterns(label))
    if template_value is not None:
        is_valid, normalized = validator.validate_field(field, template_value, description)
        if is_valid:
            LOGGER.info("Recovery success via template pattern for field '%s'", field)
            return normalized, "template", {}

    # 3. Focused LLM retry with single-field schema
    llm_single_schema = {field: description or f"Valor para o campo {field}"}
    base_context = context_text or text

    llm_result, llm_meta = await llm_extractor.extract_fields(
        text=base_context,
        label=label,
        schema=llm_single_schema,
        tables=tables,
    )

    candidate = llm_result.get(field)
    is_valid, normalized = validator.validate_field(field, candidate, description)
    if is_valid and normalized not in (None, "", []):
        LOGGER.info("Recovery success via LLM retry for field '%s'", field)
        return normalized, "llm_retry", llm_meta

    # 4. Expanded context retry: include previously learned example when available
    patterns = schema_learner.get_patterns(label)
    example_value = patterns.get(field, {}).get("example")
    augmented_description = description
    if example_value:
        augmented_description = f"{description} (exemplo anterior: {example_value})"

    llm_result, llm_meta_expanded = await llm_extractor.extract_fields(
        text=base_context,
        label=label,
        schema={field: augmented_description},
        tables=tables,
    )
    candidate = llm_result.get(field)
    is_valid, normalized = validator.validate_field(field, candidate, description)
    if is_valid and normalized not in (None, "", []):
        LOGGER.info("Recovery success via LLM expanded context for field '%s'", field)
        metadata = dict(llm_meta_expanded)
        metadata["step"] = "expanded_context"
        return normalized, "llm_refined", metadata

    LOGGER.info("Recovery failed for field '%s'", field)
    return None, "not_found", {}


def _retry_heuristics(
    field: str,
    description: str,
    text: str,
    heuristic_extractor: HeuristicExtractor,
) -> Optional[str]:
    """Run an additional, more permissive heuristic attempt."""

    value = heuristic_extractor.extract_by_field_name(field, text)
    if value:
        return value

    value = heuristic_extractor.extract_by_description(description, text)
    if value:
        return value

    # Relaxed search: look for enum matches even without explicit hints
    candidates = re.findall(rf"{re.escape(field)}\s*[:\-]\s*([^\n]+)", text, flags=re.IGNORECASE)
    if candidates:
        return candidates[0].strip()

    return None


def _match_with_template(field: str, text: str, label_patterns: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Try to match previously seen examples with a generalized regex."""

    field_pattern = label_patterns.get(field)
    if not field_pattern:
        return None

    example = field_pattern.get("example")
    if not isinstance(example, str) or not example:
        return None

    generalized = _generalize_example(example)
    if not generalized:
        return None

    match = re.search(generalized, text, flags=re.IGNORECASE)
    if match:
        return match.group().strip()
    return None


def _generalize_example(example: str) -> Optional[str]:
    """Convert a literal example into a regex pattern tolerant to digits/letters variance."""

    if not example:
        return None

    pattern_parts = []
    for char in example:
        if char.isdigit():
            pattern_parts.append(r"\d")
        elif char.isalpha():
            if char.isupper():
                pattern_parts.append(r"[A-Z]")
            elif char.islower():
                pattern_parts.append(r"[a-z]")
            else:
                pattern_parts.append(r"[A-Za-z]")
        else:
            pattern_parts.append(re.escape(char))

    if not pattern_parts:
        return None

    pattern = "".join(pattern_parts)
    # Allow optional whitespace variations
    pattern = pattern.replace(r"\ ", r"\s+")
    return pattern
