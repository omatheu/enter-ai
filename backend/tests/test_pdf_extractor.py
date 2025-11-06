from pathlib import Path

from app.extractors.pdf_extractor import PDFExtractor

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "docs" / "files"


def test_extract_text_returns_content():
    pdf_path = FIXTURE_DIR / "oab_1.pdf"
    text = PDFExtractor.extract_text(str(pdf_path))
    assert isinstance(text, str)
    assert len(text) > 0


def test_extract_tables_returns_list():
    pdf_path = FIXTURE_DIR / "oab_1.pdf"
    tables = PDFExtractor.extract_tables(str(pdf_path))
    assert isinstance(tables, list)
