"""Application service that orchestrates the validated extraction pipeline."""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, Iterable, Optional

from ..cache import MemoryCache
from ..config import get_settings
from ..extractors import (
    HeuristicExtractor,
    LLMExtractor,
    PDFExtractor,
    Validator,
    extract_with_recovery,
)
from ..models import ExtractionMetadata, ExtractionRequest, ExtractionResult, FieldResult
from ..schema import ConfidenceScorer, SchemaLearner
from ..utils import ProfileCollector, build_compact_context

LOGGER = logging.getLogger(__name__)


class ExtractionService:
    """Coordinates PDF parsing, heuristics, recovery, and LLM field extraction."""

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
        settings = get_settings()
        self.llm_context_chars = min(2500, settings.extraction_max_chars)
        self.max_table_rows = 40

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        LOGGER.info("Starting extraction for %s", request.label)

        cache_key = self._build_cache_key(request)
        cached_payload = self.cache.get_pdf_result(cache_key)
        if cached_payload:
            LOGGER.info("Cache hit for %s", request.label)
            cached_result = ExtractionResult.model_validate(cached_payload)
            cached_result.metadata.source = "cache"
            return cached_result

        profiler = ProfileCollector()
        text: str
        tables: Any
        field_values: Dict[str, Any]
        field_sources: Dict[str, str]
        results_list: list[FieldResult]
        metadata_payload: Dict[str, Any]

        with profiler.track("total_ms"):
            with profiler.track("pdf_text_ms"):
                text = self.pdf_extractor.extract_text(request.pdf_path)
            with profiler.track("pdf_tables_ms"):
                tables = self.pdf_extractor.extract_tables(request.pdf_path)
            tables = self._limit_tables(tables, self.max_table_rows)
            learned_patterns = self.schema_learner.get_patterns(request.label)

            field_details: Dict[str, Dict[str, Any]] = {
                field: {
                    "value": None,
                    "source": "not_found",
                    "confidence": 0.0,
                    "validated": False,
                    "needs_retry": False,
                }
                for field in request.extraction_schema
            }

            llm_schema: Dict[str, str] = {}
            metadata_aggregate: Dict[str, Any] = {
                "duration_ms": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "model": None,
            }
            had_llm_call = False

            for field, description in request.extraction_schema.items():
                info = field_details[field]
                preferred_source = self.schema_learner.suggest_source_for_field(request.label, field)

                heuristic_value = None
                if preferred_source != "llm":
                    with profiler.track("heuristics_ms"):
                        heuristic_value = self._run_heuristics(
                            self.heuristic_extractor,
                            field,
                            description or "",
                            text,
                        )

                if heuristic_value is not None:
                    with profiler.track("validation_ms"):
                        is_valid, normalized = self.validator.validate_field(
                            field, heuristic_value, description or ""
                        )
                    if is_valid:
                        confidence = ConfidenceScorer.score_extraction(
                            field=field,
                            value=normalized,
                            description=description or "",
                            source="heuristic",
                            context=description or "",
                            validated=True,
                        )
                        info.update(
                            value=normalized,
                            source="heuristic",
                            confidence=confidence,
                            validated=True,
                            needs_retry=ConfidenceScorer.should_retry_with_llm(confidence, field),
                        )

                        if info["needs_retry"]:
                            llm_schema[field] = description
                        continue

                info["needs_retry"] = True
                llm_schema[field] = description

            if llm_schema:
                llm_context = build_compact_context(
                    text,
                    llm_schema,
                    learned_patterns,
                    max_chars=self.llm_context_chars,
                )
                with profiler.track("llm_batch_ms"):
                    llm_fields, llm_metadata = await self.llm_extractor.extract_fields(
                        text=llm_context,
                        label=request.label,
                        schema=llm_schema,
                        tables=tables,
                    )
                self._merge_metadata(metadata_aggregate, llm_metadata)
                profiler.record("llm_ms", llm_metadata.get("duration_ms"))
                had_llm_call = True

                for field, description in llm_schema.items():
                    info = field_details[field]
                    candidate = llm_fields.get(field)
                    with profiler.track("validation_ms"):
                        is_valid, normalized = self.validator.validate_field(field, candidate, description or "")

                    if is_valid and normalized not in (None, "", [], {}):
                        confidence = ConfidenceScorer.score_extraction(
                            field=field,
                            value=normalized,
                            description=description or "",
                            source="llm",
                            context=description or "",
                            validated=True,
                        )
                        if confidence >= info["confidence"]:
                            info.update(
                                value=normalized,
                                source="llm",
                                confidence=confidence,
                                validated=True,
                            )
                    info["needs_retry"] = ConfidenceScorer.should_retry_with_llm(info["confidence"], field)
                    if info["value"] is None:
                        info["needs_retry"] = True

            for field, description in request.extraction_schema.items():
                info = field_details[field]
                if not info.get("needs_retry", False):
                    continue
                if info.get("value") is not None:
                    continue

                with profiler.track("recovery_ms"):
                    field_context = build_compact_context(
                        text,
                        {field: description or ""},
                        learned_patterns,
                        max_chars=self.llm_context_chars,
                    )
                    recovered_value, recovered_source, recovery_metadata = await extract_with_recovery(
                        field=field,
                        description=description or "",
                        text=text,
                        context_text=field_context,
                        label=request.label,
                        heuristic_extractor=self.heuristic_extractor,
                        validator=self.validator,
                        llm_extractor=self.llm_extractor,
                        schema_learner=self.schema_learner,
                        tables=tables,
                    )

                if recovery_metadata:
                    self._merge_metadata(metadata_aggregate, recovery_metadata)
                    profiler.record("llm_ms", recovery_metadata.get("duration_ms"))
                    had_llm_call = had_llm_call or "llm" in recovered_source

                if recovered_value is None:
                    info["needs_retry"] = False
                    continue

                with profiler.track("validation_ms"):
                    is_valid, normalized = self.validator.validate_field(field, recovered_value, description or "")
                if not is_valid or normalized in (None, "", [], {}):
                    info["needs_retry"] = False
                    continue

                confidence = ConfidenceScorer.score_extraction(
                    field=field,
                    value=normalized,
                    description=description or "",
                    source=recovered_source,
                    context=description or "",
                    validated=True,
                )

                if confidence >= info["confidence"]:
                    info.update(
                        value=normalized,
                        source=recovered_source,
                        confidence=confidence,
                        validated=True,
                    )

                info["needs_retry"] = False
                had_llm_call = had_llm_call or recovered_source.startswith("llm")

            field_values = {field: details["value"] for field, details in field_details.items()}
            field_sources = {field: details["source"] for field, details in field_details.items()}

            results_list = list(self._build_field_results(field_details))

            metadata_source = self._resolve_metadata_source(field_sources)
            metadata_payload = {}

            if had_llm_call:
                for key in ("duration_ms", "prompt_tokens", "completion_tokens", "total_tokens"):
                    value = metadata_aggregate.get(key)
                    if value:
                        metadata_payload[key] = value
                if metadata_aggregate.get("model"):
                    metadata_payload["model"] = metadata_aggregate["model"]

            metadata_payload["source"] = metadata_source

        profiling_snapshot = profiler.snapshot()
        if profiling_snapshot:
            metadata_payload["profiling"] = profiling_snapshot

        self.schema_learner.learn_from_result(
            label=request.label,
            schema=request.extraction_schema,
            results=field_values,
            source_analysis=field_sources,
        )

        extraction_metadata = ExtractionMetadata.model_validate(metadata_payload)
        extraction_result = ExtractionResult(
            label=request.label,
            results=results_list,
            metadata=extraction_metadata,
            flat=dict(field_values),
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
        sources = {source for source in field_sources.values() if source != "not_found"}
        if not sources:
            return "unknown"
        if sources == {"heuristic"}:
            return "heuristic"
        if sources == {"llm"}:
            return "llm"
        if sources == {"template"}:
            return "template"
        return "mixed"

    @staticmethod
    def _build_field_results(field_details: Dict[str, Dict[str, Any]]) -> Iterable[FieldResult]:
        for field, details in field_details.items():
            yield FieldResult(
                field_name=field,
                value=details["value"],
                source=details["source"],
                confidence=round(details["confidence"], 2),
            )

    @staticmethod
    def _merge_metadata(target: Dict[str, Any], new: Dict[str, Any]) -> None:
        if not isinstance(new, dict):
            return

        for key in ("duration_ms", "prompt_tokens", "completion_tokens", "total_tokens"):
            value = new.get(key)
            if value is None:
                continue
            try:
                target[key] = target.get(key, 0) + int(value)
            except (TypeError, ValueError):
                continue

        model = new.get("model")
        if model:
            target["model"] = model

    @staticmethod
    def _limit_tables(tables: Any, max_rows: int = 40) -> Any:
        if not isinstance(tables, list):
            return tables
        if len(tables) <= max_rows:
            return tables
        return tables[:max_rows]

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
