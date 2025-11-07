from pathlib import Path
from typing import Any, Dict, Tuple
from unittest.mock import patch

import pytest

from app.models import ExtractionRequest
from app.services.extraction import ExtractionService

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "docs" / "files"


class StubLLMExtractor:
    """Fake extractor returning deterministic data for tests."""

    async def extract_fields(
        self, text: str, label: str, schema: Dict[str, str], tables: Any = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        return {field: f"fake-{field}" for field in schema}, {"model": "stub"}


@pytest.mark.asyncio
async def test_service_returns_expected_structure():
    pdf_path = FIXTURE_DIR / "oab_1.pdf"
    request = ExtractionRequest(
        label="carteira_oab",
        schema={"nome": "Nome"},
        pdf_path=str(pdf_path),
    )

    # Mock settings to avoid needing OPENAI_API_KEY in tests
    with patch("app.services.extraction.get_settings") as mock_settings:
        mock_settings.return_value.extraction_max_chars = 6000
        mock_settings.return_value.openai_api_key = "test-key"
        mock_settings.return_value.openai_model = "gpt-5-mini"
        mock_settings.return_value.temperature = 1.0

        service = ExtractionService(llm_extractor=StubLLMExtractor())
        result = await service.extract(request)

        assert result.label == "carteira_oab"
        assert result.results[0].field_name == "nome"
        assert result.results[0].value == "fake-nome"
        assert result.metadata.model == "stub"
        assert result.metadata.profiling is not None
        assert "total_ms" in result.metadata.profiling
        assert result.flat["nome"] == "fake-nome"
