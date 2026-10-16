"""Optional enterprise adapters for Solo Enterprise for agentgateway."""

import os
from typing import Dict, Any, Optional


class EnterpriseOptionalAdapter:
    """Provides non-blocking hooks for optional enterprise capabilities."""

    @staticmethod
    def is_enterprise_enabled() -> bool:
        return os.getenv("SOLO_ENTERPRISE_ENABLED", "false").lower() == "true"

    @staticmethod
    def get_extended_pricing_catalog() -> Dict[str, Any]:
        """Return explicit unavailability until a real enterprise adapter is configured."""
        return {
            "status": "not_configured",
            "pricing_catalog": None,
            "sla": None,
        }
