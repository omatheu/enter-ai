import asyncio
from pathlib import Path
from typing import Any, Dict, Tuple

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

    service = ExtractionService(llm_extractor=StubLLMExtractor())
    result = await service.extract(request)

    assert result.label == "carteira_oab"
    assert result.results[0].field_name == "nome"
    assert result.results[0].value == "fake-nome"
    assert result.metadata.model == "stub"
