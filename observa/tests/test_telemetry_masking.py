import copy

import pytest

from observa.security.telemetry_masking import TelemetryMaskingProcessor


def test_masks_sensitive_fields_and_patterns_without_mutating_input():
    payload = [
        {
            "count": 12,
            "customer": {
                "email": "ana@example.com",
                "name": "Ana Silva",
                "note": "Contact ana@example.com",
                "api_key": "secret-value",
            },
        }
    ]
    original = copy.deepcopy(payload)
    processor = TelemetryMaskingProcessor()

    sanitized = processor.process(payload)

    assert sanitized == [
        {
            "count": 12,
            "customer": {
                "email": "[REDACTED]",
                "name": "Ana Silva",
                "note": "Contact [REDACTED]",
                "api_key": "[REDACTED]",
            },
        }
    ]
    assert payload == original


def test_masks_credentials_and_brazilian_document_patterns():
    processor = TelemetryMaskingProcessor()

    sanitized = processor.process(
        {
            "message": (
                "Authorization: Bearer abc.def.ghi CPF 123.456.789-00 "
                "Password=my-secret"
            ),
            "connection_string": "Server=db;Password=secret",
            "details": "postgresql://app:db-secret@db.internal:5432/observa",
        }
    )

    assert sanitized["message"] == (
        "Authorization: [REDACTED] CPF [REDACTED] [REDACTED]"
    )
    assert sanitized["connection_string"] == "[REDACTED]"
    assert "db-secret" not in sanitized["details"]
    assert "[REDACTED]" in sanitized["details"]


def test_preserves_detection_fields_and_masks_nested_custom_field():
    processor = TelemetryMaskingProcessor(
        masked_fields={"identity.document"},
        preserved_fields={"count", "quantidade"},
        patterns=(),
    )

    sanitized = processor.process(
        {"count": 13, "quantidade": 7, "identity": {"document": "123"}}
    )

    assert sanitized == {
        "count": 13,
        "quantidade": 7,
        "identity": {"document": "[REDACTED]"},
    }


def test_rejects_sensitive_detection_field_conflict():
    with pytest.raises(ValueError, match="cannot be both masked and preserved"):
        TelemetryMaskingProcessor(
            masked_fields={"count"},
            preserved_fields={"count"},
            patterns=(),
        )


def test_loads_additional_masking_rules_from_environment(monkeypatch):
    monkeypatch.setenv("OBSERVA_MASKING_FIELDS", "employee_id")
    monkeypatch.setenv("OBSERVA_MASKING_PATTERNS", '["SECRET-[A-Z0-9]+"]')
    monkeypatch.setenv("OBSERVA_MASKING_PRESERVED_FIELDS", "count,quantity")

    processor = TelemetryMaskingProcessor.from_environment()

    assert processor.process({"employee_id": "E-17", "note": "SECRET-ABC"}) == {
        "employee_id": "[REDACTED]",
        "note": "[REDACTED]",
    }


def test_rejects_invalid_pattern_configuration(monkeypatch):
    monkeypatch.setenv("OBSERVA_MASKING_PATTERNS", '["["]')

    with pytest.raises(ValueError, match="invalid telemetry masking pattern"):
        TelemetryMaskingProcessor.from_environment()