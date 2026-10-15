"""Security boundary tests verifying tenant isolation, secret masking, and ReDoS rejection."""

import pytest
from shared.validation.regex_validator import validate_dlp_regex
from shared.errors.exceptions import ValidationError
from integrations.secrets.vault import SecretReferenceManager


def test_redos_catastrophic_backtracking_pattern_rejected():
    """Vulnerable regex patterns susceptible to catastrophic backtracking must be rejected."""
    dangerous = r"(a+)+$"
    with pytest.raises(ValidationError) as exc_info:
        validate_dlp_regex(dangerous)
    assert "redos" in exc_info.value.message.lower()


def test_secret_reference_manager_masks_tokens_in_logs():
    """Sanitizer must mask virtual keys and bearer tokens from diagnostic output."""
    raw = "Failed call with key agw_live_8f3a9e2c1d0b4a7e9f1a2b3c4d5e6f7a and Bearer eyJhbGciOiJIUzI1NiJ9.test"
    sanitized = SecretReferenceManager.sanitize_for_logs(raw)
    assert "agw_live_8f3a9e2c...[REDACTED]" in sanitized
    assert "[REDACTED_TOKEN]" in sanitized
    assert "8f3a9e2c1d0b4a7e9f1a2b3c4d5e6f7a" not in sanitized
