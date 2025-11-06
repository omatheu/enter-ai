from app.schema.confidence import ConfidenceScorer


def test_confidence_scoring_for_validated_heuristic():
    score = ConfidenceScorer.score_extraction(
        field="cpf",
        value="123.456.789-00",
        description="Documento CPF do titular",
        source="heuristic",
        context="Documento CPF do titular",
        validated=True,
    )
    assert 0.0 < score <= 0.99


def test_retry_policy_for_critical_field():
    assert ConfidenceScorer.should_retry_with_llm(0.8, "cpf") is True
    assert ConfidenceScorer.should_retry_with_llm(0.9, "cpf") is False


def test_retry_policy_for_generic_field():
    assert ConfidenceScorer.should_retry_with_llm(0.77, "nome") is True
    assert ConfidenceScorer.should_retry_with_llm(0.80, "nome") is False
