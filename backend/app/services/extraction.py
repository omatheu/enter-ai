"""Application service that orchestrates the optimized extraction pipeline."""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, Iterable, Optional

from ..cache import MemoryCache
from ..extractors import HeuristicExtractor, LLMExtractor, PDFExtractor, Validator
from ..models import ExtractionMetadata, ExtractionRequest, ExtractionResult, FieldResult
from ..schema import SchemaLearner

LOGGER = logging.getLogger(__name__)


class ExtractionService:
    """Coordinates PDF parsing, heuristics, cache, and LLM field extraction."""

    def __init__(
        self,
        pdf_extractor: Optional[PDFExtractor] = None,
        llm_extractor: Optional[LLMExtractor] = None,
        heuristic_extractor: Optional[HeuristicExtractor] = None,
        validator: Optional[Validator] = None,
        cache: Optional[MemoryCache] = None,
        schema_learner: Optional[SchemaLearner] = None,
    ) -> None:
        self.pdf_extractor = pdf_extractor or PDFExtractor()
        self.llm_extractor = llm_extractor or LLMExtractor()
        self.heuristic_extractor = heuristic_extractor or HeuristicExtractor()
        self.validator = validator or Validator()
        self.cache = cache or MemoryCache()
        self.schema_learner = schema_learner or SchemaLearner()

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        LOGGER.info("Starting extraction for %s", request.label)

        cache_key = self._build_cache_key(request)
        cached_payload = self.cache.get_pdf_result(cache_key)
        if cached_payload:
            LOGGER.info("Cache hit for %s", request.label)
            cached_result = ExtractionResult.model_validate(cached_payload)
            cached_result.metadata.source = "cache"
            return cached_result

        text = self.pdf_extractor.extract_text(request.pdf_path)
        tables = self.pdf_extractor.extract_tables(request.pdf_path)

        field_values: Dict[str, Any] = {}
        field_sources: Dict[str, str] = {}
        llm_schema: Dict[str, str] = {}

        for field, description in request.extraction_schema.items():
            preferred_source = self.schema_learner.suggest_source_for_field(request.label, field)
            heuristic_value = None
            if preferred_source != "llm":
                heuristic_value = self._run_heuristics(self.heuristic_extractor, field, description or "", text)
                if heuristic_value is not None:
                    is_valid, normalized = self.validator.validate_field(field, heuristic_value, description or "")
                    if is_valid:
                        field_values[field] = normalized
                        field_sources[field] = "heuristic"
                        continue

            llm_schema[field] = description

        llm_metadata: Dict[str, Any] = {}
        if llm_schema:
            llm_fields, llm_metadata = await self.llm_extractor.extract_fields(
                text=text,
                label=request.label,
                schema=llm_schema,
                tables=tables,
            )

            for field, value in llm_fields.items():
                schema_description = request.extraction_schema.get(field, "")
                is_valid, normalized = self.validator.validate_field(field, value, schema_description)
                field_values[field] = normalized if is_valid else None
                field_sources[field] = "llm"

        results = self._build_field_results(
            request.extraction_schema,
            field_values,
            field_sources,
        )

        metadata_source = self._resolve_metadata_source(field_sources)
        metadata_payload: Dict[str, Any] = dict(llm_metadata) if llm_metadata else {}
        metadata_payload["source"] = metadata_source
        extraction_metadata = ExtractionMetadata.model_validate(metadata_payload)

        self.schema_learner.learn_from_result(
            label=request.label,
            schema=request.extraction_schema,
            results=field_values,
            source_analysis=field_sources,
        )

        extraction_result = ExtractionResult(
            label=request.label,
            results=list(results),
            metadata=extraction_metadata,
        )

        self.cache.set_pdf_result(cache_key, extraction_result.model_dump(mode="python"))
        return extraction_result

    @staticmethod
    def _run_heuristics(
        extractor: HeuristicExtractor,
        field: str,
        description: str,
        text: str,
    ) -> Optional[str]:
        heur_value = extractor.extract_by_field_name(field, text)
        if heur_value:
            return heur_value

        heur_value = extractor.extract_by_description(description, text)
        if heur_value:
            return heur_value

        if description:
            heur_value = extractor.extract_enum_values(description, text)
        return heur_value

    @staticmethod
    def _resolve_metadata_source(field_sources: Dict[str, str]) -> str:
        sources = {source for source in field_sources.values()}
        if not sources:
            return "unknown"
        if sources == {"heuristic"}:
            return "heuristic"
        if sources == {"llm"}:
            return "llm"
        return "mixed"

    @staticmethod
    def _build_field_results(
        schema: Dict[str, str],
        values: Dict[str, Any],
        sources: Dict[str, str],
    ) -> Iterable[FieldResult]:
        for field in schema.keys():
            value = values.get(field)
            source = sources.get(field, "not_found")
            confidence = 0.9 if source == "heuristic" else 0.75 if source == "llm" else 0.0
            yield FieldResult(
                field_name=field,
                value=value,
                source=source,
                confidence=confidence,
            )

    @staticmethod
    def _build_cache_key(request: ExtractionRequest) -> str:
        pdf_hash = ExtractionService._hash_pdf(request.pdf_path)
        schema_fingerprint = "|".join(sorted(request.extraction_schema.keys()))
        return f"{request.label}:{pdf_hash}:{schema_fingerprint}"

    @staticmethod
    def _hash_pdf(pdf_path: str) -> str:
        hasher = hashlib.sha1()
        with open(pdf_path, "rb") as pdf_file:
            while chunk := pdf_file.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
