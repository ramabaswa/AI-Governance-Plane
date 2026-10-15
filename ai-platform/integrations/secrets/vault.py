"""Secret reference manager ensuring zero plaintext credentials in DB or API logs."""

import os
from typing import Optional


class SecretReferenceManager:
    """
    Manages references to Kubernetes Secrets and Vault paths.
    Strict Rule: Plaintext keys are never stored in the database or returned in API responses.
    """

    @staticmethod
    def format_k8s_secret_ref(secret_name: str, key: str = "api-key") -> str:
        """Format a Kubernetes secret pointer."""
        clean_name = secret_name.replace(" ", "-").lower()
        return f"{clean_name}/{key}"

    @staticmethod
    def resolve_secret_for_gateway(secret_ref: str) -> str:
        """
        Produce declarative YAML reference for agentgateway.
        Returns the SecretRef mapping (e.g. secretRef: anthropic-key).
        """
        return secret_ref.split("/")[0]

    @staticmethod
    def sanitize_for_logs(text: str) -> str:
        """Mask potential secrets in diagnostic strings."""
        if not text:
            return ""
        # Redact patterns like sk-..., agw_live_..., Bearer ...
        import re
        text = re.sub(r"(agw_live_[a-zA-Z0-9]{8})[a-zA-Z0-9]+", r"\1...[REDACTED]", text)
        text = re.sub(r"(sk-[a-zA-Z0-9]{4})[a-zA-Z0-9]+", r"\1...[REDACTED]", text)
        text = re.sub(r"(Bearer\s+)[^\s]+", r"\1[REDACTED_TOKEN]", text)
        return text
