import json
import logging

from app.core.logging import JSONFormatter, redact_sensitive_data


def test_redact_sensitive_data_masks_secrets() -> None:
    data = {
        "user": "bruno",
        "password": "super_secret_password",
        "api_key": "secret_token_123",
        "csrf_token": "token_abc",
        "nested": {
            "auth_token": "bearer xyz",
            "safe_field": 42,
        },
        "list_data": [
            {"access_token": "tok1"},
            {"name": "fiber_1"},
        ],
    }

    cleaned = redact_sensitive_data(data)
    assert cleaned["user"] == "bruno"
    assert cleaned["password"] == "[REDACTED]"
    assert cleaned["api_key"] == "[REDACTED]"
    assert cleaned["csrf_token"] == "[REDACTED]"
    assert cleaned["nested"]["auth_token"] == "[REDACTED]"
    assert cleaned["nested"]["safe_field"] == 42
    assert cleaned["list_data"][0]["access_token"] == "[REDACTED]"
    assert cleaned["list_data"][1]["name"] == "fiber_1"


def test_json_formatter_produces_valid_json() -> None:
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message with extra info",
        args=(),
        exc_info=None,
    )
    record.user_id = "user-123"
    record.password = "secret"

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Test message with extra info"
    assert "timestamp" in parsed
    assert parsed["extra"]["user_id"] == "user-123"
    assert parsed["extra"]["password"] == "[REDACTED]"
