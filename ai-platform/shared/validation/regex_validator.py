"""Regex validation and ReDoS safety analysis for PromptGuard DLP rules."""

import re
from typing import List
from shared.errors.exceptions import ValidationError

# Patterns susceptible to catastrophic backtracking (ReDoS)
DANGEROUS_PATTERNS = [
    r"(\w+\+)+",
    r"([a-zA-Z0-9]+)+",
    r"(\.\*)+",
    r"([0-9]+\*)+",
]


def validate_dlp_regex(pattern: str) -> None:
    """Validate regex compilation and check for dangerous nested quantifiers."""
    if not pattern:
        raise ValidationError("DLP regex pattern cannot be empty")

    try:
        re.compile(pattern)
    except re.error as e:
        raise ValidationError(
            f"Invalid regular expression: {str(e)}",
            details=[{"field": "regex", "issue": "syntax_error", "error": str(e)}],
        )

    for danger in DANGEROUS_PATTERNS:
        if re.search(danger, pattern):
            raise ValidationError(
                "Regex pattern rejected due to potential ReDoS vulnerability (nested quantifiers detected)",
                details=[{"field": "regex", "issue": "redos_vulnerability"}],
            )
