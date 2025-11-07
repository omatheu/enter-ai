import pytest

from app.extractors.error_recovery import extract_with_recovery
from app.extractors.heuristics import HeuristicExtractor
from app.extractors.validator import Validator
from app.schema import SchemaLearner


class NullLLMExtractor:
    async def extract_fields(self, *args, **kwargs):
        return {}, {}


@pytest.mark.asyncio
async def test_error_recovery_uses_template_pattern():
    text = "Código localizado: ABC-5678\nOutro dado."

    schema_learner = SchemaLearner()
    schema_learner.learned = {
        "documento": {
            "codigo": {
                "example": "ABC-1234",
                "last_source": "llm",
                "description": "Código alfanumérico",
            }
        }
    }

    value, source, metadata = await extract_with_recovery(
        field="codigo",
        description="Código alfanumérico",
        text=text,
        label="documento",
        heuristic_extractor=HeuristicExtractor(),
        validator=Validator(),
        llm_extractor=NullLLMExtractor(),
        schema_learner=schema_learner,
        tables=None,
    )

    assert value == "ABC-5678"
    assert source == "template"
    assert metadata == {}
