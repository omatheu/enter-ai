"""Application service that orchestrates full extraction pipeline."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, Optional

from ..models import ExtractionRequest, ExtractionResult, FieldResult, ExtractionMetadata
from ..extractors.pdf_extractor import PDFExtractor
from ..extractors.llm_extractor import LLMExtractor

LOGGER = logging.getLogger(__name__)


class ExtractionService:
    """Coordinates PDF parsing and LLM field extraction."""

    def __init__(
        self,
        pdf_extractor: Optional[PDFExtractor] = None,
        llm_extractor: Optional[LLMExtractor] = None,
    ) -> None:
        self.pdf_extractor = pdf_extractor or PDFExtractor()
        self.llm_extractor = llm_extractor or LLMExtractor()

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        LOGGER.info("Starting extraction for %s", request.label)
        text = self.pdf_extractor.extract_text(request.pdf_path)
        tables = self.pdf_extractor.extract_tables(request.pdf_path)

        raw_fields, metadata = await self.llm_extractor.extract_fields(
            text=text,
            label=request.label,
            schema=request.extraction_schema,
            tables=tables,
        )

        results: Iterable[FieldResult] = (
            FieldResult(
                field_name=field,
                value=value,
                source="llm",
                confidence=metadata.get("confidence", 0.0) if isinstance(metadata, dict) else 0.0,
            )
            for field, value in raw_fields.items()
        )

        extraction_metadata = ExtractionMetadata.model_validate(metadata)

        return ExtractionResult(
            label=request.label,
            results=list(results),
            metadata=extraction_metadata,
        )
