"""Pydantic models for extraction requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtractionRequest(BaseModel):
    """Input payload for a single extraction run."""

    model_config = ConfigDict(populate_by_name=True)

    label: str = Field(..., description="Identifier of the document type (e.g. carteira_oab)")
    extraction_schema: Dict[str, str] = Field(
        ...,
        alias="schema",
        description="Mapping of field name to human-readable description"
    )
    pdf_path: str = Field(..., description="Filesystem path to the PDF asset to parse")


class FieldResult(BaseModel):
    """LLM response for a single field."""

    field_name: str
    value: Optional[Any]
    source: str = Field(default="llm", description="What produced the value (heuristic, llm, etc)")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ExtractionMetadata(BaseModel):
    """Diagnostic metadata returned with each extraction."""

    model_config = ConfigDict(populate_by_name=True)

    model: Optional[str] = None
    tokens_prompt: Optional[int] = Field(default=None, alias="prompt_tokens")
    tokens_completion: Optional[int] = Field(default=None, alias="completion_tokens")
    total_tokens: Optional[int] = None
    duration_ms: Optional[int] = Field(default=None, description="Processing time in milliseconds")
    source: str = Field(default="llm")
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    profiling: Optional[Dict[str, int]] = Field(default=None, description="Per-step execution timings in ms")


class ExtractionResult(BaseModel):
    """Response returned to API clients."""

    model_config = ConfigDict(populate_by_name=True)

    label: str
    results: List[FieldResult]
    metadata: ExtractionMetadata
    flat: Dict[str, Optional[Any]] = Field(
        default_factory=dict,
        description="Shallow mapping of field name to extracted value",
    )

    @field_validator("results")
    @classmethod
    def ensure_unique_fields(cls, value: List[FieldResult]) -> List[FieldResult]:
        """Guard against duplicated field names."""

        seen = set()
        for item in value:
            if item.field_name in seen:
                raise ValueError(f"duplicate field '{item.field_name}' in extraction results")
            seen.add(item.field_name)
        return value
