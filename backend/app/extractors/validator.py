"""Basic field validators used after extraction."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional, Tuple


class Validator:
    """Provides lightweight format checks for common field types."""

    CPF_REGEX = re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$")
    CPF_DIGITS_REGEX = re.compile(r"^\d{11}$")
    EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    PHONE_REGEX = re.compile(r"^(?:\+?55)?\s*\(?\d{2}\)?\s*9?\d{4}-?\d{4}$")
    DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d")

    @staticmethod
    def validate_cpf(value: str) -> bool:
        """Validate CPF format (structure only, not checksum)."""

        if Validator.CPF_REGEX.match(value):
            digits = re.sub(r"\D", "", value)
        else:
            digits = re.sub(r"\D", "", value)
            if not Validator.CPF_DIGITS_REGEX.match(digits):
                return False

        if digits == digits[0] * 11:
            return False
        return True

    @staticmethod
    def validate_email(value: str) -> bool:
        return bool(Validator.EMAIL_REGEX.match(value.strip()))

    @staticmethod
    def validate_phone(value: str) -> bool:
        return bool(Validator.PHONE_REGEX.match(value.strip()))

    @staticmethod
    def validate_date(value: str) -> bool:
        for fmt in Validator.DATE_FORMATS:
            try:
                datetime.strptime(value.strip(), fmt)
                return True
            except ValueError:
                continue
        return False

    @staticmethod
    def validate_enum(value: str, allowed: list[str]) -> bool:
        lowered = value.strip().lower()
        return lowered in {item.lower() for item in allowed}

    @staticmethod
    def _detect_enum_options(field_description: str) -> list[str]:
        from .heuristics import HeuristicExtractor  # Lazy import to avoid cycles

        return HeuristicExtractor._parse_enum_options(field_description.lower())

    @staticmethod
    def validate_field(
        field_name: str,
        value: Any,
        field_description: str = "",
    ) -> Tuple[bool, Optional[Any]]:
        """Validate value using lightweight heuristics."""

        if value is None:
            return False, None

        if isinstance(value, str):
            candidate = value.strip()
        else:
            candidate = str(value).strip()

        if not candidate:
            return False, None

        field_lower = field_name.lower()
        desc_lower = field_description.lower()

        if "cpf" in field_lower or "cpf" in desc_lower:
            if Validator.validate_cpf(candidate):
                digits = re.sub(r"\D", "", candidate)
                normalized = (
                    f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"
                    if len(digits) == 11
                    else candidate
                )
                return True, normalized
            return False, None

        if "email" in field_lower or "email" in desc_lower:
            is_valid = Validator.validate_email(candidate)
            return is_valid, candidate if is_valid else None

        if any(word in field_lower for word in ("telefone", "celular", "phone")) or any(
            word in desc_lower for word in ("telefone", "celular", "phone")
        ):
            is_valid = Validator.validate_phone(candidate)
            return is_valid, candidate if is_valid else None

        if any(word in field_lower for word in ("data", "nascimento", "emissao")) or any(
            word in desc_lower for word in ("data", "nascimento", "emissao")
        ):
            if Validator.validate_date(candidate):
                return True, candidate
            return False, None

        enum_options = Validator._detect_enum_options(desc_lower)
        if enum_options:
            is_valid = Validator.validate_enum(candidate, enum_options)
            return is_valid, candidate if is_valid else None

        # Default: accept as string
        return True, candidate
