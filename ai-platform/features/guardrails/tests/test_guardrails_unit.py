import pytest

from features.guardrails.service import validate_prompt_guard_rules
from shared.contracts.route import PromptGuardRule
from shared.errors.exceptions import ValidationError


def test_prompt_guard_validation_accepts_safe_regex_and_rejects_redos():
    validate_prompt_guard_rules([
        PromptGuardRule(name="digits", regex_patterns=[r"\d{4}"]),
    ])
    with pytest.raises(ValidationError, match="ReDoS"):
        validate_prompt_guard_rules([
            PromptGuardRule(name="unsafe", regex_patterns=[r"(\w+)+"]),
        ])
