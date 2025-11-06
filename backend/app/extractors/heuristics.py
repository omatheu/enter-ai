"""Heuristic-based field extraction helpers."""

from __future__ import annotations

import re
from typing import Optional


class HeuristicExtractor:
    """Provides lightweight, regex-driven extraction strategies."""

    PATTERNS = {
        "cpf": r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",
        "cnpj": r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b",
        "email": r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
        "telefone": r"\b(?:\+?55\s*)?\(?\d{2}\)?[\s-]*9?\d{4}[\s-]*\d{4}\b",
        "data": r"\b\d{1,2}/\d{1,2}/\d{4}\b",
        "cep": r"\b\d{5}-?\d{3}\b",
        "placa": r"\b[a-zA-Z]{3}-?\d{4}\b",
        "valor": r"R?\$\s*\d{1,3}(?:\.\d{3})*,\d{2}",
        "numero_documento": r"\b\d{6,12}\b",
        "subsecao": r"Conselho\s+Seccional\s*-\s*[^\n]+",
    }

    KEYWORD_TO_PATTERN = {
        "cpf": "cpf",
        "cnpj": "cnpj",
        "email": "email",
        "mail": "email",
        "telefone": "telefone",
        "celular": "telefone",
        "phone": "telefone",
        "data": "data",
        "nascimento": "data",
        "emissao": "data",
        "cep": "cep",
        "placa": "placa",
        "valor": "valor",
        "total": "valor",
        "numero": "numero_documento",
        "documento": "numero_documento",
        "subsecao": "subsecao",
    }

    ENUM_HINTS = ("pode ser", "opções", "options", "um dos", "one of")

    @classmethod
    def _run_pattern(cls, pattern: str, text: str) -> Optional[str]:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group().strip()
        return None

    @classmethod
    def extract_by_field_name(cls, field: str, text: str) -> Optional[str]:
        """Attempt extraction using the field name as hint."""

        field_normalized = field.lower()
        for keyword, pattern_name in cls.KEYWORD_TO_PATTERN.items():
            if keyword in field_normalized:
                pattern = cls.PATTERNS.get(pattern_name)
                if pattern:
                    value = cls._run_pattern(pattern, text)
                    if value:
                        return value
        return None

    @classmethod
    def extract_by_description(cls, desc: str, text: str) -> Optional[str]:
        """Attempt extraction using schema description hints."""

        description = desc.lower()
        for keyword, pattern_name in cls.KEYWORD_TO_PATTERN.items():
            if keyword in description:
                pattern = cls.PATTERNS.get(pattern_name)
                if pattern:
                    value = cls._run_pattern(pattern, text)
                    if value:
                        return value
        return None

    @classmethod
    def extract_enum_values(cls, desc: str, text: str) -> Optional[str]:
        """If the description lists allowed values, try to find one in the PDF text."""

        description = desc.lower()
        if not any(hint in description for hint in cls.ENUM_HINTS):
            return None

        options = cls._parse_enum_options(description)
        if not options:
            return None

        for option in options:
            match = re.search(rf"\b{re.escape(option)}\b", text, flags=re.IGNORECASE)
            if match:
                return match.group().strip()
        return None

    @staticmethod
    def _parse_enum_options(description: str) -> list[str]:
        """Return a list of enum-like options hinted in the description."""

        # Look for structures like "pode ser A, B ou C"
        enum_match = re.search(
            r"(?:pode ser|opções|options|um dos|one of)\s*[:\-]?\s*(.+)",
            description,
        )
        if not enum_match:
            return []

        enum_text = enum_match.group(1)

        # Split on common delimiters while removing filler words
        raw_options = re.split(r"[,/]| ou | or ", enum_text)
        cleaned = []
        for option in raw_options:
            token = option.strip(" .:-").lower()
            if token and token not in {"", "etc"}:
                cleaned.append(token)
        return cleaned
