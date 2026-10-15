"""Validation for the regex PromptGuard capability supported in this slice."""

from shared.contracts.route import PromptGuardRule
from shared.validation.regex_validator import validate_dlp_regex


def validate_prompt_guard_rules(rules: list[PromptGuardRule]) -> None:
    for rule in rules:
        for pattern in rule.regex_patterns:
            validate_dlp_regex(pattern)
