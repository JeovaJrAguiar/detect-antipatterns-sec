import copy
import json
import os
import re
from typing import Any, Iterable, Optional, Pattern, Set, Tuple


REDACTED = "[REDACTED]"
DEFAULT_MASKED_FIELDS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "authorization",
        "cookie",
        "set_cookie",
        "email",
        "cpf",
        "cnpj",
        "phone",
        "telephone",
        "telefone",
        "celular",
        "connection_string",
    }
)
DEFAULT_PRESERVED_FIELDS = frozenset({"count", "quantidade"})
DEFAULT_PATTERNS = (
    r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    r"(?<!\d)(?:\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})(?!\d)",
    r"(?<!\d)(?:\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14})(?!\d)",
    r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*",
    r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token)\s*[:=]\s*['\"]?[^'\"\s,;&]+",
    r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^/\s:@]+:[^@\s/]+@[^/\s]+[^\s]*",
)


class TelemetryMaskingProcessor:
    def __init__(
        self,
        masked_fields: Optional[Iterable[str]] = None,
        preserved_fields: Optional[Iterable[str]] = None,
        patterns: Optional[Iterable[str]] = None,
    ):
        self.masked_fields = self._normalize_fields(
            DEFAULT_MASKED_FIELDS | self._normalize_fields(masked_fields or ())
        )
        self.preserved_fields = self._normalize_fields(
            DEFAULT_PRESERVED_FIELDS | self._normalize_fields(preserved_fields or ())
        )
        conflicts = self.masked_fields & self.preserved_fields
        if conflicts:
            raise ValueError(
                "A telemetry field cannot be both masked and preserved: "
                + ", ".join(sorted(conflicts))
            )

        configured_patterns = DEFAULT_PATTERNS if patterns is None else tuple(patterns)
        try:
            self.patterns: Tuple[Pattern[str], ...] = tuple(
                re.compile(pattern) for pattern in configured_patterns
            )
        except re.error as error:
            raise ValueError("invalid telemetry masking pattern") from error

    @classmethod
    def from_environment(cls) -> "TelemetryMaskingProcessor":
        custom_patterns = os.getenv("OBSERVA_MASKING_PATTERNS", "[]")
        try:
            decoded_patterns = json.loads(custom_patterns)
        except json.JSONDecodeError as error:
            raise ValueError("OBSERVA_MASKING_PATTERNS must be a JSON array of regex strings") from error
        if not isinstance(decoded_patterns, list) or not all(
            isinstance(pattern, str) for pattern in decoded_patterns
        ):
            raise ValueError("OBSERVA_MASKING_PATTERNS must be a JSON array of regex strings")

        return cls(
            masked_fields=os.getenv("OBSERVA_MASKING_FIELDS", "").split(","),
            preserved_fields=os.getenv("OBSERVA_MASKING_PRESERVED_FIELDS", "").split(","),
            patterns=(*DEFAULT_PATTERNS, *decoded_patterns),
        )

    def process(self, data: Any) -> Any:
        return self._process_value(data)

    @staticmethod
    def _normalize_fields(fields: Iterable[str]) -> Set[str]:
        return {field.strip().casefold() for field in fields if field.strip()}

    def _process_value(self, value: Any, path: str = "") -> Any:
        if isinstance(value, dict):
            sanitized = {}
            for key, item in value.items():
                field_name = str(key).casefold()
                field_path = f"{path}.{field_name}" if path else field_name
                if field_name in self.preserved_fields or field_path in self.preserved_fields:
                    sanitized[key] = copy.deepcopy(item)
                elif field_name in self.masked_fields or field_path in self.masked_fields:
                    sanitized[key] = REDACTED
                else:
                    sanitized[key] = self._process_value(item, field_path)
            return sanitized

        if isinstance(value, list):
            return [self._process_value(item, path) for item in value]

        if isinstance(value, str):
            sanitized = value
            for pattern in self.patterns:
                sanitized = pattern.sub(REDACTED, sanitized)
            return sanitized

        return copy.deepcopy(value)


def mask_telemetry(data: Any) -> Any:
    return TelemetryMaskingProcessor.from_environment().process(data)