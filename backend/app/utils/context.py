"""Utilities to shrink raw PDF text to a compact context for LLM usage."""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, List, Tuple


def build_compact_context(
    full_text: str,
    schema: Dict[str, str],
    learned_patterns: Dict[str, Dict[str, str]] | None = None,
    max_chars: int = 2500,
    window: int = 240,
) -> str:
    """Return a reduced text containing only the most relevant segments.

    The strategy:
    1. Gather keywords from field names, descriptions, and learned examples.
    2. For each keyword locate occurrences in the document.
    3. Extract sliding windows around occurrences and merge them.
    4. If nothing matches, fall back to the start of the document.
    """

    if len(full_text) <= max_chars:
        return full_text

    keywords = _collect_keywords(schema, learned_patterns or {})
    segments: List[Tuple[int, str]] = []
    normalized_text = _normalize(full_text)
    used_spans: List[tuple[int, int]] = []

    for keyword in keywords:
        if len(keyword) < 3:
            continue
        needle = _normalize(keyword)
        if len(needle) < 3:
            continue

        pattern = re.escape(needle)
        for match in re.finditer(pattern, normalized_text):
            idx = match.start()
            segment_start = max(0, idx - window)
            segment_end = min(len(full_text), idx + len(needle) + window)
            if not _overlaps(segment_start, segment_end, used_spans):
                segments.append((segment_start, full_text[segment_start:segment_end].strip()))
                used_spans.append((segment_start, segment_end))

    # Fallback: take the first max_chars chunk
    if not segments:
        return full_text[:max_chars]

    compact = _join_segments(segments, max_chars)
    if compact:
        return compact
    return full_text[:max_chars]


def _collect_keywords(schema: Dict[str, str], learned_patterns: Dict[str, Dict[str, str]]) -> Iterable[str]:
    keywords: set[str] = set()

    for field_name, description in schema.items():
        keywords.update(_tokenize(field_name))
        keywords.update(_tokenize(description))

        example = (learned_patterns.get(field_name) or {}).get("example")
        if example:
            keywords.update(_tokenize(example))

    return keywords


def _tokenize(text: str) -> Iterable[str]:
    for token in re.split(r"[^A-Za-z0-9]+", text or ""):
        token = token.strip()
        if len(token) >= 3:
            yield token


def _overlaps(start: int, end: int, spans: List[tuple[int, int]]) -> bool:
    for span_start, span_end in spans:
        if max(span_start, start) < min(span_end, end):
            return True
    return False


def _join_segments(segments: List[Tuple[int, str]], max_chars: int) -> str:
    compact_parts: List[str] = []
    current_size = 0

    for _, segment in sorted(segments, key=lambda item: item[0]):
        segment = segment.strip()
        if not segment:
            continue
        addition = segment if current_size == 0 else f"\n\n{segment}"
        if current_size + len(addition) > max_chars:
            continue
        compact_parts.append(segment)
        current_size += len(addition)

    if not compact_parts:
        return ""
    return "\n\n".join(compact_parts)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()
