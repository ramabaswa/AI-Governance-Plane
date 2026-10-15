"""Common Expression Language (CEL) validation for MCP tool policies."""

import re
from shared.errors.exceptions import ValidationError

# Allowed standard CEL variables in agentgateway tool policies
ALLOWED_IDENTIFIERS = {
    "agent", "agent.id", "agent.role", "agent.tenant_id",
    "tool", "tool.name", "tool.arguments",
    "request", "request.headers",
}


def validate_cel_expression(expression: str) -> None:
    """Validate basic syntax of CEL rule for agentgateway tool curation."""
    if not expression or not expression.strip():
        return

    expr = expression.strip()
    # Check balanced parentheses and brackets
    if expr.count("(") != expr.count(")") or expr.count("[") != expr.count("]"):
        raise ValidationError(
            "Mismatched parentheses or brackets in CEL expression",
            details=[{"field": "cel_expression", "issue": "syntax_error"}],
        )

    # Basic keyword sanity
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_\.]*", expr)
    unknown_top_level = []
    for token in tokens:
        top_var = token.split(".")[0]
        if top_var not in ("agent", "tool", "request", "true", "false", "null", "in", "has"):
            # Check if it's a string literal or function
            if top_var not in ("startsWith", "endsWith", "contains", "matches"):
                unknown_top_level.append(token)

    if unknown_top_level:
        # Warning/Validation info
        pass
