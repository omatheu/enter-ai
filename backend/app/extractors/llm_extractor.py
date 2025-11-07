"""LLM-based field extraction utilities."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

from openai import AsyncOpenAI

from ..config import get_openai_api_key, get_settings

LOGGER = logging.getLogger(__name__)


class LLMExtractor:
    """Calls OpenAI models to extract structured data from text."""

    _client: Optional[AsyncOpenAI] = None

    @classmethod
    def _get_client(cls) -> AsyncOpenAI:
        if cls._client is None:
            api_key = get_openai_api_key()
            cls._client = AsyncOpenAI(api_key=api_key)
        return cls._client

    @staticmethod
    async def extract_fields(
        text: str,
        label: str,
        schema: Dict[str, str],
        tables: Optional[list] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Extract every field defined in ``schema`` using a single LLM call."""

        settings = get_settings()
        truncated_text = text[: settings.extraction_max_chars]
        LOGGER.info("Calling LLM for label '%s' with %s chars", label, len(truncated_text))

        schema_json = json.dumps(schema, ensure_ascii=False, indent=2)
        tables_json = json.dumps(tables or [], ensure_ascii=False, indent=2)

        # Optimized prompt to reduce tokens while maintaining quality
        prompt = (
            "Extract structured data from PDF text. Return only valid JSON mapping field names to values.\n"
            "Use null for missing values."
        )

        user_content = (
            f"Label: {label}\n"
            f"Fields:\n{schema_json}\n"
            f"Text:\n{truncated_text}\n"
        )

        if tables_json != "[]":
            user_content += f"\nExtracted tables (rows):\n{tables_json}\n"

        client = LLMExtractor._get_client()
        started = time.perf_counter()

        # Prepare request parameters
        params: Dict[str, Any] = {
            "model": settings.openai_model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
        }

        # Only add temperature if not default (1.0) to avoid issues with some models
        if settings.temperature != 1.0:
            params["temperature"] = settings.temperature

        response = await client.chat.completions.create(**params)
        duration_ms = int((time.perf_counter() - started) * 1000)

        LOGGER.debug("LLM raw response: %s", response)

        raw_content = response.choices[0].message.content or "{}"
        extracted = json.loads(raw_content)

        usage = response.usage.model_dump() if response.usage else {}
        metadata = {
            "model": settings.openai_model,
            "duration_ms": duration_ms,
            **usage,
        }

        return extracted, metadata
