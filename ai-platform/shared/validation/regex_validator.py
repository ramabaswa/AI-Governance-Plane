"""Regex validation and ReDoS safety analysis for PromptGuard DLP rules."""

import re

from shared.errors.exceptions import ValidationError


def _has_nested_unbounded_quantifier(pattern: str) -> bool:
    groups = [False]
    in_character_class = False
    index = 0

    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            index += 2
            continue
        if in_character_class:
            if char == "]":
                in_character_class = False
        elif char == "[":
            in_character_class = True
        elif char == "(":
            groups.append(False)
        elif char == ")":
            if len(groups) == 1:
                continue
            contains_unbounded = groups.pop()
            quantifier_end, unbounded = _following_quantifier(pattern, index + 1)
            if unbounded and contains_unbounded:
                return True
            groups[-1] = groups[-1] or contains_unbounded or unbounded
            index = quantifier_end - 1
        elif char in "*+":
            groups[-1] = True
        elif char == "{":
            quantifier_end, unbounded = _following_quantifier(pattern, index)
            if quantifier_end > index + 1:
                groups[-1] = groups[-1] or unbounded
                index = quantifier_end - 1
        index += 1
    return False


def _following_quantifier(pattern: str, index: int) -> tuple[int, bool]:
    if index >= len(pattern):
        return index, False
    if pattern[index] in "*+":
        return index + 1, True
    if pattern[index] != "{":
        return index, False
    match = re.match(r"\{(\d+)(?:,(\d*)?)?\}", pattern[index:])
    if match is None:
        return index, False
    unbounded = match.group(2) == "" if "," in match.group(0) else False
    return index + len(match.group(0)), unbounded


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

    if _has_nested_unbounded_quantifier(pattern):
        raise ValidationError(
            "Regex pattern rejected due to potential ReDoS vulnerability (nested quantifiers detected)",
            details=[{"field": "regex", "issue": "redos_vulnerability"}],
        )
