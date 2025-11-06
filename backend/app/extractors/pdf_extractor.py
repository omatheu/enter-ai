"""PDF extraction utilities built on pdfplumber."""

from __future__ import annotations

import logging
from typing import List, Sequence

import pdfplumber

LOGGER = logging.getLogger(__name__)


class PDFExtractor:
    """Thin wrapper around pdfplumber for text and table extraction."""

    @staticmethod
    def extract_text(pdf_path: str) -> str:
        """Return concatenated text from every page of the PDF."""

        LOGGER.debug("Extracting text from PDF: %s", pdf_path)
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for index, page in enumerate(pdf.pages):
                content = page.extract_text() or ""
                LOGGER.debug("Page %s text length: %s", index, len(content))
                pages_text.append(content)
        return "\n\n".join(pages_text).strip()

    @staticmethod
    def extract_tables(pdf_path: str) -> List[Sequence[str]]:
        """Extract table rows from the PDF when available."""

        LOGGER.debug("Extracting tables from PDF: %s", pdf_path)
        table_rows: List[Sequence[str]] = []
        with pdfplumber.open(pdf_path) as pdf:
            for index, page in enumerate(pdf.pages):
                tables = page.extract_tables() or []
                LOGGER.debug("Page %s yielded %s tables", index, len(tables))
                for table in tables:
                    for row in table:
                        if row:
                            table_rows.append(tuple(cell or "" for cell in row))
        return table_rows
