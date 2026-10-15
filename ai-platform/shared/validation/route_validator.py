"""Validation rules for gateway routes and upstream backends."""

from urllib.parse import urlparse
from typing import List, Dict, Any
from shared.errors.exceptions import ValidationError


def validate_backend_url(url: str) -> None:
    """
    Validate that backend URL is a valid http/https URL and DOES NOT contain query parameters.
    Query parameters in upstream inference backend URLs are rejected for security and predictability.
    """
    if not url:
        raise ValidationError("Backend URL cannot be empty")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValidationError(
            f"Invalid scheme '{parsed.scheme}'. Backend URL must use 'http' or 'https'",
            details=[{"field": "backend_url", "issue": "invalid_scheme"}],
        )

    if not parsed.netloc:
        raise ValidationError(
            "Backend URL must include a valid host / netloc",
            details=[{"field": "backend_url", "issue": "missing_host"}],
        )

    if parsed.query:
        raise ValidationError(
            "Backend URL query parameters are rejected. Please provide a clean upstream endpoint URL.",
            details=[{
                "field": "backend_url",
                "issue": "query_parameters_forbidden",
                "query": parsed.query,
            }],
        )


def validate_path_prefix(path_prefix: str) -> None:
    """Validate that path prefix begins with '/' and does not contain query parameters or fragments."""
    if not path_prefix or not path_prefix.startswith("/"):
        raise ValidationError(
            "Path prefix must start with '/' (e.g. '/v1/chat/completions')",
            details=[{"field": "path_prefix", "issue": "invalid_prefix"}],
        )
    if "?" in path_prefix or "#" in path_prefix:
        raise ValidationError(
            "Path prefix cannot contain query parameters or fragments",
            details=[{"field": "path_prefix", "issue": "query_parameters_forbidden"}],
        )


def validate_traffic_weights(weights: Dict[str, int]) -> None:
    """Validate that traffic weights sum up to 100%."""
    if not weights:
        return
    if any(not isinstance(weight, int) or weight < 0 or weight > 100 for weight in weights.values()):
        raise ValidationError(
            "Traffic weights must be whole numbers between 0 and 100",
            details=[{"field": "weights", "issue": "invalid_weight"}],
        )
    total = sum(weights.values())
    if total != 100:
        raise ValidationError(
            f"Traffic split weights must sum to exactly 100 (current sum: {total})",
            details=[{"field": "weights", "issue": "invalid_weight_sum", "sum": total}],
        )
